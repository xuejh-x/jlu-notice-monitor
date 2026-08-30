# Gate 6C Result（第 1 轮 — Favorite Mutation Chain）

**PASS**

Gate 6C 第一轮完成 favorite/read mutation chain 的 contract 治理：

```
用户点击收藏 → mutation → backend → TanStack Query cache → Notices / Favorites / Dashboard / Notice Detail
```

审计发现 3 个真实问题并全部最小修复：mutation 返回类型与真实 backend 契约不符（F-008）、详情页收藏后不失效 Dashboard 缓存、列表收藏后不失效 Detail 缓存。统一失效集收敛到单一 helper，保证四个消费者一致。**未改 backend、未改 UI、未加 optimistic update、未加依赖。**

# Existing Architecture

- **Backend 契约**（`backend/app/api/routes.py` `_set_state`）：`POST /api/notices/{id}/read|unread|favorite|unfavorite|archive|unarchive` → 动态键响应，实测 `{"notice_id":34,"is_favorite":true}`（键是 mutated field 名，不是 `field` 字符串）。
- **前端 mutation**：`api/notices.ts` 的 `setNoticeRead`/`setNoticeFavorite` 声明为 `apiRequest<Notice>`（错误）；两个调用点（`NoticeCard`、`NoticeDetailPage`）均不消费返回值，依赖 onSuccess 失效 + refetch。
- **cache key 空间**：`['notice', id]`（详情）、`['notices', ...]`（all/favorites/feed/competitions/deadlines/today/important）、`['dashboard']`（unread 计数 + `recent_notices` 经 NoticeCard 渲染）、`['search', keyword]`（无星标，不涉及）。
- **失效矩阵（改前）**：Card 收藏 → `['notices']`+`['dashboard']`；Detail 收藏 → `['notice',id]`+`['notices']`；auto-read → `['notices']`+`['dashboard']`。
- app QueryClient：`staleTime 30s / retry 1 / refetchOnWindowFocus false`。

# Problems Found

1. **Mutation response contract 与真实 backend 不符（F-008）**
   - problem：`setNoticeRead`/`setNoticeFavorite` 类型为 `Notice`；backend 实际返回动态键 state object（实测 `{"notice_id":34,"is_favorite":true}`）。
   - impact：类型在说谎；任何未来消费者按 `Notice` 读取会拿到 undefined 字段（当前无人消费，latent）。
   - reproduction：`POST /api/notices/34/favorite` 响应体为 `{"notice_id":34,"is_favorite":true}`，与 `Notice` 形状不符。
   - root cause：类型从未按真实响应修正（UI_AUDIT F-008 遗留）。

2. **Detail 收藏不失效 `['dashboard']`**
   - problem：详情页收藏后，30s（staleTime）内返回 Dashboard，`['dashboard']` 缓存仍 fresh → `recent_notices` 星标显示旧状态。
   - impact：用户刚在详情收藏，首页星标却未收藏（最长 30s）。
   - reproduction：`/`（prime dashboard cache）→ 客户端导航到 `/notices/34` → 点收藏 → 客户端导航回 `/` → 星标仍是旧状态。
   - root cause：Detail 的 onSuccess 只失效 `['notice',id]`+`['notices']`，漏 `['dashboard']`。

3. **Card 收藏不失效 `['notice', id]`**
   - problem：列表收藏后 30s 内重开详情，`['notice',id]` 缓存 fresh → 详情星标显示旧状态。
   - impact：列表刚收藏，详情星标却未收藏。
   - reproduction：打开详情（缓存 `['notice',id]`）→ 返回列表 → 列表点收藏 → 重开详情 → 星标旧。
   - root cause：Card 的 onSuccess 只失效 `['notices']`+`['dashboard']`，漏 `['notice',id]`。

# Changes

- `frontend/src/types/index.ts`：新增 `NoticeStateResult`（discriminated union，匹配真实动态键响应）。
- `frontend/src/api/notices.ts`：`setNoticeRead` → `Extract<NoticeStateResult, { is_read: boolean }>`、`setNoticeFavorite` → `Extract<NoticeStateResult, { is_favorite: boolean }>`。
- `frontend/src/utils/noticeCache.ts`（新增）：`invalidateNoticeState(client, noticeId)` —— 唯一权威失效集 `['notice', id]` + `['notices']` + `['dashboard']`。
- `frontend/src/components/notice/NoticeCard.tsx`：收藏 onSuccess → `invalidateNoticeState`（补上 `['notice',id]`）。
- `frontend/src/pages/NoticeDetailPage.tsx`：收藏 onSuccess → `invalidateNoticeState`（补上 `['dashboard']`）。
- auto-read effect 与 backend **未改**（P1 保留行为）。

# Tests Added

新增 6 项（102 → 108，23 files）：

- `api/notices.test.ts`（3）：favorite/unfavorite/read 的 endpoint + POST method + 解析真实动态键 payload（`{notice_id, is_favorite: true}`）。
- `utils/noticeCache.test.ts`（1）：`invalidateNoticeState` 恰好以三个权威 key 调用 `invalidateQueries`。
- `NoticeCard.test.tsx`（+1）：行为证明——列表收藏后，挂载中的 `['notice',7]` observer 被 refetch（GET 1→2）。
- `NoticeDetailPage.test.tsx`（+1）：行为证明——详情收藏后，挂载中的 `['dashboard']` observer 被 refetch（GET 1→2）。

未删除、skip、todo 或弱化任何既有测试。

# Browser Verification

方法：headless Chrome（CDP，独立临时 profile，端口 9338）+ 本轮自启 Vite 5173（PID 56152，验证后停止释放）+ 既有后端 8000（未终止）。真实数据 notice 34（原状态 `is_favorite=true`），**全程客户端 SPA 导航**（保留 QueryClient cache）以证明跨路由失效，5/5 通过：

| 步骤 | 结果 |
| --- | --- |
| `/` prime dashboard cache | notice 34 星标 `取消收藏`（与真实状态一致） |
| 客户端导航到 `/notices/34` | 详情星标 `取消收藏` |
| 详情点击收藏（unfavorite） | 星标翻转为 `收藏通知`（`['notice',34]` 失效 + refetch 生效） |
| 客户端导航回 `/` | Dashboard 星标变为 `收藏通知`（30s 内缓存被 `['dashboard']` 失效 → refetch，旧实现会显示 stale 星标） |
| 客户端导航 `/favorites` | notice 34 从收藏列表消失（`['notices','favorites']` 失效生效） |

验证后通过 API 恢复：`POST /api/notices/34/favorite` → `{"notice_id":34,"is_favorite":true}`，Dashboard 复查 `is_favorite=True`——无数据污染。该恢复响应同时实证了 backend 动态键契约（问题 1 的现场证据）。

# Validation

| 命令 | 结果 |
| --- | --- |
| `npm test -- --run` | PASS — 23 files / 108 tests（102 → 108） |
| `npm run lint` | PASS — 0 errors |
| `npm run build` | PASS — 2789 modules |
| `backend/.venv/Scripts/python.exe -m pytest` | PASS — 43 tests |

（沙箱拦截原生子进程与原生 Tailwind oxide 加载，按既有先例以 `danger-full-access` 重跑；未改项目配置。）

# Files Changed

- `frontend/src/types/index.ts`（`NoticeStateResult`）
- `frontend/src/api/notices.ts`（mutation 返回类型对齐真实契约）
- `frontend/src/utils/noticeCache.ts`（新增，权威失效集）
- `frontend/src/utils/noticeCache.test.ts`（新增）
- `frontend/src/components/notice/NoticeCard.tsx`（收藏失效改用 helper）
- `frontend/src/components/notice/NoticeCard.test.tsx`（+1 行为测试）
- `frontend/src/pages/NoticeDetailPage.tsx`（收藏失效改用 helper）
- `frontend/src/pages/NoticeDetailPage.test.tsx`（+1 行为测试）
- `frontend/src/api/notices.test.ts`（新增，mutation contract）
- `docs/GATE_6C_REPORT.md`（本报告）

# Preserved Behavior

全部 unchanged：

- backend（`routes.py` 与全部 endpoint 未改）。
- mutation 交互模型（server-confirmed + invalidate + refetch，无 optimistic update）。
- toast 文案与触发语义、收藏按钮 UI/aria-label/焦点。
- auto-read（`Set<number>` effect 逐字未改，仍失效 `['notices']`+`['dashboard']`）。
- URL schema、request lifecycle、error taxonomy、SearchDialog、Settings、routes、responsive/accessibility。

# Deferred（Gate 6C 后续轮次）

- mutation 返回值的 UI 消费（若未来需要 optimistic update / 直接用 `{notice_id, is_*: bool}` 更新）。
- API normalization、TanStack Query cache/staleTime/gcTime 策略治理、source filter data-driven architecture。
- archive/unarchive 前端消费（当前无 UI，类型已覆盖于 union）。

# Recommended Next Gate

Gate 6C 第 2 轮 — API / Query Cache Governance（或按新的 Gate 规划执行）
