# jlu-notice-monitor

吉林大学通知与竞赛信息自动监控系统，包含 FastAPI 本机后端、SQLite 数据库、响应式中文 React 前端和 Tauri 2 Windows 桌面壳层。当前完成 Phase 3A Shell 集成，Python 后端仍由开发者手工启动。

## Phase 3A — Tauri Shell

```text
Tauri Window
    ↓
React Frontend
    ↓ localhost HTTP
FastAPI Backend
    ↓
SQLite
```

本阶段只集成原生窗口，不包含 Python 打包、sidecar 自动启动或安装器。自动管理 Backend 的生命周期将在 Phase 3C 开始。

桌面开发需要先分别启动 Backend 和 Tauri：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app serve
```

```powershell
Set-Location frontend
npm install
npm run tauri dev
```

Tauri 会自动启动 Vite，但不会启动 Python Backend。React 继续通过 `VITE_API_BASE_URL` 访问默认的 `http://127.0.0.1:8000`。当前临时应用图标由 Tauri 初始化生成，正式图标留到 Phase 3D。

## 本地开发

后端：

```powershell
Set-Location backend
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m app serve
```

Web 前端（另一个 PowerShell 窗口）：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

默认访问 `http://127.0.0.1:5173`，后端默认监听 `http://127.0.0.1:8000`。

## 分页与筛选 API

`GET /api/notices` 在数据库层完成筛选、排序与分页，支持：

- `page`、`page_size`
- `favorite`、`read`
- `category`、`source`
- `deadline_status`
- `q`
- 兼容参数：`keyword`、`status`、`min_score`、`date_from`、`date_to`
- `sort=newest|priority|deadline`

响应包含 `items`、`page`、`page_size`、`total` 和 `total_pages`。前端通知列表、收藏和分类 Feed 均使用服务端分页，不再读取最多 100 条后本地筛选。

## Runtime Data Directory

开发环境默认保持原有目录，便于继续调试：

```text
backend/
├── data/notices.db
├── logs/
├── data/browser_profile/oa/
├── cache/
└── data/runtime-config/
```

生产环境设置 `JLU_ENVIRONMENT=production` 后，运行时可写数据使用：

```text
%LOCALAPPDATA%\JLU Notice Monitor\
├── data\notices.db
├── logs\
├── oa-profile\
├── cache\
└── config\
```

测试或特殊部署可通过 `JLU_APP_DATA_DIR` 覆盖根目录。程序不会自动迁移或删除现有数据库。

## Health Check

`GET /api/health` 会轻量验证数据库连接，并返回版本、数据库、Crawler 与运行环境状态。它不会启动爬虫，也不会暴露本地路径、Cookie、Token 或 OA 登录信息。

未来 Tauri 应采用以下启动顺序：

1. 启动 Python FastAPI sidecar；
2. 轮询 `/api/health` 直到后端就绪；
3. 加载 React 前端；
4. 应用退出时终止 Backend，并等待其完成 graceful shutdown。

## OA 当前状态

OA 数据源默认关闭，前端会显示“尚未配置”，不会影响其他公开数据源。首次在可正常访问 OA 的网络环境中使用时：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app oa-login
```

人工登录并完成真实 DOM 验证后，再启用 `config/sources.yaml` 中的 OA 并执行 `python -m app crawl --source oa`。当前不会猜测 OA DOM、绕过认证或保存明文密码。

更详细说明见 `backend/README.md` 与 `frontend/README.md`。
