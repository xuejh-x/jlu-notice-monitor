# Notice Hub · Desktop 设计交付

本次任务：创建面向高校学生的通知阅读应用设计，1440 × 900，深色优先。

## 交付状态

Figma MCP 在创建空白文件后返回 Starter 调用额度限制；在线设计节点尚未生成。此目录提供可在 Figma Desktop 中运行的本地开发插件，运行后生成原生可编辑页面、Auto Layout、组件集、实例、变量与文字样式。不是把预览图贴入 Figma。

1. 解压 `Notice-Hub-Figma.zip`。
2. 在 Figma Desktop 打开一个 Design 文件。
3. 菜单 → Plugins → Development → Import plugin from manifest，选择解压目录中的 `manifest.json`。
4. 运行 `Notice Hub · Build editable UI`，点击「创建可编辑设计」。

生成内容放在当前页面的独立区段，不覆盖已有节点。Starter 套餐使用两个单模式颜色集合（Dark / Light），组件通过 Theme 变体切换。

包含：5 个完整界面、13 类组件 / 94 个深浅色变体、45 个语义颜色角色、7 级文字样式、间距 / 圆角 / 阴影规范及状态页。详细设计与验证范围见 `HANDOFF.md`。

## 本次设计契约

本交付是独立设计提案，不自动替换现有产品实现或 `design-spec.md`。

- 主画布：1440 × 900；Sidebar 282，Notice List 574，Detail Reader 584。
- 用户指定的一级入口：全部通知、未读通知、收藏、重要通知；追加即将截止快捷视图，来源按学院 / 部门 / 组织分组。
- 移除原方案的处理进度统计，阅读和截止时间为主要任务。
- 通知行 86px：来源 / 发布时间，标题，标签 / 重要程度 / 截止时间 / 阅读状态；选中、未读和收藏互相独立。
- 采用现有语义颜色命名，12px 元数据、14px 控件、15px 正文、24px 阅读标题；无大标题、渐变、图表。
- Figma 字体采用可用的 Noto Sans SC，代码字体栈仍保留 Microsoft YaHei UI / PingFang SC / Noto Sans CJK SC。
- 桌面三栏 ≥1280；768 为列表与可返回的详情；390 为单栏列表与独立详情，不缩小桌面字号。
- 原有 URL 筛选参数、附件字段、自动已读、AbortController 与错误类型契约保持为后续实现约束。

设计数据均为排版演示，不代表真实已发布校园通知。

`preview.html` 是同一设计数据生成的本地预览。预览验证与 Figma 实际执行验证分开记录，不声称在线 Figma 稿已完成。
