"""Cribbage's runtime support (pure stdlib primitives).

The whole hand — the crib discards, the starter cut (his heels), pegging
(fifteens, pairs, runs, 31, go / last card), and the show (fifteens, pairs,
runs, flush, his nob over non-dealer / dealer / crib in order, stopping the
instant a player crosses 121) — runs in the DSL (docs/games/cribbage.cardlang)
as filtered movements and ordinary statement control flow. This module holds
what is not expressible there:

- `value`/`count_fifteens`/`count_pairs`/`run_score`/`flush_score`/
  `nob_score`/`show_score` — the show's combination scorers, and
  `peg_pair_points`/`peg_run_points` — the pegging-count scorers. Module-level
  so they can be unit-tested against known cribbage hands (the strongest
  falsifiable check for a counting game) independent of the ctx-adapter
  wiring below. The run scorers take the rank order as a parameter — the
  ctx adapters pass `rs.rank_index`, built by the driver from the game's
  `ranking: aces low` — so this module holds NO private copy of the rank
  order; the declaration is the single source of truth for what "adjacent
  ranks" means.
- `peg_origin`/`peg_origin_of` — the pegging sub-round's card-provenance
  decoder. Zones don't retain who moved a card, and no `round` form fits
  pegging's per-play scoring plus forced-play flow (docs/kernel-migration.md,
  WS4), so `phase play` tracks provenance itself as two Integer state vars
  (`seq_bits` packs one bit per play, MSB first, 1 = dealer; `seq_len` counts
  the plays — both public information, since everyone at the table watched
  the count). `peg_origin_of` decodes them to route a `play_pile` card to
  `played[dealer]` / `played[nondealer]` at each sub-round close.
- `cribbage_show_value`/`cribbage_crib_value` — the show's per-zone
  adapters, reading `played[player]` / `crib` against the shared `starter`.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import combinations

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/cribbage.py", "cribbage.cardlang")

_VALUE = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
          "10": 10, "J": 10, "Q": 10, "K": 10}


def value(c: Card) -> int:
    """Pegging / fifteens value: A=1, face cards 10, otherwise pips."""
    return _VALUE[c.rank]


# --- the show ---


def count_fifteens(cards: list[Card]) -> int:
    vals = [_VALUE[c.rank] for c in cards]
    subsets = sum(
        1
        for r in range(2, len(vals) + 1)
        for combo in combinations(vals, r)
        if sum(combo) == 15
    )
    return 2 * subsets


def count_pairs(cards: list[Card]) -> int:
    return 2 * sum(1 for a, b in combinations(cards, 2) if a.rank == b.rank)


def run_score(cards: list[Card], order: Mapping[str, int]) -> int:
    """Length × multiplicity of the run (≥3) over the ranks (a 5-card show hand
    contains at most one run). `order` is the game's declared rank order —
    `ctx.rs.rank_index` from cribbage.cardlang's `ranking: aces low` — under
    which "a run" means ranks ADJACENT in the declaration: strengths are dense
    consecutive integers (the driver's `enumerate` formula), so A-2-3 runs and
    Q-K-A does not, exactly the A-low no-wraparound rule. `order` must cover
    every rank it is asked for, exactly as `rank_value` requires — the same
    partial-`ranking:` residual, moot here since `aces low` covers the whole
    deck."""
    counts: dict[int, int] = {}
    for c in cards:
        counts[order[c.rank]] = counts.get(order[c.rank], 0) + 1
    distinct = sorted(counts)
    i = 0
    while i < len(distinct):
        j = i
        while j + 1 < len(distinct) and distinct[j + 1] == distinct[j] + 1:
            j += 1
        length = j - i + 1
        if length >= 3:
            mult = 1
            for k in range(i, j + 1):
                mult *= counts[distinct[k]]
            return length * mult
        i = j + 1
    return 0


def flush_score(hand4: list[Card], starter: Card, is_crib: bool) -> int:
    if len({c.suit for c in hand4}) != 1:
        return 0
    if starter.suit == hand4[0].suit:
        return 5
    return 0 if is_crib else 4


def nob_score(hand4: list[Card], starter: Card) -> int:
    return 1 if any(c.rank == "J" and c.suit == starter.suit for c in hand4) else 0


def show_score(hand4: list[Card], starter: Card, is_crib: bool, order: Mapping[str, int]) -> int:
    five = [*hand4, starter]
    return (
        count_fifteens(five)
        + count_pairs(five)
        + run_score(five, order)
        + flush_score(hand4, starter, is_crib)
        + nob_score(hand4, starter)
    )


# --- pegging ---


def peg_pair_points(seq: list[Card]) -> int:
    if len(seq) < 2:
        return 0
    n_same = 1
    for c in reversed(seq[:-1]):
        if c.rank == seq[-1].rank:
            n_same += 1
        else:
            break
    return n_same * (n_same - 1) if n_same >= 2 else 0


def peg_run_points(seq: list[Card], order: Mapping[str, int]) -> int:
    """`order` as in `run_score`: the declared ranking's `rank_index`, whose
    dense consecutive strengths carry the run-adjacency meaning."""
    for k in range(len(seq), 2, -1):
        orders = [order[c.rank] for c in seq[-k:]]
        if len(set(orders)) == k and max(orders) - min(orders) == k - 1:
            return k
    return 0


# --- pegging provenance (see the module docstring) ---


def peg_origin(seq_bits: int, seq_len: int, position: int) -> int:
    """1 if the position-th play (0-based, oldest first) of the current
    pegging sub-round was made by the dealer, else 0."""
    return (seq_bits >> (seq_len - 1 - position)) & 1


def peg_origin_of(facts: EngineFacts, gr: reads.GameReads, c: Card) -> Player:
    """Which player played `c` in the live pegging sub-round: reads `c`'s
    position in `play_pile` (the sub-round's cards, oldest first) against the
    `seq_bits`/`seq_len`/`dealer` state `phase play` maintains. Must be read
    before `play_pile` is drained for this sub-round — the close routing reads
    every card's origin before either split movement removes anything."""
    position = gr.singles["play_pile"].index(c)
    seq_bits = gr.state["seq_bits"]
    seq_len = gr.state["seq_len"]
    dealer: Player = gr.state["dealer"]
    if peg_origin(seq_bits, seq_len, position):
        return dealer
    return next(p for p in facts.seating.players if p != dealer)


def cribbage_show_value(
    facts: EngineFacts, gr: reads.GameReads, p: Player
) -> int:
    """`p`'s show score: `played[p]` holds exactly the monolith's `hand4[p]`
    snapshot once pegging ends (every card started in `hand[p]` and is routed
    to `played[p]`, never the crib), scored against the shared starter."""
    hand4 = list(gr.families["played"][p])
    starter = gr.singles["starter"][0]
    return show_score(hand4, starter, is_crib=False, order=facts.rank_index)


def cribbage_crib_value(facts: EngineFacts, gr: reads.GameReads) -> int:
    """The dealer's crib show score against the shared starter."""
    crib = list(gr.singles["crib"])
    starter = gr.singles["starter"][0]
    return show_score(crib, starter, is_crib=True, order=facts.rank_index)
