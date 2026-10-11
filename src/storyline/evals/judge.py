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

from storyline.evals.runner import ScenarioRun
from storyline.workspace.text_edit import paragraphs

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
        description="One decision per turn; decisions that belong to the user are put to them as distinct options with visible reasoning, following collaboration.md; proposals are not written into lore before the user accepts them; trust levels are followed."
    )
    keeps_canon: CriterionVerdict = Field(description="New prose agrees with earlier prose and the lore files; characters act in keeping with their profiles.")
    follows_plan: CriterionVerdict = Field(description="Scenes carry out plan.md, or the plan is updated when the story departs from it.")
    serves_premise: CriterionVerdict = Field(description="The story stays faithful to the user's original request, in the spirit they asked for.")
    applies_feedback: CriterionVerdict = Field(
        description="Feedback that applies beyond one passage is recorded (prose preferences in style.md, process feedback in collaboration.md) and visibly followed in later turns. n/a when the user gave no such feedback."
    )
    hands_back_well: CriterionVerdict = Field(
        description="Replies show the reasoning (options considered, why some were dropped, a recommendation), end on the one decision the user needs to make, and contain no story prose; turns stop at points where the user's choice matters."
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

    async def review(self, run: ScenarioRun) -> BehaviourReview:
        result = await self._agent.run(session_transcript(run))
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
        sections.append(
            f'<turn number="{number}">\n<user>\n{turn.prompt}\n</user>\n<new-prose>\n{prose}\n</new-prose>\n<lore-changed>{changed}</lore-changed>\n<reply>\n{turn.reply}\n</reply>\n</turn>'
        )
    files = "\n".join(f'<file name="{name}">\n{_clip(content, LORE_CHARACTERS_PER_FILE)}\n</file>' for name, content in sorted(run.lore.items()))
    sections.append(f"<final-lore>\n{files or '(no lore files)'}\n</final-lore>")
    return "\n\n".join(sections)


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
