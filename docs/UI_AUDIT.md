# JLU Notice Monitor UI Audit

Audit date: 2026-08-30
Scope: Gate 1 fact baseline only. No existing UI, interaction, API, or dependency was changed.

## Executive Summary

The frontend runs with its local FastAPI service and real SQLite data. Frontend lint, production build, and all existing backend tests pass. The shared application shell, list/card primitives, TanStack Query server state, and tested responsive layouts provide a sound baseline.

Gate 1 is PASS as an audit gate. There are no P0 findings, but six P1 issues should be planned before Gate 2 implementation. The clearest functional defect is an API/UI attachment DTO mismatch: the API returns filename/type while the UI reads name/title/file_type. All eight real attachments on notice #13 rendered as the fallback text “附件”.

## Environment Snapshot

| Item | Observed value | Notes |
| --- | --- | --- |
| Node.js | v24.16.0 | Local audit environment |
| npm / pnpm / yarn | 11.13.0 / 11.19.0 / not installed | npm lockfile and scripts are in use |
| React / React DOM | 19.2.8 / 19.2.8 | Runtime |
| TypeScript / Vite | 6.0.2 / 8.2.2 | Build stack |
| Tailwind CSS | 4.3.3 via @tailwindcss/vite | Styling |
| Router | react-router-dom 7.18.3 | BrowserRouter and declarative routes |
| UI component library | Radix Dialog 1.1.23 | Dialog/drawer primitive only |
| Icon library | lucide-react 1.35.0 | Icons |
| Server state | @tanstack/react-query 5.102.8 | staleTime 30 seconds; retry 1 |
| Local state | React state/context + localStorage | Theme, settings, shell state |
| Lint/format | oxlint 1.79.0; no Prettier found | npm run lint |
| Testing | No frontend runner; backend pytest | 43 backend tests |
| Playwright | Not a frontend dependency | Backend optional OA extra declares it |
| CI | Not found | No workflow/config located |
| Desktop wrapper | Tauri 2 | src-tauri is present |

Primary dependency roles: Radix provides accessible dialogs; TanStack Query owns HTTP cache/loading state; Tauri/API/opener support desktop and external links; clsx plus tailwind-merge resolve classes; date-fns formats dates; Lucide supplies icons. Dev dependencies provide Vite/React compilation, Tailwind integration, Oxlint, TypeScript, and Tauri tooling. No upgrade is recommended merely because a version is not latest.

tsconfig.app.json enables unused-local/parameter and fallthrough checks but does not enable TypeScript strict mode.

## Route Inventory

Source of truth: frontend/src/App.tsx. There are 16 explicit route definitions, including the wildcard fallback.

| Route | Component/Page | Purpose | Criticality |
| --- | --- | --- | --- |
| / | HomeRoute → DashboardPage or saved home | Default landing | High |
| /today | TodayPage | Newly found today | High |
| /deadlines | DeadlinesPage | Deadline feed | High |
| /competitions | CompetitionsPage | Filterable competition feed | High |
| /competitions/algorithm | FeedPage | Algorithm competition feed | Medium |
| /algorithm | redirect | Compatibility redirect | Low |
| /cybersecurity | FeedPage | Security feed | Medium |
| /training | TrainingPage / FeedPage | Training and internship feed | Medium |
| /research | FeedPage | Research/lab feed | Medium |
| /postgraduate | FeedPage | Postgraduate recommendation feed | Medium |
| /favorites | FavoritesPage | Saved notices | High |
| /notices | NoticesPage | Main searchable/filterable list | Critical |
| /notices/:id | NoticeDetailPage | Content, attachments, original link | Critical |
| /sources | SourcesPage | Source health | Medium |
| /settings | SettingsPage | Local preferences | Medium |
| * | redirect | Unknown-location fallback | Low |

## Component Inventory

src/components has 14 component files: 3 layout, 3 notice, 1 search, and 7 UI primitives. There are 11 page files.

| Component | Consumers | Problem | Recommendation |
| --- | --- | --- | --- |
| AppShell / NavItems | All routes | Navigation, crawler health, theme, and mobile drawer are densely co-located | Split only when a scoped Gate 2 change requires it |
| NoticeCard | NoticeList, DeadlinesPage | Favorite mutation/cache/toast and rendering are coupled | Extract a notice-action hook before more actions are added |
| NoticeRow | Dashboard | Repeats unread/category/source/date presentation from NoticeCard | Define a shared status/metadata display contract |
| NoticeList | Today, favorites, feeds, notices | Good list and empty boundary | Preserve it; standardize page loading/error ownership |
| Feedback | Most list pages | Dashboard maintains separate skeleton/error UI | Consolidate during a planned dashboard pass |
| Button/Card | Multiple | Raw button/card class sets still occur in pages/shell | Migrate only repeated controls when touching them |
| Form | Notices, competitions, settings | Filter option lists/reset behavior are repeated | Centralize filter model before reuse |
| SearchDialog | AppShell | Shortcut, query, and dialog are local-only | Move search to URL state in a later search/filter pass |
| CrawlerButton | AppShell | Polling/mutation/cache behavior and display are coupled | Extract controller when crawler functionality expands |

## State Map

| State class | State | Owner/source | Observed behavior | Risk |
| --- | --- | --- | --- | --- |
| Server | dashboard, important notices | React Query in DashboardPage | Cached 30s; retry once | Important-query error can look empty |
| Server | lists, feeds, today, deadlines, favorites | React Query per page | Keys include local filter/page inputs | Healthy baseline |
| Server | notice detail | React Query [notice,id] | Detail fetch triggers auto-read | Read ref does not reset by id |
| Server | sources/crawler | React Query in shell/button | 60s shell polling, 1.5s tracking polling | Shared key works |
| URL | pathname, notice id | React Router | Direct detail links work | Filters/search/page absent |
| Local UI | list filters/query/page | NoticesPage state | Filters reset page | Refresh/share/back cannot restore |
| Local UI | competition filters/page | CompetitionsPage state | Same local-only pattern | Same URL-state risk |
| Local UI | search, tabs, range, drawer | Individual components | Ephemeral as designed | Search context cannot be linked |
| Persisted | page size, threshold, home | localStorage settings | Saved immediately | Mounted consumers read snapshots, not reactive state |

## API Map

Shared client behavior in src/api/client.ts: JSON header, ApiError for network/non-2xx response. No AbortSignal, timeout, request cancellation, or per-endpoint retry. React Query globally uses staleTime 30 seconds, retry 1, and no refetch on window focus.

| Endpoint | Method | Consumer | Request / response | Loading / empty / error |
| --- | --- | --- | --- | --- |
| /api/dashboard | GET | Dashboard | DashboardData | Custom skeleton and retryable error |
| /api/notices/important | GET | Dashboard | Notice[] | Pending/empty; no explicit error branch |
| /api/notices | GET | Notices, feeds, competitions, favorites | NoticeFilters → PaginatedNotices | Shared skeleton/list empty/ErrorState |
| /api/notices/today | GET | Today | Notice[] | Shared states |
| /api/notices/deadlines | GET | Deadlines | days → Notice[] | Shared states and grouping |
| /api/notices/:id | GET | Detail | id → NoticeDetail | 404 is presented as offline |
| /api/search | GET | Search dialog | keyword → PaginatedNotices | Empty branch; error falls through to empty |
| /api/notices/:id/read or unread | POST | Detail auto-read | Typed Notice; API returns state payload | Failure is silent |
| /api/notices/:id/favorite or unfavorite | POST | Card/detail | Typed Notice; API returns state payload | Toast and cache invalidation |
| /api/sources | GET | Sources | Source[] | Shared states |
| /api/crawler/status | GET | Shell/crawler button | CrawlerStatus | Status polling |
| /api/crawler/run | POST | Crawler button | status payload | Tracking + toast; 409 becomes generic error |

Verified behavior: direct /notices/999999 returned backend 404 “Notice not found”, while the UI heading was “无法连接本地服务”. Real notice #13 returned eight attachments and all displayed as “附件”.

## TypeScript Audit

| Priority | Evidence | Finding |
| --- | --- | --- |
| P1 | Attachment type expects name/title/file_type; API serializes filename/type | Attachment display loses real labels |
| P1 | Read/favorite requests typed as Notice; API returns state object | Mutation response contracts are inaccurate |
| P2 | strict is omitted from tsconfig | Optional/null handling is less compiler-protected |
| P2 | updates is Array<Record<string, unknown>> | DTO and UI model are weakly mixed |
| P2 | Category/source/deadline unions include string | Resilient but reduces exhaustiveness |

No explicit any was found under src. The generic response.json cast has no runtime validation, so it depends on backend contract stability.

## Styling Audit

| File/component | Code pattern | Impact |
| --- | --- | --- |
| src/index.css | Raw hex foreground/background/focus colors | Global token layer is bypassed |
| AppShell.tsx | Arbitrary 72px/232px/sidebar and 1500px layout values | Intentional dimensions are unnamed |
| NoticeDetailPage.tsx | Arbitrary grid width and 15px text | Detail scale diverges from named utility scale |
| AppShell and pages | Repeated raw control/card classes | Future visual change costs multiple edits |
| Dashboard/detail/source | Repeated rounded border/shadow cards | “Card everywhere” pattern needs a future design decision |

No gradients were found. Overlay shadows and one backdrop blur are limited to transient layers; no visual judgment is inferred from their presence.

## Responsive Audit

Real local frontend at http://127.0.0.1:5173 ran with the real FastAPI backend at http://127.0.0.1:8000 and 76 notices.

| Viewport | Pages checked | Result |
| --- | --- | --- |
| 360×800 | Notices; notice #13 detail | No document-level horizontal overflow; long title and 8 attachments contained |
| 390×844 | Notices; sources; deadlines | No overflow; mobile navigation/filter controls rendered |
| 768×1024 | Notices | No overflow; desktop sidebar breakpoint rendered |
| 1366×768 | Dashboard; notices; detail | No overflow |
| 1440×900 | Notices | No overflow |

Long NoticeCard titles wrap; dashboard row titles truncate by design. Sources, badges, filters, detail content, attachments, and real empty states remained contained. Loading and real 5xx/network screens were source-reviewed but not screenshot-baselined; no synthetic behavior was introduced.

## Accessibility Audit

| Priority | Evidence | Impact / recommendation |
| --- | --- | --- |
| P1 | SearchDialog input has only a placeholder, no associated label or aria-label | Add a stable accessible name |
| P2 | NoticeCard/NoticeRow unread dot is visual-only | Announce unread state in text/semantics |
| P2 | Small informational text often uses zinc-400 on white | Measure intended combinations for contrast before palette edits |
| P2 | ErrorState calls every error “无法连接本地服务” | Recovery instructions are wrong for 404 and some server errors |
| P3 | Pages generally use h1 then h2 sections | Preserve heading structure |

Positive evidence: mostly-native link/button usage; form selects carry aria-label; global focus-visible styles cover links, buttons, inputs, and selects; Radix supplies dialog focus behavior; dialog titles exist; toasts use aria-live polite; status badges include text, not color only. Common controls are 36px+, above WCAG 2.2 AA’s 24px target minimum.

## Performance Baseline

| Metric | Observed result |
| --- | --- |
| Production build | PASS |
| Modules transformed | 2,783 |
| HTML | 0.60 kB; 0.41 kB gzip |
| CSS | 32.79 kB; 6.95 kB gzip |
| JS | 419.88 kB; 129.69 kB gzip |
| Output chunks | 1 JS and 1 CSS asset |
| Large static asset | hero.png exists but was not emitted/referenced in observed production output |
| Lighthouse LCP / CLS / INP/TBT | NOT MEASURED |

The single JS bundle is a baseline, not a defect by itself. No duplicate dependency was demonstrated.

## Test Coverage

| Test layer | Existing evidence | Status |
| --- | --- | --- |
| Frontend unit | None found | Missing |
| Frontend integration | None found | Missing |
| Frontend E2E/visual | None found | Missing |
| Backend unit/integration | 10 pytest files | 43 passed |
| Manual visual baseline | Two real browser screenshots | Added by this audit |

| Risk area | Existing automated coverage | Gate 1 evidence | Risk |
| --- | --- | --- | --- |
| Notice List | No frontend tests | Real list/filter UI | High |
| Search | No frontend tests | Real debounced empty search | High |
| Filter | Backend filter tests only | Read filter changed result to 0 | High |
| Notice Detail | No frontend tests | Real #13 data and attachments | Critical |
| Read/unread | Backend API tests only | Source review; no mutation made | Critical |
| Important/favorite | Backend API tests only | Source review; no mutation made | High |
| Attachments/original link | Backend API tests only | Attachment defect reproduced; links not opened | Critical |
| Loading | No frontend tests | Source review | Medium |
| Empty | No frontend tests | Real deadline/search empty states | Medium |
| Error | No frontend tests | Real 404 error state | High |
| Responsive | No frontend tests | Five viewport checks | High |

## Findings

| ID | Priority | Area | Evidence | Impact | Proposed Fix | Effort | Risk | Acceptance | Files |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-001 | P1 | API/type | API filename/type versus UI name/title/file_type; #13 reproduced | Attachment names/types hidden | Align DTO and add contract/UI test | S | Low | Real filename displayed | types/index.ts; NoticeDetailPage.tsx |
| F-002 | P1 | Error UX | Real 404 shown as offline service | Wrong recovery action | Distinguish 404, 4xx, network, 5xx | M | Low | Missing notice names resource issue | api/client.ts; Feedback.tsx; consumers |
| F-003 | P1 | URL state | Filter/page/search stay in component state; URL stayed /notices after filter | Context lost on refresh/share/back | Define search-param ownership | M | Medium | Deep link restores list state | NoticesPage.tsx; CompetitionsPage.tsx; search |
| F-004 | P1 | Request resilience | Shared fetch has no timeout/AbortSignal | Obsolete or hung work cannot stop | Add scoped cancellation/timeout policy | M | Medium | Search/navigation cancels stale work | api/client.ts; API modules |
| F-005 | P1 | Read state | Detail marked ref never resets by id | Later same-instance details may not auto-read | Reset/key side effect by id and test it | S | Low | Two unread routes each mark read | NoticeDetailPage.tsx |
| F-006 | P1 | Test gap | No frontend tests found | No regression safety for Gate 2 | Add small test harness for P1 paths | L | Medium | Detail/error/filter/read tests exist | frontend new config/tests |
| F-007 | P2 | Error UX | Dashboard important query lacks isError branch | Failure looks empty | Render retryable error | S | Low | Failed query is not empty state | DashboardPage.tsx |
| F-008 | P2 | API/type | Favorite/read mutation return types wrong | Future contract use can fail silently | Type state payloads correctly | S | Low | Types match backend | api/notices.ts; types/index.ts |
| F-009 | P2 | Settings state | loadSettings reads snapshots | Settings may need remount to apply | Reactive persisted settings source | M | Medium | Active consumer updates predictably | stores/settings.ts; consumers |
| F-010 | P2 | TypeScript | strict disabled | Nullability less protected | Plan incremental strict migration | M | Medium | Zero ignored strict errors | tsconfig.app.json |
| F-011 | P2 | Accessibility | Search label missing; unread dot visual only | Incomplete nonvisual access | Add label and semantic status | S | Low | Accessible-name/status checks pass | SearchDialog.tsx; notice components |
| F-012 | P2 | Styling | Raw values and repeated control/card classes | Design maintenance cost | Introduce narrow semantic tokens/primitives when touching areas | M | Low | High-use values have one source | index.css; shell/pages |
| F-013 | P3 | Search error | Error falls through to empty | Failure may look like zero results | Add error/retry branch | S | Low | Failed search identifies failure | SearchDialog.tsx |
| F-014 | P3 | Health signal | Pending crawler query says online | Brief misleading health state | Distinct pending/online semantics | S | Low | Online only after success | AppShell.tsx |

Counts: P0 0, P1 6, P2 6, P3 2.

## Quick Wins

1. Correct attachment and mutation DTOs.
2. Split error presentation by error class.
3. Reset read-mark lifecycle by notice id.
4. Add an accessible search label and unread semantics.
5. Render an error branch for Dashboard important notices.

## Unknowns / Blockers

- Lighthouse/web-vitals were not measured; no metric is inferred.
- Loading and true 5xx/network error layouts were not screenshot-baselined.
- Tauri window/external-opener behavior was not audited in this browser-only run.
- CI configuration was not found.

## Baseline Artifacts

- docs/ui-audit-baseline/desktop-1366x768-dashboard.jpg — real desktop dashboard.
- docs/ui-audit-baseline/mobile-390x844-notices.jpg — real mobile notice list/filter view.

## Commands Executed

- node --version
- npm --version
- pnpm --version
- yarn --version
- npm run lint
- npm run build
- .\.venv\Scripts\python.exe -m pytest
- .\.venv\Scripts\python.exe -m app serve
- npm run dev

The audit also used a local browser with real backend data to inspect routes, filter/search/empty/error states, DOM overflow, headings, and responsive baselines.

