"""True 3D Perspective + Phong-Shaded Software Renderer (NumPy + OpenCV AA).

Renders genuine 3D camera perspective (FOV, orbit, dolly, pitch, roll), Phong-lit
triangulated/quad 3D meshes (boxes, cylinders, gears, wedges, 3D force arrows),
and per-pixel Phong + Fresnel rim-lit 3D spheres & tapered capsules, all depth-sorted
together in camera space for true 3D occlusion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

import cv2
import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-8 else v


def rot_matrix(rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> np.ndarray:
    """3x3 Euler rotation matrix (radians, XYZ order)."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float32)
    return (Rz @ Ry @ Rx).astype(np.float32)


@dataclass
class Camera3D:
    """True pinhole 3D perspective camera (right-handed: X right, Y up, Z toward viewer)."""

    eye: tuple[float, float, float]
    target: tuple[float, float, float] = (0.0, 0.0, 0.0)
    up: tuple[float, float, float] = (0.0, 1.0, 0.0)
    fov_deg: float = 42.0
    width: int = 1080
    height: int = 1920
    cy_offset: float = 0.0

    def __post_init__(self) -> None:
        self._eye = np.array(self.eye, dtype=np.float32)
        self._target = np.array(self.target, dtype=np.float32)
        forward = _normalize(self._target - self._eye)
        right = _normalize(np.cross(forward, np.array(self.up, dtype=np.float32)))
        true_up = _normalize(np.cross(right, forward))
        # View matrix rows: right, true_up, forward (so cam_z > 0 is in front of camera)
        self._R = np.stack([right, true_up, forward], axis=0).astype(np.float32)
        self._focal = (self.width * 0.5) / math.tan(math.radians(self.fov_deg * 0.5))

    def world_to_cam(self, pts: np.ndarray) -> np.ndarray:
        """Transform Nx3 world points into camera space (x right, y up, z forward)."""
        return (pts - self._eye[None, :]) @ self._R.T

    def project(self, cam_pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Project Nx3 camera-space points to Nx2 screen pixels and depth array."""
        z = np.maximum(cam_pts[:, 2], 0.08)
        u = self.width * 0.5 + (cam_pts[:, 0] * self._focal) / z
        v = self.height * 0.5 + self.cy_offset - (cam_pts[:, 1] * self._focal) / z
        return np.stack([u, v], axis=1), z

    def project_point(self, pt: tuple[float, float, float]) -> tuple[float, float, float, float]:
        """Project a single 3D world point -> (u, v, depth_z, px_per_unit)."""
        c = self.world_to_cam(np.array([pt], dtype=np.float32))[0]
        z = max(float(c[2]), 0.08)
        scale = float(self._focal / z)
        u = self.width * 0.5 + float(c[0]) * scale
        v = self.height * 0.5 + self.cy_offset - float(c[1]) * scale
        return (u, v, z, scale)


@lru_cache(maxsize=96)
def _shaded_sphere_sprite(
    rgb: tuple[int, int, int],
    radius_bin: int,
    metallic: float = 0.35,
    rim_rgb: tuple[int, int, int] = (70, 210, 255),
    emissive: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a smooth per-pixel Phong + Fresnel rim-lit 3D sphere sprite (BGR + float alpha)."""
    r = max(6, radius_bin)
    size = r * 2 + 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    nx = (xx - (r + 0.5)) / r
    ny = -((yy - (r + 0.5)) / r)  # Y up
    r2 = nx * nx + ny * ny
    inside = r2 <= 1.0
    nz = np.sqrt(np.maximum(0.0, 1.0 - r2))

    # 3-point studio lighting: warm key top-left, cool cyan fill right, strong Fresnel rim
    L1 = _normalize(np.array([-0.48, 0.62, 0.62], dtype=np.float32))
    L2 = _normalize(np.array([0.72, -0.15, 0.45], dtype=np.float32))
    H1 = _normalize(L1 + np.array([0.0, 0.0, 1.0], dtype=np.float32))

    ndotl1 = np.clip(nx * L1[0] + ny * L1[1] + nz * L1[2], 0.0, 1.0)
    ndotl2 = np.clip(nx * L2[0] + ny * L2[1] + nz * L2[2], 0.0, 1.0)
    spec_pow = 28.0 + 36.0 * metallic
    spec = np.clip(nx * H1[0] + ny * H1[1] + nz * H1[2], 0.0, 1.0) ** spec_pow
    fresnel = np.clip(1.0 - nz, 0.0, 1.0) ** 2.6

    base = np.array([rgb[2], rgb[1], rgb[0]], dtype=np.float32)  # BGR
    rim = np.array([rim_rgb[2], rim_rgb[1], rim_rgb[0]], dtype=np.float32)
    cool_fill = np.array([150.0, 110.0, 55.0], dtype=np.float32)  # BGR cyan-navy bounce

    ambient = 0.24 + 0.55 * emissive
    col = (
        base[None, None, :] * (ambient + (0.86 - 0.3 * emissive) * ndotl1[:, :, None])
        + cool_fill[None, None, :] * (0.20 * ndotl2[:, :, None])
        + 255.0 * ((0.30 + 0.55 * metallic) * spec[:, :, None])
        + rim[None, None, :] * (0.42 * fresnel[:, :, None])
    )
    # Subtle dark bevel contour at silhouette edge for clean graphic readability
    edge_dark = np.clip((r2 - 0.86) / 0.14, 0.0, 1.0)
    col *= (1.0 - 0.35 * edge_dark[:, :, None])

    # Antialiased alpha at border
    dist = np.sqrt(r2)
    alpha = np.clip((1.0 - dist) * r * 0.9 + 0.5, 0.0, 1.0) * inside.astype(np.float32)
    return np.clip(col, 0, 255).astype(np.uint8), alpha.astype(np.float32)


def _blend_sprite(
    canvas_bgr: np.ndarray,
    sprite_bgr: np.ndarray,
    alpha: np.ndarray,
    cx: float,
    cy: float,
    target_w: int,
    target_h: int,
) -> None:
    """Alpha-blend a shaded 3D sphere/ellipsoid sprite onto canvas_bgr cleanly with clipping."""
    if target_w < 3 or target_h < 3:
        return
    if sprite_bgr.shape[1] != target_w or sprite_bgr.shape[0] != target_h:
        spr = cv2.resize(sprite_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        alp = cv2.resize(alpha, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    else:
        spr, alp = sprite_bgr, alpha

    H, W = canvas_bgr.shape[:2]
    x0 = int(round(cx - target_w * 0.5))
    y0 = int(round(cy - target_h * 0.5))
    x1, y1 = x0 + target_w, y0 + target_h
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(W, x1), min(H, y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return

    sx0, sy0 = cx0 - x0, cy0 - y0
    sx1, sy1 = sx0 + (cx1 - cx0), sy0 + (cy1 - cy0)
    a = alp[sy0:sy1, sx0:sx1, None]
    roi = canvas_bgr[cy0:cy1, cx0:cx1].astype(np.float32)
    out = spr[sy0:sy1, sx0:sx1].astype(np.float32) * a + roi * (1.0 - a)
    canvas_bgr[cy0:cy1, cx0:cx1] = out.astype(np.uint8)


def _shade_color_bgr(
    normal_cam: np.ndarray,
    base_rgb: tuple[int, int, int],
    metallic: float = 0.35,
    emissive: float = 0.0,
    rim_rgb: tuple[int, int, int] = (70, 210, 255),
) -> tuple[int, int, int]:
    """Compute Phong + Fresnel studio lighting color (BGR) for a 3D face normal in camera space."""
    n = _normalize(normal_cam)
    if n[2] > 0:
        n = -n  # Face normal pointing toward camera (-Z in our cam space? Wait: forward is +Z, viewer is -Z)
    # In our Camera3D, forward is +Z, so camera looks from -Z toward +Z -> front face normal has n[2] < 0
    v_dir = np.array([0.0, 0.0, -1.0], dtype=np.float32)
    L1 = _normalize(np.array([-0.48, 0.65, -0.58], dtype=np.float32))
    L2 = _normalize(np.array([0.75, -0.20, -0.40], dtype=np.float32))
    H1 = _normalize(L1 + v_dir)

    ndotl1 = max(0.0, float(np.dot(n, L1)))
    ndotl2 = max(0.0, float(np.dot(n, L2)))
    ndotv = max(0.0, float(np.dot(n, v_dir)))
    spec = (max(0.0, float(np.dot(n, H1))) ** (20.0 + 36.0 * metallic)) * (0.30 + 0.55 * metallic)
    rim = ((1.0 - ndotv) ** 2.4) * 0.32

    r, g, b = float(base_rgb[0]), float(base_rgb[1]), float(base_rgb[2])
    amb = 0.24 + 0.60 * emissive
    diff = (0.82 - 0.30 * emissive) * ndotl1
    cr = r * (amb + diff) + 55.0 * 0.16 * ndotl2 + 255.0 * spec + rim_rgb[0] * rim
    cg = g * (amb + diff) + 115.0 * 0.16 * ndotl2 + 255.0 * spec + rim_rgb[1] * rim
    cb = b * (amb + diff) + 165.0 * 0.16 * ndotl2 + 255.0 * spec + rim_rgb[2] * rim
    return (
        max(0, min(255, int(round(cb)))),
        max(0, min(255, int(round(cg)))),
        max(0, min(255, int(round(cr)))),
    )


@dataclass
class _RenderItem:
    depth: float
    kind: str
    payload: tuple


class Scene3D:
    """Immediate-mode 3D scene builder with depth-sorted Phong-lit meshes, spheres & callbacks."""

    def __init__(self, camera: Camera3D) -> None:
        self.cam = camera
        self._items: list[_RenderItem] = []

    def add_quad(
        self,
        pts_world: np.ndarray,
        rgb: tuple[int, int, int],
        metallic: float = 0.35,
        emissive: float = 0.0,
        outline_bgr: tuple[int, int, int] | None = (18, 12, 8),
        outline_w: int = 1,
        double_sided: bool = True,
        rim_rgb: tuple[int, int, int] = (70, 210, 255),
        alpha: float = 1.0,
    ) -> None:
        cam_pts = self.cam.world_to_cam(pts_world)
        if np.any(cam_pts[:, 2] <= 0.12):
            return
        e1 = cam_pts[1] - cam_pts[0]
        e2 = cam_pts[2] - cam_pts[0]
        normal = np.cross(e1, e2)
        if not double_sided and normal[2] > 0:
            return
        uv, z = self.cam.project(cam_pts)
        depth = float(np.mean(z))
        bgr = _shade_color_bgr(normal, rgb, metallic=metallic, emissive=emissive, rim_rgb=rim_rgb)
        poly = np.round(uv).astype(np.int32)
        self._items.append(_RenderItem(depth, "poly", (poly, bgr, outline_bgr, outline_w, alpha)))

    def add_line_3d(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        rgb: tuple[int, int, int],
        width: int = 3,
    ) -> None:
        pts = np.array([p0, p1], dtype=np.float32)
        cam_pts = self.cam.world_to_cam(pts)
        if np.any(cam_pts[:, 2] <= 0.12):
            return
        uv, z = self.cam.project(cam_pts)
        bgr = (rgb[2], rgb[1], rgb[0])
        self._items.append(
            _RenderItem(
                float(np.mean(z)),
                "line",
                ((int(round(uv[0, 0])), int(round(uv[0, 1]))), (int(round(uv[1, 0])), int(round(uv[1, 1]))), bgr, width),
            )
        )

    def add_sphere(
        self,
        center: tuple[float, float, float],
        radius: float,
        rgb: tuple[int, int, int],
        metallic: float = 0.35,
        emissive: float = 0.0,
        rim_rgb: tuple[int, int, int] = (70, 210, 255),
        squash_y: float = 1.0,
        depth_bias: float = 0.0,
    ) -> tuple[float, float, float]:
        """Add a per-pixel Phong + Fresnel rim-lit 3D sphere; returns (u, v, px_radius)."""
        u, v, z, scale = self.cam.project_point(center)
        if z <= 0.12:
            return (u, v, 0.0)
        pr = radius * scale
        self._items.append(
            _RenderItem(z + depth_bias, "sphere", (u, v, pr, pr * squash_y, rgb, metallic, rim_rgb, emissive))
        )
        return (u, v, pr)

    def add_capsule(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        r0: float,
        r1: float,
        rgb: tuple[int, int, int],
        metallic: float = 0.30,
        rim_rgb: tuple[int, int, int] = (70, 210, 255),
        segments: int = 12,
    ) -> None:
        """Add a smooth 3D Phong-lit tapered capsule (cylinder + endcap spheres) for limbs & rods."""
        self.add_cylinder(p0, p1, r0, r1, rgb, segments=segments, metallic=metallic, caps=False, rim_rgb=rim_rgb, outline_w=0)
        self.add_sphere(p0, r0 * 0.99, rgb, metallic=metallic, rim_rgb=rim_rgb)
        self.add_sphere(p1, r1 * 0.99, rgb, metallic=metallic, rim_rgb=rim_rgb)

    def add_box(
        self,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        rgb: tuple[int, int, int],
        rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
        metallic: float = 0.45,
        emissive: float = 0.0,
        outline_w: int = 1,
        rim_rgb: tuple[int, int, int] = (70, 210, 255),
        alpha: float = 1.0,
    ) -> None:
        """Add an oriented 3D rectangular prism with 6 lit faces."""
        hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        verts = np.array(
            [
                [-hx, -hy, -hz],
                [hx, -hy, -hz],
                [hx, hy, -hz],
                [-hx, hy, -hz],
                [-hx, -hy, hz],
                [hx, -hy, hz],
                [hx, hy, hz],
                [-hx, hy, hz],
            ],
            dtype=np.float32,
        )
        R = rot_matrix(*rot)
        w_verts = verts @ R.T + np.array(center, dtype=np.float32)[None, :]
        faces = (
            (0, 3, 2, 1),  # -Z
            (4, 5, 6, 7),  # +Z
            (0, 1, 5, 4),  # -Y
            (2, 3, 7, 6),  # +Y
            (0, 4, 7, 3),  # -X
            (1, 2, 6, 5),  # +X
        )
        for f in faces:
            self.add_quad(
                w_verts[list(f)],
                rgb=rgb,
                metallic=metallic,
                emissive=emissive,
                outline_w=outline_w,
                double_sided=True,
                rim_rgb=rim_rgb,
                alpha=alpha,
            )

    def add_cylinder(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        r0: float,
        r1: float | None = None,
        rgb: tuple[int, int, int] = (140, 160, 185),
        segments: int = 16,
        metallic: float = 0.55,
        emissive: float = 0.0,
        caps: bool = True,
        outline_w: int = 0,
        rim_rgb: tuple[int, int, int] = (70, 210, 255),
        alpha: float = 1.0,
    ) -> None:
        """Add a true 3D Phong-lit cylinder / frustum along any 3D segment (p0 -> p1)."""
        rad1 = r0 if r1 is None else r1
        a = np.array(p0, dtype=np.float32)
        b = np.array(p1, dtype=np.float32)
        axis = b - a
        length = float(np.linalg.norm(axis))
        if length < 1e-5:
            return
        w_ax = axis / length
        ref = np.array([0.0, 1.0, 0.0], dtype=np.float32) if abs(w_ax[1]) < 0.9 else np.array([1.0, 0.0, 0.0], dtype=np.float32)
        u_ax = _normalize(np.cross(ref, w_ax))
        v_ax = _normalize(np.cross(w_ax, u_ax))

        angles = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
        ring0 = np.array([a + r0 * (math.cos(th) * u_ax + math.sin(th) * v_ax) for th in angles], dtype=np.float32)
        ring1 = np.array([b + rad1 * (math.cos(th) * u_ax + math.sin(th) * v_ax) for th in angles], dtype=np.float32)

        for i in range(segments):
            j = (i + 1) % segments
            quad = np.stack([ring0[i], ring0[j], ring1[j], ring1[i]], axis=0)
            self.add_quad(quad, rgb=rgb, metallic=metallic, emissive=emissive, outline_w=outline_w, rim_rgb=rim_rgb, alpha=alpha)

        if caps and segments >= 6:
            # Render endcaps as lit polygons
            if r0 > 1e-4:
                self.add_quad(ring0[::-1], rgb=rgb, metallic=metallic, emissive=emissive, outline_w=1, rim_rgb=rim_rgb, alpha=alpha)
            if rad1 > 1e-4:
                self.add_quad(ring1, rgb=rgb, metallic=metallic, emissive=emissive, outline_w=1, rim_rgb=rim_rgb, alpha=alpha)

    def add_gear_3d(
        self,
        center: tuple[float, float, float],
        outer_r: float,
        thickness: float,
        teeth: int,
        angle: float,
        rgb: tuple[int, int, int],
        rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
        metallic: float = 0.65,
    ) -> None:
        """Add an extruded 3D machined spur gear / flywheel."""
        R = rot_matrix(*rot)
        c = np.array(center, dtype=np.float32)
        # Main central drum
        p_back = tuple((c + R @ np.array([0.0, 0.0, -thickness * 0.5], dtype=np.float32)).tolist())
        p_front = tuple((c + R @ np.array([0.0, 0.0, thickness * 0.5], dtype=np.float32)).tolist())
        self.add_cylinder(p_back, p_front, outer_r * 0.82, outer_r * 0.82, rgb, segments=18, metallic=metallic)
        # Raised center axle hub
        p_hb = tuple((c + R @ np.array([0.0, 0.0, -thickness * 0.72], dtype=np.float32)).tolist())
        p_hf = tuple((c + R @ np.array([0.0, 0.0, thickness * 0.72], dtype=np.float32)).tolist())
        self.add_cylinder(p_hb, p_hf, outer_r * 0.28, outer_r * 0.28, (200, 215, 232), segments=12, metallic=0.8)

        # Articulated 3D gear teeth around perimeter
        tooth_w = (2.0 * math.pi * outer_r * 0.82) / (teeth * 2.1)
        tooth_h = outer_r * 0.24
        for i in range(teeth):
            a = angle + i * (2.0 * math.pi / teeth)
            local_pos = np.array([math.cos(a) * (outer_r * 0.88), math.sin(a) * (outer_r * 0.88), 0.0], dtype=np.float32)
            # Build tooth vertices in gear local frame, then transform by R
            tx, ty, tz = tooth_h * 0.5, tooth_w * 0.5, thickness * 0.46
            c_a, s_a = math.cos(a), math.sin(a)
            Rt = np.array([[c_a, -s_a, 0], [s_a, c_a, 0], [0, 0, 1]], dtype=np.float32)
            verts = np.array(
                [
                    [-tx, -ty, -tz], [tx, -ty * 0.75, -tz], [tx, ty * 0.75, -tz], [-tx, ty, -tz],
                    [-tx, -ty, tz], [tx, -ty * 0.75, tz], [tx, ty * 0.75, tz], [-tx, ty, tz],
                ],
                dtype=np.float32,
            )
            w_verts = (verts @ Rt.T + local_pos[None, :]) @ R.T + c[None, :]
            for f in ((4, 5, 6, 7), (0, 3, 2, 1), (1, 2, 6, 5), (0, 1, 5, 4), (2, 3, 7, 6)):
                self.add_quad(w_verts[list(f)], rgb=rgb, metallic=metallic, outline_w=1)

    def add_arrow_3d(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        rgb: tuple[int, int, int],
        shaft_r: float = 0.075,
        head_r: float = 0.19,
        head_len_frac: float = 0.30,
    ) -> None:
        """Add a glowing 3D cylindrical + conical force vector arrow in 3D space."""
        a = np.array(p0, dtype=np.float32)
        b = np.array(p1, dtype=np.float32)
        vec = b - a
        dist = float(np.linalg.norm(vec))
        if dist < 1e-4:
            return
        mid = a + vec * (1.0 - head_len_frac)
        self.add_cylinder(tuple(a.tolist()), tuple(mid.tolist()), shaft_r, shaft_r, rgb, segments=10, metallic=0.2, emissive=0.45, caps=True)
        self.add_cylinder(tuple(mid.tolist()), tuple(b.tolist()), head_r, 0.005, rgb, segments=12, metallic=0.2, emissive=0.55, caps=True)

    def add_floor_grid(
        self,
        y_level: float = -2.0,
        span: float = 8.0,
        step: float = 1.0,
        rgb: tuple[int, int, int] = (28, 52, 88),
    ) -> None:
        """Add true 3D perspective lab floor grid receding to vanishing point."""
        n = int(span / step)
        for i in range(-n, n + 1):
            coord = i * step
            self.add_line_3d((coord, y_level, -span), (coord, y_level, span), rgb, width=2)
            self.add_line_3d((-span, y_level, coord), (span, y_level, coord), rgb, width=2)

    def add_custom_2d(self, depth_z: float, fn: Callable[[np.ndarray], None]) -> None:
        """Register a custom 2D OpenCV overlay callback depth-sorted at exact 3D depth_z."""
        self._items.append(_RenderItem(depth_z, "custom", (fn,)))

    def render_to_bgr(self, bg_bgr: np.ndarray) -> np.ndarray:
        """Painter's-sort all 3D primitives back-to-front and rasterize onto a copy of bg_bgr."""
        canvas = bg_bgr.copy()
        self._items.sort(key=lambda item: item.depth, reverse=True)
        for item in self._items:
            if item.kind == "poly":
                poly, bgr, outline_bgr, outline_w, alpha = item.payload
                if alpha >= 0.99:
                    cv2.fillConvexPoly(canvas, poly, bgr, lineType=cv2.LINE_AA)
                else:
                    x0 = max(0, int(np.min(poly[:, 0])) - 2)
                    y0 = max(0, int(np.min(poly[:, 1])) - 2)
                    x1 = min(canvas.shape[1], int(np.max(poly[:, 0])) + 3)
                    y1 = min(canvas.shape[0], int(np.max(poly[:, 1])) + 3)
                    if x1 > x0 and y1 > y0:
                        roi = canvas[y0:y1, x0:x1].copy()
                        shifted = poly - np.array([[x0, y0]], dtype=np.int32)
                        cv2.fillConvexPoly(roi, shifted, bgr, lineType=cv2.LINE_AA)
                        cv2.addWeighted(roi, alpha, canvas[y0:y1, x0:x1], 1.0 - alpha, 0.0, dst=canvas[y0:y1, x0:x1])
                if outline_bgr is not None and outline_w > 0:
                    cv2.polylines(canvas, [poly], True, outline_bgr, outline_w, lineType=cv2.LINE_AA)
            elif item.kind == "line":
                p0, p1, bgr, w = item.payload
                cv2.line(canvas, p0, p1, bgr, w, lineType=cv2.LINE_AA)
            elif item.kind == "sphere":
                u, v, pr_x, pr_y, rgb, metallic, rim_rgb, emissive = item.payload
                tw = int(round(pr_x * 2.0))
                th = int(round(pr_y * 2.0))
                if tw >= 4 and th >= 4:
                    r_bin = min(220, max(16, int(round(max(pr_x, pr_y) / 16.0)) * 16))
                    spr, alp = _shaded_sphere_sprite(rgb, r_bin, round(metallic, 2), rim_rgb, round(emissive, 2))
                    _blend_sprite(canvas, spr, alp, u, v, tw, th)
            elif item.kind == "custom":
                item.payload[0](canvas)
        return canvas
