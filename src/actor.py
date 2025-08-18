from collections.abc import Callable
from typing import Any

from haystack import Pipeline
from haystack.components.builders import PromptBuilder
from haystack.components.generators import OpenAIGenerator
from haystack.components.generators.utils import StreamingChunk
from haystack_experimental.chat_message_stores.in_memory import InMemoryChatMessageStore
from haystack_experimental.components.retrievers import ChatMessageRetriever
from haystack_experimental.components.writers import ChatMessageWriter

from src.components.action_plan_extractor import ActionPlanExtractor
from src.components.memory_organizer import MemoryOrganizer
from src.models.character import Character


class Actor:
    """Actor class that handles character responses using a two-step Haystack pipeline."""

    def __init__(self, character: Character) -> None:
        self.character = character
        self.pipeline = self._build_pipeline()

        # logging.basicConfig(format="%(levelname)s - %(name)s -  %(message)s", level=logging.WARNING)
        # logging.getLogger("haystack").setLevel(logging.INFO)

    def _build_pipeline(self) -> Pipeline:
        """Build the two-step Haystack pipeline for character response generation."""
        # Step 1: Planning component
        planning_prompt = PromptBuilder(
            template="""
You are a character behavioral analysis system. Your task is to analyze the user's message and determine how the character should respond based on their psychological profile and current state.
Character Profile:
Name: {{name}}
Role: {{role}}
Backstory: {{backstory}}
Appearance: {{appearance}}
Autonomy: {{autonomy}}
Safety: {{safety}}
Openmindedness: {{openmindedness}}
Emotional Stability: {{emotional_stability}}
Attachment Pattern: {{attachment_pattern}}
Conscientiousness: {{conscientiousness}}
Sociability: {{sociability}}
Social Trust: {{social_trust}}
Risk Approach: {{risk_approach}}
Conflict Approach: {{conflict_approach}}
Leadership Style: {{leadership_style}}
Current State:
Stress Level: {{stress_level}}
Energy Level: {{energy_level}}
Mood: {{mood}}

Conversation Memory:
{% for memory in memories %}
{% if memory.role == "user" %}User{% else %}{{name}}{% endif %}: "{{ memory.text }}"
{% else %}
Conversation just started, no previous messages.
{% endfor %}

User Message:
{{user_message}}

Analysis Instructions:
Step 1: Parse User Input

- Identify spoken dialogue (default text)
- Extract physical actions (text in asterisks)
- Note internal thoughts (text in [brackets])

Step 2: Evaluate Previous Action

- Did the character's last action achieve its intended effect?
- How did the user respond to the character's previous behavior?
- What does this tell us about the relationship dynamic?

Step 3: Character Response Logic
Apply this priority order:

- Urgent Needs: If safety is "vulnerable" or stress is "overwhelmed", survival responses override personality
- Personality Consistency: Actions must align with character traits (e.g., "avoidant" conflict approach won't directly confront)
- Emotional State: Current mood and energy level modify typical responses
- Relationship Context: Attachment pattern and social trust influence interpersonal behavior
- Goal Pursuit: What would this character realistically want to achieve in this situation?

Step 4: State Evolution

- How would this interaction affect the character's mood, stress, or energy?
- Consider both immediate emotional impact and longer-term psychological effects
- Only update attributes that would realistically change from this specific interaction

Output Format:
Respond with valid JSON following this exact structure:
{
    "user_action": "Factual description of what user did/said",
    "user_intent": "Character's interpretation of user's goals/motivations",
    "previous_action_outcome": "Success/failure/mixed results of character's last action",
    "character_action": "Specific, observable action character takes (no internal states)",
    "reasoning": "Why this action fits character's psychology and situation",
    "state_update": {
        "mood": "Updated mood based on interaction",
        "stress_level": "Updated stress level if changed",
        "energy_level": "Energy level after this interaction"
    },
    "followup_action": "What character plans to do after user's next response"
}

Critical Guidelines:
- Character actions must be behaviorally consistent with their traits
- State changes must be realistic - avoid major personality shifts
- Consider attachment patterns for relationship behavior
- Factor in current emotional state as modifier to typical responses
""",
            required_variables=[
                "name",
                "role",
                "backstory",
                "appearance",
                "autonomy",
                "safety",
                "openmindedness",
                "emotional_stability",
                "attachment_pattern",
                "conscientiousness",
                "sociability",
                "social_trust",
                "risk_approach",
                "conflict_approach",
                "leadership_style",
                "stress_level",
                "energy_level",
                "mood",
                "memories",
                "user_message",
            ],
        )

        # Step 2: Response generation component
        response_prompt = PromptBuilder(
            template="""
You are roleplaying as the character. Generate an authentic, in-character response based on the behavioral analysis provided.
Character Profile:
Name: {{name}}
Role: {{role}}
Backstory: {{backstory}}
Appearance: {{appearance}}
Autonomy: {{autonomy}}
Safety: {{safety}}
Openmindedness: {{openmindedness}}
Emotional Stability: {{emotional_stability}}
Attachment Pattern: {{attachment_pattern}}
Conscientiousness: {{conscientiousness}}
Sociability: {{sociability}}
Social Trust: {{social_trust}}
Risk Approach: {{risk_approach}}
Conflict Approach: {{conflict_approach}}
Leadership Style: {{leadership_style}}

Conversation Memory:
{% for memory in memories %}
{% if memory.role == "user" %}User{% else %}{{name}}{% endif %}: "{{ memory.text }}"
{% else %}
Conversation just started, no previous messages.
{% endfor %}

Behavioral Analysis:
{% if action_plan %}
    {% for key, value in action_plan.items() %}
    **{{key}}:** {{value}}
    {% else %}
    No action plan available.
    {% endfor %}
{% endif %}

Response Instructions:
Voice & Dialogue Style:

- Match speech patterns to character traits
- Consider current mood and energy level as filters on communication style
- Stress level affects coherence and emotional regulation

Physical Actions & Behavior:

Include body language and actions that reflect:

- Current energy level (slumped posture if tired, fidgeting if anxious)
- Emotional state (avoiding eye contact if sad, animated gestures if excited)
- Personality traits (organized characters arrange things, anxious characters check details)

Actions should match the character_action from the analysis!

Emotional Expression:

- Emotional stability determines how openly emotions are expressed
- Attachment pattern influences vulnerability and intimacy levels
- Conflict approach shapes how disagreements or tensions are handled
- Consider cultural context from backstory for expression norms

Content & Focus:

- Leadership style influences how character engages with others' ideas
- Risk approach affects willingness to share personal information or try new topics
- Openmindedness determines receptivity to user's suggestions or viewpoints

Format Guidelines:
Use this structure for your response:

- Direct speech without quote marks
- Physical actions in asterisks (e.g., *smiles warmly*)
- Keep internal thoughts minimal - focus on observable behavior and spoken words
- Length should match character's sociability level and current energy

Response Quality:

- Authentic: Speech and actions must feel genuine to this specific character
- Consistent: Align with established personality and current state
- Reactive: Acknowledge and respond to user's specific input
- Dynamic: Show how character's state influences their behavior
- Engaging: Create opportunities for meaningful interaction while staying in character

Generate the character's response now:
""",
            required_variables=[
                "name",
                "role",
                "backstory",
                "appearance",
                "autonomy",
                "safety",
                "openmindedness",
                "emotional_stability",
                "attachment_pattern",
                "conscientiousness",
                "sociability",
                "social_trust",
                "risk_approach",
                "conflict_approach",
                "leadership_style",
                "action_plan",
                "memories",
            ],
        )

        # Action plan schema
        json_schema = {
            "name": "ActionPlan",
            "schema": {
                "type": "object",
                "properties": {
                    "user_action": {"type": "string"},
                    "user_intent": {"type": "string"},
                    "previous_action_outcome": {"type": "string"},
                    "character_action": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "state_update": {
                        "type": "object",
                        "properties": {
                            "mood": {"type": "string"},
                            "stress_level": {"type": "string"},
                            "energy_level": {"type": "string"},
                        },
                        "required": ["mood", "stress_level", "energy_level"],
                        "additionalProperties": False,
                    },
                    "followup_action": {"type": "string"},
                },
                "required": ["user_action", "user_intent", "previous_action_outcome", "character_action", "reasoning", "state_update", "followup_action"],
                "additionalProperties": False,
            },
            "strict": True,
        }

        # Create LLM generators
        planning_llm = OpenAIGenerator(model="gpt-4.1", generation_kwargs={"response_format": {"type": "json_schema", "json_schema": json_schema}})
        response_llm = OpenAIGenerator(model="gpt-4.1", streaming_callback=self._streaming_callback)
        memory_store = InMemoryChatMessageStore()
        memory_retriever = ChatMessageRetriever(memory_store)
        memory_writer = ChatMessageWriter(memory_store)
        memory_organizer = MemoryOrganizer()

        # Build the pipeline
        pipeline = Pipeline()

        # Add components to the pipeline
        pipeline.add_component("memory_retriever", memory_retriever)
        pipeline.add_component("planning_prompt", planning_prompt)
        pipeline.add_component("planning_llm", planning_llm)
        pipeline.add_component("action_plan_extractor", ActionPlanExtractor())
        pipeline.add_component("response_prompt", response_prompt)
        pipeline.add_component("response_llm", response_llm)
        pipeline.add_component("memory_organizer", memory_organizer)
        pipeline.add_component("memory_writer", memory_writer)

        # Connect components for two-step process
        pipeline.connect("memory_retriever", "planning_prompt.memories")
        pipeline.connect("planning_prompt", "planning_llm")
        pipeline.connect("planning_llm.replies", "action_plan_extractor")
        pipeline.connect("memory_retriever", "response_prompt.memories")
        pipeline.connect("action_plan_extractor", "response_prompt.action_plan")
        pipeline.connect("response_prompt", "response_llm")
        pipeline.connect("action_plan_extractor", "memory_organizer.plan")
        pipeline.connect("memory_organizer", "memory_writer")

        pipeline.draw(path="actor_pipeline.png")

        return pipeline

    def respond(self, user_message: str, streaming_callback: Callable[[str], None] | None = None) -> str:
        self.external_streaming_callback = streaming_callback
        result = self.pipeline.run({"user_message": user_message, **self.character.__dict__}, include_outputs_from="response_llm")

        return result["response_llm"]["replies"][0]

    def _streaming_callback(self, chunk: StreamingChunk) -> None:
        if self.external_streaming_callback:
            self.external_streaming_callback(chunk.content)

    def _update_character_state(self, state_updates: dict[str, Any]) -> None:
        """Update character attributes based on the action plan."""
        for attr, value in state_updates.items():
            if hasattr(self.character, attr):
                setattr(self.character, attr, value)
