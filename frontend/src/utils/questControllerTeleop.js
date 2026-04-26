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

function applyDeadzone(value, deadzone) {
  const x = clamp(value, -1, 1);
  const dz = clamp(deadzone, 0, 0.5);
  const magnitude = Math.abs(x);
  if (magnitude <= dz) return 0;
  const normalized = (magnitude - dz) / (1 - dz);
  return Math.sign(x) * normalized;
}

function resolvePressedGroup(controls) {
  if (!controls || typeof controls !== "object") return null;
  if (clamp(controls.select_wrist, 0, 1) > 0.5) return "wrist";
  if (clamp(controls.select_forearm, 0, 1) > 0.5) return "forearm";
  if (clamp(controls.select_upper_arm, 0, 1) > 0.5) return "upper_arm";
  return null;
}

function isNeutralControlSnapshot(controls, cfg) {
  if (!controls || typeof controls !== "object") return true;
  const stickX = Math.abs(clamp(controls.stick_x, -1, 1));
  const stickY = Math.abs(clamp(controls.stick_y, -1, 1));
  const trigger = clamp(controls.trigger, 0, 1);
  const upper = clamp(controls.select_upper_arm, 0, 1);
  const forearm = clamp(controls.select_forearm, 0, 1);
  const wrist = clamp(controls.select_wrist, 0, 1);
  const precision = clamp(controls.precision, 0, 1);
  const stickThreshold = Math.max(0.02, cfg.stick_activity_epsilon);
  return (
    stickX <= stickThreshold &&
    stickY <= stickThreshold &&
    trigger <= 0.05 &&
    upper <= 0.1 &&
    forearm <= 0.1 &&
    wrist <= 0.1 &&
    precision <= 0.1
  );
}

export function createQuestControllerTeleop(options = {}) {
  const cfg = {
    deadzone: Number.isFinite(Number(options.deadzone)) ? Number(options.deadzone) : 0.1,
    joint_step: Number.isFinite(Number(options.joint_step)) ? Number(options.joint_step) : 0.07,
    precision_scale: Number.isFinite(Number(options.precision_scale)) ? Number(options.precision_scale) : 0.4,
    stick_smoothing: Number.isFinite(Number(options.stick_smoothing)) ? Number(options.stick_smoothing) : 0.25,
    stick_activity_epsilon: Number.isFinite(Number(options.stick_activity_epsilon))
      ? Number(options.stick_activity_epsilon)
      : 0.035,
    gripper_smoothing: Number.isFinite(Number(options.gripper_smoothing))
      ? Number(options.gripper_smoothing)
      : 0.16,
    gripper_min: 0,
    gripper_max: 0.9,
  };

  let selectedGroup = "upper_arm";
  let lastStickX = 0;
  let lastStickY = 0;
  let lastGripper = 0.8;
  let commandGuardUntilMs = 0;
  let requireNeutralRelease = false;

  function getState() {
    return {
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      group_sequence: [...GROUP_SEQUENCE],
    };
  }

  function applySnapshot(snapshot, currentArmRadians, currentGripperOpening, dtSec = BASE_STEP_DT_SEC) {
    const nowMs = Number(snapshot?.timestamp_ms) || Date.now();
    const arm = Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null;
    if (!arm || arm.length < 6) {
      return { has_command: false, reason: "invalid_arm_state", ...getState() };
    }

    if (!snapshot?.available || !snapshot?.controls) {
      lastStickX = lowPass(lastStickX, 0, cfg.stick_smoothing);
      lastStickY = lowPass(lastStickY, 0, cfg.stick_smoothing);
      lastGripper = lowPass(lastGripper, clamp(currentGripperOpening, 0, 1), cfg.gripper_smoothing);
      return { has_command: false, reason: "controller_unavailable", ...getState() };
    }

    if (requireNeutralRelease && isNeutralControlSnapshot(snapshot.controls, cfg)) {
      requireNeutralRelease = false;
    }

    if (nowMs < commandGuardUntilMs || requireNeutralRelease) {
      lastStickX = lowPass(lastStickX, 0, cfg.stick_smoothing);
      lastStickY = lowPass(lastStickY, 0, cfg.stick_smoothing);
      lastGripper = lowPass(lastGripper, clamp(currentGripperOpening, 0, 1), cfg.gripper_smoothing);
      return {
        has_command: false,
        reason: "control_guard",
        target_positions: arm,
        gripper_opening: clamp(lastGripper, cfg.gripper_min, cfg.gripper_max),
        input_source: "quest3_controller",
        selected_joint_group: selectedGroup,
        selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
        changed_joint_group: false,
        normalized_input: {
          stick_x: 0,
          stick_y: 0,
          trigger: 0,
          precision: 0,
          select_upper_arm: 0,
          select_forearm: 0,
          select_wrist: 0,
        },
        raw_input: snapshot.raw || null,
        timestamp_ms: nowMs,
      };
    }

    const pressedGroup = resolvePressedGroup(snapshot.controls);
    const previousGroup = selectedGroup;
    if (pressedGroup) {
      selectedGroup = pressedGroup;
    }

    const rawStickX = applyDeadzone(snapshot.controls.stick_x, cfg.deadzone);
    const rawStickY = applyDeadzone(snapshot.controls.stick_y, cfg.deadzone);
    const triggerRaw = clamp(snapshot.controls.trigger, 0, 1);
    const precisionMode = clamp(snapshot.controls.precision, 0, 1) > 0.1;

    const smoothStickX = lowPass(lastStickX, rawStickX, cfg.stick_smoothing);
    const smoothStickY = lowPass(lastStickY, rawStickY, cfg.stick_smoothing);
    lastStickX = smoothStickX;
    lastStickY = smoothStickY;

    const dtScale = normalizeDtScale(dtSec);
    const speedScale = cfg.joint_step * dtScale * (precisionMode ? cfg.precision_scale : 1);
    let deltaA = 0;
    let deltaB = 0;
    if (pressedGroup) {
      const pair = GROUP_JOINT_INDEX[selectedGroup] || GROUP_JOINT_INDEX.upper_arm;
      const [indexA, indexB] = pair;
      deltaA = smoothStickY * speedScale;
      deltaB = smoothStickX * speedScale;
      arm[indexA] = clamp(arm[indexA] + deltaA, JOINT_LIMITS_RAD[indexA][0], JOINT_LIMITS_RAD[indexA][1]);
      arm[indexB] = clamp(arm[indexB] + deltaB, JOINT_LIMITS_RAD[indexB][0], JOINT_LIMITS_RAD[indexB][1]);
    }

    const mappedGripper = cfg.gripper_min + triggerRaw * (cfg.gripper_max - cfg.gripper_min);
    lastGripper = lowPass(lastGripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(lastGripper, cfg.gripper_min, cfg.gripper_max);

    const changedGroup = previousGroup !== selectedGroup;
    const stickIntent = Math.abs(smoothStickX) + Math.abs(smoothStickY) > cfg.stick_activity_epsilon;
    const hasJointActivity = Boolean(pressedGroup) && stickIntent && Math.abs(deltaA) + Math.abs(deltaB) > 1e-4;
    const hasGripperActivity = Math.abs(nextGripper - clamp(currentGripperOpening, 0, 1)) > 0.004;
    const hasCommand = hasJointActivity || hasGripperActivity;

    return {
      has_command: hasCommand,
      reason: hasCommand ? "ok" : "idle",
      target_positions: arm,
      gripper_opening: nextGripper,
      input_source: "quest3_controller",
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      changed_joint_group: changedGroup,
      normalized_input: {
        stick_x: smoothStickX,
        stick_y: smoothStickY,
        trigger: triggerRaw,
        precision: precisionMode ? 1 : 0,
        select_upper_arm: clamp(snapshot.controls.select_upper_arm, 0, 1),
        select_forearm: clamp(snapshot.controls.select_forearm, 0, 1),
        select_wrist: clamp(snapshot.controls.select_wrist, 0, 1),
      },
      raw_input: snapshot.raw || null,
      timestamp_ms: nowMs,
    };
  }

  function suppressCommands(options = {}) {
    const durationMs = Math.max(0, Number(options.duration_ms ?? options.durationMs) || 0);
    const nowMs = Date.now();
    commandGuardUntilMs = Math.max(commandGuardUntilMs, nowMs + durationMs);
    requireNeutralRelease = options.require_neutral === true || options.requireNeutral === true;
  }

  function reset(options = {}) {
    if (options.preserve_group !== true && options.preserveGroup !== true) {
      selectedGroup = "upper_arm";
    }
    lastStickX = 0;
    lastStickY = 0;
    lastGripper = 0.8;
    commandGuardUntilMs = 0;
    requireNeutralRelease = false;
  }

  return {
    getState,
    applySnapshot,
    suppressCommands,
    reset,
  };
}
