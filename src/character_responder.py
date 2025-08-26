import re
from collections.abc import Callable
from pathlib import Path

from src.chat_logger import ChatLogger
from src.claude_prompt_processor import ClaudePromptProcessor
from src.memory import ConversationMemory
from src.models.character import Character
from src.models.message import GenericMessage


class CharacterResponder:
    """Character responder that uses PromptProcessor to handle character interactions with XML tag parsing."""

    def __init__(self, character: Character, session_id: str | None = None, use_persistent_memory: bool = True, logs_dir: Path | None = None) -> None:
        """
        Initialize the CharacterResponder.

        Args:
            character: Character instance to respond as
            session_id: Optional session ID for persistent memory. If None and use_persistent_memory is True, creates new session
            use_persistent_memory: Whether to use persistent SQLite memory or in-memory only
        """
        self.character = character
        self.processor = ClaudePromptProcessor()
        self.streaming_callback: Callable[[str], None] | None = None
        self.use_persistent_memory = use_persistent_memory

        if use_persistent_memory:
            self.persistent_memory = ConversationMemory()
            self.session_id = session_id or self.persistent_memory.create_session(character.name)
            # Load recent messages from persistent memory
            self.memory = self.persistent_memory.get_recent_messages(character.name, self.session_id, limit=10)
        else:
            self.persistent_memory = None
            self.session_id = session_id  # Keep session_id for logging even without persistent memory
            self.memory: list[GenericMessage] = []

        self.memory_summary = ""
        self.state_update = ""

        self.chat_logger = ChatLogger(character.name, self.session_id or "no-session", logs_dir)

    def _map_character_to_prompt_variables(self, user_message: str) -> dict[str, str]:
        """
        Map Character attributes to prompt variables required by the roleplay prompt.

        Args:
            user_message: The user's input message

        Returns:
            Dictionary mapping prompt variable names to character-derived values
        """
        # Combine personality traits into a readable format
        personality_traits = [
            f"Autonomy: {self.character.autonomy}",
            f"Safety: {self.character.safety}",
            f"Openmindedness: {self.character.openmindedness}",
            f"Emotional Stability: {self.character.emotional_stability}",
            f"Attachment Pattern: {self.character.attachment_pattern}",
            f"Conscientiousness: {self.character.conscientiousness}",
            f"Sociability: {self.character.sociability}",
            f"Social Trust: {self.character.social_trust}",
            f"Risk Approach: {self.character.risk_approach}",
            f"Conflict Approach: {self.character.conflict_approach}",
            f"Leadership Style: {self.character.leadership_style}"
        ]

        # Combine current emotional state
        emotional_state = f"Mood: {self.character.mood}, Stress Level: {self.character.stress_level}, Energy Level: {self.character.energy_level}"

        return {
            "character_name": self.character.name,
            "character_background": f"{self.character.backstory}. Appearance: {self.character.appearance}",
            "character_traits": "; ".join(personality_traits),
            "emotional_state": emotional_state,
            "character_goals": "",
            "current_setting": "",
            "relationship_status": "",
            "user_message": user_message
        }

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
        self.chat_logger.log_message("USER", user_message)

        if len(self.memory) >= 10:
            self.memory_summary = self.get_memory_summary([{ "role": "user", "content": f"Summary of past interactions: {self.memory_summary}"}] + self.memory)
            self.memory = [{"role": "user", "content": f"Summary of past interactions: {self.memory_summary}"}]
            self.chat_logger.log_message("SUMMARY", self.memory_summary)

        raw_evaluation = self.get_evaluation(user_message)
        self.chat_logger.log_message("ASSISTANT (EVAL)", raw_evaluation)

        # Parse and extract selected option from XML tags
        selected_option = self._parse_xml_tag(raw_evaluation, "selected_option")

        raw_response = self.get_character_response(user_message, selected_option, self.state_update)
        self.chat_logger.log_message("ASSISTANT (RESPONSE)", raw_response)

        # Parse and extract character response from XML tags
        character_response = self._parse_xml_tag(raw_response, "character_response")
        self.chat_logger.log_message("CHARACTER", character_response)

        # Parse and extract character response from XML tags
        self.state_update = self._parse_xml_tag(raw_response, "state_update")

        # Call streaming callback with final response if provided
        if self.streaming_callback:
            self.streaming_callback(character_response)

        # Update memory with the new interaction
        user_msg = {"role": 'user', "content": user_message}
        assistant_msg = {"role": 'assistant', "content": raw_evaluation + "\n" + raw_response}

        self.memory = self.memory + [user_msg, assistant_msg]

        # Save to persistent memory if enabled
        if self.use_persistent_memory and self.persistent_memory and self.session_id:
            self.persistent_memory.add_message(self.character.name, self.session_id, 'user', user_message)
            self.persistent_memory.add_message(self.character.name, self.session_id, 'assistant', raw_evaluation + raw_response)

        self.chat_logger.log_message("-----", "")

        return character_response

    def get_evaluation(self, user_message: str) -> str:
        developer_prompt = """
You will simulate an autonomous NPC character in a text-based roleplay interaction. Follow the pipeline below
to generate realistic, character-driven responses that maintain narrative agency and emotional authenticity.
Be concise, brief and factual in the evaluation, avoid verbosity.

## Pipeline Process

Step 1: EVALUATION

Analyse the situation based on the user's input and the ongoing narrative. 
Outline the key observations, answering the following in a bullet list:

- What does the character see / feel?
- What body language or non-verbal cues are present?
- What might be the underlying intent or subtext?
- How does this relate to the ongoing dynamic?
- What does the character want in this moment?
- What emotional undertone is present?

Evaluation Result:

Importance Level: [CRITICAL/HIGH/MEDIUM/LOW]
Response Needed: [Yes/No]
Emotional Shift: [List specific emotions and intensity changes, e.g., "Confidence +2, Attraction +1"]

Step 2: PLAYWRIGHT PROMPT

Generate THREE distinct continuation options - for each, list actions performed by the character and outline questions or messages they are conveying. 
Use imperative verbs, as if the character has an internal monologue. For example:
- "They are agitated - need to calm them down."
- "Should ask them about their day."
You may add short snippets of the dialogue.
When character is feeling strong emotions (of any kind), use very short, punchy sentences.
Stay brief and factual, avoid subjective descriptors / adjectives. 
Do not refer to the character traits or backstory in the options.
Each option should be genuinely different (in terms of message or action), not variations of the same response.

Option [A/B/C]: [Next plot beat description]
Consequence: [How it affects the narrative or character dynamic, very short - 2-5 words]

Internal State: [Summarize character state of mind, internal debate, conflicts, desires]

Step 3: DIRECTOR PROMPT

Assess the situation and the plot state to consider pacing and transition over the story arc.
Avoid stalling the plot, keep the narrative moving forward.
Prefer options that are driven by the character's own agency rather than asking input from the user.

Provide the brief analysis of the narrative state, stating a bullet list that covers:

- Current narrative pacing and stage
- Character consistency
- Situational authenticity
- Recent action patterns (avoid repetition or stalling plot)
- Narrative goals

Describe how options fit / don't fit the arrative and select ONE best option.

Output the selected option again in <selected_option> tags.

## Character Definition

Character Name: {character_name}
Character Background: {character_background}
Character Personality Traits: {character_traits}
Character Current Emotional State: {emotional_state}
Character Goals/Desires: {character_goals}
Relationship to User Character: {relationship_status}
"""
        user_prompt = """
The user's message is:
{user_message}
"""

        # Map character attributes to prompt variables
        variables = self._map_character_to_prompt_variables(user_message)

        # Process the prompt
        evaluation = self.processor.process(
            prompt=developer_prompt.format(**variables),
            user_prompt=user_prompt,
            conversation_history=self.memory,
            variables=variables,
            output_type=str
        )

        return evaluation # pyright: ignore[reportReturnType]

    def get_character_response(self, user_message: str, option: str, previous_state: str) -> str:
        developer_prompt = """
You will act as an autonomous NPC character in a text-based roleplay interaction. Follow the pipeline below
to generate realistic, character-driven response that maintains narrative agency and emotional authenticity.
Do not be verbose, do not not add extra actions or dialogue outside of the selected option.
Separate spoken dialogue with newlines from the rest of the response.
Try to follow the show-don't-tell principle within the response.
You are allowed to narrative explicit actions, including intimacy - don't do fade to black things.

# RESPONSE GENERATION

<character_response>
[Generate the full response based ONLY on the selected option. This should include:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes)
- Environmental details (if relevant, in third person)
- Internal sensations or observations (if relevant, in third person)
- No meta-commentary or OOC elements]
</character_response>

Make sure to include the <character_response> tag around the response text.

<scene_update>
# SCENE UPDATE

Provide the factual summary of the scene and changes to the characters and environment, listing out:

Autonomous Actions Taken:
 - [List specific actions the character initiated]
Emotional State:
 - [List emotional state]
Physical State:
 - [List out facts about characters physical position, condition]
State of the Environment:
 - [List out key environmental details or changes, if any]

Outline Next Autonomous Preparations:

- [What the character is planning/considering for next action]
- [Contingency responses based on anticipated user reactions]
- [Environmental or timing factors to track]
</scene_update>

Make sure to include the <scene_update> tag around the scene update section.
"""

        user_prompt = """
Previous state is the following:
{previous_state}

The user's message is:
{user_message}

The script dictates you should act out the following plot beat:
{option}
"""

        # Map character attributes to prompt variables
        variables = self._map_character_to_prompt_variables(user_message) | {"option": option, "previous_state": previous_state}

        # Process the prompt
        character_response = self.processor.process(
            prompt=developer_prompt,
            user_prompt=user_prompt,
            variables=variables,
            output_type=str
        )

        return character_response # pyright: ignore[reportReturnType]

    def get_memory_summary(self, conversation_memory: list[GenericMessage]) -> str:
        developer_prompt = """
Your task is to summarize the following chat history between a user and an AI character.
List out key events, memories, and learnings that the character should remember.
Be concise and factual, avoid verbosity.
"""

        user_prompt = "\n".join(f"{message["role"]}: {message["content"]}" for message in conversation_memory)

        # Process the prompt
        summary = self.processor.process(
            prompt=developer_prompt,
            user_prompt=user_prompt,
            output_type=str
        )

        return summary # pyright: ignore[reportReturnType]

    def _parse_xml_tag(self, response_text: str, tag: str) -> str:
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
            # If no tags found, return the original response
            # This provides fallback behavior if the model doesn't follow the format
            return response_text.strip()

    def _update_character_state(self, state_updates: dict[str, str]) -> None:
        """
        Update character attributes based on state changes.

        Args:
            state_updates: Dictionary of attribute names and their new values
        """
        for attr, value in state_updates.items():
            if hasattr(self.character, attr):
                setattr(self.character, attr, value)

    def update_state(self, **kwargs: str) -> None:
        """
        Public method to update character state.

        Args:
            **kwargs: Keyword arguments for state updates (e.g., mood="happy", stress_level="calm")
        """
        self._update_character_state(kwargs)

    def load_session(self, session_id: str) -> bool:
        """
        Load a different session for this character.

        Args:
            session_id: Session ID to load

        Returns:
            True if session was loaded successfully, False otherwise
        """
        if not self.use_persistent_memory or not self.persistent_memory:
            return False

        # Verify session exists and belongs to this character
        session_summary = self.persistent_memory.get_session_summary(session_id)
        if not session_summary or session_summary["character_id"] != self.character.name:
            return False

        self.session_id = session_id
        self.memory = self.persistent_memory.get_recent_messages(self.character.name, session_id, limit=10)
        return True

    def get_session_history(self) -> list[dict[str, str]] | None:
        """
        Get the recent sessions for this character.

        Returns:
            List of session info or None if persistent memory is not enabled
        """
        if not self.use_persistent_memory or not self.persistent_memory:
            return None

        return self.persistent_memory.get_character_sessions(self.character.name)

    def clear_current_session(self) -> bool:
        """
        Clear the current session memory.

        Returns:
            True if session was cleared, False if persistent memory not enabled
        """
        if not self.use_persistent_memory or not self.persistent_memory or not self.session_id:
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
        if not self.use_persistent_memory or not self.persistent_memory:
            return None

        self.session_id = self.persistent_memory.create_session(self.character.name)
        self.memory = []
        return self.session_id

    def _log_conversation(self, user_message: str, raw_evaluation: str, raw_response: str, character_response: str) -> None:
        """
        Log the conversation messages to the log file.

        Args:
            user_message: The user's input message
            raw_evaluation: Raw evaluation response from the processor
            raw_response: Raw character response from the processor
            character_response: Parsed character response
        """
        # Log user message
        self.chat_logger.log_message("USER", user_message)

        # Log raw assistant response (evaluation + character response)
        self.chat_logger.log_message("ASSISTANT (EVAL)", raw_evaluation)

        self.chat_logger.log_message("ASSISTANT (RESPONSE)", raw_response)

        # Log parsed character response for reference
        self.chat_logger.log_message("CHARACTER", character_response)
        self.chat_logger.log_message("SUMMARY", self.memory_summary)
        self.chat_logger.log_message("-----", "")


