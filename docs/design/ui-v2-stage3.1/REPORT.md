# UI v2 Stage 3.1 — Detail Reader Visual Refinement

日期：2026-09-11。**Functional PASS / Visual FAIL（整体视觉验收尚未闭环）**。

已直接实施 refinement，完成真实开发环境截图和回归；Stage 4、OA Live Validation 均未开始。

## 修改文件与对应修复

| 文件 | 修复 |
|---|---|
| `frontend/src/pages/NoticeDetailPage.tsx` | 所有详情区段使用同一内容容器；标签/标题/来源日期/截止行重新组织；分隔线与正文间距16px，内容区段间距20px；原文与来源合并为紧凑底部区 |
| `frontend/src/components/notice/DetailToolbar.tsx` | 工具栏内层与正文同宽；按钮点击区外伸8px，首个图标与标题、正文左边界对齐；增加收藏pressed与操作active视觉 |
| `frontend/src/components/notice/NoticeContent.tsx` | 仅调整展示类；中文正文15/30，段间12px，保留原始分段、转义及连续字符折行 |
| `frontend/src/components/notice/AttachmentRow.tsx` | DOC/DOCX文档图标，46px行，8px行间距；压缩类型/操作占位，长名称中间省略并保留尾部10字符、完整title及可访问名称；hover/active反馈 |
| `frontend/src/index.css` | 新增详情专用共同容器规则，复用既有704px reader token与32/18px间距；不改变全局颜色、AppShell或List规则 |
| `docs/design/design.md` | 编码前同步Stage 3.1版型、字距/行距及边界约定 |

此外新增本目录的报告、截图及逐张几何JSON。没有修改API、Notice模型、crawler、OA、URL契约、外链安全、下载机制、AppShell、Notice List、Sources或Settings。未引入依赖。

## 实际环境与证据来源

- 前后端开发服务已重启：`127.0.0.1:5173` / `127.0.0.1:8000`，使用原数据库 `backend/data/notices.db`。
- 仅本次服务进程关闭启动同步和定时抓取；没有改动配置文件，没有启动OA Live Validation。
- Chrome为用户当前已连接的Chrome；原生桌面实测1707×923 CSS px、DPR 1.5。1440/768/390通过同一Chrome的尺寸覆盖验收，覆盖后的DPR约1；结束已恢复默认。
- 通知90：真实长标题、单段中文、3个长DOCX名称、无deadline。通知36：真实长标题、单段中文、过期deadline、6个DOC/DOCX附件及多个来源。未注入示例通知，未改正文/日期/附件。
- reference来自交付包 `preview.html?view=screen-0` / `screen-1`，只读本地服务打开并截图；结合HANDOFF、design-data和build脚本核对。
- before在改代码前于真实 `/notices/90` 捕获；不是此前独立种子数据库的Stage 3验收图。

## Reference / Before / After

| 环境 | Reference | Before | After |
|---|---|---|---|
| 1440 Dark | [设计预览](reference-dark.png) | [真实旧版](before-1440-dark.png) | [真实新版](after-1440-dark.png) |
| 1440 Light | [设计预览](reference-light.png) | [真实旧版](before-1440-light.png) | [真实新版](after-1440-light.png) |
| 默认1707×923 Dark | 同一1440设计基准，响应式扩展 | [真实旧版](before-wide-dark.png) | [真实新版](after-wide-dark.png) |
| 默认1707×923 Light | 同一浅色设计基准 | 未单独留存该尺寸before | [真实新版](after-wide-light.png) |
| 768×900 Detail | HANDOFF的可返回阅读页约定 | — | [真实新版](after-768.png) |
| 390×844 Detail | HANDOFF的单栏阅读约定 | — | [顶部](after-390.png)、[附件与来源](after-390-bottom.png) |

补充：[真实过期deadline与多附件](after-wide-deadline.png)、[收藏pressed状态](after-favorited.png)。

每张after主截图都有同名JSON测量记录。所有截图均在浏览器中逐张肉眼查看；未通过裁切、替换内容或图片修饰隐藏差异。

## 几何测量

| 场景 | Reader宽 | 正文宽 | 工具栏首图标/标题/正文/附件/来源左边界 | 横向溢出 |
|---|---:|---:|---:|---|
| before 默认宽屏 #90 | 851.33 | 520 | 工具栏约886 / 内容1022，错开约136px | 未见 |
| after 1440 Dark/Light #90 | 584 | 519.33 | 均888.67 | 无，scrollWidth=clientWidth=1440 |
| after 默认宽屏 Dark/Light #90 | 851.33 | 704 | 均930 | 无，scrollWidth=clientWidth=1707 |
| after 768 #36 | 680.67 | 601.33 | 均104 | 无，scrollWidth=clientWidth=753 |
| after 390 #36 | 374.67 | 338.67 | 均18 | 无，scrollWidth=clientWidth=375 |

宽屏每侧内容空白从约166px降至约74px。1440仍保留32px内边距。Chrome边框、原生滚动条和缩放导致小数尺寸；768与390表格记录的是实际可用尺寸，没有把768/390误写为内容宽度。

## 逐张视觉判断

- **1440 Dark/Light #90：Reader局部PASS。** 保持交付稿的小标签、24/34标题、低对比分隔线、紧凑工具栏和附件行。长标题两行、正文和附件同轴。比before减少底部重复的独立区段，文件名尾部可识别。
- **默认宽屏 Dark/Light #90：Reader局部PASS。** 内容扩展至704px；工具栏不再与孤立窄正文分离，标题、正文与底部共同居中。真实内容没有被拉伸成仪表盘或卡片栅格。
- **真实 #36：截止信息与附件样式PASS。** 截止行使用真实“已截止 · 2026-06-15”，六条附件、不同真实来源均保留；单段正文15/30，无人工标题/分段。
- **390：内容排版与可达性PASS。** 标题自然换行；正文、附件、底部可滚动到达，附件扩展名保持可见，返回/工具栏固定，无横向滚动。
- **768以及尺寸切换后的长详情：滚动版型未通过。** 截图中仍出现外层文档与Reader两根纵向滚动条，影响可用宽度和整体视觉。这一项阻止最终Visual PASS。

## Remaining Visual Differences

1. **未闭环：长详情的外层滚动条。** 768实测document clientHeight=900、scrollHeight=960，AppShell和body自身高度/scrollHeight都是900；HTML外有审计覆盖层。新建Chrome标签在默认1707×923打开同一#36时，document clientHeight=scrollHeight=923，只有Reader滚动条；尺寸切换/部分交互后现象重现。已有证据表明它随环境/页面状态变化，但不能据此断言完全由审计覆盖层引起。未通过修改AppShell、隐藏全局overflow或裁剪截图掩盖此问题。
2. **明确的展示适配：** 来源与发布时间允许同一行，deadline单列；正文由设计15/28调整为15/30，宽屏扩展至704px。保持同一视觉体系，但不是逐像素复制静态样例。
3. **内容差异仍可见：** 真实正文只有一个长段，后端空格仍保留；reference包含称谓、小标题、列表及额外标签。没有据此补造语义或修改解析。这类差异不代表渲染丢失，但单段长文本不可能呈现与人工分段示例完全相同的正文轮廓。

下一步应先隔离并定位第1项，在用户Chrome中复验长详情的滚动边界；定位前不能把测试通过等同于视觉通过，也不能宣称Stage 3.1已经视觉验收完成。

## 工程回归

| 检查 | 最后一轮结果 |
|---|---|
| `npm test -- --run` | 28个文件，162 passed |
| `npm run lint` | PASS |
| `npm run build` | PASS，主包519.44kB；保留既有>500kB提示 |
| `.venv/Scripts/python.exe -m pytest` | 126 passed |
| `git diff --check` | PASS |
| query / mutation / auto-read代码块 | 与Stage 3.1前本地副本逐字相同 |

浏览器中验证收藏及取消收藏，aria-pressed同步并恢复原false；列表状态随之更新。768和390点击返回均保留 `?source=csw&page=2`。外链和附件没有实际下载操作，仍由原安全组件处理。既有正文转义、安全附件、404与自动已读测试全部继续通过。

**最终：Functional PASS / Visual FAIL。** 已完成此次实现与如实交付，在尚有未闭环视觉项的状态下暂停；不进入Stage 4或OA Live Validation。
