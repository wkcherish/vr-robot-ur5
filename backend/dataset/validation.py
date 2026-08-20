from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_SCHEMA_PATH = REPO_ROOT / "shared" / "dataset_schema.json"
DEFAULT_DATASET_ROOT = REPO_ROOT / "data" / "datasets" / "quest3_vr_lerobot_pi05_v1"

TRAINING_COLLECTION_STAGES = {"train_candidate", "eval_candidate"}
TRAINING_QUALITY_LABELS = {"train_candidate", "eval_candidate"}
DEBUG_OR_REJECTED_LABELS = {"debug_only", "debug_trial", "rejected"}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _read_jsonl(path: Path, limit: int | None = None) -> tuple[list[dict[str, Any]], int, list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    count = 0
    if not path.exists():
        return rows, count, errors
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            count += 1
            if limit is not None and len(rows) >= limit:
                continue
            try:
                parsed = json.loads(line)
            except Exception as exc:
                errors.append(f"{path.name}:{line_no}: invalid jsonl ({exc})")
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                errors.append(f"{path.name}:{line_no}: row is not an object")
    return rows, count, errors


def _required_layout(schema: dict[str, Any]) -> dict[str, str]:
    layout = schema.get("episode_layout") if isinstance(schema.get("episode_layout"), dict) else {}
    return {str(key): str(value) for key, value in layout.items() if value}


def _missing_fields(payload: dict[str, Any], required_fields: list[Any], prefix: str) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        field_name = str(field)
        if field_name not in payload:
            missing.append(f"{prefix}.{field_name} missing")
    return missing


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for child in path.iterdir() if child.is_file())


def _camera_source_forbidden(row: dict[str, Any], forbidden_sources: set[str]) -> bool:
    candidates = {
        str(row.get("camera_name") or "").strip(),
        str(row.get("camera_source") or "").strip(),
        str(row.get("source") or "").strip(),
    }
    candidates.discard("")
    return any(candidate in forbidden_sources for candidate in candidates)


def validate_raw_episode(
    episode_dir: str | Path,
    schema_path: str | Path = DEFAULT_DATASET_SCHEMA_PATH,
) -> dict[str, Any]:
    """Validate one raw Quest3 episode before LeRobot/OpenPI conversion.

    返回值中的 valid_for_training 表示“可进入训练格式转换候选”，不是 raw JSONL 可直接训练。
    """
    root = Path(episode_dir)
    schema = _load_json(Path(schema_path))
    layout = _required_layout(schema)
    blocking: list[str] = []
    warnings: list[str] = []

    required_files = [
        layout.get("metadata_file", "metadata.json"),
        layout.get("language_file", "language.json"),
        layout.get("visuals_file", "visuals.jsonl"),
        layout.get("states_file", "states.jsonl"),
        layout.get("actions_file", "actions.jsonl"),
        layout.get("relations_file", "relations.jsonl"),
        layout.get("events_file", "events.jsonl"),
        layout.get("phase_labels_file", "phase_labels.jsonl"),
        layout.get("result_file", "result.json"),
        layout.get("validation_summary_file", "validation_summary.json"),
    ]
    for filename in required_files:
        if filename and not (root / filename).exists():
            blocking.append(f"missing file: {filename}")

    metadata = _load_json(root / layout.get("metadata_file", "metadata.json"))
    result = _load_json(root / layout.get("result_file", "result.json"))
    validation = _load_json(root / layout.get("validation_summary_file", "validation_summary.json"))
    language = _load_json(root / layout.get("language_file", "language.json"))

    blocking.extend(_missing_fields(metadata, schema.get("metadata_required_fields", []), "metadata"))
    blocking.extend(_missing_fields(validation, schema.get("validation_summary_required_fields", []), "validation_summary"))

    task_type = str(metadata.get("task_type") or metadata.get("episode_type") or "").strip()
    collection_stage = str(metadata.get("collection_stage") or "").strip()
    quality_label = str(result.get("quality_label") or "").strip()
    result_status = str(result.get("result_status") or "").strip()
    scripted_collection = bool(metadata.get("scripted_collection", False))

    if task_type == "debug_trial":
        blocking.append("metadata.task_type=debug_trial")
    if collection_stage == "debug_trial":
        blocking.append("metadata.collection_stage=debug_trial")
    if collection_stage and collection_stage not in TRAINING_COLLECTION_STAGES:
        blocking.append(f"metadata.collection_stage={collection_stage}")
    if quality_label in DEBUG_OR_REJECTED_LABELS:
        blocking.append(f"result.quality_label={quality_label}")
    if quality_label and quality_label not in TRAINING_QUALITY_LABELS:
        blocking.append(f"result.quality_label={quality_label}")
    if result_status and result_status != "success":
        blocking.append(f"result.result_status={result_status}")
    if scripted_collection and collection_stage in TRAINING_COLLECTION_STAGES:
        blocking.append("metadata.scripted_collection=true")

    camera_checks = {
        "camera_source_ok": True,
        "camera_capture_ok": True,
        "camera_view_ok": True,
        "frame_alignment_ok": True,
        "rgb_valid": True,
        "depth_valid": True,
    }
    for key, expected in camera_checks.items():
        if bool(validation.get(key, False)) != expected:
            blocking.append(f"validation_summary.{key}=false")
    if bool(validation.get("stub_frame_used", True)):
        blocking.append("validation_summary.stub_frame_used=true")

    visuals, visual_count, visual_errors = _read_jsonl(root / layout.get("visuals_file", "visuals.jsonl"))
    states, state_count, state_errors = _read_jsonl(root / layout.get("states_file", "states.jsonl"))
    actions, action_count, action_errors = _read_jsonl(root / layout.get("actions_file", "actions.jsonl"))
    relations, relation_count, relation_errors = _read_jsonl(root / layout.get("relations_file", "relations.jsonl"))
    phases, phase_count, phase_errors = _read_jsonl(root / layout.get("phase_labels_file", "phase_labels.jsonl"))

    blocking.extend(visual_errors)
    blocking.extend(state_errors)
    blocking.extend(action_errors)
    blocking.extend(relation_errors)
    blocking.extend(phase_errors)

    if visual_count <= 0:
        blocking.append("visuals.jsonl has no samples")
    if state_count <= 0:
        blocking.append("states.jsonl has no samples")
    if action_count <= 0:
        blocking.append("actions.jsonl has no samples")
    if relation_count <= 0:
        blocking.append("relations.jsonl has no samples")
    if phase_count <= 0:
        blocking.append("phase_labels.jsonl has no samples")
    if visual_count != state_count:
        blocking.append(f"visual/state count mismatch: {visual_count}!={state_count}")
    if action_count > state_count:
        blocking.append(f"action count exceeds state count: {action_count}>{state_count}")

    for index, row in enumerate(visuals[:3]):
        blocking.extend(_missing_fields(row, schema.get("visual_sample_required_fields", []), f"visuals[{index}]"))
    for index, row in enumerate(states[:3]):
        blocking.extend(_missing_fields(row, schema.get("state_sample_required_fields", []), f"states[{index}]"))
    for index, row in enumerate(actions[:3]):
        blocking.extend(_missing_fields(row, schema.get("action_sample_required_fields", []), f"actions[{index}]"))

    visual_frame_ids = {str(row.get("frame_id") or row.get("d405_frame_id") or "") for row in visuals}
    visual_frame_ids.discard("")
    for index, action in enumerate(actions):
        paired_frame_id = str(action.get("paired_frame_id") or "").strip()
        if not paired_frame_id:
            blocking.append(f"actions[{index}].paired_frame_id missing")
        elif paired_frame_id not in visual_frame_ids:
            blocking.append(f"actions[{index}].paired_frame_id not in visuals: {paired_frame_id}")
        if action.get("valid_for_training") is False:
            blocking.append(f"actions[{index}].valid_for_training=false")

    forbidden_sources = {
        str(item)
        for item in schema.get("camera_source_policy", {}).get("forbidden_training_sources", [])
        if str(item).strip()
    }
    for index, visual in enumerate(visuals):
        if _camera_source_forbidden(visual, forbidden_sources):
            blocking.append(f"visuals[{index}].camera_source forbidden")
        rgb_path = str(visual.get("rgb_path") or "").strip()
        depth_path = str(visual.get("depth_path") or "").strip()
        if rgb_path and not (root / rgb_path).exists():
            blocking.append(f"visuals[{index}].rgb_path missing on disk: {rgb_path}")
        if depth_path and not (root / depth_path).exists():
            blocking.append(f"visuals[{index}].depth_path missing on disk: {depth_path}")

    instruction = str(metadata.get("instruction_text") or "").strip()
    language_instruction = str(language.get("instruction_text") or language.get("text") or "").strip()
    if not instruction:
        blocking.append("metadata.instruction_text empty")
    if language and language_instruction and instruction and language_instruction != instruction:
        warnings.append("language.instruction_text differs from metadata.instruction_text")

    counts = {
        "visuals": visual_count,
        "states": state_count,
        "actions": action_count,
        "relations": relation_count,
        "phase_labels": phase_count,
        "rgb_frames": _count_files(root / layout.get("rgb_dir", "rgb")),
        "depth_frames": _count_files(root / layout.get("depth_dir", "depth")),
    }
    return {
        "episode_id": str(metadata.get("episode_id") or root.name),
        "episode_dir": str(root),
        "valid_for_training": len(blocking) == 0,
        "conversion_required": True,
        "blocking_issues": sorted(set(blocking)),
        "warnings": sorted(set(warnings)),
        "counts": counts,
        "collection_stage": collection_stage,
        "quality_label": quality_label,
        "result_status": result_status,
    }


def validate_raw_dataset(
    dataset_root: str | Path = DEFAULT_DATASET_ROOT,
    schema_path: str | Path = DEFAULT_DATASET_SCHEMA_PATH,
) -> dict[str, Any]:
    root = Path(dataset_root)
    raw_root = root / "raw" if (root / "raw").exists() else root
    episode_dirs = sorted(
        path for path in raw_root.iterdir() if path.is_dir() and (path / "metadata.json").exists()
    ) if raw_root.exists() else []
    episodes = [validate_raw_episode(path, schema_path=schema_path) for path in episode_dirs]
    valid = [episode for episode in episodes if episode.get("valid_for_training")]
    invalid = [episode for episode in episodes if not episode.get("valid_for_training")]
    return {
        "dataset_root": str(root),
        "episode_count": len(episodes),
        "valid_episode_count": len(valid),
        "invalid_episode_count": len(invalid),
        "valid_episode_ids": [str(episode.get("episode_id")) for episode in valid],
        "invalid_episode_ids": [str(episode.get("episode_id")) for episode in invalid],
        "episodes": episodes,
        "conversion_required": True,
        "notes": "raw JSONL 不能直接训练 pi0.5/SmolVLA；必须先转换为 LeRobot/OpenPI 格式并通过 loader smoke test。",
    }
