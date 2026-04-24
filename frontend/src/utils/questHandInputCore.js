export const DEFAULT_SNAPSHOT = {
  available: false,
  reason: "not_started",
  timestamp_ms: 0,
  tracking_stability: 0,
  hands: {
    left: { tracked: false, stability: 0, palm_position: null, pinch: {} },
    right: { tracked: false, stability: 0, palm_position: null, pinch: {} },
  },
  raw: null,
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

function readHandState(frame, handInputSource, referenceSpace) {
  if (!frame || !handInputSource || !handInputSource.hand || !referenceSpace) {
    return { tracked: false, stability: 0, palm_position: null, pinch: {}, raw_joints: {} };
  }

  const readJoint = (jointName) => {
    const joint = handInputSource.hand.get(jointName);
    if (!joint) return null;
    return toPositionArray(frame.getJointPose(joint, referenceSpace));
  };

  const wrist = readJoint(JOINT_NAMES.wrist);
  const thumb = readJoint(JOINT_NAMES.thumb);
  const index = readJoint(JOINT_NAMES.index);
  const middle = readJoint(JOINT_NAMES.middle);
  const ring = readJoint(JOINT_NAMES.ring);
  const little = readJoint(JOINT_NAMES.little);

  const observedCount = [wrist, thumb, index, middle, ring, little].filter(Boolean).length;
  const stability = clamp(observedCount / 6, 0, 1);
  const tracked = Boolean(wrist && thumb && stability >= 0.45);

  return {
    tracked,
    stability,
    palm_position: wrist,
    pinch: {
      index: pinchStrength(thumb, index),
      middle: pinchStrength(thumb, middle),
      ring: pinchStrength(thumb, ring),
      little: pinchStrength(thumb, little),
    },
    raw_joints: { wrist, thumb, index, middle, ring, little },
  };
}

export function buildSnapshot(frame, session, referenceSpace) {
  const hands = {
    left: { tracked: false, stability: 0, palm_position: null, pinch: {}, raw_joints: {} },
    right: { tracked: false, stability: 0, palm_position: null, pinch: {}, raw_joints: {} },
  };

  const sources = Array.from(session?.inputSources || []);
  sources.forEach((source) => {
    const handed = source?.handedness === "left" ? "left" : source?.handedness === "right" ? "right" : "";
    if (!handed) return;
    hands[handed] = readHandState(frame, source, referenceSpace);
  });

  const available = Boolean(hands.left.tracked || hands.right.tracked);
  const trackedScores = [hands.left.stability || 0, hands.right.stability || 0];
  const trackingStability = clamp((trackedScores[0] + trackedScores[1]) / 2, 0, 1);

  return {
    available,
    reason: available ? "ok" : "hand_not_tracked",
    timestamp_ms: Date.now(),
    tracking_stability: trackingStability,
    hands: {
      left: {
        tracked: hands.left.tracked,
        stability: hands.left.stability,
        palm_position: hands.left.palm_position,
        pinch: hands.left.pinch,
      },
      right: {
        tracked: hands.right.tracked,
        stability: hands.right.stability,
        palm_position: hands.right.palm_position,
        pinch: hands.right.pinch,
      },
    },
    raw: {
      input_source_count: sources.length,
      left: hands.left,
      right: hands.right,
    },
  };
}
