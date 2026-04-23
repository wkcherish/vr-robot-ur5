function normalizeOrigin(origin) {
  if (typeof origin !== "string" || origin.trim().length === 0) {
    return "";
  }

  const value = origin.trim();
  if (/^https?:\/\//i.test(value)) {
    return value.replace(/\/$/, "");
  }
  return "http://" + value.replace(/\/$/, "");
}

function normalizeWsUrl(url) {
  if (typeof url !== "string" || url.trim().length === 0) {
    return "";
  }

  const value = url.trim();
  if (/^wss?:\/\//i.test(value)) {
    return value.replace(/\/$/, "");
  }

  if (/^https?:\/\//i.test(value)) {
    return value.replace(/^http/i, "ws").replace(/\/$/, "");
  }

  return "ws://" + value.replace(/\/$/, "");
}

function inferBackendOrigin() {
  if (import.meta.env.VITE_BACKEND_HTTP_ORIGIN) {
    return normalizeOrigin(import.meta.env.VITE_BACKEND_HTTP_ORIGIN);
  }

  if (typeof window === "undefined" || !window.location) {
    return "http://localhost:8000";
  }

  // Default to same-origin relative path so Vite dev server proxy can bridge
  // HTTPS frontend to HTTP backend without browser mixed-content/CORS issues.
  return "";
}

function inferBackendWsUrl(origin) {
  if (import.meta.env.VITE_BACKEND_WS_URL) {
    return normalizeWsUrl(import.meta.env.VITE_BACKEND_WS_URL);
  }

  const asUrl = new URL(origin);
  const wsProtocol = asUrl.protocol === "https:" ? "wss:" : "ws:";
  return wsProtocol + "//" + asUrl.host;
}

const backendOrigin = inferBackendOrigin();
const backendWsBase = backendOrigin
  ? inferBackendWsUrl(backendOrigin)
  : (typeof window !== "undefined" && window.location
      ? window.location.origin.replace(/^http/i, "ws")
      : "");

export const runtimeConfig = {
  backendOrigin: backendOrigin || (typeof window !== "undefined" ? window.location.origin : ""),
  backendWsBase,
  healthUrl: (backendOrigin || "") + "/health/",
  simStateUrl: (backendOrigin || "") + "/sim/state/",
  legacyDataUrl: (backendOrigin || "") + "/data/",
  simStepUrl: (backendOrigin || "") + "/sim/step/",
  simWsUrl: backendWsBase ? (backendWsBase + "/sim/ws") : "/sim/ws",
};

export function makePageAccessUrl(hostIp) {
  const ip = String(hostIp || "").trim();
  if (!ip) return "";
  const pagePort = Number(import.meta.env.VITE_PAGE_PORT || 5173);
  const pageProtocol =
    typeof window !== "undefined" && window.location && window.location.protocol === "https:"
      ? "https://"
      : "http://";
  return pageProtocol + ip + ":" + pagePort;
}

export function getDeviceCategory() {
  if (typeof navigator === "undefined") return "desktop";

  const ua = String(navigator.userAgent || "").toLowerCase();
  const isQuest = ua.includes("oculusbrowser") || ua.includes("quest");
  if (isQuest) return "quest3";
  return "desktop";
}
