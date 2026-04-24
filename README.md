# ar-ur5-rl

## 项目简介

`ar-ur5-rl` 是一个面向 Quest3 远程示教与仿真验证的 UR5 数字孪生项目，包含：

- 前端：Vue 3 + Three.js 机械臂与场景可视化
- 后端：FastAPI + MuJoCo 仿真状态与控制接口
- VR 控制：Quest3 手柄模式与手势模式

## 技术栈

- 前端：Vite、Vue 3、Three.js、Element Plus、Axios
- 后端：FastAPI、Pydantic、MuJoCo

## 目录结构

```text
ar-ur5-rl/
├─ frontend/              # 前端工程（Vite + Vue）
├─ backend/               # 后端工程（FastAPI + MuJoCo）
├─ shared/                # 场景与数据协议共享配置
└─ docs/                  # 任务与实现文档
```

## 环境要求

- Node.js 18+
- Python 3.10+
- npm / pnpm / yarn 任一包管理器

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认访问：`http://localhost:5173`

Quest3 建议使用 HTTPS 访问（示例：`https://<LAN_IP>:5173`）。  
可通过环境变量启用 HTTPS 证书：

```bash
VITE_HTTPS_CERT=<path/to/cert.pem> VITE_HTTPS_KEY=<path/to/key.pem> npm run dev
```

## 后端启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.api_app:app --reload --host 0.0.0.0 --port 8000
```

Windows 可使用：

```bash
.venv\Scripts\activate
```

更多后端启动方式见：

- [backend/README.md](backend/README.md)

## VR 控制与性能修复记录（2026-04-24）

本次针对“进入 VR 后选模式无法稳定控制机械臂”和“高负载卡顿”问题，已完成具体参数级修复。  
详细见：

- [docs/vr_control_and_performance_update_2026-04-24.md](docs/vr_control_and_performance_update_2026-04-24.md)
