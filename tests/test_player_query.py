"""Player-collection queries — introduced by Getaway.

Three forms over the player ring, sharing a predicate evaluated per player with
`player` bound to the candidate:

    players where <pred>             -> the set of matching players (participants)
    the player where <pred>          -> the unique matching player (loser select)
    number of players where <pred>   -> how many match (elimination counts)

Plus `is not empty` (the negation of the existing `is empty`), since an
elimination game selects the player who still holds cards.
"""

from __future__ import annotations

import random
from importlib import resources

from lark import Lark, Tree

from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def _loser_selection(game: n.Game) -> n.Expr:
    assert game.loser is not None
    return game.loser.selection


def test_three_player_query_forms_parse() -> None:
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { hand[player] : Hand<player> }
      state { eliminated[player] : Boolean = false }
      phase p {
        let a = players where not eliminated[player]
        let b = the player where hand[player] is not empty
        let c = number of players where hand[player] is not empty
      }
    }
    """
    game = parse_text(text, "t.dsl")
    lets = [it for it in game.phases[0].items if isinstance(it, n.LetStmt)]
    kinds = [q.value.kind for q in lets if isinstance(q.value, n.PlayerQuery)]
    assert kinds == ["set", "pick", "count"]


def test_is_not_empty_parses() -> None:
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      zones { hand[player] : Hand<player> }
      phase p { let a = hand is not empty }
    }
    """
    game = parse_text(text, "t.dsl")
    let0 = next(it for it in game.phases[0].items if isinstance(it, n.LetStmt))
    assert isinstance(let0.value, n.IsCheck)
    assert let0.value.kind == "not_empty"


def test_player_query_zero_ambiguity() -> None:
    text = """
    game T {
      players: 4
      max_length: 1000
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { hand[player] : Hand<player> }
      state { eliminated[player] : Boolean = false }
      phase p {
        repeat until (number of players where hand[player] is not empty) == 1 {
          let s = players where not eliminated[player]
        }
      }
      loser: the player where hand[player] is not empty
    }
    """
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    explicit = Lark(grammar, parser="earley", ambiguity="explicit",
                    propagate_positions=True, maybe_placeholders=True)
    tree = explicit.parse(text)
    assert isinstance(tree, Tree)
    ambig = sum(1 for nd in tree.iter_subtrees() if nd.data == "_ambig")
    assert ambig == 0, f"player-query introduced {ambig} ambiguity site(s)"


PICK_GAME = """
game PickTest {
  players: 1
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {
    deck : Deck
    hand[player] : Hand<player>
  }
  phase setup { deal 13 cards from deck to each hand }
  loser: the player where hand[player] is not empty
}
"""


def test_the_player_where_selects_the_unique_match_at_runtime() -> None:
    game = check_dsl(PICK_GAME, "pick.dsl")
    result = play_game(game, random.Random(0))
    assert result.loser == 0  # the sole player, who holds cards
