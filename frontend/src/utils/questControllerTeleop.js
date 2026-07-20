import {
  BASE_STEP_DT_SEC,
  clamp,
  cloneEePose,
  cloneQuat,
  cloneVec3,
  createQuestEePoseTargetTracker,
  lowPass,
  vecNorm,
  vecSub,
} from "./questEePoseTarget.js";

const EE_CONTROL_GROUP = "end_effector";
const EE_CONTROL_GROUP_LABEL = "末端执行器";
const JOINT_GROUP_SEQUENCE = [
  { key: "upper_arm", label: "大臂组", joint_indices: [0, 1] },
  { key: "forearm", label: "前臂组", joint_indices: [2, 3] },
  { key: "wrist", label: "腕部组", joint_indices: [4, 5] },
];
const JOINT_GROUP_BY_KEY = Object.fromEntries(
  JOINT_GROUP_SEQUENCE.map((group) => [group.key, group])
);

function normalizeControllerStrategy(value) {
  // Keep Quest controller teleop on a single servo path so tuning remains
  // predictable and easier to maintain across frontend/backend updates.
  return "ee_servo";
}

function getJointGroupMeta(groupKey) {
  return JOINT_GROUP_BY_KEY[String(groupKey || "").trim()] || JOINT_GROUP_SEQUENCE[0];
}

function cloneArmJoints(value) {
  if (!Array.isArray(value) || value.length < 6) return null;
  const joints = value.slice(0, 6).map((item) => Number(item));
  return joints.every((item) => Number.isFinite(item)) ? joints : null;
}

function normalizeHandedness(value) {
  const handed = String(value || "").toLowerCase();
  if (handed === "left" || handed === "right") return handed;
  return "";
}

function cloneControllerPose(pose, fallbackHandedness = "") {
  const position = cloneVec3(pose?.position);
  if (!pose?.tracked || !position) return null;
  return {
    tracked: true,
    handedness: normalizeHandedness(pose?.handedness) || normalizeHandedness(fallbackHandedness),
    position,
    quaternion: cloneQuat(pose?.quaternion),
    pose_source: String(pose?.pose_source || ""),
    timestamp_ms: Number(pose?.timestamp_ms) || Date.now(),
  };
}

function normalizeControllerPoses(controllerPose) {
  const left = cloneControllerPose(controllerPose?.left, "left");
  const right = cloneControllerPose(controllerPose?.right, "right");
  let active = cloneControllerPose(controllerPose?.active);

  if (!active) {
    const singlePose = cloneControllerPose(controllerPose);
    if (singlePose) {
      active = singlePose;
    }
  }

  if (!active) {
    active = right || left || null;
  }

  return { left, right, active };
}

function readHandControl(controls, hand) {
  const handedness = normalizeHandedness(hand);
  const activeHand = normalizeHandedness(controls?.active_hand);
  const triggerKey = handedness ? `${handedness}_trigger` : "";
  const gripKey = handedness ? `${handedness}_grip` : "";
  const triggerFallback = activeHand === handedness ? controls?.trigger : 0;
  const gripFallback = activeHand === handedness ? controls?.grip : 0;
  return {
    hand: handedness,
    trigger: clamp(controls?.[triggerKey] ?? triggerFallback, 0, 1),
    grip: clamp(controls?.[gripKey] ?? gripFallback, 0, 1),
  };
}

function selectMotionController(controls, poses, cfg, currentHand) {
  const candidates = ["left", "right"].map((hand) => {
    const input = readHandControl(controls, hand);
    const isCurrent = hand === currentHand;
    return {
      ...input,
      pose: poses?.[hand] || null,
      engaged: isCurrent
        ? input.grip > cfg.grip_release_threshold
        : input.grip >= cfg.grip_engage_threshold,
      held: input.grip > cfg.grip_release_threshold,
    };
  });

  const current = candidates.find((item) => item.hand === currentHand);
  if (current?.pose && current.held) {
    return current;
  }

  const activeHand = normalizeHandedness(controls?.active_hand);
  const engaged = candidates
    .filter((item) => item.engaged)
    .sort((a, b) => {
      if (Boolean(a.pose) !== Boolean(b.pose)) return a.pose ? -1 : 1;
      if (b.grip !== a.grip) return b.grip - a.grip;
      if (a.hand === activeHand) return -1;
      if (b.hand === activeHand) return 1;
      return a.hand === "right" ? -1 : 1;
    });

  const selected = engaged[0] || null;
  if (selected?.pose || !selected?.engaged) return selected;

  const posedFallback = candidates.find((item) => item.pose);
  if (!posedFallback) return selected;
  return {
    ...posedFallback,
    grip: selected.grip,
    trigger: Math.max(posedFallback.trigger, selected.trigger),
    engaged: true,
    held: selected.held,
    input_hand: selected.hand,
  };
}

function selectGripperTrigger(controls, motionController) {
  if (motionController?.hand) {
    return readHandControl(controls, motionController.hand);
  }

  const activeHand = normalizeHandedness(controls?.active_hand);
  if (activeHand) {
    const active = readHandControl(controls, activeHand);
    if (active.trigger > 0) return active;
  }

  const left = readHandControl(controls, "left");
  const right = readHandControl(controls, "right");
  if (right.trigger >= left.trigger) return right;
  return left;
}

function serializeControllerPose(pose) {
  const cloned = cloneControllerPose(pose);
  if (!cloned) return null;
  return {
    handedness: cloned.handedness,
    position: cloned.position,
    quaternion: cloned.quaternion,
    pose_source: cloned.pose_source,
    timestamp_ms: cloned.timestamp_ms,
  };
}

function isNeutralControlSnapshot(controls, cfg) {
  if (!controls || typeof controls !== "object") return true;
  const trigger = Math.max(
    clamp(controls.trigger, 0, 1),
    clamp(controls.left_trigger, 0, 1),
    clamp(controls.right_trigger, 0, 1)
  );
  const grip = Math.max(
    clamp(controls.grip, 0, 1),
    clamp(controls.left_grip, 0, 1),
    clamp(controls.right_grip, 0, 1)
  );
  return (
    trigger <= cfg.trigger_release_threshold &&
    grip <= cfg.grip_release_threshold
  );
}

function readStickState(controls, hand) {
  const normalizedHand = normalizeHandedness(hand);
  const xKey = normalizedHand ? `${normalizedHand}_stick_x` : "stick_x";
  const yKey = normalizedHand ? `${normalizedHand}_stick_y` : "stick_y";
  const x = clamp(controls?.[xKey] ?? 0, -1, 1);
  const y = clamp(controls?.[yKey] ?? 0, -1, 1);
  return {
    hand: normalizedHand,
    x,
    y,
    magnitude: Math.abs(x) + Math.abs(y),
  };
}

function selectJointControlStick(controls, cfg) {
  const right = readStickState(controls, "right");
  const left = readStickState(controls, "left");
  const active = normalizeHandedness(controls?.active_hand);
  const epsilon = Math.max(0.01, Number(cfg.stick_activity_epsilon) || 0);

  if (right.magnitude > epsilon) return right;
  if (left.magnitude > epsilon) return left;
  if (active === "left") return left;
  return right.magnitude >= left.magnitude ? right : left;
}

export function createQuestControllerTeleop(options = {}) {
  const initialStrategy = normalizeControllerStrategy(options.control_strategy);
  const cfg = {
    control_strategy: initialStrategy,
    // Bias the default servo profile toward stable, low-jitter teleoperation.
    // We can always loosen these values later if we want more aggressive motion.
    movement_deadzone: Number.isFinite(Number(options.movement_deadzone))
      ? Number(options.movement_deadzone)
      : 0.006,
    max_control_offset: Number.isFinite(Number(options.max_control_offset))
      ? Number(options.max_control_offset)
      : 0.42,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 2.1
      : 3.0,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.72,
    orientation_smoothing: Number.isFinite(Number(options.orientation_smoothing))
      ? Number(options.orientation_smoothing)
      : 0.74,
    max_orientation_step_rad: Number.isFinite(Number(options.max_orientation_step_rad))
      ? Number(options.max_orientation_step_rad)
      : 0.24,
    orientation_gain: Number.isFinite(Number(options.orientation_gain))
      ? Number(options.orientation_gain)
      : 1.0,
    precision_orientation_gain: Number.isFinite(Number(options.precision_orientation_gain))
      ? Number(options.precision_orientation_gain)
      : 1.08,
    orientation_activity_epsilon_rad: Number.isFinite(Number(options.orientation_activity_epsilon_rad))
      ? Number(options.orientation_activity_epsilon_rad)
      : 0.016,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.04,
    anchor_reset_threshold_m: Number.isFinite(Number(options.anchor_reset_threshold_m))
      ? Number(options.anchor_reset_threshold_m)
      : 0.78,
    grip_engage_threshold: Number.isFinite(Number(options.grip_engage_threshold))
      ? Number(options.grip_engage_threshold)
      : 0.04,
    grip_release_threshold: Number.isFinite(Number(options.grip_release_threshold))
      ? Number(options.grip_release_threshold)
      : 0.02,
    trigger_engage_threshold: Number.isFinite(Number(options.trigger_engage_threshold))
      ? Number(options.trigger_engage_threshold)
      : 0.04,
    trigger_release_threshold: Number.isFinite(Number(options.trigger_release_threshold))
      ? Number(options.trigger_release_threshold)
      : 0.02,
    precision_scale: Number.isFinite(Number(options.precision_scale)) ? Number(options.precision_scale) : 0.4,
    stick_activity_epsilon: Number.isFinite(Number(options.stick_activity_epsilon))
      ? Number(options.stick_activity_epsilon)
      : 0.035,
    gripper_smoothing: Number.isFinite(Number(options.gripper_smoothing))
      ? Number(options.gripper_smoothing)
      : 0.82,
    gripper_min: 0,
    gripper_max: 1.0,
    ee_activity_epsilon_m: Number.isFinite(Number(options.ee_activity_epsilon_m))
      ? Number(options.ee_activity_epsilon_m)
      : 0.0015,
    gripper_activity_epsilon: Number.isFinite(Number(options.gripper_activity_epsilon))
      ? Number(options.gripper_activity_epsilon)
      : 0.01,
    position_target_blend: Number.isFinite(Number(options.position_target_blend))
      ? Number(options.position_target_blend)
      : 0.84,
    position_target_deadband_m: Number.isFinite(Number(options.position_target_deadband_m))
      ? Number(options.position_target_deadband_m)
      : 0.0008,
    orientation_target_deadband_rad: Number.isFinite(Number(options.orientation_target_deadband_rad))
      ? Number(options.orientation_target_deadband_rad)
      : 0.010,
    joint_step_rad_per_sec: Number.isFinite(Number(options.joint_step_rad_per_sec))
      ? Number(options.joint_step_rad_per_sec)
      : Math.max(0.45, clamp(Number(options.sensitivity) || 1.0, 0.4, 3.0) * 0.78),
    joint_axis_smoothing: Number.isFinite(Number(options.joint_axis_smoothing))
      ? Number(options.joint_axis_smoothing)
      : 0.34,
    joint_activity_epsilon_rad: Number.isFinite(Number(options.joint_activity_epsilon_rad))
      ? Number(options.joint_activity_epsilon_rad)
      : 0.0008,
  };

  const eeTargetTracker = createQuestEePoseTargetTracker({
    movement_deadzone: cfg.movement_deadzone,
    max_control_offset: cfg.max_control_offset,
    movement_smoothing: cfg.movement_smoothing,
    max_ee_step_m: cfg.max_ee_step_m,
    anchor_reset_threshold_m: cfg.anchor_reset_threshold_m,
    max_orientation_step_rad: cfg.max_orientation_step_rad,
    orientation_smoothing: cfg.orientation_smoothing,
    position_target_blend: cfg.position_target_blend,
    position_target_deadband_m: cfg.position_target_deadband_m,
    orientation_target_deadband_rad: cfg.orientation_target_deadband_rad,
  });
  let anchorController = null;
  let smoothedTrigger = 0;
  let motionEngaged = false;
  let activeControllerHand = "";
  let gripper = 0;
  let gripperInitialized = false;
  let commandGuardUntilMs = 0;
  let requireNeutralRelease = false;
  let selectedJointGroup = JOINT_GROUP_SEQUENCE[0].key;
  let jointTarget = null;
  let smoothedJointAxis = { x: 0, y: 0 };
  let selectionLatch = {
    upper_arm: false,
    forearm: false,
    wrist: false,
  };

  function getState() {
    const strategy = normalizeControllerStrategy(cfg.control_strategy);
    if (strategy === "joint_delta") {
      const group = getJointGroupMeta(selectedJointGroup);
      return {
        selected_joint_group: group.key,
        selected_joint_group_label: group.label,
        input_mode: "controller_joint_delta",
        group_sequence: JOINT_GROUP_SEQUENCE.map((item) => item.key),
      };
    }
    return {
      selected_joint_group: EE_CONTROL_GROUP,
      selected_joint_group_label: EE_CONTROL_GROUP_LABEL,
      input_mode: "controller_ee_servo",
      group_sequence: [EE_CONTROL_GROUP],
    };
  }

  function resetAnchor(controllerPosition, currentEePose, controllerQuaternion) {
    anchorController = cloneVec3(controllerPosition);
    eeTargetTracker.resetAnchor(controllerPosition, currentEePose, controllerQuaternion);
  }

  function clearAnchor() {
    anchorController = null;
    eeTargetTracker.clear();
    motionEngaged = false;
    activeControllerHand = "";
  }

  function syncSelectedJointGroup(controls) {
    const nextLatch = {
      upper_arm: clamp(controls?.select_upper_arm ?? 0, 0, 1) >= 0.5,
      forearm: clamp(controls?.select_forearm ?? 0, 0, 1) >= 0.5,
      wrist: clamp(controls?.select_wrist ?? 0, 0, 1) >= 0.5,
    };
    let changed = false;
    JOINT_GROUP_SEQUENCE.forEach((group) => {
      if (nextLatch[group.key] && !selectionLatch[group.key] && selectedJointGroup !== group.key) {
        selectedJointGroup = group.key;
        changed = true;
      }
    });
    selectionLatch = nextLatch;
    return changed;
  }

  function buildRawInput(snapshot, controllerPoses, activePose, strategy) {
    return {
      ...(snapshot?.raw || {}),
      control_strategy: strategy,
      controller_pose: serializeControllerPose(activePose),
      controller_poses: {
        left: serializeControllerPose(controllerPoses.left),
        right: serializeControllerPose(controllerPoses.right),
        active: serializeControllerPose(activePose),
      },
    };
  }

  function buildJointNoCommandResult({
    reason,
    nowMs,
    currentGripper,
    rawInput,
    precisionMode,
    triggerRaw,
    gripRaw,
    changedJointGroup,
    currentArm,
  }) {
    const state = getState();
    if (!jointTarget && currentArm) {
      jointTarget = currentArm.slice(0, 6);
    }
    return {
      has_command: false,
      reason,
      target_positions: jointTarget ? jointTarget.slice(0, 6) : currentArm,
      target_ee_pose: null,
      gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
      control_mode: "position",
      input_source: "quest3_controller",
      selected_joint_group: state.selected_joint_group,
      selected_joint_group_label: state.selected_joint_group_label,
      changed_joint_group: changedJointGroup,
      normalized_input: {
        control_mode: "joint_delta",
        ee_active: 0,
        trigger: triggerRaw,
        grip: gripRaw,
        grip_active: 0,
        precision: precisionMode ? 1 : 0,
        joint_group: state.selected_joint_group,
        joint_axis_x: Number(smoothedJointAxis.x || 0),
        joint_axis_y: Number(smoothedJointAxis.y || 0),
      },
      raw_input: rawInput,
      timestamp_ms: nowMs,
    };
  }

  function applyJointDeltaSnapshot({
    snapshot,
    nowMs,
    currentGripper,
    currentArm,
    precisionMode,
    triggerRaw,
    gripRaw,
    rawInput,
    changedJointGroup,
  }) {
    smoothedTrigger = lowPass(smoothedTrigger, triggerRaw, 0.65);
    const mappedGripper = cfg.gripper_min + smoothedTrigger * (cfg.gripper_max - cfg.gripper_min);
    gripper = lowPass(gripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(gripper, cfg.gripper_min, cfg.gripper_max);

    if (!currentArm) {
      return buildJointNoCommandResult({
        reason: "invalid_arm_state",
        nowMs,
        currentGripper,
        rawInput,
        precisionMode,
        triggerRaw,
        gripRaw,
        changedJointGroup,
        currentArm,
      });
    }

    if (!jointTarget || jointTarget.length < 6) {
      jointTarget = currentArm.slice(0, 6);
    }

    const stick = selectJointControlStick(snapshot?.controls || {}, cfg);
    const jointGrip = Math.max(
      gripRaw,
      clamp(snapshot?.controls?.right_grip ?? 0, 0, 1),
      clamp(snapshot?.controls?.left_grip ?? 0, 0, 1)
    );
    const engaged = jointGrip >= cfg.grip_engage_threshold;
    const rawAxisX = engaged ? clamp(stick.x, -1, 1) : 0;
    const rawAxisY = engaged ? clamp(-stick.y, -1, 1) : 0;
    smoothedJointAxis = {
      x: lowPass(smoothedJointAxis.x, rawAxisX, cfg.joint_axis_smoothing),
      y: lowPass(smoothedJointAxis.y, rawAxisY, cfg.joint_axis_smoothing),
    };

    const group = getJointGroupMeta(selectedJointGroup);
    const jointStepBase =
      cfg.joint_step_rad_per_sec *
      Math.max(0.25, Number(precisionMode ? cfg.precision_scale : 1.0)) *
      Math.max(BASE_STEP_DT_SEC * 0.5, Number(snapshot?.dt_sec) || BASE_STEP_DT_SEC);
    const jointDeltaA = smoothedJointAxis.x * jointStepBase;
    const jointDeltaB = smoothedJointAxis.y * jointStepBase;
    const hasJointActivity =
      engaged &&
      (Math.abs(jointDeltaA) > cfg.joint_activity_epsilon_rad ||
        Math.abs(jointDeltaB) > cfg.joint_activity_epsilon_rad);

    if (hasJointActivity) {
      const nextTarget = jointTarget.slice(0, 6);
      const [jointA, jointB] = group.joint_indices;
      nextTarget[jointA] += jointDeltaA;
      nextTarget[jointB] += jointDeltaB;
      jointTarget = nextTarget;
    } else if (!engaged) {
      jointTarget = currentArm.slice(0, 6);
    }

    const hasGripperActivity =
      Math.abs(nextGripper - currentGripper) > cfg.gripper_activity_epsilon;
    const hasCommand = hasJointActivity || hasGripperActivity;

    return {
      has_command: hasCommand,
      reason: hasJointActivity ? "joint_delta_active" : hasGripperActivity ? "gripper_only" : "idle",
      target_positions: jointTarget.slice(0, 6),
      target_ee_pose: null,
      gripper_opening: nextGripper,
      control_mode: "position",
      input_source: "quest3_controller",
      selected_joint_group: group.key,
      selected_joint_group_label: group.label,
      changed_joint_group: changedJointGroup,
      normalized_input: {
        control_mode: "joint_delta",
        ee_active: 0,
        trigger: smoothedTrigger,
        grip: gripRaw,
        grip_active: engaged ? 1 : 0,
        precision: precisionMode ? 1 : 0,
        active_hand: stick.hand || normalizeHandedness(snapshot?.controls?.active_hand),
        joint_group: group.key,
        joint_axis_x: Number(smoothedJointAxis.x || 0),
        joint_axis_y: Number(smoothedJointAxis.y || 0),
        joint_delta_a: jointDeltaA,
        joint_delta_b: jointDeltaB,
        joint_index_a: group.joint_indices[0],
        joint_index_b: group.joint_indices[1],
        joint_step_rad_per_sec: cfg.joint_step_rad_per_sec,
      },
      raw_input: rawInput,
      timestamp_ms: nowMs,
    };
  }

  function ensureAnchor(controllerPosition, currentEePose, controllerQuaternion) {
    if (!anchorController || !eeTargetTracker.getTargetPose()) {
      resetAnchor(controllerPosition, currentEePose, controllerQuaternion);
    }
  }

  function applySnapshot(
    snapshot,
    controllerPose,
    currentGripperOpening,
    currentEePose,
    currentArmJoints,
    dtSec = BASE_STEP_DT_SEC
  ) {
    const nowMs = Number(snapshot?.timestamp_ms) || Date.now();
    const currentPose = cloneEePose(currentEePose);
    if (!currentPose) {
      return { has_command: false, reason: "invalid_ee_state", ...getState() };
    }

    const currentGripper = clamp(currentGripperOpening, 0, 1);
    const currentArm = cloneArmJoints(currentArmJoints);
    if (!gripperInitialized) {
      gripper = currentGripper;
      gripperInitialized = true;
    }

    const controls = snapshot?.controls || {};
    const controllerPoses = normalizeControllerPoses(controllerPose);
    const motionController = selectMotionController(
      controls,
      controllerPoses,
      cfg,
      activeControllerHand
    );
    const triggerControl = selectGripperTrigger(controls, motionController);
    const triggerRaw = clamp(triggerControl?.trigger, 0, 1);
    const gripRaw = clamp(motionController?.grip, 0, 1);
    const precisionMode = clamp(snapshot?.controls?.precision, 0, 1) > 0.1;
    const poseTracked = Boolean(motionController?.pose?.tracked && Array.isArray(motionController?.pose?.position));
    const poseQuaternion = cloneQuat(motionController?.pose?.quaternion);
    const activePose = motionController?.pose || controllerPoses.active || null;
    const strategy = normalizeControllerStrategy(cfg.control_strategy);
    const changedJointGroup = strategy === "joint_delta" ? syncSelectedJointGroup(controls) : false;
    const rawInput = buildRawInput(snapshot, controllerPoses, activePose, strategy);

    if (requireNeutralRelease) {
      if (isNeutralControlSnapshot(snapshot?.controls, cfg) || nowMs >= commandGuardUntilMs) {
        requireNeutralRelease = false;
      }
    }

    if (nowMs < commandGuardUntilMs || requireNeutralRelease) {
      gripper = lowPass(gripper, currentGripper, cfg.gripper_smoothing);
      clearAnchor();
      if (strategy === "joint_delta") {
        return buildJointNoCommandResult({
          reason: "control_guard",
          nowMs,
          currentGripper,
          rawInput,
          precisionMode,
          triggerRaw,
          gripRaw,
          changedJointGroup,
          currentArm,
        });
      }
      return {
        has_command: false,
        reason: "control_guard",
        target_positions: null,
        target_ee_pose: eeTargetTracker.getTargetPose() || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        control_mode: "cartesian_servo",
        input_source: "quest3_controller",
        selected_joint_group: EE_CONTROL_GROUP,
        selected_joint_group_label: EE_CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        normalized_input: {
          trigger: 0,
          grip: 0,
          precision: precisionMode ? 1 : 0,
          control_mode: "ee_servo",
          ee_active: 0,
          active_hand: activeControllerHand || "",
        },
        raw_input: rawInput,
        timestamp_ms: nowMs,
      };
    }

    smoothedTrigger = lowPass(smoothedTrigger, triggerRaw, 0.65);
    if (!snapshot?.available || !snapshot?.has_device) {
      gripper = lowPass(gripper, currentGripper, cfg.gripper_smoothing);
      clearAnchor();
      if (strategy === "joint_delta") {
        return buildJointNoCommandResult({
          reason: "controller_unavailable",
          nowMs,
          currentGripper,
          rawInput,
          precisionMode,
          triggerRaw,
          gripRaw,
          changedJointGroup,
          currentArm,
        });
      }
      return {
        has_command: false,
        reason: "controller_unavailable",
        target_positions: null,
        target_ee_pose: eeTargetTracker.getTargetPose() || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        control_mode: "cartesian_servo",
        input_source: "quest3_controller",
        selected_joint_group: EE_CONTROL_GROUP,
        selected_joint_group_label: EE_CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        normalized_input: {
          control_mode: "ee_servo",
          ee_active: 0,
          trigger: triggerRaw,
          grip: gripRaw,
          precision: precisionMode ? 1 : 0,
          active_hand: activeControllerHand || "",
        },
        raw_input: rawInput,
        timestamp_ms: nowMs,
      };
    }

    if (strategy === "joint_delta") {
      clearAnchor();
      return applyJointDeltaSnapshot({
        snapshot: {
          ...snapshot,
          dt_sec: dtSec,
        },
        nowMs,
        currentGripper,
        currentArm,
        precisionMode,
        triggerRaw,
        gripRaw,
        rawInput,
        changedJointGroup,
      });
    }

    const mappedGripper = cfg.gripper_min + smoothedTrigger * (cfg.gripper_max - cfg.gripper_min);
    gripper = lowPass(gripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(gripper, cfg.gripper_min, cfg.gripper_max);

    const engaged = Boolean(motionController?.pose && motionController.engaged);
    let releaseHoldCommand = false;
    let eeTracking = null;
    // Grip acts as a 6DoF "grab" of the end effector. Precision keeps the same
    // orientation authority while reducing translation gain for wrist alignment.
    const positionFollowGain = precisionMode ? cfg.precision_scale : 1;
    const orientationFollowEnabled = engaged && Boolean(poseQuaternion);
    const orientationFollowGain = orientationFollowEnabled
      ? precisionMode
        ? Math.max(cfg.orientation_gain, cfg.precision_orientation_gain)
        : cfg.orientation_gain
      : 0;
    const eeFollowMode = orientationFollowEnabled
      ? precisionMode
        ? "anchored_absolute_6dof_precision"
        : "anchored_absolute_6dof"
      : "anchored_absolute_position";
    if (engaged && poseTracked) {
      if (!motionEngaged || activeControllerHand !== motionController.hand) {
        resetAnchor(motionController.pose.position, currentPose, poseQuaternion);
      } else {
        ensureAnchor(motionController.pose.position, currentPose, poseQuaternion);
      }
      eeTracking = eeTargetTracker.update({
        inputPosition: motionController.pose.position,
        inputQuaternion: poseQuaternion,
        currentEePose: currentPose,
        movementGain: positionFollowGain,
        orientationGain: orientationFollowGain,
        dtSec,
      });
      motionEngaged = true;
      activeControllerHand = motionController.hand;
    } else if (motionEngaged) {
      releaseHoldCommand = true;
      clearAnchor();
    }

    const targetEePose = eeTracking?.targetEePose || eeTargetTracker.getTargetPose();
    const eeError = Number(eeTracking?.eeError) || 0;
    const orientationError = Number(eeTracking?.orientationError) || 0;
    const eeMotion = vecNorm(eeTracking?.smoothedBackendDelta);
    const hasEeActivity =
      releaseHoldCommand ||
      (engaged &&
        (eeError > cfg.ee_activity_epsilon_m ||
          eeMotion > cfg.ee_activity_epsilon_m ||
          orientationError > cfg.orientation_activity_epsilon_rad));
    const hasGripperActivity =
      Math.abs(nextGripper - currentGripper) > cfg.gripper_activity_epsilon;
    const hasCommand = hasEeActivity || hasGripperActivity;
    const poseUnavailable = Boolean(motionController?.engaged && !poseTracked);

    return {
      has_command: hasCommand,
      reason: releaseHoldCommand
        ? "hold_current"
        : poseUnavailable
          ? "controller_pose_unavailable"
          : hasCommand
            ? "ok"
            : engaged
              ? "hold"
              : "idle",
      target_positions: null,
      target_ee_pose: cloneEePose(targetEePose) || currentPose,
      gripper_opening: nextGripper,
      control_mode: "cartesian_servo",
      input_source: "quest3_controller",
      selected_joint_group: EE_CONTROL_GROUP,
      selected_joint_group_label: EE_CONTROL_GROUP_LABEL,
      changed_joint_group: false,
      normalized_input: {
        control_mode: "ee_servo",
        ee_active: hasEeActivity ? 1 : 0,
        ee_hold: releaseHoldCommand ? 1 : 0,
        trigger: smoothedTrigger,
        trigger_hand: triggerControl?.hand || "",
        grip: gripRaw,
        grip_input_hand: motionController?.input_hand || motionController?.hand || "",
        grip_active: engaged ? 1 : 0,
        active_hand: activeControllerHand || motionController?.hand || "",
        pose_source: String(activePose?.pose_source || ""),
        precision: precisionMode ? 1 : 0,
        controller_dx: Number(motionController?.pose?.position?.[0] || 0) - Number(anchorController?.[0] || 0),
        controller_dy: Number(motionController?.pose?.position?.[1] || 0) - Number(anchorController?.[1] || 0),
        controller_dz: Number(motionController?.pose?.position?.[2] || 0) - Number(anchorController?.[2] || 0),
        target_dx: Number(eeTracking?.smoothedBackendDelta?.[0] || 0),
        target_dy: Number(eeTracking?.smoothedBackendDelta?.[1] || 0),
        target_dz: Number(eeTracking?.smoothedBackendDelta?.[2] || 0),
        ee_error_m: eeError,
        orientation_error_rad: orientationError,
        movement_gain: positionFollowGain,
        orientation_gain: orientationFollowGain,
        orientation_follow_enabled: orientationFollowEnabled ? 1 : 0,
        orientation_active:
          orientationFollowEnabled && orientationError > cfg.orientation_activity_epsilon_rad ? 1 : 0,
        ee_follow_mode: eeFollowMode,
        max_control_offset_m: cfg.max_control_offset,
      },
      raw_input: rawInput,
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
    clearAnchor();
    smoothedTrigger = 0;
    activeControllerHand = "";
    gripper = 0;
    gripperInitialized = false;
    commandGuardUntilMs = 0;
    requireNeutralRelease = false;
    selectedJointGroup = JOINT_GROUP_SEQUENCE[0].key;
    jointTarget = null;
    smoothedJointAxis = { x: 0, y: 0 };
    selectionLatch = {
      upper_arm: false,
      forearm: false,
      wrist: false,
    };
  }

  return {
    getState,
    applySnapshot,
    suppressCommands,
    reset,
  };
}
