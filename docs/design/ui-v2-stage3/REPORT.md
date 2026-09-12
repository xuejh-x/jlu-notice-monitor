# UI v2 · Stage 3 — Detail Reader 验收报告

日期：2026-09-11。状态：完成并暂停；未开始 Stage 4。

## 修改文件

| 文件 | 内容 |
|---|---|
| `frontend/src/pages/NoticeDetailPage.tsx` | 详情标题/标签/来源/日期/截止层级，正文容器，紧凑结构化信息及来源区，附件区；移动与404返回保留当前查询参数 |
| `frontend/src/components/notice/DetailToolbar.tsx` | 44px固定工具栏，32px控件，收藏/阅读/原文入口；收藏状态可访问语义 |
| `frontend/src/components/notice/NoticeContent.tsx` | 段间距与连续长字符换行；纯文本分段和转义保持不变 |
| `frontend/src/components/notice/AttachmentRow.tsx` | 46px附件行，文件名/类型截断与完整提示，文件标识、下载图标及不可用提示 |
| `frontend/src/index.css` | 仅详情专用工具栏高度、侧边距和内容宽度tokens |
| `frontend/src/pages/NoticeDetailPage.test.tsx` | 新增3项回归：正常/404返回查询参数、长附件名与不安全链接 |
| `docs/design/design.md` | 实施前记录Stage 3设计与适配边界 |

本目录保存验收截图与测量结果。未更改AppShell、Sidebar、Notice List、Sources、Settings、API、模型或OA文件。前两个阶段的未提交改动保持原状。

## 设计对应

唯一设计参考：`../figma-delivery/` 内的HANDOFF、组件数据、生成脚本和预览。交付包已注明在线Figma设计节点尚未完成验收；本次对应其本地交付规范。

| 设计 | 实现 |
|---|---|
| Detail Reader 584px | 桌面右栏保持584px。内容容器最大584px，左右各32px；现有右栏左边框占1px，因此1440实测正文519px，768实测520px且居中 |
| Title 24/34 Medium | 标题24px、行高34px，自然换行；分类/重要/阅读状态在上，来源与日期在下 |
| Toolbar 44px | 顶部固定；收藏、阅读状态按钮与原文链接沿用原回调；现有无更多操作，因此不增加空入口 |
| Reader 15/28 | 正文15px、行高28px、段间8px；长正文滚动，连续英文/URL可折行 |
| Deadline Badge | 复用已有20px徽章及deadlineDetail完整日期文案；Today/Soon/Future/Expired沿用既有语义判断 |
| Attachment Card 46px | 文件类型图标、文件名、类型、原有安全外链；长内容截断并保留完整提示；不可用链接无下载动作 |
| Mobile Reader | 390单栏，左右18px；返回栏与工具栏固定，长正文可到达底部原文入口 |

保留真实结构化通知信息及所有来源链接，不添加设计示例中的虚构学年/人群标签或截止提醒正文。原文大按钮变为底部紧凑链接。正文仍是后端提取后的纯文本，未增加HTML或Markdown解析。

## 测试与检查

| 检查 | 结果 |
|---|---|
| Frontend `npm test -- --run` | 28个文件，162项通过 |
| `npm run lint` | PASS |
| `npm run build` | PASS；主包518.56kB，保留既有500kB阈值提示 |
| Backend `.venv/Scripts/python.exe -m pytest` | 126 passed |
| 浏览器脚本错误 | 0 |

尺寸检查发现旧detail-content宽度token覆盖新值，已合并为单一定义并复测。新增测试使用严格模式，每次请求返回独立Response，未跳过或删除既有测试。

真实本地前后端与独立测试数据库验证，关闭启动同步和定时抓取；未操作用户实际数据库或真实OA。测试数据包括普通中文正文、80段长正文、800字符连续URL、长标题/发布单位、长附件名、PDF/XLSX和不可用附件。

- 1440×900深色/浅色：Reader584px、Toolbar44px、正文519px；标题24/34、正文15/28；附件46px。
- 768×900：阅读栏696px，正文520px居中；返回列表保留搜索词、来源及页码。
- 390×844：正文354px；无横向滚动；返回栏和工具栏在滚动后保留；可到达原文入口。
- 自动已读首次恰好一次，收藏/取消收藏不重复触发自动已读；手动标记未读/已读状态同步。
- 查询、mutation、自动已读代码块保持不变；查询参数返回只透传location.search，不改解析/序列化规则。
- 附件与原文仍使用现有ExternalAnchor及URL安全检查；未更改下载或外链打开机制。

测量及交互记录：[verification.json](verification.json)。

截图：[Desktop Dark](desktop-dark.png)、[Desktop Light](desktop-light.png)、[Tablet](tablet.png)、[Mobile](mobile.png)。长正文滚动：[Desktop](desktop-dark-scrolled.png)、[Tablet](tablet-scrolled.png)、[Mobile](mobile-scrolled.png)。

Stage 3 完成；停止于 Detail Reader。
