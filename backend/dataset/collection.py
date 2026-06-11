from __future__ import annotations

import json
import os
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.schemas import (
    DatasetEpisodeResultRequest,
    DatasetEpisodeStartRequest,
    DatasetEpisodeStopRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = REPO_ROOT / "data" / "datasets" / "quest3_vr_lerobot_pi05_v1"
DEFAULT_TOOL_CATALOG_PATH = REPO_ROOT / "shared" / "tool_catalog.json"
DEFAULT_SCENE_MANIFEST_PATH = REPO_ROOT / "shared" / "scene_manifest.json"
DEFAULT_DATASET_SCHEMA_PATH = REPO_ROOT / "shared" / "dataset_schema.json"

TASK_ID = "quest3_vr_lerobot_pi05_v1"
DEFAULT_AUTONOMY_LEVEL = "manual_demonstration"
TASK_TEMPLATE_ORDER = ["tool_grasp", "tool_pick_place", "tool_reposition", "debug_trial"]
GRASPABLE_TOOL_IDS = {"wrench_01", "screwdriver_01", "pliers_01"}
FORMAL_COLLECTION_STAGES = {"pilot", "train_candidate", "eval_candidate"}

TASK_TEMPLATES: dict[str, dict[str, Any]] = {
    "tool_grasp": {
        "task_type": "tool_grasp",
        "display_name": "Tool Grasp",
        "default_instruction_by_class": {
            "wrench": "pick up the wrench",
            "screwdriver": "pick up the screwdriver",
            "pliers": "pick up the pliers",
        },
        "allowed_collection_stages": ["pilot", "train_candidate", "eval_candidate", "rejected"],
        "requires_target_zone": False,
    },
    "tool_pick_place": {
        "task_type": "tool_pick_place",
        "display_name": "Tool Pick Place",
        "default_instruction_by_class": {
            "wrench": "place the wrench in the toolbox",
            "screwdriver": "place the screwdriver in the toolbox",
            "pliers": "place the pliers in the toolbox",
        },
        "allowed_collection_stages": ["pilot", "train_candidate", "eval_candidate", "rejected"],
        "requires_target_zone": True,
    },
    "tool_reposition": {
        "task_type": "tool_reposition",
        "display_name": "Tool Reposition",
        "default_instruction_by_class": {
            "wrench": "move the wrench to the target zone",
            "screwdriver": "move the screwdriver to the target zone",
            "pliers": "move the pliers to the target zone",
        },
        "allowed_collection_stages": ["pilot", "train_candidate", "eval_candidate", "rejected"],
        "requires_target_zone": True,
    },
    "debug_trial": {
        "task_type": "debug_trial",
        "display_name": "Debug Trial",
        "default_instruction_by_class": {
            "wrench": "debug trial with the wrench",
            "screwdriver": "debug trial with the screwdriver",
            "pliers": "debug trial with the pliers",
        },
        "allowed_collection_stages": ["debug_trial", "rejected"],
        "requires_target_zone": False,
    },
}


@dataclass(frozen=True)
class ToolInstance:
    tool_id: str
    class_id: str
    display_name: str


def _load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback or {})
    return parsed if isinstance(parsed, dict) else dict(fallback or {})


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def _path_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text(str(time.time()), encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _safe_text(raw: Any, fallback: str) -> str:
    value = str(raw or "").strip()
    return value if value else fallback


def _tool_class_from_id(tool_id: str) -> str:
    if tool_id.startswith("wrench"):
        return "wrench"
    if tool_id.startswith("screwdriver"):
        return "screwdriver"
    if tool_id.startswith("pliers"):
        return "pliers"
    return ""


class DatasetCollectionService:
    def __init__(
        self,
        root: Path | None = None,
        tool_catalog_path: Path | None = None,
        scene_manifest_path: Path | None = None,
        dataset_schema_path: Path | None = None,
    ) -> None:
        env_root = os.getenv("QUEST3_DATASET_ROOT", "").strip()
        self._root = Path(env_root).expanduser().resolve() if env_root else (root or DEFAULT_DATASET_ROOT)
        self._tool_catalog_path = tool_catalog_path or DEFAULT_TOOL_CATALOG_PATH
        self._scene_manifest_path = scene_manifest_path or DEFAULT_SCENE_MANIFEST_PATH
        self._dataset_schema_path = dataset_schema_path or DEFAULT_DATASET_SCHEMA_PATH
        self._session_id = f"session_{time.strftime('%Y%m%d_%H%M%S', time.localtime())}"
        self._active_episode_id: str | None = None
        self._active_episode_dir: Path | None = None
        self._tool_catalog: dict[str, Any] = {}
        self._scene_manifest: dict[str, Any] = {}
        self._dataset_schema: dict[str, Any] = {}
        self._tool_instances: dict[str, ToolInstance] = {}
        self._target_zones: list[dict[str, Any]] = []
        self.reload_shared_config()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def active_episode_id(self) -> str | None:
        return self._active_episode_id

    def reload_shared_config(self) -> None:
        self._tool_catalog = _load_json(self._tool_catalog_path)
        self._scene_manifest = _load_json(self._scene_manifest_path)
        self._dataset_schema = _load_json(self._dataset_schema_path)
        self._tool_instances = self._load_tool_instances()
        self._target_zones = self._load_target_zones()

    def get_templates(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID,
            "task_templates": [deepcopy(TASK_TEMPLATES[name]) for name in TASK_TEMPLATE_ORDER],
            "target_tools": [
                {
                    "id": tool.tool_id,
                    "class_id": tool.class_id,
                    "display_name": tool.display_name,
                }
                for tool in self._tool_instances.values()
                if tool.tool_id in GRASPABLE_TOOL_IDS
            ],
            "target_zones": deepcopy(self._target_zones),
            "collection_stages": ["debug_trial", "pilot", "train_candidate", "eval_candidate", "rejected"],
            "control_modes": ["vr_controller", "vr_hand"],
            "dataset_root": str(self._root),
            "active_episode_id": self._active_episode_id,
        }

    async def precheck(self, simulation: Any, ws_active_count: int = 0) -> dict[str, Any]:
        self.reload_shared_config()
        state = await simulation.get_state(refresh_camera=True)
        model_backend = str(getattr(simulation, "model_backend", "unknown") or "unknown")
        checks = self._build_precheck_checks(
            state=state,
            ws_active_count=ws_active_count,
            model_backend=model_backend,
        )
        recording_ready = all(item["ok"] for item in checks.values())
        return {
            "task_id": TASK_ID,
            "timestamp": time.time(),
            "recording_ready": bool(recording_ready),
            "debug_trial_allowed": True,
            "dataset_root": str(self._root),
            "session_id": self._session_id,
            "active_episode_id": self._active_episode_id,
            "checks": checks,
            "summary": self._summarize_checks(checks),
        }

    async def start_episode(
        self,
        request: DatasetEpisodeStartRequest,
        simulation: Any,
        ws_active_count: int = 0,
    ) -> dict[str, Any]:
        self.reload_shared_config()
        precheck = await self.precheck(simulation=simulation, ws_active_count=ws_active_count)
        is_debug_trial = request.task_type == "debug_trial" or request.collection_stage == "debug_trial"
        if not precheck["recording_ready"] and not is_debug_trial:
            return {
                "status": "error",
                "message": "recording_ready=false; only debug_trial can start before precheck passes",
                "precheck": precheck,
            }

        if self._active_episode_id is not None:
            return {
                "status": "error",
                "message": f"episode already active: {self._active_episode_id}",
                "active_episode_id": self._active_episode_id,
                "precheck": precheck,
            }

        validation_error = self._validate_start_request(request)
        if validation_error:
            return {
                "status": "error",
                "message": validation_error,
                "precheck": precheck,
            }

        state = await simulation.get_state(refresh_camera=False)
        episode_id = f"episode_{time.strftime('%Y%m%d_%H%M%S', time.localtime())}_{uuid.uuid4().hex[:8]}"
        episode_dir = self._root / "raw" / episode_id
        self._create_episode_layout(episode_dir)

        metadata = self._build_episode_metadata(
            episode_id=episode_id,
            episode_dir=episode_dir,
            request=request,
            state=state,
            precheck=precheck,
        )
        _write_json(episode_dir / "metadata.json", metadata)
        _write_json(
            episode_dir / "language.json",
            {
                "episode_id": episode_id,
                "instruction_text": metadata["instruction_text"],
                "task_type": metadata["task_type"],
                "target_tool_id": metadata["target_tool_id"],
                "target_zone_id": metadata["target_zone_id"],
            },
        )
        _write_json(episode_dir / "precheck.json", precheck)
        _write_json(
            episode_dir / "validation_summary.json",
            self._build_validation_summary(precheck=precheck, state=state, completed=False),
        )
        _append_jsonl(
            episode_dir / "events.jsonl",
            {
                "timestamp": time.time(),
                "event_type": "episode_start",
                "episode_id": episode_id,
                "task_type": request.task_type,
                "collection_stage": request.collection_stage,
                "control_mode": request.control_mode,
                "robot_input_source": request.robot_input_source,
                "recording_ready": bool(precheck["recording_ready"]),
            },
        )

        self._active_episode_id = episode_id
        self._active_episode_dir = episode_dir
        return {
            "status": "success",
            "message": "episode started",
            "episode_id": episode_id,
            "episode_dir": str(episode_dir),
            "metadata": metadata,
            "precheck": precheck,
        }

    async def stop_episode(
        self,
        request: DatasetEpisodeStopRequest,
        simulation: Any,
        ws_active_count: int = 0,
    ) -> dict[str, Any]:
        if self._active_episode_id != request.episode_id:
            return {
                "status": "error",
                "message": f"active episode mismatch: {self._active_episode_id or 'none'}",
                "active_episode_id": self._active_episode_id,
            }
        if self._active_episode_dir is None:
            return {
                "status": "error",
                "message": "active episode directory missing",
                "active_episode_id": self._active_episode_id,
            }

        episode_dir = self._active_episode_dir
        state = await simulation.get_state(refresh_camera=True)
        precheck = await self.precheck(simulation=simulation, ws_active_count=ws_active_count)
        result = self._build_episode_result(request)
        _write_json(episode_dir / "result.json", result)
        _write_json(
            episode_dir / "validation_summary.json",
            self._build_validation_summary(precheck=precheck, state=state, completed=True),
        )
        _append_jsonl(
            episode_dir / "events.jsonl",
            {
                "timestamp": time.time(),
                "event_type": "episode_stop",
                "episode_id": request.episode_id,
                "result_status": request.result_status,
                "quality_label": request.quality_label,
                "notes": request.notes,
            },
        )
        self._active_episode_id = None
        self._active_episode_dir = None
        return {
            "status": "success",
            "message": "episode stopped",
            "episode_id": request.episode_id,
            "episode_dir": str(episode_dir),
            "result": result,
            "precheck": precheck,
        }

    async def update_result(self, request: DatasetEpisodeResultRequest) -> dict[str, Any]:
        episode_dir = self._resolve_episode_dir(request.episode_id)
        if episode_dir is None:
            return {
                "status": "error",
                "message": f"episode not found: {request.episode_id}",
            }
        result = {
            "episode_id": request.episode_id,
            "result_status": _safe_text(request.result_status, "unknown"),
            "quality_label": request.quality_label,
            "notes": request.notes,
            "updated_at": _utc_timestamp(),
        }
        _write_json(episode_dir / "result.json", result)
        _append_jsonl(
            episode_dir / "events.jsonl",
            {
                "timestamp": time.time(),
                "event_type": "result_update",
                **result,
            },
        )
        return {
            "status": "success",
            "message": "episode result updated",
            "episode_id": request.episode_id,
            "episode_dir": str(episode_dir),
            "result": result,
        }

    def _load_tool_instances(self) -> dict[str, ToolInstance]:
        class_names: dict[str, str] = {}
        for class_item in self._tool_catalog.get("tool_classes", []):
            if not isinstance(class_item, dict):
                continue
            class_id = str(class_item.get("class_id", "")).strip()
            display_name = str(class_item.get("display_name", class_id)).strip()
            if class_id:
                class_names[class_id] = display_name

        instances: dict[str, ToolInstance] = {}
        for item in self._tool_catalog.get("instances", []):
            if not isinstance(item, dict):
                continue
            tool_id = str(item.get("id", "")).strip()
            class_id = str(item.get("class_id", _tool_class_from_id(tool_id))).strip()
            if not tool_id or not class_id:
                continue
            display_name = str(item.get("display_name", class_names.get(class_id, tool_id))).strip()
            instances[tool_id] = ToolInstance(tool_id=tool_id, class_id=class_id, display_name=display_name)

        if not instances:
            for tool_id in sorted(GRASPABLE_TOOL_IDS):
                class_id = _tool_class_from_id(tool_id)
                instances[tool_id] = ToolInstance(tool_id=tool_id, class_id=class_id, display_name=tool_id)
        return instances

    def _load_target_zones(self) -> list[dict[str, Any]]:
        zones: list[dict[str, Any]] = []
        seen: set[str] = set()
        for region in self._tool_catalog.get("spawn_regions", []):
            if not isinstance(region, dict):
                continue
            region_id = str(region.get("id", "")).strip()
            if not region_id or region_id in seen:
                continue
            seen.add(region_id)
            zones.append(
                {
                    "id": region_id,
                    "type": "spawn_region",
                    "display_name": region_id,
                    "frame": region.get("frame", "frontend"),
                }
            )
        for slot in self._tool_catalog.get("toolbox_slots", []):
            if not isinstance(slot, dict):
                continue
            slot_id = str(slot.get("slot_id", "")).strip()
            if not slot_id or slot_id in seen:
                continue
            seen.add(slot_id)
            zones.append(
                {
                    "id": slot_id,
                    "type": "toolbox_slot",
                    "display_name": slot_id,
                    "tool_class": slot.get("tool_class"),
                }
            )
        if "toolbox" not in seen:
            zones.append({"id": "toolbox", "type": "container", "display_name": "toolbox"})
        return zones

    def _build_precheck_checks(
        self,
        state: dict[str, Any],
        ws_active_count: int,
        model_backend: str,
    ) -> dict[str, dict[str, Any]]:
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        objects = state.get("objects") if isinstance(state.get("objects"), dict) else {}
        qpos = state.get("qpos") if isinstance(state.get("qpos"), list) else []
        qvel = state.get("qvel") if isinstance(state.get("qvel"), list) else []
        camera_summary = state.get("camera_observation", {})
        if not isinstance(camera_summary, dict):
            camera_summary = {}

        camera_capture_ready = bool(
            camera.get("camera_source_ok", camera_summary.get("camera_source_ok", False))
            and camera.get("camera_capture_ok", state.get("camera_capture_ok", False))
            and camera.get("rgb_valid", False)
            and camera.get("depth_valid", False)
            and camera.get("frame_aligned", False)
            and not camera.get("stub_frame_used", True)
        )
        camera_view_ok = bool(camera.get("camera_view_ok", False))
        dataset_dir_writable = _path_writable(self._root)
        mujoco_ok = model_backend == "mujoco"
        return {
            "websocket": {
                "ok": int(ws_active_count) > 0,
                "message": "WebSocket connected" if int(ws_active_count) > 0 else "no active WebSocket client",
                "active_count": int(ws_active_count),
            },
            "d405": {
                "ok": camera_capture_ready,
                "message": "D405 RGB-D capture ready"
                if camera_capture_ready
                else str(camera.get("last_error") or "D405 RGB-D not ready"),
                "frame_id": camera.get("d405_frame_id") or state.get("d405_frame_id"),
                "camera_device": camera.get("device"),
                "camera_intrinsics_version": camera.get("camera_intrinsics_version"),
                "camera_extrinsics_version": camera.get("camera_extrinsics_version"),
                "camera_view_ok": bool(camera.get("camera_view_ok", False)),
                "camera_view_status": camera.get("camera_view_status"),
            },
            "camera_view": {
                "ok": camera_view_ok,
                "message": "D405 view verified"
                if camera_view_ok
                else str(camera.get("camera_view_status") or "D405 view not verified"),
                "camera_view_status": camera.get("camera_view_status"),
            },
            "mujoco": {
                "ok": mujoco_ok,
                "message": "MuJoCo model loaded" if mujoco_ok else f"simulation backend is {model_backend}",
                "model_backend": model_backend,
                "sim_time": state.get("sim_time"),
            },
            "ur5": {
                "ok": len(qpos) >= 6 and len(qvel) >= 6,
                "message": "UR5 state complete" if len(qpos) >= 6 and len(qvel) >= 6 else "UR5 qpos/qvel incomplete",
                "joint_count": len(qpos),
            },
            "tools": {
                "ok": all(tool_id in objects for tool_id in GRASPABLE_TOOL_IDS),
                "message": "tool objects present"
                if all(tool_id in objects for tool_id in GRASPABLE_TOOL_IDS)
                else "missing one or more target tool states",
                "required_tool_ids": sorted(GRASPABLE_TOOL_IDS),
                "present_tool_ids": sorted(tool_id for tool_id in GRASPABLE_TOOL_IDS if tool_id in objects),
            },
            "dataset_dir": {
                "ok": dataset_dir_writable,
                "message": "dataset directory writable" if dataset_dir_writable else "dataset directory not writable",
                "path": str(self._root),
            },
        }

    def _summarize_checks(self, checks: dict[str, dict[str, Any]]) -> list[str]:
        failed: list[str] = []
        for name, item in checks.items():
            if not item.get("ok", False):
                failed.append(f"{name}: {item.get('message', 'failed')}")
        return failed

    def _validate_start_request(self, request: DatasetEpisodeStartRequest) -> str | None:
        if request.task_type not in TASK_TEMPLATES:
            return f"unsupported task_type: {request.task_type}"
        if request.target_tool_id not in self._tool_instances or request.target_tool_id not in GRASPABLE_TOOL_IDS:
            return f"unsupported target_tool_id: {request.target_tool_id}"
        if request.collection_stage not in TASK_TEMPLATES[request.task_type]["allowed_collection_stages"]:
            return f"collection_stage {request.collection_stage} is not allowed for {request.task_type}"
        if bool(getattr(request, "scripted_collection", False)) and request.collection_stage in FORMAL_COLLECTION_STAGES:
            return "scripted_collection=true cannot be marked as a formal training or evaluation candidate"
        if request.control_mode == "vr_controller" and request.robot_input_source != "quest3_controller":
            return "vr_controller requires robot_input_source=quest3_controller"
        if request.control_mode == "vr_hand" and request.robot_input_source != "quest3_hand":
            return "vr_hand requires robot_input_source=quest3_hand"
        known_zone_ids = {str(zone.get("id")) for zone in self._target_zones}
        if request.target_zone_id and request.target_zone_id not in known_zone_ids:
            return f"unsupported target_zone_id: {request.target_zone_id}"
        return None

    def _create_episode_layout(self, episode_dir: Path) -> None:
        for child in ["rgb", "depth"]:
            (episode_dir / child).mkdir(parents=True, exist_ok=True)
        for filename in ["visuals.jsonl", "states.jsonl", "actions.jsonl", "events.jsonl"]:
            path = episode_dir / filename
            if not path.exists():
                path.write_text("", encoding="utf-8")

    def _build_episode_metadata(
        self,
        episode_id: str,
        episode_dir: Path,
        request: DatasetEpisodeStartRequest,
        state: dict[str, Any],
        precheck: dict[str, Any],
    ) -> dict[str, Any]:
        tool = self._tool_instances[request.target_tool_id]
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        instruction = _safe_text(
            request.instruction_text,
            self._default_instruction(request.task_type, tool.class_id),
        )
        return {
            "task_id": TASK_ID,
            "session_id": self._session_id,
            "episode_id": episode_id,
            "episode_dir": str(episode_dir),
            "captured_at": _utc_timestamp(),
            "input_mode": request.control_mode,
            "input_source": request.robot_input_source,
            "control_mode": request.control_mode,
            "robot_input_source": request.robot_input_source,
            "runtime_target": "mujoco",
            "operator_controlled": True,
            "autonomy_level": DEFAULT_AUTONOMY_LEVEL,
            "scripted_collection": bool(getattr(request, "scripted_collection", False)),
            "instruction_text": instruction,
            "collection_stage": request.collection_stage,
            "episode_type": request.task_type,
            "task_type": request.task_type,
            "target_tool_id": request.target_tool_id,
            "target_tool_class": tool.class_id,
            "target_zone_id": request.target_zone_id,
            "handover_object_id": request.target_tool_id,
            "handover_object_class": tool.class_id,
            "handover_zone_id": request.target_zone_id,
            "reset_seed": request.reset_seed,
            "camera_device": camera.get("device"),
            "camera_mount_name": camera.get("mount_name"),
            "camera_intrinsics_version": camera.get("camera_intrinsics_version"),
            "camera_extrinsics_version": camera.get("camera_extrinsics_version"),
            "scene_manifest_version": self._scene_manifest.get("manifest_version"),
            "tool_catalog_version": self._tool_catalog.get("catalog_version"),
            "dataset_schema_version": self._dataset_schema.get("dataset_schema_version"),
            "recording_ready_at_start": bool(precheck.get("recording_ready", False)),
            "precheck_summary": list(precheck.get("summary", [])),
            "operator_id": request.operator_id,
            "notes": request.notes,
        }

    def _build_validation_summary(
        self,
        precheck: dict[str, Any],
        state: dict[str, Any],
        completed: bool,
    ) -> dict[str, Any]:
        camera = state.get("camera") if isinstance(state.get("camera"), dict) else {}
        return {
            "camera_source_ok": bool(camera.get("camera_source_ok", False)),
            "camera_capture_ok": bool(camera.get("camera_capture_ok", False)),
            "camera_view_ok": bool(camera.get("camera_view_ok", False)),
            "frame_alignment_ok": bool(camera.get("frame_aligned", False)),
            "rgb_valid": bool(camera.get("rgb_valid", False)),
            "depth_valid": bool(camera.get("depth_valid", False)),
            "stub_frame_used": bool(camera.get("stub_frame_used", True)),
            "recording_ready": bool(precheck.get("recording_ready", False)),
            "episode_completed": bool(completed),
            "validation_time": _utc_timestamp(),
            "precheck_summary": list(precheck.get("summary", [])),
        }

    def _build_episode_result(self, request: DatasetEpisodeStopRequest) -> dict[str, Any]:
        return {
            "episode_id": request.episode_id,
            "result_status": _safe_text(request.result_status, "unknown"),
            "quality_label": request.quality_label,
            "notes": request.notes,
            "stopped_at": _utc_timestamp(),
        }

    def _default_instruction(self, task_type: str, class_id: str) -> str:
        template = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES["debug_trial"])
        by_class = template.get("default_instruction_by_class", {})
        if isinstance(by_class, dict):
            candidate = str(by_class.get(class_id, "")).strip()
            if candidate:
                return candidate
        return f"debug trial with the {class_id or 'tool'}"

    def _resolve_episode_dir(self, episode_id: str) -> Path | None:
        candidate = self._root / "raw" / str(episode_id)
        if (candidate / "metadata.json").exists():
            return candidate
        return None
