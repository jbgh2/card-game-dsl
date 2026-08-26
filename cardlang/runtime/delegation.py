"""Delegated Play: who decides at a decision, when that is not the seat the
move is attributed to.

The [[decider]] is the seat that makes the choice; the [[actor]] is the seat
the move belongs to. They coincide everywhere except under Delegated Play
(decisions.md "Delegated play"), whose canonical case is Bridge's dummy:
dummy's card, dummy's trick, declarer's choice. A game opts in by defining
the two helper functions this module names — ordinary per-game functions,
the settled design's rejected alternative being a zone-level construct.

Contract
--------
Assumes: a checked game (helpers, where defined, have passed the signature
Owner Guard in resolve). Establishes: `DECISION_POINTS` classifies every
chooser call site in the engine as routable or actor-only, reconciled
against an AST scrape by `tests/test_delegated_play.py`, so a new decision
point must declare its routing posture to land. Illegal after this: a
`ctx.chooser(...)` call site absent from the table, and consulting the
helpers from an actor-only site.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Player

if TYPE_CHECKING:  # pragma: no cover - typing only
    from cardlang.ast import nodes as n
    from cardlang.runtime.state import Ctx, Zone

# The exact helper names a game defines to opt in (decisions.md "Delegated
# play"). Exact-name docking is the settled design; a misspelled name is an
# ordinary unused function, which is the same recorded trap every magic name
# carries (`hand`, the deck zone) — the signature Owner Guard fires on the
# exact names only.
CHOOSER_HELPER = "chooser_for"
SOURCE_HELPER = "play_source_for"
HELPER_NAMES: frozenset[str] = frozenset({CHOOSER_HELPER, SOURCE_HELPER})

# Every chooser call site in the engine — the decision points (glossary
# "Chooser") — classified. "routable": the site consults the helpers.
# "actor_only": the site never consults them, and a game whose helpers can
# reach no routable site is refused at resolve (issue #458 records the lift).
# Keys are "module.function" of the call site; the grid's AST scrape
# reconciles this table against the tree, so the table cannot go stale
# silently in either direction.
DECISION_POINTS: dict[str, str] = {
    "mechanics.run_decision_round": "routable",
    "execute._select": "actor_only",
    "execute._select_filtered": "actor_only",
    "execute._select_joint": "actor_only",
    "execute._offer": "actor_only",  # designed but witness-gated — issue #458
    "execute._pass_selection": "actor_only",
    "evaluate._choose": "actor_only",
}


# The forms whose decisions the routable site actually routes. TrickForm is
# the witnessed form (Bridge's dummy plays tricks); the auction and climb
# forms share the loop but stay actor-decides until a witness lands — their
# candidate pools have no visibility guard designed yet, so consulting the
# helpers there would route a decider into a pool nothing checked they can
# see. Reconciled against the DecisionForm implementations by
# tests/test_delegated_play.py.
ROUTED_FORMS: frozenset[str] = frozenset({"TrickForm"})


def helper(rs: Any, name: str) -> "n.FunctionDef | None":
    """The game's routing helper of this exact name, or None. Exact-name
    docking: any other spelling is an ordinary function."""
    fn = rs.function_index.get(name)
    return fn if fn is not None and name in HELPER_NAMES else None


def decider_for(ctx: "Ctx", actor: Player) -> Player:
    """The seat that decides `actor`'s round move: `chooser_for(actor)` when
    the game defines it, else the actor. The result must be a real seat —
    the same phantom-decider guard `Ctx.acting_as` applies, fired here so a
    bad helper names itself."""
    fn = helper(ctx.rs, CHOOSER_HELPER)
    if fn is None:
        return actor
    from cardlang.runtime.evaluate import call_user_function

    decided = call_user_function(fn, [actor], ctx)
    if not isinstance(decided, Player) or decided not in ctx.rs.seating.players:
        raise OwnerGuardError(
            f"{CHOOSER_HELPER}({actor}) returned {decided!r}, which is not a "
            f"seat in this game — the decider of a delegated move must be a "
            f"player"
        )
    return decided


def source_for(ctx: "Ctx", actor: Player, declared: "Zone") -> "Zone":
    """The zone `actor` plays this trick from: `play_source_for(actor)` when
    the game defines it, else the round's declared source instance. A helper
    returning anything but a zone is refused here — the checker leaves the
    return type open (zones are a facet, issue #123), so the guard is this
    site's, like the movement executor's."""
    fn = helper(ctx.rs, SOURCE_HELPER)
    if fn is None:
        return declared
    from cardlang.runtime.evaluate import call_user_function
    from cardlang.runtime.state import Zone

    routed = call_user_function(fn, [actor], ctx)
    if not isinstance(routed, Zone):
        raise OwnerGuardError(
            f"{SOURCE_HELPER}({actor}) returned "
            f"{type(routed).__name__}, not a zone — the checker leaves this "
            f"value's type open, so it is checked here"
        )
    return routed
