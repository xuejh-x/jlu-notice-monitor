# 吉林大学通知适配修复：B2 验证报告

日期：2026-10-14（Asia/Shanghai）。状态：B2 已完成，停在本批交付点。B3–B7 尚未执行，没有新增正式来源。

## 1. 结果

本批修复校级完整标题、VSB 列表发布日期、详情元信息日期及图片链接保留，并补上发布日期纠正后的持久化更新。

- 隔离基线 **269 passed、1 skipped**；最终后端全量回归 **300 passed、1 skipped**。新增 31 项测试。跳过项为未配置可丢弃 PostgreSQL 测试库；不代表 Cloud 生产验收。
- 现有 `NoticeContent` 渲染测试 **3 passed**；正文仍为 React 转义显示的纯文本，未新增 HTML 执行或远程图片自动加载。
- 68 个历史栏目/引用重放，列表 URL 集合全部保持一致；27 个导航误抓控制仍为零候选。11 个原通过样本的标题、发布日期、解析接受状态及原有文本保持一致，其中五个补充了原先丢失的正文图片 URL。
- 实时复验 11 个栏目：**完全通过 0、部分通过 10、失败 1、需认证 0、未检测 0**。剩余附件与分页问题没有隐藏；失败项是今日 OA robots 获取时的 TLS EOF。
- 三个重点原文实时复核均符合本批预期：校级完整标题、学工发布日期、CSE 原始图片链接。最终版本再次离线重放这三份新快照，结果相同。
- 食品学院响应原始字节本身已含三处 UTF-8 替换字符；本批没有盲目转码或编造修复。

正式 `sources.yaml`、SQLite schema、URL/附件 DTO、Cloud / Desktop 策略及安全校验保持不变。没有修改正式数据库、清理历史通知、安装客户端、改系统网络、提交 GitHub 或发布 Release。

## 2. 变更与规则

相对本批基线，应用代码只改三个文件，差异见 [application-changes.patch](jlu-fix-b2/application-changes.patch)。用户原有未提交改动和 B0＋B1 修复均保留。

| 文件 | 变更 |
| --- | --- |
| `backend/app/parsers/html.py` | 优先使用明确标题节点；`.nr_title` 去除作者、时间、点击等元信息；补 `.art-tit h3`、`.detail-title`、`.detail-tit h4` 等实际模板。无明确上下文的全局 h1/栏目标题不能覆盖列表真实标题。 |
| 同上 | 列表先取完整 title 属性或标题子节点，避免日期、摘要混进标题。独立日/年月节点组合成日期，补纯日期 span；无明确日历时不从摘要/标题中推断发布日期。详情只允许文章元信息或标准 published-time 元数据覆盖列表日期，不再使用全页第一个日期。 |
| 同上 | 正文容器按模板优先级选择，取消以 20 字符决定是否改选外层容器。保留正文内符合规则的原始图片 URL，图片型正文可以产生真实内容引用；确为空、登录页、导航页和不受支持的图片仍被拒绝。 |
| `backend/app/sources/generic.py` | 显式正文选择器也使用相同的图片引用保留与正文检查，避免普通适配器和预览行为不同。 |
| `backend/app/crawler/runner.py` | 对已存在来源关系及规范原文 URL，非空发布日期变化即使正文 hash 不变也能更新；不会因日期纠正创建第二条通知。缺失日期不抹掉已有日期，其他原文 URL 的来源关系不能改写规范通知日期。 |

正文保持现有 **纯文本契约**。合法图片引用目前限定同源 HTTP(S) 的 jpg/jpeg/png/gif/webp，保留原路径及查询参数、按出现顺序去重；不接收凭据 URL、data/javascript、跨源图片、SVG 或明显 1px 跟踪图片。正文中的图片 URL 是实际原始内容引用，没有用生成文字、复制标题或导航填充正文。

图片 URL 在现有 API、SQLite 及阅读组件中作为普通文本保留，可复制，亦可通过现有“原网页”入口查看。**本批没有实现内嵌图片、OCR 或自动图片下载，也未验证图片文件端点可下载。** 外部 CDN、无扩展名图片等未知格式继续报未支持，不能当成已适配。正文图片没有混入附件列表，附件扩展留待 B3。

发布日期规则覆盖跨年、闰日、非法日期、置顶旧日期、摘要公示期、活动/报名截止日期及缺失日期。明确发布元信息可以纠正列表日期；没有发布证据时保持列表日期或缺失，不使用抓取当天补日期。

## 3. 隔离、fixtures 与数据保护

[baseline-manifest.json](jlu-fix-b2/baseline-manifest.json)和 [final-manifest.json](jlu-fix-b2/final-manifest.json)保存 revision、工作区文件 hash、时间和隔离副本位置。沿用独立副本测试入口，新增 `--batch b2`，证据写入 `docs/jlu-fix-b2/`；不覆盖 B0＋B1 结果。隔离副本不复制正式 `.env`、SQLite 或资料目录，入口断言有效数据库为 `sqlite://`。

[四组脱敏 fixtures](../backend/tests/fixtures/jlu_b2/manifest.json)来自已保存的校级、学工、CSE、食品学院原网页，保留必要标题、日期、图片链接和结构；无关正文及个人信息作最小处理。原网页 URL、原抓取时间及 SHA-256 保留，结构 fixture 不冒充新的联网结果。

新增测试验证：

- 校级截断标题恢复且不包含作者/日期；学工 5941 的发布日期取 2026-10-13，摘要的 2026-10-12 不能成为发布日期。
- 食品学院标题不混入日历及摘要；社科、国际教育已观察到的元信息结构继续支持。
- 图片型、短文本、文字与多图混合、重复图片、带查询参数图片，以及非法/跨源/未支持图片的处理。
- Static 与 Generic 自动/显式选择器的正文结果一致，只请求详情，不请求图片。
- 日期单独更新、随后标题/图片内容更新、重复运行仍只有一条通知；notice ID、来源关系、已读、收藏及其更新时间保持不变。缺失日期及其他来源 URL 不能覆盖规范记录日期。
- 已保存图片 URL 能通过现有详情 DTO 序列化，保持字符串，未改变附件字段或正文安全边界。

这些是隔离验证，不是对正式历史数据执行迁移。已有错误标题/日期是否自动被下一轮识别，仍受现有列表增量检查影响；**本批没有强制重抓或批量回写历史库**。

## 4. 历史快照对照

[before](jlu-fix-b2/replay-before.json)、[after](jlu-fix-b2/replay-after.json)各执行 145 次快照 SHA-256 校验，覆盖 68 条栏目/引用记录；分组有交集。原抓取时间与本次重放时间分开记录，纯通用解析重放不联网、不导入数据库模块。[汇总](jlu-fix-b2/replay-summary.json)记录 11 个正向控制和图片补充情况。

| 控制 | B1 结果 | B2 结果 |
| --- | --- | --- |
| [校级 58176](https://www.jlu.edu.cn/info/1095/58176.htm) | 标题以省略号结束 | 恢复到“人员名单公示”，排除元信息 |
| [学工 5941](https://xsc.jlu.edu.cn/info/1048/5941.htm) | 列表可能取摘要公示起始日 | 独立日历节点得到 2026-10-13 |
| [CSE 1381](https://cse.jlu.edu.cn/info/1003/1381.htm) | 图片型正文报未支持 | 保留同源原图 URL，发布日期 2024-07-18 |
| 11 个原通过样本 | 正常接受 | 标题、日期、原有文本与接受状态保持；五个补正文图片引用 |
| 27 个导航疑似栏目 | B1 已阻止伪候选 | 仍为零伪候选 |

三份原引用/导航详情的旧“日期”变为缺失：外校招生单篇引用两份及 `bjkg` 首页一份。它们缺乏本批认可的文章发布元信息，旧全页日期推断不再保留；不是三个正式来源回归失败。未对其实施新增适配。

## 5. 实时复验及具体证据

栏目复验窗口为 **15:37:07–15:38:17**；重点复核及原始字节探测为 **15:38:47–15:38:53**，均为 2026-10-14 北京时间。

串行、同源至少 1.2 秒、全局至少 1 秒，并遵守更长 robots crawl-delay。单请求超时 12 秒，瞬时超时/502/503/504 最多两次尝试；401/403/429、robots 禁止及确定性证书失败不反复请求。OA 此次 EOF 在 robots 阶段即停止，不尝试绕过访问规则。没有导入旧 HTTP 缓存。

11 个首屏、19 个详情、9 个附件端点和9 个下一页形成 **57 条请求缓存记录、55 条实际 HTTP 响应记录**；含 robots 与受阻请求，不能当成 57 个网站。补充三个重点详情和一个原始字节探测，含 robots 另有 8 条 HTTP 响应记录，没有请求正文图片文件。

| 栏目 | 列表数 | 自动结论 | 仍需处理 |
| --- | ---: | --- | --- |
| [CCST 教学通知](https://ccst.jlu.edu.cn/rcpy/bksjy/jxtz.htm) | 10 | 部分通过 | 附件端点、分页 |
| [CSE 本科教学](https://cse.jlu.edu.cn/bkjxtz.htm) | 3 | 部分通过 | 动态分页/历史范围 |
| [CSE 学院通知](https://cse.jlu.edu.cn/xytz.htm) | 8 | 部分通过 | 图片链接已保留；分页；另有旧审计容器误报 |
| [软件教办](https://csw.jlu.edu.cn/index/jbtz.htm) | 15 | 部分通过 | 图片附件未提取、下载端点、分页 |
| [软件学院](https://csw.jlu.edu.cn/index/xytz_.htm) | 15 | 部分通过 | 附件验证不完整、分页 |
| [创新创业](https://cxcyjyxy.jlu.edu.cn/index/tzgg.htm) | 15 | 部分通过 | 附件端点、分页 |
| [教务通知](https://jwc.jlu.edu.cn/zxzx/tzgg.htm) | 15 | 部分通过 | 附件端点、分页 |
| [OA 校内通知](https://oa.jlu.edu.cn/defaultroot/PortalInformation!jldxList.action?channelId=179577) | 0 | 失败 | robots 获取发生 TLS EOF；本次没有详情验收 |
| [校级通知](https://www.jlu.edu.cn/index/tzgg.htm) | 20 | 部分通过 | 附件端点、分页；另有标题恢复后的旧审计误报 |
| [学工通知](https://xsc.jlu.edu.cn/index/tzgg.htm) | 10 | 部分通过 | 日期已纠正；附件端点、分页 |
| [食品学院教学信息](https://spxy.jlu.edu.cn/bksjy/jxxx.htm) | 10 | 部分通过 | 返回内容已有替换字符；附件、分页 |

逐栏 URL、检查时间、代码指纹、列表/详情/附件/分页见 [兼容 CSV](jlu-fix-b2/live-20261014/jlu-compatibility-report.csv)、[results.json](jlu-fix-b2/live-20261014/results.json)、[requests.json](jlu-fix-b2/live-20261014/requests.json)和 [运行指纹](jlu-fix-b2/live-20261014/validation-code-manifest.json)。该 CSV 的站点/机构发现元数据沿用原审计时间，不能解释为本轮访问了全校 164 个主机。

重点详情见 [spot-results.json](jlu-fix-b2/spot-20261014/spot-results.json)，每条含 URL、时间、原快照 hash 及解析结果。最终补充“无文章上下文的站点 h1 不覆盖列表标题”及“元信息中的活动/报名时间不当成发布时间”防护；[最终重放](jlu-fix-b2/spot-final-replay.json)以最终代码处理这三份新快照，结果相同，未伪造新的抓取时间。补充探测入口也增加了代码指纹保护，[旧目录恢复检查](jlu-fix-b2/probe-resume-guard.json)证实缺少版本记录时会在联网前拒绝混用。

### 不能直接当缺陷或成功的结果

[manual-review.json](jlu-fix-b2/manual-review.json)保留人工复核层，不改写自动结果：

- CSE 的 `BODY_CONTAINER_FALLBACK` 是旧审计用 20 字符判断正文容器造成的误报；实际 `.v_news_content` 存在并包含原图，解析器没有整页回退。
- 校级 `TITLE_MISMATCH / TITLE_NOT_IN_DETAIL_HEADING` 是旧审计忽略 `.nr_title`、把列表省略号当标题内容造成的误报。恢复后的标题和原文标题相同。
- OA 昨日曾成功不代表今日成功。今日 robots TLS EOF 有完整异常链；专用解析器离线回归通过，**网络受阻与解析兼容性分别记录**，实际 Cloud 生产仍未验收。
- [食品学院原始字节证据](jlu-fix-b2/spot-20261014/encoding.json)：响应无 charset header，meta 为 UTF-8；35,470 字节可严格 UTF-8 解码，但已含三个 `EF BF BD` 序列。问题在本机解码前已存在，保留告警，不尝试无依据的 GBK/UTF-8 来回转码。
- 附件端点返回说明/限制页，或附件未全检，仍不能直接判定文件损坏；图片 URL 保留也不能宣称图片端点下载成功。

## 6. 保留事项与下一批

[preservation.json](jlu-fix-b2/preservation.json)确认原审计 1,449 个受保护文件及 B0＋B1 报告不变。正式来源 YAML hash 仍为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。未修改源码中的 Cloud policy、source ownership/identity、私网/连接地址校验、TLS 工厂、来源配置或 SQLite schema。

本批仅对 11 个栏目做实时复验；原审计其余对象没有重新联网验收。原全校清单和兼容 CSV 不改写，也不提高全校通过率。UI、路由、筛选参数、auto-read 和附件 DTO 均未改动；只对现有正文组件运行针对性测试，没有声称完成新的 UI/客户端验收。

下一批建议 **B3：附件提取和下载页识别**，优先软件教办六个 jpg 附件、下载端点分类及 OA 专用附件；OA 当前网络阻塞独立保留，不改安全校验换取成功。B4 才做高价值新来源准入，B5 再验证分页、增量去重及真实 Cloud。当前完成 B2 后停止。

## 7. 复现入口

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py final --batch b2
.\backend\.venv\Scripts\python.exe backend/scripts/replay_jlu_b1.py --batch b2 --output docs/jlu-fix-b2/replay-after.json
```

重做实时检查请用新的证据目录；同目录恢复仅允许代码指纹不变，避免旧失败或成功缓存冒充新版本结果：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/audit_jlu_sites.py validate `
  --output-dir docs/jlu-fix-b2/next-live-run --input-dir docs/jlu-audit-evidence `
  --column-url https://cse.jlu.edu.cn/xytz.htm
.\backend\.venv\Scripts\python.exe backend/scripts/probe_jlu_b2.py --output-dir docs/jlu-fix-b2/next-spot-run
```

测试原始结果：[baseline tests](jlu-fix-b2/baseline-tests.log)、[final tests](jlu-fix-b2/final-tests.log)、[正文渲染测试](jlu-fix-b2/frontend-content-tests.json)。最终文件与证据校验见 [acceptance.json](jlu-fix-b2/acceptance.json)。
