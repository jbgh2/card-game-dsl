"""Misuse probes for the `uses` family-library tier, plus its completeness pin.

The surface-totality artifact for the import tier (CLAUDE.md, decisions.md
"Surface totality" / "Closed-domain completeness"). Every wall `_apply_uses`
raises is probed here with the most plausible WRONG sentence for it, and each is
proven loud in the layer whose currency it belongs to — resolve's diagnostic bag,
carrying the game's own `uses` span, never a stray name error from inside library
text the author did not write.

Completeness ledger
-------------------
property: a family-library file parses as the items its author wrote; its
          `requires` contract is SUFFICIENT, so a game meeting it in full is
          enough; and every way a `uses` line can be wrong is rejected, loudly,
          at resolve.
domain:   two layers. At PARSE, the library file's clause skeleton: the
          `?library_item` alternatives times {well-formed, truncated at their
          last required slot}, crossed with every alternative as the NEIGHBOUR
          written below — the cell that matters being a truncated item that
          completes itself from its neighbour and drops it. At RESOLVE, three
          products. (a) The library's ENCAPSULATION: each definition kind of
          `resolve._LIBRARY_DEF_KINDS` as the site a leak is written in, times
          the reference kinds a body can leak through (a state name, a function
          call). (b) The `requires` contract per name: how many declarations the
          game holds {0, 1, 2} times the shape of the last one {matching, and
          one row per field `_check_requires` compares}. (c) The import tier's
          error space — the failure modes of a `uses` line (unknown library,
          repeated import) times, for each definition kind, the three-way
          collision matrix (game/library, library/library, library/stdlib).
registry: the ITEM axis from the grammar's `?library_item`, scraped by
          `library_item_alternatives` (shared with tests/test_game_clause_walls,
          which owns the other half of the same absorption class and pins the
          `STRUCT_TYPE_NAME` terminal against both clause registries); the
          DEFINITION-KIND axis from `resolve._LIBRARY_DEF_KINDS`, pinned to
          `n.Library`'s own fields by `test_def_kinds_covers_every_library_field`
          and reused as the leak-site axis (`test_leak_sites_cover_every_
          definition_kind`); the SHAPE axis from `n.RequireDecl`'s own fields
          minus its key and span — the field set `_check_requires` compares —
          pinned by `test_shape_axis_covers_every_compared_field`, which is how
          the `optional` row came to exist;
          the COLLISION-SOURCE axis from the three namespaces a library name can
          land in — the game (`n.Game`'s same-named fields), another library, and
          the stdlib registries (`library_rules()`, `STDLIB_CALL_FUNCS`,
          `LIBRARY_MOVE_TYPES`), read through `_stdlib_member`. Every axis is
          computed, never spelled: the probe NAMES come out of the registries
          too, which is the fix for how this file's first stdlib move-type cell
          shipped vacuous (it probed `play_card`, which `stdlib/moves.py`
          documents as game-defined, so no edit could redden it).
covered:  the parse grid — item x neighbour, all 49 truncated cells executed by
          `test_a_truncated_library_item_may_not_absorb_its_neighbour`, all
          commanded REJECT, plus the 42 off-diagonal well-formed cells as its
          control; the diagonal's one real cell (a repeated `requires` block) is
          its own probe, the rest of the diagonal asserting nothing the
          off-diagonal does not. One truncated cell was open when this grid was
          written — `function_def` then `requires_block` — and its
          red-before-green transition is in this branch's history; the other 48
          are refused by brace structure rather than by the fix and are the
          sweep of the class. The builder's side of the same registry is
          `test_the_library_builder_files_every_item_kind` (7 cells, each item
          filed in its own `n.Library` field and no other) with
          `test_an_unhandled_library_item_is_loud` as the pin under it.
          The encapsulation grid — leak site x reference kind, all 12 cells
          executed by `test_a_library_may_not_reach_past_its_contract` and all
          commanded REJECT, each against a game that satisfies the contract AND
          happens to provide what the leak reaches for (without that second
          half the cells would be ordinary unresolved names and would prove
          nothing about the contract), each paired with a control twin in
          `test_the_same_site_reaching_only_its_contract_is_accepted` differing
          by one name. All 12 were open before the wall; the red-before-green
          transition is in this branch's history.
          The `requires` grid — multiplicity x shape, 9 cells executed by
          `test_a_requirement_is_answered_by_exactly_one_matching_declaration`,
          accepting in exactly one; the multiplicity-2 row was open and is the
          reason the grid exists. The three long-standing single-axis probes
          beside it stay, asserting the MESSAGES the grid only asserts the
          verdict of.
          The collision grid — definition kind x collision source, all 18 cells
          executed: `test_game_local_definition_may_not_shadow_a_library_one`
          (6), `test_two_libraries_may_not_define_the_same_name` (6), and
          `test_library_definition_against_the_stdlib_namespace` (6, of which
          the 3 kinds with no stdlib registry skip with that reason named).
          Every cell's expected outcome is a commanded decision: the stdlib row
          is `_STDLIB_REJECTS`, where `False` is as deliberate as `True`.
          Born-green cells carry their reddening edit as `red under:` in the
          test docstring; the move-type accept was demonstrated red by extending
          `_check_library_collisions`'s stdlib leg to move_types.
sampled:  the `uses`-line failure modes (unknown library, repeated import) are
          one probe each — a single-axis error with no second axis to cross.
          The truncation axis takes ONE truncation per item (its last required
          slot); an item can also be cut mid-slot, but every such cut is a
          strict prefix of this one and cannot absorb more.
residual: none of the collision grid. The stdlib row's three accepting cells are
          decisions, not gaps: stdlib move types and a game's `move_type`
          definitions are disjoint consult paths that never share a namespace
          (`cardlang/stdlib/moves.py`), and types/defines/procedures have no
          stdlib registry at all. `test_the_accepting_move_type_cell_has_real_
          corpus_dependents` keeps the first decision honest by DERIVING its
          dependent games from the corpus — the hand-written version of that
          list named four games of which three were wrong, and named Stud, which
          the same change that wrote it had just made wrong.

          TWO residuals outside it, both recorded in docs/roadmap.md, "Family
          libraries — unchecked residuals in the `requires` contract":

          1. REFERENCE KIND. The encapsulation grid's reference axis covers what
             a body READS — free names and calls, the two things classified
             against a namespace. It does not cover a DEFINITION name written
             into a fixed slot as a bare string: `constrains: <move_type>`,
             `run <procedure>()`, `produces <define>`, `offer [<move_types>]`.
             Those have no namespace registry to derive an axis from, so a
             hand-listed one would be complete only by luck. The wall bounding
             the residual is that the fully-undefined case IS rejected — resolve
             refuses a `constrains:` naming no move type anywhere — so what is
             unchecked is exactly the narrower case of a name only the importing
             game defines.
          2. SCOPE. The multiplicity grid proves a requirement is answered by
             exactly one declaration of the right shape; it does NOT prove that
             declaration is in scope where the library's definitions run. Moving
             Kuhn's `limit` into `phase deal` while the imported `bet` runs in
             `phase betting` passes resolve and typecheck and dies mid-playout
             on a bare KeyError. Deliberately not walled here: the root cause is
             the general cross-phase state-scope hole (a plain game with no
             library reproduces it), and the wall bounding it is that a
             requirement declared NOWHERE is rejected, so what is unchecked is a
             declaration that exists but cannot be reached. The grid does not
             claim this cell — `_check_requires`'s docstring says what is
             checked and what is not, so the claim and the check agree.

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
from lark import Tree
from lark.exceptions import VisitError

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.libraries import library_names, load_library
from cardlang.parse import _Builder, _transform, parse_library, parse_text, parse_to_tree
from cardlang.resolve import (
    _LIBRARY_DEF_KINDS,
    _PARAM_BEARING,
    _Categories,
    _library_reach,
    resolve,
)
from cardlang.stdlib.functions import STDLIB_CALL_FUNCS
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import library_rules
from tests.test_game_clause_walls import library_item_alternatives

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
  phase play {{ {phase_state} }}
  winner: highest stack
}}
{extra}
"""


def _game(
    *,
    extra: str = "",
    extra_state: str = "",
    phase_state: str = "",
    uses: str = "uses poker_betting",
) -> n.Game:
    text = _GAME.format(extra=extra, extra_state=extra_state, phase_state=phase_state)
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


# --- the library file's own clause skeleton (parse layer) ---------------------
#
# Before a `uses` line can be wrong, the library FILE has to parse as the items
# its author wrote. `?library_item*` is a sibling sequence with no separator, so
# an item whose last required slot is left empty can complete itself from the
# item written below it — silently, with no `_ambig` node, because only one
# derivation is complete and the ambiguity budget counts ambiguity, not loss.
# The grid below is that class: every alternative, well-formed and truncated,
# crossed with every alternative as its neighbour.

# One minimally-valid source line per `?library_item` alternative, and the same
# item truncated at its last required slot. Keyed by grammar rule name so both
# grids stay derived from the registry; pinned by `test_library_item_registry_pin`.
_ITEM_WELL_FORMED: dict[str, str] = {
    "requires_block": "requires { y : Integer }",
    "rule_def": "rule r { }",
    "move_type_def": "move_type m { effect { } }",
    "type_def": "type T = { x : Integer }",
    "define_def": "define d -> { a | b } { }",
    "function_def": "function f() = 1",
    "procedure_def": "procedure p() { }",
}

_ITEM_TRUNCATED: dict[str, str] = {
    "requires_block": "requires {",
    "rule_def": "rule r {",
    "move_type_def": "move_type m {",
    "type_def": "type T = {",
    "define_def": "define d ->",
    "function_def": "function f() =",
    "procedure_def": "procedure p() {",
}

# grammar rule name -> the `n.Library` field the builder must file the item
# under. The third derived column: `parse.library()` files each child by one
# dispatch over the item kinds, so a kind with no arm is a loud stop rather
# than a clause dropped without a word.
_ITEM_FIELD: dict[str, str] = {
    "requires_block": "requires",
    "rule_def": "rules",
    "move_type_def": "move_types",
    "type_def": "types",
    "define_def": "defines",
    "function_def": "functions",
    "procedure_def": "procedures",
}


def test_library_item_registry_pin() -> None:
    """All three tables above are keyed by grammar rule name and must cover
    `?library_item` exactly — an eighth alternative added to the grammar fails
    here until it is given a well-formed spelling, a truncated spelling, and the
    field it is filed under.

    red under: add an alternative to `?library_item` in cardlang.lark."""
    alternatives = library_item_alternatives()
    for what, table in (
        ("well-formed", _ITEM_WELL_FORMED),
        ("truncated", _ITEM_TRUNCATED),
        ("field", _ITEM_FIELD),
    ):
        assert set(table) == alternatives, (
            f"the {what} table does not cover `?library_item`: "
            f"{sorted(set(table) ^ alternatives)}"
        )
    assert set(_ITEM_FIELD.values()) == {f.name for f in fields(n.Library)} - {
        "name",
        "span",
    }, "every `n.Library` payload field must be the home of exactly one item kind"


def _neighbour_cells(*, truncated: bool) -> list[object]:
    """The grid: every `?library_item` alternative crossed with every other as
    its neighbour."""
    items = sorted(library_item_alternatives())
    cells: list[object] = []
    for item in items:
        for follower in items:
            if not truncated and item == follower:
                # A repeat of the single-valued `requires` block is its own
                # error, probed separately below; the rest of the diagonal
                # asserts nothing the off-diagonal cells do not.
                continue
            cells.append(pytest.param(item, follower, id=f"{item}-then-{follower}"))
    return cells


@pytest.mark.parametrize("item,follower", _neighbour_cells(truncated=True))
def test_a_truncated_library_item_may_not_absorb_its_neighbour(
    item: str, follower: str
) -> None:
    """An item missing its required slot is a syntax error, always — never an
    item completed from the one below it, which would drop that one silently.

    Asserted at the PARSE layer deliberately: the absorbed reading IS a
    well-formed parse, so letting a later stage reject it for some other reason
    (an unknown struct type, an unresolved name) would leave this cell green
    while the neighbouring item had vanished.

    One cell was open when this grid was written: a `function_def` truncated to
    `function f() =`, whose empty `expr` slot read the `requires { y : Integer }`
    below it as a `struct_lit` — `NAME "{" NAME ":" expr "}"` being exactly a
    single-entry brace clause — leaving the contract silently empty. The other
    48 are refused by brace structure rather than by the fix, and are the sweep
    of the class.

    red under: delete `requires` from STRUCT_TYPE_NAME's exclusion list in
    cardlang.lark."""
    src = f"library L {{\n  {_ITEM_TRUNCATED[item]}\n  {_ITEM_WELL_FORMED[follower]}\n}}"
    with pytest.raises(DiagnosticError) as exc:
        parse_library(src, "L.cardlang")
    assert exc.value.diagnostic.span is not None, (
        "a parse-layer refusal must be located, not a bare error"
    )


@pytest.mark.parametrize("item,follower", _neighbour_cells(truncated=False))
def test_two_well_formed_library_items_both_survive(item: str, follower: str) -> None:
    """The control for the grid above. Without it every truncated cell could be
    passing because the FOLLOWER cannot appear there at all, rather than because
    the truncation is refused.

    red under: delete any dispatch arm from `parse.library()`."""
    src = (
        f"library L {{\n  {_ITEM_WELL_FORMED[item]}\n  "
        f"{_ITEM_WELL_FORMED[follower]}\n}}"
    )
    library = parse_library(src, "L.cardlang")
    for name in (item, follower):
        assert getattr(library, _ITEM_FIELD[name]), (
            f"`{_ITEM_WELL_FORMED[name]}` did not reach `Library.{_ITEM_FIELD[name]}`"
        )


def test_a_repeated_requires_block_is_rejected() -> None:
    """The `requires` diagonal of the control grid: `requires` is the library's
    one single-valued item, so a second block is the same defect a repeated
    game clause is — keeping the last would discard the first."""
    with pytest.raises(DiagnosticError) as exc:
        parse_library(
            "library L { requires { a : Integer } requires { b : Integer } }",
            "L.cardlang",
        )
    assert "one `requires` block" in str(exc.value)


@pytest.mark.parametrize("item", sorted(library_item_alternatives()))
def test_the_library_builder_files_every_item_kind(item: str) -> None:
    """Every `?library_item` the grammar accepts reaches the field it belongs
    in, and no other. `parse.library()` dispatches each child once over the item
    kinds; the `else` arm under that dispatch is what stops a kind the grammar
    grows and the builder does not know from being dropped without a word.

    red under: point any dispatch arm in `parse.library()` at the wrong list —
    the row for that kind then finds its own field empty and another populated."""
    library = parse_library(f"library L {{ {_ITEM_WELL_FORMED[item]} }}", "L.cardlang")
    home = _ITEM_FIELD[item]
    assert getattr(library, home), f"`{_ITEM_WELL_FORMED[item]}` never reached `{home}`"
    elsewhere = [f for f in _ITEM_FIELD.values() if f != home and getattr(library, f)]
    assert not elsewhere, f"it also landed in {elsewhere}"


def test_an_unhandled_library_item_is_loud() -> None:
    """The pin for the filters above: an eighth `?library_item` alternative that
    no filter matches must stop the build, not vanish. Simulated the way the
    grammar would deliver it — Lark's `Transformer` leaves a rule it has no
    callback for as a bare `Tree`, which is what an unclassified alternative
    hands the builder.

    An `AssertionError`, not a `DiagnosticError`, and matching `game()`'s arm
    exactly: a grammar alternative with no builder arm is a defect in this
    package, not a sentence the designer got wrong, so it may not be reported in
    the author-facing diagnostic currency.

    red under: delete the `else: raise AssertionError` arm from
    `parse.library()`."""
    tree = parse_to_tree("library L { }", "L.cardlang", start="library")
    tree.children.append(Tree("an_eighth_library_item", []))
    # Lark wraps a builder-callback exception in `VisitError`, and `_transform`
    # unwraps only `DiagnosticError` — deliberately, since that is the
    # author-facing currency and this is not. `game()`'s arm surfaces the same
    # way, which is what "the equivalent arm" means here.
    with pytest.raises(VisitError) as exc:
        _transform(_Builder("L.cardlang", 0), tree)
    assert isinstance(exc.value.orig_exc, AssertionError)
    assert "unexpected library item" in str(exc.value.orig_exc)


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
#
# A requirement is answered by exactly ONE declaration of the right shape. Both
# halves of that are a grid: how MANY declarations of the name the game holds,
# and what SHAPE the declaration answering it has. The shape axis is derived —
# it is the field set `_check_requires` compares between a `RequireDecl` and the
# `StateDecl` that answers it, which is `n.RequireDecl`'s own fields minus the
# name it is keyed by and its span.

# One `state { }` line declaring `raise_cap` per shape: "matching" is what
# `poker_betting` asks for, and each other key breaks EXACTLY the field it names
# and nothing else. Pinned to `n.RequireDecl` by the test below.
_SHAPE_TEXT: dict[str, str] = {
    "matching": "raise_cap : Integer = 2",
    "type_name": "raise_cap : Boolean = false",
    "index": "raise_cap[player] : Integer = 2",
    "optional": "raise_cap : Integer? = none",
}


def test_shape_axis_covers_every_compared_field() -> None:
    """`_check_requires` compares a requirement against a declaration field by
    field, so the shape axis must be those fields exactly. A field added to
    `n.RequireDecl` — a new dimension the contract can disagree on — fails here
    until the grid gets a row that breaks it.

    red under: add a field to `n.RequireDecl` without adding a `_SHAPE_TEXT`
    row for it."""
    compared = {f.name for f in fields(n.RequireDecl)} - {"name", "span"}
    assert set(_SHAPE_TEXT) - {"matching"} == compared


def _requires_cells() -> list[object]:
    """Multiplicity x shape, where the shape is the LAST-written declaration's:
    at multiplicity 1 that is the only one, and at multiplicity 2 it is a
    phase-local one written under a game-level declaration left MATCHING. That
    asymmetry is the point — a second declaration whose shape is wrong is
    invisible to a first-wins contract precisely because the first one is
    right. Multiplicity 0 takes one cell, not four: with no declaration at all
    there is nothing for a shape to be wrong about."""
    cells: list[object] = [pytest.param(0, "matching", id="absent")]
    for shape in sorted(_SHAPE_TEXT):
        cells.append(pytest.param(1, shape, id=f"once-{shape}"))
        cells.append(pytest.param(2, shape, id=f"twice-{shape}"))
    return cells


@pytest.mark.parametrize("multiplicity,shape", _requires_cells())
def test_a_requirement_is_answered_by_exactly_one_matching_declaration(
    multiplicity: int, shape: str
) -> None:
    """The one accepting cell is (exactly one declaration, matching shape).

    The multiplicity-2 row is the reason this grid exists. `_check_requires`
    used to take the FIRST declaration it walked, while `typecheck` and
    `runtime/driver.py` both take the LAST — so a game declaring `raise_cap :
    Integer` at game level and `raise_cap : Boolean` in a phase passed this
    contract on the Integer and then bound the Boolean. Neither bias is the fix:
    the question is scoped, not flat — a shadow in the phase where the library
    runs makes last-wins right, a shadow in some other phase makes first-wins
    right — so the contract refuses to answer it at all. Cross-block shadowing
    stays legal in general (`_check_duplicate_names`); it is refused only for a
    `requires`d name, which is an interface rather than game-private state
    (decisions.md "Family libraries", the metamorphic-rename carve-out).

    red under: replace the multiplicity wall in `_check_requires` with either
    bias — `declared[want.name][0]` or `[-1]`."""
    game = _game(
        phase_state=f"state {{ {_SHAPE_TEXT[shape]} }}" if multiplicity == 2 else "",
    )
    if multiplicity == 0:
        assert game.state is not None
        game = replace(
            game,
            state=replace(
                game.state,
                decls=tuple(d for d in game.state.decls if d.name != "raise_cap"),
            ),
        )
    elif multiplicity == 1 and shape != "matching":
        game = _reshaped(game, shape)
    if (multiplicity, shape) == (1, "matching"):
        resolve(game)
        return
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    assert "probe.cardlang:3:" in str(exc.value), (
        "every requires failure lands on the `uses` line, in the game's currency"
    )


def _reshaped(game: n.Game, shape: str) -> n.Game:
    """Re-declare the game-level `raise_cap` with the shape's own text, through a
    real parse so the probe never hand-builds a declaration the parser would
    not."""
    assert game.state is not None
    replacement = _parse_state_decl(_SHAPE_TEXT[shape])
    decls = tuple(
        replace(replacement, span=d.span) if d.name == "raise_cap" else d
        for d in game.state.decls
    )
    return replace(game, state=replace(game.state, decls=decls))


def _parse_state_decl(text: str) -> n.StateDecl:
    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 zones {{ deck : Deck }} "
        f"state {{ {text} }} }}",
        "decl.cardlang",
    )
    assert game.state is not None
    return game.state.decls[0]


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


def test_a_requirement_declared_twice_says_so() -> None:
    """The message half of the multiplicity grid's rejecting row: it must name
    the count and the fix, not merely fail. A designer who shadowed on purpose
    has to be told that this particular name may not be shadowed."""
    _rejects(
        _game(phase_state="state { raise_cap : Integer = 2 }"),
        "requires state `raise_cap : Integer`, which game 'Probe' declares 2 times",
        "keep a single declaration of 'raise_cap'",
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


# --- the contract is SUFFICIENT, not merely advisory --------------------------
#
# `requires` is only a contract if a game that meets it in full is enough. That
# is a property of the LIBRARY, checked once against the library's own
# namespaces, not of any game that imports it: a leak reaching past the contract
# resolves fine against a game that happens to declare the extra name and fails
# against a game that satisfies the contract exactly — reported inside library
# text the author never wrote, which is the very currency failure the contract
# exists to prevent.
#
# The grid is definition kind x reference kind: WHERE the leak is written (the
# six kinds of `_LIBRARY_DEF_KINDS`, so no definition form is checked less than
# another) times WHAT it reaches for. The reference axis is derived from
# `_Categories` — the namespaces a bare name resolves against — taking the
# fields an importing GAME can populate but a library cannot: `state_vars`
# beyond the contract, `zones`, and the deck-derived `enums`/`ranks`/`suits`,
# reachable both as a bare value name and inside a card literal, whose rank and
# suit are plain strings rather than classified names. `locals` and the stdlib
# `functions` are not on the axis: both are the same for a library as for a
# game, so neither is a channel the game can feed. Calls are the axis's second
# half, since a `Call`'s func is a name the game's own definitions could supply.

# One leak site per definition kind, with a `{read}` slot for the reference. Each
# site puts `{read}` where any of the five spellings is grammatical, so the axes
# are genuinely crossed rather than paired off. The `procedures` site carries a
# move type that runs it, because an uninvoked procedure is separately an error
# and the cell must fail for its OWN reason.
_LEAK_SITE: dict[str, str] = {
    "rules": "rule r {{ applies_when: {read} is not none }}",
    "move_types": (
        "move_type m {{ effect "
        "{{ declared_thing := if {read} is not none then 1 else 2 }} }}"
    ),
    "types": "type T = {{ x : Integer }} derived {{ y = {read} }}",
    "defines": (
        "define d -> {{ a | b }} "
        "{{ if {read} is not none {{ produce a }} else {{ produce b }} }}"
    ),
    "functions": "function f() = {read}",
    "procedures": (
        "procedure p() {{ declared_thing := if {read} is not none then 1 else 2 }} "
        "move_type runner {{ effect {{ run p() }} }}"
    ),
}

# reference kind -> (the leaking spelling, the contracted spelling that is its
# control, or None where no legal counterpart exists). Where a control exists it
# is the same shape in the same slot, so a cell that rejects can only be
# rejecting the leak. Three kinds have no control by construction: a library
# holds no zones and names no deck, so there is no in-contract way to write a
# zone name, a suit, or a card — for those the wall is total, and the site's
# own validity is established by the `state` and `call` controls beside them.
_LEAK_READS: dict[str, tuple[str, str | None]] = {
    "state": ("undeclared_thing", "declared_thing"),
    "call": ("undeclared_helper()", "contracted_helper()"),
    "zone": ("hand", None),
    "deck_value": ("hearts", None),
    "card_literal": ("(Q of hearts)", None),
}


def test_leak_sites_cover_every_definition_kind() -> None:
    """A library holds six definition kinds and any of them can leak, so the
    grid's site table must cover `_LIBRARY_DEF_KINDS` exactly — the same
    registry the collision matrix above sweeps.

    red under: drop a key from `_LEAK_SITE`."""
    assert set(_LEAK_SITE) == {field for field, _ in _LIBRARY_DEF_KINDS}


# reference kind -> the `_Categories` field(s) it reaches through. `call` has no
# entry: a `Call`'s func is not classified against `_Categories` at all, so it is
# the axis's one non-namespace channel.
_AXIS_NAMESPACE: dict[str, frozenset[str]] = {
    "state": frozenset({"state_vars"}),
    "zone": frozenset({"zones"}),
    "deck_value": frozenset({"enums"}),
    "card_literal": frozenset({"ranks", "suits"}),
}


def test_the_reference_axis_covers_every_game_fed_namespace() -> None:
    """`_Categories` is the registry of namespaces a bare name resolves against,
    and the grid's reference axis must cover every field of it an importing GAME
    can feed. Two are excluded and neither is a gap: `locals` is whatever the
    body binds for itself, and `functions` is the stdlib value set, identical for
    a library and a game — no game can put anything into either.

    Derived rather than spelled, because spelling it is how this axis went wrong:
    it began as {state, call} and silently omitted zones, deck values and card
    literals — three channels the design forbids a library, one of which the
    wall did not in fact refuse.

    red under: add a field to `_Categories`, or drop a key from
    `_AXIS_NAMESPACE`."""
    game_fed = {f.name for f in fields(_Categories)} - {"locals", "functions"}
    covered: set[str] = set()
    for reached in _AXIS_NAMESPACE.values():
        covered |= reached
    assert covered == game_fed, (
        f"reference axis reaches {sorted(covered)}, `_Categories` offers "
        f"{sorted(game_fed)}"
    )
    assert set(_AXIS_NAMESPACE) | {"call"} == set(_LEAK_READS)


def _leaky(field: str, kind: str, *, leaking: bool) -> n.Library:
    spellings = _LEAK_READS[kind]
    read = spellings[0] if leaking else spellings[1]
    assert read is not None
    return parse_library(
        "library leaky { requires { declared_thing : Integer } "
        "function contracted_helper() = declared_thing "
        f"{_LEAK_SITE[field].format(read=read)} }}",
        "docs/libraries/leaky.cardlang",
    )


# A game that satisfies `leaky`'s contract AND happens to provide everything the
# leaks reach for — the undeclared state name, the helper function, a `hand`
# zone, and a deck holding the queen of hearts. That second half is what makes
# the cells meaningful: without it they would fail as ordinary unresolved names
# and prove nothing about the contract.
_LEAK_GAME = """
game Host {
  uses leaky
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state {
    declared_thing   : Integer = 0
    undeclared_thing : Integer = 0
  }
  phase play { }
  winner: highest declared_thing
}
function undeclared_helper() = 1
"""


def _leak_host() -> n.Game:
    return parse_text(_LEAK_GAME, "host.cardlang")


def _leak_cells() -> list[object]:
    """The full cross. The `card_literal` column is the one open today: a card
    literal's rank and suit are plain strings on the node, not classified
    `NameRef`s, so the classification sweep never saw them."""
    return [
        pytest.param(
            field,
            kind,
            id=f"{field}-{kind}",
            marks=[pytest.mark.xfail(strict=True)] if kind == "card_literal" else [],
        )
        for field, _ in _LIBRARY_DEF_KINDS
        for kind in sorted(_LEAK_READS)
    ]


@pytest.mark.parametrize("field,kind", _leak_cells())
def test_a_library_may_not_reach_past_its_contract(
    field: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every leak is refused, wherever it is written and whatever it reaches
    for, and refused in the LIBRARY's currency — the span is in the library
    file, because the library author is who must fix it. A game cannot: the
    only thing it could do is provide the name, which is exactly the accident
    that made the leak invisible.

    red under: delete the `_check_library_encapsulation` call from
    `_apply_uses`."""
    _patch_libraries(monkeypatch, {"leaky": _leaky(field, kind, leaking=True)})
    with pytest.raises(DiagnosticError) as exc:
        resolve(_leak_host())
    message = str(exc.value)
    assert "docs/libraries/leaky.cardlang:" in message, (
        f"the failure must land in the library file, not in the game:\n{message}"
    )
    assert "library 'leaky'" in message


@pytest.mark.parametrize(
    "field,kind",
    [
        (f, k)
        for f, _ in _LIBRARY_DEF_KINDS
        for k in sorted(_LEAK_READS)
        if _LEAK_READS[k][1] is not None
    ],
    ids=lambda v: str(v),
)
def test_the_same_site_reaching_only_its_contract_is_accepted(
    field: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control row. Each cell is its leaking twin with one name swapped —
    a contracted state variable for the undeclared one, a library-defined
    function for the game's — so a rejecting leak cell can only be rejecting
    the leak and not the site.

    red under: make `_check_library_encapsulation` reject anything it classifies
    rather than only what it fails to."""
    _patch_libraries(monkeypatch, {"leaky": _leaky(field, kind, leaking=False)})
    resolve(_leak_host())


# A body reading its OWN parameter is the second control the encapsulation check
# needs: a parameter is bound, so counting it as a leak would refuse a perfectly
# ordinary library. The axis is `resolve._PARAM_BEARING` — the registry of
# declaration kinds that HAVE parameters — filtered to the kinds a library can
# hold, so a new parameterized declaration form joins this sweep automatically.
_PARAM_SITE: dict[str, str] = {
    "rules": (
        "rule NoLead(suit : Suit) {{ constrains: play_to_trick "
        "applies_when: {read} is not none }}"
    ),
    "move_types": "move_type m(s : Suit) {{ when: {read} is not none effect {{ }} }}",
    "functions": "function fn(x : Integer) = {read} + 1",
    "procedures": "procedure pr(y : Integer) {{ declared_thing := {read} }}",
}

# Which parameter each site reads, keyed the same way.
_PARAM_READ: dict[str, str] = {
    "rules": "suit",
    "move_types": "s",
    "functions": "x",
    "procedures": "y",
}


def _param_bearing_library_kinds() -> list[str]:
    """The `_PARAM_BEARING` collections a library can hold — all of them, since a
    library holds every definition kind a game does. Derived so the sweep below
    cannot silently stop covering one."""
    kinds = {collection for collection, _, _ in _PARAM_BEARING.values()}
    return sorted(kinds & {field for field, _ in _LIBRARY_DEF_KINDS})


def test_param_sites_cover_every_parameterized_kind() -> None:
    """red under: drop a key from `_PARAM_SITE`."""
    assert set(_PARAM_SITE) == set(_param_bearing_library_kinds())
    assert set(_PARAM_READ) == set(_PARAM_SITE)


@pytest.mark.parametrize("field", _param_bearing_library_kinds())
def test_a_body_reading_its_own_parameter_is_not_a_leak(field: str) -> None:
    """A parameter is bound in the body it belongs to, so it is not something the
    contract has to cover — for every kind that has parameters, not the three
    whose scoping happened to be implemented.

    `rules` was the open cell: `_rewrite` scoped move-type, function and
    procedure parameters but not a rule template's, because the game path
    instantiates templates (substituting the arguments away) before it
    classifies, so it never needed the arm. Reading a library's definitions
    directly is the first caller that does.

    red under: delete the `n.RuleDef` arm from `_rewrite`."""
    source = _PARAM_SITE[field].format(read=_PARAM_READ[field])
    library = parse_library(
        f"library probe {{ requires {{ declared_thing : Integer }} {source} }}",
        "docs/libraries/probe.cardlang",
    )
    reach = _library_reach(library)
    assert not reach.unresolved, (
        f"a {field} parameter is bound, not a leak: "
        f"{sorted({r.name for r in reach.unresolved})}"
    )


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


@pytest.mark.parametrize("name", sorted(library_names()))
def test_every_library_contracts_for_exactly_what_it_reaches(name: str) -> None:
    """Both directions of the contract, for every library in docs/libraries/ —
    the registry, not the one library that exists today.

    Sufficiency (nothing reached past the contract) is what the wall enforces,
    asserted here as the acceptance half: the corpus library must actually
    satisfy the wall the grid above proves fires. Minimality (nothing in the
    contract that is never reached) is the other direction — a `requires` entry
    no definition reads is dead contract, forcing every consumer to declare
    state for no reason.

    Both read the classified `state_reads` set rather than the library's text.
    The text version of the minimality half was a substring search over
    comment-inclusive source, which a bogus entry `street` passed because the
    word appeared in a comment, and `rais` passed as a substring of `raises`.

    red under: add `unused_thing : Integer` to
    docs/libraries/poker_betting.cardlang's `requires` block."""
    library = load_library(name)
    reach = _library_reach(library)
    assert not reach.unresolved, (
        f"library '{name}' reads "
        f"{sorted({r.name for r in reach.unresolved})} past its contract"
    )
    assert not reach.unknown_calls, (
        f"library '{name}' calls "
        f"{sorted({c.func for c in reach.unknown_calls})} past its contract"
    )
    dead = {r.name for r in library.requires} - reach.state_reads
    assert not dead, (
        f"library '{name}' requires {sorted(dead)}, which no definition in it "
        f"reads — drop them from the contract"
    )


def test_poker_betting_is_registered() -> None:
    assert "poker_betting" in library_names()
