# Gate 7A Result

PASS

# E2E Architecture

- Playwright Test `1.62.1`，Chromium-family 项目，单 worker，`retries: 0`。
- browser/channel：本地使用 Playwright `channel: 'chrome'` 驱动系统 Google Chrome，不设置硬编码 `executablePath`。
- frontend server：Playwright `webServer` 自动启动 Vite `127.0.0.1:4173`，并注入隔离后端 URL。
- backend server：Node 启动器自动 seed 后，以仓库虚拟环境启动 FastAPI `127.0.0.1:8010`。
- isolated DB：通过 `JLU_ENVIRONMENT=test` 与 `JLU_APP_DATA_DIR=frontend/.e2e/runtime` 使用专用 SQLite。
- lifecycle：`npm run e2e` 自动重建测试数据、启动前后端、启动浏览器、运行测试并停止相关服务，无需手工预启 5173/8000。
- Vitest 显式排除 `frontend/e2e/**`，单元测试与 Playwright 测试分别收集。

# Test Data Isolation

- E2E 数据库固定为 `frontend/.e2e/runtime/data/notices.db`，与用户数据库 `backend/data/notices.db` 路径完全分离。
- suite 启动时先删除旧 E2E runtime，再用真实 SQLAlchemy models 重建 schema，仅 seed 5 条 E2E 通知和 2 个 E2E 来源。
- seed 进程和 FastAPI 进程共享同一组 test-only 环境变量，不会回退到 development 数据目录。
- 每条测试开始前通过真实 mutation API 恢复 5 条 fixture 的 read/favorite 状态；每条测试使用独立浏览器 context，不依赖顺序或上一条测试的 localStorage。
- 最终两轮运行后确认 4173/8010 均无监听进程，测试后端已退出。

因此 Gate 7A 的 seed、mutation 和自动阅读验证只作用于专用测试 SQLite，绝不读取或污染用户真实 DB。

# Critical Journeys

1. Dashboard → Notice Detail：从首页最近通知进入正确详情。
2. Notices filter：关键词输入后 URL、筛选 UI 与结果集合一致，清空后恢复。
3. Favorite → Favorites → unfavorite：收藏后进入收藏页，取消收藏后成员关系更新。
4. SearchDialog → Notice Detail：搜索稳定关键词并打开正确详情。
5. Auto-read + list membership：未读详情触发真实 read mutation，随后从 `read=0` 列表移除。
6. Settings persistence：主题设置在 reload 后保持。
7. Notice 404：不存在的通知显示专用 404 状态与返回列表入口。
8. 390px mobile smoke：通过既有底部导航从首页进入“今日”。

# Browser Runtime

- Playwright bundled Chromium 在当前网络环境中长期停留于 0%，因此未再次无条件下载。
- 本机已安装 Google Chrome `152.0.7977.64`，Playwright system Chrome channel 的真实无头启动验证通过。
- 最终两轮完整 E2E 均使用 system Chrome channel。
- 这是本地 runtime 策略，不影响 Gate 7B；CI 可独立安装、缓存并切换到 Playwright bundled Chromium。

# Test Strategy

- selectors：优先使用 `getByRole`、`getByLabel`、可访问名称与稳定可见文本；URL 和 mutation 使用 `toHaveURL` 与真实 response 条件验证。
- waiting：只使用 Playwright locator/web-first assertions、URL/response 等待；没有任意 sleep 或 `waitForTimeout`。
- reset：suite 启动时重建隔离 DB，每条测试前恢复 mutation fixture，每条测试使用新 browser context。
- mutation isolation：所有 read/favorite 变更仅请求 `8010` 的隔离 test backend，测试不依赖执行顺序。
- retries：固定为 `0`，没有用重试掩盖 flaky。
- artifacts：screenshot `only-on-failure`、trace `retain-on-failure`、video off、HTML report 不自动打开。
- ignored outputs：`frontend/.e2e/`、`frontend/playwright-report/`、`frontend/test-results/` 已加入 `.gitignore`。

# Problems Found

- bundled Chromium 下载在当前网络长期 0%：改用已验证的 system Chrome channel。
- 测试前端 `4173` 未被隔离后端 CORS 允许：仅在 E2E 环境加入该 test origin。
- 初始断言与现有 UI 语义不一致：Dashboard 使用动态问候主标题、SearchDialog 结果是 button、移动底栏实际入口为“今日”；测试已按真实可访问语义修正。
- 初始 localStorage 清理脚本会在 reload 时再次执行，破坏 Settings persistence 验证：移除多余脚本，使用 Playwright 原生 context 隔离。
- Vitest 会收集 Playwright spec：显式排除 `e2e/**`，恢复 111 项单测的独立边界。

# Production Changes

No production change required.

Gate 7A 仅新增测试依赖、E2E 启动/seed/spec、测试收集边界、文档和生成物忽略规则；未修改产品业务实现。

# Files Changed

共 10 个文件：

- `.gitignore`
- `docs/GATE_7A_REPORT.md`
- `frontend/README.md`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.ts`
- `frontend/playwright.config.ts`
- `frontend/e2e/backend-server.mjs`
- `frontend/e2e/seed.py`
- `frontend/e2e/critical-journeys.spec.ts`

# E2E Validation

Run #1:

- 8/8 PASS。
- Playwright reported duration：16.0s。
- 1 worker，`retries: 0`，system Chrome channel。

Run #2:

- 8/8 PASS。
- Playwright reported duration：16.0s。
- 与 Run #1 之间未修改工作树；重新 seed 隔离 DB，1 worker，`retries: 0`。

补充：`npx playwright test --list` PASS，发现 1 个 spec 文件、8 条测试。

# Regression Validation

- frontend tests：111/111 PASS（25 files）。
- lint：PASS。
- build：PASS。
- backend pytest：43/43 PASS。

# Preserved Behavior

- Gate 6 Settings contract，包括 persistence/reactivity architecture。
- SearchDialog concurrency 与 request architecture。
- mutation/cache contract。
- auto-read。
- URL schema。
- request lifecycle。
- routes。
- error taxonomy。
- responsive/accessibility 与既有 UI / UX。
- backend production behavior。
- 用户数据库与真实数据。

# Deferred

Gate 7B：

- GitHub Actions CI。
- CI 中安装/缓存 Playwright bundled Chromium。
- CI artifact 上传、保留周期、并发和运行时预算。

Gate 8：

- Backend production hardening。

# Recommended Next Gate

Gate 7B
