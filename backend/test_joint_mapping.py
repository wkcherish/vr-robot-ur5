#!/usr/bin/env python3
"""
关节映射验证测试脚本
测试关节顺序映射的正确性
"""

import sys
import os
import time
import numpy as np
from typing import List, Dict

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from simulation import get_simulation_instance, SimState
    from joint_mapping_validator import JointMappingValidator
except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保在正确的环境中运行此脚本")
    sys.exit(1)


class JointMappingTester:
    """关节映射测试器"""

    def __init__(self):
        self.sim = get_simulation_instance()
        self.validator = JointMappingValidator()

    def test_joint_order_consistency(self) -> Dict:
        """测试关节顺序一致性"""
        print("[INFO] 测试关节顺序一致性...")

        results = {
            'passed': True,
            'tests': [],
            'details': {}
        }

        # 测试关节角度设置和读取
        test_angles = [
            [0, 0, 0, 0, 0, 0],           # 零位
            [30, -45, 90, -60, 45, 0],     # 典型工作位姿
            [-90, 90, -90, 90, -90, 90],   # 极限位置
            [45, 0, 45, 0, 45, 0]         # 对称位置
        ]

        for i, angles_deg in enumerate(test_angles):
            test_name = f"位置测试 {i+1}"
            print(f"  测试 {test_name}: {angles_deg}")

            # 转换为弧度
            angles_rad = [np.deg2rad(angle) for angle in angles_deg]

            # 设置关节角度
            success = self.sim.step_simulation(
                target_positions=angles_rad,
                n_steps=50,  # 多步以确保收敛
                control_mode='position'
            )

            if not success:
                results['tests'].append({
                    'name': test_name,
                    'passed': False,
                    'error': '仿真步进失败'
                })
                results['passed'] = False
                continue

            # 等待仿真稳定
            time.sleep(0.1)

            # 获取当前状态
            state = self.sim.get_current_state()
            if not state:
                results['tests'].append({
                    'name': test_name,
                    'passed': False,
                    'error': '无法获取状态'
                })
                results['passed'] = False
                continue

            # 验证关节角度
            actual_angles_rad = state.qpos[:6]
            actual_angles_deg = [np.rad2deg(angle) for angle in actual_angles_rad]

            # 计算误差
            errors = []
            max_error = 0
            for j, (expected, actual) in enumerate(zip(angles_deg, actual_angles_deg)):
                error = abs(expected - actual)
                errors.append(error)
                max_error = max(max_error, error)

                # 角度误差超过5度认为失败
                if error > 5.0:
                    results['tests'].append({
                        'name': f"{test_name} - 关节{j+1}",
                        'passed': False,
                        'error': f'角度误差过大: 期望{expected:.1f}°, 实际{actual:.1f}°, 误差{error:.1f}°'
                    })
                    results['passed'] = False

            # 记录详细信息
            results['details'][test_name] = {
                'expected': angles_deg,
                'actual': actual_angles_deg,
                'errors': errors,
                'max_error': max_error
            }

            if max_error <= 5.0:
                results['tests'].append({
                    'name': test_name,
                    'passed': True,
                    'info': f'最大误差: {max_error:.1f}°'
                })

        return results

    def test_coordinate_system_consistency(self) -> Dict:
        """测试坐标系统一致性"""
        print("[INFO] 测试坐标系统一致性...")

        results = {
            'passed': True,
            'tests': [],
            'details': {}
        }

        # 测试末端执行器位置计算
        test_poses = [
            {'name': '零位', 'angles': [0, 0, 0, 0, 0, 0]},
            {'name': '伸直位', 'angles': [0, -90, 90, 0, 0, 0]},
            {'name': '弯曲位', 'angles': [0, -45, 45, 0, 0, 0]}
        ]

        for pose in test_poses:
            print(f"  测试 {pose['name']}: {pose['angles']}")

            # 设置关节角度
            angles_rad = [np.deg2rad(angle) for angle in pose['angles']]
            success = self.sim.step_simulation(
                target_positions=angles_rad,
                n_steps=50
            )

            if not success:
                results['tests'].append({
                    'name': f"{pose['name']} - 坐标测试",
                    'passed': False,
                    'error': '设置关节角度失败'
                })
                results['passed'] = False
                continue

            # 获取末端执行器位置
            state = self.sim.get_current_state()
            if not state or not state.ee_pose:
                results['tests'].append({
                    'name': f"{pose['name']} - 坐标测试",
                    'passed': False,
                    'error': '无法获取末端执行器位置'
                })
                results['passed'] = False
                continue

            ee_pos = state.ee_pose['position']
            ee_ori = state.ee_pose['orientation']

            # 验证位置在合理范围内
            pos_magnitude = np.linalg.norm(ee_pos)
            if pos_magnitude > 2.0:  # UR5臂展约1.5m，这里给些余量
                results['tests'].append({
                    'name': f"{pose['name']} - 坐标测试",
                    'passed': False,
                    'error': f'末端位置异常: {ee_pos}, 距离: {pos_magnitude:.3f}m'
                })
                results['passed'] = False
            else:
                results['tests'].append({
                    'name': f"{pose['name']} - 坐标测试",
                    'passed': True,
                    'info': f'末端位置: [{ee_pos[0]:.3f}, {ee_pos[1]:.3f}, {ee_pos[2]:.3f}]'
                })

            results['details'][pose['name']] = {
                'angles': pose['angles'],
                'ee_position': ee_pos,
                'ee_orientation': ee_ori
            }

        return results

    def test_joint_limits(self) -> Dict:
        """测试关节限制"""
        print("[INFO] 测试关节限制...")

        results = {
            'passed': True,
            'tests': [],
            'joint_limits': {}
        }

        # 从MJCF模型获取关节限制
        try:
            if self.sim.model:
                for i in range(6):
                    joint_id = self.sim.model.jnt_dofadr[i]  # 获取关节的自由度地址
                    range_min = self.sim.model.jnt_range[i][0]
                    range_max = self.sim.model.jnt_range[i][1]

                    results['joint_limits'][f'joint_{i+1}'] = {
                        'min': float(range_min),
                        'max': float(range_max),
                        'min_deg': np.rad2deg(range_min),
                        'max_deg': np.rad2deg(range_max)
                    }

                    print(f"    关节{i+1} 限制: [{np.rad2deg(range_min):.1f}°, {np.rad2deg(range_max):.1f}°]")

                results['tests'].append({
                    'name': '关节限制读取',
                    'passed': True,
                    'info': f'成功读取{len(results["joint_limits"])}个关节的限制'
                })
            else:
                results['tests'].append({
                    'name': '关节限制读取',
                    'passed': False,
                    'error': '无法访问仿真模型'
                })
                results['passed'] = False

        except Exception as e:
            results['tests'].append({
                'name': '关节限制读取',
                'passed': False,
                'error': f'读取关节限制失败: {e}'
            })
            results['passed'] = False

        return results

    def generate_test_report(self, results: Dict) -> str:
        """生成测试报告"""
        print("\n[INFO] 生成测试报告...")

        report = []
        report.append("# 关节映射测试报告")
        report.append("")
        report.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # 总体结果
        total_tests = len(results.get('order_test', {}).get('tests', [])) + \
                     len(results.get('coordinate_test', {}).get('tests', [])) + \
                     len(results.get('limits_test', {}).get('tests', []))

        passed_tests = sum(1 for test in results.get('order_test', {}).get('tests', [])
                          if test.get('passed', False)) + \
                      sum(1 for test in results.get('coordinate_test', {}).get('tests', [])
                          if test.get('passed', False)) + \
                      sum(1 for test in results.get('limits_test', {}).get('tests', [])
                          if test.get('passed', False))

        report.append(f"## 总体结果")
        report.append(f"- 总测试数: {total_tests}")
        report.append(f"- 通过测试: {passed_tests}")
        report.append(f"- 失败测试: {total_tests - passed_tests}")
        report.append(f"- 成功率: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        report.append("")

        # 关节顺序测试
        if 'order_test' in results:
            order_test = results['order_test']
            report.append("## 关节顺序一致性测试")
            report.append(f"状态: {'[OK] 通过' if order_test['passed'] else '[ERROR] 失败'}")
            report.append("")

            for test in order_test['tests']:
                status = "[OK]" if test['passed'] else "[ERROR]"
                report.append(f"- {status} {test['name']}")
                if 'error' in test:
                    report.append(f"  - 错误: {test['error']}")
                elif 'info' in test:
                    report.append(f"  - 信息: {test['info']}")
            report.append("")

        # 坐标系统测试
        if 'coordinate_test' in results:
            coord_test = results['coordinate_test']
            report.append("## 坐标系统一致性测试")
            report.append(f"状态: {'[OK] 通过' if coord_test['passed'] else '[ERROR] 失败'}")
            report.append("")

            for test in coord_test['tests']:
                status = "[OK]" if test['passed'] else "[ERROR]"
                report.append(f"- {status} {test['name']}")
                if 'error' in test:
                    report.append(f"  - 错误: {test['error']}")
                elif 'info' in test:
                    report.append(f"  - 信息: {test['info']}")
            report.append("")

        # 关节限制测试
        if 'limits_test' in results:
            limits_test = results['limits_test']
            report.append("## 关节限制测试")
            report.append(f"状态: {'[OK] 通过' if limits_test['passed'] else '[ERROR] 失败'}")
            report.append("")

            if limits_test.get('joint_limits'):
                report.append("### 关节限制范围")
                for joint_name, limits in limits_test['joint_limits'].items():
                    report.append(f"- **{joint_name}**: [{limits['min_deg']:.1f}°, {limits['max_deg']:.1f}°] "
                                f"(弧度: [{limits['min']:.3f}, {limits['max']:.3f}])")
                report.append("")

            for test in limits_test['tests']:
                status = "[OK]" if test['passed'] else "[ERROR]"
                report.append(f"- {status} {test['name']}")
                if 'error' in test:
                    report.append(f"  - 错误: {test['error']}")
                elif 'info' in test:
                    report.append(f"  - 信息: {test['info']}")
            report.append("")

        return "\n".join(report)

    def run_all_tests(self) -> Dict:
        """运行所有测试"""
        print("[START] 开始关节映射测试...")

        # 初始化仿真
        if not self.sim.load_model():
            print("[ERROR] 仿真模型加载失败")
            return {'error': '仿真模型加载失败'}

        # 运行各个测试
        order_test = self.test_joint_order_consistency()
        coordinate_test = self.test_coordinate_system_consistency()
        limits_test = self.test_joint_limits()

        results = {
            'order_test': order_test,
            'coordinate_test': coordinate_test,
            'limits_test': limits_test,
            'timestamp': time.time()
        }

        # 生成报告
        report = self.generate_test_report(results)

        # 保存结果
        output_dir = "test_results"
        os.makedirs(output_dir, exist_ok=True)

        with open(f"{output_dir}/joint_mapping_test_report.md", 'w', encoding='utf-8') as f:
            f.write(report)

        # 保存详细结果
        import json
        with open(f"{output_dir}/joint_mapping_test_results.json", 'w', encoding='utf-8') as f:
            # 转换numpy数组为列表以便JSON序列化
            def convert_numpy(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, np.float64):
                    return float(obj)
                return obj

            json.dump(results, f, indent=2, default=convert_numpy, ensure_ascii=False)

        print(f"[OK] 测试结果已保存到 {output_dir}/")

        # 打印简要结果
        all_passed = all([
            order_test['passed'],
            coordinate_test['passed'],
            limits_test['passed']
        ])

        print("\n" + "="*50)
        print("测试完成！")
        print("="*50)

        if all_passed:
            print("[SUCCESS] 所有测试通过！关节映射正确。")
        else:
            print("[WARN] 部分测试失败，请检查详细报告。")

        return results


def main():
    """主函数"""
    tester = JointMappingTester()
    results = tester.run_all_tests()

    # 如果有错误，退出时显示错误码
    if 'error' in results:
        print(f"测试失败: {results['error']}")
        sys.exit(1)

    # 根据测试结果设置退出码
    all_passed = all([
        results.get('order_test', {}).get('passed', False),
        results.get('coordinate_test', {}).get('passed', False),
        results.get('limits_test', {}).get('passed', False)
    ])

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
