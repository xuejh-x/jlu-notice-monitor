# Gate 10 Final Acceptance

## Final Result

**FAIL**

Gate 10 的生产稳定性浸泡已经超过最低 72 小时，并且可用性、SQLite 完整性、调度连续性、备份、TLS 续期和资源水位均达到验收阈值。但是，已浸泡的生产版本存在可复现的增量抓取缺陷：列表页未提供可选元数据时，已保存的详情页元数据会被误判为“列表发生变化”，导致未变化详情页被周期性重复抓取。2026-09-08 的一轮生产任务中，81 条已存在通知有 41 条重新抓取详情，其中 `csw` 为 30/30；该轮新增 0、更新 0。

该问题已在当前工作区做最小修复并通过完整本地回归，但修复尚未部署到 Gate 10 生产版本，也没有基于修复后构建重新取得 72 小时生产证据。因此不能将既有浸泡结果移植到修复后的代码上，也不能签署 Gate 10 PASS。

验收时间：2026-09-08（Asia/Shanghai）

## Acceptance Scope and Criteria Recovery

仓库中不存在 `docs/GATE_10*.md`，完整 Git 历史中也没有 Gate 10 报告文件。因此，本次没有把后续 Gate 的描述反向当作原始标准，而是从以下证据恢复验收边界：

1. 当前 Gate 10 最终验收任务给出的强制检查项和 72 小时最低标准。
2. 历史任务交接记录中的首次生产部署、生产加固和 Gate 10D 监控设置要求。
3. Git 提交 `9149448`（crawler scheduling and diagnostics）和 `d9042b0`（trigger visibility race fix）。
4. 当前仓库真实实现、测试和生产只读诊断。

历史资料明确记录了 Gate 10B、10C 已通过，以及 Gate 10D 的监控已设置但最终验收待完成；没有找到能够独立恢复“Gate 10A”原始标题和逐字条款的仓库事实。下表因此只对可证实的边界作结论，不伪造缺失的原文。

| Phase | Recovered scope | Result | Evidence |
| --- | --- | --- | --- |
| Gate 10A | 原始标签/逐字标准不可恢复；可确认其前置运行时能力由 `9149448`、`d9042b0` 提供 | PASS（仅限可恢复范围） | scheduler、并发锁、状态持久化、结构化诊断实现及回归测试存在 |
| Gate 10B | 首次生产部署与服务运行 | PASS | 历史部署记录；当前 `notice-hub`、Nginx 均 active；生产数据持续更新 |
| Gate 10C | HTTPS、访问控制、systemd、备份、日志轮转和重启后恢复 | PASS | 当前 HTTPS/401/301、loopback-only、各 timer、轮转文件和 8 份备份的只读证据 |
| Gate 10D | 至少 72 小时生产 soak，并完成最终关闭验收 | FAIL | 167.858 小时稳定性指标达标，但浸泡版本的增量详情抓取不满足最终验收；修复后尚未重新浸泡 |

## Production Timeline

所有时间均换算为 Asia/Shanghai（UTC+08:00）。

| Time | Event / evidence |
| --- | --- |
| 2026-09-01 18:23:58 | 最早保留的结构化 soak 样本 |
| 2026-09-02 06:10:35 | 当前 `notice-hub` systemd activation 起点；截至验收 `NRestarts=0` |
| 2026-09-04 20:30 左右 | 监控样本中的证书到期时间从 2026-09-08 更新为 2026-09-11，证明自动续期实际成功 |
| 2026-09-08 18:15:28 | 本次分析使用的最后一个完整 soak 样本 |
| 2026-09-08 18:18–18:26 | 只读在线复核；服务健康，最近一次 scheduled crawler 成功 |

保留样本覆盖 **167.858 小时（约 6 天 23 小时 51 分）**，共有 673 条 15 分钟采样记录；相邻样本最大间隔 946.637 秒。满足“至少 72 小时连续证据”的时长要求。

## Soak Evidence

### Availability and continuity

| Metric | Required | Observed | Result |
| --- | ---: | ---: | --- |
| Backend active samples | ≥99% | 673/673，100% | PASS |
| Nginx active samples | ≥99% | 673/673，100% | PASS |
| Health endpoint | 持续正常 | 673/673 `ok` | PASS |
| Monitor overall | 无持续失败 | 670 `ok`，3 `warning`，0 `fail` | PASS |
| Backend restarts | 无 restart loop | 当前 activation 内 0 | PASS |
| OOM events | 0 | 0 | PASS |
| Fatal events | 无持续 fatal | 0 | PASS |

应用日志保留区间内记录 676 个 crawler rounds，其中 674 个为 scheduler 触发、2 个为人工触发。Crawler 结果为 674 success、2 partial failure；scheduler 完成结果为 672 success、2 partial failure。没有积压式并发运行或持续失败证据。

### Database and data safety

| Check | Observed | Result |
| --- | --- | --- |
| Soak SQLite integrity | 673/673 `ok` | PASS |
| Current DB `PRAGMA quick_check` | `ok` | PASS |
| Backup spot checks | 2026-09-01、05、06、07、08 的备份均 `ok` | PASS |
| Backup count | 8 份（日更，要求至少 3 份） | PASS |
| Backup freshness | 最大观测 age 23.974 h，低于 36 h 阈值 | PASS |
| Duplicate canonical URL | 0 | PASS |
| Duplicate source URL | 0 | PASS |

验收时生产库包含 88 条 notices、6 个 sources、93 条 notice/source relations、68 个 attachments 和 88 条 user states。`first_seen_at` 范围为 2026-09-01 至 2026-09-06，`last_seen_at` 已推进至 2026-09-08，说明调度任务持续刷新已见记录，而非只启动不工作。

### Sources and scheduler

- Scheduler：enabled、running，间隔 15 分钟；最近一次结果 success，下一次运行时间存在。
- 最近一次生产抓取：scheduled，5 个公开来源均 success；OA 按配置 disabled，不作为公开来源故障。
- 3380 个 source runs 中有 3375 success、5 failure（0.148%）；失败分布为 `ccst` 2 次，`cse`、`csw`、`jwc` 各 1 次。
- 两次 partial-failure 均在下一个 15 分钟样本恢复：一次只影响 `ccst`，一次同时影响 4 个来源。没有来源持续不可用，也没有全来源持续失败。
- 监控样本的 healthy source 最低值为 1、最高值为 5；最低值只出现于上述瞬时事件，下一采样恢复为 5。

### TLS, access boundary, backup and rotation

- 673/673 样本：TLS 检查成功。
- 673/673 样本：HTTP 返回 301，未认证 HTTPS 返回 401，Backend 保持 loopback-only。
- `notice-hub-backup.timer`、`notice-hub-soak.timer`、`snap.certbot.renew.timer` 均 active/enabled。
- soak 与 app 日志均存在按日轮转文件；soak 覆盖 2026-09-01 至 2026-09-08。
- 首张观测证书到期时间为 2026-09-08T00:23:31Z；2026-09-04 的后续样本切换到 2026-09-11T11:18:25Z，证明续期链路在 soak 内真实执行，而非仅 timer 显示 active。

### Resource health

| Metric | Observed maximum/minimum | Result |
| --- | ---: | --- |
| Memory used | max 540.129 MB | PASS |
| Memory available | min 1072.836 MB | PASS |
| Swap used | max 0 | PASS |
| Disk used | max 14.768% | PASS |
| Inodes used | max 4.913% | PASS |
| 1-minute load | max 0.555 | PASS |
| Monitor checker duration | max 530.471 ms | PASS |

没有 OOM、磁盘异常增长、inode 压力、swap 抖动或负载持续升高证据。

## Incident Review

**Major incidents: 0**

保留记录中有 3 个 overall warning：

1. 2026-09-07 05:15 左右：Nginx error count 为 4，但 severe count 为 0，服务、健康检查、crawler、scheduler、数据库均正常，下一样本恢复。
2. 2026-09-07 14:45 左右：`ccst` 单次 partial failure，下一样本恢复。
3. 2026-09-08 06:00 左右：4 个来源单次 partial failure，仍有 1 个健康来源，下一样本全部恢复。

这些事件不构成持续生产事故，也没有耗尽稳定性错误预算。真正阻断 Gate 的问题来自功能/效率验收，而非可用性指标。

## Functional Audit

### Scheduler and concurrency

- 同一进程使用 async lock，并使用 on-disk lock 防止跨任务重入。
- manual/scheduled 冲突走 `skipped_running`，不会形成待运行积压。
- shutdown 会取消并等待活动 crawler；scheduler 支持 clean restart。
- 状态端点公开 current source、completed/total、trigger source、last/next run 和错误结果。
- 本地 scheduler/runtime/orchestration 回归全部通过；生产日志没有重叠执行或 restart loop 证据。

### Deduplication

- 生产库 canonical URL 重复数：0。
- 生产库同一 source URL 重复数：0。
- 88 notices 对应 93 source relations，符合跨来源关系模型；没有以“关系数大于通知数”误判重复。
- 新增/更新/未变化计数持续产生，最近生产轮次为 0/0/81。

### Incremental crawling — blocker

最近生产轮次的明细：

| Source | List fetched | Detail fetched | Detail skipped | New / updated / unchanged |
| --- | ---: | ---: | ---: | ---: |
| cse | 11 | 1 | 10 | 0 / 0 / 11 |
| ccst | 10 | 0 | 10 | 0 / 0 / 10 |
| csw | 30 | 30 | 0 | 0 / 0 / 30 |
| jwc | 15 | 4 | 11 | 0 / 0 / 15 |
| innovation | 15 | 6 | 9 | 0 / 0 / 15 |

合计 81 条列表项中 41 条（50.6%）重新抓取详情；`csw` 为 100%。应用日志还显示若干稳定详情 URL 在保留期内被请求约 675 次，与每 15 分钟重复抓取一致。

根因位于 `CrawlerManager._find_unchanged_list_item`：通用列表解析器不会总是提供 `publish_date`/`publisher`，详情解析则可能补充它们。旧逻辑对这些可选字段做严格相等比较，因而把“列表缺字段、数据库已有详情值”误判成变化。

### Local corrective change

已做最小修复：

- 标题仍必须严格相等。
- 列表页实际提供 publish date 或 publisher 时，仍使用它们识别可疑变化。
- 列表页没有提供可选字段时，不再用缺失值否定详情页已保存的丰富元数据。
- 新增回归覆盖“详情页补充日期/发布者后，下一轮应跳过详情”。

该修复只影响增量抓取的 cheap-change detector；没有修改 URL、去重键、正文 content hash、附件、API、数据库 schema、scheduler 或 UI。

## Regression

验收在当前工作区 HEAD `367f2d1a6c7529fc2a7945b4b6dd637b8a1828fb` 加上述未提交 Gate 10 修复上执行。生产 Gate 10 构建记录对应 `d9042b0f3b21d05a7284b48df16133e7a8c9b469`，API version 为 `0.2.0`；两者不是同一已部署制品，故本地结果不冒充生产部署验证。

| Layer | Command | Result |
| --- | --- | --- |
| Targeted crawler regression | `pytest backend/tests/test_crawler_orchestration.py -q` | 5/5 PASS |
| Backend | `pytest backend -q` | 114/114 PASS |
| Frontend unit/integration | `npm test -- --run` | 28 files，143/143 PASS |
| Frontend lint | `npm run lint` | PASS |
| Frontend production build | `npm run build` | PASS，2802 modules transformed |
| Browser E2E | `npm run e2e -- --reporter=line` | Chromium 18/18 PASS |

非阻断提示：Vite 报告单个压缩前 JS chunk 约 510.92 kB；E2E 通过期间测试服务记录一次客户端连接重置。两者均未导致测试、构建或生产 soak 失败，不作为 Gate 10 blocker。

## Problems Found

### G10-F01 — P1 / Gate blocker: unchanged details are repeatedly fetched

- **Production evidence:** 最近一轮 41/81 条详情被重新抓取，`csw` 30/30；结果仍为 0 new、0 updated。
- **Longitudinal evidence:** 多个稳定详情地址在保留日志中约有 675 次请求。
- **Impact:** 放大外站负载、提高被限流/封禁概率、增加网络依赖和抓取时长；明确违反“增量策略没有失效导致 detail 全量反复抓取”的验收要求。
- **Root cause:** 缺失的列表可选元数据与详情增强后的数据库值被严格比较。
- **Local state:** 最小代码修复和回归测试已完成，完整回归通过。
- **Production state:** 未部署、未重新 soak，因此仍未关闭。

## Required Closure

1. 将本报告中的增量修复移植到以 Gate 10 生产提交为基线的发布分支；不要直接用包含 Gate 12–14 的当前 `master` 替换 Gate 10 生产服务。
2. 部署后先验证连续稳定轮次：在无真实内容变化时，`csw` 应从 30 detail fetched / 0 skipped 转为接近 0 fetched / 30 skipped；其他来源只在列表字段确有变化时抓取详情。
3. 对修复后的确切制品重新累计至少 72 小时结构化 soak。期间继续满足本报告中的可用性、SQLite、scheduler、来源、备份、TLS、OOM、磁盘和日志标准。
4. 重新运行完整 regression，并把部署 commit、起止时间、样本数和事件复盘补入本报告。

修复部署后的状态应先记为 **PENDING**；只有新的 72 小时证据完成且没有新的 blocker，Gate 10 才能改为 **PASS**。

## Gate 10 Status

**FAIL — soak 时长和稳定性阈值已满足，但已浸泡制品存在确认的增量抓取 blocker；修复后的生产制品尚未部署并重新完成 ≥72 小时 soak。**
