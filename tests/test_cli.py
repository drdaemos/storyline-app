import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from src.cli import InteractiveChatCLI
from src.models.character import Character


class TestInteractiveChatCLI:
    def test_init(self):
        cli = InteractiveChatCLI()
        assert cli.console is not None
        assert cli.loader is not None
        assert cli.current_character is None

    def test_get_ai_response(self):
        cli = InteractiveChatCLI()
        cli.current_character = Character(
            name="Test Character",
            role="Test Role",
            backstory="Test backstory",
            appearance="Test appearance",
            autonomy=5,
            safety=5,
            openmindedness=5,
            emotional_stability=5,
            attachment_pattern="secure",
            conscientiousness=5,
            sociability=5,
            social_trust=5,
            risk_approach="balanced",
            conflict_approach="collaborative",
            leadership_style="democratic",
            stress_level="low",
            energy_level="medium",
            mood="neutral"
        )

        # Test without actor (should return no actor message)
        response = cli.get_ai_response("Hello")
        assert "No actor available" in response
        assert "Test Character" in response

    @patch('src.cli.Prompt.ask')
    def test_select_character_with_valid_choice(self, mock_ask):
        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            # Create a minimal character file
            character_data = {
                "name": "Test Character",
                "role": "Test Role",
                "backstory": "Test backstory",
                "appearance": "Test appearance",
                "autonomy": 5,
                "safety": 5,
                "openmindedness": 5,
                "emotional_stability": 5,
                "attachment_pattern": "secure",
                "conscientiousness": 5,
                "sociability": 5,
                "social_trust": 5,
                "risk_approach": "balanced",
                "conflict_approach": "collaborative",
                "leadership_style": "democratic",
                "stress_level": "low",
                "energy_level": "medium",
                "mood": "neutral"
            }

            char_file = chars_dir / "test.yaml"
            with open(char_file, "w") as f:
                yaml.dump(character_data, f)

            cli = InteractiveChatCLI()
            cli.loader.characters_dir = chars_dir

            mock_ask.return_value = "1"

            with patch.object(cli.console, 'print'):
                character = cli.select_character()

            assert character is not None
            assert character.name == "Test Character"
            assert character.role == "Test Role"

    def test_display_character_info(self):
        cli = InteractiveChatCLI()
        character = Character(
            name="Test Character",
            role="Test Role",
            backstory="Test backstory",
            appearance="Test appearance",
            autonomy=5,
            safety=5,
            openmindedness=5,
            emotional_stability=5,
            attachment_pattern="secure",
            conscientiousness=5,
            sociability=5,
            social_trust=5,
            risk_approach="balanced",
            conflict_approach="collaborative",
            leadership_style="democratic",
            stress_level="low",
            energy_level="medium",
            mood="neutral"
        )

        with patch.object(cli.console, 'print') as mock_print:
            cli.display_character_info(character)
            mock_print.assert_called_once()
