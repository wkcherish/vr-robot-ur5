const state = {
  session: null,
  referenceSpace: null,
  referenceSpaceType: "",
  pendingSessionPromise: null,
  status: {
    ready: false,
    reason: "not_started",
    detail: "",
  },
};

function isSecureContextAvailable() {
  if (typeof window === "undefined") return false;
  return Boolean(window.isSecureContext);
}

function getSessionInitCandidates() {
  return [
    {
      requiredFeatures: ["local-floor"],
      optionalFeatures: ["hand-tracking", "bounded-floor"],
    },
    {
      optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"],
    },
    {
      optionalFeatures: ["local-floor", "bounded-floor"],
    },
    {
      optionalFeatures: ["hand-tracking"],
    },
    {},
  ];
}

function normalizeSessionErrorMessage(error) {
  const name = String(error?.name || "");
  const message = String(error?.message || "");
  if (message) return `${name}:${message}`;
  return name || "unknown_error";
}

function shouldTryNextCandidate(error) {
  const name = String(error?.name || "");
  return name === "NotSupportedError" || name === "TypeError";
}

async function requestImmersiveVrSession(xr) {
  const initCandidates = getSessionInitCandidates();
  const errors = [];

  for (let index = 0; index < initCandidates.length; index += 1) {
    const sessionInit = initCandidates[index] || {};
    try {
      const session = await xr.requestSession("immersive-vr", sessionInit);
      return { session, sessionInit };
    } catch (error) {
      errors.push(`[candidate_${index}] ${normalizeSessionErrorMessage(error)}`);
      if (!shouldTryNextCandidate(error)) {
        throw error;
      }
    }
  }

  const fallbackError = new Error("immersive_vr_request_failed");
  fallbackError.name = "NotSupportedError";
  fallbackError.detail = errors.join(" | ");
  throw fallbackError;
}

async function resolveReferenceSpace(session) {
  const candidates = ["local-floor", "bounded-floor", "local", "viewer"];
  let lastError = null;
  for (const name of candidates) {
    try {
      const referenceSpace = await session.requestReferenceSpace(name);
      return { referenceSpace, type: name };
    } catch (error) {
      lastError = error;
    }
  }
  const refError = new Error("reference_space_failed");
  refError.name = "NotSupportedError";
  refError.detail = lastError ? normalizeSessionErrorMessage(lastError) : "";
  throw refError;
}

function clearSessionState(reason = "not_started") {
  state.session = null;
  state.referenceSpace = null;
  state.referenceSpaceType = "";
  state.status = {
    ready: false,
    reason,
    detail: "",
  };
}

function handleSessionEnded() {
  clearSessionState("xr_session_ended");
}

function mapSessionError(error) {
  const name = String(error?.name || "");
  const message = String(error?.message || "");
  const detail = String(error?.detail || message || "").trim();
  if (name === "NotAllowedError") {
    return { reason: "user_gesture_or_permission_denied", detail };
  }
  if (name === "NotSupportedError") {
    return { reason: "immersive_vr_not_supported", detail };
  }
  if (name === "SecurityError") {
    return { reason: "insecure_context", detail };
  }
  if (name === "InvalidStateError") {
    return { reason: "xr_runtime_invalid_state", detail };
  }
  if (name === "AbortError") {
    return { reason: "xr_runtime_aborted", detail };
  }
  return { reason: "xr_session_failed", detail: detail || name || "unknown_error" };
}

function getXrApi() {
  if (typeof navigator === "undefined") return null;
  if (!navigator.xr) return null;
  return navigator.xr;
}

async function checkImmersiveVrSupport(xr) {
  if (!xr || typeof xr.isSessionSupported !== "function") {
    return { ok: true, detail: "" };
  }
  try {
    const supported = await xr.isSessionSupported("immersive-vr");
    if (!supported) {
      return { ok: false, detail: "isSessionSupported returned false" };
    }
    return { ok: true, detail: "" };
  } catch (error) {
    return {
      ok: false,
      detail: normalizeSessionErrorMessage(error),
    };
  }
}

export function getQuestXRSession() {
  return state.session;
}

export function getQuestXRReferenceSpace() {
  return state.referenceSpace;
}

export function getQuestXRReferenceSpaceType() {
  return state.referenceSpaceType;
}

export function getQuestXRStatus() {
  return {
    ready: Boolean(
      state.session &&
      state.referenceSpace &&
      state.referenceSpaceType &&
      state.status.ready
    ),
    reason: state.status.reason,
    detail: state.status.detail || "",
    reference_space_type: state.referenceSpaceType || "",
  };
}

export async function ensureQuestXRSession() {
  if (state.session && state.referenceSpace && state.referenceSpaceType) {
    state.status = { ready: true, reason: "ok", detail: "" };
    return getQuestXRStatus();
  }

  if (state.pendingSessionPromise) {
    return await state.pendingSessionPromise;
  }

  const xr = getXrApi();
  if (!xr || typeof xr.requestSession !== "function") {
    state.status = { ready: false, reason: "webxr_unavailable", detail: "" };
    return getQuestXRStatus();
  }

  if (!isSecureContextAvailable()) {
    state.status = { ready: false, reason: "insecure_context", detail: "" };
    return getQuestXRStatus();
  }

  state.pendingSessionPromise = (async () => {
    const support = await checkImmersiveVrSupport(xr);
    if (!support.ok) {
      clearSessionState("immersive_vr_not_supported");
      state.status.detail = support.detail;
      return getQuestXRStatus();
    }

    try {
      const { session } = await requestImmersiveVrSession(xr);
      const { referenceSpace, type } = await resolveReferenceSpace(session);
      session.addEventListener("end", handleSessionEnded, { once: true });
      state.session = session;
      state.referenceSpace = referenceSpace;
      state.referenceSpaceType = type;
      state.status = { ready: true, reason: "ok", detail: "" };
      return getQuestXRStatus();
    } catch (error) {
      clearSessionState("xr_session_failed");
      const mapped = mapSessionError(error);
      state.status = { ready: false, reason: mapped.reason, detail: mapped.detail };
      return getQuestXRStatus();
    } finally {
      state.pendingSessionPromise = null;
    }
  })();

  return await state.pendingSessionPromise;
}

export async function stopQuestXRSession() {
  const activeSession = state.session;
  state.pendingSessionPromise = null;
  clearSessionState("stopped");
  if (!activeSession) {
    return;
  }
  try {
    await activeSession.end();
  } catch (_) {}
}
