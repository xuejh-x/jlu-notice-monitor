# Gate 2C — P1 Regression Closure Report

**项目：** JLU Notice Monitor  
**范围：** Gate 2C — P1 Regression Closure  
**日期：** 2026-08-30  
**结论：** PASS

## 1. Executive Summary

Gate 2C 对 Gate 2A/2B 已交付的六项 P1 修复进行了代码、自动化测试和真实浏览器三层复核。生产逻辑无需再改动；本轮只补齐了三个最小化回归断言：非 404 HTTP 错误分类、请求完成后的资源清理，以及完整 Notices URL schema 往返；另补充了 404 页面不显示离线文案的断言。

## 2. Repository State

仓库在 Gate 2C 开始时已有用户工作区改动。审计和验证均在保留这些改动的前提下进行。本轮新增/修改的范围仅为：

- `frontend/src/api/client.test.ts`
- `frontend/src/pages/NoticesPage.test.tsx`
- `frontend/src/pages/NoticeDetailPage.test.tsx`
- 本报告

未修改 production behavior，未启动 P2/P3 工作。

## 3. P1 Closure Matrix

| P1 项 | 验收结论 | 证据 |
| --- | --- | --- |
| P1-1 Attachment | PASS | DTO 已包含 `filename`、`url`、`type`；详情页真实显示附件文件链接。 |
| P1-2 Error / 404 | PASS | `NOT_FOUND` 与网络/超时/HTTP 错误分类独立；真实 404 显示专用页面且不显示离线文案；后端停止后显示离线状态。 |
| P1-3 URL State | PASS | Notices 从 URL 初始化并写回；全部 schema 字段 round-trip 自动化通过；刷新、分享、分页、前进/后退真实通过。 |
| P1-4 Request Lifecycle | PASS | query signal 向 API 透传；15 秒超时与外部 abort 均覆盖；完成后 timer 与 abort listener 清理有显式断言。 |
| P1-5 Auto-read | PASS | `Set<number>` 按通知 ID 去重；两个真实未读通知各产生一次 `/read` 请求，最终状态恢复。 |
| P1-6 Regression Harness | PASS | Vitest + RTL + jsdom 已可运行；本轮前端 18 项测试、后端 43 项测试全通过。 |

## 4. P1-1 Attachment Closure

前后端附件契约采用 `filename`、`url`、`type`。浏览器打开通知 36 后，附件区域可见实际文件链接；链接使用真实附件 URL，而不是仅把远端 URL 当作显示名称。

## 5. P1-2 Error / 404 Closure

`apiRequest` 可区分 `NETWORK_ERROR`、`TIMEOUT`、`ABORTED`、`HTTP_ERROR` 和 `NOT_FOUND`。本轮补充了 HTTP 500 必须归类为 `HTTP_ERROR` 的测试。

真实浏览器中，`/notices/999999` 显示“通知不存在”和返回通知列表链接（`/notices`），不显示“无法连接本地服务”。停止本轮启动的后端后访问数据源页，显示“无法连接本地服务”和“重新连接”。

## 6. P1-3 URL State Closure

`NoticesPage` 使用 URL 作为查询、筛选与分页状态来源。`noticeSearchParams` 的回归测试覆盖了 `q`、`category`、`source`、`min_score`、`date_from`、`deadline_status`、`read`、`favorite`、`page`、`page_size` 的完整往返。

真实浏览器验证了带 `q=软件&source=csw&page=2&page_size=10` 的链接：初次打开、刷新和新标签分享均保留关键词、来源和页码；分页生成 `page=2&page_size=10`，切换科研分类重置为 `category=research&page_size=10`，浏览器后退/前进均恢复对应 URL。

## 7. P1-4 Request Lifecycle Closure

请求层统一创建内部 `AbortController`，转发外部 signal，15 秒超时后 abort，并在 `finally` 中清理 timeout 与外部 abort listener。`apiRequest` 测试已覆盖：成功、404、其他 HTTP 错误、网络错误、超时、外部 abort 和清理行为。

## 8. P1-5 Auto-read Closure

详情页用 `Set<number>` 保存已自动标记的通知 ID，避免组件重渲染或 Strict Mode 造成重复读请求。

真实验证中，通知 34、35 初始均为已读；为执行测试临时设为未读。浏览器依次打开两条通知后，服务访问日志中 `POST /api/notices/34/read` 与 `POST /api/notices/35/read` 的计数均为 1，两个通知最终均恢复为已读，未留下数据状态变化。

## 9. P1-6 Regression Harness Closure

前端使用 Vitest、React Testing Library、jsdom 和 `jest-dom`；后端使用 pytest。现有测试覆盖关键 API 分类、附件、详情 404、URL 状态和自动标记已读。该基础设施足以为 P1 行为提供可重复回归保护。

## 10. Tests Added

- `client.test.ts`：HTTP 500 → `HTTP_ERROR`；完成后清理 timeout 和外部 abort listener。
- `NoticesPage.test.tsx`：完整 Notices URL schema parse/serialize round-trip。
- `NoticeDetailPage.test.tsx`：404 专用页面不显示离线错误态。

## 11. Automated Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 3 个测试文件、18 项测试通过。 |
| `npm run lint` | PASS。 |
| `npm run build` | PASS。 |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 项测试通过。 |

## 12. Browser Closure Smoke

使用本机临时启动的后端（8000）和 Vite 前端（5173）完成以下验证：

- Dashboard 成功加载，显示“上午好”和通知列表。
- Notices 带真实 URL 参数加载、刷新和新标签分享均保留状态。
- 分页、筛选后 URL 写回，浏览器后退/前进状态一致。
- 通知 36 显示附件文件链接。
- 不存在通知显示专用 404 页面，并带返回列表链接。
- 停止本轮后端后，数据源页显示离线错误态和“重新连接”。
- 通知 34、35 作为真实未读样本均仅发起一次自动 `/read` 请求；最终状态已恢复。

## 13. Known Out-of-scope Issues

以下项目不属于 Gate 2C，不在本轮修复范围内：

- 收藏/已读 mutation 的响应契约不一致。
- Dashboard 重要通知查询的错误态 UI。
- 持久化设置响应式问题。
- SearchDialog 的错误体验。
- `csw` 可能产生重复 React key 警告。
- strict/style、MSW、Playwright、CI 和视觉重构。

## 14. Remaining Risks

P1 已闭环，但尚未覆盖网络抖动下的端到端重试/取消组合，以及跨浏览器的持久化设置行为。当前回归集以单元/组件测试和人工浏览器 smoke 为主，尚未引入 MSW 或 Playwright CI。

## 15. Gate Result

**PASS**。六个 P1 项均有生产实现、自动化回归保护和相应的 closure 验证证据。

## 16. Recommendation for Next Phase

**P2 Remediation Planning**
