# Backend (Milestone C)

本目录已从里程碑 B 的骨架升级到里程碑 C 的 MuJoCo 场景落地版本。

## 当前能力

- FastAPI 服务入口：`backend/api_app.py`
- 统一启动入口（后端 + 可选 MuJoCo viewer）：`backend/main.py`
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

## 里程碑 C 新增内容

- MuJoCo 场景文件：
  - `backend/mujoco_models/environment.xml`
  - `backend/mujoco_models/ur5.xml`
  - `backend/mujoco_models/rack.xml`
  - `backend/mujoco_models/battery_pack.xml`
  - `backend/mujoco_models/camera_base.xml`
  - `backend/mujoco_models/camera.xml`
- 场景 mesh 目录：
  - `backend/mujoco_models/meshes/`
- `SimulationCore` 默认加载 `environment.xml`，并从 MuJoCo 实时回传：
  - `qpos` / `qvel`
  - `ee_pose`
  - `gripper_opening` / `gripper_joints`
  - `objects`

说明：

- 后端仍以 `shared/scene_manifest.json` 作为场景位姿与 home 基线来源。
- `battery_pack` 网格已在后端模型目录做降采样，以满足 MuJoCo 面片数量限制。

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
uvicorn backend.api_app:app --reload --host 0.0.0.0 --port 8000
```

如果你使用环境变量，可参考 `backend/.env.example`。

## 打开 MuJoCo 可视化界面

在仓库根目录执行：

```bash
python backend/main.py
```

行为说明：

- 脚本会先启动 FastAPI 后端（等价于开发命令 `uvicorn backend.api_app:app --app-dir .. --reload --host 0.0.0.0 --port 8000`）。
- 后端健康检查通过后，终端会提示 `yes/no`：是否加载 MuJoCo 仿真窗口。
- 后端会持续运行，按 `Ctrl+C` 停止。

可选参数：

```bash
python backend/main.py --open-viewer ask --model backend/mujoco_models/environment.xml --fps 60
python backend/main.py --open-viewer no --no-reload
```

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

## Milestone C Verification

- Gripper contact stability tuning is applied in `backend/mujoco_models/ur5.xml`:
  - decoupled visual meshes and contact geoms for finger pads
  - higher joint damping/frictionloss on Robotiq linkage
  - dedicated pad collision friction/solver settings for more stable pinch contact
- Scene alignment verification script:
  - `python backend/tools/verify_scene_alignment.py`
  - optional JSON report: `python backend/tools/verify_scene_alignment.py --json-out docs/mC_alignment_check.json`
