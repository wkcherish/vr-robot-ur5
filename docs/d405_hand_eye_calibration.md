# D405 手眼标定与真实场景外参校准

更新时间：`2026-06-08`

本文用于判断末端 Intel RealSense D405 是否已经达到真实场景采集要求。这里的“真实”不是只看 CAD 装配是否像照片，而是要求相机坐标、UR5 末端坐标和 MuJoCo/真实工作台坐标之间的几何关系可以被复现和追溯。

## 1. 当前状态判断

当前 MuJoCo 场景可以作为仿真开发和调试基线：

- UR5、Robotiq、工具、工具箱、桌面和 D405 都能加载并稳定仿真。
- D405 RGB/Depth 能输出非空帧。
- D405 固定随腕部运动，不是外部观察相机。

但当前还不能声明为真实场景姿态已闭环：

- `shared/camera_sensor_config.json` 中的 D405 外参来自 CAD/照片估计，不是手眼标定结果。
- `backend/mujoco_models/ur5.xml` 中 D405 `focalpixel/principalpixel` 仍是名义值或占位值，除非已经运行真实 D405 内参写回脚本。
- 当前 home 姿态下，D405 主要朝桌面工作区，能看到部分工具和工具箱，但不一定同时看到夹爪、目标工具和放置区域。

因此：

- 纯 MuJoCo 内部数据采集：可以先用当前配置做 debug/pilot，但必须把数据标记为 `sim_nominal_camera_uncalibrated`。
- 面向真实 UR5/D405 或 sim2real 的训练数据：必须先完成内参读取和手眼外参标定。

## 2. 是否需要手眼标定

需要。D405 是固定在 UR5 末端/腕部的 eye-in-hand 相机，训练和回放依赖以下变换：

```text
T_base_camera = T_base_wrist_or_tool * T_wrist_or_tool_camera
```

其中：

- `T_base_wrist_or_tool` 来自 UR5 正运动学。
- `T_wrist_or_tool_camera` 是 D405 相对腕部或 `tool0` 的固定外参。

当前 XML/JSON 只给了 `T_wrist_or_tool_camera` 的名义值。真实夹具装配会有毫米级位移误差和数度角度误差；对近距离 D405 来说，这会明显改变画面中夹爪、工具和目标区的位置。仅靠照片估计不够。

## 3. 标定内容

最少需要两类标定。

### 3.1 D405 内参

目标：得到真实设备在采集分辨率下的 `fx/fy/ppx/ppy`。

执行：

```bash
conda activate wk_vr_ur5
python backend/d405_intrinsics.py --width 1280 --height 720 --fps 30 --apply
```

通过后应更新：

- `backend/mujoco_models/ur5.xml`
- `shared/camera_sensor_config.json`
- `data/calibration/camera_intrinsics/<intrinsics_version>.json`

### 3.2 D405 手眼外参

目标：得到 `T_wrist_3_link_camera` 或 `T_tool0_camera`。

推荐优先冻结为：

```text
parent_frame = wrist_3_link
child_frame = d405_color_optical_frame
```

原因：当前 MuJoCo 中相机和夹具实际挂在 `wrist_3_link` 下，`tool0` 更适合作为末端控制/广播语义帧。

标定板方案：

1. 固定 AprilTag/ChArUco 标定板在工作台上，测量或估计其在 robot base 下的位姿。
2. 让 UR5 带着 D405 从 12 个以上不同姿态观察标定板。
3. 每个姿态记录：
   - UR5 关节角。
   - `T_base_wrist_3_link` 或 `T_base_tool0`。
   - D405 RGB 图像。
   - 标定板在相机下的 `T_camera_target`。
4. 用 eye-in-hand 求解 `T_wrist_3_link_camera`。
5. 把结果写入：
   - `data/calibration/camera_extrinsics/<extrinsics_version>.json`
   - `data/calibration/mounts/wrist_d405_v1.json`
   - `shared/camera_sensor_config.json`
   - 必要时同步更新 `backend/mujoco_models/ur5.xml` 的 camera `pos/quat`。

## 4. 采集姿态要求

标定姿态不要只在一个小范围内移动。至少覆盖：

- 近/中/远三个距离。
- 左/中/右三个横向位置。
- 相机绕光轴或腕部有明显转动。
- 标定板出现在画面中心、左上、右下等不同区域。
- 避免全部姿态共面或只改变一个关节。

建议采 20-30 组，筛掉模糊、遮挡、角点检测不稳定的样本。

## 5. 验收标准

内参验收：

- `intrinsics_reference.source = pyrealsense2_measured_device_intrinsics`。
- RGB 能正常解码，Depth 非全零、非全 NaN。
- principal point 不再只是未测量的默认占位值。

外参验收：

- 重投影误差稳定，优先低于 1-2 px；如果真实噪声较大，可先接受低于 3 px 的 pilot。
- 在 3-5 个未参与标定的验证姿态中，MuJoCo D405 画面和真实 D405 画面的夹爪、工具、桌面相对位置一致。
- 近距离工具位置误差不应明显影响抓取可见性；经验上相机位姿误差应尽量控制在约 5 mm / 2 deg 以内。
- `camera_pose_in_base` 随机器人运动连续，无跳变。

## 6. 当前可以怎样推进

如果当前目标只是验证软件链路：

- 可以继续做 debug/pilot。
- 数据只能用于接口、回放、转换脚本、训练管线 smoke test。
- 不要把这些 episode 标记为真实训练候选。

如果目标是采集将来要训练并可能迁移到真实 UR5 的数据：

- 先做真实 D405 内参。
- 再做手眼外参。
- 再用 camera-only smoke test 检查抓取、移动、放置阶段视野。
- 通过后再批量采集。

## 7. 需要避免的误区

- 只让 MuJoCo 画面看起来“差不多”不等于真实外参正确。
- 只标内参不等于完成手眼标定。
- 只用一张安装照片不能确定 D405 光心和光轴。
- Quest3 页面画面、Three.js 外部相机或 MP4 预览不能替代 D405 训练观测。
- 如果 D405 在关键阶段看不到夹爪或工具，数据中即使有机器人状态，也不适合作为视觉动作训练样本。
