import re
from datetime import UTC, datetime
from typing import Protocol

from src.components.character_pipeline import CharacterPipeline, CharacterResponseInput, EvaluationInput, GetMemorySummaryInput, PlanGenerationInput
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.models.evaluation import Evaluation
from src.models.message import GenericMessage
from src.models.persona import create_default_persona
from src.models.summary import PlotTracking, RelationshipState, StorySummary, TimeState


class EventCallback(Protocol):
    """Protocol for event callbacks that can send different types of events."""

    def __call__(self, event_type: str, **kwargs: str) -> None: ...


class StreamingCallback(Protocol):
    """Protocol for streaming callbacks that send text chunks."""

    def __call__(self, chunk: str) -> None: ...


class CharacterResponder:
    """Character responder that uses PromptProcessor to handle character interactions with XML tag parsing."""

    RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER = 15
    EPOCH_MESSAGES = 2
    PROPAGATED_MEMORY_SIZE = RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * EPOCH_MESSAGES

    def __init__(self, character: Character, dependencies: CharacterResponderDependencies, persona: Character | None = None) -> None:
        """
        Initialize the CharacterResponder.

        Args:
            character: Character instance to respond as
            dependencies: Dependencies container with processors, memory, logger, and session config
            persona: Optional persona character representing the user in the conversation
        """
        self.character = character
        self.streaming_callback: StreamingCallback | None = None
        self.event_callback: EventCallback | None = None
        self.dependencies = dependencies
        self.persona = persona or create_default_persona()

        # Extract dependencies for easier access
        self.processor = dependencies.primary_processor
        self.backup_processor = dependencies.backup_processor
        self.persistent_memory = dependencies.conversation_memory
        self.summary_memory = dependencies.summary_memory
        self.chat_logger = dependencies.chat_logger
        self.session_id = dependencies.session_id
        self.user_id = dependencies.user_id

        # Setup memory and session
        # Load existing summaries and concatenate them
        summary, last_offset = self._load_existing_summaries()
        self.memory_summary = summary

        # Load recent messages from persistent memory after the last summary offset
        # If last_offset is -1 (no summaries), use default from_offset=0 to get all messages
        # If last_offset is N (end of summary), use from_offset=N+1 to get messages after the summary
        if last_offset >= 0:
            self.memory = self.persistent_memory.get_recent_messages(
                self.session_id,
                self.user_id,
                limit=self.PROPAGATED_MEMORY_SIZE * 5,
                from_offset=last_offset + 1,
            )
        else:
            self.memory = self.persistent_memory.get_recent_messages(
                self.session_id,
                self.user_id,
                limit=self.PROPAGATED_MEMORY_SIZE * 5,
            )
        # Track current message offset for this session
        self._current_message_offset = self._get_current_message_offset()

        self.status_update = ""
        self.user_name = self.persona.name
        self.plans = ""

    def respond(self, user_message: str, streaming_callback: StreamingCallback | None = None, event_callback: EventCallback | None = None) -> str:
        """
        Generate a character response to the user message or handle commands.

        Args:
            user_message: The user's input message
            streaming_callback: Optional callback for streaming response chunks
            event_callback: Optional callback for events

        Returns:
            The character's response text or command result
        """
        self.streaming_callback = streaming_callback
        self.event_callback = event_callback

        # Check if the message is a command
        trimmed_message = user_message.strip()
        if trimmed_message.startswith("/"):
            return self._handle_command(trimmed_message)

        # Handle regular conversation
        return self._handle_conversation(user_message)

    def _handle_command(self, command: str) -> str:
        """
        Handle slash commands.

        Args:
            command: The command string starting with '/'

        Returns:
            Result of the command execution

        Raises:
            ValueError: For unknown commands or command execution errors
        """
        command_parts = command.split()
        command_name = command_parts[0].lower()

        if command_name == "/regenerate":
            return self._handle_regenerate_command()
        elif command_name == "/rewind":
            return self._handle_rewind_command()
        else:
            raise ValueError(f"Unknown command: {command_name}. Available commands: /regenerate, /rewind")

    def _handle_conversation(self, user_message: str) -> str:
        """
        Handle regular conversation flow.

        Args:
            user_message: The user's input message

        Returns:
            The character's response text parsed from <character_response> tags
        """
        # Log user message
        self.chat_logger.log_message("USER", user_message)

        user_msg: GenericMessage = {"role": "user", "content": user_message, "created_at": datetime.now(UTC).isoformat(), "type": "conversation"}

        # Compress / summarize memory if too many messages
        if self._should_trigger_summarization(user_message):
            if self.event_callback:
                self.event_callback("thinking", stage="summarizing")
            self.compress_memory()
            # self.plans = self.get_character_plans()

        # Get scenario evaluation
        # if self.event_callback:
        #     self.event_callback("thinking", stage="deliberating")
        # Disable eval for now
        # evaluation = self.get_evaluation(user_message)
        # eval_msg: GenericMessage = {"role": "assistant", "content": evaluation.to_string(), "created_at": datetime.now(UTC).isoformat(), "type": "evaluation"}

        # # Extract character's idea of continuation
        # continuation_option = self._parse_xml_tag(raw_evaluation, "continuation")
        # option_text = self._parse_xml_tag(raw_evaluation, continuation_option) if continuation_option else None
        # if option_text is None:
        #     raise ValueError("Failed to parse continuation option from evaluation response.")

        # If user mentioned their name - store it
        # self.user_name = evaluation.user_name or self.user_name

        # Generate character response text
        # status_update comes from the previous response
        if self.event_callback:
            self.event_callback("thinking", stage="responding")
        character_response = self.get_character_response(user_message, None)

        # Update memory with the new interaction
        response_msg: GenericMessage = {"role": "assistant", "content": character_response, "created_at": datetime.now(UTC).isoformat(), "type": "conversation"}

        self.memory = self.memory + [user_msg, response_msg]

        # Save to persistent memory
        self.persistent_memory.add_messages(self.character.name, self.session_id, [user_msg, response_msg], user_id=self.user_id)
        # Update current message offset
        self._current_message_offset += self.EPOCH_MESSAGES

        return character_response

    def _handle_regenerate_command(self) -> str:
        """
        Handle /regenerate command - regenerate the last character response.

        Returns:
            New character response

        Raises:
            ValueError: If there's no conversation history or no user message found
        """
        if not self.memory:
            raise ValueError("No conversation history to regenerate from.")

        # Find the last user message and remove subsequent assistant messages
        last_user_idx = -1
        for i in range(len(self.memory) - 1, -1, -1):
            if self.memory[i]["role"] == "user" and self.memory[i]["type"] == "conversation":
                last_user_idx = i
                break

        if last_user_idx == -1:
            raise ValueError("No user message found to regenerate response for.")

        # Get the last user message
        last_user_message = self.memory[last_user_idx]["content"]

        # Remove last round of conversation (user + assistant)
        messages_to_remove = len(self.memory) - last_user_idx
        self.memory = self.memory[:last_user_idx]

        # Update persistent memory and message offset
        if messages_to_remove > 0:
            # Calculate the offset from which to delete messages
            delete_from_offset = self._current_message_offset - messages_to_remove
            # Delete messages from persistent storage using offset
            self.persistent_memory.delete_messages_from_offset(self.session_id, self.user_id, delete_from_offset)
            # Update current message offset
            self._current_message_offset = delete_from_offset

        # Generate new response for the last user message
        return self._handle_conversation(last_user_message)

    def _handle_rewind_command(self) -> str:
        """
        Handle /rewind command - remove the last exchange (user message + assistant response).

        Returns:
            Empty string (communicates via streaming_callback)

        Raises:
            ValueError: If there's no conversation history or no user message found
        """
        if not self.memory:
            raise ValueError("No conversation history to rewind.")

        # Find the last user message and remove it along with subsequent assistant messages
        last_user_idx = -1
        for i in range(len(self.memory) - 1, -1, -1):
            if self.memory[i]["role"] == "user" and self.memory[i]["type"] == "conversation":
                last_user_idx = i
                break

        if last_user_idx == -1:
            raise ValueError("No user message found to rewind.")

        # Count messages to remove (from last user message to end)
        messages_to_remove = len(self.memory) - last_user_idx

        # Remove messages from memory
        self.memory = self.memory[:last_user_idx]

        # Update persistent memory and message offset
        # Calculate the offset from which to delete messages
        delete_from_offset = self._current_message_offset - messages_to_remove
        # Delete messages from persistent storage using offset
        self.persistent_memory.delete_messages_from_offset(self.session_id, self.user_id, delete_from_offset)
        # Update current message offset
        self._current_message_offset = delete_from_offset

        # Send completion event
        if self.event_callback:
            self.event_callback("command", succeeded="true")

        return ""

    def get_evaluation(self, user_message: str) -> Evaluation:
        fallback = False
        input: EvaluationInput = {"summary": self.memory_summary, "plans": self.plans, "user_message": user_message, "character": self.character}
        # pass only the most recent messages for context (use only user msg and character comms)
        memory: list[GenericMessage] = [msg for msg in self.memory[-self.PROPAGATED_MEMORY_SIZE :] if msg["type"] == "conversation"]

        # Process the prompt
        try:
            evaluation = CharacterPipeline.get_evaluation(
                processor=self.processor,
                input=input,
                memory=memory,  # pass only the most recent messages for context
            )
            # if evaluation is None:
            #     raise ValueError("No evaluation from primary processor.")
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err)
            fallback = True
            evaluation = CharacterPipeline.get_evaluation(processor=self.backup_processor, input=input, memory=memory)
            # if evaluation is None:
            #     raise ValueError("No evaluation from both primary and backup processor.") from err

        self.chat_logger.log_message(f"ASSISTANT (EVAL) {'FALLBACK' if fallback else 'NORMAL'}", evaluation.to_string())

        return evaluation

    def get_character_plans(self) -> str:
        fallback = False
        input: PlanGenerationInput = {"character": self.character, "user_name": self.user_name, "summary": self.memory_summary, "scenario_state": self.status_update}

        # Process the prompt
        try:
            plans = CharacterPipeline.get_character_plans(processor=self.processor, input=input)
            if plans is None:
                raise ValueError("No plans from primary processor.")
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err)
            fallback = True
            plans = CharacterPipeline.get_character_plans(processor=self.backup_processor, input=input)
            if plans is None:
                raise ValueError("Failed to get plans from both primary and backup processors.") from err

        self.chat_logger.log_message(f"PLANS ({'FALLBACK' if fallback else 'NORMAL'})", plans)

        return plans

    def get_character_response(self, user_message: str, scenario_state: Evaluation | None) -> str:
        fallback = False
        input_data: CharacterResponseInput = {
            "summary": self.memory_summary,
            "plans": self.plans,
            "previous_response": self.memory[-1]["content"] if self.memory else "",
            "user_message": user_message,
            "scenario_state": scenario_state.to_string() if scenario_state else "",
            "persona": self.persona,
            "character": self.character,
        }
        # pass only the most recent messages for context (use only user msg and character comms)
        memory: list[GenericMessage] = [msg for msg in self.memory[-self.PROPAGATED_MEMORY_SIZE :] if msg["type"] == "conversation"]

        # Process the prompt
        try:
            stream = CharacterPipeline.get_character_response(
                processor=self.processor,
                input=input_data,
                memory=memory,  # pass only the most recent messages for context
            )
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err)
            fallback = True
            stream = CharacterPipeline.get_character_response(
                processor=self.backup_processor,
                input=input_data,
                memory=memory,  # pass only the most recent messages for context
            )

        response = ""
        for chunk in stream:
            response += chunk
            if self.streaming_callback:
                self.streaming_callback(chunk)

        self.chat_logger.log_message(f"CHARACTER ({'FALLBACK' if fallback else 'NORMAL'})", response)

        return response

    def get_memory_summary(self, conversation_memory: list[GenericMessage]) -> StorySummary:
        input: GetMemorySummaryInput = {"character": self.character, "persona": self.persona, "summary": self.memory_summary}
        try:
            summary = CharacterPipeline.get_memory_summary(processor=self.processor, memory=conversation_memory, input=input)
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err)
            summary = CharacterPipeline.get_memory_summary(processor=self.backup_processor, memory=conversation_memory, input=input)

        self.chat_logger.log_message(f"SUMMARY ({len(conversation_memory)} messages)", summary.to_string())

        return summary

    def compress_memory(self) -> None:
        """Compress the current memory using the summarization mechanism."""
        if not self.memory:
            return

        # Calculate offset range for the messages being summarized
        messages_to_summarize = [msg for msg in self.memory if msg["type"] == "conversation"]

        if not messages_to_summarize:
            return

        # Calculate start and end offsets for the messages being summarized
        # start_offset is the offset of the first message being summarized
        # end_offset is the offset of the last message being summarized (inclusive)
        start_offset = self._current_message_offset - len(self.memory)
        end_offset = self._current_message_offset - 1  # -1 because offset is 0-indexed, but count is 1-indexed

        new_summary = self.get_memory_summary(messages_to_summarize)

        # Store the summary with offset range in SummaryMemory
        self.summary_memory.add_summary(
            character_id=self.character.name,
            session_id=self.session_id,
            summary=new_summary.model_dump_json(),
            start_offset=max(0, start_offset),  # Ensure non-negative
            end_offset=max(0, end_offset),  # Ensure non-negative
            user_id=self.user_id,
        )

        summary, last_offset = self._load_existing_summaries()
        self.memory_summary = summary
        # Keep the last EPOCH_MESSAGES, ensuring we have at least one user-assistant pair for /regenerate
        # Filter to keep only conversation messages, excluding any evaluation/summary messages
        conversation_msgs = [msg for msg in self.memory if msg["type"] == "conversation"]
        self.memory = conversation_msgs[-self.EPOCH_MESSAGES :]

    def _should_trigger_summarization(self, user_message: str) -> bool:
        """
        Determine if memory summarization should be triggered based on offset difference.

        Compares the current message offset with the end offset of the most recent summary.
        If the difference exceeds the trigger threshold, summarization is triggered.
        """
        # Get the maximum processed offset (end of last summary)
        max_processed_offset = self.summary_memory.get_max_processed_offset(self.session_id, self.user_id)

        # If no summaries exist, assume we start from offset -1 (so first message is offset 0)
        if max_processed_offset is None:
            max_processed_offset = -1

        # Calculate messages since last summary
        messages_since_last_summary = self._current_message_offset - max_processed_offset - 1

        # Trigger if we have enough new messages since the last summary
        return messages_since_last_summary >= self.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * self.EPOCH_MESSAGES

    def _parse_xml_tag(self, response_text: str, tag: str) -> str | None:
        """
        Parse character response from <character_response> XML tags.

        Args:
            response_text: Raw response text containing XML tags

        Returns:
            Extracted character response text, or original text if no tags found
        """
        # Look for content between <character_response> tags
        pattern = rf"<{tag}>(.*?)</{tag}>"
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Return the first match, stripped of leading/trailing whitespace
            return matches[0].strip()
        else:
            # If no tags found, return None to allow to handle this
            return None

    def get_last_character_response(self) -> str | None:
        """
        Get the last character response from the current session.

        Returns:
            The last character response text, or None if no previous response exists
        """
        if not self.memory:
            return None

        # Look for the most recent assistant message and parse the character response from it
        for message in reversed(self.memory):
            if message["role"] == "assistant" and message["type"] == "conversation":
                return message["content"]

        return None

    def clear_current_session(self) -> bool:
        """
        Clear the current session memory.

        Returns:
            True if session was cleared
        """
        self.persistent_memory.delete_session(self.session_id, self.user_id)
        self.summary_memory.delete_session_summaries(self.session_id, self.user_id)
        self.memory = []
        self.memory_summary = None
        self._current_message_offset = 0
        return True

    def _get_current_message_offset(self) -> int:
        """
        Get the current message offset for the session.

        Returns:
            Current message offset (total messages in session)
        """
        # Get all messages for this session to determine current offset
        all_messages = self.persistent_memory.get_session_messages(self.session_id, self.user_id)
        return len(all_messages)

    def _load_existing_summaries(self) -> tuple[StorySummary | None, int]:
        """
        Load existing summaries for the current session and concatenate them.

        Returns:
            Tuple of (summary text, last_offset)
            - summary text: Concatenated summary from all existing summaries
            - last_offset: The end_offset of the last summary, or -1 if no summaries exist
        """
        # Get all summaries for this session
        summaries = self.summary_memory.get_session_summaries(self.session_id, self.user_id)
        if not summaries:
            return None, -1  # Return -1 so that offset > -1 includes offset 0

        # Concatenate all summary texts
        beats = []
        learnings = []
        last_summary = None
        last_summary_offset = 0
        for summary in summaries:
            try:
                summary_model = StorySummary.model_validate_json(summary["summary"])
                beats.extend(summary_model.story_beats)
                learnings.extend(summary_model.user_learnings)
                last_summary_offset = summary["end_offset"]
                last_summary = summary_model
            except Exception as e:
                self.chat_logger.log_message("ERROR", f"Failed to parse summary JSON: {e}")

        summary = StorySummary(
            time=last_summary.time if last_summary else TimeState(current_time="Unknown"),
            relationship=last_summary.relationship if last_summary else RelationshipState(trust=5, attraction=5, emotional_intimacy=5, conflict=1, power_balance=5, relationship_label=''),
            plot=last_summary.plot if last_summary else PlotTracking(location="uknown", notable_objects=""),
            physical_state=last_summary.physical_state if last_summary else [],
            emotional_state=last_summary.emotional_state if last_summary else [],
            story_beats=beats,
            user_learnings=learnings,
            ai_quality_issues=last_summary.ai_quality_issues if last_summary else [],
        )

        return summary, last_summary_offset
