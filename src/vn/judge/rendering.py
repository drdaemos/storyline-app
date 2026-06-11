"""Deterministic judge inputs: a readable screenplay-like rendering of the script
plus a computed branch/flag digest. Judges reconstruct graph structure poorly from
raw JSON, so both are produced in code and fed to every lens pass."""

from src.models.vn.judge import ChoiceBeatDigest, ScriptDigest, StateVarUsage
from src.models.vn.script import (
    Beat,
    CheckBeat,
    ChoiceBeat,
    Condition,
    CounterVar,
    Effect,
    EndingBeat,
    EnumVar,
    Guard,
    PlainBeat,
    Script,
    StateVar,
)


def _condition_text(condition: Condition) -> str:
    if condition.is_var:
        return f"{condition.var} {condition.op} {condition.value}"
    return f"visited({condition.visited}) is {condition.value}"


def _guard_text(guard: Guard) -> str:
    return " AND ".join(_condition_text(condition) for condition in guard)


def _effect_text(effect: Effect) -> str:
    if effect.op == "set":
        return f"set {effect.var} = {effect.value}"
    return f"{effect.op} {effect.var} by {effect.value}"


def _beat_lines(beat: Beat) -> list[str]:
    lines: list[str] = []
    if isinstance(beat, PlainBeat):
        lines.append(f"  ({beat.id}) plain: {beat.intent}")
    elif isinstance(beat, ChoiceBeat):
        lines.append(f"  ({beat.id}) choice: {beat.intent}")
    elif isinstance(beat, CheckBeat):
        lines.append(f"  ({beat.id}) check, difficulty {beat.check.difficulty}: {beat.intent}")
    elif isinstance(beat, EndingBeat):
        lines.append(f"  ({beat.id}) ENDING [{beat.ending_id}]: {beat.intent}")
    if beat.effects:
        lines.append("      effects: " + "; ".join(_effect_text(effect) for effect in beat.effects))
    if beat.extension is not None:
        lines.append(f"      extension point (deeper: {beat.extension.deeper_domain or 'unspecified'})")
    if isinstance(beat, PlainBeat):
        if beat.next is not None:
            lines.append(f"      -> {beat.next}")
        if beat.exit_edges is not None:
            for edge in beat.exit_edges:
                guard = f" [if {_guard_text(edge.guard)}]" if edge.guard else ""
                lines.append(f"      EXIT -> scene {edge.target_scene}{guard} (priority {edge.priority})")
        if beat.exit == "open":
            lines.append("      OPEN EXIT (player picks any available scene)")
    elif isinstance(beat, ChoiceBeat):
        for index, option in enumerate(beat.options, start=1):
            guard = f" [if {_guard_text(option.guard)}]" if option.guard else ""
            lines.append(f"      option {index}: \"{option.intent}\"{guard} -> {option.target}")
    elif isinstance(beat, CheckBeat):
        for modifier in beat.check.modifiers:
            lines.append(f"      modifier {modifier.mod:+d} if {_condition_text(modifier)}")
        lines.append(f"      success -> {beat.check.on_success}; failure -> {beat.check.on_failure}")
    return lines


def _state_var_line(var: StateVar) -> str:
    if isinstance(var, CounterVar):
        return f"- {var.name}: counter 0..{var.max} (initial {var.initial})"
    if isinstance(var, EnumVar):
        return f"- {var.name}: enum {var.values} (initial {var.initial})"
    return f"- {var.name}: flag (initial {var.initial})"


def render_script_text(script: Script) -> str:
    """Screenplay-like linearization: every beat, choice, check, guard, and effect."""
    lines = [f"TITLE: {script.meta.title}", f"PROTAGONIST: {script.meta.protagonist}", f"START SCENE: {script.start_scene}"]
    if script.state_vars:
        lines.append("STATE VARIABLES:")
        lines.extend(_state_var_line(var) for var in script.state_vars)
    for scene in script.scenes:
        lines.append("")
        header = f"SCENE {scene.id}: {scene.intent}"
        flags = []
        if scene.prerequisites:
            flags.append(f"prerequisites: {_guard_text(scene.prerequisites)}")
        if scene.repeatable:
            flags.append("repeatable")
        if scene.forced is not None:
            flags.append(f"forced (priority {scene.forced})")
        if flags:
            header += "  [" + "; ".join(flags) + "]"
        lines.append(header)
        lines.append(f"  entry beat: {scene.entry_beat}")
        for beat in scene.beats:
            lines.extend(_beat_lines(beat))
    return "\n".join(lines)


def build_digest(script: Script) -> ScriptDigest:
    """Computed structural facts: branch shape and state-variable usage."""
    writes: dict[str, int] = {var.name: 0 for var in script.state_vars}
    reads: dict[str, int] = {var.name: 0 for var in script.state_vars}

    def count_guard(guard: Guard) -> None:
        for condition in guard:
            if condition.var is not None and condition.var in reads:
                reads[condition.var] += 1

    choice_digests: list[ChoiceBeatDigest] = []
    plain = choice = check = ending = 0
    ending_ids: list[str] = []
    open_exit_scenes: list[str] = []

    for scene in script.scenes:
        count_guard(scene.prerequisites)
        for beat in scene.beats:
            for effect in beat.effects:
                if effect.var in writes:
                    writes[effect.var] += 1
            if isinstance(beat, PlainBeat):
                plain += 1
                if beat.exit == "open" and scene.id not in open_exit_scenes:
                    open_exit_scenes.append(scene.id)
                for edge in beat.exit_edges or []:
                    count_guard(edge.guard)
            elif isinstance(beat, ChoiceBeat):
                choice += 1
                for option in beat.options:
                    count_guard(option.guard)
                choice_digests.append(
                    ChoiceBeatDigest(
                        scene_id=scene.id,
                        beat_id=beat.id,
                        option_count=len(beat.options),
                        guarded_option_count=sum(1 for option in beat.options if option.guard),
                        distinct_target_count=len({option.target for option in beat.options}),
                    )
                )
            elif isinstance(beat, CheckBeat):
                check += 1
                for modifier in beat.check.modifiers:
                    if modifier.var is not None and modifier.var in reads:
                        reads[modifier.var] += 1
            elif isinstance(beat, EndingBeat):
                ending += 1
                ending_ids.append(beat.ending_id)

    return ScriptDigest(
        scene_count=len(script.scenes),
        beat_count=plain + choice + check + ending,
        plain_beat_count=plain,
        choice_beat_count=choice,
        check_beat_count=check,
        ending_beat_count=ending,
        ending_ids=ending_ids,
        scenes_with_open_exit=open_exit_scenes,
        forced_scenes=[scene.id for scene in script.scenes if scene.forced is not None],
        repeatable_scenes=[scene.id for scene in script.scenes if scene.repeatable],
        choice_beats=choice_digests,
        var_usage=[
            StateVarUsage(name=var.name, type=var.type, writes=writes[var.name], reads=reads[var.name])
            for var in script.state_vars
        ],
        never_read_vars=[name for name, count in reads.items() if count == 0],
        never_written_vars=[name for name, count in writes.items() if count == 0],
    )


def render_digest_text(digest: ScriptDigest) -> str:
    """Digest as prompt text. Marked 'computed' so the judge treats it as ground truth."""
    lines = [
        "STRUCTURE DIGEST (computed from the script graph; treat as ground truth):",
        f"- {digest.scene_count} scenes, {digest.beat_count} beats "
        f"({digest.plain_beat_count} plain, {digest.choice_beat_count} choice, {digest.check_beat_count} check, {digest.ending_beat_count} ending)",
        f"- endings: {', '.join(digest.ending_ids) or 'none'}",
        f"- scenes with open exits: {', '.join(digest.scenes_with_open_exit) or 'none'}",
        f"- forced scenes: {', '.join(digest.forced_scenes) or 'none'}; repeatable: {', '.join(digest.repeatable_scenes) or 'none'}",
    ]
    for item in digest.choice_beats:
        lines.append(
            f"- choice {item.scene_id}/{item.beat_id}: {item.option_count} options, "
            f"{item.guarded_option_count} guarded, {item.distinct_target_count} distinct targets"
        )
    for usage in digest.var_usage:
        warning = ""
        if usage.reads == 0:
            warning = "  (WARNING: written but never read — consequences invisible to the player)"
        elif usage.writes == 0:
            warning = "  (WARNING: read but never written — dead gate)"
        lines.append(f"- var {usage.name} ({usage.type}): {usage.writes} writes, {usage.reads} reads{warning}")
    return "\n".join(lines)
