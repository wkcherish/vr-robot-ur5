export const CLIENT_PHYSICS_DIAGNOSTICS_MIN_INTERVAL_MS = 250;

function clampNumber(value, min, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return min;
  return Math.min(Math.max(numeric, min), max);
}

function scaleInterpolationAlpha(alpha, dtSec) {
  const baseAlpha = clampNumber(alpha, 0.01, 1.0);
  const frameScale = clampNumber((Number(dtSec) || 1 / 60) * 60, 0.25, 2.5);
  return 1 - Math.pow(1 - baseAlpha, frameScale);
}

function getAdaptiveRenderAlpha(baseAlpha, errorRad, lowErrorRad, highErrorRad) {
  const base = clampNumber(baseAlpha, 0.01, 1.0);
  const low = Number(lowErrorRad);
  const high = Number(highErrorRad);
  const range = Number.isFinite(high) && Number.isFinite(low) && high > low ? high - low : 1;
  const t = clampNumber((Math.abs(Number(errorRad) || 0) - low) / range, 0, 1);
  return base * (0.45 + 1.3 * t);
}

export function getSceneJointInterpolationAlphaForMode({
  vrModeEntered,
  backendPoseSmoothingEnabled,
  backendPoseSmoothingAlpha,
  vrRenderSmoothingAlpha,
  dtSec = 1 / 60,
  errorRad = 0,
  lowErrorRad = 0.006,
  highErrorRad = 0.18,
} = {}) {
  if (vrModeEntered === true) {
    return scaleInterpolationAlpha(
      getAdaptiveRenderAlpha(vrRenderSmoothingAlpha, errorRad, lowErrorRad, highErrorRad),
      dtSec
    );
  }

  if (backendPoseSmoothingEnabled !== true) return 1.0;
  const alpha = Number(backendPoseSmoothingAlpha);
  if (!Number.isFinite(alpha)) return 1.0;
  return scaleInterpolationAlpha(
    getAdaptiveRenderAlpha(alpha, errorRad, lowErrorRad, highErrorRad),
    dtSec
  );
}

export function shouldApplyBackendPoseImmediately(options = {}) {
  return options?.immediate === true;
}

export function shouldRunClientPhysicsDiagnostics({
  strictAuthority,
  debugProxiesEnabled,
  nowMs,
  lastRunAtMs,
  minIntervalMs = CLIENT_PHYSICS_DIAGNOSTICS_MIN_INTERVAL_MS,
} = {}) {
  if (strictAuthority !== true) return false;
  if (debugProxiesEnabled !== true) return false;

  const now = Number(nowMs);
  const lastRun = Number(lastRunAtMs || 0);
  const minInterval = Math.max(0, Number(minIntervalMs) || 0);
  if (!Number.isFinite(now)) return false;
  return now - lastRun >= minInterval;
}
