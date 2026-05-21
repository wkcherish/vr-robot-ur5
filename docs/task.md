# Quest3 工具抓取实验任务书（2026-04-12 修订）

## 1. 文档定位

- 本文档基于 `2026-04-12` 的仓库实际代码状态编写。
- 本轮目标不是改业务代码，而是把现有“电池模块搬运演示”重新整理为“Quest3 示教采集 + pi0.5 初训 + MuJoCo 强化学习微调 + 工具抓取入箱”的详细实施方案。
- 本文档同时服务三类用途：
  1. 开发路线图
  2. 实验记录与验收基线
  3. 后续小论文的方法、实验设置与结果章节草稿

---

## 2. 你的目标（统一表述版）

结合你的说明，当前项目的统一目标应明确为：

1. 在开始 Quest3 / VR 示教任务之前，先完成真实末端相机方案的冻结：以 `Intel RealSense D405` 作为主视觉传感器，并把其安装方式、仿真对应关系、采集字段和标定版本先定义清楚。
2. `D405` 需要以“UR5 末端固定安装的 RGB-D 相机”进入数字孪生，而不是继续沿用当前场景中的 `camera / camera_base` 调试占位物作为主观测来源。
3. Quest3 通过局域网访问现有前端，并作为 UR5 机械臂的示教/遥操作入口。
4. 由你本人通过 Quest3 在 MuJoCo 数字孪生场景中手动示教采集抓取工具的数据集，系统负责录制、存档与回放。
5. 采集的数据不只是关节角和控制量，而应至少包含：末端 `RGB-D` 观测、机器人状态、任务文本和动作标签，以满足 `pi0.5` 这类 VLA 训练的基础要求。
6. 由你先用采集的数据对 `pi0.5` 做初步模仿学习或行为克隆训练，并将初训模型存入模型目录。
7. 初训模型可以在需要时加载回 MuJoCo 做仿真验证；强化学习微调后的模型也同样可以回到 MuJoCo 再验证。
8. 已完成：将电池模块场景替换为“桌面随机工具 + 工具箱”场景，且前后端资产、状态和交互保持同步；S4.5 已补齐物理边界，解决前后端虚拟干涉导致的明显穿模问题。
9. 最终目标任务是：UR5 从桌面随机位置抓取工具，并将工具放入工具箱，即完成“工具入库”。
10. VR 交互采用“非沉浸式优先”的设计，不重做整套沉浸式场景，而是在现有界面基础上扩展 Quest3 输入模式。
11. 强化学习环境、模型加载接口、MuJoCo 验证入口和微调流程由系统侧负责搭建；数据采集与初训由你执行。
12. 建立专门的数据集目录、模型目录、日志目录和实验目录，为后续训练复现和论文写作做准备。
13. 整个流程从一开始就要考虑 `sim2real`，即最终强化学习微调后的权重不仅能在 MuJoCo 中运行，还应具备迁移到真实 UR5 机械臂上的可行性。

建议将新的实验主任务统一命名为：

`quest3_tool_sorting_v1`

旧占位任务名 `battery_transfer_v1` 可以短期兼容保留，但后续文档、训练脚本、实验记录与 UI 表达都应逐步切换到新的任务名，避免“代码在做工具、文档还在写电池”的混乱。

---

## 2.1 角色分工与责任边界

为了避免后面“谁负责采集、谁负责训练环境、谁负责验证”再次混淆，这里把责任边界明确写死：

### 你负责的部分

- 使用 Quest3 进行手动示教采集
- 控制每个采集 session / episode 的开始与结束
- 检查采集数据是否可用
- 使用采集数据完成第一轮 `pi0.5` 初步训练
- 将训练完成的初训模型放入约定的模型目录
- 参与检查初训模型与强化学习模型在 MuJoCo 中的验证结果

### 系统与代码侧需要提供的部分

- Quest3 局域网接入能力
- Quest3 手柄模式与手势模式控制链
- 数据录制、存档、回放和元数据管理
- 模型目录规范与模型加载接口
- 初训模型加载到 MuJoCo 的验证入口
- 强化学习环境、奖励、随机化和微调流程
- 强化学习后模型再次加载回 MuJoCo 的验证入口

### 必须遵守的顺序原则

- 数据采集由你完成，不由系统自动生成专家数据。
- 初训模型不是训练完就结束，而是建议先入库，并支持回到 MuJoCo 中验证。
- 强化学习也不是单独黑盒训练，而是要加载初训模型或以初训模型为基线继续优化。
- 每一个阶段训练得到的模型，只要进入模型目录，就应当支持被加载到 MuJoCo 中单独查看和验证。
- 即使当前先在仿真中完成主要实验，控制接口、动作空间、观测空间、关节顺序和部署入口也应按后续可迁移到真实 UR5 的方向设计。

## 2.2 Sim2Real 总约束

你这次补充的要求非常关键：最终强化学习训练好的权重，希望不是只停留在 MuJoCo 中，而是后续可以迁移到真实机械臂。  
因此 `sim2real` 不应被当成最后才看的附加项，而应当是贯穿整个项目的设计约束。

### 2.2.1 这句话在项目里意味着什么

在本项目中，“考虑 sim2real”建议明确理解为：

- 仿真中的控制接口不能和真实机械臂未来的控制接口完全割裂
- 模型输出不能只适配 MuJoCo 内部的临时动作形式
- 训练时使用的观测字段，应尽量与实机可获取字段保持一致
- 机器人关节顺序、夹爪语义、任务目标和工具状态表达，都要可映射到真实系统
- 强化学习中的随机化、噪声和延迟建模，需要提前为 sim2real 服务

### 2.2.2 需要从现在就坚持的一致性约束

后续所有设计，建议遵守以下一致性：

1. 控制一致性  
仿真端和实机端尽量共用一套高层动作定义，例如“6 轴关节目标 + 夹爪开合量”。

2. 状态一致性  
训练和推理使用的核心状态字段，应尽量来自后续实机也能获得的信息。

3. 坐标一致性  
桌面、工具箱、工具、末端执行器的坐标定义，需要能与实机标定流程对齐。

4. 节奏一致性  
Quest3 控制频率、后端控制频率、策略推理频率，要为后续实机运行留出空间。

5. 部署一致性  
初训模型和 RL 模型的加载入口，最好都复用同一套策略加载接口，避免仿真与实机两套代码。

### 2.2.3 从现在起必须额外考虑的技术点

- 真实 UR5 与 Robotiq 的控制接口适配
- 实机关节状态回读与夹爪状态回读
- 仿真与实机模式切换
- 桌面与工具箱位姿标定
- 实机安全联锁、限速、急停和 watchdog
- 训练中的 domain randomization
- 视觉、延迟、摩擦、质量和接触误差对策略迁移的影响

### 2.2.4 对当前实验路线的影响

这意味着后续不应该把系统只做成“仿真里能跑的 demo”，而应尽量做成：

- Quest3 负责人工示教采集
- MuJoCo 负责数据采集、初训验证和 RL 微调
- 策略加载器既能服务 MuJoCo 验证，也能服务未来实机部署
- 真实 UR5 接入时主要替换底层执行器，而不是完全推翻上层训练与推理接口

### 2.2.5 Sim2Real 就绪检查表

| 维度 | 当前阶段建议约束 | 后续落地目标 |
| --- | --- | --- |
| 动作接口 | 统一使用“6 轴关节目标/增量 + 夹爪开合量” | 同一策略头既能接 MuJoCo，也能接真实 UR5 控制适配层 |
| 观测接口 | 优先使用实机也能获得的关节、夹爪、工具位姿、目标槽位字段 | 避免训练时依赖实机拿不到的临时内部量 |
| 坐标体系 | 桌面、工具箱、工具、末端执行器统一基坐标定义 | 后续可接入标定结果并直接映射到实机 |
| 时序节奏 | 记录 Quest3 输入频率、后端控制频率、策略推理频率 | 为实机控制周期、限速和延迟补偿预留空间 |
| 安全机制 | 文档先冻结 watchdog、限速、急停、掉线保护要求 | 实机接入时直接落到控制适配器与运行时 |
| 模型部署 | 初训模型与 RL 模型走统一的注册、导出、加载接口 | 形成“同一模型目录 -> 仿真验证 / 实机部署”双出口 |

## 3. 基于当前代码的现状复核

这一节很重要。当前仓库已经不是“只有前端、没有后端”的状态，旧文档明显落后于主分支实际代码。

### 3.1 已完成的真实基线

当前主分支已经具备以下基础能力，这部分应被视为后续工作的继承资产，而不是重新从零开始：

#### 3.1.1 共享场景与基线配置

- 已有 `shared/scene_manifest.json`。
- 已在清单中定义：
  - UR5 基座变换
  - 机器人 home 姿态
  - `rack`
  - `toolbox`
  - `wrench_01`
  - `screwdriver_01`
  - `pliers_01`
  - `camera_base`
  - `camera`
- 已明确夹爪的高层语义输入 `gripper_opening` 与关键关节集合。

补充说明：

- 当前 `scene_manifest` 中的 `camera_base` 与 `camera` 是旧版场景调试资产。
- 这两个对象目前只能视为“参考相机 / 对齐占位物”，不能视为本实验真正要训练和部署的视觉主传感器。
- 后续真正的主视觉链路应切换为“安装在 UR5 末端的 `Intel RealSense D405 RGB-D` 相机”。

#### 3.1.2 后端服务骨架

当前仓库已经有真实后端，不再是预留目录：

- `backend/api_app.py`：FastAPI 入口
- `backend/schemas.py`：协议模型
- `backend/sim/simulation.py`：仿真核心
- `backend/main.py`：统一启动入口，支持拉起后端并可选打开 MuJoCo viewer

现有后端接口包括：

- `GET /health/`
- `GET /sim/state/`
- `POST /sim/step/`
- `POST /sim/reset/`
- `WebSocket /sim/ws`
- 兼容旧逻辑的 `GET /data/`

#### 3.1.3 MuJoCo 场景资产

当前仓库已经有 MuJoCo XML 与 mesh，而不是空壳：

- `backend/mujoco_models/environment.xml`
- `backend/mujoco_models/ur5.xml`
- `backend/mujoco_models/rack.xml`
- `backend/mujoco_models/toolbox.xml`
- `backend/mujoco_models/wrench.xml`
- `backend/mujoco_models/screwdriver.xml`
- `backend/mujoco_models/pliers.xml`
- `backend/mujoco_models/camera_base.xml`
- `backend/mujoco_models/camera.xml`
- `backend/mujoco_models/meshes/`

说明：

- UR5 + Robotiq 结构已经进入 MuJoCo 模型。
- `environment.xml` 已切换为包含 `toolbox + wrench + screwdriver + pliers` 的工具入库场景。
- `battery_pack.xml` 仍保留在仓库中作为历史资产，但当前任务默认不再加载。

#### 3.1.4 前后端状态同步基线

当前代码已经具备“前端 <-> 后端”双向映射基础：

- 前端 `frontend/src/utils/websocket.js` 已支持：
  - `control`
  - `reset`
  - `get_state`
  - `execute_task`
  - `stop_task`
- 前端 `frontend/src/App.vue` 已能：
  - 发送机械臂关节控制命令
  - 发送夹爪开合命令
  - 接收后端 `state_update` / `state_broadcast`
  - 将后端 `qpos` 映射到 UR5 与夹爪显示
  - 将 `toolbox + wrench_01 + screwdriver_01 + pliers_01` 位姿从后端同步回 Three.js 场景
- 前端已经加入：
  - 状态缓冲
  - 连接质量统计
  - 简单插值
  - 手动命令防回弹保护

#### 3.1.5 MuJoCo 桌面 viewer 桥接

`backend/main.py` 已经不是简单启动器，而是包含一个有价值的桥接器：

- 可以拉起 FastAPI 后端
- 可以打开 MuJoCo desktop viewer
- 可以从 viewer 端读取本地编辑后的关节/夹爪目标
- 可以把这些改动再推回后端 `/sim/step/`
- 可以从后端 `/sim/state/` 回拉状态并覆盖 viewer 显示

这说明“局部双向控制关系”已经存在，后续并不是从 0 写到 1，而是从“桌面 viewer 桥接 + 前后端同步基线”继续往 Quest3 和数据采集方向扩展。

#### 3.1.6 关节限位双侧裁剪（2026-05-11 新增）

VR / 手动控制大幅累加目标关节角时，可能直接越过 UR5 的物理 `jnt_range`，造成 MuJoCo 解算报警或末端姿态翻飞。本轮已经把“关节限位裁剪”落到前后端两侧，作为后续 Quest3 采集与 RL 微调的安全前置：

- 后端 `backend/sim/simulation.py`：
  - `SimulationCore` 新增 `_arm_joint_limits` 缓存，加载模型时读取 `jnt_limited` / `jnt_range`，按关节名记录 `(lo, hi)`。
  - 新增 `_clamp_arm_targets`，在 `_apply_arm_command` 中对所有来源（`manual` / `vr` / `replay` 等）的目标关节角执行逐维裁剪，再做 blend 与积分。
  - 状态接口（`state_broadcast` / `state_update`）的 payload 中追加 `joint_limits` 字段，与 `joint_names` 同序对外公布。
- 前端 `frontend/src/utils/websocket.js`：
  - `handleStateUpdate` 中缓存 `jointNames` 与 `jointLimits`，供发送链路即时复用。
  - `sendControlCommand` 在组装 `target_positions` 时调用新增的 `clampToJointLimits`，先按后端公布的限位完成预裁剪，避免越界值进入 WebSocket。

形成的安全模型为：前端预裁剪保证“可视控件 / VR 增量”不会发出违法目标，后端兜底裁剪保证“跨客户端、跨任务源”的命令也无法绕过物理限位。该机制对后续数据集采集（避免越界帧污染示教数据）与 RL 微调（动作空间和真实硬件保持一致）都是必备前置。

#### 3.1.7 物理边界与前后端虚拟干涉修复（S4.5 已完成）

S4.5 阶段已经从“泛化接触稳定大包”收敛为“物理边界与前后端虚拟干涉修复”。当前已完成的结论是：桌面、工具箱、工具对象、夹爪和 UR5 工作区已经具备一致的前后端物理边界基线，手动控制和 Quest3 控制下不再出现明显穿桌、穿箱、穿工具等虚拟干涉问题。

本阶段完成内容包括：

- 前端 Three.js 可视对象与后端 MuJoCo 对象统一使用同一对象 ID、位姿和尺寸基线。
- 桌面、工具箱、工具对象和夹爪交互区域已经补齐可用物理边界。
- 工具 reset 后的位姿约束已经纳入物理边界检查，避免悬空、穿桌、翻立或与工具箱 / 其他工具明显重叠。
- 手动控制和 Quest3 控制复用同一边界基线，避免不同输入源产生不同干涉表现。

需要注意：S4.5 的完成不等于完整工具抓取任务闭环已经完成。抓取成功判定、临时附着、释放校验和放置成败状态机仍属于后续任务闭环与录制筛选阶段。

### 3.2 当前仍未完成的部分

虽然基线已经存在，但以下关键环节仍基本未落地：

#### 3.2.1 任务执行仍是 stub

- `execute_task` 目前只是把任务状态标为 running。
- 没有真正的任务运行器。
- `backend/tasks/` 目录目前为空。
- 没有脚本化的完整“抓取 -> 搬运 -> 放置”任务闭环。

#### 3.2.2 抓取判定与附着机制未落地

当前代码中：

- `attached_to_gripper` 仍始终为 `false`
- 没有抓取成功判定
- 没有释放成功判定
- 没有对象 weld/constraint 或等效附着逻辑
- 没有掉落、碰撞、放置成败的状态机

这意味着当前系统最多只是“能控制机械臂和夹爪”，但还不是“已经具备任务闭环”。

#### 3.2.3 当前“工具识别”已完成基础替换，但任务闭环仍是占位逻辑

`frontend/src/components/control.vue` 当前状态是：

- 已从 `state.objects` 动态提取工具对象，并过滤 `rack`、`camera`、`camera_base`、`toolbox`
- 已按 `wrench / screwdriver / pliers` 分类展示名称和图标
- 抓取、移动、放置仍以预设流程命令为主
- 仍未接入逆运动学求解
- 仍未接入真实抓取判定与工具箱槽位约束

因此当前 UI 里虽然已经有“识别桌面工具 / 抓取工具 / 放置工具”的入口，但仍不能视为真实任务功能已经完成。

#### 3.2.4 VR / Quest3 已完成基础控制，但尚未接入正式采集闭环

根据 `2026-04-24` 的修复记录，当前仓库已经不能再按“VR / Quest3 能力尚不存在”来描述。  
现阶段应修正为：Quest3 控制链路已经具备基础可用性，但还没有完成与正式数据集采集器、安全校验和回放筛选的闭环绑定。

当前已完成或已具备基础的部分包括：

- Quest3 局域网访问与 `VR模式` 入口
- 手柄模式与手势模式的基础控制链路
- 关节组选取、夹爪连续控制与输入状态同步
- VR 状态广播、节流、in-flight 控制和超时回收
- 手柄/手势输入源写入控制消息的基础字段

当前仍不能视为完成正式采集的原因是：

- `recording_ready` 还需要由后端采集前置检查硬性驱动，而不能只由前端状态估计
- Quest3 控制命令还需要和 `dataset_recorder` 的 step 级写盘严格对齐
- S4.5 物理边界与 reset 合法性基线已经完成，但接触/抓取状态仍需要进入状态广播和数据集日志
- 还需要回放器、预览视频和 `validation_summary.json` 来筛选 episode

因此，后续工作不是从零实现 VR 控制，而是在已有 VR 控制基础上补齐“安全采集闭环”。

#### 3.2.5 数据集与训练基础设施尚不存在

当前仓库尚未建立：

- 专门的数据集目录
- 专门的模型目录
- session / episode 管理
- 采集录制器
- 数据回放器
- `pi0.5` 训练脚本
- RL 环境
- RL 微调脚本
- 评估脚本

`backend/rl/` 当前仅是空目录初始化，不具备训练功能。

#### 3.2.6 末端 RGB-D 相机链路已完成基础定义，但尚未完成正式落盘验证

当前仓库已经具备末端 `D405 RGB-D` 的基础定义和观测接口，不应再写成完全不存在：

- 已有 `shared/camera_sensor_config.json` 冻结 `Intel RealSense D405`、安装名、相机内外参版本和 `RGB/Depth` 输出规格
- 已有 `shared/dataset_schema.json` 将 `RGB-D + 状态 + 动作 + 文本` 定义为采集必需模态
- MuJoCo 侧已有末端 D405 相机挂载与 `d405_rgb / d405_depth` 相机名
- 后端已有 `/sim/observation/`、`/sim/camera/rgb/`、`/sim/camera/depth/` 等观测接口

但它距离“可以正式采集训练数据”仍差一步闭环验证：

- 需要确认返回帧不是 stub / fallback 图像
- 需要通过 smoke recording 验证 RGB、Depth、状态、动作、文本可以同步落盘
- 需要保存逐帧文件、视觉索引和 MP4 预览视频
- 需要 episode 结束后生成 `validation_summary.json`
- 需要回放器能逐帧检查 RGB、Depth、状态、动作和接触/安全时间轴

因此，当前视觉链路可以作为数据采集开发基础，但正式采集前必须先完成落盘、回放和完整性校验。

#### 3.2.7 场景资产已切换为工具版本（已完成）

当前前后端默认主场景已使用：

- `frontend/public/tools/urdf/toolbox.urdf`
- `frontend/public/tools/urdf/wrench.urdf`
- `frontend/public/tools/urdf/screwdriver.urdf`
- `frontend/public/tools/urdf/pliers.urdf`
- `backend/mujoco_models/toolbox.xml`
- `backend/mujoco_models/wrench.xml`
- `backend/mujoco_models/screwdriver.xml`
- `backend/mujoco_models/pliers.xml`
- `shared/scene_manifest.json` 与 `shared/tool_catalog.json`

已完成能力：

- 工具状态注册表
- 多工具随机生成逻辑
- 前后端按 manifest 一一对应同步对象位姿

### 3.3 对旧 ToDo 的客观结论

基于 `2026-04-10` 的实际代码复核，可以对旧版里程碑做如下判断：

| 旧里程碑 | 代码复核结论 |
| --- | --- |
| 里程碑 0 | 基本完成 |
| 里程碑 A | 基本完成 |
| 里程碑 B | 基本完成 |
| 里程碑 C | 基本完成，但缺少更系统的验证材料 |
| 里程碑 D | “手动双向同步基线”基本完成；“任务/策略闭环同步”未完成 |
| 里程碑 E 以后 | 基本未完成或只有界面/协议占位 |

结论很明确：

- 现阶段最有价值的已有资产，是“前后端场景与状态同步基础”。
- 现阶段最大的工作量，不在基础通信，而在“任务、VR、数据、训练、评估”。

---

## 4. 新实验范围定义

### 4.1 新场景定义

新场景建议由以下对象组成：

- UR5 + Robotiq 2F-85
- 安装在 UR5 末端的 `Intel RealSense D405 RGB-D` 相机
- 桌面 / 工作台
- 工具箱
- 工具对象集合
- 可选的参考相机或调试相机
- 可选的桌面随机投放区域标记

#### 4.1.1 2026-04-12 场景冻结参数（前后端一一对应）

以下参数以 `shared/scene_manifest.json` 与 `shared/tool_catalog.json` 为唯一真值，前端与 MuJoCo 必须严格对齐：

| 对象 | position (m) | rotation_rpy (rad) | scale 基线 |
| --- | --- | --- | --- |
| `toolbox` | `[0.48, 0.5, -0.2]` | `[-1.5707963267948966, 0.0, -1.5707963267948966]` | `0.32` |
| `wrench_01` | `[0.08, 0.5240336800934792, 0.3]` | `[0.0, 0.0, 0.0]` | `0.13` |
| `screwdriver_01` | `[0.2, 0.5, 0.26]` | `[-1.5707963267948966, 0.0, 0.0]` | `0.13` |
| `pliers_01` | `[0.28, 0.5100852437109232, 0.12]` | `[0.0, 0.0, 0.0]` | `0.13` |

说明：

- 工具箱当前姿态为“开口朝上、放置在桌面上、长边不带盖侧朝向机械臂”。
- 位置与姿态取自 `scene_manifest`，缩放基线取自 `tool_catalog.physics_baseline.scale`。

#### 4.1.2 工具箱槽位冻结参数

| 槽位 | 工具类别 | position (m) | size (m) |
| --- | --- | --- | --- |
| `slot_wrench` | `wrench` | `[0.46, 0.54, -0.175]` | `[0.11, 0.04, 0.04]` |
| `slot_screwdriver` | `screwdriver` | `[0.48, 0.54, -0.2]` | `[0.04, 0.12, 0.04]` |
| `slot_pliers` | `pliers` | `[0.46, 0.54, -0.225]` | `[0.11, 0.04, 0.04]` |

### 4.2 工具对象范围

当前代码已落地的第一版范围如下：

建议拆成两层：

#### V1 必做对象

- 扳手 `wrench`
- 螺丝刀 `screwdriver`
- 钳子 `pliers`
- 工具箱 `toolbox`

#### V2 可选扩展对象

- 螺栓 `bolt`
- 六角扳手 `hex_key`
- 锤子 `hammer`

### 4.3 任务目标定义

建议把第一版任务明确成：

“机械臂在桌面随机位置抓取指定工具，并放入工具箱指定区域，完成工具入库。”

第一版的约束建议：

- 工具初始位置在桌面随机采样
- 工具姿态只做有限随机化
- 每个 episode 出现 1 到 2 个工具实例即可
- 工具箱目标槽位可以先固定
- 先不做复杂装配动作，只做：
  - 接近
  - 抓取
  - 抬升
  - 搬运
  - 放入工具箱

### 4.4 为什么不建议第一版做太多工具

原因有三点：

1. 你的论文核心并不是“物体种类越多越好”，而是“Quest3 数据采集 + 模仿学习 + RL 微调”这条实验链是否成立。
2. 工具过多会显著增加：资产处理、碰撞调参、抓取策略难度、数据标注成本。
3. 当前工具场景已经切换完成，先把 `wrench + screwdriver + pliers` 这 3 类工具做稳，比一次上 6 类工具更利于项目收敛。

### 4.5 末端 D405 相机定义

这部分从现在起应视为主场景冻结项，而不是后续可有可无的优化项。

#### 4.5.1 主传感器选型冻结

- 主视觉传感器冻结为：`Intel RealSense D405`
- 模态冻结为：`RGB-D`
- 安装位置冻结为：`UR5 + Robotiq` 末端执行器附近的固定安装位
- 后续 `pi0.5` 路线默认以“末端 `RGB-D` + 机器人状态 + 任务文本 + 动作标签”为训练输入基础

#### 4.5.2 已有资产与安装参考

当前你已经准备好的与相机相关的本地资产包括：

- `frontend/public/camera/mesh/d405.stl`
- `frontend/public/camera/mesh/前半.STL`
- `frontend/public/camera/mesh/后半.STL`
- `pic/camera.jpg`

其中：

- `d405.stl` 对应相机主体
- `前半.STL` 与 `后半.STL` 对应安装到机械臂末端的夹持/连接结构
- `camera.jpg` 提供了真实安装方式的视觉参考，应作为后续仿真挂载姿态的第一依据

#### 4.5.3 安装参考图对应的结构理解

根据 `pic/camera.jpg`，建议在文档层先冻结以下安装认知：

- `D405` 安装在夹爪上方附近、靠近末端法兰/手抓本体的位置
- 相机主体位于末端侧方，朝向抓取工作区而不是朝向机器人本体
- 安装支架是一个包裹式或夹持式的两片结构，对应你已准备好的 `前半.STL` 与 `后半.STL`
- 线缆从相机顶部或后侧引出，因此仿真与后续实机接线都要给线缆留出运动空间

#### 4.5.4 仿真中需要对应的不是“相机模型”，而是“相机传感器”

后续在 MuJoCo 中不能只做以下事情：

- 把 `d405.stl` 放到末端

还必须同时完成：

- 明确相机相对 `tool0` 或 `wrist_3_link` 的固定外参
- 提供可录制的 `RGB` 图像输出
- 提供可录制的 `Depth` 图像输出
- 明确 `RGB` 与 `Depth` 是否对齐、时间戳如何对齐
- 为数据集记录器输出可索引的视觉观测路径和元数据

#### 4.5.5 当前场景调试相机的处理原则

从现在开始应把两类相机严格区分：

- `camera / camera_base`：调试相机、对齐占位物、论文示意或场景观察用途
- `D405`：训练、采集、sim2real 对齐所依赖的主传感器

因此后续文档与实现都应遵守：

- `camera / camera_base` 不能再被写成主采集相机
- 如果保留它们，也只作为 `debug_only` 对象存在
- `D405` 才是 VR 示教、数据录制和 VLA 训练真正要使用的视觉源

#### 4.5.6 为什么必须把 D405 放在 VR 之前

原因非常直接：

1. 如果先做 Quest3 控制、后补相机，那么前面采到的数据集很可能无法直接用于 `pi0.5`
2. 如果先采“无视觉”数据、后想改成 `RGB-D`，数据格式、回放器和训练脚本都会返工
3. `D405` 是实机固定安装在末端的，因此它的位姿、视角、时序和噪声本来就是 `sim2real` 主约束之一
4. 你后面不是只做低维策略，而是希望走 `pi0.5` VLA 路线，所以视觉输入必须从最开始就进入数据规范

---

## 5. Quest3 交互目标定义

在进入这一章之前，默认前提应改为：

- 末端 `D405 RGB-D` 相机已经作为主视觉传感器完成场景接入定义
- 仿真侧已经明确末端相机挂载位姿与 `RGB-D` 输出接口
- 数据录制协议已经为视觉帧、状态、动作和任务文本预留字段

也就是说：

- Quest3 不是视觉链路的替代品
- Quest3 的角色是“人工示教控制输入”
- `D405` 的角色是“主观测传感器”

### 5.1 访问方式

- Quest3 通过局域网访问前端页面。
- 建议保留桌面浏览器入口和 Quest3 浏览器入口共用同一个前端项目。
- 需要支持通过局域网 IP 直接访问，例如：

```text
http://<host-ip>:<frontend-port>
```

- 前端应提供简洁的局域网接入提示，例如：
  - 当前主机 IP
  - 建议端口
  - 后端服务状态
  - Quest3 是否已连接

#### 5.1.1 局域网连接前提

Quest3 局域网连接要想稳定，文档里建议直接写清楚以下前提：

- Quest3 与开发主机必须连接到同一个局域网
- 前端服务必须监听 `0.0.0.0`
- 后端服务必须允许局域网访问
- WebSocket 地址不能再写死为仅本机可访问的形式
- 局域网内的防火墙、端口和跨域策略要提前检查

推荐的运行链路是：

1. 主机启动前端服务
2. 主机启动后端服务
3. 主机确认 `health`、`/sim/ws`、前端首页都可访问
4. Quest3 浏览器访问前端地址
5. 前端自动检测 Quest3 访问环境并展示 `VR模式` 入口

#### 5.1.2 Quest3 接入后的控制启动顺序

当 Quest3 已经通过局域网进入页面后，机械臂控制顺序建议固定为：

1. 前端检测 Quest3 端能力、后端在线状态以及末端 `D405` 数据流是否已可用
2. 用户点击“连接机器人”或由系统自动建立 WebSocket
3. 前端确认当前 episode 将记录 `RGB-D + 状态 + 动作 + 文本`
4. 用户点击 `VR模式`
5. 用户选择 `手柄模式` 或 `手势模式`
6. 前端开始从 Quest3 输入设备读取数据
7. 前端将 Quest3 输入转换为 UR5 关节组控制命令
8. 前端通过 WebSocket 将控制命令发给后端
9. 后端在 MuJoCo 中执行一步或多步控制，并同步产出该步对应的末端 `RGB-D` 观测
10. 后端通过 `state_update` / `state_broadcast` 把最新机器人和对象状态回传前端
11. 录制器将当前步的视觉、状态、动作、文本统一写入 episode
12. 前端同步更新机械臂显示、工具对象显示和录制器状态

#### 5.1.3 Quest3 局域网连接后的控制源定义

为了后续调试和论文记录，建议把“手动控制”再细分成更明确的来源：

- `desktop_manual`：桌面端鼠标/滑块/输入框控制
- `quest3_controller`：Quest3 手柄模式控制
- `quest3_hand`：Quest3 手势模式控制
- `task`：脚本化任务控制
- `policy_initial`：初训模型推理控制
- `policy_rl`：强化学习后模型推理控制

说明：

- 当前代码里的 `source` 只有 `manual | task | policy`，这是现有实现。
- 后续文档与协议建议在不破坏现有兼容性的前提下，增加更细粒度的 `input_source` 或 `policy_stage` 字段。

### 5.2 模式要求

用户要求是“非沉浸模式”。这里必须明确解释，否则后期很容易实现跑偏。

本项目中“非沉浸模式”建议定义为：

- 不重做一个完全独立的沉浸式 3D VR 应用
- 保留当前主界面和主场景结构
- Quest3 端优先以“现有前端 + 额外输入层 / HUD”的方式工作
- VR 模式更像“Quest3 输入与控制模式”，而不是“完全替代当前界面的全屏新界面”

### 5.3 关键技术边界说明

Quest 浏览器对手柄与手势输入的可用能力，很可能与 WebXR session 绑定。  
因此“非沉浸模式”在技术实现上建议理解为：

- 视觉和交互布局上保持非全屏沉浸体验
- 保留现有 UI，不覆盖现有场景中心视图
- 底层如果必须开启轻量 XR 会话来读取 Quest3 输入，这是允许的实现细节

换句话说，本项目追求的是“非全屏沉浸式体验”，而不是“完全不用 XR API”。

### 5.4 前端按钮与菜单要求

当前底部按钮中已有“状态同步”。根据你的新需求，应调整为：

- 将 `状态同步` 入口升级或替换为 `VR模式`
- 将数据集采集入口放在前端底部导航栏，与 `VR模式` 同级但职责分离
- 点击 `VR模式` 后：
  - 桌面端显示：VR 连接状态、局域网说明、Quest3 接入提示
  - Quest3 端显示：VR 模式选择菜单
- 点击 `采集` 或 `录制` 入口后：
  - 显示采集前置检查结果
  - 显示当前 session / episode / 目标工具 / 任务文本
  - 只在 `recording_ready=true` 时允许进入正式录制
  - 未通过检查时只能启动 `debug_trial`

Quest3 端模式菜单必须包含：

- 手柄模式
- 手势模式
- 退出 VR 模式

采集入口建议采用底部导航栏中的一个独立按钮或按钮组：

- `采集`：打开采集面板
- `开始录制`：通过检查后开始 episode
- `停止录制`：结束 episode 并触发保存与校验

如果底部空间不足，建议底部只保留一个 `采集` 主按钮，点击后在右侧窄面板或底部轻量抽屉里展示 `开始录制 / 停止录制 / debug_trial / 当前状态`。  
这样既符合“采集是主流程入口”的重要性，也不会让底部导航栏塞满高风险按钮。

### 5.5 菜单布局要求

你特别强调“这个界面不能覆盖现有界面”，因此模式菜单必须满足：

- 非模态
- 非全屏
- 不遮挡场景中心区域
- 不阻断现有底部控制栏的主要可视性
- 不让 `开始录制` 与普通控制按钮视觉混淆
- 录制中必须持续显示明显但不遮挡操作的状态，例如 `REC`、episode ID 和当前目标工具

推荐形式：

- 右上角浮层
- 右侧窄抽屉
- 底部悬浮卡片
- 底部导航栏保留入口，详细采集控制放入二级面板

不推荐形式：

- 全屏弹窗
- 整屏遮罩
- 覆盖整个 WebGL 画布中心的对话框
- 把 `开始录制`、`停止录制`、`重置`、`VR模式` 全部平铺成同等视觉权重，导致 Quest3 中误触

### 5.6 底部采集入口的推荐状态机

底部导航栏中的 `采集` 入口建议只承担两个职责：

1. 提醒用户当前是否可以采集。
2. 打开二级采集面板。

真正的 `开始录制`、`停止录制`、`保存结果` 和 `人工剔除` 操作，建议放到二级采集面板里。  
这样做的好处是：底部导航栏保持稳定，Quest3 中不容易误触，同时采集流程仍然足够显眼。

建议前端维护以下采集 UI 状态：

| 状态 | 底部入口表现 | 面板允许操作 | 说明 |
| --- | --- | --- | --- |
| `idle` | `采集` | 打开面板、刷新检查 | 未创建 episode |
| `checking` | `检查中` | 暂停开始按钮 | 正在执行采集前置检查 |
| `ready` | `可录制` | `开始正式录制`、`开始 debug_trial` | 所有 P0 检查通过 |
| `debug_only` | `仅调试` | `开始 debug_trial` | 相机、reset 或安全壳未通过 |
| `recording` | `REC` | `停止录制`、查看状态 | 正在写入 episode |
| `finalizing` | `保存中` | 禁止重复点击 | 正在写入结果、校验和预览 |
| `completed` | `已保存` | 查看摘要、打开回放 | episode 已结束 |
| `error` | `采集异常` | 查看错误、重试检查 | 录制或保存失败 |

底部入口不要只显示布尔值，建议至少显示：

- 当前状态：`可录制 / 仅调试 / REC / 保存中 / 异常`
- 当前 episode ID
- 当前目标工具
- 简短错误原因，例如 `camera_missing`、`reset_invalid`、`safe_hold`

### 5.7 采集面板最小功能

第一版采集面板不需要做复杂的数据管理系统，但必须包含以下最小功能：

| 区域 | 必需内容 |
| --- | --- |
| 采集前置检查 | 后端、WebSocket、MuJoCo、D405 RGB、D405 Depth、状态流、reset 合法性、安全壳 |
| episode 配置 | 目标工具、目标槽位、任务文本、采集等级、输入模式 |
| 录制控制 | 刷新检查、开始正式录制、开始 debug_trial、停止录制 |
| 实时状态 | RGB/Depth 帧号、状态样本数、动作样本数、写盘状态、碰撞拦截次数 |
| 结束摘要 | 是否保存成功、是否通过校验、是否可成为 `train_candidate`、剔除原因 |
| 快速查看 | 打开 RGB 预览视频、查看 Depth 伪彩、查看时间轴 |

面板中的按钮启用规则应严格一些：

- `开始正式录制`：仅当 `recording_ready=true` 且 `safety_status=normal` 时启用
- `开始 debug_trial`：允许在检查不完整时启用，但必须写入 `recording_tier=debug_trial`
- `停止录制`：仅在 `recording` 状态启用
- `reset`：录制中禁用，避免 episode 初始条件被破坏
- `VR模式切换`：录制中如果切换输入源，必须写入异常标记或自动结束 episode

### 5.8 采集入口位置是否可行

将采集按钮放在前端下面导航栏是可行的，而且适合本项目。

理由如下：

1. 数据采集是主流程，不应该藏在调试菜单里。
2. 底部导航栏已经承载 `VR模式` 等运行入口，采集入口与它同级符合操作顺序。
3. Quest3 中视线和手柄指向操作更容易稳定点击底部固定入口。
4. 采集状态需要持续可见，底部 `REC / episode / target tool` 很适合做常驻提示。

但有两个约束必须遵守：

- 底部只放 `采集` 主入口和录制状态，不把所有危险操作平铺出来。
- `开始录制` 必须由二级面板承载，并受采集前置检查控制。

因此推荐布局是：

```text
底部导航栏：
[连接/状态] [VR模式] [采集: 可录制/REC] [任务/策略] [设置]

采集面板：
前置检查 -> episode 配置 -> 开始/停止 -> 实时计数 -> 结束摘要 -> 回放入口
```

---

## 6. VR 控制方案定义

这一部分直接对应你给的第二张图。

### 6.1 手柄模式

建议固定为“左手选组、右手控制、右 Trigger 控夹爪”的结构。

#### 6.1.1 关节分组

- 大臂组：`shoulder_pan_joint` + `shoulder_lift_joint`
- 前臂组：`elbow_joint` + `wrist_1_joint`
- 腕部组：`wrist_2_joint` + `wrist_3_joint`

#### 6.1.2 按钮映射

按你截图中的逻辑，建议采用：

- 左手 `X`：切换或选择大臂组
- 左手 `Y`：切换或选择前臂组
- 左手 `Grip`：切换或选择腕部组
- 右摇杆上下：控制当前组第一个关节
- 右摇杆左右：控制当前组第二个关节
- 右 `Trigger`：连续控制夹爪开合

#### 6.1.3 手柄模式的实现要求

- 前端要持续显示当前关节组
- 当前组切换后要有明显但不遮挡场景的提示
- 关节变化应支持速度缩放，避免 Quest 输入抖动造成大幅突变
- 夹爪输入应支持连续量，而不是只有开/关两态

### 6.2 手势模式

建议优先实现“双手模式”，同时保留“单手降级模式”，避免 Quest3 手部追踪不稳定时完全不可用。

#### 6.2.1 双手模式建议

- 左手负责关节组选择
- 右手负责当前组的连续控制
- 右手食指捏合并拖动：控制当前关节组两个自由度
- 右手中指或指定手势：控制夹爪开合
- 预留横向微调或位姿微调模式，但可以放到第二阶段

#### 6.2.2 单手降级模式建议

当只有一只手稳定追踪时：

- 无名指捏合：循环切换关节组
- 食指捏合并拖动：控制当前组
- 中指捏合：控制夹爪

#### 6.2.3 手势模式的实现要求

- 必须显示当前输入源是否为 `hand`
- 必须显示当前追踪状态是否稳定
- 必须在追踪丢失时给出轻提示，而不是静默失控
- 需要为 Quest3 手部追踪抖动设置阈值滤波与速度限制

### 6.3 VR 模式状态机要求

前后端建议统一维护以下状态：

- `vr_disabled`
- `vr_ready`
- `vr_controller_mode`
- `vr_hand_mode`
- `vr_error`

状态同步中建议至少广播：

- 当前 VR 模式
- 当前输入源是否可用
- 当前选中关节组
- 夹爪控制状态
- 最近一次有效输入时间
- Quest3 是否在线

### 6.4 Quest3 局域网连接后控制机械臂的完整方式

这一节对应你这次特别强调的内容，建议作为后续实现和论文方法描述的统一版本。

#### 6.4.1 控制链总览

Quest3 接入后的控制链建议固定为：

```text
Quest3 输入设备
-> 前端 XR / 输入桥接层
-> 前端控制映射层
-> WebSocket 控制消息
-> FastAPI /sim/ws
-> SimulationCore
-> MuJoCo step
-> state_broadcast
-> 前端 Three.js 场景 / 录制器 / 状态面板
```

#### 6.4.2 前端侧分层建议

Quest3 接入后，前端侧建议至少分成 4 层：

1. 设备接入层  
负责识别 Quest3 当前是手柄还是手势可用。

2. 输入归一化层  
把摇杆、Trigger、捏合、拖动等原始输入统一变成标准化控制量。

3. 关节组映射层  
把标准化输入映射成：
   - 当前关节组
   - 两个目标关节的增量或目标值
   - 夹爪开合量

4. 命令发送层  
把最终控制量封装成后端可接收的控制消息，并通过 WebSocket 发出。

#### 6.4.3 后端侧分层建议

后端接到 Quest3 控制后，建议按下面链路处理：

1. 接收控制消息
2. 校验控制来源、控制模式和关节长度
3. 把 Quest3 控制输入转成 MuJoCo 目标动作
4. 执行一步或多步仿真
5. 生成统一状态快照
6. 广播给前端显示层和录制器

#### 6.4.4 Quest3 手柄模式执行步骤

建议文档中把手柄控制写成可执行步骤：

1. Quest3 进入前端页面
2. 点击 `VR模式`
3. 选择 `手柄模式`
4. 左手 `X / Y / Grip` 选择关节组
5. 右摇杆连续控制当前关节组的两个关节
6. 右 `Trigger` 控制夹爪开合
7. 前端按固定频率发送控制命令
8. 后端执行控制并回传状态
9. 录制器将当前状态、动作和输入模式写入 episode

#### 6.4.5 Quest3 手势模式执行步骤

建议文档中把手势控制也写成可执行步骤：

1. Quest3 进入前端页面
2. 点击 `VR模式`
3. 选择 `手势模式`
4. 系统确认手部追踪已激活
5. 左手完成关节组选择
6. 右手捏合拖动控制当前关节组
7. 指定手势控制夹爪开合
8. 前端按固定频率发送控制命令
9. 后端执行控制并回传状态
10. 录制器写入状态、动作和输入模式

#### 6.4.6 推荐控制频率

为了兼顾稳定性与网络负载，建议先按以下频率设计：

- Quest3 输入采样：`30-60 Hz`
- 前端控制命令发送：`20-30 Hz`
- 后端状态广播：`30-50 Hz`
- 录制器写盘频率：与控制消息或状态消息保持同频或近似同频

#### 6.4.7 控制中断与退出规则

Quest3 控制链必须有明确的退出规则：

- 用户点击“退出 VR 模式”后，停止 Quest3 输入采样
- Quest3 丢失连接后，立即停止发送新的控制增量
- 手柄或手势追踪丢失时，进入保持或安全停状态
- 切换到脚本任务或策略任务前，Quest3 手动控制应显式释放控制权

### 6.4.8 VR 控制下的接触与穿模问题定位

当前已经实现 Quest3 对机械臂的控制后，需要特别注意一个容易被误解的问题：  
“机械臂能被 VR 控制移动”不等于“机械臂已经具备真实可靠的接触动力学抓取能力”。

在当前阶段，VR 输入通常会被转换为关节目标、关节增量或夹爪开合目标。  
如果后端主要是把这些目标写入 MuJoCo 状态或位置伺服，而不是完整依赖接触力、摩擦、重力和电机动力学来推动世界，那么接触工具、桌面和工具箱时就可能出现以下现象：

- 机械臂或夹爪看起来穿过桌面、工具箱或工具
- 工具被夹爪碰到但不会像真实物体一样滑动、滚动或被推开
- 夹爪闭合后视觉上夹住了工具，但工具不会稳定跟随机械臂移动
- 碰撞被系统硬性拦截，表现为卡住、跳变或控制不连续
- 工具、桌面或工具箱的碰撞体与可视模型不一致，导致“看起来没碰到/看起来穿了”的错觉

S4.5 完成后，上述问题中的“前后端边界不一致”和“明显穿桌、穿箱、穿工具”已经通过物理边界修复收敛到可继续采集前置检查的范围。后续仍不应把这等同于完整真实力控抓取，抓取附着和释放判定仍需要单独实现。

因此后续文档和实现应把当前控制阶段称为：

```text
VR teleop + joint target control + contact safety check
```

而不能直接称为：

```text
fully physics-based grasping teleoperation
```

这不是坏事。对当前项目而言，最重要的是先建立可控、可重复、可记录的数据采集链路，而不是一开始就追求完全真实的物理抓取手感。

### 6.4.9 已完成的物理边界与 VR 运动安全壳基线

正式采集数据前原本需要先解决 Quest3 / 手动控制下的明显虚拟干涉问题。  
当前 S4.5 已经完成这一前置：通过统一前端可视边界和后端 MuJoCo 物理边界，桌面、工具箱、工具对象和夹爪交互空间已经具备可复用的物理边界基线。

已完成或冻结的规则如下：

1. 前后端使用同一工具、工具箱、桌面和机械臂对象基线，避免可视边界与物理边界分叉。
2. 桌面、工具箱、工具对象和夹爪交互区域具备物理边界，阻止明显穿桌、穿箱和穿工具。
3. reset 后检查工具平躺、工具箱开口朝上、对象不穿透且位于 UR5 工作区内。
4. 手动控制和 Quest3 控制复用同一物理边界基线，避免不同输入源产生不同干涉表现。
5. 第一版半物理抓取的抓取判定、临时附着和释放校验不再归入 S4.5，而是放到后续任务闭环阶段实现。

这里需要区分“允许接触”和“禁止接触”：

| 接触类型 | 是否允许 | 说明 |
| --- | --- | --- |
| 夹爪指尖接触目标工具 | 允许 | 这是抓取任务的一部分 |
| 夹爪轻微接触工具箱边缘 | 视情况允许或警告 | 需要记录，避免放置阶段穿箱 |
| 机械臂连杆穿桌 | 禁止 | 应立即拦截或回退 |
| 夹爪穿过工具实体 | 禁止 | 正式采集数据中不应出现 |
| 工具初始状态与桌面/工具箱穿透 | 禁止 | reset 阶段应重采样 |
| 非目标工具被大幅碰撞 | 默认禁止或标记异常 | 第一版任务应尽量简化场景干扰 |

后续状态广播和数据集记录仍建议增加以下语义字段，用于录制筛选和训练数据质量控制：

- `safety_status`: `normal / limited / collision_blocked / safe_hold`
- `collision_blocked`: 当前动作是否被碰撞保护拦截
- `collision_objects`: 发生拦截的对象对
- `max_penetration_depth_m`: 最大穿透深度
- `contact_state`: 夹爪、工具、桌面和工具箱的接触摘要
- `grasp_state`: `none / candidate / attached / released / failed`

这些字段不只是调试用，也会直接影响后续数据筛选。  
例如包含连续 `collision_blocked`、明显穿桌或 `safe_hold` 的 episode，默认不应进入训练集。

### 6.4.10 工具抓取建议先采用半物理方案

完全依赖 MuJoCo 接触、摩擦和夹爪力来真实夹住细长工具，调参成本较高。  
对第一版数据采集来说，更稳妥的方案是：

```text
物理接触检测 + 抓取规则判定 + 临时附着 + 释放判定
```

建议第一版抓取状态机如下：

1. `none`：未接触工具。
2. `candidate`：目标工具进入夹爪工作区域，且夹爪正在闭合。
3. `attached`：距离、接触和夹爪闭合阈值满足条件，工具临时附着到夹爪或末端。
4. `released`：夹爪打开并解除附着。
5. `failed`：发生滑落、误抓、穿模、碰撞或超时。

第一版抓取成功判定可以包括：

- 目标工具是当前语言指令中指定的工具
- 目标工具中心或推荐抓取区域位于两指之间
- 夹爪闭合量超过阈值
- 左右指尖与工具距离或接触状态满足阈值
- 抓取后工具随末端移动一小段距离仍保持稳定

第一版释放成功判定可以包括：

- 已解除附着
- 工具位于工具箱有效空间或目标槽位附近
- 工具没有明显穿透工具箱、桌面或夹爪
- 工具姿态没有严重违反常识，例如竖直插起、悬空或倒扣

这类半物理方案比纯物理夹取更容易稳定，也更适合先完成 Quest3 示教数据采集。  
后续如果时间允许，再逐步增加更真实的动力学、摩擦和接触随机化。

### 6.5 建议增加的控制消息字段

为了让局域网控制、数据采集和训练验证都能统一，后续控制消息建议在兼容现有字段的基础上扩展。

| 字段名 | 层级 | 类型 | 是否必填 | 示例 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `type` | 顶层 | `string` | 是 | `control` | WebSocket 消息类型 |
| `data.target_positions` | `data` | `number[]` | 是 | `[0.0, -1.2, 1.4, -1.1, -1.5, 0.2]` | 6 轴关节目标值，建议统一为弧度 |
| `data.gripper_command.mode` | `data.gripper_command` | `string` | 是 | `open_close` | 当前阶段统一使用开合模式 |
| `data.gripper_command.value` | `data.gripper_command` | `number` | 是 | `0.35` | 夹爪开合量，建议范围 `0.0-1.0` |
| `data.n_steps` | `data` | `integer` | 否 | `12` | 后端一次执行的步数 |
| `data.control_mode` | `data` | `string` | 否 | `position` | 当前建议先统一为位置控制 |
| `data.source` | `data` | `string` | 是 | `manual` | 现有兼容字段，建议保留 |
| `data.input_source` | `data` | `string` | 否 | `quest3_controller` | 更细粒度区分控制来源 |
| `data.runtime_target` | `data` | `string` | 否 | `sim` | 当前命令目标运行端，后续建议支持 `sim` / `real_ur5` |
| `data.selected_joint_group` | `data` | `string` | 否 | `forearm` | 当前正在控制的大臂/前臂/腕部组 |
| `data.teleop_session_id` | `data` | `string` | 否 | `session_20260410_01` | 对应一次采集会话 |
| `data.episode_id` | `data` | `string` | 否 | `episode_0007` | 对应一条示教轨迹 |
| `data.recording_enabled` | `data` | `boolean` | 否 | `true` | 当前控制是否进入录制状态 |
| `data.policy_stage` | `data` | `string` | 否 | `human_demo` | 区分人工示教、初训推理、RL 推理 |
| `timestamp` | 顶层 | `number` | 否 | `1710000000000` | 客户端发送时间戳，便于延迟统计 |

建议示例：

```json
{
  "type": "control",
  "data": {
    "target_positions": [0.0, -1.2, 1.4, -1.1, -1.5, 0.2],
    "gripper_command": { "mode": "open_close", "value": 0.35 },
    "n_steps": 12,
    "control_mode": "position",
    "source": "manual",
    "input_source": "quest3_controller",
    "runtime_target": "sim",
    "selected_joint_group": "forearm",
    "teleop_session_id": "session_20260410_01",
    "episode_id": "episode_0007",
    "recording_enabled": true,
    "policy_stage": "human_demo"
  },
  "timestamp": 1710000000000
}
```

### 6.6 建议增加的状态广播字段

状态广播建议补充以下字段，服务于 Quest3 控制、数据集录制和模型验证：

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `vr_mode` | `string` | `vr_controller_mode` | 当前 VR 模式状态 |
| `input_source` | `string` | `quest3_controller` | 当前激活输入源 |
| `selected_joint_group` | `string` | `forearm` | 当前控制关节组 |
| `quest_connected` | `boolean` | `true` | Quest3 是否在线 |
| `recording_status` | `string` | `recording` | 当前是否正在录制 |
| `active_policy_stage` | `string` | `human_demo` | 当前阶段是人工示教、初训推理还是 RL 推理 |
| `active_model_path` | `string` | `models/pi05/initial_runs/run_20260410_01/exported/policy.pt` | 当前激活模型路径，可为空 |
| `runtime_target` | `string` | `sim` | 当前运行端，后续建议支持 `sim` / `real_ur5` |
| `control_backend` | `string` | `mujoco` | 当前由 MuJoCo 还是实机适配层执行 |
| `safety_status` | `string` | `normal` | 当前安全状态，例如 `normal / hold / estop / watchdog_timeout` |
| `teleop_session_id` | `string` | `session_20260410_01` | 当前采集会话 ID |
| `episode_id` | `string` | `episode_0007` | 当前轨迹 ID |
| `task_goal` | `string` | `tool_sorting_to_toolbox` | 当前目标任务，用于强调“工具入库” |
| `toolbox_slot_id` | `string` | `slot_A` | 当前目标工具箱槽位 |
| `validation_mode` | `string` | `mujoco_replay` | 当前是否处于 MuJoCo 模型验证模式 |

---

## 7. 数据采集与存储设计

### 7.0 正式采集前置闸门

在进入正式批量采集前，建议把采集分成三个等级：

| 等级 | 用途 | 是否进入训练集 |
| --- | --- | --- |
| `debug_trial` | 调试相机、VR 控制、reset、接触安全壳和写盘链路 | 否 |
| `pilot` | 小规模试采，用于检查数据完整性和标注流程 | 默认否，人工确认后可选 |
| `train_candidate` | 通过自动校验和人工抽查的正式候选数据 | 可以 |

当前阶段不建议一上来直接批量采集。  
原因是数据集一旦混入相机缺帧、stub 图像、穿桌、工具竖立、工具箱倒扣、语言标签缺失等问题，后续训练会很难定位问题来源。

正式 episode 开始前，至少应通过以下检查：

- 后端在线，WebSocket 在线，MuJoCo backend 可用
- 末端 `D405` 的 `RGB` 与 `Depth` 接口均可返回观测
- `camera_capture_ok=true`
- 当前视觉帧不是 stub / fallback 图像
- `qpos`、`qvel`、`ee_pose`、`gripper_opening`、`objects` 均能持续更新
- Quest3 输入模式、输入源、关节组和原始输入值可以记录
- 当前目标工具、目标槽位和 `instruction_text` 已绑定
- reset 后工具位姿、工具箱位姿、碰撞状态和工作区可达性均合法
- `safety_status=normal`
- 短时 smoke recording 能同时写入 RGB、Depth、状态和动作

如果任一检查失败，本次只能作为 `debug_trial`，不能标记为正式训练候选数据。

### 7.0.1 录制生命周期

数据集采集建议按一个明确的 episode 生命周期实现：

```text
idle
  -> precheck
  -> episode_created
  -> recording
  -> stopping
  -> finalizing
  -> completed / rejected / aborted
```

各阶段语义如下：

| 阶段 | 触发条件 | 主要动作 | 允许进入训练集 |
| --- | --- | --- | --- |
| `idle` | 无活动 episode | 等待用户打开采集面板 | 否 |
| `precheck` | 用户点击刷新检查或开始录制 | 检查相机、状态、reset、安全壳、磁盘、语言标签 | 否 |
| `episode_created` | 预检查通过或允许 debug_trial | 生成 session / episode ID，冻结 metadata | 否 |
| `recording` | 用户确认开始 | 持续写入 RGB、Depth、状态、动作、文本和索引 | 取决于最终校验 |
| `stopping` | 用户点击停止或触发终止条件 | 停止接收新样本，刷写缓冲队列 | 否 |
| `finalizing` | 样本写入完成 | 写入 result、validation_summary、MP4 预览和统计 | 否 |
| `completed` | 校验通过并保存成功 | 标记成功或失败结果，允许人工查看 | 可选 |
| `rejected` | 自动或人工剔除 | 写入剔除原因 | 否 |
| `aborted` | 异常中断、掉线或用户强制终止 | 保留目录和部分日志 | 否 |

正式训练候选数据必须满足：

- 生命周期到达 `completed`
- `recording_tier=train_candidate`
- `validation_summary.can_be_train_candidate=true`
- 人工抽查没有剔除

### 7.0.2 建议新增的采集接口

为避免前端直接拼凑录制逻辑，建议后端提供一组清晰的采集 API。  
接口名可以在实现时调整，但语义建议保持稳定。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/dataset/status/` | 获取当前采集状态、活动 session、活动 episode、写盘状态 |
| `POST` | `/dataset/precheck/` | 执行采集前置检查，返回 `recording_ready` 和失败原因 |
| `POST` | `/dataset/session/start/` | 创建或恢复采集 session |
| `POST` | `/dataset/episode/start/` | 创建 episode 并开始录制 |
| `POST` | `/dataset/episode/stop/` | 停止录制并进入保存/校验 |
| `POST` | `/dataset/episode/abort/` | 异常中止，保留 `aborted` 目录 |
| `GET` | `/dataset/episode/{episode_id}/summary/` | 读取结果和 `validation_summary` |
| `GET` | `/dataset/episode/{episode_id}/preview/` | 获取 RGB 预览视频或关键帧 |
| `POST` | `/dataset/episode/{episode_id}/mark/` | 人工标记是否纳入训练集和剔除原因 |

WebSocket 状态广播建议补充：

- `recording_status`
- `recording_tier`
- `recording_ready`
- `active_session_id`
- `active_episode_id`
- `target_tool_id`
- `target_tool_class`
- `instruction_text`
- `num_rgb_frames`
- `num_depth_frames`
- `num_state_samples`
- `num_action_samples`
- `last_record_error`
- `writer_queue_size`

前端底部导航栏只订阅这些摘要字段；完整细节由采集面板读取。

### 7.0.3 采集前置检查返回结构

`/dataset/precheck/` 建议返回结构化结果，而不是只返回一句文本：

```json
{
  "recording_ready": true,
  "allowed_tier": "train_candidate",
  "checks": {
    "backend_online": true,
    "websocket_online": true,
    "mujoco_backend_ok": true,
    "rgb_ok": true,
    "depth_ok": true,
    "camera_capture_ok": true,
    "stub_frame_used": false,
    "state_stream_ok": true,
    "quest_input_ok": true,
    "instruction_bound": true,
    "reset_valid": true,
    "safety_status_ok": true,
    "disk_space_ok": true
  },
  "reject_reasons": [],
  "warnings": []
}
```

如果不通过，`recording_ready=false`，但可以返回：

```json
{
  "recording_ready": false,
  "allowed_tier": "debug_trial",
  "reject_reasons": ["camera_capture_stub", "reset_invalid"],
  "warnings": ["正式训练数据禁止使用当前相机帧"]
}
```

这样前端可以明确禁用正式录制按钮，同时允许用户做调试试采。

### 7.0.4 异常与中断处理

正式录制时必须明确处理以下异常：

| 异常 | 处理方式 |
| --- | --- |
| Quest3 掉线 | 停止接收新动作，episode 标记 `operator_or_device_disconnect` |
| WebSocket 断开 | 后端继续刷写缓冲，前端重连后读取 status |
| 相机缺帧 | 写入 `rgb_missing/depth_missing`，超过阈值则 `camera_failure` |
| 出现 stub 图像 | 正式 episode 自动降级或标记不可训练 |
| reset 非法 | 禁止开始正式录制，只允许 debug_trial |
| safe hold | 写入 `safe_hold_triggered`，必要时自动停止 episode |
| 磁盘不足 | 禁止开始或立即安全停止，保留错误摘要 |
| 用户误触停止 | 正常停止，但 result 中记录 `operator_abort` |

异常中断的 episode 不应删除。  
保留 `aborted` 目录和 `partial_summary.json`，后续可以用于调试，但默认不进入训练集。

### 7.0.5 可训练视觉数据硬性约束

这一节需要写成硬性要求，而不是建议。  
否则后续确实无法稳定训练 `pi0.5` 或其他 VLA / imitation learning 模型。

正式训练候选 episode 的视觉数据必须满足：

1. 视觉源必须是 MuJoCo 中挂在 UR5 末端的 `D405` 相机，也就是 `d405_rgb / d405_depth` 对应的 eye-in-hand 视角。
2. 不能把 Quest3 头显看到的页面画面当作训练视觉输入。
3. 不能把前端 Three.js 观察相机画面当作训练视觉输入。
4. 不能把 `camera / camera_base` 调试对象或外部观察相机当作主采集相机。
5. 不能只保存 MP4 视频后再反解训练数据；MP4 只能作为预览和论文展示。
6. 训练主数据必须是逐帧 `RGB` 文件、逐帧 `Depth` 文件和 `visuals.jsonl` 索引。
7. 每条动作样本必须能追溯到最近有效视觉帧 `paired_frame_id`。
8. 每条状态样本必须包含同一时刻附近的 `qpos/qvel/ee_pose/gripper/objects/camera_capture_ok`。
9. 每条 episode 必须有具体 `instruction_text`，明确当前抓取的工具类别。
10. `Depth` 必须使用 `png16`、`npy` 或等价无损格式，不能使用 JPG 或有损视频编码作为深度主数据。

正式训练候选 episode 的硬性拒绝条件：

| 条件 | 结果 |
| --- | --- |
| `camera_capture_ok=false` | 不得进入训练集 |
| `stub_frame_used=true` 或 `stub_frame_count > 0` | 不得进入训练集 |
| 缺少 `rgb_path` 或 `depth_path` | 不得进入训练集 |
| RGB 与 Depth 时间对齐超过阈值 | 不得进入训练集，除非明确标为调试数据 |
| 任一动作缺少 `paired_frame_id` | 不得进入训练集 |
| 只有 MP4，没有逐帧 RGB/Depth | 不得进入训练集 |
| 任务文本缺失或只写 `pick up the tool` | 不得进入训练集 |
| 视觉源不是末端 D405 | 不得进入训练集 |

换句话说，MP4 是人看的，`rgb/ + depth/ + visuals.jsonl + states.jsonl + actions.jsonl + language.json` 才是模型训练真正读取的数据。

### 7.1 采集责任边界

这一点现在需要明确冻结：

- 数据集不是系统自动生成，而是由你本人完成示教采集。
- Quest3 的角色是“人工示教输入设备”。
- 前端/后端系统的角色是“录制器、状态同步器、存档器和回放器”。
- 因此后续所有“采集”相关任务，默认都应理解为“你操作 Quest3，系统记录 episode”，而不是“系统自己跑任务生成数据”。

### 7.2 数据采集目标

Quest3 采集的不应只是“最终关节角度”。为了后续训练和论文复现，应该尽量保留示教上下文。

对你当前要走的 `pi0.5` 路线而言，这里需要额外明确：

- 如果只采 `qpos / ee_pose / gripper / objects` 等低维状态，这更像“状态条件策略数据”
- 如果要称为面向 `pi0.5` 的 VLA 数据集，就必须把视觉和任务文本一起纳入录制
- 因此本项目从现在开始建议把单步样本统一理解为：
  `RGB-D 观测 + 机器人状态 + 任务文本 -> 动作`

进一步说：

- Quest3 负责“人类示教输入”
- `D405` 负责“视觉观测”
- 后端状态广播负责“机器人与环境状态”
- 录制器负责把这三类信息按时间对齐后落盘

### 7.3 每条 episode 必须保存的内容

正式采集的每个 episode 至少必须包含以下信息；缺任一主字段都不能标记为 `train_candidate`。

#### 7.3.1 元数据

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `task_id` | `string` | `quest3_tool_sorting_v1` | 当前实验任务 ID |
| `session_id` | `string` | `session_20260410_01` | 一次连续采集会话 |
| `episode_id` | `string` | `episode_0007` | 单条示教轨迹编号 |
| `captured_at` | `string` | `2026-04-10T14:30:00+08:00` | 采集开始时间 |
| `operator_id` | `string` | `sunshine` | 操作员标识，默认可直接写你本人 |
| `input_mode` | `string` | `controller` | Quest3 手柄或手势模式 |
| `tool_class` | `string` | `wrench` | 当前目标工具类别 |
| `tool_instance_id` | `string` | `wrench_01` | 当前目标工具实例 ID |
| `toolbox_slot_id` | `string` | `slot_A` | 当前目标放置槽位 |
| `env_seed` | `integer` | `42` | 环境随机种子 |
| `quest_device_info` | `object` | `{"device":"Quest3","browser":"Meta Browser"}` | Quest3 设备信息 |
| `input_source` | `string` | `quest3_controller` | 当前控制来源 |
| `policy_stage` | `string` | `human_demo` | 当前轨迹对应的人机/模型阶段 |
| `runtime_target` | `string` | `sim` | 当前轨迹运行在仿真还是实机，建议先支持 `sim` |
| `robot_platform` | `string` | `ur5_robotiq_2f85` | 机器人平台标识，便于后续实机部署对齐 |
| `calibration_version` | `string` | `calib_20260410_a` | 当前桌面/工具箱/相机标定版本，可为空 |
| `goal_description` | `string` | `pick wrench and place into toolbox` | 当前轨迹目标描述，建议固定指向工具入库 |
| `instruction_text` | `string` | `pick up the wrench and place it into the toolbox` | 当前轨迹对应的任务文本，建议固定模板化 |
| `camera_device` | `string` | `intel_realsense_d405` | 主视觉设备标识 |
| `camera_mount_name` | `string` | `wrist_d405_v1` | 当前末端安装方案名称 |
| `camera_modalities` | `string[]` | `["rgb","depth"]` | 本轨迹使用的视觉模态 |
| `camera_intrinsics_version` | `string` | `d405_intr_20260412_a` | 相机内参版本 |
| `camera_extrinsics_version` | `string` | `d405_ext_20260412_a` | 相机相对末端的外参版本 |
| `visual_recording_required` | `boolean` | `true` | 该轨迹是否要求视觉完整录制；面向 `pi0.5` 应为 `true` |
| `recording_tier` | `string` | `train_candidate` | `debug_trial / pilot / train_candidate` |
| `schema_version` | `string` | `quest3_tool_sorting_v1_s5` | 当前数据格式版本 |
| `code_version` | `string` | `git commit hash` | 采集时对应代码版本 |
| `config_versions` | `object` | `{"scene_manifest":"v2.1.0"}` | 场景、工具、相机和数据 schema 版本 |
| `reset_seed` | `integer` | `42` | 当前 episode 的 reset 随机种子 |
| `reset_valid` | `boolean` | `true` | reset 后初始状态是否合法 |
| `reset_resample_count` | `integer` | `2` | reset 非法后重采样次数 |
| `safety_gate_passed` | `boolean` | `true` | 是否通过 VR 运动安全壳采集前检查 |

#### 7.3.2 视觉观测序列

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `timestamp` | `number` | `1710000000.123` | 当前视觉样本时间戳 |
| `frame_id` | `string` | `frame_000123` | 当前视觉帧编号 |
| `rgb_path` | `string` | `rgb/frame_000123.jpg` | 当前 RGB 帧路径 |
| `depth_path` | `string` | `depth/frame_000123.png` | 当前 Depth 帧路径，建议无损格式 |
| `rgb_width` | `integer` | `640` | RGB 宽度 |
| `rgb_height` | `integer` | `480` | RGB 高度 |
| `depth_width` | `integer` | `640` | Depth 宽度 |
| `depth_height` | `integer` | `480` | Depth 高度 |
| `depth_unit` | `string` | `millimeter` | 深度单位，建议明确冻结 |
| `depth_scale` | `number` | `0.001` | 深度换算尺度 |
| `rgb_timestamp` | `number` | `1710000000.121` | RGB 帧时间戳 |
| `depth_timestamp` | `number` | `1710000000.122` | Depth 帧时间戳 |
| `frame_aligned` | `boolean` | `true` | 当前 RGB 与 Depth 是否已对齐 |
| `camera_pose_in_ee` | `object` | `{"position":[...],"quaternion":[...]}` | 当前相机相对末端坐标的固定外参记录 |
| `camera_pose_in_base` | `object` | `{"position":[...],"quaternion":[...]}` | 当前步相机在机器人基坐标系下的位姿 |
| `rgb_missing` | `boolean` | `false` | 当前步 RGB 是否缺帧 |
| `depth_missing` | `boolean` | `false` | 当前步 Depth 是否缺帧 |
| `visual_valid` | `boolean` | `true` | 当前视觉观测是否可用于训练 |
| `stub_frame_used` | `boolean` | `false` | 是否使用了 fallback/stub 图像；正式训练应为 `false` |
| `rgb_file_size_bytes` | `integer` | `38291` | RGB 文件大小，便于完整性检查 |
| `depth_file_size_bytes` | `integer` | `614400` | Depth 文件大小，便于完整性检查 |
| `depth_invalid_ratio` | `number` | `0.02` | 深度无效像素占比，可用于筛选 |

#### 7.3.3 状态序列

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `timestamp` | `number` | `1710000000.123` | 当前状态时间戳 |
| `sim_time` | `number` | `12.34` | MuJoCo 仿真时间 |
| `qpos` | `number[]` | `[0.0, -1.2, 1.4, -1.1, -1.5, 0.2, 0.35]` | 当前关节与夹爪状态 |
| `qvel` | `number[]` | `[0.0, 0.1, ...]` | 当前关节速度 |
| `ee_pose` | `object` | `{"position":[...],"quaternion":[...]}` | 末端位姿 |
| `gripper_opening` | `number` | `0.35` | 当前夹爪开合量 |
| `objects` | `object` | `{"wrench_01": {...}, "screwdriver_01": {...}, "pliers_01": {...}, "toolbox": {...}}` | 所有工具和工具箱对象状态 |
| `target_tool_id` | `string` | `wrench_01` | 当前目标工具 |
| `attached_to_gripper` | `boolean` | `false` | 当前是否附着在夹爪上 |
| `contact_state` | `object` | `{"left_pad": true, "right_pad": false}` | 当前接触信息 |
| `vr_mode` | `string` | `vr_controller_mode` | 当前 VR 模式 |
| `selected_joint_group` | `string` | `forearm` | 当前被控制的关节组 |
| `active_input_source` | `string` | `quest3_controller` | 当前激活控制源 |
| `active_model_path` | `string` | `""` | 当前策略路径，示教阶段可为空 |
| `runtime_target` | `string` | `sim` | 当前状态来自仿真还是实机运行端 |
| `task_goal` | `string` | `tool_sorting_to_toolbox` | 当前任务目标，统一表示工具入库 |
| `camera_capture_ok` | `boolean` | `true` | 当前步是否成功关联到完整的 `RGB-D` 观测 |
| `instruction_text` | `string` | `pick up the wrench and place it into the toolbox` | 当前步对应的任务文本，便于训练时直接读取 |
| `safety_status` | `string` | `normal` | `normal / limited / collision_blocked / safe_hold` |
| `collision_blocked` | `boolean` | `false` | 当前步是否被碰撞保护拦截 |
| `collision_objects` | `string[]` | `["left_pad","wrench_01"]` | 当前相关接触或拦截对象 |
| `max_penetration_depth_m` | `number` | `0.0` | 最大穿透深度，正式数据应低于阈值 |
| `grasp_state` | `string` | `attached` | `none / candidate / attached / released / failed` |
| `reset_valid` | `boolean` | `true` | 当前 episode 初始 reset 是否通过合法性检查 |

#### 7.3.4 动作序列

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `command_timestamp` | `number` | `1710000000123` | 控制消息发送时间戳 |
| `ack_timestamp` | `number` | `1710000000131` | 后端确认时间戳 |
| `target_positions` | `number[]` | `[0.0, -1.2, 1.4, -1.1, -1.5, 0.2]` | 目标关节命令 |
| `joint_delta` | `number[]` | `[0.0, 0.02, -0.01, 0.0, 0.0, 0.01]` | 如果采用增量控制则记录增量 |
| `gripper_command` | `object` | `{"mode":"open_close","value":0.35}` | 当前夹爪命令 |
| `input_mode` | `string` | `controller` | 当前输入模式 |
| `selected_joint_group` | `string` | `forearm` | 当前关节组 |
| `runtime_target` | `string` | `sim` | 当前动作要发往的运行目标 |
| `raw_input` | `object` | `{"right_stick_x":0.42,"right_stick_y":-0.31}` | 原始手柄或手势输入 |
| `input_interrupted` | `boolean` | `false` | 当前步是否发生追踪中断 |
| `input_confidence` | `number` | `0.92` | 当前手势或输入可信度，可选 |
| `paired_frame_id` | `string` | `frame_000123` | 与当前动作对应的视觉帧 ID |
| `instruction_text` | `string` | `pick up the wrench and place it into the toolbox` | 当前动作对应的任务文本 |
| `safety_status_before` | `string` | `normal` | 执行动作前安全状态 |
| `safety_status_after` | `string` | `normal` | 执行动作后安全状态 |
| `action_accepted` | `boolean` | `true` | 动作是否被后端接受执行 |
| `action_reject_reason` | `string` | `` | 被拒绝时的原因，例如碰撞、限幅或 stale command |

#### 7.3.5 结果标签

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `grasp_success` | `boolean` | `true` | 是否成功抓取工具 |
| `place_success` | `boolean` | `true` | 是否成功放入工具箱 |
| `tool_putaway_success` | `boolean` | `true` | 是否完成工具入库，建议作为最终主标签 |
| `timeout` | `boolean` | `false` | 是否超时 |
| `drop_failure` | `boolean` | `false` | 是否中途掉落 |
| `collision_failure` | `boolean` | `false` | 是否因碰撞失败 |
| `duration_s` | `number` | `18.6` | 整条轨迹耗时 |
| `included_in_train` | `boolean` | `true` | 是否纳入训练集 |
| `manually_rejected` | `boolean` | `false` | 是否被人工剔除 |
| `failure_reason` | `string` | `` | 失败原因说明 |
| `notes` | `string` | `controller mode was stable` | 备注信息 |
| `camera_failure` | `boolean` | `false` | 是否因 RGB-D 缺失、错帧或 stub 图像失败 |
| `reset_invalid` | `boolean` | `false` | 是否因 reset 位姿非法失败 |
| `operator_abort` | `boolean` | `false` | 是否人工中止 |
| `safe_hold_triggered` | `boolean` | `false` | 是否触发安全保持 |
| `collision_block_count` | `integer` | `0` | episode 中碰撞拦截次数 |
| `stub_frame_count` | `integer` | `0` | episode 中 fallback/stub 图像帧数 |
| `validation_passed` | `boolean` | `true` | 自动校验是否通过 |

#### 7.3.6 采集校验摘要

每条 episode 结束时建议生成 `validation_summary.json`，至少包含：

| 字段名 | 类型 | 示例 | 说明 |
| --- | --- | --- | --- |
| `episode_id` | `string` | `episode_0007` | 当前 episode |
| `duration_s` | `number` | `18.6` | 轨迹时长 |
| `num_rgb_frames` | `integer` | `558` | RGB 帧数 |
| `num_depth_frames` | `integer` | `558` | Depth 帧数 |
| `num_state_samples` | `integer` | `558` | 状态样本数 |
| `num_action_samples` | `integer` | `372` | 动作样本数 |
| `missing_rgb_count` | `integer` | `0` | RGB 缺帧数 |
| `missing_depth_count` | `integer` | `0` | Depth 缺帧数 |
| `misaligned_frame_count` | `integer` | `0` | RGB/Depth 未对齐帧数 |
| `stub_frame_count` | `integer` | `0` | fallback/stub 图像帧数 |
| `collision_block_count` | `integer` | `1` | 碰撞保护拦截次数 |
| `max_penetration_depth_m` | `number` | `0.0002` | 最大穿透深度 |
| `reset_valid` | `boolean` | `true` | 初始 reset 是否有效 |
| `instruction_text_present` | `boolean` | `true` | 是否存在任务文本 |
| `can_be_train_candidate` | `boolean` | `true` | 是否允许作为训练候选 |
| `reject_reasons` | `string[]` | `[]` | 自动剔除原因 |

`validation_summary` 不是论文装饰项，而是采集质量控制的硬闸门。  
如果 `stub_frame_count > 0`、关键字段缺失、RGB-D 未对齐严重、reset 非法或发生明显穿模，该 episode 默认不能进入训练集。

### 7.4 数据目录规范

后续代码和实验应统一使用如下目录：

```text
data/
  datasets/
    quest3_tool_sorting_v1/
      raw/
        session_YYYYMMDD_xx/
          metadata.json
          episodes/
            episode_0001/
              metadata.json
              language.json
              visuals.jsonl
              rgb/
              depth/
              states.jsonl
              actions.jsonl
              result.json
              validation_summary.json
          videos/
          logs/
      processed/
      splits/
  replay/
  calibration/

models/
  pi05/
    initial_runs/
      run_YYYYMMDD_xx/
        config.json
        checkpoints/
        exported/
        mujoco_validation/
  rl/
    finetune_runs/
      run_YYYYMMDD_xx/
        config.json
        checkpoints/
        exported/
        mujoco_validation/
  registry/
    active_policy.json

logs/
  teleop/
  train/
  eval/

experiments/
  paper/
    figures/
    tables/
    notes/
```

### 7.5 数据格式规范

正式训练数据统一使用：

- 元数据：JSON
- 时序数据：JSONL 或 Parquet
- RGB 图像：JPG 或 PNG
- Depth 图像：PNG16、NPY 或其他无损格式，不建议使用 JPG
- 视频：MP4，仅作为预览和展示，不作为训练主数据
- 训练划分：manifest JSON
- 任务文本：JSON 或直接写入 `metadata.json`

第一版最小可训练落盘结构必须包含：

- `metadata.json`
- `language.json`
- `visuals.jsonl`
- `rgb/frame_xxxxxx.jpg`
- `depth/frame_xxxxxx.png`
- `states.jsonl`
- `actions.jsonl`
- `result.json`
- `validation_summary.json`

### 7.6 为什么要尽早冻结数据格式

原因非常现实：

1. 如果先写采集逻辑、后想训练，很容易发现字段不够。
2. 如果先训练、后写论文，很容易发现关键统计量没有存。
3. Quest3 输入模式本身就是论文中的一部分变量，必须从一开始被记录。
4. 由于数据集由你本人手动采集，所以 session、episode、输入模式、失败原因等人工示教上下文都必须被完整记录。
5. 对 `pi0.5` 而言，视觉和任务文本不是锦上添花，而是决定数据集是否可直接训练的核心字段。
6. `Depth` 一旦用错格式，后续训练和回放会直接失真，因此必须先把深度存储规范写死。
7. 如果接触安全壳不稳定，模型会学到“穿过桌子/工具/工具箱”的错误动作先验，后续 RL 或 sim2real 会更难补救。
8. 如果 reset 姿态不符合现实，例如工具竖直立起或工具箱开口不朝上，数据分布会偏离真实任务。

### 7.7 试采到正式采集的推荐流程

建议按下面顺序推进：

1. `debug_trial`：只验证链路，不进入训练集。
2. `pilot`：每类工具至少采少量成功和失败轨迹，检查标签、回放和筛选是否可用。
3. 人工抽查：查看 RGB、Depth、状态、动作、reset 初始状态、接触状态和结果标签。
4. 自动校验：生成 `validation_summary.json` 并给出是否可成为 `train_candidate`。
5. 正式采集：固定 schema、相机标定版本、reset 随机化范围和语言模板后再批量采。
6. 数据冻结：每次采集 session 结束后冻结配置版本、代码版本、采集统计和剔除原因。

第一版正式采集建议保守一些：

- 优先使用手柄模式作为主采集方式
- 手势模式先作为对比或增强数据，不要一开始混入主训练集
- 每条 episode 只指定一个目标工具
- 工具箱位置先固定，工具位置有限随机
- 工具姿态只做平面 yaw 随机或小范围扰动
- 每类工具先采少量高质量轨迹，再决定是否扩大规模

### 7.8 语言描述规则

面向 `pi0.5` 或 VLA 训练，任务文本必须明确“抓什么”。  
不建议只写泛化文本 `pick up the tool` 作为唯一描述。

第一版建议采用稳定模板：

| 工具类别 | 英文模板 | 中文备注 |
| --- | --- | --- |
| `wrench` | `pick up the wrench and place it into the toolbox` | 抓取扳手并放入工具箱 |
| `screwdriver` | `pick up the screwdriver and place it into the toolbox` | 抓取螺丝刀并放入工具箱 |
| `pliers` | `pick up the pliers and place them into the toolbox` | 抓取钳子并放入工具箱 |

每条 episode 的 `metadata.json`、`language.json`、`states.jsonl` 和 `actions.jsonl` 都应能追溯到同一条任务文本。  
如果后续要扩充自然语言多样性，可以在 `language.json` 中增加 `instruction_variants`，但第一版训练建议先使用固定模板，减少无关变量。

---

## 8. 模型训练路线

### 8.1 总体原则：先形成可验证的 IL 闭环，再做 RL 微调

本项目的训练路线建议明确拆成四层，而不是把“采集完数据直接训 pi0.5、再直接 RL”写成一个模糊阶段：

```text
raw Quest3 episode 数据
  -> 数据清洗与质量筛选
  -> LeRobot / OpenPI 可训练数据集
  -> pi0.5 模仿学习初训
  -> MuJoCo 策略验证
  -> RL residual / warm-start 微调
  -> RL 模型入库与 MuJoCo 再验证
```

这里有一个必须写死的判断：

- `raw/` 目录下的 `metadata.json + visuals.jsonl + states.jsonl + actions.jsonl + rgb/ + depth/` 是本项目自己的高保真原始采集格式。
- `pi0.5` 训练不应直接读取这些原始 JSONL，而应先转换为 `LeRobot / OpenPI` 兼容的数据集格式。
- 第一版 `pi0.5` 初训应优先验证“数据转换、训练、推理、MuJoCo 执行”闭环，不追求一开始就达到强随机泛化。
- 第一版 RL 不建议直接端到端微调整个 `pi0.5` 大模型，而建议先做 `pi0.5 frozen + residual policy` 或 `pi0.5 warm-start policy`，降低训练成本和不稳定性。

官方路线也支持这个拆法：OpenPI 的自有数据 fine-tuning 流程分为“转换为 LeRobot dataset、定义训练 config、计算 norm stats、训练、启动 policy server 做推理”；LeRobot 的 `pi05` 策略训练也要求 dataset、policy config、pretrained path、normalization mapping 等配置明确。

### 8.2 训练阶段的责任边界

#### 8.2.1 你负责

- 使用 Quest3 完成手动示教采集。
- 根据 `validation_summary.json` 和人工回放筛选可训练 episode。
- 确认每轮训练使用的数据集版本、工具类别比例、语言模板和采集模式。
- 启动或参与启动 `pi0.5` 第一轮初训。
- 查看初训模型和 RL 模型在 MuJoCo 中的验证结果。

#### 8.2.2 系统与代码侧负责

- 实现 raw episode 到 LeRobot / OpenPI 数据集的转换工具。
- 实现数据集校验、统计、划分和转换报告。
- 提供 `pi0.5` 训练配置、训练脚本包装、日志和模型入库规范。
- 提供统一策略加载器，让初训模型和 RL 模型都能接入 MuJoCo。
- 提供 RL 环境、奖励、随机化、训练脚本和评估脚本。
- 记录所有模型的来源数据集、训练配置、动作空间、控制频率和验证结果。

### 8.3 推荐开发顺序

建议把训练链条冻结为以下可执行顺序：

1. 完成 S5 数据采集闭环，确保 episode 能落盘、回放和自动校验。
2. 完成 S6 抓取附着、释放、成功判定和脚本化任务，确保 reward 与结果标签可信。
3. 运行 `debug_trial` 和 `pilot`，每类工具先采少量可回放 episode。
4. 将通过筛选的 raw episode 标记为 `train_candidate`。
5. 运行 raw -> LeRobot / OpenPI 转换脚本，生成 `processed/pi05_lerobot/`。
6. 生成 train / val / test split，按 episode 划分，不按帧随机打散。
7. 计算 state / action normalization stats，并固化到数据集和训练 run 配置中。
8. 进行 `pi0.5` 初训，默认先使用 `RGB + robot_state + instruction_text -> action`。
9. 将初训模型写入 `models/pi05/initial_runs/<run_id>/`。
10. 使用统一策略加载器把初训模型加载回 MuJoCo 做固定场景和随机场景验证。
11. 基于初训模型进入 RL 微调，第一版优先采用 residual policy。
12. 将 RL 模型写入 `models/rl/finetune_runs/<run_id>/`。
13. 再次通过 MuJoCo 验证，比较 `scripted / pi0.5 IL / pi0.5 + RL` 三组结果。
14. 将通过验证的最终模型写入 `models/registry/active_policy.json`。

### 8.4 raw 数据到 pi0.5 数据集的转换

#### 8.4.1 为什么必须有转换层

本项目 raw episode 追求的是“可回放、可审计、可写论文”，字段丰富且保留大量工程上下文。`pi0.5` 训练则需要稳定、规则、张量化、可批量加载的数据结构。

因此必须新增一个转换层：

```text
raw episode 格式
  metadata.json
  language.json
  visuals.jsonl
  states.jsonl
  actions.jsonl
  rgb/*.jpg
  depth/*.png

转换为：

LeRobot / OpenPI 格式
  meta/info.json
  meta/stats.json
  meta/tasks.jsonl 或 tasks.parquet
  meta/episodes/...
  data/chunk-xxx/file-xxx.parquet
  videos/observation.images.d405_rgb/chunk-xxx/file-xxx.mp4
```

转换层不只是改文件格式，还要完成以下工作：

- 筛选 `validation_summary.can_be_train_candidate=true` 的 episode。
- 检查 `camera_capture_ok=true`、`stub_frame_count=0`、`paired_frame_id` 完整。
- 将不规则的控制时间戳重采样到统一 `policy_fps`。
- 将动作统一成训练用 action 向量。
- 将 `instruction_text` 映射为 task / prompt。
- 生成训练、验证、测试划分。
- 计算 normalization stats。
- 输出转换报告，方便定位训练问题。

#### 8.4.2 建议新增转换脚本

建议新增：

```text
scripts/datasets/convert_quest3_to_lerobot.py
scripts/datasets/validate_pi05_dataset.py
scripts/datasets/split_quest3_dataset.py
scripts/datasets/inspect_pi05_sample.py
```

第一版命令建议设计为：

```bash
python scripts/datasets/convert_quest3_to_lerobot.py \
  --raw-root data/datasets/quest3_tool_sorting_v1/raw \
  --output-root data/datasets/quest3_tool_sorting_v1/processed/pi05_lerobot_v1 \
  --split-file data/datasets/quest3_tool_sorting_v1/splits/pi05_v1.json \
  --policy-fps 10 \
  --image-key observation.images.d405_rgb \
  --state-mode qpos_gripper \
  --action-mode joint_delta_gripper_abs \
  --require-train-candidate true
```

转换完成后建议生成：

```text
data/datasets/quest3_tool_sorting_v1/processed/pi05_lerobot_v1/
  meta/
    info.json
    stats.json
    tasks.jsonl 或 tasks.parquet
    episodes/
  data/
    chunk-000/
      file-000.parquet
  videos/
    observation.images.d405_rgb/
      chunk-000/
        file-000.mp4
  conversion_report.json
  feature_mapping.json
  rejected_episodes.jsonl
```

#### 8.4.3 pi0.5 第一版 feature mapping

第一版不要把所有 raw 字段都塞进模型。为了减少 sim-only 依赖、提高后续实机迁移可能性，建议 `pi0.5` 训练输入先使用以下特征：

| 训练字段 | 来源 | 形状建议 | 是否 P0 | 说明 |
| --- | --- | --- | --- | --- |
| `observation.images.d405_rgb` | `rgb/frame_xxxxxx.jpg` | `3 x H x W` | 是 | 第一版主视觉输入，建议转换时另存训练视频或训练图像索引 |
| `observation.state` | `qpos[0:6] + gripper_opening` | `7` | 是 | 只用实机可直接获得的关节和夹爪状态 |
| `task` / `prompt` | `instruction_text` | string / task id | 是 | 例如 `pick up the wrench and place it into the toolbox` |
| `action` | `actions.jsonl + states.jsonl` | `7` | 是 | 默认 `6 轴关节增量 + 夹爪目标开合量` |
| `timestamp` | 对齐后的采样时间 | scalar | 是 | 用于调试和回放，不一定进入模型 |
| `episode_index` / `frame_index` | 转换器生成 | scalar | 是 | 用于 LeRobot 索引 |
| `observation.images.d405_depth` | `depth/frame_xxxxxx.png` | 可选 | 否 | 第一版保留但不默认接入 pi0.5 主干 |
| `objects` / `toolbox` 位姿 | `states.jsonl` | object | 否 | 用于筛选、评估和 RL reward，不作为第一版 pi0.5 输入 |

第一版建议：

```text
pi0.5 input:
  observation.images.d405_rgb
  observation.state = [q1, q2, q3, q4, q5, q6, gripper_opening]
  prompt = instruction_text

pi0.5 target:
  action = [delta_q1, delta_q2, delta_q3, delta_q4, delta_q5, delta_q6, gripper_target]
```

不建议第一版直接把 MuJoCo ground-truth `objects` 位姿作为 `pi0.5` 输入。原因是实机迁移时这些字段需要额外感知或标定才能获得；它们可以作为 reward、评估和失败分析字段，但不应成为第一版 VLA 模型的核心观测。

#### 8.4.4 动作定义

为保证初训和 RL 共用动作语义，建议统一动作向量为 7 维：

```text
action[0:6] = joint_delta_rad
              = target_positions[0:6] - state.qpos[0:6]

action[6]   = gripper_target_opening
              in [0.0, 1.0]
```

执行时由 runtime 转换为：

```text
next_target_positions = current_qpos[0:6] + clipped_joint_delta
next_gripper_command  = action[6]
```

建议第一版限幅：

| 项 | 建议值 | 说明 |
| --- | --- | --- |
| `max_abs_joint_delta_per_step` | `0.03 rad` | 可根据控制频率调整 |
| `max_abs_joint_delta_eval` | `0.05 rad` | 仅用于离线或慢速验证 |
| `gripper_range` | `[0.0, 1.0]` | 与现有 `gripper_opening` 语义一致 |
| `policy_fps` | `10 Hz` | 第一版保守，降低抖动和写盘压力 |
| `action_chunk_size` | 与 pi0.5 config 对齐 | 如果使用默认 chunk，应在 config 中记录 |

如果后续使用 LeRobot 的 relative actions，建议保持“关节为相对动作、夹爪为绝对开合”的语义，即 gripper 不参与 relative action 变换。

#### 8.4.5 时间对齐与重采样

raw 数据中视觉、状态和动作可能不是完全同频。转换器应生成统一训练采样点：

```text
policy_t = episode_start + k / policy_fps
```

每个 `policy_t` 按以下规则匹配：

1. 选择最近的有效状态样本，要求时间差小于 `state_max_delta_ms`。
2. 选择最近且不晚于该动作时间太多的有效视觉帧，要求 `camera_capture_ok=true`。
3. 选择该时刻之后一个控制周期内的人类动作目标，或根据连续 target 计算 joint_delta。
4. 若任一字段缺失，则该 step 标记为 rejected，不进入训练样本。
5. 若某个 episode 有效样本比例低于阈值，则整个 episode 从训练候选中剔除。

建议第一版阈值：

| 项 | 建议值 |
| --- | --- |
| `state_max_delta_ms` | `50` |
| `visual_max_delta_ms` | `80` |
| `action_max_delta_ms` | `100` |
| `min_valid_step_ratio` | `0.95` |
| `max_stub_frame_count` | `0` |
| `max_rgb_depth_delta_ms` | 沿用 `shared/dataset_schema.json` 中的 `5 ms` |

#### 8.4.6 split 规则

训练划分必须按 episode 级别做，不能按帧随机打散。否则同一条轨迹的相邻帧会同时进入 train 和 val，验证指标会虚高。

建议第一版比例：

```text
train: 80%
val:   10%
test:  10%
```

划分规则：

- 同一个 `reset_seed` 不要同时出现在 train 和 test。
- 同一工具类别在三个 split 中都要覆盖。
- 如果某类工具 episode 很少，先保证 val/test 至少各有 1 条成功 episode。
- `debug_trial` 默认不进入任何训练 split。
- `pilot` 默认不进入训练，除非人工标记 `included_in_train=true`。
- `train_candidate` 仍需通过自动校验和人工抽查。

#### 8.4.7 转换报告

每次转换必须生成 `conversion_report.json`，至少包含：

| 字段 | 说明 |
| --- | --- |
| `raw_root` | 输入 raw 数据目录 |
| `output_root` | 输出 LeRobot / OpenPI 数据目录 |
| `converter_version` | 转换脚本版本 |
| `dataset_schema_version` | raw schema 版本 |
| `camera_config_version` | D405 配置版本 |
| `policy_fps` | 重采样频率 |
| `state_mode` | 状态向量定义 |
| `action_mode` | 动作向量定义 |
| `num_raw_episodes` | 原始 episode 数 |
| `num_included_episodes` | 纳入训练候选的 episode 数 |
| `num_rejected_episodes` | 剔除 episode 数 |
| `reject_reason_counts` | 各类剔除原因统计 |
| `num_frames` | 转换后样本数 |
| `split_counts` | train / val / test 数量 |
| `tool_class_counts` | 各工具类别数量 |
| `input_feature_shapes` | 输入特征 shape |
| `action_dim` | 动作维度 |
| `normalization_stats_path` | stats 文件路径 |

### 8.5 pi0.5 初训开发规格

#### 8.5.1 训练目标

第一阶段目标不是让模型马上在大随机场景中高成功率，而是达成以下闭环：

```text
转换后的 LeRobot / OpenPI 数据集
  -> pi0.5 fine-tune
  -> checkpoint / exported policy
  -> MuJoCo policy runtime
  -> 固定场景能复现基本抓取放置行为
```

第一版成功标准：

- 模型能读取 `observation.images.d405_rgb + observation.state + prompt`。
- 模型输出 7 维动作并能被 runtime 转成 `/sim/step/` 命令。
- 固定工具位置下能完成或接近完成抓取-放置轨迹。
- 推理轨迹没有明显高频抖动、关节跳变或夹爪乱开合。
- 训练 run 可复现，能追溯到数据集版本、split、config 和 checkpoint。

#### 8.5.2 建议新增文件

```text
configs/pi05/
  quest3_tool_sorting_v1_pi05.yaml
  quest3_tool_sorting_v1_pi05_debug.yaml

scripts/training/
  train_pi05.py
  export_pi05_policy.py
  evaluate_pi05_offline.py
  evaluate_pi05_mujoco.py

backend/policies/
  __init__.py
  policy_loader.py
  pi05_policy_adapter.py
  action_postprocess.py
```

其中：

- `train_pi05.py` 可以是 LeRobot/OpenPI CLI 的项目包装器，负责读取本项目 config、创建 run 目录、写入元数据。
- `evaluate_pi05_offline.py` 负责在 val/test 上统计 action loss、轨迹误差、夹爪动作误差。
- `evaluate_pi05_mujoco.py` 负责把模型加载回 MuJoCo 执行 episode。
- `pi05_policy_adapter.py` 负责把当前后端状态转换为 pi0.5 inference 输入，并把 action chunk 转成 `/sim/step/`。

#### 8.5.3 训练配置必须记录的字段

每次训练 run 的 `config.json` 或 YAML 必须记录：

| 字段 | 说明 |
| --- | --- |
| `run_id` | 训练运行 ID |
| `base_model` | 例如 `pi05_base` 或 LeRobot pi05 base checkpoint |
| `dataset_root` | 转换后的 LeRobot / OpenPI 数据集路径 |
| `raw_dataset_root` | 原始数据集路径 |
| `split_file` | train / val / test 划分文件 |
| `feature_mapping_path` | feature mapping 文件 |
| `normalization_stats_path` | stats 文件 |
| `image_key` | 默认 `observation.images.d405_rgb` |
| `state_key` | 默认 `observation.state` |
| `prompt_key` | 默认 `task` / `prompt` |
| `action_key` | 默认 `action` |
| `state_dim` | 默认 `7` |
| `action_dim` | 默认 `7` |
| `policy_fps` | 默认 `10` |
| `action_mode` | 默认 `joint_delta_gripper_abs` |
| `camera_intrinsics_version` | D405 内参版本 |
| `camera_extrinsics_version` | D405 外参版本 |
| `training_mode` | `expert_only / lora / full_finetune` 等 |
| `batch_size` | 按显存调整 |
| `steps` | 训练步数 |
| `seed` | 随机种子 |
| `git_commit` | 代码版本 |

#### 8.5.4 第一版训练策略

建议第一版采用保守配置：

- 优先使用 `train_expert_only=true`、LoRA 或等效低成本微调方式。
- 如果显存不足，冻结 vision encoder，先训练 action expert / projection。
- 第一版先使用 RGB，不默认把 Depth 接入 pi0.5 主干。
- 不使用 ground-truth object pose 作为模型输入。
- 使用 action/state mean-std normalization；如果所用 LeRobot 版本要求 quantile stats，则在训练前生成 quantile stats。
- 若使用 relative actions，应保证 `chunk_size`、stats 和训练 config 一致，并让 gripper 保持绝对开合量。

第一版可接受的训练命令包装形式：

```bash
python scripts/training/train_pi05.py \
  --config configs/pi05/quest3_tool_sorting_v1_pi05.yaml \
  --dataset-root data/datasets/quest3_tool_sorting_v1/processed/pi05_lerobot_v1 \
  --run-id run_YYYYMMDD_HHMM_pi05_v1
```

内部可以调用 OpenPI 或 LeRobot 官方训练入口，但项目侧必须统一输出到：

```text
models/pi05/initial_runs/<run_id>/
  config.json
  feature_mapping.json
  dataset_snapshot.json
  normalization_stats.json
  checkpoints/
  exported/
  logs/
  offline_eval/
  mujoco_validation/
```

#### 8.5.5 离线评估

离线评估不代表任务成功，但可以快速发现数据和训练问题。建议至少输出：

| 指标 | 说明 |
| --- | --- |
| `val_action_mse` | 归一化或反归一化动作误差 |
| `joint_delta_mse` | 6 轴关节增量误差 |
| `gripper_mae` | 夹爪动作误差 |
| `action_smoothness` | 预测动作变化率 |
| `language_condition_check` | 不同 prompt 是否输出不同动作分布 |
| `tool_class_breakdown` | 按工具类别统计误差 |
| `failure_case_samples` | 保存若干误差最大样本 |

离线评估需要生成：

```text
models/pi05/initial_runs/<run_id>/offline_eval/
  metrics.json
  per_tool_metrics.json
  worst_samples.jsonl
  action_plot_episode_0001.png
```

#### 8.5.6 MuJoCo 策略验证

初训模型入库后，应支持可选 MuJoCo 验证。验证入口建议为：

```bash
python scripts/training/evaluate_pi05_mujoco.py \
  --model-run models/pi05/initial_runs/<run_id> \
  --num-episodes 30 \
  --eval-split fixed_and_random \
  --save-video true
```

验证运行时：

1. reset 场景。
2. 绑定目标工具和 prompt。
3. 从 `/sim/observation/` 或内部 policy adapter 构造模型输入。
4. 调用 pi0.5，得到 action chunk。
5. 通过 `action_postprocess.py` 做限幅、平滑、安全检查。
6. 调用 `/sim/step/` 或 `SimulationCore.enqueue_step()` 执行动作。
7. 记录抓取、抬升、放置、碰撞、超时等指标。

建议验证指标：

| 指标 | 说明 |
| --- | --- |
| `grasp_success_rate` | 成功抓取比例 |
| `place_success_rate` | 成功放入工具箱比例 |
| `tool_putaway_success_rate` | 完整任务成功率 |
| `mean_duration_s` | 平均耗时 |
| `drop_failure_rate` | 掉落失败比例 |
| `collision_block_rate` | 碰撞拦截比例 |
| `mean_action_norm` | 动作幅值 |
| `jitter_score` | 高频抖动评分 |
| `per_tool_success` | 按 wrench / screwdriver / pliers 统计 |

验证结果写入：

```text
models/pi05/initial_runs/<run_id>/mujoco_validation/
  eval_config.json
  metrics.json
  episodes.jsonl
  videos/
  snapshots/
```

### 8.6 强化学习微调开发规格

#### 8.6.1 RL 阶段定位

RL 微调不是替代 pi0.5，也不建议第一版直接对整个 VLA 做在线 RL。当前更可行的定义是：

```text
pi0.5 提供模仿学习动作先验
RL 学习低维 residual / correction
最终执行动作 = pi0.5_action + rl_residual
```

这样做有几个好处：

- RL 动作空间小，训练更稳定。
- 不需要频繁反向更新 4B 级 VLA 大模型。
- 可以保留 pi0.5 的视觉语言能力，让 RL 只修正抓取精度、放置精度和稳定性。
- 后续如果要实机迁移，residual 层更容易加安全限制。

第一版 RL 的目标建议写成：

```text
在随机工具位置和小范围姿态扰动下，提升 pi0.5 初训模型的抓取稳定性、放置成功率和轨迹平滑性。
```

#### 8.6.2 RL 前置条件

进入 RL 前必须满足：

- S6 已实现抓取成功判定、放置成功判定、附着和释放机制。
- `grasp_state` 能稳定区分 `none / candidate / attached / released / failed`。
- `tool_putaway_success` 可由程序判定，而不是只靠人工观察。
- `collision_blocked`、`max_penetration_depth_m`、`drop_failure` 能进入日志。
- 初训 `pi0.5` 模型已入库，并能通过 policy adapter 在 MuJoCo 中执行。
- 至少有一个脚本化 baseline 和一个 pi0.5 IL baseline 可比较。

如果这些条件不满足，只能做 RL env smoke test，不应开始正式 RL 训练。

#### 8.6.3 RL 环境接口

建议新增：

```text
backend/rl/envs/tool_sorting_env.py
backend/rl/rewards/tool_sorting_reward.py
backend/rl/curriculum/tool_sorting_curriculum.py
backend/rl/policies/residual_policy.py
scripts/training/finetune_rl.py
scripts/training/evaluate_policy.py
```

环境接口建议采用 Gymnasium 风格：

```python
obs, info = env.reset(seed=seed, options={"tool_class": "wrench"})
obs, reward, terminated, truncated, info = env.step(action)
```

`info` 至少包含：

```text
sim_time
target_tool_id
target_tool_class
grasp_state
attached_to_gripper
grip_success
place_success
tool_putaway_success
collision_blocked
collision_objects
max_penetration_depth_m
drop_failure
timeout
reward_terms
```

#### 8.6.4 RL observation 设计

第一版 RL observation 建议分为两类：

| 类型 | 是否给 RL policy | 说明 |
| --- | --- | --- |
| `policy_observation` | 是 | 未来实机可用字段 |
| `privileged_info` | 否，只用于 reward / logging | MuJoCo 内部真值 |

`policy_observation` 建议包含：

```text
qpos[0:6]
gripper_opening
ee_pose
pi0.5_action_current
pi0.5_action_chunk_phase
target_tool_class_onehot
optional: compact visual embedding 或最近 D405 RGB 特征
```

第一版 residual RL 可以先不直接训练视觉网络，而是使用 pi0.5 已经输出的动作作为视觉语言先验。这样 RL 更像“动作修正器”。

`privileged_info` 可包含：

```text
target_tool_pose
toolbox_slot_pose
distance_ee_to_tool
distance_tool_to_slot
tool_height
contact_state
inside_toolbox_flag
```

注意：`privileged_info` 可以用于 reward，但不要输入给最终部署策略，否则 sim2real 会断。

#### 8.6.5 RL action 设计

第一版推荐 residual action：

```text
rl_action[0:6] = residual_joint_delta_rad
rl_action[6]   = residual_gripper_delta 或 gripper_override

final_joint_delta = clip(pi0.5_joint_delta + residual_joint_delta)
final_gripper     = clip(pi0.5_gripper_target + residual_gripper_delta, 0, 1)
```

建议限幅：

| 项 | 建议值 |
| --- | --- |
| `residual_joint_delta_limit` | `0.01 ~ 0.02 rad` |
| `final_joint_delta_limit` | `0.03 rad` |
| `residual_gripper_limit` | `0.10` |
| `action_smoothing_alpha` | `0.3 ~ 0.6` |

这样即使 RL 初期策略不稳定，也不会彻底破坏 pi0.5 的动作先验。

#### 8.6.6 奖励函数第一版

建议第一版 reward 明确拆项，并在每一步写入 `reward_terms`：

```text
reward =
  w_reach      * r_reach_tool
+ w_align      * r_pregrasp_align
+ w_grasp      * r_grasp_success
+ w_lift       * r_lift
+ w_transport  * r_transport_to_toolbox
+ w_place      * r_place_success
+ w_success    * r_task_success
- w_collision  * p_collision
- w_drop       * p_drop
- w_timeout    * p_timeout
- w_action     * p_action_magnitude
- w_jitter     * p_action_jitter
```

建议第一版权重：

| 项 | 建议权重 | 说明 |
| --- | --- | --- |
| `w_reach` | `1.0` | 末端接近目标工具 |
| `w_align` | `0.3` | 抓取姿态对齐，第一版可弱化 |
| `w_grasp` | `3.0` | 成功附着或稳定夹持 |
| `w_lift` | `2.0` | 工具离开桌面达到高度阈值 |
| `w_transport` | `1.0` | 工具接近工具箱目标区域 |
| `w_place` | `4.0` | 工具释放且位于工具箱内 |
| `w_success` | `10.0` | 完整任务成功终止奖励 |
| `w_collision` | `2.0` | 禁止碰撞或穿透惩罚 |
| `w_drop` | `4.0` | 中途掉落惩罚 |
| `w_timeout` | `2.0` | 超时惩罚 |
| `w_action` | `0.01` | 动作幅值正则 |
| `w_jitter` | `0.05` | 抖动惩罚 |

各项定义建议：

```text
r_reach_tool = exp(-distance(ee, target_tool_grasp_pose) / 0.10)
r_lift = clamp((tool_z - table_z) / 0.10, 0, 1)
r_transport_to_toolbox = exp(-distance(tool, target_slot) / 0.15)
r_grasp_success = 1 if grasp_state == attached else 0
r_place_success = 1 if released and inside_toolbox else 0
r_task_success = 1 if tool_putaway_success else 0
```

第一版不要把 reward 设计得过于复杂。先保证每一项都能解释、能记录、能画曲线。

#### 8.6.7 curriculum 与随机化

RL 难度建议分阶段增加：

| 阶段 | 随机化范围 | 目标 |
| --- | --- | --- |
| `rl_debug_fixed` | 固定工具、固定工具箱 | 检查 env / reward / action 是否工作 |
| `rl_easy_position` | 工具 XY 小范围随机，yaw 固定 | 学会修正接近和抓取误差 |
| `rl_medium_pose` | 工具 XY + yaw 随机 | 提升抓取姿态适应性 |
| `rl_place_random` | 工具箱目标区域小范围扰动 | 提升放置鲁棒性 |
| `rl_sim2real_noise` | 加入视觉噪声、状态噪声、延迟、摩擦扰动 | 为实机迁移做准备 |

每个阶段必须记录：

```text
randomization_config.json
reward_config.json
success_rate_by_seed.json
failure_breakdown.json
```

#### 8.6.8 RL 算法建议

第一版可选两条路线：

| 路线 | 建议优先级 | 说明 |
| --- | --- | --- |
| `PPO residual policy` | P0 | 实现简单，适合连续小动作修正和并行环境 |
| `SAC residual policy` | P1 | 样本效率可能更好，但调参复杂 |

P0 建议先实现 `PPO residual policy`。原因是本项目第一阶段更需要稳定工程闭环，而不是最大化样本效率。

训练命令建议：

```bash
python scripts/training/finetune_rl.py \
  --base-policy models/pi05/initial_runs/<pi05_run_id> \
  --config configs/rl/tool_sorting_residual_ppo.yaml \
  --run-id run_YYYYMMDD_HHMM_rl_residual_v1 \
  --num-envs 8 \
  --total-steps 500000
```

输出目录：

```text
models/rl/finetune_runs/<run_id>/
  config.json
  reward_config.json
  randomization_config.json
  base_policy_ref.json
  checkpoints/
  exported/
  logs/
  eval/
  mujoco_validation/
```

#### 8.6.9 RL 评估与成功标准

RL 评估必须和 pi0.5 初训模型做同种 seed、同种随机化范围对比。

建议至少评估：

```text
scripted baseline
pi0.5 IL baseline
pi0.5 + RL residual
```

每组至少：

- `fixed` 场景 20 episodes。
- `easy_random` 场景 50 episodes。
- `medium_random` 场景 100 episodes，如果时间允许。

核心指标：

| 指标 | 预期 |
| --- | --- |
| `tool_putaway_success_rate` | RL 相比 pi0.5 IL 有提升 |
| `grasp_success_rate` | 不低于 IL，最好提升 |
| `place_success_rate` | 明显提升或更稳定 |
| `collision_failure_rate` | 不高于 IL |
| `drop_failure_rate` | 不高于 IL |
| `mean_duration_s` | 不显著变差 |
| `jitter_score` | 不显著变差 |

第一版可接受目标：

- 固定场景：`pi0.5 + RL` 不低于 `pi0.5 IL`。
- 随机场景：`pi0.5 + RL` 在成功率或失败率上有可测提升。
- 如果 RL 只提升训练 seed、不提升 held-out seed，则不能作为最终模型，只能作为调试结果。

### 8.7 统一模型注册与部署接口

所有进入模型目录的模型都应能通过统一接口被加载：

```text
models/registry/active_policy.json
```

建议格式：

```json
{
  "active_policy_id": "rl_residual_run_YYYYMMDD_HHMM",
  "policy_stage": "pi05_rl_residual",
  "runtime_target": "sim",
  "base_pi05_run_id": "run_YYYYMMDD_HHMM_pi05_v1",
  "model_path": "models/rl/finetune_runs/run_YYYYMMDD_HHMM_rl_residual_v1/exported/policy.pt",
  "adapter": "backend.policies.pi05_residual_adapter",
  "action_mode": "joint_delta_gripper_abs",
  "state_mode": "qpos_gripper",
  "policy_fps": 10,
  "camera_device": "intel_realsense_d405",
  "camera_mount_name": "wrist_d405_v1",
  "camera_intrinsics_version": "d405_intr_20260412_a",
  "camera_extrinsics_version": "d405_ext_20260412_a",
  "validated_in_mujoco": true,
  "mujoco_validation_path": "models/rl/finetune_runs/run_YYYYMMDD_HHMM_rl_residual_v1/mujoco_validation/metrics.json"
}
```

前端或后端任务入口不应硬编码模型路径，而应通过 registry 激活策略。

### 8.8 训练阶段验收标准

#### 8.8.1 数据转换验收

- raw episode 能转换为 LeRobot / OpenPI 可读数据集。
- 转换后样本包含 `observation.images.d405_rgb`、`observation.state`、`action`、`task/prompt`。
- `conversion_report.json` 能说明纳入和剔除 episode 的原因。
- train / val / test 按 episode 划分。
- normalization stats 已生成并与训练 config 绑定。

#### 8.8.2 pi0.5 初训验收

- 能基于转换后的数据集启动训练。
- 能生成 checkpoint、best model、exported policy。
- 能写入 `models/pi05/initial_runs/<run_id>/`。
- 离线评估能输出动作误差和按工具类别的指标。
- 初训模型能通过 policy adapter 在 MuJoCo 中跑通基础推理。

#### 8.8.3 RL 微调验收

- `tool_sorting_env.py` 能 reset、step、返回 reward 和 info。
- RL env 能加载 pi0.5 初训模型作为 base policy。
- residual policy 能训练并保存 checkpoint。
- RL 模型能写入 `models/rl/finetune_runs/<run_id>/`。
- RL 模型能和 scripted / pi0.5 IL 做同 seed 对比。
- 若 RL 成功率没有提升，也必须输出失败分析，而不是只保留 checkpoint。

#### 8.8.4 Sim2Real 约束

为了保证最终模型有机会迁移到真实 UR5，训练阶段继续遵守：

| 维度 | 约束 |
| --- | --- |
| 观测 | 第一版 pi0.5 输入只使用未来实机可直接获得或可稳定估计的字段 |
| 动作 | 初训和 RL 共用 `joint_delta + gripper_target` 语义 |
| 相机 | 训练输入固定为末端 D405 主视角，不使用 Quest3 页面画面 |
| 标定 | 训练 run 记录内参、外参、mount 版本 |
| 安全 | 策略输出必须经过限幅、平滑、碰撞检查和 watchdog |
| 随机化 | RL 后期逐步加入视觉噪声、状态噪声、延迟、摩擦和质量扰动 |
| 日志 | 每次训练和验证都保存 config、seed、数据集版本、模型版本和失败案例 |

---

## 9. 前后端改造重点

### 9.1 前端需要改的核心点

- `tools + toolbox` 场景替换已完成，后续重点是任务执行与采集训练闭环
- 优先把末端 `D405` 的模型、挂载姿态和 `RGB-D` 预览能力接入前端
- 底部按钮将 `状态同步` 改为 `VR模式`
- 在底部导航栏新增 `采集` 入口，作为数据集录制的主入口；详细的开始、停止、模式选择和校验信息放入二级面板，避免误触
- 新增 Quest3 模式菜单，不覆盖现有界面
- 新增采集状态显示：
  - 当前 session
  - 当前 episode
  - 当前输入模式
  - 是否正在录制
  - 当前采集等级：`debug_trial / pilot / train_candidate`
  - 当前目标工具与 `instruction_text`
- 新增视觉采集状态显示：
  - 当前相机设备 `D405`
  - `RGB` / `Depth` 是否在线
  - 最近一帧时间戳
  - 当前标定版本
- 新增采集前置检查状态显示：
  - 相机是否真实可用，不能只是 stub 图像
  - reset 初始状态是否合法
  - S4.5 物理边界基线是否通过
  - 当前是否允许正式录制
- 新增接触与安全状态显示：
  - `safety_status`
  - 碰撞拦截原因
  - 当前 `grasp_state`
  - 当前 episode 是否只属于 `debug_trial`
- 新增回放与人工筛选入口：
  - 快速查看 RGB 预览视频
  - 查看 Depth 原始图或伪彩深度图
  - 查看状态/动作/接触时间轴
  - 标记是否纳入训练集
- 继续增强多工具对象状态同步稳定性与插值质量
- 根据 Quest3 能力决定展示桌面端 UI 还是 Quest3 精简 UI

### 9.2 后端需要改的核心点

- 多对象状态模型（`tools[] + toolbox`）已落地，后续重点是任务与策略运行时
- 新增末端 `D405 RGB-D` 观测导出链路
- 新增 Quest3 输入桥接层或 VR 输入状态模型
- 新增数据集记录器
- 新增采集前置检查器：
  - 检查相机、状态、动作、reset、语言标签和安全壳
  - 输出 `recording_ready`
  - 阻止不合格 episode 进入正式录制
- 新增 episode 校验器：
  - 生成 `validation_summary.json`
  - 检查缺帧、错帧、stub 图像、未对齐、穿模、reset 非法和语言缺失
- 新增回放与预览导出：
  - RGB/Depth 单帧读取
  - MP4 预览视频
  - 状态/动作/接触时间轴
- 新增模型加载器与模型注册器
- 新增 MuJoCo 模型验证运行器
- 新增任务运行时：
  - 脚本化任务
  - 初训模型推理
  - 强化学习模型推理
- 新增抓取判定与附着逻辑
- 已完成 S4.5 物理边界与前后端虚拟干涉修复：
  - 桌面、工具箱、工具对象和夹爪交互区域具备统一物理边界
  - reset 合法性基线已补齐
  - 手动控制与 Quest3 控制复用同一边界基线
- 后续仍需把碰撞、接触、抓取和释放事件写入录制日志

### 9.3 共享配置需要改的核心点

在保留 `shared/scene_manifest.json` 的基础上，建议后续新增：

- `shared/tool_catalog.json`
- `shared/camera_sensor_config.json`
- `shared/vr_mode_config.json`
- `shared/dataset_schema.json`
- `shared/contact_safety_config.json`
- `shared/reset_randomization_config.json`

其中：

- `scene_manifest` 负责场景布局与位姿基线
- `tool_catalog` 负责工具资产、尺寸、质量、抓取提示位姿
- `camera_sensor_config` 负责 `D405` 的挂载位姿、分辨率、深度尺度、内外参版本和导出字段
- `vr_mode_config` 负责输入模式、关节组、按钮映射
- `dataset_schema` 负责采集字段定义
- `contact_safety_config` 负责允许接触、禁止接触、穿透阈值和 safe hold 策略
- `reset_randomization_config` 负责工具/工具箱采样区域、姿态限制、重采样上限和合法性检查

### 9.4 面向 Sim2Real 的接口改造重点

如果最终希望 RL 权重能迁移到真实 UR5，那么后端与共享配置层还需要预留以下接口约束：

- 定义统一的 `runtime_target`，至少支持 `sim` 与未来的 `real_ur5`
- 为 MuJoCo 执行端和真实机械臂执行端保留一致的高层动作接口
- 为实机关节回读、夹爪回读、状态广播预留同构字段
- 为桌面、工具箱、工具标定结果预留配置加载位置
- 为 watchdog、限速、急停、掉线保护预留运行时状态字段
- 为模型注册表增加“是否可部署到实机”“对应标定版本”“对应控制周期”等元数据

---

## 10. 建议的目录重构

基于你现在的目标，后续代码结构建议逐步演进为：

```text
backend/
  api_app.py
  main.py
  schemas.py
  sim/
    simulation.py
    task_runtime.py
    vr_input_bridge.py
    dataset_recorder.py
    tool_state_manager.py
    policy_loader.py
    model_registry.py
    mujoco_validation_runner.py
  tasks/
    tool_sorting_scripted.py
  rl/
    envs/
      tool_sorting_env.py
    train_pi05.py
    finetune_rl.py
    evaluate_policy.py

shared/
  scene_manifest.json
  tool_catalog.json
  vr_mode_config.json
  dataset_schema.json

frontend/
  src/
    components/
      vrModePanel.vue
      questStatusPanel.vue
      datasetRecorderPanel.vue

data/
  datasets/
  replay/
  calibration/
models/
  pi05/
    initial_runs/
  rl/
    finetune_runs/
  registry/
logs/
experiments/
```

说明：

- 本轮不创建这些目录，仅在文档中冻结后续组织方式。
- 这样做的目的是防止后续边开发边改目录，导致数据、模型和实验记录到处散落。

---

## 11. 分阶段实施建议

### 阶段 S0：基线固化与旧任务归档（已完成）

目标：

- 已明确旧 battery 版本的完成边界
- 已把现有代码状态作为“旧任务基线”归档
- 已在此基础上切换到工具抓取任务

### 阶段 S1：工具场景替换（已完成）

目标：

- 已完成前后端场景从电池资产到工具资产的替换
- 已完成 `tools + toolbox` 的统一场景定义
- 已完成多对象状态同步与重置随机投放

### 阶段 S1.5：末端 D405 RGB-D 相机接入与观测链冻结

目标：

- 完成 `Intel RealSense D405` 作为主视觉传感器的场景定义
- 按 `pic/camera.jpg` 的安装参考冻结末端挂载方案
- 让仿真侧具备可录制的 `RGB` 与 `Depth` 输出
- 让数据结构明确支持 `RGB-D + 状态 + 动作 + 文本`

### 阶段 S2：Quest3 非沉浸式 VR 控制

目标：

- 完成 LAN 访问
- 完成 `VR模式` UI
- 完成手柄模式
- 完成手势模式
- 完成 Quest3 模式切换与输入状态同步

### 阶段 S2.5：物理边界与前后端虚拟干涉修复（已完成）

目标：

- 明确 VR 控制目前不是完整真实力控抓取，S4.5 只解决物理边界和虚拟干涉问题
- 已统一前端可视边界和后端 MuJoCo 物理边界
- 已让机械臂/夹爪不再明显穿桌、穿箱或穿过工具
- 已让 reset 后工具与工具箱姿态符合当前真实桌面任务基线
- 将第一版抓取判定与临时附着语义移到后续任务闭环阶段
- 后续录制器仍需要写入 `safety_status`、`contact_state`、`grasp_state`

### 阶段 S3：数据集采集闭环

目标：

- 完成正式采集前置检查
- 完成 session / episode 管理
- 完成录制开始、停止、保存
- 完成数据回放
- 完成 Quest3 操作元数据记录
- 完成 `debug_trial -> pilot -> train_candidate` 的数据分级
- 完成 `validation_summary.json` 自动生成与训练候选筛选

### 阶段 S4：pi0.5 初训

目标：

- 完成训练数据预处理
- 完成模仿学习训练脚本
- 完成离线评估和 checkpoint 管理
- 完成初训模型入库
- 支持初训模型在需要时加载到 MuJoCo 中做仿真验证

### 阶段 S5：强化学习微调

目标：

- 完成 MuJoCo RL 环境
- 能够加载初训模型作为基线或 warm start
- 完成 reward 与 randomization
- 完成 fine-tune 训练
- 完成强化学习模型入库
- 支持强化学习模型在需要时加载到 MuJoCo 中做仿真验证
- 完成和初训模型的对比

### 阶段 S6：Sim2Real 就绪与实机迁移准备

目标：

- 在不破坏现有仿真主链路的前提下，为真实 UR5 接入提前冻结接口和安全约束
- 让初训模型与 RL 模型都具备走向实机部署的基础条件

### 阶段 S7：论文实验与结果固化

目标：

- 固定实验配置
- 批量评估
- 导出图表、视频、日志和统计表
- 整理论文中的方法、实验设置、结果与消融

---

## 12. 论文导向的实验指标建议

至少建议记录以下指标：

- 抓取成功率
- 放置成功率
- 平均任务时长
- 平均轨迹长度
- 平均碰撞次数
- 掉落率
- 不同输入模式下的数据采集效率
- `RGB-D` 帧有效率
- `RGB` / `Depth` 时间对齐误差
- 深度缺帧率与无效像素占比
- `pi0.5` 初训与 `pi0.5 + RL` 微调的性能差异
- 随机位置下的泛化成功率

如果后续进入 sim2real 联调阶段，建议额外记录：

- 仿真与实机使用的动作接口是否完全一致
- 标定版本与策略版本的对应关系
- 实机控制周期、推理周期与延迟统计
- 安全停、watchdog、掉线保护触发次数
- 仿真验证与实机验证的成功率差值

建议论文至少做三组主对比：

1. 仅脚本或规则基线
2. 仅模仿学习
3. 模仿学习 + 强化学习微调

如果时间允许，再补两组消融：

4. 手柄数据集 vs 手势数据集
5. 单工具场景 vs 多工具场景

---

## 13. 当前最重要的结论

1. 当前最有价值的既有成果，是前后端场景与状态同步基础，而不是任务本身已经完成。
2. 场景切换（`battery_pack` -> `tools + toolbox`）已经完成，下一步应聚焦任务闭环、数据采集与训练链路。
3. 在开始 VR 任务之前，必须先把末端 `D405 RGB-D` 相机的安装定义、仿真对应与采集字段冻结下来，否则后续数据无法直接用于 `pi0.5`。
4. Quest3 采集链路必须尽早设计好 `RGB-D + 状态 + 动作 + 文本` 数据格式，否则后面训练和论文都会返工。
5. VR 已经能控制机械臂，且 S4.5 已解决物理边界与前后端虚拟干涉问题；下一步仍不能直接批量采集，必须先把录制器、回放筛选和接触/抓取状态日志接入。
6. 第一版不建议死磕完全真实物理夹取，应优先在已完成的物理边界基线上采用“接触检查 + 抓取判定 + 临时附着 + 释放校验”的半物理方案，保证数据可重复。
7. `execute_task`、抓取附着、数据记录、模型加载、MuJoCo 验证入口、RL 环境目前都没有真正落地，这是后续主工作量。
8. 训练链条必须明确是“你采集和初训，系统搭 RL 环境与验证入口”，不能混成一个模糊阶段。
9. VR 需求里最需要尽早澄清的是“非沉浸式体验”与“Quest 输入 API 可用性”的技术边界；本文档已按“体验非沉浸、实现允许轻量 XR”处理。
10. 由于最终权重希望具备实机可用性，所以动作接口、观测字段、模型加载方式和安全状态从现在起就要按 sim2real 方向设计，尤其是末端 `D405` 的模态、标定和时序一致性。

---

## 14. 推荐的下一步开发顺序

建议严格按下面顺序推进：

1. 在已完成工具场景冻结的基础上，先完成末端 `D405` 的挂载定义、安装参考确认和 `RGB-D` 输出设计
2. S4.5 物理边界与 reset 合法性已经完成，后续以该结果作为采集前置基线
3. 再建立面向 `RGB-D + 状态 + 动作 + 文本 + 接触/安全状态` 的数据集目录、格式和录制协议
4. 再完成 Quest3 `VR模式` 交互和输入状态设计
5. 再做 Quest3 局域网控制链与录制器闭环
6. 再进行 `debug_trial` 和 `pilot` 试采，确认回放、校验和筛选可用
7. 再做脚本化工具抓取任务和第一版半物理抓取附着机制
8. 再进入 `pi0.5` 初训，完成模型入库，并预留 MuJoCo 验证入口
9. 最后进入 RL 微调，完成 RL 模型入库，并同样预留 MuJoCo 验证入口
10. 在 RL 主链路稳定后，补齐 `runtime_target`、标定、watchdog 和部署接口，为真实 UR5 接入做准备

这条顺序的核心原因是：

- 场景不稳定，数据集就不稳定
- 主相机方案不稳定，视觉数据集就不稳定
- S4.5 物理边界虽然已经完成，但录制器和回放筛选不稳定时，示教数据仍无法直接进入训练集
- 抓取附着和释放状态机不稳定，数据分布会偏离真实桌面工具抓取任务
- 数据格式不稳定，训练脚本就会反复返工
- Quest3 控制链和录制器没稳定，人工采集质量就无法保证
- 脚本化任务没跑通，RL 很难高效收敛
- 如果完全不预留 MuJoCo 验证入口，后续就很难定位问题到底出在数据、模型还是环境
- 没有实验记录规范，后续论文会非常被动
