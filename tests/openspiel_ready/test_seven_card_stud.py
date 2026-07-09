"""Seven-Card Stud — OpenSpiel readiness.

Hidden zone `hole`: Stud's hidden cards live in `hole` (its `upcards` are
public); everyone else in the corpus hides a `hand`.

`swap_axis="any"`: Stud's recorded actions are betting vocabulary — none names
a card — so ANY hole swap replays legally (and its two-card holes rarely
share a suit, so the harness's default same-suit filter would starve the
pool).

Bounded conformance walk: full `pyspiel.random_sim_test` re-simulates the
whole (seed, history) state after every action — O(n^2) in game length — and
a Stud game runs until one player holds all 400 chips: ~486 hands x ~21
decisions ~ 10k actions, which extrapolates to a ~15-minute median full sim.
"""

from typing import Any

import pytest

from cardlang.openspiel.replay import Pause, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_seven_card_stud",
        "seven-card-stud.cardlang",
        hidden_zone="hole",
        conformance_steps=120,
        swap_axis="any",
    )


def _is_reveal_event(e: tuple[Any, ...]) -> bool:
    """A Stud showdown reveal (the park-then-flip `hole[p] -> upcards[p]`
    movement in seven-card-stud.cardlang's showdown block) as any NON-owner
    sees it: `hole[p]` collapses to a count (the owner's own view of the same
    event is a 7-card identity tuple, filtered out here) while `upcards[p]` —
    a PublicHand — stays identity for every observer, all seven merged cards
    landing in the clear at once."""
    return bool(
        e[0] == "move"
        and isinstance(e[1], str) and e[1].startswith("hole[")
        and isinstance(e[2], int)
        and isinstance(e[3], str) and e[3].startswith("upcards[")
        and isinstance(e[4], tuple) and len(e[4]) == 7
    )


def test_showdown_reveals_contenders_holes_to_others() -> None:
    """The showdown block is the one place a Stud hand's hidden hole cards
    become public — and it is exactly what the score goldens can't see (the
    scores are provably insensitive to the reveal) and what the four harness
    proofs never reach (their swaps pause pre-showdown, at the spec's default
    depth). This drives an actual hand past it and inspects the emitted
    events directly: a non-owner learns all seven of a contender's cards at
    once (count-only source, full-identity dest); a folded entrant's
    still-hidden hole cards muck count-only, with no identity leak to anyone
    else.

    The policy is `legal[0]` (check/call, the betting vocabulary's id order
    52..56) throughout, which alone reaches a contested 4-entrant showdown —
    nobody ever folds under it, since call and fold share a guard
    (`bet_to_match > bet_by[actor]`) and call's id sorts lower — except the
    first time `fold` itself is offered, where it is taken once, on purpose,
    to also exercise the folded-entrant guard in the same hand.
    """
    path = str(GAMES_DIR / "seven-card-stud.cardlang")
    game, space = load(path)
    seed = 3

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    folded_player: int | None = None
    reveal: dict[int, tuple[Any, ...]] = {}  # contender -> a non-owner's view of their reveal
    for _ in range(40):
        names = [space.to_string(a) for a in r.legal]
        if folded_player is None and "fold" in names:
            folded_player = r.player
            aid = r.legal[names.index("fold")]
        else:
            aid = r.legal[0]
        history.append(aid)
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the hand ended before a showdown reveal was observed"
        r = nxt
        for log in r.obs_logs.values():
            for e in log:
                if _is_reveal_event(e):
                    reveal[int(e[3][len("upcards["):-1])] = e
        if reveal:
            break
    else:
        pytest.fail("no contested stud showdown reveal within 40 steps")
    assert folded_player is not None, "the drive never saw a legal fold to take"

    contenders = set(reveal)
    assert len(contenders) > 1, "need a CONTESTED showdown (more than one contender)"
    assert contenders == set(range(game.players.low)) - {folded_player}

    # Every contender's reveal is visible to a NON-contender observer (the
    # folded entrant): source count-only over the merged 7-card hand, dest
    # identity with all seven card names.
    folded_log = r.obs_logs[folded_player]
    for p in contenders:
        src, dst = f"hole[{p}]", f"upcards[{p}]"
        matches = [
            e for e in folded_log if _is_reveal_event(e) and e[1] == src and e[3] == dst
        ]
        assert matches, f"P{folded_player} never observed contender {p}'s reveal"
        event = matches[0]
        assert event[2] == 7, "the source view must be count-only over all seven cards"
        assert len(event[4]) == 7 and all(isinstance(c, str) for c in event[4])

    # Converse guard: the folded entrant's own hole cards were never
    # revealed. Their eventual hole -> muck event must stay count-only
    # (trivial dest) in every OTHER player's log — only the owner's own log
    # may show identity, and that isn't a leak.
    saw_fold_muck = False
    for q, log in r.obs_logs.items():
        if q == folded_player:
            continue
        for e in log:
            if e[0] == "move" and e[1] == f"hole[{folded_player}]" and e[3] == "muck":
                saw_fold_muck = True
                assert isinstance(e[2], int), (
                    f"P{q} saw the folded entrant's hole-card identity leak into the muck"
                )
                assert e[4] is None
    assert saw_fold_muck, "the folded entrant's hole cards were never observed mucking"
