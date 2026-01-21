#!/usr/bin/env python3
"""
MuJoCo 仿真可视化查看器
用于显示和交互控制 UR5 机器人仿真
"""

import time
import numpy as np
import threading
from simulation import Simulation

def create_simple_viewer():
    """
    创建简单的仿真查看器
    """
    print("初始化 MuJoCo 仿真查看器...")

    # 创建仿真实例
    sim = Simulation()

    # 加载模型
    print("加载 UR5 模型...")
    if not sim.load_model("mujoco_models/ur5.xml"):
        print("模型加载失败！")
        return

    print("模型加载成功！")

    # 尝试创建可视化窗口
    try:
        import mujoco
        import mujoco.viewer

        print("启动 MuJoCo 查看器...")

        # 创建查看器
        with mujoco.viewer.launch_passive(sim.model, sim.data) as viewer:
            print("\n" + "="*50)
            print("MuJoCo 查看器已启动！")
            print("控制说明:")
            print("- 鼠标拖拽: 旋转视角")
            print("- 鼠标滚轮: 缩放")
            print("- WASD: 移动相机")
            print("- 空格: 暂停/继续仿真")
            print("- ESC: 退出")
            print("="*50)

            # 主循环
            last_time = time.time()
            step_count = 0

            while viewer.is_running():
                current_time = time.time()

                # 控制仿真速度 (30Hz)
                if current_time - last_time >= 1.0/30.0:
                    # 执行仿真步进
                    mujoco.mj_step(sim.model, sim.data)
                    step_count += 1

                    # 更新查看器
                    viewer.sync()

                    # 每100步打印一次状态
                    if step_count % 100 == 0:
                        state = sim.get_current_state()
                        if state:
                            print(f"步进 {step_count}: 关节角度 = {[f'{x:.3f}' for x in state.qpos[:6]]}")

                    last_time = current_time

                # 小延迟避免CPU占用过高
                time.sleep(0.001)

        print("查看器已关闭")

    except ImportError:
        print("错误: 无法导入 mujoco.viewer")
        print("请确保安装了支持可视化的 MuJoCo 版本")
        print("在 Linux/Mac 上: pip install mujoco")
        print("在 Windows 上可能需要额外配置")

        # 提供备选方案：命令行状态监控
        print("\n启动命令行状态监控模式...")
        command_line_viewer(sim)

    except Exception as e:
        print(f"查看器启动失败: {e}")
        print("启动命令行状态监控模式...")
        command_line_viewer(sim)

def command_line_viewer(sim: Simulation):
    """
    命令行状态监控模式
    """
    print("\n" + "="*50)
    print("命令行仿真监控模式")
    print("输入 'q' 退出, 'r' 重置, 's' 步进, 'c' 连续运行")
    print("="*50)

    continuous = False

    while True:
        try:
            # 显示当前状态
            state = sim.get_current_state()
            if state:
                print(f"关节角度: {[f'{x:.3f}' for x in state.qpos[:6]]}")
                print(f"关节速度: {[f'{x:.3f}' for x in state.qvel[:6]]}")
                print(f"末端位置: {[f'{x:.3f}' for x in state.ee_pose['position']]}")

            if not continuous:
                # 等待用户输入
                cmd = input("\n命令 (q/r/s/c): ").strip().lower()

                if cmd == 'q':
                    break
                elif cmd == 'r':
                    sim.reset_simulation()
                    print("仿真已重置")
                elif cmd == 's':
                    # 执行单步
                    target_pos = [0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0]  # home pose
                    sim.step_simulation(target_pos, n_steps=10)
                    print("执行了 10 步仿真")
                elif cmd == 'c':
                    continuous = True
                    print("切换到连续运行模式 (输入任何键停止)")
                else:
                    print("无效命令")
            else:
                # 连续模式
                target_pos = [0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0]
                sim.step_simulation(target_pos, n_steps=1)
                time.sleep(0.1)

                # 检查是否有输入
                import select
                import sys
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    sys.stdin.read(1)  # 读取输入
                    continuous = False
                    print("停止连续运行")

        except KeyboardInterrupt:
            print("\n用户中断")
            break
        except Exception as e:
            print(f"错误: {e}")
            break

def test_camera_rendering():
    """
    测试相机渲染功能
    """
    print("测试相机渲染功能...")

    sim = Simulation()
    if not sim.load_model("mujoco_models/ur5.xml"):
        print("模型加载失败")
        return

    # 列出可用相机
    cameras = sim.list_cameras()
    if cameras:
        print(f"发现 {len(cameras)} 个相机:")
        for cam in cameras:
            print(f"  - {cam['name']} (ID: {cam['id']})")

        # 测试渲染
        camera_name = cameras[0]['name']
        print(f"\n测试相机 '{camera_name}' 渲染...")

        image = sim.render_camera(camera_name, 640, 480)
        if image is not None:
            print(f"✓ 相机渲染成功! 图像尺寸: {image.shape}")
        else:
            print("✗ 相机渲染失败")
    else:
        print("未发现相机")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "camera":
            test_camera_rendering()
        else:
            print("用法: python viewer.py [camera]")
            print("  无参数: 启动可视化查看器")
            print("  camera: 测试相机渲染功能")
    else:
        create_simple_viewer()
