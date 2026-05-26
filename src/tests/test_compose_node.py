import pytest
from pathlib import Path
from unittest.mock import patch
from langgraph.graph import StateGraph, START, END

from nodes import PersonaRunState
from nodes.compose_node.node import compose_node

from tests.base_test_class import BaseTestClass

_WORD_TIMINGS = [
    {"text": "Hello", "start": 0.0, "end": 0.5},
    {"text": "world", "start": 0.6, "end": 1.0},
]


class TestComposeNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(compose_node)
        graph.add_edge(START, "compose_node")
        graph.add_edge("compose_node", END)
        return graph

    @pytest.fixture(autouse=True)
    def mock_compose(self, tmp_path):
        def _create_output(video_path, audio_path, words, out_path, font_path=None):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"fake-mp4")
            return out_path

        with patch("nodes.compose_node.node.compose", side_effect=_create_output) as m:
            self.mock_compose = m
            yield m

    def _base_state(self):
        return {
            "run_id": "run-1",
            "persona_id": "persona-1",
            "audio_path": "runs/run-1/persona-1/speech.wav",
            "background_video_path": "media/satisfying/clip.mp4",
            "word_timings": _WORD_TIMINGS,
        }

    def test_successful_composition(self, graph: StateGraph):
        result = graph.compile().invoke(self._base_state())

        assert result.get("is_fatal_error") is None
        assert result["output_video_path"] == str(
            Path("runs/run-1/persona-1/output.mp4")
        )
        self.mock_compose.assert_called_once()

    def test_compose_error(self, graph: StateGraph):
        self.mock_compose.side_effect = RuntimeError("ffmpeg error")

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"]
        assert "Video composition failed" in result["error_message"]
