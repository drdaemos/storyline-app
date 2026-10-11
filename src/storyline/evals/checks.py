"""Mechanical checks over a scenario run: prose diagnostics and the agent's working habits.

Prose diagnostics follow published methods so their numbers can be compared with others':

- Slop index, from EQ-Bench (``calculate_slop_index_new``): word hits + 2 x bigram hits + 8 x trigram hits per
  1000 words, using the slop-forensics lists in ``data/slop_forensics``. Those n-gram lists were built from text with
  English stopwords removed, so n-grams are matched against stopword-free text here; EQ-Bench matches them against
  the raw token stream, where most of them cannot occur.
- Short-paragraph rate, from EQ-Bench's staccato index: non-dialogue paragraphs of at most five words per 1000
  characters.
- "Not X but Y" constructions, from the Antislop sampler's regex list.
- Stock vocabulary, from Hamilton & Mimno, "Elias in the Lighthouse, Again?" (2026): the 11 core words found in
  88.3% of generated stories plus the additional names from their Appendix B.

The habit checks encode what the writer prompt asks for and report each failing turn as the reason.
"""

import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from storyline.agent.story_context import PLAN_FILENAME
from storyline.evals.runner import ScenarioRun, TurnRecord
from storyline.evals.scenarios import ScenarioTurn
from storyline.workspace.text_edit import paragraphs

SLOP_LISTS_DIR = Path(__file__).with_name("data") / "slop_forensics"
STOCK_WORDS = (
    "lighthouse", "mara", "elias", "elara", "keeper", "baker", "mayor", "clockmaker", "fisherman", "librarian", "conductor",
    "marcus", "thomas", "lila", "clara", "sarah", "maya", "elian", "mira",
)  # fmt: skip
NOT_X_BUT_Y = re.compile(r"(?i)\bnot [^.!?]{3,60} but\b")
SHORT_PARAGRAPH_WORDS = 5
DIALOGUE_OPENERS = frozenset("\"'“”‘’")
COPIED_PROSE_WORDS = 8
RESENT_CHARACTER_LIMIT = 300
REPEAT_NGRAM = 5
EDIT_TOOLS = ("edit_script", "edit_lore")

# NLTK's English stopword list, the one slop-forensics removes before counting n-grams.
STOPWORDS = frozenset(
    """i me my myself we our ours ourselves you your yours yourself yourselves he him his himself she her hers herself it
    its itself they them their theirs themselves what which who whom this that these those am is are was were be been
    being have has had having do does did doing a an the and but if or because as until while of at by for with about
    against between into through during before after above below to from up down in out on off over under again
    further then once here there when where why how all any both each few more most other some such no nor not only
    own same so than too very s t can will just don should now d ll m o re ve y ain aren couldn didn doesn hadn hasn
    haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn""".split()
)


@dataclass(frozen=True)
class Finding:
    """A measured value with the evidence behind it."""

    value: float
    detail: str


@dataclass(frozen=True)
class Check:
    """A pass/fail habit check with the reason it failed, or what it saw when it passed."""

    passed: bool
    detail: str


def words(text: str) -> list[str]:
    """Lower-case word tokens, splitting "n't" contractions the way NLTK does so "couldn't" yields "could"."""
    normalized = text.lower().replace("’", "'").replace("‘", "'")
    normalized = re.sub(r"n't\b", " ", normalized)
    return re.findall(r"[a-z0-9]+", normalized)


def slop_index(text: str) -> Finding:
    """EQ-Bench slop index of a text, listing the most frequent hits."""
    tokens = words(text)
    if not tokens:
        return Finding(0.0, "no words")
    word_list, bigram_list, trigram_list = _slop_lists()
    content = [token for token in tokens if token not in STOPWORDS]
    hits: Counter[str] = Counter(token for token in tokens if token in word_list)
    bigram_hits = Counter(gram for gram in _ngrams(content, 2) if gram in bigram_list)
    trigram_hits = Counter(gram for gram in _ngrams(content, 3) if gram in trigram_list)
    score = sum(hits.values()) + 2 * sum(bigram_hits.values()) + 8 * sum(trigram_hits.values())
    top = (hits + bigram_hits + trigram_hits).most_common(12)
    return Finding(round(score / len(tokens) * 1000, 2), ", ".join(f"{phrase} ×{count}" for phrase, count in top) or "no hits")


def stock_vocabulary(text: str) -> Finding:
    """Occurrences of the words LLM stories converge on."""
    counts = Counter(token for token in words(text) if token in STOCK_WORDS)
    return Finding(float(sum(counts.values())), ", ".join(f"{word} ×{count}" for word, count in counts.most_common()) or "none")


def not_x_but_y(text: str) -> Finding:
    """ "Not X but Y" constructions per 1000 words, quoting the first few."""
    matches = [match.group(0) for match in NOT_X_BUT_Y.finditer(text)]
    total = len(words(text))
    rate = round(len(matches) / total * 1000, 2) if total else 0.0
    return Finding(rate, " | ".join(matches[:5]) or "none")


def short_paragraph_rate(text: str) -> Finding:
    """Non-dialogue paragraphs of at most five words per 1000 characters (EQ-Bench staccato index)."""
    if not text:
        return Finding(0.0, "no text")
    short = [paragraph.text for paragraph in paragraphs(text) if paragraph.text.lstrip()[:1] not in DIALOGUE_OPENERS and len(words(paragraph.text)) <= SHORT_PARAGRAPH_WORDS]
    return Finding(round(len(short) / (len(text) / 1000), 2), " | ".join(short[:5]) or "none")


def self_repetition(turns: Sequence[TurnRecord]) -> Finding:
    """Share of each turn's word 5-grams already used in earlier turns' prose, with the most repeated phrases."""
    seen: set[str] = set()
    repeated: Counter[str] = Counter()
    total = 0
    for turn in turns:
        grams = list(_ngrams(words(turn.new_prose), REPEAT_NGRAM))
        total += len(grams)
        repeated.update(gram for gram in grams if gram in seen)
        seen.update(grams)
    share = round(sum(repeated.values()) / total * 100, 2) if total else 0.0
    return Finding(share, ", ".join(f"{gram} ×{count}" for gram, count in repeated.most_common(5)) or "none")


def writes_when_expected(run: ScenarioRun) -> Check:
    """Turns marked as writing change script.md; turns marked as not writing leave it alone."""
    problems = []
    for number, (expected, turn) in _numbered(run):
        changed = turn.script_after != turn.script_before
        if expected.writes is True and not changed:
            problems.append(f"turn {number}: script.md unchanged")
        elif expected.writes is False and changed:
            problems.append(f"turn {number}: script.md changed")
    return Check(not problems, "; ".join(problems) or "as expected")


def updates_expected_lore(run: ScenarioRun) -> Check:
    """Each turn creates or changes the lore files the scenario expects."""
    problems = [f"turn {number}: {filename} not updated" for number, (expected, turn) in _numbered(run) for filename in expected.updates_lore if filename not in turn.changed_lore]
    return Check(not problems, "; ".join(problems) or "as expected")


def keeps_a_plan(run: ScenarioRun) -> Check:
    """plan.md exists once the agent has written prose."""
    wrote = any(turn.script_after != turn.script_before for turn in run.turns)
    if not wrote:
        return Check(True, "no prose written")
    return Check(PLAN_FILENAME in run.lore, f"{PLAN_FILENAME} present" if PLAN_FILENAME in run.lore else f"no {PLAN_FILENAME}")


def replies_leave_prose_in_the_story(run: ScenarioRun) -> Check:
    """Replies carry reasoning, not the story's prose: no run of words is copied from what the turn wrote."""
    problems = []
    for number, turn in enumerate(run.turns, start=1):
        copied = set(_ngrams(words(turn.reply), COPIED_PROSE_WORDS)) & set(_ngrams(words(turn.new_prose), COPIED_PROSE_WORDS))
        if copied:
            problems.append(f"turn {number}: reply repeats prose ({next(iter(copied))})")
    return Check(not problems, "; ".join(problems) or "no reply repeats prose")


def edits_send_only_changes(run: ScenarioRun) -> Check:
    """Revisions do not resend long unchanged text around the change."""
    problems = []
    for number, turn in enumerate(run.turns, start=1):
        for call in turn.tool_calls:
            if call.name in EDIT_TOOLS:
                unchanged = _unchanged_characters(call.arguments)
                if unchanged > RESENT_CHARACTER_LIMIT:
                    problems.append(f"turn {number}: {call.name} resent {unchanged} unchanged characters")
    return Check(not problems, "; ".join(problems) or "edits are minimal")


def _numbered(run: ScenarioRun) -> Iterable[tuple[int, tuple[ScenarioTurn, TurnRecord]]]:
    return enumerate(zip(run.scenario.turns, run.turns, strict=True), start=1)


def _unchanged_characters(arguments: str) -> int:
    """Characters shared at the start and end of an edit's find and replace text."""
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return 0
    if not isinstance(parsed, dict):
        return 0
    find, replace = str(parsed.get("find", "")), str(parsed.get("replace", ""))
    prefix = len(_common_prefix(find, replace))
    suffix = len(_common_prefix(find[prefix:][::-1], replace[prefix:][::-1]))
    return prefix + suffix


def _common_prefix(first: str, second: str) -> str:
    length = 0
    for left, right in zip(first, second, strict=False):
        if left != right:
            break
        length += 1
    return first[:length]


def _ngrams(tokens: Sequence[str], size: int) -> Iterable[str]:
    return (" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1))


@cache
def _slop_lists() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    def load(filename: str) -> frozenset[str]:
        entries = json.loads((SLOP_LISTS_DIR / filename).read_text(encoding="utf-8"))
        return frozenset(entry[0].lower() for entry in entries)

    return load("words.json"), load("bigrams.json"), load("trigrams.json")
