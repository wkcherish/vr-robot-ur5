<template>
  <div class="robot-container">
    <!-- 机器臂位置信息面板 - 始终显示 -->
    <div class="position-panel">
      <h3 class="panel-title">机器臂位置信息</h3>

      <div class="panel-section">
        <h4 class="section-title">末端位置</h4>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">X:</span>
            <span class="value"
              >{{ endEffectorPose.position.x.toFixed(3) }}
              <small>m</small></span
            >
          </div>
          <div class="data-item">
            <span class="label">Y:</span>
            <span class="value"
              >{{ endEffectorPose.position.y.toFixed(3) }}
              <small>m</small></span
            >
          </div>
          <div class="data-item">
            <span class="label">Z:</span>
            <span class="value"
              >{{ endEffectorPose.position.z.toFixed(3) }}
              <small>m</small></span
            >
          </div>
        </div>
      </div>

      <div class="panel-section">
        <h4 class="section-title">末端姿态</h4>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">Roll:</span>
            <span class="value"
              >{{
                ((endEffectorPose.orientation.roll * Math.PI) / 180).toFixed(4)
              }}
              <small>rad</small></span
            >
          </div>
          <div class="data-item">
            <span class="label">Pitch:</span>
            <span class="value"
              >{{
                ((endEffectorPose.orientation.pitch * Math.PI) / 180).toFixed(4)
              }}
              <small>rad</small></span
            >
          </div>
          <div class="data-item">
            <span class="label">Yaw:</span>
            <span class="value"
              >{{
                ((endEffectorPose.orientation.yaw * Math.PI) / 180).toFixed(4)
              }}
              <small>rad</small></span
            >
          </div>
        </div>
      </div>
    </div>

    <!-- 滑块控制区域 - 根据 prop 控制显示/隐藏 -->
    <div class="slider-block" v-show="showSliderControls">
      <div class="slider-grid">
        <div class="slider-item" v-for="(joint, index) in joints" :key="index">
          <p class="demonstration">关节{{ index + 1 }}</p>
          <el-slider
            v-model="joint.value"
            :min="min"
            :max="max"
            :step="1"
            @input="sliderInput(joint.value, joint.name)"
          />
          <el-input-number
            v-model="joint.value"
            type="number"
            @input="sliderInput(joint.value, joint.name)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineEmits, computed, defineProps } from "vue";

// 新增 props 定义
const props = defineProps({
  showSliderControls: {
    type: Boolean,
    default: true,
  },
});

const emit = defineEmits(["sliderInput"]);
const min = -180;
const max = 180;

// 定义关节
const joints = ref([
  { name: "link1_joint", value: 0 },
  { name: "link2_joint", value: -90 },
  { name: "link3_joint", value: 90 },
  { name: "link4_joint", value: -90 },
  { name: "link5_joint", value: -90 },
  { name: "link6_joint", value: 0 },
]);

const sliderInput = (value, name) => {
  const radianValue = value * (Math.PI / 180);
  console.log(
    `Slider Input: ${value} degrees (${radianValue} radians) for ${name}`
  );
  emit("sliderInput", radianValue, name);
};

// 计算末端位置和姿态
const endEffectorPose = computed(() => {
  const jointAngles = joints.value.map((joint) => joint.value);
  return calculateForwardKinematics(jointAngles);
});

// 正向运动学计算函数
function calculateForwardKinematics(jointAngles) {
  // 将角度转换为弧度
  const radians = jointAngles.map((deg) => (deg * Math.PI) / 180);

  // 机器人的D-H参数 [a, alpha, d, theta]
  // 注意：以下是示例D-H参数，需要根据实际机器人模型进行调整
  const dhParams = [
    // link1_joint
    [0, Math.PI / 2, 0.1, radians[0]],
    // link2_joint
    [0.4, 0, 0, radians[1]],
    // link3_joint
    [0.3, 0, 0, radians[2]],
    // link4_joint
    [0, Math.PI / 2, 0, radians[3]],
    // link5_joint
    [0, -Math.PI / 2, 0.1, radians[4]],
    // link6_joint
    [0, 0, 0.1, radians[5]],
  ];

  // 计算每个关节的变换矩阵
  const transformMatrices = dhParams.map(([a, alpha, d, theta]) => {
    const ct = Math.cos(theta);
    const st = Math.sin(theta);
    const ca = Math.cos(alpha);
    const sa = Math.sin(alpha);

    return [
      [ct, -st * ca, st * sa, a * ct],
      [st, ct * ca, -ct * sa, a * st],
      [0, sa, ca, d],
      [0, 0, 0, 1],
    ];
  });

  // 计算从基座到末端执行器的总变换矩阵
  let T = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ]; // 单位矩阵
  for (const matrix of transformMatrices) {
    T = multiplyMatrices(T, matrix);
  }

  // 从总变换矩阵中提取位置和姿态
  const position = {
    x: T[0][3],
    y: T[1][3],
    z: T[2][3],
  };

  // 从旋转矩阵中提取欧拉角 (roll, pitch, yaw)
  const roll = Math.atan2(T[2][1], T[2][2]);
  const pitch = Math.atan2(
    -T[2][0],
    Math.sqrt(T[2][1] * T[2][1] + T[2][2] * T[2][2])
  );
  const yaw = Math.atan2(T[1][0], T[0][0]);

  // 转换为角度
  const orientation = {
    roll: (roll * 180) / Math.PI,
    pitch: (pitch * 180) / Math.PI,
    yaw: (yaw * 180) / Math.PI,
  };

  return { position, orientation };
}

// 矩阵乘法辅助函数
function multiplyMatrices(A, B) {
  const rowsA = A.length;
  const colsA = A[0].length;
  const rowsB = B.length;
  const colsB = B[0].length;

  if (colsA !== rowsB) {
    throw new Error("矩阵维度不匹配");
  }

  const C = Array(rowsA)
    .fill()
    .map(() => Array(colsB).fill(0));

  for (let i = 0; i < rowsA; i++) {
    for (let j = 0; j < colsB; j++) {
      for (let k = 0; k < colsA; k++) {
        C[i][j] += A[i][k] * B[k][j];
      }
    }
  }

  return C;
}
</script>

<style>
.robot-container {
  position: relative;
}
.slider-block {
  padding: 20px;
  box-sizing: border-box;
  position: fixed; /* 添加了缺少的分号 */
  bottom: 150px; /* 改为距离底部50px */
  right: 20px;
  width: 30%;
  max-width: 400px;
  background-color: rgba(255, 255, 255, 0.7);
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

.position-panel {
  padding: 20px;
  box-sizing: border-box;
  position: fixed !important;
  top: 20px;
  right: 20px;
  width: 30%;
  max-width: 400px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000 !important;
  display: block !important;
  visibility: visible !important;
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
}

.section-title {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
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

.slider-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.slider-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  font-size: 12px;
}

.demonstration {
  font-size: 12px;
}

.position-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.position-item {
  text-align: center;
  font-size: 12px;
}
</style>
