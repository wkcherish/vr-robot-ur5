export function normalizeXrHandedness(value) {
  const handedness = String(value || "").trim().toLowerCase();
  if (handedness === "left" || handedness === "right") return handedness;
  return "";
}

export function resolveQuestXrNodeKey(node, fallbackKey = "") {
  return normalizeXrHandedness(node?.userData?.handedness) || normalizeXrHandedness(fallbackKey);
}

function findSourceByHandedness(sources, handedness) {
  const hand = normalizeXrHandedness(handedness);
  if (!hand || !Array.isArray(sources)) return null;
  return sources.find((source) => normalizeXrHandedness(source?.handedness) === hand) || null;
}

export function resolveQuestXrNodeSourceForIndex(sources, index, node, fallbackKey = "") {
  const normalizedSources = Array.isArray(sources) ? sources : [];

  const existingSource = node?.userData?.inputSource || null;
  const existingHandedness = normalizeXrHandedness(existingSource?.handedness);
  if (existingHandedness) {
    return findSourceByHandedness(normalizedSources, existingHandedness) || existingSource;
  }

  const nodeHandedness = normalizeXrHandedness(node?.userData?.handedness);
  if (nodeHandedness) {
    return findSourceByHandedness(normalizedSources, nodeHandedness);
  }

  const fallbackHandedness = normalizeXrHandedness(fallbackKey);
  if (fallbackHandedness) {
    return findSourceByHandedness(normalizedSources, fallbackHandedness);
  }

  // Quest 的 inputSources 顺序在重连/切换模式后不稳定，不能用数组下标推断左右手。
  // 等待 Three.js connected 事件提供节点自己的 inputSource，宁可短暂隐藏也不显示反手柄。
  void index;
  return null;
}

export function buildQuestXrNodeSourceState(node, source, fallbackKey = "") {
  const handedness = normalizeXrHandedness(source?.handedness) || resolveQuestXrNodeKey(node, fallbackKey);
  const existingSource = node?.userData?.inputSource || null;
  const wasConnected = node?.userData?.connected === true;
  const nextSource = source || existingSource || null;
  return {
    handedness,
    inputSource: nextSource,
    connected: Boolean(source) || (wasConnected && Boolean(handedness)),
    shouldHide: !source && !wasConnected && !handedness,
  };
}
