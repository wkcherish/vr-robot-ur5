# 里程碑 A：场景、坐标、关节与协议基线

更新时间：`2026-04-07`

## A1. 共享场景单一数据源

- 基线文件：`shared/scene_manifest.json`
- 该文件已记录：
  - UR5 基座补偿信息（`rotation.x = -PI/2`）
  - UR5 home 姿态
  - `battery_pack` / `rack` / `camera_base` / `camera` 初始位姿
  - 每个对象的资源路径、位置、旋转、缩放与备注
  - 版本号与更新时间
- 执行规则：
  - 前端后续必须读取该清单，不再手写散落位姿
  - 后端/MuJoCo 必须读取该清单，或由该清单生成场景配置

## A2. 坐标系与零位统一

### 1) 坐标与单位基线

- 位置单位统一：`meter`
- 角度单位统一：`radian`
- 前端世界基线（Three.js）：当前场景通过 `robot.rotation.x = -PI/2` 做 UR5 基座补偿
- 后端世界基线（MuJoCo）：应在模型装配或根 body 变换中复现同一补偿，保证初始可视对齐

### 2) `robot.rotation.x = -PI/2` 的补偿意义

- 该补偿用于对齐 URDF 默认坐标朝向与当前 Three.js 场景坐标基线。
- 若 MuJoCo 不做等价补偿，将出现“前后端看起来接近但姿态轴系不一致”的问题。

### 3) UR5 `base` / `base_link` / `tool0` 对照

- `base_link`：UR 机器人在 URDF 中的基础链入口
- `base`：ROS-Industrial 约定参考帧（由 `base_link` 经过固定变换得到）
- `tool0`：末端工具零位参考帧（前后端末端姿态对齐锚点）

### 4) reset 后 home 定义

- home 关节顺序固定为：
  - `shoulder_pan_joint`
  - `shoulder_lift_joint`
  - `elbow_joint`
  - `wrist_1_joint`
  - `wrist_2_joint`
  - `wrist_3_joint`
- home 角（rad）：
  - `[0.0, -1.5707963267948966, 1.5707963267948966, -1.5707963267948966, -1.5707963267948966, 0.0]`
- `gripper_opening = 0.0`（定义为 fully open）

### 5) 坐标与零位对照表（首版）

| 项 | 前端基线 | 后端/MuJoCo 要求 |
| --- | --- | --- |
| 长度单位 | meter | meter |
| 角度单位 | rad（内部） | rad |
| UR5 根补偿 | `rotation.x = -PI/2` | 必须等价复现 |
| Home 角 | 见上方 6 轴数组 | reset 后返回完全同值 |
| 末端参考帧 | `tool0` | 广播 `ee_pose` 时锚定同一语义帧 |

## A3. 手臂与完整手抓映射

### 1) UR5 主控制顺序冻结

- `shoulder_pan_joint`
- `shoulder_lift_joint`
- `elbow_joint`
- `wrist_1_joint`
- `wrist_2_joint`
- `wrist_3_joint`

### 2) 前端旧命名映射（兼容层）

| 旧命名 | 真实 UR5 关节 |
| --- | --- |
| `link1_joint` | `shoulder_pan_joint` |
| `link2_joint` | `shoulder_lift_joint` |
| `link3_joint` | `elbow_joint` |
| `link4_joint` | `wrist_1_joint` |
| `link5_joint` | `wrist_2_joint` |
| `link6_joint` | `wrist_3_joint` |

### 3) Robotiq 关键关节链与角色

| 关节 | 角色 | 关节限位（rad） |
| --- | --- | --- |
| `left_driver_joint` | 主驱动 | `[0.0, 0.9]` |
| `right_driver_joint` | 主驱动 | `[0.0, 0.9]` |
| `left_spring_link_joint` | 联动/从动 | `[-0.29670597283, 0.9]` |
| `right_spring_link_joint` | 联动/从动 | `[-0.29670597283, 0.9]` |
| `left_follower_joint` | 联动/从动 | `[-0.872664, 0.9]` |
| `right_follower_joint` | 联动/从动 | `[-0.872664, 0.9]` |

### 4) 高层开合量 -> 完整夹爪关节映射

- 统一高层输入：`gripper_opening`，范围 `[0.0, 1.0]`
- 语义冻结：`0.0 = fully open`，`1.0 = fully closed`
- 第一版线性映射：
  - `driver = clamp(gripper_opening * 0.87, 0.0, 0.87)`
  - `left_driver_joint = driver`
  - `right_driver_joint = driver`
  - `left_spring_link_joint = driver`
  - `right_spring_link_joint = driver`
  - `left_follower_joint = -driver`
  - `right_follower_joint = -driver`

### 5) 完整夹爪状态 -> 前端显示回传映射

- 后端必须同时回传：
  - `gripper_opening`（高层语义值）
  - `gripper_joints`（完整关键关节值）
- 前端显示层策略：
  - 若 `gripper_joints` 存在：优先用 `gripper_joints` 驱动完整手抓模型
  - 否则回退到 `gripper_opening`（仅用于兼容旧版本）

## A4. 通信协议冻结

### 1) WebSocket 消息类型

- 客户端 -> 服务端：`get_state`、`control`、`reset`、`execute_task`、`stop_task`
- 服务端 -> 客户端：`state_broadcast`、`control_result`、`reset_result`、`task_result`、`error`

### 2) `state_broadcast` 字段冻结

- `qpos`
- `qvel`
- `ee_pose`
- `gripper_opening`
- `gripper_joints`
- `objects`
- `task_state`
- `source`

### 3) HTTP 接口冻结

- `GET /health/`
- `GET /sim/state/`
- `POST /sim/step/`
- `POST /sim/reset/`
- `GET /sim/camera.jpg`

### 4) 时间戳、频率、错误格式

- 时间戳约定：
  - WebSocket 命令包：`timestamp` 使用 Unix 毫秒（int）
  - `state_broadcast.data.timestamp`：Unix 秒（float）
- 广播频率约定：
  - 默认 `20Hz`
  - 目标可提升到 `50Hz`（需在后端配置并保持稳定）
- 统一错误体格式：

```json
{
  "code": "SIM_CONTROL_TIMEOUT",
  "message": "control command timeout",
  "detail": "optional detail text",
  "request_id": "optional-request-id",
  "timestamp": 1775491200.123
}
```

### 5) 重试、超时、停止与中断（首版策略）

- `control` 命令超时：`3s`（超时返回 `error`，前端允许 1 次重试）
- `reset` 命令超时：`5s`（超时后前端提示用户手动重置）
- `execute_task`：
  - 任务开始后必须连续广播 `task_state`
  - 支持 `stop_task` 中断
  - 中断或异常结束必须发送 `task_result`
- 非正常中断（服务端异常）必须发送 `error` 且 `task_state.running=false`
