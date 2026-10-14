# 吉林大学通知适配修复：B3 验证报告

日期：2026-10-14（Asia/Shanghai）。状态：B3 已完成并停止；B4–B7 尚未执行。未新增或启用正式来源。

## 1. 结果

已补齐软件教办目标通知的六个 jpg 附件，限定自动提取范围，保留链接参数及附件 DTO，并把有限下载检查改为有明确范围的前缀分类。

- 实施前隔离基线：**300 passed，1 skipped**；最终后端全量：**350 passed，1 skipped**。新增 50 项测试。跳过项为未配置可丢弃 PostgreSQL 测试库，不代表 Cloud 生产验收。
- [软件教办 8548](https://csw.jlu.edu.cn/info/1095/8548.htm)附件由 **0 补为 6**，文件名、顺序、完整 `owner / wbfileid / urltype` 参数均与原文一致。六个文件均为明确附件列表中的 jpg。
- 历史 68 个栏目/引用的列表 URL 集合、抽样标题、日期、正文 hash 和接受状态均保持一致。附件差异只有上述六个新增，没有移除旧样本附件；27 个导航控制仍无伪候选。
- 实时检查 **11 个附件端点**：**2 个文件/容器前缀已验证、9 个验证码页、完整下载验证 0**。HTTP 206 也可能是验证码 HTML，不能作为下载成功依据。
- 既有 8 个栏目实时回归：**完全通过 0、部分通过 7、失败 1、需认证 0、未检测 0**。失败项为 OA robots 获取时的 TLS EOF；本次未执行真实 OA 附件 POST。

“六个附件提取正确”与“六个附件可自动下载”是两个结论。本批只确认前者；验证码限制没有绕过，原始合法入口仍保留。原全校审计清单及通过率没有改写。

## 2. 代码变更与可复用规则

应用代码相对本批基线改动四个既有文件，另加一个审计用分类服务。差异见 [application-changes.patch](jlu-fix-b3/application-changes.patch)，指纹见 [final-manifest.json](jlu-fix-b3/final-manifest.json)。

| 文件 | 改动 |
| --- | --- |
| `backend/app/parsers/html.py` | 文档类链接保留正文内的既有识别能力。图片、rar/7z、ppt/pptx、csv/txt 等扩展只在明确附件上下文中识别；正文之外只扫描文章范围内的明确附件。排除导航、页脚、非法 href 和凭据 URL。 |
| `backend/app/sources/base.py` | 正式静态适配器返回详情前过滤显式私网/localhost 等不允许的附件地址；过滤后真正无内容无附件的详情继续拒绝。 |
| `backend/app/sources/generic.py` | 附件按完整 URL 去重，保留既有 local/cloud URL 安全策略及显式允许私网的私有来源行为；显式选择器排除导航/非法链接，过滤后空详情不得假成功。 |
| `backend/app/sources/oa_public.py` | 保留原专用编码协议及 URL 构造。4xx、验证码/HTML 等确定性编码响应错误立即停止；临时 5xx 仍受既有重试上限约束，证书错误保留异常链并立即停止。 |
| `backend/app/services/attachment_validation.py` | 只分类给定的有限字节前缀，不联网、不执行文件。区分文件签名、HTML/验证码/认证/校内网限制页、HTTP 错误、空响应、类型冲突及无法确认的文本/未知内容。 |

可复用的明确附件依据包括：VSB `/system/_content/download.jsp?...news.DownloadAttachUrl...`、`download` 属性、文章范围内的附件容器以及“附件【…】”列表。VSB 的附件列表常在 `.v_news_content` 之外、`form[name='_newscontent_fromname']` 内，本批保留这个实际结构。

默认扫描不把正文 `<img>`、图片放大链接、站点 logo 或普通图片导航当附件。B2 正文图片 URL 保留路径继续工作，没有把正文图片搬进附件 DTO。未观察到的 CMS 附件模板仍需选择器/专用适配，不宣称本批规则涵盖全部网站。

文件名优先保留锚点文字，空文字时使用明确下载文件名或解码后的路径 basename；类型小写。URL 保留原身份参数及顺序，不猜测物理文件路径、不删除查询参数、不用文本文件名拼接新的服务器入口。重复链接只保留一份。

## 3. 隔离回归与用户数据

[baseline-manifest.json](jlu-fix-b3/baseline-manifest.json)、[baseline tests](jlu-fix-b3/baseline-tests.log)、[final tests](jlu-fix-b3/final-tests.log)记录本批实际结果。继续从独立 `backend/build/jlu-b3-*` 副本运行，排除正式 `.env`、SQLite 和资料目录；入口断言有效数据库为 `sqlite://`，测试文件仅写入隔离临时目录。

[脱敏 fixture](../backend/tests/fixtures/jlu_b3/manifest.json)从原始快照提取真实六文件附件结构，保留 URL、文件名、原抓取时间和 SHA-256，移除无关正文及脚本。它是结构控制，不冒充实时网页。

测试覆盖：

- 六个 jpg 的数量、顺序、完整查询参数、文件名和类型；扩展格式必须具有明确附件证据。
- 导航/页脚文档、logo、正文普通图片不进入附件列表；附件型空正文、重复 URL、大小写扩展名、旧 opaque download query 及空锚点文件名继续兼容。
- 非法、凭据及显式私网链接被拒绝；已授权私有 Generic 来源的私网策略保持原行为。
- prefix 分类不因 200/206、非空或 `Content-Disposition: attachment` 假成功；文件类型与响应头/签名冲突保留未验证。
- 即使服务器忽略 Range 返回更大文件，探测只保留 4 KiB 前缀并关闭流；同一运行复用缓存，不重复联网；认证重定向不跟随，403 及 URL 策略拒绝不重试。
- OA 真正调用 `_attachment_url` 的 MockTransport 验证了 POST 路径、`res` 请求体、Referer、`+ / =` token 的 URL 编码以及 HTML、403、429、503、证书异常分支；没有拿“把整个编码方法 mock 掉”的测试当协议验证。
- 在内存 SQLite 中为旧通知补附件，连续两次持久化仍只有一条通知和六条附件，已读、收藏、notice ID 及其更新时间保持不变。详情序列化仍严格使用 `filename / url / type`。

未改 SQLite schema、去重模型、成功 baseline、Cloud policy、ownership/identity、UI 或附件 DTO。没有批量回写历史数据。既有列表元信息不变时，增量策略仍可能跳过旧详情；**本批没有强制重抓历史库，旧缺失附件不能据此宣称已自动补齐**。相关历史重验须使用后续独立、明确范围的任务。

## 4. 历史快照对照

[before](jlu-fix-b3/replay-before.json)、[after](jlu-fix-b3/replay-after.json)分别核验 145 次快照 SHA-256，覆盖 68 个栏目/引用；分组有交集。原抓取时间和本次重放时间分开保存，纯通用解析重放不联网、不导入数据库模块。

全部列表集合及抽样标题、日期、正文、接受状态保持一致。唯一附件变化为软件教办 8548：0 → 6；其余已抽样的办公文档和直链附件没有丢失。原 11 个通过样本仍兼容，27 个导航疑似栏目仍为零候选。

原审计 **108 个带附件端点问题标签的栏目**仅保留在 [historical-triage.json](jlu-fix-b3/historical-triage.json)，含原 URL、检查时间、原因及证据。它们不是 108 个独立文件；本批没有全面实时重验这些栏目，也没有仅凭旧 16 字节 hex 就把其余问题全部改标为验证码或文件损坏。

## 5. 实时附件兼容矩阵

完整 [CSV 矩阵](jlu-fix-b3/attachment-matrix.csv)与 [JSON 矩阵](jlu-fix-b3/attachment-matrix.json)包含机构/原文、原附件 URL、文件名、类型、时间、HTTP 状态、分类、读取数量、前缀文件及 SHA-256、原因和验证范围。CSV 已检查 11 行与 JSON 的 URL/文件名一致。

| 原文/样本 | 检查数量 | 结果 | 验证范围 |
| --- | ---: | --- | --- |
| [软件教办 8548](https://csw.jlu.edu.cn/info/1095/8548.htm) | 6 | 全部 CAPTCHA_REQUIRED | HTTP 206、每份返回 3,805 字节 HTML；未取得 jpg 文件字节 |
| [计算机学院 21217](https://ccst.jlu.edu.cn/info/1056/21217.htm) | 1 | CAPTCHA_REQUIRED | 办公文档下载入口返回同类验证码页 |
| [教务 12677](https://jwc.jlu.edu.cn/info/1050/12677.htm) | 1 | CAPTCHA_REQUIRED | xls 下载入口返回验证码页 |
| [创新创业 2351](https://cxcyjyxy.jlu.edu.cn/info/1060/2351.htm) | 1 | CAPTCHA_REQUIRED | 文档下载入口返回验证码页 |
| [研究生招生 3347](https://yzb.jlu.edu.cn/info/1052/3347.htm) | 1 | FILE_PREFIX_VERIFIED | HTTP 206、4 KiB 含 `%PDF-` 签名；完整 PDF 未检查 |
| [植物科学 6178](https://zky.jlu.edu.cn/info/1022/6178.htm) | 1 | FILE_PREFIX_VERIFIED | HTTP 206、4 KiB 为 ZIP/Office 容器；内部 xlsx 结构与完整文件未检查 |

人工核对验证码响应可见文字为“附件下载”“请输入验证码下载附件”，含 `codeValue` 文本输入框。没有提交验证码、执行页面脚本或推导替代下载地址。这些是受限下载入口，不是已确认损坏的附件。保留原入口让用户按站点正常流程访问。

`FILE_PREFIX_VERIFIED` 只说明有限响应字节具有符合声明类型的文件/容器签名，不说明完整文件、Office 内部类型、完整性、安全性或下载成功。所有结果的 `complete_download_verified` 均为 false。CSV/TXT 无决定性签名，不能只凭 MIME/文件名当已验证文件。

有限读取规则：`Range: bytes=0-4095`，流式最多保留 4 KiB，最多跟随三次重定向且每跳验证 URL 和 robots；只对超时/502/503/504 最多再试一次，验证码/认证/403/429 立即停止。编码器为固定公共端点，真实访问前仍检查 URL 与 robots。本批没有完整下载、解压、执行或安装任何附件。

原始运行证据：[九个 VSB 端点](jlu-fix-b3/attachments-20261014/summary.json)、[两个直链控制](jlu-fix-b3/direct-20261014/summary.json)。最终分类器对已保存 11 份前缀再次离线重放，分类一致，见 [prefix-final-replay.json](jlu-fix-b3/prefix-final-replay.json)。最后仅补充响应头大小写兼容及探测边界测试，没有重复联网冒充新抓取。

## 6. 既有来源与 OA

8 个既有栏目首屏均尝试复验：7 个部分通过、OA 失败；14 个详情、7 个附件端点、6 个下一页。结果见 [兼容 CSV](jlu-fix-b3/live-existing-20261014/jlu-compatibility-report.csv)、[results](jlu-fix-b3/live-existing-20261014/results.json)及 [requests](jlu-fix-b3/live-existing-20261014/requests.json)。来源/机构发现元数据沿用旧时间，不代表本次重新访问全校站点。

软件教办的 `ATTACHMENT_MISSING` 已消失；新增附件因只有限探测而保留 `ATTACHMENTS_UNCHECKED`。附件端点和历史分页仍为待办。CSE 的 `BODY_CONTAINER_FALLBACK` 是旧审计按 20 字符选正文容器造成的既有误报；本批解析器仍使用实际 `.v_news_content`，没有恢复整页回退。

OA 实时结果见 [oa.json](jlu-fix-b3/attachments-20261014/oa.json)：在 robots 获取阶段出现 `SSLEOFError: UNEXPECTED_EOF_WHILE_READING`，因此 `encoder_post_exercised=false`。专用 POST 协议只能记本轮离线测试通过，不能记真实 OA 下载、Cloud 或已安装客户端恢复。保留 TLS、代理和访问规则，不追加认证、不改系统路由。

执行记录：附件探测与既有栏目验证两个任务短时并行，总并发不超过 2；每个任务内部串行并按自身全局至少 1 秒、同源至少 1.2 秒及更长 Crawl-delay 限速。**限速状态按任务独立，未保证两个任务叠加后的共享同主机节拍**，这是本轮执行改进项。补充直链控制随后单独串行运行；后续同源任务应串行安排，不把每任务间隔当跨任务全局间隔。

三组分别记录 17、39、6 条实际 HTTP 响应，含 robots，另有受阻请求未产生 HTTP 响应；不能把响应数当独立网站数。各运行保存原检查时间、代码指纹和断点缓存。新增分类器及审计脚本也纳入后续指纹校验，改变规则后不得直接复用旧结论缓存。

## 7. 保留与下一批

[preservation.json](jlu-fix-b3/preservation.json)确认原审计 1,449 个受保护文件、B0＋B1 与 B2 报告保持不变。正式来源 SHA-256 仍为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。原有工作区改动保留，未写正式 SQLite、提交 GitHub、发布 Release、安装客户端或修改 UI。

下一批建议 B4：依次处理学工、就业、科研、教务及招生等高价值公开栏目，先给候选配置和逐栏内容/附件结论，不自动写正式来源。验证码限制和 OA 网络阻塞继续单独保留；B5 再验收历史分页、增量/去重及真实 Cloud。当前停在 B3。

## 8. 复现入口

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py final --batch b3
.\backend\.venv\Scripts\python.exe backend/scripts/replay_jlu_b1.py --batch b3 --output docs/jlu-fix-b3/replay-after.json
```

实时复核请使用新目录，并串行执行。只有代码及检查模式指纹一致才允许同目录断点恢复：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/probe_jlu_b3.py --output-dir docs/jlu-fix-b3/next-core-run
.\backend\.venv\Scripts\python.exe backend/scripts/probe_jlu_b3.py --only-direct --output-dir docs/jlu-fix-b3/next-direct-run
```

最终代码、前缀及报告链接校验见 [acceptance.json](jlu-fix-b3/acceptance.json)。
