from abc import ABC, abstractmethod

import pytest
from langgraph.graph import StateGraph
from sqlalchemy import Engine

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

        engine = get_engine()
        reset_db()

        return engine
