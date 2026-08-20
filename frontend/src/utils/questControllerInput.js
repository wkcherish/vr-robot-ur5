import { getQuestXRSession } from "./questXRSession.js";

const QUEST_PAD_PATTERN = /(quest|oculus|meta|touch|xr-standard)/i;
const LEFT_PAD_PATTERN = /(left|l-touch|left controller)/i;
const RIGHT_PAD_PATTERN = /(right|r-touch|right controller)/i;
const THUMBSTICK_BUTTON_INDEX = [2];

const LEFT_BUTTON_INDEX = {
  precision: THUMBSTICK_BUTTON_INDEX,
  select_wrist: [3],
  select_upper_arm: [4],
  select_forearm: [5],
  // Quest 左手柄 X/Y 在沉浸式采集里作为快捷键：X=结束/复原，Y=开始采集。
  dataset_reset: [4],
  dataset_start: [5],
  grip: [1],
  trigger: [0],
};

const RIGHT_BUTTON_INDEX = {
  trigger: [0],
  grip: [1],
  precision: THUMBSTICK_BUTTON_INDEX,
  next_episode: [4, 5],
};

function asConnectedPads() {
  if (typeof navigator === "undefined" || typeof navigator.getGamepads !== "function") {
    return [];
  }
  return Array.from(navigator.getGamepads() || []).filter((pad) => pad && pad.connected);
}

function scoreQuestPad(pad) {
  const id = String(pad?.id || "");
  let score = 0;
  if (QUEST_PAD_PATTERN.test(id)) score += 10;
  const hand = String(pad?.hand || "").toLowerCase();
  if (hand === "left" || hand === "right") score += 8;
  if (String(pad?.mapping || "") === "xr-standard") score += 5;
  if (Array.isArray(pad?.axes) && pad.axes.length >= 2) score += 3;
  if (Array.isArray(pad?.buttons) && pad.buttons.length >= 2) score += 2;
  return score;
}

function pickByPattern(pads, pattern) {
  const matched = pads.filter((pad) => pattern.test(String(pad?.id || "")));
  if (matched.length > 0) return matched[0];
  return null;
}

function pickLeftRightPads() {
  const all = asConnectedPads();
  if (all.length === 0) {
    return { leftPad: null, rightPad: null, source: "none" };
  }

  const leftByHand = all.find((pad) => String(pad?.hand || "").toLowerCase() === "left") || null;
  const rightByHand = all.find((pad) => String(pad?.hand || "").toLowerCase() === "right") || null;
  if (leftByHand && rightByHand && leftByHand !== rightByHand) {
    return { leftPad: leftByHand, rightPad: rightByHand, source: "navigator_gamepads" };
  }

  const ranked = [...all].sort((a, b) => scoreQuestPad(b) - scoreQuestPad(a));
  const questCandidates = ranked.slice(0, 2);
  const pool = questCandidates.length >= 2 ? questCandidates : ranked;

  const leftByPattern = pickByPattern(pool, LEFT_PAD_PATTERN);
  const rightByPattern = pickByPattern(pool, RIGHT_PAD_PATTERN);

  let leftPad = leftByPattern;
  let rightPad = rightByPattern;

  if (!leftPad && !rightPad) {
    leftPad = pool[0] || null;
    rightPad = pool[1] || null;
  } else if (!leftPad) {
    leftPad = pool.find((pad) => pad !== rightPad) || null;
  } else if (!rightPad) {
    rightPad = pool.find((pad) => pad !== leftPad) || null;
  }

  return { leftPad, rightPad, source: "navigator_gamepads" };
}

function clamp01(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(numeric, 0), 1);
}

function clampAxis(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(numeric, -1), 1);
}

function readNumericArray(values) {
  if (!values || typeof values.length !== "number") return [];
  return Array.from(values).map((value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : 0;
  });
}

function summarizeButtons(buttons) {
  if (!buttons || typeof buttons.length !== "number") {
    return { values: [], pressed: [], touched: [] };
  }
  const values = [];
  const pressed = [];
  const touched = [];
  Array.from(buttons).forEach((button) => {
    values.push(clamp01(button?.value));
    pressed.push(Boolean(button?.pressed));
    touched.push(Boolean(button?.touched));
  });
  return { values, pressed, touched };
}

function readButtonValue(pad, candidates) {
  if (!pad || !pad.buttons || typeof pad.buttons.length !== "number") return 0;
  const indices = Array.isArray(candidates) ? candidates : [candidates];
  let maxValue = 0;
  indices.forEach((index) => {
    const button = pad.buttons[index];
    if (!button) return;
    const value = Math.max(clamp01(button.value), button.pressed ? 1 : 0);
    if (value > maxValue) maxValue = value;
  });
  return maxValue;
}

function readButtonPressedValue(pad, candidates) {
  if (!pad || !pad.buttons || typeof pad.buttons.length !== "number") return 0;
  const indices = Array.isArray(candidates) ? candidates : [candidates];
  return indices.some((index) => Boolean(pad.buttons[index]?.pressed)) ? 1 : 0;
}

function readAxisPair(pad, startIndex) {
  const axes = pad?.axes;
  const xRaw = Number(axes?.[startIndex]);
  const yRaw = Number(axes?.[startIndex + 1]);
  const hasX = Number.isFinite(xRaw);
  const hasY = Number.isFinite(yRaw);
  const x = hasX ? clampAxis(xRaw) : 0;
  const y = hasY ? clampAxis(yRaw) : 0;
  return {
    x,
    y,
    pair: `${startIndex}/${startIndex + 1}`,
    present: hasX || hasY,
    magnitude: Math.abs(x) + Math.abs(y),
  };
}

function readStickMagnitude(stick) {
  return Math.abs(Number(stick?.x) || 0) + Math.abs(Number(stick?.y) || 0);
}

function readStickAxes(pad) {
  if (!pad || !pad.axes || typeof pad.axes.length !== "number") {
    return { x: 0, y: 0, pair: "" };
  }

  const candidates = [readAxisPair(pad, 2), readAxisPair(pad, 0)].filter((item) => item.present);
  if (candidates.length === 0) {
    return { x: 0, y: 0, pair: "" };
  }
  candidates.sort((a, b) => b.magnitude - a.magnitude);
  const selected = candidates[0];

  return {
    x: selected.x,
    y: selected.y,
    pair: selected.pair,
  };
}

function readButtonValueFromPads(pads, candidates) {
  return pads.reduce((maxValue, pad) => Math.max(maxValue, readButtonValue(pad, candidates)), 0);
}

function normalizeHandedness(value) {
  const handed = String(value || "").toLowerCase();
  if (handed === "left" || handed === "right") return handed;
  return "";
}

function buildControllerRaw(handedness, pad, buttonIndexMap) {
  const stick = readStickAxes(pad);
  const buttons = summarizeButtons(pad?.buttons);
  const logicalHandedness = normalizeHandedness(handedness);
  const reportedHandedness = normalizeHandedness(pad?.hand);
  return {
    id: String(pad?.id || ""),
    mapping: String(pad?.mapping || ""),
    // handedness 表示系统内部的逻辑左右手，reported_handedness 保留浏览器原始上报值用于排查。
    handedness: logicalHandedness || reportedHandedness,
    reported_handedness: reportedHandedness,
    axes: readNumericArray(pad?.axes),
    axis_pair: stick.pair,
    button_values: buttons.values,
    button_pressed: buttons.pressed,
    button_touched: buttons.touched,
    stick_x: stick.x,
    stick_y: stick.y,
    trigger: readButtonValue(pad, buttonIndexMap.trigger || []),
    grip: readButtonValue(pad, buttonIndexMap.grip || []),
    precision: readButtonValue(pad, buttonIndexMap.precision || []),
  };
}

function pickActiveController(raw) {
  const leftGrip = Number(raw?.left?.grip) || 0;
  const rightGrip = Number(raw?.right?.grip) || 0;
  const leftTrigger = Number(raw?.left?.trigger) || 0;
  const rightTrigger = Number(raw?.right?.trigger) || 0;
  const leftStickMagnitude = readStickMagnitude(raw?.left);
  const rightStickMagnitude = readStickMagnitude(raw?.right);

  if (rightGrip > 0 || leftGrip > 0) {
    return rightGrip >= leftGrip ? "right" : "left";
  }
  if (rightTrigger > 0 || leftTrigger > 0) {
    return rightTrigger >= leftTrigger ? "right" : "left";
  }
  if (rightStickMagnitude > 0 || leftStickMagnitude > 0) {
    return rightStickMagnitude >= leftStickMagnitude ? "right" : "left";
  }
  if (raw?.right?.id) return "right";
  return raw?.left?.id ? "left" : "";
}

function pickLeftRightPadsFromXRSession() {
  const session = getQuestXRSession();
  if (!session) {
    return { leftPad: null, rightPad: null, source: "none" };
  }
  const sources = Array.from(session.inputSources || []);
  if (sources.length === 0) {
    return { leftPad: null, rightPad: null, source: "none" };
  }

  const gamepadEntries = [];
  sources.forEach((source, index) => {
    if (!source || !source.gamepad) return;
    gamepadEntries.push({
      source,
      gamepad: source.gamepad,
      handedness: normalizeHandedness(source.handedness),
      index,
    });
  });

  if (gamepadEntries.length === 0) {
    return { leftPad: null, rightPad: null, source: "none" };
  }

  let leftPad = null;
  let rightPad = null;

  for (const entry of gamepadEntries) {
    if (entry.handedness === "left" && !leftPad) {
      leftPad = entry.gamepad;
    }
    if (entry.handedness === "right" && !rightPad) {
      rightPad = entry.gamepad;
    }
  }

  if (!leftPad || !rightPad) {
    const sorted = [...gamepadEntries].sort((a, b) => {
      const scoreA = scoreQuestPad(a.gamepad);
      const scoreB = scoreQuestPad(b.gamepad);
      if (scoreA !== scoreB) return scoreB - scoreA;
      return a.index - b.index;
    });

    if (!leftPad) {
      leftPad = sorted[0]?.gamepad || null;
    }
    if (!rightPad) {
      rightPad = sorted.find((entry) => entry.gamepad !== leftPad)?.gamepad || null;
    }
  }

  return {
    leftPad,
    rightPad,
    source: "xr_input_sources",
  };
}

function readSnapshotFromPads(leftPad, rightPad, source) {
  if (!leftPad && !rightPad) {
    return {
      available: true,
      has_device: false,
      reason: "idle",
      timestamp_ms: Date.now(),
      controls: {
        select_upper_arm: 0,
        select_forearm: 0,
        select_wrist: 0,
        precision: 0,
        stick_x: 0,
        stick_y: 0,
        left_stick_x: 0,
        left_stick_y: 0,
        right_stick_x: 0,
        right_stick_y: 0,
        trigger: 0,
        grip: 0,
        left_trigger: 0,
        left_grip: 0,
        right_trigger: 0,
        right_grip: 0,
        dataset_start: 0,
        dataset_reset: 0,
        next_episode: 0,
        active_hand: "",
      },
      raw: null,
    };
  }

  const pads = [leftPad, rightPad].filter(Boolean);
  const selectPad = leftPad || rightPad || null;
  const leftButtons = summarizeButtons(selectPad?.buttons);
  const selectUpperArm = readButtonValue(selectPad, LEFT_BUTTON_INDEX.select_upper_arm);
  const selectForearm = readButtonValue(selectPad, LEFT_BUTTON_INDEX.select_forearm);
  const selectWrist = readButtonValue(selectPad, LEFT_BUTTON_INDEX.select_wrist);
  const datasetReset = readButtonValue(leftPad, LEFT_BUTTON_INDEX.dataset_reset);
  const datasetStart = readButtonValue(leftPad, LEFT_BUTTON_INDEX.dataset_start);
  const leftPrecision = readButtonPressedValue(leftPad, LEFT_BUTTON_INDEX.precision);
  const rightPrecision = readButtonPressedValue(rightPad, RIGHT_BUTTON_INDEX.precision);
  const precision = Math.max(leftPrecision, rightPrecision);
  const nextEpisode = readButtonValue(rightPad, RIGHT_BUTTON_INDEX.next_episode);
  const raw = {
    source,
    roles: {
      select: leftPad ? "left" : rightPad ? "right" : "",
      control: "",
    },
    left: {
      ...buildControllerRaw("left", leftPad, {
        trigger: LEFT_BUTTON_INDEX.trigger,
        grip: LEFT_BUTTON_INDEX.grip,
      }),
      select_id: String(selectPad?.id || ""),
      select_mapping: String(selectPad?.mapping || ""),
      select_handedness: String(selectPad?.hand || ""),
      select_button_values: leftButtons.values,
      select_button_pressed: leftButtons.pressed,
      select_button_touched: leftButtons.touched,
      select_upper_arm: selectUpperArm,
      select_forearm: selectForearm,
      select_wrist: selectWrist,
      dataset_start: datasetStart,
      dataset_reset: datasetReset,
      precision: leftPrecision,
    },
    right: {
      ...buildControllerRaw("right", rightPad, RIGHT_BUTTON_INDEX),
      next_episode: nextEpisode,
    },
  };
  const activeHand = pickActiveController(raw);
  raw.roles.control = activeHand;
  raw.active_hand = activeHand;
  const activeRaw = activeHand === "left" ? raw.left : raw.right;

  return {
    available: true,
    has_device: true,
    reason: "ok",
    timestamp_ms: Date.now(),
    controls: {
      select_upper_arm: raw.left.select_upper_arm,
      select_forearm: raw.left.select_forearm,
      select_wrist: raw.left.select_wrist,
      precision,
      stick_x: activeRaw?.stick_x || 0,
      stick_y: activeRaw?.stick_y || 0,
      left_stick_x: raw.left.stick_x || 0,
      left_stick_y: raw.left.stick_y || 0,
      right_stick_x: raw.right.stick_x || 0,
      right_stick_y: raw.right.stick_y || 0,
      trigger: activeRaw?.trigger || 0,
      grip: activeRaw?.grip || 0,
      left_trigger: raw.left.trigger,
      left_grip: raw.left.grip,
      right_trigger: raw.right.trigger,
      right_grip: raw.right.grip,
      dataset_start: raw.left.dataset_start,
      dataset_reset: raw.left.dataset_reset,
      next_episode: raw.right.next_episode,
      active_hand: activeHand,
    },
    raw,
  };
}

export function readQuestControllerSnapshotFromPads(leftPad, rightPad, source = "manual") {
  return readSnapshotFromPads(leftPad, rightPad, source);
}

export function readQuestControllerSnapshot() {
  const xrPads = pickLeftRightPadsFromXRSession();
  if (xrPads.leftPad || xrPads.rightPad) {
    return readQuestControllerSnapshotFromPads(xrPads.leftPad, xrPads.rightPad, xrPads.source);
  }

  const navigatorPads = pickLeftRightPads();
  return readQuestControllerSnapshotFromPads(navigatorPads.leftPad, navigatorPads.rightPad, navigatorPads.source);
}
