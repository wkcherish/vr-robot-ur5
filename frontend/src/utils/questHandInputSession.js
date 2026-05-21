import { DEFAULT_SNAPSHOT } from "./questHandInputCore.js";
import {
  ensureQuestXRSession,
  getQuestXRReferenceSpace,
  getQuestXRSession,
  getQuestXRStatus,
} from "./questXRSession.js";

export const state = {
  running: false,
  session: null,
  referenceSpace: null,
  status: { ready: false, reason: "not_started" },
  lastSnapshot: { ...DEFAULT_SNAPSHOT },
};

export async function ensureSession(options = {}) {
  if (state.session && state.referenceSpace) {
    state.status = { ready: true, reason: "ok" };
    return;
  }

  const status = await ensureQuestXRSession({
    preferHandTracking: options?.preferHandTracking === true,
  });
  state.session = getQuestXRSession();
  state.referenceSpace = getQuestXRReferenceSpace();
  state.status = {
    ready: Boolean(status.ready && state.session && state.referenceSpace),
    reason: status.reason,
  };
}

export async function closeSession() {
  const status = getQuestXRStatus();
  state.session = null;
  state.referenceSpace = null;
  state.status = { ready: false, reason: status.reason || "stopped" };
  state.lastSnapshot = { ...DEFAULT_SNAPSHOT, reason: state.status.reason, timestamp_ms: Date.now() };
}
