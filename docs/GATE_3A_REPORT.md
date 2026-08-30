# Gate 3A Result

**PASS**

Gate 3A — Design Contract / Design System Specification 完成。本轮只新增/修改文档，未改动任何生产 UI、API、URL、附件、auto-read 或 backend 行为。

## Repository Baseline

| 项 | 事实 |
| --- | --- |
| Frontend stack | React 19.2.8 + TypeScript 6.0.2 + Vite 8.2.2 + Tailwind CSS 4.3.3（`@tailwindcss/vite`）+ TanStack Query 5.102.8 + React Router 7.18.3 + Radix Dialog 1.1.23 + lucide-react + Tauri 2 |
| Backend stack | FastAPI + SQLAlchemy + SQLite，Python 3.13，pytest |
| Test runner | 前端 Vitest + React Testing Library + jsdom；后端 pytest |
| Routes | 16 条路由（见 `frontend/src/App.tsx`）：`/`、`/today`、`/deadlines`、`/competitions`、`/competitions/algorithm`、`/algorithm`(redirect)、`/cybersecurity`、`/training`、`/research`、`/postgraduate`、`/favorites`、`/notices`、`/notices/:id`、`/sources`、`/settings`、`*`(redirect) |
| Test baseline（进入时） | 前端 3 个测试文件 18 项；后端 pytest 43 项（Gate 2C 记录） |
| Git | `master`，工作区含大量未提交改动（`M`/`??`），本 Gate 未覆盖、未清理任何用户改动 |

## Inputs Read

- `README.md`、`frontend/README.md`、`backend/README.md`
- `frontend/package.json`、`frontend/vite.config.ts`、`frontend/tsconfig.app.json`、`frontend/.oxlintrc.json`
- `docs/UI_AUDIT.md`（Gate 1 事实基线 / frontend audit）
- `docs/GATE_1_5_P1_PLAN.md`（Gate 1.5）
- `docs/GATE_2A_REPORT.md`、`docs/GATE_2B_REPORT.md`、`docs/GATE_2C_REPORT.md`
- Frontend source：`App.tsx`、`index.css`、`types/index.ts`、`components/layout/*`、`components/notice/*`、`components/search/SearchDialog.tsx`、`components/ui/*`、`pages/*`、`stores/{theme,settings,toast}.tsx`、`api/{client,notices,dashboard,sources,crawler}.ts`、`utils/{labels,format,noticeSearchParams}.ts`
- Backend source：`app/api/routes.py`、`app/schemas/notice.py`、`app/classifier/rules.py`
- `git status` / `git log`

未发现既有 `docs/design/` 目录或其它 design 文档，因此按约定新建 `docs/design/design.md`。

## Product Design Decisions

最终设计原则（详见 `docs/design/design.md`）：

1. **Information-first**：产品是信息阅读器 / 生产力工具，不是 admin dashboard 或 ERP。
2. **Scanability + hierarchy over decoration**：标题 → 重要度/截止（决策簇）→ 来源/分类/时间（上下文簇）→ 状态/收藏；所有元数据不等权。
3. **Restrained**：少量语义色、无渐变、不堆砌指标卡。
4. **Progressive disclosure**：列表只放分流信息，摘要/正文/附件/原文在详情展开。
5. **Responsive by design**：桌面侧栏 + 移动底部导航是两套重新组织的目的地，不是同构件机械缩小。
6. **States are first-class**：loading / empty / filter-empty / search-empty / 各类 error 独立可区分。
7. **Accessibility is structural**：WCAG 2.2 AA，键盘/焦点/语义/非颜色状态/触控目标/对比度组件层成立。
8. **Dark-first, dual-theme**：深色气质但支持 dark/light/system，共享 semantic tokens。
9. **Source-agnostic**：来源是 `Source` 一等公民，不写死“吉林大学 OA”。

## Design System Summary

- **Colors**：semantic tokens（background / surface / surface-raised / surface-muted / text primary·secondary·muted·inverse / border / border-strong / accent / accent-hover / accent-soft / success / warning / danger / important / deadline / unread / focus），dark+light 双主题。accent 标记 **Brand TODO**（仓库无吉林大学官方品牌规范，当前 indigo 仅为过渡色）。
- **Typography**：中文优先字体族；7 档（page-title / section-heading / notice-title / body / detail-body / metadata / label）；层级靠字号/字重/行高，不靠颜色。
- **Spacing**：4px 网格 + 命名布局 token（侧栏 232/72、顶栏 64、移动导航 68、内容 max 1500、详情 max 1024），禁止 magic numbers。
- **Radius**：small 6 / medium 8 / large 12 / xlarge 16。
- **Elevation**：light 用 shadow-sm/xl/2xl；dark 不用高强度 shadow，靠 surface + border-strong 对比。
- **Layout**：桌面 = 左侧固定可折叠侧栏 + sticky 顶栏（搜索/爬虫状态/主题）+ 阅读优先内容列；移动 = 顶栏 + 底部导航 + filter bottom sheet，详情单列。
- **Navigation**：侧栏三组（总览 / 分类 / 管理）；active 态 indigo + 字重 + `aria-current`；**未读留在顶部/总览，不重复进 Sidebar**。
- **Responsive**：断点行为定义 320 / 390 / 768 / 1366 / 1440。
- **Notice anatomy**：决策簇（截止+重要度）与上下文簇（来源→分类→时间）视觉分离；未读=点+字重+无障碍文字；expired 整项 opacity 弱化。
- **States**：Deadline（no deadline / normal / urgent / today / expired）、Importance（normal <70 / important 70–89 / high ≥90）、Read/Unread、Loading、Empty（三类）、Error（沿用 `ApiError.kind` 五态）。
- **Accessibility**：WCAG 2.2 AA，逐项落地方式已写入。

## Existing Decisions Preserved

- dark-first but light/dark/system supported（shared semantic tokens）。
- layout 方案一（左侧导航 + 顶部状态 + 阅读优先主区）。
- 未读留在顶部/总览，不重复进 Sidebar。
- Notices URL schema 原样保留。
- P1 行为（request lifecycle / auto-read / 404 / attachment contract）原样保留。
- 未来来源可扩展（`Source` 抽象，不绑定吉林大学 OA）。

## Deferred Backlog

| 项 | 归属 |
| --- | --- |
| mutation response contract（read/favorite 返回类型） | Gate 6 |
| Dashboard important-query 错误态 | Gate 4C / 6 |
| persistent settings reactivity | Settings / Gate 6 |
| SearchDialog error UX | Gate 4C / 6 |
| `csw` duplicate React key | 对应组件 / Quality Gate |
| MSW | 后续自动化评估 |
| Playwright | Gate 7 |
| CI | Gate 7 |
| strict / style 全量治理；重要度裸数字、未读点语义、搜索 label、对比度实测 | Gate 4 / 5 |

## Files Changed

- `docs/design/design.md`（新增，Design Contract / Design System Specification）
- `AGENTS.md`（新增，Frontend Design Contract 规则）
- `docs/GATE_3A_REPORT.md`（本报告）

仅新增文档，未触碰任何生产源码、配置、测试或用户工作区改动。

## Validation

| 命令 | 结果 |
| --- | --- |
| `frontend: npm test -- --run` | PASS（见运行结果） |
| `frontend: npm run lint` | PASS |
| `frontend: npm run build` | PASS |
| `backend: .\.venv\Scripts\python.exe -m pytest` | PASS |

（以实际运行输出为准，数字变化时记录真实值。）

## Risks

- 文档契约与现有代码存在已知差异（裸重要度数字、未读点视觉-only、SearchDialog 错误回退为空、部分对比度未实测、magic layout 值尚未收口为 token）。这些是**目标契约 vs 现状**的差距，已全部记入 deferred backlog，不在本 Gate 修复，也不会破坏 P1 baseline。
- 后续 Gate 3B 落地 token 时若误改组件行为，可能回归 URL state / auto-read / 404。`AGENTS.md` 已加入强制约束。

## Recommended Next Gate

# Gate 3B — Design Tokens + UI Primitives

本 Gate 已完成，不自动开始 Gate 3B。
