from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import random
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.schemas import GripperCommand, StepRequest, VRStateUpdateRequest

try:
    import mujoco as _mujoco  # type: ignore
except Exception:
    _mujoco = None

try:
    import numpy as np  # type: ignore
except Exception:
    np = None


DEFAULT_ARM_JOINT_NAMES = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]
DEFAULT_GRIPPER_JOINT_NAMES = [
    "left_driver_joint",
    "right_driver_joint",
    "left_spring_link_joint",
    "right_spring_link_joint",
    "left_follower_joint",
    "right_follower_joint",
]
DEFAULT_ARM_ACTUATOR_NAMES = [
    "act_shoulder_pan",
    "act_shoulder_lift",
    "act_elbow",
    "act_wrist_1",
    "act_wrist_2",
    "act_wrist_3",
]
DEFAULT_GRIPPER_ACTUATOR_NAME = "act_gripper_driver"
TOOL_BODY_NAMES = {
    "toolbox",
    "wrench_01",
    "screwdriver_01",
    "pliers_01",
}
GRASPABLE_TOOL_BODY_NAMES = {
    "wrench_01",
    "screwdriver_01",
    "pliers_01",
}
GRIPPER_BODY_NAMES = {
    "left_driver_link",
    "left_coupler_link",
    "left_spring_link",
    "left_follower_link",
    "left_pad_link",
    "right_driver_link",
    "right_coupler_link",
    "right_spring_link",
    "right_follower_link",
    "right_pad_link",
}

DEFAULT_HOME_QPOS = [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0]
DEFAULT_DT = 0.02
GRIPPER_DRIVER_LIMIT = 0.9
ARM_COMMAND_BLEND_PER_STEP = 0.12
GRIPPER_COMMAND_BLEND_PER_STEP = 0.16
TOOL_SITE_CANDIDATES = ["tool0"]
TOOL_BODY_CANDIDATES = ["tool0", "wrist_3_link"]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MUJOCO_MODEL_PATH = REPO_ROOT / "backend" / "mujoco_models" / "environment.xml"
DEFAULT_CAMERA_SENSOR_CONFIG_PATH = REPO_ROOT / "shared" / "camera_sensor_config.json"
DEFAULT_DATASET_SCHEMA_PATH = REPO_ROOT / "shared" / "dataset_schema.json"
DEFAULT_HANDOVER_SCENE_CONFIG_PATH = REPO_ROOT / "shared" / "handover_scene_config.json"
MUJOCO_DEPTH_MAP_MODE = str(os.getenv("SIM_MUJOCO_DEPTH_MAP", "zeronear")).strip().lower()
BACKEND_FRAME_Z_OFFSET = 0.5
BACKEND_ALIGNMENT_QUATERNION = [math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0]
MAX_ALLOWED_PENETRATION_M = 8e-4
MAX_COLLISION_REPORTS = 3
ENABLE_HARD_COLLISION_ROLLBACK = str(
    os.getenv("SIM_ENABLE_HARD_COLLISION_ROLLBACK", "true")
).strip().lower() not in {"0", "false", "off", "no"}
EXPECTED_CAMERA_DEVICE = "intel_realsense_d405"
EXPECTED_RGB_CAMERA_NAME = "d405_rgb"
EXPECTED_DEPTH_CAMERA_NAME = "d405_depth"
DEFAULT_CAMERA_MOUNT_POSITION = [0.0, -0.077929684, 0.077]
DEFAULT_CAMERA_MOUNT_QUATERNION = [0.0, 1.0, 0.0, 0.0]
DEFAULT_RGB_STREAM = {
    "interface_name": "sim_camera_rgb",
    "camera_name": "d405_rgb",
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "pixel_format": "rgb8",
    "dataset_storage_format": "jpg",
}
DEFAULT_DEPTH_STREAM = {
    "interface_name": "sim_camera_depth",
    "camera_name": "d405_depth",
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "pixel_format": "depth16",
    "dataset_storage_format": "png16",
    "depth_unit": "millimeter",
    "depth_scale": 1.0,
}
DEFAULT_CAMERA_ALIGNMENT_MODE = "same_tick"
DEFAULT_CAMERA_ALIGNMENT_MAX_DELTA_MS = 5.0
DEFAULT_CAMERA_DEBUG_OBJECTS = ["camera_base", "camera"]
REALTIME_SOURCE_MIN_PHYSICS_HORIZON_S = 0.024
REALTIME_COMMAND_BLEND_PER_STEP = 1.0
REALTIME_ARM_MAX_DELTA_RAD = 0.12
REALTIME_GRIPPER_MAX_DELTA_OPENING = 0.18
# Conservative realtime EE tracking defaults. These favor smooth, stable
# teleoperation over aggressive goal chasing when XR pose input is noisy.
REALTIME_EE_TARGET_MAX_STEP_M = 0.05
REALTIME_EE_TARGET_MAX_STEP_RAD = 0.20
REALTIME_EE_POSITION_DEADBAND_M = 1.5e-3
REALTIME_EE_ORIENTATION_DEADBAND_RAD = 0.018
REALTIME_EE_RESEED_DRIFT_M = 0.22
REALTIME_EE_RESEED_DRIFT_RAD = 0.70
PASSIVE_ADVANCE_MAX_STEPS = 80
INTERACTIVE_SOURCE_MAX_BLOCKING_STEPS = 5
SLIDER_COMMIT_MAX_BLOCKING_STEPS = 24
STREAMING_CONTROL_HOLD_TIMEOUT_S = 0.18
FRONTEND_SLIDER_OVERWRITE_GUARD_S = 2.0
SERVO_HOLD_ARM_ERROR_RAD = 0.006
SERVO_HOLD_GRIPPER_ERROR_OPENING = 0.008
SERVO_BRAKE_ARM_ERROR_RAD = 0.022
SERVO_BRAKE_GRIPPER_ERROR_OPENING = 0.022
SERVO_BRAKE_ARM_QVEL_RAD_S = 0.12
SERVO_BRAKE_GRIPPER_QVEL_OPENING_S = 0.06
SERVO_CTRL_ARM_MAX_SPEED_RAD_S = 1.8
SERVO_CTRL_GRIPPER_MAX_SPEED_OPENING_S = 2.4
SERVO_CTRL_ARM_MAX_ACCEL_RAD_S2 = 12.0
SERVO_CTRL_GRIPPER_MAX_ACCEL_OPENING_S2 = 14.0
SERVO_CTRL_ARM_MAX_JERK_RAD_S3 = 80.0
SERVO_CTRL_GRIPPER_MAX_JERK_OPENING_S3 = 110.0
REALTIME_SERVO_CTRL_ARM_MAX_SPEED_RAD_S = 3.2
REALTIME_SERVO_CTRL_GRIPPER_MAX_SPEED_OPENING_S = 3.8
REALTIME_SERVO_CTRL_ARM_MAX_ACCEL_RAD_S2 = 36.0
REALTIME_SERVO_CTRL_GRIPPER_MAX_ACCEL_OPENING_S2 = 34.0
REALTIME_SERVO_CTRL_ARM_MAX_JERK_RAD_S3 = 260.0
REALTIME_SERVO_CTRL_GRIPPER_MAX_JERK_OPENING_S3 = 260.0
IK_MAX_ITERATIONS = 24
IK_REALTIME_MAX_ITERATIONS = 10
IK_POSITION_TOLERANCE_M = 0.003
IK_ORIENTATION_TOLERANCE_RAD = 0.035
IK_DAMPING = 0.10
IK_MAX_STEP_RAD = 0.24
IK_POSITION_WEIGHT = 1.0
IK_ORIENTATION_WEIGHT = 0.30
# Realtime XR teleop benefits from a more conservative IK profile: smaller
# joint updates and lighter orientation coupling reduce the "near the tool and
# suddenly flailing" failure mode without changing the user's control strategy.
IK_REALTIME_DAMPING = 0.16
IK_REALTIME_MAX_STEP_RAD = 0.16
IK_REALTIME_ORIENTATION_WEIGHT = 0.16
IK_REALTIME_LOCKED_ORIENTATION_WEIGHT = 0.05
CARTESIAN_SERVO_LINEAR_GAIN_S = 4.2
CARTESIAN_SERVO_ANGULAR_GAIN_S = 2.8
CARTESIAN_SERVO_LINEAR_DAMPING = 0.25
CARTESIAN_SERVO_ANGULAR_DAMPING = 0.20
CARTESIAN_SERVO_MAX_LINEAR_SPEED_M_S = 0.34
CARTESIAN_SERVO_MAX_ANGULAR_SPEED_RAD_S = 1.18
CARTESIAN_SERVO_DAMPING = 0.10
CARTESIAN_SERVO_POSITION_WEIGHT = 1.0
CARTESIAN_SERVO_ORIENTATION_WEIGHT = 0.34
CARTESIAN_SERVO_LOCKED_ORIENTATION_WEIGHT = 0.0
CARTESIAN_SERVO_MAX_JOINT_SPEED_RAD_S = 1.35
CARTESIAN_SERVO_MAX_JOINT_ACCEL_RAD_S2 = 9.0
CARTESIAN_SERVO_COMMAND_LOOKAHEAD_S = 0.030
CARTESIAN_SERVO_MAX_COMMAND_LEAD_RAD = 0.045
CARTESIAN_SERVO_JOINT_LIMIT_MARGIN_RAD = 0.18
CARTESIAN_SERVO_MIN_SINGULAR_VALUE = 0.035
CARTESIAN_SERVO_POSITION_DEADBAND_M = 1.2e-3
CARTESIAN_SERVO_ORIENTATION_DEADBAND_RAD = 0.010
GRASP_ASSIST_MODE = str(os.getenv("SIM_GRASP_ASSIST_MODE", "disabled")).strip().lower()
GRASP_ASSIST_ENABLED_MODES = {
    "1",
    "true",
    "on",
    "enabled",
    "assist",
    "loose",
    "strict",
    "high_fidelity",
    "contact",
}
GRASP_ASSIST_STRICT_CONTACT_MODES = {"strict", "high_fidelity", "contact"}
GRIPPER_GRASP_ENGAGE_OPENING = 0.70
GRIPPER_GRASP_RELEASE_OPENING = 0.24
GRIPPER_GRASP_CONTACT_MARGIN_M = 0.003
GRIPPER_GRASP_PAD_BODY_NAMES = ("left_pad_link", "right_pad_link")
SCENE_SETTLE_STEPS = 1000


@dataclass
class _QueuedCommand:
    request: StepRequest
    future: asyncio.Future[dict[str, Any]]
    return_state: bool = True


@dataclass
class _CartesianServoTarget:
    source_key: str
    position: list[float]
    quaternion: list[float]
    orientation_follow_enabled: bool
    updated_at: float
    last_qvel: list[float]
    last_qaccel: list[float]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _compute_command_blend(n_steps: int, per_step_blend: float) -> float:
    """
    Convert a per-step blend ratio to a final blend for this command horizon.
    Small n_steps -> smoother incremental move; large n_steps -> closer to target.
    """
    steps = max(1, int(n_steps))
    per_step = _clamp(float(per_step_blend), 0.0, 1.0)
    if per_step <= 0.0:
        return 0.0
    if per_step >= 1.0:
        return 1.0
    return 1.0 - math.pow(1.0 - per_step, steps)


def _normalize_control_source(source: str, input_source: str | None = None) -> str:
    normalized_source = str(source or "").strip().lower()
    normalized_input = str(input_source or "").strip().lower()
    if normalized_source in {"manual", "desktop_manual"} and normalized_input in {"slider", "joint_slider"}:
        return "desktop_manual_slider"
    return normalized_source


def _resolve_command_blend(
    source: str,
    n_steps: int,
    per_step_blend: float,
    input_source: str | None = None,
) -> float:
    """
    VR teleop sources are already incremental, but LAN delivery can be bursty.
    Blend them over the physics horizon so the actuator target advances without
    snapping back and forth when an older broadcast arrives late.
    """
    normalized = _normalize_control_source(source, input_source=input_source)
    if normalized in {"quest3_controller", "quest3_hand", "desktop_manual_slider"}:
        return _clamp(REALTIME_COMMAND_BLEND_PER_STEP, 0.0, 1.0)
    return _compute_command_blend(n_steps, per_step_blend)


def _is_realtime_source(source: str, input_source: str | None = None) -> bool:
    normalized = _normalize_control_source(source, input_source=input_source)
    return normalized in {"quest3_controller", "quest3_hand", "desktop_manual_slider"}


def _should_limit_realtime_target_delta(source: str, input_source: str | None = None) -> bool:
    normalized = _normalize_control_source(source, input_source=input_source)
    return normalized in {"quest3_controller", "quest3_hand"}


def _should_hold_stale_streaming_source(source: str, input_source: str | None = None) -> bool:
    normalized = _normalize_control_source(source, input_source=input_source)
    return normalized in {"quest3_controller", "quest3_hand"}


def _is_interactive_source(source: str, input_source: str | None = None) -> bool:
    normalized = _normalize_control_source(source, input_source=input_source)
    return normalized in {
        "manual",
        "desktop_manual",
        "desktop_manual_slider",
        "quest3_controller",
        "quest3_hand",
    }


def _resolve_physics_steps(source: str, requested_steps: int, dt: float, input_source: str | None = None) -> int:
    base_steps = max(1, int(requested_steps))
    normalized = _normalize_control_source(source, input_source=input_source)
    if normalized not in {"quest3_controller", "quest3_hand", "desktop_manual_slider"}:
        return base_steps
    stable_dt = max(1e-4, float(dt))
    min_steps = max(1, int(round(REALTIME_SOURCE_MIN_PHYSICS_HORIZON_S / stable_dt)))
    return max(base_steps, min_steps)


def _read_orientation_follow_enabled_from_request(request: StepRequest) -> bool:
    normalized_input = getattr(request, "normalized_input", None)
    if not isinstance(normalized_input, dict):
        return False
    return float(normalized_input.get("orientation_follow_enabled", 0) or 0) >= 0.5


def _should_servo_snap_to_target(
    error: float,
    velocity: float,
    hold_tolerance: float,
    brake_tolerance: float,
    min_brake_velocity: float,
) -> bool:
    abs_error = abs(float(error))
    abs_velocity = abs(float(velocity))
    if abs_error <= hold_tolerance:
        return abs_velocity <= min_brake_velocity
    if abs_error > brake_tolerance:
        return False
    if abs_velocity <= min_brake_velocity:
        return True
    return float(error) * float(velocity) < 0.0


def _resolve_servo_motion_limits(source: str, input_source: str | None = None) -> dict[str, float]:
    if _is_realtime_source(source, input_source=input_source):
        return {
            "arm_speed": REALTIME_SERVO_CTRL_ARM_MAX_SPEED_RAD_S,
            "arm_accel": REALTIME_SERVO_CTRL_ARM_MAX_ACCEL_RAD_S2,
            "arm_jerk": REALTIME_SERVO_CTRL_ARM_MAX_JERK_RAD_S3,
            "gripper_speed": REALTIME_SERVO_CTRL_GRIPPER_MAX_SPEED_OPENING_S,
            "gripper_accel": REALTIME_SERVO_CTRL_GRIPPER_MAX_ACCEL_OPENING_S2,
            "gripper_jerk": REALTIME_SERVO_CTRL_GRIPPER_MAX_JERK_OPENING_S3,
        }
    return {
        "arm_speed": SERVO_CTRL_ARM_MAX_SPEED_RAD_S,
        "arm_accel": SERVO_CTRL_ARM_MAX_ACCEL_RAD_S2,
        "arm_jerk": SERVO_CTRL_ARM_MAX_JERK_RAD_S3,
        "gripper_speed": SERVO_CTRL_GRIPPER_MAX_SPEED_OPENING_S,
        "gripper_accel": SERVO_CTRL_GRIPPER_MAX_ACCEL_OPENING_S2,
        "gripper_jerk": SERVO_CTRL_GRIPPER_MAX_JERK_OPENING_S3,
    }


def _is_slider_commit_input(input_source: str | None) -> bool:
    return str(input_source or "").strip().lower() == "slider_commit"


def _is_grasp_assist_enabled() -> bool:
    return GRASP_ASSIST_MODE in GRASP_ASSIST_ENABLED_MODES


def _grasp_assist_requires_both_pads() -> bool:
    return GRASP_ASSIST_MODE in GRASP_ASSIST_STRICT_CONTACT_MODES


def _is_desktop_slider_input(source: str | None, input_source: str | None) -> bool:
    normalized_source = str(source or "").strip().lower()
    normalized_input = str(input_source or "").strip().lower()
    return normalized_source in {"manual", "desktop_manual"} and normalized_input in {
        "slider",
        "joint_slider",
        "slider_commit",
    }


def _request_origin(raw_input: dict[str, Any] | None) -> str:
    if not isinstance(raw_input, dict):
        return ""
    return str(raw_input.get("origin", "") or "").strip().lower()


def _move_toward(value: float, target: float, max_delta: float) -> float:
    delta = float(target) - float(value)
    return float(value) + _clamp(delta, -abs(float(max_delta)), abs(float(max_delta)))


def _vec_distance(lhs: list[float], rhs: list[float]) -> float:
    return math.sqrt(
        sum(
            math.pow(float(lhs[idx]) - float(rhs[idx]), 2.0)
            for idx in range(min(len(lhs), len(rhs), 3))
        )
    )


def _quaternion_angle_distance_rad(lhs: list[float], rhs: list[float]) -> float:
    left = _normalize_quaternion(lhs)
    right = _normalize_quaternion(rhs)
    dot = abs(sum(left[idx] * right[idx] for idx in range(4)))
    return 2.0 * math.acos(_clamp(dot, -1.0, 1.0))


def _quaternion_slerp(lhs: list[float], rhs: list[float], alpha: float) -> list[float]:
    left = _normalize_quaternion(lhs)
    right = _normalize_quaternion(rhs)
    dot = sum(left[idx] * right[idx] for idx in range(4))
    if dot < 0.0:
        right = [-value for value in right]
        dot = -dot

    t = _clamp(float(alpha), 0.0, 1.0)
    if dot > 0.9995:
        return _normalize_quaternion([
            left[idx] + (right[idx] - left[idx]) * t
            for idx in range(4)
        ])

    theta_0 = math.acos(_clamp(dot, -1.0, 1.0))
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return _normalize_quaternion([
        left[idx] * s0 + right[idx] * s1
        for idx in range(4)
    ])


def _advance_smooth_servo_target(
    current: float,
    target: float,
    velocity: float,
    acceleration: float,
    dt: float,
    max_speed: float,
    max_accel: float,
    max_jerk: float,
) -> tuple[float, float, float]:
    stable_dt = max(float(dt), 1e-6)
    current_value = float(current)
    target_value = float(target)
    try:
        current_velocity = float(velocity)
    except (TypeError, ValueError):
        current_velocity = 0.0
    if not math.isfinite(current_velocity):
        current_velocity = 0.0
    try:
        current_acceleration = float(acceleration)
    except (TypeError, ValueError):
        current_acceleration = 0.0
    if not math.isfinite(current_acceleration):
        current_acceleration = 0.0
    error = target_value - current_value
    if abs(error) <= 1e-7 and abs(current_velocity) <= 1e-6 and abs(current_acceleration) <= 1e-5:
        return target_value, 0.0, 0.0

    speed_limit = max(1e-6, abs(float(max_speed)))
    accel_limit = max(1e-6, abs(float(max_accel)))
    jerk_limit = max(1e-6, abs(float(max_jerk)))
    desired_speed = min(speed_limit, math.sqrt(max(0.0, 2.0 * accel_limit * abs(error))))
    desired_velocity = math.copysign(desired_speed, error) if abs(error) > 1e-9 else 0.0
    desired_acceleration = _clamp(
        (desired_velocity - current_velocity) / stable_dt,
        -accel_limit,
        accel_limit,
    )
    next_acceleration = _move_toward(
        current_acceleration,
        desired_acceleration,
        jerk_limit * stable_dt,
    )
    next_acceleration = _clamp(next_acceleration, -accel_limit, accel_limit)
    next_velocity = _clamp(
        current_velocity + next_acceleration * stable_dt,
        -speed_limit,
        speed_limit,
    )
    next_position = current_value + next_velocity * stable_dt

    if (target_value - current_value) * (target_value - next_position) <= 0.0:
        return target_value, 0.0, 0.0
    return next_position, next_velocity, next_acceleration


def _rpy_to_quaternion(roll: float, pitch: float, yaw: float) -> list[float]:
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return [w, x, y, z]


def _euler_xyz_to_quaternion(x_angle: float, y_angle: float, z_angle: float) -> list[float]:
    """
    Match Three.js `Euler(..., "XYZ")` so manifest rotations stay frame-consistent
    between frontend object init and backend MuJoCo state sync.
    """
    hx = x_angle * 0.5
    hy = y_angle * 0.5
    hz = z_angle * 0.5
    sx, cx = math.sin(hx), math.cos(hx)
    sy, cy = math.sin(hy), math.cos(hy)
    sz, cz = math.sin(hz), math.cos(hz)
    return [
        cx * cy * cz - sx * sy * sz,
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
    ]


def _quaternion_multiply(lhs_wxyz: list[float], rhs_wxyz: list[float]) -> list[float]:
    lw, lx, ly, lz = lhs_wxyz
    rw, rx, ry, rz = rhs_wxyz
    return [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]


def _quaternion_conjugate(quaternion_wxyz: list[float]) -> list[float]:
    w, x, y, z = quaternion_wxyz
    return [w, -x, -y, -z]


def _normalize_quaternion(quaternion_wxyz: list[float]) -> list[float]:
    if len(quaternion_wxyz) < 4:
        return [1.0, 0.0, 0.0, 0.0]
    w, x, y, z = [float(v) for v in quaternion_wxyz[:4]]
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm <= 1e-8:
        return [1.0, 0.0, 0.0, 0.0]
    inv = 1.0 / norm
    return [w * inv, x * inv, y * inv, z * inv]


def _quaternion_error_vector(target_wxyz: list[float], current_wxyz: list[float]) -> list[float]:
    target = _normalize_quaternion(target_wxyz)
    current = _normalize_quaternion(current_wxyz)
    error = _quaternion_multiply(target, _quaternion_conjugate(current))
    if error[0] < 0.0:
        error = [-value for value in error]
    w, x, y, z = error
    sin_half = math.sqrt(x * x + y * y + z * z)
    if sin_half <= 1e-8:
        return [2.0 * x, 2.0 * y, 2.0 * z]
    angle = 2.0 * math.atan2(sin_half, max(-1.0, min(1.0, w)))
    scale = angle / sin_half
    return [x * scale, y * scale, z * scale]


def _rotate_vector_by_quaternion(vector_xyz: list[float], quaternion_wxyz: list[float]) -> list[float]:
    q = _normalize_quaternion(quaternion_wxyz)
    pure = [0.0, float(vector_xyz[0]), float(vector_xyz[1]), float(vector_xyz[2])]
    rotated = _quaternion_multiply(_quaternion_multiply(q, pure), _quaternion_conjugate(q))
    return [float(rotated[1]), float(rotated[2]), float(rotated[3])]


def _compose_pose(
    parent_position_xyz: list[float],
    parent_quaternion_wxyz: list[float],
    child_position_xyz: list[float],
    child_quaternion_wxyz: list[float],
) -> dict[str, list[float]]:
    parent_q = _normalize_quaternion(parent_quaternion_wxyz)
    child_q = _normalize_quaternion(child_quaternion_wxyz)
    rotated_child_pos = _rotate_vector_by_quaternion(child_position_xyz, parent_q)
    composed_position = [
        float(parent_position_xyz[0]) + rotated_child_pos[0],
        float(parent_position_xyz[1]) + rotated_child_pos[1],
        float(parent_position_xyz[2]) + rotated_child_pos[2],
    ]
    composed_quaternion = _normalize_quaternion(_quaternion_multiply(parent_q, child_q))
    return {
        "position": composed_position,
        "quaternion": composed_quaternion,
    }


def _matrix_to_quaternion_wxyz(matrix_rowmajor: Any) -> list[float]:
    values = [float(v) for v in list(matrix_rowmajor)[:9]]
    if len(values) < 9:
        return [1.0, 0.0, 0.0, 0.0]
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = values
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return _normalize_quaternion([
            0.25 * s,
            (m21 - m12) / s,
            (m02 - m20) / s,
            (m10 - m01) / s,
        ])
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        return _normalize_quaternion([
            (m21 - m12) / s,
            0.25 * s,
            (m01 + m10) / s,
            (m02 + m20) / s,
        ])
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        return _normalize_quaternion([
            (m02 - m20) / s,
            (m01 + m10) / s,
            0.25 * s,
            (m12 + m21) / s,
        ])
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
    return _normalize_quaternion([
        (m10 - m01) / s,
        (m02 + m20) / s,
        (m12 + m21) / s,
        0.25 * s,
    ])


class SimulationCore:
    def __init__(self, manifest_path: Path):
        self._manifest_path = manifest_path
        self._manifest_data: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._command_queue: asyncio.Queue[_QueuedCommand] = asyncio.Queue()
        self._queue_worker: asyncio.Task[None] | None = None
        self._running = False

        self._model_backend = "mujoco" if _mujoco is not None else "stub"
        self._loaded_model_path: str | None = None
        self._model_load_error: str | None = None
        self._default_model_path = DEFAULT_MUJOCO_MODEL_PATH
        self._arm_joint_names = list(DEFAULT_ARM_JOINT_NAMES)
        self._home_arm_qpos = list(DEFAULT_HOME_QPOS)
        self._scene_objects_template: dict[str, dict[str, Any]] = {}
        self._scene_objects_manifest_template: dict[str, dict[str, Any]] = {}
        self._object_reset_policy: dict[str, dict[str, Any]] = {}
        self._spawn_regions: dict[str, dict[str, Any]] = {}
        self._camera_sensor_config_path: str | None = None
        self._dataset_schema_path: str | None = None
        self._handover_scene_config_path: str | None = None
        self._dataset_schema: dict[str, Any] = {}
        self._handover_zones: list[dict[str, Any]] = []
        self._camera_smoke_test_plan: dict[str, Any] = {}
        self._camera_device = "intel_realsense_d405"
        self._camera_mount_name = "wrist_d405_v1"
        self._camera_mount_parent_frame = "wrist_3_link"
        self._camera_pose_in_ee = {
            "position": list(DEFAULT_CAMERA_MOUNT_POSITION),
            "quaternion": list(DEFAULT_CAMERA_MOUNT_QUATERNION),
        }
        self._camera_intrinsics_version = "d405_intr_20260412_a"
        self._camera_extrinsics_version = "d405_ext_20260412_a"
        self._camera_alignment_mode = DEFAULT_CAMERA_ALIGNMENT_MODE
        self._camera_alignment_max_delta_ms = float(DEFAULT_CAMERA_ALIGNMENT_MAX_DELTA_MS)
        self._camera_recordable_training_observation = True
        self._camera_debug_only_objects = list(DEFAULT_CAMERA_DEBUG_OBJECTS)
        self._rgb_stream = dict(DEFAULT_RGB_STREAM)
        self._depth_stream = dict(DEFAULT_DEPTH_STREAM)
        self._camera_capture_interval_s = 1.0 / max(1.0, float(self._rgb_stream["fps"]))
        self._camera_frame_counter = 0
        self._camera_last_capture_ts = 0.0
        self._camera_last_state: dict[str, Any] | None = None
        self._camera_last_rgb_frame: Any | None = None
        self._camera_last_depth_frame: Any | None = None

        self._mj_model: Any | None = None
        self._mj_data: Any | None = None
        self._arm_joint_qpos_addr: dict[str, int] = {}
        self._arm_joint_qvel_addr: dict[str, int] = {}
        self._arm_joint_limits: dict[str, tuple[float, float]] = {}
        self._gripper_joint_qpos_addr: dict[str, int] = {}
        self._gripper_joint_qvel_addr: dict[str, int] = {}
        self._arm_actuator_ids: dict[str, int] = {}
        self._gripper_driver_actuator_id: int | None = None
        self._object_body_ids: dict[str, int] = {}
        self._object_freejoint_qpos_addr: dict[str, int] = {}
        self._object_freejoint_dof_addr: dict[str, int] = {}
        self._gripper_body_ids: dict[str, int] = {}
        self._tool_site_id: int | None = None
        self._tool_body_id: int | None = None
        self._mj_rgb_camera_id: int = -1
        self._mj_depth_camera_id: int = -1
        self._mj_renderer: Any | None = None
        self._mj_renderer_width = 0
        self._mj_renderer_height = 0

        self._arm_qpos = list(DEFAULT_HOME_QPOS)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._arm_command_qpos = list(DEFAULT_HOME_QPOS)
        self._arm_servo_ctrl_qpos = list(DEFAULT_HOME_QPOS)
        self._arm_servo_ctrl_qvel = [0.0 for _ in self._arm_servo_ctrl_qpos]
        self._arm_servo_ctrl_qaccel = [0.0 for _ in self._arm_servo_ctrl_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
        self._gripper_command_opening = 0.0
        self._gripper_servo_ctrl_opening = 0.0
        self._gripper_servo_ctrl_velocity = 0.0
        self._gripper_servo_ctrl_accel = 0.0
        self._gripper_joints = self._map_gripper_joints(0.0)
        self._objects_state: dict[str, dict[str, Any]] = {}
        self._attached_object_id: str | None = None
        self._attached_object_rel_position: list[float] | None = None
        self._attached_object_rel_quaternion: list[float] | None = None
        self._source = "manual"
        self._task_state = {"running": False, "name": None, "phase": None}
        self._vr_state = {
            "mode": "vr_disabled",
            "input_source_available": {
                "controller": False,
                "hand": False,
            },
            "selected_joint_group": "arm_full",
            "control_owner": "desktop_manual",
            "recording_ready": False,
            "last_quest_input_ts": None,
            "active_policy_path": None,
            "error_message": None,
        }
        self._last_input_source: str | None = None
        self._last_selected_joint_group: str | None = None
        self._last_raw_input: dict[str, Any] | None = None
        self._last_normalized_input: dict[str, Any] | None = None
        self._safety_status = "normal"
        self._collision_blocked = False
        self._last_collision_contacts: list[dict[str, Any]] = []
        self._sim_time = 0.0
        self._dt = DEFAULT_DT
        self._stats = {
            "steps": 0,
            "commands": 0,
            "last_step_ms": 0.0,
            "avg_step_ms": 0.0,
            "camera_frames": 0,
            "camera_drops": 0,
        }
        self._latest_realtime_seq_by_source: dict[str, int] = {}
        self._realtime_ee_target_by_source: dict[str, dict[str, list[float]]] = {}
        self._active_cartesian_servo_target: _CartesianServoTarget | None = None
        self._pending_realtime_futures_by_source: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_realtime_commands_by_source: dict[str, _QueuedCommand] = {}
        self._last_streaming_command_at: float | None = None
        self._frontend_slider_guard_until: float = 0.0

        self._load_scene_manifest()
        self._load_model(None)
        self._reset_state_locked()

    @property
    def model_backend(self) -> str:
        return self._model_backend

    @property
    def scene_manifest_path(self) -> str:
        return str(self._manifest_path)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._queue_worker = asyncio.create_task(self._command_worker(), name="sim-command-worker")

    async def stop(self) -> None:
        self._running = False
        if self._queue_worker is not None:
            self._queue_worker.cancel()
            try:
                await self._queue_worker
            except asyncio.CancelledError:
                pass
            self._queue_worker = None
        async with self._lock:
            self._close_mujoco_renderer()

    def _track_realtime_future(
        self,
        request: StepRequest,
        future: asyncio.Future[dict[str, Any]],
        return_state: bool,
    ) -> None:
        if return_state:
            return

        source_key = self._realtime_queue_source_key(request)
        if source_key is None:
            return

        previous = self._pending_realtime_futures_by_source.get(source_key)
        if previous is not None and previous is not future and not previous.done():
            previous.cancel()

        self._pending_realtime_futures_by_source[source_key] = future

        def _clear_done(done_future: asyncio.Future[dict[str, Any]]) -> None:
            if self._pending_realtime_futures_by_source.get(source_key) is done_future:
                self._pending_realtime_futures_by_source.pop(source_key, None)

        future.add_done_callback(_clear_done)

    def queue_step(self, request: StepRequest, return_state: bool = True) -> asyncio.Future[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._remember_realtime_command_seq(request)
        self._track_realtime_future(request, future, return_state=bool(return_state))
        source_key = self._realtime_queue_source_key(request) if not bool(return_state) else None
        pending = self._pending_realtime_commands_by_source.get(source_key) if source_key else None
        if pending is not None:
            previous_future = pending.future
            pending.request = request
            pending.future = future
            pending.return_state = bool(return_state)
            if previous_future is not future and not previous_future.done():
                previous_future.cancel()
            return future

        queued_command = _QueuedCommand(
            request=request,
            future=future,
            return_state=bool(return_state),
        )
        if source_key is not None:
            self._pending_realtime_commands_by_source[source_key] = queued_command
        self._command_queue.put_nowait(queued_command)
        return future

    async def enqueue_step(self, request: StepRequest, return_state: bool = True) -> dict[str, Any]:
        future = self.queue_step(request, return_state=return_state)
        return await future

    async def step(self, request: StepRequest, return_state: bool = True) -> dict[str, Any]:
        async with self._lock:
            started_at = perf_counter()
            request_input_source = str(request.input_source).strip() if request.input_source is not None else None
            request_raw_input = dict(request.raw_input) if isinstance(request.raw_input, dict) else None
            request_origin = _request_origin(request_raw_input)
            is_desktop_slider_request = _is_desktop_slider_input(request.source, request_input_source)
            if (
                is_desktop_slider_request
                and request_origin in {"", "mujoco_viewer"}
                and perf_counter() < self._frontend_slider_guard_until
            ):
                if return_state:
                    return self._build_state_locked(refresh_camera=False)
                return {
                    "timestamp": time.time(),
                    "sim_time": self._sim_time,
                    "source": self._source,
                    "selected_joint_group": self._last_selected_joint_group,
                    "input_source": self._last_input_source,
                    "status": "ignored_frontend_slider_guard",
                }
            if is_desktop_slider_request and request_origin in {"", "frontend"}:
                self._frontend_slider_guard_until = max(
                    self._frontend_slider_guard_until,
                    perf_counter() + FRONTEND_SLIDER_OVERWRITE_GUARD_S,
                )

            target_positions = request.target_positions

            snapshot: dict[str, Any] = {
                "arm_qpos": list(self._arm_qpos),
                "arm_qvel": list(self._arm_qvel),
                "gripper_opening": float(self._gripper_opening),
                "gripper_velocity": float(self._gripper_velocity),
                "arm_command_qpos": list(self._arm_command_qpos),
                "arm_servo_ctrl_qpos": list(self._arm_servo_ctrl_qpos),
                "arm_servo_ctrl_qvel": list(self._arm_servo_ctrl_qvel),
                "arm_servo_ctrl_qaccel": list(self._arm_servo_ctrl_qaccel),
                "gripper_command_opening": float(self._gripper_command_opening),
                "gripper_servo_ctrl_opening": float(self._gripper_servo_ctrl_opening),
                "gripper_servo_ctrl_velocity": float(self._gripper_servo_ctrl_velocity),
                "gripper_servo_ctrl_accel": float(self._gripper_servo_ctrl_accel),
                "gripper_joints": dict(self._gripper_joints),
                "attached_object_id": self._attached_object_id,
                "attached_object_rel_position": (
                    list(self._attached_object_rel_position)
                    if self._attached_object_rel_position is not None
                    else None
                ),
                "attached_object_rel_quaternion": (
                    list(self._attached_object_rel_quaternion)
                    if self._attached_object_rel_quaternion is not None
                    else None
                ),
            }
            if self._using_mujoco_model() and self._mj_data is not None:
                snapshot["mj_qpos"] = self._mj_data.qpos.copy()
                snapshot["mj_qvel"] = self._mj_data.qvel.copy()
                snapshot["mj_ctrl"] = self._mj_data.ctrl.copy()
                if self._mj_data.act is not None and len(self._mj_data.act) > 0:
                    snapshot["mj_act"] = self._mj_data.act.copy()

            self._source = request.source
            self._last_input_source = (
                request_input_source
            )
            self._last_selected_joint_group = (
                str(request.selected_joint_group).strip()
                if request.selected_joint_group is not None
                else None
            )
            self._last_raw_input = request_raw_input
            self._last_normalized_input = (
                dict(request.normalized_input) if isinstance(request.normalized_input, dict) else None
            )
            if request.source in {"manual", "desktop_manual"}:
                # Desktop/manual commands must reclaim ownership immediately,
                # otherwise stale Quest ownership can keep the frontend stuck
                # in a teleop-only state after XR exits unexpectedly.
                self._vr_state["control_owner"] = "desktop_manual"
            elif request.source == "quest3_controller":
                self._vr_state["control_owner"] = "quest3_controller"
                self._vr_state["last_quest_input_ts"] = time.time()
                self._vr_state["input_source_available"]["controller"] = True
                if self._last_selected_joint_group:
                    self._vr_state["selected_joint_group"] = self._last_selected_joint_group
            elif request.source == "quest3_hand":
                self._vr_state["control_owner"] = "quest3_hand"
                self._vr_state["last_quest_input_ts"] = time.time()
                self._vr_state["input_source_available"]["hand"] = True
                if self._last_selected_joint_group:
                    self._vr_state["selected_joint_group"] = self._last_selected_joint_group
            target_positions = self._resolve_arm_target_for_request_locked(request, target_positions)
            if target_positions is not None and len(target_positions) != len(self._arm_joint_names):
                raise ValueError(
                    f"Expected {len(self._arm_joint_names)} arm joints, got {len(target_positions)}."
                )
            requested_steps = max(1, int(request.n_steps))
            control_source = _normalize_control_source(self._source, self._last_input_source)
            if _is_realtime_source(control_source) and not _is_slider_commit_input(self._last_input_source):
                self._last_streaming_command_at = perf_counter()
            elif _is_slider_commit_input(self._last_input_source):
                self._last_streaming_command_at = None
            physics_horizon_steps = _resolve_physics_steps(
                control_source,
                requested_steps,
                self._dt,
                self._last_input_source,
            )
            if _is_slider_commit_input(self._last_input_source):
                execute_steps = min(physics_horizon_steps, SLIDER_COMMIT_MAX_BLOCKING_STEPS)
            else:
                execute_steps = (
                    min(physics_horizon_steps, INTERACTIVE_SOURCE_MAX_BLOCKING_STEPS)
                    if _is_interactive_source(control_source)
                    else physics_horizon_steps
                )
            self._apply_arm_command(target_positions, physics_horizon_steps, control_source)
            self._apply_gripper_command(request.gripper_command, physics_horizon_steps, control_source)
            self._update_grasp_assist_locked(forward=True)

            forbidden_contacts: list[dict[str, Any]] = []
            if self._using_mujoco_model() and self._mj_model is not None and self._mj_data is not None and _mujoco is not None:
                start_qpos = snapshot.get("mj_qpos")
                start_qvel = snapshot.get("mj_qvel")
                if start_qpos is not None and start_qvel is not None:
                    last_safe_qpos = start_qpos.copy()
                    last_safe_qvel = start_qvel.copy()
                    for _ in range(execute_steps):
                        self._apply_mujoco_servo_command_locked(advance_cartesian_servo=True)
                        _mujoco.mj_step(self._mj_model, self._mj_data)
                        self._update_grasp_assist_locked(forward=False)
                        forbidden_contacts = self._collect_forbidden_contacts_locked()
                        if forbidden_contacts:
                            break
                        last_safe_qpos = self._mj_data.qpos.copy()
                        last_safe_qvel = self._mj_data.qvel.copy()

                    if forbidden_contacts:
                        # Clip to the last collision-free dynamic state instead of hard rollback.
                        self._mj_data.qpos[:] = last_safe_qpos
                        self._mj_data.qvel[:] = last_safe_qvel
                        _mujoco.mj_forward(self._mj_model, self._mj_data)
                        self._sync_internal_state_from_mujoco_locked()
                        self._hold_current_pose_targets_locked()
                    else:
                        self._apply_mujoco_servo_command_locked()
                        self._sync_internal_state_from_mujoco_locked()
                        self._apply_servo_hold_locked()
                    self._update_grasp_assist_locked(forward=True)
                else:
                    forbidden_contacts = self._collect_forbidden_contacts_locked()
            else:
                forbidden_contacts = self._collect_forbidden_contacts_locked()

            if forbidden_contacts:
                self._safety_status = "collision_blocked"
                self._collision_blocked = True
                self._last_collision_contacts = deepcopy(forbidden_contacts)
                raise RuntimeError(self._format_collision_message(forbidden_contacts))

            self._safety_status = "normal"
            self._collision_blocked = False
            self._last_collision_contacts = []
            self._sim_time += execute_steps * self._dt
            self._stats["steps"] += execute_steps
            self._stats["commands"] += 1

            elapsed_ms = (perf_counter() - started_at) * 1000.0
            self._stats["last_step_ms"] = elapsed_ms
            command_count = max(1, int(self._stats["commands"]))
            old_avg = float(self._stats["avg_step_ms"])
            self._stats["avg_step_ms"] = old_avg + ((elapsed_ms - old_avg) / command_count)

            if not return_state:
                return {
                    "timestamp": time.time(),
                    "sim_time": self._sim_time,
                    "source": self._source,
                    "selected_joint_group": self._last_selected_joint_group,
                    "input_source": self._last_input_source,
                }

            refresh_camera = request.source not in {
                "manual",
                "desktop_manual",
                "quest3_controller",
                "quest3_hand",
            }
            return self._build_state_locked(refresh_camera=refresh_camera)

    async def reset(
        self,
        model_path: str | None = None,
        reload_model: bool = True,
        preserve_vr_state: bool = False,
        settle_steps: int | None = None,
        randomize_scene_objects: bool = False,
    ) -> dict[str, Any]:
        async with self._lock:
            preserved_vr_state = deepcopy(self._vr_state) if preserve_vr_state else None
            if reload_model or model_path is not None:
                self._load_model(model_path)
            self._reset_state_locked(
                settle_steps=settle_steps,
                randomize_scene_objects=randomize_scene_objects,
            )
            if isinstance(preserved_vr_state, dict):
                # 采集流程 reset 只复原机械臂/工具，不应把 Quest 沉浸式控制状态打回桌面模式。
                self._vr_state.update(preserved_vr_state)
                owner = str(self._vr_state.get("control_owner") or "").strip()
                if owner in {"quest3_controller", "quest3_hand"}:
                    self._source = owner
                    self._last_input_source = owner
                    selected_group = str(self._vr_state.get("selected_joint_group") or "").strip()
                    self._last_selected_joint_group = selected_group or self._last_selected_joint_group
            return self._build_state_locked()

    async def get_state(self, refresh_camera: bool = True) -> dict[str, Any]:
        async with self._lock:
            return self._build_state_locked(refresh_camera=refresh_camera)

    async def advance_and_get_state(
        self,
        elapsed_s: float | None = None,
        refresh_camera: bool = True,
    ) -> dict[str, Any]:
        async with self._lock:
            self._advance_passive_physics_locked(elapsed_s)
            return self._build_state_locked(refresh_camera=refresh_camera)

    async def advance_and_get_broadcast_state(
        self,
    ) -> dict[str, Any]:
        async with self._lock:
            return self._build_broadcast_state_locked()

    async def get_motion_state(self) -> dict[str, Any]:
        async with self._lock:
            return self._build_motion_state_locked()

    async def advance_passive(self, elapsed_s: float | None = None) -> int:
        async with self._lock:
            return self._advance_passive_physics_locked(elapsed_s)

    async def needs_background_physics(self) -> bool:
        async with self._lock:
            return self._has_pending_dynamics_locked()

    async def get_camera_observation(self, include_data: bool = False) -> dict[str, Any]:
        async with self._lock:
            return self._build_camera_observation_locked(include_data=include_data)

    async def get_camera_stream(self, stream_name: str, include_data: bool = False) -> dict[str, Any]:
        if stream_name not in {"rgb", "depth"}:
            raise ValueError("stream_name must be one of: rgb, depth")
        async with self._lock:
            observation = self._build_camera_observation_locked(include_data=include_data)
            stream_state = dict(observation.get(stream_name, {}))
            payload: dict[str, Any] = {
                "timestamp": time.time(),
                "frame_id": observation.get("frame_id"),
                "d405_frame_id": observation.get("d405_frame_id"),
                "camera_device": observation.get("camera_device"),
                "camera_mount_name": observation.get("camera_mount_name"),
                "camera_source_ok": observation.get("camera_source_ok", False),
                "camera_capture_ok": observation.get("camera_capture_ok", False),
                "rgb_valid": observation.get("rgb_valid", False),
                "depth_valid": observation.get("depth_valid", False),
                "stub_frame_used": observation.get("stub_frame_used", False),
                "last_error": observation.get("last_error"),
                "stream_name": stream_name,
                "stream": stream_state,
            }
            if include_data:
                stream_data_key = f"{stream_name}_data"
                payload[stream_data_key] = observation.get(stream_data_key)
            return payload

    async def start_task(self, task_name: str) -> dict[str, Any]:
        async with self._lock:
            self._source = "task"
            self._task_state = {"running": True, "name": task_name, "phase": "queued"}
            self._vr_state["control_owner"] = "task"
            return self._build_state_locked()

    async def stop_task(self) -> dict[str, Any]:
        async with self._lock:
            self._source = "manual"
            self._task_state = {"running": False, "name": None, "phase": None}
            self._vr_state["control_owner"] = "desktop_manual"
            return self._build_state_locked()

    async def set_source(self, source: str) -> dict[str, Any]:
        if source not in {"manual", "desktop_manual", "quest3_controller", "quest3_hand", "task", "policy"}:
            raise ValueError(
                "source must be one of: manual, desktop_manual, quest3_controller, quest3_hand, task, policy"
            )
        async with self._lock:
            self._source = source
            if source in {"manual", "desktop_manual"}:
                self._vr_state["control_owner"] = "desktop_manual"
            elif source == "quest3_controller":
                self._vr_state["control_owner"] = "quest3_controller"
            elif source == "quest3_hand":
                self._vr_state["control_owner"] = "quest3_hand"
            else:
                self._vr_state["control_owner"] = source
            if source in {"quest3_controller", "quest3_hand"}:
                self._vr_state["last_quest_input_ts"] = time.time()
            return self._build_state_locked()

    async def update_vr_state(self, request: VRStateUpdateRequest) -> dict[str, Any]:
        async with self._lock:
            if request.mode is not None:
                self._vr_state["mode"] = request.mode

            if request.controller_available is not None:
                self._vr_state["input_source_available"]["controller"] = bool(request.controller_available)

            if request.hand_tracking_available is not None:
                self._vr_state["input_source_available"]["hand"] = bool(request.hand_tracking_available)

            if request.selected_joint_group is not None:
                selected_joint_group = str(request.selected_joint_group)
                self._vr_state["selected_joint_group"] = selected_joint_group
                self._last_selected_joint_group = selected_joint_group

            if request.recording_ready is not None:
                self._vr_state["recording_ready"] = bool(request.recording_ready)

            if request.last_quest_input_ts is not None:
                self._vr_state["last_quest_input_ts"] = float(request.last_quest_input_ts)

            if request.active_policy_path is not None:
                self._vr_state["active_policy_path"] = str(request.active_policy_path)

            if request.error_message is not None:
                self._vr_state["error_message"] = str(request.error_message)

            if request.source is not None:
                self._last_input_source = str(request.source)

            if isinstance(request.raw_input, dict):
                self._last_raw_input = deepcopy(request.raw_input)
            elif request.source in {"manual", "desktop_manual"}:
                self._last_raw_input = None

            if isinstance(request.normalized_input, dict):
                self._last_normalized_input = deepcopy(request.normalized_input)
            elif request.source in {"manual", "desktop_manual"}:
                self._last_normalized_input = None

            if request.source is not None:
                self._source = request.source
                if request.source in {"manual", "desktop_manual"}:
                    self._vr_state["control_owner"] = "desktop_manual"
                elif request.source == "quest3_controller":
                    self._vr_state["control_owner"] = "quest3_controller"
                    self._vr_state["last_quest_input_ts"] = time.time()
                elif request.source == "quest3_hand":
                    self._vr_state["control_owner"] = "quest3_hand"
                    self._vr_state["last_quest_input_ts"] = time.time()
                else:
                    self._vr_state["control_owner"] = request.source

            return self._build_state_locked()

    def _load_scene_manifest(self) -> None:
        if not self._manifest_path.exists():
            raise FileNotFoundError(f"Scene manifest not found: {self._manifest_path}")
        raw = self._manifest_path.read_text(encoding="utf-8")
        self._manifest_data = json.loads(raw)

        robot = self._manifest_data.get("robot", {})
        home_pose = robot.get("home_pose", {})
        joint_order = home_pose.get("joint_order", DEFAULT_ARM_JOINT_NAMES)
        qpos_arm = home_pose.get("qpos_arm", DEFAULT_HOME_QPOS)

        if isinstance(joint_order, list) and len(joint_order) >= 6:
            self._arm_joint_names = [str(name) for name in joint_order[:6]]
        if isinstance(qpos_arm, list) and len(qpos_arm) >= 6:
            self._home_arm_qpos = [float(v) for v in qpos_arm[:6]]
        else:
            self._home_arm_qpos = list(DEFAULT_HOME_QPOS)

        self._scene_objects_template = {}
        self._scene_objects_manifest_template = {}
        self._object_reset_policy = {}
        for obj in self._manifest_data.get("objects", []):
            obj_id = str(obj.get("id", "")).strip()
            if not obj_id:
                continue
            transform = obj.get("transform", {})
            frontend_position = [float(v) for v in transform.get("position", [0.0, 0.0, 0.0])]
            rotation_rpy = [float(v) for v in transform.get("rotation_rpy", [0.0, 0.0, 0.0])]
            frontend_quaternion = _euler_xyz_to_quaternion(*rotation_rpy)
            backend_position = self._frontend_to_backend_position(frontend_position)
            backend_quaternion = _quaternion_multiply(BACKEND_ALIGNMENT_QUATERNION, frontend_quaternion)
            self._scene_objects_template[obj_id] = {
                "position": backend_position,
                "quaternion": backend_quaternion,
                "attached_to_gripper": False,
            }
            self._scene_objects_manifest_template[obj_id] = {
                "position": list(backend_position),
                "quaternion": list(backend_quaternion),
                "attached_to_gripper": False,
            }
            reset_policy = obj.get("reset_policy", {})
            if isinstance(reset_policy, dict):
                self._object_reset_policy[obj_id] = dict(reset_policy)
            else:
                self._object_reset_policy[obj_id] = {"mode": "fixed"}

        self._spawn_regions = {}
        for region in self._manifest_data.get("spawn_regions", []):
            self._register_spawn_region(region)
        self._load_spawn_regions_from_tool_catalog()
        self._load_camera_sensor_config()
        self._load_dataset_schema()
        self._load_handover_scene_config()

    def _register_spawn_region(self, region: Any) -> None:
        if not isinstance(region, dict):
            return
        region_id = str(region.get("id", "")).strip()
        if not region_id:
            return
        min_vec = region.get("min", [0.0, 0.0, 0.0])
        max_vec = region.get("max", [0.0, 0.0, 0.0])
        if not isinstance(min_vec, list) or not isinstance(max_vec, list):
            return
        if len(min_vec) < 3 or len(max_vec) < 3:
            return
        try:
            min_pos = [float(min_vec[0]), float(min_vec[1]), float(min_vec[2])]
            max_pos = [float(max_vec[0]), float(max_vec[1]), float(max_vec[2])]
        except (TypeError, ValueError):
            return

        frame = str(region.get("frame", "frontend")).strip().lower()
        if frame not in {"frontend", "backend"}:
            frame = "frontend"

        self._spawn_regions[region_id] = {
            "frame": frame,
            "min": min_pos,
            "max": max_pos,
        }

    def _load_spawn_regions_from_tool_catalog(self) -> None:
        catalog_path = self._resolve_repo_path(self._manifest_data.get("tool_catalog_path"))
        if catalog_path is None:
            return
        if not catalog_path.exists():
            return

        try:
            raw = catalog_path.read_text(encoding="utf-8")
            catalog_data = json.loads(raw)
        except Exception:
            return

        for region in catalog_data.get("spawn_regions", []):
            region_id = str(region.get("id", "")).strip() if isinstance(region, dict) else ""
            if region_id and region_id in self._spawn_regions:
                continue
            self._register_spawn_region(region)

    def _resolve_repo_path(self, path_value: Any) -> Path | None:
        if not isinstance(path_value, str) or not path_value.strip():
            return None
        candidate = Path(path_value).expanduser()
        if candidate.is_absolute():
            return candidate
        return (REPO_ROOT / candidate).resolve()

    def _load_camera_sensor_config(self) -> None:
        config_path = self._resolve_repo_path(self._manifest_data.get("camera_sensor_config_path"))
        if config_path is None:
            config_path = DEFAULT_CAMERA_SENSOR_CONFIG_PATH
        self._camera_sensor_config_path = str(config_path)
        if not config_path.exists():
            return

        try:
            raw = config_path.read_text(encoding="utf-8")
            config_data = json.loads(raw)
        except Exception:
            return

        primary_sensor = config_data.get("primary_sensor", {})
        if isinstance(primary_sensor, dict):
            device = str(primary_sensor.get("device", self._camera_device)).strip()
            if device:
                self._camera_device = device

            mount = primary_sensor.get("mount", {})
            if isinstance(mount, dict):
                mount_name = str(mount.get("name", self._camera_mount_name)).strip()
                if mount_name:
                    self._camera_mount_name = mount_name

                parent_frame = str(mount.get("parent_frame", self._camera_mount_parent_frame)).strip()
                if parent_frame:
                    self._camera_mount_parent_frame = parent_frame

                mount_pos_raw = mount.get("position", DEFAULT_CAMERA_MOUNT_POSITION)
                if isinstance(mount_pos_raw, list) and len(mount_pos_raw) >= 3:
                    try:
                        mount_pos = [float(mount_pos_raw[0]), float(mount_pos_raw[1]), float(mount_pos_raw[2])]
                        self._camera_pose_in_ee["position"] = mount_pos
                    except (TypeError, ValueError):
                        pass

                mount_quat_raw = mount.get("quaternion_wxyz", mount.get("quaternion", DEFAULT_CAMERA_MOUNT_QUATERNION))
                if isinstance(mount_quat_raw, list) and len(mount_quat_raw) >= 4:
                    try:
                        mount_quat = [float(mount_quat_raw[0]), float(mount_quat_raw[1]), float(mount_quat_raw[2]), float(mount_quat_raw[3])]
                        self._camera_pose_in_ee["quaternion"] = _normalize_quaternion(mount_quat)
                    except (TypeError, ValueError):
                        pass

            outputs = primary_sensor.get("outputs", {})
            if isinstance(outputs, dict):
                rgb_raw = outputs.get("rgb", {})
                if isinstance(rgb_raw, dict):
                    merged_rgb = dict(DEFAULT_RGB_STREAM)
                    for key, default_value in DEFAULT_RGB_STREAM.items():
                        merged_rgb[key] = rgb_raw.get(key, default_value)
                    try:
                        merged_rgb["width"] = max(1, int(merged_rgb["width"]))
                        merged_rgb["height"] = max(1, int(merged_rgb["height"]))
                        merged_rgb["fps"] = max(1.0, float(merged_rgb["fps"]))
                    except (TypeError, ValueError):
                        merged_rgb = dict(DEFAULT_RGB_STREAM)
                    self._rgb_stream = merged_rgb

                depth_raw = outputs.get("depth", {})
                if isinstance(depth_raw, dict):
                    merged_depth = dict(DEFAULT_DEPTH_STREAM)
                    for key, default_value in DEFAULT_DEPTH_STREAM.items():
                        merged_depth[key] = depth_raw.get(key, default_value)
                    try:
                        merged_depth["width"] = max(1, int(merged_depth["width"]))
                        merged_depth["height"] = max(1, int(merged_depth["height"]))
                        merged_depth["fps"] = max(1.0, float(merged_depth["fps"]))
                        merged_depth["depth_scale"] = float(merged_depth["depth_scale"])
                    except (TypeError, ValueError):
                        merged_depth = dict(DEFAULT_DEPTH_STREAM)
                    self._depth_stream = merged_depth

                alignment_raw = outputs.get("timestamp_alignment", {})
                if isinstance(alignment_raw, dict):
                    alignment_mode = str(alignment_raw.get("mode", self._camera_alignment_mode)).strip()
                    if alignment_mode:
                        self._camera_alignment_mode = alignment_mode
                    try:
                        self._camera_alignment_max_delta_ms = max(
                            0.0,
                            float(alignment_raw.get("max_delta_ms", self._camera_alignment_max_delta_ms)),
                        )
                    except (TypeError, ValueError):
                        pass

            recording_contract = primary_sensor.get("recording_contract", {})
            if isinstance(recording_contract, dict):
                self._camera_recordable_training_observation = bool(
                    recording_contract.get(
                        "recordable_training_observation",
                        self._camera_recordable_training_observation,
                    )
                )

            calibration_raw = primary_sensor.get("calibration", {})
            if isinstance(calibration_raw, dict):
                intrinsics_version = str(
                    calibration_raw.get("intrinsics_version", self._camera_intrinsics_version)
                ).strip()
                extrinsics_version = str(
                    calibration_raw.get("extrinsics_version", self._camera_extrinsics_version)
                ).strip()
                if intrinsics_version:
                    self._camera_intrinsics_version = intrinsics_version
                if extrinsics_version:
                    self._camera_extrinsics_version = extrinsics_version

        debug_objects_raw = config_data.get("debug_only_scene_objects", [])
        parsed_debug_objects: list[str] = []
        if isinstance(debug_objects_raw, list):
            for item in debug_objects_raw:
                if isinstance(item, str):
                    candidate = item.strip()
                elif isinstance(item, dict):
                    candidate = str(item.get("id", "")).strip()
                else:
                    candidate = ""
                if candidate:
                    parsed_debug_objects.append(candidate)
        if parsed_debug_objects:
            self._camera_debug_only_objects = parsed_debug_objects

        capture_fps = max(1.0, min(float(self._rgb_stream["fps"]), float(self._depth_stream["fps"])))
        self._camera_capture_interval_s = 1.0 / capture_fps

    def _load_dataset_schema(self) -> None:
        schema_path = self._resolve_repo_path(self._manifest_data.get("dataset_schema_path"))
        if schema_path is None:
            schema_path = DEFAULT_DATASET_SCHEMA_PATH
        self._dataset_schema_path = str(schema_path)
        self._dataset_schema = {}
        if not schema_path.exists():
            return

        try:
            raw = schema_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except Exception:
            return

        if isinstance(parsed, dict):
            self._dataset_schema = parsed

    def _load_handover_scene_config(self) -> None:
        config_path = self._resolve_repo_path(self._manifest_data.get("handover_scene_config_path"))
        if config_path is None:
            config_path = DEFAULT_HANDOVER_SCENE_CONFIG_PATH
        self._handover_scene_config_path = str(config_path)
        self._handover_zones = []
        self._camera_smoke_test_plan = {}
        if not config_path.exists():
            return

        try:
            raw = config_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
        except Exception:
            return
        if not isinstance(parsed, dict):
            return

        zones_raw = parsed.get("handover_zones", [])
        if isinstance(zones_raw, list):
            for zone_raw in zones_raw:
                zone = self._parse_handover_zone(zone_raw)
                if zone is not None:
                    self._handover_zones.append(zone)

        smoke_plan = parsed.get("camera_smoke_test", {})
        if isinstance(smoke_plan, dict):
            self._camera_smoke_test_plan = deepcopy(smoke_plan)

    def _parse_handover_zone(self, zone_raw: Any) -> dict[str, Any] | None:
        if not isinstance(zone_raw, dict):
            return None
        zone_id = str(zone_raw.get("id", "")).strip()
        if not zone_id:
            return None

        center_raw = zone_raw.get("center", zone_raw.get("position", [0.0, 0.0, 0.0]))
        size_raw = zone_raw.get("size", [0.12, 0.12, 0.12])
        if not isinstance(center_raw, list) or len(center_raw) < 3:
            return None
        if not isinstance(size_raw, list) or len(size_raw) < 3:
            return None

        try:
            center = [float(center_raw[0]), float(center_raw[1]), float(center_raw[2])]
            size = [max(0.0, float(size_raw[0])), max(0.0, float(size_raw[1])), max(0.0, float(size_raw[2]))]
        except (TypeError, ValueError):
            return None

        frame = str(zone_raw.get("frame", "backend")).strip().lower()
        if frame not in {"frontend", "backend"}:
            frame = "backend"
        backend_center = self._frontend_to_backend_position(center) if frame == "frontend" else list(center)

        return {
            "id": zone_id,
            "frame": frame,
            "center": center,
            "backend_center": backend_center,
            "size": size,
            "purpose": str(zone_raw.get("purpose", "safe_handover_reception")),
            "visible_in_d405_smoke_test": bool(zone_raw.get("visible_in_d405_smoke_test", True)),
            "notes": str(zone_raw.get("notes", "")),
        }

    def _frontend_to_backend_position(self, frontend_position: list[float]) -> list[float]:
        x_frontend, y_frontend, z_frontend = frontend_position
        return [x_frontend, -z_frontend, y_frontend + BACKEND_FRAME_Z_OFFSET]

    def _backend_to_frontend_position(self, backend_position: list[float]) -> list[float]:
        x_backend, y_backend, z_backend = backend_position
        return [x_backend, z_backend - BACKEND_FRAME_Z_OFFSET, -y_backend]

    def _resolve_model_path(self, model_path: str | None) -> Path:
        if model_path is None:
            return self._default_model_path
        requested = Path(model_path).expanduser()
        if requested.is_absolute():
            return requested
        return (REPO_ROOT / requested).resolve()

    def _set_stub_mode(self) -> None:
        self._close_mujoco_renderer()
        self._model_backend = "stub"
        self._mj_model = None
        self._mj_data = None
        self._arm_joint_qpos_addr = {}
        self._arm_joint_qvel_addr = {}
        self._arm_joint_limits = {}
        self._gripper_joint_qpos_addr = {}
        self._gripper_joint_qvel_addr = {}
        self._arm_actuator_ids = {}
        self._gripper_driver_actuator_id = None
        self._object_body_ids = {}
        self._object_freejoint_qpos_addr = {}
        self._object_freejoint_dof_addr = {}
        self._gripper_body_ids = {}
        self._tool_site_id = None
        self._tool_body_id = None
        self._mj_rgb_camera_id = -1
        self._mj_depth_camera_id = -1
        self._dt = DEFAULT_DT

    def _close_mujoco_renderer(self) -> None:
        if self._mj_renderer is None:
            return
        try:
            close_fn = getattr(self._mj_renderer, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass
        finally:
            self._mj_renderer = None
            self._mj_renderer_width = 0
            self._mj_renderer_height = 0

    def _using_mujoco_model(self) -> bool:
        return self._model_backend == "mujoco" and self._mj_model is not None and self._mj_data is not None

    def _load_model(self, model_path: str | None) -> None:
        explicit_request = model_path is not None
        resolved_path = self._resolve_model_path(model_path)
        self._loaded_model_path = str(resolved_path)
        self._model_load_error = None
        self._close_mujoco_renderer()

        if _mujoco is None:
            self._set_stub_mode()
            if explicit_request:
                raise RuntimeError("MuJoCo Python package is not available in this environment.")
            return

        if not resolved_path.exists():
            self._set_stub_mode()
            if explicit_request:
                raise FileNotFoundError(f"MuJoCo model not found: {resolved_path}")
            return

        try:
            model = _mujoco.MjModel.from_xml_path(str(resolved_path))
            data = _mujoco.MjData(model)
        except Exception as exc:
            self._set_stub_mode()
            self._model_load_error = str(exc)
            if explicit_request:
                raise RuntimeError(f"Failed to load MuJoCo model '{resolved_path}': {exc}") from exc
            return

        self._mj_model = model
        self._mj_data = data
        self._model_backend = "mujoco"
        self._dt = float(model.opt.timestep) if float(model.opt.timestep) > 0.0 else DEFAULT_DT
        self._cache_mujoco_handles()

    def _cache_mujoco_handles(self) -> None:
        if _mujoco is None or self._mj_model is None:
            return

        model = self._mj_model
        self._arm_joint_qpos_addr = {}
        self._arm_joint_qvel_addr = {}
        self._arm_joint_limits = {}
        for name in self._arm_joint_names:
            joint_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_JOINT, name)
            if joint_id >= 0:
                self._arm_joint_qpos_addr[name] = int(model.jnt_qposadr[joint_id])
                self._arm_joint_qvel_addr[name] = int(model.jnt_dofadr[joint_id])
                if bool(model.jnt_limited[joint_id]):
                    lo, hi = model.jnt_range[joint_id]
                    self._arm_joint_limits[name] = (float(lo), float(hi))

        self._gripper_joint_qpos_addr = {}
        self._gripper_joint_qvel_addr = {}
        for name in DEFAULT_GRIPPER_JOINT_NAMES:
            joint_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_JOINT, name)
            if joint_id >= 0:
                self._gripper_joint_qpos_addr[name] = int(model.jnt_qposadr[joint_id])
                self._gripper_joint_qvel_addr[name] = int(model.jnt_dofadr[joint_id])

        self._arm_actuator_ids = {}
        for actuator_name in DEFAULT_ARM_ACTUATOR_NAMES:
            actuator_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id >= 0:
                self._arm_actuator_ids[actuator_name] = int(actuator_id)

        self._gripper_driver_actuator_id = None
        gripper_actuator_id = _mujoco.mj_name2id(
            model,
            _mujoco.mjtObj.mjOBJ_ACTUATOR,
            DEFAULT_GRIPPER_ACTUATOR_NAME,
        )
        if gripper_actuator_id >= 0:
            self._gripper_driver_actuator_id = int(gripper_actuator_id)

        self._gripper_body_ids = {}
        for name in GRIPPER_GRASP_PAD_BODY_NAMES:
            body_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_BODY, name)
            if body_id >= 0:
                self._gripper_body_ids[name] = int(body_id)

        self._object_body_ids = {}
        self._object_freejoint_qpos_addr = {}
        self._object_freejoint_dof_addr = {}
        for obj_id in self._scene_objects_template:
            body_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_BODY, obj_id)
            if body_id < 0:
                self._object_body_ids[obj_id] = -1
                continue

            body_id_int = int(body_id)
            self._object_body_ids[obj_id] = body_id_int

            body_joint_count = int(model.body_jntnum[body_id_int])
            if body_joint_count <= 0:
                continue

            joint_start = int(model.body_jntadr[body_id_int])
            joint_id = int(joint_start)
            if int(model.jnt_type[joint_id]) != int(_mujoco.mjtJoint.mjJNT_FREE):
                continue

            self._object_freejoint_qpos_addr[obj_id] = int(model.jnt_qposadr[joint_id])
            self._object_freejoint_dof_addr[obj_id] = int(model.jnt_dofadr[joint_id])

        self._tool_site_id = None
        for candidate in TOOL_SITE_CANDIDATES:
            site_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_SITE, candidate)
            if site_id >= 0:
                self._tool_site_id = int(site_id)
                break

        self._tool_body_id = None
        for candidate in TOOL_BODY_CANDIDATES:
            body_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_BODY, candidate)
            if body_id >= 0:
                self._tool_body_id = int(body_id)
                break

        self._mj_rgb_camera_id = -1
        rgb_camera_name = str(self._rgb_stream.get("camera_name", DEFAULT_RGB_STREAM["camera_name"])).strip()
        if rgb_camera_name:
            rgb_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_CAMERA, rgb_camera_name)
            if rgb_id >= 0:
                self._mj_rgb_camera_id = int(rgb_id)

        self._mj_depth_camera_id = -1
        depth_camera_name = str(self._depth_stream.get("camera_name", DEFAULT_DEPTH_STREAM["camera_name"])).strip()
        if depth_camera_name:
            depth_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_CAMERA, depth_camera_name)
            if depth_id >= 0:
                self._mj_depth_camera_id = int(depth_id)

    def _is_ancestor_body_id(self, ancestor_id: int, body_id: int) -> bool:
        if self._mj_model is None or ancestor_id <= 0 or body_id <= 0:
            return False
        current = int(body_id)
        while current > 0:
            if current == int(ancestor_id):
                return True
            current = int(self._mj_model.body_parentid[current])
        return False

    def _should_ignore_contact(self, body_a: int, body_b: int) -> bool:
        if body_a <= 0 and body_b <= 0:
            return True
        if body_a == body_b:
            return True
        # Ignore parent-child/ancestor internal contacts, keep world contacts.
        if body_a > 0 and body_b > 0 and self._is_ancestor_body_id(body_a, body_b):
            return True
        if body_a > 0 and body_b > 0 and self._is_ancestor_body_id(body_b, body_a):
            return True
        return False

    def _is_allowed_physics_contact(self, body_name_a: str, body_name_b: str) -> bool:
        # Tool/table/container contacts are part of the scene dynamics. They
        # should be solved by MuJoCo and streamed to the frontend, not rejected
        # as command errors.
        if body_name_a in TOOL_BODY_NAMES or body_name_b in TOOL_BODY_NAMES:
            return True

        # Gripper internal contacts can appear near full close and are not safety-critical.
        if body_name_a in GRIPPER_BODY_NAMES and body_name_b in GRIPPER_BODY_NAMES:
            return True

        return False

    def _collect_forbidden_contacts_locked(self) -> list[dict[str, Any]]:
        if not ENABLE_HARD_COLLISION_ROLLBACK:
            return []
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None:
            return []

        assert _mujoco is not None
        contacts: list[dict[str, Any]] = []
        ncon = int(self._mj_data.ncon)
        for idx in range(ncon):
            contact = self._mj_data.contact[idx]
            dist = float(contact.dist)
            if dist >= -MAX_ALLOWED_PENETRATION_M:
                continue

            geom_a = int(contact.geom1)
            geom_b = int(contact.geom2)
            body_a = int(self._mj_model.geom_bodyid[geom_a])
            body_b = int(self._mj_model.geom_bodyid[geom_b])
            if self._should_ignore_contact(body_a, body_b):
                continue

            if body_a <= 0:
                body_name_a = "world"
            else:
                body_name_a = _mujoco.mj_id2name(self._mj_model, _mujoco.mjtObj.mjOBJ_BODY, body_a) or f"body_{body_a}"
            if body_b <= 0:
                body_name_b = "world"
            else:
                body_name_b = _mujoco.mj_id2name(self._mj_model, _mujoco.mjtObj.mjOBJ_BODY, body_b) or f"body_{body_b}"
            if self._is_allowed_physics_contact(body_name_a, body_name_b):
                continue
            contacts.append(
                {
                    "dist": dist,
                    "body_a": body_name_a,
                    "body_b": body_name_b,
                }
            )

        contacts.sort(key=lambda item: float(item["dist"]))
        return contacts

    def _restore_previous_pose_locked(self, snapshot: dict[str, Any]) -> None:
        self._arm_qpos = list(snapshot.get("arm_qpos", self._arm_qpos))
        self._arm_qvel = list(snapshot.get("arm_qvel", self._arm_qvel))
        self._gripper_opening = float(snapshot.get("gripper_opening", self._gripper_opening))
        self._gripper_velocity = float(snapshot.get("gripper_velocity", self._gripper_velocity))
        restored_arm_command_qpos = snapshot.get("arm_command_qpos")
        self._arm_command_qpos = (
            [float(v) for v in restored_arm_command_qpos[: len(self._arm_joint_names)]]
            if isinstance(restored_arm_command_qpos, list) and len(restored_arm_command_qpos) >= len(self._arm_joint_names)
            else list(self._arm_qpos)
        )
        restored_servo_qpos = snapshot.get("arm_servo_ctrl_qpos")
        self._arm_servo_ctrl_qpos = (
            [float(v) for v in restored_servo_qpos[: len(self._arm_joint_names)]]
            if isinstance(restored_servo_qpos, list) and len(restored_servo_qpos) >= len(self._arm_joint_names)
            else list(self._arm_command_qpos)
        )
        restored_servo_qvel = snapshot.get("arm_servo_ctrl_qvel")
        self._arm_servo_ctrl_qvel = (
            [float(v) for v in restored_servo_qvel[: len(self._arm_joint_names)]]
            if isinstance(restored_servo_qvel, list) and len(restored_servo_qvel) >= len(self._arm_joint_names)
            else [0.0 for _ in self._arm_joint_names]
        )
        restored_servo_qaccel = snapshot.get("arm_servo_ctrl_qaccel")
        self._arm_servo_ctrl_qaccel = (
            [float(v) for v in restored_servo_qaccel[: len(self._arm_joint_names)]]
            if isinstance(restored_servo_qaccel, list) and len(restored_servo_qaccel) >= len(self._arm_joint_names)
            else [0.0 for _ in self._arm_joint_names]
        )
        self._gripper_command_opening = float(
            snapshot.get("gripper_command_opening", self._gripper_opening)
        )
        self._gripper_servo_ctrl_opening = float(
            snapshot.get("gripper_servo_ctrl_opening", self._gripper_command_opening)
        )
        self._gripper_servo_ctrl_velocity = float(
            snapshot.get("gripper_servo_ctrl_velocity", 0.0)
        )
        self._gripper_servo_ctrl_accel = float(
            snapshot.get("gripper_servo_ctrl_accel", 0.0)
        )
        self._gripper_joints = dict(snapshot.get("gripper_joints", self._gripper_joints))
        restored_attached_id = snapshot.get("attached_object_id")
        self._attached_object_id = str(restored_attached_id) if restored_attached_id else None
        restored_rel_position = snapshot.get("attached_object_rel_position")
        self._attached_object_rel_position = (
            [float(v) for v in restored_rel_position[:3]]
            if isinstance(restored_rel_position, list) and len(restored_rel_position) >= 3
            else None
        )
        restored_rel_quaternion = snapshot.get("attached_object_rel_quaternion")
        self._attached_object_rel_quaternion = (
            _normalize_quaternion(restored_rel_quaternion)
            if isinstance(restored_rel_quaternion, list) and len(restored_rel_quaternion) >= 4
            else None
        )
        if not _is_grasp_assist_enabled():
            self._clear_grasp_attachment_locked()

        if not self._using_mujoco_model() or self._mj_data is None or _mujoco is None or self._mj_model is None:
            return

        qpos_snapshot = snapshot.get("mj_qpos")
        qvel_snapshot = snapshot.get("mj_qvel")
        ctrl_snapshot = snapshot.get("mj_ctrl")
        act_snapshot = snapshot.get("mj_act")
        if qpos_snapshot is not None:
            self._mj_data.qpos[:] = qpos_snapshot
        if qvel_snapshot is not None:
            self._mj_data.qvel[:] = qvel_snapshot
        if ctrl_snapshot is not None:
            self._mj_data.ctrl[:] = ctrl_snapshot
        if act_snapshot is not None and self._mj_data.act is not None and len(self._mj_data.act) == len(act_snapshot):
            self._mj_data.act[:] = act_snapshot
        _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _sync_internal_state_from_mujoco_locked(self) -> None:
        if not self._using_mujoco_model() or self._mj_data is None:
            return

        arm_qpos: list[float] = []
        arm_qvel: list[float] = []
        for name in self._arm_joint_names:
            qpos_addr = self._arm_joint_qpos_addr.get(name)
            qvel_addr = self._arm_joint_qvel_addr.get(name)
            if qpos_addr is None:
                arm_qpos.append(0.0)
            else:
                arm_qpos.append(float(self._mj_data.qpos[qpos_addr]))
            if qvel_addr is None:
                arm_qvel.append(0.0)
            else:
                arm_qvel.append(float(self._mj_data.qvel[qvel_addr]))
        self._arm_qpos = arm_qpos
        self._arm_qvel = arm_qvel

        gripper_joints: dict[str, float] = {}
        for name in DEFAULT_GRIPPER_JOINT_NAMES:
            qpos_addr = self._gripper_joint_qpos_addr.get(name)
            if qpos_addr is None:
                continue
            gripper_joints[name] = float(self._mj_data.qpos[qpos_addr])

        left_driver = gripper_joints.get("left_driver_joint", 0.0)
        self._gripper_opening = _clamp(left_driver / GRIPPER_DRIVER_LIMIT, 0.0, 1.0)
        left_driver_qvel_addr = self._gripper_joint_qvel_addr.get("left_driver_joint")
        if left_driver_qvel_addr is not None:
            self._gripper_velocity = float(self._mj_data.qvel[left_driver_qvel_addr]) / max(GRIPPER_DRIVER_LIMIT, 1e-8)
        else:
            self._gripper_velocity = 0.0
        default_mapping = self._map_gripper_joints(self._gripper_opening)
        for name, value in default_mapping.items():
            gripper_joints.setdefault(name, float(value))
        self._gripper_joints = gripper_joints

    def _set_mujoco_gripper_joint_state_locked(
        self,
        opening: float,
        opening_velocity: float = 0.0,
        forward: bool = False,
    ) -> None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None:
            return

        targets = self._map_gripper_joints(opening)
        joint_velocity = float(opening_velocity) * GRIPPER_DRIVER_LIMIT
        for joint_name, target in targets.items():
            qpos_addr = self._gripper_joint_qpos_addr.get(joint_name)
            if qpos_addr is not None:
                self._mj_data.qpos[qpos_addr] = float(target)
            qvel_addr = self._gripper_joint_qvel_addr.get(joint_name)
            if qvel_addr is not None:
                self._mj_data.qvel[qvel_addr] = joint_velocity

        if self._gripper_driver_actuator_id is not None:
            self._mj_data.ctrl[self._gripper_driver_actuator_id] = float(targets["left_driver_joint"])
            self._set_mujoco_actuator_activation_locked(
                self._gripper_driver_actuator_id,
                float(targets["left_driver_joint"]),
            )
        self._gripper_servo_ctrl_opening = _clamp(float(opening), 0.0, 1.0)
        self._gripper_servo_ctrl_velocity = float(opening_velocity)
        self._gripper_servo_ctrl_accel = 0.0

        if forward and _mujoco is not None:
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _set_mujoco_gripper_target_locked(self, opening: float) -> None:
        if not self._using_mujoco_model() or self._mj_data is None:
            return

        if self._gripper_driver_actuator_id is None:
            self._set_mujoco_gripper_joint_state_locked(opening, forward=False)
            return

        # Drive the gripper through its actuator instead of teleporting each
        # finger joint every substep; this keeps contacts and grasp motion smooth.
        targets = self._map_gripper_joints(opening)
        self._mj_data.ctrl[self._gripper_driver_actuator_id] = float(targets["left_driver_joint"])
        self._gripper_servo_ctrl_opening = _clamp(float(opening), 0.0, 1.0)
        self._gripper_servo_ctrl_velocity = 0.0
        self._gripper_servo_ctrl_accel = 0.0

    def _apply_mujoco_servo_command_locked(
        self,
        immediate: bool = False,
        advance_cartesian_servo: bool = False,
    ) -> None:
        if not self._using_mujoco_model() or self._mj_data is None:
            return

        dt = max(self._dt, 1e-6)
        arm_count = len(self._arm_joint_names)
        if len(self._arm_servo_ctrl_qpos) < arm_count:
            self._arm_servo_ctrl_qpos = list(self._read_current_arm_qpos_locked())
        if len(self._arm_servo_ctrl_qvel) < arm_count:
            self._arm_servo_ctrl_qvel = [0.0 for _ in range(arm_count)]
        if len(self._arm_servo_ctrl_qaccel) < arm_count:
            self._arm_servo_ctrl_qaccel = [0.0 for _ in range(arm_count)]

        if advance_cartesian_servo and not immediate:
            self._update_cartesian_servo_arm_command_locked(dt)

        limits = _resolve_servo_motion_limits(self._source, self._last_input_source)
        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            actuator_id = self._arm_actuator_ids.get(actuator_name)
            if actuator_id is None or idx >= len(self._arm_command_qpos):
                continue
            target = float(self._arm_command_qpos[idx])
            current = float(self._mj_data.ctrl[actuator_id])
            if immediate:
                next_ctrl = target
                next_velocity = 0.0
                next_acceleration = 0.0
            else:
                next_ctrl, next_velocity, next_acceleration = _advance_smooth_servo_target(
                    current=current,
                    target=target,
                    velocity=self._arm_servo_ctrl_qvel[idx],
                    acceleration=self._arm_servo_ctrl_qaccel[idx],
                    dt=dt,
                    max_speed=limits["arm_speed"],
                    max_accel=limits["arm_accel"],
                    max_jerk=limits["arm_jerk"],
                )
            self._mj_data.ctrl[actuator_id] = float(next_ctrl)
            self._arm_servo_ctrl_qpos[idx] = float(next_ctrl)
            self._arm_servo_ctrl_qvel[idx] = float(next_velocity)
            self._arm_servo_ctrl_qaccel[idx] = float(next_acceleration)

        if self._gripper_driver_actuator_id is None:
            return
        gripper_target_opening = _clamp(float(self._gripper_command_opening), 0.0, 1.0)
        current_driver = float(self._mj_data.ctrl[self._gripper_driver_actuator_id])
        current_opening = _clamp(current_driver / GRIPPER_DRIVER_LIMIT, 0.0, 1.0)
        if immediate:
            next_opening = gripper_target_opening
            next_velocity = 0.0
            next_acceleration = 0.0
        else:
            next_opening, next_velocity, next_acceleration = _advance_smooth_servo_target(
                current=current_opening,
                target=gripper_target_opening,
                velocity=self._gripper_servo_ctrl_velocity,
                acceleration=self._gripper_servo_ctrl_accel,
                dt=dt,
                max_speed=limits["gripper_speed"],
                max_accel=limits["gripper_accel"],
                max_jerk=limits["gripper_jerk"],
            )
        self._gripper_servo_ctrl_opening = float(next_opening)
        self._gripper_servo_ctrl_velocity = float(next_velocity)
        self._gripper_servo_ctrl_accel = float(next_acceleration)
        self._mj_data.ctrl[self._gripper_driver_actuator_id] = float(next_opening) * GRIPPER_DRIVER_LIMIT

    def _read_current_gripper_opening_locked(self) -> float:
        if self._using_mujoco_model() and self._mj_data is not None:
            driver_addr = self._gripper_joint_qpos_addr.get("left_driver_joint")
            if driver_addr is not None:
                return _clamp(float(self._mj_data.qpos[driver_addr]) / GRIPPER_DRIVER_LIMIT, 0.0, 1.0)
        return _clamp(float(self._gripper_opening), 0.0, 1.0)

    def _read_current_ctrl_targets_locked(self) -> tuple[list[float], float]:
        arm = list(self._arm_command_qpos)
        gripper = float(self._gripper_command_opening)
        if not self._using_mujoco_model() or self._mj_data is None:
            return arm, gripper

        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            actuator_id = self._arm_actuator_ids.get(actuator_name)
            if actuator_id is not None and idx < len(arm):
                arm[idx] = float(self._mj_data.ctrl[actuator_id])
        if self._gripper_driver_actuator_id is not None:
            gripper = _clamp(
                float(self._mj_data.ctrl[self._gripper_driver_actuator_id]) / GRIPPER_DRIVER_LIMIT,
                0.0,
                1.0,
            )
        return arm, gripper

    def _hold_current_pose_targets_locked(self) -> None:
        self._clear_cartesian_servo_target_locked()
        current_arm = self._read_current_arm_qpos_locked()
        self._arm_command_qpos = list(current_arm)
        self._arm_servo_ctrl_qpos = list(current_arm)
        self._arm_servo_ctrl_qvel = [0.0 for _ in current_arm]
        self._arm_servo_ctrl_qaccel = [0.0 for _ in current_arm]
        self._gripper_command_opening = self._read_current_gripper_opening_locked()
        self._gripper_servo_ctrl_opening = float(self._gripper_command_opening)
        self._gripper_servo_ctrl_velocity = 0.0
        self._gripper_servo_ctrl_accel = 0.0

        if not self._using_mujoco_model() or self._mj_data is None:
            self._arm_qpos = list(current_arm)
            self._gripper_opening = self._gripper_command_opening
            self._gripper_joints = self._map_gripper_joints(self._gripper_opening)
            return

        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            actuator_id = self._arm_actuator_ids.get(actuator_name)
            if actuator_id is None or idx >= len(self._arm_command_qpos):
                continue
            self._mj_data.ctrl[actuator_id] = float(self._arm_command_qpos[idx])
            self._set_mujoco_actuator_activation_locked(actuator_id, float(self._arm_command_qpos[idx]))
        self._zero_controlled_joint_velocities_locked()
        self._set_mujoco_gripper_target_locked(self._gripper_command_opening)

    def _format_collision_message(self, contacts: list[dict[str, Any]]) -> str:
        if not contacts:
            return "step blocked to avoid collision."

        top_contacts = contacts[:MAX_COLLISION_REPORTS]
        parts = []
        for item in top_contacts:
            depth_mm = abs(float(item["dist"])) * 1000.0
            parts.append(f'{item["body_a"]}<->{item["body_b"]} ({depth_mm:.1f}mm)')
        return "step blocked: collision/interference detected at " + ", ".join(parts)

    def _set_object_pose_locked(
        self,
        obj_id: str,
        position: list[float],
        quaternion: list[float],
        reset_velocity: bool = False,
    ) -> bool:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None:
            return False

        freejoint_qpos_addr = self._object_freejoint_qpos_addr.get(obj_id)
        if freejoint_qpos_addr is not None:
            self._mj_data.qpos[freejoint_qpos_addr : freejoint_qpos_addr + 3] = [
                float(position[0]),
                float(position[1]),
                float(position[2]),
            ]
            normalized_quat = _normalize_quaternion(quaternion)
            self._mj_data.qpos[freejoint_qpos_addr + 3 : freejoint_qpos_addr + 7] = [
                float(normalized_quat[0]),
                float(normalized_quat[1]),
                float(normalized_quat[2]),
                float(normalized_quat[3]),
            ]

            if reset_velocity:
                freejoint_dof_addr = self._object_freejoint_dof_addr.get(obj_id)
                if freejoint_dof_addr is not None:
                    self._mj_data.qvel[freejoint_dof_addr : freejoint_dof_addr + 6] = 0.0
            return True

        body_id = self._object_body_ids.get(obj_id, -1)
        if body_id < 0:
            return False

        self._mj_model.body_pos[body_id] = [float(position[0]), float(position[1]), float(position[2])]
        normalized_quat = _normalize_quaternion(quaternion)
        self._mj_model.body_quat[body_id] = [
            float(normalized_quat[0]),
            float(normalized_quat[1]),
            float(normalized_quat[2]),
            float(normalized_quat[3]),
        ]
        return True

    def _get_object_pose_locked(self, obj_id: str) -> dict[str, list[float]] | None:
        if self._using_mujoco_model() and self._mj_data is not None:
            body_id = self._object_body_ids.get(obj_id, -1)
            if body_id >= 0:
                return {
                    "position": [float(v) for v in self._mj_data.xpos[body_id]],
                    "quaternion": [float(v) for v in self._mj_data.xquat[body_id]],
                }

        state = self._objects_state.get(obj_id) or self._scene_objects_template.get(obj_id)
        if not isinstance(state, dict):
            return None
        position = state.get("position")
        quaternion = state.get("quaternion")
        if not isinstance(position, list) or len(position) < 3:
            return None
        if not isinstance(quaternion, list) or len(quaternion) < 4:
            return None
        return {
            "position": [float(v) for v in position[:3]],
            "quaternion": _normalize_quaternion(quaternion),
        }

    def _compute_gripper_grasp_pose_locked(self) -> dict[str, list[float]]:
        pose = self._compute_control_ee_pose_locked()
        if pose is not None:
            return pose

        return self._compute_ee_pose_locked()

    def _compute_tool_frame_pose_locked(self) -> dict[str, list[float]] | None:
        if self._using_mujoco_model() and self._mj_data is not None:
            if self._tool_site_id is not None:
                return {
                    "position": [float(v) for v in self._mj_data.site_xpos[self._tool_site_id]],
                    "quaternion": _matrix_to_quaternion_wxyz(self._mj_data.site_xmat[self._tool_site_id]),
                }
            if self._tool_body_id is not None:
                return {
                    "position": [float(v) for v in self._mj_data.xpos[self._tool_body_id]],
                    "quaternion": [float(v) for v in self._mj_data.xquat[self._tool_body_id]],
                }
        return None

    def _compute_control_ee_pose_locked(self) -> dict[str, list[float]] | None:
        if self._using_mujoco_model() and self._mj_data is not None:
            tool_frame_pose = self._compute_tool_frame_pose_locked()
            orientation_quaternion: list[float] | None = (
                _normalize_quaternion(tool_frame_pose["quaternion"])
                if tool_frame_pose is not None
                else None
            )

            pad_positions: list[list[float]] = []
            for name in GRIPPER_GRASP_PAD_BODY_NAMES:
                body_id = self._gripper_body_ids.get(name)
                if body_id is not None:
                    pad_positions.append([float(v) for v in self._mj_data.xpos[body_id]])

            if pad_positions:
                inv_count = 1.0 / len(pad_positions)
                # Drive teleop/IK from the actual pinch center between the two
                # pads so "reach the tool and grasp it" lines up with what the
                # user sees, rather than with the wrist flange origin.
                position = [
                    sum(pad_position[axis] for pad_position in pad_positions) * inv_count
                    for axis in range(3)
                ]
                if orientation_quaternion is None:
                    first_pad_id = self._gripper_body_ids.get(GRIPPER_GRASP_PAD_BODY_NAMES[0])
                    orientation_quaternion = (
                        [float(v) for v in self._mj_data.xquat[first_pad_id]]
                        if first_pad_id is not None
                        else [1.0, 0.0, 0.0, 0.0]
                    )
                return {
                    "position": position,
                    "quaternion": _normalize_quaternion(orientation_quaternion),
                }

            if tool_frame_pose is not None:
                return tool_frame_pose

        return None

    def _compute_control_ee_jacobian_locked(self) -> tuple[Any, Any] | None:
        if (
            not self._using_mujoco_model()
            or self._mj_model is None
            or self._mj_data is None
            or _mujoco is None
            or np is None
        ):
            return None

        jacp = np.zeros((3, self._mj_model.nv), dtype=float)
        jacr = np.zeros((3, self._mj_model.nv), dtype=float)
        pad_body_ids = [
            int(body_id)
            for body_id in (
                self._gripper_body_ids.get(name)
                for name in GRIPPER_GRASP_PAD_BODY_NAMES
            )
            if body_id is not None
        ]

        if pad_body_ids:
            pad_jacp = np.zeros((3, self._mj_model.nv), dtype=float)
            pad_jacr = np.zeros((3, self._mj_model.nv), dtype=float)
            for body_id in pad_body_ids:
                pad_jacp.fill(0.0)
                pad_jacr.fill(0.0)
                _mujoco.mj_jacBody(self._mj_model, self._mj_data, pad_jacp, pad_jacr, body_id)
                jacp += pad_jacp
            jacp /= float(len(pad_body_ids))
        elif self._tool_site_id is not None:
            _mujoco.mj_jacSite(self._mj_model, self._mj_data, jacp, jacr, int(self._tool_site_id))
        elif self._tool_body_id is not None:
            _mujoco.mj_jacBody(self._mj_model, self._mj_data, jacp, jacr, int(self._tool_body_id))
        else:
            return None

        if self._tool_site_id is not None:
            orientation_jacp = np.zeros((3, self._mj_model.nv), dtype=float)
            _mujoco.mj_jacSite(
                self._mj_model,
                self._mj_data,
                orientation_jacp,
                jacr,
                int(self._tool_site_id),
            )
        elif self._tool_body_id is not None:
            orientation_jacp = np.zeros((3, self._mj_model.nv), dtype=float)
            _mujoco.mj_jacBody(
                self._mj_model,
                self._mj_data,
                orientation_jacp,
                jacr,
                int(self._tool_body_id),
            )

        return jacp, jacr

    def _clear_grasp_attachment_locked(self) -> None:
        for template_state in self._scene_objects_template.values():
            if isinstance(template_state, dict):
                template_state["attached_to_gripper"] = False
        self._attached_object_id = None
        self._attached_object_rel_position = None
        self._attached_object_rel_quaternion = None

    def _allows_grasp_assist_locked(self) -> bool:
        if not _is_grasp_assist_enabled():
            return False
        normalized_source = _normalize_control_source(self._source, self._last_input_source)
        return normalized_source not in {"quest3_controller", "quest3_hand"}

    def _find_contacted_graspable_object_locked(self) -> str | None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None or _mujoco is None:
            return None

        contacts_by_object: dict[str, set[str]] = {}
        for idx in range(int(self._mj_data.ncon)):
            contact = self._mj_data.contact[idx]
            if float(contact.dist) > GRIPPER_GRASP_CONTACT_MARGIN_M:
                continue

            geom_a = int(contact.geom1)
            geom_b = int(contact.geom2)
            body_a = int(self._mj_model.geom_bodyid[geom_a])
            body_b = int(self._mj_model.geom_bodyid[geom_b])
            body_name_a = (
                _mujoco.mj_id2name(self._mj_model, _mujoco.mjtObj.mjOBJ_BODY, body_a)
                if body_a > 0
                else ""
            )
            body_name_b = (
                _mujoco.mj_id2name(self._mj_model, _mujoco.mjtObj.mjOBJ_BODY, body_b)
                if body_b > 0
                else ""
            )

            if body_name_a in GRASPABLE_TOOL_BODY_NAMES and body_name_b in GRIPPER_GRASP_PAD_BODY_NAMES:
                contacts_by_object.setdefault(body_name_a, set()).add(body_name_b)
            if body_name_b in GRASPABLE_TOOL_BODY_NAMES and body_name_a in GRIPPER_GRASP_PAD_BODY_NAMES:
                contacts_by_object.setdefault(body_name_b, set()).add(body_name_a)

        if not contacts_by_object:
            return None

        if not _grasp_assist_requires_both_pads():
            return next(iter(contacts_by_object))

        required_pads = set(GRIPPER_GRASP_PAD_BODY_NAMES)
        for obj_id, pad_names in contacts_by_object.items():
            if required_pads.issubset(pad_names):
                return obj_id

        return None

    def _attach_object_to_gripper_locked(
        self,
        obj_id: str,
        grasp_pose: dict[str, list[float]],
    ) -> bool:
        object_pose = self._get_object_pose_locked(obj_id)
        if object_pose is None:
            return False

        grasp_position = grasp_pose["position"]
        grasp_quaternion = _normalize_quaternion(grasp_pose["quaternion"])
        object_position = object_pose["position"]
        object_quaternion = _normalize_quaternion(object_pose["quaternion"])
        inverse_grasp_quaternion = _quaternion_conjugate(grasp_quaternion)
        relative_position_world = [
            object_position[axis] - grasp_position[axis]
            for axis in range(3)
        ]

        self._attached_object_id = obj_id
        self._attached_object_rel_position = _rotate_vector_by_quaternion(
            relative_position_world,
            inverse_grasp_quaternion,
        )
        self._attached_object_rel_quaternion = _normalize_quaternion(
            _quaternion_multiply(inverse_grasp_quaternion, object_quaternion)
        )
        if obj_id in self._scene_objects_template:
            self._scene_objects_template[obj_id]["attached_to_gripper"] = True
        return True

    def _follow_attached_object_locked(self, forward: bool = True) -> None:
        obj_id = self._attached_object_id
        if (
            not obj_id
            or self._attached_object_rel_position is None
            or self._attached_object_rel_quaternion is None
        ):
            return

        grasp_pose = self._compute_gripper_grasp_pose_locked()
        object_pose = _compose_pose(
            grasp_pose["position"],
            grasp_pose["quaternion"],
            self._attached_object_rel_position,
            self._attached_object_rel_quaternion,
        )
        if not self._set_object_pose_locked(
            obj_id,
            object_pose["position"],
            object_pose["quaternion"],
            reset_velocity=True,
        ):
            self._clear_grasp_attachment_locked()
            return

        if obj_id in self._scene_objects_template:
            self._scene_objects_template[obj_id]["attached_to_gripper"] = True
        if (
            forward
            and self._using_mujoco_model()
            and _mujoco is not None
            and self._mj_model is not None
            and self._mj_data is not None
        ):
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _update_grasp_assist_locked(self, forward: bool = True) -> None:
        if not self._allows_grasp_assist_locked():
            self._clear_grasp_attachment_locked()
            return

        if self._gripper_opening <= GRIPPER_GRASP_RELEASE_OPENING:
            self._clear_grasp_attachment_locked()
            return

        if self._attached_object_id is not None:
            self._follow_attached_object_locked(forward=forward)
            return

        if self._gripper_opening < GRIPPER_GRASP_ENGAGE_OPENING:
            return

        grasp_pose = self._compute_gripper_grasp_pose_locked()
        graspable_id = self._find_contacted_graspable_object_locked()
        if graspable_id is None:
            return
        if self._attach_object_to_gripper_locked(graspable_id, grasp_pose):
            self._follow_attached_object_locked(forward=forward)

    def _sync_scene_objects_to_model_locked(self) -> None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None:
            return

        scene_changed = False
        for obj_id, template_state in self._scene_objects_template.items():
            body_id = self._object_body_ids.get(obj_id, -1)
            if body_id < 0:
                continue

            position = template_state.get("position", [0.0, 0.0, 0.0])
            quaternion = template_state.get("quaternion", [1.0, 0.0, 0.0, 0.0])

            if (
                isinstance(position, list)
                and len(position) >= 3
                and isinstance(quaternion, list)
                and len(quaternion) >= 4
            ):
                if self._set_object_pose_locked(obj_id, position, quaternion, reset_velocity=True):
                    scene_changed = True

            template_state["attached_to_gripper"] = False

        if scene_changed and _mujoco is not None:
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _restore_manifest_scene_objects_locked(self) -> None:
        self._scene_objects_template = deepcopy(self._scene_objects_manifest_template)

    def _reset_state_locked(
        self,
        settle_steps: int | None = None,
        randomize_scene_objects: bool = False,
    ) -> None:
        self._arm_qpos = list(self._home_arm_qpos)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._arm_command_qpos = list(self._home_arm_qpos)
        self._arm_servo_ctrl_qpos = list(self._home_arm_qpos)
        self._arm_servo_ctrl_qvel = [0.0 for _ in self._arm_servo_ctrl_qpos]
        self._arm_servo_ctrl_qaccel = [0.0 for _ in self._arm_servo_ctrl_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
        self._gripper_command_opening = 0.0
        self._gripper_servo_ctrl_opening = 0.0
        self._gripper_servo_ctrl_velocity = 0.0
        self._gripper_servo_ctrl_accel = 0.0
        self._gripper_joints = self._map_gripper_joints(self._gripper_opening)
        self._attached_object_id = None
        self._attached_object_rel_position = None
        self._attached_object_rel_quaternion = None

        if self._using_mujoco_model():
            assert _mujoco is not None
            assert self._mj_model is not None
            assert self._mj_data is not None
            self._mj_data.qpos[:] = 0.0
            self._mj_data.qvel[:] = 0.0
            for idx, name in enumerate(self._arm_joint_names):
                qpos_addr = self._arm_joint_qpos_addr.get(name)
                if qpos_addr is not None:
                    self._mj_data.qpos[qpos_addr] = float(self._home_arm_qpos[idx])
            for name, value in self._gripper_joints.items():
                qpos_addr = self._gripper_joint_qpos_addr.get(name)
                if qpos_addr is not None:
                    self._mj_data.qpos[qpos_addr] = float(value)
            for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
                actuator_id = self._arm_actuator_ids.get(actuator_name)
                if actuator_id is None:
                    continue
                if idx < len(self._home_arm_qpos):
                    self._mj_data.ctrl[actuator_id] = float(self._home_arm_qpos[idx])
                    self._set_mujoco_actuator_activation_locked(actuator_id, float(self._home_arm_qpos[idx]))
            if self._gripper_driver_actuator_id is not None:
                self._mj_data.ctrl[self._gripper_driver_actuator_id] = float(
                    self._gripper_joints.get("left_driver_joint", 0.0)
                )
                self._set_mujoco_actuator_activation_locked(
                    self._gripper_driver_actuator_id,
                    float(self._gripper_joints.get("left_driver_joint", 0.0)),
                )
            self._set_mujoco_gripper_joint_state_locked(
                self._gripper_opening,
                self._gripper_velocity,
                forward=True,
            )
            _mujoco.mj_forward(self._mj_model, self._mj_data)

        # 先回到 manifest 定义的固定初始位置，再按调用方要求随机化工具。
        self._restore_manifest_scene_objects_locked()
        self._sync_scene_objects_to_model_locked()
        if randomize_scene_objects:
            self._apply_object_reset_policy_locked()
        settle_locked_objects = self._get_scene_object_ids_to_lock_during_settle(randomize_scene_objects)
        self._settle_scene_locked(
            settle_steps=settle_steps,
            locked_scene_object_ids=settle_locked_objects,
        )
        self._hold_current_pose_targets_locked()
        self._objects_state = self._collect_objects_state_locked()
        self._source = "manual"
        self._task_state = {"running": False, "name": None, "phase": None}
        self._vr_state = {
            "mode": "vr_disabled",
            "input_source_available": {
                "controller": False,
                "hand": False,
            },
            "selected_joint_group": "arm_full",
            "control_owner": "desktop_manual",
            "recording_ready": False,
            "last_quest_input_ts": None,
            "active_policy_path": None,
            "error_message": None,
        }
        self._last_input_source = None
        self._last_selected_joint_group = None
        self._last_raw_input = None
        self._last_normalized_input = None
        self._safety_status = "normal"
        self._collision_blocked = False
        self._last_collision_contacts = []
        self._latest_realtime_seq_by_source = {}
        self._realtime_ee_target_by_source = {}
        self._last_streaming_command_at = None
        self._frontend_slider_guard_until = 0.0
        self._sim_time = 0.0
        self._stats["steps"] = 0
        self._stats["commands"] = 0
        self._stats["last_step_ms"] = 0.0
        self._stats["avg_step_ms"] = 0.0
        self._stats["camera_frames"] = 0
        self._stats["camera_drops"] = 0
        self._camera_frame_counter = 0
        self._camera_last_capture_ts = 0.0
        self._camera_last_state = None
        self._camera_last_rgb_frame = None
        self._camera_last_depth_frame = None

    def _set_mujoco_actuator_activation_locked(self, actuator_id: int, target: float) -> None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None:
            return
        if self._mj_data.act is None or len(self._mj_data.act) <= 0:
            return
        act_addr = int(self._mj_model.actuator_actadr[int(actuator_id)])
        if act_addr < 0 or act_addr >= len(self._mj_data.act):
            return
        self._mj_data.act[act_addr] = float(target)

    def _get_scene_object_ids_to_lock_during_settle(self, randomize_scene_objects: bool) -> set[str]:
        if not randomize_scene_objects:
            return set(self._scene_objects_template.keys())

        locked_object_ids: set[str] = set()
        for obj_id, policy in self._object_reset_policy.items():
            mode = str(policy.get("mode", "fixed")).strip().lower()
            if mode == "fixed":
                locked_object_ids.add(obj_id)
        return locked_object_ids

    def _settle_scene_locked(
        self,
        settle_steps: int | None = None,
        locked_scene_object_ids: set[str] | None = None,
    ) -> None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None or _mujoco is None:
            return

        preserved_qpos: list[tuple[int, float]] = []
        preserved_qvel: list[int] = []
        for joint_name in [*self._arm_joint_names, *DEFAULT_GRIPPER_JOINT_NAMES]:
            qpos_addr = self._arm_joint_qpos_addr.get(joint_name)
            if qpos_addr is None:
                qpos_addr = self._gripper_joint_qpos_addr.get(joint_name)
            if qpos_addr is None:
                continue
            preserved_qpos.append((int(qpos_addr), float(self._mj_data.qpos[int(qpos_addr)])))

            qvel_addr = self._arm_joint_qvel_addr.get(joint_name)
            if qvel_addr is None:
                qvel_addr = self._gripper_joint_qvel_addr.get(joint_name)
            if qvel_addr is not None:
                preserved_qvel.append(int(qvel_addr))

        preserved_object_qpos: list[tuple[int, list[float]]] = []
        preserved_object_qvel: list[int] = []
        for obj_id in locked_scene_object_ids or set():
            qpos_addr = self._object_freejoint_qpos_addr.get(obj_id)
            if qpos_addr is None:
                continue
            qpos_addr_int = int(qpos_addr)
            preserved_object_qpos.append(
                (qpos_addr_int, [float(value) for value in self._mj_data.qpos[qpos_addr_int : qpos_addr_int + 7]])
            )
            qvel_addr = self._object_freejoint_dof_addr.get(obj_id)
            if qvel_addr is not None:
                preserved_object_qvel.append(int(qvel_addr))

        def restore_locked_scene_objects() -> None:
            # 固定对象在 settle 期间保持 manifest/采集锚点位姿，避免工具箱被碰撞或重力带偏。
            for qpos_addr, values in preserved_object_qpos:
                self._mj_data.qpos[qpos_addr : qpos_addr + 7] = values
            for qvel_addr in preserved_object_qvel:
                self._mj_data.qvel[qvel_addr : qvel_addr + 6] = [0.0] * 6

        ctrl_snapshot = self._mj_data.ctrl.copy() if self._mj_data.ctrl is not None and len(self._mj_data.ctrl) > 0 else None
        step_count = SCENE_SETTLE_STEPS if settle_steps is None else int(settle_steps)
        for _ in range(max(0, step_count)):
            _mujoco.mj_step(self._mj_model, self._mj_data)
            restore_locked_scene_objects()
            for qpos_addr, qpos_value in preserved_qpos:
                self._mj_data.qpos[qpos_addr] = qpos_value
            for qvel_addr in preserved_qvel:
                self._mj_data.qvel[qvel_addr] = 0.0
            if ctrl_snapshot is not None:
                self._mj_data.ctrl[:] = ctrl_snapshot
            _mujoco.mj_forward(self._mj_model, self._mj_data)
        restore_locked_scene_objects()
        for qpos_addr, qpos_value in preserved_qpos:
            self._mj_data.qpos[qpos_addr] = qpos_value
        for qvel_addr in preserved_qvel:
            self._mj_data.qvel[qvel_addr] = 0.0
        if ctrl_snapshot is not None:
            self._mj_data.ctrl[:] = ctrl_snapshot
        self._mj_data.qvel[:] = 0.0
        _mujoco.mj_forward(self._mj_model, self._mj_data)
        self._sync_internal_state_from_mujoco_locked()

    def _apply_object_reset_policy_locked(self) -> None:
        using_mujoco = self._using_mujoco_model()
        scene_changed = False

        for obj_id, policy in self._object_reset_policy.items():
            mode = str(policy.get("mode", "fixed")).strip().lower()
            if mode != "random_in_region":
                continue

            region_id = str(policy.get("region_id", "")).strip()
            if not region_id:
                continue
            region = self._spawn_regions.get(region_id)
            if region is None:
                continue

            min_pos = region["min"]
            max_pos = region["max"]
            sampled = [
                random.uniform(min_pos[0], max_pos[0]),
                random.uniform(min_pos[1], max_pos[1]),
                random.uniform(min_pos[2], max_pos[2]),
            ]
            preserve_height = bool(policy.get("preserve_height", False))
            template_state = self._scene_objects_template.get(obj_id)
            template_position = (
                template_state.get("position", [0.0, 0.0, BACKEND_FRAME_Z_OFFSET])
                if isinstance(template_state, dict)
                else [0.0, 0.0, BACKEND_FRAME_Z_OFFSET]
            )
            if preserve_height and isinstance(template_position, list) and len(template_position) >= 3:
                if region["frame"] == "frontend":
                    sampled[1] = float(self._backend_to_frontend_position(template_position)[1])
                else:
                    sampled[2] = float(template_position[2])
            backend_position = (
                self._frontend_to_backend_position(sampled)
                if region["frame"] == "frontend"
                else sampled
            )

            template_quaternion = [1.0, 0.0, 0.0, 0.0]
            if isinstance(template_state, dict):
                raw_quaternion = template_state.get("quaternion", template_quaternion)
                if isinstance(raw_quaternion, list) and len(raw_quaternion) >= 4:
                    template_quaternion = _normalize_quaternion(raw_quaternion)

            quaternion = list(template_quaternion)
            if bool(policy.get("random_yaw", False)):
                yaw_range = policy.get("yaw_range_rad", [-math.pi, math.pi])
                yaw_min = -math.pi
                yaw_max = math.pi
                if isinstance(yaw_range, list) and len(yaw_range) >= 2:
                    try:
                        yaw_min = float(yaw_range[0])
                        yaw_max = float(yaw_range[1])
                    except (TypeError, ValueError):
                        yaw_min = -math.pi
                        yaw_max = math.pi
                # 工具只绕后端竖直 Z 轴随机朝向，保持贴桌面和平放姿态，避免出现悬空或翻转。
                yaw = random.uniform(min(yaw_min, yaw_max), max(yaw_min, yaw_max))
                quaternion = _normalize_quaternion(_quaternion_multiply(_rpy_to_quaternion(0.0, 0.0, yaw), template_quaternion))

            if obj_id in self._scene_objects_template:
                self._scene_objects_template[obj_id]["position"] = list(backend_position)
                self._scene_objects_template[obj_id]["quaternion"] = list(quaternion)
                self._scene_objects_template[obj_id]["attached_to_gripper"] = False

            if using_mujoco and obj_id in self._scene_objects_template:
                if isinstance(quaternion, list) and len(quaternion) >= 4:
                    if self._set_object_pose_locked(obj_id, backend_position, quaternion, reset_velocity=True):
                        scene_changed = True

        if using_mujoco and scene_changed and _mujoco is not None and self._mj_model is not None and self._mj_data is not None:
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _clamp_arm_targets(self, target: list[float]) -> list[float]:
        if not self._arm_joint_limits:
            return target
        clamped = list(target)
        for idx, name in enumerate(self._arm_joint_names):
            if idx >= len(clamped):
                break
            limits = self._arm_joint_limits.get(name)
            if limits is None:
                continue
            lo, hi = limits
            if clamped[idx] < lo:
                clamped[idx] = lo
            elif clamped[idx] > hi:
                clamped[idx] = hi
        return clamped

    def _read_current_arm_qpos_locked(self) -> list[float]:
        if self._using_mujoco_model() and self._mj_data is not None:
            current: list[float] = []
            for idx, name in enumerate(self._arm_joint_names):
                qpos_addr = self._arm_joint_qpos_addr.get(name)
                if qpos_addr is None:
                    current.append(self._arm_qpos[idx] if idx < len(self._arm_qpos) else 0.0)
                else:
                    current.append(float(self._mj_data.qpos[qpos_addr]))
            return current
        return list(self._arm_qpos)

    def _clear_realtime_ee_target_locked(self, source_key: str | None = None) -> None:
        if source_key:
            self._realtime_ee_target_by_source.pop(str(source_key), None)
            self._clear_cartesian_servo_target_locked(source_key)
            return
        self._realtime_ee_target_by_source = {}
        self._clear_cartesian_servo_target_locked()

    def _clear_cartesian_servo_target_locked(self, source_key: str | None = None) -> None:
        if source_key is None:
            self._active_cartesian_servo_target = None
            return
        active = self._active_cartesian_servo_target
        if active is not None and active.source_key == str(source_key):
            self._active_cartesian_servo_target = None

    def _update_last_normalized_input_locked(self, values: dict[str, Any]) -> None:
        if isinstance(self._last_normalized_input, dict):
            self._last_normalized_input.update(values)
            return
        self._last_normalized_input = dict(values)

    def _stabilize_realtime_ee_target_locked(
        self,
        source_key: str,
        target_position: list[float],
        target_quaternion: list[float],
        current_pose: dict[str, Any],
    ) -> tuple[list[float], list[float]]:
        current_position = [float(v) for v in current_pose["position"][:3]]
        current_quaternion = _normalize_quaternion(current_pose["quaternion"])
        previous = self._realtime_ee_target_by_source.get(source_key)
        if previous is None:
            base_position = list(current_position)
            base_quaternion = list(current_quaternion)
        else:
            base_position = [float(v) for v in previous.get("position", current_position)[:3]]
            base_quaternion = _normalize_quaternion(previous.get("quaternion", current_quaternion))
            if (
                _vec_distance(base_position, current_position) > REALTIME_EE_RESEED_DRIFT_M
                or _quaternion_angle_distance_rad(base_quaternion, current_quaternion)
                > REALTIME_EE_RESEED_DRIFT_RAD
            ):
                base_position = list(current_position)
                base_quaternion = list(current_quaternion)

        delta_position = [
            float(target_position[idx]) - float(base_position[idx])
            for idx in range(3)
        ]
        delta_norm = math.sqrt(sum(component * component for component in delta_position))
        if delta_norm <= REALTIME_EE_POSITION_DEADBAND_M:
            stabilized_position = list(base_position)
        elif delta_norm <= REALTIME_EE_TARGET_MAX_STEP_M:
            stabilized_position = [float(v) for v in target_position[:3]]
        else:
            scale = REALTIME_EE_TARGET_MAX_STEP_M / max(delta_norm, 1e-8)
            stabilized_position = [
                float(base_position[idx]) + delta_position[idx] * scale
                for idx in range(3)
            ]

        target_quat = _normalize_quaternion(target_quaternion)
        quat_error = _quaternion_angle_distance_rad(base_quaternion, target_quat)
        if quat_error <= REALTIME_EE_ORIENTATION_DEADBAND_RAD:
            stabilized_quaternion = list(base_quaternion)
        elif quat_error <= REALTIME_EE_TARGET_MAX_STEP_RAD:
            stabilized_quaternion = list(target_quat)
        else:
            stabilized_quaternion = _quaternion_slerp(
                base_quaternion,
                target_quat,
                REALTIME_EE_TARGET_MAX_STEP_RAD / max(quat_error, 1e-8),
            )

        self._realtime_ee_target_by_source[source_key] = {
            "position": [float(v) for v in stabilized_position[:3]],
            "quaternion": [float(v) for v in stabilized_quaternion[:4]],
        }
        return stabilized_position, stabilized_quaternion

    def _extract_ee_target_pose_locked(
        self,
        request: StepRequest,
    ) -> tuple[list[float], list[float]] | None:
        target_pose = getattr(request, "target_ee_pose", None)
        target_delta = getattr(request, "target_ee_delta", None)
        if target_pose is None and target_delta is None:
            return None

        current_pose = self._build_control_ee_pose_locked()
        target_position: list[float] | None = None
        target_quaternion = _normalize_quaternion(current_pose.get("quaternion", [1.0, 0.0, 0.0, 0.0]))

        raw_position = getattr(target_pose, "position", None) if target_pose is not None else None
        if isinstance(raw_position, list) and len(raw_position) >= 3:
            try:
                target_position = [float(raw_position[0]), float(raw_position[1]), float(raw_position[2])]
            except (TypeError, ValueError):
                target_position = None

        raw_quaternion = getattr(target_pose, "quaternion", None) if target_pose is not None else None
        if isinstance(raw_quaternion, list) and len(raw_quaternion) >= 4:
            try:
                target_quaternion = _normalize_quaternion([float(v) for v in raw_quaternion[:4]])
            except (TypeError, ValueError):
                target_quaternion = _normalize_quaternion(current_pose.get("quaternion", [1.0, 0.0, 0.0, 0.0]))

        if target_position is None and isinstance(target_delta, list) and len(target_delta) >= 3:
            try:
                target_position = [
                    float(current_pose["position"][axis]) + float(target_delta[axis])
                    for axis in range(3)
                ]
            except (TypeError, ValueError):
                target_position = None

        if target_position is None:
            return None

        if _is_realtime_source(request.source, input_source=getattr(request, "input_source", None)):
            source_key = self._realtime_queue_source_key(request) or str(request.source)
            target_position, target_quaternion = self._stabilize_realtime_ee_target_locked(
                source_key,
                target_position,
                target_quaternion,
                current_pose,
            )

        return target_position, target_quaternion

    def _can_use_cartesian_servo_locked(self) -> bool:
        has_control_frame = (
            self._tool_site_id is not None
            or self._tool_body_id is not None
            or any(self._gripper_body_ids.get(name) is not None for name in GRIPPER_GRASP_PAD_BODY_NAMES)
        )
        return (
            self._using_mujoco_model()
            and self._mj_model is not None
            and self._mj_data is not None
            and _mujoco is not None
            and np is not None
            and has_control_frame
            and all(self._arm_joint_qvel_addr.get(name) is not None for name in self._arm_joint_names)
        )

    def _activate_cartesian_servo_target_locked(
        self,
        request: StepRequest,
        target_position: list[float],
        target_quaternion: list[float],
    ) -> None:
        source_key = self._realtime_queue_source_key(request) or str(request.source)
        previous = self._active_cartesian_servo_target
        arm_count = len(self._arm_joint_names)
        if previous is not None and previous.source_key == source_key:
            last_qvel = list(previous.last_qvel[:arm_count])
            last_qaccel = list(previous.last_qaccel[:arm_count])
        else:
            last_qvel = [0.0 for _ in range(arm_count)]
            last_qaccel = [0.0 for _ in range(arm_count)]

        if len(last_qvel) < arm_count:
            last_qvel = [0.0 for _ in range(arm_count)]
        if len(last_qaccel) < arm_count:
            last_qaccel = [0.0 for _ in range(arm_count)]

        self._active_cartesian_servo_target = _CartesianServoTarget(
            source_key=source_key,
            position=[float(v) for v in target_position[:3]],
            quaternion=_normalize_quaternion(target_quaternion),
            orientation_follow_enabled=_read_orientation_follow_enabled_from_request(request),
            updated_at=perf_counter(),
            last_qvel=last_qvel,
            last_qaccel=last_qaccel,
        )

    def _limit_cartesian_servo_joint_velocity(
        self,
        qpos: Any,
        desired_qvel: Any,
        previous_qvel: list[float],
        dt: float,
    ) -> Any:
        if np is None:
            return desired_qvel

        qvel = np.asarray(desired_qvel, dtype=float)
        previous = np.asarray(previous_qvel[: qvel.size], dtype=float)
        if previous.size != qvel.size:
            previous = np.zeros_like(qvel)

        stable_dt = max(float(dt), 1e-6)
        max_accel_step = CARTESIAN_SERVO_MAX_JOINT_ACCEL_RAD_S2 * stable_dt
        qvel = previous + np.clip(qvel - previous, -max_accel_step, max_accel_step)
        qvel = np.clip(
            qvel,
            -CARTESIAN_SERVO_MAX_JOINT_SPEED_RAD_S,
            CARTESIAN_SERVO_MAX_JOINT_SPEED_RAD_S,
        )

        for idx, joint_name in enumerate(self._arm_joint_names[: qvel.size]):
            limits = self._arm_joint_limits.get(joint_name)
            if limits is None:
                continue
            lo, hi = limits
            q_value = float(qpos[idx])
            distance_to_lower = max(0.0, q_value - float(lo))
            distance_to_upper = max(0.0, float(hi) - q_value)
            margin = max(CARTESIAN_SERVO_JOINT_LIMIT_MARGIN_RAD, 1e-6)

            if qvel[idx] < 0.0 and distance_to_lower < margin:
                qvel[idx] *= _clamp(distance_to_lower / margin, 0.0, 1.0)
            elif qvel[idx] > 0.0 and distance_to_upper < margin:
                qvel[idx] *= _clamp(distance_to_upper / margin, 0.0, 1.0)

            next_q = q_value + float(qvel[idx]) * stable_dt
            if next_q < lo:
                qvel[idx] = (float(lo) - q_value) / stable_dt
            elif next_q > hi:
                qvel[idx] = (float(hi) - q_value) / stable_dt

        return qvel

    def _update_cartesian_servo_arm_command_locked(self, dt: float) -> bool:
        target = self._active_cartesian_servo_target
        if target is None:
            return False
        if (
            not self._can_use_cartesian_servo_locked()
            or self._mj_model is None
            or self._mj_data is None
            or np is None
        ):
            self._clear_cartesian_servo_target_locked()
            return False

        active_source_key = self._realtime_state_source_key(self._source, self._last_input_source)
        if active_source_key is None:
            self._clear_cartesian_servo_target_locked()
            return False
        if active_source_key != target.source_key:
            return False

        current_pose = self._build_control_ee_pose_locked()
        current_position = np.asarray(current_pose["position"][:3], dtype=float)
        current_quaternion = _normalize_quaternion(current_pose["quaternion"])
        target_position = np.asarray(target.position[:3], dtype=float)
        target_quaternion = _normalize_quaternion(target.quaternion)

        position_error = target_position - current_position
        position_error_norm = float(np.linalg.norm(position_error))
        jacobian = self._compute_control_ee_jacobian_locked()
        if jacobian is None:
            self._clear_cartesian_servo_target_locked()
            return False

        jacp, jacr = jacobian
        dof_indices = [int(self._arm_joint_qvel_addr[name]) for name in self._arm_joint_names]
        current_joint_qvel = np.asarray(
            [float(self._mj_data.qvel[idx]) for idx in dof_indices],
            dtype=float,
        )
        current_linear_velocity = jacp[:, dof_indices] @ current_joint_qvel
        current_angular_velocity = jacr[:, dof_indices] @ current_joint_qvel

        if position_error_norm <= CARTESIAN_SERVO_POSITION_DEADBAND_M:
            linear_velocity = -current_linear_velocity * CARTESIAN_SERVO_LINEAR_DAMPING
        else:
            linear_velocity = (
                position_error * CARTESIAN_SERVO_LINEAR_GAIN_S
                - current_linear_velocity * CARTESIAN_SERVO_LINEAR_DAMPING
            )
            linear_speed = float(np.linalg.norm(linear_velocity))
            if linear_speed > CARTESIAN_SERVO_MAX_LINEAR_SPEED_M_S:
                linear_velocity *= CARTESIAN_SERVO_MAX_LINEAR_SPEED_M_S / max(linear_speed, 1e-8)

        orientation_error = np.asarray(
            _quaternion_error_vector(target_quaternion, current_quaternion),
            dtype=float,
        )
        orientation_error_norm = float(np.linalg.norm(orientation_error))
        orientation_weight = (
            CARTESIAN_SERVO_ORIENTATION_WEIGHT
            if target.orientation_follow_enabled
            else CARTESIAN_SERVO_LOCKED_ORIENTATION_WEIGHT
        )
        if orientation_weight <= 1e-6:
            angular_velocity = np.zeros(3, dtype=float)
        elif orientation_error_norm <= CARTESIAN_SERVO_ORIENTATION_DEADBAND_RAD:
            angular_velocity = -current_angular_velocity * CARTESIAN_SERVO_ANGULAR_DAMPING
        else:
            angular_velocity = (
                orientation_error * CARTESIAN_SERVO_ANGULAR_GAIN_S
                - current_angular_velocity * CARTESIAN_SERVO_ANGULAR_DAMPING
            )
            angular_speed = float(np.linalg.norm(angular_velocity))
            if angular_speed > CARTESIAN_SERVO_MAX_ANGULAR_SPEED_RAD_S:
                angular_velocity *= CARTESIAN_SERVO_MAX_ANGULAR_SPEED_RAD_S / max(angular_speed, 1e-8)
        task_velocity_parts = [linear_velocity * CARTESIAN_SERVO_POSITION_WEIGHT]
        task_jacobian_parts = [jacp[:, dof_indices] * CARTESIAN_SERVO_POSITION_WEIGHT]
        if orientation_weight > 1e-6:
            task_velocity_parts.append(angular_velocity * orientation_weight)
            task_jacobian_parts.append(jacr[:, dof_indices] * orientation_weight)
        task_velocity = np.concatenate(task_velocity_parts)
        task_jacobian = np.vstack(task_jacobian_parts)

        try:
            singular_values = np.linalg.svd(task_jacobian, compute_uv=False)
        except Exception:
            singular_values = np.asarray([], dtype=float)
        min_singular = float(np.min(singular_values)) if singular_values.size else 0.0
        singular_scale = 1.0
        if min_singular < CARTESIAN_SERVO_MIN_SINGULAR_VALUE:
            singular_scale = _clamp(
                min_singular / max(CARTESIAN_SERVO_MIN_SINGULAR_VALUE, 1e-8),
                0.20,
                1.0,
            )

        lhs = task_jacobian @ task_jacobian.T
        lhs += np.eye(lhs.shape[0]) * (CARTESIAN_SERVO_DAMPING * CARTESIAN_SERVO_DAMPING)
        try:
            task_step = np.linalg.solve(lhs, task_velocity)
        except Exception:
            task_step = np.linalg.lstsq(lhs, task_velocity, rcond=None)[0]
        desired_qvel = (task_jacobian.T @ task_step) * singular_scale

        qpos = np.asarray(self._read_current_arm_qpos_locked(), dtype=float)
        qvel = self._limit_cartesian_servo_joint_velocity(
            qpos,
            desired_qvel,
            target.last_qvel,
            dt,
        )
        stable_dt = max(float(dt), 1e-6)
        command_qpos = np.asarray(self._arm_command_qpos[: qvel.size], dtype=float)
        if command_qpos.size != qvel.size:
            command_qpos = qpos.copy()

        proposed_qpos = command_qpos + qvel * stable_dt
        command_lead = np.clip(
            proposed_qpos - qpos,
            -CARTESIAN_SERVO_MAX_COMMAND_LEAD_RAD,
            CARTESIAN_SERVO_MAX_COMMAND_LEAD_RAD,
        )
        next_qpos = np.asarray(
            self._clamp_arm_targets((qpos + command_lead).tolist()),
            dtype=float,
        )
        limited_qvel = qvel
        previous_qvel = np.asarray(target.last_qvel[: limited_qvel.size], dtype=float)
        if previous_qvel.size != limited_qvel.size:
            previous_qvel = np.zeros_like(limited_qvel)
        actual_qaccel = (limited_qvel - previous_qvel) / stable_dt

        target.last_qvel = [float(v) for v in limited_qvel.tolist()]
        target.last_qaccel = [float(v) for v in actual_qaccel.tolist()]
        self._arm_command_qpos = [float(v) for v in next_qpos.tolist()]
        self._arm_qvel = [float(v) for v in limited_qvel.tolist()]

        servo_status = "holding"
        if position_error_norm > CARTESIAN_SERVO_POSITION_DEADBAND_M or (
            target.orientation_follow_enabled
            and orientation_error_norm > CARTESIAN_SERVO_ORIENTATION_DEADBAND_RAD
        ):
            servo_status = "tracking"
        if singular_scale < 0.99:
            servo_status = "singularity_slowdown"

        self._update_last_normalized_input_locked(
            {
                "cartesian_servo_active": 1,
                "cartesian_servo_status": servo_status,
                "cartesian_servo_position_error_m": position_error_norm,
                "cartesian_servo_orientation_error_rad": orientation_error_norm,
                "cartesian_servo_min_singular_value": min_singular,
                "cartesian_servo_speed_scale": singular_scale,
                "cartesian_servo_orientation_enabled": 1 if target.orientation_follow_enabled else 0,
                "cartesian_servo_orientation_weight": orientation_weight,
                "ik_active": 0,
                "ik_status": "cartesian_servo",
            }
        )
        return True

    def _solve_ee_ik_locked(
        self,
        target_position: list[float],
        target_quaternion: list[float],
        ik_profile: dict[str, float] | None = None,
    ) -> tuple[list[float] | None, dict[str, Any]]:
        info: dict[str, Any] = {
            "active": True,
            "status": "unavailable",
            "position_error_m": None,
            "orientation_error_rad": None,
        }
        if (
            not self._using_mujoco_model()
            or self._mj_model is None
            or self._mj_data is None
            or (self._tool_site_id is None and self._tool_body_id is None)
            or _mujoco is None
            or np is None
        ):
            return None, info

        arm_qpos_addrs = [self._arm_joint_qpos_addr.get(name) for name in self._arm_joint_names]
        arm_dof_addrs = [self._arm_joint_qvel_addr.get(name) for name in self._arm_joint_names]
        if any(addr is None for addr in arm_qpos_addrs) or any(addr is None for addr in arm_dof_addrs):
            info["status"] = "missing_arm_joints"
            return None, info

        profile = dict(ik_profile or {})
        max_iterations = max(1, int(profile.get("max_iterations", IK_MAX_ITERATIONS)))
        position_weight = max(1e-4, float(profile.get("position_weight", IK_POSITION_WEIGHT)))
        orientation_weight = max(0.0, float(profile.get("orientation_weight", IK_ORIENTATION_WEIGHT)))
        damping = max(1e-5, float(profile.get("damping", IK_DAMPING)))
        max_step_rad = max(1e-5, float(profile.get("max_step_rad", IK_MAX_STEP_RAD)))
        position_tolerance_m = max(1e-5, float(profile.get("position_tolerance_m", IK_POSITION_TOLERANCE_M)))
        orientation_tolerance_rad = max(
            1e-5,
            float(profile.get("orientation_tolerance_rad", IK_ORIENTATION_TOLERANCE_RAD)),
        )
        orientation_goal_active = orientation_weight > 1e-4
        info["position_weight"] = position_weight
        info["orientation_weight"] = orientation_weight
        info["orientation_target_active"] = orientation_goal_active

        qpos_snapshot = self._mj_data.qpos.copy()
        qvel_snapshot = self._mj_data.qvel.copy()
        ctrl_snapshot = self._mj_data.ctrl.copy()
        act_snapshot = self._mj_data.act.copy() if self._mj_data.act is not None and len(self._mj_data.act) > 0 else None

        try:
            q = np.asarray(self._read_current_arm_qpos_locked(), dtype=float)
            target_pos = np.asarray(target_position[:3], dtype=float)
            target_quat = _normalize_quaternion(target_quaternion)
            qpos_indices = [int(addr) for addr in arm_qpos_addrs if addr is not None]
            dof_indices = [int(addr) for addr in arm_dof_addrs if addr is not None]

            def read_tool_pose() -> tuple[Any, list[float]]:
                pose = self._build_control_ee_pose_locked()
                if pose is None:
                    return (
                        np.asarray(target_pos, dtype=float),
                        _normalize_quaternion(target_quat),
                    )
                return (
                    np.asarray(pose["position"], dtype=float),
                    _normalize_quaternion(pose["quaternion"]),
                )

            for idx, qpos_addr in enumerate(qpos_indices):
                self._mj_data.qpos[qpos_addr] = float(q[idx])
            self._mj_data.qvel[:] = 0.0
            _mujoco.mj_forward(self._mj_model, self._mj_data)

            final_position_error = float("inf")
            final_orientation_error = float("inf")
            for _ in range(max_iterations):
                current_pos, current_quat = read_tool_pose()
                position_error = target_pos - current_pos
                orientation_error = np.asarray(
                    _quaternion_error_vector(target_quat, current_quat),
                    dtype=float,
                )
                final_position_error = float(np.linalg.norm(position_error))
                final_orientation_error = float(np.linalg.norm(orientation_error))
                if (
                    final_position_error <= position_tolerance_m
                    and (
                        not orientation_goal_active
                        or final_orientation_error <= orientation_tolerance_rad
                    )
                ):
                    break

                control_jacobian = self._compute_control_ee_jacobian_locked()
                if control_jacobian is None:
                    jacp = np.zeros((3, self._mj_model.nv), dtype=float)
                    jacr = np.zeros((3, self._mj_model.nv), dtype=float)
                    if self._tool_site_id is not None:
                        _mujoco.mj_jacSite(
                            self._mj_model,
                            self._mj_data,
                            jacp,
                            jacr,
                            int(self._tool_site_id),
                        )
                    else:
                        _mujoco.mj_jacBody(
                            self._mj_model,
                            self._mj_data,
                            jacp,
                            jacr,
                            int(self._tool_body_id),
                        )
                else:
                    jacp, jacr = control_jacobian
                task_error = np.concatenate(
                    [
                        position_error * position_weight,
                        orientation_error * orientation_weight,
                    ]
                )
                task_jacobian = np.vstack(
                    [
                        jacp[:, dof_indices] * position_weight,
                        jacr[:, dof_indices] * orientation_weight,
                    ]
                )
                lhs = task_jacobian @ task_jacobian.T
                lhs += np.eye(lhs.shape[0]) * (damping * damping)
                try:
                    task_step = np.linalg.solve(lhs, task_error)
                except Exception:
                    task_step = np.linalg.lstsq(lhs, task_error, rcond=None)[0]
                dq = task_jacobian.T @ task_step
                max_abs_step = float(np.max(np.abs(dq))) if dq.size else 0.0
                if max_abs_step > max_step_rad:
                    dq *= max_step_rad / max_abs_step

                q = np.asarray(self._clamp_arm_targets((q + dq).tolist()), dtype=float)
                for idx, qpos_addr in enumerate(qpos_indices):
                    self._mj_data.qpos[qpos_addr] = float(q[idx])
                self._mj_data.qvel[:] = 0.0
                _mujoco.mj_forward(self._mj_model, self._mj_data)

            current_pos, current_quat = read_tool_pose()
            final_position_error = float(np.linalg.norm(target_pos - current_pos))
            final_orientation_error = float(
                np.linalg.norm(np.asarray(_quaternion_error_vector(target_quat, current_quat), dtype=float))
            )
            info["position_error_m"] = final_position_error
            info["orientation_error_rad"] = final_orientation_error
            info["status"] = (
                "solved"
                if (
                    final_position_error <= max(0.012, position_tolerance_m * 3.0)
                    and (
                        not orientation_goal_active
                        or final_orientation_error <= max(0.10, orientation_tolerance_rad * 3.0)
                    )
                )
                else "best_effort"
            )
            return self._clamp_arm_targets(q.tolist()), info
        finally:
            self._mj_data.qpos[:] = qpos_snapshot
            self._mj_data.qvel[:] = qvel_snapshot
            self._mj_data.ctrl[:] = ctrl_snapshot
            if act_snapshot is not None:
                self._mj_data.act[:] = act_snapshot
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _resolve_arm_target_for_request_locked(
        self,
        request: StepRequest,
        target_positions: list[float] | None,
    ) -> list[float] | None:
        ee_target = self._extract_ee_target_pose_locked(request)
        if ee_target is None:
            if target_positions is not None or not _is_realtime_source(
                request.source,
                input_source=getattr(request, "input_source", None),
            ):
                self._clear_cartesian_servo_target_locked()
            return target_positions

        orientation_follow_enabled = _read_orientation_follow_enabled_from_request(request)
        realtime_source = _is_realtime_source(request.source, input_source=getattr(request, "input_source", None))
        self._update_last_normalized_input_locked(
            {
                "ee_target_position": [float(v) for v in ee_target[0][:3]],
                "ee_target_quaternion": [float(v) for v in ee_target[1][:4]],
                "ee_orientation_follow_enabled": 1 if orientation_follow_enabled else 0,
            }
        )
        if realtime_source and self._can_use_cartesian_servo_locked():
            self._activate_cartesian_servo_target_locked(request, ee_target[0], ee_target[1])
            self._update_last_normalized_input_locked(
                {
                    "control_mode": "cartesian_servo",
                    "cartesian_servo_active": 1,
                    "cartesian_servo_status": "queued",
                    "ik_active": 0,
                    "ik_status": "cartesian_servo",
                }
            )
            if len(self._arm_command_qpos) >= len(self._arm_joint_names):
                return list(self._arm_command_qpos[: len(self._arm_joint_names)])
            return self._read_current_arm_qpos_locked()

        self._clear_cartesian_servo_target_locked()
        ik_profile = {
            "position_weight": IK_POSITION_WEIGHT,
            "orientation_weight": IK_ORIENTATION_WEIGHT,
            "damping": IK_DAMPING,
            "max_step_rad": IK_MAX_STEP_RAD,
            "position_tolerance_m": IK_POSITION_TOLERANCE_M,
            "orientation_tolerance_rad": IK_ORIENTATION_TOLERANCE_RAD,
        }
        if realtime_source:
            ik_profile.update(
                {
                    "damping": IK_REALTIME_DAMPING,
                    "max_iterations": IK_REALTIME_MAX_ITERATIONS,
                    "max_step_rad": IK_REALTIME_MAX_STEP_RAD,
                    "orientation_weight": (
                        IK_REALTIME_ORIENTATION_WEIGHT
                        if orientation_follow_enabled
                        else IK_REALTIME_LOCKED_ORIENTATION_WEIGHT
                    ),
                }
            )
        solved_target, ik_info = self._solve_ee_ik_locked(ee_target[0], ee_target[1], ik_profile=ik_profile)
        if isinstance(self._last_normalized_input, dict):
            self._last_normalized_input.update(
                {
                    "ik_active": 1,
                    "ik_status": ik_info.get("status"),
                    "ik_position_error_m": ik_info.get("position_error_m"),
                    "ik_orientation_error_rad": ik_info.get("orientation_error_rad"),
                    "ik_position_weight": ik_info.get("position_weight"),
                    "ik_orientation_weight": ik_info.get("orientation_weight"),
                    "ik_orientation_target_active": ik_info.get("orientation_target_active"),
                }
            )
        else:
            self._last_normalized_input = {
                "ik_active": 1,
                "ik_status": ik_info.get("status"),
            }

        if solved_target is not None:
            return solved_target
        if target_positions is not None:
            return target_positions
        return self._read_current_arm_qpos_locked()

    def _is_realtime_hold_input_locked(self) -> bool:
        return (
            isinstance(self._last_normalized_input, dict)
            and float(self._last_normalized_input.get("ee_hold", 0) or 0) >= 0.5
        )

    def _apply_arm_command(self, target_positions: list[float] | None, n_steps: int, source: str = "manual") -> None:
        if target_positions is None:
            self._clear_cartesian_servo_target_locked()
            self._arm_qvel = [0.0 for _ in self._arm_qvel]
            self._arm_servo_ctrl_qvel = [0.0 for _ in self._arm_servo_ctrl_qvel]
            self._arm_servo_ctrl_qaccel = [0.0 for _ in self._arm_servo_ctrl_qaccel]
            return

        current = self._read_current_arm_qpos_locked()
        if self._is_realtime_hold_input_locked():
            self._clear_cartesian_servo_target_locked()
            self._arm_qvel = [0.0 for _ in current]
            self._arm_command_qpos = list(current)
            self._arm_servo_ctrl_qpos = list(current)
            self._arm_servo_ctrl_qvel = [0.0 for _ in current]
            self._arm_servo_ctrl_qaccel = [0.0 for _ in current]
            if self._using_mujoco_model() and self._mj_data is not None:
                for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
                    actuator_id = self._arm_actuator_ids.get(actuator_name)
                    if actuator_id is not None and idx < len(current):
                        self._mj_data.ctrl[actuator_id] = float(current[idx])
            else:
                self._arm_qpos = list(current)
            return

        target = self._clamp_arm_targets([float(v) for v in target_positions])
        if _should_limit_realtime_target_delta(source):
            limited_target: list[float] = []
            for idx, target_value in enumerate(target):
                current_value = current[idx] if idx < len(current) else 0.0
                delta = _clamp(
                    target_value - current_value,
                    -REALTIME_ARM_MAX_DELTA_RAD,
                    REALTIME_ARM_MAX_DELTA_RAD,
                )
                limited_target.append(current_value + delta)
            target = limited_target
        blend_current = current
        blend = _resolve_command_blend(source, n_steps, ARM_COMMAND_BLEND_PER_STEP)
        applied = [
            blend_current[idx] + (target[idx] - blend_current[idx]) * blend
            for idx in range(len(target))
        ]
        duration = max(self._dt, n_steps * self._dt)
        self._arm_qvel = [(applied[i] - current[i]) / duration for i in range(len(applied))]
        self._arm_command_qpos = list(applied)

        if self._using_mujoco_model() and self._mj_data is not None:
            self._apply_mujoco_servo_command_locked(immediate=False)
            return

        # Stub fallback path.
        self._arm_qpos = list(applied)

    def _apply_gripper_command(
        self,
        command: GripperCommand | None,
        n_steps: int,
        source: str = "manual",
    ) -> None:
        if command is None:
            self._gripper_velocity = 0.0
            self._gripper_servo_ctrl_velocity = 0.0
            self._gripper_servo_ctrl_accel = 0.0
            return

        if command.mode != "open_close":
            raise ValueError(f"Unsupported gripper command mode: {command.mode}")

        current_opening = self._read_current_gripper_opening_locked()
        if self._is_realtime_hold_input_locked():
            self._gripper_velocity = 0.0
            self._gripper_command_opening = current_opening
            self._gripper_servo_ctrl_opening = current_opening
            self._gripper_servo_ctrl_velocity = 0.0
            self._gripper_servo_ctrl_accel = 0.0
            self._gripper_opening = current_opening
            self._gripper_joints = self._map_gripper_joints(current_opening)
            if self._using_mujoco_model() and self._mj_data is not None:
                self._set_mujoco_gripper_target_locked(current_opening)
            return

        desired_opening = _clamp(float(command.value), 0.0, 1.0)
        if _should_limit_realtime_target_delta(source):
            desired_opening = _clamp(
                current_opening
                + _clamp(
                    desired_opening - current_opening,
                    -REALTIME_GRIPPER_MAX_DELTA_OPENING,
                    REALTIME_GRIPPER_MAX_DELTA_OPENING,
                ),
                0.0,
                1.0,
            )
        blend_current_opening = current_opening
        blend = _resolve_command_blend(source, n_steps, GRIPPER_COMMAND_BLEND_PER_STEP)
        target_opening = blend_current_opening + (desired_opening - blend_current_opening) * blend
        duration = max(self._dt, n_steps * self._dt)
        self._gripper_velocity = (target_opening - current_opening) / duration
        self._gripper_command_opening = target_opening
        self._gripper_opening = target_opening
        self._gripper_joints = self._map_gripper_joints(self._gripper_command_opening)

        if self._using_mujoco_model() and self._mj_data is not None:
            self._apply_mujoco_servo_command_locked(immediate=False)
            return

    def _advance_passive_physics_locked(self, elapsed_s: float | None = None) -> int:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None or _mujoco is None:
            return 0

        raw_elapsed = float(elapsed_s) if elapsed_s is not None else self._dt
        if not math.isfinite(raw_elapsed) or raw_elapsed <= 0.0:
            return 0

        if self._should_hold_stale_streaming_control_locked():
            self._clear_realtime_ee_target_locked(
                self._realtime_state_source_key(self._source, self._last_input_source)
            )
            self._hold_current_pose_targets_locked()
            self._last_streaming_command_at = None
            self._objects_state = self._collect_objects_state_locked()
            return 0

        dt = max(self._dt, 1e-6)
        steps = max(1, int(round(raw_elapsed / dt)))
        steps = min(steps, PASSIVE_ADVANCE_MAX_STEPS)

        last_safe_qpos = self._mj_data.qpos.copy()
        last_safe_qvel = self._mj_data.qvel.copy()
        forbidden_contacts: list[dict[str, Any]] = []
        for _ in range(steps):
            self._apply_mujoco_servo_command_locked(advance_cartesian_servo=True)
            _mujoco.mj_step(self._mj_model, self._mj_data)
            self._update_grasp_assist_locked(forward=False)
            forbidden_contacts = self._collect_forbidden_contacts_locked()
            if forbidden_contacts:
                break
            last_safe_qpos = self._mj_data.qpos.copy()
            last_safe_qvel = self._mj_data.qvel.copy()

        if forbidden_contacts:
            self._mj_data.qpos[:] = last_safe_qpos
            self._mj_data.qvel[:] = last_safe_qvel
            _mujoco.mj_forward(self._mj_model, self._mj_data)
            self._sync_internal_state_from_mujoco_locked()
            self._hold_current_pose_targets_locked()
            self._safety_status = "collision_blocked"
            self._collision_blocked = True
            self._last_collision_contacts = deepcopy(forbidden_contacts)
        else:
            self._apply_mujoco_servo_command_locked()
            self._sync_internal_state_from_mujoco_locked()
            self._apply_servo_hold_locked()
            self._safety_status = "normal"
            self._collision_blocked = False
            self._last_collision_contacts = []
        self._update_grasp_assist_locked(forward=True)

        self._sim_time += steps * self._dt
        self._stats["steps"] += steps
        self._objects_state = self._collect_objects_state_locked()
        return steps

    def _should_hold_stale_streaming_control_locked(self) -> bool:
        if self._last_streaming_command_at is None:
            return False
        if not _should_hold_stale_streaming_source(self._source, self._last_input_source):
            return False
        elapsed_s = perf_counter() - float(self._last_streaming_command_at)
        return elapsed_s >= STREAMING_CONTROL_HOLD_TIMEOUT_S

    def _zero_controlled_joint_velocities_locked(self) -> bool:
        if not self._using_mujoco_model() or self._mj_data is None:
            return False

        changed = False
        for qvel_addr in [
            *self._arm_joint_qvel_addr.values(),
            *self._gripper_joint_qvel_addr.values(),
        ]:
            if abs(float(self._mj_data.qvel[int(qvel_addr)])) > 0.0:
                self._mj_data.qvel[int(qvel_addr)] = 0.0
                changed = True
        self._arm_qvel = [0.0 for _ in self._arm_qvel]
        self._gripper_velocity = 0.0
        return changed

    def _apply_servo_hold_locked(self) -> None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None or _mujoco is None:
            return

        realtime_hold_input = self._is_realtime_hold_input_locked()
        streaming_realtime_input = (
            _should_hold_stale_streaming_source(self._source, self._last_input_source)
            and not realtime_hold_input
            and self._last_streaming_command_at is not None
        )
        if streaming_realtime_input:
            return

        snapped = False
        target_arm = self._clamp_arm_targets(list(self._arm_command_qpos))
        actual_arm = self._read_current_arm_qpos_locked()
        hold_arm = list(target_arm)
        arm_count = len(self._arm_joint_names)
        if len(self._arm_servo_ctrl_qpos) < arm_count:
            self._arm_servo_ctrl_qpos = list(actual_arm)
        if len(self._arm_servo_ctrl_qvel) < arm_count:
            self._arm_servo_ctrl_qvel = [0.0 for _ in range(arm_count)]
        if len(self._arm_servo_ctrl_qaccel) < arm_count:
            self._arm_servo_ctrl_qaccel = [0.0 for _ in range(arm_count)]
        for idx, joint_name in enumerate(self._arm_joint_names):
            if idx >= len(target_arm) or idx >= len(actual_arm):
                break
            qpos_addr = self._arm_joint_qpos_addr.get(joint_name)
            qvel_addr = self._arm_joint_qvel_addr.get(joint_name)
            qvel_value = 0.0
            if qvel_addr is not None:
                qvel_value = float(self._mj_data.qvel[qvel_addr])
            error = float(target_arm[idx]) - float(actual_arm[idx])
            if not _should_servo_snap_to_target(
                error,
                qvel_value,
                SERVO_HOLD_ARM_ERROR_RAD,
                SERVO_BRAKE_ARM_ERROR_RAD,
                SERVO_BRAKE_ARM_QVEL_RAD_S,
            ):
                continue
            if qpos_addr is not None:
                self._mj_data.qpos[qpos_addr] = float(target_arm[idx])
                snapped = True
            if qvel_addr is not None:
                self._mj_data.qvel[qvel_addr] = 0.0
                snapped = True
            self._arm_servo_ctrl_qpos[idx] = float(target_arm[idx])
            self._arm_servo_ctrl_qvel[idx] = 0.0
            self._arm_servo_ctrl_qaccel[idx] = 0.0

        current_opening = self._read_current_gripper_opening_locked()
        target_opening = _clamp(float(self._gripper_command_opening), 0.0, 1.0)
        hold_opening = target_opening
        gripper_velocity = 0.0
        driver_qvel_addr = self._gripper_joint_qvel_addr.get("left_driver_joint")
        if driver_qvel_addr is not None:
            gripper_velocity = float(self._mj_data.qvel[driver_qvel_addr]) / max(GRIPPER_DRIVER_LIMIT, 1e-8)
        should_hold_gripper = _should_servo_snap_to_target(
            target_opening - current_opening,
            gripper_velocity,
            SERVO_HOLD_GRIPPER_ERROR_OPENING,
            SERVO_BRAKE_GRIPPER_ERROR_OPENING,
            SERVO_BRAKE_GRIPPER_QVEL_OPENING_S,
        )
        if should_hold_gripper:
            targets = self._map_gripper_joints(hold_opening)
            for joint_name, joint_target in targets.items():
                qpos_addr = self._gripper_joint_qpos_addr.get(joint_name)
                qvel_addr = self._gripper_joint_qvel_addr.get(joint_name)
                if qpos_addr is not None:
                    self._mj_data.qpos[qpos_addr] = float(joint_target)
                    snapped = True
                if qvel_addr is not None:
                    self._mj_data.qvel[qvel_addr] = 0.0
                    snapped = True
            self._gripper_servo_ctrl_opening = float(hold_opening)
            self._gripper_servo_ctrl_velocity = 0.0
            self._gripper_servo_ctrl_accel = 0.0

        if not snapped:
            return

        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            actuator_id = self._arm_actuator_ids.get(actuator_name)
            if actuator_id is None or idx >= len(hold_arm):
                continue
            self._mj_data.ctrl[actuator_id] = float(hold_arm[idx])
            self._set_mujoco_actuator_activation_locked(actuator_id, float(hold_arm[idx]))
        self._set_mujoco_gripper_target_locked(hold_opening)
        _mujoco.mj_forward(self._mj_model, self._mj_data)
        self._sync_internal_state_from_mujoco_locked()

    def _has_pending_dynamics_locked(self) -> bool:
        arm_actual = self._read_current_arm_qpos_locked()
        if len(self._arm_command_qpos) >= len(arm_actual):
            for idx, actual in enumerate(arm_actual):
                if abs(float(self._arm_command_qpos[idx]) - float(actual)) > 1e-4:
                    return True

        current_opening = self._read_current_gripper_opening_locked()
        if abs(float(self._gripper_command_opening) - float(current_opening)) > 1e-4:
            return True

        if any(abs(float(value)) > 1e-4 for value in self._arm_qvel):
            return True
        if abs(float(self._gripper_velocity)) > 1e-4:
            return True

        if self._using_mujoco_model() and self._mj_data is not None:
            return any(abs(float(value)) > 1e-4 for value in self._mj_data.qvel)

        return False

    def _map_gripper_joints(self, opening: float) -> dict[str, float]:
        driver = _clamp(opening, 0.0, 1.0) * GRIPPER_DRIVER_LIMIT
        return {
            "left_driver_joint": driver,
            "right_driver_joint": driver,
            "left_spring_link_joint": driver,
            "right_spring_link_joint": driver,
            "left_follower_joint": driver,
            "right_follower_joint": driver,
        }

    def _collect_objects_state_locked(self) -> dict[str, dict[str, Any]]:
        objects = deepcopy(self._scene_objects_template)
        if not self._using_mujoco_model() or self._mj_data is None:
            return objects

        for obj_id in objects:
            body_id = self._object_body_ids.get(obj_id, -1)
            if body_id < 0:
                continue
            objects[obj_id]["position"] = [float(v) for v in self._mj_data.xpos[body_id]]
            objects[obj_id]["quaternion"] = [float(v) for v in self._mj_data.xquat[body_id]]
            objects[obj_id]["attached_to_gripper"] = (
                self._allows_grasp_assist_locked() and obj_id == self._attached_object_id
            )
        return objects

    def _compute_ee_pose_locked(self) -> dict[str, list[float]]:
        pose = self._compute_tool_frame_pose_locked()
        if pose is not None:
            return pose

        # Fallback FK for stub mode.
        base = self._manifest_data.get("robot", {}).get("transform", {}).get("position", [-0.2, 0.5, -0.1])
        q1, q2, q3, q4, q5, q6 = self._arm_qpos
        reach_xy = 0.45 + 0.05 * math.cos(q3)
        x = float(base[0]) + reach_xy * math.cos(q1) * math.cos(q2)
        y = float(base[1]) + reach_xy * math.sin(q1) * math.cos(q2)
        z = float(base[2]) + 0.35 + 0.15 * math.sin(-q2) + 0.06 * math.sin(q3)
        quat = _rpy_to_quaternion(q4, q5, q6)
        return {"position": [x, y, z], "quaternion": quat}

    def _build_control_ee_pose_locked(self) -> dict[str, list[float]]:
        pose = self._compute_control_ee_pose_locked()
        if pose is not None:
            return pose
        return self._compute_ee_pose_locked()

    def _ensure_mujoco_renderer_locked(self) -> Any | None:
        if (
            not self._using_mujoco_model()
            or self._mj_model is None
            or self._mj_data is None
            or _mujoco is None
            or np is None
        ):
            return None

        render_width = max(int(self._rgb_stream["width"]), int(self._depth_stream["width"]))
        render_height = max(int(self._rgb_stream["height"]), int(self._depth_stream["height"]))
        if render_width <= 0 or render_height <= 0:
            return None

        if (
            self._mj_renderer is not None
            and self._mj_renderer_width == render_width
            and self._mj_renderer_height == render_height
        ):
            return self._mj_renderer

        self._close_mujoco_renderer()
        try:
            self._mj_renderer = _mujoco.Renderer(self._mj_model, width=render_width, height=render_height)
            self._configure_mujoco_depth_map_locked(self._mj_renderer)
            self._mj_renderer_width = render_width
            self._mj_renderer_height = render_height
            return self._mj_renderer
        except Exception:
            self._close_mujoco_renderer()
            return None

    def _configure_mujoco_depth_map_locked(self, renderer: Any) -> str:
        if _mujoco is None:
            return "unavailable"
        context = getattr(renderer, "_mjr_context", None)
        if context is None or not hasattr(context, "readDepthMap"):
            return "unavailable"

        mode = MUJOCO_DEPTH_MAP_MODE
        if mode in {"zerofar", "zero_far", "reverse_z", "reverse-z"}:
            context.readDepthMap = _mujoco.mjtDepthMap.mjDEPTH_ZEROFAR
            return "zerofar"

        # MuJoCo's Python Renderer defaults to mjDEPTH_ZEROFAR, which needs
        # GL_ARB_clip_control for its high-precision reverse-Z path. macOS and
        # some bundled OpenGL contexts do not expose that extension, producing
        # noisy warnings on every depth capture. mjDEPTH_ZERONEAR is the
        # standard OpenGL depth mapping and stays warning-free in those contexts.
        context.readDepthMap = _mujoco.mjtDepthMap.mjDEPTH_ZERONEAR
        return "zeronear"

    def _mujoco_depth_map_mode_locked(self, renderer: Any) -> str:
        context = getattr(renderer, "_mjr_context", None)
        if _mujoco is None or context is None or not hasattr(context, "readDepthMap"):
            return "unavailable"
        if int(context.readDepthMap) == int(_mujoco.mjtDepthMap.mjDEPTH_ZEROFAR):
            return "zerofar"
        return "zeronear"

    def _convert_mujoco_depth_buffer_locked(self, depth_buffer: Any, depth_map_mode: str) -> Any:
        if self._mj_model is None or np is None:
            return depth_buffer

        extent = float(self._mj_model.stat.extent)
        znear = float(self._mj_model.vis.map.znear) * extent
        zfar = float(self._mj_model.vis.map.zfar) * extent
        if not math.isfinite(znear) or not math.isfinite(zfar) or znear <= 0.0 or zfar <= znear:
            return np.asarray(depth_buffer, dtype=np.float32)

        raw = np.asarray(depth_buffer, dtype=np.float64)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            if depth_map_mode == "zerofar":
                zfar32 = np.float32(zfar)
                znear32 = np.float32(znear)
                c_coef = -(zfar32 + znear32) / (zfar32 - znear32)
                d_coef = -(np.float32(2.0) * zfar32 * znear32) / (zfar32 - znear32)
                c_coef = np.float32(-0.5) * c_coef - np.float32(0.5)
                d_coef = np.float32(-0.5) * d_coef
                depth_m = d_coef / (raw + c_coef)
            else:
                depth_m = (znear * zfar) / (zfar - raw * (zfar - znear))
        return np.asarray(depth_m, dtype=np.float32)

    def _render_mujoco_depth_frame_locked(self, renderer: Any, camera_name: str) -> Any | None:
        if _mujoco is None or np is None or self._mj_data is None:
            return None

        self._configure_mujoco_depth_map_locked(renderer)
        renderer.disable_depth_rendering()
        renderer.update_scene(self._mj_data, camera=camera_name)

        scene = getattr(renderer, "_scene", None)
        rect = getattr(renderer, "_rect", None)
        context = getattr(renderer, "_mjr_context", None)
        if scene is None or rect is None or context is None:
            return None

        original_flags = scene.flags.copy()
        try:
            scene.flags[_mujoco.mjtRndFlag.mjRND_SEGMENT] = True
            scene.flags[_mujoco.mjtRndFlag.mjRND_IDCOLOR] = True

            gl_context = getattr(renderer, "_gl_context", None)
            if gl_context:
                gl_context.make_current()

            depth_buffer = np.empty((int(rect.height), int(rect.width)), dtype=np.float32)
            _mujoco.mjr_render(rect, scene, context)
            _mujoco.mjr_readPixels(None, depth_buffer, rect, context)

            if gl_context:
                depth_buffer[:] = np.flipud(depth_buffer)

            return self._convert_mujoco_depth_buffer_locked(
                depth_buffer,
                self._mujoco_depth_map_mode_locked(renderer),
            )
        finally:
            np.copyto(scene.flags, original_flags)

    def _build_stub_camera_frames_locked(self) -> tuple[Any | None, Any | None]:
        if np is None:
            return None, None

        rgb_h = max(1, int(self._rgb_stream["height"]))
        rgb_w = max(1, int(self._rgb_stream["width"]))
        depth_h = max(1, int(self._depth_stream["height"]))
        depth_w = max(1, int(self._depth_stream["width"]))

        # Stub frame carries simple gradients so callers can detect frame refresh.
        tick = int((self._sim_time * 100.0) % 255.0)
        rgb = np.zeros((rgb_h, rgb_w, 3), dtype=np.uint8)
        rgb[:, :, 0] = tick
        rgb[:, :, 1] = 120
        rgb[:, :, 2] = 64

        depth_mm = np.full((depth_h, depth_w), 900, dtype=np.uint16)
        return rgb, depth_mm

    def _validate_rgb_frame(self, frame: Any | None, missing: bool) -> tuple[bool, str | None]:
        if missing or frame is None:
            return False, "rgb_render_missing"
        if np is None:
            return False, "numpy_unavailable"
        arr = np.asarray(frame)
        expected_height = int(self._rgb_stream["height"])
        expected_width = int(self._rgb_stream["width"])
        if arr.ndim != 3 or arr.shape[2] < 3:
            return False, "rgb_shape_invalid"
        if arr.shape[0] != expected_height or arr.shape[1] != expected_width:
            return False, "rgb_resolution_mismatch"
        if arr.size == 0:
            return False, "rgb_empty"
        return True, None

    def _validate_depth_frame(self, frame: Any | None, missing: bool) -> tuple[bool, str | None]:
        if missing or frame is None:
            return False, "depth_render_missing"
        if np is None:
            return False, "numpy_unavailable"
        arr = np.asarray(frame)
        expected_height = int(self._depth_stream["height"])
        expected_width = int(self._depth_stream["width"])
        if arr.ndim != 2:
            return False, "depth_shape_invalid"
        if arr.shape[0] != expected_height or arr.shape[1] != expected_width:
            return False, "depth_resolution_mismatch"
        if arr.size == 0:
            return False, "depth_empty"
        if not np.isfinite(arr.astype(np.float32)).all():
            return False, "depth_non_finite"
        if int(np.max(arr)) <= 0:
            return False, "depth_all_zero"
        return True, None

    def _camera_source_ok(self) -> bool:
        return bool(
            self._camera_device == EXPECTED_CAMERA_DEVICE
            and str(self._rgb_stream.get("camera_name")) == EXPECTED_RGB_CAMERA_NAME
            and str(self._depth_stream.get("camera_name")) == EXPECTED_DEPTH_CAMERA_NAME
            and bool(self._camera_recordable_training_observation)
        )

    def _depth_storage_lossless_ok(self) -> bool:
        depth_format = str(self._depth_stream.get("dataset_storage_format", "")).strip().lower()
        image_storage_raw = self._dataset_schema.get("image_storage", {})
        image_storage = image_storage_raw if isinstance(image_storage_raw, dict) else {}
        depth_storage_raw = image_storage.get("depth", {})
        depth_storage = depth_storage_raw if isinstance(depth_storage_raw, dict) else {}
        allowed_depth_formats = depth_storage.get("allowed_formats", ["png16", "npy"])
        if not isinstance(allowed_depth_formats, list):
            allowed_depth_formats = ["png16", "npy"]
        allowed = {str(item).strip().lower() for item in allowed_depth_formats}
        return depth_format in allowed and depth_format not in {"jpg", "jpeg", "mp4"}

    def _build_camera_validation_summary(self, camera_state: dict[str, Any]) -> dict[str, Any]:
        camera_capture_ok = bool(camera_state.get("camera_capture_ok", False))
        camera_source_ok = bool(camera_state.get("camera_source_ok", False))
        frame_alignment_ok = bool(camera_state.get("frame_aligned", False))
        rgb_valid = bool(camera_state.get("rgb_valid", False))
        depth_valid = bool(camera_state.get("depth_valid", False))
        stub_frame_used = bool(camera_state.get("stub_frame_used", False))
        camera_view_ok = bool(camera_state.get("camera_view_ok", False))
        camera_view_status = str(camera_state.get("camera_view_status", "unchecked"))
        pending_human_hand_retest = True
        return {
            "camera_source_ok": camera_source_ok,
            "camera_capture_ok": camera_capture_ok,
            "camera_view_ok": camera_view_ok,
            "camera_view_status": camera_view_status,
            "frame_alignment_ok": frame_alignment_ok,
            "rgb_valid": rgb_valid,
            "depth_valid": depth_valid,
            "stub_frame_used": stub_frame_used,
            "depth_lossless_storage_ok": self._depth_storage_lossless_ok(),
            "mp4_preview_only": True,
            "ready_for_camera_only_smoke_test": bool(
                camera_source_ok and camera_capture_ok and frame_alignment_ok and not stub_frame_used
            ),
            "pending_human_hand_retest": pending_human_hand_retest,
            "last_error": camera_state.get("last_error"),
        }

    def _build_visuals_record_template(self, camera_state: dict[str, Any]) -> dict[str, Any]:
        frame_id = str(camera_state.get("d405_frame_id") or camera_state.get("frame_id") or "d405_000000")
        rgb_format = str(self._rgb_stream.get("dataset_storage_format", "jpg")).strip().lower() or "jpg"
        depth_format = str(self._depth_stream.get("dataset_storage_format", "png16")).strip().lower() or "png16"
        depth_ext = "png" if depth_format == "png16" else depth_format
        return {
            "timestamp": camera_state.get("timestamp"),
            "frame_id": frame_id,
            "d405_frame_id": frame_id,
            "rgb_path": f"rgb/{frame_id}.{rgb_format}",
            "depth_path": f"depth/{frame_id}.{depth_ext}",
            "rgb_timestamp": camera_state.get("rgb", {}).get("timestamp"),
            "depth_timestamp": camera_state.get("depth", {}).get("timestamp"),
            "frame_aligned": bool(camera_state.get("frame_aligned", False)),
            "camera_pose_in_ee": deepcopy(camera_state.get("camera_pose_in_ee", {})),
            "camera_pose_in_base": deepcopy(camera_state.get("camera_pose_in_base", {})),
            "rgb_missing": bool(camera_state.get("rgb", {}).get("missing", True)),
            "depth_missing": bool(camera_state.get("depth", {}).get("missing", True)),
            "rgb_valid": bool(camera_state.get("rgb_valid", False)),
            "depth_valid": bool(camera_state.get("depth_valid", False)),
            "camera_source_ok": bool(camera_state.get("camera_source_ok", False)),
            "stub_frame_used": bool(camera_state.get("stub_frame_used", False)),
            "visual_valid": bool(camera_state.get("camera_capture_ok", False)),
        }

    def _render_camera_frames_locked(self) -> tuple[Any | None, Any | None]:
        if (
            not self._using_mujoco_model()
            or self._mj_data is None
            or _mujoco is None
            or np is None
            or self._mj_rgb_camera_id < 0
            or self._mj_depth_camera_id < 0
        ):
            return None, None

        renderer = self._ensure_mujoco_renderer_locked()
        if renderer is None:
            return None, None

        rgb_camera_name = str(self._rgb_stream.get("camera_name", DEFAULT_RGB_STREAM["camera_name"]))
        depth_camera_name = str(self._depth_stream.get("camera_name", DEFAULT_DEPTH_STREAM["camera_name"]))
        try:
            renderer.disable_depth_rendering()
            renderer.update_scene(self._mj_data, camera=rgb_camera_name)
            rgb_frame = renderer.render()
            rgb_frame = np.ascontiguousarray(rgb_frame, dtype=np.uint8)

            depth_raw = self._render_mujoco_depth_frame_locked(renderer, depth_camera_name)

            if depth_raw is None:
                return None, None

            depth_arr = np.asarray(depth_raw)
            if depth_arr.ndim == 3:
                depth_arr = depth_arr[:, :, 0]
            depth_arr = np.clip(depth_arr.astype(np.float32) * 1000.0, 0.0, 65535.0)
            depth_mm = np.ascontiguousarray(depth_arr.astype(np.uint16))
            return rgb_frame, depth_mm
        except Exception:
            try:
                renderer.disable_depth_rendering()
            except Exception:
                pass
            return None, None

    def _compose_camera_pose_in_base_locked(self, ee_pose: dict[str, list[float]]) -> dict[str, list[float]]:
        return _compose_pose(
            parent_position_xyz=[float(v) for v in ee_pose["position"][:3]],
            parent_quaternion_wxyz=[float(v) for v in ee_pose["quaternion"][:4]],
            child_position_xyz=[float(v) for v in self._camera_pose_in_ee["position"][:3]],
            child_quaternion_wxyz=[float(v) for v in self._camera_pose_in_ee["quaternion"][:4]],
        )

    def _capture_camera_state_locked(
        self,
        force_capture: bool = False,
        ee_pose: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        if (
            not force_capture
            and self._camera_last_state is not None
            and (now - self._camera_last_capture_ts) < self._camera_capture_interval_s
        ):
            return deepcopy(self._camera_last_state)

        rgb_rendered, depth_rendered = self._render_camera_frames_locked()
        rgb_missing = rgb_rendered is None
        depth_missing = depth_rendered is None
        rgb_valid, rgb_error = self._validate_rgb_frame(rgb_rendered, rgb_missing)
        depth_valid, depth_error = self._validate_depth_frame(depth_rendered, depth_missing)
        stub_frame_used = bool(rgb_missing or depth_missing)
        if rgb_missing or depth_missing:
            stub_rgb, stub_depth = self._build_stub_camera_frames_locked()
            if rgb_rendered is None:
                rgb_rendered = stub_rgb
            if depth_rendered is None:
                depth_rendered = stub_depth

        if ee_pose is None:
            ee_pose = self._compute_ee_pose_locked()
        camera_pose_in_base = self._compose_camera_pose_in_base_locked(ee_pose)

        rgb_timestamp = float(now)
        if self._camera_alignment_mode == "same_tick":
            depth_timestamp = float(now)
        else:
            depth_timestamp = float(now + min(0.001, self._camera_alignment_max_delta_ms / 1000.0))

        alignment_error_ms = abs(rgb_timestamp - depth_timestamp) * 1000.0
        frame_aligned = alignment_error_ms <= self._camera_alignment_max_delta_ms

        self._camera_frame_counter += 1
        frame_id = f"d405_{self._camera_frame_counter:06d}"
        self._stats["camera_frames"] = int(self._stats.get("camera_frames", 0)) + 1

        if np is not None and rgb_rendered is not None:
            self._camera_last_rgb_frame = np.ascontiguousarray(rgb_rendered, dtype=np.uint8)
        else:
            self._camera_last_rgb_frame = None

        if np is not None and depth_rendered is not None:
            self._camera_last_depth_frame = np.ascontiguousarray(depth_rendered, dtype=np.uint16)
        else:
            self._camera_last_depth_frame = None

        camera_source_ok = self._camera_source_ok()
        camera_capture_ok = bool(camera_source_ok and rgb_valid and depth_valid and frame_aligned and not stub_frame_used)
        if not camera_capture_ok:
            self._stats["camera_drops"] = int(self._stats.get("camera_drops", 0)) + 1
        error_reasons = [
            reason
            for reason in [
                None if camera_source_ok else "camera_source_not_d405_primary",
                rgb_error,
                depth_error,
                None if frame_aligned else "rgb_depth_frame_misaligned",
                "stub_frame_used" if stub_frame_used else None,
                None if self._camera_recordable_training_observation else "camera_not_recordable",
            ]
            if reason
        ]
        last_error = ";".join(error_reasons) if error_reasons else None
        camera_view_status = "pending_camera_only_smoke_test" if camera_capture_ok else "capture_invalid"

        camera_state: dict[str, Any] = {
            "timestamp": float(now),
            "device": self._camera_device,
            "mount_name": self._camera_mount_name,
            "mount_parent_frame": self._camera_mount_parent_frame,
            "camera_intrinsics_version": self._camera_intrinsics_version,
            "camera_extrinsics_version": self._camera_extrinsics_version,
            "frame_id": frame_id,
            "d405_frame_id": frame_id,
            "frame_aligned": frame_aligned,
            "alignment_mode": self._camera_alignment_mode,
            "max_alignment_error_ms": float(self._camera_alignment_max_delta_ms),
            "recordable_training_observation": bool(self._camera_recordable_training_observation),
            "camera_capture_ok": camera_capture_ok,
            "camera_source_ok": camera_source_ok,
            "rgb_valid": rgb_valid,
            "depth_valid": depth_valid,
            "stub_frame_used": stub_frame_used,
            "camera_view_ok": False,
            "camera_view_status": camera_view_status,
            "last_error": last_error,
            "debug_only_objects": list(self._camera_debug_only_objects),
            "camera_pose_in_ee": {
                "position": [float(v) for v in self._camera_pose_in_ee["position"]],
                "quaternion": [float(v) for v in self._camera_pose_in_ee["quaternion"]],
            },
            "camera_pose_in_base": {
                "position": [float(v) for v in camera_pose_in_base["position"]],
                "quaternion": [float(v) for v in camera_pose_in_base["quaternion"]],
            },
            "rgb": {
                "interface_name": str(self._rgb_stream["interface_name"]),
                "camera_name": str(self._rgb_stream["camera_name"]),
                "width": int(self._rgb_stream["width"]),
                "height": int(self._rgb_stream["height"]),
                "fps": float(self._rgb_stream["fps"]),
                "pixel_format": str(self._rgb_stream["pixel_format"]),
                "dataset_storage_format": str(self._rgb_stream["dataset_storage_format"]),
                "timestamp": rgb_timestamp,
                "missing": bool(rgb_missing),
                "valid": rgb_valid,
                "error_reason": rgb_error,
            },
            "depth": {
                "interface_name": str(self._depth_stream["interface_name"]),
                "camera_name": str(self._depth_stream["camera_name"]),
                "width": int(self._depth_stream["width"]),
                "height": int(self._depth_stream["height"]),
                "fps": float(self._depth_stream["fps"]),
                "pixel_format": str(self._depth_stream["pixel_format"]),
                "dataset_storage_format": str(self._depth_stream["dataset_storage_format"]),
                "timestamp": depth_timestamp,
                "missing": bool(depth_missing),
                "valid": depth_valid,
                "error_reason": depth_error,
                "depth_unit": str(self._depth_stream.get("depth_unit", "millimeter")),
                "depth_scale": float(self._depth_stream.get("depth_scale", 1.0)),
            },
        }

        self._camera_last_state = camera_state
        self._camera_last_capture_ts = now
        return camera_state

    def _build_camera_frame_data_locked(self) -> dict[str, Any]:
        if np is None or self._camera_last_rgb_frame is None or self._camera_last_depth_frame is None:
            return {
                "rgb_data": None,
                "depth_data": None,
            }

        rgb_bytes = np.ascontiguousarray(self._camera_last_rgb_frame, dtype=np.uint8).tobytes()
        depth_bytes = np.ascontiguousarray(self._camera_last_depth_frame, dtype=np.uint16).tobytes()
        return {
            "rgb_data": {
                "encoding": "base64_raw_rgb8",
                "byte_count": len(rgb_bytes),
                "data_base64": base64.b64encode(rgb_bytes).decode("ascii"),
            },
            "depth_data": {
                "encoding": "base64_raw_depth16_mm",
                "byte_count": len(depth_bytes),
                "data_base64": base64.b64encode(depth_bytes).decode("ascii"),
            },
        }

    def _build_camera_observation_locked(self, include_data: bool = False) -> dict[str, Any]:
        camera_state = self._capture_camera_state_locked(force_capture=include_data)
        alignment_rules_raw = self._dataset_schema.get("alignment_rules", {})
        alignment_rules = alignment_rules_raw if isinstance(alignment_rules_raw, dict) else {}
        validation_summary = self._build_camera_validation_summary(camera_state)
        visuals_record_template = self._build_visuals_record_template(camera_state)
        observation: dict[str, Any] = {
            "timestamp": time.time(),
            "frame_id": camera_state.get("frame_id"),
            "d405_frame_id": camera_state.get("d405_frame_id"),
            "camera_device": camera_state.get("device"),
            "camera_mount_name": camera_state.get("mount_name"),
            "camera_intrinsics_version": camera_state.get("camera_intrinsics_version"),
            "camera_extrinsics_version": camera_state.get("camera_extrinsics_version"),
            "camera_source_ok": camera_state.get("camera_source_ok", False),
            "camera_capture_ok": camera_state.get("camera_capture_ok", False),
            "frame_aligned": camera_state.get("frame_aligned", False),
            "recordable_training_observation": camera_state.get("recordable_training_observation", False),
            "rgb_valid": camera_state.get("rgb_valid", False),
            "depth_valid": camera_state.get("depth_valid", False),
            "stub_frame_used": camera_state.get("stub_frame_used", False),
            "camera_view_ok": camera_state.get("camera_view_ok", False),
            "camera_view_status": camera_state.get("camera_view_status", "unchecked"),
            "last_error": camera_state.get("last_error"),
            "rgb": dict(camera_state.get("rgb", {})),
            "depth": dict(camera_state.get("depth", {})),
            "camera_pose_in_ee": deepcopy(camera_state.get("camera_pose_in_ee", {})),
            "camera_pose_in_base": deepcopy(camera_state.get("camera_pose_in_base", {})),
            "dataset_schema_version": self._dataset_schema.get("dataset_schema_version"),
            "handover_zones": deepcopy(self._handover_zones),
            "camera_smoke_test_plan": deepcopy(self._camera_smoke_test_plan),
            "validation_summary": validation_summary,
            "visuals_record_template": visuals_record_template,
            "paired_frame_required_for_each_action": bool(
                alignment_rules.get("paired_frame_required_for_each_action", True)
            ),
            "instruction_text_required_in_metadata_and_step": bool(
                alignment_rules.get("instruction_text_required_in_metadata_and_step", True)
            ),
            "camera": camera_state,
        }
        if include_data:
            observation.update(self._build_camera_frame_data_locked())
        return observation

    def _build_state_locked(self, refresh_camera: bool = True) -> dict[str, Any]:
        if self._using_mujoco_model() and self._mj_data is not None:
            arm_qpos = []
            arm_qvel = []
            for idx, name in enumerate(self._arm_joint_names):
                qpos_addr = self._arm_joint_qpos_addr.get(name)
                qvel_addr = self._arm_joint_qvel_addr.get(name)
                if qpos_addr is None:
                    arm_qpos.append(self._arm_qpos[idx])
                else:
                    arm_qpos.append(float(self._mj_data.qpos[qpos_addr]))
                if qvel_addr is None:
                    arm_qvel.append(self._arm_qvel[idx] if idx < len(self._arm_qvel) else 0.0)
                else:
                    arm_qvel.append(float(self._mj_data.qvel[qvel_addr]))
            self._arm_qpos = arm_qpos
            self._arm_qvel = arm_qvel
            self._update_grasp_assist_locked(forward=True)
            self._objects_state = self._collect_objects_state_locked()

            # Keep exported gripper state aligned with current MuJoCo qpos
            # (including external viewer/manual manipulations) without touching arm velocity caches.
            gripper_joints: dict[str, float] = {}
            for name in DEFAULT_GRIPPER_JOINT_NAMES:
                qpos_addr = self._gripper_joint_qpos_addr.get(name)
                if qpos_addr is None:
                    continue
                gripper_joints[name] = float(self._mj_data.qpos[qpos_addr])

            if gripper_joints:
                left_driver = gripper_joints.get(
                    "left_driver_joint",
                    float(self._gripper_joints.get("left_driver_joint", 0.0)),
                )
                self._gripper_opening = _clamp(left_driver / GRIPPER_DRIVER_LIMIT, 0.0, 1.0)
                left_driver_qvel_addr = self._gripper_joint_qvel_addr.get("left_driver_joint")
                if left_driver_qvel_addr is not None:
                    self._gripper_velocity = float(self._mj_data.qvel[left_driver_qvel_addr]) / max(
                        GRIPPER_DRIVER_LIMIT,
                        1e-8,
                    )
                default_mapping = self._map_gripper_joints(self._gripper_opening)
                for name, value in default_mapping.items():
                    gripper_joints.setdefault(name, float(value))
                self._gripper_joints = gripper_joints

        gripper_driver = float(self._gripper_joints["left_driver_joint"])
        qpos = list(self._arm_qpos) + [gripper_driver]
        qvel = list(self._arm_qvel) + [self._gripper_velocity]
        arm_ctrl_qpos, gripper_ctrl_opening = self._read_current_ctrl_targets_locked()
        ee_pose = self._compute_ee_pose_locked()
        control_ee_pose = self._build_control_ee_pose_locked()
        if refresh_camera:
            camera_state = self._capture_camera_state_locked(force_capture=False, ee_pose=ee_pose)
        elif self._camera_last_state is not None:
            camera_state = deepcopy(self._camera_last_state)
        else:
            # Initialize camera snapshot once so lightweight broadcasts can reuse it.
            camera_state = self._capture_camera_state_locked(force_capture=False, ee_pose=ee_pose)
        camera_validation_summary = self._build_camera_validation_summary(camera_state)
        camera_observation = {
            "d405_frame_id": camera_state.get("d405_frame_id"),
            "timestamp": camera_state.get("timestamp"),
            "camera_device": camera_state.get("device"),
            "camera_mount_name": camera_state.get("mount_name"),
            "camera_source_ok": bool(camera_state.get("camera_source_ok", False)),
            "camera_capture_ok": bool(camera_state.get("camera_capture_ok", False)),
            "rgb_valid": bool(camera_state.get("rgb_valid", False)),
            "depth_valid": bool(camera_state.get("depth_valid", False)),
            "frame_aligned": bool(camera_state.get("frame_aligned", False)),
            "stub_frame_used": bool(camera_state.get("stub_frame_used", False)),
            "camera_view_ok": bool(camera_state.get("camera_view_ok", False)),
            "camera_view_status": str(camera_state.get("camera_view_status", "unchecked")),
            "last_error": camera_state.get("last_error"),
            "validation_summary": camera_validation_summary,
        }
        return {
            "timestamp": time.time(),
            "sim_time": self._sim_time,
            "joint_names": list(self._arm_joint_names),
            "joint_limits": {
                name: [float(limits[0]), float(limits[1])]
                for name, limits in self._arm_joint_limits.items()
            },
            "qpos": qpos,
            "qvel": qvel,
            "arm_target_qpos": list(self._arm_command_qpos),
            "arm_ctrl_qpos": list(arm_ctrl_qpos),
            "gripper_target_opening": float(self._gripper_command_opening),
            "gripper_ctrl_opening": float(gripper_ctrl_opening),
            "ee_pose": ee_pose,
            "control_ee_pose": control_ee_pose,
            "gripper_opening": self._gripper_opening,
            "gripper_joints": dict(self._gripper_joints),
            "objects": deepcopy(self._objects_state),
            "handover_zones": deepcopy(self._handover_zones),
            "camera": camera_state,
            "camera_capture_ok": bool(camera_state.get("camera_capture_ok", False)),
            "d405_frame_id": camera_state.get("d405_frame_id"),
            "camera_observation": camera_observation,
            "task_state": dict(self._task_state),
            "source": self._source,
            "input_source": self._last_input_source,
            "selected_joint_group": self._last_selected_joint_group,
            "raw_input": deepcopy(self._last_raw_input),
            "normalized_input": deepcopy(self._last_normalized_input),
            "safety_status": self._safety_status,
            "collision_blocked": bool(self._collision_blocked),
            "collision_contacts": deepcopy(self._last_collision_contacts),
            "vr": deepcopy(self._vr_state),
            "stats": {
                "steps": int(self._stats["steps"]),
                "commands": int(self._stats["commands"]),
                "last_step_ms": float(self._stats["last_step_ms"]),
                "avg_step_ms": float(self._stats["avg_step_ms"]),
                "camera_frames": int(self._stats.get("camera_frames", 0)),
                "camera_drops": int(self._stats.get("camera_drops", 0)),
            },
        }

    def _build_broadcast_state_locked(self) -> dict[str, Any]:
        state = self._build_state_locked(refresh_camera=False)
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        camera_summary = {
            "timestamp": camera.get("timestamp"),
            "device": camera.get("device"),
            "camera_intrinsics_version": camera.get("camera_intrinsics_version"),
            "camera_extrinsics_version": camera.get("camera_extrinsics_version"),
            "frame_id": camera.get("frame_id"),
            "d405_frame_id": camera.get("d405_frame_id"),
            "frame_aligned": camera.get("frame_aligned"),
            "recordable_training_observation": camera.get("recordable_training_observation"),
            "camera_capture_ok": camera.get("camera_capture_ok"),
            "camera_source_ok": camera.get("camera_source_ok"),
            "rgb_valid": camera.get("rgb_valid"),
            "depth_valid": camera.get("depth_valid"),
            "stub_frame_used": camera.get("stub_frame_used"),
            "camera_view_ok": camera.get("camera_view_ok"),
            "camera_view_status": camera.get("camera_view_status"),
            "last_error": camera.get("last_error"),
            "rgb": {
                "interface_name": camera.get("rgb", {}).get("interface_name") if isinstance(camera.get("rgb"), dict) else None,
                "camera_name": camera.get("rgb", {}).get("camera_name") if isinstance(camera.get("rgb"), dict) else None,
                "fps": camera.get("rgb", {}).get("fps") if isinstance(camera.get("rgb"), dict) else None,
            },
            "depth": {
                "interface_name": camera.get("depth", {}).get("interface_name") if isinstance(camera.get("depth"), dict) else None,
                "camera_name": camera.get("depth", {}).get("camera_name") if isinstance(camera.get("depth"), dict) else None,
                "fps": camera.get("depth", {}).get("fps") if isinstance(camera.get("depth"), dict) else None,
            },
        }
        return {
            "timestamp": state["timestamp"],
            "sim_time": state["sim_time"],
            "objects": state["objects"],
            "camera": camera_summary,
            "camera_capture_ok": state.get("camera_capture_ok", False),
            "d405_frame_id": state.get("d405_frame_id"),
            "task_state": state["task_state"],
            "source": state["source"],
            "input_source": state.get("input_source"),
            "selected_joint_group": state.get("selected_joint_group"),
            "raw_input": state.get("raw_input"),
            "normalized_input": state.get("normalized_input"),
            "safety_status": state.get("safety_status", "normal"),
            "collision_blocked": bool(state.get("collision_blocked", False)),
            "collision_contacts": state.get("collision_contacts", []),
            "vr": state.get("vr", {}),
            "stats": state.get("stats", {}),
        }

    def _build_motion_state_locked(self) -> dict[str, Any]:
        arm_ctrl_qpos, gripper_ctrl_opening = self._read_current_ctrl_targets_locked()
        ee_pose = self._compute_ee_pose_locked()
        collision_blocked = bool(self._collision_blocked)
        normalized_input = self._last_normalized_input if isinstance(self._last_normalized_input, dict) else {}
        motion_normalized_input = {
            key: deepcopy(normalized_input[key])
            for key in (
                "control_seq",
                "control_mode",
                "hand_input_mode",
                "cartesian_servo_active",
                "cartesian_servo_status",
                "cartesian_servo_position_error_m",
                "cartesian_servo_orientation_error_rad",
                "ee_active",
                "ee_hold",
                "orientation_follow_enabled",
            )
            if key in normalized_input
        }
        payload: dict[str, Any] = {
            "timestamp": time.time(),
            "sim_time": self._sim_time,
            "qpos": list(self._arm_qpos) + [float(self._gripper_joints["left_driver_joint"])],
            "qvel": list(self._arm_qvel) + [float(self._gripper_velocity)],
            "arm_target_qpos": list(self._arm_command_qpos),
            "arm_ctrl_qpos": list(arm_ctrl_qpos),
            "gripper_target_opening": float(self._gripper_command_opening),
            "gripper_ctrl_opening": float(gripper_ctrl_opening),
            "ee_pose": ee_pose,
            "control_ee_pose": self._build_control_ee_pose_locked(),
            "gripper_opening": float(self._gripper_opening),
            "gripper_joints": dict(self._gripper_joints),
            "source": self._source,
            "input_source": self._last_input_source,
            "selected_joint_group": self._last_selected_joint_group,
            "normalized_input": motion_normalized_input,
            "safety_status": self._safety_status,
            "collision_blocked": collision_blocked,
            "collision_contacts": deepcopy(self._last_collision_contacts) if collision_blocked else [],
        }
        return payload

    async def _command_worker(self) -> None:
        while self._running:
            try:
                queued = await self._command_queue.get()
            except asyncio.CancelledError:
                break

            source_key = self._realtime_queue_source_key(queued.request) if not queued.return_state else None
            if source_key is not None and self._pending_realtime_commands_by_source.get(source_key) is queued:
                self._pending_realtime_commands_by_source.pop(source_key, None)

            if queued.future.cancelled():
                self._command_queue.task_done()
                continue

            try:
                if self._is_stale_realtime_command(queued.request):
                    if not queued.future.done():
                        queued.future.set_result(
                            {
                                "timestamp": time.time(),
                                "sim_time": self._sim_time,
                                "source": queued.request.source,
                                "selected_joint_group": self._last_selected_joint_group,
                                "input_source": self._last_input_source,
                                "status": "dropped_stale_seq",
                            }
                        )
                    continue
                state = await self.step(queued.request, return_state=queued.return_state)
                if not queued.future.done():
                    queued.future.set_result(state)
            except Exception as exc:
                if not queued.future.done():
                    queued.future.set_exception(exc)
            finally:
                self._command_queue.task_done()

    def _realtime_queue_source_key(self, request: StepRequest) -> str | None:
        return self._realtime_state_source_key(
            getattr(request, "source", None),
            getattr(request, "input_source", None),
        )

    def _realtime_state_source_key(
        self,
        source: str | None,
        input_source: str | None,
    ) -> str | None:
        normalized_source = str(source or "").strip().lower()
        normalized_input = str(input_source or "").strip().lower()
        if normalized_source in {"quest3_controller", "quest3_hand"}:
            return normalized_source
        if normalized_source in {"manual", "desktop_manual"} and normalized_input in {
            "slider",
            "joint_slider",
            "slider_commit",
        }:
            return "desktop_manual_slider"
        return None

    def _extract_realtime_command_seq(self, request: StepRequest) -> tuple[str, int] | None:
        """
        Return (source_key, sequence) for realtime commands that carry an
        anti-replay sequence number.
        """
        source_key = self._realtime_queue_source_key(request)
        if source_key is None:
            return None

        normalized = request.normalized_input
        if not isinstance(normalized, dict):
            return None

        seq_raw = normalized.get("control_seq")
        try:
            seq = int(seq_raw)
        except (TypeError, ValueError):
            return None

        return source_key, seq

    def _remember_realtime_command_seq(self, request: StepRequest) -> None:
        seq_info = self._extract_realtime_command_seq(request)
        if seq_info is None:
            return
        source, seq = seq_info
        latest = int(self._latest_realtime_seq_by_source.get(source, -1))
        if seq > latest:
            self._latest_realtime_seq_by_source[source] = seq

    def _is_stale_realtime_command(self, request: StepRequest) -> bool:
        """
        Realtime control anti-replay:
        if request.normalized_input.control_seq is older than the latest enqueued
        command for the same source, drop it to avoid delayed rollback.
        """
        seq_info = self._extract_realtime_command_seq(request)
        if seq_info is None:
            return False

        source, seq = seq_info
        latest = int(self._latest_realtime_seq_by_source.get(source, -1))
        if seq < latest:
            return True
        if seq > latest:
            self._latest_realtime_seq_by_source[source] = seq
        return False
