import assert from "node:assert/strict";

import {
  buildDatasetSceneResetPayload,
  buildDesktopSceneRestorePayload,
  shouldDisableDesktopSceneRestore,
} from "../src/utils/sceneRestoreControl.js";

assert.equal(
  shouldDisableDesktopSceneRestore({
    sceneRestorePending: false,
    datasetEpisodeActive: true,
    datasetEpisodeInFlight: true,
    datasetAutoCollecting: true,
  }),
  false,
  "桌面恢复初始场景按钮不应被数据集 episode 或连续采集状态禁用"
);

assert.equal(
  shouldDisableDesktopSceneRestore({ sceneRestorePending: true }),
  true,
  "桌面恢复初始场景进行中应禁用按钮，避免重复提交 reset"
);

assert.deepEqual(
  buildDesktopSceneRestorePayload(),
  {
    reload_model: true,
    preserve_vr_state: false,
    randomize_scene_objects: false,
  },
  "桌面恢复初始场景应恢复固定初始位置，不应触发数据集随机摆放"
);

assert.deepEqual(
  buildDatasetSceneResetPayload(),
  {
    reload_model: false,
    preserve_vr_state: true,
    settle_steps: 120,
    randomize_scene_objects: true,
  },
  "沉浸式数据采集 reset 应保留 VR 状态并随机工具位置"
);
