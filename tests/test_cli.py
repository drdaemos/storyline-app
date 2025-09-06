import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

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
            personality="Independent, secure, organized character. Extroverted with balanced approach.",
            appearance="Test appearance",
            relationships={"user": "Test relationship"},
            key_locations=["Test Location"],
            setting_description="Test environment"
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
            personality="Independent, secure, organized character. Extroverted with balanced approach.",
            appearance="Test appearance",
            relationships={"user": "Test relationship"},
            key_locations=["Test Location"],
            setting_description="Test environment"
        )

        with patch.object(cli.console, "print") as mock_print:
            cli.display_character_info(character)
            mock_print.assert_called_once()

    @patch('src.interactive_chat.ConversationMemory')
    def test_setup_character_session_no_existing_sessions(self, mock_memory_class: Mock):
        """Test setting up character session when no existing sessions exist."""
        # Mock responder for session checking
        mock_memory_class.get_character_sessions.return_value = []

        cli = InteractiveChatCLI()
        character = Character(
            name="Test Character",
            role="Test Role",
            backstory="Test backstory",
            personality="Independent, secure, organized character. Extroverted with balanced approach.",
            appearance="Test appearance",
            relationships={"user": "Test relationship"},
            key_locations=["Test Location"],
            setting_description="Test environment"
        )

        with patch.object(cli.console, "print"):
            result = cli._setup_character_session(character)

        assert result.get_last_character_response() is None

    @patch('src.interactive_chat.ConversationMemory')
    @patch('src.models.character_responder_dependencies.ConversationMemory')
    def test_setup_character_session_continue_existing(self, mock_deps_memory_class: Mock, mock_memory_class: Mock):
        """Test setting up character session when choosing to continue existing session."""
        # Create a mock memory instance
        mock_memory_instance = Mock()
        mock_memory_instance.get_character_sessions.return_value = [{
            "session_id": 'test-session',
            "last_message_time": '2023-01-01',
            "message_count": 5
        }]
        mock_memory_instance.get_recent_messages.return_value = [{
            "role": 'user',
            "content": 'test'
        },{
            "role": 'assistant',
            "content": 'response'
        }]
        mock_memory_instance.get_session_messages.return_value = [{
            "role": 'user',
            "content": 'test'
        },{
            "role": 'assistant',
            "content": 'response'
        }]

        # Mock both ConversationMemory constructors to return the same mock instance
        mock_memory_class.return_value = mock_memory_instance
        mock_deps_memory_class.return_value = mock_memory_instance

        cli = InteractiveChatCLI()
        character = Character(
            name="Test Character",
            role="Test Role",
            backstory="Test backstory",
            personality="Independent, secure, organized character. Extroverted with balanced approach.",
            appearance="Test appearance",
            relationships={"user": "Test relationship"},
            key_locations=["Test Location"],
            setting_description="Test environment"
        )

        # Mock the session choice to return "continue"
        with patch.object(cli.console, "print"), \
             patch.object(cli, '_prompt_session_choice', return_value='continue'):
            result = cli._setup_character_session(character)

        assert result.get_last_character_response() == "response"

    @patch('src.interactive_chat.ConversationMemory')
    @patch('src.models.character_responder_dependencies.ConversationMemory')
    def test_setup_character_session_start_new(self, mock_deps_memory_class: Mock, mock_memory_class: Mock):
        """Test setting up character session when choosing to start new session."""
        # Create a mock memory instance
        mock_memory_instance = Mock()
        mock_memory_instance.get_character_sessions.return_value = [{
            "session_id": 'test-session',
            "last_message_time": '2023-01-01',
            "message_count": 5
        }]
        mock_memory_instance.get_recent_messages.return_value = [{
            "role": 'user',
            "content": 'test'
        },{
            "role": 'assistant',
            "content": 'response'
        }]

        # Create a separate mock memory instance for dependencies (after clear)
        mock_deps_memory_instance = Mock()
        mock_deps_memory_instance.get_recent_messages.return_value = []
        mock_deps_memory_instance.get_session_messages.return_value = []  # Add for offset tracking

        # Mock both ConversationMemory constructors
        mock_memory_class.return_value = mock_memory_instance
        mock_deps_memory_class.return_value = mock_deps_memory_instance

        cli = InteractiveChatCLI()
        character = Character(
            name="Test Character",
            role="Test Role",
            backstory="Test backstory",
            personality="Independent, secure, organized character. Extroverted with balanced approach.",
            appearance="Test appearance",
            relationships={"user": "Test relationship"},
            key_locations=["Test Location"],
            setting_description="Test environment"
        )

        with patch.object(cli.console, "print"), \
             patch.object(cli, '_prompt_session_choice', return_value='new'):
            result = cli._setup_character_session(character)

        assert result.get_last_character_response() is None

    def test_display_session_history(self):
        """Test displaying session history."""
        cli = InteractiveChatCLI()
        session_history = [
            {"session_id": "session-1", "message_count": 10, "last_message_time": "2023-01-01 10:00:00"},
            {"session_id": "session-2", "message_count": 5, "last_message_time": "2023-01-01 09:00:00"},
            {"session_id": "session-3", "message_count": 3, "last_message_time": "2023-01-01 08:00:00"},
            {"session_id": "session-4", "message_count": 1, "last_message_time": "2023-01-01 07:00:00"},
        ]

        with patch.object(cli.console, "print") as mock_print:
            cli._display_session_history(session_history)

        # Should print header + 3 sessions + "... and X more" message
        assert mock_print.call_count >= 4

    @patch('src.interactive_chat.Prompt.ask')
    def test_prompt_session_choice_continue(self, mock_ask):
        """Test prompting for session choice - continue option."""
        mock_ask.return_value = "1"

        cli = InteractiveChatCLI()

        with patch.object(cli.console, "print"):
            choice = cli._prompt_session_choice()

        assert choice == "continue"

    @patch('src.interactive_chat.Prompt.ask')
    def test_prompt_session_choice_new(self, mock_ask):
        """Test prompting for session choice - new option."""
        mock_ask.return_value = "2"

        cli = InteractiveChatCLI()

        with patch.object(cli.console, "print"):
            choice = cli._prompt_session_choice()

        assert choice == "new"

    @patch('src.interactive_chat.Prompt.ask')
    def test_prompt_session_choice_various_inputs(self, mock_ask):
        """Test prompting for session choice with various valid inputs."""
        cli = InteractiveChatCLI()

        test_cases = [
            ("continue", "continue"),
            ("c", "continue"),
            ("new", "new"),
            ("n", "new"),
            ("1", "continue"),
            ("2", "new")
        ]

        for input_val, expected in test_cases:
            mock_ask.return_value = input_val

            with patch.object(cli.console, "print"):
                choice = cli._prompt_session_choice()

            assert choice == expected, f"Input '{input_val}' should return '{expected}', got '{choice}'"


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
