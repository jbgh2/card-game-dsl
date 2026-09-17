"""The [[opponent]] that plays by what a game declares.

`ranked` answers from two things and nothing else: the [[seat-view]] it is
handed, and the declarations of the checked game it was built against. It reads
no game by name — what it does at a decision follows from the declared ranking,
the `winner:` clause's direction, and the library type of the zones the view
shows it, all of which every game states for itself.

What it does with each block of action ids is `DISPOSITIONS`, keyed by
`encoding.BLOCKS`:

- **card** — ranked only while a trick is IN PROGRESS, which the view says by
  showing cards in the trick pile. Holding cards that would take it, it plays
  the cheapest of them where the game wants its score high, and otherwise sheds
  the dearest card that takes nothing. A card takes the trick when it outranks
  every card of the suit led, and a card of the trump suit outranks any card
  that is not — the trump being the one the game's Trick Round declares, read
  through the view where the round names a State Variable rather than fixing a
  suit, as Oh Hell, Bridge and Pinochle all do. Where nothing on offer takes and
  the game wants its score high, it throws the cheapest card of the suit the
  hand is long in, counted over the zone the decision plays from — which is not
  always the seat's own, since a game may seat a decision with one player and
  the cards with another.

  Five things send the decision to the draw instead: a game that declares no
  ranking; one that declares a `trick_order { }` of its own (its trumps and
  strengths are expressions this reads nothing of); one that keeps more than one
  trick pile, or whose rounds name different trumps, where which round a
  decision belongs to is not a fact the view carries; a throw whose source zone
  the view cannot name, which a deck that repeats a card can leave undecidable;
  and an EMPTY trick pile, which does not mean a lead. The card block numbers
  every decision that offers a card — a hand passed to a neighbour before play,
  a discard, cards staged for a meld — and nothing the seat is handed tells
  those from leading. Ranking them alike ranks a decision by a rule the game
  never stated, so the lead goes to the draw until the view carries which
  decision it is (issue #713).
- **integer** — a number near the tricks its own cards look like taking: the
  cards in the top two ranks of the declared ranking, plus trump length past a
  fair share of the deck's suits, clamped to what is on offer. The same
  heuristic the playout instrument uses, stated deck-agnostically. This ASSUMES
  a number decision is a bid on the hand, which the block cannot say and two of
  the three games offering one mean; Cheat's number is the count a player claims
  to be playing and may be lying about, and this answers it as though it were a
  bid (issue #713).
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

import dataclasses
from collections import Counter
from collections.abc import Sequence
from typing import Any

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.seat_policy import SeatBinding, UniformSeatPolicy
from cardlang.runtime.values import Card, deck_suits
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


def _played_from(view: SeatView, offered: Sequence[Card]) -> list[Card] | None:
    """Every card of the one zone this decision plays from — the single zone
    instance the view shows holding all of `offered`.

    Which zone that is cannot be assumed to be the seat's own: a game may seat
    the decision with one player and the cards with another, as a hand played
    face up by its partner is. Nor is it a question about zone NAMES, since two
    instances of one name are two hands. Where a deck repeats a card, two zones
    can each hold what is offered and the view cannot tell which is the source;
    it says so by returning None rather than choosing."""
    wanted = Counter(offered)
    found: list[Card] | None = None
    for _, shown in view.zones:
        if not isinstance(shown, tuple):
            continue
        cards = [card for card in shown if isinstance(card, Card)]
        counted = Counter(cards)
        if all(counted[card] >= count for card, count in wanted.items()):
            if found is not None:
                return None
            found = cards
    return found


_DISAGREE = object()


def _declared_trump(game: n.Game) -> Any:
    """What the game's Trick Rounds say their trump is: a suit name, a
    `NameRef` to the State Variable holding it, or None where they declare
    none. A game whose rounds disagree returns `_DISAGREE` — which round a
    decision belongs to is not a fact the view carries, so a policy that
    picked one would be picking.

    The top-level `trump:` declaration is the fallback for a game that states
    it once for the whole game rather than on the round."""
    specs = [rnd.trump for rnd in _trick_rounds(game)]
    if not specs:
        return game.trump
    first = specs[0]
    for other in specs[1:]:
        if _spec_key(other) != _spec_key(first):
            return _DISAGREE
    return first if first is not None else game.trump


def _spec_key(spec: Any) -> Any:
    """Two trump declarations are the same declaration when they name the same
    thing — a `NameRef` is not equal to another by value."""
    return spec.name if isinstance(spec, n.NameRef) else spec


def _trick_rounds(game: n.Game) -> list[Any]:
    """Every Trick Round the checked game declares, wherever it sits."""
    out: list[Any] = []

    def walk(node: Any) -> None:
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            if type(node).__name__ == "TrickRound":
                out.append(node)
            for field in dataclasses.fields(node):
                walk(getattr(node, field.name))
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(game)
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
        self.suits = deck_suits(binding.game.deck)
        self.trump_spec = _declared_trump(binding.game)
        # A declared Trick Order states its trumps and strengths as expressions,
        # and a second trick pile leaves the trick in progress unidentified.
        # Either way the cards on the table are not a fact this can read.
        self.reads_the_trick = (
            binding.game.trick_order is None
            and len(self.trick_zones) < 2
            and self.trump_spec is not _DISAGREE
        )
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
        trump = self._trump_now(view)
        if trump is not None:
            fair_share = len(cards) // max(1, len(self.suits))
            likely += max(0, sum(1 for card in cards if card.suit == trump) - fair_share)
        return likely

    def _card(self, view: SeatView, legal: Sequence[int]) -> int:
        """The cheapest card that takes the trick, or the dearest that does
        not, by the direction the game's `winner:` clause names."""
        if not self.reads_the_trick:
            return self.draw(view, legal)
        table = _cards_in(view, self.trick_zones)
        if not table:
            # An empty trick pile does not say this is a lead. The card block
            # numbers every decision that offers a card — a hand passed to a
            # neighbour before play, a discard, cards staged for a meld — and
            # which of them this is is not a fact the view carries. Ranking it
            # as a lead ranks a decision by a rule the game never stated.
            return self.draw(view, legal)
        trump = self._trump_now(view)
        cheapest = sorted(legal, key=lambda aid: (self._worth(aid), aid))
        led = table[0].suit
        best = max((self._takes(card, led, trump) for card in table), default=(False, 0))
        takes = [
            aid for aid in legal if self._takes(self.space.decode(aid), led, trump) > best
        ]
        if self.wants_high:
            if takes:
                return min(takes, key=lambda aid: (self._worth(aid), aid))
            return self._thrown(view, legal)
        misses = [aid for aid in legal if aid not in takes]
        return max(misses, key=lambda aid: (self._worth(aid), -aid)) if misses else cheapest[0]

    def _trump_now(self, view: SeatView) -> str | None:
        """The suit that trumps at this decision. A game may fix it once for
        the whole game, or name a State Variable its Trick Round points at and
        set it as the deal turns it up — Oh Hell, Bridge and Pinochle all do
        the second, so reading the fixed declaration alone reads no trump at
        all in three of the corpus's trick games."""
        spec = self.trump_spec
        if isinstance(spec, n.NameRef):
            value = dict(view.state).get(spec.name)
            return value if isinstance(value, str) else None
        return spec if isinstance(spec, str) else None

    def _takes(self, card: Card, led: str, trump: str | None) -> tuple[bool, int]:
        """How far a card gets in the trick: a card of the declared trump suit
        outranks every card that is not one, and among cards of one suit the
        declared ranking orders them. A card of neither the trump suit nor the
        suit led takes nothing."""
        if trump is not None and card.suit == trump:
            return (True, self.strength.get(card.rank, 0))
        if card.suit == led:
            return (False, self.strength.get(card.rank, 0))
        return (False, 0)

    def _thrown(self, view: SeatView, legal: Sequence[int]) -> int:
        """Which card to throw when none on offer takes the trick: the cheapest
        of the suit the hand is long in, and its cheapest card overall where it
        holds no suit twice. Throwing the cheapest card outright spends the last
        card of a short suit, which is the one still able to take a trick in it.

        The suits are counted over every card of the zone the decision plays
        from — not over the cards on offer, since a rule that filters what may
        be played says nothing about which suit the hand is long in; and not
        over the seat's own zones, since the hand being played may belong to
        another seat. Where the view cannot name that zone the length of the
        hand is not a fact this can read, and the card is drawn."""
        source = _played_from(view, [self.space.decode(aid) for aid in legal])
        if source is None:
            return self.draw(view, legal)
        held: dict[str, int] = {}
        for card in source:
            held[card.suit] = held.get(card.suit, 0) + 1
        return min(
            legal,
            key=lambda aid: (
                -held.get(self.space.decode(aid).suit, 0),
                self._worth(aid),
                aid,
            ),
        )

    def _worth(self, aid: int) -> int:
        card = self.space.decode(aid)
        return self.strength.get(card.rank, 0)

