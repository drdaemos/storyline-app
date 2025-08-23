import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from src.cli import analyze, chat, cli
from src.interactive_chat import InteractiveChatCLI
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
            autonomy="independent",
            safety="secure",
            openmindedness="high",
            emotional_stability="stable",
            attachment_pattern="secure",
            conscientiousness="organized",
            sociability="extraverted",
            social_trust="trusting",
            risk_approach="balanced",
            conflict_approach="collaborative",
            leadership_style="democratic",
            stress_level="low",
            energy_level="medium",
            mood="neutral",
        )

        # Test without responder (should return no responder message)
        response = cli.get_ai_response("Hello")
        assert "No responder available" in response
        assert "Test Character" in response

    @patch("src.interactive_chat.Prompt.ask")
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
                "autonomy": "independent",
                "safety": "secure",
                "openmindedness": "high",
                "emotional_stability": "stable",
                "attachment_pattern": "secure",
                "conscientiousness": "organized",
                "sociability": "extraverted",
                "social_trust": "trusting",
                "risk_approach": "balanced",
                "conflict_approach": "collaborative",
                "leadership_style": "democratic",
                "stress_level": "low",
                "energy_level": "medium",
                "mood": "neutral",
            }

            char_file = chars_dir / "test.yaml"
            with open(char_file, "w") as f:
                yaml.dump(character_data, f)

            cli = InteractiveChatCLI()
            cli.loader.characters_dir = chars_dir

            mock_ask.return_value = "1"

            with patch.object(cli.console, "print"):
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
            autonomy="independent",
            safety="secure",
            openmindedness="high",
            emotional_stability="stable",
            attachment_pattern="secure",
            conscientiousness="organized",
            sociability="extraverted",
            social_trust="trusting",
            risk_approach="balanced",
            conflict_approach="collaborative",
            leadership_style="democratic",
            stress_level="low",
            energy_level="medium",
            mood="neutral",
        )

        with patch.object(cli.console, "print") as mock_print:
            cli.display_character_info(character)
            mock_print.assert_called_once()


class TestCLICommands:
    def test_cli_group(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Interactive chat and text analysis" in result.output

    @patch("src.cli.InteractiveChatCLI")
    def test_chat_command(self, mock_interactive_cli) -> None:
        runner = CliRunner()
        result = runner.invoke(chat, ["--list-characters"])
        assert result.exit_code == 0

    @patch("src.cli.TextAnalyzer")
    def test_analyze_command_with_file(self, mock_analyzer) -> None:
        # Mock the analyzer
        mock_instance = mock_analyzer.return_value
        mock_instance.analyze_file.return_value = {"file_path": "test.txt", "file_stats": {"word_count": 10, "character_count": 50}, "analysis": "Test analysis result"}

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("Test content")
            tmp_path = tmp.name

        try:
            result = runner.invoke(analyze, [tmp_path])
            assert result.exit_code == 0
            mock_instance.analyze_file.assert_called_once_with(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_analyze_command_nonexistent_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(analyze, ["nonexistent_file.txt"])
        assert result.exit_code != 0
