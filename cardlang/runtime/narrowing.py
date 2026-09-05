"""The narrow interface a game-local [[primitive]] sees.

A primitive is sanctioned Python for pure value computation (library.md
"Native functions"). Until this module existed, that purity was
conventional: the dispatch layer handed each primitive the engine's whole
`Ctx` and trusted it to self-serve politely. `Ctx` carries the chooser (so
a "pure read" could make a decision), the tracer and observer (so it could
emit), `RuntimeState.set`/`declare` (so it could mutate), and every zone in
the game (so it could read a hidden holding it never declared). Nothing
structural said no.

This module is the no. A narrowed primitive receives the two frozen halves of
its [[primitive-bundle]], plain values and nothing else:

  `EngineFacts`  the engine-structural facts — the seating ring, the
                 team map, the rank strengths, the round accumulator
                 views, the acting player. A CLOSED set: a primitive that
                 needs a fact not listed here cannot reach it, and adding a
                 field is a visible change with a test that pins where the
                 value comes from.
  `GameReads`    the module's declared name-keyed reads (`reads.py`),
                 bounded by its row — the entry's own, built from its
                 declaration, or a walled binder's authored one — and
                 materialized as tuples, so an undeclared zone is absent
                 rather than merely unfetched.

Scope (docs/design-notes/primitive-sidecars.md §5): the two halves are
declared at different granularities, and the difference is the live one.
`GameReads` is PER-PRIMITIVE for a call-position Primitive — its row is built
from the game's own `primitives { }` entry, and an indexed read narrows to the
instance the CALL names — and per-MODULE for the walled namespaces a block
cannot name, whose binders take an authored `PRIMITIVE_READS` row. `EngineFacts` is
whole either way: its field names are not spellable in a `reads` clause, so
every primitive receives every fact (issue #474). What no primitive can do,
under either regime, is mutate, decide, emit, or reach a name nothing
declared.

Contract:
  assumes      the caller is the dispatch layer, holding a live `Ctx`, and
               the primitive has a row — the entry's own, built from its
               declaration, or a walled binder's authored one (issue #535).
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
from typing import Any, NamedTuple

from cardlang.runtime import reads
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Player, Seating


@dataclass(frozen=True, slots=True)
class EngineFacts:
    """The engine-structural facts a game primitive may see.

    Every field mirrors one named engine expression, pinned per field by
    tests/test_primitive_narrowing.py. The set is closed on purpose: it is
    the second half of what a primitive reads, the first being its declared
    zone and state names. Narrowing THIS half per primitive — admitting these
    names into a `reads` clause — is issue #474; a declaration that spells one
    is refused at resolve rather than accepted and dropped.
    """

    seating: Seating
    """The player ring — a frozen value type, so `players`, `turn_order_from`
    and `offset_by` come along without an engine handle."""

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
        "team_of": rs.team_of,
        "rank_index": rs.rank_index,
        "round_state": rs.mech_state[-1] if rs.mech_state else rs.last_round_state,
        "last_round_state": rs.last_round_state,
        "actor": actor,
    }
    return EngineFacts(**{name: reads.deep_freeze(value) for name, value in raw.items()})


class PrimitiveBundle(NamedTuple):
    """The [[primitive-bundle]]: what one narrowed primitive receives.

    A NamedTuple rather than a bare pair, so the two halves carry their names
    at every site that holds the whole thing — and still unpack positionally,
    which is how every primitive's signature reads them."""

    facts: EngineFacts
    reads: reads.GameReads


def bind(
    rs: RuntimeState,
    actor: Player | None,
    r: reads.PrimitiveReads,
    keys: Mapping[str, int | str] | None = None,
    primitive: str | None = None,
    scopes: Mapping[str, str] | None = None,
) -> PrimitiveBundle:
    """The dispatch layer's one call: both bundles for one primitive call.

    `keys` narrows an INDEXED declared read to the one instance a call names —
    the granularity a `primitives { }` entry's `reads hand[p]` buys, applied
    per call because the key is an argument. None materializes the whole row,
    which is what a module-granular declaration means.

    `primitive` is the DECLARED entry's name, passed by the declared dispatch
    alone: it is what a read-miss message names, since a declared entry's fix
    is its own `reads` clause and an authored row's is the registry.

    `scopes` names the phase each [[phase-scoped-read]] was declared in. It
    changes no value — a scoped read materializes through the same frame walk —
    and exists so the one refusal that could otherwise read as a drifted row
    can name the phase and the Owner Guard instead."""
    return PrimitiveBundle(
        engine_facts(rs, actor), reads.game_reads(rs, r, keys, primitive, scopes)
    )
