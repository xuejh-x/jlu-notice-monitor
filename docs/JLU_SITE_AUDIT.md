# 吉林大学全校网站通知适配验证专项

审计日期：2026-10-13（Asia/Shanghai）。报告生成：2026-10-13T15:02:15+08:00。

本轮完成官方目录清单建立和公开栏目有限抽样验证。结果不能作为“全校网站已支持”的声明，也不能替代 Cloud 生产运行或历史全量验收。没有修改正式 sources.yaml、执行策略、数据库模型或解析器，没有启动正式 crawler，没有提交 GitHub、发布 Release 或安装客户端。

## 1. 数量与统计口径

| 指标 | 数量 |
| --- | ---: |
| 官方目录、官网导航及补充证据对应的机构记录（含别名/多职能） | 510 |
| 去重机构名称 | 491 |
| 未提供/未确认独立官网的机构记录 | 305 |
| 规范化官网入口 URL | 180 |
| 官网主机名去重 | 164 |
| 已完成入口发现检查 | 180 |
| 有响应入口的最终 URL 去重 | 164 |
| 有响应入口的最终主机名去重 | 149 |
| 规范化去重后的候选栏目/引用入口 | 306 |
| 已检测的适配对象 | 293 |
| 未检测的适配对象 | 0 |
| 无需适配（范围外引用或单篇文章；不是已支持） | 13 |
| 完全通过（仅本轮样本） | 11 |
| 部分通过 | 234 |
| 失败/访问检查受阻 | 48 |
| 需认证 | 0 |
| 最终清单保留的详情样本记录（允许缓存复用） | 297 |
| 最终清单保留的附件端点检查记录 | 122 |
| 最终清单保留的下一页检查记录 | 189 |
| 跨栏目同 URL 组 | 113 |
| 不同 URL 同规范标题/日期候选组 | 48 |

首轮 326 个候选入口均已尝试验证；合并 20 个有证据的路径/传输别名重复后保留 306 个入口，其中 13 个是无需适配的单篇文章或范围外引用。机构、网站、栏目分别计数，不能相加计算覆盖率。一个机构可能有多个站点；同一站点可能服务多个机构。主机名不同的别名不在没有证据时强行合并，HTTP/HTTPS 只有实际跳转、相同页面哈希或字符等价证据才合并。已检测 + 未检测 + 无需适配 = 候选入口总数。失败包括抓取受阻，不能一概解释成解析器不兼容。问题标签可重叠，其数量不能相加当成失败总数。

`jlu-site-inventory.csv` 的 `record_type` 区分 institution/site/column；`jlu-compatibility-report.csv` 每个规范化候选栏目一行，含原 URL、检查时间、原因、发现依据和逐项证据文件。空数值代表该步未执行或未获得可报告值，0 代表执行后确为零。既有栏目标记“既有正式配置；本轮回归结果”，其他行标记“未登记支持；仅审计结果”；本轮没有新增支持登记。

## 2. 代码审计结论

1. `backend/config/sources.yaml` 有 7 个来源：6 个吉大官方来源共 8 个已配置栏目，以及个人本地蓝桥杯单页监控。蓝桥杯不属于全校通知栏目范围，本轮不运行其个人监控或写入 baseline。
2. `app/sources/registry.py` 构建来源。CSE、CCST、CSW、本科生院、创新创业学院都是 `StaticHTMLSource` 的薄子类，共用 `app/parsers/html.py`；没有各学院独立的通用补救规则。OA 是独立公开适配器，使用 Struts 列表/详情、相对日期和 OA 附件引用解析。
3. 通用列表按 `.list`、`.news_list` 等选择器回退至 `ul li a`，以 `info/` 或 .htm/.html 判断文章。空栏目可能误抓导航；就业网 `/portal/jyzp/article/details?id=...` 不满足现有规则。列表日期对整个 li/tr 搜索完整日期，会遗漏拆分日期，并可能读到摘要中的活动/公示日期。
4. 通用详情只识别 h1/.article-title/.title，正文优先 `.v_news_content`、`#vsb_content` 等，最终可回退整页 body。校级站的 `.nr_title` 和其他模板不在标题规则内。附件扩展名只覆盖 pdf/doc/docx/xls/xlsx/zip；图片附件、rar/7z/ppt 等需要后续明确范围。VSB download.jsp 返回 HTML 时不能认定附件已下载。
5. `app/api/source_management.py` 的 preview 使用 GenericPublicSource，取至多 3 条详情。当前成功条件主要是解析出非空样本，不验证页面语义、日期对照、附件下载及历史覆盖，因此“预览成功”不是本专项验收标准。高级配置支持选择器和 next_page_selector，受 source_max_pages（默认 3）限制；未配置时默认 1 页。StaticHTMLSource 本身只抓配置的首屏，每栏目最多 30 条。
6. `CrawlerManager` 负责入库、增量跳过、baseline、关系及健康状态，来源并发默认 2。本专项不实例化/启动它。去重优先 public_id、canonical_url；通常按 source_id 限制标题匹配，OA 配置 dedup_across_sources=true。精确标题匹配有 14 天窗口；近似匹配阈值 0.92，检查最近 300 条。跨站转载的相同标题是候选，不能直接合并；不同 URL 的转载、HTTP/HTTPS 别名和模板标题污染可能影响去重。
7. `_sync_sources` 对缺省 ownership 的官方配置归为 OFFICIAL_CLOUD。Desktop 优先 CloudFeedSource，官方 cloud_preferred 只有规定的 Cloud feed 错误才允许已配置本地 fallback；SHARED_CLOUD 默认 cloud_only，个人来源 local_only。Cloud 只执行云所有权来源，遵守 enabled、cloud_policy 和间隔。本轮只测公开原站解析，不把本机结果外推成实际 Cloud feed 成功。
8. SafeFetcher 保留逐跳 URL 校验、大小上限、重定向上限和 TLS 校验；Local 允许系统代理/Fake-IP 的域名解析语义，Cloud 保留严格 DNS/IP/peer 边界。StaticHTMLSource 的静态正式来源路径没有相同的逐跳通用 URL/大小约束，后续扩展不能绕过 GenericPublicSource 的安全边界。审计网络统一经过 SafeFetcher 包装，未更改这两条产品路径。
9. TLS 使用当前工作区工厂：Windows truststore + certifi，非 Windows 保持 certifi。此前 TLS 报告不是本轮全校验收证据；本机证书链能构建也不等于 Linux Cloud 能构建。证书失败不降级、不关闭验证。
10. 现有测试覆盖 parser fixtures、OA、source preview/选择器、安全、Cloud/本地 fallback、去重、数据库迁移、增量、保留策略和 TLS。本轮完整回归最终结果：**235 passed, 1 skipped in 33.76s**。早期测试环境覆盖引起 4 个默认设置断言失败；工作区同时变化期间另有 6 个新增 HTTP 诊断测试失败，后续独立 7 项和完整回归均通过。保留原日志，不用早期结果替代最终基线。前端未改动，本轮不重复 UI 测试。

审计以当前工作区为准。开始时已存在 TLS、前端等未提交改动，过程中另有 HTTP 诊断代码/测试变化，全部保留。解析验证代码指纹见 `jlu-audit-evidence/validation-code-manifest.json`；最终指纹复核见验收记录。相关背景已读取 UI_AUDIT、Gate 13/14 架构与 Fake-IP/TLS 报告；本专项不改变 UI 或跨入后续实现 Gate。

收尾时另一个同期专项的 [OA_SOURCE_ERROR_REPORT.md](OA_SOURCE_ERROR_REPORT.md) 已记录：默认域名路径 TLS EOF、独立以太网定向访问成功、旧 certifi 路径链验证失败及 Cloud feed 未配置。该报告的定向 socket/临时路由实验不属于本专项；本轮未更改出口或复用它作为 OA 的通过证据。这里的 OA 仍按匿名默认路径实际受阻记录。SafeFetcher 当前仍可能把空消息异常压成 `Source request failed:`，故本轮未将这些不完整错误擅自判成超时或证书失败。

## 3. 官方发现依据和执行方法

从学校官网的 [管理、服务与业务机构](https://www.jlu.edu.cn/jgsz/gl_fwyywjg.htm)、[院系设置](https://www.jlu.edu.cn/jgsz/yxsz.htm)、[研究机构](https://www.jlu.edu.cn/jgsz/yjjg.htm)、[附属单位及校管企业](https://www.jlu.edu.cn/jgsz/fsdwjxgqy.htm) 提取真实链接与未链接名称。补充 [官网通知](https://www.jlu.edu.cn/index/tzgg.htm)、[学工处通知](https://xsc.jlu.edu.cn/index/tzgg.htm)、[就业网公开列表](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg) 及官方页面证实的附属学校站点。每条发现依据保存在 CSV 与 supplemental-seeds.json，没有暴力扫描或猜测子域名。

先完成代码审计和四类目录/站点/栏目清单，再冻结清单执行批量预览。每站只看首页及最多六个一级教学、学工、科研等入口；保留被数量上限排除的入口。除官方目录和补充种子外不无限递归遍历。目录里的研究平台分组标题不计机构，未链接研究机构仍保留待确认；混合机构段落的未链接名称保留原样，不擅自拆解组织关系。

请求串行，全局至少 1 秒、同 origin 至少 1.2 秒，遵守更长 robots Crawl-delay；每请求 12 秒超时，瞬时故障最多两次尝试，证书/401/403/429/禁止规则不重试。robots 404/410 可继续；不可读取 robots 时保守停止，记录受阻而不推测规则。HTTP 目录入口失效时仅尝试同主机 HTTPS，保留原失败证据，不降级 HTTPS。遇登录、验证码或访问控制不操作、不绕过。

复用 GenericPublicSource.fetch_list/fetch_detail 与已配置来源纯解析方法，网络改由同一限速缓存提供；不调用带入库副作用的 crawler/API。P0/P1 取前两条详情，其他栏目取第一条；详情失败也记录。对照 DOM 的文章链接、标题/文档标题、独立发布日期标记、正文容器、可见附件；至多跟随一页分页。附件最多读取首个文件端点的 1 KiB，识别 HTML/空响应，其他文件明确未检查。OA 编码附件需要 POST 的链路本轮不执行，不能声称附件通过。

“完全通过”只表示本轮已检查样本没有发现问题。存在缺日期、标题截断/不一致、正文回退、附件未核验、分页不完整等任一项即部分通过；空结果、明显导航误抓、正文导航污染或所有详情失败即失败。单页 VSB 的禁用下页按钮会复核为单页，避免误报“分页未解析”。栏目外全国平台和单篇文章引用排除适配；URL 百分号别名去重记录见 url-aliases.json。可疑漏抓列表只作为待复核候选，因为旁栏文章可能不属于目标栏目。

## 4. 网站发现状态

| 状态 | 入口数 | 解释 |
| --- | ---: | --- |
| no_column_discovered | 44 | 限定发现范围内未找到栏目，不等于站点无通知 |
| unreachable | 15 | 网络、TLS、robots 或访问限制受阻 |
| reachable | 121 | 发现了候选栏目，尚不等于兼容 |

### 无法访问或规则受阻的入口

| URL | 时间 | 原因 |
| --- | --- | --- |
| https://bmb.jlu.edu.cn/ | 2026-10-13T13:33:53+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://jjw.jlu.edu.cn/ | 2026-10-13T13:33:59+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://xinfang.jlu.edu.cn/ | 2026-10-13T13:34:07+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| http://zzb.jlu.edu.cn/ | 2026-10-13T13:49:12+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://jgdw.jlu.edu.cn/ | 2026-10-13T13:34:20+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://cw.jlu.edu.cn/ | 2026-10-13T13:35:16+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://sjc.jlu.edu.cn/ | 2026-10-13T13:35:22+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://lab.jlu.edu.cn/ | 2026-10-13T13:37:23+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://xyk.jlu.edu.cn/ | 2026-10-13T13:38:01+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| http://lib.jlu.edu.cn/ | 2026-10-13T13:49:18+08:00 | RuntimeError: ROBOTS_DISALLOWED: https://lib.jlu.edu.cn/ |
| https://www.jdyy.cn/ | 2026-10-13T13:44:05+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed: Server disconnected without sending a response. |
| http://www.legal-theory.org/ | 2026-10-13T13:49:20+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| http://zsb.jlu.edu.cn/ | 2026-10-13T13:49:34+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: RuntimeError: ACCESS_RESTRICTED_HTTP_403: https://zsb.jlu.edu.cn/robots.txt |
| https://oa.jlu.edu.cn/ | 2026-10-13T13:48:46+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
| https://jdgz.jlu.edu.cn/ | 2026-10-13T13:49:41+08:00 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: TLS_CERTIFICATE_VERIFY_FAILED: GET https://jdgz.jlu.edu.cn/robots.txt: ('根据当前系统时钟或签名文件中的时间戳验证时要求的证书不在有效期内。',) <- ConnectError: ('根据当前系统时钟或签名文件中的时间戳验证时要求的证书不在有效期内。',) <- ConnectError: ('根据当前系统时钟或签名文件中的时间戳验证时要求的证书不在有效期内。',) <- SSLCertVerificationError: ('根据当前系统时钟或签名文件中的时间戳验证时要求的证书不在有效期内。',) <- SSLCertVerificationError: ('根据当前系统时钟或签名文件中的时间戳验证时要求的证书不在有效期内。',) |

## 5. 现有来源与校级通知回归

以下仅代表原站本轮样本，Cloud feed 与已安装客户端另列未验证。

| 栏目 | URL | 列表数 | 详情样本数 | 结果 | 问题/证据 |
| --- | --- | ---: | ---: | --- | --- |
| 吉林大学计算机科学与技术学院 / 教学通知 | https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm | 10 | 2 | 部分通过 | ATTACHMENT_ENDPOINT_FAILED; PAGINATION_NOT_CONFIGURED；[1cd1acce79f072ab.json](jlu-audit-evidence/results/1cd1acce79f072ab.json) |
| 吉林大学网络安全学院 / 本科教学通知 | https://cse.jlu.edu.cn/bkjxtz.htm | 3 | 2 | 完全通过 | 本次样本标题、日期、正文、可见附件与单页状态检查无发现；非历史全量或Cloud认证；[84dfcf2a24e7e5a0.json](jlu-audit-evidence/results/84dfcf2a24e7e5a0.json) |
| 吉林大学网络安全学院 / 学院通知 | https://cse.jlu.edu.cn/xytz.htm | 8 | 2 | 部分通过 | BODY_CONTAINER_FALLBACK; BODY_TOO_SHORT; PAGINATION_NOT_CONFIGURED；[680c118ccf5bb51c.json](jlu-audit-evidence/results/680c118ccf5bb51c.json) |
| 吉林大学软件学院 / 教办通知 | https://csw.jlu.edu.cn/index/jbtz.htm | 15 | 2 | 部分通过 | ATTACHMENT_ENDPOINT_FAILED; ATTACHMENT_MISSING; PAGINATION_NOT_CONFIGURED；[1e705b1f23e7eeb0.json](jlu-audit-evidence/results/1e705b1f23e7eeb0.json) |
| 吉林大学软件学院 / 学院通知 | https://csw.jlu.edu.cn/index/xytz_.htm | 15 | 2 | 部分通过 | ATTACHMENT_ENDPOINT_FAILED; ATTACHMENTS_UNCHECKED; PAGINATION_NOT_CONFIGURED；[164eccdf38fd0d67.json](jlu-audit-evidence/results/164eccdf38fd0d67.json) |
| 吉林大学创新创业教育学院 / 通知公告 | https://cxcyjyxy.jlu.edu.cn/index/tzgg.htm | 15 | 2 | 部分通过 | ATTACHMENT_ENDPOINT_FAILED; PAGINATION_NOT_CONFIGURED；[792363a55457d183.json](jlu-audit-evidence/results/792363a55457d183.json) |
| 吉林大学本科生院 / 通知公告 | https://jwc.jlu.edu.cn/zxzx/tzgg.htm | 15 | 2 | 部分通过 | ATTACHMENT_ENDPOINT_FAILED; PAGINATION_NOT_CONFIGURED；[dc5149df919d48b0.json](jlu-audit-evidence/results/dc5149df919d48b0.json) |
| 吉林大学 OA 校内通知 / 校内通知 | https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577 | 未执行 | 0 | 失败 | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed: ；[cd2035ca91d0ee7c.json](jlu-audit-evidence/results/cd2035ca91d0ee7c.json) |
| 吉林大学 / 通知公告 | https://www.jlu.edu.cn/index/tzgg.htm | 20 | 2 | 部分通过 | TITLE_NOT_IN_DETAIL_HEADING; PAGINATION_NOT_CONFIGURED; TITLE_TRUNCATED；[c08776d235e432b8.json](jlu-audit-evidence/results/c08776d235e432b8.json) |

## 6. 问题分类与复现证据

每个栏目的全部标签、时间和快照在兼容性 CSV 与对应 JSON 中；这里按问题类型各列至多两个样例，标签数允许重叠。

| 问题 | 栏目数 | 样例 URL |
| --- | ---: | --- |
| PAGINATION_NOT_CONFIGURED | 189 | https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm；https://cse.jlu.edu.cn/xytz.htm |
| ATTACHMENT_ENDPOINT_FAILED | 108 | https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm；https://csw.jlu.edu.cn/index/jbtz.htm |
| LIST_DATES_MISSING | 77 | https://yzb.jlu.edu.cn/bszs/lqgs.htm；https://yzb.jlu.edu.cn/bszs/zsgg.htm |
| TITLE_NOT_IN_DETAIL_HEADING | 72 | https://www.jlu.edu.cn/index/tzgg.htm；https://auto.jlu.edu.cn/zsxx.htm |
| ATTACHMENTS_UNCHECKED | 53 | https://csw.jlu.edu.cn/index/xytz_.htm；https://hssra.jlu.edu.cn/tzgg1.htm |
| TITLE_MISMATCH | 40 | https://cbae.jlu.edu.cn/jyxx.htm；https://ccfe.jlu.edu.cn/djgz/tbtz.htm |
| BODY_CONTAINER_FALLBACK | 37 | https://cse.jlu.edu.cn/xytz.htm；https://auto.jlu.edu.cn/zsxx.htm |
| POSSIBLE_NAVIGATION_CAPTURE | 27 | https://auto.jlu.edu.cn/zsxx.htm；https://ccfe.jlu.edu.cn/djgz/tbtz.htm |
| PAGINATION_DYNAMIC_OR_UNRESOLVED | 19 | https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs；https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg |
| LIST_CANDIDATE_RECALL_GAP | 17 | https://dmse.jlu.edu.cn/gjjl/tzgg.htm；https://dmse.jlu.edu.cn/ynbg/xytz.htm |
| BODY_TOO_SHORT | 14 | https://cse.jlu.edu.cn/xytz.htm；https://cer.jlu.edu.cn/jyxx/tzg.htm |
| EMPTY_LIST | 14 | https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs；https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg |
| OUT_OF_SCOPE_REFERENCE | 13 | https://dec.jlu.edu.cn/html/xljy/tzgg/tzggjwbgs/202609281485.html；https://yz.chsi.com.cn/ |
| ATTACHMENT_MISSING | 11 | https://csw.jlu.edu.cn/index/jbtz.htm；https://ccst.jlu.edu.cn/kxyj/kytz.htm |
| BODY_NAVIGATION_CONTAMINATION | 10 | https://hac.jlu.edu.cn/dqgz/tzgg.htm；https://hac.jlu.edu.cn/gjjl/tzgg.htm |
| LIST_DETAIL_DATE_DIFFERENCE | 8 | https://xsc.jlu.edu.cn/index/tzgg.htm；https://chem.jlu.edu.cn/glfw/hxzhpt/ptgg.htm |
| DATE_MISSING | 7 | https://cbae.jlu.edu.cn/jyxx.htm；https://ccfe.jlu.edu.cn/djgz/tbtz.htm |
| DATE_MISMATCH | 5 | https://ee.jlu.edu.cn/sys_/sysaqtzgg.htm；https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm |
| ROBOTS_UNAVAILABLE | 4 | https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577；https://yjs.jlu.edu.cn/gsapp/sys/dbgsglappecupl/*default/index.do |
| TITLE_TRUNCATED | 4 | https://www.jlu.edu.cn/index/tzgg.htm；https://gest.jlu.edu.cn/yjsjy/tztg.htm |
| COLUMN_IS_HOMEPAGE_NEEDS_SCOPE_REVIEW | 4 | https://jwc.jlu.edu.cn/；http://icfs.jlu.edu.cn/index.htm |
| NETWORK_ERROR | 2 | https://dec.jlu.edu.cn/html/tzgg1；https://dec.jlu.edu.cn/html/xljy/tzgg |
| ENCODING_REPLACEMENT | 1 | https://spxy.jlu.edu.cn/bksjy/jxxx.htm |
| PAGINATION_PARSE_EMPTY | 1 | https://fszx.jlu.edu.cn/xwzx/tzgg.htm |
| HTTP_ERROR | 1 | http://jlucqe.jlu.edu.cn/list.php?SID=1 |

### 已人工对照的关键现象

- 计算机教学通知 `https://ccst.jlu.edu.cn/info/1056/21217.htm`：列表/详情标题及 2026-10-10 日期一致，正文 716 字符，可见 docx 已提取；下载端点 `wbfileid=18207182` 的 Range 请求返回 206、`text/html;charset=UTF-8`、HTML 文件头，不能计为附件下载通过。没有绕过下载页验证。
- 校级通知 `https://www.jlu.edu.cn/info/1095/58176.htm`：完整标题在 `.nr_title`，列表末尾有省略号，通用标题选择器未命中而保留截断标题。应补模板标题选择器；不能把“返回非空标题”当正确。
- 学工 `https://xsc.jlu.edu.cn/info/1048/5941.htm`：详情发布日期为 2026-10-13；列表日期分为日与年月，摘要出现公示期 2026-10-12，通用 li 全文搜索错误取后者。应绑定日期节点并组合年月日，不从摘要取第一个日期。
- 软件教办 `https://csw.jlu.edu.cn/info/1095/8548.htm`：有六个 jpg 的 download.jsp 附件引用，通用附件扩展名规则均未输出。图片型成绩公示需要明确附件/图片内容呈现方案。
- 就业网通知、公示原页是公开服务端 HTML，存在 `/portal/jyzp/article/details?id=...` 标题链接与“创建时间”，不是只靠浏览器渲染才可见；通用规则未识别该 URL 类型而返回空列表。
- 多个空栏目回退 `ul li a` 后把 .htm 导航当文章，出现 30 条“候选”。例如汽车招生、公共计算机党建、历史文化部分栏目，详情又回退 body，构成可复现的预览假成功风险。
- 附中实验学校 `jdgz.jlu.edu.cn` 的 TLS 返回证书有效期校验失败原始异常，未关闭验证。图书馆入口因 robots 禁止而未继续访问，不能判为解析失败或无需适配。

复现时以本地快照与请求时间为准；搜索工具可能返回旧缓存或超时，不能用它覆盖真实匿名抓取结果。报告不附完整正文摘录，必要摘要与 HTML SHA-256 在逐项证据里。

## 7. 可复用规则与后续实现建议

| 模板/机制 | 复用方向 | 验收条件 |
| --- | --- | --- |
| VSB 普通列表与 `.v_news_content` / `#vsb_content` | 先复用现有 GenericPublicSource，按站点配置列表容器、标题和日期节点 | 空栏目为零、排除导航、至少三条详情比对；列表/详情日期一致 |
| VSB 分拆日期（学工、招生、部分学院） | 合成年/月/日，限定在日期元素；详情使用发布元信息 | 跨月跨年、摘要含截止日期也不能影响发布日期 |
| 校级 `.nr_title` 及学院不同标题容器 | 明确选择器并从标题节点剔除元信息 | 截断列表标题必须恢复全文，不将栏目名当通知标题 |
| VSB download.jsp / 图片附件 | 保留 filename/url/type；扩展名白名单需明确图片/压缩包/演示文件范围；区分下载页与二进制 | 不绕验证码，受限附件明确标记，不能以 200/206 当可下载 |
| VSB `.p_next a` / 禁用 `.p_next_d` | 使用现有 next_page_selector 与 1–3 页上限，页间 URL 去重 | 首次历史覆盖与日常增量分别验收，单页按钮禁用不误报 |
| 吉林大学就业网 SSR 列表 | 公开 details?id 链接、独立创建时间与内容容器的选择器/小型适配器 | 通知、公示、招聘、实习分别限定栏目；保持 id/query 的身份语义 |
| 公开 OA | 保留专用 Struts、相对日期及附件编码规则 | 本地与实际 Cloud 各自验收；POST 附件链路另开受限验证，不纳入本轮已通过 |
| 非 VSB/动态平台、重定向链较长 | 先确认公开 API 或服务端 HTML，再评估现有 api/selector 适配 | 不提高安全上限来掩盖登录跳转；需要认证时保持 local_only 的既有策略 |

本轮没有将建议写入正式来源。后续每批先加脱敏 fixture 与失败复现，再实现最小规则，离线测试、原站抽样、Cloud 环境和不污染正式 DB 的增量/去重回归通过后，才逐条登记支持。

## 8. 分级待适配方案

- **P0**：先闭环 OA 原站访问回归受阻、校级标题截断、现有 CSE 空正文及既有来源附件可用性。为通用 preview 加语义门槛，禁止导航/body 回退假成功流入正式来源。保持 cloud_preferred/fallback 条件和既有数据库身份。
- **P1**：学工日期节点、就业网 details?id 规则、本科/研究生招生、教务、科研和团委。优先用高级选择器验证高价值栏目，补一页受限分页和附件证据，再决定是否需要新 adapter。
- **P2**：按 CMS 模板批量复用各学院公开通知规则；先修误抓导航、错误标题和图片附件，再扩大栏目。已发现列表引用旁栏不能直接归为漏抓。
- **P3**：研究机构、医院、附属学校与校管企业。先确认官方链接/组织归属与 robots；未知官网、证书失败、站点消失分别处理，不用子域名猜测填满覆盖率。

具体待办按 CSV 的 priority/status/issues 排序，每个栏目都有可复现证据，不以机构级别的一个样本代替全部栏目验收。

## 9. 重复通知与覆盖边界

`duplicates.json` 分开保留跨栏目同 URL 与不同 URL 同标题/日期候选，只统计通过/部分通过列表，排除导航误抓和范围外引用。同 URL 重复发布通常可复用现有 canonical_url/关系去重；标题/日期重复可能是转载，也可能是不同对象的同名通知。正文一致性、目标人群及来源身份未充分对照前，不算数据库重复缺陷、不执行合并。数据仅来自本轮首屏，不能统计全校历史重复率。

未覆盖：无独立官网链接的机构；robots/网络/TLS/认证受阻入口；每站超过六个一级入口及更深页面；名称不含发现关键词的栏目；仅微信/公众号/内网发布；历史全部分页与历史详情；每栏目样本以外的附件和图片 OCR；OA 的附件 POST；受限系统；真实 Cloud Linux/PostgreSQL/feed 调度与安装客户端。没有条件证明无通知的网站不标无需适配。公开学术/新闻栏目混合通知时需要后续产品范围复核。

本轮因限速和有限递归而具有明确边界，不宣称穷尽所有官方站点。需认证数为本轮实际观测，不能解释成全校没有认证栏目。不能从兼容性样本计算“全校支持率”。

## 10. 证据、续检与验证

- [网站与栏目清单](jlu-site-inventory.csv)、[逐栏兼容性报告](jlu-compatibility-report.csv)。
- `jlu-audit-evidence/requests.json`：URL、原检查时间、重试次数、错误/HTTP、最终 URL、编码替换字符和快照 SHA-256。
- `http.jsonl`：每次实际响应元数据，不保存 Cookie/Authorization；网络无响应的异常在 requests.json。
- `html/`：公开页面快照；`results/`：逐栏详情对照、附件前缀/响应类型、分页及原因；`results.json` 汇总。
- `retry-history.json`、`pre-recheck-results.json`：有限重检前后证据；`review-decisions.json`：排除范围/单页/标题复核；`duplicates.json`：重复候选。
- 后端测试日志保留在 evidence；独立审计器有 7 项离线检查，覆盖错误标题、导航正文、附件漏抓、更多链接、分页与 OA URL 规范化。

```powershell
# 先审计/建清单，验证阶段只读；缓存存在时从断点继续。
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py discover
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate
# 可选有限瞬时故障重检，每 URL 累计尝试上限二次。
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py recheck
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py review
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py report
```

缓存的失败不会无限重试，成功记录保留原检查时间而非伪装成重新联网。要建立新日期的独立审计，应使用新证据目录/另行规划，不覆盖本轮历史。CSV 为 UTF-8 BOM，中文可直接导入 Excel；长原因和 URL 保持完整。

### 本机 TLS 对照（不代表 Cloud 生产）

| 来源 | certifi-only | Cloud DNS 策略对照 | 错误 |
| --- | --- | --- | --- |
| cse | True | UnsafeSourceUrl: Local and private network addresses are not allowed for this source |  |
| ccst | True | UnsafeSourceUrl: Local and private network addresses are not allowed for this source |  |
| csw | True | UnsafeSourceUrl: Local and private network addresses are not allowed for this source |  |
| jwc | True | UnsafeSourceUrl: Local and private network addresses are not allowed for this source |  |
| innovation | True | UnsafeSourceUrl: Local and private network addresses are not allowed for this source |  |
| oa | False | UnsafeSourceUrl: Local and private network addresses are not allowed for this source | RuntimeError: ROBOTS_UNAVAILABLE: SourceError: Source request failed:  |
