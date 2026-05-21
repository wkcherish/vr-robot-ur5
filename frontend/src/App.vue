<template>
  <div class="common-layout">
    <el-container>
      <div id="webgl">
        <!-- 现有面板添加显示条件 -->
        <Menu
          :show-slider-controls="showSlider"
          :joint-values="sliderJointValues"
          @sliderInput="sliderInput"
          @sliderCommit="sliderCommit"
          v-show="showSlider"
        />

        <!-- 机器人控制面板 -->
        <div class="robot-control-panel" v-show="showRobotPanel">
          <div class="panel-header">
            <h3>机器人双向映射系统</h3>
            <div class="connection-status" :class="{ connected: isWebSocketConnected }">
              {{ isWebSocketConnected ? "已连接" : "未连接" }}
            </div>
          </div>

          <!-- 添加仿真控制组件 -->
          <Control v-show="showControlPanel" />
          <!-- 连接控制区 -->
          <div class="panel-section">
            <h4 class="section-title">机器人连接</h4>
            <button
              @click="isWebSocketConnected ? stopFetchingData() : startFetchingData()"
              class="control-button"
              :class="{
                'robot-connect-btn--connected': isWebSocketConnected,
                'robot-connect-btn--disconnected': !isWebSocketConnected,
              }"
            >
              {{ isWebSocketConnected ? "断开连接" : "连接机器人" }}
            </button>
            <div v-if="isWebSocketConnected" class="status-indicator">
              <span class="status-dot pulse"></span> 正在实时同步机器人位置...
            </div>
          </div>

          <!-- 角度控制区 -->
          <div class="panel-section">
            <h4 class="section-title">角度控制</h4>
            <div class="angle-input-container">
              <input
                v-model="angleInput"
                type="text"
                placeholder="输入关节角度: J1,J2,J3,J4,J5,J6,Grip"
                class="angle-input"
              />
              <div class="preset-angles">
                <span class="preset-title">预设:</span>
                <button @click="setPresetAngles('home')" class="preset-btn">
                  初始位置
                </button>
                <button @click="setPresetAngles('work')" class="preset-btn">
                  工作位置
                </button>
                <button @click="setPresetAngles('safe-1')" class="preset-btn">
                  安全点1
                </button>
                <button @click="setPresetAngles('safe-2')" class="preset-btn">
                  安全点2
                </button>
                <button @click="setPresetAngles('safe-3')" class="preset-btn">
                  安全点3
                </button>
              </div>
            </div>
            <div class="action-buttons">
              <button @click="inputRobotAngles" class="action-button send-btn">
                <span class="btn-icon">↗</span>发送到机器人
              </button>
              <button @click="testSendData" class="action-button test-btn">
                <span class="btn-icon">⚙</span>测试运动
              </button>
            </div>
          </div>

          <!-- 状态反馈区 -->
          <div class="panel-section">
            <h4 class="section-title">操作反馈</h4>
            <div class="feedback-area">
              <div v-if="jointAngles.length" class="feedback-item">
                <div class="feedback-label">当前关节角度:</div>
                <div class="feedback-value">
                  {{ formatAngles(jointAngles) }}
                </div>
              </div>

              <div v-if="setAnglesResponse.length" class="feedback-item">
                <div class="feedback-label">已设置角度值:</div>
                <div class="feedback-value">
                  {{ formatAngles(setAnglesResponse) }}
                </div>
              </div>

              <div v-if="receivedText" class="feedback-item">
                <div class="feedback-label">系统反馈:</div>
                <div class="feedback-value">{{ receivedText }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 修改视角切换按钮为下拉菜单 -->
        <div class="view-controls" v-show="showViewControls">
          <select
            v-model="selectedView"
            @change="changeView"
            class="view-selector"
          >
            <option value="perspective">透视视角</option>
            <option value="top">俯视视角</option>
          </select>
        </div>

        <!-- 添加任务进度显示 -->
        <div class="task-progress" v-show="showTaskProgress">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${taskProgress}%` }"
            ></div>
          </div>
          <div class="progress-text">任务进度: {{ taskProgress }}%</div>
        </div>

        <div class="vr-control-panel" :class="{ 'quest-device': isQuest3Device }" v-if="showVrControlPanel">
          <div class="vr-control-header">
            <h4>VR控制中心</h4>
            <button class="vr-control-close" @click="showVrControlPanel = false">关闭</button>
          </div>

          <div class="vr-control-section">
            <div class="vr-section-title">局域网接入分析</div>
            <button class="network-check-button" @click="runQuest3AccessChecks">重新分析</button>
            <div class="network-status-row">
              <span class="network-label">访问端:</span>
              <span class="network-value">{{ isQuest3Device ? "Quest3" : "桌面浏览器" }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">主机名:</span>
              <span class="network-value">{{ localHostname || "-" }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">宿主机 IP:</span>
              <span class="network-value">{{ localHostIp || "未解析" }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">前端访问地址:</span>
              <span class="network-value">{{ hostPageAccessUrl || "自动生成中..." }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">后端 HTTP:</span>
              <span class="network-value">{{ backendHttpOrigin }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">后端 WS:</span>
              <span class="network-value">{{ backendWsAddress }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">health:</span>
              <span class="network-value" :class="`status-${backendHealthStatus}`">
                {{ normalizeStatusLabel(backendHealthStatus) }} | {{ backendHealthMessage }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">WebSocket:</span>
              <span class="network-value" :class="`status-${wsCheckStatus}`">
                {{ normalizeStatusLabel(wsCheckStatus) }} | {{ wsCheckMessage }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">D405链路:</span>
              <span class="network-value" :class="`status-${d405CheckStatus}`">
                {{ normalizeStatusLabel(d405CheckStatus) }} | {{ d405CheckMessage }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">录制配置:</span>
              <span class="network-value" :class="`status-${recordingCheckStatus}`">
                {{ normalizeStatusLabel(recordingCheckStatus) }} | {{ recordingCheckMessage }}
              </span>
            </div>
            <div class="network-hint-row" v-for="hint in networkAccessHints" :key="hint">
              {{ hint }}
            </div>
          </div>

          <div class="vr-control-section">
            <div class="vr-section-title">VR模式控制</div>
            <div class="vr-mode-line">
              <span class="vr-mode-chip" :class="`status-${vrModeState}`">{{ vrModeText }}</span>
              <span class="vr-owner-chip">控制源: {{ vrControlOwnerText }}</span>
            </div>
            <div class="vr-menu-buttons vr-entry-buttons">
              <button
                class="vr-menu-btn enter"
                :class="{ active: isVrModeEntered }"
                :disabled="vrEnterInProgress"
                @click="enterVrMode"
              >
                {{ vrEnterInProgress ? "进入中..." : "进入VR模式" }}
              </button>
              <button
                class="vr-menu-btn exit"
                :class="{ active: !isVrModeEntered }"
                @click="exitVrMode"
              >
                退出VR模式
              </button>
            </div>
            <div class="vr-menu-buttons" v-if="isVrModeEntered">
              <button
                class="vr-menu-btn"
                :class="{ active: vrModeState === 'vr_controller_mode' }"
                @click="chooseVrInputMode('controller')"
              >
                手柄模式
              </button>
              <button
                class="vr-menu-btn"
                :class="{ active: vrModeState === 'vr_hand_mode' }"
                @click="chooseVrInputMode('hand')"
              >
                手势模式
              </button>
            </div>
            <div class="quest-controller-status" v-if="isVrModeEntered && vrModeState === 'vr_controller_mode'">
              <div class="network-status-row">
                <span class="network-label">当前关节组:</span>
                <span class="network-value">{{ vrSelectedJointGroupText }}</span>
              </div>
              <div class="network-status-row" v-if="questControllerRawInput && questControllerRawInput.right">
                <span class="network-label">右摇杆/扳机:</span>
                <span class="network-value">
                  X={{ Number(questControllerRawInput.right.stick_x || 0).toFixed(2) }},
                  Y={{ Number(questControllerRawInput.right.stick_y || 0).toFixed(2) }},
                  T={{ Number(questControllerRawInput.right.trigger || 0).toFixed(2) }}
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">灵敏度:</span>
                <span class="network-value">
                  <input
                    class="vr-inline-slider"
                    type="range"
                    min="0.4"
                    max="1.8"
                    step="0.1"
                    v-model.number="questControllerSensitivity"
                  />
                  {{ questControllerSensitivity.toFixed(1) }}
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">输入死区:</span>
                <span class="network-value">
                  <input
                    class="vr-inline-slider"
                    type="range"
                    min="0.05"
                    max="0.30"
                    step="0.01"
                    v-model.number="questControllerDeadzone"
                  />
                  {{ questControllerDeadzone.toFixed(2) }}
                </span>
              </div>
              <div v-if="questControllerGroupToast" class="vr-joint-toast">{{ questControllerGroupToast }}</div>
            </div>
            <div class="quest-hand-status" v-if="isVrModeEntered && vrModeState === 'vr_hand_mode'">
              <div class="network-status-row">
                <span class="network-label">追踪稳定性:</span>
                <span class="network-value" :class="{ 'status-ok': questHandTrackingStable, 'status-error': !questHandTrackingStable }">
                  {{ questHandTrackingStable ? "稳定" : "不稳定" }} | {{ (questHandTrackingStability * 100).toFixed(0) }}%
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">手势模式:</span>
                <span class="network-value">
                  {{
                    questHandRawInput && questHandRawInput.left_controller_fallback
                      ? "左控制器兜底模式"
                      : questHandInputMode === "left_hand_ee_ik"
                        ? "左手末端IK模式"
                        : questHandInputMode === "left_hand"
                          ? "左手单手模式"
                        : questHandInputMode === "dual_hand"
                          ? "双手模式"
                          : "单手降级模式"
                  }}
                </span>
              </div>
              <div
                class="network-status-row"
                v-if="questHandRawInput && questHandRawInput.left"
              >
                <span class="network-label">左手追踪:</span>
                <span class="network-value">
                  {{
                    questHandRawInput.left && (questHandRawInput.left.tracked || questHandRawInput.left.recently_tracked)
                      ? "可用"
                      : "丢失"
                  }}
                  ({{ (((questHandRawInput.left && questHandRawInput.left.stability) || 0) * 100).toFixed(0) }}%)
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">控制目标:</span>
                <span class="network-value">{{ vrSelectedJointGroupText }}</span>
              </div>
              <div class="network-status-row">
                <span class="network-label">手势灵敏度:</span>
                <span class="network-value">
                  <input
                    class="vr-inline-slider"
                    type="range"
                    min="0.4"
                    max="1.8"
                    step="0.1"
                    v-model.number="questHandSensitivity"
                  />
                  {{ questHandSensitivity.toFixed(1) }}
                </span>
              </div>
              <div class="network-status-row" v-if="questHandRawInput && questHandRawInput.input_source_count !== undefined">
                <span class="network-label">输入源计数:</span>
                <span class="network-value">{{ questHandRawInput.input_source_count }}</span>
              </div>
              <div v-if="questHandGroupToast" class="vr-joint-toast">{{ questHandGroupToast }}</div>
            </div>
            <div v-if="vrErrorMessage" class="vr-menu-error">{{ vrErrorMessage }}</div>
          </div>

          <div class="vr-control-section">
            <div class="vr-section-title">状态同步</div>
            <div class="sync-status-grid compact">
              <div class="sync-status-item">
                <span class="sync-label">连接状态:</span>
                <span class="sync-value" :class="{ 'sync-connected': isWebSocketConnected, 'sync-disconnected': !isWebSocketConnected }">
                  {{ isWebSocketConnected ? '已连接' : '未连接' }}
                </span>
              </div>
              <div class="sync-status-item">
                <span class="sync-label">连接质量:</span>
                <span class="sync-value" :class="{ 'sync-good': connectionQuality >= 80, 'sync-fair': connectionQuality >= 50 && connectionQuality < 80, 'sync-poor': connectionQuality < 50 }">
                  {{ connectionQuality }}%
                </span>
              </div>
              <div class="sync-status-item">
                <span class="sync-label">实际帧率:</span>
                <span class="sync-value">{{ actualUpdateRate.toFixed(1) }} Hz</span>
              </div>
              <div class="sync-status-item">
                <span class="sync-label">网络延迟:</span>
                <span class="sync-value" :class="{ 'sync-high-latency': networkLatency > 100 }">
                  {{ networkLatency.toFixed(0) }} ms
                </span>
              </div>
              <div class="sync-status-item">
                <span class="sync-label">同步错误:</span>
                <span class="sync-value" :class="{ 'sync-has-errors': stateSyncErrors > 0 }">
                  {{ stateSyncErrors }}
                </span>
              </div>
              <div class="sync-status-item">
                <span class="sync-label">插值状态:</span>
                <span class="sync-value">
                  <button @click="toggleStateInterpolation" class="interpolation-toggle" :class="{ active: stateInterpolationEnabled }">
                    {{ stateInterpolationEnabled ? '启用' : '禁用' }}
                  </button>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 添加底部控制面板 -->
        <div class="panel-controls">
          <button
            @click="togglePanel('slider')"
            class="panel-control-button"
            :class="{ active: showSlider }"
          >
            <span class="panel-icon">🎚️</span> 滑块面板
          </button>
          <button
            @click="togglePanel('robot')"
            class="panel-control-button"
            :class="{ active: showRobotPanel }"
          >
            <span class="panel-icon">🤖</span> 机器人控制
          </button>
          <button
            @click="togglePanel('control')"
            class="panel-control-button"
            :class="{ active: showControlPanel }"
          >
            <span class="panel-icon">🎮</span> 仿真控制
          </button>
          <button
            @click="togglePanel('view')"
            class="panel-control-button"
            :class="{ active: showViewControls }"
          >
            <span class="panel-icon">👁️</span> 视角切换
          </button>
          <button
            @click="togglePanel('progress')"
            class="panel-control-button"
            :class="{ active: showTaskProgress }"
          >
            <span class="panel-icon">📊</span> 任务进度
          </button>
          <button
            @click="togglePanel('vr-control')"
            class="panel-control-button"
            :class="{ active: showVrControlPanel }"
          >
            <span class="panel-icon">🥽</span> VR控制
          </button>
        </div>
      </div>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, defineAsyncComponent } from "vue";
const Menu = defineAsyncComponent(() => import("./components/robot.vue"));
const Control = defineAsyncComponent(() => import("./components/control.vue"));
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { XRControllerModelFactory } from "three/addons/webxr/XRControllerModelFactory.js";
import { XRHandModelFactory } from "three/addons/webxr/XRHandModelFactory.js";
import URDFLoader from "urdf-loader";
import websocketManager from "./utils/websocket.js"; // 引入WebSocket管理器
import { runtimeConfig, getDeviceCategory } from "./utils/runtimeConfig.js";
import { get, post } from "./utils/network.js";
import { readQuestControllerSnapshot } from "./utils/questControllerInput.js";
import { createQuestControllerTeleop } from "./utils/questControllerTeleop.js";
import {
  startQuestHandInput,
  stopQuestHandInput,
  readQuestHandSnapshot,
  getQuestHandInputStatus,
} from "./utils/questHandInput.js";
import { createQuestHandTeleop } from "./utils/questHandTeleop.js";
import {
  ensureQuestXRSession,
  getQuestXRSession,
  stopQuestXRSession,
} from "./utils/questXRSession.js";

// 修改视角控制为下拉菜单
const selectedView = ref("perspective"); // 默认选择透视视角
// 新增任务进度变量
const taskProgress = ref(0);

// 各面板显示状态控制
const showSlider = ref(false); // 滑块面板默认不显示
const showRobotPanel = ref(false); // 机器人控制面板默认不显示
const showControlPanel = ref(false); // 仿真控制面板默认不显示
const showViewControls = ref(true); // 视角控制默认显示
const showTaskProgress = ref(true); // 任务进度默认显示
const showVrControlPanel = ref(false); // VR控制中心默认不显示
const ARM_JOINT_COUNT = 6;
const TOTAL_INPUT_JOINT_COUNT = 7;
const GRIPPER_MIN_RAD = 0;
const GRIPPER_MAX_RAD = 0.87;
const GRIPPER_MIN_DEG = 0;
const GRIPPER_MAX_DEG = (GRIPPER_MAX_RAD * 180) / Math.PI;
const DEFAULT_ANGLES_DEG = [0, -90, 90, -90, -90, 0, 0];
const DEFAULT_TEST_ANGLES_DEG = [60, -90, 90, -140, -90, 0, 0];
const BACKEND_ARM_JOINT_NAMES = [
  "shoulder_pan_joint",
  "shoulder_lift_joint",
  "elbow_joint",
  "wrist_1_joint",
  "wrist_2_joint",
  "wrist_3_joint",
];
const LOCAL_MANUAL_SOURCES = new Set([
  "desktop_manual",
  "quest3_controller",
  "quest3_hand",
]);
const ARM_JOINT_NAMES = [
  "link1_joint",
  "link2_joint",
  "link3_joint",
  "link4_joint",
  "link5_joint",
  "link6_joint",
];
const GRIPPER_JOINT_NAMES = [
  "left_driver_joint",
  "right_driver_joint",
  "left_driver-left_coupler",
  "right_driver-right_coupler",
  "left_spring_link_joint",
  "right_spring_link_joint",
  "left_follower_joint",
  "right_follower_joint",
];

const angleInput = ref(""); // 新增用于存储输入角度的变量
// 自动返回设置
const enableAutoReturn = ref(false); // 如果启用，发送位置后自动返回home
const autoReturnDelayMs = ref(2000); // 自动返回延迟（ms）
const homeAnglesDeg = ref([...DEFAULT_ANGLES_DEG]); // 默认home角度（度）

const inputText = ref(""); // 新增用于存储输入字符的变量

const receivedText = ref(""); // 新增用于存储后端返回的文本
const fetchedValue = ref(null); // 新增用于存储从后端获取的数值

const jointAngles = ref([]); // 新增用于存储关节角度的变量
const setAnglesResponse = ref([]); // 用于存储设置的角度值的响应
const gripperAngleDeg = ref(0);
const sliderJointValues = computed(() => {
  const armAngles =
    jointAngles.value.length >= ARM_JOINT_COUNT
      ? jointAngles.value.slice(0, ARM_JOINT_COUNT)
      : DEFAULT_ANGLES_DEG.slice(0, ARM_JOINT_COUNT);
  return [...armAngles, gripperAngleDeg.value];
});

const fetchInterval = ref(null); // 用于存储定时器的引用
const testvalue = ref(null); // 用于存储从后端获取的数值
const isFetching = ref(false);
const fetchFailures = ref(0); // 连续获取失败计数
const sendCommandPending = ref(false); // 命令发送等待回复标志
const isApplyingBackendState = ref(false); // 防止回放后端状态时触发反向发送
const sliderSyncTimer = ref(null);
const lastRealtimeSliderSendAt = ref(0);
const pendingManualTarget = ref(null);
const realtimeSliderDraft = ref(null);
const realtimeSliderFallbackInFlight = ref(false);
const backendPoseSmoothingEnabled = ref(true);
const backendPoseSmoothingAlpha = ref(0.26);
const backendRenderTarget = ref(null);
const questRenderPreviewTarget = ref(null);

const REALTIME_SLIDER_DEBOUNCE_MS = 16;
const REALTIME_SLIDER_MIN_SEND_INTERVAL_MS = 33;
const REALTIME_SLIDER_COMMAND_STEPS = 40;
const REALTIME_SLIDER_DRAFT_TTL_MS = 1200;
const MANUAL_STATE_GUARD_MS = 700;
const VR_MANUAL_STATE_GUARD_MS = 1200;
const BACKEND_STATE_STALE_TOLERANCE_MS = 120;
const BACKEND_STATE_TIMESTAMP_EPSILON_MS = 1;
const ARM_STATE_MATCH_THRESHOLD_RAD = 0.08;
const GRIPPER_STATE_MATCH_THRESHOLD_RAD = 0.12;
const MAX_RENDER_PIXEL_RATIO = 1.5;
const QUEST_MAX_RENDER_PIXEL_RATIO = 1.0;
const UI_SYNC_INTERVAL_MS = 66;
const UI_POSE_SYNC_INTERVAL_MS = 100;
const VR_STATE_SYNC_MIN_INTERVAL_MS = 180;
const VR_COMMAND_MIN_INTERVAL_MS = 20;
const VR_COMMAND_STEPS = 20;
const VR_MODE_TRANSITION_GUARD_MS = 420;
const VR_CONTROL_WATCHDOG_INTERVAL_MS = 33;
const VR_CONTROL_WATCHDOG_STALE_MS = 55;
const VR_RENDER_SMOOTHING_ALPHA = 0.42;
const QUEST_RENDER_PREVIEW_TTL_MS = 180;
const RENDER_ARM_EPSILON_RAD = 2e-4;
const RENDER_GRIPPER_EPSILON_RAD = 2e-4;
const DEBUG_VR_CONTROL_RESULTS = false;

// WebSocket 状态同步相关
const isWebSocketConnected = ref(false);
const websocketStatus = ref("未连接");
const simulationState = ref(null); // 完整的仿真状态
const stateUpdateHistory = ref([]); // 状态更新历史，用于插值
const networkLatency = ref(0); // 网络延迟
const stateSyncErrors = ref(0); // 状态同步错误计数
const lastStateUpdate = ref(0); // 最后状态更新时间
const lastAcceptedBackendStateTimestampMs = ref(0);
const stateInterpolationEnabled = ref(true); // 启用状态插值
const targetUpdateRate = ref(50); // 目标更新率 (Hz)
const actualUpdateRate = ref(0); // 实际更新率
const stateBufferSize = ref(10); // 状态缓冲区大小
const connectionQuality = ref(100); // 连接质量百分比
const robotPosition = ref({ x: 0, y: 0, z: 0 });
const robotOrientation = ref({ roll: 0, pitch: 0, yaw: 0 });

const deviceCategory = ref(getDeviceCategory());
const localHostname = ref("");
const localHostIp = ref("");
const hostPageAccessUrl = ref("");
const backendHealthStatus = ref("unknown");
const backendHealthMessage = ref("未检查");
const wsCheckStatus = ref("unknown");
const wsCheckMessage = ref("未检查");
const d405CheckStatus = ref("unknown");
const d405CheckMessage = ref("未检查");
const recordingCheckStatus = ref("unknown");
const recordingCheckMessage = ref("未检查");
const networkPrereqOk = ref(false);

const vrModeState = ref("vr_disabled");
const selectedVrInputMode = ref("");
const vrErrorMessage = ref("");
const vrEnterInProgress = ref(false);
const vrSelectedJointGroup = ref("arm_full");
const vrControlOwner = ref("desktop_manual");
const lastLocalVrModeSetAt = ref(0);
const questControllerAvailable = ref(false);
const questControllerStatusText = ref("未激活");
const questControllerSensitivity = ref(1.0);
const questControllerDeadzone = ref(0.1);
const questControllerGroupToast = ref("");
const questControllerGroupToastAt = ref(0);
const questControllerRawInput = ref(null);
const questControllerFallbackInFlight = ref(false);
const lastQuestControllerTickAt = ref(0);
const lastQuestControllerSentAt = ref(0);
const questControllerQueuedFlushTimer = ref(null);
const questControllerPendingMapped = ref(null);
const questControllerControlSeq = ref(0);
const questHandAvailable = ref(false);
const questHandStatusText = ref("未激活");
const questHandSensitivity = ref(0.9);
const questHandTrackingStable = ref(false);
const questHandTrackingStability = ref(0);
const questHandInputMode = ref("left_hand_ee_ik");
const questHandGroupToast = ref("");
const questHandGroupToastAt = ref(0);
const questHandRawInput = ref(null);
const questHandFallbackInFlight = ref(false);
const lastQuestHandTickAt = ref(0);
const lastQuestHandSentAt = ref(0);
const questHandQueuedFlushTimer = ref(null);
const questHandPendingMapped = ref(null);
const questHandControlSeq = ref(0);
const questVrControlWatchdogTimer = ref(null);
const lastVrStateSyncedAt = ref(0);
const questHandUnstableSinceAt = ref(0);
const questHandUnavailableSinceAt = ref(0);
const QUEST_HAND_UNSTABLE_GRACE_MS = 260;
const QUEST_HAND_UNAVAILABLE_GRACE_MS = 320;

const VR_MODE_LOCAL_LOCK_MS = 1200;
const VR_ENTERED_MODES = new Set(["vr_ready", "vr_controller_mode", "vr_hand_mode"]);

const uiLastJointSyncAt = ref(0);
const uiLastPoseSyncAt = ref(0);

let questControllerTeleop = createQuestControllerTeleop({
  deadzone: questControllerDeadzone.value,
  joint_step: 0.085 * clamp(questControllerSensitivity.value, 0.4, 1.8),
  max_target_lead_rad: 0.45,
});
let questHandTeleop = createQuestHandTeleop({
  sensitivity: questHandSensitivity.value,
});

const isQuest3Device = computed(() => deviceCategory.value === "quest3");
const isPageSecureContext = computed(() => {
  if (typeof window === "undefined") return false;
  return Boolean(window.isSecureContext);
});
const backendHttpOrigin = computed(() => runtimeConfig.backendOrigin);
const backendWsAddress = computed(() => runtimeConfig.simWsUrl);
const networkAccessHints = computed(() => {
  const hints = [];
  if (!localHostIp.value) {
    hints.push("主机 IP 未解析，建议手动设置 VITE_HOST_IP。");
  }
  if (isQuest3Device.value) {
    hints.push("当前为 Quest3 访问，请确认与主机处于同一局域网。");
    if (!isPageSecureContext.value) {
      hints.push("当前页面不是安全上下文，请改用 HTTPS 地址访问（需先信任证书）。");
    }
  }
  return hints;
});

const vrSelectedJointGroupText = computed(() => {
  const mapping = {
    upper_arm: "大臂组",
    forearm: "前臂组",
    wrist: "腕部组",
    arm_full: "全臂",
    end_effector: "末端执行器",
  };
  return mapping[vrSelectedJointGroup.value] || "未选择";
});

const vrModeText = computed(() => {
  if (vrModeState.value === "vr_controller_mode") return "手柄模式";
  if (vrModeState.value === "vr_hand_mode") return "手势模式";
  if (vrModeState.value === "vr_ready") return "待机";
  if (vrModeState.value === "vr_disabled") return "未启用";
  if (vrModeState.value === "vr_error") return "异常";
  return "未知";
});

const isVrModeEntered = computed(() => VR_ENTERED_MODES.has(vrModeState.value));

const vrControlOwnerText = computed(() => {
  const mapping = {
    desktop_manual: "桌面手动",
    quest3_controller: "Quest3手柄",
    quest3_hand: "Quest3手势",
    task: "任务执行",
    policy: "策略控制",
    manual: "手动",
  };
  return mapping[vrControlOwner.value] || "未知";
});

// 兼容旧 UI 关节名(link*_joint)与当前 URDF 关节名
const jointNameMap = {
  link1_joint: "shoulder_pan_joint",
  link2_joint: "shoulder_lift_joint",
  link3_joint: "elbow_joint",
  link4_joint: "wrist_1_joint",
  link5_joint: "wrist_2_joint",
  link6_joint: "wrist_3_joint",
};
const warnedMissingJoints = new Set();

// 新增: 计算机器臂末端位置的函数
const calculateEndEffectorPosition = () => {
  if (!robot || !robot.joints) return;

  // 获取末端执行器位置
  const endEffector = robot.links["tool0"];
  if (!endEffector) return;

  // 获取世界坐标中的位置
  const worldPosition = new THREE.Vector3();
  endEffector.getWorldPosition(worldPosition);

  // 更新位置数据
  robotPosition.value = {
    x: worldPosition.x,
    y: worldPosition.y,
    z: worldPosition.z,
  };

  // 获取姿态信息
  const worldQuaternion = new THREE.Quaternion();
  endEffector.getWorldQuaternion(worldQuaternion);

  // 从四元数转换为欧拉角 (角度)
  const euler = new THREE.Euler().setFromQuaternion(worldQuaternion);
  robotOrientation.value = {
    roll: euler.x * (180 / Math.PI),
    pitch: euler.y * (180 / Math.PI),
    yaw: euler.z * (180 / Math.PI),
  };
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function getRenderPixelRatio() {
  const dpr =
    typeof window !== "undefined" ? Number(window.devicePixelRatio || 1) : 1;
  if (!Number.isFinite(dpr)) return 1;
  const maxRatio = isQuest3Device.value ? QUEST_MAX_RENDER_PIXEL_RATIO : MAX_RENDER_PIXEL_RATIO;
  return clamp(dpr, 1, maxRatio);
}

const BACKEND_FRAME_Z_OFFSET = 0.5;
const BACKEND_TO_FRONTEND_ROT = new THREE.Quaternion().setFromAxisAngle(
  new THREE.Vector3(1, 0, 0),
  -Math.PI / 2
);

function toRadians(degrees) {
  return (Number(degrees) * Math.PI) / 180;
}

function toDegrees(radians) {
  return (Number(radians) * 180) / Math.PI;
}

function readHostCandidate() {
  const envHostIp = String(import.meta.env.VITE_HOST_IP || "").trim();
  if (envHostIp) return envHostIp;

  if (typeof window === "undefined" || !window.location) return "";
  const host = String(window.location.hostname || "").trim();
  if (!host || host === "localhost" || host === "127.0.0.1") return "";
  return host;
}

function buildPageAccessUrlFromHost(hostValue) {
  const host = String(hostValue || "").trim();
  if (!host) return "";
  const pagePort = Number(import.meta.env.VITE_PAGE_PORT || window.location.port || 5173);
  const preferProtocol = String(import.meta.env.VITE_PAGE_PROTOCOL || "").trim().toLowerCase();
  const forceHttpsRaw = String(import.meta.env.VITE_FORCE_HTTPS_PAGE_URL || "").trim().toLowerCase();
  const forceHttpsByFlag = ["1", "true", "yes", "on"].includes(forceHttpsRaw);
  const hasHttpsCertEnv =
    String(import.meta.env.VITE_HTTPS_CERT || "").trim().length > 0 &&
    String(import.meta.env.VITE_HTTPS_KEY || "").trim().length > 0;
  const pageIsHttps =
    typeof window !== "undefined" && window.location && window.location.protocol === "https:";
  const shouldUseHttps =
    preferProtocol === "https" ||
    (preferProtocol !== "http" && (forceHttpsByFlag || hasHttpsCertEnv || pageIsHttps || isLikelySameLan(host)));
  const pageProtocol = shouldUseHttps ? "https://" : "http://";
  if (host.includes(":")) {
    return pageProtocol + "[" + host + "]:" + pagePort;
  }
  return pageProtocol + host + ":" + pagePort;
}

function normalizeStatusLabel(status) {
  if (status === "ok") return "可用";
  if (status === "error") return "异常";
  if (status === "checking") return "检查中";
  return "未检查";
}

function isLikelySameLan(ipLikeHost) {
  const host = String(ipLikeHost || "").trim();
  if (!host) return false;
  if (host === "localhost" || host === "127.0.0.1") return false;
  if (/^10\./.test(host)) return true;
  if (/^192\.168\./.test(host)) return true;
  if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(host)) return true;
  if (host.endsWith(".local")) return true;
  return false;
}

function updateNetworkPrereq() {
  const lanOk = isLikelySameLan(localHostIp.value) || isLikelySameLan(localHostname.value);
  const checksOk =
    backendHealthStatus.value === "ok" &&
    wsCheckStatus.value === "ok" &&
    d405CheckStatus.value === "ok" &&
    recordingCheckStatus.value === "ok";
  networkPrereqOk.value = lanOk && checksOk;
}

async function checkBackendHealth() {
  backendHealthStatus.value = "checking";
  backendHealthMessage.value = "检查 /health/...";
  try {
    const response = await get("/health/", { timeout: 2000 });
    const status = String(response?.data?.status || "").toLowerCase();
    const service = response?.data?.service || "backend";
    if (status === "healthy" || status === "degraded") {
      backendHealthStatus.value = "ok";
      backendHealthMessage.value = service + " 在线(" + status + ")";

      const hostIpFromBackend = String(response?.data?.host_ip || "").trim();
      if (hostIpFromBackend) {
        localHostIp.value = hostIpFromBackend;
      }

      if (!localHostname.value && typeof window !== "undefined" && window.location) {
        localHostname.value = String(window.location.hostname || "").trim();
      }

      if (!localHostIp.value && localHostname.value) {
        localHostIp.value = localHostname.value;
      }

      const preferredHost = localHostIp.value || localHostname.value;
      if (preferredHost) {
        hostPageAccessUrl.value = buildPageAccessUrlFromHost(preferredHost);
      }
    } else {
      backendHealthStatus.value = "error";
      backendHealthMessage.value = "健康检查返回异常状态";
    }
  } catch (error) {
    backendHealthStatus.value = "error";
    backendHealthMessage.value = "健康检查失败: " + (error?.message || error);
  }
}

function checkWebSocketReady() {
  wsCheckStatus.value = websocketManager.isConnected ? "ok" : "error";
  wsCheckMessage.value = websocketManager.isConnected
    ? "WebSocket 已连接"
    : "WebSocket 未连接";
}

function updateHandTrackingFromBackend(state) {
  const vr = state?.vr || {};
  const handAvailable = Boolean(vr?.input_source_available?.hand);
  if (typeof vr?.mode === "string" && vr.mode === "vr_hand_mode") {
    questHandAvailable.value = handAvailable;
  }
  const backendStability = Number(state?.normalized_input?.tracking_stability);
  if (Number.isFinite(backendStability)) {
    questHandTrackingStability.value = clamp(backendStability, 0, 1);
    questHandTrackingStable.value = backendStability >= 0.30;
  }
  const backendInputMode = String(state?.normalized_input?.hand_input_mode || "").trim();
  if (
    backendInputMode === "left_hand_ee_ik" ||
    backendInputMode === "left_hand" ||
    backendInputMode === "dual_hand" ||
    backendInputMode === "single_hand"
  ) {
    questHandInputMode.value = backendInputMode;
  }
}

function checkD405ObservationReady(state) {
  const camera = state?.camera;
  const cameraDevice = String(camera?.device || "");
  const rgbName = String(camera?.rgb?.interface_name || "");
  const depthName = String(camera?.depth?.interface_name || "");
  const captureOk = Boolean(state?.camera_capture_ok ?? camera?.camera_capture_ok);
  const frameAligned = Boolean(camera?.frame_aligned);
  const recordable = Boolean(camera?.recordable_training_observation);

  const isD405 = cameraDevice === "intel_realsense_d405";
  const hasStreams = rgbName.length > 0 && depthName.length > 0;

  if (isD405 && hasStreams && captureOk && frameAligned && recordable) {
    d405CheckStatus.value = "ok";
    d405CheckMessage.value = "D405 RGB-D 已就绪";
    return;
  }

  d405CheckStatus.value = "error";
  d405CheckMessage.value = "D405 观测链未就绪";
}

function checkRecordingBindingReady(state) {
  const camera = state?.camera;
  const intrinsicsVersion = String(camera?.camera_intrinsics_version || "");
  const extrinsicsVersion = String(camera?.camera_extrinsics_version || "");
  const recordable = Boolean(camera?.recordable_training_observation);

  if (recordable && intrinsicsVersion.length > 0 && extrinsicsVersion.length > 0) {
    recordingCheckStatus.value = "ok";
    recordingCheckMessage.value = "RGB-D 录制配置已绑定";
    return;
  }

  recordingCheckStatus.value = "error";
  recordingCheckMessage.value = "录制配置未绑定(缺少标定版本或录制标记)";
}

function getQuestSourceFromBackendState(state) {
  const source = String(state?.source || state?.input_source || state?.vr?.control_owner || "").trim();
  return source === "quest3_controller" || source === "quest3_hand" ? source : "";
}

function isInactiveQuestSourceState(state) {
  const source = getQuestSourceFromBackendState(state);
  if (!source) return false;

  const wantsHand = selectedVrInputMode.value === "hand" || vrModeState.value === "vr_hand_mode";
  const wantsController =
    selectedVrInputMode.value === "controller" || vrModeState.value === "vr_controller_mode";

  if (wantsHand && source === "quest3_controller") return true;
  if (wantsController && source === "quest3_hand") return true;
  return false;
}

function applyVrStateFromBackend(state) {
  if (isInactiveQuestSourceState(state)) {
    return;
  }
  const vr = state?.vr;
  if (!vr || typeof vr !== "object") return;
  if (typeof vr.mode === "string") {
    if (!shouldIgnoreBackendVrMode(vr.mode)) {
      vrModeState.value = vr.mode;
    }
  }
  if (typeof vr.selected_joint_group === "string" && vr.selected_joint_group.length > 0) {
    vrSelectedJointGroup.value = vr.selected_joint_group;
  }
  if (typeof vr.control_owner === "string" && vr.control_owner.length > 0) {
    vrControlOwner.value = vr.control_owner;
  }
  if (typeof vr.error_message === "string") {
    vrErrorMessage.value = vr.error_message;
  }
  const selectedGroup = String(state?.selected_joint_group || "").trim();
  if (selectedGroup) {
    vrSelectedJointGroup.value = selectedGroup;
  }
  const inputSource = String(state?.input_source || "").trim();
  if (inputSource === "quest3_controller" || inputSource === "quest3_hand") {
    vrControlOwner.value = inputSource;
  }
  if (state?.raw_input && typeof state.raw_input === "object") {
    questControllerRawInput.value = state.raw_input;
    questHandRawInput.value = state.raw_input;
  }
  updateHandTrackingFromBackend(state);
}

function syncVrStateToBackend(payload, options = {}) {
  const now = Date.now();
  const elapsed = now - Number(lastVrStateSyncedAt.value || 0);
  const forceSync = Boolean(
    options.force === true ||
      payload?.mode === "vr_disabled" ||
      payload?.mode === "vr_error"
  );
  if (!forceSync && elapsed < VR_STATE_SYNC_MIN_INTERVAL_MS) {
    return;
  }
  lastVrStateSyncedAt.value = now;

  if (websocketManager.isConnected) {
    websocketManager.sendVrStateUpdate(payload);
    return;
  }

  post("/sim/vr/state/", payload).catch((error) => {
    console.warn("VR状态同步失败:", error?.message || error);
  });
}

function setVrModeLocally(mode) {
  vrModeState.value = mode;
  lastLocalVrModeSetAt.value = Date.now();
}

function shouldIgnoreBackendVrMode(mode) {
  if (!mode) return false;
  const now = Date.now();
  const elapsed = now - Number(lastLocalVrModeSetAt.value || 0);
  if (elapsed <= VR_MODE_LOCAL_LOCK_MS && mode !== vrModeState.value) {
    return true;
  }
  return false;
}

function buildHttpsAccessHint() {
  const preferredHost = String(localHostIp.value || localHostname.value || "").trim();
  const pagePort = Number(import.meta.env.VITE_PAGE_PORT || window.location.port || 5173);
  const httpsUrl = preferredHost
    ? `https://${preferredHost}:${pagePort}`
    : (typeof window !== "undefined" && window.location
        ? `${window.location.origin.replace(/^http:/, "https:")}`
        : "https://<主机IP>:5173");
  return `请改用 HTTPS 访问前端（示例：${httpsUrl}），并在 Quest3 浏览器中先信任该证书。`;
}

function describeVrEnterFailure(reason, detail) {
  const detailText = String(detail || "").trim();
  if (reason === "insecure_context") {
    const suffix = buildHttpsAccessHint();
    return `进入VR失败：当前页面不是安全上下文。${suffix}`;
  }
  if (reason === "webxr_unavailable") {
    return "进入VR失败：浏览器未提供 WebXR 能力（请确认使用 Quest3 浏览器且系统已启用 XR）。";
  }
  if (reason === "immersive_vr_not_supported") {
    return detailText
      ? `进入VR失败：设备/浏览器不支持 immersive-vr（${detailText}）。`
      : "进入VR失败：设备/浏览器不支持 immersive-vr。";
  }
  if (reason === "user_gesture_or_permission_denied") {
    return detailText
      ? `进入VR失败：未获得手势/权限授权（${detailText}）。`
      : "进入VR失败：未获得手势/权限授权，请在 Quest3 中允许进入 VR。";
  }
  if (reason === "xr_runtime_invalid_state") {
    return detailText
      ? `进入VR失败：XR 运行时状态异常（${detailText}），请先退出已有 VR 会话后重试。`
      : "进入VR失败：XR 运行时状态异常，请先退出已有 VR 会话后重试。";
  }
  if (reason === "xr_runtime_aborted") {
    return detailText
      ? `进入VR失败：XR 会话被中止（${detailText}）。`
      : "进入VR失败：XR 会话被中止，请重试。";
  }
  return detailText
    ? `进入VR失败：XR会话未就绪(${reason}) - ${detailText}`
    : `进入VR失败：XR会话未就绪(${reason})`;
}

async function runQuest3AccessChecks() {
  await checkBackendHealth();

  const latestWsOk = websocketManager.isConnected;

  try {
    const stateResponse = await get("/sim/state/", { timeout: 2000 });
    const state = stateResponse?.data || null;
    checkD405ObservationReady(state);
    checkRecordingBindingReady(state);
    applyVrStateFromBackend(state);
  } catch (error) {
    d405CheckStatus.value = "error";
    d405CheckMessage.value = "读取状态失败: " + (error?.message || error);
    recordingCheckStatus.value = "error";
    recordingCheckMessage.value = "录制配置检查失败";
  }

  wsCheckStatus.value = latestWsOk ? "ok" : "error";
  wsCheckMessage.value = latestWsOk ? "WebSocket 已连接" : "WebSocket 未连接";
  updateNetworkPrereq();
  if (!isQuest3Device.value && !vrErrorMessage.value) {
    vrErrorMessage.value = "当前访问端不是 Quest3，建议在 Quest3 浏览器中操作。";
  } else if (isQuest3Device.value && !networkPrereqOk.value && !vrErrorMessage.value) {
    vrErrorMessage.value = "局域网接入前置检查未通过";
  } else if (networkPrereqOk.value && vrModeState.value !== "vr_error") {
    vrErrorMessage.value = "";
  }

  if (isQuest3Device.value) {
    if (typeof window !== "undefined" && !window.isSecureContext) {
      vrErrorMessage.value = `XR 不可用：当前页面不是安全上下文（需 HTTPS 或 localhost）。${buildHttpsAccessHint()}`;
      return;
    }
    if (typeof navigator === "undefined" || !navigator.xr || !navigator.xr.isSessionSupported) {
      vrErrorMessage.value = "XR 不可用：浏览器不支持 WebXR。";
      return;
    }
    let immersiveVrSupported = false;
    try {
      immersiveVrSupported = await navigator.xr.isSessionSupported("immersive-vr");
    } catch (_) {
      immersiveVrSupported = false;
    }
    if (!immersiveVrSupported) {
      vrErrorMessage.value = "XR 不可用：设备/浏览器不支持 immersive-vr。";
    }
  }
}

function buildQuestControllerRay() {
  const geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, 0, -1),
  ]);
  const material = new THREE.LineBasicMaterial({
    color: 0x69a8ff,
    transparent: true,
    opacity: 0.6,
  });
  const line = new THREE.Line(geometry, material);
  line.name = "quest_controller_ray";
  line.scale.z = 1.6;
  return line;
}

function ensureQuestXrVisualNodes() {
  if (!renderer?.xr || !scene) return;
  const slots = [
    { index: 0, key: "left" },
    { index: 1, key: "right" },
  ];
  slots.forEach(({ index, key }) => {
    const controllerRay = renderer.xr.getController(index);
    if (controllerRay) {
      if (!controllerRay.getObjectByName("quest_controller_ray")) {
        controllerRay.add(buildQuestControllerRay());
      }
      if (!controllerRay.parent) {
        scene.add(controllerRay);
      }
      xrVisualNodes.controllerRays[key] = controllerRay;
    }

    const controllerGrip = renderer.xr.getControllerGrip(index);
    if (controllerGrip) {
      if (!controllerGrip.userData.questControllerModelAttached) {
        controllerGrip.add(xrControllerModelFactory.createControllerModel(controllerGrip));
        controllerGrip.userData.questControllerModelAttached = true;
      }
      if (!controllerGrip.parent) {
        scene.add(controllerGrip);
      }
      xrVisualNodes.controllerGrips[key] = controllerGrip;
    }

    const handNode = renderer.xr.getHand(index);
    if (handNode) {
      if (!handNode.userData.questHandModelAttached) {
        handNode.add(xrHandModelFactory.createHandModel(handNode, "mesh"));
        handNode.userData.questHandModelAttached = true;
      }
      if (!handNode.parent) {
        scene.add(handNode);
      }
      xrVisualNodes.hands[key] = handNode;
    }
  });
}

function updateQuestXrVisualVisibility() {
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  const showControllers = xrPresenting && vrModeState.value === "vr_controller_mode";
  const showLeftHand = xrPresenting && vrModeState.value === "vr_hand_mode";
  const applyVisible = (nodeMap, visible) => {
    Object.values(nodeMap).forEach((node) => {
      if (!node) return;
      node.visible = visible;
    });
  };
  applyVisible(xrVisualNodes.controllerRays, showControllers);
  applyVisible(xrVisualNodes.controllerGrips, showControllers);
  if (xrVisualNodes.hands.left) {
    xrVisualNodes.hands.left.visible = showLeftHand;
  }
  if (xrVisualNodes.hands.right) {
    xrVisualNodes.hands.right.visible = false;
  }
}

function detachQuestXrSessionListeners() {
  if (!activeQuestXrSession) return;
  if (questXrVisibilityHandler) {
    activeQuestXrSession.removeEventListener("visibilitychange", questXrVisibilityHandler);
  }
  if (questXrInputSourcesHandler) {
    activeQuestXrSession.removeEventListener("inputsourceschange", questXrInputSourcesHandler);
  }
  if (questXrEndedHandler) {
    activeQuestXrSession.removeEventListener("end", questXrEndedHandler);
  }
  activeQuestXrSession = null;
  questXrVisibilityHandler = null;
  questXrInputSourcesHandler = null;
  questXrEndedHandler = null;
}

function suppressQuestControllerTransition(options = {}) {
  const durationMs = Math.max(
    0,
    Number(options.duration_ms ?? options.durationMs ?? VR_MODE_TRANSITION_GUARD_MS) || 0
  );
  const requireNeutral = options.require_neutral === true || options.requireNeutral === true;
  if (questControllerTeleop && typeof questControllerTeleop.suppressCommands === "function") {
    questControllerTeleop.suppressCommands({
      duration_ms: durationMs,
      require_neutral: requireNeutral,
    });
  }
  if (options.clear_queue !== false && options.clearQueue !== false) {
    questControllerPendingMapped.value = null;
    resetQuestControllerQueuedFlushTimer();
  }
  if (isQuestControllerModeActive()) {
    questControllerStatusText.value = "输入保护中";
  }
}

function attachQuestXrSessionListeners(session) {
  if (!session || typeof session.addEventListener !== "function") return;
  if (activeQuestXrSession === session) return;
  detachQuestXrSessionListeners();
  activeQuestXrSession = session;
  questXrVisibilityHandler = () => {
    const visibilityState = String(session.visibilityState || "").toLowerCase();
    if (visibilityState && visibilityState !== "visible") {
      suppressQuestControllerTransition({
        duration_ms: VR_MODE_TRANSITION_GUARD_MS + 380,
        require_neutral: true,
        clear_queue: true,
      });
      if (isQuestControllerModeActive()) {
        questControllerStatusText.value = "系统菜单中(已保护)";
      }
    } else {
      suppressQuestControllerTransition({
        duration_ms: VR_MODE_TRANSITION_GUARD_MS,
        require_neutral: true,
        clear_queue: true,
      });
      if (isQuestControllerModeActive()) {
        questControllerStatusText.value = "从系统菜单恢复，等待输入稳定";
      }
    }
    ensureQuestXrVisualNodes();
    updateQuestXrVisualVisibility();
  };
  questXrInputSourcesHandler = () => {
    ensureQuestXrVisualNodes();
    updateQuestXrVisualVisibility();
    if (isQuestControllerModeActive()) {
      suppressQuestControllerTransition({
        duration_ms: Math.max(220, VR_MODE_TRANSITION_GUARD_MS / 2),
        require_neutral: true,
        clear_queue: true,
      });
    }
  };
  questXrEndedHandler = () => {
    updateQuestXrVisualVisibility();
  };
  session.addEventListener("visibilitychange", questXrVisibilityHandler);
  session.addEventListener("inputsourceschange", questXrInputSourcesHandler);
  session.addEventListener("end", questXrEndedHandler);
}

async function chooseVrInputMode(mode) {
  if (mode !== "controller" && mode !== "hand") return;
  if (!isVrModeEntered.value) {
    vrErrorMessage.value = "请先点击“进入VR模式”，再选择手柄或手势模式。";
    return;
  }
  selectedVrInputMode.value = mode;
  if (!isQuest3Device.value) {
    vrErrorMessage.value = "当前访问端不是 Quest3，建议在 Quest3 浏览器中操作。";
  } else if (!networkPrereqOk.value || !isWebSocketConnected.value) {
    vrErrorMessage.value = "局域网或连接检查未完全通过，已尝试进入模式。";
  } else {
    vrErrorMessage.value = "";
  }

  if (mode === "controller") {
    stopQuestHandLoop();
    suppressQuestControllerTransition({
      duration_ms: VR_MODE_TRANSITION_GUARD_MS,
      require_neutral: true,
      clear_queue: true,
    });
    setVrModeLocally("vr_controller_mode");
    vrControlOwner.value = "quest3_controller";
    vrSelectedJointGroup.value = questControllerTeleop.getState().selected_joint_group;
    syncVrStateToBackend({
      mode: "vr_controller_mode",
      source: "quest3_controller",
      selected_joint_group: vrSelectedJointGroup.value,
      controller_available: true,
      recording_ready: recordingCheckStatus.value === "ok",
      last_quest_input_ts: Date.now() / 1000,
      error_message: "",
    }, { force: true });
    ensureQuestXrVisualNodes();
    updateQuestXrVisualVisibility();
    startQuestControllerLoop();
    return;
  }

  setVrModeLocally("vr_hand_mode");
  vrControlOwner.value = "quest3_hand";
  vrSelectedJointGroup.value = questHandTeleop.getState().selected_joint_group;
  syncVrStateToBackend({
    mode: "vr_hand_mode",
    source: "quest3_hand",
    selected_joint_group: vrSelectedJointGroup.value,
    hand_tracking_available: true,
    recording_ready: recordingCheckStatus.value === "ok",
    last_quest_input_ts: Date.now() / 1000,
    error_message: "",
  }, { force: true });
  ensureQuestXrVisualNodes();
  updateQuestXrVisualVisibility();
  stopQuestControllerLoop();
  await startQuestHandLoop();
}

async function enterVrMode() {
  if (vrEnterInProgress.value) {
    return;
  }
  if (!isQuest3Device.value) {
    vrErrorMessage.value = "当前访问端不是 Quest3，建议在 Quest3 浏览器中操作。";
    return;
  }

  vrEnterInProgress.value = true;
  try {
    const prereqOkAtClick = Boolean(networkPrereqOk.value);
    const preferHandTracking = selectedVrInputMode.value === "hand";
    const xrStatus = await ensureQuestXRSession({ preferHandTracking });
    if (!xrStatus.ready) {
      vrErrorMessage.value = describeVrEnterFailure(xrStatus.reason, xrStatus.detail);
      return;
    }

    const xrSession = getQuestXRSession();
    if (!xrSession || !renderer?.xr || typeof renderer.xr.setSession !== "function") {
      vrErrorMessage.value = "进入VR失败：XR会话已创建，但渲染器XR通道未就绪。";
      await stopQuestXRSession();
      return;
    }

    try {
      await renderer.xr.setSession(xrSession);
    } catch (error) {
      const detail = String(error?.message || "").trim();
      vrErrorMessage.value = detail
        ? `进入VR失败：XR渲染会话绑定失败（${detail}）。`
        : "进入VR失败：XR渲染会话绑定失败。";
      await stopQuestXRSession();
      return;
    }

    attachQuestXrSessionListeners(xrSession);
    ensureQuestXrVisualNodes();
    updateQuestXrVisualVisibility();

    stopQuestControllerLoop();
    stopQuestHandLoop();
    setVrModeLocally("vr_ready");
    vrControlOwner.value = "desktop_manual";
    vrErrorMessage.value = prereqOkAtClick ? "" : "VR已进入；前置检查未全部通过，请关注连接状态。";
    syncVrStateToBackend({
      mode: "vr_ready",
      source: "desktop_manual",
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: recordingCheckStatus.value === "ok",
      error_message: "",
    });

    const autoMode = selectedVrInputMode.value === "hand" ? "hand" : "controller";
    await chooseVrInputMode(autoMode);
    void runQuest3AccessChecks();
  } finally {
    vrEnterInProgress.value = false;
  }
}

function ensureVrModeActive() {
  if (isQuestControllerModeActive() || isQuestHandModeActive()) {
    return;
  }
  const autoMode = selectedVrInputMode.value === "hand" ? "hand" : "controller";
  void chooseVrInputMode(autoMode);
}

function exitVrMode() {
  stopQuestControllerLoop();
  stopQuestHandLoop();
  stopQuestVrControlWatchdog();
  selectedVrInputMode.value = "";
  setVrModeLocally("vr_disabled");
  vrControlOwner.value = "desktop_manual";
  vrErrorMessage.value = "";
  syncVrStateToBackend({
    mode: "vr_disabled",
    source: "desktop_manual",
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: recordingCheckStatus.value === "ok",
    error_message: "",
  });
  detachQuestXrSessionListeners();
  if (renderer?.xr) {
    Promise.resolve(renderer.xr.setSession(null)).catch(() => {});
  }
  void stopQuestXRSession();
  updateQuestXrVisualVisibility();
}

function handleQuestDisconnected() {
  if (vrControlOwner.value !== "quest3_controller" && vrControlOwner.value !== "quest3_hand") {
    return;
  }
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  if (xrPresenting && (isQuestControllerModeActive() || isQuestHandModeActive())) {
    vrErrorMessage.value = "WebSocket中断，已切换HTTP兜底控制；建议重连后继续采集。";
    syncVrStateToBackend({
      mode: vrModeState.value,
      source: vrControlOwner.value,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: false,
      error_message: vrErrorMessage.value,
    });
    return;
  }

  stopQuestControllerLoop();
  stopQuestHandLoop();
  setVrModeLocally("vr_ready");
  selectedVrInputMode.value = "";
  vrErrorMessage.value = "连接中断，已停止控制；XR会话保留，可重连后继续。";
  vrControlOwner.value = "desktop_manual";
  syncVrStateToBackend({
    mode: "vr_ready",
    source: "desktop_manual",
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: recordingCheckStatus.value === "ok",
    error_message: vrErrorMessage.value,
  });
}

function markQuestHandRecordingAnomaly(tag = "hand_tracking_lost") {
  syncVrStateToBackend({
    mode: "vr_hand_mode",
    source: "quest3_hand",
    hand_tracking_available: false,
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: false,
    last_quest_input_ts: Date.now() / 1000,
    error_message: `recording_anomaly:${tag}`,
  });
}

function getCurrentArmRadians() {
  const sourceAngles =
    jointAngles.value.length >= ARM_JOINT_COUNT
      ? jointAngles.value.slice(0, ARM_JOINT_COUNT)
      : DEFAULT_ANGLES_DEG.slice(0, ARM_JOINT_COUNT);
  return sourceAngles.map((deg) => toRadians(deg));
}

function getCurrentGripperRadians() {
  if (robot && robot.joints) {
    const leftDriver = Number(robot.joints.left_driver_joint?.jointValue?.[0]);
    if (Number.isFinite(leftDriver)) {
      return clamp(leftDriver, GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
    }

    const rightDriver = Number(robot.joints.right_driver_joint?.jointValue?.[0]);
    if (Number.isFinite(rightDriver)) {
      return clamp(rightDriver, GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
    }
  }

  return clamp(toRadians(gripperAngleDeg.value), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
}

function toGripperOpening(gripperRadians) {
  return clamp(gripperRadians / GRIPPER_MAX_RAD, 0, 1);
}

function isQuestControllerModeActive() {
  return (
    vrModeState.value === "vr_controller_mode" &&
    (selectedVrInputMode.value === "controller" || vrControlOwner.value === "quest3_controller")
  );
}

function isQuestHandModeActive() {
  return (
    vrModeState.value === "vr_hand_mode" &&
    (selectedVrInputMode.value === "hand" || vrControlOwner.value === "quest3_hand")
  );
}

function rebuildQuestControllerTeleop() {
  questControllerTeleop = createQuestControllerTeleop({
    deadzone: questControllerDeadzone.value,
    joint_step: 0.085 * clamp(questControllerSensitivity.value, 0.4, 1.8),
    max_target_lead_rad: 0.45,
  });
}

function rebuildQuestHandTeleop() {
  questHandTeleop = createQuestHandTeleop({
    sensitivity: clamp(questHandSensitivity.value, 0.4, 1.8),
  });
}

function updateQuestGroupToast(groupLabel) {
  questControllerGroupToast.value = `已切换到${groupLabel}`;
  questControllerGroupToastAt.value = Date.now();
}

function cleanupQuestGroupToast(nowMs = Date.now()) {
  if (!questControllerGroupToast.value) return;
  if (nowMs - Number(questControllerGroupToastAt.value) > 1400) {
    questControllerGroupToast.value = "";
  }
}

function updateQuestHandGroupToast(groupLabel) {
  questHandGroupToast.value = `已切换到${groupLabel}`;
  questHandGroupToastAt.value = Date.now();
}

function cleanupQuestHandGroupToast(nowMs = Date.now()) {
  if (!questHandGroupToast.value) return;
  if (nowMs - Number(questHandGroupToastAt.value) > 1400) {
    questHandGroupToast.value = "";
  }
}

function resetQuestControllerQueuedFlushTimer() {
  if (questControllerQueuedFlushTimer.value) {
    clearTimeout(questControllerQueuedFlushTimer.value);
    questControllerQueuedFlushTimer.value = null;
  }
}

function resetQuestHandQueuedFlushTimer() {
  if (questHandQueuedFlushTimer.value) {
    clearTimeout(questHandQueuedFlushTimer.value);
    questHandQueuedFlushTimer.value = null;
  }
}

function stopQuestVrControlWatchdog() {
  if (questVrControlWatchdogTimer.value) {
    clearInterval(questVrControlWatchdogTimer.value);
    questVrControlWatchdogTimer.value = null;
  }
}

function runQuestVrControlWatchdogTick() {
  const controllerActive = isQuestControllerModeActive();
  const handActive = isQuestHandModeActive();
  if (!controllerActive && !handActive) {
    stopQuestVrControlWatchdog();
    return;
  }

  const nowMs = Date.now();
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  if (
    controllerActive &&
    (!xrPresenting || nowMs - Number(lastQuestControllerTickAt.value || 0) >= VR_CONTROL_WATCHDOG_STALE_MS)
  ) {
    runQuestControllerTick(nowMs);
  }
  if (
    handActive &&
    (!xrPresenting || nowMs - Number(lastQuestHandTickAt.value || 0) >= VR_CONTROL_WATCHDOG_STALE_MS)
  ) {
    runQuestHandTick(nowMs);
  }
}

function startQuestVrControlWatchdog() {
  if (questVrControlWatchdogTimer.value) return;
  questVrControlWatchdogTimer.value = setInterval(
    runQuestVrControlWatchdogTick,
    VR_CONTROL_WATCHDOG_INTERVAL_MS
  );
}

function scheduleQuestControllerQueuedFlush(delayMs = VR_COMMAND_MIN_INTERVAL_MS) {
  resetQuestControllerQueuedFlushTimer();
  const timeoutMs = clamp(Number(delayMs) || 0, 0, VR_COMMAND_MIN_INTERVAL_MS);
  questControllerQueuedFlushTimer.value = setTimeout(() => {
    questControllerQueuedFlushTimer.value = null;
    flushQueuedQuestControlCommand();
  }, timeoutMs);
}

function scheduleQuestHandQueuedFlush(delayMs = VR_COMMAND_MIN_INTERVAL_MS) {
  resetQuestHandQueuedFlushTimer();
  const timeoutMs = clamp(Number(delayMs) || 0, 0, VR_COMMAND_MIN_INTERVAL_MS);
  questHandQueuedFlushTimer.value = setTimeout(() => {
    questHandQueuedFlushTimer.value = null;
    flushQueuedQuestHandControlCommand();
  }, timeoutMs);
}

function buildQuestControlPayload(mapped) {
  questControllerControlSeq.value += 1;
  return {
    target_positions: mapped.target_positions,
    n_steps: VR_COMMAND_STEPS,
    control_mode: "position",
    expect_result: false,
    gripper_command: { mode: "open_close", value: mapped.gripper_opening },
    source: "quest3_controller",
    input_source: "quest3_controller",
    selected_joint_group: mapped.selected_joint_group,
    raw_input: mapped.raw_input || null,
    normalized_input: {
      ...(mapped.normalized_input || {}),
      control_seq: Number(questControllerControlSeq.value),
    },
  };
}

function buildQuestHandControlPayload(mapped) {
  questHandControlSeq.value += 1;
  return {
    target_positions: mapped.target_positions || null,
    target_ee_pose: mapped.target_ee_pose || null,
    n_steps: VR_COMMAND_STEPS,
    control_mode: mapped.control_mode || (mapped.target_ee_pose ? "ik_pose" : "position"),
    expect_result: false,
    gripper_command: { mode: "open_close", value: mapped.gripper_opening },
    source: "quest3_hand",
    input_source: "quest3_hand",
    selected_joint_group: mapped.selected_joint_group,
    raw_input: mapped.raw_input || null,
    normalized_input: {
      ...(mapped.normalized_input || {}),
      tracking_stability: mapped.tracking_stability,
      hand_input_mode: mapped.hand_input_mode,
      control_seq: Number(questHandControlSeq.value),
    },
  };
}

function stageQuestRenderTarget(payload) {
  const arm = Array.isArray(payload?.target_positions)
    ? payload.target_positions.slice(0, ARM_JOINT_COUNT).map((value) => Number(value))
    : null;
  if (!arm || arm.length < ARM_JOINT_COUNT || arm.some((value) => !Number.isFinite(value))) {
    return;
  }

  const gripperOpening = Number.isFinite(Number(payload?.gripper_command?.value))
    ? clamp(Number(payload.gripper_command.value), 0, 1)
    : getAuthoritativeGripperOpening();
  const target = {
    timestamp: Date.now(),
    arm,
    gripper: gripperOpening * GRIPPER_MAX_RAD,
  };
  questRenderPreviewTarget.value = target;
  backendRenderTarget.value = target;
}

function applyQuestCommandLocally(payload = {}) {
  clearPendingManualTarget();
  if (payload?.control_mode === "ik_pose" || payload?.target_ee_pose) {
    clearQuestRenderPreview();
    return;
  }
  stageQuestRenderTarget(payload);
}

async function sendQuestControlByHttp(payload) {
  if (questControllerFallbackInFlight.value) return;
  questControllerFallbackInFlight.value = true;
  try {
    const resp = await post("/sim/step/", payload);
    if (resp?.data?.state) {
      commitQuestControlStateSnapshot(resp.data.state);
    }
  } catch (error) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
    questControllerStatusText.value = "手柄控制HTTP发送失败";
    console.warn("Quest3手柄HTTP控制发送失败:", error?.message || error);
  } finally {
    questControllerFallbackInFlight.value = false;
    flushQueuedQuestControlCommand();
  }
}

function sendQuestControlPayload(payload) {
  if (!payload || typeof payload !== "object") return;
  lastQuestControllerSentAt.value = Date.now();
  applyQuestCommandLocally(payload);

  if (websocketManager.isConnected) {
    const sent = websocketManager.sendControlCommand(payload.target_positions, payload);
    if (sent) return;
  }

  sendQuestControlByHttp(payload);
}

function flushQueuedQuestControlCommand() {
  const queued = questControllerPendingMapped.value;
  if (!queued?.has_command) return;
  questControllerPendingMapped.value = null;
  sendQuestControlToBackend(queued);
}

function sendQuestControlToBackend(mapped) {
  if (!mapped?.has_command) return;
  if (!websocketManager.isConnected && questControllerFallbackInFlight.value) {
    questControllerPendingMapped.value = mapped;
    scheduleQuestControllerQueuedFlush(VR_COMMAND_MIN_INTERVAL_MS);
    return;
  }

  const now = Date.now();
  const elapsed = now - Number(lastQuestControllerSentAt.value || 0);
  if (elapsed < VR_COMMAND_MIN_INTERVAL_MS) {
    questControllerPendingMapped.value = mapped;
    scheduleQuestControllerQueuedFlush(VR_COMMAND_MIN_INTERVAL_MS - elapsed);
    return;
  }

  resetQuestControllerQueuedFlushTimer();
  questControllerPendingMapped.value = null;
  const payload = buildQuestControlPayload(mapped);
  sendQuestControlPayload(payload);
}

function applyQuestSafetyHoldState() {
  markQuestHandRecordingAnomaly("tracking_unstable");
  syncVrStateToBackend({
    mode: "vr_hand_mode",
    source: "quest3_hand",
    hand_tracking_available: false,
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: recordingCheckStatus.value === "ok",
    last_quest_input_ts: Date.now() / 1000,
    error_message: "手势追踪不稳定，已进入安全保持状态",
  });
}

async function sendQuestHandControlByHttp(payload) {
  if (questHandFallbackInFlight.value) return;
  questHandFallbackInFlight.value = true;
  try {
    const resp = await post("/sim/step/", payload);
    if (resp?.data?.state) {
      commitQuestControlStateSnapshot(resp.data.state);
    }
  } catch (error) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
    questHandStatusText.value = "手势控制HTTP发送失败";
    console.warn("Quest3手势HTTP控制发送失败:", error?.message || error);
  } finally {
    questHandFallbackInFlight.value = false;
    flushQueuedQuestHandControlCommand();
  }
}

function sendQuestHandControlPayload(payload) {
  if (!payload || typeof payload !== "object") return;
  lastQuestHandSentAt.value = Date.now();
  applyQuestCommandLocally(payload);

  if (websocketManager.isConnected) {
    const sent = websocketManager.sendControlCommand(payload.target_positions, payload);
    if (sent) return;
  }
  sendQuestHandControlByHttp(payload);
}

function flushQueuedQuestHandControlCommand() {
  const queued = questHandPendingMapped.value;
  if (!queued?.has_command) return;
  questHandPendingMapped.value = null;
  sendQuestHandControlToBackend(queued);
}

function sendQuestHandControlToBackend(mapped) {
  if (!mapped?.has_command) return;
  if (!websocketManager.isConnected && questHandFallbackInFlight.value) {
    questHandPendingMapped.value = mapped;
    scheduleQuestHandQueuedFlush(VR_COMMAND_MIN_INTERVAL_MS);
    return;
  }

  const now = Date.now();
  const elapsed = now - Number(lastQuestHandSentAt.value || 0);
  if (elapsed < VR_COMMAND_MIN_INTERVAL_MS) {
    questHandPendingMapped.value = mapped;
    scheduleQuestHandQueuedFlush(VR_COMMAND_MIN_INTERVAL_MS - elapsed);
    return;
  }

  resetQuestHandQueuedFlushTimer();
  questHandPendingMapped.value = null;
  const payload = buildQuestHandControlPayload(mapped);
  sendQuestHandControlPayload(payload);
}

function runQuestControllerTick(nowOverrideMs = Date.now()) {
  cleanupQuestGroupToast();
  if (!isQuestControllerModeActive()) {
    questControllerAvailable.value = false;
    questControllerStatusText.value = "未激活";
    return;
  }

  const nowMs = Number.isFinite(Number(nowOverrideMs))
    ? Number(nowOverrideMs)
    : Date.now();
  const prevTickAt = Number(lastQuestControllerTickAt.value) || nowMs;
  const dtSec = clamp((nowMs - prevTickAt) / 1000, 1 / 120, 1 / 10);
  lastQuestControllerTickAt.value = nowMs;

  const snapshot = readQuestControllerSnapshot() || {
    available: true,
    has_device: false,
    reason: "idle",
    timestamp_ms: nowMs,
    controls: {
      select_upper_arm: 0,
      select_forearm: 0,
      select_wrist: 0,
      precision: 0,
      stick_x: 0,
      stick_y: 0,
      trigger: 0,
    },
    raw: null,
  };
  questControllerRawInput.value = snapshot?.raw || null;
  questControllerAvailable.value = true;
  questControllerStatusText.value = snapshot?.has_device ? "采样中" : "运行中(等待输入)";

  const mapped = questControllerTeleop.applySnapshot(
    snapshot,
    getAuthoritativeArmRadians(),
    getAuthoritativeGripperOpening(),
    dtSec
  );

  if (mapped?.selected_joint_group) {
    if (vrSelectedJointGroup.value !== mapped.selected_joint_group) {
      updateQuestGroupToast(mapped.selected_joint_group_label || mapped.selected_joint_group);
    }
    vrSelectedJointGroup.value = mapped.selected_joint_group;
  }

  syncVrStateToBackend({
    mode: "vr_controller_mode",
    source: "quest3_controller",
    controller_available: true,
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: recordingCheckStatus.value === "ok",
    last_quest_input_ts: nowMs / 1000,
    raw_input: mapped?.raw_input || snapshot?.raw || null,
    normalized_input: {
      ...(mapped?.normalized_input || {}),
      has_command: mapped?.has_command ? 1 : 0,
      reason: mapped?.reason || snapshot?.reason || "idle",
      has_device: snapshot?.has_device ? 1 : 0,
      timestamp_ms: Number(snapshot?.timestamp_ms) || nowMs,
    },
    error_message: "",
  });

  if (mapped?.reason === "control_guard") {
    questControllerStatusText.value = "输入保护中";
    return;
  }

  if (mapped?.has_command) {
    sendQuestControlToBackend(mapped);
  }
}

function markQuestHandSafeHold(reasonText, anomalyTag = "tracking_unstable") {
  questHandAvailable.value = false;
  questHandTrackingStable.value = false;
  questHandStatusText.value = reasonText;
  markQuestHandRecordingAnomaly(anomalyTag);
  applyQuestSafetyHoldState();
}

function runQuestHandTick(nowOverrideMs = Date.now()) {
  cleanupQuestHandGroupToast();
  if (!isQuestHandModeActive()) {
    questHandAvailable.value = false;
    questHandStatusText.value = "未激活";
    return;
  }

  const status = getQuestHandInputStatus();
  const nowMs = Number.isFinite(Number(nowOverrideMs))
    ? Number(nowOverrideMs)
    : Date.now();
  const prevTickAt = Number(lastQuestHandTickAt.value) || nowMs;
  const dtSec = clamp((nowMs - prevTickAt) / 1000, 1 / 120, 1 / 10);
  lastQuestHandTickAt.value = nowMs;

  if (!status.ready) {
    markQuestHandSafeHold("手势会话未就绪", "session_not_ready");
    return;
  }

  const snapshot = readQuestHandSnapshot();
  questHandRawInput.value = snapshot?.raw || null;
  questHandTrackingStability.value = clamp(snapshot?.tracking_stability || 0, 0, 1);

  if (!snapshot?.available) {
    if (questHandUnavailableSinceAt.value <= 0) {
      questHandUnavailableSinceAt.value = nowMs;
    }
    const unavailableElapsed = nowMs - Number(questHandUnavailableSinceAt.value || nowMs);
    syncVrStateToBackend({
      mode: "vr_hand_mode",
      source: "quest3_hand",
      hand_tracking_available: false,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: recordingCheckStatus.value === "ok",
      last_quest_input_ts: nowMs / 1000,
      raw_input: snapshot?.raw || null,
      normalized_input: {
        has_command: 0,
        reason: snapshot?.reason || "hand_not_tracked",
        tracking_stable: 0,
        tracking_stability: clamp(snapshot?.tracking_stability || 0, 0, 1),
      },
      error_message: "",
    });
    if (unavailableElapsed < QUEST_HAND_UNAVAILABLE_GRACE_MS) {
      questHandAvailable.value = true;
      questHandTrackingStable.value = false;
      questHandStatusText.value = "手势短暂波动，保持上一控制";
      return;
    }
    markQuestHandSafeHold("未检测到稳定手势", "hand_not_tracked");
    return;
  }
  questHandUnavailableSinceAt.value = 0;

  questHandAvailable.value = true;
  questHandStatusText.value = "采样中";
  const mapped = questHandTeleop.applySnapshot(
    snapshot,
    getAuthoritativeArmRadians(),
    getAuthoritativeGripperOpening(),
    getAuthoritativeEePoseBackend(),
    dtSec
  );

  questHandTrackingStable.value = Boolean(mapped?.tracking_stable);
  questHandInputMode.value = mapped?.hand_input_mode || "left_hand_ee_ik";
  questHandStatusText.value = buildHandTrackingStatusText();

  if (!mapped?.tracking_stable) {
    syncVrStateToBackend({
      mode: "vr_hand_mode",
      source: "quest3_hand",
      hand_tracking_available: true,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: recordingCheckStatus.value === "ok",
      last_quest_input_ts: nowMs / 1000,
      raw_input: mapped?.raw_input || snapshot?.raw || null,
      normalized_input: {
        ...(mapped?.normalized_input || {}),
        has_command: 0,
        reason: mapped?.reason || "tracking_unstable",
        tracking_stable: 0,
        tracking_stability: mapped?.tracking_stability ?? clamp(snapshot?.tracking_stability || 0, 0, 1),
        hand_input_mode: mapped?.hand_input_mode || questHandInputMode.value,
      },
      error_message: "",
    });
    if (questHandUnstableSinceAt.value <= 0) {
      questHandUnstableSinceAt.value = nowMs;
    }
    const unstableElapsed = nowMs - Number(questHandUnstableSinceAt.value || nowMs);
    if (unstableElapsed < QUEST_HAND_UNSTABLE_GRACE_MS) {
      questHandTrackingStable.value = false;
      questHandStatusText.value = "追踪短暂抖动，保持上一控制";
      return;
    }
    markQuestHandSafeHold("追踪不稳定(已保持)", "tracking_unstable");
    return;
  }
  questHandUnstableSinceAt.value = 0;

  if (mapped?.selected_joint_group) {
    if (vrSelectedJointGroup.value !== mapped.selected_joint_group) {
      updateQuestHandGroupToast(mapped.selected_joint_group_label || mapped.selected_joint_group);
    }
    vrSelectedJointGroup.value = mapped.selected_joint_group;
  }

  syncVrStateToBackend({
    mode: "vr_hand_mode",
    source: "quest3_hand",
    hand_tracking_available: true,
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: recordingCheckStatus.value === "ok",
    last_quest_input_ts: nowMs / 1000,
    raw_input: mapped?.raw_input || snapshot?.raw || null,
    normalized_input: {
      ...(mapped?.normalized_input || {}),
      has_command: mapped?.has_command ? 1 : 0,
      reason: mapped?.reason || "idle",
      tracking_stable: mapped?.tracking_stable ? 1 : 0,
      tracking_stability: mapped?.tracking_stability ?? clamp(snapshot?.tracking_stability || 0, 0, 1),
      hand_input_mode: mapped?.hand_input_mode || questHandInputMode.value,
      timestamp_ms: Number(snapshot?.timestamp_ms) || nowMs,
    },
    error_message: "",
  });

  if (mapped?.has_command) {
    sendQuestHandControlToBackend(mapped);
  }
}

function runQuestVrControlFrame() {
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  if (!xrPresenting) {
    updateQuestXrVisualVisibility();
    return;
  }

  ensureQuestXrVisualNodes();
  updateQuestXrVisualVisibility();

  const nowMs = Date.now();
  if (isQuestControllerModeActive()) {
    runQuestControllerTick(nowMs);
  }
  if (isQuestHandModeActive()) {
    runQuestHandTick(nowMs);
  }
}

function handleQuestGamepadConnectionEvent(event) {
  if (!isQuestControllerModeActive()) return;
  if (event?.type === "gamepadconnected") {
    questControllerStatusText.value = "手柄已连接";
  } else if (event?.type === "gamepaddisconnected") {
    questControllerStatusText.value = "手柄已断开(可继续)";
  }
}

function startQuestControllerLoop() {
  stopQuestControllerLoop();
  rebuildQuestControllerTeleop();
  suppressQuestControllerTransition({
    duration_ms: VR_MODE_TRANSITION_GUARD_MS,
    require_neutral: true,
    clear_queue: true,
  });
  questControllerAvailable.value = false;
  questControllerStatusText.value = "启动中";
  lastQuestControllerTickAt.value = Date.now();
  runQuestControllerTick(Date.now());
  startQuestVrControlWatchdog();
}

async function startQuestHandLoop() {
  stopQuestHandLoop();
  rebuildQuestHandTeleop();
  await startQuestHandInput({ preferHandTracking: true });
  questHandAvailable.value = false;
  questHandStatusText.value = "启动中";
  lastQuestHandTickAt.value = Date.now();
  runQuestHandTick(Date.now());
  startQuestVrControlWatchdog();
}

function stopQuestControllerLoop() {
  if (questControllerTeleop && typeof questControllerTeleop.reset === "function") {
    questControllerTeleop.reset({ preserve_group: true });
  }
  questControllerAvailable.value = false;
  questControllerStatusText.value = "未激活";
  questControllerRawInput.value = null;
  questControllerPendingMapped.value = null;
  lastQuestControllerSentAt.value = 0;
  resetQuestControllerQueuedFlushTimer();
  questControllerGroupToast.value = "";
  questControllerGroupToastAt.value = 0;
  lastQuestControllerTickAt.value = 0;
  clearQuestRenderPreview();
}

function stopQuestHandLoop() {
  stopQuestHandInput();
  questHandTeleop.reset();
  questHandAvailable.value = false;
  questHandStatusText.value = "未激活";
  questHandTrackingStable.value = false;
  questHandTrackingStability.value = 0;
  questHandInputMode.value = "left_hand_ee_ik";
  questHandRawInput.value = null;
  questHandPendingMapped.value = null;
  lastQuestHandSentAt.value = 0;
  questHandUnstableSinceAt.value = 0;
  questHandUnavailableSinceAt.value = 0;
  resetQuestHandQueuedFlushTimer();
  questHandGroupToast.value = "";
  questHandGroupToastAt.value = 0;
  lastQuestHandTickAt.value = 0;
  clearQuestRenderPreview();
}

function buildHandTrackingStatusText() {
  if (!questHandAvailable.value) return "未检测到稳定手势";
  if (!questHandTrackingStable.value) return "追踪不稳定(已保持)";
  const modeText = questHandInputMode.value === "left_hand_ee_ik"
    ? "左手末端IK"
    : questHandInputMode.value === "left_hand"
      ? "左手单手"
      : questHandInputMode.value === "dual_hand"
        ? "双手"
        : "单手";
  return `采样中(${modeText})`;
}

function buildGripperCommand(options = {}) {
  if (options.gripper_command && typeof options.gripper_command === "object") {
    const commandValue = Number(options.gripper_command.value);
    return {
      mode: "open_close",
      value: Number.isFinite(commandValue)
        ? clamp(commandValue, 0, 1)
        : getAuthoritativeGripperOpening(),
    };
  }

  if (Number.isFinite(Number(options.gripper_opening))) {
    const opening = Number(options.gripper_opening);
    return {
      mode: "open_close",
      value: clamp(opening, 0, 1),
    };
  }

  return {
    mode: "open_close",
    value: getAuthoritativeGripperOpening(),
  };
}

function rememberPendingManualTarget(armRadians, gripperOpening, options = {}) {
  if (!Array.isArray(armRadians) || armRadians.length < ARM_JOINT_COUNT) {
    pendingManualTarget.value = null;
    return;
  }

  const opening = Number.isFinite(Number(gripperOpening))
    ? clamp(Number(gripperOpening), 0, 1)
    : toGripperOpening(getCurrentGripperRadians());

  pendingManualTarget.value = {
    sentAt: Date.now(),
    arm: armRadians.slice(0, ARM_JOINT_COUNT).map((v) => Number(v)),
    gripper: opening * GRIPPER_MAX_RAD,
  };

  if (options.updateRenderTarget === true) {
    backendRenderTarget.value = {
      timestamp: pendingManualTarget.value.sentAt,
      arm: [...pendingManualTarget.value.arm],
      gripper: pendingManualTarget.value.gripper,
    };
  }
}

function clearPendingManualTarget() {
  pendingManualTarget.value = null;
}

function clearRealtimeSliderDraft() {
  realtimeSliderDraft.value = null;
}

function clearQuestRenderPreview() {
  questRenderPreviewTarget.value = null;
}

function getFreshQuestRenderPreview() {
  const preview = questRenderPreviewTarget.value;
  if (!preview || typeof preview !== "object") return null;
  if (Date.now() - Number(preview.timestamp || 0) > QUEST_RENDER_PREVIEW_TTL_MS) {
    clearQuestRenderPreview();
    return null;
  }
  return preview;
}

function getBackendStateTimestampMs(state) {
  if (!state || typeof state !== "object") return null;
  const raw = Number(state.timestamp);
  if (!Number.isFinite(raw)) return null;
  // Backend emits seconds; convert to ms.
  return raw * 1000;
}

function formatCollisionContacts(contacts) {
  if (!Array.isArray(contacts) || contacts.length === 0) return "";
  return contacts
    .slice(0, 3)
    .map((contact) => {
      const bodyA = String(contact?.body_a || "unknown");
      const bodyB = String(contact?.body_b || "unknown");
      const depthMm = Math.abs(Number(contact?.dist) || 0) * 1000;
      return `${bodyA}<->${bodyB} ${depthMm.toFixed(1)}mm`;
    })
    .join(", ");
}

function updateSafetyFeedbackFromState(state) {
  if (!state || typeof state !== "object") return;
  if (!state.collision_blocked) return;

  clearPendingManualTarget();
  clearQuestRenderPreview();
  const contactText = formatCollisionContacts(state.collision_contacts);
  receivedText.value = contactText
    ? `物理拦截：检测到穿模/干涉，已保持最近安全状态(${contactText})`
    : "物理拦截：检测到穿模/干涉，已保持最近安全状态";
}

function acceptBackendStateTimestamp(state) {
  const timestampMs = getBackendStateTimestampMs(state);
  if (!Number.isFinite(Number(timestampMs))) return true;

  const lastTimestampMs = Number(lastAcceptedBackendStateTimestampMs.value || 0);
  if (
    lastTimestampMs > 0 &&
    Number(timestampMs) + BACKEND_STATE_TIMESTAMP_EPSILON_MS < lastTimestampMs
  ) {
    return false;
  }

  if (Number(timestampMs) > lastTimestampMs) {
    lastAcceptedBackendStateTimestampMs.value = Number(timestampMs);
  }
  return true;
}

function commitBackendStateSnapshot(state, options = {}) {
  if (!state || typeof state !== "object") return false;
  if (!acceptBackendStateTimestamp(state)) return false;

  simulationState.value = state;
  lastStateUpdate.value = Date.now();
  updateSafetyFeedbackFromState(state);
  applyBackendStateToScene(state, { immediate: true });
  if (options.clearPendingManualTarget === true) {
    clearPendingManualTarget();
  }
  return true;
}

function isQuestControlBackendState(state) {
  const source = String(state?.source || state?.input_source || state?.vr?.control_owner || "").trim();
  return source === "quest3_controller" || source === "quest3_hand";
}

function commitQuestControlStateSnapshot(state, nowMs = Date.now()) {
  if (!state || typeof state !== "object") return false;
  if (!acceptBackendStateTimestamp(state)) return false;

  clearPendingManualTarget();
  simulationState.value = state;
  applyVrStateFromBackend(state);
  checkD405ObservationReady(state);
  checkRecordingBindingReady(state);
  checkWebSocketReady();
  updateNetworkPrereq();
  updateSafetyFeedbackFromState(state);
  clearQuestRenderPreview();
  applyBackendStateToScene(state);

  lastStateUpdate.value = nowMs;
  return true;
}

function isBackendStateAlignedWithPendingTarget(state) {
  const pending = pendingManualTarget.value;
  if (!pending || !Array.isArray(state?.qpos) || state.qpos.length < ARM_JOINT_COUNT) {
    return true;
  }

  const incomingJointNames = Array.isArray(state?.joint_names)
    ? state.joint_names.map((name) => String(name))
    : [];

  let maxArmError = 0;
  for (let i = 0; i < ARM_JOINT_COUNT; i++) {
    let backendValue = Number(state.qpos[i]);
    if (incomingJointNames.length > 0) {
      const expectedName = BACKEND_ARM_JOINT_NAMES[i];
      const incomingIndex = incomingJointNames.indexOf(expectedName);
      if (incomingIndex >= 0) {
        const mappedValue = Number(state.qpos[incomingIndex]);
        if (Number.isFinite(mappedValue)) {
          backendValue = mappedValue;
        }
      }
    }
    if (!Number.isFinite(backendValue)) continue;
    const error = Math.abs(backendValue - pending.arm[i]);
    if (error > maxArmError) maxArmError = error;
  }

  const backendGripper = getGripperRadiansFromBackendState(state);
  const gripperError =
    backendGripper === null ? 0 : Math.abs(Number(backendGripper) - Number(pending.gripper));

  return maxArmError <= ARM_STATE_MATCH_THRESHOLD_RAD && gripperError <= GRIPPER_STATE_MATCH_THRESHOLD_RAD;
}

function shouldApplyIncomingBackendState(state, nowMs = Date.now()) {
  const pending = pendingManualTarget.value;
  if (!pending) return true;
  if (isQuestControlBackendState(state)) {
    clearPendingManualTarget();
    return true;
  }

  const backendStateTimestampMs = getBackendStateTimestampMs(state);
  if (
    Number.isFinite(Number(backendStateTimestampMs)) &&
    Number(backendStateTimestampMs) + BACKEND_STATE_STALE_TOLERANCE_MS < Number(pending.sentAt)
  ) {
    return false;
  }

  if (
    typeof state?.source === "string" &&
    state.source.length > 0 &&
    !LOCAL_MANUAL_SOURCES.has(state.source) &&
    Number.isFinite(Number(backendStateTimestampMs)) &&
    Number(backendStateTimestampMs) + BACKEND_STATE_STALE_TOLERANCE_MS >= Number(pending.sentAt)
  ) {
    clearPendingManualTarget();
    return true;
  }

  const source = String(state?.source || "").trim();
  const isVrSource = source === "quest3_controller" || source === "quest3_hand";
  const guardMs = isVrSource ? VR_MANUAL_STATE_GUARD_MS : MANUAL_STATE_GUARD_MS;

  if (nowMs - Number(pending.sentAt) > guardMs) {
    clearPendingManualTarget();
    return true;
  }

  if (isBackendStateAlignedWithPendingTarget(state)) {
    clearPendingManualTarget();
    return true;
  }

  return false;
}

function normalizeInputAngles(values) {
  if (!Array.isArray(values)) return null;

  const parsed = values.map((v) => Number(v));
  if (parsed.length === ARM_JOINT_COUNT) {
    parsed.push(gripperAngleDeg.value);
  }

  if (
    parsed.length !== TOTAL_INPUT_JOINT_COUNT ||
    parsed.some((value) => !Number.isFinite(value))
  ) {
    return null;
  }

  parsed[ARM_JOINT_COUNT] = clamp(
    parsed[ARM_JOINT_COUNT],
    GRIPPER_MIN_DEG,
    GRIPPER_MAX_DEG
  );

  return parsed;
}

function ensureJointAnglesBuffer() {
  if (!Array.isArray(jointAngles.value) || jointAngles.value.length < TOTAL_INPUT_JOINT_COUNT) {
    jointAngles.value = [...DEFAULT_ANGLES_DEG];
  }
}

function parseAngleText(inputText) {
  const rawAngles = inputText
    .split(",")
    .map((angle) => parseFloat(angle.trim()));
  return normalizeInputAngles(rawAngles);
}

function getGripperDegFromQpos(qpos) {
  if (!Array.isArray(qpos) || qpos.length <= ARM_JOINT_COUNT) {
    return gripperAngleDeg.value;
  }

  const qposValue = Number(qpos[ARM_JOINT_COUNT]);
  if (!Number.isFinite(qposValue)) return gripperAngleDeg.value;

  return clamp(toDegrees(qposValue), GRIPPER_MIN_DEG, GRIPPER_MAX_DEG);
}

function getGripperRadiansFromBackendState(state) {
  if (!state || typeof state !== "object") return null;

  if (Number.isFinite(Number(state.gripper_opening))) {
    return clamp(Number(state.gripper_opening), 0, 1) * GRIPPER_MAX_RAD;
  }

  const driver = state?.gripper_joints?.left_driver_joint;
  if (Number.isFinite(Number(driver))) {
    return clamp(Number(driver), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
  }

  if (Array.isArray(state.qpos) && Number.isFinite(Number(state.qpos[ARM_JOINT_COUNT]))) {
    return clamp(Number(state.qpos[ARM_JOINT_COUNT]), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
  }

  return null;
}

function backendPositionToFrontend(position) {
  if (!Array.isArray(position) || position.length < 3) {
    return null;
  }

  const [xMj, yMj, zMj] = position.map((v) => Number(v));
  if (![xMj, yMj, zMj].every((v) => Number.isFinite(v))) {
    return null;
  }

  return [xMj, zMj - BACKEND_FRAME_Z_OFFSET, -yMj];
}

function backendQuaternionToFrontend(quaternionWXYZ) {
  if (!Array.isArray(quaternionWXYZ) || quaternionWXYZ.length < 4) {
    return null;
  }

  const [w, x, y, z] = quaternionWXYZ.map((v) => Number(v));
  if (![w, x, y, z].every((v) => Number.isFinite(v))) {
    return null;
  }

  const qBackend = new THREE.Quaternion(x, y, z, w);
  return BACKEND_TO_FRONTEND_ROT.clone().multiply(qBackend).normalize();
}

function frontendPositionToBackend(position) {
  if (!Array.isArray(position) || position.length < 3) {
    return null;
  }

  const [xFront, yFront, zFront] = position.map((v) => Number(v));
  if (![xFront, yFront, zFront].every((v) => Number.isFinite(v))) {
    return null;
  }

  return [xFront, -zFront, yFront + BACKEND_FRAME_Z_OFFSET];
}

function frontendQuaternionToBackend(quaternionXYZW) {
  if (!quaternionXYZW) return null;
  const qFrontend =
    quaternionXYZW instanceof THREE.Quaternion
      ? quaternionXYZW.clone()
      : Array.isArray(quaternionXYZW) && quaternionXYZW.length >= 4
        ? new THREE.Quaternion(
            Number(quaternionXYZW[0]),
            Number(quaternionXYZW[1]),
            Number(quaternionXYZW[2]),
            Number(quaternionXYZW[3])
          )
        : null;
  if (!qFrontend) return null;
  const qBackend = BACKEND_TO_FRONTEND_ROT.clone().invert().multiply(qFrontend).normalize();
  return [qBackend.w, qBackend.x, qBackend.y, qBackend.z];
}

function normalizeBackendEePose(pose) {
  if (!pose || typeof pose !== "object") return null;
  const position = Array.isArray(pose.position)
    ? pose.position.slice(0, 3).map((value) => Number(value))
    : null;
  const quaternion = Array.isArray(pose.quaternion)
    ? pose.quaternion.slice(0, 4).map((value) => Number(value))
    : null;
  if (
    !position ||
    !quaternion ||
    position.some((value) => !Number.isFinite(value)) ||
    quaternion.some((value) => !Number.isFinite(value))
  ) {
    return null;
  }
  return { position, quaternion };
}

function getCurrentSceneEePoseBackend() {
  if (!robot || !robot.links) return null;
  const endEffector = robot.links.tool0 || robot.links.wrist_3_link;
  if (!endEffector) return null;

  const worldPosition = new THREE.Vector3();
  const worldQuaternion = new THREE.Quaternion();
  endEffector.getWorldPosition(worldPosition);
  endEffector.getWorldQuaternion(worldQuaternion);

  const position = frontendPositionToBackend([
    worldPosition.x,
    worldPosition.y,
    worldPosition.z,
  ]);
  const quaternion = frontendQuaternionToBackend(worldQuaternion);
  if (!position || !quaternion) return null;
  return { position, quaternion };
}

function getAuthoritativeEePoseBackend() {
  const backendPose = normalizeBackendEePose(simulationState.value?.ee_pose);
  if (backendPose) return backendPose;
  return getCurrentSceneEePoseBackend();
}

function getBackendArmRadiansFromState(state) {
  if (!state || typeof state !== "object") return null;
  if (!Array.isArray(state.qpos) || state.qpos.length < ARM_JOINT_COUNT) return null;

  const incomingJointNames = Array.isArray(state.joint_names)
    ? state.joint_names.map((name) => String(name))
    : [];

  const armRadians = BACKEND_ARM_JOINT_NAMES.map((jointName, index) => {
    if (incomingJointNames.length > 0) {
      const incomingIndex = incomingJointNames.indexOf(jointName);
      if (incomingIndex >= 0) {
        const mappedValue = Number(state.qpos[incomingIndex]);
        if (Number.isFinite(mappedValue)) return mappedValue;
      }
    }
    const fallback = Number(state.qpos[index]);
    return Number.isFinite(fallback) ? fallback : 0;
  });

  return armRadians.every((value) => Number.isFinite(value)) ? armRadians : null;
}

function getLatestBackendArmRadians() {
  const arm = getBackendArmRadiansFromState(simulationState.value);
  return Array.isArray(arm) && arm.length >= ARM_JOINT_COUNT ? arm : null;
}

function getAuthoritativeArmRadians() {
  const pending = pendingManualTarget.value;
  if (Array.isArray(pending?.arm) && pending.arm.length >= ARM_JOINT_COUNT) {
    return pending.arm.slice(0, ARM_JOINT_COUNT);
  }
  const backendArm = getLatestBackendArmRadians();
  return backendArm || getCurrentSceneArmRadians();
}

function getLatestBackendGripperRadians() {
  const gripperRadians = getGripperRadiansFromBackendState(simulationState.value);
  return gripperRadians === null ? null : gripperRadians;
}

function getAuthoritativeGripperOpening() {
  const pending = pendingManualTarget.value;
  if (Number.isFinite(Number(pending?.gripper))) {
    return toGripperOpening(Number(pending.gripper));
  }
  const backendGripper = getLatestBackendGripperRadians();
  if (backendGripper !== null) {
    return toGripperOpening(backendGripper);
  }
  return toGripperOpening(getCurrentGripperRadians());
}

function buildBackendRenderTarget(state) {
  const armRadians = getBackendArmRadiansFromState(state);
  if (!armRadians) return null;

  const gripperRadians = getGripperRadiansFromBackendState(state);
  const clampedGripper =
    gripperRadians === null
      ? clamp(getCurrentGripperRadians(), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD)
      : clamp(Number(gripperRadians), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);

  return {
    timestamp: Date.now(),
    arm: armRadians,
    gripper: clampedGripper,
  };
}

function getCurrentSceneArmRadians() {
  if (!robot || !robot.joints) {
    return getCurrentArmRadians();
  }

  return BACKEND_ARM_JOINT_NAMES.map((jointName, index) => {
    const joint = robot.joints[jointName];
    const value = Number(joint?.jointValue?.[0]);
    if (Number.isFinite(value)) return value;
    return toRadians(jointAngles.value?.[index] ?? DEFAULT_ANGLES_DEG[index]);
  });
}

function shouldSyncUiSnapshot(lastAtRef, intervalMs, force = false) {
  if (force) {
    lastAtRef.value = Date.now();
    return true;
  }
  const now = Date.now();
  const lastAt = Number(lastAtRef.value || 0);
  if (now - lastAt < intervalMs) {
    return false;
  }
  lastAtRef.value = now;
  return true;
}

function syncJointDisplayFromSceneIfNeeded(force = false) {
  if (!shouldSyncUiSnapshot(uiLastJointSyncAt, UI_SYNC_INTERVAL_MS, force)) return;
  const armRadians = getCurrentSceneArmRadians();
  const gripperRadians = clamp(getCurrentGripperRadians(), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
  const armAnglesDeg = armRadians.map((rad) => toDegrees(rad));
  const gripperDeg = clamp(toDegrees(gripperRadians), GRIPPER_MIN_DEG, GRIPPER_MAX_DEG);
  jointAngles.value = [...armAnglesDeg, gripperDeg];
  gripperAngleDeg.value = gripperDeg;
}

function syncEndEffectorPoseIfNeeded(force = false) {
  if (!shouldSyncUiSnapshot(uiLastPoseSyncAt, UI_POSE_SYNC_INTERVAL_MS, force)) return;
  calculateEndEffectorPosition();
}

function getSceneJointInterpolationAlpha() {
  if (isVrModeEntered.value) return VR_RENDER_SMOOTHING_ALPHA;
  if (!backendPoseSmoothingEnabled.value) return 1.0;
  const alpha = Number(backendPoseSmoothingAlpha.value);
  if (!Number.isFinite(alpha)) return 1.0;
  return clamp(alpha, 0.05, 1.0);
}

function interpolateArmPose(currentArm, targetArm, alpha) {
  const out = [];
  const count = Math.min(currentArm.length, targetArm.length, ARM_JOINT_COUNT);
  for (let i = 0; i < count; i++) {
    const current = Number(currentArm[i]);
    const target = Number(targetArm[i]);
    if (!Number.isFinite(current) || !Number.isFinite(target)) {
      out.push(Number.isFinite(target) ? target : 0);
      continue;
    }
    out.push(current + (target - current) * alpha);
  }
  return out;
}

function interpolateScalar(current, target, alpha) {
  const c = Number(current);
  const t = Number(target);
  if (!Number.isFinite(c)) return Number.isFinite(t) ? t : 0;
  if (!Number.isFinite(t)) return c;
  return c + (t - c) * alpha;
}

function applySmoothedBackendPose(options = {}) {
  const target = backendRenderTarget.value;
  if (!target || !robot || !robot.joints) return;

  const alpha = options.immediate === true ? 1 : getSceneJointInterpolationAlpha();
  const currentArm = getCurrentSceneArmRadians();
  const nextArm = interpolateArmPose(currentArm, target.arm, alpha);
  const currentGrip = getCurrentGripperRadians();
  const nextGrip = clamp(
    interpolateScalar(currentGrip, target.gripper, alpha),
    GRIPPER_MIN_RAD,
    GRIPPER_MAX_RAD
  );

  const armHasVisibleDelta = nextArm.some((value, index) => {
    const current = Number(currentArm[index]);
    const next = Number(value);
    return Number.isFinite(current) && Number.isFinite(next)
      ? Math.abs(next - current) > RENDER_ARM_EPSILON_RAD
      : false;
  });
  const gripperHasVisibleDelta = Math.abs(nextGrip - currentGrip) > RENDER_GRIPPER_EPSILON_RAD;
  if (!armHasVisibleDelta && !gripperHasVisibleDelta) {
    return;
  }

  isApplyingBackendState.value = true;
  try {
    BACKEND_ARM_JOINT_NAMES.forEach((jointName, index) => {
      const joint = robot.joints[jointName];
      const value = Number(nextArm[index]);
      if (!joint || !Number.isFinite(value)) return;
      joint.setJointValue(value);
    });

    setGripperJointValue(nextGrip, { skipPoseUpdate: true });
    syncJointDisplayFromSceneIfNeeded();
    syncEndEffectorPoseIfNeeded();
  } finally {
    isApplyingBackendState.value = false;
  }
}

function applySceneObjectPoseFromBackend(objectId, objectState) {
  if (objectState && typeof objectState === "object") {
    latestSceneObjectStates.set(objectId, objectState);
  }
  const model = sceneObjectModels.get(objectId);
  if (!model) return;
  if (!objectState || typeof objectState !== "object") return;

  const positionFrontend = backendPositionToFrontend(objectState.position);
  if (positionFrontend) {
    model.position.set(
      positionFrontend[0],
      positionFrontend[1],
      positionFrontend[2]
    );
  }

  const quaternionFrontend = backendQuaternionToFrontend(objectState.quaternion);
  if (quaternionFrontend) {
    model.quaternion.copy(quaternionFrontend);
  }
}

function applySceneObjectsFromBackendState(state) {
  if (!state?.objects || typeof state.objects !== "object") return;
  Object.entries(state.objects).forEach(([objectId, objectState]) => {
    applySceneObjectPoseFromBackend(objectId, objectState);
  });
}

function applyBackendStateToScene(state, options = {}) {
  if (!state || typeof state !== "object") return;

  const renderTarget = buildBackendRenderTarget(state);
  const previewTarget =
    options.preferQuestPreview === true ? getFreshQuestRenderPreview() : null;
  const visualTarget = previewTarget || renderTarget;
  if (visualTarget) {
    backendRenderTarget.value = visualTarget;
    applySmoothedBackendPose({ immediate: options.immediate === true });
  }

  isApplyingBackendState.value = true;
  try {
    applySceneObjectsFromBackendState(state);
    if (visualTarget) {
      syncJointDisplayFromSceneIfNeeded(true);
      syncEndEffectorPoseIfNeeded(true);
    }
  } finally {
    isApplyingBackendState.value = false;
  }
}

function applyAnglesToRobot(anglesDeg, options = {}) {
  const skipBackendSync = options.skipBackendSync !== false;
  const skipPoseUpdate = options.skipPoseUpdate === true;
  const normalizedAngles = normalizeInputAngles(anglesDeg);
  if (!normalizedAngles) return null;

  const radians = normalizedAngles.map((value) => toRadians(value));

  ARM_JOINT_NAMES.forEach((jointName, index) => {
    sliderInput(radians[index], jointName, { skipBackendSync, skipPoseUpdate });
  });
  sliderInput(radians[ARM_JOINT_COUNT], "gripper_joint", { skipBackendSync, skipPoseUpdate });

  if (skipPoseUpdate) {
    syncEndEffectorPoseIfNeeded(true);
  }

  return {
    normalizedAngles,
    radians,
  };
}

// 用于更新任务进度的函数（示例）
const updateTaskProgress = () => {
  // 这里可以根据实际需求更新任务进度
  // 例如：连接后端获取实际进度或根据当前操作阶段设置不同的进度值
  if (taskProgress.value < 100) {
    taskProgress.value += 5;
    if (taskProgress.value > 100) {
      taskProgress.value = 100;
    }
  }
};

// 修改fetchData函数，优先使用 /sim/state/，失败时回退到 /data/，并实现简单退避
const fetchData = async () => {
  if (!isFetching.value) return;
  if (websocketManager.isConnected) return;

  const trySimState = async () => {
    const resp = await get("/sim/state/");
    return resp.data;
  };

  const tryLegacy = async () => {
    const resp = await get("/data/");
    return resp.data;
  };

  try {
    // 尝试获取最新仿真状态
    const data = await trySimState();

    // data 应包含 qpos 数组与对象状态
    if (data && typeof data === "object") {
      commitBackendStateSnapshot(data);
      updateTaskProgress();
      fetchFailures.value = 0;
      return;
    }

    // 回退到 legacy /data/ 接口（兼容）
    const legacy = await tryLegacy();
    if (legacy && legacy.value) {
      // legacy.value 可能是字符串或数组
      let vals = legacy.value;
      if (typeof vals === "string") {
        vals = vals.split(" ").map(Number);
      }
      const normalizedAngles = normalizeInputAngles(vals.map((v) => Number(v)));
      if (normalizedAngles) {
        setRobotAngles(normalizedAngles);
      }
      updateTaskProgress();
      syncEndEffectorPoseIfNeeded(true);
      fetchFailures.value = 0;
      return;
    }

    throw new Error("无效的仿真状态响应");
  } catch (error) {
    // 避免控制台被刷屏：记录失败次数并在首次失败时打印日志
    fetchFailures.value += 1;
    if (fetchFailures.value === 1) {
      console.warn("Error fetching data (first failure):", error.message || error);
    } else if (fetchFailures.value % 10 === 0) {
      console.warn(`Error fetching data (${fetchFailures.value}次失败):`, error.message || error);
    }

    // 如果连续失败过多，自动停止获取以避免频繁请求（用户可重新连接）
    if (fetchFailures.value >= 50) {
      console.error("连续多次获取失败，已停止自动同步。请检查后端服务。");
      stopFetchingData();
    }
  }
};

const sendArmCommandToBackend = async (armRadians, options = {}) => {
  const n_steps = options.n_steps || 30;
  const control_mode = options.control_mode || "position";
  const gripperCommand = buildGripperCommand(options);
  rememberPendingManualTarget(armRadians, gripperCommand.value);

  // WebSocket 可用时优先走 WS，确保与实时广播链路一致
  if (websocketManager.isConnected) {
    const sent = websocketManager.sendControlCommand(armRadians, {
      n_steps,
      control_mode,
      gripper_command: gripperCommand,
      source: "desktop_manual",
    });

    if (sent) {
      sendCommandPending.value = true;

      // 安全超时：防止 controlResult 丢失导致前端永久 pending
      setTimeout(() => {
        if (sendCommandPending.value) {
          console.warn("controlResult 超时，自动清除等待标志");
          sendCommandPending.value = false;
        }
      }, 7000);

      return { ok: true, message: "命令已发送（通过 WebSocket）" };
    }

    console.warn("WebSocket 已连接但命令发送失败，将回退到 HTTP /sim/step/");
    clearPendingManualTarget();
  }

  // WS 不可用时直接 HTTP 下发，避免前端先动后被旧状态拉回
  sendCommandPending.value = true;
  try {
    const resp = await post("/sim/step/", {
      target_positions: armRadians,
      n_steps,
      control_mode,
      gripper_command: gripperCommand,
      source: "desktop_manual",
    });

    const status = String(resp?.data?.status || "").toLowerCase();
    if (status !== "success") {
      clearPendingManualTarget();
      try {
        const latest = await get("/sim/state/", { timeout: 1500 });
        if (latest?.data) {
          commitBackendStateSnapshot(latest.data);
        }
      } catch (_) {}
      return { ok: false, message: resp?.data?.message || "Command rejected due to collision/interference." };
    }

    if (resp?.data?.state?.qpos && Array.isArray(resp.data.state.qpos)) {
      commitBackendStateSnapshot(resp.data.state, { clearPendingManualTarget: true });
    }

    return { ok: true, message: resp.data?.message || "Command sent (HTTP)." };
  } catch (err) {
    clearPendingManualTarget();
    return { ok: false, message: "命令发送失败: " + (err.message || err) };
  } finally {
    sendCommandPending.value = false;
  }
};

// 优化测试发送数据的函数
const testSendData = async () => {
  try {
    let testAngles;
    if (angleInput.value.trim()) {
      testAngles = parseAngleText(angleInput.value);
      if (!testAngles) {
        alert("请先输入6或7个有效的关节角度值（J1..J6[,Grip]）");
        return;
      }
    } else {
      testAngles = [...DEFAULT_TEST_ANGLES_DEG];
      angleInput.value = testAngles.join(", ");
    }

    receivedText.value = "正在发送测试命令...";
    const normalizedAngles = normalizeInputAngles(testAngles);
    if (!normalizedAngles) {
      alert("角度格式不正确，请检查后重试");
      return;
    }

    const radians = normalizedAngles.map((value) => toRadians(value));
    const armRadians = radians.slice(0, ARM_JOINT_COUNT);

    if (!websocketManager.isConnected) {
      applyAnglesToRobot(normalizedAngles);
      syncJointDisplayFromSceneIfNeeded(true);
      syncEndEffectorPoseIfNeeded(true);
      receivedText.value = "已在本地设置角度（未接入仿真）";
      setAnglesResponse.value = [...normalizedAngles];
      updateTaskProgress();
      return;
    }

    const result = await sendArmCommandToBackend(armRadians, {
      n_steps: 50,
      control_mode: "position",
      gripper_opening: toGripperOpening(radians[ARM_JOINT_COUNT]),
    });
    receivedText.value = result.message;
    setAnglesResponse.value = [...normalizedAngles];
    updateTaskProgress();
  } catch (error) {
    receivedText.value = "命令发送失败: " + error.message;
    console.error("发送测试命令失败:", error);
  }
};

// 优化开始获取数据的函数
const startFetchingData = () => {
  if (!websocketManager.isConnected) {
    websocketManager.connect(runtimeConfig.simWsUrl);
  } else {
    websocketManager.requestState();
  }

  isFetching.value = true;
  fetchData(); // 作为 WS 不可用时的兜底
  if (!fetchInterval.value) {
    fetchInterval.value = setInterval(fetchData, 200); // fallback
  }
  console.log("已连接机器人，开始同步位置");
  // 重置任务进度
  taskProgress.value = 0;
  checkWebSocketReady();
  updateNetworkPrereq();
};

// 优化停止连接的函数
const stopFetchingData = () => {
  stopQuestControllerLoop();
  stopQuestHandLoop();
  isFetching.value = false;
  sendCommandPending.value = false;
  clearPendingManualTarget();
  clearRealtimeSliderDraft();
  lastRealtimeSliderSendAt.value = 0;
  clearInterval(fetchInterval.value);
  fetchInterval.value = null;
  if (websocketManager.isConnected) {
    websocketManager.disconnect();
  }
  console.log("已断开机器人连接");
  taskProgress.value = 100;

  if (vrControlOwner.value === "quest3_controller" || vrControlOwner.value === "quest3_hand") {
    handleQuestDisconnected();
  } else {
    checkWebSocketReady();
    updateNetworkPrereq();
  }
};

// 格式化角度数组显示
function formatAngles(angles) {
  return angles.map((angle) => angle.toFixed(1) + "°").join("  ");
}

// 设置预设角度
function setPresetAngles(preset) {
  if (preset === "home") {
    angleInput.value = "0, -90, 90, -90, -90, 0, 0";
  } else if (preset === "work") {
    angleInput.value = "45, -45, 45, -90, -45, 90, 20";
  } else if (preset === "safe-1") {
    angleInput.value = "-70, -90, 90, -90, -90, 0, 0";
  } else if (preset === "safe-2") {
    angleInput.value = "-30, -90, 90, -90, -90, 0, 0";
  } else if (preset === "safe-3") {
    angleInput.value = "-45, -70, 70, -90, -90, 0, 0";
  }
}

// 优化角度输入函数
async function inputRobotAngles() {
  if (sendCommandPending.value) {
    alert("上一个命令尚未完成，请稍候再发送。");
    return;
  }

  const normalizedAngles = parseAngleText(angleInput.value);
  if (!normalizedAngles) {
    alert("请输入6或7个关节角度值，用逗号分隔（J1..J6[,Grip]）");
    return;
  }

  console.log("正在发送角度命令:", normalizedAngles);

  const radians = normalizedAngles.map((value) => toRadians(value));
  const armRadians = radians.slice(0, ARM_JOINT_COUNT);

  if (!websocketManager.isConnected) {
    const applyResult = applyAnglesToRobot(normalizedAngles);
    if (!applyResult) {
      alert("角度格式不正确，请检查后重试");
      return;
    }
    syncJointDisplayFromSceneIfNeeded(true);
    syncEndEffectorPoseIfNeeded(true);
    receivedText.value = "已在本地设置角度（未接入仿真）";
    setAnglesResponse.value = [...normalizedAngles];
    updateTaskProgress();

    if (enableAutoReturn.value) {
      setTimeout(() => {
        setRobotAngles(homeAnglesDeg.value);
      }, autoReturnDelayMs.value);
    }

    return;
  }

  try {
    const result = await sendArmCommandToBackend(armRadians, {
      n_steps: 50,
      control_mode: "position",
      gripper_opening: toGripperOpening(radians[ARM_JOINT_COUNT]),
    });
    receivedText.value = result.message;
    if (!result.ok) {
      console.error("发送控制命令失败:", result.message);
    }
  } catch (e) {
    console.error("发送控制命令失败:", e);
  }

  if (enableAutoReturn.value && websocketManager.isConnected) {
    console.log("已连接仿真，跳过自动返回以保持目标姿态");
  }

  setAnglesResponse.value = [...normalizedAngles];

  updateTaskProgress();
}

// 使用的机械臂urdf模型
const urdf = "./ur5/ur5.urdf";
const WRIST_CAMERA_MOUNT_CONFIG = {
  assetPath: "./camera/urdf/d405_mount_assembly.urdf",
  parentLinkName: "robotiq_base_link",
  transform: {
    // Align clamp-ring center to gripper base axis so the mount is actually installed on the gripper.
    // Keep the ring around the wrist/gripper boundary (near robotiq base root).
    position: [-0.035392, -0.089332, 0.032],
    // Keep the camera/mount facing the toolbox side after the 180deg self-axis rotation.
    rotation: [0.0, -Math.PI, Math.PI / 2],
    scale: [1.0, 1.0, 1.0],
  },
};
const SCENE_OBJECT_CONFIGS = [
  {
    id: "rack",
    assetPath: "./rack/urdf/rack.urdf",
    transform: {
      position: [0.5, 0.0, 0.0],
      rotation: [0.0, 0.0, 0.0],
      scale: [1.0, 1.0, 1.0],
    },
  },
  {
    id: "toolbox",
    assetPath: "./tools/urdf/toolbox.urdf",
    transform: {
      position: [0.48, 0.5, -0.2],
      rotation: [-Math.PI / 2, 0.0, -Math.PI / 2],
      scale: [1.0, 1.0, 1.0],
    },
  },
  {
    id: "wrench_01",
    assetPath: "./tools/urdf/wrench.urdf",
    transform: {
      position: [0.08, 0.5240336800934792, 0.3],
      rotation: [0.0, 0.0, 0.0],
      scale: [1.0, 1.0, 1.0],
    },
  },
  {
    id: "screwdriver_01",
    assetPath: "./tools/urdf/screwdriver.urdf",
    transform: {
      position: [0.2, 0.5, 0.26],
      rotation: [-Math.PI / 2, 0.0, 0.0],
      scale: [1.0, 1.0, 1.0],
    },
  },
  {
    id: "pliers_01",
    assetPath: "./tools/urdf/pliers.urdf",
    transform: {
      position: [0.28, 0.5100852437109232, 0.12],
      rotation: [0.0, 0.0, 0.0],
      scale: [1.0, 1.0, 1.0],
    },
  },
];

// 添加切换面板显示状态的函数
function togglePanel(panel) {
  switch (panel) {
    case "slider":
      showSlider.value = !showSlider.value;
      break;
    case "robot":
      showRobotPanel.value = !showRobotPanel.value;
      break;
    case "control":
      showControlPanel.value = !showControlPanel.value;
      break;
    case "view":
      showViewControls.value = !showViewControls.value;
      break;
    case "progress":
      showTaskProgress.value = !showTaskProgress.value;
      break;
    case "vr-control":
      showVrControlPanel.value = !showVrControlPanel.value;
      break;
  }
}

function resolveJointName(name) {
  if (!robot || !robot.joints) return null;
  if (robot.joints[name]) return name;
  const mappedName = jointNameMap[name];
  if (mappedName && robot.joints[mappedName]) return mappedName;
  return null;
}

function setGripperJointValue(value, options = {}) {
  const skipPoseUpdate = options.skipPoseUpdate === true;
  const clampedValue = clamp(value, GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);

  if (!robot || !robot.joints) return;

  const targetValues = {
    left_driver_joint: clampedValue,
    right_driver_joint: clampedValue,
    "left_driver-left_coupler": -clampedValue,
    "right_driver-right_coupler": -clampedValue,
    left_spring_link_joint: clampedValue,
    right_spring_link_joint: clampedValue,
    left_follower_joint: clampedValue,
    right_follower_joint: clampedValue,
  };

  let hasApplied = false;
  Object.entries(targetValues).forEach(([jointName, jointValue]) => {
    const joint = robot.joints[jointName];
    if (!joint) return;
    joint.setJointValue(jointValue);
    hasApplied = true;
  });

  if (!skipPoseUpdate) {
    syncJointDisplayFromSceneIfNeeded();
    syncEndEffectorPoseIfNeeded();
  }

  if (!hasApplied && !warnedMissingJoints.has("gripper_joint")) {
    warnedMissingJoints.add("gripper_joint");
    console.warn(
      "未找到手抓相关关节:",
      GRIPPER_JOINT_NAMES,
      "可用关节:",
      Object.keys(robot.joints || {})
    );
  }
}

function getFreshRealtimeSliderDraft() {
  const draft = realtimeSliderDraft.value;
  if (!draft || typeof draft !== "object") return null;
  if (Date.now() - Number(draft.updatedAt || 0) > REALTIME_SLIDER_DRAFT_TTL_MS) {
    clearRealtimeSliderDraft();
    return null;
  }
  if (!Array.isArray(draft.arm) || draft.arm.length < ARM_JOINT_COUNT) return null;
  return draft;
}

function updateRealtimeSliderDraft(name, value) {
  const draft = getFreshRealtimeSliderDraft();
  const arm = Array.isArray(draft?.arm)
    ? draft.arm.slice(0, ARM_JOINT_COUNT)
    : getAuthoritativeArmRadians().slice(0, ARM_JOINT_COUNT);
  let gripperOpening = Number.isFinite(Number(draft?.gripperOpening))
    ? clamp(Number(draft.gripperOpening), 0, 1)
    : getAuthoritativeGripperOpening();

  if (name === "gripper_joint") {
    gripperOpening = toGripperOpening(clamp(Number(value), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD));
  } else {
    const backendName = jointNameMap[name] || name;
    const jointIndex = BACKEND_ARM_JOINT_NAMES.indexOf(backendName);
    if (jointIndex < 0) return null;
    arm[jointIndex] = Number(value);
  }

  const nextDraft = {
    updatedAt: Date.now(),
    arm,
    gripperOpening,
  };
  realtimeSliderDraft.value = nextDraft;
  return nextDraft;
}

function sendRealtimeSliderControl(options = {}) {
  const force = options.force === true;
  if (isApplyingBackendState.value && !force) return;
  const now = Date.now();
  if (
    !force &&
    now - Number(lastRealtimeSliderSendAt.value) < REALTIME_SLIDER_MIN_SEND_INTERVAL_MS
  ) {
    return;
  }

  const draft = options.draft || getFreshRealtimeSliderDraft();
  const armRadians = Array.isArray(options.armRadians)
    ? options.armRadians.slice(0, ARM_JOINT_COUNT)
    : Array.isArray(draft?.arm)
      ? draft.arm.slice(0, ARM_JOINT_COUNT)
      : getAuthoritativeArmRadians();
  if (!Array.isArray(armRadians) || armRadians.length < ARM_JOINT_COUNT) return;

  const gripperOpening = Number.isFinite(Number(options.gripperOpening))
    ? clamp(Number(options.gripperOpening), 0, 1)
    : Number.isFinite(Number(draft?.gripperOpening))
      ? clamp(Number(draft.gripperOpening), 0, 1)
      : getAuthoritativeGripperOpening();
  const gripperCommand = {
    mode: "open_close",
    value: gripperOpening,
  };

  const sent = websocketManager.isConnected
    ? websocketManager.sendControlCommand(armRadians, {
        n_steps: REALTIME_SLIDER_COMMAND_STEPS,
        control_mode: "position",
        gripper_command: gripperCommand,
        source: "desktop_manual",
      })
    : false;

  if (sent) {
    lastRealtimeSliderSendAt.value = now;
  } else {
    if (realtimeSliderFallbackInFlight.value) {
      return;
    }
    realtimeSliderFallbackInFlight.value = true;
    post("/sim/step/", {
      target_positions: armRadians,
      n_steps: REALTIME_SLIDER_COMMAND_STEPS,
      control_mode: "position",
      gripper_command: gripperCommand,
      source: "desktop_manual",
    })
      .then((resp) => {
        if (resp?.data?.state) {
          commitBackendStateSnapshot(resp.data.state);
        }
      })
      .catch((error) => {
        console.warn("实时滑条 HTTP 兜底失败:", error?.message || error);
        clearPendingManualTarget();
      })
      .finally(() => {
        realtimeSliderFallbackInFlight.value = false;
        lastRealtimeSliderSendAt.value = Date.now();
      });
  }
}

function scheduleRealtimeSliderSync() {
  if (isVrModeEntered.value) {
    // In VR mode, Quest teleop is the active control source.
    // Block desktop slider auto-sync to avoid sending stale desktop commands
    // that can pull the robot back after a few seconds.
    return;
  }
  if (sliderSyncTimer.value) {
    clearTimeout(sliderSyncTimer.value);
  }

  sliderSyncTimer.value = setTimeout(() => {
    sendRealtimeSliderControl();
  }, REALTIME_SLIDER_DEBOUNCE_MS);
}

function flushRealtimeSliderSync() {
  if (isVrModeEntered.value) {
    return;
  }
  if (sliderSyncTimer.value) {
    clearTimeout(sliderSyncTimer.value);
    sliderSyncTimer.value = null;
  }
  sendRealtimeSliderControl();
}

// 修改sliderInput函数，确保每次角度变化时更新位置信息
function sliderInput(value, name, options = {}) {
  const skipBackendSync = options.skipBackendSync === true || isVrModeEntered.value;
  const skipPoseUpdate = options.skipPoseUpdate === true;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return;
  const physicsAuthoritative = websocketManager.isConnected && !skipBackendSync;

  if (name === "gripper_joint") {
    if (physicsAuthoritative) {
      updateRealtimeSliderDraft(name, numericValue);
      scheduleRealtimeSliderSync();
      return;
    }

    setGripperJointValue(numericValue, { skipPoseUpdate });
    if (!skipBackendSync) {
      updateRealtimeSliderDraft(name, numericValue);
      scheduleRealtimeSliderSync();
    }
    return;
  }

  if (physicsAuthoritative) {
    const draft = updateRealtimeSliderDraft(name, numericValue);
    if (!draft && !warnedMissingJoints.has(name)) {
      warnedMissingJoints.add(name);
      console.warn("未找到后端关节映射:", name);
    }
    if (draft) {
      scheduleRealtimeSliderSync();
    }
    return;
  }

  const resolvedName = resolveJointName(name);
  if (!resolvedName) {
    if (!warnedMissingJoints.has(name)) {
      warnedMissingJoints.add(name);
      console.warn("未找到关节:", name, "可用关节:", robot && robot.joints ? Object.keys(robot.joints) : []);
    }
    return;
  }

  ensureJointAnglesBuffer();
  robot.joints[resolvedName].setJointValue(numericValue);
  if (!skipPoseUpdate) {
    syncJointDisplayFromSceneIfNeeded();
    syncEndEffectorPoseIfNeeded();
  }

  if (!skipBackendSync) {
    updateRealtimeSliderDraft(name, numericValue);
    scheduleRealtimeSliderSync();
  }
}

function sliderCommit(value, name) {
  sliderInput(value, name);
  flushRealtimeSliderSync();
}

// 新增设置机器臂六个角度的函数
function setRobotAngles(angles) {
  const applyResult = applyAnglesToRobot(angles, {
    skipBackendSync: true,
    skipPoseUpdate: true,
  });
  if (!applyResult) {
    console.error("必须提供6或7个角度值");
    syncEndEffectorPoseIfNeeded(true);
    return;
  }
  syncJointDisplayFromSceneIfNeeded(true);
  syncEndEffectorPoseIfNeeded(true);
}

// 修改为视角切换函数
const changeView = () => {
  if (selectedView.value === "top") {
    // 切换到俯视视角
    camera.position.set(0, 3, 0);
    camera.lookAt(0, 0, 0);
    camera.up.set(0, 0, -1);
  } else {
    // 切换到透视视角
    camera.position.set(2.5, 1.51, 1.02);
    camera.lookAt(0, 0, 0);
    camera.up.set(0, 1, 0);
  }
  // 更新控制器
  controls.update();
};

// 创建场景->相机->渲染器->相机添加到场景中->渲染器渲染场景和相机->渲染器添加到dom中
var robot = null;
let scene = "";
let camera = "";
let renderer = "";
// 轨道控制器
let controls = "";
const sceneObjectModels = new Map();
const latestSceneObjectStates = new Map();
let wristCameraMountModel = null;
const xrControllerModelFactory = new XRControllerModelFactory();
const xrHandModelFactory = new XRHandModelFactory();
const xrVisualNodes = {
  controllerGrips: { left: null, right: null },
  controllerRays: { left: null, right: null },
  hands: { left: null, right: null },
};
let activeQuestXrSession = null;
let questXrVisibilityHandler = null;
let questXrInputSourcesHandler = null;
let questXrEndedHandler = null;

// 初始化
function initBase() {
  // 创建场景
  scene = new THREE.Scene();
  // 设置场景位置
  scene.position.set(0, 0, 0);
  // 创建相机
  camera = new THREE.PerspectiveCamera(
    45,
    window.innerWidth / window.innerHeight,
    0.1,
    100
  );
  // 设置相机位置
  camera.position.set(2.5, 1.51, 1.02);

  // 相机添加到场景中
  scene.add(camera);

  // antialias:开启抗锯齿  logarithmicDepthBuffer:使用对数深度缓冲器,一般在单个场景处理较大的差异
  renderer = new THREE.WebGLRenderer({
    antialias: true,
    logarithmicDepthBuffer: true,
  });

  // 设置渲染器尺寸
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(getRenderPixelRatio());
  renderer.xr.enabled = true;

  // 设置渲染器颜色
  renderer.setClearColor("#DCDCDC");
}

// 添加光线
function addLight() {
  const ambient = new THREE.AmbientLight("#ffffff", 0.75);
  scene.add(ambient);

  const positions = [
    { x: 15, y: 15, z: 15 },
    { x: -15, y: -15, z: -15 },
  ];
  positions.forEach((pos) => {
    // 创建平行光
    const light = new THREE.DirectionalLight("#fff", 1);
    // 设置灯光位置
    light.position.set(pos.x, pos.y, pos.z);
    //将灯光添加到场景中
    scene.add(light);
  });
}

// 轨道控制器
function initOrbitControls() {
  // 设置控制器
  controls = new OrbitControls(camera, renderer.domElement);
  // 开启阻尼 更加真实
  controls.enableDamping = true;
}

// render渲染器
function render() {
  // Keep approaching latest backend state between WS ticks for visually smooth motion.
  applySmoothedBackendPose();
  // In immersive XR, browser timer throttling can stall setInterval-based teleop loops.
  // Drive Quest teleop ticks from the XR render loop to match AR-UR5 control behavior.
  runQuestVrControlFrame();
  renderer.render(scene, camera);
  if (controls && !(renderer?.xr && renderer.xr.isPresenting)) {
    controls.update();
  }
}

// 辅助线
function addHelpLine() {
  // 网格辅助线
  const gridHelper = new THREE.GridHelper(100, 20);
  scene.add(gridHelper);
}

function loadUrdfModel(modelPath, onLoad, onError) {
  const loader = new URDFLoader();
  loader.load(
    modelPath,
    (result) => {
      console.log("URDF加载成功:", modelPath);
      onLoad(result);
    },
    undefined,
    (error) => {
      console.error("URDF加载失败:", modelPath, error);
      if (typeof onError === "function") {
        onError(error);
      }
    }
  );
}

function loadUrdfModelAsync(modelPath) {
  return new Promise((resolve, reject) => {
    loadUrdfModel(modelPath, resolve, reject);
  });
}

function focusCameraOnObject(object) {
  if (!object || !camera || !controls) return;
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) return;

  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const distance = Math.max(maxDim * 2.2, 1.5);

  camera.position.set(center.x + distance, center.y + distance * 0.7, center.z + distance);
  controls.target.copy(center);
  camera.lookAt(center);
  controls.update();
}

// 初始化
initBase();
// 添加灯光
addLight();
// 添加控制器
initOrbitControls();
// 添加辅助线和网格地板
addHelpLine();

function initSceneObjects() {
  SCENE_OBJECT_CONFIGS.forEach(async (config) => {
    try {
      const result = await loadUrdfModelAsync(config.assetPath);
      const { position, rotation, scale } = config.transform;
      result.scale.set(scale[0], scale[1], scale[2]);
      result.position.set(position[0], position[1], position[2]);
      result.rotation.set(rotation[0], rotation[1], rotation[2]);
      scene.add(result);
      sceneObjectModels.set(config.id, result);
      const latestState =
        latestSceneObjectStates.get(config.id) || simulationState.value?.objects?.[config.id];
      if (latestState) {
        applySceneObjectPoseFromBackend(config.id, latestState);
      }
    } catch (error) {
      console.error("场景对象加载失败:", config.assetPath, error);
    }
  });
}

function attachWristCameraMount() {
  if (!robot || !robot.links) return;

  const parentLink = robot.links[WRIST_CAMERA_MOUNT_CONFIG.parentLinkName];
  if (!parentLink) {
    console.warn(
      "未找到相机支架挂载父链接:",
      WRIST_CAMERA_MOUNT_CONFIG.parentLinkName
    );
    return;
  }

  if (wristCameraMountModel && wristCameraMountModel.parent) {
    wristCameraMountModel.parent.remove(wristCameraMountModel);
  }

  loadUrdfModelAsync(WRIST_CAMERA_MOUNT_CONFIG.assetPath)
    .then((mountAssembly) => {
      const { position, rotation, scale } = WRIST_CAMERA_MOUNT_CONFIG.transform;
      mountAssembly.scale.set(scale[0], scale[1], scale[2]);
      mountAssembly.position.set(position[0], position[1], position[2]);
      mountAssembly.rotation.set(rotation[0], rotation[1], rotation[2]);
      parentLink.add(mountAssembly);
      wristCameraMountModel = mountAssembly;
    })
    .catch((error) => {
      console.error("腕部相机支架加载失败:", error);
    });
}

function initRobot() {
  loadUrdfModelAsync(urdf)
    .then((result) => {
      robot = result;
      console.log("机器人关节:", Object.keys(robot.joints || {}));

      //设置ROBOT坐标z朝上
      robot.rotation.x = -Math.PI / 2;
      robot.rotation.z = 0;
      robot.position.set(-0.2, 0.5, 0.0); // 将机械臂放置在实验台上
      scene.add(robot);
      attachWristCameraMount();
      focusCameraOnObject(robot);
      sliderInput(-Math.PI / 2, "link2_joint");
      sliderInput(Math.PI / 2, "link3_joint");
      sliderInput(-Math.PI / 2, "link4_joint");
      sliderInput(-Math.PI / 2, "link5_joint");
      sliderInput(0, "gripper_joint");

      // 初始化后计算位置信息
      syncJointDisplayFromSceneIfNeeded(true);
      syncEndEffectorPoseIfNeeded(true);
    })
    .catch((error) => {
      console.error("机器人加载失败:", error);
    });
}

// 按顺序加载模型
initSceneObjects();
initRobot();

// 设置位置信息更新定时器
const positionUpdateInterval = ref(null);

// WebSocket 状态同步监听器
const setupWebSocketStateSync = () => {
  // 连接状态监听
  websocketManager.on('statusChange', (status) => {
    websocketStatus.value = status;
    isWebSocketConnected.value = websocketManager.isConnected;
    isFetching.value = isWebSocketConnected.value;

    if (isWebSocketConnected.value) {
      console.log('WebSocket状态同步已连接');
      websocketManager.requestState();
      if (fetchInterval.value) {
        clearInterval(fetchInterval.value);
        fetchInterval.value = null;
      }
    } else {
      console.log('WebSocket状态同步已断开');
      sendCommandPending.value = false;
      clearPendingManualTarget();
      clearRealtimeSliderDraft();
      lastRealtimeSliderSendAt.value = 0;
      resetStateSync();
      checkWebSocketReady();
      updateNetworkPrereq();
      handleQuestDisconnected();
    }
  });

  // 状态更新监听
  websocketManager.on('stateUpdate', (data) => {
    handleStateUpdate(data);
  });

  // 控制结果监听：用于清理命令等待标志
  websocketManager.on('controlResult', (data) => {
    if (DEBUG_VR_CONTROL_RESULTS) {
      console.debug('Received controlResult:', data);
    }
    sendCommandPending.value = false;
    if (Array.isArray(data?.state?.qpos)) {
      if (isQuestControlBackendState(data.state)) {
        commitQuestControlStateSnapshot(data.state);
      } else {
        commitBackendStateSnapshot(data.state, { clearPendingManualTarget: true });
      }
    }
    if (isQuestControllerModeActive()) {
      const state = data?.state;
      if (state && typeof state === "object") {
        const backendGroup = String(state.selected_joint_group || "").trim();
        if (backendGroup) {
          vrSelectedJointGroup.value = backendGroup;
        }
      }
    }
    if (data?.status && String(data.status).toLowerCase() !== "success") {
      clearPendingManualTarget();
      clearQuestRenderPreview();
      if (websocketManager.isConnected) {
        websocketManager.requestState();
      }
      receivedText.value = data?.message || "Command rejected due to collision/interference.";
      return;
    }
    flushQueuedQuestControlCommand();
    flushQueuedQuestHandControlCommand();
  });

  // 错误处理
  websocketManager.on('error', (error) => {
    sendCommandPending.value = false;
    questControllerPendingMapped.value = null;
    questHandPendingMapped.value = null;
    resetQuestControllerQueuedFlushTimer();
    resetQuestHandQueuedFlushTimer();
    clearPendingManualTarget();
    clearRealtimeSliderDraft();
    clearQuestRenderPreview();
    if (websocketManager.isConnected) {
      websocketManager.requestState();
    }
    stateSyncErrors.value++;
    console.error('State sync/control error:', error);
    const errorMessage =
      typeof error === "string"
        ? error
        : error?.message || error?.detail || "State sync/control error.";
    if (errorMessage) {
      receivedText.value = String(errorMessage);
    }
    updateConnectionQuality();
  });

  // 连接断开
  websocketManager.on('disconnected', () => {
    sendCommandPending.value = false;
    questControllerPendingMapped.value = null;
    questHandPendingMapped.value = null;
    resetQuestControllerQueuedFlushTimer();
    resetQuestHandQueuedFlushTimer();
    clearPendingManualTarget();
    clearRealtimeSliderDraft();
    clearQuestRenderPreview();
    lastRealtimeSliderSendAt.value = 0;
    resetStateSync();
    checkWebSocketReady();
    updateNetworkPrereq();
    handleQuestDisconnected();
  });

  websocketManager.on('vrStateResult', (data) => {
    if (data?.state) {
      applyVrStateFromBackend(data.state);
      updateNetworkPrereq();
    }
  });
};

// 处理状态更新
const handleStateUpdate = (data) => {
  const now = Date.now();
  const prevUpdate = lastStateUpdate.value;
  if (!acceptBackendStateTimestamp(data)) {
    return;
  }

  // 计算网络延迟（如果有时间戳）
  if (data.timestamp) {
    const serverTime = data.timestamp * 1000; // 假设时间戳是秒
    networkLatency.value = now - serverTime;
  }

  // 更新状态
  simulationState.value = data;
  applyVrStateFromBackend(data);
  checkD405ObservationReady(data);
  checkRecordingBindingReady(data);
  checkWebSocketReady();
  updateNetworkPrereq();
  updateSafetyFeedbackFromState(data);

  // 手动控制刚发出时，短时间忽略明显滞后的旧状态，避免前端“回弹到初始位”
  if (isQuestControlBackendState(data)) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
    applyBackendStateToScene(data);
  } else if (shouldApplyIncomingBackendState(data, now)) {
    // 以后端回传状态为准，统一驱动机器人/夹爪/对象（带平滑）
    applyBackendStateToScene(data);
  } else {
    // Guard 命中时维持本地最新目标，不使用这帧滞后状态更新目标姿态。
    applySceneObjectsFromBackendState(data);
    applySmoothedBackendPose();
  }

  // 添加到状态历史缓冲区
  addToStateBuffer(data, now);

  // 更新统计信息
  updateSyncStats(now, prevUpdate);
  updateConnectionQuality();

  lastStateUpdate.value = now;
};

// 保留轻量时间戳缓冲，避免对完整状态做高频深拷贝导致界面卡顿。
const addToStateBuffer = (state, timestamp) => {
  stateUpdateHistory.value = [{ state: null, timestamp }];
};

// 更新同步统计信息
const updateSyncStats = (now, prevUpdate) => {
  if (prevUpdate > 0) {
    const timeDiff = now - prevUpdate;
    const instantRate = 1000 / timeDiff; // Hz

    // 计算移动平均更新率
    const alpha = 0.1; // 平滑因子
    actualUpdateRate.value = actualUpdateRate.value * (1 - alpha) + instantRate * alpha;
  }
};

// 更新连接质量
const updateConnectionQuality = () => {
  const now = Date.now();
  const timeSinceLastUpdate = now - lastStateUpdate.value;

  // 如果超过2秒没有更新，降低质量
  let quality = 100;
  if (timeSinceLastUpdate > 2000) {
    quality = Math.max(0, 100 - (timeSinceLastUpdate - 2000) / 10);
  }

  // 根据错误率降低质量
  if (stateSyncErrors.value > 0) {
    quality = Math.max(0, quality - stateSyncErrors.value * 10);
  }

  connectionQuality.value = Math.round(quality);
};

// 获取插值状态（用于平滑动画）
const getInterpolatedState = (targetTime) => {
  if (!stateInterpolationEnabled.value || stateUpdateHistory.value.length < 2) {
    return simulationState.value;
  }

  // 找到最接近的时间点
  const history = stateUpdateHistory.value;
  let beforeIndex = -1;
  let afterIndex = -1;

  for (let i = 0; i < history.length - 1; i++) {
    if (history[i].timestamp <= targetTime && history[i + 1].timestamp >= targetTime) {
      beforeIndex = i;
      afterIndex = i + 1;
      break;
    }
  }

  if (beforeIndex === -1 || afterIndex === -1) {
    return simulationState.value;
  }

  const before = history[beforeIndex];
  const after = history[afterIndex];

  // 计算插值因子
  const timeDiff = after.timestamp - before.timestamp;
  const factor = (targetTime - before.timestamp) / timeDiff;

  // 对关节角度进行插值
  const interpolatedQpos = [];
  for (let i = 0; i < Math.min(before.state.qpos.length, after.state.qpos.length); i++) {
    const interpolated = before.state.qpos[i] + (after.state.qpos[i] - before.state.qpos[i]) * factor;
    interpolatedQpos.push(interpolated);
  }

  // 返回插值后的状态
  return {
    ...after.state,
    qpos: interpolatedQpos
  };
};

// 重置状态同步
const resetStateSync = () => {
  simulationState.value = null;
  stateUpdateHistory.value = [];
  backendRenderTarget.value = null;
  networkLatency.value = 0;
  stateSyncErrors.value = 0;
  actualUpdateRate.value = 0;
  connectionQuality.value = 0;
  lastStateUpdate.value = 0;
  lastAcceptedBackendStateTimestampMs.value = 0;
  clearPendingManualTarget();
  clearRealtimeSliderDraft();
  clearQuestRenderPreview();
};

// 切换状态插值
const toggleStateInterpolation = () => {
  stateInterpolationEnabled.value = !stateInterpolationEnabled.value;
  backendPoseSmoothingEnabled.value = stateInterpolationEnabled.value;
  console.log(`状态插值: ${stateInterpolationEnabled.value ? '启用' : '禁用'}`);
};

// 调整目标更新率
const setTargetUpdateRate = (rate) => {
  targetUpdateRate.value = rate;
  console.log(`目标更新率设置为: ${rate} Hz`);
};

// 调整缓冲区大小
const setStateBufferSize = (size) => {
  stateBufferSize.value = size;
  console.log(`状态缓冲区大小设置为: ${size}`);
};

// 获取状态同步状态
const getStateSyncStatus = () => {
  return {
    isConnected: isWebSocketConnected.value,
    status: websocketStatus.value,
    lastUpdate: lastStateUpdate.value,
    latency: networkLatency.value,
    actualRate: actualUpdateRate.value,
    targetRate: targetUpdateRate.value,
    quality: connectionQuality.value,
    errors: stateSyncErrors.value,
    bufferSize: stateUpdateHistory.value.length,
    interpolationEnabled: stateInterpolationEnabled.value
  };
};

watch(questControllerSensitivity, () => {
  rebuildQuestControllerTeleop();
});

watch(questControllerDeadzone, () => {
  rebuildQuestControllerTeleop();
});

watch(questHandSensitivity, () => {
  rebuildQuestHandTeleop();
});

watch(questHandTrackingStable, () => {
  if (!isQuestHandModeActive()) return;
  questHandStatusText.value = buildHandTrackingStatusText();
});

watch(questHandInputMode, () => {
  if (!isQuestHandModeActive()) return;
  questHandStatusText.value = buildHandTrackingStatusText();
});

watch(vrModeState, () => {
  updateQuestXrVisualVisibility();
});

const handleWindowResize = () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(getRenderPixelRatio());
};

const taskProgressInterval = ref(null);

onMounted(() => {
  localHostname.value = typeof window !== "undefined" ? window.location.hostname : "";
  localHostIp.value = readHostCandidate();
  if (localHostIp.value) {
    hostPageAccessUrl.value = buildPageAccessUrlFromHost(localHostIp.value);
  } else if (localHostname.value) {
    hostPageAccessUrl.value = buildPageAccessUrlFromHost(localHostname.value);
  } else {
    hostPageAccessUrl.value =
      typeof window !== "undefined" && window.location ? window.location.origin : "";
  }

  // 设置WebSocket状态同步
  setupWebSocketStateSync();

  // 如果WebSocket未连接，尝试连接
  if (!isWebSocketConnected.value) {
    setTimeout(() => {
      websocketManager.connect(runtimeConfig.simWsUrl);
    }, 1000);
  }

  // 保持原有的初始化逻辑
  fetchData(); // 作为后备
  document.getElementById("webgl").appendChild(renderer.domElement);
  renderer.setAnimationLoop(render);

  window.addEventListener("resize", handleWindowResize);
  window.addEventListener("gamepadconnected", handleQuestGamepadConnectionEvent);
  window.addEventListener("gamepaddisconnected", handleQuestGamepadConnectionEvent);

  taskProgressInterval.value = setInterval(() => {
    if (isFetching.value && taskProgress.value < 95) {
      updateTaskProgress();
    }
  }, 2000);

  runQuest3AccessChecks();
});

watch(isVrModeEntered, (entered) => {
  if (!entered) return;
  ensureVrModeActive();
});

onBeforeUnmount(() => {
  stopQuestControllerLoop();
  stopQuestHandLoop();
  stopQuestVrControlWatchdog();
  detachQuestXrSessionListeners();
  resetQuestControllerQueuedFlushTimer();
  resetQuestHandQueuedFlushTimer();
  if (renderer?.xr) {
    Promise.resolve(renderer.xr.setSession(null)).catch(() => {});
    renderer.setAnimationLoop(null);
  }
  void stopQuestXRSession();
  stopFetchingData();
  if (sliderSyncTimer.value) {
    clearTimeout(sliderSyncTimer.value);
    sliderSyncTimer.value = null;
  }
  if (taskProgressInterval.value) {
    clearInterval(taskProgressInterval.value);
    taskProgressInterval.value = null;
  }
  window.removeEventListener("resize", handleWindowResize);
  window.removeEventListener("gamepadconnected", handleQuestGamepadConnectionEvent);
  window.removeEventListener("gamepaddisconnected", handleQuestGamepadConnectionEvent);
  // 清理WebSocket监听器
  websocketManager.off('statusChange');
  websocketManager.off('stateUpdate');
  websocketManager.off('controlResult');
  websocketManager.off('vrStateResult');
  websocketManager.off('error');
  websocketManager.off('disconnected');
});
</script>

<style>
.btn {
  position: fixed;
  bottom: 5%;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  background-color: #48719d; /* 按钮背景颜色 */
  color: white; /* 按钮文字颜色 */
  border: none; /* 去掉默认边框 */
  border-radius: 25px; /* 圆角边框 */
  font-size: 16px; /* 调整字体大小 */
  font-weight: 600; /* 字体加粗 */
  cursor: pointer; /* 鼠标移到按钮上时显示手指图标 */
  transition: all 0.3s ease; /* 过渡效果 */
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2); /* 添加阴影效果 */
  opacity: 0.8; /* 设置按钮透明度 */
}

/* 按钮悬停效果 */
.btn:hover {
  background-color: #0056b3; /* 悬停时改变背景颜色 */
  box-shadow: 0 6px 15px rgba(0, 0, 0, 0.3); /* 增强阴影效果 */
  transform: translateX(-50%) translateY(-2px); /* 悬停时轻微上移 */
}

/* 按钮按下时的效果 */
.btn:active {
  background-color: #004085; /* 按下时背景颜色变化 */
  transform: translateX(-50%) translateY(0); /* 按下时重置位置 */
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.2); /* 按下时减少阴影 */
}

.fetch-button {
  margin-bottom: 20px; /* 为获取关节角度的按钮添加底部间距 */
  padding: 10px 20px; /* 添加内边距 */
  background-color: #48719d; /* 按钮背景颜色 */
  color: white; /* 按钮文字颜色 */
  border: none; /* 去掉默认边框 */
  border-radius: 5px; /* 圆角边框 */
  font-size: 16px; /* 调整字体大小 */
  font-weight: 600; /* 字体加粗 */
  cursor: pointer; /* 鼠标移到按钮上时显示手指图标 */
  transition: background-color 0.3s ease, transform 0.2s ease; /* 过渡效果 */
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2); /* 添加阴影效果 */
}

/* 按钮悬停效果 */
.fetch-button:hover {
  background-color: #0056b3; /* 悬停时改变背景颜色 */
  transform: translateY(-2px); /* 悬停时轻微上移 */
}

/* 按钮按下时的效果 */
.fetch-button:active {
  background-color: #004085; /* 按下时背景颜色变化 */
  transform: translateY(0); /* 按下时重置位置 */
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); /* 按下时减少阴影 */
}

/* 提交按钮样式 */
.input-section button {
  padding: 10px 20px; /* 添加内边距 */
  background-color: #28a745; /* 提交按钮背景颜色 */
  color: white; /* 提交按钮文字颜色 */
  border: none; /* 去掉默认边框 */
  border-radius: 5px; /* 圆角边框 */
  font-size: 16px; /* 调整字体大小 */
  font-weight: 600; /* 字体加粗 */
  cursor: pointer; /* 鼠标移到按钮上时显示手指图标 */
  transition: background-color 0.3s ease, transform 0.2s ease; /* 过渡效果 */
}

/* 提交按钮悬停效果 */
.input-section button:hover {
  background-color: #218838; /* 悬停时改变背景颜色 */
  transform: translateY(-2px); /* 悬停时轻微上移 */
}

/* 提交按钮按下时的效果 */
.input-section button:active {
  background-color: #1e7e34; /* 按下时背景颜色变化 */
  transform: translateY(0); /* 按下时重置位置 */
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); /* 按下时减少阴影 */
}

.transparent-panel {
  position: absolute; /* 绝对定位 */
  top: 20px; /* 距离顶部的距离 */
  left: 20px; /* 距离左侧的距离 */
  padding: 20px; /* 内边距 */
  background-color: rgba(255, 255, 255, 0.8); /* 半透明白色背景 */
  border-radius: 10px; /* 圆角边框 */
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3); /* 添加阴影效果 */
  z-index: 10; /* 确保面板在其他元素之上 */
}

/* 修改为下拉菜单样式 */
.view-controls {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 10;
}

.view-selector {
  padding: 10px;
  font-size: 16px;
  border: none;
  border-radius: 5px;
  background-color: #4caf50;
  color: white;
  cursor: pointer;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  transition: background-color 0.3s;
}

.view-selector:hover {
  background-color: #45a049;
}

.view-selector:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.5);
}

/* 任务进度样式 */
.task-progress {
  position: fixed;
  bottom: 20px;
  left: 20px;
  z-index: 10;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 15px;
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  width: 200px;
}

.progress-bar {
  width: 100%;
  height: 15px;
  background-color: #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 5px;
}

.progress-fill {
  height: 100%;
  background-color: #4caf50;
  border-radius: 10px;
  transition: width 0.3s ease;
}

.progress-text {
  text-align: center;
  font-weight: bold;
  color: #333;
}

.vr-control-panel {
  position: fixed;
  top: 72px;
  right: 20px;
  width: 460px;
  max-height: calc(100vh - 164px);
  overflow-y: auto;
  background: rgba(18, 28, 38, 0.88);
  color: #e8eef3;
  border: 1px solid rgba(119, 156, 186, 0.35);
  border-radius: 12px;
  padding: 12px;
  z-index: 11;
  backdrop-filter: blur(6px);
}

.vr-control-panel.quest-device {
  width: min(420px, calc(100vw - 24px));
  right: 12px;
  top: 60px;
  max-height: calc(100vh - 120px);
}

.vr-control-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(119, 156, 186, 0.2);
  padding-bottom: 8px;
}

.vr-control-header h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #d7ebff;
}

.vr-control-close {
  padding: 5px 9px;
  border: 1px solid rgba(119, 156, 186, 0.6);
  border-radius: 6px;
  background: rgba(40, 68, 96, 0.9);
  color: #d7ebff;
  cursor: pointer;
  font-size: 12px;
}

.vr-control-close:hover {
  background: rgba(52, 84, 116, 0.95);
}

.vr-control-section {
  margin-top: 10px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(119, 156, 186, 0.2);
  background: rgba(13, 21, 29, 0.5);
}

.vr-section-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
  color: #d8ecff;
}

.network-check-button {
  padding: 5px 9px;
  border: 1px solid rgba(119, 156, 186, 0.6);
  border-radius: 6px;
  background: rgba(40, 68, 96, 0.9);
  color: #d7ebff;
  cursor: pointer;
  font-size: 12px;
}

.network-check-button:hover {
  background: rgba(52, 84, 116, 0.95);
}

.network-status-row {
  display: grid;
  grid-template-columns: 104px 1fr;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
}

.network-label {
  color: #9bc3e2;
}

.network-value {
  color: #eef4f8;
  word-break: break-all;
}

.network-hint-row {
  margin-top: 8px;
  font-size: 12px;
  color: #b4d7f1;
}

.vr-mode-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.vr-mode-chip,
.vr-owner-chip {
  font-size: 12px;
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(56, 87, 115, 0.65);
  color: #e6f2fb;
}

.quest-controller-status {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid rgba(121, 167, 198, 0.25);
  background: rgba(14, 24, 34, 0.62);
}

.quest-hand-status {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid rgba(121, 167, 198, 0.25);
  background: rgba(14, 24, 34, 0.62);
}

.vr-inline-slider {
  width: 140px;
  margin-right: 8px;
  vertical-align: middle;
}

.vr-joint-toast {
  margin-top: 8px;
  border: 1px solid rgba(121, 220, 164, 0.65);
  border-radius: 6px;
  background: rgba(33, 95, 64, 0.82);
  color: #dffdea;
  padding: 6px 8px;
  font-size: 12px;
}

.vr-menu-buttons {
  display: grid;
  gap: 7px;
  margin-top: 8px;
}

.vr-entry-buttons {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.vr-menu-btn {
  border: 1px solid rgba(116, 148, 175, 0.5);
  border-radius: 8px;
  padding: 8px;
  background: rgba(32, 55, 76, 0.92);
  color: #eff6fc;
  cursor: pointer;
}

.vr-menu-btn.enter {
  border-color: rgba(90, 190, 130, 0.55);
  background: rgba(30, 92, 60, 0.9);
}

.vr-menu-btn.enter:hover {
  background: rgba(43, 118, 79, 0.94);
}

.vr-menu-btn:hover {
  background: rgba(44, 71, 95, 0.94);
}

.vr-menu-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.vr-menu-btn.active {
  border-color: rgba(121, 220, 164, 0.85);
  background: rgba(39, 110, 72, 0.95);
  color: #eafff3;
}

.vr-menu-btn.exit {
  border-color: rgba(196, 95, 95, 0.65);
  background: rgba(88, 36, 36, 0.9);
}

.vr-menu-error {
  margin-top: 8px;
  font-size: 12px;
  color: #ffc4c4;
}

.status-ok {
  color: #72d88a;
}

.status-error {
  color: #ff9b9b;
}

.status-checking {
  color: #f6d07a;
}

.status-unknown {
  color: #b6cad7;
}

.status-vr_disabled {
  color: #b6cad7;
}

.status-vr_ready {
  color: #72d88a;
}

.status-vr_controller_mode,
.status-vr_hand_mode {
  color: #92e6ff;
}

.status-vr_error {
  color: #ff9b9b;
}

.position-info,
.orientation-info {
  margin-bottom: 10px;
}

.position-info p,
.orientation-info p {
  margin: 5px 0;
  font-size: 14px;
  color: #444;
  font-family: "Courier New", monospace;
  display: flex;
  justify-content: space-between;
}

/* 添加高亮效果，当值变化时 */
.position-info p.highlight,
.orientation-info p.highlight {
  background-color: rgba(255, 255, 0, 0.2);
  transition: background-color 0.5s ease;
}

/* 机器人控制面板样式 */
.robot-control-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  width: 380px;
  background-color: rgba(245, 245, 247, 0.95);
  border-radius: 10px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
  z-index: 10;
  padding: 0;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
    Ubuntu, Cantarell, sans-serif;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: #48719d;
  color: white;
  border-radius: 10px 10px 0 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.connection-status {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background-color: #f56c6c;
}

.connection-status.connected {
  background-color: #67c23a;
}

.panel-section {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.control-button {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.control-button.robot-connect-btn--disconnected {
  background-color: #409eff;
  color: white;
}

.control-button.robot-connect-btn--connected {
  background-color: #f56c6c;
  color: white;
}

.control-button.robot-connect-btn--disconnected:hover {
  background-color: #66b1ff;
}

.control-button.robot-connect-btn--connected:hover {
  background-color: #f78989;
}

.status-indicator {
  display: flex;
  align-items: center;
  margin-top: 12px;
  font-size: 12px;
  color: #67c23a;
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #67c23a;
  border-radius: 50%;
  margin-right: 8px;
}

.pulse {
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

.angle-input-container {
  margin-bottom: 12px;
}

.angle-input {
  width: 100%;
  padding: 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 14px;
  margin-bottom: 8px;
}

.angle-input:focus {
  border-color: #409eff;
  outline: none;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.preset-angles {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.preset-title {
  font-size: 12px;
  color: #909399;
}

.preset-btn {
  padding: 4px 8px;
  background-color: #f2f6fc;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.preset-btn:hover {
  background-color: #ecf5ff;
  color: #409eff;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.action-button {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.send-btn {
  background-color: #67c23a;
  color: white;
}

.test-btn {
  background-color: #e6a23c;
  color: white;
}

.send-btn:hover {
  background-color: #85ce61;
}

.test-btn:hover {
  background-color: #ebb563;
}

.btn-icon {
  margin-right: 6px;
}

.feedback-area {
  background-color: #f8f9fa;
  border-radius: 6px;
  padding: 12px;
}

.feedback-item {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #eeeeee;
}

.feedback-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.feedback-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.feedback-value {
  font-family: "Monaco", "Consolas", monospace;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

/* 底部面板控制按钮样式 */
.panel-controls {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 10px;
  padding: 10px 15px;
  background-color: rgba(0, 0, 0, 0.7);
  border-radius: 30px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  z-index: 1000;
}

.panel-control-button {
  padding: 8px 12px;
  background: none;
  border: none;
  border-radius: 20px;
  color: #ccc;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.panel-control-button:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: white;
}

.panel-control-button.active {
  background-color: rgba(72, 113, 157, 0.8);
  color: white;
}

.panel-icon {
  margin-right: 5px;
  font-size: 14px;
}

/* 状态同步样式 */
.sync-status-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.sync-status-grid.compact {
  grid-template-columns: 1fr;
}

.sync-status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f5f5f5;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.sync-label {
  color: #606266;
  font-weight: 500;
}

.sync-value {
  color: #303133;
  font-family: monospace;
  font-weight: 500;
}

.sync-connected {
  color: #67c23a;
}

.sync-disconnected {
  color: #f56c6c;
}

.sync-good {
  color: #67c23a;
}

.sync-fair {
  color: #e6a23c;
}

.sync-poor {
  color: #f56c6c;
}

.sync-high-latency {
  color: #e6a23c;
}

.sync-has-errors {
  color: #f56c6c;
}

.interpolation-toggle {
  padding: 2px 6px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  background-color: white;
  color: #606266;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}

.interpolation-toggle:hover {
  border-color: #409eff;
  color: #409eff;
}

.interpolation-toggle.active {
  background-color: #409eff;
  border-color: #409eff;
  color: white;
}

/* 在小屏幕上调整布局 */
@media (max-width: 1200px) {
  .panel-controls {
    flex-wrap: wrap;
    justify-content: center;
    width: calc(100% - 40px);
    max-width: 600px;
  }

  .sync-status-grid {
    grid-template-columns: 1fr;
  }

  .vr-control-panel {
    width: calc(100% - 40px);
    max-height: calc(100vh - 200px);
    left: 20px;
    right: 20px;
    top: 70px;
  }
}
</style>
