from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import get_settings


@pytest.fixture()
def sqlite_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "memory_governance.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    get_settings.cache_clear()
    yield db_path
    get_settings.cache_clear()

