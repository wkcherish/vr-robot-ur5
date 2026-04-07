from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

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
        "left_follower_joint": -driver,
        "right_follower_joint": -driver,
    }
    for name in GRIPPER_JOINT_NAMES:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            continue
        qpos_addr = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_addr] = gripper_values[name]

    mujoco.mj_forward(model, data)


def run_viewer(model_path: Path, manifest_path: Path, fps: float) -> None:
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)

    names, qpos = _read_home_pose(manifest_path)
    _apply_home_pose(model, data, names, qpos)

    dt = max(1e-4, 1.0 / max(1.0, fps))
    print(f"[viewer] loading: {model_path}")
    print("[viewer] controls: left-drag rotate, right-drag pan, wheel zoom")
    print("[viewer] close the window to return to backend console")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            start = time.perf_counter()
            mujoco.mj_step(model, data)
            viewer.sync()
            sleep_time = dt - (time.perf_counter() - start)
            if sleep_time > 0:
                time.sleep(sleep_time)


def _start_backend(host: str, port: int, reload_enabled: bool) -> subprocess.Popen[bytes]:
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

    backend_cwd = REPO_ROOT / "backend"
    print("[backend] starting:", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=str(backend_cwd))


def _health_check_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _wait_backend_ready(process: subprocess.Popen[bytes], host: str, port: int, timeout_s: float) -> None:
    check_host = _health_check_host(host)
    health_url = f"http://{check_host}:{port}/health/"
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
        backend_process = _start_backend(host=args.host, port=args.port, reload_enabled=not args.no_reload)
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
            run_viewer(model_path=model_path, manifest_path=manifest_path, fps=args.fps)

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
