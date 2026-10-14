# 吉林大学通知适配历次失败汇总

整理时间：2026-10-14T17:07:00.324112+08:00（Asia/Shanghai）。只汇总已保存证据，本次不联网、不运行 crawler、不访问正式数据库、不修改来源。

## 1. 先看结论

原始审计最终清单有 **48 个失败栏目**：27 个疑似导航误抓、14 个空列表、7 个访问或链接受阻。它们并非 48 个站点，也不是 48 个当前仍坏的解析器。

合并原审计、B1/B2/B3 实时结果、B4 首轮初判及最终离线复核，按完整栏目 URL 去重得到 **60 个曾失败或权限受限的栏目**，对应 70 条失败事件和 1 条权限事件。这个数含已修复问题及工具初判，不能称为当前失败总数。更早审计初判、别名及中间重放不重复累计，原始记录保持不变。

| 最新有证据的处置状态 | 栏目数 | 含义 |
| --- | ---: | --- |
| 导航误抓已拦截 | 27 | 已阻止伪通知；栏目是否为空/旧路径/需专门选择器仍逐条待准入 |
| 已有修复或复核，仍部分通过 | 8 | 就业两个栏目、CSE 学院通知、科研处、人文社科处、研究生院、团委、国际教育 |
| 内容结构已核对，发布日期待确认 | 6 | 招生栏目只显示更新时间，不可当作已核验发布日期 |
| 原空结果，尚未后续逐栏复验 | 11 | 不知道是空栏目、模板不支持、动态加载、目标类型或权限问题 |
| 访问/链接受阻 | 7 | OA、答辩入口、两个继续教育入口、体育的两个索引/登录入口、数量经济旧链接 |
| 明确栏目权限限制 | 1 | 教务教学公示 1402；未证实登录能解决 |

7 个访问/链接项中，OA、答辩和两个继续教育入口共 4 个有 B3/B4 的较新受阻证据；体育两个入口和数量经济旧链接仅有原审计证据，当前状态未知。不能将它们全部宣称今天仍失败。

## 2. 原因分类

| 原因 | 具体表现 | 现有处理与剩余工作 |
| --- | --- | --- |
| 列表回退过宽 | 真空栏目、旧路径或未知模板被扫描成导航通知；原 27 项中 10 项还出现正文导航污染 | B1 收紧文章识别并拒绝导航；27 个快照候选从 1,178 降到 0。风险已拦截，不等于 27 栏目已支持 |
| 模板未适配 | 就业 details?id 链接不符合旧静态文章规则，标题/日期/正文容器不同 | B4 复用高级选择器，修复两个就业栏目；其他模板不能凭 HTTP 200 或非空判断适配 |
| 真实空/不支持尚难区分 | 其余 11 个原空列表缺少逐条新证据 | P2/P3 复核原页、栏目目标和动态机制；禁止导航回退补结果 |
| 正文形式和附件范围不足 | CSE 图片正文被当成不支持；软件教办六个 jpg 未提取 | B2 保留同源原图 URL，B3 提取明确附件；没有 OCR、自动图像下载或历史库补写 |
| 元信息提取错误 | 标题截断、正文小标题覆盖标题、把摘要公示期当发布日期 | B2/B4 按实际文章容器修复；招生更新日期的含义仍未确认 |
| 网络/TLS | OA 在 robots 阶段 TLS EOF；答辩入口 robots 连接超时 | 未取得正文时停止，不改 TLS 或绕访问规则；OA 曾在 B1 成功、B2/B3 又受阻，说明可达性有时间/路径变化，不能只归因解析器 |
| 重定向和失效入口 | 继续教育两个入口 HTTP 308 超过既有跳转上限；数量经济旧入口 404 | 核对官方新入口或站点侧跳转；没有证明循环根因，不提高上限伪造通过 |
| 权限/访问规则 | 教务无权限页、图书馆 robots 禁止、招生办 robots 403、附件验证码 | 保留合法入口并停止；认证/验证码/规则问题不是加选择器能解决的 |
| 证书有效期 | 附属高中 jdgz 原证据为证书有效期校验失败 | 站点/时钟/链路需核实，不能把 OA EOF 和证书有效期混为一类 |
| 验证器初判局限 | 图片 URL 加入纯文本后对照失败，部分标题容器未纳入对照，权限页被算空列表 | B4 使用同一 SHA 快照修正复核，保留初判；最终 15 部分通过、1 权限、3 受阻，不把离线时间当实时抓取时间 |

## 3. 附件、分页与其他未闭环项

原审计 **108 个栏目**带附件端点问题标签，仅说明未确认取得文件，不是 108 个附件损坏；不能把后续少量验证码样本外推到全部。B3 11 个端点为 9 验证码页、2 文件前缀；B4 14 个为 8 验证码页、5 文件前缀、1 robots 阻止。按实际附件完整 URL 去重及取最新有限记录的数量如下：

- CAPTCHA_REQUIRED：17 个端点。
- FILE_PREFIX_VERIFIED：7 个端点。
- ROBOTS_BLOCKED：1 个端点。

所有探测均未验证完整下载。HTML 验证码页可能返回 HTTP 206，所以 HTTP 状态成功不能当文件成功。原始各批次次数与去重端点数分别保留在 JSON，不相加当损坏数量。

原审计另有分页未配置 189 个栏目、列表日期缺失 77 个、编码替换字符 1 个，以及同 URL 113 组、同标题/日期 48 组重复候选。这些是可重叠问题/待验收范围，不计入 48 个失败的主因分类，也没有证据证明全部日常漏抓或数据库重复。食品学院替换字符已存在于响应原字节，不能靠盲目转码修好。B5 验证分页、增量和去重；本轮不执行 B5。

## 4. 60 个曾失败/权限栏目的完整台账

下表保留最近一次已有记录的时间，不表示重新检查。导航拦截项列中的旧失败状态没有被覆盖，处置栏另说明修复范围。逐次事件的原始原因、标签、时间、证据及输入 SHA 见 [机器台账](jlu-failure-summary.json)。

| # | 优先级／机构／栏目 | 栏目 URL | 处置状态 | 最近记录及时间 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 1 | P0／吉林大学网络安全学院／学院通知 | [https://cse.jlu.edu.cn/xytz.htm](https://cse.jlu.edu.cn/xytz.htm) | 已有修复或复核证据；仍为部分通过 | B3 实时：部分通过；2026-10-14T16:02:20+08:00 | [记录](jlu-fix-b3/live-existing-20261014/results/680c118ccf5bb51c.json) |
| 2 | P0／吉林大学 OA 校内通知／校内通知 | [https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577](https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577) | 访问或链接受阻 | B3 实时：失败；2026-10-14T16:02:55+08:00 | [记录](jlu-fix-b3/live-existing-20261014/results/cd2035ca91d0ee7c.json) |
| 3 | P1／研究生招生／录取公示 | [https://yzb.jlu.edu.cn/bszs/lqgs.htm](https://yzb.jlu.edu.cn/bszs/lqgs.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:34:57+08:00；复核 2026-10-14T16:47:31+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-doctor-publicity.json) |
| 4 | P1／研究生招生／招生公告 | [https://yzb.jlu.edu.cn/bszs/zsgg.htm](https://yzb.jlu.edu.cn/bszs/zsgg.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:34:51+08:00；复核 2026-10-14T16:47:30+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-doctor-notices.json) |
| 5 | P1／研究生招生／录取公示 | [https://yzb.jlu.edu.cn/index/lqgs.htm](https://yzb.jlu.edu.cn/index/lqgs.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:34:45+08:00；复核 2026-10-14T16:47:29+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-publicity.json) |
| 6 | P1／研究生招生／通知公告 | [https://yzb.jlu.edu.cn/index/tzgg.htm](https://yzb.jlu.edu.cn/index/tzgg.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:34:39+08:00；复核 2026-10-14T16:47:29+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-notices.json) |
| 7 | P1／研究生招生／录取公示 | [https://yzb.jlu.edu.cn/sszs/lqgs.htm](https://yzb.jlu.edu.cn/sszs/lqgs.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:35:10+08:00；复核 2026-10-14T16:47:33+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-master-publicity.json) |
| 8 | P1／研究生招生／招生公告 | [https://yzb.jlu.edu.cn/sszs/zsgg.htm](https://yzb.jlu.edu.cn/sszs/zsgg.htm) | 内容结构已核对；发布日期含义待确认 | B4 最终离线复核：部分通过；2026-10-14T16:35:04+08:00；复核 2026-10-14T16:47:31+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/yzb-master-notices.json) |
| 9 | P1／国际教育学院 / 留学生教育 / 留学生招生／公告通知 / NOTICE | [http://cie.jlu.edu.cn/ggtz.htm](http://cie.jlu.edu.cn/ggtz.htm) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:35:43+08:00；复核 2026-10-14T16:47:36+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/international.json) |
| 10 | P1／社会科学研究院／通知公告 | [https://hssra.jlu.edu.cn/tzgg1.htm](https://hssra.jlu.edu.cn/tzgg1.htm) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:35:22+08:00；复核 2026-10-14T16:47:34+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/hssra.json) |
| 11 | P1／学生就业创业指导与服务中心／公示 | [https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:34:22+08:00；复核 2026-10-14T16:47:27+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/employment-publicity.json) |
| 12 | P1／学生就业创业指导与服务中心／通知公告 | [https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg](https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:34:00+08:00；复核 2026-10-14T16:47:27+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/employment-notices.json) |
| 13 | P1／科研院 / 科技管理办公室／通知公告 | [https://kjc.jlu.edu.cn/tzgg.htm](https://kjc.jlu.edu.cn/tzgg.htm) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:35:15+08:00；复核 2026-10-14T16:47:33+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/kjc.json) |
| 14 | P1／研究生院 / 学位办公室 / 研究生培养办公室 / 研究生管理办公室 / 研究生工作部 / 研究生综合办公室／通知公告 | [https://yjsy.jlu.edu.cn/tzgg.htm](https://yjsy.jlu.edu.cn/tzgg.htm) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:35:29+08:00；复核 2026-10-14T16:47:35+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/graduate-school.json) |
| 15 | P1／团委／通知公告 | [https://youth.jlu.edu.cn/index/tzgg.htm](https://youth.jlu.edu.cn/index/tzgg.htm) | 已有修复或复核证据；仍为部分通过 | B4 最终离线复核：部分通过；2026-10-14T16:35:36+08:00；复核 2026-10-14T16:47:35+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/youth.json) |
| 16 | P1／本科生院 / 吉林大学本科生院／教学公示 | [https://jwc.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1402](https://jwc.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1402) | 明确栏目权限限制 | B4 最终离线复核：需认证；2026-10-14T16:34:28+08:00；复核 2026-10-14T16:47:28+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/jwc-teaching-publicity.json) |
| 17 | P1／继续教育学院（培训学院 / 继续教育 / 继续教育招生／通知公告 | [https://dec.jlu.edu.cn/html/tzgg1](https://dec.jlu.edu.cn/html/tzgg1) | 访问或链接受阻 | B4 最终离线复核：失败；2026-10-14T16:36:19+08:00；复核 2026-10-14T16:47:37+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/continuing-conditional.json) |
| 18 | P1／继续教育学院（培训学院 / 继续教育 / 继续教育招生／通知公告 | [https://dec.jlu.edu.cn/html/xljy/tzgg](https://dec.jlu.edu.cn/html/xljy/tzgg) | 访问或链接受阻 | B4 最终离线复核：失败；2026-10-14T16:36:26+08:00；复核 2026-10-14T16:47:37+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/continuing-academic-conditional.json) |
| 19 | P1／研究生院 / 学位办公室 / 研究生培养办公室 / 研究生管理办公室 / 研究生工作部 / 研究生综合办公室／答辩公告 | [https://yjs.jlu.edu.cn/gsapp/sys/dbgsglappecupl/*default/index.do](https://yjs.jlu.edu.cn/gsapp/sys/dbgsglappecupl/*default/index.do) | 访问或链接受阻 | B4 最终离线复核：失败；2026-10-14T16:35:50+08:00；复核 2026-10-14T16:47:37+08:00 | [记录](jlu-fix-b4/review-final-20261014/results/defense-conditional.json) |
| 20 | P2／白求恩第三临床医学院／通知公告 | [https://www.zrlyyy.com/tongzhiy_g7yU_91.html](https://www.zrlyyy.com/tongzhiy_g7yU_91.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:18+08:00 | [记录](jlu-audit-evidence/results/fd4944826664c69d.json) |
| 21 | P2／白求恩第三临床医学院／关于因停电暂停官网服务的通知 2026.05.08 | [https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html](https://www.zrlyyy.com/wujia_detail_g7yU_62/177728.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:20+08:00 | [记录](jlu-audit-evidence/results/fe74f8a02d7a2d3b.json) |
| 22 | P2／白求恩第三临床医学院／信息公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_59.html](https://www.zrlyyy.com/wujiaquery_g7yU_59.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:21+08:00 | [记录](jlu-audit-evidence/results/9230d60e0f53f653.json) |
| 23 | P2／白求恩第三临床医学院／招生信息 | [https://www.zrlyyy.com/wujiaquery_g7yU_60.html](https://www.zrlyyy.com/wujiaquery_g7yU_60.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:22+08:00 | [记录](jlu-audit-evidence/results/af1ca3ec1c4af90d.json) |
| 24 | P2／白求恩第三临床医学院／招标采购公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_61.html](https://www.zrlyyy.com/wujiaquery_g7yU_61.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:23+08:00 | [记录](jlu-audit-evidence/results/c44f268c159ec7c9.json) |
| 25 | P2／白求恩第三临床医学院／通知公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_62.html](https://www.zrlyyy.com/wujiaquery_g7yU_62.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T13:44:13+08:00 | [记录](jlu-audit-evidence/results/3315d5f7eb5985d6.json) |
| 26 | P2／白求恩第三临床医学院／调研公告 | [https://www.zrlyyy.com/wujiaquery_g7yU_864.html](https://www.zrlyyy.com/wujiaquery_g7yU_864.html) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:01:25+08:00 | [记录](jlu-audit-evidence/results/c85b8be444d2c98b.json) |
| 27 | P2／药学院／学院通知 | [https://yxy.jlu.edu.cn/wz-list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1209](https://yxy.jlu.edu.cn/wz-list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1209) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:02:00+08:00 | [记录](jlu-audit-evidence/results/53c4ac131f1cc0ef.json) |
| 28 | P2／汽车工程学院／招生信息 | [https://auto.jlu.edu.cn/zsxx.htm](https://auto.jlu.edu.cn/zsxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:54:03+08:00 | [记录](jlu-audit-evidence/results/8e958c4c25bd5b90.json) |
| 29 | P2／公共计算机教学与研究中心／通报通知 | [https://ccfe.jlu.edu.cn/djgz/tbtz.htm](https://ccfe.jlu.edu.cn/djgz/tbtz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:54:14+08:00 | [记录](jlu-audit-evidence/results/4adc4212e4ac27b5.json) |
| 30 | P2／吉林大学网络安全学院／本科教学通知 | [https://cse.jlu.edu.cn/bksjy/bkjxtz.htm](https://cse.jlu.edu.cn/bksjy/bkjxtz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:05:53+08:00 | [记录](jlu-audit-evidence/results/0ca7e7c9518e54f4.json) |
| 31 | P2／吉林大学网络安全学院／研究生通知 | [https://cse.jlu.edu.cn/yjsjy/yjstz.htm](https://cse.jlu.edu.cn/yjsjy/yjstz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:05:55+08:00 | [记录](jlu-audit-evidence/results/8882a3f2c6422bb7.json) |
| 32 | P2／通信工程学院／招聘信息 | [https://dce.jlu.edu.cn/tzgg/zpxx.htm](https://dce.jlu.edu.cn/tzgg/zpxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:55:32+08:00 | [记录](jlu-audit-evidence/results/fae607a04b9c9b80.json) |
| 33 | P2／通信工程学院／招生信息 | [https://dce.jlu.edu.cn/tzgg/zsxx.htm](https://dce.jlu.edu.cn/tzgg/zsxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:55:34+08:00 | [记录](jlu-audit-evidence/results/46e3c78121198557.json) |
| 34 | P2／电子科学与工程学院、集成电路学院／实验室安全通知公告 | [https://ee.jlu.edu.cn/sys_/sysaqtzgg.htm](https://ee.jlu.edu.cn/sys_/sysaqtzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:56:11+08:00 | [记录](jlu-audit-evidence/results/8cc2288150cd9e37.json) |
| 35 | P2／历史文化学院／通知公告 | [https://hac.jlu.edu.cn/dqgz/tzgg.htm](https://hac.jlu.edu.cn/dqgz/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:40:09+08:00 | [记录](jlu-audit-evidence/results/10b02b68c1e98da7.json) |
| 36 | P2／历史文化学院／通知公告 | [https://hac.jlu.edu.cn/gjjl/tzgg.htm](https://hac.jlu.edu.cn/gjjl/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:40:11+08:00 | [记录](jlu-audit-evidence/results/00df1137578aec37.json) |
| 37 | P2／历史文化学院／就业信息 | [https://hac.jlu.edu.cn/zsyjy/jyxx.htm](https://hac.jlu.edu.cn/zsyjy/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:56:54+08:00 | [记录](jlu-audit-evidence/results/746d87b2613e6e22.json) |
| 38 | P2／生命科学学院／通知公告 | [https://life.jlu.edu.cn/xsgz/yjsgl/tzgg.htm](https://life.jlu.edu.cn/xsgz/yjsgl/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:58:26+08:00 | [记录](jlu-audit-evidence/results/4e030ec36a90ae60.json) |
| 39 | P2／数学学院／招生信息 | [https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm](https://math.jlu.edu.cn/zsjy/bkszs/zsx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:58:48+08:00 | [记录](jlu-audit-evidence/results/f80ea8ffb1777c55.json) |
| 40 | P2／东北亚学院、东北亚研究院／就业信息 | [https://nasa.jlu.edu.cn/bksjy/jyxx.htm](https://nasa.jlu.edu.cn/bksjy/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:58:57+08:00 | [记录](jlu-audit-evidence/results/1ce2bf7487f4e614.json) |
| 41 | P2／东北亚学院、东北亚研究院／院办通知 | [https://nasa.jlu.edu.cn/xzgz/ybtz.htm](https://nasa.jlu.edu.cn/xzgz/ybtz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:59:20+08:00 | [记录](jlu-audit-evidence/results/3e37d545072d1396.json) |
| 42 | P2／东北亚学院、东北亚研究院／就业信息 | [https://nasa.jlu.edu.cn/yjsjy/jyxx.htm](https://nasa.jlu.edu.cn/yjsjy/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:59:22+08:00 | [记录](jlu-audit-evidence/results/bdfdf1b773403b4e.json) |
| 43 | P2／物理学院／就业信息 | [https://phy.jlu.edu.cn/rcpy/yjsjy/jyxx.htm](https://phy.jlu.edu.cn/rcpy/yjsjy/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:59:50+08:00 | [记录](jlu-audit-evidence/results/5a4d3e884db0df27.json) |
| 44 | P2／外国语言文化学院／党务公示 | [https://sflc.jlu.edu.cn/dzgz/dwgs.htm](https://sflc.jlu.edu.cn/dzgz/dwgs.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:00:05+08:00 | [记录](jlu-audit-evidence/results/0f03bd864044d026.json) |
| 45 | P2／外国语言文化学院／就业信息 | [https://sflc.jlu.edu.cn/xtgz/jyxx.htm](https://sflc.jlu.edu.cn/xtgz/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:00:08+08:00 | [记录](jlu-audit-evidence/results/4bfc23b0fadd94b7.json) |
| 46 | P2／公共外交学院／通知公告 | [https://sipa.jlu.edu.cn/hzjl/tzgg.htm](https://sipa.jlu.edu.cn/hzjl/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:00:53+08:00 | [记录](jlu-audit-evidence/results/0f712420c5c4200a.json) |
| 47 | P2／哲学社会学院／就业信息 | [https://zsy.jlu.edu.cn/yjsjy/jyxx.htm](https://zsy.jlu.edu.cn/yjsjy/jyxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:02:25+08:00 | [记录](jlu-audit-evidence/results/b4ad9576f8de3377.json) |
| 48 | P2／体育学院／校内通知部门索引 | [http://isc.jlu.edu.cn/oaindex.htm](http://isc.jlu.edu.cn/oaindex.htm) | 访问或链接受阻 | 原始审计：失败；2026-10-13T13:59:30+08:00 | [记录](jlu-audit-evidence/results/6a839d15a4049e18.json) |
| 49 | P2／体育学院／校内通知 | [https://oa.jlu.edu.cn/defaultroot/login.jsp](https://oa.jlu.edu.cn/defaultroot/login.jsp) | 访问或链接受阻 | 原始审计：失败；2026-10-13T13:59:33+08:00 | [记录](jlu-audit-evidence/results/c0bb9a0353fb16e3.json) |
| 50 | P3／测试科学实验中心／通知通告 | [https://cszx.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1008](https://cszx.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1008) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T14:06:08+08:00 | [记录](jlu-audit-evidence/results/9cfc1755cb34af9d.json) |
| 51 | P3／吉林大学附属中学／通知公告 | [https://fszx.jlu.edu.cn/xwzx/tzgg.htm](https://fszx.jlu.edu.cn/xwzx/tzgg.htm) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T13:49:38+08:00 | [记录](jlu-audit-evidence/results/aec68cedee883bf7.json) |
| 52 | P3／后勤服务集团／通知公告 | [https://hqserver.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1023](https://hqserver.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1023) | 原空结果；未获后续逐栏复验 | 原始审计：失败；2026-10-13T13:38:58+08:00 | [记录](jlu-audit-evidence/results/918d011e17e42822.json) |
| 53 | P3／边疆考古研究中心／通知公告 | [http://bjkg.jlu.edu.cn/tzgg.htm](http://bjkg.jlu.edu.cn/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:45:18+08:00 | [记录](jlu-audit-evidence/results/dbe97ad67104327e.json) |
| 54 | P3／高等教育研究所／招生信息 | [http://gjs.jlu.edu.cn/zsjy/zsxx.htm](http://gjs.jlu.edu.cn/zsjy/zsxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:02:51+08:00 | [记录](jlu-audit-evidence/results/0a00088dd271056d.json) |
| 55 | P3／吉林大学国家发展与安全研究院／通知公告 | [http://indss.jlu.edu.cn/rcpy/tzgg.htm](http://indss.jlu.edu.cn/rcpy/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:47:37+08:00 | [记录](jlu-audit-evidence/results/8a5615f2d971146e.json) |
| 56 | P3／白求恩医学部／研究生院通知 | [http://jdyxb.jlu.edu.cn/bqeyjsbgs/yjsjy/yjsytz.htm](http://jdyxb.jlu.edu.cn/bqeyjsbgs/yjsjy/yjsytz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:07:03+08:00 | [记录](jlu-audit-evidence/results/f0c7249752019d50.json) |
| 57 | P3／哲学基础理论研究中心／中心通知 | [http://pftheory.jlu.edu.cn/zxxw1/zxtz.htm](http://pftheory.jlu.edu.cn/zxxw1/zxtz.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:05:04+08:00 | [记录](jlu-audit-evidence/results/dccdc07e027f15b6.json) |
| 58 | P3／博士后工作办公室／招聘信息 | [https://bsh.jlu.edu.cn/zpxx.htm](https://bsh.jlu.edu.cn/zpxx.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T14:05:43+08:00 | [记录](jlu-audit-evidence/results/064a4d605439a05e.json) |
| 59 | P3／智能仪器与测控技术研究所／通知公告 | [https://iiimct.jlu.edu.cn/xwzx/tzgg.htm](https://iiimct.jlu.edu.cn/xwzx/tzgg.htm) | 导航误抓已拦截；来源尚未准入 | 原始审计：失败；2026-10-13T13:48:11+08:00 | [记录](jlu-audit-evidence/results/d631ccd9f5224213.json) |
| 60 | P3／数量经济研究中心／中心通知 | [http://jlucqe.jlu.edu.cn/list.php?SID=1](http://jlucqe.jlu.edu.cn/list.php?SID=1) | 访问或链接受阻 | 原始审计：失败；2026-10-13T14:03:36+08:00 | [记录](jlu-audit-evidence/results/86da28c024119c6b.json) |

## 5. 站点发现阶段另有 15 个受阻入口

这是站点入口口径，与上面的栏目台账有重叠，不能相加。以下均为 2026-10-13 原始发现记录，未逐站重新访问。多数旧异常丢失细节，不能擅自认定为 DNS、超时或证书问题。

| 机构 | 入口 | 当时原因分类 | 时间 |
| --- | --- | --- | --- |
| 保密工作办公室 | [https://bmb.jlu.edu.cn/](https://bmb.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:33:53+08:00 |
| 学校纪检监察机构 | [https://jjw.jlu.edu.cn/](https://jjw.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:33:59+08:00 |
| 党委信访工作办公室、信访工作办公室 | [https://xinfang.jlu.edu.cn/](https://xinfang.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:34:07+08:00 |
| 党委组织部 | [http://zzb.jlu.edu.cn/](http://zzb.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:49:12+08:00 |
| 机关党委 | [https://jgdw.jlu.edu.cn/](https://jgdw.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:34:20+08:00 |
| 财务处 | [https://cw.jlu.edu.cn/](https://cw.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:35:16+08:00 |
| 审计处 | [https://sjc.jlu.edu.cn/](https://sjc.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:35:22+08:00 |
| 实验室管理处 | [https://lab.jlu.edu.cn/](https://lab.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:37:23+08:00 |
| 校园卡服务中心 | [https://xyk.jlu.edu.cn/](https://xyk.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:38:01+08:00 |
| 图书馆 | [http://lib.jlu.edu.cn/](http://lib.jlu.edu.cn/) | robots 明确禁止 | 2026-10-13T13:49:18+08:00 |
| 白求恩第一临床医学院 | [https://www.jdyy.cn/](https://www.jdyy.cn/) | 服务器断开响应 | 2026-10-13T13:44:05+08:00 |
| 理论法学研究中心 | [http://www.legal-theory.org/](http://www.legal-theory.org/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:49:20+08:00 |
| 本科招生 | [http://zsb.jlu.edu.cn/](http://zsb.jlu.edu.cn/) | HTTP 403 访问限制 | 2026-10-13T13:49:34+08:00 |
| 吉林大学 OA 校内通知 | [https://oa.jlu.edu.cn/](https://oa.jlu.edu.cn/) | robots 不可取得；原异常细节不足 | 2026-10-13T13:48:46+08:00 |
| 长春吉大附中实验学校 | [https://jdgz.jlu.edu.cn/](https://jdgz.jlu.edu.cn/) | 证书有效期校验失败 | 2026-10-13T13:49:41+08:00 |

证据：[完整发现记录](jlu-audit-evidence/discovery.json)。另有 44 个入口未发现栏目、305 条机构官网未知，它们是覆盖发现缺口，不是已证实抓取失败或无需适配。

## 6. 建议处理顺序

1. P0：OA 的默认访问/TLS 与实际 Cloud 路径先分别定位；既有来源持续回归。保留 B1 成功与 B2/B3 失败的不同时间证据。
2. P1：先验收已修复的就业、学工、科研等内容的分页/增量，再确认六个招生日期语义。教学公示、答辩和继续教育分别按权限、网络和跳转问题处理。
3. P2：27 个导航风险虽然已拦截，仍须逐条确认真空/旧路径/新模板；先复核学院和医院空列表。不要重新放开导航回退。
4. P3：处理其他空列表、失效官方链接和站点发现缺口；robots/验证码限制保留，不绕过。

早期回归日志也出现过环境变量导致的 4 个默认设置断言失败及同期代码变化中的 6 个 HTTP 诊断测试失败，后续完整回归已通过。它们不计为网站失败；B4 最终结果为 365 passed、1 skipped，跳过的 PostgreSQL 集成环境未配置不能算 Cloud 生产验收。

## 7. 依据与限制

依据：[原审计](JLU_SITE_AUDIT.md)、[B0＋B1](JLU_SITE_FIX_B0_B1_REPORT.md)、[B2](JLU_SITE_FIX_B2_REPORT.md)、[B3](JLU_SITE_FIX_B3_REPORT.md)、[B4](JLU_SITE_FIX_B4_REPORT.md)。原审计初步清单在 [initial-validation-results](jlu-audit-evidence/initial-validation-results.json)，未与最终去重清单重复累计。本汇总没有重写旧结论或声称未复验的来源已恢复。

本汇总仅按这些批次已保存的栏目 URL 建立台账，不是全校当前故障率、当前失败总数、Cloud 健康检查或数据库修复任务。所有候选正式准入状态仍按原报告，未新增支持。
