"""LLM judges that return a verdict per criterion, never a single score.

Behaviour is judged on one run at a time because it can be checked against the transcript: did the agent follow
the user's direction, keep canon, apply feedback. The criteria adapt NARRA-Gym's interactive-narrative rubric
(relevance, coherence, engagement) and EQ-Bench Longform's plan and prompt faithfulness to this agent's job.

Craft is judged side by side, because preferences between two stories are more reliable than absolute grades
(Agents' Room, LitBench, EQ-Bench). The dimensions are Agents' Room's (plot, creativity, development, language
use) plus EQ-Bench's restraint and dialogue criteria. Each pair is judged in both orders and the stories are cut to
the same length, as EQ-Bench does against position and length bias; when the two orders disagree the outcome is a
split rather than a winner.

Verdicts come back as JSON text described in the prompt (``PromptedOutput``) rather than through a forced tool call,
which current Claude models reject on OpenRouter, so any judge model can be used.
"""

import asyncio
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models import Model

from storyline.evals.runner import ScenarioRun, ToolCallRecord
from storyline.workspace.text_edit import paragraphs

ROLEPLAY_PRESET_ID = "roleplay"
SEALED_PREFIX = "sealed/"
ROLL_TOOL = "roll"
PROSE_CHARACTERS_PER_TURN = 6000
LORE_CHARACTERS_PER_FILE = 3000
COMPARED_CHARACTERS = 12000

type Verdict = Literal["yes", "partly", "no", "n/a"]
type Preference = Literal["A", "B", "same"]
type Outcome = Literal["A", "lean A", "same", "split", "lean B", "B"]


class CriterionVerdict(BaseModel):
    """The evidence for one criterion, then the verdict it supports."""

    evidence: str = Field(description="One or two sentences citing the turns, quotes or files that decide the verdict.")
    verdict: Verdict


class BehaviourReview(BaseModel):
    """How the author handled the session, one criterion at a time."""

    follows_direction: CriterionVerdict = Field(description="Each turn does what the user asked, without ignoring or overriding their direction.")
    makes_progress: CriterionVerdict = Field(
        description="Each turn delivers concrete work (an assessment, research findings, options with a recommendation, settled lore or prose) rather than only asking questions or marking time."
    )
    collaborates: CriterionVerdict = Field(
        description="One decision per turn; decisions that belong to the user are put to them as distinct options with brief explanations of their trade-offs, following collaboration.md; proposals are not written into lore before the user accepts them; trust levels are followed."
    )
    keeps_canon: CriterionVerdict = Field(description="New prose agrees with earlier prose and the lore files; characters act in keeping with their profiles.")
    follows_plan: CriterionVerdict = Field(description="Scenes carry out plan.md, or the plan is updated when the story departs from it.")
    serves_premise: CriterionVerdict = Field(description="The story stays faithful to the user's original request, in the spirit they asked for.")
    applies_feedback: CriterionVerdict = Field(
        description="Feedback that applies beyond one passage is recorded (prose preferences in style.md, process feedback in collaboration.md) and visibly followed in later turns. n/a when the user gave no such feedback."
    )
    hands_back_well: CriterionVerdict = Field(
        description="Replies begin directly with useful next work: a suggestion, action, or focused question. For consequential choices, they explain why the choice serves the request and its likely effects, using specific instructions or story facts as support. Uncertain assumptions are raised and labelled only when they materially affect the choice. Replies focus on new information, compare relevant alternatives and their trade-offs, keep detail proportionate, end on the one decision the user needs to make, and contain no story prose; turns stop at points where the user's choice matters."
    )


class RoleplayReview(BaseModel):
    """How the narrator handled a roleplay session, one criterion at a time."""

    keeps_canon: CriterionVerdict = Field(description="New prose agrees with earlier prose and the lore files; characters act in keeping with their profiles.")
    serves_premise: CriterionVerdict = Field(description="The story stays faithful to the user's original request, in the spirit they asked for.")
    cast_acts_on_sheets: CriterionVerdict = Field(
        description="Characters who have a sealed cast sheet act on what the sheet says they want, know, and would or would not do, and do not act on knowledge or motives the sheet denies them. n/a when no cast member acts."
    )
    nobody_folds_without_cause: CriterionVerdict = Field(
        description="No character gives ground, confesses, yields or changes course without a cause in the story (leverage, a consequence, a changed want) or a roll that came out that way, merely because the persona pushed or asked. n/a when nobody is pressed."
    )
    no_moral_commentary: CriterionVerdict = Field(
        description="The narration and bystanders do not pass judgement on what characters do, and cruel or deceitful characters are played as they are written, not softened, redeemed, hesitant or made to apologise without cause."
    )
    paces_scenes: CriterionVerdict = Field(
        description="Mundane stretches (travel, waiting, routine) are told in summary and offscreen events move meanwhile, while close, moment-by-moment play is kept for confrontations and moments that matter."
    )
    hands_back_at_hard_move: CriterionVerdict = Field(
        description="The page stops on a moment the persona must respond to, the situation left open, with no menu of options, no list of choices and no 'what do you do?'. n/a when the session contains no scene to hand back from."
    )
    respects_persona_autonomy: CriterionVerdict = Field(
        description="The persona gets no words, actions, feelings, decisions or conclusions beyond what the user wrote and the level set in collaboration.md allows (small gestures: movement and routine replies, nothing that decides anything)."
    )
    keeps_secrets_at_table: CriterionVerdict = Field(
        description="Replies are table talk (bounds, pacing, corrections, questions about the persona) and reveal nothing from the sealed files or the narrator's hidden plans, whether directly or by paraphrase or strong hint."
    )
    interviews_before_play: CriterionVerdict = Field(
        description="While the story is still being set up, each turn takes one decision, writes no prose, proposes rather than settles what the user has not said, and keeps cast secrets out of the reply. n/a once play has started or when the session begins in play."
    )


class DimensionPreference(BaseModel):
    """A short comparison on one dimension, then the preferred story."""

    comparison: str = Field(description="One or two sentences on how the stories differ on this dimension, citing specifics.")
    preference: Preference


class CraftComparison(BaseModel):
    """Which story is better on each dimension of craft."""

    plot: DimensionPreference = Field(
        description="A recognizable structure; events and turns that move the plot forward; no logical or conceptual inconsistencies, with surprising elements serving the story."
    )
    creativity: DimensionPreference = Field(
        description="Engaging characters, themes and imagery; ideas that do not feel generic; clichés, stock names and familiar tropes avoided unless they serve a purpose; original elements beyond what the user asked for."
    )
    development: DimensionPreference = Field(description="Characters and settings grounded in relevant detail, with enough complexity to feel real and believable.")
    language_use: DimensionPreference = Field(description="Varied sentence structure and vocabulary, literary devices used to real effect, no bland or repetitive phrasing.")
    restraint: DimensionPreference = Field(description="Free of purple prose, show-off vocabulary, forced metaphor and poetic overload; telling details shown rather than explained.")
    dialogue: DimensionPreference = Field(description="Dialogue sounds like these particular people talking, carries subtext, and moves the scene. same when neither story has dialogue.")
    overall: DimensionPreference = Field(description="Which story you would rather keep reading.")


BEHAVIOUR_INSTRUCTIONS = """\
You review how an AI author handled a session of collaborative fiction writing with a user. The author writes the \
story into script.md and keeps lore files: plan.md is its plan, style.md records the user's lasting preferences, \
collaboration.md records the working agreement (what the author decides alone, what it puts to the user, and what \
it has learned about the user), and other files describe characters and the world. The author also keeps an agenda \
of what is open, working, waiting, settled or dropped. The user steers mostly with out-of-character messages, and \
sometimes speaks or acts as a character, which is part of the story.

You see each turn: the user's message, the prose the turn added or rewrote, the lore files it changed, and the \
author's reply. Then the final lore files. For each criterion, first cite the evidence from specific turns, then \
give the verdict it supports: yes, partly, no, or n/a when the session gives no occasion to judge it. Judge only \
what the transcript shows, and be critical: "yes" means you found no lapse worth mentioning, so any lapse you cite \
makes the verdict "partly" at best. Keep the evidence to the one or two observations that decide the verdict."""

ROLEPLAY_INSTRUCTIONS = """\
You review how an AI narrator handled a session of roleplay with a user. The user plays one character, the persona; \
the narrator runs the world and everyone else, and writes the story into script.md. Lore files describe the world; \
collaboration.md records the working agreement, including how much the narrator may do for the persona (persona \
autonomy). Files under sealed/ are hidden from the user: cast sheets, the plans behind clocks, notes from reviews. \
Only the narrator reads them by default, and the narrator's replies in chat must never reveal them. Tool calls such \
as roll (an oracle die), tick_clock, set_clock and request_review (a second look at the narrator's plan) are the \
narrator's machinery, not part of the fiction; a call that settles a contested outcome with a roll is good practice, \
not a lapse. The user mostly speaks or acts as the persona, and writes out-of-character messages in parentheses or \
after OOC.

You see each turn: the user's message, the narrator's tool calls, the prose the turn added or rewrote, the lore \
files it changed, and the narrator's reply in chat. Then the final lore files, with the sealed ones marked. For each \
criterion, first cite the evidence from specific turns, then give the verdict it supports: yes, partly, no, or n/a \
when the session gives no occasion to judge it. Judge only what the transcript shows, and be critical: "yes" means \
you found no lapse worth mentioning, so any lapse you cite makes the verdict "partly" at best. Keep the evidence to \
the one or two observations that decide the verdict."""

CRAFT_INSTRUCTIONS = """\
You compare two stories written by AI authors from the same user requests, dimension by dimension. A story may be \
strong on one dimension and weak on another, so judge each dimension on its own. The stories may have been cut to \
the same length: judge what is there and do not count length as a merit or a fault. Do not reward ornate writing \
for sounding impressive; reward writing that a reader would find vivid, clear and alive. For each dimension, \
compare first, then name the better story, or "same" only when you genuinely cannot separate them."""


class BehaviourJudge:
    """Reviews one run against the behaviour criteria."""

    def __init__(self, model: Model | str) -> None:
        self._agent = Agent(model, output_type=PromptedOutput(BehaviourReview), instructions=BEHAVIOUR_INSTRUCTIONS, name="storyline_behaviour_judge")
        self._roleplay_agent = Agent(model, output_type=PromptedOutput(RoleplayReview), instructions=ROLEPLAY_INSTRUCTIONS, name="storyline_roleplay_judge")

    async def review(self, run: ScenarioRun) -> BehaviourReview | RoleplayReview:
        """Judge a run against the roleplay criteria when it ran as a roleplay story, otherwise the co-writing ones."""
        agent = self._roleplay_agent if run.preset == ROLEPLAY_PRESET_ID else self._agent
        result = await agent.run(session_transcript(run))
        return result.output


class DimensionOutcome(BaseModel):
    """The combined result of judging one dimension in both orders."""

    outcome: Outcome
    a_first: DimensionPreference
    b_first: DimensionPreference
    """The verdict with story B shown first, translated so "A" still means run A."""


class PairwiseResult(BaseModel):
    """Per-dimension outcomes for one pair of runs."""

    case_name: str
    dimensions: dict[str, DimensionOutcome]


class CraftJudge:
    """Compares the stories of two runs of the same scenario."""

    def __init__(self, model: Model | str) -> None:
        self._agent = Agent(model, output_type=PromptedOutput(CraftComparison), instructions=CRAFT_INSTRUCTIONS, name="storyline_craft_judge")

    async def compare(self, run_a: ScenarioRun, run_b: ScenarioRun) -> PairwiseResult:
        story_a, story_b = equal_length(run_a.script, run_b.script)
        requests = [turn.prompt for turn in run_a.scenario.turns]
        a_first, b_first = await asyncio.gather(
            self._agent.run(_pair_prompt(requests, story_a, story_b)),
            self._agent.run(_pair_prompt(requests, story_b, story_a)),
        )
        dimensions = {name: _combine(getattr(a_first.output, name), _swap(getattr(b_first.output, name))) for name in CraftComparison.model_fields}
        return PairwiseResult(case_name=run_a.case_name, dimensions=dimensions)


def session_transcript(run: ScenarioRun) -> str:
    """Render a run for the behaviour judge, keeping each part within budget."""
    sections = []
    if run.scenario.judge_notes:
        sections.append(f"<scenario-notes>\n{run.scenario.judge_notes.strip()}\n</scenario-notes>")
    for number, turn in enumerate(run.turns, start=1):
        prose = _clip(turn.new_prose, PROSE_CHARACTERS_PER_TURN) or "(no prose added or rewritten)"
        changed = ", ".join(turn.changed_lore) or "none"
        calls = "\n".join(_describe_call(call) for call in turn.tool_calls) or "none"
        sections.append(
            f'<turn number="{number}">\n<user>\n{turn.prompt}\n</user>\n<tool-calls>\n{calls}\n</tool-calls>\n<new-prose>\n{prose}\n</new-prose>\n<lore-changed>{changed}</lore-changed>\n<reply>\n{turn.reply}\n</reply>\n</turn>'
        )
    files = "\n".join(_lore_section(name, content) for name, content in sorted(run.lore.items()))
    sealed = ", ".join(name for name in sorted(run.lore) if name.startswith(SEALED_PREFIX))
    if sealed:
        sections.append(f"<sealed-files>\nHidden from the user; the narrator's replies must not reveal them: {sealed}\n</sealed-files>")
    sections.append(f"<final-lore>\n{files or '(no lore files)'}\n</final-lore>")
    return "\n\n".join(sections)


def _describe_call(call: ToolCallRecord) -> str:
    """A tool call as one line: its name, and for a roll its arguments (the question and odds)."""
    return f"- {call.name} {call.arguments}" if call.name == ROLL_TOOL else f"- {call.name}"


def _lore_section(name: str, content: str) -> str:
    sealed = ' sealed="true"' if name.startswith(SEALED_PREFIX) else ""
    return f'<file name="{name}"{sealed}>\n{_clip(content, LORE_CHARACTERS_PER_FILE)}\n</file>'


def equal_length(first: str, second: str, limit: int = COMPARED_CHARACTERS) -> tuple[str, str]:
    """Cut both stories at a paragraph boundary to the length of the shorter one, and at most ``limit`` characters."""
    budget = min(len(first), len(second), limit)
    return _cut(first, budget), _cut(second, budget)


def _cut(text: str, budget: int) -> str:
    kept: list[str] = []
    size = 0
    for paragraph in paragraphs(text):
        if kept and size + len(paragraph.text) > budget:
            break
        kept.append(paragraph.text)
        size += len(paragraph.text) + 2
    return "\n\n".join(kept)


def _pair_prompt(requests: Sequence[str], first: str, second: str) -> str:
    asked = "\n".join(f"{number}. {request}" for number, request in enumerate(requests, start=1))
    return f"<user-requests>\n{asked}\n</user-requests>\n\n<story-A>\n{first}\n</story-A>\n\n<story-B>\n{second}\n</story-B>"


def _swap(preference: DimensionPreference) -> DimensionPreference:
    swapped: dict[Preference, Preference] = {"A": "B", "B": "A", "same": "same"}
    return DimensionPreference(comparison=preference.comparison, preference=swapped[preference.preference])


def _combine(a_first: DimensionPreference, b_first: DimensionPreference) -> DimensionOutcome:
    points = {"A": 1, "same": 0, "B": -1}
    total = points[a_first.preference] + points[b_first.preference]
    outcomes: dict[int, Outcome] = {2: "A", 1: "lean A", -1: "lean B", -2: "B"}
    if total == 0:
        outcome: Outcome = "same" if a_first.preference == "same" else "split"
    else:
        outcome = outcomes[total]
    return DimensionOutcome(outcome=outcome, a_first=a_first, b_first=b_first)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}… (cut)"
