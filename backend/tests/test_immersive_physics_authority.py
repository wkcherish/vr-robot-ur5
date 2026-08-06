from __future__ import annotations

import unittest

from backend.sim.simulation import REPO_ROOT, SimulationCore


class ImmersivePhysicsAuthorityTest(unittest.TestCase):
    def _make_sim(self) -> SimulationCore:
        return SimulationCore(REPO_ROOT / "shared" / "scene_manifest.json")

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


if __name__ == "__main__":
    unittest.main()
