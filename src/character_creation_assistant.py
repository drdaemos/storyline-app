import json
import re
from collections.abc import Callable
from typing import Any

from .models.prompt_processor import PromptProcessor


class CharacterCreationAssistant:
    """
    Interactive AI assistant for creating characters through conversation.

    This assistant helps users create characters by conversing with them and
    gradually extracting or generating character details based on the conversation.
    """

    def __init__(self, prompt_processor: PromptProcessor) -> None:
        """
        Initialize the CharacterCreationAssistant.

        Args:
            prompt_processor: The prompt processor to use for AI interactions
        """
        self.prompt_processor = prompt_processor

    def process_message(
        self,
        user_message: str,
        current_character: dict[str, Any],
        conversation_history: list[dict[str, str]],
        streaming_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Process a user message and return AI response + character updates.

        Args:
            user_message: The user's message describing or modifying the character
            current_character: Current partial character data
            conversation_history: List of previous messages (dicts with 'author', 'content', 'is_user')
            streaming_callback: Optional callback for streaming AI response chunks

        Returns:
            Tuple of (AI response text, character updates dict)
        """
        # Build the prompt with conversation history and current character state
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(user_message, current_character, conversation_history)

        # Get AI response with streaming support
        if streaming_callback:
            # Use streaming version
            ai_response_parts = []
            for chunk in self.prompt_processor.respond_with_stream(
                prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
            ):
                ai_response_parts.append(chunk)
                streaming_callback(chunk)
            ai_response = "".join(ai_response_parts)
        else:
            # Use non-streaming version
            ai_response = self.prompt_processor.respond_with_text(
                prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2000,
            )

        # Extract character updates from the AI response
        character_updates = self._extract_character_updates(ai_response, current_character)

        return ai_response, character_updates

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the character creation assistant."""
        return """You are a helpful AI assistant for creating role-playing characters. Your role is to help users build detailed, interesting characters through conversation.

Your responsibilities:
- Understand what the user wants to create or modify about their character
- Extract character details from natural conversation
- Ask clarifying questions when details are vague or missing
- Suggest ideas while respecting user's creative vision
- Be conversational and friendly

Character fields you can help with:
- name: Character's name
- tagline: A short, striking tagline or motto
- backstory: Character's history and background
- personality: Personality traits and characteristics
- appearance: Physical description
- relationships: Dictionary of relationships {name: description}
- key_locations: List of important locations
- setting_description: Description of the world/setting

When you want to update character fields, use this format in your response:
<character_update>
{
  "field_name": "value",
  "relationships": {"character_name": "relationship description"},
  "key_locations": ["location1", "location2"]
}
</character_update>

Guidelines:
- Only include fields in <character_update> that should be created or modified
- If the user asks for a complete character, include all relevant fields
- If the user asks to change one specific thing, only include that field
- If the conversation is just clarifying or chatting, don't include <character_update> at all
- Keep your conversational responses friendly and helpful
- The <character_update> section should contain valid JSON"""

    def _build_user_prompt(
        self,
        user_message: str,
        current_character: dict[str, Any],
        conversation_history: list[dict[str, str]],
    ) -> str:
        """Build the user prompt with conversation history and current state."""
        prompt_parts = []

        # Add current character state if any
        if current_character:
            prompt_parts.append("Current character state:")
            prompt_parts.append("```json")
            prompt_parts.append(json.dumps(current_character, indent=2))
            prompt_parts.append("```")
            prompt_parts.append("")

        # Add conversation history if any
        if conversation_history:
            prompt_parts.append("Previous conversation:")
            for msg in conversation_history:
                author = "User" if msg.get("is_user") else "Assistant"
                prompt_parts.append(f"{author}: {msg['content']}")
            prompt_parts.append("")

        # Add current user message
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("")
        prompt_parts.append("Please respond to the user and include <character_update> tags if you're modifying character fields.")

        return "\n".join(prompt_parts)

    def _extract_character_updates(self, ai_response: str, current_character: dict[str, Any]) -> dict[str, Any]:
        """
        Extract character updates from AI response.

        Looks for <character_update> tags in the response and parses the JSON inside.

        Args:
            ai_response: The AI's response text
            current_character: Current character state for context

        Returns:
            Dictionary of character field updates (empty if no updates found)
        """
        # Look for <character_update> tags
        update_pattern = r"<character_update>\s*(\{[\s\S]*?\})\s*</character_update>"
        match = re.search(update_pattern, ai_response)

        if not match:
            return {}

        try:
            # Parse the JSON inside the tags
            update_json = match.group(1)
            updates = json.loads(update_json)

            # Validate that updates only contain valid character fields
            valid_fields = {
                "name",
                "tagline",
                "backstory",
                "personality",
                "appearance",
                "relationships",
                "key_locations",
                "setting_description",
            }

            filtered_updates = {
                key: value for key, value in updates.items() if key in valid_fields and value
            }

            return filtered_updates

        except (json.JSONDecodeError, AttributeError) as e:
            # If parsing fails, log and return empty updates
            print(f"Failed to parse character updates from AI response: {e}")
            return {}

    def clean_response_text(self, ai_response: str) -> str:
        """
        Remove <character_update> tags from the response to get clean chat message.

        Args:
            ai_response: The full AI response with potential tags

        Returns:
            Clean response text without <character_update> tags
        """
        # Remove <character_update> tags and their contents
        clean_text = re.sub(r"<character_update>[\s\S]*?</character_update>", "", ai_response)

        # Clean up extra whitespace
        clean_text = re.sub(r"\n\n\n+", "\n\n", clean_text)
        clean_text = clean_text.strip()

        return clean_text
