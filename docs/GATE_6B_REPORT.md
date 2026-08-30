# Gate 6B Result

**PASS**

Gate 6B — SearchDialog Request Race / Concurrency 完成。审计从代码路径严格推导 + 6 个可控 Promise 的 deterministic 测试证明：**当前实现不存在响应乱序 race**。根因是 TanStack Query 以 `['search', keyword]` 为 queryKey 的结构性隔离（每个逻辑 query 独占 cache entry 与 observer），加上 `waitingForDebounce` 在 debounce 窗口遮蔽旧数据/旧错误——stale 请求完成时只能写入无人观察的旧 cache entry，永远无法控制当前 UI。因此本轮**零生产代码修改**，交付物为完整 concurrency regression proof。

# Existing Request Flow

```
用户输入 (keyword state)
  → normalizedKeyword = keyword.trim()
  → debouncedKeyword = useDebouncedValue(normalizedKeyword, 300ms)
      (trailing debounce: useEffect + setTimeout + cleanup)
  → useQuery({
      queryKey: ['search', debouncedKeyword],
      queryFn: ({ signal }) => searchNotices(debouncedKeyword, { signal }),
      enabled: debouncedKeyword.length > 0,
    })
  → searchNotices → apiRequest → fetch
      (内部 AbortController + 外部 signal 透传 + 15s timeout + cleanup，P1 契约)
  → query state: isPending / isError / data
  → UI 分支: idle → (waitingForDebounce || isPending) loading → isError → data.items 长度 ? results : empty
```

关键架构事实：

1. **queryKey 含 keyword**：`['search', debouncedKeyword]`。每个关键词是独立 cache entry。
2. **TanStack Query observer 语义**：key 变化时 observer 从旧 query 解绑、订阅新 query；旧 query 的 in-flight 完成只通知旧 query 的 observer（此时已无人订阅）→ 无法触发 hook re-render。
3. **同 key 去重**：同一关键词的并发 fetch 被 TanStack Query 去重（共享同一 promise），不存在同 key 双请求乱序。
4. **`waitingForDebounce` 门控**：UI 分支中 `waitingForDebounce || query.isPending` 先于 data/error 判定——debounce 窗口内旧缓存数据/旧错误被遮蔽。
5. **API client 已原生支持外部 AbortSignal**（P1 请求生命周期）；`ABORTED` 静默是既有 error taxonomy。

# Race Analysis

**race 是否真实存在：否。**

按场景逐一验证（全部由 `SearchDialog.race.test.tsx` 以可控 Promise 严格证明）：

| 场景 | 结论 | 机制 |
| --- | --- | --- |
| A. stale success（A 后 resolve） | 不存在 | A 写入 `['search','A']` cache，observer 已订阅 `['search','B']`，UI 不被触碰 |
| B. stale error（A 后 reject） | 不存在 | A 的 error 落在旧 key；当前 key 无 error，无 error UI |
| C. stale empty（A 后返回 []） | 不存在 | 同上，旧 key 的 empty 不驱动 UI |
| D. clear while pending | 不存在 | 清空后 `normalizedKeyword=''` 直接进入 idle 分支；A 完成只写旧 cache |
| E. rapid A→B→C | 不存在 | 只有 `['search','C']` 被观察；A/B 完成不改变 C 的 loading/results/error |
| F. close while pending | 不存在 | Dialog 关闭时组件仍挂载、请求后台完成；关闭期间无可见 error；reopen 显示当前关键词的真实状态（error+retry），非 stale 污染 |
| G. abort/cancellation | 不适用 | 本轮未引入主动取消；`ABORTED` 静默由既有 `client.test.ts` 覆盖 |

**为什么 debounce 不是 race 证明**：debounce（300ms trailing）只减少请求数量，不约束已发出请求的完成顺序。真正保证顺序安全的机制是 queryKey 隔离（第 2 点）——这是架构级的 ownership 边界，不依赖时序假设。

**root cause（若被问“为什么没有 race”）**：UI 状态由 `useQuery` 的 observer 结果驱动，observer 每帧只绑定一个 queryKey；stale 响应的写入目标（旧 cache entry）与 UI 的读取源（当前 key 的 query state）结构上不相交。

# Concurrency Contract

**Only the latest logical query owns SearchDialog UI state.**

- **request ownership**：一个逻辑 query = 一个 `['search', keyword]` cache entry；同 key 请求去重，跨 key 请求互不影响。
- **result / empty ownership**：只有当前 key 的 `data` 能渲染；旧 key 的 success/empty 写入无人观察的 entry。
- **error ownership**：只有当前 key 的 `isError` 能渲染 ErrorState；旧 key 的失败不产生可见 error。
- **loading ownership**：`waitingForDebounce || 当前 key 的 isPending`；旧请求的完成不触碰当前 key 的 isPending。
- **cancellation / cleanup**：不做主动 abort（无正确性必要，见 Problems Found）；若信号被外部 abort（GC/调用方），client 抛 `ABORTED`，TanStack Query 视为 cancel，不进入 error UI。

# Problems Found

无需要修改的真实问题。两个残余项经评估不属于问题：

1. **旧请求在 key 切换后继续在后台执行直到 GC**（~5min 后由 TanStack Query abort）。影响：每条 debounce 窗口最多一个多余 fetch，后端为本地廉价 SQL，资源开销可忽略；正确性零影响。结论：不为此引入 abort-on-key-change（会扩大修改半径且无实际收益）。
2. **无主动 cancellation**：仅当外部 signal 被 abort 时 `ABORTED` 静默生效（既有契约，`client.test.ts` 覆盖）。结论：sequence/queryKey isolation 已可靠，cancellation 无必要。

# Changes

生产代码：**零修改**。`SearchDialog.tsx`、`api/client.ts`、`api/notices.ts`、`useDebouncedValue` 均未改。

# Regression Tests

新增 `frontend/src/components/search/SearchDialog.race.test.tsx`（6 项，全部 deterministic：手动可控 deferred fetch + 固定 300ms debounce，无真实网络、无任意 sleep）：

- **stale success**：A、B 先后发出，B 先 resolve、A 后 resolve → UI 保持 B，A 不出现。
- **stale error**：B 成功、A 后 reject → B results 保留，无“无法连接本地服务”/“重新连接”。
- **stale empty**：B 成功、A 后 resolve [] → 不切换 empty。
- **clear while pending**：A pending 时清空 → idle 状态；A 后 resolve → 不重新填充。
- **rapid A→B→C**：C pending 期间 A success、B error 均不改变 loading、不产生 error UI；C resolve 后独占 results/empty/error/loading。
- **close while pending**：关闭期间请求失败 → 无可见 stale error；reopen → 当前关键词的真实 error+retry 状态（一致，非污染）。

`fetch` 完成顺序在测试中完全人为控制（`Map<keyword, deferred>`），证明不依赖时序运气。未删除/弱化既有测试；Gate 5/6A 及历史 regression 全部保留。

# Browser Verification

方法：headless Chrome（CDP，独立临时 profile，端口 9336）+ 本轮自启 Vite `127.0.0.1:5173`（PID 54148，验证后停止并释放）+ 既有后端 `127.0.0.1:8000`（未终止）；network-error 用 throwaway Vite 5174 指向 dead 8010（PID 56272，验证后停止释放）。共 12/12 通过：

| 场景 | 结果 |
| --- | --- |
| Ctrl+K 打开 | dialog 出现 |
| focus | activeElement = 搜索输入框 |
| 正常搜索“软件” | 结果区 `搜索结果，共 33 条` |
| 快速改 query（竞赛→蓝桥→推免） | 稳定落在最终关键词状态，无旧关键词 empty 残留 |
| clear query | 回 idle“输入关键词开始搜索” |
| 搜索“不存在关键词xyz” | “没有匹配“不存在关键词xyz”的通知” |
| Escape 关闭 | dialog 消失 |
| Ctrl+K 重开 | 输入框保留“不存在关键词xyz”，状态一致 |
| network error（5174→dead 8010） | “无法连接本地服务”+“重新连接”，不显示“没有匹配” |

（浏览器无法稳定人为控制真实后端响应顺序，故乱序正确性以 deterministic 单测为主要证据；浏览器只做功能级局部验证，符合本 Gate 约定。）

# Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 21 files / 102 tests（96 → 102） |
| `npm run lint` | PASS — 0 errors（初版遗留一个未用 helper，已删除后通过） |
| `npm run build` | PASS — 2788 modules |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 tests |

（沙箱拦截原生子进程与原生 Tailwind oxide 加载，按既有先例以 `danger-full-access` 重跑；未改项目配置。）

# Files Changed

- `frontend/src/components/search/SearchDialog.race.test.tsx`（新增，6 项 concurrency regression）
- `docs/GATE_6B_REPORT.md`（本报告）

生产代码零改动；无新增依赖。

# Preserved Behavior

全部 unchanged：

- SearchDialog 视觉设计与 UI 分支（idle/loading/result/empty/error）。
- debounce 语义（300ms trailing，`useDebouncedValue` 未改）。
- URL schema 与 `/api/search` 响应 schema。
- request lifecycle（AbortController + external signal + 15s timeout + cleanup）与 error taxonomy（ABORTED 静默）。
- Settings/persistence contract（Gate 6A 的 `settings.ts`/`theme.tsx` 未碰）。
- routes、auto-read、mutation、Dashboard/Collection/Detail/Sources 页面。
- responsive/accessibility 行为。

# Deferred

## Gate 6C

- mutation response contract（read/favorite 返回类型）。
- API normalization、TanStack Query/cache governance、source filter data-driven architecture。

# Recommended Next Gate

Gate 6C — Mutation Contract / API & State Governance
