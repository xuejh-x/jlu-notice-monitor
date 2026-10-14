# HTTPS 证书验证失败排查与修复报告

日期：2026-10-11（Asia/Shanghai）。范围：来源抓取 TLS、诊断、测试及证书打包声明。版本保持 0.7.3；未提交、推送、构建正式客户端、安装或替换现有客户端。

## 1. 根因

### 直接证据

1. 正在运行的旧安装版 `app.log` 在 12:51:29–12:51:30 记录创新创业学院和 OA 的 `SourceError`：`CERTIFICATE_VERIFY_FAILED / unable to get local issuer certificate`。开发虚拟环境也复现同类错误，发生在 TLS 握手，尚未收到 HTTP 响应。
2. 通过有证书验证的 Windows 原生 TLS 连接读取 **服务器实际发送的链**（`get_unverified_chain`，并非 Windows 构建后的链），三个异常域名均出现仅一张叶证书的情况。OpenSSL `s_client -showcerts -verify_return_error -verify_hostname ... -CAfile certifi/cacert.pem` 同时得到错误 20、链长 1。
3. 叶证书：`CN=*.jlu.edu.cn`；SAN 为 `*.jlu.edu.cn`、`jlu.edu.cn`；颁发者 `RapidSSL TLS RSA CA G1`；有效期 2026-07-07 至 2027-01-21。SHA256 指纹：`1F:F3:45:E1:8B:5F:B1:59:76:4D:1D:F1:35:DD:61:1C:E8:50:A2:02:8E:51:09:24:D2:3E:42:BD:DB:60:01:17`。没有过期或主机名不匹配。
4. 完整链的连接还发送 `RapidSSL TLS RSA CA G1` → `DigiCert Global Root G2`（交叉签名证书）。缺链连接没有发送这些中间材料。叶证书 AIA 指向 `http://cacerts.rapidssl.com/RapidSSLTLSRSACAG1.crt`。项目没有下载、保存或信任这张中间证书作为修复。
5. 当前 DNS 返回 `198.18.0.*`，说明存在 Fake-IP 网络路径。使用经过 HTTPS 验证的 Cloudflare DNS 查询得到 ccst/cse/csw/jwc 的 `202.198.16.22`、创新创业学院的 `202.198.16.25`、OA 的 `10.100.18.18`。连接这些解析地址时保留原主机名/SNI，仍得到相同指纹和缺链。因此缺链现象并不限于 Fake-IP 名称解析结果。OA 的地址是校内私网，当前网络具备到它的路径。
6. HTTPX 默认 certifi 验证失败，而 Windows 原生验证对六个真实来源连续两轮全部得到 HTTP 200。仅改为 `ssl.create_default_context()` 在当前 Windows 机器仍有失败，不能替代原生链构建。被测列表均无 HTTP 跳转或跨域重定向。

**结论：直接原因是部分 TLS 连接提供的证书链缺少中间证书；HTTPX 默认静态 certifi/OpenSSL 验证没有 Windows 原生链构建和补链能力。** 同一域名的连接有时提供完整链、有时缺链，正常来源也不是永远正常。未确定具体学校边缘节点/负载均衡配置，不将其作为已确认事实。

### 复现与环境对照

| 来源 | 两轮原 HTTPX 默认请求 | 两轮 Windows 原生请求 |
| --- | --- | --- |
| 计算机学院 | 失败 / 失败 | 200 / 200 |
| 创新创业学院 | 200 / 失败 | 200 / 200 |
| OA | 失败 / 失败 | 200 / 200 |
| 网络安全学院 | 200 / 失败 | 200 / 200 |
| 软件学院 | 失败 / 200 | 200 / 200 |
| 本科生院 | 200 / 200 | 200 / 200 |

证书失败可重复观察，但不能声称所有站点每次请求都会失败。

- 开发环境：项目 `.venv`；Python **3.13.13**，OpenSSL **3.0.19**，HTTPX **0.28.1**，certifi **2026.07.22**。未升级这些依赖；新增 truststore **0.10.4**。
- Python 默认 OpenSSL 文件/目录为 `C:\Program Files\Common Files\SSL/cert.pem` 和 `.../certs`，当前均不存在；HTTPX 实际使用其已存在的 certifi bundle，这两个默认路径缺失不是文件漏打包的证据。
- 旧安装版只读归档检查：包含 `certifi/cacert.pem`，与开发环境的 240,216 字节文件完全一致（SHA256 `9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f`）；包含 HTTPX 0.28.1、certifi 2026.07.22。其 `python313.dll`、`_ssl.pyd`、`libssl-3.dll`、`libcrypto-3.dll` 与开发环境逐字节一致。**不是仅打包后才出现，也不是 certifi 丢失/损坏。**
- Tauri 通过 `backend.rs` 启动 sidecar `serve --managed --host 127.0.0.1 --port ...`，设置 `JLU_ENVIRONMENT=production`；生产数据目录与开发目录分离。抓取不是由 WebView 发起。
- 当前诊断进程的 `SSL_CERT_FILE / SSL_CERT_DIR / REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE / HTTPS_PROXY / HTTP_PROXY / ALL_PROXY / NO_PROXY` 均未设置。WinHTTP 为直连，Windows 用户代理关闭。这不能排除 VPN/TUN；Fake-IP 已证实存在。未读取旧运行进程的完整环境块，也未检查安全软件配置。
- 观察到的证书是公开 CA 签发的相同通配符证书，没有发现企业/安全软件替换证书的证据；不能据此断言不存在任何透明网络设备。
- 系统日期为 2026-10-11，与多个 HTTPS 响应 Date 在分钟量级一致，且处于证书有效期内；Windows Time 服务未运行，无法从 `w32tm` 确认 NTP 同步。没有把时钟问题当作本次根因。

**地址差异：**问题描述的 `cxcjyxy.jlu.edu.cn` 与仓库及旧安装版日志中的 `cxcyjyxy.jlu.edu.cn` 不同。前者独立测试全部 TLS EOF，Cloudflare 查询未返回 A 记录；本次保留并修复真实配置的后者，没有修改来源 URL。

### 请求实现

- 六个学院/OA 适配器共用 `StaticHTMLSource` / `httpx.AsyncClient`；OA 附件编码 POST 也共用该客户端。timeout 20s，原重试 2 次，线性退避 1s/2s；静态列表允许重定向。
- 通用 HTML/RSS/API、认证来源使用 `SafeFetcher`；保留每跳验证、3 次重定向上限、响应大小限制和 local/cloud SSRF 区分。
- 桌面云优先源可先读取 `CloudFeedSource`，失败后通过原适配器本地回退；旧日志证实三个异常发生在回退的原站 GET。
- Cloud feed、Cloud admin/registry、Chrome CDP 这些其他客户端本次未改动。HTTPX 本来不使用 `REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE`。

## 2. 修改文件

| 文件 | 修改 |
| --- | --- |
| `backend/app/services/tls.py` | 新增统一来源 SSLContext 工厂；识别异常链中的 `SSLCertVerificationError`。 |
| `backend/app/sources/base.py` | 静态来源接入验证上下文；证书错误明确标记、保留原因，立即失败。 |
| `backend/app/sources/generic.py` | SafeFetcher 接入同一工厂；保留 local/cloud trust_env 和 SSRF 策略，明确证书错误。 |
| `backend/app/sources/oa_public.py` | 附件编码 POST 也保留明确证书错误及原始原因。 |
| `backend/pyproject.toml` | Windows 专用 `truststore>=0.10.4,<0.11`；将直接使用的 certifi 显式声明为依赖。 |
| `backend/jlu_notice_backend.spec` | 显式收集 certifi 资源和 `truststore._windows`。 |
| `backend/tests/test_tls.py`、`backend/tests/fixtures/tls/*` | 真实 loopback TLS 正/负例、CA override、通用抓取、错误恢复与历史保护。证书和服务端密钥仅供测试，未安装进系统信任库。 |
| `backend/scripts/diagnose_tls.py` | 不启动应用、不访问数据库的信任/证书链对照工具。 |
| `backend/scripts/verify_source_tls.py` | 真实抓取器列表/详情 smoke，不启动服务、不入库。 |
| 本报告及 `docs/tls-*.json`、`docs/tls-frozen-probe.jsonl` | 保存实际诊断、抓取和冻结验证证据。 |

没有改动 URL/API、通知去重、附件 DTO、用户状态、数据库模型/迁移、订阅、版本号或前端源码。用户已有其他修改保持原样。

## 3. 修复机制

- Windows 使用显式 `truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`：CryptoAPI 按系统信任策略构建链，使用 Windows 缓存/AIA 的中间证书材料，验证至受信任根。保留 certifi 根集合以兼容之前 HTTPX 接受的公共 CA。
- 外部上下文始终 `CERT_REQUIRED`、`check_hostname=True`；未全局 monkeypatch SSL，没有 verify=False、没有无条件信任、没有忽略证书异常。
- 中间证书只是构建链的材料，不会作为任意受信根加入系统；其签名、有效期和主机名仍需验证。未把某学校叶证书或中间证书硬编码进应用。
- 显式 `SSL_CERT_FILE` 优先，其次 `SSL_CERT_DIR`：保持原 HTTPX 的独占信任语义，使用标准验证上下文，不额外回退系统根；路径错误直接暴露。Cloud `trust_env=False` 仍忽略这些本地覆盖。非 Windows 继续使用原 certifi/OpenSSL 行为。
- 证书错误保留为来源失败及 `TLS_CERTIFICATE_VERIFY_FAILED`，不会改称超时/不可访问；这类确定性失败不再重复重试，其他异常沿用原 timeout/重试策略。
- truststore 是小型纯 Python 包，Windows 调用系统 CryptoAPI，无需额外浏览器或自带 CA 路径。项目要求 Python ≥3.12，高于该库最低要求。

机制依据：[HTTPX SSL 文档](https://www.python-httpx.org/advanced/ssl/)、[truststore 官方文档](https://truststore.readthedocs.io/en/stable/index.html)。

## 4. 验证结果

### 真实抓取（修复后开发运行时）

| 来源 | 列表候选 | 实际详情正文字符数 | 附件 | 结果 |
| --- | ---: | ---: | ---: | --- |
| 计算机学院 | 10 | 716 | 1 | PASS |
| 创新创业学院（cxcyjyxy） | 15 | 154 | 1 | PASS |
| OA 校内通知 | 30 | 559 | 0 | PASS |
| 网络安全学院 | 11 | 第二条 1,600 | 0 | PASS；首条正文为空，已在证据中保留 |
| 软件学院 | 30 | 1,409 | 2 | PASS |
| 本科生院 | 15 | 200 | 1 | PASS |
| 蓝桥杯单页监控 | 按设计为 0 | 成功解析 snapshot | — | PASS |

正文和附件字段由真实现有解析器产生；未下载附件文件。网络安全学院首条解析为空是本次实测发现的独立现象，未顺手改解析器。

### 安全、状态与构建

- 本地真实 TLS：可信有效证书通过；未知 CA、过期、错误主机名均抛 `SSLCertVerificationError`，不是 MockTransport 假握手。StaticHTMLSource 和 SafeFetcher 的证书失败明确记录并向上报告。
- 内存 SQLite + 真实 TLS：先验证失败为 SOURCE_ERROR，再启用测试上下文中的可信测试 CA 后成功抓取，连续两次恢复为 healthy，last_error/code 清空、错误计数归零；只有同一历史 ID、保持 baseline/read，new_count=0，重复详情跳过。未修改用户真实数据库。
- 原有完整回归覆盖云优先首次本地回退的历史 baseline/read、后续新增未读、去重、增量、失败不推进基线等行为。
- 最终代码后端完整回归：**228 passed, 1 skipped**（`python -m pytest -p no:cacheprovider`）；可选 PostgreSQL 环境测试跳过。新增 TLS 相关测试 9 项；相关 TLS/OA/基线/保留子集另有 **40 passed**。
- 前端：**29 files / 212 tests passed**；lint PASS；TypeScript/Vite build PASS，只有既有 chunk >500 kB 提示。未进行 UI 改动。
- `pip check`：No broken requirements found。
- PyInstaller **6.22.2** 冻结了独立 TLS probe（位于忽略的 `backend/build/tls-probe`，不是正式后端/客户端）；使用本次相同工厂、hidden import 和 certifi 收集配置。冻结运行时六个学院/OA URL 全部 200；`expired.badssl.com`（有效期）、`wrong.host.badssl.com`（域名）、`self-signed.badssl.com`（不可信根）全部拒绝。外部上下文显示 verify_mode=2、check_hostname=true。

原始证据：`tls-diagnostics-before.json`、`tls-diagnostics-origin.json`、`tls-runtime-evidence.json`、`tls-source-verification.json`、`tls-frozen-probe.jsonl`。

## 5. 剩余风险 / 客户端验收边界

1. **当前安装版依然是旧二进制。** 未重启、替换或向其注入修复，不能宣称用户正在看的订阅页面已经恢复。已验证错误到 healthy 的后端状态转换；修改后的正式 sidecar/Tauri 安装版仍需未来重新构建并实际验收。
2. 冻结 probe 证明关键依赖/证书资源能在此 Windows 冻结环境运行，不能替代整个正式 sidecar、安装包和 WebView 的验收。
3. Windows 依赖其可信根、缓存/AIA 可达性及系统策略。新设备如果缺少中间缓存且不能访问 CA AIA，仍可能明确报证书错误；不会降级跳过验证。未来学校更换证书无需更新硬编码证书。
4. 非 Windows 云部署本次保持原验证策略；本机修复不能替代学校修复完整链，也不代表独立云服务器环境已验收。
5. 网络安全学院首条详情为空、问题描述的错误拼写域名 TLS EOF 分别独立存在，不属于此次证书信任修复。
6. 正式客户端验收时使用原资料目录，在不重置数据库的前提下刷新三个来源，确认订阅状态恢复、历史已读/基线保持、再次刷新无重复新增。当前任务未运行真实数据库写入抓取。
