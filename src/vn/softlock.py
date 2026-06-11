"""Softlock checker: forward exploration of (beat graph x reachable states).

Walks forward from the initial state only (no full domain-product enumeration).
Termination is by construction: visited bits are monotone, counters bounded,
enums finite — plus an explicit explored-node budget as a safety net.

Flags:
- dead_end: a reachable node with no successors that is not an ending
  (all choice options gated off, no eligible exit edge, empty open-exit pool);
- softlock: a reachable node from which no ending beat is reachable;
- equal_forced_priorities: two available scenes tie on `forced` at an open exit
  (generation-time error per spec, detectable only with state);
- unreached_ending (warning): a declared ending no walk path reaches;
- state_space_budget_exceeded (warning): the walk gave up — the script is
  unverified rather than broken, so this must not hard-fail a gate.

Node identity tracks only the visited ids that can influence routing (scene ids
for once-only pools, plus ids referenced by visited() guards). Unreferenced beat
ids would otherwise multiply node identities exponentially on reconverging paths
without changing any routing decision.

Extension micro-loops are outcome-neutral, always-escapable self-loops and are
ignored. Directed exit edges are authored continuations: they respect only their
guard, not the target's prerequisites/once-only (those govern the open-exit pool).
"""

from collections import deque
from dataclasses import dataclass

from src.models.vn.script import (
    Beat,
    CheckBeat,
    ChoiceBeat,
    EndingBeat,
    Guard,
    PlainBeat,
    Scene,
    Script,
    StateValue,
    VisitedCondition,
)
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.conditions import StateMap, evaluate_guard
from src.vn.effects import apply_effects, declarations_by_name, initial_state

DEFAULT_NODE_BUDGET = 100_000

StateKey = tuple[tuple[str, StateValue], ...]


@dataclass(frozen=True)
class WalkNode:
    """About to execute `beat_id` with this state and visited set."""

    beat_id: str
    state: StateKey
    visited: frozenset[str]


def _to_key(state: StateMap) -> StateKey:
    return tuple(sorted(state.items()))


def _to_map(key: StateKey) -> StateMap:
    return dict(key)


class SoftlockChecker:
    def __init__(self, script: Script, max_nodes: int = DEFAULT_NODE_BUDGET) -> None:
        self.script = script
        self.max_nodes = max_nodes
        self.declarations = declarations_by_name(script.state_vars)
        self.scenes_by_id: dict[str, Scene] = {scene.id: scene for scene in script.scenes}
        self.beats_by_id: dict[str, Beat] = {}
        self.scene_of_beat: dict[str, str] = {}
        for scene in script.scenes:
            for beat in scene.beats:
                self.beats_by_id[beat.id] = beat
                self.scene_of_beat[beat.id] = scene.id
        self.tracked_ids = self._tracked_ids(script)

    def check(self) -> ValidationReport:
        issues: list[ValidationIssue] = []
        start_scene = self.scenes_by_id[self.script.start_scene]
        start = WalkNode(beat_id=start_scene.entry_beat, state=_to_key(initial_state(self.script.state_vars)), visited=frozenset())

        successors: dict[WalkNode, list[WalkNode]] = {}
        terminals: set[WalkNode] = set()
        reached_endings: set[str] = set()
        budget_exceeded = False

        frontier: deque[WalkNode] = deque([start])
        seen: set[WalkNode] = {start}
        while frontier:
            if len(seen) > self.max_nodes:
                budget_exceeded = True
                issues.append(
                    ValidationIssue(
                        code="state_space_budget_exceeded",
                        severity="warning",
                        message=f"explored more than {self.max_nodes} (beat, state) nodes; softlock freedom could not be fully verified",
                    )
                )
                break
            node = frontier.popleft()
            node_successors, node_issues, ending_id = self._expand(node)
            successors[node] = node_successors
            issues.extend(node_issues)
            if ending_id is not None:
                terminals.add(node)
                reached_endings.add(ending_id)
            for successor in node_successors:
                if successor not in seen:
                    seen.add(successor)
                    frontier.append(successor)

        if not budget_exceeded:
            issues.extend(self._softlock_issues(successors, terminals))
            issues.extend(self._unreached_ending_issues(reached_endings))

        return ValidationReport(issues=issues)

    # --- expansion -----------------------------------------------------------

    def _tracked_ids(self, script: Script) -> frozenset[str]:
        """Visited ids that can influence routing: scene ids (once-only pools and prerequisites)
        plus everything referenced by a visited() condition in a routing guard."""
        ids = {scene.id for scene in script.scenes}
        for scene in script.scenes:
            ids.update(self._guard_refs(scene.prerequisites))
            for beat in scene.beats:
                if isinstance(beat, ChoiceBeat):
                    for option in beat.options:
                        ids.update(self._guard_refs(option.guard))
                elif isinstance(beat, PlainBeat) and beat.exit_edges is not None:
                    for edge in beat.exit_edges:
                        ids.update(self._guard_refs(edge.guard))
        return frozenset(ids)

    def _guard_refs(self, guard: Guard) -> set[str]:
        return {condition.visited for condition in guard if isinstance(condition, VisitedCondition)}

    def _expand(self, node: WalkNode) -> tuple[list[WalkNode], list[ValidationIssue], str | None]:
        """Execute one beat: mark visited, apply effects, enumerate all possible successors."""
        beat = self.beats_by_id[node.beat_id]
        visited = node.visited | ({beat.id, self.scene_of_beat[beat.id]} & self.tracked_ids)
        state = apply_effects(beat.effects, _to_map(node.state), self.declarations)
        state_key = _to_key(state)

        if isinstance(beat, EndingBeat):
            return [], [], beat.ending_id

        if isinstance(beat, CheckBeat):
            targets = [beat.check.on_success, beat.check.on_failure]
            return [WalkNode(t, state_key, visited) for t in targets], [], None

        if isinstance(beat, ChoiceBeat):
            targets = [option.target for option in beat.options if evaluate_guard(option.guard, state, visited)]
            if not targets:
                return [], [self._dead_end(beat.id, state, "all choice options are gated off")], None
            return [WalkNode(t, state_key, visited) for t in targets], [], None

        return self._expand_plain(beat, state, state_key, visited)

    def _expand_plain(self, beat: PlainBeat, state: StateMap, state_key: StateKey, visited: frozenset[str]) -> tuple[list[WalkNode], list[ValidationIssue], str | None]:
        if beat.next is not None:
            return [WalkNode(beat.next, state_key, visited)], [], None

        if beat.exit_edges is not None:
            eligible = [edge for edge in beat.exit_edges if evaluate_guard(edge.guard, state, visited)]
            if not eligible:
                return [], [self._dead_end(beat.id, state, "no exit edge guard matches state")], None
            best = max(eligible, key=lambda edge: edge.priority)
            target_scene = self.scenes_by_id[best.target_scene]
            return [WalkNode(target_scene.entry_beat, state_key, visited)], [], None

        # open exit: query the pool
        available = [scene for scene in self.script.scenes if self._is_available(scene, state, visited)]
        if not available:
            return [], [self._dead_end(beat.id, state, "open exit with an empty scene pool")], None

        forced = [scene for scene in available if scene.forced is not None]
        if forced:
            top_priority = max(scene.forced for scene in forced if scene.forced is not None)
            top = [scene for scene in forced if scene.forced == top_priority]
            if len(top) > 1:
                issue = ValidationIssue(
                    code="equal_forced_priorities",
                    beat_id=beat.id,
                    scene_id=self.scene_of_beat[beat.id],
                    state=dict(state),
                    message=f"open exit '{beat.id}': scenes {[scene.id for scene in top]} are simultaneously available with equal forced priority {top_priority}",
                )
                return [WalkNode(scene.entry_beat, state_key, visited) for scene in top], [issue], None
            return [WalkNode(top[0].entry_beat, state_key, visited)], [], None

        return [WalkNode(scene.entry_beat, state_key, visited) for scene in available], [], None

    def _is_available(self, scene: Scene, state: StateMap, visited: frozenset[str]) -> bool:
        if scene.id in visited and not scene.repeatable:
            return False
        return evaluate_guard(scene.prerequisites, state, visited)

    def _dead_end(self, beat_id: str, state: StateMap, reason: str) -> ValidationIssue:
        return ValidationIssue(
            code="dead_end",
            beat_id=beat_id,
            scene_id=self.scene_of_beat[beat_id],
            state=dict(state),
            message=f"beat '{beat_id}': {reason}",
        )

    # --- co-reachability -------------------------------------------------------

    def _softlock_issues(self, successors: dict[WalkNode, list[WalkNode]], terminals: set[WalkNode]) -> list[ValidationIssue]:
        predecessors: dict[WalkNode, list[WalkNode]] = {}
        for node, node_successors in successors.items():
            for successor in node_successors:
                predecessors.setdefault(successor, []).append(node)

        can_finish: set[WalkNode] = set(terminals)
        frontier = deque(terminals)
        while frontier:
            node = frontier.popleft()
            for predecessor in predecessors.get(node, []):
                if predecessor not in can_finish:
                    can_finish.add(predecessor)
                    frontier.append(predecessor)

        # One witness per beat to avoid flooding the report.
        flagged_beats: set[str] = set()
        issues: list[ValidationIssue] = []
        for node in successors:
            if node not in can_finish and node.beat_id not in flagged_beats:
                flagged_beats.add(node.beat_id)
                issues.append(
                    ValidationIssue(
                        code="softlock",
                        beat_id=node.beat_id,
                        scene_id=self.scene_of_beat[node.beat_id],
                        state=dict(_to_map(node.state)),
                        message=f"beat '{node.beat_id}' is reachable in a state from which no ending can be reached",
                    )
                )
        return issues

    def _unreached_ending_issues(self, reached_endings: set[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for scene in self.script.scenes:
            for beat in scene.beats:
                if isinstance(beat, EndingBeat) and beat.ending_id not in reached_endings:
                    issues.append(
                        ValidationIssue(
                            code="unreached_ending",
                            severity="warning",
                            scene_id=scene.id,
                            beat_id=beat.id,
                            message=f"ending '{beat.ending_id}' is never reached from the initial state",
                        )
                    )
        return issues


def check_softlocks(script: Script, max_nodes: int = DEFAULT_NODE_BUDGET) -> ValidationReport:
    """Run the full softlock walk. Assumes the script already passed validate_script."""
    return SoftlockChecker(script, max_nodes=max_nodes).check()
