# UI v2 · Stage 2 — Notice List 验收报告

日期：2026-09-11。状态：完成并暂停；未实施 Stage 3 / Stage 4。

## 修改文件

| 文件 | 变更 |
|---|---|
| `frontend/src/components/notice/NoticeCard.tsx` | 重构主列表使用的 compact 模式；86px 行、来源/时间、截断标题、分类/阅读/重要/更新状态、收藏按钮 |
| `frontend/src/components/notice/NoticeList.tsx` | 取消列表行外边距，保持整栏连续排列；骨架复用86px行高 |
| `frontend/src/components/notice/DeadlineBadge.tsx` | 新增仅列表启用的20px展示变体、时钟图标、Today/Soon/Future/Expired视觉 |
| `frontend/src/components/notice/SourceIcon.tsx` | 新增仅列表启用的14px无背景图标变体；沿用现有来源标识逻辑 |
| `frontend/src/components/ui/Pagination.tsx` | 新增 compact 展示选项；保留上一页/下一页、禁用条件与回调 |
| `frontend/src/pages/NoticesPage.tsx` | 52px标题栏、36px阅读筛选栏、28px结果状态栏、40px分页区；移动列表全宽展示 |
| `frontend/src/index.css` | 更新列表标题/行高 tokens，增加筛选/状态/分页高度 tokens |
| `frontend/src/components/notice/NoticeCard.test.tsx` | 增加7项回归：组合状态、收藏与选择解耦、4种deadline展示、无截止与完整长标题 |
| `docs/design/design.md` | 编码前记录 Stage 2 设计与适配边界 |

验收截图和尺寸结果位于本目录。Stage 1 已有改动和原始交付包保持原状。

## 与交付设计的对应关系

以 `../figma-delivery/HANDOFF.md`、`design-data.json`、`build.mjs` 和参考图为依据。交付包明确说明在线 Figma 文件尚无已验收设计节点，本阶段对应其本地组件规范与预览。

| 设计组件/区域 | 实现映射 |
|---|---|
| Notification Row | 主列表现有 `NoticeCard compact`；不是其他页面使用的简版 `NoticeRow`。86px高，左右18px、上下10px；来源18px、标题24px、状态20px，间距2px |
| Default / Read | 无边框卡片或阴影，来源和状态文字使用低对比语义色 |
| Selected / Hover / Focus | `selected-surface` / `surface-hover` / 2px内侧focus ring；选中独立于已读 |
| Unread | 既有 `is_read` 控制6px未读点、标题字重及可见阅读文字 |
| Important | 既有 `importanceLevel(importance_score)` 控制星形标识与“重要/高相关”标签 |
| Favorited | 既有 `is_favorite` 控制实心书签及 `aria-pressed`；收藏按钮独立于行链接 |
| Deadline Badge | `list`选项：20px高、6px水平padding、12px时钟；Today红色、Soon暖色、Future/Expired中性色 |
| Tags / Status | 复用 Badge，依照行组件使用紧凑文字样式；分类来自 `categoryLabels`，更新状态来自 `status === 'updated'` |
| List Header / Filter / Status / Footer | 52 / 36 / 28 / 40px；现有tabs与筛选弹窗保留，排序继续显示真实的“按截止时间” |

适配说明：不把示例“最新发布”实现为新排序，不把示例“最近更新”变成数据重排或日期分组。结果区显示当前真实查询总数；不虚构来源分组、标签或统计值。发布时间保留现有相对时间格式，deadline保留现有计算与文案。详情的 DeadlineBadge 默认样式保持原样。

## 验证结果

| 检查 | 结果 |
|---|---|
| `npm test -- --run` | 28 个测试文件 / 159 项通过 |
| `npm run lint` | PASS |
| `npm run build` | PASS；主包516.82kB，仍有既有500kB阈值提示 |
| Backend `.venv/Scripts/python.exe -m pytest` | 126 passed |
| `git diff --check` | PASS |

初次回归发现旧“当前为列表视图”静态提示丢失；已接入新的状态栏，并在不删除或跳过原测试的情况下全量通过。

浏览器使用真实本地前后端、隔离数据库和明确的测试通知，不读取或修改用户数据库；启动同步和定时抓取关闭。逐张检查桌面深浅色、平板、手机和手机滚动底部截图。

- 1440×900：三栏仍为282 / 574 / 584px；列表内部52 / 36 / 28 / 40px实测匹配；所有行86px。
- 768×900：72px侧栏 + 696px列表；所有行86px；可点击进入详情并返回。
- 390×844：390px单栏；所有行86px；可点击进入详情并返回；滚动到底部后分页位于固定底部导航上方。
- 长标题使用真实超长测试标题，三个尺寸均为单行省略；完整标题留在链接的可访问名称和title中；文档及每行无横向溢出。
- 收藏、取消收藏不会导航；点击行选择通知；详情成功后显示已读；测试覆盖选中且未读、重要且收藏、已更新、今天/即将/未来/过期以及无截止时间的组合。
- 浏览器页面脚本错误：0。未执行真实OA远端抓取或登录。

尺寸与交互记录：[geometry.json](geometry.json)。截图：[Desktop Dark](desktop-dark.png)、[Desktop Light](desktop-light.png)、[Tablet](tablet-list.png)、[Mobile](mobile-list.png)、[Mobile底部](mobile-bottom.png)。

## 保持不变

API请求代码、Notice类型、数据模型、URL参数解析与序列化、搜索/收藏/已读事件处理、自动刷新、AbortController、错误处理分支、OA代码未修改。NoticeCard普通模式、NoticeDetailPage、DetailToolbar、附件组件、Sources和Settings页面未修改。共享组件的新展示选项仅在列表显式启用。

本阶段停止于 Notice List；等待下一阶段指示。
