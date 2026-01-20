# UR5 机器人 URDF 结构分析

## 📋 概述
- **机器人型号**: UR5 (Universal Robots)
- **关节数量**: 7 个关节（6个主要关节 + 1个夹爪关节）
- **坐标系**: 右手坐标系，Z轴向上
- **URDF 文件**: `public/ur5/ur5.urdf`

## 🔗 关节层级关系

### 关节链结构
```
world (固定关节)
└── base_link
    ├── link1_joint (revolute) → shoulder_link
    │   ├── link2_joint (revolute) → upper_arm_link
    │   │   ├── link3_joint (revolute) → forearm_link
    │   │   │   ├── link4_joint (revolute) → wrist_1_link
    │   │   │   │   ├── link5_joint (revolute) → wrist_2_link
    │   │   │   │   │   ├── link6_joint (revolute) → wrist_3_link
    │   │   │   │   │   │   └── link7_joint (revolute) → gr_link (夹爪)
    │   │   │   │   │   │       └── link7_joint (fixed) → world (循环连接)
    │   │   │   │   │   └── link7_joint (fixed) → world (循环连接)
    │   │   │   │   └── link7_joint (fixed) → world (循环连接)
    │   │   │   └── link7_joint (fixed) → world (循环连接)
    │   │   └── link7_joint (fixed) → world (循环连接)
    │   └── link7_joint (fixed) → world (循环连接)
    └── link7_joint (fixed) → world (循环连接)
```

### 关节参数详情

| 关节名称 | 类型 | 父链接 | 子链接 | 轴向 | 角度范围 | 最大力矩 | 最大速度 |
|----------|------|--------|--------|------|----------|----------|----------|
| link1_joint | revolute | base_link | shoulder_link | Z轴 (0,0,1) | ±360° | 150.0 N·m | 3.15 rad/s |
| link2_joint | revolute | shoulder_link | upper_arm_link | Z轴 (0,0,1) | ±360° | 150.0 N·m | 3.15 rad/s |
| link3_joint | revolute | upper_arm_link | forearm_link | Z轴 (0,0,1) | ±180° | 150.0 N·m | 3.15 rad/s |
| link4_joint | revolute | forearm_link | wrist_1_link | Z轴 (0,0,1) | ±360° | 28.0 N·m | 3.2 rad/s |
| link5_joint | revolute | wrist_1_link | wrist_2_link | Z轴 (0,0,1) | ±360° | 28.0 N·m | 3.2 rad/s |
| link6_joint | revolute | wrist_2_link | wrist_3_link | Z轴 (0,0,1) | ±360° | 28.0 N·m | 3.2 rad/s |
| link7_joint | revolute | wrist_3_link | gr_link | Y轴 (0,1,0) | ±360° | 28.0 N·m | 6.28 rad/s |

## 📐 坐标变换

### 关节原点位置 (xyz in meters)

| 关节名称 | 相对于父关节的位移 | 旋转 (rpy in radians) |
|----------|---------------------|----------------------|
| base_link | world → base_link: [0, 0, 0] | [0, 0, 0] |
| link1_joint | base_link → shoulder_link: [0, 0, 0.0893] | [0, 0, 0] |
| link2_joint | shoulder_link → upper_arm_link: [0.000014, 0, 0] | [1.5702, 0, 0.000024] |
| link3_joint | upper_arm_link → forearm_link: [-0.4255, 0, 0] | [0.0009, 0.0015, -0.000035] |
| link4_joint | forearm_link → wrist_1_link: [-0.3925, 0.00004, 0.1098] | [3.1412, -3.1404, 3.1416] |
| link5_joint | wrist_1_link → wrist_2_link: [0.00007, -0.0949, 0.00004] | [1.5703, 0, -0.00006] |
| link6_joint | wrist_2_link → wrist_3_link: [-0.00009, 0.0827, 0.00003] | [1.5711, 3.1416, 3.1416] |
| link7_joint | wrist_3_link → gr_link: [0, 0.09, 0] | [1.57, 0, 0] |

## 📁 Mesh 文件清单

### Visual Meshes (DAE格式)
- `base.dae` - 底座视觉网格
- `shoulder.dae` - 肩部视觉网格
- `upperarm.dae` - 上臂视觉网格
- `forearm.dae` - 前臂视觉网格
- `wrist1.dae` - 腕部1视觉网格
- `wrist2.dae` - 腕部2视觉网格
- `wrist3.dae` - 腕部3视觉网格
- `grasp.dae` - 夹爪视觉网格 (缩放: 0.001)

### Collision Meshes (STL格式)
- `base.stl` - 底座碰撞网格
- `shoulder.stl` - 肩部碰撞网格
- `upperarm.stl` - 上臂碰撞网格
- `forearm.stl` - 前臂碰撞网格
- `wrist1.stl` - 腕部1碰撞网格
- `wrist2.stl` - 腕部2碰撞网格
- `wrist3.stl` - 腕部3碰撞网格
- `grasp.stl` - 夹爪碰撞网格

## ⚖️ 惯性参数

| 链接名称 | 质量 (kg) | 惯性矩 (kg·m²) | 重心位置 (m) |
|----------|-----------|----------------|-------------|
| base_link | 4.0 | ixx=0.0044, iyy=0.0044, izz=0.0072 | [0, 0, 0] |
| shoulder_link | 3.7 | ixx=0.0150, iyy=0.0150, izz=0.0104 | [0, 0, 0] |
| upper_arm_link | 8.393 | ixx=0.1342, iyy=0.1342, izz=0.0151 | [-0.2128, 0, 0.136] |
| forearm_link | 2.275 | ixx=0.0313, iyy=0.0313, izz=0.0041 | [-0.2128, 0, 0.0165] |
| wrist_1_link | 1.219 | ixx=0.0026, iyy=0.0026, izz=0.0034 | [0, 0, 0] |
| wrist_2_link | 1.219 | ixx=0.0018, iyy=0.0018, izz=0.0022 | [0, 0, 0] |
| wrist_3_link | 0.1879 | ixx=0.00008, iyy=0.00008, izz=0.00013 | [0, 0, -0.0153] |
| gr_link | 0.1879 | ixx=0.000099, iyy=0.000099, izz=0.00013 | [0, 0.0771, 0] |

## 🔄 MuJoCo 转换注意事项

1. **关节映射**: UR5的6个主要关节对应 MuJoCo 中的 shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3
2. **坐标系对齐**: URDF 使用 Z轴向上，MuJoCo 也使用 Z轴向上，无需额外转换
3. **Mesh 路径**: 需要将所有 mesh 文件复制到 `mujoco_models/meshes/` 目录
4. **执行器配置**: 需要为每个关节添加 PD 位置控制器
5. **传感器添加**: 建议添加关节位置、速度、力矩传感器

## 📝 关键发现

1. **关节顺序**: 关节顺序与标准 UR5 定义一致 (shoulder_pan → shoulder_lift → elbow → wrist_1 → wrist_2 → wrist_3)
2. **坐标系**: 所有关节都围绕 Z轴旋转，符合工业机器人标准
3. **力矩分布**: 肩部和肘部关节力矩较大 (150N·m)，腕部关节力矩较小 (28N·m)
4. **Mesh 完整性**: 同时提供视觉网格 (DAE) 和碰撞网格 (STL)，满足仿真需求
5. **夹爪集成**: 包含 Robotiq 85 夹爪模型，可以选择性包含

---

