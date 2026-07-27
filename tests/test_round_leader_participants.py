"""Who leads when `from <leader>` names a player `over <participants>` excludes.

property:   Every kernel construct that starts an acting sequence builds it
            from two independently-evaluated game expressions — `from
            <leader>` and `over <participants>`. When the leader is not a
            participant (a climbing game's trick winner who shed out on the
            winning play), the sequence starts at the first participant
            at/after the leader in game turn order. A genuinely empty
            participant set is an error, and so is a leader who is not a seat.
domain:     acting path x leader/participants relationship x game direction.
registry:   acting path -- the AST constructs carrying BOTH `leader` and
                          `participants` (`n.Round` and `n.Turns`), with
                          `n.Round` split into its three forms by
                          `mechanics.build_form`'s field cascade and the
                          auction form split again by `n.ROUND_ORDER_MODES`
                          (two distinct `next_actor` bodies). `turns` is a
                          member of this class though it is NOT a `round`
                          form and does not go through `build_form` — the
                          class is the leader/participants shape, not the
                          `round` keyword. Pinned by
                          `test_acting_path_axis_is_derived_from_the_registries`.
            direction  -- `values.GAME_DIRECTIONS`. Pinned by
                          `test_direction_axis_is_the_seating_registry`.
            relationship -- the space of two independent runtime values:
                          leader in the set, leader outside a non-empty set,
                          set empty, leader not a seat at all. Pinned by
                          `test_relationship_axis_is_total`.
covered:    `test_leader_participants_grid`, the full
            ACTING_PATHS x RELATIONSHIPS x DIRECTIONS cross (40 rows).
sampled:    none.
residual:   The `participants_empty` column is CAPTURED per path, not
            unified: the four paths fail four different ways (trick: no
            actor, then the outcome function meets zero plays; auction-ring:
            the 1000-step ring guard; auction-priority: its own
            termination/participants-disagreement error; climb: the empty-ring
            error). The grid pins that each path is LOUD, which is the
            property that matters; it does not pin one shared message.

            One of those four is loud in the WRONG CURRENCY, and the grid
            found it: the trick path reaches `highest_of_led_suit` with zero
            plays and dies on a raw `ValueError: max() arg is an empty
            sequence` from `stdlib.py`, not a typed error naming the empty
            participant set. That is a real defect of the currency class
            (decisions.md: a runtime failure is a typed error with the fix in
            its message, never a bare Python exception) -- R3, reachable by a
            designer whose `over` predicate empties. Filed as issue #167; not
            fixed here because it belongs to the outcome-function boundary,
            not to leader/participant ring construction, and this change is
            already three issues wide (planning Gate 3.5). The grid's expected
            column admits `ValueError` for exactly that cell so the row states
            today's truth rather than the truth we want.

            The `leader_out_of_range` column is NOT a residual — it is
            uniformly green, and settled one layer above the runtime: the
            player-literal range wall rejects `from 9` in a 4-player game at
            typecheck, identically for all five paths, so no acting path ever
            meets an out-of-range leader literal. The grid rows assert that
            static rejection.

            The residual underneath it is narrow. `Seating.turn_order_from`
            itself validates nothing — it is pure modular arithmetic
            (values.py:435-439), verified directly:
            `Seating(4).turn_order_from(9) == [1, 2, 3, 0]`. So a leader that
            escapes the literal wall by being COMPUTED would be silently
            normalized by `trick` and both auction modes, while `turns`
            (execute.py:596-601) and, pre-#24, `climb` would raise. Whether a
            Player-typed expression can compute out of range at all is
            unverified — every producer the author checked derives its value
            from live seating. Recorded as issue #168, which owns both the
            question and the fix (inside `turn_order_from`, the shared cause,
            not at four call sites). The #24 fix below therefore does NOT add
            a climb-local seat wall: a fourth bespoke wall for a case the
            shared fix should own is the wall you cannot need (decisions.md,
            "Prefer the wall you cannot need").

            NOT cells, and deliberately so — a different property with its own
            owner: participants-content validity (a non-seat member, duplicates,
            a `Zone`-valued `over`), and the evaluation-TIMING axis (trick and
            climb read `participants` once at construction; auction re-reads it
            every step and `turns` every pick, so a set that shrinks mid-round
            is seen by two members and not the other two). A non-int leader
            dying on a bare `TypeError` inside `turn_order_from` is the same
            missing validation as issue #168 and is recorded there.

Framing check: RAN. A fresh-context subagent derived this domain from the
definition sources alone (grammar, AST unions, the whole `cardlang/` package),
with no access to the plan or the diff. Diffing its axis list against the
author's changed the grid twice, and both changes are load-bearing:
  - it found `turns` — a fifth member of the leader/participants class that
    the author's `round`-rooted derivation had missed entirely, and the ONLY
    member that already walls its leader. The path axis grew from 4 to 5.
  - it found that an out-of-range leader is silently normalized, disproving
    an author-written residual line that had claimed the case was walled
    elsewhere and therefore "not a cell". That line was wrong; the corrected
    capture is above. It also showed that removing the climb form's refusal
    would DELETE that form's only out-of-range catch (it fell out of the
    `ring[0] != leader` test), which is why ClimbForm now carries an explicit
    seat check rather than inheriting one.
Its remaining reports (participants-content, evaluation timing) are the
recorded not-cells above.

red under: the four born-green `leader_out` paths claim the sibling
constructs already advance past a shed-out leader. Each has its OWN
participant filter, so each needs its own mutation — RUN, not reasoned:
  - trick: `TrickForm.next_actor`, `if player in self.participants` -> `if
    True` (mechanics.py). Reddens both `trick-leader_out` rows.
  - auction-ring: `AuctionForm.next_actor`, `if player in participants` ->
    `if True` (mechanics.py). Reddens both `auction_ring-leader_out` rows.
  - auction-priority: same method's priority branch, `next((p for p in order
    if p in participants), None)` -> drop the `if` clause. Reddens both
    `auction_priority-leader_out` rows.
  - turns: `_turns`, `next((p for p in candidate_seq if p in participants),
    None)` -> drop the `if` clause (execute.py). Reddens both
    `turns-leader_out` rows.
Each mutation reddens ONLY its own path's rows, which is the point: one
mutation reddening all four would mean the rows share a code path and three
of them are decorative. The `climb` `leader_out` rows were born RED against
the pre-fix refusal, so their xfail run is their own witness.
"""

from __future__ import annotations

import dataclasses
import inspect
import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime import mechanics
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import ChooserAbort
from cardlang.runtime.values import GAME_DIRECTIONS

# --- the axes, each derived from the registry that defines it ---

# The auction form is the only `round` form whose `next_actor` branches on the
# order mode, so it contributes one path per mode; `turns` is not a `round`
# form at all but carries the same `from`/`over` clauses, which is what the
# class is defined by.
ACTING_PATHS: tuple[str, ...] = (
    "trick",
    "auction_ring",
    "auction_priority",
    "climb",
    "turns",
)
RELATIONSHIPS: tuple[str, ...] = (
    "leader_in",
    "leader_out",
    "participants_empty",
    "leader_out_of_range",
)
DIRECTIONS: tuple[str, ...] = GAME_DIRECTIONS

LEADER = 1  # every fixture leads from seat 1 of 4
OUT_OF_RANGE_LEADER = 9  # no such seat in a 4-player game


class NoDecisionReached(Exception):
    """A fixture ran to completion without ever offering a decision. Its own
    type, NOT a bare AssertionError: the `participants_empty` cell asserts
    that each path FAILS LOUDLY, and if a generic assertion counted as the
    expected failure then a fixture that quietly stopped reaching decisions
    for an unrelated reason — an `until` predicate drifting to satisfiable, a
    typo in the source template — would satisfy that cell without proving
    anything. Deriving from `Exception` rather than `RuntimeError` keeps it
    outside the tuple the empty cell accepts."""

# Authored expected column, independent of `Seating.turn_order_from` (deriving
# it from the utility under test would be circular). Four seats, leading from
# 1: clockwise turn order is [1, 2, 3, 0], counterclockwise is [1, 0, 3, 2].
FIRST_PARTICIPANT_AFTER_LEADER = {"clockwise": 2, "counterclockwise": 0}


# --- axis-derivation pins ---


def test_acting_path_axis_is_derived_from_the_registries() -> None:
    """The path axis is the AST constructs carrying BOTH `leader` and
    `participants` — the shape that defines the class — with `Round` split by
    `build_form`'s cascade and the auction form split by the order modes. A
    sixth path (a new construct with a `from`/`over` pair, a fourth form
    class, a third order mode) must fail here rather than go unnoticed."""
    fields_of = {
        node.__name__: {f.name for f in dataclasses.fields(node)}
        for node in (n.Round, n.Turns)
    }
    for name, names in fields_of.items():
        assert {"leader", "participants"} <= names, (
            f"{name} no longer carries the leader/participants pair"
        )
    # No OTHER AST node carries the pair — that is what bounds the class.
    carriers = {
        obj.__name__
        for obj in vars(n).values()
        if dataclasses.is_dataclass(obj)
        and isinstance(obj, type)
        and {"leader", "participants"}
        <= {f.name for f in dataclasses.fields(obj)}
    }
    assert carriers == {"Round", "Turns"}, (
        f"a new leader/participants construct appeared: {carriers}"
    )

    forms = {mechanics.TrickForm, mechanics.AuctionForm, mechanics.ClimbForm}
    source = inspect.getsource(mechanics.build_form)
    for form in forms:
        assert form.__name__ in source, (
            f"{form.__name__} is not accounted for in build_form's cascade"
        )
    assert n.ROUND_ORDER_MODES == {n.ROUND_ORDER_RING, n.ROUND_ORDER_PRIORITY}
    # Round's 3 forms, the auction one split by its 2 order modes, plus Turns.
    assert len(ACTING_PATHS) == (len(forms) - 1) + len(n.ROUND_ORDER_MODES) + 1


def test_direction_axis_is_the_seating_registry() -> None:
    assert DIRECTIONS == GAME_DIRECTIONS
    assert set(FIRST_PARTICIPANT_AFTER_LEADER) == set(GAME_DIRECTIONS)


def test_relationship_axis_is_total() -> None:
    """Two independently-evaluated runtime values, neither statically
    constrained when computed: the leader is a seat or it is not, and if it is,
    it is inside the participant set or outside a set that is itself empty or
    not. This states the partition so a fifth case cannot be added silently."""
    assert RELATIONSHIPS == (
        "leader_in",
        "leader_out",
        "participants_empty",
        "leader_out_of_range",
    )


# --- fixtures: one per ring path, parameterized by direction and predicate ---

# Always-true / always-false participant predicates written over the game's own
# state, so the leader's membership is a runtime fact the checker cannot fold.
PREDICATES = {
    "leader_in": "x[player] >= 0",
    "leader_out": f"player is not {LEADER}",
    "participants_empty": "x[player] < 0",
    # An out-of-range leader over a full participant set: the leader is the
    # only thing wrong, so whatever the path does is attributable to it.
    "leader_out_of_range": "x[player] >= 0",
}

TRICK = """
game G {{
  players: 4
  direction: {dir}
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }}
  state {{ x[player] : Integer = 0 }}
  phase play {{
    deal 5 cards from deck to each hand
    round play_to_trick from {leader} over players where {pred}
          source hand into trick_pile outcome highest_of_led_suit
    move all cards from trick_pile to waste
  }}
  winner: highest x
}}
"""

AUCTION = """
game G {{
  players: 4
  direction: {dir}
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck }}
  state {{ x[player] : Integer = 0 }}
  phase run {{
    round offering [step] from {leader} over players where {pred}
{order}          until false
  }}
  winner: highest x
}}
move_type step {{ effect {{ x[actor] := x[actor] + 1 }} }}
"""

CLIMB = """
game G {{
  players: 4
  direction: {dir}
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ x[player] : Integer = 0 }}
  phase play {{
    deal 5 cards from deck to each hand
    round climb play_combination from {leader} over players where {pred}
          source hand into trick_pile
          combinations president_lead_options follows president_follows
          until false
  }}
  winner: highest x
}}
"""


TURNS = """
game G {{
  players: 4
  direction: {dir}
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck }}
  state {{ x[player] : Integer = 0 }}
  phase run {{
    turns t from {leader} over players where {pred} until false {{
      offer to t one of [step]
    }}
  }}
  winner: highest x
}}
move_type step {{ effect {{ x[actor] := x[actor] + 1 }} }}
"""


def _source(path: str, relationship: str, direction: str) -> str:
    pred = PREDICATES[relationship]
    leader = (
        OUT_OF_RANGE_LEADER if relationship == "leader_out_of_range" else LEADER
    )
    if path == "trick":
        return TRICK.format(dir=direction, leader=leader, pred=pred)
    if path == "climb":
        return CLIMB.format(dir=direction, leader=leader, pred=pred)
    if path == "turns":
        return TURNS.format(dir=direction, leader=leader, pred=pred)
    order = "          order priority\n" if path == "auction_priority" else ""
    return AUCTION.format(dir=direction, leader=leader, pred=pred, order=order)


def _first_actor(src: str) -> int:
    """The seat offered the round's FIRST decision. Aborting at that decision
    keeps the grid independent of whether the fixture's round can terminate."""
    game = check_dsl(src, "grid.cardlang")

    def abort(player: int, candidates: list[Any], count: int) -> list[Any]:
        raise ChooserAbort(player, list(candidates))

    try:
        play_game(game, random.Random(0), chooser=abort)
    except ChooserAbort as exc:
        return exc.player
    raise NoDecisionReached("the round completed without offering a decision")


# --- the grid ---


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("relationship", RELATIONSHIPS)
@pytest.mark.parametrize("path", ACTING_PATHS)
def test_leader_participants_grid(
    path: str, relationship: str, direction: str
) -> None:
    src = _source(path, relationship, direction)

    if relationship == "leader_out_of_range":
        # UNIFORM across all five paths, and settled one layer UP: the
        # player-literal range wall rejects the game at typecheck, so no path
        # ever reaches the runtime with an out-of-range leader literal. This
        # is the cell's real answer — the runtime divergence between the paths
        # (issue #168) is reachable only by a COMPUTED Player-typed leader,
        # which the type system does not obviously admit.
        with pytest.raises(DiagnosticError, match="out of range"):
            check_dsl(src, "grid.cardlang")
        return

    if relationship == "participants_empty":
        # Captured, not unified: each path is loud in its own currency (see the
        # module docstring's residual row). The property pinned here is that
        # NO path silently proceeds with an empty acting set. `ValueError` is
        # the trick path's WRONG-currency failure, admitted deliberately and
        # recorded as issue #167 — remove it from this tuple when that lands.
        # `NoDecisionReached` is deliberately NOT here: a path that simply
        # stops offering decisions has not failed loudly, and must not pass.
        with pytest.raises((RuntimeError, ValueError)):
            _first_actor(src)
        return

    expected = (
        LEADER
        if relationship == "leader_in"
        else FIRST_PARTICIPANT_AFTER_LEADER[direction]
    )
    assert _first_actor(src) == expected
