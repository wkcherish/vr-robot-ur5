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

function normalizeAxis(raw, deadzone) {
  const x = clamp(raw, -1, 1);
  const dz = clamp(deadzone, 0, 0.5);
  if (Math.abs(x) <= dz) return 0;
  const sign = x >= 0 ? 1 : -1;
  return sign * ((Math.abs(x) - dz) / (1 - dz));
}

function nextGroupFromButtons(controls, fallbackGroup) {
  if (!controls || typeof controls !== "object") return fallbackGroup;
  if ((controls.select_upper_arm || 0) > 0.6) return "upper_arm";
  if ((controls.select_forearm || 0) > 0.6) return "forearm";
  if ((controls.select_wrist || 0) > 0.6) return "wrist";
  return fallbackGroup;
}

export function createQuestControllerTeleop(options = {}) {
  const cfg = {
    deadzone: Number.isFinite(Number(options.deadzone)) ? Number(options.deadzone) : 0.14,
    sensitivity: Number.isFinite(Number(options.sensitivity)) ? Number(options.sensitivity) : 1.0,
    filter_alpha: Number.isFinite(Number(options.filter_alpha)) ? Number(options.filter_alpha) : 0.36,
    max_joint_speed_rad_s: Number.isFinite(Number(options.max_joint_speed_rad_s))
      ? Number(options.max_joint_speed_rad_s)
      : 1.2,
    max_delta_rad_per_tick: Number.isFinite(Number(options.max_delta_rad_per_tick))
      ? Number(options.max_delta_rad_per_tick)
      : 0.045,
    max_gripper_delta_per_tick: Number.isFinite(Number(options.max_gripper_delta_per_tick))
      ? Number(options.max_gripper_delta_per_tick)
      : 0.04,
  };

  let selectedGroup = "upper_arm";
  let lastAxisX = 0;
  let lastAxisY = 0;
  let lastTrigger = 0;

  function smooth(current, previous) {
    const alpha = clamp(cfg.filter_alpha, 0.01, 1);
    return previous + (current - previous) * alpha;
  }

  function getState() {
    return {
      selected_joint_group: selectedGroup,
      selected_joint_group_label: GROUP_LABEL[selectedGroup] || selectedGroup,
      group_sequence: [...GROUP_SEQUENCE],
    };
  }

  function applySnapshot(snapshot, currentArmRadians, currentGripperOpening, dtSec = 1 / 30) {
    const arm = Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null;
    if (!arm || arm.length < 6) {
      return { has_command: false, reason: "invalid_arm_state", ...getState() };
    }

    if (!snapshot?.available || !snapshot?.controls) {
      return { has_command: false, reason: "controller_unavailable", ...getState() };
    }

    const previousGroup = selectedGroup;
    selectedGroup = nextGroupFromButtons(snapshot.controls, selectedGroup);

    const normX = normalizeAxis(snapshot.controls.stick_x, cfg.deadzone);
    const normY = normalizeAxis(snapshot.controls.stick_y, cfg.deadzone);
    const triggerRaw = clamp(snapshot.controls.trigger, 0, 1);

    const filteredX = smooth(normX, lastAxisX);
    const filteredY = smooth(normY, lastAxisY);
    const filteredTrigger = smooth(triggerRaw, lastTrigger);

    lastAxisX = filteredX;
    lastAxisY = filteredY;
    lastTrigger = filteredTrigger;

    const dt = clamp(dtSec, 1 / 120, 1 / 10);
    const speed = clamp(cfg.max_joint_speed_rad_s * cfg.sensitivity, 0.1, 3.0);
    const rawDeltaA = clamp(-filteredY * speed * dt, -cfg.max_delta_rad_per_tick, cfg.max_delta_rad_per_tick);
    const rawDeltaB = clamp(filteredX * speed * dt, -cfg.max_delta_rad_per_tick, cfg.max_delta_rad_per_tick);

    const groupPair = GROUP_JOINT_INDEX[selectedGroup] || GROUP_JOINT_INDEX.upper_arm;
    const [indexA, indexB] = groupPair;
    arm[indexA] = clamp(arm[indexA] + rawDeltaA, JOINT_LIMITS_RAD[indexA][0], JOINT_LIMITS_RAD[indexA][1]);
    arm[indexB] = clamp(arm[indexB] + rawDeltaB, JOINT_LIMITS_RAD[indexB][0], JOINT_LIMITS_RAD[indexB][1]);

    const currentGrip = clamp(currentGripperOpening, 0, 1);
    const gripDelta = clamp(
      filteredTrigger - currentGrip,
      -cfg.max_gripper_delta_per_tick,
      cfg.max_gripper_delta_per_tick
    );
    const nextGripper = clamp(currentGrip + gripDelta, 0, 1);

    const activity = Math.abs(rawDeltaA) + Math.abs(rawDeltaB) + Math.abs(gripDelta);
    const changedGroup = previousGroup !== selectedGroup;
    const hasCommand = changedGroup || activity > 1e-4;

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
        stick_x: filteredX,
        stick_y: filteredY,
        trigger: filteredTrigger,
        select_upper_arm: clamp(snapshot.controls.select_upper_arm, 0, 1),
        select_forearm: clamp(snapshot.controls.select_forearm, 0, 1),
        select_wrist: clamp(snapshot.controls.select_wrist, 0, 1),
      },
      raw_input: snapshot.raw || null,
      timestamp_ms: Number(snapshot.timestamp_ms) || Date.now(),
    };
  }

  return {
    getState,
    applySnapshot,
  };
}
