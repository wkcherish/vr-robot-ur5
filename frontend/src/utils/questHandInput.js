import { buildSnapshot, DEFAULT_SNAPSHOT } from "./questHandInputCore.js";
import { shouldContinueXrInputLoop } from "./immersiveStateHotPath.js";
import { closeSession, ensureSession, state } from "./questHandInputSession.js";

function frameLoop(timestamp, frame, generation) {
  if (!shouldContinueXrInputLoop({
    running: state.running,
    generation,
    activeGeneration: state.loopGeneration,
    frameSession: frame?.session,
    session: state.session,
  })) return;
  state.lastSnapshot = buildSnapshot(frame, state.session, state.referenceSpace);
  state.session.requestAnimationFrame((nextTimestamp, nextFrame) => {
    frameLoop(nextTimestamp, nextFrame, generation);
  });
}

export async function startQuestHandInput(options = {}) {
  const generation = state.loopGeneration + 1;
  state.loopGeneration = generation;
  state.running = true;
  await ensureSession(options);
  if (state.session) {
    state.session.requestAnimationFrame((timestamp, frame) => {
      frameLoop(timestamp, frame, generation);
    });
  }
  return getQuestHandInputStatus();
}

export async function stopQuestHandInput() {
  // 递增代次，使旧会话排队中的 XR 帧不再继续执行。
  state.loopGeneration += 1;
  state.running = false;
  await closeSession();
}

export function readQuestHandSnapshot() {
  if (typeof window !== "undefined" && window.__QUEST_HAND_SNAPSHOT__) {
    const debugSnapshot = window.__QUEST_HAND_SNAPSHOT__;
    if (debugSnapshot && typeof debugSnapshot === "object") {
      return { ...DEFAULT_SNAPSHOT, ...debugSnapshot, timestamp_ms: Date.now() };
    }
  }
  return { ...state.lastSnapshot };
}

export function getQuestHandInputStatus() {
  return {
    running: state.running,
    ready: Boolean(state.session && state.referenceSpace && state.status.ready),
    reason: state.status.reason,
    has_snapshot: Boolean(state.lastSnapshot && state.lastSnapshot.timestamp_ms > 0),
  };
}
