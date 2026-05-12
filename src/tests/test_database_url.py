from db.database import DEFAULT_DATABASE_URL, database_url


def test_database_url_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")

    assert database_url() == "sqlite:///explicit.db"


def test_database_url_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert database_url() == DEFAULT_DATABASE_URL
