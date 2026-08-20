import assert from "node:assert/strict";

import viteConfig from "../vite.config.js";

const config = typeof viteConfig === "function" ? viteConfig({ command: "serve", mode: "development" }) : viteConfig;
const proxy = config?.server?.proxy || {};

assert.equal(
  proxy["/sim/ws"]?.ws,
  true,
  "只有 /sim/ws 应启用 WebSocket 代理，避免普通 /sim HTTP 请求被 WS 代理链路干扰"
);

assert.equal(
  Boolean(proxy["/sim"]?.ws),
  false,
  "/sim 普通 HTTP API 不应启用 ws:true，避免 reset 等 HTTP 请求触发 Vite ws proxy socket error"
);
