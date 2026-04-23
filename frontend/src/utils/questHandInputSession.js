import { DEFAULT_SNAPSHOT } from "./questHandInputCore.js";

export const state = {
  running: false,
  session: null,
  referenceSpace: null,
  status: { ready: false, reason: "not_started" },
  lastSnapshot: { ...DEFAULT_SNAPSHOT },
};

export async function createHandTrackingSession() {
  if (typeof navigator === "undefined" || !navigator.xr || !navigator.xr.requestSession) {
    state.status = { ready: false, reason: "webxr_unavailable" };
    return false;
  }

  try {
    state.session = await navigator.xr.requestSession("inline", {
      optionalFeatures: ["hand-tracking", "local-floor"],
    });
  } catch (_) {
    state.status = { ready: false, reason: "xr_session_failed" };
    return false;
  }

  try {
    state.referenceSpace = await state.session.requestReferenceSpace("local");
  } catch (_) {
    state.referenceSpace = await state.session.requestReferenceSpace("viewer");
  }

  state.session.addEventListener("end", () => {
    state.session = null;
    state.referenceSpace = null;
    state.status = { ready: false, reason: "xr_session_ended" };
    state.lastSnapshot = { ...DEFAULT_SNAPSHOT, reason: "xr_session_ended", timestamp_ms: Date.now() };
  });

  state.status = { ready: true, reason: "ok" };
  return true;
}

export async function ensureSession() {
  if (state.session) return;
  await createHandTrackingSession();
}
