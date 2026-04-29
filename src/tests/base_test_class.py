import os
from abc import ABC, abstractmethod

import pytest
from sqlalchemy import Engine
from langgraph.graph import StateGraph
from dotenv import load_dotenv

from src.db import get_engine, reset_db

load_dotenv()

RUN_MODE = os.getenv("RUN_MODE")


class BaseTestClass(ABC):
    """Base test class that provides common fixtures for all tests."""

    @abstractmethod
    def create_graph(self) -> StateGraph:
        """Abstract fixture to create the graph for the test."""

        pass

    @pytest.fixture(autouse=True, name="engine")
    def setup_db(self) -> Engine:
        """Fixture to set up the database for each test."""

        if RUN_MODE != "test":
            raise Exception(
                "Tests must be run in test mode. Set RUN_MODE=test in your environment variables."
            )

        engine = get_engine()
        reset_db()

        return engine
