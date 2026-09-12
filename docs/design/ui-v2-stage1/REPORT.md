# UI v2 · Stage 1 验收报告

日期：2026-09-10。范围：基础布局；Stage 2–4 尚未实施。

## 设计与实现

唯一视觉参考为 `../figma-delivery/`，实施边界记录在 `../design.md`。现有 React / TypeScript / Tailwind CSS v4 体系继续使用，未添加依赖或 UI 框架。

| 文件 | 实施内容 |
|---|---|
| `frontend/src/components/layout/AppShell.tsx` | 全窗口布局、固定桌面三栏、紧凑侧栏、Header、底部同步区域、完整导航入口；中等宽度详情返回保持当前查询参数 |
| `frontend/src/components/layout/navigation.tsx` | 全部/未读/收藏/重要入口、六个现有来源快捷入口、来源管理与设置；保留原有完整导航 |
| `frontend/src/components/search/SearchDialog.tsx` | 搜索外观、宽高和收缩规则；搜索逻辑保持不变 |
| `frontend/src/index.css` | 语义主题变量、全局字阶/字体、尺寸变量与响应式布局 |
| `frontend/src/components/layout/AppShell.test.tsx` | 新导航、详情筛选选中状态、来源参数、完整导航及焦点恢复回归 |

Sidebar 计数只使用现有 dashboard 字段。来源快捷入口复用现有允许的 source 参数及名称；未虚构来源分组、收藏总数或各来源未读数。主题保留 light/dark/system 和现有持久化行为。

## 自动验证

| 检查 | 结果 |
|---|---|
| Backend `.venv/Scripts/python.exe -m pytest` | 126 passed |
| Frontend `npm test -- --run` | 28 个文件，152 项通过 |
| Frontend `npm run lint` | PASS |
| Frontend `npm run build` | PASS；仍有主包超过 500 kB 的构建体积提示 |
| `git diff --check` | PASS |

后端测试使用仓库虚拟环境；其基础 Python 位于用户安装目录，普通沙箱无法启动，获得自动审查许可后运行原命令通过。

## 浏览器验收

使用本地 Chrome、真实前后端及独立测试数据库。禁止启动定时抓取和启动同步；未操作实际用户数据库。测试通知来自仓库已有 E2E seed，截图中的 E2E 名称不是产品文案。8 个视图均无页面脚本错误或文档横向溢出。

| 视图 | 实测 |
|---|---|
| 1440×900 深色/浅色 | Sidebar 282px；List 574px；Reader 584px；Header 56px；内容高 844px |
| 768×900 列表/详情 | 72px 侧栏 + 696px 内容；详情具有返回列表入口 |
| 390×844 列表/详情 | 单栏；保留底部导航和详情返回能力 |
| 1440×900 Sources / Settings | 页面可达、正常渲染，沿用原有页面内容 |

完整测量见 [geometry.json](geometry.json)。截图：[桌面深色](desktop-dark.png)、[桌面浅色](desktop-light.png)、[768 列表](tablet-list.png)、[768 详情](tablet-reader.png)、[390 列表](mobile-list.png)、[390 详情](mobile-reader.png)、[Sources](desktop-sources.png)、[Settings](desktop-settings.png)。已逐张检查截图。

## 不变边界与后续

后端、API 客户端、数据类型、URL 参数解析、路由定义、自动已读、请求取消、错误类型和 OA 接口均无代码修改。通知列表、详情、来源管理、设置的页面组件未修改。未在本阶段重新执行真实 OA 登录或远端抓取。

当前截图展示的是 Stage 1 的最终状态：通知行、标签与截止标识的结构细化留到 Stage 2；Reader 内部工具栏、元信息、正文和附件留到 Stage 3；Sources / Settings 内容布局留到 Stage 4。全局字体和颜色会自然应用于这些既有页面。

Stage 1 完成，按要求暂停。
