"""The catalogue pass: a game's Combination Catalogues and its Rank Sequence,
judged at check time (decisions.md "Combination Catalogues").

Contract:
  assumes:      parse built each `CombinationCatalogue` and `RankSequence`;
                resolve has stamped each climbing round's engine
                (`_resolve_climb_engines`) and validated the deck.
  establishes:  every row is admissible (its counts agree with their nouns and
                can name a play of the deck; each qualifier removes some
                multiset and leaves some); the Rank Sequence names the deck's
                ranks, repeats one only at both ends, and is declared exactly
                where a row reads it; every catalogue is named by a round; no
                row label names anything else of the game; no two rows name one
                multiset; the catalogue's universe is within
                `catalogue.ENUMERATED_UNIVERSE_BOUND`.
  illegal after: an unsettled overlap; a row that names no play; a qualifier
                that removes nothing; a catalogue no round reads.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator

from cardlang.ast import nodes as n
from cardlang.catalogue import ENUMERATED_UNIVERSE_BOUND, SHAPE_QUALIFIERS, ShapeQualifierKind
from cardlang.diagnostics import DiagnosticBag
from cardlang.runtime import declared
from cardlang.stdlib.enums import rank_names
from cardlang.runtime.values import Card, build_deck

_PHRASE = {
    "shape_card": "{n} card",
    "shape_cards": "{n} cards",
    "shape_of_a_kind": "{n} of a kind",
    "shape_in_sequence": "{n} in sequence",
}


def phrase(row: n.ShapeRow) -> str:
    """A row's shape phrase as the designer wrote it."""
    parts = " with ".join(_PHRASE[p.kind].format(n=p.count) for p in row.parts)
    quals = "".join(f", {SHAPE_QUALIFIERS[q].strip('`')}" for q in row.qualifiers)
    return parts + quals


# The enum a Combination Shape's label is a value of: `play.shape is flush`
# compares two of them.
SHAPE_ENUM = "Shape"


def shape_labels(game: n.Game) -> frozenset[str]:
    """Every row label of the game's catalogues: the members of its `Shape`
    enum, classified as values wherever the game reads one bare."""
    return frozenset(row.label for c in game.catalogues for row in c.rows)


def _reads_sequence(row: n.ShapeRow) -> bool:
    return any(p.kind == "shape_in_sequence" for p in row.parts) or (
        "q_not_in_sequence" in row.qualifiers
    )


def check_catalogues(
    game: n.Game, names: Callable[[str], str | None], bag: DiagnosticBag
) -> None:
    """Judge every catalogue and the Rank Sequence. `names(label)` says what
    else of the game a label's spelling names, or None."""
    reading = [row for c in game.catalogues for row in c.rows if _reads_sequence(row)]
    sequence = _check_sequence(game, reading, bag)
    named = {
        nd.engine.catalogue
        for nd in _walk_rounds(game)
        if isinstance(nd.engine, n.DeclaredEngine)
    }
    deck = build_deck(game.deck)
    widest = max(Counter(c.rank for c in deck).values(), default=0)
    for cat in game.catalogues:
        if cat.name not in named:
            bag.error(
                f"combination catalogue `{cat.name}` is named by no round — a "
                f"catalogue declares a climbing round's plays; name it in the "
                f"round's `combinations` slot",
                cat.span,
            )
        seen: dict[str, n.ShapeRow] = {}
        admissible = True
        for row in cat.rows:
            if row.label in seen:
                bag.error(f"`{row.label}` labels two rows of `{cat.name}` — each row's label is its own, so it is written once, not twice", row.span)
                admissible = False
            seen[row.label] = row
            other = names(row.label)
            if other is not None:
                bag.error(f"row label `{row.label}` is already {other} of this game — a row's label names its shape and nothing else", row.span)
                admissible = False
            if not _check_row(row, game.deck, widest, sequence, bag):
                admissible = False
        if admissible and (sequence is not None or not any(_reads_sequence(r) for r in cat.rows)):
            _check_universe(cat, game.deck, sequence or (), bag)


def _walk_rounds(game: n.Game) -> Iterator[n.ClimbRound]:
    from cardlang.resolve import _walk

    for nd in _walk(game):
        if isinstance(nd, n.ClimbRound):
            yield nd


def _check_sequence(
    game: n.Game, reading: list[n.ShapeRow], bag: DiagnosticBag
) -> tuple[str, ...] | None:
    seq = game.rank_sequence
    if seq is None:
        if reading:
            bag.error(
                f"`{phrase(reading[0])}` reads `in sequence`, and the game declares no "
                f"`sequence:` — write `sequence: <its ranks, lowest place first>`, "
                f"the order a run reads",
                reading[0].span,
            )
        return None
    ok = True
    if not reading:
        bag.error(
            "`sequence:` declares an order no row reads — a row reads it with "
            "`in sequence`; drop the clause, or write the row",
            seq.span,
        )
        ok = False
    if len(seq.ranks) < 2:
        bag.error("`sequence:` names at least 2 ranks, the shortest run's places", seq.span)
        ok = False
    deck_ranks = rank_names(game.deck)
    for r in seq.ranks:
        if r not in deck_ranks:
            bag.error(f"`sequence:` names `{r}`, which is no rank of `{game.deck}`", seq.span)
            ok = False
    counts = Counter(seq.ranks)
    for r, k in counts.items():
        ends = seq.ranks[0] == r and seq.ranks[-1] == r
        if k > 2 or (k == 2 and not ends):
            bag.error(
                f"`sequence:` names `{r}` twice — a rank may stand at both ends "
                f"(the ace low and high) and nowhere else twice",
                seq.span,
            )
            ok = False
    return seq.ranks if ok else None


def _check_row(
    row: n.ShapeRow,
    deck: str,
    widest: int,
    sequence: tuple[str, ...] | None,
    bag: DiagnosticBag,
) -> bool:
    ok = True
    for part in row.parts:
        said = _PHRASE[part.kind].format(n=part.count)
        match part.kind:
            case "shape_card" if part.count != 1:
                bag.error(f"`{said}` is written `{part.count} cards`", row.span)
                ok = False
            case "shape_cards" if part.count == 1:
                bag.error("`1 cards` is written `1 card`", row.span)
                ok = False
            case "shape_of_a_kind" if part.count == 1:
                bag.error("`1 of a kind` is written `1 card`", row.span)
                ok = False
            case "shape_of_a_kind" if part.count > widest:
                bag.error(
                    f"`{said}` names no play: no rank of `{deck}` holds "
                    f"{part.count} cards",
                    row.span,
                )
                ok = False
            case "shape_in_sequence" if part.count < 2:
                bag.error(f"`{said}` names no run — a sequence holds at least 2 cards", row.span)
                ok = False
            case "shape_in_sequence" if sequence is not None and part.count > len(sequence):
                bag.error(
                    f"`{said}` is longer than the game's `sequence:`, which has "
                    f"{len(sequence)} places",
                    row.span,
                )
                ok = False
            case _:
                pass
    if len(row.parts) == 2 and all(p.kind == "shape_card" for p in row.parts):
        bag.error(
            "`1 card with 1 card` is two cards of two ranks — write `2 cards`, "
            "and settle what it must not be in the row's qualifiers",
            row.span,
        )
        ok = False
    for q, k in Counter(row.qualifiers).items():
        if k > 1:
            bag.error(f"`{SHAPE_QUALIFIERS[q].strip('`')}` is said twice in `{row.label}`'s row", row.span)
            ok = False
    return ok


def _check_universe(cat: n.CombinationCatalogue, deck: str, sequence: tuple[str, ...], bag: DiagnosticBag) -> None:
    pool = build_deck(deck)
    order = declared.card_order(deck)
    owner: dict[declared.Identity, str] = {}
    total = 0
    for row in cat.rows:
        named = 0
        for cards in declared.row_multisets(row, pool, sequence, order):
            named += 1
            total += 1
            if total > ENUMERATED_UNIVERSE_BOUND:
                bag.error(
                    f"catalogue `{cat.name}` numbers more than "
                    f"{ENUMERATED_UNIVERSE_BOUND} plays — a catalogue that large "
                    f"needs its plays numbered arithmetically from its rows, which "
                    f"issue #989 holds",
                    cat.span,
                )
                return
            first = owner.setdefault(cards, row.label)
            if first != row.label:
                witness = "".join(str(c) for c in cards)
                bag.error(
                    f"{witness} is both a `{first}` and a `{row.label}` in "
                    f"catalogue `{cat.name}` — settle it in the rows (`, not all "
                    f"one suit`, `, not in sequence`)",
                    row.span,
                )
                return
        if named == 0:
            bag.error(f"`{row.label}: {phrase(row)}` names no play of `{deck}`", row.span)
            continue
        for q in row.qualifiers:
            if _removes_nothing(row, q, pool, sequence, order):
                bag.error(
                    f"`{SHAPE_QUALIFIERS[q].strip('`')}` removes nothing from "
                    f"`{row.label}`'s plays — every one of them already is that; "
                    f"drop it",
                    row.span,
                )


def _removes_nothing(
    row: n.ShapeRow,
    q: ShapeQualifierKind,
    pool: list[Card],
    sequence: tuple[str, ...],
    order: dict[Card, int],
) -> bool:
    """Whether every multiset the row names without `q` already satisfies
    `q`: the search stops at the first that does not."""
    from dataclasses import replace

    rest = tuple(x for x in row.qualifiers if x != q)
    bare = replace(row, qualifiers=rest)
    only = replace(row, qualifiers=(q,))
    return all(
        declared._qualified(cards, only, sequence)
        for cards in declared.row_multisets(bare, pool, sequence, order)
    )
