"""The narrow interface a game-local primitive sees.

A primitive is sanctioned Python for pure value computation (library.md
"Stdlib functions"). Until this module existed, that purity was
conventional: the dispatch layer handed each primitive the engine's whole
`Ctx` and trusted it to self-serve politely. `Ctx` carries the chooser (so
a "pure read" could make a decision), the tracer and observer (so it could
emit), `RuntimeState.set`/`declare` (so it could mutate), and every zone in
the game (so it could read a hidden holding it never declared). Nothing
structural said no.

This module is the no. A narrowed primitive receives two frozen bundles of
plain values and nothing else:

  `EngineFacts`  the engine-structural facts — the seating ring, the
                 partnership map, the rank strengths, the round accumulator
                 views, the acting player. A CLOSED set: a primitive that
                 needs a fact not listed here cannot reach it, and adding a
                 field is a visible change with a test that pins where the
                 value comes from.
  `GameReads`    the module's declared name-keyed reads (`reads.py`),
                 bounded by its `PRIMITIVE_READS` row and materialized as
                 tuples, so an undeclared zone is absent rather than merely
                 unfetched.

Scope (docs/design-notes/primitive-sidecars.md §5, stage 2): the bundles are
MODULE-granular. The design note's §2 end state is per-PRIMITIVE declared
reads, which arrives with the `primitives { }` block in stage 3; until then a
primitive can still see a declared name it does not personally need. What it
can no longer do is mutate, decide, emit, or reach a name its module never
declared.

Contract:
  assumes      the caller is the dispatch layer, holding a live `Ctx`, and
               the primitive's module has a `PRIMITIVE_READS` row.
  establishes  a game module receives values only — no engine handle
               crosses the boundary, so purity is structural (pinned by the
               crossed grid in tests/test_primitive_narrowing.py).
  illegal after it
               `Ctx`, `RuntimeState`, `ZoneStore` or `Chooser` appearing in
               any module under `cardlang/runtime/` outside the engine core.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cardlang.runtime import reads
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Player, Seating

TraceEvent = tuple[str, Any]
"""One deferred trace emission: `(event name, payload)`.

A few primitives compute a real value AND emit the engine's own
`play`/`trick`/`trick_end` trace events from a game-local site. Emitting needs
`ctx.trace`, which is exactly the handle this module removes — so a narrowed
primitive RETURNS its events alongside its value and the dispatch layer
performs the emission. The events stay data until they cross back into the
engine, which keeps the primitive pure without changing what is emitted, in
what order, or when (the goldens are byte-identical either way). Which
primitives do this is pinned both ways by `EMITS_TRACE` in
tests/test_primitive_narrowing.py."""


@dataclass(frozen=True, slots=True)
class EngineFacts:
    """The engine-structural facts a game primitive may see.

    Every field mirrors one named engine expression, pinned per field by
    tests/test_primitive_narrowing.py. The set is closed on purpose: it is
    the second half of what a primitive reads (the first being its declared
    zone/state names), and stage 3's `reads` clause narrows it per primitive.
    """

    seating: Seating
    """The player ring — a frozen value type, so `players`, `turn_order_from`
    and `offset_by` come along without an engine handle."""

    teams: tuple[int, ...]
    """Team ids; empty for non-partnership games."""

    team_of: Mapping[Player, int]
    """Player -> team id."""

    rank_index: Mapping[str, int]
    """Rank -> strength under the game's `ranking:` (higher is stronger)."""

    round_state: Mapping[str, Any] | None
    """The `state` pronoun's view: the LIVE round accumulator while a round
    runs, else the just-completed round's terminal frame. Distinct from
    `last_round_state` — see that field."""

    last_round_state: Mapping[str, Any] | None
    """The just-completed round's terminal frame, unconditionally. NOT the
    same as `round_state` while a round is active: Tarot and Belote read the
    live frame, Tichu's `tichu_dragon_won` reads the terminal one. Collapsing
    the two changes behavior mid-round, so they are separate fields."""

    actor: Player | None
    """The acting player the rules engine bound, for primitives evaluated
    inside a rule's `applies_when`. `None` outside such a context."""


def engine_facts(rs: RuntimeState, actor: Player | None) -> EngineFacts:
    """Snapshot the engine-structural facts for one primitive call.

    EVERY field goes through `deep_freeze`, uniformly — not a hand-picked
    subset. `seating` is the reason: it is a frozen+slots `Seating`, which
    `object.__setattr__` can still mutate (see `deep_freeze`), so passing it
    by identity would expose the live `rs.seating` — the same identity leak
    `deep_freeze` copies away for every other engine dataclass. Building the
    bundle by freezing a dict of raw values (rather than freezing a chosen
    few by hand) makes it structurally impossible to forget a field: a
    scalar `actor` frozen is a no-op, a `Seating` frozen is a copy, a
    round-state dict frozen is a deep snapshot."""
    raw: dict[str, Any] = {
        "seating": rs.seating,
        "teams": rs.teams,
        "team_of": rs.team_of,
        "rank_index": rs.rank_index,
        "round_state": rs.mech_state[-1] if rs.mech_state else rs.last_round_state,
        "last_round_state": rs.last_round_state,
        "actor": actor,
    }
    return EngineFacts(**{name: reads.deep_freeze(value) for name, value in raw.items()})


def bind(
    rs: RuntimeState, actor: Player | None, r: reads.PrimitiveReads
) -> tuple[EngineFacts, reads.GameReads]:
    """The dispatch layer's one call: both bundles for one primitive call."""
    return engine_facts(rs, actor), reads.game_reads(rs, r)
