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

const backendProxyTarget = normalizeProxyTarget(
  process.env.VITE_BACKEND_PROXY_TARGET || process.env.VITE_BACKEND_HTTP_ORIGIN
);

function keepSingleLocalAndNetworkUrl() {
  return {
    name: 'keep-single-local-and-network-url',
    configureServer(server) {
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
    proxy: {
      '/health/': {
        target: backendProxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '/sim': {
        target: backendProxyTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      '/data/': {
        target: backendProxyTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
