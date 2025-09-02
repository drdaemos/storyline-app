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
        self.chat_logger = dependencies.chat_logger
        self.session_id = dependencies.session_id

        # Setup memory and session
        if self.persistent_memory and self.session_id:
            # Load recent messages from persistent memory
            self.memory = self.persistent_memory.get_recent_messages(
                character.name,
                self.session_id,
                limit=self.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * self.EPOCH_MESSAGES
            )
        else:
            self.memory: list[GenericMessage] = []

        self.memory_summary = ""
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
        if len(self.memory) >= self.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * self.EPOCH_MESSAGES:
            summary_msg: GenericMessage = { "role": "user", "content": f"Summary of previous interactions: {self.memory_summary}"}
            self.memory_summary = self.get_memory_summary([summary_msg] + self.memory)
            self.memory = self.memory[-self.EPOCH_MESSAGES:]
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

        if self.chat_logger:
            self.chat_logger.log_message("-----", "")

        return character_response

    def get_evaluation(self, user_message: str) -> str:
        fallback = False
        input: EvaluationInput = {
            "memory_summary": self.memory_summary,
            "plans": self.plans,
            "user_message": user_message,
            "character": self.character
        }

        # Process the prompt
        evaluation = CharacterPipeline.get_evaluation(
            processor=self.processor,
            input=input,
            memory=self.memory
        )

        if evaluation is None:
            fallback = True
            evaluation = CharacterPipeline.get_evaluation(
                processor=self.backup_processor,
                input=input,
                memory=self.memory
            )
            if evaluation is None:
                raise ValueError("Failed to get evaluation from both primary and backup processors.")

        if self.chat_logger:
            self.chat_logger.log_message(f"ASSISTANT (EVAL) {"FALLBACK" if fallback else "NORMAL"}", evaluation)

        return evaluation

    def get_character_plans(self) -> str:
        fallback = False
        input: PlanGenerationInput = {
            "character_name": self.character.name,
            "user_name": self.user_name,
            "summary": self.memory_summary,
            "scenario_state": self.status_update
        }

        # Process the prompt
        plans = CharacterPipeline.get_character_plans(
            processor=self.processor,
            input=input
        )

        if plans is None:
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
            "previous_response": self.memory[-1]["content"] if self.memory else "",
            "user_message": user_message,
            "continuation_option": continuation_option,
            "scenario_state": scenario_state,
            "user_name": user_name,
            "character_name": self.character.name
        }

        # Process the prompt
        stream = CharacterPipeline.get_character_response(
            processor=self.processor,
            input=input
        )

        if stream is None:
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
        return CharacterPipeline.get_memory_summary(
            processor=self.processor,
            memory=conversation_memory
        )

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
        self.memory = []
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
        return self.session_id


