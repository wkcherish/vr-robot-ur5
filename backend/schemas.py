from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ControlSource = Literal["manual", "task", "policy"]


class WSMessage(BaseModel):
    type: str
    data: dict[str, Any] | None = None
    timestamp: int | float | None = None

    class Config:
        extra = "ignore"


class GripperCommand(BaseModel):
    mode: Literal["open_close"] = "open_close"
    value: float = Field(default=0.0, ge=0.0, le=1.0)

    class Config:
        extra = "ignore"


class StepRequest(BaseModel):
    target_positions: list[float] | None = None
    n_steps: int = Field(default=10, ge=1, le=2000)
    control_mode: str = "position"
    kp: float | None = None
    kd: float | None = None
    gripper_command: GripperCommand | None = None
    source: ControlSource = "manual"

    class Config:
        extra = "ignore"


class ResetRequest(BaseModel):
    model_path: str | None = None

    class Config:
        extra = "ignore"


class EEPose(BaseModel):
    position: list[float]
    quaternion: list[float]


class ObjectPose(BaseModel):
    position: list[float]
    quaternion: list[float]
    attached_to_gripper: bool = False


class TaskState(BaseModel):
    running: bool = False
    name: str | None = None
    phase: str | None = None


class SimState(BaseModel):
    timestamp: float
    sim_time: float
    joint_names: list[str]
    qpos: list[float]
    qvel: list[float]
    ee_pose: EEPose
    gripper_opening: float
    gripper_joints: dict[str, float]
    objects: dict[str, ObjectPose]
    task_state: TaskState
    source: ControlSource
    stats: dict[str, float | int]


class CommandResult(BaseModel):
    status: Literal["success", "error"]
    message: str
    state: SimState | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    timestamp: float
    model_backend: str
    scene_manifest: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str | None = None
    timestamp: float
