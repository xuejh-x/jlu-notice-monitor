# Gate 6C Round 2 Result

**PASS**

Gate 6C Round 2 — API / Query Cache Governance Audit 完成。全量枚举 query topology 与 entity-bearing caches，审计 Round 1 失效契约的完整性，逐条核对 API 响应与 TS 类型。发现并修复 3 个真实问题（read mutation 未失效 search cache、`runCrawler` 类型漂移、`SourceStatus.last_error_at` 字段名漂移）。**未做全局重构、未建 query-key factory、未引入 normalization、未改 backend。**

# Query Topology

全量 query family 清单（代码搜索得到的真实结果；app 级默认 `staleTime 30_000 / retry 1 / refetchOnWindowFocus false`）：

| Query Key | Owner | Fetch | Data type | 含 Notice snapshot | mutation 后是否可能变旧 | Invalidation |
| --- | --- | --- | --- | --- | --- | --- |
| `['notice', id]` | NoticeDetailPage | getNotice | NoticeDetail | 单实体 | 是 | `invalidateNoticeState`（favorite）；read 不失效（详情 UI 不显示 read，见 Read Contract） |
| `['notices', 'all', requestFilters]` | NoticesPage | getNotices | PaginatedNotices | 是 | 是 | `['notices']` 前缀（favorite/read/crawler 完成） |
| `['notices', 'favorites', page, pageSize]` | FavoritesPage | getNotices(favorite=true) | PaginatedNotices | 是 | 是（membership） | `['notices']` 前缀 |
| `['notices', 'competitions', category, source, minScore, deadlineStatus, sort, page, pageSize]` | CompetitionsPage | getNotices | PaginatedNotices | 是 | 是 | `['notices']` 前缀 |
| `['notices', 'feed', category, keyword, page, pageSize]` | FeedPage | getNotices | PaginatedNotices | 是 | 是 | `['notices']` 前缀 |
| `['notices', 'deadlines', days]` | DeadlinesPage | getDeadlineNotices | Notice[] | 是 | 是 | `['notices']` 前缀 |
| `['notices', 'today']` | TodayPage | getTodayNotices | Notice[] | 是 | 是 | `['notices']` 前缀 |
| `['notices', 'important', threshold]` | DashboardPage | getImportantNotices | Notice[] | 是 | 是 | `['notices']` 前缀 |
| `['dashboard']` | DashboardPage | getDashboard | DashboardData（unread 计数 + recent_notices + source_status） | 是（recent_notices） | 是 | `invalidateNoticeState` + auto-read + CrawlerButton |
| `['search', debouncedKeyword]` | SearchDialog | searchNotices | PaginatedNotices | 是（结果行显示未读点，无收藏星标） | 是（仅 read 状态） | **Round 2 新增：auto-read 失效 `['search']`** |
| `['sources']` | SourcesPage | getSources | Source[] | 否 | 否 | CrawlerButton 完成后失效 |
| `['crawler']` | AppShell / CrawlerButton | getCrawlerStatus | CrawlerStatus | 否 | 否 | 自身 refetchInterval（60s / 追踪中 1.5s） |

Mutation 全量：`setNoticeFavorite`（NoticeCard、NoticeDetailPage，→ `invalidateNoticeState`）、`setNoticeRead`（仅 NoticeDetailPage auto-read）、`runCrawler`（CrawlerButton，完成后失效 `['dashboard']`+`['notices']`+`['sources']`）。

# Entity Cache Map

一个 Notice entity 的 snapshot 可能存在于 **10 个 cache family**：7 个列表 family（all/favorites/competitions/feed/deadlines/today/important）+ `['dashboard']`（其 `recent_notices` 直接缓存 backend `_serialize_notice` 序列化的完整 Notice 快照，Round 1 已证明其受 favorite mutation 影响，属 entity-bearing）+ `['notice', id]` 详情 + `['search', keyword]` 搜索结果。它们全部被 `['notices']` 前缀 + `['notice',id]` + `['dashboard']` + `['search']` 四个 targeted prefix 覆盖（TanStack Query 前缀语义）。collection pages 复用 `['notices', variant, params]` 同一 family，不算独立 cache 体系。

# Round-1 Invalidation Review

- `['notice', id]` + `['notices']` + `['dashboard']`（`invalidateNoticeState`）：对 **favorite** 完整（Round 1 已有行为测试证明 Card→detail、Detail→dashboard refetch）。
- **`['search', keyword]` 审计结论：存在真实 gap，已修。** SearchResultRow 渲染 `is_read`（未读点 + `sr-only` 已读/未读），但不渲染 `is_favorite`。用户流：搜索 → 打开结果（auto-read POST /read）→ 返回 → 30s 内重开 Dialog（keyword 保留、query 仍 fresh）→ 显示缓存的旧「未读」。favorite mutation 不影响 search UI（无星标），故 favorite 不失效 search。
- 修复方式：auto-read 成功后增加 `invalidateQueries({ queryKey: ['search'] })`（前缀覆盖全部 keyword entry；active observer 立即 refetch，无 active observer 时标记 stale、下次 reopen 时 refetch）。未对 favorite 路径加 `['search']`（避免无意义失效）。

# Read / Unread Contract

- **触发点**：只有 NoticeDetailPage auto-read（打开未读通知，`Set<number>` 每 id 恰好一次）。**UI 不提供 manual mark unread / mark read 按钮**；backend 的 `/unread` endpoint 存在但无前端消费者（不测试不存在的 UI）。
- 数据链：auto-read → `POST /api/notices/{id}/read` → backend 返回 `{"notice_id", "is_read": true}`（动态键，Round 1 已按真实 payload 定型）→ 失效 `['notices']` + `['dashboard']` + `['search']`（Round 2 新增）。
- 受影响视图：NoticeCard（各列表）、unread 过滤列表（`read=false` membership——`['notices']` 前缀覆盖）、Dashboard unread 计数与 recent_notices、Search 结果未读点。
- `['notice', id]` 不失效：详情页不显示 read 状态，`markedIds` 防重复 POST，无用户可见问题（保留 Round 1 决定）。

# API Contract Audit

逐条核对（backend 实际序列化 vs 前端 TS 类型）：

| Endpoint | 结论 |
| --- | --- |
| GET /notices /notices/today /notices/deadlines /notices/important /search | ✅ 类型与 payload 一致 |
| GET /notices/{id}（detail，含 attachments/updates/sources） | ✅ 一致（updates 为 `Record<string, unknown>[]`，弱类型但如实） |
| POST read/unread/favorite/unfavorite/archive/unarchive | ✅ Round 1 已修正为 `NoticeStateResult`（动态键 union），本轮浏览器又复证 `{"notice_id":11,"is_read":false}` |
| GET /sources | ✅ `Source` 与 backend `sources()` 全字段一致 |
| GET /dashboard | ⚠️ **`SourceStatus.last_error_at` 漂移**：backend 发 `last_error`（另有 `last_checked_at`）；前端声明的 `last_error_at` 不存在。无消费者读取（Dashboard 只读 `.status`），latent。→ 已修正为 `last_checked_at? / last_success_at? / last_error?` |
| GET /crawler/status | ✅ `CrawlerStatus` 与 `crawler_manager.status()` 全字段一致 |
| POST /crawler/run | ⚠️ **`runCrawler` 漂移**：前端声明 `{ message?: string }`，backend 实际返回 `{"status": "started"}`。结果未被消费，latent。→ 已修正为 `{ status: string }` |

# Query-Key Governance

**不需要 query-key factory。** 证据：

- 全部 Notice 列表 family 遵循统一形状 `['notices', <variant>, <params>]`，前缀失效语义明确；无“同一资源不同 key shape”。
- `NoticesPage` 的 `requestFilters` 虽每次 render 新建对象，但字段为固定字面量键序 + 原始值，TanStack Query 结构哈希稳定（`queryKeyHashFn` = 稳定序列化），不会造成 key churn 或重复请求。
- 未发现 key 拼写分散 / 漏失效 / params 不稳定导致的 correctness risk。Round 1 的 `invalidateNoticeState` 已是 Notice domain 的最小统一入口，再抽象 key factory 只会增加间接层。

# Normalization Decision

**Not justified.** 理由：单用户本地应用、76 条通知；TanStack Query server-state + 4 个 targeted prefix 失效已完整覆盖 10 个 entity-bearing family（Round 2 补齐 `['search']` 后无缺口）；无 duplicated-snapshot 导致的 consistency bug；无失效不可维护的问题。duplicated snapshot 本身是 TanStack Query 的常态，不是 normalization 的理由。

# Problems Found

1. **auto-read 不失效 `['search']`**
   - problem：搜索结果行渲染未读点；打开通知 auto-read 后，30s 内重开 Dialog 显示缓存的旧「未读」。
   - impact：用户可见 stale read 状态（最长 30s）。
   - reproduction：`POST /unread` 置通知 11 未读 → 搜索 CSP → 结果行「未读」→ 点击打开（auto-read）→ 重开搜索 → 行仍「未读」（修复前）；修复后「已读」（本轮浏览器实测）。
   - root cause：auto-read 失效集只含 `['notices']`+`['dashboard']`，漏 read 状态可见的 search family。

2. **`runCrawler` 返回类型漂移**
   - problem：`apiRequest<{ message?: string }>` vs backend `{"status": "started"}`。
   - impact：latent（结果未消费）；未来消费者会读错字段。
   - root cause：类型从未按真实响应修正（F-008 同类）。

3. **`SourceStatus.last_error_at` 字段名漂移**
   - problem：backend 发 `last_error` / `last_checked_at`，前端声明 `last_error_at`。
   - impact：latent（Dashboard 只读 `.status`）。
   - root cause：Dashboard 内嵌 `/api/sources` 序列化时未对齐字段名。

# Changes

- `frontend/src/pages/NoticeDetailPage.tsx`：auto-read 成功后新增 `invalidateQueries({ queryKey: ['search'] })`（effect 的 POST-once 语义未变）。
- `frontend/src/utils/noticeCache.ts`：docstring 明确 search 为 read-only 展示、由 read 路径失效。
- `frontend/src/api/crawler.ts`：`runCrawler` 返回类型 `{ status: string }`。
- `frontend/src/types/index.ts`：`SourceStatus` 字段对齐真实 payload（`last_checked_at?/last_success_at?/last_error?`）。
- 无其他生产修改；backend 未改；无新依赖。

# Regression Tests

新增 3 项（108 → 111，25 files）：

- `NoticeDetailPage.test.tsx`（+1）：auto-read 后，挂载中的 `['search','kw']` observer 恰好 refetch（GET 1→2），锁定 read→search 失效契约。
- `FavoritesPage.test.tsx`（新增，1）：`['notices']` 前缀失效使挂载中的 favorites 列表 refetch（unfavorite → 集合消失的 cache 层契约）。
- `api/crawler.test.ts`（新增，1）：`runCrawler` POST endpoint + 解析真实 `{status:'started'}` payload。

未删除、skip、todo 或弱化任何既有测试。

# Browser Verification

方法：headless Chrome（CDP，独立临时 profile，端口 9339）+ 本轮自启 Vite 5173（PID 44116，验证后停止释放）+ 既有后端 8000（未终止）。真实数据 notice 11（原始 `is_read=true`，经 `POST /unread` 临时置未读）。4/4 通过：

| 步骤 | 结果 |
| --- | --- |
| `/notices?read=0`（unread 过滤） | 含 notice 11（membership） |
| Ctrl+K 搜索 CSP | 结果行 `sr-only` = 未读 |
| 点击结果打开详情（auto-read）→ 重开搜索 | 结果行 = 已读（`['search']` 失效生效；修复前 30s 内显示 stale 未读） |
| 重新加载 `/notices?read=0` | notice 11 已从 unread 过滤列表消失（read 后 membership） |

验证后确认 `GET /api/notices/11` 的 `is_read=true`——auto-read 自动恢复原始状态，无数据污染（未需显式恢复）。

# Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 25 files / 111 tests（108 → 111） |
| `npm run lint` | PASS — 0 errors |
| `npm run build` | PASS — 2789 modules |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 tests |

（沙箱拦截原生子进程与原生 Tailwind oxide 加载，按既有先例以 `danger-full-access` 重跑；未改项目配置。）

# Files Changed

- `frontend/src/pages/NoticeDetailPage.tsx`（auto-read 失效 `['search']`）
- `frontend/src/pages/NoticeDetailPage.test.tsx`（+1 read→search 测试）
- `frontend/src/utils/noticeCache.ts`（docstring 契约说明）
- `frontend/src/api/crawler.ts`（`runCrawler` 类型修正）
- `frontend/src/api/crawler.test.ts`（新增）
- `frontend/src/types/index.ts`（`SourceStatus` 字段对齐）
- `frontend/src/pages/FavoritesPage.test.tsx`（新增）
- `docs/GATE_6C_R2_REPORT.md`（本报告）

# Preserved Behavior

全部 unchanged：

- backend endpoints/schema；auto-read `Set<number>` 每 id 恰好一次的语义（仅扩展缓存失效）。
- SearchDialog concurrency contract 与 300ms debounce。
- Settings contract、theme、URL schema、routes、error taxonomy。
- UI design、responsive、accessibility、Tauri、deployment。
- Round 1 的 favorite mutation contract 与 `invalidateNoticeState` 权威失效集。

# Deferred

- Archive / unarchive 前端消费（backend capability exists, no frontend consumer）。
- mutation 返回 payload 的 UI 消费（server-confirmed + invalidate/refetch 已正确，无必要）。
- 大规模缓存策略调整（staleTime/gcTime 细分）——无真实问题，不调整。

# Recommended Next Gate

治理审计已闭环（topology 完整、失效契约完整、类型漂移清零、normalization 明确不需要）。不再预设 Gate 6C Round 3；建议进入按 roadmap 的下一个 Gate（如 Gate 7 — Quality / E2E / CI，或用户指定的新目标）。
