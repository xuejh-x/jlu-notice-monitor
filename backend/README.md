# JLU Notice Monitor Backend

运行于 Windows 11 的吉林大学通知监控后端。它抓取公开通知列表与详情，完成 NEW / UPDATED / UNCHANGED 判断、跨来源去重、规则分类、重要度评分、上下文日期提取，并将结果写入 SQLite，供 FastAPI 和未来的 React 前端使用。核心流程不依赖任何 AI API。

## 环境与安装

要求 Windows 11、PowerShell、Python 3.12+（当前开发验收使用 Python 3.13.13）。在 PowerShell 中执行：

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

若 `py` 启动器可用，也可用 `py -3.13 -m venv .venv`。配置文件位于 `config/`：

- `sources.yaml`：来源、栏目 URL、启用状态和 Adapter；
- `keywords.yaml`：分类关键词及评分权重；
- `settings.yaml`：重试、User-Agent、锁文件和截止日期规则；
- `.env`：本机数据库、超时、CORS 等覆盖项。

开发环境数据库默认位于 `data/notices.db`，滚动日志位于 `logs/app.log`。两者都不会进入 Git。生产环境的运行时文件统一放入 `%LOCALAPPDATA%\JLU Notice Monitor\`。

## CLI

```powershell
.\.venv\Scripts\python.exe -m app bootstrap
.\.venv\Scripts\python.exe -m app crawl
.\.venv\Scripts\python.exe -m app crawl --source ccst
.\.venv\Scripts\python.exe -m app test-source ccst
.\.venv\Scripts\python.exe -m app serve
.\.venv\Scripts\python.exe -m app serve --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m app run
```

`bootstrap` 建立初始基线，保存抓到的历史通知但不把它们计为 NEW。`crawl` 才进行正常的新通知/更新统计。`run` 先抓取一次再启动 API。也可直接执行 `scripts/bootstrap.ps1`、`scripts/run_crawler.ps1` 和 `scripts/start_backend.ps1`。

API 默认地址为 `http://127.0.0.1:8000`，Swagger 为 `http://127.0.0.1:8000/docs`。CORS 仅允许配置中的本机开发 Origin，默认是 `localhost:5173` 与 `127.0.0.1:5173`。

## API

- `GET /health`：兼容健康检查入口
- `GET /api/health`：数据库 readiness probe，供未来 Tauri sidecar 使用
- `GET /api/notices`：数据库层分页与组合筛选，支持 `page`、`page_size`、`favorite`、`read`、`category`、`source`、`deadline_status`、`q`，并兼容 `keyword`、`status`、`min_score`、`date_from`、`date_to`
- `GET /api/notices/{id}`
- `GET /api/notices/today`
- `GET /api/notices/important`
- `GET /api/notices/deadlines`
- `GET /api/categories`
- `GET /api/sources`
- `GET /api/stats`
- `GET /api/search?keyword=...`
- `GET /api/dashboard`
- `POST /api/notices/{id}/read` 与 `/unread`
- `POST /api/notices/{id}/favorite` 与 `/unfavorite`
- `POST /api/notices/{id}/archive` 与 `/unarchive`
- `POST /api/crawler/run`
- `POST /api/crawler/run/{source}`
- `GET /api/crawler/status`

手动抓取 API 使用进程内任务和跨进程文件锁，重复请求返回 409；单个 Source 或单条详情失败会被记录，但不会中止其他公开 Source。

## 当前公开数据源

默认启用并已用真实公开页面验证：

- `cse`：网络安全学院“学院通知”“本科教学通知”；
- `ccst`：计算机科学与技术学院“教学通知”；
- `csw`：软件学院“学院通知”“教办通知”；
- `jwc`：本科生院“通知公告”；
- `innovation`：创新创业教育学院“通知公告”。

各站点使用独立 Adapter 类型和配置化栏目，公共 WebPlus 页面解析由容错解析器复用。测试 HTML 固定在 `tests/fixtures/`，pytest 不依赖实时网站。

## OA 当前状态

OA 数据源当前默认关闭，`GET /api/sources` 会返回 `enabled: false`、`status: "disabled"` 和“尚未完成首次登录配置”。它不参与公开 Source 的抓取，也不会影响公开 Source 的成功或失败。

框架已预留 Playwright persistent context、登录状态检查、`OA_LOGIN_EXPIRED` 异常和独立 Source 隔离。浏览器 profile 保存到 `data/browser_profile/oa/`，不会读取或保存明文密码，且已被 `.gitignore` 排除。

首次在能够正常访问 OA 的网络环境中执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[oa]"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m app oa-login
```

浏览器打开后由本人完成统一身份认证。首次真实登录后，先根据登录后的实际 HTML 完成并测试 OA Adapter，再将 `config/sources.yaml` 中 OA 的 `enabled` 改为 `true`，最后执行：

```powershell
.\.venv\Scripts\python.exe -m app crawl --source oa
```

当前代码明确返回 `OA_UNCONFIGURED`，没有猜测登录后的通知 DOM，也不会模拟成功抓取。

## 运行目录

所有运行时可写路径由 `app.paths` 统一管理，不依赖当前工作目录，也不硬编码用户名：

- `get_app_data_dir()`
- `get_database_path()`
- `get_log_dir()`
- `get_oa_profile_dir()`
- `get_cache_dir()`
- `get_runtime_config_dir()`

开发环境继续使用项目内的 `data/`、`logs/` 和 `cache/` 等目录。生产环境设置 `JLU_ENVIRONMENT=production` 后使用：

```text
%LOCALAPPDATA%\JLU Notice Monitor\
├── data\notices.db
├── logs\
├── oa-profile\
├── cache\
└── config\
```

`JLU_APP_DATA_DIR` 可覆盖运行目录，测试全部使用临时目录。`JLU_DATABASE_URL` 仍可显式覆盖数据库连接；程序不会自动迁移或删除旧数据库。

## Sidecar 生命周期准备

Backend 默认仅监听 `127.0.0.1:8000`。可通过 `JLU_HOST` / `JLU_PORT`，或 `serve --host` / `serve --port` 覆盖。FastAPI lifespan 会完成数据库初始化、Source 同步、Crawler 后台任务取消和 SQLAlchemy engine 释放；正常 Ctrl+C 可干净退出。

未来 Tauri 应先启动 Backend，轮询 `GET /api/health`，健康后加载前端，并在应用退出时终止 Backend、等待 graceful shutdown。本阶段尚未开始 Tauri 或 EXE 打包。

## Windows Task Scheduler

安装每天 08:00 的任务：

```powershell
Set-Location E:\jlu-notice-monitor\backend
.\scripts\install_task.ps1
```

修改时间（例如 07:30）会覆盖同名任务：

```powershell
.\scripts\install_task.ps1 -DailyAt "07:30"
```

查看与手动启动：

```powershell
Get-ScheduledTask -TaskName "JLU Notice Monitor"
Start-ScheduledTask -TaskName "JLU Notice Monitor"
```

删除：

```powershell
Unregister-ScheduledTask -TaskName "JLU Notice Monitor" -Confirm:$false
```

脚本使用当前用户和 `RunLevel Limited`，通常不要求管理员权限；若本机组策略禁止普通用户注册计划任务，请以管理员身份打开 PowerShell 后重试。任务设置为错过后尽快运行、最多同时一个实例、最长运行两小时。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

测试覆盖 HTML 列表与详情解析、附件、日期与截止语境、规范化、内容哈希、分类评分、跨站去重、NEW/UPDATED/UNCHANGED 持久化、SQLite、API、OA 禁用状态和 OA 异常框架。

## 安全说明

不要提交 `.env`、SQLite、日志、Cookie、OA profile 或任何 session。日志只记录来源、数量、耗时和错误，不记录密码、Token、Cookie 或 session。程序不会绕过统一身份认证、验证码或权限控制。
