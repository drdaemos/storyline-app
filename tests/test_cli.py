import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from click.testing import CliRunner

from src.cli import main


class TestCLI:
    def test_main_requires_parameters(self):
        runner = CliRunner()

        result = runner.invoke(main)

        assert result.exit_code == 0
        assert "Error: Either provide --character or all of --name, --role, and --backstory" in result.output

    def test_main_custom_parameters(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["quit"]),
        ):
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(
                main,
                [
                    "--name",
                    "Luna",
                    "--role",
                    "Mysterious Wizard",
                    "--backstory",
                    "An ancient wizard with secrets",
                ],
            )

            # Verify NPCAgent was created with custom values
            mock_npc_agent.assert_called_once_with(role="Mysterious Wizard", backstory="An ancient wizard with secrets", name="Luna")

            assert result.exit_code == 0
            assert "Creating Luna, the Mysterious Wizard" in result.output
            assert "Luna has entered the conversation!" in result.output

    def test_conversation_flow(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["Hello there!", "How are you?", "quit"]),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.respond.side_effect = [
                "Greetings, traveler!",
                "I am well, thank you for asking.",
            ]
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(main, ["--name", "Bob", "--role", "Merchant", "--backstory", "A friendly trader"])

            # Verify respond was called for each user input (excluding quit)
            assert mock_agent_instance.respond.call_count == 2
            mock_agent_instance.respond.assert_any_call("Hello there!")
            mock_agent_instance.respond.assert_any_call("How are you?")

            assert result.exit_code == 0
            assert "Bob: Greetings, traveler!" in result.output
            assert "Bob: I am well, thank you for asking." in result.output
            assert "Farewell, traveler! Safe journeys!" in result.output

    def test_empty_input_handling(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["", "   ", "Hello", "quit"]),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.respond.return_value = "Hello back!"
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(main, ["--name", "TestNPC", "--role", "Test Role", "--backstory", "Test backstory"])

            # Should only call respond once (for "Hello", not empty strings)
            mock_agent_instance.respond.assert_called_once_with("Hello")
            assert result.exit_code == 0

    def test_exit_commands(self):
        runner = CliRunner()

        exit_commands = ["quit", "exit", "bye", "QUIT", "EXIT", "BYE"]

        for exit_cmd in exit_commands:
            with (
                patch("src.cli.NPCAgent") as mock_npc_agent,
                patch("builtins.input", side_effect=[exit_cmd]),
            ):
                mock_agent_instance = Mock()
                mock_npc_agent.return_value = mock_agent_instance

                result = runner.invoke(
                    main,
                    ["--name", "TestNPC", "--role", "Test Role", "--backstory", "Test backstory"],
                )

                # Should not call respond for exit commands
                mock_agent_instance.respond.assert_not_called()
                assert result.exit_code == 0
                assert "Farewell, traveler! Safe journeys!" in result.output

    def test_keyboard_interrupt_handling(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=KeyboardInterrupt()),
        ):
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(
                main,
                [
                    "--name",
                    "InterruptedNPC",
                    "--role",
                    "Test Role",
                    "--backstory",
                    "Test backstory",
                ],
            )

            assert result.exit_code == 0
            assert "Until we meet again!" in result.output

    def test_exception_handling(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["Hello", "quit"]),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.respond.side_effect = Exception("Test error")
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(main, ["--name", "TestNPC", "--role", "Test Role", "--backstory", "Test backstory"])

            assert result.exit_code == 0
            assert "Error: Test error" in result.output

    def test_colorama_output_formatting(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["quit"]),
        ):
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(
                main,
                ["--name", "ColorTest", "--role", "Test Role", "--backstory", "Test backstory"],
            )

            # Check that colorama codes are present (they show up as ANSI escape codes)
            output = result.output
            assert "🎭" in output  # emoji should be present
            assert "ColorTest" in output
            assert "Type 'quit' to exit" in output

    def test_thinking_indicator(self):
        runner = CliRunner()

        with (
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["test message", "quit"]),
            patch("builtins.print"),
        ):
            mock_agent_instance = Mock()
            mock_agent_instance.respond.return_value = "Test response"
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(main, ["--name", "TestNPC", "--role", "Test Role", "--backstory", "Test backstory"])

            # Verify the thinking indicator is shown
            # This is tricky to test directly, but we can verify the response method was called
            mock_agent_instance.respond.assert_called_once_with("test message")
            assert result.exit_code == 0

    def test_list_characters_flag(self):
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            chars_dir = Path(temp_dir) / "characters"
            chars_dir.mkdir()

            # Create test character files
            char_data1 = {"name": "Alice", "role": "Merchant", "backstory": "A friendly trader"}
            char_data2 = {"name": "Bob", "role": "Guard", "backstory": "A town guard"}

            (chars_dir / "alice.yaml").write_text(yaml.dump(char_data1))
            (chars_dir / "bob.yaml").write_text(yaml.dump(char_data2))

            with patch("src.cli.CharacterLoader") as mock_loader_class:
                mock_loader = Mock()
                mock_loader.list_characters.return_value = ["alice", "bob"]
                mock_loader.get_character_info.side_effect = [char_data1, char_data2]
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(main, ["--list-characters"])

                assert result.exit_code == 0
                assert "Available characters:" in result.output
                assert "alice" in result.output
                assert "bob" in result.output
                assert "Merchant" in result.output
                assert "Guard" in result.output

    def test_list_characters_empty(self):
        runner = CliRunner()

        with patch("src.cli.CharacterLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.list_characters.return_value = []
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(main, ["--list-characters"])

            assert result.exit_code == 0
            assert "No character files found" in result.output

    def test_load_character_from_yaml(self):
        runner = CliRunner()

        character_data = {
            "name": "Eldric",
            "role": "Village Blacksmith",
            "backstory": "A gruff but kind blacksmith",
        }

        with (
            patch("src.cli.CharacterLoader") as mock_loader_class,
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["quit"]),
        ):
            mock_loader = Mock()
            mock_loader.load_character.return_value = character_data
            mock_loader_class.return_value = mock_loader

            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(main, ["--character", "eldric"])

            # Verify character was loaded
            mock_loader.load_character.assert_called_once_with("eldric")

            # Verify NPCAgent was created with loaded data
            mock_npc_agent.assert_called_once_with(role="Village Blacksmith", backstory="A gruff but kind blacksmith", name="Eldric")

            assert result.exit_code == 0
            assert "Loaded character from eldric.yaml" in result.output
            assert "Creating Eldric, the Village Blacksmith" in result.output

    def test_load_character_file_not_found(self):
        runner = CliRunner()

        with patch("src.cli.CharacterLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.load_character.side_effect = FileNotFoundError("Character file not found")
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(main, ["--character", "nonexistent"])

            assert result.exit_code == 0
            assert "Character file 'nonexistent.yaml' not found" in result.output

    def test_load_character_invalid_yaml(self):
        runner = CliRunner()

        with patch("src.cli.CharacterLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.load_character.side_effect = ValueError("Missing required field 'name'")
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(main, ["--character", "invalid"])

            assert result.exit_code == 0
            assert "Error loading character: Missing required field 'name'" in result.output

    def test_character_with_overrides(self):
        runner = CliRunner()

        character_data = {
            "name": "Original",
            "role": "Original Role",
            "backstory": "Original backstory",
        }

        with (
            patch("src.cli.CharacterLoader") as mock_loader_class,
            patch("src.cli.NPCAgent") as mock_npc_agent,
            patch("builtins.input", side_effect=["quit"]),
        ):
            mock_loader = Mock()
            mock_loader.load_character.return_value = character_data
            mock_loader_class.return_value = mock_loader

            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance

            result = runner.invoke(
                main,
                [
                    "--character",
                    "test",
                    "--name",
                    "Override Name",
                    "--backstory",
                    "Override backstory",
                ],
            )

            # Verify NPCAgent was created with overridden values
            mock_npc_agent.assert_called_once_with(
                role="Original Role",  # not overridden
                backstory="Override backstory",  # overridden
                name="Override Name",  # overridden
            )

            assert result.exit_code == 0
            assert "Creating Override Name, the Original Role" in result.output
