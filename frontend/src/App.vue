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

        <div class="scene-restore-panel" v-show="showTaskProgress">
          <div class="scene-restore-header">
            <div class="scene-restore-title">场景复原</div>
          </div>
          <button
            class="scene-restore-button"
            :disabled="sceneRestorePending || datasetEpisodeActive || datasetEpisodeInFlight || datasetAutoCollecting"
            @click="restoreSceneToInitialState"
          >
            {{ sceneRestorePending ? "复原中..." : "恢复初始场景" }}
          </button>
          <div
            class="scene-restore-status"
            :class="{
              'status-success': sceneRestoreStatusTone === 'success',
              'status-error': sceneRestoreStatusTone === 'error',
            }"
          >
            {{ sceneRestoreStatusMessage }}
          </div>
        </div>

        <D405ObservationPanel
          v-if="showD405Panel"
          :snapshot="simulationState"
          @close="showD405Panel = false"
        />

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
              <div class="network-status-row" v-if="questControllerRawInput && (questControllerRawInput.left || questControllerRawInput.right)">
                <span class="network-label">手柄握柄/扳机:</span>
                <span class="network-value">
                  L G={{ Number(questControllerRawInput.left?.grip || 0).toFixed(2) }},
                  L T={{ Number(questControllerRawInput.left?.trigger || 0).toFixed(2) }},
                  R G={{ Number(questControllerRawInput.right?.grip || 0).toFixed(2) }},
                  R T={{ Number(questControllerRawInput.right?.trigger || 0).toFixed(2) }}
                </span>
              </div>
              <div class="network-status-row" v-if="questControllerNormalizedInput">
                <span class="network-label">活跃/目标:</span>
                <span class="network-value">
                  {{ questControllerNormalizedInput.active_hand || "-" }}
                  Δ=({{ Number(questControllerNormalizedInput.target_dx || 0).toFixed(2) }},
                  {{ Number(questControllerNormalizedInput.target_dy || 0).toFixed(2) }},
                  {{ Number(questControllerNormalizedInput.target_dz || 0).toFixed(2) }})m
                </span>
              </div>
              <div class="network-status-row" v-if="questControllerNormalizedInput">
                <span class="network-label">控制状态:</span>
                <span class="network-value">
                  cmd={{ Number(questControllerNormalizedInput.has_command || 0) >= 1 ? "1" : "0" }},
                  reason={{ questControllerNormalizedInput.reason || "-" }},
                  grip={{ Number(questControllerNormalizedInput.grip || 0).toFixed(2) }},
                  pose={{ questControllerNormalizedInput.pose_source || "-" }}
                </span>
              </div>
              <div class="network-status-row" v-if="questControllerNormalizedInput">
                <span class="network-label">末端误差:</span>
                <span class="network-value">
                  pos={{ Number(questControllerNormalizedInput.ee_error_m || 0).toFixed(3) }}m,
                  rot={{ Number(questControllerNormalizedInput.orientation_error_rad || 0).toFixed(2) }}rad,
                  Servo={{ questControllerNormalizedInput.cartesian_servo_status || questControllerNormalizedInput.ik_status || "-" }}
                </span>
              </div>
              <div class="network-status-row" v-if="questControllerNormalizedInput">
                <span class="network-label">姿态跟随:</span>
                <span class="network-value">
                  {{ Number(questControllerNormalizedInput.orientation_follow_enabled || questControllerNormalizedInput.ee_orientation_follow_enabled || questControllerNormalizedInput.cartesian_servo_orientation_enabled || 0) >= 1 ? "开启" : "锁定" }}
                  | {{ questControllerNormalizedInput.ee_follow_mode || "-" }}
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">灵敏度:</span>
                <span class="network-value">
                  <input
                    class="vr-inline-slider"
                    type="range"
                    min="0.4"
                    max="3.0"
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
                    questHandRawInput && questHandRawInput.right_controller_fallback
                      ? "右控制器兜底模式"
                      : questHandInputMode === "right_hand_ee_servo" || questHandInputMode === "right_hand_ee_ik"
                        ? "右手末端伺服模式"
                        : questHandInputMode === "right_hand"
                          ? "右手单手模式"
                        : questHandInputMode === "dual_hand"
                          ? "双手模式"
                          : "单手降级模式"
                  }}
                </span>
              </div>
              <div
                class="network-status-row"
                v-if="questHandRawInput && questHandRawInput.right"
              >
                <span class="network-label">右手追踪:</span>
                <span class="network-value">
                  {{
                    questHandRawInput.right && (questHandRawInput.right.tracked || questHandRawInput.right.recently_tracked)
                      ? "可用"
                      : "丢失"
                  }}
                  ({{ (((questHandRawInput.right && questHandRawInput.right.stability) || 0) * 100).toFixed(0) }}%)
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">控制目标:</span>
                <span class="network-value">{{ vrSelectedJointGroupText }}</span>
              </div>
              <div class="network-status-row" v-if="questHandNormalizedInput">
                <span class="network-label">手掌目标:</span>
                <span class="network-value">
                  Δ=({{ Number(questHandNormalizedInput.target_dx || 0).toFixed(2) }},
                  {{ Number(questHandNormalizedInput.target_dy || 0).toFixed(2) }},
                  {{ Number(questHandNormalizedInput.target_dz || 0).toFixed(2) }})m
                </span>
              </div>
              <div class="network-status-row" v-if="questHandNormalizedInput">
                <span class="network-label">末端误差:</span>
                <span class="network-value">
                  pos={{ Number(questHandNormalizedInput.ee_error_m || 0).toFixed(3) }}m,
                  rot={{ Number(questHandNormalizedInput.orientation_error_rad || 0).toFixed(2) }}rad,
                  Servo={{ questHandNormalizedInput.cartesian_servo_status || questHandNormalizedInput.ik_status || "-" }}
                </span>
              </div>
              <div class="network-status-row" v-if="questHandNormalizedInput">
                <span class="network-label">姿态跟随:</span>
                <span class="network-value">
                  {{ Number(questHandNormalizedInput.orientation_follow_enabled || questHandNormalizedInput.ee_orientation_follow_enabled || questHandNormalizedInput.cartesian_servo_orientation_enabled || 0) >= 1 ? "开启" : "锁定" }}
                  | {{ questHandNormalizedInput.ee_follow_mode || "-" }}
                </span>
              </div>
              <div class="network-status-row" v-if="questHandNormalizedInput">
                <span class="network-label">拳握/夹爪:</span>
                <span class="network-value">
                  fist={{ Number(questHandNormalizedInput.fist || 0).toFixed(2) }},
                  grip={{ Number(questHandNormalizedInput.grip || 0).toFixed(2) }}
                </span>
              </div>
              <div class="network-status-row">
                <span class="network-label">手势灵敏度:</span>
                <span class="network-value">
                  <input
                    class="vr-inline-slider"
                    type="range"
                    min="0.4"
                    max="3.0"
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
            <div class="vr-section-title">VR采集模式</div>
            <div class="dataset-status-strip">
              <span class="dataset-pill" :class="datasetRecordingReady ? 'status-ok' : 'status-error'">
                recording_ready={{ datasetRecordingReady ? "true" : "false" }}
              </span>
              <span class="dataset-pill" :class="datasetEpisodeActive ? 'status-checking' : 'status-unknown'">
                {{ datasetEpisodeActive ? "episode录制中" : "episode空闲" }}
              </span>
              <span class="dataset-pill" :class="datasetAutoCollecting ? 'status-checking' : 'status-unknown'">
                {{ datasetAutoCollecting ? `连续采集 episode${datasetAutoEpisodeIndex}` : "连续采集空闲" }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">D405:</span>
              <span class="network-value" :class="`status-${d405CheckStatus}`">
                {{ normalizeStatusLabel(d405CheckStatus) }} | {{ d405CheckMessage }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">WebSocket:</span>
              <span class="network-value" :class="`status-${wsCheckStatus}`">
                {{ normalizeStatusLabel(wsCheckStatus) }} | {{ wsCheckMessage }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">控制模式:</span>
              <span class="network-value">{{ datasetControlModeText }}</span>
            </div>
            <div class="network-status-row">
              <span class="network-label">最近错误:</span>
              <span class="network-value" :class="{ 'status-error': datasetLastError }">
                {{ datasetLastError || "-" }}
              </span>
            </div>
            <div class="network-status-row">
              <span class="network-label">视野确认:</span>
              <span class="network-value">
                {{ datasetPrecheck?.camera_view_verification?.verified_at ? `已确认 @ ${datasetPrecheck.camera_view_verification.verified_at}` : "未确认" }}
              </span>
            </div>
            <button
              class="network-check-button dataset-precheck-button"
              :disabled="datasetPrecheckInFlight"
              @click="runDatasetPrecheck"
            >
              {{ datasetPrecheckInFlight ? "检查中..." : "执行precheck" }}
            </button>
            <button
              class="network-check-button dataset-precheck-button"
              :disabled="datasetCameraViewVerifyInFlight"
              @click="verifyDatasetCameraView"
            >
              {{ datasetCameraViewVerifyInFlight ? "确认中..." : "确认当前D405视野可用" }}
            </button>
            <div class="dataset-form-grid">
              <label class="dataset-field">
                <span class="dataset-label">任务模板</span>
                <select
                  class="dataset-select"
                  v-model="selectedDatasetTaskType"
                  @change="handleDatasetTemplateChanged"
                  :disabled="datasetEpisodeActive"
                >
                  <option
                    v-for="template in datasetTemplates"
                    :key="template.task_type"
                    :value="template.task_type"
                  >
                    {{ template.display_name || template.task_type }}
                  </option>
                </select>
              </label>
              <label class="dataset-field">
                <span class="dataset-label">目标工具</span>
                <select
                  class="dataset-select"
                  v-model="selectedDatasetTargetTool"
                  @change="syncDatasetInstructionFromTemplate(true)"
                  :disabled="datasetEpisodeActive"
                >
                  <option
                    v-for="tool in datasetTargetTools"
                    :key="tool.id"
                    :value="tool.id"
                  >
                    {{ tool.display_name || tool.id }}
                  </option>
                </select>
              </label>
              <label class="dataset-field">
                <span class="dataset-label">目标区域</span>
                <select
                  class="dataset-select"
                  v-model="selectedDatasetTargetZone"
                  :disabled="datasetEpisodeActive"
                >
                  <option
                    v-for="zone in datasetTargetZones"
                    :key="zone.id"
                    :value="zone.id"
                  >
                    {{ zone.display_name || zone.id }}
                  </option>
                </select>
              </label>
              <label class="dataset-field">
                <span class="dataset-label">采集等级</span>
                <select
                  class="dataset-select"
                  v-model="selectedDatasetCollectionStage"
                  :disabled="datasetEpisodeActive"
                >
                  <option
                    v-for="stage in datasetCollectionStageOptions"
                    :key="stage"
                    :value="stage"
                  >
                    {{ formatDatasetStage(stage) }}
                  </option>
                </select>
              </label>
            </div>
            <label class="dataset-field full-width">
              <span class="dataset-label">任务文本</span>
              <textarea
                class="dataset-textarea"
                v-model="datasetInstructionText"
                :disabled="datasetEpisodeActive"
                rows="2"
                @input="datasetInstructionEdited = true"
              ></textarea>
            </label>
            <div class="dataset-form-grid compact">
              <label class="dataset-field">
                <span class="dataset-label">结果标记</span>
                <select class="dataset-select" v-model="datasetResultStatus">
                  <option value="success">成功</option>
                  <option value="failed_attempt">失败尝试</option>
                  <option value="operator_abort">操作者中止</option>
                  <option value="unknown">未定</option>
                </select>
              </label>
              <label class="dataset-field">
                <span class="dataset-label">质量标签</span>
                <select class="dataset-select" v-model="datasetQualityLabel">
                  <option value="debug_only">debug_only</option>
                  <option value="train_candidate">train_candidate</option>
                  <option value="eval_candidate">eval_candidate</option>
                  <option value="rejected">rejected</option>
                </select>
              </label>
            </div>
            <div class="dataset-action-row">
              <button
                class="dataset-button primary"
                :disabled="!datasetCanStartEpisode || datasetAutoCollecting"
                @click="startDatasetEpisode"
              >
                {{ datasetEpisodeInFlight ? "处理中..." : "开始episode" }}
              </button>
              <button
                class="dataset-button danger"
                :disabled="!datasetCanStopEpisode || datasetAutoCollecting"
                @click="stopDatasetEpisode"
              >
                停止并标记
              </button>
              <button
                class="dataset-button"
                :disabled="!datasetCanUpdateResult"
                @click="updateDatasetEpisodeResult"
              >
                更新结果
              </button>
            </div>
            <div class="dataset-form-grid compact">
              <label class="dataset-field">
                <span class="dataset-label">单轮秒数</span>
                <input
                  class="dataset-select"
                  type="number"
                  min="3"
                  max="3600"
                  step="1"
                  v-model.number="datasetAutoEpisodeDurationSec"
                  :disabled="datasetAutoCollecting"
                />
              </label>
              <label class="dataset-field">
                <span class="dataset-label">轮数(0不限)</span>
                <input
                  class="dataset-select"
                  type="number"
                  min="0"
                  max="9999"
                  step="1"
                  v-model.number="datasetAutoMaxEpisodes"
                  :disabled="datasetAutoCollecting"
                />
              </label>
            </div>
            <div class="dataset-auto-row">
              <label class="dataset-toggle">
                <input type="checkbox" v-model="datasetVoiceEnabled" />
                <span>语音提示</span>
              </label>
              <span class="dataset-auto-status">{{ datasetAutoStatusText }}</span>
            </div>
            <div class="dataset-action-row dataset-auto-actions">
              <button
                class="dataset-button primary"
                :disabled="!datasetCanStartAutoCollection"
                @click="startDatasetAutoCollection"
              >
                开始连续采集
              </button>
              <button
                class="dataset-button danger"
                :disabled="!datasetCanStopAutoCollection"
                @click="stopDatasetAutoCollection"
              >
                停止连续采集
              </button>
            </div>
            <div v-if="datasetAutoVoiceText" class="dataset-message">{{ datasetAutoVoiceText }}</div>
            <div v-if="datasetActiveEpisodeId || datasetLastEpisodeId" class="dataset-episode-id">
              {{
                datasetEpisodeActive
                  ? `当前: ${datasetActiveEpisodeId}`
                  : `最近: ${datasetLastEpisodeId}`
              }}
            </div>
            <div v-if="datasetLastMessage" class="dataset-message">{{ datasetLastMessage }}</div>
            <div v-if="!datasetCanStartEpisode && datasetFormalModeSelected && !datasetRecordingReady" class="dataset-warning">
              precheck 未通过时只能采集 debug_trial。
            </div>
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
            <span class="panel-icon">♻️</span> 场景复原
          </button>
          <button
            @click="togglePanel('d405')"
            class="panel-control-button"
            :class="{ active: showD405Panel }"
          >
            <span class="panel-icon">▣</span> D405观测
          </button>
          <button
            @click="togglePanel('vr-control')"
            class="panel-control-button"
            :class="{ active: showVrControlPanel }"
          >
            <span class="panel-icon">VR</span> VR采集
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
const D405ObservationPanel = defineAsyncComponent(() => import("./components/D405ObservationPanel.vue"));
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
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
  getQuestXRReferenceSpace,
  getQuestXRSession,
  stopQuestXRSession,
} from "./utils/questXRSession.js";
import sceneManifest from "../../shared/scene_manifest.json";

// 修改视角控制为下拉菜单
const selectedView = ref("perspective"); // 默认选择透视视角
const sceneRestorePending = ref(false);
const sceneRestoreStatusMessage = ref("碰撞后可一键恢复 MuJoCo 与前端初始场景。");
const sceneRestoreStatusTone = ref("idle");

// 各面板显示状态控制
const showSlider = ref(false); // 滑块面板默认不显示
const showRobotPanel = ref(false); // 机器人控制面板默认不显示
const showControlPanel = ref(false); // 仿真控制面板默认不显示
const showViewControls = ref(true); // 视角控制默认显示
const showTaskProgress = ref(true); // 场景复原面板默认显示
const showVrControlPanel = ref(false); // VR控制中心默认不显示
const showD405Panel = ref(false); // D405 观测面板默认不显示
const ARM_JOINT_COUNT = 6;
const TOTAL_INPUT_JOINT_COUNT = 7;
const GRIPPER_MIN_RAD = 0;
const GRIPPER_MAX_RAD = 0.9;
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
const ARM_JOINT_NAMES = [...BACKEND_ARM_JOINT_NAMES];
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
const STRICT_MUJOCO_RENDER_AUTHORITY = true;
const SHOW_MUJOCO_COLLISION_PROXIES =
  String(import.meta.env.VITE_SHOW_MUJOCO_COLLISION_PROXIES || "").trim() === "1";
const CLIENT_PHYSICS_INTERFERENCE_EPSILON_M = 0.003;
const sliderJointValues = computed(() => {
  const draft = STRICT_MUJOCO_RENDER_AUTHORITY ? null : getFreshRealtimeSliderDraft();
  if (draft && Array.isArray(draft.arm) && draft.arm.length >= ARM_JOINT_COUNT) {
    const armAngles = draft.arm
      .slice(0, ARM_JOINT_COUNT)
      .map((value) => toDegrees(Number(value)));
    if (armAngles.every((value) => Number.isFinite(value))) {
      const gripperOpening = Number.isFinite(Number(draft.gripperOpening))
        ? clamp(Number(draft.gripperOpening), 0, 1)
        : getAuthoritativeGripperOpening();
      return [...armAngles, toDegrees(gripperOpening * GRIPPER_MAX_RAD)];
    }
  }

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
const desktopSliderControlSeq = ref(0);
const backendPoseSmoothingEnabled = ref(!STRICT_MUJOCO_RENDER_AUTHORITY);
const backendPoseSmoothingAlpha = ref(0.18);
const backendRenderTarget = ref(null);
const questRenderPreviewTarget = ref(null);
const lastRenderFrameAt = ref(0);

const REALTIME_SLIDER_DEBOUNCE_MS = 8;
const REALTIME_SLIDER_MIN_SEND_INTERVAL_MS = 16;
const REALTIME_SLIDER_COMMAND_STEPS = 40;
const REALTIME_SLIDER_DRAFT_TTL_MS = 4000;
const HTTP_STATE_FALLBACK_INTERVAL_MS = 33;
const MANUAL_STATE_GUARD_MS = 1100;
const VR_MANUAL_STATE_GUARD_MS = 1200;
const BACKEND_STATE_STALE_TOLERANCE_MS = 120;
const BACKEND_STATE_TIMESTAMP_EPSILON_MS = 1;
const ARM_STATE_MATCH_THRESHOLD_RAD = 0.01;
const GRIPPER_STATE_MATCH_THRESHOLD_RAD = 0.012;
const ARM_TARGET_ACCEPT_THRESHOLD_RAD = 0.015;
const GRIPPER_TARGET_ACCEPT_THRESHOLD_RAD = 0.02;
const MAX_RENDER_PIXEL_RATIO = 1.5;
const QUEST_MAX_RENDER_PIXEL_RATIO = 0.8;
const QUEST_XR_FRAMEBUFFER_SCALE = 0.82;
const UI_SYNC_INTERVAL_MS = 33;
const UI_POSE_SYNC_INTERVAL_MS = 50;
const UI_REACTIVE_MOTION_MIN_INTERVAL_MS = 250;
const SYNC_STATS_MIN_INTERVAL_MS = 250;
const VR_STATE_SYNC_MIN_INTERVAL_MS = 180;
const QUEST_TELEOP_UI_MIN_INTERVAL_MS = 125;
// 16ms caps teleop at about 62.5Hz, which is visibly below Quest's common
// 72Hz refresh. Use a slightly tighter send interval to reduce step feeling.
const VR_COMMAND_MIN_INTERVAL_MS = 16;
const VR_COMMAND_STEPS = 1;
const VR_MODE_TRANSITION_GUARD_MS = 420;
const VR_CONTROL_WATCHDOG_INTERVAL_MS = 33;
const VR_CONTROL_WATCHDOG_STALE_MS = 55;
const QUEST_CONTROLLER_GRIP_ENGAGE_THRESHOLD = 0.035;
const QUEST_CONTROLLER_GRIP_RELEASE_THRESHOLD = 0.018;
const QUEST_CONTROLLER_POSE_HOLD_MS = 380;
const VR_RENDER_SMOOTHING_ALPHA = 0.16;
const BACKEND_RENDER_PREDICTION_MS = 36;
const BACKEND_RENDER_MAX_PREDICTION_MS = 80;
const BACKEND_RENDER_TARGET_BLEND = 0.38;
const BACKEND_RENDER_MAX_QVEL_RAD_S = 4.5;
const BACKEND_RENDER_MAX_GRIPPER_QVEL_RAD_S = 3.0;
const QUEST_RENDER_PREVIEW_TTL_MS = 550;
const QUEST_PREVIEW_ARM_ALIGN_THRESHOLD_RAD = 0.075;
const QUEST_PREVIEW_GRIPPER_ALIGN_THRESHOLD_RAD = 0.08;
const RENDER_ARM_EPSILON_RAD = 2e-4;
const RENDER_GRIPPER_EPSILON_RAD = 2e-4;
const RENDER_ADAPTIVE_LOW_ERROR_RAD = 0.006;
const RENDER_ADAPTIVE_HIGH_ERROR_RAD = 0.18;
const DEBUG_VR_CONTROL_RESULTS = false;
const DATASET_CONTROLLER_NEXT_THRESHOLD = 0.65;
const DATASET_CONTROLLER_NEXT_COOLDOWN_MS = 900;

// WebSocket 状态同步相关
const isWebSocketConnected = ref(false);
const websocketStatus = ref("未连接");
const simulationState = ref(null); // 完整的仿真状态
const stateUpdateHistory = ref([]); // 状态更新历史，用于插值
const networkLatency = ref(0); // 网络延迟
const stateSyncErrors = ref(0); // 状态同步错误计数
const lastStateUpdate = ref(0); // 最后状态更新时间
const lastAcceptedBackendStateTimestampMs = ref(0);
const stateInterpolationEnabled = ref(!STRICT_MUJOCO_RENDER_AUTHORITY); // 启用状态插值
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
const questControllerSensitivity = ref(1.6);
const questControllerDeadzone = ref(0.1);
const questControllerGroupToast = ref("");
const questControllerGroupToastAt = ref(0);
const questControllerRawInput = ref(null);
const questControllerNormalizedInput = ref(null);
const questControllerFallbackInFlight = ref(false);
const lastQuestControllerTickAt = ref(0);
const lastQuestControllerSentAt = ref(0);
const questControllerQueuedFlushTimer = ref(null);
const questControllerPendingMapped = ref(null);
const questControllerControlSeq = ref(0);
const questHandAvailable = ref(false);
const questHandStatusText = ref("未激活");
const questHandSensitivity = ref(1.5);
const questHandTrackingStable = ref(false);
const questHandTrackingStability = ref(0);
const questHandInputMode = ref("right_hand_ee_servo");
const questHandGroupToast = ref("");
const questHandGroupToastAt = ref(0);
const questHandRawInput = ref(null);
const questHandNormalizedInput = ref(null);
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
const questXrPresentingLostSinceAt = ref(0);
const QUEST_HAND_UNSTABLE_GRACE_MS = 260;
const QUEST_HAND_UNAVAILABLE_GRACE_MS = 320;
const QUEST_XR_PRESENTING_LOST_GRACE_MS = 900;
const QUEST_XR_SOURCE_REFRESH_DELAY_MS = 120;

const datasetTemplates = ref([]);
const datasetTargetTools = ref([]);
const datasetTargetZones = ref([]);
const datasetCollectionStages = ref(["debug_trial", "pilot", "train_candidate", "eval_candidate", "rejected"]);
const selectedDatasetTaskType = ref("debug_trial");
const selectedDatasetTargetTool = ref("wrench_01");
const selectedDatasetTargetZone = ref("desk_drop_zone");
const selectedDatasetCollectionStage = ref("debug_trial");
const datasetInstructionText = ref("debug trial with the wrench");
const datasetPrecheck = ref(null);
const datasetRecordingReady = ref(false);
const datasetPrecheckInFlight = ref(false);
const datasetCameraViewVerifyInFlight = ref(false);
const datasetEpisodeInFlight = ref(false);
const datasetActiveEpisodeId = ref("");
const datasetLastEpisodeId = ref("");
const datasetLastEpisodeDir = ref("");
const datasetLastMessage = ref("");
const datasetLastError = ref("");
const datasetResultStatus = ref("success");
const datasetQualityLabel = ref("debug_only");
const datasetInstructionEdited = ref(false);
const datasetAutoCollecting = ref(false);
const datasetAutoStopRequested = ref(false);
const datasetAutoEpisodeIndex = ref(0);
const datasetAutoEpisodeDurationSec = ref(30);
const datasetAutoResetDelaySec = ref(2);
const datasetAutoMaxEpisodes = ref(0);
const datasetAutoStatus = ref("未启动");
const datasetAutoVoiceText = ref("");
const datasetVoiceEnabled = ref(true);
const datasetAutoDelayTimer = ref(null);
const datasetControllerNextWasPressed = ref(false);
const lastDatasetControllerNextAt = ref(0);
let datasetAutoDelayResolver = null;

datasetTemplates.value = [
  {
    task_type: "debug_trial",
    display_name: "Debug Trial",
    allowed_collection_stages: ["debug_trial", "rejected"],
    default_instruction_by_class: {
      wrench: "debug trial with the wrench",
      screwdriver: "debug trial with the screwdriver",
      pliers: "debug trial with the pliers",
    },
  },
  {
    task_type: "tool_grasp",
    display_name: "Tool Grasp",
    allowed_collection_stages: ["pilot", "train_candidate", "eval_candidate", "rejected"],
    default_instruction_by_class: {
      wrench: "pick up the wrench",
      screwdriver: "pick up the screwdriver",
      pliers: "pick up the pliers",
    },
  },
  {
    task_type: "tool_pick_place",
    display_name: "Tool Pick Place",
    allowed_collection_stages: ["pilot", "train_candidate", "eval_candidate", "rejected"],
    default_instruction_by_class: {
      wrench: "place the wrench in the toolbox",
      screwdriver: "place the screwdriver in the toolbox",
      pliers: "place the pliers in the toolbox",
    },
  },
  {
    task_type: "tool_reposition",
    display_name: "Tool Reposition",
    allowed_collection_stages: ["pilot", "train_candidate", "eval_candidate", "rejected"],
    default_instruction_by_class: {
      wrench: "move the wrench to the target zone",
      screwdriver: "move the screwdriver to the target zone",
      pliers: "move the pliers to the target zone",
    },
  },
];
datasetTargetTools.value = [
  { id: "wrench_01", class_id: "wrench", display_name: "Wrench #1" },
  { id: "screwdriver_01", class_id: "screwdriver", display_name: "Screwdriver #1" },
  { id: "pliers_01", class_id: "pliers", display_name: "Pliers #1" },
];
datasetTargetZones.value = [
  { id: "desk_drop_zone", type: "spawn_region", display_name: "desk_drop_zone" },
  { id: "slot_wrench", type: "toolbox_slot", display_name: "slot_wrench" },
  { id: "slot_screwdriver", type: "toolbox_slot", display_name: "slot_screwdriver" },
  { id: "slot_pliers", type: "toolbox_slot", display_name: "slot_pliers" },
  { id: "toolbox", type: "container", display_name: "toolbox" },
];

const VR_MODE_LOCAL_LOCK_MS = 1200;
const VR_ENTERED_MODES = new Set(["vr_ready", "vr_controller_mode", "vr_hand_mode"]);

const uiLastJointSyncAt = ref(0);
const uiLastPoseSyncAt = ref(0);

let questControllerTeleop = createQuestControllerTeleop({
  sensitivity: clamp(questControllerSensitivity.value, 0.4, 3.0),
  ...getQuestControllerTeleopThresholds(),
});
let questHandTeleop = createQuestHandTeleop({
  sensitivity: clamp(questHandSensitivity.value, 0.4, 3.0),
});
let lastQuestControllerPoseSnapshot = null;
let latestMotionState = null;
let lastReactiveMotionCommitAt = 0;
let lastQuestControllerUiCommitAt = 0;
let lastQuestHandUiCommitAt = 0;
let lastSyncStatsCommitAt = 0;
let lastMotionPacketAt = 0;

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

const selectedDatasetTemplate = computed(() => {
  return (
    datasetTemplates.value.find(
      (template) => String(template?.task_type || "") === selectedDatasetTaskType.value
    ) || null
  );
});

const selectedDatasetTool = computed(() => {
  return (
    datasetTargetTools.value.find(
      (tool) => String(tool?.id || "") === selectedDatasetTargetTool.value
    ) || null
  );
});

const datasetEpisodeActive = computed(() => Boolean(datasetActiveEpisodeId.value));

const datasetFormalModeSelected = computed(() => selectedDatasetCollectionStage.value !== "debug_trial");

const datasetCollectionStageOptions = computed(() => {
  const allowed = selectedDatasetTemplate.value?.allowed_collection_stages;
  if (Array.isArray(allowed) && allowed.length > 0) {
    return allowed.map((stage) => String(stage));
  }
  return datasetCollectionStages.value;
});

const datasetControlMode = computed(() => {
  if (selectedVrInputMode.value === "hand" || vrModeState.value === "vr_hand_mode") {
    return "vr_hand";
  }
  return "vr_controller";
});

const datasetRobotInputSource = computed(() => {
  return datasetControlMode.value === "vr_hand" ? "quest3_hand" : "quest3_controller";
});

const datasetControlModeText = computed(() => {
  return datasetControlMode.value === "vr_hand" ? "VR手势 / quest3_hand" : "VR手柄 / quest3_controller";
});

const datasetCanStartEpisode = computed(() => {
  if (datasetEpisodeInFlight.value || datasetEpisodeActive.value) return false;
  if (!isVrModeEntered.value) return false;
  if (!selectedDatasetTaskType.value || !selectedDatasetTargetTool.value) return false;
  if (!String(datasetInstructionText.value || "").trim()) return false;
  if (selectedDatasetCollectionStage.value === "debug_trial") return true;
  return datasetRecordingReady.value;
});

const datasetCanStopEpisode = computed(() => {
  return datasetEpisodeActive.value && !datasetEpisodeInFlight.value;
});

const datasetCanUpdateResult = computed(() => {
  return Boolean(datasetLastEpisodeId.value) && !datasetEpisodeInFlight.value;
});

const datasetCanStartAutoCollection = computed(() => {
  if (datasetAutoCollecting.value || datasetEpisodeInFlight.value || datasetEpisodeActive.value) return false;
  if (!isVrModeEntered.value) return false;
  if (!selectedDatasetTaskType.value || !selectedDatasetTargetTool.value) return false;
  return Boolean(String(datasetInstructionText.value || "").trim());
});

const datasetCanStopAutoCollection = computed(() => {
  return datasetAutoCollecting.value || datasetAutoStopRequested.value;
});

const datasetAutoStatusText = computed(() => {
  if (datasetAutoCollecting.value) {
    return `${datasetAutoStatus.value} | episode${datasetAutoEpisodeIndex.value}`;
  }
  return datasetAutoStatus.value || "未启动";
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
    datasetRecordingReady.value;
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
    backendInputMode === "right_hand_ee_servo" ||
    backendInputMode === "right_hand_ee_ik" ||
    backendInputMode === "right_hand" ||
    backendInputMode === "left_hand_ee_ik" ||
    backendInputMode === "left_hand_ee_servo" ||
    backendInputMode === "left_hand" ||
    backendInputMode === "dual_hand" ||
    backendInputMode === "single_hand"
  ) {
    questHandInputMode.value = backendInputMode;
  }
}

function getQuestControllerTeleopThresholds() {
  const deadzone = clamp(questControllerDeadzone.value, 0.02, 0.3);
  return {
    grip_engage_threshold: QUEST_CONTROLLER_GRIP_ENGAGE_THRESHOLD,
    grip_release_threshold: QUEST_CONTROLLER_GRIP_RELEASE_THRESHOLD,
    trigger_engage_threshold: deadzone,
    trigger_release_threshold: Math.max(0.01, deadzone * 0.55),
    stick_activity_epsilon: deadzone,
  };
}

function checkD405ObservationReady(state) {
  const camera = state?.camera || state;
  const cameraDevice = String(camera?.device || camera?.camera_device || "");
  const rgbName = String(camera?.rgb?.interface_name || "");
  const depthName = String(camera?.depth?.interface_name || "");
  const captureOk = Boolean(state?.camera_capture_ok ?? camera?.camera_capture_ok);
  const frameAligned = Boolean(camera?.frame_aligned);
  const recordable = Boolean(camera?.recordable_training_observation);
  const sourceOk = Boolean(camera?.camera_source_ok ?? true);
  const stubFrameUsed = Boolean(camera?.stub_frame_used);

  const isD405 = cameraDevice === "intel_realsense_d405";
  const hasStreams = rgbName.length > 0 && depthName.length > 0;

  if (isD405 && hasStreams && captureOk && frameAligned && recordable && sourceOk && !stubFrameUsed) {
    d405CheckStatus.value = "ok";
    d405CheckMessage.value = "D405 RGB-D 已就绪";
    return;
  }

  d405CheckStatus.value = "error";
  d405CheckMessage.value = camera?.last_error || "D405 观测链未就绪";
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

function getDatasetRecordingReady() {
  return Boolean(datasetRecordingReady.value);
}

function formatDatasetStage(stage) {
  const mapping = {
    debug_trial: "debug_trial",
    pilot: "pilot",
    train_candidate: "train_candidate",
    eval_candidate: "eval_candidate",
    rejected: "rejected",
  };
  return mapping[stage] || String(stage || "");
}

function inferToolClassFromId(toolId) {
  const id = String(toolId || "");
  if (id.startsWith("wrench")) return "wrench";
  if (id.startsWith("screwdriver")) return "screwdriver";
  if (id.startsWith("pliers")) return "pliers";
  return "tool";
}

function buildDefaultDatasetInstruction() {
  const template = selectedDatasetTemplate.value;
  const tool = selectedDatasetTool.value;
  const classId = String(tool?.class_id || inferToolClassFromId(selectedDatasetTargetTool.value));
  const byClass = template?.default_instruction_by_class;
  if (byClass && typeof byClass === "object") {
    const candidate = String(byClass[classId] || "").trim();
    if (candidate) return candidate;
  }
  if (selectedDatasetTaskType.value === "tool_grasp") {
    return `pick up the ${classId}`;
  }
  if (selectedDatasetTaskType.value === "tool_pick_place") {
    return `place the ${classId} in the toolbox`;
  }
  if (selectedDatasetTaskType.value === "tool_reposition") {
    return `move the ${classId} to the target zone`;
  }
  return `debug trial with the ${classId}`;
}

function syncDatasetInstructionFromTemplate(force = false) {
  if (!force && datasetInstructionEdited.value) return;
  datasetInstructionText.value = buildDefaultDatasetInstruction();
  datasetInstructionEdited.value = false;
}

function applyDatasetTemplatesPayload(payload) {
  if (!payload || typeof payload !== "object") return;
  if (Array.isArray(payload.task_templates) && payload.task_templates.length > 0) {
    datasetTemplates.value = payload.task_templates;
  }
  if (Array.isArray(payload.target_tools) && payload.target_tools.length > 0) {
    datasetTargetTools.value = payload.target_tools;
    if (!datasetTargetTools.value.some((tool) => tool.id === selectedDatasetTargetTool.value)) {
      selectedDatasetTargetTool.value = String(datasetTargetTools.value[0]?.id || "wrench_01");
    }
  }
  if (Array.isArray(payload.target_zones) && payload.target_zones.length > 0) {
    datasetTargetZones.value = payload.target_zones;
    if (!datasetTargetZones.value.some((zone) => zone.id === selectedDatasetTargetZone.value)) {
      selectedDatasetTargetZone.value = String(datasetTargetZones.value[0]?.id || "desk_drop_zone");
    }
  }
  if (Array.isArray(payload.collection_stages) && payload.collection_stages.length > 0) {
    datasetCollectionStages.value = payload.collection_stages.map((stage) => String(stage));
  }
  const activeEpisode = String(payload.active_episode_id || "").trim();
  if (activeEpisode) {
    datasetActiveEpisodeId.value = activeEpisode;
  }
  if (!datasetTemplates.value.some((template) => template.task_type === selectedDatasetTaskType.value)) {
    selectedDatasetTaskType.value = String(datasetTemplates.value[0]?.task_type || "debug_trial");
  }
  syncDatasetInstructionFromTemplate(false);
}

function applyDatasetPrecheckPayload(payload) {
  datasetPrecheck.value = payload || null;
  datasetRecordingReady.value = Boolean(payload?.recording_ready);
  const activeEpisode = String(payload?.active_episode_id || "").trim();
  datasetActiveEpisodeId.value = activeEpisode;
  const summary = Array.isArray(payload?.summary) ? payload.summary : [];
  if (summary.length > 0) {
    datasetLastError.value = summary[0];
  } else {
    datasetLastError.value = "";
  }
  if (datasetRecordingReady.value) {
    recordingCheckStatus.value = "ok";
    recordingCheckMessage.value = "precheck 已通过";
  } else if (payload) {
    recordingCheckStatus.value = "error";
    recordingCheckMessage.value = summary[0] || "precheck 未通过";
  }
}

async function loadDatasetTemplates() {
  try {
    const response = await get("/dataset/templates/", { timeout: 2000 });
    applyDatasetTemplatesPayload(response?.data);
  } catch (error) {
    datasetLastError.value = "任务模板加载失败: " + (error?.message || error);
  }
}

async function runDatasetPrecheck() {
  datasetPrecheckInFlight.value = true;
  datasetLastMessage.value = "正在执行采集 precheck...";
  try {
    const response = await get("/dataset/precheck/", { timeout: 6000 });
    applyDatasetPrecheckPayload(response?.data);
    const ready = Boolean(response?.data?.recording_ready);
    datasetLastMessage.value = ready
      ? "precheck 通过，可以开始正式录制。"
      : "precheck 未通过，只允许 debug_trial。";
    syncVrStateToBackend({
      mode: vrModeState.value,
      source: vrControlOwner.value,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: ready,
      error_message: ready ? "" : datasetLastError.value,
    }, { force: true });
    return response?.data;
  } catch (error) {
    datasetLastError.value = "precheck 失败: " + (error?.message || error);
    datasetLastMessage.value = datasetLastError.value;
    datasetRecordingReady.value = false;
    return null;
  } finally {
    datasetPrecheckInFlight.value = false;
    updateNetworkPrereq();
  }
}

async function verifyDatasetCameraView() {
  datasetCameraViewVerifyInFlight.value = true;
  datasetLastError.value = "";
  datasetLastMessage.value = "正在确认当前 D405 视野...";
  try {
    const response = await post("/dataset/camera-view/verify/", {}, { timeout: 6000 });
    const data = response?.data || {};
    if (data.status !== "success") {
      datasetLastError.value = data.message || "D405 视野确认失败";
      datasetLastMessage.value = datasetLastError.value;
      return data;
    }
    if (data.precheck) {
      applyDatasetPrecheckPayload(data.precheck);
    }
    datasetLastMessage.value = "D405 视野已确认，可重新执行 precheck。";
    return data;
  } catch (error) {
    datasetLastError.value = "D405 视野确认失败: " + (error?.message || error);
    datasetLastMessage.value = datasetLastError.value;
    return null;
  } finally {
    datasetCameraViewVerifyInFlight.value = false;
  }
}

function handleDatasetTemplateChanged() {
  const allowed = datasetCollectionStageOptions.value;
  if (!allowed.includes(selectedDatasetCollectionStage.value)) {
    selectedDatasetCollectionStage.value = allowed[0] || "debug_trial";
  }
  syncDatasetInstructionFromTemplate(true);
}

function buildDatasetEpisodeStartPayload() {
  return {
    task_type: selectedDatasetTaskType.value,
    target_tool_id: selectedDatasetTargetTool.value,
    target_zone_id: selectedDatasetTargetZone.value,
    instruction_text: String(datasetInstructionText.value || "").trim(),
    collection_stage: selectedDatasetCollectionStage.value,
    control_mode: datasetControlMode.value,
    robot_input_source: datasetRobotInputSource.value,
  };
}

async function startDatasetEpisode() {
  if (!datasetCanStartEpisode.value) return null;
  datasetEpisodeInFlight.value = true;
  datasetLastError.value = "";
  datasetLastMessage.value = "正在开始 episode...";
  try {
    const response = await post("/dataset/episode/start/", buildDatasetEpisodeStartPayload(), {
      timeout: 6000,
    });
    const data = response?.data || {};
    if (data.status !== "success") {
      datasetLastError.value = data.message || "episode 启动失败";
      datasetLastMessage.value = datasetLastError.value;
      applyDatasetPrecheckPayload(data.precheck);
      return data;
    }
    applyDatasetPrecheckPayload(data.precheck);
    datasetActiveEpisodeId.value = String(data.episode_id || "");
    datasetLastEpisodeId.value = datasetActiveEpisodeId.value;
    datasetLastEpisodeDir.value = String(data.episode_dir || "");
    datasetLastMessage.value = `episode 已开始: ${datasetActiveEpisodeId.value}`;
    return data;
  } catch (error) {
    datasetLastError.value = "episode 启动失败: " + (error?.message || error);
    datasetLastMessage.value = datasetLastError.value;
    return null;
  } finally {
    datasetEpisodeInFlight.value = false;
  }
}

async function stopDatasetEpisode() {
  if (!datasetCanStopEpisode.value) return null;
  datasetEpisodeInFlight.value = true;
  datasetLastError.value = "";
  datasetLastMessage.value = "正在停止 episode...";
  const episodeId = datasetActiveEpisodeId.value;
  try {
    const response = await post("/dataset/episode/stop/", {
      episode_id: episodeId,
      result_status: datasetResultStatus.value,
      quality_label: datasetQualityLabel.value,
      notes: "",
    }, { timeout: 6000 });
    const data = response?.data || {};
    if (data.status !== "success") {
      datasetLastError.value = data.message || "episode 停止失败";
      datasetLastMessage.value = datasetLastError.value;
      return data;
    }
    datasetLastEpisodeId.value = episodeId;
    datasetLastEpisodeDir.value = String(data.episode_dir || datasetLastEpisodeDir.value || "");
    datasetActiveEpisodeId.value = "";
    datasetLastMessage.value = `episode 已停止并标记: ${datasetResultStatus.value}`;
    applyDatasetPrecheckPayload(data.precheck);
    datasetActiveEpisodeId.value = "";
    return data;
  } catch (error) {
    datasetLastError.value = "episode 停止失败: " + (error?.message || error);
    datasetLastMessage.value = datasetLastError.value;
    return null;
  } finally {
    datasetEpisodeInFlight.value = false;
  }
}

async function updateDatasetEpisodeResult() {
  const episodeId = datasetLastEpisodeId.value;
  if (!episodeId) return;
  datasetEpisodeInFlight.value = true;
  datasetLastError.value = "";
  try {
    const response = await post("/dataset/episode/result/", {
      episode_id: episodeId,
      result_status: datasetResultStatus.value,
      quality_label: datasetQualityLabel.value,
      notes: "",
    }, { timeout: 3000 });
    const data = response?.data || {};
    if (data.status !== "success") {
      datasetLastError.value = data.message || "结果更新失败";
      datasetLastMessage.value = datasetLastError.value;
      return data;
    }
    datasetLastMessage.value = `结果已更新: ${datasetResultStatus.value}`;
    return data;
  } catch (error) {
    datasetLastError.value = "结果更新失败: " + (error?.message || error);
    datasetLastMessage.value = datasetLastError.value;
    return null;
  } finally {
    datasetEpisodeInFlight.value = false;
  }
}

function normalizeDatasetAutoSeconds(value, fallback, min, max) {
  const parsed = Math.floor(Number(value));
  if (!Number.isFinite(parsed)) return fallback;
  return clamp(parsed, min, max);
}

function normalizeDatasetAutoMaxEpisodes(value) {
  const parsed = Math.floor(Number(value));
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return clamp(parsed, 0, 9999);
}

function clearDatasetAutoDelay(resolveNow = false) {
  if (datasetAutoDelayTimer.value) {
    clearTimeout(datasetAutoDelayTimer.value);
    datasetAutoDelayTimer.value = null;
  }
  const resolver = datasetAutoDelayResolver;
  datasetAutoDelayResolver = null;
  if (resolveNow && typeof resolver === "function") {
    resolver();
  }
}

function waitDatasetAutoDelay(ms) {
  clearDatasetAutoDelay(false);
  const delayMs = Math.max(0, Math.floor(Number(ms) || 0));
  return new Promise((resolve) => {
    datasetAutoDelayResolver = resolve;
    datasetAutoDelayTimer.value = setTimeout(() => {
      clearDatasetAutoDelay(true);
    }, delayMs);
  });
}

function speakDatasetPrompt(text) {
  const message = String(text || "").trim();
  if (!message) return false;
  datasetAutoVoiceText.value = message;

  if (!datasetVoiceEnabled.value || typeof window === "undefined") return false;
  const synth = window.speechSynthesis;
  const Utterance = window.SpeechSynthesisUtterance;
  if (!synth || typeof Utterance !== "function") return false;

  try {
    synth.cancel();
    const utterance = new Utterance(message);
    utterance.lang = "zh-CN";
    utterance.rate = 0.98;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    synth.speak(utterance);
    return true;
  } catch (error) {
    console.warn("采集语音提示失败:", error?.message || error);
    return false;
  }
}

function stopDatasetVoicePrompt() {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  try {
    window.speechSynthesis.cancel();
  } catch (error) {
    console.warn("停止采集语音失败:", error?.message || error);
  }
}

function getDatasetAutoInputMode() {
  if (selectedVrInputMode.value === "hand" || vrModeState.value === "vr_hand_mode") {
    return "hand";
  }
  return "controller";
}

async function restoreQuestModeAfterDatasetReset(inputMode) {
  const mode = inputMode === "hand" ? "hand" : "controller";
  if (!isVrModeEntered.value && !renderer?.xr?.isPresenting) return;
  setVrModeLocally("vr_ready");
  await chooseVrInputMode(mode);
}

async function resetDatasetSceneForNextEpisode() {
  const inputMode = getDatasetAutoInputMode();
  datasetAutoStatus.value = "重置场景";
  datasetLastMessage.value = "正在重置场景并随机工具位置...";

  stopQuestControllerLoop();
  stopQuestHandLoop();
  const response = await post("/sim/reset/", {}, { timeout: 12000 });
  const data = response?.data || {};
  if (data.status !== "success") {
    throw new Error(data.message || "场景重置失败");
  }

  if (data.state && typeof data.state === "object") {
    const now = Date.now();
    simulationState.value = data.state;
    const stateTimestampMs = getBackendStateTimestampMs(data.state);
    if (Number.isFinite(Number(stateTimestampMs))) {
      lastAcceptedBackendStateTimestampMs.value = Number(stateTimestampMs);
    }
    applyBackendStateToScene(data.state, { immediate: true });
    checkD405ObservationReady(data.state);
    checkRecordingBindingReady(data.state);
    updateSafetyFeedbackFromState(data.state);
    lastStateUpdate.value = now;
  }

  await restoreQuestModeAfterDatasetReset(inputMode);
  updateNetworkPrereq();
  return data;
}

function startDatasetAutoCollection() {
  if (!datasetCanStartAutoCollection.value) return;
  datasetAutoCollecting.value = true;
  datasetAutoStopRequested.value = false;
  datasetAutoEpisodeIndex.value = 0;
  datasetAutoStatus.value = "准备中";
  datasetLastError.value = "";
  datasetLastMessage.value = "连续采集准备中...";
  datasetControllerNextWasPressed.value = false;
  lastDatasetControllerNextAt.value = 0;
  datasetAutoEpisodeDurationSec.value = normalizeDatasetAutoSeconds(
    datasetAutoEpisodeDurationSec.value,
    30,
    3,
    3600
  );
  datasetAutoResetDelaySec.value = normalizeDatasetAutoSeconds(
    datasetAutoResetDelaySec.value,
    2,
    0,
    60
  );
  datasetAutoMaxEpisodes.value = normalizeDatasetAutoMaxEpisodes(datasetAutoMaxEpisodes.value);
  void runDatasetAutoCollectionLoop();
}

function stopDatasetAutoCollection() {
  if (!datasetCanStopAutoCollection.value) return;
  datasetAutoStopRequested.value = true;
  datasetAutoStatus.value = "正在停止";
  datasetLastMessage.value = "正在停止连续采集...";
  datasetControllerNextWasPressed.value = false;
  clearDatasetAutoDelay(true);
}

function readDatasetControllerNextValue(snapshot) {
  const controlValue = Number(snapshot?.controls?.next_episode);
  const rawValue = Number(snapshot?.raw?.right?.next_episode);
  const values = [controlValue, rawValue].filter((value) => Number.isFinite(value));
  return values.length > 0 ? Math.max(...values) : 0;
}

function requestDatasetAutoNextFromController(nowMs = Date.now()) {
  if (!datasetAutoCollecting.value || datasetAutoStopRequested.value) return;
  const now = Number.isFinite(Number(nowMs)) ? Number(nowMs) : Date.now();
  if (now - Number(lastDatasetControllerNextAt.value || 0) < DATASET_CONTROLLER_NEXT_COOLDOWN_MS) {
    return;
  }
  lastDatasetControllerNextAt.value = now;
  datasetAutoStatus.value = datasetEpisodeActive.value ? "提前结束当前轮" : "跳过等待";
  datasetLastMessage.value = datasetEpisodeActive.value
    ? `手柄触发: 结束 episode${datasetAutoEpisodeIndex.value} 并进入下一轮`
    : "手柄触发: 准备进入下一轮";
  speakDatasetPrompt(datasetEpisodeActive.value ? "已收到，进入下一轮" : "已收到，准备下一轮");
  clearDatasetAutoDelay(true);
}

function handleDatasetControllerNextButton(snapshot, nowMs = Date.now()) {
  const nextValue = readDatasetControllerNextValue(snapshot);
  const pressed = nextValue >= DATASET_CONTROLLER_NEXT_THRESHOLD;
  if (pressed && !datasetControllerNextWasPressed.value) {
    requestDatasetAutoNextFromController(nowMs);
  }
  datasetControllerNextWasPressed.value = pressed;
}

async function runDatasetAutoCollectionLoop() {
  try {
    if (selectedDatasetCollectionStage.value !== "debug_trial" && !datasetRecordingReady.value) {
      const precheck = await runDatasetPrecheck();
      if (!precheck?.recording_ready) {
        throw new Error("precheck 未通过，不能开始正式连续采集");
      }
    }

    while (datasetAutoCollecting.value && !datasetAutoStopRequested.value) {
      const maxEpisodes = normalizeDatasetAutoMaxEpisodes(datasetAutoMaxEpisodes.value);
      if (maxEpisodes > 0 && datasetAutoEpisodeIndex.value >= maxEpisodes) {
        datasetAutoStatus.value = "已完成";
        datasetLastMessage.value = `连续采集完成: ${maxEpisodes} 轮`;
        speakDatasetPrompt("连续采集完成");
        break;
      }

      const currentIndex = datasetAutoEpisodeIndex.value;
      const episodeSeconds = normalizeDatasetAutoSeconds(
        datasetAutoEpisodeDurationSec.value,
        30,
        3,
        3600
      );
      datasetAutoEpisodeDurationSec.value = episodeSeconds;
      datasetAutoStatus.value = "采集中";
      datasetLastMessage.value = `开始采集 episode${currentIndex}`;
      speakDatasetPrompt(`开始采集数据 episode ${currentIndex}`);

      const startData = await startDatasetEpisode();
      if (startData?.status !== "success") {
        throw new Error(startData?.message || datasetLastError.value || "episode 启动失败");
      }

      await waitDatasetAutoDelay(episodeSeconds * 1000);

      datasetAutoStatus.value = "结束当前轮";
      speakDatasetPrompt(`episode ${currentIndex} 采集结束，请重置场景`);
      const stopData = await stopDatasetEpisode();
      if (stopData?.status !== "success") {
        throw new Error(stopData?.message || datasetLastError.value || "episode 停止失败");
      }

      if (datasetAutoStopRequested.value) {
        break;
      }

      datasetAutoEpisodeIndex.value = currentIndex + 1;
      const nextMaxEpisodes = normalizeDatasetAutoMaxEpisodes(datasetAutoMaxEpisodes.value);
      if (nextMaxEpisodes > 0 && datasetAutoEpisodeIndex.value >= nextMaxEpisodes) {
        datasetAutoStatus.value = "已完成";
        datasetLastMessage.value = `连续采集完成: ${nextMaxEpisodes} 轮`;
        speakDatasetPrompt("连续采集完成");
        break;
      }

      await resetDatasetSceneForNextEpisode();
      if (datasetAutoStopRequested.value) {
        break;
      }

      speakDatasetPrompt(`场景已重置，准备采集数据 episode ${datasetAutoEpisodeIndex.value}`);
      const resetDelaySeconds = normalizeDatasetAutoSeconds(datasetAutoResetDelaySec.value, 2, 0, 60);
      datasetAutoResetDelaySec.value = resetDelaySeconds;
      await waitDatasetAutoDelay(resetDelaySeconds * 1000);
    }

    if (datasetAutoStopRequested.value) {
      datasetAutoStatus.value = "已停止";
      datasetLastMessage.value = "连续采集已停止";
      speakDatasetPrompt("连续采集已停止");
    }
  } catch (error) {
    const message = error?.message || String(error);
    datasetAutoStatus.value = "异常";
    datasetLastError.value = "连续采集异常: " + message;
    datasetLastMessage.value = datasetLastError.value;
    speakDatasetPrompt("连续采集异常，流程已停止");
  } finally {
    if (datasetAutoStopRequested.value && datasetEpisodeActive.value && !datasetEpisodeInFlight.value) {
      await stopDatasetEpisode();
    }
    clearDatasetAutoDelay(false);
    datasetAutoCollecting.value = false;
    datasetAutoStopRequested.value = false;
  }
}

function getQuestSourceFromBackendState(state) {
  const source = String(state?.source || state?.input_source || state?.vr?.control_owner || "").trim();
  return source === "quest3_controller" || source === "quest3_hand" ? source : "";
}

function getSelectedQuestControlSource() {
  if (selectedVrInputMode.value === "controller") {
    return { mode: "vr_controller_mode", source: "quest3_controller" };
  }
  if (selectedVrInputMode.value === "hand") {
    return { mode: "vr_hand_mode", source: "quest3_hand" };
  }
  return null;
}

function shouldPreserveLocalQuestControl(state) {
  const selectedControl = getSelectedQuestControlSource();
  if (!selectedControl || !hasLocalQuestXrControlContext()) return false;
  const backendMode = String(state?.vr?.mode || "").trim();
  const backendOwner = String(state?.vr?.control_owner || state?.source || state?.input_source || "").trim();
  if (backendMode === "vr_error") return false;
  if (backendMode === selectedControl.mode || backendOwner === selectedControl.source) return false;
  return Boolean(backendMode || backendOwner);
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
  const questSource = getQuestSourceFromBackendState(state);
  const preserveLocalQuestControl = shouldPreserveLocalQuestControl(state);
  if (preserveLocalQuestControl) {
    const selectedControl = getSelectedQuestControlSource();
    if (selectedControl) {
      vrModeState.value = selectedControl.mode;
      vrControlOwner.value = selectedControl.source;
    }
  }
  const nowMs = Date.now();
  const shouldCommitControllerUi =
    questSource === "quest3_controller" &&
    (!questControllerNormalizedInput.value ||
      nowMs - lastQuestControllerUiCommitAt >= QUEST_TELEOP_UI_MIN_INTERVAL_MS);
  const shouldCommitHandUi =
    questSource === "quest3_hand" &&
    (!questHandNormalizedInput.value ||
      nowMs - lastQuestHandUiCommitAt >= QUEST_TELEOP_UI_MIN_INTERVAL_MS);
  let committedControllerUi = false;
  let committedHandUi = false;
  if (typeof vr.mode === "string") {
    if (!preserveLocalQuestControl && !shouldIgnoreBackendVrMode(vr.mode)) {
      vrModeState.value = vr.mode;
    }
  }
  if (typeof vr.selected_joint_group === "string" && vr.selected_joint_group.length > 0) {
    vrSelectedJointGroup.value = vr.selected_joint_group;
  }
  if (!preserveLocalQuestControl && typeof vr.control_owner === "string" && vr.control_owner.length > 0) {
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
  if (!preserveLocalQuestControl && (inputSource === "quest3_controller" || inputSource === "quest3_hand")) {
    vrControlOwner.value = inputSource;
  }
  if (state?.raw_input && typeof state.raw_input === "object") {
    if (shouldCommitControllerUi) {
      questControllerRawInput.value = state.raw_input;
      committedControllerUi = true;
    } else if (shouldCommitHandUi) {
      questHandRawInput.value = state.raw_input;
      committedHandUi = true;
    }
  }
  if (state?.normalized_input && typeof state.normalized_input === "object") {
    const normalizedInput = { ...state.normalized_input };
    if (shouldCommitControllerUi) {
      questControllerNormalizedInput.value = normalizedInput;
      committedControllerUi = true;
    } else if (shouldCommitHandUi) {
      questHandNormalizedInput.value = normalizedInput;
      committedHandUi = true;
    }
  }
  if (committedControllerUi) lastQuestControllerUiCommitAt = nowMs;
  if (committedHandUi) lastQuestHandUiCommitAt = nowMs;
  if (questSource === "quest3_hand" && shouldCommitHandUi) {
    updateHandTrackingFromBackend(state);
  }
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

  await runDatasetPrecheck();

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

const QUEST_HAND_JOINT_NAMES = [
  "wrist",
  "thumb-metacarpal",
  "thumb-phalanx-proximal",
  "thumb-phalanx-distal",
  "thumb-tip",
  "index-finger-metacarpal",
  "index-finger-phalanx-proximal",
  "index-finger-phalanx-intermediate",
  "index-finger-phalanx-distal",
  "index-finger-tip",
  "middle-finger-metacarpal",
  "middle-finger-phalanx-proximal",
  "middle-finger-phalanx-intermediate",
  "middle-finger-phalanx-distal",
  "middle-finger-tip",
  "ring-finger-metacarpal",
  "ring-finger-phalanx-proximal",
  "ring-finger-phalanx-intermediate",
  "ring-finger-phalanx-distal",
  "ring-finger-tip",
  "pinky-finger-metacarpal",
  "pinky-finger-phalanx-proximal",
  "pinky-finger-phalanx-intermediate",
  "pinky-finger-phalanx-distal",
  "pinky-finger-tip",
];

const QUEST_HAND_BONE_PAIRS = [
  ["wrist", "thumb-metacarpal"],
  ["thumb-metacarpal", "thumb-phalanx-proximal"],
  ["thumb-phalanx-proximal", "thumb-phalanx-distal"],
  ["thumb-phalanx-distal", "thumb-tip"],
  ["wrist", "index-finger-metacarpal"],
  ["index-finger-metacarpal", "index-finger-phalanx-proximal"],
  ["index-finger-phalanx-proximal", "index-finger-phalanx-intermediate"],
  ["index-finger-phalanx-intermediate", "index-finger-phalanx-distal"],
  ["index-finger-phalanx-distal", "index-finger-tip"],
  ["wrist", "middle-finger-metacarpal"],
  ["middle-finger-metacarpal", "middle-finger-phalanx-proximal"],
  ["middle-finger-phalanx-proximal", "middle-finger-phalanx-intermediate"],
  ["middle-finger-phalanx-intermediate", "middle-finger-phalanx-distal"],
  ["middle-finger-phalanx-distal", "middle-finger-tip"],
  ["wrist", "ring-finger-metacarpal"],
  ["ring-finger-metacarpal", "ring-finger-phalanx-proximal"],
  ["ring-finger-phalanx-proximal", "ring-finger-phalanx-intermediate"],
  ["ring-finger-phalanx-intermediate", "ring-finger-phalanx-distal"],
  ["ring-finger-phalanx-distal", "ring-finger-tip"],
  ["wrist", "pinky-finger-metacarpal"],
  ["pinky-finger-metacarpal", "pinky-finger-phalanx-proximal"],
  ["pinky-finger-phalanx-proximal", "pinky-finger-phalanx-intermediate"],
  ["pinky-finger-phalanx-intermediate", "pinky-finger-phalanx-distal"],
  ["pinky-finger-phalanx-distal", "pinky-finger-tip"],
];

function buildQuestHandSkeletonFallback() {
  const group = new THREE.Group();
  group.name = "quest_hand_skeleton_fallback";
  group.visible = false;

  const jointMaterial = new THREE.MeshStandardMaterial({
    color: 0xf6f2df,
    roughness: 0.54,
    metalness: 0.02,
  });
  const tipMaterial = new THREE.MeshStandardMaterial({
    color: 0x65d6ad,
    roughness: 0.48,
    metalness: 0.02,
  });
  const jointMeshes = {};
  QUEST_HAND_JOINT_NAMES.forEach((jointName) => {
    const isTip = jointName.endsWith("tip");
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(isTip ? 0.0078 : 0.0058, 12, 8),
      isTip ? tipMaterial : jointMaterial
    );
    mesh.name = `quest_hand_joint_${jointName}`;
    jointMeshes[jointName] = mesh;
    group.add(mesh);
  });

  const boneMaterial = new THREE.MeshStandardMaterial({
    color: 0xd8c8b4,
    transparent: true,
    opacity: 0.86,
    roughness: 0.58,
    metalness: 0.01,
  });
  const boneMeshes = {};
  QUEST_HAND_BONE_PAIRS.forEach(([fromName, toName]) => {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(0.0045, 0.0045, 1, 10), boneMaterial);
    mesh.name = `quest_hand_bone_${fromName}_${toName}`;
    mesh.visible = false;
    boneMeshes[`${fromName}:${toName}`] = mesh;
    group.add(mesh);
  });

  const palmGeometry = new THREE.BufferGeometry();
  palmGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(new Array(5 * 3).fill(0), 3)
  );
  palmGeometry.setIndex([0, 1, 2, 0, 2, 3, 0, 3, 4]);
  palmGeometry.computeVertexNormals();
  const palmMesh = new THREE.Mesh(
    palmGeometry,
    new THREE.MeshStandardMaterial({
      color: 0xf0dfc9,
      transparent: true,
      opacity: 0.42,
      roughness: 0.62,
      metalness: 0.0,
      side: THREE.DoubleSide,
    })
  );
  palmMesh.name = "quest_hand_palm_surface";
  palmMesh.visible = false;
  group.add(palmMesh);

  const boneGeometry = new THREE.BufferGeometry();
  boneGeometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(new Array(QUEST_HAND_BONE_PAIRS.length * 2 * 3).fill(0), 3)
  );
  const boneLines = new THREE.LineSegments(
    boneGeometry,
    new THREE.LineBasicMaterial({
      color: 0x65d6ad,
      transparent: true,
      opacity: 0.82,
    })
  );
  boneLines.name = "quest_hand_bone_lines";
  boneLines.visible = false;
  group.add(boneLines);
  group.userData.jointMeshes = jointMeshes;
  group.userData.boneMeshes = boneMeshes;
  group.userData.palmMesh = palmMesh;
  group.userData.boneLines = boneLines;
  return group;
}

function normalizeXrHandedness(value) {
  const handedness = String(value || "").toLowerCase();
  if (handedness === "left" || handedness === "right") return handedness;
  return "";
}

function resolveXrNodeKey(node, fallbackKey = "") {
  return normalizeXrHandedness(node?.userData?.handedness) || normalizeXrHandedness(fallbackKey);
}

function assignQuestXrVisualNode(kind, key, node) {
  if (!node || !xrVisualNodes[kind]) return;
  Object.keys(xrVisualNodes[kind]).forEach((entryKey) => {
    if (xrVisualNodes[kind][entryKey] === node && entryKey !== key) {
      xrVisualNodes[kind][entryKey] = null;
    }
  });
  if (!key) return;
  xrVisualNodes[kind][key] = node;
}

function setQuestXrNodeSourceState(node, kind, source, fallbackKey = "") {
  if (!node) return;
  const handedness =
    normalizeXrHandedness(source?.handedness) ||
    resolveXrNodeKey(node, fallbackKey);
  if (handedness) {
    node.userData.handedness = handedness;
    assignQuestXrVisualNode(kind, handedness, node);
  }
  node.userData.inputSource = source || null;
  node.userData.connected = Boolean(source);
  if (!source) {
    node.visible = false;
  }
}

function resetQuestXrVisualNodes() {
  Object.values(xrVisualNodes).forEach((nodeMap) => {
    Object.keys(nodeMap).forEach((key) => {
      const node = nodeMap[key];
      if (node) {
        node.userData.connected = false;
        node.userData.handedness = "";
        node.userData.inputSource = null;
        node.visible = false;
      }
      nodeMap[key] = null;
    });
  });
}

function registerQuestXrNodeEvents(node, kind, fallbackKey = "") {
  if (!node || node.userData.questXrVisualEventsAttached) return;
  node.userData.questXrVisualEventsAttached = true;
  node.addEventListener("connected", (event) => {
    const handedness = normalizeXrHandedness(event?.data?.handedness) || normalizeXrHandedness(fallbackKey);
    node.userData.inputSource = event?.data || null;
    if (!handedness) return;
    node.userData.handedness = handedness;
    node.userData.connected = true;
    assignQuestXrVisualNode(kind, handedness, node);
    updateQuestXrVisualVisibility();
  });
  node.addEventListener("disconnected", () => {
    node.userData.connected = false;
    node.userData.inputSource = null;
    node.visible = false;
  });
}

function resolveQuestXrNodeSourceForIndex(sources, index, node, fallbackKey = "") {
  const nodeHandedness = normalizeXrHandedness(node?.userData?.handedness);
  if (nodeHandedness) {
    return sources.find((source) => normalizeXrHandedness(source?.handedness) === nodeHandedness) || null;
  }

  const existingSource = node?.userData?.inputSource || null;
  const existingHandedness = normalizeXrHandedness(existingSource?.handedness);
  if (existingHandedness) {
    return existingSource;
  }

  const indexedSource = sources[index] || null;
  if (normalizeXrHandedness(indexedSource?.handedness)) {
    return indexedSource;
  }

  const fallbackHandedness = normalizeXrHandedness(fallbackKey);
  if (fallbackHandedness) {
    return sources.find((source) => normalizeXrHandedness(source?.handedness) === fallbackHandedness) || null;
  }

  return null;
}

function getQuestControllerModelPath(handedness = "") {
  return handedness === "left"
    ? QUEST_CONTROLLER_MODEL_PATHS.left
    : QUEST_CONTROLLER_MODEL_PATHS.right;
}

async function loadQuestControllerModelClone(handedness = "") {
  const modelPath = getQuestControllerModelPath(handedness);
  const cachedScene = questControllerModelCache.get(modelPath);
  if (cachedScene) {
    return cachedScene.clone(true);
  }

  let loadingPromise = questControllerModelPromiseCache.get(modelPath);
  if (!loadingPromise) {
    loadingPromise = new Promise((resolve, reject) => {
      questControllerModelLoader.load(
        modelPath,
        (gltf) => {
          const sceneModel = gltf?.scene || null;
          if (!sceneModel) {
            reject(new Error(`Quest controller model scene missing: ${modelPath}`));
            return;
          }
          questControllerModelCache.set(modelPath, sceneModel);
          resolve(sceneModel);
        },
        undefined,
        reject
      );
    }).finally(() => {
      questControllerModelPromiseCache.delete(modelPath);
    });
    questControllerModelPromiseCache.set(modelPath, loadingPromise);
  }

  const loadedScene = await loadingPromise;
  return loadedScene.clone(true);
}

function ensureQuestControllerGripVisuals(controllerGrip, handedness = "") {
  if (!controllerGrip) return;
  const normalizedHandedness = normalizeXrHandedness(handedness) || "right";
  const expectedModelPath = getQuestControllerModelPath(normalizedHandedness);
  const currentModelPath = String(controllerGrip.userData.questControllerModelPath || "");
  const needsReload =
    controllerGrip.userData.questControllerModelAttached !== true ||
    currentModelPath !== expectedModelPath;
  if (needsReload && !controllerGrip.userData.questControllerModelLoading) {
    controllerGrip.userData.questControllerModelAttached = true;
    controllerGrip.userData.questControllerModelLoading = true;
    controllerGrip.userData.questControllerModelPath = expectedModelPath;
    // Use the downloaded local GLB directly so immersive mode does not depend
    // on browser profile matching or remote model resolution.
    loadQuestControllerModelClone(normalizedHandedness)
      .then((model) => {
        if (!controllerGrip?.userData) return;
        if (String(controllerGrip.userData.questControllerModelPath || "") !== expectedModelPath) {
          return;
        }
        const existing = controllerGrip.getObjectByName("quest_controller_local_model");
        if (existing) {
          controllerGrip.remove(existing);
        }
        model.name = "quest_controller_local_model";
        controllerGrip.add(model);
      })
      .catch((error) => {
        controllerGrip.userData.questControllerModelAttached = false;
        console.warn("Quest controller local model unavailable:", error?.message || error);
      })
      .finally(() => {
        if (controllerGrip?.userData) {
          controllerGrip.userData.questControllerModelLoading = false;
        }
      });
  }
}

function ensureQuestHandNodeVisuals(handNode) {
  if (!handNode) return;
  if (!handNode.userData.questHandModelAttached) {
    try {
      const meshModel = xrHandModelFactory.createHandModel(handNode, "mesh");
      meshModel.name = "quest_hand_mesh_model";
      handNode.add(meshModel);
    } catch (error) {
      console.warn("Quest hand mesh model unavailable:", error?.message || error);
    }
    handNode.userData.questHandModelAttached = true;
  }
  if (!handNode.userData.questHandSkeletonFallbackAttached) {
    handNode.add(buildQuestHandSkeletonFallback());
    handNode.userData.questHandSkeletonFallbackAttached = true;
  }
}

function hasVisibleQuestHandMesh(handNode) {
  const model = handNode?.getObjectByName?.("quest_hand_mesh_model");
  if (!model) return false;
  let hasSkinnedMesh = false;
  model.traverse((child) => {
    if (child?.isSkinnedMesh || child?.type === "SkinnedMesh") {
      hasSkinnedMesh = true;
    }
  });
  return hasSkinnedMesh;
}

function updateQuestHandSkeletonFallbacks() {
  if (!renderer?.xr?.isPresenting || vrModeState.value !== "vr_hand_mode") return;
  const tmpPosition = new THREE.Vector3();
  const tmpFrom = new THREE.Vector3();
  const tmpTo = new THREE.Vector3();
  const tmpMid = new THREE.Vector3();
  const tmpDirection = new THREE.Vector3();
  const tmpQuaternion = new THREE.Quaternion();
  const yAxis = new THREE.Vector3(0, 1, 0);
  Object.values(xrVisualNodes.hands).forEach((handNode) => {
    if (!handNode) return;
    const skeleton = handNode.getObjectByName("quest_hand_skeleton_fallback");
    if (!skeleton) return;
    const joints = handNode.joints || {};
    const jointMeshes = skeleton.userData.jointMeshes || {};
    const boneMeshes = skeleton.userData.boneMeshes || {};
    const palmMesh = skeleton.userData.palmMesh || null;
    const boneLines = skeleton.userData.boneLines || null;
    const positions = boneLines?.geometry?.attributes?.position;
    let visibleJointCount = 0;
    const useFallback = Boolean(handNode.visible && !hasVisibleQuestHandMesh(handNode));

    QUEST_HAND_JOINT_NAMES.forEach((jointName) => {
      const joint = joints[jointName];
      const mesh = jointMeshes[jointName];
      if (!joint || !mesh) return;
      tmpPosition.setFromMatrixPosition(joint.matrixWorld);
      handNode.worldToLocal(tmpPosition);
      mesh.position.copy(tmpPosition);
      const radius = Number(joint.jointRadius);
      if (Number.isFinite(radius) && radius > 0) {
        const scale = clamp(radius / 0.0065, 0.7, 1.8);
        mesh.scale.setScalar(scale);
      }
      mesh.visible = useFallback;
      visibleJointCount += 1;
    });

    QUEST_HAND_BONE_PAIRS.forEach(([fromName, toName]) => {
      const boneMesh = boneMeshes[`${fromName}:${toName}`];
      const from = jointMeshes[fromName];
      const to = jointMeshes[toName];
      const visible = Boolean(useFallback && from?.visible && to?.visible);
      if (!boneMesh) return;
      boneMesh.visible = visible;
      if (!visible) return;
      tmpFrom.copy(from.position);
      tmpTo.copy(to.position);
      tmpMid.addVectors(tmpFrom, tmpTo).multiplyScalar(0.5);
      tmpDirection.subVectors(tmpTo, tmpFrom);
      const length = tmpDirection.length();
      if (length <= 1e-5) {
        boneMesh.visible = false;
        return;
      }
      tmpDirection.normalize();
      tmpQuaternion.setFromUnitVectors(yAxis, tmpDirection);
      boneMesh.position.copy(tmpMid);
      boneMesh.quaternion.copy(tmpQuaternion);
      boneMesh.scale.set(1, length, 1);
    });

    if (palmMesh?.geometry?.attributes?.position) {
      const palmJoints = [
        jointMeshes.wrist,
        jointMeshes["index-finger-metacarpal"],
        jointMeshes["middle-finger-metacarpal"],
        jointMeshes["ring-finger-metacarpal"],
        jointMeshes["pinky-finger-metacarpal"],
      ];
      const palmVisible = Boolean(useFallback && palmJoints.every((mesh) => mesh?.visible));
      palmMesh.visible = palmVisible;
      if (palmVisible) {
        const palmPositions = palmMesh.geometry.attributes.position;
        palmJoints.forEach((mesh, index) => {
          palmPositions.setXYZ(index, mesh.position.x, mesh.position.y, mesh.position.z);
        });
        palmPositions.needsUpdate = true;
        palmMesh.geometry.computeVertexNormals();
      }
    }

    if (positions) {
      let offset = 0;
      QUEST_HAND_BONE_PAIRS.forEach(([fromName, toName]) => {
        const from = jointMeshes[fromName];
        const to = jointMeshes[toName];
        const fromVisible = Boolean(from?.visible);
        const toVisible = Boolean(to?.visible);
        const fromPos = fromVisible ? from.position : new THREE.Vector3();
        const toPos = toVisible ? to.position : fromPos;
        positions.setXYZ(offset, fromPos.x, fromPos.y, fromPos.z);
        positions.setXYZ(offset + 1, toPos.x, toPos.y, toPos.z);
        offset += 2;
      });
      positions.needsUpdate = true;
    }
    if (boneLines) {
      boneLines.visible = Boolean(useFallback && visibleJointCount >= 6);
    }
    skeleton.visible = Boolean(useFallback && visibleJointCount >= 6);
  });
}

function ensureQuestXrVisualNodes() {
  if (!renderer?.xr || !scene) return;
  const sessionSources = Array.from(getQuestXRSession()?.inputSources || []);
  const controllerInputSources = sessionSources.filter((source) => source && !source.hand);
  const handInputSources = sessionSources.filter((source) => source && source.hand);
  const slots = [
    { index: 0, fallbackKey: "" },
    { index: 1, fallbackKey: "" },
  ];
  slots.forEach(({ index, fallbackKey }) => {
    const controllerRay = renderer.xr.getController(index);
    const controllerSource = resolveQuestXrNodeSourceForIndex(
      controllerInputSources,
      index,
      controllerRay,
      fallbackKey
    );
    const controllerKey = normalizeXrHandedness(controllerSource?.handedness) || resolveXrNodeKey(controllerRay, fallbackKey);
    if (controllerRay) {
      registerQuestXrNodeEvents(controllerRay, "controllerRays", controllerKey);
      setQuestXrNodeSourceState(controllerRay, "controllerRays", controllerSource, controllerKey);
      if (!controllerRay.getObjectByName("quest_controller_ray")) {
        controllerRay.add(buildQuestControllerRay());
      }
      if (!controllerRay.parent) {
        scene.add(controllerRay);
      }
    }

    const controllerGrip = renderer.xr.getControllerGrip(index);
    if (controllerGrip) {
      registerQuestXrNodeEvents(controllerGrip, "controllerGrips", controllerKey);
      setQuestXrNodeSourceState(controllerGrip, "controllerGrips", controllerSource, controllerKey);
      ensureQuestControllerGripVisuals(controllerGrip, resolveXrNodeKey(controllerGrip, controllerKey));
      if (!controllerGrip.parent) {
        scene.add(controllerGrip);
      }
    }

    const handNode = renderer.xr.getHand(index);
    const handSource = resolveQuestXrNodeSourceForIndex(
      handInputSources,
      index,
      handNode,
      fallbackKey
    );
    const handKey = normalizeXrHandedness(handSource?.handedness) || resolveXrNodeKey(handNode, fallbackKey);
    if (handNode) {
      registerQuestXrNodeEvents(handNode, "hands", handKey);
      setQuestXrNodeSourceState(handNode, "hands", handSource, handKey);
      ensureQuestHandNodeVisuals(handNode);
      if (!handNode.parent) {
        scene.add(handNode);
      }
    }
  });
}

function updateQuestXrVisualVisibility() {
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  const showControllers = xrPresenting && vrModeState.value === "vr_controller_mode";
  const showHands = xrPresenting && vrModeState.value === "vr_hand_mode";
  const applyVisible = (nodeMap, visible) => {
    Object.values(nodeMap).forEach((node) => {
      if (!node) return;
      node.visible = visible && node.userData.connected !== false;
    });
  };
  applyVisible(xrVisualNodes.controllerRays, showControllers);
  applyVisible(xrVisualNodes.controllerGrips, showControllers);
  applyVisible(xrVisualNodes.hands, showHands);
}

function readQuestControllerVisualInput(hand) {
  const normalizedHand = normalizeXrHandedness(hand);
  const raw = questControllerRawInput.value || {};
  const normalized = questControllerNormalizedInput.value || {};
  const input = raw?.[normalizedHand] || {};
  const activeHand =
    normalizeXrHandedness(normalized.active_hand) ||
    normalizeXrHandedness(raw.active_hand);
  return {
    trigger: clamp(Number(input.trigger || 0), 0, 1),
    grip: clamp(Number(input.grip || 0), 0, 1),
    active: activeHand === normalizedHand,
  };
}

function setMaterialOpacity(object, opacity) {
  const material = object?.material;
  const materials = Array.isArray(material) ? material : material ? [material] : [];
  const nextOpacity = clamp(opacity, 0, 1);
  materials.forEach((item) => {
    if (item.transparent !== true) {
      item.transparent = true;
      item.needsUpdate = true;
    }
    if (Math.abs(Number(item.opacity ?? 1) - nextOpacity) > 0.005) {
      item.opacity = nextOpacity;
    }
  });
}

function updateQuestControllerRayVisual(controllerRay, hand) {
  const ray = controllerRay?.getObjectByName?.("quest_controller_ray");
  if (!ray) return;
  const input = readQuestControllerVisualInput(hand);
  const activity = Math.max(input.trigger, input.grip, input.active ? 0.35 : 0);
  const nextScaleZ = 1.0 + activity * 1.35;
  const nextVisible = Boolean(controllerRay.visible && activity > 0.02);
  if (Math.abs(ray.scale.z - nextScaleZ) > 0.01) {
    ray.scale.z = nextScaleZ;
  }
  if (ray.visible !== nextVisible) {
    ray.visible = nextVisible;
  }
  setMaterialOpacity(ray, input.active ? 0.86 : 0.36 + activity * 0.32);
}

function updateQuestControllerVisualState() {
  if (!renderer?.xr?.isPresenting || vrModeState.value !== "vr_controller_mode") return;
  Object.entries(xrVisualNodes.controllerRays).forEach(([hand, node]) => {
    updateQuestControllerRayVisual(node, hand);
  });
}

function resetQuestXrSourceRefreshTimer() {
  if (!questXrSourceRefreshTimer) return;
  clearTimeout(questXrSourceRefreshTimer);
  questXrSourceRefreshTimer = null;
}

async function refreshQuestXrInputBindings() {
  lastQuestControllerPoseSnapshot = null;
  ensureQuestXrVisualNodes();
  updateQuestXrVisualVisibility();

  if (isQuestControllerModeActive()) {
    suppressQuestControllerTransition({
      duration_ms: Math.max(180, VR_MODE_TRANSITION_GUARD_MS / 2),
      require_neutral: true,
      clear_queue: true,
    });
    runQuestControllerTick(Date.now());
  }

  if (isQuestHandModeActive()) {
    const handStatus = getQuestHandInputStatus();
    if (!handStatus.ready) {
      await startQuestHandLoop();
      return;
    }
    runQuestHandTick(Date.now());
  }
}

function scheduleQuestXrInputRefresh(delayMs = QUEST_XR_SOURCE_REFRESH_DELAY_MS) {
  resetQuestXrSourceRefreshTimer();
  questXrSourceRefreshTimer = setTimeout(() => {
    questXrSourceRefreshTimer = null;
    void refreshQuestXrInputBindings();
  }, Math.max(0, Number(delayMs) || 0));
}

async function cleanupQuestVrMode(options = {}) {
  if (questVrExitInFlight) return;
  questVrExitInFlight = true;
  try {
    stopDatasetAutoCollection();
    stopQuestControllerLoop();
    stopQuestHandLoop();
    stopQuestVrControlWatchdog();
    resetQuestXrSourceRefreshTimer();
    questXrPresentingLostSinceAt.value = 0;
    if (options.reset_selected_mode !== false) {
      selectedVrInputMode.value = "";
    }
    setVrModeLocally(options.mode || "vr_disabled");
    vrControlOwner.value = "desktop_manual";
    vrErrorMessage.value = String(options.error_message || "");
    syncVrStateToBackend({
      mode: options.mode || "vr_disabled",
      source: "desktop_manual",
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: getDatasetRecordingReady(),
      error_message: vrErrorMessage.value,
    });
    detachQuestXrSessionListeners();
    resetQuestXrVisualNodes();
    if (renderer?.xr) {
      await Promise.resolve(renderer.xr.setSession(null)).catch(() => {});
    }
    if (options.stop_session !== false) {
      await stopQuestXRSession();
    }
    updateQuestXrVisualVisibility();
  } finally {
    questVrExitInFlight = false;
  }
}

function syncQuestXrPresentationState(nowMs = Date.now()) {
  if (!isVrModeEntered.value || questVrExitInFlight) {
    questXrPresentingLostSinceAt.value = 0;
    return;
  }

  const xrSession = getQuestXRSession();
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  if (xrSession && xrPresenting) {
    questXrPresentingLostSinceAt.value = 0;
    return;
  }

  if (questXrPresentingLostSinceAt.value <= 0) {
    questXrPresentingLostSinceAt.value = Number(nowMs) || Date.now();
    return;
  }

  if (nowMs - Number(questXrPresentingLostSinceAt.value) < QUEST_XR_PRESENTING_LOST_GRACE_MS) {
    return;
  }

  const errorMessage = xrSession
    ? "XR 已离开沉浸模式，已自动退出，避免控制与显示状态卡住。"
    : "XR 会话已结束，已自动退出 VR 模式。";
  questXrPresentingLostSinceAt.value = 0;
  void cleanupQuestVrMode({
    mode: "vr_disabled",
    error_message: errorMessage,
    stop_session: Boolean(xrSession),
  });
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
      scheduleQuestXrInputRefresh(VR_MODE_TRANSITION_GUARD_MS);
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
    scheduleQuestXrInputRefresh(QUEST_XR_SOURCE_REFRESH_DELAY_MS);
  };
  questXrEndedHandler = () => {
    updateQuestXrVisualVisibility();
    void cleanupQuestVrMode({
      mode: "vr_disabled",
      error_message: "XR 会话已结束，已自动退出 VR 模式。",
      stop_session: false,
    });
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
    const controllerSnapshot = readQuestControllerSnapshot();
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
      controller_available: Boolean(controllerSnapshot?.has_device),
      recording_ready: getDatasetRecordingReady(),
      last_quest_input_ts: Date.now() / 1000,
      error_message: "",
    }, { force: true });
    ensureQuestXrVisualNodes();
    updateQuestXrVisualVisibility();
    startQuestControllerLoop();
    return;
  }

  const handStatus = getQuestHandInputStatus();
  setVrModeLocally("vr_hand_mode");
  vrControlOwner.value = "quest3_hand";
  vrSelectedJointGroup.value = questHandTeleop.getState().selected_joint_group;
  syncVrStateToBackend({
    mode: "vr_hand_mode",
    source: "quest3_hand",
    selected_joint_group: vrSelectedJointGroup.value,
    hand_tracking_available: Boolean(handStatus.ready),
    recording_ready: getDatasetRecordingReady(),
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
    questXrPresentingLostSinceAt.value = 0;
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
      recording_ready: getDatasetRecordingReady(),
      error_message: "",
    });

    const autoMode = selectedVrInputMode.value === "hand" ? "hand" : "controller";
    await chooseVrInputMode(autoMode);
    scheduleQuestXrInputRefresh(VR_MODE_TRANSITION_GUARD_MS);
    void runQuest3AccessChecks();
  } finally {
    vrEnterInProgress.value = false;
  }
}

function ensureVrModeActive() {
  if (!hasLocalQuestXrControlContext()) {
    return;
  }
  if (isQuestControllerModeActive() || isQuestHandModeActive()) {
    return;
  }
  const autoMode = selectedVrInputMode.value === "hand" ? "hand" : "controller";
  void chooseVrInputMode(autoMode);
}

function exitVrMode() {
  void cleanupQuestVrMode({
    mode: "vr_disabled",
    error_message: "",
    stop_session: true,
  });
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
    recording_ready: getDatasetRecordingReady(),
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
  if (hasLocalQuestXrControlContext() && selectedVrInputMode.value === "controller") {
    return vrModeState.value !== "vr_disabled" && vrModeState.value !== "vr_error";
  }
  return (
    vrModeState.value === "vr_controller_mode" &&
    (selectedVrInputMode.value === "controller" || vrControlOwner.value === "quest3_controller")
  );
}

function isQuestHandModeActive() {
  if (hasLocalQuestXrControlContext() && selectedVrInputMode.value === "hand") {
    return vrModeState.value !== "vr_disabled" && vrModeState.value !== "vr_error";
  }
  return (
    vrModeState.value === "vr_hand_mode" &&
    (selectedVrInputMode.value === "hand" || vrControlOwner.value === "quest3_hand")
  );
}

function isQuestTeleopControlActive() {
  return isQuestControllerModeActive() || isQuestHandModeActive();
}

function hasLocalQuestXrControlContext() {
  return Boolean(renderer?.xr?.isPresenting || activeQuestXrSession || getQuestXRSession());
}

function shouldBlockDesktopSliderSync() {
  return hasLocalQuestXrControlContext() && isQuestTeleopControlActive();
}

function rebuildQuestControllerTeleop() {
  questControllerTeleop = createQuestControllerTeleop({
    sensitivity: clamp(questControllerSensitivity.value, 0.4, 3.0),
    ...getQuestControllerTeleopThresholds(),
  });
}

function rebuildQuestHandTeleop() {
  questHandTeleop = createQuestHandTeleop({
    sensitivity: clamp(questHandSensitivity.value, 0.4, 3.0),
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

function readControllerSourcePose(xrFrame, referenceSpace, source) {
  const pose =
    (source?.gripSpace && xrFrame.getPose(source.gripSpace, referenceSpace)) ||
    (source?.targetRaySpace && xrFrame.getPose(source.targetRaySpace, referenceSpace)) ||
    null;
  if (!pose?.transform?.position) return null;

  const position = [
    Number(pose.transform.position.x),
    Number(pose.transform.position.y),
    Number(pose.transform.position.z),
  ];
  if (position.some((value) => !Number.isFinite(value))) return null;

  const orientation = pose.transform.orientation;
  return {
    tracked: true,
    handedness: String(source?.handedness || ""),
    position,
    quaternion: orientation
      ? [
          Number(orientation.x),
          Number(orientation.y),
          Number(orientation.z),
          Number(orientation.w),
        ]
      : null,
    pose_source: "webxr_frame",
    timestamp_ms: Date.now(),
  };
}

function readControllerNodePose(handedness = "") {
  const hand = normalizeXrHandedness(handedness);
  if (!hand) return null;
  const node = xrVisualNodes.controllerGrips[hand] || xrVisualNodes.controllerRays[hand] || null;
  if (!node || node.userData?.connected === false) return null;
  node.updateWorldMatrix?.(true, false);
  node.getWorldPosition(questControllerPoseWorldPosition);
  node.getWorldQuaternion(questControllerPoseWorldQuaternion);
  const position = [
    questControllerPoseWorldPosition.x,
    questControllerPoseWorldPosition.y,
    questControllerPoseWorldPosition.z,
  ];
  const quaternion = [
    questControllerPoseWorldQuaternion.x,
    questControllerPoseWorldQuaternion.y,
    questControllerPoseWorldQuaternion.z,
    questControllerPoseWorldQuaternion.w,
  ];
  if (position.some((value) => !Number.isFinite(value))) return null;
  if (quaternion.some((value) => !Number.isFinite(value))) return null;
  return {
    tracked: true,
    handedness: hand,
    position,
    quaternion,
    pose_source: "three_xr_node",
    timestamp_ms: Date.now(),
  };
}

function cloneHeldControllerPose(pose, nowMs = Date.now()) {
  if (!pose || !Array.isArray(pose.position)) return null;
  const ageMs = nowMs - Number(pose.timestamp_ms || 0);
  if (!Number.isFinite(ageMs) || ageMs > QUEST_CONTROLLER_POSE_HOLD_MS) return null;
  const baseSource = String(pose.pose_source || "pose").replace(/_held$/, "");
  return {
    ...pose,
    position: [...pose.position],
    quaternion: Array.isArray(pose.quaternion) ? [...pose.quaternion] : null,
    pose_source: `${baseSource}_held`,
  };
}

function readQuestControllerPoseSnapshot(xrFrame = null) {
  const nowMs = Date.now();
  const referenceSpace = getQuestXRReferenceSpace();
  if (!xrFrame || !referenceSpace) {
    const left =
      readControllerNodePose("left") ||
      cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.left, nowMs);
    const right =
      readControllerNodePose("right") ||
      cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.right, nowMs);
    const active =
      right ||
      left ||
      cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.active, nowMs);
    if (!active) {
      lastQuestControllerPoseSnapshot = null;
      return null;
    }

    lastQuestControllerPoseSnapshot = {
      ...active,
      left,
      right,
      active,
      timestamp_ms: nowMs,
    };
    return lastQuestControllerPoseSnapshot;
  }

  const sources = Array.from(xrFrame.session?.inputSources || []).filter(
    (source) => source && !source.hand
  );
  const leftSource = sources.find((source) => String(source?.handedness || "").toLowerCase() === "left") || null;
  const rightSource = sources.find((source) => String(source?.handedness || "").toLowerCase() === "right") || null;
  const left =
    (leftSource ? readControllerSourcePose(xrFrame, referenceSpace, leftSource) : null) ||
    readControllerNodePose("left") ||
    cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.left, nowMs);
  const right =
    (rightSource ? readControllerSourcePose(xrFrame, referenceSpace, rightSource) : null) ||
    readControllerNodePose("right") ||
    cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.right, nowMs);
  const fallbackSource = sources.find((source) => source !== leftSource && source !== rightSource) || sources[0];
  const fallback = fallbackSource ? readControllerSourcePose(xrFrame, referenceSpace, fallbackSource) : null;
  const active =
    right ||
    left ||
    fallback ||
    cloneHeldControllerPose(lastQuestControllerPoseSnapshot?.active, nowMs);
  if (!active) {
    lastQuestControllerPoseSnapshot = null;
    return null;
  }

  lastQuestControllerPoseSnapshot = {
    ...active,
    left,
    right,
    active,
    timestamp_ms: nowMs,
  };
  return lastQuestControllerPoseSnapshot;
}

function buildQuestControlPayload(mapped) {
  questControllerControlSeq.value += 1;
  const fallbackArm = getAuthoritativeArmRadians();
  return {
    target_positions: mapped.target_positions || fallbackArm,
    target_ee_pose: mapped.target_ee_pose || null,
    n_steps: VR_COMMAND_STEPS,
    control_mode: mapped.control_mode || (mapped.target_ee_pose ? "cartesian_servo" : "position"),
    expect_result: false,
    gripper_command: { mode: "open_close", value: mapped.gripper_opening },
    source: "quest3_controller",
    input_source: "quest3_controller",
    selected_joint_group: mapped.selected_joint_group,
    raw_input: mapped.raw_input || null,
    normalized_input: {
      ...(mapped.normalized_input || {}),
      cartesian_servo_command: mapped.target_ee_pose ? 1 : 0,
      ik_pose_command: mapped.target_ee_pose ? 1 : 0,
      control_seq: Number(questControllerControlSeq.value),
    },
  };
}

function buildQuestHandControlPayload(mapped) {
  questHandControlSeq.value += 1;
  const fallbackArm = getAuthoritativeArmRadians();
  return {
    target_positions: mapped.target_positions || fallbackArm,
    target_ee_pose: mapped.target_ee_pose || null,
    n_steps: VR_COMMAND_STEPS,
    control_mode: mapped.control_mode || (mapped.target_ee_pose ? "cartesian_servo" : "position"),
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
      cartesian_servo_command: mapped.target_ee_pose ? 1 : 0,
      ik_pose_command: mapped.target_ee_pose ? 1 : 0,
      control_seq: Number(questHandControlSeq.value),
    },
  };
}

function isQuestEePoseCommandPayload(payload = {}) {
  const mode = String(payload?.control_mode || "").trim();
  return mode === "cartesian_servo" || mode === "ik_pose" || Boolean(payload?.target_ee_pose);
}

function stageQuestRenderTarget(payload) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    clearQuestRenderPreview();
    return;
  }

  if (isQuestEePoseCommandPayload(payload)) {
    clearQuestRenderPreview();
    return;
  }

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
    controlSeq: Number(payload?.normalized_input?.control_seq) || null,
    source: String(payload?.source || "").trim(),
  };
  questRenderPreviewTarget.value = target;
}

function applyQuestCommandLocally(payload = {}) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
    return;
  }

  if (isQuestEePoseCommandPayload(payload)) {
    clearPendingManualTarget();
    stageQuestRenderTarget(payload);
    return;
  }

  const arm = Array.isArray(payload?.target_positions)
    ? payload.target_positions.slice(0, ARM_JOINT_COUNT).map((value) => Number(value))
    : null;
  if (arm && arm.length >= ARM_JOINT_COUNT && arm.every((value) => Number.isFinite(value))) {
    const opening = Number.isFinite(Number(payload?.gripper_command?.value))
      ? clamp(Number(payload.gripper_command.value), 0, 1)
      : getAuthoritativeGripperOpening();
    rememberPendingManualTarget(arm, opening);
  } else {
    clearPendingManualTarget();
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
    recording_ready: getDatasetRecordingReady(),
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

function runQuestControllerTick(nowOverrideMs = Date.now(), xrFrame = null) {
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
      grip: 0,
      left_trigger: 0,
      left_grip: 0,
      right_trigger: 0,
      right_grip: 0,
      next_episode: 0,
      active_hand: "",
    },
    raw: null,
  };
  handleDatasetControllerNextButton(snapshot, nowMs);
  const controllerPose = readQuestControllerPoseSnapshot(xrFrame);

  const mapped = questControllerTeleop.applySnapshot(
    snapshot,
    controllerPose,
    getAuthoritativeGripperOpening(),
    getAuthoritativeEePoseBackend(),
    getAuthoritativeArmRadians(),
    dtSec
  );
  const localControllerNormalizedInput = mapped
    ? {
        ...(mapped.normalized_input || {}),
        has_command: mapped.has_command ? 1 : 0,
        reason: mapped.reason || snapshot?.reason || "idle",
      }
    : null;
  const controllerUiReason = String(localControllerNormalizedInput?.reason || "idle");
  const shouldCommitControllerUi =
    !questControllerNormalizedInput.value ||
    questControllerAvailable.value !== Boolean(snapshot?.has_device) ||
    String(questControllerNormalizedInput.value?.reason || "") !== controllerUiReason ||
    nowMs - lastQuestControllerUiCommitAt >= QUEST_TELEOP_UI_MIN_INTERVAL_MS;
  if (shouldCommitControllerUi) {
    questControllerRawInput.value = snapshot?.raw || null;
    questControllerAvailable.value = Boolean(snapshot?.has_device);
    questControllerNormalizedInput.value = localControllerNormalizedInput;
    questControllerStatusText.value = snapshot?.has_device ? "采样中" : "运行中(等待输入)";
    lastQuestControllerUiCommitAt = nowMs;
  }

  if (mapped?.selected_joint_group) {
    if (vrSelectedJointGroup.value !== mapped.selected_joint_group) {
      updateQuestGroupToast(mapped.selected_joint_group_label || mapped.selected_joint_group);
    }
    vrSelectedJointGroup.value = mapped.selected_joint_group;
  }

  syncVrStateToBackend({
    mode: "vr_controller_mode",
    source: "quest3_controller",
    controller_available: Boolean(snapshot?.has_device),
    selected_joint_group: vrSelectedJointGroup.value,
    recording_ready: getDatasetRecordingReady(),
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
    if (shouldCommitControllerUi) questControllerStatusText.value = "输入保护中";
    return;
  }
  if (mapped?.reason === "controller_pose_unavailable") {
    if (shouldCommitControllerUi) questControllerStatusText.value = "等待手柄位姿";
    if (!mapped?.has_command) return;
  }
  if (mapped?.reason === "idle" && !mapped?.has_command && shouldCommitControllerUi) {
    questControllerStatusText.value = "按住握柄移动，扳机抓取";
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
    questHandNormalizedInput.value = null;
    markQuestHandSafeHold("手势会话未就绪", "session_not_ready");
    return;
  }

  const snapshot = readQuestHandSnapshot();
  const handTrackingStability = clamp(snapshot?.tracking_stability || 0, 0, 1);
  const shouldCommitHandUi =
    !questHandNormalizedInput.value ||
    nowMs - lastQuestHandUiCommitAt >= QUEST_TELEOP_UI_MIN_INTERVAL_MS;
  if (shouldCommitHandUi) {
    questHandRawInput.value = snapshot?.raw || null;
    questHandTrackingStability.value = handTrackingStability;
  }

  if (!snapshot?.available) {
    if (shouldCommitHandUi) {
      questHandNormalizedInput.value = {
        has_command: 0,
        reason: snapshot?.reason || "hand_not_tracked",
        tracking_stable: 0,
        tracking_stability: handTrackingStability,
      };
      lastQuestHandUiCommitAt = nowMs;
    }
    if (questHandUnavailableSinceAt.value <= 0) {
      questHandUnavailableSinceAt.value = nowMs;
    }
    const unavailableElapsed = nowMs - Number(questHandUnavailableSinceAt.value || nowMs);
    syncVrStateToBackend({
      mode: "vr_hand_mode",
      source: "quest3_hand",
      hand_tracking_available: false,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: getDatasetRecordingReady(),
      last_quest_input_ts: nowMs / 1000,
      raw_input: snapshot?.raw || null,
      normalized_input: {
        has_command: 0,
        reason: snapshot?.reason || "hand_not_tracked",
        tracking_stable: 0,
        tracking_stability: handTrackingStability,
      },
      error_message: "",
    });
    if (unavailableElapsed < QUEST_HAND_UNAVAILABLE_GRACE_MS) {
      if (shouldCommitHandUi) {
        questHandAvailable.value = true;
        questHandTrackingStable.value = false;
        questHandStatusText.value = "手势短暂波动，保持上一控制";
        lastQuestHandUiCommitAt = nowMs;
      }
      return;
    }
    markQuestHandSafeHold("未检测到稳定手势", "hand_not_tracked");
    return;
  }
  questHandUnavailableSinceAt.value = 0;

  const mapped = questHandTeleop.applySnapshot(
    snapshot,
    getAuthoritativeArmRadians(),
    getAuthoritativeGripperOpening(),
    getAuthoritativeEePoseBackend(),
    dtSec
  );
  const localHandInputMode = mapped?.hand_input_mode || "right_hand_ee_servo";
  const localHandTrackingStable = Boolean(mapped?.tracking_stable);
  const localHandNormalizedInput = mapped
    ? {
        ...(mapped.normalized_input || {}),
        has_command: mapped.has_command ? 1 : 0,
        reason: mapped.reason || "idle",
        tracking_stable: localHandTrackingStable ? 1 : 0,
        tracking_stability: mapped.tracking_stability ?? handTrackingStability,
        hand_input_mode: localHandInputMode,
      }
    : null;
  if (shouldCommitHandUi) {
    questHandAvailable.value = true;
    questHandTrackingStable.value = localHandTrackingStable;
    questHandInputMode.value = localHandInputMode;
    questHandNormalizedInput.value = localHandNormalizedInput;
    questHandStatusText.value = buildHandTrackingStatusText();
    lastQuestHandUiCommitAt = nowMs;
  }

  if (!mapped?.tracking_stable) {
    syncVrStateToBackend({
      mode: "vr_hand_mode",
      source: "quest3_hand",
      hand_tracking_available: true,
      selected_joint_group: vrSelectedJointGroup.value,
      recording_ready: getDatasetRecordingReady(),
      last_quest_input_ts: nowMs / 1000,
      raw_input: mapped?.raw_input || snapshot?.raw || null,
      normalized_input: {
        ...(mapped?.normalized_input || {}),
        has_command: 0,
        reason: mapped?.reason || "tracking_unstable",
        tracking_stable: 0,
        tracking_stability: mapped?.tracking_stability ?? clamp(snapshot?.tracking_stability || 0, 0, 1),
        hand_input_mode: localHandInputMode,
      },
      error_message: "",
    });
    if (questHandUnstableSinceAt.value <= 0) {
      questHandUnstableSinceAt.value = nowMs;
    }
    const unstableElapsed = nowMs - Number(questHandUnstableSinceAt.value || nowMs);
    if (unstableElapsed < QUEST_HAND_UNSTABLE_GRACE_MS) {
      if (shouldCommitHandUi) {
        questHandTrackingStable.value = false;
        questHandStatusText.value = "追踪短暂抖动，保持上一控制";
        lastQuestHandUiCommitAt = nowMs;
      }
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
    recording_ready: getDatasetRecordingReady(),
    last_quest_input_ts: nowMs / 1000,
    raw_input: mapped?.raw_input || snapshot?.raw || null,
    normalized_input: {
      ...(mapped?.normalized_input || {}),
      has_command: mapped?.has_command ? 1 : 0,
      reason: mapped?.reason || "idle",
      tracking_stable: mapped?.tracking_stable ? 1 : 0,
      tracking_stability: mapped?.tracking_stability ?? clamp(snapshot?.tracking_stability || 0, 0, 1),
      hand_input_mode: localHandInputMode,
      timestamp_ms: Number(snapshot?.timestamp_ms) || nowMs,
    },
    error_message: "",
  });

  if (mapped?.has_command) {
    sendQuestHandControlToBackend(mapped);
  }
}

function runQuestVrControlFrame(xrFrame = null) {
  syncQuestXrPresentationState(Date.now());
  const xrPresenting = Boolean(renderer?.xr?.isPresenting);
  if (!xrPresenting) {
    updateQuestXrVisualVisibility();
    return;
  }

  ensureQuestXrVisualNodes();
  updateQuestXrVisualVisibility();

  const nowMs = Date.now();
  if (isQuestControllerModeActive()) {
    runQuestControllerTick(nowMs, xrFrame);
  }
  if (isQuestHandModeActive()) {
    runQuestHandTick(nowMs);
  }
}

function handleQuestGamepadConnectionEvent(event) {
  if (!isQuestControllerModeActive()) return;
  if (event?.type === "gamepadconnected") {
    questControllerStatusText.value = "手柄已连接";
    scheduleQuestXrInputRefresh(80);
  } else if (event?.type === "gamepaddisconnected") {
    questControllerStatusText.value = "手柄已断开(可继续)";
    scheduleQuestXrInputRefresh(80);
  }
}

function startQuestControllerLoop() {
  stopQuestControllerLoop();
  rebuildQuestControllerTeleop();
  lastQuestControllerPoseSnapshot = null;
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
  lastQuestControllerPoseSnapshot = null;
  questControllerAvailable.value = false;
  questControllerStatusText.value = "未激活";
  questControllerRawInput.value = null;
  questControllerNormalizedInput.value = null;
  questControllerPendingMapped.value = null;
  lastQuestControllerSentAt.value = 0;
  resetQuestControllerQueuedFlushTimer();
  questControllerGroupToast.value = "";
  questControllerGroupToastAt.value = 0;
  lastQuestControllerTickAt.value = 0;
  lastQuestControllerUiCommitAt = 0;
  clearPendingManualTarget();
  clearQuestRenderPreview();
}

function stopQuestHandLoop() {
  stopQuestHandInput();
  questHandTeleop.reset();
  questHandAvailable.value = false;
  questHandStatusText.value = "未激活";
  questHandTrackingStable.value = false;
  questHandTrackingStability.value = 0;
  questHandInputMode.value = "right_hand_ee_servo";
  questHandRawInput.value = null;
  questHandNormalizedInput.value = null;
  questHandPendingMapped.value = null;
  lastQuestHandSentAt.value = 0;
  questHandUnstableSinceAt.value = 0;
  questHandUnavailableSinceAt.value = 0;
  resetQuestHandQueuedFlushTimer();
  questHandGroupToast.value = "";
  questHandGroupToastAt.value = 0;
  lastQuestHandTickAt.value = 0;
  lastQuestHandUiCommitAt = 0;
  clearPendingManualTarget();
  clearQuestRenderPreview();
}

function buildHandTrackingStatusText() {
  if (!questHandAvailable.value) return "未检测到稳定手势";
  if (!questHandTrackingStable.value) return "追踪不稳定(已保持)";
  const modeText = questHandInputMode.value === "right_hand_ee_servo" || questHandInputMode.value === "right_hand_ee_ik"
    ? "右手末端伺服"
    : questHandInputMode.value === "right_hand"
      ? "右手单手"
      : questHandInputMode.value === "left_hand_ee_servo" || questHandInputMode.value === "left_hand_ee_ik"
        ? "左手末端伺服"
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

  if (!STRICT_MUJOCO_RENDER_AUTHORITY && options.updateRenderTarget === true) {
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
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    clearQuestRenderPreview();
    return null;
  }

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
  clearRealtimeSliderDraft();
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

function mergeSimulationState(baseState, patchState) {
  if (!patchState || typeof patchState !== "object") return baseState;
  if (!baseState || typeof baseState !== "object") return patchState;
  return {
    ...baseState,
    ...patchState,
  };
}

function rememberLatestBackendMotionState(state) {
  if (!state || typeof state !== "object") return;
  latestMotionState = state;
}

function commitBackendStateSnapshot(state, options = {}) {
  if (!state || typeof state !== "object") return false;
  if (!acceptBackendStateTimestamp(state)) return false;

  const hadState = Boolean(simulationState.value);
  rememberLatestBackendMotionState(state);
  simulationState.value = state;
  lastStateUpdate.value = Date.now();
  updateSafetyFeedbackFromState(state);
  applyBackendStateToScene(state, {
    immediate: options.immediate === true || !hadState,
  });
  if (options.clearPendingManualTarget === true) {
    clearPendingManualTarget();
    clearRealtimeSliderDraft();
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

  const hadState = Boolean(simulationState.value);
  rememberLatestBackendMotionState(state);
  simulationState.value = state;
  applyVrStateFromBackend(state);
  checkD405ObservationReady(state);
  checkRecordingBindingReady(state);
  checkWebSocketReady();
  updateNetworkPrereq();
  updateSafetyFeedbackFromState(state);
  applyQuestBackendStateToScene(state, { immediate: !hadState });

  lastStateUpdate.value = nowMs;
  return true;
}

function commitDesktopControlStateSnapshot(state, nowMs = Date.now()) {
  if (!state || typeof state !== "object") return false;
  if (!acceptBackendStateTimestamp(state)) return false;

  const hadState = Boolean(simulationState.value);
  rememberLatestBackendMotionState(state);
  simulationState.value = state;
  applyVrStateFromBackend(state);
  checkD405ObservationReady(state);
  checkRecordingBindingReady(state);
  checkWebSocketReady();
  updateNetworkPrereq();
  updateSafetyFeedbackFromState(state);

  if (shouldApplyIncomingBackendState(state, nowMs)) {
    applyBackendStateToScene(state, { immediate: !hadState });
  } else {
    applySceneObjectsFromBackendState(state);
  }
  maybeClearRealtimeSliderDraftFromState(state);

  lastStateUpdate.value = nowMs;
  return true;
}

function applyRestoredSceneState(state) {
  if (!state || typeof state !== "object") return false;

  sendCommandPending.value = false;
  clearPendingManualTarget();
  clearRealtimeSliderDraft();
  clearQuestRenderPreview();
  lastRealtimeSliderSendAt.value = 0;

  const applied = commitBackendStateSnapshot(state, {
    immediate: true,
    clearPendingManualTarget: true,
  });
  if (!applied) {
    return false;
  }

  applyVrStateFromBackend(state);
  checkD405ObservationReady(state);
  checkRecordingBindingReady(state);
  checkWebSocketReady();
  updateNetworkPrereq();
  return true;
}

async function restoreSceneToInitialState() {
  if (sceneRestorePending.value) return;
  if (datasetEpisodeActive.value || datasetEpisodeInFlight.value || datasetAutoCollecting.value) {
    sceneRestoreStatusTone.value = "error";
    sceneRestoreStatusMessage.value = "采集进行中，当前不允许执行场景复原。";
    receivedText.value = sceneRestoreStatusMessage.value;
    return;
  }

  sceneRestorePending.value = true;
  sceneRestoreStatusTone.value = "idle";
  sceneRestoreStatusMessage.value = "正在复原场景...";
  receivedText.value = "正在复原场景...";

  stopQuestControllerLoop();
  stopQuestHandLoop();

  try {
    const response = await post("/sim/reset/", {}, { timeout: 12000 });
    const data = response?.data || {};
    if (String(data.status || "").toLowerCase() !== "success") {
      throw new Error(data.message || "场景复原失败");
    }
    if (!applyRestoredSceneState(data.state)) {
      throw new Error("场景复原后未收到有效状态");
    }

    sceneRestoreStatusTone.value = "success";
    sceneRestoreStatusMessage.value = "场景已恢复到初始状态。";
    receivedText.value = data.message || sceneRestoreStatusMessage.value;
  } catch (error) {
    sceneRestoreStatusTone.value = "error";
    sceneRestoreStatusMessage.value = "场景复原失败: " + (error?.message || error);
    receivedText.value = sceneRestoreStatusMessage.value;
    if (websocketManager.isConnected) {
      websocketManager.requestState();
    }
  } finally {
    sceneRestorePending.value = false;
    checkWebSocketReady();
    updateNetworkPrereq();
  }
}

function isBackendStateAlignedWithQuestPreview(state) {
  const preview = getFreshQuestRenderPreview();
  if (!preview) return true;
  if (!Array.isArray(preview.arm) || preview.arm.length < ARM_JOINT_COUNT) return true;

  const arm = getBackendArmRadiansFromState(state);
  if (!Array.isArray(arm) || arm.length < ARM_JOINT_COUNT) return false;

  let maxArmError = 0;
  for (let i = 0; i < ARM_JOINT_COUNT; i += 1) {
    const err = Math.abs(Number(arm[i]) - Number(preview.arm?.[i]));
    if (Number.isFinite(err) && err > maxArmError) {
      maxArmError = err;
    }
  }

  const backendGrip = getGripperRadiansFromBackendState(state);
  const gripError =
    backendGrip === null || !Number.isFinite(Number(preview.gripper))
      ? 0
      : Math.abs(Number(backendGrip) - Number(preview.gripper));

  return (
    maxArmError <= QUEST_PREVIEW_ARM_ALIGN_THRESHOLD_RAD &&
    gripError <= QUEST_PREVIEW_GRIPPER_ALIGN_THRESHOLD_RAD
  );
}

function isQuestBackendStateStaleForPreview(state) {
  const preview = getFreshQuestRenderPreview();
  if (!preview) return false;

  const previewSeq = Number(preview.controlSeq);
  const stateSeq = Number(state?.normalized_input?.control_seq);
  if (Number.isFinite(previewSeq) && Number.isFinite(stateSeq)) {
    return stateSeq < previewSeq;
  }

  return false;
}

function applyQuestBackendStateToScene(state, options = {}) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
    applyBackendStateToScene(state, options);
    return;
  }

  if (isQuestBackendStateStaleForPreview(state)) {
    applySceneObjectsFromBackendState(state);
    return;
  }

  if (isBackendStateAlignedWithQuestPreview(state)) {
    clearPendingManualTarget();
    clearQuestRenderPreview();
  }
  applyBackendStateToScene(state, options);
}

function isBackendStateAlignedWithTarget(state, armTarget, gripperTargetRad) {
  if (!Array.isArray(armTarget) || armTarget.length < ARM_JOINT_COUNT) {
    return true;
  }
  if (!Array.isArray(state?.qpos) || state.qpos.length < ARM_JOINT_COUNT) {
    return false;
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
    const error = Math.abs(backendValue - Number(armTarget[i]));
    if (error > maxArmError) maxArmError = error;
  }

  const backendGripper = getGripperRadiansFromBackendState(state);
  const gripperError =
    backendGripper === null ? 0 : Math.abs(Number(backendGripper) - Number(gripperTargetRad));

  return maxArmError <= ARM_STATE_MATCH_THRESHOLD_RAD && gripperError <= GRIPPER_STATE_MATCH_THRESHOLD_RAD;
}

function isBackendStateAlignedWithPendingTarget(state) {
  const pending = pendingManualTarget.value;
  if (!pending) return true;
  return isBackendStateAlignedWithTarget(state, pending.arm, pending.gripper);
}

function isSliderDrivenState(state) {
  if (!state || typeof state !== "object") return false;
  const source = String(state.source || "").trim().toLowerCase();
  const inputSource = String(state.input_source || "").trim().toLowerCase();
  return source === "desktop_manual" && (
    inputSource === "slider" ||
    inputSource === "joint_slider" ||
    inputSource === "slider_commit"
  );
}

function isBackendStateAlignedWithRealtimeSliderDraft(state) {
  const draft = getFreshRealtimeSliderDraft();
  if (!draft) return false;
  return isBackendStateAlignedWithTarget(
    state,
    draft.arm,
    clamp(Number(draft.gripperOpening), 0, 1) * GRIPPER_MAX_RAD
  );
}

function isBackendTargetAlignedWithRealtimeSliderDraft(state) {
  const draft = getFreshRealtimeSliderDraft();
  if (!draft) return false;
  const backendTargetArm = getBackendArmTargetFromState(state);
  if (!Array.isArray(backendTargetArm) || backendTargetArm.length < ARM_JOINT_COUNT) {
    return false;
  }

  let maxArmError = 0;
  for (let i = 0; i < ARM_JOINT_COUNT; i += 1) {
    const error = Math.abs(Number(backendTargetArm[i]) - Number(draft.arm[i]));
    if (Number.isFinite(error) && error > maxArmError) {
      maxArmError = error;
    }
  }

  const backendTargetGripper = getGripperTargetRadiansFromBackendState(state);
  const draftGripperRad = clamp(Number(draft.gripperOpening), 0, 1) * GRIPPER_MAX_RAD;
  const gripperError =
    backendTargetGripper === null
      ? Number.POSITIVE_INFINITY
      : Math.abs(Number(backendTargetGripper) - draftGripperRad);

  return (
    maxArmError <= ARM_TARGET_ACCEPT_THRESHOLD_RAD &&
    gripperError <= GRIPPER_TARGET_ACCEPT_THRESHOLD_RAD
  );
}

function shouldKeepRealtimeSliderPreview(state) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) return false;

  const draft = getFreshRealtimeSliderDraft();
  if (!draft) return false;
  if (isSliderDrivenState(state)) {
    return (
      isBackendTargetAlignedWithRealtimeSliderDraft(state) &&
      !isBackendStateAlignedWithRealtimeSliderDraft(state)
    );
  }

  const source = String(state?.source || "").trim();
  if (source.length > 0 && !LOCAL_MANUAL_SOURCES.has(source)) {
    return false;
  }

  return !isBackendStateAlignedWithRealtimeSliderDraft(state);
}

function maybeClearRealtimeSliderDraftFromState(state) {
  if (!realtimeSliderDraft.value) return;
  if (isBackendStateAlignedWithRealtimeSliderDraft(state)) {
    clearRealtimeSliderDraft();
  }
}

function isBackendTargetAlignedWithPendingTarget(state) {
  const pending = pendingManualTarget.value;
  const backendTargetArm = getBackendArmTargetFromState(state);
  if (!pending || !Array.isArray(backendTargetArm) || backendTargetArm.length < ARM_JOINT_COUNT) {
    return false;
  }

  let maxArmError = 0;
  for (let i = 0; i < ARM_JOINT_COUNT; i++) {
    const backendValue = Number(backendTargetArm[i]);
    if (!Number.isFinite(backendValue)) continue;
    const error = Math.abs(backendValue - pending.arm[i]);
    if (error > maxArmError) maxArmError = error;
  }

  const backendTargetGripper = getGripperTargetRadiansFromBackendState(state);
  const gripperError =
    backendTargetGripper === null
      ? Number.POSITIVE_INFINITY
      : Math.abs(Number(backendTargetGripper) - Number(pending.gripper));

  return (
    maxArmError <= ARM_TARGET_ACCEPT_THRESHOLD_RAD &&
    gripperError <= GRIPPER_TARGET_ACCEPT_THRESHOLD_RAD
  );
}

function shouldApplyIncomingBackendState(state, nowMs = Date.now()) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    clearPendingManualTarget();
    return true;
  }

  if (isQuestControlBackendState(state)) {
    clearPendingManualTarget();
    clearRealtimeSliderDraft();
    return true;
  }

  if (isSliderDrivenState(state)) {
    clearPendingManualTarget();
    return !shouldKeepRealtimeSliderPreview(state);
  }

  if (shouldKeepRealtimeSliderPreview(state)) {
    return false;
  }

  const pending = pendingManualTarget.value;
  if (!pending) return true;

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
    clearRealtimeSliderDraft();
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
    clearRealtimeSliderDraft();
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

function getManifestQuaternion(transform) {
  const rotation = normalizeManifestVector(transform?.rotation, 3, [0, 0, 0]);
  return new THREE.Quaternion().setFromEuler(
    new THREE.Euler(rotation[0], rotation[1], rotation[2], "XYZ")
  );
}

function getSceneObjectVisualQuaternion(model, physicsQuaternion) {
  if (!model.userData.physicsToVisualQuaternion) {
    const visualQuaternion =
      model.userData.manifestQuaternion instanceof THREE.Quaternion
        ? model.userData.manifestQuaternion
        : model.quaternion;
    model.userData.physicsToVisualQuaternion = physicsQuaternion
      .clone()
      .invert()
      .multiply(visualQuaternion)
      .normalize();
  }

  return physicsQuaternion
    .clone()
    .multiply(model.userData.physicsToVisualQuaternion)
    .normalize();
}

function getSceneObjectVisualOffsetWorld(model) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    return new THREE.Vector3(0, 0, 0);
  }

  const localOffset = model?.userData?.visualOffsetLocal;
  if (!(localOffset instanceof THREE.Vector3)) {
    return new THREE.Vector3(0, 0, 0);
  }
  return localOffset.clone().applyQuaternion(model.quaternion);
}

function resolveSceneObjectSupportPlaneTargetY(config) {
  const bodyOriginY = Number(config?.transform?.position?.[1]);
  if (!Number.isFinite(bodyOriginY)) return null;

  const explicitOffsetY = Number(config?.visualAlignment?.support_plane_offset_y);
  if (Number.isFinite(explicitOffsetY)) {
    return bodyOriginY + explicitOffsetY;
  }

  if (config?.visualAlignment?.support_plane_at_body_origin_y) {
    return bodyOriginY;
  }

  return null;
}

function resolveSceneObjectMinWorldY(config) {
  const minWorldY = Number(config?.visualAlignment?.min_world_y);
  if (Number.isFinite(minWorldY)) {
    return minWorldY;
  }
  return null;
}

function enforceSceneObjectVisualMinWorldY(model, config) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) return;
  if (!model) return;

  const minWorldY = resolveSceneObjectMinWorldY(config);
  if (!Number.isFinite(minWorldY)) return;

  const box = new THREE.Box3().setFromObject(model);
  if (box.isEmpty()) return;

  const deltaY = minWorldY - box.min.y;
  if (!Number.isFinite(deltaY) || deltaY <= 1e-6) return;

  model.position.y += deltaY;
}

function calibrateSceneObjectVisualAlignment(model, config) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) return;
  if (!model) return;

  const box = new THREE.Box3().setFromObject(model);
  if (box.isEmpty()) return;

  const targetY = resolveSceneObjectSupportPlaneTargetY(config);
  if (!Number.isFinite(targetY)) return;

  const deltaY = targetY - box.min.y;
  if (!Number.isFinite(deltaY) || Math.abs(deltaY) <= 1e-6) return;

  const manifestQuaternion =
    model.userData.manifestQuaternion instanceof THREE.Quaternion
      ? model.userData.manifestQuaternion
      : getManifestQuaternion(config.transform);
  model.userData.visualOffsetLocal = new THREE.Vector3(0, deltaY, 0).applyQuaternion(
    manifestQuaternion.clone().invert()
  );
  model.position.y += deltaY;
  enforceSceneObjectVisualMinWorldY(model, config);
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

function getLatestBackendMotionState() {
  return latestMotionState && typeof latestMotionState === "object"
    ? latestMotionState
    : simulationState.value;
}

function getAuthoritativeEePoseBackend() {
  const latestState = getLatestBackendMotionState();
  // Prefer the backend's explicit VR control pose when it is valid, but fall
  // back immediately to the real tool-frame ee_pose if that field is missing
  // or malformed on an older / partially restarted backend.
  const controlPose = normalizeBackendEePose(latestState?.control_ee_pose);
  if (controlPose) return controlPose;
  const backendPose = normalizeBackendEePose(latestState?.ee_pose);
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
  const arm = getBackendArmRadiansFromState(getLatestBackendMotionState());
  return Array.isArray(arm) && arm.length >= ARM_JOINT_COUNT ? arm : null;
}

function getAuthoritativeArmRadians() {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    const backendArm = getLatestBackendArmRadians();
    return backendArm || getCurrentSceneArmRadians();
  }

  const pending = pendingManualTarget.value;
  if (Array.isArray(pending?.arm) && pending.arm.length >= ARM_JOINT_COUNT) {
    return pending.arm.slice(0, ARM_JOINT_COUNT);
  }
  const preview = getFreshQuestRenderPreview();
  if (Array.isArray(preview?.arm) && preview.arm.length >= ARM_JOINT_COUNT) {
    return preview.arm.slice(0, ARM_JOINT_COUNT);
  }
  const backendArm = getLatestBackendArmRadians();
  return backendArm || getCurrentSceneArmRadians();
}

function getLatestBackendGripperRadians() {
  const gripperRadians = getGripperRadiansFromBackendState(getLatestBackendMotionState());
  return gripperRadians === null ? null : gripperRadians;
}

function getBackendArmTargetFromState(state) {
  if (!state || typeof state !== "object") return null;
  if (!Array.isArray(state.arm_target_qpos) || state.arm_target_qpos.length < ARM_JOINT_COUNT) {
    return null;
  }

  const incomingJointNames = Array.isArray(state.joint_names)
    ? state.joint_names.map((name) => String(name))
    : [];
  const armTargets = BACKEND_ARM_JOINT_NAMES.map((jointName, index) => {
    if (incomingJointNames.length > 0) {
      const incomingIndex = incomingJointNames.indexOf(jointName);
      if (incomingIndex >= 0) {
        const mappedValue = Number(state.arm_target_qpos[incomingIndex]);
        if (Number.isFinite(mappedValue)) return mappedValue;
      }
    }
    const fallback = Number(state.arm_target_qpos[index]);
    return Number.isFinite(fallback) ? fallback : 0;
  });

  return armTargets.every((value) => Number.isFinite(value)) ? armTargets : null;
}

function getBackendArmVelocitiesFromState(state) {
  if (!state || typeof state !== "object") return null;
  if (!Array.isArray(state.qvel) || state.qvel.length < ARM_JOINT_COUNT) return null;

  const incomingJointNames = Array.isArray(state.joint_names)
    ? state.joint_names.map((name) => String(name))
    : [];
  const armQvel = BACKEND_ARM_JOINT_NAMES.map((jointName, index) => {
    if (incomingJointNames.length > 0) {
      const incomingIndex = incomingJointNames.indexOf(jointName);
      if (incomingIndex >= 0) {
        const mappedValue = Number(state.qvel[incomingIndex]);
        if (Number.isFinite(mappedValue)) return mappedValue;
      }
    }
    const fallback = Number(state.qvel[index]);
    return Number.isFinite(fallback) ? fallback : 0;
  });

  return armQvel.every((value) => Number.isFinite(value)) ? armQvel : null;
}

function getGripperTargetRadiansFromBackendState(state) {
  if (!state || typeof state !== "object") return null;
  if (!Number.isFinite(Number(state.gripper_target_opening))) return null;
  return clamp(Number(state.gripper_target_opening), 0, 1) * GRIPPER_MAX_RAD;
}

function getGripperVelocityRadiansFromBackendState(state) {
  if (!state || typeof state !== "object") return null;
  if (!Array.isArray(state.qvel) || state.qvel.length <= ARM_JOINT_COUNT) return null;
  const velocity = Number(state.qvel[ARM_JOINT_COUNT]);
  return Number.isFinite(velocity) ? velocity : null;
}

function getBackendRenderPredictionLeadSeconds(state, nowMs = Date.now()) {
  const timestampMs = getBackendStateTimestampMs(state);
  const stateAgeMs = Number.isFinite(Number(timestampMs))
    ? clamp(nowMs - Number(timestampMs), 0, BACKEND_RENDER_MAX_PREDICTION_MS)
    : 0;
  return clamp(
    (stateAgeMs + BACKEND_RENDER_PREDICTION_MS) / 1000,
    0,
    BACKEND_RENDER_MAX_PREDICTION_MS / 1000
  );
}

function predictBackendScalar(current, velocity, target, leadSec, maxVelocityAbs, targetBlend) {
  const currentValue = Number(current);
  if (!Number.isFinite(currentValue)) {
    return Number.isFinite(Number(target)) ? Number(target) : 0;
  }

  let predicted = currentValue;
  const velocityValue = Number(velocity);
  if (Number.isFinite(velocityValue) && Number.isFinite(leadSec) && leadSec > 0) {
    predicted = currentValue + clamp(velocityValue, -maxVelocityAbs, maxVelocityAbs) * leadSec;
  }

  const targetValue = Number(target);
  if (Number.isFinite(targetValue)) {
    const low = Math.min(currentValue, targetValue);
    const high = Math.max(currentValue, targetValue);
    predicted = clamp(predicted, low, high);
    predicted = predicted + (targetValue - predicted) * clamp(targetBlend, 0, 1);
    predicted = clamp(predicted, low, high);
  }

  return predicted;
}

function getAuthoritativeGripperOpening() {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    const backendGripper = getLatestBackendGripperRadians();
    if (backendGripper !== null) {
      return toGripperOpening(backendGripper);
    }
    return toGripperOpening(getCurrentGripperRadians());
  }

  const pending = pendingManualTarget.value;
  if (Number.isFinite(Number(pending?.gripper))) {
    return toGripperOpening(Number(pending.gripper));
  }
  const preview = getFreshQuestRenderPreview();
  if (Number.isFinite(Number(preview?.gripper))) {
    return toGripperOpening(Number(preview.gripper));
  }
  const backendGripper = getLatestBackendGripperRadians();
  if (backendGripper !== null) {
    return toGripperOpening(backendGripper);
  }
  return toGripperOpening(getCurrentGripperRadians());
}

function shouldPredictBackendMotion(state) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) return false;

  const source = String(state?.source || "").trim();
  if (!source) return true;
  if (state?.collision_blocked) return false;
  if (LOCAL_MANUAL_SOURCES.has(source)) return false;
  return !isSliderDrivenState(state);
}

function buildBackendRenderTarget(state, nowMs = Date.now()) {
  const armRadians = getBackendArmRadiansFromState(state);
  if (!armRadians) return null;
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    const gripperRadians = getGripperRadiansFromBackendState(state);
    return {
      timestamp: nowMs,
      arm: armRadians.slice(0, ARM_JOINT_COUNT),
      gripper:
        gripperRadians === null
          ? clamp(getCurrentGripperRadians(), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD)
          : clamp(Number(gripperRadians), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD),
    };
  }

  const armTargetRadians = getBackendArmTargetFromState(state);
  const armVelocities = getBackendArmVelocitiesFromState(state);
  const allowPrediction = shouldPredictBackendMotion(state);
  const leadSec = allowPrediction ? getBackendRenderPredictionLeadSeconds(state, nowMs) : 0;
  const targetBlend = allowPrediction ? BACKEND_RENDER_TARGET_BLEND : 0;

  const gripperRadians = getGripperRadiansFromBackendState(state);
  const gripperTargetRadians = getGripperTargetRadiansFromBackendState(state);
  const gripperVelocity = getGripperVelocityRadiansFromBackendState(state);
  const clampedGripper =
    gripperRadians === null
      ? clamp(getCurrentGripperRadians(), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD)
      : clamp(Number(gripperRadians), GRIPPER_MIN_RAD, GRIPPER_MAX_RAD);
  const predictedArm = armRadians.map((value, index) =>
    predictBackendScalar(
      value,
      armVelocities?.[index],
      armTargetRadians?.[index],
      leadSec,
      BACKEND_RENDER_MAX_QVEL_RAD_S,
      targetBlend
    )
  );
  const predictedGripper = clamp(
    predictBackendScalar(
      clampedGripper,
      gripperVelocity,
      gripperTargetRadians,
      leadSec,
      BACKEND_RENDER_MAX_GRIPPER_QVEL_RAD_S,
      targetBlend
    ),
    GRIPPER_MIN_RAD,
    GRIPPER_MAX_RAD
  );

  return {
    timestamp: nowMs,
    arm: predictedArm,
    gripper: predictedGripper,
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

function scaleInterpolationAlpha(alpha, dtSec) {
  const baseAlpha = clamp(Number(alpha), 0.01, 1.0);
  const frameScale = clamp((Number(dtSec) || 1 / 60) * 60, 0.25, 2.5);
  return 1 - Math.pow(1 - baseAlpha, frameScale);
}

function getAdaptiveRenderAlpha(baseAlpha, errorRad) {
  const base = clamp(Number(baseAlpha), 0.01, 1.0);
  const t = clamp(
    (Math.abs(Number(errorRad) || 0) - RENDER_ADAPTIVE_LOW_ERROR_RAD) /
      (RENDER_ADAPTIVE_HIGH_ERROR_RAD - RENDER_ADAPTIVE_LOW_ERROR_RAD),
    0,
    1
  );
  return base * (0.45 + 1.3 * t);
}

function getSceneJointInterpolationAlpha(dtSec = 1 / 60, errorRad = 0) {
  if (STRICT_MUJOCO_RENDER_AUTHORITY) return 1.0;

  if (isVrModeEntered.value) {
    return scaleInterpolationAlpha(
      getAdaptiveRenderAlpha(VR_RENDER_SMOOTHING_ALPHA, errorRad),
      dtSec
    );
  }
  if (!backendPoseSmoothingEnabled.value) return 1.0;
  const alpha = Number(backendPoseSmoothingAlpha.value);
  if (!Number.isFinite(alpha)) return 1.0;
  return scaleInterpolationAlpha(getAdaptiveRenderAlpha(alpha, errorRad), dtSec);
}

function getMaxRenderPoseError(currentArm, targetArm, currentGrip, targetGrip) {
  let maxError = 0;
  for (let i = 0; i < Math.min(currentArm.length, targetArm.length, ARM_JOINT_COUNT); i += 1) {
    const error = Math.abs(Number(targetArm[i]) - Number(currentArm[i]));
    if (Number.isFinite(error) && error > maxError) maxError = error;
  }
  const gripperError = Math.abs(Number(targetGrip) - Number(currentGrip));
  return Number.isFinite(gripperError) ? Math.max(maxError, gripperError) : maxError;
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

  const currentArm = getCurrentSceneArmRadians();
  const currentGrip = getCurrentGripperRadians();
  const maxError = getMaxRenderPoseError(currentArm, target.arm, currentGrip, target.gripper);
  const alpha =
    options.immediate === true ? 1 : getSceneJointInterpolationAlpha(options.dtSec, maxError);
  const nextArm = interpolateArmPose(currentArm, target.arm, alpha);
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
  const config = SCENE_OBJECT_CONFIGS.find((item) => item?.id === objectId) || null;
  model.visible = true;
  model.userData.hasMujocoState = true;

  const quaternionFrontend = backendQuaternionToFrontend(objectState.quaternion);
  if (quaternionFrontend) {
    model.quaternion.copy(getSceneObjectVisualQuaternion(model, quaternionFrontend));
  }

  const positionFrontend = backendPositionToFrontend(objectState.position);
  if (positionFrontend) {
    const offsetWorld = getSceneObjectVisualOffsetWorld(model);
    model.position.set(
      positionFrontend[0] + offsetWorld.x,
      positionFrontend[1] + offsetWorld.y,
      positionFrontend[2] + offsetWorld.z
    );
  }

  enforceSceneObjectVisualMinWorldY(model, config);
}

function applySceneObjectsFromBackendState(state) {
  if (!state?.objects || typeof state.objects !== "object") return;
  Object.entries(state.objects).forEach(([objectId, objectState]) => {
    applySceneObjectPoseFromBackend(objectId, objectState);
  });
  updateClientPhysicsMirrorDiagnostics();
}

function applyBackendStateToScene(state, options = {}) {
  if (!state || typeof state !== "object") return;

  const renderTarget = buildBackendRenderTarget(state, Date.now());
  const previewTarget =
    !STRICT_MUJOCO_RENDER_AUTHORITY && options.preferQuestPreview === true
      ? getFreshQuestRenderPreview()
      : null;
  const visualTarget = previewTarget || renderTarget;
  if (visualTarget) {
    backendRenderTarget.value = visualTarget;
    if (STRICT_MUJOCO_RENDER_AUTHORITY || options.immediate === true) {
      applySmoothedBackendPose({ immediate: true });
    }
  }

  isApplyingBackendState.value = true;
  try {
    applySceneObjectsFromBackendState(state);
    if (visualTarget) {
      const forceUiSync = options.immediate === true;
      syncJointDisplayFromSceneIfNeeded(forceUiSync);
      syncEndEffectorPoseIfNeeded(forceUiSync);
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
    clearRealtimeSliderDraft();
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
      clearRealtimeSliderDraft();
      try {
        const latest = await get("/sim/state/", { timeout: 1500 });
        if (latest?.data) {
          commitBackendStateSnapshot(latest.data);
        }
      } catch (_) {}
      return { ok: false, message: resp?.data?.message || "Command rejected due to collision/interference." };
    }

    if (resp?.data?.state?.qpos && Array.isArray(resp.data.state.qpos)) {
      commitDesktopControlStateSnapshot(resp.data.state);
    }

    return { ok: true, message: resp.data?.message || "Command sent (HTTP)." };
  } catch (err) {
    clearPendingManualTarget();
    clearRealtimeSliderDraft();
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
      return;
    }

    const result = await sendArmCommandToBackend(armRadians, {
      n_steps: 50,
      control_mode: "position",
      gripper_opening: toGripperOpening(radians[ARM_JOINT_COUNT]),
    });
    receivedText.value = result.message;
    setAnglesResponse.value = [...normalizedAngles];
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
    fetchInterval.value = setInterval(fetchData, HTTP_STATE_FALLBACK_INTERVAL_MS); // fallback
  }
  console.log("已连接机器人，开始同步位置");
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
}

function normalizeManifestVector(values, expectedLength, fallback) {
  if (!Array.isArray(values) || values.length < expectedLength) {
    return fallback.slice(0, expectedLength);
  }
  const parsed = values.slice(0, expectedLength).map((value, index) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback[index];
  });
  return parsed.length === expectedLength ? parsed : fallback.slice(0, expectedLength);
}

function resolvePublicAssetPath(resourcePath, fallbackPath) {
  const raw = String(resourcePath || "").trim();
  if (!raw) return fallbackPath;
  if (raw.startsWith("frontend/public/")) {
    return "./" + raw.slice("frontend/public/".length);
  }
  if (raw.startsWith("public/")) {
    return "./" + raw.slice("public/".length);
  }
  if (raw.startsWith("./") || raw.startsWith("../") || raw.startsWith("/")) {
    return raw;
  }
  return "./" + raw;
}

function buildManifestTransform(transform, fallback) {
  return {
    position: normalizeManifestVector(transform?.position, 3, fallback.position),
    rotation: normalizeManifestVector(transform?.rotation_rpy, 3, fallback.rotation),
    scale: normalizeManifestVector(transform?.scale, 3, fallback.scale),
  };
}

function normalizePhysicsConfig(physics) {
  if (!physics || typeof physics !== "object") return null;
  const collisionProxies = Array.isArray(physics.collision_proxies)
    ? physics.collision_proxies
        .map((proxy) => (proxy && typeof proxy === "object" ? { ...proxy } : null))
        .filter(Boolean)
    : [];
  return {
    ...physics,
    collision_proxies: collisionProxies,
  };
}

const DEFAULT_ROBOT_SCENE_CONFIG = {
  assetPath: "./ur5/ur5.urdf",
  transform: {
    position: [-0.2, 0.5, 0.0],
    rotation: [-Math.PI / 2, 0.0, 0.0],
    scale: [1.0, 1.0, 1.0],
  },
};

const DEFAULT_SCENE_OBJECT_CONFIGS = [
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

const manifestRobot = sceneManifest?.robot || {};
const ROBOT_SCENE_CONFIG = {
  assetPath: resolvePublicAssetPath(manifestRobot.resource_path, DEFAULT_ROBOT_SCENE_CONFIG.assetPath),
  transform: buildManifestTransform(manifestRobot.transform, DEFAULT_ROBOT_SCENE_CONFIG.transform),
};

const manifestObjectConfigs = Array.isArray(sceneManifest?.objects)
  ? sceneManifest.objects
      .map((item) => {
        const objectId = String(item?.id || "").trim();
        if (!objectId) return null;
        return {
          id: objectId,
          assetPath: resolvePublicAssetPath(item?.resource_path, ""),
          transform: buildManifestTransform(item?.transform, {
            position: [0, 0, 0],
            rotation: [0, 0, 0],
            scale: [1, 1, 1],
          }),
          visualAlignment:
            item?.visual_alignment && typeof item.visual_alignment === "object"
              ? { ...item.visual_alignment }
              : null,
          physics: normalizePhysicsConfig(item?.physics),
        };
      })
      .filter((item) => item && item.assetPath)
  : [];

const urdf = ROBOT_SCENE_CONFIG.assetPath;
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
const SCENE_OBJECT_CONFIGS =
  manifestObjectConfigs.length > 0 ? manifestObjectConfigs : DEFAULT_SCENE_OBJECT_CONFIGS;

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
    case "d405":
      showD405Panel.value = !showD405Panel.value;
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

function updateRealtimeSliderDraft(name, value, options = {}) {
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
  if (!STRICT_MUJOCO_RENDER_AUTHORITY && options.applyPreview !== false) {
    backendRenderTarget.value = {
      timestamp: nextDraft.updatedAt,
      arm: arm.slice(0, ARM_JOINT_COUNT),
      gripper: gripperOpening * GRIPPER_MAX_RAD,
    };
    if (options.immediate === true) {
      applySmoothedBackendPose({ immediate: true });
    }
  }
  return nextDraft;
}

function sendRealtimeSliderControl(options = {}) {
  const force = options.force === true;
  const expectResult = options.expectResult === true;
  const inputSource =
    typeof options.inputSource === "string" && options.inputSource.trim().length > 0
      ? options.inputSource.trim()
      : "slider";
  const commandSteps = Number.isFinite(Number(options.n_steps))
    ? Math.max(1, Math.floor(Number(options.n_steps)))
    : REALTIME_SLIDER_COMMAND_STEPS;
  if (isApplyingBackendState.value && !force) return;
  const now = Date.now();
  if (
    !force &&
    now - Number(lastRealtimeSliderSendAt.value) < REALTIME_SLIDER_MIN_SEND_INTERVAL_MS
  ) {
    scheduleRealtimeSliderSync();
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
  const controlSeq = Number(options.controlSeq) || (desktopSliderControlSeq.value += 1);
  rememberPendingManualTarget(armRadians, gripperOpening, { updateRenderTarget: true });

  const sent = websocketManager.isConnected
    ? websocketManager.sendControlCommand(armRadians, {
        n_steps: commandSteps,
        control_mode: "position",
        gripper_command: gripperCommand,
        source: "desktop_manual",
        input_source: inputSource,
        raw_input: {
          origin: "frontend",
          input_source: inputSource,
        },
        normalized_input: {
          control_seq: controlSeq,
        },
        expect_result: expectResult,
        ack: expectResult,
      })
    : false;

  if (sent) {
    lastRealtimeSliderSendAt.value = now;
    if (expectResult) {
      sendCommandPending.value = true;
      window.setTimeout(() => {
        if (sendCommandPending.value) {
          sendCommandPending.value = false;
          if (websocketManager.isConnected) {
            websocketManager.requestState();
          }
        }
      }, 2500);
    }
  } else {
    if (realtimeSliderFallbackInFlight.value) {
      return;
    }
    realtimeSliderFallbackInFlight.value = true;
    post("/sim/step/", {
      target_positions: armRadians,
      n_steps: commandSteps,
      control_mode: "position",
      gripper_command: gripperCommand,
      source: "desktop_manual",
      input_source: inputSource,
      raw_input: {
        origin: "frontend",
        input_source: inputSource,
      },
      normalized_input: {
        control_seq: controlSeq,
      },
    })
      .then((resp) => {
        const status = String(resp?.data?.status || "").toLowerCase();
        if (resp?.data?.state) {
          commitDesktopControlStateSnapshot(resp.data.state);
        } else if (status !== "success") {
          clearPendingManualTarget();
          clearRealtimeSliderDraft();
          if (websocketManager.isConnected) {
            websocketManager.requestState();
          }
        }
      })
      .catch((error) => {
        console.warn("实时滑条 HTTP 兜底失败:", error?.message || error);
        clearPendingManualTarget();
        clearRealtimeSliderDraft();
      })
      .finally(() => {
        realtimeSliderFallbackInFlight.value = false;
        lastRealtimeSliderSendAt.value = Date.now();
      });
  }
}

function scheduleRealtimeSliderSync() {
  if (shouldBlockDesktopSliderSync()) {
    // Only block desktop slider sync while Quest is actively teleoperating.
    // This keeps PC sliders available during VR ready/standby, but prevents
    // stale desktop commands from fighting the live Quest control stream on
    // the same immersive page.
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
  if (shouldBlockDesktopSliderSync()) {
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
  const skipBackendSync = options.skipBackendSync === true || shouldBlockDesktopSliderSync();
  const skipPoseUpdate = options.skipPoseUpdate === true;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return;
  const physicsAuthoritative = websocketManager.isConnected && !skipBackendSync;

  if (name === "gripper_joint") {
    if (physicsAuthoritative) {
      updateRealtimeSliderDraft(name, numericValue, { immediate: true });
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
    const draft = updateRealtimeSliderDraft(name, numericValue, { immediate: true });
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
  if (websocketManager.isConnected && !shouldBlockDesktopSliderSync()) {
    if (sliderSyncTimer.value) {
      clearTimeout(sliderSyncTimer.value);
      sliderSyncTimer.value = null;
    }
    sendRealtimeSliderControl({
      force: true,
      inputSource: "slider_commit",
      n_steps: 60,
      expectResult: true,
    });
    return;
  }
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
const scenePhysicsProxyGroups = new Map();
let lastClientPhysicsWarningAt = 0;
let wristCameraMountModel = null;
const QUEST_CONTROLLER_MODEL_PATHS = {
  left: "./webxr-input-profiles/profiles/meta-quest-touch-plus-v2/left.glb",
  right: "./webxr-input-profiles/profiles/meta-quest-touch-plus-v2/right.glb",
};
const questControllerModelLoader = new GLTFLoader();
const questControllerModelCache = new Map();
const questControllerModelPromiseCache = new Map();
const xrHandModelFactory = new XRHandModelFactory();
const xrVisualNodes = {
  controllerGrips: { left: null, right: null },
  controllerRays: { left: null, right: null },
  hands: { left: null, right: null },
};
const questControllerPoseWorldPosition = new THREE.Vector3();
const questControllerPoseWorldQuaternion = new THREE.Quaternion();
let activeQuestXrSession = null;
let questXrVisibilityHandler = null;
let questXrInputSourcesHandler = null;
let questXrEndedHandler = null;
let questXrSourceRefreshTimer = null;
let questVrExitInFlight = false;

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

  const questRenderProfile = Boolean(isQuest3Device.value);
  // Quest 浏览器/GPU 预算有限；桌面保留高质量渲染，Quest 走低开销配置。
  renderer = new THREE.WebGLRenderer({
    antialias: !questRenderProfile,
    logarithmicDepthBuffer: !questRenderProfile,
    powerPreference: "high-performance",
  });

  // 设置渲染器尺寸
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(getRenderPixelRatio());
  renderer.xr.enabled = true;
  if (
    questRenderProfile &&
    renderer.xr &&
    typeof renderer.xr.setFramebufferScaleFactor === "function"
  ) {
    renderer.xr.setFramebufferScaleFactor(QUEST_XR_FRAMEBUFFER_SCALE);
  }

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
function render(_, xrFrame) {
  const nowMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  const prevMs = Number(lastRenderFrameAt.value || nowMs);
  lastRenderFrameAt.value = nowMs;
  const dtSec = clamp((nowMs - prevMs) / 1000, 1 / 120, 1 / 20);

  // Keep approaching latest backend state between WS ticks for visually smooth motion.
  applySmoothedBackendPose({ dtSec });
  // In immersive XR, browser timer throttling can stall setInterval-based teleop loops.
  // Drive Quest teleop ticks from the XR render loop to match AR-UR5 control behavior.
  runQuestVrControlFrame(xrFrame);
  updateQuestControllerVisualState();
  updateQuestHandSkeletonFallbacks();
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

function makeCollisionProxyMaterial() {
  return new THREE.MeshBasicMaterial({
    color: 0x21a3ff,
    transparent: true,
    opacity: SHOW_MUJOCO_COLLISION_PROXIES ? 0.18 : 0.0,
    depthWrite: false,
    wireframe: true,
  });
}

function getProxyLocalQuaternion(proxy) {
  const quat = normalizeManifestVector(proxy?.quaternion_xyzw, 4, [0, 0, 0, 1]);
  if (Array.isArray(proxy?.quaternion_xyzw) && proxy.quaternion_xyzw.length >= 4) {
    return new THREE.Quaternion(quat[0], quat[1], quat[2], quat[3]).normalize();
  }

  const rpy = normalizeManifestVector(proxy?.rotation_rpy, 3, [0, 0, 0]);
  if (Array.isArray(proxy?.rotation_rpy) && proxy.rotation_rpy.length >= 3) {
    return new THREE.Quaternion().setFromEuler(new THREE.Euler(rpy[0], rpy[1], rpy[2], "XYZ"));
  }

  return new THREE.Quaternion();
}

function createBoxCollisionProxy(proxy, material) {
  const halfSize = normalizeManifestVector(proxy?.size, 3, [0, 0, 0]);
  if (halfSize.some((value) => value <= 0)) return null;
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(halfSize[0] * 2, halfSize[1] * 2, halfSize[2] * 2),
    material
  );
  mesh.position.fromArray(normalizeManifestVector(proxy?.position, 3, [0, 0, 0]));
  mesh.quaternion.copy(getProxyLocalQuaternion(proxy));
  return mesh;
}

function createCapsuleCollisionProxy(proxy, material) {
  const fromto = normalizeManifestVector(proxy?.fromto, 6, [0, 0, 0, 0, 0, 0]);
  const radius = Math.max(0, Number(proxy?.size?.[0] ?? proxy?.radius ?? 0));
  if (!Number.isFinite(radius) || radius <= 0) return null;

  const start = new THREE.Vector3(fromto[0], fromto[1], fromto[2]);
  const end = new THREE.Vector3(fromto[3], fromto[4], fromto[5]);
  const axis = end.clone().sub(start);
  const length = axis.length();
  if (!Number.isFinite(length) || length <= 1e-6) return null;

  const mesh = new THREE.Mesh(
    new THREE.CapsuleGeometry(radius, Math.max(0, length - radius * 2), 8, 12),
    material
  );
  mesh.position.copy(start.clone().add(end).multiplyScalar(0.5));
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis.normalize());
  mesh.quaternion.multiply(getProxyLocalQuaternion(proxy));
  return mesh;
}

function createSceneCollisionProxy(proxy, objectId, material) {
  const type = String(proxy?.type || "").trim().toLowerCase();
  const mesh =
    type === "box"
      ? createBoxCollisionProxy(proxy, material)
      : type === "capsule"
        ? createCapsuleCollisionProxy(proxy, material)
        : null;
  if (!mesh) return null;

  mesh.name = String(proxy?.name || `${objectId}_${type}_collision`);
  mesh.visible = SHOW_MUJOCO_COLLISION_PROXIES;
  mesh.userData.mujocoCollisionProxy = true;
  mesh.userData.objectId = objectId;
  mesh.userData.proxyType = type;
  mesh.userData.proxyName = mesh.name;
  return mesh;
}

function attachSceneObjectPhysicsProxies(model, config) {
  if (!model || !config?.physics) return;

  const existing = scenePhysicsProxyGroups.get(config.id);
  if (existing?.parent) {
    existing.parent.remove(existing);
  }

  const proxies = Array.isArray(config.physics.collision_proxies)
    ? config.physics.collision_proxies
    : [];
  if (proxies.length === 0) return;

  const group = new THREE.Group();
  group.name = `${config.id}_mujoco_collision_proxies`;
  group.userData.mujocoPhysicsSource = config.physics.source || "";
  const material = makeCollisionProxyMaterial();

  proxies.forEach((proxy) => {
    const mesh = createSceneCollisionProxy(proxy, config.id, material);
    if (mesh) group.add(mesh);
  });

  if (group.children.length === 0) return;
  model.add(group);
  scenePhysicsProxyGroups.set(config.id, group);
}

function shouldSkipClientPhysicsPair(left, right) {
  if (!left || !right) return true;
  if (left.objectId === right.objectId) return true;
  const pair = new Set([left.objectId, right.objectId]);
  if (pair.has("rack")) return true;
  if (pair.has("toolbox")) {
    return true;
  }
  return false;
}

function getBoxIntersectionDepth(a, b) {
  const overlapX = Math.min(a.max.x, b.max.x) - Math.max(a.min.x, b.min.x);
  const overlapY = Math.min(a.max.y, b.max.y) - Math.max(a.min.y, b.min.y);
  const overlapZ = Math.min(a.max.z, b.max.z) - Math.max(a.min.z, b.min.z);
  if (
    overlapX <= CLIENT_PHYSICS_INTERFERENCE_EPSILON_M ||
    overlapY <= CLIENT_PHYSICS_INTERFERENCE_EPSILON_M ||
    overlapZ <= CLIENT_PHYSICS_INTERFERENCE_EPSILON_M
  ) {
    return 0;
  }
  return Math.min(overlapX, overlapY, overlapZ);
}

function collectClientPhysicsInterferences() {
  const entries = [];
  scenePhysicsProxyGroups.forEach((group, objectId) => {
    if (!group?.parent || group.parent.visible === false) return;
    group.updateWorldMatrix(true, true);
    group.traverse((child) => {
      if (!child?.userData?.mujocoCollisionProxy) return;
      const bounds = new THREE.Box3().setFromObject(child);
      if (bounds.isEmpty()) return;
      entries.push({
        objectId,
        proxyName: child.userData.proxyName || child.name || objectId,
        bounds,
      });
    });
  });

  const interferences = [];
  for (let leftIdx = 0; leftIdx < entries.length; leftIdx += 1) {
    for (let rightIdx = leftIdx + 1; rightIdx < entries.length; rightIdx += 1) {
      const left = entries[leftIdx];
      const right = entries[rightIdx];
      if (shouldSkipClientPhysicsPair(left, right)) continue;
      const depth = getBoxIntersectionDepth(left.bounds, right.bounds);
      if (depth <= 0) continue;
      interferences.push({
        body_a: left.objectId,
        body_b: right.objectId,
        proxy_a: left.proxyName,
        proxy_b: right.proxyName,
        dist: -depth,
      });
    }
  }
  return interferences;
}

function updateClientPhysicsMirrorDiagnostics() {
  if (!STRICT_MUJOCO_RENDER_AUTHORITY) return;
  const interferences = collectClientPhysicsInterferences();
  if (interferences.length === 0) return;

  const now = Date.now();
  if (now - lastClientPhysicsWarningAt < 1000) return;
  lastClientPhysicsWarningAt = now;
  console.warn("前端 MuJoCo 碰撞代理检测到镜像干涉:", interferences.slice(0, 3));
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
      result.userData.manifestQuaternion = getManifestQuaternion(config.transform);
      attachSceneObjectPhysicsProxies(result, config);
      calibrateSceneObjectVisualAlignment(result, config);
      enforceSceneObjectVisualMinWorldY(result, config);
      result.userData.hasMujocoState = false;
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

      const { position, rotation, scale } = ROBOT_SCENE_CONFIG.transform;
      robot.scale.set(scale[0], scale[1], scale[2]);
      robot.rotation.set(rotation[0], rotation[1], rotation[2]);
      robot.position.set(position[0], position[1], position[2]);
      scene.add(robot);
      attachWristCameraMount();
      focusCameraOnObject(robot);
      sliderInput(-Math.PI / 2, "shoulder_lift_joint");
      sliderInput(Math.PI / 2, "elbow_joint");
      sliderInput(-Math.PI / 2, "wrist_1_joint");
      sliderInput(-Math.PI / 2, "wrist_2_joint");
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

  websocketManager.on('motionUpdate', (data) => {
    handleMotionUpdate(data);
  });

  websocketManager.on('sceneUpdate', (data) => {
    handleSceneUpdate(data);
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
        commitDesktopControlStateSnapshot(data.state);
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
      clearRealtimeSliderDraft();
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

  websocketManager.on('resetResult', (data) => {
    sendCommandPending.value = false;
    if (data?.status && String(data.status).toLowerCase() !== "success") {
      sceneRestoreStatusTone.value = "error";
      sceneRestoreStatusMessage.value = data?.message || "场景复原失败。";
      receivedText.value = sceneRestoreStatusMessage.value;
      if (websocketManager.isConnected) {
        websocketManager.requestState();
      }
      return;
    }
    if (applyRestoredSceneState(data?.state)) {
      sceneRestoreStatusTone.value = "success";
      sceneRestoreStatusMessage.value = "场景已恢复到初始状态。";
      receivedText.value = data?.message || sceneRestoreStatusMessage.value;
    }
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
const handleMotionUpdate = (data) => {
  const now = Date.now();
  const hadState = Boolean(simulationState.value);
  if (!acceptBackendStateTimestamp(data)) {
    return;
  }

  rememberLatestBackendMotionState(data);

  const shouldCommitReactiveState =
    !simulationState.value ||
    Boolean(data?.collision_blocked) ||
    now - lastReactiveMotionCommitAt >= UI_REACTIVE_MOTION_MIN_INTERVAL_MS;
  const uiState = shouldCommitReactiveState
    ? mergeSimulationState(simulationState.value, data)
    : simulationState.value;

  if (shouldCommitReactiveState && uiState) {
    simulationState.value = uiState;
    lastReactiveMotionCommitAt = now;
  }

  updateSafetyFeedbackFromState(data);

  if (isQuestControlBackendState(data)) {
    applyQuestBackendStateToScene(data, { immediate: !hadState });
  } else if (shouldApplyIncomingBackendState(data, now)) {
    applyBackendStateToScene(data, { immediate: !hadState });
  } else {
    applySceneObjectsFromBackendState(data);
  }
  maybeClearRealtimeSliderDraftFromState(data);

  const prevPacketAt = lastMotionPacketAt;
  lastMotionPacketAt = now;
  if (now - lastSyncStatsCommitAt >= SYNC_STATS_MIN_INTERVAL_MS) {
    if (data.timestamp) {
      const serverTime = data.timestamp * 1000;
      networkLatency.value = now - serverTime;
    }
    addToStateBuffer(data, now);
    updateSyncStats(now, prevPacketAt);
    updateConnectionQuality();
    lastStateUpdate.value = now;
    lastSyncStatsCommitAt = now;
  }
};

const handleSceneUpdate = (data) => {
  const now = Date.now();
  const merged = mergeSimulationState(simulationState.value, data);
  if (!acceptBackendStateTimestamp(merged)) {
    return;
  }

  rememberLatestBackendMotionState(merged);
  simulationState.value = merged;
  lastReactiveMotionCommitAt = now;
  applyVrStateFromBackend(merged);
  checkD405ObservationReady(merged);
  checkRecordingBindingReady(merged);
  checkWebSocketReady();
  updateNetworkPrereq();
  updateSafetyFeedbackFromState(merged);
  applySceneObjectsFromBackendState(merged);
  lastStateUpdate.value = now;
};

const handleStateUpdate = (data) => {
  const now = Date.now();
  const prevUpdate = lastStateUpdate.value;
  const hadState = Boolean(simulationState.value);
  if (!acceptBackendStateTimestamp(data)) {
    return;
  }

  rememberLatestBackendMotionState(data);
  lastReactiveMotionCommitAt = now;

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
    applyQuestBackendStateToScene(data, { immediate: !hadState });
  } else if (shouldApplyIncomingBackendState(data, now)) {
    // 以后端回传状态为准，统一驱动机器人/夹爪/对象（带平滑）
    applyBackendStateToScene(data, { immediate: !hadState });
  } else {
    // Guard 命中时维持本地最新目标，不使用这帧滞后状态更新目标姿态。
    applySceneObjectsFromBackendState(data);
  }
  maybeClearRealtimeSliderDraftFromState(data);

  // 添加到状态历史缓冲区
  addToStateBuffer(data, now);

  // 更新统计信息
  updateSyncStats(now, prevUpdate);
  updateConnectionQuality();

  lastStateUpdate.value = now;
};

// 保留轻量时间戳缓冲，避免对完整状态做高频深拷贝导致界面卡顿。
const addToStateBuffer = (state, timestamp) => {
  const maxSize = clamp(Number(stateBufferSize.value) || 10, 2, 60);
  const lightweightState = {
    timestamp: state?.timestamp,
    qpos: Array.isArray(state?.qpos) ? state.qpos.slice(0, ARM_JOINT_COUNT + 1) : [],
  };
  const nextHistory = [...stateUpdateHistory.value, { state: lightweightState, timestamp }];
  if (nextHistory.length > maxSize) {
    nextHistory.splice(0, nextHistory.length - maxSize);
  }
  stateUpdateHistory.value = nextHistory;
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
  latestMotionState = null;
  lastReactiveMotionCommitAt = 0;
  lastSyncStatsCommitAt = 0;
  lastMotionPacketAt = 0;
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
  if (STRICT_MUJOCO_RENDER_AUTHORITY) {
    stateInterpolationEnabled.value = false;
    backendPoseSmoothingEnabled.value = false;
    if (simulationState.value) {
      applyBackendStateToScene(simulationState.value, { immediate: true });
    }
    console.log("状态插值: 禁用（MuJoCo物理状态权威）");
    return;
  }

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

  loadDatasetTemplates();
  runQuest3AccessChecks();
});

watch(isVrModeEntered, (entered) => {
  if (!entered || !hasLocalQuestXrControlContext()) return;
  ensureVrModeActive();
});

onBeforeUnmount(() => {
  stopDatasetAutoCollection();
  clearDatasetAutoDelay(true);
  stopDatasetVoicePrompt();
  stopQuestControllerLoop();
  stopQuestHandLoop();
  stopQuestVrControlWatchdog();
  detachQuestXrSessionListeners();
  resetQuestXrSourceRefreshTimer();
  resetQuestXrVisualNodes();
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
  window.removeEventListener("resize", handleWindowResize);
  window.removeEventListener("gamepadconnected", handleQuestGamepadConnectionEvent);
  window.removeEventListener("gamepaddisconnected", handleQuestGamepadConnectionEvent);
  // 清理WebSocket监听器
  websocketManager.off('statusChange');
  websocketManager.off('stateUpdate');
  websocketManager.off('motionUpdate');
  websocketManager.off('sceneUpdate');
  websocketManager.off('controlResult');
  websocketManager.off('resetResult');
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

.scene-restore-panel {
  position: fixed;
  bottom: 20px;
  left: 20px;
  z-index: 10;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 15px;
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  width: 220px;
}

.scene-restore-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.scene-restore-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.scene-restore-button {
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background-color: #409eff;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease;
}

.scene-restore-button:hover:not(:disabled) {
  background-color: #66b1ff;
  transform: translateY(-1px);
}

.scene-restore-button:disabled {
  background-color: #a0cfff;
  cursor: not-allowed;
  transform: none;
}

.scene-restore-status {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
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

.dataset-status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.dataset-pill {
  border: 1px solid rgba(116, 148, 175, 0.45);
  border-radius: 999px;
  padding: 4px 7px;
  background: rgba(32, 55, 76, 0.68);
  font-size: 11px;
}

.dataset-precheck-button {
  margin-top: 8px;
  width: 100%;
}

.dataset-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 9px;
}

.dataset-form-grid.compact {
  margin-top: 8px;
}

.dataset-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.dataset-field.full-width {
  margin-top: 8px;
}

.dataset-label {
  font-size: 11px;
  color: #9bc3e2;
}

.dataset-select,
.dataset-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(116, 148, 175, 0.5);
  border-radius: 7px;
  background: rgba(13, 22, 31, 0.9);
  color: #eff6fc;
  font-size: 12px;
}

.dataset-select {
  height: 32px;
  padding: 0 7px;
}

.dataset-textarea {
  min-height: 52px;
  padding: 7px;
  resize: vertical;
}

.dataset-select:disabled,
.dataset-textarea:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.dataset-action-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
  margin-top: 9px;
}

.dataset-action-row.dataset-auto-actions {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dataset-auto-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
}

.dataset-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d7ebff;
  white-space: nowrap;
}

.dataset-auto-status {
  min-width: 0;
  color: #b4d7f1;
  text-align: right;
  word-break: break-word;
}

.dataset-button {
  border: 1px solid rgba(116, 148, 175, 0.5);
  border-radius: 8px;
  padding: 8px 6px;
  background: rgba(32, 55, 76, 0.92);
  color: #eff6fc;
  cursor: pointer;
  font-size: 12px;
}

.dataset-button.primary {
  border-color: rgba(90, 190, 130, 0.55);
  background: rgba(30, 92, 60, 0.9);
}

.dataset-button.danger {
  border-color: rgba(196, 95, 95, 0.65);
  background: rgba(88, 36, 36, 0.9);
}

.dataset-button:hover {
  background: rgba(44, 71, 95, 0.94);
}

.dataset-button.primary:hover {
  background: rgba(43, 118, 79, 0.94);
}

.dataset-button.danger:hover {
  background: rgba(112, 44, 44, 0.94);
}

.dataset-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dataset-episode-id,
.dataset-message,
.dataset-warning {
  margin-top: 8px;
  font-size: 12px;
  word-break: break-all;
}

.dataset-episode-id {
  color: #b4d7f1;
}

.dataset-message {
  color: #d7ebff;
}

.dataset-warning {
  color: #f6d07a;
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

.panel-control-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.panel-control-button:disabled:hover {
  background-color: transparent;
  color: #ccc;
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
