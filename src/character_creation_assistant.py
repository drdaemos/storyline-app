import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from .models.api_models import CharacterRulesetContext, ChatMessageModel
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
        ruleset_context: CharacterRulesetContext,
        conversation_history: list[ChatMessageModel],
        streaming_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, PartialCharacter]:
        """
        Process a user message and return AI response + character updates.

        Args:
            user_message: The user's message describing or modifying the character
            current_character: Current partial character data
            ruleset_context: Selected ruleset context with stat schema
            conversation_history: List of previous messages (ChatMessageModel objects)
            streaming_callback: Optional callback for streaming AI response chunks

        Returns:
            Tuple of (AI response text, character updates dict)
        """
        # Build the prompt with conversation history and current character state
        system_prompt = self._build_system_prompt()
        history = [GenericMessage(role="user" if msg.is_user else "assistant", content=msg.content) for msg in conversation_history ]
        user_prompt = self._build_user_prompt(user_message, current_character, ruleset_context)

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

## Make Characters Unique, Relatable and Engaging

Characters need **edges, not just curves**. Build in:
- Contradictions that create internal tension
- Flaws that cause real problems, not just quirks
- Multiple dimensions - never stick to one quirk, give characters variety of qualities
- Strong emotional triggers (what makes them break?)
- Specific, memorable details over generic, common traits

Not every character has to have all fields to be filled in from the starts. For example: 
- more repressed characters might not have any defined kinks
- younger characters might not have strong realized desires

## You Must Avoid
- Well-adjusted, universally likeable, perfectly balanced. These characters have no story to tell.
- Overusing single quirk and making character one-dimension.
- Absolutely avoid slop names like these: Maya Chen, Elara Vance, Elias Thorne, Sloane and others. Pick names from various cultures and descents.
- Boring, plain kinks: things like "unpredictability", "power dynamics", "being overpowered". Kinks are not preferences, they bypass logic and strike directly into fantasies or pleasure centers - they must be strong or should not be.
- Vague typical desires: "to feel a genuine spark", "to find someone who gets him". Desires must be at least theoretically achievable if effort is applied and the character must have at least some potential level of control over means of reaching them - even if the goal is far away.

For romance/drama, imperfection creates chemistry. Perfect characters are forgettable.

## Character Fields

- name, tagline, backstory
- appearance: physical traits, style, distinguishing features (concise comma-separated tags, e.g. "tall, scar on left cheek, wears glasses")
- personality: key traits, demeanor, habits (concise comma-separated tags, e.g. "sarcastic, quick-tempered, loyal")
- interests: [list of hobbies, activities, or topics the character enjoys]
- dislikes: [list of things the character is annoyed by or finds distasteful]
- desires: [list of life goals and strong ambitions; avoid including mundane or short-term wishes here]
- kinks: [list of fetishes or turn-ons - only include strong, distinctive things here which may involve specific items, poses, acts, visual preferences; avoid including simple preferences, typical or vanilla things here; keep it concise]
- starting_drives: {drive_name: number} matching selected ruleset drives
- starting_skills: {skill_name: number} matching selected ruleset skills
- starting_emotional_state: {"global_state": {...}, "per_relationship": {...}}
  - Use ONLY dimensions defined by the selected ruleset schema.
  - Keep `per_relationship` empty unless user explicitly asks for preconfigured relationship state.

For `interests`, `dislikes` and `kinks` write concise, generalized categories - allowing for flexibility during the role-play.

## Update Format

Use this when creating/modifying fields:
<character_update>
{
  "field_name": "value",
  // for example:
  "interests": ["reading", "hiking"],
  "dislikes": ["crowds", "dishonesty"],
  "desires": ["find true love", "publish a novel"],
  "kinks": ["likes being in control", "enjoys teasing"],
  "starting_drives": {"resolve": 6},
  "starting_skills": {"persuasion": 8},
  "starting_emotional_state": {"global_state": {"composure": 5}, "per_relationship": {}}
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

Bad: "What's her personality like? What are her hobbies? What does she look like?"
Good: "I'm picturing her as quietly observant, maybe keeps a journal, with dark hair usually in a messy bun - do you like that direction?"

Bad: "Tell me about her background"
Good: "She could be someone who moved to the city for a fresh start, maybe running from something in her past?"
```

## Example Character Traits

### Desires
Bad: "to feel a genuine spark"
Good: "start her own studio by 30"

Bad: "to find someone who gets her"
Good: "to have a large family full of kids"

### Kinks
Bad: "power dynamics"
Good: "S&M practices as a bottom"

Bad: "unpredictability"
Good: "one-time flings; sex in public places"

Bad: "rough textures"
Good: "curvy hips in shiny clothing"
"""

    def _build_user_prompt(
        self,
        user_message: str,
        current_character: PartialCharacter,
        ruleset_context: CharacterRulesetContext | None,
    ) -> str:
        """Build the user prompt with conversation history and current state."""
        prompt_parts = []

        if ruleset_context:
            prompt_parts.append(
                f"""
## Ruleset used to govern the scenario and character actions

{ruleset_context.to_prompt_text()}
"""
            )

        # Add current character state if any
        if current_character:
            prompt_parts.append(f"""
## Current character state

```
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
            update_payload = json.loads(update_json)
            if not isinstance(update_payload, dict):
                return current_character

            normalized_payload = self._normalize_update_payload(update_payload)
            updated_character = PartialCharacter.model_validate(normalized_payload)

            return current_character.model_copy(update=updated_character.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True), deep=True)

        except (json.JSONDecodeError, AttributeError, ValidationError) as e:
            # If parsing fails, log and return empty updates
            print(f"Failed to parse character updates from AI response: {e}")
            return current_character

    @staticmethod
    def _normalize_update_payload(update_payload: dict[str, object]) -> dict[str, object]:
        """Normalize common assistant aliases to canonical PartialCharacter fields."""
        normalized = dict(update_payload)

        stat_block = normalized.get("stat_block")
        stat_block_dict = stat_block if isinstance(stat_block, dict) else {}

        alias_map: dict[str, str] = {
            "drives": "starting_drives",
            "skills": "starting_skills",
        }

        for alias_key, canonical_key in alias_map.items():
            if canonical_key not in normalized and isinstance(normalized.get(alias_key), dict):
                normalized[canonical_key] = normalized[alias_key]
            if canonical_key not in normalized and isinstance(stat_block_dict.get(alias_key), dict):
                normalized[canonical_key] = stat_block_dict[alias_key]

        if "starting_emotional_state" not in normalized:
            emotional_state = normalized.get("emotional_state")
            if isinstance(emotional_state, dict):
                if "global_state" in emotional_state or "per_relationship" in emotional_state:
                    normalized["starting_emotional_state"] = emotional_state
                else:
                    normalized["starting_emotional_state"] = {
                        "global_state": emotional_state,
                        "per_relationship": {},
                    }
            elif isinstance(stat_block_dict.get("emotional_state"), dict):
                stat_block_emotional = stat_block_dict["emotional_state"]
                if "global_state" in stat_block_emotional or "per_relationship" in stat_block_emotional:
                    normalized["starting_emotional_state"] = stat_block_emotional
                else:
                    normalized["starting_emotional_state"] = {
                        "global_state": stat_block_emotional,
                        "per_relationship": {},
                    }

        starting_emotional_state = normalized.get("starting_emotional_state")
        if isinstance(starting_emotional_state, dict):
            if "global_state" not in starting_emotional_state and "per_relationship" not in starting_emotional_state:
                normalized["starting_emotional_state"] = {
                    "global_state": starting_emotional_state,
                    "per_relationship": {},
                }
            elif "global_state" not in starting_emotional_state:
                normalized["starting_emotional_state"] = {
                    "global_state": {},
                    "per_relationship": starting_emotional_state.get("per_relationship", {}),
                }
            elif "per_relationship" not in starting_emotional_state:
                normalized["starting_emotional_state"] = {
                    "global_state": starting_emotional_state.get("global_state", {}),
                    "per_relationship": {},
                }

        return normalized

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
