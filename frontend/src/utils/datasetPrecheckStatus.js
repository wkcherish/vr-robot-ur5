const WEBSOCKET_INACTIVE_PATTERN = /websocket:.*no active websocket client/i;

function normalizeSummary(summary) {
  if (!Array.isArray(summary)) return [];
  return summary.map((item) => String(item || "").trim()).filter(Boolean);
}

function isRecoveredBackendWebSocketError(message, websocketConnected) {
  return Boolean(websocketConnected) && WEBSOCKET_INACTIVE_PATTERN.test(String(message || ""));
}

export function shouldClearRecoveredWebSocketError(message, websocketConnected) {
  return isRecoveredBackendWebSocketError(message, websocketConnected);
}

export function buildDatasetPrecheckUiStatus(payload, options = {}) {
  const websocketConnected = Boolean(options.websocketConnected);
  const recordingReady = Boolean(payload?.recording_ready);
  const rawSummary = normalizeSummary(payload?.summary);
  // 后端 precheck 可能早于前端 WebSocket 重连返回；此时只清理这个已恢复的旧连接错误，保留其它真实失败项。
  const summary = rawSummary.filter(
    (item) => !isRecoveredBackendWebSocketError(item, websocketConnected)
  );
  const recoveredWebSocketOnly = !recordingReady && rawSummary.length > 0 && summary.length === 0;
  const lastError = recordingReady ? "" : (summary[0] || "");

  if (recordingReady) {
    return {
      recordingReady,
      summary,
      lastError,
      recordingStatus: "ok",
      recordingMessage: "precheck 已通过",
    };
  }

  return {
    recordingReady,
    summary,
    lastError,
    recordingStatus: "error",
    recordingMessage: recoveredWebSocketOnly
      ? "WebSocket 已恢复，请重新执行 precheck。"
      : (lastError || "precheck 未通过"),
  };
}
