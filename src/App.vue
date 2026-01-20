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
const angleInput = ref(""); // 新增用于存储输入角度的变量
const angles = ref([0, 0, 0, 0, 0, 0]); // 新增数组用于存储六个角度

const inputText = ref(""); // 新增用于存储输入字符的变量

const receivedText = ref(""); // 新增用于存储后端返回的文本
const fetchedValue = ref(null); // 新增用于存储从后端获取的数值

const jointAngles = ref([]); // 新增用于存储关节角度的变量
const setAnglesResponse = ref([]); // 用于存储设置的角度值的响应

const fetchInterval = ref(null); // 用于存储定时器的引用
const testvalue = ref(null); // 用于存储从后端获取的数值
const isFetching = ref(false);

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

// 修改fetchData函数，确保从后端获取数据后立即更新位置
const fetchData = async () => {
  if (!isFetching.value) return;
  try {
    const response = await axios.get("http://localhost:8000/data/");
    jointAngles.value = response.data.value.split(" ").map(Number);
    setRobotAngles(jointAngles.value);
    updateTaskProgress();
    // 确保在设置角度后立即更新位置信息
    calculateEndEffectorPosition();
  } catch (error) {
    console.error("Error fetching data:", error);
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
    const response = await axios.post(
      "http://localhost:8000/test-data/",
      testData
    );
    receivedText.value = response.data.message || "命令已发送";
    console.log("测试命令响应:", response.data);
    updateTaskProgress();

    // 更新界面显示的角度值
    setAnglesResponse.value = [...testAngles];
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

  // 应用到机器人
  sliderInput(radians[0], "link1_joint");
  sliderInput(radians[1], "link2_joint");
  sliderInput(radians[2], "link3_joint");
  sliderInput(radians[3], "link4_joint");
  sliderInput(radians[4], "link5_joint");
  sliderInput(radians[5], "link6_joint");

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
  }
}

// 修改sliderInput函数，确保每次角度变化时更新位置信息
function sliderInput(value, name) {
  robot.joints[name].setJointValue(value);
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

  // 设置渲染器颜色
  renderer.setClearColor("#DCDCDC");
}

// 添加光线
function addLight() {
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

// 初始化
initBase();
// 添加灯光
addLight();
// 添加控制器
initOrbitControls();
// 添加辅助线和网格地板
addHelpLine();

function initCamera() {
  const loader = new URDFLoader();
  loader.load(real_camera, (result) => {
    // 调整相机位置和大小
    result.scale.set(1, 1, 1);
    result.position.set(-0.205, 0.832, 0.4);
    result.rotation.y = Math.PI; // 旋转90度

    scene.add(result);
  });
}

function initCameraBase() {
  const loader = new URDFLoader();
  loader.load(camera_base, (result) => {
    // 调整相机三脚架位置和大小
    result.scale.set(0.01, 0.01, 0.01);
    result.position.set(-0.1, 0.68, 0.4);
    result.rotation.x = Math.PI; // 旋转90度
    scene.add(result);
  });
}

// 添加实验台模型加载函数
function initRack() {
  const loader = new URDFLoader();
  loader.load(rack, (result) => {
    // 调整实验台位置和大小
    result.scale.set(1, 1, 1);
    result.position.set(0.5, 0, 0);
    scene.add(result);
  });
}

// 添加电池模型加载函数
function initBattery() {
  const loader = new URDFLoader();
  loader.load(battery, (result) => {
    // 调整电池位置和大小
    result.scale.set(0.8, 0.8, 0.8);
    result.position.set(0.3, 1.085, 0.5);
    // 添加90度旋转（绕Y轴）
    result.rotation.y = Math.PI / 2; // 旋转90度
    // 添加调试代码，查看电池的包围盒
    const box = new THREE.Box3().setFromObject(result);
    console.log("Battery bounds:", box.min, box.max);

    scene.add(result);
  });
}

function initRobot() {
  // 实例化 URDF模型加载器
  const loader = new URDFLoader();

  // 导入URDF模型
  loader.load(urdf, (result) => {
    robot = result;
    console.log(robot.joints);

    //设置ROBOT坐标z朝上
    robot.rotation.x = -Math.PI / 2;
    robot.rotation.z = -Math.PI;
    robot.position.set(-0.2, 0.5, -0.1); // 将机械臂放置在实验台上
    scene.add(robot);
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

// 移除positionUpdateInterval定时器，因为render函数已经在每帧更新
onMounted(() => {
  fetchData();
  document.getElementById("webgl").appendChild(renderer.domElement);
  render();

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.innerWidth / window.innerHeight);
  });

  setInterval(() => {
    if (isFetching.value && taskProgress.value < 95) {
      updateTaskProgress();
    }
  }, 2000);

  // 移除这个定时器，因为render函数已经在每帧更新位置信息
  // positionUpdateInterval.value = setInterval(() => {
  //   if (robot && robot.joints) {
  //     calculateEndEffectorPosition();
  //   }
  // }, 100);
});
// 在onBeforeUnmount中也需要移除对应的清除代码
onBeforeUnmount(() => {
  stopFetchingData();
  // 移除清除定时器的代码
  // clearInterval(positionUpdateInterval.value);
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

/* 在小屏幕上调整布局 */
@media (max-width: 1200px) {
  .panel-controls {
    flex-wrap: wrap;
    justify-content: center;
    width: calc(100% - 40px);
    max-width: 600px;
  }
}
</style>
