from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.dataset.collection import DatasetCollectionService
from backend.dataset.validation import validate_raw_dataset, validate_raw_episode


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _create_episode(root: Path, episode_id: str, *, debug: bool = False, include_required_sidecars: bool = True) -> Path:
    episode_dir = root / "raw" / episode_id
    stage = "debug_trial" if debug else "train_candidate"
    task_type = "debug_trial" if debug else "tool_pick_place"
    _write_json(
        episode_dir / "metadata.json",
        {
            "task_id": "quest3_vr_lerobot_pi05_v1",
            "session_id": "session_test",
            "episode_id": episode_id,
            "captured_at": "2026-08-20T00:00:00Z",
            "input_mode": "vr_controller",
            "input_source": "quest3_controller",
            "runtime_target": "mujoco",
            "instruction_text": "place the wrench in the toolbox",
            "collection_stage": stage,
            "episode_type": task_type,
            "task_type": task_type,
            "handover_object_id": "wrench_01",
            "handover_object_class": "wrench",
            "handover_zone_id": "slot_wrench",
            "camera_device": "intel_realsense_d405",
            "camera_mount_name": "wrist_d405_mount",
            "camera_intrinsics_version": "test_intrinsics",
            "camera_extrinsics_version": "test_extrinsics",
        },
    )
    _write_json(episode_dir / "language.json", {"instruction_text": "place the wrench in the toolbox"})
    _write_json(
        episode_dir / "validation_summary.json",
        {
            "camera_source_ok": not debug,
            "camera_capture_ok": not debug,
            "camera_view_ok": not debug,
            "frame_alignment_ok": not debug,
            "rgb_valid": not debug,
            "depth_valid": not debug,
            "stub_frame_used": debug,
            "episode_completed": True,
            "recording_ready": not debug,
            "files_complete": include_required_sidecars,
        },
    )
    _write_json(
        episode_dir / "result.json",
        {
            "episode_id": episode_id,
            "result_status": "success",
            "quality_label": "debug_only" if debug else "train_candidate",
        },
    )
    for index in range(3):
        (episode_dir / "rgb").mkdir(parents=True, exist_ok=True)
        (episode_dir / "depth").mkdir(parents=True, exist_ok=True)
        (episode_dir / "rgb" / f"d405_{index:06d}.jpg").write_bytes(b"rgb")
        (episode_dir / "depth" / f"d405_{index:06d}.png").write_bytes(b"depth")
    visuals = [
        {
            "timestamp": index,
            "frame_id": f"d405_{index:06d}",
            "d405_frame_id": f"d405_{index:06d}",
            "rgb_path": f"rgb/d405_{index:06d}.jpg",
            "depth_path": f"depth/d405_{index:06d}.png",
            "rgb_timestamp": index,
            "depth_timestamp": index,
            "frame_aligned": True,
            "camera_pose_in_ee": {},
            "camera_pose_in_base": {},
            "rgb_missing": False,
            "depth_missing": False,
            "rgb_valid": True,
            "depth_valid": True,
            "camera_source_ok": True,
            "stub_frame_used": False,
            "visual_valid": True,
            "camera_name": "d405_rgb",
        }
        for index in range(3)
    ]
    states = [
        {
            "timestamp": index,
            "sim_time": index * 0.02,
            "qpos": [0.0] * 7,
            "qvel": [0.0] * 6,
            "ee_pose": {},
            "gripper_opening": 0.0,
            "objects": {},
            "camera_capture_ok": True,
            "d405_frame_id": f"d405_{index:06d}",
            "camera_observation": {"camera_view_ok": True},
            "instruction_text": "place the wrench in the toolbox",
        }
        for index in range(3)
    ]
    actions = [
        {
            "command_timestamp": index,
            "ack_timestamp": index,
            "target_positions": [0.0] * 6,
            "gripper_command": {"mode": "open_close", "value": 0.0},
            "input_mode": "vr_controller",
            "runtime_target": "mujoco",
            "paired_frame_id": f"d405_{index:06d}",
            "instruction_text": "place the wrench in the toolbox",
            "valid_for_training": True,
        }
        for index in range(2)
    ]
    _append_jsonl(episode_dir / "visuals.jsonl", visuals)
    _append_jsonl(episode_dir / "states.jsonl", states)
    _append_jsonl(episode_dir / "actions.jsonl", actions)
    _append_jsonl(episode_dir / "events.jsonl", [{"event_type": "episode_stop"}])
    if include_required_sidecars:
        _append_jsonl(episode_dir / "relations.jsonl", [{"relation_type": "target_slot", "object_id": "wrench_01"}])
        _append_jsonl(episode_dir / "phase_labels.jsonl", [{"phase": "place", "start_frame_id": "d405_000000"}])
    return episode_dir


class DatasetValidationTest(unittest.TestCase):
    def test_debug_or_incomplete_episode_is_blocked_from_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode_dir = _create_episode(Path(tmp), "episode_debug", debug=True, include_required_sidecars=False)

            report = validate_raw_episode(episode_dir)

        self.assertFalse(report["valid_for_training"])
        self.assertIn("metadata.collection_stage=debug_trial", report["blocking_issues"])
        self.assertIn("result.quality_label=debug_only", report["blocking_issues"])
        self.assertIn("missing file: relations.jsonl", report["blocking_issues"])
        self.assertIn("validation_summary.camera_view_ok=false", report["blocking_issues"])

    def test_complete_train_candidate_episode_is_convertible_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode_dir = _create_episode(Path(tmp), "episode_train")

            report = validate_raw_episode(episode_dir)

        self.assertTrue(report["valid_for_training"])
        self.assertEqual(report["blocking_issues"], [])
        self.assertEqual(report["counts"]["visuals"], 3)
        self.assertEqual(report["counts"]["actions"], 2)

    def test_dataset_report_summarizes_trainable_and_rejected_episodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_episode(root, "episode_train")
            _create_episode(root, "episode_debug", debug=True, include_required_sidecars=False)

            report = validate_raw_dataset(root)

        self.assertEqual(report["episode_count"], 2)
        self.assertEqual(report["valid_episode_count"], 1)
        self.assertEqual(report["invalid_episode_count"], 1)

    def test_new_episode_layout_creates_schema_sidecar_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            episode_dir = Path(tmp) / "raw" / "episode_new"
            service = DatasetCollectionService(root=Path(tmp))

            service._create_episode_layout(episode_dir)

            self.assertTrue((episode_dir / "relations.jsonl").exists())
            self.assertTrue((episode_dir / "phase_labels.jsonl").exists())

    def test_toolbox_target_zones_expose_local_collision_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DatasetCollectionService(root=Path(tmp))

            zones = {zone["id"]: zone for zone in service.get_templates()["target_zones"]}

        wrench_slot = zones["slot_wrench"]
        self.assertEqual(wrench_slot["frame"], "toolbox_local")
        self.assertEqual(wrench_slot["position"], [-0.055, -0.006, 0.052])
        self.assertEqual(wrench_slot["size"], [0.09, 0.03, 0.03])
        self.assertEqual(wrench_slot["collision_margin_m"], 0.004)


if __name__ == "__main__":
    unittest.main()
