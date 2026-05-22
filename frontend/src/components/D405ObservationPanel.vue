<template>
  <div class="d405-observation-panel">
    <div class="d405-panel-header">
      <div>
        <h4>D405 RGB-D</h4>
        <div class="d405-source-label">训练主视觉源</div>
      </div>
      <button class="d405-close-button" @click="emit('close')">关闭</button>
    </div>

    <div class="d405-status-grid">
      <div class="d405-status-item">
        <span>帧号</span>
        <strong>{{ frameId }}</strong>
      </div>
      <div class="d405-status-item">
        <span>时间戳</span>
        <strong>{{ timestampText }}</strong>
      </div>
      <div class="d405-status-item">
        <span>采集</span>
        <strong :class="statusClass(captureOk)">{{ captureOk ? "OK" : "异常" }}</strong>
      </div>
      <div class="d405-status-item">
        <span>对齐</span>
        <strong :class="statusClass(frameAligned)">{{ frameAligned ? "OK" : "异常" }}</strong>
      </div>
      <div class="d405-status-item">
        <span>RGB</span>
        <strong :class="statusClass(rgbValid)">{{ rgbValid ? "有效" : "无效" }}</strong>
      </div>
      <div class="d405-status-item">
        <span>Depth</span>
        <strong :class="statusClass(depthValid)">{{ depthValid ? "有效" : "无效" }}</strong>
      </div>
      <div class="d405-status-item">
        <span>帧率</span>
        <strong>{{ fpsText }}</strong>
      </div>
    </div>

    <div class="d405-actions">
      <button class="d405-action-button" :disabled="loading" @click="refreshObservation">
        {{ loading ? "刷新中..." : "刷新画面" }}
      </button>
      <span class="d405-mini-status" :class="statusClass(captureOk && frameAligned)">
        {{ captureOk && frameAligned ? "可录制" : "待检查" }}
      </span>
      <label class="d405-auto-refresh">
        <input type="checkbox" v-model="autoRefresh" />
        自动刷新
      </label>
    </div>

    <div class="d405-preview-grid">
      <div class="d405-preview">
        <div class="d405-preview-title">RGB</div>
        <canvas ref="rgbCanvas"></canvas>
      </div>
      <div class="d405-preview">
        <div class="d405-preview-title">Depth 伪彩</div>
        <canvas ref="depthCanvas"></canvas>
      </div>
    </div>

    <div class="d405-note">{{ statusText }}</div>
    <div class="d405-error" v-if="lastError">{{ lastError }}</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

import { get } from "../utils/network.js";

const props = defineProps({
  snapshot: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["close"]);

const observation = ref(null);
const loading = ref(false);
const autoRefresh = ref(false);
const refreshTimer = ref(null);
const rgbCanvas = ref(null);
const depthCanvas = ref(null);
const lastError = ref("");

const latestSnapshot = computed(() => {
  return observation.value || props.snapshot?.camera_observation || props.snapshot?.camera || null;
});

const frameId = computed(() => {
  const snapshot = latestSnapshot.value;
  return String(snapshot?.d405_frame_id || snapshot?.frame_id || "-");
});

const timestampText = computed(() => {
  const raw = Number(latestSnapshot.value?.timestamp);
  if (!Number.isFinite(raw)) return "-";
  return new Date(raw * 1000).toLocaleTimeString();
});

const captureOk = computed(() => Boolean(latestSnapshot.value?.camera_capture_ok));
const frameAligned = computed(() => Boolean(latestSnapshot.value?.frame_aligned));
const rgbValid = computed(() => Boolean(latestSnapshot.value?.rgb_valid ?? latestSnapshot.value?.rgb?.valid));
const depthValid = computed(() => Boolean(latestSnapshot.value?.depth_valid ?? latestSnapshot.value?.depth?.valid));
const fpsText = computed(() => {
  const rgbFps = Number(latestSnapshot.value?.rgb?.fps);
  const depthFps = Number(latestSnapshot.value?.depth?.fps);
  if (!Number.isFinite(rgbFps) && !Number.isFinite(depthFps)) return "-";
  if (Number.isFinite(rgbFps) && Number.isFinite(depthFps)) {
    return `${rgbFps.toFixed(0)} / ${depthFps.toFixed(0)} Hz`;
  }
  return `${(rgbFps || depthFps).toFixed(0)} Hz`;
});

const statusText = computed(() => {
  const snapshot = latestSnapshot.value;
  if (!snapshot) return "尚未收到 D405 观测。";
  const device = String(snapshot?.camera_device || snapshot?.device || "-");
  const rgbName = String(snapshot?.rgb?.camera_name || "-");
  const depthName = String(snapshot?.depth?.camera_name || "-");
  const viewStatus = String(snapshot?.camera_view_status || "unchecked");
  return `当前源：${device}；RGB：${rgbName}；Depth：${depthName}；视野：${viewStatus}`;
});

function statusClass(ok) {
  return ok ? "status-ok" : "status-error";
}

function decodeBase64Bytes(base64) {
  if (!base64 || typeof window === "undefined" || typeof window.atob !== "function") {
    return null;
  }
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let idx = 0; idx < binary.length; idx += 1) {
    bytes[idx] = binary.charCodeAt(idx);
  }
  return bytes;
}

function resizeCanvas(canvas, width, height) {
  if (!canvas) return false;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  return true;
}

function drawRgbFrame(canvas, frameData, stream) {
  const width = Number(stream?.width);
  const height = Number(stream?.height);
  const bytes = decodeBase64Bytes(frameData?.data_base64);
  if (!canvas || !Number.isFinite(width) || !Number.isFinite(height) || !bytes) return;
  if (bytes.length < width * height * 3) return;
  resizeCanvas(canvas, width, height);
  const context = canvas.getContext("2d");
  if (!context) return;
  const image = context.createImageData(width, height);
  for (let src = 0, dst = 0; dst < image.data.length; src += 3, dst += 4) {
    image.data[dst] = bytes[src];
    image.data[dst + 1] = bytes[src + 1];
    image.data[dst + 2] = bytes[src + 2];
    image.data[dst + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function drawDepthFrame(canvas, frameData, stream) {
  const width = Number(stream?.width);
  const height = Number(stream?.height);
  const bytes = decodeBase64Bytes(frameData?.data_base64);
  if (!canvas || !Number.isFinite(width) || !Number.isFinite(height) || !bytes) return;
  if (bytes.length < width * height * 2) return;
  resizeCanvas(canvas, width, height);
  const context = canvas.getContext("2d");
  if (!context) return;

  const depth = new Uint16Array(width * height);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let maxDepth = 0;
  for (let idx = 0; idx < depth.length; idx += 1) {
    const value = view.getUint16(idx * 2, true);
    depth[idx] = value;
    if (value > maxDepth) maxDepth = value;
  }

  const scale = Math.max(1, Math.min(maxDepth || 1, 3000));
  const image = context.createImageData(width, height);
  for (let idx = 0, dst = 0; idx < depth.length; idx += 1, dst += 4) {
    const value = depth[idx];
    const normalized = value <= 0 ? 0 : Math.max(0, Math.min(1, 1 - value / scale));
    image.data[dst] = Math.round(255 * normalized);
    image.data[dst + 1] = Math.round(180 * normalized + 40);
    image.data[dst + 2] = Math.round(255 * (1 - normalized));
    image.data[dst + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

async function applyObservation(data) {
  if (!data || typeof data !== "object") return;
  observation.value = data;
  lastError.value = String(data.last_error || data.validation_summary?.last_error || "");
  await nextTick();
  if (data.rgb_data) {
    drawRgbFrame(rgbCanvas.value, data.rgb_data, data.rgb);
  }
  if (data.depth_data) {
    drawDepthFrame(depthCanvas.value, data.depth_data, data.depth);
  }
}

async function refreshObservation() {
  if (loading.value) return;
  loading.value = true;
  try {
    const response = await get("/sim/observation/", {
      params: { include_data: true },
      timeout: 5000,
    });
    await applyObservation(response?.data);
  } catch (error) {
    lastError.value = `D405 画面刷新失败: ${error?.message || error}`;
  } finally {
    loading.value = false;
  }
}

function startAutoRefresh() {
  if (refreshTimer.value) return;
  refreshTimer.value = window.setInterval(() => {
    if (autoRefresh.value) {
      refreshObservation();
    }
  }, 1000);
}

function stopAutoRefresh() {
  if (!refreshTimer.value) return;
  window.clearInterval(refreshTimer.value);
  refreshTimer.value = null;
}

watch(autoRefresh, (enabled) => {
  if (enabled) {
    startAutoRefresh();
    refreshObservation();
    return;
  }
  stopAutoRefresh();
});

watch(
  () => props.snapshot,
  (snapshot) => {
    const last = snapshot?.camera_observation?.last_error || snapshot?.camera?.last_error || "";
    if (last) {
      lastError.value = String(last);
    }
  },
  { immediate: true }
);

refreshObservation();

onBeforeUnmount(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.d405-observation-panel {
  position: absolute;
  right: 16px;
  bottom: 80px;
  width: min(360px, calc(100vw - 32px));
  max-height: calc(100vh - 112px);
  overflow: auto;
  z-index: 11;
  border: 1px solid rgba(98, 139, 168, 0.35);
  border-radius: 8px;
  background: rgba(14, 23, 32, 0.90);
  color: #ecf6fc;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.35);
  padding: 10px;
  backdrop-filter: blur(5px);
}

.d405-panel-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(119, 156, 186, 0.22);
}

.d405-panel-header h4 {
  margin: 0;
  font-size: 14px;
  line-height: 1.3;
}

.d405-source-label {
  margin-top: 2px;
  color: #a9cee8;
  font-size: 11px;
}

.d405-close-button,
.d405-action-button {
  border: 1px solid rgba(119, 156, 186, 0.55);
  border-radius: 6px;
  background: rgba(40, 68, 96, 0.9);
  color: #d7ebff;
  cursor: pointer;
  font-size: 12px;
  padding: 5px 9px;
}

.d405-close-button:hover,
.d405-action-button:hover {
  background: rgba(52, 84, 116, 0.95);
}

.d405-action-button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.d405-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.d405-status-item {
  min-width: 0;
  padding: 7px;
  border-radius: 6px;
  background: rgba(27, 42, 55, 0.8);
}

.d405-status-item:nth-child(1),
.d405-status-item:nth-child(2) {
  grid-column: span 2;
}

.d405-status-item span,
.d405-preview-title {
  display: block;
  color: #9bc3e2;
  font-size: 11px;
}

.d405-status-item strong {
  display: block;
  margin-top: 3px;
  color: #eef7fc;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.status-ok {
  color: #72d88a;
}

.status-error {
  color: #ff9b9b;
}

.d405-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.d405-mini-status {
  font-size: 12px;
  white-space: nowrap;
}

.d405-auto-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #cde4f4;
  font-size: 12px;
}

.d405-preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}

.d405-preview {
  min-width: 0;
}

.d405-preview canvas {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  margin-top: 5px;
  border-radius: 6px;
  background: #05080c;
  image-rendering: pixelated;
}

.d405-note {
  margin-top: 8px;
  color: #cfe3f2;
  font-size: 11px;
  overflow-wrap: anywhere;
}

.d405-error {
  margin-top: 6px;
  color: #ffb4b4;
  font-size: 11px;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .d405-observation-panel {
    right: 12px;
    bottom: 74px;
    width: calc(100vw - 24px);
  }

  .d405-status-grid,
  .d405-preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
