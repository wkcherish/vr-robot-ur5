# Quest3 VR 数据采集转 LeRobot 并微调 pi0.5 ToDo（2026-06-08 任务回归）

基于 [task.md](task.md) 重新整理。  
本清单以 `2026-04-12` 主分支真实代码状态为基准，分成两部分：

1. 当前已经完成的基线总结
2. 围绕 Quest3 / VR 采集数据、转换 LeRobot 格式并微调 pi0.5 的新主链路任务

说明：

- `P0`：主链路必做，直接影响实验是否成立
- `P1`：重要增强项，建议主链路稳定后补齐
- `P2`：优化项、结果分析增强项或后续扩展项
- 本轮是文档重构，不创建目录、不修改业务代码

---

## 一、已完成基线总结

这一部分对应“旧 ToDo 中已经完成、而且经代码复核确认属实”的内容。

### A0-1. 2026-05-11 关节限位双侧裁剪修复

- [x] `P0` 后端 `SimulationCore` 在加载 MuJoCo 模型时缓存所有受限手臂关节的 `jnt_range`（`_arm_joint_limits`）
- [x] `P0` 在 `_apply_arm_command` 之前新增 `_clamp_arm_targets`，对来自任意 `source`（manual / vr / replay 等）的目标关节角逐维 clamp 到 `[lo, hi]`
- [x] `P0` 状态广播 `state_broadcast` / `state_update` 中新增 `joint_limits` 字段（与 `joint_names` 同序），向前端公布限位
- [x] `P0` 前端 `frontend/src/utils/websocket.js` 在 `handleStateUpdate` 中缓存 `jointNames` / `jointLimits`
- [x] `P0` 前端 `sendControlCommand` 在发送前调用新的 `clampToJointLimits` 完成预裁剪，避免越界目标进入网络与 MuJoCo
- [x] `P0` 解决的问题：Quest3 / VR 控制及面板手动控制在大幅累加增量时，UR5 关节会越过物理限位导致 MuJoCo 报警或姿态翻飞；现在前后端形成“前端预裁剪 + 后端兜底裁剪”的双层防护

### A0. 2026-04-24 VR 控制与性能修复记录

- [x] `P0` 修复 Quest3 进入 VR 后已选模式但控制链不稳定的问题（会话创建时机、输入采样链、发送链路）
- [x] `P0` 明确并落地手柄模式按键映射细节（含精细模式、关节组选取、右扳机夹爪）
- [x] `P0` 明确并落地手势模式阈值与拖拽规则（双手选组、单手轮切、食指拖拽、中指夹爪）
- [x] `P0` 为 VR 状态同步与控制命令增加节流、in-flight 与超时回收机制，避免命令堆积
- [x] `P0` 降低后端相机状态构建路径的深拷贝开销，缓解前端高负载场景下的卡顿风险
- [x] `P0` 输出本次参数级修改说明文档：`docs/vr_control_and_performance_update_2026-04-24.md`

### A. 仓库与共享基线

- [x] `P0` 已有 `shared/scene_manifest.json` 作为场景基线
- [x] `P0` 已在 manifest 中定义 UR5、rack、toolbox、wrench_01、screwdriver_01、pliers_01、camera_base、camera 的初始位姿
- [x] `P0` 已在 manifest 中记录 UR5 home 姿态与夹爪高层语义
- [x] `P0` 已明确前后端需要共享场景基线，而不是完全各写一套

### B. 后端服务骨架

- [x] `P0` 已存在 `backend/` 目录和真实后端代码
- [x] `P0` 已存在 `backend/api_app.py`
- [x] `P0` 已存在 `backend/schemas.py`
- [x] `P0` 已存在 `backend/sim/simulation.py`
- [x] `P0` 已存在 `backend/main.py`
- [x] `P0` 已提供 `GET /health/`
- [x] `P0` 已提供 `GET /sim/state/`
- [x] `P0` 已提供 `POST /sim/step/`
- [x] `P0` 已提供 `POST /sim/reset/`
- [x] `P0` 已提供 `WebSocket /sim/ws`
- [x] `P1` 已保留兼容旧前端逻辑的 `GET /data/`

### C. MuJoCo 场景与模型基线

- [x] `P0` 已存在 `backend/mujoco_models/environment.xml`
- [x] `P0` 已存在 `backend/mujoco_models/ur5.xml`
- [x] `P0` 已存在 `backend/mujoco_models/rack.xml`
- [x] `P0` 已存在 `backend/mujoco_models/toolbox.xml`
- [x] `P0` 已存在 `backend/mujoco_models/wrench.xml`
- [x] `P0` 已存在 `backend/mujoco_models/screwdriver.xml`
- [x] `P0` 已存在 `backend/mujoco_models/pliers.xml`
- [x] `P0` 已存在 `backend/mujoco_models/camera_base.xml`
- [x] `P0` 已存在 `backend/mujoco_models/camera.xml`
- [x] `P0` 已整理 MuJoCo 所需 mesh 目录
- [x] `P0` 已将 UR5 + Robotiq 结构落入 MuJoCo 模型
- [x] `P1` 已保留 `battery_pack.xml` 历史资产用于旧版本回溯

### D. 前后端状态同步基线

- [x] `P0` 前端已具备 WebSocket 管理器 `frontend/src/utils/websocket.js`
- [x] `P0` 前端已支持发送机械臂关节控制命令
- [x] `P0` 前端已支持发送夹爪高层开合命令
- [x] `P0` 前端已支持请求后端状态 `get_state`
- [x] `P0` 前端已支持接收 `state_update` 和 `state_broadcast`
- [x] `P0` 前端已将后端 `qpos` 回放到 UR5 关节显示
- [x] `P0` 前端已将后端夹爪状态回放到 Robotiq 显示
- [x] `P0` 前端已将 `toolbox + wrench_01 + screwdriver_01 + pliers_01` 位姿从后端同步到 Three.js 场景
- [x] `P0` 前端已加入手动发送后的防回弹保护逻辑
- [x] `P1` 前端已加入状态缓冲、连接质量与插值显示

### D2. 工具箱与工具场景校准（2026-04-12）

- [x] `P0` 工具箱尺寸已放大到当前基线（`scale=0.32`）
- [x] `P0` 工具尺寸已放大到当前基线（`scale=0.13`）
- [x] `P0` 工具箱与工具已分区放置，避免互相重叠
- [x] `P0` 工具箱姿态已校准为开口朝上，且长边不带盖侧朝向机械臂
- [x] `P0` 工具箱与工具位姿已在前端与 MuJoCo 侧一一对应

### E. 桌面 viewer 桥接基线

- [x] `P0` `backend/main.py` 已能启动后端并可选打开 MuJoCo viewer
- [x] `P0` 已能从 viewer 拉取本地关节/夹爪编辑结果
- [x] `P0` 已能把 viewer 改动推送回后端 `/sim/step/`
- [x] `P0` 已能从后端 `/sim/state/` 拉取状态覆盖 viewer
- [x] `P1` 已具备 viewer 与后端的基本双向桥接思路，可作为 Quest3 输入桥接参考

### F. 旧任务中仍未真正完成的部分

这部分虽然旧文档里存在目标，但按当前代码复核，仍不能标完成。2026-06-08 任务回归后，其中与人机协作交接相关的项目只保留为历史未完成记录，当前不再作为主链路推进。

- [ ] `P0` 真实任务运行器
- [ ] `P0` 抓取成功判定
- [ ] `P0` 附着与释放机制
- [ ] `P0` 末端 `Intel RealSense D405` 主相机接入
- [ ] `P0` 末端 `RGB-D` 观测导出链路
- [ ] `P0` `RGB-D + 机器人状态 + 工具状态 + 动作 + 任务文本 + 质量标签` 采集协议冻结
- [ ] `P0` LeRobot / OpenPI 数据转换器与 loader smoke test
- [ ] `P0` pi0.5 LoRA 微调模型加载到 MuJoCo 的验证入口
- [ ] `P0` 数据集与模型目录
- [ ] `P1` 末端 `D405` 的调试预览与回放接口
- [ ] `P1` 自动化测试体系

历史暂停项：

- 人机安全交接成功判定（当前暂停）
- `RGB-D + 机器人状态 + 人手状态 + 工具状态 + relation feature + 动作 + 交互阶段标签` 协作采集协议冻结（当前暂停）
- 协作记忆模型训练与验证脚本（当前暂停）
- interaction gating 与交接 release 控制入口（当前暂停）
- Quest3 双边协作输入链路：左手控制机器人，右手控制仿真人手（当前暂停）

---

## 二、当前主链路 ToDo

以下任务在已完成 `quest3_tool_sorting_v1` 工具场景基线上继续推进，当前主目标是 `quest3_vr_lerobot_pi05_v1`：用 Quest3 / VR 采集机器人操作示教数据，将 raw episode 转换为 LeRobot / OpenPI 可读取格式，并用转换后的数据微调 pi0.5，再回到 MuJoCo 中验证抓取、移动、放置和对齐能力。

## 里程碑 S0：文档与基线冻结

### 目标

把当前代码现状和新实验目标统一下来，避免后续开发方向来回切换。

### ToDo

- [x] `P0` 回到主分支并同步远端最新代码
- [x] `P0` 基于最新主分支创建新的文档工作分支
- [x] `P0` 复核当前主分支是否已经有真实后端、MuJoCo 模型和前后端同步
- [x] `P0` 将旧“电池搬运”文档重构为“Quest3 工具抓取实验”文档
- [x] `P0` 在新 ToDo 中明确“已完成基线”和“未完成主链路”的边界
- [x] `P0` 统一新的实验任务名：`quest3_tool_sorting_v1`
- [ ] `P1` 输出一份旧 battery 版本的归档说明，供后续展示或答辩时回溯使用

### 产出

- [x] `P0` 更新后的 `docs/task.md`
- [x] `P0` 更新后的 `docs/todolist.md`

---

## 里程碑 S1：工具场景替换与对象模型重构

### 目标

将当前前后端电池场景替换为“工具 + 工具箱”场景，并建立统一的对象状态模型。

### S1.1 工具资产范围冻结

- [x] `P0` 冻结第一版工具范围为 `wrench + screwdriver + pliers + toolbox`
- [x] `P0` 明确是否保留 `camera` / `camera_base` 作为调试对象
- [x] `P0` 为每个工具定义唯一 ID、类别名和显示名
- [x] `P0` 为每类工具定义前端资产路径
- [x] `P0` 为每类工具定义 MuJoCo mesh / XML 路径
- [ ] `P1` 为每类工具定义抓取提示位姿或抓取推荐区域

### S1.2 共享配置重构

- [x] `P0` 更新 `shared/scene_manifest.json`，从 `battery_pack` 场景切换到 `tools + toolbox`
- [x] `P0` 新增 `shared/tool_catalog.json`
- [x] `P0` 在共享配置中定义工具箱槽位
- [x] `P0` 在共享配置中定义桌面随机投放区域
- [x] `P0` 在共享配置中定义对象质量、尺寸、缩放基线
- [x] `P1` 在共享配置中加入工具类别到目标槽位的映射

### S1.3 前端场景替换

- [x] `P0` 移除前端对 `battery_pack` 单对象逻辑的依赖
- [x] `P0` 新增前端 `toolbox` 模型加载逻辑
- [x] `P0` 新增前端多工具对象加载逻辑
- [x] `P0` 前端支持按对象 ID 更新多工具位姿
- [x] `P0` 旧控制面板中的“电池包”命名统一改为“工具对象”
- [x] `P1` 前端为不同工具类别显示不同图标或标签

### S1.4 后端场景替换

- [x] `P0` 在 `backend/mujoco_models/` 中落地 `toolbox/wrench/screwdriver/pliers` 工具对象模型结构
- [x] `P0` 新增 `toolbox.xml`
- [x] `P0` 将 `environment.xml` 改为加载工具箱和工具对象
- [x] `P0` `SimulationCore` 支持多工具对象状态收集
- [x] `P0` `SimulationCore` 支持 reset 时随机生成工具位置
- [x] `P1` 为不同工具设置合理的质量、摩擦和碰撞参数

### S1.5 场景替换验收

- [x] `P0` 前后端均不再以 `battery_pack` 作为主任务对象
- [x] `P0` 前端能稳定显示 `wrench`、`screwdriver`、`pliers`、`toolbox`
- [x] `P0` 后端能广播多工具对象状态
- [x] `P0` reset 后工具可在桌面随机区域内生成
- [x] `P0` 工具箱在桌面上、开口朝上、与工具保持分离且在机械臂工作范围内

---

## 里程碑 S1.5：末端 D405 RGB-D 相机接入与观测链冻结

### 目标

在开始 Quest3 / VR 示教前，先把真实实验要用的主视觉传感器冻结下来。  
这里的主传感器不是当前场景里的 `camera / camera_base` 调试对象，而是安装在机械臂末端的 `Intel RealSense D405 RGB-D` 相机。

本轮落地参考：`docs/s1_5_d405_freeze.md`、`shared/camera_sensor_config.json`、`shared/dataset_schema.json`。

### S1.5.1 相机资产与安装方式冻结

- [x] `P0` 明确主相机设备为 `Intel RealSense D405`
- [x] `P0` 明确当前场景中的 `camera / camera_base` 仅保留为 `debug_only` 参考对象，不再作为主采集相机
- [x] `P0` 盘点并冻结以下资产的用途：
- [x] `P0` `frontend/public/camera/mesh/d405.stl` 作为相机主体模型
- [x] `P0` `frontend/public/camera/mesh/前半.STL` 作为末端安装结构的一部分
- [x] `P0` `frontend/public/camera/mesh/后半.STL` 作为末端安装结构的另一部分
- [x] `P0` `pic/camera.jpg` 作为真实安装参考图
- [x] `P0` 根据 `pic/camera.jpg` 冻结 D405 在末端的安装方向、朝向工作区的视角和线缆出线方向
- [x] `P0` 冻结 D405 是“夹爪上方附近的固定安装相机”，而不是场景外部俯视相机

### S1.5.2 仿真侧传感器接入定义

- [x] `P0` 在 MuJoCo 中新增末端 D405 挂载定义，而不是只保留场景调试相机
- [x] `P0` 明确 D405 相对 `tool0` 或 `wrist_3_link` 的固定挂载坐标系
- [x] `P0` 明确仿真中 D405 的 `RGB` 输出接口
- [x] `P0` 明确仿真中 D405 的 `Depth` 输出接口
- [x] `P0` 明确 `RGB` 与 `Depth` 的分辨率、帧率和时间戳对齐方式
- [x] `P0` 明确仿真中相机输出是“可录制训练观测”，不是仅供页面展示
- [ ] `P1` 为后续 sim2real 预留深度缺测、噪声和轻微外参偏差随机化入口

### S1.5.3 标定与版本规范

- [x] `P0` 冻结相机内参版本命名规范
- [x] `P0` 冻结相机外参版本命名规范
- [x] `P0` 冻结相机相对末端的安装方案命名，例如 `wrist_d405_v1`
- [x] `P0` 明确 `data/calibration/` 下相机标定文件的组织方式
- [x] `P0` 明确 episode 元数据中必须记录 `camera_device`、`camera_intrinsics_version`、`camera_extrinsics_version`
- [ ] `P0` 按 `docs/d405_real_intrinsics_validation.md` 连接真实 D405，读取实测 `fx/fy/ppx/ppy`，并写回 MuJoCo `focalpixel/principalpixel`
- [ ] `P1` 预留后续真实 D405 与仿真相机的误差分析字段

### S1.5.4 数据录制前置条件

- [x] `P0` 在进入 Quest3 录制前先冻结 `RGB-D + 状态 + 动作 + 文本` 样本结构
- [x] `P0` 明确 `RGB` 图像文件存储格式
- [x] `P0` 明确 `Depth` 图像文件存储格式，禁止使用会破坏深度值的有损格式
- [x] `P0` 明确每一步动作都要关联对应的视觉帧 ID
- [x] `P0` 明确任务文本要进入 episode 元数据和单步训练样本
- [x] `P0` 明确录制器需要检查 `RGB`、`Depth`、状态、动作是否时间对齐
- [ ] `P1` 预留视觉缺帧、深度异常和未对齐样本的剔除标签

### S1.5.5 验收

- [x] `P0` 文档层已明确 D405 才是主视觉传感器
- [x] `P0` 文档层已明确 `camera / camera_base` 只是调试对象
- [x] `P0` 文档层已明确安装参考来自 `pic/camera.jpg`
- [x] `P0` 文档层已明确 `d405.stl + 前半.STL + 后半.STL` 的资产角色
- [x] `P0` 文档层已明确 Quest3 / VR 开发必须在 D405 任务之后推进
- [x] `P0` 文档层已明确数据集必须支持 `RGB-D + 状态 + 动作 + 文本`

---

## 里程碑 S2：Quest3 局域网接入与 VR 模式 UI

### 目标

让 Quest3 通过局域网进入现有前端，并拥有独立但不遮挡主界面的 VR 模式控制入口。  
这一里程碑默认以 `S1.5` 已完成为前提，即末端 D405 及其录制字段已经先冻结。

### S2.1 接入链路

- [x] `P0` 前端开发环境支持 `0.0.0.0` 暴露，允许局域网访问
- [x] `P0` 在前端显示当前宿主机 IP 与访问地址提示
- [x] `P0` 在前端显示后端服务地址与 WebSocket 地址提示
- [x] `P0` 检查 Quest3 与主机处于同一局域网的接入前提
- [x] `P0` 区分桌面端与 Quest3 端访问场景
- [x] `P0` Quest3 端进入页面后能识别“当前可进入 VR 模式”
- [x] `P0` Quest3 端进入页面后检测后端 `health` 和 `WebSocket` 是否可用
- [x] `P0` Quest3 端进入页面后检测末端 `D405` 观测链是否已准备就绪
- [x] `P0` Quest3 端接入失败时给出清晰错误提示

### S2.2 接入后控制启动流程

- [x] `P0` 固定 Quest3 接入后的控制启动顺序：访问页面 -> 检查相机链 -> 连接机器人 -> 点击 `VR模式` -> 选择输入模式 -> 开始控制
- [x] `P0` 前端在进入 `VR模式` 前确认后端已在线
- [x] `P0` 前端在进入 `VR模式` 前确认当前 episode 已绑定 `RGB-D` 录制配置
- [x] `P0` 前端在进入 `VR模式` 后锁定当前输入源
- [x] `P0` Quest3 退出 `VR模式` 后释放控制权
- [x] `P0` Quest3 掉线后自动停止发送新的控制命令

### S2.3 底部入口改造

- [x] `P0` 将底部 `状态同步` 按钮升级或替换为 `VR模式`
- [x] `P0` 保留原状态同步信息，但转移到新的状态区或二级面板
- [x] `P0` `VR模式` 按钮在桌面端和 Quest3 端都可见

### S2.4 模式选择菜单

- [x] `P0` Quest3 端点击 `VR模式` 后显示非全屏菜单
- [x] `P0` 菜单包含 `手柄模式`、`手势模式`、`退出VR模式`
- [x] `P0` 菜单不覆盖现有主界面中心区域
- [x] `P0` 菜单支持关闭和再次打开

### S2.5 状态模型

- [x] `P0` 定义 `vr_disabled / vr_ready / vr_controller_mode / vr_hand_mode / vr_error`
- [x] `P0` 前后端同步当前 VR 模式
- [x] `P0` 同步当前输入源是否可用
- [x] `P0` 同步当前选中关节组
- [x] `P0` 同步当前控制来源 `desktop_manual / quest3_controller / quest3_hand / task / policy`
- [x] `P0` 同步当前录制状态

### S2.6 验收

- [x] `P0` Quest3 可通过局域网稳定访问前端（2026-04-23 已验证）
- [x] `P0` Quest3 端可打开 `VR模式` 菜单
- [x] `P0` 模式菜单不遮挡现有主要界面
- [x] `P0` 桌面端和 Quest3 端对 VR 模式状态显示一致

---

## 里程碑 S3：手柄模式控制落地

### 目标

先把更稳定的手柄模式跑通，为数据采集提供第一条可靠链路。

### ToDo

- [x] `P0` 定义左手柄选组、右手柄控制、右 Trigger 控夹爪的完整输入映射
- [x] `P0` 实现大臂组：`shoulder_pan + shoulder_lift`
- [x] `P0` 实现前臂组：`elbow + wrist_1`
- [x] `P0` 实现腕部组：`wrist_2 + wrist_3`
- [x] `P0` 实现 Quest3 手柄原始输入读取
- [x] `P0` 实现原始输入到标准控制量的归一化
- [x] `P0` 实现标准控制量到关节组命令的映射
- [x] `P0` 当前关节组切换后在 UI 有轻提示
- [x] `P0` 输入增量经过限幅和滤波
- [x] `P0` 夹爪采用连续量控制而不是二值开关
- [x] `P0` 控制消息中记录 `input_source=quest3_controller`
- [x] `P0` 控制消息中记录当前关节组
- [x] `P0` 前端按固定频率持续发送控制消息
- [x] `P0` 后端状态广播回前端后不产生明显回弹
- [x] `P1` 增加灵敏度调节
- [x] `P1` 增加输入死区和回中处理
- [x] `P1` 记录手柄输入原始值到数据集

### 验收

- [x] `P0` Quest3 手柄可稳定切换关节组
- [x] `P0` Quest3 手柄可稳定控制 6 个关节
- [x] `P0` Quest3 手柄可稳定控制夹爪开合
- [x] `P0` 前端显示与后端广播状态一致
- [x] `P0` 手柄模式下的控制记录可直接进入数据集

---

## 里程碑 S4：手势模式控制落地

### 目标

在手柄模式之后，再补齐手势模式，用于比较不同采集方式对训练的影响。

### ToDo

- [x] `P0` 定义双手模式手势映射
- [x] `P0` 定义单手降级模式映射
- [x] `P0` 显示当前输入源 `hand`
- [x] `P0` 显示当前追踪稳定性
- [x] `P0` 实现 Quest3 手部原始输入读取
- [x] `P0` 实现手势输入到关节组命令的映射
- [x] `P0` 控制消息中记录 `input_source=quest3_hand`
- [x] `P0` 为手势输入加入阈值滤波和速度限制
- [x] `P0` 丢失追踪时进入安全状态而不是继续发送旧命令
- [x] `P0` 丢失追踪后暂停录制或写入异常标记
- [ ] `P1` 实现横向微调或位姿微调模式
- [ ] `P1` 记录不同手势模式下的使用日志

### 验收

- [x] `P0` Quest3 手势模式可完成 6 轴关节基本控制
- [x] `P0` Quest3 手势模式可控制夹爪
- [x] `P0` 追踪短暂丢失不会导致危险跳变
- [ ] `P1` 手势模式可用于实际数据采集，而不是只能演示

---

## 里程碑 S4.5：物理边界与前后端虚拟干涉修复

### 目标

本阶段目标是为前后端共享的桌面、工具箱、工具和夹爪场景补齐物理边界，解决前端可视模型与后端 MuJoCo 物理世界不一致时产生的虚拟干涉问题。  
当前该问题已解决：后续正式采集可以在这套物理边界基线上继续接入录制器、回放筛选和抓取附着状态机。

### S4.5.1 问题边界冻结

- [x] `P0` 明确当前问题是“前端虚拟显示边界”和“后端物理仿真边界”不一致造成的穿模、遮挡和控制干涉
- [x] `P0` 将本阶段范围收敛为桌面、工具箱、工具对象、夹爪和 UR5 工作区的物理边界一致性
- [x] `P0` 明确本阶段验收重点是解决明显穿桌、穿箱、穿工具和 reset 初始位姿非法问题
- [x] `P0` 将抓取判定、临时附着、释放校验保留到后续任务闭环阶段，不再混入本阶段完成条件

### S4.5.2 物理边界补齐

- [x] `P0` 后端 MuJoCo 场景已为桌面、工具箱、工具对象和夹爪交互区域补齐可用物理边界
- [x] `P0` 工具对象不再只是前端视觉占位，已经具备与后端状态同步的物理交互基线
- [x] `P0` 工具箱与桌面边界已经用于约束对象初始姿态和交互空间，避免明显穿透
- [x] `P0` UR5 / 夹爪靠近桌面、工具箱和工具时，前后端不再出现明显虚拟干涉
- [x] `P0` 已确保工具 reset 后不会悬空、穿桌、翻立或与工具箱 / 其他工具明显重叠

### S4.5.3 前后端边界一致性

- [x] `P0` 前端 Three.js 可视对象与后端 MuJoCo 对象使用同一对象 ID、位姿和尺寸基线
- [x] `P0` 后端广播的工具、工具箱和机械臂状态能够驱动前端回放，减少“看起来没碰到 / 看起来穿了”的错觉
- [x] `P0` 前端不再单独假设工具或工具箱位置，以后端状态作为最终物理事实来源
- [x] `P0` 手动控制和 Quest3 控制都复用同一物理边界基线，避免不同输入源产生不同干涉表现

### S4.5.4 验收状态

- [x] `P0` Quest3 / 手动控制机械臂靠近桌面时不会明显穿桌
- [x] `P0` Quest3 / 手动控制夹爪靠近工具时不会直接穿过目标工具
- [x] `P0` 工具箱和非目标物体的边界能阻止或显著减少明显虚拟干涉
- [x] `P0` reset 后工具和工具箱姿态符合当前桌面工具抓取场景的物理常识
- [x] `P0` S4.5 已完成，可作为后续数据集采集、回放筛选和半物理抓取附着机制的前置基线

---

## 里程碑 S5：任务重定向与安全交接问题冻结

### 目标

把后续主链路从“工具抓取入箱”升级为“人机协作安全交接时机理解”。已完成的工具、工具箱、UR5、VR 控制和物理边界能力作为基础资产继续复用；新的核心问题是：机器人在递送工具时，如何根据人手行为的历史变化判断当前是否已经形成稳定可信的交接关系。

本轮落地产物：`docs/s5_safe_handover_freeze.md`。

### S5.1 研究问题与任务名称冻结

- [x] `P0` 将新主任务名冻结为 `quest3_safe_handover_v1`
- [x] `P0` 明确主问题不是单纯抓取、避障或碰撞检测，而是“什么时候适合释放工具”
- [x] `P0` 明确系统输出不只是 `ready/not_ready`，还要能识别 `approach/stabilization/hesitation/retreat/ready/release`
- [x] `P0` 明确 `quest3_tool_sorting_v1` 保留为工具场景和机器人操作基线，不再作为最终主任务
- [x] `P0` 明确工具箱在新任务中可作为初始工具收纳/场景资产，不再是最终放置目标
- [x] `P0` 明确第一版交接对象仍使用已建好的 `wrench/screwdriver/pliers`，避免重新处理资产
- [x] `P0` 明确第一版 human hand 是仿真人手，由 Quest3 手势模式控制，不依赖真实人手硬件接入

### S5.2 双层协作架构冻结

- [x] `P0` 冻结总体架构：`pi0.5/VLA manipulation layer + collaboration memory layer + interaction gating`
- [x] `P0` 明确 `pi0.5` 负责“怎么递”：抓取工具、移动到交接区域、对齐人手、保持稳定姿态
- [x] `P0` 明确 `collaboration memory` 负责“什么时候递”：根据关系序列判断是否允许 release
- [x] `P0` 明确 `interaction gating` 是 release 的硬闸门：memory 未判定 `ready` 时禁止释放
- [x] `P0` 明确 `hesitation`、`retreat`、`unstable` 状态下必须保持夹持或进入安全等待
- [x] `P0` 明确 VLA 候选动作和 gating 输出都需要写入日志，便于复盘“模型想释放但被拦截”的样本

### S5.3 交接任务状态机冻结

- [x] `P0` 定义 episode 阶段：`reset -> robot_grasp -> robot_offer -> human_approach -> stabilization/hesitation/retreat -> ready -> release -> result`
- [x] `P0` 定义 `handover_phase` 枚举：`approach/stabilization/hesitation/retreat/ready/release/fail`
- [x] `P0` 定义 `handover_gate` 枚举：`blocked_by_memory/blocked_by_safety/allowed_release/manual_override`
- [x] `P0` 定义 `release_decision` 字段，记录每一帧是否允许释放以及原因
- [x] `P0` 定义交接成功条件：工具从夹爪释放后由人手稳定接住，且短时间内无掉落、无危险接触
- [x] `P0` 定义危险交接条件：提前松手、人在后撤时松手、人手晃动未稳定时松手、工具掉落、夹爪碰撞人手

### S5.4 验收

- [x] `P0` 文档层已经把主任务切换为 `quest3_safe_handover_v1`
- [x] `P0` 所有后续未开始任务都围绕安全交接时机理解展开
- [x] `P0` 已明确现有工具场景、VR 控制、D405 和物理边界如何服务新任务后
- [x] `P0` 已明确 VLA 和协作记忆模型的职责边界

---

## 里程碑 S5.5：2026-06-08 任务回归冻结

### 目标

保留 S5 已完成的安全交接文档冻结记录，但当前开发主线回归为：`VR 采集机器人操作示教数据 -> 转换 LeRobot / OpenPI 数据格式 -> 微调 pi0.5 -> MuJoCo 验证`。后续未完成任务不再围绕 human hand、collaboration memory 或 interaction gating 展开。

### S5.5.1 当前任务名与范围冻结

- [x] `P0` 当前主任务名回归为 `quest3_vr_lerobot_pi05_v1`
- [x] `P0` 明确 `quest3_tool_sorting_v1` 继续作为工具场景、机器人操作和抓取资产基线
- [x] `P0` 明确当前 P0 不新增 `human_hand`
- [x] `P0` 明确当前 P0 不训练 collaboration memory
- [x] `P0` 明确当前 P0 不集成 interaction gating
- [x] `P0` 明确当前 P0 不以 release timing / unsafe handover 作为评估指标
- [x] `P0` 明确当前训练主线只服务 pi0.5 操作能力微调

### S5.5.2 新数据闭环冻结

- [x] `P0` 冻结新闭环：`Quest3 VR 示教 -> raw episode -> validation -> LeRobot/OpenPI conversion -> loader smoke test -> pi0.5 LoRA -> MuJoCo rollout`
- [x] `P0` 明确 raw JSONL 不能直接用于 pi0.5 训练，必须先转换为 LeRobot / OpenPI 可读取数据集
- [x] `P0` 明确训练主视觉仍为末端 D405 RGB，Depth 第一版作为 sidecar 或评估/回放字段
- [x] `P0` 明确训练动作空间第一版使用 `joint_delta[0:6] + gripper_target`
- [x] `P0` 明确 train/val/test 必须按 episode 划分，禁止按帧随机打散
- [x] `P0` 明确 5090D 32GB 服务器第一版只做 LoRA / adapter，不做全参数微调

### S5.5.3 验收

- [x] `P0` `docs/task.md` 已回归到 VR 数据采集、LeRobot 转换和 pi0.5 微调任务
- [x] `P0` `docs/todolist.md` 保留已完成 todo，并把后续未完成任务转向当前主链路

---

## 里程碑 S6：末端 D405 摄像头模块与 MuJoCo 观测验证

### 目标

训练主视觉观测必须来自机械臂末端 D405，而不是 Quest3 页面画面、Three.js 外部观察相机或调试相机。本阶段第一轮先验证夹爪、目标工具、目标放置区域和工具箱是否在末端相机视野内。

本轮落地产物：后端 D405 观测状态字段、`/sim/observation/` RGB-D 验证、前端 `D405ObservationPanel`、数据录制所需相机字段。

### S6.1 视觉来源边界冻结

- [x] `P0` 明确 `d405_rgb / d405_depth` 是当前 pi0.5 数据集的训练主视觉来源
- [x] `P0` 明确 Quest3 页面画面、Three.js 观察相机、`camera / camera_base` 只能用于调试和展示
- [x] `P0` 在 episode metadata 中记录 `camera_device=intel_realsense_d405`
- [x] `P0` 在 episode metadata 中记录 `camera_mount_name`、`camera_intrinsics_version`、`camera_extrinsics_version`
- [x] `P0` 在 `validation_summary.json` 中增加 `camera_source_ok`，确认没有使用非 D405 图像

### S6.2 MuJoCo D405 挂载与第一轮渲染验证

- [x] `P0` 确认 D405 在 MuJoCo 中固定挂载到 UR5 末端或腕部坐标系，并随机械臂运动
- [x] `P0` 确认 `d405_rgb` 渲染视角与真实末端相机方向一致，朝向夹爪、工具和目标操作区域
- [x] `P0` 确认 `d405_depth` 与 RGB 同视角、同时间戳或可对齐时间戳
- [ ] `P0` 确认 MuJoCo D405 内参来自真实 D405 实测值，而不是只用图像中心光轴占位
- [ ] `P0` 确认 D405 在 `robot_grasp` 阶段能看到夹爪和目标工具
- [ ] `P0` 确认 D405 在 `robot_place` 阶段能看到工具和目标放置区域
- [x] `P0` 使用目标区域标记或占位体检查未来工具放置区域是否在视野内
- [ ] `P0` 记录不同抓取、移动和放置姿态下的遮挡情况，优先找出能同时看到夹爪、工具和目标区域的姿态

### S6.3 RGB-D 接口与落盘

- [x] `P0` 验证 `GET /sim/observation/` 返回 D405 观测摘要
- [x] `P0` 验证 `GET /sim/camera/rgb/` 返回有效 D405 RGB 图像
- [x] `P0` 验证 `GET /sim/camera/depth/` 返回有效 D405 Depth 图像
- [x] `P0` WebSocket 状态广播包含最近一帧 `d405_frame_id`、时间戳、有效性和错误原因
- [ ] `P0` 录制器写入 `visuals.jsonl`，包含 RGB 路径、Depth 路径、时间戳、相机位姿和有效性
- [x] `P0` Depth 使用无损格式保存，禁止把 JPG 或普通 MP4 帧作为训练主深度数据
- [x] `P0` MP4 预览仅用于人工检查，不作为训练主数据

### S6.4 前端 D405 观测面板

- [x] `P0` 前端新增或复用 D405 观测面板，显示当前 RGB 画面
- [x] `P0` 前端显示 Depth 原图或伪彩深度图
- [x] `P0` 前端显示帧号、时间戳、帧率和最近错误
- [x] `P0` 前端显示 `camera_capture_ok`、`rgb_valid`、`depth_valid`、`frame_aligned`
- [x] `P0` 前端明确标记当前视觉源是 D405，而不是 Quest3 页面画面或外部观察相机
- [ ] `P1` 在观测面板中叠加目标区域或关键区域提示，辅助采集前检查

### S6.5 摄像头阶段验收

- [ ] `P0` 第一轮 camera-only smoke test 中，D405 能稳定看到夹爪、目标工具和目标放置区域
- [x] `P0` D405 Depth 不出现全零、全 NaN、严重错位或明显尺度错误
- [x] `P0` `validation_summary.json` 能报告 `camera_capture_ok`、`camera_view_ok`、`frame_alignment_ok`
- [ ] `P0` 未通过 D405 观测验证前，不允许进入批量训练数据采集
- [ ] `P0` 若 D405 看不到操作关键区域，优先调整目标区、机器人姿态或相机挂载角度

---

## 里程碑 S7：VR 采集入口与任务模板

### 目标

在 Quest3 / VR 中建立面向 pi0.5 数据采集的单边机器人操作入口，让操作者能在头显内完成 precheck、选择任务模板、开始/停止录制和结果标记。

### S7.1 任务模板与采集入口

- [ ] `P0` 新增或更新 Quest3 `VR采集模式`，面向 `quest3_vr_lerobot_pi05_v1`
- [ ] `P0` VR 采集模式显示 D405 状态、WebSocket 状态、控制模式、`recording_ready` 和最近错误
- [ ] `P0` VR 采集模式提供任务模板：`tool_grasp/tool_pick_place/tool_reposition/debug_trial`
- [ ] `P0` VR 采集模式可选择目标工具：`wrench_01/screwdriver_01/pliers_01`
- [ ] `P0` VR 采集模式可选择 `target_zone_id` 或工具箱槽位
- [ ] `P0` VR 采集模式可写入稳定任务文本，例如 `pick up the wrench`、`place the screwdriver in the toolbox`
- [ ] `P0` VR 内必须能一键或少步骤开始/停止 episode，避免操作者摘下头显回桌面端操作

### S7.2 precheck 与元数据

- [ ] `P0` 实现 `/dataset/precheck/` 或等效检查，覆盖 WebSocket、D405、MuJoCo、UR5、工具状态和录制目录
- [ ] `P0` 只有 `recording_ready=true` 时允许进入正式录制；否则只能进入 `debug_trial`
- [ ] `P0` 每条正式 episode 写入 `operator_controlled=true`
- [ ] `P0` 每条正式 episode 写入 `control_mode=vr_controller/vr_hand`
- [ ] `P0` 每条正式 episode 写入 `robot_input_source=quest3_controller/quest3_hand`
- [ ] `P0` 每条正式 episode 写入 `autonomy_level=manual_demonstration`
- [ ] `P0` 每条正式 episode 写入 `scripted_collection=false`

### 验收

- [ ] `P0` 操作者可以不摘下 Quest3，在 VR 采集模式内完成一条 `debug_trial` 的开始、停止和结果标记
- [ ] `P0` 每条 episode 都能追溯任务模板、目标工具、目标区域、控制源和开始/停止事件
- [ ] `P0` 脚本生成的测试轨迹不会被标记为正式训练候选

---

## 里程碑 S8：raw episode 录制器与数据质量校验

### 目标

建立 raw episode 录制器。当前数据只记录机器人操作示教，不记录 human hand、relation feature、phase label 或 release gate。

### S8.1 数据目录与 episode 分级

- [ ] `P0` 创建 `data/datasets/quest3_vr_lerobot_pi05_v1/`
- [ ] `P0` 定义 episode 类型：`tool_grasp/tool_pick_place/tool_reposition/failed_attempt/operator_abort`
- [ ] `P0` 定义采集等级：`debug_trial/pilot/train_candidate/eval_candidate/rejected`
- [ ] `P0` 每条 episode 记录 `task_type`、`target_tool_id`、`target_tool_class`、`target_zone_id`
- [ ] `P0` 每条 episode 记录 `instruction_text`、`reset_seed`、相机标定版本和场景配置版本
- [ ] `P0` episode 结束后生成 `result.json` 和 `validation_summary.json`

### S8.2 原始数据字段

- [ ] `P0` 记录机器人状态：`qpos/qvel/ee_pose/gripper_opening/grasp_state/attached_tool_id`
- [ ] `P0` 记录工具状态：`tool_pose/tool_velocity/tool_attached/tool_dropped/tool_in_target_zone`
- [ ] `P0` 记录视觉信息：`d405_rgb/d405_depth/frame_id/timestamp/frame_aligned`
- [ ] `P0` 记录动作信息：`joint_target/joint_delta/gripper_target/source/control_mode/raw_input`
- [ ] `P0` 记录质量事件：`camera_error/tracking_warning/workspace_limit_hit/collision_warning/operator_abort`
- [ ] `P0` 写入 `metadata.json/visuals.jsonl/states.jsonl/actions.jsonl/events.jsonl/result.json/validation_summary.json`

### S8.3 自动验证与人工筛选

- [ ] `P0` 自动验证 raw 文件是否齐全
- [ ] `P0` 自动验证 RGB 和 Depth 均来自 D405，且 `stub_frame_used=false`
- [ ] `P0` 自动验证 D405 视野中能看到工具、夹爪和目标区域关键帧
- [ ] `P0` 自动验证 RGB、Depth、状态和动作时间戳对齐误差低于阈值
- [ ] `P0` 自动验证机器人状态连续有效，`qpos/qvel/ee_pose/gripper` 无明显缺失
- [ ] `P0` 自动验证动作维度固定、无 NaN、控制源清晰
- [ ] `P0` 自动验证正式训练候选来自 VR 人工示教，而不是脚本自动采集
- [ ] `P0` 人工回放 RGB-D，确认工具、夹爪和目标区域可见
- [ ] `P0` 人工回放 3D 状态和 action timeline，确认任务类型、动作和结果标签一致
- [ ] `P0` 根据验证结果把 episode 标记为 `train_candidate/eval_candidate/debug_trial/rejected`

### S8.4 pilot 验证门槛

- [ ] `P0` 每种工具至少完成 3 条 `tool_grasp` pilot
- [ ] `P0` 每种工具至少完成 3 条 `tool_pick_place` 或 `tool_reposition` pilot
- [ ] `P0` 所有 pilot episode 都能生成完整 raw 文件和 `validation_summary.json`
- [ ] `P0` 至少 80% pilot episode 通过 `camera_capture_ok`、`frame_alignment_ok` 和 `camera_view_ok`
- [ ] `P0` 人工回放确认 pilot 的动作、任务文本和结果标签基本一致
- [ ] `P0` 未通过 pilot 验证前，不进入批量训练数据采集

### 验收

- [ ] `P0` 一条 episode 能完整回放 D405 RGB-D、机器人状态、工具状态和动作序列
- [ ] `P0` `validation_summary.json` 能区分 `train_candidate/eval_candidate/debug_trial/rejected`
- [ ] `P0` 已形成可照着执行的数据采集操作手册和验证清单

---

## 里程碑 S9：LeRobot / OpenPI 数据转换

### 目标

把通过校验的 raw episode 转换成 LeRobot / OpenPI 可读取的数据集。raw JSONL 不能直接用于 pi0.5 训练。

### S9.1 转换脚本与字段映射

- [ ] `P0` 新增 `scripts/datasets/convert_vr_to_lerobot.py`
- [ ] `P0` 新增 `scripts/datasets/validate_lerobot_dataset.py`
- [ ] `P0` 新增 `configs/pi05/quest3_vr_tools_lora.yaml`
- [ ] `P0` 转换器只读取 `train_candidate` 和明确允许的 `eval_candidate`
- [ ] `P0` 转换器跳过 `debug_trial/rejected`
- [ ] `P0` 输出 `observation.images.d405_rgb`
- [ ] `P0` 输出 `observation.state=[qpos[0:6], gripper_opening]`
- [ ] `P0` 输出 `action=[joint_delta[0:6], gripper_target]`
- [ ] `P0` 输出 `task/prompt`
- [ ] `P0` Depth 第一版作为 sidecar 或回放/评估字段保留，不强制进入 pi0.5 主输入

### S9.2 转换报告与 split

- [ ] `P0` 生成连续 `episode_index/frame_index/timestamp`
- [ ] `P0` 生成 `feature_mapping.json`
- [ ] `P0` 生成 `conversion_report.json`
- [ ] `P0` 生成 `rejected_episodes.jsonl`
- [ ] `P0` 生成 action/state normalization 统计
- [ ] `P0` 按 episode 划分 train/val/test，禁止按帧随机打散
- [ ] `P0` 记录相机标定版本、数据采集版本和转换脚本版本

### S9.3 loader smoke test

- [ ] `P0` 用 LeRobot / OpenPI loader 随机读取一个 episode
- [ ] `P0` 检查 RGB 能正常解码
- [ ] `P0` 检查 `observation.state` 维度固定
- [ ] `P0` 检查 `action` 维度固定且无 NaN
- [ ] `P0` 检查 prompt 与目标工具和任务类型一致
- [ ] `P0` 检查 timestamp 单调递增
- [ ] `P0` 检查 train/val/test 没有同一 episode 泄漏
- [ ] `P0` 检查 normalization 统计没有被 rejected episode 污染

### 验收

- [ ] `P0` pilot 数据可转换为 LeRobot / OpenPI 可训练格式
- [ ] `P0` 转换后的数据能通过 loader smoke test
- [ ] `P0` 转换报告能说明接收、跳过和拒绝的 episode 数量及原因

---

## 里程碑 S10：pi0.5 LoRA / adapter 微调

### 目标

让 `pi0.5` 基于 VR 示教数据学习工具抓取、移动、放置和重定位能力。当前不训练人机交接 release 时机，不集成 collaboration memory 或 interaction gating。

### S10.1 训练配置

- [ ] `P0` 训练输入必须来自通过 loader smoke test 的 LeRobot / OpenPI 数据集
- [ ] `P0` 第一版优先 LoRA 或 adapter，冻结大部分 backbone，不做全参数微调
- [ ] `P0` 第一版 pi0.5 训练放到 5090D 32GB 服务器执行
- [ ] `P0` 训练配置支持 batch size `1-2`
- [ ] `P0` 训练配置支持 gradient accumulation
- [ ] `P0` 训练配置支持半精度和 gradient checkpointing
- [ ] `P0` 训练配置支持降低 D405 RGB 分辨率或缓存视觉特征
- [ ] `P0` 训练配置记录数据集版本、相机版本、动作定义和任务文本模板

### S10.2 训练输出与离线指标

- [ ] `P0` 模型输出写入 `models/pi05/quest3_vr_lora_runs/<run_id>/`
- [ ] `P0` run 目录包含 `config.json/dataset_snapshot.json/feature_mapping.json`
- [ ] `P0` run 目录包含 `checkpoints/exported/offline_eval/mujoco_validation`
- [ ] `P0` 离线评估输出 `action_mse`
- [ ] `P0` 离线评估输出 `joint_delta_mse`
- [ ] `P0` 离线评估输出 `gripper_mae`
- [ ] `P0` 记录 train/val loss、checkpoint step、数据集版本和 normalization 版本

### 验收

- [ ] `P0` pi0.5 LoRA run 可复现并入库
- [ ] `P0` 训练配置可在 5090D 32GB 显存边界内启动
- [ ] `P0` 训练输出能追溯到 LeRobot 数据集版本和 raw episode 来源

---

## 里程碑 S11：MuJoCo rollout 验证与动作后处理

### 目标

把 pi0.5 checkpoint 加载回当前 MuJoCo 场景，验证基础工具操作能力，并用动作后处理保护仿真执行。

### S11.1 runtime 与动作安全约束

- [ ] `P0` 新增或复用 `backend/policies/pi05_policy_runtime.py`
- [ ] `P0` 新增或复用 `backend/policies/action_postprocess.py`
- [ ] `P0` 关节目标或增量必须经过 UR5 关节限位裁剪
- [ ] `P0` 单步 `joint_delta` 必须限幅，避免模型输出造成跳变
- [ ] `P0` 夹爪目标必须限制在合法开合范围
- [ ] `P0` 当 WebSocket、D405 或仿真状态异常时，策略进入 `safe_hold`
- [ ] `P0` 当动作包含 NaN、Inf、维度错误或时间戳过旧时，直接丢弃该动作

### S11.2 MuJoCo 评估脚本

- [ ] `P0` 新增 `scripts/training/evaluate_pi05_mujoco.py`
- [ ] `P0` 验证固定工具初始位姿下的 `tool_grasp`
- [ ] `P0` 验证固定目标区下的 `tool_pick_place`
- [ ] `P0` 验证 `tool_reposition`
- [ ] `P0` 验证不同工具类别下动作维度、夹爪控制和状态归一化一致
- [ ] `P0` rollout 中无明显关节越界、剧烈抖动、穿桌或持续碰撞

### S11.3 rollout 指标

- [ ] `P0` 输出 `task_success_rate`
- [ ] `P0` 输出 `grasp_success_rate`
- [ ] `P0` 输出 `placement_error`
- [ ] `P0` 输出 `tool_drop_rate`
- [ ] `P0` 输出 `collision_rate`
- [ ] `P0` 输出 `joint_limit_violation_count`
- [ ] `P0` 输出 `robot_motion_jitter`
- [ ] `P0` 输出 `mean_episode_duration_s`

### 验收

- [ ] `P0` pi0.5 能在 MuJoCo 中完成基础工具抓取 rollout
- [ ] `P0` pi0.5 能在 MuJoCo 中完成基础工具放置或重定位 rollout
- [ ] `P0` 所有评估结果能追溯到数据集版本、模型版本和配置版本

---

## 里程碑 S12：数字孪生映射与真实机械臂验证准备

### 目标

在仿真中验证稳定后，把实时状态映射到真实 UR5 的接口约束先冻结。第一版可以只做 shadow mode 或低速 smoke test，不要求马上让真实机械臂执行完整策略。

### S12.1 sim2real 接口

- [ ] `P0` 定义统一 `runtime_target=sim/real_ur5/shadow_real_ur5`
- [ ] `P0` 统一仿真和实机的高层动作：`joint_target/joint_delta/gripper_target`
- [ ] `P0` 统一观测字段：机器人关节、夹爪、D405 RGB-D、任务文本和必要状态
- [ ] `P0` 模型注册表记录 LeRobot 数据集版本、pi0.5 checkpoint、相机标定和动作空间定义
- [ ] `P0` 明确实机执行必须保留限速、急停、watchdog、掉线保护和人工确认开关

### S12.2 安全与日志

- [ ] `P0` 规划实机限速、急停、掉线保护和 watchdog
- [ ] `P0` 规划 `safe_hold`：停止发送新动作，保持安全姿态或进入人工接管
- [ ] `P0` 规划实机 shadow mode：策略只输出建议动作，不驱动真实硬件
- [ ] `P0` 记录仿真状态到实机状态映射误差
- [ ] `P0` 记录实机验证时的建议动作、后处理结果和人工接管事件

### S12.3 结果固化与复现实验

- [ ] `P0` 冻结 raw 数据集版本、LeRobot 数据集版本和 split
- [ ] `P0` 冻结 pi0.5 LoRA 版本和动作后处理配置版本
- [ ] `P0` 输出失败案例清单：抓取失败、掉落、穿桌、动作抖动、相机不可见、状态映射异常
- [ ] `P0` 输出关键回放材料到 `experiments/pi05_vr_tools/`
- [ ] `P1` 整理 sim2real shadow mode 结果和真实机械臂低速验证记录

### 验收

- [ ] `P0` 仿真端 VR 数据采集 -> LeRobot 转换 -> pi0.5 微调 -> MuJoCo 验证闭环可复现
- [ ] `P0` 真实机械臂接口字段和安全约束已冻结
- [ ] `P0` 所有结果都能追溯到 raw 数据、LeRobot 数据、模型和配置版本

---

## 历史暂停：原 S7-S12 协作任务（当前不执行）

以下原 S7-S12 内容来自 `quest3_safe_handover_v1` 安全交接规划，当前仅作为历史未完成记录保留。当前主线不继续推进 human hand、双边协作、relation feature、collaboration memory 或 interaction gating。

暂停范围摘要：

- 原 S7：仿真人手与双边 VR 协作控制。
- 原 S8：交互数据集、relation feature 与 phase 标签。
- 原 S9：collaboration memory 训练、评估和在线推理。
- 原 S10：面向 handover manipulation 的 pi0.5 LoRA。
- 原 S11：interaction gating、安全交接验证、baseline 和消融。
- 原 S12：围绕 release gate 的实机 shadow mode 与安全交接约束。

---

## 三、按开发先后顺序的周计划版本

这部分不是替代上面的详细里程碑，而是把当前任务按更容易执行的时间顺序重新展开。如果实际开发节奏更快或更慢，可以把“一周”理解为“一个阶段块”。

### 第 1 周：任务回归与 D405 验证周

目标：

- 把当前主线冻结为 `quest3_vr_lerobot_pi05_v1`
- 确认末端 D405 作为 pi0.5 数据集主视觉源
- 验证夹爪、目标工具和目标区域在 D405 视野内

本周建议完成：

- [x] `P0` 冻结任务回归：VR 采集 -> LeRobot / OpenPI 转换 -> pi0.5 微调 -> MuJoCo 验证
- [x] `P0` 保留已完成工具场景、VR 控制、D405 和物理边界基线
- [ ] `P0` 确认 MuJoCo D405 内参来自真实 D405 实测值
- [ ] `P0` 验证 `robot_grasp / robot_place` 阶段的 D405 画面
- [ ] `P0` 录制器能把 RGB、Depth 和 `visuals.jsonl` 一起落盘
- [ ] `P0` camera-only smoke test 中 D405 能稳定看到夹爪、目标工具和目标区域

周验收：

- [ ] `P0` 未通过 D405 观测验证前，不进入批量训练数据采集
- [ ] `P0` D405 观测质量能写入 `validation_summary.json`

### 第 2 周：VR 采集入口与 raw recorder 周

目标：

- 在 Quest3 中完成任务模板、precheck、开始/停止录制和结果标记
- 建立 raw episode 录制器

本周建议完成：

- [ ] `P0` 新增或更新 Quest3 `VR采集模式`
- [ ] `P0` VR 采集模式支持 `tool_grasp/tool_pick_place/tool_reposition/debug_trial`
- [ ] `P0` 实现 `/dataset/precheck/` 或等效检查
- [ ] `P0` 创建 `data/datasets/quest3_vr_lerobot_pi05_v1/`
- [ ] `P0` 录制 `metadata/visuals/states/actions/events/result/validation_summary`
- [ ] `P0` 每条正式 episode 写入 `operator_controlled=true` 和 `scripted_collection=false`

周验收：

- [ ] `P0` 操作者可以不摘下 Quest3 完成一条 `debug_trial`
- [ ] `P0` 一条 episode 能完整回放 D405、机器人状态、工具状态和动作序列

### 第 3 周：pilot 数据与质量筛选周

目标：

- 采集最小 pilot 数据
- 建立自动验证和人工筛选流程

本周建议完成：

- [ ] `P0` 每种工具至少完成 3 条 `tool_grasp` pilot
- [ ] `P0` 每种工具至少完成 3 条 `tool_pick_place` 或 `tool_reposition` pilot
- [ ] `P0` 自动验证文件完整性、D405 来源、时间戳对齐、机器人状态和动作有效性
- [ ] `P0` 人工回放 RGB-D、3D 状态和 action timeline
- [ ] `P0` 根据验证结果标记 `train_candidate/eval_candidate/debug_trial/rejected`

周验收：

- [ ] `P0` 至少 80% pilot 通过 `camera_capture_ok/frame_alignment_ok/camera_view_ok`
- [ ] `P0` 未通过 pilot 验证前，不进入批量训练数据采集

### 第 4 周：LeRobot / OpenPI 转换周

目标：

- 把 raw episode 转换为 LeRobot / OpenPI 可读取数据集
- 跑通 loader smoke test

本周建议完成：

- [ ] `P0` 完成 `scripts/datasets/convert_vr_to_lerobot.py`
- [ ] `P0` 完成 `scripts/datasets/validate_lerobot_dataset.py`
- [ ] `P0` 输出 `observation.images.d405_rgb`
- [ ] `P0` 输出 `observation.state=[qpos[0:6], gripper_opening]`
- [ ] `P0` 输出 `action=[joint_delta[0:6], gripper_target]`
- [ ] `P0` 输出 `task/prompt`
- [ ] `P0` 生成 `feature_mapping.json/conversion_report.json/rejected_episodes.jsonl`
- [ ] `P0` 按 episode 划分 train/val/test

周验收：

- [ ] `P0` 转换后的数据能通过 loader smoke test
- [ ] `P0` train/val/test 没有同一 episode 泄漏

### 第 5 周：pi0.5 LoRA 微调周

目标：

- 在 5090D 32GB 服务器上启动 pi0.5 LoRA / adapter 训练
- 训练 run 可复现并入库

本周建议完成：

- [ ] `P0` 完成 `configs/pi05/quest3_vr_tools_lora.yaml`
- [ ] `P0` 训练输入只使用通过 loader smoke test 的 LeRobot / OpenPI 数据集
- [ ] `P0` 使用 LoRA / adapter，不做全参数微调
- [ ] `P0` 使用 batch size `1-2`、gradient accumulation、半精度和 gradient checkpointing
- [ ] `P0` 模型输出到 `models/pi05/quest3_vr_lora_runs/<run_id>/`
- [ ] `P0` 离线评估输出 action MSE、joint delta MSE 和 gripper MAE

周验收：

- [ ] `P0` pi0.5 LoRA run 可复现并能追溯到数据集、相机和动作空间版本

### 第 6 周：MuJoCo rollout 验证周

目标：

- 将 pi0.5 checkpoint 加载回 MuJoCo
- 验证工具抓取、放置和重定位 rollout

本周建议完成：

- [ ] `P0` 完成 `scripts/training/evaluate_pi05_mujoco.py`
- [ ] `P0` 完成 `backend/policies/pi05_policy_runtime.py` 或等效 runtime
- [ ] `P0` 完成动作后处理：关节限位、增量限幅、夹爪限幅、NaN 丢弃、异常 safe hold
- [ ] `P0` 验证固定工具初始位姿下的 `tool_grasp`
- [ ] `P0` 验证固定目标区下的 `tool_pick_place/tool_reposition`
- [ ] `P0` 输出 task success、grasp success、placement error、drop rate、collision rate 和 motion jitter

周验收：

- [ ] `P0` pi0.5 能在 MuJoCo 中完成基础工具抓取 rollout
- [ ] `P0` pi0.5 能在 MuJoCo 中完成基础放置或重定位 rollout

### 第 7 周：版本固化与 shadow mode 准备周

目标：

- 固化数据集、模型、配置和失败案例
- 冻结真实 UR5 shadow mode 接口

本周建议完成：

- [ ] `P0` 冻结 raw 数据集版本、LeRobot 数据集版本和 split
- [ ] `P0` 冻结 pi0.5 LoRA 版本和动作后处理配置
- [ ] `P0` 输出失败案例清单：抓取失败、掉落、穿桌、动作抖动、相机不可见、状态映射异常
- [ ] `P0` 冻结 `runtime_target=sim/real_ur5/shadow_real_ur5`
- [ ] `P0` 冻结实机观测字段和高层动作字段

周验收：

- [ ] `P0` 仿真端 VR 数据采集 -> LeRobot 转换 -> pi0.5 微调 -> MuJoCo 验证闭环可复现
- [ ] `P0` 真实机械臂接口字段和安全约束已冻结

---

## 四、当前最优先的主链路任务

为了避免任务过散，下一轮实际开发优先盯住这组任务：

- [x] `P0` 前后端把 `battery_pack` 逻辑替换为 `tools + toolbox`
- [x] `P0` 实现多工具对象状态同步
- [x] `P0` 建立物理边界基线，解决前后端虚拟干涉并阻止明显穿桌、穿箱、穿工具
- [x] `P0` 完成 reset 合法性检查，确保工具平躺、工具箱开口朝上且对象不穿透
- [x] `P0` 回归当前任务：`quest3_vr_lerobot_pi05_v1`
- [ ] `P0` 固定 `d405_rgb / d405_depth` 为 pi0.5 数据集主视觉来源，并禁止使用 Quest3 页面画面或 Three.js 外部相机替代
- [ ] `P0` 完成末端 D405 在 MuJoCo 中的第一轮观测验证，确认工具、夹爪和目标区域可见
- [ ] `P0` 新增或更新 VR 采集入口，支持任务模板、precheck、开始/停止录制和结果标记
- [ ] `P0` 建立 raw episode 录制器
- [ ] `P0` 固定单条 episode 的采集操作流程：precheck、选择任务、开始录制、执行操作、停止、校验、标记去向
- [ ] `P0` 采集 `tool_grasp/tool_pick_place/tool_reposition` pilot 数据
- [ ] `P0` 建立自动验证和人工回放筛选流程
- [ ] `P0` 完成 LeRobot / OpenPI 数据转换器和 loader smoke test
- [ ] `P0` 按 episode 划分 train/val/test，禁止按帧随机打散
- [ ] `P0` 在 5090D 32GB 服务器上完成 pi0.5 LoRA / adapter 微调
- [ ] `P0` 在 MuJoCo 中验证 pi0.5 工具抓取、放置和重定位 rollout
- [ ] `P0` 冻结 sim2real shadow mode 接口和基础动作安全约束

---

## 五、补充提醒

- 当前最有价值的既有资产，是已经能实时映射的 UR5、工具、工具箱、VR 控制、D405 规划和 S4.5 物理边界基线。
- 当前最不建议的路线，是在数据闭环没跑通前恢复 human hand、collaboration memory 或 interaction gating。
- 当前路线的核心顺序是“末端 D405 MuJoCo 观测验证 -> VR 采集入口 -> raw episode 录制 -> pilot 数据筛选 -> LeRobot / OpenPI 转换 -> loader smoke test -> pi0.5 LoRA -> MuJoCo rollout -> shadow mode”。
- 正式采集的底线，是每条 episode 必须同时有机器人状态、工具状态、D405 视觉帧、动作、任务文本、metadata 和 validation summary。
- 正式训练候选必须来自操作者在 Quest3 中的人工示教，程序脚本只能用于相机、接口、固定姿态、回放验证和数据管线测试。
- raw JSONL 不能直接训练 pi0.5，必须先转换为 LeRobot / OpenPI 可读取数据集，并保留字段映射、转换报告和 rejected episode 列表。
- 5090D 32GB 服务器第一版只做 LoRA / adapter，不做全参数微调。
- human hand、collaboration memory、interaction gating 和安全交接评估已作为历史暂停任务保留，当前不执行。
