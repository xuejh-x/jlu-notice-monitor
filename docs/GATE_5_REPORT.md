# Gate 5 Result

**PASS**

Gate 5 — Responsive + Mobile + Accessibility 完成。本 Gate 先用真实前后端环境审计现有实现，再只修复浏览器中可复现或由语义结构明确证明的问题；未重设计页面、导航、卡片或布局，未修改 backend production code，也未进入 Gate 6 的请求 / 状态架构工作。

# Audit Summary

- 以 `docs/design/design.md`、`docs/GATE_4C_REPORT.md`、真实 router 和当前组件为事实源。
- 使用运行中的真实 API 数据覆盖 14 条主要路径：Dashboard、Notices、Today、Deadlines、Favorites、全部竞赛、算法、网络安全、实训/实习、科研、推免、Notice Detail、Sources、Settings。
- 对上述路径执行 320 / 360 / 390 / 430 / 768 / 1024 / 1366 共 98 个 viewport-route 检查；另做 667×375 移动横屏与构建后 36 个关键 smoke checks。
- 审计 document overflow、裁切、长标题/附件、fixed/sticky collision、移动触控、heading/landmark、accessible name、control state、Dialog focus/隔离、外链、明暗主题和 reduced motion。
- 使用现有真实数据；筛选空态仅改变内存态，主题和 switch 临时值均恢复；未为验证修改通知、收藏或后端持久数据。

# Responsive

## 320

- 14 条主要路径最终 `documentElement.scrollWidth - clientWidth = 0`。
- 首轮在 `/notices` 复现分页器把 273px 内容区撑到 290px、导致文档 1px 横向溢出；收紧小屏分页 gap / padding / label min-width 后，分页器 `scrollWidth = clientWidth = 273px`。
- 长详情标题、6 个长附件名、来源状态、设置单列、筛选 sheet 和 SearchDialog 均无裁切。

## 390

- 14 条主要路径无 document-level overflow 或意外 clipping。
- Dashboard 双列摘要、NoticeCard 决策/上下文簇、Sources rows、Settings controls 与移动 BottomNav 均可用。
- 竞赛以“创新创业 + 网络安全学院”得到真实筛选空态，保持单 h1、明确空态和 0 overflow。

## 768

- 14 条主要路径无横向溢出；Sidebar 显示、BottomNav 隐藏，断点切换正确。
- Notices desktop filters、collection controls、详情布局和长附件名正常收缩。

## 1366

- 14 条主要路径无横向溢出、裁切或 fixed/sticky collision。
- Dashboard 双列 notice sections、Sources 三列 row、Notice Detail 正文/侧栏布局均正常。

补充宽度：360、430、1024 的同一 14-route matrix 全部通过。667×375 横屏下 Dashboard、Notices、Detail、Sources、Settings 均无溢出；筛选 sheet 与 More panel 可内部滚动，BottomNav 保持 68px 且不遮挡页面末尾。

# Mobile UX

- Form Input / Select、默认 Button、icon Button、header 搜索/主题、NoticeCard 收藏、筛选 sheet、More panel、截止范围、来源/详情主链接和 toast close 在移动端使用 ≥44px 目标；桌面从 `md` 起继续保持原 36px 密度。
- Toggle 保留 44×24px 视觉 track，同时把实际按钮命中区扩大为 56×44px；`role=switch` 与 `aria-checked` 不变。
- BottomNav 的 5 个目标使用完整 68px 导航高度，不再只有 40px 内容高度。
- 320×320 压缩视口模拟虚拟键盘占用：SearchDialog 位于 16–266px，输入和关闭按钮仍可见，20 条结果在 192px 内部滚动区滚动（`scrollHeight 1896px`），无 document overflow。
- 667×375 横屏：筛选 sheet `clientHeight 318px / scrollHeight 544px`，More panel `375px / 788px`，均使用内部 `overflow-y:auto`，页面未误锁。

# Accessibility

## Semantics

- 98 个 route/viewport 检查均为一个 main、一个主要 h1；heading 层级未发现跳级造成的主要结构错误。
- 修复 Notice Detail loading / 404 / network error 分支缺少页面 h1：loading 使用 sr-only“通知详情”，详情错误通过 `ErrorState headingLevel={1}` 输出主标题。
- loading skeleton 使用 `role=status`；动态错误使用 `role=alert`；`ABORTED` 仍保持静默。
- 所有 `onClick` 交互继续使用原生 button/link，不用 div 模拟控件。

## Keyboard

- Sidebar、BottomNav、搜索、筛选、收藏、Settings、外链、Dialog close 均由原生可聚焦元素实现。
- 浏览器验证 Search / Filter / More 打开后焦点进入 Dialog，Escape 可关闭且无 keyboard trap。
- 原生 button/link/select/switch 保留 Enter / Space 行为；新增测试覆盖受控 Dialog 的展开状态、关闭和焦点恢复，既有测试继续覆盖 switch / navigation / mutations。

## Focus

- 实测 `focus-visible` 为 2px solid + 2px offset；浅色 focus/surface 对比 6.29:1，深色 3.97:1。
- SearchDialog 原有 focus return 保留。
- 修复 Filter sheet 与 More panel：关闭后分别回到 `notice-filter-trigger` 和“更多导航”按钮；浏览器与测试均验证。

## Forms

- 98 个 route/viewport 检查未发现无 accessible name 的可见 input/select/button/link/switch。
- Notices、Competitions、Settings 的 input/select 均有 label 或 aria-labelledby；switch 有 aria-checked。

## State

- Router active state继续使用 `aria-current=page`；tabs/ranges 使用 `aria-pressed`；switch 使用 `aria-checked`。
- 新增 Filter / More trigger 的 `aria-haspopup=dialog`、`aria-expanded` 和 `aria-controls`；实测 false → true → false。
- read/unread、favorite、healthy/disabled/error 均同时有文字或 accessible text，不只依赖颜色。

## Dialog

- Search / Filter / More 均渲染有可访问名称的 `role=dialog`；打开后 active element 位于 dialog 内。
- Radix modal 打开时锁定 body scroll / pointer interaction，并给 AppShell 背景设置 `aria-hidden=true`。
- Search 320px 长查询、20 条结果、empty、close、压缩高度均通过；Filter / More 横屏内部滚动通过。

## Links

- `/notices/36` 的 6 个附件链接和来源链接均保留完整 accessible text、`target=_blank`、`rel="noopener noreferrer"`；附件行高度约 45px。
- Sources 的 6 个真实外链均为 44px 高，名称包含“在新窗口打开”，且保留安全 URL gate。
- 404 返回列表链接为 44px，href 仍是 `/notices`。

## Theme / Contrast

- 浏览器实际切换 light / dark；Settings、Dashboard、Sources、Detail、SearchDialog 均无溢出，临时 theme 最终恢复 `system`。
- 语义 token 计算结果：light 正文最低 4.81:1（muted 4.83:1），dark 正文最低 5.42:1（muted 6.91:1）；inverse/accent 6.29:1；focus 分别 6.29:1 / 3.97:1。
- 未发现明显 badge、error、link 或 disabled state 对比问题。

## Motion

- 项目动效仅为短 transition、loading pulse 与 crawler spin；全局 `prefers-reduced-motion: reduce` 将 animation / transition 压缩至 0.01ms 并关闭 smooth scrolling。未发现会妨碍使用的位移动画。

# Issues Found

## 1. 320px pagination document overflow

- Problem：`/notices` 分页器在 Windows classic scrollbar 下可用内容宽度为 273px，但内部宽度为 290px，产生 1px document overflow。
- Severity：Medium。
- Reproduction：320×844，真实数据产生 4 页时打开 `/notices`。
- Fix：仅对小屏收紧 Pagination gap、按钮 padding 与页码 min-width；从 `sm` 起恢复原桌面间距。

## 2. Controlled mobile dialogs did not expose or restore trigger state

- Problem：Filter / More trigger 没有 `aria-expanded` / `aria-haspopup`；Escape 关闭后 active element 落回 body，而不是触发按钮。
- Severity：Medium。
- Reproduction：320×844，打开 Filter 或 More，按 Escape，检查 trigger state 和 active element。
- Fix：补 `aria-haspopup`、`aria-expanded`、`aria-controls`，并在 `onCloseAutoFocus` 恢复各自 trigger focus。

## 3. Primary mobile targets were 36–40px

- Problem：筛选 controls、header actions、favorite、More links、BottomNav 等实测为 36–40px，低于 Design Contract 的移动优先 44px。
- Severity：Medium。
- Reproduction：320×844，测量 `/notices`、Filter、More、Settings 主要交互矩形。
- Fix：使用响应式高度；移动 44px，desktop `md` 起保留原密度；Toggle 扩大命中区而不改变视觉 track。

## 4. Async feedback and detail error structure

- Problem：共享 loading/error 缺少 status/alert 语义；详情 loading 与 404/error 分支没有主 h1。
- Severity：Medium。
- Reproduction：打开不存在 notice id 并等待 retry 结束；首轮 DOM 只有 ErrorState h2。
- Fix：loading 加 `role=status`，error 加 `role=alert`；ErrorState 支持局部 heading level，详情错误使用 h1，loading 补 sr-only h1。

其他审计区域经验证未发现需要 Gate 5 修复的问题。

# Files Changed

收尾时重新读取当前工作树：`git status` 显示 43 个已跟踪修改文件、66 个未跟踪文件，共 109 项。它们包含前序 Gate 已存在的用户改动；本报告不把这些既有改动误归因于 Gate 5，也没有 reset / clean / 覆盖它们。

结合当前 diff 与本轮 Gate 5 实际触及范围，Gate 5 归因文件为 19 个（18 个 frontend 文件 + 本报告）：

- `docs/GATE_5_REPORT.md`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/components/layout/AppShell.test.tsx`
- `frontend/src/components/notice/NoticeCard.tsx`
- `frontend/src/components/notice/NoticeList.tsx`
- `frontend/src/components/search/SearchDialog.tsx`
- `frontend/src/components/ui/Button.tsx`
- `frontend/src/components/ui/Feedback.tsx`
- `frontend/src/components/ui/Feedback.test.tsx`
- `frontend/src/components/ui/Form.tsx`
- `frontend/src/components/ui/Pagination.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DeadlinesPage.tsx`
- `frontend/src/pages/NoticeDetailPage.tsx`
- `frontend/src/pages/NoticeDetailPage.test.tsx`
- `frontend/src/pages/NoticesPage.tsx`
- `frontend/src/pages/NoticesPage.test.tsx`
- `frontend/src/pages/SourcesPage.tsx`
- `frontend/src/stores/toast.tsx`

没有新增依赖，没有修改 Design Contract（实现只是在既有 ≥44px mobile target / focus / semantic state 契约内收敛）。

# Browser Verification

运行环境：

- 复用项目已有 Vite `http://127.0.0.1:5173`；尝试启动时由 strict port 明确确认该服务已运行，未终止既有进程。
- 真实页面显示后端在线、真实来源和通知数据；未启动或终止未知进程。
- 浏览器验证完成后重置 viewport override 并关闭本轮临时 tab。

覆盖：

- 98 checks：14 routes × 7 widths（320 / 360 / 390 / 430 / 768 / 1024 / 1366）。
- 667×375 横屏：Dashboard、Notices、Detail、Sources、Settings、Filter、More、Search。
- light / dark / system；临时值恢复 system。
- Search：result（20 rows）、long query empty、320×320 compressed viewport、Escape / focus return。
- Collection empty：Competitions 的真实组合筛选空态。
- Detail：长 h1、正文、6 attachments、source links、404、loading/error semantics。
- Sources：5 healthy + 1 disabled OA、6 external links。
- 最终构建后：4 个关键宽度 × 9 条路径 = 36 smoke checks；overflow / h1 / unexpected dialog 全部为 0 issue。

# Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 18 files / 84 tests |
| `npm run lint` | PASS — 0 errors |
| `npm run build` | PASS — 2788 modules transformed |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 tests |

Gate 5 新增 2 项回归测试（82 → 84）：Filter sheet state/focus restore；async loading/error announcements。既有 AppShell More test 与 Notice Detail 404 test 被加强为 expanded/focus 和 h1 assertions；未删除、skip、todo 或弱化测试。

# Preserved Behavior

以下行为保持不变：

- Notices URL schema：`q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`。
- request lifecycle：AbortController + external signal + 15s timeout + cleanup。
- Auto-read：按 notice id 的 `Set<number>`，每 id 恰好一次。
- mutation contract 与 Query cache invalidation。
- dedicated 404 文案与 NOT_FOUND / NETWORK / TIMEOUT / HTTP / ABORTED 错误分类；ABORTED 静默。
- attachment `filename / url / type` 与外链安全闸门。
- routes、redirect、Sidebar / BottomNav IA、未读入口和 source abstraction。
- Settings persistence/reactivity 架构与 SearchDialog request/debounce 架构。
- Gate 4A Notice List / Filters、Gate 4B Notice Detail、Gate 4C 页面视觉语言。

# Deferred

保持到 Gate 6：

- Settings persistence / reactivity architecture。
- SearchDialog request race / request architecture。
- mutation response contract。
- API normalization、TanStack Query/cache governance、source filter data-driven architecture。

Later gate：backend crawler、dynamic source management、cloud/deployment、完整自动化 E2E/CI 与专用屏幕阅读器人工回归。

# Recommended Next Gate

Gate 6
