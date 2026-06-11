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

  return engaged[0] || null;
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
  const precision = clamp(controls.precision, 0, 1);
  const stickX = Math.abs(clamp(controls.stick_x, -1, 1));
  const stickY = Math.abs(clamp(controls.stick_y, -1, 1));
  const stickThreshold = Math.max(0.02, cfg.stick_activity_epsilon);
  return (
    trigger <= cfg.trigger_release_threshold &&
    grip <= cfg.grip_release_threshold &&
    precision <= 0.1 &&
    stickX <= stickThreshold &&
    stickY <= stickThreshold
  );
}

export function createQuestControllerTeleop(options = {}) {
  const cfg = {
    movement_deadzone: Number.isFinite(Number(options.movement_deadzone))
      ? Number(options.movement_deadzone)
      : 0.003,
    max_control_offset: Number.isFinite(Number(options.max_control_offset))
      ? Number(options.max_control_offset)
      : 0.72,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 2.8
      : 4.5,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.68,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.12,
    anchor_reset_threshold_m: Number.isFinite(Number(options.anchor_reset_threshold_m))
      ? Number(options.anchor_reset_threshold_m)
      : 0.38,
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
      : 0.45,
    gripper_min: 0,
    gripper_max: 0.9,
    ee_activity_epsilon_m: Number.isFinite(Number(options.ee_activity_epsilon_m))
      ? Number(options.ee_activity_epsilon_m)
      : 0.0015,
    gripper_activity_epsilon: Number.isFinite(Number(options.gripper_activity_epsilon))
      ? Number(options.gripper_activity_epsilon)
      : 0.01,
  };

  let anchorController = null;
  let anchorEePose = null;
  let targetEePose = null;
  let smoothedBackendDelta = [0, 0, 0];
  let smoothedTrigger = 0;
  let motionEngaged = false;
  let activeControllerHand = "";
  let gripper = 0;
  let gripperInitialized = false;
  let commandGuardUntilMs = 0;
  let requireNeutralRelease = false;

  function getState() {
    return {
      selected_joint_group: CONTROL_GROUP,
      selected_joint_group_label: CONTROL_GROUP_LABEL,
      input_mode: "controller_ee_ik",
      group_sequence: [CONTROL_GROUP],
    };
  }

  function resetAnchor(controllerPosition, currentEePose) {
    anchorController = cloneVec3(controllerPosition);
    anchorEePose = cloneEePose(currentEePose);
    targetEePose = cloneEePose(currentEePose);
    smoothedBackendDelta = [0, 0, 0];
  }

  function clearAnchor() {
    anchorController = null;
    anchorEePose = null;
    targetEePose = null;
    smoothedBackendDelta = [0, 0, 0];
    motionEngaged = false;
    activeControllerHand = "";
  }

  function ensureAnchor(controllerPosition, currentEePose) {
    if (!anchorController || !anchorEePose || !targetEePose) {
      resetAnchor(controllerPosition, currentEePose);
      return;
    }

    const drift = vecNorm(vecSub(targetEePose.position, currentEePose.position));
    if (drift > cfg.anchor_reset_threshold_m) {
      resetAnchor(controllerPosition, currentEePose);
    }
  }

  function applySnapshot(
    snapshot,
    controllerPose,
    currentGripperOpening,
    currentEePose,
    dtSec = BASE_STEP_DT_SEC
  ) {
    const nowMs = Number(snapshot?.timestamp_ms) || Date.now();
    const currentPose = cloneEePose(currentEePose);
    if (!currentPose) {
      return { has_command: false, reason: "invalid_ee_state", ...getState() };
    }

    const currentGripper = clamp(currentGripperOpening, 0, 1);
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
    const activePose = motionController?.pose || controllerPoses.active || null;
    const rawInput = {
      ...(snapshot?.raw || {}),
      controller_pose: serializeControllerPose(activePose),
      controller_poses: {
        left: serializeControllerPose(controllerPoses.left),
        right: serializeControllerPose(controllerPoses.right),
        active: serializeControllerPose(activePose),
      },
    };

    if (requireNeutralRelease && isNeutralControlSnapshot(snapshot?.controls, cfg)) {
      requireNeutralRelease = false;
    }

    if (nowMs < commandGuardUntilMs || requireNeutralRelease) {
      gripper = lowPass(gripper, currentGripper, cfg.gripper_smoothing);
      clearAnchor();
      return {
        has_command: false,
        reason: "control_guard",
        target_positions: null,
        target_ee_pose: cloneEePose(targetEePose) || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        control_mode: "ik_pose",
        input_source: "quest3_controller",
        selected_joint_group: CONTROL_GROUP,
        selected_joint_group_label: CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        normalized_input: {
          trigger: 0,
          grip: 0,
          precision: precisionMode ? 1 : 0,
          control_mode: "ee_ik",
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
      return {
        has_command: false,
        reason: "controller_unavailable",
        target_positions: null,
        target_ee_pose: cloneEePose(targetEePose) || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        control_mode: "ik_pose",
        input_source: "quest3_controller",
        selected_joint_group: CONTROL_GROUP,
        selected_joint_group_label: CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        normalized_input: {
          control_mode: "ee_ik",
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

    const mappedGripper = cfg.gripper_min + smoothedTrigger * (cfg.gripper_max - cfg.gripper_min);
    gripper = lowPass(gripper, mappedGripper, cfg.gripper_smoothing);
    const nextGripper = clamp(gripper, cfg.gripper_min, cfg.gripper_max);

    const engaged = Boolean(motionController?.pose && motionController.engaged);
    let releaseHoldCommand = false;
    if (engaged && poseTracked) {
      if (!motionEngaged || activeControllerHand !== motionController.hand) {
        resetAnchor(motionController.pose.position, currentPose);
      } else {
        ensureAnchor(motionController.pose.position, currentPose);
      }
      const rawControllerDelta = applyVecDeadzone(
        vecSub(motionController.pose.position, anchorController),
        cfg.movement_deadzone
      );
      const gain = cfg.movement_gain * (precisionMode ? cfg.precision_scale : 1);
      const backendDelta = clampVecMagnitude(
        frontendDeltaToBackend(vecScale(rawControllerDelta, gain)),
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
      motionEngaged = true;
      activeControllerHand = motionController.hand;
    } else if (motionEngaged) {
      releaseHoldCommand = true;
      clearAnchor();
    }

    const eeError = targetEePose
      ? vecNorm(vecSub(targetEePose.position, currentPose.position))
      : 0;
    const eeMotion = vecNorm(smoothedBackendDelta);
    const hasEeActivity =
      releaseHoldCommand ||
      (engaged && (eeError > cfg.ee_activity_epsilon_m || eeMotion > cfg.ee_activity_epsilon_m));
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
      control_mode: "ik_pose",
      input_source: "quest3_controller",
      selected_joint_group: CONTROL_GROUP,
      selected_joint_group_label: CONTROL_GROUP_LABEL,
      changed_joint_group: false,
      normalized_input: {
        control_mode: "ee_ik",
        ee_active: hasEeActivity ? 1 : 0,
        ee_hold: releaseHoldCommand ? 1 : 0,
        trigger: smoothedTrigger,
        trigger_hand: triggerControl?.hand || "",
        grip: gripRaw,
        grip_active: engaged ? 1 : 0,
        active_hand: activeControllerHand || motionController?.hand || "",
        precision: precisionMode ? 1 : 0,
        controller_dx: Number(motionController?.pose?.position?.[0] || 0) - Number(anchorController?.[0] || 0),
        controller_dy: Number(motionController?.pose?.position?.[1] || 0) - Number(anchorController?.[1] || 0),
        controller_dz: Number(motionController?.pose?.position?.[2] || 0) - Number(anchorController?.[2] || 0),
        target_dx: smoothedBackendDelta[0],
        target_dy: smoothedBackendDelta[1],
        target_dz: smoothedBackendDelta[2],
        ee_error_m: eeError,
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
  }

  return {
    getState,
    applySnapshot,
    suppressCommands,
    reset,
  };
}
