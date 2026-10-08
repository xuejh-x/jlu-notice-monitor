# v0.7.3 Windows 升级验收清单

状态：本地构建验收阶段。**未执行真实客户端安装、卸载、替换或真实数据库修改；等待用户确认。**

## 1. 安装前准备（确认后再执行）

- [ ] 记录当前安装版本、安装位置、全库/未读/收藏数量、代表性通知 ID 与已读状态、来源启用/订阅配置及界面偏好。
- [ ] 检查存储页面的保留天数与待清理数量。既有策略默认保留 365 天，启动和定时清理可删除更早的通知，包含收藏/未读。数量差异必须区分正常保留策略、同步新增和真正的数据丢失；需要永久留存的历史数据应先保存到独立备份。
- [ ] 在原客户端仍运行时，数据库备份必须使用 SQLite 在线备份 API（`sqlite3.Connection.backup`），源连接使用只读 URI，目标是新建的独立备份文件；随后对备份执行 `PRAGMA integrity_check`，应返回 `ok`。不得直接复制正在写入的 `.db` 文件。
- [ ] 另一种方式是正常完全退出客户端，并确认其托管后端也已退出，再整体备份 `%LOCALAPPDATA%\JLU Notice Monitor`。若仍有 WAL/SHM 文件，保留完整文件集；不要删除它们或只复制主数据库。备份后同样验证独立副本完整性。
- [ ] 数据库位于 `%LOCALAPPDATA%\JLU Notice Monitor\data\notices.db`；其中包含来源、用户阅读状态和 AppState 监控基线。运行目录中的 `config`、`credentials`、`auth-profiles` 等已有配置/登录资料一并私下备份，不上传至 GitHub。
- [ ] 完全退出后备份存在的 `%LOCALAPPDATA%\com.jlunoticemonitor.desktop` 与 `%APPDATA%\com.jlunoticemonitor.desktop`，用于保护 WebView 的 `jlu-settings` / `jlu-theme` 等本地界面状态；只备份存在的路径，不创建或重置用户目录。
- [ ] 保存旧版本安装包及备份的路径、时间、SHA-256。升级后发生异常时先保留现场，不直接用旧数据库覆盖正在运行的客户端。

## 2. 安装器与数据安全

- [ ] 核对本次安装包 SHA-256，与本清单最终构建记录一致。
- [ ] 正常退出原客户端及其后端，再运行新安装器。使用原有当前用户升级方式，不提前手动卸载，不勾选“删除应用数据”。
- [ ] 确认程序文件没有安装到数据库所在 `data` 目录。既有安装钩子把默认程序目录与 `%LOCALAPPDATA%\JLU Notice Monitor` 运行数据目录分离；应用标识仍是 `com.jlunoticemonitor.desktop`。
- [ ] 安装后版本应为 0.7.3。第一次启动前已有备份，不以“安装成功”替代后续运行验收。
- [ ] 本次没有新 Schema Migration；应用启动仍执行原有的兼容初始化和正常保留策略。不能承诺全部历史记录永不减少。

## 3. 真实客户端升级后

- [ ] 检查后端正常连接、通知列表和详情可打开，现有自定义源、订阅、启用状态、通知偏好和界面设置仍保留。
- [ ] 对比保留期限内的原有通知 ID、正文、附件、已读/未读及收藏状态。不得只看总数；记录因保留策略删除与同步新增的差异。
- [ ] 来源管理出现“蓝桥杯赛事信息（吉林大学）”，为 `single_page_monitor` / `local_only`，不可通用编辑或上云。
- [ ] 若该来源此前没有成功建立基线，首次成功检查只建立 `single-page-baseline:{source_id}`，不创建历史 Notice / 未读 / NEW 通知事件；已有基线不得重置。
- [ ] 手动检查成功后，“最近检查”、健康状态应刷新；短时任务无需先看见“正在检查”。网络/解析失败应显示对应错误，恢复后状态应更新，不应覆盖先前基线。
- [ ] 保持联网及客户端运行，等待配置的调度周期（默认 15 分钟）；观察自动检查时间更新，页面无变化时不增加通知。
- [ ] 正常退出并重启后，基线仍在，重复检查同一页面不重复生成修订；新旧普通来源重复同步也不出现重复通知。
- [ ] 界面解释监控限制：完全退出或休眠期间不会检查，恢复后可手动检查；离线期间出现又撤回的变化可能漏检。窗口关闭与“完全退出”以实际进程是否运行为准，不开发后台常驻服务。
- [ ] 若真实出现蓝桥杯更新，检查默认最新排序、日期筛选、首页最近通知与分页能找到该未读；日期显示“首次检测”，不伪造官方发布时间。
- [ ] 最后人工检查 GUI、原文跳转、Windows 通知及退出重启后的用户状态持久性。

## 4. 模拟网页变化（仅独立测试库）

- [ ] 使用新建测试目录或经在线备份得到的独立数据库副本；同时显式指定 `JLU_APP_DATA_DIR` 和 `JLU_DATABASE_URL`。禁用自动启动同步，确保测试进程不连接真实数据库。
- [ ] 通过现有 `backend/tests/test_lqb_monitor.py` / `test_single_page_release.py` 的独立 fixture 验证重要章节变化、无关获奖变化、解析失败、基线不被覆盖、重复去重、并发互斥及日期分页。
- [ ] 若需 GUI 模拟，使用另一个隔离账户/虚拟机或明确隔离的测试客户端与本地测试网页；不得修改当前客户端的来源 URL、生产网页、真实 AppState 或基线。
- [ ] 首次有效快照零未读；重要更新产生可读的实际差异；重复快照零新增；失败后恢复不会重新导入历史。测试读写、还原或删除只针对已确认的独立测试目录。

## 5. 验收失败与发布门槛

- [ ] 出现真实数据丢失、阅读状态重置、监控基线重置、普通来源重复或来源失效但显示健康时，暂停发布并保留日志、版本与私有备份。
- [ ] 不清空数据库，不重置基线，不用删除测试/扩大 skip 绕过失败。
- [ ] Windows 实际升级、GUI 和原生通知检查由确认后的人工验收完成；PostgreSQL 实机及 Cloud 生产链路未验证，不能宣称已通过。
- [ ] 只有用户确认后才进行安装；Git commit/push/tag、GitHub Release、上传、自动更新均未获本轮执行授权。

## 6. 本轮构建记录

### 实际产物

- 版本：0.7.3，Windows x64 NSIS。
- 路径：`E:\jlu-notice-monitor\frontend\src-tauri\target\release\bundle\nsis\JLU Notice Monitor_0.7.3_x64-setup.exe`。
- 大小：29,546,936 bytes。
- SHA-256：`81EDD227CE95952AEED4BF02E5E1780AF0C8D7DEDAA2C0105365616E319864F2`。
- 同目录校验文件：`JLU Notice Monitor_0.7.3_x64-setup.exe.sha256`。
- 安装器及桌面主程序 ProductVersion / FileVersion：0.7.3；NSIS 目标 x64。
- Authenticode：`NotSigned`，Windows 可能显示安全提示；哈希核验不等同于代码签名。
- 默认 WebView2 安装方式仍为已有 `downloadBootstrapper`；缺少运行时的新机器可能需要联网，未改变现有安装方式。

### 实际检查

| 检查 | 本轮执行 | 结果 |
| --- | --- | --- |
| 正式打包 | `npm.cmd run desktop:build`（frontend） | PASS；依次重新构建 PyInstaller sidecar、前端 production build、Tauri 主程序、NSIS |
| 版本与标识 | 核对7个版本配置文件、生成的 NSIS 脚本、PE 版本资源 | PASS；标识、产品名、安装模式不变；lockfile 未更新依赖 |
| 包内模块/数据 | PyInstaller archive reader 检查实际 sidecar | PASS；含 `app.sources.lqb`、`app.services.page_monitor`、API、BeautifulSoup/httpx/YAML/SQLAlchemy/tzdata 和新增来源 YAML；无 DB/WAL、.env、日志、DPAPI、OA 失败 HTML |
| 后端 staging | 对比 `backend/dist` 与 Tauri sidecar SHA-256 | PASS；一致为 `4BC6CF053FE85858ADB944F0C33E7F672B7D0169C1C3A41A472AE828E3477F38` |
| 隔离后端 | `backend\.venv\Scripts\python.exe artifacts\verification\v0.7.3\verify_packaged_backend.py`（仓库根目录） | PASS；真实打包 EXE 健康端点返回0.7.3，来源 API 可用，公开蓝桥杯页面首次/重复检查均202并成功，零 Notice/UserState/NotificationEvent |
| SQLite / 重启 | 同一独立数据目录启动两次实际 sidecar | PASS；默认最新排序/日期查询正常，基线持久，零重复通知/事件；不代表 GUI 或安装升级验收 |
| 安装器数据边界 | 审阅既有 hooks 与本次生成的 NSIS install/uninstall 段 | PASS（静态检查）；仅携带主程序与后端，默认程序目录与运行数据分离；升级 `/UPDATE` 下不执行删除 WebView 数据分支；应用自身原有保留策略仍适用 |
| 工作区安全 | `git diff --check`、全部变更路径和敏感内容检查、ignore 核验 | PASS；构建与诊断产物均忽略，未提交数据库/日志/凭据，没有临时调试代码进入待提交变更；未执行任何 Git 写操作 |
| 真实 Windows 升级 / GUI / 原生通知 | 未执行 | NOT VERIFIED，等待确认 |

隔离验收目录：`E:\jlu-notice-monitor\artifacts\verification\v0.7.3\packaged-0.7.3-xqwpjvn2`，仅为独立新建测试数据，保留备查，不是用户数据库。诊断脚本在被 Git 忽略的 artifacts 目录，不属于发布代码。

诊断脚本最初遇到未消费控制台管道造成的状态查询阻塞，以及错误使用 `sort=latest`（真实 API 参数为 `newest`）返回422；仅修正隔离验收脚本并重新执行，最终上述检查通过，未改业务代码或降低断言。构建警告仍有既有前端 >500kB bundle 提示及 SQLAlchemy 可选 `pysqlite2` / `MySQLdb` / `psycopg2` 未安装提示；SQLite 打包服务实际运行通过，未声称 PostgreSQL 实机通过。

前一轮完整回归结果见 [蓝桥杯专项报告](LQB_MONITOR_REPORT.md)：218 passed / 1 skipped、前端199 passed、E2E34 passed、lint/build PASS。本轮仅改版本/文档，未无意义重复运行整套测试；正式构建已再次运行 production build。

Git：master，HEAD `71dc42a9d8321a2c0c61f032b41c7d8594ff907e`，功能修复与发布准备仍未提交。远程 Tag 只读检查未发现0.7.2/0.7.3；0.7.2 已是仓库此前本地升级版本，因此采用0.7.3，不覆盖旧版本安装包或 Tag。

结论：安装包构建完成，可进入用户确认后的真实升级验收，**尚不可把本次 Windows 升级与 GUI 验收标记为通过**；未安装、未提交、未推送、未创建 Release、未启用自动更新。
