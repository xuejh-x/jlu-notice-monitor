# 吉林大学通知适配 B6 完整板块修复与验证报告

交付时间：2026-10-15T20:27:22.476537+08:00（Asia/Shanghai）。本批网络采集：2026-10-15T19:26:41+08:00 至 2026-10-15T20:10:23+08:00；离线复核时间另存于逐条记录。

按用户“B6 和 B7 分两次，每次完成一整个大板块”的要求，本次覆盖原清单全部 **164 个 P2 入口**，并在 B6 交付点停止。B7 尚未执行。这里的完成指限定范围内的检查、可复现代码修复、逐条结论和独立候选交付，**不表示全部来源已支持或生产准入已完成**。

## 1. 范围与结果

原口径：30 个曾失败、127 个部分通过、7 个抽样通过；按完整入口 URL 去重为 164 条，涉及 47 个主机。原始全校清单和报告保留原时间与原结论，不覆盖。

其中 **163 个入口执行了本次访问检查，161 个取得页面、2 个访问受阻；1 个 OA 登录引用按用户要求未发请求**。5 个无需作为独立公开通知来源的性质结论与这些访问计数重叠，不能相加。

| 本次结论 | 数量 | 含义 |
| --- | ---: | --- |
| 有界内容／分页／隔离增量样本通过 | 131 | 本机保存页面核对通过；仍有下载、Cloud、历史等能力限制 |
| 当前空栏目 | 19 | 有明确零记录或空列表＋禁用分页证据；不能视为通知样本通过 |
| 权限受限 | 1 | 明确拒绝访问栏目；未证明登录能解决，未绕过 |
| 访问受阻 | 2 | 服务器断连或 robots 不可读取；不归为解析失败 |
| 能力／证据限制待处理 | 6 | 个别文章权限拒绝、外部图片、正文为空、发布日期未确认、重复发布候选 |
| 引用、静态介绍、目录或登录入口 | 5 | 不作为独立公开通知来源；OA 保持用户要求暂缓 |

完整环境准入 **0**；正式启用 **0**；新增独立候选 **159**，全部禁用。无需作为栏目适配是目标性质结论，不表示该机构没有通知。

最终检查 247 个列表页面记录、2986 条去重后的各栏目列表记录（跨栏目不合并计数）、394 篇详情检查记录，其中 389 篇通过标题／日期／正文／附件 DOM 对照。成功隔离两轮重放 136 项；同文合并候选仍单列，不能据此推断生产数据库重复。

[逐栏 CSV](jlu-b6-compatibility-report.csv) · [完整结果](jlu-fix-b6/review-accepted-20261015/results.json) · [最终统计](jlu-fix-b6/review-accepted-20261015/summary.json) · [候选](jlu-fix-b6/source-candidates.json) · [环境矩阵](jlu-fix-b6/admission-matrix.json)

## 2. 实际修复

1. **空栏目识别**：支持 VSB 空 UL 与全禁用首屏分页组合、旧版 `共0条 0/0` 分页表格及医院明确空数据容器；真实文章链接与空标记冲突时不宣告为空，不再退回导航。
2. **医院 CMS**：五个有内容栏目复用高级选择器，标题和列表日期分开；详情使用 `.article_details1 .cont > .title`、`.liner`、`.cont > .text`；支持实际公开 GET 分页链接，不执行 JS 或猜接口。图片正文保留同源图链接，未下载图片或 OCR。
3. **VSB 文章头部**：补经页面证明的作用域标题规则；未知 VSB h3/h5 仅在文章正文之前且有列表前缀／文档标题佐证时采用。新增未知头部日期回退仅使用文章正文之前的明确元信息；冲突或仅有更新／正文活动日期时保留未确认。
4. **分类错抓和旧文漏抓**：同一带日期列表行中的分类链接不能借用文章日期。旧版 JSP 文章只识别 `urltype=news.NewsContentUrl` 且有单一合法 `wbtreeid/wbnewsid` 的已见链接，完整保留查询身份；树目录或异常参数不视为文章。两个实际旧文返回权限提示，已按明确权限受限分类，未伪装成成功详情。
5. **相邻文章标题污染**：正文之后的上一条／下一条标题不覆盖当前通知。东北亚学院实际样本证明旧解析曾误用相邻链接文字。
6. **明确 MP4 附件**：艺术学院附件区的合法视频下载链接现在保留名称、类型和完整参数；不把正文图片当附件，也不声称视频可自动下载。
7. **奖学金误合并**：材料学院“学业奖学金”和“国家奖学金”通知具有不同正文和附件，原近似匹配在隔离库中只保留两条样本；修复后保留三条。仅拦截明确不同奖项的标题近似匹配，URL/public_id 优先级、14 天窗口、0.92 阈值、来源关系和用户状态保持。

应用改动限于 `backend/app/parsers/html.py` 和 `backend/app/services/deduplication.py`。见 [本批代码差异](jlu-fix-b6/application-changes.diff)、[真实模板样本来源](../backend/tests/fixtures/jlu_b6/manifest.json)。

## 3. 仍有限制的结果

| 机构／栏目 | URL | 原因 |
| --- | --- | --- |
| 法学院／通知公告 | [https://law.jlu.edu.cn/djgz/tzgg.htm](https://law.jlu.edu.cn/djgz/tzgg.htm) | HTML_PERMISSION_REQUIRED: response denies access to this page or column；[记录](jlu-fix-b6/results/p2-2ec9326c9cde.json) |
| 商学与管理学院／招聘通知 | [https://sg.jlu.edu.cn/zyfz/zptz.htm](https://sg.jlu.edu.cn/zyfz/zptz.htm) | HTML_DETAIL_IMAGE_ONLY_UNSUPPORTED: image notice has no extractable text; image support requires verification；[记录](jlu-fix-b6/results/p2-5231cd19a622.json) |
| 东北亚学院、东北亚研究院／通知公告 | [https://nasa.jlu.edu.cn/tzgg.htm](https://nasa.jlu.edu.cn/tzgg.htm) | HTML_PERMISSION_REQUIRED: response denies access to this page or column；[记录](jlu-fix-b6/results/p2-e6225fdb065b.json) |
| 生物与农业工程学院、仿生科学与工程学院／就业信息 | [https://cbae.jlu.edu.cn/jyxx.htm](https://cbae.jlu.edu.cn/jyxx.htm) | DATE_NOT_INDEPENDENTLY_VERIFIED；[记录](jlu-fix-b6/results/p2-05b686fcce16.json) |
| 计算机科学与技术学院 / 吉林大学计算机科学与技术学院／科研通知 | [https://ccst.jlu.edu.cn/kxyj/kytz.htm](https://ccst.jlu.edu.cn/kxyj/kytz.htm) | Same-title publication/identity candidate requires manual review; no production merge；[记录](jlu-fix-b6/results/p2-545799ceadc0.json) |
| 软件学院 / 吉林大学软件学院／招生信息 | [https://csw.jlu.edu.cn/zsxx/bkzs.htm](https://csw.jlu.edu.cn/zsxx/bkzs.htm) | HTML_DETAIL_EMPTY: no text or supported attachment in the notice container；[记录](jlu-fix-b6/results/p2-cbc532d0ce0d.json) |

- 商学招聘图片样本的外部／不允许图片引用未被放行，维持既有同源图片边界。
- 软件学院空正文不以标题、导航或虚构文字填充。生物与农业工程学院静态就业介绍缺少可确认发布元信息，不用活动日或抓取日补齐。
- 计算机学院两个同标题同日正文样本属于重复发布候选，但附件下载编号不同，未下载附件；保留人工复核，不据此在正式库合并或删除。
- 药学院旧学院通知入口仍返回“您没有访问当前栏目的权限”；其官网公开通知和招生栏目分别核验，不能据此宣布旧受限入口恢复。
- 法学院和东北亚学院两个旧版 JSP 详情返回 HTTP 200 并跳到权限提示页，明确写“您无权访问此页面”。已修复权限分类，保留文章受限结论；未猜测其他文章路径或尝试绕过。
- 历史文化学院 `xwgg/tzgg.htm` 在本次请求断连；体育旧 `isc/oaindex.htm` 因 robots 断连停止。未关闭 TLS、改变网络出口或增加重试。
- 数学招生入口嵌入单篇招生介绍、汽车招生入口是四个子板块的目录、医院停电链接是单篇文章、卓越工程师招生入口全部引用外站；分别排除为独立通知栏目，子板块与外站全文仍未纳入本批。
- 原标签中附件端点、正文之外的历史样本和源数据编码问题未因样本通过而清零。CSV 保留原标签及本轮列表替换字符数；本批没有重新探测已知验证码／robots 限制的附件端点。

食品学院教学信息列表本次仍有 **3 个替换字符**；详情抽样通过不代表列表其余源数据已修复，未盲目转码。此项与有界样本分类重叠，不另加进 164 条总数。

## 4. 分页、重复和数据保护

每栏目最多两页、每轮最多三篇合法文章详情（不足三篇全检）；修正错误采样后另补五篇详情，再为旧版 JSP 增补两篇模板控制，全部来自已保存列表的实际 href。初轮误选的分类入口保留请求证据，不能当作有效详情样本。没有请求第三页或开展历史补抓。

隔离重放使用内存 SQLite，检查 notice 身份、来源关系、baseline、已读和收藏；旧于十年的样本仅在该身份测试上下文中关闭过期筛选，生产保留期最大值仍为 3650，默认策略未修改。此处是保存的解析样本重放，不能代替实际 Cloud/feed 或已安装客户端刷新。

本轮有界列表出现同 URL 跨栏目引用候选 92 组、同标题同日期不同 URL 候选 53 组。[候选台账](jlu-fix-b6/duplicate-candidates.json)保留来源与 URL；它们不是已证实的生产数据库重复。

## 5. 执行环境、测试和证据

网络单进程串行，全局至少 1 秒、同源至少 1.2 秒，遵守更长 robots Crawl-delay；超时／瞬时 502/503/504 最多两次尝试，权限／403／429／证书／robots 限制停止。本批共 728 次 HTTP 请求尝试，最终缓存 726 个逻辑 URL 记录，核对 678 个解码后 HTML 快照 SHA。

无登录或验证码操作、无附件文件下载、无 OA 请求、无真实远程 Cloud/feed 请求、无正式数据库连接。Windows 公开抓取与离线重放分别记录；Cloud/Linux、公共 feed、安装客户端的当前状态仍未验证。

| 验证 | 真实结果 |
| --- | --- |
| 本批前完整基线 | 487 passed, 1 skipped |
| 首轮缺陷复现 | 15 failed, 355 passed |
| 最终针对性回归 | 394 passed |
| 最终完整后端回归 | 533 passed, 1 skipped |
| 新增测试 | 46 项 |

1 项跳过为未提供 `JLU_TEST_POSTGRES_URL` 的可选 PostgreSQL 集成测试；隔离入口不连接外部数据库，不能算作 PostgreSQL 或 Cloud 生产验收通过。

[测试日志和指纹](jlu-fix-b6/final-manifest.json)与各阶段日志保留。中间的样本裁剪、测试保留期参数和审计 helper 导入环境泄漏均已修正；[工具迭代记录](jlu-fix-b6/tooling-iterations.json)说明其原因，不计为站点失败。未改 UI，因此未运行前端测试。

原审计 1449 个受保护文件、8 份先前批次报告 SHA 保持；正式 sources/settings、API、Cloud/Desktop 策略、数据库结构、前端和系统网络均未改。[保护校验](jlu-fix-b6/preservation.json)

## 6. 原 30 个失败入口的逐条处置

| 机构／栏目 | URL | 最新结论 | 证据 |
| --- | --- | --- | --- |
| 哲学社会学院／就业信息 | [https://zsy.jlu.edu.cn/yjsjy/jyxx.htm](https://zsy.jlu.edu.cn/yjsjy/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-b4ad9576f8de.json) |
| 历史文化学院／通知公告 | [https://hac.jlu.edu.cn/dqgz/tzgg.htm](https://hac.jlu.edu.cn/dqgz/tzgg.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-10b02b68c1e9.json) |
| 历史文化学院／通知公告 | [https://hac.jlu.edu.cn/gjjl/tzgg.htm](https://hac.jlu.edu.cn/gjjl/tzgg.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-00df1137578a.json) |
| 历史文化学院／就业信息 | [https://hac.jlu.edu.cn/zsyjy/jyxx.htm](https://hac.jlu.edu.cn/zsyjy/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-746d87b2613e.json) |
| 外国语言文化学院／党务公示 | [https://sflc.jlu.edu.cn/dzgz/dwgs.htm](https://sflc.jlu.edu.cn/dzgz/dwgs.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-0f03bd864044.json) |
| 外国语言文化学院／就业信息 | [https://sflc.jlu.edu.cn/xtgz/jyxx.htm](https://sflc.jlu.edu.cn/xtgz/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-4bfc23b0fadd.json) |
| 体育学院／校内通知 | [https://oa.jlu.edu.cn/defaultroot/login.jsp](https://oa.jlu.edu.cn/defaultroot/login.jsp) | 无需作为公开栏目适配／LOGIN_REFERENCE_OA_DEFERRED | [记录](jlu-fix-b6/results/p2-c0bb9a0353fb.json) |
| 东北亚学院、东北亚研究院／就业信息 | [https://nasa.jlu.edu.cn/bksjy/jyxx.htm](https://nasa.jlu.edu.cn/bksjy/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-1ce2bf7487f4.json) |
| 东北亚学院、东北亚研究院／就业信息 | [https://nasa.jlu.edu.cn/yjsjy/jyxx.htm](https://nasa.jlu.edu.cn/yjsjy/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-bdfdf1b77340.json) |
| 东北亚学院、东北亚研究院／院办通知 | [https://nasa.jlu.edu.cn/xzgz/ybtz.htm](https://nasa.jlu.edu.cn/xzgz/ybtz.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-3e37d545072d.json) |
| 公共外交学院／通知公告 | [https://sipa.jlu.edu.cn/hzjl/tzgg.htm](https://sipa.jlu.edu.cn/hzjl/tzgg.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-0f712420c5c4.json) |
| 数学学院／招生信息 | [https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm](https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm) | 无需作为栏目适配／STATIC_INFORMATION_PAGE | [记录](jlu-fix-b6/results/p2-f80ea8ffb177.json) |
| 物理学院／就业信息 | [https://phy.jlu.edu.cn/rcpy/yjsjy/jyxx.htm](https://phy.jlu.edu.cn/rcpy/yjsjy/jyxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-5a4d3e884db0.json) |
| 生命科学学院／通知公告 | [https://life.jlu.edu.cn/xsgz/yjsgl/tzgg.htm](https://life.jlu.edu.cn/xsgz/yjsgl/tzgg.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-4e030ec36a90.json) |
| 汽车工程学院／招生信息 | [https://auto.jlu.edu.cn/zsxx.htm](https://auto.jlu.edu.cn/zsxx.htm) | 无需作为栏目适配／SECTION_DIRECTORY_REFERENCE | [记录](jlu-fix-b6/results/p2-8e958c4c25bd.json) |
| 电子科学与工程学院、集成电路学院／实验室安全通知公告 | [https://ee.jlu.edu.cn/sys_/sysaqtzgg.htm](https://ee.jlu.edu.cn/sys_/sysaqtzgg.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-8cc2288150cd.json) |
| 通信工程学院／招生信息 | [https://dce.jlu.edu.cn/tzgg/zsxx.htm](https://dce.jlu.edu.cn/tzgg/zsxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-46e3c7812119.json) |
| 通信工程学院／招聘信息 | [https://dce.jlu.edu.cn/tzgg/zpxx.htm](https://dce.jlu.edu.cn/tzgg/zpxx.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-fae607a04b9c.json) |
| 公共计算机教学与研究中心／通报通知 | [https://ccfe.jlu.edu.cn/djgz/tbtz.htm](https://ccfe.jlu.edu.cn/djgz/tbtz.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-4adc4212e4ac.json) |
| 药学院／学院通知 | [https://yxy.jlu.edu.cn/wz-list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1209](https://yxy.jlu.edu.cn/wz-list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1209) | 权限受限／PERMISSION_RESTRICTED | [记录](jlu-fix-b6/results/p2-53c4ac131f1c.json) |
| 白求恩第三临床医学院／信息公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_59.html](https://www.zrlyyy.com/wujiaquery_g7yU_59.html) | 部分通过／BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | [记录](jlu-fix-b6/results/p2-9230d60e0f53.json) |
| 白求恩第三临床医学院／招生信息 | [https://www.zrlyyy.com/wujiaquery_g7yU_60.html](https://www.zrlyyy.com/wujiaquery_g7yU_60.html) | 部分通过／BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | [记录](jlu-fix-b6/results/p2-af1ca3ec1c4a.json) |
| 白求恩第三临床医学院／招标采购公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_61.html](https://www.zrlyyy.com/wujiaquery_g7yU_61.html) | 部分通过／BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | [记录](jlu-fix-b6/results/p2-c44f268c159e.json) |
| 白求恩第三临床医学院／通知公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_62.html](https://www.zrlyyy.com/wujiaquery_g7yU_62.html) | 部分通过／BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | [记录](jlu-fix-b6/results/p2-3315d5f7eb59.json) |
| 白求恩第三临床医学院／调研公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_864.html](https://www.zrlyyy.com/wujiaquery_g7yU_864.html) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-c85b8be444d2.json) |
| 白求恩第三临床医学院／关于因停电暂停官网服务的通知 2026.05.08 | [https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html](https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html) | 无需作为栏目适配／SINGLE_ARTICLE_REFERENCE | [记录](jlu-fix-b6/results/p2-fe74f8a02d7a.json) |
| 白求恩第三临床医学院／通知公告 | [https://www.zrlyyy.com/tongzhiy_g7yU_91.html](https://www.zrlyyy.com/tongzhiy_g7yU_91.html) | 部分通过／BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN | [记录](jlu-fix-b6/results/p2-fd4944826664.json) |
| 吉林大学网络安全学院／本科教学通知 | [https://cse.jlu.edu.cn/bksjy/bkjxtz.htm](https://cse.jlu.edu.cn/bksjy/bkjxtz.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-0ca7e7c9518e.json) |
| 吉林大学网络安全学院／研究生通知 | [https://cse.jlu.edu.cn/yjsjy/yjstz.htm](https://cse.jlu.edu.cn/yjsjy/yjstz.htm) | 当前空栏目／VERIFIED_EMPTY_COLUMN | [记录](jlu-fix-b6/results/p2-8882a3f2c642.json) |
| 体育学院／校内通知部门索引 | [http://isc.jlu.edu.cn/oaindex.htm](http://isc.jlu.edu.cn/oaindex.htm) | 受阻／ACCESS_BLOCKED | [记录](jlu-fix-b6/results/p2-6a839d15a404.json) |

其余原 127 个部分通过、7 个抽样通过入口也全部纳入同一最终 CSV 和机器台账，未因原状态良好而跳过。

## 7. 下一板块与未覆盖范围

本次停在完整 B6。按用户安排，下一次执行整个 **B7：P3 研究机构／附属单位、失效入口与剩余发现缺口**；包括原 112 个 P3 入口口径、剩余三个 P3 空结果、P3 导航风险和访问限制，以及 44 个未发现栏目、305 条官网未知机构的有界补证。各口径有重叠，不相加当机构或故障数。

B6 未覆盖：全部历史分页、非抽样详情、附件完整下载／校验和、图片 OCR、外站引用全文、需要访问权限的内容、实际 Cloud Linux/feed、客户端安装运行、正式数据库迁移。既有 OA 暂缓、招生日期未确认与本报告受限项继续保留，不因进入 B7 而改成已支持。

本批未提交 GitHub、发布 Release、更新安装客户端或启用来源。后续正式准入应按指定环境逐条审查；B7 本次没有执行。
