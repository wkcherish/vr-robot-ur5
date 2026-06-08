# MuJoCo UR5 丝滑性与真实物理调参记录（2026-05-28）

目标：解决当前仓库里 UR5 + Robotiq 在 MuJoCo 中“动作不丝滑、接触发硬、抓取时容易抖”的问题，并把调参依据落到官方文档。

## 1. 本轮代码改动

- `backend/mujoco_models/ur5.xml`
  - 将 UR5 与夹爪 actuator 从手写 `general` 位置伺服改为 `position` actuator。
  - 为 actuator 增加 `dampratio` 与 `timeconst`，让目标角变化先经过一阶滤波，再按阻尼比驱动关节。
  - 提高大臂/腕部/夹爪机构的 `damping` 与 `armature`，降低高频振荡。
  - 将接触 `solref` 从 `0.004~0.006` 放宽到 `0.01~0.012`，减少“硬碰硬”。
  - 在默认 `mesh` 上增加 `maxhullvert="64"`，降低机器人碰撞 hull 复杂度。

- `backend/sim/simulation.py`
  - 手臂 actuator 控制从“目标角减 qpos0 偏移”切到“直接给关节目标角”。
  - 夹爪不再在每个 physics step 里强制写所有关节 `qpos/qvel`，改为持续写 actuator target。
  - 保留 reset 时的硬同步，但运行时抓取/接触走 MuJoCo 动力学。

- `backend/main.py`
  - viewer 桥接同步改成与新 actuator 语义一致：`ctrl` 直接表示目标关节角。

- `backend/mujoco_models/environment.xml` 与工具/货架模型
  - 放宽接触 `solref`。
  - 将 solver 精度从 `iterations=120 / noslip=16 / tolerance=1e-10` 调到更现实的 `90 / 8 / 1e-8`，减轻实时仿真负担。

## 2. 根因判断

当前项目里“不丝滑”主要不是单一问题，而是三层叠加：

1. 位置伺服太硬  
   旧 `general` actuator 直接把网络/VR 的目标角变成高刚度 PD 力矩，目标一抖，力矩就抖。

2. 夹爪是“伪动力学”  
   运行时每步直接重写夹爪 joint `qpos/qvel`，接触一发生就会把物体顶开或夹爪反复打架。

3. 接触与求解器过硬  
   `dt=0.001` 下还使用 `solref=0.004~0.006` 和很严的 solver 容差，抓取时容易表现成“硬、抖、费算力”。

## 3. MuJoCo 官方调参原则

### 3.1 关节伺服优先用 `position` actuator

MuJoCo 官方 XML Reference 明确给了 `position` actuator，并支持：

- `timeconst`：控制输入一阶滤波
- `dampratio`：按系统惯量自动配阻尼

这比手工堆 `gainprm/biasprm` 更适合机械臂位置伺服，尤其是 Quest/网络输入这种本身带采样抖动的场景。

参考：
- https://mujoco.readthedocs.io/en/stable/XMLreference.html#actuator-position

### 3.2 `solref` 的 time constant 不要贴着 timestep 走

MuJoCo 建模文档明确指出，接触/约束的 `solref` 里 `timeconst` 至少应大于 `2 * timestep`。  
本项目虽然没有违反下限，但 `0.004` 对 `dt=0.001` 仍偏硬，抓取时常会显得“脆”。

经验上：

- 桌面机械臂自由运动：伺服可偏硬
- 夹爪接触/抓取：`solref` 更适合落在 `0.008~0.02`

参考：
- https://mujoco.readthedocs.io/en/stable/modeling.html#solver-parameters

### 3.3 `armature` 很重要，它代表电机反射惯量

MuJoCo 官方对 `joint/armature` 的解释就是 actuator 反射到关节侧的转子惯量。  
机械臂如果只给 link 惯量、不补 armature，常见现象就是：

- 关节太“轻”
- 伺服容易高频振
- `kp` 一上去就不自然

参考：
- https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-joint

### 3.4 碰撞几何应尽量简化

MuJoCo 官方建模文档建议尽量用 fitted primitives 或更简单的凸几何，而不是复杂 mesh 直接参与碰撞。  
如果暂时不能重建 collision proxy，至少要限制 convex hull 顶点数，例如 `maxhullvert`。

参考：
- https://mujoco.readthedocs.io/en/stable/modeling.html#fitted-primitives
- https://mujoco.readthedocs.io/en/stable/XMLreference.html#compiler

## 4. 机械臂仿真的推荐调参顺序

建议以后按这个顺序调，不要一上来就只改 `kp`：

1. 先校正质量、惯量、COM  
   质量和惯量不对，后面所有 damping / kp 都会假。

2. 再补 `armature` 和基础 `damping`  
   让系统先“像一台真实电机驱动的机械臂”。

3. 再定 actuator
   - 优先 `position`
   - 先定 `kp`
   - 再用 `dampratio≈1.0~1.2`
   - 然后给 `timeconst≈0.02~0.05`

4. 接着调接触
   - 抓取 pad / 工具 / 桌面先调 `solref`
   - 再调 `friction`
   - 最后再碰 solver iterations

5. 最后才看实时性能
   - solver 太重就降 `iterations`
   - collision 太贵就简化碰撞 proxy

## 5. 对本仓库的后续建议

- `P0` 为 UR5 link 建一套更简单的 collision proxy（capsule / box / convex proxy），替代当前 mesh collision。
- `P0` 在装有 MuJoCo 的主机上做三组回归：
  - 空载关节阶跃响应
  - 夹爪闭合抓取工具响应
  - 工具接触桌面后的稳定性与实时帧率
- `P1` 记录量化指标：
  - `robot_motion_jitter`
  - `ee_settle_time_ms`
  - `grasp_contact_bounce_count`
  - `sim_step_ms`

## 6. 当前限制

当前工作区环境里没有安装 `mujoco` Python 包，所以本轮完成的是：

- 代码层修复
- XML 静态校验
- Python 语法校验

还没完成的是：

- 在真实 MuJoCo 运行时的动态回归
- 对比修改前后的抓取视频/轨迹数据
