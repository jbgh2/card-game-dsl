"""A state variable's default must be assignable to the variable's declared
type. `v : Integer = "s"` had parsed, resolved, and run — the declared
`type_name` reached the checker only as the variable's type for later reads, and
the default expression was never compared against it.

Found by the surface-totality audit of the declare-time scope wall
(`test_state_default_scope.py`), recorded as that grid's one residual (the
`AllPlayers` row: `v : Integer = all players` was accepted), and closed here.
The check mirrors `_check_assign`: `infer(default)` must be `assignable` to
`type_from_name(decl.type_name, decl.optional)` — the value type, which is the
element type an indexed default broadcasts to every key.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `state { }` default that `check_dsl` accepts has a type
            assignable to its variable's declared type. Refused cells are
            refused with a located diagnostic naming the variable.
domain:     declared value type x inferred default type. The declared axis is
            `KNOWN_TYPE_NAMES` (scalars + enums) crossed with {plain, optional,
            indexed} plus struct types; the default axis is the `n.Expr` union's
            inferred types. The verdict for a cell is `coercible(default,
            declared)` — the same relation the wall uses, computed
            independently in the breadth sweep so the test drives the real
            pipeline against an expected column it did not scrape from the wall.
covered:    the concrete cells below (hand-decided outcomes for the behaviours
            that matter — primitive mismatch, the `all players` residual,
            optional/non-optional `none`, indexed element-checking, struct
            fit), executed at BOTH default sites (game-level and nested-phase);
            plus the derived breadth sweep over the declared x default cross.
residual:   PRECISION, stated like the `Call` ban's: the wall is exactly as
            sharp as `infer`, which returns `TAny` (the permissive top) for its
            unrefined arms, so a default whose inferred type is `TAny` passes
            whatever the declared type. This is the type system's design, not a
            hole in the wall — `assignable` treats `TAny` as compatible
            everywhere. No corpus default is `TAny`-typed (all 268 are precise),
            so nothing rides on the boundary today; it moves as `infer` gains
            precision, never needing a change here.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.typecheck import env_from_game, infer, type_from_name
from cardlang.types import coercible


def _game(state_decls: str, tail: str = "", *, deck: str = "standard52") -> str:
    # 8 seats so the breadth sweep's fixed integer default (`7`) is a VALID seat
    # for a `Player`-typed cell: this test isolates ASSIGNABILITY, and the
    # operand choke point additionally range-checks a Player/Team literal (that
    # wall is `tests/test_player_literal_range.py`). Keeping 7 in range makes the
    # range check a no-op here, so `assignable` stays the sweep's complete model.
    return f"""
game Probe {{
  players: 8
  cards: {deck}
  max_length: 100
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  {state_decls} }}
  phase play {{ }}
  winner: highest score
}}
{tail}
"""


# Each cell: (declaration text, ACCEPT?) — the outcome is a human judgement about
# what the language should do, not a value read back from the wall.
_CELLS: list[tuple[str, bool]] = [
    ("v : Integer = 7", True),
    ('v : Integer = "s"', False),  # StrLit into Integer
    ("v : Integer = false", False),  # Boolean into Integer
    ("v : Boolean = 7", False),  # Integer into Boolean
    ("v : Boolean = false", True),
    ("v : Integer = all players", False),  # the AllPlayers residual, now closed
    ("v : Suit? = none", True),  # none fits an optional
    ("v : Suit = none", False),  # none on a non-optional
    ("v : Card? = (Q of hearts)", True),
    ("v : Player = 0", True),  # an Integer stands for a 0-based Player seat
    ("v : Suit = hearts", True),  # an enum value of its own type
    ("v : Integer = 3 + 4", True),  # BinOp arithmetic is Integer
    ("v : Boolean = none is none", True),  # IsCheck is Boolean
    ("v[player] : Integer = false", False),  # indexed: default checked as element
    ("v[player] : Integer = 0", True),
]


@pytest.mark.parametrize(
    "decl,accept", _CELLS, ids=[c.replace(" ", "_") for c, _ in _CELLS]
)
def test_a_default_must_fit_its_declared_type(decl: str, accept: bool) -> None:
    """The concrete grid. Each accepted cell is PLAYED, not merely resolved, so
    an accept that would die at declare time is caught too.

    red under: delete the `assignable` check from `_check_state_default_type`
    (every REJECT cell goes green)."""
    source = _game(decl)
    if not accept:
        with pytest.raises(DiagnosticError) as exc:
            check_dsl(source, "type.cardlang")
        assert exc.value.diagnostic.span is not None, (
            "a type refusal must be located, not a bare error"
        )
        assert "v" in exc.value.diagnostic.message
        return
    play_game(check_dsl(source, "type.cardlang"), random.Random(0))


def test_the_grid_commands_both_outcomes() -> None:
    """A guard on the grid: if every cell expected the same verdict the sweep
    would prove nothing.

    red under: make every `_CELLS` entry the same boolean."""
    assert {accept for _, accept in _CELLS} == {True, False}


# The declared axis for the breadth sweep, as (declaration prefix, the value
# `type_from_name` builds it into). Derived so a cell's expected verdict is a
# real `assignable` call, not a second hand-list.
_DECLARED: list[tuple[str, str, bool]] = [
    ("w : Integer", "Integer", False),
    ("w : Boolean", "Boolean", False),
    ("w : Suit", "Suit", False),
    ("w : Suit?", "Suit", True),
    ("w : Player", "Player", False),
]
_DEFAULTS: list[str] = ["7", '"s"', "false", "none", "hearts", "all players"]


@pytest.mark.parametrize("default", _DEFAULTS)
@pytest.mark.parametrize("decl_prefix,type_name,optional", _DECLARED)
def test_breadth_sweep_matches_assignable(
    decl_prefix: str, type_name: str, optional: bool, default: str
) -> None:
    """The added-breadth cross. The expected column is `coercible(infer(default),
    type_from_name(...))` computed here against the real type machinery — NOT
    scraped from `check_dsl` or the new helper — so the test proves the default
    is actually routed through `assignable`, and a wiring bug (checking the
    wrong operand, or not at all) diverges from this expectation.

    red under: delete the `assignable` check from `_check_state_default_type`
    (the four rejecting cells stop rejecting)."""
    source = _game(f"{decl_prefix} = {default}")
    # Independently compute the expectation from the type machinery.
    probe_env = env_from_game(check_bare(source))
    declared = type_from_name(type_name, optional, probe_env.structs)
    got = infer(_default_expr(source), probe_env)
    expected_accept = coercible(got, declared)

    accepted = True
    try:
        check_dsl(source, "sweep.cardlang")
    except DiagnosticError:
        accepted = False
    verb = "accepted" if accepted else "rejected"
    assert accepted == expected_accept, (
        f"{decl_prefix} = {default}: pipeline {verb}, "
        f"coercible({got}, {declared}) = {expected_accept}"
    )


def check_bare(source: str):  # type: ignore[no-untyped-def]
    """Parse+resolve without typecheck, so a default that the wall would reject
    is still available to `infer` for the sweep's independent expectation."""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve

    return resolve(parse_text(source, "bare.cardlang"))


def _default_expr(source: str):  # type: ignore[no-untyped-def]
    game = check_bare(source)
    assert game.state is not None
    return game.state.decls[-1].default


def test_both_default_sites_are_wired() -> None:
    """A bad default is refused at the game-level block AND inside a nested
    phase, so neither of the two walk sites can silently go unchecked.

    red under: delete either `_check_state_default_type` call site."""
    game_level = """
game GameLevel {
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  bad : Integer = "s" }
  phase play { }
  winner: highest score
}
"""
    phase_level = """
game PhaseLevel {
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase outer {
    phase inner { state { bad : Boolean = 7 } }
  }
  winner: highest score
}
"""
    for source in (game_level, phase_level):
        with pytest.raises(DiagnosticError) as exc:
            check_dsl(source, "sites.cardlang")
        assert "bad" in exc.value.diagnostic.message
