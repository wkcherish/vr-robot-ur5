from __future__ import annotations

import asyncio
import json
import math
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.schemas import GripperCommand, StepRequest

try:
    import mujoco as _mujoco  # type: ignore
except Exception:
    _mujoco = None


DEFAULT_ARM_JOINT_NAMES = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]

DEFAULT_HOME_QPOS = [0.0, -math.pi / 2, math.pi / 2, -math.pi / 2, -math.pi / 2, 0.0]
DEFAULT_DT = 0.02
GRIPPER_DRIVER_LIMIT = 0.87


@dataclass
class _QueuedCommand:
    request: StepRequest
    future: asyncio.Future[dict[str, Any]]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


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
        self._arm_joint_names = list(DEFAULT_ARM_JOINT_NAMES)
        self._home_arm_qpos = list(DEFAULT_HOME_QPOS)
        self._scene_objects_template: dict[str, dict[str, Any]] = {}

        self._arm_qpos = list(DEFAULT_HOME_QPOS)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
        self._gripper_joints = self._map_gripper_joints(0.0)
        self._objects_state: dict[str, dict[str, Any]] = {}
        self._source = "manual"
        self._task_state = {"running": False, "name": None, "phase": None}
        self._sim_time = 0.0
        self._dt = DEFAULT_DT
        self._stats = {
            "steps": 0,
            "commands": 0,
            "last_step_ms": 0.0,
            "avg_step_ms": 0.0,
        }

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

    async def enqueue_step(self, request: StepRequest) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        await self._command_queue.put(_QueuedCommand(request=request, future=future))
        return await future

    async def step(self, request: StepRequest) -> dict[str, Any]:
        async with self._lock:
            started_at = perf_counter()

            target_positions = request.target_positions
            if target_positions is not None and len(target_positions) != len(self._arm_joint_names):
                raise ValueError(
                    f"Expected {len(self._arm_joint_names)} arm joints, got {len(target_positions)}."
                )

            self._source = request.source
            n_steps = max(1, int(request.n_steps))
            self._apply_arm_command(target_positions, n_steps)
            self._apply_gripper_command(request.gripper_command, n_steps)
            self._sim_time += n_steps * self._dt
            self._stats["steps"] += n_steps
            self._stats["commands"] += 1

            elapsed_ms = (perf_counter() - started_at) * 1000.0
            self._stats["last_step_ms"] = elapsed_ms
            command_count = max(1, int(self._stats["commands"]))
            old_avg = float(self._stats["avg_step_ms"])
            self._stats["avg_step_ms"] = old_avg + ((elapsed_ms - old_avg) / command_count)

            return self._build_state_locked()

    async def reset(self, model_path: str | None = None) -> dict[str, Any]:
        async with self._lock:
            self._load_model(model_path)
            self._reset_state_locked()
            return self._build_state_locked()

    async def get_state(self) -> dict[str, Any]:
        async with self._lock:
            return self._build_state_locked()

    async def start_task(self, task_name: str) -> dict[str, Any]:
        async with self._lock:
            self._source = "task"
            self._task_state = {"running": True, "name": task_name, "phase": "queued"}
            return self._build_state_locked()

    async def stop_task(self) -> dict[str, Any]:
        async with self._lock:
            self._source = "manual"
            self._task_state = {"running": False, "name": None, "phase": None}
            return self._build_state_locked()

    async def set_source(self, source: str) -> dict[str, Any]:
        if source not in {"manual", "task", "policy"}:
            raise ValueError("source must be one of: manual, task, policy")
        async with self._lock:
            self._source = source
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
        for obj in self._manifest_data.get("objects", []):
            obj_id = str(obj.get("id", "")).strip()
            if not obj_id:
                continue
            transform = obj.get("transform", {})
            position = [float(v) for v in transform.get("position", [0.0, 0.0, 0.0])]
            rotation_rpy = [float(v) for v in transform.get("rotation_rpy", [0.0, 0.0, 0.0])]
            quaternion = _rpy_to_quaternion(*rotation_rpy)
            self._scene_objects_template[obj_id] = {
                "position": position,
                "quaternion": quaternion,
                "attached_to_gripper": False,
            }

    def _load_model(self, model_path: str | None) -> None:
        # Milestone B keeps a model-loading seam without requiring MuJoCo assets yet.
        self._loaded_model_path = model_path or str(self._manifest_path)

    def _reset_state_locked(self) -> None:
        self._arm_qpos = list(self._home_arm_qpos)
        self._arm_qvel = [0.0 for _ in self._arm_qpos]
        self._gripper_opening = 0.0
        self._gripper_velocity = 0.0
        self._gripper_joints = self._map_gripper_joints(self._gripper_opening)
        self._objects_state = deepcopy(self._scene_objects_template)
        self._source = "manual"
        self._task_state = {"running": False, "name": None, "phase": None}
        self._sim_time = 0.0
        self._stats["steps"] = 0
        self._stats["commands"] = 0
        self._stats["last_step_ms"] = 0.0
        self._stats["avg_step_ms"] = 0.0

    def _apply_arm_command(self, target_positions: list[float] | None, n_steps: int) -> None:
        if target_positions is None:
            self._arm_qvel = [0.0 for _ in self._arm_qvel]
            return

        current = list(self._arm_qpos)
        target = [float(v) for v in target_positions]
        duration = max(self._dt, n_steps * self._dt)
        self._arm_qvel = [(target[i] - current[i]) / duration for i in range(len(target))]
        self._arm_qpos = target

    def _apply_gripper_command(self, command: GripperCommand | None, n_steps: int) -> None:
        if command is None:
            self._gripper_velocity = 0.0
            return

        if command.mode != "open_close":
            raise ValueError(f"Unsupported gripper command mode: {command.mode}")

        target_opening = _clamp(float(command.value), 0.0, 1.0)
        duration = max(self._dt, n_steps * self._dt)
        self._gripper_velocity = (target_opening - self._gripper_opening) / duration
        self._gripper_opening = target_opening
        self._gripper_joints = self._map_gripper_joints(self._gripper_opening)

    def _map_gripper_joints(self, opening: float) -> dict[str, float]:
        driver = _clamp(opening, 0.0, 1.0) * GRIPPER_DRIVER_LIMIT
        return {
            "left_driver_joint": driver,
            "right_driver_joint": driver,
            "left_spring_link_joint": driver,
            "right_spring_link_joint": driver,
            "left_follower_joint": -driver,
            "right_follower_joint": -driver,
        }

    def _compute_ee_pose_locked(self) -> dict[str, list[float]]:
        # Placeholder FK for milestone B to keep a stable response schema.
        base = self._manifest_data.get("robot", {}).get("transform", {}).get("position", [-0.2, 0.5, -0.1])
        q1, q2, q3, q4, q5, q6 = self._arm_qpos
        reach_xy = 0.45 + 0.05 * math.cos(q3)
        x = float(base[0]) + reach_xy * math.cos(q1) * math.cos(q2)
        y = float(base[1]) + reach_xy * math.sin(q1) * math.cos(q2)
        z = float(base[2]) + 0.35 + 0.15 * math.sin(-q2) + 0.06 * math.sin(q3)
        quat = _rpy_to_quaternion(q4, q5, q6)
        return {"position": [x, y, z], "quaternion": quat}

    def _build_state_locked(self) -> dict[str, Any]:
        gripper_driver = self._gripper_joints["left_driver_joint"]
        qpos = list(self._arm_qpos) + [gripper_driver]
        qvel = list(self._arm_qvel) + [self._gripper_velocity]
        return {
            "timestamp": time.time(),
            "sim_time": self._sim_time,
            "joint_names": list(self._arm_joint_names),
            "qpos": qpos,
            "qvel": qvel,
            "ee_pose": self._compute_ee_pose_locked(),
            "gripper_opening": self._gripper_opening,
            "gripper_joints": dict(self._gripper_joints),
            "objects": deepcopy(self._objects_state),
            "task_state": dict(self._task_state),
            "source": self._source,
            "stats": {
                "steps": int(self._stats["steps"]),
                "commands": int(self._stats["commands"]),
                "last_step_ms": float(self._stats["last_step_ms"]),
                "avg_step_ms": float(self._stats["avg_step_ms"]),
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
                state = await self.step(queued.request)
                if not queued.future.done():
                    queued.future.set_result(state)
            except Exception as exc:
                if not queued.future.done():
                    queued.future.set_exception(exc)
            finally:
                self._command_queue.task_done()
