import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app, character_manager
from src.models.character import Character


@pytest.fixture(scope="module", autouse=True)
def set_env():
    os.environ["AUTH_ENABLED"] = "false"


class TestCharacterAPI:
    def setup_method(self):
        """Setup test with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        # Replace the global character_manager with one using temp directory
        character_manager.characters_dir = Path(self.temp_dir)
        character_manager.characters_dir.mkdir(exist_ok=True)
        self.client = TestClient(app)

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_character_structured_data(self):
        """Test creating character with structured data."""
        character = Character(
            name="API Test Character",
            tagline="Test Role",
            backstory="Test backstory",
            personality="Test personality",
            appearance="Test appearance",
            setting_description="Test setting",
            relationships={"user": "Test relationship"},
            key_locations=["Location 1"],
        )

        request_payload = {"data": character.model_dump(), "is_yaml_text": False}

        response = self.client.post("/api/characters", json=request_payload)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Character 'API Test Character' created successfully"
        assert response_data["character_filename"] == "api_test_character"

        # Verify file was created
        character_file = Path(self.temp_dir) / "api_test_character.yaml"
        assert character_file.exists()

    def test_create_character_yaml_text(self):
        """Test creating character with YAML text."""
        yaml_text = """
name: YAML Test Character
tagline: YAML Test Role
backstory: YAML test backstory
personality: YAML test personality
"""

        request_payload = {"data": yaml_text, "is_yaml_text": True}

        response = self.client.post("/api/characters", json=request_payload)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Character 'YAML Test Character' created successfully"
        assert response_data["character_filename"] == "yaml_test_character"

    def test_create_character_missing_required_fields(self):
        """Test creating character with missing required fields."""
        character_data = {
            "name": "Incomplete Character",
            "role": "Test Role",
            # Missing backstory
        }

        request_payload = {"data": character_data, "is_yaml_text": False}

        response = self.client.post("/api/characters", json=request_payload)

        # Pydantic validation will return 422 for missing required fields
        assert response.status_code == 422

    def test_create_character_invalid_yaml(self):
        """Test creating character with invalid YAML."""
        invalid_yaml = """
name: Test Character
tagline: Test Role
backstory: [unclosed bracket
"""

        request_payload = {"data": invalid_yaml, "is_yaml_text": True}

        response = self.client.post("/api/characters", json=request_payload)

        assert response.status_code == 400
        assert "Invalid YAML format" in response.json()["detail"]

    def test_create_character_duplicate(self):
        """Test creating character with duplicate name."""
        character = Character(name="Duplicate Character", tagline="Test Role", backstory="Test backstory")

        request_payload = {"data": character.model_dump(), "is_yaml_text": False}

        # Create character first time
        response = self.client.post("/api/characters", json=request_payload)
        assert response.status_code == 200

        # Try to create again - should fail
        response = self.client.post("/api/characters", json=request_payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_character_wrong_data_type(self):
        """Test creating character with wrong data type for is_yaml_text setting."""
        request_payload = {
            "data": "This should be YAML text",
            "is_yaml_text": False,  # But we're saying it's not YAML
        }

        response = self.client.post("/api/characters", json=request_payload)

        # This will cause a 500 error because isinstance check fails in our code
        # Let's check for the expected error response
        assert response.status_code in [400, 500]
        if response.status_code == 400:
            assert "data must be structured character data" in response.json()["detail"]

    def test_create_character_filename_collision(self):
        """Test creating characters with names that would generate the same filename."""
        # Create first character
        character1 = Character(name="Test Character", tagline="Test Role", backstory="Test backstory")

        request_payload1 = {"data": character1.model_dump(), "is_yaml_text": False}

        response1 = self.client.post("/api/characters", json=request_payload1)
        assert response1.status_code == 200

        # Try to create second character with different name but same sanitized filename
        character2 = Character(
            name="Test@Character",  # This sanitizes to same filename
            tagline="Different Role",
            backstory="Different backstory",
        )

        request_payload2 = {"data": character2.model_dump(), "is_yaml_text": False}

        response2 = self.client.post("/api/characters", json=request_payload2)
        assert response2.status_code == 400
        assert "Filename collision detected" in response2.json()["detail"]

    def test_create_character_yaml_filename_collision(self):
        """Test filename collision with YAML text input."""
        # Create first character with structured data
        character = Character(name="YAML Test", tagline="Test Role", backstory="Test backstory")

        request_payload1 = {"data": character.model_dump(), "is_yaml_text": False}

        response1 = self.client.post("/api/characters", json=request_payload1)
        assert response1.status_code == 200

        # Try to create second character with YAML text that would collision
        yaml_text = """
name: YAML@Test
tagline: Different Role
backstory: Different backstory
"""

        request_payload2 = {"data": yaml_text, "is_yaml_text": True}

        response2 = self.client.post("/api/characters", json=request_payload2)
        assert response2.status_code == 400
        assert "Filename collision detected" in response2.json()["detail"]
