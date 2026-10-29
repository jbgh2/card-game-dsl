"""A Declared Engine plays what its catalogue declares: the execution grid.

property:        A climb round over a combination catalogue numbers exactly
                 the card multisets its rows name over the game's deck (each
                 once, by multiset, so a duplicate deck's copies stay
                 distinct), offers a seat exactly the multisets of its hand
                 that a row names and the follows function admits, in action-id
                 order with the pass after them, answers the same with its
                 result cache on and off, and refuses a follows function that
                 reads the absent standing play. Big Two and President offer
                 at every climb ask exactly the list their registered engines
                 offered (the swap proof), and the proof goes red under each
                 planted fault.
domain:          universe: shape rows (`catalogue.SHAPE_PARTS` ×
                 `SHAPE_QUALIFIERS` × `SHAPE_FORMS`) × decks
                 (`values.DECKS`: a subset deck, a duplicate deck, standard52);
                 candidates: every corpus game declaring a catalogue, at every
                 climb ask of the seeds below; the swap proof: every climb ask
                 of the seeds the frozen digests hold, for every game they
                 hold; planted faults: the wheel, a qualifier, the threes'
                 absorption.
registry:        `cardlang.catalogue`; `cardlang.runtime.values.DECKS`; the
                 corpus (`docs/games/*.cardlang`); tests/golden/climb_ask_digests.json
                 and climb_action_ids.json.
held by:         execution. Each oracle is written from the definitions in
                 decisions.md ("Combination Catalogues"), never from the
                 engine; the swap proof's reference is the registered engines'
                 offers, frozen while they played the games, an independent
                 implementation that shares no code with a Declared Engine.
does not prove:  That a check-time refusal fires (tests/test_combination_catalogue.py);
                 anything about Tichu (issue #989).
"""

from __future__ import annotations

import itertools
import json
import random
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from cardlang import catalogue
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime import driver, mechanics, primitives
from cardlang.runtime.values import Card, build_deck, deck_ranks

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "declared_engine"
GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
GOLDEN = Path(__file__).resolve().parent / "golden"
# Every corpus game declaring a catalogue, and the games the registered
# engines' offers were frozen for.
DECLARING = sorted(p.stem for p in GAMES.glob("*.cardlang") if "\ncombinations " in p.read_text())
FROZEN = sorted(json.loads((GOLDEN / "climb_ask_digests.json").read_text()))
FROZEN_IDS = sorted(json.loads((GOLDEN / "climb_action_ids.json").read_text()))


def test_every_frozen_game_declares_its_plays() -> None:
    """The frozen offers and ids are of games that declare a catalogue, so
    the swap proof and the id table ask something of a Declared Engine."""
    assert FROZEN and FROZEN_IDS
    assert set(FROZEN) | set(FROZEN_IDS) <= set(DECLARING)
MINIMAL = (FIXTURES / "minimal.cardlang").read_text()

_ROWS = re.compile(r"combinations climb \{\n(?P<rows>.*?)\n\}", re.DOTALL)
_SEQ_LINE = "  sequence: A 2 3 4 5 6 7 8 9 10 J Q K A\n"

Multiset = tuple[tuple[str, str], ...]


def _key(cards: Any) -> Multiset:
    return tuple(sorted((c.rank, c.suit) for c in cards))


# ---------------------------------------------------------------------------
# The oracle: the definitions, over a multiset of cards.
# ---------------------------------------------------------------------------


def _in_sequence(cards: Multiset, sequence: list[str]) -> bool:
    n = len(cards)
    if n < 2:
        return False
    ranks = Counter(r for r, _ in cards)
    return any(Counter(sequence[i : i + n]) == ranks for i in range(len(sequence) - n + 1))


def _part(cards: Multiset, part: str, n: int, sequence: list[str]) -> bool:
    if len(cards) != n:
        return False
    if part in ("shape_card", "shape_cards"):
        return True
    if part == "shape_of_a_kind":
        return len({r for r, _ in cards}) == 1
    assert part == "shape_in_sequence"
    return _in_sequence(cards, sequence)


def _qualified(cards: Multiset, quals: tuple[str, ...], sequence: list[str]) -> bool:
    one_suit = len({s for _, s in cards}) == 1
    for q in quals:
        if q == "q_all_one_suit" and not one_suit:
            return False
        if q == "q_not_all_one_suit" and one_suit:
            return False
        if q == "q_not_in_sequence" and _in_sequence(cards, sequence):
            return False
    return True


Row = tuple[str, int, tuple[str, ...]] | tuple[tuple[str, int], tuple[str, int]]


def _names(cards: Multiset, row: Row, sequence: list[str]) -> bool:
    """Whether `row` names the multiset `cards`."""
    first = row[0]
    if isinstance(first, tuple):
        (pa, na), (pb, nb) = row  # type: ignore[misc]
        ranks = Counter(r for r, _ in cards)
        for ra in ranks:
            a = tuple(c for c in cards if c[0] == ra)
            b = tuple(c for c in cards if c[0] != ra)
            if a and b and _part(a, pa, na, sequence) and _part(b, pb, nb, sequence):
                return True
        return False
    part, n, quals = row  # type: ignore[misc]
    return _part(cards, part, n, sequence) and _qualified(cards, quals, sequence)


def _oracle_universe(deck: list[Card], rows: list[Row], sequence: list[str]) -> Counter[Multiset]:
    sizes = {r[0][1] + r[1][1] if isinstance(r[0], tuple) else r[1] for r in rows}
    out: Counter[Multiset] = Counter()
    for size in sizes:
        for combo in set(itertools.combinations(sorted((c.rank, c.suit) for c in deck), size)):
            if any(_names(combo, row, sequence) for row in rows):
                out[combo] += 1
    return out


# ---------------------------------------------------------------------------
# Universe: rows × decks.
# ---------------------------------------------------------------------------

_PHRASE = {
    "shape_card": "{n} card",
    "shape_cards": "{n} cards",
    "shape_of_a_kind": "{n} of a kind",
    "shape_in_sequence": "{n} in sequence",
}
_QUALIFIER = {
    "q_all_one_suit": "all one suit",
    "q_not_all_one_suit": "not all one suit",
    "q_not_in_sequence": "not in sequence",
}

# Each deck with a Rank Sequence over its own ranks: a subset deck, a
# duplicate deck, and the standard deck the witnesses play.
_DECKS = {
    "schnapsen20": "J Q K 10 A",
    "pinochle48": "9 J Q K 10 A",
    "standard52": "A 2 3 4 5 6 7 8 9 10 J Q K A",
}

UNIVERSE_ROWS: list[Row] = [
    ("shape_card", 1, ()),
    ("shape_of_a_kind", 2, ()),
    ("shape_of_a_kind", 3, ()),
    ("shape_in_sequence", 3, ()),
    ("shape_in_sequence", 3, ("q_all_one_suit",)),
    ("shape_in_sequence", 3, ("q_not_all_one_suit",)),
    ("shape_cards", 3, ("q_all_one_suit", "q_not_in_sequence")),
    (("shape_of_a_kind", 2), ("shape_card", 1)),
]


def _phrase(row: Row) -> str:
    if isinstance(row[0], tuple):
        (pa, na), (pb, nb) = row
        return f"{_PHRASE[pa].format(n=na)} with {_PHRASE[pb].format(n=nb)}"
    part, n, quals = row
    return _PHRASE[part].format(n=n) + "".join(f", {_QUALIFIER[q]}" for q in quals)


def _probe(deck: str, rows: list[Row]) -> str:
    body = "\n".join(f"  r{i}: {_phrase(r)}" for i, r in enumerate(rows))
    source = MINIMAL.replace("cards: standard52", f"cards: {deck}", 1)
    reads = any("sequence" in _phrase(r) for r in rows)
    source = source.replace(_SEQ_LINE, f"  sequence: {_DECKS[deck]}\n" if reads else "", 1)
    source = source.replace("deal 13 cards", "deal 4 cards", 1)
    return _ROWS.sub(lambda _m: f"combinations climb {{\n{body}\n}}", source, count=1)


def _universe(source: str) -> Counter[Multiset]:
    space = ActionSpace.for_game(check_dsl(source, "probe.cardlang"))
    return Counter(_key(p.cards) for p in space._combos)


UNIVERSE_CELLS = [(deck, row) for deck in _DECKS for row in UNIVERSE_ROWS]


def test_the_universe_rows_reach_every_part_qualifier_and_form() -> None:
    parts = {r[0] for r in UNIVERSE_ROWS if not isinstance(r[0], tuple)}
    quals = {q for r in UNIVERSE_ROWS if not isinstance(r[0], tuple) for q in r[2]}
    assert parts == set(catalogue.SHAPE_PARTS)
    assert quals == set(catalogue.SHAPE_QUALIFIERS)
    assert any(isinstance(r[0], tuple) for r in UNIVERSE_ROWS)
    assert {"schnapsen20", "pinochle48", "standard52"} <= set(_DECKS)


@pytest.mark.parametrize(("deck", "row"), UNIVERSE_CELLS, ids=[f"{d}-{_phrase(r)}" for d, r in UNIVERSE_CELLS])
def test_a_catalogue_numbers_exactly_the_multisets_its_rows_name(deck: str, row: Row) -> None:
    sequence = _DECKS[deck].split()
    assert set(sequence) <= set(deck_ranks(deck))
    want = _oracle_universe(build_deck(deck), [row], sequence)
    got = _universe(_probe(deck, [row]))
    assert got == Counter(dict.fromkeys(want, 1)), (len(got), len(want))


def test_a_duplicate_decks_copies_are_distinct_plays() -> None:
    """pinochle48 holds two copies of each card: `1 card` and `2 of a kind`
    name 24 singles and the pairs of one rank — 36 distinct-card pairs and 24
    pairs of identical copies — 84 multisets, where a set key folds the 24
    copy-pairs onto the singles."""
    rows: list[Row] = [("shape_card", 1, ()), ("shape_of_a_kind", 2, ())]
    got = _universe(_probe("pinochle48", rows))
    assert len(got) == 84
    assert all(v == 1 for v in got.values())


@pytest.mark.parametrize("witness", FROZEN_IDS)
def test_a_witness_numbers_the_frozen_table(witness: str) -> None:
    """The witness's catalogue numbers, id for id, the table the registered
    engine's universe froze (tests/golden/climb_action_ids.json)."""
    import json

    from cardlang.runtime.values import card_to_action

    frozen = json.loads((Path(__file__).parent / "golden" / "climb_action_ids.json").read_text())[witness]
    space = ActionSpace.for_game(check_source(str(GAMES / f"{witness}.cardlang")))
    rows = [" ".join(str(i) for i in sorted(card_to_action(c) for c in p.cards)) for p in space._combos]
    assert rows == frozen


# ---------------------------------------------------------------------------
# Candidates at every ask, against the oracle and in id order.
# ---------------------------------------------------------------------------

_SEEDS = range(3)


def _asks(game: Any, seeds: range) -> Iterator[tuple[Any, list[Any]]]:
    """Every climb ask of the seeds: the form's state and what it offered."""
    seen: list[tuple[Any, list[Any]]] = []
    orig = mechanics.ClimbForm.candidates

    def record(self: mechanics.ClimbForm, actor: Any, state: Any, ctx: Any) -> list[Any]:
        offered = orig(self, actor, state, ctx)
        seen.append(((self, actor, dict(state)), list(offered)))
        return offered

    mechanics.ClimbForm.candidates = record  # type: ignore[method-assign]
    try:
        for seed in seeds:
            driver.play_game(game, random.Random(seed))
    finally:
        mechanics.ClimbForm.candidates = orig  # type: ignore[method-assign]
    yield from seen


@pytest.mark.parametrize("witness", DECLARING)
def test_a_witness_offers_its_plays_in_id_order_with_the_pass_last_each_in_card_order(witness: str) -> None:
    game = check_source(str(GAMES / f"{witness}.cardlang"))
    space = ActionSpace.for_game(game)
    asks = 0
    for _, offered in _asks(game, _SEEDS):
        plays = [c for c in offered if c != primitives.CLIMB_PASS]
        assert offered[: len(plays)] == plays
        ids = [space.encode(p) for p in plays]
        assert ids == sorted(set(ids))
        for p in plays:
            assert tuple(p.cards) == primitives.in_card_order(p.cards), p
        asks += 1
    assert asks > 0


# ---------------------------------------------------------------------------
# The swap proof: a Declared Engine offers what the registered engine offered.
# ---------------------------------------------------------------------------


def _ask_lists(game: Any, seeds: range) -> list[list[Multiset | str]]:
    return [
        [c if isinstance(c, str) else _key(c.cards) for c in offered] for _, offered in _asks(game, seeds)
    ]


def _ask_digests(game: Any, seeds: range) -> dict[str, dict[str, object]]:
    """Each seed's climb asks, as their count and a digest of every offered
    list (identities by rank and suit, the pass by name), in ask order."""
    import hashlib
    import json

    out: dict[str, dict[str, object]] = {}
    for seed in seeds:
        lists = [
            [c if isinstance(c, str) else sorted([x.rank, x.suit] for x in c.cards) for c in offered]
            for _, offered in _asks(game, range(seed, seed + 1))
        ]
        text = json.dumps(lists, separators=(",", ":"))
        out[str(seed)] = {"asks": len(lists), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    return out


def _frozen(witness: str) -> dict[str, dict[str, object]]:
    import json

    frozen: dict[str, dict[str, object]] = json.loads(
        (Path(__file__).parent / "golden" / "climb_ask_digests.json").read_text()
    )[witness]
    return frozen


@pytest.mark.parametrize("witness", FROZEN)
def test_the_declared_engine_offers_the_frozen_registered_lists_at_every_ask(witness: str) -> None:
    """The registered engines' offered lists at every climb ask of ten seeds,
    frozen while those engines played the witnesses
    (tests/golden/climb_ask_digests.json), are what the Declared Engine
    offers, digest for digest."""
    frozen = _frozen(witness)
    game = check_source(str(GAMES / f"{witness}.cardlang"))
    assert _ask_digests(game, range(len(frozen))) == frozen


PLANTED_FAULTS = [
    # Big Two: the ace no longer stands low in A-2-3-4-5.
    (
        "big-two",
        "  if c.rank is A and (any card in play where card.rank is \"2\") then 1\n",
        "  if false then 1\n",
    ),
    # Big Two: a flush no longer outranks a straight.
    ("big-two", "then 2000 + 20 *", "then 500 + 20 *"),
    # President: threes no longer take on the rank they beat.
    ("president", "(all cards in play where card.rank is \"3\")", "false"),
]


@pytest.mark.parametrize(("witness", "old", "new"), PLANTED_FAULTS)
def test_the_swap_proof_goes_red_under_each_planted_fault(witness: str, old: str, new: str) -> None:
    text = (GAMES / f"{witness}.cardlang").read_text()
    assert old in text
    faulty = check_dsl(text.replace(old, new, 1), f"{witness}.cardlang")
    frozen = _frozen(witness)
    assert _ask_digests(faulty, range(len(frozen))) != frozen


# ---------------------------------------------------------------------------
# The result cache, and the absent standing play.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("witness", DECLARING)
def test_the_follows_cache_changes_no_answer(witness: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from cardlang.runtime import declared

    game = check_source(str(GAMES / f"{witness}.cardlang"))
    cached = _ask_lists(game, _SEEDS)
    monkeypatch.setattr(declared, "CACHE", False)
    assert _ask_lists(game, _SEEDS) == cached


def test_reading_the_absent_standing_play_is_refused_at_the_first_lead() -> None:
    source = re.sub(
        r"function climb_follows\(.*",
        "function climb_follows(play : Combination, standing : Combination?) =\n"
        "  (number of cards in play) is (number of cards in standing)\n",
        MINIMAL,
        flags=re.DOTALL,
    )
    game = check_dsl(source, "probe.cardlang")
    with pytest.raises(Exception, match=r"standing is none.*issue #990|issue #990.*standing is none"):
        driver.play_game(game, random.Random(0))


def test_a_lead_the_follows_function_refuses_entirely_is_a_loud_error() -> None:
    source = re.sub(
        r"function climb_follows\(.*",
        "function climb_follows(play : Combination, standing : Combination?) =\n"
        "  standing is not none\n",
        MINIMAL,
        flags=re.DOTALL,
    )
    game = check_dsl(source, "probe.cardlang")
    with pytest.raises(Exception, match="no play"):
        driver.play_game(game, random.Random(0))
