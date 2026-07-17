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
from cardlang.domains import ZONE_INDEX_ROLES, DomainSources, role_static_members
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


def elements(value: Any) -> Any:
    """The Zone -> ordered-elements coercion shared by every raw-Python site
    that accepts either a Zone or an already-evaluated collection — the two
    runtime shapes of a collection-typed expression.  The evaluator applies
    it at its own consuming sites (card-query and comprehension sources, the
    right-hand side of `in`, rule fallbacks, `turns` participants), and
    `stdlib.call` applies it to every argument at its entry, so bare-Python
    adapters never see a Zone handle.  A Zone yields its `.cards` list
    (already a materialized, multi-pass `list`); anything else passes
    through unchanged, since a `[...]` literal, a nested query or
    comprehension result, and every other collection-typed expression
    already evaluate to a concrete `list`.  Callers that need a fresh,
    independent list (card-query, comprehension) wrap the result in
    `list(...)` themselves; single-pass consumers use it as-is."""
    return value.cards if isinstance(value, Zone) else value


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
                # players` silently keyed ANY other role by players. The gate
                # below is what makes the backstop REAL: an unknown role
                # raises inside `role_static_members`, but a known
                # non-indexable row (suit/rank) would quietly enumerate the
                # deliberately-empty () sources and build a zero-instance
                # family whose every access key-errors far from the cause.
                # Resolve walls these declarations; reaching this raise means
                # a construction path bypassed it.
                if decl.index not in ZONE_INDEX_ROLES:
                    raise AssertionError(
                        f"zone family '{decl.name}' is indexed by "
                        f"'{decl.index}', which is not a zone-index role "
                        f"(resolve rejects this declaration)"
                    )
                keys = role_static_members(
                    decl.index,
                    DomainSources(suits=(), ranks=(), players=players, teams=teams),
                )
                self.families[decl.name] = {k: Zone() for k in keys}

    def is_family(self, name: str) -> bool:
        return name in self.families

    def single(self, name: str) -> Zone:
        if name not in self.singles:
            raise RuntimeError(
                f"no zone '{name}' in this game — a game-local stdlib "
                f"primitive that reads it was called from a game without "
                f"its zones"
            )
        return self.singles[name]

    def instance(self, name: str, key: int) -> Zone:
        # The typed wall for the whole game-local-primitive class: every
        # per-game primitive (cribbage, gin, …) reads its zones by name
        # through here, and calling one from a game without those zones used
        # to die as a bare KeyError naming only the zone. (DSL-side zone
        # references are resolve-walled long before this; only primitives
        # and driver internals reach here with a foreign name.)
        if name not in self.families:
            raise RuntimeError(
                f"no zone family '{name}' in this game — a game-local stdlib "
                f"primitive that reads it was called from a game without "
                f"its zones"
            )
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
        """Bind the acting player for a body. The player MUST be a real seat.
        `as <expr>` and `offer to <expr>` evaluate an arbitrary expression here,
        and a player expression is runtime data: an off-by-one at a ring's edge,
        or a non-player value the checker leaves deliberately loose (`TAny` —
        `as active_rules`, `as outcome` before a round has produced one, `as 5`
        in a two-player game), would otherwise reach the chooser as a phantom
        decider and silently corrupt the decision node's information set. This is
        the acting-player analogue of the phantom-key write wall in
        `RuntimeState.set`, and it is what keeps `as` from being *more* dangerous
        than the guarded loop it replaces (a `for each player p: if p is <who>`
        guard never matches a non-seat, so it drops the decision; `as` binds
        unconditionally, so the seat check moves here). The trusted callers
        (`for each`, the simultaneous pass, move effects) always pass a real
        seat, so this never fires for them."""
        if player not in self.rs.seating.players:
            raise RuntimeError(
                f"cannot act as {player!r}: not a seat of this "
                f"{len(self.rs.seating.players)}-player game — the player "
                f"expression bound a non-player value"
            )
        return replace(self, current_player=player)

    def require_actor(self, what: str) -> Player:
        """The acting player at a decision point — never an implicit default. A
        choice with no acting player is a malformed game (who is choosing?), so
        fail loudly rather than silently attributing it to player 0. (Seat
        validity is enforced upstream, when the player is bound — `acting_as`.)"""
        if self.current_player is None:
            raise RuntimeError(
                f"{what} with no acting player; make it part of a per-player "
                f"context (`as <player>` for one decider, `for each player p` "
                f"for all) so the chooser knows who decides"
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
