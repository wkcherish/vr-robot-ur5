from __future__ import annotations

import argparse
import base64
import json
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


DEFAULT_CAMERA_URL = "http://127.0.0.1:8000/sim/camera/rgb/?include_data=true"
DEFAULT_FPS = 15.0
DEFAULT_TIMEOUT_S = 1.0


@dataclass(frozen=True)
class CameraFrame:
    width: int
    height: int
    rgb: bytes
    frame_id: str
    timestamp: float | None
    status: str


def _url_with_include_data(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["include_data"] = "true"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _fetch_camera_frame(url: str, timeout_s: float) -> CameraFrame:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=max(0.1, float(timeout_s))) as response:
        payload = json.loads(response.read().decode("utf-8"))

    stream = payload.get("stream", {})
    frame_data = payload.get("rgb_data", {})
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    encoded = str(frame_data.get("data_base64", ""))
    if width <= 0 or height <= 0 or not encoded:
        raise RuntimeError("camera response does not contain an RGB frame")

    rgb = base64.b64decode(encoded)
    expected_bytes = width * height * 3
    if len(rgb) < expected_bytes:
        raise RuntimeError(f"RGB frame is truncated: got {len(rgb)} bytes, expected {expected_bytes}")

    frame_id = str(payload.get("d405_frame_id") or payload.get("frame_id") or "-")
    timestamp_raw = payload.get("timestamp")
    timestamp = float(timestamp_raw) if isinstance(timestamp_raw, (int, float)) else None
    capture_ok = bool(payload.get("camera_capture_ok", False))
    valid = bool(payload.get("rgb_valid", False))
    status = "OK" if capture_ok and valid else str(payload.get("last_error") or "camera frame not valid")
    return CameraFrame(
        width=width,
        height=height,
        rgb=rgb[:expected_bytes],
        frame_id=frame_id,
        timestamp=timestamp,
        status=status,
    )


def _photo_image_from_rgb(frame: CameraFrame) -> tk.PhotoImage:
    header = f"P6\n{frame.width} {frame.height}\n255\n".encode("ascii")
    ppm = header + frame.rgb
    try:
        return tk.PhotoImage(data=ppm, format="PPM")
    except tk.TclError:
        encoded = base64.b64encode(ppm).decode("ascii")
        return tk.PhotoImage(data=encoded, format="PPM")


class CameraPreviewApp:
    def __init__(self, url: str, fps: float, timeout_s: float, title: str) -> None:
        self._url = _url_with_include_data(url)
        self._interval_s = 1.0 / max(1.0, float(fps))
        self._timeout_s = max(0.1, float(timeout_s))
        self._frames: queue.Queue[CameraFrame] = queue.Queue(maxsize=1)
        self._errors: queue.Queue[str] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._fetch_loop, daemon=True)
        self._photo: tk.PhotoImage | None = None
        self._image_id: int | None = None

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("660x540")
        self.root.minsize(320, 260)
        self.root.configure(background="#111820")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._canvas = tk.Canvas(self.root, background="#111820", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._status_var = tk.StringVar(value="Waiting for D405 RGB frame...")
        self._status = tk.Label(
            self.root,
            textvariable=self._status_var,
            anchor="w",
            padx=8,
            pady=4,
            foreground="#e7eef5",
            background="#202a33",
        )
        self._status.pack(fill=tk.X)

        self._canvas.bind("<Configure>", lambda _event: self._center_image())

    def run(self) -> None:
        self._worker.start()
        self.root.after(16, self._poll_queues)
        self.root.mainloop()

    def close(self) -> None:
        self._stop_event.set()
        self.root.destroy()

    def _fetch_loop(self) -> None:
        while not self._stop_event.is_set():
            started_at = time.monotonic()
            try:
                frame = _fetch_camera_frame(self._url, self._timeout_s)
                self._replace_queue_item(self._frames, frame)
            except (OSError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
                self._replace_queue_item(self._errors, f"Waiting for D405 frame: {exc}")

            elapsed = time.monotonic() - started_at
            self._stop_event.wait(max(0.0, self._interval_s - elapsed))

    @staticmethod
    def _replace_queue_item(target: queue.Queue[object], item: object) -> None:
        try:
            target.put_nowait(item)
            return
        except queue.Full:
            pass
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        try:
            target.put_nowait(item)
        except queue.Full:
            pass

    def _poll_queues(self) -> None:
        try:
            frame = self._frames.get_nowait()
        except queue.Empty:
            frame = None

        if frame is not None:
            self._show_frame(frame)
        else:
            try:
                error = self._errors.get_nowait()
            except queue.Empty:
                error = None
            if error:
                self._status_var.set(error)

        if not self._stop_event.is_set():
            self.root.after(16, self._poll_queues)

    def _show_frame(self, frame: CameraFrame) -> None:
        photo = _photo_image_from_rgb(frame)
        canvas_width = max(1, int(self._canvas.winfo_width()))
        canvas_height = max(1, int(self._canvas.winfo_height()))
        subsample = max(1, int(max(frame.width / canvas_width, frame.height / canvas_height)))
        self._photo = photo.subsample(subsample, subsample) if subsample > 1 else photo
        if self._image_id is None:
            self._image_id = self._canvas.create_image(0, 0, anchor=tk.CENTER, image=self._photo)
        else:
            self._canvas.itemconfigure(self._image_id, image=self._photo)

        timestamp_text = "-" if frame.timestamp is None else time.strftime("%H:%M:%S", time.localtime(frame.timestamp))
        self._status_var.set(f"{frame.frame_id}  {frame.width}x{frame.height}  {timestamp_text}  {frame.status}")
        self._center_image()

    def _center_image(self) -> None:
        if self._image_id is None:
            return
        width = max(1, int(self._canvas.winfo_width()))
        height = max(1, int(self._canvas.winfo_height()))
        self._canvas.coords(self._image_id, width // 2, height // 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a draggable D405 RGB preview window.")
    parser.add_argument("--url", type=str, default=DEFAULT_CAMERA_URL, help="D405 RGB endpoint URL.")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Preview polling FPS.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="HTTP timeout in seconds.")
    parser.add_argument("--title", type=str, default="D405 RGB Preview", help="Window title.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = CameraPreviewApp(
        url=args.url,
        fps=args.fps,
        timeout_s=args.timeout,
        title=args.title,
    )
    app.run()


if __name__ == "__main__":
    main()
