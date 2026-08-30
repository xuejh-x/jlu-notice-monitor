# Gate 4B Result

**PASS**

Gate 4B — Notice Detail 完成。将 `NoticeDetailPage` 从“堆叠摘要卡片 + 假结构化文案”重构为清晰、可信、适合长时间阅读的通知阅读页：标题/决策簇优先，关键信息只用 backend 真实结构化字段，正文为纯文本安全渲染，附件/原通知链接经外链安全校验，收藏/自动已读/404/错误分类全部保留。未重构 Notice List / Filters、Dashboard、路由、API client 或 backend。

## Baseline

| 项 | 进入时 | 完成时 |
| --- | --- | --- |
| 前端测试 | 55（10 files） | 69（12 files） |
| lint | PASS | PASS（0 warnings / 0 errors） |
| build | PASS（2787 modules） | PASS（2789 modules） |
| 后端 pytest | 43 | 43 |

## Previous Detail Audit

进入时 `NoticeDetailPage.tsx` 为一个高度压缩的单行 JSX 组件，主要问题：

- **假结构化摘要**：`摘要` 卡片硬编码 `这是什么=暂无结构化摘要`、`建议=暂无结构化建议`，仅 `适合谁` 读到真实 `target_students`——三格子里两格是无字段支撑的占位文案。
- **假下一步**：`下一步` 卡片永远显示“当前未提取到明确行动项”，无对应字段。
- **正文**：`content.split(/\n+/)` 渲染，但 backend 抽取时 `normalize_whitespace` 已把空白（含换行）压成单空格，故正文是一整段；样式用 raw `text-[15px] leading-8 zinc-700/300`，未用 `type-detail-body` token。
- **元数据堆叠**：`关键信息` 用 `fullDate(null)` 返回“通知中未说明”，未按字段有无省略；截止与列表重复一个 Badge 化，未给详情更完整呈现。
- **附件**：`a.filename ?? '附件'`（无“附件 N”递增 fallback），未显示 `type`，外链无 scheme 校验。
- **来源**：`sources.map(s => Badge)` 弱化为几乎不可见的 footer，未突出“查看原通知”。
- **布局**：`lg:grid-cols-[minmax(0,1fr)_280px]` 已接近 70/30，但移动端把右侧栏直接堆到正文后，无“关键信息在正文前”。
- **loading**：复用 `PageSkeleton`（5 条列表占位），形状不符详情页。
- **404**：已用 `ErrorState` 的 `NOT_FOUND` 分支 + raw `bg-indigo-600` 链接（正确但未 token 化）。

## Target Detail Architecture

信息层级（自上而下，Desktop `lg+` 为 article + 右侧关键信息列，Mobile 单列、关键信息在正文前）：

```
返回通知列表
  分类 Badge +（已更新）
  h1 标题 + ★ 收藏（独立 button，44px）
  决策簇：重要度标签 + 截止（deadlinePresentation 语义）
  关键信息 / 结构化摘要（dl，仅真实字段）      ← Mobile 在正文前，Desktop 在右侧 aside
  通知正文（NoticeContent，type-detail-body）
  附件（filename + type + 外链）
  来源（source name + 查看原通知 + 发布单位）
```

- **article（左，~70%）** 与 **aside（右，300px / ~30%）** 用 `lg:grid-cols-[minmax(0,1fr)_300px]`，非 50/50。
- 移动端 `lg:hidden` 的 KeyInfoPanel/SourcePanel 与桌面 `hidden lg:block` 的 aside 是同一组件在两处按断点显隐（沿用本项目 NoticeFilters 的既有 dual-render 模式，生产环境仅一处可见）。

## Header / Title

- 返回链接文案保留“返回通知列表”，`to="/notices"`（§6：当前明确返回 `/notices`，不擅自设计 history 架构）。
- `h1` 用 `text-page-title`（24→30px / tracking-tight），`min-w-0 flex-1` 可多行换行，不被收藏按钮挤压。
- 分类 `Badge variant="accent"` + `status==='updated'` 时“已更新”Badge（保留）。
- 收藏为独立 `Button`（`aria-label` 收藏通知/取消收藏、`h-11 w-11` = 44px 触点、focus-visible、`Star` 实心 amber / 描边 muted），沿用现有 mutation，未改 response contract。

## Decision Information

标题下决策簇：重要度标签（`importanceLevel` 语义带，normal 不显示，important=重要 / high=高相关，`Badge variant="important"`）+ 截止（`deadlinePresentation`，danger 带 `CalendarClock` 图标，tone 映射与列表一致）。先回答“重不重要 / 什么时候截止”。

## Structured Information

`KeyInfoPanel` 为 `dl`（grouped definition list，非多卡片），**只渲染真实 backend 字段，字段为 null 直接省略**：

| 展示项 | 来源字段 | 说明 |
| --- | --- | --- |
| 报名截止 | `registration_deadline` + `days_until_deadline` + `deadline_status` | `deadlineDetail()`：无→时间待定；已截止→`已截止 · yyyy-MM-dd`；今天→`今天截止 · date`；≤3 天/正常→`date · 剩余 N 天` |
| 面向对象 | `target_students` | 为 null 省略 |
| 报名方式 | `registration_method` | 为 null 省略 |
| 竞赛级别 | `competition_level` | 为 null 省略 |
| 比赛时间 | `event_start` + `event_end` | 任一存在才显示 `start 至 end` |
| 发布时间 | `publish_date` | 为 null 省略 |
| 来源 | `sources[0].name`（fallback `publisher`） | 为 null 省略 |

**不生成 AI 摘要**，无“是什么 / 适合谁 / 建议 / 下一步”等无字段支撑文案；空字段省略，不显示 `-`/`N/A`/`null`/`undefined`。`deadlineDetail` 复用 `noticeMeta.ts` 既有 `isExpired`/`fullDate`，未复制第三套 deadline mapping。

## Article / Body Rendering

正文抽为 `NoticeContent` 组件：

- 输入为 **plain text**（backend `parse_detail_html` 用 `get_text("\n")` + `normalize_whitespace` 抽取，空白压成单空格——当前数据 76 条正文均无换行）。
- `content.split(/\n+/).filter(Boolean)` 分段（兼容未来含换行数据），每段 `<p className="text-detail-body break-words text-text-primary">`。
- `type-detail-body` = 15px / 32px（design.md §6），`break-words` 防长 URL / 无空格英文溢出。
- `content` 为空显示“尚未抓取到正文，请查看原网页。”
- 正文无 HTML，故无 tables/images/links/headings 需处理（见 HTML Security Boundary）。

## HTML Security Boundary

| 问题 | 结论 |
| --- | --- |
| 正文当前格式 | **plain text**（server 端 `get_text` + `normalize_whitespace` 抽取，非 HTML） |
| 是否 `dangerouslySetInnerHTML` | **否**（全仓库 `grep dangerouslySetInnerHTML|innerHTML|sanitize|DOMPurify` 无匹配） |
| 是否 sanitized | **无需**——React 将文本作为转义文本节点渲染，无 HTML 进入 DOM |
| script/style/event-handler 是否可执行 | **不可**——正文是文本节点，非元素 |
| 外链如何处理 | `ExternalAnchor`（`target=_blank` + `rel=noopener noreferrer`，Tauri `openUrl` 系统浏览器）；新增 `isSafeExternalUrl`（仅 `http(s):`）作为打开前闸门，`javascript:`/`data:`/`mailto:`/畸形 URL 一律不生成锚点 |
| inline style 是否保留 | **不涉及**——正文无 HTML，无 inline style |
| XSS 边界是否 acceptable | **是**。正文无 HTML 注入面；外链（来源/附件）经 scheme 白名单校验 |

`isSafeExternalUrl` 在附件与来源链接处生效：URL 不安全时不渲染 `<a>`（附件退化为纯文本行，来源省略链接），不会执行 `javascript:`。

## Attachments

- 契约 `filename` / `url` / `type` 保持。
- 显示 `FileText` 图标 + filename（`filename ?? '附件 N'` 递增 fallback，非 `undefined`）+ `type`（uppercase muted）+ 外链图标。
- 链接为 `ExternalAnchor`（安全校验 + `_blank noopener noreferrer`），显示 filename 而非长 URL；`truncate` + `min-w-0` 防溢出；每行 `rounded-large border p-3` ≥ 44px 可点击。

## Original Source

`SourcePanel`：逐个 source 显示 `name` + “查看原通知”链接（`text-accent-soft-text` + `ExternalLink` 图标，`ExternalAnchor` 安全校验）；`sources` 为空时 fallback 到 `notice.url`（名称 fallback `publisher`）。多来源正确列出（notice 36 有 2 条 source relation → 2 个链接）。`publisher` 存在时显示“发布单位”。来源不再是几乎看不见的 footer，但也不抢 title/deadline 权重。

## Favorite

沿用现有 `useMutation(setNoticeFavorite)`，`onSuccess` 失效 `['notice',id]` + `['notices']` + toast、`onError` toast，未改 mutation response contract；点击不导航；`aria-label` + focus-visible + 44px。

## Auto-read

`Set<number>` 按 notice id 去重的 effect **逐字保留**（仅格式化）；未改语义。浏览器回归：临时将 notice 11 `is_read` 置 0 → 打开 `/notices/11` → DB `is_read` 自动回到 1（POST `/read` 触发），随后恢复原状态 1（无净变更）。exactly-once 由既有 `StrictMode` 单测（3 条：A/B 各一次、重渲染不重读、已读不读）保证。

## 404 / Error

- `NOT_FOUND` → 专用“通知不存在” + “返回通知列表”链接（`to="/notices"`，Button primary token 化），无 retry、无 offline 文案。
- `NETWORK_ERROR` / `TIMEOUT` / `HTTP_ERROR` → Gate 3B `ErrorState`（“无法连接本地服务”/“请求超时”/“暂时无法完成请求” + “重新连接” retry）。
- `ABORTED` 静默。404 与 network error 严格分离（单测 + 浏览器均验证）。

## Loading

`DetailSkeleton`：back 占位 + 标题条 + 决策条 + 左正文多行 + 右面板占位（`animate-pulse`，`aria-label="正在加载"`，尊重 reduced-motion），非整屏 spinner，形状贴近详情页。

## Responsive

| 视口 | 结果 |
| --- | --- |
| 320×700 | 无横向溢出（overflow=0），aside 隐藏（`display:none`） |
| 390×844 | 无溢出（overflow=-15），aside 隐藏 |
| 768×1024 | 无溢出，aside 隐藏（`lg`=1024 起才显示，无 awkward half sidebar） |
| 1366×768 | 无溢出，aside `display:flex` |
| 1440×900 | 无溢出，aside `display:flex`，`max-w-detail-max`（1024px）不无限拉宽 |

长标题（notice 36）在 320 下自然换行无文档级横向滚动；正文长 token 由 `break-words` 约束；附件 filename `truncate`。

## Dark / Light

CDP 实测：`body` 背景 light `rgb(250,250,250)` ↔ dark `rgb(9,9,11)`；正文/标题/关键信息/附件/来源全部走 semantic tokens（`text-text-primary` / `text-text-secondary` / `text-text-muted` / `surface` / `border`），无正文 hardcode white/black。

## Accessibility

- 单页面 h1（标题）；区块 `h2`（关键信息 / 通知正文 / 附件 / 来源）+ `section`/`aria-labelledby`；关键信息 `dl/dt/dd`。
- 收藏 `aria-label`；附件链接名=filename（或“附件 N”）；来源“查看原通知”链接名；`target=_blank` + `noopener noreferrer`。
- 外链可区分（图标 + 文字）；错误/404 有 heading；焦点沿用 Gate 3B 全局 focus-visible；移动触点 ≥44px（收藏/附件行）。
- 图片 alt 无障碍限制：正文为纯文本，无内嵌图片需 alt（不适用）。

## Browser Verification

方法：headless Chrome（CDP，独立 profile，端口 9333/9334）+ Vite dev（5173，指向 8000 真实后端）+ CDP 计算样式/DOM 探针。27/27 检查通过。

| 场景 | 结果 |
| --- | --- |
| `/notices/11`（expired deadline 2025-03-22，importance 76→重要，algorithm_competition） | h1 `第41次CCF CSP认证报名通知`、重要标签、截止文本、收藏 `aria-label=收藏通知`、查看原通知 `href=ccst.jlu.edu.cn` + `target=_blank` + `rel=noopener noreferrer`、无溢出 |
| `/notices/13`（8 附件 .xlsx，无 deadline） | 附件链接 8 条、filename `25级唐班.xlsx` 显示、不显示 `DownloadAttachUrl` 原始 URL |
| `/notices/64`（deadline 2026-03-09 expired，competition_level 省级，2 附件） | 关键信息含“省级”与“已截止 · 2026-03-09” |
| `/notices/36`（6 附件，2 source relation） | 查看原通知链接 ≥2（多来源正确） |
| `/notices/999999` | “通知不存在” + “返回通知列表”（href=/notices），无“无法连接本地服务” |
| dark/light | body 背景 250,250,250 ↔ 9,9,11，正文/标题 token 双主题 |
| 320/390/768/1366/1440 | 无横向溢出；aside `<lg` 隐藏、`≥lg` 显示 |
| auto-read | notice 11 置 unread 后打开 → DB `is_read` 回到 1（POST `/read` 触发） |
| offline（throwaway 前端指向 dead 端口 8010，不触碰用户进程） | `无法连接本地服务` + `重新连接`，无“通知不存在” |

**Deadline 状态数据说明**：当前数据集 deadline 分布为 expired 8 / no_deadline 68，**无 upcoming(normal)/soon(urgent)/today 未来截止样本**——`soon/today/normal` 详情呈现由 `deadlineDetail` 单测覆盖，浏览器无法用真实数据验证，记录为 not available in current dataset。

## Tests Added

新增 14 项（55 → 69）：

- `utils/url.test.ts`（3）：`isSafeExternalUrl` http/https 通过、javascript/data/mailto 拒绝、空/畸形不抛错。
- `utils/noticeMeta.test.ts`（+4）：`deadlineDetail` 无 deadline/已截止/今天/soon+normal 四态。
- `components/notice/NoticeContent.test.tsx`（3）：空内容 fallback、危险 HTML 作为转义文本渲染（无 script/img 元素）、换行分段 + `break-words`。
- `pages/NoticeDetailPage.test.tsx`（+4）：收藏 action 可访问名 + 触发既有 mutation、原通知链接 href、network error 与 404 分离、真实 deadline 字段渲染。

既有 Gate 2C 断言（404、附件 filename、auto-read exactly-once、已读不读）全部保留。

## Files Changed

- `frontend/src/pages/NoticeDetailPage.tsx`（重写：header/决策簇/关键信息/正文/附件/来源/收藏/skeleton/404/error）
- `frontend/src/components/notice/NoticeContent.tsx`（新增，正文纯文本渲染器）
- `frontend/src/utils/url.ts`（新增，`isSafeExternalUrl`）
- `frontend/src/utils/noticeMeta.ts`（新增 `deadlineDetail`）
- `frontend/src/pages/NoticeDetailPage.test.tsx`、`frontend/src/utils/noticeMeta.test.ts`、`frontend/src/components/notice/NoticeContent.test.tsx`、`frontend/src/utils/url.test.ts`（测试）
- `docs/design/design.md`（§13.4 详情页结构修订：删除“是什么/适合谁/建议”假摘要，改为真实字段结构化摘要 + 正文纯文本安全边界）
- `docs/GATE_4B_REPORT.md`（本报告）

未修改：backend、`api/client.ts`、routes、AppShell、NoticesPage、Filters、Dashboard、Sources、Settings。

## Dependencies Added

None

## Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 12 files，69 项 |
| `npm run lint` | PASS — 0 warnings / 0 errors |
| `npm run build` | PASS — 2789 modules |
| `.\.venv\Scripts\python.exe -m pytest` | PASS — 43 项 |

（沙箱拦截原生子进程/命名管道与原生 Tailwind oxide 模块加载，按本会话既有拒绝先例以 `danger-full-access` 重跑 test/lint/build/pytest；未改任何项目配置。）

## Preserved Behavior

- **URL**：unchanged（`/notices/:id` 路由未改，返回 `/notices` 文案保留）。
- **Request lifecycle**：unchanged（AbortController + external signal + 15s timeout + cleanup；未改 `api/client.ts`）。
- **Auto-read**：unchanged（`Set<number>` by id，effect 逐字保留）。
- **404**：unchanged（专用“通知不存在”+ 返回列表，与 network error 分离）。
- **Attachment**：unchanged（`filename/url/type` 契约，filename 优先显示）。
- **Error taxonomy**：unchanged（`NETWORK_ERROR|TIMEOUT|ABORTED|HTTP_ERROR|NOT_FOUND`）。
- **Routes**：unchanged（未新增/删除/改 path/redirect/fallback）。
- **Notice List / Filters**：unchanged（Gate 4A 未被重构）。

## Deferred

- Dashboard 重构（Gate 4C）。
- SearchDialog error UX / race（Gate 4C / 6）。
- mutation response contract（Gate 6）。
- backend 正文段落抽取（当前 `normalize_whitespace` 把正文压成单段，属 crawler/extraction 层，Gate 4B 不跨入；前端已用 `break-words` + 可读排版兜底）。
- 未来截止样本（soon/today/normal）真实浏览器验证（当前数据集无此类数据）。
- Tauri 系统浏览器打开行为（Web `_blank noopener noreferrer` 已验证，Tauri 未 smoke，沿用既有 `ExternalAnchor` handler 未改）。

## Risks

- **正文单段可读性**：backend 抽取把换行压成单空格，长正文（如 notice 63 ≈ 2916 字）是一整段；段落重排属 backend extraction 层，Gate 4B 仅保证排版 + 溢出安全，未在 scope 内解决（记录为后续 backlog）。
- **外链安全**：`isSafeExternalUrl` 只在 detail 页来源/附件处生效；`SourcesPage` 的 `base_url` 外链与 list 组件未纳入本轮（Gate 4B scope 外，SourcesPage 属 Gate 4C）。
- **数据状态**：auto-read 回归临时改 `is_read`，已恢复原值（1）；未污染数据。unread 样本当前为 0，回归使用可恢复的临时置位。
- **预存后端**：8000 端口由一个非本轮启动的进程占用（`git`/会话外遗留），按 §58 未终止；offline 验证改用指向 dead 端口 8010 的 throwaway 前端完成，未触碰用户/既有进程。

## Recommended Next Gate

# Gate 4C — Remaining Core Pages

本 Gate 已完成，不自动开始 Gate 4C。
