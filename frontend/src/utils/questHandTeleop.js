const GROUP_SEQUENCE = ["upper_arm", "forearm", "wrist"];
const GROUP_JOINT_INDEX = {
  upper_arm: [0, 1],
  forearm: [2, 3],
  wrist: [4, 5],
};

const GROUP_LABEL = {
  upper_arm: "大臂组",
  forearm: "前臂组",
  wrist: "腕部组",
};
const BASE_STEP_DT_SEC = 1 / 25;

const JOINT_LIMITS_RAD = [
  [-2 * Math.PI, 2 * Math.PI],
  [-2 * Math.PI, 2 * Math.PI],
  [-Math.PI, Math.PI],
  [-2 * Math.PI, 2 * Math.PI],
  [-2 * Math.PI, 2 * Math.PI],
  [-2 * Math.PI, 2 * Math.PI],
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

function applyLinearDeadzone(value, deadzone) {
  const magnitude = Math.abs(value);
  if (magnitude <= deadzone) return 0;
  return Math.sign(value) * (magnitude - deadzone);
}

function applyDeadzone(value, deadzone) {
  const x = clamp(value, 0, 1);
  if (x <= deadzone) return 0;
  return (x - deadzone) / (1 - deadzone);
}

function resolveGroupFromLeftPinch(leftPinch, threshold) {
  if (!leftPinch) return null;
  const candidates = [
    { group: "forearm", strength: clamp(leftPinch.middle, 0, 1) },
    { group: "upper_arm", strength: clamp(leftPinch.ring, 0, 1) },
    { group: "wrist", strength: clamp(leftPinch.index, 0, 1) },
  ];
  let selected = null;
  let maxStrength = threshold;
  for (const candidate of candidates) {
    if (candidate.strength >= maxStrength) {
      selected = candidate.group;
      maxStrength = candidate.strength;
    }
  }
  return selected;
}

function nextGroup(current) {
  if (!current || current === "wrist") return "forearm";
  if (current === "forearm") return "upper_arm";
  return "wrist";
}

function mapReason(reason) {
  if (reason === "invalid_arm_state") return "invalid_arm_state";
  if (reason === "hand_unavailable") return "hand_unavailable";
  return reason;
}

export function createQuestHandTeleop(options = {}) {
  const cfg = {
    movement_deadzone: Number.isFinite(Number(options.movement_deadzone))
      ? Number(options.movement_deadzone)
      : 0.0012,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 4.1
      : 4.1,
    max_frame_movement: Number.isFinite(Number(options.max_frame_movement))
      ? Number(options.max_frame_movement)
      : 0.03,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.32,
    move_pinch_engage_threshold: 0.38,
    move_pinch_release_threshold: 0.2,
    drag_engage_hold_ms: Number.isFinite(Number(options.drag_engage_hold_ms))
      ? Number(options.drag_engage_hold_ms)
      : 70,
    drag_hold_ms: 180,
    tracking_grace_ms: 280,
    tracking_stable_enter_threshold: Number.isFinite(Number(options.tracking_stable_enter_threshold))
      ? Number(options.tracking_stable_enter_threshold)
      : 0.42,
    tracking_stable_exit_threshold: Number.isFinite(Number(options.tracking_stable_exit_threshold))
      ? Number(options.tracking_stable_exit_threshold)
      : 0.30,
    dual_hand_release_ms: Number.isFinite(Number(options.dual_hand_release_ms))
      ? Number(options.dual_hand_release_ms)
      : 180,
    precision_scale: 0.42,
    group_pinch_threshold: 0.56,
    precision_pinch_threshold: 0.72,
    gripper_pinch_engage_threshold: Number.isFinite(Number(options.gripper_pinch_engage_threshold))
      ? Number(options.gripper_pinch_engage_threshold)
      : 0.34,
    gripper_pinch_release_threshold: Number.isFinite(Number(options.gripper_pinch_release_threshold))
      ? Number(options.gripper_pinch_release_threshold)
      : 0.2,
    gripper_smoothing: 0.2,
    gripper_min: 0,
    gripper_max: 0.9,
    joint_activity_epsilon: Number.isFinite(Number(options.joint_activity_epsilon))
      ? Number(options.joint_activity_epsilon)
      : 4e-4,
    gripper_activity_epsilon: Number.isFinite(Number(options.gripper_activity_epsilon))
      ? Number(options.gripper_activity_epsilon)
      : 0.01,
  };

  let selectedGroup = "wrist";
  let moveX = 0;
  let moveY = 0;
  let previousRightX = null;
  let previousRightY = null;
  let isDragging = false;
  let dragEngageAt = null;
  let dragReleaseAt = null;
  let lastTrackedAt = 0;
  let gripper = 0.8;
  let gripperPinchLatched = false;
  let groupCycleLatched = false;
  let lastInputMode = "dual_hand";
  let trackingStableLatched = false;
  let dualHandLatched = false;
  let dualHandLastSeenAt = 0;

  function getState() {
    return {
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      input_mode: lastInputMode,
      tracking_stable: false,
      group_sequence: [...GROUP_SEQUENCE],
    };
  }

  function applySnapshot(snapshot, currentArmRadians, currentGripperOpening, dtSec = BASE_STEP_DT_SEC) {
    const arm = Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null;
    if (!arm || arm.length < 6) {
      return { has_command: false, reason: "invalid_arm_state", ...getState() };
    }

    const now = Date.now();
    const leftHand = snapshot?.hands?.left || {};
    const rightHand = snapshot?.hands?.right || {};
    const leftTracked = Boolean(leftHand.tracked || leftHand.recently_tracked);
    const rightTracked = Boolean(rightHand.tracked || rightHand.recently_tracked);
    const leftLiveTracked = Boolean(leftHand.tracked && !leftHand.predicted);
    const dualCandidate = Boolean(leftLiveTracked && rightTracked);
    if (dualCandidate) {
      dualHandLastSeenAt = now;
      dualHandLatched = true;
    } else if (dualHandLatched && now - dualHandLastSeenAt > cfg.dual_hand_release_ms) {
      dualHandLatched = false;
    }
    const hasDualHand = Boolean(dualHandLatched && rightTracked);
    const primaryHand = rightTracked ? rightHand : leftTracked ? leftHand : null;
    const trackingStability = clamp(snapshot?.tracking_stability, 0, 1);
    const trackingPresent = Boolean(leftTracked || rightTracked);
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

    if (!snapshot?.available || !trackingStable || !primaryHand) {
      const recentlyTracked = lastTrackedAt > 0 && now - lastTrackedAt <= cfg.tracking_grace_ms;
      moveX = lowPass(moveX, 0, cfg.movement_smoothing);
      moveY = lowPass(moveY, 0, cfg.movement_smoothing);
      if (!recentlyTracked) {
        isDragging = false;
        dragEngageAt = null;
        dragReleaseAt = null;
        previousRightX = null;
        previousRightY = null;
        gripperPinchLatched = false;
        groupCycleLatched = false;
      }
      gripper = lowPass(gripper, clamp(currentGripperOpening, 0, 1), cfg.gripper_smoothing);
      return {
        has_command: false,
        reason: mapReason("hand_unavailable"),
        target_positions: arm,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        input_source: "quest3_hand",
        selected_joint_group: selectedGroup,
        selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
        changed_joint_group: false,
        tracking_stable: false,
        tracking_stability: trackingStability,
        hand_input_mode: hasDualHand ? "dual_hand" : "single_hand",
        normalized_input: {
          move_x: moveX,
          move_y: moveY,
          grip: gripper,
          switch_pressed: 0,
        },
        raw_input: snapshot?.raw || null,
        timestamp_ms: Number(snapshot?.timestamp_ms) || Date.now(),
      };
    }

    lastTrackedAt = now;
    lastInputMode = hasDualHand ? "dual_hand" : "single_hand";

    const leftPinch = leftHand.pinch || {};
    const primaryPinch = primaryHand.pinch || {};

    let changedGroup = false;
    if (hasDualHand) {
      const selected = resolveGroupFromLeftPinch(leftPinch, cfg.group_pinch_threshold);
      if (selected && selected !== selectedGroup) {
        selectedGroup = selected;
        changedGroup = true;
      }
      groupCycleLatched = false;
    } else {
      const cyclePinch = clamp(primaryPinch.ring, 0, 1);
      if (cyclePinch >= cfg.group_pinch_threshold && !groupCycleLatched) {
        selectedGroup = nextGroup(selectedGroup);
        changedGroup = true;
        groupCycleLatched = true;
      } else if (cyclePinch <= cfg.move_pinch_release_threshold) {
        groupCycleLatched = false;
      }
    }

    const dragPinch = clamp(primaryPinch.index, 0, 1);
    const rightPalm = Array.isArray(primaryHand.palm_position) ? primaryHand.palm_position : null;
    if (!isDragging) {
      if (dragPinch >= cfg.move_pinch_engage_threshold && rightPalm) {
        if (dragEngageAt === null) {
          dragEngageAt = now;
        } else if (now - dragEngageAt >= cfg.drag_engage_hold_ms) {
          isDragging = true;
          dragEngageAt = null;
          dragReleaseAt = null;
          previousRightX = Number(rightPalm[0]) || 0;
          previousRightY = Number(rightPalm[1]) || 0;
        }
      } else {
        dragEngageAt = null;
      }
    } else if (isDragging) {
      if (dragPinch <= cfg.move_pinch_release_threshold) {
        if (dragReleaseAt === null) {
          dragReleaseAt = now;
        } else if (now - dragReleaseAt >= cfg.drag_hold_ms) {
          isDragging = false;
          dragReleaseAt = null;
          previousRightX = null;
          previousRightY = null;
        }
      } else {
        dragReleaseAt = null;
      }
    }

    let rawMoveX = 0;
    let rawMoveY = 0;
    if (isDragging && rightPalm && previousRightX !== null && previousRightY !== null) {
      rawMoveX = clamp(Number(rightPalm[0]) - previousRightX, -cfg.max_frame_movement, cfg.max_frame_movement);
      rawMoveY = clamp(Number(rightPalm[1]) - previousRightY, -cfg.max_frame_movement, cfg.max_frame_movement);
      previousRightX = Number(rightPalm[0]) || 0;
      previousRightY = Number(rightPalm[1]) || 0;
    } else if (!isDragging) {
      previousRightX = null;
      previousRightY = null;
    }

    const filteredMoveX = applyLinearDeadzone(rawMoveX, cfg.movement_deadzone);
    const filteredMoveY = applyLinearDeadzone(rawMoveY, cfg.movement_deadzone);
    const targetMoveX = isDragging ? filteredMoveX : 0;
    const targetMoveY = isDragging ? filteredMoveY : 0;
    moveX = lowPass(moveX, targetMoveX, cfg.movement_smoothing);
    moveY = lowPass(moveY, targetMoveY, cfg.movement_smoothing);

    const precisionMode = hasDualHand && clamp(primaryPinch.ring, 0, 1) >= cfg.precision_pinch_threshold;
    const dtScale = normalizeDtScale(dtSec);
    const speedScale = cfg.movement_gain * dtScale * (precisionMode ? cfg.precision_scale : 1);
    const deltaA = moveY * speedScale;
    const deltaB = moveX * speedScale;

    const pair = GROUP_JOINT_INDEX[selectedGroup] || GROUP_JOINT_INDEX.upper_arm;
    const [indexA, indexB] = pair;
    const hasDragMove = isDragging && (Math.abs(deltaA) + Math.abs(deltaB) > cfg.joint_activity_epsilon);
    if (hasDragMove) {
      arm[indexA] = clamp(arm[indexA] + deltaA, JOINT_LIMITS_RAD[indexA][0], JOINT_LIMITS_RAD[indexA][1]);
      arm[indexB] = clamp(arm[indexB] + deltaB, JOINT_LIMITS_RAD[indexB][0], JOINT_LIMITS_RAD[indexB][1]);
    }

    const gripPinch = clamp(primaryPinch.middle, 0, 1);
    if (!gripperPinchLatched && gripPinch >= cfg.gripper_pinch_engage_threshold) {
      gripperPinchLatched = true;
    } else if (gripperPinchLatched && gripPinch <= cfg.gripper_pinch_release_threshold) {
      gripperPinchLatched = false;
    }
    const gripRaw = gripperPinchLatched
      ? applyDeadzone(gripPinch, cfg.gripper_pinch_release_threshold)
      : 0;
    const mappedGripper = cfg.gripper_min + gripRaw * (cfg.gripper_max - cfg.gripper_min);
    gripper = lowPass(gripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(gripper, cfg.gripper_min, cfg.gripper_max);

    const hasGripperActivity =
      Math.abs(nextGripper - clamp(currentGripperOpening, 0, 1)) > cfg.gripper_activity_epsilon;
    const hasCommand = changedGroup || hasDragMove || hasGripperActivity;

    return {
      has_command: hasCommand,
      reason: hasCommand ? "ok" : "idle",
      target_positions: arm,
      gripper_opening: nextGripper,
      input_source: "quest3_hand",
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      changed_joint_group: changedGroup,
      tracking_stable: trackingStable,
      tracking_stability: trackingStability,
      hand_input_mode: lastInputMode,
      normalized_input: {
        move_x: moveX,
        move_y: moveY,
        grip: gripRaw,
        grip_active: gripperPinchLatched ? 1 : 0,
        switch_pressed: changedGroup ? 1 : 0,
      },
      raw_input: snapshot?.raw || null,
      timestamp_ms: Number(snapshot?.timestamp_ms) || Date.now(),
    };
  }

  function reset() {
    selectedGroup = "wrist";
    moveX = 0;
    moveY = 0;
    previousRightX = null;
    previousRightY = null;
    isDragging = false;
    dragEngageAt = null;
    dragReleaseAt = null;
    lastTrackedAt = 0;
    gripper = 0.8;
    gripperPinchLatched = false;
    groupCycleLatched = false;
    lastInputMode = "dual_hand";
    trackingStableLatched = false;
    dualHandLatched = false;
    dualHandLastSeenAt = 0;
  }

  return {
    getState,
    applySnapshot,
    reset,
  };
}
