import {
  applyDeadzone,
  BASE_STEP_DT_SEC,
  clamp,
  cloneEePose,
  cloneQuat,
  cloneVec3,
  createQuestEePoseTargetTracker,
  lowPass,
  vecNorm,
} from "./questEePoseTarget.js";

const CONTROL_GROUP = "end_effector";
const CONTROL_GROUP_LABEL = "末端执行器";

function midpointVec3(a, b) {
  if (!a || !b) return a || b || null;
  return [
    (Number(a[0]) + Number(b[0])) * 0.5,
    (Number(a[1]) + Number(b[1])) * 0.5,
    (Number(a[2]) + Number(b[2])) * 0.5,
  ];
}

function readRightHandControlPose(snapshot) {
  const rightHand = snapshot?.hands?.right || {};
  const rawJoints = snapshot?.raw?.right?.raw_joints || {};
  const thumbTip = cloneVec3(rawJoints.thumb);
  const indexTip = cloneVec3(rawJoints.index);
  const palmPosition = cloneVec3(rightHand.palm_position);
  const controlPosition = midpointVec3(thumbTip, indexTip) || indexTip || thumbTip || palmPosition;
  return {
    position: controlPosition,
    quaternion: cloneQuat(rightHand.palm_quaternion),
    controlPoint: thumbTip && indexTip ? "pinch_center" : "palm",
  };
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
      : 0.0045,
    max_control_offset: Number.isFinite(Number(options.max_control_offset))
      ? Number(options.max_control_offset)
      : 0.42,
    movement_gain: Number.isFinite(Number(options.sensitivity))
      ? Number(options.sensitivity) * 2.0
      : 3.0,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.76,
    orientation_smoothing: Number.isFinite(Number(options.orientation_smoothing))
      ? Number(options.orientation_smoothing)
      : 0.70,
    max_orientation_step_rad: Number.isFinite(Number(options.max_orientation_step_rad))
      ? Number(options.max_orientation_step_rad)
      : 0.20,
    orientation_gain: Number.isFinite(Number(options.orientation_gain))
      ? Number(options.orientation_gain)
      : 0.95,
    orientation_activity_epsilon_rad: Number.isFinite(Number(options.orientation_activity_epsilon_rad))
      ? Number(options.orientation_activity_epsilon_rad)
      : 0.016,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.045,
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
    position_target_blend: Number.isFinite(Number(options.position_target_blend))
      ? Number(options.position_target_blend)
      : 0.86,
    position_target_deadband_m: Number.isFinite(Number(options.position_target_deadband_m))
      ? Number(options.position_target_deadband_m)
      : 0.0008,
    orientation_target_deadband_rad: Number.isFinite(Number(options.orientation_target_deadband_rad))
      ? Number(options.orientation_target_deadband_rad)
      : 0.010,
  };

  const eeTargetTracker = createQuestEePoseTargetTracker({
    mapping_mode: "anchored_absolute",
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
      input_mode: "right_hand_ee_servo",
      tracking_stable: false,
      group_sequence: [CONTROL_GROUP],
    };
  }

  function resetAnchor(rightPalm, currentEePose, rightPalmQuaternion) {
    eeTargetTracker.resetAnchor(rightPalm, currentEePose, rightPalmQuaternion);
  }

  function ensureAnchor(rightPalm, currentEePose, rightPalmQuaternion) {
    if (!eeTargetTracker.getTargetPose()) {
      resetAnchor(rightPalm, currentEePose, rightPalmQuaternion);
    }
  }

  function clearTrackingLatch() {
    eeTargetTracker.clear();
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
    const controlPose = readRightHandControlPose(snapshot);
    const rightControlPosition = cloneVec3(controlPose.position);
    const rightPalmQuaternion = cloneQuat(controlPose.quaternion);
    const trackingStability = clamp(rightHand.stability ?? snapshot?.tracking_stability, 0, 1);
    const trackingPresent = Boolean(rightTracked && rightControlPosition);
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

    if (!snapshot?.available || !trackingStable || !rightTracked || !rightControlPosition) {
      const recentlyTracked = lastTrackedAt > 0 && now - lastTrackedAt <= cfg.tracking_grace_ms;
      gripper = lowPass(gripper, currentGripper, cfg.gripper_smoothing);
      if (!recentlyTracked) {
        clearTrackingLatch();
      }
      return {
        has_command: false,
        reason: "hand_unavailable",
        target_positions: Array.isArray(currentArmRadians) ? currentArmRadians.slice(0, 6) : null,
        target_ee_pose: eeTargetTracker.getTargetPose() || currentPose,
        gripper_opening: clamp(gripper, cfg.gripper_min, cfg.gripper_max),
        input_source: "quest3_hand",
        selected_joint_group: CONTROL_GROUP,
        selected_joint_group_label: CONTROL_GROUP_LABEL,
        changed_joint_group: false,
        tracking_stable: false,
        tracking_stability: trackingStability,
        hand_input_mode: "right_hand_ee_servo",
        normalized_input: {
          control_mode: "ee_servo",
          ee_active: 0,
          fist: smoothedFist,
          grip: gripper,
          hand_control_point: controlPose.controlPoint,
          tracking_stability: trackingStability,
        },
        raw_input: snapshot?.raw || null,
        timestamp_ms: Number(snapshot?.timestamp_ms) || Date.now(),
      };
    }

    lastTrackedAt = now;
    ensureAnchor(rightControlPosition, currentPose, rightPalmQuaternion);
    // Use the live pinch center as the hand control point, but keep the
    // anchored-absolute mapping so the robot follows the hand smoothly inside
    // the shared scene instead of jumping to a raw absolute XR world pose.
    const positionFollowGain = clamp(cfg.movement_gain, 0.4, 6.0);
    const orientationFollowEnabled = false;
    const orientationFollowGain = orientationFollowEnabled ? 1 : 0;
    const eeTracking = eeTargetTracker.update({
      inputPosition: rightControlPosition,
      inputQuaternion: rightPalmQuaternion,
      currentEePose: currentPose,
      movementGain: positionFollowGain,
      orientationGain: orientationFollowGain,
      dtSec,
    });
    const targetEePose = eeTracking?.targetEePose || eeTargetTracker.getTargetPose() || currentPose;

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

    const eeError = Number(eeTracking?.eeError) || 0;
    const orientationError = Number(eeTracking?.orientationError) || 0;
    const handMotion = vecNorm(eeTracking?.smoothedBackendDelta);
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
      control_mode: "cartesian_servo",
      input_source: "quest3_hand",
      selected_joint_group: CONTROL_GROUP,
      selected_joint_group_label: CONTROL_GROUP_LABEL,
      changed_joint_group: false,
      tracking_stable: trackingStable,
      tracking_stability: trackingStability,
      hand_input_mode: "right_hand_ee_servo",
      normalized_input: {
        control_mode: "ee_servo",
        ee_active: hasEeActivity ? 1 : 0,
        palm_dx: Number(eeTracking?.rawInputDelta?.[0] || 0),
        palm_dy: Number(eeTracking?.rawInputDelta?.[1] || 0),
        palm_dz: Number(eeTracking?.rawInputDelta?.[2] || 0),
        target_dx: Number(eeTracking?.smoothedBackendDelta?.[0] || 0),
        target_dy: Number(eeTracking?.smoothedBackendDelta?.[1] || 0),
        target_dz: Number(eeTracking?.smoothedBackendDelta?.[2] || 0),
        ee_error_m: eeError,
        orientation_error_rad: orientationError,
        movement_gain: positionFollowGain,
        orientation_gain: orientationFollowGain,
        orientation_follow_enabled: orientationFollowEnabled ? 1 : 0,
        hand_control_point: controlPose.controlPoint,
        ee_follow_mode: "anchored_absolute",
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
    eeTargetTracker.clear();
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
