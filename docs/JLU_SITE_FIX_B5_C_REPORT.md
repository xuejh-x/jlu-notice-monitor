# 吉林大学通知适配修复 B5-C：有界分页、增量与去重

日期：2026-10-14（Asia/Shanghai）。状态：**B5-C 完成，停在本子批交付点**。修复多请求一页、多页结果被截回单页、分页循环/越界、不同序号通知误合并及 VSB 内嵌 PDF 被判空。正式来源配置未变；六个招生栏目继续禁用；没有正式数据库迁移、历史补抓、发布或客户端更新。

## 1. 真实结果与范围

本批对象为既有 8 个通知栏目及 B4 的 9 个内容样本通过栏目，按完整 URL 去重后为 **17 个不同栏目**。不含日期语义未确认的 6 个招生栏目，也不把单页蓝桥杯监控算作学校通知栏目。

| 项目 | 结果 |
| --- | ---: |
| 已尝试 / 未尝试 / 无需适配 | 17 / 0 / 0 |
| 完全通过 / 部分通过 / 失败（访问受阻）/ 需认证 | 0 / 16 / 1 / 0 |
| 实际检查列表页 | 45 |
| 列表候选出现次数（各栏目内已去重） | 575 |
| 详情抽样 | 48，结构核验通过 48 |
| 独立内存数据库连续两轮来源重放 | 16；第二轮新增、更新均为 0 |
| 原同 URL 组 / 同标题日期候选重现 | 113 / 48 |
| 正式来源变更 / 正式合并 / 正式准入 | 0 / 0 / 0 |

575 是各栏目数量之和，未声明为全校唯一通知数，也没有将全部 575 条写入测试库。数据库重放仅使用核验过的 **48 篇详情**，与服务器的实时再次抓取分开。所有来源最多三页、总候选最多 90 条；14 个栏目因页数上限停止，网安学院两个栏目分别在两页及一页达到可见末页。未核验全历史、实际 Cloud、实际 Desktop fallback 或附件文件下载，故没有任何栏目记为“完全通过”。

证据：[最终代码重放汇总](jlu-fix-b5-c/replay-final-20261014/summary.json)、[逐栏目准入矩阵](jlu-fix-b5-c/admission-matrix.json)、[完整结果](jlu-fix-b5-c/replay-final-20261014/results.json)。

## 2. 逐栏目结果

| 对象 | 页数 | 栏目内去重候选 | 详情 | 本批结论 |
| --- | ---: | ---: | ---: | --- |
| [网安学院通知](https://cse.jlu.edu.cn/xytz.htm) | 2 | 14 | 3 | 有界样本通过；其中一篇仅验证 PDF 引用 |
| [网安本科教学通知](https://cse.jlu.edu.cn/bkjxtz.htm) | 1 | 3 | 3 | 明确序号误合并修复后通过 |
| [计算机学院教学通知](https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm) | 3 | 30 | 3 | 有界样本通过 |
| [软件学院通知](https://csw.jlu.edu.cn/index/xytz_.htm) | 3 | 45 | 3 | 有界样本通过 |
| [软件教办通知](https://csw.jlu.edu.cn/index/jbtz.htm) | 3 | 45 | 3 | 有界样本通过 |
| [本科生院通知](https://jwc.jlu.edu.cn/zxzx/tzgg.htm) | 3 | 45 | 3 | 有界样本通过 |
| [创新创业学院通知](https://cxcyjyxy.jlu.edu.cn/index/tzgg.htm) | 3 | 45 | 3 | 有界样本通过 |
| [OA 校内通知](https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577) | 0 | 未取得 | 0 | robots 获取时 TLS EOF；未继续正文 |
| [学工通知](https://xsc.jlu.edu.cn/index/tzgg.htm) | 3 | 30 | 3 | 有界样本通过 |
| [就业通知](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg) | 3 | 36 | 3 | 已观察公开 GET 表单分页样本通过 |
| [就业公示](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs) | 3 | 36 | 3 | 已观察公开 GET 表单分页样本通过 |
| [证明书公示](https://jwc.jlu.edu.cn/fwzn/xy1/zmsgs.htm) | 3 | 45 | 3 | 有界样本通过 |
| [科研通知](https://kjc.jlu.edu.cn/tzgg.htm) | 3 | 51 | 3 | 有界样本通过 |
| [社科通知](https://hssra.jlu.edu.cn/tzgg1.htm) | 3 | 60 | 3 | 有界样本通过 |
| [研究生院通知](https://yjsy.jlu.edu.cn/tzgg.htm) | 3 | 45 | 3 | 有界样本通过 |
| [团委通知](https://youth.jlu.edu.cn/index/tzgg.htm) | 3 | 15 | 3 | 有界样本通过 |
| [国际教育公告](http://cie.jlu.edu.cn/ggtz.htm) | 3 | 30 | 3 | 有界样本通过 |

每栏详情选择首屏前两篇及第二页新增的一篇；只有一页时补到三篇。标题、日期、正文/图片或附件型正文、可见附件引用逐篇对照 DOM，不凭 HTTP 200 或非空结果通过。原文 URL、捕获时间、HTTP/编码信息、快照 SHA、列表独立链接集合、遗漏/额外链接和停止原因均在准入矩阵及完整结果中。17 个预览配置副本均不启用；既有正式来源的启用状态并未被改成禁用。

## 3. 修复及复现证据

### 分页

旧 Generic 循环在最后允许页解析后仍请求下一页，最终又用单页条数截断所有多页结果。StaticHTMLSource 原先只实现首屏。本批新增共用 `ListPagination`，Generic 使用现有 `next_page_selector / pagination_limit`，Static 仅在显式配置选择器时启用；缺省首屏行为保持。

上限为 `min(配置页数, 全局页数, 3)`，总候选上限为单节条数 × 实际允许页数，达到任一上限即停止请求。本轮每节条数 30，因此每栏最多 90。保留所有已接受页的结果，按既有 canonical URL 规则去重；记录实际页、条数、截断数与停止原因。重复页、已访问 URL、禁用链接、非 HTTP 链接、跨源及跨栏目链接不继续；后续页重定向到栏目范围外时拒绝结果。请求仍使用既有 SafeFetcher 的逐跳 URL、TLS、Cloud DNS/peer 校验，不扩大私网或重定向权限。

栏目范围限定为同源、原列表路径或对应 VSB 历史目录，并保留非分页查询条件。新旧 VSB 的 `.p_next a` 与 `a.Next` 都以实际页面为依据。就业网首页明确给出 `searchForm` 的 GET action、`cid/pageNo/pageSize/keyword` 及只改页码/条数后提交的脚本；仅严格匹配该公开结构才复现 GET，不执行 JavaScript、不发 POST、不猜 API。不识别结构变化、表达式、外域 action、敏感/未知字段。

首轮验证工具仅匹配新式 VSB，曾漏检软件、创新创业、国际教育四个栏目的下一页。现已按已捕获旧式标记补检，并加入“页面观察到下一页但选择器未命中时不能验收”的检查。旧运行保留，最终表格只采用修正后的验证。[验证过程说明](jlu-fix-b5-c/validation-refinement-notes.json)区分此工具问题和应用缺陷。

### 明确序号冲突误合并

真实例子为 [暑期实训（一）](https://cse.jlu.edu.cn/info/1006/1369.htm)（2024-07-01）和 [暑期实训（二）](https://cse.jlu.edu.cn/info/1006/1377.htm)（2024-07-10）。不同文章 URL、序号和方案内容，在原同来源标题相似度规则下仍被合并；同栏三篇样本只剩两条 notice、三条关系。修复后得到三条 notice、三条关系，第二轮全部跳过详情，ID、正文和用户状态保持。

本批只为标题匹配增加明确括号序号、期/批/届/次/轮/场冲突保护；canonical URL、public_id、已有来源关系仍优先，不改 0.92 相似阈值，不改变默认跨来源去重开关，也不拆分或回写正式库既有合并项。其他同名、近似标题的不同通知仍需证据审查，未承诺所有误合并都已消除。

证据：[修复前实际重放](jlu-fix-b5-c/followup-20261014/results.json)、[序号回归失败日志](jlu-fix-b5-c/identity-regression-before-tests.log)、最终矩阵中的 `existing-cse-1`。

### VSB PDF 型正文

[2024 年信息安全竞赛参赛须知](https://cse.jlu.edu.cn/info/1003/1358.htm)，抓取于 `2026-10-14T23:16:24+08:00`。文章容器只有 `showVsbpdfIframe` 的静态 PDF 引用，旧流程先去除 script，再提取附件，因此误判空正文。快照 SHA-256：`7419c35c63d1070369620233cd005508c982522afa3c8113472a9a6c6855d910`。

现于清除脚本前提取文章容器内已知调用的同源 PDF 字面量，保留为原 `filename / url / type` 附件。外域、带凭据、危险协议及动态表达式不被提升为可用正文；不运行脚本、不请求 PDF 或其中图片。该篇标记 `EMBEDDED_PDF_ATTACHMENT_REFERENCE_ONLY`：只通过标题、日期与 PDF 引用核对，**没有验证 PDF 内文字、OCR 或文件完整性**。

证据：[PDF 回归失败日志](jlu-fix-b5-c/pdf-regression-before-tests.log)、最终 `existing-cse-0` 详情记录及[应用改动](jlu-fix-b5-c/application-changes.diff)。

## 4. 增量、身份与用户状态

每个可访问栏目用其三篇已解析样本进入独立内存库：首轮建立已读 baseline，保存 ID、canonical URL、public_id、来源关系、内容 hash、版本和已读/收藏状态；次轮调用真实 crawler 的来源执行方法，验证没有重复新增或更新、用户状态及关系保持。测试库为覆盖旧样本单独使用 3,650 天保留期，正式默认 365 天没有改变；旧置顶不会阻止后续新通知的默认保留期行为另有独立回归控制。

新增用例还验证标题恢复、日期纠正、图片链接与附件补齐、失败单条后继续处理正常条目、失败恢复和下一轮跳过；失败条目不改变其既有正文/关系 hash、baseline 或收藏/已读状态。相同 URL、tracking 别名、同标题不同来源、相同 public_id 的控制均保持既有身份策略。

**既有增量边界仍保留：**列表标题、日期、发布者不变时，runner 会跳过详情。因此只有正文/附件变化、列表完全不变的历史条目不会自动重新核验；本批没有偷偷启用全量详情刷新。若需修复已经缺正文/附件的历史数据，后续须按明确来源/URL 和有界数量，先 dry-run、备份与差异审查，再决定专门回写方案，不能直接批量迁移正式库。

## 5. 原重复候选分类

从原审计实际导出使用的、含人工复核的 `results.json` 重建聚类，逐项与原 `duplicates.json` 比较，原 113/48 统计完全复现；较早的单栏目观察文件未覆盖人工复核结果，不能替代该输入。

| 集合 | 分类 | 数量 | 处置 |
| --- | --- | ---: | --- |
| 同 URL 组 | 同一 URL 在多个栏目被引用 | 113 | 保留 canonical 身份及来源关系，不据此认定库内已有重复 |
| 同标题/日期候选 | 跨站转载候选 | 5 | 保留各来源身份，未经审查不全局合并 |
| 同标题/日期候选 | 同站不同 URL 候选 | 29 | 需核对文章、对象和来源归属 |
| 同标题/日期候选 | HTTP/HTTPS 协议别名候选 | 14 | 未凭去掉协议就合并，不推断已验证跳转 |

48 组中，只有 1 组保存了全部候选的可对照正文且文本相同，作为转载文本证据；另外 47 组正文证据不足，保持待审。文本相同也不自动授权跨来源合并。没有据这 161 组候选清理正式库，也没有把它们宣传成 161 个真实数据库重复故障。网安序号问题是本批额外实测发现，与原同规范标题候选口径不同。

证据：[完整分类与输入 SHA](jlu-fix-b5-c/duplicate-classification.json)。

## 6. 测试、访问规则与保护

| 检查 | 真实结果 |
| --- | --- |
| 修改前隔离基线 | 415 passed，1 skipped |
| 最初分页/边界复现 | 20 failed，266 passed |
| 表单规则加入前 | 1 failed，299 passed |
| 序号去重修复前 | 3 failed，300 passed |
| PDF 提取修复前（含序号缺陷） | 5 failed，304 passed |
| 最终定向回归 | 310 passed |
| 最终完整后端回归 | 465 passed，1 skipped |
| 最终代码离线重放 | 17 栏；0 新 HTTP；16 栏有界样本通过、OA 受阻 |
| 原始审计文件 / 既有批次报告 | 1,449 个 / 6 份 SHA 保持不变 |

新增 50 个回归用例。日志：[基线](jlu-fix-b5-c/baseline-tests.log)、[最初缺陷](jlu-fix-b5-c/regression-before-tests.log)、[定向](jlu-fix-b5-c/targeted-tests.log)、[完整回归](jlu-fix-b5-c/final-tests.log)。最终应用、测试和配置与完整测试副本 SHA 一致，后续离线制表工具的最终 SHA 另留验收记录。

网络使用单进程串行，共享 HTML 限速及 robots 状态，全局至少 1 秒、同源至少 1.2 秒，保留更长 Crawl-delay 与瞬时故障最多两次尝试上限。实际请求分阶段共 110 次，收到 109 个 HTTP 响应；其中一个 OA robots 请求为 TLS EOF，没有 HTTP 响应，未继续 OA 正文或反复复检。实时快照主要捕获于 23:08–23:23，后续只读离线重放保留原捕获时间。混合续检的旧/新请求及最初结果序列化异常均留档，不冒充同一时刻的连续全站抓取。

HTML 缓存按确切请求 URL 保存，代码/输入指纹变化使用新运行目录。每栏结果落盘支持断点续检。应用导入前指定内存 URL、独立资料目录并关闭调度/启动同步；应用全局引擎安装拒绝连接守卫，实际应用数据库连接为 0。数据库验证另建测试内存引擎，不连接正式 SQLite。正式 `sources.yaml` SHA 保持 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`，原 B4 候选不改，Cloud/Desktop 策略、ownership、API、数据库 schema、前端与 UI 不变。

证据：[保护检查](jlu-fix-b5-c/preservation.json)、[验收记录](jlu-fix-b5-c/acceptance.json)、[现场补检汇总](jlu-fix-b5-c/final-live-20261014/summary.json)、[首屏发现依据](jlu-fix-b5-c/discovery-20261014/results.json)。

离线复验示例（在 `backend/`，使用新目录，不覆盖既有证据）：

```powershell
.\.venv\Scripts\python.exe scripts/validate_jlu_b5_c.py --output-dir docs/jlu-fix-b5-c/replay-review --input-dir docs/jlu-fix-b5-c/final-live-20261014 --offline
.\.venv\Scripts\python.exe scripts/classify_jlu_b5_c_duplicates.py
.\.venv\Scripts\python.exe scripts/finalize_jlu_b5_c.py
```

## 7. 下一步及保留问题

下一实施范围为 **B5-D：附件能力分类与真实 Cloud / Desktop 分环境准入**。优先既有来源，再处理已通过本批有界样本的候选；验证码/robots 限制沿用既有证据，缺少实际 Cloud 环境时保留未验证。OA 的网络/TLS 阻塞、招生日期语义、47 组正文证据不足候选、未翻过第三页的历史以及详情独立变化的增量边界均继续保留，不能因 B5-C 完成就宣称全校适配完成。

本批改动仍在工作区，尚未推送 GitHub、发布新 Release 或更新本地客户端；已发布/安装版本仍是之前的 v0.7.4。
