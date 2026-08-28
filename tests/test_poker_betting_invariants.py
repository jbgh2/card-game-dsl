"""Structural invariants of a betting street, held at every decision of
randomized play.

property:        six facts survive every legal sequence of betting moves, from
                 the street's open to its close: chips are conserved per seat
                 (stack plus committed is the seat's opening holding), no stack
                 goes negative, no seat's street contribution exceeds the
                 standing bet, the standing bet sits in the three-position band
                 (at least the level, short of the level plus the street), the
                 standing bet and the aggression count never decrease, and the
                 street terminates.
domain:          random walks. Six stack PROFILES chosen for shape — deep,
                 tiny, one short stack among deep ones, descending, heads-up,
                 stacks at exact half-bet boundaries — each played under many
                 rng seeds, every offered move equally likely. The random
                 chooser is legitimate HERE and only here, because the oracle
                 is implicit: an invariant is checked at every decision of
                 whatever sequence the walk takes, so reach buys breadth of
                 evidence rather than deciding what a green can claim. The
                 expected-column modules cannot afford random driving for
                 exactly the opposite reason.
registry:        `PROFILES` x `SEEDS` below; the library under test is
                 `docs/libraries/poker_betting.cardlang`; the invariants are
                 `_check_invariants`.
does not prove:  that any move pays the RIGHT amount or is offered to the RIGHT
                 seat — a library that charged double and never reopened would
                 conserve chips, stay in band, and terminate. The rule-level
                 expected columns live in tests/test_poker_betting_sizing.py,
                 tests/test_poker_betting_offers.py and
                 tests/test_poker_betting_transitions.py, and the books' own
                 figures in tests/test_poker_betting_rulebook.py. A green here
                 means the bookkeeping cannot be driven incoherent, and no more.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

LIMIT = 4
"""The street's bet size — 4 so half of it is a whole chip and the half-bet
boundary is drivable."""

# Stack shapes, each chosen to reach a corner random depth alone would not:
# every seat deep (long raise wars), every seat tiny (immediate all-ins), one
# short seat among deep ones (short all-ins mid-street), strictly descending
# (each raise can be answered by a shorter stack), heads-up, and stacks parked
# exactly at half-bet multiples (the boundary the counting rule decides).
PROFILES: dict[str, tuple[int, ...]] = {
    "deep": (40, 40, 40, 40),
    "tiny": (2, 1, 3, 2),
    "one-short": (30, 2, 30, 30),
    "descending": (24, 12, 6, 3),
    "heads-up": (25, 25),
    "half-steps": (2, 4, 6, 8),
}

SEEDS = range(50)

_PROBE = """
game Invariants {{
  uses poker_betting
  players: {seats}
  cards: standard52
  max_length: 300
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 0
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    level             : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 4
    snapped           : Boolean = false
  }}
  phase play {{
    run open_street({limit})
{stacks}    round offering [check, bet, call, raise] from 0
          over players where pending(player)
          until (number of players where pending(player)) is 0
    round offering [snapshot] from 0
          over players where player is 0 and not snapped
          until snapped
  }}
  winner: highest stack
}}

move_type snapshot {{
  when: not snapped
  effect {{ snapped := true }}
}}
"""


def _source(profile: tuple[int, ...]) -> str:
    stacks = "".join(
        f"    stack[{seat}] := {chips}\n" for seat, chips in enumerate(profile)
    )
    return _PROBE.format(seats=len(profile), limit=LIMIT, stacks=stacks)


def _check_invariants(
    state: RuntimeState,
    profile: tuple[int, ...],
    prev: dict[str, int],
    where: str,
) -> None:
    """The six facts, asserted wherever the walk happens to be."""
    stack = state.get("stack")
    committed = state.get("committed")
    bet_by = state.get("bet_by")
    standing = state.get("bet_to_match")
    level = state.get("level")
    raises = state.get("raises")

    for seat, opening in enumerate(profile):
        held = stack[seat] + committed[seat]
        assert held == opening, (
            f"{where}: seat {seat} opened with {opening} chips and now accounts "
            f"for {held} — chips created or destroyed"
        )
        assert stack[seat] >= 0, f"{where}: seat {seat} holds {stack[seat]}"
        assert bet_by[seat] <= standing, (
            f"{where}: seat {seat} has {bet_by[seat]} in against a standing bet "
            f"of {standing} — a contribution above the bet is a raise that never "
            f"moved it"
        )

    # The three-position band. The upper bound is strict BETWEEN actions: a
    # wager that reaches the level plus the street becomes the level itself, so
    # a standing bet observed at or past it is one the library failed to record.
    assert level <= standing < level + LIMIT, (
        f"{where}: the bet stands at {standing} against a level of {level} on a "
        f"street of {LIMIT} — outside every position the rules have"
    )
    assert standing >= prev["standing"], (
        f"{where}: the standing bet fell from {prev['standing']} to {standing}"
    )
    assert raises >= prev["raises"], (
        f"{where}: the aggression count fell from {prev['raises']} to {raises}"
    )
    prev["standing"] = standing
    prev["raises"] = raises


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_no_walk_drives_the_bookkeeping_incoherent(name: str) -> None:
    """Every profile, every seed, every decision — and the close.

    red under (each verified by running the mutated library): drop the `min`
    from `call`'s payment and the tiny profiles drive a stack negative; drop
    `raise`'s `level` advance and the first full raise leaves the band; drop
    `call`'s stack deduction and conservation names the seat. Termination is
    the `until` closing on `pending`, backstopped by `max_length` — a walk
    that hits the cap fails the play itself.

    The monotonicity assertions have no reddening mutation in today's library:
    `raise`'s guard requires the stack to exceed the call, so its wager always
    lands past the standing bet and the standing-bet fold in its effect cannot
    bind — replacing it with a bare assignment leaves every walk green. They
    stand as walls against effects not yet written, and the plant that proves
    them able to fail is a future effect that lowers the bet, not a mutation
    of this one.
    """
    profile = PROFILES[name]
    game = check_dsl(_source(profile), "invariants.cardlang")
    for seed in SEEDS:
        _walk_one(game, profile, name, seed)


def _walk_one(game: Any, profile: tuple[int, ...], name: str, seed: int) -> None:
    """One street under one seed. A function so the closures bind arguments,
    not loop variables — they are consumed before the loop moves anyway, but a
    reader (and the linter) should not have to prove that."""
    rng = random.Random(seed)
    box: list[RuntimeState] = []
    prev = {"standing": 0, "raises": 0}
    decisions = 0

    def on_first(state: RuntimeState) -> None:
        box.append(state)

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        # The state is read before each action, and once more at the
        # `snapshot` decision the probe schedules after the street closes —
        # which is how the LAST action's effect is observed, since a phase
        # that exits cleanly pops its frames and takes the names with it.
        nonlocal decisions
        decisions += 1
        if box:
            _check_invariants(
                box[0], profile, prev, f"{name} seed {seed} decision {decisions}"
            )
        return [candidates[rng.randrange(len(candidates))]]

    play_game(game, random.Random(seed), None, chooser, None, on_first)
    assert decisions >= 2, (
        f"{name} seed {seed}: the walk closed after {decisions} decisions, "
        f"so the snapshot never fired and the final action went unobserved"
    )
