"""Sculpted Studio 3D Crash-Test Dummy Mascot ('UNIT-01' v2) for FailSafe Lab.

Features clearcoat Phong-shaded amber-gold polymer shell, machined titanium shoulder
pauldrons & collar ring, high-res quadrant crash-test decals, grounded soft contact
shadow, and a glossy curved dark-glass visor with bloom-lit expressive LED eyes.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from cts_factory.engine.renderer3d import Scene3D, rot_matrix

DUMMY_SHELL = (246, 188, 48)       # Satin clearcoat crash-test gold-amber
DUMMY_SHELL_ALT = (218, 154, 34)   # Sculpted lower torso polymer
DUMMY_JOINT = (48, 62, 82)         # Machined dark titanium ball joints
DUMMY_TRIM = (176, 194, 216)       # Brushed chrome accent rings
DUMMY_RIM = (90, 225, 255)         # Studio cyan Fresnel rim light


def _draw_quadrant_target(canvas: np.ndarray, cx: int, cy: int, r: int) -> None:
    """Crisp high-contrast crash-test dummy calibration target decal."""
    if r < 4:
        return
    cv2.circle(canvas, (cx, cy), r + 1, (220, 232, 245), max(1, r // 10), lineType=cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), r, (22, 24, 30), -1, lineType=cv2.LINE_AA)
    cv2.ellipse(canvas, (cx, cy), (r - 1, r - 1), 0, 0, 90, (48, 206, 252), -1, lineType=cv2.LINE_AA)
    cv2.ellipse(canvas, (cx, cy), (r - 1, r - 1), 0, 180, 270, (48, 206, 252), -1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), r, (14, 16, 22), max(1, r // 8), lineType=cv2.LINE_AA)
    cv2.line(canvas, (cx - r, cy), (cx + r, cy), (14, 16, 22), max(1, r // 10), lineType=cv2.LINE_AA)
    cv2.line(canvas, (cx, cy - r), (cx, cy + r), (14, 16, 22), max(1, r // 10), lineType=cv2.LINE_AA)


def _draw_dummy_face_visor(
    canvas: np.ndarray,
    u: float,
    v: float,
    pr: float,
    emotion: str,
    t: float,
    yaw_bias: float = 0.0,
    scale_factor: float = 1.0,
    bloom_only: bool = False,
) -> None:
    """Render glossy curved obsidian glass visor + bloom-lit animated LED eyes & forehead target."""
    if pr * scale_factor < 4:
        return
    sf = scale_factor
    cx = int(round((u + yaw_bias * pr * 0.28) * sf))
    cy = int(round((v + pr * 0.04) * sf))
    vw = max(4, int(round(pr * 0.74 * sf)))
    vh = max(3, int(round(pr * 0.45 * sf)))

    if not bloom_only:
        # Metallic bezel + glossy obsidian curved glass visor
        cv2.ellipse(canvas, (cx, cy), (vw + max(2, int(pr * 0.04 * sf)), vh + max(2, int(pr * 0.04 * sf))), 0, 0, 360, (165, 182, 204), -1, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, (cx, cy), (vw, vh), 0, 0, 360, (24, 16, 11), -1, lineType=cv2.LINE_AA)
        # Dual glossy studio reflection arcs on curved visor glass
        cv2.ellipse(
            canvas,
            (cx - int(vw * 0.24), cy - int(vh * 0.42)),
            (max(3, int(vw * 0.42)), max(2, int(vh * 0.14))),
            -14,
            0,
            360,
            (115, 98, 80),
            -1,
            lineType=cv2.LINE_AA,
        )
        # Forehead calibration target decal
        _draw_quadrant_target(
            canvas,
            int(round((u + yaw_bias * pr * 0.14) * sf)),
            int(round((v - pr * 0.58) * sf)),
            max(5, int(round(pr * 0.21 * sf))),
        )

    eye_dx = int(round(vw * 0.40))
    eye_y = cy - int(round(vh * 0.05))
    blink = 1.0 if ((t * 0.9) % 4.3) > 0.11 else 0.15

    if emotion in ("panic", "shock"):
        eye_bgr = (65, 222, 255)
        er = max(2, int(round(pr * 0.22 * sf)))
        jitter = int(round(math.sin(t * 48.0) * max(1.0, pr * 0.028 * sf)))
        for sx in (-1, 1):
            ex = cx + sx * eye_dx + jitter
            cv2.circle(canvas, (ex, eye_y), er, eye_bgr, -1, lineType=cv2.LINE_AA)
            if not bloom_only:
                cv2.circle(canvas, (ex, eye_y), max(2, int(er * 0.30)), (16, 12, 10), -1, lineType=cv2.LINE_AA)
                cv2.circle(canvas, (ex - max(1, er // 3), eye_y - max(1, er // 3)), max(1, er // 5), (255, 255, 255), -1, lineType=cv2.LINE_AA)
        mw = max(2, int(round(pr * 0.15 * sf)))
        mh = max(3, int(round(pr * 0.17 * sf)))
        cv2.ellipse(canvas, (cx, cy + int(vh * 0.46)), (mw, mh), 0, 0, 360, (60, 150, 255), max(1, int(pr * 0.055 * sf)), lineType=cv2.LINE_AA)
    elif emotion == "brace":
        eye_bgr = (60, 185, 255)
        s = max(2, int(round(pr * 0.16 * sf)))
        th = max(1, int(round(pr * 0.065 * sf)))
        cv2.line(canvas, (cx - eye_dx - s, eye_y - s // 2), (cx - eye_dx + s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx - eye_dx - s, eye_y + s // 2), (cx - eye_dx + s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx + eye_dx + s, eye_y - s // 2), (cx + eye_dx - s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx + eye_dx + s, eye_y + s // 2), (cx + eye_dx - s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx - s, cy + int(vh * 0.45)), (cx + s, cy + int(vh * 0.45)), eye_bgr, th, lineType=cv2.LINE_AA)
    elif emotion == "relief":
        eye_bgr = (145, 242, 70)
        r_arc = max(2, int(round(pr * 0.17 * sf)))
        th = max(1, int(round(pr * 0.07 * sf)))
        for sx in (-1, 1):
            cv2.ellipse(canvas, (cx + sx * eye_dx, eye_y + r_arc // 2), (r_arc, r_arc), 0, 200, 340, eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, (cx, cy + int(vh * 0.34)), (r_arc, max(1, int(r_arc * 0.6))), 0, 15, 165, eye_bgr, th, lineType=cv2.LINE_AA)
    elif emotion == "curious":
        eye_bgr = (255, 224, 45)
        er = max(2, int(round(pr * 0.17 * sf)))
        cv2.ellipse(canvas, (cx - eye_dx, eye_y), (er, max(1, int(er * blink))), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, (cx + eye_dx, eye_y - max(1, int(2 * sf))), (int(er * 1.15), max(1, int(er * 0.65 * blink))), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
    else:
        eye_bgr = (255, 222, 42)
        er_x = max(2, int(round(pr * 0.165 * sf)))
        er_y = max(1, int(round(pr * 0.185 * blink * sf)))
        for sx in (-1, 1):
            ex = cx + sx * eye_dx
            cv2.ellipse(canvas, (ex, eye_y), (er_x, er_y), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
            if not bloom_only:
                cv2.circle(canvas, (ex - max(1, er_x // 3), eye_y - max(1, er_y // 3)), max(1, er_x // 4), (255, 255, 255), -1, lineType=cv2.LINE_AA)
        if emotion == "cta":
            cv2.ellipse(canvas, (cx, cy + int(vh * 0.38)), (max(2, int(pr * 0.18 * sf)), max(1, int(pr * 0.10 * sf))), 0, 10, 170, (70, 215, 255), max(1, int(pr * 0.055 * sf)), lineType=cv2.LINE_AA)


def add_crash_test_dummy(
    scene: Scene3D,
    pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
    yaw: float = 0.0,
    pose: str = "explain",
    emotion: str = "engineer",
    t: float = 0.0,
    tilt_z: float = 0.0,
    ground_shadow: bool = True,
) -> None:
    """Add sculpted studio 3D Crash-Test Dummy ('UNIT-01' v2) with clearcoat shading & LED bloom."""
    R = rot_matrix(0.0, yaw, tilt_z)
    origin = np.array(pos, dtype=np.float32)

    def _pt(x: float, y: float, z: float) -> tuple[float, float, float]:
        v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
        return tuple((origin + R @ v).tolist())

    bob = math.sin(t * 3.2) * 0.03
    if pose == "panic_freefall":
        bob = math.sin(t * 22.0) * 0.05

    pelvis = (0.0, 0.0 + bob, 0.0)
    chest = (0.0, 0.56 + bob, 0.02)
    head = (0.0, 1.24 + bob, 0.04)

    l_sh = (-0.43, 0.78 + bob, 0.0)
    r_sh = (0.43, 0.78 + bob, 0.0)
    l_hip = (-0.21, -0.10 + bob, 0.0)
    r_hip = (0.21, -0.10 + bob, 0.0)

    if pose == "panic_freefall":
        wave = math.sin(t * 16.0) * 0.16
        l_el = (-0.68, 1.08 + bob + wave, 0.22)
        l_ha = (-0.54, 1.48 + bob - wave, 0.34)
        r_el = (0.68, 1.12 + bob - wave, 0.22)
        r_ha = (0.56, 1.50 + bob + wave, 0.34)
        l_kn = (-0.32, -0.44 + bob, 0.36)
        l_ft = (-0.30, -0.92 + bob + wave * 0.6, 0.12)
        r_kn = (0.32, -0.40 + bob, 0.38)
        r_ft = (0.30, -0.88 + bob - wave * 0.6, 0.14)
    elif pose == "brace_impact":
        l_el = (-0.52, 0.84 + bob, 0.35)
        l_ha = (-0.22, 1.16 + bob, 0.42)
        r_el = (0.52, 0.84 + bob, 0.35)
        r_ha = (0.22, 1.16 + bob, 0.42)
        l_kn = (-0.28, -0.46 + bob, 0.34)
        l_ft = (-0.26, -0.98 + bob, 0.02)
        r_kn = (0.28, -0.46 + bob, 0.34)
        r_ft = (0.26, -0.98 + bob, 0.02)
    elif pose == "point_right":
        gest = math.sin(t * 4.5) * 0.06
        l_el = (-0.52, 0.38 + bob, 0.08)
        l_ha = (-0.42, 0.06 + bob, 0.16)
        r_el = (0.76, 0.82 + bob + gest, 0.18)
        r_ha = (1.14, 0.96 + bob + gest, 0.24)
        l_kn = (-0.23, -0.60, 0.06)
        l_ft = (-0.24, -1.16, 0.0)
        r_kn = (0.24, -0.60, 0.06)
        r_ft = (0.25, -1.16, 0.0)
    elif pose == "point_left":
        gest = math.sin(t * 4.5) * 0.06
        l_el = (-0.76, 0.82 + bob + gest, 0.18)
        l_ha = (-1.14, 0.96 + bob + gest, 0.24)
        r_el = (0.52, 0.38 + bob, 0.08)
        r_ha = (0.42, 0.06 + bob, 0.16)
        l_kn = (-0.23, -0.60, 0.06)
        l_ft = (-0.24, -1.16, 0.0)
        r_kn = (0.24, -0.60, 0.06)
        r_ft = (0.25, -1.16, 0.0)
    elif pose == "cta_shrug":
        sw = math.sin(t * 5.0) * 0.05
        l_el = (-0.64, 0.56 + bob, 0.16)
        l_ha = (-0.86, 0.86 + bob + sw, 0.32)
        r_el = (0.64, 0.56 + bob, 0.16)
        r_ha = (0.86, 0.86 + bob - sw, 0.32)
        l_kn = (-0.24, -0.60, 0.05)
        l_ft = (-0.25, -1.16, 0.0)
        r_kn = (0.24, -0.60, 0.05)
        r_ft = (0.25, -1.16, 0.0)
    elif pose == "relief_wave":
        w = math.sin(t * 7.0) * 0.09
        l_el = (-0.52, 0.40 + bob, 0.10)
        l_ha = (-0.36, 0.12 + bob, 0.18)
        r_el = (0.66, 0.96 + bob, 0.24)
        r_ha = (0.42 + w, 1.38 + bob, 0.32)
        l_kn = (-0.24, -0.60, 0.04)
        l_ft = (-0.24, -1.16, 0.0)
        r_kn = (0.24, -0.60, 0.04)
        r_ft = (0.24, -1.16, 0.0)
    elif pose == "pilot_sub":
        steer = math.sin(t * 7.5) * 0.08
        l_el = (-0.42, 0.44 + bob, 0.24)
        l_ha = (-0.24, 0.50 + bob + steer, 0.56)
        r_el = (0.42, 0.44 + bob, 0.24)
        r_ha = (0.24, 0.50 + bob - steer, 0.56)
        l_kn = (-0.24, -0.32 + bob, 0.44)
        l_ft = (-0.24, -0.78 + bob, 0.36)
        r_kn = (0.24, -0.32 + bob, 0.44)
        r_ft = (0.24, -0.78 + bob, 0.36)
    elif pose == "sprint_escape":
        run = math.sin(t * 20.0)
        run_b = abs(math.cos(t * 20.0)) * 0.14
        bob = run_b
        l_el = (-0.56, 0.52 + bob + run * 0.24, 0.16 - run * 0.22)
        l_ha = (-0.48, 0.82 + bob + run * 0.30, 0.34 - run * 0.28)
        r_el = (0.56, 0.52 + bob - run * 0.24, 0.16 + run * 0.22)
        r_ha = (0.48, 0.82 + bob - run * 0.30, 0.34 + run * 0.28)
        l_kn = (-0.26, -0.44 + bob - run * 0.22, 0.28 + run * 0.30)
        l_ft = (-0.26, -0.96 + bob - run * 0.28, -0.05 + run * 0.42)
        r_kn = (0.26, -0.44 + bob + run * 0.22, 0.28 - run * 0.30)
        r_ft = (0.26, -0.96 + bob + run * 0.28, -0.05 - run * 0.42)
    else:
        sw = math.sin(t * 3.8) * 0.05
        l_el = (-0.54, 0.42 + bob, 0.10)
        l_ha = (-0.44, 0.12 + bob, 0.22)
        r_el = (0.60, 0.60 + bob, 0.18)
        r_ha = (0.82, 0.82 + bob + sw, 0.30)
        l_kn = (-0.23, -0.60, 0.05)
        l_ft = (-0.24, -1.16, 0.0)
        r_kn = (0.23, -0.60, 0.05)
        r_ft = (0.24, -1.16, 0.0)

    # Grounded soft ambient-occlusion contact shadow beneath boots
    if ground_shadow and pose not in ("panic_freefall", "pilot_sub"):
        scene.add_ground_shadow(_pt(0.0, -1.24, 0.0), 0.62 * scale, 0.55 * scale, opacity=0.52)

    # Sculpted 3D Torso, Chrome Belt Ring & Pelvis
    scene.add_capsule(_pt(*pelvis), _pt(0.0, 0.50 + bob, 0.0), 0.23 * scale, 0.31 * scale, DUMMY_SHELL_ALT, metallic=0.42, rim_rgb=DUMMY_RIM, segments=14)
    scene.add_sphere(_pt(*pelvis), 0.25 * scale, DUMMY_JOINT, metallic=0.65)
    scene.add_cylinder(_pt(0.0, 0.14 + bob, 0.0), _pt(0.0, 0.22 + bob, 0.0), 0.26 * scale, 0.26 * scale, DUMMY_TRIM, segments=14, metallic=0.82, caps=False)

    # Chrome neck collar + recessed neck hydraulic piston (zero dark block overlap!)
    scene.add_sphere(_pt(0.0, 0.86 + bob, -0.02), 0.15 * scale, DUMMY_TRIM, metallic=0.82, squash_y=0.55, depth_bias=0.06)
    scene.add_sphere(_pt(0.0, 0.94 + bob, -0.01), 0.11 * scale, DUMMY_JOINT, metallic=0.70, depth_bias=0.05)

    # Sculpted clearcoat chest shell + calibration target decal
    cu, cv, cr = scene.add_sphere(_pt(0.0, 0.58 + bob, 0.05), 0.34 * scale, DUMMY_SHELL, metallic=0.45, squash_y=1.06)
    chest_z = scene.cam.project_point(_pt(0.0, 0.58 + bob, 0.42))[2]
    scene.add_custom_2d(
        chest_z - 0.03,
        lambda c, _u=cu, _v=cv, _r=cr: _draw_quadrant_target(c, int(round(_u)), int(round(_v + _r * 0.05)), max(5, int(round(_r * 0.31)))),
    )

    # Glossy 3D Head + Bloom-lit Expressive Curved Glass Visor
    hu, hv, hr = scene.add_sphere(_pt(*head), 0.38 * scale, DUMMY_SHELL, metallic=0.42, squash_y=1.06, rim_rgb=DUMMY_RIM)
    head_front_z = scene.cam.project_point(_pt(0.0, 1.24 + bob, 0.46))[2]
    yaw_bias = math.sin(yaw)
    scene.add_custom_2d(
        head_front_z - 0.04,
        lambda c, _u=hu, _v=hv, _r=hr, _em=emotion, _t=t, _yb=yaw_bias: _draw_dummy_face_visor(c, _u, _v, _r, _em, _t, _yb, 1.0, False),
        bloom_fn=lambda b, _u=hu, _v=hv, _r=hr, _em=emotion, _t=t, _yb=yaw_bias: _draw_dummy_face_visor(b, _u, _v, _r, _em, _t, _yb, 0.25, True),
    )

    # Articulated 3D Arms with machined titanium joints
    for sh, el, ha in ((l_sh, l_el, l_ha), (r_sh, r_el, r_ha)):
        scene.add_sphere(_pt(*sh), 0.145 * scale, DUMMY_JOINT, metallic=0.68)
        scene.add_capsule(_pt(*sh), _pt(*el), 0.11 * scale, 0.095 * scale, DUMMY_SHELL, metallic=0.42, segments=12)
        scene.add_sphere(_pt(*el), 0.108 * scale, DUMMY_JOINT, metallic=0.68)
        scene.add_capsule(_pt(*el), _pt(*ha), 0.095 * scale, 0.082 * scale, DUMMY_SHELL, metallic=0.42, segments=12)
        scene.add_sphere(_pt(*ha), 0.115 * scale, DUMMY_JOINT, metallic=0.62)

    # Articulated 3D Legs & Industrial Boots
    for hip, kn, ft in ((l_hip, l_kn, l_ft), (r_hip, r_kn, r_ft)):
        scene.add_sphere(_pt(*hip), 0.135 * scale, DUMMY_JOINT, metallic=0.68)
        scene.add_capsule(_pt(*hip), _pt(*kn), 0.135 * scale, 0.112 * scale, DUMMY_SHELL, metallic=0.42, segments=12)
        scene.add_sphere(_pt(*kn), 0.118 * scale, DUMMY_JOINT, metallic=0.68)
        scene.add_capsule(_pt(*kn), _pt(*ft), 0.105 * scale, 0.092 * scale, DUMMY_SHELL, metallic=0.42, segments=12)
        scene.add_sphere(_pt(ft[0], ft[1] - 0.04, ft[2] + 0.09), 0.13 * scale, DUMMY_JOINT, metallic=0.65, squash_y=0.70)
