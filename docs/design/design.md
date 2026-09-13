# UI v2 Design Contract

2026-09-10：用户指定 `figma-delivery/` 为本次 UI v2 唯一设计来源。本文件只记录分阶段实施范围与已核实的适配约束，不另立视觉方案。具体规范见 [交付规范](figma-delivery/HANDOFF.md) 与 `figma-delivery/design-data.json`。

## Stage 1 — 基础布局

- 1440×900 全窗口布局：Sidebar 282px，List 574px，Reader 584px；不再添加旧版窗口外边距。
- Header 56px；≥1280 使用三栏，额外宽度分配给阅读区；768–1279 为72px侧栏加单面板，列表/详情保持原组件与路由；<768 保留已有完整导航和通知返回能力。
- 主导航：全部通知、未读通知、收藏、重要通知；快捷入口：即将截止。设置、来源管理、提醒中心、手动同步必须可达。
- 现有 `source` 只允许 cse/ccst/csw/jwc/innovation/oa，使用已有 `NoticeFilters` 的来源名称。没有来源组织分类或未读统计字段，不虚构分组/数字，不新增筛选值。
- Header 复用 SearchDialog；输入 438×34px，在空间不足时可收缩；保留请求、键盘、取消及搜索跳转行为。
- 移除侧栏进度统计卡；同步状态与 CrawlerButton 放到底部。主题继续使用原 light/dark/system provider，不改变持久化默认行为。
- 全局颜色与7级字阶依照交付包；新 hover、spacing、shadow tokens 仅由交付包引入。保留既有 token 名以兼容现有组件。
- Stage 1 不修改通知行高度/状态结构、详情 Toolbar/metadata/content/attachments 的内部布局，也不修改 Sources/Settings 内容页。

## Stage 2 — Notice List

- 复用 `NoticeCard` 的 compact 模式（主列表实际行组件），不另建同用途组件；其他页面的普通卡片与 `NoticeRow` 保持不变。
- 行高86px、上下10px/左右18px；来源行18px、标题区24px、状态行20px，区段间距2px。无卡片圆角或阴影；选中背景、hover 背景、2px focus ring。
- 标题单行截断；来源与分类可收缩；发布时间、截止与收藏操作保持可见。显示现有分类、已读/未读、重要/高相关、已更新标签。
- 来源图标14px，不带底色块。Deadline 在列表内使用20px高度和 Clock 图标；today 用 danger，已有 danger（3天内）用 warning，未来/过期用 neutral。复用既有 `deadlinePresentation`/`isExpired`，不改变日期判断或文案计算；详情 Badge 保持原样。
- 列表标题栏52px、阅读筛选栏36px、结果状态栏28px、分页区40px。保留现有阅读 tabs、搜索输入、筛选弹窗、分页操作和实际“按截止时间”排序，不引入交付示例中的假排序或按日期重排。
- 390 单栏列表沿用86px行高，窄屏内容可截断但不能横向溢出。只在本列表调整共享组件的 opt-in 展示变体。
- Stage 2 完成并验证后暂停，不实施 Reader 或 Sources/Settings。

## Stage 3 — Detail Reader

- 只修改详情页及专用 Toolbar / Content / Attachment 组件，复用已有 Badge、SourceIcon 与外链组件；不改 AppShell、Sidebar、Notice List、Sources、Settings。
- Toolbar 高44px，桌面左右22px，操作控件32px；顶部固定，正文沿现有详情容器滚动。保留收藏、标记已读/未读和原文；无现成更多操作，因此不添加占位功能。
- 内容容器最大584px（包含左右各32px），桌面正文520px并居中；390使用18px侧边距。标题24/34 Medium，自然换行；元信息12/18，正文15/28，段间距8px。
- 顶部分类、重要/高相关与阅读状态；标题、来源、发布时间与Deadline。标签只读已有字段，不增加虚构的学年/人群标签或截止说明。
- Deadline复用已有计算、文案与20px徽章展示。正文保留当前纯文本分段和React转义，不能新增HTML/Markdown解析。
- 附件行46px：文件标识、截断文件名、类型、原有链接；不可用链接使用明确提示。不增加文件大小或改变外链/下载处理。
- 原有结构化信息与全部来源链接保留为紧凑区段，原文大按钮改为底部文字入口。移动返回和404返回保留当前 location.search，不改URL解析规则。
- 回归自动已读每id一次、收藏和阅读状态同步、附件安全、查询参数返回、长正文滚动以及1440/768/390无横向溢出；完成后暂停。

## Stage 3.1 — Detail Reader Visual Refinement

- 延续交付包的44px工具栏、24/34标题、15px正文、46px附件及语义颜色；本阶段只改详情展示，Stage 4和OA验证暂停。
- 详情内部统一使用 `detail-content-frame`：桌面左右32px，移动18px；1440时正文约520px。宽屏内容适度扩展至既有reader宽度704px，容器总宽768px；工具栏操作、Header、正文、附件和来源区共用此容器。工具栏按钮点击区向外延伸8px，图标与正文起点对齐。
- Header以标签、标题、来源/发布日期、独立截止行组织；无deadline不保留空行。标题至元信息12px，Header分隔线两侧16px；不补造示例标签。
- 正文保持纯文本分段和转义，15/30改善连续中文长段阅读，段间12px；正文至附件/补充信息20px，不人为分段或加入标题。
- 附件仍46px、间隔8px；DOC/DOCX采用文档图标，长名称保留尾部10字符（完整文件名保留可访问名称及title），类型与下载图标使用紧凑空间；安全链接契约不变。
- 底部原文与来源合并为同一紧凑分隔区，保留全部原始链接、来源及发布单位信息。
- 必须使用真实数据库通知90/36的长标题、单段正文、DOC/DOCX附件，在Chrome的1440深浅色、实际宽屏深浅色、768/390逐张检查。截图与自动化通过分别报告。

## Stage 3.2 — Visual Polish

- 以未改动的figma-delivery预览为基准；本轮允许对实际应用做同色系的对比度增强，而非声称所有颜色值逐字等于预览。预览文件与生成脚本不重新生成。
- Dark区域层次：保留深色画布/Sidebar，List调整为`#111d2c`、Detail为`#0f1824`、附件为`#152231`；选中为`#1b2745`、hover为`#19283c`，边界为`#2a374a`，不依赖整体透明度叠加。Light保持原有区域基色。
- 保持blue/purple为选中与操作语义；分类标签按交付Tag映射source-blue/source-green/deadline-warning/neutral。复用Badge建立NoticeCategoryTag供列表和详情共用，不更改分类值、标签名称和筛选行为。
- Today/Soon用不透明的danger/warning底色，保留现有截止计算；非交互徽章不添加伪点击状态。重要状态仍使用已有importance判断与黄色星标。
- 修复全局`font: inherit`盖过Tailwind控件字阶：将重置放入base layer，使控件12/18与设计一致。列表标题恢复Notice Medium，正文/元信息保持各自色阶。
- 交互按钮增加可辨识的hover边界/背景与active/pressed；附件使用统一蓝色文档/绿色表格/红色PDF标识与描边，保留真实链接和文件名。
- 本轮只修改展示样式及展示组件；不进入Sources/Settings实现或OA验证。真实Chrome同一通知截图对照，并检查深浅色、768/390，运行全部既有回归。

## Stage 3.3 — Reading continuity and scroll boundaries

- AppShell在所有断点使用固定`100dvh`并裁切document滚动；Header占固定行，通知工作区占剩余高度。Sidebar、Notice List、Detail Reader各自拥有唯一的纵向滚动容器。
- 390底部导航继续固定；列表和详情滚动容器预留导航高度，使页脚与最后一条附件可以滚动到导航上方。不得通过body padding或document滚动补偿。
- 自动已读仍按notice id去重并立即写入后端；成功后原地更新已缓存通知的`is_read`，将通知查询标记为stale但不立即重新请求。因此当前未读列表保留已打开行，并立即展示已读状态。
- 用户关闭详情重新进入未读列表、切换筛选/query key、显式刷新或重新加载应用时，重新请求真实列表；已读项届时按现有API筛选消失。不更改URL schema、API、模型、收藏或详情选择行为。
- 使用长正文和多附件通知验证1440×900、默认宽屏、768×900、390×844；document必须保持`scrollHeight === clientHeight`，且目标pane自身存在滚动时只出现该pane滚动。

## 不变边界

API、数据模型、抓取、自动已读、请求取消、错误类型、URL schema 和 OA 接口保持不变。共享 token 更新允许影响现有组件的颜色/字体，但不改变它们的功能或事件处理。

## Gate 13.5 — Sources management and global counts

- 来源管理按“我的订阅 / 云端共享来源 / 本地来源”组织；Cloud Shared Source 的创建入口必须始终可用，即使当前没有任何来源记录。
- 云端共享创建使用现有 Form、Button、Toggle、Badge 与语义 token，不新增视觉 token。表单顺序为来源信息、Test Fetch / Preview、一次性管理员认证、创建结果。
- Cloud 行展示名称、URL、类型、健康状态和最近更新时间；390px 下允许 URL 换行，不允许横向溢出。
- “全部通知 / 未读通知 / 重要通知 / 即将截止”均来自独立 Dashboard 聚合；列表筛选结果只能控制当前列表和分页，不得回写全局导航计数。
- 用户主动标记未读优先于自动已读；读状态 mutation 必须立即投影到详情、列表、搜索、Dashboard 最近通知与未读计数，再与服务端结果校准。

## Storage management — notification retention

- 设置页使用现有 `SettingsSection`、`SettingRow`、`Card`、`Button`、`Dialog` 与语义 token 提供“存储管理”；不得新增视觉 token 或在页面硬编码色值。
- 显示数据库大小、通知数量、可清理数量和上次清理时间。清理按钮必须先打开确认对话框，明确说明本地未读、收藏和高重要度通知会保留。
- 成功后刷新存储统计，并使通知列表、Dashboard 与搜索缓存失效；不改 URL schema、通知阅读语义、来源、Crawler、Cloud Feed 或提醒状态机。
- 窄屏确认对话框沿用 `w-[min(92vw,440px)]`，页面在 390px 不得产生横向溢出。

## Gate 13.6 / OA 公开源后续决策 — advanced Cloud HTML and OA 校内通知

- 经真实环境核实，OA 首页“校内通知”列表与详情无需登录。该来源改为 `OFFICIAL_CLOUD` / `source_scope=official` / `execution=cloud` / `cloud_policy=force_enabled`，名称为“吉林大学 OA 校内通知”。
- Sources 页面把 OA 校内通知列入“我的订阅”，不展示首次登录、重新登录、Chrome Runtime、Cookie、Credential 或 Private Source 操作；Desktop 只同步 Cloud Feed，不直抓 OA URL。
- OA 公开适配器使用列表元数据做增量分流，详情页才解析正文与附件；继续复用统一去重、正文清洗、重要性、截止日期和 Notification 流水线。
- 云端共享来源的自动预览失败后展开“高级 HTML 配置”，字段为列表元素、标题、URL、时间 CSS Selector。配置以 `parser_config.type=html_selector` 保存，并由 Desktop 预览与 Cloud Worker 的同一 HTML parser 执行；若初始 HTML 为空，使用系统 Chrome 无界面渲染并等待列表 Selector。
- 动态渲染的每个 HTTP(S) 请求在 CDP 放行前必须通过现有来源 URL 安全校验；不得为了兼容 SPA 绕过私网、localhost、协议或重定向边界。Cloud Worker 未安装兼容 Chrome 时显示明确的渲染 Runtime 错误。
- 高级配置不绕过预览门禁：用户修改 Selector 后必须重新 Test Fetch / Preview 成功，才能管理员认证并写入 Cloud Registry。创建后仍保持 `cloud_source_id` / `execution=cloud`，Desktop 不重复抓取。

## Stage 17.1 — Execution policy foundation

- Sources 页面为每个来源只读展示执行策略：`cloud_preferred` 显示“云端优先”，`cloud_only` 显示“仅云端”，`local_only` 显示“仅本地”；不提供用户修改入口。
- `execution_policy` 仅作为未来 Hybrid Execution 的策略元数据；本阶段继续由既有 `execution`、ownership 与 deployment role 决定实际执行位置，不实现 fallback、circuit breaker 或 scheduler 行为变化。
- Official Public Source 默认 `cloud_preferred`，Shared Cloud Source 默认 `cloud_only`，Custom Local Source 默认 `local_only`。OA 使用 Official Public Source 的通用规则，不增加 OA 专用 UI 或执行分支。

## Stage 17.2 — Cloud preferred local fallback

- Desktop 上的 Official Public Source 且 `execution_policy=cloud_preferred` 时，一个 SourceRun 先执行 Cloud Feed；仅在 Feed 未配置、网络错误、超时、HTTP 错误、响应无效或云端数据过期时，串行执行该来源已有的 Local Adapter。Cloud 返回空列表仍视为成功。
- 同一 SourceRun 只产生一个最终结果，并记录 `attempts`、`effective_execution`、`fallback_used` 与 `fallback_reason`。Shared Cloud、Custom Local 与 Private Source 不启用 fallback，不新增独立调度器。
- Sources 页面只读显示当前执行状态：“云端运行”或“本地回退生效”；不增加策略编辑入口。回退状态复用现有 Badge 与语义色，不新增视觉 token。
- Cloud Feed 与 Local Adapter 通过 `origin_item_key` 对齐来源内通知身份：优先来源原生 ID，否则使用 canonical URL 的 SHA-256。该身份落在来源关系上，继续复用既有 Notice 去重和 NotificationEvent 去重流程。
- 本阶段不实现 circuit breaker、half-open probing、自动恢复编排、多设备同步，也不修改 NotificationEvent / NotificationDelivery 状态机。

## 验收

每阶段运行后端 pytest、前端 `npm test -- --run` / `npm run lint` / `npm run build`；检查1440×900深浅色、768与390布局、导航/搜索/主题/菜单回归。Stage 1 完成后停止，等待用户指示。
