from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import mujoco
import mujoco.viewer


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "backend" / "mujoco_models" / "environment.xml"
DEFAULT_MANIFEST = REPO_ROOT / "shared" / "scene_manifest.json"
GRIPPER_DRIVER_LIMIT = 0.87
GRIPPER_JOINT_NAMES = [
    "left_driver_joint",
    "right_driver_joint",
    "left_spring_link_joint",
    "right_spring_link_joint",
    "left_follower_joint",
    "right_follower_joint",
]
DEFAULT_ARM_JOINT_NAMES = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]
DEFAULT_ARM_ACTUATOR_NAMES = [
    "act_shoulder_pan",
    "act_shoulder_lift",
    "act_elbow",
    "act_wrist_1",
    "act_wrist_2",
    "act_wrist_3",
]
DEFAULT_GRIPPER_ACTUATOR_NAME = "act_gripper_driver"
VIEWER_BRIDGE_EDIT_THRESHOLD_RAD = 0.02
VIEWER_BRIDGE_MATCH_THRESHOLD_RAD = 0.06
VIEWER_BRIDGE_GUARD_S = 0.35
VIEWER_BRIDGE_MIN_PUSH_INTERVAL_S = 0.08
VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD = 0.003
VIEWER_BRIDGE_PENDING_TIMEOUT_S = 2.0


def _resolve_path(raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def _read_home_pose(manifest_path: Path) -> tuple[list[str], list[float]]:
    if not manifest_path.exists():
        return [], []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    home = manifest.get("robot", {}).get("home_pose", {})
    names = [str(x) for x in home.get("joint_order", [])]
    qpos = [float(x) for x in home.get("qpos_arm", [])]
    return names, qpos


def _apply_home_pose(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    joint_names: list[str],
    arm_qpos: list[float],
) -> None:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0

    for idx, name in enumerate(joint_names):
        if idx >= len(arm_qpos):
            break
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_addr] = arm_qpos[idx]

    # Keep gripper in fully open baseline.
    driver = 0.0 * GRIPPER_DRIVER_LIMIT
    gripper_values = {
        "left_driver_joint": driver,
        "right_driver_joint": driver,
        "left_spring_link_joint": driver,
        "right_spring_link_joint": driver,
        "left_follower_joint": driver,
        "right_follower_joint": driver,
    }
    for name in GRIPPER_JOINT_NAMES:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_addr] = gripper_values[name]

    mujoco.mj_forward(model, data)


def _extract_gripper_joint_targets(state: dict[str, object]) -> dict[str, float]:
    gripper_values: dict[str, float] = {}
    driver_from_state: float | None = None
    gripper_joints = state.get("gripper_joints")
    if isinstance(gripper_joints, dict):
        for joint_name in GRIPPER_JOINT_NAMES:
            raw_value = gripper_joints.get(joint_name)
            if raw_value is None:
                continue
            try:
                gripper_values[joint_name] = float(raw_value)
            except (TypeError, ValueError):
                continue
        if len(gripper_values) == len(GRIPPER_JOINT_NAMES):
            return gripper_values
        raw_driver = gripper_joints.get("left_driver_joint")
        try:
            if raw_driver is not None:
                driver_from_state = max(0.0, min(float(raw_driver), GRIPPER_DRIVER_LIMIT))
        except (TypeError, ValueError):
            driver_from_state = None

    if driver_from_state is None:
        qpos = state.get("qpos")
        if not isinstance(qpos, list) or len(qpos) < len(DEFAULT_ARM_JOINT_NAMES) + 1:
            return gripper_values
        try:
            driver_from_state = max(0.0, min(float(qpos[len(DEFAULT_ARM_JOINT_NAMES)]), GRIPPER_DRIVER_LIMIT))
        except (TypeError, ValueError):
            return gripper_values

    driver = driver_from_state
    return {
        "left_driver_joint": driver,
        "right_driver_joint": driver,
        "left_spring_link_joint": driver,
        "right_spring_link_joint": driver,
        "left_follower_joint": driver,
        "right_follower_joint": driver,
    }


def _apply_backend_state_to_viewer(model: mujoco.MjModel, data: mujoco.MjData, state: dict[str, object]) -> bool:
    qpos = state.get("qpos")
    if not isinstance(qpos, list) or len(qpos) < len(DEFAULT_ARM_JOINT_NAMES):
        return False

    joint_names_raw = state.get("joint_names")
    if isinstance(joint_names_raw, list) and joint_names_raw:
        joint_names = [str(name) for name in joint_names_raw]
    else:
        joint_names = list(DEFAULT_ARM_JOINT_NAMES)

    arm_joint_count = min(len(joint_names), len(DEFAULT_ARM_JOINT_NAMES), len(qpos))
    applied_arm_qpos: list[float | None] = [None for _ in range(len(DEFAULT_ARM_JOINT_NAMES))]
    for idx in range(arm_joint_count):
        joint_name = joint_names[idx]
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        try:
            qpos_value = float(qpos[idx])
            data.qpos[qpos_addr] = qpos_value
            applied_arm_qpos[idx] = qpos_value
        except (TypeError, ValueError):
            continue

    gripper_targets = _extract_gripper_joint_targets(state)
    applied_driver: float | None = None
    for joint_name, joint_target in gripper_targets.items():
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_addr] = float(joint_target)
        if joint_name == "left_driver_joint":
            applied_driver = float(joint_target)

    if data.ctrl is not None and len(data.ctrl) > 0:
        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            if idx >= len(applied_arm_qpos):
                break
            target_value = applied_arm_qpos[idx]
            if target_value is None:
                continue
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id < 0:
                continue
            data.ctrl[int(actuator_id)] = float(target_value)
        if applied_driver is not None:
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
            if actuator_id >= 0:
                data.ctrl[int(actuator_id)] = float(applied_driver)

    # Keep tabletop objects in viewer aligned with backend state (toolbox/tools/camera assets).
    objects_raw = state.get("objects")
    if isinstance(objects_raw, dict):
        for object_name, object_state in objects_raw.items():
            if not isinstance(object_name, str) or not object_name:
                continue
            if not isinstance(object_state, dict):
                continue

            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, object_name)
            if body_id < 0:
                continue

            position = object_state.get("position")
            if isinstance(position, list) and len(position) >= 3:
                try:
                    model.body_pos[int(body_id)] = [float(position[0]), float(position[1]), float(position[2])]
                except (TypeError, ValueError):
                    pass

            quaternion = object_state.get("quaternion")
            if isinstance(quaternion, list) and len(quaternion) >= 4:
                try:
                    model.body_quat[int(body_id)] = [
                        float(quaternion[0]),
                        float(quaternion[1]),
                        float(quaternion[2]),
                        float(quaternion[3]),
                    ]
                except (TypeError, ValueError):
                    pass

    mujoco.mj_forward(model, data)
    return True


def _apply_pose_to_viewer(model: mujoco.MjModel, data: mujoco.MjData, pose: dict[str, object]) -> bool:
    arm_raw = pose.get("arm")
    if not isinstance(arm_raw, list) or len(arm_raw) < len(DEFAULT_ARM_JOINT_NAMES):
        return False

    arm_values: list[float | None] = [None for _ in range(len(DEFAULT_ARM_JOINT_NAMES))]
    for idx, joint_name in enumerate(DEFAULT_ARM_JOINT_NAMES):
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        try:
            qpos_value = float(arm_raw[idx])
        except (TypeError, ValueError):
            continue
        data.qpos[qpos_addr] = qpos_value
        arm_values[idx] = qpos_value

    driver_value: float | None = None
    driver_raw = pose.get("driver")
    if driver_raw is not None:
        try:
            driver_value = max(0.0, min(float(driver_raw), GRIPPER_DRIVER_LIMIT))
        except (TypeError, ValueError):
            driver_value = None

    if driver_value is not None:
        gripper_targets = {
            "left_driver_joint": driver_value,
            "right_driver_joint": driver_value,
            "left_spring_link_joint": driver_value,
            "right_spring_link_joint": driver_value,
            "left_follower_joint": driver_value,
            "right_follower_joint": driver_value,
        }
        for joint_name, joint_target in gripper_targets.items():
            joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
            if joint_id < 0:
                continue
            qpos_addr = int(model.jnt_qposadr[joint_id])
            data.qpos[qpos_addr] = float(joint_target)

    if data.ctrl is not None and len(data.ctrl) > 0:
        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            target_value = arm_values[idx]
            if target_value is None:
                continue
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id < 0:
                continue
            data.ctrl[int(actuator_id)] = float(target_value)
        if driver_value is not None:
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
            if actuator_id >= 0:
                data.ctrl[int(actuator_id)] = float(driver_value)

    mujoco.mj_forward(model, data)
    return True


def _fetch_backend_state(state_url: str, timeout_s: float) -> dict[str, object] | None:
    query_separator = "&" if "?" in state_url else "?"
    state_url = f"{state_url}{query_separator}refresh_camera=false"
    try:
        with urlopen(state_url, timeout=timeout_s) as resp:
            if not (200 <= int(resp.status) < 300):
                return None
            payload = json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _extract_pose_from_backend_state(state: dict[str, object]) -> dict[str, object] | None:
    qpos = state.get("qpos")
    if not isinstance(qpos, list) or len(qpos) < len(DEFAULT_ARM_JOINT_NAMES):
        return None

    try:
        arm = [float(qpos[idx]) for idx in range(len(DEFAULT_ARM_JOINT_NAMES))]
    except (TypeError, ValueError):
        return None

    driver: float | None = None
    gripper_joints = state.get("gripper_joints")
    if isinstance(gripper_joints, dict):
        raw_driver = gripper_joints.get("left_driver_joint")
        try:
            if raw_driver is not None:
                driver = float(raw_driver)
        except (TypeError, ValueError):
            driver = None

    if driver is None and len(qpos) > len(DEFAULT_ARM_JOINT_NAMES):
        try:
            driver = float(qpos[len(DEFAULT_ARM_JOINT_NAMES)])
        except (TypeError, ValueError):
            driver = None

    return {"arm": arm, "driver": driver}


def _capture_viewer_pose(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, object] | None:
    arm: list[float] = []
    for joint_name in DEFAULT_ARM_JOINT_NAMES:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            return None
        qpos_addr = int(model.jnt_qposadr[joint_id])
        arm.append(float(data.qpos[qpos_addr]))

    driver: float | None = None
    driver_joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "left_driver_joint")
    if driver_joint_id >= 0:
        qpos_addr = int(model.jnt_qposadr[driver_joint_id])
        driver = float(data.qpos[qpos_addr])

    return {"arm": arm, "driver": driver}


def _resolve_actuator_ids(model: mujoco.MjModel) -> tuple[list[int | None], int | None]:
    arm_ids: list[int | None] = []
    for actuator_name in DEFAULT_ARM_ACTUATOR_NAMES:
        actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
        arm_ids.append(int(actuator_id) if actuator_id >= 0 else None)
    gripper_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
    return arm_ids, (int(gripper_id) if gripper_id >= 0 else None)


def _capture_viewer_target_pose_from_ctrl(
    data: mujoco.MjData,
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
) -> dict[str, object] | None:
    if data.ctrl is None:
        return None
    if len(arm_actuator_ids) < len(DEFAULT_ARM_JOINT_NAMES):
        return None

    arm: list[float] = []
    for actuator_id in arm_actuator_ids[: len(DEFAULT_ARM_JOINT_NAMES)]:
        if actuator_id is None:
            return None
        arm.append(float(data.ctrl[actuator_id]))

    driver: float | None = None
    if gripper_actuator_id is not None:
        driver = float(data.ctrl[gripper_actuator_id])

    return {"arm": arm, "driver": driver}


def _extract_ctrl_vector(
    data: mujoco.MjData,
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
) -> list[float]:
    if data.ctrl is None:
        return []

    values: list[float] = []
    for actuator_id in arm_actuator_ids[: len(DEFAULT_ARM_JOINT_NAMES)]:
        if actuator_id is None:
            values.append(float("nan"))
        else:
            values.append(float(data.ctrl[actuator_id]))

    if gripper_actuator_id is None:
        values.append(float("nan"))
    else:
        values.append(float(data.ctrl[gripper_actuator_id]))

    return values


def _ctrl_changed(current: list[float], previous: list[float], threshold: float) -> bool:
    if not current or not previous:
        return False
    if len(current) != len(previous):
        return True

    for idx in range(len(current)):
        cur = current[idx]
        prev = previous[idx]
        if not (isinstance(cur, float) and isinstance(prev, float)):
            return True
        if cur != cur or prev != prev:  # NaN check
            continue
        if abs(cur - prev) > threshold:
            return True
    return False


def _pose_max_error(pose_a: dict[str, object], pose_b: dict[str, object]) -> float:
    arm_a_raw = pose_a.get("arm")
    arm_b_raw = pose_b.get("arm")
    if not isinstance(arm_a_raw, list) or not isinstance(arm_b_raw, list):
        return float("inf")
    if len(arm_a_raw) < len(DEFAULT_ARM_JOINT_NAMES) or len(arm_b_raw) < len(DEFAULT_ARM_JOINT_NAMES):
        return float("inf")

    max_err = 0.0
    for idx in range(len(DEFAULT_ARM_JOINT_NAMES)):
        try:
            err = abs(float(arm_a_raw[idx]) - float(arm_b_raw[idx]))
        except (TypeError, ValueError):
            return float("inf")
        if err > max_err:
            max_err = err

    driver_a_raw = pose_a.get("driver")
    driver_b_raw = pose_b.get("driver")
    if driver_a_raw is not None and driver_b_raw is not None:
        try:
            driver_err = abs(float(driver_a_raw) - float(driver_b_raw))
        except (TypeError, ValueError):
            return float("inf")
        if driver_err > max_err:
            max_err = driver_err

    return max_err


def _push_viewer_pose_to_backend(step_url: str, pose: dict[str, object], timeout_s: float) -> bool:
    arm_raw = pose.get("arm")
    if not isinstance(arm_raw, list) or len(arm_raw) < len(DEFAULT_ARM_JOINT_NAMES):
        return False

    try:
        arm = [float(arm_raw[idx]) for idx in range(len(DEFAULT_ARM_JOINT_NAMES))]
    except (TypeError, ValueError):
        return False

    payload: dict[str, object] = {
        "target_positions": arm,
        "n_steps": 12,
        "control_mode": "position",
        "source": "manual",
    }

    driver_raw = pose.get("driver")
    if driver_raw is not None:
        try:
            driver = max(0.0, min(float(driver_raw), GRIPPER_DRIVER_LIMIT))
        except (TypeError, ValueError):
            driver = None
        if driver is not None:
            payload["gripper_command"] = {
                "mode": "open_close",
                "value": max(0.0, min(driver / GRIPPER_DRIVER_LIMIT, 1.0)),
            }

    try:
        request = Request(
            step_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_s) as resp:
            return 200 <= int(resp.status) < 300
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def run_viewer(model_path: Path, manifest_path: Path, fps: float, state_url: str, step_url: str) -> None:
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)

    names, qpos = _read_home_pose(manifest_path)
    _apply_home_pose(model, data, names, qpos)

    dt = max(1e-4, 1.0 / max(1.0, fps))
    state_poll_interval = max(0.005, 1.0 / min(max(fps, 1.0), 60.0))
    state_fetch_timeout = min(0.5, dt)
    last_poll_at = 0.0
    last_state: dict[str, object] | None = None
    arm_actuator_ids, gripper_actuator_id = _resolve_actuator_ids(model)
    last_applied_backend_pose: dict[str, object] | None = _capture_viewer_pose(model, data)
    last_ctrl_snapshot = _extract_ctrl_vector(data, arm_actuator_ids, gripper_actuator_id)
    pending_viewer_push: dict[str, object] | None = None
    last_manual_push_at = 0.0
    local_override_until = 0.0
    poll_failures = 0

    print(f"[viewer] loading: {model_path}")
    print(f"[viewer] syncing state from: {state_url}")
    print(f"[viewer] forwarding local edits to: {step_url}")
    print("[viewer] controls: left-drag rotate, right-drag pan, wheel zoom")
    print("[viewer] close the window to return to backend console")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            start = time.perf_counter()
            current_pose = _capture_viewer_pose(model, data)
            ctrl_target_pose = _capture_viewer_target_pose_from_ctrl(data, arm_actuator_ids, gripper_actuator_id)
            current_ctrl_snapshot = _extract_ctrl_vector(data, arm_actuator_ids, gripper_actuator_id)
            ctrl_changed = _ctrl_changed(
                current=current_ctrl_snapshot,
                previous=last_ctrl_snapshot,
                threshold=VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD,
            )

            edit_pose: dict[str, object] | None = None
            if current_pose is not None and last_applied_backend_pose is not None:
                local_edit_error = _pose_max_error(current_pose, last_applied_backend_pose)
                if local_edit_error > VIEWER_BRIDGE_EDIT_THRESHOLD_RAD:
                    edit_pose = current_pose

            if (
                ctrl_changed
                and ctrl_target_pose is not None
                and last_applied_backend_pose is not None
                and _pose_max_error(ctrl_target_pose, last_applied_backend_pose) > VIEWER_BRIDGE_EDIT_THRESHOLD_RAD
            ):
                # Prefer ctrl-target pose when user drags the MuJoCo Control panel sliders.
                edit_pose = ctrl_target_pose

            if edit_pose is not None:
                # Make local slider interaction effective immediately in viewer, then bridge to backend.
                _apply_pose_to_viewer(model, data, edit_pose)
                local_override_until = max(local_override_until, start + VIEWER_BRIDGE_GUARD_S)

                replace_pending = True
                if pending_viewer_push is not None:
                    pending_pose_raw = pending_viewer_push.get("pose")
                    if isinstance(pending_pose_raw, dict):
                        delta_to_pending = _pose_max_error(edit_pose, pending_pose_raw)
                        replace_pending = delta_to_pending > VIEWER_BRIDGE_EDIT_THRESHOLD_RAD
                if replace_pending:
                    pending_viewer_push = {
                        "pose": edit_pose,
                        "created_at": start,
                        "last_attempt_at": 0.0,
                    }

            if pending_viewer_push is not None:
                last_attempt_at_raw = pending_viewer_push.get("last_attempt_at", 0.0)
                last_attempt_at = float(last_attempt_at_raw) if isinstance(last_attempt_at_raw, (int, float)) else 0.0
                if (start - last_attempt_at) >= VIEWER_BRIDGE_MIN_PUSH_INTERVAL_S:
                    pending_pose_raw = pending_viewer_push.get("pose")
                    if isinstance(pending_pose_raw, dict):
                        pushed = _push_viewer_pose_to_backend(
                            step_url=step_url,
                            pose=pending_pose_raw,
                            timeout_s=min(0.45, max(0.2, 2.0 * dt)),
                        )
                        pending_viewer_push["last_attempt_at"] = start
                        if pushed:
                            pending_viewer_push["sent_at"] = start
                            last_manual_push_at = start

            if (start - last_poll_at) >= state_poll_interval:
                fetched = _fetch_backend_state(state_url=state_url, timeout_s=state_fetch_timeout)
                last_poll_at = start
                if fetched is not None:
                    last_state = fetched
                    if poll_failures > 0:
                        print("[viewer] backend state stream recovered.")
                    poll_failures = 0
                else:
                    poll_failures += 1
                    if poll_failures in {1, 60, 300}:
                        print("[viewer] warning: failed to fetch backend state, keeping last rendered pose.")

            should_apply_backend = True
            if pending_viewer_push is not None and last_state is not None:
                pending_pose_raw = pending_viewer_push.get("pose")
                created_at_raw = pending_viewer_push.get("created_at", start)
                created_at = float(created_at_raw) if isinstance(created_at_raw, (int, float)) else start
                backend_pose = _extract_pose_from_backend_state(last_state)
                if isinstance(pending_pose_raw, dict) and backend_pose is not None:
                    backend_err = _pose_max_error(backend_pose, pending_pose_raw)
                    if backend_err <= VIEWER_BRIDGE_MATCH_THRESHOLD_RAD:
                        pending_viewer_push = None
                    elif (start < local_override_until) or ((start - created_at) < VIEWER_BRIDGE_PENDING_TIMEOUT_S):
                        # Keep local interaction visible while backend catches up.
                        should_apply_backend = False
                    else:
                        pending_viewer_push = None
                else:
                    pending_viewer_push = None
            elif start < local_override_until:
                should_apply_backend = False

            if last_state is not None:
                if should_apply_backend:
                    applied = _apply_backend_state_to_viewer(model, data, last_state)
                    if applied:
                        backend_pose = _extract_pose_from_backend_state(last_state)
                        if backend_pose is not None:
                            last_applied_backend_pose = backend_pose
                else:
                    mujoco.mj_forward(model, data)
            else:
                mujoco.mj_forward(model, data)

            viewer.sync()
            # Keep the pre-sync ctrl snapshot as baseline so UI edits applied during
            # viewer.sync() are detected on the next loop instead of being swallowed.
            last_ctrl_snapshot = list(current_ctrl_snapshot)
            sleep_time = dt - (time.perf_counter() - start)
            if sleep_time > 0:
                time.sleep(sleep_time)


def _start_backend(
    host: str,
    port: int,
    reload_enabled: bool,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api_app:app",
        "--app-dir",
        "..",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload_enabled:
        cmd.append("--reload")
    if ssl_certfile:
        cmd.extend(["--ssl-certfile", ssl_certfile])
    if ssl_keyfile:
        cmd.extend(["--ssl-keyfile", ssl_keyfile])

    backend_cwd = REPO_ROOT / "backend"
    print("[backend] starting:", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=str(backend_cwd))


def _health_check_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _wait_backend_ready(process: subprocess.Popen[bytes], host: str, port: int, timeout_s: float) -> None:
    check_host = _health_check_host(host)
    process_args = [str(arg) for arg in (process.args or [])]
    has_ssl = "--ssl-certfile" in process_args and "--ssl-keyfile" in process_args
    health_scheme = "https" if has_ssl else "http"
    health_url = f"{health_scheme}://{check_host}:{port}/health/"
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend exited early with code {process.returncode}.")
        try:
            with urlopen(health_url, timeout=1.0) as resp:
                if 200 <= int(resp.status) < 300:
                    print(f"[backend] ready: {health_url}")
                    return
        except URLError:
            pass
        time.sleep(0.4)

    raise TimeoutError(f"Backend health check timed out after {timeout_s:.1f}s: {health_url}")


def _ask_yes_no(prompt: str) -> bool:
    raw = input(prompt).strip().lower()
    return raw == "yes"


def _stop_backend(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start FastAPI backend and optionally open MuJoCo desktop viewer."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to MuJoCo XML model. Default: backend/mujoco_models/environment.xml",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to scene manifest. Default: shared/scene_manifest.json",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=60.0,
        help="Viewer stepping FPS (default: 60).",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Backend host (default: 0.0.0.0).")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000).")
    parser.add_argument(
        "--ssl-certfile",
        type=str,
        default=None,
        help="SSL certificate file path (PEM). Provide with --ssl-keyfile to enable HTTPS/WSS.",
    )
    parser.add_argument(
        "--ssl-keyfile",
        type=str,
        default=None,
        help="SSL private key file path (PEM). Provide with --ssl-certfile to enable HTTPS/WSS.",
    )
    parser.add_argument(
        "--backend-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for backend /health/ ready (default: 30).",
    )
    parser.add_argument(
        "--open-viewer",
        choices=["ask", "yes", "no"],
        default="ask",
        help="Open MuJoCo viewer after backend starts: ask|yes|no (default: ask).",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable uvicorn --reload (enabled by default to match current dev command).",
    )
    args = parser.parse_args()

    model_path = _resolve_path(args.model, DEFAULT_MODEL)
    manifest_path = _resolve_path(args.manifest, DEFAULT_MANIFEST)

    backend_process: subprocess.Popen[bytes] | None = None
    try:
        backend_process = _start_backend(
            host=args.host,
            port=args.port,
            reload_enabled=not args.no_reload,
            ssl_certfile=args.ssl_certfile,
            ssl_keyfile=args.ssl_keyfile,
        )
        _wait_backend_ready(
            process=backend_process,
            host=args.host,
            port=args.port,
            timeout_s=max(3.0, args.backend_timeout),
        )

        if args.open_viewer == "yes":
            should_open_viewer = True
        elif args.open_viewer == "no":
            should_open_viewer = False
        else:
            should_open_viewer = _ask_yes_no(
                "是否加载 MuJoCo 仿真环境? 输入 yes 才加载，其他输入均不加载: ",
            )

        if should_open_viewer:
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            check_host = _health_check_host(args.host)
            scheme = "https" if args.ssl_certfile and args.ssl_keyfile else "http"
            state_url = f"{scheme}://{check_host}:{args.port}/sim/state/"
            step_url = f"{scheme}://{check_host}:{args.port}/sim/step/"
            run_viewer(
                model_path=model_path,
                manifest_path=manifest_path,
                fps=args.fps,
                state_url=state_url,
                step_url=step_url,
            )

        print("[backend] running. Press Ctrl+C to stop backend.")
        while backend_process.poll() is None:
            time.sleep(0.8)

        raise RuntimeError(f"Backend exited unexpectedly with code {backend_process.returncode}.")
    except KeyboardInterrupt:
        print("\n[launcher] stopping backend...")
    finally:
        _stop_backend(backend_process)


if __name__ == "__main__":
    main()
