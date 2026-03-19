"""Schema initialization."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.store.sqlite import connect


def run_migrations(settings: Settings) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")
    connection = connect(settings)
    try:
        connection.executescript(sql)
    finally:
        connection.close()

