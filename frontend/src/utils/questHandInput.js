import { buildSnapshot, DEFAULT_SNAPSHOT } from "./questHandInputCore.js";
import { closeSession, ensureSession, state } from "./questHandInputSession.js";

function frameLoop(timestamp, frame) {
  if (!state.running || !state.session || !frame || frame.session !== state.session) return;
  state.lastSnapshot = buildSnapshot(frame, state.session, state.referenceSpace);
  state.session.requestAnimationFrame(frameLoop);
}

export async function startQuestHandInput(options = {}) {
  state.running = true;
  await ensureSession(options);
  if (state.session) {
    state.session.requestAnimationFrame(frameLoop);
  }
  return getQuestHandInputStatus();
}

export async function stopQuestHandInput() {
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
