# VR 控制与性能修复明细（2026-04-24）

本文档记录本次对 `ar-ur5-rl` 的具体代码修改细节，重点覆盖：

- 进入 VR 后已选模式但无法稳定控制机械臂的问题
- 前端高负载/卡顿与内存压力问题
- 控制映射与发送链路的可维护性改进

## 1. 修改范围

前端核心文件：

- `frontend/src/App.vue`
- `frontend/src/utils/questXRSession.js`（新增）
- `frontend/src/utils/questControllerInput.js`
- `frontend/src/utils/questControllerTeleop.js`
- `frontend/src/utils/questHandInputSession.js`
- `frontend/src/utils/questHandInput.js`
- `frontend/src/utils/questHandTeleop.js`

后端核心文件：

- `backend/sim/simulation.py`

## 2. VR 会话链路修复

### 2.1 新增 XR 会话管理模块

新增 `frontend/src/utils/questXRSession.js`，统一管理：

- `immersive-vr` 会话创建与关闭
- `referenceSpace` 选择回退（`local-floor -> bounded-floor -> local -> viewer`）
- 会话状态（`ready/reason`）

### 2.2 会话创建时机调整

`App.vue` 中做了两层处理：

1. `runQuest3AccessChecks()` 只做支持性检查，不主动创建会话
2. `enterVrMode()` 在用户点击“进入VR模式”后调用 `ensureQuestXRSession()`

这样避免了非用户手势上下文下 `requestSession()` 被浏览器拒绝，减少“模式已选但输入不可用”。

### 2.3 会话释放策略

在以下路径确保调用 `stopQuestXRSession()`：

- 退出 VR 模式
- Quest 连接断开
- 页面卸载（`onBeforeUnmount`）

## 3. 手柄控制映射细节（明确参数）

文件：`frontend/src/utils/questControllerInput.js`、`frontend/src/utils/questControllerTeleop.js`

### 3.1 按键/轴映射

- 左手：
  - `precision`: `buttons[0]`
  - `select_wrist`: `buttons[1]`
  - `select_upper_arm`: `buttons[4]`
  - `select_forearm`: `buttons[5]`
- 右手：
  - `trigger`: `buttons[0]`
  - 摇杆：优先 `axes[2]/axes[3]`，回退 `axes[0]/axes[1]`

### 3.2 手柄识别策略

优先按 `gamepad.hand` 识别左右手柄（`left/right`），再回退到 `id/mapping` 模式匹配，减少设备标识差异导致的误判。

### 3.3 控制参数

- 摇杆死区：`deadzone = 0.1`
- 摇杆平滑：`stick_smoothing = 0.25`
- 关节步长：`joint_step = 0.07 * UI灵敏度倍率`
- 精细模式倍率：`precision_scale = 0.4`（`precision > 0.1` 生效）
- 夹爪平滑：`gripper_smoothing = 0.16`
- 夹爪范围：`0 ~ 0.9`
- 夹爪变化判定阈值：`0.004`

### 3.4 关节组逻辑

- `select_wrist` -> 腕组（索引 `4,5`）
- `select_forearm` -> 前臂组（索引 `2,3`）
- `select_upper_arm` -> 大臂组（索引 `0,1`）

对应组内增量：

- 第一关节：`stick_y * speedScale`
- 第二关节：`stick_x * speedScale`

补充约束（已落地）：

- 仅当左手对应组选键被按下时，才发送关节增量
- 未按下组选键时，仅允许右扳机驱动夹爪，不发送关节位移命令

## 4. 手势控制映射细节（明确参数）

文件：`frontend/src/utils/questHandTeleop.js`

### 4.1 手势输入模式

- 双手：左手选组，右手拖拽控制
- 单手：右手无名指轮切关节组 + 食指拖拽控制

### 4.2 选组规则

双手模式下，左手 pinch 强度按阈值 `0.56` 选择：

- `middle` -> `forearm`
- `ring` -> `upper_arm`
- `index` -> `wrist`

单手模式下：

- `ring >= 0.56` 且未锁存时切换到下一组（`wrist -> forearm -> upper_arm -> wrist`）
- `ring <= 0.2` 解除锁存

### 4.3 拖拽控制参数

- 拖拽进入阈值：`index >= 0.38`
- 拖拽释放阈值：`index <= 0.2`
- 释放保持时间：`180ms`
- 追踪宽限：`280ms`
- 单帧位移上限：`0.03`
- 位移死区：`0.0012`
- 位移平滑：`0.32`
- 位移增益：`movement_gain = 4.1 * UI灵敏度倍率`
- 精细模式：`ring >= 0.72`，倍率 `0.42`

### 4.4 夹爪控制参数

- 夹爪输入：`middle pinch`
- pinch 死区阈值：`0.2`
- 平滑：`0.2`
- 输出范围：`0 ~ 0.9`
- 变化判定阈值：`0.004`

### 4.5 pinch 强度归一化参数

文件：`frontend/src/utils/questHandInputCore.js`

- 食指/中指/无名指 pinch 强度统一按“拇指到指尖距离”归一化
- 闭合阈值距离：`0.018m`（按下视为 1）
- 释放阈值距离：`0.055m`（松开视为 0）
- 归一化公式：`(0.055 - d) / (0.055 - 0.018)` 并裁剪到 `0~1`

## 5. 发送链路稳定性修复

文件：`frontend/src/App.vue`

### 5.1 VR 状态同步节流

- `syncVrStateToBackend()` 增加最小间隔：`180ms`
- `vr_disabled`、`vr_error` 强制立即同步，不受节流限制

### 5.2 控制发送节流

手柄/手势控制命令统一增加：

- 最小发送间隔：`50ms`
- `in-flight` 标志：防止同一模式并发堆积
- in-flight 超时回收：`420ms`（避免回包异常造成“发送锁死”）

### 5.3 in-flight 清理时机

以下路径统一清理：

- 收到 `controlResult`
- WebSocket `error`
- WebSocket `disconnected`
- 停止手柄/手势循环
- 组件卸载

## 6. 后端状态构建内存压力优化

文件：`backend/sim/simulation.py`

在 `_capture_camera_state_locked()` 中：

- `self._camera_last_state = deepcopy(camera_state)` 改为直接引用 `camera_state`
- `return deepcopy(camera_state)` 改为 `return camera_state`

效果：

- 降低每次相机状态构建的深拷贝成本
- 减少高频状态路径上的对象分配与回收压力

## 7. 验证结果

已执行并通过：

- `cd frontend && npm run build`
- `python -m py_compile backend/sim/simulation.py`

说明：

- 本次文档仅描述已落地的代码修改细节，不包含未实现规划项。
