"""Resolve step: the game's result clauses and its offered move types.

The last step, after every sharper diagnostic: a fixture written to probe
one construct need not also carry a result clause or present every move
type.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the classified tree; the game's own move types, named before
              the splice added a library's.
Establishes:  every result
              ranking -- a ``winner:`` clause, a Stop Result's ranking --
              carries its target declaration's index role
              (``Winner.keyed_by``, ``StopResult.keyed_by``), so no later pass
              walks state declarations to learn how the result is keyed, and
              an ``as it stands`` Stop Result sits only on a game with a
              ``winner:`` clause.
Now illegal:  a
              result ranking's target (``ranking_slot``) that is not a
              per-member score — unindexed, optional, or declared outside
              ``Integer``/``Boolean`` (``_check_winner_target``, decisions.md "Game result:
              `winner:` and `loser:`"); ``runtime/driver`` may therefore
              assume the target reads as a map from member to score, and
              hard-fails on one this pass did not admit as its Shadow Guard.
              One of the game's own move types that no reachable
              ``offer`` presents, with or without a
              Stake row on it (``_check_unoffered_move_types``; a library's
              move types are exempt, since a game importing a library need
              not present every move type it offers); every game move type after this
              pass is one some reachable offering presents.
"""

from __future__ import annotations

from dataclasses import field, replace
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.attribution import cite_named
from cardlang.diagnostics import DiagnosticBag, SlotKind, Unless
from cardlang.resolve.slots import _REFERENCE_SLOTS
from cardlang.resolve.crossings import _definition_closure
from cardlang.resolve.declared import type_slot
from cardlang.resolve.ranking_slots import _result_rankings, ranking_slot


def step(game: n.Game, bag: DiagnosticBag, own_move_types: frozenset[str]) -> n.Game:
    """The result step. Returns the game with every result ranking keyed."""
    game = _check_winner_target(game, bag)
    # Last, so a fixture missing its result clause still surfaces the
    # sharper diagnostic it was aimed at first (bag order is report order).
    _resolve_winner_loser(game, bag)
    # After every sharper diagnostic, for the same reason: a fixture written to
    # probe one move type's declaration need not also present it.
    _check_unoffered_move_types(game, own_move_types, bag)
    return game


# The DEFINITION containers: a statement body reached by NAME, never by
# containment. Every other statement holder (`if`, `repeat until`, `turns`,
# `as`, a `produces:` arm, the loop hooks) sits inside a phase body, so
# walking the phases reaches it; these three are top-level lists on `n.Game`
# and their bodies run only where something names them.
#
# The value is (the `n.Game` field holding them, the reference namespace that
# names one). Authored, and pinned complete against the AST-derived container
# set by `tests/test_trump_slot_class.py::test_every_name_reached_container_
# is_classified` — a new statement-holding definition form fails there rather
# than silently defaulting to "always reachable", which is the shape of the
# defect this table exists to end.
_DEFINITION_CONTAINERS: dict[type, tuple[str, str]] = {
    n.MoveTypeDef: ("move_types", "move_type"),
    n.ProcedureDef: ("procedures", "procedure"),
}

# Runtime refusal (decisions.md "Closed-domain completeness"): each namespace
# above must be one the reference registry actually issues, or the lookup below
# silently matches nothing and every container reads as unreachable.
_UNKNOWN_CONTAINER_NAMESPACES = {
    ns for _, ns in _DEFINITION_CONTAINERS.values()
} - set(_REFERENCE_SLOTS.values())
if _UNKNOWN_CONTAINER_NAMESPACES:
    raise AssertionError(
        f"_DEFINITION_CONTAINERS names namespaces no reference slot issues: "
        f"{sorted(_UNKNOWN_CONTAINER_NAMESPACES)}"
    )


def _reachable_definitions(game: n.Game) -> dict[tuple[str, str], object]:
    """Every definition container reachable from a phase body, keyed by
    (namespace, name).

    A fixpoint, not one pass: a procedure run from a reachable move-type
    effect is reachable, and so is a move type offered from inside a reachable
    procedure body. Which slots NAME a container is read off `slot_namespace`
    rather than matched by node kind, so a future invoking construct added to
    `_REFERENCE_SLOTS` reaches this sweep without editing it.

    NOT a Shadow of `_reaches`: that walks the function-to-function call graph
    for recursion detection (name to name, one namespace). This walks name to
    CONTAINER across two namespaces, and answers a different question — does
    this body run at all. It also does not close issue #242, which is about
    what STATE a callable body may read; this establishes only which bodies
    run, which #242's conservative rule would need but is not."""
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for field, ns in _DEFINITION_CONTAINERS.values()
    }
    return {
        key: target
        for key, (target, _via) in _definition_closure(list(game.phases), pools).items()
    }


def _resolve_winner_loser(game: n.Game, bag: DiagnosticBag) -> None:
    """A game names its result. `winner:` and `loser:` are each optional
    grammar positions, so their joint absence is checked here; without this
    Owner Guard a game with neither would compile clean and then reach a driver that
    requires at least one of them before it can play a single decision."""
    if game.winner is None and game.loser is None:
        bag.error(
            f"game '{game.name}' must declare `winner: <rank-dir> <var>` or "
            "`loser: <player-expr>` — without one the playout has no result",
            game.span,
            code=Code.MISSING_DECLARATION,
        )
    elif game.loser is not None and game.players.count == 1:
        # An elimination names one loser among the survivors, so a one-seat
        # table has nobody left to win. A malformed count is typecheck's.
        bag.error(
            "`loser:` names the player eliminated from the rest, so an "
            "elimination game needs at least two players — this game seats "
            "one; rank a score with `winner:` instead",
            game.loser.span,
            code=Code.USE_WINNER_NOT_LOSER,
        )
    if (
        game.stop_result is not None
        and game.stop_result.kind == "as_it_stands"
        and game.winner is None
        and game.loser is not None
    ):
        # `as it stands` is the result clause read at the stopped position,
        # and a game scored by `winner:` reads it at a stop as at a rules end
        # (issue #247 is the game declaring both).
        bag.error(
            "`as it stands` reads the game's `winner:` clause at the stop, and "
            "this game declares `loser:`, "
            "which a stopped game has not decided: at a Length Stop it would "
            "name nobody, several seats, or the wrong one. Declare `at "
            "max_length: tie` — every seat a winner — or rank a state variable "
            "the game keeps: `at max_length: lowest <variable>`.",
            game.stop_result.span,
            code=Code.USE_WINNER_NOT_LOSER,
        )


# The declared types a game may be RANKED by: totally ordered, and their
# values are what `openspiel/replay.returns_for` hands OpenSpiel as utilities.
# `Boolean` is here on the corpus's authority, not as a lenience -- `cheat`
# ranks on `won[player]` and `coup` on `alive[player]`, so an Integer-only
# rule would refuse two corpus games. Every other member of
# `typecheck.KNOWN_TYPE_NAMES` either cannot be compared at all (`Card` is
# unorderable) or -- worse -- compares fine and means nothing: a
# `Player`-typed target ranks without complaint and delivers SEAT IDS as
# utilities, silently, at every layer.
_RANKABLE_TYPES: frozenset[str] = frozenset({"Integer", "Boolean"})


def _check_unoffered_move_types(
    game: n.Game, own: frozenset[str], bag: DiagnosticBag
) -> None:
    """One of the game's `own` move types (those it declares, not a library's)
    that no reachable `offer` presents is a declaration
    nothing reads (the `_check_unread_clauses` precedent): no seat can ever play it,
    so it is refused, and a Stake row on it is named as the row nothing reads.
    Reachable is `_reachable_definitions`' fixpoint from the phases, so an
    offer inside a move type or procedure nothing reaches presents nothing. A
    library's move types are its own to define: a game that imports one and
    presents it nowhere has not made an error. A move type a library CONTRACTS
    for (`requires { fold : Move }`) is the game's own, and the library's
    offer of it is reachable only where the game runs the procedure holding
    it — so a game that defines it and reaches no offer of it is refused like
    any other game-local move type."""
    offered = {name for ns, name in _reachable_definitions(game) if ns == "move_type"}
    if all(mt.name not in own or mt.name in offered for mt in game.move_types):
        return
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)} for field, ns in _DEFINITION_CONTAINERS.values()
    }
    offers: dict[tuple[str, str], set[str]] = {}
    for ns, field in (("procedure", "procedures"), ("move_type", "move_types")):
        for definition in getattr(game, field):
            reached = {name for kind, name in _definition_closure([definition], pools) if kind == "move_type"}
            offers[(ns, definition.name)] = reached | ({definition.name} if ns == "move_type" else set())
    for mt in game.move_types:
        if mt.name not in own or mt.name in offered:
            continue
        # A misspelled `run` or offer, fixed, reaches what its fix reaches.
        unless = tuple(
            Unless(kind, frozenset(name for (ns, name), names in offers.items() if ns == space and mt.name in names))
            for space, kind in (("procedure", SlotKind.PROCEDURE), ("move_type", SlotKind.MOVE_TYPE))
        )
        if mt.stake is not None:
            bag.error(
                f"`{mt.stake}` on move type " + cite_named(mt, f"`{mt.name}`") + f", which no reachable "
                f"`offer` presents: nothing reads the row. "
                f"Delete it, or present the move at an offering the game reaches",
                mt.span,
                code=Code.UNUSED_DECLARATION,
                unless=unless,
            )
            continue
        bag.error(
            f"move type " + cite_named(mt, f"`{mt.name}`") + f" is never offered: no reachable `offer` "
            f"presents it, so no seat can ever play it. "
            f"Present it at an offering the game reaches, or delete it",
            mt.span,
            code=Code.UNUSED_DECLARATION,
            unless=unless,
        )


def _check_winner_target(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Each result ranking's target must be a state variable a game can be
    ranked by, and the game it returns carries the target's index role on
    the ranking (`Winner.keyed_by`, `StopResult.keyed_by`) -- the one fact
    the result is keyed through. One Owner Guard for both slots
    (`ranking_slot`), each refusal addressed to the slot it fires in.

    Resolve already walls the NAME -- undeclared, or declared inside a phase
    -- and says nothing about the DECLARATION it lands on. Two of that
    declaration's properties decide whether the result path works at all, and
    neither was checked:

    * UNINDEXED. `driver` builds the result with
      `dict(rs.get(game.winner.state_var))`, so a scalar target dies with a
      bare `TypeError: 'int' object is not iterable` (issue #153) -- and in a
      game with a `repeat until` phase it dies earlier still, at the per-hand
      trace, so which Python error the author meets depends on whether their
      game loops.
    * UNRANKABLE TYPE. Nothing anywhere read it. The crashing cells are the
      mild ones; the dangerous cells are the silent ones (`_RANKABLE_TYPES`).

    Reported only when the target IS a game-level declaration. `game.state`
    being absent, and the name resolving to nothing or to a phase-local
    declaration, are all `_check_state_scope`'s to report -- it is the Owner
    Guard for whether a `winner:` name names a game-level state variable at
    all. Speaking here too would add a second diagnostic about a name the
    author has just been told does not exist, burying the one that matters.

    The grid is tests/test_winner_target.py.
    """
    for ranking in _result_rankings(game):
        keyed_by = _ranking_target_role(game, ranking, bag)
        if keyed_by is None:
            continue
        if isinstance(ranking, n.Winner):
            game = replace(game, winner=replace(ranking, keyed_by=keyed_by))
        else:
            game = replace(game, stop_result=replace(ranking, keyed_by=keyed_by))
    return game


def _ranking_target_role(
    game: n.Game, ranking: n.Winner | n.StopResult, bag: DiagnosticBag
) -> str | None:
    """The index role of a ranking's target declaration, or None where the
    declaration is refused here or is another guard's to report."""
    if game.state is None:
        return None
    decl = next((d for d in game.state.decls if d.name == ranking.state_var), None)
    if decl is None:
        return None
    slot = ranking_slot(ranking)
    what = f"{slot.clause} ranks {slot.ranks} on state variable " + cite_named(decl, f"'{decl.name}'") + ", "
    if decl.index is None:
        bag.error(
            f"" + what + f"which is not indexed — a game is ranked by a score each "
            f"player or team holds, so the target is declared "
            "`" + cite_named(decl, decl.name) + "[player]` or `"
            + cite_named(decl, decl.name) + "[team]`. A scalar has no "
            f"per-member value to rank",
            ranking.span,
            code=Code.UNRANKABLE_WINNER_TARGET,
        )
        return None
    if decl.optional:
        bag.error(
            f"" + what + f"declared `{decl.type_name}?` — an optional score may be "
            f"`none`, which cannot be ranked against a number",
            ranking.span,
            code=Code.UNRANKABLE_WINNER_TARGET,
        )
        return None
    if decl.type_name not in _RANKABLE_TYPES:
        rankable = ", ".join(sorted(_RANKABLE_TYPES))
        bag.error(
            f"" + what + f"declared `{decl.type_name}` — a game is ranked by a "
            f"score, so the target must be {rankable}. Its values become "
            f"the game's OpenSpiel returns",
            ranking.span,
            code=Code.UNRANKABLE_WINNER_TARGET,
            unless=Unless(SlotKind.TYPE, _RANKABLE_TYPES, frozenset({type_slot("state", decl.name).name})),
        )
        return None
    return decl.index
