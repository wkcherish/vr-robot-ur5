from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UR5_XML_PATH = REPO_ROOT / "backend" / "mujoco_models" / "ur5.xml"
DEFAULT_CAMERA_CONFIG_PATH = REPO_ROOT / "shared" / "camera_sensor_config.json"
DEFAULT_CALIBRATION_DIR = REPO_ROOT / "data" / "calibration" / "camera_intrinsics"


@dataclass(frozen=True)
class StreamIntrinsics:
    stream: str
    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float
    model: str
    coeffs: list[float]

    @property
    def center_x(self) -> float:
        return self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.height / 2.0

    @property
    def opencv_offset_x(self) -> float:
        return self.ppx - self.center_x

    @property
    def opencv_offset_y(self) -> float:
        return self.ppy - self.center_y

    @property
    def mujoco_principalpixel(self) -> tuple[float, float]:
        # RealSense/OpenCV pixel y grows downward. MuJoCo camera +Y is upward
        # in image space, so the vertical principal-point offset changes sign.
        return (self.opencv_offset_x, -self.opencv_offset_y)

    @property
    def offset_norm_px(self) -> float:
        return math.hypot(self.opencv_offset_x, self.opencv_offset_y)


def _load_pyrealsense2() -> Any:
    try:
        import pyrealsense2 as rs  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyrealsense2 is not installed in this Python environment") from exc
    return rs


def _stream_intrinsics(stream: str, profile: Any) -> StreamIntrinsics:
    intr = profile.as_video_stream_profile().get_intrinsics()
    model = str(intr.model)
    return StreamIntrinsics(
        stream=stream,
        width=int(intr.width),
        height=int(intr.height),
        fx=float(intr.fx),
        fy=float(intr.fy),
        ppx=float(intr.ppx),
        ppy=float(intr.ppy),
        model=model,
        coeffs=[float(value) for value in intr.coeffs],
    )


def read_d405_intrinsics(
    *,
    width: int,
    height: int,
    fps: int,
    serial: str | None,
    depth_mode: str,
    depth_width: int,
    depth_height: int,
    depth_fps: int,
) -> tuple[StreamIntrinsics, StreamIntrinsics | None]:
    rs = _load_pyrealsense2()
    pipeline = rs.pipeline()
    config = rs.config()
    if serial:
        config.enable_device(serial)

    config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)
    if depth_mode == "raw-depth":
        config.enable_stream(rs.stream.depth, depth_width, depth_height, rs.format.z16, depth_fps)

    profile = None
    try:
        profile = pipeline.start(config)
        device = profile.get_device()
        product_name = device.get_info(rs.camera_info.name) if device.supports(rs.camera_info.name) else ""
        if "D405" not in product_name.upper():
            print(f"warning: connected RealSense device is '{product_name}', not obviously D405", file=sys.stderr)
        color_intr = _stream_intrinsics("color", profile.get_stream(rs.stream.color))
        depth_intr = None
        if depth_mode == "raw-depth":
            depth_intr = _stream_intrinsics("depth", profile.get_stream(rs.stream.depth))
        return color_intr, depth_intr
    finally:
        if profile is not None:
            pipeline.stop()


def _format_pair(values: tuple[float, float] | list[float]) -> str:
    return f"{values[0]:.6f} {values[1]:.6f}"


def _print_intrinsics(title: str, intr: StreamIntrinsics) -> None:
    mujoco_pp = intr.mujoco_principalpixel
    print(title)
    print(f"  width: {intr.width}")
    print(f"  height: {intr.height}")
    print(f"  fx: {intr.fx:.6f}")
    print(f"  fy: {intr.fy:.6f}")
    print(f"  ppx: {intr.ppx:.6f}")
    print(f"  ppy: {intr.ppy:.6f}")
    print(f"  image_center: ({intr.center_x:.6f}, {intr.center_y:.6f})")
    print(f"  opencv_offset_px: ({intr.opencv_offset_x:.6f}, {intr.opencv_offset_y:.6f})")
    print(f"  offset_norm_px: {intr.offset_norm_px:.6f}")
    print(f"  mujoco_focalpixel: {_format_pair([intr.fx, intr.fy])}")
    print(f"  mujoco_principalpixel: {_format_pair(mujoco_pp)}")


def _set_camera_attr(xml_text: str, camera_name: str, attr: str, value: str) -> str:
    camera_pattern = re.compile(
        rf'(<camera\b(?=[^>]*\bname="{re.escape(camera_name)}")[^>]*?)(\s*/>)',
        re.DOTALL,
    )
    match = camera_pattern.search(xml_text)
    if match is None:
        raise RuntimeError(f"camera '{camera_name}' was not found in XML")

    camera_tag = match.group(1)
    closing = match.group(2)
    attr_pattern = re.compile(rf'(\b{re.escape(attr)}=")[^"]*(")')
    if attr_pattern.search(camera_tag):
        camera_tag = attr_pattern.sub(rf'\g<1>{value}\2', camera_tag, count=1)
    else:
        camera_tag = f'{camera_tag}\n                        {attr}="{value}"'
    return xml_text[: match.start()] + camera_tag + closing + xml_text[match.end() :]


def _patch_xml(xml_path: Path, rgb_intr: StreamIntrinsics, depth_intr: StreamIntrinsics) -> None:
    xml_text = xml_path.read_text(encoding="utf-8")
    for camera_name, intr in (("d405_rgb", rgb_intr), ("d405_depth", depth_intr)):
        xml_text = _set_camera_attr(xml_text, camera_name, "resolution", f"{intr.width} {intr.height}")
        xml_text = _set_camera_attr(xml_text, camera_name, "focalpixel", _format_pair([intr.fx, intr.fy]))
        xml_text = _set_camera_attr(xml_text, camera_name, "principalpixel", _format_pair(intr.mujoco_principalpixel))
    xml_path.write_text(xml_text, encoding="utf-8")


def _intrinsics_payload(intr: StreamIntrinsics) -> dict[str, Any]:
    payload = asdict(intr)
    payload["image_center"] = [intr.center_x, intr.center_y]
    payload["opencv_offset_px"] = [intr.opencv_offset_x, intr.opencv_offset_y]
    payload["mujoco_principalpixel"] = list(intr.mujoco_principalpixel)
    payload["offset_norm_px"] = intr.offset_norm_px
    return payload


def _patch_config(
    config_path: Path,
    rgb_intr: StreamIntrinsics,
    depth_intr: StreamIntrinsics,
    *,
    version: str,
    depth_mode: str,
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    primary_sensor = config.setdefault("primary_sensor", {})
    ref = primary_sensor.setdefault("intrinsics_reference", {})
    ref["source"] = "pyrealsense2_measured_device_intrinsics"
    ref["measured_at"] = datetime.now(timezone.utc).isoformat()
    ref["depth_mode"] = depth_mode
    ref["sim_resolution"] = [rgb_intr.width, rgb_intr.height]
    ref["sim_focalpixel"] = [rgb_intr.fx, rgb_intr.fy]
    ref["sim_principalpixel"] = list(rgb_intr.mujoco_principalpixel)
    ref["sim_depth_resolution"] = [depth_intr.width, depth_intr.height]
    ref["sim_depth_focalpixel"] = [depth_intr.fx, depth_intr.fy]
    ref["sim_depth_principalpixel"] = list(depth_intr.mujoco_principalpixel)
    ref["real_rgb_intrinsics"] = _intrinsics_payload(rgb_intr)
    ref["real_depth_intrinsics"] = _intrinsics_payload(depth_intr)
    notes = ref.setdefault("notes", [])
    if isinstance(notes, list):
        note = "Values were measured from the physical D405 with pyrealsense2; MuJoCo principalpixel stores offset from image center."
        if note not in notes:
            notes.append(note)

    calibration = primary_sensor.setdefault("calibration", {})
    calibration["intrinsics_version"] = version
    outputs = primary_sensor.setdefault("outputs", {})
    rgb_output = outputs.setdefault("rgb", {})
    rgb_output["width"] = rgb_intr.width
    rgb_output["height"] = rgb_intr.height
    depth_output = outputs.setdefault("depth", {})
    depth_output["width"] = depth_intr.width
    depth_output["height"] = depth_intr.height
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_calibration_json(
    calibration_dir: Path,
    rgb_intr: StreamIntrinsics,
    depth_intr: StreamIntrinsics,
    *,
    version: str,
    depth_mode: str,
) -> Path:
    calibration_dir.mkdir(parents=True, exist_ok=True)
    output_path = calibration_dir / f"{version}.json"
    payload = {
        "schema_version": "1.0.0",
        "intrinsics_version": version,
        "device": "intel_realsense_d405",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "source": "pyrealsense2_measured_device_intrinsics",
        "depth_mode": depth_mode,
        "rgb": _intrinsics_payload(rgb_intr),
        "depth": _intrinsics_payload(depth_intr),
        "mujoco_conversion": {
            "principalpixel_x": "ppx - width / 2",
            "principalpixel_y": "height / 2 - ppy",
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read measured Intel RealSense D405 intrinsics and convert them to MuJoCo camera attributes."
    )
    parser.add_argument("--width", type=int, default=1280, help="RealSense color stream width.")
    parser.add_argument("--height", type=int, default=720, help="RealSense color stream height.")
    parser.add_argument("--fps", type=int, default=30, help="RealSense color stream FPS.")
    parser.add_argument("--serial", type=str, default=None, help="Optional RealSense serial number.")
    parser.add_argument(
        "--depth-mode",
        choices=["aligned-to-color", "raw-depth"],
        default="aligned-to-color",
        help="Use color intrinsics for simulated aligned depth, or read raw depth intrinsics separately.",
    )
    parser.add_argument("--depth-width", type=int, default=1280, help="Raw RealSense depth stream width.")
    parser.add_argument("--depth-height", type=int, default=720, help="Raw RealSense depth stream height.")
    parser.add_argument("--depth-fps", type=int, default=30, help="Raw RealSense depth stream FPS.")
    parser.add_argument("--xml", type=Path, default=DEFAULT_UR5_XML_PATH, help="MuJoCo UR5 XML path to patch.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CAMERA_CONFIG_PATH,
        help="Camera sensor config JSON path to patch.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Intrinsics version string. Defaults to d405_intr_<UTC date>_measured.",
    )
    parser.add_argument("--apply", action="store_true", help="Patch XML/config and write calibration JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    version = args.version or f"d405_intr_{datetime.now(timezone.utc):%Y%m%d}_measured"
    try:
        rgb_intr, raw_depth_intr = read_d405_intrinsics(
            width=args.width,
            height=args.height,
            fps=args.fps,
            serial=args.serial,
            depth_mode=args.depth_mode,
            depth_width=args.depth_width,
            depth_height=args.depth_height,
            depth_fps=args.depth_fps,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    depth_intr = raw_depth_intr if raw_depth_intr is not None else rgb_intr
    _print_intrinsics("D405 RGB/color intrinsics", rgb_intr)
    if args.depth_mode == "aligned-to-color":
        print("D405 depth intrinsics: using RGB/color intrinsics because simulated depth is aligned to color.")
    else:
        _print_intrinsics("D405 raw depth intrinsics", depth_intr)

    if not args.apply:
        print("dry_run: no files changed; pass --apply to patch MuJoCo XML/config.")
        return

    _patch_xml(args.xml, rgb_intr, depth_intr)
    _patch_config(args.config, rgb_intr, depth_intr, version=version, depth_mode=args.depth_mode)
    calibration_path = _write_calibration_json(
        DEFAULT_CALIBRATION_DIR,
        rgb_intr,
        depth_intr,
        version=version,
        depth_mode=args.depth_mode,
    )
    print(f"patched_xml: {args.xml}")
    print(f"patched_config: {args.config}")
    print(f"wrote_calibration: {calibration_path}")


if __name__ == "__main__":
    main()
