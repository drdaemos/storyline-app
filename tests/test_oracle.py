"""Tests for the oracle: the odds ladder, strong results, the sealed roll log and the snapshot section."""

import json
from datetime import UTC, datetime

import pytest

from storyline.agent import TurnOutcome, tool_call_is_sealed, turn_prompt
from storyline.mechanics import OracleMechanic, resolve_mechanics
from storyline.mechanics.oracle import LOG_LIMIT, ODDS_CHANCE, SNAPSHOT_ROLLS, answer_for
from storyline.registry import MECHANICS
from storyline.workspace import Roll, RollLogError
from storyline.workspace.file_story import FileStory
from tests.mechanics_support import run_turn, story_with, writer_calling


def _die(*values: int) -> OracleMechanic:
    """An oracle whose die shows these values in turn."""
    remaining = iter(values)
    return OracleMechanic(roll_die=lambda: next(remaining))


async def _roll(tmp_path, oracle: OracleMechanic, *calls: tuple[str, str]):
    story = await story_with(tmp_path)
    arguments = [("roll", {"question": question, "odds": odds}) for question, odds in calls]
    _, outcome, results = await run_turn(story, writer_calling(*arguments), replacing={"oracle": oracle})
    assert outcome is TurnOutcome.COMPLETED
    return story, results


# The ladder


def test_the_odds_ladder_has_five_steps_from_unlikely_to_certain() -> None:
    assert ODDS_CHANCE == {"almost certain": 90, "likely": 75, "even": 50, "unlikely": 25, "small chance": 10}


@pytest.mark.parametrize(
    ("odds", "die", "expected"),
    [
        ("almost certain", 1, ("yes", True)),
        ("almost certain", 18, ("yes", True)),
        ("almost certain", 19, ("yes", False)),
        ("almost certain", 90, ("yes", False)),
        ("almost certain", 91, ("no", False)),
        ("almost certain", 98, ("no", False)),
        ("almost certain", 99, ("no", True)),
        ("likely", 15, ("yes", True)),
        ("likely", 16, ("yes", False)),
        ("likely", 75, ("yes", False)),
        ("likely", 76, ("no", False)),
        ("likely", 95, ("no", False)),
        ("likely", 96, ("no", True)),
        ("even", 10, ("yes", True)),
        ("even", 11, ("yes", False)),
        ("even", 50, ("yes", False)),
        ("even", 51, ("no", False)),
        ("even", 90, ("no", False)),
        ("even", 91, ("no", True)),
        ("unlikely", 5, ("yes", True)),
        ("unlikely", 6, ("yes", False)),
        ("unlikely", 25, ("yes", False)),
        ("unlikely", 26, ("no", False)),
        ("unlikely", 85, ("no", False)),
        ("unlikely", 86, ("no", True)),
        ("small chance", 2, ("yes", True)),
        ("small chance", 3, ("yes", False)),
        ("small chance", 10, ("yes", False)),
        ("small chance", 11, ("no", False)),
        ("small chance", 82, ("no", False)),
        ("small chance", 83, ("no", True)),
        ("small chance", 100, ("no", True)),
    ],
)
def test_a_die_answers_yes_up_to_the_chance_and_strongly_at_the_extremes(odds: str, die: int, expected: tuple[str, bool]) -> None:
    assert answer_for(die, ODDS_CHANCE[odds]) == expected


# The tool


@pytest.mark.asyncio
async def test_a_roll_says_the_answer_plainly_and_logs_it(tmp_path) -> None:
    story, [result] = await _roll(tmp_path, _die(97), ("Does the guard believe the lie?", "likely"))

    assert str(result.content) == "Strong no (rolled 97 against likely)."
    [logged] = await story.read_rolls()
    assert (logged.question, logged.odds, logged.die, logged.answer, logged.strong) == ("Does the guard believe the lie?", "likely", 97, "no", True)
    assert logged.at.tzinfo is not None


@pytest.mark.asyncio
async def test_rolls_are_logged_newest_first(tmp_path) -> None:
    story, results = await _roll(tmp_path, _die(40, 60, 8), ("First?", "even"), ("Second?", "even"), ("Third?", "even"))

    assert [str(result.content) for result in results] == ["Yes (rolled 40 against even).", "No (rolled 60 against even).", "Strong yes (rolled 8 against even)."]
    assert [roll.question for roll in await story.read_rolls()] == ["Third?", "Second?", "First?"]


@pytest.mark.asyncio
async def test_the_log_keeps_only_the_latest_rolls(tmp_path) -> None:
    story = await story_with(tmp_path)
    old = tuple(Roll(question=f"Old {number}?", odds="even", die=50, answer="yes", at=datetime.now(UTC)) for number in reversed(range(LOG_LIMIT)))
    await story.change_rolls(change=lambda _: old)

    await run_turn(story, writer_calling(("roll", {"question": "New?", "odds": "even"})), replacing={"oracle": _die(50)})

    rolls = await story.read_rolls()
    assert len(rolls) == LOG_LIMIT
    assert rolls[0].question == "New?"
    assert rolls[1] == old[0]
    assert rolls[-1] == old[LOG_LIMIT - 2]


@pytest.mark.asyncio
async def test_the_roll_log_lives_in_the_sealed_folder_and_is_not_lore(tmp_path) -> None:
    story, _ = await _roll(tmp_path, _die(50), ("Does it rain?", "even"))

    assert (tmp_path / "sealed" / "rolls.json").is_file()
    assert [lore.filename for lore in await story.list_lore()] == ["sealed/vera.md"]


@pytest.mark.asyncio
async def test_an_empty_question_is_refused_and_nothing_is_logged(tmp_path) -> None:
    story = await story_with(tmp_path)

    _, outcome, [result] = await run_turn(story, writer_calling(("roll", {"question": " ", "odds": "even"})), replacing={"oracle": _die(50)})

    assert outcome is TurnOutcome.COMPLETED and result.outcome == "failed"
    assert await story.read_rolls() == ()


def test_the_roll_tool_accepts_only_the_odds_of_the_ladder() -> None:
    toolset = MECHANICS["oracle"].toolset
    assert toolset is not None

    schema = toolset.tools["roll"].function_schema.json_schema

    assert all(f'"{odds}"' in json.dumps(schema) for odds in ODDS_CHANCE)


@pytest.mark.asyncio
async def test_an_unreadable_log_fails_the_roll_but_still_reports_what_came_up(tmp_path) -> None:
    story = await story_with(tmp_path)
    (tmp_path / "sealed").mkdir(exist_ok=True)
    (tmp_path / "sealed" / "rolls.json").write_text("not json", encoding="utf-8")

    _, outcome, [result] = await run_turn(story, writer_calling(("roll", {"question": "Does it rain?", "odds": "even"})), replacing={"oracle": _die(50)})

    assert outcome is TurnOutcome.COMPLETED and result.outcome == "failed"
    assert "rolled 50" in str(result.content)
    with pytest.raises(RollLogError):
        await story.read_rolls()


def test_the_default_die_rolls_from_one_to_one_hundred() -> None:
    rolls = {OracleMechanic().roll_die() for _ in range(2000)}

    assert min(rolls) >= 1 and max(rolls) <= 100 and len(rolls) > 50


def test_the_registered_oracle_offers_the_roll_tool_and_is_its_own_instance() -> None:
    assert MECHANICS["oracle"] is not _die(1)
    assert MECHANICS["oracle"].toolset is not None and set(MECHANICS["oracle"].toolset.tools) == {"roll"}


# Snapshot and sealing


@pytest.mark.asyncio
async def test_the_snapshot_shows_the_latest_rolls_and_says_so_when_there_are_none(tmp_path) -> None:
    story = await story_with(tmp_path)
    mechanics = resolve_mechanics(["oracle"], MECHANICS)
    empty = str((await turn_prompt(story, "Go.", mechanics, registry=MECHANICS))[0])
    count = SNAPSHOT_ROLLS + 2
    arguments = [("roll", {"question": f"Question {number}?", "odds": "even"}) for number in range(count)]
    await run_turn(story, writer_calling(*arguments), replacing={"oracle": _die(*([50] * count))})

    snapshot = str((await turn_prompt(story, "Go.", mechanics, registry=MECHANICS))[0])

    assert "Question 0?" not in empty and "none" in empty
    shown = [line for line in snapshot.splitlines() if "Question" in line]
    assert len(shown) == SNAPSHOT_ROLLS
    assert f"Question {count - 1}?" in shown[0] and "Yes (rolled 50 against even)." in shown[0]
    assert "Question 1?" not in snapshot


def test_a_roll_is_sealed_in_a_story_with_the_oracle() -> None:
    mechanics = resolve_mechanics(["oracle"], MECHANICS)

    assert tool_call_is_sealed("roll", {"question": "x", "odds": "even"}, mechanics) is True
    assert tool_call_is_sealed("roll", {}, ()) is False


@pytest.mark.asyncio
async def test_a_story_that_never_rolled_has_an_empty_log(tmp_path) -> None:
    assert await FileStory(tmp_path).read_rolls() == ()
