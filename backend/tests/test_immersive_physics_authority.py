from __future__ import annotations

import unittest
import asyncio
import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from math import cos, pi, sin, sqrt
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

    def test_all_control_sources_disable_legacy_grasp_attachment_even_when_env_enabled(self) -> None:
        sim = self._make_sim()
        sim._source = "desktop_manual"
        sim._last_input_source = "slider"
        sim._attached_object_id = "wrench_01"
        sim._attached_object_rel_position = [0.0, 0.0, 0.0]
        sim._attached_object_rel_quaternion = [1.0, 0.0, 0.0, 0.0]
        sim._scene_objects_template = {
            "wrench_01": {
                "position": [0.0, 0.0, 0.0],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
                "attached_to_gripper": True,
            }
        }

        with patch("backend.sim.simulation.GRASP_ASSIST_MODE", "enabled"):
            self.assertFalse(sim._allows_grasp_assist_locked())
            sim._update_grasp_assist_locked(forward=False)

        self.assertIsNone(sim._attached_object_id)
        self.assertIsNone(sim._attached_object_rel_position)
        self.assertIsNone(sim._attached_object_rel_quaternion)
        self.assertFalse(sim._scene_objects_template["wrench_01"]["attached_to_gripper"])

    def test_legacy_grasp_attach_helpers_are_defensive_noops(self) -> None:
        sim = self._make_sim()
        sim._scene_objects_template = {
            "wrench_01": {
                "position": [1.0, 2.0, 3.0],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
                "attached_to_gripper": False,
            }
        }

        attached = sim._attach_object_to_gripper_locked(
            "wrench_01",
            {
                "position": [0.0, 0.0, 0.0],
                "quaternion": [1.0, 0.0, 0.0, 0.0],
            },
        )
        sim._attached_object_id = "wrench_01"
        sim._attached_object_rel_position = [0.0, 0.0, 0.0]
        sim._attached_object_rel_quaternion = [1.0, 0.0, 0.0, 0.0]
        sim._follow_attached_object_locked(forward=False)

        self.assertFalse(attached)
        self.assertIsNone(sim._attached_object_id)
        self.assertEqual(sim._scene_objects_template["wrench_01"]["position"], [1.0, 2.0, 3.0])
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

    def test_toolbox_slots_are_defined_in_mujoco_local_collision_space(self) -> None:
        catalog = json.loads((REPO_ROOT / "shared" / "tool_catalog.json").read_text(encoding="utf-8"))
        manifest = json.loads((REPO_ROOT / "shared" / "scene_manifest.json").read_text(encoding="utf-8"))
        toolbox = next(obj for obj in manifest["objects"] if obj["id"] == "toolbox")
        proxies = {proxy["name"]: proxy for proxy in toolbox["physics"]["collision_proxies"]}
        left_wall = proxies["toolbox_left_wall_collision"]
        right_wall = proxies["toolbox_right_wall_collision"]
        front_wall = proxies["toolbox_front_wall_collision"]
        back_wall = proxies["toolbox_back_wall_collision"]
        bottom = proxies["toolbox_bottom_collision"]

        inner_x_min = left_wall["position"][0] + left_wall["size"][0]
        inner_x_max = right_wall["position"][0] - right_wall["size"][0]
        inner_y_min = front_wall["position"][1] + front_wall["size"][1]
        inner_y_max = back_wall["position"][1] - back_wall["size"][1]
        floor_top_z = bottom["position"][2] + bottom["size"][2]
        wall_top_z = left_wall["position"][2] + left_wall["size"][2]

        for slot in catalog["toolbox_slots"]:
            with self.subTest(slot=slot["slot_id"]):
                self.assertEqual(slot.get("frame"), "toolbox_local")
                position = slot["position"]
                size = slot["size"]
                margin = float(slot.get("collision_margin_m", 0.0))
                self.assertGreaterEqual(position[0] - size[0] * 0.5, inner_x_min + margin)
                self.assertLessEqual(position[0] + size[0] * 0.5, inner_x_max - margin)
                self.assertGreaterEqual(position[1] - size[1] * 0.5, inner_y_min + margin)
                self.assertLessEqual(position[1] + size[1] * 0.5, inner_y_max - margin)
                self.assertGreaterEqual(position[2] - size[2] * 0.5, floor_top_z + margin)
                self.assertLessEqual(position[2] + size[2] * 0.5, wall_top_z - margin)

    def test_tool_initial_collision_proxies_start_clear_of_tabletop(self) -> None:
        manifest = json.loads((REPO_ROOT / "shared" / "scene_manifest.json").read_text(encoding="utf-8"))
        objects = {obj["id"]: obj for obj in manifest["objects"]}
        rack = objects["rack"]
        tabletop = next(proxy for proxy in rack["physics"]["collision_proxies"] if proxy["name"] == "rack_tabletop_collision")
        tabletop_y = rack["transform"]["position"][1] + tabletop["position"][1] + tabletop["size"][1]

        for obj in manifest["objects"]:
            if obj.get("object_type") != "tool":
                continue
            with self.subTest(obj_id=obj["id"]):
                min_y = self._min_frontend_collision_y(obj)
                self.assertGreaterEqual(
                    min_y - tabletop_y,
                    0.002,
                    "工具初始碰撞体必须略高于桌面，避免 MuJoCo 初始穿透后把零件弹起/翻起。",
                )

    def test_tool_manifest_positions_match_mujoco_xml_initial_positions(self) -> None:
        manifest = json.loads((REPO_ROOT / "shared" / "scene_manifest.json").read_text(encoding="utf-8"))
        for obj in manifest["objects"]:
            if obj.get("object_type") != "tool":
                continue
            with self.subTest(obj_id=obj["id"]):
                xml_path = REPO_ROOT / obj["physics"]["source"]
                body = ET.parse(xml_path).getroot().find(f".//body[@name='{obj['id']}']")
                self.assertIsNotNone(body)
                xml_pos = [float(value) for value in body.attrib["pos"].split()]
                frontend_pos = obj["transform"]["position"]
                expected_backend = [frontend_pos[0], -frontend_pos[2], frontend_pos[1] + 0.5]
                for actual, expected in zip(xml_pos, expected_backend):
                    self.assertAlmostEqual(actual, expected, places=6)

    def _min_frontend_collision_y(self, obj: dict) -> float:
        base = obj["transform"]["position"]
        rotation = obj["transform"].get("rotation_rpy", [0.0, 0.0, 0.0])
        min_y = float("inf")
        for proxy in obj["physics"].get("collision_proxies", []):
            for point in self._proxy_points(proxy):
                rotated = self._rotate_xyz(point, rotation)
                min_y = min(min_y, float(base[1]) + rotated[1])
        return min_y

    def _proxy_points(self, proxy: dict) -> list[list[float]]:
        if proxy.get("type") == "box":
            return self._box_points(proxy["position"], proxy["size"])
        if proxy.get("type") == "capsule":
            radius = float(proxy["size"][0])
            fromto = proxy["fromto"]
            return self._box_points(fromto[0:3], [radius, radius, radius]) + self._box_points(
                fromto[3:6],
                [radius, radius, radius],
            )
        return []

    def _box_points(self, center: list[float], half_size: list[float]) -> list[list[float]]:
        return [
            [
                float(center[0]) + sx * float(half_size[0]),
                float(center[1]) + sy * float(half_size[1]),
                float(center[2]) + sz * float(half_size[2]),
            ]
            for sx in (-1.0, 1.0)
            for sy in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]

    def _rotate_xyz(self, point: list[float], rotation: list[float]) -> list[float]:
        x, y, z = [float(value) for value in point]
        rx, ry, rz = [float(value) for value in rotation[:3]]
        cy, sy = cos(rx), sin(rx)
        y, z = y * cy - z * sy, y * sy + z * cy
        cy, sy = cos(ry), sin(ry)
        x, z = x * cy + z * sy, -x * sy + z * cy
        cy, sy = cos(rz), sin(rz)
        x, y = x * cy - y * sy, x * sy + y * cy
        return [x, y, z]

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
