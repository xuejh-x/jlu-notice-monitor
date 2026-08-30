# Gate 6A Result

**PASS**

Gate 6A — State & Persistence Contract 完成。审计确认 Settings/persistence 已有清晰的单一读写入口（`stores/settings.ts` + `stores/theme.tsx`），无需重构为 Context 或引入状态库；本轮只加固了唯一真实缺口——**持久化值的逐字段校验与 hydration 白名单**。未改 UI、路由、backend、API schema，未动 SearchDialog race（6B）与 mutation contract（6C）。

# Existing Architecture

进入时的 state/persistence 全景（全仓库 `grep localStorage|sessionStorage` 确认，无 sessionStorage）：

| Key | Schema | 读 / 写位置 | 模型 |
| --- | --- | --- | --- |
| `jlu-settings` | JSON `{pageSize, hideLowPriority, priorityThreshold, defaultHome}` | `stores/settings.ts` `loadSettings()` / `saveSettings()` | snapshot（非 reactive） |
| `jlu-theme` | `'light' \| 'dark' \| 'system'` | `stores/theme.tsx` ThemeProvider init / `setTheme` | reactive（React Context） |
| `jlu-sidebar` | `'collapsed' \| 'expanded'` | `AppShell.tsx` 本地 state / toggle | component-local，单一 owner |

- **Settings source of truth** = `localStorage['jlu-settings']`。唯一模块 `stores/settings.ts` 统一读写；`loadSettings()` = `{...defaults, ...JSON.parse(...)}` + `try/catch` 回退 defaults，**无逐字段校验**。
- 消费者各自在 render 调用 `loadSettings()` 取快照：`App.tsx` HomeRoute（`defaultHome`）、`DashboardPage`（`priorityThreshold` + `hideLowPriority`）、`NoticesPage` / `FeedPage` / `CompetitionsPage` / `FavoritesPage`（`pageSize`）、`SettingsPage`（`useState(loadSettings)` + `saveSettings`）。路由切换 unmount/remount，故每次进页读到新快照，功能自洽。
- **Theme source of truth** = `localStorage['jlu-theme']` + `ThemeContext`（`useEffect` 把 `.dark` class 打到 `documentElement`）；`useTheme()` 消费者 `AppShell`、`SettingsPage`；默认 `system`。init 为 `localStorage.getItem('jlu-theme') as ThemeMode || 'system'`，**无白名单校验**。
- 三个 key 均只有一个读写入口模块，不存在“多个组件各自管理同一 setting”；存在的是“多个组件 render 里调用同一 `loadSettings()`”的快照读取（代码气味，非 bug，本轮不改）。

# Problems Found

## 1. `loadSettings` 无逐字段校验（P2）

- **problem**：`jlu-settings` 是合法 JSON 但字段类型/取值非法时原样透传：`pageSize:"abc"`、`priorityThreshold:99` 或 `"70"`（字符串）、`hideLowPriority:"false"`（truthy 字符串）、`defaultHome:"/notices"`（非法 route）。
- **impact**：`DashboardPage` 会向 `/api/notices/important?min_score=abc` 发请求 → 后端 422；`HomeRoute` 会 `Navigate` 到任意/回退路径。手工改坏或旧版本遗留值可破坏页面行为。
- **reproduction**：`localStorage.setItem('jlu-settings', JSON.stringify({priorityThreshold:'abc'}))` 后进入 Dashboard，important 子查询 422 → 显示 HTTP error。
- **root cause**：`loadSettings` 只做浅合并 + JSON parse 保护，无 schema 层校验/强转。

## 2. theme 无白名单校验（P3）

- **problem**：`localStorage.getItem('jlu-theme') as ThemeMode` 直接断言，任意字符串透传。
- **impact**：非法值使主题 Select 无选中项，且 `apply()` 中 `theme === 'dark' || (theme === 'system' && …)` 恒 false → 静默浅色、永远无法进入 dark。
- **reproduction**：`localStorage.setItem('jlu-theme', 'banana')` 后进入设置页，主题下拉无选中项。
- **root cause**：init 无枚举白名单校验。

# State Contract

## source of truth

| 状态 | source of truth |
| --- | --- |
| Settings | `localStorage['jlu-settings']`（JSON），唯一读写模块 `stores/settings.ts` |
| Theme | `localStorage['jlu-theme']` + React `ThemeContext`（reactive） |
| Sidebar collapse | `localStorage['jlu-sidebar']` + AppShell 本地 state（单一 owner） |

## persisted state

`jlu-settings` = `{ pageSize: number; hideLowPriority: boolean; priorityThreshold: number; defaultHome: string }`；`jlu-theme` = `'light'|'dark'|'system'`；`jlu-sidebar` = `'collapsed'|'expanded'`。

## derived state

无持久化 derived state；`priorityThreshold` 只作为“用户 cutoff”影响 Dashboard important query 与 `/notices?min_score=`，不改变 notice 自身 semantic band（design.md §15）。

## defaults

`DEFAULTS = { pageSize: 20, hideLowPriority: false, priorityThreshold: 70, defaultHome: '/' }`；theme 默认 `'system'`；sidebar 默认展开。

## hydration

Settings：`loadSettings()` 在 consumer render / `useState` 初始化时从 localStorage 读取并 `parseSettings` 归一化；Theme：`ThemeProvider` `useState(readTheme)` 读取白名单校验后的值，`useEffect` 同步 `.dark` class。

## validation

`parseSettings(raw)` 为唯一校验边界：`pageSize ∈ {10,20,50}`、`priorityThreshold ∈ {60,70,80}`、`defaultHome ∈ {'/','/today','/deadlines'}`、`hideLowPriority === true`；数字字段接受数字字符串（`Number()`）；非法/越界 → `DEFAULTS`；未知 key 丢弃；非对象值 → `DEFAULTS`。`readTheme()` 白名单 `['light','dark','system']`，非法 → `'system'`。

## write path

`saveSettings(value)` 序列化整对象；`setTheme(value)` 写 `jlu-theme` 并更新 context；AppShell `toggleCollapse` 写 `jlu-sidebar`。写路径不改（仅 hydration 校验加固）。

# Changes

- `frontend/src/stores/settings.ts`：新增 `DEFAULTS` 常量与 `parseSettings(raw)`（逐字段白名单/强转/默认值），`loadSettings` 改走 `parseSettings`；`Settings` / `loadSettings` / `saveSettings` 对外签名与语义不变（零 consumer 改动）。
- `frontend/src/stores/theme.tsx`：新增 `THEMES` 白名单与 `readTheme()`，`ThemeProvider` init 改用 `readTheme()`；`setTheme` 写路径不变。
- 无其它生产代码修改，无新增依赖，未改 UI / 路由 / backend / API。

# Tests Added

新增 12 项（84 → 96，20 files）：

- `stores/settings.test.ts`（8）：默认值、合法 restore、partial merge、非法 JSON、非法/越界值强转默认、数字字符串强转、save→load round-trip、非对象/未知 key。
- `stores/theme.test.tsx`（4）：默认 system、非法值回退 system、合法值恢复、setTheme 持久化。

未删除、skip、todo 或弱化任何既有测试（Gate 5 的 84 项全保留）。

# Browser Verification

方法：headless Chrome（CDP，独立临时 profile，端口 9335）+ 既有 Vite `http://127.0.0.1:5173`（PID 23160）+ 既有后端 `http://127.0.0.1:8000`（PID 31724），均为前序会话已有进程，本轮只读复用、未终止。10/10 通过：

| 场景 | 结果 |
| --- | --- |
| 全新 profile 进入 /settings | 默认 `['system','70','20','/']`（theme/threshold/pageSize/defaultHome） |
| theme → dark | `.dark` 即时生效，body `rgb(9,9,11)`，`jlu-theme=dark` |
| theme → light | `.dark` 即时移除，`jlu-theme=light` |
| priority threshold → 80 | select 即时显示 80，`jlu-settings` 持久化 `priorityThreshold:80`（整对象归一化写入） |
| reload | `['light','80','20','/']` 完整 hydration 恢复 |
| 非法值注入（`jlu-settings='{bad-json'` + `jlu-theme='banana'`） | reload 后回退默认 `['system','70','20','/']` |
| 导航 / | Dashboard h1“晚上好”，无“无法连接本地服务” |
| 导航 /notices | h1“全部通知”，正常 |

未重跑 Gate 5 全 viewport matrix（本 Gate 无布局改动）。

# Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 20 files / 96 tests（84 → 96） |
| `npm run lint` | PASS — 0 errors |
| `npm run build` | PASS — 2788 modules |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 tests |

（沙箱拦截原生子进程/命名管道与原生 Tailwind oxide 模块加载，按既有先例以 `danger-full-access` 重跑；未改任何项目配置。）

# Preserved Behavior

以下全部 unchanged：

- Notices URL schema：`q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`。
- request lifecycle：AbortController + external signal + 15s timeout + cleanup。
- auto-read：按 notice id 的 `Set<number>`，每 id 恰好一次。
- routes / redirect / fallback / Sidebar / BottomNav IA。
- error taxonomy：`NETWORK_ERROR | TIMEOUT | ABORTED | HTTP_ERROR | NOT_FOUND`，ABORTED 静默。
- attachment `filename/url/type` 与外链安全闸门。
- NoticeList / NoticeCard / Filters / Notice Detail / Dashboard / Today / Deadlines / Favorites / Categories / Sources / SearchDialog UI 与 responsive/accessibility 行为。
- 所有 `loadSettings()` / `saveSettings()` / `useTheme()` / `setTheme()` consumer 调用点：**零改动**（`App.tsx`、`DashboardPage`、`NoticesPage`、`FeedPage`、`CompetitionsPage`、`FavoritesPage`、`SettingsPage`、`AppShell`）。

# Deferred

## Gate 6B

SearchDialog request race / concurrency / debounce-request architecture。

## Gate 6C

mutation response contract（read/favorite 返回类型）；API normalization、TanStack Query/cache governance、source filter data-driven architecture。

# Recommended Next Gate

Gate 6B — SearchDialog Request Race
