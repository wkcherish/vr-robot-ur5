# vr-robot-ur5

基于 MuJoCo + FastAPI + Vue 3 + WebXR 的 UR5 数字孪生与 Quest3 VR 控制项目。支持桌面端调试与 Quest3 局域网访问，进入 VR 后可通过手柄或手势连续控制机械臂与夹爪。

## 项目结构

```text
ar-ur5-rl/
├── backend/               # FastAPI + MuJoCo 仿真与接口
├── frontend/              # Vue + Three.js + WebXR 前端
├── shared/                # 场景与协议共享配置
├── docs/                  # 设计/修复文档
├── pic/                   # 截图素材
└── README.md
```

## 环境要求

- Python 3.10+
- Anaconda / Miniconda
- Node.js 18+（建议 20 LTS）
- npm 9+
- Quest3（与开发机同一局域网，建议 5GHz Wi-Fi）

## 快速开始

### 1. 使用 Conda 创建后端环境

在仓库根目录执行：

```bash
conda create -n ar-ur5-rl python=3.10 -y
conda activate ar-ur5-rl
pip install -r backend/requirements.txt
```

### 2. 启动后端（按当前约定）

```bash
cd backend
python ./main.py
```

默认监听 `0.0.0.0:8000`，并启动 FastAPI 服务。
如果 `8000` 已被占用，启动器会自动切换到下一个可用端口，并把实际端口写入 `shared/runtime/backend-dev.json` 供前端代理读取。

输入 `yes` 打开 MuJoCo viewer 后，会同时打开一个独立的 `D405 RGB Preview` 窗口。这个窗口可拖动、可按需移到旁边，不会遮挡 MuJoCo 主场景。如果要把 MuJoCo 主视角也切到 D405：

```bash
cd backend
python ./main.py --open-viewer yes --viewer-camera d405_rgb
```

macOS 上 MuJoCo viewer 需要 `mjpython`。当前启动器会在需要打开 viewer 时自动切换到同一 Conda 环境里的 `mjpython`；也可以手动执行 `mjpython ./main.py --open-viewer yes`。

`Sensor` 面板显示的是传感器数值，不是 RGB-D 相机画面。D405 固定相机名称为 `d405_rgb` / `d405_depth`。独立窗口可用 `--camera-preview-window no` 关闭；如需旧的 MuJoCo 内嵌贴图调试，可用 `--viewer-camera-overlay d405_rgb`。训练画面也可从前端 D405 面板或 `/sim/camera/rgb/`、`/sim/camera/depth/` 接口查看。

### 3. 启动前端（按当前约定）

新开终端，回到项目目录后执行：

```bash
cd frontend
npm install
npm run dev
```

前端开发服务默认在 `https://0.0.0.0:5173`（Vite 输出为准）。
若后端刚刚因为端口占用切换过端口，请在后端启动完成后再启动前端；如果前端已经开着，重启一次前端开发服务即可让代理读取新的后端端口。

### 4. Quest3 访问

1. 在终端查看前端局域网地址（示例：`https://192.168.x.x:5173`）
2. 在 Quest3 浏览器打开该地址并信任证书
3. 页面内确认网络检查通过后点击“进入VR模式”

## 控制方式学习

### 手柄模式（Controller）

1. 在 VR 顶部切换到“手柄模式”。
2. 用左手柄选择关节组（按一下或按住都可，浏览器未标记左右手时会自动匹配活动手柄）：
   - `Grip`：腕部组（`wrist_2` / `wrist_3`）
   - `Y`：前臂组（`elbow` / `wrist_1`）
   - `X`：大臂组（`shoulder_pan` / `shoulder_lift`）
3. 用右手摇杆控制当前关节组：
   - 摇杆上下：控制组内第一个关节
   - 摇杆左右：控制组内第二个关节
4. 用右手 `Trigger` 连续控制夹爪开合（按得越深开合越大）。

### 手势模式（Hand Tracking）

1. 在 VR 顶部切换到“手势模式”，等待 HUD 显示左手追踪稳定，并确认能看到左手模型。
2. 左手控制末端执行器：
   - 进入手势模式后，系统会把当前左手位置和当前末端执行器位置绑定为控制原点。
   - 左手向左/右移动，末端执行器跟随横向移动。
   - 左手向上/下移动，末端执行器跟随升降。
   - 左手向前/后移动，末端执行器跟随前后移动。
   - 手移动得越远，末端目标位姿偏移越大；系统会限制单帧最大位移，避免突然跳动。
3. 后端 IK 求解：
   - 前端不再把左手动作映射到某两个关节，而是持续发送 `target_ee_pose` 末端目标位姿。
   - 后端收到 `quest3_hand` 控制包后，用 MuJoCo Jacobian IK 解出 UR5 的 6 个关节角。
   - 求解后的 6 关节目标再进入原有的位置控制、限位和碰撞保护流程。
4. 攥拳抓取：
   - 左手自然张开时，夹爪保持打开。
   - 左手攥拳时，夹爪闭合并尝试抓取工具。
   - 攥拳程度会连续映射到夹爪开合量，不是简单开/关。
   - 松开拳头后，夹爪打开并释放。
5. 控制注意事项：
   - 右手不参与机械臂控制，可自然放下或移出视野。
   - 如果进入模式时末端位置不理想，退出再进入手势模式即可重新绑定左手控制原点。
   - 若 Quest 浏览器没有提供手部骨骼输入，系统会自动使用左控制器作为同一套左侧控制通道。
6. 若出现“看不到手”或追踪不稳定：
   - 保持左手在视野内，避免贴近摄像头或快速甩手
   - 保证环境光线充足
   - 在 Quest 设置中确认已启用 Hand Tracking

## 常见问题

### 1. 无法进入 VR

- 确认在 Quest3 上使用 `https://` 地址访问前端
- 确认浏览器支持并启用了 WebXR
- 确认前端与后端网络连通

### 2. VR 已进入但无法控制

- 先确认已连接 WebSocket
- 检查是否已在 VR 菜单中选择“手柄模式”或“手势模式”
- 手势模式下确认手部追踪稳定

### 3. 感觉有卡顿或指令滞后

- 优先检查局域网质量
- 确保前后端版本一致
- 避免同时用桌面滑条和 VR 输入源抢控制权

## 相关文档

- [backend/README.md](backend/README.md)
- [docs/task.md](docs/task.md)
- [docs/todolist.md](docs/todolist.md)
- [docs/s5_safe_handover_freeze.md](docs/s5_safe_handover_freeze.md)
- [docs/vr_control_and_performance_update_2026-04-24.md](docs/vr_control_and_performance_update_2026-04-24.md)
