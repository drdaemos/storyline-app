import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.agent import NPCAgent


class TestNPCAgent:
    def test_init(self):
        with patch("src.agent.LLM") as mock_llm, patch("src.agent.Agent") as mock_agent:
            agent = NPCAgent(role="Blacksmith", backstory="A skilled craftsman", name="Gareth")

            assert agent.name == "Gareth"
            assert agent.role == "Blacksmith"
            assert agent.backstory == "A skilled craftsman"
            assert agent.memory is not None
            assert agent.few_shot_loader is not None

            # Verify LLM was created with correct parameters
            mock_llm.assert_called_once_with(model="openai/gpt-4.1", stream=True)

            # Verify Agent was created with correct parameters
            mock_agent.assert_called_once_with(
                llm=mock_llm.return_value,
                role="Blacksmith",
                goal="Act as Gareth, staying in character and using your memory of past interactions",
                backstory="A skilled craftsman",
                verbose=False,
                allow_delegation=False,
            )

    def test_init_default_name(self):
        with patch("src.agent.LLM"), patch("src.agent.Agent"):
            agent = NPCAgent(role="Merchant", backstory="A traveling trader")

            assert agent.name == "NPC"

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_respond(self, mock_llm, mock_agent, mock_task, mock_crew):
        # Setup mocks
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance
        mock_crew_instance.kickoff.return_value = "Hello, traveler! How can I help you today?"

        # Create agent
        agent = NPCAgent(role="Innkeeper", backstory="Friendly innkeeper who knows everyone", name="Martha")

        # Test response
        response = agent.respond("Hello there!")

        # Verify the response
        assert response == "Hello, traveler! How can I help you today?"

        # Verify Task was created with correct description
        mock_task.assert_called_once()
        task_call_args = mock_task.call_args[1]

        assert "You are Martha" in task_call_args["description"]
        assert "Friendly innkeeper who knows everyone" in task_call_args["description"]
        assert "Respond to the following user message: Hello there!" in task_call_args["description"]
        assert task_call_args["agent"] == mock_agent.return_value
        assert task_call_args["expected_output"] == "A character response that stays in role and references memory when appropriate"

        # Verify Crew was created correctly
        mock_crew.assert_called_once_with(agents=[mock_agent.return_value], tasks=[mock_task.return_value], verbose=False)

        # Verify crew.kickoff was called
        mock_crew_instance.kickoff.assert_called_once()

        # Verify conversation was added to memory
        assert len(agent.memory.conversations) == 1
        conversation = agent.memory.conversations[0]
        assert conversation["user"] == "Hello there!"
        assert conversation["npc"] == "Hello, traveler! How can I help you today?"

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_respond_with_memory_context(self, mock_llm, mock_agent, mock_task, mock_crew):
        # Setup mocks
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance
        mock_crew_instance.kickoff.return_value = "I remember you mentioned the weather earlier!"

        # Create agent and add some memory
        agent = NPCAgent(role="Guard", backstory="Village guard who remembers faces", name="Captain Rex")

        # Add previous conversation to memory
        agent.memory.add_conversation("Nice weather today", "Indeed it is!")
        agent.memory.add_fact("weather_preference", "sunny")

        # Test response
        response = agent.respond("Do you remember me?")

        # Verify Task was created with memory context
        mock_task.assert_called_once()
        task_description = mock_task.call_args[1]["description"]

        assert "Previous conversations:" in task_description
        assert "User: Nice weather today" in task_description
        assert "NPC: Indeed it is!" in task_description
        assert "Known facts:" in task_description
        assert "- weather_preference: sunny" in task_description
        assert "Respond to the following user message: Do you remember me?" in task_description

        # Verify response and memory update
        assert response == "I remember you mentioned the weather earlier!"
        assert len(agent.memory.conversations) == 2

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_respond_handles_crew_result_conversion(self, mock_llm, mock_agent, mock_task, mock_crew):
        # Test that non-string results are converted to strings
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance

        # Mock a complex result object
        mock_result = Mock()
        mock_result.__str__ = Mock(return_value="Converted response")
        mock_crew_instance.kickoff.return_value = mock_result

        agent = NPCAgent("Wizard", "Ancient wizard", "Merlin")
        response = agent.respond("Cast a spell!")

        assert response == "Converted response"
        mock_result.__str__.assert_called_once()

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_multiple_responses_build_memory(self, mock_llm, mock_agent, mock_task, mock_crew):
        # Setup mocks
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance

        responses = ["Hello!", "How are you?", "Goodbye!"]
        mock_crew_instance.kickoff.side_effect = responses

        agent = NPCAgent("Bard", "Traveling musician", "Melody")

        # Make multiple calls
        for i, expected_response in enumerate(responses):
            user_input = f"Message {i + 1}"
            response = agent.respond(user_input)

            assert response == expected_response
            assert len(agent.memory.conversations) == i + 1

            # Check that the latest conversation is stored correctly
            latest_conv = agent.memory.conversations[-1]
            assert latest_conv["user"] == user_input
            assert latest_conv["npc"] == expected_response

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_respond_includes_few_shot_examples(self, mock_llm, mock_agent, mock_task, mock_crew):
        """Test that few-shot examples are included in the task description."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test example file
            example_file = Path(temp_dir) / "style_example.txt"
            example_file.write_text("Greetings, noble traveler! *tips hat*", encoding="utf-8")

            # Setup mocks
            mock_crew_instance = Mock()
            mock_crew.return_value = mock_crew_instance
            mock_crew_instance.kickoff.return_value = "Greetings, friend!"

            # Patch FewShotLoader to use our temp directory
            with patch("src.agent.FewShotLoader") as mock_loader_class:
                mock_loader = Mock()
                mock_loader.get_style_context.return_value = "Few-shot style examples:\nGreetings, noble traveler! *tips hat*\n---\n\n"
                mock_loader_class.return_value = mock_loader

                # Create agent
                agent = NPCAgent(role="Knight", backstory="Honorable knight", name="Sir Lancelot")

                # Test response
                agent.respond("Hello!")

                # Verify Task was created with few-shot context
                mock_task.assert_called_once()
                task_description = mock_task.call_args[1]["description"]

                assert "Few-shot style examples:" in task_description
                assert "Greetings, noble traveler! *tips hat*" in task_description
                assert "If few-shot examples are provided below, emulate their writing style" in task_description
                assert "You are Sir Lancelot" in task_description
                assert "Respond to the following user message: Hello!" in task_description

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_respond_without_few_shot_examples(self, mock_llm, mock_agent, mock_task, mock_crew):
        """Test behavior when no few-shot examples are available."""
        # Setup mocks
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance
        mock_crew_instance.kickoff.return_value = "Hello there!"

        # Patch FewShotLoader to return empty context
        with patch("src.agent.FewShotLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.get_style_context.return_value = ""
            mock_loader_class.return_value = mock_loader

            # Create agent
            agent = NPCAgent(role="Merchant", backstory="Friendly merchant", name="Bob")

            # Test response
            agent.respond("Hi!")

            # Verify Task was created without few-shot context
            mock_task.assert_called_once()
            task_description = mock_task.call_args[1]["description"]

            # Should not contain few-shot content since context is empty
            assert "Few-shot style examples:" not in task_description
            assert "You are Bob" in task_description
            assert "Friendly merchant" in task_description
            assert "Respond to the following user message: Hi!" in task_description

    @patch("src.agent.Crew")
    @patch("src.agent.Task")
    @patch("src.agent.Agent")
    @patch("src.agent.LLM")
    def test_few_shot_loader_integration(self, mock_llm, mock_agent, mock_task, mock_crew):
        """Test that FewShotLoader is properly integrated and called."""
        # Setup mocks
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance
        mock_crew_instance.kickoff.return_value = "Response"

        with patch("src.agent.FewShotLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.get_style_context.return_value = "Test context"
            mock_loader_class.return_value = mock_loader

            # Create agent and respond
            agent = NPCAgent("Role", "Backstory", "Name")
            agent.respond("Input")

            # Verify FewShotLoader was instantiated
            mock_loader_class.assert_called_once_with()

            # Verify get_style_context was called
            mock_loader.get_style_context.assert_called_once()
