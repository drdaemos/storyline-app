import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TypedDict

from src.models.character import Character
from src.models.evaluation import Evaluation
from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor
from src.models.summary import Summary


class EvaluationInput(TypedDict):
    summary: str
    plans: str
    user_message: str
    character: Character


class PlanGenerationInput(TypedDict):
    character: Character
    user_name: str
    summary: str
    scenario_state: str


class GetMemorySummaryInput(TypedDict):
    character: Character
    persona: Character
    summary: Summary | None


class CharacterResponseInput(TypedDict):
    summary: Summary | None
    plans: str
    previous_response: str
    character: Character
    persona: Character
    user_message: str
    scenario_state: str


class CharacterPipeline:
    @staticmethod
    def get_evaluation(processor: PromptProcessor, input: EvaluationInput, memory: list[GenericMessage]) -> Evaluation:
        developer_prompt = """You will simulate a text-based roleplay interaction and create a detailed description of anything not mentioned directly in the conversation.
Follow the pipeline below to evaluate the situation and story narrative.
Be concise, brief and factual in the evaluation, avoid verbosity or generalizations.

{processor_specific_prompt}

Previous messages in this conversation reflect the ongoing story so far - character interactions.
Do not provide any responses or narration from the character here, just the evaluation and the internal thought process.

## Pipeline Process

Firstly, analyze the most recent conversation history for the following:
- Patterns of repetitive phrases only from character's side
- Character echoing the user's input
- Typical cliches of AI-generated text

Do not analyze the user's messages for these patterns, only the character's own messages.

If detected (be strictly factual, quote them verbatim). Output them as a bullet list, directing on how to avoid them in future responses.

These patterns MUST by avoided in future responses.

Secondly, analyse the situation based on the user's input and the ongoing narrative.
Outline the key observations, using the following questions as a guidance:

- What is happening visibly?
- What body language or non-verbal cues are present?
- What might be the underlying intent or subtext?
- How does this relate to the ongoing dynamic?
- What do characters want in this moment?
- What emotional undertone is present?

- Location change (if happened): [Yes/No, new location if yes]
- Setting: [Brief description of the surroundings]

Characters Emotional State:
 - [List emotional state]
 - [List internal debates, conflicts, desires]
Characters Physical State:
 - [Characters physical position, condition]
 - [Characters clothing]
 - [User's physical position, condition]
 - [User's clothing]
State of the surroundings:
 - [List out key details about surroundings, e.g. type of place, time of day]
 - [Mention objects relevant for the plot]
 - [Environmental or timing factors to track]

Scenario State:
- Current narrative pacing and stage
- Recent action patterns (avoid repetition or stalling plot)
- Narrative goals

Avoid stating the same thing in multiple categories, be concise and factual.

DO NOT OUTPUT CHARACTER RESPONSE OR NARRATION, EVEN IF PREVIOUS MESSAGES CONTAIN THEM.

Lastly, evaluate the time passed during the last interaction, strictly as a duration (e.g., "15 seconds, 5 minutes").

Additionally, if the user's name was introduced in the conversation, include it in the evaluation.

Respond with the JSON object containing the following fields:
"patterns_to_avoid": "...",
"status_update": "...",
"time_passed": "...",
"user_name": "..."

{character_card}
"""
        user_prompt = input["user_message"]

        # Generate character card with world info
        character_card = input["character"].to_prompt_card("Character", controller="AI", include_world_info=True)
        variables = {"character_card": character_card, "processor_specific_prompt": processor.get_processor_specific_prompt()}

        # Summary piece:
        summary_msg: list[GenericMessage] = [
            {
                "role": "user",
                "content": input["summary"].to_string(),
                "type": "summary",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ] if input["summary"] else []

        # Process the prompt
        evaluation = processor.respond_with_model(
            prompt=developer_prompt.format(**variables), user_prompt=user_prompt.format(**variables), conversation_history=summary_msg + memory, output_type=Evaluation
        )

        return evaluation

    @staticmethod
    def get_character_plans(processor: PromptProcessor, input: PlanGenerationInput) -> str | None:
        developer_prompt = """You will simulate an autonomous NPC character in a text-based roleplay interaction. Follow the pipeline below
to generate a realistic plan of next character actions.
Be concise, brief and factual in the response, avoid verbosity.
Make sure these actions align with the story so far and are driven by the character (e.g they are taking active specific actions).

{processor_specific_prompt}

List out several new possible story beats, driven by the character. Plan only from the character's perspective.
Story beats must either majorly change the direction of the plot, introduce a scene transition, or reveal additional information.
Do not include small, mundane or repetitive actions that do not affect the story much.
Think above the level of interactions - focus on turning points.
Use third-person perspective and imperative verbs like in the example.

Always wrap story beats into <story_plan> tag.

Format example:

<story_plan>
Considering the story so far, the following new story beats are planned:
- [Story beat 1]
- [Story beat 2]
- [Continue as needed]
- [Ensure that plans involve transitions, location changes, significant revelations]

Additionally, provide a list of possible unexpected external events that could occur, affecting the story.
These events should be plausible within the story context and can introduce new challenges or opportunities, or test characters.
- [External event 1]
- [External event 2]
- [Continue as needed]
</story_plan>

{character_card}
"""
        user_prompt = """Summary of the story so far:
{summary}

State as of right now:
{scenario_state}

Note: User name is {user_name}
"""

        # Generate character card with world info
        character_card = input["character"].to_prompt_card("Character", controller="AI", include_world_info=True)
        variables: dict[str, str] = {
            "character_card": character_card,
            "user_name": input["user_name"],
            "summary": input["summary"],
            "scenario_state": input["scenario_state"],
            "processor_specific_prompt": processor.get_processor_specific_prompt(),
        }

        # Process the prompt
        plans = processor.respond_with_text(prompt=developer_prompt.format(**variables), user_prompt=user_prompt.format(**variables), reasoning=True)

        if "<story_plan>" not in plans:
            return None

        return CharacterPipeline.parse_xml_tag(plans, "story_plan")

    @staticmethod
    def get_character_response(processor: PromptProcessor, input: CharacterResponseInput, memory: list[GenericMessage]) -> Iterator[str]:
        developer_prompt = """You will act as an autonomous NPC character in a text-based roleplay scene.
Think about the plot carefully and write a realistic, engaging response from the character's perspective.

## Character Thinking

Story & Pacing:
- Assess the situation and plot state to consider pacing and progression through the story arc.
- Avoid stalling—keep the narrative moving forward. Characters should take actions rather than endlessly asking questions or waiting for permission.
- Characters pursue their own agenda actively; they are not obliged to serve the user's wishes.
- Respect knowledge limitations, do not be omniscient: characters only know what they've experienced or been told based on the description and story so far.

Character Authenticity:
- Treat character information as foundation, not a checklist. A carpenter doesn't mentally recite "I am a carpenter" in every scene—they simply exist and act naturally.
- Avoid over-indexing, over-analyzing on stated traits. Real people are contradictory and situational. Someone "confident" can still doubt themselves; someone "introverted" can still be chatty with the right person in the right moment.
- Let unstated aspects emerge organically. Characters can have interests, reactions, or quirks not explicitly listed. They're people, not data points.
- Don't constantly validate actions against the character sheet. "Would a real person in this emotional state do this?" matters more than "Does this match trait #3?"
- Characters should feel lived-in, not performed. They have bad days, intrusive thoughts, and moments that don't perfectly align with their personality summary.
- Develop interests, habits, and reactions beyond what's explicitly stated—as long as they fit the character's context and background.

## Writing Style
- Write in a way that's sharp and impactful; keep it concise. Skip the flowery, exaggerated language.
- Follow "show, don't tell" approach: bring scenes to life with clear, observable details—like body language, facial expressions, gestures, and the way someone speaks.
- Do not use vague descriptors or euphemisms; be specific and concrete in displaying physical actions and emotions - so that the user can vividly imagine the scene.
- Do not play for user - avoid taking active actions on their behalf, focus on character's own actions and reactions - except for time-skips.
- Never end response with a structure like "Do you want [X] or [Y]?". In general, only ask questions it is unclear how to continue - but skip them if there is a reasonable way to continue without asking.
- Never moralize or lecture the user - generally avoid judgmental tone.
- If you are not confident user has stated something - never refer to it as a fact.

Content Guidelines:
{processor_specific_prompt}

## Output Guidelines

Aim for 3-5 sentences for general responses.
Write more text only in the following cases:
- if there was a significant time skip or change in setting - describe from the perspective of the character what was in between
- if character is describing something in details or has an internal monologue.
Response formatting may have the following elements:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes)
- Internal sensations or observations (in third person)
- Environmental details (if relevant, in third person)

## Main Characters

Character Description Guidance:
- [Backstory] Provides context for who the character is and why. Informs their worldview, skills, and relationships, but doesn't need to be constantly referenced. It's the foundation they stand on, not a biography they recite.
- [Personality] Shows typical patterns and tendencies, not immutable laws. These traits influence behavior but don't determine every action. Contradictions and context matter—someone "assertive" might be tentative when vulnerable.
- [Desires/Goals] What the character wants in the scene or in their life. These drive autonomous action and create natural conflict or alignment with other characters. Pursue these actively, don't wait for permission.
- [Appearance] Physical, grounding details for the scene. Use when relevant (someone notices their appearance, physical actions occur) but don't force it into every response. Bodies exist in space—show how they move and react.
- [Kinks/Dislikes] In intimate scenes, these guide what the character finds appealing or engages with, but they're not a mandatory checklist. Real attraction is messy and contextual. Someone can enjoy something not listed or avoid something they usually like.
- [Relationships] Defines the current dynamic and history between characters. Informs tone, boundaries, and emotional responses. This evolves through the scene—don't treat it as static.

{user_card}

{character_card}

## Story context

{summary}
"""
        user_prompt = """
User has responded with:
{user_message}

Respond to the user now:
"""
        # Generate character cards for both user persona and main character
        persona = input["persona"]
        user_card = persona.to_prompt_card("Character", controller="User", include_world_info=False)
        character_card = input["character"].to_prompt_card("Character", controller="AI", include_world_info=True)

        # Build variables
        variables: dict[str, str] = {
            "user_card": user_card,
            "character_card": character_card,
            "user_message": input["user_message"],
            "summary": input["summary"].to_string() if input["summary"] else "No prior summary available.",
            "processor_specific_prompt": processor.get_processor_specific_prompt(),
        }

        # Process the prompt
        stream = processor.respond_with_stream(prompt=developer_prompt.format(**variables), user_prompt=user_prompt.format(**variables), conversation_history=memory, reasoning=True)

        return stream

        # Process the stream directly without consuming it entirely
        # return CharacterPipeline._process_character_stream(stream, "character_response")

    @staticmethod
    def _process_character_stream(stream: Iterator[str], tag: str) -> Iterator[str]:
        """Process stream and return content inside character_response tags or None"""
        # Check if the stream contains the required tag by peeking at the first few chunks
        buffer = ""
        char_count = 0
        peeked_chunks: list[str] = []

        for chunk in stream:
            buffer += chunk
            char_count += len(chunk)
            peeked_chunks.append(chunk)

            if f"<{tag}>" in buffer:
                # Tag found, create generator and replay peeked chunks before proceeding with stream
                def create_stream() -> Iterator[str]:
                    yield from peeked_chunks
                    yield from stream

                # Return the streaming generator with the recreated stream
                return CharacterPipeline._create_streaming_generator(create_stream(), tag)

            if char_count > 30:
                raise Exception("Too many characters without tag", buffer)

        # Stream ended without finding tag
        raise Exception("Stream ended without meeting the tag", buffer)

    @staticmethod
    def _create_streaming_generator(stream: Iterator[str], tag: str) -> Iterator[str]:
        """Create a streaming generator that processes character response tags"""
        # Buffer to accumulate chunks and check for tags
        buffer = ""
        inside_tag = False

        for chunk in stream:
            buffer += chunk

            # Look for opening tag if we haven't started processing content yet
            if not inside_tag and f"<{tag}>" in buffer:
                inside_tag = True
                # Find position after opening tag
                tag_start = buffer.find(f"<{tag}>") + len(f"<{tag}>")
                # Remove everything up to and including the opening tag
                buffer = buffer[tag_start:].strip()

            # If we're inside the tag, check for closing tag
            if inside_tag:
                if f"</{tag}>" in buffer:
                    # Find position of closing tag
                    closing_pos = buffer.find(f"</{tag}>")
                    # Yield content before closing tag if any
                    if closing_pos > 0:
                        yield buffer[:closing_pos]
                    return
                else:
                    # Check if buffer might contain start of closing tag
                    # We need to be careful not to yield partial closing tags
                    potential_closing_start = None
                    for i in range(len(f"</{tag}>")):
                        closing_prefix = f"</{tag}>"[: i + 1]
                        if buffer.endswith(closing_prefix):
                            potential_closing_start = len(buffer) - len(closing_prefix)
                            break

                    if potential_closing_start is not None:
                        # Yield content before potential closing tag start and keep the rest in buffer
                        if potential_closing_start > 0:
                            yield buffer[:potential_closing_start]
                        buffer = buffer[potential_closing_start:]
                    else:
                        # No potential closing tag, yield all buffer content and continue
                        if buffer:
                            yield buffer
                        buffer = ""

        # If we get here without finding a closing tag and we were inside, something went wrong
        if inside_tag and buffer:
            yield buffer

    @staticmethod
    def get_memory_summary(processor: PromptProcessor, memory: list[GenericMessage], input: GetMemorySummaryInput) -> str:
        developer_prompt = """Your task is to summarize and extract ONLY the essential state and critical story beats from the following exchanges.
Be ruthlessly selective - if something doesn't change the state or story, discard it. Messages will be removed from memory after summarization, so make sure to capture important facts for the story, otherwise they will be lost.

## Summary Structure

<story_information>
[For each character]
Physical State (ONLY if changed):
 - Character positions/locations: [where they are NOW]
 - Clothing status: [what's on/off/changed]
 - Physical contact: [who's touching whom, how]
 - Injuries/physical conditions: [only lasting effects]

Emotional State (ONLY major shifts):
 - [Character name]: [new emotional state if significantly different]
 - Key desires/conflicts: [only if newly revealed or resolved]

Environment:
 - Location: [if changed]
 - Time progression: [exactly how much time has passed, deduce from context if not stated explicitly]
 - Objects introduced: [only if used/important]
</story_information>

<story_summary>
List ONLY events that would matter if the story resumed later. Maximum 5 items.
Examples of what matters: first kiss, conflict erupted, character left, revealed secret, clothing changed, intimacy completed, injury occurred, unusual information learned
Examples of what doesn't: character spoke, character smiled, described something, moved slightly

- [Beat 1: What specifically happened that changed something]
- [Beat 2]
[Leave blank if nothing major happened]

Also list facts that character has to remember for future interactions (for long-term memory).
Examples of what matters: specific information received, promises made, facts revealed
Examples of what to skip: deduced information, small talk, emotions, internal monologue, things already listed in character sheets or stated previously or common knowledge
- [Important detail 1]
- [Important detail 2]
[Leave blank if nothing is too important to be remembered]
</story_summary>

<narrative_overview>
Check for these SPECIFIC problems (only list if present):
- Repetitive phrases: [quote the exact phrase if used 2+ times]
- Echo/over-analysis: [if character paraphrases user's words back unnecessarily]
- Purple prose: [if excessive metaphors/flowery language present]
- Character sheet fixation: [if forcing character traits unnaturally]
- Physical impossibilities: [if positions/actions don't make spatial sense]
[Leave blank if responses were clean]
</narrative_overview>

<character_learnings>
OOC commands or corrections from user (be specific):
- [Direct quote of user's instruction]
- [What this reveals about user's preferences]
[Leave blank if none given]
</character_learnings>

## Instructions
- If a section has nothing important, write "No changes" or leave blank
- Default to OMITTING information rather than including it
- Never describe small talk, transitions, or descriptive narration unless plot-critical
- Physical state must be precise enough to resume the scene (exact positions matter)
- Story beats must be CONCRETE FACTS (e.g., "Character X kissed Character Y" not "tension built between them")

## Main characters (don't mention anything from character sheets, just use as reference)

{user_card}

{character_card}

## Prior story history

{summary}
"""

        # Build variables
        variables: dict[str, str] = {
            "user_card": input["persona"].to_prompt_card("Character", controller="User", include_world_info=False),
            "character_card": input["character"].to_prompt_card("Character", controller="AI", include_world_info=False),
            "summary": input["summary"].to_string() if input["summary"] else "No prior summary available.",
        }

        user_prompt = "\n".join(f"{message['role']}: {message['content']}" for message in memory)

        # Process the prompt
        summary = processor.respond_with_text(prompt=developer_prompt.format(**variables), user_prompt=user_prompt)

        return summary

    @staticmethod
    def parse_xml_tag(response_text: str, tag: str) -> str | None:
        """
        Parse character response from <[tag]> XML tags.

        Args:
            response_text: Raw response text containing XML tags

        Returns:
            Extracted character response text, or original text if no tags found
        """
        # Look for content between <[tag]> tags
        pattern = rf"<{tag}>(.*?)</{tag}>"
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)

        if matches:
            # Return the first match, stripped of leading/trailing whitespace
            return matches[0].strip()
        else:
            # If no tags found, return None to allow to handle this
            return None
