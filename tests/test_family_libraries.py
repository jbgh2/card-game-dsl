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
registry: `resolve._LIBRARY_DEF_KINDS` (the definition kinds) and
          `cardlang.libraries.library_names()` (the available libraries). Both
          are derived, not hand-listed: the kinds are pinned to `n.Library`'s
          own fields by `test_def_kinds_covers_every_library_field` below, and
          the library set is glob-derived from docs/libraries/.
covered:  all of it, exhaustively for the per-kind legs — the game/library and
          library/library collision probes are PARAMETERIZED over
          `_LIBRARY_DEF_KINDS` rather than written out for the kinds that happen
          to collide in today's corpus, so a seventh definition form added to
          `n.Library` fails the pin above before it can ship unwalled.
sampled:  nothing.
residual: the library/stdlib leg covers rules and call functions but NOT move
          types, and that is deliberate rather than a gap: stdlib move types and
          a game's `move_type` definitions are two disjoint consult paths that
          never merge into one namespace (`cardlang/stdlib/moves.py`), so there
          is no collision to wall — Stud, Skat, Schnapsen and Coup all rely on
          defining game-local move types under stdlib-known names today, and a
          wall here would reject four correct games. `test_stdlib_move_type_name_
          is_not_a_collision` below is the falsifiable half of this row: it
          pins the non-collision as intended behaviour rather than an oversight.
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Iterator

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.libraries import library_names, load_library
from cardlang.parse import parse_library, parse_text
from cardlang.resolve import _LIBRARY_DEF_KINDS, resolve

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
    failure that prevents it."""
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
    tier composition rather than inheritance (decisions.md "Family libraries")."""
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
    make a game's meaning depend on `uses` order."""
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


def test_library_rule_may_not_shadow_a_stdlib_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The library leg of the wall `resolve` already applies to game-local rules
    — in library currency, naming the library rather than telling the author to
    delete a local definition they do not have."""
    _patch_libraries(
        monkeypatch,
        {
            "probe_lib": parse_library(
                "library probe_lib { rule MustFollowSuit { } }", "probe_lib.cardlang"
            )
        },
    )
    _rejects(
        _game(uses="uses probe_lib"),
        "library 'probe_lib' defines rule 'MustFollowSuit'",
        "shadows the standard-library rule",
    )


def test_library_function_may_not_shadow_a_stdlib_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_libraries(
        monkeypatch,
        {
            "probe_lib": parse_library(
                "library probe_lib { function pot_share(p : Player) = 1 }",
                "probe_lib.cardlang",
            )
        },
    )
    _rejects(
        _game(uses="uses probe_lib"),
        "library 'probe_lib' defines function 'pot_share'",
        "shadows the stdlib function",
    )


def test_stdlib_move_type_name_is_not_a_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The falsifiable half of this file's residual ledger row. Stdlib move types
    and a game's `move_type` definitions are disjoint consult paths, so a library
    defining one under a stdlib-known name is NOT an error — and must not become
    one, because Stud, Skat, Schnapsen and Coup all rely on that today."""
    _patch_libraries(
        monkeypatch,
        {
            "probe_lib": parse_library(
                "library probe_lib { move_type play_card { effect { } } }",
                "probe_lib.cardlang",
            )
        },
    )
    resolve(_game(uses="uses probe_lib"))


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
