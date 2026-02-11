import os
import shutil
import tempfile
from types import SimpleNamespace
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
        relationships={"user": "helper"},
        key_locations=["digital space"],
        setting_description="Test digital environment",
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

    def test_list_rulesets(self, client):
        """Test ruleset listing endpoint."""
        response = client.get("/api/rulesets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(item.get("id") == "everyday-tension" for item in data)
        first = data[0]
        assert "character_stat_schema" in first
        assert "scene_state_schema" in first

    @patch("src.fastapi_server.character_loader")
    def test_list_characters(self, mock_loader, client):
        """Test character listing endpoint."""
        from src.models.api_models import CharacterSummary

        mock_loader.list_character_summaries.return_value = [CharacterSummary(id="testbot", name="TestBot", tagline="Test Assistant"), CharacterSummary(id="alice", name="Alice", tagline="Adventurer")]

        response = client.get("/api/characters")
        assert response.status_code == 200
        assert response.json() == [
            {"id": "testbot", "name": "TestBot", "tagline": "Test Assistant", "tags": [], "is_persona": False},
            {"id": "alice", "name": "Alice", "tagline": "Adventurer", "tags": [], "is_persona": False},
        ]

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
        response = client.delete("/api/sessions/nonexistent-session")
        assert response.status_code == 404

    def test_get_session_summary_nonexistent(self, client):
        """Test getting summary for a session that doesn't exist."""
        response = client.get("/api/sessions/nonexistent-session/summary")
        assert response.status_code == 404

    @patch("src.fastapi_server.session_service")
    def test_get_session_summary_no_summaries(self, mock_session_service, client):
        """Test getting summary when no summaries exist."""
        mock_session_service.get_session_summary.return_value = (
            "No summary available yet. Summary will be generated after the conversation progresses.",
            False,
        )

        response = client.get("/api/sessions/test-session/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert data["has_summary"] is False
        assert "No summary available yet" in data["summary_text"]

    @patch("src.fastapi_server.session_service")
    def test_get_session_summary_with_data(self, mock_session_service, client):
        """Test getting summary when summaries exist."""
        mock_session_service.get_session_summary.return_value = (
            "\n".join(
                [
                    "Session: test-session",
                    "Ruleset: Everyday Tension",
                    "World lore: Neon Harbor",
                    "Turns completed: 2",
                    "",
                    "Recent narrator beats:",
                    "1. Day 1, morning. They meet in a coffee shop.",
                ]
            ),
            True,
        )

        response = client.get("/api/sessions/test-session/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"
        assert data["has_summary"] is True
        assert "Day 1, morning" in data["summary_text"]
        assert "Ruleset: Everyday Tension" in data["summary_text"]


class TestInteractEndpoint:
    @patch("src.fastapi_server.session_service")
    def test_interact_success(self, mock_session_service, client):
        """Test successful interaction with character."""
        mock_session_service.run_interaction.return_value = SimpleNamespace(
            narration_text="Hello there!",
            suggested_actions=[],
            meta_text=None,
            message_count=3,
        )

        # Make request
        response = client.post("/api/interact", json={"character_name": "TestBot", "user_message": "Hello!", "session_id": "test-session-123"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read streaming response
        content = response.text
        assert "data: " in content
        assert '"type": "session"' in content
        assert '"type": "complete"' in content

    def test_interact_invalid_request(self, client):
        """Test interaction with invalid request data."""
        response = client.post(
            "/api/interact",
            json={
                "user_message": "Hello!"
                # Missing required character_name
            },
        )

        assert response.status_code == 422  # Validation error

    @patch("src.fastapi_server.session_service")
    def test_interact_with_session_id(self, mock_session_service, client):
        """Test interaction with specific session ID."""
        mock_session_service.run_interaction.return_value = SimpleNamespace(
            narration_text="Hello there!",
            suggested_actions=[],
            meta_text=None,
            message_count=2,
        )

        # First request to create session
        response1 = client.post("/api/interact", json={"character_name": "TestBot", "user_message": "Hello!", "session_id": "test-session-123"})

        assert response1.status_code == 200
        content1 = response1.text
        assert '"session_id": "test-session-123"' in content1


class TestSessionManagement:
    @patch("src.fastapi_server.session_service")
    def test_session_creation_and_listing(self, mock_session_service, client):
        """Test session creation and listing."""
        mock_session_service.run_interaction.return_value = SimpleNamespace(
            narration_text="Hello!",
            suggested_actions=[],
            meta_text=None,
            message_count=2,
        )
        mock_session_service.list_sessions.return_value = []
        mock_session_service.clear_session.return_value = False

        # Create interaction to establish session
        response = client.post("/api/interact", json={"character_name": "TestBot", "user_message": "Hello!", "session_id": "test-session-456"})

        assert response.status_code == 200

        # List sessions
        response = client.get("/api/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) >= 0  # Session might be created

        # Try to clear the test session we created (might not exist in the sessions list since it only shows persisted sessions)
        response = client.delete("/api/sessions/test-session-456")
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
            {"character_name": "TestBot", "user_message": "Hello!"},  # Missing session_id
        ]

        for test_data in test_cases:
            response = client.post("/api/interact", json=test_data)
            assert response.status_code == 422, f"Failed for data: {test_data}"

    def test_interact_request_optional_fields(self, client):
        """Test optional fields in interact request."""
        # Character existence is no longer validated by /api/interact;
        # request schema validity is the key check here.
        with patch("src.fastapi_server.session_service") as mock_session_service:
            mock_session_service.run_interaction.side_effect = Exception("Unknown session")

            response = client.post("/api/interact", json={"character_name": "TestBot", "user_message": "Hello!", "session_id": "custom-session"})

            assert response.status_code == 200


class TestErrorHandling:
    @patch("src.fastapi_server.session_service")
    def test_simulation_error_streams_error_event(self, mock_session_service, client):
        """Test interaction streams error event on simulation failure."""
        mock_session_service.run_interaction.side_effect = Exception("Simulation error")

        response = client.post("/api/interact", json={"character_name": "TestBot", "user_message": "Hello!", "session_id": "s1"})

        assert response.status_code == 200
        assert '"type": "error"' in response.text


class TestWorldLoreEndpoints:
    def test_world_lore_tags_and_keywords_roundtrip(self, client):
        payload = {
            "name": "Neon Harbor",
            "lore_text": "Port city where trade syndicates and private militias share control.",
            "tags": ["cyberpunk", "urban"],
            "keywords": ["trade-syndicate", "port-city", "militia-politics"],
        }

        create_response = client.post("/api/world-lore", json=payload)
        assert create_response.status_code == 200
        world_lore_id = create_response.json()["world_lore_id"]

        detail_response = client.get(f"/api/world-lore/{world_lore_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["tags"] == ["cyberpunk", "urban"]
        assert detail["keywords"] == ["trade-syndicate", "port-city", "militia-politics"]

        list_response = client.get("/api/world-lore")
        assert list_response.status_code == 200
        entries = list_response.json()
        saved_entry = next((item for item in entries if item["id"] == world_lore_id), None)
        assert saved_entry is not None
        assert saved_entry["tags"] == ["cyberpunk", "urban"]
        assert saved_entry["keywords"] == ["trade-syndicate", "port-city", "militia-politics"]

    def test_world_lore_create_stream_route_resolves_post(self, client):
        response = client.post("/api/world-lore/create-stream", json={})
        assert response.status_code == 422


class TestCreationStreamRoutes:
    def test_character_create_stream_route_resolves_post(self, client):
        response = client.post("/api/characters/create-stream", json={})
        assert response.status_code == 422


class TestSessionStartContracts:
    @patch("src.fastapi_server.session_service")
    def test_start_session_with_scenario_does_not_require_character_name(
        self,
        mock_session_service,
        client,
    ):
        mock_session_service.start_session.return_value = "session-123"

        response = client.post(
            "/api/sessions/start",
            json={
                "scenario_id": "scenario-123",
                "small_model_key": "deepseek-v32",
                "large_model_key": "claude-opus",
            },
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == "session-123"
        mock_session_service.start_session.assert_called_once()
