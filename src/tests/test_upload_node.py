from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from late.models import PostCreateResponse
from requests import RequestException
from sqlmodel import Session

from db import get_engine
from logging_config import get_logger
from models import Persona, Run
from nodes import PersonaRunState
from nodes.upload_node.node import upload_node
from tests.base_test_class import BaseTestClass
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_upload_error_handler = build_error_handler(
    log,
    "upload.failed",
    "Upload failed",
    context_keys=("run_id", "persona_id"),
)


class TestUploadNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(upload_node, retry_policy=LLM_RETRY, error_handler=_upload_error_handler)
        graph.add_edge(START, "upload_node")
        graph.add_edge("upload_node", END)
        return graph

    @pytest.fixture(autouse=True)
    def mock_zernio_client(self):
        with patch("nodes.upload_node.node._client") as mock_client:
            mock_client.media.get_media_presigned_url.return_value = {
                "uploadUrl": "https://s3.example.com/upload",
                "publicUrl": "https://cdn.example.com/video.mp4",
            }
            mock_client.posts.create.return_value = PostCreateResponse.model_validate(
                {"message": "ok", "post": {"_id": "post-123"}}
            )
            self.mock_client = mock_client
            yield mock_client

    @pytest.fixture(autouse=True)
    def mock_requests_put(self):
        with patch("nodes.upload_node.node.requests.put") as mock_put:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_put.return_value = mock_response
            self.mock_put = mock_put
            yield mock_put

    @pytest.fixture(autouse=True)
    def mock_video_path(self):
        with patch("nodes.upload_node.node.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.is_file.return_value = True
            mock_path.suffix = ".mp4"
            mock_path.open.return_value = MagicMock()

            mock_path_cls.return_value = mock_path
            self.mock_video_path = mock_path

            yield mock_path_cls

    def _make_persona(self, **kwargs) -> Persona:
        defaults = {
            "id": "1",
            "tiktok_account_id": "tiktok-news",
            "language": "en",
            "style": "dramatic",
            "tone": "serious",
        }
        defaults.update(kwargs)
        return Persona(**defaults)

    def _base_state(self, persona_id: str = "1"):
        return {
            "run_id": "run-1",
            "persona_run_id": "persona-run-1",
            "persona_id": persona_id,
            "story_mode": "real_news",
            "base_script": "A base script.",
            "narration": "A narration.",
            "tiktok_caption": "Breaking news!",
            "hashtags": ["#news", "#tiktok"],
            "video_category": "news",
            "output_video_path": "path/to/video.mp4",
        }

    def _make_run(self, **kwargs) -> Run:
        defaults = {
            "id": "run-1",
            "status": "running",
            "source_article_url": "https://example.com/news",
            "source_article_title": "Source headline",
            "base_script": "Stored base script.",
        }
        defaults.update(kwargs)
        return Run(**defaults)

    def test_successful_upload(self, graph: StateGraph):
        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result.get("is_fatal_error") is None
        assert result.get("error_message") is None
        assert result.get("zernio_post_id") == "post-123"
        self.mock_client.media.get_media_presigned_url.assert_called_once()
        self.mock_put.assert_called_once()

        description = "Breaking news!\n\n#news #tiktok"
        self.mock_client.posts.create.assert_called_once_with(
            media_items=[{"url": "https://cdn.example.com/video.mp4", "type": "video"}],
            content=description,
            hashtags=["#news", "#tiktok"],
            platforms=[{"platform": "tiktok", "accountId": "tiktok-news"}],
            publish_now=True,
            metadata={
                "schema_version": 1,
                "app": "szponciciel",
                "run": {
                    "id": "run-1",
                    "source_article_url": "https://example.com/news",
                    "source_article_title": "Source headline",
                },
                "persona_run": {
                    "id": "persona-run-1",
                    "story_mode": "real_news",
                },
                "persona": {
                    "id": "1",
                    "tiktok_account_id": "tiktok-news",
                    "language": "en",
                    "style": "dramatic",
                    "tone": "serious",
                },
                "generation": {
                    "llm_model": "gemini-2.5-flash-lite",
                    "writer_critic_max_iters": 3,
                    "base_script": "A base script.",
                    "narration": "A narration.",
                    "caption": "Breaking news!",
                    "hashtags": ["#news", "#tiktok"],
                    "video_category": "news",
                },
            },
        )

    def test_persona_not_found(self, graph: StateGraph):
        result = graph.compile().invoke(self._base_state(persona_id="missing-persona"))

        assert result["is_fatal_error"] is True
        assert "missing-persona" in result["error_message"]
        self.mock_client.media.get_media_presigned_url.assert_not_called()

    def test_run_not_found(self, graph: StateGraph):
        with Session(get_engine()) as session:
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "run-1" in result["error_message"]
        self.mock_client.media.get_media_presigned_url.assert_not_called()

    def test_presigned_url_failure(self, graph: StateGraph):
        from zernio import ZernioAPIError

        self.mock_client.media.get_media_presigned_url.side_effect = ZernioAPIError("S3 error")

        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Upload failed: LateAPIError: S3 error"
        self.mock_put.assert_not_called()

    def test_video_file_not_found(self, graph: StateGraph):
        self.mock_video_path.exists.return_value = False

        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "File not found" in result["error_message"]
        self.mock_put.assert_not_called()

    def test_put_upload_failure(self, graph: StateGraph):
        self.mock_put.return_value.ok = False
        self.mock_put.return_value.text = "403 Forbidden"

        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "Failed to upload video" in result["error_message"]
        self.mock_client.posts.create.assert_not_called()

    def test_put_upload_network_failure(self, graph: StateGraph):
        self.mock_put.side_effect = RequestException("Network error")

        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Upload failed: RequestException: Network error"
        self.mock_client.posts.create.assert_not_called()

    def test_create_post_failure(self, graph: StateGraph):
        from zernio import ZernioAPIError

        self.mock_client.posts.create.side_effect = ZernioAPIError("post creation failed")

        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Upload failed: LateAPIError: post creation failed"

    def test_unexpected_create_post_exception_is_logged(self, graph: StateGraph):
        with Session(get_engine()) as session:
            session.add(self._make_run())
            session.add(self._make_persona())
            session.commit()

        self.mock_client.posts.create.side_effect = KeyError("tiktok_account_id")

        with patch("utils.graph_utils.log_exception") as mock_log_exception:
            result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Upload failed: KeyError: 'tiktok_account_id'"
        mock_log_exception.assert_called_once()
