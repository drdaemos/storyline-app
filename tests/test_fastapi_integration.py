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
