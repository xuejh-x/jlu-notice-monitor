# Gate 1.5：P1 Remediation Planning

日期：2026-08-30
范围：本文件只确认 Gate 1 的 P1、记录最小修复设计与实施顺序。未修改任何生产代码、后端行为、数据库 schema、crawler 或 UI 视觉设计。

## Executive Summary

六个 P1 均已再次确认。它们可分为三条相互关联的链路：

1. 前后端契约：附件字段与错误分类没有在前端被可靠建模。
2. 查询状态：请求没有消费 TanStack Query 的 AbortSignal；列表状态没有以 URL 为唯一来源。
3. 回归防护：缺少前端测试，使上述契约和生命周期行为无法稳定验证。

建议不重写 API 层，也不增加状态管理库。采用小步方案：保留现有 API 路径和 TanStack Query，扩展单一 apiRequest 入口；将 NoticesPage 的可见筛选状态规范化到 URL；用 Vitest + React Testing Library 建立最小回归网。

## Confirmed P1 Findings

### P1-01 Attachment DTO mismatch

#### Current flow

Backend Attachment model
→ backend app/api/routes.py _serialize_notice(detailed=True)
→ GET /api/notices/:id response
→ frontend NoticeDetail/Attachment DTO
→ getNotice()
→ NoticeDetailPage attachment rendering

#### Evidence and root cause

backend/app/api/routes.py 第 66–69 行序列化附件为 filename、url、type。真实 GET /api/notices/13 返回的前两项为：

- filename: 25级唐班.xlsx, type: xlsx
- filename: 24级网安.xlsx, type: xlsx

frontend/src/types/index.ts 中 Attachment 却声明 name、title、file_type；frontend/src/pages/NoticeDetailPage.tsx 读取 a.name ?? a.title ?? 附件。因此，真实 notice #13 的八个附件都只显示“附件”。

根因是前端 detail DTO 没有跟随已存在的后端序列化契约，不是后端数据缺失，也不是数据库问题。

#### Files involved

- backend/app/api/routes.py — 当前正确的响应定义；P1 不应修改。
- frontend/src/types/index.ts — Attachment DTO。
- frontend/src/api/notices.ts — getNotice 的类型出口。
- frontend/src/pages/NoticeDetailPage.tsx — 名称与文件类型的展示消费点。
- 将新增的前端测试文件 — 契约回归断言。

#### Impact, risk, dependency

影响范围仅为通知详情附件区。修复风险低，不影响 API 形状、下载链接或 Tauri opener 行为。它依赖 P1-06 提供测试执行环境；与 P1-02/P1-04 共享 API 契约思路，但实现上可独立。

### P1-02 Error contract / 404 handling

#### Current flow

FastAPI HTTPException(404, detail)
→ JSON response { detail: Notice not found }
→ apiRequest catches non-2xx
→ ApiError(message, status)
→ React Query isError
→ ErrorState
→ 固定标题“无法连接本地服务”

#### Evidence and root cause

backend/app/api/routes.py 第 93–97 行在不存在的 notice 时抛出 HTTP 404。真实 GET /api/notices/999999 得到 HTTP 404 和 JSON { detail: Notice not found }。

frontend/src/api/client.ts 对 fetch 抛出的网络异常与所有非 2xx 都只生成带 message/status 的 ApiError。frontend/src/components/ui/Feedback.tsx 的 ErrorState 对所有失败固定显示“无法连接本地服务”。因此，存在资源与后端离线在 UI 中被混为一类。

根因是 ApiError 没有可供界面可靠消费的错误类别，且 ErrorState 把基础设施文案硬编码为通用错误标题。

#### Files involved

- backend/app/api/routes.py — 当前 404 契约；不改。
- frontend/src/api/client.ts — 统一错误分类入口。
- frontend/src/components/ui/Feedback.tsx — 通用错误呈现。
- frontend/src/pages/NoticeDetailPage.tsx — 详情页的 NOT_FOUND 文案/返回列表动作。
- 其他现有 ErrorState 消费页面 — 应通过共用组件获得正确的网络/超时/HTTP 文案，不做页面重构。
- 前端测试文件。

#### Impact, risk, dependency

错误组件由多个页面共享，属于中等回归风险；必须保持“重新连接”在 NETWORK_ERROR/TIMEOUT 的现有行为可用。它与 P1-04 共用 apiRequest 的错误模型，应在同一实施批次完成。404 不等于 backend offline 是验收不可妥协项。

### P1-03 URL state

#### Current flow

NoticesPage useState
→ debouncedKeyword / local filters / local page
→ React Query queryKey
→ getNotices filters
→ GET /api/notices query string

#### Evidence and root cause

frontend/src/pages/NoticesPage.tsx 将 keyword、category、source、minScore、deadlineStatus、dateFrom、read、favorite、page 都保存为本地 state。浏览器实际选择 read=unread 后，地址仍为 /notices，刷新/分享/后退无法恢复上下文。TanStack Query queryKey 虽然包含状态，却不代表 URL 状态。

根因是路由只管理 pathname，没有为列表查询定义 search-param schema。

#### Files involved

- frontend/src/pages/NoticesPage.tsx — P1 唯一必须改变的可见列表状态所有者。
- frontend/src/api/notices.ts — 可继续复用现有 NoticeFilters/queryString，无须重写。
- frontend/src/types/index.ts — 若提取 URL 解析 helper，需要复用 NoticeFilters。
- 可新增 frontend/src/utils/noticeSearchParams.ts 或同等小型纯函数模块。
- 前端测试文件。

#### Impact, risk, dependency

这是中等风险行为修改：将影响刷新、分享和 Back/Forward，但目标是修复这些行为，不能改变实际筛选语义。它不依赖后端改动，建议在 P1-02/P1-04 的共享客户端稳定后实施，并以 P1-06 测试覆盖。CompetitionsPage、FeedPage、FavoritesPage、TrainingPage、DeadlinesPage 不纳入本 P1，避免将 URL-state 重构扩大到所有页面。

### P1-04 Request lifecycle

#### Current flow

TanStack Query useQuery queryFn
→ API wrapper such as getNotices/getNotice
→ apiRequest(path, init)
→ fetch without signal or timeout

#### Evidence and root cause

frontend/src/api/client.ts 只转发 RequestInit，没有超时、AbortController 或错误区分。现有 useQuery queryFn 均不接收 TanStack Query 的 signal，因此 query 在失活/参数变更后不会将取消信号实际传给 fetch。TanStack Query v5 的 QueryFunctionContext 会提供 signal；只有由 queryFn 继续传入 fetch，才会消费这一取消能力。

根因是统一 client 接口没有 signal/timeout 语义，页面 queryFn 也没有把 QueryFunctionContext.signal 传下去。

#### Files involved

- frontend/src/api/client.ts — timeout、外部 signal 合并、分类错误。
- frontend/src/api/notices.ts、dashboard.ts、sources.ts、crawler.ts — 仅增加可选请求选项并透传。
- 所有使用 useQuery 的现有页面/组件 — queryFn 接收 { signal } 并将其传给对应 API 函数；不改变 queryKey、缓存或 UI。
- frontend/src/components/search/SearchDialog.tsx — 搜索请求必须消费 signal。
- 前端测试文件。

#### Impact, risk, dependency

这是六项中影响面最大的一项：共享 client 和所有查询调用点都会触及。风险中等，但不需要后端变更。P1-02 与它必须一起设计，因为 timeout、abort、network、HTTP 的区分来自同一 client。Mutation 不应因普通页面导航自动取消；它们只使用同一超时和 HTTP 分类，不消费 TanStack Query query signal。

### P1-05 Notice detail auto-read lifecycle

#### Current flow

Route /notices/:id
→ NoticeDetailPage stays mounted for same route element
→ id changes from useParams()
→ query key changes and detail refetches
→ useEffect sees marked.current
→ POST read may be skipped

#### Evidence and root cause

frontend/src/pages/NoticeDetailPage.tsx 初始化 const marked = useRef(false)。effect 的依赖包含 q.data、id、client，但 marked.current 在第一次自动标记时设为 true，未在 id 变化时重置。React Router 对同一路由元素参数变化可以复用该组件实例，因此从 /notices/A 切换到 /notices/B 时，B 可能被旧 ref 阻止自动标已读。

根因是一次性副作用的 guard 以组件实例而非 notice id 为作用域。

#### Files involved

- frontend/src/pages/NoticeDetailPage.tsx。
- frontend/src/api/notices.ts — 仅在 P1-04 新请求选项透传时涉及。
- 前端测试文件。

#### Impact, risk, dependency

修复代码小，但已读状态是用户数据，验证风险中等。它不依赖 URL state 或后端 schema；建议在共享请求错误模型后单独完成，测试必须模拟从 A 到 B 的路由参数切换。保留现有“自动标记失败静默”的产品行为，除非后续需求明确改变。

### P1-06 Frontend regression coverage

#### Current flow

package.json 只有 dev/build/lint/preview/tauri scripts。
→ 没有 test script、Vitest、DOM test environment、React Testing Library 或 frontend test files。
→ Gate 1 的关键行为只能手工验证。

#### Evidence and root cause

frontend/package.json 和 frontend 目录均未发现 Vitest、React Testing Library、MSW、Playwright 配置或 .test/.spec 文件。后端 pytest 通过 43 项测试，但不能覆盖 React 组件、浏览器 URL 或 fetch 分类。

根因不是单个 bug，而是前端项目没有最小测试执行和测试边界。

#### Files involved

- frontend/package.json、frontend/package-lock.json。
- frontend/vite.config.ts 或单独 vitest.config.ts。
- frontend/src/test/setup.ts。
- frontend/src/**/*.test.ts(x)。
- 仅在后续确有 E2E 需求时才考虑 playwright.config.ts；本 P1 不创建。

#### Impact, risk, dependency

引入少量 devDependencies 与脚本是结构性变更，但不影响生产 bundle。它应首先搭好基本支架，并伴随其余 P1 逐项加入测试，而非在所有修复后补测。

## Root Cause Analysis

| 共享根因 | 关联 P1 | 结论 |
| --- | --- | --- |
| 前端边界契约不显式 | P1-01、P1-02、P1-04 | Attachment DTO、HTTP error 和 fetch 终止语义都在 apiRequest/DTO 边界缺少稳定表示 |
| 本地状态不是可恢复状态 | P1-03、P1-05 | 列表状态与 auto-read guard 都以组件实例/local state 表示，而非以路由参数或资源 id 表示 |
| 缺少自动化回归网 | P1-01 至 P1-05 | 任何契约/生命周期修复都需要 P1-06 作为持续验证能力 |

后端不是 P1 根因：附件 JSON、404 状态与 detail 字段均已按当前后端实现返回。数据库 schema、crawler 和 API path 均不需要变更。

## Dependency Graph

P1-06 测试支架
→ P1-02/P1-04 统一 ApiError 与请求生命周期
→ P1-01 附件 DTO 与 P1-02 404 UI 消费
→ P1-05 详情 auto-read 生命周期
→ P1-03 Notices URL state
→ 全量回归验证

其中 P1-01 与 P1-05 在代码上可并行，但建议在共享测试工具可用后分别落地。P1-03 与 P1-05 不互相依赖。P1-02 与 P1-04 必须同批次，避免先改 UI 分类、后改 client 分类而产生短期双模型。

## Recommended Implementation Order

### Step 1 — 建立最小测试支架

原因：先建立可执行断言，后续每步都能验证且容易回滚。
依赖：无。
计划文件：frontend/package.json、package-lock.json、Vitest 配置、测试 setup、首批 test 文件。
验证：npm run test 能在一次运行模式执行；不影响 npm run lint 与 npm run build。
PASS：测试环境能渲染 React、隔离 fetch、创建 QueryClient，并通过至少一个 API client 测试和一个组件渲染测试。

### Step 2 — 统一前端错误与请求生命周期

原因：P1-02 和 P1-04 共享唯一 client 边界，必须先定错误可判别性。
依赖：Step 1。
计划文件：src/api/client.ts；src/api/notices.ts、dashboard.ts、sources.ts、crawler.ts；所有 useQuery 调用点；SearchDialog。
验证：单测网络失败、超时、HTTP 404、其他 HTTP、abort；确认 queryFn 消费 signal。
PASS：错误对象有稳定 kind；timeout 和 caller abort 可区分；abort 不被 UI 作为 backend offline；现有 API path/method/query 参数不变。

### Step 3 — 修复附件 DTO 与 404 消费层

原因：这两项都消费 Step 2 提供的前端契约，但不改变后端。
依赖：Step 2。
计划文件：src/types/index.ts、src/pages/NoticeDetailPage.tsx、src/components/ui/Feedback.tsx，以及必要测试。
验证：mock/真实契约中的 filename 显示；404 显示“通知不存在”或等价资源文案；NETWORK_ERROR 仍显示连接问题。
PASS：详情附件不再回退为“附件”；404 与 backend offline 有不同可见文案和恢复动作。

### Step 4 — 修复详情 auto-read 的资源生命周期

原因：范围小、与 URL schema 无关，可在 client 行为稳定后隔离验证。
依赖：Step 1；若 Step 2 改动 getNotice/setNoticeRead 签名，则依赖 Step 2。
计划文件：src/pages/NoticeDetailPage.tsx、相应测试。
验证：在同一组件实例从 /notices/A 切换 /notices/B，两个 unread notice 都各调用一次 read；已读 notice 不发 read。
PASS：副作用 guard 的作用域为 notice id；不会重复标记同一 id，也不会遗漏下一个 id。

### Step 5 — 将 NoticesPage 状态作为 URL state

原因：这是局部但交互敏感的变更，放在 client/错误稳定后实施，并用测试覆盖 Back/Forward。
依赖：Step 1；复用 Step 2 的 signal 流；不依赖 Step 3/4。
计划文件：src/pages/NoticesPage.tsx、可选 src/utils/noticeSearchParams.ts、测试。
验证：深链接、刷新、Back/Forward、无效参数、筛选变更重置 page、搜索 debounce。
PASS：URL 是 NoticesPage 筛选/页码的唯一持久来源；React Query queryKey 从标准化 URL state 生成；不存在双份保存的筛选 state。

### Step 6 — 扩展回归覆盖并执行质量关卡

原因：在每步已有测试的基础上补齐矩阵，避免“安装了测试但未保护 P1”。
依赖：Step 2–5。
计划文件：测试文件；可能只补充 npm scripts。
验证：npm run test、npm run lint、npm run build、backend pytest。
PASS：本计划的 Regression Test Plan 全部通过；现有 API、视觉布局和 crawler 行为无回归。

## File Impact Matrix

| 文件 | Step | 变更类型 | P1 必要性 |
| --- | --- | --- | --- |
| frontend/src/api/client.ts | 2 | 小型统一 client 扩展 | 必要 |
| frontend/src/api/notices.ts | 2 | 可选 request options 透传 | 必要 |
| frontend/src/api/dashboard.ts | 2 | signal 透传 | 必要，以实现一致查询取消 |
| frontend/src/api/sources.ts | 2 | signal 透传 | 必要 |
| frontend/src/api/crawler.ts | 2 | status query signal 透传；mutation 保持非取消 | 必要 |
| frontend/src/pages/*.tsx 与 SearchDialog | 2 | queryFn 使用 signal | 必要 |
| frontend/src/types/index.ts | 3 | Attachment 契约对齐 | 必要 |
| frontend/src/pages/NoticeDetailPage.tsx | 3、4 | 附件呈现、404、auto-read guard | 必要 |
| frontend/src/components/ui/Feedback.tsx | 3 | 基于错误类别呈现 | 必要 |
| frontend/src/pages/NoticesPage.tsx | 5 | URL state | 必要 |
| frontend/src/utils/noticeSearchParams.ts | 5 | 可测试的 parse/serialize helper | 建议新增 |
| frontend/package.json、package-lock.json | 1 | 最小测试依赖/scripts | 必要 |
| frontend/vite.config.ts 或 vitest.config.ts | 1 | 测试配置 | 必要 |
| frontend/src/test/*、*.test.ts(x) | 1–6 | 回归覆盖 | 必要 |
| backend/app/api/routes.py | 无 | 不修改 | 明确排除 |

## API / DTO Contract Plan

### 保持的后端契约

- GET /api/notices/:id 继续返回 NoticeDetail。
- Attachment 字段保持 filename、url、type。
- 404 继续返回 HTTP 404 与 FastAPI detail。
- POST read/unread/favorite/unfavorite 继续返回 { notice_id, is_read/is_favorite }。
- 不新增 API endpoint，不改 schema，不改 crawler。

### P1 修复必要修改

- 前端 Attachment DTO 改为 filename、url、type，或在唯一前端映射层明确将 filename 映射为 UI name；推荐直接与后端字段同名以减少映射漂移。
- 为请求失败定义最小可区分字段，例如 kind、status、message；保持 ApiError 作为单一 public error class。
- API wrapper 增加可选 RequestOptions（signal、timeoutMs），不改变现有调用者默认行为和 API URL。

### 未来可顺带优化，但当前不应做

- favorite/read mutation 的返回类型确实与后端状态 payload 不一致，但当前调用者不消费返回值。它是 P2，应保留到后续 contract cleanup。
- Notice/NoticeDetail 的完整运行时 schema 验证、生成式 OpenAPI client、后端 Pydantic response_model 改造均不属于 P1。
- updates 的精确定义、Category union 收紧、strict TypeScript 迁移仍是 P2。

## Error Handling Plan

### 最小错误模型

| kind | 触发条件 | UI 默认策略 |
| --- | --- | --- |
| NETWORK_ERROR | fetch 因连接/DNS/CORS 等网络错误失败，且不是 abort/timeout | 显示后端不可连接与重试 |
| TIMEOUT | client 自己的 timeout controller 触发 | 显示请求超时与重试 |
| ABORTED | TanStack Query signal 或调用者 signal 中止，且非 timeout | 不显示 toast/error；交由下一次有效查询 |
| NOT_FOUND | HTTP 404 | 详情页显示通知不存在并提供返回通知列表 |
| HTTP_ERROR | 其他非 2xx | 显示服务请求失败及后端 detail（若安全可用），提供重试 |

实现不需要复杂 error framework：ApiError 扩展 kind 和 status 即可。client 内部创建 timeout AbortController，将外部 signal 的 abort 事件转发/合并；finally 清理 timer 和 listener。应优先使用由本 client 控制的 timeout 标记区分 TIMEOUT 与 ABORTED，而不是仅依赖浏览器 AbortError 文案。

TanStack Query 的 queryFn 改为接收 { signal } 并透传到 API wrapper。Mutation 使用相同 timeout/error 分类，但不绑定 query signal，避免导航取消已经开始的 read/favorite/crawler 行为。

## URL State Plan

本 P1 仅覆盖 NoticesPage 已存在的列表控件，不把全局 SearchDialog、竞赛页、收藏页、deadline tab 或设置页重构为 URL state。

### URL schema

| 当前 UI state | URL 参数 | 缺省时含义 |
| --- | --- | --- |
| keyword | q | 无关键词 |
| category | category | 全部分类 |
| source | source | 全部来源 |
| minScore | min_score | 不限优先级 |
| dateFrom | date_from | 不限起始日期 |
| deadlineStatus | deadline_status | 全部截止状态 |
| read | read=1 或 read=0 | 全部阅读状态 |
| favorite | favorite=1 或 favorite=0 | 全部收藏状态 |
| page | page | 1 |
| pageSize | page_size | 读取现有保存设置，或项目默认 20 |

NoticesPage 当前没有 sort 控件；尽管 NoticeFilters 支持 sort，本 P1 不把不存在的 UI 状态写入 URL。

示例：/notices?q=CTF&source=cse&min_score=70&read=0&page=2&page_size=20

### 规范化规则

- 默认/空值从 URL 移除，避免无意义长链接；page=1 移除。
- 解析只接受现有 UI 可选值：已知 category/source/deadline 状态，min_score 为 70/80/90，read/favorite 为 1/0，page 为正整数，page_size 为 10/20/50。
- 非法参数忽略并回落到缺省值；不会发出非法后端请求。
- 任一筛选、q 或 page_size 变化都重置 page 为 1；只改 page 时不重置。
- 输入框使用临时 qDraft；300ms debounce 后以 replace 更新 q，避免每个字符生成 history entry。下拉筛选和分页使用正常导航更新，因此 Back/Forward 恢复先前的标准化参数。
- TanStack Query queryKey 只从标准化后的 URL state 生成；getNotices 也从同一对象生成，避免 URL、local state、queryKey 三份真相。
- 保存的 pageSize 只在 page_size 缺席时作为初始默认值；明确 URL 的 page_size 优先。此 P1 不修复设置 store 非响应式问题。

## Request Lifecycle Plan

1. timeout 放在 apiRequest 内部，作为所有 HTTP 调用的一致保护；默认值在一个常量中定义，单测覆盖，必要时允许调用方覆盖。
2. API 函数以可选 options 接收 signal/timeoutMs，再传入 apiRequest。
3. useQuery 的 queryFn 消费 TanStack Query signal；这使 query key 变化、失活或卸载可以终止正在进行的 fetch。
4. timeout 使用 client 自己创建的 controller；外部 signal 触发时标记 ABORTED，timeout 触发时标记 TIMEOUT。
5. ABORTED 不触发 toast，也不呈现为失败界面；TanStack Query 的下一有效 query 负责 UI。TIMEOUT、NETWORK_ERROR、HTTP_ERROR 保持错误/重试路径。
6. backend offline 仅指 NETWORK_ERROR：无法建立/维持到 VITE_API_BASE_URL 的请求；HTTP 404/409/5xx 都不是 offline。
7. HTTP 404 映射 NOT_FOUND；其他非 2xx 映射 HTTP_ERROR，并保留 status 供特定页面决定文案。

这是一层小型扩展，不建立新的请求库、不替换 fetch、不重写已有 endpoint wrappers。

## Regression Test Plan

### 测试工具选择

- 采用 Vitest：项目已经使用 Vite，配置和 TypeScript 转换可复用。
- 采用 React Testing Library 加 jsdom：覆盖组件、路由、可访问名称和用户交互。
- 采用 vi.stubGlobal 或等价 fetch mock 作为第一阶段 HTTP 边界；当前 endpoint 数量有限，MSW 不是 P1 必需依赖。
- 暂不引入 Playwright：本项目已有真实手工浏览器截图，P1 的关键分支可由 unit/integration 覆盖；等 Gate 2 完成后再根据跨浏览器/真实导航需求判断。
- 暂不引入 MSW：若后续 mock 路由/handler 大量重复，再在单独 Gate 评估。

### 必测用例

| Area | 最小用例 |
| --- | --- |
| API / DTO | getNotice 使用 filename/type 响应；详情渲染真实附件 filename |
| Errors | 网络失败→NETWORK_ERROR；timeout→TIMEOUT；外部 abort→ABORTED；404→NOT_FOUND；500→HTTP_ERROR |
| Error UI | 404 详情不显示 backend offline；网络失败仍显示连接错误与 retry |
| URL state | /notices?q=CTF&source=cse&page=2 恢复控件与请求；筛选变更重置 page；刷新保持；Back/Forward 恢复；非法参数回落 |
| Request lifecycle | queryFn 将 signal 传给 fetch；abort 不产生 user-visible error；timeout 清理 timer |
| Detail lifecycle | 从 /notices/A 切换 /notices/B；每个 unread id 发一次 read；已读不发 |
| Non-regression | npm run lint、npm run build、backend pytest 继续通过 |

测试不调用真实外部链接、crawler 或生产数据写操作。read/favorite 仅在 mock 层验证。

## Per-step Acceptance Criteria

| Step | PASS 条件 |
| --- | --- |
| 1 | npm run test 可运行；React/Query/router 测试基线通过 |
| 2 | 所有 queryFn 接入 signal；五类错误可单测区分；API 路径/方法未变 |
| 3 | attachment filename 可见；404 与 offline 文案/动作可区分 |
| 4 | A→B 不漏标；同一 id 不重复标；已读不请求 |
| 5 | URL 成为 NoticesPage 持久状态来源；默认值、非法值、分页和 debounce 均符合 schema |
| 6 | 计划内测试、lint、build、backend pytest 全通过；真实浏览器复查核心路径 |

## Risks / Rollback Notes

| 风险 | 控制措施 | 回滚方式 |
| --- | --- | --- |
| 共享 client 改动影响所有 query | 每个 error kind 与 signal 行为先单测；逐个 queryFn 迁移 | 还原 apiRequest/options 与迁移调用点；后端无变更 |
| URL 参数导致不一致或 history 噪声 | 纯 parse/serialize helper；默认值规范化；q 使用 replace | 还原 NoticesPage URL helper，恢复原 local state |
| auto-read 重复或遗漏 | Mock A→B 路由测试；不改后端 endpoint | 还原详情 guard 的局部改动 |
| 新测试依赖影响构建 | devDependency 限制；保持 build script 不变 | 回滚 package/config/test 文件 |
| ErrorState 共享组件改变多页文案 | 在 detail 优先测试 NOT_FOUND，network/timeout 维持重试语义 | 还原错误展示映射；API 无变更 |

每个实施提交应限制在一个步骤内，先通过对应 acceptance 再进入下一步。不得删除或覆盖当前 dirty worktree 中的用户修改。

## Out-of-scope Items

以下保留到后续 Gate，不应借 P1 顺带实施：

- favorite/read mutation response type 对齐（P2，当前消费者未使用返回值）。
- Dashboard important query 的独立错误状态（P2）。
- settings 的响应式 store（P2）。
- strict TypeScript 迁移、完整运行时 schema 验证、生成式 client（P2）。
- SearchDialog 自身错误 UI（P3）和全局搜索的 URL 重设计。
- crawler health pending 文案（P3）。
- 所有 Feed/Competitions/Favorites/Deadlines 的 URL-state 迁移。
- 样式 token、组件重构、视觉设计、响应式重排。
- Redux、Zustand、路由器替换、TanStack Query 替换、后端 API/schema/crawler 改造。
- Playwright、MSW 和 CI 的引入，除非后续单独审批。

## Official References

- TanStack Query Query Functions：queryFn context 提供 AbortSignal，可用于 query cancellation。
- Vitest Getting Started：可复用 Vite 配置并以 npm script 运行。
- 以上资料仅用于后续实现阶段的技术选择，不构成本阶段依赖安装或代码变更。

