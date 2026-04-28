import pytest
from src.db import get_engine, reset_db


class BaseTestClass:
    """Base test class that provides common fixtures for all tests."""

    @pytest.fixture(autouse=True, name="engine")
    def setup_db(self):
        engine = get_engine()
        reset_db()
        return engine
