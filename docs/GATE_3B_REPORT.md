# Gate 3B Result

**PASS**

Gate 3B — Design Tokens + UI Primitives 完成。Design Contract（Gate 3A / 3A.1，已冻结）已落实为最小、统一的 Tailwind v4 token 层与基础 UI primitives。未做业务页面重构，未新增任何 route，未改 API/URL/请求/auto-read/404/附件行为。

## Baseline

| 项 | 值 |
| --- | --- |
| 进入时 | 前端 18 tests（3 files）/ lint PASS / build PASS；后端 43 pytest |
| 完成时 | 前端 26 tests（6 files）/ lint PASS / build PASS；后端 43 pytest |
| Stack | Tailwind CSS v4（`@tailwindcss/vite`，CSS-first）+ Radix Dialog + React 19 + TanStack Query |

## Existing Primitive Inventory

| Primitive | Existing? | Current file | Gate 3B action |
| --- | --- | --- | --- |
| Button | Yes | `components/ui/Button.tsx` | Converged to tokens（primary/secondary/ghost/danger） |
| Input / Select | Yes | `components/ui/Form.tsx` | Converged to tokens + disabled 态 |
| Badge | Yes（仅 neutral） | `components/ui/Badge.tsx` | 新增 6 个 semantic variants（neutral/accent/success/warning/danger/important） |
| Card | Yes | `components/ui/Card.tsx` | Converged to tokens（surface/border/radius-large） |
| Skeleton / EmptyState / ErrorState | Yes | `components/ui/Feedback.tsx` | 视觉收敛；ErrorState 的 `ApiError.kind` 逻辑一字未改 |
| Pagination | Yes | `components/ui/Pagination.tsx` | 文本色/字号 token 化 |
| Toast | Yes | `stores/toast.tsx` | 容器/图标 token 化（surface-raised） |
| Toggle/Switch | 仅 SettingsPage 内联 | `pages/SettingsPage.tsx` | Deferred（无独立可复用 consumer，避免动页面） |
| IconButton | 仅内联 pattern | AppShell/dialog/NoticeCard | 不创建（无可迁移 consumer，避免触碰禁区文件） |
| Dialog / Sheet | Radix 内联使用 | `SearchDialog.tsx`、`AppShell.tsx` | Deferred 到 Gate 3C |
| Spinner | 无 | — | 不创建（无 consumer） |
| SettingRow | 仅内联 | `pages/SettingsPage.tsx` | Deferred |
| ExternalAnchor | Yes | `components/ui/ExternalAnchor.tsx` | 无视觉改动 |
| cn utility | Yes | `utils/cn.ts` | 扩展 tailwind-merge（登记 Gate 3B typography token） |
| theme | Yes（light/dark/system） | `stores/theme.tsx` | 未改（状态架构属 Gate 6） |

## Tokens Added（`frontend/src/index.css`）

### Colors（semantic，`:root` light / `.dark` dark + `@theme inline` 映射）

Design Contract name → implementation（Tailwind v4 utility）：

| Contract | Runtime var | Utility | Light | Dark |
| --- | --- | --- | --- | --- |
| color-bg | `--background` | `bg-bg` | zinc-50 | zinc-950 |
| color-surface | `--surface` | `bg-surface` | white | zinc-900 |
| color-surface-raised | `--surface-raised` | `bg-surface-raised` | white | zinc-800 |
| color-surface-muted | `--surface-muted` | `bg-surface-muted` | zinc-100 | zinc-800/60 |
| color-text-primary | `--text-primary` | `text-text-primary` | zinc-900 | zinc-100 |
| color-text-secondary | `--text-secondary` | `text-text-secondary` | zinc-600 | zinc-300 |
| color-text-muted | `--text-muted` | `text-text-muted` | zinc-500 | zinc-400 |
| color-text-inverse | `--text-inverse` | `text-text-inverse` | white | white |
| color-border | `--border` | `border-border` | zinc-200 | zinc-800 |
| color-border-strong | `--border-strong` | `border-border-strong` | zinc-300 | zinc-700 |
| color-accent | `--accent` | `bg-accent` 等 | indigo-600 | indigo-600 |
| color-accent-hover | `--accent-hover` | `hover:bg-accent-hover` | indigo-700 | indigo-700 |
| color-accent-soft | `--accent-soft` | `bg-accent-soft` | indigo-50 | indigo-950 |
| color-accent-soft-text | `--accent-soft-text` | `text-accent-soft-text` | indigo-700 | indigo-300 |
| color-success | `--success` | `text-success` 等 | emerald-700 | emerald-500 |
| color-warning | `--warning` | `text-warning` 等 | amber-700 | amber-500 |
| color-danger | `--danger` | `text-danger` 等 | rose-700 | rose-500 |
| color-important | `--important` | `text-important` 等 | amber-700 | amber-300 |
| color-unread | `--unread` | 未读点 | indigo-500 | indigo-500 |
| color-focus | `--focus` | focus ring | indigo-600 | indigo-500 |

> `color-accent-soft-text` 是实现层补充 token（契约中 accent-soft 为“底+字”对）。`color-deadline` 未引入；Deadline 复用 `color-text-muted` / `color-text-secondary` / `color-danger`。

### Typography（`--text-*` → `text-page-title` / `text-section-heading` / `text-notice-title` / `text-body` / `text-detail-body` / `text-metadata` / `text-label`）

### Spacing / Layout（`--spacing-sidebar-expanded` → `w-sidebar-expanded`；`--spacing-sidebar-collapsed`；`--spacing-header-height` → `h-header-height`；`--spacing-mobile-nav-height`；`--max-width-content-max` → `max-w-content-max`；`--max-width-detail-max`）

> 仅创建 token；Sidebar/Header/BottomNav/AppShell 实现属于 Gate 3C。

### Radius（`--radius-small/medium/large/xlarge` → `rounded-small/medium/large/xlarge` = 6/8/12/16px）

### Focus（全局 `focus-visible`：`2px solid var(--focus)` + `offset 2px`，覆盖 button/a/input/select/`[role="switch"]`）

### Motion（`--default-transition-*` = 150ms ease + 限定属性集；`prefers-reduced-motion` 全局压缩动画/过渡）

## Theme Implementation

- **light**：`:root` 定义全部 runtime 语义变量 + `color-scheme: light`。
- **dark**：`.dark` 覆盖同名变量 + `color-scheme: dark`（theme.tsx 继续切换 `documentElement` 上的 `.dark` 类）。
- **system**：theme.tsx 已有 `system` 分支（`matchMedia('(prefers-color-scheme: dark)')`），CSS 侧两个 token 集齐备，无需新代码。
- primitives 全部只写语义工具类，不再写 `dark:` 变体；旧页面保留的 `dark:` 变体继续可用（`@custom-variant dark` 未改）。

## Primitive Changes

- **Button**：variants → `bg-accent`/`bg-surface`/`bg-transparent`/`bg-danger` + `text-text-inverse`/`text-text-secondary` + `hover:bg-accent-hover`/`hover:bg-surface-muted`/`hover:bg-danger/90`；`rounded-medium`；disabled 保留。
- **Input / Select**：`bg-surface` + `border-border` + `text-text-primary` + `placeholder:text-text-muted`；新增 `disabled:cursor-not-allowed disabled:opacity-50`；原生 Select 行为保留（未做 custom select）。
- **Badge**：`variant` prop，6 个 semantic variants；`rounded-small` + `text-label`（11px）。
- **Card**：`rounded-large border-border bg-surface shadow-sm`。
- **Skeleton / EmptyState / ErrorState**：容器/图标 token 化；ErrorState 的 kind→文案/动作映射原样保留（404 专用页、offline 文案、重新连接均未变）。
- **Pagination**：`text-metadata tabular-nums text-text-muted`。
- **Toast**：`bg-surface-raised border-border`，成功/错误图标 → `text-success`/`text-danger`。
- **cn.ts**：`extendTailwindMerge` 将 `page-title/section-heading/notice-title/body/detail-body/metadata/label` 登记为 `font-size` group——否则 `text-label` 会被 tailwind-merge 当作颜色类，被后续 `text-indigo-700` 覆盖（smoke 实测发现的 16px→11px regression，已修复并加测试）。

## Contrast Results

WCAG 2.2 计算（全部组合实测，正文 ≥4.5:1、图形/UI ≥3:1）：

| 组合 | Light | Dark |
| --- | --- | --- |
| text-primary / bg | 16.97 PASS | 18.10 PASS |
| text-primary / surface | 17.72 PASS | 16.12 PASS |
| text-secondary / surface | 7.73 PASS | 11.99 PASS |
| text-secondary / surface-muted | 7.03 PASS | 10.87 PASS |
| text-muted / surface | 4.83 PASS | 6.91 PASS |
| accent-soft-text / accent-soft | 7.07 PASS | 8.02 PASS |
| text-inverse / accent | 6.29 PASS | 6.29 PASS |
| danger / surface | 6.29 PASS | 4.83 PASS |
| success / surface | 5.48 PASS | 6.98 PASS |
| warning / surface | 5.02 PASS | 8.25 PASS |
| important / surface | 5.02 PASS | 12.29 PASS |
| unread / surface（图形） | 4.47 UI PASS | 3.97 UI PASS |
| focus / bg（UI） | 6.02 PASS | 4.45 UI PASS |
| accent / surface（深色强调文字） | — | 2.82 **不达标** → 契约规则：深色表面强调文字用 `color-accent-soft-text`（8.02） |

为达标调整的参考 step（语义未变，已同步 `docs/design/design.md` §5）：light text-muted zinc-400→zinc-500；text-inverse dark zinc-900→white；dark accent indigo-500→indigo-600、accent-hover indigo-400→indigo-700（白字 4.5:1）；light success emerald-500→700、warning amber-500→700、danger rose-500→700（文字 4.5:1）；dark surface-raised → zinc-800。

## Browser Smoke

方法：headless Chrome（DevTools Protocol）+ Vite dev（5173，后端 CORS allowlist origin）+ 真实后端数据；模型无法读图，故用 CDP 计算样式探针验证（light/dark × 1366×768 / 390×844，含 `/` 与 `/notices`）。

| 检查 | 结果 |
| --- | --- |
| Desktop 1366×768 light/dark | body bg `rgb(250,250,250)` / `rgb(9,9,11)`，文字 `rgb(24,24,27)` / `rgb(244,244,245)`；sidebar flex、bottom nav none；无横向溢出 |
| Mobile 390×844 light/dark | sidebar none、bottom nav flex；scrollWidth 375 ≤ 390，无溢出 |
| 主题切换 | `html.dark` 正确落位，两套 token 集生效 |
| Migrated primitives | Input/Select/Card bg = surface（white / zinc-900）、border = color-border、radius 12px；Button accent `rgb(79,70,229)` + 白字两主题一致；Badge radius 6px + fontSize **11px**（cn 修复后） |
| 真实数据 | Dashboard“上午好”+ 4 张统计卡 + 真实通知列表；Notices 全部分类/来源筛选；后端在线 |
| Motion | 按钮 transition-duration 0.15s（150ms 基础） |
| Focus | 全局 `2px solid var(--focus)` + offset 2px 规则存在于产物 CSS |

smoke 结束后已按端口精确停止我启动的 8000/5173/9222 进程；`frontend/.smoke-*.log` 4 个临时日志仍被残留 wrapper 进程锁定（见 Risks，未继续杀进程）。

## Files Changed

- `frontend/src/index.css`（token 层 + focus + motion 基础）
- `frontend/src/components/ui/Button.tsx`、`Form.tsx`、`Badge.tsx`、`Card.tsx`、`Feedback.tsx`、`Pagination.tsx`
- `frontend/src/stores/toast.tsx`
- `frontend/src/utils/cn.ts`（tailwind-merge 扩展）
- 新增：`frontend/src/components/ui/Button.test.tsx`、`frontend/src/components/ui/Badge.test.tsx`、`frontend/src/utils/cn.test.ts`
- `docs/design/design.md`（§5 token 表按实测值冻结 + §6/§7/§8/§9/§25/§26 实施说明）
- `docs/GATE_3B_REPORT.md`（本报告）

未修改：页面文件、AppShell/SearchDialog/SettingsPage、backend、package/config、routes、API。

## Tests Added / Changed

新增 8 项（18 → 26）：Button 3（渲染、disabled 不触发 onClick、enabled 触发）、Badge 2（label 渲染、6 variants 可渲染）、cn 3（自定义字号 token 与颜色共存、语义色共存、真实冲突 last-wins）。既有 P1 回归（client/NoticesPage/NoticeDetailPage）全部保留且通过。

## Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 6 files，26 项 |
| `npm run lint` | PASS — 0 warnings / 0 errors |
| `npm run build` | PASS — 2784 modules |
| `.\.venv\Scripts\python.exe -m pytest` | PASS — 43 项 |

（沙箱拦截原生子进程/命名管道与 pytest 目录枚举，已按本会话既有拒绝先例以 `danger-full-access` 重跑；未改任何项目配置。）

## Preserved Behavior

- **URL schema**：未动（`q/category/source/min_score/date_from/deadline_status/read/favorite/page/page_size`）。
- **Request lifecycle**：未动（AbortController + external signal + 15s timeout + cleanup）。
- **Auto-read**：未动（`Set<number>` 按 id 去重）。
- **404**：未动（ErrorState kind 映射逐字保留，专用“通知不存在”+ 返回列表）。
- **Attachment**：未动（`filename/url/type`）。
- **Error taxonomy**：未动（`NETWORK_ERROR|TIMEOUT|ABORTED|HTTP_ERROR|NOT_FOUND`）。
- Theme 状态架构未改（Gate 6 范围）。

## Deferred

- 旧页面（Dashboard/NoticesPage/NoticeDetailPage/SourcesPage/SettingsPage/AppShell 等）仍含 `zinc-*`/`indigo-*` raw palette classes——**允许的 transitional state**，属 Gate 3C/4 迁移范围。
- Toggle/Switch 提取（SettingsPage 内联 consumer）→ 后续 Settings/Gate 4C。
- IconButton、Dialog/Sheet 统一 primitive → Gate 3C。
- `frontend/.smoke-backend.log`、`.smoke-backend.err.log`、`.smoke-dev.log`、`.smoke-dev2.err.log` 为 smoke 临时日志，仍被残留 npm/python wrapper 进程锁定；端口已全部释放，文件无害（gitignore 未覆盖），待 wrapper 进程自然退出后即可删除——未继续为此杀进程。

## Risks

- 自定义 `--text-*` 字号 token 依赖 tailwind-merge 的 `font-size` 扩展登记；新增字号 token 时必须同步 `utils/cn.ts`（已在文件内注释说明）。
- `bg-success/10` 等透明度修饰依赖 `color-mix`（现代浏览器 OK；产物 CSS 已含 fallback）。
- 深色表面强调文字必须用 `color-accent-soft-text`（`color-accent` 2.8:1 不达标）——规则已写入 design.md。
- 旧页面 raw classes 与 token 并存期间，视觉差异属预期；Gate 3C/4 逐页迁移。

## Recommended Next Gate

# Gate 3C — App Shell + Navigation

本 Gate 已完成，不自动开始 Gate 3C。
