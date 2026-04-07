# MuJoCo / FastAPI 集成任务分析与实施清单

## 1. 文档目的

这份文档基于当前仓库的真实代码状态，重新整理你要完成的 3 个核心目标：

1. 前端机器人与后端 MuJoCo 机器人双向同步。
2. MuJoCo 场景与前端 Three.js 场景一致。
3. 在 MuJoCo 中完成“电池搬运/拆解前置动作”的强化学习训练，并在前端通过“执行任务”触发。

本轮只更新文档，不修改业务代码。

---

## 2. 当前项目现状分析

## 2.1 仓库结构现状

- 当前仓库只有前端工程，`backend/` 目录并不存在。
- `README.md` 中也明确说明后端目录只是预留，当前没有 FastAPI 或 MuJoCo 代码。
- 这意味着项目目前的基础能力是“前端 3D 可视化 + 部分后端接口预埋”，还没有真正的仿真后端。

## 2.2 前端现有能力

- 已使用 `Vue 3 + Vite + Three.js + URDFLoader` 加载场景。
- 已具备 UR5、battery、rack、camera、camera_base 的 URDF 和 mesh 资产。
- `frontend/src/App.vue` 已能在页面中加载机器人和场景模型，并支持关节角度可视化。
- `frontend/src/utils/websocket.js` 已实现 WebSocket 管理器，默认连接 `ws://localhost:8000/sim/ws`。
- `frontend/src/App.vue` 已预埋 `GET /sim/state/`、`POST /sim/step/`、`/data/` 兼容轮询逻辑。
- `frontend/src/components/camera.vue` 已预埋 `/health/`、`/sim/camera.jpg`、`/sim/camera.json` 接口。
- `frontend/src/components/control.vue` 已有“仿真控制系统”面板，但工具识别和抓取流程仍是前端模拟数据，不是真实后端任务。

## 2.3 前端当前不是“空白”，但后端仍是 0 到 1

当前项目并不是从零开始，因为前端已经做了以下准备：

- WebSocket 消息类型已经有雏形：`control`、`reset`、`get_state`、`state_update`、`state_broadcast`、`control_result`、`reset_result`。
- 前端已经按 6 轴机械臂思路发送关节命令。
- 前端已经有状态同步缓冲、插值、连接质量统计等 UI 壳子。

但真正缺失的关键部分是：

- 没有 FastAPI 服务。
- 没有 MuJoCo 模型与仿真循环。
- 没有前后端统一的场景基线和坐标映射。
- 没有任务执行器。
- 没有强化学习环境、训练脚本、策略加载与推理闭环。

## 2.4 当前场景基线

下面这组参数应当被视为后续 MuJoCo 场景复刻的第一版基线，先以“和前端当前显示一致”为目标：

| 对象 | 前端资源 | 当前前端变换基线 |
| --- | --- | --- |
| UR5 机器人 | `frontend/public/ur5/ur5.urdf` | `position = (-0.2, 0.5, -0.1)`，`rotation.x = -PI/2` |
| Rack | `frontend/public/rack/urdf/rack.urdf` | `position = (0.5, 0, 0)`，`scale = (1, 1, 1)` |
| Battery | `frontend/public/battery/urdf/battery.urdf` | `position = (0.1, 1.085, 0.5)`，`rotation.y = PI/2`，`scale = (0.8, 0.8, 0.8)` |
| Camera Base | `frontend/public/camera_base/urdf/camera_base.urdf` | `position = (-0.1, 0.68, 0.4)`，`rotation.x = PI`，`scale = (0.01, 0.01, 0.01)` |
| Camera | `frontend/public/camera/urdf/camera.urdf` | `position = (-0.205, 0.832, 0.4)`，`rotation.y = 0.65PI` |

补充说明：

- UR5 前端默认还会设置一组初始关节姿态：`J2=-90°`、`J3=90°`、`J4=-90°`、`J5=-90°`。
- 前端当前通过 `robot.rotation.x = -PI/2` 做了一次坐标补偿，这说明 Three.js 场景坐标与 URDF 原始姿态并不直接一致。
- 后端 MuJoCo 侧不能只“加载模型”，还必须明确复现这套基座姿态补偿，否则前后端看起来会对不上。

## 2.5 机械臂模型现状

- `frontend/public/ur5/ur5.urdf` 包含 UR5 六轴关节和完整的 Robotiq 夹爪链。
- 前端 UI 目前按“6 轴机械臂 + 1 个手抓开合量”来控制，但这只是前端交互层的简化，不代表后端物理模型可以简化。
- 后端 MuJoCo 中的机器人手抓必须与前端 URDF 保持一致，至少要保留 Robotiq 基座及其联动关节链，不能只用一个抽象的单自由度夹爪替代。
- 第一版建议前端仍可保留一个高层“开合量”控制输入，但后端内部必须把这个输入映射到完整夹爪关节，而不是删除夹爪结构。
- 当前前端 URDF 中可直接对照的夹爪关键关节包括：`left_driver_joint`、`left_spring_link_joint`、`left_follower_joint`、`right_driver_joint`、`right_spring_link_joint`、`right_follower_joint`。

## 2.6 现有代码与目标的差距

| 目标 | 当前状态 | 差距判断 |
| --- | --- | --- |
| 前后端机器人双向同步 | 前端已有消息壳子，但无真实后端 | 需要新建后端仿真核心与状态映射 |
| MuJoCo 场景与前端一致 | 前端场景已可视化，MuJoCo 场景不存在 | 需要建立统一场景清单、坐标转换和 MJCF |
| 强化学习电池搬运任务 | 控制面板有任务 UI 雏形，但逻辑是模拟数据 | 需要先完成环境、状态、抓取对象和任务执行器 |

---

## 3. 结论：推荐的真实实施路径

不建议一上来直接做强化学习。更稳妥的路径是：

1. 先把前端场景和 MuJoCo 场景完全对齐。
2. 再把机器人双向同步链路打通。
3. 然后用一个脚本化抓取/搬运任务验证后端场景与控制链是否可靠。
4. 最后再把该任务替换或增强为强化学习策略。

原因很简单：

- 如果场景坐标和关节映射都没有对齐，强化学习训练出来的策略基本无法在前端正确回放。
- 如果前后端状态不是同一套权威状态，前端看到的动作和 MuJoCo 里的动作会分叉。
- 先做脚本化任务可以更快验证“场景一致 + 同步一致 + 任务执行入口”。

---

## 4. 目标架构建议

建议后续代码结构按下面方式落地：

```text
backend/
├─ main.py                     # FastAPI 入口
├─ schemas.py                  # REST / WebSocket 消息结构
├─ sim/
│  ├─ simulation.py            # MuJoCo 模型加载、step、reset、状态采集
│  ├─ state_mapper.py          # 前端关节顺序 / 完整夹爪映射 / 对象状态 / 坐标映射
│  ├─ scene_config.py          # 场景对象初始位姿与标定参数
│  ├─ camera_service.py        # 相机渲染输出
│  └─ task_runtime.py          # 任务执行循环
├─ mujoco_models/
│  ├─ environment.xml          # 总场景
│  ├─ ur5.xml                  # 机器人（包含 UR5 + 完整 Robotiq 夹爪）
│  ├─ battery_pack.xml         # 暂时视为整体刚体
│  ├─ rack.xml
│  └─ meshes/
├─ rl/
│  ├─ envs/
│  │  └─ battery_transfer_env.py
│  ├─ train_battery_transfer.py
│  ├─ evaluate_policy.py
│  └─ policies/
└─ tasks/
   ├─ registry.py              # 任务注册
   └─ battery_transfer.py      # “执行任务”入口
```

前后端职责建议如下：

- 前端负责展示、人工控制、任务触发、状态监控。
- 后端负责权威机器人状态、场景状态、物理步进、任务执行、策略推理。
- WebSocket 作为实时状态与控制主通道。
- HTTP 作为重置、快照、相机抓拍、健康检查等辅助通道。

---

## 5. 双向同步设计

## 5.1 权威状态原则

必须明确：后端 MuJoCo 状态是权威状态源。

前端可以做本地预显示，但最终必须以后端回传的状态为准，否则会出现：

- 前端角度变了，MuJoCo 没变。
- MuJoCo 跑任务了，前端机器人没动。
- 前端和后端都在改姿态，但彼此覆盖。

## 5.2 统一关节顺序与夹爪映射

第一版建议把“手臂主控制顺序”和“夹爪完整关节链”分开定义：

手臂主控制顺序：

1. `shoulder_pan_joint`
2. `shoulder_lift_joint`
3. `elbow_joint`
4. `wrist_1_joint`
5. `wrist_2_joint`
6. `wrist_3_joint`

夹爪建模要求：

- MuJoCo 中不得只保留 6 轴并省略夹爪机构。
- MuJoCo 中应保留与前端 URDF 对应的 Robotiq 夹爪关节链和联动关系。
- 前端现有 `jointNameMap` 已经把旧命名 `link1_joint ~ link6_joint` 映射到 UR5 真实名称。
- 后端 `qpos`、`ctrl`、`actuator`、任务动作向量都必须使用同一套手臂顺序。
- 前端可以继续发送一个高层 `gripper_command` 或 `gripper_opening`，但后端要负责把该命令映射到完整夹爪关节状态。
- 状态广播中不能只返回一个抽象夹爪值，至少要同时返回高层开合量和完整夹爪关键关节状态。

## 5.3 建议的 WebSocket 主消息

前端发送：

```json
{ "type": "get_state" }
```

```json
{
  "type": "control",
  "data": {
    "target_positions": [0.0, -1.57, 1.57, -1.57, -1.57, 0.0],
    "gripper_command": {
      "mode": "open_close",
      "value": 0.0
    },
    "n_steps": 50,
    "control_mode": "position"
  },
  "timestamp": 1710000000000
}
```

```json
{
  "type": "execute_task",
  "data": {
    "task_name": "battery_transfer_v1"
  }
}
```

后端广播：

```json
{
  "type": "state_broadcast",
  "data": {
    "timestamp": 1710000000.123,
    "sim_time": 12.34,
    "joint_names": [
      "shoulder_pan_joint",
      "shoulder_lift_joint",
      "elbow_joint",
      "wrist_1_joint",
      "wrist_2_joint",
      "wrist_3_joint"
    ],
    "qpos": [0.0, -1.57, 1.57, -1.57, -1.57, 0.0],
    "qvel": [0, 0, 0, 0, 0, 0],
    "gripper_opening": 0.0,
    "gripper_joints": {
      "left_driver_joint": 0.0,
      "left_spring_link_joint": 0.0,
      "left_follower_joint": 0.0,
      "right_driver_joint": 0.0,
      "right_spring_link_joint": 0.0,
      "right_follower_joint": 0.0
    },
    "ee_pose": {
      "position": [x, y, z],
      "quaternion": [w, x, y, z]
    },
    "objects": {
      "battery_pack": {
        "position": [x, y, z],
        "quaternion": [w, x, y, z],
        "attached_to_gripper": false
      }
    },
    "task_state": {
      "running": false,
      "name": null,
      "phase": null
    },
    "source": "manual|task|policy"
  }
}
```

## 5.4 双向同步验收标准

- 前端滑块调整后，MuJoCo 机器人在 100 ms 级别内开始跟随。
- 后端执行任务或策略后，前端机器人姿态持续跟随，无明显跳变。
- 前后端同一时刻的 6 轴角度误差维持在可接受范围内。
- 前后端夹爪开合状态与关键夹爪关节状态可相互校验，不允许“前端有夹爪、后端只有抽象抓取器”的分裂实现。
- 电池对象状态也能被前端同步展示，而不是只有机械臂同步。

---

## 6. 场景一致性设计

## 6.1 统一场景清单

第一阶段场景对象建议固定为：

- UR5 机器人
- Battery Pack（先把“电池 + 电池箱”视为一个整体刚体）
- Rack
- Camera Base
- Camera
- 地面 / 工作台 / 参考坐标系

## 6.2 场景一致性的关键不是“资源一样”，而是“变换一样”

要保证 MuJoCo 和前端一致，至少要统一下面 4 类信息：

- 资源来源：mesh / URDF / MJCF 指向同一批模型资源。
- 初始位姿：每个对象的平移、旋转、缩放一致。
- 坐标系补偿：前端已有的旋转修正必须在后端显式记录。
- 关节零位：前端 home 姿态与 MuJoCo reset 姿态一致。

## 6.3 推荐做法

建议新增一个共享场景标定文件，作为前后端共同基线，例如：

```text
shared/
└─ scene_manifest.json
```

这个文件至少包含：

- 对象名称
- 资源路径
- 初始位置
- 初始姿态
- 缩放
- 是否参与碰撞
- 是否参与强化学习任务

这样可以避免：

- 前端手写一套位置
- MuJoCo XML 再手写一套位置
- 后期两个场景越改越不一致

## 6.4 第一版建模策略

为保证项目推进速度，建议分两步：

### V1

- 机器人先做 6 轴关节控制。
- 夹爪在 MuJoCo 中必须保留完整 Robotiq 结构与联动关系，并与前端 URDF 一致。
- 前端允许继续使用单一开合量输入，但后端必须做完整夹爪映射与状态回传。
- Battery Pack 先作为一个整体刚体。
- 任务先完成“接近 -> 抓取 -> 抬起 -> 搬运 -> 放置”。

### V2

- 把 Battery Pack 替换成更细的拆解部件。
- 在完整夹爪结构基础上继续优化接触参数、摩擦、夹持稳定性和抓取成功率。
- 再增加更复杂的拆解序列。

---

## 7. 强化学习任务设计

## 7.1 第一版任务定义

建议先把任务收敛为：

`battery_transfer_v1`

任务描述：

- 机器人从初始 home 姿态出发。
- 接近电池整体模型。
- 完成抓取。
- 将电池搬运到指定目标区域。
- 稳定放置。

这一步虽然还不是完整“拆解”，但它能先把最核心的 4 件事打通：

- 场景一致
- 控制一致
- 接触/抓取一致
- 前端触发任务一致

## 7.2 强化学习环境的最小状态

建议 observation 至少包含：

- 机器人 `qpos`
- 机器人 `qvel`
- 末端执行器位姿
- 电池对象位姿
- 电池相对末端的位置差
- 目标区域相对电池的位置差
- 抓取状态 / 接触状态

## 7.3 动作空间建议

第一版优先使用以下两种方案之一：

- 关节目标位置动作：输出 6 个关节增量或目标值。
- 末端位姿增量动作：由后端 IK / 控制层转换成关节动作。

就当前仓库基础而言，更容易先落地的是“关节目标位置动作”，因为前端与现有控制协议已经按关节角在走。

## 7.4 奖励建议

- 靠近电池奖励
- 姿态对齐奖励
- 成功抓取奖励
- 抬升成功奖励
- 接近目标放置区奖励
- 稳定放置奖励
- 碰撞惩罚
- 关节越界惩罚
- 时间步惩罚

## 7.5 课程学习建议

建议分阶段训练：

1. 固定电池位置、固定目标位置。
2. 小范围随机化电池位置。
3. 随机化目标位置。
4. 随机化初始关节扰动和视觉噪声。

---

## 8. 任务执行链设计

## 8.1 前端触发方式

当前 `control.vue` 的“识别桌面工具 / 抓取工具 / 放置工具”更像演示壳子。

后续应改成面向任务的控制入口，例如：

- 连接仿真
- 重置场景
- 执行电池搬运任务
- 停止任务
- 查看任务状态

## 8.2 后端执行方式

后端建议提供统一任务执行器：

- 接收 `execute_task`
- 加载或选择对应策略
- 驱动 MuJoCo 连续步进
- 周期性向前端广播状态
- 在结束时返回 `task_result`

## 8.3 从训练到部署的链路

链路建议固定为：

1. MuJoCo 环境训练策略。
2. 导出策略权重。
3. 后端 `task_runtime.py` 加载策略。
4. 前端点击“执行任务”。
5. 后端在 MuJoCo 中执行策略。
6. 前端实时显示机器人和电池对象动作。

---

## 9. 分阶段实施计划

## 阶段 A：场景与协议对齐

目标：

- 梳理前端真实场景基线。
- 固定统一关节顺序。
- 固定 WebSocket / HTTP 协议。
- 固定 Battery Pack 第一版任务对象定义。

产出：

- `scene_manifest`
- 关节映射表
- WebSocket 消息协议
- MuJoCo 场景对象清单

## 阶段 B：后端仿真骨架

目标：

- 建立 FastAPI 服务。
- 建立 MuJoCo 仿真循环。
- 支持 reset / get_state / step / ws broadcast。

产出：

- `backend/main.py`
- `backend/sim/simulation.py`
- `/health/`
- `/sim/state/`
- `/sim/step/`
- `/sim/ws`

## 阶段 C：场景一致性落地

目标：

- 把 UR5、rack、battery、camera base、camera 放入 MuJoCo。
- 让 MuJoCo 初始状态与前端显示一致。

产出：

- `ur5.xml`
- `rack.xml`
- `battery_pack.xml`
- `environment.xml`
- 初始姿态对齐验证脚本

## 阶段 D：双向同步闭环

目标：

- 前端手动调关节，MuJoCo 跟着动。
- MuJoCo 任务驱动机器人时，前端跟着动。
- 电池对象状态同步到前端。

产出：

- 稳定的 `state_broadcast`
- 前后端状态误差统计
- 统一 reset 行为

## 阶段 E：脚本化任务验证

目标：

- 在不依赖 RL 的情况下，先用脚本或状态机跑通电池搬运。

产出：

- `battery_transfer_scripted`
- 前端“执行任务”按钮
- 全链路回放验证

## 阶段 F：强化学习训练与部署

目标：

- 在 MuJoCo 中训练 `battery_transfer_v1`。
- 将策略接入任务执行器。
- 前端触发后可直接运行。

产出：

- RL 环境
- 训练脚本
- 策略权重
- 策略执行接口

---

## 10. 本项目下一步最值得先做的事情

如果按投入产出比排序，最优先的不是“训练”，而是下面 5 件事：

1. 先把前端当前场景参数固化成共享场景清单。
2. 新建 FastAPI + MuJoCo 后端骨架。
3. 跑通 `/sim/ws` 和 `/sim/state/`，让前端真正收到后端状态。
4. 让 MuJoCo 场景中的 UR5、battery、rack 与前端位置一致。
5. 先用脚本化搬运任务验证闭环，再切换到强化学习。

---

## 11. 验收标准

## 11.1 对应目标 1：前后端双向同步

- 前端连接后，手动调整关节，MuJoCo 内机械臂同步变化。
- 后端执行控制或任务，前端机器人同步变化。
- 同步时不出现明显跳姿、回弹、长期漂移。

## 11.2 对应目标 2：场景一致

- MuJoCo 中机器人、rack、电池、相机与前端场景布局一致。
- reset 后前后端场景都回到同一初始状态。
- 电池对象在前后端的位置和姿态可相互验证。

## 11.3 对应目标 3：强化学习任务

- MuJoCo 中可训练出 `battery_transfer_v1`。
- 后端可加载训练好的策略并执行。
- 前端连接后点击“执行任务”，机器人能完成对应搬运动作。

---

## 12. 当前风险与注意事项

- 当前前端虽然预埋了 WebSocket 和 HTTP 接口，但这些接口还没有真实后端支撑，不能误判为“后端已经完成一半”。
- 前端存在局部本地角度预显示逻辑，后续必须以后端广播状态为准，避免前后端状态源冲突。
- `control.vue` 里的工具识别和抓取流程目前是示意逻辑，不能直接当成电池任务链。
- `camera.vue` 里 WebSocket 图像流仍未实现，当前是 HTTP 轮询思路。
- 前端目前把夹爪当成一个高层开合量来交互，但后端 MuJoCo 实现不能因此把夹爪物理结构简化掉；需要区分“交互简化”和“模型简化”。
- `frontend/package.json` 中虽然已经有 `mujoco-js` 依赖，但当前代码并未实际使用；你的目标里后端明确要用 Python MuJoCo，因此浏览器侧 MuJoCo 不是主线。

---

## 13. 本文档对应的开发判断

基于当前代码情况，我对项目状态的判断如下：

- 前端可视化基础：已经具备。
- 前端实时同步壳子：已经具备，但未接入真实后端。
- 后端仿真核心：未开始。
- 场景一致性校准：未开始。
- 强化学习训练链：未开始。
- 任务执行链：UI 有雏形，真实执行未开始。

换句话说，这个项目最关键的突破口不是继续堆前端功能，而是把后端 MuJoCo 仿真和统一状态源搭起来。

---

## 14. 建议的后续开发顺序

1. 创建 `backend/` 基础目录与 FastAPI 入口。
2. 把前端当前场景参数整理成共享清单。
3. 用 MuJoCo 先跑通 UR5 + rack + battery 的静态场景。
4. 打通 `/sim/ws` 和前端 `websocketManager`。
5. 完成前端与 MuJoCo 机器人的双向同步。
6. 实现脚本化 `battery_transfer_v1`。
7. 再引入强化学习训练与策略部署。

如果后续继续推进编码，实现顺序就按上面这 7 步走，会比“直接开做 RL”更稳。
