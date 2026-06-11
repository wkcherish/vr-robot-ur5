# Quest3 VR 数据采集转 LeRobot 并微调 pi0.5 任务书（2026-06-08 任务回归）

## 1. 文档定位

本文档基于当前仓库已经完成的 UR5 数字孪生、工具场景、前后端实时同步、Quest3 基础控制、末端 D405 规划和 S4.5 物理边界修复继续规划。

2026-06-08 起，当前任务主线回归为：

```text
使用 Quest3 / VR 采集机器人操作示教数据
  -> 将 raw episode 转换为 LeRobot / OpenPI 可读取的数据格式
  -> 使用转换后的数据对 pi0.5 做 LoRA / adapter 微调
  -> 在 MuJoCo 中验证微调策略的抓取、移动和放置/对齐能力
```

此前 `quest3_safe_handover_v1` 中的人机协作交接、人手建模、协作记忆模型和 interaction gating 方向不再作为当前开发任务推进。已经完成的文档冻结、场景基线、VR 控制、D405 和物理边界内容继续保留为历史记录和可复用资产；未完成的协作任务不再进入当前 ToDo 主链路。

---

## 2. 统一目标

当前主任务建议命名为：

```text
quest3_vr_lerobot_pi05_v1
```

已有 `quest3_tool_sorting_v1` 继续作为工具场景、机器人操作和抓取资产基线。它的价值是已经提供了 UR5、工具、工具箱、状态同步、VR 控制和物理边界基础；当前任务在此基础上补齐数据采集、数据格式转换、pi0.5 微调和 MuJoCo 验证闭环。

### 2.1 要解决的问题

当前要解决的问题不是继续扩展协作语义，而是把已有 VR 控制能力转化为可训练的数据资产：

- VR 示教 episode 能否稳定落盘，包含 D405 RGB-D、机器人状态、动作、任务文本和质量标记。
- raw JSONL / 图像文件能否转换成 LeRobot / OpenPI 可读取、可复现的数据集。
- 转换后的数据能否通过 loader smoke test、统计检查和 episode 级 train/val/test 划分。
- pi0.5 是否能在 5090D 32GB 服务器上以 LoRA / adapter 方式完成轻量微调。
- 微调模型是否能回到 MuJoCo 中完成基础抓取、移动、放置或目标对齐 rollout。

因此本项目的核心问题是“从 VR 示教到 pi0.5 微调的数据闭环”。质量控制重点放在观测来源、动作定义、时间对齐、数据转换、训练可复现和仿真验证上。

### 2.2 当前闭环架构

后续系统采用数据闭环架构：

```text
Quest3 / VR 示教
  负责采集人类操作者控制 UR5 + Robotiq 的操作轨迹

raw episode recorder
  负责落盘 D405 RGB-D、机器人状态、动作、事件、metadata 和 validation_summary

LeRobot / OpenPI converter
  负责把 raw episode 转成模型训练能读取的数据集、字段映射和统计报告

pi0.5 LoRA / adapter training
  负责学习抓取、移动、放置/对齐等机器人操作能力

MuJoCo rollout validation
  负责验证 checkpoint 是否能回到当前数字孪生场景执行基础任务
```

本轮不训练 collaboration memory，不新增 human hand，不集成 interaction gating，也不以 release timing / unsafe handover 作为当前评估指标。

---

## 3. 当前已有实验基础

当前仓库已经具备后续 VR 数据采集、LeRobot 转换和 pi0.5 微调验证需要的关键基础，不需要从零开始。

### 3.1 已完成能力

- 已有真实后端服务：`backend/api_app.py`、`backend/sim/simulation.py`、`backend/main.py`。
- 已有 MuJoCo 场景：UR5、Robotiq、桌面、工具箱、扳手、螺丝刀、钳子。
- 已有前后端状态同步：前端可接收后端 `qpos`、夹爪状态和工具对象位姿。
- 已有 `shared/scene_manifest.json` 和 `shared/tool_catalog.json` 作为共享场景基线。
- 已有 Quest3 / VR 基础控制链：手柄模式、手势模式、输入节流、in-flight 控制和超时回收。
- 已完成关节限位双侧裁剪，避免 Quest3 或手动控制越过 UR5 关节物理限位。
- 已完成 S4.5 物理边界修复，解决前后端虚拟干涉和明显穿桌、穿箱、穿工具问题。
- 已有末端 D405 RGB-D 相机方案的基础定义，后续需要用于正式落盘和回放校验。

### 3.2 当前仍未完成

以下内容仍需要围绕当前主线补齐：

- 末端 D405 在 MuJoCo 中的主视觉观测验证、RGB-D 接口和落盘校验。
- VR 数据采集入口：precheck、选择任务模板、开始/停止录制、结果标记和异常提示。
- 单边机器人操作 episode 录制器：记录 RGB-D、机器人状态、动作、控制源、事件、metadata 和校验摘要。
- raw episode 数据协议冻结，明确哪些字段进入 pi0.5 训练，哪些只用于回放和筛选。
- LeRobot / OpenPI 数据转换器、loader smoke test、字段映射和转换报告。
- 数据集 train/val/test 按 episode 划分，禁止按帧随机打散。
- pi0.5 LoRA / adapter 微调配置、训练脚本、checkpoint 入库和离线指标。
- MuJoCo rollout 验证入口，确认微调模型能完成基础工具操作。
- 数据集、模型、配置、相机标定和训练 run 的版本追溯。

以下旧方向当前暂停，不再作为未完成主链路：

- MuJoCo `human hand` 模型与 Quest3 右手控制链路。
- relation feature、interaction phase、collaboration memory。
- interaction gating、release timing、安全交接指标和协作交接对比实验。

---

## 4. 当前场景与任务定义

### 4.1 场景对象

第一版 `quest3_vr_lerobot_pi05_v1` 复用当前工具场景，不新增协作对象：

- `UR5 + Robotiq 2F-85`
- 末端 `Intel RealSense D405 RGB-D`
- 桌面 / 工作台
- 已有工具：`wrench_01`、`screwdriver_01`、`pliers_01`
- 工具箱：作为放置、归位或场景约束对象保留
- `camera / camera_base`：仅作为调试对象，不作为训练主视觉来源

当前 P0 不新增 `human_hand`，不新增双边交接状态机，不把 `handover_zone` 作为协作语义对象。若需要目标区域，可使用普通 `target_zone / place_zone` 表示工具放置或对齐位置。

### 4.2 主任务流程

一个标准数据闭环包含以下阶段：

```text
reset
  -> select_task_and_tool
  -> dataset_precheck
  -> start_vr_episode
  -> robot_grasp
  -> robot_move / robot_place / robot_align
  -> stop_episode
  -> validate_raw_episode
  -> convert_to_lerobot
  -> loader_smoke_test
  -> pi0.5_lora_train
  -> mujoco_rollout_eval
```

当前第一版任务类型建议冻结为：

| task type | 含义 | 是否 P0 |
| --- | --- | --- |
| `tool_grasp` | 从桌面抓取指定工具 | 是 |
| `tool_pick_place` | 抓取工具并放到指定区域或工具箱槽位 | 是 |
| `tool_reposition` | 把工具移动到指定姿态或位置 | 是 |
| `tool_sorting` | 多工具按类别归位，作为后续扩展 | P1 |
| `handover / safe_release` | 人机交接、释放时机、安全 gate | 暂停 |

### 4.3 当前不做的范围

以下内容保留为历史规划，不进入当前主线：

- 人机协作安全交接任务。
- `human_hand` 建模、右手控制和人手状态广播。
- `approach/stabilization/hesitation/retreat/ready/release` 阶段标签。
- relation feature 与 collaboration memory。
- interaction gating 与 release timing 评估。

---

## 5. Quest3 / VR 数据采集控制

### 5.1 控制分工

第一版正式数据采集采用 VR 示教模式，并保留桌面端作为监督和调试面板。

- Quest3 手柄或手势：控制 UR5 / 夹爪，完成抓取、移动、放置和对齐。
- 桌面端：显示 D405、状态、日志、回放和采集质量，不抢占 VR 控制权。
- 程序侧：负责 precheck、reset、状态同步、安全边界检查、录制、校验和回放。

正式训练候选数据应来自操作者 VR 示教。脚本轨迹可以用于 camera smoke test、接口测试、固定姿态检查、回放验证或数据管线测试，但不能混入 `train_candidate`。

### 5.2 VR 采集入口

VR 采集模式需要支持快速启动：

1. 操作者戴上 Quest3 进入 `VR采集模式`。
2. 头显内显示 D405 状态、WebSocket 状态、控制模式、追踪状态和 `recording_ready`。
3. 操作者选择任务模板、目标工具、目标区域和任务文本。
4. 通过 VR 内按钮或手势执行 `start episode`。
5. 操作者控制 UR5 完成抓取、移动、放置或对齐。
6. 通过 VR 内按钮或手势执行 `stop episode`。
7. 头显内快速显示本条结果：成功、失败、人工中止、追踪异常、相机异常或待回放确认。

每条正式 episode 的元数据建议明确记录：

- `operator_controlled=true`
- `control_mode=vr_controller / vr_hand`
- `robot_input_source=quest3_controller / quest3_hand`
- `autonomy_level=manual_demonstration`
- `scripted_collection=false`

### 5.3 状态广播与动作记录

后端状态广播和录制器需要至少覆盖：

```json
{
  "robot_state": {
    "qpos": [0, 0, 0, 0, 0, 0],
    "qvel": [0, 0, 0, 0, 0, 0],
    "ee_pose": [0, 0, 0, 0, 0, 0, 1],
    "gripper_opening": 0.0
  },
  "dataset_state": {
    "episode_id": "episode_000001",
    "task_type": "tool_pick_place",
    "target_tool_id": "wrench_01",
    "recording": true,
    "recording_ready": true,
    "validation_status": "pending"
  }
}
```

---

## 6. 末端 D405 摄像头模块与 MuJoCo 观测验证

训练主视觉观测必须来自机械臂末端安装的 D405 RGB-D 相机。Quest3 页面画面、Three.js 观察相机和场景里的 `camera / camera_base` 只能用于调试或展示，不能作为训练主视觉来源。

这一阶段需要在正式采集前完成。第一轮重点验证夹爪、目标工具、目标放置区域和工具箱是否在末端相机视野内。

这样安排更合理，因为 `pi0.5` 的操作能力训练、回放检查和后续 sim2real 都依赖末端相机视角是否真实可用。如果 D405 在抓取或放置阶段看不到工具、夹爪或目标区域，后续数据即使有状态字段，也不适合作为稳定的视觉-动作训练样本。

### 6.1 摄像头在 MuJoCo 中的角色

D405 在 MuJoCo 中不是一个普通装饰模型，而是训练观测源。它应满足：

- 固定挂载在 UR5 末端或腕部坐标系上，随机械臂运动。
- 输出 `d405_rgb` 和 `d405_depth`。
- RGB 与 Depth 使用同一时间戳或可对齐时间戳。
- 每帧记录相机内参版本、外参版本、mount 名称和相机位姿。
- 视野覆盖夹爪、目标工具、目标放置区域和工具箱关键区域。

### 6.2 MuJoCo 视觉效果验证

在做视觉 smoke test 前，必须先完成真实 D405 内参与 MuJoCo 光轴验证。操作步骤见 [docs/d405_real_intrinsics_validation.md](d405_real_intrinsics_validation.md)。不能只用 `principalpixel="0 0"` 强制居中来替代真实 `ppx/ppy`；真实 D405 的 `fx/fy/ppx/ppy` 需要通过 `pyrealsense2` 读取并写回 MuJoCo 配置。

正式录制前必须在 MuJoCo 中做视觉 smoke test，至少覆盖以下场景：

| 场景 | 检查目标 |
| --- | --- |
| `reset_view` | D405 能看到桌面主要工作区和至少一个目标工具 |
| `robot_approach` | 机械臂接近工具时夹爪和目标工具可见 |
| `robot_grasp` | 抓取闭合前后夹爪、工具和接触区域可见 |
| `robot_lift` | 工具离桌后仍在视野内，无遮挡或严重裁切 |
| `robot_place` | 放置到目标区或工具箱附近时，目标区域和工具可见 |
| `failure_cases` | 抓取失败、工具掉落或遮挡时能在回放中定位原因 |

如果 D405 在某些阶段持续看不到工具或夹爪，不能直接进入批量采集，应先调整工具初始区、目标区、机械臂姿态或相机挂载角度。

### 6.3 RGB-D 输出接口要求

后端需要提供或验证以下接口：

- `GET /sim/observation/`：返回当前训练观测摘要。
- `GET /sim/camera/rgb/`：返回 D405 RGB 图像。
- `GET /sim/camera/depth/`：返回 D405 Depth 图像。
- WebSocket 状态中包含最近一帧 `d405_frame_id`、时间戳、有效性和错误原因。
- 录制器写入 `visuals.jsonl`，关联 RGB 路径、Depth 路径、时间戳、相机位姿和有效性。

Depth 必须使用无损格式保存，不能用 JPG 或普通 MP4 帧作为训练主深度数据。MP4 只能作为快速预览。

### 6.4 前端观测面板

前端需要一个 D405 观测面板，用于采集前和回放时检查：

- 当前 RGB 画面。
- 当前 Depth 原图或伪彩显示。
- 帧号、时间戳、帧率和最近错误。
- `camera_capture_ok`、`rgb_valid`、`depth_valid`、`frame_aligned`。
- 当前是否为 D405，而不是 Quest3 页面画面或 Three.js 外部相机。

这个面板是采集质量控制的一部分，不是装饰 UI。采集者应能在开始录制前确认末端相机确实看到操作关键区域。

### 6.5 摄像头验证通过条件

D405 阶段通过后，至少应满足：

- `d405_rgb` 和 `d405_depth` 在 MuJoCo 中稳定输出。
- RGB 和 Depth 帧可落盘，并能通过 `visuals.jsonl` 回溯。
- camera-only smoke test 中，夹爪、目标工具和目标放置区域大部分时间可见。
- Depth 不出现全零、全 NaN、严重错位或明显尺度错误。
- 每条 episode 的 `validation_summary.json` 能报告 D405 观测是否可用于训练。
- 训练数据中明确禁止使用 Quest3 页面画面、Three.js 外部观察相机或 stub 图像替代 D405。

---

## 7. 数据采集设计

### 7.1 数据集目录

建议创建：

```text
data/
  datasets/
    quest3_vr_lerobot_pi05_v1/
      raw/
      lerobot/
      splits/
      reports/
      previews/
models/
  pi05/
    quest3_vr_lora_runs/
  registry/
experiments/
  pi05_vr_tools/
logs/
  train/
  eval/
```

### 7.2 episode 必须保存的内容

每条 raw episode 必须保存：

- `metadata.json`
- `visuals.jsonl`
- `states.jsonl`
- `actions.jsonl`
- `events.jsonl`
- `result.json`
- `validation_summary.json`
- 可选 `videos/` 预览文件

训练主数据必须以逐帧 RGB/Depth 和 JSONL 索引为准，视频只用于快速检查和结果展示。

### 7.3 原始状态字段

`states.jsonl` 至少包含：

- 机器人：`qpos`、`qvel`、`ee_pose`、`gripper_opening`、`grasp_state`、`attached_tool_id`
- 工具：`tool_pose`、`tool_velocity`、`tool_attached`、`tool_dropped`、`tool_in_target_zone`
- 视觉：`d405_rgb`、`d405_depth`、`frame_id`、`timestamp`、`frame_aligned`
- 场景：`target_zone_id`、`toolbox_pose`、`reset_seed`
- 安全与质量：`collision_warning`、`workspace_limit_hit`、`tracking_warning`、`operator_abort`

### 7.4 动作字段

`actions.jsonl` 至少包含：

| 字段 | 含义 |
| --- | --- |
| `timestamp` | 动作发送或采样时间 |
| `source` | `quest3_controller / quest3_hand / desktop_manual / script_test / policy` |
| `control_mode` | 当前控制模式 |
| `joint_target` | 6 轴目标关节角，可选 |
| `joint_delta` | 6 轴增量动作，pi0.5 第一版推荐训练动作 |
| `gripper_target` | 夹爪目标开合量 |
| `raw_input` | Quest3 原始输入摘要，用于回放和调试 |
| `valid_for_training` | 是否可进入训练动作序列 |

动作空间第一版建议使用：

```text
action = [joint_delta[0:6], gripper_target]
observation.state = [qpos[0:6], gripper_opening]
```

### 7.5 数据采集类型

第一版必须采集以下操作类型：

1. `tool_grasp`：目标工具抓取。
2. `tool_pick_place`：抓取后移动到目标区域或工具箱槽位。
3. `tool_reposition`：把工具调整到指定位置或姿态。
4. `failed_attempt`：抓取失败、滑落、误碰等调试样本，默认不进入训练，可用于筛选规则。

每种工具至少覆盖 `wrench_01`、`screwdriver_01`、`pliers_01`。第一版不要求加入人手接收、犹豫、后撤或安全 release 负样本。

### 7.6 单条 episode 的采集操作流程

开始一条 episode 前，先完成以下检查：

1. 启动后端和前端，确认 WebSocket 已连接。
2. 确认 MuJoCo 场景已加载 UR5、工具、工具箱和 D405。
3. 执行 reset，确认工具在桌面上、无遮挡、无明显穿模。
4. 确认 `d405_rgb`、`d405_depth` 可用，且不是 stub / fallback 图像。
5. 打开 D405 观测面板，确认夹爪、目标工具和目标区域在末端相机视野内。
6. 确认 Quest3 当前控制模式可用，追踪或手柄输入状态正常。
7. 进入 Quest3 `VR采集模式`，确认头显内能看到采集状态、阶段模板和开始/停止入口。
8. 在 VR 采集面板选择 `task_type`、目标工具、`target_zone_id` 和 `instruction_text`。
9. 运行 `/dataset/precheck/` 或等效检查，只有 `recording_ready=true` 时才能进入正式录制；否则只能进入 `debug_trial`。

录制时按固定流程：

1. 操作者在 VR 采集模式中点击开始录制，冻结本条 episode 的 metadata、工具类别、任务文本和 reset seed。
2. 控制 UR5 接近目标工具，夹爪闭合并抓取工具。
3. 根据任务模板移动工具到目标区域、工具箱槽位或指定姿态。
4. 完成放置、保持或撤离动作。
5. 操作者在 VR 中停止录制。
6. 系统写入 `result.json` 和 `validation_summary.json`。
7. 根据自动校验和人工回放，将 episode 标记为 `train_candidate / eval_candidate / debug_trial / rejected`。

### 7.7 采集后的验证与筛选流程

每条 episode 结束后都必须经过自动校验和人工回放检查。不能只因为文件成功保存就进入训练集。

`validation_summary.json` 至少应包含以下检查：

| 检查项 | 通过条件 |
| --- | --- |
| `files_complete` | metadata、visuals、states、actions、events、result 都存在 |
| `camera_capture_ok` | RGB 和 Depth 均来自 D405，且无 stub / fallback |
| `camera_view_ok` | D405 视野中能看到工具、夹爪和目标区域关键帧 |
| `frame_alignment_ok` | RGB、Depth、状态和动作时间戳误差低于阈值 |
| `robot_state_ok` | `qpos/qvel/ee_pose/gripper` 连续有效 |
| `action_ok` | 动作维度固定、无 NaN、控制源清晰 |
| `task_metadata_ok` | 任务类型、目标工具、任务文本和 reset seed 完整 |
| `manual_control_ok` | episode 来自 VR 人工示教，不是程序自动驱动生成 |
| `safety_ok` | 无严重穿模、危险碰撞或越界动作 |

人工抽查重点：

1. 回放 D405 RGB-D，确认画面中工具、夹爪和目标区域可见。
2. 回放 3D 状态，确认机器人、工具轨迹与任务类型一致。
3. 查看 action timeline，确认动作连续、无异常跳变。
4. 检查 result 标签，确认成功、失败、掉落、人工中止等标记正确。
5. 检查 Quest3 输入时间线，确认关键动作来自操作者控制。

episode 最终进入以下类别之一：

| 类别 | 用途 |
| --- | --- |
| `debug_trial` | 只用于调试链路，不进入训练 |
| `train_candidate` | 可转换为 LeRobot / OpenPI 训练数据 |
| `eval_candidate` | 适合做评估或消融，不一定进入训练 |
| `rejected` | 文件缺失、标签不可信、追踪异常或安全问题严重 |

### 7.8 最小 pilot 验证要求

进入批量采集前，至少完成以下 pilot 验证：

- 每种工具至少 3 条 `tool_grasp`。
- 每种工具至少 3 条 `tool_pick_place` 或 `tool_reposition`。
- 所有 pilot episode 都能生成完整 `metadata/visuals/states/actions/events/result/validation_summary`。
- 至少 80% pilot episode 通过 `camera_capture_ok` 和 `frame_alignment_ok`。
- 至少 80% pilot episode 通过 `camera_view_ok`。
- 人工回放确认动作、任务文本和结果标签基本一致。
- 转换器能把 pilot 数据转换成 LeRobot / OpenPI loader 可读取的数据。

### 7.9 数据如何进入训练

当前训练链路只保留 pi0.5 操作能力微调：

```text
raw VR episode
  -> validation / replay / quality filter
  -> LeRobot / OpenPI dataset: d405_rgb + robot_state + action + task prompt
  -> loader smoke test
  -> pi0.5 LoRA / adapter training
  -> MuJoCo rollout validation
```

也就是说：

- raw episode 不直接喂给 pi0.5。
- LeRobot / OpenPI 转换是训练前的硬前置条件。
- 当前不生成 memory dataset，不训练 collaboration memory，不集成 interaction gating。
- Depth 第一版作为 sidecar 或回放/评估字段保留，不强制进入 pi0.5 主输入。

---

## 8. LeRobot / OpenPI 数据转换

### 8.1 转换目标

pi0.5 微调前必须先把 raw episode 转成 LeRobot / OpenPI 可读取的数据格式。raw 目录里的 `visuals.jsonl/states.jsonl/actions.jsonl` 只是采集原始记录，不能直接作为 pi0.5 训练集使用。

建议新增：

- `scripts/datasets/convert_vr_to_lerobot.py`
- `scripts/datasets/validate_lerobot_dataset.py`
- `configs/pi05/quest3_vr_tools_lora.yaml`

第一版 feature mapping：

| 字段 | 来源 | 是否 P0 |
| --- | --- | --- |
| `observation.images.d405_rgb` | 末端 D405 RGB | 是 |
| `observation.state` | `[qpos[0:6], gripper_opening]` | 是 |
| `task/prompt` | `pick up the wrench`、`place the screwdriver in the toolbox` 等模板 | 是 |
| `action` | `[joint_delta[0:6], gripper_target]` | 是 |
| `observation.images.d405_depth` | 末端 D405 Depth | P1 / sidecar |
| `tool_pose` | MuJoCo 工具真值 | P1，筛选和评估用，默认不进 pi0.5 主输入 |

### 8.2 转换器要求

转换器至少要完成：

- 只读取 `train_candidate` 和明确允许的 `eval_candidate`，跳过 `debug_trial/rejected`。
- 按 episode 对齐 D405 RGB、机器人状态、动作和任务文本。
- 生成连续的 `episode_index/frame_index/timestamp`。
- 把动作统一成训练动作空间，例如 `joint_delta[0:6] + gripper_target`。
- 把任务文本映射成稳定 prompt，例如 `pick up the wrench and place it in the toolbox`。
- 生成 `feature_mapping.json`，记录 raw 字段到训练字段的映射。
- 生成 `conversion_report.json` 和 `rejected_episodes.jsonl`。
- 生成 action/state normalization 统计。
- 按 episode 划分 train/val/test，禁止按帧随机打散。
- 记录相机标定版本、数据采集版本和转换脚本版本。

Depth 第一版可以作为 sidecar 或评估/回放字段保留，不强制进入 pi0.5 主输入；P0 先确保 `d405_rgb + robot_state + action + prompt` 能被训练脚本稳定读取。具体目录结构以实际安装的 LeRobot / OpenPI 版本为准，但本项目必须保留转换报告和字段映射，避免后续无法追溯。

### 8.3 loader smoke test

转换后必须用 loader 做 smoke test：

- 随机读取一个 episode。
- 检查 RGB 能正常解码。
- 检查 `observation.state` 维度固定。
- 检查 `action` 维度固定且无 NaN。
- 检查 prompt 与目标工具和任务类型一致。
- 检查 timestamp 单调递增。
- 检查 train/val/test 没有同一 episode 泄漏。
- 检查 normalization 统计没有被 rejected episode 污染。

第一版不建议把所有 MuJoCo 真值状态都塞进 `pi0.5`。工具姿态、碰撞、接触等真值可以用于筛选和评估，但 VLA 主输入应尽量靠近未来实机可获得的观测。

---

## 9. pi0.5 LoRA 操作能力

### 9.1 模型定位

`pi0.5` 负责底层 manipulation：

- 抓取指定工具。
- 移动到目标区域或工具箱槽位。
- 调整工具位置和姿态。
- 在任务完成后稳定撤离或保持。

当前第一版不训练人机交接 release 时机，也不让 pi0.5 学习协作 gate。夹爪开合只是普通操作动作的一部分，是否进入训练由 episode 质量和任务类型决定。

### 9.2 数据转换

数据转换要求见第 8 节。本节只定义训练和验证边界：pi0.5 训练输入必须来自通过 loader smoke test 的 LeRobot / OpenPI 数据集，不能直接使用 raw JSONL。

5090D 32GB 服务器上的第一版训练边界：

- 只做 LoRA / adapter，不做全参数微调。
- 从小 batch、短序列、低分辨率 RGB 开始。
- 优先保证数据转换、训练启动、checkpoint 保存和 MuJoCo 验证闭环。
- 不把 collaboration memory 或 gating 放进同一个训练图里一起训练。
- 使用半精度、gradient checkpointing 和低显存优化器。
- batch size 从 `1-2` 开始，用 gradient accumulation 补有效 batch。
- D405 RGB 先降到可控分辨率，例如 `224/256/320` 级别，再根据显存调整。
- 按 episode 划分 train/val/test，禁止按帧随机打散。
- 训练配置必须记录数据集版本、相机版本、动作定义和任务文本模板。

### 9.3 模型入库

建议输出到：

```text
models/pi05/quest3_vr_lora_runs/<run_id>/
  config.json
  dataset_snapshot.json
  feature_mapping.json
  checkpoints/
  exported/
  offline_eval/
  mujoco_validation/
```

### 9.4 MuJoCo 验证

每个可用 checkpoint 至少需要在 MuJoCo 中验证：

- 固定工具初始位姿下能完成 `tool_grasp`。
- 固定目标区下能完成 `tool_pick_place` 或 `tool_reposition`。
- 不同工具类别下动作维度、夹爪控制和状态归一化一致。
- rollout 中无明显关节越界、剧烈抖动、穿桌或持续碰撞。
- 记录 `task_success_rate`、`grasp_success_rate`、`placement_error`、`tool_drop_rate`、`robot_motion_jitter`。

---

## 10. 策略运行与动作安全约束

### 10.1 后处理规则

当前不实现 interaction gating，但 pi0.5 rollout 仍必须经过基础动作后处理：

- 关节目标或增量必须经过 UR5 关节限位裁剪。
- 单步 `joint_delta` 必须限幅，避免模型输出造成跳变。
- 夹爪目标必须限制在合法开合范围。
- 当 WebSocket、D405 或仿真状态异常时，策略进入 `safe_hold`，不继续发送新动作。
- 当动作包含 NaN、Inf、维度错误或时间戳过旧时，直接丢弃该动作。
- 当预测动作导致明显穿桌、越界或持续碰撞时，记录失败并停止 rollout。

### 10.2 runtime

建议新增或复用：

- `backend/policies/pi05_policy_runtime.py`
- `backend/policies/action_postprocess.py`
- `scripts/training/evaluate_pi05_mujoco.py`

每个控制周期都记录：

- `observation_summary`
- `candidate_action`
- `postprocessed_action`
- `safety_status`
- `postprocess_reason`
- `task_progress`

这些日志用于判断失败来自数据、模型、动作空间、后处理还是仿真物理。

---

## 11. 评估设计

### 11.1 数据集指标

必须记录：

- `episode_count`
- `train/val/test_episode_count`
- `accepted_episode_count`
- `rejected_episode_count`
- `camera_capture_ok_rate`
- `frame_alignment_ok_rate`
- `camera_view_ok_rate`
- `action_nan_rate`
- `manual_control_rate`
- 每种工具和每种任务类型的样本数

### 11.2 离线训练指标

必须记录：

- `action_mse`
- `joint_delta_mse`
- `gripper_mae`
- `loss_train / loss_val`
- `checkpoint_step`
- `dataset_version`
- `feature_mapping_version`
- `normalization_version`

### 11.3 MuJoCo rollout 指标

必须记录：

- `task_success_rate`
- `grasp_success_rate`
- `placement_error`
- `tool_drop_rate`
- `collision_rate`
- `joint_limit_violation_count`
- `robot_motion_jitter`
- `mean_episode_duration_s`

第一版重点不是证明安全交接，而是证明从 VR 示教到 LeRobot 数据转换、pi0.5 微调和 MuJoCo 验证的闭环可复现。

---

## 12. 前后端改造重点

### 12.1 前端

- 新增 D405 观测面板，显示末端 RGB、Depth、帧号、有效性和对齐状态。
- 新增 Quest3 `VR采集模式`，支持操作者在头显内完成 precheck、任务模板选择、开始/停止录制和结果标记。
- 显示当前控制模式、目标工具、任务类型、录制状态和最近错误。
- 采集面板支持查看 action timeline、camera timeline 和 validation summary。
- 回放界面支持同时查看 RGB-D、机器人、工具、动作和结果标签。

### 12.2 后端

- 新增 D405 RGB-D 观测有效性检查、帧索引和落盘接口。
- 新增 VR episode recorder，落盘 metadata、visuals、states、actions、events、result 和 validation summary。
- 新增 LeRobot / OpenPI 转换器和数据集校验脚本。
- 新增 pi0.5 policy runtime 和动作后处理。
- 新增 evaluation scripts，输出数据质量、离线训练和 MuJoCo rollout 指标。

### 12.3 共享配置

建议新增：

- `shared/dataset_schema.json`
- `shared/task_templates.json`
- `shared/action_space_schema.json`
- `shared/lerobot_feature_mapping.json`
- `shared/d405_observation_check_config.json`

---

## 13. Sim2Real 与数字孪生约束

第一版可以先做 shadow mode，不要求真实 UR5 立即执行完整策略。

必须提前冻结：

- `runtime_target=sim/real_ur5/shadow_real_ur5`
- 高层动作：`joint_target/joint_delta/gripper_target`
- 观测字段：真实 UR5 关节、夹爪、D405 RGB-D、任务文本和必要状态
- 实机安全机制：限速、急停、watchdog、掉线保护、人工确认开关
- 数据与模型版本：相机标定、LeRobot 数据集、pi0.5 checkpoint 和动作空间定义

真实机械臂验证建议顺序：

1. `shadow_real_ur5`：模型只输出建议动作，不驱动硬件。
2. 低速 replay：只验证动作范围、状态映射和安全停。
3. 低速工具抓取：验证抓取动作范围和夹爪控制。
4. 低速 pick/place：验证放置区域、工具掉落和碰撞风险。
5. 全闭环策略：仅在前面阶段稳定后考虑。

---

## 14. 推荐开发顺序

建议严格按下面顺序推进：

1. 冻结 `quest3_vr_lerobot_pi05_v1`、任务模板、动作空间和 episode schema。
2. 先完成末端 D405 在 MuJoCo 中的第一轮 RGB-D 观测验证，确认工具、夹爪和目标区域可见。
3. 建立 Quest3 VR 快速采集入口，支持 precheck、任务模板、开始/停止和结果标记。
4. 建立单边机器人操作 episode 录制器。
5. 采集每种工具的 `tool_grasp / tool_pick_place / tool_reposition` pilot。
6. 完成自动校验和人工回放筛选。
7. 完成 LeRobot / OpenPI 数据转换器。
8. 用 loader smoke test 验证 RGB、state、action、prompt、timestamp 和 split。
9. 按 episode 划分 train/val/test，并生成 conversion report 和 normalization 统计。
10. 在 5090D 32GB 服务器上进行 pi0.5 LoRA / adapter 微调。
11. 将 checkpoint 入库到 `models/pi05/quest3_vr_lora_runs/<run_id>/`。
12. 在 MuJoCo 中验证工具抓取、移动和放置 rollout。
13. 输出数据质量、离线训练和 rollout 指标。
14. 固化 sim2real shadow mode 接口和动作安全约束。

这条顺序的核心原因是：

- 没有末端 D405 的 MuJoCo 视觉验证，采集到的数据就缺少可靠的机器人第一视角。
- 没有 VR 快速采集入口，操作者很难稳定采集高质量 episode。
- 没有 raw episode 校验，坏数据会直接污染转换和训练。
- 没有 LeRobot / OpenPI 转换与 loader smoke test，pi0.5 训练不可复现。
- 没有 MuJoCo rollout 验证，checkpoint 只能说明 loss 下降，不能说明策略可用。
- 没有 shadow mode，后续真实 UR5 验证风险过高。

---

## 15. 当前最重要结论

1. 当前已有基础足够支撑新主线：UR5、工具、工具箱、前后端同步、Quest3 控制和 S4.5 物理边界都已经是可复用资产。
2. 当前主问题是“VR 采集数据能否稳定转换为 LeRobot / OpenPI 格式并微调 pi0.5”，不是人机协作交接。
3. 训练主视觉必须来自机械臂末端 D405，不能用 Quest3 页面画面或 Three.js 外部相机替代。
4. raw episode 不能直接训练 pi0.5，必须先通过数据校验、转换报告、字段映射和 loader smoke test。
5. 正式训练候选必须来自操作者在 Quest3 中的人工示教，脚本数据只能用于调试或管线测试。
6. 5090D 32GB 服务器第一版只做 LoRA / adapter，不做全参数微调。
7. 当前暂停 human hand、collaboration memory、interaction gating 和安全交接评估，待数据闭环稳定后再决定是否恢复。
