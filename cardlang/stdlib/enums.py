"""Enumerable values a game's deck and the built-in types define.

Suits and ranks come from the deck; SeatDirection (the seat-direction payload) is
a built-in enum. The name resolver gives a bare name the `enum_value` [[ref-kind]]
when it appears here, so the [[ir]] can distinguish `left` / `hearts` (values)
from `leader` (a variable).
Seeded for the formalized corpus; extended corpus-first.

The membership functions here are `suit_names`/`rank_names`, not
`deck_suits`/`deck_ranks`: those spellings belong to `runtime/values.py` and
return the deck's ORDERED tuple, while these return an unordered frozenset for
namespace membership. One name, one shape (glossary preamble, rule 3) — the
two shapes therefore get two names rather than one name and an import alias.
"""

from __future__ import annotations

from cardlang.runtime.values import deck_ranks, deck_suits

# The stdlib SeatDirection enum: a relative direction around the seating ring,
# fed to `offset_by`. `hold` is the identity offset (the no-pass / keep value);
# `none` is NOT a seat direction — it is the universal null literal (see
# resolve._classify).
SEAT_DIRECTION_VALUES: frozenset[str] = frozenset({"left", "right", "across", "hold"})


# component set name -> total item count. Irregular decks (copies in
# pinochle48/coup15, explicit lists in tarot78/tichu56) make a suits x ranks
# formula wrong, so the size is an explicit table — pinned to
# `len(runtime.build_deck(name))` by a drift test.
_DECK_SIZE: dict[str, int] = {
    "standard52": 52,
    "standard54": 54,
    "schnapsen20": 20,
    "pinochle48": 48,
    "doppelkopf48": 48,
    "skat32": 32,
    "tarot78": 78,
    "tichu56": 56,
    "five_hundred43": 43,
    "coup15": 15,
    "canasta108": 108,
    "kuhn3": 3,
    "leduc6": 6,
    "xo_marks": 9,
    "breakthrough_men": 32,
}


def suit_names(deck: str) -> frozenset[str]:
    """A deck's suits, derived from the runtime deck registry — one source of
    truth (closed-domain completeness): a deck registered in `DECKS` can
    never be silently absent here, and an unknown deck name fails loudly in
    `build_deck` rather than resolving every suit literal to an empty
    namespace."""
    return frozenset(deck_suits(deck))


def deck_size(deck: str) -> int | None:
    """The deck's card count, or None for an unknown deck (rejected earlier; the
    capacity check treats None as 'cannot bound' and skips the game)."""
    return _DECK_SIZE.get(deck)


def rank_names(deck: str) -> frozenset[str]:
    """A deck's ranks, derived from the runtime deck registry — the same
    single-source rule as `deck_suits`. The rank namespace comes from the
    deck, not `ranking:` (Coup and Tarot declare no ranking but their rank
    values must still resolve); `ranking:` only orders it."""
    return frozenset(deck_ranks(deck))


def enum_values(deck: str) -> frozenset[str]:
    """All bare-name enum values visible in a game with the given deck.
    Name-form ranks resolve bare (`card.rank == Duke`); numeric ranks can
    never appear here (a bare `10` lexes as an Integer literal) and keep the
    string spelling, validated by the type checker's comparison Owner Guard."""
    return suit_names(deck) | rank_names(deck) | SEAT_DIRECTION_VALUES
