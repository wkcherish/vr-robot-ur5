const QUEST_PAD_PATTERN = /(quest|oculus|meta|touch|xr-standard)/i;
const LEFT_PAD_PATTERN = /(left|l-touch|left controller)/i;
const RIGHT_PAD_PATTERN = /(right|r-touch|right controller)/i;

const LEFT_BUTTON_INDEX = {
  select_upper_arm: [3],
  select_forearm: [4],
  select_wrist: [1, 2],
};

const RIGHT_BUTTON_INDEX = {
  trigger: [0],
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
  if (String(pad?.mapping || "") === "xr-standard") score += 5;
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
    return { leftPad: null, rightPad: null };
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

  return { leftPad, rightPad };
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

function readButtonValue(pad, candidates) {
  if (!pad || !Array.isArray(pad.buttons)) return 0;
  const indices = Array.isArray(candidates) ? candidates : [candidates];
  let maxValue = 0;
  indices.forEach((index) => {
    const button = pad.buttons[index];
    if (!button) return;
    const value = clamp01(button.value);
    if (value > maxValue) maxValue = value;
  });
  return maxValue;
}

function readStickAxes(pad) {
  if (!pad || !Array.isArray(pad.axes)) {
    return { x: 0, y: 0 };
  }

  const xRaw = Number.isFinite(Number(pad.axes[2])) ? pad.axes[2] : pad.axes[0];
  const yRaw = Number.isFinite(Number(pad.axes[3])) ? pad.axes[3] : pad.axes[1];

  return {
    x: clampAxis(xRaw),
    y: clampAxis(yRaw),
  };
}

export function readQuestControllerSnapshot() {
  const { leftPad, rightPad } = pickLeftRightPads();
  if (!leftPad || !rightPad) {
    return {
      available: false,
      reason: "missing_controller",
      timestamp_ms: Date.now(),
    };
  }

  const rightStick = readStickAxes(rightPad);
  const raw = {
    left: {
      id: String(leftPad.id || ""),
      select_upper_arm: readButtonValue(leftPad, LEFT_BUTTON_INDEX.select_upper_arm),
      select_forearm: readButtonValue(leftPad, LEFT_BUTTON_INDEX.select_forearm),
      select_wrist: readButtonValue(leftPad, LEFT_BUTTON_INDEX.select_wrist),
    },
    right: {
      id: String(rightPad.id || ""),
      stick_x: rightStick.x,
      stick_y: rightStick.y,
      trigger: readButtonValue(rightPad, RIGHT_BUTTON_INDEX.trigger),
    },
  };

  return {
    available: true,
    reason: "ok",
    timestamp_ms: Date.now(),
    controls: {
      select_upper_arm: raw.left.select_upper_arm,
      select_forearm: raw.left.select_forearm,
      select_wrist: raw.left.select_wrist,
      stick_x: raw.right.stick_x,
      stick_y: raw.right.stick_y,
      trigger: raw.right.trigger,
    },
    raw,
  };
}
