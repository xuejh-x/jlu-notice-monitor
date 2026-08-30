# Gate 4C Result

**PASS**

Gate 4C — Remaining Core Pages 完成。Dashboard、Today、Deadlines、Favorites、全部现有分类 route、Sources、Settings 与 SearchDialog 已统一到 Design Contract、semantic tokens、AppShell 和既有 notice domain components；未新增或修改 route，未修改 backend production code，也未进入 Gate 5/6 的专项架构工作。

## Baseline

| 项 | 进入时 | 完成时 |
| --- | --- | --- |
| 前端测试 | 69（12 files） | 82（18 files） |
| lint | PASS | PASS |
| build | PASS（2789 modules） | PASS（2788 modules） |
| 后端 pytest | 43 | 43 |

模块数减少 1 是因为 Dashboard 不再消费 legacy NoticeRow，改为直接复用 NoticeList / NoticeCard；未删除该用户工作区文件。

## Remaining Pages Audit

以当前 frontend/src/App.tsx 为事实源：

| Route | 实际组件 | 架构 / query semantics |
| --- | --- | --- |
| / | HomeRoute → DashboardPage 或保存的默认首页 redirect | 独立 Dashboard；dashboard + important query |
| /today | TodayPage | 独立页；/api/notices/today，不重新定义“今日” |
| /deadlines | DeadlinesPage | 独立页；既有 deadline endpoint + days preset |
| /favorites | FavoritesPage | 独立分页页；favorite=true |
| /competitions | CompetitionsPage | 独立页；真实 category/source/min_score/deadline/sort preset |
| /competitions/algorithm | FeedPage | shared category preset：algorithm_competition |
| /cybersecurity | FeedPage | shared category preset：cybersecurity_competition |
| /research | FeedPage | shared category preset：research |
| /postgraduate | FeedPage | shared category preset：postgraduate_recommendation |
| /training | TrainingPage → FeedPage | shared feed + training/internship preset tabs |
| /sources | SourcesPage | 独立只读来源概览 |
| /settings | SettingsPage | 既有 theme context + settings localStorage |
| /notices | NoticesPage | Gate 4A，未重构；仅替换 Dialog overlay token |
| /notices/:id | NoticeDetailPage | Gate 4B，未修改 |
| /algorithm | Navigate | redirect unchanged |
| * | Navigate | fallback unchanged |

安全复用边界：

- PageHeader：remaining core pages 的 h1 / description / action。
- NoticeList / NoticeCard / NoticeListSkeleton：Today、Favorites、Feeds、Deadlines、Dashboard。
- FeedPage：四个 category route + Training wrapper。
- ErrorState / EmptyState：统一 page-level state；ABORTED 按契约静默。
- Select / Toggle：Settings 的真实 controls。
- isSafeExternalUrl + ExternalAnchor：Sources 与 Gate 4B Detail 共用同一外链闸门。

进入时 raw palette / legacy layout 位于 Dashboard、NoticeRow、PageHeader、Deadlines/Competition/Training tabs、Sources、Settings、SearchDialog。完成后 Gate 4C scope 均使用 semantic tokens；未全仓机械替换。

## Dashboard

- 层级：context → 4 个核心摘要 → 优先关注 / 最近通知 → 来源状态。
- 指标仅保留今日新增、未读、3 天内截止、待办截止；不展示数据库或 crawler 内部 KPI。
- 优先阈值明确为用户 cutoff，不改变固定 importance band。
- 优先/最近通知区均复用 NoticeList / NoticeCard；不创建 Dashboard 专用 notice card。
- 主 query 与 important 子 query 的 loading / error / empty 分离。
- true-empty 显示“尚无通知”并引导查看数据源。
- 来源摘要使用真实 source_status，不新增实时监控 API。

## Today

- 使用既有 /api/notices/today semantics。
- PageHeader 始终存在；成功后显示真实 result count。
- contextual empty：“今天暂无新通知”。
- loading 使用 NoticeListSkeleton，error 使用 ErrorState。

## Deadlines

- 继续使用真实 deadline endpoint，不新增前端截止算法。
- 保留全部 / 今天 / 3 天 / 7 天 / 30 天 preset，改为 semantic segmented controls。
- 按 registration deadline 分组，组内复用 NoticeList。
- 当前数据集无未来截止样本，浏览器显示 contextual empty；其他 deadline branches 由既有 metadata tests 覆盖。

## Favorites

- 继续使用 favorite=true 的既有 paginated query 与 mutation/cache。
- 显示真实收藏总数。
- contextual empty：“还没有收藏通知”+“前往全部通知”。
- 未创建第二套 favorite state。

## Category / Collection Pages

- 算法、网络安全、科研、推免继续共用 FeedPage；Training 只提供真实 training/internship preset controls。
- FeedPage 统一 PageHeader、result count、NoticeList、pagination、loading/error/contextual empty。
- CompetitionsPage 因真实筛选能力保持独立；tabs 与筛选 token 化，threshold 文案为“评分 N 以上”。
- 浏览器真实数据：全部竞赛 10、算法 3、网络安全 3、实训/实习 6、科研 10、推免 1。
- 竞赛选择“创新创业 + 网络安全学院”构造真实 empty，显示“暂无符合条件的竞赛通知”。
- 从算法页通知链接 /notices/11 导航到详情成功；未改 Gate 4A/4B。

## Sources

- 从卡片网格改为紧凑只读 row/list；展示 name/code、enabled、status、最近检查、最近成功、notice count、真实 message。
- healthy 使用 success；disabled / unconfigured 使用 neutral；login/unavailable 使用 warning/danger，且始终带文字。
- OA 真实状态为 disabled：显示“未启用 / 已停用 / 尚未完成首次登录配置”，不显示为 fatal crawler failure；disabled 时不重复显示历史 last_error。
- base_url 先通过 Gate 4B isSafeExternalUrl；不安全 URL 只显示“来源网站地址不可用”，不生成 anchor。
- 安全外链为 target=_blank + noopener noreferrer；浏览器核验 6 个真实链接全部为 https。
- true-empty 与 page-level loading/error 已补齐。

## Settings

真实设置能力：

- theme：light / dark / system；
- priority threshold；
- 精简首页优先列表（既有 hideLowPriority）；
- page size；
- default home。

视觉组织为“外观 / 通知偏好 / 阅读与显示”。每个 section 使用 h2，设置项使用 h3/accessible label；移动端单列、桌面 label/control 对齐。新增 Toggle primitive 仅服务现有真实 switch consumer。

Settings persistence / reactivity 完全保持既有 loadSettings / saveSettings + localStorage 快照行为，未重构 store。

## SearchDialog

本 Gate 实际修改：

- 全部视觉迁移到 semantic tokens，Dialog 使用 color-overlay；
- 移动端为 16px inset、受 viewport 高度约束的布局；
- 输入框新增 accessible name；
- result row 复用 importanceLevel / deadlinePresentation / sourceLabel，显示 title、decision signal、source/category/date；
- loading / result / search-empty / error 四态分离；
- ErrorState 可重试，error 不再落成“没有结果”；
- 关闭按钮达到 44px mobile target。

未修改 debounce/request layer/query architecture；SearchDialog race 保留到 Gate 6。

## Shared Components

- PageHeader：token 化并使用 semantic header。
- ErrorState：ABORTED 静默。
- Toggle：真实 Settings consumer。
- FeedPage：统一 route category presets。
- SourceRow、SettingsSection、SettingRow、SearchResultRow：局部轻量组件，不建立 page DSL。
- color-overlay：同步写入 Design Contract / Tailwind，并替换 SearchDialog、AppShell More、Notices filter overlay。
- Dashboard 不再消费 NoticeRow；该文件仅 token 化保留，不删除用户工作区内容。

## Loading / Empty / Error

- Loading：列表场景统一 NoticeListSkeleton，其他页使用现有 PageSkeleton。
- Empty：Today、Deadlines、Favorites、category feeds、Sources、Dashboard 均有 contextual copy。
- Error：NETWORK_ERROR / TIMEOUT / HTTP_ERROR 保持可重试，NOT_FOUND 继续专用于详情，ABORTED 静默。
- Dashboard important 子 query error 与 empty 已分离。
- SearchDialog error 与 no-result 已分离。

## Responsive

| Viewport | 实际验证 |
| --- | --- |
| 320×700 | /、/deadlines、/sources、/settings；overflow 0 |
| 390×844 | 全部 Gate 4C routes；Sidebar none、BottomNav flex、每页单 h1、overflow 0 |
| 768×1024 | /、/competitions、/sources、/settings；Sidebar flex、BottomNav none、overflow 0 |
| 1366×768 | 全部 Gate 4C routes；Desktop shell、单 h1、overflow 0 |

首次 320 spot-check 发现 html/body min-width:320px 与 Windows classic scrollbar 产生 15px overflow；已删除强制 min-width，并在 Design Contract 记录“320 是验证下限而非 root CSS min-width”，复测为 0。

## Dark / Light

- Dark（原 theme=system、当前系统 dark）与临时 light 均完成 Dashboard、Sources、Settings、SearchDialog 核验。
- body 背景实测 light rgb(250,250,250) / dark rgb(9,9,11)。
- Dashboard metrics、source statuses、settings sections、dialog、empty/error 全部走 semantic tokens。
- 浏览器测试后 theme 已从临时 light 恢复原 system，其他设置未改。

## Accessibility

- 每个 route 恰好一个 h1；page sections 使用逻辑 h2，Settings rows 为 h3。
- Settings selects / switch 有可见 accessible labels 与 descriptions。
- Search input、close、result buttons 有 accessible names；Radix focus/Escape/focus restore 保留。
- status 不只靠颜色；Sources/notice/search result 均有文字语义。
- 外链有文字、external icon、sr-only“在新窗口打开”。
- Tabs/range buttons 使用 aria-pressed；移动关键 controls 达到基本 touch target。
- 完整 WCAG/zoom/keyboard matrix 留 Gate 5。

## Browser Verification

运行环境：

- 现有项目后端 127.0.0.1:8000：PID 31724，health ok，database ok，crawler idle。
- 现有项目 Vite 127.0.0.1:5173：PID 23160。
- 两者均为用户/前序会话已有进程，本轮只读确认 command line，未终止。
- Search error 使用本轮独立 Vite 5174 指向 dead 8010；精确验证 PID 53388 后停止，5174 已释放。
- 启动新 backend 的尝试因 8000 已占用正常退出；未终止既有服务或未知进程。

逐页面：

| Route / scenario | 实际结果 |
| --- | --- |
| / | 真实 data、4 metrics、priority/recent lists、来源 5 normal + 1 paused |
| /today | 0 条；contextual true-empty |
| /deadlines | 30 天 0 项；contextual true-empty + range controls |
| /favorites | 1 条真实收藏 |
| /competitions | 10 条；filters；构造 empty 成功 |
| /competitions/algorithm | 3 条；通知导航到 /notices/11 |
| /cybersecurity | 3 条 |
| /training | 6 条；真实 preset tabs |
| /research | 10 条 |
| /postgraduate | 1 条 |
| /sources | 6 rows；5 healthy + OA disabled；外链安全属性正确 |
| /settings | 3 sections / 5 controls；light/dark/system；移动单列 |
| Search result | “软件”返回 20 个 compact results；390px dialog width 358 / overflow 0 |
| Search empty | “不存在关键词xyz”显示 query-specific empty |
| Search error | 5174→dead 8010：显示“无法连接本地服务”+“重新连接”，不显示 no-result |
| dark/light | Dashboard/Sources/Settings/SearchDialog 均通过 |

## Tests Added

新增 13 项（69 → 82）：

- DashboardPage.test.tsx（3）：data/source summary、HTTP error、true-empty。
- CollectionPages.test.tsx（2）：Today contextual empty、shared Feed preset/result/empty/query。
- SourcesPage.test.tsx（2）：healthy/disabled、safe/unsafe URL、disabled historical error suppression、true-empty。
- SettingsPage.test.tsx（2）：sections/labels/controls、既有 localStorage persistence、threshold wording。
- SearchDialog.test.tsx（3）：result decision signals、search-empty、HTTP error ≠ empty。
- Feedback.test.tsx（1）：ABORTED silent。

未删除、skip、todo 或弱化任何既有测试。

## Files Changed

Gate 4C 实际涉及：

- docs/design/design.md
- docs/GATE_4C_REPORT.md
- frontend/src/index.css
- frontend/src/components/layout/AppShell.tsx（overlay token only）
- frontend/src/components/layout/PageHeader.tsx
- frontend/src/components/notice/NoticeRow.tsx
- frontend/src/components/search/SearchDialog.tsx
- frontend/src/components/ui/Feedback.tsx
- frontend/src/components/ui/Form.tsx
- frontend/src/pages/DashboardPage.tsx
- frontend/src/pages/TodayPage.tsx
- frontend/src/pages/DeadlinesPage.tsx
- frontend/src/pages/FavoritesPage.tsx
- frontend/src/pages/CompetitionsPage.tsx
- frontend/src/pages/FeedPage.tsx
- frontend/src/pages/TrainingPage.tsx
- frontend/src/pages/SourcesPage.tsx
- frontend/src/pages/SettingsPage.tsx
- frontend/src/pages/NoticesPage.tsx（overlay token only）
- frontend/src/utils/labels.ts
- tests：DashboardPage.test.tsx、CollectionPages.test.tsx、SourcesPage.test.tsx、SettingsPage.test.tsx、SearchDialog.test.tsx、Feedback.test.tsx

## Dependencies Added

None

## Validation

| 命令 | 结果 |
| --- | --- |
| npm test -- --run | PASS — 18 files / 82 tests |
| npm run lint | PASS — 0 errors |
| npm run build | PASS — 2788 modules |
| backend/.venv/Scripts/python.exe -m pytest | PASS — 43 tests |

后端 venv 的 base interpreter 位于 sandbox 外，按权限要求在批准的 escalated 环境运行；项目与 venv 未修改。

## Preserved Behavior

全部 unchanged：

- Notices URL schema：q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size；
- request lifecycle：AbortController + external signal + 15s timeout + cleanup；
- auto-read：Set<number> per notice id exactly once；
- dedicated 404；
- attachment filename / url / type；
- error taxonomy；
- routes / redirect / fallback；
- Gate 4A Notice List / Filters；
- Gate 4B Notice Detail。

## Deferred

- Settings persistence / reactivity architecture → Gate 6。
- SearchDialog request race / request architecture → Gate 6。
- mutation response contract → Gate 6。
- API normalization、TanStack Query/cache governance、source filter data-driven architecture → Gate 6。
- exhaustive responsive / zoom / keyboard / screen-reader / contrast audit → Gate 5。
- backend structured-body extraction、dynamic source management、scheduler / cloud / deployment → later backend gate。
- MSW、Playwright、CI → later quality/automation gate。

## Risks

- Dashboard important endpoint 按现有 backend contract 返回全历史高分通知，可能包含已截止项；本 Gate 未创建冲突前端算法或修改 backend。
- Settings 仍是 snapshot + localStorage；同一已挂载 consumer 的即时 reactivity 不保证，deferred Gate 6。
- SearchDialog 仍使用现有 debounce/query request model；快速输入 race architecture 未重写。
- 当前真实数据无 future deadline 样本，Deadlines 浏览器验证为 true-empty；semantic branches 由既有 unit coverage 保留。
- 320 root min-width 修复是全站基础 CSS 的最小 reflow 修正；四个重点页及 390/768/1366 复测均无回归。

## Recommended Next Gate

# Gate 5 — Responsive + Mobile + Accessibility

本 Gate 到此停止，不自动开始 Gate 5。

