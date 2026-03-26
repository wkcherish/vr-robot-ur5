<template>
  <div class="common-layout">
    <el-container>
      <div id="webgl">
        <!-- 现有面板添加显示条件 -->
        <Menu
          :show-slider-controls="showSlider"
          @sliderInput="sliderInput"
          v-show="showSlider"
        />

        <!-- 机器人控制面板 -->
        <div class="robot-control-panel" v-show="showRobotPanel">
          <div class="panel-header">
            <h3>机器人双向映射系统</h3>
            <div class="connection-status" :class="{ connected: isFetching }">
              {{ isFetching ? "已连接" : "未连接" }}
            </div>
          </div>

          <!-- 添加仿真控制组件 -->
          <Control v-show="showControlPanel" />
          <!-- 连接控制区 -->
          <div class="panel-section">
            <h4 class="section-title">机器人连接</h4>
            <button
              @click="isFetching ? stopFetchingData() : startFetchingData()"
              class="control-button"
              :class="{
                'connected-btn': isFetching,
                'disconnected-btn': !isFetching,
              }"
            >
              {{ isFetching ? "断开连接" : "连接机器人" }}
            </button>
            <div v-if="isFetching" class="status-indicator">
              <span class="status-dot pulse"></span> 正在实时同步机器人位置...
            </div>
          </div>

          <!-- 状态同步状态区 -->
          <div class="panel-section" v-if="showStateSyncStatus">
            <h4 class="section-title">状态同步</h4>
            <div class="sync-status-grid">
              <div class="sync-status-item">
                <span class="sync-label">连接状态:</span>
                <span class="sync-value" :class="{ 'sync-connected': isFetching, 'sync-disconnected': !isFetching }">
                  {{ isFetching ? '已连接' : '未连接' }}
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

          <!-- 角度控制区 -->
          <div class="panel-section">
            <h4 class="section-title">角度控制</h4>
            <div class="angle-input-container">
              <input
                v-model="angleInput"
                type="text"
                placeholder="输入关节角度: J1,J2,J3,J4,J5,J6"
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

        <!-- 引入相机状态面板 -->
        <Camera v-show="showCameraPanel" />

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
            @click="togglePanel('camera')"
            class="panel-control-button"
            :class="{ active: showCameraPanel }"
          >
            <span class="panel-icon">📷</span> 相机状态
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
            @click="togglePanel('sync')"
            class="panel-control-button"
            :class="{ active: showStateSyncStatus }"
          >
            <span class="panel-icon">🔄</span> 状态同步
          </button>
        </div>
      </div>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import Menu from "./components/robot.vue";
import Camera from "./components/camera.vue"; // 引入相机组件
import Control from "./components/control.vue"; // 引入仿真控制组件
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import URDFLoader from "urdf-loader";
import axios from "axios";
import websocketManager from "./utils/websocket.js"; // 引入WebSocket管理器
import endEffectorPose from "./components/robot.vue"; // 引入末端执行器位姿

// 修改视角控制为下拉菜单
const selectedView = ref("perspective"); // 默认选择透视视角
// console.log("endEffectorPose", endEffectorPose);
// 新增任务进度变量
const taskProgress = ref(0);

// 各面板显示状态控制
const showSlider = ref(false); // 滑块面板默认不显示
const showRobotPanel = ref(false); // 机器人控制面板默认显示
const showCameraPanel = ref(false); // 相机状态面板默认显示
const showControlPanel = ref(false); // 仿真控制面板默认显示
const showViewControls = ref(true); // 视角控制默认显示
const showTaskProgress = ref(true); // 任务进度默认显示
const showStateSyncStatus = ref(true); // 状态同步状态默认显示
const angleInput = ref(""); // 新增用于存储输入角度的变量
const angles = ref([0, 0, 0, 0, 0, 0]); // 新增数组用于存储六个角度
// 自动返回设置
const enableAutoReturn = ref(false); // 如果启用，发送位置后自动返回home
const autoReturnDelayMs = ref(2000); // 自动返回延迟（ms）
const homeAnglesDeg = ref([0, -90, 90, -90, -90, 0]); // 默认home角度（度）

const inputText = ref(""); // 新增用于存储输入字符的变量

const receivedText = ref(""); // 新增用于存储后端返回的文本
const fetchedValue = ref(null); // 新增用于存储从后端获取的数值

const jointAngles = ref([]); // 新增用于存储关节角度的变量
const setAnglesResponse = ref([]); // 用于存储设置的角度值的响应

const fetchInterval = ref(null); // 用于存储定时器的引用
const testvalue = ref(null); // 用于存储从后端获取的数值
const isFetching = ref(false);
const fetchFailures = ref(0); // 连续获取失败计数
const sendCommandPending = ref(false); // 命令发送等待回复标志

// WebSocket 状态同步相关
const isWebSocketConnected = ref(false);
const websocketStatus = ref("未连接");
const simulationState = ref(null); // 完整的仿真状态
const stateUpdateHistory = ref([]); // 状态更新历史，用于插值
const networkLatency = ref(0); // 网络延迟
const stateSyncErrors = ref(0); // 状态同步错误计数
const lastStateUpdate = ref(0); // 最后状态更新时间
const stateInterpolationEnabled = ref(true); // 启用状态插值
const targetUpdateRate = ref(50); // 目标更新率 (Hz)
const actualUpdateRate = ref(0); // 实际更新率
const stateBufferSize = ref(10); // 状态缓冲区大小
const connectionQuality = ref(100); // 连接质量百分比
const robotPosition = ref({ x: 0, y: 0, z: 0 });
const robotOrientation = ref({ roll: 0, pitch: 0, yaw: 0 });

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

  const trySimState = async () => {
    const resp = await axios.get("http://localhost:8000/sim/state/", { timeout: 3000 });
    return resp.data;
  };

  const tryLegacy = async () => {
    const resp = await axios.get("http://localhost:8000/data/", { timeout: 3000 });
    return resp.data;
  };

  try {
    // 尝试获取最新仿真状态
    const data = await trySimState();

    // data 应包含 qpos 数组
    if (data && data.qpos && Array.isArray(data.qpos)) {
      // 将弧度转换为角度
      const anglesDeg = data.qpos.slice(0, 6).map((v) => v * (180 / Math.PI));
      jointAngles.value = anglesDeg;
      setRobotAngles(anglesDeg);
      updateTaskProgress();
      calculateEndEffectorPosition();
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
      jointAngles.value = vals.map((v) => Number(v));
      setRobotAngles(jointAngles.value);
      updateTaskProgress();
      calculateEndEffectorPosition();
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

// 优化测试发送数据的函数
const testSendData = async () => {
  try {
    // 首先检查是否有输入角度
    let testAngles;
    if (angleInput.value.trim()) {
      testAngles = angleInput.value
        .split(",")
        .map((angle) => parseFloat(angle.trim()));
      if (testAngles.length !== 6 || testAngles.some(isNaN)) {
        alert("请先输入6个有效的关节角度值");
        return;
      }
    } else {
      // 使用默认测试角度
      testAngles = [60, -90, 90, -140, -90, 0];
      angleInput.value = testAngles.join(", ");
    }

    const testData = {
      angles: testAngles,
      command: "move_to_position",
    };

    receivedText.value = "正在发送测试命令...";
    // 将角度转换为弧度
    const radians = testAngles.map((v) => (v * Math.PI) / 180);

    // 如果当前未与服务器/仿真连接，则仅在本地应用角度（不接入 mujoco）
    if (!isFetching.value) {
      // 直接在本地 Three.js 模型上应用角度（即时视觉反馈）
      sliderInput(radians[0], "link1_joint");
      sliderInput(radians[1], "link2_joint");
      sliderInput(radians[2], "link3_joint");
      sliderInput(radians[3], "link4_joint");
      sliderInput(radians[4], "link5_joint");
      sliderInput(radians[5], "link6_joint");

      receivedText.value = "已在本地设置角度（未接入仿真）";
      setAnglesResponse.value = [...testAngles];
      updateTaskProgress();
      return;
    }

    // 否则尝试通过 WebSocket/HTTP 发送到后端仿真（mujoco）
    const sent = websocketManager.sendControlCommand(radians, { n_steps: 50, control_mode: "position" });
    if (sent) {
      receivedText.value = "命令已发送（通过 WebSocket）";
      sendCommandPending.value = true;
      setAnglesResponse.value = [...testAngles];
      updateTaskProgress();
    } else {
      // 回退到 HTTP 接口 /sim/step/
      try {
        const resp = await axios.post("http://localhost:8000/sim/step/", {
          target_positions: radians,
          n_steps: 50,
          control_mode: "position",
        });
        receivedText.value = resp.data.message || "命令已发送(HTTP)";
        setAnglesResponse.value = [...testAngles];
        updateTaskProgress();
      } catch (err) {
        receivedText.value = "命令发送失败: " + (err.message || err);
        console.error("发送测试命令失败:", err);
      }
    }
  } catch (error) {
    receivedText.value = "命令发送失败: " + error.message;
    console.error("发送测试命令失败:", error);
  }
};

// 优化开始获取数据的函数
const startFetchingData = () => {
  isFetching.value = true;
  fetchData(); // 立即调用一次
  fetchInterval.value = setInterval(fetchData, 100); // 每100ms同步一次
  console.log("已连接机器人，开始同步位置");
  // 重置任务进度
  taskProgress.value = 0;
};

// 优化停止连接的函数
const stopFetchingData = () => {
  isFetching.value = false;
  clearInterval(fetchInterval.value);
  fetchInterval.value = null;
  console.log("已断开机器人连接");
  taskProgress.value = 100;
};

// 格式化角度数组显示
function formatAngles(angles) {
  return angles.map((angle) => angle.toFixed(1) + "°").join("  ");
}

// 设置预设角度
function setPresetAngles(preset) {
  if (preset === "home") {
    angleInput.value = "0, -90, 90, -90, -90, 0";
  } else if (preset === "work") {
    angleInput.value = "45, -45, 45, -90, -45, 90";
  } else if (preset === "safe-1") {
    angleInput.value = "-70, -90, 90, -90, -90, 0";
  } else if (preset === "safe-2") {
    angleInput.value = "-30, -90, 90, -90, -90, 0";
  } else if (preset === "safe-3") {
    angleInput.value = "-45, -70, 70, -90, -90, 0";
  }
}

// 优化角度输入函数
function inputRobotAngles() {
  // 将输入的角度字符串转换为数组
  if (sendCommandPending.value) {
    alert("上一个命令尚未完成，请稍候再发送。");
    return;
  }
  const angles_input = angleInput.value
    .split(",")
    .map((angle) => parseFloat(angle.trim()));

  // 验证输入
  if (angles_input.length !== 6) {
    alert("请输入6个关节角度值，用逗号分隔");
    return;
  }

  if (angles_input.some(isNaN)) {
    alert("输入包含无效的数字");
    return;
  }

  console.log("正在发送角度命令:", angles_input);

  // 将角度转换为弧度并更新
  const radians = angles_input.map((v) => v * (Math.PI / 180));

  // 先在本地应用到Three.js机器人（即时视觉反馈）
  sliderInput(radians[0], "link1_joint");
  sliderInput(radians[1], "link2_joint");
  sliderInput(radians[2], "link3_joint");
  sliderInput(radians[3], "link4_joint");
  sliderInput(radians[4], "link5_joint");
  sliderInput(radians[5], "link6_joint");

  // 如果未与服务器/仿真连接，则只在本地应用角度（不接入 mujoco）
  if (!isFetching.value) {
    receivedText.value = "已在本地设置角度（未接入仿真）";
    setAnglesResponse.value = [...angles_input];
    updateTaskProgress();
    return;
  }

  // 发送控制命令到后端仿真（通过 WebSocketManager）
  try {
    const sent = websocketManager.sendControlCommand(radians, { n_steps: 50, control_mode: "position" });
    if (!sent) {
      console.warn("控制命令未立即发送（已入队列或未连接）");
    } else {
      console.log("控制命令已发送到后端仿真");
      // 标记为命令等待状态，忽略来自服务器的临时状态更新
      // 以防仿真在命令执行过程中短暂回到初始位导致前端覆盖目标姿态。
      sendCommandPending.value = true;

      // 额外发送一次短时“保持”命令，确保后端 ctrl 被设置为目标位置并保持
      // （某些后端实现会在多步控制后更新 ctrl，这里再发一次保证最后的 ctrl 值）
      setTimeout(() => {
        try {
          websocketManager.sendControlCommand(radians, { n_steps: 1, control_mode: "position" });
        } catch (err) {
          console.warn("发送保持命令失败:", err);
        }
      }, 120);

      // 安全超时：如果很长时间没有收到 controlResult，自动清除等待标志（防止永久屏蔽状态同步）
      setTimeout(() => {
        if (sendCommandPending.value) {
          console.warn("controlResult 超时，自动清除等待标志");
          sendCommandPending.value = false;
        }
      }, 7000);
    }
  } catch (e) {
    console.error("发送控制命令失败:", e);
  }

  // 如果启用了自动返回并且当前未连接服务器，则安排返回到home位置
  // 在已连接（isFetching）时跳过自动返回，以保持机械臂到达目标角度后停留
  if (enableAutoReturn.value && !isFetching.value) {
    const homeRad = homeAnglesDeg.value.map((v) => v * (Math.PI / 180));
    setTimeout(() => {
      try {
        const sentBack = websocketManager.sendControlCommand(homeRad, { n_steps: 60, control_mode: "position" });
        if (!sentBack) {
          console.warn("自动返回命令未立即发送（已入队列或未连接）");
        } else {
          console.log("自动返回命令已发送");
        }
      } catch (err) {
        console.error("自动返回命令发送失败:", err);
      }
      // 同时在本地更新显示（以应对后端延迟）
      sliderInput(homeRad[0], "link1_joint");
      sliderInput(homeRad[1], "link2_joint");
      sliderInput(homeRad[2], "link3_joint");
      sliderInput(homeRad[3], "link4_joint");
      sliderInput(homeRad[4], "link5_joint");
      sliderInput(homeRad[5], "link6_joint");
    }, autoReturnDelayMs.value);
  } else if (enableAutoReturn.value && isFetching.value) {
    console.log("已连接仿真，跳过自动返回以保持目标姿态");
  }

  // 保存设置的角度值以便显示
  setAnglesResponse.value = [...angles_input];

  updateTaskProgress();
}

// 使用的机械臂urdf模型
const urdf = "./ur5/ur5.urdf";
// 电池模型
const battery = "./battery/urdf/battery.urdf";
// 实验台模型
const rack = "./rack/urdf/rack.urdf";
// 相机三脚架模型
const camera_base = "./camera_base/urdf/camera_base.urdf";
// 实际相机模型
const real_camera = "./camera/urdf/camera.urdf";

// 添加切换面板显示状态的函数
function togglePanel(panel) {
  switch (panel) {
    case "slider":
      showSlider.value = !showSlider.value;
      break;
    case "robot":
      showRobotPanel.value = !showRobotPanel.value;
      break;
    case "camera":
      showCameraPanel.value = !showCameraPanel.value;
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
    case "sync":
      showStateSyncStatus.value = !showStateSyncStatus.value;
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

// 修改sliderInput函数，确保每次角度变化时更新位置信息
function sliderInput(value, name) {
  const resolvedName = resolveJointName(name);
  if (!resolvedName) {
    if (!warnedMissingJoints.has(name)) {
      warnedMissingJoints.add(name);
      console.warn("未找到关节:", name, "可用关节:", robot && robot.joints ? Object.keys(robot.joints) : []);
    }
    return;
  }

  robot.joints[resolvedName].setJointValue(value);
  // 在每次关节变化后立即更新位置信息
  calculateEndEffectorPosition();
}

// 新增设置机器臂六个角度的函数
function setRobotAngles(angles) {
  // 将输入的角度字符串转换为数组

  if (angles.length === 6) {
    // 将角度转换为弧度并更新六个角度
    const radians = angles.map((v) => v * (Math.PI / 180));
    // 假设关节名称为 'link1_joint', 'link2_joint', 'link3_joint', 'link4_joint', 'link5_joint', 'link6_joint'
    sliderInput(radians[0], "link1_joint");
    sliderInput(radians[1], "link2_joint");
    sliderInput(radians[2], "link3_joint");
    sliderInput(radians[3], "link4_joint");
    sliderInput(radians[4], "link5_joint");
    sliderInput(radians[5], "link6_joint");
  } else {
    console.error("必须提供六个角度值");
    // 更新位置信息
    calculateEndEffectorPosition();
  }
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
  renderer.setPixelRatio(window.devicePixelRatio || 1);

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
  renderer.render(scene, camera);
  controls.update();

  // 每帧都更新位置信息
  calculateEndEffectorPosition();

  requestAnimationFrame(render);
}

// 辅助线
function addHelpLine() {
  // 网格辅助线
  const gridHelper = new THREE.GridHelper(100, 20);
  scene.add(gridHelper);
}

function loadUrdfModel(modelPath, onLoad) {
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
    }
  );
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

function initCamera() {
  loadUrdfModel(real_camera, (result) => {
    // 调整相机位置和大小
    result.scale.set(1, 1, 1);
    result.position.set(-0.205, 0.832, 0.4);
    result.rotation.y = Math.PI*0.65; // 旋转相机以正确朝向场景

    scene.add(result);
  });
}

function initCameraBase() {
  loadUrdfModel(camera_base, (result) => {
    // 调整相机三脚架位置和大小
    result.scale.set(0.01, 0.01, 0.01);
    result.position.set(-0.1, 0.68, 0.4);
    result.rotation.x = Math.PI; // 旋转90度
    scene.add(result);
  });
}

// 添加实验台模型加载函数
function initRack() {
  loadUrdfModel(rack, (result) => {
    // 调整实验台位置和大小
    result.scale.set(1, 1, 1);
    result.position.set(0.5, 0, 0);
    scene.add(result);
  });
}

// 添加电池模型加载函数
function initBattery() {
  loadUrdfModel(battery, (result) => {
    // 调整电池位置和大小
    result.scale.set(0.8, 0.8, 0.8);
    result.position.set(0.1, 1.085, 0.5);
    // 添加90度旋转（绕Y轴）
    result.rotation.y = Math.PI / 2; // 旋转90度
    // 添加调试代码，查看电池的包围盒
    const box = new THREE.Box3().setFromObject(result);
    console.log("Battery bounds:", box.min, box.max);

    scene.add(result);
  });
}

function initRobot() {
  loadUrdfModel(urdf, (result) => {
    robot = result;
    console.log("机器人关节:", Object.keys(robot.joints || {}));

    //设置ROBOT坐标z朝上
    robot.rotation.x = -Math.PI / 2;
    robot.rotation.z = 0;
    robot.position.set(-0.2, 0.5, -0.1); // 将机械臂放置在实验台上
    scene.add(robot);
    focusCameraOnObject(robot);
    sliderInput(-Math.PI / 2, "link2_joint");
    sliderInput(Math.PI / 2, "link3_joint");
    sliderInput(-Math.PI / 2, "link4_joint");
    sliderInput(-Math.PI / 2, "link5_joint");

    // 初始化后计算位置信息
    calculateEndEffectorPosition();
  });
}

// 按顺序加载模型
initRack();
initBattery();
initRobot();
initCamera();
initCameraBase();

// 设置位置信息更新定时器
const positionUpdateInterval = ref(null);

// WebSocket 状态同步监听器
const setupWebSocketStateSync = () => {
  // 连接状态监听
  websocketManager.on('statusChange', (status) => {
    websocketStatus.value = status;
    isWebSocketConnected.value = websocketManager.isConnected;

    if (isWebSocketConnected.value) {
      console.log('WebSocket状态同步已连接');
    } else {
      console.log('WebSocket状态同步已断开');
      resetStateSync();
    }
  });

  // 状态更新监听
  websocketManager.on('stateUpdate', (data) => {
    handleStateUpdate(data);
  });

  // 控制结果监听：用于清理命令等待标志
  websocketManager.on('controlResult', (data) => {
    console.log('收到 controlResult:', data);
    sendCommandPending.value = false;
  });

  // 错误处理
  websocketManager.on('error', (error) => {
    stateSyncErrors.value++;
    console.error('状态同步错误:', error);
    updateConnectionQuality();
  });

  // 连接断开
  websocketManager.on('disconnected', () => {
    resetStateSync();
  });
};

// 处理状态更新
const handleStateUpdate = (data) => {
  const now = Date.now();
  const prevUpdate = lastStateUpdate.value;

  // 计算网络延迟（如果有时间戳）
  if (data.timestamp) {
    const serverTime = data.timestamp * 1000; // 假设时间戳是秒
    networkLatency.value = now - serverTime;
  }

  // 更新状态
  simulationState.value = data;

  // 同步关节角度
  if (data.qpos && Array.isArray(data.qpos)) {
    updateJointAngles(data.qpos);
  }

  // 添加到状态历史缓冲区
  addToStateBuffer(data, now);

  // 更新统计信息
  updateSyncStats(now, prevUpdate);
  updateConnectionQuality();

  lastStateUpdate.value = now;
};

// 更新关节角度
const updateJointAngles = (qpos) => {
  // 如果正在等待控制命令结果，则暂时忽略来自服务器的 qpos 更新，
  // 保持前端当前显示的目标角度，直到收到 controlResult 清除等待标志。
  if (sendCommandPending.value) {
    // 可选：打印调试信息，但避免频繁日志打印
    // console.log('忽略状态更新（等待控制结果）');
    return;
  }
  // 将弧度转换为角度
  const anglesInDegrees = qpos.slice(0, 6).map(rad => rad * (180 / Math.PI));
  jointAngles.value = anglesInDegrees;

  // 应用到机器人模型
  setRobotAngles(anglesInDegrees);

  // 更新末端执行器位置
  calculateEndEffectorPosition();
};

// 添加到状态缓冲区（用于插值）
const addToStateBuffer = (state, timestamp) => {
  stateUpdateHistory.value.push({
    state: { ...state },
    timestamp: timestamp
  });

  // 保持缓冲区大小
  if (stateUpdateHistory.value.length > stateBufferSize.value) {
    stateUpdateHistory.value.shift();
  }
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
  networkLatency.value = 0;
  stateSyncErrors.value = 0;
  actualUpdateRate.value = 0;
  connectionQuality.value = 0;
  lastStateUpdate.value = 0;
};

// 切换状态插值
const toggleStateInterpolation = () => {
  stateInterpolationEnabled.value = !stateInterpolationEnabled.value;
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

onMounted(() => {
  // 设置WebSocket状态同步
  setupWebSocketStateSync();

  // 如果WebSocket未连接，尝试连接
  if (!isWebSocketConnected.value) {
    setTimeout(() => {
      websocketManager.connect();
    }, 1000);
  }

  // 保持原有的初始化逻辑
  fetchData(); // 作为后备
  document.getElementById("webgl").appendChild(renderer.domElement);
  render();

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
  });

  setInterval(() => {
    if (isFetching.value && taskProgress.value < 95) {
      updateTaskProgress();
    }
  }, 2000);
});

onBeforeUnmount(() => {
  stopFetchingData();
  // 清理WebSocket监听器
  websocketManager.off('statusChange');
  websocketManager.off('stateUpdate');
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

.disconnected-btn {
  background-color: #409eff;
  color: white;
}

.connected-btn {
  background-color: #f56c6c;
  color: white;
}

.disconnected-btn:hover {
  background-color: #66b1ff;
}

.connected-btn:hover {
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
}
</style>
