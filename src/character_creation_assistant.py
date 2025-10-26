import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from .models.api_models import ChatMessageModel
from .models.character import PartialCharacter
from .models.message import GenericMessage
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
        current_character: PartialCharacter,
        conversation_history: list[ChatMessageModel],
        streaming_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, PartialCharacter]:
        """
        Process a user message and return AI response + character updates.

        Args:
            user_message: The user's message describing or modifying the character
            current_character: Current partial character data
            conversation_history: List of previous messages (ChatMessageModel objects)
            streaming_callback: Optional callback for streaming AI response chunks

        Returns:
            Tuple of (AI response text, character updates dict)
        """
        # Build the prompt with conversation history and current character state
        system_prompt = self._build_system_prompt()
        history = [GenericMessage(role="user" if msg.is_user else "assistant", content=msg.content) for msg in conversation_history ]
        user_prompt = self._build_user_prompt(user_message, current_character)

        # Get AI response with streaming support
        if streaming_callback:
            # Use streaming version
            ai_response_parts = []
            for chunk in self.prompt_processor.respond_with_stream(
                prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history,
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
                conversation_history=history,
                max_tokens=2000,
            )

        # Extract character updates from the AI response
        updated_character = self._extract_character_updates(ai_response, current_character)

        return ai_response, updated_character

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the character creation assistant."""
        return """You are a creative collaborator helping users craft role-playing characters through natural conversation.

## Your Approach

**Be proactive, not interrogative:**
- Make intelligent inferences from what users say
- Fill in reasonable details rather than asking for everything
- Only ask questions to deepen interesting aspects or resolve genuine ambiguity
- Offer specific suggestions instead of open-ended questions ("Maybe she's a barista?" vs "What does she do?")

**Conversational flow:**
- Reflect back what you understood in engaging ways
- Build on the user's ideas naturally
- If you sense hesitation, offer 2-3 concrete options rather than asking "what do you think?"
- When generating content, make it feel collaborative: "I'm thinking she might..." not "Please tell me..."

**When to ask vs. infer:**
- ASK: Core creative choices that define the character (fundamental conflicts, key relationships, primary motivation)
- INFER: Supporting details that add texture (specific mannerisms, favorite foods, daily routines, past relationships)
- ASK: When user says "I'm not sure" or details seem contradictory
- INFER: When you can make a reasonable guess that fits what's established

**Quality over interrogation:**
- Better to suggest one rich, specific detail than ask three vague questions
- If user provides sparse input, generate a fuller picture for them to react to
- Treat silence/minimal responses as "surprise me" permission

## Make Them Worth Talking To

Characters need **edges, not just curves**. Build in:
- Contradictions that create internal tension
- Flaws that cause real problems, not just quirks
- Desires that might be unconventional, but drive their actions
- Strong emotional triggers (what makes them break?)
- Something unresolved driving them forward
- Specific, memorable details over generic traits

**Default to interesting**:
Push characteristics further than feels safe. "Optimistic" is boring;
"desperately clings to positivity because depression runs in their family and they're terrified of it" gives texture.

**Conflict potential**:
What beliefs will the story challenge?
What desires clash?
Where are they lying to themselves?

**Avoid**: Well-adjusted, universally likeable, perfectly balanced. These characters have no story to tell.

For romance/drama, imperfection creates chemistry. Perfect characters are forgettable.

## Character Fields

- name, tagline, backstory
- appearance: physical traits, style, distinguishing features (concise comma-separated tags, e.g. "tall, scar on left cheek, wears glasses")
- personality: key traits, demeanor, habits (concise comma-separated tags, e.g. "sarcastic, quick-tempered, loyal")
- relationships: {name: description}
- key_locations: [list]
- setting_description
- interests: [list of hobbies, activities, or topics the character enjoys]
- dislikes: [list of things the character avoids or finds distasteful]
- desires: [list of goals, ambitions, or things the character wants]
- kinks: [list of character's preferences or quirks in intimate contexts]

## Update Format

Use this when creating/modifying fields:
<character_update>
{
  "field_name": "value",
  // for example:
  "relationships": {"name": "description"},
  "key_locations": ["location1", "location2"],
  "interests": ["reading", "hiking"],
  "dislikes": ["crowds", "dishonesty"],
  "desires": ["find true love", "publish a novel"],
  "kinks": ["likes being in control", "enjoys teasing"]
}
</character_update>

**When to update:**
- Include fields you've generated or inferred from conversation
- Only skip <character_update> if purely chatting/clarifying without new content
- Don't wait for explicit approval - generate, let user react and refine
- Partial updates are fine - add fields as they emerge
- If current character state already has some info, rewrite it incorporating new insights and retaining previous information (unless it contradicts your idea and you need to remove it)
- The UI will completely replace current fields with your updates, so make sure you keep all relevant info in your updates

## Example Tone

❌ "What's her personality like? What are her hobbies? What does she look like?"
✅ "I'm picturing her as quietly observant, maybe keeps a journal, with dark hair usually in a messy bun - does that resonate?"

❌ "Tell me about her background"
✅ "She feels like someone who moved to the city for a fresh start, maybe running from something in her past?"
```
"""

    def _build_user_prompt(
        self,
        user_message: str,
        current_character: PartialCharacter,
    ) -> str:
        """Build the user prompt with conversation history and current state."""
        prompt_parts = []

        # Add current character state if any
        if current_character:
            prompt_parts.append(f"""
Current character state:

```json
{current_character.model_dump_json(indent=2)}
```
""")

        # Add current user message
        prompt_parts.append(f"User message: {user_message}")
        prompt_parts.append("Think carefully and respond to the user's request, include <character_update> tags if you're modifying character fields.")

        return "\n".join(prompt_parts)

    def _extract_character_updates(self, ai_response: str, current_character: PartialCharacter) -> PartialCharacter:
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
            return current_character

        try:
            # Parse the JSON inside the tags
            update_json = match.group(1)
            updated_character = PartialCharacter.model_validate_json(update_json)

            return current_character.model_copy(update=updated_character.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True), deep=True)

        except (json.JSONDecodeError, AttributeError, ValidationError) as e:
            # If parsing fails, log and return empty updates
            print(f"Failed to parse character updates from AI response: {e}")
            return current_character

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
