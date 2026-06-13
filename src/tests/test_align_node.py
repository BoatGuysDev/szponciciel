from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph

from config import settings
from logging_config import get_logger
from nodes import PersonaRunState
from nodes.video_assembly_graph.align_node.node import align_node
from nodes.video_assembly_graph.transforms import Word
from tests.base_test_class import BaseTestClass
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_align_error_handler = build_error_handler(
    log,
    "alignment.failed",
    "WhisperX alignment failed",
    context_keys=("audio_path",),
)

_MOCK_WORDS = [
    Word(text="Hello", start=0.0, end=0.5),
    Word(text="world", start=0.6, end=1.0),
]
_EXPECTED_TIMINGS = [
    {"text": "Hello", "start": 0.0, "end": 0.5},
    {"text": "world", "start": 0.6, "end": 1.0},
]


class TestAlignNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(align_node, retry_policy=LLM_RETRY, error_handler=_align_error_handler)
        graph.add_edge(START, "align_node")
        graph.add_edge("align_node", END)
        return graph

    @pytest.fixture(autouse=True)
    def mock_transcribe(self):
        with patch(
            "nodes.video_assembly_graph.align_node.node.transcribe_and_align",
            return_value=_MOCK_WORDS,
        ) as m:
            self.mock_transcribe = m
            yield m

    def test_missing_audio_file(self, graph: StateGraph):
        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "audio_path": "nonexistent.wav",
            }
        )

        assert result["is_fatal_error"]
        assert "Audio file not found" in result["error_message"]
        self.mock_transcribe.assert_not_called()

    def test_successful_alignment(self, graph: StateGraph, tmp_path):
        audio_file = tmp_path / "speech.wav"
        audio_file.write_bytes(b"")

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "audio_path": str(audio_file),
            }
        )

        self.mock_transcribe.assert_called_once_with(
            audio_file,
            device=settings.compute_device,
            model_size=settings.whisper_model,
        )
        assert not result.get("is_fatal_error")
        assert result["word_timings"] == _EXPECTED_TIMINGS

    def test_transcription_error(self, graph: StateGraph, tmp_path):
        audio_file = tmp_path / "speech.wav"
        audio_file.write_bytes(b"")
        self.mock_transcribe.side_effect = RuntimeError("model load failed")

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "audio_path": str(audio_file),
            }
        )

        assert result["is_fatal_error"]
        assert result["error_message"] == "WhisperX alignment failed: RuntimeError: model load failed"
