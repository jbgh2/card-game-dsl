"""Scopa's subset codec and capture predicates — grid and completeness ledger.

property:   the capture decision's action encoding is a bijection between
            `SCOPA_CAPTURE_CODEC`'s id range and every card set a Scopa
            capture can ever be, over the deck the game declares; the two
            capture predicates agree with each other and with the ordinal
            the game file reads off `ranking:`; and every joint-predicate
            root the corpus writes has a codec registered for it.
domain:     four crossed axes, each derived from its registry. The UNIVERSE
            axis is every subset of the deck the GAME FILE selects, of two
            or more cards whose capture values sum to at most a king's,
            enumerated here by size-wise `combinations` against the codec's
            own depth-first growth — two structurally different walks of
            one set, so the grid measures the codec rather than restating
            it. Its bounds come from the rules source (`PAGAT_*` above),
            never from the constants the codec computes with, so a moved
            constant moves one side of every comparison and not both.
            The ID axis is `range(SCOPA_CAPTURE_CODEC.size)`, walked whole.
            The PREDICATE axis is every layout of up to four cards drawn
            from a two-suited pool (so a layout may hold two cards of one
            capture value, which a real layout may) crossed with every
            capture value a played card can carry. The ROOT axis is every
            `where jointly` predicate root in `docs/games/*.cardlang`.
            Deck compatibility is inside the domain, not beside it: the
            codec is keyed by predicate root and not by deck, so "these
            cards are cards of this game's deck" is a claim the grid makes
            rather than assumes.
registry:   the deck is `cardlang.runtime.values.COMPONENT_SETS["scopa40"]`;
            the id space is `SCOPA_CAPTURE_CODEC.size`; the codec registry
            is `cardlang.runtime.primitives.joint_codec_function`; the
            corpus is `docs/games/*.cardlang`, the same glob
            `cardlang.openspiel.registry` derives `GAMES` from. The
            declared-signature side of these two Primitives is pinned at
            tests/test_signatures.py::test_tables_reconcile_with_name_sets,
            and their ranking gate at
            tests/test_trump_slot_class.py::test_every_ranking_reader_has_a_driver.
does not prove: nothing here runs the game, so it says nothing about WHICH
            of the universe's members a position offers — that is the
            movement's own candidate enumeration, and
            tests/test_playout_scopa.py is where a real layout meets it.
            The cross-process ordering cell re-imports in subprocesses
            whose hash seeds CPython randomizes, which pins the ordering
            against hash-order leakage and against nothing else: an
            ordering that varied with, say, a locale would pass it.
"""

from __future__ import annotations

import subprocess
import sys
from itertools import combinations
from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.resolve import _walk
from cardlang.runtime.execute import _JOINT_ENUMERATION_BOUND
from cardlang.runtime.primitives import joint_codec_function
from cardlang.runtime.scopa import (
    DECK_CAPTURE_VALUES,
    DECK_NAME,
    MAX_CAPTURE_VALUE,
    MIN_CAPTURE_SET,
    SCOPA_CAPTURE_CODEC,
    sums_to,
)
from cardlang.runtime.values import Card, build_deck

ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "docs" / "games"

# The capture values Pagat states, authored here rather than derived — this is
# the rules source's own claim, and the one fact in this module that no
# derivation may supply. Every other value table below is checked against it.
PAGAT_CAPTURE_VALUES = {
    "A": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "7": 7, "J": 8, "Q": 9, "K": 10,
}


# The rules source's own two numbers, authored beside the value table above for
# the same reason: a sum-capture is "a set of two or more cards", and the
# largest card a player can play is a king. Every derivation below is measured
# against these rather than against the module constants that restate them —
# reading `MIN_CAPTURE_SET` here would move both sides of the comparison
# together and measure the codec against itself.
PAGAT_MIN_CAPTURE_SET = 2
PAGAT_MAX_CAPTURE_VALUE = 10


def _declared_deck_name() -> str:
    """The deck `docs/games/scopa.cardlang` selects. The codec is keyed by
    predicate root and not by deck, so this is the only statement tying its
    universe to the cards the game is played with."""
    return str(check_source(GAMES_DIR / "scopa.cardlang").deck)


def _deck() -> list[Card]:
    return build_deck(_declared_deck_name())


def _independent_universe() -> set[frozenset[Card]]:
    """The universe by a size-wise walk: every combination of the deck, by
    ascending size, kept when it sums within a king's. Structurally unlike the
    codec's pruned depth-first growth, and parameterized by the rules source
    rather than by the codec's own constants, so agreement is evidence."""
    deck = _deck()
    out: set[frozenset[Card]] = set()
    size = PAGAT_MIN_CAPTURE_SET
    while True:
        found = False
        for combo in combinations(deck, size):
            if sum(PAGAT_CAPTURE_VALUES[c.rank] for c in combo) <= PAGAT_MAX_CAPTURE_VALUE:
                out.add(frozenset(combo))
                found = True
        if not found:
            return out
        size += 1


# =============================================================================
# The capture value: three statements of one fact
# =============================================================================


def test_the_deck_ordinal_is_the_capture_value_pagat_states() -> None:
    """The codec's deck-derived table against the rules source.

    red under: reverse `ranks=` in COMPONENT_SETS["scopa40"]."""
    assert DECK_CAPTURE_VALUES == PAGAT_CAPTURE_VALUES


def test_the_game_files_ranking_yields_the_same_ordinal() -> None:
    """`rank_value(c) + 1`, which is what `docs/games/scopa.cardlang`'s
    `capture_value` computes, over the ranking that file declares. The driver
    builds the index exactly as `runtime/driver.py` does, so the game and the
    codec are pinned to one ordinal rather than to each other's word for it.

    red under: swap two ranks in scopa.cardlang's `ranking:` clause."""
    game = check_source(GAMES_DIR / "scopa.cardlang")
    rank_index = {r: len(game.ranking) - 1 - i for i, r in enumerate(game.ranking)}
    assert {r: rank_index[r] + 1 for r in game.ranking} == PAGAT_CAPTURE_VALUES


def test_the_primiera_scale_is_the_declared_card_points_table() -> None:
    """The other rank-keyed fact, which is NOT the capture value and is why the
    game spends its one `card_points { }` clause on it: 7 outranks 6 outranks
    ace there, against an ordinal that runs ace up to king.

    red under: drop the `else: 10` row from scopa.cardlang's card_points."""
    game = check_source(GAMES_DIR / "scopa.cardlang")
    assert game.card_points is not None
    from cardlang.runtime.driver import declared_card_points

    assert declared_card_points(game) == {
        "7": 21, "6": 18, "A": 16, "5": 15, "4": 14,
        "3": 13, "2": 12, "J": 10, "Q": 10, "K": 10,
    }


# =============================================================================
# The universe
# =============================================================================


def test_the_codec_universe_is_every_capture_set_the_deck_can_form() -> None:
    """Set equality against the independent walk — the codec holds every
    capture set and nothing else.

    red under: raise MIN_CAPTURE_SET to 3 in cardlang/runtime/scopa.py."""
    codec_universe = {SCOPA_CAPTURE_CODEC.decode(i) for i in range(SCOPA_CAPTURE_CODEC.size)}
    assert codec_universe == _independent_universe()


def test_the_universe_holds_each_set_once() -> None:
    """`size` counts distinct sets: an id space larger than the set it encodes
    would leave `encode_cards` unable to recover the duplicate's other id.

    red under: append `universe.append(frozenset(chosen))` a second time in
    `_ScopaCaptureCodec.__init__`."""
    decoded = [SCOPA_CAPTURE_CODEC.decode(i) for i in range(SCOPA_CAPTURE_CODEC.size)]
    assert len(set(decoded)) == SCOPA_CAPTURE_CODEC.size


def test_every_universe_member_is_a_card_of_this_games_deck() -> None:
    """The codec is keyed by predicate root, never by deck, so nothing upstream
    ties it to the cards the game is played with — the tie is here, against the
    deck the game file itself selects.

    red under: change DECK_NAME to "skat32" in cardlang/runtime/scopa.py."""
    assert DECK_NAME == _declared_deck_name(), (
        "the codec's deck and the game file's `cards:` clause disagree"
    )
    deck = set(_deck())
    assert len(deck) == len(_deck()), "the deck must be duplicate-free to key subsets by frozenset"
    for i in range(SCOPA_CAPTURE_CODEC.size):
        assert SCOPA_CAPTURE_CODEC.decode(i) <= deck


# =============================================================================
# The id space
# =============================================================================


def test_every_id_round_trips_through_the_card_set() -> None:
    """`encode_cards(decode(i)) == i` over the whole id range.

    red under: return `self._universe[idx - 1]` from `decode`."""
    for i in range(SCOPA_CAPTURE_CODEC.size):
        assert SCOPA_CAPTURE_CODEC.encode_cards(SCOPA_CAPTURE_CODEC.decode(i)) == i


def test_every_card_set_round_trips_through_its_id() -> None:
    """`decode(encode_cards(S)) == S` over the whole universe — the other
    direction, which the id walk above does not imply for a codec whose
    `_ids` and `_universe` could disagree.

    red under: build `self._ids` with `(i + 1) % len(universe)` for the id."""
    for cards in _independent_universe():
        assert SCOPA_CAPTURE_CODEC.decode(SCOPA_CAPTURE_CODEC.encode_cards(cards)) == cards


def test_kind_of_is_total_and_speaks_one_word() -> None:
    """Every id renders. Scopa's combination vocabulary has a single member —
    a capture is a capture — unlike the melds and combinations the other
    codecs distinguish, so the pin is that the vocabulary stays that one word.

    red under: return `str(idx)` from `kind_of`."""
    kinds = {SCOPA_CAPTURE_CODEC.kind_of(i) for i in range(SCOPA_CAPTURE_CODEC.size)}
    assert kinds == {"capture"}


def test_a_set_outside_the_universe_is_loud() -> None:
    """A card set no capture can be gets a refusal, never an id belonging to
    some other set. Two shapes: too large to sum within a king's, and a single
    card (which the forced single-card match takes as a plain movement, so it
    is never a joint selection's result).

    red under: give `encode_cards` a `self._ids.get(cards, 0)` fallback."""
    too_big = frozenset({Card("K", "clubs"), Card("K", "hearts")})
    lone = frozenset({Card("A", "clubs")})
    for bad in (too_big, lone):
        with pytest.raises(KeyError):
            SCOPA_CAPTURE_CODEC.encode_cards(bad)


def test_ids_are_stable_across_processes() -> None:
    """Action ids outlive a process — a replayed history means nothing if the
    ordering moves. Fresh interpreters must number the universe identically.

    The child inherits no hash seed, which CPython answers by randomizing one
    per process, so each run below builds the universe under a different string
    hash order. Setting a seed is what this must NOT do
    (tests/test_migration_characterization.py, the retired pin convention);
    leaving it unset is both permitted and the sharper probe.

    red under: build the universe from `set(...)` rather than the ordered walk
    in `_ScopaCaptureCodec.__init__`."""
    probe = (
        "from cardlang.runtime.scopa import SCOPA_CAPTURE_CODEC as c;"
        "print(c.size, [sorted(map(str, c.decode(i))) for i in (0, 1, c.size // 2, c.size - 1)])"
    )
    here = (
        SCOPA_CAPTURE_CODEC.size,
        [
            sorted(map(str, SCOPA_CAPTURE_CODEC.decode(i)))
            for i in (0, 1, SCOPA_CAPTURE_CODEC.size // 2, SCOPA_CAPTURE_CODEC.size - 1)
        ],
    )
    for _run in range(3):
        out = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)},
        )
        assert out.stdout.strip() == f"{here[0]} {here[1]}", out.stdout


# =============================================================================
# The two predicates, and their pairing
# =============================================================================

# Layouts of up to four cards over two suits, so a layout may hold two cards
# of one capture value — which a real layout may, since the four face-up cards
# are dealt rather than played. Crossed with every capture value a played card
# can carry.
_POOL = [Card(r, s) for s in ("diamonds", "hearts") for r in DECK_CAPTURE_VALUES]
_TARGETS = sorted(set(DECK_CAPTURE_VALUES.values()))


@pytest.mark.parametrize("layout_size", range(0, 5))
@pytest.mark.parametrize("target", _TARGETS)
def test_can_sum_agrees_with_the_predicate_it_guards(layout_size: int, target: int) -> None:
    """The no-implicit-actions pairing: `scopa_can_sum` is true exactly when
    some subset of the layout satisfies `scopa_sums_to`. False either way is a
    live defect — true with no satisfying subset offers a movement with nothing
    to select, and false with one silently drops a legal capture.

    Both sides run here as plain functions over values, which is what the two
    Primitives are once their reads are bound; the bound versions are driven
    against a live layout in tests/test_playout_scopa.py.

    red under: drop `n >= minimum` from `_some_subset_sums`'s final test."""
    from cardlang.runtime.scopa import _some_subset_sums

    seen = 0
    for layout in combinations(_POOL, layout_size):
        values = [DECK_CAPTURE_VALUES[c.rank] for c in layout]
        by_enumeration = any(
            sums_to([values[i] for i in idx], target)
            for k in range(MIN_CAPTURE_SET, len(values) + 1)
            for idx in combinations(range(len(values)), k)
        )
        assert _some_subset_sums(values, target, MIN_CAPTURE_SET) is by_enumeration, layout
        seen += 1
    assert seen, "no layouts of this size — the cell would pass vacuously"


@pytest.mark.parametrize("target", _TARGETS)
def test_every_satisfying_subset_of_a_layout_has_an_id(target: int) -> None:
    """The seam between the runtime's per-position enumeration and the codec's
    fixed universe: whatever the movement offers, the action space can name.
    Quantified over the same derived layouts, whose satisfying subsets are the
    candidate sets a real decision would carry.

    The lowest targets carry no sum-capture at all and say so rather than
    passing on an empty loop: the smallest sum two cards can reach is twice the
    cheapest card, so an ace is captured by a single ace or by nothing.

    red under: drop the `total + v <= MAX_CAPTURE_VALUE` prune's `=` in
    `_ScopaCaptureCodec.__init__`."""
    floor = MIN_CAPTURE_SET * min(DECK_CAPTURE_VALUES.values())
    seen = 0
    for layout_size in range(MIN_CAPTURE_SET, 5):
        for layout in combinations(_POOL, layout_size):
            values = [DECK_CAPTURE_VALUES[c.rank] for c in layout]
            for k in range(MIN_CAPTURE_SET, len(layout) + 1):
                for idx in combinations(range(len(layout)), k):
                    if sums_to([values[i] for i in idx], target):
                        SCOPA_CAPTURE_CODEC.encode_cards(frozenset(layout[i] for i in idx))
                        seen += 1
    assert bool(seen) is (target >= floor), (
        f"target {target}: {seen} satisfying subsets, against a sum-capture "
        f"floor of {floor}"
    )


def test_the_enumeration_bound_admits_every_capture_set() -> None:
    """A capture set is never larger than the runtime's own subset-enumeration
    bound, so the two limits cannot disagree about which sets exist. The widest
    capture the deck can form is four aces and three twos.

    red under: lower `_JOINT_ENUMERATION_BOUND` in cardlang/runtime/execute.py."""
    widest = max(len(SCOPA_CAPTURE_CODEC.decode(i)) for i in range(SCOPA_CAPTURE_CODEC.size))
    assert widest == 7
    assert widest <= _JOINT_ENUMERATION_BOUND


# =============================================================================
# The corpus against the codec registry
# =============================================================================


def _joint_roots(path: Path) -> set[str | None]:
    """Every `where jointly` predicate root in one game, as
    `ActionSpace.for_game` reads it: the root call's name, or None where the
    predicate is not rooted in a call at all."""
    game = check_source(path)
    roots: set[str | None] = set()
    for node in _walk(game):
        if isinstance(node, n.Transfer) and node.joint:
            roots.add(node.where.func if isinstance(node.where, n.Call) else None)
    return roots


def test_every_corpus_joint_predicate_root_has_a_registered_codec() -> None:
    """The reconciliation the joint form lacked: a `where jointly` root with no
    codec is refused at `ActionSpace.for_game`, which every corpus game reaches
    only through its proof module — so without this the missing registration
    surfaces as a game that will not build rather than as a registry that lost
    a row. The climb form's twin is
    tests/test_signatures.py::test_climb_action_space_is_derivable.

    The axis is the corpus glob, so a game that starts writing a joint
    selection joins without an edit here.

    red under: delete the `scopa_sums_to` arm from `joint_codec_function`."""
    games = sorted(GAMES_DIR.glob("*.cardlang"))
    assert games, "the corpus glob found nothing"
    unregistered: dict[str, set[str | None]] = {}
    witnessed = 0
    for path in games:
        roots = _joint_roots(path)
        witnessed += len(roots)
        missing = {r for r in roots if r is None or joint_codec_function(r) is None}
        if missing:
            unregistered[path.name] = missing
    assert witnessed, "no corpus game writes a joint selection — the check is vacuous"
    assert not unregistered, (
        f"joint predicate roots with no subset codec: {unregistered} — register "
        f"each in cardlang.runtime.primitives.joint_codec_function"
    )


def test_scopas_joint_root_resolves_to_its_own_codec() -> None:
    """The registry answers for this game's root, and answers with the object
    whose universe the grid above measures — not merely with something.

    red under: point the `scopa_sums_to` arm at `GIN_MELD_CODEC`."""
    assert joint_codec_function("scopa_sums_to") is SCOPA_CAPTURE_CODEC
