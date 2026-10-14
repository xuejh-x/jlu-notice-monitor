# 通知搜索与列表同步修复

日期：2026-10-11。直接修复现有工作区；未提交、推送、修改版本号或构建安装包。

## 根因与现有状态流

- `SearchDialog.tsx` 通过 `/api/search` 查询，点击结果只导航到 `/notices/:id`，丢失原有列表 URL 参数。
- `AppShell.tsx` 已从路由解析当前 ID，并将同一个 ID 传给 `NoticesPage` 和 `NoticeDetailPage`，因此无需再引入选中状态。
- `NoticesPage.tsx` 从 URL 解析关键词、分类、来源、日期、阅读状态等参数，通过 `['notices', 'all', requestFilters]` 查询当前页。列表为服务端分页，无虚拟滚动，也没有自动定位逻辑。
- `NoticeList` 只渲染当前页的 `items`；目标不在当前页时，即使 `selectedId` 正确，也没有可以高亮的条目。
- 后端 `/api/search` 复用 `list_notices` 和同一序列化逻辑，搜索结果、普通列表和详情使用同一个数据库通知 ID；问题不在 ID 映射。

## 修改与同步机制

1. `frontend/src/components/search/SearchDialog.tsx`：从通知工作区搜索打开详情时保留 `location.search`；从设置等其他页面搜索时不携带无关参数。
2. `frontend/src/pages/NoticesPage.tsx`：复用详情的 `['notice', id]` 查询。当前 ID 不在本页时，在列表滚动区顶部展示带说明的 compact 临时条目；在本页时只高亮原条目。
3. 详情和临时条目共享 React Query 缓存、请求去重、AbortSignal 和阅读/收藏状态更新。没有复制通知对象到独立状态，也没有新增选中 ID。切换 ID 后，旧请求的结果不能成为新 ID 的条目。
4. 选择或加载完成后，只调整通知列表容器的 `scrollTop`；临时条目的说明和条目一起进入视区。`ResizeObserver` 处理从窄屏详情切回双栏时的定位。
5. 清空/关闭全局搜索不改变当前详情；关闭详情后，临时条目与高亮消失。直接刷新详情 URL 也能通过相同机制恢复定位。
6. 全部已读成功后额外使详情缓存失效，避免当前详情和临时条目保留旧的未读状态。自动已读及手动阅读状态的原有实现不改动。
7. 在修改代码前同步 `docs/design/design.md`，说明临时展示和滚动规则；复用现有语义颜色及通知行，无新 token。

## 分页与筛选冲突

采用临时展示当前通知的方案，保留用户原有关键词、分类、来源、日期、未读等筛选及页码。说明明确标为“当前打开的通知（不在本页结果中）”，不混入服务端 `items`，不增加结果总数、未读数或页数。

选择此方案是因为 API 没有按 ID 定位页码的接口，目标也可能不符合筛选。临时展示无需扫描全库或悄悄清空筛选。切换到包含目标的页面后，临时条目自动消失；刷新结果排除当前通知时，临时条目自动恢复。详情加载失败或 404 时沿用现有错误契约，不用旧临时条目冒充有效结果。

## 验证

| 检查 | 最终结果 |
| --- | --- |
| `npm test -- --run` | 29 个文件，212 项通过；新增 13 项工作区集成测试 |
| `npm run lint` | 通过，无 warning |
| `npm run build` | TypeScript 与 Vite 通过；仍有既有的 >500 kB chunk 提示 |
| 相关 Playwright 浏览器回归 | 18 项通过：新增 6 项，既有 12 项 |
| `git diff --check` | 通过 |

新增集成测试文件：`frontend/src/components/layout/NoticeSelection.test.tsx`。覆盖普通列表打开、已有搜索目标、分页外目标、多筛选排除、快速连续选择及旧详情晚返回、清空搜索/关闭详情、自动已读、手动未读/全部已读、换页、刷新列表后的去重与恢复、直接详情 URL、非工作区搜索、404 和列表请求失败。

新增浏览器测试文件：`frontend/e2e/notice-selection.spec.ts`。1440×900、768×900、390×900 各验证本页目标与分页/筛选外目标；检查高亮唯一性、选中行实际进入列表视区、说明可见、刷新恢复、窄屏返回、窄屏扩大为双栏后的定位、无横向溢出及 document 未被滚动。已查看桌面临时条目、768 详情、390 详情及返回列表截图。

浏览器使用本机 Chrome 和隔离 E2E 数据库；列表分页极端场景使用显式 MOCK / FIXTURE 数据，搜索和详情使用真实测试后端。既有浏览器用例验证真实 API 的分页、分类/来源/日期/阅读筛选、清除筛选、搜索、收藏、自动已读、手动未读及 404。

最终浏览器命令：

```powershell
npm run e2e -- notice-selection.spec.ts critical-journeys.spec.ts --grep 'search selection|Notices|Inline search|Auto-read|Mark unread|manually unread|Unknown notice|Favorite →'
```

浏览器日志位于 `frontend/.e2e/notice-selection-validation.log`，截图位于 `frontend/test-results/notice-selection-*/`（均为忽略的测试产物，下次执行可能覆盖）。首次启动测试后端时沙箱拒绝执行系统 Python 3.13；获准在沙箱外运行隔离本地回归后完成验证，未修改虚拟环境。

## 验证范围

未构建或运行打包后的 Tauri 安装程序，未在用户生产数据库及真实 OA 联网环境执行验证。未修改后端代码或 API，未运行全量后端 pytest；相关后端搜索/详情/阅读接口已由上述浏览器测试调用。浅色截图经过检查；本轮未另做深色主题截图验收，也未变更主题样式。
