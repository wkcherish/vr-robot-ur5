# VR 控制与性能修复明细（2026-04-24）

本文档记录 `ar-ur5-rl` 在 2026-04-24 完成的一轮 VR 控制链路与性能修复，内容已按当前代码实现校准。

## 1. 修改范围

前端核心文件：

- `frontend/src/App.vue`
- `frontend/src/utils/questXRSession.js`（新增 XR 会话管理）
- `frontend/src/utils/questControllerInput.js`
- `frontend/src/utils/questControllerTeleop.js`
- `frontend/src/utils/questHandInputSession.js`
- `frontend/src/utils/questHandInput.js`
- `frontend/src/utils/questHandInputCore.js`
- `frontend/src/utils/questHandTeleop.js`

后端核心文件：

- `backend/sim/simulation.py`

## 2. VR 会话链路修复

### 2.1 统一 XR 会话管理

新增 `questXRSession.js`，集中管理：

- `immersive-vr` 会话创建/销毁
- 会话状态机（`ready/reason/detail`）
- `referenceSpace` 自动回退：
  `local-floor -> bounded-floor -> local -> viewer`

### 2.2 会话创建时机改为“用户点击进入 VR”

`App.vue` 中：

- `runQuest3AccessChecks()` 只做前置检查，不主动创建 XR 会话
- `enterVrMode()` 里调用 `ensureQuestXRSession()`

效果：避免在非用户手势上下文触发 `requestSession()` 被浏览器拒绝，降低“模式已选但无法输入”的概率。

### 2.3 会话释放与清理

在退出 VR、输入模式切换与组件销毁路径统一执行清理，避免残留会话和状态漂移。

## 3. 手柄控制修复（Controller）

文件：`questControllerInput.js`、`questControllerTeleop.js`、`App.vue`

### 3.1 左右手柄识别策略

- 优先使用 XR 会话 `inputSources + handedness`
- 再回退 `navigator.getGamepads()`
- 最后回退 `id/mapping` 模式匹配

提升了不同固件/浏览器版本下的识别稳定性。

### 3.2 按键与关节组映射

- 左手 `buttons[1]`：腕部组 `wrist (4,5)`
- 左手 `buttons[5]`：前臂组 `forearm (2,3)`
- 左手 `buttons[4]`：大臂组 `upper_arm (0,1)`
- 左手 `buttons[0]`：精细模式
- 右手摇杆：优先 `axes[2]/axes[3]`，回退 `axes[0]/axes[1]`
- 右手 `buttons[0]`：夹爪连续开合

### 3.3 关键参数（当前实现）

- 死区（默认）：`deadzone = 0.10`
- UI 默认死区：`0.14`（可调）
- 摇杆平滑：`stick_smoothing = 0.25`
- 摇杆活动阈值：`stick_activity_epsilon = 0.035`
- 关节步长：`joint_step = 0.07 * sensitivity`
- 精细模式倍率：`precision_scale = 0.4`
- 夹爪平滑：`gripper_smoothing = 0.16`
- 夹爪范围：`0 ~ 0.9`
- 夹爪活动阈值：`0.004`

### 3.4 发送逻辑约束

- 只有按住左手关节组选键时才发关节增量
- 未按组选键时允许右扳机单独控制夹爪
- 控制包携带 `control_seq` 用于后端反回退

### 3.5 系统菜单/模式切换防抖（修复腕部偶发乱动）

针对“按 Meta 键打开前端界面并切模式后，腕部偶发乱动”的问题，新增了控制保护门：

- `questControllerTeleop.js`
  - 增加 `suppressCommands()` 与 `reset()` 接口
  - 增加 `control_guard` 状态，保护期内不产生命令
  - 支持 `require_neutral`：要求输入回到中立（摇杆/扳机/按键释放）后才恢复控制
- `App.vue`
  - 新增 `VR_MODE_TRANSITION_GUARD_MS = 420`
  - 在以下场景触发保护门并清空待发送队列：
    - 手柄模式启动/切换
    - XR `visibilitychange`（进入系统菜单、从系统菜单恢复）
    - XR `inputsourceschange`（输入源重建或切换）
  - 手柄 tick 中识别 `control_guard`，仅更新状态不发送控制指令

效果：避免系统菜单恢复时的瞬时脏输入被当作腕部控制增量，显著降低随机抖动和突发动作。

## 4. 手势控制修复（Hand Tracking）

文件：`questHandInputCore.js`、`questHandTeleop.js`、`App.vue`

### 4.1 模式策略

- 双手模式优先：左手选组，右手拖拽控制
- 仅单手追踪时：无名指循环切组 + 食指拖拽 + 中指夹爪

### 4.2 选组与拖拽阈值

- 左手选组阈值：`group_pinch_threshold = 0.56`
  - `index -> wrist`
  - `middle -> forearm`
  - `ring -> upper_arm`
- 拖拽进入阈值：`index >= 0.38`
- 拖拽进入保持：`70ms`
- 拖拽释放阈值：`index <= 0.2`
- 拖拽释放保持：`180ms`

### 4.3 运动与精细控制参数

- 位移死区：`movement_deadzone = 0.0012`
- 单帧位移上限：`max_frame_movement = 0.03`
- 位移平滑：`movement_smoothing = 0.32`
- 位移增益：`movement_gain = 4.1 * sensitivity`
- 精细模式阈值：`ring >= 0.72`
- 精细模式倍率：`precision_scale = 0.42`

### 4.4 夹爪控制参数

- 输入：中指 pinch
- 进入阈值：`0.34`
- 释放阈值：`0.2`
- 平滑：`0.2`
- 输出范围：`0 ~ 0.9`
- 活动阈值：`0.01`

### 4.5 手部 pinch 强度归一化

`questHandInputCore.js` 中按拇指到指尖距离统一归一化：

- `pinchMin = 0.018m`（视作 1）
- `pinchMax = 0.055m`（视作 0）
- 公式：`(pinchMax - d) / (pinchMax - pinchMin)`，并裁剪到 `0~1`

### 4.6 左手“卡住”稳定性修复（2026-04-25）

问题现象：右手可动但左手在双手模式下经常丢失，导致选组像“卡住”。

根因（代码层面）：

- 左手 `tracked` 判定过于刚性，短时遮挡（尤其拇指/指尖）就立即掉线
- `inputSources` 短暂重建时没有做有效的手部状态延续

本次修复：

- `frontend/src/utils/questHandInputCore.js`
  - 引入左右手缓存 `HAND_CACHE`
  - 增加短时回退窗口：
    - 关节点回退：`JOINT_FALLBACK_GRACE_MS = 180`
    - pinch 回退：`PINCH_FALLBACK_GRACE_MS = 220`
    - 输入源回退：`SOURCE_FALLBACK_GRACE_MS = 260`
  - 追踪稳定性加入平滑：`STABILITY_SMOOTH_ALPHA = 0.45`
  - `tracked` 判定由“必须 wrist + thumb 且高阈值”调整为“wrist + 任一控制指 + 稳定性阈值”
  - 输出新增 `recently_tracked` 与 `predicted` 字段，供上层在短时丢帧时保持交互连续
- `frontend/src/utils/questHandTeleop.js`
  - 双手模式判定从 `left.tracked && right.tracked` 放宽为
    `(left.tracked || left.recently_tracked) && (right.tracked || right.recently_tracked)`
- `frontend/src/App.vue`
  - VR 面板新增“左右手追踪”状态行，显示左右手可用性与稳定度，便于现场排障

效果：左手在短时遮挡/输入源抖动时不再频繁“硬掉线”，双手模式更连续。

### 4.7 手势丝滑性优化（2026-04-25 第二轮）

针对“手势模式仍有略微卡顿，尤其左手不够丝滑”的反馈，再追加了两项核心优化：

1. 输入源污染修复（关键）
- 在 `buildSnapshot()` 中，先将 `session.inputSources` 过滤为 `source.hand === true`
- 仅使用 hand source 更新左右手状态，避免 controller/source 事件覆盖手势状态

2. 运动/捏合信号平滑
- 掌心位置平滑：`PALM_SMOOTH_ALPHA = 0.42`
- pinch 强度平滑：`PINCH_SMOOTH_ALPHA = 0.38`
- 在有缓存窗口时，对实时值做低通融合，降低微抖和突变

另外修复了一个隐藏问题：
- 关节回退缓存索引从 XR joint 名称改为内部缓存 key，避免回退 miss 导致左手更易抖动。

效果：
- 左手在遮挡边界和输入源切换时的抖动明显下降
- 双手模式选组与拖拽连续性更好，控制体感更接近“丝滑”

### 4.8 手势“偶发卡住”继续优化（2026-04-25 第三轮）

针对“仍有时卡住、不够丝滑”的情况，继续补了三层容错：

1. 追踪稳定性滞回（Hysteresis）
- 文件：`frontend/src/utils/questHandTeleop.js`
- 新增：
  - `tracking_stable_enter_threshold = 0.42`
  - `tracking_stable_exit_threshold = 0.30`
- 作用：避免稳定度在单阈值附近抖动时频繁进入/退出稳定状态。

2. 双手模式短时锁存
- 文件：`frontend/src/utils/questHandTeleop.js`
- 新增：
  - `dual_hand_release_ms = 180`
  - `dualHandLatched` / `dualHandLastSeenAt`
- 作用：左手短时掉帧时不立刻降级到单手，减少模式来回切换导致的顿挫感。

3. App 层短时波动宽限（不立刻安全保持）
- 文件：`frontend/src/App.vue`
- 新增：
  - `QUEST_HAND_UNSTABLE_GRACE_MS = 260`
  - `QUEST_HAND_UNAVAILABLE_GRACE_MS = 320`
  - `questHandUnstableSinceAt` / `questHandUnavailableSinceAt`
- 作用：对短暂追踪波动先“保持上一控制”，仅在持续异常后才进入安全保持，明显降低“瞬时卡住”体感。

结果：手势控制在弱抖动、短时遮挡、左手偶发丢追踪时的连续性进一步提升。

## 5. 发送链路与抗回退修复

前端（`App.vue`）：

- VR 状态同步节流：`VR_STATE_SYNC_MIN_INTERVAL_MS = 180`
- 控制命令最小发送间隔：`VR_COMMAND_MIN_INTERVAL_MS = 22`（约 45Hz）
- 控制步数：`VR_COMMAND_STEPS = 1`
- 发送策略：`latest-only`（只保留最新待发送命令）

后端（`simulation.py`）：

- 对 `quest3_controller / quest3_hand` 指令按 `normalized_input.control_seq` 判新旧
- 旧序列直接丢弃并返回 `status = dropped_stale_seq`
- VR 来源 command blend 固定为 `1.0`，避免前端增量再被后端二次平滑导致滞后

## 6. 状态一致性与控制权修复

- 前端增加本地 VR 模式短锁（`VR_MODE_LOCAL_LOCK_MS = 1200`）
  防止本地刚切模式就被旧后端状态覆盖。
- VR 控制下启用手动目标保护窗口（`VR_MANUAL_STATE_GUARD_MS = 1200`）
  减少“控制后被旧状态拉回”的回弹。
- 控制源与关节组在状态中持续同步：
  `source / input_source / selected_joint_group / raw_input / normalized_input / vr`。

## 6.1 XR 输入可视化补齐（手势显示手，手柄显示手柄）

文件：`frontend/src/App.vue`

- 引入 `XRControllerModelFactory` 与 `XRHandModelFactory`
- 为左右手分别创建并维护：
  - controller ray（`renderer.xr.getController(index)`）
  - controller grip model（`renderer.xr.getControllerGrip(index)`）
  - hand mesh model（`renderer.xr.getHand(index)`）
- 按模式动态可见性：
  - `vr_controller_mode`：显示手柄（ray + grip），隐藏手部 mesh
  - `vr_hand_mode`：显示手部 mesh，隐藏手柄
- 说明：
  - 是否显示“简化版手柄”不由 MR / passthrough 自动决定，而是由 XR runtime 是否提供 controller profile mesh，以及前端 fallback 模型质量共同决定。
  - 当前代码优先显示 `XRControllerModelFactory` 的 profile 模型；如果运行时未提供可见 mesh，则退回项目内的 fallback controller 视觉。
- 在 XR 帧循环内持续校准可见性，并监听：
  - `visibilitychange`
  - `inputsourceschange`
  - `end`

效果：进入手势模式可看到手部模型；进入手柄模式可看到手柄模型，满足模式感知与操作反馈。

## 7. 相机状态路径性能优化

文件：`backend/sim/simulation.py`

- `self._camera_last_state = camera_state`（缓存引用）
- `_capture_camera_state_locked()` 在节流窗口内仍返回 `deepcopy(self._camera_last_state)`
- `_build_state_locked(refresh_camera=False)` 复用缓存相机状态

效果：降低高频状态广播下的重复构建成本，同时维持对外返回值隔离。

## 8. 验证结果

已通过基础验证：

- `cd frontend && npm run build`
- `python -m py_compile backend/sim/simulation.py`

说明：本文仅记录已落地实现，不包含未合入的规划项。

## 9. 手势精确控制操作指南（快速上手）

### 9.1 先确认状态

1. 进入 VR 后切到“手势模式”
2. 在 VR 控制面板确认：
   - `手势模式: 双手模式`（优先）
   - `左右手追踪` 两侧都为“可用”
   - `追踪稳定性` 尽量高于 `60%`

### 9.2 双手模式（推荐，最准确）

1. 左手选组（捏住并保持）：
   - 左手食指 pinch：腕部组（`wrist_2/wrist_3`）
   - 左手中指 pinch：前臂组（`elbow/wrist_1`）
   - 左手无名指 pinch：大臂组（`shoulder_lift/elbow`）
2. 右手移动控制（食指 pinch 后拖拽）：
   - 小幅移动右手掌心，机械臂对应组小幅增量运动
   - 停止时先松开 pinch，再回中位
3. 右手中指 pinch 控夹爪：
   - 轻捏微调
   - 避免一次性捏到底

### 9.3 单手降级模式（左手不稳定时）

1. 右手无名指轻捏一次：循环切组（腕 -> 前臂 -> 大臂）
2. 右手食指 pinch + 拖拽：控制当前组
3. 右手中指 pinch：控制夹爪

### 9.4 想要“更准”的实操技巧

1. 每次只动一个维度：先上下再左右，不要同时大幅斜拉
2. 先粗调后细调：先把手势灵敏度调到 `0.8~1.0`，接近目标后再微动
3. 保持左手在胸前可见区，避免贴头显边缘或被右手遮住
4. 出现漂移时：松开右手食指 pinch，等待 0.2~0.3 秒再重新捏合
