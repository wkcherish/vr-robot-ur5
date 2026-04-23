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

const JOINT_LIMITS_RAD = [
  [-Math.PI, Math.PI],
  [-Math.PI, Math.PI],
  [-Math.PI, Math.PI],
  [-Math.PI, Math.PI],
  [-Math.PI, Math.PI],
  [-Math.PI, Math.PI],
];

function clamp(value, min, max) {
  return Math.min(Math.max(Number(value) || 0, min), max);
}

function smooth(current, previous, alpha) {
  const a = clamp(alpha, 0.01, 1);
  return previous + (current - previous) * a;
}

function normDelta(current, previous, scale) {
  if (!Array.isArray(current) || !Array.isArray(previous)) return { x: 0, y: 0 };
  const dx = clamp((Number(current[0]) - Number(previous[0])) * scale, -1, 1);
  const dy = clamp((Number(current[1]) - Number(previous[1])) * scale, -1, 1);
  return { x: dx, y: dy };
}

export function createQuestHandTeleop(options = {}) {
  const cfg = {
    filter_alpha: Number.isFinite(Number(options.filter_alpha)) ? Number(options.filter_alpha) : 0.34,
    sensitivity: Number.isFinite(Number(options.sensitivity)) ? Number(options.sensitivity) : 0.9,
    max_joint_speed_rad_s: Number.isFinite(Number(options.max_joint_speed_rad_s))
      ? Number(options.max_joint_speed_rad_s)
      : 1.0,
    max_delta_rad_per_tick: Number.isFinite(Number(options.max_delta_rad_per_tick))
      ? Number(options.max_delta_rad_per_tick)
      : 0.038,
    max_gripper_delta_per_tick: Number.isFinite(Number(options.max_gripper_delta_per_tick))
      ? Number(options.max_gripper_delta_per_tick)
      : 0.03,
    pinch_switch_threshold: Number.isFinite(Number(options.pinch_switch_threshold))
      ? Number(options.pinch_switch_threshold)
      : 0.7,
    pinch_hold_threshold: Number.isFinite(Number(options.pinch_hold_threshold))
      ? Number(options.pinch_hold_threshold)
      : 0.45,
  };

  let selectedGroup = "upper_arm";
  let prevRightPalm = null;
  let lastAxisX = 0;
  let lastAxisY = 0;
  let lastGrip = 0;
  let lastSwitchPressed = false;
  let lastInputMode = "dual_hand";
  let trackingStable = false;

  function getState() {
    return {
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      input_mode: lastInputMode,
      tracking_stable: trackingStable,
      group_sequence: [...GROUP_SEQUENCE],
    };
  }

  function nextGroup() {
    const currentIndex = GROUP_SEQUENCE.indexOf(selectedGroup);
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % GROUP_SEQUENCE.length : 0;
    selectedGroup = GROUP_SEQUENCE[nextIndex];
  }

  function applySnapshot(snapshot, currentArmRadians, currentGripperOpening, dtSec = 1 / 30) {
    const arm = Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null;
    if (!arm || arm.length < 6) {
      return { has_command: false, reason: "invalid_arm_state", ...getState() };
    }

    const leftTracked = Boolean(snapshot?.hands?.left?.tracked);
    const rightTracked = Boolean(snapshot?.hands?.right?.tracked);
    const trackingStability = clamp(snapshot?.tracking_stability, 0, 1);
    trackingStable = trackingStability >= 0.45 && (rightTracked || leftTracked);

    if (!snapshot?.available || !trackingStable) {
      prevRightPalm = null;
      return {
        has_command: false,
        reason: "hand_unavailable",
        tracking_stable: false,
        tracking_stability: trackingStability,
        ...getState(),
      };
    }

    lastInputMode = leftTracked && rightTracked ? "dual_hand" : "single_hand";

    const leftPinch = snapshot?.hands?.left?.pinch || {};
    const rightPinch = snapshot?.hands?.right?.pinch || {};
    const rightPalm = snapshot?.hands?.right?.palm_position || null;

    let switchPressed = false;
    if (lastInputMode === "dual_hand") {
      switchPressed = (leftPinch.index || 0) >= cfg.pinch_switch_threshold;
    } else {
      switchPressed = (rightPinch.ring || 0) >= cfg.pinch_switch_threshold;
    }
    if (switchPressed && !lastSwitchPressed) nextGroup();
    lastSwitchPressed = switchPressed;

    const holdGesture = (rightPinch.index || 0) >= cfg.pinch_hold_threshold;
    let axisX = 0;
    let axisY = 0;
    if (holdGesture && rightPalm && Array.isArray(prevRightPalm)) {
      const delta = normDelta(rightPalm, prevRightPalm, 11.0);
      axisX = delta.x;
      axisY = delta.y;
    }
    prevRightPalm = Array.isArray(rightPalm) ? [...rightPalm] : prevRightPalm;

    const filteredX = smooth(axisX, lastAxisX, cfg.filter_alpha);
    const filteredY = smooth(axisY, lastAxisY, cfg.filter_alpha);
    lastAxisX = filteredX;
    lastAxisY = filteredY;

    const gripRaw = clamp(lastInputMode === "dual_hand" ? rightPinch.middle || 0 : rightPinch.middle || 0, 0, 1);
    const gripFiltered = smooth(gripRaw, lastGrip, cfg.filter_alpha);
    lastGrip = gripFiltered;

    const dt = clamp(dtSec, 1 / 120, 1 / 10);
    const speed = clamp(cfg.max_joint_speed_rad_s * cfg.sensitivity, 0.1, 3.0);
    const deltaA = clamp(-filteredY * speed * dt, -cfg.max_delta_rad_per_tick, cfg.max_delta_rad_per_tick);
    const deltaB = clamp(filteredX * speed * dt, -cfg.max_delta_rad_per_tick, cfg.max_delta_rad_per_tick);

    const groupPair = GROUP_JOINT_INDEX[selectedGroup] || GROUP_JOINT_INDEX.upper_arm;
    const [indexA, indexB] = groupPair;
    arm[indexA] = clamp(arm[indexA] + deltaA, JOINT_LIMITS_RAD[indexA][0], JOINT_LIMITS_RAD[indexA][1]);
    arm[indexB] = clamp(arm[indexB] + deltaB, JOINT_LIMITS_RAD[indexB][0], JOINT_LIMITS_RAD[indexB][1]);

    const currentGrip = clamp(currentGripperOpening, 0, 1);
    const gripDelta = clamp(
      gripFiltered - currentGrip,
      -cfg.max_gripper_delta_per_tick,
      cfg.max_gripper_delta_per_tick
    );
    const nextGripper = clamp(currentGrip + gripDelta, 0, 1);

    const activity = Math.abs(deltaA) + Math.abs(deltaB) + Math.abs(gripDelta);
    const hasCommand = activity > 1e-4 || switchPressed;

    return {
      has_command: hasCommand,
      reason: hasCommand ? "ok" : "idle",
      target_positions: arm,
      gripper_opening: nextGripper,
      input_source: "quest3_hand",
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      changed_joint_group: switchPressed,
      tracking_stable: trackingStable,
      tracking_stability: trackingStability,
      hand_input_mode: lastInputMode,
      normalized_input: {
        move_x: filteredX,
        move_y: filteredY,
        grip: gripFiltered,
        switch_pressed: switchPressed ? 1 : 0,
      },
      raw_input: snapshot.raw || null,
      timestamp_ms: Number(snapshot.timestamp_ms) || Date.now(),
    };
  }

  function reset() {
    prevRightPalm = null;
    lastAxisX = 0;
    lastAxisY = 0;
    lastGrip = 0;
    lastSwitchPressed = false;
    trackingStable = false;
  }

  return {
    getState,
    applySnapshot,
    reset,
  };
}
