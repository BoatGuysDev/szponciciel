import pytest
from pathlib import Path
from unittest.mock import patch
from langgraph.graph import StateGraph, START, END
from sqlmodel import Session
from sqlalchemy import Engine

from src.nodes import tts_node, PersonaRunState
from src.models import Persona

from .base_test_class import BaseTestClass


class TestTtsNode(BaseTestClass):
    """Tests for the TTS node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(tts_node)
        graph.add_edge(START, "tts_node")
        graph.add_edge("tts_node", END)

        return graph

    @pytest.fixture(autouse=True)
    def mock_tts(self):
        with patch("src.nodes.tts_node._tts") as mock_tts_instance:
            self.mock_tts_instance = mock_tts_instance
            yield mock_tts_instance

    def _seed_persona(self, engine: Engine, **kwargs):
        defaults = {
            "id": "persona-1",
            "tiktok_account_id": "tiktok-news",
            "language": "en",
            "voice_speaker": "default_speaker",
            "voice_speaker_wav": None,
        }
        defaults.update(kwargs)

        with Session(engine) as session:
            persona = Persona(**defaults)
            session.add(persona)
            session.commit()

    def test_missing_persona(self, graph: StateGraph):
        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "nonexistent",
                "narration": "Some narration text.",
            }
        )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Persona with id nonexistent not found."

    def test_empty_narration(self, graph: StateGraph, engine: Engine):
        self._seed_persona(engine)

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "narration": "",
            }
        )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Narration text is empty."

    def test_successful_tts_with_speaker_wav(self, graph: StateGraph, engine: Engine):
        self._seed_persona(
            engine, voice_speaker_wav="path/to/voice.wav", voice_speaker=None
        )

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "narration": "Hello, this is a test narration.",
            }
        )

        audio_path = str(Path("runs/run-1/persona-1/speech.wav"))

        self.mock_tts_instance.tts_to_file.assert_called_once_with(
            text="Hello, this is a test narration.",
            file_path=audio_path,
            language="en",
            speaker_wav="path/to/voice.wav",
        )

        assert result.get("is_fatal_error") is None
        assert result.get("error_message") is None
        assert result["audio_path"] == audio_path

    def test_successful_tts_with_named_speaker(self, graph: StateGraph, engine: Engine):
        self._seed_persona(engine, voice_speaker="en_speaker_0", voice_speaker_wav=None)

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "narration": "Hello, this is a test narration.",
            }
        )

        audio_path = str(Path("runs/run-1/persona-1/speech.wav"))

        self.mock_tts_instance.tts_to_file.assert_called_once_with(
            text="Hello, this is a test narration.",
            file_path=audio_path,
            language="en",
            speaker="en_speaker_0",
        )

        assert result.get("is_fatal_error") is None
        assert result.get("error_message") is None
        assert result["audio_path"] == audio_path

    def test_successful_tts_defaults_language_to_en(
        self, graph: StateGraph, engine: Engine
    ):
        self._seed_persona(engine, language=None, voice_speaker="en_speaker_0")

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "narration": "Hello, this is a test narration.",
            }
        )

        self.mock_tts_instance.tts_to_file.assert_called_once()
        call_kwargs = self.mock_tts_instance.tts_to_file.call_args.kwargs
        assert call_kwargs["language"] == "en"

        assert result.get("is_fatal_error") is None

    def test_successful_tts_with_none_speaker(self, graph: StateGraph, engine: Engine):
        """When both voice_speaker_wav and voice_speaker are None, speaker=None is passed."""

        self._seed_persona(engine, voice_speaker=None, voice_speaker_wav=None)

        result = graph.compile().invoke(
            {
                "run_id": "run-1",
                "persona_id": "persona-1",
                "narration": "Hello, this is a test narration.",
            }
        )

        call_kwargs = self.mock_tts_instance.tts_to_file.call_args.kwargs
        assert "speaker_wav" not in call_kwargs
        assert call_kwargs["speaker"] is None

        assert result.get("is_fatal_error") is None
