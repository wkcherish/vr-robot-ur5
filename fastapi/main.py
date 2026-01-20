"""
UR5 机器人仿真 API 服务
提供基于 MuJoCo 的机器人仿真控制接口
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi import responses as fastapi_responses
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 导入仿真模块
from simulation import get_simulation_instance, SimState

# 兼容性处理：保留原有 UR_Robot 相关代码（可选）
try:
    from UR_Robot import UR_Robot
except ImportError:
    UR_Robot = None

app = FastAPI(
    title="UR5 Robot Simulation API",
    description="基于 MuJoCo 的 UR5 机器人实时仿真服务",
    version="1.0.0"
)

# 添加 CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局仿真实例
simulation = get_simulation_instance()


# ===== Pydantic 数据模型 =====

class SimulationState(BaseModel):
    """仿真状态响应模型"""
    timestamp: float = Field(..., description="时间戳")
    qpos: List[float] = Field(..., description="关节位置 (rad)")
    qvel: List[float] = Field(..., description="关节速度 (rad/s)")
    ctrl: List[float] = Field(..., description="控制信号")
    ee_pose: Dict[str, List[float]] = Field(..., description="末端执行器位姿")
    sensor_data: Optional[Dict[str, Any]] = Field(None, description="传感器数据")


class SimulationStepRequest(BaseModel):
    """仿真步进请求模型"""
    target_positions: List[float] = Field(..., description="目标关节位置 (rad)", min_items=1, max_items=6)
    n_steps: int = Field(1, description="步进次数", ge=1, le=1000)
    kp: Optional[List[float]] = Field(None, description="比例增益", min_items=1, max_items=6)
    kd: Optional[List[float]] = Field(None, description="微分增益", min_items=1, max_items=6)
    control_mode: str = Field("position", description="控制模式: position/velocity/torque")


class SimulationResetRequest(BaseModel):
    """仿真重置请求模型"""
    model_path: Optional[str] = Field(None, description="模型文件路径，不指定则使用默认模型")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    timestamp: float = Field(default_factory=time.time, description="错误发生时间")


# ===== 仿真 API 端点 =====

@app.post("/sim/reset/",
          summary="重置仿真状态",
          response_model=Dict[str, Any])
async def reset_simulation(request: SimulationResetRequest = SimulationResetRequest()):
    """
    重置仿真状态到初始配置

    - **model_path**: 可选的模型文件路径，用于切换模型
    """
    try:
        # 如果指定了模型路径，先加载模型
        if request.model_path:
            load_success = simulation.load_model(request.model_path)
            if not load_success:
                raise HTTPException(
                    status_code=400,
                    detail=f"模型加载失败: {request.model_path}"
                )

        # 重置仿真
        reset_success = simulation.reset_simulation()
        if not reset_success:
            raise HTTPException(
                status_code=500,
                detail="仿真重置失败"
            )

        # 获取重置后的状态
        state = simulation.get_current_state()
        if not state:
            raise HTTPException(
                status_code=500,
                detail="无法获取仿真状态"
            )

        return {
            "status": "success",
            "message": "仿真已重置",
            "state": state.__dict__,
            "timestamp": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"重置仿真时发生错误: {str(e)}"
        )


@app.post("/sim/step/",
          summary="执行控制步进",
          response_model=Dict[str, Any])
async def step_simulation(request: SimulationStepRequest):
    """
    执行机器人控制步进

    - **target_positions**: 目标关节位置 (弧度)
    - **n_steps**: 步进次数 (1-1000)
    - **kp**: 可选的比例增益
    - **kd**: 可选的微分增益
    - **control_mode**: 控制模式 (position/velocity/torque)
    """
    try:
        # 执行仿真步进
        step_success = simulation.step_simulation(
            target_positions=request.target_positions,
            n_steps=request.n_steps,
            kp=request.kp,
            kd=request.kd,
            control_mode=request.control_mode
        )

        if not step_success:
            raise HTTPException(
                status_code=500,
                detail="仿真步进执行失败"
            )

        # 获取执行后的状态
        state = simulation.get_current_state()
        if not state:
            raise HTTPException(
                status_code=500,
                detail="无法获取仿真状态"
            )

        return {
            "status": "success",
            "message": f"成功执行 {request.n_steps} 步控制",
            "state": state.__dict__,
            "request": request.__dict__,
            "timestamp": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"执行控制步进时发生错误: {str(e)}"
        )


@app.get("/sim/state/",
         summary="获取当前状态",
         response_model=SimulationState)
async def get_simulation_state():
    """
    获取当前的仿真状态

    返回包含关节位置、速度、控制信号和末端执行器位姿的完整状态信息
    """
    try:
        state = simulation.get_current_state()
        if not state:
            raise HTTPException(
                status_code=503,
                detail="仿真未初始化或模型未加载"
            )

        return SimulationState(**state.__dict__)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取仿真状态时发生错误: {str(e)}"
        )


# ===== 相机渲染 API 端点 =====

@app.get("/sim/camera.jpg",
         summary="获取相机 JPEG 图像",
         response_class=fastapi.responses.Response)
async def get_camera_jpeg(
    camera: str = "camera1",
    width: int = fastapi.Query(640, description="图像宽度", ge=160, le=1920),
    height: int = fastapi.Query(480, description="图像高度", ge=120, le=1080),
    quality: int = fastapi.Query(80, description="JPEG 质量", ge=1, le=100)
):
    """
    获取相机渲染的 JPEG 图像

    - **camera**: 相机名称 (默认: camera1)
    - **width**: 图像宽度 (160-1920)
    - **height**: 图像高度 (120-1080)
    - **quality**: JPEG 质量 (1-100)
    """
    try:
        # 提交相机渲染请求到队列
        future = simulation.submit_request(
            "get_image",
            camera_name=camera,
            width=width,
            height=height,
            format="jpeg",
            quality=quality
        )

        # 等待结果（带超时）
        image_data = await asyncio.wait_for(asyncio.wrap_future(future), timeout=5.0)

        if image_data is None:
            raise HTTPException(
                status_code=500,
                detail="相机渲染失败或相机不存在"
            )

        # 返回图像响应
        return fastapi.responses.Response(
            content=image_data,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache"}
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="相机渲染请求超时"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取相机图像时发生错误: {str(e)}"
        )


@app.get("/sim/camera.png",
         summary="获取相机 PNG 图像",
         response_class=fastapi.responses.Response)
async def get_camera_png(
    camera: str = "camera1",
    width: int = fastapi.Query(640, description="图像宽度", ge=160, le=1920),
    height: int = fastapi.Query(480, description="图像高度", ge=120, le=1080)
):
    """
    获取相机渲染的 PNG 图像

    - **camera**: 相机名称 (默认: camera1)
    - **width**: 图像宽度 (160-1920)
    - **height**: 图像高度 (120-1080)
    """
    try:
        # 提交相机渲染请求到队列
        future = simulation.submit_request(
            "get_image",
            camera_name=camera,
            width=width,
            height=height,
            format="png"
        )

        # 等待结果（带超时）
        image_data = await asyncio.wait_for(asyncio.wrap_future(future), timeout=5.0)

        if image_data is None:
            raise HTTPException(
                status_code=500,
                detail="相机渲染失败或相机不存在"
            )

        # 返回图像响应
        return fastapi.responses.Response(
            content=image_data,
            media_type="image/png",
            headers={"Cache-Control": "no-cache"}
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="相机渲染请求超时"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取相机图像时发生错误: {str(e)}"
        )


@app.get("/sim/camera.json",
         summary="获取相机图像 (Base64)")
async def get_camera_base64(
    camera: str = "camera1",
    width: int = fastapi.Query(640, description="图像宽度", ge=160, le=1920),
    height: int = fastapi.Query(480, description="图像高度", ge=120, le=1080),
    quality: int = fastapi.Query(80, description="JPEG 质量", ge=1, le=100),
    format: str = fastapi.Query("jpeg", description="图像格式", regex="^(jpeg|png)$")
):
    """
    获取相机图像的 Base64 编码

    - **camera**: 相机名称 (默认: camera1)
    - **width**: 图像宽度 (160-1920)
    - **height**: 图像高度 (120-1080)
    - **quality**: JPEG 质量 (1-100，仅 JPEG 格式)
    - **format**: 图像格式 (jpeg/png)
    """
    try:
        # 提交相机渲染请求到队列
        future = simulation.submit_request(
            "get_image",
            camera_name=camera,
            width=width,
            height=height,
            format="base64",
            quality=quality
        )

        # 等待结果（带超时）
        image_data = await asyncio.wait_for(asyncio.wrap_future(future), timeout=5.0)

        if image_data is None:
            raise HTTPException(
                status_code=500,
                detail="相机渲染失败或相机不存在"
            )

        # 解码 base64 并返回
        try:
            base64_string = image_data.decode('ascii')
        except:
            base64_string = base64.b64encode(image_data).decode('ascii')

        return {
            "camera": camera,
            "width": width,
            "height": height,
            "format": format,
            "quality": quality if format == "jpeg" else None,
            "image_base64": base64_string,
            "timestamp": time.time()
        }

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="相机渲染请求超时"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取相机图像时发生错误: {str(e)}"
        )


@app.get("/sim/cameras/",
         summary="列出可用相机")
async def list_available_cameras():
    """
    获取所有可用相机的列表
    """
    try:
        # 提交相机列表请求到队列
        future = simulation.submit_request("list_cameras")
        cameras = await asyncio.wait_for(asyncio.wrap_future(future), timeout=2.0)

        return {
            "cameras": cameras,
            "count": len(cameras),
            "timestamp": time.time()
        }

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="获取相机列表请求超时"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取相机列表时发生错误: {str(e)}"
        )


# ===== 兼容性 API 端点 (保留原有功能) =====

class InputData(BaseModel):
    """原有输入数据模型 (兼容性保留)"""
    text: str


@app.post("/submit/")
def submit_data(data: InputData):
    """原有数据提交接口 (兼容性保留)"""
    return {"received_text": data.text}


@app.get("/")
def read_root():
    """根路径 - API 信息"""
    return {
        "message": "UR5 Robot Simulation API",
        "version": "1.0.0",
        "endpoints": {
            "simulation": {
                "POST /sim/reset/": "重置仿真状态",
                "POST /sim/step/": "执行控制步进",
                "GET /sim/state/": "获取当前状态"
            },
            "legacy": {
                "POST /submit/": "数据提交 (兼容)",
                "GET /data/": "获取数据 (兼容)"
            }
        },
        "status": "running"
    }


# ===== 废弃的兼容性函数 (保留但标记为废弃) =====

def mytest():
    """废弃: 仅为兼容性保留"""
    test_angle = [33.23733291649368, -101.63522656787138, 92.0165543852219,
                  -81.27484246341358, -89.61791853458415, 254.20671818996493]
    return test_angle


def myget():
    """废弃: 仅为兼容性保留"""
    if UR_Robot:
        ur_robot = UR_Robot()
        angels = ur_robot.mytest()
        return angels
    else:
        return mytest()


@app.get("/data/")
def get_data():
    """废弃: 获取数据的兼容性接口"""
    value = myget()
    return {"value": value, "deprecated": True, "use": "/sim/state/"}


# ===== 健康检查端点 =====

@app.get("/health/")
def health_check():
    """健康检查接口"""
    try:
        # 检查仿真状态
        state = simulation.get_current_state()

        return {
            "status": "healthy",
            "simulation_loaded": state is not None,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }


@app.get("/sim/queue/status/")
def get_queue_status():
    """获取请求队列状态（调试用）"""
    try:
        # 注意：这里直接访问队列状态，不使用请求队列
        # 因为这是监控接口，不应该被队列本身阻塞
        queue_size = simulation._request_queue.qsize()
        is_processing = simulation._processing_request
        active_connections = len(manager.active_connections)

        return {
            "queue_size": queue_size,
            "max_queue_size": simulation._request_queue.maxsize,
            "is_processing": is_processing,
            "active_connections": active_connections,
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": time.time()
        }


# ===== 启动和关闭事件 =====

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    print("UR5 仿真 API 服务关闭中...")
    try:
        simulation.stop_realtime_simulation()
        print("✓ 仿真服务已停止")
    except Exception as e:
        print(f"⚠ 仿真服务停止时出错: {e}")


# ===== WebSocket 连接管理器 =====

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ws-sim")

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket 客户端连接建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"WebSocket 客户端连接断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"广播消息失败: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"发送个人消息失败: {e}")
            self.disconnect(websocket)


# 全局连接管理器实例
manager = ConnectionManager()


# ===== WebSocket 端点 =====

@app.websocket("/sim/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时通信端点

    支持功能：
    - 实时状态推送 (50-100Hz)
    - 控制命令接收和处理
    - 多客户端并发连接
    """
    await manager.connect(websocket)

    # 启动状态推送任务
    push_task = None
    try:
        # 发送欢迎消息
        await manager.send_personal_message({
            "type": "welcome",
            "message": "连接到 UR5 仿真服务",
            "timestamp": time.time(),
            "supported_commands": [
                "control",
                "reset",
                "get_state",
                "ping"
            ]
        }, websocket)

        # 启动状态推送循环
        push_task = asyncio.create_task(state_push_loop(websocket))

        # 主消息处理循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)

                # 处理消息
                response = await handle_websocket_message(message)

                # 发送响应
                if response:
                    await manager.send_personal_message(response, websocket)

            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "error": "invalid_json",
                    "message": "无效的 JSON 格式",
                    "timestamp": time.time()
                }, websocket)

            except WebSocketDisconnect:
                break

            except Exception as e:
                print(f"WebSocket 消息处理错误: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "error": "internal_error",
                    "message": f"内部错误: {str(e)}",
                    "timestamp": time.time()
                }, websocket)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket 连接错误: {e}")
    finally:
        # 清理任务
        if push_task:
            push_task.cancel()
            try:
                await push_task
            except asyncio.CancelledError:
                pass

        # 断开连接
        manager.disconnect(websocket)


async def state_push_loop(websocket: WebSocket):
    """状态推送循环 (50-100Hz)"""
    push_interval = 1.0 / 60.0  # 60Hz 默认

    while True:
        try:
            # 获取当前状态
            state = await asyncio.get_event_loop().run_in_executor(
                manager.executor,
                simulation.get_current_state
            )

            if state:
                # 发送状态更新
                await manager.send_personal_message({
                    "type": "state_update",
                    "timestamp": time.time(),
                    "data": state.__dict__
                }, websocket)

            # 等待下一帧
            await asyncio.sleep(push_interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"状态推送错误: {e}")
            await asyncio.sleep(1.0)  # 出错时降低频率


async def handle_websocket_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    处理 WebSocket 消息

    支持的消息类型：
    - control: 执行控制命令
    - reset: 重置仿真
    - get_state: 获取当前状态
    - ping: 心跳检测
    """
    msg_type = message.get("type", "")
    timestamp = time.time()

    try:
        if msg_type == "control":
            # 控制命令
            return await handle_control_command(message, timestamp)

        elif msg_type == "reset":
            # 重置命令
            return await handle_reset_command(message, timestamp)

        elif msg_type == "get_state":
            # 获取状态
            return await handle_get_state_command(timestamp)

        elif msg_type == "ping":
            # 心跳
            return {
                "type": "pong",
                "timestamp": timestamp,
                "echo": message.get("data")
            }

        else:
            return {
                "type": "error",
                "error": "unknown_command",
                "message": f"未知命令类型: {msg_type}",
                "timestamp": timestamp
            }

    except Exception as e:
        return {
            "type": "error",
            "error": "command_failed",
            "message": f"命令执行失败: {str(e)}",
            "timestamp": timestamp
        }


async def handle_control_command(message: Dict[str, Any], timestamp: float) -> Dict[str, Any]:
    """处理控制命令"""
    data = message.get("data", {})

    # 验证必需参数
    if "target_positions" not in data:
        return {
            "type": "error",
            "error": "missing_parameter",
            "message": "缺少必需参数: target_positions",
            "timestamp": timestamp
        }

    # 提交控制请求到队列
    try:
        future = simulation.submit_request(
            "control",
            target_positions=data["target_positions"],
            n_steps=data.get("n_steps", 1),
            kp=data.get("kp"),
            kd=data.get("kd"),
            control_mode=data.get("control_mode", "position")
        )

        # 等待结果（带超时）
        success = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)

        if success:
            return {
                "type": "control_result",
                "status": "success",
                "message": "控制命令执行成功",
                "timestamp": timestamp
            }
        else:
            return {
                "type": "control_result",
                "status": "failed",
                "message": "控制命令执行失败",
                "timestamp": timestamp
            }

    except asyncio.TimeoutError:
        return {
            "type": "error",
            "error": "timeout",
            "message": "控制命令执行超时",
            "timestamp": timestamp
        }
    except Exception as e:
        return {
            "type": "error",
            "error": "control_failed",
            "message": f"控制执行失败: {str(e)}",
            "timestamp": timestamp
        }


async def handle_reset_command(message: Dict[str, Any], timestamp: float) -> Dict[str, Any]:
    """处理重置命令"""
    data = message.get("data", {})

    try:
        # 如果指定了模型路径，先加载模型
        model_path = data.get("model_path")
        if model_path:
            future = simulation.submit_request("load_model", model_path=model_path)
            load_success = await asyncio.wait_for(asyncio.wrap_future(future), timeout=30.0)
            if not load_success:
                return {
                    "type": "reset_result",
                    "status": "failed",
                    "message": f"模型加载失败: {model_path}",
                    "timestamp": timestamp
                }

        # 重置仿真
        future = simulation.submit_request("reset")
        reset_success = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)

        if reset_success:
            return {
                "type": "reset_result",
                "status": "success",
                "message": "仿真重置成功",
                "timestamp": timestamp
            }
        else:
            return {
                "type": "reset_result",
                "status": "failed",
                "message": "仿真重置失败",
                "timestamp": timestamp
            }

    except asyncio.TimeoutError:
        return {
            "type": "error",
            "error": "timeout",
            "message": "重置命令执行超时",
            "timestamp": timestamp
        }
    except Exception as e:
        return {
            "type": "error",
            "error": "reset_failed",
            "message": f"重置失败: {str(e)}",
            "timestamp": timestamp
        }


async def handle_get_state_command(timestamp: float) -> Dict[str, Any]:
    """处理获取状态命令"""
    try:
        state = await asyncio.get_event_loop().run_in_executor(
            manager.executor,
            simulation.get_current_state
        )

        if state:
            return {
                "type": "state_response",
                "timestamp": timestamp,
                "data": state.__dict__
            }
        else:
            return {
                "type": "error",
                "error": "no_state",
                "message": "无法获取仿真状态",
                "timestamp": timestamp
            }

    except Exception as e:
        return {
            "type": "error",
            "error": "state_fetch_failed",
            "message": f"获取状态失败: {str(e)}",
            "timestamp": timestamp
        }


# ===== WebSocket 广播状态推送 =====

async def broadcast_state_updates():
    """定期广播状态更新给所有连接的客户端"""
    while True:
        try:
            # 获取当前状态
            state = await asyncio.get_event_loop().run_in_executor(
                manager.executor,
                simulation.get_current_state
            )

            if state and manager.active_connections:
                # 广播状态更新
                await manager.broadcast({
                    "type": "state_broadcast",
                    "timestamp": time.time(),
                    "data": state.__dict__
                })

            # 每秒广播一次
            await asyncio.sleep(1.0)

        except Exception as e:
            print(f"状态广播错误: {e}")
            await asyncio.sleep(5.0)  # 出错时等待更长时间


# 在应用启动时启动广播任务
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    print("UR5 仿真 API 服务启动中...")

    # 尝试加载默认模型
    try:
        success = simulation.load_model()
        if success:
            print("✓ 默认模型加载成功")
            reset_success = simulation.reset_simulation()
            if reset_success:
                print("✓ 仿真初始化完成")
            else:
                print("⚠ 仿真重置失败")
        else:
            print("⚠ 默认模型加载失败，请通过 API 手动加载")
    except Exception as e:
        print(f"⚠ 启动时模型加载失败: {e}")

    # 启动状态广播任务
    asyncio.create_task(broadcast_state_updates())

    print("UR5 仿真 API 服务已就绪")
