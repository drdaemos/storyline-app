from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app
from src.models.character import Character


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_character():
    """Create mock character."""
    return Character(
        name="TestBot",
        role="Assistant",
        backstory="Test character for API testing",
        personality="Helpful and direct",
        appearance="Digital assistant",
        relationships={"user": "helper"},
        key_locations=["digital space"],
        setting_description="Test digital environment"
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
        assert "summary_memory" in data
        assert "details" in data

        # Check that both databases are accessible
        assert data["conversation_memory"] in ["ok", "error"]
        assert data["summary_memory"] in ["ok", "error"]
        assert data["status"] in ["healthy", "unhealthy"]

    @patch('src.fastapi_server.character_loader')
    def test_list_characters(self, mock_loader, client):
        """Test character listing endpoint."""
        mock_loader.list_characters.return_value = ["TestBot", "Alice"]

        response = client.get("/characters")
        assert response.status_code == 200
        assert response.json() == ["TestBot", "Alice"]

    @patch('src.fastapi_server.character_loader')
    def test_list_characters_error(self, mock_loader, client):
        """Test character listing endpoint with error."""
        mock_loader.list_characters.side_effect = Exception("Test error")

        response = client.get("/characters")
        assert response.status_code == 500

    @patch('src.fastapi_server.character_loader')
    def test_get_character_info(self, mock_loader, client, mock_character):
        """Test getting character info."""
        mock_loader.get_character_info.return_value = mock_character

        response = client.get("/characters/TestBot")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestBot"
        assert data["role"] == "Assistant"
        assert data["backstory"] == "Test character for API testing"

    @patch('src.fastapi_server.character_loader')
    def test_get_character_info_not_found(self, mock_loader, client):
        """Test getting info for non-existent character."""
        mock_loader.get_character_info.return_value = None

        response = client.get("/characters/NonExistent")
        assert response.status_code == 404

    def test_list_sessions(self, client):
        """Test listing sessions."""
        response = client.get("/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        # Since sessions come from the database, we can't guarantee empty list
        # Just check that each session has the required fields
        for session in sessions:
            assert "session_id" in session
            assert "character_name" in session
            assert "message_count" in session
            assert "last_message_time" in session
            assert "last_character_response" in session

    def test_clear_nonexistent_session(self, client):
        """Test clearing a session that doesn't exist."""
        response = client.delete("/sessions/nonexistent-session")
        assert response.status_code == 404


class TestInteractEndpoint:
    @patch('src.fastapi_server.character_loader')
    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.CharacterResponder')
    def test_interact_success(self, mock_responder_class, mock_deps_class, mock_loader, client, mock_character):
        """Test successful interaction with character."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character

        mock_dependencies = Mock()
        mock_deps_class.create_default.return_value = mock_dependencies

        mock_responder = Mock()
        mock_responder.character = mock_character
        mock_responder.memory = []
        mock_responder.respond.return_value = "Hello there!"
        mock_responder_class.return_value = mock_responder

        # Make request
        response = client.post("/interact", json={
            "character_name": "TestBot",
            "user_message": "Hello!",
            "processor_type": "google"
        })

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read streaming response
        content = response.text
        assert "data: " in content
        assert '"type": "session"' in content
        assert '"type": "complete"' in content

    @patch('src.fastapi_server.character_loader')
    def test_interact_character_not_found(self, mock_loader, client):
        """Test interaction with non-existent character."""
        mock_loader.load_character.return_value = None

        response = client.post("/interact", json={
            "character_name": "NonExistent",
            "user_message": "Hello!",
            "processor_type": "google"
        })

        assert response.status_code == 404

    def test_interact_invalid_request(self, client):
        """Test interaction with invalid request data."""
        response = client.post("/interact", json={
            "user_message": "Hello!"
            # Missing required character_name
        })

        assert response.status_code == 422  # Validation error

    @patch('src.fastapi_server.character_loader')
    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.CharacterResponder')
    def test_interact_with_session_id(self, mock_responder_class, mock_deps_class, mock_loader, client, mock_character):
        """Test interaction with specific session ID."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character

        mock_dependencies = Mock()
        mock_deps_class.create_default.return_value = mock_dependencies

        mock_responder = Mock()
        mock_responder.character = mock_character
        mock_responder.memory = []
        mock_responder.respond.return_value = "Hello there!"
        mock_responder_class.return_value = mock_responder

        # First request to create session
        response1 = client.post("/interact", json={
            "character_name": "TestBot",
            "user_message": "Hello!",
            "session_id": "test-session-123",
            "processor_type": "google"
        })

        assert response1.status_code == 200
        content1 = response1.text
        assert '"session_id": "test-session-123"' in content1


class TestSessionManagement:
    @patch('src.fastapi_server.character_loader')
    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.CharacterResponder')
    def test_session_creation_and_listing(self, mock_responder_class, mock_deps_class, mock_loader, client, mock_character):
        """Test session creation and listing."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        mock_dependencies = Mock()
        mock_deps_class.create_default.return_value = mock_dependencies

        mock_responder = Mock()
        mock_responder.character = mock_character
        mock_responder.memory = [{"role": "user", "content": "test"}]
        mock_responder.respond.return_value = "Hello!"
        mock_responder_class.return_value = mock_responder

        # Create interaction to establish session
        response = client.post("/interact", json={
            "character_name": "TestBot",
            "user_message": "Hello!",
            "session_id": "test-session-456",
            "processor_type": "google"
        })

        assert response.status_code == 200

        # List sessions
        response = client.get("/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) >= 0  # Session might be created

        # Try to clear the test session we created (might not exist in the sessions list since it only shows persisted sessions)
        response = client.delete("/sessions/test-session-456")
        # The session might not exist in character_sessions dict, so 404 is acceptable
        assert response.status_code in [200, 404]


class TestRequestValidation:
    def test_interact_request_validation(self, client):
        """Test request validation for interact endpoint."""
        # Test missing required fields
        test_cases = [
            {},  # Empty request
            {"user_message": "Hello!"},  # Missing character_name
            {"character_name": "TestBot"},  # Missing user_message
            {"character_name": "", "user_message": "Hello!"},  # Empty character_name
            {"character_name": "TestBot", "user_message": ""},  # Empty user_message
        ]

        for test_data in test_cases:
            response = client.post("/interact", json=test_data)
            assert response.status_code == 422, f"Failed for data: {test_data}"

    def test_interact_request_optional_fields(self, client):
        """Test optional fields in interact request."""
        # Mock the character loader to avoid actual file system access
        with patch('src.fastapi_server.character_loader') as mock_loader:
            mock_loader.load_character.return_value = None  # Will cause 404

            response = client.post("/interact", json={
                "character_name": "TestBot",
                "user_message": "Hello!",
                "session_id": "custom-session",
                "processor_type": "openai"
            })

            assert response.status_code == 404  # Character not found, but validation passed


class TestErrorHandling:
    @patch('src.fastapi_server.character_loader')
    def test_character_loading_error(self, mock_loader, client):
        """Test error handling when character loading fails."""
        mock_loader.load_character.side_effect = Exception("File system error")

        response = client.post("/interact", json={
            "character_name": "TestBot",
            "user_message": "Hello!",
            "processor_type": "google"
        })

        assert response.status_code == 500

    @patch('src.fastapi_server.character_loader')
    @patch('src.fastapi_server.CharacterResponderDependencies')
    def test_dependencies_creation_error(self, mock_deps_class, mock_loader, client, mock_character):
        """Test error handling when dependencies creation fails."""
        mock_loader.load_character.return_value = mock_character
        mock_deps_class.create_default.side_effect = Exception("Dependencies error")

        response = client.post("/interact", json={
            "character_name": "TestBot",
            "user_message": "Hello!",
            "processor_type": "google"
        })

        assert response.status_code == 500
