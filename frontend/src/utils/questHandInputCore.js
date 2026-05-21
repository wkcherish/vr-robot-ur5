export const DEFAULT_SNAPSHOT = {
  available: false,
  reason: "not_started",
  timestamp_ms: 0,
  tracking_stability: 0,
  hands: {
    left: { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0 },
    right: { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0 },
  },
  raw: null,
};

const TRACKED_STABILITY_MIN = 0.3;
const STABILITY_SMOOTH_ALPHA = 0.58;
const JOINT_FALLBACK_GRACE_MS = 180;
const SOURCE_FALLBACK_GRACE_MS = 260;
const PINCH_FALLBACK_GRACE_MS = 220;
const PALM_SMOOTH_ALPHA = 0.68;
const PINCH_SMOOTH_ALPHA = 0.56;
const CONTROLLER_STABILITY = 0.72;

function createEmptyCacheState() {
  return {
    timestamp_ms: 0,
    tracked: false,
    stability: 0,
    palm_position: null,
    pinch: { index: 0, middle: 0, ring: 0, little: 0 },
    fist: 0,
    raw_joints: {
      wrist: null,
      thumb: null,
      index: null,
      middle: null,
      ring: null,
      little: null,
    },
  };
}

const HAND_CACHE = {
  left: createEmptyCacheState(),
};

const JOINT_NAMES = {
  wrist: "wrist",
  thumb: "thumb-tip",
  index: "index-finger-tip",
  middle: "middle-finger-tip",
  ring: "ring-finger-tip",
  little: "pinky-finger-tip",
};

function clamp(value, min, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return min;
  return Math.min(Math.max(numeric, min), max);
}

function toPositionArray(pose) {
  if (!pose || !pose.transform || !pose.transform.position) return null;
  const p = pose.transform.position;
  return [Number(p.x) || 0, Number(p.y) || 0, Number(p.z) || 0];
}

function readButtonValue(gamepad, candidates) {
  if (!gamepad || !gamepad.buttons || typeof gamepad.buttons.length !== "number") return 0;
  const indices = Array.isArray(candidates) ? candidates : [candidates];
  let maxValue = 0;
  indices.forEach((index) => {
    const button = gamepad.buttons[index];
    if (!button) return;
    const value = Math.max(clamp(button.value, 0, 1), button.pressed ? 1 : 0);
    if (value > maxValue) maxValue = value;
  });
  return maxValue;
}

function distance(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) return Infinity;
  const dx = Number(a[0]) - Number(b[0]);
  const dy = Number(a[1]) - Number(b[1]);
  const dz = Number(a[2]) - Number(b[2]);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function pinchStrength(thumbPos, fingerPos) {
  const pinchDist = distance(thumbPos, fingerPos);
  if (!Number.isFinite(pinchDist)) return 0;
  const pinchMin = 0.018;
  const pinchMax = 0.055;
  if (pinchDist <= pinchMin) return 1;
  if (pinchDist >= pinchMax) return 0;
  return clamp((pinchMax - pinchDist) / (pinchMax - pinchMin), 0, 1);
}

function fingerCurlStrength(wristPos, fingerPos, fingerName) {
  const fingerDist = distance(wristPos, fingerPos);
  if (!Number.isFinite(fingerDist)) return null;
  const thresholds = {
    index: [0.075, 0.170],
    middle: [0.080, 0.185],
    ring: [0.072, 0.172],
    little: [0.060, 0.152],
  };
  const [closedDist, openDist] = thresholds[fingerName] || [0.075, 0.170];
  if (fingerDist <= closedDist) return 1;
  if (fingerDist >= openDist) return 0;
  return clamp((openDist - fingerDist) / (openDist - closedDist), 0, 1);
}

function estimateFistStrength(rawJoints, pinch = {}) {
  const wrist = rawJoints?.wrist;
  const curlValues = ["index", "middle", "ring", "little"]
    .map((name) => fingerCurlStrength(wrist, rawJoints?.[name], name))
    .filter((value) => Number.isFinite(value));
  const curlAvg =
    curlValues.length > 0
      ? curlValues.reduce((sum, value) => sum + value, 0) / curlValues.length
      : 0;
  const pinchValues = ["index", "middle", "ring", "little"]
    .map((name) => clamp(pinch?.[name], 0, 1))
    .filter((value) => Number.isFinite(value));
  const pinchAvg =
    pinchValues.length > 0
      ? pinchValues.reduce((sum, value) => sum + value, 0) / pinchValues.length
      : 0;
  return clamp(Math.max(curlAvg, pinchAvg * 0.85), 0, 1);
}

function cloneJoint(value) {
  if (!Array.isArray(value) || value.length < 3) return null;
  return [Number(value[0]) || 0, Number(value[1]) || 0, Number(value[2]) || 0];
}

function cloneRawJoints(raw = {}) {
  return {
    wrist: cloneJoint(raw.wrist),
    thumb: cloneJoint(raw.thumb),
    index: cloneJoint(raw.index),
    middle: cloneJoint(raw.middle),
    ring: cloneJoint(raw.ring),
    little: cloneJoint(raw.little),
  };
}

function blendScalar(previous, next, alpha) {
  const p = Number(previous);
  const n = Number(next);
  if (!Number.isFinite(n)) return Number.isFinite(p) ? p : 0;
  if (!Number.isFinite(p)) return n;
  const a = clamp(alpha, 0, 1);
  return p + (n - p) * a;
}

function blendVec3(previous, next, alpha) {
  const p = Array.isArray(previous) && previous.length >= 3 ? previous : null;
  const n = Array.isArray(next) && next.length >= 3 ? next : null;
  if (!n && !p) return null;
  if (!n) return cloneJoint(p);
  if (!p) return cloneJoint(n);
  const a = clamp(alpha, 0, 1);
  return [
    blendScalar(p[0], n[0], a),
    blendScalar(p[1], n[1], a),
    blendScalar(p[2], n[2], a),
  ];
}

function readCachedHandState(handedness, nowMs) {
  const cache = HAND_CACHE[handedness];
  if (!cache || cache.timestamp_ms <= 0) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} };
  }
  const ageMs = nowMs - cache.timestamp_ms;
  if (ageMs > SOURCE_FALLBACK_GRACE_MS) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} };
  }
  const decay = clamp(1 - ageMs / SOURCE_FALLBACK_GRACE_MS, 0, 1);
  const stability = clamp((Number(cache.stability) || 0) * decay, 0, 1);
  return {
    tracked: Boolean(cache.tracked && stability >= TRACKED_STABILITY_MIN * 0.7),
    recently_tracked: Boolean(cache.tracked),
    stability,
    palm_position: cloneJoint(cache.palm_position),
    pinch: {
      index: clamp(cache?.pinch?.index, 0, 1),
      middle: clamp(cache?.pinch?.middle, 0, 1),
      ring: clamp(cache?.pinch?.ring, 0, 1),
      little: clamp(cache?.pinch?.little, 0, 1),
    },
    fist: clamp(cache?.fist, 0, 1),
    raw_joints: cloneRawJoints(cache.raw_joints),
    predicted: true,
  };
}

function writeCache(handedness, state, nowMs) {
  HAND_CACHE[handedness] = {
    timestamp_ms: nowMs,
    tracked: Boolean(state?.tracked),
    stability: clamp(state?.stability, 0, 1),
    palm_position: cloneJoint(state?.palm_position),
    pinch: {
      index: clamp(state?.pinch?.index, 0, 1),
      middle: clamp(state?.pinch?.middle, 0, 1),
      ring: clamp(state?.pinch?.ring, 0, 1),
      little: clamp(state?.pinch?.little, 0, 1),
    },
    fist: clamp(state?.fist, 0, 1),
    raw_joints: cloneRawJoints(state?.raw_joints || {}),
  };
}

function readHandState(frame, handInputSource, referenceSpace, handedness, nowMs) {
  if (!frame || !handInputSource || !handInputSource.hand || !referenceSpace || !handedness) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} };
  }
  const cache = HAND_CACHE[handedness];
  const cacheAgeMs = nowMs - Number(cache?.timestamp_ms || 0);
  const cacheValidForJoint = cacheAgeMs >= 0 && cacheAgeMs <= JOINT_FALLBACK_GRACE_MS;
  const cacheValidForPinch = cacheAgeMs >= 0 && cacheAgeMs <= PINCH_FALLBACK_GRACE_MS;

  const readJoint = (cacheKey, jointName) => {
    const joint = handInputSource.hand.get(jointName);
    if (joint) {
      const current = toPositionArray(frame.getJointPose(joint, referenceSpace));
      if (current) return current;
    }
    if (cacheValidForJoint) {
      const cached = cache?.raw_joints?.[cacheKey];
      if (Array.isArray(cached) && cached.length >= 3) {
        return cloneJoint(cached);
      }
    }
    return null;
  };

  const wrist = readJoint("wrist", JOINT_NAMES.wrist);
  const thumb = readJoint("thumb", JOINT_NAMES.thumb);
  const index = readJoint("index", JOINT_NAMES.index);
  const middle = readJoint("middle", JOINT_NAMES.middle);
  const ring = readJoint("ring", JOINT_NAMES.ring);
  const little = readJoint("little", JOINT_NAMES.little);

  const observedCount = [wrist, thumb, index, middle, ring, little].filter(Boolean).length;
  const rawStability = clamp(observedCount / 6, 0, 1);
  const previousStability =
    cacheAgeMs >= 0 && cacheAgeMs <= SOURCE_FALLBACK_GRACE_MS
      ? clamp(cache?.stability, 0, 1)
      : rawStability;
  const stability = clamp(
    previousStability + (rawStability - previousStability) * STABILITY_SMOOTH_ALPHA,
    0,
    1
  );
  const hasControlJoint = Boolean(thumb || index || middle || ring || little);
  const tracked = Boolean(wrist && hasControlJoint && stability >= TRACKED_STABILITY_MIN);
  const readPinch = (fingerName, fingerPose) => {
    const previous = clamp(cache?.pinch?.[fingerName], 0, 1);
    if (thumb && fingerPose) {
      const measured = pinchStrength(thumb, fingerPose);
      if (cacheValidForPinch) {
        return clamp(blendScalar(previous, measured, PINCH_SMOOTH_ALPHA), 0, 1);
      }
      return measured;
    }
    if (cacheValidForPinch) {
      return previous;
    }
    return 0;
  };

  const smoothedPalm = blendVec3(cache?.palm_position, wrist, PALM_SMOOTH_ALPHA);
  const pinch = {
    index: readPinch("index", index),
    middle: readPinch("middle", middle),
    ring: readPinch("ring", ring),
    little: readPinch("little", little),
  };
  const rawJoints = { wrist, thumb, index, middle, ring, little };
  const measuredFist = estimateFistStrength(rawJoints, pinch);
  const previousFist = clamp(cache?.fist, 0, 1);
  const fist = cacheValidForPinch
    ? clamp(blendScalar(previousFist, measuredFist, PINCH_SMOOTH_ALPHA), 0, 1)
    : measuredFist;

  return {
    tracked,
    recently_tracked: Boolean(
      tracked ||
      (cacheAgeMs >= 0 && cacheAgeMs <= SOURCE_FALLBACK_GRACE_MS && Boolean(cache?.tracked))
    ),
    stability,
    palm_position: smoothedPalm,
    pinch,
    fist,
    raw_joints: rawJoints,
    predicted: false,
  };
}

function readControllerAsHandState(frame, inputSource, referenceSpace, handedness, nowMs) {
  if (!frame || !inputSource || !referenceSpace || !handedness) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} };
  }

  const space = inputSource.gripSpace || inputSource.targetRaySpace;
  const pose = space ? frame.getPose(space, referenceSpace) : null;
  const palmPosition = toPositionArray(pose);
  if (!palmPosition) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} };
  }

  const cache = HAND_CACHE[handedness];
  const smoothedPalm = blendVec3(cache?.palm_position, palmPosition, PALM_SMOOTH_ALPHA);
  const gamepad = inputSource.gamepad || null;
  const fist = Math.max(readButtonValue(gamepad, [1]), readButtonValue(gamepad, [2, 3]));
  const state = {
    tracked: true,
    recently_tracked: true,
    stability: CONTROLLER_STABILITY,
    palm_position: smoothedPalm,
    pinch: {
      index: readButtonValue(gamepad, [0]),
      middle: readButtonValue(gamepad, [1]),
      ring: readButtonValue(gamepad, [4, 5, 3]),
      little: readButtonValue(gamepad, [2, 3]),
    },
    fist,
    raw_joints: {
      wrist: palmPosition,
      thumb: null,
      index: null,
      middle: null,
      ring: null,
      little: null,
    },
    predicted: false,
    controller_fallback: true,
    input_profiles: Array.from(inputSource.profiles || []),
  };
  writeCache(handedness, state, nowMs);
  return state;
}

export function buildSnapshot(frame, session, referenceSpace) {
  const nowMs = Date.now();
  const hands = {
    left: { tracked: false, stability: 0, palm_position: null, pinch: {}, fist: 0, raw_joints: {} },
  };

  const sources = Array.from(session?.inputSources || []);
  const handSources = sources.filter((source) => Boolean(source?.hand));
  const leftHandSources = handSources.filter((source) => source?.handedness === "left");
  const controllerSources = sources.filter((source) => Boolean(!source?.hand));
  let hasLeftSource = false;
  const leftHandSource = leftHandSources[0] || null;
  if (leftHandSource) {
    hasLeftSource = true;
    hands.left = readHandState(frame, leftHandSource, referenceSpace, "left", nowMs);
    writeCache("left", hands.left, nowMs);
  }

  if (!hasLeftSource) {
    const leftControllerSource =
      controllerSources.find((source) => source?.handedness === "left") ||
      controllerSources[0] ||
      null;
    if (leftControllerSource) {
      hands.left = readControllerAsHandState(frame, leftControllerSource, referenceSpace, "left", nowMs);
      hasLeftSource = Boolean(hands.left.tracked || hands.left.recently_tracked);
    } else {
      hands.left = readCachedHandState("left", nowMs);
    }
  }

  const leftAvailable = Boolean(hands.left.tracked || hands.left.recently_tracked);
  const available = Boolean(leftAvailable);
  const trackingStability = leftAvailable ? clamp(hands.left.stability || 0, 0, 1) : 0;

  return {
    available,
    reason: available ? "ok" : "hand_not_tracked",
    timestamp_ms: nowMs,
    tracking_stability: trackingStability,
    hands: {
      left: {
        tracked: hands.left.tracked,
        recently_tracked: Boolean(hands.left.recently_tracked),
        predicted: Boolean(hands.left.predicted),
        stability: hands.left.stability,
        palm_position: hands.left.palm_position,
        pinch: hands.left.pinch,
        fist: clamp(hands.left.fist, 0, 1),
        controller_fallback: Boolean(hands.left.controller_fallback),
      },
      right: { tracked: false, recently_tracked: false, predicted: false, stability: 0, palm_position: null, pinch: {}, fist: 0 },
    },
    raw: {
      input_source_count: sources.length,
      hand_input_source_count: leftHandSources.length,
      left_controller_fallback: Boolean(hands.left.controller_fallback),
      left: hands.left,
    },
  };
}
