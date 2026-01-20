<template>
  <div class="camera-panel">
    <h3 class="panel-title">相机状态信息</h3>

    <div class="panel-section">
      <h4 class="section-title">连接状态</h4>
      <div class="status-container">
        <div class="status-indicator" :class="{ connected: isConnected }">
          <div class="status-dot" :class="{ pulse: isConnected }"></div>
          <span class="status-text">{{
            isConnected ? "已连接" : "未连接"
          }}</span>
        </div>
        <!-- 使用与机器人控制面板相同的按钮颜色样式 -->
        <button
          @click="toggleConnection"
          class="camera-button"
          :class="{
            'connected-btn': isConnected,
            'disconnected-btn': !isConnected,
          }"
        >
          {{ isConnected ? "断开连接" : "连接相机" }}
        </button>
      </div>
    </div>

    <div class="panel-section">
      <h4 class="section-title">相机参数</h4>
      <div class="data-grid">
        <div class="data-item">
          <span class="label">分辨率:</span>
          <span class="value">{{ resolution }}</span>
        </div>
        <div class="data-item">
          <span class="label">帧率:</span>
          <span class="value">{{ framerate }} <small>fps</small></span>
        </div>
        <div class="data-item">
          <span class="label">延迟:</span>
          <span class="value">{{ latency }} <small>ms</small></span>
        </div>
      </div>
    </div>

    <div class="panel-section" v-if="isConnected">
      <h4 class="section-title">控制选项</h4>
      <div class="control-grid">
        <button @click="captureImage" class="camera-button secondary">
          <span class="btn-icon">📷</span>拍照
        </button>
        <button @click="toggleStream" class="camera-button tertiary">
          <span class="btn-icon">{{ isStreaming ? "⏹" : "▶" }}</span>
          {{ isStreaming ? "停止视频流" : "开始视频流" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

// 相机状态数据
const isConnected = ref(false);
const isStreaming = ref(false);
const resolution = ref("1280x720");
const framerate = ref(30);
const latency = ref(45);

// 连接/断开相机
const toggleConnection = () => {
  isConnected.value = !isConnected.value;
  if (!isConnected.value) {
    isStreaming.value = false;
  }
};

// 开始/停止视频流
const toggleStream = () => {
  if (isConnected.value) {
    isStreaming.value = !isStreaming.value;
  }
};

// 拍照功能
const captureImage = () => {
  if (isConnected.value) {
    console.log("拍照成功");
    // 这里可以添加实际拍照逻辑
  }
};
</script>

<style>
.camera-panel {
  padding: 20px;
  box-sizing: border-box;
  position: fixed;
  bottom: 150px;
  left: 20px;
  width: 30%; /* 与 position-panel 一致的百分比宽度 */
  max-width: 380px;
  background-color: rgba(
    245,
    245,
    247,
    0.95
  ); /* 调整为与控制面板一致的背景色 */
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
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
  padding: 0 0 15px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06); /* 添加边框与控制面板一致 */
}

.panel-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-title {
  font-size: 14px;
  color: #606266; /* 与控制面板一致 */
  margin-bottom: 12px;
  font-weight: 500;
}

.status-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.status-indicator {
  display: flex;
  align-items: center;
}

.status-dot {
  width: 10px;
  height: 10px;
  background-color: #f56c6c;
  border-radius: 50%;
  margin-right: 8px;
}

.status-dot.pulse {
  background-color: #67c23a;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}

.status-text {
  font-size: 14px;
}

.status-indicator.connected .status-text {
  color: #67c23a;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 8px;
}

.data-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f5f5f5;
  padding: 8px 12px;
  border-radius: 6px;
}

.label {
  font-weight: bold;
  color: #555;
  font-size: 14px;
}

.value {
  font-family: monospace;
  font-size: 15px;
  color: #2c3e50;
}

.value small {
  color: #7f8c8d;
  font-size: 12px;
  margin-left: 2px;
}

.control-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 8px;
}

.camera-button {
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background-color: #48719d; /* 与控制面板标题栏颜色一致 */
  color: white;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
  font-weight: 500; /* 与控制面板按钮一致 */
}

.camera-button:hover {
  background-color: #5a82ad; /* 稍微亮一点的悬停颜色 */
}

.camera-button.secondary {
  background-color: #67c23a; /* 与"发送"按钮颜色一致(绿色) */
}

.camera-button.secondary:hover {
  background-color: #85ce61; /* 与控制面板绿色按钮悬停颜色一致 */
}

/* 添加新的按钮类型 */
.camera-button.tertiary {
  background-color: #e6a23c; /* 与"测试"按钮颜色一致(黄色) */
}

.camera-button.tertiary:hover {
  background-color: #ebb563; /* 与控制面板黄色按钮悬停颜色一致 */
}

.camera-button.connected-btn {
  background-color: #67c23a; /* 连接状态按钮颜色 */
}

.camera-button.disconnected-btn {
  background-color: #f56c6c; /* 未连接状态按钮颜色 */
}

.connected-btn {
  background-color: #f56c6c !important; /* 红色，与机器人控制面板一致 */
}

.disconnected-btn {
  background-color: #409eff !important; /* 蓝色，与机器人控制面板一致 */
}

.connected-btn:hover {
  background-color: #f78989 !important;
}

.disconnected-btn:hover {
  background-color: #66b1ff !important;
}

.btn-icon {
  margin-right: 6px;
}
</style>
