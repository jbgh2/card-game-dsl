"""Stud's two seats, as the `stud` family library defines them.

`bring_in_seat()` (the lowest door card) and `best_showing_seat()` (the best
hand showing) are DSL functions in `docs/libraries/stud.cardlang`. Each is
evaluated here on hand-built boards, through the library exactly as a stud game
splices it in, and answered two ways: by Pagat's own worked examples, pinned
because an order that happened to agree on easier cases would rank them
backwards, and by `pagat_showing_key`, an independent Python statement of the
same rule, over seeded random boards drawn to be dense in pairs.

One rule, one selector: the street's opener is the best POKER hand showing, so
multiplicity is read ahead of card value. A lexicographic compare of card values
would rank Pagat's own worked example backwards.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import cache

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import RANKS, SUITS, Card, Player, Seating

_SUIT = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}


def _c(rank: str, suit: str) -> Card:
    return Card(rank, _SUIT[suit])


# The smallest game that satisfies the library's `requires` contract, asking
# one selector. `stack` is declared and ignored by both selectors, so a
# chip-filtered selector would RUN here and answer a funded seat rather than
# fail for want of the name: what the chip cases below red on is the seat
# choice, which is the whole of what they are about.
_GAME = """
game G {{
  players: {players}
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: aces high
  uses stud
  zones {{ deck : Deck  upcards[player] : PublicHand<player> }}
  state {{
    stack[player] : Integer = 100  folded[player] : Boolean = false
    lowest_suit : Suit = clubs  second_suit : Suit = diamonds  third_suit : Suit = hearts
  }}
  phase p {{
    let seat = {selector}()
  }}
  winner: highest stack
}}
"""


@cache
def _probe(players: int, selector: str) -> tuple[n.Game, n.Expr]:
    game = check_dsl(_GAME.format(players=players, selector=selector), "stud-seat.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.LetStmt)
    return game, stmt.value


def _no_choice(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("a seat selector makes no decision")


def _seat(
    selector: str,
    boards: Mapping[Player, Sequence[Card]],
    folded: frozenset[Player] = frozenset(),
    stack: Mapping[Player, int] | None = None,
) -> Player:
    """The seat `selector` names over `boards` (seat -> face-up cards, in the
    order dealt), under the same `ranking:` and function index the driver
    loads."""
    players = len(boards)
    game, expr = _probe(players, selector)
    seats = tuple(range(players))
    rs = RuntimeState(Seating(players), ZoneStore(game.zones, seats), random.Random(0))
    rs.rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    rs.function_index = {f.name: f for f in game.functions}
    rs.push_frame()
    rs.declare("stack", True, {p: (stack or {}).get(p, 100) for p in seats})
    rs.declare("folded", True, {p: p in folded for p in seats})
    for name, suit in (("lowest_suit", "clubs"), ("second_suit", "diamonds"), ("third_suit", "hearts")):
        rs.declare(name, False, suit)
    for p, cards in boards.items():
        rs.zones.instance("upcards", p).add_all(list(cards))
    seat = evaluate(expr, Ctx(rs=rs, chooser=_no_choice))
    assert isinstance(seat, int)
    return seat


def _best(boards: Mapping[Player, Sequence[Card]], folded: frozenset[Player] = frozenset()) -> Player:
    return _seat("best_showing_seat", boards, folded)


def _bring_in(boards: Mapping[Player, Sequence[Card]], stack: Mapping[Player, int] | None = None) -> Player:
    return _seat("bring_in_seat", boards, stack=stack)


# --- the best hand showing -----------------------------------------------------


def test_best_showing_ranks_multiplicity_ahead_of_card_value() -> None:
    # Pagat's own worked example, three cards showing: "3-3-3 is higher than
    # 7-7-8, which is higher than A-K-Q."
    trips = [_c("3", "C"), _c("3", "D"), _c("3", "H")]
    pair = [_c("7", "C"), _c("7", "D"), _c("8", "H")]
    high = [_c("A", "C"), _c("K", "D"), _c("Q", "H")]
    assert _best({0: high, 1: pair, 2: trips}) == 2
    assert _best({0: high, 1: pair}) == 1


def test_best_showing_orders_every_class_multiplicity_can_show() -> None:
    # Four cards showing: quads > trips > two pair > pair > high card, whatever
    # the card values under them say.
    quads = [_c("2", "C"), _c("2", "D"), _c("2", "H"), _c("2", "S")]
    trips = [_c("3", "C"), _c("3", "D"), _c("3", "H"), _c("4", "S")]
    two_pair = [_c("5", "C"), _c("5", "D"), _c("6", "H"), _c("6", "S")]
    pair = [_c("7", "C"), _c("7", "D"), _c("8", "H"), _c("9", "S")]
    high = [_c("A", "C"), _c("K", "D"), _c("Q", "H"), _c("J", "S")]
    ladder = [high, pair, two_pair, trips, quads]
    for i in range(len(ladder) - 1):
        worse, better = ladder[i], ladder[i + 1]
        assert _best({0: better, 1: worse}) == 0
        assert _best({0: worse, 1: better}) == 1


def test_two_pair_beats_a_higher_pair_whatever_the_kickers() -> None:
    # The shape is read whole before any rank: a pair of kings with an ace
    # kicker is still one pair.
    two_pair = [_c("5", "C"), _c("5", "D"), _c("6", "H"), _c("6", "S")]
    kings = [_c("K", "C"), _c("K", "D"), _c("A", "H"), _c("Q", "S")]
    assert _best({0: kings, 1: two_pair}) == 1


def test_within_a_shape_the_group_is_read_before_its_kickers() -> None:
    # Same shape: the higher pair wins over the higher kicker, and on equal
    # pairs the kickers decide, highest first.
    sevens = [_c("7", "C"), _c("7", "D"), _c("2", "H")]
    sixes = [_c("6", "C"), _c("6", "D"), _c("A", "H")]
    assert _best({0: sixes, 1: sevens}) == 1
    sevens_king = [_c("7", "H"), _c("7", "S"), _c("K", "C")]
    assert _best({0: sevens, 1: sevens_king}) == 1


def test_every_kicker_of_a_five_card_board_has_its_own_place() -> None:
    """Two high-card boards that agree on 8-7-6 differ on the fourth card, so
    the 5 kicker wins whatever suit the eight is.

    red under: drop `place`'s fifth arm, so the fourth and fifth cards share a
    place and 4+3 packs equal to 5+2 — RUN, not predicted: the spade eight then
    opens."""
    low_kickers = [_c("8", "S"), _c("7", "C"), _c("6", "C"), _c("4", "C"), _c("3", "C")]
    five_kicker = [_c("8", "H"), _c("7", "D"), _c("6", "D"), _c("5", "D"), _c("2", "D")]
    assert _best({0: low_kickers, 1: five_kicker}) == 1


def test_best_showing_does_not_count_incomplete_straights_or_flushes() -> None:
    # "Incomplete straights and flushes do not count": four to a straight flush
    # is a high-card board, and the lowest possible pair outranks it.
    straight_flush_draw = [_c("9", "H"), _c("8", "H"), _c("7", "H"), _c("6", "H")]
    lowest_pair = [_c("2", "C"), _c("2", "D"), _c("3", "H"), _c("4", "S")]
    assert _best({0: straight_flush_draw, 1: lowest_pair}) == 1


def test_best_showing_breaks_a_tie_on_the_suit_of_the_highest_card() -> None:
    # Same ranks in both hands, so the suits of the highest card decide, on
    # clubs (low), diamonds, hearts, spades (high).
    assert _best({0: [_c("K", "C"), _c("4", "S")], 1: [_c("K", "S"), _c("4", "C")]}) == 1
    # The tie-break reads the HIGHEST card's suit, not the whole board's best
    # suit: seat 0 holds the only spade and still loses on the king.
    assert _best({0: [_c("K", "D"), _c("4", "S")], 1: [_c("K", "H"), _c("4", "D")]}) == 1


def test_a_folded_or_empty_board_never_opens() -> None:
    # A folder's cards are mucked and an absent seat was dealt none, but either
    # being read would hand it the street: seat 0 is marked folded while still
    # holding the best board, and seat 2 holds nothing.
    best = [_c("A", "C"), _c("A", "D")]
    other = [_c("3", "C"), _c("4", "D")]
    assert _best({0: best, 1: other, 2: []}, folded=frozenset({0})) == 1


def test_an_all_in_board_still_anchors_the_street() -> None:
    # The membership is the cards, not the chips: the seat with no chips left
    # holds the best board and the street is anchored on it.
    boards = {0: [_c("A", "C"), _c("A", "D")], 1: [_c("3", "C"), _c("4", "D")]}
    assert _seat("best_showing_seat", boards, stack={0: 0, 1: 100}) == 0


# --- the bring-in -----------------------------------------------------------------


def test_lowest_door_picks_lowest_rank_then_lowest_suit() -> None:
    # Players 1 and 2 both show a 5; clubs beats diamonds as the lower.
    assert _bring_in({0: [_c("7", "C")], 1: [_c("5", "D")], 2: [_c("5", "C")]}) == 2
    # An ace door is the *highest*, never the bring-in.
    assert _bring_in({0: [_c("A", "S")], 1: [_c("K", "C")], 2: [_c("2", "H")]}) == 2


def test_bring_in_is_the_lowest_door_even_when_that_seat_holds_no_chips() -> None:
    # Seat 2 was left with nothing by the ante and still shows the lowest door.
    # The street is anchored where the card is: chips decide who can PAY, never
    # which card the bring-in is read off. Anchoring on the lowest FUNDED door
    # would bring in seat 1.
    boards = {0: [_c("9", "C")], 1: [_c("7", "D")], 2: [_c("3", "S")]}
    assert _bring_in(boards, stack={0: 100, 1: 100, 2: 0}) == 2


def test_bring_in_skips_a_seat_that_was_dealt_no_cards() -> None:
    # A seat that never entered the hand holds an empty board, which is not a
    # door card to compare — and comparing it would have no first card to read.
    assert _bring_in({0: [_c("9", "C")], 1: [], 2: [_c("5", "H")]}) == 2


# --- against an independent statement of the rule ---------------------------------


def pagat_showing_key(cards: Sequence[Card]) -> tuple[list[int], list[int], tuple[int, int]]:
    """Pagat's order written directly: the shape (rank multiplicities,
    descending), then the ranks ordered by multiplicity and then value, then
    the highest card's (rank, suit)."""
    counts = Counter(RANKS.index(c.rank) for c in cards)
    by_weight = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    top = max((RANKS.index(c.rank), SUITS.index(c.suit)) for c in cards)
    return ([k for _, k in by_weight], [v for v, _ in by_weight], top)


def _random_table(rng: random.Random) -> tuple[dict[Player, list[Card]], frozenset[Player]]:
    """A table of two to eight seats showing one to five cards each, drawn from
    a handful of ranks most of the time so that pairs, two pairs and trips —
    where the shape and the group order decide — are common rather than rare."""
    players = rng.randint(2, 8)
    showing = rng.randint(1, 5)
    deck = [Card(r, s) for r in RANKS for s in SUITS]
    ranks = rng.sample(RANKS, min(len(RANKS), rng.randint(players, 2 * players)))
    pool = [c for c in deck if c.rank in ranks]
    if len(pool) < players * showing or rng.random() < 0.2:
        pool = deck
    cards = rng.sample(pool, players * showing)
    boards = {p: cards[p * showing : (p + 1) * showing] for p in range(players)}
    folded = frozenset(p for p in range(1, players) if rng.random() < 0.2)
    for p in folded:
        boards[p] = []
    return boards, folded


def test_best_showing_agrees_with_pagat_on_random_tables() -> None:
    """red under: in `showing_order`, drop the leading `matching(p) * …` term
    (two pair then loses to a higher pair) — RUN, not predicted: this test
    reds at the first disagreeing table."""
    rng = random.Random(20261011)
    for _ in range(300):
        boards, folded = _random_table(rng)
        live = [p for p in boards if p not in folded and boards[p]]
        want = max(live, key=lambda p: pagat_showing_key(boards[p]))
        assert _best(boards, folded) == want, (boards, folded)


def test_bring_in_agrees_with_the_lowest_door_on_random_tables() -> None:
    rng = random.Random(20261012)
    deck = [Card(r, s) for r in RANKS for s in SUITS]
    for _ in range(200):
        players = rng.randint(2, 8)
        doors = rng.sample(deck, players)
        boards = {p: [doors[p]] if p == 0 or rng.random() > 0.15 else [] for p in range(players)}
        want = min(
            (p for p in boards if boards[p]),
            key=lambda p: (RANKS.index(boards[p][0].rank), SUITS.index(boards[p][0].suit)),
        )
        assert _bring_in(boards) == want, boards
