"""Misuse probes for the `uses` family-library tier, plus its completeness pin.

The surface-totality artifact for the import tier (CLAUDE.md, decisions.md
"Surface totality" / "Closed-domain completeness"). Every wall `_apply_uses`
raises is probed here with the most plausible WRONG sentence for it, and each is
proven loud in the layer whose currency it belongs to — resolve's diagnostic bag,
carrying the game's own `uses` span, never a stray name error from inside library
text the author did not write.

Completeness ledger
-------------------
property: every way a `uses` line can be wrong is rejected, loudly, at resolve.
domain:   the import tier's error space, which is the product of two closed sets
          — the failure modes of a `uses` line (unknown library, repeated import)
          and, for each definition kind in `resolve._LIBRARY_DEF_KINDS`, the
          three-way collision matrix (game/library, library/library,
          library/stdlib) — plus the three ways a `requires` entry can go unmet
          (absent, wrong type, wrong index).
registry: the DEFINITION-KIND axis from `resolve._LIBRARY_DEF_KINDS`, pinned to
          `n.Library`'s own fields by `test_def_kinds_covers_every_library_field`;
          the COLLISION-SOURCE axis from the three namespaces a library name can
          land in — the game (`n.Game`'s same-named fields), another library, and
          the stdlib registries (`library_rules()`, `STDLIB_CALL_FUNCS`,
          `LIBRARY_MOVE_TYPES`), read through `_stdlib_member`. Every axis is
          computed, never spelled: the probe NAMES come out of the registries
          too, which is the fix for how this file's first stdlib move-type cell
          shipped vacuous (it probed `play_card`, which `stdlib/moves.py`
          documents as game-defined, so no edit could redden it).
covered:  the grid — definition kind x collision source, all 18 cells executed:
          `test_game_local_definition_may_not_shadow_a_library_one` (6),
          `test_two_libraries_may_not_define_the_same_name` (6), and
          `test_library_definition_against_the_stdlib_namespace` (6, of which
          the 3 kinds with no stdlib registry skip with that reason named).
          Every cell's expected outcome is a commanded decision: the stdlib row
          is `_STDLIB_REJECTS`, where `False` is as deliberate as `True`.
          Born-green cells carry their reddening edit as `red under:` in the
          test docstring; the move-type accept was demonstrated red by extending
          `_check_library_collisions`'s stdlib leg to move_types.
sampled:  the `uses`-line failure modes (unknown library, repeated import) and
          the three `requires` mismatch modes are one probe each, not a crossed
          product — each is a single-axis error with no second axis to cross.
residual: none of the grid. The stdlib row's three accepting cells are decisions,
          not gaps: stdlib move types and a game's `move_type` definitions are
          disjoint consult paths that never share a namespace
          (`cardlang/stdlib/moves.py`), and types/defines/procedures have no
          stdlib registry at all. `test_the_accepting_move_type_cell_has_real_
          corpus_dependents` keeps the first decision honest by DERIVING its
          dependent games from the corpus — the hand-written version of that
          list named four games of which three were wrong, and named Stud, which
          the same change that wrote it had just made wrong.

One deliberate NON-error, recorded here so a later reader does not mistake its
absence from the probes for an omission: an imported definition a game never
uses is legal (decisions.md "Family libraries", the subset-vocabulary
paragraph). Kuhn imports `raise` and never offers it. That is the tier working
as designed — `uses` names a family, not a manifest — and its cost at the
OpenSpiel target is pinned to zero in
`tests/openspiel_ready/test_kuhn_poker.py`, not here: the claim is about the
action-space derivation, so it belongs in the currency of the adapter.
"""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
from typing import Iterator

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.libraries import library_names, load_library
from cardlang.parse import parse_library, parse_text
from cardlang.resolve import _LIBRARY_DEF_KINDS, resolve
from cardlang.stdlib.functions import STDLIB_CALL_FUNCS
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import library_rules

# A minimal game that satisfies `poker_betting`'s whole `requires` contract. Every
# probe below is this game plus exactly one thing wrong, so a failure names the
# wall under test and nothing else.
_GAME = """
game Probe {{
  uses poker_betting
  players: 2
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 2
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    acted[player]     : Boolean = false
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    limit             : Integer = 1
    raise_cap         : Integer = 2
{extra_state}  }}
  phase play {{ }}
  winner: highest stack
}}
{extra}
"""


def _game(*, extra: str = "", extra_state: str = "", uses: str = "uses poker_betting") -> n.Game:
    text = _GAME.format(extra=extra, extra_state=extra_state)
    text = text.replace("uses poker_betting", uses, 1)
    return parse_text(text, "probe.cardlang")


def _rejects(game: n.Game, *needles: str) -> None:
    """Resolve `game`, require it to fail, and require the message to say the
    thing the wall exists to say — not merely to fail somehow."""
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = str(exc.value)
    for needle in needles:
        assert needle in message, f"expected {needle!r} in:\n{message}"


def test_the_probe_game_is_otherwise_valid() -> None:
    """The control. Without it every probe below could be passing for the wrong
    reason — a vacuously-green suite is the defect class this file guards."""
    resolve(_game())


# --- the `uses` line itself ---------------------------------------------------


def test_unknown_library_is_rejected() -> None:
    _rejects(
        _game(uses="uses porker_betting"),
        "unknown library 'porker_betting'",
        "poker_betting",  # the message lists what IS available
    )


def test_repeated_uses_of_one_library_is_rejected() -> None:
    _rejects(
        _game(uses="uses poker_betting\n  uses poker_betting"),
        "already uses library 'poker_betting'",
    )


# --- the three-way collision matrix, swept over every definition kind ---------

# One minimally-valid source text per definition kind, named `collide`. The keys
# are checked against `_LIBRARY_DEF_KINDS` by the pin below, so a new kind cannot
# be added without a probe for it.
_DEF_SOURCE: dict[str, str] = {
    "rules": "rule collide { }",
    "move_types": "move_type collide { effect { } }",
    "types": "type collide = { x : Integer }",
    "defines": "define collide -> { a | b } { }",
    "functions": "function collide() = 1",
    "procedures": "procedure collide() { }",
}


def test_def_kinds_covers_every_library_field() -> None:
    """`_LIBRARY_DEF_KINDS` is the closed domain the collision walls sweep, so it
    must equal `n.Library`'s definition fields exactly. A seventh form added to
    the node without an entry there would ship unwalled; this is the static
    failure that prevents it.

    red under: add a field to `n.Library` without adding it to
    `_LIBRARY_DEF_KINDS`."""
    node_fields = {f.name for f in fields(n.Library)} - {"name", "requires", "span"}
    assert {field for field, _ in _LIBRARY_DEF_KINDS} == node_fields
    assert set(_DEF_SOURCE) == node_fields, (
        "every definition kind needs a collision probe below"
    )


def _kinds() -> Iterator[tuple[str, str]]:
    return iter(_LIBRARY_DEF_KINDS)


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_game_local_definition_may_not_shadow_a_library_one(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uses` imports, it does not inherit — so a game-local definition under an
    imported name is an error, not an override. This is the wall that keeps the
    tier composition rather than inheritance (decisions.md "Family libraries").

    red under: delete the `if definition.name in local` arm of
    `_check_library_collisions`."""
    library = parse_library(
        f"library probe_lib {{ {_DEF_SOURCE[field]} }}", "probe_lib.cardlang"
    )
    _patch_libraries(monkeypatch, {"probe_lib": library})
    _rejects(
        _game(uses="uses probe_lib", extra=_DEF_SOURCE[field]),
        f"{noun} 'collide' is defined by this game and also by library 'probe_lib'",
        "it does not inherit",
    )


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_two_libraries_may_not_define_the_same_name(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolution is flat, so neither library wins — silently picking one would
    make a game's meaning depend on `uses` order.

    red under: delete the `elif definition.name in from_libraries` arm of
    `_check_library_collisions`."""
    source = _DEF_SOURCE[field]
    _patch_libraries(
        monkeypatch,
        {
            "lib_a": parse_library(f"library lib_a {{ {source} }}", "lib_a.cardlang"),
            "lib_b": parse_library(f"library lib_b {{ {source} }}", "lib_b.cardlang"),
        },
    )
    _rejects(
        _game(uses="uses lib_a\n  uses lib_b"),
        f"{noun} 'collide' is defined by both library 'lib_a' and library 'lib_b'",
    )


def _stdlib_member(field: str) -> str | None:
    """A real member of the stdlib registry that shares a namespace with this
    definition kind, drawn FROM the registry, or None when no stdlib registry
    exists for the kind. Derived rather than spelled: a hand-written probe name
    can silently not be a member of the registry it claims to probe, which is
    exactly how this file's first stdlib-move-type cell shipped vacuous (it
    probed `play_card`, which `stdlib/moves.py` documents as game-defined)."""
    registry: dict[str, frozenset[str] | set[str]] = {
        "rules": frozenset(library_rules()),
        "functions": frozenset(STDLIB_CALL_FUNCS),
        "move_types": frozenset(LIBRARY_MOVE_TYPES),
    }
    members = registry.get(field)
    return min(members) if members else None


# The stdlib leg of the collision grid: for each definition kind, whether a
# library defining something under a REAL stdlib name of that kind is rejected.
# `False` is as much a commanded decision as `True` — move_types are a
# deliberate non-collision (two disjoint consult paths), and the three kinds
# with no stdlib registry cannot collide at all.
_STDLIB_REJECTS: dict[str, bool] = {
    "rules": True,
    "functions": True,
    "move_types": False,
    "types": False,
    "defines": False,
    "procedures": False,
}


def test_stdlib_grid_covers_every_definition_kind() -> None:
    """Both axes of the stdlib leg are derived, so the grid below cannot silently
    stop covering a kind.

    red under: drop any key from `_STDLIB_REJECTS`."""
    assert set(_STDLIB_REJECTS) == {field for field, _ in _LIBRARY_DEF_KINDS}
    # A kind commanded to reject must have a registry to collide with, and a
    # kind commanded to accept because no registry exists must really have none.
    assert {f for f in _STDLIB_REJECTS if _stdlib_member(f)} == {
        "rules",
        "functions",
        "move_types",
    }


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_library_definition_against_the_stdlib_namespace(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stdlib row of the collision grid, run for every definition kind rather
    than written out for the two that reject.

    The accepting cells are the load-bearing ones. Stdlib move types and a game's
    `move_type` definitions are disjoint consult paths that never share a
    namespace, so a library defining one under a stdlib name must NOT be an
    error: six corpus games depend on that (see `_stdlib_move_type_games`).

    red under: extend `_check_library_collisions`'s stdlib leg to move_types, or
    delete its `library_rules()` leg."""
    name = _stdlib_member(field)
    if name is None:
        pytest.skip(f"no stdlib registry shares a namespace with {noun}s")
    source = _DEF_SOURCE[field].replace("collide", name)
    _patch_libraries(
        monkeypatch,
        {"probe_lib": parse_library(f"library probe_lib {{ {source} }}", "pl.cardlang")},
    )
    game = _game(uses="uses probe_lib")
    if _STDLIB_REJECTS[field]:
        _rejects(game, f"library 'probe_lib' defines {noun} '{name}'", "shadows the")
    else:
        resolve(game)


def _stdlib_move_type_games() -> list[str]:
    """Corpus games that define a `move_type` under a stdlib move-type name — the
    games the accepting move_types cell above protects. Derived from the corpus,
    because the hand-written version of this list named four games of which three
    were wrong, and one (Stud) was made wrong by the very change that wrote it."""
    games_dir = Path(__file__).resolve().parent.parent / "docs" / "games"
    hits = []
    for path in sorted(games_dir.glob("*.cardlang")):
        game = parse_text(path.read_text(), path.name)
        if {m.name for m in game.move_types} & set(LIBRARY_MOVE_TYPES):
            hits.append(path.stem)
    return hits


def test_the_accepting_move_type_cell_has_real_corpus_dependents() -> None:
    """The accepting cell is only a design decision if something depends on it;
    otherwise it is an untested branch wearing a decision's name.

    red under: add the stdlib move-type leg to `_check_library_collisions` — every
    game below then fails to resolve."""
    dependents = _stdlib_move_type_games()
    assert len(dependents) >= 3, (
        f"only {dependents} still define a move type under a stdlib name; if this "
        f"reaches zero the non-collision is no longer load-bearing and the "
        f"residual ledger row should be revisited rather than left standing"
    )


# --- the `requires` contract --------------------------------------------------


def test_unmet_requirement_is_reported_on_the_uses_line() -> None:
    """The diagnostics-currency requirement: the author wrote `uses`, so that is
    where the failure lands — not as an undeclared `raise_cap` deep inside
    library text they never typed."""
    game = _game()
    stripped = replace(
        game,
        state=replace(
            game.state,
            decls=tuple(d for d in game.state.decls if d.name != "raise_cap"),
        ),
    ) if game.state else game
    _rejects(
        stripped,
        "library 'poker_betting' requires state `raise_cap : Integer`",
        "does not declare",
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(stripped)
    assert "probe.cardlang:3:" in str(exc.value), (
        "the requires failure must carry the `uses` line's span"
    )


def test_requirement_declared_at_the_wrong_type_is_rejected() -> None:
    _rejects(
        _mistyped("raise_cap", type_name="Boolean", default="false"),
        "library 'poker_betting' requires state `raise_cap : Integer`",
        "declares it as `Boolean`",
    )


def test_requirement_declared_with_the_wrong_arity_is_rejected() -> None:
    """Per-player where the library wants a scalar. Silently accepting this would
    make every library read of `raise_cap` a subscript-less read of a family."""
    _rejects(
        _mistyped("raise_cap", index="player"),
        "requires state `raise_cap : Integer` to be a scalar",
        "declares it as per-player",
    )


def _mistyped(
    name: str,
    *,
    type_name: str = "Integer",
    index: str | None = None,
    default: str = "2",
) -> n.Game:
    game = _game()
    assert game.state is not None
    decls = tuple(
        replace(d, type_name=type_name, index=index, default=parse_default(default))
        if d.name == name
        else d
        for d in game.state.decls
    )
    return replace(game, state=replace(game.state, decls=decls))


def parse_default(literal: str) -> n.Expr:
    """The default expression for a rewritten state decl, taken from a real parse
    so the probe never hand-builds an expression shape the parser would not."""
    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 zones {{ deck : Deck }} "
        f"state {{ x : Integer = {literal} }} }}",
        "default.cardlang",
    )
    assert game.state is not None
    return game.state.decls[0].default


def _patch_libraries(
    monkeypatch: pytest.MonkeyPatch, libraries: dict[str, n.Library]
) -> None:
    """Point resolve at synthetic libraries. Probing collisions against the real
    corpus library would mean adding deliberately-broken files to docs/libraries/,
    where they would be indistinguishable from real family libraries."""
    monkeypatch.setattr(
        "cardlang.resolve.library_names", lambda: frozenset(libraries)
    )
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: libraries[name])


# --- the real corpus library --------------------------------------------------


def test_poker_betting_declares_only_state_it_uses() -> None:
    """A `requires` entry nothing in the library reads is dead contract: it would
    force every consumer to declare state for no reason. Derived from the library
    text rather than a hand-listed set."""
    library = load_library("poker_betting")
    text = (
        "docs/libraries/poker_betting.cardlang"
    )
    from pathlib import Path

    body = Path(text).read_text().split("requires {", 1)[1].split("}", 1)[1]
    for require in library.requires:
        assert require.name in body, (
            f"`requires` declares {require.name!r}, which no definition in "
            f"{text} reads — drop it from the contract"
        )


def test_poker_betting_is_registered() -> None:
    assert "poker_betting" in library_names()
