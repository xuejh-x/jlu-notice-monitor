# Stage 3.2 — Visual Polish 验收

日期：2026-09-11。范围：颜色层次、强调色、字阶及通知组件的视觉状态。Stage 4 与 OA Live Validation 继续暂停。

**Stage 3.2 本轮视觉语言验收：Visual PASS。工程回归：PASS。**

此结论针对下列已截图、逐张目视检查的场景，不表示整个 UI v2 的所有历史问题已经关闭。Stage 3.1 记录的通知 #36 在尺寸切换后可能出现双纵向滚动条的问题，本轮没有在 Chrome 中重新隔离复验，仍保留未闭环状态；见文末。

## 对比依据与证据

- Reference：未经本轮修改的 `figma-delivery/preview.html` 的 Dark / Light 页面；规范来自同目录 HANDOFF、design-data、build。
- Before：Stage 3.2 修改前真实 Chrome 的 `/notices/90`，文件使用 `current-*` 命名。
- After：同一真实通知 `/notices/90`，未替换正文、附件或元数据，使用 `after-*` 命名。
- [打开并排对比页](comparison.html)。所有图片均保留原截图，未重绘、拼接或裁剪页面内容。
- `current-user-snapshot.png` 是用户当时浏览的另一条通知，不作为同数据 before/after 证据。

| 场景 | Reference | Before | After |
|---|---|---|---|
| 1440×900 Dark | [设计](reference-dark.png) | [修复前](current-1440-dark.png) | [修复后](after-1440-dark.png) |
| 1440×900 Light | [设计](reference-light.png) | 未保存本轮修复前浅色截图，不重建冒充历史截图 | [修复后](after-1440-light.png) |
| 1707×923 Dark | 沿用1440设计基准 | [真实宽屏修复前](current-wide-dark.png) | [真实宽屏修复后](after-wide-dark.png) |
| 1707×923 Light | 沿用1440设计基准 | 未保存本轮修复前浅色截图 | [真实宽屏修复后](after-wide-light.png) |
| 768×900 Dark | 沿用交付包响应式规则 | — | [详情](after-768.png) |
| 390×844 Dark | 沿用交付包响应式规则 | — | [详情顶部](after-390.png)、[附件与来源](after-390-attachments.png) |

上述整页截图来自已连接的用户 Chrome；宽屏实测1707×923、DPR1.5。补充组件验收时 Chrome 连接已不可用，因此 [语义色状态图](after-semantic-states.png) 使用 Codex 内置浏览器1440×900，**只作真实组件的隔离状态检查，不冒充 Chrome 实际通知页面**。使用测试 Notice 字段展示不同状态，没有写入数据库或触发收藏、下载、原文访问。

## 逐项视觉比较

| 项目 | Before 的问题 | After 的观察与判断 |
|---|---|---|
| 区域颜色 | Sidebar、列表、Reader接近同一灰黑；分栏与附件不易辨认 | Dark列表呈清晰深蓝层，Reader更沉静，Sidebar更深；边界可辨而不抢正文。Light维持浅灰侧栏、微蓝列表和白色Reader。与参考属于同一阅读产品视觉体系。PASS |
| 选中与强调 | 选中行较暗；分类/状态大面积灰化 | 导航、阅读筛选、选中行采用一致蓝紫语义；分类蓝/绿/琥珀底色可辨；重要星标仍为警示黄。没有新增状态字段。PASS |
| 字阶 | 阅读筛选按钮实际受全局 font 重置覆盖，显得过大；已读列表标题偏弱 | 修正层叠后控件恢复紧凑12px；列表15px Medium，Reader标题最高层，元信息及正文保持不同色阶。不是只修改配置值。PASS |
| Deadline | 色底和描边过弱，与普通灰标签区别不足 | Today红、Soon琥珀，Future/Expired中性；深浅色均清楚可辨。计算与文案来源不变。PASS |
| Toolbar | 普通与收藏选中态缺少清晰边界 | 紧凑文字与图标保持同轴；已收藏有蓝紫底色与内描边，原文入口继续在右侧。普通/pressed状态已目视核对；hover/active样式保留并增强，本轮不声称截取了鼠标按下瞬间。PASS |
| Attachment | 图标、边界与底色层次较弱 | 蓝色DOCX、绿色表格、红色PDF能快速区分；真实长DOCX名称保留末尾与扩展名；附件与正文同左边界，下载图标独立。PASS |
| 1440整体 | 灰黑区域和过大的筛选字影响阅读层次 | 分栏、蓝紫选中、紧凑列表与正文区的关系稳定，标题与元信息层级明确。PASS |
| 宽屏整体 | Stage3.1布局已收敛，本轮仍缺少区域颜色层次 | 色彩变化覆盖整个区域而非透明度补丁；Toolbar、标题、正文、附件与来源沿同一阅读框架，未重新扩大无效空白。Dark/Light均PASS |
| 768 | 需要验证紧凑侧栏与详情颜色能否保持一致 | #90截图中单一Reader纵向滚动，元信息清晰、附件可达、无横向滚动。PASS（不据此关闭#36历史问题） |
| 390 | 长正文和附件挤压时容易失去层级 | 标题自然换行，来源/日期可读，附件保留类型与尾名；滚动后工具栏/返回可见，底部来源可达，无横向滚动。PASS |

## 语义状态补充验收

[深浅色真实组件对照](after-semantic-states.png) 使用现有 `NoticeCard`、`DetailToolbar`、`AttachmentRow`，不是重新画的组件。状态来自原有字段：

- Selected + Important + Today：蓝紫行、黄色星标、红色截止徽章互不混淆。
- Unread + Soon：未读圆点与文字可辨，科研分类为绿色，临近截止为琥珀色。
- Read + Future：标题次级色但保持Medium，实习标签与中性截止徽章分离。
- Favorited + Expired：收藏实心蓝紫图标，过期中性徽章；不会把过期变成新的紧急状态。
- Toolbar Saved：`aria-pressed=true` 显示蓝紫底色与描边；正常阅读操作保持次级文字。
- DOCX / XLSX / PDF：蓝/绿/红文件标识与统一附件底色，Light没有被Dark色值污染。

组件实测见 [after-semantic-states.json](after-semantic-states.json)：通知标题15px/500，工具栏12px；Dark已收藏底色`rgb(27,39,69)`、Light为`rgb(238,242,255)`。此处数据用于证明截图中的状态已真实生效，视觉判断以图片为主。

## 视口测量

| Chrome场景 | 实际 viewport | document clientWidth / scrollWidth | document clientHeight / scrollHeight | 结果 |
|---|---|---|---|---|
| Dark / Light基准 | 1440×900 | 1440 / 1440 | 900 / 900 | 无横向溢出 |
| Dark / Light默认宽屏 | 1707×923，DPR1.5 | 1707 / 1707 | 923 / 923 | 无横向溢出 |
| 768详情 | 768×900 | 768 / 768 | 900 / 900 | 无横向溢出，Reader滚动 |
| 390详情 | 390×844 | 375 / 375 | 844 / 1100 | 原生纵向滚动条占宽15px；无横向溢出 |

每张After整页截图有同名JSON记录。Stage3.1既有阅读宽度策略继续保留：1440正文约520px，宽屏正文最多704px；本轮没有修改三栏尺寸或正文布局规则。

## 本轮修改文件

| 文件 | 改动 |
|---|---|
| `frontend/src/index.css` | Dark语义色层次、4px compact圆角；font重置移入base layer，使Tailwind控件字阶生效 |
| `frontend/src/components/notice/NoticeCategoryTag.tsx` | 复用Badge的共享分类展示映射，供列表和详情使用 |
| `frontend/src/components/notice/NoticeCard.tsx` | compact模式分类标签、标题字重、来源/未读色、更新标签及active底色 |
| `frontend/src/components/notice/DeadlineBadge.tsx` | 紧凑圆角与可辨描边，不改deadline判断 |
| `frontend/src/components/notice/AttachmentRow.tsx` | 文件图标底色描边与下载hover强调 |
| `frontend/src/components/notice/DetailToolbar.tsx` | hover内描边、pressed底色/描边；原回调保留 |
| `frontend/src/pages/NoticeDetailPage.tsx` | 复用分类标签，来源图标使用来源蓝色 |
| `frontend/src/pages/NoticesPage.tsx` | 现有阅读筛选的选中色，交互不变 |
| `frontend/src/components/layout/AppShell.tsx` | 两处边界改用完整semantic border色；无结构改动 |
| `docs/design/design.md` | 先记录本轮有意的设计适配，再落地实现 |
| `docs/design/ui-v2-stage3.2/` | 截图、实测、并排比较页和本报告 |

仓库中其他未提交的Stage1/2/3/3.1变更保留，不能把整份git diff都归属于本轮。隔离组件验收入口放在已忽略的 `frontend/.visual-qa/`，没有加入产品路由。

## 工程回归

生产代码最后一轮修改后执行；后续仅补充验收截图和文档，没有继续修改生产代码。

| 检查 | 结果 |
|---|---|
| `npm test -- --run` | 28个测试文件，162 passed |
| `npm run lint` | PASS |
| `npm run build` | PASS；主包519.92kB，保留已有>500kB提示 |
| 后端 `.venv/Scripts/python.exe -m pytest` | 126 passed |
| `git diff --check` | PASS |

API、Notice模型、请求取消、URL参数、auto-read、收藏mutation、正文解析、外链安全和下载契约没有改动。隔离状态页未用模拟点击来冒充业务回归。

## Remaining Visual Differences

1. **有意的同色系适配：** Dark列表、Reader、选中和警示色比原始preview更明确；列表分类使用带底色的共享Tag，而preview的部分列表分类为普通文字。按本轮“增强层次和语义色”的要求实施，不声称逐像素或逐色值复制。
2. **真实数据轮廓：** #90有一个长正文段及三个DOCX附件，reference有分段、截止说明和PDF/XLSX。原始数据没有的标签、Deadline与段落没有补造；样例内容轮廓不能用于证明真实页面已渲染这些不存在的数据。
3. **证据边界：** 本轮保留了Dark同数据before/after；未保存浅色before。Light结论来自reference与真实after对照，不能包装成完整的浅色三时点证据。补充组件状态为内置浏览器，整页为Chrome。
4. **仍未闭环的Stage3.1问题：** #36在尺寸切换后的双纵向滚动条，详见 [Stage3.1报告](../ui-v2-stage3.1/REPORT.md)。#90本轮768截图没有双滚动条，不足以证明#36场景已修复。该项继续阻止宣布“整个Reader所有视觉问题都已关闭”。

**最终：Stage3.2所列颜色、字阶、组件及视口场景 Visual PASS；既有Stage3.1滚动问题仍未闭环。完成本轮验收后暂停，不进入Stage4。**
