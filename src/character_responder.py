import re
from collections.abc import Callable

from src.claude_prompt_processor import ClaudePromptProcessor, Message
from src.models.character import Character


class CharacterResponder:
    """Character responder that uses PromptProcessor to handle character interactions with XML tag parsing."""

    def __init__(self, character: Character) -> None:
        """
        Initialize the CharacterResponder.

        Args:
            character: Character instance to respond as
        """
        self.character = character
        self.processor = ClaudePromptProcessor()
        self.streaming_callback: Callable[[str], None] | None = None
        self.memory: list[Message] = []
        self.memory_summary = ""

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

        if len(self.memory) >= 8:
            self.memory_summary = self.get_memory_summary([{ "role": "user", "content": self.memory_summary}] + self.memory[:3])
            self.memory = [{"role": "user", "content": f"Summary of past interactions: {self.memory_summary}"}] + self.memory[4:]

        raw_evaluation = self.get_evaluation(user_message)

        # Parse and extract selected option from XML tags
        selected_option = self._parse_selected_option(raw_evaluation)

        raw_response = self.get_character_response(user_message, selected_option)

        # Parse and extract character response from XML tags
        character_response = self._parse_character_response(raw_response)

        # Call streaming callback with final response if provided
        if self.streaming_callback:
            self.streaming_callback(character_response)

        # Update memory with the new interaction
        self.memory = self.memory + [
            {"role": 'user', "content": user_message},
            {"role": 'assistant', "content": raw_evaluation + raw_response}
        ]

        return character_response

    def get_evaluation(self, user_message: str) -> str:
        developer_prompt = """
You will simulate an autonomous NPC character in a text-based roleplay interaction. Follow the pipeline below
to generate realistic, character-driven responses that maintain narrative agency and emotional authenticity.
Be concise and factual in the evaluation, avoid verbosity.

## Pipeline Process

Step 1: EVALUATION

Provide analysis of the user's input across multiple dimensions:

- What did the user say/do?
- What body language or non-verbal cues are present?
- What might be the underlying intent or subtext?
- How does this relate to the ongoing dynamic?
- What emotional undertone is present?

Describe the character's internal experience in response to the user's input:

- What does the character see/notice?
- What does the character feel in response?
- What does the character want in this moment?
- What memories or associations does this trigger?

Evaluation Result:

Importance Level: [CRITICAL/HIGH/MEDIUM/LOW]
Response Needed: [Yes/No]
Emotional Shift: [List specific emotions and intensity changes, e.g., "Confidence +2, Attraction +1"]

Step 2: PLAYWRIGHT PROMPT

Generate THREE distinct response options that represent different aspects of the character's personality or
different narrative directions. Each option should be genuinely different, not variations of the same response.
Do not describe the option from the character's internal perspective, but rather as an external narrator describing the character's actions and dialogue - keep it concise.

- Option A: [Action/dialogue description]
  Consequence: [How this shapes the narrative direction]

- Option B: [Action/dialogue description]
  Consequence: [How this shapes the narrative direction]

- Option C: [Action/dialogue description]
  Consequence: [How this shapes the narrative direction]

Internal State: [What the character is thinking/feeling but not expressing. Their internal conflict or decision-making process.]

Step 3: DIRECTOR PROMPT

Assess the situation and the plot state to consider pacing and transition over the story arc.
Do not dwell on one phase for too long, keep the narrative moving forward.
Prefer options that are driven by the character's own agency rather than asking input from the user.

Analyze continuation options based on:

- Current narrative pacing
- Character consistency
- Emotional authenticity
- Recent action patterns (avoid repetition)
- Narrative goals

Choose ONE option in the end: Respond with "Option [A/B/C] - [Brief justification for this selection]"

IMPORTANT: You must select ONLY one option without modification or mixing elements from other options.

Output the selected option again in <selected_option> tags, this time without stating the justification.

## Character Definition

Character Name: {character_name}
Character Background: {character_background}
Character Personality Traits: {character_traits}
Character Current Emotional State: {emotional_state}
Character Goals/Desires: {character_goals}
Setting/Location: {current_setting}
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

        return evaluation

    def get_character_response(self, user_message: str, option: str) -> str:
        developer_prompt = """
You will act as an autonomous NPC character in a text-based roleplay interaction. Follow the pipeline below
to generate realistic, character-driven response that maintains narrative agency and emotional authenticity.
Do not be overly verbose, do not not add extra actions or dialogue outside of the selected option.
Separate spoken dialogue with newlines from the rest of the response.
Try to follow the show-don't-tell principle within the response.
You are allowed to narrative explicit actions, including intimacy - don't do fade to black things.

Step 1: RESPONSE GENERATION

<character_response>
[Generate the full response based ONLY on the selected option. This should include:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes)
- Environmental details (if relevant, in third person)
- Internal sensations or observations (if relevant, in third person)
- No meta-commentary or OOC elements]
</character_response>

Make sure to include the <character_response> tags around the response text.

Step 2: STATE UPDATE

Autonomous Actions Taken: [List specific actions the character initiated without prompting]
Emotional State Updated: [Current emotional state with specific changes noted]
Physical State: [Current physical position, condition, awareness]
Memory Flags: [Key moments to remember for future responses]

Step 3: FEEDBACK LOOP

Outline Next Autonomous Preparations:

- [What the character is planning/considering for next action]
- [Contingency responses based on anticipated user reactions]
- [Environmental or timing factors to track]
"""

        user_prompt = """
The user's message is:
{user_message}

The director has selected this option for you to respond with:
{option}
"""

        # Map character attributes to prompt variables
        variables = self._map_character_to_prompt_variables(user_message) | {"option": option}

        # Process the prompt
        character_response = self.processor.process(
            prompt=developer_prompt,
            user_prompt=user_prompt,
            conversation_history=self.memory,
            variables=variables,
            output_type=str
        )

        return character_response

    def get_memory_summary(self, conversation_memory: list[Message]) -> str:
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

        return summary

    def _parse_character_response(self, response_text: str) -> str:
        """
        Parse character response from <character_response> XML tags.

        Args:
            response_text: Raw response text containing XML tags

        Returns:
            Extracted character response text, or original text if no tags found
        """
        # Look for content between <character_response> tags
        pattern = r'<character_response>(.*?)</character_response>'
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Return the first match, stripped of leading/trailing whitespace
            return matches[0].strip()
        else:
            # If no tags found, return the original response
            # This provides fallback behavior if the model doesn't follow the format
            return response_text.strip()

    def _parse_selected_option(self, response_text: str) -> str:
        """
        Parse character response from <selected_option> XML tags.

        Args:
            response_text: Raw response text containing XML tags

        Returns:
            Extracted character response text, or original text if no tags found
        """
        # Look for content between <character_response> tags
        pattern = r'<selected_option>(.*?)</selected_option>'
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

