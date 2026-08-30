# Gate 3C Result

**PASS**

Gate 3C — App Shell + Navigation 完成。基于 Gate 3B tokens/primitives 建立了统一响应式应用外壳：Desktop Sidebar（232/72px 可折叠）+ Sticky Header（64px）+ Main Content Frame；Mobile Top Bar + Bottom Navigation + More Sheet。未新增/删除/改任何 route，未重构业务页面。

## Baseline

| 项 | 值 |
| --- | --- |
| 进入时 | 前端 26 tests（6 files）/ lint PASS / build PASS；后端 43 pytest |
| 完成时 | 前端 36 tests（8 files）/ lint PASS / build PASS；后端 43 pytest |
| Stack | Tailwind v4 tokens（Gate 3B）+ Radix Dialog + React Router 7 + TanStack Query |

## Current Shell Audit

旧 `AppShell.tsx` 单文件 27 行，全部内联：

- `groups`（3 组：总览/分类/管理）与 `mobile`（4 项）两份硬编码导航数组。
- `NavItems` 内联渲染（`<NavLink>`，`end={to==='/'}` 仅对首页精确匹配）。
- 桌面：`<aside>` 72/232px 用 `w-[72px]`/`w-[232px]` 魔数；内容偏移用 `md:pl-[72px]`/`md:pl-[232px]`。
- Header：`h-16`，含**移动端 hamburger**（`md:hidden`）+ SearchDialog + CrawlerButton + theme toggle。
- `<main>` `max-w-[1500px]`。
- 底部 `<nav>` `h-[68px]` + `更多` 按钮。
- Drawer：Radix Dialog 右侧 sheet，`NavItems` 复用。
- 全部 shell 用 raw palette（zinc-*/indigo-*）。

问题：移动端 **hamburger 与 `更多` 双入口重复**（违反 Gate 3A.1 C2）、魔数布局值、导航配置无单一来源、active 态对 nested route 不够明确。

## Shell Architecture

- **Desktop（≥768px）**：`<aside>` fixed 左侧（232px 展开 / 72px 折叠，`w-sidebar-expanded`/`w-sidebar-collapsed`）+ 内容区 `md:pl-sidebar-expanded`/`md:pl-sidebar-collapsed` 偏移 + `sticky` header（`h-header-height`）+ `<main class="mx-auto max-w-content-max p-4 sm:p-6 lg:p-8">`。
- **Mobile（<768px）**：Sidebar `hidden md:flex`；Top Bar（页面 context + Search + Theme，**无 hamburger**）；Bottom Nav `fixed` `h-mobile-nav-height`；body 底部 padding（Gate 3B 已设 `var(--spacing-mobile-nav-height)`）。
- **Content frame**：统一 `main`，页面仍各自渲染 `PageHeader`/内容，未改页面内部。
- **z-index**：content 0 < header 20 < sidebar 30 < bottom nav 40 < overlay/sheet/dialog 50 < toast 100（已写入 design.md §10.3）。

## Navigation Configuration

抽取 `components/layout/navigation.tsx`（单一来源）：

- `navGroups`：13 个真实 route 映射到 总览/分类/管理 三组（图标 + label + to）。
- `mobileNavItems`：底部导航 4 项（`/`、`/today`、`/deadlines`、`/favorites`）。
- `getRouteTitle(pathname)`：route→context title（`/notices/:id` → 通知详情；未知 → 吉大通知助手）。
- 所有 `NavLink` 使用 `end`（精确匹配）→ nested route（如 `/competitions/algorithm`）只高亮自身，active 态明确。

## Desktop Sidebar

- 展开 232px / 折叠 72px（`transition-[width]`，150ms motion）；折叠只显示图标，分组 heading 隐藏，`title` 提供 collapsed label 的可访问名。
- active：`bg-accent-soft text-accent-soft-text`（对比度 7.1/8.0:1）+ `font-medium` + `aria-current="page"`（NavLink 默认）。
- `<nav aria-label="主导航">`、`<aside>`、分组结构。
- 折叠按钮 `aria-label` 折叠/展开侧边栏，键盘可操作，不改 route。
- 折叠持久化沿用现有 `localStorage['jlu-sidebar']`（不引入新状态架构）。

## Header

- `sticky top-0 h-header-height`、`bg-surface/90 backdrop-blur`、`border-border`。
- 内容：全局搜索入口（复用 SearchDialog，未改其行为）、CrawlerButton（桌面 `hidden md:block`）、theme toggle（icon button，`aria-label`）。
- 移动端额外显示页面 context（`data-testid="route-context"`，`md:hidden`）。

## Mobile Top Bar

- 仅移动：页面 context/title + Search + Theme；**无 hamburger / 无重复 More 按钮**。
- 优先级 context > search > theme；theme 为 icon button。

## Mobile Bottom Navigation

- `fixed inset-x-0 bottom-0 h-mobile-nav-height`，`md:hidden`。
- 4 项 destination（首页/今日/截止/收藏）+ `更多`（`aria-label="更多导航"`）。
- active：`text-accent-soft-text font-medium`（非纯颜色），`aria-current`。
- 无 badge spam / 无 unread nav item / 无 FAB。

## More Navigation Panel

- `更多` 是移动端完整导航唯一主要入口；复用 Radix Dialog 右侧 sheet。
- 含全部 13 个真实 route（按 总览/分类/管理 分组），`<nav aria-label="完整导航">`。
- Radix 提供 focus trap / Escape / focus restore / backdrop；`Dialog.Title` "全部功能" + `关闭菜单` 按钮。
- 选择任一 route 后自动关闭（`onSelect` → `onOpenChange(false)`）。

## Responsive Behavior

| 视口 | 结果 |
| --- | --- |
| 320×700 | 无横向滚动（scrollWidth 320），bottom nav 显示，route-context "收藏"，Sidebar 隐藏 |
| 390×844 | 同上（scrollWidth 375），light+dark 均正常 |
| 768×1024 | Sidebar flex（232px）、bottom nav 消失、无中间态冲突 |
| 1366×768 | Sidebar 展开 232 / 折叠 72，Header 64px，content offset 232/72px，active 正确，light+dark |
| 1440×900 | 同上，main max-width 1500px 不无限拉宽 |

## Accessibility

- Sidebar/导航：`<nav>`+`aria-label`、`aria-current="page"`、折叠按钮 accessible name、collapsed `title`。
- Header：search 入口、theme toggle 均 accessible。
- BottomNav：每项 accessible name，active 非纯颜色。
- More Panel：Radix 焦点陷阱/Escape/焦点恢复/backdrop/`Dialog.Title`。
- Focus：沿用 Gate 3B 全局 `focus-visible`（`2px solid var(--focus)` + offset 2px）。

## Browser Verification

方法：专用 headless Chrome（DevTools Protocol，port 9333，独立 profile，记录 PID）+ Vite dev（5173）+ 真实后端（8000）+ CDP 计算样式探针（模型无法读图，故用 DOM/计算样式断言）。

| 检查 | 结果 |
| --- | --- |
| Desktop 1366 expanded/collapsed light+dark | sidebar 232px/72px、content offset 232px/72px、header 64px、bottom nav none、无溢出、折叠按钮名正确 |
| Desktop 1440 / tablet 768 | 同上，main max-width 1500px，无溢出 |
| Mobile 390 light+dark / 320 | sidebar none、bottom nav 68px、route-context 正确（全部通知/设置/收藏）、无溢出 |
| Route spot-check（/notices /favorites /sources /settings /cybersecurity） | h1 正确、active 正确、无溢出 |
| More panel | 打开显示完整导航（含 全部通知），关闭后 dialog 消失 |
| 主题 | light/dark `html.dark` 正确落位 |

smoke 结束后按记录 PID（chrome=43872 / backend=34548 / dev=37104）逐一终止，未使用任何全局 kill；端口 8000/5173/9333 已全部释放。

## Tests Added

新增 10 项（26 → 36）：
- `navigation.test.ts`（4）：route→group 完整映射、mobile 4 项、静态+动态 title、未知 fallback。
- `AppShell.test.tsx`（6）：sidebar 分组 destinations、current route `aria-current`、collapse toggle + localStorage 持久化、bottom nav 4+更多、More panel 打开/含完整导航/关闭、动态 route context。
- `test/setup.ts`：新增 `matchMedia` polyfill（ThemeProvider 依赖）。

## Files Changed

- `frontend/src/components/layout/navigation.tsx`（新增，导航配置单一来源）
- `frontend/src/components/layout/AppShell.tsx`（重写：Sidebar/Header/TopBar/BottomNav/MorePanel，全部 token 化）
- `frontend/src/test/setup.ts`（matchMedia polyfill）
- `frontend/src/components/layout/AppShell.test.tsx`、`frontend/src/components/layout/navigation.test.ts`（新增测试）
- `docs/design/design.md`（§10.3 z-index 分层约定）
- `docs/GATE_3C_REPORT.md`（本报告）

未修改：路由、`PageHeader`、`SearchDialog`、`CrawlerButton`、所有业务页面、backend、package/config。

## Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 8 files，36 项 |
| `npm run lint` | PASS — 0 warnings / 0 errors |
| `npm run build` | PASS — 2785 modules |
| `.\.venv\Scripts\python.exe -m pytest` | PASS — 43 项 |

（沙箱拦截原生子进程/命名管道与 pytest 目录枚举，已按本会话既有拒绝先例以 `danger-full-access` 重跑；未改任何项目配置。）

## Preserved Behavior

- **URL schema**：unchanged（未新增/删除/改 route、redirect、fallback）。
- **Request lifecycle**：unchanged（AbortController + external signal + 15s timeout + cleanup）。
- **Auto-read**：unchanged（`Set<number>` by id）。
- **404**：unchanged（专用“通知不存在”）。
- **Attachment**：unchanged（`filename/url/type`）。
- **Error taxonomy**：unchanged（`NETWORK_ERROR|TIMEOUT|ABORTED|HTTP_ERROR|NOT_FOUND`）。
- Theme persistence 未重构；sidebar collapse 沿用既有 localStorage。

## Deferred

- 业务页面（Dashboard/Notice list/detail/Filters/Settings form/Source cards）仍未迁移到 tokens——属 Gate 4。
- SearchDialog error UX / request race / keyboard result logic（Gate 4C / 6）。
- Toggle/Switch、IconButton primitive（Gate 4C / 后续）。
- Gate 3B 遗留的 4 个被锁定 `.smoke-*.log` 临时日志（gitignored、无害，待旧 wrapper 进程退出可删）。

## Risks

- `end` 精确匹配使“父分类上下文”不再随子路由高亮（`/competitions/algorithm` 只亮“算法竞赛”）；这是换取 active 态明确性的有意取舍，符合 Gate 3C 要求。
- 移动 top bar 页面 context 与页面 h1 文案可能重复（如“全部通知”），属预期（top bar 为 context 提示，非 h1）。
- 折叠持久化仍走 localStorage 快照读取（Gate 6 已知 settings reactivity 问题不涉及 sidebar collapse，未跨入）。

## Recommended Next Gate

# Gate 4A — Notice List + Filters

本 Gate 已完成，不自动开始 Gate 4A。
