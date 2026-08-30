# Gate 2B 报告

## Scope

本 Gate 只关闭两个剩余 P1：NoticesPage 的可分享 URL 状态，以及 NoticeDetailPage 的 per-notice auto-read 生命周期。未处理任何 P2/P3。

## Files Changed

- `frontend/src/pages/NoticesPage.tsx`
- `frontend/src/utils/noticeSearchParams.ts`
- `frontend/src/pages/NoticesPage.test.tsx`
- `frontend/src/pages/NoticeDetailPage.tsx`
- `frontend/src/pages/NoticeDetailPage.test.tsx`
- `docs/GATE_2B_REPORT.md`

对 Gate 2A 时已存在修改的两个页面只追加本 Gate 必要差异；未 reset、checkout、clean、stash 或覆盖其他 dirty 文件。

## URL Schema

| 参数 | UI 状态 | 合法值 / 规则 | 缺省值 |
| --- | --- | --- | --- |
| `q` | 搜索词 | 任意非空文本 | 无搜索词 |
| `category` | 分类 | 当前分类下拉框的八个非默认值 | 全部分类 |
| `source` | 来源 | `cse/ccst/csw/jwc/innovation/oa` | 全部来源 |
| `min_score` | 最低优先级 | `70/80/90` | 不限 |
| `date_from` | 起始日期 | 有效 `YYYY-MM-DD` | 不限 |
| `deadline_status` | 截止状态 | `today/urgent/normal/expired/unknown` | 全部 |
| `read` | 阅读状态 | `1` 已读、`0` 未读 | 全部 |
| `favorite` | 收藏状态 | `1` 已收藏、`0` 未收藏 | 全部 |
| `page` | 页码 | 正安全整数 | `1` |
| `page_size` | 每页数量 | `10/20/50` | 当前保存设置，设置非法时为 `20` |

NoticesPage 当前没有 sort 控件，因此没有新增 `sort` 参数。默认筛选与 `page=1` 不写入 URL；`page_size` 等于当前保存默认值时省略。

## URL State Ownership

URL search params 是搜索、筛选、页码和每页数量的唯一持久状态源。页面每次 render 都通过纯函数解析标准化状态；除 debounce 内部值外，不再为这些字段维护并行 React state。Back、Forward、刷新和新标签页都会从 URL 重新生成控件值与请求参数。

## Search / Debounce Strategy

搜索输入直接更新 URL 并使用 `replace`，因此输入多个字符不会制造逐字符 history entry。API 查询使用现有 `useDebouncedValue` 延迟 300ms，并对请求词执行 trim。输入变化同时将 page 重置为 1。

## History Strategy

- 搜索输入：`replace`。
- 显式筛选变化：普通导航 `push`。
- 分页：普通导航 `push`。
- Back / Forward：由 React Router 恢复 URL，受控表单和 Query 随标准化 URL 状态同步。

## Page Reset Rules

`q/category/source/min_score/date_from/deadline_status/read/favorite` 变化都将 page 重置为 1，并从 URL 移除默认第一页。只改变分页时保留所有有效筛选。`page_size` 当前没有 NoticesPage 内控件，不新增交互。

## TanStack Query Alignment

数据链路为：

`URLSearchParams` → `parseNoticesSearchParams` → 标准化 `requestFilters` → 同一个对象进入 `queryKey` 和 `getNotices`。

因此影响后端结果的每个 URL 字段均参与缓存身份；非法枚举、日期、页码和 page size 在进入 API 前已回退，不会发送 NaN 或非法筛选。

## Auto-read Lifecycle Fix

原实现使用单个 boolean ref，作用域是组件生命周期；同一路由实例从 A 切到 B 时，A 会阻止 B 自动标记。

现在使用组件内 `Set<number>` 记录已处理 notice ID，并要求：详情成功加载、响应 ID 与 route ID 一致、当前未读、该 ID 尚未处理。ID 在发起 mutation 前加入 Set，可抵御 React 19 StrictMode effect 重放和普通 rerender；切换到新 ID 时仍会执行一次。自动标记失败继续静默，保持原产品语义。mutation response 类型未改。

## Tests Added

新增 8 项 Gate 2B 回归，共 15 项前端测试：

- 初始 URL 恢复搜索、来源、阅读状态、page 和 page size，并核对 API 参数。
- 显式筛选写入 URL 且重置 page。
- 搜索写入 URL、请求保持 300ms debounce。
- 分页写入 URL并保留筛选。
- 非法 page、page size、category、read 安全回退。
- 同一组件实例 A→B 各 auto-read 一次。
- 同一 notice 普通 rerender 不重复 auto-read。
- 已读 notice 不发送 auto-read。

Gate 2A 的 7 项测试全部保留且继续通过。

## Automated Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | 3 个文件，15 项通过 |
| `npm run lint` | 通过 |
| `npm run build` | 通过，2,784 modules transformed |
| `.\.venv\Scripts\python.exe -m pytest` | 43 项通过 |

## Browser Verification

- 搜索“软件”后 URL 更新，300ms 后结果同步；选择来源“软件学院”后 URL 增加 `source=csw`，结果为 28 条。
- 刷新后搜索框恢复“软件”、来源恢复“软件学院”，结果保持 28 条。
- 使用 `page_size=10` 进入 page 2 后 URL 为 `page=2&page_size=10`；从 page 2 改为科研分类时 page 被移除并回到第一页。
- 浏览器 Back 恢复 page 2，Forward 恢复科研分类。
- 新标签页打开 `q=软件&source=csw&page=2&page_size=10`，恢复对应控件、第 2 页和相同 28 条结果集。
- 将本地通知 34、35 临时设为未读后依次打开详情，两者最终均为已读；后端访问日志确认每个 ID 恰好一次 `POST /read`。测试前后的最终阅读状态一致。

本次未新增截图。验证结束后已关闭标签页和临时服务，并删除四个临时日志。

## Remaining Risks

- URL 未显式提供 `page_size` 时会按既有产品语义继承当前浏览器保存的设置；跨不同本地设置环境分享时，每页数量可能不同。需要完全固定时可在共享 URL 中显式携带 `page_size`。
- Gate 2A 记录的 `csw` duplicate React key 告警仍存在；按本 Gate 范围明确未修复，且不阻塞 URL state 或 auto-read。

## Out of Scope

确认未处理：favorite/read mutation response P2、Dashboard important-query error P2、`csw` duplicate key、settings reactivity、SearchDialog 独立错误 UX、其他页面 URL state、视觉重设计、MSW、Playwright、CI、后端 API/schema/crawler。

## Gate Result

PASS。Gate 2B 的 URL state、auto-read、回归、质量关卡与真实浏览器验收条件全部满足。下一阶段应为 **Gate 2C — P1 Regression Closure**；本轮未提前执行 Gate 2C。
