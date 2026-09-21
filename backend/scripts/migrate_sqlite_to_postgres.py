from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.cloud.migration import migrate_public_data
from app.database.migrations import run_phase15_cloud_data_migrations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy public notice facts from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", required=True, type=Path)
    parser.add_argument("--database-url", required=True, help="SQLAlchemy PostgreSQL URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = args.sqlite_path.expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"SQLite database does not exist: {source_path}")
    source_engine = create_engine(f"sqlite:///{source_path.as_posix()}")
    run_phase15_cloud_data_migrations(source_engine)
    target_engine = create_engine(args.database_url)
    if target_engine.dialect.name != "postgresql":
        raise SystemExit("--database-url must use a PostgreSQL dialect")
    with Session(source_engine) as source_db, Session(target_engine) as target_db:
        result = migrate_public_data(source_db, target_db)
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
