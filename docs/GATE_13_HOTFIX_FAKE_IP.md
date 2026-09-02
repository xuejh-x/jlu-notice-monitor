# Gate 13 Hotfix — Proxy / Fake-IP Compatibility & Public Feed UX

## Result

PASS. Version remains `0.5.0`. Production and real JLU OA were not accessed.

## Minimal Architecture Audit

1. Local Custom HTML/RSS Test and Preview entered `preview_source()`, then used `GenericPublicSource` and `SafeFetcher`.
2. Cloud promotion entered `_cloud_preview()`, then used the same `GenericPublicSource` and `SafeFetcher` implementation.
3. URL syntax, DNS and IP classification live in `app/services/source_security.py`.
4. DNS resolution previously ran inside `validate_source_url()` for every hostname in both execution environments.
5. `SafeFetcher` disables automatic redirects and validates each redirect target before the next request.
6. Parsed notice and attachment URLs are validated by `GenericPublicSource` before use.
7. Root cause: Local and Cloud fetches shared the strict Cloud DNS/peer policy. A Desktop hostname resolved by the user's Fake-IP network to `198.18.1.29` was rejected before the proxy/network stack could fetch it.
8. `PUBLIC_FEED_NOT_CONFIGURED` was stored as a generic `SOURCE_ERROR`; Sources UI rendered both the danger badge and raw internal code.

## Validation Boundary Fix

- `validate_local_source_url()` accepts only HTTP(S), rejects invalid/credential-bearing URLs, explicit `localhost` names and unsafe direct IP literals. It does not classify DNS answers for ordinary hostnames, so Desktop proxy/VPN/Fake-IP resolution can proceed to the actual fetch.
- `validate_cloud_source_url()` retains strict DNS resolution and unsafe-address rejection. `validate_source_url()` remains a strict-Cloud compatibility entry point by default.
- `SafeFetcher.validation_scope` is explicit. Desktop preview and Desktop crawler configs use `local`; Cloud promotion and Cloud-role crawler configs use `cloud`.
- Only local fetching trusts HTTP proxy environment configuration. Cloud fetching retains DNS, redirect, actual-peer, notice-link and attachment validation.
- No `198.18.0.0/15` allowlist or hostname/site-specific exception was added.

## Public Feed UX

- The crawler now records `PUBLIC_FEED_NOT_CONFIGURED` as `cloud_unconfigured` instead of `source_error`.
- API projections also recognize legacy Gate 13 rows containing `SourceError: PUBLIC_FEED_NOT_CONFIGURED`, so an existing Desktop database receives the corrected UX without migration.
- Sources UI renders a neutral **云端尚未配置** badge and **等待 Notice Hub 公共源启用** helper text. It hides the raw internal code in normal UI.
- Other source errors retain the danger state and their diagnostic message.

## Fake-IP Regression Matrix

- Local normal hostname with mocked DNS `198.18.1.29`: reaches fetch; DNS classification is not invoked by Local validation.
- Local direct `http://198.18.1.29/`: rejected.
- Cloud direct `198.18.1.29`: rejected.
- Cloud hostname resolving to `198.18.1.29`: rejected.
- Cloud public hostname redirecting to `198.18.1.29`: rejected before the redirected request.
- Existing localhost, private IPv4/IPv6, link-local metadata, non-HTTP scheme, DNS, redirect, peer and attachment SSRF coverage remains enabled and passing.

## Blue Bridge Smoke

One Local Preview was performed against `https://dasai.lanqiao.cn/notices` in the reported Windows environment:

- Local DNS result: `198.18.1.29`.
- Fetch passed the Local validation boundary and reached the parser.
- Auto-detect result: HTML path; no parseable notice list was detected.
- Final response: `422 Source preview failed: This page is unsupported or needs advanced selector configuration`.
- This is a parser/configuration limitation, not an SSRF or network false positive. No site-specific selector was hardcoded.

## Verification

- Backend: `104 passed`.
- Frontend: `27 files / 137 tests passed`.
- Lint: PASS.
- TypeScript/Vite: PASS, 2,795 modules transformed.
- Rust fmt/check/clippy: PASS.
- Rust tests: `4 passed`.
- Playwright: `13 passed`.
- Visual QA: PASS at 1440×900 and 390×844; no horizontal overflow at 390px.

## Production Protection

- production server accessed: NO
- production changed: NO
- production database changed: NO
- production environment changed: NO
- Gate 10D soak modified: NO
- real JLU OA accessed: NO
