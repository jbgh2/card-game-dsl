"""The Combination Catalogue's closed words — the one home of its phrases.

A game's `combinations <name> { <label>: <shape phrase> … }` block declares
which card multisets are plays (decisions.md, "Combination Catalogues"). Its
phrases are a closed set, keyed here by the grammar alias each one
parses to: the grammar's `shape_part`, `shape_qualifier` and `shape_phrase`
alternatives are exactly these keys (pinned by
tests/test_combination_catalogue.py), so a phrase added to the grammar with no
row here, or a row with no production, reddens that pin before any pass can
silently ignore it.

Contract:
  assumes:      nothing; this module is data.
  establishes:  the closed sets of shape parts, qualifiers and phrase forms; the
                fields a Combination value exposes; the largest universe a
                catalogue may enumerate.
  illegal after: a shape phrase, qualifier or Combination field that some pass
                handles and this module does not name.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, get_args

# The closed kinds, as types the AST carries; each registry below is keyed by
# exactly one of them (pinned in this module, at import).
ShapePartKind = Literal["shape_card", "shape_cards", "shape_of_a_kind", "shape_in_sequence"]
ShapeQualifierKind = Literal["q_all_one_suit", "q_not_all_one_suit", "q_not_in_sequence"]

# Each shape part, by grammar alias, with its designer phrase. A part names a
# card multiset of `n` cards: any `n` cards, `n` of one rank, or `n` of
# consecutive places in the game's Rank Sequence (`sequence:`).
SHAPE_PARTS: Mapping[str, str] = MappingProxyType(
    {
        "shape_card": "`<n> card`",
        "shape_cards": "`<n> cards`",
        "shape_of_a_kind": "`<n> of a kind`",
        "shape_in_sequence": "`<n> in sequence`",
    }
)

# Each qualifier, by grammar alias, with its designer phrase. A qualifier
# narrows the part it follows; it settles an overlap between two rows in the
# file's own words (a straight `not all one suit` is no straight flush).
SHAPE_QUALIFIERS: Mapping[str, str] = MappingProxyType(
    {
        "q_all_one_suit": "`all one suit`",
        "q_not_all_one_suit": "`not all one suit`",
        "q_not_in_sequence": "`not in sequence`",
    }
)

# The two phrase forms: one part with its qualifiers, or two parts joined by
# `with` (disjoint cards of disjoint ranks: a full house is `3 of a kind with
# 2 of a kind`).
SHAPE_FORMS: Mapping[str, str] = MappingProxyType(
    {
        "shape_simple": "`<part>[, <qualifier>]…`",
        "shape_with": "`<part> with <part>`",
    }
)

# The fields a Combination value exposes to `play.<field>`, each with what it
# reads, or None for a field the language names and refuses for now. `wild`
# is the rank a wild card in the play stands for: a play's identity carries it
# (decisions.md, "Combination Catalogues"), and its read waits for a catalogue
# that can stand a wild card, issue #989.
COMBINATION_FIELDS: Mapping[str, str | None] = MappingProxyType(
    {
        "shape": "the label of the catalogue row the play is",
        "wild": None,
    }
)

# The largest play universe a catalogue may enumerate. The catalogue pass
# derives every play the catalogue names at check time, and the action space
# numbers them; a catalogue past this bound needs an arithmetic codec composed
# from its rows, which issue #989 holds. It is a fixed engine limit with no
# game-side setting, sized so the check-time enumeration stays under a second
# (measured 2026-10-29: `declared.universe` derives a `4 cards` catalogue's
# 270,725 plays over standard52 in 2.0s).
ENUMERATED_UNIVERSE_BOUND = 100_000

assert set(SHAPE_PARTS) == set(get_args(ShapePartKind))
assert set(SHAPE_QUALIFIERS) == set(get_args(ShapeQualifierKind))
