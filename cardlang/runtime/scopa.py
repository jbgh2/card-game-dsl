"""Scopa's runtime support: the capture's joint predicate and its codec.

The whole game runs in the DSL (docs/games/scopa.cardlang) — the misdeal
redeal, the alternating turn loop, the forced single-card capture, the scopa
bonus and its final-play exception, the last capturer taking what remains, all
five scoring categories with the primiera included, and the guard that asks
whether the layout holds a satisfying set at all, which is the subset binder.

Two things stay here, and both because the capture is a DECISION rather than a
question:

- `scopa_sums_to` — the joint predicate the capture decision selects over: two
  or more cards whose capture values sum to the played card's. `where jointly`
  requires a predicate rooted in a CALL, because the root names the codec
  below; and a collection type — the type of the candidate set the predicate is
  handed — is spellable in a `primitives { }` entry and nowhere else, so the
  arithmetic has no home in the language (issue #246).
- `SCOPA_CAPTURE_CODEC` — the subset universe as pure card-set <-> action-index
  functions, served to the OpenSpiel action space by
  `primitives.joint_codec_function`. Every joint predicate needs one: a
  candidate set's action id cannot be derived from the predicate's text.

A card's capture value is A=1 through 7=7, J=8, Q=9, K=10 — the deck's own
ordinal. The predicate reads it off `facts.rank_index`, the game's declared `ranking:`,
which is the same order the game file's own `capture_value` reads — in the
guard beside the movement as well as in the scoring — so the DSL and the Python
cannot state different values. The codec has no engine
facts to read, so it derives the ordinal from the `scopa40` deck registry
instead; `tests/test_scopa_capture_codec.py` pins the two derivations equal and
pins both against the ordinal the game file declares.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import COMPONENT_SETS, Card, build_deck, rank_strength

# The deck a Scopa capture is drawn from, and the largest capture value a
# played card can carry — the King's. Both derive from the deck registry, so
# the codec's universe follows the deck rather than restating it.
DECK_NAME = "scopa40"

# rank -> capture value, from the deck's own rank tuple. `Deck.ranks` is
# strongest-first, so the last rank is worth one and the first is worth ten.
_RANKS = COMPONENT_SETS[DECK_NAME].deck.ranks
DECK_CAPTURE_VALUES: dict[str, int] = {r: len(_RANKS) - i for i, r in enumerate(_RANKS)}

MAX_CAPTURE_VALUE = max(DECK_CAPTURE_VALUES.values())

# A sum-capture takes two or more cards (the single-card match is forced and is
# a plain filtered movement in the game file, not a joint selection).
MIN_CAPTURE_SET = 2


def capture_value(rank_index: Mapping[str, int], rank: str, reader: str) -> int:
    """A rank's capture value under a declared `ranking:` — one above its
    strength, so the weakest rank is worth one. The game file's
    `capture_value(c) = rank_value(c) + 1` is the same arithmetic over the
    same table. Through `rank_strength`, the one lookup every `rank_index`
    consumer takes, so a rank a partial order does not rank meets that
    function's Owner Guard naming this reader rather than a bare KeyError."""
    return rank_strength(rank_index, rank, reader) + 1


def _values(cards: Sequence[Card], rank_index: Mapping[str, int], reader: str) -> list[int]:
    return [capture_value(rank_index, c.rank, reader) for c in cards]


def sums_to(values: list[int], target: int) -> bool:
    """Whether these cards are a legal sum-capture of a card worth `target`:
    two or more of them, adding up to it exactly."""
    return len(values) >= MIN_CAPTURE_SET and sum(values) == target


# --- the declared Primitives (signatures in primitives_block.PRIMITIVE_IMPLEMENTATIONS) ---


def scopa_sums_to(facts: EngineFacts, gr: reads.GameReads, cards: list[Card], target: int) -> bool:
    """The capture's joint predicate: two or more cards whose capture values
    sum to the played card's. Pure over its argument — the candidate set is the
    joint selection's own."""
    return sums_to(_values(cards, facts.rank_index, "scopa_sums_to"), target)


# --- the subset codec (the joint-selection combo block) ---


class _ScopaCaptureCodec:
    """Every set of two or more `scopa40` cards whose capture values sum to at
    most a King's, index <-> card-set.

    This is the union of `scopa_sums_to`'s satisfying sets over every target a
    played card can carry, which is what the action space needs: a capture
    legal in some position has an id, and which ids are legal in THIS position
    is the movement's own candidate set, matched per state by
    `ActionSpace.match`. A set summing past the largest capture value satisfies
    the predicate for no target and is absent, so `encode_cards` raising on one
    is the loud refusal rather than a wrong id.

    The enumeration walks the deck in build order and grows each prefix, so the
    ordering is a function of the deck registry alone — no hashing and no set
    iteration reaches it, and ids are stable across processes.
    """

    def __init__(self) -> None:
        deck = build_deck(DECK_NAME)
        universe: list[frozenset[Card]] = []
        # Depth-first over the deck in build order, pruning on the value bound:
        # a prefix already past the largest capture value extends to nothing.
        def grow(start: int, chosen: list[Card], total: int) -> None:
            if len(chosen) >= MIN_CAPTURE_SET:
                universe.append(frozenset(chosen))
            for j in range(start, len(deck)):
                v = DECK_CAPTURE_VALUES[deck[j].rank]
                if total + v <= MAX_CAPTURE_VALUE:
                    chosen.append(deck[j])
                    grow(j + 1, chosen, total + v)
                    chosen.pop()

        grow(0, [], 0)
        self._universe = universe
        self._ids = {cards: i for i, cards in enumerate(universe)}
        self.size = len(universe)

    def encode_cards(self, cards: frozenset[Card]) -> int:
        return self._ids[cards]  # KeyError off the universe: loud, not a wrong id

    def decode(self, idx: int) -> frozenset[Card]:
        return self._universe[idx]

    def kind_of(self, idx: int) -> str:
        return "capture"


SCOPA_CAPTURE_CODEC = _ScopaCaptureCodec()
