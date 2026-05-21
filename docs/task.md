# Quest3 人机协作安全交接实验任务书（2026-05-21 修订）

## 1. 文档定位

本文档基于当前仓库已经完成的 UR5 数字孪生、工具场景、前后端实时同步、Quest3 基础控制和 S4.5 物理边界修复继续规划。后续主线不再只是“工具能否被抓取和放置”，而是研究人机协作交接中更关键的时机判断问题：

```text
机器人什么时候才应该把工具交给人。
```

也就是说，底层操作能力要继续保留，但主问题从“能不能递过去”升级为“什么时候安全、稳定、可信地递过去”。

---

## 2. 统一目标

新的主任务建议命名为：

```text
quest3_safe_handover_v1
```

已有 `quest3_tool_sorting_v1` 继续作为工具场景、机器人操作和抓取资产基线。它的价值是已经提供了 UR5、工具、工具箱、状态同步、VR 控制和物理边界基础；新任务在此基础上加入仿真人手与协作关系理解。

### 2.1 要解决的问题

传统人机协作系统通常关注机械臂本体能力，例如抓取、移动、避障、碰撞检测或距离阈值保护。但在真实交接任务中，困难点并不只是机械臂能不能把工具送到人附近，而是：

- 人是否真的准备好接收。
- 人是否正在犹豫、后撤或晃动。
- 人手与工具的关系是否已经稳定。
- 当前释放工具是否会导致提前松手、掉落或危险接触。

因此本项目的核心问题是“安全感知驱动的交接时机理解”。机器人不仅要会操作，还要理解人与机器人之间的协作状态是否已经进入稳定可信的 `ready` 阶段。

### 2.2 双层架构

后续系统采用双层协作架构：

```text
pi0.5 / VLA 操作模型
  负责怎么递：抓取、移动、对齐、保持递送姿态

collaboration memory 协作记忆模型
  负责什么时候递：根据历史关系序列判断是否允许 release

interaction gating
  负责最终闸门：只有 ready 且安全条件满足时才执行释放
```

这种拆分的原因是：操作能力和协作理解不是同一个问题。`pi0.5` 可以持续生成候选动作，但是否真正 release 必须由协作记忆和安全 gate 决定。

---

## 3. 当前已有实验基础

当前仓库已经具备后续安全交接实验需要的关键基础，不需要从零开始。

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

以下内容仍需要围绕新主线补齐：

- 末端 D405 在 MuJoCo 中的主视觉观测验证、RGB-D 接口和落盘校验。
- MuJoCo 中的 `human hand` 模型与前端显示。
- Quest3 右手控制仿真人手的链路。
- VR 沉浸式快速采集入口，让操作者在头显内完成 precheck、选择阶段模板、开始/停止录制和标记结果。
- 双边协作 episode 录制器。
- 人手状态、工具状态、机器人状态之间的 relation feature。
- `approach/stabilization/hesitation/retreat/ready/release` 阶段标签。
- collaboration memory 训练、评估和在线推理。
- `pi0.5` 面向 handover manipulation 的 LoRA 微调。
- `interaction gating` 运行时。
- 安全交接指标、基线对比和复现实验记录。
- 数字孪生到真实 UR5 的 shadow mode 接口与安全约束。

---

## 4. 新场景与任务定义

### 4.1 场景对象

第一版 `quest3_safe_handover_v1` 场景由以下对象组成：

- `UR5 + Robotiq 2F-85`
- 末端 `Intel RealSense D405 RGB-D`
- 桌面 / 工作台
- 已有工具：`wrench_01`、`screwdriver_01`、`pliers_01`
- 工具箱：作为场景资产和初始收纳对象保留，不再作为最终任务目标
- 新增 `human_hand`
- 新增 `handover_zone`

第一版不增加更多工具种类，优先使用已有工具资产降低变量数量。这样可以把主要实验变量集中在人机交接关系上，而不是资产处理、碰撞调参或工具类别泛化上。

### 4.2 主任务流程

一个标准 episode 建议包含以下阶段：

```text
reset
  -> robot_grasp
  -> robot_offer
  -> human_approach
  -> stabilization / hesitation / retreat
  -> ready
  -> gated_release
  -> result
```

其中 `gated_release` 是关键：即使 `pi0.5` 产生 release 候选动作，只要 memory 未判定 ready，或者安全状态不满足，系统就必须保持夹持或进入安全等待。

### 4.3 interaction phase

第一版冻结以下交互阶段：

| phase | 含义 | release |
| --- | --- | --- |
| `approach` | 人手正在靠近工具或机器人 | 禁止 |
| `stabilization` | 人手接触或接近工具，但仍在调整 | 禁止 |
| `hesitation` | 人手反复微调、晃动或停顿，接收意图不稳定 | 禁止 |
| `retreat` | 人手后撤或离开交接区域 | 禁止 |
| `ready` | 人手稳定、姿态对齐、接触可信 | 可候选 |
| `release` | gate 已允许，机器人释放工具 | 执行 |
| `fail` | 掉落、危险接触、追踪丢失或人工中止 | 禁止 |

---

## 5. Quest3 双边协作控制

### 5.1 控制分工

第一版正式数据采集采用 VR 沉浸式采集模式，并保留桌面端作为监督和调试面板。采集主体必须是人类操作者，而不是程序自动驱动机械臂生成 episode。

- Quest3 左手：控制 UR5 / 夹爪，完成抓取、递送和对齐。
- Quest3 右手：控制 MuJoCo 中的 `human_hand`，制造正常接收、犹豫、后撤和不稳定交互。
- 桌面端：显示 D405、状态、日志和回放，不抢占 VR 采集控制权。

这样做的目的不是模拟完整人体，而是可控地采集协作关系变化。人手行为必须可重复、可记录、可回放。

程序侧只负责：

- 采集前 `precheck`。
- reset、状态同步和安全边界检查。
- 录制 RGB-D、状态、动作、事件和 gate 日志。
- 生成 `validation_summary.json`。
- 辅助回放、标注和筛选。

程序侧不得把正式数据采集写成“自动控制机械臂批量生成协作 episode”。如果需要脚本，只能用于 camera smoke test、接口测试、回放验证或固定姿态检查；正式 `normal_handover/hesitation/retreat/unstable` 数据必须来自 VR 人工示教。

### 5.2 human hand 模型要求

第一版 human hand 不追求复杂手部动力学，应优先满足：

- 可稳定显示。
- 可由右手 VR 手势控制。
- 有 palm / fingertip 碰撞体。
- 可记录位置、姿态、速度和追踪置信度。
- 可与工具产生接触。
- 不穿桌、不穿工具箱、不穿夹爪实体。

建议新增：

- `backend/mujoco_models/human_hand.xml`
- `shared/handover_scene_config.json`
- `shared/human_hand_config.json`

### 5.3 状态广播新增字段

后端状态广播建议增加：

```json
{
  "human_hand_state": {
    "pose": [0, 0, 0, 0, 0, 0, 1],
    "velocity": [0, 0, 0],
    "tracking_status": "tracked",
    "stability_score": 0.0
  },
  "handover_state": {
    "phase": "approach",
    "handover_confidence": 0.0,
    "release_allowed": false,
    "gate_reason": "not_ready"
  }
}
```

---

## 6. 末端 D405 摄像头模块与 MuJoCo 观测验证

协作数据的主视觉观测必须来自机械臂末端安装的 D405 RGB-D 相机。Quest3 页面画面、Three.js 观察相机和场景里的 `camera / camera_base` 只能用于调试或展示，不能作为训练主视觉来源。

这一阶段可以优先启动，并且需要在正式采集前完成。第一轮不必等待 human hand 完全接入，可以先验证夹爪、工具和 handover zone 是否在末端相机视野内；等 human hand 接入后，再复测人手进入、犹豫、后撤和 release 前后的可见性。

这样安排更合理，因为 relation feature 虽然主要来自仿真状态，但 `pi0.5` 的操作能力训练、回放检查和后续 sim2real 都依赖末端相机视角是否真实可用。如果 D405 在递送阶段看不到工具、人手或夹爪接触区域，后续数据即使有状态字段，也不适合作为稳定的视觉-动作训练样本。

### 6.1 摄像头在 MuJoCo 中的角色

D405 在 MuJoCo 中不是一个普通装饰模型，而是训练观测源。它应满足：

- 固定挂载在 UR5 末端或腕部坐标系上，随机械臂运动。
- 输出 `d405_rgb` 和 `d405_depth`。
- RGB 与 Depth 使用同一时间戳或可对齐时间戳。
- 每帧记录相机内参版本、外参版本、mount 名称和相机位姿。
- 视野覆盖夹爪、被递送工具、human hand 接收区域和 handover zone。

### 6.2 MuJoCo 视觉效果验证

正式录制前必须在 MuJoCo 中做视觉 smoke test，至少覆盖以下场景：

| 场景 | 检查目标 |
| --- | --- |
| robot grasp | D405 能看到夹爪和被抓工具 |
| robot offer | 工具移动到 handover zone 后仍在视野内 |
| handover zone placeholder | 没有 human hand 前，先用接收区标记或占位体确认未来人手进入区域可见 |
| human approach | human hand 接入后复测，确认能看到手与工具的相对关系 |
| stabilization | human hand 接入后复测，确认人手接触或接近工具时 RGB 能分辨手/工具/夹爪 |
| hesitation | human hand 接入后复测，确认人手小幅晃动时连续帧能看到关系变化 |
| retreat | human hand 接入后复测，确认 D405 视野能记录后撤方向 |
| ready/release | human hand 接入后复测，确认 release 前后工具、人手和夹爪不应全部被遮挡 |

如果 D405 在某些阶段持续看不到 human hand 或工具，不能直接进入批量采集，应先调整 handover zone、机械臂递送姿态或相机挂载角度。

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

这个面板是采集质量控制的一部分，不是装饰 UI。采集者应能在开始录制前确认末端相机确实看到交接区域。

### 6.5 摄像头验证通过条件

D405 阶段通过后，至少应满足：

- `d405_rgb` 和 `d405_depth` 在 MuJoCo 中稳定输出。
- RGB 和 Depth 帧可落盘，并能通过 `visuals.jsonl` 回溯。
- 第一轮 camera-only smoke test 中，夹爪、目标工具和 handover zone 大部分时间可见。
- human hand 接入后，正常、hesitation、retreat、unstable 四类 pilot 中，人手、工具和夹爪关键区域大部分时间可见。
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
    quest3_safe_handover_v1/
      raw/
      processed/
      splits/
      reports/
models/
  pi05/
    handover_lora_runs/
  memory/
  registry/
experiments/
  safe_handover/
logs/
  train/
  eval/
```

### 7.2 episode 必须保存的内容

每条 episode 必须保存：

- `metadata.json`
- `visuals.jsonl`
- `states.jsonl`
- `actions.jsonl`
- `relations.jsonl`
- `events.jsonl`
- `phase_labels.jsonl`
- `result.json`
- `validation_summary.json`
- 可选 `videos/` 预览文件

训练主数据必须以逐帧 RGB/Depth 和 JSONL 索引为准，视频只用于快速检查和结果展示。

### 7.3 原始状态字段

`states.jsonl` 至少包含：

- 机器人：`qpos`、`qvel`、`ee_pose`、`gripper_opening`、`grasp_state`、`attached_tool_id`
- 人手：`hand_pose`、`hand_velocity`、`fingertip_pose`、`tracking_status`、`tracking_confidence`
- 工具：`tool_pose`、`tool_velocity`、`tool_attached`、`tool_in_human_hand`、`tool_dropped`
- 视觉：`d405_rgb`、`d405_depth`、`frame_id`、`timestamp`、`frame_aligned`
- 安全：`human_robot_min_distance`、`collision_warning`、`safe_hold`

### 7.4 relation feature

`relations.jsonl` 是协作记忆模型的核心输入，至少包含：

| feature | 含义 |
| --- | --- |
| `human_tool_distance` | 人手到工具的距离 |
| `human_robot_distance` | 人手到机器人最近距离 |
| `human_ee_distance` | 人手到末端执行器距离 |
| `human_tool_relative_velocity` | 人手相对工具速度 |
| `human_approach_speed` | 人手接近速度 |
| `retreat_speed` | 人手后撤速度 |
| `retreat_detected` | 是否检测到后撤 |
| `hand_stability_score` | 滑动窗口内手部稳定性 |
| `pose_alignment_score` | 人手接收姿态与工具递送方向对齐程度 |
| `contact_valid` | 是否发生有效接触 |
| `contact_duration_ms` | 有效接触持续时间 |
| `hesitation_score` | 犹豫程度，结合微抖、停顿、反复接近后撤 |
| `handover_confidence_target` | 训练或评估用的目标置信度 |

这些特征必须能从现有仿真状态、工具状态、人手状态和接触信息中计算出来，避免依赖未来实机无法估计的内部量。

### 7.5 数据采集类型

第一版必须采集四类关键交互：

1. `normal_handover`：人手稳定接近、对齐、接触后接收。
2. `hesitation`：人手接近后停顿、晃动、反复微调。
3. `retreat`：人手接近后后撤或离开交接区域。
4. `unstable`：人手姿态不对齐、接触不稳或速度过快。

可选负样本：

- `early_release`：仅在调试模式中制造提前释放，用于标注危险案例。
- `collision_near_miss`：人手与夹爪/连杆距离过近，但未发生严重碰撞。

如果数据集中只有顺利交接，协作记忆模型无法学会阻止危险 release，因此 `hesitation` 和 `retreat` 是必须采集的主类。

### 7.6 VR 沉浸式阶段化采集入口

正式协作数据必须由操作者在 Quest3 VR 沉浸式采集模式中完成。系统不能用程序自动驱动机械臂去生成训练 episode，因为那样只能得到脚本轨迹，不能得到真实的人机交互犹豫、后撤、微调和接收时机变化。

每条正式 episode 的元数据建议明确记录：

- `operator_controlled=true`
- `control_mode=vr_immersive_bilateral`
- `robot_input_source=quest3_left_hand`
- `human_input_source=quest3_right_hand`
- `autonomy_level=manual_demonstration`
- `scripted_collection=false`

VR 采集模式需要支持快速启动：

1. 操作者戴上 Quest3 进入 `VR采集模式`。
2. 头显内显示 D405 状态、WebSocket 状态、双手追踪状态和 `recording_ready`。
3. 操作者选择本轮采集阶段模板，而不是每次从零配置。
4. 通过 VR 内按钮或手势执行 `start episode`。
5. 操作者左手控制 UR5，右手控制 `human_hand`，按阶段要求完成交互。
6. 通过 VR 内按钮或手势执行 `stop episode`。
7. 头显内快速显示本条结果：成功、失败、人工中止、追踪异常、相机异常或待回放确认。

第一版采集应按阶段推进，不建议一开始就混合采所有情况：

| 采集阶段 | 目的 | 是否进入训练候选 |
| --- | --- | --- |
| `stage_0_camera_check` | 只验证 D405、视野和落盘 | 否 |
| `stage_1_robot_offer_dryrun` | 人只控制机器人抓取和递送姿态，不做交接 | 可作为 manipulation 调试 |
| `stage_2_normal_handover` | 采集稳定接收正样本 | 是 |
| `stage_3_hesitation` | 采集犹豫、停顿、反复微调 | 是，偏 memory |
| `stage_4_retreat` | 采集接近后后撤 | 是，偏 memory |
| `stage_5_unstable` | 采集姿态不稳、速度过快、接触不可信 | 是，偏 memory / eval |
| `stage_6_debug_negative` | 受控制造 early release 或 near miss | 默认否，仅用于调试或评估 |

每个阶段都必须先完成少量 pilot，并通过自动校验和人工回放检查后，才能进入该阶段的批量采集。阶段之间不能混着推进，否则后续很难判断问题来自相机、人手控制、机器人递送姿态、标签规则还是交互本身。

### 7.7 单条 episode 的采集操作流程

每条数据都应按固定流程采集，避免后续回放时无法判断问题来自人手、机器人、相机、录制器还是交互标注。

#### 7.7.1 采集前检查

开始一条 episode 前，先完成以下检查：

1. 启动后端和前端，确认 WebSocket 已连接。
2. 确认 MuJoCo 场景已加载 UR5、工具、工具箱、D405 和 `human_hand`。
3. 执行 reset，确认工具在桌面上、无遮挡、无明显穿模。
4. 确认 `d405_rgb`、`d405_depth` 可用，且不是 stub / fallback 图像。
5. 打开 D405 观测面板，确认夹爪、目标工具和 human hand 接收区域在末端相机视野内。
6. 确认 Quest3 左手和右手追踪状态均为 `tracked`。
7. 进入 Quest3 `VR采集模式`，确认头显内能看到采集状态、阶段模板和开始/停止入口。
8. 在 VR 采集面板选择：
   - `collection_stage`: `stage_1_robot_offer_dryrun / stage_2_normal_handover / stage_3_hesitation / stage_4_retreat / stage_5_unstable / stage_6_debug_negative`
   - `episode_type`: `normal_handover / hesitation / retreat / unstable`
   - `handover_object_class`: `wrench / screwdriver / pliers`
   - `handover_zone_id`
   - `instruction_text`
9. 运行 `/dataset/precheck/` 或等效检查，只有 `recording_ready=true` 时才能进入正式录制；否则只能进入 `debug_trial`。

#### 7.7.2 正常交接采集操作

`normal_handover` 用于采集稳定、可信、可释放的正样本：

1. 操作者在 VR 采集模式中点击开始录制，冻结本条 episode 的 metadata、工具类别、任务文本和 reset seed。
2. 左手控制 UR5 接近目标工具，夹爪闭合并抓取工具。
3. 左手控制 UR5 将工具移动到 `handover_zone`。
4. 右手控制 `human_hand` 从安全距离稳定接近工具。
5. 右手让人手姿态与工具递送方向对齐，并保持短时间稳定接触。
6. 等待系统记录到 `stabilization -> ready` 的阶段变化。
7. 当 memory 和 safety gate 都允许 release 时，执行释放。
8. 保持人手稳定一小段时间，确认工具没有掉落或危险接触。
9. 操作者在 VR 中停止录制，等待 `result.json` 和 `validation_summary.json` 生成。

#### 7.7.3 hesitation 样本采集操作

`hesitation` 用于训练模型识别人手犹豫或接收意图不稳定：

1. 左手照常完成抓取和递送，使工具到达 `handover_zone`。
2. 右手控制 `human_hand` 接近工具，但不要马上稳定接触。
3. 在工具附近做小幅停顿、晃动、微调或反复靠近。
4. 避免长时间稳定接触，保持接收状态不确定。
5. 观察系统是否维持 `release_allowed=false`。
6. 停止录制后，将 episode 类型标为 `hesitation`。

这类数据的重点不是成功交接，而是让模型学到“接近不等于 ready”。

#### 7.7.4 retreat 样本采集操作

`retreat` 用于训练模型识别人手后撤：

1. 左手照常完成抓取和递送。
2. 右手控制 `human_hand` 接近工具，制造看似即将接收的过程。
3. 在接触前或短暂接触后，让人手明显后撤。
4. 后撤过程中禁止主动 release，观察 gate 是否阻止释放。
5. 录制结束后检查 `retreat_detected=true`，并确认 phase 中出现 `retreat`。

这类数据的重点是让模型学到“曾经接近过，也不代表现在可以释放”。

#### 7.7.5 unstable 样本采集操作

`unstable` 用于采集姿态不稳或接触不可信的情况：

1. 左手完成抓取和递送。
2. 右手控制人手快速接近、姿态不对齐或轻微晃动。
3. 可以让人手短暂接触工具，但不要形成稳定接收。
4. 记录 `hand_stability_score` 较低、`pose_alignment_score` 较低或 `contact_consistency` 较差的片段。
5. 录制结束后检查该 episode 不应被标成可 release 的正样本。

#### 7.7.6 调试负样本操作

`early_release` 和 `collision_near_miss` 只能在 `debug_trial` 或受控 pilot 中采集，不能直接进入训练候选：

- `early_release`：人为制造过早 release，用于标注危险案例和验证指标。
- `collision_near_miss`：让人手与夹爪/连杆距离过近，但避免真实严重碰撞，用于安全 gate 验证。

这类数据默认 `included_in_train=false`，除非后续只用于 gate 负样本或评估集。

### 7.8 采集后的验证与筛选流程

每条 episode 结束后都必须经过自动校验和人工回放检查。不能只因为文件成功保存就进入训练集。

#### 7.8.1 自动校验

`validation_summary.json` 至少应包含以下检查：

| 检查项 | 通过条件 |
| --- | --- |
| `files_complete` | metadata、visuals、states、actions、relations、events、phase labels 都存在 |
| `camera_capture_ok` | RGB 和 Depth 均来自 D405，且无 stub / fallback |
| `camera_view_ok` | D405 视野中能看到工具、夹爪和 human hand 关键区域 |
| `frame_alignment_ok` | RGB、Depth、状态和动作时间戳误差低于阈值 |
| `robot_state_ok` | `qpos/qvel/ee_pose/gripper` 连续有效 |
| `human_hand_state_ok` | 人手追踪未长时间丢失，位姿无异常跳变 |
| `relations_ok` | 每个有效 step 都能计算 relation feature |
| `phase_label_ok` | phase 标签完整，且没有大段缺失 |
| `safety_ok` | 无严重穿模、危险碰撞或未记录的 safe hold |
| `release_log_ok` | candidate action、gated action、release_allowed 和 gate_reason 可追溯 |
| `manual_control_ok` | episode 来自 VR 人工示教，不是程序自动驱动生成 |

#### 7.8.2 人工回放检查

自动校验通过后，还需要人工抽查：

1. 回放 D405 RGB-D，确认画面中工具、夹爪和人手可见。
2. 回放 3D 状态，确认机器人、人手、工具轨迹与录制类型一致。
3. 查看 relation timeline，确认距离、速度、稳定性和接触变化符合画面。
4. 查看 phase timeline，确认 `hesitation`、`retreat`、`ready` 没有明显误标。
5. 查看 release/gate timeline，确认不安全状态下没有执行 release。
6. 检查 result 标签，确认成功、失败、掉落、提前释放、人工中止等标记正确。
7. 检查左右手输入时间线，确认机器人和 human hand 的关键动作来自操作者控制。

#### 7.8.3 数据去向判定

episode 最终进入以下类别之一：

| 类别 | 用途 |
| --- | --- |
| `debug_trial` | 只用于调试链路，不进入训练 |
| `memory_train_candidate` | relation sequence 和 phase 标签可用于训练协作记忆 |
| `manipulation_train_candidate` | 操作轨迹可用于 pi0.5 LoRA 微调 |
| `eval_candidate` | 适合做评估或消融，不一定进入训练 |
| `rejected` | 文件缺失、标签不可信、追踪异常或安全问题严重 |

同一条 episode 可以同时属于 `memory_train_candidate` 和 `manipulation_train_candidate`，但必须分别满足对应条件。比如一条 `retreat` 样本可能非常适合训练 memory，但不一定适合作为 pi0.5 的正向操作示教。

#### 7.8.4 最小 pilot 验证要求

进入批量采集前，至少完成以下 pilot 验证：

- 每种工具至少 1 条 `normal_handover`。
- 每种工具至少 1 条 `hesitation`。
- 每种工具至少 1 条 `retreat`。
- 每种工具至少 1 条 `unstable`。
- 所有 pilot episode 都能生成完整 `relations.jsonl`。
- 至少 80% pilot episode 通过 `camera_capture_ok` 和 `frame_alignment_ok`。
- 人工回放确认 phase 标签与画面基本一致。
- gate 在 `hesitation` 和 `retreat` 样本中默认不允许 release。
- D405 观测在四类 pilot 中都能覆盖交接关键区域。

### 7.9 数据如何进入训练

同一批 VR 人工采集 episode 不建议“一块端到端训练”。第一版应拆成两条训练流，再在运行时合起来：

```text
raw VR episode
  -> validation / replay / phase label
  -> memory dataset: relations.jsonl + phase_labels.jsonl
  -> pi0.5 dataset: LeRobot/OpenPI compatible d405_rgb + robot_state + action + task prompt
  -> runtime: pi0.5 candidate action + collaboration memory + interaction gating
```

也就是说：

- collaboration memory 只训练“什么时候可以 release”。
- pi0.5 LoRA 只训练“怎么抓取、递送、对齐和保持姿态”。
- interaction gating 在推理阶段合并两者，不把 release 决策直接交给 pi0.5。

这种拆分对硬件也更现实：

| 部分 | 输入 | 训练位置 | 原因 |
| --- | --- | --- | --- |
| relation feature 构建 | `states/actions/events/phase_labels` | 本地机器即可 | 主要是数据处理，不吃显存 |
| collaboration memory | 低维 relation sequence | 本地机器优先 | GRU/LSTM 很小，普通 GPU 甚至 CPU 都能先跑通 |
| pi0.5 LoRA | D405 RGB + robot state + action | 5090D 32GB 服务器 | 视觉动作模型最吃显存，只在服务器上做轻量微调 |
| gating / evaluation | 模型输出 + relation feature | 本地或服务器 | 主要验证 release 时机和安全指标 |

5090D 只有 32GB 时，第一版不要做全参数微调，也不要把 memory、VLA、gating 全部端到端一起训。建议采用：

- LoRA / adapter 微调，冻结大部分 backbone。
- batch size 从 `1-2` 开始，用 gradient accumulation 补有效 batch。
- D405 RGB 先降到可控分辨率，例如 `224/256/320` 级别，再根据显存调整。
- 优先训练动作头、adapter 或少量高层模块。
- 使用半精度、gradient checkpointing 和低显存优化器。
- 按 episode 划分 train/val/test，禁止按帧随机打散。
- 先训练 `robot_grasp -> robot_offer -> align/hold`，release 相关动作单独标记并继续由 gate 控制。

如果 32GB 仍然紧张，先不训练完整 pi0.5：可以先做 action head / adapter 小模型，或者用离线特征缓存加小策略头，等数据和评估链路稳定后再扩到更完整的 LoRA。

---

## 8. 协作记忆模型

### 8.1 模型定位

`collaboration memory` 不直接输出机械臂动作。它输入过去一段时间的 relation sequence，输出：

- `handover_phase`
- `handover_confidence`
- `release_allowed`
- `unsafe_handover_risk`

它要解决的是“当前协作关系是否已经稳定可信”，不是“机械臂怎么移动”。

### 8.2 输入与输出

输入窗口建议：

```text
relation_feature[t-N:t]
robot_state_summary[t-N:t]
human_hand_state_summary[t-N:t]
tool_state_summary[t-N:t]
```

输出建议：

```text
phase_logits
ready_confidence
release_allowed
unsafe_risk
```

第一版模型使用 GRU 或 LSTM 即可，重点是验证历史记忆是否能减少提前释放和危险交接。

### 8.3 训练与评估

建议新增：

- `scripts/datasets/build_relation_sequences.py`
- `scripts/training/train_collaboration_memory.py`
- `scripts/training/evaluate_collaboration_memory.py`
- `backend/models/collaboration_memory/`
- `backend/policies/collaboration_memory_adapter.py`

必须记录指标：

- `phase_accuracy`
- `ready_precision`
- `ready_recall`
- `ready_f1`
- `hesitation_recall`
- `retreat_recall`
- `unsafe_release_false_positive_rate`
- `release_timing_error_ms`

重点不是总体 accuracy，而是 `hesitation/retreat` 不要被误判为 `ready`。

训练资源建议：

- 优先在本地机器训练第一版 GRU/LSTM。
- 如果本地 GPU 很弱，可以先用 CPU 或小 batch 跑通数据、loss 和指标。
- memory 模型不读取 D405 图像，训练成本应明显低于 pi0.5 LoRA。
- 每次 memory run 都记录 relation feature 版本、phase label 版本和数据 split。

---

## 9. pi0.5 LoRA 操作能力

### 9.1 模型定位

`pi0.5` 负责底层 manipulation：

- 抓取指定工具。
- 移动到 handover zone。
- 对齐仿真人手。
- 在交接前保持稳定递送姿态。

`pi0.5` 不负责最终 release。它可以生成 release 候选动作，但真实执行必须经过 interaction gating。

### 9.2 数据转换

建议新增：

- `scripts/datasets/convert_handover_to_lerobot.py`
- `scripts/datasets/validate_handover_dataset.py`
- `configs/pi05/quest3_safe_handover_lora.yaml`

pi0.5 微调前必须先把 raw episode 转成 LeRobot / OpenPI 可读取的数据格式。raw 目录里的 `visuals.jsonl/states.jsonl/actions.jsonl` 只是采集原始记录，不能直接作为 pi0.5 训练集使用。

第一版 feature mapping：

| 字段 | 来源 | 是否 P0 |
| --- | --- | --- |
| `observation.images.d405_rgb` | 末端 D405 RGB | 是 |
| `observation.state` | `[qpos[0:6], gripper_opening]` | 是 |
| `task/prompt` | `hand the wrench to the human` 等模板 | 是 |
| `action` | `[joint_delta[0:6], gripper_target]` | 是 |
| `human_hand_compact_state` | 人手相对工具/末端的低维状态 | P1 |

转换器至少要完成：

- 只读取 `manipulation_train_candidate`，跳过 `debug_trial/rejected`。
- 按 episode 对齐 D405 RGB、机器人状态、动作和任务文本。
- 生成连续的 `episode_index/frame_index/timestamp`。
- 把动作统一成训练动作空间，例如 `joint_delta[0:6] + gripper_target`。
- 把任务文本映射成稳定 prompt，例如 `pick up the wrench and hand it to the human`。
- 生成 `feature_mapping.json`，记录 raw 字段到训练字段的映射。
- 生成 `conversion_report.json` 和 `rejected_episodes.jsonl`。
- 生成 action/state normalization 统计。
- 按 episode 划分 train/val/test，禁止按帧随机打散。
- release 相关帧单独标记，默认不作为普通动作学习。

Depth 第一版可以作为 sidecar 或评估/回放字段保留，不强制进入 pi0.5 主输入；P0 先确保 `d405_rgb + robot_state + action + prompt` 能被训练脚本稳定读取。具体目录结构以实际安装的 LeRobot / OpenPI 版本为准，但本项目必须保留转换报告和字段映射，避免后续无法追溯。

转换后必须用 loader 做 smoke test：

- 随机读取一个 episode。
- 检查 RGB 能正常解码。
- 检查 `observation.state` 维度固定。
- 检查 `action` 维度固定且无 NaN。
- 检查 prompt 与目标工具一致。
- 检查 timestamp 单调递增。
- 检查 train/val/test 没有同一 episode 泄漏。

第一版不建议把所有 MuJoCo 真值状态都塞进 `pi0.5`。工具、人手、接触等真值可以用于筛选、评估和 memory 训练，但 VLA 主输入应尽量靠近未来实机可获得的观测。

5090D 32GB 服务器上的第一版训练边界：

- 只做 LoRA / adapter，不做全参数微调。
- 从小 batch、短序列、低分辨率 RGB 开始。
- 优先保证数据转换、训练启动、checkpoint 保存和 MuJoCo 验证闭环。
- 不把 collaboration memory 放进同一个训练图里一起训练。
- release 相关帧单独标记，避免模型把不安全 release 当作普通动作学习。

### 9.3 模型入库

建议输出到：

```text
models/pi05/handover_lora_runs/<run_id>/
  config.json
  dataset_snapshot.json
  feature_mapping.json
  checkpoints/
  exported/
  offline_eval/
  mujoco_validation/
```

---

## 10. interaction gating

### 10.1 gate 规则

第一版 gate 规则：

```text
release_allowed =
  memory_phase == ready
  and hand_stability_score >= threshold
  and pose_alignment_score >= threshold
  and contact_valid == true
  and safety_status == normal
  and human_hand_tracking_status == tracked
```

强制禁止 release 的情况：

- `memory_phase=hesitation`
- `memory_phase=retreat`
- 人手追踪丢失或低置信度
- 人手与机器人距离低于安全阈值
- 工具未稳定接触人手
- relation feature 缺失或时间戳过旧
- 连续 ready 时间不足最短稳定窗口

### 10.2 runtime

建议新增：

- `backend/policies/handover_policy_runtime.py`
- `backend/policies/interaction_gating.py`
- `backend/policies/action_postprocess.py`

每个控制周期都记录：

- `candidate_action`
- `memory_phase`
- `handover_confidence`
- `release_allowed`
- `gate_reason`
- `gated_action`

如果 `candidate_action` 要 release 但 gate 拒绝，系统应替换为保持夹持、低速等待或 `safe_hold`。

---

## 11. 评估设计

### 11.1 基线

至少需要以下对比：

1. 距离阈值 release：只看人手与工具距离。
2. 瞬时接触 release：只看当前接触状态。
3. `pi0.5` without memory gating：操作模型直接释放或使用简单规则释放。
4. `pi0.5 + collaboration memory + interaction gating`：完整方法。
5. 去掉 history 的消融：只用当前 relation feature，不用 GRU/LSTM 记忆。

### 11.2 指标

必须记录：

- `release_timing_accuracy`
- `unsafe_handover_rate`
- `collision_rate`
- `premature_release_rate`
- `handover_success_rate`
- `handover_drop_rate`
- `hesitation_block_success_rate`
- `retreat_block_success_rate`
- `mean_handover_duration_s`
- `release_delay_ms`

重点指标是提前释放率和危险交接率是否下降，而不只是交接成功率是否上升。

---

## 12. 前后端改造重点

### 12.1 前端

- 在 Three.js 场景中显示 `human_hand`。
- 新增 D405 观测面板，显示末端 RGB、Depth、帧号、有效性和对齐状态。
- 新增 Quest3 `VR采集模式`，支持操作者在头显内完成 precheck、阶段模板选择、开始/停止录制和结果标记。
- 显示左手/右手当前控制对象。
- 显示 handover phase、confidence、release_allowed 和 gate_reason。
- 采集面板支持查看 relation timeline 和 phase timeline。
- 回放界面支持同时查看 RGB-D、机器人、人手、工具、relation feature、candidate/gated action。

### 12.2 后端

- 新增 human hand 状态收集与广播。
- 新增 D405 RGB-D 观测有效性检查、帧索引和落盘接口。
- 新增 relation feature 计算模块。
- 新增 collaboration memory adapter。
- 新增 interaction gating runtime。
- 新增 handover episode recorder。
- 新增 evaluation scripts，输出安全交接指标。

### 12.3 共享配置

建议新增：

- `shared/handover_scene_config.json`
- `shared/human_hand_config.json`
- `shared/relation_feature_schema.json`
- `shared/interaction_phase_schema.json`
- `shared/handover_dataset_schema.json`
- `shared/gating_config.json`
- `shared/d405_observation_check_config.json`

---

## 13. Sim2Real 与数字孪生约束

第一版可以先做 shadow mode，不要求真实 UR5 立即执行完整交接。

必须提前冻结：

- `runtime_target=sim/real_ur5/shadow_real_ur5`
- 高层动作：`joint_target/joint_delta/gripper_target/release_request`
- release 必须经过 memory gate 和 safety gate
- 真实人手状态未来由视觉或外部追踪估计，当前仿真人手字段作为接口占位
- 实机安全机制：限速、急停、watchdog、掉线保护、人工确认开关

真实机械臂验证建议顺序：

1. `shadow_real_ur5`：模型只输出建议动作和 release 决策，不驱动硬件。
2. 低速 replay：只验证动作范围、状态映射和安全停。
3. 低速抓取递送：不自动 release，只验证递送对齐。
4. 人工确认 release：gate 允许后仍需人工确认。
5. 全闭环 release：仅在前面阶段稳定后考虑。

---

## 14. 推荐开发顺序

建议严格按下面顺序推进：

1. 冻结 `quest3_safe_handover_v1` 和 interaction phase。
2. 先完成末端 D405 在 MuJoCo 中的第一轮 RGB-D 观测验证，确认工具、夹爪和 handover zone 可见。
3. 在已有工具场景中加入 human hand。
4. 打通 Quest3 右手控制 human hand。
5. 复测 D405 对 human hand、工具、夹爪关键区域的可见性。
6. 建立 Quest3 VR 沉浸式快速采集入口。
7. 建立双边协作 episode 录制器。
8. 提取 relation feature 并生成 `relations.jsonl`。
9. 按阶段采集 normal、hesitation、retreat、unstable pilot 数据。
10. 完成 phase 标注和回放检查。
11. 训练第一版 GRU/LSTM collaboration memory。
12. 转换 handover manipulation 数据并进行 pi0.5 LoRA 微调。
13. 集成 interaction gating。
14. 完成距离阈值、瞬时接触、without memory 和完整方法对比。
15. 固化 sim2real shadow mode 接口和 release 安全约束。

这条顺序的核心原因是：

- 没有末端 D405 的 MuJoCo 视觉验证，采集到的协作数据就缺少可靠的机器人第一视角。
- 没有 human hand，就没有真实的人机关系数据。
- 没有 VR 沉浸式快速采集入口，操作者就很难稳定地分阶段采集高质量 episode。
- 没有 relation feature，就无法训练协作记忆。
- 没有 hesitation 和 retreat 负样本，模型无法学习阻止危险 release。
- 没有 gating，`pi0.5` 的操作能力无法转化为安全交接能力。
- 没有 shadow mode，后续真实 UR5 验证风险过高。

---

## 15. 当前最重要结论

1. 当前已有基础足够支撑新主线：UR5、工具、工具箱、前后端同步、Quest3 控制和 S4.5 物理边界都已经是可复用资产。
2. 后续主问题不是“工具是否能被放进工具箱”，而是“人是否已经准备好接收工具”。
3. `pi0.5` 负责操作能力，collaboration memory 负责协作关系理解，interaction gating 负责 release 闸门。
4. 协作数据的视觉主观测必须来自机械臂末端 D405，不能用 Quest3 页面画面或 Three.js 外部相机替代。
5. 数据采集必须由操作者在 Quest3 VR 采集模式中阶段化完成，程序不能自动驱动机械臂批量生成正式训练 episode。
6. 安全交接评估必须关注 release timing、unsafe handover、premature release 和 collision，而不是只看成功率。
7. 未来实机迁移时，release 是最高风险动作，必须从接口层保证 memory gate、safety gate 和人工确认机制都有明确落点。
