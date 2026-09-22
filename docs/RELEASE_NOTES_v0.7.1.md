# JLU Notice Monitor v0.7.1

## Fixes

- Fixed a Cloud-first source fallback issue where a first successful local crawl could treat historical notices as new and unread after the Cloud Feed was unavailable.
- Added a source-level local fallback baseline. Historical notices imported during that first successful fallback are stored as read baseline records and do not generate NEW notification events.
- Kept Cloud Feed baseline behavior independent from local fallback baseline behavior.

## Verification

- Backend pytest: 163 passed, 1 skipped (the PostgreSQL integration suite requires `JLU_TEST_POSTGRES_URL`).
- Frontend Vitest: 185 passed.
- E2E: 32 passed.
- Windows Desktop build passed.

## Data notes

- No database schema migration is required.
- This release does not automatically change existing incorrect unread records created by earlier versions.
- Existing historical pollution requires separate, explicit handling; this release prevents new occurrences through the Cloud-first local fallback path.

## Known limits

- PostgreSQL live-instance testing and the production Cloud service chain have not been completed.
- Real Windows clean-install and upgrade acceptance remain manual verification steps.
