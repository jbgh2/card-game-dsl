"""T5: declaration reorder (docs/design-notes/metamorphic-suite.md, item 4).

Permutes four declaration lists unconditionally — `game.zones`,
`game.move_types`, `game.rules`, and every `StateBlock`'s `.decls` (top-level
AND phase-local, each permuted independently, never merged across blocks).
Permutation is by REVERSAL — the
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

**`game.zones` is reordered for every game.** A gather (`move all cards to
<zone>` — "collect from everywhere") visits zones in canonical
lexicographic-name order (`runtime/execute.py::_gather`; decisions.md, "Loop
lifecycle: `before_each` and `after_each`"), so its per-zone event sequence
is independent of zone declaration order and the zones axis is sound
corpus-wide. This transform originally excluded the gather-using games —
`_gather` used to iterate `ZoneStore`'s declaration-ordered dicts, an order
sensitivity this suite's first run surfaced as a real finding — and the
canonicalization is what retired the exclusion; the reversed-zones pairing
runs over the whole corpus are the regression proof it stays retired.

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

from dataclasses import fields, is_dataclass, replace

from cardlang.ast import nodes as n
from cardlang.diagnostics import Span


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


def reorder_declarations(game: n.Game) -> n.Game:
    """The T5 transform proper: `Game -> Game`, matching `pairing.Transform`.
    Reverses `zones`, `move_types`, and `rules` at the top level, and every
    `StateBlock`'s `decls` wherever one appears (top-level and phase-local,
    independently)."""
    game = replace(
        game,
        zones=tuple(reversed(game.zones)),
        move_types=tuple(reversed(game.move_types)),
        rules=tuple(reversed(game.rules)),
    )
    reordered = _reverse_state_blocks(game)
    assert isinstance(reordered, n.Game)
    return reordered
