"""The Tichu combination engine held to its rules by an independent oracle.

Two artifacts, per decisions.md "Closed-domain completeness":

- **The grid.** `KINDS` (cardlang/runtime/tichu_combinations.py) is the
  registry of combination kinds; crossed with the two special cards a kind
  may or may not admit (the Phoenix as a wildcard, the Mahjong as a one), it
  is the domain `_combos` must be total over. Each cell's expected outcome —
  a play of that shape exists, or nothing of that shape is ever built — is
  authored below from the rules, and the cell is checked by BUILDING a
  witness hand for it and asking the enumerator, never by reading the
  enumerator's own table back.

- **The oracle.** `is_combination` is a validator written from the rules
  (Fata Morgana English edition) that never calls `_combos`: it says whether
  a card-set with a wildcard assignment is a combination of a kind, with
  what key. The differential runs both directions over every subset of
  sampled hands — soundness (every play the enumerator emits is a
  combination, at the key it claims) and completeness (every combination the
  validator accepts is emitted, at every wildcard value) — and the follows
  query against a brute-force "beats" relation over the same universe.

What a green here does not prove: nothing about play ORDER (the goldens pin
that), nothing about the wish (tests/test_tichu_wish.py), and nothing about
the codec (tests/test_openspiel_encoding.py pins the id bijection).

Completeness ledger — the grid's axes and outcomes:
  kind        : every key of KINDS (derived in code)
  phoenix     : {absent, present} — present means the play holds it
  mahjong     : {absent, present} — present means the play holds it
  outcome     : built | never — `never` cells are the rules' exclusions
                (the Phoenix in no bomb; the Mahjong in nothing but a single
                or a straight; the Dog alone), each one asserted by a
                witness hand that could build the shape were it allowed.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator

import pytest

from cardlang.runtime.tichu import tichu_lead_options
from cardlang.runtime.tichu_combinations import (
    KINDS,
    Play,
    _combos,
    _legal_follows,
    bomb_rank,
)
from cardlang.runtime.values import Card, build_deck
from tests.test_openspiel_encoding import _tichu_bundles

DECK = build_deck("tichu56")
MAHJONG = next(c for c in DECK if c.rank == "Mahjong")
DOG = next(c for c in DECK if c.rank == "Dog")
PHOENIX = next(c for c in DECK if c.rank == "Phoenix")
DRAGON = next(c for c in DECK if c.rank == "Dragon")
VAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
       "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
SUITS = ("clubs", "diamonds", "hearts", "spades")


def C(rank: str, suit: str = "clubs") -> Card:
    return Card(rank, suit)


# ---------------------------------------------------------------------------
# The oracle: a validator written from the rules, calling nothing it judges
# ---------------------------------------------------------------------------


def is_combination(cards: frozenset[Card], wild: int | None) -> tuple[str, int, float] | None:
    """`(kind, length, key)` if `cards` with the Phoenix standing for `wild`
    is one Tichu combination, else None. The Phoenix as a single carries no
    wildcard value and its key is contextual, so a lone Phoenix answers
    ("single", 1, 0) and the callers treat the key as unknown."""
    n = len(cards)
    has_ph = PHOENIX in cards
    has_mj = MAHJONG in cards
    has_dog = DOG in cards
    has_dr = DRAGON in cards
    normals = [c for c in cards if c.rank in VAL]
    if wild is not None and (not has_ph or not 2 <= wild <= 14):
        return None
    if has_dog:
        return ("dog", 1, 0) if n == 1 else None
    if n == 1:
        if has_ph:
            return ("single", 1, 0)
        if has_mj:
            return ("single", 1, 1)
        if has_dr:
            return ("single", 1, 15)
        return ("single", 1, VAL[normals[0].rank])
    if has_dr:
        return None  # the Dragon joins no combination
    if has_ph and wild is None:
        return None  # a wildcard play states what it stands for
    # Multiset of rank values, the Phoenix counted at its wild value.
    vals: list[int] = sorted([VAL[c.rank] for c in normals] + ([wild] if wild is not None else []))
    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    if has_mj:
        # The Mahjong is a one, and a one is only the low end of a straight.
        run = [1, *vals]
        if len(run) >= 5 and len(set(run)) == len(run) and run == list(range(1, len(run) + 1)):
            return ("straight", len(run), run[-1])
        return None
    distinct = sorted(counts)
    if n == 2 and len(distinct) == 1:
        return ("pair", 2, distinct[0])
    if n == 3 and len(distinct) == 1:
        return ("triple", 3, distinct[0])
    if n == 4 and len(distinct) == 1:
        return None if has_ph else ("bomb", 4, distinct[0])
    if n == 5 and len(distinct) == 2 and sorted(counts.values()) == [2, 3]:
        tr = next(v for v, k in counts.items() if k == 3)
        return ("fullhouse", 5, tr)
    consecutive = distinct == list(range(distinct[0], distinct[-1] + 1))
    if consecutive and all(k == 1 for k in counts.values()) and n >= 5:
        suits = {c.suit for c in normals}
        if not has_ph and len(suits) == 1:
            return ("bomb", n, distinct[-1])
        return ("straight", n, distinct[-1])
    if consecutive and all(k == 2 for k in counts.values()) and len(distinct) >= 2:
        return ("pairseq", len(distinct), distinct[-1])
    return None


def beats(p: tuple[str, int, float], q: tuple[str, int, float]) -> bool:
    """Whether a play of shape `p` beats the standing shape `q`, by the rules:
    a bomb over anything it outranks (cards, then rank), else the same kind
    and length at a higher key."""
    if q[0] == "dog":
        return False
    if p[0] == "bomb":
        return q[0] != "bomb" or (p[1], p[2]) > (q[1], q[2])
    if q[0] == "bomb":
        return False
    return p[0] == q[0] and p[1] == q[1] and p[2] > q[2]


# ---------------------------------------------------------------------------
# The grid: KINDS x phoenix x mahjong, outcomes authored from the rules
# ---------------------------------------------------------------------------

# Witness hands per kind that could build the shape WITH the special card
# were it allowed — so a `never` cell is refuted by a hand that tempts it.
_WITNESS: dict[str, list[Card]] = {
    "dog": [DOG, C("2")],
    "single": [C("2")],
    "pair": [C("2"), C("2", "hearts")],
    "triple": [C("2"), C("2", "hearts"), C("2", "spades")],
    "fullhouse": [C("2"), C("2", "hearts"), C("2", "spades"), C("3"), C("3", "hearts")],
    "straight": [C("2"), C("3"), C("4"), C("5"), C("6", "hearts")],
    "pairseq": [C("4"), C("4", "hearts"), C("5"), C("5", "hearts")],
    "bomb": [C("2"), C("2", "hearts"), C("2", "spades"), C("2", "diamonds")],
}

# The rules' answer per (kind, phoenix, mahjong): the Phoenix joins every
# kind but the Dog and a bomb; the Mahjong joins a single (as its own single)
# and a straight (as the one) and nothing else.
_EXPECTED: dict[tuple[str, bool, bool], bool] = {}
for _kind in KINDS:
    for _ph, _mj in itertools.product((False, True), repeat=2):
        ok = True
        if _ph and _kind in ("dog", "bomb"):
            ok = False
        if _mj and _kind not in ("single", "straight"):
            ok = False
        if _ph and _mj and _kind == "single":
            ok = False  # a single is one card
        _EXPECTED[(_kind, _ph, _mj)] = ok


@pytest.mark.parametrize(
    ("kind", "phoenix", "mahjong"),
    sorted(_EXPECTED),
    ids=lambda v: str(v),
)
def test_grid_kind_x_phoenix_x_mahjong(kind: str, phoenix: bool, mahjong: bool) -> None:
    hand = list(_WITNESS[kind])
    if phoenix:
        # Tempt the wildcard: drop one natural so only the Phoenix completes
        # the shape (the single keeps its card and adds the Phoenix beside).
        if kind not in ("single", "dog"):
            hand.pop()
        hand.append(PHOENIX)
    if mahjong:
        if kind == "straight":
            hand = [MAHJONG, C("2"), C("3"), C("4"), C("5")] + ([PHOENIX] if phoenix else [])
            if phoenix:
                hand.remove(C("5"))
        else:
            hand.append(MAHJONG)
    # The lead site's universe: the engine's combinations plus the two
    # lead-only plays (the Dog, the Phoenix as a single at 1.5).
    plays = [
        p for p in tichu_lead_options(*_tichu_bundles(), hand)
        if p.kind == kind
        and (PHOENIX in p.cards) == phoenix
        and (MAHJONG in p.cards) == mahjong
    ]
    if kind == "dog":
        # The Dog is led alone: with a special card beside it, nothing.
        assert [p.cards for p in plays] == ([] if phoenix or mahjong else [(DOG,)])
        return
    expected = _EXPECTED[(kind, phoenix, mahjong)]
    assert bool(plays) == expected, (kind, phoenix, mahjong, plays)
    for p in plays:
        assert p.length in KINDS[kind].lengths
        assert (p.wild is not None) == phoenix or kind == "single"
        shape = is_combination(frozenset(p.cards), p.wild)
        assert shape is not None and shape[0] == kind, (p, shape)
        assert p.kind != "single" or PHOENIX in p.cards or shape[2] == p.key


def test_every_kind_the_registry_names_is_built_somewhere() -> None:
    """The grid's rows are KINDS; each row has a witness hand, and the lead
    site builds a play of that kind from it — so a kind added to the
    registry without a witness, or without an enumerator arm, fails here
    rather than sitting unbuilt. Executes the enumerator; reads no table
    back."""
    assert set(_WITNESS) == set(KINDS)
    for kind, hand in _WITNESS.items():
        built = {p.kind for p in tichu_lead_options(*_tichu_bundles(), list(hand))}
        assert kind in built, (kind, built)


def test_the_authored_outcomes_agree_with_the_registry() -> None:
    """`_EXPECTED` is authored from the rules; `KINDS` states the same two
    admissibilities per kind. Pinned equal, so neither can drift from the
    other: a flag flipped in the registry reddens here, and a cell authored
    against the rules reddens against the registry."""
    for (kind, phoenix, mahjong), expected in _EXPECTED.items():
        admitted = (not phoenix or KINDS[kind].phoenix) and (not mahjong or KINDS[kind].mahjong)
        if phoenix and mahjong and kind == "single":
            admitted = False  # one card
        assert expected == admitted, (kind, phoenix, mahjong)


# ---------------------------------------------------------------------------
# The differential: enumerator against validator, both directions
# ---------------------------------------------------------------------------


def _subsets(hand: list[Card]) -> Iterator[frozenset[Card]]:
    for k in range(1, len(hand) + 1):
        for combo in itertools.combinations(hand, k):
            yield frozenset(combo)


@pytest.mark.parametrize("seed", range(6))
def test_enumerator_is_sound_and_complete_against_the_validator(seed: int) -> None:
    rng = random.Random(seed)
    hand = rng.sample(DECK, 11 if seed else 14)  # one full hand; the rest smaller, faster
    emitted: dict[tuple[frozenset[Card], int | None], Play] = {}
    for p in _combos(hand):
        key = (frozenset(p.cards), p.wild)
        assert key not in emitted, f"emitted twice: {p}"
        emitted[key] = p
        shape = is_combination(*key)
        assert shape is not None, f"emitted a non-combination: {p}"
        assert shape == (p.kind, p.length, p.key), (p, shape)
    for cards in _subsets(hand):
        wilds: list[int | None] = [None] if PHOENIX not in cards else [None, *range(2, 15)]
        for wild in wilds:
            shape = is_combination(cards, wild)
            if shape is None or shape[0] == "dog":
                assert (cards, wild) not in emitted
                continue
            if len(cards) == 1 and PHOENIX in cards:
                continue  # the Phoenix single is the lead site's / a contextual follow
            assert (cards, wild) in emitted, f"validator accepts, enumerator missed: {sorted(map(str, cards))} wild={wild} {shape}"


@pytest.mark.parametrize("seed", range(4))
def test_follows_match_the_beats_relation(seed: int) -> None:
    rng = random.Random(100 + seed)
    hand = rng.sample(DECK, 12)
    other = rng.sample([c for c in DECK if c not in hand], 12)
    standing = [p for p in _combos(other) if p.kind != "dog"]
    standing.append(Play("dog", 1, 0, (DOG,)))
    for cur in standing:
        follows = _legal_follows(hand, cur)
        got = {(frozenset(p.cards), p.wild) for p in follows}
        expected: set[tuple[frozenset[Card], int | None]] = set()
        for p in _combos(hand):
            if beats((p.kind, p.length, p.key), (cur.kind, cur.length, cur.key)):
                expected.add((frozenset(p.cards), p.wild))
        if PHOENIX in hand and cur.kind == "single" and cur.key < 15:
            expected.add((frozenset({PHOENIX}), None))
        assert got == expected, (cur, got ^ expected)
        for p in follows:
            if p.is_bomb and cur.is_bomb:
                assert bomb_rank(p) > bomb_rank(cur)


# ---------------------------------------------------------------------------
# Misuse probes: the wrong sentences a designer or the engine could reach
# ---------------------------------------------------------------------------


def test_the_mahjong_pairs_with_nothing_and_fills_no_full_house() -> None:
    # issue #725's two witnesses
    assert not [p for p in _combos([MAHJONG, PHOENIX]) if len(p.cards) > 1]
    nines = [C("9"), C("9", "diamonds"), C("9", "hearts")]
    assert not [p for p in _combos([MAHJONG, PHOENIX, *nines]) if p.kind == "fullhouse"]


def test_a_lower_bomb_never_answers_a_higher_one() -> None:
    # issue #724's witness, and the length clause it makes live
    kings = Play("bomb", 4, 13, tuple(C("K", s) for s in SUITS))
    threes = [C("3", s) for s in SUITS]
    assert _legal_follows(threes, kings) == []
    flush = [C(r, "hearts") for r in ("2", "3", "4", "5", "6")]
    assert [(p.kind, p.length) for p in _legal_follows(flush, kings)] == [("bomb", 5)]
    six_flush = [C(r, "spades") for r in ("2", "3", "4", "5", "6", "7")]
    five = Play("bomb", 5, 14, tuple(C(r, "hearts") for r in ("10", "J", "Q", "K", "A")))
    assert [(p.kind, p.length) for p in _legal_follows(six_flush, five)] == [("bomb", 6)]


def test_a_suited_run_is_a_bomb_and_never_a_straight() -> None:
    flush = [C(r, "hearts") for r in ("2", "3", "4", "5", "6")]
    assert {p.kind for p in _combos(flush) if len(p.cards) == 5} == {"bomb"}


def test_the_phoenix_makes_no_bomb() -> None:
    assert not [p for p in _combos([C("2"), C("2", "hearts"), C("2", "spades"), PHOENIX]) if p.is_bomb]
    run = [C(r, "hearts") for r in ("2", "3", "4", "5")] + [PHOENIX]
    assert {p.kind for p in _combos(run) if len(p.cards) == 5} == {"straight"}


def test_a_gapless_phoenix_straight_is_two_plays() -> None:
    hand = [C("3"), C("4"), C("5"), C("6"), PHOENIX]
    keys = sorted((p.key, p.wild) for p in _combos(hand) if p.kind == "straight")
    assert keys == [(6, 2), (7, 7)]


def test_the_phoenix_completes_either_slot_of_a_full_house() -> None:
    hand = [C("8"), C("8", "hearts"), C("K"), C("K", "hearts"), PHOENIX]
    assert sorted((p.key, p.wild) for p in _combos(hand) if p.kind == "fullhouse") == [(8, 8), (13, 13)]


def test_the_dragon_joins_nothing_and_is_offered_once() -> None:
    hand = [DRAGON, C("A"), C("A", "hearts")]
    plays = _combos(hand)
    assert sum(1 for p in plays if DRAGON in p.cards) == 1
    assert all(p.kind == "single" for p in plays if DRAGON in p.cards)
