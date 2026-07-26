"""A state variable's default is evaluated while the state block is still being
declared, so it can only reach state that already exists.

Seeded by the family-library audit: a library's PROVIDED default reading one of
its own `requires` names was accepted by the front end and died at playout on a
bare ``KeyError`` from ``runtime/state.py``. The splice puts every provided decl
before every game decl (`resolve._apply_uses`), so a required name is never in
scope where a provided default runs — but nothing said so, and the branch
shipped a control-row test COMMANDING that sentence accepted.

The class is not the library, though: after the splice a provided default and a
game default are the same node in the same block, and a plain game reproduces the
defect with no `uses` line at all. So the wall is the base language's, swept over
the whole scope relation rather than patched at the library end (decisions.md
"Closed-domain completeness": sweep the class, don't patch the instance).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `state { }` default that `check_dsl` accepts survives declare
            time — no `KeyError: variable '…' not in scope`, and no other
            runtime error from evaluating it before the world exists. Every
            cell asserts BOTH halves: refused cells are refused with a located
            diagnostic, accepted cells are actually PLAYED.
domain:     TWO axes, each read off its own registry rather than off the wall.

            (1) The SCOPE relation, for a name in the default's own tree:
            the state-block tree crossed with every declared name. `_BLOCKS`
            below is the tree; `_in_scope` computes the expected column from
            the declaration order `runtime/driver` actually uses (a frame per
            phase, pushed on entry and popped on exit), so no cell is pinned
            to what the code happens to do.

            (2) The `n.Expr` UNION — every expression kind the grammar can put
            in a default position, not the kinds this wall handles. That axis
            is what found the `Choose` cell, which no witness and no argument
            had suggested: the "two channels, direct and indirect" reasoning
            that preceded it was an argument about NAMES, and a `choose` needs
            an acting player rather than a name. An argument is not a sweep.
registry:   `_BLOCKS` + `runtime/driver.run_phase`'s frame discipline for (1);
            `n.Expr` for (2).
covered:    all 32 scope cells (4 reader sites x 8 targets), executed and
            played; all 19 `n.Expr` rows, executed
            (`test_every_expression_kind_is_accounted_for_in_a_default`, whose
            axis is pinned equal to the union itself); 3 call cells; both
            library cells (in `test_family_libraries.py`).
sampled:    two shapes, each a single instance standing for a family.
            The scope axis uses one block tree, chosen to contain every
            relation the runtime can produce — enclosing, self, later-sibling,
            sibling-phase, nested-phase — so a deeper tree adds instances of
            relations already covered, not new relations. The `n.Expr` axis
            runs in one game (2 players, `standard52`, a deck and a hand), so
            a kind whose declare-time behaviour depends on the SHAPE of the
            game rather than on the expression — a quantifier over teams in a
            game with no `partnerships`, a query over a positional zone — is
            sampled by proxy, not swept. The team case was spot-checked and is
            clean (an empty role domain evaluates to `false`, it does not
            crash); the rest are unprobed, and belong to whatever wall owns
            empty role domains rather than to this one.
residual:   none. `AllPlayers` was this grid's one open row — `v : Integer =
            all players` was accepted because a default was never checked
            against its declared type — and it is now closed by the type wall
            (`test_state_default_type.py`, decisions.md "State scoping
            (lexical)"), which refuses it along with the other precisely-typed
            mismatches (`StrLit`, `ListLit`). Those three appear in
            `_EXPR_REFUSED` above, refused before declare order is reached; the
            record that named this residual has moved to the type wall's ledger.
"""

from __future__ import annotations

import random
from typing import get_args

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# The block tree the direct grid is derived from: block -> (parent, ordered
# vars). Parent is the ENCLOSING state block, which is exactly the runtime's
# frame chain — `driver` pushes a frame per phase and pops it at phase end, so
# `beta` cannot see `alpha`'s state and `game` cannot see either.
_BLOCKS: dict[str, tuple[str | None, tuple[str, str]]] = {
    "game": (None, ("g1", "g2")),
    "alpha": ("game", ("a1", "a2")),
    "inner": ("alpha", ("i1", "i2")),
    "beta": ("game", ("b1", "b2")),
}

# Each reader writes its SECOND variable's default, so the same-block axis has
# an earlier sibling (legal), itself (illegal) and a later sibling (illegal).
_READER_INDEX = 1


def _in_scope(reader_block: str, target_block: str, target_index: int) -> bool:
    """The property, stated once: a default reaches a name iff the name is
    declared earlier in the same block, or in a STRICT ancestor block."""
    if target_block == reader_block:
        return target_index < _READER_INDEX
    ancestor = _BLOCKS[reader_block][0]
    while ancestor is not None:
        if ancestor == target_block:
            return True
        ancestor = _BLOCKS[ancestor][0]
    return False


def _decls(block: str, reader_block: str, read: str) -> str:
    parts = []
    for i, name in enumerate(_BLOCKS[block][1]):
        default = read if (block == reader_block and i == _READER_INDEX) else "1"
        parts.append(f"{name} : Integer = {default}")
    return "  ".join(parts)


def _probe(reader_block: str, read: str) -> str:
    def block(name: str) -> str:
        return "state { " + _decls(name, reader_block, read) + " }"

    return f"""
game Probe {{
  players: 2
  cards: standard52
  max_length: 100
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0
           {_decls("game", reader_block, read)} }}
  phase alpha {{ {block("alpha")}
    phase inner {{ {block("inner")} }}
  }}
  phase beta {{ {block("beta")} }}
  winner: highest score
}}
"""


def _direct_cells() -> list[object]:
    return [
        pytest.param(
            reader,
            target_block,
            target_index,
            id=f"{reader}-reads-{_BLOCKS[target_block][1][target_index]}",
        )
        for reader in sorted(_BLOCKS)
        for target_block in sorted(_BLOCKS)
        for target_index in (0, 1)
    ]


@pytest.mark.parametrize("reader,target_block,target_index", _direct_cells())
def test_a_default_reaches_exactly_what_is_already_declared(
    reader: str, target_block: str, target_index: int
) -> None:
    """The direct channel, over the whole scope relation. The expected column is
    computed by `_in_scope` from the runtime's own declaration order, so a cell
    cannot be pinned to whatever the code happens to do.

    red under: drop the `< _READER_INDEX` from `_in_scope` (fails the
    same-block cells), or delete the ancestor walk (fails the cross-block ones).
    """
    target = _BLOCKS[target_block][1][target_index]
    source = _probe(reader, target)
    expected = _in_scope(reader, target_block, target_index)

    if not expected:
        with pytest.raises(DiagnosticError) as exc:
            check_dsl(source, "scope.cardlang")
        assert exc.value.diagnostic.span is not None, (
            "a scope refusal must be located, not a bare error"
        )
        assert target in exc.value.diagnostic.message
        return

    game = check_dsl(source, "scope.cardlang")
    # The half that matters: an ACCEPTED default must actually survive declare
    # time. A cell that only checked `check_dsl` would have passed on the
    # defect this file exists to close.
    play_game(game, random.Random(0))


def test_the_grid_commands_both_outcomes() -> None:
    """A guard on the grid itself: if every cell expected the same answer the
    sweep above would prove nothing, and a broken `_in_scope` could make that
    true silently.

    red under: return a constant from `_in_scope`."""
    verdicts = {
        _in_scope(reader, block, index)
        for reader in _BLOCKS
        for block in _BLOCKS
        for index in (0, 1)
    }
    assert verdicts == {True, False}


# cell -> (the state block, the callee's body). The body varies with the cell so
# that each one fails on the CALL and not on something incidental: giving the
# no-state cell a body that reads `a` would refuse it as an unresolved name and
# prove nothing.
_CALL_CELLS: dict[str, tuple[str, str]] = {
    "reads-later-var": (
        "state { score[player] : Integer = 0"
        "  b : Integer = helper()  a : Integer = 7 }",
        "a",
    ),
    "reads-earlier-var": (
        "state { score[player] : Integer = 0"
        "  a : Integer = 7  b : Integer = helper() }",
        "a",
    ),
    "reads-no-state": (
        "state { score[player] : Integer = 0  b : Integer = helper() }",
        "1 + 1",
    ),
}


@pytest.mark.parametrize("cell", sorted(_CALL_CELLS))
def test_a_default_may_not_call(cell: str) -> None:
    """The indirect channel, refused outright rather than followed into the
    callee. All three cells are refused, including the two that would run clean
    today — this is a deliberate narrowing, not an approximation of a
    reachability analysis, and it is recorded as one in decisions.md
    "State scoping (lexical)".

    Following the body instead would mean an interprocedural scope check
    (nested calls, mutual recursion) bought for a capability no game in the
    corpus uses: an AST scan of every `state` default across `docs/games/` and
    `docs/libraries/` finds `IntLit` and `NameRef` only, and the only spellings
    are `none`, `false`, `true` and `hold`. Not one default reads a state
    variable, let alone calls anything.

    red under: delete the `n.Call` arm from the default check."""
    state_block, body = _CALL_CELLS[cell]
    source = f"""
game Probe {{
  players: 2
  cards: standard52
  max_length: 100
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  {state_block}
  phase play {{ }}
  winner: highest score
}}
function helper() = {body}
"""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "call.cardlang")
    assert exc.value.diagnostic.span is not None
    assert "helper" in exc.value.diagnostic.message


# Every member of `n.Expr`, in default position: kind -> (declared type, the
# default, any top-level text it needs). The verdict column is deliberately not
# here — it is asserted below, so a kind that changes behaviour fails rather
# than being re-described.
_EXPR_CELLS: dict[str, tuple[str, str, str]] = {
    "NameRef": ("Integer", "first", ""),
    "IntLit": ("Integer", "7", ""),
    "StrLit": ("Integer", '"s"', ""),
    "CardLiteral": ("Card?", "(Q of hearts)", ""),
    "ListLit": ("Integer", "[1, 2]", ""),
    "Member": ("Integer", "state.first", ""),
    "Subscript": ("Integer", "score[0]", ""),
    "StructLit": ("T", "T { x: 1 }", "type T = { x : Integer }\n"),
    "Call": ("Integer", "helper()", "function helper() = 1\n"),
    "BinOp": ("Integer", "3 + 4", ""),
    "Not": ("Boolean", "not false", ""),
    "IsCheck": ("Boolean", "none is none", ""),
    "Quantifier": ("Boolean", "any player where score[player] > 0", ""),
    "IfExpr": ("Integer", "if false then 1 else 2", ""),
    "Comprehension": ("Integer", "sum of 1 over cards in deck", ""),
    "Choose": ("Integer", "choose integer in 0 .. 3", ""),
    "PlayerQuery": ("Integer", "number of players where score[player] > 0", ""),
    "CardQuery": ("Integer", "number of cards in deck", ""),
    "AllPlayers": ("Integer", "all players", ""),
    "DomainQuery": ("Boolean", "any column where first > 0", ""),
}

# Every kind that must be REFUSED, and by whose wall — the grid's property is
# "accounted for", not "refused by THIS wall", so a cell a sibling default-check
# owns is listed with the message that check emits. Everything else must survive
# declare time, asserted by PLAYING it, not by accepting it.
#   - Call / Choose: this file's `_check_state_default_scope`.
#   - Member: the pre-existing `state.`-publishes check, long before declare order.
#   - StrLit / ListLit / AllPlayers: the TYPE wall
#     (`test_state_default_type.py`) — a `String` / collection default cannot fit
#     the `Integer` these cells declare, so they never reach declare time. This
#     is where the `AllPlayers` row that was this grid's one residual is closed.
_EXPR_REFUSED = {
    "Call": "cannot call",
    "Choose": "cannot `choose`",
    "Member": "publishes no",
    "StrLit": "is declared",
    "ListLit": "is declared",
    "AllPlayers": "is declared",
    "DomainQuery": "unknown position domain",
}


def test_the_expr_axis_is_the_whole_union() -> None:
    """The grid's second axis is `n.Expr` itself, so an expression kind added to
    the language joins it or fails here. Deriving the axis from the kinds the
    wall already handles is the failure this guard exists to prevent — it is how
    the `Choose` cell stayed invisible through an argument that sounded complete.

    red under: delete a key from `_EXPR_CELLS`."""
    union = {arg.__name__ for arg in get_args(n.Expr)}
    assert set(_EXPR_CELLS) == union, (
        f"unswept: {sorted(union - set(_EXPR_CELLS))}; "
        f"stale: {sorted(set(_EXPR_CELLS) - union)}"
    )


@pytest.mark.parametrize("kind", sorted(_EXPR_CELLS))
def test_every_expression_kind_is_accounted_for_in_a_default(kind: str) -> None:
    """Each kind is either refused with a located diagnostic or plays clean. The
    forbidden outcome is the middle one this whole change exists to remove:
    accepted by `check_dsl`, then dead at declare time.

    A refusal may come from any wall a default passes through — this grid asserts
    the kind is ACCOUNTED FOR, not that this file's wall is the one that fires.
    `StrLit`, `ListLit` and `AllPlayers` on an `Integer` var are refused by the
    type wall (`test_state_default_type.py`), which is where the `AllPlayers` row
    that was once this grid's lone residual is now closed.

    red under: delete any arm of `_check_state_default_scope` (the Call/Choose
    rows redden); the type-wall rows have their own red-under in their file."""
    type_name, default, tail = _EXPR_CELLS[kind]
    source = f"""
game Probe {{
  players: 2
  cards: standard52
  max_length: 100
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0
           first : Integer = 1
           probe_var : {type_name} = {default} }}
  phase play {{ }}
  winner: highest score
}}
{tail}"""
    if kind in _EXPR_REFUSED:
        with pytest.raises(DiagnosticError) as exc:
            check_dsl(source, "expr.cardlang")
        assert exc.value.diagnostic.span is not None
        assert _EXPR_REFUSED[kind] in exc.value.diagnostic.message
        return
    play_game(check_dsl(source, "expr.cardlang"), random.Random(0))


def test_a_struct_default_is_not_an_indirect_channel() -> None:
    """A `derived { }` body reads its state lazily, on access, so a struct
    default whose derived field names a LATER variable is sound — the third
    channel this grid would otherwise need. Pinned because it is a property of
    the evaluator, not of the grammar: if `derived` ever became eager this goes
    red, which is the signal to widen the indirect arm.

    red under: make `evaluate` force derived fields at construction."""
    source = """
game Probe {
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  b : T = T { x: 1 }  a : Integer = 7 }
  phase play { }
  winner: highest score
}
type T = { x : Integer } derived { y = a }
"""
    play_game(check_dsl(source, "struct.cardlang"), random.Random(0))
