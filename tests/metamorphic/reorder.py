"""T5: declaration reorder (docs/design-notes/metamorphic-suite.md, item 4).

Permutes three top-level declaration lists unconditionally — `game.move_types`,
`game.rules`, and every `StateBlock`'s `.decls` (top-level AND phase-local,
each permuted independently, never merged across blocks) — plus a FOURTH,
`game.zones`, conditionally (see below). Permutation is by REVERSAL — the
simplest nontrivial one (identity only for a list of length <= 1) and, being
an involution, its own inverse.

Why these are safe to reorder: every consumer this module found reads
move-types/rules/state-decls as a NAME-KEYED lookup, never by position —
confirmed by reading every consumption site, not by running the corpus and
hoping:

- **state variables.** `runtime/driver.py::_declare_state` evaluates each
  decl's default IN LIST ORDER, so reordering is safe only if no later
  default expression is evaluated as if an EARLIER sibling in the same block
  had already run — concretely, no default expression references a sibling
  declared in the same block. Checked structurally across every `StateBlock`
  in the corpus (`test_reorder.py::test_no_state_default_reads_a_sibling`),
  not assumed.
- **move types / rules.** `runtime/driver.py` builds `rs.move_type_index` /
  `rs.rule_index` dicts keyed by `.name`. The one place PHASE-level rule
  ORDER is observable — `ctx.active_rules`, `runtime/rules.py`'s demand
  cascade — is built by `runtime/phases.py::compute_active_rules` from the
  PHASE's own `active_rules:` list (`ActiveRules.refs`, phase-body content
  this transform never touches), via `rs.rule_index[name]` lookups: `game.rules`'
  OWN declaration order never reaches it. `typecheck.py`'s move-type/rule
  consumers are per-item checks accumulating into one shared diagnostic bag
  (order can only change WHICH bag item is reported first when several items
  independently error — moot for the corpus, which type-checks clean, and
  for the rejection corpus, whose cases are each single-issue by
  construction, checked below).

**`game.zones` is reordered only for a game with no "gather" movement** —
derived structurally (`_has_gather`: any `Movement` with `source is None`
anywhere in the tree), not hand-listed. Found empirically while building
this transform, then confirmed by reading the code: `runtime/execute.py::
_gather` (`move all cards to <zone>` — "collect from everywhere") iterates
`ctx.rs.zones.singles.items()` then `.families.items()`, and `ZoneStore`
(`runtime/state.py`) builds those two dicts by inserting one entry per
`game.zones` declaration IN DECLARATION ORDER — so a gather's per-zone
visiting order, and therefore the SEQUENCE of "move" events every observer
sees it emit, is a function of zone declaration order. This is real: 3
corpus games' pairing runs caught it directly (cribbage/schnapsen/seven-
card-stud, each reversed and immediately diverging on a gather's event
order), and 10 more corpus games contain the identical `Movement(source=
None)` shape and would diverge the same way if their gather fired inside
this harness's step cap. decisions.md never documents zone declaration
order as meaningful — this is the "declaration order... the engine silently
depending on something semantically inert" class CLAUDE.md names, not a
defect in this transform, and not fixed here (constraints: no `cardlang/`
changes); it is reported as a real finding. `_has_gather` derives the
exclusion from the SAME AST shape that causes it, rather than hand-listing
the 13 affected games (or worse, excluding zones corpus-wide and leaving the
4 unaffected games — coup, getaway, go-fish, gops — untested on this axis
for no reason).

`game.phases` and each phase's `items` (the statement sequence) are
DELIBERATELY excluded — reordering either changes what the game DOES
(decisions.md never claims phase or statement order is meaningless; the
opposite: phases "run in order," "control enters the next sub-phase when the
previous one" — "Sub-phase entry and exit"). `active_rules:` / `legal_moves:`
lists (phase-body content, not top-level declarations) are excluded for the
same reason this module never touches phase bodies at all — they are not one
of decisions.md's order-irrelevant declaration lists.

One more CONFIRMED order-sensitive spot, orthogonal to the gather: `resolve.
_check_duplicate_names`'s "duplicate" diagnostic fires on whichever
occurrence its OWN iteration reaches second — reversing a list with a
duplicate flips WHICH occurrence that is, so the diagnostic's SPAN can move
even though its MESSAGE (the designer-facing text) does not.
`test_reorder.py` compares rejection-corpus diagnostics by `.message`, not
the full rendered `source:line:col:` form, for exactly this reason.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace

from cardlang.ast import nodes as n
from cardlang.diagnostics import Span
from cardlang.resolve import _walk as _resolve_walk


def _has_gather(game: n.Game) -> bool:
    """A `move all cards to <zone>` ("collect from everywhere") anywhere in
    the tree — the shape `runtime/execute.py::_gather` serves by iterating
    `ZoneStore`'s dicts in `game.zones` declaration order (module
    docstring)."""
    return any(
        isinstance(nd, n.Movement) and nd.source is None for nd in _resolve_walk(game)
    )


def _reverse_state_blocks(node: object) -> object:
    if isinstance(node, n.StateBlock):
        node = replace(node, decls=tuple(reversed(node.decls)))
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(value: object) -> object:
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item) for item in value)
    if is_dataclass(value) and not isinstance(value, Span):
        return _reverse_state_blocks(value)
    return value


@dataclass(frozen=True)
class ReorderPlan:
    """What `reorder_declarations` did: `zones_reordered` is False exactly
    when `_has_gather` excluded `game.zones` — surfaced so tests can assert
    the exclusion fired for the right reason, not just infer it from the
    trace comparison passing."""

    zones_reordered: bool


def plan_for(game: n.Game) -> ReorderPlan:
    return ReorderPlan(zones_reordered=not _has_gather(game))


def reorder_declarations(game: n.Game) -> n.Game:
    """The T5 transform proper: `Game -> Game`, matching `pairing.Transform`.
    Reverses `move_types`, `rules` at the top level unconditionally; reverses
    `zones` only when the game has no gather movement (see `plan_for` to
    inspect which happened); reverses every `StateBlock`'s `decls` wherever
    one appears (top-level and phase-local, independently)."""
    zones = game.zones if _has_gather(game) else tuple(reversed(game.zones))
    game = replace(
        game,
        zones=zones,
        move_types=tuple(reversed(game.move_types)),
        rules=tuple(reversed(game.rules)),
    )
    reordered = _reverse_state_blocks(game)
    assert isinstance(reordered, n.Game)
    return reordered
