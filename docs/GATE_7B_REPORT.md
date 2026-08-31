# Gate 7B Result

LOCAL PASS — CI PENDING

Windows 本地测试链路、E2E 隔离与 workflow 静态审计均已通过。当前仓库没有 Git remote，本机也没有 GitHub CLI，因此无法在本 Gate 内真实触发 GitHub Actions；必须在 workflow 被提交并推送后，以第一次 GitHub-hosted run 的结果决定是否改为正式 PASS。

# CI Architecture

新增 `.github/workflows/ci.yml`，触发条件为 push、pull request 和手工 workflow dispatch；权限仅为 `contents: read`，并对同一 ref 的旧运行启用并发取消。

Workflow 使用三个 job：

1. Backend tests
   - Ubuntu 24.04。
   - Python 3.13。
   - 安装 `backend[dev]`。
   - 执行 `python -m pytest`。
2. Frontend quality
   - Ubuntu 24.04。
   - Node.js 24。
   - `npm ci`。
   - lint、111 项 Vitest、production build。
3. Playwright E2E
   - 等待 Backend 与 Frontend job 都成功。
   - 创建 `backend/.venv` 并安装后端运行依赖。
   - `npm ci`。
   - 显式执行 `npx playwright install --with-deps chromium`。
   - 运行现有 8 条关键 Journey。
   - 失败时上传诊断文件，结束时始终清理 E2E runtime。

各 job 都有明确 timeout。Workflow 使用 `actions/checkout@v7`、`actions/setup-python@v7`、`actions/setup-node@v7` 和 `actions/upload-artifact@v7`。

# Environment

- Local OS：Windows 当前开发工作站。
- Local Python：3.13.13。
- Local Node.js：24.16.0。
- Local browser：Google Chrome 152.0.7977.64，通过 Playwright system Chrome channel。
- Playwright Test：1.62.1。
- CI runner：GitHub-hosted Ubuntu 24.04。
- CI Python：3.13。
- CI Node.js：24。
- CI browser：由 Playwright 1.62.1 明确安装的 bundled Chromium，不依赖 runner 预装 Chrome。

# E2E Runtime

- Frontend：Vite `127.0.0.1:4173`。
- Backend：FastAPI `127.0.0.1:8010`。
- Readiness：Playwright `webServer` 轮询前端 URL 和后端 `/api/health`；不使用固定 sleep。
- Database：`frontend/.e2e/runtime/data/notices.db`。
- Seed：每轮先删除旧 runtime，再用真实 SQLAlchemy models 重建 schema，写入 5 条测试通知和 2 个测试来源。
- Per-test reset：每条测试前通过隔离后端的真实 mutation API 恢复 read/favorite fixture。
- Process cleanup：Playwright 管理前后端进程；本地验证结束后 4173/8010 均无监听进程。
- Data cleanup：新增跨平台 E2E runner，在 Playwright 退出后的 `finally` 中删除 runtime 并保留原始退出码；workflow 另有 `if: always()` cleanup 兜底。

# CI Isolation

- E2E 启动器显式设置 `JLU_ENVIRONMENT=test` 与 `JLU_APP_DATA_DIR=frontend/.e2e/runtime`，不读取或修改 `backend/data/notices.db`。
- CI 不提交、不缓存、不上传 `.e2e/runtime` 或任何 SQLite。
- OA 来源在真实配置中保持 disabled；CI 不安装 backend OA extra，不执行 crawl 或 oa-login。
- E2E 只访问本地 4173/8010 服务和 seed 数据，不访问真实 OA、公开学院站点或吉林大学校园网。
- Workflow 不需要开发者 secret、Cookie、OA profile 或任何校园网状态。
- 测试环境仅为 `http://127.0.0.1:4173` 配置后端 CORS。

# Failure Diagnostics

- Screenshot：`only-on-failure`。
- Trace：本地 `retain-on-failure`；CI `on-first-retry`。
- HTML report：始终由 Playwright 生成，默认不自动打开。
- Video：关闭，避免无必要的体积与隐私面。
- CI retry：1；同时启用 `failOnFlakyTests`，重试后通过的 flaky 仍会使 CI 失败。
- E2E job 失败时，`actions/upload-artifact@v7` 上传 `frontend/playwright-report/` 与 `frontend/test-results/`，保留 7 天。
- Artifact 路径不包含 `.e2e/runtime`、SQLite、node_modules、Python venv、日志、用户数据或 secret。

# Verification

实际在当前 Windows 环境执行：

- `npm run e2e`：8/8 PASS，Playwright reported duration 15.2s。
- E2E 后检查：4173/8010 均无监听进程，`frontend/.e2e/runtime` 已删除。
- `npm test -- --run`：111/111 PASS（25 files）。
- `npm run lint`：PASS。
- `npm run build`：PASS。
- `backend/.venv/Scripts/python.exe -m pytest`：43/43 PASS。
- Local Playwright discovery：8 tests / 1 file — PASS。
- CI-mode Playwright discovery（`CI=true`）：8 tests / 1 file — PASS，配置不再要求 system Chrome channel。
- Workflow YAML parse：PASS，识别 `backend`、`frontend`、`e2e` 三个 job。
- `git diff --check`：PASS。

尚未执行：

- GitHub-hosted Ubuntu 24.04 workflow。原因是当前仓库没有 Git remote，且本机没有 GitHub CLI；未 commit、未 push，也未虚假声明 Actions 通过。

# Problems Found

1. Gate 7A backend launcher 只识别 Windows `.venv/Scripts/python.exe`。
   - 修复：按平台选择 Windows `Scripts/python.exe` 或 POSIX `.venv/bin/python`，同时允许显式 `JLU_E2E_PYTHON` 覆盖。
2. Playwright 项目始终强制 system Chrome channel，CI 即使安装 bundled Chromium 也不会使用。
   - 修复：本地保留 `channel: chrome`，CI 分支不设置 channel，使用明确安装的 bundled Chromium。
3. Gate 7A 运行后会释放进程和端口，但隔离 SQLite/runtime 仍保留在磁盘。
   - 修复：新增跨平台 runner 的 `finally` cleanup，并在 workflow 中使用 `if: always()` 二次兜底；本地已验证 runtime 被删除。
4. CI retry 可能掩盖不稳定测试。
   - 修复：CI 允许一次 retry 以生成首重试 trace，同时启用 `failOnFlakyTests`，flaky 仍为失败。
5. 仓库原先没有 GitHub Actions workflow。
   - 修复：新增完整 Backend / Frontend / E2E pipeline、read-only permission、timeout、concurrency 与失败 artifact。

# Remaining Risks

- GitHub-hosted Ubuntu workflow 尚未真实运行；这是 Gate 7B 当前唯一阻止正式 PASS 的验收项。
- Backend 依赖使用 `pyproject.toml` 中的兼容版本范围而非完整 lock file；未来兼容范围内的新版本仍可能改变 CI 解析结果。当前 workflow 固定 Python/OS，并由 pytest 与真实 app startup E2E 作为防线。

# Files Changed

Gate 7B 新增或进一步修改 8 个文件：

- `.github/workflows/ci.yml`
- `README.md`
- `docs/GATE_7B_REPORT.md`
- `frontend/README.md`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/e2e/backend-server.mjs`
- `frontend/e2e/run.mjs`

Gate 7A 的既有未提交文件和改动均保留，没有 reset、checkout、clean、commit 或 push。

# Recommended Next Step

将当前工作树提交并推送到 GitHub，观察 `.github/workflows/ci.yml` 的第一次 Ubuntu 24.04 run。Backend、Frontend、Playwright E2E 三个 job 全部通过后，将本报告的结果从 `LOCAL PASS — CI PENDING` 更新为 `PASS`。
