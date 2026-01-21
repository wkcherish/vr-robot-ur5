/**
 * WebSocket 管理器
 * 提供全局 WebSocket 连接管理和消息发送功能
 */

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
  }

  // 连接到 WebSocket 服务器
  connect(url = 'ws://localhost:8000/sim/ws') {
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
  sendMessage(message) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      try {
        this.websocket.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('发送 WebSocket 消息失败:', error);
        this.messageQueue.push(message);
        return false;
      }
    } else {
      this.messageQueue.push(message);
      return false;
    }
  }

  // 发送控制命令
  sendControlCommand(targetPositions, options = {}) {
    const message = {
      type: 'control',
      data: {
        target_positions: targetPositions,
        n_steps: options.n_steps || 10,
        kp: options.kp,
        kd: options.kd,
        control_mode: options.control_mode || 'position'
      },
      timestamp: Date.now()
    };

    return this.sendMessage(message);
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

  // 事件监听
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.eventListeners.has(event)) {
      const listeners = this.eventListeners.get(event);
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
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
    const { type, data } = message;

    switch (type) {
      case 'welcome':
        console.log('收到服务器欢迎消息:', data.message);
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
    this.emit('stateUpdate', data);
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
