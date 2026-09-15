"""Subset enumeration over a card pool — the engine's one home for it.

Two constructs ask the same question of a pool of cards: `where jointly`
enumerates the source's subsets to offer them as one decision
(`runtime/execute.py`), and the subset binder enumerates a zone's subsets to
fold a predicate over them (`runtime/evaluate.py`). The enumeration, its
ordering and its bound are the same question either way, so they are stated
once here rather than once per caller — a second site holding the same
constant is not a second guard, it is the same guard written twice, and the
two wordings drift.

Ordering is deterministic and is part of the contract: sizes ascending, then
`itertools.combinations` in source order. The action-space encoder and the
chooser walk the same list, and a fold that short-circuits must stop at the
same place every run.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from itertools import combinations

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Card

# Beyond this pool size the subset count stops being a sane thing to walk
# (2^16 candidates) — refuse loudly rather than hang. This is a fixed engine
# limit with no game-side setting, and it is a non-termination backstop rather
# than a performance budget: a pool AT the bound is finite, not fast.
ENUMERATION_BOUND = 16


def check_pool(pool: Sequence[Card], what: str, remedy: str) -> None:
    """Refuse a pool too large to enumerate, naming the caller's own remedy.

    `what` names the construct in the designer's words and `remedy` says what
    to do about it, because the two callers are reached from different
    sentences and a shared message would name neither.

    The bound is on the POOL, and the message says so rather than quoting a
    subset count. Both callers can be asked for a bounded slice of the powerset
    — an exact size here, an exact amount there — and for those the pool's
    2^n is not what would be walked, so a message quoting it would be false
    about the very sentence it refuses. What is true of every caller, and is
    the whole reason the limit is a pool size, is that one number is the one a
    designer can hold: the zone is on the page, the arithmetic is not."""
    if len(pool) > ENUMERATION_BOUND:
        raise OwnerGuardError(
            f"{what} over {len(pool)} cards exceeds the enumeration bound "
            f"({ENUMERATION_BOUND} cards), a fixed engine limit with no "
            f"game-side setting; {remedy}"
        )


def sized(pool: Sequence[Card], sizes: Iterable[int]) -> Iterator[tuple[Card, ...]]:
    """Every subset of `pool` whose size is one of `sizes`, in the contract's
    order. Sizes outside `0 .. len(pool)` contribute nothing rather than
    raising: a count the source cannot supply is an empty domain, which is the
    reading a `where` that empties a zone already has."""
    for k in sizes:
        if 0 <= k <= len(pool):
            yield from combinations(pool, k)
