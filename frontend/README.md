# 吉大通知助手前端

`jlu-notice-monitor` 的响应式中文 Web UI。技术栈为 React、TypeScript、Vite、Tailwind CSS、TanStack Query 和 React Router。

## 开发

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

默认访问 `http://127.0.0.1:5173`，并连接 `http://127.0.0.1:8000`。后端地址只在 `src/api/client.ts` 集中读取 `VITE_API_BASE_URL`，便于未来由 Tauri 决定 sidecar 地址。

## 服务端数据查询

全部通知、收藏、分类 Feed、竞赛筛选和搜索均通过 TanStack Query 调用真实 FastAPI。分页、收藏、已读、来源、分类、截止状态与关键词筛选由 SQLite 查询完成；前端不再获取最多 100 条后本地筛选。

筛选条件、页码和每页数量都进入 query key。筛选变化会回到第一页，搜索输入带短防抖，翻页期间保留上一页内容以减少界面闪烁。

## 质量检查

```powershell
npm run lint
npm run build
```

## Phase 2.5 Architecture

```text
React Web UI
    │ VITE_API_BASE_URL
    ▼
FastAPI /api
    ▼
SQLite
```

未来桌面版本将由 Tauri 启动 Python FastAPI sidecar，轮询 `/api/health` 后加载本前端。本阶段尚未加入 Tauri、EXE 或 APK 打包代码。
