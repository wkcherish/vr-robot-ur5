# 里程碑 S5 冻结说明（安全交接任务重定向）

更新时间：`2026-05-22`

本文件用于冻结 `S5` 的任务重定向、研究问题、分层架构和交接状态机。后续 `S6-S12` 的相机验证、人手建模、数据采集、协作记忆、VLA 微调和 interaction gating 都必须围绕这里定义的安全交接主线展开。

## 1. 任务名称与问题边界冻结

新主任务名冻结为：

```text
quest3_safe_handover_v1
```

已有 `quest3_tool_sorting_v1` 保留为工具场景、UR5 操作、工具资产、Quest3 控制和物理边界基线，不再作为最终主任务。工具箱在新任务中保留为初始收纳对象或场景资产，不再是最终放置目标。

第一版安全交接任务对象范围冻结为：

- `UR5 + Robotiq 2F-85`
- `Intel RealSense D405 RGB-D`
- `wrench_01`
- `screwdriver_01`
- `pliers_01`
- `toolbox`
- `human_hand`
- `handover_zone`

第一版继续使用已有 `wrench / screwdriver / pliers` 三类工具，避免在安全交接主线启动阶段重新引入资产、碰撞和尺度变量。第一版 `human_hand` 是仿真人手，由 Quest3 右手控制，不依赖真实人手硬件接入。

核心研究问题冻结为：

```text
机器人什么时候才应该把工具交给人。
```

因此系统目标不是单纯完成抓取、避障或碰撞检测，而是在递送工具时根据人手和工具关系的历史变化判断当前是否已经形成稳定可信的交接关系。

系统输出不得退化为单一 `ready/not_ready`。第一版必须能表达以下 interaction phase：

- `approach`
- `stabilization`
- `hesitation`
- `retreat`
- `ready`
- `release`
- `fail`

## 2. 双层协作架构冻结

总体架构冻结为：

```text
pi0.5 / VLA manipulation layer
  -> collaboration memory layer
  -> interaction gating
  -> executed action
```

### 2.1 pi0.5 / VLA manipulation layer

`pi0.5` 或其他 VLA 操作模型只负责“怎么递”：

- 抓取目标工具。
- 移动到 `handover_zone`。
- 对齐人手接收方向。
- 保持稳定递送姿态。
- 生成候选动作 `candidate_action`。

VLA 可以提出 `release_request`，但不得直接执行最终释放。真实执行必须经过 `interaction gating`。

### 2.2 collaboration memory layer

`collaboration memory` 负责“什么时候递”：

- 输入 relation sequence、机器人状态摘要、人手状态摘要、工具状态摘要。
- 输出 `handover_phase`。
- 输出 `handover_confidence`。
- 输出 `release_allowed` 的模型侧判断。

该层必须利用历史窗口，而不是只看当前一帧距离或当前一帧接触状态。

### 2.3 interaction gating

`interaction gating` 是 release 硬闸门：

- memory 未判定 `ready` 时禁止释放。
- safety 条件不满足时禁止释放。
- `hesitation`、`retreat`、`unstable` 条件或追踪异常时保持夹持或进入 `safe_hold`。
- 如果 `candidate_action` 请求 release 但 gate 拒绝，执行动作必须替换为保持夹持、低速等待或 `safe_hold`。

每个控制周期都必须记录 VLA 候选动作与 gate 输出，便于复盘“模型想释放但被拦截”的样本。

## 3. Episode 阶段与 phase 枚举冻结

标准 episode 阶段冻结为：

```text
reset
  -> robot_grasp
  -> robot_offer
  -> human_approach
  -> stabilization / hesitation / retreat
  -> ready
  -> release
  -> result
```

`handover_phase` 枚举冻结如下：

| phase | 含义 | release 语义 |
| --- | --- | --- |
| `approach` | 人手正在靠近工具或机器人 | 禁止 |
| `stabilization` | 人手接触或接近工具，但仍在调整 | 禁止 |
| `hesitation` | 人手反复微调、晃动或停顿，接收意图不稳定 | 禁止 |
| `retreat` | 人手后撤或离开交接区域 | 禁止 |
| `ready` | 人手稳定、姿态对齐、接触可信 | 可候选 |
| `release` | gate 已允许并执行释放 | 执行 |
| `fail` | 掉落、危险接触、追踪丢失或人工中止 | 禁止 |

`handover_gate` 枚举冻结如下：

| gate | 含义 |
| --- | --- |
| `blocked_by_memory` | 协作记忆未判定 ready 或置信度不足 |
| `blocked_by_safety` | 安全规则不满足，例如距离过近、追踪丢失或接触不可信 |
| `allowed_release` | memory 与 safety 同时允许 release |
| `manual_override` | 调试或人工确认通道，必须显式记录原因 |

## 4. release_decision 字段冻结

每一帧或每个控制周期必须记录 `release_decision`。第一版字段冻结为：

```json
{
  "timestamp": 0.0,
  "frame_id": "d405_000000",
  "handover_phase": "approach",
  "handover_confidence": 0.0,
  "handover_gate": "blocked_by_memory",
  "release_allowed": false,
  "gate_reason": "not_ready",
  "memory_ready": false,
  "safety_ok": true,
  "candidate_action": {
    "type": "safe_hold",
    "release_request": false
  },
  "gated_action": {
    "type": "safe_hold",
    "release_executed": false
  }
}
```

字段语义：

- `handover_phase`：当前交互阶段。
- `handover_confidence`：当前阶段或 ready 判断置信度。
- `handover_gate`：最终 gate 类别。
- `release_allowed`：本周期是否允许释放。
- `gate_reason`：拒绝或允许 release 的可读原因。
- `memory_ready`：collaboration memory 是否认为已经 ready。
- `safety_ok`：安全规则是否全部满足。
- `candidate_action`：VLA 或操作者候选动作。
- `gated_action`：经过 gate 后实际允许执行的动作。

`release_decision` 必须能写入 episode 日志、回放视图和验证报告。后续命名可以扩展，但不得丢失上述语义。

## 5. 成功与危险条件冻结

交接成功条件冻结为：

- 工具从夹爪释放前，`handover_phase=ready`。
- `release_allowed=true` 且 `handover_gate=allowed_release`。
- 工具释放后由 `human_hand` 稳定接住。
- 短时间验证窗口内无掉落。
- 短时间验证窗口内无夹爪或机器人对人手的危险接触。
- episode 结果、release 时间和 gate 日志可追溯。

危险交接条件冻结为：

- `approach`、`stabilization`、`hesitation` 或 `retreat` 阶段提前松手。
- 人手正在后撤时松手。
- 人手晃动或姿态未稳定时松手。
- 人手追踪丢失或低置信度时松手。
- 工具掉落。
- 夹爪、工具或机器人连杆与人手发生危险接触。
- `candidate_action` 请求 release 但缺少对应的 gate 记录。

危险条件出现时，episode 不能作为正常正样本进入训练候选；可以作为调试样本、gate 负样本或评估样本，但必须明确标记。

## 6. 对后续里程碑的约束

S5 之后的开发约束如下：

- `S6` 必须验证 D405 是 `quest3_safe_handover_v1` 的训练主视觉来源。
- `S7` 必须加入可记录、可碰撞、可由 Quest3 右手控制的 `human_hand`。
- `S8` 数据集必须保存 `release_decision`、relation feature、phase 标签、candidate action 和 gated action。
- `S9` collaboration memory 只训练“什么时候可以 release”，不直接控制机械臂。
- `S10` pi0.5 LoRA 只训练抓取、递送、对齐和保持，不绕过 gate 学习最终 release。
- `S11` interaction gating 必须把 memory 输出、安全规则和候选动作合并为最终执行动作。
- `S12` 未来真实机械臂 release 必须保留 safety gate 和人工确认约束。

正式协作数据必须来自 Quest3 人工双边示教。脚本只能用于 camera smoke test、接口测试、固定姿态检查或回放验证，不能冒充正式协作采集数据。

## 7. S5 验收结论

S5 冻结结论：

- 文档层主任务已经切换为 `quest3_safe_handover_v1`。
- 后续未开始任务围绕安全交接时机理解展开。
- 现有工具场景、VR 控制、D405 和物理边界继续服务新任务。
- VLA、collaboration memory 和 interaction gating 的职责边界已经冻结。
