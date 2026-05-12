import pytest

from db.database import database_url


def test_database_url_returns_env_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")

    assert database_url() == "sqlite:///explicit.db"


def test_database_url_raises_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        database_url()
