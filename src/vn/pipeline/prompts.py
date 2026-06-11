"""All generation-pipeline prompt text. Tests must never assert on this wording (it changes often).

Output shape is enforced by structured outputs (the processor passes the stage's model
to the provider), so prompts describe intent, not JSON syntax."""

from src.models.vn.input import VNInput
from src.models.vn.pipeline import SceneOutlineItem, ScriptOutline
from src.models.vn.script import Scene
from src.models.vn.validation import ValidationReport

SYSTEM_PROMPT = """You are a narrative architect for branching visual novels.
You design structural skeletons only: scene graphs, beats, choices, checks, state variables.
You never write prose — every 'intent' field is a terse description of what happens, not narration.

Core rules of the format you produce:
- The story is a graph of beats (types: plain, check, choice, ending) grouped into scenes.
- A scene has exactly one entry beat and one or more exit nodes (a beat with exit_edges, exit "open", or an ending beat).
- Every scene needs an objective, active pressure/conflict, and a turn: the situation at exit must be meaningfully changed from entry.
- Every beat must do new structural work: pressure, evidence, commitment, reversal, cost, or route differentiation. Avoid recap-only beats.
- Choices route between beats inside one scene; scene changes happen only at exit nodes.
- Guarded (state-gated) options must be additive: every scene keeps an ungated path from entry to an exit.
- Both outcomes of every check must lead somewhere meaningful and visibly different. If success and failure would do the same thing, use a plain beat instead.
- State variables are declared once: flags, bounded counters, or enums. Effects attach to beats only.
- Endings are explicit terminal beats with an ending_id.
Make every branch interesting in a different way; choices must have consequences through state or clearly differentiated scene content."""


def _input_block(vn_input: VNInput) -> str:
    lines = ["## Story input", f"Synopsis: {vn_input.premise.synopsis}", f"Protagonist goal: {vn_input.premise.protagonist_goal}"]
    for character in vn_input.characters:
        role = "PROTAGONIST" if character.protagonist else "character"
        lines.append(f"- {character.name} ({role}): {character.background} {character.appearance}".rstrip())
    if vn_input.setting.world_description:
        lines.append(f"World: {vn_input.setting.world_description}")
    if vn_input.setting.anchors:
        lines.append(f"Key places: {', '.join(vn_input.setting.anchors)}")
    if vn_input.rules:
        lines.append(f"Rules and tone: {vn_input.rules}")
    lines.append(f"Scope: aim for about {vn_input.premise.scope.target_scenes} scenes (more is fine if the story needs them) and exactly {vn_input.premise.scope.target_endings} endings.")
    return "\n".join(lines)


def _feedback_block(feedback: ValidationReport | None) -> str:
    if feedback is None or not feedback.issues:
        return ""
    lines = ["", "## Your previous attempt failed validation. Fix exactly these problems:"]
    for issue in feedback.issues:
        location = " ".join(part for part in [f"scene={issue.scene_id}" if issue.scene_id else "", f"beat={issue.beat_id}" if issue.beat_id else ""] if part)
        lines.append(f"- [{issue.code}] {location} {issue.message}".replace("  ", " "))
    return "\n".join(lines)


def outline_user_prompt(vn_input: VNInput, feedback: ValidationReport | None) -> str:
    return (
        f"{_input_block(vn_input)}\n\n"
        "Produce a scene-level outline of the whole story. For each scene give: a unique snake_case id "
        "(prefix sc_), an intent (one sentence, phrased so it can double as a choice option), a synopsis "
        "(2-4 sentences of what structurally happens: objective, pressure/conflict, turn, and any consequence "
        "that should be paid off later), an exit_mode ('directed' = authored continuation, "
        "'open' = the player picks the next scene from whatever is available, 'ending' = the scene contains "
        "ending beats), and ending_ids (only for ending scenes; unique snake_case ids prefixed end_). "
        "Choose a start_scene. Scenes reached from open exits must read sensibly regardless of where the player came from. "
        "Plan at least one early player action whose state consequence is read in a later scene, and avoid outline scenes "
        "whose only job is restating information the player already has."
        f"{_feedback_block(feedback)}"
    )


def scene_graph_user_prompt(vn_input: VNInput, outline: ScriptOutline, item: SceneOutlineItem, feedback: ValidationReport | None) -> str:
    other_scenes = "\n".join(f"- {scene.id}: {scene.synopsis}" for scene in outline.scenes)
    return (
        f"{_input_block(vn_input)}\n\n"
        f"## Full outline\n{other_scenes}\n\n"
        f"## Your task: build the beat mini-graph for scene '{item.id}'\n"
        f"Intent: {item.intent}\nSynopsis: {item.synopsis}\nExit mode: {item.exit_mode}\n"
        f"Required ending ids in this scene: {item.ending_ids or 'none'}\n\n"
        "Emit the simplified scene graph object. Use this exact scene id. Beat ids must be globally unique "
        "across the eventual script: prefix them with b_<scene_stem>_ rather than generic names likely to recur. "
        "Create an entry beat, in-scene routing, and exits matching the exit mode. Every beat must create new pressure, "
        "evidence, commitment, reversal, cost, or route texture; do not add recap beats that only summarize known facts.\n"
        "Exit-mode requirements:\n"
        "- open: include at least one plain beat whose route is exit:open.\n"
        "- directed: include at least one plain beat whose route is edges:<scene_id>@<priority>|..., with unique integer priorities.\n"
        "- ending: include ending beats for exactly the required ending_ids and no other ending ids.\n"
        "For plain beats, set route to exactly one of: next:<beat_id>, exit:open, or "
        "edges:<scene_id>@<priority>|<scene_id>@<priority>. For check beats, set check_difficulty around 10-14 "
        "plus check_success/check_failure, and make success and failure target different beats with different "
        "immediate consequences. If both outcomes would reconverge immediately without a distinct beat, make it a "
        "plain beat instead. For choice beats, options must target distinct beats, so each option creates different "
        "content now and can optionally reconverge later. For ending beats, fill ending_id. Leave irrelevant "
        "string fields empty, irrelevant numeric fields 0, and irrelevant lists empty. Use extension_domain only on "
        "1-2 high-tension beats. Do not gate the only path forward."
        f"{_feedback_block(feedback)}"
    )


def mechanics_user_prompt(vn_input: VNInput, outline: ScriptOutline, scenes: list[Scene], feedback: ValidationReport | None) -> str:
    drafted = "\n\n".join(scene.model_dump_json(exclude_none=True) for scene in scenes)
    return (
        f"{_input_block(vn_input)}\n\n"
        f"## Drafted scenes (structurally valid, mechanics still missing)\n{drafted}\n\n"
        f"Title: {outline.title}. Start scene: {outline.start_scene}.\n\n"
        "Produce ONLY a simplified mechanics patch over the drafted scenes — never re-emit scenes, beats, or routing. "
        "Reference existing ids exactly; option_index and edge_index are 0-based positions in the drafted lists.\n"
        "You cannot add, remove, rename, or duplicate scenes, beats, routes, or endings in this stage. If a consequence "
        "needs more weight, use effects, guards, prerequisites, and modifiers on existing ids.\n"
        "Use this DSL inside string fields:\n"
        "- state_vars: \"flag name=false\", \"counter trust max=3 initial=1\", \"enum mood values=calm|alert initial=calm\".\n"
        "- effects: \"trust += 1\", \"trust -= 1\", \"lamp_color = white\", \"injured = true\".\n"
        "- guards/prerequisites: only \"trust >= 2\", \"trust <= 1\", \"lamp_color == white\", \"flag_name == true\", "
        "\"flag_name == false\", \"visited:b_ledger\", or \"not visited:sc_town\". Never write bare flags like "
        "\"logbook_read\" or bare negation like \"not logbook_read\".\n"
        "- check modifiers: \"trust >= 2 => +2\" or \"visited:b_alarm => -1\".\n"
        "Fill every patch list; use [] where there is nothing to patch. For scene_patches, forced = -1 means not forced.\n"
        "1. state_vars: declare a small set of flags / bounded counters / enums that capture meaningful consequences.\n"
        "2. beat_effects: attach DSL effects to beats where things change.\n"
        "3. option_guards / exit_edge_guards: gate choices and exits where state should matter — guarded options "
        "must stay additive (never the only path), and every prominent player choice should either write a variable "
        "or route to a beat whose consequence is read later.\n"
        "4. scene_patches: prerequisites (and visited() conditions) control when scenes appear at open exits; "
        "set repeatable / forced only where the story needs it.\n"
        "5. check_modifiers: give checks state-conditional modifiers referencing your vars, but do not use modifiers "
        "to decorate inert checks; a check should already have distinct success and failure consequences in the draft.\n"
        "Every variable must be both written somewhere and read somewhere, with counters read at meaningful thresholds "
        "before they feel like bookkeeping. The state must make every ending reachable."
        f"{_feedback_block(feedback)}"
    )
