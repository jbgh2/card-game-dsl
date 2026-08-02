"""Pure parsing of the engine's information-state string.

Everything the rule-based baseline decides and everything the metrics layer
measures is derived HERE — from the same bytes the LLM sees — rather than from
the live `RuntimeState`. That is deliberate: a fact this module can compute is
a fact the acting player is entitled to, so a baseline built on it inherits the
same leak-freeness argument the LLM agent does (BUILDLOG, "Leak-freeness").

The format is `cardlang/openspiel/infostate.py`'s `information_state`:

    P<n>|<zone>=<view>;...|state:<k>=<v>;...|obs:<repr>;...

with a zone view rendered as `[c1,c2,...]` (identity), `#k` (count only), or
`?` (nothing). This module parses the first three sections; the observation log
is kept as an opaque string, since nothing below needs to interpret it.

Contract
--------
Assumes: a string produced by `information_state` for a standard-52 game.
Establishes: `Info`, whose fields are exactly the observer's entitled view.
Illegal after: reading game facts from anywhere but an `Info` (or an action
string) inside `agents.py` and `metrics.py`.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

# The 13 standard ranks, as cards render them. Two separate facts ride on this
# tuple and they are reconciled separately, because only one of them is the
# engine's:
#
#   MEMBERSHIP is the deck's rank set. Held as a literal rather than imported so
#   this module stays a pure string parser with no engine dependency;
#   `test_infostate.py` reconciles it against `cardlang.runtime.values.RANKS` as
#   a SET, so a deck change reddens instead of silently mis-parsing.
#
#   ORDER is Cheat's claim cycle (A, 2, ... K, back to A) from `next_rank` in
#   `docs/games/cheat.cardlang` — deliberately NOT the engine constant's order,
#   which is aces-high (2 ... A). It is used only as a deterministic tie-break
#   when the rule agent picks a card to discard, and `test_game.py` pins it
#   against the cycle a live game actually walks.
RANKS: tuple[str, ...] = (
    "A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K",
)

COPIES_PER_RANK = 4  # a standard 52-card deck holds four of each rank


def rank_of(card: str) -> str:
    """The rank of a rendered card (`'10♥'` -> `'10'`). The suit is always the
    final character; every card renders as rank followed by one suit glyph."""
    return card[:-1]


@dataclass(frozen=True)
class Info:
    """One observer's parsed view at one decision point."""

    player: int
    zones: dict[str, list[str] | int | None]
    state: dict[str, str]
    obs: str

    @property
    def hand(self) -> list[str]:
        """The observer's own hand — identities, since a `Hand<player>` projects
        in full to its owner. Raises if the view is a count: that would mean the
        parser was handed another player's perspective, which no caller does."""
        view = self.zones[f"hand[{self.player}]"]
        if not isinstance(view, list):
            raise ValueError(
                f"hand[{self.player}] rendered as {view!r}, not identities — "
                f"this Info is not the acting player's own view"
            )
        return view

    def count_of_rank(self, rank: str) -> int:
        """How many cards of `rank` the observer holds."""
        return sum(1 for c in self.hand if rank_of(c) == rank)

    def hand_size(self, player: int) -> int:
        """Any player's hand size — identities for the observer, the projected
        count for everyone else. Both are entitled information."""
        view = self.zones[f"hand[{player}]"]
        if isinstance(view, list):
            return len(view)
        if isinstance(view, int):
            return view
        raise ValueError(f"hand[{player}] is not visible even as a count")

    @property
    def claim_rank(self) -> str:
        return self.state["claim_rank"]

    @property
    def claim_count(self) -> int:
        return int(self.state["claim_count"])

    @property
    def claimant(self) -> int:
        return int(self.state["claimant"])


def _parse_zone_view(text: str) -> list[str] | int | None:
    if text == "?":
        return None
    if text.startswith("#"):
        return int(text[1:])
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        return inner.split(",") if inner else []
    raise ValueError(f"unrecognized zone view {text!r}")


def parse(info_state: str) -> Info:
    """Parse an information-state string into its three entitled sections.

    Raises on anything that does not match the layout rather than returning a
    partially-populated `Info`: a silently-empty parse would make every
    downstream metric read zero, which is the "vacuously green" failure mode.
    """
    head, _, rest = info_state.partition("|")
    if not head.startswith("P") or not rest:
        raise ValueError(f"not an information-state string: {info_state[:60]!r}")
    player = int(head[1:])

    zones_text, sep, rest = rest.partition("|state:")
    if not sep:
        raise ValueError("information state has no `state:` section")
    state_text, sep, obs = rest.partition("|obs:")
    if not sep:
        raise ValueError("information state has no `obs:` section")

    zones: dict[str, list[str] | int | None] = {}
    for entry in zones_text.split(";"):
        name, _, view = entry.partition("=")
        zones[name] = _parse_zone_view(view)

    state: dict[str, str] = {}
    for entry in state_text.split(";"):
        if not entry:
            continue
        key, _, value = entry.partition("=")
        state[key] = value

    return Info(player=player, zones=zones, state=state, obs=obs)


def zone_player(zone: str) -> int | None:
    """The seat a `hand[n]` zone label names, or None for any other zone."""
    if zone.startswith("hand[") and zone.endswith("]"):
        return int(zone[5:-1])
    return None


def parse_events(obs: str) -> list[tuple[Any, ...]]:
    """The observer's event log, decoded from the `obs:` section.

    `information_state` renders the log as `";".join(repr(e) for e in log)`,
    where every entry is a tuple of card strings, zone names, ints and move
    names — none of which can contain a `;`, so the split is exact rather than
    merely usually-right. Decoded with `ast.literal_eval`, which accepts only
    literals, and any chunk that is not a tuple raises: a silently-dropped event
    would weaken the exclusion analysis below into unsoundness-by-omission,
    which is the one failure mode this module must not have.
    """
    events: list[tuple[Any, ...]] = []
    for chunk in obs.split(";"):
        if not chunk:
            continue
        value = ast.literal_eval(chunk)
        if not isinstance(value, tuple):
            raise ValueError(f"observation log entry is not a tuple: {chunk!r}")
        events.append(value)
    return events


def cards_known_elsewhere(info: Info, claimant: int) -> dict[str, int]:
    """Cards the observer can prove are NOT in `claimant`'s hand, from the
    public challenge record. Maps card -> the seat known to hold it.

    A challenge routes the flipped cards into one named hand, in view of the
    whole table (`('move', 'flipped', (cards...), 'hand[X]', ...)`). That tells
    every observer where those specific cards went. The knowledge is not
    permanent: a card can only ever reach the claimant's hand by being played
    into the pile and then collected, so it survives exactly until the claimant
    picks up a pile.

    Deliberately conservative at that point — ANY pile pickup by the claimant
    discards ALL flip-derived knowledge, not just the cards whose holder has
    played since. A finer analysis (invalidate a card only when its holder
    played between the observation and the pickup) would exclude more, and is
    left undone on purpose: this function is the soundness-critical half of the
    provable-lie criterion, and its guarantee is checked against ground truth
    over whole games in `test_infostate_widened.py`. Precision that is not
    obviously sound is worth less here than a bound that is.
    """
    holder: dict[str, int] = {}
    for event in parse_events(info.obs):
        if not event or event[0] != "move" or len(event) < 5:
            continue
        source, payload, destination = event[1], event[2], event[3]
        seat = zone_player(str(destination))
        if seat is None:
            continue
        if source == "pile" and seat == claimant:
            # The claimant collected an unseen pile. Any card previously seen
            # elsewhere could have been played into it since, so nothing
            # flip-derived survives.
            holder.clear()
        elif source == "flipped" and isinstance(payload, tuple):
            for card in payload:
                holder[str(card)] = seat
    return {card: seat for card, seat in holder.items() if seat != claimant}


def _excluded_count(info: Info, claim_rank: str, claimant: int) -> int:
    """How many cards of `claim_rank` the observer can prove the claimant does
    not hold: their own, plus those the challenge record places elsewhere."""
    own = {c for c in info.hand if rank_of(c) == claim_rank}
    elsewhere = {
        card
        for card in cards_known_elsewhere(info, claimant)
        if rank_of(card) == claim_rank
    }
    return len(own | elsewhere)  # a card cannot be in both, but union is safest


def provably_false_hand_only(info: Info, claim_rank: str, claim_count: int) -> bool:
    """The narrow criterion: the observer's own hand alone.

    Kept alongside the widened one so the improvement is measurable and the
    previously-reported number stays quotable.
    """
    return info.count_of_rank(claim_rank) + claim_count > COPIES_PER_RANK


def provably_false(
    info: Info, claim_rank: str, claim_count: int, claimant: int | None = None
) -> bool:
    """Is the standing claim *logically impossible* from what the observer knows?

    A standard deck holds four of each rank, so a claim of `claim_count` cards
    of `claim_rank` is impossible once the observer can account for more than
    `4 - claim_count` of that rank in places the claimant cannot be holding —
    their own hand, plus cards the public challenge record places in another
    player's hand (`cards_known_elsewhere`).

    Sound by construction and checked against ground truth over whole games:
    every card counted is one the claimant demonstrably cannot have played.
    Still incomplete — it draws no inference from pile contents the observer
    partially knows, or from the claimant's own past pickups — so a reported
    detection rate remains a LOWER bound on the observer's opportunity.

    `claimant` defaults to the value in the observer's public state, which is
    the seat whose play stands in the window.
    """
    seat = info.claimant if claimant is None else claimant
    return _excluded_count(info, claim_rank, seat) + claim_count > COPIES_PER_RANK
