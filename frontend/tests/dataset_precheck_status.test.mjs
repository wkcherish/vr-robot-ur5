import assert from "node:assert/strict";

import {
  buildDatasetPrecheckUiStatus,
  shouldClearRecoveredWebSocketError,
} from "../src/utils/datasetPrecheckStatus.js";

const staleWebSocketPayload = {
  recording_ready: false,
  summary: ["websocket: no active WebSocket client"],
  checks: {
    websocket: { ok: false, message: "no active WebSocket client" },
  },
};

assert.deepEqual(
  buildDatasetPrecheckUiStatus(staleWebSocketPayload, { websocketConnected: true }),
  {
    recordingReady: false,
    summary: [],
    lastError: "",
    recordingStatus: "error",
    recordingMessage: "WebSocket 已恢复，请重新执行 precheck。",
  },
  "前端 WebSocket 已连接时，应清理后端旧的 no active WebSocket client 预检错误"
);

assert.equal(
  buildDatasetPrecheckUiStatus(
    {
      ...staleWebSocketPayload,
      summary: ["d405: camera unavailable", "websocket: no active WebSocket client"],
      checks: {
        d405: { ok: false, message: "camera unavailable" },
        websocket: { ok: false, message: "no active WebSocket client" },
      },
    },
    { websocketConnected: true }
  ).lastError,
  "d405: camera unavailable",
  "过滤已恢复的 WebSocket 旧错误时，仍应保留其它真实预检失败"
);

assert.equal(
  buildDatasetPrecheckUiStatus(staleWebSocketPayload, { websocketConnected: false }).lastError,
  "websocket: no active WebSocket client",
  "WebSocket 未连接时，应继续显示当前连接错误"
);

assert.equal(
  shouldClearRecoveredWebSocketError("websocket: no active WebSocket client", true),
  true,
  "连接恢复后，VR 与采集面板中的旧 WebSocket 错误应允许被清空"
);

assert.equal(
  shouldClearRecoveredWebSocketError("D405 观测链未就绪", true),
  false,
  "非 WebSocket 错误不应被连接恢复逻辑误清除"
);
