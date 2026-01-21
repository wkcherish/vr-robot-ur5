# 关节顺序映射验证报告

## 关节映射表

| 关节索引 | 标准名称 | URDF名称 | MJCF名称 | 前端名称 | 状态 |
|-----------|----------|----------|----------|----------|------|
| 0 | shoulder_pan | link1_joint | shoulder_pan_joint | link1_joint | [OK] |
| 1 | shoulder_lift | link2_joint | shoulder_lift_joint | link2_joint | [OK] |
| 2 | elbow | link3_joint | elbow_joint | link3_joint | [OK] |
| 3 | wrist_1 | link4_joint | wrist_1_joint | link4_joint | [OK] |
| 4 | wrist_2 | link5_joint | wrist_2_joint | link5_joint | [OK] |
| 5 | wrist_3 | link6_joint | wrist_3_joint | link6_joint | [OK] |

## 详细验证结果

### shoulder_pan (索引: 0)

- **URDF**: link1_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **MJCF**: shoulder_pan_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **前端**: link1_joint (索引: 0)

### shoulder_lift (索引: 1)

- **URDF**: link2_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **MJCF**: shoulder_lift_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **前端**: link2_joint (索引: 1)

### elbow (索引: 2)

- **URDF**: link3_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-3.141592653589793, 3.141592653589793]
- **MJCF**: elbow_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-3.141592653589793, 3.141592653589793]
- **前端**: link3_joint (索引: 2)

### wrist_1 (索引: 3)

- **URDF**: link4_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **MJCF**: wrist_1_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **前端**: link4_joint (索引: 3)

### wrist_2 (索引: 4)

- **URDF**: link5_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **MJCF**: wrist_2_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **前端**: link5_joint (索引: 4)

### wrist_3 (索引: 5)

- **URDF**: link6_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **MJCF**: wrist_3_joint
  - 轴: [0.0, 0.0, 1.0]
  - 范围: [-6.283185307179586, 6.283185307179586]
- **前端**: link6_joint (索引: 5)

## 总体状态: [OK] 所有关节映射一致