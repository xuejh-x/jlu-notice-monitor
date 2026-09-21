from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.paths import BACKEND_DIR


def main() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
