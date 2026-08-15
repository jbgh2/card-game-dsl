"""The Tichu combination engine (shared, RNG-free).

The enumeration of the combinations a hand can form (singles, pairs, triples, full
houses, straights, consecutive pairs, four-of-a-kind bombs), the legal follows over
a standing play, and the card-point table. Extracted from the Tichu monolith so the
kernel migration can call them as Primitives — ported *verbatim* so the
candidate-list order matches the monolith's chooser draws exactly.

Scope reductions (random play; see docs/kernel-migration.md, Workstream 5,
and issue #140): the Phoenix is a wildcard in
pairs / triples / full houses (not straights / consecutive pairs / bombs);
straight-flush bombs are omitted (four-of-a-kind bombs only); the Mahjong wish is
omitted.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.runtime.values import Card

_RANKVAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "Mahjong": 1, "Dragon": 15}


def _rv(c: Card) -> float | None:
    return _RANKVAL.get(c.rank)  # None for Phoenix / Dog


def _points(c: Card) -> int:
    if c.rank == "Dragon":
        return 25
    if c.rank == "Phoenix":
        return -25
    if c.rank in ("K", "10"):
        return 10
    if c.rank == "5":
        return 5
    return 0


@dataclass(frozen=True, slots=True)
class Play:
    kind: str       # single|pair|triple|fullhouse|straight|pairseq|bomb|dog
    length: int
    key: float      # comparison key within (kind, length); bombs compare across
    cards: tuple[Card, ...]

    @property
    def is_bomb(self) -> bool:
        return self.kind == "bomb"

    @property
    def ends_trick(self) -> bool:
        """A Dog lead ends the trick at once — its followers get no chooser
        draw; the lead passes to the partner (the climb form reads this)."""
        return self.kind == "dog"


def _combos(hand: list[Card]) -> list[Play]:
    """Combinations a hand can form. Phoenix is used as a wildcard in pairs,
    triples, and full houses (not straights/pairseqs/bombs); plain singles cover
    every card. Straight-flush bombs are omitted (four-of-a-kind bombs only)."""
    out: list[Play] = []
    phoenix = next((c for c in hand if c.rank == "Phoenix"), None)
    normal = [c for c in hand if c.rank not in ("Dog", "Dragon", "Phoenix")]

    for c in hand:  # singles (Dog handled as a lead only, Phoenix/Dragon added at call sites)
        if c.rank != "Dog":
            v = _rv(c)
            if v is not None:
                out.append(Play("single", 1, v, (c,)))

    by_rank: dict[float, list[Card]] = {}
    for c in normal:
        by_rank.setdefault(_rv(c), []).append(c)  # type: ignore[arg-type]

    for r, cs in by_rank.items():
        if len(cs) >= 2:
            out.append(Play("pair", 2, r, tuple(cs[:2])))
        if len(cs) >= 3:
            out.append(Play("triple", 3, r, tuple(cs[:3])))
        if len(cs) >= 4:
            out.append(Play("bomb", 4, r, tuple(cs[:4])))
        if phoenix is not None:
            if len(cs) >= 1:
                out.append(Play("pair", 2, r, (cs[0], phoenix)))
            if len(cs) >= 2:
                out.append(Play("triple", 3, r, (cs[0], cs[1], phoenix)))

    # full houses: a triple rank + a different pair rank (Phoenix can fill either)
    triples = [r for r, cs in by_rank.items() if len(cs) >= 3]
    pairs = [r for r, cs in by_rank.items() if len(cs) >= 2]
    for tr in triples:
        for pr in pairs:
            if pr != tr:
                cards = tuple(by_rank[tr][:3] + by_rank[pr][:2])
                out.append(Play("fullhouse", 5, tr, cards))
    if phoenix is not None:  # Phoenix completes a pair atop a natural triple
        for tr in triples:
            for pr, cs in by_rank.items():
                if pr != tr and len(cs) >= 1:
                    cards = tuple(by_rank[tr][:3] + [cs[0], phoenix])
                    out.append(Play("fullhouse", 5, tr, cards))

    # straights (>= 5 consecutive ranks, one card each)
    ranks_present = sorted(by_rank)
    for i in range(len(ranks_present)):
        run = [ranks_present[i]]
        while run[-1] + 1 in by_rank:
            run.append(run[-1] + 1)
        if len(run) >= 5:
            for length in range(5, len(run) + 1):
                for s in range(len(run) - length + 1):
                    seg = run[s:s + length]
                    cards = tuple(by_rank[r][0] for r in seg)
                    out.append(Play("straight", length, seg[-1], cards))

    # consecutive pairs (>= 2 consecutive ranks each with a pair)
    pair_ranks = sorted(r for r, cs in by_rank.items() if len(cs) >= 2)
    for i in range(len(pair_ranks)):
        run = [pair_ranks[i]]
        while run[-1] + 1 in by_rank and len(by_rank[run[-1] + 1]) >= 2:
            run.append(run[-1] + 1)
        if len(run) >= 2:
            for length in range(2, len(run) + 1):
                for s in range(len(run) - length + 1):
                    seg = run[s:s + length]
                    cards = tuple(c for r in seg for c in by_rank[r][:2])
                    out.append(Play("pairseq", length, seg[-1], cards))
    return out


def _legal_follows(hand: list[Card], current: Play) -> list[Play]:
    if current.kind == "dog":
        return []
    phoenix = next((c for c in hand if c.rank == "Phoenix"), None)
    dragon = next((c for c in hand if c.rank == "Dragon"), None)
    follows: list[Play] = []
    for p in _combos(hand):
        if p.is_bomb:
            follows.append(p)  # a bomb beats any non-bomb
        elif p.kind == current.kind and p.length == current.length and p.key > current.key:
            follows.append(p)
    if current.kind == "single":
        if dragon is not None:
            follows.append(Play("single", 1, 15, (dragon,)))
        if phoenix is not None and current.key < 15:  # Phoenix can't top the Dragon
            follows.append(Play("single", 1, current.key + 0.5, (phoenix,)))
    return follows
