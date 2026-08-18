"""The game's [[trick-order]], materialized — the runtime side of the block.

The `trick_order { }` clause declares three per-card facts as expressions over
the implicit `card` binder (decisions.md "Trick Order"). This module holds what
the driver builds from that clause ONCE at load — `TrickOrderTable`, the three
row callables with their defaults already applied — and the thin wrappers that
carry a zone's [[arrival-record]] into the pure comparisons of
`runtime/winners.py`.

Neutral by construction, like `winners.py`: BOTH dispatch halves consume it
(`runtime/builtins.py` for the five calls, `runtime/primitives.py` for the
winner slot's second contract) and the two may not import each other. It
imports `winners` and `state` and never `evaluate` — the row callables arrive
already closed over the evaluator, built by the driver, so this module can be
imported from anywhere in the runtime without a cycle.

Contract
--------
Assumes: resolve admitted the block and its consumers (the presence partition
in both directions), every row is hermetic, and every [[arrival-record]] read
names a static identity-to-all zone
(`resolve._check_arrival_record_pile_args`). Assumes the driver materialized
`rs.trick_order` for any game whose description reaches these entry points.
Establishes: a card's three Trick Order facts, and the winner / follow answer
over a public pile — each a pure function of the card and public state.
Illegal after: reading a row's raw `Expr` anywhere downstream; re-applying a
row default (the defaults are decided once, in the driver's table).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cardlang.runtime import winners
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.state import Ctx, Zone
from cardlang.runtime.values import Card, Player
from cardlang.stdlib.zones import identity_to_all

# One row, as a callable over the card and the live ctx. The ctx is threaded
# because a row may read public state (`card.suit is trump_suit`); it is
# hermetic by resolve's guards, never by convention here.
RowFn = Callable[[Card, Ctx], Any]


@dataclass(frozen=True)
class TrickOrderTable:
    """The three rows, defaults already applied. Built once per game by the
    driver (`runtime/driver.py`), read by every consumer — so an omitted
    `follow_class:` or `card_strength:` row has exactly one meaning, decided
    at load, and no reader re-derives it."""

    is_trump: RowFn
    follow_class: RowFn
    card_strength: RowFn


def table_of(ctx: Ctx, caller: str) -> TrickOrderTable:
    """The game's materialized Trick Order. [[shadow-guard]] behind resolve's
    presence partition, which refuses every consumer of the block in a game
    that declares none — so a missing table here is an engine gap, not a bad
    game."""
    table = ctx.rs.trick_order
    if table is None:
        raise ShadowGuardError(
            "resolve._check_trick_order_partition",
            f"{caller} reads the game's `trick_order {{ }}` block, but the "
            f"game declares none",
        )
    return table


def project(card: Card, ctx: Ctx, actor: Player, caller: str) -> winners.Arrival:
    """One play, with its three Trick Order facts computed. The single place a
    row is asked anything on behalf of a comparison."""
    table = table_of(ctx, caller)
    return winners.Arrival(
        actor,
        card,
        bool(table.is_trump(card, ctx)),
        table.follow_class(card, ctx),
    )


def public_pile_plays(
    value: Any, ctx: Ctx, caller: str
) -> tuple[str, list[tuple[Player, Card]]]:
    """A pile's [[arrival-record]] as (label, plays in play order) — the shared
    boundary of every Arrival-Record call (`ARRIVAL_RECORD_CALLS`).

    Four guards, in two roles. The argument being a zone, and that zone's type
    projecting identity to every observer, are now decided STATICALLY
    (`resolve._check_arrival_record_pile_args`, issue #250 PR 1), so both are
    [[shadow-guard]]s naming it. Every arrival carrying a deciding actor is
    this boundary's own [[owner-guard]]: whether a pile was fed by plays or by
    a deal is a fact of what ran, which no static pass can decide.

    Emptiness is deliberately NOT refused here — `follows_lead` answers false
    on an empty pile (issue #345), so the pairs come back possibly empty and
    the winner's own guard reports it, with the pile's label."""
    if not isinstance(value, Zone):
        raise ShadowGuardError(
            "resolve._check_arrival_record_pile_args",
            f"{caller} expects a zone, got {type(value).__name__} — this "
            f"value is not a zone",
        )
    name, key = ctx.rs.zones.locate(value)
    label = name if key is None else f"{name}[{key}]"
    ztype = ctx.rs.zones.zone_type[name]
    if not identity_to_all(ztype):
        raise ShadowGuardError(
            "resolve._check_arrival_record_pile_args",
            f"{caller} over '{label}' ({ztype}): the zone type does not "
            f"project identity to every observer, so its provenance is not "
            f"derivable from any observer's stream — a winner may only be "
            f"named over a fully public pile",
        )
    played: list[tuple[Player, Card]] = []
    for a in value.arrivals:
        if a.actor is None:
            raise OwnerGuardError(
                f"{caller} over '{label}': {a.card} arrived with no deciding "
                f"actor (an engine deal, not a play) — a winner is named among "
                f"players, so every card in the pile must have been played by one"
            )
        played.append((a.actor, a.card))
    return label, played


def _arrivals(
    played: list[tuple[Player, Card]], ctx: Ctx, caller: str
) -> list[winners.Arrival]:
    return [project(card, ctx, actor, caller) for actor, card in played]


def _strength_of(ctx: Ctx, caller: str) -> Callable[[Card], int]:
    table = table_of(ctx, caller)

    def strength(card: Card) -> int:
        value = table.card_strength(card, ctx)
        # shadow guard: typecheck `_check_trick_order` (T1) requires the
        # `card_strength:` row to type exactly Integer
        assert isinstance(value, int), f"card_strength row yielded {value!r}"
        return value

    return strength


def winner_over_pile(value: Any, ctx: Ctx) -> Player:
    """`highest_by_trick_order(pile)` — the winner over a public pile's
    [[arrival-record]]. Over a complete trick the winner; over a partial one
    the winner so far (issue #350, designed surface)."""
    caller = "highest_by_trick_order"
    label, played = public_pile_plays(value, ctx, caller)
    return winners.highest_by_trick_order(
        _arrivals(played, ctx, caller),
        _strength_of(ctx, caller),
        f"{caller} over '{label}'",
        label,
    )


def follows_lead_over_pile(card: Any, value: Any, ctx: Ctx) -> bool:
    """`follows_lead(card, pile)` — whether the card follows what the pile has
    been led. False on an empty pile (issue #345's ruling: the value, not an
    error).

    The LEGALITY path, and the hot one: a follow filter asks this once per
    candidate per decision, so it runs orders of magnitude more often than the
    winner below. It therefore projects LAZILY -- the pile scan stops at the
    [[effective-lead]] and each row is asked only where the answer can still
    change (`winners.follows_lead_lazily`). Projecting the whole pile per ask,
    as the winner path does, was measured as the dominant cost of the whole
    construct."""
    caller = "follows_lead"
    if not isinstance(card, Card):
        raise OwnerGuardError(
            f"follows_lead expects a card, got {type(card).__name__}"
        )
    _label, played = public_pile_plays(value, ctx, caller)
    table = table_of(ctx, caller)
    return winners.follows_lead_lazily(
        lambda: bool(table.is_trump(card, ctx)),
        lambda: table.follow_class(card, ctx),
        played,
        lambda c: bool(table.is_trump(c, ctx)),
        lambda c: table.follow_class(c, ctx),
    )


class TrickOrderWinner:
    """The winner slot's SECOND contract, as a type.

    A `round … winner <name>` callback is dispatched by the one
    `primitives.value_function`; which contract the returned callable answers
    is this type (`cardlang/builtins/functions.py`,
    `TRICK_ORDER_GATED_WINNERS`). The uniform contract takes the round's
    configuration — (played, led_suit, trump, rank_index); this one takes
    (played, ctx), because a Trick Order winner's trumps, classes and
    strengths are the GAME's rows, not the round's arguments, and the rows
    need a ctx to evaluate under.

    A type rather than a plain closure so the contract is INSPECTABLE: the
    dispatcher's caller branches on `isinstance`, and the grid reconciles the
    set of winners under this contract against the registry rather than
    against a hand-written list
    (tests/test_trick_order.py::test_winner_slot_has_two_contracts_keyed_by_registry)."""

    def __call__(self, played: list[tuple[Player, Card]], ctx: Ctx) -> Player:
        caller = "highest_by_trick_order"
        return winners.highest_by_trick_order(
            _arrivals(list(played), ctx, caller),
            _strength_of(ctx, caller),
            caller,
        )
