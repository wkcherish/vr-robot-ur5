export const DATASET_CONTROLLER_SHORTCUT_THRESHOLD = 0.65;
export const DATASET_CONTROLLER_SHORTCUT_COOLDOWN_MS = 900;

function clamp01(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(numeric, 0), 1);
}

function maxFinite(values) {
  const finiteValues = values.map((value) => Number(value)).filter((value) => Number.isFinite(value));
  if (finiteValues.length === 0) return 0;
  return clamp01(Math.max(...finiteValues));
}

export function readDatasetControllerShortcutValues(snapshot) {
  return {
    start: maxFinite([
      snapshot?.controls?.dataset_start,
      snapshot?.raw?.left?.dataset_start,
    ]),
    reset: maxFinite([
      snapshot?.controls?.dataset_reset,
      snapshot?.raw?.left?.dataset_reset,
    ]),
  };
}

export function resolveDatasetControllerShortcutAction({
  snapshot,
  previousLatch = {},
  nowMs = Date.now(),
  lastActionAtMs = 0,
  threshold = DATASET_CONTROLLER_SHORTCUT_THRESHOLD,
  cooldownMs = DATASET_CONTROLLER_SHORTCUT_COOLDOWN_MS,
  autoCollecting = false,
  canStartCollection = false,
  canStartEpisode = false,
  episodeActive = false,
  canResetScene = false,
} = {}) {
  const values = readDatasetControllerShortcutValues(snapshot);
  const startPressed = values.start >= threshold;
  const resetPressed = values.reset >= threshold;
  const nextLatch = {
    start: startPressed,
    reset: resetPressed,
  };

  const startEdge = startPressed && !previousLatch.start;
  const resetEdge = resetPressed && !previousLatch.reset;
  const elapsedMs = Number(nowMs) - Number(lastActionAtMs || 0);
  if (Number.isFinite(elapsedMs) && elapsedMs < cooldownMs) {
    return { action: "none", nextLatch, values };
  }

  // 连续采集流程里 X 是“本轮完成”的确认键，由采集循环负责停止、保存和复原。
  if (resetEdge && autoCollecting) {
    return { action: "advance_collection", nextLatch, values };
  }
  // X 在单轮录制中优先解释为“结束本轮并复原”，避免误把一轮数据留在 active 状态。
  if (resetEdge && episodeActive) {
    return { action: "finish_episode_and_reset", nextLatch, values };
  }
  if (startEdge && canStartCollection && !autoCollecting && !episodeActive) {
    return { action: "start_collection", nextLatch, values };
  }
  if (startEdge && canStartEpisode && !autoCollecting && !episodeActive) {
    return { action: "start_episode", nextLatch, values };
  }
  if (resetEdge && canResetScene) {
    return { action: "reset_scene", nextLatch, values };
  }

  return { action: "none", nextLatch, values };
}
