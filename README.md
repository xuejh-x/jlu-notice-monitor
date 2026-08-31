# jlu-notice-monitor

吉林大学通知与竞赛信息自动监控系统，包含 FastAPI 本机后端、SQLite 数据库、响应式中文 React 前端和 Tauri 2 Windows 桌面壳层。桌面开发模式会构建并自动管理自包含的 Windows Backend sidecar；普通 Web 开发模式仍可分别启动前后端。

## Desktop Backend Sidecar

```text
Tauri Window
    ↓
React Frontend
    ↓ readiness boundary
Tauri lifecycle manager
    ↓ managed sidecar
Packaged FastAPI Backend
    ↓
SQLite
```

Tauri 使用官方 sidecar 机制启动 `jlu-notice-backend.exe`，轮询 `http://127.0.0.1:8000/api/health` 后才放行 React 主界面。关闭桌面窗口时会先通过 sidecar stdin 请求 graceful shutdown，超时后只结束当前窗口持有的 child process。正式安装器、签名、更新与 Release workflow 留给 Gate 8B。

首次准备环境：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,dev]"

Set-Location ..\frontend
npm install
```

桌面开发无需手工启动 Python Backend：

```powershell
Set-Location frontend
npm run tauri dev
```

该命令会依次执行 `npm run backend:build`、按 Rust target triple 暂存 sidecar、启动 Vite，再启动 Tauri。也可以单独执行 `npm run backend:build` 复现 PyInstaller one-file 构建。生成物位于忽略 Git 的 `frontend/src-tauri/binaries/`，不要求系统安装 Python 才能运行。

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

Web 开发流程与桌面 sidecar 相互独立：`npm run dev` 不会自动启动 Backend，方便继续调试 Python 代码。若 8000 已由健康的本项目 Backend 占用，桌面应用会复用它且不会取得进程所有权；若被其他程序占用，则显示明确失败状态与重试入口，不会重复 spawn 或终止外部进程。

## CI

GitHub Actions 在 Ubuntu 24.04 上依次验证后端 pytest、前端 lint / Vitest / production build，以及使用 bundled Chromium 的 8 条 Playwright E2E。E2E 自动创建和清理 `frontend/.e2e/runtime` 下的隔离数据库，不访问真实 SQLite 或 OA，也不依赖校园网和开发者 secret。

本地完整验证：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest

Set-Location ..\frontend
npm test -- --run
npm run lint
npm run build
npm run e2e
```

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

Tauri 采用以下启动顺序：

1. 检查 8000 的服务身份并启动 packaged FastAPI sidecar；
2. 轮询 `/api/health` 直到后端就绪；
3. 加载 React 前端；
4. 应用退出时请求 Backend graceful shutdown，并等待其退出；
5. 超时才结束当前 Tauri 实例持有的 child，绝不按进程名全局终止。

## OA 当前状态

OA 数据源默认关闭，前端会显示“尚未配置”，不会影响其他公开数据源。首次在可正常访问 OA 的网络环境中使用时：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app oa-login
```

人工登录并完成真实 DOM 验证后，再启用 `config/sources.yaml` 中的 OA 并执行 `python -m app crawl --source oa`。当前不会猜测 OA DOM、绕过认证或保存明文密码。

更详细说明见 `backend/README.md` 与 `frontend/README.md`。
