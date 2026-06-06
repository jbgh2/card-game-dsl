"""Tests for the parse stage (Lark + Transformer -> typed AST).

Walking-skeleton subset only: game header, players, deck, zones.
"""

from __future__ import annotations

from cardlang.ast.nodes import Game, PlayersSpec, TypeArg, TypeRef, ZoneDecl
from cardlang.parse import parse_text

SKELETON = """game Skeleton {
  players: 2
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
    text = "game R { players: 2..8 cards: standard52 zones { } }"
    game = parse_text(text, "r.dsl")
    assert game.players.low == 2
    assert game.players.high == 8
    assert game.players.is_range


def test_spans_point_into_source() -> None:
    game = parse_text(SKELETON, "skeleton.dsl")
    assert game.span is not None
    assert game.span.source_name == "skeleton.dsl"
    # The hand zone is on line 6 of the source text.
    hand_zone = game.zones[1]
    assert hand_zone.span is not None
    assert hand_zone.span.line == 6


def test_line_offset_is_applied() -> None:
    # Simulates a block whose content starts at line 4 of a markdown file.
    game = parse_text(SKELETON, "hearts.md", line_offset=3)
    assert game.span is not None
    assert game.span.line == 4  # "game Skeleton" was line 1 in the block, +3 offset


def test_comments_are_ignored() -> None:
    text = """game C {
  players: 2  // two players
  cards: standard52
  // a comment line
  zones { }
}
"""
    game = parse_text(text, "c.dsl")
    assert game.name == "C"
    assert game.zones == ()
