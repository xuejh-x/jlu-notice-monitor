# JLU Notice Monitor

[English](README.md)

吉林大学校园通知聚合与智能提醒系统。


项目目标是自动收集学校官方通知来源，通过增量抓取、内容去重、结构化解析、重要度分析和桌面通知，帮助学生及时获取重要信息。

## 功能特点

### 通知聚合

- 聚合学校官方通知来源
- 支持学院、部门等多来源接入
- 支持吉林大学 OA 校内通知公开源
- 基于 Cloud Source Registry 管理来源

### 信息处理

- 增量抓取
- 内容哈希去重
- 通知正文解析
- 附件提取
- 重要度评分
- 截止时间识别

### 通知提醒

- 事件驱动通知架构
- Windows 原生桌面提醒
- 通知状态管理
- 本地提醒偏好设置
- 通知权限引导

### 稳定性设计

- 来源健康监控
- 自动调度抓取
- Cloud-first 执行模式
- 完整测试体系

---

## 技术栈

后端：

- Python
- FastAPI
- SQLite


前端：

- React
- TypeScript
- Vite


桌面端：

- Tauri
- Windows Native Notification


测试：

- Pytest
- Vitest
- Playwright


---

## 项目架构

```
官方通知来源

        ↓

Cloud Source Registry

        ↓

Crawler

        ↓

Parser

        ↓

Deduplication

        ↓

Importance Analysis

        ↓

Notification Engine

        ↓

Windows Desktop App
```

---

## 当前状态

版本：

```
v0.6.0
```

已完成：

- Cloud-first 架构
- 官方来源统一管理
- 吉林大学 OA 公开通知接入
- 增量抓取与去重
- 通知事件系统
- Windows 桌面提醒

---

## License

To be determined.