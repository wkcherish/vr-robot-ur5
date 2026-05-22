# Quest3 人机协作安全交接实验 ToDo（2026-05-21 修订）

基于 [task.md](task.md) 重新整理。  
本清单以 `2026-04-12` 主分支真实代码状态为基准，分成两部分：

1. 当前已经完成的基线总结
2. 围绕 Quest3 人机协作安全交接实验的新主链路任务

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

这部分虽然旧文档里存在目标，但按当前代码复核，仍不能标完成：

- [ ] `P0` 真实任务运行器
- [ ] `P0` 抓取成功判定
- [ ] `P0` 附着与释放机制
- [ ] `P0` 人机安全交接成功判定
- [ ] `P0` 末端 `Intel RealSense D405` 主相机接入
- [ ] `P0` 末端 `RGB-D` 观测导出链路
- [ ] `P0` `RGB-D + 机器人状态 + 人手状态 + 工具状态 + relation feature + 动作 + 交互阶段标签` 采集协议冻结
- [ ] `P0` 协作记忆模型训练与验证脚本
- [ ] `P0` pi0.5 LoRA 微调模型加载到 MuJoCo 的验证入口
- [ ] `P0` interaction gating 与交接 release 控制入口
- [ ] `P0` Quest3 双边协作输入链路：左手控制机器人，右手控制仿真人手
- [ ] `P0` 数据集与模型目录
- [ ] `P1` 末端 `D405` 的调试预览与回放接口
- [ ] `P1` 自动化测试体系

---

## 二、新实验主链路 ToDo

以下任务在已完成 `quest3_tool_sorting_v1` 工具场景基线上继续推进，新的主目标是 `quest3_safe_handover_v1`：机器人不仅要会抓取和递送工具，还要理解人与机器人之间是否已经形成稳定可信的协作关系，并据此决定是否允许释放工具。

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

## 里程碑 S6：末端 D405 摄像头模块与 MuJoCo 观测验证

### 目标

协作数据的主视觉观测必须来自机械臂末端 D405，而不是 Quest3 页面画面、Three.js 外部观察相机或调试相机。本阶段可以先于 human hand 开发启动：第一轮先验证夹爪、工具和 handover zone 是否在末端相机视野内；等 S7 的 human hand 接入后，再复测人手进入、犹豫、后撤和 release 前后的可见性。

本轮落地产物：后端 D405 观测状态字段、`/sim/observation/` RGB-D 验证、前端 `D405ObservationPanel`、`shared/handover_scene_config.json`。

### S6.1 视觉来源边界冻结

- [x] `P0` 明确 `d405_rgb / d405_depth` 是 `quest3_safe_handover_v1` 的唯一训练主视觉来源
- [x] `P0` 明确 Quest3 页面画面、Three.js 观察相机、`camera / camera_base` 只能用于调试和展示
- [x] `P0` 在 episode metadata 中记录 `camera_device=intel_realsense_d405`
- [x] `P0` 在 episode metadata 中记录 `camera_mount_name`、`camera_intrinsics_version`、`camera_extrinsics_version`
- [x] `P0` 在 `validation_summary.json` 中增加 `camera_source_ok`，确认没有使用非 D405 图像

### S6.2 MuJoCo D405 挂载与第一轮渲染验证

- [x] `P0` 确认 D405 在 MuJoCo 中固定挂载到 UR5 末端或腕部坐标系，并随机械臂运动
- [x] `P0` 确认 `d405_rgb` 渲染视角与真实末端相机方向一致，朝向夹爪、工具和 handover zone
- [x] `P0` 确认 `d405_depth` 与 RGB 同视角、同时间戳或可对齐时间戳
- [ ] `P0` 确认 MuJoCo D405 内参来自真实 D405 实测值，而不是只用图像中心光轴占位
- [ ] `P0` 确认 D405 在 `robot_grasp` 阶段能看到夹爪和目标工具
- [ ] `P0` 确认 D405 在 `robot_offer` 阶段能看到工具和 handover zone
- [x] `P0` 在没有 human hand 前，先用 handover zone 标记或简化接收占位体检查未来人手进入区域是否在视野内
- [ ] `P0` 记录不同递送姿态下的遮挡情况，优先找出能同时看到夹爪、工具和接收区域的姿态

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
- [ ] `P1` 在观测面板中叠加 handover zone 或关键区域提示，辅助采集前检查

### S6.5 摄像头阶段验收

- [ ] `P0` 第一轮 camera-only smoke test 中，D405 能稳定看到夹爪、目标工具和 handover zone
- [x] `P0` D405 Depth 不出现全零、全 NaN、严重错位或明显尺度错误
- [x] `P0` `validation_summary.json` 能报告 `camera_capture_ok`、`camera_view_ok`、`frame_alignment_ok`
- [ ] `P0` S7 接入 human hand 后，必须复测 `human_approach/hesitation/retreat/release` 阶段的人手可见性
- [ ] `P0` 未通过 D405 观测验证和 human hand 可见性复测前，不允许进入批量协作数据采集
- [ ] `P0` 若 D405 看不到交接关键区域，优先调整 handover zone、机器人递送姿态或相机挂载角度

---

## 里程碑 S7：仿真人手与双边 VR 协作控制

### 目标

在现有 UR5 + 工具场景基础上加入 human hand，使 Quest3 能同时控制机器人侧和人手侧：左手控制机械臂抓取/递送，右手通过手势模式控制仿真人手接近、犹豫、后撤、稳定接收等行为。

### S7.1 human hand 资产与物理模型

- [ ] `P0` 选择第一版 human hand 表达：简化手掌 + 指尖碰撞体，优先保证可控和可记录
- [ ] `P0` 新增 `backend/mujoco_models/human_hand.xml` 或等效模型
- [ ] `P0` 为 human hand 配置稳定的 palm / fingertip collision geom
- [ ] `P0` 为 human hand 定义 `human_hand_root` 自由度，第一版至少支持 3D 平移 + yaw/pitch/roll
- [ ] `P0` 为人手定义接收区域 `handover_zone`，与 UR5 工作空间、桌面和工具保持合理距离
- [ ] `P0` 在 `shared/scene_manifest.json` 或新增配置中记录 human hand 初始位姿、可移动范围和安全边界
- [ ] `P0` 前端 Three.js 场景加载 human hand 可视模型，并按后端状态实时同步

### S7.2 右手 VR 手势到 human hand 的映射

- [ ] `P0` 明确 Quest3 左手用于机器人控制，右手用于 human hand 控制
- [ ] `P0` 设计右手位姿映射：Quest3 手部位姿 -> MuJoCo human hand 目标位姿
- [ ] `P0` 设计右手输入滤波、速度限制、工作区限制和丢失追踪后的 hold 逻辑
- [ ] `P0` 记录右手原始追踪状态：`tracked/lost/low_confidence`
- [ ] `P0` 记录右手派生动作：接近、停止、后撤、横向微调、晃动
- [ ] `P0` 前端显示 human hand 控制状态，区分机器人控制焦点和人手控制焦点
- [ ] `P1` 支持右手轨迹回放，用于复现 hesitation 和 retreat 样本

### S7.3 双边控制安全规则

- [ ] `P0` human hand 不允许穿桌、穿工具箱或穿过机器人夹爪实体
- [ ] `P0` human hand 与工具允许接触，但接触必须记录接触点、接触对象和接触持续时间
- [ ] `P0` human hand 与机器人连杆/夹爪发生危险距离过近时触发 `human_robot_proximity_warning`
- [ ] `P0` 当右手追踪丢失或快速跳变时，禁止 release 并进入 `handover_hold`
- [ ] `P0` 当左手机器人控制和右手人手控制出现冲突时，优先保证 human hand 安全边界
- [ ] `P0` 在状态广播中增加 `human_hand_state`、`human_hand_tracking_status`、`human_robot_min_distance`

### S7.4 VR 沉浸式快速采集入口

- [ ] `P0` 新增 Quest3 `VR采集模式`，让操作者在头显内完成 precheck、阶段选择、开始录制、停止录制和结果标记
- [ ] `P0` VR 采集模式显示 D405 状态、WebSocket 状态、左右手追踪状态、`recording_ready` 和最近错误
- [ ] `P0` VR 采集模式提供阶段模板：`camera_check/robot_offer_dryrun/normal_handover/hesitation/retreat/unstable/debug_negative`
- [ ] `P0` VR 采集模式中必须能一键或少步骤开始/停止 episode，避免操作者摘下头显回桌面端操作
- [ ] `P0` 每条正式 episode 写入 `operator_controlled=true`、`control_mode=vr_immersive_bilateral`、`autonomy_level=manual_demonstration`
- [ ] `P0` 正式训练候选数据必须来自 VR 人工示教，不允许程序自动驱动机械臂批量生成协作 episode
- [ ] `P0` 程序脚本只能用于 camera smoke test、接口测试、固定姿态检查或回放验证，不得冒充正式协作采集数据

### 验收

- [ ] `P0` 前后端能显示并同步 human hand 位姿
- [ ] `P0` Quest3 右手能稳定控制仿真人手靠近、停止和后撤
- [ ] `P0` 左手控制机器人、右手控制人手可同时录制，不互相覆盖控制状态
- [ ] `P0` 人手与工具、夹爪、机器人之间的距离和接触状态可记录
- [ ] `P0` 操作者可以不摘下 Quest3，在 VR 采集模式内完成一条 debug_trial 的开始、停止和结果标记

---

## 里程碑 S8：交互数据集、关系特征与阶段标签

### 目标

建立 interaction dataset。数据不只记录机器人轨迹，还要记录人手行为、工具状态、视觉观测和人机关系变化，尤其是用于训练协作记忆模型的 relation sequence。

### S8.1 数据目录与 episode 分级

- [ ] `P0` 创建 `data/datasets/quest3_safe_handover_v1/`
- [ ] `P0` 定义 episode 类型：`normal_handover/hesitation/retreat/unstable/early_release/collision_near_miss/operator_abort`
- [ ] `P0` 定义采集等级：`debug_trial/pilot/train_candidate/rejected`
- [ ] `P0` 定义采集控制来源字段：`operator_controlled/control_mode/autonomy_level/scripted_collection`
- [ ] `P0` 正式训练候选必须满足 `operator_controlled=true` 且 `scripted_collection=false`
- [ ] `P0` 每条 episode 记录 `handover_object_id`、`handover_object_class`、`handover_zone_id`
- [ ] `P0` 每条 episode 记录双边输入源：`robot_input_source`、`human_input_source`
- [ ] `P0` episode 结束后生成 `validation_summary.json`，判断是否可进入 manipulation 数据、memory 数据或仅保留调试

### S8.2 原始数据字段

- [ ] `P0` 记录机器人状态：`qpos/qvel/ee_pose/gripper_opening/grasp_state/attached_tool_id`
- [ ] `P0` 记录人手状态：`hand_pose/hand_velocity/fingertip_pose/tracking_confidence/hand_stability`
- [ ] `P0` 记录工具状态：`tool_pose/tool_velocity/tool_attached/tool_in_human_hand/tool_dropped`
- [ ] `P0` 记录视觉信息：`d405_rgb/d405_depth/frame_id/timestamp/frame_aligned`
- [ ] `P0` 记录动作信息：机器人动作、人手动作、原始 Quest3 输入和控制模式
- [ ] `P0` 记录交互事件：`first_contact_time/stable_contact_start/release_time/drop_time/retract_start`
- [ ] `P0` 记录安全事件：`unsafe_distance/collision_warning/premature_release/safe_hold`

### S8.3 relation feature 冻结

- [ ] `P0` 计算 `human_tool_distance`
- [ ] `P0` 计算 `human_robot_distance`
- [ ] `P0` 计算 `human_ee_distance`
- [ ] `P0` 计算 `human_tool_relative_velocity`
- [ ] `P0` 计算 `human_approach_speed`
- [ ] `P0` 计算 `retreat_speed` 与 `retreat_detected`
- [ ] `P0` 计算 `hand_stability_score`，例如滑动窗口内位置/姿态方差
- [ ] `P0` 计算 `pose_alignment_score`，衡量手掌接收姿态与工具递送方向是否对齐
- [ ] `P0` 计算 `contact_valid`、`contact_duration_ms`、`contact_consistency`
- [ ] `P0` 计算 `hesitation_score`，综合反复接近/后撤、速度符号变化和微抖动
- [ ] `P0` 计算 `handover_confidence_target`，供后续监督训练或评估使用

### S8.4 interaction phase 标注

- [ ] `P0` 冻结 phase 标签：`approach/stabilization/hesitation/retreat/ready/release/fail`
- [ ] `P0` 先实现规则辅助标注脚本，根据距离、速度、稳定性和接触事件生成候选标签
- [ ] `P0` 支持人工在回放界面修正 phase 标签
- [ ] `P0` 每条 step 保存 `phase_label`、`phase_source=rule/manual/model`、`phase_confidence`
- [ ] `P0` 对 `hesitation` 与 `retreat` 做强制覆盖检查，避免被误标为 `ready`
- [ ] `P1` 支持导出 phase 时间轴可视化

### S8.5 采集策略

- [ ] `P0` 分阶段采集，先 `camera_check`，再 `robot_offer_dryrun`，再 normal，最后采集 hesitation/retreat/unstable
- [ ] `P0` 每个阶段先完成少量 pilot，校验通过后再进入该阶段的批量采集
- [ ] `P0` 采集正常交接样本：操作者左手递送工具，右手稳定接近、对齐、短暂停顿后接收
- [ ] `P0` 采集 hesitation 样本：操作者右手接近后小幅晃动、停顿、反复微调
- [ ] `P0` 采集 retreat 样本：操作者右手接近后后撤或突然改变方向
- [ ] `P0` 采集 unstable 样本：操作者右手制造接触不稳、姿态不对齐或速度过快
- [ ] `P0` 采集 early release 负样本：仅在调试模式下由操作者受控制造提前释放，用于标注危险案例
- [ ] `P0` 每种工具至少覆盖正常、犹豫、后撤和不稳定四类交互
- [ ] `P1` 建立 episode 配比表，避免数据只包含成功交接

### S8.6 单条 episode 采集操作流程

- [ ] `P0` 采集前启动后端和前端，确认 WebSocket、MuJoCo、D405、UR5、工具和 human hand 均在线
- [ ] `P0` 采集前执行 reset，确认工具位姿、human hand 初始位姿和 handover zone 合法
- [ ] `P0` 采集前打开 D405 观测面板，确认夹爪、目标工具和 human hand 接收区域在末端相机视野内
- [ ] `P0` 采集前确认 Quest3 左手和右手追踪状态均为 `tracked`
- [ ] `P0` 采集前进入 Quest3 `VR采集模式`，确认头显内能看到采集状态和开始/停止入口
- [ ] `P0` 采集前在 VR 采集面板选择 `collection_stage`、`episode_type`、目标工具、`handover_zone_id` 和 `instruction_text`
- [ ] `P0` 采集前调用 `/dataset/precheck/` 或等效检查，只有 `recording_ready=true` 才允许正式录制
- [ ] `P0` 正常交接采集流程：操作者左手控制 UR5 抓取工具，移动到 handover zone，右手控制 human hand 稳定接近并对齐，ready 后执行 gated release
- [ ] `P0` hesitation 采集流程：右手接近工具后停顿、晃动、微调或反复接近，保持 `release_allowed=false`
- [ ] `P0` retreat 采集流程：右手先接近工具，再明显后撤，确认 `retreat_detected=true` 且 gate 阻止 release
- [ ] `P0` unstable 采集流程：右手快速接近、姿态不对齐或接触不稳，记录低稳定性和低对齐度片段
- [ ] `P0` early release 和 collision near miss 只允许在 `debug_trial` 或受控 pilot 中采集，默认不得进入正式训练候选
- [ ] `P0` 操作者在 VR 内停止 episode，并快速标记成功、失败、人工中止、相机异常或追踪异常
- [ ] `P0` 每条 episode 停止后写入 `result.json`、`validation_summary.json` 和基础预览信息

### S8.7 自动验证与人工筛选

- [ ] `P0` 自动验证 `metadata/visuals/states/actions/relations/events/phase_labels/result` 文件是否齐全
- [ ] `P0` 自动验证 RGB 和 Depth 均来自 D405，且 `stub_frame_used=false`
- [ ] `P0` 自动验证 D405 视野中能看到工具、夹爪和 human hand 关键区域
- [ ] `P0` 自动验证 RGB、Depth、状态和动作时间戳对齐误差低于阈值
- [ ] `P0` 自动验证机器人状态连续有效，`qpos/qvel/ee_pose/gripper` 无明显缺失
- [ ] `P0` 自动验证 human hand 追踪未长时间丢失，位姿没有异常跳变
- [ ] `P0` 自动验证每个有效 step 都能计算 relation feature
- [ ] `P0` 自动验证 phase 标签完整，且 `hesitation/retreat/ready` 无明显空洞
- [ ] `P0` 自动验证 candidate action、gated action、`release_allowed` 和 `gate_reason` 可追溯
- [ ] `P0` 自动验证正式训练候选来自 VR 人工示教，而不是脚本自动采集
- [ ] `P0` 人工回放 RGB-D，确认工具、夹爪和 human hand 可见
- [ ] `P0` 人工回放 3D 状态，确认机器人、人手和工具轨迹与 episode 类型一致
- [ ] `P0` 人工检查 relation timeline，确认距离、速度、稳定性和接触变化与画面一致
- [ ] `P0` 人工检查 phase timeline，确认 `hesitation`、`retreat`、`ready` 没有明显误标
- [ ] `P0` 人工检查 release/gate timeline，确认不安全状态下没有执行 release
- [ ] `P0` 根据验证结果把 episode 标记为 `debug_trial`、`memory_train_candidate`、`manipulation_train_candidate`、`eval_candidate` 或 `rejected`
- [ ] `P1` 生成 session 级采集质量报告，统计各类 episode 数量、通过率、缺帧率、误标修正数和 gate 拦截次数

### S8.8 pilot 验证门槛

- [ ] `P0` 每种工具至少完成 1 条 `normal_handover` pilot
- [ ] `P0` 每种工具至少完成 1 条 `hesitation` pilot
- [ ] `P0` 每种工具至少完成 1 条 `retreat` pilot
- [ ] `P0` 每种工具至少完成 1 条 `unstable` pilot
- [ ] `P0` 所有 pilot episode 都能生成完整 `relations.jsonl`
- [ ] `P0` 至少 80% pilot episode 通过 `camera_capture_ok` 和 `frame_alignment_ok`
- [ ] `P0` 至少 80% pilot episode 通过 `camera_view_ok`
- [ ] `P0` 人工回放确认 pilot 的 phase 标签与画面基本一致
- [ ] `P0` gate 在 `hesitation` 和 `retreat` pilot 中默认不允许 release
- [ ] `P0` 未通过 pilot 验证前，不进入批量采集

### S8.9 训练拆分与硬件策略

- [ ] `P0` 明确正式数据不做“一块端到端训练”，而是拆成 memory 数据和 pi0.5 LoRA 数据
- [ ] `P0` 从 raw episode 生成 memory 数据：`relations.jsonl + phase_labels.jsonl + release_allowed`
- [ ] `P0` 从 raw episode 生成 LeRobot / OpenPI 兼容 manipulation 数据：`d405_rgb + robot_state + action + task_prompt`
- [ ] `P0` 本地机器优先负责 relation feature 构建、phase 标注检查和 collaboration memory 小模型训练
- [ ] `P0` 5090D 32GB 服务器优先负责 pi0.5 LoRA / adapter 轻量微调
- [ ] `P0` 第一版禁止全参数微调，优先冻结 backbone，只训练 LoRA、adapter 或动作相关模块
- [ ] `P0` pi0.5 训练从 batch size `1-2`、gradient accumulation、半精度和 gradient checkpointing 开始
- [ ] `P0` D405 RGB 先使用可控分辨率版本，避免 32GB 显存被图像序列撑爆
- [ ] `P0` 训练、验证和测试按 episode 划分，禁止按帧随机打散
- [ ] `P0` release 相关帧单独标记，避免 pi0.5 把不安全 release 学成普通动作

### 验收

- [ ] `P0` 至少完成一组包含正常、hesitation、retreat、unstable 的 pilot 数据
- [ ] `P0` 每条 episode 都能生成 relation sequence
- [ ] `P0` phase 标签可回放检查
- [ ] `P0` `validation_summary.json` 能区分 manipulation 可用、memory 可用和 rejected
- [ ] `P0` 已形成可照着执行的数据采集操作手册和验证清单
- [ ] `P0` 正式训练候选数据都能追溯到 VR 操作者输入、阶段模板和开始/停止事件
- [ ] `P0` 已明确哪些数据进 memory 训练，哪些数据进 pi0.5 LoRA 训练，哪些只进评估或调试

---

## 里程碑 S9：协作记忆模型 collaboration memory

### 目标

训练一个时序模型理解人机关系是否已经稳定可信。该模型不直接控制机械臂运动，而是输出当前 `handover_phase`、`handover_confidence` 和 `release_allowed`，作为 release gating 的依据。

### S9.1 数据转换与切窗

- [ ] `P0` 新增 `scripts/datasets/build_relation_sequences.py`
- [ ] `P0` 将 raw episode 转换为固定频率 relation sequence，第一版建议 `10-20 Hz`
- [ ] `P0` 支持滑动窗口长度配置，例如 `1s/2s/3s`
- [ ] `P0` 每个窗口包含 relation feature、机器人状态摘要、人手状态摘要和工具状态摘要
- [ ] `P0` 每个窗口标签包含 `phase_label`、`release_allowed`、`unsafe_handover`
- [ ] `P0` 生成 `relation_feature_stats.json`，记录归一化参数
- [ ] `P0` 生成 `sequence_split.json`，按 episode 划分 train/val/test

### S9.2 模型结构与训练

- [ ] `P0` 新增 `backend/models/collaboration_memory/`
- [ ] `P0` 第一版实现 GRU 或 LSTM 模型
- [ ] `P0` 输入为 relation sequence，输出 phase logits、ready confidence 和 release gate
- [ ] `P0` 损失函数包含 phase classification loss、ready binary loss 和 unsafe release penalty
- [ ] `P0` 支持类别不平衡处理，避免模型把大多数帧都预测为 `approach`
- [ ] `P0` 训练配置写入 `configs/memory/safe_handover_gru.yaml`
- [ ] `P0` 训练脚本写入 `scripts/training/train_collaboration_memory.py`
- [ ] `P0` 模型输出写入 `models/memory/<run_id>/`
- [ ] `P0` 第一版 memory 训练优先在本地机器跑通，必要时用 CPU 或小 batch 先验证流程

### S9.3 离线评估

- [ ] `P0` 输出 `phase_accuracy`
- [ ] `P0` 输出 `ready_precision`、`ready_recall`、`ready_f1`
- [ ] `P0` 输出 `unsafe_release_false_positive_rate`
- [ ] `P0` 输出 `hesitation_recall` 与 `retreat_recall`
- [ ] `P0` 输出 `release_timing_error_ms`
- [ ] `P0` 输出混淆矩阵，重点检查 `hesitation/retreat` 是否被误判为 `ready`
- [ ] `P0` 保存失败窗口索引，能回溯到原始 episode 和时间戳

### S9.4 在线推理接口

- [ ] `P0` 新增 `backend/policies/collaboration_memory_adapter.py`
- [ ] `P0` 在线维护最近 N 秒 relation feature buffer
- [ ] `P0` 每个控制周期输出 `memory_phase`、`handover_confidence`、`release_allowed`
- [ ] `P0` 当输入缺帧、人手追踪丢失或 relation feature 异常时输出 `release_allowed=false`
- [ ] `P0` 在 WebSocket 状态广播中增加 memory 输出，供前端显示和录制

### 验收

- [ ] `P0` relation sequence 可训练 GRU/LSTM
- [ ] `P0` memory 模型能区分 `ready` 与 `hesitation/retreat`
- [ ] `P0` memory 模型可在线输出 release gate
- [ ] `P0` 离线评估指标和失败样本可追溯

---

## 里程碑 S10：pi0.5 LoRA 交接操作能力微调

### 目标

让 `pi0.5` 学会底层 handover manipulation：抓取工具、移动到交接区域、对齐人手、保持稳定递送姿态。`pi0.5` 不负责最终 release 决策，release 必须经过 collaboration memory gating。

### S10.1 数据转换

- [ ] `P0` 新增 `scripts/datasets/convert_handover_to_lerobot.py`
- [ ] `P0` 转换器读取 `quest3_safe_handover_v1` 中 manipulation 可用的 episode
- [ ] `P0` 转换器只读取 `manipulation_train_candidate`，跳过 `debug_trial/rejected`
- [ ] `P0` 转换器按 episode 对齐 D405 RGB、机器人状态、动作、任务文本和时间戳
- [ ] `P0` 转换器生成连续 `episode_index/frame_index/timestamp`
- [ ] `P0` 转换器输出 `observation.images.d405_rgb`
- [ ] `P0` 转换器输出 `observation.state=[qpos[0:6], gripper_opening]`
- [ ] `P0` 转换器可选输出 compact human hand state，但第一版不强制输入 pi0.5
- [ ] `P0` 转换器输出 action：`joint_delta[0:6] + gripper_target`
- [ ] `P0` 任务文本改为交接语义，例如 `pick up the wrench and hand it to the human`
- [ ] `P0` 转换器生成 `feature_mapping.json`、`conversion_report.json`、`rejected_episodes.jsonl`
- [ ] `P0` 转换器生成 action/state normalization 统计
- [ ] `P0` 按 episode 划分 train/val/test，禁止按帧随机打散
- [ ] `P0` release 相关样本单独标记，避免把不安全 release 学成普通动作
- [ ] `P0` Depth 第一版作为 sidecar 或回放/评估字段保留，不强制进入 pi0.5 主输入
- [ ] `P0` 用 LeRobot / OpenPI loader 做 smoke test，确认 RGB、state、action、prompt 和 timestamp 都可读

### S10.2 LoRA 微调

- [ ] `P0` 新增 `configs/pi05/quest3_safe_handover_lora.yaml`
- [ ] `P0` 新增或复用 `scripts/training/train_pi05.py` 支持 handover 数据集
- [ ] `P0` 第一版优先 LoRA 或冻结大部分 backbone，只微调动作相关模块
- [ ] `P0` 第一版 pi0.5 训练放到 5090D 32GB 服务器执行，不占用本地弱 GPU
- [ ] `P0` 训练配置支持 batch size `1-2`、gradient accumulation、半精度、gradient checkpointing
- [ ] `P0` 训练配置支持降低 D405 RGB 分辨率或缓存视觉特征，避免显存不足
- [ ] `P0` 训练配置记录数据集版本、相机版本、动作定义和任务文本模板
- [ ] `P0` 模型输出写入 `models/pi05/handover_lora_runs/<run_id>/`
- [ ] `P0` 离线评估输出 action MSE、gripper MAE、对齐阶段动作误差和动作平滑度

### S10.3 MuJoCo 验证

- [ ] `P0` 新增 `scripts/training/evaluate_handover_pi05_mujoco.py`
- [ ] `P0` 验证固定工具和固定 human hand 接收位姿
- [ ] `P0` 验证人手不同接近方向下的工具递送对齐能力
- [ ] `P0` 验证 pi0.5 输出 release 候选时仍必须经过 gating
- [ ] `P0` 记录 `handover_alignment_error`、`tool_drop_rate`、`robot_motion_jitter`

### 验收

- [ ] `P0` handover 数据可转换为 LeRobot / OpenPI 可训练格式，且不能直接用 raw JSONL 启动 pi0.5 训练
- [ ] `P0` 转换后的数据能通过 loader smoke test
- [ ] `P0` 转换报告能说明接收、跳过和拒绝的 episode 数量及原因
- [ ] `P0` pi0.5 LoRA run 可复现并入库
- [ ] `P0` pi0.5 能在 MuJoCo 中完成抓取、递送和对齐的基础 rollout
- [ ] `P0` pi0.5 不绕过 interaction gating 直接释放工具

---

## 里程碑 S11：interaction gating 集成与安全交接验证

### 目标

把 `pi0.5` 候选动作与 collaboration memory 的时机判断合成一个完整闭环：VLA 持续给出操作动作，memory 判断交互阶段，gating 只在 `ready` 且安全条件满足时允许 release。

### S11.1 gating 规则

- [ ] `P0` 定义 `release_allowed = memory_ready && contact_valid && hand_stable && safety_ok`
- [ ] `P0` 当 `memory_phase=hesitation/retreat` 时强制 `release_allowed=false`
- [ ] `P0` 当 `human_robot_min_distance` 低于安全阈值时强制进入 `safe_hold`
- [ ] `P0` 当人手追踪丢失、relation feature 缺失或 memory 置信度过低时禁止 release
- [ ] `P0` 当连续 ready 达到最短稳定窗口后才允许 release，避免瞬时误判
- [ ] `P0` 每次 gate 拦截都记录 `gate_reason`

### S11.2 运行时集成

- [ ] `P0` 新增 `backend/policies/handover_policy_runtime.py`
- [ ] `P0` runtime 同时加载 pi0.5 LoRA 和 collaboration memory
- [ ] `P0` runtime 每步生成 `candidate_action`、`memory_output`、`gated_action`
- [ ] `P0` 若 candidate action 包含 release，但 gate 拒绝，则替换为保持夹持或安全等待动作
- [ ] `P0` 前端显示当前 `handover_phase`、`handover_confidence`、`release_allowed`、`gate_reason`
- [ ] `P0` 录制器保存 candidate action 与 gated action 的差异

### S11.3 对比与消融

- [ ] `P0` baseline 1：距离阈值 release
- [ ] `P0` baseline 2：瞬时接触状态 release
- [ ] `P0` baseline 3：pi0.5 without memory gating
- [ ] `P0` proposed：pi0.5 + collaboration memory + interaction gating
- [ ] `P0` 消融：去掉 history，只用当前 relation feature
- [ ] `P1` 消融：GRU vs LSTM vs temporal CNN

### S11.4 评估指标

- [ ] `P0` 输出 `release_timing_accuracy`
- [ ] `P0` 输出 `unsafe_handover_rate`
- [ ] `P0` 输出 `collision_rate`
- [ ] `P0` 输出 `premature_release_rate`
- [ ] `P0` 输出 `handover_success_rate`
- [ ] `P0` 输出 `handover_drop_rate`
- [ ] `P0` 输出 `hesitation_block_success_rate`
- [ ] `P0` 输出 `retreat_block_success_rate`
- [ ] `P0` 输出平均交接时长和 release 延迟

### 验收

- [ ] `P0` 系统能在 normal handover 中允许 release
- [ ] `P0` 系统能在 hesitation 和 retreat 中阻止 release
- [ ] `P0` 与距离阈值/瞬时接触 baseline 相比，提前释放率或危险交接率有可测下降
- [ ] `P0` 所有评估结果能追溯到数据集版本、模型版本和配置版本

---

## 里程碑 S12：数字孪生映射与真实机械臂验证准备

### 目标

在仿真中验证稳定后，把实时状态映射到真实 UR5 的接口约束先冻结。第一版可以只做影子模式或低速 smoke test，不要求马上让真实机械臂执行完整交接。

### S12.1 sim2real 接口

- [ ] `P0` 定义统一 `runtime_target=sim/real_ur5/shadow_real_ur5`
- [ ] `P0` 统一仿真和实机的高层动作：`joint_target/joint_delta/gripper_target/release_request`
- [ ] `P0` 统一观测字段：机器人关节、夹爪、D405、human hand 估计状态、relation feature
- [ ] `P0` 明确真实 human hand 状态未来由视觉或外部追踪估计，当前仿真人手字段作为接口占位
- [ ] `P0` 模型注册表增加 `requires_memory_gate=true`、`release_policy=gated`
- [ ] `P0` 明确任何实机 release 都必须经过 safety gate 和人工确认开关

### S12.2 安全与日志

- [ ] `P0` 规划实机限速、急停、掉线保护和 watchdog
- [ ] `P0` 规划 `safe_hold`：机器人保持工具、不释放、不继续靠近人手
- [ ] `P0` 规划实机 shadow mode：策略只输出建议动作和 release 决策，不驱动真实硬件
- [ ] `P0` 记录仿真状态到实机状态映射误差
- [ ] `P0` 记录实机验证时的 `release_allowed`、`gate_reason`、人工接管事件

### S12.3 结果固化与复现实验

- [ ] `P0` 冻结数据集版本、phase 标签版本、relation feature 版本
- [ ] `P0` 冻结 memory 模型版本、pi0.5 LoRA 版本和 gating 配置版本
- [ ] `P0` 输出对比表：distance threshold、contact threshold、without memory、with memory
- [ ] `P0` 输出失败案例清单：提前释放、误拦截、后撤未识别、追踪丢失
- [ ] `P0` 输出关键回放材料到 `experiments/safe_handover/`
- [ ] `P1` 整理 sim2real shadow mode 结果和真实机械臂低速验证记录

### 验收

- [ ] `P0` 仿真端完整闭环可复现
- [ ] `P0` 真实机械臂接口字段和安全约束已冻结
- [ ] `P0` 所有结果都能追溯到数据集、模型和配置版本

---

## 三、按开发先后顺序的周计划版本

这部分不是替代上面的详细里程碑，而是把任务按更容易执行的时间顺序重新展开。
如果实际开发节奏更快或更慢，可以把“一周”理解为“一个阶段块”。

### 第 1 周：安全交接目标冻结周

目标：

- 把主任务从工具入库切换为安全交接时机理解
- 明确现有工具场景如何复用
- 冻结 `quest3_safe_handover_v1` 的任务定义

本周建议完成：

- [x] `P0` 冻结 `quest3_safe_handover_v1` 任务名
- [x] `P0` 写清楚“VLA 负责怎么递，memory 负责什么时候递”
- [x] `P0` 冻结 interaction phase 枚举
- [x] `P0` 冻结 release gate 的基本语义
- [x] `P0` 前后端已完成 `tools + toolbox` 场景替换
- [x] `P0` 已完成 S4.5 物理边界与 reset 合法性基线

周验收：

- [x] `P0` 新任务目标不再和工具入库混淆
- [x] `P0` 后续所有未开始任务都围绕安全交接展开

### 第 2 周：末端 D405 MuJoCo 观测验证周

目标：

- 确认协作数据的主视觉来自机械臂末端 D405
- 先在没有 human hand 的情况下验证夹爪、工具和 handover zone 可见
- 打通 RGB-D 预览、接口和落盘 smoke test

本周建议完成：

- [x] `P0` 确认 `d405_rgb / d405_depth` 是唯一训练主视觉来源
- [x] `P0` 确认 D405 末端挂载视角随机械臂运动，并朝向夹爪、工具和 handover zone
- [ ] `P0` 验证 `robot_grasp / robot_offer` 阶段的 D405 画面
- [x] `P0` 使用 handover zone 标记或简化接收占位体检查未来人手区域是否在视野内
- [x] `P0` 验证 RGB、Depth 接口均返回有效帧，且不是 stub / fallback
- [x] `P0` 前端观测面板能显示 D405 RGB、Depth、帧号、时间戳和有效性
- [ ] `P0` 录制器能把 RGB、Depth 和 `visuals.jsonl` 一起落盘
- [x] `P0` `validation_summary.json` 增加 `camera_source_ok`、`camera_capture_ok`、`camera_view_ok`、`frame_alignment_ok`

周验收：

- [ ] `P0` D405 能稳定看到夹爪、目标工具和 handover zone
- [ ] `P0` camera-only smoke test 通过后，可以进入 human hand 建模阶段
- [ ] `P0` 未通过 D405 第一轮观测验证前，不进入正式协作数据采集

### 第 3 周：human hand 建模、右手控制与 D405 复测周

目标：

- 在 MuJoCo 和前端中加入 human hand
- 让 Quest3 右手能控制仿真人手
- 打通 VR 沉浸式快速采集入口
- 复测 D405 是否能看到 human hand 进入、犹豫、后撤和 release 前后的关键区域

本周建议完成：

- [ ] `P0` 新增 human hand MuJoCo 模型
- [ ] `P0` 前端加载 human hand 可视模型
- [ ] `P0` 定义 human hand 初始位姿、接收区和工作区限制
- [ ] `P0` 完成右手位姿到 human hand 的映射
- [ ] `P0` 完成右手追踪丢失后的 hold 逻辑
- [ ] `P0` 在状态广播中加入 `human_hand_state`
- [ ] `P0` 在 Quest3 内新增 `VR采集模式`，支持 precheck、阶段模板选择、开始/停止录制和结果标记
- [ ] `P0` VR 采集模式显示 D405、WebSocket、左右手追踪和 `recording_ready`
- [ ] `P0` 复测 `human_approach / hesitation / retreat / release` 阶段的 D405 画面
- [ ] `P0` 若 human hand 关键区域不可见，调整 handover zone、递送姿态或相机挂载角度

周验收：

- [ ] `P0` Quest3 右手可稳定控制仿真人手接近、停止、后撤
- [ ] `P0` 人手状态能被前端显示和后端记录
- [ ] `P0` D405 能看到 human hand 与工具、夹爪之间的关键相对关系
- [ ] `P0` 操作者可以不摘下头显完成一条 debug_trial 的开始、停止和结果标记

### 第 4 周：双边协作录制与 relation feature 周

目标：

- 完成操作者左手机器人、右手人手的同步录制
- 生成第一版 relation sequence
- 固定 VR 沉浸式单条 episode 的操作流程，避免不同采集轮次动作不一致

本周建议完成：

- [ ] `P0` 创建 `data/datasets/quest3_safe_handover_v1/`
- [ ] `P0` 实现采集前 precheck，确认 WebSocket、D405、Quest3 双手追踪、human hand 和 reset 状态均可用
- [ ] `P0` 在 VR 采集面板中选择阶段模板、episode 类型、目标工具、handover zone 和任务文本
- [ ] `P0` 录制机器人、人手、工具、视觉和动作序列
- [ ] `P0` 每条 episode 写入 `operator_controlled=true`、`control_mode=vr_immersive_bilateral`、`scripted_collection=false`
- [ ] `P0` 计算人手-工具距离、人手-机器人距离、接近速度、后撤速度
- [ ] `P0` 计算手部稳定性、姿态对齐程度、接触持续时间
- [ ] `P0` 生成 `relations.jsonl`
- [ ] `P0` 回放界面显示 relation timeline
- [ ] `P0` episode 停止后自动生成 `result.json` 和 `validation_summary.json`

周验收：

- [ ] `P0` 一条 episode 能完整回放机器人、人手、工具和 relation feature
- [ ] `P0` relation feature 与画面表现基本一致
- [ ] `P0` 采集者能在 Quest3 内按固定步骤完成一条 normal handover 和一条 hesitation episode
- [ ] `P0` 正式训练候选不会混入程序自动驱动生成的 episode

### 第 5 周：交互阶段标注与 pilot 数据周

目标：

- 分阶段采集正常、犹豫、后撤、不稳定交接样本
- 建立可训练的 phase 标签
- 建立 pilot 数据的自动验证和人工筛选规则

本周建议完成：

- [ ] `P0` 实现规则辅助 phase 标注脚本
- [ ] `P0` 支持人工修正 `phase_label`
- [ ] `P0` 按阶段先采 normal，再采 hesitation，再采 retreat，最后采 unstable，不混着批量采
- [ ] `P0` 每种工具采集 normal / hesitation / retreat / unstable 样本
- [ ] `P0` 生成 `validation_summary.json`
- [ ] `P0` 自动验证文件完整性、D405 帧有效性、时间戳对齐、人手追踪、relation feature 和 gate 日志
- [ ] `P0` 人工回放检查 RGB-D、3D 状态、relation timeline、phase timeline 和 release/gate timeline
- [ ] `P0` 根据验证结果标记 `memory_train_candidate`、`manipulation_train_candidate`、`eval_candidate` 或 `rejected`
- [ ] `P0` 完成 episode 级 train/val/test 初步划分

周验收：

- [ ] `P0` pilot 数据覆盖至少四类交互情况
- [ ] `P0` phase 标签可回放检查
- [ ] `P0` 未通过 pilot 验证前不会进入批量采集

### 第 6 周：collaboration memory 训练周

目标：

- 用 relation sequence 训练 GRU/LSTM 协作记忆模型
- 让模型能识别 ready、hesitation 和 retreat
- 优先在本地机器跑通轻量训练和评估

本周建议完成：

- [ ] `P0` 完成 `build_relation_sequences.py`
- [ ] `P0` 完成 GRU/LSTM 第一版模型
- [ ] `P0` 完成 `train_collaboration_memory.py`
- [ ] `P0` 本地跑通 memory 小模型训练，不依赖 5090D 服务器
- [ ] `P0` 输出 phase accuracy、ready F1、unsafe false positive rate
- [ ] `P0` 失败样本可回溯到原 episode

周验收：

- [ ] `P0` memory 模型能离线区分 ready 与 hesitation/retreat
- [ ] `P0` memory 输出能进入在线 adapter

### 第 7 周：pi0.5 LoRA 交接操作周

目标：

- 让 pi0.5 学会抓取、递送和对齐人手
- 不让 pi0.5 单独决定 release
- 用 5090D 32GB 服务器做轻量 LoRA / adapter 微调，不做全参数训练

本周建议完成：

- [ ] `P0` 完成 handover 数据到 LeRobot / OpenPI 的转换
- [ ] `P0` 转换后跑通 loader smoke test，确认 RGB、state、action、prompt、timestamp 都可读
- [ ] `P0` 生成 `feature_mapping.json`、`conversion_report.json`、`rejected_episodes.jsonl` 和 normalization 统计
- [ ] `P0` 完成 `quest3_safe_handover_lora.yaml`
- [ ] `P0` 在 5090D 32GB 服务器上启动 pi0.5 LoRA 微调
- [ ] `P0` 使用小 batch、gradient accumulation、半精度和 gradient checkpointing 控制显存
- [ ] `P0` 模型入库到 `models/pi05/handover_lora_runs/<run_id>/`
- [ ] `P0` MuJoCo 验证 pi0.5 可完成基础递送对齐

周验收：

- [ ] `P0` LeRobot / OpenPI 数据集转换通过校验
- [ ] `P0` pi0.5 LoRA 模型可加载并执行 handover rollout
- [ ] `P0` release 决策仍由 gating 控制

### 第 8 周：interaction gating 集成周

目标：

- 合并 pi0.5 候选动作与 memory release gate
- 验证 hesitation/retreat 下不会释放

本周建议完成：

- [ ] `P0` 完成 `handover_policy_runtime.py`
- [ ] `P0` 每步输出 candidate action、memory output、gated action
- [ ] `P0` 实现 release 拦截和 `gate_reason`
- [ ] `P0` 前端显示 phase、confidence、release_allowed
- [ ] `P0` 录制 candidate/gated action 差异

周验收：

- [ ] `P0` normal handover 中可以 release
- [ ] `P0` hesitation/retreat 中阻止 release

### 第 9 周：评估、消融与复现周

目标：

- 对比无记忆方法和协作记忆方法
- 输出可复现结果

本周建议完成：

- [ ] `P0` 实现 distance threshold baseline
- [ ] `P0` 实现 contact threshold baseline
- [ ] `P0` 实现 without memory gating baseline
- [ ] `P0` 输出 release timing accuracy、unsafe handover rate、premature release rate
- [ ] `P0` 输出 handover success rate、collision rate、drop rate
- [ ] `P0` 固化数据集、模型和配置版本

周验收：

- [ ] `P0` with memory 相比 baseline 在危险释放或提前释放上有可测下降，或输出明确失败分析

### 第 10 周：数字孪生与实机接口冻结周

目标：

- 把仿真中稳定的状态、动作和 gate 映射到真实 UR5 接口
- 优先完成 shadow mode 和低速验证准备

本周建议完成：

- [ ] `P0` 冻结 `runtime_target=sim/real_ur5/shadow_real_ur5`
- [ ] `P0` 冻结高层动作接口和 release request 接口
- [ ] `P0` 冻结真实人手状态估计接口占位
- [ ] `P0` 规划实机安全机制和人工确认开关
- [ ] `P0` 记录仿真到实机的状态映射误差

周验收：

- [ ] `P0` 实机接入不需要推翻现有 handover runtime
- [ ] `P0` release 相关安全约束在接口层有明确落点

---

## 四、当前最优先的主链路任务

为了避免任务过散，下一轮实际开发优先盯住这组任务：

- [x] `P0` 前后端把 `battery_pack` 逻辑替换为 `tools + toolbox`
- [x] `P0` 实现多工具对象状态同步
- [x] `P0` 建立物理边界基线，解决前后端虚拟干涉并阻止明显穿桌、穿箱、穿工具
- [x] `P0` 完成 reset 合法性检查，确保工具平躺、工具箱开口朝上且对象不穿透
- [ ] `P0` 冻结 `quest3_safe_handover_v1` 主任务和 interaction phase
- [ ] `P0` 固定 `d405_rgb / d405_depth` 为协作数据唯一训练主视觉来源，并禁止使用 Quest3 页面画面或 Three.js 外部相机替代
- [ ] `P0` 先完成末端 D405 在 MuJoCo 中的第一轮观测验证，确认工具、夹爪和 handover zone 可见
- [ ] `P0` 新增 human hand 模型、前端显示和状态广播
- [ ] `P0` 打通 Quest3 右手控制仿真人手
- [ ] `P0` human hand 接入后复测 D405，确认人手、工具、夹爪关键区域可见
- [ ] `P0` 新增 VR 沉浸式快速采集入口，支持阶段模板、precheck、开始/停止录制和结果标记
- [ ] `P0` 建立双边协作 episode 录制器
- [ ] `P0` 固定单条 episode 的采集操作流程：precheck、选择类型、开始录制、执行交互、停止、校验、标记去向
- [ ] `P0` 冻结 relation feature schema，并生成 `relations.jsonl`
- [ ] `P0` 冻结训练拆分策略：memory 本地轻量训练，pi0.5 LoRA 放到 5090D 32GB 服务器
- [ ] `P0` 按阶段采集 normal / hesitation / retreat / unstable pilot 数据，每阶段先 pilot 再批量
- [ ] `P0` 建立自动验证和人工回放筛选流程
- [ ] `P0` 完成 phase 标注和回放检查
- [ ] `P0` 训练第一版 collaboration memory
- [ ] `P0` 完成 pi0.5 LoRA handover manipulation 微调
- [ ] `P0` 集成 interaction gating，阻止 hesitation/retreat 下 release
- [ ] `P0` 完成 baseline、消融和安全交接指标评估
- [ ] `P0` 冻结 sim2real shadow mode 接口和 release 安全约束

---

## 五、补充提醒

- 当前最有价值的既有资产，是已经能实时映射的 UR5、工具、工具箱、VR 控制、D405 规划和 S4.5 物理边界基线。
- 当前最不建议的路线，是继续只做“能不能抓、能不能递”的操作能力，而忽略“什么时候可以安全释放”的交互时机问题。
- 新路线的核心顺序是“末端 D405 MuJoCo 观测验证 -> human hand -> D405 人手可见性复测 -> VR 沉浸式采集入口 -> 双边人工示教录制 -> relation feature -> phase 标签 -> collaboration memory -> pi0.5 LoRA -> interaction gating -> 对比评估 -> sim2real shadow mode”。
- 正式采集的底线，是每条 episode 必须同时有机器人状态、人手状态、工具状态、视觉帧、relation sequence、phase 标签和 release/gate 日志。
- 正式训练候选必须来自操作者在 Quest3 中的人工示教，程序脚本只能用于相机、接口、固定姿态和回放验证。
- `hesitation` 与 `retreat` 是最关键的负样本；如果数据中只有顺利交接，协作记忆模型无法学会安全时机判断。
- `pi0.5` 的职责应限制在 manipulation，release 决策必须由 memory 和 safety gate 共同控制。
