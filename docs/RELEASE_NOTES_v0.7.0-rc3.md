# JLU Notice Monitor v0.7.0-rc3

## Highlights

- Cloud Feed first sync now establishes a local baseline, so historical notices do not appear as new or unread.
- OA public-detail parsing supports additional rich-text layouts and distinguishes empty bodies from parser failures.
- Unread-list navigation preserves the current row after reading; paging recalculates against current data.
- The notice list now supports confirmed, idempotent “mark all read”.
- Cloud PostgreSQL deployment, migration, and public-feed support are included.

## Data compatibility

No Desktop SQLite schema migration is required for these fixes. Existing historical NEW/unread false positives are intentionally not cleared automatically because they cannot be safely distinguished from genuine notifications with the available data.

## Verification limits

The installer is built and hashed locally. Real Windows clean-install/upgrade testing, production PostgreSQL verification, and live Cloud/OA integration require an isolated environment and remain manual verification steps.
