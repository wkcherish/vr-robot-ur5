<template>
  <div class="control-panel">
    <h3 class="panel-title">仿真控制系统</h3>

    <!-- 仿真控制区 -->
    <div class="panel-section">
      <h4 class="section-title">仿真控制</h4>
      <div class="control-grid">
        <button
          @click="toggleSimulation"
          class="control-button"
          :class="{ active: isSimulationRunning }"
          :disabled="!isConnected || commandPending"
        >
          <span class="btn-icon">{{ isSimulationRunning ? "⏹" : "▶" }}</span>
          {{ isSimulationRunning ? "停止仿真" : "开始仿真" }}
        </button>
        <button
          @click="resetSimulation"
          class="control-button secondary"
          :disabled="!isConnected || commandPending"
        >
          <span class="btn-icon">🔄</span>重置场景
        </button>
      </div>

      <div class="slider-container">
        <div class="slider-label">仿真速度</div>
        <input
          type="range"
          min="0.1"
          max="2"
          step="0.1"
          v-model="simulationSpeed"
          class="speed-slider"
        />
        <div class="slider-value">{{ simulationSpeed }}x</div>
      </div>
    </div>

    <!-- 工具识别区 -->
    <div class="panel-section">
      <h4 class="section-title">工具识别</h4>
        <button
          @click="detectTools"
          class="control-button tertiary"
          :disabled="!isConnected || !isSimulationRunning || commandPending"
        >
          <span class="btn-icon">🔍</span>识别桌面工具
        </button>

      <div v-if="detectedTools.length > 0" class="tools-container">
        <div class="section-subtitle">识别结果</div>
        <div class="tools-list">
          <div
            v-for="(tool, index) in detectedTools"
            :key="index"
            class="tool-item"
            :class="{ selected: selectedToolIndex === index }"
            @click="selectTool(index)"
          >
            <div class="tool-icon">{{ tool.icon }}</div>
            <div class="tool-info">
              <div class="tool-name">{{ tool.name }}</div>
              <div class="tool-position">
                位置: ({{ tool.position.x.toFixed(2) }},
                {{ tool.position.y.toFixed(2) }},
                {{ tool.position.z.toFixed(2) }})
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 抓取操作区 -->
    <div class="panel-section">
      <h4 class="section-title">抓取操作</h4>
      <div class="control-grid">
        <button
          @click="grabTool"
          class="control-button"
          :disabled="
            !isConnected || selectedToolIndex === null || !isSimulationRunning || commandPending
          "
        >
          <span class="btn-icon">✋</span>抓取工具
        </button>
        <button
          @click="placeTool"
          class="control-button secondary"
          :disabled="!isConnected || !isToolGrabbed || !isSimulationRunning || commandPending"
        >
          <span class="btn-icon">👇</span>放置工具
        </button>
      </div>

      <div class="preset-positions" v-if="isToolGrabbed">
        <div class="section-subtitle">预设位置</div>
        <div class="position-buttons">
          <button
            v-for="(position, index) in presetPositions"
            :key="index"
            @click="moveToPosition(position)"
            class="position-button"
            :disabled="!isConnected || !isSimulationRunning || commandPending"
          >
            {{ position.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- 连接状态区 -->
    <div class="panel-section">
      <h4 class="section-title">连接状态</h4>
      <div class="status-container">
        <div class="status-item">
          <div class="status-label">服务器连接:</div>
          <div
            class="status-value"
            :class="{
              'status-active': isConnected,
              'status-inactive': !isConnected,
            }"
          >
            {{ connectionStatus }}
          </div>
        </div>
        <div class="status-item" v-if="commandPending">
          <div class="status-label">命令状态:</div>
          <div class="status-value status-pending">
            <div class="spinner"></div> 正在执行...
          </div>
        </div>
      </div>
      <div class="control-grid" style="margin-top: 12px;">
        <button
          @click="connectWebSocket"
          class="control-button"
          :class="{ active: isConnected }"
          :disabled="isConnected"
        >
          <span class="btn-icon">🔗</span>{{ isConnected ? "已连接" : "连接服务器" }}
        </button>
        <button
          @click="disconnectWebSocket"
          class="control-button secondary"
          :disabled="!isConnected"
        >
          <span class="btn-icon">🔌</span>断开连接
        </button>
      </div>
    </div>

    <!-- 状态反馈区 -->
    <div class="panel-section">
      <h4 class="section-title">操作状态</h4>
      <div class="status-container">
        <div class="status-item">
          <div class="status-label">仿真状态:</div>
          <div
            class="status-value"
            :class="{
              'status-active': isSimulationRunning,
              'status-inactive': !isSimulationRunning,
            }"
          >
            {{ isSimulationRunning ? "运行中" : "已停止" }}
          </div>
        </div>
        <div class="status-item">
          <div class="status-label">当前操作:</div>
          <div class="status-value">{{ currentOperationText }}</div>
        </div>
        <div class="status-item" v-if="operationMessage">
          <div class="status-label">操作反馈:</div>
          <div
            class="status-value"
            :class="{
              'status-success': operationSuccess,
              'status-error': !operationSuccess,
            }"
          >
            {{ operationMessage }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import websocketManager from "../utils/websocket.js";

// 仿真状态
const isSimulationRunning = ref(false);
const simulationSpeed = ref(1.0);
const currentOperation = ref("idle");
const operationMessage = ref("");
const operationSuccess = ref(true);

// WebSocket 连接状态
const isConnected = ref(false);
const connectionStatus = ref("未连接");
const commandPending = ref(false);

// 工具识别相关
const detectedTools = ref([]);
const selectedToolIndex = ref(null);
const isToolGrabbed = ref(false);

// 操作状态相关
const isGrabbing = ref(false);
const isPlacing = ref(false);
const isMoving = ref(false);

// 预设位置
const presetPositions = ref([
  { name: "工作区A", x: 0.2, y: 0.3, z: 0.1 },
  { name: "工作区B", x: -0.2, y: 0.3, z: 0.1 },
  { name: "存放处", x: 0, y: 0.4, z: 0.2 },
]);

const TOOL_ICON_MAP = {
  wrench: "🔧",
  screwdriver: "🪛",
  pliers: "🗜️",
  toolbox: "🧰",
};

const NON_DETECTABLE_OBJECT_IDS = new Set(["rack", "toolbox"]);

function formatToolDisplayName(objectId) {
  const className = String(objectId || "").split("_")[0];
  if (className === "wrench") return "扳手";
  if (className === "screwdriver") return "螺丝刀";
  if (className === "pliers") return "钳子";
  if (className === "toolbox") return "工具箱";
  return className || String(objectId || "未知对象");
}

const extractDetectedToolsFromState = (state) => {
  const objects = state?.objects;
  if (!objects || typeof objects !== "object") {
    return [];
  }

  return Object.entries(objects)
    .filter(([objectId]) => !NON_DETECTABLE_OBJECT_IDS.has(objectId))
    .map(([objectId, pose]) => {
      const position = Array.isArray(pose?.position) ? pose.position : [];
      const [x, y, z] = position.map((v) => Number(v));
      if (![x, y, z].every((v) => Number.isFinite(v))) {
        return null;
      }
      const className = String(objectId).split("_")[0];
      return {
        id: objectId,
        name: formatToolDisplayName(objectId),
        icon: TOOL_ICON_MAP[className] || "🧩",
        position: { x, y, z },
      };
    })
    .filter(Boolean);
};

const updateDetectedToolsFromState = (state) => {
  const tools = extractDetectedToolsFromState(state);
  if (tools.length === 0) return;

  detectedTools.value = tools;
  if (selectedToolIndex.value === null || selectedToolIndex.value >= tools.length) {
    selectedToolIndex.value = 0;
  }
};

// 计算当前操作文本
const currentOperationText = computed(() => {
  switch (currentOperation.value) {
    case "idle":
      return "待机中";
    case "detecting":
      return "正在识别工具...";
    case "grabbing":
      return "正在抓取工具...";
    case "moving":
      return "正在移动工具...";
    case "placing":
      return "正在放置工具...";
    default:
      return "待机中";
  }
});

// WebSocket 事件监听
const setupWebSocketListeners = () => {
  websocketManager.on('statusChange', (status) => {
    connectionStatus.value = status;
    isConnected.value = websocketManager.isConnected;
  });

  websocketManager.on('connected', () => {
    operationMessage.value = "已连接到仿真服务器";
    operationSuccess.value = true;
    websocketManager.requestState();
  });

  websocketManager.on('disconnected', () => {
    isSimulationRunning.value = false;
    operationMessage.value = "仿真服务器连接断开";
    operationSuccess.value = false;
    resetOperationStates();
  });

  websocketManager.on('controlResult', (data) => {
    commandPending.value = false;
    if (data.status === 'success') {
      if (isGrabbing.value) {
        isToolGrabbed.value = true;
        operationMessage.value = "抓取命令执行成功";
      } else if (isMoving.value) {
        operationMessage.value = "移动命令执行成功";
      } else if (isPlacing.value) {
        isToolGrabbed.value = false;
        operationMessage.value = "放置命令执行成功";
      } else {
        operationMessage.value = "控制命令执行成功";
      }
      operationSuccess.value = true;
      resetOperationStates();
    } else {
      operationMessage.value = `控制命令失败: ${data.message || '未知错误'}`;
      operationSuccess.value = false;
      resetOperationStates();
    }
  });

  websocketManager.on('resetResult', (data) => {
    commandPending.value = false;
    if (data.status === 'success') {
      operationMessage.value = "仿真已重置";
      operationSuccess.value = true;
      resetOperationStates();
      detectedTools.value = [];
      selectedToolIndex.value = null;
      isToolGrabbed.value = false;
    } else {
      operationMessage.value = `重置失败: ${data.message || '未知错误'}`;
      operationSuccess.value = false;
    }
  });

  websocketManager.on('stateUpdate', (data) => {
    if (data?.task_state && typeof data.task_state.running === 'boolean') {
      isSimulationRunning.value = Boolean(data.task_state.running);
    }
    updateDetectedToolsFromState(data);
  });

  websocketManager.on('taskResult', (data) => {
    commandPending.value = false;
    if (data?.status === "accepted") {
      isSimulationRunning.value = true;
      operationMessage.value = data.message || "任务已启动";
      operationSuccess.value = true;
      return;
    }
    if (data?.status === "stopped") {
      isSimulationRunning.value = false;
      operationMessage.value = data.message || "任务已停止";
      operationSuccess.value = true;
      resetOperationStates();
      return;
    }
    operationMessage.value = data?.message || "任务状态更新";
    operationSuccess.value = true;
  });

  websocketManager.on('error', (error) => {
    commandPending.value = false;
    operationMessage.value = `WebSocket 错误: ${error.message || '未知错误'}`;
    operationSuccess.value = false;
  });
};

// 开始/停止仿真
const toggleSimulation = () => {
  if (!isConnected.value) {
    operationMessage.value = "请先连接到仿真服务器";
    operationSuccess.value = false;
    return;
  }

  commandPending.value = true;
  if (!isSimulationRunning.value) {
    const success = websocketManager.sendExecuteTask("quest3_tool_sorting_v1");
    if (!success) {
      commandPending.value = false;
      operationMessage.value = "发送任务启动命令失败";
      operationSuccess.value = false;
    } else {
      operationMessage.value = "正在启动任务...";
      operationSuccess.value = true;
    }
  } else {
    const success = websocketManager.sendStopTask();
    if (!success) {
      commandPending.value = false;
      operationMessage.value = "发送停止任务命令失败";
      operationSuccess.value = false;
    } else {
      operationMessage.value = "正在停止任务...";
      operationSuccess.value = true;
    }
  }
};

// 重置仿真
const resetSimulation = () => {
  if (!isConnected.value) {
    operationMessage.value = "请先连接到仿真服务器";
    operationSuccess.value = false;
    return;
  }

  commandPending.value = true;
  operationMessage.value = "正在重置仿真...";
  currentOperation.value = "resetting";

  const success = websocketManager.sendResetCommand();
  if (!success) {
    commandPending.value = false;
    operationMessage.value = "发送重置命令失败";
    operationSuccess.value = false;
  }
};

// 重置操作状态
const resetOperationStates = () => {
  currentOperation.value = "idle";
  isGrabbing.value = false;
  isPlacing.value = false;
  isMoving.value = false;
};

// 识别桌面工具
const detectTools = () => {
  if (!isConnected.value || !isSimulationRunning.value) {
    operationMessage.value = "请先连接服务器并启动仿真";
    operationSuccess.value = false;
    return;
  }

  currentOperation.value = "detecting";
  operationMessage.value = "正在识别桌面工具...";

  const state = websocketManager.getStatus().simulationState;
  const tools = extractDetectedToolsFromState(state);
  currentOperation.value = "idle";

  if (tools.length === 0) {
    websocketManager.requestState();
    operationMessage.value = "暂未获取到可识别对象，请稍后重试";
    operationSuccess.value = false;
    return;
  }

  detectedTools.value = tools;
  selectedToolIndex.value = 0;
  operationMessage.value = `成功识别到 ${tools.length} 个对象`;
  operationSuccess.value = true;
};

// 选择工具
const selectTool = (index) => {
  selectedToolIndex.value = index;
  operationMessage.value = `已选择: ${detectedTools.value[index].name}`;
  operationSuccess.value = true;
};

// 抓取工具
const grabTool = () => {
  if (!isConnected.value || !isSimulationRunning.value || selectedToolIndex.value === null) {
    operationMessage.value = "请先连接服务器并选择工具";
    operationSuccess.value = false;
    return;
  }

  const tool = detectedTools.value[selectedToolIndex.value];
  isGrabbing.value = true;
  currentOperation.value = "grabbing";
  operationMessage.value = `正在抓取 ${tool.name}...`;
  commandPending.value = true;

  // 计算抓取位置的关节角度（这里需要根据工具位置进行逆运动学计算）
  // 暂时使用预设的抓取姿态
  const grabPose = [0.0, -Math.PI/3, Math.PI/2, -Math.PI/3, -Math.PI/2, Math.PI/4]; // 抓取姿态

  const success = websocketManager.sendControlCommand(grabPose, {
    n_steps: 20,
    control_mode: 'position',
    gripper_command: {
      mode: "open_close",
      value: 1.0,
    },
  });

  if (!success) {
    resetOperationStates();
    commandPending.value = false;
    operationMessage.value = "发送抓取命令失败";
    operationSuccess.value = false;
  }
};

// 移动到预设位置
const moveToPosition = (position) => {
  if (!isConnected.value || !isSimulationRunning.value || !isToolGrabbed.value) {
    operationMessage.value = "请先连接服务器并抓取工具";
    operationSuccess.value = false;
    return;
  }

  isMoving.value = true;
  currentOperation.value = "moving";
  operationMessage.value = `正在移动到 ${position.name}...`;
  commandPending.value = true;

  // 根据预设位置计算关节角度（这里需要逆运动学计算）
  // 暂时使用预设的关节角度
  let targetPose;
  if (position.name === "工作区A") {
    targetPose = [Math.PI/6, -Math.PI/3, Math.PI/2, -Math.PI/3, -Math.PI/2, 0];
  } else if (position.name === "工作区B") {
    targetPose = [-Math.PI/6, -Math.PI/3, Math.PI/2, -Math.PI/3, -Math.PI/2, 0];
  } else if (position.name === "存放处") {
    targetPose = [0, -Math.PI/2, Math.PI/2, -Math.PI/2, -Math.PI/2, Math.PI/2];
  }

  const success = websocketManager.sendControlCommand(targetPose, {
    n_steps: 15,
    control_mode: 'position',
    gripper_command: {
      mode: "open_close",
      value: 1.0,
    },
  });

  if (!success) {
    resetOperationStates();
    commandPending.value = false;
    operationMessage.value = "发送移动命令失败";
    operationSuccess.value = false;
  }
};

// 放置工具
const placeTool = () => {
  if (!isConnected.value || !isSimulationRunning.value || !isToolGrabbed.value) {
    operationMessage.value = "请先连接服务器并抓取工具";
    operationSuccess.value = false;
    return;
  }

  isPlacing.value = true;
  currentOperation.value = "placing";
  operationMessage.value = "正在放置工具...";
  commandPending.value = true;

  // 释放姿态
  const releasePose = [0.0, -Math.PI/4, Math.PI/3, -Math.PI/4, -Math.PI/2, 0];

  const success = websocketManager.sendControlCommand(releasePose, {
    n_steps: 10,
    control_mode: 'position',
    gripper_command: {
      mode: "open_close",
      value: 0.0,
    },
  });

  if (!success) {
    resetOperationStates();
    commandPending.value = false;
    operationMessage.value = "发送放置命令失败";
    operationSuccess.value = false;
  }
};

// WebSocket 连接管理
const connectWebSocket = () => {
  if (isConnected.value) {
    operationMessage.value = "已经连接到服务器";
    operationSuccess.value = true;
    return;
  }

  operationMessage.value = "正在连接到仿真服务器...";
  websocketManager.connect();
};

const disconnectWebSocket = () => {
  if (!isConnected.value) {
    operationMessage.value = "未连接到服务器";
    operationSuccess.value = false;
    return;
  }

  websocketManager.disconnect();
  isSimulationRunning.value = false;
  commandPending.value = false;
  resetOperationStates();
  operationMessage.value = "已断开与仿真服务器的连接";
  operationSuccess.value = true;
};

// 组件生命周期
onMounted(() => {
  setupWebSocketListeners();

  // 获取初始连接状态
  const status = websocketManager.getStatus();
  isConnected.value = status.isConnected;
  connectionStatus.value = status.status;
  if (status.simulationState) {
    updateDetectedToolsFromState(status.simulationState);
    if (typeof status.simulationState?.task_state?.running === "boolean") {
      isSimulationRunning.value = Boolean(status.simulationState.task_state.running);
    }
  }
});

onBeforeUnmount(() => {
  // 清理事件监听器
  websocketManager.off('statusChange');
  websocketManager.off('connected');
  websocketManager.off('disconnected');
  websocketManager.off('controlResult');
  websocketManager.off('resetResult');
  websocketManager.off('stateUpdate');
  websocketManager.off('taskResult');
  websocketManager.off('error');
});
</script>

<style>
.control-panel {
  padding: 20px;
  /* box-sizing: border-box; */
  position: fixed;
  top: 20px;
  right: 20px; /* 取消注释并使用right而非left */
  width: 350px;
  max-width: 400px;
  background-color: rgba(245, 245, 247, 0.95);
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000; /* 恢复z-index确保面板正常显示在前面 */
  max-height: 90vh; /* 恢复最大高度限制 */
  overflow-y: auto; /* 恢复滚动条 */
}

.panel-title {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
  font-size: 18px;
  text-align: center;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.panel-section {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.panel-section:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.section-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
  font-weight: 500;
}

.section-subtitle {
  font-size: 12px;
  color: #909399;
  margin: 10px 0 5px 0;
  font-weight: 500;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

.control-button {
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background-color: #409eff;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-button:hover:not(:disabled) {
  background-color: #66b1ff;
}

.control-button:disabled {
  background-color: #c0c4cc;
  cursor: not-allowed;
  opacity: 0.7;
}

.control-button.secondary {
  background-color: #67c23a;
}

.control-button.secondary:hover:not(:disabled) {
  background-color: #85ce61;
}

.control-button.tertiary {
  background-color: #e6a23c;
  width: 100%;
}

.control-button.tertiary:hover:not(:disabled) {
  background-color: #ebb563;
}

.control-button.active {
  background-color: #f56c6c;
}

.control-button.active:hover {
  background-color: #f78989;
}

.btn-icon {
  margin-right: 6px;
}

.slider-container {
  display: flex;
  align-items: center;
  margin-top: 10px;
}

.slider-label {
  width: 70px;
  font-size: 14px;
  color: #606266;
}

.speed-slider {
  flex-grow: 1;
  margin: 0 10px;
}

.slider-value {
  width: 30px;
  font-size: 14px;
  color: #606266;
  text-align: right;
}

.tools-container {
  margin-top: 10px;
}

.tools-list {
  max-height: 150px;
  overflow-y: auto;
  background-color: #f5f5f5;
  border-radius: 6px;
}

.tool-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #e0e0e0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.tool-item:hover {
  background-color: #e8f4ff;
}

.tool-item.selected {
  background-color: #e8f4ff;
  border-left: 3px solid #409eff;
}

.tool-icon {
  font-size: 18px;
  margin-right: 10px;
  width: 24px;
  text-align: center;
}

.tool-info {
  flex-grow: 1;
}

.tool-name {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
}

.tool-position {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.preset-positions {
  margin-top: 10px;
}

.position-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.position-button {
  background-color: #f0f2f5;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.position-button:hover:not(:disabled) {
  background-color: #e6f2ff;
  border-color: #409eff;
  color: #409eff;
}

.position-button:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}

.status-container {
  background-color: #f8f9fa;
  border-radius: 6px;
  padding: 12px;
}

.status-item {
  display: flex;
  margin-bottom: 8px;
}

.status-item:last-child {
  margin-bottom: 0;
}

.status-label {
  width: 80px;
  font-size: 13px;
  color: #909399;
}

.status-value {
  flex-grow: 1;
  font-size: 13px;
  color: #303133;
  font-weight: 500;
}

.status-active {
  color: #67c23a;
}

.status-inactive {
  color: #909399;
}

.status-success {
  color: #67c23a;
}

.status-error {
  color: #f56c6c;
}

.status-pending {
  color: #e6a23c;
  display: flex;
  align-items: center;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #e6a23c;
  border-top: 2px solid transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
