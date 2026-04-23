# 机械臂仿真项目

## 项目简介
这是一个基于 Vue 3 和 Three.js 的机械臂仿真项目，用于在网页中可视化展示机械臂模型，并进行关节角度控制与交互演示。

## 技术栈
- Vite
- Vue 3
- Three.js
- Element Plus
- Axios

## 目录结构
```text
vue-robot/
├─ frontend/              # 前端工程（Vite + Vue）
│  ├─ src/
│  ├─ public/
│  ├─ package.json
│  └─ vite.config.js
└─ backend/               # 预留目录（当前为空）
```

## 环境要求
- Node.js 18 及以上（建议）
- npm / pnpm / yarn 任一包管理器

## 安装依赖
在前端目录执行：

```bash
cd frontend
npm install
# 或 pnpm install
# 或 yarn install
```

## 启动开发环境
在前端目录执行：

```bash
cd frontend
npm run dev
# 或 pnpm run dev
# 或 yarn dev
```

启动后访问：
- 前端：`http://localhost:5173`

Quest3 建议使用 HTTPS 访问（例如 `https://<LAN_IP>:5173`），并确保后端也是 HTTPS/WSS。
可通过环境变量启用前端 HTTPS 证书：

```bash
VITE_HTTPS_CERT=<path/to/cert.pem> VITE_HTTPS_KEY=<path/to/key.pem> npm run dev
```

## 生产构建
```bash
cd frontend
npm run build
npm run preview
```

## 备注
- `backend/` 目录已保留，但当前没有后端代码。
- 如需接入后端服务，可按你的技术栈（如 FastAPI）在 `backend/` 中自行扩展。
