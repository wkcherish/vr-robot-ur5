# 里程碑 0：范围与成功标准冻结

更新时间：`2026-04-07`

## 1) 当前工作约定

- 当前开发分支：`feat/milestone-0-a-foundation`
- 分支命名规则：`feat/<milestone>-<topic>`（例如 `feat/milestone-b-backend-bootstrap`）
- 文档维护方式：
  - 需求与分析主文档：`docs/task.md`
  - 执行清单：`docs/todolist.md`
  - 里程碑冻结产物：`docs/m0_scope_and_success.md`、`docs/mA_alignment_and_protocol.md`
  - 共享场景清单：`shared/scene_manifest.json`

## 2) M0 决策冻结

- 后端主技术栈固定为：`FastAPI + Python MuJoCo`
- 第一版任务名固定为：`battery_transfer_v1`
- 第一版对象范围固定为：`UR5 + 完整 Robotiq 手抓 + battery_pack + rack + camera_base + camera`
- 第一版 battery 处理方式固定为：`battery_pack` 整体刚体
- “连接机器人”默认解释固定为：连接仿真后端，不是实体机器人
- 后端 MuJoCo 夹爪实现固定要求：必须保留完整 Robotiq 关键关节链，不得简化为单自由度抽象夹爪
- RL 框架默认候选：`stable-baselines3`（后续可在不破坏协议前提下替换）

## 3) 第一版成功标准（冻结版）

- 前端机械臂动作可以驱动 MuJoCo 中的 UR5 和完整 Robotiq 手抓同步动作
- MuJoCo 执行动作或任务时，前端模型同步更新
- MuJoCo 场景中的 UR5、rack、battery_pack、camera_base、camera 与前端场景一致
- `battery_transfer_v1` 可先通过脚本化方式跑通
- 训练好的 RL 策略可由前端“执行任务”触发
- 夹爪实现必须保持前后端结构一致，禁止后端抽象简化

## 4) 对后续里程碑的约束

- 任何会改变场景位姿、关节顺序、协议字段的改动，都必须同步更新：
  - `shared/scene_manifest.json`
  - `docs/mA_alignment_and_protocol.md`
  - `docs/todolist.md`
- 若改动破坏以上冻结项，必须先在文档中显式记录“变更原因 + 影响范围 + 回滚方式”。
