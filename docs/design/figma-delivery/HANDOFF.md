# Notice Hub · 开发交付规范

版本：1.0，2026-09-10。范围：独立 UI 设计提案。示例通知均为排版数据。

## 交付物与真实完成状态

已完成共享设计数据、本地预览、Figma 原生节点生成脚本、组件与变量定义、开发规范。在线 Figma 文件在创建后遇到 Starter MCP 调用额度限制，尚未写入设计节点。本地插件通过 Plugin API 类型检查与数据引用检查，但未在真实 Figma 中运行验收。

## 布局

| 区域 | 尺寸与行为 |
|---|---|
| Desktop | 1440 × 900，三栏阅读布局 |
| Sidebar | 282px，内容上下分布；底部设置与同步状态 |
| Notice List | 574px，52px 标题栏、36px 筛选栏、28px 分组栏、86px 通知行、40px 分页 |
| Global Toolbar | 56px，搜索字段 438 × 34 |
| Detail Reader | 584px，44px 工具栏；正文左右 32px；正文区域独立滚动 |
| Attachment Card | 46px，单行文件名、文件类型、下载动作 |
| 768 | 72px 图标侧栏 + 696px 列表；详情采用可返回阅读页 |
| 390 | 单栏列表，打开后进入详情，返回栏固定；详情正文可滚动 |

通知行通过低对比背景与空隙分隔，不使用后台表格。标题优先，来源与发布时间次之。未读、重要、截止和收藏是独立维度。

## 设计系统

- 45 个语义颜色角色，每个角色提供 Dark / Light 值。
- Primitives 基础色集合，Dark / Light 独立语义集合，Dimensions 间距与圆角集合。
- 语义颜色别名引用基础色；所有变量有明确 scope 与 WEB code syntax。
- 21 个间距值，以 4px 为基础，紧凑对齐允许 2px 半步。
- 圆角：0 / 4 / 6 / 7 / 8 / 10 / 12 / 999。
- 阴影：Popover `0 8px 24px rgba(0,0,0,.24)`；列表、阅读区不加阴影。
- 字体：Noto Sans SC。未提供时插件检查 Microsoft YaHei UI、PingFang SC 等中文字体，并要求有可用中文字体。

| Text Style | 字号 / 行高 | 字重 | 用途 |
|---|---|---|---|
| Title | 24 / 34 | Medium | 阅读标题 |
| Section | 16 / 24 | Medium | 面板与区段标题 |
| Notice | 15 / 22 | Medium | 通知列表标题 |
| Body | 14 / 22 | Regular | 控件、附件、说明 |
| Reader | 15 / 28 | Regular | 连续阅读正文 |
| Metadata | 12 / 18 | Regular | 来源、发布时间 |
| Label | 11 / 16 | Medium | 紧凑状态标签 |

本提案在已有颜色的基础上增设 `surface-hover`；调整 `text-muted`、`deadline-warning-fg`、`deadline-neutral-fg` 与 `focus`，提高小字号和焦点可读性。精确值见 `design-data.json` 的 themes。这些变更未写入应用 CSS。

## 组件清单

以下每个组件都有 Theme=Dark/Light 变体。共 47 种状态结构，双主题为 94 个变体；另有 36 个原生矢量 Icon masters。

| 组件 | State 变体 |
|---|---|
| Notification Row | Unread / Read / Selected / Hover / Focus |
| Source Item | Default / Hover / Selected |
| Deadline Badge | Today / Soon / Future / Expired |
| Status Badge | Unread / Read / Important |
| Tag | Neutral / Academic / Organization |
| Attachment Card | PDF / XLSX / Hover / Unavailable |
| Toolbar | Default / Saved |
| Search Bar | Default / Focus / Filled / Loading |
| Empty State | NoResults / NoFavorites / NoSelection / CaughtUp |
| Loading State | List / Reader |
| Error State | Network / Timeout / Server / NotFound |
| Button | Default / Hover / Focus / Pressed / Disabled / Primary |
| Navigation Item | Default / Active / Focus |

TEXT 属性用于标题、来源、日期、标签、文件名等。BOOLEAN 用于未读点、重要标记、收藏图标等。INSTANCE_SWAP 用于更换图标。页面由组件实例组成，图标为可编辑矢量，非栅格截图。

## 交互与数据契约

| 操作 | 后续实现规则 |
|---|---|
| 全部通知 | `/notices` |
| 未读 | `read=0` |
| 收藏 | `favorite=1` |
| 重要 | `min_score=70`，沿用现有筛选规则 |
| 来源 | `source=<id>`，来源是一等实体 |
| 搜索 | Ctrl K 聚焦，300ms debounce；Esc 清空或关闭；搜索结果变化重置 page |
| 打开通知 | 详情成功加载后按 id Set 去重自动已读；不改变原行为 |
| 收藏 | 独立操作，不触发行打开；失败回滚并反馈 |
| 键盘阅读 | ↑↓ 切换，Enter 打开，Tab 访问操作，2px focus ring |
| Deadline | Asia/Shanghai；相对时间可查看绝对年月日与时间；无值不显示 |
| 附件 | 保留 filename / url / type；不假设有 size；不安全 URL 禁用下载 |
| 加载 | 保留框架；后台更新不清空缓存；骨架在 reduced-motion 下静态 |
| 外链 | 由已有 ExternalAnchor / 桌面外链机制处理 |

URL schema 保留 `q / category / source / min_score / date_from / deadline_status / read / favorite / page / page_size`，不因设计标签自动新增路由。

错误分别显示 NETWORK_ERROR、TIMEOUT、HTTP_ERROR、NOT_FOUND；ABORTED 静默。404 明确为通知不存在。请求继续使用 AbortController、外部 signal、15s timeout 与 cleanup。

Figma 原型只连接主题预览与移动详情/返回；筛选、搜索、收藏、重试等展示为设计状态，不能视为真实应用功能。

## 验证

- 同一份设计数据生成的 HTML 预览：1440×900 深色/浅色、768×900、390×844 列表/详情，未检测到横向溢出。
- 移动详情滚动可到达原文入口。
- 13 类组件状态结构检查通过；组件依赖、字体角色、颜色、间距、圆角均能解析。
- 16 组关键文字/背景组合对比度均 ≥4.5:1，详细数值见 `verification.json`。
- 生成脚本通过 JavaScript 语法检查与 Figma Plugin API 类型检查。
- 仓库前端：28 个测试文件 / 149 项测试通过；lint 通过；build 通过。build 保留既有大于500kB chunk提示。
- 未执行真实 Figma 运行验收，不能把 HTML 预览的验证结果当作 Figma 完成截图。导入后仍需检查中文换行、组件属性、实例调整和原型滚动。
