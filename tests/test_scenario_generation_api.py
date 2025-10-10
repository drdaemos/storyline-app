from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app
from src.models.api_models import Scenario
from src.models.character import Character


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_character():
    """Create mock character for testing."""
    return Character(
        name="Eldrin",
        role="Wizard",
        backstory="Ancient spellcaster seeking lost knowledge",
        personality="Wise but eccentric",
        appearance="Elderly man with flowing robes and a staff",
        relationships={"apprentice": "Young mage learning the craft"},
        key_locations=["Tower of Stars", "Ancient Library"],
        setting_description="A magical realm where arcane power flows freely"
    )


@pytest.fixture
def mock_scenarios():
    """Create mock scenarios for testing."""
    return [
        Scenario(
            summary="Tower encounter with floating spellbooks",
            intro_message="You find Eldrin in his tower, surrounded by floating spell books that drift lazily through the air. He gestures excitedly when he sees you, his eyes bright with discovery.",
            narrative_category="conventional"
        ),
        Scenario(
            summary="Library breakthrough with magical papers",
            intro_message="Eldrin rushes past you in the library, muttering about a breakthrough. Papers fly in his wake, some glowing with arcane symbols. He barely notices you in his excitement.",
            narrative_category="urgent discovery"
        ),
        Scenario(
            summary="Contemplative fireside moment",
            intro_message="The wizard sits by the fire, deep in thought as shadows dance across his weathered features. He looks up as you enter, relief crossing his face.",
            narrative_category="introspective"
        )
    ]


def _setup_mocks(mock_loader_class, mock_generator_class, mock_deps_class, mock_character, mock_scenarios):
    """Setup all necessary mocks for API tests."""
    # Setup character loader mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_character.return_value = mock_character
    mock_loader_class.return_value = mock_loader_instance

    # Setup dependencies mock
    mock_processor = Mock()
    mock_deps = Mock()
    mock_deps.primary_processor = mock_processor
    mock_deps_class.create_default.return_value = mock_deps

    # Setup scenario generator mock
    mock_generator_instance = Mock()
    mock_generator_instance.generate_scenarios.return_value = mock_scenarios
    mock_generator_class.return_value = mock_generator_instance

    return mock_loader_instance, mock_generator_instance


class TestScenarioGenerationAPI:
    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_default_count(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character,
        mock_scenarios
    ):
        """Test scenario generation with default count."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.return_value = mock_scenarios
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin"
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert "character_name" in data
        assert "scenarios" in data
        assert data["character_name"] == "Eldrin"
        assert len(data["scenarios"]) == 3

        # Verify scenario structure
        for scenario in data["scenarios"]:
            assert "summary" in scenario
            assert isinstance(scenario["summary"], str)
            assert "intro_message" in scenario
            assert isinstance(scenario["intro_message"], str)
            assert "narrative_category" in scenario
            assert isinstance(scenario["narrative_category"], str)

        # Verify loader was called
        mock_loader.load_character.assert_called_once_with("eldrin")

        # Verify generator was called with default count (3)
        mock_generator_instance.generate_scenarios.assert_called_once()
        call_args = mock_generator_instance.generate_scenarios.call_args
        assert call_args[1]["count"] == 3

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_custom_count(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character
    ):
        """Test scenario generation with custom count."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        custom_scenarios = [
            Scenario(
                summary=f"Scenario {i} summary",
                intro_message=f"This is the intro message for scenario {i} with detailed scene description.",
                narrative_category=f"category {i}"
            ) for i in range(5)
        ]
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.return_value = custom_scenarios
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request with custom count
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "count": 5
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["scenarios"]) == 5

        # Verify generator was called with correct count
        call_args = mock_generator_instance.generate_scenarios.call_args
        assert call_args[1]["count"] == 5

    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_character_not_found(self, mock_loader, client):
        """Test scenario generation when character is not found."""
        # Setup mock to raise FileNotFoundError
        mock_loader.load_character.side_effect = FileNotFoundError("Character 'unknown' not found in database")

        # Make request
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "unknown"
            }
        )

        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_validation_error(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character
    ):
        """Test scenario generation with validation error."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.side_effect = ValueError("Scenario count must be between 1 and 10")
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request with invalid count
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "count": 15
            }
        )

        # Verify error response (could be 400 from validation or caught ValueError)
        assert response.status_code in [400, 422]

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_server_error(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character
    ):
        """Test scenario generation with server error."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.side_effect = Exception("Server error")
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin"
            }
        )

        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to generate scenarios" in data["detail"]

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_custom_processor(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character,
        mock_scenarios
    ):
        """Test scenario generation with custom processor type."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.return_value = mock_scenarios
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request with custom processor
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "processor_type": "openai",
                "backup_processor_type": "claude"
            }
        )

        # Verify response
        assert response.status_code == 200

        # Verify dependencies were created with correct processor types
        mock_deps_class.create_default.assert_called_once()
        call_kwargs = mock_deps_class.create_default.call_args[1]
        assert call_kwargs["processor_type"] == "openai"
        assert call_kwargs["backup_processor_type"] == "claude"

    def test_generate_scenarios_missing_character_name(self, client):
        """Test scenario generation without character name."""
        response = client.post(
            "/api/scenarios/generate",
            json={
                "count": 3
            }
        )

        # Should return validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_generate_scenarios_invalid_count_type(self, client):
        """Test scenario generation with invalid count type."""
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "count": "invalid"
            }
        )

        # Should return validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_boundary_count_1(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character
    ):
        """Test scenario generation with count=1 (minimum valid)."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        single_scenario = [Scenario(
            summary="Single scenario",
            intro_message="This is a single scenario intro message.",
            narrative_category="conventional"
        )]
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.return_value = single_scenario
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "count": 1
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["scenarios"]) == 1

    @patch('src.fastapi_server.CharacterResponderDependencies')
    @patch('src.fastapi_server.ScenarioGenerator')
    @patch('src.fastapi_server.character_loader')
    def test_generate_scenarios_boundary_count_10(
        self,
        mock_loader,
        mock_generator_class,
        mock_deps_class,
        client,
        mock_character
    ):
        """Test scenario generation with count=10 (maximum valid)."""
        # Setup mocks
        mock_loader.load_character.return_value = mock_character
        ten_scenarios = [Scenario(
            summary=f"Scenario {i} summary",
            intro_message=f"This is the intro message for scenario {i}.",
            narrative_category=f"category {i}"
        ) for i in range(10)]
        mock_generator_instance = Mock()
        mock_generator_instance.generate_scenarios.return_value = ten_scenarios
        mock_generator_class.return_value = mock_generator_instance

        mock_processor = Mock()
        mock_deps = Mock()
        mock_deps.primary_processor = mock_processor
        mock_deps_class.create_default.return_value = mock_deps

        # Make request
        response = client.post(
            "/api/scenarios/generate",
            json={
                "character_name": "eldrin",
                "count": 10
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["scenarios"]) == 10
