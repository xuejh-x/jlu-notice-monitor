# Stage 3.3 — Reading Continuity and Scroll Boundary

日期：2026-09-11。Stage 4 与 OA Live Validation 继续暂停。

**Functional PASS / Visual PASS。** 自动已读不再令当前未读行瞬间消失；长详情在连续切换1440、1707、768、390后只有目标pane滚动，没有可操作的document滚动或双纵向滚动条。

## 修复结果

### 未读阅读连续性

此前自动已读成功后立即invalidate并refetch当前`['notices']`查询。未读API随即返回不含该通知的新列表，导致用户刚点击的行从当前列表消失。

现在保留原来的每notice id去重与`POST /read`流程。成功后：

1. 详情缓存立刻改为`is_read: true`。
2. 所有已缓存通知行原地改为已读，当前页的行、位置、总数保持稳定。
3. 通知查询标记为stale，但自动已读这一步不触发active list refetch。
4. dashboard和search仍按原逻辑刷新；收藏逻辑不变。
5. 用户关闭详情重新进入未读列表时显式refetch；切换筛选/query key、浏览器刷新或现有显式刷新也会重新读取后端真实状态，已读项届时移除。

回归测试从`/notices?read=0`打开未读通知，确认POST仅一次、当前行保留且显示“已读”、列表没有发生第二次GET；点击“返回通知列表”后确认第二次GET发生且该行移除。

### 滚动模型

- `html / body / #root / AppShell`固定为viewport高度并`overflow: hidden`。
- Header占56px固定行，workspace占剩余`minmax(0,1fr)`。
- Sidebar内部导航容器为`overflow-y-auto`；Sidebar自身不推动document。
- Notice List只有行列表容器滚动；Header、筛选、状态栏和分页固定在列表pane内。
- Detail Reader的workspace aside是唯一详情滚动容器；Detail内部不再创建第二个纵向滚动层。
- 390列表/详情pane预留68px底部导航高度；删除旧body padding补偿。移动详情滚到底时来源footer bottom为756px，Bottom Nav top为776px，二者不遮挡。

## Before / After

[打开截图对比页](comparison.html)

| 场景 | Before | After | 肉眼判断 |
|---|---|---|---|
| 768×900长详情 | [Stage3.1双滚动](../ui-v2-stage3.1/after-768.png) | [单Reader滚动](after-768x900.png) | Before右侧同时出现document与Reader滚动条；After只剩Reader一条。PASS |
| 390×844长详情 | [Stage3.1边界](../ui-v2-stage3.1/after-390.png) | [顶部](after-390x844-top.png)、[附件/来源到底](after-390x844-bottom.png) | AppShell固定，内容在Reader中滚动，底部导航不遮住来源。PASS |
| 1440×900长详情 | [Stage3.1](../ui-v2-stage3.1/after-1440-dark.png) | [Stage3.3](after-1440x900.png) | Sidebar、List、Reader均在固定Shell内；列表和Reader各一条滚动边界。PASS |
| 1707×923长详情 | [Stage3.1](../ui-v2-stage3.1/after-wide-deadline.png) | [Stage3.3](after-1707x923.png) | document严格等高，宽屏Reader独立滚动。PASS |
| 390×844列表 | — | [列表独立滚动](after-390x844-list.png) | Header/筛选/分页/Bottom Nav固定，只有通知行区域滚动。PASS |

截图使用真实通知#36：一个长正文段、已截止状态、六个DOC/DOCX附件、两个来源。没有改正文、附件或颜色/组件视觉。

## 实测边界

| 视口 | document | body / root / shell | 实际可滚动区域 | 结论 |
|---|---|---|---|---|
| 1707×923详情 | 923 / 923 | 均923 / 923 | List 711→1720；Reader 867→919 | document严格等高；两个并列pane独立滚动 |
| 1440×900详情 | 900 / 1011* | 均900 / 900 | List 688→1720；Reader 844→1043 | 只有List与Reader可滚动 |
| 768×900详情 | 900 / 961* | 均900 / 900 | Reader 844→993 | 只有Reader可滚动，双滚动已消失 |
| 390×844详情 | 844 / 1209* | 均844 / 844 | Reader 788→1309 | 只有Reader可滚动；到底后document scrollTop仍为0 |
| 390×844列表 | 844 / 844 | 均844 / 844 | List 516→1720 | document严格等高；只有List可滚动 |

表中格式为`clientHeight / scrollHeight`。带`*`的IAB详情页由Codex浏览器在`<html>`下额外插入固定定位的`codex-browser-sidebar-comments-root`审阅层，它会放大`documentElement.scrollHeight`。应用自己的body、root和shell仍严格等高，html/body/root都为`overflow:hidden`；扫描全部DOM只发现表中目标pane可滚动。滚动390 Reader到底后实测`documentScrollTop=0`、`bodyScrollTop=0`，因此这不是第二条可用滚动边界。

本轮最初尝试连接用户Chrome时返回不可用；After截图由同Chromium布局引擎的Codex In-app Browser按指定精确viewport采集。Before采用Stage3.1真实Chrome证据。未把IAB截图标成Chrome，也未用截图裁切掩盖滚动条。

## 修改文件

- `frontend/src/components/layout/AppShell.tsx`：固定Shell、统一两行布局、List/Reader独立overflow和移动底栏预留。
- `frontend/src/index.css`：锁定html/body/root高度与overflow；删除移动body padding。
- `frontend/src/pages/NoticesPage.tsx`：列表容器使用父pane高度；返回未读列表时refetch真实状态。
- `frontend/src/pages/NoticeDetailPage.tsx`：自动已读成功使用稳定列表缓存更新。
- `frontend/src/utils/noticeCache.ts`：新增自动已读缓存保留函数。
- `frontend/src/utils/noticeCache.test.ts`、`frontend/src/components/layout/AppShell.test.tsx`：缓存策略与完整阅读流程回归。
- `docs/design/design.md`：记录Stage3.3滚动与阅读连续性契约。
- `docs/design/ui-v2-stage3.3/`：截图、实测JSON、对比页和本报告。

## 工程回归

| 检查 | 结果 |
|---|---|
| `npm test -- --run` | 28个测试文件，164 passed |
| `npm run lint` | PASS，无warning |
| `npm run build` | PASS；主包520.29kB，保留既有>500kB提示 |
| `git diff --check` | PASS |

未修改API、数据模型、AbortController、URL schema、自动已读去重、收藏mutation、正文/附件、颜色token或Stage3.2组件视觉。

## Remaining Differences

1. After的当前用户Chrome实例无法通过浏览器连接访问，宽屏After在IAB Chromium 1707×923采集；布局数据与指定视口已完整记录，但不声称它是Chrome实例截图。
2. 1440/768/390详情的`documentElement.scrollHeight`受IAB固定审阅层影响不等于clientHeight；应用节点严格等高，document被锁定且scrollTop保持0，只有正确pane可操作滚动，符合“或明确证明只有正确区域滚动”的验收条件。

**最终：Stage3.3 Visual PASS / Functional PASS。停止于Stage3.3，不进入Stage4。**
