# JLU Notice Monitor

[English](README.md) | 中文

> 聚合、去重、筛选并主动提醒官方校园通知的 Windows 桌面应用。

当前版本：**v0.7.0-rc1**

JLU Notice Monitor 帮助学生集中查看原本分散在学校和学院网站上的重要通知。当前内置吉林大学相关来源，但来源适配器架构不永久绑定吉林大学，可扩展到其他高校和公共组织。

![JLU Notice Monitor 桌面界面](docs/design/ui-v2-stage3.3/after-1440x900.png)

## 核心功能

- 聚合多个官方通知来源。
- 支持增量抓取、内容哈希去重和通知更新检测。
- 提取正文、附件、分类、重要度和截止日期。
- 提供搜索、来源/分类筛选、已读状态、收藏和响应式布局。
- 官方公开来源采用云端优先策略；云端 Feed 不可用或过期时可安全地回退到本地适配器。
- 根据本地的重要度、截止时间、静默时段和来源健康偏好发送 Windows 原生通知。
- 数据库与个人偏好保存在用户应用数据目录中，升级不会替换这些数据。

## 已支持来源

v0.7.0-rc1 内置适配器包括：

- 吉林大学 OA 校内公开通知
- 吉林大学网络安全学院
- 吉林大学计算机科学与技术学院
- 吉林大学软件学院
- 吉林大学本科生院
- 吉林大学创新创业教育学院

来源管理架构也支持增加其他公开来源或本地来源。上游网站临时离线或页面结构变化时，对应来源仍可能暂时不可用。

## 系统架构

```text
官方来源 / 云端 Feed
          |
       来源适配器
          |
   FastAPI 处理流水线
 抓取 -> 解析 -> 去重
      -> 分类 -> 提醒
          |
       SQLite 数据
          |
 React + TypeScript 界面
          |
  Tauri 2 Windows 桌面应用
```

生产安装包包含 Tauri 应用和受管的 FastAPI 后端 sidecar。Sidecar 只监听动态分配的本机回环端口。源码、Python 环境、Node 模块、开发工具、数据库和日志不会进入安装包。

## Windows 安装

1. 打开 `v0.7.0-rc1` 对应的 GitHub Release。
2. 下载 `JLU Notice Monitor_0.7.0-rc1_x64-setup.exe` 及其 SHA256 校验值。
3. 在 PowerShell 中校验文件：

   ```powershell
   Get-FileHash -Algorithm SHA256 '.\JLU Notice Monitor_0.7.0-rc1_x64-setup.exe'
   ```

4. 运行安装器，然后从开始菜单或快捷方式启动 **JLU Notice Monitor**。

系统要求为 Windows 10/11 x64，并需要 Microsoft Edge WebView2 Runtime。受支持的 Windows 通常已包含 WebView2；若运行环境缺失，请先从 Microsoft 安装当前 Runtime。

该版本仍是候选发布版。请备份重要数据，并通过仓库 GitHub Issues 反馈问题。

## 开发

前置环境：

- Python 3.12 或更高版本（项目 CI 与发布环境使用 Python 3.13）
- Node.js 24 与 npm
- 与 Rust 1.77.2 或更高版本兼容的 Rust 工具链
- Windows 桌面打包所需的 NSIS 环境

配置后端：

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,desktop]'
.\.venv\Scripts\python.exe -m pytest
```

配置并验证前端：

```powershell
Set-Location frontend
npm ci
npm test -- --run
npm run lint
npm run build
npm run e2e
```

构建 Windows 生产安装包：

```powershell
Set-Location frontend
npm run desktop:build
```

构建脚本会先生成 PyInstaller 后端 sidecar，再构建前端和 Tauri NSIS 安装包。本地配置应基于 `.env.example` 文件创建，禁止提交凭据或运行时数据。

## 仓库结构

- `backend/` — FastAPI 应用、抓取器、SQLite 模型和 pytest 测试
- `frontend/` — React/Vite 界面、Vitest/Playwright 测试和 Tauri 壳层
- `docs/` — 设计契约、实施报告与验证证据

## 许可

项目当前尚未声明统一的开源许可证。公开源码不代表自动授予再分发或演绎作品权限；第三方资源继续遵循其同目录中记录的许可证。
