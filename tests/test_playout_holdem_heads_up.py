"""Heads-up fixed-limit Hold'em: random playouts plus the three rules the
invariants can't see.

Chip conservation is the strongest falsifiable check a betting game has, and it
is checked here at every game end. But conservation is blind to everything about
WHO is charged and HOW MUCH, so each of the game file's load-bearing claims gets
its own test. All three below are rules under which a broken game still
conserves chips, still terminates, and still looks legal:

- the BETS-PER-STREET table (`test_four_aggressions_per_street_is_the_cap`,
  `test_the_street_caps_are_the_documented_numbers`). The header spells the cap
  out as four aggressions per street — pre-flop the big blind takes the first
  slot, so three raises follow it; post-flop a bet plus three raises. A file
  that said 4 and meant "four raises after the opening bet" would play a
  five-bet street and conserve chips perfectly. This is the off-by-one the
  number alone cannot exclude, so the table is driven to the cap and `raise` is
  asserted gone from the legal set;
- NO SEAT IS EVER ALL-IN (`test_no_seat_is_ever_all_in`). The game file writes
  its blinds as flat subtractions and drops three-handed Hold'em's pre-flop
  entry guard, and BOTH are licensed by one arithmetic claim: the street caps
  sum to 48 against a 100-chip stack. If that claim were false the game would
  still conserve chips — it would just have unreachable-by-argument branches
  quietly becoming reachable;
- the HEADS-UP BLIND REVERSAL (`test_the_button_posts_the_small_blind_and_acts
  _first_preflop`). Pagat reverses the blinds heads-up: the button posts the
  SMALL blind, so it acts first pre-flop and last on every later street. Swap
  the two seats and the game is still a legal, chip-conserving poker game
  played by the wrong rules.

The hook for the state-reading tests is the chooser, as in
tests/test_playout_holdem.py: phase state is unwound by the time a decision
surfaces to a caller, but the chooser runs INSIDE the phase body, and
`RuntimeState` is one object for the whole game — so capturing it at the first
decision makes it readable at every later one.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GAME = Path(__file__).parent.parent / "docs" / "games" / "holdem-heads-up.cardlang"

_STARTING_STACK = 100
_TOTAL_CHIPS = 200  # 2 players x 100
_SMALL_BLIND = 1
_BIG_BLIND = 2

# The header's table, as data. Keyed by the number of cards on the board, which
# is what names a street: 0 pre-flop, 3 flop, 4 turn, 5 river.
_STREET_NAME = {0: "pre-flop", 3: "flop", 4: "turn", 5: "river"}
_STREET_BET_CAP = {0: 8, 3: 8, 4: 16, 5: 16}
_AGGRESSION_CAP = 4
# 8 + 8 + 16 + 16 — the whole of what one seat can be charged in a hand.
_MAX_COMMITMENT = sum(_STREET_BET_CAP.values())


def _drive(seed: int, watch: Any, policy: Any = None) -> Any:
    """Play one game, calling `watch(rs, player, candidates)` at every decision
    with phase state still in scope.

    `policy(player, candidates, rs)` returns the chosen candidate; the default
    is `candidates[0]`, the check/call line, which is the cheapest policy that
    still reaches a showdown.
    """
    game = check_source(GAME)
    box: list[Any] = []

    def on_first_decision(rs: Any) -> None:
        box.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if box and watch is not None:
            watch(box[0], player, candidates)
        if policy is None:
            return list(candidates[:k])
        return [policy(player, candidates, box[0] if box else None)][:k]

    return play_game(game, random.Random(seed), None, chooser, None, on_first_decision)


def _names(candidates: list[Any]) -> list[str]:
    """The move-type names offered at a decision. Candidates are
    `(move_name, argument)` pairs; every betting move here is nullary."""
    return [c[0] for c in candidates]


def test_20_random_games_satisfy_invariants() -> None:
    """Terminates, conserves chips, and scores as a zero-sum chip delta."""
    game = check_source(GAME)
    for seed in range(20):
        result = play_game(game, random.Random(seed))
        # `net` is the hand's chip delta against the starting stack, so a
        # two-handed hand's scores must sum to zero — the settlement neither
        # creates nor destroys chips.
        assert sum(result.scores.values()) == 0, f"seed {seed}: {result.scores}"
        # And the winner is the seat that actually won chips (or, on a split,
        # a seat that lost none). `winner: highest net` always names a seat
        # here — every hand settles — so a `None` is itself the failure.
        assert result.winner is not None, f"seed {seed}: no winner named"
        best = max(result.scores.values())
        assert result.scores[result.winner] == best, f"seed {seed}: {result.scores}"


def test_no_seat_is_ever_all_in() -> None:
    """The arithmetic claim the game file's simplifications rest on.

    `can_act`'s `stack[p] > 0` never gates, so the blinds need no short-stack
    conditional and the pre-flop street needs no entry guard. Both follow from
    the street caps summing to 48 against a 100-chip stack — checked here at
    every decision of every seed, over the raising policy that reaches the caps.

    red under: set the game file's starting stack to 20, below the 48-chip
    bound, moving `net[p] := stack[p] - 100` to `- 20` in the same edit so the
    plant is a consistent short-stack game rather than a broken scoreboard. RUN,
    not predicted: 4 of this module's 5 tests fail, this one on the all-in
    assertion. The two cap tests fall with it because a seat that runs out of
    chips can no longer answer a raise, so the streets stop short of their
    documented peaks.
    """
    worst = _STARTING_STACK

    def watch(rs: Any, player: int, candidates: list[Any]) -> None:
        nonlocal worst
        for p, chips in rs.get("stack").items():
            assert chips > 0, f"seat {p} is all-in with {chips} chips"
            worst = min(worst, chips)
        for p, put_in in rs.get("committed").items():
            assert put_in <= _MAX_COMMITMENT, (
                f"seat {p} committed {put_in}, over the {_MAX_COMMITMENT}-chip "
                f"bound the game file's header argues from"
            )

    for seed in range(20):
        _drive(seed, watch, policy=_always_aggressive)

    # The bound has to BITE, or the test passes on a game nobody bets in. The
    # threshold is the FULL commitment, not one blind: the big blind's forced
    # post puts a seat at 98 before anyone acts voluntarily, so a `worst <= 98`
    # guard is satisfied by the deal alone and passes over a purely passive
    # game — measured, 98 under check/call against 52 under the raising policy.
    assert worst <= _STARTING_STACK - _MAX_COMMITMENT, (
        f"no seat ever went below {worst} chips, but a hand that reaches every "
        f"street's cap costs {_MAX_COMMITMENT} — the raising policy is not "
        f"reaching the caps and this test proves nothing"
    )


def _always_aggressive(player: int, candidates: list[Any], rs: Any) -> Any:
    """Raise whenever it is legal, else call, else check. The policy that
    drives every street to its cap; it never folds, so every hand reaches a
    showdown."""
    offered = _names(candidates)
    for want in ("raise", "bet", "call", "check"):
        if want in offered:
            return candidates[offered.index(want)]
    return candidates[0]


def test_four_aggressions_per_street_is_the_cap() -> None:
    """The header's bets-per-street table, driven to the cap.

    Under a never-folding always-raising policy every street runs until the cap
    stops it, so this asserts the exact shape of that stop: `raises` never
    exceeds four, and at four `raise` is gone from the legal set while `call`
    remains.

    red under: change the game file's `raise_cap : Integer = 4` to `5`. RUN, not
    predicted: this test fails on the `raise not in offered` assertion —
    `pre-flop still offers 'raise' at 4 aggressions: ['call', 'fold', 'raise']`
    — which fires before `raises <= _AGGRESSION_CAP` ever can, since the fifth
    aggression is offered before it is taken. Two others fall with it
    (`test_no_seat_is_ever_all_in`, because a fifth aggression per street breaks
    the 48-chip commitment bound, and
    `test_the_street_caps_are_the_documented_numbers`, because the extra bet
    lifts every street's peak).
    """
    reached_cap: set[int] = set()

    def watch(rs: Any, player: int, candidates: list[Any]) -> None:
        board = len(rs.zones.single("board").cards)
        raises = rs.get("raises")
        offered = _names(candidates)
        assert raises <= _AGGRESSION_CAP, (
            f"{_STREET_NAME[board]} reached {raises} aggressions, over the "
            f"cap of {_AGGRESSION_CAP}"
        )
        if raises == _AGGRESSION_CAP:
            reached_cap.add(board)
            assert "raise" not in offered, (
                f"{_STREET_NAME[board]} still offers `raise` at {raises} "
                f"aggressions: {offered}"
            )
            assert "call" in offered, (
                f"{_STREET_NAME[board]} offers no `call` at the cap: {offered} "
                f"— a capped street must still let the facing seat answer"
            )

    for seed in range(20):
        _drive(seed, watch, policy=_always_aggressive)

    # Every street must actually have been driven to the cap, or the assertions
    # above are vacuous for the streets that were not.
    assert reached_cap == set(_STREET_NAME), (
        f"only {sorted(reached_cap)} of {sorted(_STREET_NAME)} board sizes "
        f"reached the cap — the streets that did not are unchecked"
    )


def test_the_street_caps_are_the_documented_numbers() -> None:
    """`bet_to_match` tops out at the header's per-street numbers: 8 on the two
    small-bet streets, 16 on the two big-bet ones.

    This is what separates "four aggressions" from "four aggressions AT THE
    RIGHT SIZE". A game that doubled the limit on the flop instead of the turn
    would pass `test_four_aggressions_per_street_is_the_cap` unchanged.

    red under: change the game file's flop `run open_street(2)` to
    `open_street(4)`. RUN, not predicted: this test fails naming the flop at 16
    against a documented 8, and `test_four_aggressions_per_street_is_the_cap`
    stays GREEN — which is the separation this test exists for, demonstrated
    rather than argued. (`test_no_seat_is_ever_all_in` falls too: the bigger
    flop breaks the 48-chip bound.)
    """
    peak: dict[int, int] = {}

    def watch(rs: Any, player: int, candidates: list[Any]) -> None:
        board = len(rs.zones.single("board").cards)
        peak[board] = max(peak.get(board, 0), rs.get("bet_to_match"))

    for seed in range(20):
        _drive(seed, watch, policy=_always_aggressive)

    assert set(peak) == set(_STREET_BET_CAP), (
        f"streets reached: {sorted(peak)} — expected all of "
        f"{sorted(_STREET_BET_CAP)}"
    )
    for board, cap in _STREET_BET_CAP.items():
        assert peak[board] == cap, (
            f"{_STREET_NAME[board]} peaked at {peak[board]}, not the "
            f"documented {cap}"
        )


def test_the_button_posts_the_small_blind_and_acts_first_preflop() -> None:
    """Pagat's heads-up reversal: the button posts the SMALL blind, so it acts
    first pre-flop and last on every later street.

    red under: swap the game file's two blind posts (`bet_by[button] := 2` and
    `bet_by[big_blind] := 1`, with the matching stack/committed lines). RUN, not
    predicted: this test fails on the posted-amount assertion and is the ONLY
    one of the five that moves — the swap is invisible to conservation, to the
    caps and to the all-in bound, which is why it needs a test of its own.
    """
    firsts: list[tuple[int, int]] = []  # (board size, seat that acted first)
    posts: list[tuple[int, int]] = []  # (button's post, big blind's post)
    seen_streets: set[int] = set()

    def watch(rs: Any, player: int, candidates: list[Any]) -> None:
        board = len(rs.zones.single("board").cards)
        button, big_blind = rs.get("button"), rs.get("big_blind")
        if board == 0 and not any(rs.get("acted").values()):
            # The pre-flop street's first decision: the blinds are in and
            # nobody has acted, so `bet_by` still holds exactly the posts.
            bet_by = rs.get("bet_by")
            posts.append((bet_by[button], bet_by[big_blind]))
        if board not in seen_streets:
            seen_streets.add(board)
            firsts.append((board, player))

    for seed in range(20):
        seen_streets = set()
        _drive(seed, watch, policy=_always_aggressive)

    assert posts, "no pre-flop opening decision was observed"
    for small, big in posts:
        assert (small, big) == (_SMALL_BLIND, _BIG_BLIND), (
            f"the button posted {small} and the big blind {big} — heads-up the "
            f"BUTTON posts the small blind ({_SMALL_BLIND}/{_BIG_BLIND})"
        )

    by_street: dict[int, set[int]] = {}
    for board, seat in firsts:
        by_street.setdefault(board, set()).add(seat)
    assert set(by_street) == set(_STREET_NAME), (
        f"streets observed: {sorted(by_street)} — expected all of "
        f"{sorted(_STREET_NAME)}"
    )
    assert by_street[0] == {0}, (
        f"pre-flop was opened by {by_street[0]} — heads-up the button (seat 0, "
        f"the small blind) acts first pre-flop"
    )
    for board in (3, 4, 5):
        assert by_street[board] == {1}, (
            f"the {_STREET_NAME[board]} was opened by {by_street[board]} — "
            f"every street after the flop is opened by the big blind (seat 1)"
        )
