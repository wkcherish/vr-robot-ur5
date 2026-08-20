import assert from "node:assert/strict";

import {
  buildQuestXrNodeSourceState,
  normalizeXrHandedness,
  resolveQuestXrNodeSourceForIndex,
} from "../src/utils/questXrHandedness.js";

const leftSource = { handedness: "left", handedLabel: "physical-left" };
const rightSource = { handedness: "right", handedLabel: "physical-right" };

assert.equal(normalizeXrHandedness(" LEFT "), "left", "左右手字符串归一化应忽略大小写和空格");
assert.equal(normalizeXrHandedness("unknown"), "", "未知 handedness 不应误归一到左右手");

assert.equal(
  resolveQuestXrNodeSourceForIndex([rightSource, leftSource], 0, { userData: {} }, ""),
  null,
  "XR 节点未收到 connected 事件前，不应按 inputSources 数组下标绑定左右手，避免 Quest 重连后左右手模型反接"
);

assert.equal(
  resolveQuestXrNodeSourceForIndex(
    [rightSource, leftSource],
    0,
    { userData: { inputSource: leftSource } },
    ""
  ),
  leftSource,
  "已有 connected 事件绑定的节点应优先使用自身 inputSource，而不是被 inputSources 顺序覆盖"
);

assert.equal(
  resolveQuestXrNodeSourceForIndex(
    [rightSource, leftSource],
    0,
    { userData: { handedness: "left" } },
    ""
  ),
  leftSource,
  "已有逻辑 handedness 的节点应按 handedness 查找输入源，保证可视模型和控制输入同手"
);

assert.equal(
  resolveQuestXrNodeSourceForIndex([rightSource, leftSource], 0, { userData: {} }, "left"),
  leftSource,
  "明确传入 fallbackKey 时才允许按逻辑 handedness 兜底绑定"
);

const connectedStateWithoutFreshSource = buildQuestXrNodeSourceState(
  { userData: { connected: true, handedness: "left", inputSource: leftSource } },
  null,
  ""
);
assert.equal(
  connectedStateWithoutFreshSource.connected,
  true,
  "已收到 connected 事件的手柄节点，即使本帧未匹配 inputSource，也不能被反复标记断开导致模型消失"
);
assert.equal(connectedStateWithoutFreshSource.inputSource, leftSource);
assert.equal(connectedStateWithoutFreshSource.shouldHide, false);

const unknownStateWithoutSource = buildQuestXrNodeSourceState({ userData: {} }, null, "");
assert.equal(
  unknownStateWithoutSource.connected,
  false,
  "未 connected 且无 handedness 的节点仍不应强行显示，避免左右手再次反接"
);
assert.equal(unknownStateWithoutSource.shouldHide, true);
