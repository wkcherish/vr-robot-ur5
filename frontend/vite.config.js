/*
 * @Author: wangzhiyu <w19165802736@163.com>
 * @version: 1.0.0
 * @Date: 2023-11-08 15:00:27
 * @LastEditTime: 2024-01-22 16:57:50
 * @Descripttion: vite配置
 */
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import fs from 'node:fs';
import path from 'node:path';

function resolveIfExists(rawPath) {
  if (!rawPath || String(rawPath).trim().length === 0) return null;
  const resolved = path.resolve(process.cwd(), String(rawPath).trim());
  if (!fs.existsSync(resolved)) return null;
  return resolved;
}

function buildHttpsConfig() {
  const certPath = resolveIfExists(process.env.VITE_HTTPS_CERT || process.env.SSL_CERTFILE);
  const keyPath = resolveIfExists(process.env.VITE_HTTPS_KEY || process.env.SSL_KEYFILE);
  if (!certPath || !keyPath) return undefined;
  return {
    cert: fs.readFileSync(certPath),
    key: fs.readFileSync(keyPath),
  };
}

const httpsConfig = buildHttpsConfig();

function keepSingleNetworkUrl() {
  return {
    name: 'keep-single-network-url',
    configureServer(server) {
      if (typeof server.printUrls !== 'function') return;
      const originalPrintUrls = server.printUrls.bind(server);
      server.printUrls = () => {
        const originalResolvedUrls = server.resolvedUrls;
        if (originalResolvedUrls?.network?.length > 1) {
          server.resolvedUrls = {
            ...originalResolvedUrls,
            network: [originalResolvedUrls.network[0]],
          };
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
  plugins: [vue(), keepSingleNetworkUrl()],
  base: './',
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_PAGE_PORT || 5173),
    strictPort: false,
    https: httpsConfig || true,
  },
});
