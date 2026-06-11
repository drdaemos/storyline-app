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
- Choices route between beats inside one scene; scene changes happen only at exit nodes.
- Guarded (state-gated) options must be additive: every scene keeps an ungated path from entry to an exit.
- Both outcomes of every check must lead somewhere meaningful (failure reroutes, never dead-ends).
- State variables are declared once: flags, bounded counters, or enums. Effects attach to beats only.
- Endings are explicit terminal beats with an ending_id.
Make every branch interesting in a different way; choices must have consequences through state."""


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
        "(2-4 sentences of what structurally happens), an exit_mode ('directed' = authored continuation, "
        "'open' = the player picks the next scene from whatever is available, 'ending' = the scene contains "
        "ending beats), and ending_ids (only for ending scenes; unique snake_case ids prefixed end_). "
        "Choose a start_scene. Scenes reached from open exits must read sensibly regardless of where the player came from."
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
        "Emit the full Scene object: unique snake_case beat ids (prefix b_), an entry beat, 3-8 beats with "
        "in-scene routing (choices may reroute and reconverge), and exits matching the exit mode "
        "(directed = exit_edges to other outline scene ids; open = exit \"open\"). You may include check "
        "beats (difficulty around 10-14) and mark 1-2 high-tension beats as extension points "
        "(extension.deeper_domain = what deeper narration may cover). Leave guards, effects, and check "
        "modifiers minimal or empty — a later pass adds state mechanics. Do not gate the only path forward."
        f"{_feedback_block(feedback)}"
    )


def mechanics_user_prompt(vn_input: VNInput, outline: ScriptOutline, scenes: list[Scene], feedback: ValidationReport | None) -> str:
    drafted = "\n\n".join(scene.model_dump_json(exclude_none=True) for scene in scenes)
    return (
        f"{_input_block(vn_input)}\n\n"
        f"## Drafted scenes (structurally valid, mechanics still missing)\n{drafted}\n\n"
        f"Title: {outline.title}. Start scene: {outline.start_scene}.\n\n"
        "Produce ONLY a mechanics patch over the drafted scenes — never re-emit scenes, beats, or routing. "
        "Reference existing ids exactly; option_index and edge_index are 0-based positions in the drafted lists.\n"
        "1. state_vars: declare flags / bounded counters / enums that capture meaningful consequences.\n"
        "2. beat_effects: attach effects to beats where things change.\n"
        "3. option_guards / exit_edge_guards: gate choices and exits where state should matter — "
        "guarded options must stay additive (never the only path).\n"
        "4. scene_patches: prerequisites (and visited() conditions) control when scenes appear at open exits; "
        "set repeatable / forced only where the story needs it.\n"
        "5. check_modifiers: give checks state-conditional modifiers referencing your vars.\n"
        "Every variable must be both written somewhere and read somewhere. The state must make every ending reachable."
        f"{_feedback_block(feedback)}"
    )
