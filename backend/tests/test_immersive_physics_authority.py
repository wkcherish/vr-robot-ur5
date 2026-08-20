from __future__ import annotations

import unittest
import asyncio
from copy import deepcopy
from math import pi, sqrt
from unittest.mock import patch

from backend.sim.simulation import REPO_ROOT, SimulationCore


class ImmersivePhysicsAuthorityTest(unittest.TestCase):
    def _make_sim(self) -> SimulationCore:
        return SimulationCore(REPO_ROOT / "shared" / "scene_manifest.json")

    class _FakeArray(list):
        def __setitem__(self, key, value):
            if isinstance(key, slice) and isinstance(value, (int, float)):
                start, stop, step = key.indices(len(self))
                indexes = range(start, stop, step)
                for index in indexes:
                    super().__setitem__(index, float(value))
                return
            super().__setitem__(key, value)

        def copy(self):
            return ImmersivePhysicsAuthorityTest._FakeArray(self)

    class _FakeMjData:
        def __init__(self) -> None:
            self.qpos = ImmersivePhysicsAuthorityTest._FakeArray([0.0] * 14)
            self.qvel = ImmersivePhysicsAuthorityTest._FakeArray([0.0] * 12)
            self.ctrl = ImmersivePhysicsAuthorityTest._FakeArray([])
            self.act = ImmersivePhysicsAuthorityTest._FakeArray([])
            self.xpos = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
            self.xquat = [[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]

    class _FakeMjModel:
        def __init__(self) -> None:
            self.actuator_actadr = []

    class _FakeMujoco:
        @staticmethod
        def mj_forward(model, data) -> None:
            data.xpos[0] = [float(value) for value in data.qpos[0:3]]
            data.xquat[0] = [float(value) for value in data.qpos[3:7]]
            data.xpos[1] = [float(value) for value in data.qpos[7:10]]
            data.xquat[1] = [float(value) for value in data.qpos[10:14]]

        @staticmethod
        def mj_step(model, data) -> None:
            # 模拟物理 settle 中碰撞/重力把固定工具箱带偏。
            data.qpos[0] += 0.5
            data.qpos[1] += 0.5
            data.qpos[2] += 0.5
            ImmersivePhysicsAuthorityTest._FakeMujoco.mj_forward(model, data)

    def test_quest_sources_disable_grasp_assist_attachment_even_when_env_enabled(self) -> None:
        sim = self._make_sim()
        sim._source = "quest3_controller"
        sim._last_input_source = "quest3_controller"
        sim._gripper_opening = 1.0
        sim._scene_objects_template = {
            "wrench_01": {
                "position": [0.0, 0.0, 0.0],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
                "attached_to_gripper": True,
            }
        }
        sim._compute_gripper_grasp_pose_locked = lambda: {
            "position": [0.0, 0.0, 0.0],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
        }
        sim._find_contacted_graspable_object_locked = lambda: "wrench_01"
        sim._follow_attached_object_locked = lambda forward=True: None

        sim._update_grasp_assist_locked(forward=False)

        self.assertIsNone(sim._attached_object_id)
        self.assertIsNone(sim._attached_object_rel_position)
        self.assertIsNone(sim._attached_object_rel_quaternion)
        self.assertFalse(sim._scene_objects_template["wrench_01"]["attached_to_gripper"])

    def test_motion_state_omits_full_object_payload_from_high_rate_stream(self) -> None:
        sim = self._make_sim()
        sim._objects_state = {
            "wrench_01": {
                "position": [1.0, 2.0, 3.0],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
                "attached_to_gripper": False,
            }
        }

        state = sim._build_motion_state_locked()

        self.assertNotIn("objects", state)

    def test_dataset_reset_keeps_toolbox_fixed_and_randomizes_real_tools(self) -> None:
        sim = self._make_sim()

        self.assertEqual(sim._object_reset_policy["toolbox"].get("mode"), "fixed")
        self.assertEqual(sim._object_reset_policy["wrench_01"].get("mode"), "random_in_region")
        self.assertEqual(sim._object_reset_policy["screwdriver_01"].get("mode"), "random_in_region")
        self.assertEqual(sim._object_reset_policy["pliers_01"].get("mode"), "random_in_region")
        self.assertEqual(sim._object_reset_policy["wrench_01"].get("region_id"), "wrench_workspace_region")
        self.assertEqual(sim._object_reset_policy["screwdriver_01"].get("region_id"), "screwdriver_workspace_region")
        self.assertEqual(sim._object_reset_policy["pliers_01"].get("region_id"), "pliers_workspace_region")
        self.assertTrue(sim._object_reset_policy["wrench_01"].get("random_yaw"))
        self.assertTrue(sim._object_reset_policy["screwdriver_01"].get("random_yaw"))
        self.assertTrue(sim._object_reset_policy["pliers_01"].get("random_yaw"))

    def test_random_tool_reset_preserves_table_height_and_applies_yaw(self) -> None:
        sim = self._make_sim()
        sim._model_backend = "stub"
        sim._spawn_regions = {
            "unit_region": {
                "frame": "backend",
                "min": [1.0, 2.0, 3.0],
                "max": [1.0, 2.0, 3.0],
            }
        }
        sim._object_reset_policy = {
            "wrench_01": {
                "mode": "random_in_region",
                "region_id": "unit_region",
                "preserve_height": True,
                "random_yaw": True,
            }
        }
        sim._scene_objects_template = {
            "wrench_01": {
                "position": [0.0, 0.0, 0.5],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
                "attached_to_gripper": True,
            }
        }

        with patch("backend.sim.simulation.random.uniform", side_effect=[1.0, 2.0, 3.0, pi / 2]):
            sim._apply_object_reset_policy_locked()

        self.assertEqual(sim._scene_objects_template["wrench_01"]["position"], [1.0, 2.0, 0.5])
        self.assertFalse(sim._scene_objects_template["wrench_01"]["attached_to_gripper"])
        self.assertAlmostEqual(sim._scene_objects_template["wrench_01"]["quaternion"][0], sqrt(0.5), places=6)
        self.assertAlmostEqual(sim._scene_objects_template["wrench_01"]["quaternion"][3], sqrt(0.5), places=6)

    def test_fast_dataset_reset_preserves_vr_state_and_skips_model_reload(self) -> None:
        sim = self._make_sim()
        sim._vr_state["mode"] = "vr_controller_mode"
        sim._vr_state["control_owner"] = "quest3_controller"
        sim._vr_state["input_source_available"]["controller"] = True
        sim._vr_state["selected_joint_group"] = "end_effector"
        reload_calls = 0

        def fail_on_reload(model_path: str | None = None) -> None:
            nonlocal reload_calls
            reload_calls += 1
            raise AssertionError("fast dataset reset should not reload the MuJoCo model")

        sim._load_model = fail_on_reload

        state = asyncio.run(
            sim.reset(
                model_path=None,
                reload_model=False,
                preserve_vr_state=True,
                settle_steps=0,
            )
        )

        self.assertEqual(reload_calls, 0)
        self.assertEqual(state["vr"]["mode"], "vr_controller_mode")
        self.assertEqual(state["vr"]["control_owner"], "quest3_controller")
        self.assertTrue(state["vr"]["input_source_available"]["controller"])
        self.assertEqual(state["vr"]["selected_joint_group"], "end_effector")

    def test_default_reset_restores_manifest_positions_without_randomizing_tools(self) -> None:
        sim = self._make_sim()
        sim._model_backend = "stub"
        initial_wrench_position = list(sim._scene_objects_template["wrench_01"]["position"])
        sim._scene_objects_template["wrench_01"]["position"] = [9.0, 9.0, 9.0]

        with patch("backend.sim.simulation.random.uniform", return_value=0.123):
            state = asyncio.run(sim.reset(reload_model=False, settle_steps=0))

        self.assertEqual(state["objects"]["wrench_01"]["position"], initial_wrench_position)

    def test_dataset_reset_can_randomize_tools_without_reloading_model(self) -> None:
        sim = self._make_sim()
        sim._model_backend = "stub"
        initial_wrench_position = list(sim._scene_objects_template["wrench_01"]["position"])

        with patch("backend.sim.simulation.random.uniform", return_value=0.123):
            state = asyncio.run(
                sim.reset(
                    reload_model=False,
                    preserve_vr_state=True,
                    settle_steps=0,
                    randomize_scene_objects=True,
                )
            )

        self.assertNotEqual(state["objects"]["wrench_01"]["position"], initial_wrench_position)

    def test_dataset_random_reset_keeps_toolbox_at_manifest_pose_during_settle(self) -> None:
        sim = self._make_sim()
        toolbox_pose = {
            "position": [0.48, 0.2, 1.0],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
            "attached_to_gripper": False,
        }
        wrench_pose = {
            "position": [0.08, -0.3, 1.02],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
            "attached_to_gripper": False,
        }
        sim._model_backend = "mujoco"
        sim._mj_model = self._FakeMjModel()
        sim._mj_data = self._FakeMjData()
        sim._scene_objects_manifest_template = {
            "toolbox": deepcopy(toolbox_pose),
            "wrench_01": deepcopy(wrench_pose),
        }
        sim._scene_objects_template = deepcopy(sim._scene_objects_manifest_template)
        sim._object_body_ids = {"toolbox": 0, "wrench_01": 1}
        sim._object_freejoint_qpos_addr = {"toolbox": 0, "wrench_01": 7}
        sim._object_freejoint_dof_addr = {"toolbox": 0, "wrench_01": 6}
        sim._object_reset_policy = {
            "toolbox": {"mode": "fixed"},
            "wrench_01": {
                "mode": "random_in_region",
                "region_id": "unit_region",
                "random_yaw": False,
            },
        }
        sim._spawn_regions = {
            "unit_region": {
                "frame": "backend",
                "min": [2.0, 2.0, 2.0],
                "max": [2.0, 2.0, 2.0],
            }
        }

        with patch("backend.sim.simulation._mujoco", self._FakeMujoco()):
            state = asyncio.run(
                sim.reset(
                    reload_model=False,
                    preserve_vr_state=True,
                    settle_steps=1,
                    randomize_scene_objects=True,
                )
            )

        self.assertEqual(state["objects"]["toolbox"]["position"], toolbox_pose["position"])
        self.assertEqual(state["objects"]["toolbox"]["quaternion"], toolbox_pose["quaternion"])
        self.assertEqual(state["objects"]["wrench_01"]["position"], [2.0, 2.0, 2.0])


if __name__ == "__main__":
    unittest.main()
