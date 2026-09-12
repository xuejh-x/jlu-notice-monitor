# JLU Notice Monitor v0.7.0-rc2

## 中文

v0.7.0-rc2 是面向外部用户的第二个 v0.7.0 候选发布版，重点修复 RC1 中通知列表筛选、统计语义与分页结果不一致的问题，并保留既有的云端优先来源架构和 Windows 桌面能力。

### 主要更新

- 修复通知筛选条件已显示但列表未及时刷新、结果数量不变化的问题；应用筛选后会关闭对话框并按 URL 查询状态重新请求后端。
- 日期、分类、来源、最低优先级、截止状态、已读/未读和收藏状态均实际参与服务端查询。
- 明确区分当前筛选结果 `total_count`、当前结果中的未读数量 `unread_count` 与全库通知数量 `all_count`，分页以 `total_count` 为准。
- 改进通知列表筛选、加载、清空筛选和分页体验，并保持 RC1 URL/query schema 兼容。
- 延续 Cloud-first 来源架构、吉林大学 OA 校内公开通知、Cloud Preferred 本地回退与稳定去重能力。
- 延续 Windows 原生通知、截止提醒、每日摘要、来源健康提醒和本地通知偏好。
- 支持从 v0.7.0-rc1 原位升级，并保留本地数据库、阅读状态、收藏与设置。

### 安装

下载 `JLU Notice Monitor_0.7.0-rc2_x64-setup.exe` 和对应 `.sha256` 文件，校验后运行安装器。

SHA-256：`9B039F17BAFAD09E37B319148C22880726384C7A9B5C04B976123F81F2A2B5AE`

系统要求：Windows 10/11 x64 与 Microsoft Edge WebView2 Runtime。

### 发布验证

- Backend pytest：146 passed
- Frontend Vitest：28 files，182 passed
- Frontend lint：PASS
- Frontend production build：PASS
- Playwright E2E：30 passed
- Tauri/Rust tests：6 passed
- PyInstaller sidecar、Tauri release 与 NSIS bundle：PASS
- RC1 原位升级：PASS，数据库、阅读状态、收藏与设置均保留
- 全新安装与首次数据库初始化：PASS
- 应用退出、sidecar 清理与静默卸载：PASS；卸载移除程序文件并保留运行数据

### 已知限制

- 这是候选发布版，建议保留重要数据备份。
- 暂不提供移动端客户端。
- 前端生产构建仍可能报告单个压缩前 JavaScript chunk 大于 500 kB；不影响安装与运行。

---

## English

v0.7.0-rc2 is the second externally distributable v0.7.0 release candidate. It focuses on the RC1 notice-filtering, count-semantics, and pagination inconsistencies while preserving the existing cloud-first source architecture and Windows desktop capabilities.

### Highlights

- Fixes the case where active filter controls were visible while the notice list and result count still showed previous data. Applying filters now closes the dialog and refreshes from the URL-backed query state.
- Ensures date, category, source, minimum importance, deadline, read/unread, and favorite filters all affect the server query.
- Separates filtered `total_count`, filtered unread `unread_count`, and global `all_count`; pagination is based on `total_count`.
- Improves filtering, loading, clearing, and pagination behavior while retaining the RC1 URL/query schema.
- Retains the cloud-first source architecture, public Jilin University OA notices, Cloud Preferred local fallback, and stable deduplication.
- Retains Windows native notifications, deadline reminders, daily summaries, source-health alerts, and local notification preferences.
- Supports in-place upgrades from v0.7.0-rc1 while preserving the local database, read state, favorites, and settings.

### Installation

Download `JLU Notice Monitor_0.7.0-rc2_x64-setup.exe` and its `.sha256` file, verify the checksum, and run the installer.

SHA-256: `9B039F17BAFAD09E37B319148C22880726384C7A9B5C04B976123F81F2A2B5AE`

Requirements: Windows 10/11 x64 and Microsoft Edge WebView2 Runtime.

### Release validation

- Backend pytest: 146 passed
- Frontend Vitest: 28 files, 182 passed
- Frontend lint: PASS
- Frontend production build: PASS
- Playwright E2E: 30 passed
- Tauri/Rust tests: 6 passed
- PyInstaller sidecar, Tauri release build, and NSIS bundle: PASS
- RC1 in-place upgrade: PASS; database, read state, favorites, and settings preserved
- Clean installation and first database initialization: PASS
- Application exit, sidecar cleanup, and silent uninstall: PASS; program files removed and runtime data preserved

### Known limitations

- This is a release candidate; keep backups of important data.
- A mobile client is not available yet.
- The production frontend may still warn that a pre-compression JavaScript chunk exceeds 500 kB; this does not affect installation or runtime behavior.
