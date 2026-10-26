"""The Big Two combination engine held to Pagat's basic game by an independent oracle.

`classify` is a validator written from the rules source
(https://www.pagat.com/climbing/bigtwo.html, "Playable Combinations") that
never calls the engine it judges: given a card-set it answers which
combination it is and a strength that orders it against every other
combination of the same size, or None. The differential runs both directions
over every subset of sampled hands:

- **completeness** — every card-set the oracle accepts is offered by the
  engine's lead query (no legal play withheld), and on the match's opening
  lead every legal combination holding the 3♦ is offered;
- **soundness** — every play the engine offers is a combination of the kind
  it claims, offered once;
- **follows** — the engine's legal follows over a standing play are exactly
  the hand's combinations the oracle says beat it;
- **live** — across whole matches of the game file, every lead and follow
  the climbing round asks for is the oracle's set on the live hand and
  standing play, and every hand's opening lead is the 3♦ holder's.

The hand generators cover the five-card shapes a uniform deal rarely holds
(quads, several flushes, straight flushes, overlapping full houses) by
drawing from narrowed decks.

What a green here does not prove: nothing about the climbing ring (who is
asked, when a trick ends — `tests/test_round_forms.py` and the pass witness
in `tests/test_playout_bigtwo.py`), nothing about the action-id bijection (`tests/test_bigtwo_universe.py`
pins the universe), and nothing about play order in live games (the goldens).

Completeness ledger:
  domain      : every subset of a hand of size 1, 2, 3, 5 — Big Two has no
                four-card play and nothing larger than five (Pagat) — so the
                candidate domain is closed and enumerated whole per hand.
  oracle      : `classify`, written from the page, sharing no table or
                function with `cardlang/runtime/bigtwo.py`.
  held by     : this differential (a Pin), the engine having no type that
                could state "every subset the rules accept".
  red under   : any candidate the engine withholds — the one-representative-
                per-rank enumeration this module replaced fails completeness
                on the first sampled hand holding a rank twice.
"""

from __future__ import annotations

import itertools
import random
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from cardlang.runtime import narrowing, reads
from cardlang.runtime.bigtwo import ROW, Play, bigtwo_follows, bigtwo_lead_options, bigtwo_universe
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import RANKS, SUITS, Card, Seating

# ---------------------------------------------------------------------------
# The oracle: the page's rules, restated without the engine's tables
# ---------------------------------------------------------------------------

# "the cards ranking from high to low: 2-A-K-Q-J-10-9-8-7-6-5-4-3"
_HIGH = "2 A K Q J 10 9 8 7 6 5 4 3".split()
_ORDER = {r: len(_HIGH) - i for i, r in enumerate(_HIGH)}
# "an ordering of suits — from high to low: spades, hearts, clubs, diamonds"
_SUIT_ORDER = {"spades": 4, "hearts": 3, "clubs": 2, "diamonds": 1}
# Straights: "Twos do not rank high in straights, but below the 3 … Aces can be
# counted as low to make the lowest type of straight 5-4-3-2-A … An ace can be
# used at either end of a straight, but not in the middle". The sequence below
# is the natural order with the ace at both ends; a straight is five adjacent
# entries, ranked by its highest entry.
_NATURAL = "A 2 3 4 5 6 7 8 9 10 J Q K A".split()
# "In ascending order they are: straight, flush, full house, four of a kind,
# straight flush."
_TYPE = {"straight": 1, "flush": 2, "fullhouse": 3, "quads": 4, "straightflush": 5}


def _straight_top(ranks: list[str]) -> int | None:
    """The index in `_NATURAL` of the straight's highest card, or None when
    the five ranks are not consecutive there."""
    wanted = sorted(ranks)
    for top in range(4, len(_NATURAL)):
        if sorted(_NATURAL[top - 4 : top + 1]) == wanted:
            return top
    return None


def classify(cards: frozenset[Card]) -> tuple[str, tuple[int, ...]] | None:
    """`(kind, strength)` if `cards` is one Big Two combination, else None.
    Strengths compare only within one size; five-card strengths lead with the
    type, so a stronger type beats any weaker one."""
    cs = sorted(cards, key=lambda c: (_ORDER[c.rank], _SUIT_ORDER[c.suit]), reverse=True)
    ranks = Counter(c.rank for c in cs)
    suits = {c.suit for c in cs}
    n = len(cs)
    if n == 1:
        # "between cards of the same rank a higher suit beats a lower suit"
        return "single", (_ORDER[cs[0].rank], _SUIT_ORDER[cs[0].suit])
    if n == 2 and len(ranks) == 1:
        # "Between equal ranked pairs, the one containing the highest suit is better"
        return "pair", (_ORDER[cs[0].rank], max(_SUIT_ORDER[c.suit] for c in cs))
    if n == 3 and len(ranks) == 1:
        return "triple", (_ORDER[cs[0].rank],)
    if n != 5:
        return None
    top = _straight_top([c.rank for c in cs])
    if top is not None:
        top_card = next(c for c in cs if c.rank == _NATURAL[top])
        # "When the ranks are the same, the suit of the top card determines";
        # straight flushes: "the rank of the highest card … then … the higher suit"
        kind = "straightflush" if len(suits) == 1 else "straight"
        return kind, (_TYPE[kind], top, _SUIT_ORDER[top_card.suit])
    if len(suits) == 1:
        # "A flush in a higher suit beats a flush in a lower suit, irrespective of
        # the ranks … Between two flushes in the same suit, the one with the
        # higher top card is better"
        return "flush", (_TYPE["flush"], _SUIT_ORDER[cs[0].suit], _ORDER[cs[0].rank])
    shape = sorted(ranks.values())
    if shape == [2, 3]:
        triple = next(r for r, k in ranks.items() if k == 3)
        return "fullhouse", (_TYPE["fullhouse"], _ORDER[triple])
    if shape == [1, 4]:
        # "all four cards of one rank, plus any fifth card"
        four = next(r for r, k in ranks.items() if k == 4)
        return "quads", (_TYPE["quads"], _ORDER[four])
    return None


def legal_plays(hand: list[Card]) -> dict[frozenset[Card], tuple[str, tuple[int, ...]]]:
    """Every combination the hand holds, by card-set."""
    out: dict[frozenset[Card], tuple[str, tuple[int, ...]]] = {}
    for size in (1, 2, 3, 5):
        for subset in itertools.combinations(hand, size):
            key = frozenset(subset)
            found = classify(key)
            if found is not None:
                out[key] = found
    return out


# ---------------------------------------------------------------------------
# Hands
# ---------------------------------------------------------------------------

DECK = [Card(r, s) for s in SUITS for r in RANKS]


def _hands() -> Iterator[list[Card]]:
    """Uniform deals, plus deals from narrowed decks: five consecutive ranks
    (quads, full houses, straights in many suit patterns) and two suits
    (several flushes and straight flushes in one hand)."""
    rng = random.Random(962)
    for _ in range(40):
        yield rng.sample(DECK, 13)
    for _ in range(40):
        start = rng.randrange(len(_NATURAL) - 5)
        window = set(_NATURAL[start : start + 5])
        yield rng.sample([c for c in DECK if c.rank in window], 13)
    for _ in range(40):
        two = set(rng.sample(SUITS, 2))
        yield rng.sample([c for c in DECK if c.suit in two], 13)


def _bundles(opened: bool) -> tuple[narrowing.EngineFacts, reads.GameReads]:
    """The bundles a Big Two climb query receives, built for real: the row's
    one state read is `opened`."""
    from cardlang.ast import nodes as n

    decls = (n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),)
    rs = RuntimeState(Seating(4), ZoneStore(decls, (0, 1, 2, 3)), random.Random(0))
    rs.push_frame()
    rs.declare("opened", False, opened)
    return narrowing.bind(rs, None, ROW)


def _offered(plays: list[Play]) -> Counter[frozenset[Card]]:
    return Counter(frozenset(p.cards) for p in plays)


# ---------------------------------------------------------------------------
# The differential
# ---------------------------------------------------------------------------


def test_the_oracle_names_the_pages_examples() -> None:
    """The oracle against the page's own worked examples, so a misreading of
    the source reddens here rather than agreeing with the engine."""

    def c(spec: str) -> Card:
        rank, suit = spec[:-1], {"s": "spades", "h": "hearts", "c": "clubs", "d": "diamonds"}[spec[-1]]
        return Card(rank, suit)

    def strength(*specs: str) -> tuple[int, ...]:
        found = classify(frozenset(c(s) for s in specs))
        assert found is not None, specs
        return found[1]

    # 9♠9♥ beats 9♥9♣ … (the pair containing the spade); Q-Q beats J-J.
    assert strength("9s", "9d") > strength("9h", "9c")
    assert strength("Qd", "Qc") > strength("Js", "Jh")
    # K-Q-J-10-9 beats Q-J-10-9-8; same ranks: the top card's suit decides.
    assert strength("Kd", "Qc", "Jh", "10s", "9d") > strength("Qs", "Jh", "10c", "9d", "8s")
    assert strength("Qs", "Jh", "10c", "9d", "8d") > strength("Qh", "Js", "10s", "9s", "8s")
    # The wheel is lowest, beaten by 6-5-4-3-2 and 7-6-5-4-3; A-K-Q-J-10 is highest.
    wheel = strength("5s", "4h", "3c", "2d", "As")
    assert strength("6d", "5h", "4c", "3d", "2s") > wheel
    assert strength("7d", "6h", "5c", "4d", "3s") > strength("6d", "5h", "4c", "3d", "2s")
    assert strength("Ad", "Kh", "Qc", "Jd", "10s") > strength("Kd", "Qh", "Jc", "10d", "9s")
    # 3-2-A-K-Q and 2-A-K-Q-J are not straights.
    assert classify(frozenset({c("3s"), c("2h"), c("Ac"), c("Kd"), c("Qs")})) is None
    assert classify(frozenset({c("2s"), c("Ah"), c("Kc"), c("Qd"), c("Js")})) is None
    # Flushes: a higher suit beats a lower outright; in one suit, the top card.
    assert strength("9s", "7s", "6s", "5s", "3s") > strength("2h", "Jh", "9h", "6h", "4h")
    assert strength("2h", "Jh", "9h", "6h", "4h") > strength("Ah", "Kh", "Qh", "10h", "7h")
    # 9-9-9-4-4 beats 8-8-8-K-K; quads need the fifth card; the type ladder.
    assert strength("9s", "9h", "9c", "4d", "4s") > strength("8s", "8h", "8c", "Kd", "Ks")
    assert classify(frozenset({c("8s"), c("8h"), c("8c"), c("8d")})) is None
    ladder = [
        strength("3s", "4h", "5c", "6d", "7s"),
        strength("3h", "5h", "7h", "9h", "Jh"),
        strength("3s", "3h", "3c", "4d", "4s"),
        strength("3s", "3h", "3c", "3d", "4s"),
        strength("3d", "4d", "5d", "6d", "7d"),
    ]
    assert ladder == sorted(ladder)
    # No two-pair combination, and a triple takes no extra cards.
    assert classify(frozenset({c("9s"), c("9h"), c("4c"), c("4d"), c("Ks")})) is None


def test_every_combination_a_hand_holds_is_offered_once() -> None:
    """Completeness and soundness of the lead query (the open lead, any
    combination): exactly the oracle's set, each card-set once, each at the
    oracle's kind."""
    bundles = _bundles(opened=True)
    for hand in _hands():
        expected = legal_plays(hand)
        plays = bigtwo_lead_options(*bundles, hand)
        offered = _offered(plays)
        dup = [k for k, n in offered.items() if n > 1]
        assert not dup, f"offered twice: {dup}"
        missing = set(expected) - set(offered)
        extra = set(offered) - set(expected)
        assert not missing, f"withheld {len(missing)} legal plays, e.g. {sorted(missing, key=len)[:3]}"
        assert not extra, f"offered {len(extra)} non-combinations, e.g. {list(extra)[:3]}"
        for p in plays:
            assert p.kind == expected[frozenset(p.cards)][0], p


def test_the_opening_lead_offers_every_combination_holding_the_three_of_diamonds() -> None:
    """Pagat: the 3♦ "must be played, either alone or as part of a legal
    combination" — every such combination, the single 3♦ among them."""
    three = Card("3", "diamonds")
    bundles = _bundles(opened=False)
    rng = random.Random(9620)
    threes_first = [c for c in DECK if c.rank in {"3", "4", "5", "6", "7"}]
    for pool in [DECK] * 40 + [threes_first] * 40:
        rest = [c for c in pool if c != three]
        hand = [three, *rng.sample(rest, 12)]
        expected = {k for k in legal_plays(hand) if three in k}
        offered = _offered(bigtwo_lead_options(*bundles, hand))
        assert set(offered) == expected
        assert frozenset({three}) in offered


def test_legal_follows_are_exactly_the_combinations_that_beat_the_standing_play() -> None:
    universe = {frozenset(p.cards): p for p in bigtwo_universe()}
    bundles = _bundles(opened=True)
    rng = random.Random(9621)
    for hand in _hands():
        held = set(hand)
        mine = legal_plays(hand)
        outside = [p for k, p in universe.items() if not (k & held)]
        for standing in rng.sample(outside, 30):
            kind, power = classify(frozenset(standing.cards)) or ("", ())
            assert kind == standing.kind, standing
            expected = {
                k for k, (_, s) in mine.items() if len(k) == len(standing.cards) and s > power
            }
            offered = _offered(bigtwo_follows(*bundles, hand, standing))
            assert set(offered) == expected, (standing, set(offered) ^ expected)


def test_every_universe_play_is_the_combination_it_names() -> None:
    """The action universe's soundness against the oracle: each of its plays
    classifies as the kind it carries."""
    for p in bigtwo_universe():
        found = classify(frozenset(p.cards))
        assert found is not None and found[0] == p.kind, p


def test_every_live_ask_of_a_played_match_offers_the_rules_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The execution differential: across whole matches of the game file,
    every lead and follow the climbing round asks for is checked against the
    oracle on the live hand and standing play — and every hand's opening lead
    is made by the 3♦'s holder, offered exactly its combinations holding it.

    red under: the one-representative-per-rank enumeration (completeness
    fails on the first live hand holding a rank twice)."""
    import cardlang.runtime.bigtwo as engine
    from cardlang.pipeline import check_source
    from cardlang.runtime.driver import play_game

    three = Card("3", "diamonds")
    lead, follows = engine.bigtwo_lead_options, engine.bigtwo_follows
    asks = {"lead": 0, "opening": 0, "follow": 0}

    def checked_lead(facts: narrowing.EngineFacts, gr: reads.GameReads, hand: list[Card]) -> list[Play]:
        plays = lead(facts, gr, hand)
        expected = set(legal_plays(hand))
        if not gr.state["opened"]:
            assert three in hand, "the opening lead is not the 3♦'s holder's"
            expected = {k for k in expected if three in k}
            asks["opening"] += 1
        offered = _offered(plays)
        assert set(offered) == expected and max(offered.values()) == 1
        asks["lead"] += 1
        return plays

    def checked_follows(
        facts: narrowing.EngineFacts, gr: reads.GameReads, hand: list[Card], current: Play
    ) -> list[Play]:
        plays = follows(facts, gr, hand, current)
        found = classify(frozenset(current.cards))
        assert found is not None and found[0] == current.kind
        expected = {
            k for k, (_, s) in legal_plays(hand).items() if len(k) == len(current.cards) and s > found[1]
        }
        offered = _offered(plays)
        assert set(offered) == expected and all(n == 1 for n in offered.values())
        asks["follow"] += 1
        return plays

    monkeypatch.setattr(engine, "bigtwo_lead_options", checked_lead)
    monkeypatch.setattr(engine, "bigtwo_follows", checked_follows)
    game = check_source(Path(__file__).resolve().parent.parent / "docs" / "games" / "big-two.cardlang")
    for seed in range(4):
        play_game(game, random.Random(seed))
    assert asks["opening"] > 0 and asks["lead"] > asks["opening"] and asks["follow"] > 0, asks
