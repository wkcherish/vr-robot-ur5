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
- 周期状态广播：`motion_broadcast` 默认 30Hz，`state_broadcast` 默认 6Hz；可用
  `STATE_BROADCAST_HZ` / `STATUS_BROADCAST_HZ` 覆盖。
- 兼容接口：`GET /data/`

## 里程碑 C 新增内容

- MuJoCo 场景文件：
  - `backend/mujoco_models/environment.xml`
  - `backend/mujoco_models/ur5.xml`
  - `backend/mujoco_models/rack.xml`
- 场景 mesh 目录：
  - `backend/mujoco_models/meshes/`
- `SimulationCore` 默认加载 `environment.xml`，并从 MuJoCo 实时回传：
  - `qpos` / `qvel`
  - `ee_pose`
  - `control_ee_pose`
  - `gripper_opening` / `gripper_joints`
  - `objects`

说明：

- `ee_pose` 保持为 MuJoCo 工具坐标系下的真实末端位姿，用于场景/相机等严格对齐。
- `control_ee_pose` 为 VR 遥操作使用的抓取中心位姿，默认取夹爪两指中点，用于让末端跟手/手柄更贴合。
- MuJoCo 深度渲染默认使用 `SIM_MUJOCO_DEPTH_MAP=zeronear` 兼容模式，避免 macOS/OpenGL 缺少 `ARB_clip_control` 时反复输出 reverse-Z 警告；支持该扩展的环境可改为 `zerofar`。
- 抓取默认走 MuJoCo 真实接触/摩擦，不做工具吸附或绑定；旧抓取辅助仅作为调试开关保留，可显式设置 `SIM_GRASP_ASSIST_MODE=strict`。
- 工具和工具箱的 MuJoCo 实体特征由 box/capsule 等简化碰撞代理负责；STL mesh 只做视觉外观，避免前后端对照时出现穿模或高复杂度 mesh 干涉。

- 后端仍以 `shared/scene_manifest.json` 作为场景位姿与 home 基线来源。

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

### Quest3 HTTPS/WSS 推荐启动方式

Quest3 若通过 `https://` 访问前端，后端也应使用 `https://`，WebSocket 需使用 `wss://`，避免混合内容被浏览器拦截。

```bash
uvicorn backend.api_app:app --host 0.0.0.0 --port 8000 \
  --ssl-certfile <path/to/cert.pem> \
  --ssl-keyfile <path/to/key.pem>
```

也可以用统一入口：

```bash
python backend/main.py --host 0.0.0.0 --port 8000 \
  --ssl-certfile <path/to/cert.pem> \
  --ssl-keyfile <path/to/key.pem>
```

统一入口 `backend/main.py` 会在 `--port` 被占用时自动寻找可用端口，并把实际监听地址写入 `shared/runtime/backend-dev.json`。
前端开发代理会优先读取这份文件；如果前端已经在运行，需要重启一次 `npm run dev` 才会切到新的后端端口。

如果你使用环境变量，可参考 `backend/.env.example`。

## 打开 MuJoCo 可视化界面

在仓库根目录执行：

```bash
python backend/main.py
```

行为说明：

- 脚本会先启动 FastAPI 后端（等价于开发命令 `uvicorn backend.api_app:app --app-dir .. --reload --host 0.0.0.0 --port 8000`）。
- 若 `8000` 已被占用，脚本会自动回退到可用端口并在终端打印最终端口。
- 后端健康检查通过后，终端会提示 `yes/no`：是否加载 MuJoCo 仿真窗口。
- 后端会持续运行，按 `Ctrl+C` 停止。

可选参数：

```bash
python backend/main.py --open-viewer ask --model backend/mujoco_models/environment.xml
python backend/main.py --open-viewer no
```

为 Quest3 采集优化后的默认值：

- 后端默认不启用 `uvicorn --reload`，减少额外 Python 进程和文件监听开销；开发时可显式加 `--reload`。
- MuJoCo viewer 默认 30 FPS；视觉调试时可加 `--fps 60`。
- viewer 默认不打开单独 D405 预览窗口；需要检查相机画面时加 `--camera-preview-window yes`。
- viewer 在 Quest3 手势/手柄实时控制时只同步后端状态，不再重复跑本地 MuJoCo 物理，避免与后端仿真抢 CPU。

macOS 上 MuJoCo viewer 需要 `mjpython`。当前启动器会在需要打开 viewer 时自动切换到同一 Conda 环境里的 `mjpython`；也可以手动执行 `mjpython backend/main.py --open-viewer yes`。

Wayland 环境提示：

- 若系统为 Wayland 且同时可用 X11（`DISPLAY` 存在），`backend/main.py` 会默认将 viewer 切到 X11 GLFW 后端，减少 `libdecor-gtk` 相关警告。
- 若你需要强制 Wayland，可手动设置 `PYGLFW_LIBRARY_VARIANT=wayland` 后再启动。

## WebSocket 协议（首版）

- 客户端 -> 服务端：
  - `ping`
  - `get_state`
  - `control`
  - `reset`
  - `execute_task`
  - `stop_task`
  - `control.data.target_ee_pose`
  - `control.data.target_ee_delta`
  - `control.data.expect_result`
  - `control.data.normalized_input.orientation_follow_enabled`: 为 `1` 时 Cartesian servo 同时跟随末端姿态；为 `0` 时仅做位置跟随/姿态锁定。
- 服务端 -> 客户端：
  - `welcome`
  - `state_update`
  - `state_broadcast`
  - `control_result`
  - `reset_result`
  - `task_result`
  - `error`
