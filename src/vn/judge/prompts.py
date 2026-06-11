"""Judge prompt text. Tests must never assert on this wording (it changes often).

Two lens passes over the same rendered script: 'playwright' (dramatic craft) and
'director' (interactive craft). Each lens carries an anchored 1-5 rubric, binary
craft checks, calibration guidance against score clustering, and severity-tiered
finding rules. Output shape is enforced by structured outputs (LensReview)."""

from src.models.vn.input import VNInput
from src.models.vn.judge import DIRECTOR_DIMENSIONS, PLAYWRIGHT_DIMENSIONS, JudgeLens
from src.models.vn.validation import ValidationReport

_SHARED_RULES = """
How to work:
- You are reviewing a structural skeleton: beats carry terse 'intent' descriptions, not prose.
  Judge the dramatic and interactive DESIGN, never the absence of prose. Structural validity
  (id resolution, reachability) is machine-checked elsewhere — do not spend findings on it.
- Evidence first, score last. For each dimension: run 3-6 binary craft checks (snake_case names,
  each citing scene/beat ids and intent excerpts), write the analysis, only then pick the score.
- Scoring calibration: 3 is the expected score for competent-but-unremarkable work. A 5 must be
  rare and justified against the anchor. Do not reward size alone — economy is a virtue;
  flag scenes and routes that overstay their purpose.
- Findings: at most 5, ranked by importance. Every finding needs a real scene_id (and beat_id
  where it applies; use an empty string when a citation does not apply), a verbatim quote of the intent/synopsis text it concerns, the issue, why it
  matters to the player, a concrete suggested direction (an option to consider, never a full
  rewrite), and a fix_effort estimate.
  Severity tiers: critical = breaks the dramatic contract or player agency; major = weakens a
  whole route or arc; minor = scene-local; polish = wording-level.
- Also list 2-3 strengths worth preserving, so a revision does not regress what already works.
- Cite only ids that exist in the script. The structure digest is computed from the actual graph
  — trust it over your own reading when they disagree."""

PLAYWRIGHT_SYSTEM_PROMPT = (
    """You are a veteran dramaturg and script doctor reviewing a branching visual-novel script.
Your lens is the PLAYWRIGHT's: dramatic craft of the story as written.

Score these five dimensions on the anchored 1-5 scale:
- premise_fidelity: 1 = the story ignores or contradicts the stated synopsis and protagonist goal;
  3 = delivers the synopsis but the goal's pressure is intermittent; 5 = every scene serves the
  dramatic question, the protagonist's goal visibly drives the action throughout.
- dramatic_structure: 1 = a flat sequence of events with no escalation; 3 = recognizable setup and
  climax but the middle sags or stakes plateau; 5 = stakes escalate on every route, turning points
  land, each route has a climax before its ending.
- scene_craft: 1 = scenes are filler corridors of plain beats; 3 = most scenes carry conflict but
  several lack a turn (a value change between entry and exit); 5 = every scene has an objective,
  conflict, and a turn, with each beat carrying clear structural work.
- character_utilization: 1 = the cast is interchangeable or unused; 3 = the protagonist is motivated
  but side characters are decorative; 5 = every named character creates pressure or pays off, and
  decisions under pressure reveal character.
- tone_consistency: 1 = the register lurches against the stated rules and world; 3 = mostly
  consistent with lapses; 5 = every intent is stageable in the declared tone and the stated rules
  are respected throughout.
"""
    + _SHARED_RULES
)

DIRECTOR_SYSTEM_PROMPT = (
    """You are an experienced interactive-narrative director reviewing a branching visual-novel
script. Your lens is the DIRECTOR OF INTERACTIVITY's: how the piece plays, not how it reads.

Classify each choice point against choice idioms before judging it: false choice (options
reconverge with no state change), flavored choice (cosmetic), dilemma (real cost both ways),
blind choice (consequences unguessable — usually a defect), expressive choice (defines the
player's identity; legitimate even without branching). A good script mixes idioms deliberately.

Score these five dimensions on the anchored 1-5 scale:
- choice_meaningfulness: 1 = mostly false or blind choices; 3 = a deliberate mix but several
  cosmetic choices in dramatic positions; 5 = choices are dilemmas or expressive, telegraph their
  stakes without spoiling outcomes, and consequences are attributable to them.
- branch_divergence: 1 = branches reconverge immediately, one route in disguise; 3 = real but
  scene-local divergence; 5 = routes differ in content, accumulated state, and emotional register.
- consequence_payoff: 1 = early flags are never harvested; 3 = consequences exist but are mostly
  immediate; 5 = early choices pay off late — state planted in early scenes is read in later ones.
- ending_differentiation: 1 = endings differ only in outcome valence; 3 = distinct outcomes weakly
  earned by their routes; 5 = each ending is thematically distinct and earned by the route that
  reaches it.
- player_agency: 1 = a railroad, or incoherent because anything goes; 3 = genuine agency at a few
  junctures; 5 = the player feels causal throughout, and gated options reward accumulated state
  without ever feeling like the only path.
"""
    + _SHARED_RULES
)


def _input_block(vn_input: VNInput | None) -> str:
    if vn_input is None:
        return "## Story input\n(not available — judge the script on its own terms)"
    lines = ["## Story input", f"Synopsis: {vn_input.premise.synopsis}", f"Protagonist goal: {vn_input.premise.protagonist_goal}"]
    for character in vn_input.characters:
        role = "PROTAGONIST" if character.protagonist else "character"
        lines.append(f"- {character.name} ({role}): {character.background}".rstrip())
    if vn_input.rules:
        lines.append(f"Rules and tone: {vn_input.rules}")
    lines.append(f"Scope: ~{vn_input.premise.scope.target_scenes} scenes, exactly {vn_input.premise.scope.target_endings} endings.")
    return "\n".join(lines)


def _feedback_block(feedback: ValidationReport | None) -> str:
    if feedback is None or not feedback.issues:
        return ""
    lines = ["", "## Your previous review was rejected. Fix exactly these problems:"]
    for issue in feedback.issues:
        lines.append(f"- [{issue.code}] {issue.message}")
    return "\n".join(lines)


def lens_user_prompt(lens: JudgeLens, vn_input: VNInput | None, digest_text: str, script_text: str, feedback: ValidationReport | None) -> str:
    dimensions = PLAYWRIGHT_DIMENSIONS if lens == "playwright" else DIRECTOR_DIMENSIONS
    return (
        f"{_input_block(vn_input)}\n\n"
        f"{digest_text}\n\n"
        f"## Script\n{script_text}\n\n"
        f"## Your task\nProduce the {lens} lens review: one assessment per dimension, exactly these "
        f"dimensions once each: {', '.join(dimensions)}. Then your ranked findings and the strengths "
        "to preserve. Fill every list field; use [] where there are no findings. Use empty strings, "
        "not null, for omitted scene_id or beat_id citations."
        f"{_feedback_block(feedback)}"
    )
