"""Texas Hold'em: random playouts plus the two rules the invariants can't see.

Chip conservation is the strongest falsifiable check a betting game has, and
Hold'em's blinds make it sharper than Stud's: chips go in every hand whether
anyone acts or not, so a settlement that leaks would show up within a few
hands. It is checked here after EVERY hand, not only at the end.

Conservation is blind to everything about WHO acts and WHAT they are charged, so
each of those rules gets its own test. All four below are rules under which a
broken game still conserves chips, still terminates, and still looks legal:

- which seat posts which blind (`test_heads_up_reverses_the_blinds`);
- that the button rotates strictly once a seat busts
  (`test_button_alternates_strictly_heads_up`) — a button that pauses on dead
  seats hands the same survivor the small blind twice in three hands;
- that a lone live player who still owes the blind is allowed to act
  (`test_a_lone_still_owing_player_is_offered_the_preflop_decision`) — skipping
  them deals the hand out around a live decision;
- that the big blind gets its option on a limped pot
  (`test_big_blind_gets_its_option_after_a_limped_pot`).

The seat-ring skip those three compose with is pinned directly by
`test_next_entrant_*`. Side-pot *misallocation* is likewise invisible to
conservation and is pinned by known-value tests in tests/test_holdem_settle.py.

The hook for the state-reading tests is the chooser: phase state is unwound by
the time a decision surfaces to a caller (`DecisionNode.rs` carries only game-level
names), but the chooser runs INSIDE the phase body with `in_hand`/`bet_by`/
`button` still in scope, and `RuntimeState` is one object for the whole game —
so capturing it at the first decision makes it readable at every later one.
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
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Seating

HOLDEM = Path(__file__).parent.parent / "docs" / "games" / "holdem.cardlang"

_TOTAL_CHIPS = 300  # 3 players x 100 starting chips
_SMALL_BLIND = 2
_BIG_BLIND = 5


def _drive(seed: int, watch: Any) -> None:
    """Play one game, calling `watch(rs, player, hand)` at every decision with
    phase state still in scope (see the module docstring). `hand` is the count of
    COMPLETED hands, taken from the engine's own `hand_end` event — a caller that
    needs per-hand facts must segment on it and never on "the value changed",
    since consecutive hands legitimately repeat a value and collapsing them hides
    exactly the repeats worth testing for.

    The policy is `[:k]` — check/call, never folding — the cheapest one that
    still busts players, since the blinds do the work."""
    game = check_source(HOLDEM)
    box: list[Any] = []
    hands = 0

    def tracer(event: str, data: Any) -> None:
        nonlocal hands
        if event == "hand_end":
            hands += 1

    def on_first_decision(rs: Any) -> None:
        box.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if box:
            watch(box[0], player, hands)
        return list(candidates[:k])

    play_game(game, random.Random(seed), tracer, chooser, None, on_first_decision)


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
    surfaces to a caller (`DecisionNode.rs` carries only game-level names), but the
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


def test_button_alternates_strictly_heads_up() -> None:
    """Once a seat busts, the button must step along the LIVE ring, so heads-up
    it alternates on every hand.

    Rotating the persistent seat through every PHYSICAL position and mapping
    dead seats forward looks equivalent and is not: with seats 1 and 2 live,
    positions 0,1,2 map to buttons 1,2,1, so seat 1 takes the button — and
    heads-up the small blind — on two hands of every three. The game still
    conserves chips and still terminates; it just charges one survivor unfairly.

    red under: restoring `dealer := dealer offset_by left` to `before_each` and
    `button := holdem_next_entrant(dealer)` in the play phase — verified by
    hand, which produced the button sequence [1,2,1,1,2,1,...] and failed this
    module's alternation assertion, then reverted.
    """
    per_hand: dict[int, tuple[int, int]] = {}  # hand index -> (button, live count)

    def watch(rs: Any, player: int, hand: int) -> None:
        in_hand = rs.get("in_hand")
        per_hand[hand] = (rs.get("button"), sum(1 for f in in_hand.values() if f))

    _drive(0, watch)

    # Consecutive HANDS (by the engine's own hand counter), both heads-up.
    pairs = [
        (per_hand[h][0], per_hand[h + 1][0])
        for h in sorted(per_hand)
        if h + 1 in per_hand and per_hand[h][1] == 2 and per_hand[h + 1][1] == 2
    ]
    assert len(pairs) > 3, f"too few consecutive heads-up hands to judge: {pairs}"
    repeats = [(a, b) for a, b in pairs if a == b]
    assert not repeats, (
        f"the button repeated across consecutive heads-up hands "
        f"({len(repeats)} of {len(pairs)} adjacent pairs) — it must alternate, "
        f"or one survivor posts the small blind twice as often"
    )


def test_a_lone_still_owing_player_is_offered_the_preflop_decision() -> None:
    """A big blind all-in for its whole post leaves ONE live player who still
    owes the standing bet. That player must be offered the call/fold, not have
    the hand dealt out around them.

    This is the case a plain "two players can act" guard gets wrong, and only
    pre-flop: the blinds are the one forced post that leaves a standing bet, so
    every later street opens with nobody owing and the two readings agree. The
    hand still conserves chips either way, which is why it needs its own test.

    red under: restoring the pre-flop guard to
    `if (number of players where can_act(player)) >= 2` — verified by hand,
    which dropped this count to 0 across all 12 seeds (it had been skipping 17
    real decisions), then reverted.
    """
    offered = 0

    def watch(rs: Any, player: int, hand: int) -> None:
        nonlocal offered
        if rs.zones.single("board").cards:
            return  # only the pre-flop street has a standing bet at street open
        in_hand, folded, stack = rs.get("in_hand"), rs.get("folded"), rs.get("stack")
        able = [p for p in stack if in_hand[p] and not folded[p] and stack[p] > 0]
        if len(able) == 1 and rs.get("bet_by")[able[0]] < rs.get("bet_to_match"):
            offered += 1

    for seed in range(12):
        _drive(seed, watch)

    assert offered > 0, (
        "no pre-flop decision was ever offered to a lone still-owing player — "
        "either the guard skips them, or the scenario stopped being reachable "
        "and this test no longer proves anything"
    )


def _drive_random(seeds: range, watch: Any) -> None:
    """`_drive` with a RANDOM policy rather than check/call.

    The policy is load-bearing for the two tests below, and getting it wrong is
    how the raise-cap branch was once measured "unreachable": an always-raise
    policy busts stacks in two or three hands (~170 decisions over 8 seeds),
    which is the fewest possible visits to the deep-betting states it was
    supposed to be probing. Random play runs ~7000 decisions over 15 seeds and
    reaches them routinely. A policy that ends the game fast is not a neutral
    sampler of the game's states.
    """
    game = check_source(HOLDEM)
    for seed in seeds:
        box: list[Any] = []
        rng = random.Random(1000 + seed)

        def on_first_decision(rs: Any) -> None:
            box.append(rs)  # noqa: B023 -- consumed within this seed's playout

        def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
            if box:  # noqa: B023 -- consumed within this seed's playout
                watch(box[0], candidates)  # noqa: B023
            return [rng.choice(candidates)] if k == 1 else list(candidates[:k])  # noqa: B023

        play_game(game, random.Random(seed), None, chooser, None, on_first_decision)


def _able(rs: Any) -> list[int]:
    stack, folded, in_hand = rs.get("stack"), rs.get("folded"), rs.get("in_hand")
    return [p for p in stack if in_hand[p] and not folded[p] and stack[p] > 0]


def test_no_raise_is_offered_when_no_opponent_can_act() -> None:
    """Facing opponents who are all-in, the only legal actions are call and fold.
    Raising into a field that cannot respond is not a poker decision.

    Invisible to every chip check the family has: the side-pot layering returns
    an uncalled excess to its sole contributor, so such a raise is economically
    a no-op. What it corrupts is the ACTION SPACE — a node the rules do not have
    — which is what the OpenSpiel target cannot tolerate. Issue #197.

    red under: dropping `and (number of players where can_act(player)) > 1` from
    `poker_betting`'s `raise` guard — verified by hand, which took this count
    from 0 to 38, then reverted.
    """
    offered = 0

    def watch(rs: Any, candidates: Any) -> None:
        nonlocal offered
        if len(_able(rs)) == 1 and any(c[0] == "raise" for c in candidates):
            offered += 1

    _drive_random(range(15), watch)
    assert offered == 0, (
        f"{offered} decisions offered a raise with no opponent able to respond"
    )


def test_no_raise_is_offered_to_a_stack_that_cannot_exceed_the_call() -> None:
    """A raise must be able to RAISE. A stack that cannot cover more than the
    call pays what it has and leaves `bet_to_match` where it was — so offering
    `raise` there bumps `raises` and clears everyone's `acted`, reopening action
    nobody reopened. A short all-in is a call.

    Sibling of `test_no_raise_is_offered_when_no_opponent_can_act`: same guard,
    same invisibility. The chips are right either way, so only the action space
    and the reopened betting show it.

    red under: dropping `and stack[actor] > bet_to_match - bet_by[actor]` from
    `poker_betting`'s `raise` guard — verified by hand, which took this count
    from 0 to 41, then reverted.
    """
    # Driven like its sibling, but inline rather than through `_drive_random`:
    # this check is per-ACTOR (`stack`/`bet_by` are read at the acting seat), and
    # the chooser's `player` argument is the only place that seat is available.
    offered = 0
    game = check_source(HOLDEM)
    for seed in range(15):
        box: list[Any] = []
        rng = random.Random(1000 + seed)

        def on_first_decision(rs: Any) -> None:
            box.append(rs)  # noqa: B023

        def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
            nonlocal offered
            if box:  # noqa: B023
                rs = box[0]  # noqa: B023
                owed = rs.get("bet_to_match") - rs.get("bet_by")[player]
                if any(c[0] == "raise" for c in candidates) and rs.get("stack")[player] <= owed:
                    offered += 1
            return [rng.choice(candidates)] if k == 1 else list(candidates[:k])  # noqa: B023

        play_game(game, random.Random(seed), None, chooser, None, on_first_decision)

    assert offered == 0, (
        f"{offered} decisions offered a raise to a stack that cannot exceed the call"
    )


def test_a_street_opening_two_handed_lifts_the_raise_cap() -> None:
    """Pagat caps a street at one bet plus three raises only when it opens with
    MORE than two active players; opening two-handed there is no cap.

    Both arms are asserted present, because either alone would pass while the
    rule was half-implemented. Note the discriminator is the count at street
    OPEN: a street that opens three-handed keeps its cap of 4 even after it
    becomes heads-up, which is why capped decisions with two players able are
    expected rather than a defect.

    red under: replacing the per-street assignment with a constant
    `raise_cap := 4` — verified by hand, which emptied the lifted arm, then
    reverted.
    """
    caps: set[int] = set()

    def watch(rs: Any, candidates: Any) -> None:
        caps.add(rs.get("raise_cap"))

    _drive_random(range(15), watch)
    assert 4 in caps, "no street ever ran under the three-or-more-handed cap"
    assert 99 in caps, (
        "no street ever ran with the cap lifted — either the per-street "
        "assignment is gone, or two-handed streets stopped being reached"
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
