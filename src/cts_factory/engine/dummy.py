"""Articulated 3D Crash-Test Dummy Mascot ('UNIT-01') for FailSafe Lab.

Built entirely from true 3D Phong-shaded spheres, tapered 3D capsules, gunmetal
ball joints, iconic black-and-yellow crash-test calibration targets, and an
expressive curved dark-glass LED visor that reacts to every engineering beat.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from cts_factory.engine.renderer3d import Scene3D, rot_matrix

# Iconic Crash-Test Dummy Palette (distinct satin amber-gold polymer + titanium gunmetal)
DUMMY_SHELL = (242, 184, 46)       # Warm crash-test amber-yellow polymer
DUMMY_SHELL_ALT = (214, 152, 34)   # Secondary torso armor plate
DUMMY_JOINT = (44, 56, 74)         # Gunmetal mechanical ball joints
DUMMY_VISOR = (12, 18, 30)         # Glossy dark glass visor
DUMMY_RIM = (90, 220, 255)         # Studio cyan rim highlight


def _draw_quadrant_target(canvas: np.ndarray, cx: int, cy: int, r: int) -> None:
    """Draw iconic black-and-yellow crash-test dummy calibration target circle."""
    if r < 4:
        return
    cv2.circle(canvas, (cx, cy), r, (24, 24, 28), -1, lineType=cv2.LINE_AA)
    cv2.ellipse(canvas, (cx, cy), (r - 1, r - 1), 0, 0, 90, (46, 200, 250), -1, lineType=cv2.LINE_AA)
    cv2.ellipse(canvas, (cx, cy), (r - 1, r - 1), 0, 180, 270, (46, 200, 250), -1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), r, (14, 14, 18), max(1, r // 7), lineType=cv2.LINE_AA)
    cv2.line(canvas, (cx - r, cy), (cx + r, cy), (14, 14, 18), max(1, r // 9), lineType=cv2.LINE_AA)
    cv2.line(canvas, (cx, cy - r), (cx, cy + r), (14, 14, 18), max(1, r // 9), lineType=cv2.LINE_AA)


def _draw_dummy_face_visor(
    canvas: np.ndarray,
    u: float,
    v: float,
    pr: float,
    emotion: str,
    t: float,
    yaw_bias: float = 0.0,
) -> None:
    """Draw curved 3D obsidian glass visor, glowing expressive LED eyes, and forehead target."""
    if pr < 12:
        return
    cx = int(round(u + yaw_bias * pr * 0.28))
    cy = int(round(v + pr * 0.04))

    # Glossy recessed visor ellipse
    vw = max(8, int(round(pr * 0.72)))
    vh = max(6, int(round(pr * 0.44)))
    cv2.ellipse(canvas, (cx, cy), (vw, vh), 0, 0, 360, (24, 16, 10), -1, lineType=cv2.LINE_AA)
    cv2.ellipse(canvas, (cx, cy), (vw, vh), 0, 0, 360, (130, 105, 80), max(2, int(pr * 0.04)), lineType=cv2.LINE_AA)
    # Subtle glossy glass reflection streak on top-left of visor
    cv2.ellipse(
        canvas,
        (cx - int(vw * 0.25), cy - int(vh * 0.38)),
        (max(3, int(vw * 0.34)), max(2, int(vh * 0.14))),
        -15,
        0,
        360,
        (95, 78, 62),
        -1,
        lineType=cv2.LINE_AA,
    )

    # Forehead calibration target decal
    _draw_quadrant_target(canvas, int(round(u + yaw_bias * pr * 0.15)), int(round(v - pr * 0.56)), max(5, int(round(pr * 0.21))))

    # Expressive glowing LED eyes (BGR colors!)
    eye_dx = int(round(vw * 0.40))
    eye_y = cy - int(round(vh * 0.06))
    blink = 1.0 if ((t * 0.9) % 4.3) > 0.11 else 0.15

    if emotion in ("panic", "shock"):
        eye_bgr = (70, 215, 255)  # Electric gold-amber alarm eyes
        er = max(4, int(round(pr * 0.22)))
        jitter = int(round(math.sin(t * 48.0) * max(1.0, pr * 0.03)))
        for sx in (-1, 1):
            ex = cx + sx * eye_dx + jitter
            cv2.circle(canvas, (ex, eye_y), er + 3, (35, 95, 160), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (ex, eye_y), er, eye_bgr, -1, lineType=cv2.LINE_AA)
            # Tiny terrified pinprick pupil
            cv2.circle(canvas, (ex, eye_y), max(2, int(er * 0.32)), (18, 14, 12), -1, lineType=cv2.LINE_AA)
        # Sharp wide-open 'O' mouth LED
        mw = max(4, int(round(pr * 0.16)))
        mh = max(5, int(round(pr * 0.18)))
        cv2.ellipse(canvas, (cx, cy + int(vh * 0.46)), (mw, mh), 0, 0, 360, (60, 140, 255), max(2, int(pr * 0.05)), lineType=cv2.LINE_AA)
    elif emotion == "brace":
        # Tightly squinted "> <" bracing eyes
        eye_bgr = (60, 180, 255)
        s = max(4, int(round(pr * 0.16)))
        th = max(2, int(round(pr * 0.06)))
        # Left >
        cv2.line(canvas, (cx - eye_dx - s, eye_y - s // 2), (cx - eye_dx + s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx - eye_dx - s, eye_y + s // 2), (cx - eye_dx + s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        # Right <
        cv2.line(canvas, (cx + eye_dx + s, eye_y - s // 2), (cx + eye_dx - s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.line(canvas, (cx + eye_dx + s, eye_y + s // 2), (cx + eye_dx - s // 2, eye_y), eye_bgr, th, lineType=cv2.LINE_AA)
        # Gritted wave line
        cv2.line(canvas, (cx - s, cy + int(vh * 0.45)), (cx + s, cy + int(vh * 0.45)), eye_bgr, th, lineType=cv2.LINE_AA)
    elif emotion == "relief":
        # Happy curved "^ ^" emerald eyes
        eye_bgr = (140, 235, 65)
        r_arc = max(5, int(round(pr * 0.17)))
        th = max(2, int(round(pr * 0.065)))
        for sx in (-1, 1):
            cv2.ellipse(canvas, (cx + sx * eye_dx, eye_y + r_arc // 2), (r_arc, r_arc), 0, 200, 340, eye_bgr, th, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, (cx, cy + int(vh * 0.34)), (r_arc, int(r_arc * 0.6)), 0, 15, 165, eye_bgr, th, lineType=cv2.LINE_AA)
    elif emotion == "curious":
        # One raised, one narrowed analytical cyan eye
        eye_bgr = (255, 220, 40)
        er = max(4, int(round(pr * 0.17)))
        cv2.ellipse(canvas, (cx - eye_dx, eye_y), (er, max(2, int(er * blink))), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
        cv2.ellipse(canvas, (cx + eye_dx, eye_y - 2), (int(er * 1.15), max(2, int(er * 0.65 * blink))), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
    else:
        # Confident analytical engineer cyan eyes + subtle smile arc
        eye_bgr = (255, 218, 35)  # Bright telemetry cyan (BGR)
        er_x = max(4, int(round(pr * 0.16)))
        er_y = max(2, int(round(pr * 0.18 * blink)))
        for sx in (-1, 1):
            ex = cx + sx * eye_dx
            cv2.ellipse(canvas, (ex, eye_y), (er_x + 2, er_y + 2), 0, 0, 360, (140, 110, 20), -1, lineType=cv2.LINE_AA)
            cv2.ellipse(canvas, (ex, eye_y), (er_x, er_y), 0, 0, 360, eye_bgr, -1, lineType=cv2.LINE_AA)
        if emotion == "cta":
            # Raised eyebrow question mark energy + smirk
            cv2.ellipse(canvas, (cx, cy + int(vh * 0.38)), (int(pr * 0.18), int(pr * 0.10)), 0, 10, 170, (70, 210, 255), max(2, int(pr * 0.05)), lineType=cv2.LINE_AA)


def add_crash_test_dummy(
    scene: Scene3D,
    pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
    yaw: float = 0.0,
    pose: str = "explain",
    emotion: str = "engineer",
    t: float = 0.0,
    tilt_z: float = 0.0,
) -> None:
    """Add our fully articulated 3D Crash-Test Dummy ('UNIT-01') into any Scene3D.

    pos is the pelvis/hip center in world coordinates. Full standing height is ~2.7 * scale.
    """
    R = rot_matrix(0.0, yaw, tilt_z)
    origin = np.array(pos, dtype=np.float32)

    def _pt(x: float, y: float, z: float) -> tuple[float, float, float]:
        v = np.array([x * scale, y * scale, z * scale], dtype=np.float32)
        return tuple((origin + R @ v).tolist())

    bob = math.sin(t * 3.2) * 0.03
    if pose == "panic_freefall":
        bob = math.sin(t * 22.0) * 0.05

    # Core spine joints (local coordinates)
    pelvis = (0.0, 0.0 + bob, 0.0)
    chest = (0.0, 0.56 + bob, 0.02)
    neck = (0.0, 0.90 + bob, 0.02)
    head = (0.0, 1.24 + bob, 0.04)

    l_sh = (-0.42, 0.78 + bob, 0.0)
    r_sh = (0.42, 0.78 + bob, 0.0)
    l_hip = (-0.21, -0.10 + bob, 0.0)
    r_hip = (0.21, -0.10 + bob, 0.0)

    # Pose-specific arm & leg kinematics
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
    else:  # explain / neutral heroic stance
        sw = math.sin(t * 3.8) * 0.05
        l_el = (-0.54, 0.42 + bob, 0.10)
        l_ha = (-0.44, 0.12 + bob, 0.22)
        r_el = (0.60, 0.60 + bob, 0.18)
        r_ha = (0.82, 0.82 + bob + sw, 0.30)
        l_kn = (-0.23, -0.60, 0.05)
        l_ft = (-0.24, -1.16, 0.0)
        r_kn = (0.23, -0.60, 0.05)
        r_ft = (0.24, -1.16, 0.0)

    # --- Sculpted 3D Torso & Pelvis ---
    scene.add_capsule(_pt(*pelvis), _pt(0.0, 0.50 + bob, 0.0), 0.23 * scale, 0.30 * scale, DUMMY_SHELL_ALT, metallic=0.35, rim_rgb=DUMMY_RIM, segments=16)
    scene.add_sphere(_pt(*pelvis), 0.25 * scale, DUMMY_JOINT, metallic=0.55)
    # Neck hydraulic cylinder (seated cleanly inside upper collar)
    scene.add_cylinder(_pt(0.0, 0.76 + bob, -0.02), _pt(0.0, 0.98 + bob, 0.0), 0.115 * scale, 0.105 * scale, DUMMY_JOINT, segments=14, metallic=0.65, caps=False)
    # Armored chest shell + calibration badge
    cu, cv, cr = scene.add_sphere(_pt(0.0, 0.56 + bob, 0.05), 0.33 * scale, DUMMY_SHELL, metallic=0.38, squash_y=1.08)
    chest_z = scene.cam.project_point(_pt(0.0, 0.56 + bob, 0.40))[2]
    scene.add_custom_2d(
        chest_z - 0.03,
        lambda c, _u=cu, _v=cv, _r=cr: _draw_quadrant_target(c, int(round(_u)), int(round(_v + _r * 0.05)), max(5, int(round(_r * 0.32)))),
    )

    # --- 3D Head + Glossy Expressive LED Visor ---
    hu, hv, hr = scene.add_sphere(_pt(*head), 0.37 * scale, DUMMY_SHELL, metallic=0.34, squash_y=1.06, rim_rgb=DUMMY_RIM)
    head_front_z = scene.cam.project_point(_pt(0.0, 1.24 + bob, 0.44))[2]
    yaw_bias = math.sin(yaw)
    scene.add_custom_2d(
        head_front_z - 0.04,
        lambda c, _u=hu, _v=hv, _r=hr, _em=emotion, _t=t, _yb=yaw_bias: _draw_dummy_face_visor(c, _u, _v, _r, _em, _t, _yb),
    )

    # --- Articulated 3D Arms ---
    for sh, el, ha in ((l_sh, l_el, l_ha), (r_sh, r_el, r_ha)):
        scene.add_sphere(_pt(*sh), 0.14 * scale, DUMMY_JOINT, metallic=0.6)
        scene.add_capsule(_pt(*sh), _pt(*el), 0.11 * scale, 0.095 * scale, DUMMY_SHELL, metallic=0.35, segments=14)
        scene.add_sphere(_pt(*el), 0.105 * scale, DUMMY_JOINT, metallic=0.6)
        scene.add_capsule(_pt(*el), _pt(*ha), 0.095 * scale, 0.08 * scale, DUMMY_SHELL, metallic=0.35, segments=14)
        scene.add_sphere(_pt(*ha), 0.11 * scale, DUMMY_JOINT, metallic=0.5)

    # --- Articulated 3D Legs & Boots ---
    for hip, kn, ft in ((l_hip, l_kn, l_ft), (r_hip, r_kn, r_ft)):
        scene.add_sphere(_pt(*hip), 0.13 * scale, DUMMY_JOINT, metallic=0.6)
        scene.add_capsule(_pt(*hip), _pt(*kn), 0.135 * scale, 0.11 * scale, DUMMY_SHELL, metallic=0.35, segments=14)
        scene.add_sphere(_pt(*kn), 0.115 * scale, DUMMY_JOINT, metallic=0.6)
        scene.add_capsule(_pt(*kn), _pt(*ft), 0.105 * scale, 0.09 * scale, DUMMY_SHELL, metallic=0.35, segments=14)
        scene.add_sphere(_pt(ft[0], ft[1] - 0.04, ft[2] + 0.08), 0.125 * scale, DUMMY_JOINT, metallic=0.55, squash_y=0.72)
