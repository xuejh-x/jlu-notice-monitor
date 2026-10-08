# 蓝桥杯单页监测来源实施报告

日期：2026-10-08。范围：新增公开本地来源 `lqb`，不安装客户端、不发布、不修改真实用户数据库。

## 行为

- 目标：<https://lus-jlu.github.io/lqb.html>。名称：蓝桥杯赛事信息（吉林大学）。
- `CUSTOM_LOCAL_PUBLIC` / `single_page_monitor` / `local_only`，复用启动、手动及默认15分钟定时检查；Cloud Worker 不执行此来源。
- 只监测最新届次比赛科目、赛程、吉林大学组织管理、院校报名、参赛相关政策和鼓励措施。政策表格仅保留蓝桥杯行及表头；不导入报名人数、累计奖项、历届获奖名单。
- 章节标准化包含 Unicode、空白、行末标点和内联排版处理，保留有意义的日期、金额、条件、链接及有序报名步骤。比赛科目重排不通知。
- 首次完整有效抓取只建立基线，没有 Notice、UserState 或 NEW 通知事件。
- 后续实质更新按一次检查合并为一条通知，提供章节增删/修改前后文本。届次切换不重新静默初始化。
- `AppState` 的 `single-page-baseline:{source.id}` 保存解析版本、届次、章节文本及 SHA-256、修订序号、首次检测及最近检查时间；与 Cloud / local fallback 基线隔离。
- 通知、UserState、NotificationEvent 和新基线使用同一事务；抓取、解析、基线格式或入库错误不会推进基线。
- 修订使用严格的 `origin_item_key` / `public_id` 身份，仅对此适配器启用，避免相同网址或相似标题合并不同更新。重复检查不通知，A → B → A 仍生成相应修订。
- `publish_date=null`，使用现有 `first_seen_at` 记录真实检测时间。正文和界面明确这是检测时间，不是官方发布时间。
- 不从变化正文中自动提取单一截止日：其中包含变更前日期及不同科目赛程，避免生成错误的截止提醒。具体日期保留在变化正文中。
- 复用原有来源筛选、详情、原文外链、自动已读、主动未读、全部已读和分页。专用来源不允许通用解析器编辑或上云。

## 修改文件

Backend：

- `app/sources/lqb.py`：页面章节解析、标准化、内容校验。
- `app/services/page_monitor.py`：基线格式、差异、修订身份和通知候选。
- `app/sources/base.py`：可选 `SinglePageSource` 接口，抓取阶段不写基线。
- `app/sources/registry.py`、`config/sources.yaml`：适配器注册及公开本地来源配置。
- `app/crawler/runner.py`：快照事务、严格身份；普通列表来源保持原来的详情跳过和去重行为。
- `app/api/source_management.py`：专用来源编辑、上云防误操作。
- `tests/test_lqb_monitor.py`：34项新增测试，包括独立基线、原有用户状态保留、链接变化、回滚及 API 阅读流程。

Frontend：

- `src/utils/noticeSearchParams.ts`、`src/components/notice/NoticeFilters.tsx`：来源筛选。
- `src/utils/noticeMeta.ts`、`src/components/notice/NoticeCard.tsx`、`src/pages/NoticeDetailPage.tsx`：检测时间展示。
- `src/pages/SourcesPage.tsx`：本地来源提示及专用适配器保护。
- `src/components/notice/NoticeCard.test.tsx`、`src/pages/NoticeDetailPage.test.tsx`、`src/pages/NoticesPage.test.tsx`、`src/pages/SourcesPage.test.tsx`：5项新增前端回归。
- `e2e/lqb-monitor.spec.ts`：1440px / 390px 的2项新流程测试。
- `docs/design/design.md`：来源选项、检测时间与管理行为约定。

## 初次实现验证（专项修复前）

| 检查 | 实际命令 / 方法 | 结果 |
| --- | --- | --- |
| Backend 完整回归 | backend 中 `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --tb=short -rs` | 205 passed，1 skipped |
| Frontend 完整回归 | frontend 中 `npm.cmd test -- --run` | 190 passed，28 files |
| Lint | `npm.cmd run lint` | PASS |
| Production build | `npm.cmd run build` | PASS；既有大于500kB的 bundle 提示仍存在 |
| E2E 完整回归 | `npm.cmd run e2e` | 34 passed |
| 新来源截图复验 | `npm.cmd run e2e -- lqb-monitor.spec.ts` | 2 passed |
| 真实页面 | 实际 HTTP GET，调用新适配器解析，无入库 | HTTP 200，第18届，6个有效章节 |
| 响应式 | Chrome 1440×900、390×900，阅读/筛选/来源控制、横向溢出断言和截图查看 | PASS |
| 差异格式检查 | `git diff --check` | PASS |

PostgreSQL 跳过项为原有 `tests/test_cloud_postgres.py`：未设置指向独立测试库的 `JLU_TEST_POSTGRES_URL`。没有新增或扩大 skip。

初次测试运行遇到沙箱临时目录/子进程限制，后续使用授权的正常测试环境执行；没有改动测试标准。新增详情测试的重复响应对象问题已修正为每请求独立 Response。所有最终回归结果如上。

截图位于忽略的 `frontend/test-results/lqb-{detail,source}-{1440,390}.png`，使用明确标识的测试通知和来源，不含真实用户数据。新 E2E 使用 HTTP fixture 验证界面，后端测试使用 MockTransport 与独立 SQLite 验证入库事务；不声称已观察到目标站点真实在线更新。

## 数据与交付边界

- 无新依赖、无 Schema Migration、无真实数据库清理或修复；既有 Cloud / fallback 基线保留。
- 未变更版本号；未构建或安装 Windows 新安装包，未提交、推送或发布 GitHub Release。
- 启用修改后的后端后，在“本地来源”管理 `lqb`；第一次成功检查静默建立基线，之后的有效变化才进入未读。
- 没有官方发布日期的单页更新使用检测时间参与最新排序、日期筛选和首页最近通知，仍保留 `publish_date=null`。普通通知继续按原发布日期排序和筛选。
- 关键章节消失或模板无法识别时暂停更新并保留基线，需要调整解析器后恢复；不将异常页面当成内容删除。

## 发布阻断项修复与最终回归（2026-10-08）

### 根因与修改

1. 原列表将空发布日期排在所有有日期通知之后，并在日期筛选中排除它们。`app/api/routes.py` 现在按所属 Source 的 `single_page_monitor` 类型选择检测时间；普通来源保留发布日期、NULL-last 和原次级排序。最新列表、分页和首页最近通知共享排序表达式。
2. 检测时间以数据库原有 naive UTC 保存；日期筛选按 `settings.yaml` 的 `app.timezone`（默认 Asia/Shanghai）解释，使用 UTC 下界和排他的次日本地午夜上界，覆盖毫秒及夏令时。SQLite 使用连接级纯函数换算普通发布日期午夜，PostgreSQL 使用原生 timezone 表达式，不修改数据库 Schema。单页通知的 `first_seen_at` 响应带 UTC 时区，避免客户端当作本地时间解析；普通通知响应不变。
3. `app/api/source_management.py` 的来源检查改为异步端点，继续调用现有 CrawlerManager，保持 202/409 和单任务互斥。
4. `src/hooks/useCrawlerCompletionRefresh.ts` 复用 `last_run` / 启动完成时间与 QueryClient，在新终态出现时刷新一次；不要求先看见 running。首次读到旧终态只校准来源健康状态，不刷新保留的未读页。多个观察组件共享去重标记，不新增调度或后台服务。
5. `SourcesPage.tsx` 检查成功后立即刷新状态查询，启动失败显示错误，ABORTED 静默。`CrawlerButton.tsx` 启动前确认旧运行标识，不把旧启动同步完成当作新任务完成。
6. 来源提示和 Design Contract 补充本地监控限制：需后端运行及联网；完全退出客户端和休眠期间不检查；恢复后可主动检查；离线期间出现又撤回的变化可能无法检测。

### 本轮实际修改文件

- `backend/app/api/routes.py`
- `backend/app/api/source_management.py`
- `backend/tests/test_single_page_release.py`（新增）
- `frontend/src/hooks/useCrawlerCompletionRefresh.ts`（新增）
- `frontend/src/components/layout/CrawlerButton.tsx`
- `frontend/src/components/layout/CrawlerButton.test.tsx`
- `frontend/src/pages/SourcesPage.tsx`
- `frontend/src/pages/SourcesPage.test.tsx`
- `frontend/e2e/lqb-monitor.spec.ts`
- `docs/design/design.md`
- `docs/LQB_MONITOR_REPORT.md`

### 测试与证据

先补回归再修复：修复前专项后端 7 failed / 4 passed，专项前端 7 failed / 25 passed，覆盖真实路由请求和界面状态更新。测试权限限制通过正常测试权限处理，没有删除断言、扩大 skip 或改用真实数据库。

新增后端13项：混合来源排序/分页/首页、普通日期与未知日期保持原语义、单页类型判断、日期区间上下界与微秒、夏令时、UTC 响应、Windows 默认时区数据缺失兼容、PostgreSQL SQL 编译，以及实际 HTTP API 的启动/冲突/404/停用/认证暂停/启动异常。

新增前端9项：短时成功/失败/部分失败、共享观察者去重、旧启动同步不冒充新任务完成、首次终态仅刷新健康状态、来源手动检查和失败提示、失败后恢复。完整回归中发现的首次加载额外刷新已修复，原有未读详情返回测试断言保持不变。

| 最终检查 | 实际命令（对应目录） | 结果 |
| --- | --- | --- |
| Backend | `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --tb=short -rs` | 218 passed，1 skipped |
| Frontend | `npm.cmd test -- --run` | 199 passed，28 files |
| Lint | `npm.cmd run lint` | PASS |
| Production build | `npm.cmd run build` | PASS；既有大于500kB的 bundle 提示保留 |
| E2E | `npm.cmd run e2e` | 34 passed |
| 专项前端（含原有 AppShell 阅读回归） | `npm.cmd test -- --run src/components/layout/CrawlerButton.test.tsx src/pages/SourcesPage.test.tsx src/components/layout/AppShell.test.tsx` | 47 passed |

扩展已有1440px/390px两项 E2E，验证短时解析失败、恢复健康、手动检查409反馈和本地限制提示，并检查横向溢出。新来源 E2E 的网页变化/健康状态仍使用明确的 HTTP fixture；真实来源检查端点由后端 TestClient 请求验证，不声称已验证真实网站更新或 Windows 休眠恢复。

唯一 skip 仍为原有 PostgreSQL 实机测试：未设置独立测试库 `JLU_TEST_POSTGRES_URL`。本轮只完成 PostgreSQL 查询编译检查，不声称实机或生产 Cloud 联调通过。

### 交付结论

本轮三项发布阻断问题已闭环，可以进入最终发布准备和安装验收。无 Schema Migration、无新增依赖、无真实用户数据修复或清理；既有 Cloud Worker、抓取、基线、去重和阅读模型未修改。本轮没有改版本、Git 提交/推送、创建 Release、构建安装包或安装客户端。此前实现的未提交改动全部保留。
