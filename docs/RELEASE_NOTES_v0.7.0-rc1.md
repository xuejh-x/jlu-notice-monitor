# JLU Notice Monitor v0.7.0-rc1

## 中文

这是 JLU Notice Monitor 的首个 v0.7.0 候选发布版。它把多来源抓取、云端/本地执行、通知处理和 Windows 桌面体验整合为一套可安装、可升级的应用。

### 主要更新

- 完成统一的 Source Adapter 与来源管理架构，支持官方公开来源、云端共享来源和本地来源。
- 正式接入无需登录的吉林大学 OA 校内公开通知，并保留正文、附件、增量抓取和统一去重能力。
- 为官方公开来源加入 Cloud Preferred：云端 Feed 未配置、网络错误、超时、响应无效或过期时，串行回退到已有本地 Adapter；同一次运行只产生一个最终结果。
- 加入来源内稳定身份、来源运行尝试记录和回退状态展示，避免云端/本地切换造成重复通知。
- 完成事件驱动提醒流水线、Windows 原生通知、通知权限引导、本地提醒偏好、截止提醒、每日摘要与来源健康提醒。
- 完成 Tauri 2 桌面封装、受管 FastAPI sidecar、动态回环端口、保留式数据库迁移与 NSIS 当前用户安装。
- 更新响应式三栏阅读体验、筛选/搜索、已读状态、收藏、附件展示和 404/网络/超时错误边界。

### 安装

下载 `JLU Notice Monitor_0.7.0-rc1_x64-setup.exe`，并使用随 Release 提供的 `.sha256` 文件校验完整性。

SHA256：`079D234A3E466FFF8B6EE777A79DF50A922BA0A27124C827AC32E1214CB8FD75`

系统要求：Windows 10/11 x64 与 Microsoft Edge WebView2 Runtime。

### 发布验证

- Backend pytest：142 passed
- Frontend Vitest：28 files，176 passed
- Frontend lint：PASS
- Frontend production build：PASS（2,804 modules transformed）
- Playwright E2E：25 passed
- Tauri/Rust tests：6 passed
- Tauri production build：PASS
- NSIS 真实安装、首次启动、sidecar 健康检查、来源/调度器/通知配置、保留式迁移、快捷方式和卸载：PASS
- 全新应用数据目录初始化、全部迁移与首次启动：PASS

### 已知限制

- 这是候选发布版，建议保留重要数据备份。
- 暂不提供移动端客户端。
- 前端生产构建仍会报告单个压缩前 JS chunk 大于 500 kB；不影响本次安装与运行验证。

---

## English

This is the first v0.7.0 release candidate of JLU Notice Monitor. It combines multi-source collection, cloud/local execution, notice processing, and the Windows desktop experience into an installable and upgrade-safe application.

### Highlights

- Introduces a unified Source Adapter and source-management architecture for official public, shared cloud, and local sources.
- Adds the public Jilin University OA campus-notice source without requiring login, including content, attachments, incremental fetches, and unified deduplication.
- Adds Cloud Preferred execution for official public sources. A configured local adapter is attempted serially when the cloud feed is missing, unreachable, invalid, timed out, or stale; one source run still produces one final result.
- Adds stable per-source identity, attempt diagnostics, and fallback-state presentation to prevent duplicate notices across cloud/local transitions.
- Completes the event-driven notification pipeline, Windows native notifications, permission guidance, local preferences, deadline reminders, daily summaries, and source-health alerts.
- Completes the Tauri 2 shell, managed FastAPI sidecar, dynamic loopback port, data-preserving database migrations, and per-user NSIS installation.
- Refines the responsive three-pane reader, filtering/search, read state, favorites, attachments, and distinct 404/network/timeout boundaries.

### Installation

Download `JLU Notice Monitor_0.7.0-rc1_x64-setup.exe` and verify it with the `.sha256` file attached to this Release.

SHA256: `079D234A3E466FFF8B6EE777A79DF50A922BA0A27124C827AC32E1214CB8FD75`

Requirements: Windows 10/11 x64 and Microsoft Edge WebView2 Runtime.

### Release validation

- Backend pytest: 142 passed
- Frontend Vitest: 28 files, 176 passed
- Frontend lint: PASS
- Frontend production build: PASS (2,804 modules transformed)
- Playwright E2E: 25 passed
- Tauri/Rust tests: 6 passed
- Tauri production build: PASS
- Real NSIS install, first launch, sidecar health, sources/scheduler/notification settings, data-preserving migration, shortcuts, and uninstall: PASS
- Empty application-data initialization, all migrations, and fresh first launch: PASS

### Known limitations

- This is a release candidate; keep backups of important data.
- A mobile client is not available yet.
- The frontend production build still warns that one pre-compression JavaScript chunk exceeds 500 kB. This did not affect installation or runtime validation.
