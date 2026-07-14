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
from cardlang.domains import DomainSources, role_static_members
from cardlang.runtime.values import Card, Player, Seating


class IllegalMove(Exception):
    """Raised by the `error(...)` fallback — the attempted move is illegal."""


class _ProduceSignal(Exception):
    """Carries a `produce`d variant (tag + payloads) up to the define runner or
    the enclosing outcome-declaring phase."""

    def __init__(self, tag: str, payloads: list[Any]) -> None:
        super().__init__(f"produced {tag}")
        self.tag = tag
        self.payloads = payloads


class _ContinueTo(Exception):
    """`continue to <phase>` — unwinds to the enclosing phase body, which resumes
    the phase sequence at the named sibling."""

    def __init__(self, target: str) -> None:
        super().__init__(f"continue to {target}")
        self.target = target


class _SkipHand(Exception):
    """`skip to next hand` — unwinds to the enclosing `repeat until` hand loop,
    which proceeds to its next iteration (after_each still runs)."""


class ChooserAbort(Exception):
    """Raised by a chooser to suspend a playout at a decision point.

    The steppable-adapter seam (e.g. the OpenSpiel adapter): a chooser may abort
    the run instead of returning a choice, carrying the deciding ``player`` and
    the ``legal`` candidates. ``play_game`` attaches the live :class:`RuntimeState`
    as ``rs`` before re-raising, so the caller can inspect the paused world.
    """

    def __init__(self, player: "Player", legal: object) -> None:
        super().__init__("chooser aborted the playout (steppable adapter)")
        self.player = player
        self.legal = legal
        self.rs: "RuntimeState | None" = None


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
    maps to one Zone per index value — per player for `hand[player]`, per team
    for `captured[team]`."""

    def __init__(
        self,
        decls: Iterable[n.ZoneDecl],
        players: tuple[Player, ...],
        teams: tuple[int, ...] = (),
    ) -> None:
        self.singles: dict[str, Zone] = {}
        self.families: dict[str, dict[int, Zone]] = {}
        # The declared library type and index kind per zone, so the observation
        # emitter and info-state builder can look up any zone's projection.
        self.zone_type: dict[str, str] = {}
        self.zone_index: dict[str, str | None] = {}
        for decl in decls:
            self.zone_type[decl.name] = decl.type_ref.name
            self.zone_index[decl.name] = decl.index
            if decl.index is None:
                self.singles[decl.name] = Zone()
            else:
                # The family's key set is the index domain's member set, read
                # from the domain table. The old `teams if index == "team" else
                # players` silently keyed ANY other role by players; the table
                # raises for a role no row covers (resolve rejects those, so
                # reaching it means a row and this site disagree).
                keys = role_static_members(
                    decl.index,
                    DomainSources(suits=(), ranks=(), players=players, teams=teams),
                )
                self.families[decl.name] = {k: Zone() for k in keys}

    def is_family(self, name: str) -> bool:
        return name in self.families

    def single(self, name: str) -> Zone:
        return self.singles[name]

    def instance(self, name: str, key: int) -> Zone:
        return self.families[name][key]

    def locate(self, zone: Zone) -> "tuple[str, Player | None]":
        """The (name, instance-key) of a zone object — the reverse lookup the
        observation emitter needs when a movement holds only the Zone value."""
        for name, z in self.singles.items():
            if z is zone:
                return name, None
        for name, family in self.families.items():
            for key, z in family.items():
                if z is zone:
                    return name, key
        raise KeyError("zone object is not in this store")


class RuntimeState:
    """The live world: zones plus a stack of variable scope frames."""

    def __init__(self, seating: Seating, zones: ZoneStore, rng: random.Random) -> None:
        # Annotated explicitly: `state` and `domains` are now a module cycle
        # (domains TYPE_CHECKING-imports RuntimeState; ZoneStore reads the
        # domain table), and mypy's within-SCC inference needs the type stated
        # rather than inferred from the parameter.
        self.seating: Seating = seating
        self.zones = zones
        self.rng = rng
        self.frames: list[dict[str, Any]] = []
        self.indexed: set[str] = set()  # variable names that are per-player
        self.mech_state: list[dict[str, Any]] = []  # active mechanic state (`state.`)
        # The most recently completed round's terminal state, so the surrounding
        # body can read `state.x` after a `round` returns (round-state exposure;
        # see runtime.mechanics.run_trick / the `state` pronoun in evaluate).
        # `None` means no round has completed yet — reading `state` then is an
        # error, not a silent empty frame.
        self.last_round_state: dict[str, Any] | None = None
        self.fired_transitions: set[str] = set()  # transition targets reached this iteration
        self.rule_index: dict[str, n.RuleDef] = {}  # rule name -> definition
        self.move_type_index: dict[str, n.MoveTypeDef] = {}  # name -> definition
        self.type_index: dict[str, n.TypeDef] = {}  # type name -> definition
        self.define_index: dict[str, n.DefineDef] = {}  # define name -> definition
        self.function_index: dict[str, n.FunctionDef] = {}  # function name -> definition
        # Outcome a phase produced as it ran, keyed by phase name; consumed (and
        # cleared) by a later-sibling `produces:` block.
        self.phase_outcomes: dict[str, tuple[str, list[Any]]] = {}
        self.deck_zone: str = ""  # the Deck-typed zone (initialized full at start)
        self.score_var: str | None = None  # the winner's score var (None for loser games)
        self.trump: str | None = None  # the trump suit, if the game declares one
        self.teams: tuple[int, ...] = ()  # team ids (empty for non-partnership games)
        self.team_of: dict[Player, int] = {}  # player -> their team id
        self.rank_index: dict[str, int] = {}  # rank -> strength (higher = stronger)
        self.card_values: dict[str, int] = {}  # rank -> card points (point-trick games)
        self.suits: tuple[str, ...] = ()  # the deck's actual card suits (move-param domains)
        self.ranks: tuple[str, ...] = ()  # rank iteration order: ranking: if declared, else deck order
        self.max_length: int = 0  # the game's declared non-termination backstop
        self.decisions_made: int = 0  # every chooser pick, checked against max_length

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


@dataclass(frozen=True, slots=True)
class StructValue:
    """A constructed user-defined struct: its type name plus declared field
    values. Derived fields are computed on access (see evaluate._member_eval)."""

    type_name: str
    fields: dict[str, Any]


# A chooser picks a subset from a candidate list (random playout: uniform). The
# candidates are usually cards, but the same interface resolves any value
# decision — an integer bid, a suit choice — so the element type is open.
Chooser = Callable[[Player, list[Any], int], list[Any]]


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
    observer: Callable[[Player, tuple[Any, ...]], None] | None = None

    def trace(self, event: str, data: Any) -> None:
        if self.tracer is not None:
            self.tracer(event, data)

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        """Deliver a per-observer observation event (the projection substrate).
        No observer installed (normal playouts) means no cost and no effect."""
        if self.observer is not None:
            self.observer(player, event)

    def with_local(self, name: str, value: Any) -> "Ctx":
        return replace(self, locals={**self.locals, name: value})

    def acting_as(self, player: Player) -> "Ctx":
        return replace(self, current_player=player)

    def require_actor(self, what: str) -> Player:
        """The acting player at a decision point — never an implicit default. A
        choice with no acting player is a malformed game (who is choosing?), so
        fail loudly rather than silently attributing it to player 0."""
        if self.current_player is None:
            raise RuntimeError(
                f"{what} with no acting player; make it part of a per-player "
                f"context (e.g. `for each player p`) so the chooser knows who decides"
            )
        return self.current_player

    def in_phase(self, phase: n.Phase) -> "Ctx":
        return replace(self, current_phase=phase)

    def with_outcome(self, player: Player) -> "Ctx":
        return replace(self, outcome=player)

    def with_action(self, action: Move) -> "Ctx":
        return replace(self, action=action)

    def with_rules(self, rules: tuple[n.RuleDef, ...]) -> "Ctx":
        return replace(self, active_rules=rules)
