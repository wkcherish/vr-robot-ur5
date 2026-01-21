#!/usr/bin/env python3
"""
关节顺序映射验证工具
验证 URDF、MJCF、前端关节顺序的一致性
"""

import xml.etree.ElementTree as ET
import json
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class JointInfo:
    """关节信息数据类"""
    name: str
    index: int
    urdf_name: str = ""
    mjcf_name: str = ""
    frontend_name: str = ""
    axis: Optional[List[float]] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None


class JointMappingValidator:
    """关节映射验证器"""

    def __init__(self):
        self.joint_mappings = {}
        self.validation_results = {}

    def analyze_urdf_joints(self, urdf_path: str) -> List[JointInfo]:
        """分析URDF文件中的关节顺序"""
        print(f"[INFO] 分析URDF文件: {urdf_path}")

        try:
            tree = ET.parse(urdf_path)
            root = tree.getroot()

            joints = []
            joint_elements = root.findall(".//joint[@type='revolute']")

            for i, joint in enumerate(joint_elements):
                name = joint.get('name')
                if name and 'link' in name and name.endswith('_joint'):
                    # 解析关节轴
                    axis_elem = joint.find('axis')
                    axis = None
                    if axis_elem is not None:
                        axis_str = axis_elem.get('xyz', '')
                        if axis_str:
                            axis = [float(x) for x in axis_str.split()]

                    # 解析关节限制
                    limit_elem = joint.find('limit')
                    range_min = range_max = None
                    if limit_elem is not None:
                        range_min = float(limit_elem.get('lower', 0))
                        range_max = float(limit_elem.get('upper', 0))

                    joint_info = JointInfo(
                        name=name,
                        index=i,
                        urdf_name=name,
                        axis=axis,
                        range_min=range_min,
                        range_max=range_max
                    )
                    joints.append(joint_info)

            print(f"[OK] 找到 {len(joints)} 个URDF关节")
            return joints

        except Exception as e:
            print(f"[ERROR] URDF分析失败: {e}")
            return []

    def analyze_mjcf_joints(self, mjcf_path: str) -> List[JointInfo]:
        """分析MJCF文件中的关节顺序"""
        print(f"[INFO] 分析MJCF文件: {mjcf_path}")

        try:
            tree = ET.parse(mjcf_path)
            root = tree.getroot()

            joints = []
            joint_elements = root.findall(".//joint")

            for i, joint in enumerate(joint_elements):
                name = joint.get('name')
                if name and ('shoulder' in name or 'elbow' in name or 'wrist' in name):
                    # 解析关节轴
                    axis_str = joint.get('axis', '')
                    axis = None
                    if axis_str:
                        axis = [float(x) for x in axis_str.split()]

                    # 解析关节范围
                    range_str = joint.get('range', '')
                    range_min = range_max = None
                    if range_str:
                        range_parts = range_str.split()
                        if len(range_parts) >= 2:
                            range_min = float(range_parts[0])
                            range_max = float(range_parts[1])

                    joint_info = JointInfo(
                        name=name,
                        index=i,
                        mjcf_name=name,
                        axis=axis,
                        range_min=range_min,
                        range_max=range_max
                    )
                    joints.append(joint_info)

            print(f"[OK] 找到 {len(joints)} 个MJCF关节")
            return joints

        except Exception as e:
            print(f"[ERROR] MJCF分析失败: {e}")
            return []

    def analyze_frontend_joints(self, app_vue_path: str) -> List[JointInfo]:
        """分析前端代码中的关节顺序"""
        print(f"[INFO] 分析前端代码: {app_vue_path}")

        try:
            with open(app_vue_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 从setRobotAngles函数中提取关节顺序
            joints = []

            # 查找sliderInput调用模式
            import re
            slider_pattern = r'sliderInput\(radians\[(\d+)\],\s*"([^"]+)"\)'
            matches = re.findall(slider_pattern, content)

            for index_str, joint_name in matches:
                index = int(index_str)
                joint_info = JointInfo(
                    name=joint_name,
                    index=index,
                    frontend_name=joint_name
                )
                joints.append(joint_info)

            print(f"[OK] 找到 {len(joints)} 个前端关节")
            return joints

        except Exception as e:
            print(f"[ERROR] 前端代码分析失败: {e}")
            return []

    def create_joint_mapping(self, urdf_joints: List[JointInfo],
                           mjcf_joints: List[JointInfo],
                           frontend_joints: List[JointInfo]) -> Dict:
        """创建关节映射表"""
        print("\n[INFO] 创建关节映射表...")

        mapping = {}

        # URDF关节名称到传统UR5关节名称的映射
        urdf_to_standard = {
            'link1_joint': 'shoulder_pan',
            'link2_joint': 'shoulder_lift',
            'link3_joint': 'elbow',
            'link4_joint': 'wrist_1',
            'link5_joint': 'wrist_2',
            'link6_joint': 'wrist_3'
        }

        # MJCF关节名称到标准名称的映射
        mjcf_to_standard = {
            'shoulder_pan_joint': 'shoulder_pan',
            'shoulder_lift_joint': 'shoulder_lift',
            'elbow_joint': 'elbow',
            'wrist_1_joint': 'wrist_1',
            'wrist_2_joint': 'wrist_2',
            'wrist_3_joint': 'wrist_3'
        }

        # 前端关节名称到标准名称的映射
        frontend_to_standard = {
            'link1_joint': 'shoulder_pan',
            'link2_joint': 'shoulder_lift',
            'link3_joint': 'elbow',
            'link4_joint': 'wrist_1',
            'link5_joint': 'wrist_2',
            'link6_joint': 'wrist_3'
        }

        # 为每个标准关节创建映射
        standard_joints = ['shoulder_pan', 'shoulder_lift', 'elbow', 'wrist_1', 'wrist_2', 'wrist_3']

        for i, standard_name in enumerate(standard_joints):
            joint_mapping = {
                'index': i,
                'standard_name': standard_name,
                'urdf': None,
                'mjcf': None,
                'frontend': None,
                'axis_consistent': True,
                'range_consistent': True
            }

            # 查找URDF关节
            for urdf_joint in urdf_joints:
                if urdf_to_standard.get(urdf_joint.urdf_name) == standard_name:
                    joint_mapping['urdf'] = {
                        'name': urdf_joint.urdf_name,
                        'axis': urdf_joint.axis,
                        'range': [urdf_joint.range_min, urdf_joint.range_max]
                    }
                    break

            # 查找MJCF关节
            for mjcf_joint in mjcf_joints:
                if mjcf_to_standard.get(mjcf_joint.mjcf_name) == standard_name:
                    joint_mapping['mjcf'] = {
                        'name': mjcf_joint.mjcf_name,
                        'axis': mjcf_joint.axis,
                        'range': [mjcf_joint.range_min, mjcf_joint.range_max]
                    }
                    break

            # 查找前端关节
            for frontend_joint in frontend_joints:
                if frontend_to_standard.get(frontend_joint.frontend_name) == standard_name:
                    joint_mapping['frontend'] = {
                        'name': frontend_joint.frontend_name,
                        'index': frontend_joint.index
                    }
                    break

            # 验证一致性
            joint_mapping.update(self._validate_joint_consistency(joint_mapping))

            mapping[standard_name] = joint_mapping

        return mapping

    def _validate_joint_consistency(self, joint_mapping: Dict) -> Dict:
        """验证关节一致性"""
        consistency = {
            'axis_consistent': True,
            'range_consistent': True,
            'warnings': [],
            'errors': []
        }

        # 检查轴的一致性
        axes = []
        if joint_mapping['urdf'] and joint_mapping['urdf']['axis']:
            axes.append(joint_mapping['urdf']['axis'])
        if joint_mapping['mjcf'] and joint_mapping['mjcf']['axis']:
            axes.append(joint_mapping['mjcf']['axis'])

        if len(axes) > 1:
            for i in range(1, len(axes)):
                if not np.allclose(axes[0], axes[i], atol=1e-6):
                    consistency['axis_consistent'] = False
                    consistency['warnings'].append(f"关节轴不一致: {axes[0]} vs {axes[i]}")

        # 检查范围的一致性
        ranges = []
        if joint_mapping['urdf'] and joint_mapping['urdf']['range']:
            ranges.append(joint_mapping['urdf']['range'])
        if joint_mapping['mjcf'] and joint_mapping['mjcf']['range']:
            ranges.append(joint_mapping['mjcf']['range'])

        if len(ranges) > 1:
            for i in range(1, len(ranges)):
                if not np.allclose(ranges[0], ranges[i], atol=1e-3):
                    consistency['range_consistent'] = False
                    consistency['warnings'].append(f"关节范围不一致: {ranges[0]} vs {ranges[i]}")

        # 检查索引一致性
        if joint_mapping['frontend'] and joint_mapping['frontend']['index'] != joint_mapping['index']:
            consistency['errors'].append(f"前端关节索引不匹配: 期望{joint_mapping['index']}, 实际{joint_mapping['frontend']['index']}")

        return consistency

    def validate_coordinate_systems(self) -> Dict:
        """验证坐标系统一致性"""
        print("\n[INFO] 验证坐标系统...")

        # URDF通常使用Y-up坐标系
        # MJCF默认使用Z-up坐标系，但可以通过设置改变
        # Three.js使用Y-up坐标系

        coordinate_info = {
            'urdf': {
                'up_axis': 'Y',  # URDF通常Y-up
                'rotation': [0, 0, 0]
            },
            'mjcf': {
                'up_axis': 'Z',  # MuJoCo默认Z-up
                'rotation': [0, 0, 0]
            },
            'threejs': {
                'up_axis': 'Y',  # Three.js Y-up
                'rotation': [-90, 0, 0]  # 需要旋转-90度绕X轴
            }
        }

        return coordinate_info

    def generate_validation_report(self, mapping: Dict) -> str:
        """生成验证报告"""
        print("\n[INFO] 生成验证报告...")

        report = []
        report.append("# 关节顺序映射验证报告")
        report.append("")
        report.append("## 关节映射表")
        report.append("")
        report.append("| 关节索引 | 标准名称 | URDF名称 | MJCF名称 | 前端名称 | 状态 |")
        report.append("|-----------|----------|----------|----------|----------|------|")

        all_consistent = True

        for joint_name, joint_data in mapping.items():
            status = "[OK]"
            if joint_data.get('errors'):
                status = "[ERROR]"
                all_consistent = False
            elif joint_data.get('warnings'):
                status = "[WARN]"
                all_consistent = False

            urdf_name = joint_data['urdf']['name'] if joint_data['urdf'] else "-"
            mjcf_name = joint_data['mjcf']['name'] if joint_data['mjcf'] else "-"
            frontend_name = joint_data['frontend']['name'] if joint_data['frontend'] else "-"

            report.append(f"| {joint_data['index']} | {joint_name} | {urdf_name} | {mjcf_name} | {frontend_name} | {status} |")

        report.append("")
        report.append("## 详细验证结果")
        report.append("")

        for joint_name, joint_data in mapping.items():
            report.append(f"### {joint_name} (索引: {joint_data['index']})")
            report.append("")

            if joint_data['urdf']:
                report.append(f"- **URDF**: {joint_data['urdf']['name']}")
                if joint_data['urdf']['axis']:
                    report.append(f"  - 轴: {joint_data['urdf']['axis']}")
                if joint_data['urdf']['range']:
                    report.append(f"  - 范围: {joint_data['urdf']['range']}")

            if joint_data['mjcf']:
                report.append(f"- **MJCF**: {joint_data['mjcf']['name']}")
                if joint_data['mjcf']['axis']:
                    report.append(f"  - 轴: {joint_data['mjcf']['axis']}")
                if joint_data['mjcf']['range']:
                    report.append(f"  - 范围: {joint_data['mjcf']['range']}")

            if joint_data['frontend']:
                report.append(f"- **前端**: {joint_data['frontend']['name']} (索引: {joint_data['frontend']['index']})")

            # 显示警告和错误
            if joint_data.get('warnings'):
                report.append("**警告:**")
                for warning in joint_data['warnings']:
                    report.append(f"- {warning}")

            if joint_data.get('errors'):
                report.append("**错误:**")
                for error in joint_data['errors']:
                    report.append(f"- {error}")

            report.append("")

        # 总体状态
        if all_consistent:
            report.append("## 总体状态: [OK] 所有关节映射一致")
        else:
            report.append("## 总体状态: [WARN] 发现映射不一致，请检查上述问题")

        return "\n".join(report)

    def create_coordinate_conversion_functions(self) -> Dict:
        """创建坐标转换函数"""
        print("\n[INFO] 创建坐标转换函数...")

        def urdf_to_threejs(position, rotation=None):
            """URDF (Y-up) 到 Three.js (Y-up) 的转换"""
            # URDF和Three.js都是Y-up，所以通常不需要转换
            # 但可能需要根据模型的具体设置进行调整
            return position, rotation

        def mjcf_to_threejs(position, rotation=None):
            """MJCF (Z-up) 到 Three.js (Y-up) 的转换"""
            # MuJoCo Z-up 到 Three.js Y-up 需要旋转
            if rotation is None:
                rotation = [0, 0, 0]

            # 绕X轴旋转-90度，将Z-up转换为Y-up
            rotation_x = rotation[0] - np.pi/2
            new_rotation = [rotation_x, rotation[1], rotation[2]]

            return position, new_rotation

        def threejs_to_urdf(position, rotation=None):
            """Three.js (Y-up) 到 URDF (Y-up) 的转换"""
            return position, rotation

        def threejs_to_mjcf(position, rotation=None):
            """Three.js (Y-up) 到 MJCF (Z-up) 的转换"""
            if rotation is None:
                rotation = [0, 0, 0]

            # 绕X轴旋转+90度，将Y-up转换为Z-up
            rotation_x = rotation[0] + np.pi/2
            new_rotation = [rotation_x, rotation[1], rotation[2]]

            return position, new_rotation

        return {
            'urdf_to_threejs': urdf_to_threejs,
            'mjcf_to_threejs': mjcf_to_threejs,
            'threejs_to_urdf': threejs_to_urdf,
            'threejs_to_mjcf': threejs_to_mjcf
        }

    def run_validation(self, urdf_path: str, mjcf_path: str, frontend_path: str) -> Dict:
        """运行完整验证流程"""
        print("[START] 开始关节映射验证...")

        # 分析各文件
        urdf_joints = self.analyze_urdf_joints(urdf_path)
        mjcf_joints = self.analyze_mjcf_joints(mjcf_path)
        frontend_joints = self.analyze_frontend_joints(frontend_path)

        # 创建映射表
        mapping = self.create_joint_mapping(urdf_joints, mjcf_joints, frontend_joints)

        # 验证坐标系统
        coordinate_info = self.validate_coordinate_systems()

        # 创建转换函数
        conversion_functions = self.create_coordinate_conversion_functions()

        # 生成报告
        report = self.generate_validation_report(mapping)

        # 保存结果
        results = {
            'mapping': mapping,
            'urdf_joints': [joint.__dict__ for joint in urdf_joints],
            'mjcf_joints': [joint.__dict__ for joint in mjcf_joints],
            'frontend_joints': [joint.__dict__ for joint in frontend_joints],
            'coordinate_info': coordinate_info,
            'conversion_functions': conversion_functions,
            'report': report
        }

        # 保存到文件
        self.save_results(results)

        return results

    def save_results(self, results: Dict, output_dir: str = "validation_results"):
        """保存验证结果"""
        os.makedirs(output_dir, exist_ok=True)

        # 保存映射表
        with open(f"{output_dir}/joint_mapping.json", 'w', encoding='utf-8') as f:
            json.dump(results['mapping'], f, indent=2, ensure_ascii=False)

        # 保存报告
        with open(f"{output_dir}/validation_report.md", 'w', encoding='utf-8') as f:
            f.write(results['report'])

        print(f"[OK] 验证结果已保存到 {output_dir}/")


def main():
    """主函数"""
    validator = JointMappingValidator()

    # 文件路径
    urdf_path = "../public/ur5/ur5.urdf"
    mjcf_path = "mujoco_models/ur5.xml"
    frontend_path = "../src/App.vue"

    # 转换为绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    urdf_path = os.path.join(script_dir, urdf_path)
    mjcf_path = os.path.join(script_dir, mjcf_path)
    frontend_path = os.path.join(script_dir, frontend_path)

    # 运行验证
    results = validator.run_validation(urdf_path, mjcf_path, frontend_path)

    # 打印简要结果
    print("\n" + "="*50)
    print("验证完成！")
    print("="*50)

    mapping = results['mapping']
    consistent_count = sum(1 for joint in mapping.values()
                          if not joint.get('errors') and not joint.get('warnings'))

    print(f"总关节数: {len(mapping)}")
    print(f"一致关节数: {consistent_count}")
    print(f"问题关节数: {len(mapping) - consistent_count}")

    if consistent_count == len(mapping):
        print("[SUCCESS] 所有关节映射一致！")
    else:
        print("[WARN] 发现关节映射问题，请查看详细报告。")


if __name__ == "__main__":
    main()
