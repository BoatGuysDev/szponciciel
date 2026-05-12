from abc import ABC, abstractmethod

import pytest
from sqlalchemy import Engine
from langgraph.graph import StateGraph

from config import settings
from db import get_engine, reset_db


class BaseTestClass(ABC):
    """Base test class that provides common fixtures for all tests."""

    @abstractmethod
    def create_graph(self) -> StateGraph:
        """Abstract fixture to create the graph for the test."""

        pass

    @pytest.fixture(autouse=True, name="engine")
    def setup_db(self) -> Engine:
        """Fixture to set up the database for each test."""

        if settings.run_mode != "test":
            raise Exception(
                "Tests must be run in test mode. Set RUN_MODE=test in your environment variables."
            )

        engine = get_engine()
        reset_db()

        return engine
