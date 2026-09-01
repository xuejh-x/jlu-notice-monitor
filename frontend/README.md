# 吉大通知助手前端

`jlu-notice-monitor` 的响应式中文 UI。技术栈为 React、TypeScript、Vite、Tailwind CSS、TanStack Query、React Router 和 Tauri 2。

## 开发

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Web 开发默认访问 `http://127.0.0.1:5173`，并连接 `http://127.0.0.1:8000`。Desktop production 由 Tauri 选择动态 loopback 端口，并在 backend ready 后通过 `src/api/client.ts` 配置 API 地址；非 `127.0.0.1` 地址会被拒绝。

## Tauri Desktop

开发模式会先构建 sidecar，再自动启动 Vite、Tauri 和本地 Backend：

```powershell
Set-Location frontend
npm run desktop:dev
```

正式 NSIS 安装包使用 `npm run desktop:build` 构建。

## E2E 关键用户旅程

E2E 使用 Playwright 驱动本机安装的 Google Chrome（Chromium family），命令会自动启动隔离的 FastAPI test backend 与 Vite，不需要预先运行 `localhost:8000` 或 `localhost:5173`。本地无需下载 Playwright bundled Chromium；GitHub Actions 会显式安装并使用 bundled Chromium。

```powershell
npm run e2e
```

测试数据写入 `frontend/.e2e/runtime/data/notices.db`，每次 suite 启动前重新 seed，结束后自动清理，不会读取或修改 `backend/data/notices.db`。失败时 trace、截图和 HTML report 分别写入 `test-results/` 与 `playwright-report/`，这些目录均被 Git 忽略。

需要观察浏览器时可运行 `npm run e2e:headed`；交互调试可运行 `npm run e2e:ui`。

当前架构为：

```text
Tauri Window
    ↓
React Frontend
    ↓ localhost HTTP
FastAPI Backend
    ↓
SQLite
```

Tauri 自动启动 PyInstaller one-file Backend sidecar，等待 readiness 后再渲染 React 应用，并在退出时优先 graceful shutdown、超时后终止自有 child。单实例插件防止重复 scheduler；Web 模式的 `npm run dev` 继续保留。

通知原网页、附件和数据源网站在 Web 模式中使用浏览器新标签页，在 Tauri 中通过最小权限的 opener 插件交给系统默认浏览器。Tauri CSP 只允许本地前端资源、内部 IPC 和动态 `http://127.0.0.1:*` API；没有开放文件系统或任意前端 Shell 权限。

## 服务端数据查询

全部通知、收藏、分类 Feed、竞赛筛选和搜索均通过 TanStack Query 调用真实 FastAPI。分页、收藏、已读、来源、分类、截止状态与关键词筛选由 SQLite 查询完成；前端不再获取最多 100 条后本地筛选。

筛选条件、页码和每页数量都进入 query key。筛选变化会回到第一页，搜索输入带短防抖，翻页期间保留上一页内容以减少界面闪烁。

## 质量检查

```powershell
npm run lint
npm run build
npm run desktop:build
```

`npm run desktop:build` 会构建 production assets、Windows sidecar 和 current-user NSIS 安装器。安装后无需 Python、Node 或 Rust。
