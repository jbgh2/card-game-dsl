"""Tests for the parse stage (Lark + Transformer -> typed AST).

Walking-skeleton subset only: game header, players, deck, zones — plus the
memoization pins `cardlang/parse.py`'s Contract block cites (see
"the memo is sound only while" below).
"""

from __future__ import annotations

import dataclasses
import pathlib

import pytest

from cardlang import parse
from cardlang.ast.nodes import Game, PlayersSpec, TypeArg, TypeRef, ZoneDecl
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _parse_text_cached, parse_text
from cardlang.pipeline import _check

SKELETON = """game Skeleton {
  players: 2
  max_length: 1000
  cards: standard52
  zones {
    deck         : Deck
    hand[player] : Hand<player>
  }
}
"""


def test_parses_game_header() -> None:
    game = parse_text(SKELETON, "skeleton.dsl")
    assert isinstance(game, Game)
    assert game.name == "Skeleton"
    assert game.deck == "standard52"
    assert game.players == PlayersSpec(low=2, high=None, span=game.players.span)


def test_parses_zones_with_index_and_type_args() -> None:
    game = parse_text(SKELETON, "skeleton.dsl")
    assert len(game.zones) == 2

    deck_zone, hand_zone = game.zones
    assert isinstance(deck_zone, ZoneDecl)
    assert deck_zone.name == "deck"
    assert deck_zone.index is None
    assert deck_zone.type_ref == TypeRef(name="Deck", args=(), span=deck_zone.type_ref.span)

    assert hand_zone.name == "hand"
    assert hand_zone.index == "player"
    assert hand_zone.type_ref.name == "Hand"
    assert hand_zone.type_ref.args == (
        TypeArg(name="player", span=hand_zone.type_ref.args[0].span),
    )


def test_players_range() -> None:
    text = "game R { players: 2..8 max_length: 1000 cards: standard52 zones { } }"
    game = parse_text(text, "r.dsl")
    assert game.players.low == 2
    assert game.players.high == 8
    assert game.players.is_range


def test_spans_point_into_source() -> None:
    game = parse_text(SKELETON, "skeleton.dsl")
    assert game.span is not None
    assert game.span.source_name == "skeleton.dsl"
    # The hand zone is on line 7 of the source text.
    hand_zone = game.zones[1]
    assert hand_zone.span is not None
    assert hand_zone.span.line == 7


def test_line_offset_is_applied() -> None:
    # Simulates a block whose content starts at line 4 of a markdown file.
    game = parse_text(SKELETON, "hearts.md", line_offset=3)
    assert game.span is not None
    assert game.span.line == 4  # "game Skeleton" was line 1 in the block, +3 offset


def test_comments_are_ignored() -> None:
    text = """game C {
  players: 2  // two players
  max_length: 1000
  cards: standard52
  // a comment line
  zones { }
}
"""
    game = parse_text(text, "c.dsl")
    assert game.name == "C"
    assert game.zones == ()


# ---------------------------------------------------------------------------
# `parse_text` memoization (cardlang/parse.py, Contract "Now illegal").
#
# One probe per condition the memo's soundness rests on: it actually fires; its
# key separates what changes the AST; its key does NOT separate mere argument
# spellings; it never caches a rejection; and the front end it stands in for is
# deterministic, so a cached answer equals a recomputed one. A last Shadow Guard
# pins the immutability that lets two callers hold one tree — the guard for that
# is test_node_registry.py, which this one names rather than duplicates.
# ---------------------------------------------------------------------------


def _unique(name: str) -> str:
    return f"""game {name} {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck }}
}}
"""


def test_repeated_parse_returns_the_identical_object() -> None:
    # Without this the optimization is vacuous: every other claim about parse
    # cost assumes the second call is free, and only object identity shows it.
    text = _unique("MemoLive")
    assert parse_text(text, "a.dsl") is parse_text(text, "a.dsl")


def test_memo_key_separates_source_name_and_line_offset() -> None:
    # Both feed the Span on every node, so a memo keyed on `text` alone would
    # hand back a tree whose diagnostics point at the wrong file and line.
    text = _unique("MemoKeyed")
    by_name = parse_text(text, "one.dsl"), parse_text(text, "two.dsl")
    assert by_name[0] is not by_name[1]
    assert by_name[0].span is not None and by_name[1].span is not None
    assert by_name[0].span.source_name == "one.dsl"
    assert by_name[1].span.source_name == "two.dsl"

    flat, offset = parse_text(text, "m.md"), parse_text(text, "m.md", line_offset=3)
    assert flat is not offset
    assert flat.span is not None and offset.span is not None
    assert offset.span.line == flat.span.line + 3


def test_argument_spelling_does_not_split_the_memo() -> None:
    # `lru_cache` keys on the call shape, so a bare `lru_cache` on `parse_text`
    # would file these three identical requests under three separate entries.
    # `_parse_text_cached` takes `line_offset` positionally to normalize them.
    text = _unique("MemoSpelling")
    parse_text(text, "s.dsl")  # prime, so the count below is spelling-only
    before = _parse_text_cached.cache_info().misses
    a = parse_text(text, "s.dsl")
    b = parse_text(text, "s.dsl", 0)
    c = parse_text(text, "s.dsl", line_offset=0)
    assert a is b is c
    assert _parse_text_cached.cache_info().misses == before


def test_a_rejection_is_re_raised_every_time_never_memoized() -> None:
    # The whole rejection corpus (tests/rejections/) asserts on diagnostics.
    # If a raise were cached, the second assertion in any such test would be
    # checking a replayed object rather than a live parse. `lru_cache` stores
    # nothing on an exception; this pins that we depend on it.
    bad = "game Broken { players: 2"
    with pytest.raises(DiagnosticError) as first:
        parse_text(bad, "broken.dsl")
    with pytest.raises(DiagnosticError) as second:
        parse_text(bad, "broken.dsl")
    assert first.value is not second.value


@pytest.mark.parametrize("game", ["hearts", "coup", "canasta"])
def test_the_front_end_is_deterministic_on_repeat(game: str) -> None:
    """The one real coverage loss the memo caused, restored deliberately.

    Before memoization the suite re-derived ~1000 parses and ~800 checks per
    run on input it had already seen. Nothing asserted they agreed, but they
    did incidentally guard against a nondeterministic front end — an AST tuple
    built by iterating a `set`, say, which would make the pipeline's output
    depend on hash order. Those are dict lookups now, so the guard is gone
    unless it is stated.

    Stated here, via `__wrapped__` to bypass both memos. Three games rather
    than the corpus because each pass is a real Earley parse: `hearts`
    (trick-taking), `coup` (interactive, procedures), `canasta` (the largest
    source, melds). SAMPLED, not exhaustive — a nondeterminism confined to a
    construct only some other game uses would not be caught here."""
    path = pathlib.Path(__file__).parent.parent / "docs" / "games" / f"{game}.cardlang"
    text = path.read_text()
    first = _parse_text_cached.__wrapped__(text, str(path), 0)
    second = _parse_text_cached.__wrapped__(text, str(path), 0)
    assert first == second, f"{game}: two parses of identical text disagree"
    assert _check.__wrapped__(first) == _check.__wrapped__(second), (
        f"{game}: two checks of equal trees disagree"
    )


def test_a_shared_ast_cannot_be_mutated() -> None:
    # A SHADOW GUARD, not the Owner Guard: it probes one field of one node. The guard for
    # the whole Node domain is test_node_registry.py's
    # `test_every_node_kind_is_frozen` + `test_every_node_kind_has_slots`,
    # enumerated from the module's own dataclass registry. This exists only to
    # fail in the parse tests' own channel — a reader who breaks the memo's
    # immutability premise while editing here sees it immediately, rather than
    # in a registry test two files away.
    game = parse_text(_unique("MemoFrozen"), "f.dsl")
    with pytest.raises(dataclasses.FrozenInstanceError):
        game.name = "Renamed"  # type: ignore[misc]


# --- the parse-hint registry ------------------------------------------------
#
# Completeness ledger (decisions.md "Closed-domain completeness")
# --------------------------------------------------------------
#     property:  a hint appended to a syntax error is TRUE where it fires. A
#                hint whose sentence holds only for one parse entry point
#                says so in the registry and is withheld everywhere else —
#                because a hint is read as a diagnosis, and a false one sends
#                a designer to fix a file that is not the problem.
#     domain:    `parse._PARSE_HINTS` (the keyword axis) x the parse entry
#                points that carry a hint (`parse_to_tree`'s `start`: a game
#                and a library). Both axes derived — the keywords from the
#                registry, the starts from `_HINT_STARTS` below, which is the
#                set of values the registry's own scope column may take.
#     registry:  cardlang/parse.py's `_PARSE_HINTS`.
#     covered:   every (keyword, start) cell, executed: the probe puts the
#                keyword alone on a line, which is malformed under every
#                start, and asserts the hint appears exactly when the
#                registry's scope admits that start.
#     does not prove:  that a hint's SENTENCE is accurate — only that it fires
#                where the registry says. The wording is held by
#                `test_a_parse_hint_never_diagnoses_the_author_s_position`
#                (tests/test_mode_surface.py) and by the rejection corpus.

_HINT_STARTS: tuple[str, ...] = ("start", "library")


def _hint_probe(keyword: str, start: str) -> str:
    """A source under `start` whose parse fails on a line beginning with
    `keyword` — the shape `_parse_hint`'s fallback probe reads."""
    if start == "library":
        return f"library L {{\n  {keyword}\n}}\n"
    return f"game G {{\n  players: 2\n  {keyword}\n}}\n"


_HINT_CELLS = [
    (keyword, start) for keyword in sorted(parse._PARSE_HINTS) for start in _HINT_STARTS
]


@pytest.mark.parametrize("keyword,start", _HINT_CELLS)
def test_a_parse_hint_fires_exactly_where_its_sentence_is_true(
    keyword: str, start: str
) -> None:
    """keyword x parse entry point, over the registry itself.

    The `primitives` hint tells its reader that a LIBRARY may not declare the
    block. Fired on a game — which may — it is a false diagnosis attached to
    a real syntax error, and its advice ("write the block in the game") is
    advice the author has already taken.

    red under: drop the scope column from `_PARSE_HINTS`' `primitives` row and
    let `_parse_hint` return every entry's text — the game cells for that
    keyword then carry a sentence about libraries.
    """
    scope, text = parse._PARSE_HINTS[keyword]
    with pytest.raises(DiagnosticError) as ei:
        parse.parse_to_tree(_hint_probe(keyword, start), "probe", start=start)
    message = str(ei.value)
    assert "syntax error" in message, message
    if scope is None or scope == start:
        assert text in message, (
            f"the {keyword!r} hint is true under {start!r} and did not fire: "
            f"{message}"
        )
    else:
        assert text not in message, (
            f"the {keyword!r} hint claims something true only under {scope!r} "
            f"and fired under {start!r}: {message}"
        )


def test_every_parse_hint_scope_is_a_real_entry_point() -> None:
    """The scope column's own domain, so a typo cannot silence a hint.

    A scope naming a start nobody parses withholds the hint everywhere while
    reading like a restriction — the vacuously-green shape one level down from
    the grid above.

    red under: set a row's scope to `"libary"`.
    """
    for keyword, (scope, _text) in parse._PARSE_HINTS.items():
        assert scope is None or scope in _HINT_STARTS, (
            f"the {keyword!r} hint is scoped to {scope!r}, which is not a "
            f"parse entry point — the hint would never fire"
        )
