# AGENTS.md — JLU Notice Monitor

本文件是所有 AI Agent（Codex / DeepSeek / 其他）在本仓库工作时必须遵守的约束。仓库事实优先：若本文件与代码冲突，先核实代码与 `docs/` 报告，再行动。

## 1. 项目一句话

面向学生的通知聚合、去重、筛选、阅读系统（FastAPI + SQLite 后端，React/TypeScript + Vite + Tailwind CSS v4 + TanStack Query + React Router 前端，Tauri 2 桌面壳层）。当前首先服务吉林大学相关通知，但产品与 UI **不永久绑定吉林大学 OA**。

## 2. 仓库布局

- `backend/` — FastAPI 应用、crawler、SQLite、pytest（`backend/.venv` 为本地 venv）。
- `frontend/` — React 前端（`frontend/src`），Vitest + React Testing Library。
- `docs/` — 审计与 Gate 报告（`UI_AUDIT.md`、`GATE_*_REPORT.md`、`GATE_1_5_P1_PLAN.md`）。
- `docs/design/design.md` — **Design Contract / Design System Specification（Gate 3A 起为 UI 唯一事实源）**。

## 3. 改动前必读

1. `docs/design/design.md`（任何 UI/样式改动）。
2. 相关 `docs/GATE_*_REPORT.md` 与 `docs/UI_AUDIT.md`（了解已闭环与 backlog）。
3. 相关 `frontend/src/**` 与 `backend/app/**` 真实代码；不凭猜测文件或 API。

## 4. Frontend Design Contract（Gate 3A 确立，强制）

- UI 改动前先读 `docs/design/design.md`。
- 复用现有 primitives（`src/components/ui/*`、`src/components/notice/*`、`src/components/layout/*`）。
- 不随意新增 token；颜色用 semantic tokens，禁止在组件里 hardcode hex / 任意灰阶 / 任意背景 / 任意边框。
- 不在 visual-only 任务中修改 API behavior / URL contract / attachment contract / auto-read。
- 每次 UI 改动必须在 desktop + mobile 两个形态下验证（≥ `768px` 与 `390px`）。
- 每次改动必须运行 `npm test -- --run`、`npm run lint`、`npm run build`（在 `frontend/`）。
- 有意的设计系统变更（新 token、新布局规则、新导航结构）必须先同步更新 `docs/design/design.md` 再改代码。
- Design Contract 中的导航名称（今日、即将截止、竞赛、网络安全、实习、科研、推免等）是目标 IA / future candidates，**不得因名称出现而自动新增 route**；分类入口未来形式（URL filter / saved view / shortcut / route）由对应 Gate 根据真实架构决定。

## 5. 不可回退的既有决策（Preserved Behavior）

- **URL schema**：Notices 的 `q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`。
- **请求生命周期**：`AbortController` + external signal + 15s timeout + cleanup（`src/api/client.ts`）。
- **Auto-read**：按 notice id `Set<number>` 去重，每 id 恰好一次。
- **404**：专用“通知不存在”+ 返回列表，不与 backend offline 混同（`ApiError.kind`）。
- **附件契约**：`filename` / `url` / `type`。
- **未读入口**：留在顶部/总览，不重复进 Sidebar。
- **主题**：dark-first 但支持 dark/light/system 切换，共享 semantic tokens。
- **来源抽象**：来源是 `Source` 一等公民，不写死“吉林大学 OA”。

## 6. 错误契约

`ApiError.kind` ∈ `NETWORK_ERROR | TIMEOUT | ABORTED | HTTP_ERROR | NOT_FOUND`。UI 必须区分这些状态，不得重混成通用失败；`ABORTED` 静默。

## 7. 验证命令

```powershell
# 前端
Set-Location frontend
npm test -- --run
npm run lint
npm run build

# 后端
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
```

预计基线：前端 18 项测试、lint/build PASS、后端 43 项测试。若数字变化，记录真实数字，不造假。

## 8. 工作区纪律

- 仓库常含用户未提交改动（`git status` 有多处 `M`/`??`）。**不要 reset、checkout 覆盖、clean、删除或整理这些改动**。
- 改动最小化；不顺手重构技术债；不因“更现代”替换现有架构。
- 不跨 Gate：完成当前 Gate 后停止，等待下一条指令。
- 当前 roadmap 以“前端产品化优化路线”（Gate 3A → 3B → 3C → 4A/4B/4C → 5 → 6 → 7 → 8）为准；旧的 `P1 → P2 remediation → P3 → UI redesign` 路线已作废。
