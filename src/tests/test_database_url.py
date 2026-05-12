from db.database import DEFAULT_DATABASE_URL, database_url


def _clear_env(monkeypatch) -> None:
    for var in ("DATABASE_URL", "RUN_MODE"):
        monkeypatch.delenv(var, raising=False)


def test_database_url_env_var_wins_over_run_mode(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")
    monkeypatch.setenv("RUN_MODE", "test")

    assert database_url() == "sqlite:///explicit.db"


def test_database_url_falls_back_to_in_memory_for_test_mode(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("RUN_MODE", "test")

    assert database_url() == "sqlite:///:memory:"


def test_database_url_defaults_outside_test_mode(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("RUN_MODE", "development")

    assert database_url() == DEFAULT_DATABASE_URL


def test_database_url_defaults_when_run_mode_unset(monkeypatch):
    _clear_env(monkeypatch)

    assert database_url() == DEFAULT_DATABASE_URL
