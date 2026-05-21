const CONTROL_GROUP = "end_effector";
const CONTROL_GROUP_LABEL = "末端执行器";
const BASE_STEP_DT_SEC = 1 / 50;

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

function estimateFallbackFist(leftHand) {
  const pinch = leftHand?.pinch || {};
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
      : 0.48,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 1.9
      : 1.9,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.62,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.065,
    anchor_reset_threshold_m: Number.isFinite(Number(options.anchor_reset_threshold_m))
      ? Number(options.anchor_reset_threshold_m)
      : 0.38,
    tracking_grace_ms: 560,
    tracking_stable_enter_threshold: Number.isFinite(Number(options.tracking_stable_enter_threshold))
      ? Number(options.tracking_stable_enter_threshold)
      : 0.24,
    tracking_stable_exit_threshold: Number.isFinite(Number(options.tracking_stable_exit_threshold))
      ? Number(options.tracking_stable_exit_threshold)
      : 0.14,
    fist_engage_threshold: Number.isFinite(Number(options.fist_engage_threshold))
      ? Number(options.fist_engage_threshold)
      : 0.62,
    fist_release_threshold: Number.isFinite(Number(options.fist_release_threshold))
      ? Number(options.fist_release_threshold)
      : 0.36,
    fist_smoothing: 0.35,
    gripper_smoothing: 0.24,
    gripper_min: 0,
    gripper_max: 0.9,
    ee_activity_epsilon_m: 0.0015,
    gripper_activity_epsilon: Number.isFinite(Number(options.gripper_activity_epsilon))
      ? Number(options.gripper_activity_epsilon)
      : 0.01,
  };

  let anchorPalm = null;
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
      input_mode: "left_hand_ee_ik",
      tracking_stable: false,
      group_sequence: [CONTROL_GROUP],
    };
  }

  function resetAnchor(leftPalm, currentEePose) {
    anchorPalm = cloneVec3(leftPalm);
    anchorEePose = cloneEePose(currentEePose);
    targetEePose = cloneEePose(currentEePose);
    smoothedBackendDelta = [0, 0, 0];
  }

  function ensureAnchor(leftPalm, currentEePose) {
    if (!anchorPalm || !anchorEePose || !targetEePose) {
      resetAnchor(leftPalm, currentEePose);
      return;
    }

    const drift = vecNorm(vecSub(targetEePose.position, currentEePose.position));
    if (drift > cfg.anchor_reset_threshold_m) {
      resetAnchor(leftPalm, currentEePose);
    }
  }

  function clearTrackingLatch() {
    anchorPalm = null;
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
    const leftHand = snapshot?.hands?.left || {};
    const leftTracked = Boolean(leftHand.tracked || leftHand.recently_tracked);
    const leftPalm = cloneVec3(leftHand.palm_position);
    const trackingStability = clamp(leftHand.stability ?? snapshot?.tracking_stability, 0, 1);
    const trackingPresent = Boolean(leftTracked && leftPalm);
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

    if (!snapshot?.available || !trackingStable || !leftTracked || !leftPalm) {
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
        hand_input_mode: "left_hand_ee_ik",
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
    ensureAnchor(leftPalm, currentPose);

    const rawPalmDelta = applyVecDeadzone(vecSub(leftPalm, anchorPalm), cfg.movement_deadzone);
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
    targetEePose = {
      position: limitedPosition,
      quaternion: anchorEePose.quaternion.slice(0, 4),
    };

    const rawFist = Number.isFinite(Number(leftHand.fist))
      ? clamp(leftHand.fist, 0, 1)
      : estimateFallbackFist(leftHand);
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
    const handMotion = vecNorm(smoothedBackendDelta);
    const hasEeActivity =
      eeError > cfg.ee_activity_epsilon_m ||
      handMotion > cfg.ee_activity_epsilon_m;
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
      hand_input_mode: "left_hand_ee_ik",
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
