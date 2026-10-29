"""A climbing game declares its plays: the Combination Catalogue's check-time grid.

property:        Every sentence the catalogue surface admits checks clean and
                 every sentence it does not is refused loudly, in the layer the
                 cell names, with the fix: the shape rows and their
                 qualifiers, the `with` form, the Rank Sequence, overlaps
                 between rows, the slot pairing of a climb round, the follows
                 function's signature and reads, the `Combination` type at
                 every type host and every read position, the row-label
                 namespace, the growth spellings issue #989 holds, the climb
                 guards a Declared Engine must still meet, and the program
                 identity a catalogue edit moves.
domain:          the axes below, each derived from its registry:
                 shape parts × count × qualifier set (`catalogue.SHAPE_PARTS`,
                 `SHAPE_QUALIFIERS`; counts from the deck's rank multiplicity
                 and the Rank Sequence's length); the `with` form
                 (`SHAPE_FORMS`); overlaps (every qualifier of the Big Two
                 witness's rows, dropped in turn); the Rank Sequence's
                 presence × whether a row reads it, and its contents; slot
                 pairing ({catalogue, registered lead, unknown} × {game
                 function, registered follows, unknown}); follows arity and
                 parameter types; type hosts (every position that names a
                 declared type); Combination read positions (card-source
                 forms, membership, `COMBINATION_FIELDS` and an unknown field,
                 the refused operations); the label namespace (every kind of
                 declared or deck name); the swept climb guards; hidden reads
                 and the play zone's visibility; the program identity.
registry:        `cardlang.catalogue` (SHAPE_PARTS, SHAPE_QUALIFIERS,
                 SHAPE_FORMS, COMBINATION_FIELDS, ENUMERATED_UNIVERSE_BOUND);
                 `cardlang.builtins.functions.PRIMITIVE_CLIMB_ENGINES`;
                 `cardlang.runtime.values.build_deck`; the grammar's
                 `shape_part` / `shape_qualifier` / `shape_phrase` aliases
                 (pinned equal to the registries below).
held by:         the registries are the single owners of the vocabulary, and
                 this grid is a Pin over the passes that consume them; the
                 engine kind of a climb round is a union resolve materializes
                 (the pin `test_the_engine_kinds_are_a_closed_union`).
does not prove:  What a catalogue's plays ARE at play (the universe against a
                 brute-force oracle, multiset identity, candidate order, the
                 memo, the absent standing play): those are execution cells,
                 in tests/test_declared_engine.py. Nor that a follows function
                 compares correctly for a real game: that is the swap proof
                 against the registered engines, in the same module.

Completeness ledger (the judgment the grid cannot state itself):
- The counts per part are {smallest, smallest admissible, largest admissible,
  one past it}; a count between two admissible ones exercises no new arm of
  the catalogue pass, which reads a count only against those bounds.
- Qualifier sets are every singleton, the contradictory pair and a repeat;
  three qualifiers at once reach no arm a pair does not.
- The overlap axis is drawn from the Big Two witness, whose rows hold every
  qualifier; an overlap between rows of the President witness cannot arise
  (each of its sizes has one row).
- A wrapping Rank Sequence (`2 3 … A 2`, which runs K-A-2) checks: its ends
  repeat as Big Two's `A … A` does, and a game allowing round-the-corner
  straights declares exactly that. Only an interior repeat is refused.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from math import comb
from pathlib import Path

import pytest

from cardlang import catalogue
from cardlang.builtins.functions import PRIMITIVE_CLIMB_ENGINES
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, game_identity
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, identity_to_all

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "declared_engine"
MINIMAL = (FIXTURES / "minimal.cardlang").read_text()
BIG_TWO = (FIXTURES / "big-two.cardlang").read_text()
PRESIDENT = (FIXTURES / "president.cardlang").read_text()

_SEQUENCE = "  sequence: A 2 3 4 5 6 7 8 9 10 J Q K A\n"
_ROWS = re.compile(r"combinations climb \{\n(?P<rows>.*?)\n\}", re.DOTALL)
_FOLLOWS = re.compile(r"function climb_follows\(.*", re.DOTALL)


@dataclass(frozen=True)
class Refused:
    """A refusal: every fragment appears in the message, and the message is a
    syntax error exactly when `syntax` says so (the grammar's channel)."""

    fragments: tuple[str, ...]
    syntax: bool = False


CHECKS = None
Expected = Refused | None


def _refused(*fragments: str, syntax: bool = False) -> Refused:
    return Refused(fragments, syntax)


def _assert(source: str, expected: Expected) -> None:
    if expected is None:
        check_dsl(source, "probe.cardlang")
        return
    with pytest.raises(DiagnosticError) as err:
        check_dsl(source, "probe.cardlang")
    message = str(err.value)
    for fragment in expected.fragments:
        assert fragment in message, message
    assert ("syntax error" in message) is expected.syntax, message


def _rows(*rows: str) -> str:
    """The minimal game with its catalogue's rows replaced, and its
    `sequence:` line kept only where a row reads it."""
    body = "\n".join(f"  {r}" for r in rows)
    out = _ROWS.sub(lambda _m: f"combinations climb {{\n{body}\n}}", MINIMAL, count=1)
    assert body in out
    if "sequence" not in body:
        out = out.replace(_SEQUENCE, "", 1)
    return out


def _follows(definition: str) -> str:
    """The minimal game with its follows function replaced."""
    return _FOLLOWS.sub(lambda _m: definition + "\n", MINIMAL, count=1)


def _in_follows(expr: str) -> str:
    """The minimal game whose follows function's body is `expr`."""
    return _follows(f"function climb_follows(play : Combination, standing : Combination?) =\n  {expr}")


# ---------------------------------------------------------------------------
# The vocabulary is the grammar's: each registry equals its rule's aliases.
# ---------------------------------------------------------------------------


def _aliases(rule: str) -> set[str]:
    from cardlang.parse import _parser

    return {
        r.alias
        for r in _parser().rules
        if r.origin.name == rule and r.alias is not None
    }


@pytest.mark.parametrize(
    ("rule", "registry"),
    [
        ("shape_part", catalogue.SHAPE_PARTS),
        ("shape_qualifier", catalogue.SHAPE_QUALIFIERS),
        ("shape_phrase", catalogue.SHAPE_FORMS),
    ],
)
def test_each_shape_registry_is_its_rules_alias_set(rule: str, registry: object) -> None:
    assert isinstance(registry, dict) or hasattr(registry, "keys")
    assert _aliases(rule) == set(registry), rule  # type: ignore[call-overload]


# ---------------------------------------------------------------------------
# Shape rows: part × count × qualifiers, over the minimal game's standard52.
# ---------------------------------------------------------------------------

_DECK_MULTIPLICITY = 4  # standard52: every rank holds one card of each suit
_SEQUENCE_LENGTH = 14  # `A 2 … K A`: fourteen places
_PHRASE = {
    "shape_card": "{n} card",
    "shape_cards": "{n} cards",
    "shape_of_a_kind": "{n} of a kind",
    "shape_in_sequence": "{n} in sequence",
}
_COUNTS = {
    "shape_card": (1, 2),
    "shape_cards": (1, 2, 4, 5),
    "shape_of_a_kind": (1, 2, _DECK_MULTIPLICITY, _DECK_MULTIPLICITY + 1),
    "shape_in_sequence": (1, 2, 5, _SEQUENCE_LENGTH + 1),
}
_QUALIFIER = {
    "q_all_one_suit": "all one suit",
    "q_not_all_one_suit": "not all one suit",
    "q_not_in_sequence": "not in sequence",
}
_QUALIFIER_SETS: tuple[tuple[str, ...], ...] = (
    (),
    *((q,) for q in catalogue.SHAPE_QUALIFIERS),
    ("q_all_one_suit", "q_not_all_one_suit"),
    ("q_all_one_suit", "q_all_one_suit"),
)


def _universe(part: str, n: int, quals: tuple[str, ...]) -> int:
    """How many plays the row names over standard52 — closed forms written
    from the definitions, never from an implementation. A set is in sequence
    when its `n >= 2` cards hold `n` consecutive places of the fourteen
    (`A 2 … K A`), each place any of four suits; for `n <= 5` no two windows
    hold one set of ranks, so windows count sets."""
    one_suit = "q_all_one_suit" in quals
    not_one_suit = "q_not_all_one_suit" in quals
    not_seq = "q_not_in_sequence" in quals
    if one_suit and not_one_suit:
        return 0
    windows = _SEQUENCE_LENGTH - n + 1 if n >= 2 else 0
    if part in ("shape_card", "shape_cards"):
        assert n <= 5
        total, same_suit = comb(52, n), 4 * comb(13, n)
        in_seq, in_seq_same_suit = windows * int(4**n), windows * 4
        if one_suit:
            return same_suit - (in_seq_same_suit if not_seq else 0)
        if not_one_suit:
            return (total - same_suit) - ((in_seq - in_seq_same_suit) if not_seq else 0)
        return total - (in_seq if not_seq else 0)
    if part == "shape_of_a_kind":
        # n cards of one rank are n suits, and never consecutive places.
        return 0 if one_suit else 13 * comb(4, n)
    if not_seq:
        return 0
    if one_suit:
        return windows * 4
    if not_one_suit:
        return windows * (int(4**n) - 4)
    return windows * int(4**n)


def _expected_row(part: str, n: int, quals: tuple[str, ...]) -> Expected:
    """The spec's verdict for one row, in the order the catalogue pass asks."""
    if part == "shape_card" and n != 1:
        return _refused(f"`{n} cards`")
    if part == "shape_cards" and n == 1:
        return _refused("`1 card`")
    if part == "shape_of_a_kind" and n == 1:
        return _refused("`1 card`")
    if part == "shape_of_a_kind" and n > _DECK_MULTIPLICITY:
        return _refused("names no play", f"{n} of a kind")
    if part == "shape_in_sequence" and n == 1:
        return _refused("at least 2")
    if part == "shape_in_sequence" and n > _SEQUENCE_LENGTH:
        return _refused("longer than the game's `sequence:`")
    if len(quals) != len(set(quals)):
        return _refused("twice")
    bare = _universe(part, n, ())
    count = _universe(part, n, quals)
    if count == 0:
        return _refused("names no play")
    for q in quals:
        rest = tuple(x for x in quals if x != q)
        if _universe(part, n, rest) == count:
            return _refused("removes nothing", _QUALIFIER[q])
    if count > catalogue.ENUMERATED_UNIVERSE_BOUND:
        return _refused("issue #989")
    assert bare >= count
    return CHECKS


ROW_CELLS = [
    (part, n, quals)
    for part in catalogue.SHAPE_PARTS
    for n in _COUNTS[part]
    for quals in _QUALIFIER_SETS
]


@pytest.mark.parametrize(("part", "n", "quals"), ROW_CELLS)
def test_a_shape_row_checks_exactly_when_the_spec_admits_it(
    part: str, n: int, quals: tuple[str, ...]
) -> None:
    phrase = _PHRASE[part].format(n=n) + "".join(f", {_QUALIFIER[q]}" for q in quals)
    _assert(_rows(f"x: {phrase}"), _expected_row(part, n, quals))


def test_the_row_axis_covers_every_registered_part_and_qualifier() -> None:
    assert set(_PHRASE) == set(catalogue.SHAPE_PARTS)
    assert set(_QUALIFIER) == set(catalogue.SHAPE_QUALIFIERS)
    assert {q for qs in _QUALIFIER_SETS for q in qs} == set(catalogue.SHAPE_QUALIFIERS)


WITH_CELLS = [
    pytest.param("3 of a kind with 2 of a kind", CHECKS),
    pytest.param("4 of a kind with 1 card", CHECKS),
    pytest.param("2 of a kind with 2 of a kind", CHECKS),
    pytest.param("1 card with 1 card", _refused("`2 cards`")),
    pytest.param("4 of a kind with 4 of a kind", CHECKS),
    ("3 of a kind with 2 of a kind with 1 card", _refused("issue #994")),
    ("3 of a kind with 2 of a kind, all one suit", _refused("one part")),
]


@pytest.mark.parametrize(("phrase", "expected"), WITH_CELLS)
def test_a_with_row_joins_two_parts_of_different_ranks(phrase: str, expected: Expected) -> None:
    _assert(_rows(f"x: {phrase}"), expected)


# ---------------------------------------------------------------------------
# Overlaps: a card multiset two rows can both name is refused until the rows
# settle it in words. Drawn from the Big Two witness's qualifiers.
# ---------------------------------------------------------------------------

_BIG_TWO_ROWS = re.compile(r"combinations big_two \{\n(?P<rows>.*?)\n\}", re.DOTALL)


def _big_two_rows() -> list[tuple[str, str]]:
    m = _BIG_TWO_ROWS.search(BIG_TWO)
    assert m is not None
    rows = []
    for line in m.group("rows").splitlines():
        label, phrase = line.split(":", 1)
        rows.append((label.strip(), phrase.strip()))
    return rows


def _overlap_cells() -> list[tuple[str, str, str]]:
    cells = []
    for label, phrase in _big_two_rows():
        parts = [p.strip() for p in phrase.split(",")]
        for q in parts[1:]:
            cells.append((label, q, ", ".join(p for p in parts if p != q)))
    return cells


OVERLAP_CELLS = _overlap_cells()


def test_the_overlap_axis_drops_every_qualifier_of_the_witness() -> None:
    assert {q for _, q, _ in OVERLAP_CELLS} == set(_QUALIFIER.values())


def test_the_big_two_witness_checks_with_its_overlaps_settled() -> None:
    _assert(BIG_TWO, CHECKS)


@pytest.mark.parametrize(("label", "dropped", "phrase"), OVERLAP_CELLS)
def test_a_dropped_qualifier_leaves_an_overlap_refused(label: str, dropped: str, phrase: str) -> None:
    m = _BIG_TWO_ROWS.search(BIG_TWO)
    assert m is not None
    rows = m.group("rows")
    old = next(line for line in rows.splitlines() if line.strip().startswith(f"{label}:"))
    source = BIG_TWO.replace(old, f"  {label}: {phrase}", 1)
    if (label, dropped) == ("flush", "all one suit"):
        # `5 cards, not in sequence` alone numbers past the enumeration bound,
        # which the pass meets before any overlap.
        _assert(source, _refused("issue #989"))
        return
    _assert(source, _refused("both", f"`{label}`", "settle it"))


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (("single: 1 card", "solo: 1 card"), _refused("both", "`single`", "`solo`")),
        (("single: 1 card", "single: 2 of a kind"), _refused("`single`", "twice")),
    ],
)
def test_two_rows_naming_one_play_or_one_label_are_refused(rows: tuple[str, ...], expected: Expected) -> None:
    _assert(_rows(*rows), expected)


# ---------------------------------------------------------------------------
# The Rank Sequence.
# ---------------------------------------------------------------------------

SEQUENCE_CELLS: list[tuple[str, str, Expected]] = [
    ("present, read", "  sequence: A 2 3 4 5 6 7 8 9 10 J Q K A\n", CHECKS),
    ("absent, read", "", _refused("`sequence:`", "`in sequence`")),
    ("present, unread", "  sequence: A 2 3 4 5 6 7 8 9 10 J Q K A\n", _refused("`sequence:`", "no row")),
    ("not a rank", "  sequence: A 2 3 4 5 X\n", _refused("`X`", "rank")),
    ("interior repeat", "  sequence: A 2 3 3 4 5 6\n", _refused("`3`", "twice")),
    ("ends repeat, wrapping", "  sequence: 2 3 4 5 6 7 8 9 10 J Q K A 2\n", CHECKS),
    ("one rank", "  sequence: A\n", _refused("at least 2")),
]


@pytest.mark.parametrize(("case", "line", "expected"), SEQUENCE_CELLS, ids=[c[0] for c in SEQUENCE_CELLS])
def test_the_rank_sequence_is_declared_where_it_is_read(case: str, line: str, expected: Expected) -> None:
    source = MINIMAL.replace(_SEQUENCE, line, 1)
    row = "single: 1 card" if case == "present, unread" else "run: 5 in sequence"
    source = _ROWS.sub(lambda _m: f"combinations climb {{\n  {row}\n}}", source, count=1)
    _assert(source, expected)


# ---------------------------------------------------------------------------
# Slot pairing: what each slot of `round climb` names.
# ---------------------------------------------------------------------------

_LEAD, _REG_FOLLOWS = next(iter(sorted(PRIMITIVE_CLIMB_ENGINES.items())))
_COMBOS_SLOT = {"catalogue": "climb", "registered lead": _LEAD, "unknown": "climbx"}
_FOLLOWS_SLOT = {"game function": "climb_follows", "registered follows": _REG_FOLLOWS, "unknown": "climb_followz"}


def _expected_pairing(combos: str, follows: str) -> Expected:
    if combos == "catalogue":
        if follows == "game function":
            return CHECKS
        if follows == "registered follows":
            return _refused("catalogue", "function of the game")
        return _refused("'climb_followz'")
    if combos == "registered lead":
        if follows == "registered follows":
            return CHECKS
        return _refused(f"'{_REG_FOLLOWS}'")
    return _refused("'climbx'", "catalogue")


PAIRING_CELLS = [
    pytest.param(c, f)
    for c in _COMBOS_SLOT
    for f in _FOLLOWS_SLOT
]


@pytest.mark.parametrize(("combos", "follows"), PAIRING_CELLS)
def test_a_climb_round_pairs_a_catalogue_with_a_function_and_an_engine_with_its_own(
    combos: str, follows: str
) -> None:
    source = MINIMAL.replace(
        "combinations climb follows climb_follows",
        f"combinations {_COMBOS_SLOT[combos]} follows {_FOLLOWS_SLOT[follows]}",
        1,
    )
    if combos == "registered lead":
        # A registered engine's game declares no catalogue, sequence or
        # Combination-typed function of its own.
        source = _ROWS.sub("", source, count=1).replace(_SEQUENCE, "", 1)
        source = _FOLLOWS.sub("function climb_follows(x : Integer) = x > 0\n", source, count=1)
        source = source.replace("ranking: aces high", "ranking: twos high")
        source = source.replace(
            "    leader        : Player? = none", "    leader        : Player? = none\n    opened : Boolean = false"
        )
    _assert(source, _expected_pairing(combos, follows))


# ---------------------------------------------------------------------------
# The follows function's signature.
# ---------------------------------------------------------------------------

SIGNATURE_CELLS: list[tuple[str, Expected]] = [
    ("(play : Combination, standing : Combination?) = true", CHECKS),
    ("(play : Combination) = true", _refused("two parameters")),
    ("(play : Combination, standing : Combination?, x : Integer) = true", _refused("two parameters")),
    ("(play : Combination, standing : Combination) = true", _refused("`Combination?`", "none")),
    ("(play : Card, standing : Combination?) = true", _refused("`Combination`")),
    ("(play : Combination, standing : Combination?) = 1", _refused("Boolean")),
    (
        "(play : Collection<Card>, standing : Collection<Card>) = true",
        _refused("`Combination`"),
    ),
]


@pytest.mark.parametrize(("signature", "expected"), SIGNATURE_CELLS)
def test_the_follows_function_takes_the_play_and_the_play_it_beats(signature: str, expected: Expected) -> None:
    _assert(_follows(f"function climb_follows{signature}"), expected)


# ---------------------------------------------------------------------------
# `Combination` at every type host.
# ---------------------------------------------------------------------------

TYPE_HOST_CELLS: list[tuple[str, Callable[[str], str], Expected]] = [
    (
        "helper function parameter",
        lambda t: MINIMAL + f"\nfunction size_of(p : {t}) = number of cards in p\n",
        CHECKS,
    ),
    (
        "state declaration",
        lambda t: MINIMAL.replace(
            "    leader        : Player? = none", f"    leader : Player? = none\n    last : {t} = none"
        ),
        _refused("`Combination`", "function parameter"),
    ),
    (
        "move type parameter",
        lambda t: MINIMAL + f"\nmove_type keep(c : {t}) {{\n  effect {{ }}\n}}\n",
        _refused("`Combination`", "function parameter"),
    ),
    (
        "procedure parameter",
        lambda t: MINIMAL + f"\nprocedure p(c : {t}) {{\n}}\n",
        _refused("`Combination`", "function parameter"),
    ),
]
TYPE_SPELLINGS = ("Combination", "Combination?")


@pytest.mark.parametrize("spelling", TYPE_SPELLINGS)
@pytest.mark.parametrize(("host", "build", "expected"), TYPE_HOST_CELLS, ids=[c[0] for c in TYPE_HOST_CELLS])
def test_a_combination_is_a_function_parameter_only(
    host: str, build: Callable[[str], str], expected: Expected, spelling: str
) -> None:
    _assert(build(spelling), expected)


def test_only_a_play_reaches_a_combination_parameter() -> None:
    source = MINIMAL + (
        "\nfunction size_of(p : Combination?) = p is none\n"
        "function probe() = size_of(none)\n"
    )
    _assert(source, _refused("`size_of`", "play"))


# ---------------------------------------------------------------------------
# Reading a Combination.
# ---------------------------------------------------------------------------

READ_CELLS: list[tuple[str, Expected]] = [
    ("standing is none or (number of cards in play) is (number of cards in standing)", CHECKS),
    ("standing is none or (any card in play where card.rank is A)", CHECKS),
    ("standing is none or (all cards in play where card.suit is hearts)", CHECKS),
    ("standing is none or (highest rank_value(card) over cards in play or 0) > 3", CHECKS),
    ("standing is none or (number of cards in play where card.rank is K) is 2", CHECKS),
    ("standing is none or (3 of diamonds) in play", CHECKS),
    ("standing is none or play.shape is single", CHECKS),
    ("standing is none or play.shape is not single", CHECKS),
    ("play.shape is flush", _refused("`flush`", "`single`")),
    ("play.wild is none", _refused("`wild`", "issue #989")),
    ("play.kind is single", _refused("`kind`", "`shape`")),
    ("play.cards is none", _refused("`cards`", "`cards in play`")),
    ("rank_value(top_of(play)) > 3", _refused("no top card")),
    ("play is empty", _refused("`standing is none`")),
    ("standing is empty", _refused("`standing is none`")),
    ("play is standing", _refused("compared by")),
    ("play + 1 > 2", _refused("no number")),
    ("suit_of(play) is hearts", _refused("`suit_of`", "a card")),
    ("any subset of 2 cards in play where true", _refused("no subset source")),
]


@pytest.mark.parametrize(("expr", "expected"), READ_CELLS)
def test_a_combination_reads_as_its_cards_and_its_shape(expr: str, expected: Expected) -> None:
    _assert(_in_follows(expr), expected)


def test_the_field_axis_is_the_registry() -> None:
    fields = {c[0].split(".")[1].split()[0] for c in READ_CELLS if ".shape" in c[0] or ".wild" in c[0]}
    assert fields == set(catalogue.COMBINATION_FIELDS)


# ---------------------------------------------------------------------------
# The row-label namespace.
# ---------------------------------------------------------------------------

LABEL_CELLS: list[tuple[str, str, Expected]] = [
    ("fresh name", "single", CHECKS),
    ("rank", "A", _refused("`A`", "rank")),
    ("suit", "hearts", _refused("`hearts`", "suit")),
    ("state variable", "score", _refused("`score`", "state")),
    ("zone", "discard", _refused("`discard`", "zone")),
    ("function", "climb_follows", _refused("`climb_follows`", "function")),
    ("the catalogue", "climb", _refused("`climb`", "catalogue")),
    ("move type", "play_combination", _refused("`play_combination`")),
    ("phase", "scoring", _refused("`scoring`", "phase")),
    ("registered query", _REG_FOLLOWS, _refused(f"`{_REG_FOLLOWS}`")),
]


@pytest.mark.parametrize(("kind", "label", "expected"), LABEL_CELLS, ids=[c[0] for c in LABEL_CELLS])
def test_a_row_label_names_nothing_else(kind: str, label: str, expected: Expected) -> None:
    _assert(_rows(f"{label}: 1 card"), expected)


def test_a_binder_may_share_a_row_labels_name() -> None:
    """Big Two's precaution binds `let single` beside its `single` row; a
    binder shadows a label as it shadows a suit."""
    assert "let single" in BIG_TWO
    _assert(BIG_TWO, CHECKS)


# ---------------------------------------------------------------------------
# The growth spellings and the near misses (the Diagnostic Grammar's twins).
# ---------------------------------------------------------------------------

MISSPELLING_CELLS: list[tuple[str, Expected]] = [
    ("run of 5", _refused("`5 in sequence`")),
    ("5 in a row", _refused("`5 in sequence`")),
    ("5 of one suit", _refused("`5 cards, all one suit`")),
    ("5 cards in sequence", _refused("`5 in sequence`")),
    ("5 or more in sequence", _refused("issue #989")),
    ("2 pairs in sequence", _refused("issue #989")),
    ("Dog", _refused("issue #989")),
    ("4 of a kind, interrupts", _refused("issue #989")),
    ("1 card, wild", _refused("issue #989")),
]


@pytest.mark.parametrize(("phrase", "expected"), MISSPELLING_CELLS)
def test_a_growth_or_near_miss_spelling_is_refused_with_its_fix(phrase: str, expected: Expected) -> None:
    _assert(_rows(f"x: {phrase}"), expected)


# ---------------------------------------------------------------------------
# One catalogue per game, read by a round, written at top level.
# ---------------------------------------------------------------------------


def test_a_catalogue_no_round_names_is_refused() -> None:
    _assert(MINIMAL + "\ncombinations spare {\n  single: 1 card\n}\n", _refused("`spare`", "no round"))


def test_a_catalogue_in_a_library_is_refused() -> None:
    from cardlang.parse import parse_library

    with pytest.raises(DiagnosticError, match="catalogue"):
        parse_library("library fam {\n  combinations c {\n    single: 1 card\n  }\n}\n", "fam.cardlang")


# ---------------------------------------------------------------------------
# The climb guards keyed on a round's engine see a Declared Engine too.
# ---------------------------------------------------------------------------


def test_a_move_type_named_like_the_climb_pass_is_refused_beside_a_catalogue() -> None:
    source = MINIMAL + "\nmove_type pass {\n  effect { }\n}\n"
    _assert(source, _refused("`pass`"))


def test_a_game_with_two_climb_engines_is_refused_at_check_time() -> None:
    source = MINIMAL.replace(
        "        move all cards from trick_pile to discard\n",
        "        move all cards from trick_pile to discard\n"
        f"        round climb play_combination from leader over players source hand into trick_pile\n"
        f"              combinations {_LEAD} follows {_REG_FOLLOWS} until true\n",
        1,
    )
    _assert(source, _refused("one climb engine"))


# ---------------------------------------------------------------------------
# What the follows function may read, and what its seat sees of the play zone.
# ---------------------------------------------------------------------------

HIDDEN_READ_CELLS: list[tuple[str, Expected]] = [
    ("standing is none or (number of cards in trick_pile) > 0", CHECKS),
    ("standing is none or (any player where score[player] > 0)", CHECKS),
    ("standing is none or (number of cards in hand[0]) > 3", CHECKS),
    ("standing is none or (any card in hand[0] where card.rank is A)", _refused("hand")),
    ("standing is none or player_holding(3 of diamonds) is 0", _refused("player_holding")),
]


@pytest.mark.parametrize(("expr", "expected"), HIDDEN_READ_CELLS)
def test_the_follows_function_reads_only_what_the_asked_seat_sees(expr: str, expected: Expected) -> None:
    _assert(_in_follows(expr), expected)


# Every unowned zone type: the play zone is one zone, never a family.
PLAY_ZONE_CELLS: list[tuple[str, Expected]] = [
    (t, CHECKS if identity_to_all(t) else _refused("`trick_pile`", f"`{t}`", "`TrickPile`"))
    for t, owned in sorted(LIBRARY_ZONE_TYPES.items())
    if not owned
]


@pytest.mark.parametrize(("zone_type", "expected"), PLAY_ZONE_CELLS)
def test_a_climb_plays_into_a_zone_every_seat_sees(zone_type: str, expected: Expected) -> None:
    source = MINIMAL.replace("    trick_pile   : TrickPile", f"    trick_pile   : {zone_type}", 1)
    _assert(source, expected)


# ---------------------------------------------------------------------------
# A catalogue edit moves the program's identity.
# ---------------------------------------------------------------------------


def test_a_catalogue_or_sequence_edit_moves_the_game_identity() -> None:
    base = game_identity(check_dsl(_rows("single: 1 card", "run: 5 in sequence"), "a.cardlang"))
    row = game_identity(check_dsl(_rows("single: 1 card", "run: 6 in sequence"), "b.cardlang"))
    seq = MINIMAL.replace(_SEQUENCE, "  sequence: 2 3 4 5 6 7 8 9 10 J Q K A\n", 1)
    seq = _ROWS.sub(lambda _m: "combinations climb {\n  single: 1 card\n  run: 5 in sequence\n}", seq, count=1)
    moved = game_identity(check_dsl(seq, "c.cardlang"))
    assert len({base, row, moved}) == 3


# ---------------------------------------------------------------------------
# The engine kinds.
# ---------------------------------------------------------------------------


def test_the_engine_kinds_are_a_closed_union() -> None:
    from typing import get_args

    from cardlang.ast import nodes as n

    kinds = {k.__name__ for k in get_args(n.ClimbEngine)}
    assert kinds == {"RegisteredEngine", "DeclaredEngine"}


def test_the_president_witness_checks() -> None:
    _assert(PRESIDENT, CHECKS)
