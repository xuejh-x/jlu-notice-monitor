# JLU Notice Monitor

[中文文档](README_zh-CN.md)

A cloud-first campus notification aggregation system with incremental crawling, source health monitoring, and event-driven desktop notifications.

The system automatically aggregates official university notification sources, performs incremental crawling, content deduplication, importance analysis, deadline extraction, and delivers notifications through a Windows desktop application.

## Features

### Multi-source Notification Aggregation

- Official university notification sources
- College and department announcements
- JLU OA public notification source
- Cloud Source Registry architecture

### Intelligent Processing

- Incremental crawling
- Content hash based deduplication
- Structured notice extraction
- Importance scoring
- Deadline detection
- Attachment extraction

### Notification System

- Event-driven notification architecture
- Notification state management
- Windows native desktop notifications
- Notification permission guidance
- Local notification preferences

### Reliability

- Source health monitoring
- Scheduler based automatic crawling
- Cloud-first source execution
- Regression testing system

---

## Architecture

```
Official Sources
        |
        v
Cloud Source Registry
        |
        v
Crawler
        |
        v
Parser & Extraction
        |
        v
Deduplication
        |
        v
Importance & Deadline Analysis
        |
        v
Notification Engine
        |
        v
Windows Desktop Application
```

---

## Tech Stack

### Backend

- Python
- FastAPI
- SQLite

### Frontend

- React
- TypeScript
- Vite

### Desktop

- Tauri
- Windows Native Notification

### Testing

- Pytest
- Vitest
- Playwright

---

## Project Status

Current version:

```
v0.6.0
```

Completed:

- Cloud-first Source Architecture
- Official Cloud Source Registry
- JLU OA Public Source Integration
- Incremental Crawling System
- Notification Event Pipeline
- Windows Desktop Notification UX
- Source Health Foundation

