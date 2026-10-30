"""Tests for the review mechanic: what the reviewer is given, what it can do, how its verdict reads and how it fails."""

import json
from collections.abc import Callable

import pytest
from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import TurnOutcome, WritingSession, create_writer_agent, tool_call_is_sealed
from storyline.agent.reviewer import FALLBACK_CHECKLIST, REVIEW_MODEL_ENV_VAR, reviewer_toolset
from storyline.mechanics import Mechanic, resolve_mechanics
from storyline.mechanics.review import BeatPlan
from storyline.presets import BUNDLED_PRESETS
from storyline.registry import MECHANICS, build_mechanics
from tests.mechanics_support import run_turn, story_with, tool_returns, user_prompts, writer_calling

PLAN = {
    "persona_input": "I tell the guard I am the new cook.",
    "actions": [{"character": "Vera", "intends": "Test the story with a question about the kitchen", "because": "sealed/vera.md: she distrusts newcomers"}],
    "rolls": ["Does the guard believe the lie? likely: Yes (rolled 40 against likely)."],
    "changes": ["The guard's suspicion clock does not move."],
    "hand_back": "The guard waves her toward the kitchen door.",
}


class Reviewer:
    """A fake reviewer model: records everything it is asked and answers with a scripted verdict."""

    def __init__(self, verdict: dict[str, object] | None = None, *, error: Exception | None = None, read: tuple[str, dict[str, object]] | None = None) -> None:
        self.verdict = verdict if verdict is not None else {"verdict": "pass"}
        self.error = error
        self.read = read
        self.instructions: list[str] = []
        self.tools: list[list[str]] = []
        self.output_tools: list[list[str]] = []
        self.text_output: list[bool] = []
        self.prompts: list[list[str]] = []
        self.model = FunctionModel(self._respond)

    def _respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.instructions.append(str(info.instructions))
        self.tools.append([tool.name for tool in info.function_tools])
        self.output_tools.append([tool.name for tool in info.output_tools])
        self.text_output.append(info.allow_text_output)
        self.prompts.append(user_prompts(messages))
        if self.error is not None:
            raise self.error
        if self.read is not None and not tool_returns(messages):
            name, arguments = self.read
            return ModelResponse(parts=[ToolCallPart(tool_name=name, args=arguments)])
        return ModelResponse(parts=[TextPart(content=json.dumps(self.verdict))])


def _writer(reviewer: Reviewer) -> FunctionModel:
    """A writer that asks for a review and shares its model with the reviewer when no other model is set."""
    return writer_calling(("request_review", {"plan": PLAN}), outputs=reviewer._respond)


async def _review(tmp_path, reviewer: Reviewer, *, prompt: str = "I walk up to the guard.", mechanic: Mechanic | None = None):
    story = await story_with(tmp_path)
    await story.write_lore(filename="city.md", content="---\nsummary: The city.\nkeywords: k\n---\nBuffalo.\n")
    session, outcome, results = await run_turn(story, _writer(reviewer), prompt, replacing={"review": mechanic or MECHANICS["review"]})
    return story, session, outcome, results


# What the reviewer is given


@pytest.mark.asyncio
async def test_the_reviewer_gets_the_snapshot_the_latest_user_message_and_the_plan(tmp_path) -> None:
    reviewer = Reviewer()

    await _review(tmp_path, reviewer, prompt="I walk up to the guard.")

    [snapshot, request] = reviewer.prompts[0]
    assert "<story-snapshot>" in snapshot and "sealed/vera.md" in snapshot and "city.md" in snapshot
    assert "I walk up to the guard." in request
    assert "<story-snapshot>" not in request
    assert BeatPlan.model_validate(json.loads(request[request.index("{") :])) == BeatPlan.model_validate(PLAN)


@pytest.mark.asyncio
async def test_the_reviewer_is_told_when_the_user_has_not_written_yet(tmp_path) -> None:
    reviewer = Reviewer()

    await _review(tmp_path, reviewer, prompt="")

    assert "no message from the user" in reviewer.prompts[0][-1]


@pytest.mark.asyncio
async def test_the_reviewer_instructions_hold_its_prompt_then_the_presets_checklist(tmp_path) -> None:
    reviewer = Reviewer()
    checklist = BUNDLED_PRESETS.get("roleplay").review_checklist

    await _review(tmp_path, reviewer)

    assert checklist is not None
    instructions = reviewer.instructions[0]
    assert instructions.index("You review a narrator's plan") < instructions.index("## Checklist") < instructions.index(checklist.rstrip())


@pytest.mark.asyncio
async def test_a_story_whose_preset_has_no_checklist_gets_the_fallback(tmp_path) -> None:
    reviewer = Reviewer()
    story = await story_with(tmp_path, preset="co-writing", mechanics=("sealed", "review"))

    await run_turn(story, _writer(reviewer))

    assert FALLBACK_CHECKLIST in reviewer.instructions[0]


@pytest.mark.asyncio
async def test_the_reviewer_can_read_the_story_but_has_no_writing_tools(tmp_path) -> None:
    reviewer = Reviewer(read=("read_lore", {"filename": "sealed/vera.md"}))

    _, _, outcome, [result] = await _review(tmp_path, reviewer)

    assert outcome is TurnOutcome.COMPLETED and str(result.content) == "Pass."
    assert set(reviewer.tools[0]) == {"list_lore", "read_lore", "read_script"}
    assert len(reviewer.tools) == 2
    assert set(reviewer_toolset().tools) == {"list_lore", "read_lore", "read_script"}


# Verdicts


@pytest.mark.asyncio
async def test_the_reviewer_answers_in_text_so_no_tool_call_is_forced_on_its_model(tmp_path) -> None:
    reviewer = Reviewer()

    await _review(tmp_path, reviewer)

    review_requests = [index for index, tools in enumerate(reviewer.tools) if "request_review" not in tools]
    assert review_requests
    for index in review_requests:
        assert reviewer.output_tools[index] == []
        assert reviewer.text_output[index] is True


@pytest.mark.asyncio
async def test_a_pass_reads_pass(tmp_path) -> None:
    _, _, _, [result] = await _review(tmp_path, Reviewer({"verdict": "pass"}))

    assert str(result.content) == "Pass." and result.outcome == "success"


@pytest.mark.asyncio
async def test_objections_name_what_they_rest_on_and_what_would_fit(tmp_path) -> None:
    verdict = {
        "verdict": "object",
        "objections": [
            {"issue": "The guard believes the lie without cause.", "rests_on": "sealed/vera.md says she distrusts newcomers", "instead": "She asks a question the persona cannot answer."},
            {"issue": "The clock is ignored.", "rests_on": "the suspicion clock at 5/6", "instead": "Tick it before the beat."},
        ],
    }

    _, _, outcome, [result] = await _review(tmp_path, Reviewer(verdict))

    lines = str(result.content).splitlines()
    assert outcome is TurnOutcome.COMPLETED
    assert lines[0].startswith("Objections") and len(lines) == 3
    assert "believes the lie" in lines[1] and "sealed/vera.md" in lines[1] and "asks a question" in lines[1]
    assert "suspicion clock at 5/6" in lines[2] and "Tick it" in lines[2]


@pytest.mark.asyncio
async def test_an_objection_without_objections_is_not_accepted_as_a_verdict(tmp_path) -> None:
    reviewer = Reviewer({"verdict": "object", "objections": []})

    _, _, outcome, [result] = await _review(tmp_path, reviewer)

    assert outcome is TurnOutcome.COMPLETED and result.outcome == "failed"


# Failure and cost


@pytest.mark.asyncio
async def test_a_reviewer_that_fails_fails_the_tool_and_not_the_turn(tmp_path) -> None:
    _, _, outcome, [result] = await _review(tmp_path, Reviewer(error=RuntimeError("provider down")))

    assert outcome is TurnOutcome.COMPLETED
    assert result.outcome == "failed" and "reviewer" in str(result.content).lower()


@pytest.mark.asyncio
async def test_the_review_costs_count_in_the_turn(tmp_path) -> None:
    story = await story_with(tmp_path)
    reviewer = Reviewer()
    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=_writer(reviewer), registry=MECHANICS)
    turn = session.turn("Go.")

    await turn.run()

    writer_requests = 2
    assert turn.outcome is TurnOutcome.COMPLETED
    assert turn.usage.requests == writer_requests + len(reviewer.prompts)
    assert turn.usage.input_tokens > 0


# The reviewer's model


def _resolver(models: dict[str, FunctionModel]) -> Callable[[str], FunctionModel]:
    return lambda name: models[name]


@pytest.mark.asyncio
async def test_the_model_named_in_the_environment_reviews_when_it_is_set(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_MODEL_ENV_VAR, "openai:reviewer")
    elsewhere, narrator = Reviewer({"verdict": "pass"}), Reviewer()
    mechanic = build_mechanics(review_model_resolver=_resolver({"openai:reviewer": elsewhere.model}))["review"]

    _, _, _, [result] = await _review(tmp_path, narrator, mechanic=mechanic)

    assert str(result.content) == "Pass."
    assert len(elsewhere.prompts) == 1
    assert narrator.prompts == []


@pytest.mark.asyncio
async def test_the_narrators_model_reviews_when_nothing_is_set(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(REVIEW_MODEL_ENV_VAR, raising=False)
    narrator = Reviewer()

    await _review(tmp_path, narrator, mechanic=build_mechanics(review_model_resolver=_resolver({}))["review"])

    assert len(narrator.prompts) == 1


@pytest.mark.asyncio
async def test_an_environment_value_that_is_blank_counts_as_unset(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(REVIEW_MODEL_ENV_VAR, "  ")
    narrator = Reviewer()

    await _review(tmp_path, narrator)

    assert len(narrator.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["not-a-model", "nosuchprovider:model"])
async def test_an_invalid_environment_model_fails_the_tool_and_says_so(tmp_path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(REVIEW_MODEL_ENV_VAR, name)
    narrator = Reviewer()

    _, _, outcome, [result] = await _review(tmp_path, narrator)

    assert outcome is TurnOutcome.COMPLETED
    assert result.outcome == "failed" and REVIEW_MODEL_ENV_VAR in str(result.content)
    assert narrator.prompts == []


# Registration and sealing


def test_review_needs_the_sealed_mechanic_and_offers_one_tool() -> None:
    assert [mechanic.id for mechanic in resolve_mechanics(["review"], MECHANICS)] == ["sealed", "review"]
    toolset = MECHANICS["review"].toolset
    assert toolset is not None and set(toolset.tools) == {"request_review"}


def test_a_review_request_is_sealed() -> None:
    mechanics = resolve_mechanics(["review"], MECHANICS)

    assert tool_call_is_sealed("request_review", {"plan": PLAN}, mechanics) is True
    assert tool_call_is_sealed("request_review", {}, ()) is False


def test_the_plan_model_documents_each_field_for_the_model() -> None:
    schema = BeatPlan.model_json_schema()

    assert set(schema["required"]) == {"persona_input", "actions", "hand_back"}
    assert all(property_.get("description") for property_ in schema["properties"].values())
