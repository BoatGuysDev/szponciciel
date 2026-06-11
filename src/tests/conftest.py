import os

# Pin every test in this session to an in-memory SQLite DB. Setting this at
# conftest-import time runs before pytest collects any test module, so the
# lazy `db.database._engine` initialisation can never resolve a real file.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


def pytest_configure(config):
    """Refuse to run tests against anything other than in-memory SQLite."""

    from db.database import database_url, reset_engine

    reset_engine()
    resolved = database_url()
    if resolved != "sqlite:///:memory:":
        raise RuntimeError(f"Tests must run against in-memory SQLite; resolved {resolved!r}")
