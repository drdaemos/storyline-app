import re
from collections.abc import Callable

from src.components.character_pipeline import CharacterPipeline, CharacterResponseInput, EvaluationInput, PlanGenerationInput
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.models.message import GenericMessage


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
        self.streaming_callback: Callable[[str], None] | None = None
        self.dependencies = dependencies

        # Extract dependencies for easier access
        self.processor = dependencies.primary_processor
        self.backup_processor = dependencies.backup_processor
        self.persistent_memory = dependencies.conversation_memory
        self.summary_memory = dependencies.summary_memory
        self.chat_logger = dependencies.chat_logger
        self.session_id = dependencies.session_id

        # Setup memory and session
        if self.persistent_memory and self.session_id:
            # Load recent messages from persistent memory
            self.memory = self.persistent_memory.get_recent_messages(
                character.name,
                self.session_id,
                limit=self.PROPAGATED_MEMORY_SIZE * 10 # fetch more to do an efficient summarization
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


    def respond(self, user_message: str, streaming_callback: Callable[[str], None] | None = None) -> str:
        """
        Generate a character response to the user message.

        Args:
            user_message: The user's input message
            streaming_callback: Optional callback for streaming response chunks

        Returns:
            The character's response text parsed from <character_response> tags
        """
        self.streaming_callback = streaming_callback

        # Log user message
        if self.chat_logger:
            self.chat_logger.log_message("USER", user_message)

        # Compress / summarize memory if too many messages
        if self._should_trigger_summarization(user_message):
            self.compress_memory()
            self.plans = self.get_character_plans()

        # Get scenario evaluation
        raw_evaluation = self.get_evaluation(user_message)

        # Extract character's idea of continuation
        continuation_option = self._parse_xml_tag(raw_evaluation, "continuation")
        option_text = self._parse_xml_tag(raw_evaluation, continuation_option) if continuation_option else None
        if option_text is None:
            raise ValueError("Failed to parse continuation option from evaluation response.")

        # If user mentioned their name - store it
        self.user_name = self._parse_xml_tag(raw_evaluation, "user_name") or self.user_name

        # Generate character response text
        # status_update comes from the previous response
        character_response = self.get_character_response(user_message, option_text, self.status_update, self.user_name)

        # Parse and extract status update from XML tags
        # Will be used on the next step
        self.status_update = self._parse_xml_tag(raw_evaluation, "status_update") or ""

        # Update memory with the new interaction
        user_msg: GenericMessage = {"role": 'user', "content": user_message}
        eval_msg: GenericMessage = {"role": 'assistant', "content": raw_evaluation}
        response_msg: GenericMessage = {"role": 'assistant', "content": character_response}

        self.memory = self.memory + [user_msg, eval_msg, response_msg]

        # Save to persistent memory if enabled
        if self.persistent_memory and self.session_id:
            self.persistent_memory.add_messages(self.character.name, self.session_id, [user_msg, eval_msg, response_msg])
            # Update current message offset
            self._current_message_offset += 3

        if self.chat_logger:
            self.chat_logger.log_message("-----", "")

        return character_response

    def get_evaluation(self, user_message: str) -> str:
        fallback = False
        input: EvaluationInput = {
            "summary": self.memory_summary,
            "plans": self.plans,
            "user_message": user_message,
            "character": self.character
        }

        # Process the prompt
        try:
            evaluation = CharacterPipeline.get_evaluation(
                processor=self.processor,
                input=input,
                memory=self.memory[-self.PROPAGATED_MEMORY_SIZE:]  # pass only the most recent messages for context
            )
            if evaluation is None:
                raise ValueError("No evaluation from primary processor.")
        except Exception as e: # type: ignore
            fallback = True
            evaluation = CharacterPipeline.get_evaluation(
                processor=self.backup_processor,
                input=input,
                memory=self.memory[-self.PROPAGATED_MEMORY_SIZE:]  # pass only the most recent messages for context
            )
            if evaluation is None:
                raise ValueError("No evaluation from both primary and backup processor.")

        if self.chat_logger:
            self.chat_logger.log_message(f"ASSISTANT (EVAL) {"FALLBACK" if fallback else "NORMAL"}", evaluation)

        return evaluation

    def get_character_plans(self) -> str:
        fallback = False
        input: PlanGenerationInput = {
            "character": self.character,
            "user_name": self.user_name,
            "summary": self.memory_summary,
            "scenario_state": self.status_update
        }

        # Process the prompt
        try:
            plans = CharacterPipeline.get_character_plans(
                processor=self.processor,
                input=input
            )
            if plans is None:
                raise ValueError("No plans from primary processor.")
        except Exception as e: # type: ignore
            fallback = True
            plans = CharacterPipeline.get_character_plans(
                processor=self.backup_processor,
                input=input
            )
            if plans is None:
                raise ValueError("Failed to get plans from both primary and backup processors.")

        if self.chat_logger:
            self.chat_logger.log_message(f"PLANS ({"FALLBACK" if fallback else "NORMAL"})", plans)

        return plans

    def get_character_response(self, user_message: str, continuation_option: str, scenario_state: str, user_name: str) -> str:

        fallback = False
        input: CharacterResponseInput = {
            "summary": self.memory_summary,
            "previous_response": self.memory[-1]["content"] if self.memory else "",
            "user_message": user_message,
            "continuation_option": continuation_option,
            "scenario_state": scenario_state,
            "user_name": user_name,
            "character_name": self.character.name
        }

        # Process the prompt
        try:
            stream = CharacterPipeline.get_character_response(
                processor=self.processor,
                input=input
            )
            if stream is None:
                raise ValueError("No response stream from primary processor.")
        except Exception as e: # type: ignore
            fallback = True
            stream = CharacterPipeline.get_character_response(
                processor=self.backup_processor,
                input=input
            )
            if stream is None:
                raise ValueError("Failed to get character response from both primary and backup processors.")

        response = ""
        for chunk in stream:
            response += chunk
            if self.streaming_callback:
                self.streaming_callback(chunk)

        if self.chat_logger:
            self.chat_logger.log_message(f"CHARACTER ({"FALLBACK" if fallback else "NORMAL"})", response)

        return response

    def get_memory_summary(self, conversation_memory: list[GenericMessage]) -> str:
        try:
            summary = CharacterPipeline.get_memory_summary(
                processor=self.processor,
                memory=conversation_memory
            )
        except Exception as e: # type: ignore
            summary = CharacterPipeline.get_memory_summary(
                processor=self.backup_processor,
                memory=conversation_memory
            )

        if self.chat_logger:
            self.chat_logger.log_message(f"SUMMARY ({len(conversation_memory)} messages)", summary)

        return summary

    def compress_memory(self) -> None:
        """Compress the current memory using the summarization mechanism."""
        if not self.memory:
            return

        # Calculate offset range for the messages being summarized
        messages_to_summarize = self.memory[:-self.EPOCH_MESSAGES]
        if not messages_to_summarize:
            return

        # Calculate start and end offsets for the messages being summarized
        start_offset = self._current_message_offset - len(self.memory)
        end_offset = self._current_message_offset - self.EPOCH_MESSAGES - 1

        summary_msg: GenericMessage = { "role": "user", "content": f"Summary of previous interactions: {self.memory_summary}"}
        new_summary = self.get_memory_summary([summary_msg] + self.memory)

        # Store the summary with offset range in SummaryMemory
        if self.summary_memory and self.session_id:
            self.summary_memory.add_summary(
                character_id=self.character.name,
                session_id=self.session_id,
                summary=new_summary,
                start_offset=max(0, start_offset),  # Ensure non-negative
                end_offset=max(0, end_offset)       # Ensure non-negative
            )

        self.memory_summary = new_summary
        self.memory = self.memory[-self.EPOCH_MESSAGES:]

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
        max_processed_offset = self.summary_memory.get_max_processed_offset(self.session_id)

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
        pattern = rf'<{tag}>(.*?)</{tag}>'
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
            if message["role"] == "assistant":
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

        self.persistent_memory.delete_session(self.session_id)
        if self.summary_memory:
            self.summary_memory.delete_session_summaries(self.session_id)
        self.memory = []
        self.memory_summary = ""
        self._current_message_offset = 0
        return True

    def create_new_session(self) -> str | None:
        """
        Create a new session for this character.

        Returns:
            New session ID or None if persistent memory not enabled
        """
        if not self.persistent_memory:
            return None

        self.session_id = self.persistent_memory.create_session(self.character.name)
        self.memory = []
        self._current_message_offset = 0
        return self.session_id

    def _get_current_message_offset(self) -> int:
        """
        Get the current message offset for the session.

        Returns:
            Current message offset (total messages in session)
        """
        if not self.persistent_memory or not self.session_id:
            return 0

        # Get all messages for this session to determine current offset
        all_messages = self.persistent_memory.get_session_messages(self.session_id)
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
        summaries = self.summary_memory.get_session_summaries(self.session_id)
        if not summaries:
            return ""

        # Concatenate all summary texts
        summary_parts: list[str] = []
        for summary in summaries:
            summary_parts.append(f"Summary (messages {summary['start_offset']}-{summary['end_offset']}): {summary['summary']}")

        return "\n".join(summary_parts)


