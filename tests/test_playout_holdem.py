"""Texas Hold'em: random playouts plus the two rules the invariants can't see.

Chip conservation is the strongest falsifiable check a betting game has, and
Hold'em's blinds make it sharper than Stud's: chips go in every hand whether
anyone acts or not, so a settlement that leaks would show up within a few
hands. It is checked here after EVERY hand, not only at the end.

Conservation is blind to two things, so both get their own test:

- **which** seat posts **which** blind — a wrong blind still conserves chips
  (`test_heads_up_reverses_the_blinds`, driven through the replay API and read
  off the live state at the first pre-flop decision);
- the seat-ring skip past busted players (`test_next_entrant_*`), which decides
  the button and both blinds once a player has been eliminated.

Side-pot *misallocation* is likewise invisible to conservation and is pinned by
known-value tests in tests/test_holdem_settle.py.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.holdem import holdem_next_entrant
from cardlang.runtime.reads import GameReads
from cardlang.runtime.sidecar import EngineFacts
from cardlang.runtime.values import Seating

HOLDEM = Path(__file__).parent.parent / "docs" / "games" / "holdem.cardlang"

_TOTAL_CHIPS = 300  # 3 players x 100 starting chips
_SMALL_BLIND = 2
_BIG_BLIND = 5


def test_12_random_games_satisfy_invariants() -> None:
    game = check_source(HOLDEM)
    start = time.monotonic()
    reached_heads_up = 0
    for seed in range(12):
        census: dict[str, int] = {}
        per_hand: list[dict[int, int]] = []

        def tracer(event: str, data: Any) -> None:
            if event == "hand_end":
                per_hand.append(dict(data))  # noqa: B023 -- consumed after the playout
            elif event == "game_end":
                census.clear()  # noqa: B023 -- consumed after the playout
                census.update(data)  # noqa: B023 -- consumed after the playout

        result = play_game(game, random.Random(seed), tracer)

        # Chip conservation after EVERY hand, not just at the end: the blinds
        # move chips unconditionally, so a settlement leak shows up immediately.
        assert per_hand, f"seed {seed}: no hand completed"
        for i, stacks in enumerate(per_hand):
            assert sum(stacks.values()) == _TOTAL_CHIPS, f"seed {seed} hand {i}: {stacks}"

        # Terminates with exactly one player holding chips; the winner holds all.
        assert sum(result.scores.values()) == _TOTAL_CHIPS, f"seed {seed}: {result.scores}"
        with_chips = [p for p, s in result.scores.items() if s > 0]
        assert len(with_chips) == 1, f"seed {seed}: {result.scores}"
        assert result.winner == with_chips[0]
        assert result.scores[result.winner] == _TOTAL_CHIPS
        # Card conservation.
        assert census["total"] == 52, f"seed {seed}: {census}"

        # A three-player game busting down to one passes THROUGH heads-up, so
        # the blind-reversal branch is live rather than dead code. Counted
        # rather than asserted per seed: this pins that the branch is reached
        # at all, and the reversal's behaviour is `test_heads_up_reverses_the
        # _blinds` below.
        if any(sum(1 for v in s.values() if v > 0) == 2 for s in per_hand):
            reached_heads_up += 1
    assert reached_heads_up == 12, f"only {reached_heads_up}/12 seeds reached heads-up"
    assert time.monotonic() - start < 60  # stays comfortably fast


# --- the blind assignment, which conservation cannot see ---------------------


def test_heads_up_reverses_the_blinds() -> None:
    """Heads-up, the BUTTON posts the small blind (Pagat); with three entrants
    the button posts nothing and the small blind is the seat to its left. Both
    readings conserve chips and both terminate, so nothing else in this file can
    tell them apart — this reads the posted amounts off Hold'em's own live state.

    The hook is the chooser: phase state is unwound by the time a decision
    surfaces to a caller (`Pause.rs` carries only game-level names), but the
    chooser runs INSIDE the phase body with `in_hand`/`bet_by`/`button` still in
    scope. `RuntimeState` is one object for the whole game, so capturing it at
    the first decision makes it readable at every later one.
    """
    game = check_source(HOLDEM)
    box: list[Any] = []
    seen: dict[int, int] = {2: 0, 3: 0}

    def on_first_decision(rs: Any) -> None:
        box.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if box:
            rs = box[0]
            in_hand = rs.get("in_hand")
            bet_by = rs.get("bet_by")
            button = rs.get("button")
            entrants = [p for p, flag in in_hand.items() if flag]
            # The pre-flop street with only the blinds in front of anyone. The
            # exact-total filter is what makes that precise: `open_street` zeroes
            # `bet_by` on every later street, and it also skips the partial-blind
            # case (a seat with one chip posts one), where the amounts asserted
            # below would not be the full 2 and 5.
            if sum(bet_by.values()) == _SMALL_BLIND + _BIG_BLIND:
                posted = {p: bet_by[p] for p in entrants if bet_by[p] > 0}
                if len(entrants) == 2:
                    assert posted.get(button) == _SMALL_BLIND, (
                        f"heads-up: the button (seat {button}) must post the "
                        f"small blind, saw {posted}"
                    )
                    seen[2] += 1
                elif len(entrants) == 3:
                    assert button not in posted, (
                        f"three-handed: the button (seat {button}) posts no "
                        f"blind, saw {posted}"
                    )
                    seen[3] += 1
        return list(candidates[:k])

    play_game(game, random.Random(0), None, chooser, None, on_first_decision)
    assert seen[3] > 0, "never observed a three-handed pre-flop street"
    assert seen[2] > 0, "never observed a heads-up pre-flop street"


def test_big_blind_gets_its_option_after_a_limped_pot() -> None:
    """When everyone merely calls the big blind, the big blind still acts — the
    "option" to raise its own forced bet. This is a rule a ring keyed on debt
    alone would silently drop: the big blind owes nothing (`bet_by == 5 ==
    bet_to_match`), so only `pending`'s `not acted[p]` arm keeps it in.

    Pinned here because Hold'em is the family's first consumer with a forced bet
    that is also a full street's opening bet — Stud's bring-in is posted by a
    seat that still owes the difference up to the limit, so it never exercises
    this arm. Nothing else in this file would notice its loss: a big blind denied
    its option plays a legal-looking, chip-conserving, terminating game.

    red under: rewriting the library's `pending` to `can_act(p) and owes(p)`
    (dropping the `not acted[p]` arm) — verified by hand, which failed this
    module's `assert options > 0` as `assert 0 > 0` and nothing else here, then
    reverted.
    """
    game = check_source(HOLDEM)
    box: list[Any] = []
    options = 0

    def on_first_decision(rs: Any) -> None:
        box.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal options
        if box:
            rs = box[0]
            big_blind = rs.get("big_blind")
            bet_by = rs.get("bet_by")
            if (
                player == big_blind
                and bet_by[big_blind] == rs.get("bet_to_match") == _BIG_BLIND
                and not rs.get("acted")[big_blind]
            ):
                options += 1
        return list(candidates[:k])

    play_game(game, random.Random(1), None, chooser, None, on_first_decision)
    assert options > 0, (
        "the big blind was never offered its option on a limped-around street"
    )


# --- the seat-ring skip -----------------------------------------------------


def _facts(count: int) -> EngineFacts:
    return EngineFacts(
        seating=Seating(count),
        teams=(),
        team_of={},
        rank_index={},
        round_state=None,
        last_round_state=None,
        actor=None,
    )


def _reads(in_hand: dict[int, bool]) -> GameReads:
    return GameReads(state={"in_hand": in_hand}, families={}, singles={})


def test_next_entrant_returns_the_seat_itself_when_it_entered() -> None:
    gr = _reads({0: True, 1: True, 2: True})
    assert holdem_next_entrant(_facts(3), gr, 1) == 1


def test_next_entrant_skips_a_busted_seat() -> None:
    gr = _reads({0: True, 1: False, 2: True})
    assert holdem_next_entrant(_facts(3), gr, 1) == 2


def test_next_entrant_wraps_around_the_ring() -> None:
    gr = _reads({0: True, 1: False, 2: False})
    assert holdem_next_entrant(_facts(3), gr, 1) == 0
    assert holdem_next_entrant(_facts(3), gr, 2) == 0
