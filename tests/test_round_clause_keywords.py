"""A round's result-function clause keyword is fixed by its FORM, both ways.

`outcome` and `winner` name different things (docs/glossary.md, Outcome /
Winner): a trick round yields a player, so its clause is `winner <fn>`; an
auction yields a tagged `(tag, payloads)` result, so its clause is
`outcome <fn>`. The two are not interchangeable spellings of one slot, and
this module pins that neither form accepts the other's keyword.

Why it needs a pin at all, when the grammar already enforces it: it enforces
it only because `round_stmt` and `auction_stmt` happen to spell different
literals today. Nothing NAMES the property, so a later edit that unified the
productions — issue #210's Round node split touches exactly these two — could
let an auction take `winner`, and every existing test would still pass. The
corpus parsing proves the correct pairings work; only a rejection test proves
the incorrect ones still fail.

The asymmetry this closes is a review hazard, not just a theoretical one. When
the trick clause was renamed (#205 slice 2), a mechanical transform had to
convert the trick form's `outcome` while leaving the auction form's alone. A
transform that converted too MUCH is caught by the corpus failing to parse; one
that converted too LITTLE would have been caught the same way — but only
because both directions are refused. If either became permissive, a
mis-transformed clause would parse and silently run on the wrong form.

property:  the clause keyword and the round form agree, in both directions
domain:    {trick, auction} x {`winner`, `outcome`} — the full cross, since a
           round form's result clause admits exactly one keyword and the two
           forms are the only ones that carry a result function (`build_form`'s
           cascade; the climb form binds its winner implicitly and the betting
           form has no clause at all, so neither has a cell here)
covered:   all four cells, as the parametrization below
residual:  none — the cross is complete over the forms that carry a clause

red under: change `round_stmt`'s `"winner"` literal back to `"outcome"` in
cardlang/grammar/cardlang.lark — both trick rows then fail (the `winner` cell
stops parsing, the `outcome` cell starts), while the two auction rows stay
green, since the plant reaches only `round_stmt`. Verified by making that edit.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

TRICK = """
game G {
  players: 4
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile
          captured[player] : PlayerPile<player> }
  state { leader : Player? = none }
  phase play {
    round play_to_trick from leader over all players source hand into trick_pile %s
    leader := winner
  }
  winner: highest leader
}
"""

AUCTION = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { passes : Integer = 0 }
  phase bid -> outcome { all_pass } {
    round offering [pass] from 0 over all players until (passes >= 2) %s
  }
  winner: highest passes
}
move_type pass { effect { passes += 1 } }
"""

# (form, keyword, accepted?) — the full cross. The function named in each clause
# is drawn from that form's own registry, so a rejection can only be about the
# KEYWORD: pairing the right keyword with a wrong-registry function is a
# different wall, pinned in tests/test_fail_loud.py.
CELLS = [
    ("trick", "winner", "highest_of_led_suit", True),
    ("trick", "outcome", "highest_of_led_suit", False),
    ("auction", "outcome", "bridge_auction_outcome", True),
    ("auction", "winner", "bridge_auction_outcome", False),
]


@pytest.mark.parametrize("form,keyword,fn,accepted", CELLS)
def test_clause_keyword_is_fixed_by_round_form(
    form: str, keyword: str, fn: str, accepted: bool
) -> None:
    src = (TRICK if form == "trick" else AUCTION) % f"{keyword} {fn}"
    if accepted:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    # The refusal must be the grammar's, not a downstream name lookup: if the
    # production accepted the keyword and something later happened to reject the
    # sentence, the pairing would not actually be enforced.
    assert "syntax error" in str(ei.value), str(ei.value)
