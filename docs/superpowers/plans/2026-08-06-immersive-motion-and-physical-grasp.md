# Immersive Motion and Physical Grasp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make XR robot motion smooth while enforcing MuJoCo-only physical tool grasping.

**Architecture:** Keep the backend as authority for control and object state. Make the high-rate motion stream lightweight, let the frontend render loop interpolate robot joints, and remove backend grasp-assist attachment for Quest input sources.

**Tech Stack:** Python backend with MuJoCo optional import, Vue/Three frontend, Node regression scripts, Python `unittest`.

## Global Constraints

- Do not change control precision, servo targets, or MuJoCo stepping semantics.
- Do not add frontend-side tool pickup or predictive Quest control in strict backend-authority mode.
- Keep full object state available through reset, HTTP state, and low-rate broadcasts.
- Use tests that fail before implementation and pass after the smallest production changes.

---

### Task 1: Backend Physical Grasp Authority

**Files:**
- Modify: `backend/sim/simulation.py`
- Create: `backend/tests/test_immersive_physics_authority.py`

**Interfaces:**
- Consumes: `SimulationState._source`, `SimulationState._last_input_source`, `_is_realtime_source()`
- Produces: `_allows_grasp_assist_locked() -> bool`

- [ ] **Step 1: Write failing tests**

```python
def test_quest_sources_disable_grasp_assist_attachment_even_when_env_enabled():
    sim = SimulationState()
    sim._source = "quest3_controller"
    sim._last_input_source = "quest3_controller"
    sim._attached_object_id = "wrench_01"
    sim._scene_objects_template = {"wrench_01": {"attached_to_gripper": True}}

    sim._update_grasp_assist_locked(forward=False)

    assert sim._attached_object_id is None
    assert sim._scene_objects_template["wrench_01"]["attached_to_gripper"] is False
```

- [ ] **Step 2: Verify failure**

Run: `SIM_GRASP_ASSIST_MODE=assist python3 -m unittest backend.tests.test_immersive_physics_authority -v`

Expected: FAIL because Quest sources still allow an existing grasp attachment to persist.

- [ ] **Step 3: Implement minimal backend rule**

Add `_allows_grasp_assist_locked()` and call it at the start of `_update_grasp_assist_locked()` so Quest controller/hand sources always clear the attachment path.

- [ ] **Step 4: Verify pass**

Run: `SIM_GRASP_ASSIST_MODE=assist python3 -m unittest backend.tests.test_immersive_physics_authority -v`

Expected: PASS.

### Task 2: Lightweight Motion Broadcast

**Files:**
- Modify: `backend/sim/simulation.py`
- Modify: `backend/tests/test_immersive_physics_authority.py`

**Interfaces:**
- Consumes: `_build_motion_state_locked()`
- Produces: motion payloads without `objects`, with `objects_revision` for future diagnostics.

- [ ] **Step 1: Write failing test**

```python
def test_motion_state_omits_full_object_payload_from_high_rate_stream():
    sim = SimulationState()
    sim._objects_state = {"wrench_01": {"position": [1, 2, 3], "quaternion": [1, 0, 0, 0]}}

    state = sim._build_motion_state_locked()

    assert "objects" not in state
```

- [ ] **Step 2: Verify failure**

Run: `python3 -m unittest backend.tests.test_immersive_physics_authority -v`

Expected: FAIL because the high-rate payload still includes `objects`.

- [ ] **Step 3: Implement minimal backend change**

Remove the `objects` field from `_build_motion_state_locked()` and keep full object payloads in `_build_state_locked()` and `_build_broadcast_state_locked()`.

- [ ] **Step 4: Verify pass**

Run: `python3 -m unittest backend.tests.test_immersive_physics_authority -v`

Expected: PASS.

### Task 3: Frontend Render-Loop Smoothing

**Files:**
- Modify: `frontend/src/App.vue`
- Create: `frontend/tests/immersive_state_hot_path.test.mjs`

**Interfaces:**
- Consumes: `applyBackendStateToScene(state, options)` and state handlers
- Produces: strict-authority packets update render targets without per-packet immediate robot joint application except first/restore frames.

- [ ] **Step 1: Write failing regression script**

The script reads `App.vue` and verifies the strict-authority immediate branch is gone from `applyBackendStateToScene`, and that `applySceneObjectsFromBackendState` does not call diagnostics unconditionally.

- [ ] **Step 2: Verify failure**

Run: `node frontend/tests/immersive_state_hot_path.test.mjs`

Expected: FAIL against the current hot path.

- [ ] **Step 3: Implement minimal frontend change**

Only apply robot pose immediately when `options.immediate === true`; skip object work when state lacks `objects`; run diagnostics only when debug proxies are enabled and throttled.

- [ ] **Step 4: Verify pass**

Run: `node frontend/tests/immersive_state_hot_path.test.mjs`

Expected: PASS.

### Task 4: Full Verification

**Files:**
- Verify: backend and frontend project files

- [ ] **Step 1: Run backend tests**

Run: `SIM_GRASP_ASSIST_MODE=assist python3 -m unittest backend.tests.test_immersive_physics_authority -v`

- [ ] **Step 2: Run frontend regression script**

Run: `node frontend/tests/immersive_state_hot_path.test.mjs`

- [ ] **Step 3: Compile backend**

Run: `python3 -m compileall -q backend`

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
