# 吉林大学通知适配修复：B0＋B1 验证报告

日期：2026-10-13，Asia/Shanghai。状态：首批 B0＋B1 完成，停在本批交付点；B2–B7 尚未执行。

## 1. 结论与范围

已阻止本轮复现的导航候选和整页正文回退，补齐通用 HTTP 请求诊断，并使普通 HTML 预览、显式选择器预览及实际抓取使用同一正文检查。保留短文本和已有附件型通知支持。没有新增正式来源、修改数据库结构或改变 Cloud / Desktop 执行策略。

- 隔离实施前基线：**238 passed，1 skipped**。最终隔离全量测试：**269 passed，1 skipped**。新增 31 项测试，覆盖解析、两种预览、请求错误、附件型控制及用户数据保留。
- 原审计的 27 个疑似导航栏目，在同一批已保存网页上，候选总数由 **1,178 降为 0**。这些是首屏候选条目计数，包含跨栏目重复，不是删除的数据库记录，也不代表新增 27 个受支持来源。
- 原 11 个通过样本作正向对照，**11 个列表 URL 集合及对应详情解析结果全部保持一致**。这只是原样本兼容性，不代表所有历史通知通过。
- 实时复验既有 8 个栏目：**完全通过 0、部分通过 7、失败 1、需认证 0、未检测 0**。失败项是 CSE 的图片型通知无法被当前文本解析器表示。本批先拒绝空内容写入，图片支持留待 B2。
- 独立输出与缓存保护检查：**4 项通过，原审计 1,449 个文件 SHA-256 不变，0 次网络请求**。原审计报告及两份全校 CSV 保留原时间和结果。

因此，本批完成的是误抓防护与隔离验证基础，不能宣称全校适配完成或提高正式来源支持率。

## 2. B0：基线、隔离与证据

实施前 revision、相关工作区文件 SHA-256、隔离副本路径见 [baseline-manifest.json](jlu-fix-b0-b1/baseline-manifest.json)，最终版本见 [final-manifest.json](jlu-fix-b0-b1/final-manifest.json)。测试从 `backend/build/jlu-b1-*/backend` 的独立副本运行；没有复制正式 `.env`、SQLite 或用户资料目录。入口先断言导入来自隔离副本且有效数据库 URL 为 `sqlite://`；各测试自行创建的 SQLite 文件也只在隔离临时目录中。

这里使用 `sqlite://`：当前 Settings 会将 `sqlite:///:memory:` 当成相对路径重写，因此准备阶段的数据库路径保护曾主动拒绝该写法；本批没有顺带修改 Settings。

从原快照提取了七组既有非 OA 栏目的脱敏列表/详情控制，以及一组实际空栏目结构，见 [fixture manifest](../backend/tests/fixtures/jlu_b1/manifest.json)。OA 继续使用既有专用 fixtures；原审计没有成功取得 OA 快照，本次没有为其编造历史控制。校级、学工等高价值历史样本还纳入了完整快照重放；受阻且无快照的记录明确保留 `NO_SNAPSHOT`。就业来源准入仍待 B4。

[问题台账](jlu-fix-b0-b1/issue-ledger.json)保留全部 306 个原栏目/引用的 URL、原检查时间、优先级及证据指向，将问题分为已证实解析错误、访问阻塞、能力/评估边界、尚未逐条核验和无需新增适配引用。分类不会把旧标记自动升级为已确认缺陷。

审计工具新增：

- 独立 `--output-dir`，限制在 `docs/` 下，禁止覆盖原证据目录；CSV 同样写入新目录。
- `--input-dir` 只复制发现元数据，不复制 HTTP 缓存、兼容结果或旧失败。
- 可重复的 `--column-url` 选择复验栏目；同一运行内仍可断点恢复。
- 恢复前核对解析代码指纹；版本变化拒绝混用旧结果，要求新建运行目录。
- 解析失败也保存原 URL、检查时间、快照与 SHA-256。旧报告专用的复核/最终化阶段不开放给独立运行，避免旧结论模板污染新报告。

历史快照重放是另一入口，明确记录 `offline`、重放时间、原抓取时间和代码指纹，不产生实时检查时间伪证。纯通用解析重放没有导入数据库模块或联网。

## 3. B1：实际代码变更

相对实施前工作区，应用代码只改动三个文件，见 [preservation.json](jlu-fix-b0-b1/preservation.json)：

| 文件 | 改变与目的 |
| --- | --- |
| `backend/app/parsers/html.py` | 排除语义导航容器、分页容器、非法链接；VSB article 路径或有明确日期的其他静态列表行才进入自动候选；确认“共 0 条”的栏目不回退扫描导航。无受支持正文容器、导航正文、登录/验证/错误页、无文本无附件的详情被拒绝。图片型正文单独报未支持。 |
| `backend/app/sources/base.py` | 正式静态适配器区分真实空栏目和无法识别的列表；未知模板报告错误，不再静默当成功空抓。 |
| `backend/app/sources/generic.py` | 自动/显式选择器 HTML 共用质量检查；空栏目预览不签发成功 token。SafeFetcher 记录耗时、尝试次数、HTTP 状态、内容类型、响应大小和异常链，复用既有日志脱敏与 TLS 工厂。 |

无需改预览 API 或 runner：既有本地与 Cloud 预览捕获 `SourceError / ValueError` 并返回 422；runner 既有逐通知异常处理继续隔离失败。新增集成测试证实，坏详情不能覆盖旧正文、notice ID、来源关系、已读、收藏及其更新时间；同批另一条有效通知仍可持久化。

有效短通知不按字数拒绝。正文容器内的受支持附件，以及显式附件选择器指向正文容器外的合法附件，均有正向测试。没有扩展附件类型、抓取图片、生成替代正文或清理历史数据库内容。

SafeFetcher 复用实施前已有 `http_diagnostics.exception_summary` 与 `logging_config` 脱敏；本批没有重复替换其实现。空 `ReadTimeout`、EOF、HTTP 503、证书错误均能保留 cause，日志 query/fragment 中的测试秘密被移除。重试上限、Cloud 私网与连接地址校验、重定向检查、响应体限制和 TLS 验证保持原策略。

## 4. 历史快照对照

证据：[before](jlu-fix-b0-b1/replay-before.json)、[after](jlu-fix-b0-b1/replay-after.json)、[汇总](jlu-fix-b0-b1/replay-summary.json)。两个版本各核验了 **143 次快照 SHA-256**；含重复使用同一快照，不是 143 个独立站点。分组有交集：27 个导航疑似栏目、11 个正向样本、8 个既有栏目、30 个 P0/P1 高价值条目。

| 代表样本 | 修复前列表候选 | 修复后 | 解释 |
| --- | ---: | ---: | --- |
| [汽车学院招生信息](https://auto.jlu.edu.cn/zsxx.htm) | 66 | 0 | 实际“共 0 条”，之前回退扫描导航。 |
| [新能源学院本科就业](https://nasa.jlu.edu.cn/bksjy/jyxx.htm) | 70 | 0 | 不再把栏目/导航链接提升为通知。 |
| [CSE 旧路径本科教学](https://cse.jlu.edu.cn/bksjy/bkjxtz.htm) | 24 | 0 | 旧路径页面导航不能代替正式通知列表。 |
| [计算机学院教学通知](https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm) | 10 | 10 | 两条原详情保持兼容。 |
| [CSE 正式本科教学](https://cse.jlu.edu.cn/bkjxtz.htm) | 3 | 3 | 原通过样本保持兼容。 |

27 个疑似栏目对应历史详情中仍有四个可解析出受限容器的正文；本批没有把这四个详情单独宣称为导航误抓。它们已不能经这些不合格栏目自动进入候选。未知模板可以通过经验证的显式选择器继续适配；本批没有因此批量登记来源。

## 5. 实时既有来源回归

运行窗口：2026-10-13 **18:46:46–18:47:39**。新目录 [live-existing-20261013](jlu-fix-b0-b1/live-existing-20261013/run.json)，没有导入旧请求缓存。串行访问；全局间隔至少 1 秒、同源至少 1.2 秒，并尊重更长 robots crawl-delay；单次超时 12 秒，仅超时或 502/503/504 最多再试一次，401/403/429 不重试、不绕访问控制。

8 个首屏、16 个详情、6 个附件端点、7 个下一页，共 43 条 HTTP 响应记录（含 robots）。附件只作既有有限探测，不批量下载。机器汇总见 [summary.json](jlu-fix-b0-b1/live-existing-20261013/summary.json)，逐栏见 [兼容 CSV](jlu-fix-b0-b1/live-existing-20261013/jlu-compatibility-report.csv)，具体复现见 [results.json](jlu-fix-b0-b1/live-existing-20261013/results.json)及 [requests.json](jlu-fix-b0-b1/live-existing-20261013/requests.json)。

| 既有栏目 | 列表数 | 自动结论 | 本次发现及下一批 |
| --- | ---: | --- | --- |
| [CCST 教学通知](https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm) | 10 | 部分通过 | 正文正常；附件端点尚未验证为文件，分页未配置。B3/B5。 |
| [CSE 本科教学](https://cse.jlu.edu.cn/bkjxtz.htm) | 3 | 部分通过 | 两条详情正常；动态分页/历史范围未核验。B5。 |
| [CSE 学院通知](https://cse.jlu.edu.cn/xytz.htm) | 8 | 失败 | 首条为图片型通知，不能当文本空结果写入；第二条正常。B2。 |
| [软件教办通知](https://csw.jlu.edu.cn/index/jbtz.htm) | 15 | 部分通过 | 可见 jpg 附件未提取，端点/分页仍待核验。B3/B5。 |
| [软件学院通知](https://csw.jlu.edu.cn/index/xytz_.htm) | 15 | 部分通过 | 附件仅有限探测、分页未配置。B3/B5。 |
| [创新创业通知](https://cxcyjyxy.jlu.edu.cn/index/tzgg.htm) | 15 | 部分通过 | 附件端点和分页仍待核验。B3/B5。 |
| [教务通知](https://jwc.jlu.edu.cn/zxzx/tzgg.htm) | 15 | 部分通过 | 附件端点和分页仍待核验。B3/B5。 |
| [OA 校内通知](https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577) | 30 | 部分通过 | 公开列表和两条详情可访问；OA 附件 POST 未执行、历史分页未配置。另有三项审计工具误报/边界，见下。 |

### 人工复核与工具局限

人工复核独立保存于 [manual-review.json](jlu-fix-b0-b1/manual-review.json)，没有改写自动结果或旧证据：

1. [CSE 图片通知](https://cse.jlu.edu.cn/info/1003/1381.htm)的 `.v_news_content` 含一张 1080px 图片，没有可提取文本；不能称作原网页为空。实时复验时错误名是 `HTML_DETAIL_EMPTY`；随后最终代码细化为 `HTML_DETAIL_IMAGE_ONLY_UNSUPPORTED`，由最终快照重放和测试验证，没有重复联网或伪造新抓取时间。
2. [OA 通知 71065225](https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?channelId=179577&id=71065225)发布元信息为 **2026-10-10 15:02**，正文会议时间为 **2026-10-14**。OA 解析日期正确；自动审计的 `DATE_MISMATCH` 来自宽泛参考正则误取会议日期。
3. OA `LIST_CANDIDATE_RECALL_GAP` 的五个参考链接是页脚平台说明、纠错、反馈等入口，不是通知行，不能据此认定漏抓。
4. OA `PAGINATION_PARSE_EMPTY` 来自审计工具对下一页使用通用静态解析器。对同一已保存下一页用 OA 专用纯解析函数重放得到 **30 条、30 个新 URL**；不构成 OA 解析失败。该补充入口导入了数据库模块，但已固定 `sqlite://`，无正式数据库或网络访问。生产历史分页仍未启用。

最终通用解析文件及显式附件选择器有两项后续兼容补充；实时运行指纹与最终测试指纹分别保留。补充通过离线验证，没有把实时结果的代码时间改成最终代码时间。

新目录中机构与站点发现元数据来自原审计；它们保留旧发现时间，不能把新 CSV 中的 164 个主机当成本次重新访问了 164 个站点。

## 6. 数据与执行策略保护

- `backend/config/sources.yaml` SHA-256 仍为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。
- 对照 B0 指纹，应用目录内仅上述三个文件有本批差异。实施前已有 runner、OA、TLS、日志、前端等未提交改动均保留。
- 不迁移、清空或重写正式 SQLite；不清理既有通知，不重置 ID、收藏、已读、来源或成功 baseline。
- 不更改 Cloud policy、source identity、ownership、URL/附件 DTO、Cloud 私网限制或 Desktop fallback；Cloud 预览的同规则拒绝由离线测试证明，**实际 Cloud Linux 生产运行未验收**。
- 本次没有改系统代理/路由、安装客户端、发布 Release、提交或推送 GitHub，也没有改 UI。

## 7. 后续优先级与停止点

下一批 B2：P0 先处理 CSE 图片型正文、校级标题容器与现有来源内容异常；P1 再处理学工拆分日期、其他标题/日期和编码问题。保持可核验的原图/原通知链接，不能用导航或生成文字补正文。

B3 继续软件教办图片附件、下载端点分类及 OA 专用附件；B4 才做学工、科研、就业等新来源准入；B5 再验证分页、增量/去重及真实 Cloud。P2 学院与 P3 其他机构按 B6/B7 分批扩展。旧审计的其余 285 个适配对象没有在本次实时重验，305 条官网未知机构及受阻站点仍保留原状态。

本批没有改变原全校审计通过率。已按计划停在 B0＋B1，不自动进入后续批次。

## 8. 复现入口

仓库根目录使用既有 venv，无需安装依赖：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py final
.\backend\.venv\Scripts\python.exe backend/scripts/replay_jlu_b1.py --output docs/jlu-fix-b0-b1/replay-after.json
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_audit_isolation.py
```

首次实时复验用新目录，后续同目录仅在代码指纹一致时恢复。每个待复验 URL 重复提供 `--column-url`：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate `
  --output-dir docs/jlu-fix-b0-b1/next-live-run `
  --input-dir docs/jlu-audit-evidence `
  --column-url https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm
```

原运行留存的 [baseline tests](jlu-fix-b0-b1/baseline-tests.log)、[final tests](jlu-fix-b0-b1/final-tests.log)、[工具隔离验证](jlu-fix-b0-b1/tool-isolation-verification.json)及代码指纹是本报告数字依据。重新运行会产生新的隔离代码副本；保留每次证据时间，不以缓存成功代替新版本验收。
