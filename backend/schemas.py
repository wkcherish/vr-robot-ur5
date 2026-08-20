from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ControlSource = Literal[
    "manual",
    "desktop_manual",
    "quest3_controller",
    "quest3_hand",
    "task",
    "policy",
]
VRMode = Literal[
    "vr_disabled",
    "vr_ready",
    "vr_controller_mode",
    "vr_hand_mode",
    "vr_error",
]
DatasetTaskType = Literal[
    "tool_grasp",
    "tool_pick_place",
    "tool_reposition",
    "debug_trial",
]
DatasetCollectionStage = Literal[
    "debug_trial",
    "pilot",
    "train_candidate",
    "eval_candidate",
    "rejected",
]
DatasetControlMode = Literal["vr_controller", "vr_hand"]
DatasetRobotInputSource = Literal["quest3_controller", "quest3_hand"]


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


class TargetEEPose(BaseModel):
    position: list[float] | None = None
    quaternion: list[float] | None = None

    class Config:
        extra = "ignore"


class StepRequest(BaseModel):
    target_positions: list[float] | None = None
    target_ee_pose: TargetEEPose | None = None
    target_ee_delta: list[float] | None = None
    n_steps: int = Field(default=10, ge=1, le=2000)
    control_mode: str = "position"
    kp: float | None = None
    kd: float | None = None
    gripper_command: GripperCommand | None = None
    source: ControlSource = "manual"
    input_source: str | None = None
    selected_joint_group: str | None = None
    raw_input: dict[str, Any] | None = None
    normalized_input: dict[str, Any] | None = None

    class Config:
        extra = "ignore"


class ResetRequest(BaseModel):
    model_path: str | None = None
    reload_model: bool = True
    preserve_vr_state: bool = False
    settle_steps: int | None = Field(default=None, ge=0, le=1000)
    randomize_scene_objects: bool = False

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


class CameraStreamState(BaseModel):
    interface_name: str
    camera_name: str
    width: int
    height: int
    fps: float
    pixel_format: str
    dataset_storage_format: str
    timestamp: float | None = None
    missing: bool = False
    valid: bool = False
    error_reason: str | None = None
    depth_unit: str | None = None
    depth_scale: float | None = None


class CameraState(BaseModel):
    device: str
    mount_name: str
    mount_parent_frame: str
    camera_intrinsics_version: str
    camera_extrinsics_version: str
    frame_id: str
    d405_frame_id: str
    timestamp: float
    frame_aligned: bool
    alignment_mode: str
    max_alignment_error_ms: float
    recordable_training_observation: bool
    camera_capture_ok: bool
    camera_source_ok: bool = False
    rgb_valid: bool = False
    depth_valid: bool = False
    stub_frame_used: bool = False
    camera_view_ok: bool = False
    camera_view_status: str = "unchecked"
    last_error: str | None = None
    debug_only_objects: list[str]
    camera_pose_in_ee: EEPose
    camera_pose_in_base: EEPose
    rgb: CameraStreamState
    depth: CameraStreamState


class SimState(BaseModel):
    timestamp: float
    sim_time: float
    joint_names: list[str]
    joint_limits: dict[str, list[float]] = Field(default_factory=dict)
    qpos: list[float]
    qvel: list[float]
    arm_target_qpos: list[float] | None = None
    arm_ctrl_qpos: list[float] | None = None
    gripper_target_opening: float | None = None
    gripper_ctrl_opening: float | None = None
    ee_pose: EEPose
    control_ee_pose: EEPose | None = None
    gripper_opening: float
    gripper_joints: dict[str, float]
    objects: dict[str, ObjectPose]
    handover_zones: list[dict[str, Any]] = Field(default_factory=list)
    camera: CameraState | None = None
    camera_capture_ok: bool = False
    d405_frame_id: str | None = None
    camera_observation: dict[str, Any] | None = None
    task_state: TaskState
    source: ControlSource
    input_source: str | None = None
    selected_joint_group: str | None = None
    raw_input: dict[str, Any] | None = None
    normalized_input: dict[str, Any] | None = None
    safety_status: str = "normal"
    collision_blocked: bool = False
    collision_contacts: list[dict[str, Any]] = []
    vr: dict[str, Any]
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
    host_ip: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str | None = None
    timestamp: float


class VRStateUpdateRequest(BaseModel):
    mode: VRMode | None = None
    controller_available: bool | None = None
    hand_tracking_available: bool | None = None
    selected_joint_group: str | None = None
    recording_ready: bool | None = None
    last_quest_input_ts: float | None = None
    active_policy_path: str | None = None
    error_message: str | None = None
    source: ControlSource | None = None
    raw_input: dict[str, Any] | None = None
    normalized_input: dict[str, Any] | None = None

    class Config:
        extra = "ignore"


class DatasetEpisodeStartRequest(BaseModel):
    task_type: DatasetTaskType = "debug_trial"
    target_tool_id: str = "wrench_01"
    target_zone_id: str = "desk_drop_zone"
    instruction_text: str = "debug trial with the wrench"
    collection_stage: DatasetCollectionStage = "debug_trial"
    control_mode: DatasetControlMode = "vr_controller"
    robot_input_source: DatasetRobotInputSource = "quest3_controller"
    reset_seed: int | None = None
    operator_id: str | None = None
    notes: str | None = None
    scripted_collection: bool = False

    class Config:
        extra = "ignore"


class DatasetEpisodeStopRequest(BaseModel):
    episode_id: str
    result_status: str = "unknown"
    quality_label: str | None = None
    notes: str | None = None

    class Config:
        extra = "ignore"


class DatasetEpisodeResultRequest(BaseModel):
    episode_id: str
    result_status: str
    quality_label: str | None = None
    notes: str | None = None

    class Config:
        extra = "ignore"
