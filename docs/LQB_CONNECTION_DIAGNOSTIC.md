# 蓝桥杯来源连接失败诊断

日期：2026-10-16（Asia/Shanghai）。针对用户截图中的 `https://lus-jlu.github.io/lqb.html` 请求失败；本次只读诊断，没有恢复成功。

## 已确认

截图显示 `ConnectError -> EndOfStream -> SSLEOFError`，原因为 `UNEXPECTED_EOF_WHILE_READING`：TLS 连接提前关闭，未取得可用于解析的网页。错误链没有显示证书校验失败，不能据此判断证书过期或缺根证书。

| 对照 | 观察结果 | 证据 |
| --- | --- | --- |
| 当前 Python + 应用所用 TLS 上下文，默认代理环境设置 | 同样的 TLS EOF，5.409 秒 | [默认/直连诊断](lqb-connection-diagnostic.json) |
| 当前 Python，忽略代理环境设置 | 同样的 TLS EOF，5.199 秒 | 同上 |
| 当前 Python，显式使用已观察到的本机 Clash 代理 `127.0.0.1:7897` | 同样的 TLS EOF，5.431 秒 | [代理诊断](lqb-connection-proxy-diagnostic.json) |
| Windows curl，默认路径 | 连接超时，HTTP 状态 000，约 5 秒 | 本次工具输出；命令见下 |
| Windows curl，经同一本机代理 | 连接超时，HTTP 状态 000，约 5 秒 | 本次工具输出；命令见下 |
| 外部网页读取工具 | 可取得蓝桥杯页面内容 | [目标页面](https://lus-jlu.github.io/lqb.html)；这不能证明本机或原站每次实时连接都成功 |

Python 诊断的准确请求时间、环境版本、原因链和零数据库导入记录已保留在 JSON 中；两次 curl 在本次会话执行，未单独保存精确请求时间，不冒充有逐次时间戳的归档结果。

只读观察到 Windows 系统代理开关关闭，Clash 相关进程运行中；没有 HTTP/HTTPS/ALL_PROXY 环境变量。**显式走现有代理也失败，因此不能宣称开启系统代理就能修复。** 当前 Python 进程环境并不等于已安装客户端的进程环境。

来源配置为 `local_only` 单页监控，使用 `LanqiaoSource -> SinglePageSource -> StaticHTMLSource`，请求成功后才进入章节解析。其他云端来源正常不能证明这个本地连接路径正常。

## 判断与边界

目前定位在本机到目标域名的连接链路，未确认具体是直连网络、Clash 分流/出站节点、上游连接还是 TLS 中间设备造成中断。不能把来源标记为恢复，也没有证据要求修改蓝桥杯正文选择器。

后续应先核对该域名的 Clash 分流、实际出站节点与 DNS，再对可用路径执行一次同 URL 验证；最后在客户端检查来源并确认快照解析和成功状态。没有增加无上限重试、关闭 TLS 校验、改用 HTTP、重置页面基线或改数据库。

本次新增的诊断脚本只导入网络和 TLS 工具，不导入数据库模块。它不修改应用运行行为、来源配置、系统代理、Clash 规则、客户端或既有审计报告。

curl 对照命令（不含凭据）：

```powershell
curl.exe --silent --show-error --connect-timeout 5 --max-time 8 --output NUL --write-out 'http_status=%{http_code} ssl_verify_result=%{ssl_verify_result} remote_ip=%{remote_ip}\n' 'https://lus-jlu.github.io/lqb.html'
curl.exe --silent --show-error --proxy 'http://127.0.0.1:7897' --connect-timeout 5 --max-time 8 --output NUL --write-out 'http_status=%{http_code} ssl_verify_result=%{ssl_verify_result}\n' 'https://lus-jlu.github.io/lqb.html'
```

脚本：`backend/scripts/diagnose_lqb_connection.py`。默认最多两次请求；显式 `--proxy` 时只有一次代理对照。TLS 校验保持开启，各次超时 8 秒，不执行抓取入库或网页快照基线更新。
