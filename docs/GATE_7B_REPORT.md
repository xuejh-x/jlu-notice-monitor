# Gate 7B Result

PASS

Windows 本地测试链路、E2E 隔离、workflow 静态审计和真实 GitHub-hosted CI 均已完成。第一次 CI 暴露了一处 E2E 客户端导航同步缺口；修复后第二次完整运行的 Backend、Frontend、Playwright E2E 三个 job 全部通过，因此 Gate 7B 正式 PASS。

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

# GitHub Actions Runs

真实运行环境为 GitHub-hosted `ubuntu-24.04`；workflow 配置 Python 3.13 与 Node.js 24，第一次 E2E 日志实际记录 Python 3.13.15，并使用 Playwright 1.62.1 安装的 bundled Chromium。

第一次运行：CI #1，run `33344944833`，commit `8d239e4`。

- Backend tests：PASS，20s。
- Frontend quality：PASS，44s；Vitest 111/111 PASS（25 files），lint 与 build 均通过。
- Playwright E2E：FAIL，57s；7/8 PASS，收藏旅程在原始尝试和 retry 中均因同一严格定位错误失败。
- 失败诊断 artifact 正常上传，包含 screenshot、error context、retry trace 与 HTML report，不包含 runtime 或 SQLite。

修复后运行：CI #2，run `33345362497`，commit `c2154e7`。

- Backend tests：PASS，21s。
- Frontend quality：PASS，48s；Vitest 111/111 PASS（25 files），lint 与 build 均通过。
- Playwright E2E：PASS，1m 9s，8/8 PASS。
- Workflow 总状态：Success，总时长 2m 3s，无失败 artifact。

没有发现 Linux 路径、可执行权限、Python 3.13、Node.js 24、`npm ci`、Playwright Chromium 安装、localhost readiness、进程清理或测试数据库路径问题。唯一差异是 CI Chromium 的客户端导航时序更快地暴露了测试缺少明确路由同步的问题；该问题已按测试同步契约修复。

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

- 修复后 `npm run e2e`：8/8 PASS，Playwright reported duration 15.8s。
- E2E 后检查：4173/8010 均无监听进程，`frontend/.e2e/runtime` 已删除。
- `npm test -- --run`：111/111 PASS（25 files）。
- `npm run lint`：PASS。
- `npm run build`：PASS。
- `backend/.venv/Scripts/python.exe -m pytest`：43/43 PASS。
- Local Playwright discovery：8 tests / 1 file — PASS。
- CI-mode Playwright discovery（`CI=true`）：8 tests / 1 file — PASS，配置不再要求 system Chrome channel。
- Workflow YAML parse：PASS，识别 `backend`、`frontend`、`e2e` 三个 job。
- `git diff --check`：PASS。

真实 GitHub Actions 最终结果：

- Backend tests：PASS。
- Frontend quality：PASS。
- Playwright E2E：PASS，8/8。
- CI #2 workflow：PASS。

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
6. 第一次 GitHub-hosted E2E 中，收藏旅程点击 Favorites 列表链接后立即查找全局“取消收藏”按钮，没有等待 React Router 完成客户端导航；CI Chromium 此时仍可见列表中的两个同名按钮，Playwright strict mode 因匹配 2 个元素而稳定失败。
   - 修复：点击详情链接后明确等待 URL 变为 `/notices/102`，并确认详情页主标题可见，再执行取消收藏。未增加 timeout、未放宽定位、未删除测试，也未用 retry 掩盖失败；本地 8/8 与 CI 8/8 均通过。

# Remaining Risks

- Backend 依赖使用 `pyproject.toml` 中的兼容版本范围而非完整 lock file；未来兼容范围内的新版本仍可能改变 CI 解析结果。当前 workflow 固定 Python/OS，并由 pytest 与真实 app startup E2E 作为防线。
- GitHub Actions 匿名 API 可能受共享出口 rate limit 影响，但不影响 workflow 执行；本 Gate 使用已登录的 Actions 页面和原始 job 日志完成逐 job 验证。

# Files Changed

Gate 7B 新增或进一步修改 9 个文件：

- `.github/workflows/ci.yml`
- `README.md`
- `docs/GATE_7B_REPORT.md`
- `frontend/README.md`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/e2e/backend-server.mjs`
- `frontend/e2e/critical-journeys.spec.ts`
- `frontend/e2e/run.mjs`

Gate 7A / Gate 7B 的既有改动均被保留；整个收尾过程没有 reset、checkout 或 clean，也没有将数据库、secret、OA 登录数据、runtime、venv、node_modules 或 Playwright 产物提交到 GitHub。

# Recommended Next Step

Gate 7B 已完成。下一步为 Gate 8；在收到明确指令前不进入 Gate 8。
