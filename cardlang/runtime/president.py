"""President's combination engine and game-local Primitive queries.

The corpus's third climbing game (after Tichu and Big Two). The whole hand runs
on the climb [[form]] of [[round]] (`docs/games/president.cardlang`); this module
is the RNG-free combination engine plus the queries the climb round and the game
body name:
`president_lead_options` (lead candidates), `president_follows` (legal follows,
including the transparent-threes variant), and `president_is_top_rank` (the
between-hands exchange filter: is this card the Scum's highest?). The
post-trick leader advance is NOT here: the kernel's `round climb` starts its
ring at the first participant at or after the named leader, so a winner who
shed out on their winning play needs no game-local fallback.

President's combination model is the simplest of the three engines: a play is
1-4 cards of EQUAL rank, suits are entirely irrelevant (no tie-breaks, no
flushes, no straights), there are no bombs, and a follow must be the same size
and strictly higher rank. The rank order is 2 high, 3 low; the live queries
read it from the engine facts' `rank_index` (built by the driver from the game's
`ranking:`), so the engine and the declaration cannot drift.

The one variant carried (Pagat "Transparent cards"): a set made entirely of
threes beats a standing set of the same size regardless of its rank, and TAKES
ON the beaten set's effective rank — the next follower must beat *that* rank,
not the threes'. The climb form threads the standing play but never compares
plays itself (comparison lives entirely in the follows query), so transparency
is implemented by constructing the threes play with `key = current.key`: when
it becomes the standing play, the chain compares against the rank it absorbed.
Led naturally, threes carry their own (lowest) rank.

Scope reduction (random play, the Big Two precedent): each (rank, size) is
offered as ONE representative set — the group's highest-suit cards — rather
than every suit subset. Suits never matter in President, so this changes no
legality whatsoever: any representative beats exactly what any other suit
subset of the same rank and size would beat.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import SUITS, Card, Player

ROW = reads.row("cardlang/runtime/president.py", "president.cardlang")

# The rank order (high to low) — exactly president.cardlang's `ranking:` line,
# mapped to strengths by the driver's formula (first-listed strongest). The
# live queries use the engine facts' `rank_index`; this module-level table
# serves the bundle-free universe enumeration. tests/test_playout_president.py pins the two
# against each other, so the table and the declaration cannot drift.
_RANKING: tuple[str, ...] = ("2", "A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3")
_STRENGTH: dict[str, int] = {r: len(_RANKING) - 1 - i for i, r in enumerate(_RANKING)}

# Highest suit first — only for picking a deterministic representative; suits
# carry no strength in President.
_SUITS_DESC: tuple[str, ...] = tuple(reversed(SUITS))


@dataclass(frozen=True, slots=True)
class Play:
    """A playable set of equal-ranked cards. `key` is the play's EFFECTIVE rank
    strength: the cards' own rank for a natural set, the absorbed standing rank
    for a transparent-threes follow (kind "threes")."""

    kind: str            # "set" (natural equal-rank set) | "threes" (transparent follow)
    size: int            # 1..4
    key: int             # effective rank strength (higher = stronger)
    cards: tuple[Card, ...]


def _by_rank(hand: list[Card]) -> dict[str, list[Card]]:
    """Group a hand by rank, each group's cards sorted highest suit first (a
    deterministic representative order; suits carry no strength)."""
    groups: dict[str, list[Card]] = {}
    for c in hand:
        groups.setdefault(c.rank, []).append(c)
    for cs in groups.values():
        cs.sort(key=lambda c: _SUITS_DESC.index(c.suit))
    return groups


# ---------------------------------------------------------------------------
# The climbing-form Primitive queries (named on `round climb` in president.cardlang)
# ---------------------------------------------------------------------------


def president_lead_options(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card]
) -> list[Play]:
    """Every set the leader may lead: for each rank held, one representative
    set of each size 1..count. A led set of threes is a natural lead — its key
    is the threes' own (lowest) strength; transparency applies only when
    threes BEAT a standing set (the follows query)."""
    strength = facts.rank_index
    leads: list[Play] = []
    for r, cs in _by_rank(hand).items():
        for size in range(1, len(cs) + 1):
            leads.append(Play("set", size, strength[r], tuple(cs[:size])))
    return leads


def president_follows(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card], current: Play
) -> list[Play]:
    """The plays that legally beat the standing play: a natural equal-rank set
    of the SAME size with strictly higher rank strength than the standing
    play's EFFECTIVE rank, plus — the transparent-threes variant — a pure set
    of threes of the same size, regardless of the standing rank (it beats even
    an effective rank of 2, and a standing threes-as-X). The threes play's key
    is the STANDING key: it takes on the rank of the cards it has beaten, so
    the next follower must beat that rank. A natural threes set never beats
    anything (3 is the lowest rank), and a mixed set is impossible (sets are
    equal-rank by construction), so threes appear in a follow pool only via
    the transparent path. Passing is provided by the climb form itself."""
    strength = facts.rank_index
    follows: list[Play] = []
    for r, cs in _by_rank(hand).items():
        if len(cs) >= current.size and strength[r] > current.key:
            follows.append(Play("set", current.size, strength[r], tuple(cs[:current.size])))
    threes = [c for c in hand if c.rank == "3"]
    threes.sort(key=lambda c: _SUITS_DESC.index(c.suit))
    if len(threes) >= current.size:
        follows.append(Play("threes", current.size, current.key, tuple(threes[:current.size])))
    return follows


def president_universe() -> list[Play]:
    """Every play this engine can ever produce over any hand — the combination
    action universe for the OpenSpiel adapter: all sets of 1..4 equal-ranked
    cards (13 ranks x every suit subset of each size; 195 plays, each card-set
    unique). A superset of the queries' representatives, safe by the same rule
    as Big Two's (supersets are safe, collisions are not). A transparent-threes
    follow moves a card-set this enumeration already contains — its action id
    is the card-set's, and its effective key lives in the live candidate, so
    transparency needs no ids of its own."""
    out: list[Play] = []
    for r in _RANKING:
        for size in (1, 2, 3, 4):
            for suits in itertools.combinations(_SUITS_DESC, size):
                out.append(
                    Play("set", size, _STRENGTH[r], tuple(Card(r, s) for s in suits))
                )
    return out


# --- zone / seating / state reads (pure) ---


def president_is_top_rank(
    facts: EngineFacts, gr: reads.GameReads, p: Player, c: Card
) -> bool:
    """Is `c` of the highest rank in `p`'s hand (2 high, 3 low)? The
    between-hands exchange filter: the Scum's give is their single
    highest-ranked card. Suits are irrelevant in President, so when several
    cards tie at the top rank any of them is a faithful give — the filtered
    movement takes the first match in hand order."""
    strength = facts.rank_index
    hand = gr.families["hand"][p]
    return strength[c.rank] == max(strength[x.rank] for x in hand)
