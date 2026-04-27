import pytest
from sqlmodel import Session

from src.db import get_test_engine


class BaseTestClass:
    """Base test class that provides common fixtures for all tests."""

    @pytest.fixture(name="session")
    def init_session(self):
        engine = get_test_engine()
        with Session(engine) as session:
            yield session
