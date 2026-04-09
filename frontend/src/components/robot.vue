<template>
  <div class="robot-container" v-show="showSliderControls">
    <div class="robot-panel">
      <h3 class="panel-title">机械臂位置信息</h3>

      <div class="panel-section">
        <h4 class="section-title">末端位置</h4>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">X:</span>
            <span class="value">{{ endEffectorPose.position.x.toFixed(3) }} <small>m</small></span>
          </div>
          <div class="data-item">
            <span class="label">Y:</span>
            <span class="value">{{ endEffectorPose.position.y.toFixed(3) }} <small>m</small></span>
          </div>
          <div class="data-item">
            <span class="label">Z:</span>
            <span class="value">{{ endEffectorPose.position.z.toFixed(3) }} <small>m</small></span>
          </div>
        </div>
      </div>

      <div class="panel-section">
        <h4 class="section-title">末端姿态</h4>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">Roll:</span>
            <span class="value">
              {{ ((endEffectorPose.orientation.roll * Math.PI) / 180).toFixed(4) }}
              <small>rad</small>
            </span>
          </div>
          <div class="data-item">
            <span class="label">Pitch:</span>
            <span class="value">
              {{ ((endEffectorPose.orientation.pitch * Math.PI) / 180).toFixed(4) }}
              <small>rad</small>
            </span>
          </div>
          <div class="data-item">
            <span class="label">Yaw:</span>
            <span class="value">
              {{ ((endEffectorPose.orientation.yaw * Math.PI) / 180).toFixed(4) }}
              <small>rad</small>
            </span>
          </div>
        </div>
      </div>

      <div class="panel-section panel-section-last">
        <h4 class="section-title">关节控制</h4>
        <div class="slider-grid">
          <div class="slider-item" v-for="(joint, index) in joints" :key="joint.name">
            <p class="demonstration">{{ joint.label || `关节${index + 1}` }}</p>
            <el-slider
              v-model="joint.value"
              :min="joint.min"
              :max="joint.max"
              :step="joint.step"
              @input="sliderInput(joint.value, joint.name)"
              @change="sliderCommit(joint.value, joint.name)"
            />
            <el-input-number
              v-model="joint.value"
              :min="joint.min"
              :max="joint.max"
              :step="joint.step"
              type="number"
              @input="sliderInput(joint.value, joint.name)"
              @change="sliderCommit(joint.value, joint.name)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const DEFAULT_JOINT_VALUES = [0, -90, 90, -90, -90, 0, 0];
const JOINT_CONFIG = [
  { name: "link1_joint", label: "关节1", min: -180, max: 180, step: 1 },
  { name: "link2_joint", label: "关节2", min: -180, max: 180, step: 1 },
  { name: "link3_joint", label: "关节3", min: -180, max: 180, step: 1 },
  { name: "link4_joint", label: "关节4", min: -180, max: 180, step: 1 },
  { name: "link5_joint", label: "关节5", min: -180, max: 180, step: 1 },
  { name: "link6_joint", label: "关节6", min: -180, max: 180, step: 1 },
  { name: "gripper_joint", label: "手抓", min: 0, max: 50, step: 1 },
];

const props = defineProps({
  showSliderControls: {
    type: Boolean,
    default: true,
  },
  jointValues: {
    type: Array,
    default: () => [0, -90, 90, -90, -90, 0, 0],
  },
});

const emit = defineEmits(["sliderInput", "sliderCommit"]);

const joints = ref(
  JOINT_CONFIG.map((joint, index) => ({
    ...joint,
    value: Number.isFinite(Number(props.jointValues?.[index]))
      ? Number(props.jointValues[index])
      : DEFAULT_JOINT_VALUES[index],
  }))
);

watch(
  () => props.jointValues,
  (values) => {
    if (!Array.isArray(values)) return;
    joints.value.forEach((joint, index) => {
      const nextValue = Number(values[index]);
      if (!Number.isFinite(nextValue)) return;
      joint.value = nextValue;
    });
  },
  { deep: true, immediate: true }
);

const sliderInput = (value, name) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return;
  const radianValue = (numericValue * Math.PI) / 180;
  emit("sliderInput", radianValue, name);
};

const sliderCommit = (value, name) => {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return;
  const radianValue = (numericValue * Math.PI) / 180;
  emit("sliderCommit", radianValue, name);
};

const endEffectorPose = computed(() => {
  const jointAngles = joints.value.slice(0, 6).map((joint) => joint.value);
  return calculateForwardKinematics(jointAngles);
});

function calculateForwardKinematics(jointAngles) {
  const radians = jointAngles.map((deg) => (deg * Math.PI) / 180);

  const dhParams = [
    [0, Math.PI / 2, 0.1, radians[0]],
    [0.4, 0, 0, radians[1]],
    [0.3, 0, 0, radians[2]],
    [0, Math.PI / 2, 0, radians[3]],
    [0, -Math.PI / 2, 0.1, radians[4]],
    [0, 0, 0.1, radians[5]],
  ];

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

  let T = [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];

  for (const matrix of transformMatrices) {
    T = multiplyMatrices(T, matrix);
  }

  const position = {
    x: T[0][3],
    y: T[1][3],
    z: T[2][3],
  };

  const roll = Math.atan2(T[2][1], T[2][2]);
  const pitch = Math.atan2(
    -T[2][0],
    Math.sqrt(T[2][1] * T[2][1] + T[2][2] * T[2][2])
  );
  const yaw = Math.atan2(T[1][0], T[0][0]);

  const orientation = {
    roll: (roll * 180) / Math.PI,
    pitch: (pitch * 180) / Math.PI,
    yaw: (yaw * 180) / Math.PI,
  };

  return { position, orientation };
}

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
  position: fixed;
  top: 20px;
  right: 20px;
  width: min(32vw, 420px);
  min-width: 320px;
  max-height: calc(100vh - 120px);
  z-index: 900;
}

.robot-panel {
  padding: 16px;
  box-sizing: border-box;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  overflow-y: auto;
  max-height: 100%;
}

.panel-title {
  margin-top: 0;
  margin-bottom: 12px;
  color: #333;
  font-size: 18px;
  text-align: center;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.panel-section {
  margin-bottom: 14px;
}

.panel-section-last {
  margin-bottom: 0;
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
  font-weight: 700;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.slider-item {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  text-align: center;
  font-size: 12px;
}

.demonstration {
  font-size: 12px;
  margin: 0 0 4px 0;
  color: #555;
}

@media (max-width: 1200px) {
  .robot-container {
    width: min(92vw, 420px);
    min-width: 0;
    right: 12px;
    top: 12px;
    max-height: calc(100vh - 140px);
  }
}
</style>
