"""Random-playout harness for Go Fish.

Go Fish is the corpus witness for declared move-parameter domains: `ask(target:
Player, rank: Rank)` is offered via a plain `offer`, enumerating the
guard-filtered Player x Rank cross-product
(docs/decisions.md "Declared parameter domains") rather than the
nullary-move-type explosion an earlier stress-branch skeleton was forced into.
Its falsifiable invariants are conservation (52 cards, always somewhere across
deck/hand/book) and termination (every hand empties or the stock runs out, and
the player with the most books wins).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GO_FISH = Path(__file__).parent.parent / "docs" / "games" / "go-fish.cardlang"


def _go_fish() -> n.Game:
    return check_source(GO_FISH)


def test_go_fish_checks_clean() -> None:
    _go_fish()  # parse -> resolve -> typecheck -> deck-capacity; must not raise


@pytest.mark.parametrize("seed", range(30))
def test_go_fish_plays_to_completion(seed: int) -> None:
    game = _go_fish()
    census: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            census.update(data)

    result = play_game(game, random.Random(seed), tracer)

    # A "most books wins" game: a winner, never an elimination loser.
    assert result.loser is None
    assert result.winner is not None
    assert set(result.scores) == set(range(game.players.low))
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])

    # Card conservation: every one of the 52 cards is still somewhere (stock,
    # a hand, or a shown-and-set-aside book) — none lost or duplicated.
    assert census["total"] == 52, f"seed {seed}: {census}"

    # At most 13 books can ever be completed (one per rank; a rank's four
    # cards can be split across hands/deck without ever completing a book).
    assert sum(result.scores.values()) <= 13, f"seed {seed}: {result.scores}"


def test_setup_phase_sweeps_an_opening_quad_book() -> None:
    """`phase setup` immediately books any rank a player is dealt all four of
    within their opening 5-card hand (docs/games/go-fish.cardlang). This is a
    ~0.1%-per-deal event (13 ranks x 4 players, each needing a specific
    4-of-a-kind among 5 dealt cards) — no seed in 0..29 (the range this
    module's other tests sweep) happens to trigger it, so the sweep has had
    zero coverage.

    The deck's post-shuffle order is a pure function of the `random.Random`
    seed: `shuffle deck` calls `rng.shuffle` exactly once, and `deal 5 cards
    ... to each hand` (no `chosen`/`random` selection mode) then slices the
    top 5 cards to player 0, the next 5 to player 1, and so on — deterministic
    slicing, no further rng draws. So a plain seed search over
    `play_game(game, random.Random(seed))` is the direct, honest way to force
    the deal — there is no need to bypass the DSL's own shuffle/deal
    statements with a hand-constructed zone. Seed 470 was found by such a
    search: it deals player 3 all four 7s (plus the 8 of hearts) as their
    opening hand.

    `on_first_decision` fires inside the FIRST chooser call — the first
    `offer` in `phase play` — which lands strictly after `phase setup`
    completes (setup makes no decisions of its own) and strictly before any
    play-phase mutation. So it is used here purely to INSPECT the post-setup,
    pre-play state, never to mutate it (unlike its swap use in
    tests/openspiel_ready/harness.py)."""
    game = _go_fish()
    captured: dict[str, Any] = {}

    def _capture(rs: Any) -> None:
        captured["book_count"] = dict(rs.get("book_count"))
        captured["hand"] = list(rs.zones.instance("hand", 3).cards)
        captured["book"] = list(rs.zones.instance("book", 3).cards)

    play_game(game, random.Random(470), on_first_decision=_capture)

    assert captured["book_count"][3] == 1
    assert len(captured["hand"]) == 1  # 5 dealt - 4 booked = 1 left
    assert len(captured["book"]) == 4
    assert {c.rank for c in captured["book"]} == {"7"}


def test_asks_actually_complete_books() -> None:
    # Termination and card conservation alone would hold even if `ask`'s
    # give-all-matching / go-fish-and-match branches were both dead (e.g. a
    # guard bug that always missed) — the game would still empty a hand or
    # drain the stock with zero books ever formed. Prove the mechanic this
    # game exists to witness actually fires: aggregate books formed across a
    # seed sweep (not a single seed, which can legitimately end at 0 on a
    # short game — seed 0 does) is reliably positive.
    game = _go_fish()
    total_books = sum(
        sum(play_game(game, random.Random(seed)).scores.values())
        for seed in range(30)
    )
    assert total_books > 0
