# Gate 10 Final Re-Soak Acceptance Report

## 1. 最终结论

**Gate 10 Final：PASS**

固定修复制品 `codex/gate10-resoak@538bb7c056e3e3b7a6339a2c4de296bbbb87140d` 已完成超过 72 小时的连续生产 re-soak。正式观察窗内没有可用性、scheduler、来源、SQLite、TLS、备份或资源告警；增量详情抓取缺陷未复现，尤其 `csw` 在 295 个唯一 scheduled 轮次中保持 `0` 次详情抓取、`8,850` 次详情跳过。

本次验收没有新增功能、没有修改 API 或数据库结构，也没有把 Gate 12–14 代码部署到 Gate 10 固定制品。生产 re-soak 与当前 `0.6.0` 开发线兼容回归分别取证，避免把不同制品的结果混写。

验收时间：`2026-09-11`（Asia/Shanghai）

## 2. 验收范围与证据边界

| 证据面 | 制品 | 用途 |
| --- | --- | --- |
| 生产固定制品 | `538bb7c056e3e3b7a6339a2c4de296bbbb87140d`，版本 `0.2.0` | 72h re-soak、真实 scheduler、真实多来源、增量详情请求、SQLite、服务重启 |
| 当前兼容回归 | `b4c306dcc9b2fce6bf50f258fe93b2fe7703637c`，版本 `0.6.0`，含工作区既有未提交改动 | new/updated fixture、Cloud/Private execution、Notification、未读状态与 Dashboard 统计 |

固定制品有意只包含 Gate 10 blocker 修复、直接回归测试和历史验收文档。若在观察窗内部署 Gate 12–14，将使 72h 固定制品证据失效，因此本轮没有这样做。

## 3. 测试环境与配置

### 3.1 生产环境

- OS：Ubuntu Linux，kernel `6.8.0-137-generic`，x86_64。
- Python：`3.12.3`；SQLite：`3.45.1`；FastAPI：`0.141.1`；SQLAlchemy：`2.0.52`；Uvicorn：`0.52.4`。
- Git branch：`codex/gate10-resoak`。
- Git SHA：`538bb7c056e3e3b7a6339a2c4de296bbbb87140d`；观察窗内唯一 SHA。
- Backend：systemd `notice-hub.service`，`/api/health` 返回 `status=ok`、`database=ok`、`crawler=idle`、`scheduler=running`、`environment=production`。
- Scheduler：enabled，15 分钟间隔；source concurrency `2`；retries `2`；retry backoff `1.0s`。
- SQLite：`/var/lib/notice-hub/data/notices.db`。
- 来源：`cse`、`ccst`、`csw`、`jwc`、`innovation` enabled；`oa` disabled 且 requires login。

正式 re-soak 前服务启动于 `2026-09-08 19:05:19 CST`，至终态冻结前 `NRestarts=0`。完成冻结后按验收要求进行了受控重启；当前启动时间与恢复结果见第 9 节。

### 3.2 当前兼容回归环境

- OS：Windows `10.0.26100.0`。
- PowerShell：`7.6.5`；Node.js：`v24.16.0`；npm：`11.13.0`；Python：`3.13.13`。
- 当前版本：`0.6.0`。
- 工作树在验收前已存在多项 Gate 13.5/13.6 与 UI 改动；本轮不 reset、不覆盖、不整理这些用户改动。

## 4. Re-Soak 运行时间与健康统计

正式观察窗：

- Start：`2026-09-08 19:13:15.359578 CST`。
- End：`2026-09-11 21:00:28.543406 CST`。
- Duration：`73.787h`。
- 最低要求：`72h`；超出要求约 `1.787h`。
- 健康采样：`298`。
- 成功 / warning / failed：`298 / 0 / 0`。
- uptime ratio：`100%`。

| 指标 | 结果 |
| --- | ---: |
| Backend failures | 0 |
| Nginx failures | 0 |
| Health failures | 0 |
| Scheduler failures | 0 |
| Source failure checks | 0 |
| Database failures | 0 |
| TLS failures | 0 |
| Backup failures | 0 |
| Fatal incidents | 0 |
| Invalid soak log lines | 0 |
| Max memory used | 582.734 MiB |
| Min memory available | 1,030.23 MiB |
| Max swap used | 0 MiB |
| Max disk used | 15.085% |
| Max inode used | 4.917% |

## 5. Crawler 轮次与增量统计

生产 API `0.2.0` 尚未暴露独立 `run_id` 字段，也不在完成态单独持久化 `started_at`。为保持验收只读且不改 API，本报告使用 `(trigger_source, last_run)` 作为唯一轮次键，并由 `last_run - duration` 还原 scheduled started_at。例如首轮为 `scheduled:2026-09-08T11:20:23.284050Z`，末轮为 `scheduled:2026-09-11T12:59:22.096227Z`。所有逐轮原始记录保存在轮转后的 `/var/log/notice-hub/soak.log*`；报告不内联 295 行重复明细。

### 5.1 汇总

| 指标 | 结果 |
| --- | ---: |
| Unique crawler runs | 295 |
| Scheduled / manual（正式窗内） | 295 / 0 |
| Success / failure | 295 / 0 |
| 每轮 source count | 6 |
| List items 总数 | 23,895 |
| New 总数 | 0 |
| Updated 总数 | 0 |
| Unchanged 总数 | 23,895 |
| Detail fetched 总数 | 590 |
| Detail skipped 总数 | 23,305 |
| Detail skip ratio | 97.531% |
| Duration min / avg / max | 1.520s / 1.826s / 7.348s |

正式观察窗内外部站点没有产生真实 new/updated 样本，因此不能用生产数据声称验证了这两种状态；它们由第 7 节的可重复 fixture 回归覆盖。

### 5.2 首轮与末轮

| 轮次 | started_at → last_run（UTC） | duration | sources | new / updated / unchanged | detail fetched / skipped | errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 首个 scheduled | `2026-09-08T11:20:21.405050`（derived）→ `11:20:23.284050` | 1.879s | 6 | 0 / 0 / 81 | 2 / 79 | 0 |
| 最后 scheduled | `2026-09-11T12:59:20.488227`（derived）→ `12:59:22.096227` | 1.608s | 6 | 0 / 0 / 81 | 2 / 79 | 0 |
| 验收手动轮次 | `2026-09-11T13:05:17.807705` → `13:05:19.347220` | 1.540s | 6 | 0 / 0 / 81 | 2 / 79 | 0 |
| 重启后首个 scheduled | `2026-09-11T13:23:52.202727` → `13:23:53.962602` | 1.755s | 6 | 0 / 0 / 81 | 2 / 79 | 0 |

### 5.3 Detail fetch 按来源

| Source | Detail fetched | Detail skipped | 结论 |
| --- | ---: | ---: | --- |
| `cse` | 295 | 2,950 | 每轮仅 1 个真实 title 差异触发必要详情 |
| `ccst` | 0 | 2,950 | unchanged 全部跳过详情 |
| `csw` | **0** | **8,850** | 旧 blocker `30/30` 重抓未复现 |
| `jwc` | 295 | 4,130 | 每轮仅 1 个真实 title/date 差异触发必要详情 |
| `innovation` | 0 | 4,425 | unchanged 全部跳过详情 |
| `oa` | 0 | 0 | disabled/private，按配置跳过 |

`cse/jwc` 的两个详情请求在内容比较后仍归类为 unchanged；它们是列表元数据与已存详情元数据的真实差异，不是“列表缺少可选字段”导致的误判。

## 6. SQLite 与数据稳定性

正式观察窗 start/end：

- notices：`88 → 88`。
- SQLite size：`454,656 bytes → 454,656 bytes`。

终态与手动轮次、重启前后：

| 数据项 | Before manual | After manual | After restart |
| --- | ---: | ---: | ---: |
| notices | 88 | 88 | 88 |
| notice_source_relations | 93 | 93 | 93 |
| attachments | 68 | 68 | 68 |
| notice_updates | 0 | 0 | 0 |
| DB size | 454,656 | 454,656 | 454,656 |
| `PRAGMA quick_check` | ok | ok | ok |

终态重复检查：duplicate canonical URL `0`，duplicate per-source URL `0`。最新备份 `notices-20260911T032308.db` 为 `454,656 bytes`、88 条 notices、`quick_check=ok`，与 live DB 一致。

结论：295 个无变化 scheduled 轮次及额外手动轮次没有生成重复 notice、relation、attachment 或 update，数据库没有异常增长。

## 7. New / Updated / Unchanged 正确性

当前开发线的 deterministic crawler fixture 覆盖同一来源连续三轮：

1. 初次运行：1 个新 notice，`new=1`、`detail_fetched=1`。
2. 未修改再次运行：`unchanged=1`、`detail_skipped=1`，详情调用总数不增加。
3. 修改原 notice 并加入新 notice：`updated=1`、`new=1`、`detail_fetched=2`；数据库最终只有 2 条 notice，不产生重复。

专门的 Gate 10 regression 还覆盖“详情页补充 publish date/publisher、列表页下一轮缺少这些可选字段”的旧缺陷：第二轮 `unchanged=1`、`detail_fetched=0`、`detail_skipped=1`。

结论：new 正常创建；updated 更新原记录；unchanged 不重复抓取详情或创建重复记录。

## 8. 来源覆盖与 execution 边界

### 8.1 固定生产制品

- 五个公开学院来源由服务器 scheduler 抓取，295 个轮次全部成功。
- OA 为登录型私有来源，生产配置 `enabled=false`，每轮明确 skipped；未把 Cookie/Session 上传生产。
- `538bb7c` 是 Gate 10 专用制品，早于 Gate 13 的 `execution=cloud/local` 与 Cloud Registry 模型，因此不把它伪称为 Cloud Registry 线上覆盖。

### 8.2 当前架构兼容回归

当前 `0.6.0` 完整 Backend/E2E 已覆盖：

- Official/Shared 的 Cloud feed 全局可见，Cloud Source 映射后禁用 Desktop 本地抓取。
- Local/Private source 不进入公共 Cloud feed。
- OA 认证失败不会阻塞公开来源；公开来源仍可创建 new notice。
- Cloud 映射重启式恢复后不产生本地重复动作，read/favorite 状态保持。

结论：Gate 10 增量修复与后续 `execution=cloud/local` 边界兼容，Desktop 不重复抓 Cloud Source。

## 9. Notification 回归

Gate 14 未部署到 Gate 10 固定生产制品，因此正式 72h 窗口没有 Notification 表或投递状态可供线上归因；本节只签署当前 `0.6.0` 兼容回归，不把本地 fixture 当作生产事件。

验证结果：

- new/important/deadline/daily summary 事件有稳定 dedupe key，重复生成返回空集合。
- delivery claim 将待投递记录进入 `SENDING`；成功确认落为 `DELIVERED`，失败可进入 `FAILED` 并按策略重试；过期且结果不确定的 `SENDING` 不盲目重发。
- SQLite 重开模拟重启后，已 `DELIVERED` 的通知不能再次 claim，避免重复发送。
- E2E `restart-style regeneration does not duplicate a daily notification` 通过。
- “标记未读”一次点击即发出一次 mutation 并保持未读；进入未读筛选后“全部通知”仍来自独立 dashboard total。
- read/unread、favorite、important、deadline 统计彼此独立；Gate 14 additive migration 保留既有 user state。

结论：Notification 状态流、重启防重、已读/未读和 Dashboard 统计回归通过。

## 10. 异常恢复

### 10.1 Backend 重启

正式观察窗冻结后执行一次受控 `systemctl restart notice-hub.service`：

- `/api/health` 恢复为 200/ok。
- `scheduler=running`，下一 scheduled 时间存在。
- Git branch/SHA 未变化。
- SQLite 计数、文件大小与 `quick_check` 未变化。
- 最近 3 分钟 journal warning-or-higher：0。

首次重启捕获到 `NeedDaemonReload=yes`：磁盘 unit 文件自 `2026-09-01` 起未变化、内容与路径正常，但 systemd manager 缓存没有 reload。这是运维配置缓存漂移，不是 crawler 代码缺陷。已执行 `systemctl daemon-reload` 并重复重启，复验为 `NeedDaemonReload=no`、service active/running、scheduler running、数据库稳定、journal 无 warning。

重载后的 service activation：`2026-09-11 21:08:50 CST`，PID `64259`。

Journal 同时确认旧进程依次记录 `application_stopping`、`scheduler_stopped`、`application_stopped` 并正常退出；新进程记录 `application_starting`、`scheduler_started`、`application_started`，随后 health/status 请求均为 200。不是仅依赖状态端点推断恢复。

重启后的首个正常 tick 于 `2026-09-11 21:23:52 CST` 自动触发，`21:23:53` 完成：trigger=`scheduled`、status=`success`、duration `1.755s`、6 个来源、`0 / 0 / 81`（new/updated/unchanged）、detail `2 / 79`（fetched/skipped）、`csw` `0 / 30`，scheduler next run 已排定且 last error 为 null。完成后数据库仍为 88 notices、93 relations、68 attachments、0 updates、`454,656 bytes`、`quick_check=ok`。

生产访问边界复验：仅一个 Backend Uvicorn 进程；FastAPI 只监听 `127.0.0.1:8000`；HTTP 返回 301 到 HTTPS；未认证 HTTPS API 返回 401；Nginx、soak、backup、certbot timers 均 active+enabled。

### 10.2 单来源与网络异常

- 正式生产窗：`source_failure_checks=0`，无真实网络异常可复现样本。
- Deterministic regression：单来源 `TimeoutError` 被记录到 `Source.last_error`；该来源返回 failure。
- OA auth failure 与公开来源并行时，总体为 partial failure，但公开来源仍成功并创建 notice。
- 单条 detail parser 失败时，健康 item 仍持久化，来源状态为 partial failure，不影响其他数据。
- Scheduler 对 failure/partial failure 保留状态与错误；下一 tick 可恢复；长任务不堆叠重入。

结论：没有通过主动破坏生产网络制造事故；异常隔离、错误记录、timeout 和恢复由确定性测试覆盖。

## 11. 测试结果

| Suite | Result |
| --- | --- |
| Exact production release Backend（部署前留存） | 63/63 PASS |
| Current Backend full | 132/132 PASS，9.85s |
| Gate 10 / scheduler / Gate 14 / counts 专项 | 41/41 PASS |
| Frontend Vitest | 28 files，169/169 PASS |
| Frontend lint | PASS |
| Frontend production build | PASS，2,804 modules transformed |
| Browser E2E | 24/24 PASS，36.4s |

非阻断备注：Vite 仍报告单个压缩前 chunk 大于 500 kB；E2E 测试后端在浏览器关闭连接时记录过一次 Windows `10054` connection reset，但 24/24 用例与服务退出均正常。这两项均不属于生产 Gate 10 故障，本轮未做无关优化。

## 12. Gate 10 Final PASS 标准

| 标准 | 结果 | 证据 |
| --- | --- | --- |
| Re-soak 达到目标周期 | PASS | 73.787h ≥ 72h |
| 无重大故障 | PASS | 298/298 checks，0 warning，0 failure，0 fatal |
| unchanged 不重复抓详情 | PASS | 23,305 skipped；`csw` 0 fetched / 8,850 skipped |
| scheduler 长时间稳定 | PASS | 295/295 unique scheduled runs success |
| Notification 正常 | PASS | 当前 0.6.0 Backend + E2E 状态流与防重回归通过 |
| 数据库无异常增长 | PASS | 88 notices、454,656 bytes、关系/附件/update 不变，quick_check=ok |
| 重启恢复正常 | PASS | 两次受控恢复均健康；daemon-reload 漂移已消除；首个自动 tick 成功 |

## 13. 变更、API 与数据库

- 本轮修改文件：仅新增 `docs/GATE_10_FINAL_ACCEPTANCE_REPORT.md`。
- 功能代码：无修改。
- API：无变化。
- 数据库 schema/migration：无变化。
- 生产数据：手动抓取与重启均未新增、删除或重建业务数据。
- 运维状态：执行一次 `systemctl daemon-reload`，消除已确认的 unit 缓存漂移；service unit 内容未修改。

## 14. 当前 Gate 状态

**Gate 10 Final 已正式验收通过（PASS）。**

旧的 `docs/GATE_10_FINAL_ACCEPTANCE.md` 继续保留为修复前 FAIL 的历史证据；本报告是 `538bb7c` 固定制品完成 re-soak 后的最终签署，不覆盖或改写历史失败记录。
