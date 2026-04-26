# Quest3 工具抓取实验 ToDo（2026-04-12 修订）

基于 [task.md](task.md) 重新整理。  
本清单以 `2026-04-12` 主分支真实代码状态为基准，分成两部分：

1. 当前已经完成的基线总结
2. 围绕 Quest3 工具抓取实验的新主链路任务

说明：

- `P0`：主链路必做，直接影响实验是否成立
- `P1`：重要增强项，建议主链路稳定后补齐
- `P2`：优化项、论文增强项或后续扩展项
- 本轮是文档重构，不创建目录、不修改业务代码

---

## 一、已完成基线总结

这一部分对应“旧 ToDo 中已经完成、而且经代码复核确认属实”的内容。

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
- [ ] `P0` 工具箱放置逻辑
- [ ] `P0` 末端 `Intel RealSense D405` 主相机接入
- [ ] `P0` 末端 `RGB-D` 观测导出链路
- [ ] `P0` `RGB-D + 状态 + 动作 + 文本` 采集协议冻结
- [ ] `P0` RL 环境与训练脚本
- [ ] `P0` 初训模型加载到 MuJoCo 的验证入口
- [ ] `P0` 强化学习后模型加载到 MuJoCo 的验证入口
- [ ] `P0` Quest3 / VR / WebXR 输入链路
- [ ] `P0` 数据集与模型目录
- [ ] `P1` 末端 `D405` 的调试预览与回放接口
- [ ] `P1` 自动化测试体系

---

## 二、新实验主链路 ToDo

以下任务全部围绕新的 `quest3_tool_sorting_v1` 实验目标展开。

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
- [ ] `P1` 输出一份旧 battery 版本的归档说明，供论文或答辩时回溯使用

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

## 里程碑 S4.5：VR 运动安全壳与接触稳定前置闸门

### 目标

在正式进入数据集采集前，先把 Quest3 控制下的穿模、干涉、接触不可信和工具不可交互问题收敛到可记录、可复现、可验收的范围。  
这一阶段不要求一步到位实现完全真实的力反馈抓取，但必须避免把明显穿桌、穿箱、穿工具或接触状态不可信的数据录入正式训练集。

### S4.5.1 问题边界冻结

- [ ] `P0` 明确当前 VR 控制属于 `teleop + joint position target`，不能默认等同于真实力控或阻抗控制
- [ ] `P0` 将接触问题拆成三类：机械臂/夹爪穿桌穿箱、工具被碰撞但不运动、工具被夹住后无法稳定搬运
- [ ] `P0` 明确正式采集前至少要解决“明显穿桌/穿箱/穿工具”的安全壳问题
- [ ] `P0` 明确第一版允许采用“物理接触 + 规则判定 + 临时附着”的半物理抓取方案
- [ ] `P0` 明确纯物理夹取不是数据集采集前的硬性目标，避免因接触参数调试阻塞主链路
- [ ] `P0` 在文档中区分 `collision_blocked`、`contact_valid`、`grasp_attached`、`physics_only_grasp` 的语义

### S4.5.2 VR 控制安全壳

- [ ] `P0` 每条 Quest3 控制命令执行前保存上一帧安全状态
- [ ] `P0` 对 VR 关节目标做限幅、速度限制和单步最大增量限制
- [ ] `P0` 对候选动作做 MuJoCo 前向检查，发现非法穿透时拒绝该动作或缩小步长
- [ ] `P0` 区分允许接触和禁止接触：允许夹爪指尖接触目标工具，禁止手臂/夹爪穿透桌面、工具箱和非目标物体
- [ ] `P0` 在状态广播中记录 `safety_status=normal/limited/collision_blocked/safe_hold`
- [ ] `P0` 在状态广播中记录最近一次拦截原因、接触对象和最大穿透深度
- [ ] `P0` 前端在 VR 模式中显示“碰撞保护中/动作被限幅/安全保持”等轻提示
- [ ] `P0` 发生连续碰撞拦截时自动进入 safe hold，而不是继续积压控制命令
- [ ] `P1` 记录 VR 控制延迟、命令丢弃数和碰撞拦截次数，作为采集质量指标

### S4.5.3 工具与桌面物理交互基线

- [ ] `P0` 确认工具对象具备可参与物理交互的运动自由度，不能只是固定展示模型
- [ ] `P0` 为工具配置合理质量、惯量、摩擦和简化碰撞体
- [ ] `P0` 为桌面、工具箱、夹爪指尖配置可用碰撞体，优先使用 box/capsule 等稳定几何
- [ ] `P0` 确认重力、接触参数和摩擦参数适合桌面抓取任务
- [ ] `P0` 工具被夹爪或手臂轻微碰到时，应能产生可解释的滑动、滚动或被拦截结果
- [ ] `P0` 工具不应在 reset 后悬空、穿桌、翻立或与工具箱/其他工具重叠
- [ ] `P1` 为不同工具分别调参，记录每类工具的质量、摩擦、碰撞体版本和已知问题

### S4.5.4 抓取稳定的第一版策略

- [ ] `P0` 定义第一版抓取成功条件：目标工具在夹爪工作区域内、夹爪闭合超过阈值、接触/距离满足阈值
- [ ] `P0` 定义第一版释放成功条件：解除附着后工具位于工具箱有效区域内且姿态合理
- [ ] `P0` 实现或规划夹爪闭合后的 `grasp_candidate -> grasp_attached -> released` 状态机
- [ ] `P0` 抓取成功后允许使用 weld/constraint 或等效逻辑附着，保证示教搬运动作可重复
- [ ] `P0` 释放时解除附着，并检查工具是否落入工具箱开口朝上的有效空间
- [ ] `P0` 附着/释放事件必须写入状态序列和结果标签
- [ ] `P1` 记录滑落、误抓、碰撞失败、放置失败等失败原因，用于后续数据筛选

### S4.5.5 reset 合法性检查

- [ ] `P0` reset 后工具位置必须在 UR5 可达桌面区域内
- [ ] `P0` reset 后工具姿态必须符合实际桌面放置：只允许平躺或有限倾斜，不允许竖直立起
- [ ] `P0` reset 后工具箱必须保持开口朝上，不允许侧翻、倒扣或悬空
- [ ] `P0` reset 后工具、工具箱、桌面、机械臂之间不能存在明显初始穿透
- [ ] `P0` reset 后目标工具与工具箱之间保留足够分离距离，避免 episode 一开始就接近完成状态
- [ ] `P0` reset 失败时应重采样并记录重采样次数，超过上限则拒绝开始 episode
- [ ] `P1` 将 reset seed、采样区域、采样姿态、重采样次数写入 episode 元数据

### S4.5.6 采集前验收

- [ ] `P0` Quest3 控制机械臂靠近桌面时不会明显穿桌
- [ ] `P0` Quest3 控制夹爪靠近工具时不会直接穿过目标工具
- [ ] `P0` 非目标物体和工具箱碰撞能被阻止或清晰标记为无效动作
- [ ] `P0` 至少连续完成 10 次 reset，工具和工具箱姿态均符合物理常识
- [ ] `P0` 至少完成 3 条试采 episode，接触/拦截/附着状态均能在日志中复查
- [ ] `P0` 正式采集开关只有在相机、reset、接触安全壳和录制器均通过检查后才允许启用

---

## 里程碑 S5：数据集采集闭环

### 目标

建立“你通过 Quest3 手动示教，系统自动录制并存盘”的完整数据采集链路。
S5 默认依赖 S4.5 的 VR 运动安全壳与接触稳定前置闸门；若接触状态仍不可信，只允许进行调试试采，不应纳入正式训练集。

### S5.0 正式采集前置检查

- [ ] `P0` 底部导航栏新增 `采集` 入口，入口状态必须能反映 `recording_ready / recording / debug_only / error`
- [ ] `P0` `采集` 入口点击后打开非全屏采集面板，不遮挡场景中心和 VR 控制反馈
- [ ] `P0` 前端采集入口实现状态机：`idle/checking/ready/debug_only/recording/finalizing/completed/error`
- [ ] `P0` 底部导航栏录制状态至少显示当前 episode、目标工具、`REC` 状态和简短错误原因
- [ ] `P0` 采集面板显示前置检查、episode 配置、录制控制、实时计数、结束摘要和快速回放入口
- [ ] `P0` 采集前检查后端在线、WebSocket 在线、MuJoCo backend 可用
- [ ] `P0` 采集前确认训练视觉源为 MuJoCo 末端 D405，即 `d405_rgb / d405_depth`，禁止使用 Quest3 页面画面或 Three.js 观察相机作为训练输入
- [ ] `P0` 采集前检查末端 D405 `RGB`、`Depth` 接口均在线
- [ ] `P0` 采集前检查 `camera_capture_ok=true`，正式训练数据禁止使用 stub / fallback 图像
- [ ] `P0` 采集前检查当前 `camera_device`、`camera_mount_name`、内参版本、外参版本已写入 metadata
- [ ] `P0` 采集前检查 `qpos`、`qvel`、`ee_pose`、`gripper_opening`、`objects` 均可持续更新
- [ ] `P0` 采集前检查 Quest3 输入源、输入模式、关节组和原始输入值可记录
- [ ] `P0` 采集前检查当前目标工具类别、工具实例、目标槽位和 `instruction_text` 已绑定
- [ ] `P0` 采集前检查 reset 采样结果通过姿态、碰撞、可达性和工作区合法性检查
- [ ] `P0` 采集前检查 `safety_status` 为 `normal`，没有连续碰撞拦截或 safe hold
- [ ] `P0` 采集前执行短时 smoke recording，确认 RGB、Depth、状态、动作能同时落盘
- [ ] `P0` 采集前 UI 显示 `recording_ready=true`，否则禁用正式录制按钮
- [ ] `P0` 后端 `/dataset/precheck/` 返回结构化检查结果：`recording_ready`、`allowed_tier`、`checks`、`reject_reasons`、`warnings`
- [ ] `P1` 采集前显示预计磁盘占用、剩余空间和当前写盘频率

### S5.0.1 采集接口与状态广播

- [ ] `P0` 新增 `GET /dataset/status/`，返回当前采集状态、活动 session、活动 episode 和写盘状态
- [ ] `P0` 新增 `POST /dataset/session/start/`，创建或恢复采集 session
- [ ] `P0` 新增 `POST /dataset/episode/start/`，创建 episode 并开始录制
- [ ] `P0` 新增 `POST /dataset/episode/stop/`，停止录制并触发保存、校验和预览生成
- [ ] `P0` 新增 `POST /dataset/episode/abort/`，异常中止并保留 `aborted` 目录
- [ ] `P0` 新增 `GET /dataset/episode/{episode_id}/summary/`，读取 `result.json` 与 `validation_summary.json`
- [ ] `P1` 新增 `GET /dataset/episode/{episode_id}/preview/`，读取 RGB 预览视频或关键帧
- [ ] `P1` 新增 `POST /dataset/episode/{episode_id}/mark/`，支持人工标记是否纳入训练集和剔除原因
- [ ] `P0` WebSocket 状态广播补充 `recording_status`、`recording_tier`、`active_session_id`、`active_episode_id`
- [ ] `P0` WebSocket 状态广播补充 `target_tool_id`、`target_tool_class`、`instruction_text`
- [ ] `P0` WebSocket 状态广播补充帧数、状态样本数、动作样本数、写盘队列和最近录制错误

### S5.0.2 episode 生命周期

- [ ] `P0` 明确 episode 生命周期为 `idle -> precheck -> episode_created -> recording -> stopping -> finalizing -> completed/rejected/aborted`
- [ ] `P0` `episode_created` 阶段冻结 metadata、目标工具、任务文本、相机版本、reset seed 和采集等级
- [ ] `P0` `recording` 阶段禁止 reset，避免破坏 episode 初始条件
- [ ] `P0` `recording` 阶段如切换 VR 输入源，必须写入异常标记或自动结束 episode
- [ ] `P0` `stopping/finalizing` 阶段禁用重复点击开始/停止，避免重复写盘
- [ ] `P0` `completed` 只代表保存完成，是否进入训练集必须由 `validation_summary` 和人工抽查决定
- [ ] `P0` `aborted` episode 必须保留目录和 partial summary，默认不可进入训练集

### S5.1 目录与命名规则

- [ ] `P0` 创建 `data/datasets/quest3_tool_sorting_v1/`
- [ ] `P0` 设计 session 命名规则
- [ ] `P0` 设计 episode 命名规则
- [ ] `P0` 创建 `models/`、`logs/`、`experiments/` 顶层目录
- [ ] `P0` 创建 `models/pi05/initial_runs/`
- [ ] `P0` 创建 `models/rl/finetune_runs/`
- [ ] `P0` 创建 `models/registry/`
- [ ] `P1` 创建 `data/replay/` 与 `data/calibration/`
- [ ] `P0` 明确 raw episode 目录内包含 `visuals.jsonl` 或等效视觉帧索引文件
- [ ] `P0` 明确 session 级 `session_metadata.json`，记录采集者、设备、代码版本和配置版本
- [ ] `P0` 明确 episode 编号不可复用，异常中断也要保留 `aborted` 状态目录
- [ ] `P0` 明确 `videos/` 仅作为快速查看和论文展示，训练主数据以逐帧 RGB/Depth 为准
- [ ] `P1` 为每个 episode 生成校验摘要，例如帧数、时长、缺帧率和文件大小

### S5.2 数据字段冻结

- [ ] `P0` 冻结 `metadata.json` 字段
- [ ] `P0` 冻结 `language.json` 或等效任务文本字段
- [ ] `P0` 冻结视觉帧索引字段
- [ ] `P0` 冻结 `visuals.jsonl` 或等效视觉索引字段
- [ ] `P0` 冻结 `states.jsonl` 字段
- [ ] `P0` 冻结 `actions.jsonl` 字段
- [ ] `P0` 冻结 `result.json` 字段
- [ ] `P0` 冻结 `validation_summary.json` 字段
- [ ] `P0` 明确记录 `RGB` 帧路径
- [ ] `P0` 明确记录 `Depth` 帧路径
- [ ] `P0` 明确训练主数据必须是逐帧 `rgb/`、逐帧 `depth/` 和 `visuals.jsonl`，不能只保存 MP4
- [ ] `P0` 明确记录 `RGB` / `Depth` 时间戳和帧对齐状态
- [ ] `P0` 明确记录输入模式、关节组、目标槽位和工具类别
- [ ] `P0` 明确记录当前控制来源和策略阶段
- [ ] `P0` 明确记录 `runtime_target`、`robot_platform` 和 `calibration_version`
- [ ] `P0` 明确记录 `camera_device=intel_realsense_d405`
- [ ] `P0` 明确记录 `camera_intrinsics_version` 与 `camera_extrinsics_version`
- [ ] `P0` 明确记录 `instruction_text`
- [ ] `P0` 明确记录 Quest3 输入原始值
- [ ] `P0` 明确 `Depth` 使用无损格式保存
- [ ] `P0` 明确 `Depth` 禁止使用 JPG、有损视频帧或其他会破坏深度值的格式作为主数据
- [ ] `P0` 明确记录 `camera_capture_ok`、`visual_valid`、`rgb_missing`、`depth_missing`、`frame_aligned`
- [ ] `P0` 明确正式训练样本中 `stub_frame_used=false` 或等效字段
- [ ] `P0` 明确记录 `safety_status`、`collision_blocked`、`contact_state` 和最大穿透深度
- [ ] `P0` 明确记录 `grasp_state=none/candidate/attached/released/failed`
- [ ] `P0` 明确记录 reset seed、工具初始位姿、工具箱位姿、采样区域和重采样次数
- [ ] `P0` 明确记录 `target_tool_id`、`target_tool_class`、`target_slot_id` 和语言模板版本
- [ ] `P0` 明确记录 episode 是否为 `debug_trial`、`pilot`、`train_candidate` 或 `rejected`
- [ ] `P0` 明确失败原因枚举：`collision_failure`、`drop_failure`、`camera_failure`、`reset_invalid`、`operator_abort`、`timeout`
- [ ] `P1` 设计 Parquet 版本的可选导出格式

### S5.3 录制器实现

- [ ] `P0` 在底部导航栏或其二级采集面板中新增采集开始按钮
- [ ] `P0` 在底部导航栏或其二级采集面板中新增采集停止按钮
- [ ] `P0` 录制开始按钮必须受 `recording_ready` 控制；不通过前置检查时只能启动 `debug_trial`
- [ ] `P0` 正式录制、`debug_trial` 录制必须使用不同的按钮文案或确认提示，防止误把调试数据当正式数据
- [ ] `P0` 录制中底部导航栏持续显示 `REC`、episode ID、目标工具和写盘状态
- [ ] `P0` 录制停止后自动触发保存、校验和预览生成，并在采集面板显示结果摘要
- [ ] `P0` 明确默认采集者为你本人，系统负责记录而不是自动生成示教
- [ ] `P0` 录制前自动生成 session / episode 标识
- [ ] `P0` 录制过程中持续写入 `RGB` 帧
- [ ] `P0` 录制过程中持续写入 `Depth` 帧
- [ ] `P0` 录制过程中持续写入 `visuals.jsonl`，每条视觉记录包含 `frame_id`、RGB 路径、Depth 路径、时间戳、相机位姿和有效性
- [ ] `P0` 录制过程中持续写入状态和动作序列
- [ ] `P0` 录制过程中写入任务文本和视觉帧索引
- [ ] `P0` episode 结束时写入结果标签
- [ ] `P0` 保存 Quest3 输入模式信息
- [ ] `P0` 保存当前控制来源信息
- [ ] `P0` 保存当前是否为人工示教阶段
- [ ] `P0` 在 episode 结束时检查 `RGB-D`、状态、动作是否完整对齐
- [ ] `P0` 录制开始前自动调用 S5.0 前置检查，不通过则只允许调试模式
- [ ] `P0` 每条动作写入前后都要关联最近有效视觉帧 ID 和状态时间戳
- [ ] `P0` 任一动作缺少 `paired_frame_id` 时，episode 默认不得成为 `train_candidate`
- [ ] `P0` 每个视觉帧写入后要记录文件路径、时间戳、尺寸、格式和有效性
- [ ] `P0` 每个状态样本写入当前 `qpos/qvel/ee_pose/gripper/objects/camera/safety/grasp_state`
- [ ] `P0` 每个动作样本写入目标关节、夹爪命令、原始输入、归一化输入和选中关节组
- [ ] `P0` 录制过程中若相机掉帧、碰撞阻塞或手势追踪丢失，需要写入异常标记而不是静默丢失
- [ ] `P0` episode 停止时写入 `result.json`，区分成功、失败、人工中止和调试试采
- [ ] `P0` episode 停止时生成 `validation_summary.json`，作为能否进入训练集的第一道筛选
- [ ] `P0` 支持保存低码率 MP4 预览视频，便于人工快速检查
- [ ] `P0` MP4 预览视频不得作为唯一训练数据；训练读取必须以逐帧 RGB/Depth 和 JSONL 索引为准
- [ ] `P0` 相机缺帧、stub 图像、safe hold、Quest3 掉线、磁盘不足等异常必须写入 result 和 summary
- [ ] `P0` 录制异常中断时保留 `aborted` episode 目录，生成 `partial_summary.json`
- [ ] `P0` 录制器启动时锁定本次 episode 的 `instruction_text`，录制中不允许静默变更
- [ ] `P1` 写盘采用缓冲或异步队列，避免录制导致 VR 控制卡顿
- [ ] `P1` 支持中断恢复与异常退出保护

### S5.4 数据回放与检查

- [ ] `P0` 支持回放单个 episode
- [ ] `P0` 支持回放单步 `RGB` 与 `Depth` 观测
- [ ] `P0` 支持确认 episode 视觉源确实来自末端 D405，而不是 Quest3 页面、Three.js 观察相机或调试相机
- [ ] `P0` 支持检查工具初始位姿与动作轨迹
- [ ] `P0` 支持快速查看 episode 成功或失败结果
- [ ] `P0` 支持检查 Quest3 输入模式与原始输入记录
- [ ] `P0` 支持检查 `RGB-D` 是否有缺帧、错帧或未对齐情况
- [ ] `P0` 支持查看 RGB 预览视频和逐帧 RGB 图像
- [ ] `P0` 支持查看 Depth 原始图和伪彩深度图，确认深度未用有损格式破坏
- [ ] `P0` 支持按时间轴同时查看动作、状态、视觉帧、接触状态和安全状态
- [ ] `P0` 支持检查 reset 初始位姿是否真实有效，例如工具是否平躺、工具箱是否开口朝上
- [ ] `P0` 支持检查 episode 是否包含 stub/fallback 图像，正式训练集必须剔除
- [ ] `P0` 支持检查是否存在“只有 MP4、没有逐帧 RGB/Depth”的 episode，并自动拒绝进入训练集
- [ ] `P0` 支持人工标记 `included_in_train=false` 并填写剔除原因
- [ ] `P0` 支持查看 `aborted` 或 `rejected` episode 的 partial summary，便于调试
- [ ] `P0` 支持从采集面板直接打开最近一条 episode 的 summary 和预览
- [ ] `P0` 支持导出 pilot 采集报告，统计成功率、缺帧率、碰撞拦截次数和平均时长
- [ ] `P1` 支持导出采集统计表

### S5.5 试采、筛选与批量采集规则

- [ ] `P0` 先进行 `debug_trial` 试采，不直接进入正式训练集
- [ ] `P0` 每类工具至少完成 1 条完整试采 episode，确认语言、工具类别和目标槽位绑定正确
- [ ] `P0` 试采阶段必须人工查看 RGB/Depth/状态/动作/接触日志，确认没有明显穿模和数据缺失
- [ ] `P0` pilot 阶段每类工具至少采集少量成功和失败样本，用于验证结果标签和筛选流程
- [ ] `P0` 只有通过 `validation_summary` 和人工抽查的 episode 才能标记为 `train_candidate`
- [ ] `P0` 批量采集时固定每轮采集的工具类别配比、输入模式配比和 reset 随机化范围
- [ ] `P0` 每次批量采集结束后冻结 session 配置、代码版本、schema 版本和相机标定版本
- [ ] `P1` 建立 train/val/test 划分规则，避免同一 reset seed 或高度相似轨迹同时进入训练和验证

### S5.6 语言描述与任务标签规则

- [ ] `P0` 为每类工具冻结中文/英文任务文本模板
- [ ] `P0` 每条 episode 的 `instruction_text` 必须明确当前要抓的工具，例如 `pick up the wrench and place it into the toolbox`
- [ ] `P0` 每条 step 样本必须能追溯到同一条 `instruction_text`
- [ ] `P0` `language.json` 中记录 `tool_class`、`tool_display_name`、`target_slot_id` 和模板版本
- [ ] `P0` 不允许只写泛化文本 `pick up the tool` 作为唯一标注，必须保留具体工具类别
- [ ] `P1` 可为同一任务保留多种自然语言改写，但第一版训练先使用模板化稳定文本

### 验收

- [ ] `P0` 你能从 Quest3 完成至少一条完整 episode 手动示教录制
- [ ] `P0` episode 文件结构完整可读
- [ ] `P0` episode 中包含可用的 `RGB-D` 观测
- [ ] `P0` episode 中的 `RGB-D` 观测确认来自 MuJoCo 末端 D405 相机
- [ ] `P0` episode 包含逐帧 `rgb/`、逐帧 `depth/`、`visuals.jsonl`，且 MP4 仅作为预览
- [ ] `P0` 每条 action 都能通过 `paired_frame_id` 对齐到有效视觉帧
- [ ] `P0` 录制数据可用于后续训练脚本读取
- [ ] `P0` 采集前置检查能阻止相机不可用、reset 非法或接触安全壳异常的正式录制
- [ ] `P0` 至少完成每类工具各 1 条试采 episode，且能人工回放检查
- [ ] `P0` `validation_summary.json` 能明确说明该 episode 是否可进入训练集
- [ ] `P0` 正式训练候选 episode 中不存在明显穿桌、穿箱、工具竖立或工具箱开口异常
- [ ] `P0` 每条训练候选 episode 都有具体工具文字描述

---

## 里程碑 S6：脚本化任务与抓取附着机制

### 目标

在训练之前，先做一个规则或脚本版本的工具抓取任务，把环境闭环验证通。

### S6.1 抓取与附着机制

- [ ] `P0` 定义什么叫“抓取成功”
- [ ] `P0` 定义什么叫“放置成功”
- [ ] `P0` 实现对象附着机制
- [ ] `P0` 实现对象释放机制
- [ ] `P0` 在状态广播中正确更新 `attached_to_gripper`
- [ ] `P1` 处理滑落、误抓和碰撞失败情况

### S6.2 脚本化任务运行器

- [ ] `P0` 新增 `backend/sim/task_runtime.py`
- [ ] `P0` 新增 `backend/tasks/tool_sorting_scripted.py`
- [ ] `P0` 实现脚本化流程：
- [ ] `P0` 阶段 1：回 home
- [ ] `P0` 阶段 2：接近目标工具
- [ ] `P0` 阶段 3：闭合夹爪
- [ ] `P0` 阶段 4：判定并附着
- [ ] `P0` 阶段 5：抬升
- [ ] `P0` 阶段 6：搬运到工具箱
- [ ] `P0` 阶段 7：释放
- [ ] `P0` 阶段 8：返回安全位并广播结果
- [ ] `P1` 支持任务停止、超时和回滚

### S6.3 前端任务入口

- [ ] `P0` `execute_task` 不再只改状态，而是真实驱动任务运行器
- [ ] `P0` 前端任务面板中的“识别工具 / 抓取工具 / 放置工具”改为真实任务入口
- [ ] `P0` 显示当前任务阶段
- [ ] `P0` 显示成功或失败结果
- [ ] `P1` 显示详细失败原因

### 验收

- [ ] `P0` 不依赖训练模型也能完成一条脚本化工具抓取任务
- [ ] `P0` 前端能实时看到工具被抓取、搬运、放置的完整过程
- [ ] `P0` `attached_to_gripper` 状态与实际画面一致

---

## 里程碑 S7：pi0.5 数据转换、模仿学习初训与 MuJoCo 验证

### 目标

把 Quest3 采集得到的 raw episode 转换为 `LeRobot / OpenPI` 可训练数据集，并在此基础上完成第一轮 `pi0.5` imitation learning / behavior cloning 初训。  
本阶段的核心验收不是追求最高成功率，而是跑通：

```text
raw 数据 -> 训练数据转换 -> pi0.5 fine-tune -> 模型入库 -> MuJoCo 推理验证
```

### S7.0 前置条件

- [ ] `P0` S5 数据采集闭环已完成，episode 可落盘、回放和生成 `validation_summary.json`
- [ ] `P0` S6 抓取附着、释放、成功判定和脚本化任务闭环已完成
- [ ] `P0` 至少每类工具有若干条 `train_candidate` episode
- [ ] `P0` 所有进入训练候选的数据满足 `camera_capture_ok=true`
- [ ] `P0` 所有进入训练候选的数据满足 `stub_frame_count=0`
- [ ] `P0` 所有进入训练候选的数据每条 action 都有 `paired_frame_id`
- [ ] `P0` 所有进入训练候选的数据都包含具体 `instruction_text`
- [ ] `P0` 明确第一版 pi0.5 训练不直接读取 raw JSONL，而先转换为 LeRobot / OpenPI 格式

### S7.1 raw -> LeRobot / OpenPI 数据转换

- [ ] `P0` 新增 `scripts/datasets/convert_quest3_to_lerobot.py`
- [ ] `P0` 新增 `scripts/datasets/validate_pi05_dataset.py`
- [ ] `P0` 新增 `scripts/datasets/split_quest3_dataset.py`
- [ ] `P0` 新增 `scripts/datasets/inspect_pi05_sample.py`
- [ ] `P0` 转换器支持读取 `data/datasets/quest3_tool_sorting_v1/raw/`
- [ ] `P0` 转换器只纳入 `validation_summary.can_be_train_candidate=true` 的 episode
- [ ] `P0` 转换器自动拒绝包含 stub/fallback 图像的 episode
- [ ] `P0` 转换器自动拒绝缺少 `paired_frame_id` 的 action 样本
- [ ] `P0` 转换器自动拒绝 RGB / Depth 时间对齐超过阈值的样本或 episode
- [ ] `P0` 转换器支持输出到 `data/datasets/quest3_tool_sorting_v1/processed/pi05_lerobot_v1/`
- [ ] `P0` 转换器生成 LeRobot / OpenPI 兼容的 `meta/`、`data/`、`videos/` 结构
- [ ] `P0` 转换器生成 `conversion_report.json`
- [ ] `P0` 转换器生成 `feature_mapping.json`
- [ ] `P0` 转换器生成 `rejected_episodes.jsonl`
- [ ] `P0` 转换器保留 raw episode 到 processed frame 的索引映射，便于追溯问题样本
- [ ] `P0` 转换器支持 `--policy-fps`，第一版默认 `10 Hz`
- [ ] `P0` 转换器支持 `--state-mode qpos_gripper`
- [ ] `P0` 转换器支持 `--action-mode joint_delta_gripper_abs`
- [ ] `P0` 转换器支持指定训练主视觉键 `observation.images.d405_rgb`
- [ ] `P1` 转换器可选保留 `observation.images.d405_depth`，但第一版不默认接入 pi0.5 主干

### S7.2 pi0.5 feature mapping 冻结

- [ ] `P0` 冻结第一版 `observation.images.d405_rgb` 来源为末端 D405 RGB 帧
- [ ] `P0` 冻结第一版 `observation.state = [q1,q2,q3,q4,q5,q6,gripper_opening]`
- [ ] `P0` 冻结第一版 `action = [delta_q1..delta_q6, gripper_target_opening]`
- [ ] `P0` 冻结第一版 `task/prompt = instruction_text`
- [ ] `P0` 明确 `objects` / `toolbox` 真值位姿只用于筛选、评估和 RL reward，不作为第一版 pi0.5 输入
- [ ] `P0` 明确第一版训练主输入使用 RGB，不强制使用 Depth
- [ ] `P0` 明确若使用 relative actions，关节为相对动作，夹爪保持绝对开合量
- [ ] `P0` 明确模型输出必须能转换为现有 `/sim/step/` 的 `target_positions + gripper_command`
- [ ] `P0` 明确策略推理频率、控制频率和 action chunk 语义
- [ ] `P0` 明确 action 限幅、平滑和安全检查规则

### S7.3 train / val / test 划分与统计

- [ ] `P0` 生成 episode 级 `train/val/test` 划分，禁止按帧随机打散
- [ ] `P0` 避免同一 `reset_seed` 同时进入 train 和 test
- [ ] `P0` 保证 wrench / screwdriver / pliers 在 split 中尽量均衡
- [ ] `P0` 生成数据集统计：episode 数、帧数、工具类别分布、成功/失败分布、输入模式分布
- [ ] `P0` 生成 action/state normalization stats
- [ ] `P0` 若所用训练框架要求 quantile stats，则生成或补齐 quantile stats
- [ ] `P0` 统计每个维度的 mean/std/min/max/q01/q99，检查异常小方差维度
- [ ] `P0` 生成 `dataset_snapshot.json`，记录 raw 数据版本、转换脚本版本、schema 版本和 git commit
- [ ] `P1` 支持导出数据集质量报告为 markdown 或 HTML

### S7.4 pi0.5 训练配置与脚本

- [ ] `P0` 新增 `configs/pi05/quest3_tool_sorting_v1_pi05.yaml`
- [ ] `P0` 新增 `configs/pi05/quest3_tool_sorting_v1_pi05_debug.yaml`
- [ ] `P0` 新增 `scripts/training/train_pi05.py`
- [ ] `P0` `train_pi05.py` 支持读取本项目 config 并调用 OpenPI 或 LeRobot 官方训练入口
- [ ] `P0` 训练 config 记录 base model、dataset root、split、feature mapping、normalization stats
- [ ] `P0` 训练 config 记录 `state_dim=7`、`action_dim=7`、`policy_fps=10`
- [ ] `P0` 训练 config 记录相机内参、外参和 mount 版本
- [ ] `P0` 训练 config 支持 `expert_only / lora / full_finetune` 或等效训练模式
- [ ] `P0` 第一版优先使用低成本微调方式，例如 expert-only、LoRA 或冻结部分 backbone
- [ ] `P0` 支持 checkpoint 保存、resume 和 best model 导出
- [ ] `P0` 训练日志写入 `logs/train/` 和模型 run 目录
- [ ] `P0` 训练失败时保留 config、stderr/stdout 和最后一个可用 checkpoint
- [ ] `P1` 支持 W&B、TensorBoard 或等效训练曲线可视化

### S7.5 模型入库

- [ ] `P0` 每次初训创建 `models/pi05/initial_runs/<run_id>/`
- [ ] `P0` run 目录包含 `config.json`
- [ ] `P0` run 目录包含 `feature_mapping.json`
- [ ] `P0` run 目录包含 `dataset_snapshot.json`
- [ ] `P0` run 目录包含 `normalization_stats.json`
- [ ] `P0` run 目录包含 `checkpoints/`
- [ ] `P0` run 目录包含 `exported/`
- [ ] `P0` run 目录包含 `logs/`
- [ ] `P0` run 目录包含 `offline_eval/`
- [ ] `P0` run 目录预留 `mujoco_validation/`
- [ ] `P0` 支持将初训模型写入 `models/registry/active_policy.json`，但默认不覆盖最终 active policy
- [ ] `P1` 支持导出统一部署格式，记录控制频率、动作定义、标定版本和 runtime target

### S7.6 离线评估

- [ ] `P0` 新增 `scripts/training/evaluate_pi05_offline.py`
- [ ] `P0` 离线评估输出 `val_action_mse`
- [ ] `P0` 离线评估输出 `joint_delta_mse`
- [ ] `P0` 离线评估输出 `gripper_mae`
- [ ] `P0` 离线评估输出 `action_smoothness`
- [ ] `P0` 离线评估输出按工具类别拆分的指标
- [ ] `P0` 离线评估保存误差最大的样本索引，能追溯回 raw episode
- [ ] `P0` 离线评估生成 `models/pi05/initial_runs/<run_id>/offline_eval/metrics.json`
- [ ] `P1` 离线评估生成动作曲线图和失败样本预览图

### S7.7 初训模型加载回 MuJoCo

- [ ] `P0` 新增 `backend/policies/policy_loader.py`
- [ ] `P0` 新增 `backend/policies/pi05_policy_adapter.py`
- [ ] `P0` 新增 `backend/policies/action_postprocess.py`
- [ ] `P0` policy adapter 能把后端状态转换为 pi0.5 inference 输入
- [ ] `P0` policy adapter 能把 D405 RGB 输入映射到 `observation.images.d405_rgb`
- [ ] `P0` policy adapter 能把任务文本映射到 `prompt`
- [ ] `P0` action postprocess 支持关节增量限幅
- [ ] `P0` action postprocess 支持夹爪命令限幅
- [ ] `P0` action postprocess 支持动作平滑
- [ ] `P0` action postprocess 支持安全检查失败时拒绝执行
- [ ] `P0` 新增 `scripts/training/evaluate_pi05_mujoco.py`
- [ ] `P0` MuJoCo 验证支持固定工具位置场景
- [ ] `P0` MuJoCo 验证支持随机工具位置场景
- [ ] `P0` MuJoCo 验证保存 `metrics.json`、`episodes.jsonl` 和可选视频

### S7 验收

- [ ] `P0` raw episode 已成功转换为 LeRobot / OpenPI 可训练数据集
- [ ] `P0` 转换后的样本包含 `observation.images.d405_rgb`、`observation.state`、`action`、`task/prompt`
- [ ] `P0` 训练前已生成 split 和 normalization stats
- [ ] `P0` 能基于转换后的数据集启动 pi0.5 训练
- [ ] `P0` 能得到可加载的初训模型权重
- [ ] `P0` 初训模型成功入库到 `models/pi05/initial_runs/<run_id>/`
- [ ] `P0` 初训模型能加载回 MuJoCo 并完成至少一次基础推理 rollout
- [ ] `P0` 离线评估和 MuJoCo 验证结果能追溯到数据集版本和训练配置

---

## 里程碑 S8：强化学习 residual 微调

### 目标

在 pi0.5 初训模型基础上，用强化学习提升随机场景下的抓取稳定性、放置精度和任务成功率。  
第一版不建议直接端到端微调整个 `pi0.5` 大模型，而是优先采用：

```text
final_action = pi0.5_action + residual_policy(observation)
```

也就是冻结或半冻结 pi0.5，让 RL 先学习低维动作修正。

### S8.0 RL 前置条件

- [ ] `P0` S6 抓取成功判定、放置成功判定、附着机制和释放机制已完成
- [ ] `P0` `grasp_state` 能稳定广播 `none/candidate/attached/released/failed`
- [ ] `P0` `tool_putaway_success` 能由程序判定
- [ ] `P0` `drop_failure`、`collision_failure`、`timeout` 能由程序记录
- [ ] `P0` pi0.5 初训模型已入库并能在 MuJoCo 中推理
- [ ] `P0` 已有 scripted baseline 和 pi0.5 IL baseline 可比较
- [ ] `P0` 未满足以上条件时，只允许做 RL env smoke test，不允许正式 RL 训练

### S8.1 RL 环境实现

- [ ] `P0` 新增 `backend/rl/envs/tool_sorting_env.py`
- [ ] `P0` 新增 `backend/rl/rewards/tool_sorting_reward.py`
- [ ] `P0` 新增 `backend/rl/curriculum/tool_sorting_curriculum.py`
- [ ] `P0` 新增 `backend/rl/policies/residual_policy.py`
- [ ] `P0` 环境接口采用 Gymnasium 风格 `reset()` / `step()`
- [ ] `P0` `reset()` 支持指定 `tool_class`、`seed`、随机化等级
- [ ] `P0` `step()` 返回 `obs, reward, terminated, truncated, info`
- [ ] `P0` `info` 包含 `grasp_state`、`attached_to_gripper`、`place_success`、`tool_putaway_success`
- [ ] `P0` `info` 包含 `collision_blocked`、`collision_objects`、`max_penetration_depth_m`
- [ ] `P0` `info` 包含 `drop_failure`、`timeout` 和 `reward_terms`
- [ ] `P0` 环境支持加载 pi0.5 初训模型作为 base policy
- [ ] `P0` 环境支持无 pi0.5 的 scripted / random smoke test

### S8.2 RL observation / action 冻结

- [ ] `P0` 定义 `policy_observation`，只包含未来实机可获得或可稳定估计的字段
- [ ] `P0` 定义 `privileged_info`，只用于 reward 和日志，不输入最终部署 policy
- [ ] `P0` 第一版 `policy_observation` 至少包含 `qpos[0:6]`、`gripper_opening`、`ee_pose`
- [ ] `P0` 第一版 `policy_observation` 包含当前 `pi0.5_action`
- [ ] `P0` 第一版 `policy_observation` 包含 action chunk phase 或 step phase
- [ ] `P0` 第一版 `policy_observation` 包含目标工具类别 one-hot 或 task id
- [ ] `P0` 第一版 `rl_action` 定义为 `residual_joint_delta + residual_gripper_delta`
- [ ] `P0` 冻结 `residual_joint_delta_limit`
- [ ] `P0` 冻结 `final_joint_delta_limit`
- [ ] `P0` 冻结 `residual_gripper_limit`
- [ ] `P0` 最终动作必须经过限幅、平滑和安全检查后才能进入 MuJoCo
- [ ] `P1` 评估加入 compact visual embedding，但不作为第一版 P0

### S8.3 reward 函数冻结

- [ ] `P0` 奖励函数拆成可记录的 `reward_terms`
- [ ] `P0` 实现接近目标工具奖励 `r_reach_tool`
- [ ] `P0` 实现抓取姿态对齐奖励 `r_pregrasp_align`
- [ ] `P0` 实现抓取成功奖励 `r_grasp_success`
- [ ] `P0` 实现抬升奖励 `r_lift`
- [ ] `P0` 实现搬运到工具箱奖励 `r_transport_to_toolbox`
- [ ] `P0` 实现放置成功奖励 `r_place_success`
- [ ] `P0` 实现完整任务成功奖励 `r_task_success`
- [ ] `P0` 实现碰撞/穿透惩罚 `p_collision`
- [ ] `P0` 实现掉落惩罚 `p_drop`
- [ ] `P0` 实现超时惩罚 `p_timeout`
- [ ] `P0` 实现动作幅值惩罚 `p_action_magnitude`
- [ ] `P0` 实现动作抖动惩罚 `p_action_jitter`
- [ ] `P0` 奖励权重写入 `reward_config.json`
- [ ] `P0` 每个 episode 保存 reward term 曲线，便于调试 reward hacking

### S8.4 curriculum 与随机化

- [ ] `P0` 实现 `rl_debug_fixed`：固定工具、固定工具箱
- [ ] `P0` 实现 `rl_easy_position`：工具 XY 小范围随机，yaw 固定
- [ ] `P0` 实现 `rl_medium_pose`：工具 XY + yaw 随机
- [ ] `P1` 实现 `rl_place_random`：工具箱目标区域小范围扰动
- [ ] `P1` 实现 `rl_sim2real_noise`：视觉噪声、状态噪声、延迟、摩擦和质量扰动
- [ ] `P0` 每个 curriculum 阶段保存 `randomization_config.json`
- [ ] `P0` 每个 curriculum 阶段保存成功率和失败分布
- [ ] `P0` 支持固定 held-out seeds 做验证，避免只在训练 seed 上提升

### S8.5 RL 训练脚本

- [ ] `P0` 新增 `configs/rl/tool_sorting_residual_ppo.yaml`
- [ ] `P0` 新增 `scripts/training/finetune_rl.py`
- [ ] `P0` 第一版实现 PPO residual policy 训练
- [ ] `P0` `finetune_rl.py` 支持传入 `--base-policy models/pi05/initial_runs/<run_id>`
- [ ] `P0` `finetune_rl.py` 支持传入 `--num-envs`
- [ ] `P0` `finetune_rl.py` 支持传入 `--total-steps`
- [ ] `P0` `finetune_rl.py` 支持 checkpoint 保存和 resume
- [ ] `P0` 训练日志写入 `logs/train/` 和 RL run 目录
- [ ] `P0` RL run 目录保存 `base_policy_ref.json`
- [ ] `P0` RL run 目录保存 `reward_config.json`
- [ ] `P0` RL run 目录保存 `randomization_config.json`
- [ ] `P0` RL run 目录保存 `checkpoints/`、`exported/`、`eval/`
- [ ] `P1` 评估 SAC residual policy，但不阻塞 P0

### S8.6 RL 评估与模型入库

- [ ] `P0` 新增 `scripts/training/evaluate_policy.py`
- [ ] `P0` 评估脚本支持 scripted baseline
- [ ] `P0` 评估脚本支持 pi0.5 IL baseline
- [ ] `P0` 评估脚本支持 pi0.5 + RL residual
- [ ] `P0` 使用相同 seeds 对三组策略做公平对比
- [ ] `P0` 输出 `tool_putaway_success_rate`
- [ ] `P0` 输出 `grasp_success_rate`
- [ ] `P0` 输出 `place_success_rate`
- [ ] `P0` 输出 `collision_failure_rate`
- [ ] `P0` 输出 `drop_failure_rate`
- [ ] `P0` 输出 `mean_duration_s`
- [ ] `P0` 输出 `jitter_score`
- [ ] `P0` 输出按工具类别统计的成功率
- [ ] `P0` RL 模型写入 `models/rl/finetune_runs/<run_id>/`
- [ ] `P0` RL 模型支持写入 `models/registry/active_policy.json`
- [ ] `P0` 如果 RL 没有提升，也必须输出失败分析和 reward 曲线，而不是只保存 checkpoint

### S8.7 MuJoCo 验证

- [ ] `P0` RL 模型支持加载回 MuJoCo 执行 rollout
- [ ] `P0` 验证固定场景不少于 20 episodes
- [ ] `P0` 验证 easy random 场景不少于 50 episodes
- [ ] `P1` 验证 medium random 场景不少于 100 episodes
- [ ] `P0` 验证结果写入 `models/rl/finetune_runs/<run_id>/mujoco_validation/metrics.json`
- [ ] `P0` 保存失败案例 episode 日志
- [ ] `P1` 保存验证视频和关键帧截图

### S8 验收

- [ ] `P0` `tool_sorting_env.py` 能完成 reset / step smoke test
- [ ] `P0` RL env 能加载 pi0.5 初训模型作为 base policy
- [ ] `P0` residual policy 能完成至少一轮训练并保存 checkpoint
- [ ] `P0` RL 模型成功入库到 `models/rl/finetune_runs/<run_id>/`
- [ ] `P0` RL 模型能加载回 MuJoCo 做 rollout
- [ ] `P0` RL 模型能与 scripted / pi0.5 IL baseline 做同 seed 对比
- [ ] `P0` 在随机工具位置下，RL 相比 pi0.5 IL 有可测提升，或明确输出未提升原因
- [ ] `P1` 如进行了 MuJoCo 视频验证，则验证结果已写入模型目录

---

## 里程碑 S9：视觉回放、观测增强与论文展示

### 目标

在 `S1.5` 已完成 D405 主链路接入的基础上，为后续视觉回放分析、数据增强和论文展示补齐增强能力。

### ToDo

- [ ] `P1` 实现用于调试和回放的 `RGB` 预览接口
- [ ] `P1` 实现用于调试和回放的 `Depth` 预览接口
- [ ] `P1` 对齐前端相机/观测面板与后端接口
- [ ] `P1` 评估是否记录训练视频或演示视频
- [ ] `P1` 评估是否保存伪彩深度图用于论文展示
- [ ] `P1` 评估是否把更多视觉增强观测纳入 `pi0.5` 或 RL 输入

### 验收

- [ ] `P1` 前端观测面板可稳定显示末端 `RGB` 与 `Depth`
- [ ] `P1` 数据集可选记录视频或关键帧

---

## 里程碑 S10：Sim2Real 就绪与实机迁移准备

### 目标

让最终的初训模型和 RL 模型不仅能在 MuJoCo 中运行，还具备迁移到真实 UR5 的接口基础、安全约束和部署元数据基础。

### ToDo

- [ ] `P0` 定义统一的 `runtime_target`，至少支持 `sim` 与未来的 `real_ur5`
- [ ] `P0` 规划 MuJoCo 执行端与真实机械臂执行端的统一高层动作接口
- [ ] `P0` 规划真实 UR5 + Robotiq 的控制适配层接口
- [ ] `P0` 统一仿真与实机的核心观测字段、关节顺序与夹爪语义
- [ ] `P0` 建立 `data/calibration/` 下的标定文件命名与版本规范
- [ ] `P0` 明确桌面、工具箱、工具、相机和机器人基坐标的标定来源
- [ ] `P0` 为模型注册表增加部署元数据：控制周期、标定版本、动作定义、是否可部署到实机
- [ ] `P0` 规划仿真 / 实机模式切换流程
- [ ] `P0` 规划实机安全机制：限速、急停、掉线保护、watchdog、异常 hold
- [ ] `P0` 规划实机推理与控制的频率约束
- [ ] `P1` 规划小范围实机 smoke test 流程
- [ ] `P1` 规划 sim2real 效果记录方式，例如仿真成功率与实机成功率差值

### 验收

- [ ] `P0` 文档层已经明确“同一模型目录可服务仿真验证与未来实机部署”
- [ ] `P0` `runtime_target`、标定版本、安全状态和部署元数据均有明确落点
- [ ] `P0` 实机接入时不需要推翻现有训练与模型加载主链路

---

## 里程碑 S11：论文实验与结果固化

### 目标

把系统从“能跑”推进到“可写论文、可复现实验”。

### ToDo

- [ ] `P0` 冻结实验版本号和配置文件
- [ ] `P0` 冻结训练集、验证集、测试集划分
- [ ] `P0` 记录成功率、时长、碰撞、掉落等指标
- [ ] `P0` 形成至少三组基线对比：脚本、IL、IL+RL
- [ ] `P1` 如进行了两阶段 MuJoCo 验证，则形成“初训模型 MuJoCo 验证”与“RL 模型 MuJoCo 验证”的对比材料
- [ ] `P0` 输出结果表格到 `experiments/paper/tables/`
- [ ] `P0` 输出关键截图和视频到 `experiments/paper/figures/`
- [ ] `P0` 记录失败案例
- [ ] `P1` 增加消融：手柄数据 vs 手势数据
- [ ] `P1` 增加消融：单工具 vs 多工具
- [ ] `P1` 整理 sim2real 设计约束与未来实机迁移讨论

### 验收

- [ ] `P0` 方法流程图、实验表格、结果图都可直接用于小论文
- [ ] `P0` 至少完成一轮完整复现实验记录

---

## 三、按开发先后顺序的周计划版本

这部分不是替代上面的详细里程碑，而是把任务按更容易执行的时间顺序重新展开。  
如果实际开发节奏更快或更慢，可以把“一周”理解为“一个阶段块”。

### 第 1 周：目标冻结与工具场景设计周

目标：

- 把“工具入库”作为最终实验目标冻结
- 冻结第一版对象范围
- 冻结共享配置结构

本周建议完成：

- [ ] `P0` 明确最终任务表述为“随机工具抓取并放入工具箱，完成工具入库”
- [x] `P0` 冻结 `wrench + screwdriver + pliers + toolbox` 第一版对象范围
- [ ] `P0` 明确每种工具的显示名、实例 ID、资产路径
- [x] `P0` 设计 `shared/tool_catalog.json`
- [ ] `P0` 设计工具箱槽位和桌面随机区域
- [ ] `P1` 先冻结一版仿真 / 实机统一动作与观测接口草案
- [ ] `P0` 区分 `D405` 主相机与 `camera / camera_base` 调试对象的角色边界

周验收：

- [ ] `P0` 工具入库目标描述不再和旧 battery 任务混淆
- [ ] `P0` 工具与工具箱的共享配置方案冻结

### 第 2 周：末端 D405 相机建模与安装定义周

目标：

- 把 `Intel RealSense D405` 冻结为主视觉传感器
- 先完成安装方式、挂载姿态和资产用途的文档冻结

本周建议完成：

- [ ] `P0` 确认 `d405.stl + 前半.STL + 后半.STL` 的资产角色
- [ ] `P0` 根据 `pic/camera.jpg` 冻结末端安装方式
- [ ] `P0` 明确 D405 相对 `tool0` 或 `wrist_3_link` 的挂载坐标系
- [ ] `P0` 明确 `camera / camera_base` 只保留为调试对象
- [ ] `P0` 冻结 `camera_device`、`camera_mount_name`、`camera_intrinsics_version`、`camera_extrinsics_version` 命名
- [ ] `P1` 冻结一版 D405 近距离抓取视场假设与工作距离说明

周验收：

- [ ] `P0` 文档层已经明确 D405 是唯一主采集相机
- [ ] `P0` 文档层已经明确真实安装参考和仿真挂载依据

### 第 3 周：末端 RGB-D 观测与录制字段冻结周

目标：

- 在 Quest3 之前先把 `RGB-D` 观测链和录制字段写清楚

本周建议完成：

- [ ] `P0` 明确仿真中 `RGB` 输出接口
- [ ] `P0` 明确仿真中 `Depth` 输出接口
- [ ] `P0` 冻结 `RGB`、`Depth`、状态、动作、文本的时间对齐规则
- [ ] `P0` 冻结 `metadata.json`、`language.json`、`states.jsonl`、`actions.jsonl`、`result.json` 的核心字段
- [ ] `P0` 明确 `Depth` 使用无损格式
- [ ] `P0` 明确动作与视觉帧 ID 的对应关系

周验收：

- [ ] `P0` 数据集定义已经能支撑 `pi0.5` 所需的 `RGB-D + 状态 + 文本 + 动作`
- [ ] `P0` Quest3 开发不再阻塞于相机字段不明确

### 第 4 周：Quest3 局域网接入与 VR 模式入口周

目标：

- 让 Quest3 通过局域网稳定打开前端
- 完成 `VR模式` 入口与模式菜单

本周建议完成：

- [ ] `P0` 前端支持局域网访问
- [ ] `P0` 页面显示主机 IP、前端地址、后端地址和 WebSocket 地址
- [ ] `P0` Quest3 端接入后检测后端 `health`、`WebSocket` 和相机观测链状态
- [ ] `P0` 固定控制启动顺序：访问页面 -> 检查相机链 -> 连接机器人 -> 点击 `VR模式` -> 选择模式 -> 开始控制
- [ ] `P0` 将底部 `状态同步` 入口升级为 `VR模式`
- [ ] `P0` 完成不遮挡现有界面的模式菜单
- [ ] `P1` 预留 `runtime_target=sim` 的前后端状态字段

周验收：

- [ ] `P0` Quest3 可通过局域网进入页面
- [ ] `P0` Quest3 端可看到并使用 `VR模式` 菜单
- [ ] `P0` 底部导航栏预留 `采集` 入口位置，且不挤占 `VR模式` 的主控制入口

### 第 5 周：Quest3 手柄控制周

目标：

- 打通 Quest3 手柄到 UR5 控制的完整链路

本周建议完成：

- [ ] `P0` 读取 Quest3 手柄原始输入
- [ ] `P0` 完成输入归一化
- [ ] `P0` 完成关节组映射
- [ ] `P0` 实现夹爪连续控制
- [ ] `P0` 控制消息写入 `input_source=quest3_controller`
- [ ] `P0` 前后端状态回传无明显回弹
- [ ] `P1` 记录手柄原始输入值

周验收：

- [ ] `P0` Quest3 手柄可稳定控制机械臂与夹爪
- [ ] `P0` 手柄模式控制可进入录制链路

### 第 6 周：VR 接触稳定、安全壳与 reset 合法性周

目标：

- 在正式采集前解决明显穿模、干涉和 reset 姿态不可信问题
- 建立 `debug_trial` 级试采前置闸门

本周建议完成：

- [ ] `P0` 明确 VR 控制阶段不是完整真实力控抓取，先按安全壳方案推进
- [ ] `P0` 对 Quest3 控制命令增加关节目标限幅、速度限制和单步最大增量约束
- [ ] `P0` 对候选动作做碰撞/穿透前向检查，非法动作拒绝、缩步或 safe hold
- [ ] `P0` 区分允许接触和禁止接触，允许指尖接触目标工具，禁止穿桌、穿箱、穿工具
- [ ] `P0` 状态广播增加 `safety_status`、碰撞拦截原因和 `grasp_state`
- [ ] `P0` reset 后检查工具平躺、工具箱开口朝上、对象不穿透且在工作区内
- [ ] `P0` 至少连续 10 次 reset 均通过姿态和碰撞合法性检查
- [ ] `P0` 规划第一版半物理抓取：抓取判定、临时附着、释放校验
- [ ] `P1` 若继续推进手势模式，先作为调试输入源，不直接进入正式采集主数据

周验收：

- [ ] `P0` Quest3 控制机械臂靠近桌面、工具和工具箱时不会明显穿模
- [ ] `P0` reset 后工具和工具箱姿态符合真实桌面场景
- [ ] `P0` 系统能清楚标记 `normal / collision_blocked / safe_hold` 等安全状态

### 第 7 周：录制器、回放与 pilot 试采周

目标：

- 建立人工示教录制器
- 完成 `debug_trial -> pilot -> train_candidate` 的采集分级
- 先试采，不直接批量进入正式训练集

本周建议完成：

- [ ] `P0` 创建 session / episode 录制链路
- [ ] `P0` 实现 `/dataset/status/`、`/dataset/precheck/`、`/dataset/episode/start/`、`/dataset/episode/stop/` 的最小接口
- [ ] `P0` 实现 episode 生命周期状态机，覆盖 `recording/finalizing/completed/aborted`
- [ ] `P0` 录制器保存 `RGB`、`Depth`、状态、动作、任务文本
- [ ] `P0` 录制器保存当前输入模式、关节组、控制来源和原始输入
- [ ] `P0` 录制器保存 `safety_status`、`contact_state`、`grasp_state` 和 reset 元数据
- [ ] `P0` 底部导航栏的 `采集` 入口可打开采集面板，并支持状态机显示、开始、停止和录制状态查看
- [ ] `P0` 采集面板显示前置检查、episode 配置、实时计数和结束摘要
- [ ] `P0` 录制结束时检查 `RGB-D` 对齐完整性
- [ ] `P0` 录制结束时生成 `validation_summary.json`
- [ ] `P0` 支持回放 RGB、Depth、状态、动作和接触/安全时间轴
- [ ] `P0` 每类工具至少完成 1 条 `debug_trial` 或 `pilot` 试采
- [ ] `P0` 每条试采都带有具体工具文字描述
- [ ] `P0` 异常中断时保留 `aborted` episode 和 `partial_summary.json`
- [ ] `P1` 支持导出 MP4 预览视频和伪彩深度图

周验收：

- [ ] `P0` 你能完成至少一条有效手动示教试采
- [ ] `P0` 录制结果可回放、可检查，且包含完整 `RGB-D`
- [ ] `P0` `validation_summary.json` 能判断 episode 是否可成为训练候选
- [ ] `P0` 底部 `采集` 入口在 `idle/ready/debug_only/recording/finalizing/error` 状态下表现正确

### 第 8 周：脚本化任务与环境闭环周

目标：

- 在已切换完成的工具场景基础上推进脚本化任务闭环
- 先用脚本化任务验证工具入库闭环

本周建议完成：

- [x] `P0` 前后端完成 `tools + toolbox` 替换
- [x] `P0` 后端支持多工具对象状态广播
- [ ] `P0` 完成抓取成功判定与附着机制
- [ ] `P0` 完成脚本化任务 `quest3_tool_sorting_v1`
- [ ] `P0` 前端任务入口真实驱动脚本任务

周验收：

- [ ] `P0` 不依赖训练模型也能完成一次工具入库演示

### 第 9 周：pi0.5 数据转换、初训与模型入库周

目标：

- 将 Quest3 raw episode 转换为 LeRobot / OpenPI 可训练数据集
- 用转换后的数据完成第一轮 pi0.5 初训
- 让初训模型进入标准模型目录，并支持 MuJoCo 基础推理验证

本周建议完成：

- [ ] `P0` 完成 `scripts/datasets/convert_quest3_to_lerobot.py`
- [ ] `P0` 完成 `scripts/datasets/validate_pi05_dataset.py`
- [ ] `P0` 完成 raw episode 到 `processed/pi05_lerobot_v1/` 的转换
- [ ] `P0` 生成 `feature_mapping.json`，冻结 `observation.images.d405_rgb`、`observation.state`、`action`、`task/prompt`
- [ ] `P0` 冻结第一版 `observation.state=[qpos[0:6], gripper_opening]`
- [ ] `P0` 冻结第一版 `action=[joint_delta[0:6], gripper_target_opening]`
- [ ] `P0` 完成 episode 级 `train/val/test` 划分，禁止按帧随机打散
- [ ] `P0` 生成 action/state normalization stats
- [ ] `P0` 生成 `conversion_report.json` 和 `rejected_episodes.jsonl`
- [ ] `P0` 完成 `configs/pi05/quest3_tool_sorting_v1_pi05.yaml`
- [ ] `P0` 完成 `scripts/training/train_pi05.py`
- [ ] `P0` 用转换后的 LeRobot / OpenPI 数据集启动 pi0.5 初训
- [ ] `P0` 生成 checkpoint、best model 和 exported policy
- [ ] `P0` 将初训模型写入 `models/pi05/initial_runs/<run_id>/`
- [ ] `P0` 完成 `scripts/training/evaluate_pi05_offline.py`
- [ ] `P0` 完成 `backend/policies/policy_loader.py`、`pi05_policy_adapter.py` 和 `action_postprocess.py` 的最小版本
- [ ] `P0` 完成 `scripts/training/evaluate_pi05_mujoco.py` 的最小版本
- [ ] `P1` 为初训模型补齐统一部署格式与部署元数据
- [ ] `P1` 如需要，执行一次 MuJoCo 仿真验证并保存视频

周验收：

- [ ] `P0` raw 数据已成功转换为 LeRobot / OpenPI 可训练格式
- [ ] `P0` 转换后的样本包含 `observation.images.d405_rgb`、`observation.state`、`action`、`task/prompt`
- [ ] `P0` 初训模型成功入库
- [ ] `P0` 初训模型支持被加载到 MuJoCo 中完成至少一次基础 rollout
- [ ] `P0` 初训 run 能追溯到数据集版本、转换配置、训练配置和 git commit

### 第 10 周：强化学习 residual 微调周

目标：

- 搭建可复现的 RL 环境、reward、curriculum 和评估脚本
- 在 pi0.5 初训模型基础上训练 residual policy
- 对比 scripted baseline、pi0.5 IL baseline 和 pi0.5 + RL residual

本周建议完成：

- [ ] `P0` 完成 `backend/rl/envs/tool_sorting_env.py`
- [ ] `P0` 完成 `backend/rl/rewards/tool_sorting_reward.py`
- [ ] `P0` 完成 `backend/rl/curriculum/tool_sorting_curriculum.py`
- [ ] `P0` 完成 `backend/rl/policies/residual_policy.py`
- [ ] `P0` 环境支持加载 pi0.5 初训模型作为 base policy
- [ ] `P0` 冻结 RL `policy_observation`、`privileged_info` 和 residual action 语义
- [ ] `P0` 冻结 `final_action = pi0.5_action + residual_action`
- [ ] `P0` 冻结 reward terms 和 `reward_config.json`
- [ ] `P0` 实现 `rl_debug_fixed` 和 `rl_easy_position` curriculum
- [ ] `P0` 完成 `configs/rl/tool_sorting_residual_ppo.yaml`
- [ ] `P0` 完成 `scripts/training/finetune_rl.py`
- [ ] `P0` 第一版完成 PPO residual policy 训练闭环
- [ ] `P0` 将 RL 模型写入 `models/rl/finetune_runs/<run_id>/`
- [ ] `P0` 完成 `scripts/training/evaluate_policy.py`
- [ ] `P0` 使用相同 seeds 对 scripted、pi0.5 IL、pi0.5 + RL residual 做对比
- [ ] `P0` RL 评估输出成功率、抓取率、放置率、碰撞失败率、掉落失败率和 jitter score
- [ ] `P0` 如果 RL 未提升，输出失败分析和 reward 曲线
- [ ] `P1` 在 RL 中加入 sim2real 导向随机化
- [ ] `P1` 如需要，执行一次 RL 模型的 MuJoCo 视频验证

周验收：

- [ ] `P0` RL env 能完成 reset / step smoke test
- [ ] `P0` residual policy 能完成至少一轮训练并保存 checkpoint
- [ ] `P0` RL 微调模型成功入库
- [ ] `P0` RL 模型支持被加载到 MuJoCo 中查看
- [ ] `P0` RL 模型能与 scripted / pi0.5 IL baseline 做同 seed 对比

### 第 11 周：Sim2Real 与论文固化周

目标：

- 在仿真主链路跑通后，集中补齐真实 UR5 接入约束并生成论文材料

本周建议完成：

- [ ] `P0` 明确 `runtime_target`、`control_backend`、`safety_status` 等运行态字段
- [ ] `P0` 冻结仿真 / 实机统一动作接口与核心观测接口
- [ ] `P0` 冻结 `data/calibration/` 标定目录与版本规范
- [ ] `P0` 明确模型注册表中的部署元数据字段
- [ ] `P0` 明确实机安全机制：限速、急停、掉线保护、watchdog
- [ ] `P0` 固定数据集版本、模型版本和配置文件
- [ ] `P0` 记录脚本、初训、RL 三组实验结果
- [ ] `P0` 输出图表到 `experiments/paper/`
- [ ] `P1` 整理失败案例、视觉对齐问题和消融记录

周验收：

- [ ] `P0` sim2real 约束已进入字段、目录和接口设计
- [ ] `P0` 论文方法、实验设置和结果材料基本齐备

---

## 四、当前最优先的主链路任务

为了避免任务过散，建议下一轮实际开发优先盯住下面这一组主链路任务：

- [x] `P0` 冻结 `wrench + screwdriver + pliers + toolbox` 第一版对象范围
- [x] `P0` 设计 `shared/tool_catalog.json`
- [ ] `P0` 冻结 `Intel RealSense D405` 为唯一主采集相机
- [ ] `P0` 根据 `pic/camera.jpg` 冻结末端安装参考
- [ ] `P0` 冻结 `d405.stl + 前半.STL + 后半.STL` 的资产角色
- [ ] `P0` 冻结 `RGB-D + 状态 + 动作 + 文本` 数据集结构
- [ ] `P0` 设计 `VR模式` 按钮与 Quest3 菜单布局
- [ ] `P0` 设计底部导航栏 `采集` 入口与二级采集面板，避免与 `VR模式`、`reset` 和手动控制按钮误触
- [ ] `P0` 设计 Quest3 局域网接入后的控制启动顺序
- [ ] `P0` 明确手柄模式的完整按键映射
- [ ] `P0` 明确手势模式的最小可行交互方案
- [x] `P0` 前后端把 `battery_pack` 逻辑替换为 `tools + toolbox`
- [x] `P0` 实现多工具对象状态同步
- [ ] `P0` 建立 VR 运动安全壳，阻止明显穿桌、穿箱、穿工具
- [ ] `P0` 完成 reset 合法性检查，确保工具平躺、工具箱开口朝上且对象不穿透
- [ ] `P0` 明确正式采集前置检查，不通过时只能进入 `debug_trial`
- [ ] `P0` 生成并使用 `validation_summary.json` 筛选训练候选 episode
- [ ] `P0` 每条数据记录具体工具文字描述，不能只写泛化 `tool`
- [ ] `P0` 实现抓取成功判定与附着机制
- [ ] `P0` 实现脚本化 `quest3_tool_sorting_v1`
- [ ] `P0` 打通 Quest3 数据采集闭环
- [ ] `P0` 完成初训模型入库，并支持可选 MuJoCo 验证
- [ ] `P0` 在此基础上再进入 RL 微调
- [ ] `P0` 完成 RL 模型入库，并支持可选 MuJoCo 验证
- [ ] `P0` 冻结仿真 / 实机统一动作与观测接口
- [ ] `P0` 提前规划标定、watchdog 和实机部署元数据

---

## 五、补充提醒

- 当前代码中最容易“看起来像完成了、其实没完成”的部分，是 `execute_task` 和 `control.vue` 的工具操作区，它们现在更多还是演示入口，不是真正任务系统。
- 当前最不建议的路线，是在末端 D405、`RGB-D` 数据格式、VR 接触安全壳、reset 合法性、Quest3 录制链和脚本化任务都没稳定前，直接开始 RL。
- 当前最需要文档里反复强调的顺序，是“先 D405 -> 再 `RGB-D` 数据格式 -> 再 VR 接触安全壳与 reset 合法性 -> 再 `debug_trial/pilot` 试采 -> 再 Quest3 正式人工采集 -> 初训模型入库 -> 可选 MuJoCo 验证 -> RL 微调 -> RL 模型入库 -> 可选 MuJoCo 再验证 -> 预留实机部署入口”。
- 当前正式采集的底线，是相机不能用 stub 图像、reset 不能出现工具竖立或工具箱开口异常、VR 控制不能有明显穿模、每条 episode 必须有具体工具文字描述和完整 `validation_summary`。
- 当前最值得保留的资产，是主分支已经存在的前后端同步链路和 MuJoCo viewer 桥接逻辑，后续 Quest3 输入桥接可以尽量复用这套思路。
