# 通知存储生命周期

## 留存规则

默认保留期为 365 天。通知的 `publish_date` 早于当前日期减 365 天时可被清理；没有发布日期的通知则按 `first_seen_at` 判断。通过 `JLU_RETENTION_DAYS` 可调整保留天数，默认值为 365。

## 云端与本地处理

- Cloud 部署会清理所有超过保留期的通知。清理前会删除绑定到该通知的 `NotificationEvent`，其 `NotificationDelivery` 继续由既有级联外键删除；附件元数据、来源关系、更新记录和用户状态由既有通知外键删除。
- Desktop/standalone 本地库在相同日期规则外，保留未读、已收藏以及重要度分数不低于 80 的通知。高重要度阈值可由 `JLU_RETENTION_HIGH_IMPORTANCE_SCORE` 调整。
- 两种部署都不会删除 `Source`、来源配置或与待删除通知无关的元数据。

## 自动与手动清理

应用启动时会检查清理是否到期，随后复用既有 crawler scheduler 在每次调度后检查。实际清理最多每 24 小时执行一次（可由 `JLU_RETENTION_CLEANUP_INTERVAL_HOURS` 调整），上次完成时间存放在已有 `app_state` 表中。因此重复触发是安全且幂等的。

设置页的“存储管理”提供手动清理。它总是显示当前数据库大小、通知数量、可清理数量和上次清理时间；用户必须在确认对话框中明确确认后才会调用清理接口。

## API

- `GET /api/storage/status`：返回 `database_size`、`database_size_bytes`、`total_notifications`、`cleanup_candidates`、`last_cleanup_at`、`retention_days` 与本地例外是否生效。
- `POST /api/storage/cleanup`：立即执行当前部署角色对应的规则，并返回已删除数量和刷新后的状态。

SQLite 的数据库大小来自页面数与页面大小；PostgreSQL 使用其数据库大小函数。删除不会主动执行 `VACUUM`，避免在正常使用时造成长时间数据库锁定；空间会在数据库后续维护时回收。
