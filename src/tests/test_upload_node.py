import pytest
from unittest.mock import MagicMock, patch
from langgraph.graph import StateGraph, START, END
from sqlmodel import Session
from requests import RequestException
from late.models import PostCreateResponse

from db import get_engine
from models import Persona
from nodes import PersonaRunState
from nodes.upload_node.node import upload_node

from tests.base_test_class import BaseTestClass


class TestUploadNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(upload_node)
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
            "persona_id": persona_id,
            "tiktok_caption": "Breaking news!",
            "hashtags": ["#news", "#tiktok"],
            "output_video_path": "path/to/video.mp4",
        }

    def test_successful_upload(self, graph: StateGraph):
        with Session(get_engine()) as session:
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result.get("is_fatal_error") is None
        assert result.get("error_message") is None
        assert result.get("tiktok_post_id") == "post-123"
        self.mock_client.media.get_media_presigned_url.assert_called_once()
        self.mock_put.assert_called_once()
        self.mock_client.posts.create.assert_called_once_with(
            media_items=[{"url": "https://cdn.example.com/video.mp4", "type": "video"}],
            content="Breaking news!",
            hashtags=["#news", "#tiktok"],
            platforms=[{"platform": "tiktok", "accountId": "tiktok-news"}],
            publish_now=True,
        )

    def test_persona_not_found(self, graph: StateGraph):
        result = graph.compile().invoke(self._base_state(persona_id="missing-persona"))

        assert result["is_fatal_error"] is True
        assert "missing-persona" in result["error_message"]
        self.mock_client.media.get_media_presigned_url.assert_not_called()

    def test_presigned_url_failure(self, graph: StateGraph):
        from zernio import ZernioAPIError

        self.mock_client.media.get_media_presigned_url.side_effect = ZernioAPIError("S3 error")

        with Session(get_engine()) as session:
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "Failed to get presigned URL" in result["error_message"]
        self.mock_put.assert_not_called()

    def test_video_file_not_found(self, graph: StateGraph):
        self.mock_video_path.exists.return_value = False

        with Session(get_engine()) as session:
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
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "Failed to upload video" in result["error_message"]
        self.mock_client.posts.create.assert_not_called()

    def test_put_upload_network_failure(self, graph: StateGraph):
        self.mock_put.side_effect = RequestException("Network error")

        with Session(get_engine()) as session:
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "Request error" in result["error_message"]
        self.mock_client.posts.create.assert_not_called()

    def test_create_post_failure(self, graph: StateGraph):
        from zernio import ZernioAPIError

        self.mock_client.posts.create.side_effect = ZernioAPIError("post creation failed")

        with Session(get_engine()) as session:
            session.add(self._make_persona())
            session.commit()

        result = graph.compile().invoke(self._base_state())

        assert result["is_fatal_error"] is True
        assert "Failed to create post" in result["error_message"]
