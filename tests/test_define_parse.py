from __future__ import annotations

from cardlang.parse import parse_text

SRC = """
define declare_trump -> { trump_declared(Suit) | bid_abandoned } {
  produce bid_abandoned
}
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  winner: highest score
}
"""


def test_define_parses_with_variant_set() -> None:
    game = parse_text(SRC, "g.cardlang")
    assert [d.name for d in game.defines] == ["declare_trump"]
    define = game.defines[0]
    assert [(c.tag, c.payload_types) for c in define.cases] == [
        ("trump_declared", ("Suit",)),
        ("bid_abandoned", ()),
    ]
    assert len(define.body) == 1
