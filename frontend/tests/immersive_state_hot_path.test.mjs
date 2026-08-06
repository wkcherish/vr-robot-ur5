import assert from "node:assert/strict";

import {
  getSceneJointInterpolationAlphaForMode,
  shouldApplyBackendPoseImmediately,
  shouldRunClientPhysicsDiagnostics,
} from "../src/utils/immersiveStateHotPath.js";

assert.equal(
  shouldApplyBackendPoseImmediately({ immediate: false }),
  false,
  "high-rate backend packets should update render targets without forcing immediate joint application"
);

assert.equal(
  shouldApplyBackendPoseImmediately({ immediate: true }),
  true,
  "explicit restore/first-frame paths should still be able to apply immediately"
);

assert.equal(
  shouldRunClientPhysicsDiagnostics({
    strictAuthority: true,
    debugProxiesEnabled: false,
    nowMs: 1000,
    lastRunAtMs: 0,
  }),
  false,
  "production XR hot path should not run client collision diagnostics"
);

assert.equal(
  shouldRunClientPhysicsDiagnostics({
    strictAuthority: true,
    debugProxiesEnabled: true,
    nowMs: 1000,
    lastRunAtMs: 900,
  }),
  false,
  "debug collision diagnostics should be throttled"
);

assert.equal(
  shouldRunClientPhysicsDiagnostics({
    strictAuthority: true,
    debugProxiesEnabled: true,
    nowMs: 1250,
    lastRunAtMs: 1000,
  }),
  true,
  "debug collision diagnostics should run after the throttle interval"
);

assert.equal(
  shouldRunClientPhysicsDiagnostics({
    strictAuthority: false,
    debugProxiesEnabled: true,
    nowMs: 1250,
    lastRunAtMs: 1000,
  }),
  false,
  "non-authoritative rendering mode should not run MuJoCo mirror diagnostics"
);

const xrStrictAlpha = getSceneJointInterpolationAlphaForMode({
  vrModeEntered: true,
  backendPoseSmoothingEnabled: false,
  backendPoseSmoothingAlpha: 0.18,
  vrRenderSmoothingAlpha: 0.16,
  dtSec: 1 / 72,
  errorRad: 0.02,
  lowErrorRad: 0.006,
  highErrorRad: 0.18,
});

assert.equal(
  xrStrictAlpha > 0 && xrStrictAlpha < 1,
  true,
  "strict backend authority should still interpolate displayed XR motion between backend packets"
);

assert.equal(
  getSceneJointInterpolationAlphaForMode({
    vrModeEntered: false,
    backendPoseSmoothingEnabled: false,
    backendPoseSmoothingAlpha: 0.18,
    vrRenderSmoothingAlpha: 0.16,
    dtSec: 1 / 72,
    errorRad: 0.02,
    lowErrorRad: 0.006,
    highErrorRad: 0.18,
  }),
  1,
  "desktop strict authority should keep the current immediate display behavior when smoothing is off"
);
