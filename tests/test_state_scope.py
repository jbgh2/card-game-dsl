"""State scoping is lexical, and the checker enforces it — completeness ledger.

decisions.md "State scoping (lexical)" settles the rule: a variable is scoped to
the phase that lexically encloses its declaration, reads from enclosing scopes
are free, and "**Writes follow the same rule.** A phase may write to a variable
declared in its enclosing scope… A phase may *not* write to a variable declared
in a sibling or descendant scope, because that variable's owning phase may not
be active. **This is statically checkable.**"

It was not statically checked. Every out-of-scope reference — read or write,
sibling or descendant — passed the whole front end and died at playout on
`KeyError: variable '…' not in scope` out of `runtime/state.py`: no span, no
mention of the scope rule, no fix in the text. Only the `state { }` DEFAULT
subclass was guarded (`resolve._check_state_default_scope`), and this module
generalises that traversal to every reference position inside a phase, plus the
game-level `winner:` clause, which has no enclosing phase at all.

Contract
--------
Assumes: resolve has classified names (`NameRef.ref_kind == "state_var"`).
Establishes: a state reference names a variable live at its position.
Illegal after this: reaching `RuntimeState._frame_of` with an out-of-scope name
from a lexical position — after this guard that `KeyError` is reachable only
through the primitive-read path, where `runtime/reads.py` converts it.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:   a state reference resolves against the frames live at its lexical
            position — the declaring phase must enclose, or be, the phase the
            reference sits in — and a game-level clause sees game-level state
            only.
domain:     declaration site x reference site x reference kind. Declaration and
            reference sites range over a fixed phase tree (`_TREE`); the
            ancestry relation between them is COMPUTED from that tree, so the
            expected column follows from the rule rather than being hand-copied
            per cell — a cell cannot be quietly authored to match whatever the
            implementation does.
registry:   `_TREE` (the phase shapes, and `_ancestors` derived from it) and
            `_KINDS` (the reference kinds). `_KINDS` is enumerated, not derived:
            the reference positions come from the grammar productions that hold
            a state name, and the four here are the distinct AST SHAPES among
            them — an expression read (`NameRef`), an assignment target
            (`AssignStmt.target`, a `NameRef`), a `rotate` target
            (`RotateStmt.target`, a `NameRef`), and `winner:` (`Winner.target`,
            a bare `str` with no `ref_kind` at all). Every other position in the
            grammar reaches the checker as one of the first two shapes.
covered:    `test_scope_grid` — the full cross product of `_TREE` sites x
            `_KINDS`, expected computed by `_in_scope`; plus
            `test_winner_target_scope` and `test_loser_selection_scope`, the
            two game-level clauses, and `test_every_game_field_is_decided`,
            which pins the guard's game-level skip set against `Game`'s real
            field set so a field added later forces a decision.
            The game-level half of the guard is DERIVED — it walks every
            `Game` field but the skipped ones — after review found `loser:`
            missing from a hand-enumerated list. The enumeration was the
            defect; the pin above is what keeps the derivation honest.
sampled:    the many expression positions that all reduce to shape 1 (a
            `NameRef` read) are covered by one representative each, not one per
            grammar production: the check walks the resolved AST, so a read
            inside `if`, inside a comprehension filter and inside a round's
            `until` are the same node reaching the same code path. A position
            that did NOT reduce to one of the four shapes would be a residual,
            and `_KINDS`' derivation note above is what makes that visible.
residual:   callable bodies — move types, rules, functions, procedures, defines
            — are OUT of this domain and stay unchecked. A `derived { }` body
            has the same shape (lazily evaluated at member access, so no single
            lexical phase) but is NOT residual: no corpus game declares one, so
            the conservative rule unavailable for the others is free here and
            a derived body may read game-level state only. Their legality depends
            on which phase invokes them, not on where they are written, so it is
            a reachability analysis rather than a traversal; 112 callable bodies
            across 15 corpus games legitimately reference phase-scoped state, so
            no conservative rule is available. Guarded by nothing here, recorded
            as issue #242 (R2). `Turns.again` and `RequireDecl.name` are bare
            `str` names this check cannot see for the same reason `winner:`
            needed special handling — issue #243 (R3).

red under: the grid was authored and run RED before the guard existed — 18 of
its 40 cells failed (the 15 out-of-scope grid cells plus the 3 out-of-scope
`winner:` cells), and all 21 in-scope cells passed even then, so the red was
the designed red and not a broken fixture. Re-verify by deleting the
`_check_state_scope(game, bag)` call in `resolve.resolve`. Verified by doing
so.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

# The phase tree every cell is built from: two top-level phases, one with a
# nested child. That is the smallest shape containing all four relationships a
# reference can have to a declaration — same, ancestor, descendant, sibling.
_TREE: dict[str, list[str]] = {"a": ["a_inner"], "b": []}

# `None` is the game level: not a phase, encloses everything.
_SITES: list[str | None] = [None, "a", "a_inner", "b"]


def _ancestors(phase: str) -> list[str]:
    """The enclosing phases of `phase`, outermost last. Computed from `_TREE`."""
    for parent, children in _TREE.items():
        if phase in children:
            return [parent, *_ancestors(parent)]
    return []


def _in_scope(decl: str | None, ref: str) -> bool:
    """decisions.md's rule, stated once: a declaration is visible where the
    declaring scope encloses, or is, the referencing phase."""
    if decl is None:
        return True  # game level encloses every phase
    return decl == ref or decl in _ancestors(ref)


# The distinct AST shapes a state name reaches the checker as. See the ledger's
# `registry` row for why these four and not one per grammar production.
_KINDS = ["read", "write", "rotate"]


def _game(decl: str | None, ref: str | None, kind: str) -> str:
    """A complete game declaring `v` at `decl` and referencing it at `ref`."""
    decls = {s: "" for s in _SITES}
    if kind == "rotate":
        decl_text = "v : SeatDirection = hold"
        use = "rotate v through [left, right, across, hold]"
    else:
        decl_text = "v : Integer = 0"
        use = "score[0] := v" if kind == "read" else "v := 1"
    if decl is not None:
        decls[decl] = f"state {{ {decl_text} }}"

    bodies = {s: "" for s in _SITES}
    if ref is not None:
        bodies[ref] = use

    # A game declares exactly ONE game-level `state { }` block, so the
    # game-level cell merges `v` into it rather than emitting a second.
    game_state = "score[player] : Integer = 0"
    if decl is None:
        game_state += f"  {decl_text}"

    a_inner = f"phase a_inner {{ {decls['a_inner']} {bodies['a_inner']} }}"
    return f"""
game G {{
  players: 2
  max_length: 200
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {game_state} }}
  phase a {{ {decls['a']} {bodies['a']} {a_inner} }}
  phase b {{ {decls['b']} {bodies['b']} }}
  winner: highest score
}}
"""


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("ref", [s for s in _SITES if s is not None])
@pytest.mark.parametrize("decl", _SITES)
def test_scope_grid(decl: str | None, ref: str, kind: str) -> None:
    """Every (declaration site, reference site, shape) cell.

    The expected value is COMPUTED by `_in_scope` from `_TREE`, so a cell that
    flips is a change against decisions.md's rule, not against this file.
    """
    src = _game(decl, ref, kind)
    expected_ok = _in_scope(decl, ref)
    if expected_ok:
        check_dsl(src, "t.cardlang")  # must not raise
        return
    with pytest.raises(DiagnosticError) as caught:
        check_dsl(src, "t.cardlang")
    # The diagnostic must name the variable and say where it IS declared —
    # "not in scope" alone sends the author looking in the wrong place.
    message = str(caught.value)
    assert "'v'" in message, message
    assert str(decl) in message, (
        f"the diagnostic must name the declaring scope ({decl}) so the author "
        f"knows where the variable actually lives: {message}"
    )
    # The declaring-scope LIST must not repeat one phase. The scope set and
    # the declaration record are built by separate traversals; when one of them
    # also did the other's job every name was recorded once per traversal and
    # the message read "declared in phase 'a' or phase 'a'".
    assert f"phase '{decl}' or phase '{decl}'" not in message, message


@pytest.mark.parametrize("decl", _SITES)
def test_winner_target_scope(decl: str | None) -> None:
    """`winner: <dir> NAME` is evaluated at game end, outside every phase.

    Its own cell because `Winner.target` is a bare `str` (issue #243) — it never
    becomes a `NameRef`, so it is invisible to the walk that covers every other
    position and needs naming directly.
    """
    src = f"""
game G {{
  players: 2
  max_length: 200
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  {"state { tally[player] : Integer = 0 }" if decl is None else ""}
  phase a {{ {"state { tally[player] : Integer = 0 }" if decl == "a" else ""}
    phase a_inner {{ {"state { tally[player] : Integer = 0 }" if decl == "a_inner" else ""} }}
  }}
  phase b {{ {"state { tally[player] : Integer = 0 }" if decl == "b" else ""} }}
  winner: highest tally
}}
"""
    if decl is None:
        check_dsl(src, "t.cardlang")
        return
    with pytest.raises(DiagnosticError, match="tally"):
        check_dsl(src, "t.cardlang")


@pytest.mark.parametrize("decl", _SITES)
def test_loser_selection_scope(decl: str | None) -> None:
    """`loser: <expr>` is the second game-level clause, and the one review
    caught missing.

    It runs only when a game declares no `winner:` (`runtime/driver.py`
    evaluates it on the winner-is-None branch), which is why a fixture carrying
    both clauses does NOT reproduce the defect — the winner branch is taken and
    the loser expression is never evaluated. Stated because it cost a wrong
    "cannot reproduce" before the real witness was built.
    """
    src = f"""
game G {{
  players: 2
  max_length: 200
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  {"state { out : Player = 0 }" if decl is None else ""}
  phase a {{ {"state { out : Player = 0 }" if decl == "a" else ""}
    phase a_inner {{ {"state { out : Player = 0 }" if decl == "a_inner" else ""} }}
  }}
  phase b {{ {"state { out : Player = 0 }" if decl == "b" else ""} }}
  loser: out
}}
"""
    if decl is None:
        check_dsl(src, "t.cardlang")
        return
    with pytest.raises(DiagnosticError, match="out"):
        check_dsl(src, "t.cardlang")


def test_every_game_field_is_decided() -> None:
    """The game-level walk is derived, and its skip set is total over `Game`.

    Two sets, not one, because the reasons are not interchangeable: a field
    another guard checks is covered, a field nobody checks is a residual. They
    were one set once, `types` sat in it under the residual comment while the
    name claimed ownership, and nothing checked derived bodies at all.

    red under: add a name to either set that `Game` does not declare, or remove
    `phases` from the owned set. Verified.
    """
    from cardlang.ast import nodes as n
    from cardlang.resolve import (
        _GAME_LEVEL_OWNED_BY_ANOTHER_GUARD,
        _GAME_LEVEL_SKIP,
        _GAME_LEVEL_UNCHECKED,
    )

    fields = set(n.Game.__dataclass_fields__)
    unknown = _GAME_LEVEL_SKIP - fields
    assert not unknown, (
        f"the skip sets name {sorted(unknown)}, which `Game` does not declare — "
        f"a renamed field silently stops being skipped, or was never a field"
    )
    assert not (_GAME_LEVEL_OWNED_BY_ANOTHER_GUARD & _GAME_LEVEL_UNCHECKED), (
        "a field cannot be both checked by another guard and unchecked"
    )
    # Naming the walked half means a NEW `Game` field shows up in this diff as
    # a decision rather than joining whichever side it happens to land on.
    walked = sorted(fields - _GAME_LEVEL_SKIP)
    assert walked == [
        # `card_points` holds rank strings and integer literals only — no
        # expression, so no state reference to find; walked (the conservative
        # side) rather than skipped.
        "board", "card_points", "content_flavor", "deck", "direction", "loser",
        "max_length",
        "name", "players", "positions", "ranking", "ranking_convention", "span",
        "teams", "trump", "types", "uses", "winner", "zones",
    ], (
        f"`Game` gained or lost a field: {walked}. Decide whether a state "
        f"reference in it runs inside a phase (skip it, and say which set) or "
        f"at game level (leave it walked), then update this list."
    )


def test_the_game_level_walk_is_not_vacuous() -> None:
    """The walk must actually visit the tuple-valued fields.

    `resolve._walk` returns immediately on anything that is not a dataclass,
    and most walked `Game` fields hold a TUPLE of nodes — so walking them with
    `_walk` visits nothing while the loop reads as total. That shipped once and
    was caught only because a reviewer asked about one specific field.

    This pins the property directly: a state reference inside a tuple-valued
    field (`types`) must be found. A grid cell would not have caught it —
    every out-of-scope cell it covers lives in a single-node field.

    red under: change `_child_nodes` back to `_walk` in the game-level loop of
    `_check_state_scope`. Verified.
    """
    src = """
game G {
  players: 2
  max_length: 200
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { box : T = T { x: 1 } }
  phase p { state { phase_var : Player = 0 } }
  loser: box.y
}
type T = { x : Integer } derived { y = phase_var }
"""
    with pytest.raises(DiagnosticError, match="phase_var"):
        check_dsl(src, "t.cardlang")
