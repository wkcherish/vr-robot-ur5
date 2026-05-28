/**
 * WebSocket 管理器
 * 提供全局 WebSocket 连接管理和消息发送功能
 */

import { runtimeConfig } from "./runtimeConfig";

class WebSocketManager {
  constructor() {
    this.websocket = null;
    this.isConnected = false;
    this.connectionStatus = '未连接';
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = null;
    this.messageQueue = [];
    this.eventListeners = new Map();

    // 状态管理
    this.simulationState = null;
    this.lastStateUpdate = 0;

    // 关节限位缓存（来自后端 state_broadcast.joint_limits）
    // 形如 { jointName: [lo, hi] }，顺序与 jointNames 一致
    this.jointNames = null;
    this.jointLimits = null;
  }

  // 连接到 WebSocket 服务器
  connect(url = runtimeConfig.simWsUrl) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      console.log('WebSocket 已经连接');
      return;
    }

    try {
      console.log(`尝试连接到: ${url}`);
      this.websocket = new WebSocket(url);
      this.websocket.onopen = this.handleOpen.bind(this);
      this.websocket.onmessage = this.handleMessage.bind(this);
      this.websocket.onclose = this.handleClose.bind(this);
      this.websocket.onerror = this.handleError.bind(this);

      this.connectionStatus = '连接中...';
      this.emit('statusChange', this.connectionStatus);
    } catch (error) {
      console.error('WebSocket 连接失败:', error);
      this.connectionStatus = '连接失败';
      this.emit('statusChange', this.connectionStatus);
      this.scheduleReconnect();
    }
  }

  // 断开连接
  disconnect() {
    if (this.websocket) {
      console.log('断开 WebSocket 连接');
      this.websocket.close(1000, '用户断开连接');
      this.websocket = null;
    }
    this.isConnected = false;
    this.connectionStatus = '已断开';
    this.emit('statusChange', this.connectionStatus);

    if (this.reconnectInterval) {
      clearTimeout(this.reconnectInterval);
      this.reconnectInterval = null;
    }
  }

  // 发送消息
  sendMessage(message, options = {}) {
    const queueWhenUnavailable = options.queueWhenUnavailable !== false;
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      try {
        this.websocket.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('发送 WebSocket 消息失败:', error);
        if (queueWhenUnavailable) {
          this.messageQueue.push(message);
        }
        return false;
      }
    } else {
      if (queueWhenUnavailable) {
        this.messageQueue.push(message);
      }
      return false;
    }
  }

  // 发送控制命令
  sendControlCommand(targetPositions, options = {}) {
    const clampedTargets = this.clampToJointLimits(targetPositions);
    const payload = {
      target_positions: clampedTargets,
      n_steps: Number.isFinite(Number(options.n_steps))
        ? Math.max(1, Math.floor(Number(options.n_steps)))
        : 2,
      kp: options.kp,
      kd: options.kd,
      control_mode: options.control_mode || 'position'
    };

    if (options.target_ee_pose && typeof options.target_ee_pose === 'object') {
      payload.target_ee_pose = options.target_ee_pose;
    }

    if (Array.isArray(options.target_ee_delta)) {
      payload.target_ee_delta = options.target_ee_delta.slice(0, 3).map((value) => Number(value));
    }

    if (typeof options.expect_result === 'boolean') {
      payload.expect_result = options.expect_result;
    }

    if (typeof options.ack === 'boolean') {
      payload.ack = options.ack;
    }

    if (options.gripper_command && typeof options.gripper_command === 'object') {
      payload.gripper_command = options.gripper_command;
    } else if (Number.isFinite(Number(options.gripper_opening))) {
      const opening = Math.min(Math.max(Number(options.gripper_opening), 0), 1);
      payload.gripper_command = { mode: 'open_close', value: opening };
    }

    if (typeof options.source === 'string' && options.source.length > 0) {
      payload.source = options.source;
    }

    if (typeof options.input_source === 'string' && options.input_source.length > 0) {
      payload.input_source = options.input_source;
    }

    if (typeof options.selected_joint_group === 'string' && options.selected_joint_group.length > 0) {
      payload.selected_joint_group = options.selected_joint_group;
    }

    if (options.raw_input && typeof options.raw_input === 'object') {
      payload.raw_input = options.raw_input;
    }

    if (options.normalized_input && typeof options.normalized_input === 'object') {
      payload.normalized_input = options.normalized_input;
    }

    const message = {
      type: 'control',
      data: payload,
      timestamp: Date.now()
    };

    return this.sendMessage(message, { queueWhenUnavailable: false });
  }

  sendExecuteTask(taskName = 'quest3_tool_sorting_v1') {
    return this.sendMessage({
      type: 'execute_task',
      data: { task_name: taskName },
      timestamp: Date.now()
    });
  }

  sendStopTask() {
    return this.sendMessage({
      type: 'stop_task',
      timestamp: Date.now()
    });
  }

  sendVrStateUpdate(payload = {}) {
    return this.sendMessage({
      type: "vr_state",
      data: payload,
      timestamp: Date.now(),
    });
  }

  // 发送重置命令
  sendResetCommand(modelPath = null) {
    const message = {
      type: 'reset',
      data: modelPath ? { model_path: modelPath } : {},
      timestamp: Date.now()
    };

    return this.sendMessage(message);
  }

  // 获取状态
  requestState() {
    const message = {
      type: 'get_state',
      timestamp: Date.now()
    };

    return this.sendMessage(message);
  }

  requestObservation(includeData = false) {
    return this.sendMessage({
      type: 'get_observation',
      data: { include_data: Boolean(includeData) },
      timestamp: Date.now()
    });
  }

  // 事件监听
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  off(event, callback) {
    if (!this.eventListeners.has(event)) return;

    if (!callback) {
      this.eventListeners.delete(event);
      return;
    }

    const listeners = this.eventListeners.get(event);
    const index = listeners.indexOf(callback);
    if (index > -1) {
      listeners.splice(index, 1);
    }

    if (listeners.length === 0) {
      this.eventListeners.delete(event);
    }
  }

  emit(event, ...args) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(...args);
        } catch (error) {
          console.error('事件回调执行失败:', error);
        }
      });
    }
  }

  // WebSocket 事件处理
  handleOpen(event) {
    console.log('WebSocket 连接已建立');
    this.isConnected = true;
    this.connectionStatus = '已连接';
    this.reconnectAttempts = 0;
    this.emit('statusChange', this.connectionStatus);
    this.emit('connected');

    // 发送欢迎消息
    this.sendMessage({
      type: 'ping',
      data: { client: 'vue-control-component' }
    });

    // 发送队列中的消息
    this.messageQueue.forEach(message => {
      this.sendMessage(message);
    });
    this.messageQueue = [];
  }

  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      this.handleMessageData(message);
    } catch (error) {
      console.error('解析 WebSocket 消息失败:', error, event.data);
    }
  }

  handleMessageData(message) {
    // Some server messages put the payload under `data`, others (legacy) place fields at top-level.
    // Be defensive: prefer `message.data` but fall back to the message itself.
    const type = message && message.type ? message.type : null;
    const data = message && (message.data !== undefined) ? message.data : message;

    switch (type) {
      case 'welcome':
        // welcome may contain a top-level `message` string (legacy) or be under `data.message`.
        console.log('收到服务器欢迎消息:', data && data.message ? data.message : message.message);
        this.emit('welcome', data);
        break;

      case 'state_update':
        this.handleStateUpdate(data);
        break;

      case 'state_broadcast':
        this.handleStateUpdate(data);
        break;

      case 'control_result':
        this.emit('controlResult', data);
        break;

      case 'reset_result':
        this.emit('resetResult', data);
        break;

      case 'task_result':
        this.emit('taskResult', data);
        break;

      case 'vr_state_result':
        this.emit('vrStateResult', data);
        break;

      case 'observation_update':
        this.emit('observationUpdate', data);
        break;

      case 'camera_rgb_update':
        this.emit('cameraRgbUpdate', data);
        break;

      case 'camera_depth_update':
        this.emit('cameraDepthUpdate', data);
        break;

      case 'error':
        this.emit('error', data);
        break;

      case 'pong':
        this.emit('pong', data);
        break;

      default:
        console.log('收到未知消息类型:', type, message);
        this.emit('unknownMessage', message);
    }
  }

  handleStateUpdate(data) {
    this.simulationState = data;
    this.lastStateUpdate = Date.now();
    if (data && Array.isArray(data.joint_names)) {
      this.jointNames = data.joint_names.map((name) => String(name));
    }
    if (data && data.joint_limits && typeof data.joint_limits === 'object') {
      this.jointLimits = data.joint_limits;
    }
    this.emit('stateUpdate', data);
  }

  // 将目标关节角裁剪到后端公布的关节限位内，防止越过物理边界
  clampToJointLimits(targetPositions) {
    if (!Array.isArray(targetPositions)) return targetPositions;
    if (!this.jointLimits || !Array.isArray(this.jointNames)) return targetPositions;
    return targetPositions.map((value, idx) => {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return value;
      const name = this.jointNames[idx];
      if (!name) return numeric;
      const limits = this.jointLimits[name];
      if (!Array.isArray(limits) || limits.length !== 2) return numeric;
      const lo = Number(limits[0]);
      const hi = Number(limits[1]);
      if (!Number.isFinite(lo) || !Number.isFinite(hi)) return numeric;
      if (numeric < lo) return lo;
      if (numeric > hi) return hi;
      return numeric;
    });
  }

  handleClose(event) {
    console.log(`WebSocket 连接关闭, 代码: ${event.code}, 原因: ${event.reason}`);
    this.isConnected = false;
    this.connectionStatus = '连接断开';
    this.emit('statusChange', this.connectionStatus);
    this.emit('disconnected', event);

    if (event.code !== 1000) {
      this.scheduleReconnect();
    }
  }

  handleError(error) {
    console.error('WebSocket 错误:', error);
    this.connectionStatus = '连接错误';
    this.isConnected = false;
    this.emit('statusChange', this.connectionStatus);
    this.emit('error', error);
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.connectionStatus = '重连失败，请检查服务器';
      console.error('达到最大重连次数，停止重连');
      this.emit('reconnectFailed');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

    this.connectionStatus = `${this.reconnectAttempts}/${this.maxReconnectAttempts} 重连中... (${delay}ms)`;
    this.emit('statusChange', this.connectionStatus);

    this.reconnectInterval = setTimeout(() => {
      console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      this.connect();
    }, delay);
  }

  // 获取连接状态
  getStatus() {
    return {
      isConnected: this.isConnected,
      status: this.connectionStatus,
      reconnectAttempts: this.reconnectAttempts,
      lastStateUpdate: this.lastStateUpdate,
      simulationState: this.simulationState
    };
  }
}

// 创建全局实例
const websocketManager = new WebSocketManager();

// 导出单例
export default websocketManager;
