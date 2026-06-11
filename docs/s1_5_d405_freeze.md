# 里程碑 S1.5 冻结说明（D405 RGB-D）

更新时间：`2026-04-12`

本文件用于冻结 `S1.5` 的主视觉传感器、挂载方式、仿真接口、标定版本与录制字段规范。

真实 D405 内参验证步骤见 [docs/d405_real_intrinsics_validation.md](d405_real_intrinsics_validation.md)。末端 D405 作为 eye-in-hand 相机时，还需要手眼外参标定，见 [docs/d405_hand_eye_calibration.md](d405_hand_eye_calibration.md)。

## 1. 主传感器角色冻结

- 主视觉设备：`Intel RealSense D405`
- 主模态：`RGB-D`
- 角色：`primary_capture_sensor`
- `camera / camera_base`：仅保留为 `debug_only` 参考对象，不再作为主采集相机

对应配置：

- `shared/camera_sensor_config.json`
- `shared/scene_manifest.json` 的 `sensor_policy`

## 2. 资产与安装参考冻结

资产角色冻结如下：

- `frontend/public/camera/mesh/d405.stl`：相机主体
- `frontend/public/camera/mesh/前半.STL`：末端安装结构前半
- `frontend/public/camera/mesh/后半.STL`：末端安装结构后半
- `pic/camera.jpg`：真实安装参考图

安装语义冻结如下：

- D405 固定在夹爪上方附近，靠近末端法兰（不是外部俯视相机）
- 相机主视轴朝向抓取工作区
- 线缆由相机顶部/后侧引出，安装时预留线缆运动空间

## 3. MuJoCo 挂载与输出接口冻结

仿真挂载：

- 挂载父坐标：`wrist_3_link`
- 安装方案名：`wrist_d405_v1`
- 名义固定外参：见 `shared/camera_sensor_config.json` 的 `primary_sensor.mount`
- MuJoCo 相机名：
  - `d405_rgb`
  - `d405_depth`
- 挂载定义位置：`backend/mujoco_models/ur5.xml`

当前外参是 CAD/照片估计值，只适合仿真调试和 pilot。正式真实场景数据采集前，应通过手眼标定生成 `T_wrist_3_link_camera` 或 `T_tool0_camera`，并更新 `camera_extrinsics_version`。

输出接口：

- `GET /sim/observation/`
- `GET /sim/camera/rgb/`
- `GET /sim/camera/depth/`
- WebSocket：
  - `get_observation`
  - `get_camera_rgb`
  - `get_camera_depth`

接口语义：

- `rgb` 与 `depth` 都是“可录制训练观测”，不是仅页面展示
- 默认冻结规格：
  - 分辨率：`640x480`
  - 帧率：`30 FPS`
  - 对齐模式：`same_tick`
  - 最大时间戳偏差：`5 ms`

## 4. 标定命名与目录规范冻结

版本命名冻结：

- `camera_mount_name`: `wrist_d405_v1`
- `camera_intrinsics_version`: `d405_intr_20260412_a`
- `camera_extrinsics_version`: `d405_ext_20260412_a`
- 版本命名规则：
  - `d405_intr_YYYYMMDD_suffix`
  - `d405_ext_YYYYMMDD_suffix`

标定组织冻结（逻辑规范）：

- 根目录：`data/calibration/`
- 文件布局：
  - `camera_intrinsics/<intrinsics_version>.json`
  - `camera_extrinsics/<extrinsics_version>.json`
  - `mounts/<mount_name>.json`

真实内参写回流程：

- 先用 `backend/d405_intrinsics.py` 连接真实 D405 读取 `fx/fy/ppx/ppy`
- 再用 `--apply` 写回 MuJoCo XML 与配置
- 详细操作见 [D405 真实内参与 MuJoCo 光轴验证步骤](d405_real_intrinsics_validation.md)

## 5. 录制前置字段冻结

冻结文件：`shared/dataset_schema.json`

强制样本结构：

- `RGB-D + 状态 + 动作 + 文本`
- 每步动作必须有 `paired_frame_id`
- `instruction_text` 必须进入 episode 元数据与单步样本
- 录制器必须校验 `RGB/Depth/状态/动作` 时间对齐

图像存储格式冻结：

- `RGB`：默认 `jpg`（允许 `png`）
- `Depth`：默认 `png16`（允许 `npy`）
- `Depth` 禁止有损格式

## 6. 开发顺序冻结

Quest3 / VR 模块必须在 S1.5 完成后推进：

1. 先完成 D405 主链路与录制字段冻结
2. 再推进 Quest3/VR 控制与数据采集闭环
