export function shouldDisableDesktopSceneRestore(state = {}) {
  return Boolean(state.sceneRestorePending);
}

export function buildDesktopSceneRestorePayload() {
  return {
    reload_model: true,
    preserve_vr_state: false,
    randomize_scene_objects: false,
  };
}

export function buildDatasetSceneResetPayload() {
  return {
    reload_model: false,
    preserve_vr_state: true,
    settle_steps: 120,
    randomize_scene_objects: true,
  };
}
