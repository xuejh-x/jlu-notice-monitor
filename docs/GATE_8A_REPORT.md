# Gate 8A Result

LOCAL PASS — CI PENDING

Gate 8A 的本地实现、自动化回归、Windows packaged sidecar、debug/release 桌面烟测和进程清理验证均已完成。最终状态将在本次改动推送并通过现有 GitHub Actions 三个 job 后升级为 `PASS`。

# Previous Architecture

```text
Tauri
  → React
  → manually started FastAPI
  → SQLite
```

桌面窗口只承载 React。开发者必须另开 PowerShell 执行 `python -m app serve`；Tauri 不持有 Backend 进程，也没有 readiness、退出清理或启动失败边界。

# New Architecture

```text
Tauri
  → managed packaged backend sidecar
  → GET /api/health readiness
  → React application
  → FastAPI
  → SQLite
```

Web 开发仍可独立手工启动 FastAPI 和 Vite。只有 Tauri runtime 启用桌面 Backend boundary，因此既有浏览器开发和 Playwright E2E 架构不变。

# Backend Packaging

- Tool: PyInstaller `6.22.2`，依赖声明为 `pyinstaller>=6.17,<7`。
- Mode: `onefile`。
- Entry point: `jlu-notice-backend.exe serve --managed --host 127.0.0.1 --port 8000`。
- Reproducible command: from `frontend/`, run `npm run backend:build`。
- Source build command: `backend/.venv/Scripts/python.exe backend/scripts/build_sidecar.py` 的等价项目内调用。
- Staged executable: `frontend/src-tauri/binaries/jlu-notice-backend-x86_64-pc-windows-msvc.exe`。
- Tauri build-time executable: Tauri stages the sidecar beside the desktop binary as `jlu-notice-backend.exe`。

选择 one-file 是因为当前 Backend 的 production startup 依赖集合可以被 PyInstaller 稳定分析，真实 packaged executable 已通过启动、health、SQLite 和日志验证；同时 Tauri `externalBin` 可以管理单一文件，避免 onedir 资源目录在 dev/build/staging 之间被遗漏。one-file 的解压启动成本由 20 秒 readiness 总超时覆盖，不使用固定 sleep 判定成功。

构建脚本通过 `rustc --print host-tuple` 自动生成 Tauri 所需 target-triple 文件名，不依赖手工复制、重命名或开发机绝对路径。PyInstaller 的 build/dist 目录和 staged binary 均被 Git 忽略。

# Sidecar Integration

- `tauri.conf.json` 的 `bundle.externalBin` 声明 `binaries/jlu-notice-backend`。
- Tauri 2 的 `tauri-plugin-shell` 仅从 Rust 内部调用；没有向 WebView 开放通用 shell command 权限。
- `BackendController` 持有 child handle、PID、generation、termination flag、phase 和安全错误摘要。
- 原子 start guard 防止重复启动调用产生多个 sidecar。
- shell plugin 的 child tracking 作为异常退出兜底；正常退出使用项目自己的 graceful shutdown 协议。
- Cargo.lock 现在纳入版本控制，以固定 Rust/Tauri 依赖解析。

# Startup Lifecycle

```text
Tauri setup
  → inspect 127.0.0.1:8000
  → spawn owned sidecar when free
  → poll /api/health every 150 ms
  → require HTTP 200 + service marker + status ok + database ok
  → expose ready state
  → React DesktopBackendBoundary renders the application
```

总 startup timeout 为 20 秒。sidecar 在 ready 前终止时立即失败。React 在 Tauri 中先显示带页面主 `h1` 的启动状态；失败时复用 `ErrorState`，展示安全的中文摘要和“重新启动服务”按钮。普通 Web 环境由 `isTauri()` 旁路，不新增启动等待。

# Shutdown Lifecycle

```text
Tauri ExitRequested
  → prevent first exit
  → write "shutdown" to owned child stdin
  → Backend sets Uvicorn should_exit
  → FastAPI lifespan shuts down crawler and database
  → wait up to 5 seconds
  → kill only the owned child handle if still alive
  → Tauri exits
```

Backend 的 managed stdin watcher 也把 owner pipe EOF 视为 shutdown，因此 owner 异常消失时仍有退出信号。实现不按进程名终止 Python 或 Backend，不会杀死外部服务。

# Runtime Data

Production sidecar 强制设置 `JLU_ENVIRONMENT=production`，继续使用已有 path abstraction：

```text
%LOCALAPPDATA%\JLU Notice Monitor\
├── data\notices.db
├── logs\app.log
├── oa-profile\
├── cache\
└── config\
```

桌面烟测使用 `JLU_APP_DATA_DIR=frontend/.e2e/gate8a-runtime` 隔离覆盖，避免触碰开发者或用户真实数据。packaged executable 首次创建 SQLite 和日志后，Tauri debug/release 均复用同一数据库；重启前后数据库 SHA-256 均为 `B3D636DA5135081F04E44C75D6D8FA3578E50C3EF526888CFBEBB5ED5B2BEC89`，证明没有删除或覆盖。production path 单元测试同时验证未设置 override 时落入 `%LOCALAPPDATA%\JLU Notice Monitor`。

# Port Strategy

Gate 8A 保留固定 `127.0.0.1:8000`：

- Port free: spawn one owned sidecar。
- Healthy JLU Notice Monitor Backend already present: reuse it as external，不启动第二实例，也不在退出时终止它。
- Other service occupies 8000: fail immediately with clear UI，不无限等待、不重复 spawn、不终止外部进程。

`/api/health` 新增稳定的 `service: "jlu-notice-monitor"` marker；身份判断还要求 `status=ok` 和 `database=ok`。Backend 始终显式绑定 `127.0.0.1`，没有监听 `0.0.0.0`。

# Security

- API 仅监听 loopback。
- CSP 继续只允许 `http://127.0.0.1:8000` 和既有 Tauri IPC；没有 wildcard。
- WebView 不获得通用 shell plugin 权限。
- UI 只显示预定义安全错误，不显示 token、cookie、secret、OA credential 或完整本地路径。
- Backend production 日志继续写入 runtime `logs/`；认证头、密码、cookie 与 token 未加入日志。
- OA 保持默认 disabled；PyInstaller production sidecar 不打包 Playwright，OA 不阻塞桌面启动。

# Verification

- Packaged Backend build: PASS (`npm run backend:build`)。
- Packaged Backend standalone: PASS；无系统 Python 命令参与运行，`/api/health` 返回 service/status/database all healthy。
- Tauri dev: PASS；自动 build/stage sidecar、启动 Vite、编译 Tauri 和打开 Dashboard。
- Tauri release build without installer: PASS (`npm run tauri -- build --no-bundle`)。
- Tauri release executable: PASS；Dashboard 可见、Backend online、正常退出。
- Loopback: PASS；真实 health 显示 `environment=production`。
- Runtime log and database: PASS；隔离目录实际产生 `logs/app.log` 与 `data/notices.db`。
- Existing GitHub workflow: unchanged；final hosted run pending Gate 8A push。

# Tests

- Backend pytest: `45/45 PASS`（原 43 项 + 2 项 Gate 8A managed CLI/lifecycle tests）。
- Frontend Vitest: `114/114 PASS`（原 111 项 + 3 项 DesktopBackendBoundary tests）。
- Frontend lint: `PASS`。
- Frontend production build: `PASS`。
- Playwright E2E: `8/8 PASS`。
- Rust `cargo fmt --check`: `PASS`。
- Rust `cargo check`: `PASS`。
- Rust `cargo clippy --all-targets -- -D warnings`: `PASS`。
- Rust tests: `3/3 PASS`。
- Tauri release build (`--no-bundle`): `PASS`。

# Manual Desktop Smoke

## Cold Start

- Confirmed port 8000 free before launch。
- Started Tauri without manually starting Python。
- PyInstaller one-file sidecar automatically started as a Tauri child/descendant。
- `/api/health` reached ready with `service=jlu-notice-monitor`, `database=ok`, `environment=production`。
- Dashboard rendered normally and displayed Backend online；notice/dashboard requests completed with no offline state。

## Exit

- Closed the real Windows window through its native close button。
- Graceful shutdown completed and Tauri exited with code 0。
- Matching Tauri/sidecar process count after close: `0`。
- Port 8000 listener count after close: `0`。

## Restart

- Restarted the compiled desktop application against the same isolated runtime root。
- Backend became healthy again and Dashboard rendered normally。
- Existing six source records were readable。
- Second close again left `0` matching processes and `0` port listeners。

## Failure

- Started an unrelated loopback HTTP server on port 8000。
- Tauri did not spawn a sidecar and did not kill the unrelated server。
- UI rendered an alert with page `h1` “本地通知服务启动失败”, the specific port-conflict summary, and a “重新启动服务” button。
- After stopping only the test server, clicking retry started the owned sidecar and restored Dashboard。
- Final close left no Backend process or 8000 listener。

## Existing Data

- The SQLite file existed before the first Tauri launch because it was created by the standalone packaged Backend smoke。
- Debug start, exit, restart, failure recovery and release start all reused the same file。
- Database SHA-256 remained exactly unchanged across the restart checkpoint；the file was neither deleted nor overwritten。

# Problems Found

1. **Tauri shell had no Backend ownership.** It required a separately started Python process. Fixed with a packaged sidecar and `BackendController` lifecycle state。
2. **Health did not identify this product.** An arbitrary HTTP 200 responder could not be safely distinguished. Added the stable service marker and strict health payload checks。
3. **Backend had no owner-bound graceful shutdown channel.** Added `serve --managed`, stdin command/EOF monitoring, Uvicorn graceful exit, and a child-handle-only force fallback。
4. **Desktop startup could render the normal app before Backend readiness.** Added a Tauri-only startup/failure boundary with accessible status, safe error copy and retry。
5. **Tauri externalBin requires target-triple naming and compilation failed when the staged file was absent.** Added a reproducible script that builds and stages the correct filename automatically。
6. **Cargo.lock was caught by the repository-wide `*.lock` rule.** Added a narrow exception so Rust desktop dependency resolution is reproducible。
7. **The first managed lifecycle test used an invalid Python `TextIO` import.** The backend regression suite exposed it immediately; corrected to `typing.TextIO` before packaging and smoke tests。

# Remaining Risks

- Fixed port 8000 can still conflict with another local application. Gate 8A handles this safely and visibly but does not implement a dynamic port handshake。
- A second desktop process can reuse the first process's healthy Backend without spawning a duplicate. If the owning desktop exits first, the second process does not take over ownership automatically; a single-instance desktop policy or ownership handoff may be considered in a later Gate。
- PyInstaller one-file startup includes extraction overhead and may be inspected more aggressively by endpoint security products; the measured local startup fits the 20-second readiness budget。
- OA browser automation is intentionally excluded from the packaged sidecar and remains disabled. Real OA integration requires its own validated Gate。
- Installer layout, code signing, application identifier cleanup, Windows release CI and updater behavior are not covered here and belong to Gate 8B/Release Gate。

# Changed Files

- `.gitignore`
- `README.md`
- `backend/app/__main__.py`
- `backend/app/api/routes.py`
- `backend/jlu_notice_backend.spec`
- `backend/pyproject.toml`
- `backend/scripts/backend_sidecar.py`
- `backend/scripts/build_sidecar.py`
- `backend/tests/test_runtime.py`
- `frontend/package.json`
- `frontend/src-tauri/Cargo.lock`
- `frontend/src-tauri/Cargo.toml`
- `frontend/src-tauri/src/backend.rs`
- `frontend/src-tauri/src/lib.rs`
- `frontend/src-tauri/tauri.conf.json`
- `frontend/src/components/runtime/DesktopBackendBoundary.test.tsx`
- `frontend/src/components/runtime/DesktopBackendBoundary.tsx`
- `frontend/src/components/ui/Feedback.tsx`
- `frontend/src/main.tsx`
- `docs/GATE_8A_REPORT.md`

Generated PyInstaller output, staged sidecar binaries, Cargo target artifacts, frontend dist, E2E runtime, Playwright reports, virtual environments and node_modules remain ignored and are not included in Git。

# Next Step

Gate 8B — Windows installer/release packaging, signing/reputation strategy, Windows packaging CI and release delivery. Do not start it as part of Gate 8A.
