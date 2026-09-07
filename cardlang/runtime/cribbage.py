"""Cribbage's runtime support (pure Primitives).

The whole hand — the crib discards, the starter cut (his heels), pegging
(fifteens, pairs, runs, 31, go / last card), and the show (fifteens, pairs,
runs, flush, his nob over non-dealer / dealer / crib in order, stopping the
instant a player crosses 121) — runs in the DSL (docs/games/cribbage.cardlang)
as filtered [[transfer]]s, ordinary statement control flow, and, for the show,
subset queries over the hand listed with the starter. This module holds what
is not expressible there:

- `peg_pairs`/`peg_run` — the pegging-count scorers, pure over their
  arguments so they can be unit-tested against known counts independent of
  the bundle-taking adapters below. `peg_run` takes the rank order as a
  parameter — the adapter passes `facts.rank_index`, built by the driver from
  the game's `ranking: aces low` — so this module holds NO private copy of
  the rank order; the declaration is the single source of truth for what
  "adjacent ranks" means. `peg_pairs` reads no order at all, which is why its
  adapter is the control the rank-index scrape discriminates against
  (tests/test_primitives_block.py) and why the two adapters share no helper.
  (The pegging COUNT values are the game file's own `card_points { }`
  clause, read at the pegging sites.)
- `peg_origin`/`peg_origin_of` — the pegging sub-round's card-provenance
  decoder. Zones don't retain who moved a card, and no `round` [[form]] fits
  pegging's per-play scoring plus forced-play flow (docs/kernel-migration.md,
  WS4), so `phase play` tracks provenance itself as two Integer state vars
  (`seq_bits` packs one bit per play, MSB first, 1 = dealer; `seq_len` counts
  the plays — both public information, since everyone at the table watched
  the count). `peg_origin_of` decodes them to route a `play_pile` card to
  `played[dealer]` / `played[nondealer]` at each sub-round close.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cardlang.runtime import reads
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player, rank_strength


# --- pegging ---


def peg_pairs(seq: Sequence[Card]) -> int:
    """Pair points at the tail of the live count: rank EQUALITY over the run of
    cards matching the last one, so no rank order is consulted."""
    if len(seq) < 2:
        return 0
    n_same = 1
    for c in reversed(seq[:-1]):
        if c.rank == seq[-1].rank:
            n_same += 1
        else:
            break
    return n_same * (n_same - 1) if n_same >= 2 else 0


def peg_run(seq: Sequence[Card], order: Mapping[str, int]) -> int:
    """`order` as in `run_score`: the declared ranking's `rank_index`, whose
    dense consecutive strengths carry the run-adjacency meaning (and whose
    misses `rank_strength` refuses, naming the Primitive that asked)."""
    for k in range(len(seq), 2, -1):
        orders = [rank_strength(order, c.rank, "peg_run_points") for c in seq[-k:]]
        if len(set(orders)) == k and max(orders) - min(orders) == k - 1:
            return k
    return 0


def peg_pair_points(facts: EngineFacts, gr: reads.GameReads) -> int:
    """The pair points the card just played scores against the live pegging
    pile."""
    return peg_pairs(gr.singles["play_pile"])


def peg_run_points(facts: EngineFacts, gr: reads.GameReads) -> int:
    """The run points the card just played scores against the live pegging
    pile, under the game's declared rank order."""
    return peg_run(gr.singles["play_pile"], facts.rank_index)


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
