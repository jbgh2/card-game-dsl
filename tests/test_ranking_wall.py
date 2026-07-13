"""`ranking:` entries must name real ranks of the declared deck.

Unchecked, a typo (`ranking: A K Q J 11 9 ...` for `10`) silently widened
typecheck's Rank enum domain (`value_enum_map` unions `game.ranking` into it;
its comment claimed a declared ranking "adds nothing here beyond order" —
false for an unknown entry) — the mistyped literal then type-checked fine
and every comparison against it was simply False forever, at runtime, with
no diagnostic anywhere (Surface totality). A duplicate entry had the same
shape: `driver.py` builds `rs.rank_index` from `enumerate(game.ranking)`, so
a repeat would silently give one rank two strengths and shift every rank
after it down by one, last-wins, with no error.

Property: every `ranking:` entry names a rank of the declared deck, and no
entry repeats.

Domain: `game.ranking: tuple[str, ...]` x `deck_ranks(game.deck)` membership,
for every deck in `cardlang.runtime.values.DECKS`.

Registry: `cardlang.stdlib.values.deck_ranks` (the same source
`driver.py`'s `rs.rank_index` and `mechanics.py`'s Rank-parameter
enumeration read at runtime — one source of truth by construction).

Covered: unknown entry (standard52, and a non-French deck — coup15), a
repeated entry, and acceptance of a real corpus ranking (hearts')
per-deck-shape sample plus every full-permutation ranking in
`docs/games/*.cardlang` (swept below). An unknown deck name is a no-op here
(`_resolve_deck` reports it separately; `_resolve_ranking` returns early
rather than raising from `deck_ranks` on a name it cannot look up). An
undeclared (empty) `ranking:` is likewise a no-op — nothing to validate.

Sampled: not every one of the 8 decks in `DECKS` gets its own dedicated
misuse-probe test (standard52 and coup15 stand in for the French-suited and
non-French shapes); every deck's `ranking:` shape when one IS declared is
still exhaustively checked by the corpus sweep, which iterates every
`docs/games/*.cardlang` game that declares one.

Residual: coverage (every deck rank present) is deliberately NOT required —
`tests/test_action_space_multiparam.py`'s
`test_rank_domain_sourced_from_game_ranking_not_deck` pins a genuine PARTIAL
`ranking:` (`ranking: A K Q` under standard52's 13 ranks) as a supported,
deliberate feature that narrows the `Rank` move-parameter domain; walling
partial coverage here would break that regression test. The corpus itself
(docs/games/*.cardlang) happens to declare only full permutations — swept
below — but that is incidental, not required. A card whose rank falls
outside a partial ranking still crashes `rank_value`'s
`ctx.rs.rank_index[...]` lookup at runtime instead of erroring at resolve
time — recorded in docs/roadmap.md ("`ranking:` coverage is unchecked"),
walled only by that runtime KeyError, not by this check.

Adjacent cell closed here (same two-source domain, opposite direction):
card-LITERAL rank validation (`resolve._categories.ranks`, consumed by the
`CardLiteral` arm of `_validate_refs`) derives from `deck_ranks(deck)` —
never from `ranking:` — because a literal asks "does this card exist",
not "where does it sort". Probed: no-`ranking:` literal accepts, a
partial-ranking-excluded literal accepts, a non-deck rank still rejects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.stdlib.values import deck_ranks

GAMES = Path(__file__).parent.parent / "docs" / "games"


def _game(ranking: str, deck: str = "standard52") -> str:
    return f"""
game Mini {{
  players: 4
  max_length: 1000
  cards: {deck}
  ranking: {ranking}
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0 }}
  phase play {{ }}
  winner: highest score
}}
"""


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


# --- rejections --------------------------------------------------------


def test_unknown_rank_entry_rejected() -> None:
    _rejects(_game("A K Q J 11 9 8 7 6 5 4 3 2"), "names unknown rank '11'")


def test_unknown_rank_entry_rejected_on_a_non_french_deck() -> None:
    _rejects(
        _game("Duke Assassin Captain Ambassador Countess", deck="coup15"),
        "names unknown rank 'Countess'",
    )


def test_duplicate_rank_entry_rejected() -> None:
    _rejects(_game("A A K Q J 10 9 8 7 6 5 4 3"), "repeats rank 'A'")


def test_unknown_deck_does_not_crash_the_ranking_check() -> None:
    # `_resolve_deck` reports the unknown deck; `_resolve_ranking` must not
    # ALSO raise a raw exception from `deck_ranks` on a name it can't resolve.
    _rejects(_game("A K Q", deck="nope99"), "unknown deck 'nope99'")


# --- acceptances --------------------------------------------------------


def test_partial_ranking_accepted_not_a_full_permutation() -> None:
    # The residual this check deliberately leaves open (module docstring):
    # a strict subset of the deck's ranks is a legal, supported declaration.
    game = check_dsl(_game("A K Q"), "mini.cardlang")
    assert game.ranking == ("A", "K", "Q")


def test_full_permutation_ranking_accepted() -> None:
    check_dsl(_game("A K Q J 10 9 8 7 6 5 4 3 2"), "mini.cardlang")


def test_reordered_full_permutation_accepted() -> None:
    # ranking: declares STRENGTH order, not deck order — any permutation of
    # the deck's ranks is legal (president.cardlang's low-to-high-2 order).
    check_dsl(_game("2 A K Q J 10 9 8 7 6 5 4 3"), "mini.cardlang")


def test_no_ranking_declared_is_a_no_op() -> None:
    src = """
game Mini {
  players: 4
  max_length: 1000
  cards: coup15
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { }
  winner: highest score
}
"""
    check_dsl(src, "mini.cardlang")


# --- corpus sweep --------------------------------------------------------


@pytest.mark.parametrize("path", sorted(GAMES.glob("*.cardlang")), ids=lambda p: p.stem)
def test_corpus_ranking_resolves_clean(path: Path) -> None:
    check_source(path)


def test_every_declared_corpus_ranking_is_a_full_permutation_of_its_deck() -> None:
    """Documents the corpus fact this module's docstring relies on: every
    `docs/games/*.cardlang` game that declares a `ranking:` declares a FULL
    permutation of its deck's ranks (verified directly here, independent of
    resolve.py, since resolve.py itself does not require this)."""
    from cardlang.parse import parse_text

    checked_any = False
    for path in sorted(GAMES.glob("*.cardlang")):
        game = parse_text(path.read_text(), str(path))
        if not game.ranking:
            continue
        checked_any = True
        assert set(game.ranking) == set(deck_ranks(game.deck)), path
        assert len(game.ranking) == len(set(game.ranking)), path
    assert checked_any  # the sweep isn't vacuous


# --- card literals validate against the DECK, not the ranking ----------
# (Codex review of PR #48, round 2: `cats.ranks` read `game.ranking`, so a
# no-`ranking:` game rejected every card literal, and a partial ranking
# rejected literals naming real deck cards outside it — while the bare
# enum spelling `card.rank is Q` resolved via the deck. Existence is the
# deck's domain; `ranking:` is an ordering.)


def _literal_game(ranking_line: str, lit: str) -> str:
    return f"""
game Mini {{
  players: 4
  max_length: 1000
  cards: standard52
  {ranking_line}
  zones {{ deck : Deck  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    let x = any card in pile where card is ({lit})
  }}
  winner: highest score
}}
"""


def test_card_literal_accepted_without_a_ranking_header() -> None:
    check_dsl(_literal_game("", "Q of spades"), "mini.cardlang")


def test_card_literal_outside_a_partial_ranking_accepted() -> None:
    # `J of spades` EXISTS in standard52; the partial ranking narrows the
    # Rank move-param domain, not which cards can be named.
    check_dsl(_literal_game("ranking: A K Q", "J of spades"), "mini.cardlang")


def test_card_literal_with_a_nondeck_rank_still_rejected() -> None:
    _rejects(
        _literal_game("", "X of spades"),
        "unknown rank 'X' in card literal",
    )
