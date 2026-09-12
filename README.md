# JLU Notice Monitor

[中文文档](README_zh-CN.md)

> An extensible campus notification aggregation and intelligent
> notification platform.

JLU Notice Monitor is a cloud-first campus information aggregation
system designed to collect, process, and deliver important notifications
from official sources.

Although initially developed for Jilin University, the system is
designed with an extensible source architecture that allows integration
with other universities, departments, and organizations.

## Features

### Extensible Source Architecture

The system uses a unified source adapter architecture.

Supported source types: - University official websites - College and
department announcements - Public portal / OA notification systems -
Custom notification sources

Currently supported: - Jilin University OA public notices - College
announcement pages - Undergraduate education notices - Innovation and
entrepreneurship notices

### Intelligent Notification Processing

-   Incremental crawling
-   Content hash based deduplication
-   Notice update detection
-   Structured content extraction
-   Attachment extraction
-   Importance scoring
-   Deadline detection

### Cloud-first Hybrid Architecture

The system supports: - Cloud-first deployment - Local fallback
execution - Source-level execution policies

### Event-driven Notification System

Includes: - NotificationEvent - NotificationDelivery -
NotificationPreference

Supports Windows native notifications and local user preferences.

## Tech Stack

Backend: - Python - FastAPI - SQLite

Frontend: - React - TypeScript - Vite

Desktop: - Tauri - Windows Native Notification

Testing: - Pytest - Vitest - Playwright

## Current Status

Version: v0.6.0

Completed: - Cloud-first source architecture - Extensible source adapter
system - JLU OA public source integration - Incremental crawling
pipeline - Notification event system - Windows desktop notification UX

## License

To be determined.
