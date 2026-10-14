# 吉林大学通知适配修复 B4：高价值公开栏目

日期：2026-10-14（Asia/Shanghai）。B4 候选配置、内容适配及有界验证完成，停在本批交付点。**19 个候选全部禁用，正式准入 0 个。** 逐栏结论为 15 个部分通过、1 个需认证/权限受限、3 个访问失败，完全通过 0 个。分页、增量去重和真实 Cloud 环境留给 B5。

## 1. 范围与结果口径

候选来自原审计已确认的官方栏目，保留机构、发现依据、URL 和范围。19 个不同栏目 URL 分布在 11 个主机，均已尝试检查；本批未检测 0 个、无需适配 0 个。全校原始站点和栏目总数沿用 [专项审计](JLU_SITE_AUDIT.md)，本报告不把本批 19 个对象当作全校覆盖范围。

[候选 JSON](jlu-fix-b4/source-candidates.json)、[候选 YAML](jlu-fix-b4/source-candidates.yaml)位于独立文档目录。YAML 顶层为 `candidate_sources_only`，不是正式 `sources`。全部 `enabled: false`，不执行来源注册、订阅、调度或持久化。`validation_scope: local` 和 `cloud_preferred` 只是候选策略值，不代表真实 Cloud 验收。

| 验证范围 | 数量 | 结论 |
| --- | ---: | --- |
| 栏目入口 | 19 | 15 部分通过、1 权限受限、3 访问受阻 |
| 首屏解析通知 URL | 176 | 本批首屏之间未发现完全相同 URL；不是历史去重验收 |
| 详情尝试 | 47 | 29 条标题、日期、正文、附件提取逐项核对通过 |
| 招生详情 | 18 | 标题、正文、附件提取结构通过，发布日期语义未确认 |
| 附件有限探测 | 14 | 5 文件前缀、8 验证码页、1 robots 阻止 |
| 完整附件下载 | 0 | 未验证完整性、内部格式或下载成功 |
| 正式来源变更 | 0 | 19 个候选继续禁用 |

其中 9 个栏目为 `CONTENT_SAMPLE_PASSED`，另 6 个招生栏目为 `CONTENT_PASSED_DATE_SEMANTICS_REVIEW_REQUIRED`。前者也只完成有限内容样本验证，不能标为来源完全支持。结果及 URL、时间、原因见 [逐栏 CSV](jlu-fix-b4/review-final-20261014/compatibility-report.csv)、[完整 JSON](jlu-fix-b4/review-final-20261014/results.json)与 [准入决策](jlu-fix-b4/admission-decisions.json)。

## 2. 本批代码变化

相对 B4 开始时的隔离基线，应用代码只改 `backend/app/parsers/html.py` 和 `backend/app/sources/generic.py`，差异见 [application-changes.diff](jlu-fix-b4/application-changes.diff)。没有新增专用就业 adapter、修改正式来源或放宽安全策略。

- 就业网复用现有高级选择器，限定 `.m-list-line_content` 内的标题与 `/portal/jyzp/article/details?id=` 链接，保留 `cid` 栏目身份和 `id` 通知身份。标题优先取原 `title` 属性，避免可见置顶标记和截断文字。日期从独立创建时间节点提取，不读取摘要中的活动日期。
- 就业详情适配 `.m-detail-container__title`、`.m-detail-container__info` 和 `.m-detail-content__container`。仅此元信息容器接受“创建时间”，没有全局把任意创建时间当发布日期。
- 就业附件识别明确的 `.m-detail-container__file`，保留 opaque `downloadFile?id=` 入口，移除文件名末尾的展示大小 ` - (31.5 MB)`。仍使用 `filename / url / type` DTO，不猜物理文件地址。
- 科研处、人文社科处、团委使用实际快照中的标题和元信息容器。标题候选不能来自已选正文容器内部，防止正文居中小标题覆盖文章标题。
- 验证器区分原文“更新时间”和发布日期；图片正文增加原始图片 URL 后仍按原文文字独立核对。HTTP 200 的无权限提示单独分类。

就业可复用选择器：

```yaml
item_selector: .m-list-line_content
title_selector: h3 a[title]
url_selector: h3 a[href*='/portal/jyzp/article/details?id=']
time_selector: span:last-child
pagination_limit: 1
```

VSB 可复用正文为 `.v_news_content`；科研处标题 `.detail_head1`、日期 `.content-bt-xia`；人文社科处为文章表单内 `h2.tit`、`.conttime`；团委为文章表单内居中 `h2`、`.title3 > p.ac`。这些规则只由已观察模板支撑，不按子域名批量猜测套用。

## 3. 逐栏验收

下表“详情核对”只计日期也已核对的严格样本。每行证据含完整栏目 URL、原抓取时间、复核时间、详情 URL、原文容器、内容摘要及 SHA-256。所有行均未验收历史分页或真实 Cloud。

| 栏目 | 首屏条数 | 详情核对 | 结论及剩余问题 | 证据 |
| --- | ---: | ---: | --- | --- |
| 学工通知 | 10 | 3/3 | 部分通过；附件验证码，其余附件未检 | [xsc](jlu-fix-b4/review-final-20261014/results/xsc.json) |
| 就业通知 | 12 | 3/3 | 部分通过；文件前缀有效，其余附件未检 | [employment-notices](jlu-fix-b4/review-final-20261014/results/employment-notices.json) |
| 就业公示 | 12 | 3/3 | 部分通过；文件前缀有效，其余附件未检 | [employment-publicity](jlu-fix-b4/review-final-20261014/results/employment-publicity.json) |
| 教学公示 1402 | — | 0 | 需认证/权限受限；HTTP 200 明确提示无访问权限 | [jwc-teaching-publicity](jlu-fix-b4/review-final-20261014/results/jwc-teaching-publicity.json) |
| 教务证明公示 | 15 | 5/5 | 部分通过；最多五条未见附件，不能推断全栏目无附件 | [jwc-certificates](jlu-fix-b4/review-final-20261014/results/jwc-certificates.json) |
| 招生通知 | 10 | 0/3 | 部分通过；仅更新时间，附件验证码 | [yzb-notices](jlu-fix-b4/review-final-20261014/results/yzb-notices.json) |
| 招生录取公示 | 10 | 0/3 | 部分通过；仅更新时间，附件验证码 | [yzb-publicity](jlu-fix-b4/review-final-20261014/results/yzb-publicity.json) |
| 博士招生公告 | 10 | 0/3 | 部分通过；仅更新时间，文件前缀有效 | [yzb-doctor-notices](jlu-fix-b4/review-final-20261014/results/yzb-doctor-notices.json) |
| 博士录取公示 | 10 | 0/3 | 部分通过；仅更新时间，附件验证码 | [yzb-doctor-publicity](jlu-fix-b4/review-final-20261014/results/yzb-doctor-publicity.json) |
| 硕士招生公告 | 10 | 0/3 | 部分通过；仅更新时间，附件被 robots 阻止 | [yzb-master-notices](jlu-fix-b4/review-final-20261014/results/yzb-master-notices.json) |
| 硕士录取公示 | 10 | 0/3 | 部分通过；仅更新时间，文件前缀有效 | [yzb-master-publicity](jlu-fix-b4/review-final-20261014/results/yzb-master-publicity.json) |
| 科研处通知 | 17 | 3/3 | 部分通过；附件验证码，其余附件未检 | [kjc](jlu-fix-b4/review-final-20261014/results/kjc.json) |
| 人文社科处通知 | 20 | 3/3 | 部分通过；附件验证码，其余附件未检 | [hssra](jlu-fix-b4/review-final-20261014/results/hssra.json) |
| 研究生院通知 | 15 | 3/3 | 部分通过；附件验证码，其余附件未检 | [graduate-school](jlu-fix-b4/review-final-20261014/results/graduate-school.json) |
| 团委通知 | 5 | 3/3 | 部分通过；附件验证码，其余附件未检 | [youth](jlu-fix-b4/review-final-20261014/results/youth.json) |
| 国际教育通知 | 10 | 3/3 | 部分通过；文件前缀有效，其余附件未检 | [international](jlu-fix-b4/review-final-20261014/results/international.json) |
| 研究生答辩入口 | — | 0 | 失败；robots 获取连接超时，保守停止 | [defense-conditional](jlu-fix-b4/review-final-20261014/results/defense-conditional.json) |
| 继续教育通知 | — | 0 | 失败；HTTP 308 重定向超出既有上限 | [continuing-conditional](jlu-fix-b4/review-final-20261014/results/continuing-conditional.json) |
| 继续教育学历通知 | — | 0 | 失败；HTTP 308 重定向超出既有上限 | [continuing-academic-conditional](jlu-fix-b4/review-final-20261014/results/continuing-academic-conditional.json) |

招生 18 条详情的 `.arc-info` 可见“更新时间”，没有独立发布元信息。保留既有列表日期回退行为，但不为该日期签发发布日期核对通过结论。需要官方语义依据或明确日期来源后再准入，不能直接把“更新”改名成“发布”。

教学公示明确显示“您没有访问当前栏目的权限”，不是空栏目或通用选择器失效。“需认证”是权限受限统计桶，**没有证实登录即可解决**。答辩入口未取得正文；继续教育仅证实重定向上限触发，不推测最终目标、栏目不存在或服务器永久故障。

## 4. 证据时间、有限访问与初判修正

就业模板发现先串行检查两个列表及各三条详情，原始证据见 [employment inspection](jlu-fix-b4/employment-discovery-20261014/inspection.json)。主验证运行列表检查时间为 **16:33:54–16:36:26**，运行结束 16:36:30，见 [实时运行](jlu-fix-b4/live-20261014/results.json)、[请求缓存](jlu-fix-b4/live-20261014/requests.json)及 [当时代码指纹](jlu-fix-b4/live-20261014/code-manifest.json)。

主运行单进程串行，共用 HTML/附件限速状态，审计入口全局至少 1 秒、同源至少 1.2 秒，遵守更长 Crawl-delay。瞬时超时/502/503/504 最多两次尝试，认证、验证码、403/429、robots 拒绝不重复试探。保留原 TLS、SSRF 和跳转限制。每栏目首屏，默认三条详情；未见附件时最多扩至五条；若存在附件，仅探测一个入口，最多保留 4 KiB。没有暴力扫描、提交验证码、登录或批量下载。

首轮原始分类为 3 部分通过、16 失败，完整保留。随后核对原始 DOM，补齐实际标题/日期容器，并发现验证器未计入正文图片 URL，且把更新时间与发布日期混为一类检查。最终使用**相同 SHA-256 的已保存 HTML/附件前缀离线复核**，不是再次联网。复核时间 **16:47:26–16:47:37**，原 `captured_at` 和新 `validated_at` 分开记录。

最终 [复核模式](jlu-fix-b4/review-final-20261014/review-mode.json)、[代码及输入指纹](jlu-fix-b4/review-final-20261014/code-manifest.json)绑定原请求缓存和原代码清单。快照逐份核验 SHA 后复制到独立复核目录，改变规则/模式不能直接复用旧结果断点。目录 `review-20261014` 是中间复核，**最终结论以 `review-final-20261014` 为准**。本批没有把修正后的离线结论冒充最新 HTTP 结果。

附件 8 个验证码、1 个 robots 限制均保留原合法入口；5 个文件前缀只说明有限字节符合文件或 ZIP/Office 容器签名。就业通知中 31.5 MB 展示大小的文件也只读前缀，不代表完整下载。未探测的同页其他附件继续标为未检查。

[首屏 URL 对照](jlu-fix-b4/review-final-20261014/overlaps.json)为空，表示这 19 个候选的当前 176 个首屏 URL 未出现完全相同链接。没有检查全历史、正文相似度、协议别名或正式数据库重复，不推导“没有重复通知”。就业未发现通用下一页链接也不等于无分页，留给 B5 确认实际机制。

## 5. 回归与数据保护

| 检查 | 实际结果 |
| --- | --- |
| B4 实施前完整后端基线 | 350 passed、1 skipped，45.52 秒 |
| B4 定向回归 | 197 passed，21.95 秒 |
| B4 最终完整后端回归 | 365 passed、1 skipped，45.25 秒 |
| 原审计快照重放 | 68 个栏目/引用中 67 个全部字段一致，1 个校外参考样本标题纠正；前后各核验 145 次 SHA |
| 旧审计证据保留 | 1,449 个受保护文件及前三批报告未变 |
| 正式来源文件 | SHA-256 未变；未新增/启用来源 |

测试日志：[baseline](jlu-fix-b4/baseline-tests.log)、[targeted](jlu-fix-b4/targeted-tests.log)、[final](jlu-fix-b4/final-tests.log)。使用独立源代码副本，排除正式 `.env`、资料目录和 SQLite，入口断言 `sqlite://`。单项跳过沿用既有外部 PostgreSQL 集成环境未配置，未把跳过记成通过。测试清单及代码哈希见 [最终 manifest](jlu-fix-b4/final-manifest.json)。

[脱敏就业 fixtures](../backend/tests/fixtures/jlu_b4/manifest.json)、[VSB fixtures](../backend/tests/fixtures/jlu_b4/vsb-manifest.json)保留真实容器、URL、标题、日期和附件结构，正文改为离线控制文字。新增 15 项测试覆盖两个就业列表、实际 Generic 抓取入口、通知身份、附件大小后缀、元信息日期、正文小标题隔离、VSB 元信息、更新时间不误验和权限页面分类。

[历史 before](jlu-fix-b4/replay-before.json)、[after](jlu-fix-b4/replay-after.json)及 [对照摘要](jlu-fix-b4/replay-summary.json)覆盖 68 个栏目/引用。全部列表集合、详情日期/正文/附件及接受状态一致，67 个记录全部字段一致。唯一变化是原审计标为无需适配的研招网校外参考链接：浙江理工大学 3395 的标题由正文小标题“一、招生类型 及学制”回到原列表标题“浙江理工大学2027年硕士研究生招生简章”，由本批正文标题隔离规则产生，未新增该校来源。8 个既有栏目、11 个原通过样本、27 个导航疑似栏目保持兼容。未进行本批 OA 新实时访问；B3 的网络受阻事实仍保留。

[保留校验](jlu-fix-b4/preservation.json)、[CSV 对照](jlu-fix-b4/csv-check.json)及 [最终验收](jlu-fix-b4/acceptance.json)记录证据哈希、候选禁用状态与链接校验。正式来源 SHA-256 为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。本批没有改 crawler、数据库 schema、Cloud/Desktop 策略、source identity/ownership、DTO 或 UI，也未写正式 SQLite、提交 GitHub、发布 Release、安装客户端。既有工作区改动保留。

## 6. 下一批及剩余优先级

1. **P0：** B5 先复验既有来源、OA 网络与独立运行环境，保持成功 baseline、ID、已读与收藏；出现回归先停止扩展。
2. **P1：** 先为本批 9 个内容样本通过的栏目补有界分页、重复刷新和实际 Cloud/本地执行验收，再逐条给准入结论。6 个招生栏目先确认日期语义。权限受限教学公示、答辩超时和继续教育跳转分别保留访问阻塞，不通过放宽安全检查解决。
3. **P2/P3：** 学院、研究机构和附属单位继续按原计划 B6/B7 分模板验证，本批未新增这些范围。全校官网未知机构、就业招聘/实习/职位接口、其他学工子栏目、中英文全部内容、历史附件及全部分页没有覆盖，不能从本批有限样本外推。

B4 完成后停止，下一步建议 B5，不自动正式启用任何候选。

## 7. 复现入口

在仓库根目录运行隔离回归或离线重放：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py final --batch b4
.\backend\.venv\Scripts\python.exe backend/scripts/replay_jlu_b1.py --batch b4 --output docs/jlu-fix-b4/replay-after.json
```

离线复核需用新目录；不向旧目录写不同版本结论：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/validate_jlu_b4.py --review-input-dir docs/jlu-fix-b4/live-20261014 --output-dir docs/jlu-fix-b4/next-offline-review
```

如需新的实时证据，串行运行并指定全新目录；不把实时命令与另一个同源网络任务同时执行：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/validate_jlu_b4.py --output-dir docs/jlu-fix-b4/next-live-run
```
