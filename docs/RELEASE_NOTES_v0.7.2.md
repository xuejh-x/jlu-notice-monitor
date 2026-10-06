# JLU Notice Monitor v0.7.2

## Changes

- Stop importing notices published before the configured retention cutoff (365 days by default), through both Cloud Feed and local crawlers. Skip detail requests when list metadata already identifies an expired notice.
- Prevent deleted historical notices from being re-created as NEW/unread after retention cleanup. The same cutoff applies to cleanup and every persistence entry point.
- Remove all existing notices outside the publication-date window, including unread, favorites and high-importance notices. Keep the cutoff date and notices with an unknown publication date.
- Extract dates from the enclosing list/table row when the date is beside a nested title, as on the Software College site.
- Correct the Computer Science College teaching-notice URL from a fixed historical page to the latest list.
- Update storage-cleanup descriptions and confirmation text to reflect the new policy.

## Verification

- Backend pytest: 171 passed, 1 skipped (PostgreSQL integration requires `JLU_TEST_POSTGRES_URL`).
- Frontend Vitest: 185 passed; lint and production build passed.
- E2E: 32 passed, including cleanup confirmation/cancellation at 1440px and 390px.
- Regression tests cover expired list/detail filtering, cutoff boundaries, unknown dates, normal new notices, and repeated cleanup/import cycles.
- Windows x64 NSIS build passed. A local in-place upgrade from v0.7.1 to v0.7.2 completed, and the installed client's backend health/version endpoints confirmed v0.7.2.
- Local upgrade preserved all pre-upgrade notices, read/favorite states, subscriptions, notification preferences and importance rules. The corrected Computer Science College entry imported 10 previously missed notices; a second real sync produced 0 NEW/0 UPDATED and no expired notices.

## Local installer

- File: `JLU Notice Monitor_0.7.2_x64-setup.exe`
- Size: 29,538,337 bytes.
- SHA-256: `392E107E84854BA163FE6375C138CF6E666CF674758D305E91E4A0AF2F50C0E9`.
- Local build/upgrade verified on 2026-10-06. This installer has not been uploaded to a GitHub Release.

## Data and upgrade notes

- No database schema migration is required.
- Existing expired records are now subject to automatic cleanup. Back up the local database before upgrading, especially if old favorites must be retained outside the app.
- Sources, subscriptions, preferences and retained notices' read states are not reset.
- This file documents the repository/local build; a GitHub Release has not yet been created for v0.7.2.

## Known limits

- PostgreSQL live-instance testing and the production Cloud chain remain unverified.
- Local upgrade validation is not a substitute for isolated Windows clean-install and comprehensive native-notification acceptance.
