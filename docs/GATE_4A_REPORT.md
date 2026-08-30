# Gate 4A Result

**PASS**

Gate 4A — Notice List + Filters 完成。将 NoticesPage / Notice List 重构为可扫读的“通知分流界面”，落实 Design Contract 的信息权重（title → decision cluster → context cluster → read/favorite）。URL schema、request lifecycle、auto-read、404、attachment、error taxonomy 全部未变；未重构 Notice Detail 或 Dashboard。

## Baseline

| 项 | 值 |
| --- | --- |
| 进入时 | 前端 36 tests（8 files）/ lint PASS / build PASS（2785 modules）；后端 43 pytest |
| 完成时 | 前端 55 tests（10 files）/ lint PASS / build PASS（2787 modules）；后端 43 pytest |

## Previous Notice List Audit

- `NoticesPage.tsx`：8 个控件全部 inline（raw palette 网格），无 reset/clear、无 active filter count、无 mobile filter sheet、单一通用 empty state。
- `NoticeCard.tsx`（列表项）：category badge 醒目（accent）、important 显示为裸 `优先级 N`、deadline/importance 混在一条 metadata、未读点纯颜色、favorite 用 absolute 定位、expired 用 `opacity-60`。
- `NoticeRow.tsx`（Dashboard）：本 Gate 未动。
- `NoticeList.tsx`：仅 Card 包裹 + 通用 empty。
- URL state（`noticeSearchParams.ts`）：Gate 2B 已闭环，本轮未改 parse/serialize 语义。

## Target Information Hierarchy

Tier 1 标题 → Tier 2 decision cluster（重要度 + deadline）→ Tier 3 context cluster（来源 → 分类 → 发布时间）→ Tier 4 read/favorite。所有元数据不等权；favorite 是 action 非 metadata。

## Notice Item Implementation

`NoticeCard.tsx` 重写为三段式：
- 顶部：unread 点（`bg-unread` / `bg-border`）+ 标题链接（`text-notice-title`，unread medium / read normal，expired 降为 `text-text-secondary`）+ 右侧 star action。
- decision cluster（`text-xs`）：重要度标签（仅 important/high）+ deadline（按 tone 着色/图标）+ “已更新”。
- context cluster（muted）：`来源 · 分类 · 日期`。
- 未读/已读用 `sr-only` 文字声明（非纯颜色）；favorite 是独立 button（不嵌套在链接内、不触发导航）。

## Importance Semantics

固定 band（`utils/noticeMeta.ts`）：`<70` normal / `70–89` 重要 / `≥90` 高相关。normal 不显示（减少噪音），important/high 显示文字标签（`color-important`）。不再显示裸 `优先级 N`；band 与 `priorityThreshold` 解耦。

## Deadline Semantics

`deadlinePresentation()`：no deadline→`时间待定` muted；normal>3 天→`截止 MM-dd · 剩余 N 天` secondary；soon 1–3 天→`剩余 N 天` danger+图标；today→`今天截止` danger；expired→`已截止` muted。无 `color-deadline` token。

## Read / Unread

未读：`bg-unread` 点 + 标题 medium + `sr-only`“未读”；已读：`bg-border` 点 + 标题 regular + `sr-only`“已读”。未改 auto-read `Set<number>` 行为。

## Favorite

独立 star button（`aria-label` 收藏/取消收藏、focus-visible、hover、44px 触点目标），沿用现有 mutation（不改 response contract）。smoke 实测点击不触发导航（pathname 保持 `/notices`）。

## Search

NoticesPage 内联搜索：300ms debounce + `q` 写 URL（replace）+ q 变化 page=1，逻辑未改；仅重构布局/视觉。

## Desktop Filters

单一搜索框 + 7 个 filter select（`hidden md:grid`，`md:grid-cols-3 xl:grid-cols-7`），全部沿用 URL schema；结果栏显示“找到 N 条通知”+ 非空且存在筛选时“清除筛选”+ 页码。7 个 select 抽到 `NoticeFilters.tsx` 的 `FilterFields`（desktop 与 mobile sheet 复用）。

## Mobile Filter Sheet

`FilterFields` 进 Radix Dialog 底部 sheet；draft state（打开时从 URL state 初始化）→ 编辑 → `应用` 写入 URL（resetPage）→ `重置` 清空 draft；关闭/Escape/backdrop 丢弃。sheet 含 accessible title、焦点陷阱、`重置`/`应用`（显示 draft 数量）。

## URL State Preservation

逐项确认（`noticeSearchParams.ts` parse/serialize 未改语义，仅新增 `countActiveFilters`）：

| 参数 | 状态 |
| --- | --- |
| q | PRESERVED（replace，page reset） |
| category | PRESERVED |
| source | PRESERVED |
| min_score | PRESERVED |
| date_from | PRESERVED |
| deadline_status | PRESERVED |
| read | PRESERVED |
| favorite | PRESERVED |
| page | PRESERVED |
| page_size | PRESERVED |

refresh/share/back-forward、非法值 fallback、默认值序列化均未变（Gate 2B 测试全保留）。

## Pagination

沿用 `Pagination`（上一页/第 X / Y 页/下一页，disabled、tabular-nums、`total_pages<=1` 隐藏），未改 page/page_size 架构。

## Loading / Empty / Error

- Loading：新增 `NoticeListSkeleton`（notice-row 形状，animate-pulse，reduced-motion 尊重）；查询用 `placeholderData` 保留上一页内容。
- Empty 三态分离：search-empty（`没有匹配 “q” 的通知`+清空搜索）/ filter-empty（`没有找到相关通知`+清除筛选）/ true-empty（`暂无通知`）。`EmptyState` 新增可选 `action`。
- Error：沿用 Gate 3B `ErrorState`（kind 映射不变），与 empty 分离。

## Responsive

| 视口 | 结果 |
| --- | --- |
| 320×700 | 无横向滚动（scrollWidth 320），bottom nav 可见，标题换行 |
| 390×844 | mobile shell，search + 筛选 button，无 desktop sidebar |
| 768×1024 | desktop shell（sidebar flex、bottom nav 隐藏），无中间态冲突 |
| 1366×768 | 完整 desktop toolbar + list，无溢出 |

## Dark / Light

Notice List 在 light + dark 下均为真实设计态（surface/border/text/important/danger tokens 双主题切换，smoke 实测）。

## Accessibility

标题为真实 link；read/unread 非纯颜色（sr-only + 字重 + 点）；favorite `aria-label` + 独立 button；deadline 文字+图标+颜色；importance 文字标签；filter controls 均有 `aria-label`；sheet 焦点陷阱/Escape/焦点恢复/title；pagination 按钮名与 disabled；沿用 Gate 3B focus foundation。

## Browser Verification

专用 headless Chrome（CDP，port 9333，记录 PID）+ Vite dev（5173）+ 真实后端（8000），CDP 计算样式/结构探针。

| 场景 | 结果 |
| --- | --- |
| /notices light+dark（1366） | list hierarchy 正确（`已读 | 标题 | 时间待定 | 来源 · 分类 · 日期`），76 条，pagination 显示，无溢出 |
| ?category=research&source=cse&deadline_status=urgent&read=0&favorite=1 | 5 个 select 全部正确恢复，URL 回灌 UI |
| ?q=软件 | 搜索框显示“软件”，33 条结果 |
| ?q=软件&source=csw&page=2 | 28 条，清除筛选按钮出现，第 2 页 |
| ?q=不存在关键词xyz | search-empty heading `没有匹配 “不存在关键词xyz” 的通知` |
| mobile 390 / 320 | sidebar none、bottom nav flex、无溢出 |
| tablet 768 | sidebar flex、bottom nav none |
| Mobile sheet | 打开→改分类→应用→URL `?category=research` |
| favorite | 点击后 pathname 保持 `/notices`（不触发导航） |

smoke 后按记录 PID 逐一停止，端口 8000/5173/9333 全部释放。

## Tests Added

新增 19 项（36 → 55）：
- `utils/noticeMeta.test.ts`（9）：importance band、deadline 各态、sourceLabel、isExpired。
- `components/notice/NoticeCard.test.tsx`（5）：title link href、importance 标签非裸数字、deadline 文本、read/unread sr-only、favorite 独立 button 不触发导航。
- `pages/NoticesPage.test.tsx`（+5）：search-empty / filter-empty / true-empty 三态、empty-state clear 写回 URL、mobile sheet open→apply→reset→URL。
- 既有 Gate 2B URL round-trip 6 项全保留。

## Files Changed

- `frontend/src/utils/noticeMeta.ts`（新增）
- `frontend/src/utils/noticeSearchParams.ts`（新增 `countActiveFilters`）
- `frontend/src/components/notice/NoticeCard.tsx`（重写）
- `frontend/src/components/notice/NoticeList.tsx`（emptyAction + `NoticeListSkeleton`）
- `frontend/src/components/notice/NoticeFilters.tsx`（新增 `FilterFields`）
- `frontend/src/components/ui/Feedback.tsx`（`EmptyState` 加可选 `action`）
- `frontend/src/pages/NoticesPage.tsx`（重写：toolbar + sheet + empty 三态 + clear/count）
- 测试：`noticeMeta.test.ts`、`NoticeCard.test.tsx`、`NoticesPage.test.tsx`
- `docs/design/design.md`（expired 语义：opacity-60 → muted 语义 + 标题降级，对比度优先）
- `docs/GATE_4A_REPORT.md`（本报告）

未修改：backend、routes、`api/client.ts`、`NoticeDetailPage`、`DashboardPage`、`NoticeRow`、`AppShell`、package/config。

## Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 10 files，55 项 |
| `npm run lint` | PASS — 0 warnings / 0 errors |
| `npm run build` | PASS — 2787 modules |
| `.\.venv\Scripts\python.exe -m pytest` | PASS — 43 项 |

（沙箱拦截原生子进程/命名管道与 pytest 目录枚举，按本会话既有拒绝先例以 `danger-full-access` 重跑；未改项目配置。）

## Preserved Behavior

- **URL**：unchanged（10 个 schema 字段、parse/serialize、refresh/share/back-forward、非法值 fallback）。
- **Request lifecycle**：unchanged（AbortController + signal + 15s timeout + cleanup）。
- **Auto-read**：unchanged（`Set<number>`）。
- **404**：unchanged（专用页面）。
- **Attachment**：unchanged（`filename/url/type`）。
- **Error taxonomy**：unchanged（`NETWORK_ERROR|TIMEOUT|ABORTED|HTTP_ERROR|NOT_FOUND`）。
- **Routes**：unchanged（未新增/删除/改 path/redirect/fallback）。

## Deferred

- Notice Detail 重构（Gate 4B）。
- Dashboard 重构（NoticeRow 复用，Gate 4C）。
- SearchDialog error UX / race（Gate 4C / 6）。
- mutation response contract（Gate 6）。
- source filter 硬编码显示名 → 数据驱动（数据层/Sources 阶段）。
- Gate 3B 遗留锁定 `.smoke-*.log` 临时日志（无害，待旧 wrapper 进程退出可删）。

## Risks

- NoticeCard 是列表页共享组件（Today/Deadlines/Favorites/Feeds 也使用），其视觉收敛会扩散到这些列表页——这是“统一 notice list primitive”的预期结果，未触碰 Dashboard（用 NoticeRow）。
- mobile sheet 的 desktop 7 个 select 始终在 DOM（CSS `hidden md:grid` 隐藏），移动端仅 sheet 可交互；jsdom 测试按需 scoped。
- 重要度 normal 不再显示任何标签（减少噪音），与 Design Contract §11“normal 可弱化”一致。

## Recommended Next Gate

# Gate 4B — Notice Detail

本 Gate 已完成，不自动开始 Gate 4B。
