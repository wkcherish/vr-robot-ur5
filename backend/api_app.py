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

from backend.dataset import DatasetCollectionService
from backend.schemas import (
    CommandResult,
    DatasetEpisodeResultRequest,
    DatasetEpisodeStartRequest,
    DatasetEpisodeStopRequest,
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
# Quest headset refresh is commonly 72Hz, so matching the default motion
# broadcast cadence removes a subtle 60Hz "stair-step" feel in immersive teleop.
STATE_BROADCAST_HZ = float(os.getenv("STATE_BROADCAST_HZ", "72"))
STATE_BROADCAST_INTERVAL = max(0.01, 1.0 / max(1.0, STATE_BROADCAST_HZ))
STATUS_BROADCAST_HZ = float(os.getenv("STATUS_BROADCAST_HZ", "6"))
STATUS_BROADCAST_INTERVAL = max(0.05, 1.0 / max(1.0, STATUS_BROADCAST_HZ))
WS_SEND_TIMEOUT_S = float(os.getenv("WS_SEND_TIMEOUT_S", "0.03"))
INTERACTIVE_PASSIVE_ADVANCE_MAX_S = float(
    os.getenv("INTERACTIVE_PASSIVE_ADVANCE_MAX_S", str(STATE_BROADCAST_INTERVAL))
)

simulation = SimulationCore(manifest_path=SCENE_MANIFEST_PATH)
dataset_service = DatasetCollectionService()


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

        async def _send_one(websocket: WebSocket) -> None:
            try:
                await asyncio.wait_for(websocket.send_json(payload), timeout=WS_SEND_TIMEOUT_S)
            except Exception:
                stale_connections.append(websocket)

        await asyncio.gather(*(_send_one(websocket) for websocket in list(self._connections)))

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


def _is_realtime_control_request(request: StepRequest) -> bool:
    input_source = str(getattr(request, "input_source", "") or "").strip().lower()
    if input_source == "slider_commit":
        return False
    return request.source in {"quest3_controller", "quest3_hand"} or (
        request.source in {"manual", "desktop_manual"}
        and input_source in {"slider", "joint_slider"}
    )


def _consume_realtime_control_result(future: asyncio.Future[dict[str, Any]]) -> None:
    try:
        future.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        print(f"[sim/ws] realtime control failed: {exc}")


async def _record_dataset_step(request: StepRequest, state: dict[str, Any] | None = None) -> None:
    try:
        await dataset_service.record_control_step(
            request=request,
            simulation=simulation,
            state=state,
        )
    except Exception as exc:
        print(f"[dataset] control step record failed: {exc}")


def _schedule_dataset_step_record(request: StepRequest, future: asyncio.Future[dict[str, Any]]) -> None:
    def _on_done(done_future: asyncio.Future[dict[str, Any]]) -> None:
        try:
            result = done_future.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            print(f"[dataset] realtime control future failed: {exc}")
            return

        state: dict[str, Any] | None = result if isinstance(result, dict) and "qpos" in result else None
        asyncio.create_task(_record_dataset_step(request=request, state=state))

    future.add_done_callback(_on_done)


async def _state_broadcast_loop() -> None:
    last_tick = time.monotonic()
    next_tick_at = last_tick
    last_status_broadcast_at = 0.0
    while True:
        now = time.monotonic()
        elapsed_s = max(0.0, now - last_tick)
        last_tick = now
        active_count = manager.active_count
        should_advance = active_count > 0 or await simulation.needs_background_physics()
        if should_advance:
            advance_elapsed_s = elapsed_s
            if active_count > 0:
                advance_elapsed_s = min(elapsed_s, INTERACTIVE_PASSIVE_ADVANCE_MAX_S)
            await simulation.advance_passive(elapsed_s=advance_elapsed_s)
        if active_count > 0:
            if should_advance:
                motion_state = await simulation.get_motion_state()
                await manager.broadcast({"type": "motion_broadcast", "data": motion_state})
            if (now - last_status_broadcast_at) >= STATUS_BROADCAST_INTERVAL:
                status_state = await simulation.advance_and_get_broadcast_state()
                await manager.broadcast({"type": "state_broadcast", "data": status_state})
                last_status_broadcast_at = now
        next_tick_at += STATE_BROADCAST_INTERVAL
        now_after_work = time.monotonic()
        if next_tick_at < now_after_work:
            next_tick_at = now_after_work
        await asyncio.sleep(max(0.0, next_tick_at - now_after_work))


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
async def get_sim_state(refresh_camera: bool = False) -> dict[str, Any]:
    return await simulation.get_state(refresh_camera=refresh_camera)


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
        await _record_dataset_step(request=request, state=state)
    except Exception as exc:
        state = await simulation.get_state(refresh_camera=False)
        return CommandResult(status="error", message=f"step failed: {exc}", state=state)

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


@app.get("/dataset/templates/")
async def get_dataset_templates() -> dict[str, Any]:
    return dataset_service.get_templates()


@app.get("/dataset/precheck/")
async def get_dataset_precheck() -> dict[str, Any]:
    precheck = await dataset_service.precheck(
        simulation=simulation,
        ws_active_count=manager.active_count,
    )
    try:
        await simulation.update_vr_state(
            VRStateUpdateRequest(
                recording_ready=bool(precheck.get("recording_ready", False)),
                error_message="" if precheck.get("recording_ready", False) else "; ".join(precheck.get("summary", [])),
            )
        )
    except Exception:
        pass
    return precheck


@app.post("/dataset/camera-view/verify/")
async def post_dataset_camera_view_verify() -> dict[str, Any]:
    result = await dataset_service.verify_camera_view(simulation=simulation)
    if result.get("status") == "success":
        precheck = await dataset_service.precheck(
            simulation=simulation,
            ws_active_count=manager.active_count,
        )
        result["precheck"] = precheck
    return result


@app.post("/dataset/episode/start/")
async def post_dataset_episode_start(request: DatasetEpisodeStartRequest) -> dict[str, Any]:
    result = await dataset_service.start_episode(
        request=request,
        simulation=simulation,
        ws_active_count=manager.active_count,
    )
    precheck = result.get("precheck") if isinstance(result.get("precheck"), dict) else {}
    recording_ready = bool(precheck.get("recording_ready", False))
    try:
        await simulation.update_vr_state(
            VRStateUpdateRequest(
                recording_ready=recording_ready,
                error_message="" if result.get("status") == "success" else str(result.get("message", "")),
            )
        )
    except Exception:
        pass
    return result


@app.post("/dataset/episode/stop/")
async def post_dataset_episode_stop(request: DatasetEpisodeStopRequest) -> dict[str, Any]:
    result = await dataset_service.stop_episode(
        request=request,
        simulation=simulation,
        ws_active_count=manager.active_count,
    )
    if result.get("status") == "success":
        precheck = result.get("precheck") if isinstance(result.get("precheck"), dict) else {}
        try:
            await simulation.update_vr_state(
                VRStateUpdateRequest(
                    recording_ready=bool(precheck.get("recording_ready", False)),
                    error_message="",
                )
            )
        except Exception:
            pass
    return result


@app.post("/dataset/episode/result/")
async def post_dataset_episode_result(request: DatasetEpisodeResultRequest) -> dict[str, Any]:
    return await dataset_service.update_result(request)


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
    await manager.send(
        websocket,
        {"type": "state_update", "data": await simulation.get_state(refresh_camera=False)},
    )

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
        refresh_camera = bool(message_data.get("refresh_camera", True))
        state = await simulation.get_state(refresh_camera=refresh_camera)
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
            if _is_realtime_control_request(request):
                future = simulation.queue_step(request, return_state=False)
                future.add_done_callback(_consume_realtime_control_result)
                _schedule_dataset_step_record(request=request, future=future)
                expect_result = message_data.get("expect_result", message_data.get("ack", True))
                if expect_result is False:
                    return None
                return {
                    "type": "control_result",
                    "data": {
                        "status": "success",
                        "message": "realtime control queued",
                        "source": request.source,
                        "selected_joint_group": request.selected_joint_group,
                        "input_source": request.input_source,
                        "realtime": True,
                    },
                }
            # Always return state so frontend can stay synchronized with backend physics.
            return_state = True
            state = await simulation.enqueue_step(request, return_state=return_state)
            await _record_dataset_step(request=request, state=state)
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
            state = await simulation.get_state(refresh_camera=False)
            return {
                "type": "control_result",
                "data": {
                    "status": "error",
                    "message": f"Control command failed: {exc}",
                    "state": state,
                },
            }

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
