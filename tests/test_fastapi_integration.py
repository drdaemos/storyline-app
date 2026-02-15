import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app
from src.models.character import Character


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Set up test database for each test."""
    temp_dir = tempfile.mkdtemp()
    original_database_url = os.environ.get("DATABASE_URL")
    test_db_path = Path(temp_dir) / "test_fastapi.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["AUTH_ENABLED"] = "false"

    yield

    # Restore original environment
    if original_database_url is not None:
        os.environ["DATABASE_URL"] = original_database_url
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]

    # Clean up temp directory
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_character():
    """Create mock character."""
    return Character(
        name="TestBot",
        tagline="Assistant",
        backstory="Test character for API testing",
        personality="Helpful and direct",
        appearance="Digital assistant",
    )


class TestFastAPIEndpoints:
    def test_api_info_endpoint(self, client):
        """Test API info endpoint."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "conversation_memory" in data
        assert data["conversation_memory"] in ["ok", "error"]
        assert data["status"] in ["healthy", "unhealthy"]

    @patch("src.fastapi_server.character_loader")
    def test_list_characters(self, mock_loader, client):
        """Test character listing endpoint."""
        from src.models.api_models import CharacterSummary

        mock_loader.list_character_summaries.return_value = [CharacterSummary(id="testbot", name="TestBot", tagline="Test Assistant"), CharacterSummary(id="alice", name="Alice", tagline="Adventurer")]

        response = client.get("/api/characters")
        assert response.status_code == 200
        assert response.json() == [{"id": "testbot", "name": "TestBot", "tagline": "Test Assistant"}, {"id": "alice", "name": "Alice", "tagline": "Adventurer"}]

    @patch("src.fastapi_server.character_loader")
    def test_list_characters_error(self, mock_loader, client):
        """Test character listing endpoint with error."""
        mock_loader.list_character_summaries.side_effect = Exception("Test error")

        response = client.get("/api/characters")
        assert response.status_code == 500

    @patch("src.fastapi_server.character_loader")
    def test_get_character_info(self, mock_loader, client, mock_character):
        """Test getting character info."""
        mock_loader.get_character_info.return_value = mock_character

        response = client.get("/api/characters/TestBot")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestBot"
        assert data["tagline"] == "Assistant"
        assert data["backstory"] == "Test character for API testing"

    @patch("src.fastapi_server.character_loader")
    def test_get_character_info_not_found(self, mock_loader, client):
        """Test getting info for non-existent character."""
        mock_loader.get_character_info.return_value = None

        response = client.get("/api/characters/NonExistent")
        assert response.status_code == 404

    def test_list_sessions(self, client):
        """Test listing sessions."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        for session in sessions:
            assert "session_id" in session
            assert "character_name" in session
            assert "message_count" in session
            assert "last_message_time" in session
            assert "last_character_response" in session

    @patch("src.fastapi_server.session_repository")
    @patch("src.fastapi_server.scenario_registry")
    @patch("src.fastapi_server.ConversationMemory")
    @patch("src.fastapi_server.character_loader")
    def test_list_character_sessions_filtered(
        self,
        mock_loader,
        mock_memory_cls,
        mock_scenario_registry,
        mock_session_repo,
        client,
        mock_character,
    ):
        """Test listing only sessions linked to a specific character."""
        mock_loader.get_character_info.return_value = mock_character
        mock_scenario_registry.get_scenario_ids_for_character.return_value = {"sc-1"}
        mock_scenario_registry.get_scenario.side_effect = lambda scenario_id, _user_id: (
            {"scenario_data": {"summary": "Linked Scenario"}} if scenario_id == "sc-1" else None
        )

        mock_memory = mock_memory_cls.return_value
        mock_memory.get_session_details.side_effect = lambda session_id, _user_id: (
            {
                "session_id": session_id,
                "message_count": 4,
                "first_message_time": "2025-01-10T09:30:00",
                "last_message_time": "2025-01-10T10:00:00",
            }
            if session_id == "sess-1"
            else None
        )
        mock_memory.get_recent_messages.side_effect = lambda session_id, _user_id, limit=1: [
            {"content": f"response-{session_id}"}
        ]
        mock_session_repo.get_user_sessions.return_value = [
            {
                "id": "sess-1",
                "scenario_id": "sc-1",
                "turn_counter": 3,
                "updated_at": "2025-01-10T10:00:00",
            }
        ]

        response = client.get("/api/characters/char-1/sessions")
        assert response.status_code == 200

        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "sess-1"
        assert sessions[0]["scenario_name"] == "Linked Scenario"
        assert sessions[0]["turn_count"] == 3
        mock_session_repo.get_user_sessions.assert_called_once_with(
            user_id="anonymous",
            status=None,
            limit=20,
            offset=0,
            scenario_ids={"sc-1"},
        )

    @patch("src.fastapi_server.session_repository")
    @patch("src.fastapi_server.scenario_registry")
    @patch("src.fastapi_server.ConversationMemory")
    @patch("src.fastapi_server.character_loader")
    def test_list_character_sessions_forwards_pagination_and_status(
        self,
        mock_loader,
        mock_memory_cls,
        mock_scenario_registry,
        mock_session_repo,
        client,
        mock_character,
    ):
        """Test that status/limit/offset query params are forwarded to repository filtering."""
        mock_loader.get_character_info.return_value = mock_character
        mock_scenario_registry.get_scenario_ids_for_character.return_value = {"sc-1"}
        mock_scenario_registry.get_scenario.return_value = {"scenario_data": {"summary": "Linked Scenario"}}
        mock_memory = mock_memory_cls.return_value
        mock_memory.get_session_details.return_value = None
        mock_memory.get_recent_messages.return_value = []
        mock_session_repo.get_user_sessions.return_value = []

        response = client.get("/api/characters/char-1/sessions?status=active&limit=5&offset=2")
        assert response.status_code == 200
        mock_session_repo.get_user_sessions.assert_called_once_with(
            user_id="anonymous",
            status="active",
            limit=5,
            offset=2,
            scenario_ids={"sc-1"},
        )

    @patch("src.fastapi_server.character_loader")
    def test_list_character_sessions_invalid_status(self, mock_loader, client, mock_character):
        """Test character-scoped sessions with invalid status query value."""
        mock_loader.get_character_info.return_value = mock_character

        response = client.get("/api/characters/char-1/sessions?status=archived")
        assert response.status_code == 400

    @patch("src.fastapi_server.character_loader")
    def test_list_character_sessions_not_found(self, mock_loader, client):
        """Test character-scoped sessions for non-existent character."""
        mock_loader.get_character_info.return_value = None

        response = client.get("/api/characters/non-existent/sessions")
        assert response.status_code == 404

    def test_clear_nonexistent_session(self, client):
        """Test clearing a session that doesn't exist."""
        response = client.delete("/api/sessions/nonexistent-session")
        assert response.status_code == 404


class TestRequestValidation:
    def test_turn_request_validation(self, client):
        """Test request validation for turn endpoint."""
        test_cases = [
            {},  # Empty request
            {"user_input": "Hello!"},  # Missing session_id
            {"session_id": "test"},  # Missing user_input
            {"session_id": "", "user_input": "Hello!"},  # Empty session_id
            {"session_id": "test", "user_input": ""},  # Empty user_input
        ]

        for test_data in test_cases:
            response = client.post("/api/turn", json=test_data)
            assert response.status_code == 422, f"Failed for data: {test_data}"


class TestErrorHandling:
    @patch("src.fastapi_server.session_repository")
    def test_turn_session_not_found(self, mock_session_repo, client):
        """Test turn with non-existent session."""
        mock_session_repo.get_session.return_value = None

        response = client.post("/api/turn", json={"session_id": "nonexistent", "user_input": "Hello!", "processor_type": "google"})
        assert response.status_code == 404
