# JLU Notice Monitor — Design Contract

> 本文件是前端产品化路线的 **Design Contract / Design System Specification**，属于 Gate 3A 的唯一交付物。
> 后续 Gate 3B（Design Tokens + UI Primitives）及之后所有 UI 改动都必须以本文件为准；与本文件冲突时，先更新本文件再改代码。
>
> 适用范围：`frontend/src` 下的所有页面、组件、样式与交互。
> 事实来源：当前代码（`frontend/src`、`backend/app`）、`docs/UI_AUDIT.md` 与各 Gate 报告。若本文件与代码存在出入，以本文件为“目标契约”，但不得在本 Gate 内改生产代码——差异记录为 deferred backlog。

---

## 1. Product Intent

JLU Notice Monitor 是一个面向学生的**个人信息阅读器 / 通知情报中心**，不是通用后台管理面板，也不是企业 ERP。

它把来自多个来源的通知**聚合、去重、抽取正文与附件、分类、评重要度、提取截止日期**，并让用户以最小成本回答四个问题：

1. 这条通知**跟我有没有关系**（来源 / 分类 / 面向对象）；
2. 它**重不重要**（重要度评分 / 分类）；
3. 它**什么时候截止**（截止状态 / 剩余天数）；
4. 我**要不要现在打开**（标题 + 摘要 + 元数据已经足以判断时，不必进入详情）。

产品的核心成功标准不是“展示很多卡片和指标”，而是**让用户在列表页就完成大部分分流判断**，只在需要正文、附件或原文时进入详情。

---

## 2. User Jobs

按优先级排序的用户任务：

1. **快速看到新通知** —— 今日新增、最新通知、未读数量。
2. **判断通知是否与自己有关** —— 来源、分类、面向对象（`target_students`）。
3. **判断重要程度** —— 重要度评分（`importance_score`）与优先级阈值。
4. **判断截止时间** —— 截止状态（`deadline_status`）、剩余天数（`days_until_deadline`）。
5. **阅读详情** —— 结构化摘要、原通知正文、关键信息。
6. **打开附件** —— 附件文件名与真实链接（`filename` / `url` / `type`）。
7. **打开原始来源** —— 原网页链接，Web 用新标签页、Tauri 用系统浏览器。
8. **保存 / 收藏** —— 星标收藏，集中回看。
9. **管理通知来源** —— 查看各来源健康状态与最近同步情况。
10. **配置偏好** —— 主题、每页数量、优先级阈值、默认首页。

来源在 UI 中永远是一等公民 `Source`（`code` + `name` + `status` + `base_url`），**不写死为“吉林大学 OA”**——除非某条真实字段本身就是来源名称。未来用户可能添加学院、其他高校、竞赛、奖学金、社团/活动等来源，设计不得阻止这一扩展。

---

## 3. Design Principles

每条原则都对应本产品的具体含义，不是空泛词汇：

| 原则 | 在本产品中的具体含义 |
| --- | --- |
| **Information-first** | 通知标题 + 重要度 + 截止时间优先于一切装饰；页面没有“为填充而填充”的卡片。 |
| **Scanability** | 列表页每行是可扫读的：标题一眼可读，重要度/截止聚成决策簇，来源/分类/时间聚成上下文簇。 |
| **Restrained** | 只用少量语义色与层级；不引入渐变、密集边框、堆砌指标卡。 |
| **Progressive disclosure** | 列表只放分流所需信息；摘要/正文/附件/原文在详情页展开。 |
| **Hierarchy over decoration** | 用字重、字号、间距区分层级，而不是用更多边框和颜色。 |
| **Responsive by design** | 桌面侧栏 + 移动底部导航是两套**重新组织**的目的地，不是同构件的机械缩小。 |
| **States are first-class** | loading / empty / filter-empty / search-empty / network-error / timeout / http-error / 404 各有独立、可区分呈现。 |
| **Accessibility is structural** | 键盘、焦点、语义、非颜色状态、触控目标、对比度在组件层就成立，而不是事后补丁。 |
| **Dark-first, dual-theme** | 默认气质偏深色，但 dark / light 是同一套 semantic tokens 的两个主题，不在组件里 hardcode 具体色值。 |
| **Source-agnostic** | 视觉与文案不绑定某个学校或 OA；来源是可增删的领域实体。 |

---

## 4. Information Hierarchy

通知字段的**最终视觉权重顺序**（1 最高）。所有元数据不得同权。

| 层级 | 字段 | 呈现位置 | 视觉处理 |
| --- | --- | --- | --- |
| 1 | 标题 `title` | 列表 / 详情 | 列表页最大字号、medium 字重、可点击；详情页为 h1。 |
| 2 | 重要度 `importance_score` + 截止 `deadline_status` / `days_until_deadline` | 列表 / 详情 | “决策簇”：截止带图标+颜色+文案，重要度带标签；两者可相邻但不混成一个数字串。 |
| 3 | 来源 `sources[].name` | 列表 / 详情 | 上下文簇第一位，是信任信号；比分类更靠前。 |
| 3 | 分类 `category` | 列表 / 详情 | Badge，与来源同级但视觉更弱。 |
| 3 | 发布时间 `publish_date` | 列表 / 详情 | 上下文簇末尾，muted 文字。 |
| 4 | 已读/未读 `is_read` | 列表 | 状态点 + 字重 + 无障碍文字，不能只靠颜色。 |
| 4 | 收藏 `is_favorite` | 列表 / 详情 | 星标 action，图标态 + 无障碍名。 |
| 5 | 摘要 `content` / 结构化摘要 | 仅详情 | 渐进披露，正文前先给摘要。 |
| 5 | 附件 / 原文链接 | 仅详情 | 附件文件名可读、链接真实。 |

**规则**：列表项不允许同时出现全部字段且等权排布；决策簇与上下文簇必须在视觉上可区分（间距、字号、颜色强度）。

---

## 5. Color System（Semantic Tokens）

- 使用 **semantic tokens**，组件内不直接写 hex / 任意灰阶 / 任意背景 / 任意边框。
- 支持 **dark + light**，二者共享同一组 token 名，只有值不同。
- 落地方式（Gate 3B）：以 CSS custom properties + Tailwind `@theme` 暴露为工具类；本 Gate 只定契约。
- 下表“参考值”使用项目当前 Tailwind palette 阶（`zinc` / `indigo` / `rose` / `emerald` / `amber` / `blue`），作为可执行的基线映射，Gate 3B 时统一收口，不再散落各组件。

### 5.1 Neutral / Surface

| Token | 角色 | Light 参考 | Dark 参考 |
| --- | --- | --- | --- |
| `color-bg` | 页面背景 | `zinc-50` | `zinc-950` |
| `color-surface` | 卡片、面板、列表容器 | `white` | `zinc-900` |
| `color-surface-raised` | 弹层、菜单、hover 浮层、toast | `white` + shadow | `zinc-800` |
| `color-surface-muted` | 内嵌凹区、说明块、次级区 | `zinc-100` | `zinc-800/60` |

### 5.2 Text

| Token | 角色 | Light 参考 | Dark 参考 |
| --- | --- | --- | --- |
| `color-text-primary` | 标题、正文主文字 | `zinc-900` | `zinc-100` |
| `color-text-secondary` | 摘要、次级说明 | `zinc-600` | `zinc-300` |
| `color-text-muted` | 元数据、占位、时间戳 | `zinc-500`（对比度 4.5:1，弃用 zinc-400） | `zinc-400` |
| `color-text-inverse` | 填充按钮/选中态上的文字 | `white`（accent 上 6.3:1） | `white`（同左；dark 弃用 zinc-900） |

### 5.3 Border / Divider

| Token | 角色 | Light 参考 | Dark 参考 |
| --- | --- | --- | --- |
| `color-border` | 卡片/列表/输入框分隔 | `zinc-200` | `zinc-800` |
| `color-border-strong` | 强调分隔（弹层、抽屉） | `zinc-300` | `zinc-700` |
| `color-overlay` | Dialog / Sheet 遮罩 | `zinc-950 / 55%` | `zinc-950 / 55%` |

### 5.4 Accent / Brand

| Token | 角色 | Light 参考 | Dark 参考 |
| --- | --- | --- | --- |
| `color-accent` | 主操作、active nav、未读点、focus | `indigo-600` | `indigo-600`（弃用 indigo-500：白字需 4.5:1） |
| `color-accent-hover` | accent 的 hover | `indigo-700` | `indigo-700`（弃用 indigo-400：白字需 4.5:1） |
| `color-accent-soft` | 选中/高亮底（badge 底） | `indigo-50` | `indigo-950` |
| `color-accent-soft-text` | accent-soft 上的文字 | `indigo-700` | `indigo-300` |

> **Brand TODO**：仓库内没有吉林大学官方品牌色规范。当前 `indigo` 仅作为过渡品牌色，不代表官方蓝。获得官方品牌规范后，在 Gate 3B/后续更新 `color-accent*`，并同步本文档。

### 5.5 Semantic Status

| Token | 角色 | Light 参考 | Dark 参考 |
| --- | --- | --- | --- |
| `color-success` | 健康、成功、已收藏确认 | `emerald-700`（弃用 emerald-500：文字 4.5:1） | `emerald-500` |
| `color-warning` | 警告、中等紧迫 | `amber-700`（弃用 amber-500：文字 4.5:1） | `amber-500` |
| `color-danger` | 错误、expired、紧急截止 | `rose-700`（弃用 rose-500：文字 4.5:1） | `rose-500` |
| `color-important` | 重要度（重要通知） | `amber-700` | `amber-300` |
| `color-unread` | 未读指示点 | `indigo-500`（图形 ≥3:1） | `indigo-500`（图形 ≥3:1） |
| `color-focus` | 可见焦点环 | `indigo-600` | `indigo-500`（≥3:1） |

> **Gate 3B 实施说明（已冻结）**：上述 token 已以 Tailwind v4 `@theme inline` 落地于 `frontend/src/index.css`。实现名与契约名一一对应：`color-bg` → `--color-bg` → 工具类 `bg-bg`，`color-text-primary` → `text-text-primary`，`color-border` → `border-border`，`color-accent-soft-text` → `text-accent-soft-text`，其余同理（完整映射见 `docs/GATE_3B_REPORT.md`）。light/dark 由 `:root` 与 `.dark` 上的运行时变量切换，组件不再写 `dark:` 变体。参考值按 Gate 3B 对比度实测调整（上表括号内注明弃用项）；`color-accent` 是填充/指示 token——深色表面上的强调**文字**请使用 `color-accent-soft-text`（8.0:1），不要用 `color-accent`（2.8:1 不达标）。

**规则**：语义色只用于“传达含义”，不用作大面积背景；大面积用 neutral surface。任何状态都不能只靠颜色传达（见 16 节 Accessibility）。

---

## 6. Typography

字体族（沿用 `index.css`，中文优先）：

```text
"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", system-ui, sans-serif
```

| 步骤 | 用途 | 字号 / 行高 | 字重 |
| --- | --- | --- | --- |
| `type-page-title` | 页面标题（h1） | `24px` / `32px`，`sm` 起 `30px`/`36px` | `700`，`tracking-tight` |
| `type-section-heading` | 区块标题（h2） | `16px` / `24px` | `600` |
| `type-notice-title` | 列表通知标题 | `15px` / `24px` | `500`（未读）/ `400`（已读） |
| `type-body` | 正文、说明 | `14px` / `20px` | `400` |
| `type-detail-body` | 详情正文 | `15px` / `32px` | `400` |
| `type-metadata` | 来源/分类/时间等元数据 | `12px` / `16px` | `400` |
| `type-label` | 标签、badge | `11px` / `16px` | `500` |

**规则**：
- 数字（页码、剩余天数、计数）使用 `tabular-nums`。
- 层级只通过 字号/字重/行高 表达，不通过颜色堆砌表达。
- 详情页 `type-notice-title` 提升为页面 h1（`page-title` 规格），与列表规格解耦。

> **Gate 3B 实施说明**：以上步骤已落地为 Tailwind v4 `--text-*` theme tokens（`frontend/src/index.css`）：`text-page-title` / `text-section-heading` / `text-notice-title` / `text-body` / `text-detail-body` / `text-metadata` / `text-label`。Typography 用样式 token，不创建 React wrapper 组件。

---

## 7. Spacing Scale

基于 4px 网格，全部使用命名阶，禁止 magic numbers（如 `15px`、`17px`、`13px`、`7px` 作为间距）。

| 阶 | 值 |
| --- | --- |
| `space-1` | `4px` |
| `space-2` | `8px` |
| `space-3` | `12px` |
| `space-4` | `16px` |
| `space-5` | `20px` |
| `space-6` | `24px` |
| `space-8` | `32px` |
| `space-10` | `40px` |
| `space-12` | `48px` |
| `space-16` | `64px` |

**布局级命名 token（Gate 3B 收口为变量，替代当前硬编码）**：

| Token | 值 | 说明 |
| --- | --- | --- |
| `layout-sidebar-expanded` | `232px` | 桌面侧栏展开宽 |
| `layout-sidebar-collapsed` | `72px` | 桌面侧栏折叠宽 |
| `layout-header-height` | `64px` | 顶栏高 |
| `layout-mobile-nav-height` | `68px` | 移动底部导航高 |
| `layout-content-max` | `1500px` | 内容列最大宽 |
| `layout-detail-max` | `1024px` | 详情页阅读列最大宽 |

> **Gate 3B 实施说明**：以上已落地为 Tailwind v4 theme tokens：`--spacing-sidebar-expanded`（→ `w-sidebar-expanded`）、`--spacing-sidebar-collapsed`、`--spacing-header-height`（→ `h-header-height`）、`--spacing-mobile-nav-height`、`--max-width-content-max`（→ `max-w-content-max`）、`--max-width-detail-max`。本 Gate 只创建 token，AppShell/Sidebar/Header/BottomNav 实现属于 Gate 3C。

---

## 8. Radius

| 阶 | 值 | 用途 |
| --- | --- | --- |
| `radius-small` | `6px`（rounded-md） | Badge |
| `radius-medium` | `8px`（rounded-lg） | 按钮、输入框、nav item、图标按钮 |
| `radius-large` | `12px`（rounded-xl） | Card、列表容器、附件行 |
| `radius-xlarge` | `16px`（rounded-2xl） | Dialog / Sheet |

> **Gate 3B 实施说明**：已落地为 Tailwind v4 `--radius-small/medium/large/xlarge` → 工具类 `rounded-small/medium/large/xlarge`，与 Tailwind 内置半径映射一致（6/8/12/16px），不建立第二套 radius 体系。

---

## 9. Elevation / Shadow

- **Light**：卡片用 `shadow-sm`；弹层 / toast / 抽屉用 `shadow-xl` 或 `shadow-2xl`。
- **Dark**：**不用高强度 shadow**。层级靠 `color-surface` 与 `color-border-strong` 的对比表达，至多保留极弱阴影。
- 顶栏 / 搜索遮罩可使用 `backdrop-blur`，仅限瞬态层。
- Dialog / Sheet 遮罩统一使用 `color-overlay`，组件内不再直接写 raw neutral palette。
- 禁止引入新渐变。

---

## 10. Layout

### 10.1 Desktop（≥ `768px`）

```text
┌────────────┬──────────────────────────────────────────────┐
│ Sidebar    │  Header（搜索 / 爬虫状态 / 主题）               │
│ 232/72px   ├──────────────────────────────────────────────┤
│ (fixed)    │  Content column（max 1500px，p-4/6/8）         │
│            │  阅读优先、单列正文、侧栏补充信息               │
└────────────┴──────────────────────────────────────────────┘
```

- **Sidebar**：左侧固定、可折叠（232px ↔ 72px）；不过度拥挤；分组见 11 节。
- **Header**：顶部 sticky（64px），承担快捷信息与工具：全局搜索、爬虫状态、主题切换。
- **Content column**：居中，最大宽 `1500px`；密度中等，列表用分隔行而非密集表格。
- **详情页**：正文单列，右侧为“关键信息 / 下一步 / 来源”补充列（`lg` 起），阅读列最大 `1024px`。

### 10.2 Mobile（< `768px`）

**不采用 `desktop sidebar → hamburger` 的机械缩小**，而是重新组织主要目的地：

- **Top bar**：只承担当前页面标题 / context、全局搜索、主题切换（空间允许时）；**不默认放 hamburger / menu**。
- **Bottom navigation**：固定 68px，承担主要目的地（首页 / 今日 / 截止 / 收藏 / 更多）。
- **`更多` 打开完整 navigation sheet / drawer，是移动端完整导航的唯一主要入口**；只有未来某个具体页面存在强需求时，才允许 Top Bar 单独出现菜单入口。
- **Filters**：使用 sheet / bottom sheet（触控友好），不是塞满一行的小下拉框。
- **Detail**：单列全宽，右侧补充列折叠到正文之后。
- 正文长标题换行，不出现文档级横向滚动。

### 10.3 Layering（z-index，最小约定）

从低到高，只在 Shell 层使用，禁止出现 `z-[9999]` 等任意值：

| 层级 | 值 | 元素 |
| --- | --- | --- |
| content | auto/0 | 主内容 |
| header | 20 | 桌面/移动顶栏（sticky） |
| sidebar | 30 | 桌面侧栏（fixed） |
| bottom nav | 40 | 移动底部导航（fixed） |
| overlay / sheet / dialog | 50 | Radix Overlay/Content、More panel |
| toast | 100 | 全局提示 |

---

## 11. Navigation

### 11.1 现有导航（Existing Navigation — 当前代码真实存在的 route）

以下全部是当前 `frontend/src/App.tsx` 中真实存在的 route，仅作事实记录。Design Contract **不要求为它们新增实现，也不要求删除**；它们的存在与否以真实代码为准。

| 分组 | 项 | Route |
| --- | --- | --- |
| 总览 | 首页 | `/` |
| 总览 | 今日 | `/today` |
| 总览 | 即将截止 | `/deadlines` |
| 分类 | 全部竞赛 | `/competitions` |
| 分类 | 算法竞赛 | `/competitions/algorithm` |
| 分类 | 网络安全 | `/cybersecurity` |
| 分类 | 实训 / 实习 | `/training` |
| 分类 | 科研 / 实验室 | `/research` |
| 分类 | 推免 | `/postgraduate` |
| 管理 | 收藏 | `/favorites` |
| 管理 | 全部通知 | `/notices` |
| 管理 | 数据源 | `/sources` |
| 管理 | 设置 | `/settings` |
| 兼容 | 算法竞赛旧路径 | `/algorithm` → `/competitions/algorithm`（重定向） |
| 兼容 | 未知路径 | `*` → `/`（回退） |

### 11.2 Target / Future Information Architecture（目标 IA，非 route 强制）

> 以下名称是产品方向 / future navigation candidates，**不代表当前必须存在独立 route**，也不代表未来必须新增 route。

- 今日、即将截止、分类快捷入口、竞赛、网络安全、实习、科研、推免 等，是信息架构层的产品方向。
- 分类入口未来可以实现为：**URL filter**、**saved view**、**shortcut** 或 **route**；具体形式在对应 Gate 根据真实架构决定。
- 当前代码中部分条目已以独立 route 实现（见 11.1），这是**当前实现选择**，不是 Design Contract 的强制要求。
- **Gate 3B / Gate 3C 不得因为 Design Contract 中出现这些名称而自动新增 route。**

### 11.3 顶部快捷区域

- 全局搜索（`Ctrl/⌘ + K`）。
- 爬虫状态（后端在线/离线 + 最近同步）。
- 主题切换。

### 11.4 Active state

- Light：`indigo-50` 底 + `indigo-700` 字 + medium。
- Dark：`indigo-950` 底 + `indigo-300` 字 + medium。
- 选中态不能只靠颜色：配合字重变化与 `aria-current`。

### 11.5 未读入口（已确定，不得回退）

**未读数量保持在顶部/总览层级**（首页“最新通知”区块标题旁显示“共 N 条未读”），**不重复放入 Sidebar**。避免与顶部状态重复。

### 11.6 Mobile bottom navigation

- 固定 68px，`md` 起隐藏。
- 项：首页 / 今日 / 截止 / 收藏 / 更多。
- **`更多` 是移动端完整导航 sheet/drawer 的唯一主要入口**（见 10.2）。
- 每项触控目标 ≥ 44px，含 icon + 文案，选中态同样带 `aria-current`。

---

## 12. Breakpoints

| 断点 | 视口 | 行为 |
| --- | --- | --- |
| `320px` | 最小 | 单列；无横向滚动；触控目标可达；正文可 reflow。 |
| `390px` | 常见手机 | 底部导航 + 顶栏；筛选用 sheet。 |
| `768px` | `md` | 侧栏出现、底部导航隐藏；卡片网格展开。 |
| `1366px` | 常见笔记本 | 完整桌面布局；Dashboard 双栏。 |
| `1440px` | 宽屏 | 内容列达到 `1500px` 上限后居中，不再无限拉宽。 |

> 规则：不是每个断点都要单独 CSS breakpoint；契约要求**行为已定义**，CSS breakpoint 在 Gate 3B/4 落地时按需建立。
> 320px 是验证下限，不通过 `html/body min-width` 强制根元素宽度；经典滚动条会占用布局宽度，强制 320px 反而会在 320px 视口制造横向溢出。

---

## 13. Notice Anatomy（领域核心组件）

列表项（`NoticeCard` / `NoticeRow`）至少呈现：标题、来源、日期、分类、截止、重要度、已读状态、收藏，可选摘要。**所有元数据不等权**（见第 4 节权重）。

### 13.1 决策簇（Tier 2，必须醒目）

- **截止**：`CalendarClock` 图标 + “截止 MM-dd” + “剩余 N 天”；颜色随 Deadline Semantics（下节）。
- **重要度**：离散标签（如“重要 / 高相关”），可附评分数字；不使用裸数字作为唯一表达。

### 13.2 上下文簇（Tier 3，弱化但可读）

- 顺序：`来源名` → `分类 Badge` → `发布 MM-dd`。
- 来源名是第一信任信号，优先于分类。

### 13.3 状态（Tier 4）

- **未读**：indigo 状态点 + 标题 medium 字重 + 无障碍文字“未读”。
- **已读**：neutral 点（`zinc-200` / `zinc-700`）+ 常规字重 + 无障碍文字“已读”。
- **收藏**：星标；已收藏为实心 amber，未收藏为描边 zinc，均带 `aria-label`。
- **已更新**：`status === 'updated'` 时显示“已更新”Badge。
- **已截止**：标题降为 `color-text-secondary`（仍可读，≥4.5:1），决策簇“已截止”用 muted；**不使用全局 `opacity-60`**（会破坏 muted 元数据对比度）。

### 13.4 详情页（`NoticeDetailPage`）

结构（Desktop `lg+` 为 article + 右侧关键信息列；Mobile 单列，关键信息在正文前）：

返回列表 → 分类/更新 Badge + 标题（h1）+ 收藏（独立 button）→ 决策簇（重要度标签 + 截止）→ 关键信息/结构化摘要 → 原通知正文 → 附件 → 来源 / 原通知链接。

- **决策簇**：重要度（复用 §15 语义带）+ 截止（复用 §14 语义）紧贴标题，先回答“重不重要 / 什么时候截止”。
- **结构化摘要 = 关键信息**：只使用 backend 真实提供的结构化字段（`target_students` / `registration_method` / `competition_level` / `registration_deadline` / `event_start` / `event_end` / `publish_date` / `sources`）。**不生成 AI 摘要**，不凭空造“是什么 / 适合谁 / 建议 / 下一步”等无字段支撑的文案；字段为空时省略或按语义显示“时间待定”等既有文案。
- **原通知正文**：`content` 为 backend 抽取后的 **plain text**（`parse_detail_html` 用 `get_text` + 空白归一），前端以 `NoticeContent` 纯文本渲染（无 `dangerouslySetInnerHTML`，无需 sanitizer），正文用 `type-detail-body`，长 token/URL 用 `break-words` 防溢出。
- **附件 / 原通知链接**：均为外链（`ExternalAnchor`，`target=_blank` + `rel=noopener noreferrer`，Tauri 用系统浏览器）；打开前经 `isSafeExternalUrl` 校验仅允许 `http(s)`。
- 右侧列（Desktop）承载“关键信息 / 来源”；正文阅读列（article）始终更宽（约 70% / 30%），**不做 50/50**。

---

## 14. Deadline Semantics

以 backend 真实字段 `deadline_status` + `days_until_deadline` + `registration_deadline` 为准：

| 状态 | 条件 | 文案 | 视觉 |
| --- | --- | --- | --- |
| no deadline | `registration_deadline == null` | `时间待定` | `color-text-muted`，无图标强调 |
| upcoming / normal | > 3 天 | `截止 MM-dd · 剩余 N 天` | `color-text-secondary` |
| soon / urgent | 0 < 天数 ≤ 3 | `3 天内截止` / `剩余 N 天` | `color-danger` 文字 + 图标 |
| today | == 今天 | `今天截止` | `color-danger` 文字 + 图标，最强 |
| expired | < 今天 | `已截止` | `color-text-muted`（标题降为 `color-text-secondary`，不用全局 opacity） |

**规则**：
- **Deadline 不设独立单用途颜色 token**；统一使用已有 semantic tokens（`color-text-muted` / `color-text-secondary` / `color-danger`）。
- 绝不只靠颜色传达；必须同时有文字文案 + 图标；expired 用 muted 语义 + 标题降级弱化（对比度优先于字面 opacity）。
- `deadline_status` 文案来源统一走 `utils/labels.ts` 的 `deadlineLabels`。

---

## 15. Importance Semantics

以 backend 真实字段 `importance_score`（0–100，连续）为准。

### 15.1 Importance Semantic Band（固定，领域语义，不受用户设置影响）

| 带 | 范围 | 标签 | 说明 |
| --- | --- | --- | --- |
| normal | `< 70` | 一般 | 默认不额外强调 |
| important | `70–89` | 重要 | `color-important` |
| high relevance | `≥ 90` | 高相关 | `color-important` 加强 |

### 15.2 User Priority Threshold（用户偏好，不改变语义标签）

Settings 的 `priorityThreshold`（60 / 70 / 80）是**用户偏好**，只影响：

- Dashboard priority / important query 的 cutoff；
- 用户“优先关注”集合的范围；
- 默认筛选或突出范围；
- 其他明确依赖该设置的行为。

它**不得改变 Notice 自身的 semantic label**。

**示例**：`importance_score = 75` 时，即使 `priorityThreshold = 80`，该通知的语义标签仍是「重要」；只是它不会进入用户当前的“优先通知”集合。

### 15.3 展示规则

- 展示应为离散标签（+可选数字），**不把裸 `优先级 N` 作为唯一表达**；当前裸数字展示记录为 Gate 4 deferred。
- 筛选 `min_score` 沿用现有 70/80/90（与 semantic band 的 70 边界一致）。

---

## 16. Read / Unread

| 状态 | 视觉 | 非视觉 |
| --- | --- | --- |
| unread | `color-unread` 状态点 + 标题 medium | 屏幕阅读器可读“未读” |
| read | neutral 状态点 + 标题常规字重 | 屏幕阅读器可读“已读” |

**规则**：
- 不使用“只有颜色/只有点”的表达；点 + 字重 + 无障碍文字三者并存。
- 自动标记已读（`Set<number>` 按 notice id 去重）是已闭环的 P1 行为，**设计不得改变其语义**，只能在其上叠加视觉。

---

## 17. Search

### 17.1 Global Search Dialog（`Ctrl/⌘ + K`）

- Radix Dialog；打开后焦点落入输入框；`Escape` 关闭并恢复焦点。
- 300ms 防抖；输入为空显示引导态“输入关键词开始搜索”。
- 结果列表：键盘可上下选择、`Enter` 打开详情、`Escape` 关闭。
- 状态：loading（“正在搜索……”）/ no result / error **三者分开**。

### 17.2 List Search（NoticesPage）

- 内联输入，300ms 防抖，`q` 写入 URL（`replace`），变更重置 page。
- 与全局搜索共用一套视觉语言。

### 17.3 状态契约

| 状态 | 呈现 |
| --- | --- |
| loading | “正在搜索……” |
| no result | 明确指向“没有匹配 ‘{query}’ 的通知”，并提供调整建议 |
| backend error | 使用 ErrorState 的 `NETWORK_ERROR` / `TIMEOUT` / `HTTP_ERROR` 分支，**不得回退成 no result** |

> 现状：SearchDialog 的错误分支会落到空结果（F-013 / Gate 2C Known Issue），保留到 Gate 4C / 6 处理；本契约定义目标行为。

---

## 18. Filters

### 18.1 Desktop

- 使用 **inline toolbar**（当前 NoticesPage 的筛选区），可按需折叠为 popover。
- 控件：搜索、分类、来源、最低优先级、起始日期、截止状态、阅读状态、收藏状态。
- 任一筛选变化重置 page=1（已闭环，不得破坏）。

### 18.2 Mobile

- 使用 **bottom sheet / filter sheet**，触控友好，不把 8 个控件横排塞满屏幕。
- sheet 内含“应用 / 重置”语义；结果数量与当前筛选在顶栏可见。

---

## 19. Pagination

- 与 Gate 2B URL state 完全相容，**不得破坏 URL schema**：
  `q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`。
- 组件形态：上一页 / “第 X / Y 页” / 下一页；`total_pages ≤ 1` 时隐藏。
- 默认 `page=1`、默认 `page_size` 不写入 URL；非法参数回退默认值。
- 翻页保留上一页内容（`placeholderData`），减少闪烁。

---

## 20. Loading

| 场景 | 呈现 |
| --- | --- |
| page loading | 骨架列表（`PageSkeleton`，5 条占位） |
| list loading | 骨架行（与真实行等高） |
| partial / widget loading | 局部小骨架（Dashboard 优先关注区） |
| 按钮内 loading | 内联 spinner / 禁用态，不阻塞整页 |

**规则**：内容区优先骨架屏；瞬时动作用禁用态/spinner。骨架用 `animate-pulse` + neutral surface，不用刺眼色。

---

## 21. Empty State

必须区分三类，不允许互相混用：

| 情况 | 标题 | 描述 |
| --- | --- | --- |
| 数据真为空 | 如“今天没有新的通知” | 说明“所有启用的数据源均已检查” |
| filter 无结果 | “没有找到相关通知” | “可以尝试调整筛选条件。” |
| search 无结果 | 指向查询词 | 明确没有匹配“{query}”，并给出建议 |

---

## 22. Error State

沿用 Gate 2C 已闭环的错误契约（`ApiError.kind`），**不得重混成通用失败**：

| kind | 标题 | 动作 |
| --- | --- | --- |
| `NETWORK_ERROR` | 无法连接本地服务 | “重新连接” |
| `TIMEOUT` | 请求超时 | “重新连接” |
| `HTTP_ERROR` | 暂时无法完成请求 | “重新连接” +（安全时）后端 detail |
| `NOT_FOUND` | 通知不存在 | “返回通知列表”，**不显示重试/离线文案** |
| `ABORTED` | （静默） | 无用户可见错误，交下一次有效查询 |

> 404 与 backend offline 是两回事，UI 必须可区分。这是 P1 闭环验收项，设计契约强制保留。

---

## 23. Forms / Settings

基础控件（Gate 3B 落地统一）：

| 控件 | 契约 |
| --- | --- |
| Input | 高 `36px`（h-9）、`radius-medium`、`color-border`、focus ring `color-focus` |
| Select | 同上，自定义下拉箭头，`appearance-none` |
| Toggle | `role="switch"` + `aria-checked`，36×22 起步，`color-accent` on 态 |
| Error | 控件下内联错误文案 + `aria-describedby`，`color-danger` |
| Help text | 控件下 muted 说明，`aria-describedby` |

**规则**：所有控件必须有可访问名称（`aria-label` 或 `<label>`）；错误与帮助文案走语义文字，不是纯红边框。设置项由 `SettingRow`（标题 + 描述 + 控件）统一承载。

Settings 页面按真实能力分为“外观”“通知偏好”“阅读与显示”等少量 section；section 使用 `h2`，设置项标题使用 `h3` 或等价可访问 label。`priorityThreshold` 只描述用户的优先集合 cutoff，不改变 §15.1 的固定重要度语义带。Gate 4C 只整理现有控件，不改变 localStorage persistence / reactivity 架构。

---

## 24. Dialog / Sheet

- 统一基于 Radix Dialog（已引入）：焦点陷阱、`Escape` 关闭、backdrop、关闭后恢复焦点。
- **Desktop**：对话框居中；遮罩 `bg-zinc-950/40` + 可选轻 backdrop-blur。
- **Mobile**：搜索可用顶部 sheet（`top-[12vh]`），全功能菜单/筛选用右侧或底部 sheet；触控目标 ≥ 44px。
- 必须有可访问标题（`Dialog.Title`）；纯内容弹层可 `aria-describedby={undefined}`，但不得缺失标题。
- 键盘：`Ctrl/⌘+K` 打开搜索；结果内方向键 + `Enter`；`Escape` 逐级关闭。

---

## 25. Motion

- **克制**：只用短时长过渡，不用装饰性动画。
- 参考时长：颜色/背景/hover `150–200ms`；dialog/sheet 进出 `200–300ms`。
- 过渡属性限定在 `color / background-color / border-color / opacity / transform`。
- **必须支持 `prefers-reduced-motion`**：用户偏好减少动效时，过渡退化为瞬时或无位移。

> **Gate 3B 实施说明**：已在 `index.css` 落地：Tailwind `--default-transition-*` 设为 150ms ease + 限定属性集（`transition`/`transition-colors` 自动遵循）；全局 `@media (prefers-reduced-motion: reduce)` 将动画/过渡压缩为瞬时。未引入任何动画库。

---

## 26. Accessibility（目标 WCAG 2.2 AA）

| 要求 | 本产品落地方式 |
| --- | --- |
| Keyboard navigation | 所有交互可用键盘；对话框焦点陷阱；结果列表方向键。 |
| Visible focus | 全局 `focus-visible`：`2px` 实线 `color-focus` + `offset 2px`，覆盖 link/button/input/select。 |
| Semantic HTML | `nav` / `main` / `article` / `h1→h2` / `dl` / `button` / `a`；不滥用 div 模拟控件。 |
| Screen-reader name | 图标按钮与表单控件均有 `aria-label` 或可见 label。 |
| No color-only state | 未读/已读、截止、重要度、来源状态均带文字/图标/字重；色盲可见。 |
| Touch target | 交互目标 ≥ 24×24px，移动端优先 ≥ 44×44px。 |
| Focus restoration | Dialog/Sheet 关闭后焦点回到触发点。 |
| Reflow | 320px 下无横向滚动。 |
| 200% text / 400% zoom | 布局不破损，内容不丢失。 |
| Contrast | 正文 ≥ 4.5:1，大字号/UI 组件 ≥ 3:1；muted 文字组合须在 Gate 3B 实测并达标。 |

> **Gate 3B 实施说明**：全局 `focus-visible` 已统一为 `2px solid var(--focus)` + `offset 2px`（`index.css`），覆盖 link/button/input/select/`[role="switch"]`，鼠标点击不显示焦点环。对比度已在 Gate 3B 实测（详见 `docs/GATE_3B_REPORT.md`）：全部正文组合 ≥ 4.5:1，unread/focus 图形组合 ≥ 3:1。

> 已知缺口（Gate 2C / UI Audit 记录，属 backlog）：SearchDialog 输入框缺独立 label、未读点视觉-only、部分 `zinc-400 on white` 组合需实测对比度。均不在本 Gate 修改，Gate 5/后续统一治理。

---

## 27. 已确定且不可回退的既有决策（Preserved）

以下决策已在前序 Gate 或产品讨论中确定，**设计实现不得推翻**：

1. **Dark-first，但支持 dark/light 切换**（`light` / `dark` / `system`，共享 semantic tokens），不做永久暗色主题。
2. **布局方案一**：左侧导航 + 顶部状态 + 阅读优先主区。
3. **未读留在顶部/总览，不重复进 Sidebar**。
4. **Notices URL schema 保留**：`q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`。
5. **请求生命周期保留**：`AbortController` + external signal + 15s timeout + cleanup。
6. **Auto-read 保留**：按 notice id `Set<number>` 去重，每 id 恰好一次。
7. **404 保留**：专用“通知不存在” + 返回列表，不与 offline 混同。
8. **附件契约保留**：`filename` / `url` / `type`。
9. **未来来源可扩展**：来源是 `Source` 抽象，不绑定吉林大学 OA。

---

## 28. Deferred Backlog（本 Gate 不处理）

| 项 | 归属 Gate |
| --- | --- |
| mutation response contract（read/favorite 返回类型） | Gate 6 |
| Dashboard important-query 错误态 | Gate 4C / 6 |
| persistent settings reactivity | Settings / Gate 6 |
| SearchDialog error UX | Gate 4C / 6 |
| `csw` duplicate React key | 对应组件 / Quality Gate |
| MSW | 后续自动化评估 |
| Playwright | Gate 7 |
| CI | Gate 7 |
| strict / style 全量治理 | 后续 |
| 重要度裸数字展示、未读点语义、搜索 label、对比度实测 | Gate 4 / 5 |

---

## 29. Remaining Core Pages（Gate 4C）

### 29.1 Dashboard

- 核心摘要最多 4 个学生可行动指标：今日新增、未读、紧急/即将截止等；不展示数据库行数或 crawler 内部计数。
- 页面顺序为 context → 核心摘要 → 优先关注 → 即将截止/最近通知 → 必要的来源状态。
- 通知区复用 `NoticeList` / `NoticeCard` 及 §13–15 的领域语义，不再创建 Dashboard 专用通知卡片。
- Dashboard 主查询与优先通知子查询的 loading / error / empty 分离；`ABORTED` 静默。

### 29.2 Sources

- Sources 是只读来源概览，采用紧凑 row/list，不伪造新增、编辑、删除或连接测试能力。
- `disabled` / `unconfigured` 是中性暂停状态，不显示为系统故障；`login_required`、`login_expired`、`unavailable` 按真实状态显示文字与 warning/danger 语义。
- `base_url` 与通知详情外链共用 `isSafeExternalUrl`；只有安全的 `http(s)` URL 才生成外链。

### 29.3 Collection pages

- Today、Favorites 与 route preset feeds 统一采用 `PageHeader` + result context + `NoticeList` + contextual loading/error/empty；分类 route 继续复用 `FeedPage`，不新增 route DSL。
- Deadlines 只消费现有 deadline endpoint 与 §14 元数据语义，不在前端另造截止算法。
