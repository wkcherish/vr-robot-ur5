from __future__ import annotations

import asyncio
import math
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.schemas import (
    CommandResult,
    ErrorResponse,
    HealthResponse,
    ResetRequest,
    StepRequest,
    VRStateUpdateRequest,
    WSMessage,
)
from backend.sim import SimulationCore

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "shared" / "scene_manifest.json"
SCENE_MANIFEST_PATH = Path(os.getenv("SCENE_MANIFEST_PATH", str(DEFAULT_MANIFEST))).resolve()
STATE_BROADCAST_HZ = float(os.getenv("STATE_BROADCAST_HZ", "50"))
STATE_BROADCAST_INTERVAL = max(0.01, 1.0 / max(1.0, STATE_BROADCAST_HZ))

simulation = SimulationCore(manifest_path=SCENE_MANIFEST_PATH)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def send(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self._connections:
            return

        stale_connections: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(websocket)


manager = ConnectionManager()


def _guess_host_ip() -> str | None:
    env_host_ip = str(os.getenv("HOST_IP", "")).strip()
    if env_host_ip:
        return env_host_ip

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            guessed = sock.getsockname()[0]
            if guessed and not guessed.startswith("127."):
                return guessed
    except Exception:
        pass

    try:
        hostname_ip = socket.gethostbyname(socket.gethostname())
        if hostname_ip and not hostname_ip.startswith("127."):
            return hostname_ip
    except Exception:
        pass

    return None


def _error_payload(code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    body = ErrorResponse(code=code, message=message, detail=detail, timestamp=time.time())
    return {"type": "error", "data": body.model_dump()}


async def _state_broadcast_loop() -> None:
    while True:
        if manager.active_count > 0:
            state = await simulation.get_state()
            await manager.broadcast({"type": "state_broadcast", "data": state})
        await asyncio.sleep(STATE_BROADCAST_INTERVAL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await simulation.start()
    broadcast_task = asyncio.create_task(_state_broadcast_loop(), name="state-broadcast-loop")
    try:
        yield
    finally:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
        await simulation.stop()


app = FastAPI(
    title="Embossed Digital Twin Backend",
    version="0.2.0-milestone-c",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health/", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="embossed-digital-twin-backend",
        timestamp=time.time(),
        model_backend=simulation.model_backend,
        scene_manifest=simulation.scene_manifest_path,
        host_ip=_guess_host_ip(),
    )


@app.get("/sim/state/")
async def get_sim_state() -> dict[str, Any]:
    return await simulation.get_state()


@app.get("/sim/observation/")
async def get_sim_observation(include_data: bool = False) -> dict[str, Any]:
    return await simulation.get_camera_observation(include_data=include_data)


@app.get("/sim/camera/rgb/")
async def get_sim_camera_rgb(include_data: bool = False) -> dict[str, Any]:
    return await simulation.get_camera_stream(stream_name="rgb", include_data=include_data)


@app.get("/sim/camera/depth/")
async def get_sim_camera_depth(include_data: bool = False) -> dict[str, Any]:
    return await simulation.get_camera_stream(stream_name="depth", include_data=include_data)


@app.post("/sim/step/", response_model=CommandResult)
async def post_sim_step(request: StepRequest) -> CommandResult:
    try:
        state = await simulation.enqueue_step(request)
    except Exception as exc:
        return CommandResult(status="error", message=f"step failed: {exc}")

    return CommandResult(status="success", message="step executed", state=state)


@app.post("/sim/reset/", response_model=CommandResult)
async def post_sim_reset(request: ResetRequest) -> CommandResult:
    try:
        state = await simulation.reset(model_path=request.model_path)
    except Exception as exc:
        return CommandResult(status="error", message=f"reset failed: {exc}")

    return CommandResult(status="success", message="simulation reset", state=state)


@app.post("/sim/vr/state/", response_model=CommandResult)
async def post_sim_vr_state(request: VRStateUpdateRequest) -> CommandResult:
    try:
        state = await simulation.update_vr_state(request)
    except Exception as exc:
        return CommandResult(status="error", message=f"vr state update failed: {exc}")

    return CommandResult(status="success", message="vr state updated", state=state)


@app.get("/data/")
async def legacy_data() -> dict[str, str]:
    state = await simulation.get_state()
    qpos = state.get("qpos", [])
    deg = [math.degrees(v) for v in qpos]
    serialized = " ".join(f"{value:.3f}" for value in deg)
    return {"value": serialized}


@app.websocket("/sim/ws")
async def websocket_sim(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await manager.send(
        websocket,
        {
            "type": "welcome",
            "data": {
                "message": "Connected to simulation backend",
                "timestamp": time.time(),
            },
        },
    )
    await manager.send(websocket, {"type": "state_update", "data": await simulation.get_state()})

    try:
        while True:
            raw_message = await websocket.receive_json()
            payload = await _handle_ws_message(raw_message)
            if payload is not None:
                await manager.send(websocket, payload)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.exception_handler(ValidationError)
async def validation_exception_handler(_, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            detail=str(exc),
            timestamp=time.time(),
        ).model_dump(),
    )


async def _handle_ws_message(raw_message: Any) -> dict[str, Any] | None:
    try:
        message = WSMessage.model_validate(raw_message)
    except ValidationError as exc:
        return _error_payload("INVALID_MESSAGE", "Malformed websocket message", str(exc))

    message_type = message.type
    message_data = message.data or {}

    if message_type == "ping":
        return {"type": "pong", "data": {"timestamp": time.time()}}

    if message_type == "get_state":
        state = await simulation.get_state()
        return {"type": "state_update", "data": state}

    if message_type == "get_observation":
        include_data = bool(message_data.get("include_data", False))
        observation = await simulation.get_camera_observation(include_data=include_data)
        return {"type": "observation_update", "data": observation}

    if message_type == "get_camera_rgb":
        include_data = bool(message_data.get("include_data", False))
        payload = await simulation.get_camera_stream(stream_name="rgb", include_data=include_data)
        return {"type": "camera_rgb_update", "data": payload}

    if message_type == "get_camera_depth":
        include_data = bool(message_data.get("include_data", False))
        payload = await simulation.get_camera_stream(stream_name="depth", include_data=include_data)
        return {"type": "camera_depth_update", "data": payload}

    if message_type == "control":
        try:
            request = StepRequest.model_validate(message_data)
            if not getattr(request, "source", None):
                request.source = "desktop_manual"
            state = await simulation.enqueue_step(request)
            return {
                "type": "control_result",
                "data": {
                    "status": "success",
                    "message": "control command executed",
                    "state": state,
                },
            }
        except ValidationError as exc:
            return _error_payload("CONTROL_VALIDATION_ERROR", "Invalid control payload", str(exc))
        except Exception as exc:
            return _error_payload("CONTROL_EXECUTION_ERROR", "Control command failed", str(exc))

    if message_type == "reset":
        try:
            request = ResetRequest.model_validate(message_data)
            state = await simulation.reset(model_path=request.model_path)
            return {
                "type": "reset_result",
                "data": {
                    "status": "success",
                    "message": "simulation reset",
                    "state": state,
                },
            }
        except ValidationError as exc:
            return _error_payload("RESET_VALIDATION_ERROR", "Invalid reset payload", str(exc))
        except Exception as exc:
            return _error_payload("RESET_EXECUTION_ERROR", "Reset failed", str(exc))

    if message_type == "vr_state":
        try:
            request = VRStateUpdateRequest.model_validate(message_data)
            state = await simulation.update_vr_state(request)
            return {
                "type": "vr_state_result",
                "data": {
                    "status": "success",
                    "message": "vr state updated",
                    "state": state,
                },
            }
        except ValidationError as exc:
            return _error_payload("VR_STATE_VALIDATION_ERROR", "Invalid vr state payload", str(exc))
        except Exception as exc:
            return _error_payload("VR_STATE_EXECUTION_ERROR", "VR state update failed", str(exc))

    if message_type == "execute_task":
        task_name = str(message_data.get("task_name", "quest3_tool_sorting_v1"))
        state = await simulation.start_task(task_name)
        return {
            "type": "task_result",
            "data": {
                "status": "accepted",
                "message": f"task '{task_name}' marked as running (stub runtime)",
                "task_name": task_name,
                "state": state,
            },
        }

    if message_type == "stop_task":
        state = await simulation.stop_task()
        return {
            "type": "task_result",
            "data": {
                "status": "stopped",
                "message": "task stopped",
                "state": state,
            },
        }

    return _error_payload("UNKNOWN_MESSAGE_TYPE", f"Unsupported message type: {message_type}")
