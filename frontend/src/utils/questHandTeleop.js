const CONTROL_GROUP = "end_effector";
const CONTROL_GROUP_LABEL = "末端执行器";
const BASE_STEP_DT_SEC = 1 / 50;
const FRONTEND_TO_BACKEND_QUAT_WXYZ = [
  Math.SQRT1_2,
  Math.SQRT1_2,
  0,
  0,
];

function clamp(value, min, max) {
  return Math.min(Math.max(Number(value) || 0, min), max);
}

function lowPass(previous, next, alpha) {
  const a = clamp(alpha, 0, 1);
  return previous + (next - previous) * a;
}

function normalizeDtScale(dtSec) {
  const dt = Number(dtSec);
  if (!Number.isFinite(dt)) return 1;
  const bounded = clamp(dt, 1 / 120, 1 / 10);
  return bounded / BASE_STEP_DT_SEC;
}

function applyDeadzone(value, deadzone) {
  const x = clamp(value, 0, 1);
  if (x <= deadzone) return 0;
  return (x - deadzone) / (1 - deadzone);
}

function cloneVec3(value) {
  if (!Array.isArray(value) || value.length < 3) return null;
  const cloned = value.slice(0, 3).map((item) => Number(item));
  return cloned.every((item) => Number.isFinite(item)) ? cloned : null;
}

function cloneQuat(value) {
  if (!Array.isArray(value) || value.length < 4) return null;
  const cloned = value.slice(0, 4).map((item) => Number(item));
  return cloned.every((item) => Number.isFinite(item)) ? cloned : null;
}

function cloneEePose(pose) {
  const position = cloneVec3(pose?.position);
  const quaternion = cloneQuat(pose?.quaternion);
  if (!position || !quaternion) return null;
  return { position, quaternion };
}

function normalizeQuatWxyz(quaternion) {
  const q = cloneQuat(quaternion);
  if (!q) return null;
  const [w, x, y, z] = q;
  const norm = Math.sqrt(w * w + x * x + y * y + z * z);
  if (norm <= 1e-8) return [1, 0, 0, 0];
  return [w / norm, x / norm, y / norm, z / norm];
}

function quatMultiplyWxyz(lhs, rhs) {
  const a = normalizeQuatWxyz(lhs);
  const b = normalizeQuatWxyz(rhs);
  if (!a || !b) return null;
  const [aw, ax, ay, az] = a;
  const [bw, bx, by, bz] = b;
  return normalizeQuatWxyz([
    aw * bw - ax * bx - ay * by - az * bz,
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
  ]);
}

function quatConjugateWxyz(quaternion) {
  const q = normalizeQuatWxyz(quaternion);
  if (!q) return null;
  return [q[0], -q[1], -q[2], -q[3]];
}

function quatDotWxyz(lhs, rhs) {
  const a = normalizeQuatWxyz(lhs);
  const b = normalizeQuatWxyz(rhs);
  if (!a || !b) return 1;
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
}

function quatAngleDistanceRad(lhs, rhs) {
  const dot = Math.abs(clamp(quatDotWxyz(lhs, rhs), -1, 1));
  return 2 * Math.acos(dot);
}

function slerpQuatWxyz(from, to, alpha) {
  const a = normalizeQuatWxyz(from);
  let b = normalizeQuatWxyz(to);
  if (!a || !b) return b || a || [1, 0, 0, 0];
  let dot = quatDotWxyz(a, b);
  if (dot < 0) {
    b = b.map((value) => -value);
    dot = -dot;
  }
  const t = clamp(alpha, 0, 1);
  if (dot > 0.9995) {
    return normalizeQuatWxyz([
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t,
      a[3] + (b[3] - a[3]) * t,
    ]);
  }
  const theta0 = Math.acos(clamp(dot, -1, 1));
  const sinTheta0 = Math.sin(theta0);
  const theta = theta0 * t;
  const sinTheta = Math.sin(theta);
  const s0 = Math.cos(theta) - dot * sinTheta / sinTheta0;
  const s1 = sinTheta / sinTheta0;
  return normalizeQuatWxyz([
    a[0] * s0 + b[0] * s1,
    a[1] * s0 + b[1] * s1,
    a[2] * s0 + b[2] * s1,
    a[3] * s0 + b[3] * s1,
  ]);
}

function clampQuatStepWxyz(previous, next, maxStepRad) {
  const prev = normalizeQuatWxyz(previous);
  const target = normalizeQuatWxyz(next);
  if (!prev || !target) return target || prev || [1, 0, 0, 0];
  const angle = quatAngleDistanceRad(prev, target);
  const maxStep = Math.max(0, Number(maxStepRad) || 0);
  if (angle <= maxStep || angle <= 1e-8 || maxStep <= 0) {
    return target;
  }
  return slerpQuatWxyz(prev, target, maxStep / angle);
}

function scaleQuatRotationWxyz(quaternion, gain) {
  let q = normalizeQuatWxyz(quaternion);
  if (!q) return null;
  if (q[0] < 0) {
    q = q.map((value) => -value);
  }
  const safeW = clamp(q[0], -1, 1);
  const halfSin = Math.sqrt(Math.max(0, 1 - safeW * safeW));
  if (halfSin <= 1e-8) return q;
  const angle = 2 * Math.acos(safeW);
  const scaledAngle = clamp(angle * Math.max(0, Number(gain) || 1), 0, Math.PI);
  const scale = Math.sin(scaledAngle / 2) / halfSin;
  return normalizeQuatWxyz([
    Math.cos(scaledAngle / 2),
    q[1] * scale,
    q[2] * scale,
    q[3] * scale,
  ]);
}

function vecSub(a, b) {
  return [
    Number(a?.[0] || 0) - Number(b?.[0] || 0),
    Number(a?.[1] || 0) - Number(b?.[1] || 0),
    Number(a?.[2] || 0) - Number(b?.[2] || 0),
  ];
}

function vecAdd(a, b) {
  return [
    Number(a?.[0] || 0) + Number(b?.[0] || 0),
    Number(a?.[1] || 0) + Number(b?.[1] || 0),
    Number(a?.[2] || 0) + Number(b?.[2] || 0),
  ];
}

function vecScale(a, scale) {
  const s = Number(scale) || 0;
  return [
    Number(a?.[0] || 0) * s,
    Number(a?.[1] || 0) * s,
    Number(a?.[2] || 0) * s,
  ];
}

function vecNorm(a) {
  const x = Number(a?.[0] || 0);
  const y = Number(a?.[1] || 0);
  const z = Number(a?.[2] || 0);
  return Math.sqrt(x * x + y * y + z * z);
}

function lowPassVec(previous, next, alpha) {
  const prev = cloneVec3(previous) || [0, 0, 0];
  const n = cloneVec3(next) || [0, 0, 0];
  return [
    lowPass(prev[0], n[0], alpha),
    lowPass(prev[1], n[1], alpha),
    lowPass(prev[2], n[2], alpha),
  ];
}

function clampVecMagnitude(vector, maxMagnitude) {
  const max = Math.max(0, Number(maxMagnitude) || 0);
  const magnitude = vecNorm(vector);
  if (max <= 0 || magnitude <= max || magnitude <= 1e-8) {
    return cloneVec3(vector) || [0, 0, 0];
  }
  return vecScale(vector, max / magnitude);
}

function clampVecStep(previous, next, maxStep) {
  const prev = cloneVec3(previous);
  const n = cloneVec3(next);
  if (!prev || !n) return n || prev || [0, 0, 0];
  const delta = vecSub(n, prev);
  return vecAdd(prev, clampVecMagnitude(delta, maxStep));
}

function applyVecDeadzone(vector, deadzone) {
  const magnitude = vecNorm(vector);
  const dz = Math.max(0, Number(deadzone) || 0);
  if (magnitude <= dz || magnitude <= 1e-8) return [0, 0, 0];
  return vecScale(vector, (magnitude - dz) / magnitude);
}

function frontendDeltaToBackend(delta) {
  return [delta[0], -delta[2], delta[1]];
}

function frontendQuatToBackendWxyz(quaternionXyzw) {
  const q = cloneQuat(quaternionXyzw);
  if (!q) return null;
  const frontendWxyz = [q[3], q[0], q[1], q[2]];
  return quatMultiplyWxyz(FRONTEND_TO_BACKEND_QUAT_WXYZ, frontendWxyz);
}

function estimateFallbackFist(handState) {
  const pinch = handState?.pinch || {};
  const values = ["index", "middle", "ring", "little"].map((name) =>
    clamp(pinch?.[name], 0, 1)
  );
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function createQuestHandTeleop(options = {}) {
  const cfg = {
    movement_deadzone: Number.isFinite(Number(options.movement_deadzone))
      ? Number(options.movement_deadzone)
      : 0.003,
    max_control_offset: Number.isFinite(Number(options.max_control_offset))
      ? Number(options.max_control_offset)
      : 1.05,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 3.8
      : 5.4,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.70,
    orientation_smoothing: Number.isFinite(Number(options.orientation_smoothing))
      ? Number(options.orientation_smoothing)
      : 0.70,
    max_orientation_step_rad: Number.isFinite(Number(options.max_orientation_step_rad))
      ? Number(options.max_orientation_step_rad)
      : 0.48,
    orientation_gain: Number.isFinite(Number(options.orientation_gain))
      ? Number(options.orientation_gain)
      : 1.35,
    orientation_activity_epsilon_rad: Number.isFinite(Number(options.orientation_activity_epsilon_rad))
      ? Number(options.orientation_activity_epsilon_rad)
      : 0.014,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.18,
    anchor_reset_threshold_m: Number.isFinite(Number(options.anchor_reset_threshold_m))
      ? Number(options.anchor_reset_threshold_m)
      : 0.85,
    tracking_grace_ms: 560,
    tracking_stable_enter_threshold: Number.isFinite(Number(options.tracking_stable_enter_threshold))
      ? Number(options.tracking_stable_enter_threshold)
      : 0.24,
    tracking_stable_exit_threshold: Number.isFinite(Number(options.tracking_stable_exit_threshold))
      ? Number(options.tracking_stable_exit_threshold)
      : 0.14,
    fist_engage_threshold: Number.isFinite(Number(options.fist_engage_threshold))
      ? Number(options.fist_engage_threshold)
      : 0.56,
    fist_release_threshold: Number.isFinite(Number(options.fist_release_threshold))
      ? Number(options.fist_release_threshold)
      : 0.30,
    fist_smoothing: 0.52,
    gripper_smoothing: 0.78,
    gripper_min: 0,
    gripper_max: 1.0,
    ee_activity_epsilon_m: 0.0015,
    gripper_activity_epsilon: Number.isFinite(Number(options.gripper_activity_epsilon))
      ? Number(options.gripper_activity_epsilon)
      : 0.01,
  };

  let anchorPalm = null;
  let anchorPalmQuaternion = null;
  let anchorEePose = null;
  let targetEePose = null;
  let smoothedBackendDelta = [0, 0, 0];
  let smoothedFist = 0;
  let fistLatched = false;
  let gripper = 0.0;
  let gripperInitialized = false;
  let lastTrackedAt = 0;
  let trackingStableLatched = false;

  function getState() {
    return {
      selected_joint_group: CONTROL_GROUP,
      selected_joint_group_label: CONTROL_GROUP_LABEL,
      input_mode: "right_hand_ee_ik",
      tracking_stable: false,
      group_sequence: [CONTROL_GROUP],
    };
  }

  function resetAnchor(rightPalm, currentEePose, rightPalmQuaternion) {
    anchorPalm = cloneVec3(rightPalm);
    anchorPalmQuaternion = frontendQuatToBackendWxyz(rightPalmQuaternion);
    anchorEePose = cloneEePose(currentEePose);
    targetEePose = cloneEePose(currentEePose);
    smoothedBackendDelta = [0, 0, 0];
  }

  function ensureAnchor(rightPalm, currentEePose, rightPalmQuaternion) {
    if (!anchorPalm || !anchorEePose || !targetEePose) {
      resetAnchor(rightPalm, currentEePose, rightPalmQuaternion);
      return;
    }

    const drift = vecNorm(vecSub(targetEePose.position, currentEePose.position));
    if (drift > cfg.anchor_reset_threshold_m) {
      resetAnchor(rightPalm, currentEePose, rightPalmQuaternion);
      return;
    }

    if (!anchorPalmQuaternion && cloneQuat(rightPalmQuaternion)) {
      anchorPalmQuaternion = frontendQuatToBackendWxyz(rightPalmQuaternion);
    }
  }

  function clearTrackingLatch() {
    anchorPalm = null;
    anchorPalmQuaternion = null;
    anchorEePose = null;
    targetEePose = null;
    smoothedBackendDelta = [0, 0, 0];
    smoothedFist = 0;
    fistLatched = false;
  }

  function applySnapshot(
    snapshot,
    currentArmRadians,
    currentGripperOpening,
    currentEePose,
    dtSec = BASE_STEP_DT_SEC
  ) {
    const currentPose = cloneEePose(currentEePose);
    if (!currentPose) {
      return { has_command: false, reason: "invalid_ee_state", ...getState() };
    }

    const currentGripper = clamp(currentGripperOpening, 0, 1);
    if (!gripperInitialized) {
      gripper = currentGripper;
      gripperInitialized = true;
    }

    const now = Date.now();
    const rightHand = snapshot?.hands?.right || {};
    const rightTracked = Boolean(rightHand.tracked || rightHand.recently_tracked);
    const rightPalm = cloneVec3(rightHand.palm_position);
    const rightPalmQuaternion = cloneQuat(rightHand.palm_quaternion);
    const trackingStability = clamp(rightHand.stability ?? snapshot?.tracking_stability, 0, 1);
    const trackingPresent = Boolean(rightTracked && rightPalm);
    let trackingStable = false;
    if (trackingStableLatched) {
      trackingStable =
        trackingPresent &&
        trackingStability >= clamp(cfg.tracking_stable_exit_threshold, 0.05, 0.95);
    } else {
      trackingStable =
        trackingPresent &&
        trackingStability >= clamp(cfg.tracking_stable_enter_threshold, 0.05, 0.95);
    }
    trackingStableLatched = trackingStable;

    if (!snapshot?.available || !trackingStable || !rightTracked || !rightPalm) {
      const recentlyTracked = lastTrackedAt > 0 && now - lastTrackedAt <= cfg.tracking_grace_ms;
      smoothedBackendDelta = lowPassVec(smoothedBackendDelta, [0, 0, 0], cfg.movement_smoothing);
      gripper = lowPass(gripper, currentGripper, cfg.gripper_smoothing);
      if (!recentlyTracked) {
        clearTrackingLatch();
      }
      return {
        has_command: false,
        reason: "hand_unavailable",
        target_positions: Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null,
        target_ee_pose: cloneEePose(targetEePose) || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        input_source: "quest3_hand",
        selected_joint_group: CONTROL_GROUP,
        selected_joint_group_label: CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        tracking_stable: false,
        tracking_stability: trackingStability,
        hand_input_mode: "right_hand_ee_ik",
        normalized_input: {
          control_mode: "ee_ik",
          ee_active: 0,
          fist: smoothedFist,
          grip: gripper,
          tracking_stability: trackingStability,
        },
        raw_input: snapshot?.raw || null,
        timestamp_ms: Number(snapshot?.timestamp_ms) || Date.now(),
      };
    }

    lastTrackedAt = now;
    ensureAnchor(rightPalm, currentPose, rightPalmQuaternion);

    const rawPalmDelta = applyVecDeadzone(vecSub(rightPalm, anchorPalm), cfg.movement_deadzone);
    const backendDelta = clampVecMagnitude(
      frontendDeltaToBackend(vecScale(rawPalmDelta, cfg.movement_gain)),
      cfg.max_control_offset
    );
    smoothedBackendDelta = lowPassVec(
      smoothedBackendDelta,
      backendDelta,
      cfg.movement_smoothing
    );

    const desiredPosition = vecAdd(anchorEePose.position, smoothedBackendDelta);
    const maxStep = Math.max(0.008, cfg.max_ee_step_m * normalizeDtScale(dtSec));
    const limitedPosition = clampVecStep(
      targetEePose?.position || currentPose.position,
      desiredPosition,
      maxStep
    );
    let desiredQuaternion = anchorEePose.quaternion.slice(0, 4);
    const palmQuaternionBackend = frontendQuatToBackendWxyz(rightPalmQuaternion);
    if (anchorPalmQuaternion && palmQuaternionBackend) {
      const palmDeltaRaw = quatMultiplyWxyz(
        palmQuaternionBackend,
        quatConjugateWxyz(anchorPalmQuaternion)
      );
      const palmDelta = scaleQuatRotationWxyz(palmDeltaRaw, cfg.orientation_gain) || palmDeltaRaw;
      desiredQuaternion = quatMultiplyWxyz(palmDelta, anchorEePose.quaternion) || desiredQuaternion;
    }
    const maxOrientationStep = Math.max(
      0.02,
      cfg.max_orientation_step_rad * normalizeDtScale(dtSec)
    );
    const limitedQuaternion = clampQuatStepWxyz(
      targetEePose?.quaternion || currentPose.quaternion,
      desiredQuaternion,
      maxOrientationStep
    );
    const smoothedQuaternion = slerpQuatWxyz(
      targetEePose?.quaternion || currentPose.quaternion,
      limitedQuaternion,
      cfg.orientation_smoothing
    );
    targetEePose = {
      position: limitedPosition,
      quaternion: smoothedQuaternion,
    };

    const rawFist = Number.isFinite(Number(rightHand.fist))
      ? clamp(rightHand.fist, 0, 1)
      : estimateFallbackFist(rightHand);
    smoothedFist = lowPass(smoothedFist, rawFist, cfg.fist_smoothing);
    if (!fistLatched && smoothedFist >= cfg.fist_engage_threshold) {
      fistLatched = true;
    } else if (fistLatched && smoothedFist <= cfg.fist_release_threshold) {
      fistLatched = false;
    }
    const gripRaw = fistLatched
      ? applyDeadzone(smoothedFist, cfg.fist_release_threshold)
      : 0;
    const mappedGripper = cfg.gripper_min + gripRaw * (cfg.gripper_max - cfg.gripper_min);
    gripper = lowPass(gripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(gripper, cfg.gripper_min, cfg.gripper_max);

    const eeError = vecNorm(vecSub(targetEePose.position, currentPose.position));
    const orientationError = quatAngleDistanceRad(targetEePose.quaternion, currentPose.quaternion);
    const handMotion = vecNorm(smoothedBackendDelta);
    const hasEeActivity =
      eeError > cfg.ee_activity_epsilon_m ||
      handMotion > cfg.ee_activity_epsilon_m ||
      orientationError > cfg.orientation_activity_epsilon_rad;
    const hasGripperActivity =
      Math.abs(nextGripper - currentGripper) > cfg.gripper_activity_epsilon;
    const hasCommand = hasEeActivity || hasGripperActivity;

    return {
      has_command: hasCommand,
      reason: hasCommand ? "ok" : "idle",
      target_positions: null,
      target_ee_pose: cloneEePose(targetEePose),
      gripper_opening: nextGripper,
      control_mode: "ik_pose",
      input_source: "quest3_hand",
      selected_joint_group: CONTROL_GROUP,
      selected_joint_group_label: CONTROL_GROUP_LABEL,
      changed_joint_group: false,
      tracking_stable: trackingStable,
      tracking_stability: trackingStability,
      hand_input_mode: "right_hand_ee_ik",
      normalized_input: {
        control_mode: "ee_ik",
        ee_active: hasEeActivity ? 1 : 0,
        palm_dx: rawPalmDelta[0],
        palm_dy: rawPalmDelta[1],
        palm_dz: rawPalmDelta[2],
        target_dx: smoothedBackendDelta[0],
        target_dy: smoothedBackendDelta[1],
        target_dz: smoothedBackendDelta[2],
        ee_error_m: eeError,
        orientation_error_rad: orientationError,
        movement_gain: cfg.movement_gain,
        orientation_gain: cfg.orientation_gain,
        max_control_offset_m: cfg.max_control_offset,
        fist: smoothedFist,
        fist_active: fistLatched ? 1 : 0,
        grip: gripRaw,
      },
      raw_input: snapshot?.raw || null,
      timestamp_ms: Number(snapshot?.timestamp_ms) || Date.now(),
    };
  }

  function reset() {
    anchorPalm = null;
    anchorPalmQuaternion = null;
    anchorEePose = null;
    targetEePose = null;
    smoothedBackendDelta = [0, 0, 0];
    smoothedFist = 0;
    fistLatched = false;
    gripper = 0;
    gripperInitialized = false;
    lastTrackedAt = 0;
    trackingStableLatched = false;
  }

  return {
    getState,
    applySnapshot,
    reset,
  };
}
