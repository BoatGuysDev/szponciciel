import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from langgraph.graph import StateGraph, START, END

from nodes import PersonaRunState
from nodes.compose_simple_node import compose_simple_node

from tests.base_test_class import BaseTestClass


class TestComposeSimpleNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(compose_simple_node)
        graph.add_edge(START, "compose_simple_node")
        graph.add_edge("compose_simple_node", END)
        return graph

    @pytest.fixture(autouse=True)
    def mock_moviepy(self):
        mock_audio = MagicMock()
        mock_audio.duration = 5.0

        mock_bg = MagicMock()
        mock_bg.without_audio.return_value = mock_bg
        mock_bg.with_audio.return_value = mock_bg

        with (
            patch(
                "nodes.compose_simple_node.AudioFileClip", return_value=mock_audio
            ) as mock_ac,
            patch(
                "nodes.compose_simple_node.VideoFileClip", return_value=mock_bg
            ) as mock_vc,
            patch(
                "nodes.compose_simple_node.fit_vertical", return_value=mock_bg
            ) as mock_fv,
            patch(
                "nodes.compose_simple_node.loop_to_duration", return_value=mock_bg
            ) as mock_ld,
        ):
            self.mock_audio_cls = mock_ac
            self.mock_video_cls = mock_vc
            self.mock_fit_vertical = mock_fv
            self.mock_loop_to_duration = mock_ld
            self.mock_audio = mock_audio
            self.mock_bg = mock_bg
            yield

    def _base_state(self):
        return {
            "run_id": "run-1",
            "persona_id": "persona-1",
            "audio_path": "runs/run-1/persona-1/speech.wav",
            "background_video_path": "media/satisfying/clip.mp4",
        }

    def test_successful_simple_composition(self, graph: StateGraph):
        result = graph.compile().invoke(self._base_state())

        assert result.get("is_fatal_error") is None
        assert result["output_video_path"] == str(
            Path("runs/run-1/persona-1/output.mp4")
        )
        self.mock_audio_cls.assert_called_once_with("runs/run-1/persona-1/speech.wav")
        self.mock_video_cls.assert_called_once_with("media/satisfying/clip.mp4")
        self.mock_fit_vertical.assert_called_once()
        self.mock_loop_to_duration.assert_called_once_with(self.mock_bg, 5.0)
        self.mock_bg.write_videofile.assert_called_once()

    def test_moviepy_error(self, graph: StateGraph):
        self.mock_audio_cls.side_effect = RuntimeError("codec not found")

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"]
        assert "Simple composition failed" in result["error_message"]
