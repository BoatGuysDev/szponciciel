from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph

from nodes.select_background_node.node import select_background_node
from nodes.state import PersonaRunState
from tests.base_test_class import BaseTestClass


class TestSelectBackgroundNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(select_background_node)
        graph.add_edge(START, "select_background_node")
        graph.add_edge("select_background_node", END)
        return graph

    def test_sets_category_and_path(self, graph: StateGraph):
        provider = MagicMock()
        provider.get_video.return_value = Path("/media/satisfying/soap_low.mp4")

        with patch(
            "nodes.select_background_node.node.StockVideoProvider",
            return_value=provider,
        ):
            result = graph.compile().invoke({})

        assert "is_fatal_error" not in result
        assert result["background_video_path"] == "/media/satisfying/soap_low.mp4"
        assert result["video_category"] in {
            "fortnite",
            "galaxy",
            "minecraft",
            "satisfying",
            "subway_surfer",
            "temple_run",
            "trackmania",
            "ugc",
        }
        # category chosen by the node is the one passed to the provider
        request = provider.get_video.call_args.args[0]
        assert request.category == result["video_category"]

    def test_missing_media_returns_fatal_error(self, graph: StateGraph):
        provider = MagicMock()
        provider.get_video.side_effect = FileNotFoundError("no .mp4 files")

        with patch(
            "nodes.select_background_node.node.StockVideoProvider",
            return_value=provider,
        ):
            result = graph.compile().invoke({})

        assert result["is_fatal_error"] is True
        assert "Background selection failed" in result["error_message"]
