"""VNEngine: the deterministic runtime state machine.

Plays a validated script with no LLM, no I/O, and no persistence: it takes a
Script plus a serializable VNRuntimeState and advances it in response to player
actions. Narration sits entirely outside (src/vn/narrator.py) and can never
change an outcome here.

Execution model per beat: enter (mark visited, apply effects) -> optional
extension offer (go deeper / proceed) -> resolve routing. Plain chains, checks,
directed exits, and forced scenes run automatically; the engine stops only when
the player must act (a choice, an open-exit scene selection presented as a
choice, or an extension offer) or the story ends.
"""

from src.models.vn.runtime import (
    BeatEntered,
    CheckResolved,
    ChoiceMade,
    EndingReached,
    EngineEvent,
    EngineView,
    Pending,
    PendingOption,
    SceneEntered,
    VNAction,
    VNRuntimeState,
    WentDeeper,
)
from src.models.vn.script import (
    Beat,
    CheckBeat,
    ChoiceBeat,
    EndingBeat,
    PlainBeat,
    Scene,
    Script,
)
from src.vn.checks import PlaceholderRollResolver, RollResolver, resolve_check
from src.vn.conditions import evaluate_guard
from src.vn.effects import apply_effects, declarations_by_name, initial_state


class VNRuntimeError(Exception):
    """Invalid action or a script hole the validator should have caught."""


class VNEngine:
    def __init__(self, script: Script, state: VNRuntimeState, roll_resolver: RollResolver | None = None) -> None:
        self.script = script
        self.state = state
        self.roll_resolver: RollResolver = roll_resolver if roll_resolver is not None else PlaceholderRollResolver(seed=state.seed, skip=state.roll_count)
        self.declarations = declarations_by_name(script.state_vars)
        self.scenes_by_id: dict[str, Scene] = {scene.id: scene for scene in script.scenes}
        self.beats_by_id: dict[str, Beat] = {}
        self.scene_of_beat: dict[str, str] = {}
        for scene in script.scenes:
            for beat in scene.beats:
                self.beats_by_id[beat.id] = beat
                self.scene_of_beat[beat.id] = scene.id

    @classmethod
    def new(cls, script: Script, seed: int = 0, roll_resolver: RollResolver | None = None) -> "VNEngine":
        start_scene = next(scene for scene in script.scenes if scene.id == script.start_scene)
        state = VNRuntimeState(vars=initial_state(script.state_vars), current_beat=start_scene.entry_beat, seed=seed)
        return cls(script, state, roll_resolver)

    # --- public API -----------------------------------------------------------

    def start(self) -> list[EngineEvent]:
        """Run from the initial state to the first pending input (or ending). Call once on a fresh session."""
        if self.state.visited or self.state.phase != "pre":
            raise VNRuntimeError("session already started")
        start_scene = self.scenes_by_id[self.script.start_scene]
        events: list[EngineEvent] = [SceneEntered(scene_id=start_scene.id, intent=start_scene.intent)]
        events.extend(self._run())
        return events

    def advance(self, action: VNAction) -> list[EngineEvent]:
        if self.state.status == "ended":
            raise VNRuntimeError("story has ended")
        if self.state.phase == "pre":
            raise VNRuntimeError("session not started; call start() first")

        beat = self.beats_by_id[self.state.current_beat]
        if self.state.phase == "extension":
            events = self._advance_extension(beat, action)
        else:
            events = self._advance_pending_choice(beat, action)
        self.state.action_log.append(action)
        return events

    def view(self) -> EngineView:
        beat = self.beats_by_id[self.state.current_beat]
        pending: Pending | None = None
        if self.state.status == "running":
            if self.state.phase == "extension":
                deeper_domain = beat.extension.deeper_domain if beat.extension is not None else ""
                pending = Pending(kind="extension", prompt=beat.intent, deeper_domain=deeper_domain)
            elif self.state.phase == "resolve":
                options = self._pending_options(beat)
                pending = Pending(kind="choice", prompt=beat.intent, options=[PendingOption(index=index, intent=intent) for index, (intent, _) in enumerate(options)])
        return EngineView(
            status=self.state.status,
            scene_id=self.scene_of_beat[self.state.current_beat],
            beat_id=self.state.current_beat,
            pending=pending,
            ending_id=self.state.ending_id,
            vars=dict(self.state.vars),
            visited=sorted(self.state.visited),
        )

    # --- action handling --------------------------------------------------------

    def _advance_extension(self, beat: Beat, action: VNAction) -> list[EngineEvent]:
        if action.type == "go_deeper":
            deeper_domain = beat.extension.deeper_domain if beat.extension is not None else ""
            return [WentDeeper(beat_id=beat.id, deeper_domain=deeper_domain)]
        if action.type == "proceed":
            self.state.phase = "resolve"
            return self._run()
        raise VNRuntimeError(f"action '{action.type}' is invalid at an extension point")

    def _advance_pending_choice(self, beat: Beat, action: VNAction) -> list[EngineEvent]:
        options = self._pending_options(beat)
        if action.type != "choose":
            raise VNRuntimeError(f"action '{action.type}' is invalid while a choice is pending")
        if action.option_index is None or not (0 <= action.option_index < len(options)):
            raise VNRuntimeError(f"option_index {action.option_index} out of range (0..{len(options) - 1})")
        intent, target = options[action.option_index]
        events: list[EngineEvent] = [ChoiceMade(intent=intent)]
        if isinstance(beat, ChoiceBeat):
            self._goto(target)
        else:  # open exit: target is a scene id
            events.append(self._enter_scene(target))
        events.extend(self._run())
        return events

    def _pending_options(self, beat: Beat) -> list[tuple[str, str]]:
        """(intent, target) pairs for whatever input is pending. Open-exit scene selection
        is presented exactly like a beat choice (spec: never exposed as scene selection)."""
        if isinstance(beat, ChoiceBeat):
            return [(option.intent, option.target) for option in beat.options if evaluate_guard(option.guard, self.state.vars, self.state.visited)]
        if isinstance(beat, PlainBeat) and beat.exit == "open":
            return [(scene.intent, scene.id) for scene in self._available_scenes()]
        raise VNRuntimeError(f"beat '{beat.id}' has no pending choice")

    # --- the run loop -------------------------------------------------------------

    def _run(self) -> list[EngineEvent]:
        """Execute beats until player input is needed or the story ends."""
        events: list[EngineEvent] = []
        while self.state.status == "running":
            beat = self.beats_by_id[self.state.current_beat]

            if self.state.phase == "pre":
                self.state.visited |= {beat.id, self.scene_of_beat[beat.id]}
                self.state.vars = apply_effects(beat.effects, self.state.vars, self.declarations)
                events.append(BeatEntered(scene_id=self.scene_of_beat[beat.id], beat_id=beat.id, intent=beat.intent))
                self.state.phase = "extension" if beat.extension is not None else "resolve"
                continue

            if self.state.phase == "extension":
                break  # waiting for go_deeper / proceed

            if isinstance(beat, EndingBeat):
                self.state.status = "ended"
                self.state.ending_id = beat.ending_id
                events.append(EndingReached(ending_id=beat.ending_id, intent=beat.intent))
                break

            if isinstance(beat, CheckBeat):
                roll = self.roll_resolver.roll()
                self.state.roll_count += 1
                success, total = resolve_check(beat.check, roll, self.state.vars, self.state.visited)
                events.append(CheckResolved(beat_id=beat.id, roll=roll, difficulty=beat.check.difficulty, modifier_total=total, success=success))
                self._goto(beat.check.on_success if success else beat.check.on_failure)
                continue

            if isinstance(beat, ChoiceBeat):
                break  # waiting for choose

            assert isinstance(beat, PlainBeat)
            if beat.next is not None:
                self._goto(beat.next)
                continue
            if beat.exit_edges is not None:
                eligible = [edge for edge in beat.exit_edges if evaluate_guard(edge.guard, self.state.vars, self.state.visited)]
                if not eligible:
                    raise VNRuntimeError(f"beat '{beat.id}': no exit edge guard matches state (validator gap)")
                best = max(eligible, key=lambda edge: edge.priority)
                events.append(self._enter_scene(best.target_scene))
                continue

            # open exit
            available = self._available_scenes()
            if not available:
                raise VNRuntimeError(f"beat '{beat.id}': open exit with an empty scene pool (validator gap)")
            forced = [scene for scene in available if scene.forced is not None]
            if forced:
                best_scene = max(forced, key=lambda scene: scene.forced or 0)
                events.append(self._enter_scene(best_scene.id))
                continue
            break  # waiting for the player to pick a scene (as an ordinary choice)

        return events

    def _available_scenes(self) -> list[Scene]:
        return [
            scene
            for scene in self.script.scenes
            if (scene.id not in self.state.visited or scene.repeatable) and evaluate_guard(scene.prerequisites, self.state.vars, self.state.visited)
        ]

    def _enter_scene(self, scene_id: str) -> SceneEntered:
        scene = self.scenes_by_id[scene_id]
        self._goto(scene.entry_beat)
        return SceneEntered(scene_id=scene.id, intent=scene.intent)

    def _goto(self, beat_id: str) -> None:
        self.state.current_beat = beat_id
        self.state.phase = "pre"
