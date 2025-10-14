import re
from datetime import UTC, datetime
from typing import Protocol

from src.components.character_pipeline import CharacterPipeline, CharacterResponseInput, EvaluationInput, PlanGenerationInput
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.models.evaluation import Evaluation
from src.models.message import GenericMessage


class EventCallback(Protocol):
    """Protocol for event callbacks that can send different types of events."""

    def __call__(self, event_type: str, **kwargs: str) -> None: ...


class StreamingCallback(Protocol):
    """Protocol for streaming callbacks that send text chunks."""

    def __call__(self, chunk: str) -> None: ...


class CharacterResponder:
    """Character responder that uses PromptProcessor to handle character interactions with XML tag parsing."""

    RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER = 10
    EPOCH_MESSAGES = 3
    PROPAGATED_MEMORY_SIZE = RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * EPOCH_MESSAGES

    def __init__(self, character: Character, dependencies: CharacterResponderDependencies) -> None:
        """
        Initialize the CharacterResponder.

        Args:
            character: Character instance to respond as
            dependencies: Dependencies container with processors, memory, logger, and session config
        """
        self.character = character
        self.streaming_callback: StreamingCallback | None = None
        self.event_callback: EventCallback | None = None
        self.dependencies = dependencies

        # Extract dependencies for easier access
        self.processor = dependencies.primary_processor
        self.backup_processor = dependencies.backup_processor
        self.persistent_memory = dependencies.conversation_memory
        self.summary_memory = dependencies.summary_memory
        self.chat_logger = dependencies.chat_logger
        self.session_id = dependencies.session_id
        self.user_id = dependencies.user_id

        # Setup memory and session
        if self.persistent_memory and self.session_id:
            # Load recent messages from persistent memory
            self.memory = self.persistent_memory.get_recent_messages(
                self.session_id,
                self.user_id,
                limit=self.PROPAGATED_MEMORY_SIZE * 10,  # fetch more to do an efficient summarization
            )
            # Track current message offset for this session
            self._current_message_offset = self._get_current_message_offset()
        else:
            self.memory: list[GenericMessage] = []
            self._current_message_offset = 0

        # Load existing summaries and concatenate them
        self.memory_summary = self._load_existing_summaries()
        self.status_update = ""
        self.user_name = ""
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
        if self.chat_logger:
            self.chat_logger.log_message("USER", user_message)

        user_msg: GenericMessage = {"role": "user", "content": user_message, "created_at": datetime.now(UTC).isoformat(), "type": "conversation"}

        # Compress / summarize memory if too many messages
        if self._should_trigger_summarization(user_message):
            if self.event_callback:
                self.event_callback("thinking", stage="summarizing")
            self.compress_memory()
            self.plans = self.get_character_plans()

        # Get scenario evaluation
        if self.event_callback:
            self.event_callback("thinking", stage="deliberating")
        evaluation = self.get_evaluation(user_message)
        eval_msg: GenericMessage = {"role": "assistant", "content": evaluation.to_string(), "created_at": datetime.now(UTC).isoformat(), "type": "evaluation"}

        # # Extract character's idea of continuation
        # continuation_option = self._parse_xml_tag(raw_evaluation, "continuation")
        # option_text = self._parse_xml_tag(raw_evaluation, continuation_option) if continuation_option else None
        # if option_text is None:
        #     raise ValueError("Failed to parse continuation option from evaluation response.")

        # If user mentioned their name - store it
        self.user_name = evaluation.user_name or self.user_name

        # Generate character response text
        # status_update comes from the previous response
        if self.event_callback:
            self.event_callback("thinking", stage="responding")
        character_response = self.get_character_response(user_message, evaluation, self.user_name)

        # Update memory with the new interaction
        response_msg: GenericMessage = {"role": "assistant", "content": character_response, "created_at": datetime.now(UTC).isoformat(), "type": "conversation"}

        self.memory = self.memory + [user_msg, eval_msg, response_msg]

        # Save to persistent memory if enabled
        if self.persistent_memory and self.session_id:
            self.persistent_memory.add_messages(self.character.name, self.session_id, [user_msg, eval_msg, response_msg], user_id=self.user_id)
            # Update current message offset
            self._current_message_offset += 3

        if self.chat_logger:
            self.chat_logger.log_message("-----", "")

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

        # Update persistent memory and message offset if enabled
        if self.persistent_memory and self.session_id and messages_to_remove > 0:
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

        # Update persistent memory and message offset if enabled
        if self.persistent_memory and self.session_id:
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
            self.chat_logger.log_exception(err) if self.chat_logger else None
            fallback = True
            evaluation = CharacterPipeline.get_evaluation(processor=self.backup_processor, input=input, memory=memory)
            # if evaluation is None:
            #     raise ValueError("No evaluation from both primary and backup processor.") from err

        if self.chat_logger:
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
            self.chat_logger.log_exception(err) if self.chat_logger else None
            fallback = True
            plans = CharacterPipeline.get_character_plans(processor=self.backup_processor, input=input)
            if plans is None:
                raise ValueError("Failed to get plans from both primary and backup processors.") from err

        if self.chat_logger:
            self.chat_logger.log_message(f"PLANS ({'FALLBACK' if fallback else 'NORMAL'})", plans)

        return plans

    def get_character_response(self, user_message: str, scenario_state: Evaluation, user_name: str) -> str:
        fallback = False
        input: CharacterResponseInput = {
            "summary": self.memory_summary,
            "previous_response": self.memory[-1]["content"] if self.memory else "",
            "user_message": user_message,
            "scenario_state": scenario_state.to_string(),
            "user_name": user_name,
            "character": self.character,
        }
        # pass only the most recent messages for context (use only user msg and character comms)
        memory: list[GenericMessage] = [msg for msg in self.memory[-self.PROPAGATED_MEMORY_SIZE :] if msg["type"] == "conversation"]

        # Process the prompt
        try:
            stream = CharacterPipeline.get_character_response(
                processor=self.processor,
                input=input,
                memory=memory,  # pass only the most recent messages for context
            )
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err) if self.chat_logger else None
            fallback = True
            stream = CharacterPipeline.get_character_response(
                processor=self.backup_processor,
                input=input,
                memory=memory,  # pass only the most recent messages for context
            )

        response = ""
        for chunk in stream:
            response += chunk
            if self.streaming_callback:
                self.streaming_callback(chunk)

        if self.chat_logger:
            self.chat_logger.log_message(f"CHARACTER ({'FALLBACK' if fallback else 'NORMAL'})", response)

        return response

    def get_memory_summary(self, conversation_memory: list[GenericMessage]) -> str:
        try:
            summary = CharacterPipeline.get_memory_summary(processor=self.processor, memory=conversation_memory)
        except Exception as err:  # type: ignore
            self.chat_logger.log_exception(err) if self.chat_logger else None
            summary = CharacterPipeline.get_memory_summary(processor=self.backup_processor, memory=conversation_memory)

        if self.chat_logger:
            self.chat_logger.log_message(f"SUMMARY ({len(conversation_memory)} messages)", summary)

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
        start_offset = self._current_message_offset - len(self.memory)
        end_offset = self._current_message_offset

        new_summary = self.get_memory_summary(messages_to_summarize)

        # Store the summary with offset range in SummaryMemory
        if self.summary_memory and self.session_id:
            self.summary_memory.add_summary(
                character_id=self.character.name,
                session_id=self.session_id,
                summary=new_summary,
                start_offset=max(0, start_offset),  # Ensure non-negative
                end_offset=max(0, end_offset),  # Ensure non-negative
                user_id=self.user_id,
            )

        self.memory_summary = self._load_existing_summaries()
        self.memory = self.memory[-self.EPOCH_MESSAGES :]

    def _should_trigger_summarization(self, user_message: str) -> bool:
        """
        Determine if memory summarization should be triggered based on offset difference.

        Compares the current message offset with the end offset of the most recent summary.
        If the difference exceeds the trigger threshold, summarization is triggered.
        """
        if not self.summary_memory or not self.session_id:
            # Fallback to memory size if summary memory is not available
            return len(self.memory) >= self.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * self.EPOCH_MESSAGES

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
            True if session was cleared, False if persistent memory not enabled
        """
        if not self.persistent_memory or not self.session_id:
            return False

        self.persistent_memory.delete_session(self.session_id, self.user_id)
        if self.summary_memory:
            self.summary_memory.delete_session_summaries(self.session_id, self.user_id)
        self.memory = []
        self.memory_summary = ""
        self._current_message_offset = 0
        return True

    def _get_current_message_offset(self) -> int:
        """
        Get the current message offset for the session.

        Returns:
            Current message offset (total messages in session)
        """
        if not self.persistent_memory or not self.session_id:
            return 0

        # Get all messages for this session to determine current offset
        all_messages = self.persistent_memory.get_session_messages(self.session_id, self.user_id)
        return len(all_messages)

    def _load_existing_summaries(self) -> str:
        """
        Load existing summaries for the current session and concatenate them.

        Returns:
            Concatenated summary text from all existing summaries
        """
        if not self.summary_memory or not self.session_id:
            return ""

        # Get all summaries for this session
        summaries = self.summary_memory.get_session_summaries(self.session_id, self.user_id)
        if not summaries:
            return ""

        # Concatenate all summary texts
        summary_parts: list[str] = []
        summary_items: list[str] = []
        for summary in summaries:
            items = self._parse_xml_tag(summary["summary"], "story_summary")
            if items:
                summary_items.append(items)

            summary_parts.append(f"Summary (messages {summary['start_offset']}-{summary['end_offset']}): {summary['summary']}")

        return "\n".join(summary_parts)
