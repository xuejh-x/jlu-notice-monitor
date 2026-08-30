# Gate 3A.1 Result

**PASS**

Gate 3A.1 — Design Contract Correction 完成。本轮只修改两份 Design Contract 文档并新增本报告，**未修改任何生产代码**。

## Corrections Applied

### C1 Existing Routes vs Future IA

- **当前真实 routes**（`frontend/src/App.tsx`，已核实）：`/`、`/today`、`/deadlines`、`/competitions`、`/competitions/algorithm`、`/cybersecurity`、`/training`、`/research`、`/postgraduate`、`/favorites`、`/notices`、`/notices/:id`、`/sources`、`/settings`，以及兼容/回退 `/algorithm` → `/competitions/algorithm`、`*` → `/`。
- **重新标注为 future IA 的导航项**：今日、即将截止、分类快捷入口、竞赛、网络安全、实习、科研、推免等，在 `design.md` 11.2 明确为“目标 IA / future navigation candidates，不代表当前必须存在独立 route，也不代表未来必须新增 route”。
- 新增说明：分类入口未来可实现为 URL filter / saved view / shortcut / route，具体形式由对应 Gate 按真实架构决定；当前已有独立 route 仅是现有实现选择。
- **是否新增任何 route：No**（未改 `App.tsx` 或任何 route 文件）。
- 同步在 `AGENTS.md` 第 4 节增加一条强制规则：不得因 Design Contract 中出现导航名称而自动新增 route。

### C2 Mobile Navigation

最终契约（`design.md` 10.2 + 11.6）：

- **Mobile Top Bar**：只承担当前页面标题 / context、全局搜索、主题切换（空间允许时）；**不默认放 hamburger / menu**。
- **Bottom Navigation**：固定 68px，承担主要目的地：首页 / 今日 / 截止 / 收藏 / 更多。
- **More**：打开完整 navigation sheet / drawer，**是移动端完整导航的唯一主要入口**。
- 例外规则：只有未来某个具体页面存在强需求时，才允许 Top Bar 单独出现菜单入口。
- 保留：不使用 `desktop sidebar → hamburger` 的机械缩小模式。

### C3 Importance Semantics

- **Importance Semantic Band（固定，领域语义，不受用户设置影响）**：`< 70` 一般 / `70–89` 重要 / `≥ 90` 高相关。
- **User Priority Threshold（用户偏好）**：Settings `priorityThreshold`（60/70/80）只影响 Dashboard priority / important query 的 cutoff、用户“优先关注”集合、默认筛选或突出范围及其他明确依赖项。
- **解耦原则**：`priorityThreshold` 不得改变 Notice 自身的 semantic label。
- **示例已写入**：`importance_score = 75`、`priorityThreshold = 80` 时，标签仍是「重要」，只是不进“优先通知”集合。

### C4 Deadline Tokens

- `color-deadline` token 已删除（`design.md` 5.5 表格行移除；14 节表格与规则中的引用全部替换）。
- Deadline 视觉统一使用已有 semantic tokens：
  - no deadline → `color-text-muted`
  - normal / >3 天 → `color-text-secondary`
  - soon / today → `color-danger`（文字 + 图标）
  - expired → `color-text-muted` + 整项 `opacity-60` 弱化
- 新增规则：Deadline 不设独立单用途颜色 token。
- 未修改任何生产 CSS / Tailwind。

### C5 Markdown Cleanup

- 全文扫描 `docs/design/design.md` 与 `AGENTS.md` 的 code fence / inline code / 表格 / blockquote / heading / 空行。
- 两处 fenced block（`design.md` 字体族、桌面布局 ASCII 图；`AGENTS.md` 验证命令 powershell 块）确认结构完整，无需重建。
- 修正一处内联文本双空格（14 节规则“必须同时有 文字文案”→“必须同时有文字文案”）。
- 未进行无意义的大规模措辞重写。

## Files Changed

- `docs/design/design.md`（C1–C5）
- `AGENTS.md`（C1 一致性规则 + 验证 Markdown）
- `docs/GATE_3A_1_REPORT.md`（本报告，新增）

## Production Code Changed

**No**。未修改 `frontend/src/**`、`backend/app/**`、package files、tests、config、route、API、CSS 或 Tailwind。

## Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run`（frontend） | PASS — 3 个文件，18 项通过 |
| `npm run lint`（frontend） | PASS — 0 warnings / 0 errors |
| `npm run build`（frontend） | PASS — 2784 modules |
| `.\.venv\Scripts\python.exe -m pytest`（backend） | PASS — 43 项通过 |

说明：沙箱会拦截 Vite/rolldown/tailwind-oxide 的原生子进程（`spawn EPERM`）与 pytest 的 temp/cache 目录枚举（`WinError 5`）。本会话此前已对同一命令在同一环境下被拒绝并成功升级，因此直接以 `danger-full-access` 重跑取得上述真实数字；未修改任何项目配置。文档-only 改动，无回归可能。

## Design Contract Status

Design Contract 已完成 correction，**可作为 Gate 3B frozen baseline**。

## Recommended Next Gate

# Gate 3B — Design Tokens + UI Primitives

本 Gate 已完成，不自动开始 Gate 3B。
