# 吉林大学通知适配修复 B5-A：访问阻塞复核

日期：2026-10-14（Asia/Shanghai）。状态：**B5-A 完成，停在本子批交付点**。修复确定性失败重复重试、重试起点、权限页识别和审计请求地址处理。B5-B 日期语义、B5-C 分页/增量去重、B5-D 附件/真实运行环境准入尚未执行。正式来源变更和准入均为 0。

## 1. 结果

| 对象 | 本轮结果 | 处理结论 |
| --- | --- | --- |
| OA 公开通知 | robots 获取时 TLS EOF，未收到正文 | 仍受默认网络路径阻塞；没有关闭 TLS、改变出口或请求编码 POST |
| 研究生答辩入口 | robots 获取连接超时 | 仍受阻；未继续正文或猜接口 |
| 继续教育通知、学历教育通知 | 原无斜杠地址仍有 301/308 循环；官网给出的两个带斜杠 URL 可直接访问 | 已修复审计传输 URL 丢失斜杠的问题，保存两个禁用候选；仅完成访问和列表 DOM 核对 |
| 教学公示 1402 | 302 到 ipauth.htm，HTTP 200 返回明确无访问权限 | 访问限制仍存在；应用解析器现已统一拒绝该权限页，不再仅报选择器空结果 |
| 体育部门索引 | robots 响应断开，未取得正文 | 仍受阻；未认定为可适配公开列表 |
| 体育 OA 登录引用 | 不请求登录页，不登录 | 保留索引/登录引用，不登记通知来源 |
| 数量经济旧链接 | 本轮未请求 | 按计划留至 B7；不把旧 404 冒充新结论 |

本批 8 个处置对象中，6 个原入口执行了有限访问检查、1 个登录引用不请求、1 个延期至 B7。另检查四个官方首页，并从继续教育首页补检两个原样栏目链接。**可访问不等于已支持**；两个新候选没有进行三条详情、日期、附件、分页或 Cloud 准入验证。

证据：[首轮结果](jlu-fix-b5-a/live-20261014/results.json)、[后续汇总](jlu-fix-b5-a/followup-20261014/summary.json)、[补充官方入口](jlu-fix-b5-a/followup-20261014/alternatives.json)、[独立候选](jlu-fix-b5-a/corrected-disabled-candidates.json)。

## 2. 可复现代码缺陷及修复

### 确定性失败重复重试

原 Generic SafeFetcher 和 StaticHTMLSource 的 GET 路径会在配置预算内重试 HTTP 401/403/404/410/429、非暂态 500/501；Generic 还会重复整个跳转超限或大小超限请求链。这会增加学校服务器压力，且无法解决权限/策略错误。

共享 `is_retryable_http_error` 现仅允许 502/503/504、超时、网络异常和远端协议断开在既有预算内重试。证书验证失败、权限/限流、其他确定性状态、重定向/大小/URL 策略错误和解码失败不重试。保留原异常链及日志脱敏，配置重试次数、退避预算和 Cloud/Desktop 策略未扩大。

产品仍使用原配置预算；本批审计把内层重试设为 0，外层只对超时/502/503/504 最多两次尝试。两种口径分别保留，不能把产品预算说成审计的两次。

### Generic 重试起点

原请求在重定向目标发生瞬时故障后，下一次会从上次目标继续，跳过原始入口及可能变化的跳转关系。现在每次重试从原 URL 开始，每一跳仍执行原安全校验。测试覆盖第一次 `/start → /first → 503`、第二次 `/start → /fresh → 200`，不重用过期目标。

### 无权限页面统一拦截

实际教务页面标题为“系统提示”，正文为“您没有访问当前栏目的权限”。原共享 HTML 检查不识别该组合，自动列表可能被当空结果，显式选择器仅报找不到通知。

现要求明确提示标题与栏目权限拒绝文字同时存在，返回 `HTML_PERMISSION_REQUIRED`，覆盖自动及配置选择器路径。正常通知讨论这段错误提示仍允许解析，不因正文提到权限就拒绝。沿用现有 `ValueError / SourceError` 失败契约，无新增 API 字段或 UI 变更。

### 审计传输 URL 不能用来源身份规范化

`canonicalize_source_url` 明确只用于来源身份，会删除末尾斜杠、整理查询参数。原审计 `AuditFetch.get` 却用身份规范化后的地址发 HTTP 并索引缓存，导致官网的 `/html/tzgg1/` 和 `/html/xljy/tzgg/` 被改成无斜杠地址，正确入口也命中错误入口的失败缓存。

现新增 `request_url`：仅去掉不参与 HTTP 的 fragment 和外围空白，保留末尾斜杠及原查询参数、顺序；传输缓存按该地址分别保存。**来源身份函数不改**，不改变正式 code、ownership、订阅或数据库身份。

测试证明：身份规范化相等的两个地址仍按原样发出独立请求和缓存，查询参数不被删除/重排，再次请求精确 URL 可以命中对应缓存。此修复适用于 AuditFetch 取得的原始地址；旧发现清单中已规范化丢失的链接不能凭空还原，仍需官方页面补证。没有重写原审计结果或重新验证全部 306 个入口。

应用仅改四个文件：`http_diagnostics.py`、`sources/base.py`、`sources/generic.py`、`parsers/html.py`。相对本批开始时的真实工作区差异见 [application-changes.diff](jlu-fix-b5-a/application-changes.diff)，不是将此前所有 Git 未提交改动算成本批。

## 3. 继续教育的证据链

首轮实际观察到：

```text
https://dec.jlu.edu.cn/html/tzgg1
  301 → http://dec.jlu.edu.cn/html/tzgg1/
  308 → https://dec.jlu.edu.cn/html/tzgg1
```

学历教育无斜杠入口有同类循环。在既有最大跳转范围内停止，没有提高跳转上限。原无斜杠地址的失败是真实响应，本次也没有自动改写服务器的 Location。

但官方首页同时给出以下真实 href，保留原样后直接 HTTP 200：

- [继续教育通知](https://dec.jlu.edu.cn/html/tzgg1/)
- [学历教育通知](https://dec.jlu.edu.cn/html/xljy/tzgg/)

两页实际文档标题均为“通知公告 - 吉林大学继续教育学院（培训学院）”，并含正文列表 `h3 a` 的真实 `.html` 文章链接。离线逐项核对：首页确有精确 href、返回 URL 保留斜杠、文档标题、栏目文章结构和快照 SHA。详见 [DOM 对照](jlu-fix-b5-a/alternative-dom-inspection.json)。这比仅凭 HTTP 200 或非空多了页面性质依据，但仍不代表详情及来源完整适配通过。

两个候选保留原候选 code 和执行策略，只有独立候选传输 URL 修正，全部 `enabled: false`、`formal_admissions: 0`。B4 的原候选文件保持不变。

## 4. 请求、缓存与工具边界

首轮访问约 **21:58–21:59**，保存 [HTTP 响应轨迹](jlu-fix-b5-a/live-20261014/http.jsonl)、[请求缓存](jlu-fix-b5-a/live-20261014/requests.json)和 [当时代码指纹](jlu-fix-b5-a/live-20261014/code-manifest.json)。17 条 HTTP 响应包括 robots、跳转和一个首页公开文章链接，不是 17 个站点；TLS/超时等未产生 HTTP 响应的尝试不能据此漏计或捏造数量。

首轮在网络检查完成后的汇总阶段发生一次工具断言失败：代码误以为导入 source 不会导入 database，实际 source 包会被动加载 registry/CloudFeedSource，初始化内存引擎。网络快照已保存，没有执行 crawler、数据库 session 或正式数据库写入。记录见 [finalization-error](jlu-fix-b5-a/first-run-finalization-error.json)。旧审计脚本“Never imports database”的头部说明与这种被动导入事实不符，本报告按实际行为说明隔离范围。

后续 **22:02:17–22:02:18** 使用新目录，明确模式为“旧缓存＋未缓存 URL 实时请求”，核验并复制旧快照 SHA，只新增两个官方带斜杠栏目请求。robots 及其他受阻入口复用已保存记录，不反复联网；它们保留原 `captured_at`，不能称为 22:02 又抓了一次。后续新增 HTTP 请求和响应均为 2，见 [HTTP 轨迹](jlu-fix-b5-a/followup-20261014/http.jsonl)与 [输入/代码指纹](jlu-fix-b5-a/followup-20261014/code-manifest.json)。

后续工具断言有效引擎 URL 为 `sqlite://`，并给该引擎安装拒绝实际连接的 guard；数据库模块确有被动导入，实际连接尝试为 0。没有用“未导入数据库”冒充验证结果。

全程只有一个网络任务运行，共享 robots/HTML 限速入口，全局至少 1 秒、同源至少 1.2 秒，遵守更长 Crawl-delay。无登录、验证码操作、附件下载、系统代理/路由修改或 Cloud 部署。OA 本次没有详情验证和 encoder POST，过去默认路径成功证据仍只代表当时时间/环境。

## 5. 隔离回归和保留

| 检查 | 实际结果 |
| --- | --- |
| 修改前全量基线 | 365 passed、1 skipped，41.31 秒 |
| 缺陷复现（旧实现＋新增测试） | 20 failed、210 passed，23.75 秒 |
| 最终定向回归 | 231 passed，25.06 秒 |
| 最终完整后端回归 | 399 passed、1 skipped，49.20 秒 |
| 新增回归项 | 34 项，含审计请求地址/缓存控制 |
| 正式来源变更/正式准入 | 0 / 0 |

日志：[baseline](jlu-fix-b5-a/baseline-tests.log)、[regression-before](jlu-fix-b5-a/regression-before-tests.log)、[targeted](jlu-fix-b5-a/targeted-tests.log)、[final](jlu-fix-b5-a/final-tests.log)。复现失败只来自新缺陷测试，修复后全部通过；原有 365 项通过测试保持兼容。跳过项仍为未配置独立 PostgreSQL 集成环境，不代表真实 Cloud 验收。

隔离副本排除正式 `.env`、SQLite 和资料目录，入口断言内存 `sqlite://`，测试临时数据只写独立目录；[最终 manifest](jlu-fix-b5-a/final-manifest.json)绑定实际应用/测试代码。证书验证、SSRF/peer/逐跳 URL 检查、页面/附件契约、执行和身份策略未放宽，runner、Cloud、数据库 schema 和 UI 未改。

[保留校验](jlu-fix-b5-a/preservation.json)确认原审计 1,449 个受保护文件及 B0＋B1、B2、B3、B4 报告不变。正式来源 SHA-256 仍为 `d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d`。原有用户改动保留，没有 GitHub 提交、Release、客户端安装或正式历史修正。

最终测试代码、证据哈希、候选禁用状态和报告链接核验见 [acceptance.json](jlu-fix-b5-a/acceptance.json)。

## 6. 余项与下一步

已修复四类代码/工具问题，继续教育有官方可访问替代入口。OA TLS EOF、答辩超时、教务权限和体育 robots 不可取得仍受阻；不把外部阻塞列为已恢复。数量经济旧链接按 B7 留待复验。

下一子批为 **B5-B：六个招生栏目的发布日期语义确认**。本次不进入 B5-B、不启用候选，也不把两个继续教育入口算成已经完成内容/附件/分页支持。B5-C/B5-D 及 B6/B7 继续待执行。

## 7. 复现

在仓库根目录执行隔离测试：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py targeted --batch b5-a
.\backend\.venv\Scripts\python.exe backend/scripts/verify_jlu_b1.py final --batch b5-a
```

新实时复核应新建目录，单独串行运行：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/probe_jlu_b5_a.py --output-dir docs/jlu-fix-b5-a/next-live-run
```

只追加未缓存的官方链接、复用已保存失败证据时，必须明确输入目录，保留旧时间和混合模式：

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/probe_jlu_b5_a.py --reuse-input-dir docs/jlu-fix-b5-a/live-20261014 --output-dir docs/jlu-fix-b5-a/next-followup
```
