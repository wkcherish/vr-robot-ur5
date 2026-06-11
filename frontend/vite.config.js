/*
 * @Author: wangzhiyu <w19165802736@163.com>
 * @version: 1.0.0
 * @Date: 2023-11-08 15:00:27
 * @LastEditTime: 2024-01-22 16:57:50
 * @Descripttion: vite配置
 */
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import basicSsl from '@vitejs/plugin-basic-ssl';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..');
const BACKEND_RUNTIME_PATH = path.join(REPO_ROOT, 'shared', 'runtime', 'backend-dev.json');

function resolveIfExists(rawPath) {
  if (!rawPath || String(rawPath).trim().length === 0) return null;
  const resolved = path.resolve(process.cwd(), String(rawPath).trim());
  if (!fs.existsSync(resolved)) return null;
  return resolved;
}

function buildHttpsConfig() {
  // Only use explicit frontend cert envs to avoid accidentally picking unrelated
  // system SSL env vars that can break TLS handshake.
  const certPath = resolveIfExists(process.env.VITE_HTTPS_CERT);
  const keyPath = resolveIfExists(process.env.VITE_HTTPS_KEY);
  if (!certPath || !keyPath) return undefined;
  return {
    cert: fs.readFileSync(certPath),
    key: fs.readFileSync(keyPath),
  };
}

function buildHttpsServerOption() {
  const explicitConfig = buildHttpsConfig();
  if (explicitConfig) return explicitConfig;

  // Keep HTTPS enabled for both local and network URLs even when user certs are absent.
  return true;
}

const httpsServerOption = buildHttpsServerOption();

function normalizeProxyTarget(rawValue) {
  const value = String(rawValue || '').trim();
  if (!value) return 'http://127.0.0.1:8000';
  if (/^https?:\/\//i.test(value)) return value.replace(/\/$/, '');
  return 'http://' + value.replace(/\/$/, '');
}

function readBackendRuntimeConfig() {
  if (!fs.existsSync(BACKEND_RUNTIME_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(BACKEND_RUNTIME_PATH, 'utf-8'));
  } catch (error) {
    console.warn('[vite] failed to read backend runtime config:', error);
  }
  return null;
}

function resolveBackendProxyTarget() {
  if (process.env.VITE_BACKEND_PROXY_TARGET) {
    return {
      target: normalizeProxyTarget(process.env.VITE_BACKEND_PROXY_TARGET),
      source: 'env:VITE_BACKEND_PROXY_TARGET',
    };
  }

  if (process.env.VITE_BACKEND_HTTP_ORIGIN) {
    return {
      target: normalizeProxyTarget(process.env.VITE_BACKEND_HTTP_ORIGIN),
      source: 'env:VITE_BACKEND_HTTP_ORIGIN',
    };
  }

  const runtimeConfig = readBackendRuntimeConfig();
  if (runtimeConfig && typeof runtimeConfig.proxy_target === 'string' && runtimeConfig.proxy_target.trim()) {
    return {
      target: normalizeProxyTarget(runtimeConfig.proxy_target),
      source: `runtime:${path.relative(FRONTEND_ROOT, BACKEND_RUNTIME_PATH)}`,
    };
  }

  return {
    target: 'http://127.0.0.1:8000',
    source: 'default:127.0.0.1:8000',
  };
}

function scrubProxyAuthChallenge(proxy) {
  proxy.on('proxyRes', (proxyRes, req) => {
    const authHeader = proxyRes?.headers?.['www-authenticate'];
    if (!authHeader) return;
    delete proxyRes.headers['www-authenticate'];
    console.warn(`[vite] stripped proxied auth challenge for ${req.method || 'GET'} ${req.url || ''}`);
  });
}

function createBackendProxyOptions(enableWs = false) {
  const initialTarget = resolveBackendProxyTarget();
  return {
    target: initialTarget.target,
    changeOrigin: true,
    secure: false,
    ...(enableWs ? { ws: true } : {}),
    router: () => resolveBackendProxyTarget().target,
    configure: scrubProxyAuthChallenge,
  };
}

function keepSingleLocalAndNetworkUrl() {
  return {
    name: 'keep-single-local-and-network-url',
    configureServer(server) {
      const backendProxyTarget = resolveBackendProxyTarget();
      console.log(
        `[vite] backend proxy target -> ${backendProxyTarget.target} (${backendProxyTarget.source})`
      );
      if (typeof server.printUrls !== 'function') return;
      const originalPrintUrls = server.printUrls.bind(server);
      server.printUrls = () => {
        const originalResolvedUrls = server.resolvedUrls;
        if (!originalResolvedUrls) {
          originalPrintUrls();
          return;
        }
        let nextResolvedUrls = originalResolvedUrls;
        if (originalResolvedUrls.local?.length > 1) {
          nextResolvedUrls = {
            ...nextResolvedUrls,
            local: [nextResolvedUrls.local[0]],
          };
        }
        if (originalResolvedUrls.network?.length > 1) {
          nextResolvedUrls = {
            ...nextResolvedUrls,
            network: [nextResolvedUrls.network[0]],
          };
        }
        if (nextResolvedUrls !== originalResolvedUrls) {
          server.resolvedUrls = nextResolvedUrls;
        }
        try {
          originalPrintUrls();
        } finally {
          server.resolvedUrls = originalResolvedUrls;
        }
      };
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), basicSsl(), keepSingleLocalAndNetworkUrl()],
  base: './',
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_PAGE_PORT || 5173),
    // Fail fast when 5173 is occupied so user does not accidentally open
    // another non-TLS service and hit ERR_SSL_VERSION_OR_CIPHER_MISMATCH.
    strictPort: true,
    https: httpsServerOption,
    fs: {
      allow: [REPO_ROOT],
    },
    proxy: {
      '/health/': createBackendProxyOptions(),
      '/sim': createBackendProxyOptions(true),
      '/data/': createBackendProxyOptions(),
      '/dataset': createBackendProxyOptions(),
    },
  },
});
