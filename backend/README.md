# Backend (Milestone B)

本目录是里程碑 B 的后端仿真骨架，目标是先打通可运行服务与协议链路。

## 当前能力

- FastAPI 服务入口：`backend/main.py`
- 协议模型：`backend/schemas.py`
- 仿真核心：`backend/sim/simulation.py`
- 接口：
  - `GET /health/`
  - `GET /sim/state/`
  - `POST /sim/step/`
  - `POST /sim/reset/`
  - `WebSocket /sim/ws`
- 周期状态广播：`state_broadcast`（默认 20Hz）
- 兼容接口：`GET /data/`

说明：

- 目前仿真核心为里程碑 B 的可运行骨架，会读取 `shared/scene_manifest.json`。
- MuJoCo 场景与完整机器人模型落地在里程碑 C 继续实现。

## 安装依赖

在仓库根目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

## 启动

在仓库根目录执行：

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

如果你使用环境变量，可参考 `backend/.env.example`。

## WebSocket 协议（首版）

- 客户端 -> 服务端：
  - `ping`
  - `get_state`
  - `control`
  - `reset`
  - `execute_task`
  - `stop_task`
- 服务端 -> 客户端：
  - `welcome`
  - `state_update`
  - `state_broadcast`
  - `control_result`
  - `reset_result`
  - `task_result`
  - `error`
