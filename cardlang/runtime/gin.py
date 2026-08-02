"""Gin Rummy's runtime support (pure stdlib primitives).

The whole hand — the upcard ritual, the draw-discard `turns` loop, the knock,
the showdown's declared arrangements (joint selections), the layoffs, and the
knock/gin/undercut scoring — runs in the DSL (docs/games/gin-rummy.cardlang).
This module holds what is not expressible there:

- `card_points` — A=1, pips, face=10. The `card_value()` deck table is empty
  for standard52 (`cardlang/runtime/values.py`), and `cards:` has no syntax
  for a per-game point table, so the points are a primitive — Cribbage's
  `peg_value` precedent exactly.
- `valid_meld` — a set (3-4 of a rank) or a run (3+ consecutive, same suit,
  ace low). The joint validity of a card GROUP; per-card filters cannot say
  it, which is what the `where jointly` surface exists for.
- `minimal_deadwood` — the optimal meld partition's leftover points. The
  combinatorial floor under three DSL guards: knock legality ("SOME
  arrangement has <= 10"), the arrangement guard (`gin_arrange_ok`: this
  meld keeps a legal knock reachable), and the gin test (0 after discard).
  Subset enumeration and recursion are not DSL-expressible (the
  stress-branch finding that motivated this whole workstream).
- `GIN_MELD_CODEC` — the meld universe of standard52 (329 melds: 65 sets +
  264 runs) as the joint-selection subset codec (`joint_codec_function`,
  the climb-engine codec pattern): pure card-set <-> index functions the
  OpenSpiel action space sizes its combo block by.
- ctx-adapters (`gin_deadwood`, `gin_knock_ok`, `gin_arrange_ok`,
  `gin_can_declare`, `gin_flat_points`, `gin_lay_ok_*`) reading hands, meld
  zones, and the `knocker` state var.

Every adapter is a pure function of the game state it reads — no hidden
state, no RNG (decisions.md kernel doctrine: meaning never state).
"""

from __future__ import annotations

from itertools import combinations

from cardlang.runtime import reads
from cardlang.runtime.sidecar import EngineFacts
from cardlang.runtime.values import Card, Player

# Every zone this module reads by name is declared in PRIMITIVE_READS
# (cardlang/runtime/reads.py) — the declared-reads coupling contract; the
# accessors below are the only sanctioned way to touch state by name.
ROW = reads.row("cardlang/runtime/gin.py", "gin-rummy.cardlang")

_POINTS = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
           "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}
# Run order: ace LOW, always (A-2-3 melds; Q-K-A does not).
_ORDER = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
          "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}
_RANKS_LOW_TO_HIGH = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_SUITS = ["clubs", "diamonds", "hearts", "spades"]


def card_points(c: Card) -> int:
    """Deadwood value: A=1, face cards 10, otherwise pips."""
    return _POINTS[c.rank]


def flat_points(cards: list[Card]) -> int:
    """The plain point sum — a hand counted as all-deadwood."""
    return sum(card_points(c) for c in cards)


def valid_meld(cards: list[Card]) -> bool:
    """A set (3-4 of the same rank) or a run (3+ consecutive same-suit, ace
    low). The joint predicate under every arrangement decision."""
    if len(cards) < 3:
        return False
    ranks = {c.rank for c in cards}
    if len(ranks) == 1:
        return len(cards) <= 4
    suits = {c.suit for c in cards}
    if len(suits) != 1 or len(ranks) != len(cards):
        return False
    order = sorted(_ORDER[c.rank] for c in cards)
    return order[-1] - order[0] == len(cards) - 1


def _candidate_melds(cards: list[Card]) -> list[frozenset[int]]:
    """Every valid meld formable from `cards`, as index sets. Sets of 3-4 per
    rank; runs as every 3+-length window of each suit's consecutive stretches
    (windows, not just maximal stretches: the optimum may split a long
    stretch to free a card for a set)."""
    melds: list[frozenset[int]] = []
    by_rank: dict[str, list[int]] = {}
    for i, c in enumerate(cards):
        by_rank.setdefault(c.rank, []).append(i)
    for idxs in by_rank.values():
        for size in (3, 4):
            melds.extend(frozenset(combo) for combo in combinations(idxs, size))
    by_suit: dict[str, list[int]] = {}
    for i, c in enumerate(cards):
        by_suit.setdefault(c.suit, []).append(i)
    for idxs in by_suit.values():
        ordered = sorted(idxs, key=lambda i: _ORDER[cards[i].rank])
        # Split into consecutive stretches, then take every >=3 window.
        stretch: list[int] = []
        stretches: list[list[int]] = []
        for i in ordered:
            if stretch and _ORDER[cards[i].rank] != _ORDER[cards[stretch[-1]].rank] + 1:
                stretches.append(stretch)
                stretch = []
            stretch.append(i)
        stretches.append(stretch)
        for s in stretches:
            for length in range(3, len(s) + 1):
                for start in range(len(s) - length + 1):
                    melds.append(frozenset(s[start : start + length]))
    return melds


def minimal_deadwood(cards: list[Card]) -> int:
    """Minimal total point value of unmelded cards over every partition of
    `cards` into disjoint valid melds plus deadwood. Exhaustive with
    branch-and-bound: hands are <= 11 cards, and branching is anchored on the
    lowest-indexed undecided card (it is either deadwood or in one of the
    candidate melds containing it), so the tree is small."""
    if not cards:
        return 0
    melds = _candidate_melds(cards)
    best = flat_points(cards)

    def go(unused: frozenset[int], acc: int) -> None:
        nonlocal best
        if acc >= best:
            return
        if not unused:
            best = acc
            return
        first = min(unused)
        for meld in melds:
            if first in meld and meld <= unused:
                go(unused - meld, acc)
        go(unused - {first}, acc + card_points(cards[first]))

    go(frozenset(range(len(cards))), 0)
    return best


# --- the meld-universe codec (the joint-selection combo block) ---


class _GinMeldCodec:
    """The 329 melds of standard52 (65 sets + 264 runs), index <-> card-set.
    Deterministic ordering (sets by rank then suit-combination, runs by suit
    then start then length — no hash order anywhere), so action ids are
    stable across processes; `joint_codec_function` serves it to the
    OpenSpiel action space (decisions.md "Joint-predicate selection")."""

    def __init__(self) -> None:
        universe: list[tuple[str, frozenset[Card]]] = []
        for rank in _RANKS_LOW_TO_HIGH:
            cards = [Card(rank, s) for s in _SUITS]
            for size in (3, 4):
                for combo in combinations(cards, size):
                    universe.append(("set", frozenset(combo)))
        for suit in _SUITS:
            run = [Card(r, suit) for r in _RANKS_LOW_TO_HIGH]
            for length in range(3, len(run) + 1):
                for start in range(len(run) - length + 1):
                    universe.append(("run", frozenset(run[start : start + length])))
        self._universe = universe
        self._ids = {cards: i for i, (_, cards) in enumerate(universe)}
        self.size = len(universe)

    def encode_cards(self, cards: frozenset[Card]) -> int:
        return self._ids[cards]  # KeyError on a non-meld: loud, not a wrong id

    def decode(self, idx: int) -> frozenset[Card]:
        return self._universe[idx][1]

    def kind_of(self, idx: int) -> str:
        return self._universe[idx][0]


GIN_MELD_CODEC = _GinMeldCodec()


# --- ctx-adapters (the DSL-visible signatures live in builtins/signatures.py) ---


def _hand(gr: reads.GameReads, player: Player) -> list[Card]:
    """The player's full private holding: `hand[p]` plus the `taken[p]`
    staging zone (the just-taken discard, held apart so the "must discard a
    different card" rule is structural — the discard/knock candidate pool is
    `hand` alone, but deadwood counts everything held)."""
    held = list(gr.families["hand"][player])
    held.extend(gr.families["taken"][player])
    return held


def gin_deadwood(facts: EngineFacts, gr: reads.GameReads, player: Player) -> int:
    """The optimal partition's deadwood of `hand[player]`."""
    return minimal_deadwood(_hand(gr, player))


def gin_can_knock(facts: EngineFacts, gr: reads.GameReads, player: Player) -> bool:
    """Knock availability — the `end_knock` announce guard: some card FROM THE
    HAND ZONE can be discarded leaving a <= 10 arrangement of everything else
    held. The discard candidates are exactly the knock movement's pool —
    `hand[player]`, never the `taken` staging card (the "must discard a
    different card" rule) — while the kept arrangement counts everything held.
    Quantifying the discard over hand+taken instead was the 3%-of-seeds crash
    class: a hand whose ONLY knock-legal discard is the taken card offered the
    announce and then had zero movement candidates. Exactly
    `any c in hand: gin_knock_ok(c)` — the no-implicit-actions pairing."""
    held = _hand(gr, player)
    hand_only = list(gr.families["hand"][player])
    return any(minimal_deadwood([c for c in held if c != d]) <= 10 for d in hand_only)


def gin_knock_ok(facts: EngineFacts, gr: reads.GameReads, player: Player, discard: Card) -> bool:
    """Knock legality: discarding `discard` leaves a hand some arrangement of
    which has <= 10 deadwood (Pagat: knock after drawing, by discarding)."""
    rest = [c for c in _hand(gr, player) if c != discard]
    return minimal_deadwood(rest) <= 10


def gin_valid_meld(facts: EngineFacts, gr: reads.GameReads, cards: list[Card]) -> bool:
    """The defender's arrangement guard: any valid meld."""
    return valid_meld(list(cards))


def gin_arrange_ok(facts: EngineFacts, gr: reads.GameReads, player: Player, cards: list[Card]) -> bool:
    """The knocker's arrangement guard: `cards` is a valid meld AND declaring
    it keeps a legal knock reachable — the rest of the hand still arranges to
    <= 10 deadwood. Every offered arrangement decision therefore stays
    knock-legal, random play included (the stress-branch staging mechanic's
    failure, closed by construction)."""
    group = list(cards)
    if not valid_meld(group):
        return False
    taken = set(group)
    rest = [c for c in _hand(gr, player) if c not in taken]
    return minimal_deadwood(rest) <= 10


def gin_can_declare(facts: EngineFacts, gr: reads.GameReads, player: Player) -> bool:
    """Whether any declarable meld exists — the `declare_meld` move guard:
    some meld in the hand passes `gin_arrange_ok` (valid, and the remainder
    still arranges to <= 10). Checked by direct enumeration over the hand's
    candidate melds, the same universe the joint selection enumerates, so
    the guard is true exactly when the movement would have a candidate (the
    no-implicit-actions pairing)."""
    hand = _hand(gr, player)
    for meld in _candidate_melds(hand):
        group = [hand[i] for i in meld]
        taken = set(group)
        rest = [c for c in hand if c not in taken]
        if minimal_deadwood(rest) <= 10:
            return True
    return False


def gin_can_declare_free(facts: EngineFacts, gr: reads.GameReads, player: Player) -> bool:
    """The defender's declare guard: any valid meld exists in the hand — no
    knock budget (a defender may arrange however they like; suboptimal is
    rule-legal). The no-implicit-actions pairing for `declare_meld_d`."""
    hand = _hand(gr, player)
    return any(valid_meld([hand[i] for i in meld]) for meld in _candidate_melds(hand))


def gin_flat_points(facts: EngineFacts, gr: reads.GameReads, player: Player) -> int:
    """The hand counted as all-deadwood — the `finish_arranging` guard (the
    undeclared remainder IS the shown deadwood) and the scoring counts."""
    return flat_points(_hand(gr, player))


def gin_shown_points(facts: EngineFacts, gr: reads.GameReads, player: Player) -> int:
    """The point count of `shown_deadwood[player]` — the scoring read after
    both arrangements (and any layoffs) are on the table."""
    return flat_points(list(gr.families["shown_deadwood"][player]))


def _extends_meld(card: Card, meld: list[Card]) -> bool:
    # The slot zone is read at each wrapper with its literal name (the
    # declared-reads scan refuses a variable name at an accessor call).
    return bool(meld) and valid_meld(meld + [card])


def gin_lay_ok_a(facts: EngineFacts, gr: reads.GameReads, card: Card, knocker: Player) -> bool:
    """Layoff legality onto the knocker's first shown meld: the extended
    group is still a valid meld. (Cards never lay off on deadwood; the gin
    case is guarded in the DSL — layoff is skipped entirely.)"""
    return _extends_meld(card, list(gr.families["meldA"][knocker]))


def gin_lay_ok_b(facts: EngineFacts, gr: reads.GameReads, card: Card, knocker: Player) -> bool:
    """Layoff legality onto the knocker's second shown meld."""
    return _extends_meld(card, list(gr.families["meldB"][knocker]))


def gin_lay_ok_c(facts: EngineFacts, gr: reads.GameReads, card: Card, knocker: Player) -> bool:
    """Layoff legality onto the knocker's third shown meld."""
    return _extends_meld(card, list(gr.families["meldC"][knocker]))
