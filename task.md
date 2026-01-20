# 🤖 Vue-Robot 项目 AI 编程任务清单

## 📋 任务总览
这是一个将 Vue-Robot 项目从 URDF 可视化升级到 MuJoCo 实时仿真，并在此基础上实现 AI 增强功能的完整开发任务。任务分为 5 个阶段 + AI 增强模块，共 28 个具体任务。

**项目目标**: 建立完整的智能机器人仿真系统，支持实时控制、状态反馈、相机渲染、多模态感知和 AI 决策

**技术栈**: MuJoCo + FastAPI + Vue.js + WebSocket + AI 模型（可选）

---

## 🏗️ 阶段一：环境准备与项目初始化
> **目标**: 确保开发环境就绪，MuJoCo 正常运行

### 任务 1.1：验证 MuJoCo 环境安装
**描述**: 检查 MuJoCo 是否正确安装并可正常运行
**步骤**:
1. 在 Python 环境中运行 `import mujoco; print(mujoco.__version__)`
2. 测试基础功能：`python -c "import mujoco; model = mujoco.MjModel.from_xml_string('<mujoco><worldbody/></mujoco>'); print('MuJoCo 环境正常')"`
3.环境是在conda环境中：conda activate vue-robot-mujoco
**验收标准**: 无错误输出，版本信息正确显示
**预计时间**: 30分钟

---

## 📦 阶段二：模型准备（MJCF 转换）
> **目标**: 将所有 URDF 模型转换为 MuJoCo MJCF 格式
> **前置条件**: 阶段一完成，MuJoCo 运行正常

### 任务 2.1：创建 MuJoCo 模型目录结构
**描述**: 建立模型文件组织结构
**步骤**:
1. 创建 `fastapi/mujoco_models/` 目录
2. 创建 `fastapi/mujoco_models/meshes/` 子目录
3. 添加 `.gitkeep` 文件防止空目录被忽略
**验收标准**: 目录结构创建完成，可通过 `ls fastapi/mujoco_models/` 确认
**预计时间**: 15分钟

### 任务 2.2：分析 UR5 URDF 文件结构
**描述**: 深入了解 UR5 机器人的关节定义和网格引用
**步骤**:
1. 查看 URDF 文件：`cat public/ur5/ur5.urdf | head -50`
2. 分析关节层级关系和坐标系定义
3. 记录所有 mesh 文件路径和关节参数
**验收标准**: 生成 UR5 结构分析文档
**预计时间**: 1小时

### 任务 2.3：创建 UR5 MJCF 模型文件
**描述**: 将 UR5 URDF 转换为 MJCF 格式
**AI 编程任务**: 生成完整的 `fastapi/mujoco_models/ur5.xml` 文件
**要求**:
- 包含 6 个关节：shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3
- 添加 position 执行器和关节传感器
- 正确引用 mesh 文件路径
- 确保坐标系一致性
**验收标准**: `python -c "import mujoco; mujoco.MjModel.from_xml_path('fastapi/mujoco_models/ur5.xml')"` 无错误
**预计时间**: 4-6小时

### 任务 2.4：创建静态环境模型
**描述**: 转换 battery、rack、camera_base 为 MJCF 格式
**AI 编程任务**: 生成三个 MJCF 文件
**步骤**:
1. 创建 `battery.xml` - 电池模型
2. 创建 `rack.xml` - 货架模型
3. 创建 `camera_base.xml` - 相机底座模型
4. 复制所有 mesh 文件到 `mujoco_models/meshes/`
**验收标准**: 所有静态模型可正确加载，无几何冲突
**预计时间**: 3-4小时

### 任务 2.5：创建环境集成文件
**描述**: 将所有环境组件集成到一个场景中
**AI 编程任务**: 生成 `fastapi/mujoco_models/environment.xml`
**要求**:
- 包含 UR5 机器人和所有静态环境
- 设置合适的初始位置和姿态
- 确保坐标系对齐
**验收标准**: 完整场景加载成功，无碰撞冲突
**预计时间**: 1-2小时

---

## 🤖 基于 MuJoCo 仿真的 AI 增强功能模块
> **说明**: 下列任务基于阶段三的 MuJoCo 仿真控制核心，实现"Environment Sensing / Multimodal Decision / Decision Generation / Embodiment"流程的高级 AI 功能。这些模块利用仿真环境中的传感器数据（相机渲染、关节力矩、接触信息）构建智能机器人控制系统。
>
> **前置条件**: 必须先完成阶段三（MuJoCo 仿真核心实现），这些 AI 模块将调用 `simulation.py` 中的接口进行数据采集和控制执行。
> **前置条件**: 必须先完成阶段三（MuJoCo 仿真核心实现），这些 AI 模块将调用 `simulation.py` 中的接口进行数据采集和控制执行。

> **过程改进原则**: 所有流程改进与优化必须以仿真控制模块（`simulation.py`）为基础进行验证与迭代。任何新的控制策略、感知流程或决策逻辑在部署到真实机器人或集成环境前，应先在 MuJoCo 仿真中完成以下验证流程：
>
- 在 `simulation.py` 中完成接口对接与回放验证（包括 `render_camera()`、关节力矩、接触事件等传感器数据）；
- 在仿真场景中复现目标任务并量化性能指标（位置误差、姿态误差、执行成功率、异常触发率等）；
- 执行安全边界与异常场景测试（关节角度/速度/力矩限制、紧急停止条件），并将测试用例纳入持续集成回归测试。
>
该原则确保改进的可重复性、安全性和可测量性，使仿真验证结果成为后续真实部署的重要依据。

### M1：环境感知（Environment Sensing）- 基于 MuJoCo 传感器
**AI 编程任务**: 在 `fastapi/` 中实现 `env_sensing.py`，利用 MuJoCo 仿真环境进行环境感知
**内容与步骤**:
1. 数据采集接口：调用 `simulation.py` 的 `render_camera()` 接口和传感器数据（关节力矩 `qfrc_constraint`、接触信息 `contact`）读取数据。
2. 主动过滤：在仿真环境中实现基于任务的 ROI 选择器，决定上报的关键传感器数据（例如：只监控特定关节的力矩变化）。
3. 预处理与特征提取：对仿真传感器数据进行滤波和阈值判断，提取关键特征用于后续决策。
**验收标准**: 提供 `GET /sim/sense/status` 接口，返回 MuJoCo 仿真环境中的传感器数据摘要（渲染图像 / 力矩异常标记）。
**预计时间**: 4-6 小时

### M2：视觉模型与检测流水线 - 基于仿真相机
**AI 编程任务**: 实现 `vision.py`，处理 MuJoCo 仿真渲染的相机图像
**内容与步骤**:
1. 接入开源检测器（YOLO、Detectron2），处理 `simulation.py` 提供的仿真相机图像。
2. 实现局部 ROI 检测，对仿真环境中渲染的物体进行目标识别。
3. 返回结构化结果：基于仿真数据的物体位置、可抓取区域、工具状态评估。
**验收标准**: 对仿真渲染的图像能正确识别和定位物体（bounding box 与标签）。
**预计时间**: 6-10 小时

### M3：力学/触觉数据处理 - 基于 MuJoCo 物理仿真
**AI 编程任务**: 实现 `tactile.py`，处理 MuJoCo 仿真中的力学和触觉传感器数据
**步骤**:
1. 从 `simulation.py` 获取关节力矩 `qfrc_constraint` 和接触力 `contact` 数据。
2. 实现基于仿真物理数据的滤波器和异常检测（卡住、碰撞等事件）。
3. 设计事件化接口，输出仿真环境中的物理事件（如 `{"type":"force_event","severity":"high","desc":"关节力矩超限"}`）。
**验收标准**: 在 MuJoCo 仿真中能正确检测物理异常事件并记录时间戳。
**预计时间**: 3-5 小时

### M4：文本理解与人机交互（Text Understanding）
**AI 编程任务**: 实现 `nlp.py`，解析操作指令并映射到仿真控制参数
**步骤**:
1. 支持自然语言指令解析，将文本命令转换为仿真控制参数。
2. 将指令映射到 MuJoCo 控制接口（关节目标位置、控制增益等）。
**验收标准**: 对指令文本能正确转换为仿真执行参数。
**预计时间**: 3-4 小时

### M5：多模态决策（Multimodal Decision）- 融合仿真数据
**AI 编程任务**: 实现 `decision_fusion.py`，融合 MuJoCo 仿真中的多模态数据
**步骤**:
1. 定义统一状态向量（仿真相机图像 + 关节传感器数据 + 文本指令）。
2. 实现决策融合器，基于仿真环境状态生成控制决策。
3. 提供 `decide()` 接口，返回仿真控制命令序列。
**验收标准**: 基于 MuJoCo 仿真数据生成合理的控制决策。
**预计时间**: 6-10 小时

### M6：决策执行与仿真控制（Decision Generation → Embodiment）
**AI 编程任务**: 将决策映射为 MuJoCo 仿真控制命令并执行
**步骤**:
1. 设计决策到仿真控制的映射表（决策 → `target_positions`、`n_steps`）。
2. 在 `simulation.py` 中实现 `apply_decision()` 方法，调用仿真步进接口。
3. 支持决策执行流程，实时监控仿真状态变化。
**验收标准**: 决策能在 MuJoCo 仿真环境中正确执行并产生预期状态变化。
**预计时间**: 4-6 小时

### M7：主动交互与反馈回路 - 基于仿真监控
**AI 编程任务**: 实现 `proactive.py`，基于仿真状态进行主动交互
**步骤**:
1. 基于仿真执行结果的置信度评估触发额外的数据采集。
2. 在仿真环境中模拟不确定性场景，触发人工确认流程。
3. 记录仿真交互历史用于系统优化。
**验收标准**: 在 MuJoCo 仿真中能正确处理不确定性和异常情况。
**预计时间**: 4-6 小时

### M8：端到端集成与仿真测试
**AI 编程任务**: 将所有 AI 模块与 MuJoCo 仿真核心集成，提供完整测试
**步骤**:
1. 定义基于仿真环境的完整消息协议和接口。
2. 在 `main.py` 中集成所有模块，提供统一的仿真控制 API。
3. 编写仿真环境下的端到端测试，验证 AI 决策到物理执行的完整链路。
**验收标准**: 在 MuJoCo 仿真环境中实现完整的 AI 增强机器人控制流程。
**预计时间**: 8-12 小时

---

请确认是否按上述模块化清单来完善 `task.md`（我已将这些项写入文档），或告诉我你想调整的优先级/合并方案。确认后我将继续把每个模块拆成更细的代码任务并生成对应代码骨架。 

## 🔧 阶段三：后端仿真核心实现
> **目标**: 实现完整的仿真后端服务
> **前置条件**: 阶段二完成，所有 MJCF 模型文件就绪

### 任务 3.1：创建 Simulation 类基础结构
**AI 编程任务**: 生成 `fastapi/simulation.py` 基础框架
**要求**:
- 导入必要的模块（mujoco, numpy, asyncio 等）
- 定义 SimState 数据类
- 创建 Simulation 类骨架（__init__, load_model, step_simulation 等方法声明）
- 实现线程安全机制
**验收标准**: 文件可导入无语法错误，类结构完整
**预计时间**: 1小时

### 任务 3.2：实现模型加载功能
**AI 编程任务**: 完善 `load_model()` 方法
**要求**:
- 支持加载 ur5.xml 和 environment.xml
- 初始化 MjModel 和 MjData 对象
- 完善的错误处理和异常管理
- 支持模型切换
**验收标准**: 模型成功加载，打印正确的关节和执行器数量
**预计时间**: 1-2小时

### 任务 3.3：实现仿真步进和控制逻辑
**AI 编程任务**: 实现 `step_simulation()` 方法
**要求**:
- PD 位置控制器实现
- 支持多步前进 (n_steps 参数)
- 状态更新和时间戳管理
- 关节角度限制处理
**验收标准**: 关节角度控制响应正常，可达到目标位置
**预计时间**: 3-4小时

### 任务 3.4：实现 REST API 接口
**AI 编程任务**: 在 `fastapi/main.py` 中添加 REST 端点
**要求**:
- `POST /sim/reset/` - 重置仿真状态
- `POST /sim/step/` - 执行控制步进
- `GET /sim/state/` - 获取当前状态
- JSON 请求响应处理
**验收标准**: 所有接口返回正确响应，数据格式符合规范
**预计时间**: 2-3小时

### 任务 3.5：实现 WebSocket 实时通信
**AI 编程任务**: 添加 WebSocket 端点 `/sim/ws`
**要求**:
- 50-100Hz 状态推送
- 控制命令接收和处理
- 连接管理和错误处理
- 支持多客户端连接
**验收标准**: WebSocket 连接稳定，实时数据传输正常
**预计时间**: 3-4小时

### 任务 3.6：实现相机渲染功能
**AI 编程任务**: 添加 `render_camera()` 方法
**要求**:
- offscreen 渲染器配置
- 支持多种分辨率 (320x240, 640x480)
- JPEG/PNG 格式输出
- 渲染性能优化
**验收标准**: 生成有效的图像数据，无渲染错误
**预计时间**: 2-3小时

### 任务 3.7：实现相机图像服务接口
**AI 编程任务**: 添加 `/sim/camera.jpg` 端点
**要求**:
- 支持 base64 和二进制格式
- 图像压缩和质量控制
- 缓存机制优化性能
**验收标准**: 接口返回有效图像数据，支持不同格式
**预计时间**: 1-2小时

### 任务 3.8：添加并发安全机制
**AI 编程任务**: 完善线程安全和并发处理
**要求**:
- 线程锁保护共享状态
- 请求队列机制
- 多客户端并发访问支持
- 死锁预防
**验收标准**: 并发访问无数据竞争，性能稳定
**预计时间**: 2-3小时

---

## 🌐 阶段四：前端实时集成
> **目标**: 将前端从轮询升级到 WebSocket 实时通信
> **前置条件**: 阶段三完成，后端服务正常运行

### 任务 4.1：分析当前前端实现
**描述**: 查看现有的轮询机制和状态管理
**步骤**:
1. 读取 `src/App.vue` 了解当前实现
2. 查看 `src/components/control.vue` 和 `robot.vue`
3. 记录需要修改的接口和数据流
**验收标准**: 完成前端代码结构分析
**预计时间**: 1小时

### 任务 4.2：实现 WebSocket 客户端连接
**AI 编程任务**: 修改 `src/App.vue` 实现 WebSocket 连接
**要求**:
- 替换原有轮询机制
- 实现自动重连逻辑
- 添加连接状态显示
- 处理消息解析和状态更新
**验收标准**: WebSocket 连接稳定，状态更新频率达到 50Hz
**预计时间**: 2-3小时

### 任务 4.3：更新控制命令发送机制
**AI 编程任务**: 修改控制组件实现 WebSocket 命令发送
**要求**:
- 更新"发送到机器人"按钮逻辑
- 实现命令确认机制
- 添加发送状态反馈
- 错误处理优化
**验收标准**: 控制命令正确发送并执行
**预计时间**: 2-3小时

### 任务 4.4：集成相机图像显示
**AI 编程任务**: 创建相机显示组件
**要求**:
- 实现图像数据接收（WebSocket 或 HTTP）
- 添加图像更新机制
- 帧率控制和性能优化
- 错误处理和加载状态
**验收标准**: 相机图像实时显示，性能流畅
**预计时间**: 2-3小时

### 任务 4.5：完善状态同步机制
**AI 编程任务**: 优化前端状态管理
**要求**:
- 关节角度实时同步
- 网络延迟补偿
- 数据缓冲和插值
- 异常状态处理
**验收标准**: 前端状态与仿真保持精确同步
**预计时间**: 2-3小时

---

## 🔍 阶段五：系统校准与测试
> **目标**: 确保系统准确性和稳定性
> **前置条件**: 阶段四完成，系统基本功能正常

### 任务 5.1：验证关节顺序映射
**AI 编程任务**: 创建关节映射验证工具
**要求**:
- 对比 URDF、MJCF、前端关节顺序
- 生成关节映射表
- 实现坐标转换函数
- 创建验证测试脚本
**验收标准**: 关节顺序一致，无错位现象
**预计时间**: 2-3小时

### 任务 5.2：坐标系对齐检查
**AI 编程任务**: 实现坐标系转换工具
**要求**:
- 分析 URDF、MuJoCo、Three.js 坐标系差异
- 编写坐标转换矩阵
- 创建验证测试用例
- 生成转换文档
**验收标准**: 坐标系统一，位姿计算准确
**预计时间**: 3-4小时

### 任务 5.3：创建测试用例套件
**AI 编程任务**: 编写完整的测试套件
**要求**:
- 单元测试（模型加载、仿真步进、API 接口）
- 集成测试（前后端通信、状态同步）
- 性能测试（WebSocket 频率、渲染性能）
- 自动化测试脚本
**验收标准**: 测试覆盖率 > 80%，所有核心功能测试通过
**预计时间**: 3-4小时

### 任务 5.4：性能优化和调优
**AI 编程任务**: 优化系统性能
**要求**:
- 分析性能瓶颈
- 优化仿真步进时间（目标 < 10ms）
- 改进网络传输效率
- 内存使用优化
**验收标准**: 达到性能目标，无明显延迟
**预计时间**: 2-3小时

### 任务 5.5：生成校准和部署文档
**描述**: 创建完整的项目文档
**步骤**:
1. 记录关节映射表和坐标转换公式
2. 生成误差统计和性能报告
3. 编写部署和使用说明
4. 创建故障排除指南
**验收标准**: 完整的技术文档可用
**预计时间**: 2-3小时

---

## 📊 执行指南

### 🎯 推荐执行顺序
1. **开始**: 任务 1.1 → 2.1 → 2.2
2. **模型转换**: 任务 2.3 → 2.4 → 2.5
3. **MuJoCo 仿真核心**: 任务 3.1 → 3.2 → 3.3
4. **仿真接口开发**: 任务 3.4 → 3.5 → 3.6 → 3.7 → 3.8
5. **前端集成**: 任务 4.1 → 4.2 → 4.3 → 4.4 → 4.5
6. **AI 增强模块**: 任务 M1 → M3 → M2 → M4 → M5 → M6 → M7 → M8
7. **验证优化**: 任务 5.1 → 5.2 → 5.3 → 5.4 → 5.5

### ⚡ 快速启动建议
- **核心路径**: 任务 2.1-2.3（模型转换）→ 3.1-3.5（MuJoCo 仿真基础）→ 4.2（WebSocket 连接）
- **AI 增强路径**: 在仿真核心完成后，可并行开发 M1+M3（传感器处理）→ M2+M4（感知增强）→ M5-M8（决策与集成）
- **测试验证**: 任务 5.1-5.3（系统校准测试）

### 🔧 技术支持
我可以为每个任务提供：
- 完整的代码实现
- 详细的实现解释
- 调试和优化建议
- 测试用例编写

**请选择要开始的具体任务，我将提供相应的代码和指导！**

---

### 五、接口定义示例（建议 JSON 结构）
- POST /sim/step/
  - 请求 body:
    {
      "target_positions": [0.0, -1.57, 1.57, 0.0, 0.0, 0.0], // rad
      "n_steps": 10
    }
  - 返回:
    {
      "timestamp": 1670000000.0,
      "qpos": [...],
      "qvel": [...],
      "ee_pose": {"position":[x,y,z],"orientation":[qw,qx,qy,qz]}
    }
- GET /sim/state/
  - 返回同上（最新状态）
- WebSocket /sim/ws
  - 服务端周期性发送 JSON 状态（上面格式），客户端可发送控制消息：
    {"type":"control","target_positions":[...],"n_steps":10}
- GET /sim/camera.jpg
  - 返回 JPEG 二进制，或 `GET /sim/camera?format=base64` 返回 base64 字符串。

---

### 六、风险、常见问题与应对
- glfw / 渲染异常（Windows 特有）：尝试用 WSL2 + X server 或 Docker；对于 headless 可启用 EGL（需显卡驱动与 EGL 支持）。
- 关节顺序/坐标系错位：先做静态姿态对齐测试（已知角度），确认每个轴与方向。
- 网络带宽瓶颈：降低图像分辨率/频率，或仅发送关键帧。
- 并发冲突：仿真状态应由单一线程管理，客户端通过队列提交命令。

---

### 七、交付物清单（详细验收标准）
1. **MuJoCo 模型文件集** `fastapi/mujoco_models/`：
   - `ur5.xml`：完整的 UR5 机器人 MJCF 模型（6关节+执行器+sensors）
   - `battery.xml`、`rack.xml`、`camera_base.xml`：静态环境组件
   - `environment.xml`：集成环境场景
   - `meshes/`：所有必需的网格文件（STL/DAE格式）
   - 验收：所有模型可被 MuJoCo 正确加载，无几何冲突

2. **后端仿真模块** `fastapi/simulation.py`：
   - 完整的 Simulation 类（模型加载、步进控制、状态管理）
   - REST API：`/sim/reset/`、`/sim/step/`、`/sim/state/`
   - WebSocket：`/sim/ws`（实时状态推送和控制接收）
   - 相机渲染：`/sim/camera.jpg`（offscreen 渲染，多种格式支持）
   - 并发安全：线程锁和请求队列机制
   - 验收：所有接口正常工作，支持并发访问

3. **前端集成代码** `src/`：
   - `App.vue`：WebSocket 连接替换轮询，实时状态同步
   - 控制组件：发送命令到仿真后端
   - 相机组件：实时图像显示（支持多种分辨率）
   - 错误处理：网络断开重连，状态同步失败处理
   - 验收：前端与仿真后端完全集成，响应延迟 < 100ms

4. **校准与映射文档**：
   - 关节顺序映射表（URDF ↔ MuJoCo ↔ 前端）
   - 坐标系转换矩阵和公式
   - 物理参数基线配置
   - 误差统计表（位置误差 < 5mm，姿态误差 < 2°）
   - 验收：仿真与实际机器人姿态一致性验证

5. **AI 增强模块** `fastapi/`：
   - `env_sensing.py`：基于 MuJoCo 传感器的环境感知模块
   - `vision.py`：仿真相机图像处理和目标检测
   - `tactile.py`：力学触觉数据处理和事件检测
   - `nlp.py`：自然语言指令解析和参数映射
   - `decision_fusion.py`：多模态决策融合器
   - `proactive.py`：主动交互和反馈回路
   - 验收：各模块能正确处理 MuJoCo 仿真数据，实现预期 AI 功能

6. **测试套件和脚本**：
   - 单元测试：模型加载、仿真步进、相机渲染、AI 模块功能
   - 集成测试：端到端控制流程验证、AI 决策到仿真执行链路
   - 性能测试：WebSocket 50Hz 状态更新，相机 10FPS，AI 推理延迟 < 100ms
   - 自动化测试脚本：一键运行所有测试
   - 验收：测试覆盖率 > 80%，所有测试通过

---

### 八、执行建议与优先级
**推荐执行顺序**（按依赖关系排序）：
1. **立即开始**：阶段二任务 2.1（创建目录）→ 2.2（UR5 MJCF转换）
2. **并行处理**：任务 2.3-2.5（静态环境组件，可并行开发）
3. **后端优先**：阶段三任务 3.1-3.3（核心仿真功能）
4. **接口开发**：任务 3.4-3.5（REST + WebSocket）
5. **前端集成**：阶段四任务（与后端接口配合开发）
6. **最后验证**：阶段五任务（完整系统测试）

**风险控制**：
- 每周进行阶段性集成测试，避免大块修改
- 优先实现核心功能（关节控制），相机渲染可后续添加
- 准备回滚方案：保留原有的 URDF 前端作为备选

**技术建议**：
- 使用 Git 分支管理：为每个主要任务创建 feature 分支
- 编写测试先行：每个接口完成时立即编写对应的测试
- 文档同步更新：代码变更时同步更新此任务文档

**我可以提供的协助**：
1. 生成 `simulation.py` 完整代码模板（MuJoCo 仿真核心）
2. 提供 UR5 MJCF 文件示例和模型转换指导
3. 创建前端 WebSocket 集成代码片段
4. 编写测试脚本和校准工具
5. 实现 AI 增强模块代码框架（`env_sensing.py`、`vision.py`、`decision_fusion.py` 等）
6. 提供 MuJoCo 传感器数据处理和 AI 决策集成的示例代码

请告诉我你想从哪个具体任务开始实施，我会提供相应的代码和指导。

---

### 九、开发环境与工具配置

#### 推荐开发环境设置
```bash
# 项目根目录结构
vue-robot/
├── fastapi/
│   ├── mujoco_models/     # MJCF 模型文件
│   ├── simulation.py      # 仿真核心模块
│   ├── main.py           # FastAPI 应用入口
│   └── run.py            # 启动脚本
├── src/                  # Vue 前端
├── public/               # 静态资源
└── task.md              # 项目文档
```

#### 开发工具推荐
- **代码编辑器**: VS Code + Python 扩展 + Volar (Vue)
- **版本控制**: Git (推荐创建功能分支)
- **API 测试**: Postman 或 Insomnia (测试 REST/WebSocket 接口)
- **MuJoCo 调试**: mujoco-viewer (可视化验证模型)
- **性能监控**: Chrome DevTools (前端) + Python profiler (后端)

#### 启动和调试命令
```bash
# 后端开发模式
cd fastapi
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端开发模式
npm run dev  # 或 yarn dev

# 测试 WebSocket 连接
# 使用浏览器控制台或在线 WebSocket 测试工具
# ws://localhost:8000/sim/ws
```

---

### 十、调试与故障排除指南

#### 常见问题及解决方案

**1. MuJoCo 模型加载失败**
```python
# 调试代码
try:
    model = mujoco.MjModel.from_xml_path('path/to/model.xml')
    print("模型加载成功")
    print(f"关节数量: {model.njnt}")
    print(f"执行器数量: {model.nu}")
except Exception as e:
    print(f"加载失败: {e}")
    # 检查 XML 语法
    # 验证 mesh 文件路径
    # 确认关节定义正确
```

**2. WebSocket 连接问题**
- 检查 CORS 设置（FastAPI 中添加中间件）
- 验证端口配置（前后端端口一致）
- 使用浏览器开发者工具检查网络请求

**3. 关节角度不同步**
- 检查关节顺序映射（URDF vs MJCF vs 前端）
- 验证坐标系一致性（Z-up vs Y-up）
- 确认角度单位（度 vs 弧度）

**4. 性能问题**
- 使用 `mujoco.mjtWarning` 检查警告信息
- 分析仿真步进时间（目标 < 10ms）
- 优化网络传输（压缩数据，减少频率）

#### 日志和监控
```python
# 建议的日志配置
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 关键性能指标监控
class PerformanceMonitor:
    def __init__(self):
        self.step_times = []

    def record_step_time(self, time_ms):
        self.step_times.append(time_ms)
        if len(self.step_times) > 100:
            self.step_times.pop(0)

    def get_avg_step_time(self):
        return sum(self.step_times) / len(self.step_times) if self.step_times else 0
```

---

### 十一、测试策略与质量保证

#### 测试层次
1. **单元测试**: 各模块独立功能
   - 模型加载测试
   - 仿真步进测试
   - API 接口测试

2. **集成测试**: 模块间协作
   - 前后端通信测试
   - 控制命令执行测试
   - 状态同步测试

3. **端到端测试**: 完整用户流程
   - 从前端发送命令到仿真执行的完整链路
   - 性能和稳定性测试

#### 自动化测试脚本示例
```python
# tests/test_simulation.py
import pytest
import numpy as np
from fastapi.testclient import TestClient
from simulation import Simulation

def test_model_loading():
    sim = Simulation()
    assert sim.model is not None
    assert sim.model.njnt == 6  # UR5 有 6 个关节

def test_simulation_step():
    sim = Simulation()
    initial_qpos = sim.data.qpos.copy()

    # 执行一步仿真
    sim.step_simulation([0.1, 0, 0, 0, 0, 0], n_steps=1)

    # 验证状态更新
    assert not np.array_equal(sim.data.qpos, initial_qpos)

def test_rest_api(client: TestClient):
    response = client.get("/sim/state")
    assert response.status_code == 200
    data = response.json()
    assert "qpos" in data
    assert len(data["qpos"]) == 6
```

#### 性能基准测试
- **仿真性能**: 步进时间 < 10ms (100Hz)
- **网络延迟**: WebSocket RTT < 50ms
- **前端渲染**: 60 FPS 流畅显示
- **内存使用**: < 500MB (稳定状态)

---

### 十二、部署和生产环境考虑

#### 生产环境配置
```python
# FastAPI 生产配置
app = FastAPI(
    title="UR5 Robot Simulation API",
    description="MuJoCo-based robot simulation service",
    version="1.0.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加性能监控
@app.middleware("http")
async def add_performance_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

#### Docker 容器化部署
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY fastapi/ ./fastapi/
COPY src/ ./src/

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "fastapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 监控和日志
- 使用 Prometheus + Grafana 监控系统性能
- 设置结构化日志（JSON 格式）
- 配置健康检查端点
- 实现优雅关闭和资源清理

---

### 十三、扩展和未来优化

#### 短期优化目标
- [ ] 实现轨迹规划算法
- [ ] 添加碰撞检测和避障
- [ ] 支持多机器人仿真
- [ ] 优化相机渲染性能

#### 长期发展方向
- [ ] 集成强化学习框架
- [ ] 支持自定义机器人模型
- [ ] 添加虚拟现实支持
- [ ] 云端仿真服务化

#### 社区资源
- **MuJoCo 官方文档**: https://mujoco.readthedocs.io/
- **FastAPI 文档**: https://fastapi.tiangolo.com/
- **Vue.js 生态**: https://vuejs.org/
- **机器人仿真社区**: ROS, Gazebo 相关论坛

---

*最后更新时间: 2025年1月20日 | 版本: v2.0 | 作者: AI Assistant*

