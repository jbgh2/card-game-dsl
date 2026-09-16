"""The [[opponent]] that plays by what a game declares.

`ranked` answers from two things and nothing else: the [[seat-view]] it is
handed, and the declarations of the checked game it was built against. It reads
no game by name — what it does at a decision follows from the declared ranking,
the `winner:` clause's direction, and the library type of the zones the view
shows it, all of which every game states for itself.

What it does with each block of action ids is `DISPOSITIONS`, keyed by
`encoding.BLOCKS`:

- **card** — the trick's cards are the view's trick-pile zones. Holding cards
  that would take the trick, it plays the cheapest of them where the game wants
  its score high, and otherwise sheds the dearest card that takes nothing;
  leading, it leads its dearest where the game wants its score high and its
  cheapest where it wants it low. A game that declares no ranking has nothing
  to rank by, and the decision is drawn instead.
- **integer** — a number near the tricks its own cards look like taking: the
  cards in the top two ranks of the declared ranking, plus trump length past a
  fair share, clamped to what is on offer. The same heuristic the playout
  instrument uses, stated deck-agnostically.
- **combination** — the fewest cards that are legal, so a hand is spent slowly;
  ties by the lowest id, which keeps the answer a function of the view.
- **name**, **offering** — drawn uniformly, and the table says so. Which side
  of an offer is a wager is not a fact any game states today (issue #703), and
  an opponent that guessed would be guessing in shipped code.

Every answer is a function of the binding's seed and the view, as a Seat Policy
must be: the draw it delegates to is the uniform opponent on that seed, and
every ranking breaks ties by the lowest id.

Contract
--------
Assumes: a checked game, its action space, and a seat that game seats.
Establishes: the answer is one of the legal ids; it is a function of the seed
and the view; every block of `encoding.BLOCKS` has a disposition, and a block
whose ids are not all alike at one decision is drawn rather than ranked.
Illegal after: reading the World, a decision node, or any game by name; ranking
a block `DISPOSITIONS` calls delegated.
"""

from __future__ import annotations

from collections.abc import Sequence

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.seat_policy import SeatBinding, UniformSeatPolicy
from cardlang.runtime.values import Card
from cardlang.stdlib.zones import ZONE_PROJECTIONS

# What `ranked` does with each block of action ids. The keys are
# `encoding.BLOCKS`; a block with no row is a decision nobody has taken.
DISPOSITIONS: dict[str, str] = {
    "card": "ranked",
    "integer": "ranked",
    "combination": "ranked",
    "name": "delegated",
    "offering": "delegated",
}


def _strengths(game: n.Game) -> dict[str, int]:
    """Each declared rank's strength, dearest first in the declaration."""
    return {rank: len(game.ranking) - place for place, rank in enumerate(game.ranking)}


def _zone_names(game: n.Game, wanted: str) -> frozenset[str]:
    """The names of the game's zones of library type `wanted`."""
    return frozenset(zone.name for zone in game.zones if zone.type_ref.name == wanted)


def _private_names(game: n.Game) -> frozenset[str]:
    """The names of the zones whose type shows identity to their owner and less
    to everyone else — the seat's own cards, wherever the game keeps them."""
    out = set()
    for zone in game.zones:
        vis = ZONE_PROJECTIONS[zone.type_ref.name]
        if vis.owner == "identity" and vis.others != "identity":
            out.add(zone.name)
    return frozenset(out)


def _cards_in(view: SeatView, names: frozenset[str]) -> list[Card]:
    """Every card the view shows in a zone of one of `names`. A zone the view
    shows as a count is another seat's and reads as no cards at all."""
    out: list[Card] = []
    for label, shown in view.zones:
        name = label.split("[", 1)[0]
        if name in names and isinstance(shown, tuple):
            out.extend(card for card in shown if isinstance(card, Card))
    return out


class RankedSeatPolicy:
    """Plays by the game's declarations; see the module docstring."""

    def __init__(self, binding: SeatBinding) -> None:
        self.game = binding.game
        self.space = binding.space
        self.seat = binding.seat
        self.draw = UniformSeatPolicy(binding.seed)
        self.strength = _strengths(binding.game)
        self.trick_zones = _zone_names(binding.game, "TrickPile")
        self.private_zones = _private_names(binding.game)
        self.wants_high = None if binding.game.winner is None else binding.game.winner.rank_dir == "highest"

    def __call__(self, view: SeatView, legal: Sequence[int]) -> int:
        blocks = {self.space.block_of(aid) for aid in legal}
        if len(blocks) != 1:
            # A decision offering ids of two kinds — a combination beside a
            # bare "pass" — is one this opponent has no ranking over: ranking
            # one kind and drawing among the rest is a ranking nobody declared.
            return self.draw(view, legal)
        block = blocks.pop()
        if DISPOSITIONS[block] != "ranked":
            return self.draw(view, legal)
        if block == "combination":
            return self._combination(legal)
        if self.wants_high is None or not self.strength:
            return self.draw(view, legal)
        if block == "integer":
            return self._number(view, legal)
        return self._card(view, legal)

    def _combination(self, legal: Sequence[int]) -> int:
        """The fewest cards on offer, ties by the lowest id."""
        return min(legal, key=lambda aid: (len(self.space.decode(aid).cards), aid))

    def _number(self, view: SeatView, legal: Sequence[int]) -> int:
        """The number nearest what the seat's own cards look like taking."""
        return min(legal, key=lambda aid: (abs(self.space.decode(aid) - self._likely(view)), aid))

    def _likely(self, view: SeatView) -> int:
        cards = _cards_in(view, self.private_zones)
        if not cards:
            return 0
        top = max(self.strength.values())
        likely = sum(1 for card in cards if self.strength.get(card.rank, 0) >= top - 1)
        if self.game.trump is not None:
            suits = {card.suit for card in cards}
            fair_share = len(cards) // max(1, len(suits))
            likely += max(0, sum(1 for card in cards if card.suit == self.game.trump) - fair_share)
        return likely

    def _card(self, view: SeatView, legal: Sequence[int]) -> int:
        """The cheapest card that takes the trick, or the dearest that does
        not, by the direction the game's `winner:` clause names."""
        table = _cards_in(view, self.trick_zones)
        dearest = sorted(legal, key=lambda aid: (-self._worth(aid), aid))
        cheapest = sorted(legal, key=lambda aid: (self._worth(aid), aid))
        if not table:
            return dearest[0] if self.wants_high else cheapest[0]
        led = table[0].suit
        best = max(
            (self.strength.get(card.rank, 0) for card in table if card.suit == led),
            default=0,
        )
        takes = [
            aid
            for aid in legal
            if self.space.decode(aid).suit == led and self._worth(aid) > best
        ]
        if self.wants_high:
            if takes:
                return min(takes, key=lambda aid: (self._worth(aid), aid))
            return self._thrown(legal)
        misses = [aid for aid in legal if aid not in takes]
        return max(misses, key=lambda aid: (self._worth(aid), -aid)) if misses else cheapest[0]

    def _thrown(self, legal: Sequence[int]) -> int:
        """Which card to throw when none on offer takes the trick: the cheapest
        of the suit the seat holds most of, and its cheapest card overall where
        it holds no suit twice. Throwing the cheapest card outright spends the
        last card of a short suit, which is the one still able to take a trick
        in it. Where a game makes a seat follow suit, every legal
        card is of one suit and this is that suit's cheapest."""
        held: dict[str, int] = {}
        for aid in legal:
            suit = self.space.decode(aid).suit
            held[suit] = held.get(suit, 0) + 1
        return min(
            legal,
            key=lambda aid: (-held[self.space.decode(aid).suit], self._worth(aid), aid),
        )

    def _worth(self, aid: int) -> int:
        card = self.space.decode(aid)
        return self.strength.get(card.rank, 0)

