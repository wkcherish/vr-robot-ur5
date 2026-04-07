from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import mujoco


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = REPO_ROOT / "backend" / "mujoco_models" / "environment.xml"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "shared" / "scene_manifest.json"

# Milestone A/B baseline: frontend scene -> MuJoCo world uses Rx(+pi/2),
# plus workspace floor offset along MuJoCo Z.
FRONTEND_TO_MUJOCO_Z_OFFSET = 0.5
FRONTEND_TO_MUJOCO_QUAT = [
    math.cos(math.pi / 4.0),
    math.sin(math.pi / 4.0),
    0.0,
    0.0,
]


def _resolve_path(raw: str | None, default_path: Path) -> Path:
    if raw is None:
        return default_path
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def _normalize_quat(quat: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in quat))
    if norm <= 1e-12:
        return [1.0, 0.0, 0.0, 0.0]
    return [v / norm for v in quat]


def _quat_mul(lhs: list[float], rhs: list[float]) -> list[float]:
    lw, lx, ly, lz = lhs
    rw, rx, ry, rz = rhs
    return [
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ]


def _rpy_to_quaternion(roll: float, pitch: float, yaw: float) -> list[float]:
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    return [
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ]


def _frontend_to_mujoco_position(position: list[float]) -> list[float]:
    x, y, z = position
    return [x, -z, y + FRONTEND_TO_MUJOCO_Z_OFFSET]


def _frontend_to_mujoco_quaternion(rpy: list[float]) -> list[float]:
    frontend_quat = _rpy_to_quaternion(rpy[0], rpy[1], rpy[2])
    mapped = _quat_mul(FRONTEND_TO_MUJOCO_QUAT, frontend_quat)
    return _normalize_quat(mapped)


def _quaternion_angle_error(lhs: list[float], rhs: list[float]) -> float:
    nl = _normalize_quat(lhs)
    nr = _normalize_quat(rhs)
    dot = abs(sum(a * b for a, b in zip(nl, nr)))
    dot = max(-1.0, min(1.0, dot))
    return 2.0 * math.acos(dot)


def _vector_error(lhs: list[float], rhs: list[float]) -> float:
    dx = lhs[0] - rhs[0]
    dy = lhs[1] - rhs[1]
    dz = lhs[2] - rhs[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _extract_transform(block: dict[str, Any]) -> tuple[list[float], list[float]]:
    transform = block.get("transform", {})
    position = [float(v) for v in transform.get("position", [0.0, 0.0, 0.0])]
    rpy = [float(v) for v in transform.get("rotation_rpy", [0.0, 0.0, 0.0])]
    if len(position) != 3 or len(rpy) != 3:
        raise ValueError("Each transform must include 3D position and rotation_rpy.")
    return position, rpy


def _build_expected_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    robot = manifest.get("robot", {})
    robot_position, robot_rpy = _extract_transform(robot)
    entries.append(
        {
            "id": "ur5",
            "body_name": "ur5_root",
            "expected_position": _frontend_to_mujoco_position(robot_position),
            "expected_quaternion": _frontend_to_mujoco_quaternion(robot_rpy),
            "check_orientation": True,
        }
    )

    for obj in manifest.get("objects", []):
        obj_id = str(obj.get("id", "")).strip()
        if not obj_id:
            continue
        obj_position, obj_rpy = _extract_transform(obj)
        entries.append(
            {
                "id": obj_id,
                "body_name": obj_id,
                "expected_position": _frontend_to_mujoco_position(obj_position),
                "expected_quaternion": _frontend_to_mujoco_quaternion(obj_rpy),
                # camera.xml is currently a simplified marker body (not the original URDF mesh),
                # so we only lock positional alignment for now.
                "check_orientation": obj_id != "camera",
            }
        )

    return entries


def _run_alignment_check(
    model_path: Path,
    manifest_path: Path,
    position_tolerance: float,
    angle_tolerance_deg: float,
) -> dict[str, Any]:
    if not model_path.exists():
        raise FileNotFoundError(f"MuJoCo model file not found: {model_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Scene manifest file not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_entries = _build_expected_entries(manifest)

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    angle_tolerance_rad = math.radians(angle_tolerance_deg)
    results: list[dict[str, Any]] = []

    for entry in expected_entries:
        body_name = entry["body_name"]
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
        if body_id < 0:
            results.append(
                {
                    "id": entry["id"],
                    "body_name": body_name,
                    "ok": False,
                    "error": "body_not_found",
                }
            )
            continue

        expected_position = entry["expected_position"]
        expected_quaternion = entry["expected_quaternion"]
        actual_position = [float(v) for v in data.xpos[body_id]]
        actual_quaternion = [float(v) for v in data.xquat[body_id]]
        check_orientation = bool(entry.get("check_orientation", True))

        position_error = _vector_error(actual_position, expected_position)
        angle_error = _quaternion_angle_error(actual_quaternion, expected_quaternion)
        ok = position_error <= position_tolerance and (
            angle_error <= angle_tolerance_rad or not check_orientation
        )

        results.append(
            {
                "id": entry["id"],
                "body_name": body_name,
                "ok": ok,
                "expected_position": expected_position,
                "actual_position": actual_position,
                "position_error_m": position_error,
                "expected_quaternion": expected_quaternion,
                "actual_quaternion": actual_quaternion,
                "angle_error_deg": math.degrees(angle_error),
                "check_orientation": check_orientation,
            }
        )

    passed = all(bool(row.get("ok")) for row in results)
    return {
        "timestamp": time.time(),
        "model_path": str(model_path),
        "manifest_path": str(manifest_path),
        "position_tolerance_m": position_tolerance,
        "angle_tolerance_deg": angle_tolerance_deg,
        "passed": passed,
        "results": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    print("Scene Alignment Report")
    print("======================")
    print(f"model_path: {report['model_path']}")
    print(f"manifest_path: {report['manifest_path']}")
    print(f"position_tolerance_m: {report['position_tolerance_m']:.6f}")
    print(f"angle_tolerance_deg: {report['angle_tolerance_deg']:.4f}")
    print("")

    for row in report["results"]:
        status = "PASS" if row.get("ok") else "FAIL"
        print(f"[{status}] {row['id']} ({row['body_name']})")
        if "error" in row:
            print(f"  error: {row['error']}")
            continue
        print(
            "  position_error_m={:.8f}, angle_error_deg={:.6f}".format(
                row["position_error_m"], row["angle_error_deg"]
            )
        )
        if not row.get("check_orientation", True):
            print("  orientation_check=skipped (camera marker model)")
        print(f"  expected_position={row['expected_position']}")
        print(f"  actual_position={row['actual_position']}")
        print("")

    print("overall:", "PASS" if report["passed"] else "FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify MuJoCo scene alignment against shared/scene_manifest.json baseline."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to MuJoCo model XML (default: backend/mujoco_models/environment.xml).",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to scene manifest (default: shared/scene_manifest.json).",
    )
    parser.add_argument(
        "--position-tol",
        type=float,
        default=1e-3,
        help="Position tolerance in meters (default: 1e-3).",
    )
    parser.add_argument(
        "--angle-tol-deg",
        type=float,
        default=1.0,
        help="Orientation tolerance in degrees (default: 1.0).",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional JSON output path for machine-readable report.",
    )
    args = parser.parse_args()

    model_path = _resolve_path(args.model, DEFAULT_MODEL_PATH)
    manifest_path = _resolve_path(args.manifest, DEFAULT_MANIFEST_PATH)
    report = _run_alignment_check(
        model_path=model_path,
        manifest_path=manifest_path,
        position_tolerance=max(1e-9, float(args.position_tol)),
        angle_tolerance_deg=max(1e-6, float(args.angle_tol_deg)),
    )
    _print_report(report)

    if args.json_out:
        json_output_path = _resolve_path(args.json_out, REPO_ROOT / "scene_alignment_report.json")
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"json_report: {json_output_path}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
