"""
MuJoCo 仿真核心模块
提供 UR5 机器人仿真控制功能
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import base64
import io
import queue
from concurrent.futures import Future

try:
    import mujoco
    from mujoco import MjModel, MjData
    # 尝试导入渲染相关的模块
    try:
        import mujoco.renderer
    except ImportError:
        mujoco.renderer = None
        print("警告: mujoco.renderer 不可用，可能需要更新 MuJoCo 版本")
except ImportError:
    print("警告: 未安装 mujoco，请运行: pip install mujoco")
    mujoco = None


@dataclass
class SimState:
    """仿真状态数据类"""
    timestamp: float
    qpos: List[float]  # 关节位置 (rad)
    qvel: List[float]  # 关节速度 (rad/s)
    ctrl: List[float]  # 控制信号
    ee_pose: Dict[str, List[float]]  # 末端执行器位姿
    sensor_data: Optional[Dict[str, Any]] = None  # 传感器数据


class Simulation:
    """
    MuJoCo 仿真核心类
    提供机器人仿真控制和状态管理
    """

    def __init__(self, model_path: str = "mujoco_models/ur5.xml"):
        """
        初始化仿真器

        Args:
            model_path: MJCF 模型文件路径
        """
        self.model_path = model_path
        self.model: Optional[MjModel] = None
        self.data: Optional[MjData] = None

        # 线程安全
        self._lock = threading.RLock()
        self._running = False
        self._simulation_thread: Optional[threading.Thread] = None

        # 仿真参数
        self.time_step = 0.002  # 仿真时间步长 (2ms)
        self.control_timestep = 0.01  # 控制时间步长 (10ms)

        # 状态缓存
        self._current_state: Optional[SimState] = None

        # 相机渲染器
        self.renderer = None
        self._render_lock = threading.Lock()

        # 相机缓存 (避免重复渲染)
        self._last_render_time = 0.0
        self._render_cache: Optional[Dict[str, Any]] = None
        self._cache_timeout = 1.0 / 30.0  # 30Hz 缓存

        # 请求队列和并发控制
        self._request_queue: queue.Queue = queue.Queue(maxsize=10)  # 最大排队请求数
        self._request_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sim-request")
        self._processing_request = False
        self._request_condition = threading.Condition()
        self._active_requests: Dict[str, Future] = {}  # 跟踪活跃请求

        # PD 控制器参数
        self.kp = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0])  # 比例增益
        self.kd = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 100.0])    # 微分增益

        # 关节限制 (UR5)
        self.joint_limits = {
            'min': np.array([-2*np.pi, -2*np.pi, -np.pi, -2*np.pi, -2*np.pi, -2*np.pi]),
            'max': np.array([2*np.pi, 2*np.pi, np.pi, 2*np.pi, 2*np.pi, 2*np.pi])
        }

    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        加载 MJCF 模型

        Args:
            model_path: 模型文件路径，如果为None则使用默认路径
                      支持 ur5.xml 和 environment.xml

        Returns:
            bool: 加载是否成功
        """
        with self._lock:
            try:
                # 更新模型路径
                if model_path:
                    self.model_path = model_path

                # 检查 MuJoCo 是否可用
                if not mujoco:
                    raise ImportError("MuJoCo 未安装，请运行: pip install mujoco")

                # 验证模型文件路径
                import os
                if not os.path.exists(self.model_path):
                    raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

                print(f"正在加载模型: {self.model_path}")

                # 停止当前仿真（如果正在运行）
                was_running = self._running
                if was_running:
                    self.stop_realtime_simulation()

                # 清理现有模型
                old_model = self.model
                self.model = None
                self.data = None

                try:
                    # 从 XML 文件加载模型
                    self.model = mujoco.MjModel.from_xml_path(self.model_path)

                    # 创建仿真数据对象
                    self.data = mujoco.MjData(self.model)

                    # 验证模型完整性
                    if not self._validate_model():
                        raise ValueError("模型验证失败")

                    # 初始化控制信号和状态
                    self._initialize_model_state()

                    # 打印模型信息
                    self._print_model_info()

                    # 如果之前在运行，重新启动
                    if was_running:
                        self.start_realtime_simulation()

                    # 清理旧模型
                    if old_model:
                        del old_model

                    print("模型加载成功")
                    return True

                except Exception as inner_e:
                    # 恢复旧模型（如果存在）
                    self.model = old_model
                    if old_model:
                        self.data = mujoco.MjData(old_model)
                    raise inner_e

            except ImportError as e:
                print(f"依赖错误: {e}")
                print("请确保已安装 MuJoCo: pip install mujoco")
                return False
            except FileNotFoundError as e:
                print(f"文件错误: {e}")
                return False
            except ValueError as e:
                print(f"模型验证错误: {e}")
                return False
            except Exception as e:
                print(f"模型加载失败: {e}")
                import traceback
                traceback.print_exc()
                return False

    def _validate_model(self) -> bool:
        """
        验证加载的模型是否有效

        Returns:
            bool: 模型是否有效
        """
        if not self.model:
            return False

        try:
            # 检查基本属性
            if self.model.njnt < 0:
                print("警告: 关节数量异常")
                return False

            if self.model.nu < 0:
                print("警告: 执行器数量异常")
                return False

            # 检查是否有必要的关节（针对 UR5 模型）
            if "ur5" in self.model_path.lower():
                if self.model.njnt < 6:
                    print("警告: UR5 模型应至少有 6 个关节")
                    return False

                if self.model.nu < 6:
                    print("警告: UR5 模型应至少有 6 个执行器")
                    return False

            # 检查是否有几何体
            if self.model.ngeom == 0:
                print("警告: 模型不包含几何体")
                return False

            return True

        except Exception as e:
            print(f"模型验证过程中出错: {e}")
            return False

    def _initialize_model_state(self) -> None:
        """
        初始化模型状态
        """
        if not self.model or not self.data:
            return

        try:
            # 初始化控制信号
            if self.model.nu > 0:
                # 设置控制信号为当前位置
                self.data.ctrl[:self.model.nu] = self.data.qpos[:self.model.nu]

            # 执行前向运动学，确保状态一致
            mujoco.mj_forward(self.model, self.data)

            # 重置速度和加速度
            if hasattr(self.data, 'qvel') and self.model.nv > 0:
                self.data.qvel[:] = 0.0
            if hasattr(self.data, 'qacc') and self.model.nv > 0:
                self.data.qacc[:] = 0.0

            # 设置默认姿态（针对 UR5）
            if "ur5" in self.model_path.lower() and self.model.njnt >= 6:
                # UR5 home pose
                home_pose = np.array([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
                self.data.qpos[:6] = home_pose
                if self.model.nu >= 6:
                    self.data.ctrl[:6] = home_pose

                # 重新计算前向运动学
                mujoco.mj_forward(self.model, self.data)

        except Exception as e:
            print(f"模型状态初始化警告: {e}")

    def _print_model_info(self) -> None:
        """
        打印模型详细信息
        """
        if not self.model:
            return

        print("=" * 50)
        print("模型信息:"        print(f"  文件: {self.model_path}")
        print(f"  关节数量: {self.model.njnt}")
        print(f"  执行器数量: {self.model.nu}")
        print(f"  自由度: {self.model.nv}")
        print(f"  几何体数量: {self.model.ngeom}")
        print(f"  传感器数量: {self.model.nsensor}")
        print(f"  身体数量: {self.model.nbody}")

        # 打印关节信息
        if self.model.njnt > 0:
            print("关节列表:")
            for i in range(self.model.njnt):
                joint_name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, i)
                joint_type = self.model.jnt_type[i]
                joint_type_name = ["hinge", "slide", "free", "ball"][joint_type] if joint_type < 4 else "unknown"
                print(f"  {i}: {joint_name} ({joint_type_name})")

        # 打印执行器信息
        if self.model.nu > 0:
            print("执行器列表:")
            for i in range(self.model.nu):
                actuator_name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
                print(f"  {i}: {actuator_name}")

        print("=" * 50)

    def submit_request(self, request_type: str, **kwargs) -> Future:
        """
        提交异步请求到队列

        Args:
            request_type: 请求类型 ("control", "reset", "render", etc.)
            **kwargs: 请求参数

        Returns:
            Future: 请求的 future 对象
        """
        if self._request_queue.full():
            # 创建失败的 future
            future = Future()
            future.set_exception(queue.Full("请求队列已满，请稍后重试"))
            return future

        # 创建请求数据
        request_data = {
            'type': request_type,
            'kwargs': kwargs,
            'timestamp': time.time(),
            'future': Future()
        }

        # 提交到队列
        try:
            self._request_queue.put_nowait(request_data)

            # 启动处理（如果没有在处理）
            with self._request_condition:
                if not self._processing_request:
                    self._request_executor.submit(self._process_request_queue)

            return request_data['future']

        except queue.Full:
            future = Future()
            future.set_exception(queue.Full("请求队列已满"))
            return future

    def _process_request_queue(self) -> None:
        """处理请求队列（单线程执行）"""
        with self._request_condition:
            self._processing_request = True

        try:
            while not self._request_queue.empty():
                try:
                    # 获取请求
                    request_data = self._request_queue.get_nowait()
                    request_type = request_data['type']
                    kwargs = request_data['kwargs']
                    future = request_data['future']

                    # 处理请求
                    result = self._execute_request(request_type, **kwargs)

                    # 设置结果
                    if isinstance(result, Exception):
                        future.set_exception(result)
                    else:
                        future.set_result(result)

                    # 标记任务完成
                    self._request_queue.task_done()

                except queue.Empty:
                    break
                except Exception as e:
                    print(f"处理请求时出错: {e}")
                    if 'future' in locals():
                        future.set_exception(e)

        finally:
            with self._request_condition:
                self._processing_request = False

    def _execute_request(self, request_type: str, **kwargs):
        """执行单个请求"""
        try:
            if request_type == "control":
                return self.step_simulation(**kwargs)
            elif request_type == "reset":
                return self.reset_simulation(**kwargs)
            elif request_type == "render":
                return self.render_camera(**kwargs)
            elif request_type == "get_image":
                return self.get_camera_image(**kwargs)
            elif request_type == "list_cameras":
                return self.list_cameras()
            elif request_type == "load_model":
                return self.load_model(**kwargs)
            else:
                raise ValueError(f"未知请求类型: {request_type}")

        except Exception as e:
            print(f"执行请求 {request_type} 失败: {e}")
            return e

    def reset_simulation(self) -> bool:
        """
        重置仿真状态

        Returns:
            bool: 重置是否成功
        """
        with self._lock:
            if not self.model or not self.data:
                print("错误: 模型未加载")
                return False

            try:
                # 重置仿真数据
                mujoco.mj_resetData(self.model, self.data)

                # 设置默认关节位置 (UR5 home pose)
                home_pose = np.array([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
                self.data.qpos[:6] = home_pose
                self.data.ctrl[:] = home_pose

                # 前向运动学计算
                mujoco.mj_forward(self.model, self.data)

                # 更新状态缓存
                self._update_state()

                print("仿真重置完成")
                return True

            except Exception as e:
                print(f"仿真重置失败: {e}")
                return False

    def step_simulation(self, target_positions: List[float],
                       n_steps: int = 1,
                       kp: Optional[np.ndarray] = None,
                       kd: Optional[np.ndarray] = None,
                       control_mode: str = "position") -> bool:
        """
        执行仿真步进

        Args:
            target_positions: 目标关节位置 (rad)
            n_steps: 步进次数
            kp: 比例增益 (可选)
            kd: 微分增益 (可选)
            control_mode: 控制模式 ("position", "velocity", "torque")

        Returns:
            bool: 步进是否成功
        """
        with self._lock:
            if not self.model or not self.data:
                print("错误: 模型未加载")
                return False

            try:
                # 参数验证
                if n_steps <= 0:
                    raise ValueError("n_steps 必须大于 0")

                if len(target_positions) == 0:
                    raise ValueError("目标位置不能为空")

                if control_mode not in ["position", "velocity", "torque"]:
                    raise ValueError(f"不支持的控制模式: {control_mode}")

                # 更新控制器参数
                if kp is not None:
                    self.kp = np.array(kp)
                if kd is not None:
                    self.kd = np.array(kd)

                # 转换为 numpy 数组
                target_pos = np.array(target_positions, dtype=np.float64)

                # 验证目标位置维度
                if len(target_pos) > self.model.nu:
                    print(f"警告: 目标位置维度 ({len(target_pos)}) 超过执行器数量 ({self.model.nu})，将截断")
                    target_pos = target_pos[:self.model.nu]

                # 记录初始状态
                initial_qpos = self.data.qpos[:len(target_pos)].copy()
                start_time = time.time()

                # 执行控制步进
                success = self._execute_control_steps(target_pos, n_steps, control_mode)

                if success:
                    # 计算执行时间和性能指标
                    execution_time = time.time() - start_time
                    final_qpos = self.data.qpos[:len(target_pos)]

                    # 更新状态缓存和时间戳
                    self._update_state()

                    # 打印控制结果（调试信息）
                    if n_steps > 1:  # 只在多步控制时打印
                        self._print_control_results(initial_qpos, final_qpos, target_pos, execution_time, n_steps)

                return success

            except ValueError as e:
                print(f"参数错误: {e}")
                return False
            except Exception as e:
                print(f"仿真步进失败: {e}")
                import traceback
                traceback.print_exc()
                return False

    def _execute_control_steps(self, target_pos: np.ndarray, n_steps: int, control_mode: str) -> bool:
        """
        执行控制步进的核心逻辑

        Args:
            target_pos: 目标位置数组
            n_steps: 步进次数
            control_mode: 控制模式

        Returns:
            bool: 执行是否成功
        """
        # 关节角度限制处理
        target_pos_clipped = self._apply_joint_limits(target_pos)

        # 控制循环
        for step in range(n_steps):
            try:
                if control_mode == "position":
                    # PD 位置控制
                    control_signal = self._compute_pd_control(target_pos_clipped)
                elif control_mode == "velocity":
                    # 速度控制
                    control_signal = self._compute_velocity_control(target_pos_clipped)
                elif control_mode == "torque":
                    # 力矩控制
                    control_signal = target_pos_clipped
                else:
                    raise ValueError(f"未知控制模式: {control_mode}")

                # 设置控制信号
                self.data.ctrl[:len(control_signal)] = control_signal

                # 执行仿真步进
                mujoco.mj_step(self.model, self.data)

                # 检查仿真状态
                if not self._check_simulation_health():
                    print(f"警告: 仿真状态异常，在步骤 {step + 1}/{n_steps}")
                    # 可以选择继续或停止，暂时继续

            except Exception as e:
                print(f"控制步骤 {step + 1} 失败: {e}")
                return False

        return True

    def _apply_joint_limits(self, target_pos: np.ndarray) -> np.ndarray:
        """
        应用关节角度限制

        Args:
            target_pos: 目标位置数组

        Returns:
            np.ndarray: 限制后的目标位置
        """
        # 获取对应关节的限制
        n_joints = min(len(target_pos), len(self.joint_limits['min']), len(self.joint_limits['max']))
        min_limits = self.joint_limits['min'][:n_joints]
        max_limits = self.joint_limits['max'][:n_joints]

        # 应用限制
        clipped_pos = np.clip(target_pos[:n_joints], min_limits, max_limits)

        # 检查是否有截断
        if not np.array_equal(target_pos[:n_joints], clipped_pos):
            diff = np.abs(target_pos[:n_joints] - clipped_pos)
            max_diff = np.max(diff)
            if max_diff > 1e-6:  # 只有显著差异时才警告
                print(f"警告: 目标位置超出关节限制，已自动截断 (最大偏差: {max_diff:.6f} rad)")

        # 如果目标位置维度大于限制的关节数，保持剩余部分不变
        if len(target_pos) > n_joints:
            result = np.concatenate([clipped_pos, target_pos[n_joints:]])
        else:
            result = clipped_pos

        return result

    def _compute_pd_control(self, target_pos: np.ndarray) -> np.ndarray:
        """
        计算 PD 位置控制信号

        Args:
            target_pos: 目标位置

        Returns:
            np.ndarray: 控制信号
        """
        # 获取当前状态
        current_pos = self.data.qpos[:len(target_pos)]
        current_vel = self.data.qvel[:len(target_pos)]

        # 计算误差
        position_error = target_pos - current_pos
        velocity_error = -current_vel  # 期望速度为 0

        # PD 控制律
        n_joints = len(target_pos)
        kp = self.kp[:n_joints] if len(self.kp) >= n_joints else self.kp[0] * np.ones(n_joints)
        kd = self.kd[:n_joints] if len(self.kd) >= n_joints else self.kd[0] * np.ones(n_joints)

        control_signal = kp * position_error + kd * velocity_error

        # 添加控制信号限制（防止过大控制力矩）
        max_torque = 300.0  # Nm，UR5 的典型关节力矩限制
        control_signal = np.clip(control_signal, -max_torque, max_torque)

        return control_signal

    def _compute_velocity_control(self, target_vel: np.ndarray) -> np.ndarray:
        """
        计算速度控制信号

        Args:
            target_vel: 目标速度

        Returns:
            np.ndarray: 控制信号
        """
        # 简化的速度控制（可以根据需要扩展）
        current_vel = self.data.qvel[:len(target_vel)]
        velocity_error = target_vel - current_vel

        # P 控制
        kv = 50.0  # 速度控制增益
        control_signal = kv * velocity_error

        return control_signal

    def _check_simulation_health(self) -> bool:
        """
        检查仿真健康状态

        Returns:
            bool: 仿真是否健康
        """
        try:
            # 检查关节位置是否为有效数值
            if not np.all(np.isfinite(self.data.qpos)):
                print("警告: 关节位置包含无效数值")
                return False

            # 检查关节速度是否过大（可能表示不稳定）
            max_vel = 10.0  # rad/s
            if np.any(np.abs(self.data.qvel) > max_vel):
                print("警告: 关节速度过大，可能不稳定")
                # 不返回False，继续运行

            # 检查接触力是否过大（可能表示碰撞）
            if hasattr(self.data, 'contact') and self.data.ncon > 0:
                for i in range(self.data.ncon):
                    contact_force = np.linalg.norm(self.data.contact[i].force)
                    if contact_force > 1000.0:  # 过大的接触力
                        print(f"警告: 检测到强力碰撞 (力: {contact_force:.1f} N)")
                        # 不返回False，继续运行

            return True

        except Exception as e:
            print(f"健康检查失败: {e}")
            return False

    def _print_control_results(self, initial_qpos: np.ndarray, final_qpos: np.ndarray,
                             target_qpos: np.ndarray, execution_time: float, n_steps: int) -> None:
        """
        打印控制结果（调试信息）

        Args:
            initial_qpos: 初始关节位置
            final_qpos: 最终关节位置
            target_qpos: 目标关节位置
            execution_time: 执行时间
            n_steps: 步进次数
        """
        try:
            # 计算误差统计
            final_error = np.abs(final_qpos - target_qpos)
            max_error = np.max(final_error)
            mean_error = np.mean(final_error)
            rms_error = np.sqrt(np.mean(final_error**2))

            # 计算位置变化
            total_displacement = np.abs(final_qpos - initial_qpos)
            max_displacement = np.max(total_displacement)

            print("控制结果:"            print(f"  步进次数: {n_steps}")
            print(f"  执行时间: {execution_time:.4f} s")
            print(f"  平均步进时间: {execution_time/n_steps*1000:.2f} ms")
            print(f"  最大位置误差: {max_error:.6f} rad ({np.degrees(max_error):.2f}°)")
            print(f"  平均位置误差: {mean_error:.6f} rad ({np.degrees(mean_error):.2f}°)")
            print(f"  RMS 位置误差: {rms_error:.6f} rad ({np.degrees(rms_error):.2f}°)")
            print(f"  最大位移: {max_displacement:.6f} rad ({np.degrees(max_displacement):.2f}°)")

            # 成功标准检查
            if max_error < 0.01:  # 0.01 rad ≈ 0.57°
                print("  ✓ 控制精度良好")
            elif max_error < 0.05:  # 0.05 rad ≈ 2.86°
                print("  ⚠ 控制精度一般")
            else:
                print("  ✗ 控制精度不足")

        except Exception as e:
            print(f"打印控制结果失败: {e}")

    def get_current_state(self) -> Optional[SimState]:
        """
        获取当前仿真状态

        Returns:
            SimState: 当前状态，如果仿真未初始化则返回 None
        """
        with self._lock:
            if not self.model or not self.data:
                return None

            # 如果状态缓存过期，更新状态
            if self._current_state is None:
                self._update_state()

            return self._current_state

    def _update_state(self) -> None:
        """内部方法：更新状态缓存"""
        if not self.model or not self.data:
            return

        # 计算末端执行器位姿
        ee_pose = self._get_end_effector_pose()

        # 创建状态对象
        self._current_state = SimState(
            timestamp=time.time(),
            qpos=self.data.qpos[:6].tolist(),
            qvel=self.data.qvel[:6].tolist(),
            ctrl=self.data.ctrl[:6].tolist(),
            ee_pose=ee_pose
        )

    def _get_end_effector_pose(self) -> Dict[str, List[float]]:
        """
        获取末端执行器位姿

        Returns:
            dict: 包含位置和姿态的字典
        """
        if not self.model or not self.data:
            return {"position": [0.0, 0.0, 0.0], "orientation": [0.0, 0.0, 0.0, 1.0]}

        # 假设末端执行器 body 名称为 "wrist_3_link" 或类似
        # 这里需要根据实际模型调整
        try:
            # 获取末端执行器 body id (需要根据模型定义调整)
            ee_body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "wrist_3_link")

            # 获取位置和姿态
            position = self.data.xpos[ee_body_id].tolist()
            orientation = self.data.xquat[ee_body_id].tolist()

            return {
                "position": position,
                "orientation": orientation
            }
        except:
            # 如果找不到末端执行器 body，返回默认值
            return {
                "position": [0.0, 0.0, 0.0],
                "orientation": [0.0, 0.0, 0.0, 1.0]
            }

    def render_camera(self, camera_name: str = "camera1",
                     width: int = 640, height: int = 480,
                     format: str = "rgb") -> Optional[np.ndarray]:
        """
        渲染相机图像

        Args:
            camera_name: 相机名称
            width: 图像宽度 (支持 320x240, 640x480)
            height: 图像高度
            format: 输出格式 ("rgb", "rgba", "depth")

        Returns:
            np.ndarray: 图像数组，如果失败返回 None
        """
        with self._render_lock:
            if not self.model or not self.data:
                print("错误: 模型未加载，无法渲染相机")
                return None

            if not mujoco or not mujoco.renderer:
                print("错误: MuJoCo 渲染器不可用")
                return None

            try:
                # 检查缓存是否有效
                current_time = time.time()
                cache_key = f"{camera_name}_{width}_{height}_{format}"

                if (self._render_cache and
                    cache_key in self._render_cache and
                    current_time - self._last_render_time < self._cache_timeout):
                    return self._render_cache[cache_key]

                # 初始化渲染器（如果需要）
                if self.renderer is None:
                    try:
                        self.renderer = mujoco.renderer.Renderer(self.model, height, width)
                        print(f"✓ 渲染器初始化成功: {width}x{height}")
                    except Exception as e:
                        print(f"渲染器初始化失败: {e}")
                        return None

                # 检查渲染器分辨率是否匹配
                if self.renderer.height != height or self.renderer.width != width:
                    try:
                        # 重新创建渲染器
                        old_renderer = self.renderer
                        self.renderer = mujoco.renderer.Renderer(self.model, height, width)
                        if old_renderer:
                            del old_renderer
                        print(f"✓ 渲染器分辨率更新: {width}x{height}")
                    except Exception as e:
                        print(f"渲染器分辨率更新失败: {e}")
                        return None

                # 查找相机 ID
                camera_id = self._find_camera_id(camera_name)
                if camera_id is None:
                    print(f"警告: 找不到相机 '{camera_name}'，使用默认相机")
                    camera_id = 0  # 使用默认相机

                # 渲染图像
                try:
                    if format == "rgb":
                        # 渲染 RGB 图像
                        self.renderer.update_scene(self.data, camera=camera_id)
                        rgb_image = self.renderer.render()
                        result = rgb_image.copy()
                    elif format == "rgba":
                        # 渲染 RGBA 图像
                        self.renderer.update_scene(self.data, camera=camera_id)
                        rgba_image = self.renderer.render()
                        # 转换为 RGBA (如果需要)
                        if rgba_image.shape[2] == 3:
                            alpha = np.full((height, width, 1), 255, dtype=np.uint8)
                            result = np.concatenate([rgba_image, alpha], axis=2)
                        else:
                            result = rgba_image.copy()
                    elif format == "depth":
                        # 渲染深度图像
                        self.renderer.enable_depth_rendering()
                        self.renderer.update_scene(self.data, camera=camera_id)
                        depth_image = self.renderer.render()
                        result = depth_image.copy()
                        self.renderer.disable_depth_rendering()
                    else:
                        print(f"错误: 不支持的图像格式 '{format}'")
                        return None

                    # 更新缓存
                    if self._render_cache is None:
                        self._render_cache = {}

                    self._render_cache[cache_key] = result
                    self._last_render_time = current_time

                    return result

                except Exception as e:
                    print(f"相机渲染失败: {e}")
                    return None

            except Exception as e:
                print(f"相机渲染过程中出错: {e}")
                return None

    def _find_camera_id(self, camera_name: str) -> Optional[int]:
        """
        查找相机 ID

        Args:
            camera_name: 相机名称

        Returns:
            int: 相机 ID，如果找不到返回 None
        """
        if not self.model:
            return None

        try:
            # 遍历所有相机
            for i in range(self.model.ncam):
                name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_CAMERA, i)
                if name == camera_name:
                    return i

            # 如果找不到，尝试模糊匹配
            camera_name_lower = camera_name.lower()
            for i in range(self.model.ncam):
                name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_CAMERA, i)
                if name and camera_name_lower in name.lower():
                    print(f"使用模糊匹配的相机: '{name}' (请求: '{camera_name}')")
                    return i

            return None

        except Exception as e:
            print(f"查找相机 ID 时出错: {e}")
            return None

    def get_camera_image(self, camera_name: str = "camera1",
                        width: int = 640, height: int = 480,
                        format: str = "jpeg",
                        quality: int = 80) -> Optional[bytes]:
        """
        获取相机图像（编码格式）

        Args:
            camera_name: 相机名称
            width: 图像宽度
            height: 图像高度
            format: 输出格式 ("jpeg", "png", "base64")
            quality: JPEG 质量 (0-100)

        Returns:
            bytes: 编码后的图像数据，如果失败返回 None
        """
        # 获取 RGB 图像
        rgb_image = self.render_camera(camera_name, width, height, format="rgb")
        if rgb_image is None:
            return None

        try:
            if format.lower() == "base64":
                # 返回 base64 编码的 JPEG
                jpeg_data = self._encode_jpeg(rgb_image, quality)
                if jpeg_data:
                    return base64.b64encode(jpeg_data)
                return None

            elif format.lower() == "jpeg":
                return self._encode_jpeg(rgb_image, quality)

            elif format.lower() == "png":
                return self._encode_png(rgb_image)

            else:
                print(f"错误: 不支持的编码格式 '{format}'")
                return None

        except Exception as e:
            print(f"图像编码失败: {e}")
            return None

    def _encode_jpeg(self, rgb_image: np.ndarray, quality: int = 80) -> Optional[bytes]:
        """将 RGB 图像编码为 JPEG"""
        try:
            # 确保图像是正确的格式
            if rgb_image.dtype != np.uint8:
                # 归一化到 0-255
                if rgb_image.max() <= 1.0:
                    rgb_image = (rgb_image * 255).astype(np.uint8)
                else:
                    rgb_image = rgb_image.astype(np.uint8)

            # 使用 PIL 编码 JPEG
            from PIL import Image
            img = Image.fromarray(rgb_image)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()

        except ImportError:
            print("错误: 需要安装 Pillow 来编码图像: pip install Pillow")
            return None
        except Exception as e:
            print(f"JPEG 编码失败: {e}")
            return None

    def _encode_png(self, rgb_image: np.ndarray) -> Optional[bytes]:
        """将 RGB 图像编码为 PNG"""
        try:
            # 确保图像是正确的格式
            if rgb_image.dtype != np.uint8:
                if rgb_image.max() <= 1.0:
                    rgb_image = (rgb_image * 255).astype(np.uint8)
                else:
                    rgb_image = rgb_image.astype(np.uint8)

            # 使用 PIL 编码 PNG
            from PIL import Image
            img = Image.fromarray(rgb_image)
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            return buffer.getvalue()

        except ImportError:
            print("错误: 需要安装 Pillow 来编码图像: pip install Pillow")
            return None
        except Exception as e:
            print(f"PNG 编码失败: {e}")
            return None

    def list_cameras(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的相机

        Returns:
            List[Dict]: 相机信息列表
        """
        cameras = []

        if not self.model:
            return cameras

        try:
            for i in range(self.model.ncam):
                name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_CAMERA, i)
                if name:
                    cameras.append({
                        "id": i,
                        "name": name,
                        "fovy": float(self.model.cam_fovy[i]),
                        "pos": self.model.cam_pos[i].tolist() if hasattr(self.model, 'cam_pos') else None,
                        "quat": self.model.cam_quat[i].tolist() if hasattr(self.model, 'cam_quat') else None
                    })

        except Exception as e:
            print(f"列出相机时出错: {e}")

        return cameras

    def start_realtime_simulation(self) -> None:
        """启动实时仿真线程"""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self._simulation_thread.start()

    def stop_realtime_simulation(self) -> None:
        """停止实时仿真线程"""
        with self._lock:
            self._running = False
            if self._simulation_thread:
                self._simulation_thread.join(timeout=1.0)

    def _simulation_loop(self) -> None:
        """内部仿真循环"""
        while self._running:
            with self._lock:
                if self.model and self.data:
                    # 执行一步仿真
                    mujoco.mj_step(self.model, self.data)
                    self._update_state()

            # 控制循环频率 (~500Hz)
            time.sleep(0.002)

    def __del__(self):
        """析构函数"""
        self.stop_realtime_simulation()

        # 清理渲染器
        with self._render_lock:
            if self.renderer:
                try:
                    del self.renderer
                    self.renderer = None
                except Exception as e:
                    print(f"清理渲染器时出错: {e}")

        # 清理请求执行器
        try:
            self._request_executor.shutdown(wait=True)
        except Exception as e:
            print(f"清理请求执行器时出错: {e}")

        # 取消所有待处理的请求
        try:
            while not self._request_queue.empty():
                try:
                    request_data = self._request_queue.get_nowait()
                    if 'future' in request_data and not request_data['future'].done():
                        request_data['future'].cancel()
                    self._request_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            print(f"清理请求队列时出错: {e}")


# 全局仿真实例
_simulation_instance: Optional[Simulation] = None
_simulation_lock = threading.Lock()


def get_simulation_instance() -> Simulation:
    """
    获取全局仿真实例 (单例模式)

    Returns:
        Simulation: 仿真实例
    """
    global _simulation_instance

    if _simulation_instance is None:
        with _simulation_lock:
            if _simulation_instance is None:
                _simulation_instance = Simulation()

    return _simulation_instance
