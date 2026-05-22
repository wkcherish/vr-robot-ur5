# D405 真实内参与 MuJoCo 光轴验证步骤

本步骤用于确认 MuJoCo 第一人称 `d405_rgb` / `d405_depth` 与真实 Intel RealSense D405 的实测光轴对应。仅让画面看起来居中不算通过；必须读取真实相机的 `fx/fy/ppx/ppy` 并写回 MuJoCo。

## 1. 连接真实 D405

1. 用支持数据传输的 USB-C 线连接 D405 和电脑。
2. 优先插电脑 USB 3.x 口，避免使用普通扩展坞。
3. 检查系统是否识别到 RealSense：

```bash
lsusb | grep -i real
```

如果本机装了 RealSense 工具，也可以执行：

```bash
rs-enumerate-devices
```

能看到 D405 后再继续。

## 2. 读取实测内参

在项目根目录运行：

```bash
python backend/d405_intrinsics.py --width 1280 --height 720 --fps 30
```

脚本会输出：

- `width`
- `height`
- `fx`
- `fy`
- `ppx`
- `ppy`
- 图像中心 `(width / 2, height / 2)`
- OpenCV/RealSense principal point 相对图像中心的偏移
- MuJoCo 需要的 `focalpixel`
- MuJoCo 需要的 `principalpixel`

如果报错 `pyrealsense2 is not installed in this Python environment`，说明当前 Python 环境还没有 RealSense Python 包，需要先安装或切换到已安装 `pyrealsense2` 的环境。

## 3. 写回 MuJoCo 配置

确认读取结果来自真实 D405 后，执行：

```bash
python backend/d405_intrinsics.py --width 1280 --height 720 --fps 30 --apply
```

该命令会自动更新：

- `backend/mujoco_models/ur5.xml`
- `shared/camera_sensor_config.json`
- `data/calibration/camera_intrinsics/<intrinsics_version>.json`

换算规则为：

```text
mujoco_principalpixel_x = ppx - width / 2
mujoco_principalpixel_y = height / 2 - ppy
```

注意：RealSense/OpenCV 的像素 `y` 轴向下，MuJoCo 的 principal point 偏移 `y` 按向上为正理解，因此 `y` 方向需要反号。

## 4. RGB-D 对齐选择

默认命令按“Depth 已对齐到 RGB/color”的方式处理：

```bash
python backend/d405_intrinsics.py --width 1280 --height 720 --fps 30 --apply
```

这适合当前 MuJoCo 里 `d405_rgb` 与 `d405_depth` 同视角、同 pose 的简化模型。

如果要读取 RealSense 原始 depth 流自己的内参，使用：

```bash
python backend/d405_intrinsics.py --depth-mode raw-depth --apply
```

但 raw depth 与 RGB 之间还存在真实外参/基线关系；仅写入 raw depth 内参不等于完整建模 D405 双目深度几何。

## 5. 验证通过标准

执行 `--apply` 后需要重新启动后端和 MuJoCo viewer，并检查：

1. `d405_rgb` 和 `d405_depth` 能正常输出。
2. `backend/mujoco_models/ur5.xml` 中 `focalpixel`、`principalpixel` 不再只是占位值。
3. `shared/camera_sensor_config.json` 中 `intrinsics_reference.source` 变为 `pyrealsense2_measured_device_intrinsics`。
4. `data/calibration/camera_intrinsics/` 下存在本次生成的内参 JSON。
5. MuJoCo 第一人称画面中，夹爪、工具、桌面和 handover zone 的位置关系与真实 D405 画面大体一致。

本步骤只校准相机内参和图像光轴。相机在末端夹具上的真实三维位置与朝向仍由挂载外参决定；如果实拍画面与仿真画面整体平移、旋转或高度明显不一致，需要继续校准 `camera_pose_in_ee` / MuJoCo camera `pos`、`quat`。
