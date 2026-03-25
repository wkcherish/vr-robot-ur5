<template>
  <div class="camera-panel">
    <h3 class="panel-title">相机状态信息</h3>

    <!-- 相机图像显示区域 -->
    <div class="panel-section" v-if="isConnected && isStreaming">
      <h4 class="section-title">实时图像</h4>
      <div class="camera-image-container">
        <div class="image-wrapper" :class="{ loading: isLoadingImage }">
          <img
            v-if="currentImageUrl"
            :src="currentImageUrl"
            :alt="`相机图像 - ${imageTimestamp}`"
            class="camera-image"
            @load="onImageLoad"
            @error="onImageError"
            :key="imageTimestamp"
          />
          <div v-else-if="isLoadingImage" class="loading-placeholder">
            <div class="loading-spinner"></div>
            <span>加载图像中...</span>
          </div>
          <div v-else class="error-placeholder">
            <span class="error-icon">📷</span>
            <span>无法加载图像</span>
          </div>
        </div>
        <div class="image-info">
          <small class="image-timestamp">
            {{ imageTimestamp ? new Date(imageTimestamp * 1000).toLocaleTimeString() : '无时间戳' }}
          </small>
          <small class="image-fps" :class="{ 'low-fps': actualFps < 10 }">
            {{ actualFps.toFixed(1) }} FPS
          </small>
        </div>
      </div>
    </div>

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
          :disabled="isConnecting"
        >
          {{ isConnecting ? "连接中..." : (isConnected ? "断开连接" : "连接相机") }}
        </button>
      </div>
      <div v-if="connectionError" class="error-message">
        <span class="error-icon">⚠️</span>
        {{ connectionError }}
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
          <span class="label">目标帧率:</span>
          <span class="value">{{ framerate }} <small>fps</small></span>
        </div>
        <div class="data-item">
          <span class="label">实际帧率:</span>
          <span class="value" :class="{ 'low-fps': actualFps < targetFps * 0.5 }">
            {{ actualFps.toFixed(1) }} <small>fps</small>
          </span>
        </div>
        <div class="data-item">
          <span class="label">平均延迟:</span>
          <span class="value" :class="{ 'high-latency': latency > 200 }">
            {{ latency.toFixed(0) }} <small>ms</small>
          </span>
        </div>
        <div class="data-item">
          <span class="label">图像质量:</span>
          <span class="value">{{ imageQuality }}%</span>
        </div>
        <div class="data-item">
          <span class="label">传输模式:</span>
          <span class="value">{{ useWebSocket ? 'WebSocket' : 'HTTP' }}</span>
        </div>
      </div>
    </div>

    <div class="panel-section" v-if="isConnected">
      <h4 class="section-title">控制选项</h4>
      <div class="control-grid">
        <button @click="captureImage" class="camera-button secondary" :disabled="isCapturing">
          <span class="btn-icon">{{ isCapturing ? '⏳' : '📷' }}</span>
          {{ isCapturing ? '拍照中...' : '拍照' }}
        </button>
        <button @click="toggleStream" class="camera-button tertiary" :disabled="!isConnected">
          <span class="btn-icon">{{ isStreaming ? "⏹" : "▶" }}</span>
          {{ isStreaming ? "停止视频流" : "开始视频流" }}
        </button>
      </div>

      <!-- 高级设置 -->
      <div class="advanced-settings">
        <h5 class="subsection-title">高级设置</h5>
        <div class="setting-item">
          <label for="resolution-select">分辨率:</label>
          <select
            id="resolution-select"
            v-model="selectedResolution"
            @change="updateResolution"
            class="setting-select"
          >
            <option value="320x240">320x240</option>
            <option value="640x480">640x480</option>
            <option value="800x600">800x600</option>
            <option value="1280x720">1280x720</option>
          </select>
        </div>
        <div class="setting-item">
          <label for="fps-select">目标帧率:</label>
          <select
            id="fps-select"
            v-model="selectedFps"
            @change="updateFrameRate"
            class="setting-select"
          >
            <option value="5">5 FPS</option>
            <option value="10">10 FPS</option>
            <option value="15">15 FPS</option>
            <option value="20">20 FPS</option>
            <option value="30">30 FPS</option>
          </select>
        </div>
        <div class="setting-item">
          <label for="quality-slider">图像质量:</label>
          <div class="quality-control">
            <input
              type="range"
              id="quality-slider"
              v-model="imageQuality"
              min="10"
              max="100"
              step="5"
              @input="updateImageQuality"
              class="quality-slider"
            />
            <span class="quality-value">{{ imageQuality }}%</span>
          </div>
        </div>
        <div class="setting-item">
          <label for="transport-select">传输模式:</label>
          <select
            id="transport-select"
            v-model="useWebSocket"
            @change="updateTransportMode"
            class="setting-select"
          >
            <option :value="false">HTTP</option>
            <option :value="true">WebSocket</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 状态统计 -->
    <div class="panel-section" v-if="isConnected">
      <h4 class="section-title">统计信息</h4>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-label">总帧数:</span>
          <span class="stat-value">{{ totalFrames }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">成功率:</span>
          <span class="stat-value">{{ successRate.toFixed(1) }}%</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均大小:</span>
          <span class="stat-value">{{ averageImageSize }} KB</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">最后更新:</span>
          <span class="stat-value">{{ lastUpdateAgo }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from "vue";
import axios from "axios";

// 相机状态数据
const isConnected = ref(false);
const isConnecting = ref(false);
const isStreaming = ref(false);
const isLoadingImage = ref(false);
const isCapturing = ref(false);
const connectionError = ref(null);

// 图像相关状态
const currentImageUrl = ref(null);
const imageTimestamp = ref(null);
const lastImageUpdate = ref(0);
const imageLoadTimes = ref([]); // 记录最近的图像加载时间
const imageErrors = ref(0);
const totalFrames = ref(0);
const successfulFrames = ref(0);

// 相机参数
const selectedResolution = ref("640x480");
const selectedFps = ref(15);
const imageQuality = ref(80);
const useWebSocket = ref(false); // 默认使用HTTP

// 性能监控
const frameTimestamps = ref([]); // 记录帧时间戳
const latencyMeasurements = ref([]); // 记录延迟测量
const imageSizes = ref([]); // 记录图像大小

// 计算属性
const resolution = computed(() => selectedResolution.value);
const framerate = computed(() => selectedFps.value);
const targetFps = computed(() => parseInt(selectedFps.value));

// 实际帧率计算
const actualFps = computed(() => {
  const now = Date.now();
  const recentFrames = frameTimestamps.value.filter(ts => now - ts < 5000); // 最近5秒的帧

  if (recentFrames.length < 2) return 0;

  const timeSpan = (recentFrames[recentFrames.length - 1] - recentFrames[0]) / 1000;
  return recentFrames.length / timeSpan;
});

// 平均延迟计算
const latency = computed(() => {
  if (latencyMeasurements.value.length === 0) return 0;
  const sum = latencyMeasurements.value.reduce((a, b) => a + b, 0);
  return sum / latencyMeasurements.value.length;
});

// 成功率计算
const successRate = computed(() => {
  if (totalFrames.value === 0) return 100;
  return (successfulFrames.value / totalFrames.value) * 100;
});

// 平均图像大小
const averageImageSize = computed(() => {
  if (imageSizes.value.length === 0) return 0;
  const sum = imageSizes.value.reduce((a, b) => a + b, 0);
  return (sum / imageSizes.value.length / 1024).toFixed(1); // KB
});

// 最后更新时间
const lastUpdateAgo = computed(() => {
  if (!lastImageUpdate.value) return '从未';
  const seconds = Math.floor((Date.now() - lastImageUpdate.value) / 1000);
  if (seconds < 60) return `${seconds}秒前`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}分钟前`;
});

// 定时器和控制器
let streamInterval = null;
let websocketConnection = null;

// 相机配置
const CAMERA_CONFIG = {
  baseUrl: 'http://localhost:8000',
  endpoints: {
    image: '/sim/camera.jpg',
    base64: '/sim/camera.json'
  }
};

// 连接/断开相机
const toggleConnection = async () => {
  if (isConnecting.value) return;

  isConnecting.value = true;
  connectionError.value = null;

  try {
    if (isConnected.value) {
      await disconnectCamera();
    } else {
      await connectCamera();
    }
  } catch (error) {
    connectionError.value = error.message || '连接失败';
    console.error('相机连接错误:', error);
  } finally {
    isConnecting.value = false;
  }
};

// 连接相机
const connectCamera = async () => {
  try {
    // 测试连接
    const response = await axios.get(`${CAMERA_CONFIG.baseUrl}/health/`, { timeout: 5000 });

    if (response.data.status === 'healthy') {
      isConnected.value = true;
      connectionError.value = null;
      console.log('相机连接成功');

      // 如果之前在流式传输，自动恢复
      if (isStreaming.value) {
        startStreaming();
      }
    } else {
      throw new Error('相机服务不可用');
    }
  } catch (error) {
    throw new Error(`连接相机失败: ${error.message}`);
  }
};

// 断开相机
const disconnectCamera = async () => {
  stopStreaming();
  closeWebSocketConnection();
  isConnected.value = false;
  isStreaming.value = false;
  currentImageUrl.value = null;
  imageTimestamp.value = null;
  connectionError.value = null;
  console.log('相机已断开');
};

// 开始/停止视频流
const toggleStream = () => {
  if (!isConnected.value) return;

  if (isStreaming.value) {
    stopStreaming();
  } else {
    startStreaming();
  }
};

// 开始流式传输
const startStreaming = () => {
  if (!isConnected.value) return;

  isStreaming.value = true;
  imageErrors.value = 0;

  if (useWebSocket.value) {
    startWebSocketStreaming();
  } else {
    startHttpStreaming();
  }

  console.log(`开始${useWebSocket.value ? 'WebSocket' : 'HTTP'}视频流`);
};

// 停止流式传输
const stopStreaming = () => {
  isStreaming.value = false;
  isLoadingImage.value = false;

  if (streamInterval) {
    clearInterval(streamInterval);
    streamInterval = null;
  }

  closeWebSocketConnection();

  console.log('停止视频流');
};

// HTTP流式传输
const startHttpStreaming = () => {
  const interval = 1000 / targetFps.value; // 根据目标帧率计算间隔

  streamInterval = setInterval(async () => {
    if (!isStreaming.value || !isConnected.value) return;

    try {
      await fetchCameraImage();
    } catch (error) {
      console.warn('获取图像失败:', error);
      handleImageError();
    }
  }, interval);

  // 立即获取第一帧
  fetchCameraImage();
};

// WebSocket流式传输
const startWebSocketStreaming = () => {
  // WebSocket流式传输实现（如果后端支持）
  console.log('WebSocket流式传输暂未实现，使用HTTP模式');
  useWebSocket.value = false;
  startHttpStreaming();
};

// 获取相机图像
const fetchCameraImage = async () => {
  if (!isConnected.value || !isStreaming.value) return;

  const startTime = Date.now();
  isLoadingImage.value = true;

  try {
    totalFrames.value++;

    // 构建请求URL
    const params = new URLSearchParams({
      width: resolution.value.split('x')[0],
      height: resolution.value.split('x')[1],
      quality: imageQuality.value
    });

    const imageUrl = `${CAMERA_CONFIG.baseUrl}${CAMERA_CONFIG.endpoints.image}?${params}`;

    // 使用缓存破坏参数确保获取最新图像
    const finalUrl = `${imageUrl}&t=${Date.now()}`;

    // 获取图像
    const response = await axios.get(finalUrl, {
      responseType: 'blob',
      timeout: 5000,
      headers: {
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      }
    });

    if (response.status === 200) {
      // 创建blob URL
      const blob = new Blob([response.data], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);

      // 记录性能数据
      const loadTime = Date.now() - startTime;
      latencyMeasurements.value.push(loadTime);
      if (latencyMeasurements.value.length > 50) {
        latencyMeasurements.value.shift(); // 保持最近50次测量
      }

      imageSizes.value.push(response.data.size);
      if (imageSizes.value.length > 20) {
        imageSizes.value.shift();
      }

      // 更新图像
      currentImageUrl.value = url;
      imageTimestamp.value = Date.now() / 1000;
      lastImageUpdate.value = Date.now();

      // 记录帧时间戳
      frameTimestamps.value.push(Date.now());
      if (frameTimestamps.value.length > 100) {
        frameTimestamps.value.shift();
      }

      successfulFrames.value++;
      imageErrors.value = 0;

      // 清理旧的blob URL
      setTimeout(() => {
        if (currentImageUrl.value === url) {
          URL.revokeObjectURL(url);
        }
      }, 1000);
    } else {
      throw new Error(`HTTP ${response.status}`);
    }

  } catch (error) {
    console.error('获取相机图像失败:', error);
    handleImageError();
  } finally {
    isLoadingImage.value = false;
  }
};

// 处理图像错误
const handleImageError = () => {
  imageErrors.value++;
  totalFrames.value++;

  // 如果连续错误太多，停止流式传输
  if (imageErrors.value >= 5) {
    console.error('连续图像获取失败，停止流式传输');
    stopStreaming();
    connectionError.value = '图像获取失败，请检查相机服务';
  }
};

// 拍照功能
const captureImage = async () => {
  if (!isConnected.value || isCapturing.value) return;

  isCapturing.value = true;

  try {
    const params = new URLSearchParams({
      width: '1280',
      height: '720',
      quality: '95'
    });

    const response = await axios.get(
      `${CAMERA_CONFIG.baseUrl}${CAMERA_CONFIG.endpoints.image}?${params}`,
      {
        responseType: 'blob',
        timeout: 10000
      }
    );

    if (response.status === 200) {
      // 创建下载链接
      const blob = new Blob([response.data], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `camera_capture_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.jpg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      console.log('拍照成功，已下载到本地');
    } else {
      throw new Error(`拍照失败: HTTP ${response.status}`);
    }

  } catch (error) {
    console.error('拍照失败:', error);
    connectionError.value = '拍照失败，请重试';
  } finally {
    isCapturing.value = false;
  }
};

// 图像加载完成处理
const onImageLoad = () => {
  // 图像加载成功
  console.log('图像加载成功');
};

// 图像加载错误处理
const onImageError = () => {
  console.error('图像加载失败');
  handleImageError();
};

// 更新分辨率
const updateResolution = () => {
  if (isStreaming.value) {
    // 如果正在流式传输，需要重启
    stopStreaming();
    setTimeout(() => startStreaming(), 100);
  }
};

// 更新帧率
const updateFrameRate = () => {
  if (isStreaming.value && !useWebSocket.value) {
    // 重新启动HTTP流以应用新帧率
    stopStreaming();
    setTimeout(() => startStreaming(), 100);
  }
};

// 更新图像质量
const updateImageQuality = () => {
  // 质量变化会在下次获取图像时生效
  console.log(`图像质量已更新为: ${imageQuality.value}%`);
};

// 更新传输模式
const updateTransportMode = () => {
  if (isStreaming.value) {
    // 如果正在流式传输，需要切换模式
    stopStreaming();
    setTimeout(() => startStreaming(), 100);
  }
};

// 关闭WebSocket连接
const closeWebSocketConnection = () => {
  if (websocketConnection) {
    websocketConnection.close();
    websocketConnection = null;
  }
};

// 清理资源
const cleanup = () => {
  stopStreaming();
  closeWebSocketConnection();

  // 清理blob URLs
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value);
    currentImageUrl.value = null;
  }
};

// 监听连接状态变化
watch(isConnected, (newValue) => {
  if (!newValue) {
    stopStreaming();
  }
});

// 生命周期钩子
onMounted(() => {
  console.log('相机组件已挂载');
});

onBeforeUnmount(() => {
  cleanup();
  console.log('相机组件已卸载');
});
</script>

<style>
.camera-panel {
  padding: 20px;
  box-sizing: border-box;
  position: fixed;
  bottom: 150px;
  left: 20px;
  width: 30%; /* 与 position-panel 一致的百分比宽度 */
  max-width: 400px;
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
  max-height: 80vh;
  overflow-y: auto;
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

.subsection-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: 500;
}

/* 相机图像显示区域 */
.camera-image-container {
  width: 100%;
}

.image-wrapper {
  position: relative;
  width: 100%;
  background-color: #f8f9fa;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e0e0e0;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-image {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
}

.loading-placeholder,
.error-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: #909399;
  text-align: center;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e0e0;
  border-top: 3px solid #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.image-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 4px 8px;
  background-color: #f5f5f5;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
}

.image-timestamp {
  flex: 1;
}

.image-fps {
  font-weight: 500;
}

.image-fps.low-fps {
  color: #e6a23c;
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

.error-message {
  margin-top: 8px;
  padding: 8px 12px;
  background-color: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
  font-size: 13px;
  display: flex;
  align-items: center;
}

.error-icon {
  margin-right: 6px;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 6px;
}

.data-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f5f5f5;
  padding: 8px 12px;
  border-radius: 6px;
}

.data-item .value.low-fps {
  color: #e6a23c;
}

.data-item .value.high-latency {
  color: #f56c6c;
}

.label {
  font-weight: bold;
  color: #555;
  font-size: 13px;
}

.value {
  font-family: monospace;
  font-size: 14px;
  color: #2c3e50;
}

.value.low-fps {
  color: #e6a23c !important;
}

.value.high-latency {
  color: #f56c6c !important;
}

.value small {
  color: #7f8c8d;
  font-size: 11px;
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
  font-size: 13px;
  font-weight: 500; /* 与控制面板按钮一致 */
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.camera-button:hover:not(:disabled) {
  background-color: #5a82ad; /* 稍微亮一点的悬停颜色 */
}

.camera-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.camera-button.secondary {
  background-color: #67c23a; /* 与"发送"按钮颜色一致(绿色) */
}

.camera-button.secondary:hover:not(:disabled) {
  background-color: #85ce61; /* 与控制面板绿色按钮悬停颜色一致 */
}

/* 添加新的按钮类型 */
.camera-button.tertiary {
  background-color: #e6a23c; /* 与"测试"按钮颜色一致(黄色) */
}

.camera-button.tertiary:hover:not(:disabled) {
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

.connected-btn:hover:not(:disabled) {
  background-color: #f78989 !important;
}

.disconnected-btn:hover:not(:disabled) {
  background-color: #66b1ff !important;
}

.btn-icon {
  margin-right: 6px;
  font-size: 14px;
}

/* 高级设置样式 */
.advanced-settings {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-item label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
  flex: 1;
}

.setting-select {
  padding: 4px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 12px;
  background-color: white;
  cursor: pointer;
  min-width: 80px;
}

.setting-select:focus {
  outline: none;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.quality-control {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  max-width: 120px;
}

.quality-slider {
  flex: 1;
  height: 4px;
  background: #dcdfe6;
  border-radius: 2px;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.quality-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #409eff;
  cursor: pointer;
}

.quality-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #409eff;
  cursor: pointer;
  border: none;
}

.quality-value {
  font-size: 12px;
  color: #666;
  font-family: monospace;
  min-width: 35px;
  text-align: right;
}

/* 统计信息样式 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f8f9fa;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.stat-label {
  color: #909399;
  font-weight: 500;
}

.stat-value {
  color: #303133;
  font-family: monospace;
  font-weight: 500;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .camera-panel {
    width: 35%;
    max-width: 380px;
  }

  .image-wrapper {
    min-height: 180px;
  }
}

@media (max-width: 768px) {
  .camera-panel {
    width: 90%;
    max-width: none;
    left: 5%;
    right: 5%;
  }

  .control-grid {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .setting-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .quality-control {
    width: 100%;
    max-width: none;
  }
}
</style>
