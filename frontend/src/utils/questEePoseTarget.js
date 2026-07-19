export const BASE_STEP_DT_SEC = 1 / 50;
const BACKEND_FRAME_Z_OFFSET = 0.5;
const FRONTEND_TO_BACKEND_QUAT_WXYZ = [
  Math.SQRT1_2,
  Math.SQRT1_2,
  0,
  0,
];

export function clamp(value, min, max) {
  return Math.min(Math.max(Number(value) || 0, min), max);
}

export function lowPass(previous, next, alpha) {
  const a = clamp(alpha, 0, 1);
  return previous + (next - previous) * a;
}

export function normalizeDtScale(dtSec) {
  const dt = Number(dtSec);
  if (!Number.isFinite(dt)) return 1;
  const bounded = clamp(dt, 1 / 120, 1 / 10);
  return bounded / BASE_STEP_DT_SEC;
}

export function applyDeadzone(value, deadzone) {
  const x = clamp(value, 0, 1);
  if (x <= deadzone) return 0;
  return (x - deadzone) / (1 - deadzone);
}

export function cloneVec3(value) {
  if (!Array.isArray(value) || value.length < 3) return null;
  const cloned = value.slice(0, 3).map((item) => Number(item));
  return cloned.every((item) => Number.isFinite(item)) ? cloned : null;
}

export function cloneQuat(value) {
  if (!Array.isArray(value) || value.length < 4) return null;
  const cloned = value.slice(0, 4).map((item) => Number(item));
  return cloned.every((item) => Number.isFinite(item)) ? cloned : null;
}

export function cloneEePose(pose) {
  const position = cloneVec3(pose?.position);
  const quaternion = cloneQuat(pose?.quaternion);
  if (!position || !quaternion) return null;
  return { position, quaternion };
}

export function normalizeQuatWxyz(quaternion) {
  const q = cloneQuat(quaternion);
  if (!q) return null;
  const [w, x, y, z] = q;
  const norm = Math.sqrt(w * w + x * x + y * y + z * z);
  if (norm <= 1e-8) return [1, 0, 0, 0];
  return [w / norm, x / norm, y / norm, z / norm];
}

export function quatMultiplyWxyz(lhs, rhs) {
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

export function quatConjugateWxyz(quaternion) {
  const q = normalizeQuatWxyz(quaternion);
  if (!q) return null;
  return [q[0], -q[1], -q[2], -q[3]];
}

export function quatDotWxyz(lhs, rhs) {
  const a = normalizeQuatWxyz(lhs);
  const b = normalizeQuatWxyz(rhs);
  if (!a || !b) return 1;
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
}

export function quatAngleDistanceRad(lhs, rhs) {
  const dot = Math.abs(clamp(quatDotWxyz(lhs, rhs), -1, 1));
  return 2 * Math.acos(dot);
}

export function slerpQuatWxyz(from, to, alpha) {
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

export function clampQuatStepWxyz(previous, next, maxStepRad) {
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

export function scaleQuatRotationWxyz(quaternion, gain) {
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

export function vecSub(a, b) {
  return [
    Number(a?.[0] || 0) - Number(b?.[0] || 0),
    Number(a?.[1] || 0) - Number(b?.[1] || 0),
    Number(a?.[2] || 0) - Number(b?.[2] || 0),
  ];
}

export function vecAdd(a, b) {
  return [
    Number(a?.[0] || 0) + Number(b?.[0] || 0),
    Number(a?.[1] || 0) + Number(b?.[1] || 0),
    Number(a?.[2] || 0) + Number(b?.[2] || 0),
  ];
}

export function vecScale(a, scale) {
  const s = Number(scale) || 0;
  return [
    Number(a?.[0] || 0) * s,
    Number(a?.[1] || 0) * s,
    Number(a?.[2] || 0) * s,
  ];
}

export function vecNorm(a) {
  const x = Number(a?.[0] || 0);
  const y = Number(a?.[1] || 0);
  const z = Number(a?.[2] || 0);
  return Math.sqrt(x * x + y * y + z * z);
}

export function lowPassVec(previous, next, alpha) {
  const prev = cloneVec3(previous) || [0, 0, 0];
  const n = cloneVec3(next) || [0, 0, 0];
  return [
    lowPass(prev[0], n[0], alpha),
    lowPass(prev[1], n[1], alpha),
    lowPass(prev[2], n[2], alpha),
  ];
}

export function clampVecMagnitude(vector, maxMagnitude) {
  const max = Math.max(0, Number(maxMagnitude) || 0);
  const magnitude = vecNorm(vector);
  if (max <= 0 || magnitude <= max || magnitude <= 1e-8) {
    return cloneVec3(vector) || [0, 0, 0];
  }
  return vecScale(vector, max / magnitude);
}

export function clampVecStep(previous, next, maxStep) {
  const prev = cloneVec3(previous);
  const n = cloneVec3(next);
  if (!prev || !n) return n || prev || [0, 0, 0];
  const delta = vecSub(n, prev);
  return vecAdd(prev, clampVecMagnitude(delta, maxStep));
}

export function applyVecDeadzone(vector, deadzone) {
  const magnitude = vecNorm(vector);
  const dz = Math.max(0, Number(deadzone) || 0);
  if (magnitude <= dz || magnitude <= 1e-8) return [0, 0, 0];
  return vecScale(vector, (magnitude - dz) / magnitude);
}

export function frontendDeltaToBackend(delta) {
  return [delta[0], -delta[2], delta[1]];
}

export function frontendPositionToBackend(position) {
  const vec = cloneVec3(position);
  if (!vec) return null;
  return [vec[0], -vec[2], vec[1] + BACKEND_FRAME_Z_OFFSET];
}

export function frontendQuatToBackendWxyz(quaternionXyzw) {
  const q = cloneQuat(quaternionXyzw);
  if (!q) return null;
  const frontendWxyz = [q[3], q[0], q[1], q[2]];
  return quatMultiplyWxyz(FRONTEND_TO_BACKEND_QUAT_WXYZ, frontendWxyz);
}

export function rotateVectorByQuatWxyz(vector, quaternion) {
  const v = cloneVec3(vector);
  const q = normalizeQuatWxyz(quaternion);
  if (!v || !q) return null;
  const [w, x, y, z] = q;
  const uv = [
    y * v[2] - z * v[1],
    z * v[0] - x * v[2],
    x * v[1] - y * v[0],
  ];
  const uuv = [
    y * uv[2] - z * uv[1],
    z * uv[0] - x * uv[2],
    x * uv[1] - y * uv[0],
  ];
  return [
    v[0] + 2 * (w * uv[0] + uuv[0]),
    v[1] + 2 * (w * uv[1] + uuv[1]),
    v[2] + 2 * (w * uv[2] + uuv[2]),
  ];
}

export function composePoseWxyz(parentPose, childPose) {
  const parentPosition = cloneVec3(parentPose?.position);
  const parentQuaternion = normalizeQuatWxyz(parentPose?.quaternion);
  const childPosition = cloneVec3(childPose?.position);
  const childQuaternion = normalizeQuatWxyz(childPose?.quaternion);
  if (!parentPosition || !parentQuaternion || !childPosition || !childQuaternion) {
    return null;
  }
  const rotatedChildPosition = rotateVectorByQuatWxyz(childPosition, parentQuaternion);
  if (!rotatedChildPosition) return null;
  return {
    position: vecAdd(parentPosition, rotatedChildPosition),
    quaternion: quatMultiplyWxyz(parentQuaternion, childQuaternion),
  };
}

export function invertPoseWxyz(pose) {
  const position = cloneVec3(pose?.position);
  const quaternion = normalizeQuatWxyz(pose?.quaternion);
  if (!position || !quaternion) return null;
  const invertedQuaternion = quatConjugateWxyz(quaternion);
  const invertedPosition = rotateVectorByQuatWxyz(
    vecScale(position, -1),
    invertedQuaternion
  );
  if (!invertedQuaternion || !invertedPosition) return null;
  return {
    position: invertedPosition,
    quaternion: invertedQuaternion,
  };
}

export function relativePoseWxyz(referencePose, targetPose) {
  const invertedReference = invertPoseWxyz(referencePose);
  if (!invertedReference) return null;
  return composePoseWxyz(invertedReference, targetPose);
}

export function createQuestEePoseTargetTracker(options = {}) {
  const cfg = {
    mapping_mode: String(options.mapping_mode || "anchored_absolute").trim() || "anchored_absolute",
    movement_deadzone: Number.isFinite(Number(options.movement_deadzone))
      ? Number(options.movement_deadzone)
      : 0.003,
    max_control_offset: Number.isFinite(Number(options.max_control_offset))
      ? Number(options.max_control_offset)
      : 0.42,
    movement_smoothing: Number.isFinite(Number(options.movement_smoothing))
      ? Number(options.movement_smoothing)
      : 0.72,
    max_ee_step_m: Number.isFinite(Number(options.max_ee_step_m))
      ? Number(options.max_ee_step_m)
      : 0.05,
    position_target_blend: Number.isFinite(Number(options.position_target_blend))
      ? Number(options.position_target_blend)
      : 0.88,
    position_target_deadband_m: Number.isFinite(Number(options.position_target_deadband_m))
      ? Number(options.position_target_deadband_m)
      : 0.0008,
    anchor_reset_threshold_m: Number.isFinite(Number(options.anchor_reset_threshold_m))
      ? Number(options.anchor_reset_threshold_m)
      : 0.8,
    max_orientation_step_rad: Number.isFinite(Number(options.max_orientation_step_rad))
      ? Number(options.max_orientation_step_rad)
      : 0.28,
    orientation_smoothing: Number.isFinite(Number(options.orientation_smoothing))
      ? Number(options.orientation_smoothing)
      : 0.72,
    orientation_target_deadband_rad: Number.isFinite(Number(options.orientation_target_deadband_rad))
      ? Number(options.orientation_target_deadband_rad)
      : 0.008,
  };

  let anchorInputPosition = null;
  let anchorInputQuaternion = null;
  let anchorInputBackendPose = null;
  let anchorInputToEePose = null;
  let anchorEePose = null;
  let targetEePose = null;
  let smoothedBackendDelta = [0, 0, 0];

  function buildBackendInputPose(inputPosition, inputQuaternion) {
    const position = frontendPositionToBackend(inputPosition);
    if (!position) return null;
    return {
      position,
      quaternion: frontendQuatToBackendWxyz(inputQuaternion),
    };
  }

  function resetAnchor(inputPosition, currentEePose, inputQuaternion) {
    anchorInputPosition = cloneVec3(inputPosition);
    anchorInputQuaternion = frontendQuatToBackendWxyz(inputQuaternion);
    anchorEePose = cloneEePose(currentEePose);
    targetEePose = cloneEePose(currentEePose);
    smoothedBackendDelta = [0, 0, 0];
    anchorInputBackendPose = buildBackendInputPose(inputPosition, inputQuaternion);
    // Record the initial device->EE offset once so later frames can rebuild
    // an absolute EE target directly from the latest tracked hand/controller pose.
    anchorInputToEePose =
      anchorInputBackendPose?.quaternion && anchorEePose?.quaternion
        ? relativePoseWxyz(anchorInputBackendPose, anchorEePose)
        : null;
  }

  function clear() {
    anchorInputPosition = null;
    anchorInputQuaternion = null;
    anchorInputBackendPose = null;
    anchorInputToEePose = null;
    anchorEePose = null;
    targetEePose = null;
    smoothedBackendDelta = [0, 0, 0];
  }

  function ensureAnchor(inputPosition, currentEePose, inputQuaternion) {
    if (!anchorInputPosition || !anchorEePose || !targetEePose) {
      resetAnchor(inputPosition, currentEePose, inputQuaternion);
      return;
    }

    if (!anchorInputQuaternion && cloneQuat(inputQuaternion)) {
      anchorInputQuaternion = frontendQuatToBackendWxyz(inputQuaternion);
    }
    if (!anchorInputBackendPose) {
      anchorInputBackendPose = buildBackendInputPose(inputPosition, inputQuaternion);
    }
    if (!anchorInputToEePose && anchorInputBackendPose?.quaternion && anchorEePose?.quaternion) {
      anchorInputToEePose = relativePoseWxyz(anchorInputBackendPose, anchorEePose);
    }
  }

  function update({
    inputPosition,
    inputQuaternion,
    currentEePose,
    movementGain = 1,
    orientationGain = 1,
    dtSec = BASE_STEP_DT_SEC,
  } = {}) {
    const currentPose = cloneEePose(currentEePose);
    const trackedPosition = cloneVec3(inputPosition);
    if (!currentPose || !trackedPosition) return null;

    ensureAnchor(trackedPosition, currentPose, inputQuaternion);

    const rawInputDelta = vecSub(trackedPosition, anchorInputPosition);
    const backendInputPose = buildBackendInputPose(trackedPosition, inputQuaternion);
    let desiredPosition = cloneVec3(currentPose.position) || [0, 0, 0];
    let desiredQuaternion =
      cloneQuat(anchorEePose?.quaternion) ||
      cloneQuat(currentPose.quaternion) ||
      [1, 0, 0, 0];

    if (cfg.mapping_mode === "direct_absolute" && backendInputPose) {
      // Direct absolute follow uses the live tracked world pose as the EE
      // position target so hand teleop can behave like "my hand is the target".
      desiredPosition = cloneVec3(backendInputPose.position) || desiredPosition;

      if (orientationGain > 0 && anchorInputQuaternion && backendInputPose.quaternion && anchorEePose) {
        const inputDeltaQuaternion = quatMultiplyWxyz(
          backendInputPose.quaternion,
          quatConjugateWxyz(anchorInputQuaternion)
        );
        const scaledInputDeltaQuaternion =
          scaleQuatRotationWxyz(inputDeltaQuaternion, orientationGain) || inputDeltaQuaternion;
        desiredQuaternion =
          quatMultiplyWxyz(scaledInputDeltaQuaternion, anchorEePose.quaternion) || desiredQuaternion;
      }

      smoothedBackendDelta = lowPassVec(
        smoothedBackendDelta,
        vecSub(desiredPosition, currentPose.position),
        cfg.movement_smoothing
      );
    } else if (
      cfg.mapping_mode === "anchored_absolute" &&
      backendInputPose &&
      anchorInputBackendPose &&
      anchorEePose
    ) {
      // In anchored absolute mode we preserve the initial grab offset but let the
      // live tracked pose drive the EE target directly, which feels much closer to
      // "the robot end effector follows my hand/controller".
      const anchorBackendPosition = cloneVec3(anchorInputBackendPose.position) || [0, 0, 0];
      const currentBackendPosition = cloneVec3(backendInputPose.position) || anchorBackendPosition;
      const positionDelta = vecSub(currentBackendPosition, anchorBackendPosition);
      const scaledInputPosition = vecAdd(
        anchorBackendPosition,
        clampVecMagnitude(vecScale(positionDelta, movementGain), cfg.max_control_offset)
      );

      let scaledInputQuaternion = anchorInputQuaternion || backendInputPose.quaternion || null;
      if (anchorInputQuaternion && backendInputPose?.quaternion) {
        const inputDeltaQuaternion = quatMultiplyWxyz(
          backendInputPose.quaternion,
          quatConjugateWxyz(anchorInputQuaternion)
        );
        const scaledInputDeltaQuaternion =
          scaleQuatRotationWxyz(inputDeltaQuaternion, orientationGain) || inputDeltaQuaternion;
        scaledInputQuaternion =
          quatMultiplyWxyz(scaledInputDeltaQuaternion, anchorInputQuaternion) || scaledInputQuaternion;
      }

      if (anchorInputToEePose && scaledInputQuaternion) {
        const desiredPose = composePoseWxyz(
          {
            position: scaledInputPosition,
            quaternion: scaledInputQuaternion,
          },
          anchorInputToEePose
        );
        if (desiredPose?.position) {
          desiredPosition = desiredPose.position;
        }
        if (desiredPose?.quaternion) {
          desiredQuaternion = desiredPose.quaternion;
        }
      }
      smoothedBackendDelta = lowPassVec(
        smoothedBackendDelta,
        vecSub(desiredPosition, anchorEePose.position),
        cfg.movement_smoothing
      );
    } else if (anchorEePose) {
      const backendDelta = clampVecMagnitude(
        frontendDeltaToBackend(vecScale(rawInputDelta, movementGain)),
        cfg.max_control_offset
      );
      smoothedBackendDelta = lowPassVec(
        smoothedBackendDelta,
        backendDelta,
        cfg.movement_smoothing
      );
      desiredPosition = vecAdd(anchorEePose.position, smoothedBackendDelta);
      const inputQuaternionBackend = frontendQuatToBackendWxyz(inputQuaternion);
      if (anchorInputQuaternion && inputQuaternionBackend) {
        const inputDeltaRaw = quatMultiplyWxyz(
          inputQuaternionBackend,
          quatConjugateWxyz(anchorInputQuaternion)
        );
        const inputDelta =
          scaleQuatRotationWxyz(inputDeltaRaw, orientationGain) || inputDeltaRaw;
        desiredQuaternion =
          quatMultiplyWxyz(inputDelta, anchorEePose.quaternion) || desiredQuaternion;
      }
    }

    const maxStep = Math.max(0.008, cfg.max_ee_step_m * normalizeDtScale(dtSec));
    const previousPosition = targetEePose?.position || currentPose.position;
    const limitedPosition = clampVecStep(previousPosition, desiredPosition, maxStep);
    const positionStep = vecNorm(vecSub(limitedPosition, previousPosition));
    const nextPosition =
      positionStep <= cfg.position_target_deadband_m
        ? cloneVec3(previousPosition)
        : lowPassVec(previousPosition, limitedPosition, cfg.position_target_blend);

    const maxOrientationStep = Math.max(
      0.02,
      cfg.max_orientation_step_rad * normalizeDtScale(dtSec)
    );
    const previousQuaternion = targetEePose?.quaternion || currentPose.quaternion;
    const limitedQuaternion = clampQuatStepWxyz(
      previousQuaternion,
      desiredQuaternion,
      maxOrientationStep
    );
    const orientationStep = quatAngleDistanceRad(previousQuaternion, limitedQuaternion);
    const nextQuaternion =
      orientationStep <= cfg.orientation_target_deadband_rad
        ? cloneQuat(previousQuaternion)
        : slerpQuatWxyz(previousQuaternion, limitedQuaternion, cfg.orientation_smoothing);

    targetEePose = {
      position: nextPosition || cloneVec3(previousPosition) || [0, 0, 0],
      quaternion: nextQuaternion || cloneQuat(previousQuaternion) || [1, 0, 0, 0],
    };

    return {
      targetEePose: cloneEePose(targetEePose),
      rawInputDelta,
      smoothedBackendDelta: cloneVec3(smoothedBackendDelta) || [0, 0, 0],
      eeError: vecNorm(vecSub(targetEePose.position, currentPose.position)),
      orientationError: quatAngleDistanceRad(targetEePose.quaternion, currentPose.quaternion),
    };
  }

  function getTargetPose() {
    return cloneEePose(targetEePose);
  }

  return {
    resetAnchor,
    clear,
    update,
    getTargetPose,
  };
}
