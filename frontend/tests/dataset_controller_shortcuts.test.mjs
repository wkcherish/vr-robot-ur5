import assert from "node:assert/strict";

import {
  readDatasetControllerShortcutValues,
  resolveDatasetControllerShortcutAction,
} from "../src/utils/datasetControllerShortcuts.js";
import { readQuestControllerSnapshotFromPads } from "../src/utils/questControllerInput.js";

function makePad({ hand = "left", pressed = [] } = {}) {
  const buttons = Array.from({ length: 6 }, (_, index) => ({
    pressed: pressed.includes(index),
    touched: pressed.includes(index),
    value: pressed.includes(index) ? 1 : 0,
  }));
  return {
    id: `Oculus Touch ${hand}`,
    hand,
    mapping: "xr-standard",
    connected: true,
    axes: [0, 0, 0, 0],
    buttons,
  };
}

const ySnapshot = readQuestControllerSnapshotFromPads(
  makePad({ hand: "left", pressed: [5] }),
  makePad({ hand: "right" }),
  "test"
);

assert.equal(
  ySnapshot.controls.dataset_start,
  1,
  "左手柄 Y 键应映射为 dataset_start，防止沉浸式采集无法从 VR 内启动"
);
assert.equal(
  ySnapshot.controls.dataset_reset,
  0,
  "只按 Y 键时不应误触发 reset"
);

const xSnapshot = readQuestControllerSnapshotFromPads(
  makePad({ hand: "left", pressed: [4] }),
  makePad({ hand: "right" }),
  "test"
);

assert.equal(
  xSnapshot.controls.dataset_reset,
  1,
  "左手柄 X 键应映射为 dataset_reset，用于一轮采集后的场景复原"
);
assert.equal(
  xSnapshot.controls.dataset_start,
  0,
  "只按 X 键时不应误触发 episode 开始"
);

const swappedReportedHandSnapshot = readQuestControllerSnapshotFromPads(
  makePad({ hand: "right", pressed: [5] }),
  makePad({ hand: "left", pressed: [4] }),
  "test"
);

assert.equal(
  swappedReportedHandSnapshot.raw.left.handedness,
  "left",
  "逻辑左手柄必须稳定标记为 left，不能被浏览器上报的反向 hand 字段覆盖"
);
assert.equal(
  swappedReportedHandSnapshot.raw.left.reported_handedness,
  "right",
  "原始浏览器 hand 字段应保存在 reported_handedness 中，便于后续排查设备上报异常"
);
assert.equal(
  swappedReportedHandSnapshot.raw.right.handedness,
  "right",
  "逻辑右手柄必须稳定标记为 right，防止 UI 和控制链路左右互换"
);

assert.deepEqual(
  readDatasetControllerShortcutValues({
    controls: { dataset_start: 0.4, dataset_reset: 0.2 },
    raw: { left: { dataset_start: 0.8, dataset_reset: 0.1 } },
  }),
  { start: 0.8, reset: 0.2 },
  "快捷键读取应取语义 controls 与 raw 兜底值中的最大值"
);

let action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 1, dataset_reset: 0 } },
  previousLatch: { start: false, reset: false },
  nowMs: 1000,
  lastActionAtMs: 0,
  canStartCollection: true,
  canStartEpisode: true,
  episodeActive: false,
  canResetScene: true,
});

assert.equal(action.action, "start_collection", "Y 键新按下且可启动时应开始连续采集流程");
assert.deepEqual(
  action.nextLatch,
  { start: true, reset: false },
  "解析后应返回新的按键锁存状态，避免长按重复触发"
);

action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 1, dataset_reset: 0 } },
  previousLatch: { start: true, reset: false },
  nowMs: 1200,
  lastActionAtMs: 0,
  canStartCollection: true,
  canStartEpisode: true,
  episodeActive: false,
  canResetScene: true,
});

assert.equal(action.action, "none", "Y 键保持按下时不应重复开始 episode");

action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 0, dataset_reset: 1 } },
  previousLatch: { start: false, reset: false },
  nowMs: 2000,
  lastActionAtMs: 0,
  autoCollecting: true,
  canStartEpisode: false,
  episodeActive: true,
  canResetScene: false,
});

assert.equal(
  action.action,
  "advance_collection",
  "连续采集时按 X 应标记本轮完成并进入停止/复原流程"
);

action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 0, dataset_reset: 1 } },
  previousLatch: { start: false, reset: false },
  nowMs: 2300,
  lastActionAtMs: 0,
  canStartEpisode: false,
  episodeActive: true,
  canResetScene: false,
});

assert.equal(
  action.action,
  "finish_episode_and_reset",
  "单 episode 活跃时按 X 应先结束当前轮再执行场景复原"
);

action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 0, dataset_reset: 1 } },
  previousLatch: { start: false, reset: false },
  nowMs: 2500,
  lastActionAtMs: 2200,
  canStartEpisode: false,
  episodeActive: false,
  canResetScene: true,
});

assert.equal(action.action, "none", "冷却时间内不应重复触发 X/Y 快捷键");

action = resolveDatasetControllerShortcutAction({
  snapshot: { controls: { dataset_start: 0, dataset_reset: 1 } },
  previousLatch: { start: false, reset: false },
  nowMs: 4000,
  lastActionAtMs: 0,
  canStartEpisode: false,
  episodeActive: false,
  canResetScene: true,
});

assert.equal(action.action, "reset_scene", "空闲时按 X 应直接随机复原场景");
