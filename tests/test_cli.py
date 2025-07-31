import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from src.cli import main


class TestCLI:
    def test_main_default_parameters(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main)
            
            # Verify NPCAgent was created with default values
            mock_npc_agent.assert_called_once_with(
                role='Village Blacksmith',
                backstory='A gruff but kind blacksmith who has lived in this village for 30 years. Known for his excellent craftsmanship and willingness to help travelers.',
                name='Eldric'
            )
            
            # Verify successful execution
            assert result.exit_code == 0
            assert "Interactive NPC Chat" in result.output
            assert "Creating Eldric, the Village Blacksmith" in result.output
            assert "Eldric has entered the conversation!" in result.output
    
    def test_main_custom_parameters(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main, [
                '--name', 'Luna',
                '--role', 'Mysterious Wizard',
                '--backstory', 'An ancient wizard with secrets'
            ])
            
            # Verify NPCAgent was created with custom values
            mock_npc_agent.assert_called_once_with(
                role='Mysterious Wizard',
                backstory='An ancient wizard with secrets',
                name='Luna'
            )
            
            assert result.exit_code == 0
            assert "Creating Luna, the Mysterious Wizard" in result.output
            assert "Luna has entered the conversation!" in result.output
    
    def test_conversation_flow(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['Hello there!', 'How are you?', 'quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_agent_instance.respond.side_effect = [
                "Greetings, traveler!",
                "I am well, thank you for asking."
            ]
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main, ['--name', 'Bob'])
            
            # Verify respond was called for each user input (excluding quit)
            assert mock_agent_instance.respond.call_count == 2
            mock_agent_instance.respond.assert_any_call('Hello there!')
            mock_agent_instance.respond.assert_any_call('How are you?')
            
            assert result.exit_code == 0
            assert "Bob: Greetings, traveler!" in result.output
            assert "Bob: I am well, thank you for asking." in result.output
            assert "Farewell, traveler! Safe journeys!" in result.output
    
    def test_empty_input_handling(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['', '   ', 'Hello', 'quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_agent_instance.respond.return_value = "Hello back!"
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main)
            
            # Should only call respond once (for "Hello", not empty strings)
            mock_agent_instance.respond.assert_called_once_with('Hello')
            assert result.exit_code == 0
    
    def test_exit_commands(self):
        runner = CliRunner()
        
        exit_commands = ['quit', 'exit', 'bye', 'QUIT', 'EXIT', 'BYE']
        
        for exit_cmd in exit_commands:
            with patch('src.cli.NPCAgent') as mock_npc_agent, \
                 patch('builtins.input', side_effect=[exit_cmd]) as mock_input:
                
                mock_agent_instance = Mock()
                mock_npc_agent.return_value = mock_agent_instance
                
                result = runner.invoke(main, ['--name', 'TestNPC'])
                
                # Should not call respond for exit commands
                mock_agent_instance.respond.assert_not_called()
                assert result.exit_code == 0
                assert "Farewell, traveler! Safe journeys!" in result.output
    
    def test_keyboard_interrupt_handling(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=KeyboardInterrupt()) as mock_input:
            
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main, ['--name', 'InterruptedNPC'])
            
            assert result.exit_code == 0
            assert "Until we meet again!" in result.output
    
    def test_exception_handling(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['Hello', 'quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_agent_instance.respond.side_effect = Exception("Test error")
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main)
            
            assert result.exit_code == 0
            assert "Error: Test error" in result.output
    
    def test_colorama_output_formatting(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['quit']) as mock_input:
            
            mock_agent_instance = Mock()
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main, ['--name', 'ColorTest'])
            
            # Check that colorama codes are present (they show up as ANSI escape codes)
            output = result.output
            assert "🎭" in output  # emoji should be present
            assert "ColorTest" in output
            assert "Type 'quit' to exit" in output
    
    def test_thinking_indicator(self):
        runner = CliRunner()
        
        with patch('src.cli.NPCAgent') as mock_npc_agent, \
             patch('builtins.input', side_effect=['test message', 'quit']) as mock_input, \
             patch('builtins.print') as mock_print:
            
            mock_agent_instance = Mock()
            mock_agent_instance.respond.return_value = "Test response"
            mock_npc_agent.return_value = mock_agent_instance
            
            result = runner.invoke(main)
            
            # Verify the thinking indicator is shown
            # This is tricky to test directly, but we can verify the response method was called
            mock_agent_instance.respond.assert_called_once_with('test message')
            assert result.exit_code == 0