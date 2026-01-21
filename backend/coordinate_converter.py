#!/usr/bin/env python3
"""
坐标系统转换工具
提供URDF、MJCF、Three.js之间的坐标转换
"""

import numpy as np
from typing import Tuple, List, Optional, Union
import math


class CoordinateConverter:
    """坐标系统转换器

    坐标系说明：
    - URDF: Y-up坐标系 (ROS标准)
    - MuJoCo/MJCF: Z-up坐标系 (MuJoCo标准)
    - Three.js: Y-up坐标系 (WebGL标准)

    转换关系：
    - URDF ↔ Three.js: 都是Y-up，通常无需转换
    - MuJoCo ↔ Three.js: Z-up ↔ Y-up，需要绕X轴旋转±90度
    """

    def __init__(self):
        # 定义坐标系统变换矩阵

        # URDF到Three.js的变换 (都是Y-up，所以通常是单位矩阵)
        self.urdf_to_threejs = np.eye(4)

        # MJCF到Three.js的变换 (Z-up 到 Y-up，需要旋转-90度绕X轴)
        self.mjcf_to_threejs = self._create_rotation_matrix(-np.pi/2, 'x')

        # Three.js到URDF的变换
        self.threejs_to_urdf = np.eye(4)

        # Three.js到MJCF的变换 (Y-up 到 Z-up，需要旋转+90度绕X轴)
        self.threejs_to_mjcf = self._create_rotation_matrix(np.pi/2, 'x')

        # 四元数转换矩阵（对应旋转矩阵）
        self.quaternion_mjcf_to_threejs = self._rotation_matrix_to_quaternion(self.mjcf_to_threejs[:3, :3])
        self.quaternion_threejs_to_mjcf = self._rotation_matrix_to_quaternion(self.threejs_to_mjcf[:3, :3])

    def _create_rotation_matrix(self, angle: float, axis: str) -> np.ndarray:
        """创建旋转矩阵"""
        c = np.cos(angle)
        s = np.sin(angle)

        if axis == 'x':
            return np.array([
                [1, 0, 0, 0],
                [0, c, -s, 0],
                [0, s, c, 0],
                [0, 0, 0, 1]
            ])
        elif axis == 'y':
            return np.array([
                [c, 0, s, 0],
                [0, 1, 0, 0],
                [-s, 0, c, 0],
                [0, 0, 0, 1]
            ])
        elif axis == 'z':
            return np.array([
                [c, -s, 0, 0],
                [s, c, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])
        else:
            raise ValueError(f"Unknown axis: {axis}")

    def _rotation_matrix_to_quaternion(self, rotation_matrix: np.ndarray) -> np.ndarray:
        """将旋转矩阵转换为四元数"""
        m = rotation_matrix
        trace = np.trace(m)

        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (m[2, 1] - m[1, 2]) * s
            y = (m[0, 2] - m[2, 0]) * s
            z = (m[1, 0] - m[0, 1]) * s
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif m[1, 1] > m[2, 2]:
            s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s

        return np.array([w, x, y, z])

    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """四元数乘法"""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2

        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

        return np.array([w, x, y, z])

    def _normalize_quaternion(self, q: np.ndarray) -> np.ndarray:
        """归一化四元数"""
        norm = np.linalg.norm(q)
        if norm > 0:
            return q / norm
        return q

    def urdf_to_threejs_transform(self, position: List[float],
                                rotation: Optional[List[float]] = None) -> Tuple[List[float], Optional[List[float]]]:
        """
        URDF坐标系转换到Three.js坐标系

        Args:
            position: 位置 [x, y, z]
            rotation: 旋转 (四元数或欧拉角) [w, x, y, z] 或 [roll, pitch, yaw]

        Returns:
            转换后的位置和旋转
        """
        # URDF和Three.js都是Y-up坐标系，通常不需要变换
        # 但可能需要根据具体的模型设置进行调整
        return position, rotation

    def mjcf_to_threejs_transform(self, position: List[float],
                                rotation: Optional[List[float]] = None) -> Tuple[List[float], Optional[List[float]]]:
        """
        MJCF坐标系转换到Three.js坐标系

        Args:
            position: 位置 [x, y, z]
            rotation: 旋转 (四元数 [w, x, y, z] 或欧拉角 [roll, pitch, yaw])

        Returns:
            转换后的位置和旋转
        """
        # 将位置转换为齐次坐标
        pos_homogeneous = np.array(position + [1])

        # 应用变换
        transformed_pos = np.dot(self.mjcf_to_threejs, pos_homogeneous)[:3]

        # 处理旋转
        transformed_rotation = rotation
        if rotation:
            if len(rotation) == 4:
                # 四元数旋转变换
                transformed_rotation = self._quaternion_multiply(self.quaternion_mjcf_to_threejs, rotation)
                transformed_rotation = self._normalize_quaternion(transformed_rotation)
            elif len(rotation) == 3:
                # 欧拉角 - 先转换为四元数，转换，再转回欧拉角
                # 这里简化处理，实际应用中可能需要更精确的转换
                pass

        return transformed_pos.tolist(), transformed_rotation.tolist() if transformed_rotation is not None else None

    def threejs_to_urdf_transform(self, position: List[float],
                                rotation: Optional[List[float]] = None) -> Tuple[List[float], Optional[List[float]]]:
        """
        Three.js坐标系转换到URDF坐标系
        """
        return position, rotation

    def threejs_to_mjcf_transform(self, position: List[float],
                                rotation: Optional[List[float]] = None) -> Tuple[List[float], Optional[List[float]]]:
        """
        Three.js坐标系转换到MJCF坐标系

        Args:
            position: 位置 [x, y, z]
            rotation: 旋转 (四元数 [w, x, y, z] 或欧拉角 [roll, pitch, yaw])

        Returns:
            转换后的位置和旋转
        """
        # 将位置转换为齐次坐标
        pos_homogeneous = np.array(position + [1])

        # 应用变换
        transformed_pos = np.dot(self.threejs_to_mjcf, pos_homogeneous)[:3]

        # 处理旋转
        transformed_rotation = rotation
        if rotation:
            if len(rotation) == 4:
                # 四元数旋转变换
                transformed_rotation = self._quaternion_multiply(self.quaternion_threejs_to_mjcf, rotation)
                transformed_rotation = self._normalize_quaternion(transformed_rotation)
            elif len(rotation) == 3:
                # 欧拉角转换
                pass

        return transformed_pos.tolist(), transformed_rotation.tolist() if transformed_rotation is not None else None

    def joint_angles_urdf_to_mjcf(self, urdf_angles: List[float]) -> List[float]:
        """
        将URDF关节角度转换为MJCF关节角度

        URDF和MJCF的关节顺序和符号可能不同
        """
        # 简化假设：直接映射，角度相同
        # 实际可能需要根据具体关节定义进行调整
        return urdf_angles.copy()

    def joint_angles_mjcf_to_threejs(self, mjcf_angles: List[float]) -> List[float]:
        """
        将MJCF关节角度转换为Three.js显示角度
        """
        # 将弧度转换为角度用于Three.js显示
        return [np.rad2deg(angle) for angle in mjcf_angles]

    def joint_angles_threejs_to_mjcf(self, threejs_angles: List[float]) -> List[float]:
        """
        将Three.js角度转换为MJCF弧度角度
        """
        # 将角度转换为弧度用于MJCF
        return [np.deg2rad(angle) for angle in threejs_angles]

    def euler_to_quaternion(self, roll: float, pitch: float, yaw: float) -> List[float]:
        """欧拉角转换为四元数 (ZYX顺序)"""
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return [w, x, y, z]

    def quaternion_to_euler(self, w: float, x: float, y: float, z: float) -> List[float]:
        """四元数转换为欧拉角 (ZYX顺序)"""
        # 滚转角 (x轴旋转)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        # 俯仰角 (y轴旋转)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.copysign(np.pi / 2, sinp)  # 使用90度
        else:
            pitch = np.arcsin(sinp)

        # 偏航角 (z轴旋转)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return [roll, pitch, yaw]

    def validate_transforms(self) -> dict:
        """验证变换的正确性"""
        print("[INFO] 验证坐标变换...")

        # 测试基本变换
        test_position = [1.0, 2.0, 3.0]
        test_quaternion = [1.0, 0.0, 0.0, 0.0]  # 单位四元数

        # MJCF -> Three.js -> MJCF 应该恢复原值
        pos_mjcf_to_threejs, quat_mjcf_to_threejs = self.mjcf_to_threejs_transform(test_position, test_quaternion)
        pos_threejs_to_mjcf, quat_threejs_to_mjcf = self.threejs_to_mjcf_transform(pos_mjcf_to_threejs, quat_mjcf_to_threejs)

        position_error = np.linalg.norm(np.array(test_position) - np.array(pos_threejs_to_mjcf))

        # 四元数误差计算 (考虑四元数等价性 q ≈ -q)
        quat_error1 = np.linalg.norm(np.array(test_quaternion) - np.array(quat_threejs_to_mjcf))
        quat_error2 = np.linalg.norm(np.array(test_quaternion) - (-np.array(quat_threejs_to_mjcf)))
        quaternion_error = min(quat_error1, quat_error2)

        results = {
            'position_roundtrip_error': position_error,
            'quaternion_roundtrip_error': quaternion_error,
            'position_transforms_consistent': position_error < 1e-10,
            'quaternion_transforms_consistent': quaternion_error < 1e-10,
            'transforms_consistent': position_error < 1e-10 and quaternion_error < 1e-10,
            'urdf_to_threejs_matrix': self.urdf_to_threejs.tolist(),
            'mjcf_to_threejs_matrix': self.mjcf_to_threejs.tolist(),
            'threejs_to_mjcf_matrix': self.threejs_to_mjcf.tolist(),
            'quaternion_mjcf_to_threejs': self.quaternion_mjcf_to_threejs.tolist(),
            'quaternion_threejs_to_mjcf': self.quaternion_threejs_to_mjcf.tolist()
        }

        print(f"[INFO] 位置往返变换误差: {position_error}")
        print(f"[INFO] 四元数往返变换误差: {quaternion_error}")
        print(f"[INFO] 变换一致性: {'通过' if results['transforms_consistent'] else '失败'}")

        return results


def create_conversion_utilities():
    """创建转换工具函数"""
    converter = CoordinateConverter()

    # 关节顺序映射
    JOINT_MAPPING = {
        'urdf_to_mjcf': {
            'link1_joint': 'shoulder_pan_joint',
            'link2_joint': 'shoulder_lift_joint',
            'link3_joint': 'elbow_joint',
            'link4_joint': 'wrist_1_joint',
            'link5_joint': 'wrist_2_joint',
            'link6_joint': 'wrist_3_joint'
        },
        'mjcf_to_threejs': {
            'shoulder_pan_joint': 'link1_joint',
            'shoulder_lift_joint': 'link2_joint',
            'elbow_joint': 'link3_joint',
            'wrist_1_joint': 'link4_joint',
            'wrist_2_joint': 'link5_joint',
            'wrist_3_joint': 'link6_joint'
        }
    }

    def convert_joint_angles(from_format: str, to_format: str, angles: List[float]) -> List[float]:
        """
        转换关节角度

        Args:
            from_format: 源格式 ('urdf', 'mjcf', 'threejs')
            to_format: 目标格式 ('urdf', 'mjcf', 'threejs')
            angles: 关节角度列表

        Returns:
            转换后的关节角度
        """
        if from_format == to_format:
            return angles.copy()

        # URDF -> MJCF
        if from_format == 'urdf' and to_format == 'mjcf':
            return converter.joint_angles_urdf_to_mjcf(angles)

        # MJCF -> Three.js
        elif from_format == 'mjcf' and to_format == 'threejs':
            return converter.joint_angles_mjcf_to_threejs(angles)

        # Three.js -> MJCF
        elif from_format == 'threejs' and to_format == 'mjcf':
            return converter.joint_angles_threejs_to_mjcf(angles)

        # URDF -> Three.js (通过MJCF中转)
        elif from_format == 'urdf' and to_format == 'threejs':
            mjcf_angles = converter.joint_angles_urdf_to_mjcf(angles)
            return converter.joint_angles_mjcf_to_threejs(mjcf_angles)

        else:
            raise ValueError(f"不支持的转换: {from_format} -> {to_format}")

    def convert_pose(from_format: str, to_format: str,
                    position: List[float], rotation=None):
        """
        转换位姿

        Args:
            from_format: 源格式 ('urdf', 'mjcf', 'threejs')
            to_format: 目标格式 ('urdf', 'mjcf', 'threejs')
            position: 位置 [x, y, z]
            rotation: 旋转 (四元数 [w,x,y,z] 或欧拉角 [roll,pitch,yaw])

        Returns:
            转换后的位置和旋转
        """
        if from_format == to_format:
            return position, rotation

        if from_format == 'urdf' and to_format == 'threejs':
            return converter.urdf_to_threejs_transform(position, rotation)
        elif from_format == 'mjcf' and to_format == 'threejs':
            return converter.mjcf_to_threejs_transform(position, rotation)
        elif from_format == 'threejs' and to_format == 'urdf':
            return converter.threejs_to_urdf_transform(position, rotation)
        elif from_format == 'threejs' and to_format == 'mjcf':
            return converter.threejs_to_mjcf_transform(position, rotation)
        else:
            raise ValueError(f"不支持的位姿转换: {from_format} -> {to_format}")

    return {
        'converter': converter,
        'convert_joint_angles': convert_joint_angles,
        'convert_pose': convert_pose,
        'joint_mapping': JOINT_MAPPING
    }


# 全局转换工具实例
conversion_utils = create_conversion_utilities()


def run_comprehensive_tests():
    """运行全面的坐标转换测试"""
    print("[INFO] 开始全面坐标转换测试...")

    converter = CoordinateConverter()
    results = {
        'basic_transforms': {},
        'joint_angle_conversions': {},
        'pose_conversions': {},
        'edge_cases': {},
        'performance': {}
    }

    # 1. 基本变换测试
    print("[TEST] 基本变换测试...")
    basic_results = converter.validate_transforms()
    results['basic_transforms'] = basic_results

    # 2. 关节角度转换测试
    print("[TEST] 关节角度转换测试...")
    test_angles = {
        'home_position': [0.0, -np.pi/2, np.pi/2, 0.0, 0.0, 0.0],
        'folded_position': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'extended_position': [0.0, -np.pi, np.pi, 0.0, 0.0, 0.0],
        'random_position': [0.5, -0.8, 1.2, -0.3, 0.7, -0.1]
    }

    joint_results = {}
    for pose_name, angles in test_angles.items():
        conversions = {}
        for from_fmt in ['urdf', 'mjcf', 'threejs']:
            for to_fmt in ['urdf', 'mjcf', 'threejs']:
                if from_fmt != to_fmt:
                    converted = conversion_utils['convert_joint_angles'](from_fmt, to_fmt, angles)
                    conversions[f"{from_fmt}_to_{to_fmt}"] = converted

        # 验证往返转换
        urdf_to_threejs = conversion_utils['convert_joint_angles']('urdf', 'threejs', angles)
        threejs_to_mjcf = conversion_utils['convert_joint_angles']('threejs', 'mjcf', urdf_to_threejs)
        mjcf_to_urdf = conversion_utils['convert_joint_angles']('mjcf', 'urdf', threejs_to_mjcf)

        roundtrip_error = np.linalg.norm(np.array(angles) - np.array(mjcf_to_urdf))

        joint_results[pose_name] = {
            'original': angles,
            'conversions': conversions,
            'roundtrip_error': roundtrip_error,
            'roundtrip_consistent': roundtrip_error < 1e-10
        }

    results['joint_angle_conversions'] = joint_results

    # 3. 位姿转换测试
    print("[TEST] 位姿转换测试...")
    test_poses = {
        'origin': ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]),
        'translated': ([1.0, 2.0, 3.0], [0.707, 0.0, 0.707, 0.0]),
        'rotated': ([0.0, 0.0, 0.0], [0.5, 0.5, 0.5, 0.5])
    }

    pose_results = {}
    for pose_name, (position, quaternion) in test_poses.items():
        conversions = {}
        for from_fmt in ['mjcf', 'threejs']:
            for to_fmt in ['mjcf', 'threejs']:
                if from_fmt != to_fmt:
                    conv_pos, conv_quat = conversion_utils['convert_pose'](from_fmt, to_fmt, position, quaternion)
                    conversions[f"{from_fmt}_to_{to_fmt}"] = {
                        'position': conv_pos,
                        'quaternion': conv_quat
                    }

        # 往返转换测试
        mjcf_to_threejs_pos, mjcf_to_threejs_quat = conversion_utils['convert_pose']('mjcf', 'threejs', position, quaternion)
        threejs_to_mjcf_pos, threejs_to_mjcf_quat = conversion_utils['convert_pose']('threejs', 'mjcf', mjcf_to_threejs_pos, mjcf_to_threejs_quat)

        pos_error = np.linalg.norm(np.array(position) - np.array(threejs_to_mjcf_pos))
        quat_error1 = np.linalg.norm(np.array(quaternion) - np.array(threejs_to_mjcf_quat))
        quat_error2 = np.linalg.norm(np.array(quaternion) - (-np.array(threejs_to_mjcf_quat)))
        quat_error = min(quat_error1, quat_error2)

        pose_results[pose_name] = {
            'original': {'position': position, 'quaternion': quaternion},
            'conversions': conversions,
            'roundtrip_pos_error': pos_error,
            'roundtrip_quat_error': quat_error,
            'roundtrip_consistent': pos_error < 1e-10 and quat_error < 1e-10
        }

    results['pose_conversions'] = pose_results

    # 4. 边界情况测试
    print("[TEST] 边界情况测试...")
    edge_cases = {
        'zero_angles': [0.0] * 6,
        'joint_limits': [-6.28, -6.28, -3.14, -6.28, -6.28, -6.28],  # 接近关节极限
        'large_angles': [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]  # 大角度
    }

    edge_results = {}
    for case_name, angles in edge_cases.items():
        try:
            threejs_angles = conversion_utils['convert_joint_angles']('urdf', 'threejs', angles)
            mjcf_angles = conversion_utils['convert_joint_angles']('threejs', 'mjcf', threejs_angles)
            urdf_back = conversion_utils['convert_joint_angles']('mjcf', 'urdf', mjcf_angles)

            error = np.linalg.norm(np.array(angles) - np.array(urdf_back))
            edge_results[case_name] = {
                'original': angles,
                'converted': threejs_angles,
                'back_converted': urdf_back,
                'error': error,
                'success': error < 1e-8
            }
        except Exception as e:
            edge_results[case_name] = {
                'error': str(e),
                'success': False
            }

    results['edge_cases'] = edge_results

    # 5. 性能测试
    print("[TEST] 性能测试...")
    import time

    # 测试大量转换的性能
    test_iterations = 1000
    test_angles_perf = [0.1 * i for i in range(6)]

    start_time = time.time()
    for _ in range(test_iterations):
        conversion_utils['convert_joint_angles']('urdf', 'threejs', test_angles_perf)
    end_time = time.time()

    avg_time_per_conversion = (end_time - start_time) / test_iterations * 1000  # ms

    results['performance'] = {
        'iterations': test_iterations,
        'total_time_ms': (end_time - start_time) * 1000,
        'avg_time_per_conversion_ms': avg_time_per_conversion,
        'conversions_per_second': 1000 / avg_time_per_conversion
    }

    # 保存详细测试结果
    def convert_for_json(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.float64):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        return obj

    import json
    with open('../validation_results/comprehensive_coordinate_tests.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=convert_for_json)

    # 打印测试摘要
    print("\n[TEST SUMMARY]")
    print(f"基本变换测试: {'通过' if basic_results['transforms_consistent'] else '失败'}")
    print(f"关节角度转换: {sum(1 for r in joint_results.values() if r['roundtrip_consistent'])}/{len(joint_results)} 通过")
    print(f"位姿转换: {sum(1 for r in pose_results.values() if r['roundtrip_consistent'])}/{len(pose_results)} 通过")
    print(f"边界情况: {sum(1 for r in edge_results.values() if r.get('success', False))}/{len(edge_results)} 通过")
    print(".2f"    print(f"平均转换时间: {avg_time_per_conversion:.4f} ms")

    all_passed = (
        basic_results['transforms_consistent'] and
        all(r['roundtrip_consistent'] for r in joint_results.values()) and
        all(r['roundtrip_consistent'] for r in pose_results.values()) and
        all(r.get('success', False) for r in edge_results.values())
    )

    print(f"\n[OVERALL RESULT] {'所有测试通过' if all_passed else '部分测试失败'}")

    return results


def main():
    """主函数 - 运行验证和演示"""
    print("[INFO] 坐标转换工具验证...")

    # 运行全面测试
    test_results = run_comprehensive_tests()

    # 保存基础验证结果
    converter = CoordinateConverter()
    basic_results = converter.validate_transforms()

    import json
    def convert_for_json(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.float64):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return obj

    with open('../validation_results/coordinate_validation.json', 'w', encoding='utf-8') as f:
        json.dump(basic_results, f, indent=2, ensure_ascii=False, default=convert_for_json)

    print("[OK] 坐标转换验证完成")

    # 演示关节角度转换
    print("\n[INFO] 关节角度转换演示:")

    # 示例角度
    urdf_angles = [0.0, -np.pi/2, np.pi/2, 0.0, 0.0, 0.0]  # URDF弧度角度

    print(f"URDF角度 (弧度): {urdf_angles}")
    print(f"URDF角度 (角度): {[np.rad2deg(a) for a in urdf_angles]}")

    # 转换为Three.js角度
    threejs_angles = conversion_utils['convert_joint_angles']('urdf', 'threejs', urdf_angles)
    print(f"Three.js角度: {threejs_angles}")

    # 转换回MJCF角度
    mjcf_angles = conversion_utils['convert_joint_angles']('threejs', 'mjcf', threejs_angles)
    print(f"MJCF角度 (弧度): {mjcf_angles}")

    print(f"[OK] 转换工具创建完成")


if __name__ == "__main__":
    main()
