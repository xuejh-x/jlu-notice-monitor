# OA SOURCE_ERROR 排查与修复报告

日期：2026-10-13，Asia/Shanghai。范围：安装版只读诊断、工作区最小代码修复、独立测试、经用户授权的临时路由实验及 OA 专用 Clash 修复。

## 最终修复结果（2026-10-13 补充）

**当前工作区代码通过正常 OA 域名的默认路径抓取已恢复。** 用户授权后，已将下述两个增量写入当前 Clash 订阅的代理/规则扩展文件，并热重载内核：

```yaml
proxies:
  - name: JLU-OA-Ethernet
    type: direct
    interface-name: 以太网
    ip-version: ipv4
rules:
  - DOMAIN,oa.jlu.edu.cn,JLU-OA-Ethernet
```

完整修复前日志明确记录：`[TUN] Auto detect interface for 10.100.18.18 --> WLAN`，随后命中 `IPCIDR/10.0.0.0/8 → DIRECT` 并 `i/o timeout`。因此不是缺少本地抓取调用，而是实际本地请求的出口选错。

修复后日志确认：`oa.jlu.edu.cn:443 match Domain(oa.jlu.edu.cn) using JLU-OA-Ethernet`。没有硬编码 OA 原站 IP，没有修改生产抓取器的网卡选择，没有改动其他域名规则、DNS/TUN 设置或全局出站接口。该机器的接口名称只出现在本地 Clash 配置中。

验收结果：

- 正常域名、普通 `OAPublicSource`、无诊断专用 transport、无进程代理覆盖：列表/详情 HTTP 200，30 条候选，首条正文 551 字符；学院对照站点也为 200。
- 真实 `CrawlerManager` + 真站点 + 内存 SQLite：连续三轮均为 Cloud `PUBLIC_FEED_NOT_CONFIGURED` → Local success，最终 healthy，错误清空。
- 取 3 条真实通知建立独立基线后，后两轮均 `new_count=0`、`detail_skipped=3`；通知 ID、来源关系 ID/去重键、已读/未读、收藏及用户状态时间不变。
- 实测合计 20 次 HTTP 请求全部 200：3 次列表、3 次详情、14 次附件编码 POST。没有下载附件文件。
- 最终完整后端回归：**238 passed, 1 skipped**，在独立源码副本中完成。新增 3 项撤销工具测试，验证保留后续配置变更、遇到冲突拒绝写入。
- 运行中的 Clash 当前第一条规则已复查为 OA 专用规则，持久扩展文件也包含同一增量。

证据：`oa-egress-isolated-verification.json`、`oa-egress-default-verification.json`、`oa-egress-live-logs.json`、`oa-egress-apply.json`、`oa-recovery-live-verification.json`、`oa-recovery-http-evidence.json`。完整回归输出位于忽略目录 `backend/build/oa-final-regression-output.txt`。

**安装版边界：仍未替换、启动或重启旧客户端。** 最后只读检查时原端口 54586 没有监听，数据库中保存的错误来自修复前的抓取，不能据此说网络修复后的安装版已经成功或失败。旧二进制仍不包含工作区的 Windows TLS 修复，不能将工作区成功等同于旧客户端已恢复。

## 结论

存在三个独立因素，不能仅归因为“未连接校园网”：

1. **修复前默认网络路径失败。** 默认域名请求在 TLS 握手阶段断开，异常链为 `httpx.ConnectError('') → httpcore.ConnectError(EndOfStream()) → EndOfStream → SSLEOFError / UNEXPECTED_EOF_WHILE_READING`，约 5–6 秒后失败，未收到 HTTP 响应。相同电脑、相同 OA 主机名和证书验证，经指定现有以太网接口可返回 HTTP 200。因此 OA 并非整体不可访问，解析器也不是这次失败的起点。
2. **旧版 TLS 证书问题确实再次出现。** 安装版 10 月 12 日日志多次记录 `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`。本次在已证明可达的以太网路径上，使用旧版 certifi/OpenSSL 信任策略仍复现该错误；使用工作区已有的 Windows 原生链构建方案则成功。此前已确认的缺中间证书链原因见 `HTTPS_CERTIFICATE_FIX_REPORT.md`；本次未重新导出服务端证书链，不将旧报告的链抓包冒充本次新证据。
3. **客户端云端 Feed 未配置。** 运行客户端 `/api/crawler/status` 的 OA Cloud attempt 为 `PUBLIC_FEED_NOT_CONFIGURED`。它没有发出云端请求，并非已部署云服务返回错误。随后确实执行 Local attempt，最终失败。`fallback_used=true` 表示执行过本地抓取，不代表本地抓取成功。

**边界：工作区修复、默认网络路径修复及独立抓取验证已完成，已安装客户端没有被替换，不能宣称旧客户端已经验收恢复。**

## 安装版与工作区分离

- 正在运行：`E:\JLU Notice Monitor de exe\jlu-notice-backend.exe`，文件时间 2026-10-08；通过 `serve --managed --host 127.0.0.1 --port 54586` 运行。
- 实际日志：`%LOCALAPPDATA%\JLU Notice Monitor\logs\app.log`。仓库的 `backend/logs/app.log` 不是当前安装版日志。
- 安装版数据库以 SQLite `mode=ro` 打开。排查时 OA `last_success_at=2026-10-11 04:18:37.347550`（UTC，即北京时间 12:18:37），`consecutive_errors=13`；共有 414 条通知、414 条用户状态和 425 条来源关系。
- 10 月 13 日 13:24:57 与 13:27:56 的安装版 OA 错误均以 `failed: ` 结尾。相应运行记录明确为 Cloud failure → Local failure。
- 工作区已有 10 月 11 日 TLS 修复，尚未进入此安装版。本次在已有修改上增量改动，没有覆盖用户其他未提交文件，也没有把已有 TLS 修复列为本次新实现。

## 初次排查的网络与 HTTP/解析对照

- 系统 DNS 为 Fake-IP `198.18.1.145`；Clash Verge/Mihomo 的 TUN 和 Fake-IP 模式启用。
- Cloudflare 与 Google 的 HTTPS DNS 查询均返回 OA A 记录 `10.100.18.18`，没有 AAAA 记录。只有私网 A 记录不足以断言所有校外环境必然不可达。
- 实际同时启用以太网、WLAN、Meta/TUN。默认路由包括 Meta/TUN、WLAN 和以太网，以太网默认路由 metric 为 256。默认连接失败而指定以太网成功，证实出口选择影响本次请求；没有证据确定是哪条 Clash 内部规则或远端设备主动断开，不能进一步臆断。

| 路径 / 验证策略 | 结果 | HTTP / 解析 |
| --- | --- | --- |
| 默认域名路径 + 工作区 Windows TLS | TLS EOF，约 5–6 秒 | 无 HTTP 响应，未进入列表解析 |
| 真实地址 + 默认出口（初始） | 约 5 秒连接重置 | 未取得 HTTP 状态 |
| 真实地址 + WLAN 定向 | 8 秒 socket 超时 | 未取得 HTTP 状态 |
| 真实地址 + 以太网定向 + Windows TLS | 成功 | 列表 200 / 38,810 bytes；详情 200 / 39,801 bytes；30 条候选、首条正文 551 字符 |
| 相同以太网路径 + 旧 certifi 策略 | CERTIFICATE_VERIFY_FAILED | 未取得 HTTP 状态 |
| 学院对照站点 + 默认路径 | 成功 | 计算机学院列表 HTTP 200 |

以太网诊断只在独立进程的 socket 上选择接口，保留 `oa.jlu.edu.cn` 的 Host、SNI、主机名验证及 `CERT_REQUIRED`，然后调用现有 OA 列表/详情解析器。没有将接口或真实 IP 写死到生产抓取器。首条真实详情没有附件；附件编码 POST 的失败诊断和成功解析由隔离 fixture 测试覆盖，未下载附件文件。

最新实际证据：`oa-path-diagnostics.json`。

## 为什么 failed: 后为空

原 `_get()` 使用 `f"... failed: {last_error}"`。HTTPX 将底层 TLS EOF 包装成 `ConnectError('')`，其 `str()` 为空。原代码还没有在最终抛出时显式保留 `__cause__`，因此 UI 和日志都丢失了可定位的底层原因。空文本并不等于超时。

另外，`log_event()` 原已传递 `fallback_reason` 和 `effective_execution`，但 `JsonFormatter` 的白名单没有这些字段，写到磁盘时被丢弃；失败的列表请求没有累计耗时，导致日志出现 `duration_seconds=0.0`。

## 本次代码改动

- `backend/app/services/http_diagnostics.py`：输出异常类型和 cause/context 链，处理空消息、循环链、重复原因；不依赖错误文本猜测证书异常。
- `backend/app/sources/base.py`：GET 最终错误显式 `raise ... from last_error`；记录每次请求的类型、超时配置、尝试次数、耗时、HTTP 状态、响应大小及异常原因。原 20 秒请求超时、重试与退避策略保持不变。
- `backend/app/sources/oa_public.py`：附件编码 POST 同样保留根因及请求日志，保留附件 DTO 和现有请求契约。
- `backend/app/crawler/runner.py`：分别记录 Cloud / Local attempt 的结果、原因和耗时；失败列表请求也计入耗时。没有改变云异常后执行本地抓取的流程或去重/入库规则。
- `backend/app/logging_config.py`：保留上述结构化字段；清除异常文本内嵌 URL 的 query、fragment 和 userinfo，避免增强诊断时泄漏凭据。
- `backend/scripts/diagnose_oa.py`：可复现的只读路径/证书对照，不启动应用、不抓取入库、不修改系统路由；接口/地址参数仅供诊断，不能当成跨设备配置。
- `backend/tests/test_source_http_diagnostics.py`：7 个新测试用例。

已有 TLS 工厂继续执行证书链、有效期和主机名验证，没有新增 `verify=False`、信任叶证书或绕过验证。

## 临时路由实验

用户明确授权后，通过标准 UAC 添加仅位于 ActiveStore 的临时路由：

```powershell
New-NetRoute -DestinationPrefix '10.100.18.18/32' -InterfaceIndex 19 `
  -NextHop '49.140.62.254' -RouteMetric 5 -PolicyStore ActiveStore
```

结果：真实地址的默认 socket TLS 恢复，但 Fake-IP 域名请求仍然 TLS EOF。该实验说明一条主机路由不足以修复当前 TUN/Fake-IP 域名路径，不能宣称网络修复成功。证据保存在 `oa-route-verification.json`。

**已经通过精确匹配目标、网卡、网关和 metric 撤销本次新增路由，并复查无残留。** 此实验阶段未修改 Clash 配置、系统 hosts、DNS、系统证书或持久路由。后续 Clash 专用规则的授权及成功验证见本文开头。

## Clash 配置备份与撤销

本地配置修复限制在当时选中的订阅 `RpIRs7CcKZuo`；切换其他订阅不会自动带入规则。以太网须保持可用，换设备/更换接口时应调整本地规则，不应把此机器的接口名称写进应用代码。

授权前先完成独立代理测试和完整候选配置语法检查。实际写入前再次检查文件未发生并发变化，并保留现有 Selector 选择。备份保存在用户原 Clash 目录，不作为仓库文件或上传内容：

`C:\Users\zc\AppData\Roaming\io.github.clash-verge-rev.clash-verge-rev\oa-egress-backups\20261013T070100Z`

备份包含原运行配置、两个扩展文件及前后 SHA256。可先只读检查撤销准备状态（在 `backend/`）：

```powershell
.\.venv\Scripts\python.exe scripts/restore_oa_egress.py --backup-directory 'C:/Users/zc/AppData/Roaming/io.github.clash-verge-rev.clash-verge-rev/oa-egress-backups/20261013T070100Z'
```

添加 `--apply` 才会实际撤销并热重载。运行配置之后已正常更新过，工具会仅移除本次准确的 OA 增量，保留后续订阅节点、代理组和其他设置；如果 OA 出站本身被用户修改或被新代理组引用，则拒绝覆盖。当前只读检查为 `ready`、`preserve_later_changes=true`，没有执行撤销。

## 独立验证与数据保护

- 相关隔离测试：**42 passed**。
- 最终后端完整回归：**235 passed, 1 skipped**；跳过的是未配置 PostgreSQL 的可选环境测试。
- 全量回归在 `backend/build/oa-regression-env` 的独立源码副本运行，复制时排除 `.env`、用户数据、日志、缓存和虚拟环境。副本使用独立数据库/运行目录；原环境变量强制覆盖默认路径的试跑导致环境断言失败，已改用此完整隔离副本并全量通过。
- 新测试验证实际 Cloud 构造失败后调用真实 OA Local adapter；使用隔离 HTTP fixture 和内存 SQLite，检查本地失败不推进成功时间、恢复后连续两次刷新不重复新增、通知与来源关系 ID 保持、已读及未读状态分别保持、收藏保持，健康错误清除。
- 既有 TLS 真实 loopback 测试验证可信证书成功，未知 CA、过期、错误主机名继续拒绝；原有 Cloud/Local 切换、初始基线及保留策略回归全部通过。
- 增强日志验证 EOF、空 ReadTimeout、HTTP 503、附件 POST；JSON 中保留诊断字段且不泄漏测试 URL 的 token。
- `git diff --check` 对本次修改的已跟踪后端文件通过。没有 UI 改动，因此本次未重复运行前端测试或构建。
- 安装版数据库仅只读检查，没有手动触发安装版抓取，也没有覆盖、迁移、清理或重置任何通知、去重、已读数据。正常运行客户端自己的调度不由本诊断进程控制。

## 后续边界

1. 当前订阅的默认域名出口已通过 OA 专用规则修复。此前无效的 Windows 主机路由已撤销；现在的成功不依赖诊断用定向 socket。
2. 已安装旧后端没有工作区 TLS 修复；即使出口恢复，仍可能遇到已经复现的证书验证失败。按照用户要求，本次没有替换它。
3. 云端 Feed 需要真实部署地址后才能配置和验收。未猜测 URL，也没有把“未配置”描述成云端站点故障。

本次补充脚本 `verify_oa_recovery.py` 要求有效 URL 为 SQLAlchemy 内存 SQLite，并要求显式桌面角色及 `backend/build` 下的隔离目录，验证前拒绝非隔离配置。命令使用 `JLU_DATABASE_URL=sqlite://`，不使用会被当前 Settings 当成路径处理的 `sqlite:///:memory:` 输入。

未发布版本、未构建正式安装包、未提交、未推送 GitHub、未替换或重启已安装客户端。
