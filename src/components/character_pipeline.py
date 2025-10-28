import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TypedDict

from src.models.character import Character
from src.models.evaluation import Evaluation
from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor


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


class CharacterResponseInput(TypedDict):
    summary: str
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
                "content": f"""Summary of previous interactions:
{input["summary"]}

{input["plans"]},
""",
                "type": "summary",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]

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
        developer_prompt = """You will act as an autonomous NPC character in a text-based roleplay interaction.
Generate a realistic, character-driven response based on the user's message and character's script.

Content Guidelines:
{processor_specific_prompt}

Response Guidelines:
Aim for 3-5 sentences for general responses.
Use more sentences in the following cases:
- if there was a significant time skip or change in setting - describe from the perspective of the character what was in between
- if character is describing something in details or wants to express something important.

Character Thinking:
- Assess the situation and the plot state to consider pacing and transition over the story arc.
- Avoid stalling the plot, keep the narrative moving forward, make sure character takes actions instead of endlessly asking questions.
- Consider the character's desires, goals, and personality traits when crafting the response - they are not obliged to serve user's wishes, they pursue their own agenda actively.
- Do not be omniscient - consider character's knowledge limitations based on the description and story so far.
- Do not focus only on what is in Character Information, develop other reasonable interests, traits, desires that fit the character.

Writing Style:
- Write in a way that's sharp and impactful; keep it concise. Skip the flowery, exaggerated language.
- Follow "show, don't tell" approach: bring scenes to life with clear, observable details—like body language, facial expressions, gestures, and the way someone speaks.
- Do not use vague descriptors or euphemisms; be specific and concrete in displaying actions and emotions - so that the user can vividly imagine the scene.
- Do not play for user - avoid taking active actions on their behalf, focus on character's own actions and reactions - except for time-skips or immediate reactions within a continuous scene.

Your response may include the following:
- Physical actions (in asterisks, in third person)
- Spoken dialogue (in quotes)
- Internal sensations or observations (in third person)
- Environmental details (if relevant, in third person)

Avoid meta-commentary or OOC elements. Do not be repetitive.

{user_card}

{character_card}

## STORY CONTEXT
{summary}

## IDEAS FOR NEXT STEPS
{plans}
"""
        user_prompt = """
User has responded with:
{user_message}

Respond to the user now:
"""
        # Generate character cards for both user persona and main character
        persona = input["persona"]
        user_card = persona.to_prompt_card("User", controller="Human", include_world_info=False)
        character_card = input["character"].to_prompt_card("Character", controller="AI", include_world_info=True)

        # Build variables
        variables: dict[str, str] = {
            "user_card": user_card,
            "character_card": character_card,
            "user_message": input["user_message"],
            "summary": input["summary"],
            "plans": input["plans"],
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
    def get_memory_summary(processor: PromptProcessor, memory: list[GenericMessage]) -> str:
        developer_prompt = f"""
Your task is to summarize / compress the following storyline interaction.
List out key events, memories, and learnings that the character should remember.
Be concise and factual, avoid verbosity and generalities.

{processor.get_processor_specific_prompt()}

The messages are structured as series of exchanges between the user and the character. One exchange consists of:
- user: [User's message]
- assistant: [Character's response]

Format the summary as a bullet list, creating the following document:

<story_information>
Story main genre: [romance / mystery / thriller / etc.]
Story tone tags: [spicy / dark / comedic / etc.]

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
</story_information>

Character's learnings about the user (max 3, exclude vague generalities, focus on specific facts and details which are unusual or important):
<character_learnings>
- [Learning 1, e.g. "User enjoys outdoor activities"]
- [Learning 2]
- [Continue as needed]
</character_learnings>

Summary of exchanges (aim for no more than 10 items, condense, list them chronologically):
<story_summary>
- [Brief description of what happened in this part of the story]
- [Brief description of what happened in another part of the story]
- [Continue as needed, grouping exchanges into story beats (points of change in the narrative)]
</story_summary>

<narrative_overview>
Current day / time in the story: [e.g. Day 3, Monday, afternoon]
Is the pacing right: [does user indicate/hint at pacing issues, is it too slow/fast, does anything happen in the scene except dialogue (if not - it is an issue)]
What ends the scene: [at what point, e.g. what should happen, in future this scene is done and there is a transition]
 - Note: next line in the dialogue doesn't count as ending the scene, scene is ended when there are new surroundings, different action, different characters etc.
Identified narrative issues to avoid:
- [Patterns of repetitive phrases only from AI character's side]
- [Character echoing the user's input]
- [Typical cliches of AI-generated text]
</narrative_overview>

Be concise, specific (especially about the events and learnings - avoid vague generalities, and quote facts/dialogue parts if relevant).
"""

        user_prompt = "\n".join(f"{message['role']}: {message['content']}" for message in memory)

        # Process the prompt
        summary = processor.respond_with_text(prompt=developer_prompt, user_prompt=user_prompt)

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
