import assert from "node:assert/strict";

import { createQuestControllerTeleop } from "../src/utils/questControllerTeleop.js";
import { createQuestHandTeleop } from "../src/utils/questHandTeleop.js";

const CURRENT_EE_POSE = {
  position: [0.0, 0.0, 1.0],
  quaternion: [1.0, 0.0, 0.0, 0.0],
};
const CURRENT_ARM = [0, 0, 0, 0, 0, 0];
const FRONTEND_IDENTITY_QUAT_XYZW = [0, 0, 0, 1];

function controllerSnapshot(timestampMs = 0) {
  return {
    available: true,
    has_device: true,
    timestamp_ms: timestampMs,
    controls: {
      active_hand: "right",
      right_grip: 1,
      right_trigger: 0,
      precision: 0,
    },
  };
}

function controllerPose(frontendY) {
  return {
    right: {
      tracked: true,
      handedness: "right",
      position: [0, frontendY, 0],
      quaternion: FRONTEND_IDENTITY_QUAT_XYZW,
      pose_source: "test",
    },
  };
}

function handSnapshot(frontendY, timestampMs = 0) {
  return {
    available: true,
    timestamp_ms: timestampMs,
    tracking_stability: 0.9,
    hands: {
      right: {
        tracked: true,
        recently_tracked: true,
        stability: 0.9,
        fist: 0,
        palm_position: [0, frontendY, 0],
        palm_quaternion: FRONTEND_IDENTITY_QUAT_XYZW,
      },
    },
    raw: {
      right: {
        raw_joints: {
          thumb: [0, frontendY, 0],
          index: [0, frontendY, 0],
        },
      },
    },
  };
}

function applyControllerFrames(teleop, frontendY) {
  let result = null;
  for (let index = 0; index < 8; index += 1) {
    result = teleop.applySnapshot(
      controllerSnapshot(100 + index * 100),
      controllerPose(frontendY),
      0,
      CURRENT_EE_POSE,
      CURRENT_ARM,
      0.1
    );
  }
  return result;
}

function applyHandFrames(teleop, frontendY) {
  let result = null;
  for (let index = 0; index < 8; index += 1) {
    result = teleop.applySnapshot(
      handSnapshot(frontendY, 100 + index * 100),
      CURRENT_ARM,
      0,
      CURRENT_EE_POSE,
      0.1
    );
  }
  return result;
}

const controllerTeleop = createQuestControllerTeleop();
applyControllerFrames(controllerTeleop, 1.0);
const controllerDown = applyControllerFrames(controllerTeleop, 0.4);

assert.ok(controllerDown.has_command, "手柄下探时应持续输出 EE servo 命令");
assert.ok(
  controllerDown.target_ee_pose.position[2] <= 0.5,
  "手柄模式应允许至少 0.5m 的后端 Z 下探，避免扳手抓取高度被偏移限制卡住"
);

const handTeleop = createQuestHandTeleop();
applyHandFrames(handTeleop, 1.0);
const handDown = applyHandFrames(handTeleop, 0.4);

assert.ok(handDown.has_command, "手势下探时应持续输出 EE servo 命令");
assert.ok(
  handDown.target_ee_pose.position[2] <= 0.5,
  "手势模式应允许至少 0.5m 的后端 Z 下探，避免扳手抓取高度被偏移限制卡住"
);
