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
        >
          <span class="btn-icon">{{ isSimulationRunning ? "⏹" : "▶" }}</span>
          {{ isSimulationRunning ? "停止仿真" : "开始仿真" }}
        </button>
        <button @click="resetSimulation" class="control-button secondary">
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
        :disabled="!isSimulationRunning"
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
            selectedToolIndex === null || !isSimulationRunning || isGrabbing
          "
        >
          <span class="btn-icon">✋</span>抓取工具
        </button>
        <button
          @click="placeTool"
          class="control-button secondary"
          :disabled="!isToolGrabbed || !isSimulationRunning || isPlacing"
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
            :disabled="!isSimulationRunning || isMoving"
          >
            {{ position.name }}
          </button>
        </div>
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
import { ref, computed } from "vue";

// 仿真状态
const isSimulationRunning = ref(false);
const simulationSpeed = ref(1.0);
const currentOperation = ref("idle");
const operationMessage = ref("");
const operationSuccess = ref(true);

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

// 开始/停止仿真
const toggleSimulation = () => {
  isSimulationRunning.value = !isSimulationRunning.value;
  if (isSimulationRunning.value) {
    operationMessage.value = "仿真已启动";
    operationSuccess.value = true;
  } else {
    operationMessage.value = "仿真已停止";
    operationSuccess.value = true;
    // 重置所有操作状态
    resetOperationStates();
  }
};

// 重置仿真
const resetSimulation = () => {
  if (isSimulationRunning.value) {
    isSimulationRunning.value = false;
  }

  // 重置所有状态
  resetOperationStates();
  detectedTools.value = [];
  selectedToolIndex.value = null;
  isToolGrabbed.value = false;
  operationMessage.value = "场景已重置";
  operationSuccess.value = true;
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
  if (!isSimulationRunning.value) return;

  currentOperation.value = "detecting";
  operationMessage.value = "";

  // 模拟识别过程
  setTimeout(() => {
    detectedTools.value = [
      {
        name: "螺丝刀",
        icon: "🔧",
        position: { x: 0.15, y: 0.12, z: 0.05 },
      },
      {
        name: "扳手",
        icon: "🔨",
        position: { x: -0.12, y: 0.08, z: 0.05 },
      },
      {
        name: "剪钳",
        icon: "✂️",
        position: { x: 0.05, y: 0.2, z: 0.05 },
      },
    ];

    currentOperation.value = "idle";
    operationMessage.value =
      "成功识别到 " + detectedTools.value.length + " 个工具";
    operationSuccess.value = true;
  }, 1500);
};

// 选择工具
const selectTool = (index) => {
  selectedToolIndex.value = index;
  operationMessage.value = `已选择: ${detectedTools.value[index].name}`;
  operationSuccess.value = true;
};

// 抓取工具
const grabTool = () => {
  if (!isSimulationRunning.value || selectedToolIndex.value === null) return;

  isGrabbing.value = true;
  currentOperation.value = "grabbing";
  operationMessage.value = "";

  // 模拟抓取过程
  setTimeout(() => {
    isToolGrabbed.value = true;
    isGrabbing.value = false;
    currentOperation.value = "idle";
    operationMessage.value = `成功抓取: ${
      detectedTools.value[selectedToolIndex.value].name
    }`;
    operationSuccess.value = true;
  }, 2000);
};

// 移动到预设位置
const moveToPosition = (position) => {
  if (!isSimulationRunning.value || !isToolGrabbed.value) return;

  isMoving.value = true;
  currentOperation.value = "moving";
  operationMessage.value = "";

  // 模拟移动过程
  setTimeout(() => {
    isMoving.value = false;
    currentOperation.value = "idle";
    operationMessage.value = `已移动到: ${position.name}`;
    operationSuccess.value = true;
  }, 1500);
};

// 放置工具
const placeTool = () => {
  if (!isSimulationRunning.value || !isToolGrabbed.value) return;

  isPlacing.value = true;
  currentOperation.value = "placing";
  operationMessage.value = "";

  // 模拟放置过程
  setTimeout(() => {
    isToolGrabbed.value = false;
    isPlacing.value = false;
    currentOperation.value = "idle";
    operationMessage.value = "工具已放置";
    operationSuccess.value = true;
    // 重置选择
    selectedToolIndex.value = null;
  }, 1500);
};
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
</style>
