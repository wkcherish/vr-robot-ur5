from __future__ import annotations

import asyncio
import base64
import json
import math
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
GRIPPER_DRIVER_LIMIT = 0.87
ARM_COMMAND_BLEND_PER_STEP = 0.12
GRIPPER_COMMAND_BLEND_PER_STEP = 0.16
TOOL_FRAME_CANDIDATES = ["tool0", "wrist_3_link"]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MUJOCO_MODEL_PATH = REPO_ROOT / "backend" / "mujoco_models" / "environment.xml"
DEFAULT_CAMERA_SENSOR_CONFIG_PATH = REPO_ROOT / "shared" / "camera_sensor_config.json"
DEFAULT_DATASET_SCHEMA_PATH = REPO_ROOT / "shared" / "dataset_schema.json"
BACKEND_FRAME_Z_OFFSET = 0.5
BACKEND_ALIGNMENT_QUATERNION = [math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0]
MAX_ALLOWED_PENETRATION_M = 8e-4
MAX_COLLISION_REPORTS = 3
DEFAULT_CAMERA_MOUNT_POSITION = [0.0, -0.077929684, 0.055]
DEFAULT_CAMERA_MOUNT_QUATERNION = [1.0, 0.0, 0.0, 0.0]
DEFAULT_RGB_STREAM = {
    "interface_name": "sim_camera_rgb",
    "camera_name": "d405_rgb",
    "width": 640,
    "height": 480,
    "fps": 30.0,
    "pixel_format": "rgb8",
    "dataset_storage_format": "jpg",
}
DEFAULT_DEPTH_STREAM = {
    "interface_name": "sim_camera_depth",
    "camera_name": "d405_depth",
    "width": 640,
    "height": 480,
    "fps": 30.0,
    "pixel_format": "depth16",
    "dataset_storage_format": "png16",
    "depth_unit": "millimeter",
    "depth_scale": 1.0,
}
DEFAULT_CAMERA_ALIGNMENT_MODE = "same_tick"
DEFAULT_CAMERA_ALIGNMENT_MAX_DELTA_MS = 5.0
DEFAULT_CAMERA_DEBUG_OBJECTS = ["camera_base", "camera"]
REALTIME_SOURCE_MIN_PHYSICS_HORIZON_S = 0.02
REALTIME_COMMAND_BLEND_PER_STEP = 1.0
REALTIME_ARM_MAX_DELTA_RAD = 0.12
REALTIME_GRIPPER_MAX_DELTA_OPENING = 0.12
REALTIME_EE_MAX_DELTA_M = 0.055
IK_MAX_ITERATIONS = 8
IK_POSITION_TOLERANCE_M = 0.003
IK_ORIENTATION_TOLERANCE_RAD = 0.055
IK_DAMPING = 0.08
IK_MAX_STEP_RAD = 0.12
IK_POSITION_WEIGHT = 1.0
IK_ORIENTATION_WEIGHT = 0.35
GRIPPER_GRASP_ENGAGE_OPENING = 0.52
GRIPPER_GRASP_RELEASE_OPENING = 0.18
GRIPPER_GRASP_ATTACH_RADIUS_M = 0.20
GRIPPER_GRASP_CONTACT_MARGIN_M = 0.015
GRIPPER_GRASP_PAD_BODY_NAMES = ("left_pad_link", "right_pad_link")
SCENE_SETTLE_STEPS = 1000


@dataclass
class _QueuedCommand:
    request: StepRequest
    future: asyncio.Future[dict[str, Any]]
    return_state: bool = True


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


def _resolve_command_blend(source: str, n_steps: int, per_step_blend: float) -> float:
    """
    VR teleop sources are already incremental, but LAN delivery can be bursty.
    Blend them over the physics horizon so the actuator target advances without
    snapping back and forth when an older broadcast arrives late.
    """
    normalized = str(source or "").strip().lower()
    if normalized in {"quest3_controller", "quest3_hand"}:
        return _compute_command_blend(n_steps, REALTIME_COMMAND_BLEND_PER_STEP)
    return _compute_command_blend(n_steps, per_step_blend)


def _is_realtime_source(source: str) -> bool:
    normalized = str(source or "").strip().lower()
    return normalized in {"quest3_controller", "quest3_hand"}


def _resolve_physics_steps(source: str, requested_steps: int, dt: float) -> int:
    base_steps = max(1, int(requested_steps))
    normalized = str(source or "").strip().lower()
    if normalized not in {"quest3_controller", "quest3_hand"}:
        return base_steps
    stable_dt = max(1e-4, float(dt))
    min_steps = max(1, int(round(REALTIME_SOURCE_MIN_PHYSICS_HORIZON_S / stable_dt)))
    return max(base_steps, min_steps)


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
        self._object_reset_policy: dict[str, dict[str, Any]] = {}
        self._spawn_regions: dict[str, dict[str, Any]] = {}
        self._camera_sensor_config_path: str | None = None
        self._dataset_schema_path: str | None = None
        self._dataset_schema: dict[str, Any] = {}
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
        self._arm_actuator_ctrl_offsets: dict[str, float] = {}
        self._gripper_driver_actuator_id: int | None = None
        self._object_body_ids: dict[str, int] = {}
        self._object_freejoint_qpos_addr: dict[str, int] = {}
        self._object_freejoint_dof_addr: dict[str, int] = {}
        self._gripper_body_ids: dict[str, int] = {}
        self._tool_body_id: int | None = None
        self._mj_rgb_camera_id: int = -1
        self._mj_depth_camera_id: int = -1
        self._mj_renderer: Any | None = None
        self._mj_renderer_width = 0
        self._mj_renderer_height = 0

        self._arm_qpos = list(DEFAULT_HOME_QPOS)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
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

    def queue_step(self, request: StepRequest, return_state: bool = True) -> asyncio.Future[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._remember_realtime_command_seq(request)
        self._command_queue.put_nowait(
            _QueuedCommand(
                request=request,
                future=future,
                return_state=bool(return_state),
            )
        )
        return future

    async def enqueue_step(self, request: StepRequest, return_state: bool = True) -> dict[str, Any]:
        future = self.queue_step(request, return_state=return_state)
        return await future

    async def step(self, request: StepRequest, return_state: bool = True) -> dict[str, Any]:
        async with self._lock:
            started_at = perf_counter()

            target_positions = request.target_positions

            snapshot: dict[str, Any] = {
                "arm_qpos": list(self._arm_qpos),
                "arm_qvel": list(self._arm_qvel),
                "gripper_opening": float(self._gripper_opening),
                "gripper_velocity": float(self._gripper_velocity),
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

            self._source = request.source
            self._last_input_source = (
                str(request.input_source).strip() if request.input_source is not None else None
            )
            self._last_selected_joint_group = (
                str(request.selected_joint_group).strip()
                if request.selected_joint_group is not None
                else None
            )
            self._last_raw_input = dict(request.raw_input) if isinstance(request.raw_input, dict) else None
            self._last_normalized_input = (
                dict(request.normalized_input) if isinstance(request.normalized_input, dict) else None
            )
            if request.source == "quest3_controller":
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
            physics_steps = _resolve_physics_steps(self._source, requested_steps, self._dt)
            self._apply_arm_command(target_positions, physics_steps, self._source)
            self._apply_gripper_command(request.gripper_command, physics_steps, self._source)
            self._update_grasp_assist_locked(forward=True)

            forbidden_contacts: list[dict[str, Any]] = []
            if self._using_mujoco_model() and self._mj_model is not None and self._mj_data is not None and _mujoco is not None:
                start_qpos = snapshot.get("mj_qpos")
                start_qvel = snapshot.get("mj_qvel")
                if start_qpos is not None and start_qvel is not None:
                    last_safe_qpos = start_qpos.copy()
                    last_safe_qvel = start_qvel.copy()
                    for _ in range(physics_steps):
                        self._set_mujoco_gripper_kinematic_state_locked(
                            self._gripper_opening,
                            self._gripper_velocity,
                        )
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

                    self._set_mujoco_gripper_kinematic_state_locked(
                        self._gripper_opening,
                        self._gripper_velocity,
                        forward=True,
                    )
                    self._sync_internal_state_from_mujoco_locked()
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
            self._sim_time += physics_steps * self._dt
            self._stats["steps"] += physics_steps
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

    async def reset(self, model_path: str | None = None) -> dict[str, Any]:
        async with self._lock:
            self._load_model(model_path)
            self._reset_state_locked()
            return self._build_state_locked()

    async def get_state(self, refresh_camera: bool = True) -> dict[str, Any]:
        async with self._lock:
            return self._build_state_locked(refresh_camera=refresh_camera)

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
                "camera_device": observation.get("camera_device"),
                "camera_mount_name": observation.get("camera_mount_name"),
                "camera_capture_ok": observation.get("camera_capture_ok", False),
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

    def _frontend_to_backend_position(self, frontend_position: list[float]) -> list[float]:
        x_frontend, y_frontend, z_frontend = frontend_position
        return [x_frontend, -z_frontend, y_frontend + BACKEND_FRAME_Z_OFFSET]

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
        self._arm_actuator_ctrl_offsets = {}
        self._gripper_driver_actuator_id = None
        self._object_body_ids = {}
        self._object_freejoint_qpos_addr = {}
        self._object_freejoint_dof_addr = {}
        self._gripper_body_ids = {}
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
        self._arm_actuator_ctrl_offsets = {}
        for actuator_name in DEFAULT_ARM_ACTUATOR_NAMES:
            actuator_id = _mujoco.mj_name2id(model, _mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id >= 0:
                self._arm_actuator_ids[actuator_name] = int(actuator_id)
                actuator_index = len(self._arm_actuator_ctrl_offsets)
                if actuator_index < len(self._arm_joint_names):
                    joint_name = self._arm_joint_names[actuator_index]
                    qpos_addr = self._arm_joint_qpos_addr.get(joint_name)
                    if qpos_addr is not None:
                        self._arm_actuator_ctrl_offsets[actuator_name] = float(model.qpos0[qpos_addr])
                    else:
                        self._arm_actuator_ctrl_offsets[actuator_name] = 0.0

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

        self._tool_body_id = None
        for candidate in TOOL_FRAME_CANDIDATES:
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
        # Tool contacts are expected during grasping and placement.
        if body_name_a in TOOL_BODY_NAMES or body_name_b in TOOL_BODY_NAMES:
            return True
        # Gripper internal contacts can appear near full close and are not safety-critical.
        if body_name_a in GRIPPER_BODY_NAMES and body_name_b in GRIPPER_BODY_NAMES:
            return True
        return False

    def _collect_forbidden_contacts_locked(self) -> list[dict[str, Any]]:
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

        if not self._using_mujoco_model() or self._mj_data is None or _mujoco is None or self._mj_model is None:
            return

        qpos_snapshot = snapshot.get("mj_qpos")
        qvel_snapshot = snapshot.get("mj_qvel")
        ctrl_snapshot = snapshot.get("mj_ctrl")
        if qpos_snapshot is not None:
            self._mj_data.qpos[:] = qpos_snapshot
        if qvel_snapshot is not None:
            self._mj_data.qvel[:] = qvel_snapshot
        if ctrl_snapshot is not None:
            self._mj_data.ctrl[:] = ctrl_snapshot
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

    def _set_mujoco_gripper_kinematic_state_locked(
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

        if forward and _mujoco is not None:
            _mujoco.mj_forward(self._mj_model, self._mj_data)

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
        if self._using_mujoco_model() and self._mj_data is not None:
            pad_positions: list[list[float]] = []
            for name in GRIPPER_GRASP_PAD_BODY_NAMES:
                body_id = self._gripper_body_ids.get(name)
                if body_id is not None:
                    pad_positions.append([float(v) for v in self._mj_data.xpos[body_id]])

            if pad_positions:
                inv_count = 1.0 / len(pad_positions)
                position = [
                    sum(pad_position[axis] for pad_position in pad_positions) * inv_count
                    for axis in range(3)
                ]
                if self._tool_body_id is not None:
                    quaternion = [float(v) for v in self._mj_data.xquat[self._tool_body_id]]
                else:
                    first_pad_id = self._gripper_body_ids.get(GRIPPER_GRASP_PAD_BODY_NAMES[0])
                    quaternion = (
                        [float(v) for v in self._mj_data.xquat[first_pad_id]]
                        if first_pad_id is not None
                        else [1.0, 0.0, 0.0, 0.0]
                    )
                return {
                    "position": position,
                    "quaternion": _normalize_quaternion(quaternion),
                }

        return self._compute_ee_pose_locked()

    def _clear_grasp_attachment_locked(self) -> None:
        if self._attached_object_id in self._scene_objects_template:
            self._scene_objects_template[self._attached_object_id]["attached_to_gripper"] = False
        self._attached_object_id = None
        self._attached_object_rel_position = None
        self._attached_object_rel_quaternion = None

    def _find_nearest_graspable_object_locked(
        self,
        grasp_pose: dict[str, list[float]],
    ) -> tuple[str | None, float]:
        grasp_position = grasp_pose.get("position", [0.0, 0.0, 0.0])
        nearest_id: str | None = None
        nearest_distance = float("inf")
        for obj_id in GRASPABLE_TOOL_BODY_NAMES:
            pose = self._get_object_pose_locked(obj_id)
            if pose is None:
                continue
            position = pose["position"]
            distance = math.sqrt(
                (position[0] - grasp_position[0]) ** 2
                + (position[1] - grasp_position[1]) ** 2
                + (position[2] - grasp_position[2]) ** 2
            )
            if distance < nearest_distance:
                nearest_id = obj_id
                nearest_distance = distance

        if nearest_distance > GRIPPER_GRASP_ATTACH_RADIUS_M:
            return None, nearest_distance
        return nearest_id, nearest_distance

    def _find_contacted_graspable_object_locked(self) -> str | None:
        if not self._using_mujoco_model() or self._mj_model is None or self._mj_data is None or _mujoco is None:
            return None

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

            if body_name_a in GRASPABLE_TOOL_BODY_NAMES and body_name_b in GRIPPER_BODY_NAMES:
                return body_name_a
            if body_name_b in GRASPABLE_TOOL_BODY_NAMES and body_name_a in GRIPPER_BODY_NAMES:
                return body_name_b

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
            graspable_id, _ = self._find_nearest_graspable_object_locked(grasp_pose)
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

    def _reset_state_locked(self) -> None:
        self._arm_qpos = list(self._home_arm_qpos)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
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
                    offset = self._arm_actuator_ctrl_offsets.get(actuator_name, 0.0)
                    self._mj_data.ctrl[actuator_id] = float(self._home_arm_qpos[idx]) - offset
            if self._gripper_driver_actuator_id is not None:
                self._mj_data.ctrl[self._gripper_driver_actuator_id] = float(
                    self._gripper_joints.get("left_driver_joint", 0.0)
                )
            self._set_mujoco_gripper_kinematic_state_locked(
                self._gripper_opening,
                self._gripper_velocity,
                forward=True,
            )
            _mujoco.mj_forward(self._mj_model, self._mj_data)

        self._sync_scene_objects_to_model_locked()
        self._apply_object_reset_policy_locked()
        self._settle_scene_locked()
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

    def _settle_scene_locked(self) -> None:
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

        ctrl_snapshot = self._mj_data.ctrl.copy() if self._mj_data.ctrl is not None and len(self._mj_data.ctrl) > 0 else None
        for _ in range(max(0, int(SCENE_SETTLE_STEPS))):
            _mujoco.mj_step(self._mj_model, self._mj_data)
            for qpos_addr, qpos_value in preserved_qpos:
                self._mj_data.qpos[qpos_addr] = qpos_value
            for qvel_addr in preserved_qvel:
                self._mj_data.qvel[qvel_addr] = 0.0
            if ctrl_snapshot is not None:
                self._mj_data.ctrl[:] = ctrl_snapshot
            _mujoco.mj_forward(self._mj_model, self._mj_data)
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
            backend_position = (
                self._frontend_to_backend_position(sampled)
                if region["frame"] == "frontend"
                else sampled
            )

            if obj_id in self._scene_objects_template:
                self._scene_objects_template[obj_id]["position"] = list(backend_position)
                self._scene_objects_template[obj_id]["attached_to_gripper"] = False

            if using_mujoco and obj_id in self._scene_objects_template:
                quaternion = self._scene_objects_template[obj_id].get("quaternion", [1.0, 0.0, 0.0, 0.0])
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

    def _extract_ee_target_pose_locked(
        self,
        request: StepRequest,
    ) -> tuple[list[float], list[float]] | None:
        target_pose = getattr(request, "target_ee_pose", None)
        target_delta = getattr(request, "target_ee_delta", None)
        if target_pose is None and target_delta is None:
            return None

        current_pose = self._compute_ee_pose_locked()
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

        if _is_realtime_source(request.source):
            current_position = [float(v) for v in current_pose["position"][:3]]
            delta = [
                target_position[axis] - current_position[axis]
                for axis in range(3)
            ]
            delta_norm = math.sqrt(sum(component * component for component in delta))
            if delta_norm > REALTIME_EE_MAX_DELTA_M and delta_norm > 1e-8:
                scale = REALTIME_EE_MAX_DELTA_M / delta_norm
                target_position = [
                    current_position[axis] + delta[axis] * scale
                    for axis in range(3)
                ]

        return target_position, target_quaternion

    def _solve_ee_ik_locked(
        self,
        target_position: list[float],
        target_quaternion: list[float],
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
            or self._tool_body_id is None
            or _mujoco is None
            or np is None
        ):
            return None, info

        arm_qpos_addrs = [self._arm_joint_qpos_addr.get(name) for name in self._arm_joint_names]
        arm_dof_addrs = [self._arm_joint_qvel_addr.get(name) for name in self._arm_joint_names]
        if any(addr is None for addr in arm_qpos_addrs) or any(addr is None for addr in arm_dof_addrs):
            info["status"] = "missing_arm_joints"
            return None, info

        qpos_snapshot = self._mj_data.qpos.copy()
        qvel_snapshot = self._mj_data.qvel.copy()
        ctrl_snapshot = self._mj_data.ctrl.copy()

        try:
            q = np.asarray(self._read_current_arm_qpos_locked(), dtype=float)
            target_pos = np.asarray(target_position[:3], dtype=float)
            target_quat = _normalize_quaternion(target_quaternion)
            qpos_indices = [int(addr) for addr in arm_qpos_addrs if addr is not None]
            dof_indices = [int(addr) for addr in arm_dof_addrs if addr is not None]

            for idx, qpos_addr in enumerate(qpos_indices):
                self._mj_data.qpos[qpos_addr] = float(q[idx])
            self._mj_data.qvel[:] = 0.0
            _mujoco.mj_forward(self._mj_model, self._mj_data)

            final_position_error = float("inf")
            final_orientation_error = float("inf")
            for _ in range(IK_MAX_ITERATIONS):
                current_pos = np.asarray(self._mj_data.xpos[self._tool_body_id], dtype=float)
                current_quat = [float(v) for v in self._mj_data.xquat[self._tool_body_id]]
                position_error = target_pos - current_pos
                orientation_error = np.asarray(
                    _quaternion_error_vector(target_quat, current_quat),
                    dtype=float,
                )
                final_position_error = float(np.linalg.norm(position_error))
                final_orientation_error = float(np.linalg.norm(orientation_error))
                if (
                    final_position_error <= IK_POSITION_TOLERANCE_M
                    and final_orientation_error <= IK_ORIENTATION_TOLERANCE_RAD
                ):
                    break

                jacp = np.zeros((3, self._mj_model.nv), dtype=float)
                jacr = np.zeros((3, self._mj_model.nv), dtype=float)
                _mujoco.mj_jacBody(self._mj_model, self._mj_data, jacp, jacr, int(self._tool_body_id))
                task_error = np.concatenate(
                    [
                        position_error * IK_POSITION_WEIGHT,
                        orientation_error * IK_ORIENTATION_WEIGHT,
                    ]
                )
                task_jacobian = np.vstack(
                    [
                        jacp[:, dof_indices] * IK_POSITION_WEIGHT,
                        jacr[:, dof_indices] * IK_ORIENTATION_WEIGHT,
                    ]
                )
                lhs = task_jacobian @ task_jacobian.T
                lhs += np.eye(lhs.shape[0]) * (IK_DAMPING * IK_DAMPING)
                try:
                    task_step = np.linalg.solve(lhs, task_error)
                except Exception:
                    task_step = np.linalg.lstsq(lhs, task_error, rcond=None)[0]
                dq = task_jacobian.T @ task_step
                max_abs_step = float(np.max(np.abs(dq))) if dq.size else 0.0
                if max_abs_step > IK_MAX_STEP_RAD:
                    dq *= IK_MAX_STEP_RAD / max_abs_step

                q = np.asarray(self._clamp_arm_targets((q + dq).tolist()), dtype=float)
                for idx, qpos_addr in enumerate(qpos_indices):
                    self._mj_data.qpos[qpos_addr] = float(q[idx])
                self._mj_data.qvel[:] = 0.0
                _mujoco.mj_forward(self._mj_model, self._mj_data)

            current_pos = np.asarray(self._mj_data.xpos[self._tool_body_id], dtype=float)
            current_quat = [float(v) for v in self._mj_data.xquat[self._tool_body_id]]
            final_position_error = float(np.linalg.norm(target_pos - current_pos))
            final_orientation_error = float(
                np.linalg.norm(np.asarray(_quaternion_error_vector(target_quat, current_quat), dtype=float))
            )
            info["position_error_m"] = final_position_error
            info["orientation_error_rad"] = final_orientation_error
            info["status"] = (
                "solved"
                if final_position_error <= max(0.012, IK_POSITION_TOLERANCE_M * 3.0)
                else "best_effort"
            )
            return self._clamp_arm_targets(q.tolist()), info
        finally:
            self._mj_data.qpos[:] = qpos_snapshot
            self._mj_data.qvel[:] = qvel_snapshot
            self._mj_data.ctrl[:] = ctrl_snapshot
            _mujoco.mj_forward(self._mj_model, self._mj_data)

    def _resolve_arm_target_for_request_locked(
        self,
        request: StepRequest,
        target_positions: list[float] | None,
    ) -> list[float] | None:
        ee_target = self._extract_ee_target_pose_locked(request)
        if ee_target is None:
            return target_positions

        solved_target, ik_info = self._solve_ee_ik_locked(ee_target[0], ee_target[1])
        if isinstance(self._last_normalized_input, dict):
            self._last_normalized_input.update(
                {
                    "ik_active": 1,
                    "ik_status": ik_info.get("status"),
                    "ik_position_error_m": ik_info.get("position_error_m"),
                    "ik_orientation_error_rad": ik_info.get("orientation_error_rad"),
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

    def _apply_arm_command(self, target_positions: list[float] | None, n_steps: int, source: str = "manual") -> None:
        if target_positions is None:
            self._arm_qvel = [0.0 for _ in self._arm_qvel]
            return

        current = list(self._arm_qpos)
        if self._using_mujoco_model() and self._mj_data is not None:
            current = []
            for name in self._arm_joint_names:
                qpos_addr = self._arm_joint_qpos_addr.get(name)
                current.append(float(self._mj_data.qpos[qpos_addr]) if qpos_addr is not None else 0.0)

        target = self._clamp_arm_targets([float(v) for v in target_positions])
        if _is_realtime_source(source):
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
        blend = _resolve_command_blend(source, n_steps, ARM_COMMAND_BLEND_PER_STEP)
        applied = [
            current[idx] + (target[idx] - current[idx]) * blend
            for idx in range(len(target))
        ]
        duration = max(self._dt, n_steps * self._dt)
        self._arm_qvel = [(applied[i] - current[i]) / duration for i in range(len(applied))]
        self._arm_qpos = list(applied)

        if self._using_mujoco_model() and self._mj_data is not None:
            for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
                actuator_id = self._arm_actuator_ids.get(actuator_name)
                if actuator_id is None or idx >= len(applied):
                    continue
                offset = self._arm_actuator_ctrl_offsets.get(actuator_name, 0.0)
                self._mj_data.ctrl[actuator_id] = float(applied[idx]) - offset
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
            return

        if command.mode != "open_close":
            raise ValueError(f"Unsupported gripper command mode: {command.mode}")

        current_opening = float(self._gripper_opening)
        if self._using_mujoco_model() and self._mj_data is not None:
            driver_addr = self._gripper_joint_qpos_addr.get("left_driver_joint")
            if driver_addr is not None:
                current_opening = _clamp(float(self._mj_data.qpos[driver_addr]) / GRIPPER_DRIVER_LIMIT, 0.0, 1.0)

        desired_opening = _clamp(float(command.value), 0.0, 1.0)
        if _is_realtime_source(source):
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
        blend = _resolve_command_blend(source, n_steps, GRIPPER_COMMAND_BLEND_PER_STEP)
        target_opening = current_opening + (desired_opening - current_opening) * blend
        duration = max(self._dt, n_steps * self._dt)
        self._gripper_velocity = (target_opening - current_opening) / duration
        self._gripper_opening = target_opening
        self._gripper_joints = self._map_gripper_joints(self._gripper_opening)

        if self._using_mujoco_model() and self._mj_data is not None:
            self._set_mujoco_gripper_kinematic_state_locked(
                self._gripper_opening,
                self._gripper_velocity,
                forward=True,
            )
            return

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
            objects[obj_id]["attached_to_gripper"] = obj_id == self._attached_object_id
        return objects

    def _compute_ee_pose_locked(self) -> dict[str, list[float]]:
        if self._using_mujoco_model() and self._mj_data is not None and self._tool_body_id is not None:
            return {
                "position": [float(v) for v in self._mj_data.xpos[self._tool_body_id]],
                "quaternion": [float(v) for v in self._mj_data.xquat[self._tool_body_id]],
            }

        # Fallback FK for stub mode.
        base = self._manifest_data.get("robot", {}).get("transform", {}).get("position", [-0.2, 0.5, -0.1])
        q1, q2, q3, q4, q5, q6 = self._arm_qpos
        reach_xy = 0.45 + 0.05 * math.cos(q3)
        x = float(base[0]) + reach_xy * math.cos(q1) * math.cos(q2)
        y = float(base[1]) + reach_xy * math.sin(q1) * math.cos(q2)
        z = float(base[2]) + 0.35 + 0.15 * math.sin(-q2) + 0.06 * math.sin(q3)
        quat = _rpy_to_quaternion(q4, q5, q6)
        return {"position": [x, y, z], "quaternion": quat}

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
            self._mj_renderer_width = render_width
            self._mj_renderer_height = render_height
            return self._mj_renderer
        except Exception:
            self._close_mujoco_renderer()
            return None

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

            renderer.enable_depth_rendering()
            renderer.update_scene(self._mj_data, camera=depth_camera_name)
            depth_raw = renderer.render()
            renderer.disable_depth_rendering()

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
        frame_id = f"frame_{self._camera_frame_counter:06d}"
        self._stats["camera_frames"] = int(self._stats.get("camera_frames", 0)) + 1

        if np is not None and rgb_rendered is not None:
            self._camera_last_rgb_frame = np.ascontiguousarray(rgb_rendered, dtype=np.uint8)
        else:
            self._camera_last_rgb_frame = None

        if np is not None and depth_rendered is not None:
            self._camera_last_depth_frame = np.ascontiguousarray(depth_rendered, dtype=np.uint16)
        else:
            self._camera_last_depth_frame = None

        camera_capture_ok = bool(
            (not rgb_missing)
            and (not depth_missing)
            and frame_aligned
            and self._camera_recordable_training_observation
        )
        if not camera_capture_ok:
            self._stats["camera_drops"] = int(self._stats.get("camera_drops", 0)) + 1

        camera_state: dict[str, Any] = {
            "device": self._camera_device,
            "mount_name": self._camera_mount_name,
            "mount_parent_frame": self._camera_mount_parent_frame,
            "camera_intrinsics_version": self._camera_intrinsics_version,
            "camera_extrinsics_version": self._camera_extrinsics_version,
            "frame_id": frame_id,
            "frame_aligned": frame_aligned,
            "alignment_mode": self._camera_alignment_mode,
            "max_alignment_error_ms": float(self._camera_alignment_max_delta_ms),
            "recordable_training_observation": bool(self._camera_recordable_training_observation),
            "camera_capture_ok": camera_capture_ok,
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
        observation: dict[str, Any] = {
            "timestamp": time.time(),
            "frame_id": camera_state.get("frame_id"),
            "camera_device": camera_state.get("device"),
            "camera_mount_name": camera_state.get("mount_name"),
            "camera_intrinsics_version": camera_state.get("camera_intrinsics_version"),
            "camera_extrinsics_version": camera_state.get("camera_extrinsics_version"),
            "camera_capture_ok": camera_state.get("camera_capture_ok", False),
            "frame_aligned": camera_state.get("frame_aligned", False),
            "recordable_training_observation": camera_state.get("recordable_training_observation", False),
            "rgb": dict(camera_state.get("rgb", {})),
            "depth": dict(camera_state.get("depth", {})),
            "camera_pose_in_ee": deepcopy(camera_state.get("camera_pose_in_ee", {})),
            "camera_pose_in_base": deepcopy(camera_state.get("camera_pose_in_base", {})),
            "dataset_schema_version": self._dataset_schema.get("dataset_schema_version"),
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
        ee_pose = self._compute_ee_pose_locked()
        if refresh_camera:
            camera_state = self._capture_camera_state_locked(force_capture=False, ee_pose=ee_pose)
        elif self._camera_last_state is not None:
            camera_state = deepcopy(self._camera_last_state)
        else:
            # Initialize camera snapshot once so lightweight broadcasts can reuse it.
            camera_state = self._capture_camera_state_locked(force_capture=False, ee_pose=ee_pose)
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
            "ee_pose": ee_pose,
            "gripper_opening": self._gripper_opening,
            "gripper_joints": dict(self._gripper_joints),
            "objects": deepcopy(self._objects_state),
            "camera": camera_state,
            "camera_capture_ok": bool(camera_state.get("camera_capture_ok", False)),
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

    async def _command_worker(self) -> None:
        while self._running:
            try:
                queued = await self._command_queue.get()
            except asyncio.CancelledError:
                break

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

    def _extract_realtime_command_seq(self, request: StepRequest) -> tuple[str, int] | None:
        """
        Return (source, sequence) for Quest realtime commands that carry an
        anti-replay sequence number.
        """
        source = str(getattr(request, "source", "") or "").strip().lower()
        if source not in {"quest3_controller", "quest3_hand"}:
            return None

        normalized = request.normalized_input
        if not isinstance(normalized, dict):
            return None

        seq_raw = normalized.get("control_seq")
        try:
            seq = int(seq_raw)
        except (TypeError, ValueError):
            return None

        return source, seq

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
