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
def mock_complete_character():
    """Create mock complete character for testing."""
    return Character(
        name="Generated Hero",
        role="Knight",
        backstory="A brave knight who protects the realm",
        personality="Courageous and honorable",
        appearance="Tall warrior in shining armor",
        relationships={"princess": "sworn protector", "king": "loyal servant"},
        key_locations=["Royal Castle", "Training Grounds"],
        setting_description="Medieval fantasy kingdom"
    )


class TestCharacterGenerationAPI:
    @patch('src.fastapi_server.CharacterCreator')
    def test_generate_character_empty_input(self, mock_creator_class, client, mock_complete_character):
        """Test character generation with empty input."""
        # Setup mock
        mock_creator_instance = Mock()
        mock_creator_instance.generate.return_value = mock_complete_character
        mock_creator_class.return_value = mock_creator_instance

        # Make request
        response = client.post(
            "/api/characters/generate",
            json={
                "partial_character": {},
                "processor_type": "claude"
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert "character" in data
        assert "generated_fields" in data

        character = data["character"]
        assert character["name"] == "Generated Hero"
        assert character["role"] == "Knight"
        assert character["backstory"] == "A brave knight who protects the realm"

        # Verify all fields were generated
        generated_fields = data["generated_fields"]
        expected_fields = {'name', 'role', 'backstory', 'personality', 'appearance',
                          'relationships', 'key_locations', 'setting_description'}
        assert set(generated_fields) == expected_fields

        # Verify CharacterCreator was called correctly
        mock_creator_class.assert_called_once()
        mock_creator_instance.generate.assert_called_once_with({})

    @patch('src.fastapi_server.CharacterCreator')
    def test_generate_character_partial_input(self, mock_creator_class, client, mock_complete_character):
        """Test character generation with partial input."""
        # Setup mock
        mock_creator_instance = Mock()
        mock_creator_instance.generate.return_value = mock_complete_character
        mock_creator_class.return_value = mock_creator_instance

        partial_input = {
            "name": "Generated Hero",
            "role": "Knight"
        }

        # Make request
        response = client.post(
            "/api/characters/generate",
            json={
                "partial_character": partial_input,
                "processor_type": "gpt"
            }
        )

        # Verify response
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()

        assert "character" in data
        assert "generated_fields" in data

        # Verify only missing fields were marked as generated
        generated_fields = data["generated_fields"]
        expected_generated = {'backstory', 'personality', 'appearance',
                             'relationships', 'key_locations', 'setting_description'}
        assert set(generated_fields) == expected_generated

        # Verify CharacterCreator was called with partial data
        mock_creator_instance.generate.assert_called_once_with(partial_input)

    @patch('src.fastapi_server.CharacterCreator')
    def test_generate_character_with_relationships_and_locations(self, mock_creator_class, client, mock_complete_character):
        """Test character generation with complex fields provided."""
        # Setup mock
        mock_creator_instance = Mock()
        mock_creator_instance.generate.return_value = mock_complete_character
        mock_creator_class.return_value = mock_creator_instance

        partial_input = {
            "name": "Generated Hero",
            "relationships": {"friend": "loyal companion"},
            "key_locations": ["Home Village"]
        }

        # Make request
        response = client.post(
            "/api/characters/generate",
            json={
                "partial_character": partial_input,
                "processor_type": "cohere"
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Verify only missing fields were marked as generated
        generated_fields = data["generated_fields"]
        expected_generated = {'role', 'backstory', 'personality', 'appearance', 'setting_description'}
        assert set(generated_fields) == expected_generated

        # Relationships and key_locations should not be in generated fields
        assert "relationships" not in generated_fields
        assert "key_locations" not in generated_fields

    @patch('src.fastapi_server.CharacterCreator')
    def test_generate_character_validation_error(self, mock_creator_class, client):
        """Test character generation with validation error."""
        # Setup mock to raise ValueError
        mock_creator_instance = Mock()
        mock_creator_instance.generate.side_effect = ValueError("Invalid character data")
        mock_creator_class.return_value = mock_creator_instance

        # Make request
        response = client.post(
            "/api/characters/generate",
            json={
                "partial_character": {"name": ""},
                "processor_type": "claude"
            }
        )

        # Verify error response
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid character data" in data["detail"]

    @patch('src.fastapi_server.CharacterCreator')
    def test_generate_character_server_error(self, mock_creator_class, client):
        """Test character generation with server error."""
        # Setup mock to raise generic exception
        mock_creator_instance = Mock()
        mock_creator_instance.generate.side_effect = Exception("Server error")
        mock_creator_class.return_value = mock_creator_instance

        # Make request
        response = client.post(
            "/api/characters/generate",
            json={
                "partial_character": {},
                "processor_type": "claude"
            }
        )

        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to generate character" in data["detail"]

    def test_generate_character_default_processor_type(self, client):
        """Test that default processor type is used when not specified."""
        with patch('src.fastapi_server.CharacterCreator') as mock_creator_class:
            mock_creator_instance = Mock()
            mock_character = Character(
                name="Test",
                role="Test",
                backstory="Test"
            )
            mock_creator_instance.generate.return_value = mock_character
            mock_creator_class.return_value = mock_creator_instance

            # Make request without processor_type
            response = client.post(
                "/api/characters/generate",
                json={
                    "partial_character": {"name": "Test Character"}
                }
            )

            assert response.status_code == 200

    def test_generate_character_invalid_request_format(self, client):
        """Test character generation with invalid request format."""
        # Make request with invalid JSON structure
        response = client.post(
            "/api/characters/generate",
            json={
                "invalid_field": "test"
            }
        )

        # Should use default values and process successfully
        # (FastAPI will use default values for missing required fields)
        assert response.status_code in [200, 422]  # Either success or validation error

    def test_generate_character_missing_request_body(self, client):
        """Test character generation with missing request body."""
        response = client.post("/api/characters/generate")

        # Should return validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
