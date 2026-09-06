"""Random-playout harness for Scopa, with a fixed-deal scoring oracle.

Two instruments, because they fail on different things.

The **reconstruction** rebuilds the layout and every capture from observer 0's
movement stream — `table`, `played` and both capture piles are identity to
every observer (cardlang/stdlib/zones.py ZONE_PROJECTIONS), so the stream
carries card identity at every transfer this reads. Against that it recomputes
the two rules a wrong capture would break, without asking the engine: a played
card that matches a single layout card takes exactly that one card, and a
capture's cards sum to the played card. Both are decidable from the layout
alone, so neither recomputation shares code with the Primitives it checks.

The **pinned-match oracle** settles a whole match from one shuffle seed, then
scores every deal's capture piles by hand — cards, coins, settebello,
primiera, scopas — and asserts the match score the game awarded. Each deal's
piles are a partition of the forty cards, so hand-scoring them shares nothing
with the game's own scoring functions; a wrong primiera or a mis-taken point
is a contradiction rather than a plausible number. A separate cell holds the
pinned match to separating the categories, because a match in which one seat
takes everything cannot tell a wrong primiera from a right one.

A uniform-random layout would leave the layout-size claim resting on whatever
the seeds happened to show, so it is asserted against the deck's own
arithmetic instead: after the deal no two layout cards can share a capture
value (a played card matching one is forced to take it), so the layout holds
at most the distinct capture values the deck has, plus whatever duplicates the
four face-up cards arrived with.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.scopa import DECK_CAPTURE_VALUES
from cardlang.runtime.values import Player

SCOPA = Path(__file__).parent.parent / "docs" / "games" / "scopa.cardlang"

_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}

# The primiera scale, from the rules source — the same table the game file
# declares as its `card_points { }` clause, authored here so the oracle scores
# independently of what the game reads.
PRIMIERA = {"7": 21, "6": 18, "A": 16, "5": 15, "4": 14, "3": 13, "2": 12}
COURT_PRIMIERA = 10

TARGET = 11  # the match score Pagat states

# One shuffle seed, so the settlement below is the same match every run.
# Chosen for separation rather than arbitrarily: its deals give the cards to
# one seat and the primiera to the other, and are swept, which is what
# `test_the_pinned_match_separates_the_scoring_categories` holds it to.
PINNED_SEED = 13


def _parse(card_str: str) -> tuple[str, str]:
    """(rank, suit) of a rendered card string (`K♣` -> (`K`, `clubs`))."""
    return card_str[:-1], _SUITS[card_str[-1]]


def _seat(label: str, family: str) -> int:
    return int(label[len(family) + 1 : -1])


def _value(card: tuple[str, str]) -> int:
    return DECK_CAPTURE_VALUES[card[0]]


class ScopaPlay:
    """Layout and capture reconstruction from observer 0's movement stream.

    The layout is rebuilt transfer by transfer rather than read off the engine,
    so the capture checks below are an independent oracle: they see what an
    observer sees and recompute the rule from it.
    """

    def __init__(self) -> None:
        self.layout: list[tuple[str, str]] = []
        self.in_play: tuple[str, str] | None = None
        self.layout_peak = 0
        # (player, played card, captured layout cards, layout before the play).
        self.captures: list[
            tuple[Player, tuple[str, str], list[tuple[str, str]], list[tuple[str, str]]]
        ] = []
        self.plays = 0
        self.no_capture = 0
        self.sweeps: list[Player] = []
        self.piles: dict[Player, list[tuple[str, str]]] = {0: [], 1: []}
        self._before: list[tuple[str, str]] = []
        self._taken: list[tuple[str, str]] = []
        self.sweep_zone_drains = 0
        # One settled deal: its final capture piles and the sweeps in it. A
        # deal closes when its cards are gathered back to the deck; the last
        # one is closed by `close_deal` after the match ends.
        self.deals: list[tuple[dict[Player, list[tuple[str, str]]], list[Player]]] = []

    def close_deal(self) -> None:
        if any(self.piles.values()):
            self.deals.append(({p: list(c) for p, c in self.piles.items()}, list(self.sweeps)))
            self.piles = {0: [], 1: []}
            self.sweeps = []

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if player != 0 or event[0] != "move":
            return
        _, src, _src_view, dst, dst_view = event
        if dst == "deck":
            # Every gather: the one that opens a deal (closing the one before
            # it) and the three-kings misdeal's. The deck is count-only to
            # every observer, so this arm reads the labels and not the view.
            self.close_deal()
            self.layout.clear()
            return
        # A count-only projection arrives as a bare int (a deal into the other
        # seat's hand); only the identity zones this reconstruction consumes
        # carry card strings, and every branch below names one.
        if not isinstance(dst_view, (list, tuple)):
            return
        cards = [_parse(c) for c in dst_view]

        if dst == "played" and isinstance(src, str) and src.startswith("hand["):
            (card,) = cards
            self.in_play = card
            self._before = list(self.layout)
            self._taken = []
            self.plays += 1
        elif src == "table" and isinstance(dst, str) and dst.startswith("captured["):
            for c in cards:
                self.layout.remove(c)
            self._taken.extend(cards)
            if self.in_play is None:
                # The end-of-deal sweep of the remaining layout, which is not a
                # capture and arrives with no card in play.
                self.sweep_zone_drains += 1
                self.piles[_seat(dst, "captured")].extend(cards)
                self._taken = []
        elif src == "played" and isinstance(dst, str) and dst.startswith("captured["):
            seat = _seat(dst, "captured")
            assert self.in_play is not None
            self.captures.append((seat, self.in_play, list(self._taken), self._before))
            self.piles[seat].extend(self._taken)
            self.piles[seat].append(self.in_play)
            if not self.layout:
                self.sweeps.append(seat)
            self.in_play = None
        elif src == "played" and dst == "table":
            assert self.in_play is not None
            self.layout.append(self.in_play)
            self.no_capture += 1
            self.in_play = None
        elif dst == "table" and src == "deck":
            self.layout.extend(cards)
        elif src == "table":
            for c in cards:
                self.layout.remove(c)

        self.layout_peak = max(self.layout_peak, len(self.layout))


def _scopa() -> Any:
    return check_source(SCOPA)


def _check_capture_rules(recon: ScopaPlay, label: str) -> None:
    """The two capture rules, recomputed from the observed layout."""
    for seat, played, taken, before in recon.captures:
        target = _value(played)
        singles = [c for c in before if _value(c) == target]
        assert taken, f"{label}: seat {seat} captured nothing with {played}"
        if singles:
            assert len(taken) == 1, (
                f"{label}: a single {target} was on the layout ({singles}) but "
                f"{played} took {taken} — the single-card match is forced"
            )
            assert _value(taken[0]) == target, f"{label}: {taken} is not a match for {played}"
        else:
            assert len(taken) >= 2, f"{label}: {played} took {taken} with no single match"
            assert sum(_value(c) for c in taken) == target, (
                f"{label}: {taken} does not sum to {played}"
            )
        for c in taken:
            assert c in before, f"{label}: {c} was not on the layout"


def _hand_score(piles: dict[Player, list[tuple[str, str]]], sweeps: list[Player]) -> dict[int, int]:
    """The five components, scored from the final capture piles alone."""

    def coins(p: Player) -> int:
        return sum(1 for c in piles[p] if c[1] == "diamonds")

    def prime(p: Player) -> tuple[bool, int]:
        best: dict[str, int] = {}
        for rank, suit in piles[p]:
            best[suit] = max(best.get(suit, 0), PRIMIERA.get(rank, COURT_PRIMIERA))
        return len(best) == 4, sum(best.values())

    out = {p: sweeps.count(p) for p in piles}
    seats = sorted(piles)
    for measure in (lambda p: len(piles[p]), coins):
        top = max(measure(p) for p in seats)
        holders = [p for p in seats if measure(p) == top]
        if len(holders) == 1:
            out[holders[0]] += 1
    for p in seats:
        if ("7", "diamonds") in piles[p]:
            out[p] += 1
    eligible = {p: prime(p) for p in seats}
    ranked = [p for p in seats if eligible[p][0]]
    if ranked:
        top = max(eligible[p][1] for p in ranked)
        holders = [p for p in ranked if eligible[p][1] == top]
        if len(holders) == 1:
            out[holders[0]] += 1
    return out


# =============================================================================
# Random playouts: the reconstruction against the rules
# =============================================================================


@pytest.mark.slow
def test_random_games_obey_the_capture_rules() -> None:
    """Every capture of every deal, checked against the layout an observer saw.

    red under: swap `is` for `is not` in the game file's single-match
    movement filter."""
    game = _scopa()
    seen_singles = 0
    seen_sums = 0
    seen_sweeps = 0
    for seed in range(40):
        census: dict[str, int] = {}

        def tracer(event: str, data: Any) -> None:
            if event == "game_end":
                census.clear()  # noqa: B023 -- consumed before the loop advances
                census.update(data)  # noqa: B023 -- consumed before the loop advances

        recon = ScopaPlay()
        result = play_game(game, random.Random(seed), tracer, observer=recon.observer)
        recon.close_deal()

        assert census["total"] == 40, f"seed {seed}: {census}"
        assert recon.plays, f"seed {seed}: no plays reconstructed"
        assert recon.captures, f"seed {seed}: no captures reconstructed"
        _check_capture_rules(recon, f"seed {seed}")

        # The match ends with a lone leader at or past the target.
        top = max(result.scores.values())
        assert top >= TARGET, f"seed {seed}: {result.scores}"
        assert [p for p, s in result.scores.items() if s == top] == [result.winner]

        # Every card ends in a capture pile: the layout is empty at the end of
        # each deal, swept by the last capturer.
        assert not recon.layout, f"seed {seed}: {recon.layout} left on the layout"
        assert len(recon.deals) == result.hands_played, f"seed {seed}: {len(recon.deals)} deals"
        for piles, _sweeps in recon.deals:
            assert len(piles[0]) + len(piles[1]) == 40, f"seed {seed}: {piles}"

        seen_singles += sum(1 for c in recon.captures if len(c[2]) == 1)
        seen_sums += sum(1 for c in recon.captures if len(c[2]) > 1)
        seen_sweeps += sum(len(s) for _p, s in recon.deals)

    # The anti-vacuity floor: the checks above would pass on a run that never
    # took a sum-capture or never swept the layout.
    assert seen_singles and seen_sums and seen_sweeps, (
        f"singles={seen_singles} sums={seen_sums} sweeps={seen_sweeps}"
    )


@pytest.mark.slow
def test_the_layout_never_outgrows_the_decks_own_arithmetic() -> None:
    """After the deal no two layout cards share a capture value, because a
    played card matching one must take it — so the layout holds at most the
    deck's distinct capture values plus the duplicates the four face-up cards
    can arrive with. The joint form refuses a source pool past sixteen cards
    (cardlang/runtime/execute.py), and this is why Scopa never meets that.

    red under: change the game file's single-match guard to
    `capture_value(card) is 0`, so a played card leaves its match on the
    layout and duplicate capture values accumulate there."""
    game = _scopa()
    ceiling = len(set(DECK_CAPTURE_VALUES.values())) + 3
    peak = 0
    for seed in range(40):
        recon = ScopaPlay()
        play_game(game, random.Random(seed), None, observer=recon.observer)
        assert recon.layout_peak <= ceiling, f"seed {seed}: layout reached {recon.layout_peak}"
        peak = max(peak, recon.layout_peak)
    assert peak > 4, f"the layout never grew past the deal ({peak}) — the bound is untested"


# =============================================================================
# The pinned match: hand-computed scoring
# =============================================================================


def _pinned_match() -> tuple[Any, ScopaPlay]:
    """The pinned match: one shuffle seed, the chooser the driver defaults to,
    every deal reconstructed."""
    game = _scopa()
    recon = ScopaPlay()
    result = play_game(game, random.Random(PINNED_SEED), None, observer=recon.observer)
    recon.close_deal()
    return result, recon


@pytest.mark.slow
def test_the_pinned_match_scores_what_the_piles_say() -> None:
    """The match score against a by-hand settlement of every deal's capture
    piles.

    Each deal's piles are a partition of the pack, so this scores the same
    deals by a route sharing no code with the game's five scoring functions: it
    counts cards and diamonds, looks for the seven of diamonds, takes each
    seat's best card per suit on the primiera scale, and adds the sweeps the
    observation stream recorded. A wrong capture, a wrong primiera or a
    mis-taken point contradicts it rather than moving it plausibly.

    red under: change `card.suit is diamonds` to `card.suit is hearts` in the
    game file's `coins_taken`."""
    result, recon = _pinned_match()
    assert len(recon.deals) == result.hands_played, (
        f"reconstructed {len(recon.deals)} deals against {result.hands_played} played"
    )
    total = {p: 0 for p in result.scores}
    for piles, sweeps in recon.deals:
        assert len(piles[0]) + len(piles[1]) == 40, f"a deal settled {piles} cards"
        for p, points in _hand_score(piles, sweeps).items():
            total[p] += points
    assert dict(result.scores) == total, (
        f"engine {dict(result.scores)} against a hand settlement {total}"
    )


@pytest.mark.slow
def test_the_pinned_match_separates_the_scoring_categories() -> None:
    """The oracle above is only discriminating if the categories disagree: a
    deal where one seat takes everything cannot tell a wrong primiera from a
    right one. This holds the pinned match to separating them — some deal in it
    gives the cards to one seat and the primiera to the other, some deal is
    swept, and some deal ends with the layout going to the last capturer.

    red under: none needed; this cell IS the discrimination floor for the cell
    above, and a pinned match that stopped separating the categories reddens
    here rather than quietly weakening that oracle."""
    _result, recon = _pinned_match()
    assert recon.deals, "no deals reconstructed"

    def prime_total(pile: list[tuple[str, str]]) -> int:
        best: dict[str, int] = {}
        for rank, suit in pile:
            best[suit] = max(best.get(suit, 0), PRIMIERA.get(rank, COURT_PRIMIERA))
        return sum(best.values())

    split = 0
    for piles, _sweeps in recon.deals:
        if len(piles[0]) == len(piles[1]) or prime_total(piles[0]) == prime_total(piles[1]):
            continue
        cards_leader = max(piles, key=lambda p: len(piles[p]))
        prime_leader = max(piles, key=lambda p: prime_total(piles[p]))
        split += cards_leader != prime_leader
    assert split, "cards and primiera went the same way in every deal"
    assert any(sweeps for _piles, sweeps in recon.deals), "no scopa in the pinned match"
    assert recon.sweep_zone_drains, "the layout was never swept to the last capturer"
