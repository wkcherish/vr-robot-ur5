# Immersive Motion and Physical Grasp Design

## Goal

Keep the existing UR5 control precision while making immersive XR motion visually smooth, and ensure tools are only lifted by MuJoCo physical contact instead of any frontend or backend grasp assist.

## Root Cause

The backend `motion_broadcast` hot path currently includes a deep copy of all scene objects on every high-rate motion state. The frontend consumes those packets by immediately applying robot joints and all object poses, then runs collision-proxy diagnostics. In strict backend-authority mode this bypasses the render-loop smoothing path, so network packet cadence becomes visible XR motion cadence.

The early tool pickup behavior is caused by backend grasp assist. When enabled by environment configuration, it can bind a tool to the gripper after near-contact or partial pad contact, then rewrite the object pose to follow the gripper. Immersive control must not use that assist path.

## Selected Approach

Use backend physics as the only authority, but make high-rate state delivery lightweight and display-friendly.

- High-rate `motion_broadcast` carries robot motion and safety state only. Full object poses stay in lower-rate/full state paths where they belong.
- The frontend updates backend render targets from packets, then lets the render loop interpolate toward them. First frames and explicit restores may still apply immediately.
- Scene object pose updates run only when packets actually include `objects`.
- Client collision-proxy diagnostics are debug-only and throttled outside the hot packet path.
- Backend grasp assist is explicitly disabled for `quest3_controller` and `quest3_hand` sources, even if `SIM_GRASP_ASSIST_MODE` is enabled.

## Requirements

- Do not change the control command math or MuJoCo physics stepping precision.
- Do not add frontend prediction for Quest control in strict backend-authority mode.
- Do not attach or move tools from the frontend.
- Preserve full state compatibility for reset, HTTP fallback, and low-rate broadcasts.
- Add regression coverage for immersive-source grasp assist suppression and lightweight motion-state payloads.

## Verification

- Backend regression tests prove Quest sources suppress attachment and motion payloads omit object poses.
- Frontend regression script proves strict backend authority no longer forces immediate apply on every state packet.
- Existing build and compile checks continue to pass.
