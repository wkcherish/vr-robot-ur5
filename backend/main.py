from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.error import URLError
from urllib.request import Request, urlopen

import mujoco
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "backend" / "mujoco_models" / "environment.xml"
DEFAULT_MANIFEST = REPO_ROOT / "shared" / "scene_manifest.json"
BACKEND_RUNTIME_DIR = REPO_ROOT / "shared" / "runtime"
BACKEND_RUNTIME_PATH = BACKEND_RUNTIME_DIR / "backend-dev.json"
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
DEFAULT_VIEWER_CAMERA_OVERLAY = None
DEFAULT_CAMERA_PREVIEW_FPS = 15.0
DEFAULT_VIEWER_FPS = 30.0
DEFAULT_VIEWER_LOCAL_PHYSICS_SUBSTEPS = 2
VIEWER_FREE_CAMERA_NAMES = {"", "free", "none", "off"}
VIEWER_CAMERA_OVERLAY_ASPECT = 4.0 / 3.0
VIEWER_CAMERA_OVERLAY_FRACTION = 0.45
VIEWER_CAMERA_OVERLAY_MARGIN_PX = 16
VIEWER_CAMERA_OVERLAY_MIN_WIDTH_PX = 220
VIEWER_CAMERA_OVERLAY_MAX_WIDTH_PX = 520
VIEWER_CAMERA_OVERLAY_FPS = 12.0
VIEWER_BRIDGE_EDIT_THRESHOLD_RAD = 0.02
VIEWER_BRIDGE_MATCH_THRESHOLD_RAD = 0.06
VIEWER_BRIDGE_GUARD_S = 0.35
VIEWER_BRIDGE_MIN_PUSH_INTERVAL_S = 0.10
VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD = 0.003
VIEWER_BRIDGE_PENDING_TIMEOUT_S = 8.0
VIEWER_BRIDGE_CTRL_IDLE_S = 0.45
VIEWER_BRIDGE_REMOTE_CONTROL_GUARD_S = 2.0
VIEWER_BRIDGE_PUSH_PHYSICS_STEPS = 24
VIEWER_BRIDGE_PUSH_TIMEOUT_S = 0.08
VIEWER_BRIDGE_PENDING_POLL_INTERVAL_S = 0.12
VIEWER_BACKEND_HARD_SYNC_THRESHOLD_RAD = 0.12
VIEWER_CTRL_ARM_MAX_SPEED_RAD_S = 2.8
VIEWER_CTRL_ARM_MAX_ACCEL_RAD_S2 = 80.0
VIEWER_CTRL_GRIPPER_MAX_SPEED_DRIVER_S = 1.8
VIEWER_CTRL_GRIPPER_MAX_ACCEL_DRIVER_S2 = 30.0
MAX_VIEWER_LOCAL_PHYSICS_SUBSTEPS = 64
SCENE_SETTLE_STEPS = 1000
# Keep viewer state polling tolerant to transient backend jitter.
MIN_STATE_FETCH_TIMEOUT_S = 0.10
MAX_STATE_FETCH_TIMEOUT_S = 1.00


def _resolve_bind_target(host: str, port: int) -> tuple[int, tuple[object, ...]]:
    if host in {"", "0.0.0.0"}:
        return socket.AF_INET, ("0.0.0.0", int(port))
    if host == "::":
        return socket.AF_INET6, ("::", int(port), 0, 0)

    try:
        addrinfo = socket.getaddrinfo(
            host,
            int(port),
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve backend host {host!r}: {exc}") from exc

    if not addrinfo:
        raise ValueError(f"Unable to resolve backend host {host!r}.")

    family, socktype, proto, _, sockaddr = addrinfo[0]
    if socktype != socket.SOCK_STREAM or proto != socket.IPPROTO_TCP:
        raise ValueError(f"Unsupported backend bind target for host {host!r}.")
    return family, tuple(sockaddr)


def _is_port_available(host: str, port: int) -> bool:
    try:
        family, sockaddr = _resolve_bind_target(host, port)
    except ValueError:
        return False

    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(sockaddr)
        except OSError:
            return False
    return True


def _allocate_ephemeral_port(host: str) -> int:
    family, sockaddr = _resolve_bind_target(host, 0)
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(sockaddr)
        bound = sock.getsockname()
    return int(bound[1])


def _select_backend_port(host: str, requested_port: int, search_window: int = 32) -> tuple[int, bool]:
    if not 1 <= int(requested_port) <= 65535:
        raise ValueError(f"Backend port must be between 1 and 65535, got {requested_port}.")

    preferred_port = int(requested_port)
    if _is_port_available(host, preferred_port):
        return preferred_port, False

    upper_bound = min(65535, preferred_port + max(1, int(search_window)))
    for candidate_port in range(preferred_port + 1, upper_bound + 1):
        if _is_port_available(host, candidate_port):
            return candidate_port, True

    return _allocate_ephemeral_port(host), True


def _write_backend_runtime_file(
    host: str,
    port: int,
    requested_port: int,
    ssl_enabled: bool,
) -> None:
    scheme = "https" if ssl_enabled else "http"
    proxy_host = _health_check_host(host)
    payload = {
        "listen_host": host,
        "port": int(port),
        "requested_port": int(requested_port),
        "scheme": scheme,
        "proxy_target": f"{scheme}://{proxy_host}:{int(port)}",
        "health_url": f"{scheme}://{proxy_host}:{int(port)}/health/",
        "sim_ws_url": f"{'wss' if ssl_enabled else 'ws'}://{proxy_host}:{int(port)}/sim/ws",
        "updated_at": time.time(),
    }
    BACKEND_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    BACKEND_RUNTIME_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_path(raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def _is_running_under_mjpython() -> bool:
    if sys.platform != "darwin":
        return True
    try:
        import mujoco.viewer as mujoco_viewer
    except Exception:
        return False

    mjpython_base = getattr(mujoco_viewer, "_MjPythonBase", None)
    if mjpython_base is None:
        return False
    return isinstance(getattr(mujoco_viewer, "_MJPYTHON", None), mjpython_base)


def _find_mjpython() -> Path | None:
    candidates: list[Path] = []

    executable = Path(sys.executable).expanduser()
    candidates.append(executable.with_name("mjpython"))

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix).expanduser() / "bin" / "mjpython")

    candidates.append(Path(sys.prefix).expanduser() / "bin" / "mjpython")

    path_mjpython = shutil.which("mjpython")
    if path_mjpython:
        candidates.append(Path(path_mjpython).expanduser())

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return resolved
    return None


def _argv_with_open_viewer(choice: str) -> list[str]:
    argv = list(sys.argv[1:])
    for idx, value in enumerate(argv):
        if value == "--open-viewer":
            if idx + 1 < len(argv):
                return argv[: idx + 1] + [choice] + argv[idx + 2 :]
            return argv + [choice]
        if value.startswith("--open-viewer="):
            argv[idx] = f"--open-viewer={choice}"
            return argv
    return [*argv, "--open-viewer", choice]


def _restart_with_mjpython_if_needed(open_viewer: bool, argv: list[str] | None = None) -> None:
    if not open_viewer or sys.platform != "darwin" or _is_running_under_mjpython():
        return

    mjpython = _find_mjpython()
    if mjpython is None:
        raise RuntimeError(
            "MuJoCo viewer on macOS requires `mjpython`, but it was not found for "
            f"the active Python environment: {sys.executable}. Activate the Conda "
            "environment and run `mjpython ./main.py --open-viewer yes`."
        )

    script_path = Path(__file__).resolve()
    next_argv = argv if argv is not None else sys.argv[1:]
    cmd = [str(mjpython), str(script_path), *next_argv]
    print("[launcher] macOS MuJoCo viewer requires mjpython; restarting with:", " ".join(cmd), flush=True)
    os.execv(str(mjpython), cmd)


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

    if data.ctrl is not None and len(data.ctrl) > 0:
        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            if idx >= len(joint_names) or idx >= len(arm_qpos):
                break
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id < 0:
                continue
            _set_actuator_ctrl_for_joint_target(
                model=model,
                data=data,
                actuator_id=int(actuator_id),
                joint_name=joint_names[idx],
                target_qpos=float(arm_qpos[idx]),
            )
            _sync_actuator_activation(model, data, int(actuator_id), float(arm_qpos[idx]))
        gripper_actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
        if gripper_actuator_id >= 0:
            _set_actuator_ctrl_for_joint_target(
                model=model,
                data=data,
                actuator_id=int(gripper_actuator_id),
                joint_name="left_driver_joint",
                target_qpos=driver,
            )
            _sync_actuator_activation(model, data, int(gripper_actuator_id), driver)

    mujoco.mj_forward(model, data)
    _settle_scene(
        model,
        data,
        preserve_joint_names=[*DEFAULT_ARM_JOINT_NAMES, *GRIPPER_JOINT_NAMES],
    )


def _normalize_quaternion(quaternion_wxyz: list[float]) -> list[float]:
    if len(quaternion_wxyz) < 4:
        return [1.0, 0.0, 0.0, 0.0]
    w, x, y, z = [float(v) for v in quaternion_wxyz[:4]]
    norm = (w * w + x * x + y * y + z * z) ** 0.5
    if norm <= 1e-8:
        return [1.0, 0.0, 0.0, 0.0]
    inv = 1.0 / norm
    return [w * inv, x * inv, y * inv, z * inv]


def _set_actuator_ctrl_for_joint_target(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    actuator_id: int,
    joint_name: str,
    target_qpos: float,
) -> None:
    data.ctrl[int(actuator_id)] = float(target_qpos)


def _sync_actuator_activation(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    actuator_id: int,
    target: float,
) -> None:
    if data.act is None or len(data.act) <= 0:
        return
    act_addr = int(model.actuator_actadr[int(actuator_id)])
    if act_addr < 0 or act_addr >= len(data.act):
        return
    data.act[act_addr] = float(target)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _move_toward(value: float, target: float, max_delta: float) -> float:
    delta = float(target) - float(value)
    return float(value) + _clamp(delta, -abs(float(max_delta)), abs(float(max_delta)))


def _advance_viewer_servo_target(
    current: float,
    target: float,
    velocity: float,
    dt: float,
    max_speed: float,
    max_accel: float,
) -> tuple[float, float]:
    stable_dt = max(float(dt), 1e-6)
    current_value = float(current)
    target_value = float(target)
    try:
        current_velocity = float(velocity)
    except (TypeError, ValueError):
        current_velocity = 0.0
    if not math.isfinite(current_velocity):
        current_velocity = 0.0

    error = target_value - current_value
    if abs(error) <= 1e-7 and abs(current_velocity) <= 1e-6:
        return target_value, 0.0

    speed_limit = max(1e-6, abs(float(max_speed)))
    accel_limit = max(1e-6, abs(float(max_accel)))
    desired_speed = min(speed_limit, math.sqrt(max(0.0, 2.0 * accel_limit * abs(error))))
    desired_velocity = math.copysign(desired_speed, error) if abs(error) > 1e-9 else 0.0
    next_velocity = _move_toward(
        current_velocity,
        desired_velocity,
        accel_limit * stable_dt,
    )
    next_position = current_value + next_velocity * stable_dt

    if (target_value - current_value) * (target_value - next_position) <= 0.0:
        return target_value, 0.0
    return next_position, next_velocity


def _reset_viewer_ctrl_servo_state(
    data: mujoco.MjData,
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
    ctrl_servo_state: dict[str, object],
) -> None:
    arm_position = [0.0 for _ in DEFAULT_ARM_JOINT_NAMES]
    if data.ctrl is None or len(data.ctrl) <= 0:
        ctrl_servo_state["arm"] = arm_position
        ctrl_servo_state["arm_velocity"] = [0.0 for _ in DEFAULT_ARM_JOINT_NAMES]
        ctrl_servo_state["driver"] = 0.0
        ctrl_servo_state["driver_velocity"] = 0.0
        return
    for idx, actuator_id in enumerate(arm_actuator_ids[: len(arm_position)]):
        if actuator_id is None:
            continue
        arm_position[idx] = float(data.ctrl[int(actuator_id)])
    ctrl_servo_state["arm"] = arm_position
    ctrl_servo_state["arm_velocity"] = [0.0 for _ in DEFAULT_ARM_JOINT_NAMES]
    if gripper_actuator_id is not None:
        ctrl_servo_state["driver"] = float(data.ctrl[int(gripper_actuator_id)])
    else:
        ctrl_servo_state["driver"] = 0.0
    ctrl_servo_state["driver_velocity"] = 0.0


def _apply_viewer_ctrl_servo_step(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target_pose: dict[str, object],
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
    ctrl_servo_state: dict[str, object],
) -> None:
    if data.ctrl is None or len(data.ctrl) <= 0:
        return

    arm_values, driver_value = _parse_viewer_pose_targets(target_pose)
    if arm_values is None:
        return

    dt = max(1e-6, float(model.opt.timestep))
    arm_position = ctrl_servo_state.get("arm")
    if not isinstance(arm_position, list) or len(arm_position) < len(DEFAULT_ARM_JOINT_NAMES):
        arm_position = [0.0 for _ in DEFAULT_ARM_JOINT_NAMES]
        for idx, actuator_id in enumerate(arm_actuator_ids[: len(arm_position)]):
            if actuator_id is not None:
                arm_position[idx] = float(data.ctrl[int(actuator_id)])
        ctrl_servo_state["arm"] = arm_position

    arm_velocity = ctrl_servo_state.get("arm_velocity")
    if not isinstance(arm_velocity, list) or len(arm_velocity) < len(DEFAULT_ARM_JOINT_NAMES):
        arm_velocity = [0.0 for _ in DEFAULT_ARM_JOINT_NAMES]
        ctrl_servo_state["arm_velocity"] = arm_velocity

    for idx, actuator_id in enumerate(arm_actuator_ids[: len(DEFAULT_ARM_JOINT_NAMES)]):
        if actuator_id is None or idx >= len(arm_values):
            continue
        target_value = arm_values[idx]
        if target_value is None:
            continue
        current = float(arm_position[idx])
        next_ctrl, next_velocity = _advance_viewer_servo_target(
            current=current,
            target=float(target_value),
            velocity=float(arm_velocity[idx]),
            dt=dt,
            max_speed=VIEWER_CTRL_ARM_MAX_SPEED_RAD_S,
            max_accel=VIEWER_CTRL_ARM_MAX_ACCEL_RAD_S2,
        )
        data.ctrl[int(actuator_id)] = float(next_ctrl)
        arm_position[idx] = float(next_ctrl)
        arm_velocity[idx] = float(next_velocity)

    if driver_value is None or gripper_actuator_id is None:
        return
    driver_raw = ctrl_servo_state.get("driver", float(data.ctrl[int(gripper_actuator_id)]))
    driver_velocity_raw = ctrl_servo_state.get("driver_velocity", 0.0)
    try:
        current_driver = float(driver_raw)
    except (TypeError, ValueError):
        current_driver = float(data.ctrl[int(gripper_actuator_id)])
    try:
        driver_velocity = float(driver_velocity_raw)
    except (TypeError, ValueError):
        driver_velocity = 0.0
    next_driver, next_driver_velocity = _advance_viewer_servo_target(
        current=current_driver,
        target=float(driver_value),
        velocity=driver_velocity,
        dt=dt,
        max_speed=VIEWER_CTRL_GRIPPER_MAX_SPEED_DRIVER_S,
        max_accel=VIEWER_CTRL_GRIPPER_MAX_ACCEL_DRIVER_S2,
    )
    data.ctrl[int(gripper_actuator_id)] = float(next_driver)
    ctrl_servo_state["driver"] = float(next_driver)
    ctrl_servo_state["driver_velocity"] = float(next_driver_velocity)


def _step_viewer_local_physics(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    steps: int,
    ctrl_target_pose: dict[str, object] | None,
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
    ctrl_servo_state: dict[str, object],
) -> None:
    for _ in range(max(1, int(steps))):
        if ctrl_target_pose is not None:
            _apply_viewer_ctrl_servo_step(
                model=model,
                data=data,
                target_pose=ctrl_target_pose,
                arm_actuator_ids=arm_actuator_ids,
                gripper_actuator_id=gripper_actuator_id,
                ctrl_servo_state=ctrl_servo_state,
            )
        mujoco.mj_step(model, data)


def _settle_scene(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    steps: int = SCENE_SETTLE_STEPS,
    preserve_joint_names: list[str] | None = None,
) -> None:
    preserved_qpos: list[tuple[int, float]] = []
    preserved_qvel: list[int] = []
    for joint_name in preserve_joint_names or []:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        preserved_qpos.append((qpos_addr, float(data.qpos[qpos_addr])))
        preserved_qvel.append(int(model.jnt_dofadr[joint_id]))

    ctrl_snapshot = data.ctrl.copy() if data.ctrl is not None and len(data.ctrl) > 0 else None
    for _ in range(max(0, int(steps))):
        mujoco.mj_step(model, data)
        if preserved_qpos:
            for qpos_addr, qpos_value in preserved_qpos:
                data.qpos[qpos_addr] = qpos_value
            for qvel_addr in preserved_qvel:
                data.qvel[qvel_addr] = 0.0
            if ctrl_snapshot is not None:
                data.ctrl[:] = ctrl_snapshot
            mujoco.mj_forward(model, data)
    for qpos_addr, qpos_value in preserved_qpos:
        data.qpos[qpos_addr] = qpos_value
    for qvel_addr in preserved_qvel:
        data.qvel[qvel_addr] = 0.0
    if ctrl_snapshot is not None:
        data.ctrl[:] = ctrl_snapshot
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def _parse_viewer_pose_targets(
    pose: dict[str, object],
) -> tuple[list[float | None] | None, float | None]:
    arm_raw = pose.get("arm")
    if not isinstance(arm_raw, list) or len(arm_raw) < len(DEFAULT_ARM_JOINT_NAMES):
        return None, None

    arm_values: list[float | None] = [None for _ in range(len(DEFAULT_ARM_JOINT_NAMES))]
    for idx in range(len(DEFAULT_ARM_JOINT_NAMES)):
        try:
            arm_values[idx] = float(arm_raw[idx])
        except (TypeError, ValueError):
            continue

    driver_value: float | None = None
    driver_raw = pose.get("driver")
    if driver_raw is not None:
        try:
            driver_value = max(0.0, min(float(driver_raw), GRIPPER_DRIVER_LIMIT))
        except (TypeError, ValueError):
            driver_value = None

    return arm_values, driver_value


def _apply_object_pose_to_viewer(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    body_id: int,
    position: list[float],
    quaternion: list[float],
) -> None:
    normalized_quat = _normalize_quaternion(quaternion)
    body_joint_count = int(model.body_jntnum[body_id])
    if body_joint_count > 0:
        joint_start = int(model.body_jntadr[body_id])
        for offset in range(body_joint_count):
            joint_id = joint_start + offset
            if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_FREE):
                continue
            qpos_addr = int(model.jnt_qposadr[joint_id])
            data.qpos[qpos_addr : qpos_addr + 3] = [
                float(position[0]),
                float(position[1]),
                float(position[2]),
            ]
            data.qpos[qpos_addr + 3 : qpos_addr + 7] = normalized_quat
            return

    model.body_pos[body_id] = [float(position[0]), float(position[1]), float(position[2])]
    model.body_quat[body_id] = normalized_quat


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


def _apply_backend_state_to_viewer(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    state: dict[str, object],
    apply_velocity: bool = True,
    hard_sync_pose: bool = True,
) -> bool:
    qpos = state.get("qpos")
    if not isinstance(qpos, list) or len(qpos) < len(DEFAULT_ARM_JOINT_NAMES):
        return False
    qvel = state.get("qvel") if isinstance(state.get("qvel"), list) else None
    arm_ctrl_qpos = state.get("arm_ctrl_qpos") if isinstance(state.get("arm_ctrl_qpos"), list) else None
    arm_target_qpos = state.get("arm_target_qpos") if isinstance(state.get("arm_target_qpos"), list) else None

    joint_names_raw = state.get("joint_names")
    if isinstance(joint_names_raw, list) and joint_names_raw:
        joint_names = [str(name) for name in joint_names_raw]
    else:
        joint_names = list(DEFAULT_ARM_JOINT_NAMES)

    arm_joint_count = min(len(joint_names), len(DEFAULT_ARM_JOINT_NAMES), len(qpos))
    joint_name_to_default_index = {
        joint_name: idx for idx, joint_name in enumerate(DEFAULT_ARM_JOINT_NAMES)
    }
    applied_arm_qpos: list[float | None] = [None for _ in range(len(DEFAULT_ARM_JOINT_NAMES))]
    applied_arm_ctrl_targets: list[float | None] = [None for _ in range(len(DEFAULT_ARM_JOINT_NAMES))]
    for idx in range(arm_joint_count):
        joint_name = joint_names[idx]
        default_index = joint_name_to_default_index.get(joint_name)
        if default_index is None:
            continue
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        qvel_addr = int(model.jnt_dofadr[joint_id])
        try:
            qpos_value = float(qpos[idx])
            applied_arm_qpos[default_index] = qpos_value
        except (TypeError, ValueError):
            continue
        if hard_sync_pose:
            data.qpos[qpos_addr] = qpos_value
        if apply_velocity and hard_sync_pose and qvel is not None and idx < len(qvel):
            try:
                qvel_value = float(qvel[idx])
                data.qvel[qvel_addr] = qvel_value
            except (TypeError, ValueError):
                pass
        if arm_ctrl_qpos is not None and idx < len(arm_ctrl_qpos):
            try:
                applied_arm_ctrl_targets[default_index] = float(arm_ctrl_qpos[idx])
            except (TypeError, ValueError):
                pass
        elif arm_target_qpos is not None and idx < len(arm_target_qpos):
            try:
                applied_arm_ctrl_targets[default_index] = float(arm_target_qpos[idx])
            except (TypeError, ValueError):
                pass

    gripper_targets = _extract_gripper_joint_targets(state)
    applied_driver: float | None = None
    gripper_target_driver: float | None = None
    gripper_ctrl_opening = state.get("gripper_ctrl_opening")
    try:
        if gripper_ctrl_opening is not None:
            gripper_target_driver = max(
                0.0,
                min(float(gripper_ctrl_opening), 1.0),
            ) * GRIPPER_DRIVER_LIMIT
    except (TypeError, ValueError):
        gripper_target_driver = None
    gripper_target_opening = state.get("gripper_target_opening")
    try:
        if gripper_target_driver is None and gripper_target_opening is not None:
            gripper_target_driver = max(
                0.0,
                min(float(gripper_target_opening), 1.0),
            ) * GRIPPER_DRIVER_LIMIT
    except (TypeError, ValueError):
        gripper_target_driver = None
    gripper_joint_velocity = 0.0
    if apply_velocity and hard_sync_pose and qvel is not None and len(qvel) > len(DEFAULT_ARM_JOINT_NAMES):
        try:
            gripper_joint_velocity = float(qvel[len(DEFAULT_ARM_JOINT_NAMES)]) * GRIPPER_DRIVER_LIMIT
        except (TypeError, ValueError):
            gripper_joint_velocity = 0.0
    for joint_name, joint_target in gripper_targets.items():
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        if hard_sync_pose:
            data.qpos[qpos_addr] = float(joint_target)
        if apply_velocity and hard_sync_pose:
            qvel_addr = int(model.jnt_dofadr[joint_id])
            data.qvel[qvel_addr] = gripper_joint_velocity
        if joint_name == "left_driver_joint":
            applied_driver = float(joint_target)

    if data.ctrl is not None and len(data.ctrl) > 0:
        for idx, actuator_name in enumerate(DEFAULT_ARM_ACTUATOR_NAMES):
            if idx >= len(applied_arm_qpos):
                break
            target_value = applied_arm_ctrl_targets[idx]
            if target_value is None:
                target_value = applied_arm_qpos[idx]
            if target_value is None:
                continue
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id < 0:
                continue
            _set_actuator_ctrl_for_joint_target(
                model=model,
                data=data,
                actuator_id=int(actuator_id),
                joint_name=DEFAULT_ARM_JOINT_NAMES[idx],
                target_qpos=float(target_value),
            )
            if hard_sync_pose:
                _sync_actuator_activation(model, data, int(actuator_id), float(target_value))
        if gripper_target_driver is None:
            gripper_target_driver = applied_driver
        if gripper_target_driver is not None:
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
            if actuator_id >= 0:
                _set_actuator_ctrl_for_joint_target(
                    model=model,
                    data=data,
                    actuator_id=int(actuator_id),
                    joint_name="left_driver_joint",
                    target_qpos=float(gripper_target_driver),
                )
                if hard_sync_pose:
                    _sync_actuator_activation(model, data, int(actuator_id), float(gripper_target_driver))

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
            parsed_position: list[float] | None = None
            if isinstance(position, list) and len(position) >= 3:
                try:
                    parsed_position = [float(position[0]), float(position[1]), float(position[2])]
                except (TypeError, ValueError):
                    pass

            quaternion = object_state.get("quaternion")
            parsed_quaternion: list[float] | None = None
            if isinstance(quaternion, list) and len(quaternion) >= 4:
                try:
                    parsed_quaternion = [
                        float(quaternion[0]),
                        float(quaternion[1]),
                        float(quaternion[2]),
                        float(quaternion[3]),
                    ]
                except (TypeError, ValueError):
                    pass

            if parsed_position is not None or parsed_quaternion is not None:
                body_id_int = int(body_id)
                if parsed_position is None:
                    parsed_position = [float(v) for v in data.xpos[body_id_int]]
                if parsed_quaternion is None:
                    parsed_quaternion = [float(v) for v in data.xquat[body_id_int]]
                _apply_object_pose_to_viewer(
                    model=model,
                    data=data,
                    body_id=body_id_int,
                    position=parsed_position,
                    quaternion=parsed_quaternion,
                )

    mujoco.mj_forward(model, data)
    return True


def _apply_pose_to_viewer(model: mujoco.MjModel, data: mujoco.MjData, pose: dict[str, object]) -> bool:
    arm_values, driver_value = _parse_viewer_pose_targets(pose)
    if arm_values is None:
        return False

    for idx, joint_name in enumerate(DEFAULT_ARM_JOINT_NAMES):
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        qpos_value = arm_values[idx]
        if qpos_value is None:
            continue
        data.qpos[qpos_addr] = qpos_value
        arm_values[idx] = qpos_value

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
            _set_actuator_ctrl_for_joint_target(
                model=model,
                data=data,
                actuator_id=int(actuator_id),
                joint_name=DEFAULT_ARM_JOINT_NAMES[idx],
                target_qpos=float(target_value),
            )
        if driver_value is not None:
            actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, DEFAULT_GRIPPER_ACTUATOR_NAME)
            if actuator_id >= 0:
                _set_actuator_ctrl_for_joint_target(
                    model=model,
                    data=data,
                    actuator_id=int(actuator_id),
                    joint_name="left_driver_joint",
                    target_qpos=float(driver_value),
                )

    mujoco.mj_forward(model, data)
    return True


def _fetch_backend_state(state_url: str, timeout_s: float) -> dict[str, object] | None:
    parts = urlsplit(state_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "refresh_camera"
    ]
    query.append(("refresh_camera", "false"))
    state_url = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )
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


def _normalize_viewer_camera_name(raw: str | None) -> str | None:
    value = str(raw or "").strip()
    if value.lower() in VIEWER_FREE_CAMERA_NAMES:
        return None
    return value


def _apply_fixed_viewer_camera(viewer: object, model: mujoco.MjModel, camera_name: str | None) -> bool:
    normalized = _normalize_viewer_camera_name(camera_name)
    if normalized is None:
        return False

    camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, normalized)
    if camera_id < 0:
        print(f"[viewer] warning: fixed camera '{normalized}' was not found; using free camera.")
        return False

    viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
    viewer.cam.fixedcamid = int(camera_id)
    print(f"[viewer] fixed camera: {normalized}")
    return True


def _build_camera_overlay_rect(viewport: mujoco.MjrRect | None) -> mujoco.MjrRect | None:
    if viewport is None:
        return None

    viewport_width = max(0, int(viewport.width))
    viewport_height = max(0, int(viewport.height))
    if viewport_width <= 0 or viewport_height <= 0:
        return None

    margin = min(VIEWER_CAMERA_OVERLAY_MARGIN_PX, max(0, viewport_width // 20), max(0, viewport_height // 20))
    max_width = max(1, viewport_width - 2 * margin)
    max_height = max(1, viewport_height - 2 * margin)
    target_width = int(min(VIEWER_CAMERA_OVERLAY_MAX_WIDTH_PX, max_width))
    target_width = min(
        target_width,
        max(VIEWER_CAMERA_OVERLAY_MIN_WIDTH_PX, int(viewport_width * VIEWER_CAMERA_OVERLAY_FRACTION)),
    )
    target_width = max(1, min(target_width, max_width))
    target_height = max(1, int(round(target_width / VIEWER_CAMERA_OVERLAY_ASPECT)))

    if target_height > max_height:
        target_height = max(1, max_height)
        target_width = max(1, int(round(target_height * VIEWER_CAMERA_OVERLAY_ASPECT)))

    left = int(viewport.left) + max(0, viewport_width - target_width - margin)
    bottom = int(viewport.bottom) + max(0, viewport_height - target_height - margin)
    return mujoco.MjrRect(left, bottom, target_width, target_height)


class ViewerCameraOverlay:
    def __init__(self, camera_name: str | None, fps: float) -> None:
        self._camera_name = _normalize_viewer_camera_name(camera_name)
        self._frame_interval_s = 1.0 / max(1.0, float(fps))
        self._next_frame_at = 0.0
        self._camera_checked = False
        self._disabled = self._camera_name is None
        self._warned = False
        self._renderer: mujoco.Renderer | None = None
        self._renderer_size: tuple[int, int] = (0, 0)

    @property
    def camera_name(self) -> str | None:
        return self._camera_name

    @property
    def enabled(self) -> bool:
        return not self._disabled

    def close(self) -> None:
        if self._renderer is None:
            return
        try:
            self._renderer.close()
        finally:
            self._renderer = None
            self._renderer_size = (0, 0)

    def _ensure_camera_exists(self, model: mujoco.MjModel) -> bool:
        if self._camera_checked:
            return not self._disabled
        self._camera_checked = True
        if self._camera_name is None:
            self._disabled = True
            return False

        camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, self._camera_name)
        if camera_id < 0:
            print(f"[viewer] warning: camera overlay '{self._camera_name}' was not found; overlay disabled.")
            self._disabled = True
            return False
        return True

    def _ensure_renderer(self, model: mujoco.MjModel, width: int, height: int) -> mujoco.Renderer:
        requested_size = (int(width), int(height))
        if self._renderer is not None and self._renderer_size == requested_size:
            return self._renderer

        self.close()
        self._renderer = mujoco.Renderer(model, height=requested_size[1], width=requested_size[0])
        self._renderer_size = requested_size
        return self._renderer

    def update(self, viewer: object, model: mujoco.MjModel, data: mujoco.MjData, now: float) -> None:
        if self._disabled or now < self._next_frame_at:
            return
        if not self._ensure_camera_exists(model):
            return

        rect = _build_camera_overlay_rect(viewer.viewport)
        if rect is None:
            return

        try:
            renderer = self._ensure_renderer(model, int(rect.width), int(rect.height))
            renderer.update_scene(data, camera=self._camera_name)
            image = renderer.render()
            if image.ndim != 3 or image.shape[2] < 3:
                raise RuntimeError(f"unexpected camera image shape: {image.shape}")
            rgb = np.ascontiguousarray(image[:, :, :3], dtype=np.uint8)
            viewer.set_images((rect, rgb))
            self._next_frame_at = now + self._frame_interval_s
        except Exception as exc:
            if not self._warned:
                print(f"[viewer] warning: failed to render camera overlay '{self._camera_name}': {exc}")
                self._warned = True
            self._disabled = True
            self.close()


def _capture_viewer_target_pose_from_ctrl(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    arm_actuator_ids: list[int | None],
    gripper_actuator_id: int | None,
) -> dict[str, object] | None:
    if data.ctrl is None:
        return None
    if len(arm_actuator_ids) < len(DEFAULT_ARM_JOINT_NAMES):
        return None

    arm: list[float] = []
    for idx, actuator_id in enumerate(arm_actuator_ids[: len(DEFAULT_ARM_JOINT_NAMES)]):
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


def _state_was_pushed_by_viewer(state: dict[str, object] | None) -> bool:
    if not isinstance(state, dict):
        return False
    raw_input = state.get("raw_input")
    return isinstance(raw_input, dict) and str(raw_input.get("origin", "")).strip() == "mujoco_viewer"


def _state_is_remote_desktop_slider(state: dict[str, object] | None) -> bool:
    if not isinstance(state, dict):
        return False
    if _state_was_pushed_by_viewer(state):
        return False
    source = str(state.get("source", "")).strip()
    input_source = str(state.get("input_source", "")).strip()
    return source == "desktop_manual" and input_source in {"slider", "joint_slider", "slider_commit"}


def _state_is_quest_realtime_control(state: dict[str, object] | None) -> bool:
    if not isinstance(state, dict):
        return False
    source = str(state.get("source", "")).strip()
    input_source = str(state.get("input_source", "")).strip()
    return source in {"quest3_controller", "quest3_hand"} or input_source in {
        "quest3_controller",
        "quest3_hand",
    }


def _state_command_count(state: dict[str, object] | None) -> int:
    if not isinstance(state, dict):
        return -1
    stats = state.get("stats")
    if not isinstance(stats, dict):
        return -1
    try:
        return int(stats.get("commands", -1))
    except (TypeError, ValueError):
        return -1


def _push_viewer_pose_to_backend(
    step_url: str,
    pose: dict[str, object],
    timeout_s: float,
    n_steps: int = VIEWER_BRIDGE_PUSH_PHYSICS_STEPS,
    input_source: str = "slider_commit",
) -> bool:
    arm_raw = pose.get("arm")
    if not isinstance(arm_raw, list) or len(arm_raw) < len(DEFAULT_ARM_JOINT_NAMES):
        return False

    try:
        arm = [float(arm_raw[idx]) for idx in range(len(DEFAULT_ARM_JOINT_NAMES))]
    except (TypeError, ValueError):
        return False

    payload: dict[str, object] = {
        "target_positions": arm,
        "n_steps": max(1, int(n_steps)),
        "control_mode": "position",
        "source": "desktop_manual",
        "input_source": input_source,
        "raw_input": {
            "origin": "mujoco_viewer",
            "input_source": input_source,
        },
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


def run_viewer(
    model_path: Path,
    manifest_path: Path,
    fps: float,
    state_url: str,
    step_url: str,
    viewer_camera: str | None = None,
    viewer_camera_overlay: str | None = DEFAULT_VIEWER_CAMERA_OVERLAY,
    viewer_camera_overlay_fps: float = VIEWER_CAMERA_OVERLAY_FPS,
    max_local_physics_substeps: int = DEFAULT_VIEWER_LOCAL_PHYSICS_SUBSTEPS,
) -> None:
    # On Wayland, prefer X11 backend when available to reduce libdecor warnings.
    # Leave room for manual override by respecting existing env values.
    if (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        and os.environ.get("DISPLAY")
        and not os.environ.get("PYGLFW_LIBRARY_VARIANT")
    ):
        os.environ["PYGLFW_LIBRARY_VARIANT"] = "x11"

    # Defer viewer import so platform env tweaks above can take effect.
    import mujoco.viewer  # local import by design

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)

    names, qpos = _read_home_pose(manifest_path)
    _apply_home_pose(model, data, names, qpos)

    dt = max(1e-4, 1.0 / max(1.0, fps))
    model_timestep = max(1e-4, float(model.opt.timestep))
    local_physics_substeps = max(
        1,
        min(
            MAX_VIEWER_LOCAL_PHYSICS_SUBSTEPS,
            max(1, int(max_local_physics_substeps)),
            int(round(dt / model_timestep)),
        ),
    )
    state_poll_interval = max(0.005, 1.0 / min(max(fps, 1.0), 60.0))
    state_fetch_timeout = max(MIN_STATE_FETCH_TIMEOUT_S, min(MAX_STATE_FETCH_TIMEOUT_S, 2.5 * dt))
    last_poll_at = 0.0
    last_state: dict[str, object] | None = None
    backend_state_dirty = False
    arm_actuator_ids, gripper_actuator_id = _resolve_actuator_ids(model)
    last_applied_backend_pose: dict[str, object] | None = _capture_viewer_pose(model, data)
    last_physics_pose: dict[str, object] | None = _capture_viewer_pose(model, data)
    last_ui_ctrl_snapshot = _extract_ctrl_vector(data, arm_actuator_ids, gripper_actuator_id)
    pending_ctrl_edit_pose: dict[str, object] | None = None
    pending_viewer_push: dict[str, object] | None = None
    local_override_until = 0.0
    ctrl_drag_until = 0.0
    joint_drag_until = 0.0
    remote_control_guard_until = 0.0
    last_remote_slider_command_count = -1
    poll_failures = 0
    push_executor: concurrent.futures.ThreadPoolExecutor | None = None
    pending_push_future: concurrent.futures.Future[bool] | None = None
    state_executor: concurrent.futures.ThreadPoolExecutor | None = None
    pending_state_future: concurrent.futures.Future[dict[str, object] | None] | None = None
    ctrl_servo_state: dict[str, object] = {
        "arm": [0.0 for _ in DEFAULT_ARM_JOINT_NAMES],
        "arm_velocity": [0.0 for _ in DEFAULT_ARM_JOINT_NAMES],
        "driver": 0.0,
        "driver_velocity": 0.0,
    }
    _reset_viewer_ctrl_servo_state(
        data,
        arm_actuator_ids,
        gripper_actuator_id,
        ctrl_servo_state,
    )

    print(f"[viewer] loading: {model_path}")
    print(f"[viewer] syncing state from: {state_url}")
    print(f"[viewer] forwarding local edits to: {step_url}")
    print(f"[viewer] local control physics substeps/frame: {local_physics_substeps}")
    print("[viewer] controls: left-drag rotate, right-drag pan, wheel zoom")
    print("[viewer] camera view: D405 preview opens in a separate draggable window by default")
    print("[viewer] camera view: pass --viewer-camera d405_rgb to make D405 the main MuJoCo view")
    print("[viewer] close the window to return to backend console")

    camera_overlay = ViewerCameraOverlay(
        camera_name=viewer_camera_overlay,
        fps=viewer_camera_overlay_fps,
    )
    if camera_overlay.enabled:
        print(f"[viewer] camera overlay: {camera_overlay.camera_name}")

    try:
        push_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="viewer-bridge-push",
        )
        state_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="viewer-state-poll",
        )
        with mujoco.viewer.launch_passive(model, data) as viewer:
            _apply_fixed_viewer_camera(viewer, model, viewer_camera)
            while viewer.is_running():
                start = time.perf_counter()
                if pending_push_future is not None and pending_push_future.done():
                    try:
                        pending_push_future.result()
                    except Exception:
                        pass
                    pending_push_future = None
                if pending_state_future is not None and pending_state_future.done():
                    try:
                        fetched = pending_state_future.result()
                    except Exception:
                        fetched = None
                    pending_state_future = None
                    if fetched is not None:
                        last_state = fetched
                        backend_state_dirty = True
                        fetched_command_count = _state_command_count(fetched)
                        is_new_remote_slider_state = (
                            _state_is_remote_desktop_slider(fetched)
                            and fetched_command_count > last_remote_slider_command_count
                        )
                        if is_new_remote_slider_state:
                            last_remote_slider_command_count = fetched_command_count
                            remote_control_guard_until = max(
                                remote_control_guard_until,
                                time.perf_counter() + VIEWER_BRIDGE_REMOTE_CONTROL_GUARD_S,
                            )
                            pending_viewer_push = None
                            pending_ctrl_edit_pose = None
                            local_override_until = 0.0
                            ctrl_drag_until = 0.0
                            joint_drag_until = 0.0
                        if poll_failures > 0:
                            print("[viewer] backend state stream recovered.")
                        poll_failures = 0
                    else:
                        poll_failures += 1
                        if poll_failures in {1, 60, 300}:
                            print("[viewer] warning: failed to fetch backend state, keeping last rendered pose.")

                current_pose = _capture_viewer_pose(model, data)
                joint_pose_changed = (
                    current_pose is not None
                    and last_physics_pose is not None
                    and _pose_max_error(current_pose, last_physics_pose) > VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD
                )
                pre_sync_ctrl_snapshot = _extract_ctrl_vector(data, arm_actuator_ids, gripper_actuator_id)
                ui_ctrl_changed_pre_sync = _ctrl_changed(
                    current=pre_sync_ctrl_snapshot,
                    previous=last_ui_ctrl_snapshot,
                    threshold=VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD,
                )
                if ui_ctrl_changed_pre_sync:
                    remote_control_guard_until = 0.0
                    local_override_until = max(local_override_until, start + VIEWER_BRIDGE_GUARD_S)
                if joint_pose_changed:
                    remote_control_guard_until = 0.0

                pending_kind = (
                    str(pending_viewer_push.get("kind", "pose"))
                    if isinstance(pending_viewer_push, dict)
                    else ""
                )
                ctrl_pending_active = pending_kind == "ctrl"
                edit_pose: dict[str, object] | None = None
                edit_kind = "pose"
                edit_source = ""
                step_local_physics = False
                remote_control_active = start < remote_control_guard_until
                last_state_is_remote_slider = _state_is_remote_desktop_slider(last_state)
                allow_viewer_pose_edit = (not remote_control_active) and (
                    ui_ctrl_changed_pre_sync or joint_pose_changed or not last_state_is_remote_slider
                )

                if allow_viewer_pose_edit and joint_pose_changed and current_pose is not None:
                    # MuJoCo joint sliders are direct qpos editors. Keep that local
                    # interaction immediate in the viewer, and bridge it to the
                    # backend asynchronously so the render loop does not stutter.
                    edit_pose = current_pose
                    edit_kind = "pose"
                    edit_source = "joint"
                    joint_drag_until = max(joint_drag_until, start + VIEWER_BRIDGE_CTRL_IDLE_S)
                elif (
                    (not remote_control_active)
                    and
                    pending_ctrl_edit_pose is not None
                    and last_applied_backend_pose is not None
                    and _pose_max_error(pending_ctrl_edit_pose, last_applied_backend_pose)
                    > VIEWER_BRIDGE_EDIT_THRESHOLD_RAD
                ):
                    # Prefer ctrl-target pose when user drags the MuJoCo Control panel sliders.
                    edit_pose = pending_ctrl_edit_pose
                    edit_kind = "ctrl"
                    edit_source = "ctrl"
                elif allow_viewer_pose_edit and current_pose is not None and last_applied_backend_pose is not None:
                    local_edit_error = _pose_max_error(current_pose, last_applied_backend_pose)
                    if (not ctrl_pending_active) and local_edit_error > VIEWER_BRIDGE_EDIT_THRESHOLD_RAD:
                        edit_pose = current_pose

                if edit_pose is not None:
                    if edit_kind == "ctrl":
                        # Control-panel sliders edit actuator targets. Let MuJoCo
                        # integrate toward them through a local rate-limited target
                        # so slider jumps do not become actuator jumps.
                        step_local_physics = True
                        if edit_source == "ctrl":
                            ctrl_drag_until = max(ctrl_drag_until, start + VIEWER_BRIDGE_CTRL_IDLE_S)
                            pending_ctrl_edit_pose = None
                    else:
                        # Keep any residual pose mismatch visible while it is bridged
                        # to the backend.
                        _apply_pose_to_viewer(model, data, edit_pose)
                        _reset_viewer_ctrl_servo_state(
                            data,
                            arm_actuator_ids,
                            gripper_actuator_id,
                            ctrl_servo_state,
                        )
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
                            "kind": edit_kind,
                            "mode": edit_source or "pose",
                            "created_at": start,
                            "last_attempt_at": 0.0,
                        }

                if pending_viewer_push is not None:
                    last_attempt_at_raw = pending_viewer_push.get("last_attempt_at", 0.0)
                    last_attempt_at = (
                        float(last_attempt_at_raw)
                        if isinstance(last_attempt_at_raw, (int, float))
                        else 0.0
                    )
                    pending_kind = str(pending_viewer_push.get("kind", "pose"))
                    pending_mode = str(pending_viewer_push.get("mode", "pose"))
                    drag_active = (
                        start < ctrl_drag_until
                        or (pending_mode == "joint" and start < joint_drag_until)
                    )
                    if (
                        not drag_active
                        and (start - last_attempt_at) >= VIEWER_BRIDGE_MIN_PUSH_INTERVAL_S
                        and pending_push_future is None
                        and push_executor is not None
                    ):
                        pending_pose_raw = pending_viewer_push.get("pose")
                        if isinstance(pending_pose_raw, dict):
                            input_source = "slider" if drag_active else "slider_commit"
                            timeout_s = (
                                VIEWER_BRIDGE_PUSH_TIMEOUT_S
                                if drag_active
                                else min(0.25, max(VIEWER_BRIDGE_PUSH_TIMEOUT_S, 2.0 * dt))
                            )
                            pose_to_push = dict(pending_pose_raw)
                            pending_push_future = push_executor.submit(
                                _push_viewer_pose_to_backend,
                                step_url,
                                pose_to_push,
                                timeout_s,
                                VIEWER_BRIDGE_PUSH_PHYSICS_STEPS,
                                input_source,
                            )
                            pending_viewer_push["last_attempt_at"] = start
                            pending_viewer_push["submitted_at"] = start

                ctrl_sync_paused = (start < ctrl_drag_until) or (start < joint_drag_until)
                poll_interval = state_poll_interval
                if pending_viewer_push is not None:
                    poll_interval = max(poll_interval, VIEWER_BRIDGE_PENDING_POLL_INTERVAL_S)
                if (
                    (not ctrl_sync_paused)
                    and pending_state_future is None
                    and state_executor is not None
                    and (start - last_poll_at) >= poll_interval
                ):
                    pending_state_future = state_executor.submit(
                        _fetch_backend_state,
                        state_url,
                        state_fetch_timeout,
                    )
                    last_poll_at = start

                should_apply_backend = True
                if ctrl_sync_paused:
                    should_apply_backend = False
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

                local_ctrl_target_pose: dict[str, object] | None = None
                if isinstance(pending_viewer_push, dict) and str(pending_viewer_push.get("kind", "")) == "ctrl":
                    pending_ctrl_pose = pending_viewer_push.get("pose")
                    if isinstance(pending_ctrl_pose, dict):
                        local_ctrl_target_pose = pending_ctrl_pose

                if last_state is not None:
                    quest_realtime_state = _state_is_quest_realtime_control(last_state)
                    if should_apply_backend:
                        if backend_state_dirty:
                            backend_pose = _extract_pose_from_backend_state(last_state)
                            current_backend_err = (
                                _pose_max_error(current_pose, backend_pose)
                                if current_pose is not None and backend_pose is not None
                                else float("inf")
                            )
                            applied = _apply_backend_state_to_viewer(
                                model,
                                data,
                                last_state,
                                apply_velocity=current_backend_err > VIEWER_BACKEND_HARD_SYNC_THRESHOLD_RAD,
                                hard_sync_pose=current_backend_err > VIEWER_BACKEND_HARD_SYNC_THRESHOLD_RAD,
                            )
                            if applied:
                                if backend_pose is not None:
                                    last_applied_backend_pose = backend_pose
                                backend_state_dirty = False
                                _reset_viewer_ctrl_servo_state(
                                    data,
                                    arm_actuator_ids,
                                    gripper_actuator_id,
                                    ctrl_servo_state,
                                )
                        else:
                            if quest_realtime_state:
                                mujoco.mj_forward(model, data)
                            else:
                                _step_viewer_local_physics(
                                    model,
                                    data,
                                    local_physics_substeps,
                                    None,
                                    arm_actuator_ids,
                                    gripper_actuator_id,
                                    ctrl_servo_state,
                                )
                    else:
                        if step_local_physics or (
                            isinstance(pending_viewer_push, dict)
                            and str(pending_viewer_push.get("kind", "")) == "ctrl"
                        ):
                            _step_viewer_local_physics(
                                model,
                                data,
                                local_physics_substeps,
                                local_ctrl_target_pose,
                                arm_actuator_ids,
                                gripper_actuator_id,
                                ctrl_servo_state,
                            )
                        else:
                            mujoco.mj_forward(model, data)
                else:
                    if step_local_physics or (
                        isinstance(pending_viewer_push, dict)
                        and str(pending_viewer_push.get("kind", "")) == "ctrl"
                    ):
                        _step_viewer_local_physics(
                            model,
                            data,
                            local_physics_substeps,
                            local_ctrl_target_pose,
                            arm_actuator_ids,
                            gripper_actuator_id,
                            ctrl_servo_state,
                        )
                    else:
                        mujoco.mj_forward(model, data)

                last_physics_pose = _capture_viewer_pose(model, data)
                camera_overlay.update(viewer, model, data, start)
                viewer.sync()
                post_sync_ctrl_snapshot = _extract_ctrl_vector(data, arm_actuator_ids, gripper_actuator_id)
                if _ctrl_changed(
                    current=post_sync_ctrl_snapshot,
                    previous=pre_sync_ctrl_snapshot,
                    threshold=VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD,
                ) and _ctrl_changed(
                    current=post_sync_ctrl_snapshot,
                    previous=last_ui_ctrl_snapshot,
                    threshold=VIEWER_BRIDGE_CTRL_DELTA_THRESHOLD,
                ):
                    last_ui_ctrl_snapshot = list(post_sync_ctrl_snapshot)
                    pending_ctrl_edit_pose = _capture_viewer_target_pose_from_ctrl(
                        model,
                        data,
                        arm_actuator_ids,
                        gripper_actuator_id,
                    )
                sleep_time = dt - (time.perf_counter() - start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
    finally:
        if push_executor is not None:
            push_executor.shutdown(wait=False, cancel_futures=True)
        if state_executor is not None:
            state_executor.shutdown(wait=False, cancel_futures=True)
        camera_overlay.close()


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
    # Keep subsequent backend logs on a clean line (avoid "yesINFO: ...").
    print("", flush=True)
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


def _start_camera_preview_window(camera_url: str, fps: float) -> subprocess.Popen[bytes]:
    script_path = REPO_ROOT / "backend" / "camera_preview.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--url",
        camera_url,
        "--fps",
        str(max(1.0, float(fps))),
    ]
    print("[viewer] starting D405 preview:", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=str(REPO_ROOT))


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
        default=DEFAULT_VIEWER_FPS,
        help=f"Viewer stepping FPS (default: {DEFAULT_VIEWER_FPS:g}; use 60 for visual debugging).",
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
        "--viewer-camera",
        type=str,
        default=None,
        help="Open MuJoCo viewer with a fixed camera name such as d405_rgb; use free/none to keep the free camera.",
    )
    parser.add_argument(
        "--viewer-camera-overlay",
        type=str,
        default=DEFAULT_VIEWER_CAMERA_OVERLAY,
        help="Show a fixed camera inset inside the MuJoCo viewer. Default is off; use d405_rgb to enable.",
    )
    parser.add_argument(
        "--viewer-camera-overlay-fps",
        type=float,
        default=VIEWER_CAMERA_OVERLAY_FPS,
        help="Target FPS for the MuJoCo camera inset (default: 12).",
    )
    parser.add_argument(
        "--camera-preview-window",
        choices=["yes", "no"],
        default="no",
        help="Open a separate draggable D405 RGB preview window when MuJoCo viewer opens (default: no).",
    )
    parser.add_argument(
        "--camera-preview-fps",
        type=float,
        default=DEFAULT_CAMERA_PREVIEW_FPS,
        help="Target FPS for the separate D405 RGB preview window (default: 15).",
    )
    parser.add_argument(
        "--viewer-local-physics-substeps",
        type=int,
        default=DEFAULT_VIEWER_LOCAL_PHYSICS_SUBSTEPS,
        help=(
            "Max local MuJoCo physics substeps per viewer frame "
            f"(default: {DEFAULT_VIEWER_LOCAL_PHYSICS_SUBSTEPS}; raise only for viewer-side slider debugging)."
        ),
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn --reload for backend development (default: off to reduce Quest/viewer latency).",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Deprecated compatibility flag; reload is already disabled unless --reload is passed.",
    )
    args = parser.parse_args()

    if args.open_viewer == "yes":
        _restart_with_mjpython_if_needed(open_viewer=True)
    elif args.open_viewer == "ask" and sys.platform == "darwin" and not _is_running_under_mjpython():
        should_open_viewer = _ask_yes_no(
            "是否加载 MuJoCo 仿真环境? 输入 yes 才加载，其他输入均不加载: ",
        )
        if should_open_viewer:
            _restart_with_mjpython_if_needed(
                open_viewer=True,
                argv=_argv_with_open_viewer("yes"),
            )
            args.open_viewer = "yes"
        else:
            args.open_viewer = "no"

    model_path = _resolve_path(args.model, DEFAULT_MODEL)
    manifest_path = _resolve_path(args.manifest, DEFAULT_MANIFEST)
    selected_port, auto_switched_port = _select_backend_port(args.host, args.port)
    if auto_switched_port:
        print(
            f"[backend] port {args.port} is unavailable; switching to available port {selected_port}.",
            flush=True,
        )

    backend_process: subprocess.Popen[bytes] | None = None
    try:
        backend_process = _start_backend(
            host=args.host,
            port=selected_port,
            reload_enabled=bool(args.reload and not args.no_reload),
            ssl_certfile=args.ssl_certfile,
            ssl_keyfile=args.ssl_keyfile,
        )
        _wait_backend_ready(
            process=backend_process,
            host=args.host,
            port=selected_port,
            timeout_s=max(3.0, args.backend_timeout),
        )
        _write_backend_runtime_file(
            host=args.host,
            port=selected_port,
            requested_port=args.port,
            ssl_enabled=bool(args.ssl_certfile and args.ssl_keyfile),
        )
        print(f"[backend] runtime target saved to {BACKEND_RUNTIME_PATH}", flush=True)

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
            state_url = f"{scheme}://{check_host}:{selected_port}/sim/state/?refresh_camera=false"
            step_url = f"{scheme}://{check_host}:{selected_port}/sim/step/"
            camera_preview_process: subprocess.Popen[bytes] | None = None
            if args.camera_preview_window == "yes":
                camera_url = f"{scheme}://{check_host}:{selected_port}/sim/camera/rgb/?include_data=true"
                camera_preview_process = _start_camera_preview_window(
                    camera_url=camera_url,
                    fps=args.camera_preview_fps,
                )
            try:
                run_viewer(
                    model_path=model_path,
                    manifest_path=manifest_path,
                    fps=args.fps,
                    state_url=state_url,
                    step_url=step_url,
                    viewer_camera=args.viewer_camera,
                    viewer_camera_overlay=args.viewer_camera_overlay,
                    viewer_camera_overlay_fps=args.viewer_camera_overlay_fps,
                    max_local_physics_substeps=args.viewer_local_physics_substeps,
                )
            finally:
                _stop_backend(camera_preview_process)

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
