#!/usr/bin/env python3
"""
坐标系统转换工具
提供URDF、MJCF、Three.js之间的坐标转换
"""

import numpy as np
from typing import Tuple, List, Optional


class CoordinateConverter:
    """坐标系统转换器"""

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
            rotation: 旋转 (四元数) [w, x, y, z]

        Returns:
            转换后的位置和旋转
        """
        # 将位置转换为齐次坐标
        pos_homogeneous = np.array(position + [1])

        # 应用变换
        transformed_pos = np.dot(self.mjcf_to_threejs, pos_homogeneous)[:3]

        # 对于旋转，如果是四元数，需要转换
        transformed_rotation = rotation
        if rotation and len(rotation) == 4:
            # 四元数旋转变换
            # 这里简化处理，实际可能需要更复杂的四元数运算
            pass

        return transformed_pos.tolist(), transformed_rotation

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
        """
        # 将位置转换为齐次坐标
        pos_homogeneous = np.array(position + [1])

        # 应用变换
        transformed_pos = np.dot(self.threejs_to_mjcf, pos_homogeneous)[:3]

        transformed_rotation = rotation
        return transformed_pos.tolist(), transformed_rotation

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

    def validate_transforms(self) -> dict:
        """验证变换的正确性"""
        print("[INFO] 验证坐标变换...")

        # 测试基本变换
        test_position = [1.0, 2.0, 3.0]

        # MJCF -> Three.js -> MJCF 应该恢复原值
        pos_mjcf_to_threejs, _ = self.mjcf_to_threejs_transform(test_position)
        pos_threejs_to_mjcf, _ = self.threejs_to_mjcf_transform(pos_mjcf_to_threejs)

        position_error = np.linalg.norm(np.array(test_position) - np.array(pos_threejs_to_mjcf))

        results = {
            'position_roundtrip_error': position_error,
            'transforms_consistent': position_error < 1e-10,
            'urdf_to_threejs_matrix': self.urdf_to_threejs.tolist(),
            'mjcf_to_threejs_matrix': self.mjcf_to_threejs.tolist(),
            'threejs_to_mjcf_matrix': self.threejs_to_mjcf.tolist()
        }

        print(f"[INFO] 位置往返变换误差: {position_error}")
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
            rotation: 旋转 (可选)

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


def main():
    """主函数 - 验证坐标转换"""
    print("[INFO] 坐标转换工具验证...")

    converter = CoordinateConverter()

    # 验证变换
    results = converter.validate_transforms()

    # 保存验证结果
    import json

    def convert_for_json(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.float64):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return obj

    with open('validation_results/coordinate_validation.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=convert_for_json)

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
