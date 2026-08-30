# Gate 2A 报告

## Gate 2A Result

PASS。已完成最小前端测试基座、统一请求生命周期、附件 DTO 对齐，以及通知详情的 404 专用界面。未实施 Gate 2B 及后续范围。

## Changed

- 新增 Vitest、React Testing Library、jest-dom 与 jsdom，并配置 `npm test`。
- 在 `api/client.ts` 集中实现 15 秒默认超时、外部 `AbortSignal` 转发和结构化 `ApiError`。
- 所有当前 React Query 读取型查询均从 `queryFn` 接收并下传 `signal`；mutation 保持原有行为。
- `Attachment` 对齐后端 `{ filename, url, type }`，详情页显示 `filename ?? '附件'`。
- `ErrorState` 按错误类型展示统一文案；详情页的 `NOT_FOUND` 显示返回通知列表入口且不提供重试。
- 新增 API 生命周期测试与详情页附件/404 测试。

本次仅在已存在用户修改的 `package.json`、`package-lock.json`、`vite.config.ts`、`DashboardPage.tsx`、`NoticeDetailPage.tsx`、`SourcesPage.tsx` 中追加必要改动；其余既有脏文件未重置、覆盖或整理。

## Error Contract

`ApiError` 提供以下字段：

| 字段 | 含义 |
| --- | --- |
| `kind` | `NETWORK_ERROR`、`TIMEOUT`、`ABORTED`、`HTTP_ERROR` 或 `NOT_FOUND` |
| `status` | HTTP 响应状态码；网络、超时和取消时为空 |
| `endpoint` | 相对 API 路径 |
| `message` | 面向 UI 的默认错误说明 |

HTTP 404 单独归类为 `NOT_FOUND`；其他非 2xx 响应归类为 `HTTP_ERROR`。超时优先于取消分类，调用方传入的 signal 触发取消时归类为 `ABORTED`。

## Request Lifecycle

`apiRequest` 为每次请求创建内部 `AbortController`，默认 15 秒后取消请求；若 React Query 提供 `signal`，它会单向转发到该控制器。无论成功、失败、超时或取消，计时器和事件监听器都会在 `finally` 清理。

读取型 API 已支持可选 `ApiRequestOptions`，并在 Dashboard、通知列表/分类/收藏/今日/截止、详情、数据源、爬虫状态和搜索查询中传递 React Query 的 `signal`。启动爬虫、收藏与已读等 mutation 未改变。

## Attachment Fix

前端附件类型从旧的 `name/title/file_type` 猜测字段改为后端真实返回的 `filename/type`。通知详情以 `filename ?? '附件'` 显示名称，链接继续使用必填 `url`。

## 404 Fix

通知详情请求返回 404 时，`ErrorState` 显示“通知不存在”和说明“该通知可能已被删除或链接无效。”，并显示“返回通知列表”链接；不显示“重新连接”或重试按钮。

## Tests

已执行并通过：

| 命令 | 结果 |
| --- | --- |
| `frontend: npm test -- --run` | 2 个测试文件，7 项通过 |
| `frontend: npm run lint` | 通过 |
| `frontend: npm run build` | 通过 |
| `backend: .\.venv\Scripts\python.exe -m pytest` | 43 项通过 |

前端测试覆盖 API 成功、404、网络错误、超时、外部取消，以及详情页附件文件名与 404 返回入口。

## Signal Propagation

信号传递路径为：`useQuery({ queryFn: ({ signal }) => api(..., { signal }) })` → API adapter → `apiRequest` → `fetch(..., { signal })`。

已检查 Dashboard、通知列表、竞赛、分类 Feed、收藏、今日、截止、详情、数据源、应用壳层爬虫状态、爬虫按钮状态和搜索。快速路由切换的真实浏览器验证未出现取消请求错误。

## Manual Verification

使用本机后端与 Vite 前端完成验证，未新增基线截图：

- Dashboard 正常加载通知与统计。
- 通知详情 `/notices/36` 显示后端返回的三个真实附件 `filename`。
- `/notices/999999` 显示专用“通知不存在”状态和返回列表链接。
- 停止本次临时启动的后端后，数据源页显示“无法连接本地服务”、说明与“重新连接”按钮。
- 快速切换通知列表、数据源和首页后，未观察到取消请求错误。

验证完成后已关闭临时服务，并清理四个临时日志文件。

## Remaining Risks

- 浏览器控制台发现一条重复 React key 告警：`csw`。它来自已有数据源列表的重复 key，和本次请求生命周期、附件 DTO 或 404 改动无关，未在 Gate 2A 扩展修复。
- 未引入 MSW、Playwright、CI 或视觉回归，符合本 Gate 的最小测试基座范围。

## Out of Scope

以下内容保持未改：URL 状态同步、自动标记已读生命周期、收藏/已读 mutation 返回结构、Dashboard“优先关注”错误 UI、设置、SearchDialog 的独立错误体验、Playwright/MSW/CI、视觉重设计和后端接口。

## Next Gate

建议进入 Gate 2B：修正收藏与已读 mutation 响应契约、自动标记已读的详情切换生命周期，以及 Dashboard 的局部错误状态。开始前应先确认上述既有 `csw` 重复 key 是否并入下一 Gate。
