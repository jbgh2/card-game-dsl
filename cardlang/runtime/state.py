"""Runtime game state and the evaluation/execution context.

`RuntimeState` is the live, mutable world: zones holding cards and a stack of
scope frames holding state variables. `Ctx` is the (immutable) context threaded
through expression evaluation and statement execution — the acting player, the
local bindings (lambda/comprehension/for-each binders), and the bound
`outcome` / `action` / mechanic state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

from cardlang.ast import nodes as n
from cardlang.runtime.values import Card, Player, Seating


class IllegalMove(Exception):
    """Raised by the `error(...)` fallback — the attempted move is illegal."""


class Zone:
    """An ordered, mutable collection of cards."""

    def __init__(self, cards: Iterable[Card] = ()) -> None:
        self.cards: list[Card] = list(cards)

    def add(self, card: Card) -> None:
        self.cards.append(card)

    def add_all(self, cards: Iterable[Card]) -> None:
        self.cards.extend(cards)

    def remove(self, card: Card) -> None:
        self.cards.remove(card)

    def take_all(self) -> list[Card]:
        taken = self.cards
        self.cards = []
        return taken

    @property
    def empty(self) -> bool:
        return not self.cards

    def __len__(self) -> int:
        return len(self.cards)


class ZoneStore:
    """All zone instances. Singleton zones map to one Zone; an indexed family
    (`hand[player]`) maps to one Zone per player."""

    def __init__(self, decls: Iterable[n.ZoneDecl], players: tuple[Player, ...]) -> None:
        self.singles: dict[str, Zone] = {}
        self.families: dict[str, dict[Player, Zone]] = {}
        for decl in decls:
            if decl.index is None:
                self.singles[decl.name] = Zone()
            else:
                self.families[decl.name] = {p: Zone() for p in players}

    def is_family(self, name: str) -> bool:
        return name in self.families

    def single(self, name: str) -> Zone:
        return self.singles[name]

    def instance(self, name: str, player: Player) -> Zone:
        return self.families[name][player]


class RuntimeState:
    """The live world: zones plus a stack of variable scope frames."""

    def __init__(self, seating: Seating, zones: ZoneStore, rng: random.Random) -> None:
        self.seating = seating
        self.zones = zones
        self.rng = rng
        self.frames: list[dict[str, Any]] = []
        self.indexed: set[str] = set()  # variable names that are per-player
        self.mech_state: list[dict[str, Any]] = []  # active mechanic state (`state.`)
        self.fired_transitions: set[str] = set()  # transition targets reached this iteration
        self.rule_index: dict[str, n.RuleDef] = {}  # rule name -> definition
        self.deck_zone: str = ""  # the Deck-typed zone (initialized full at start)
        self.score_var: str = ""  # the winner's score variable, for traces

    # --- scope frames ---

    def push_frame(self) -> None:
        self.frames.append({})

    def pop_frame(self) -> None:
        self.frames.pop()

    def declare(self, name: str, indexed: bool, value: Any) -> None:
        if indexed:
            self.indexed.add(name)
        self.frames[-1][name] = value

    def _frame_of(self, name: str) -> dict[str, Any]:
        for frame in reversed(self.frames):
            if name in frame:
                return frame
        raise KeyError(f"variable '{name}' not in scope")

    def get(self, name: str) -> Any:
        return self._frame_of(name)[name]

    def set(self, name: str, value: Any) -> None:
        self._frame_of(name)[name] = value


@dataclass(frozen=True, slots=True)
class Move:
    """A play move, as inspected by `action.card` / `action.actor` predicates."""

    card: Card
    actor: Player


# A chooser picks a subset from a candidate list (random playout: uniform).
Chooser = Callable[[Player, list[Card], int], list[Card]]


@dataclass(frozen=True, slots=True)
class Ctx:
    """Immutable evaluation/execution context threaded through the interpreter."""

    rs: RuntimeState
    chooser: Chooser
    tracer: Callable[[str, Any], None] | None = None
    locals: dict[str, Any] = field(default_factory=dict)
    current_player: Player | None = None
    current_phase: n.Phase | None = None
    outcome: Player | None = None
    action: Move | None = None
    active_rules: tuple[n.RuleDef, ...] = ()

    def trace(self, event: str, data: Any) -> None:
        if self.tracer is not None:
            self.tracer(event, data)

    def with_local(self, name: str, value: Any) -> "Ctx":
        return replace(self, locals={**self.locals, name: value})

    def acting_as(self, player: Player) -> "Ctx":
        return replace(self, current_player=player)

    def in_phase(self, phase: n.Phase) -> "Ctx":
        return replace(self, current_phase=phase)

    def with_outcome(self, player: Player) -> "Ctx":
        return replace(self, outcome=player)

    def with_action(self, action: Move) -> "Ctx":
        return replace(self, action=action)

    def with_rules(self, rules: tuple[n.RuleDef, ...]) -> "Ctx":
        return replace(self, active_rules=rules)
