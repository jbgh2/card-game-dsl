"""Reserved value-words are reserved at DECLARATION sites too, not just as
RHS keywords.

Executed evidence of the defect this module pins the fix for (both probes
run clean against the pre-fix resolver):

    1. `zones { hand[player] : Hand<player>  empty : TrickPile }` plus
       `let x = hand[0] is empty` resolves clean, and the `let` value parses
       as `IsCheck(kind="empty")` — the built-in emptiness check — never a
       comparison against the declared `empty` zone. parse.py's
       `compare_is`/`compare_is_not` dispatch on the RHS NameRef's SPELLING
       alone, at parse time, before any declaration exists to consult — no
       amount of `empty` being a real declared zone changes what `x is
       empty` parses to.
    2. `state { score[player] : Integer = 0  true : Boolean = false }` plus
       `let x = true` resolves clean, and the `let` value is a NameRef
       classified `ref_kind="bool"` — the literal — never `ref_kind=
       "state_var"`. `_classify` (resolve.py) intercepts the bare spelling
       `true` before it ever reaches `cats.state_vars`: the declaration is
       unreachable by any bare reference, by construction.

Property: no DECLARATION may take a name in `RESERVED_VALUE_NAMES` — every
name a bare `NameRef` can never mean "this declaration", because some other
fixed reading always wins first (a parser-level keyword dispatch for
`none`/`empty`, `_classify`'s literal short-circuit for `true`/`false`, or a
pronoun's fixed dot-access namespace for `_PRONOUNS`).

Domain: `RESERVED_VALUE_NAMES` (`none`, `empty`, `true`, `false`, and the
five `_PRONOUNS`: `state`, `action`, `outcome`, `active_rules`, `actor`) x
every declaration kind whose name is reachable as a bare `NameRef` in
general expression position: state variables (game-level and phase-local),
zones, functions, function/move-type/rule parameters, `let` names and
indexes, `for each` binders, `each … simultaneously` binders, and user type
names.

Registry: `RESERVED_VALUE_NAMES` itself (cardlang/resolve.py, next to
`_PRONOUNS`) and `_introduced_binders` (the one registry of which node kinds
bind names, reused here via `_check_reserved_binders` rather than
re-enumerated).

Covered: one rejection test per declaration kind in the domain above,
sourced either from `_check_duplicate_names`'s extended sweep (state var,
zone, function, type) or the two dedicated new sweeps
(`_check_reserved_params`, `_check_reserved_binders`).

Sampled: not every (word x declaration-kind) cell gets its own test — one
word per declaration-kind test is enough to prove the wall fires there
(`_check_reserved` is a single, shared, unconditional function; a per-word
test would only re-exercise `RESERVED_VALUE_NAMES` membership, already
covered by the acceptance/rejection pins directly on that constant).

One cell is a deliberate NARROWING, not an oversight: a FUNCTION parameter
may be named `actor`/`action`/`outcome` (`_CALL_SITE_PRONOUNS`) — a
function body is already forbidden from READING those (hermeticity, the
runtime clears them before a call), so a parameter of the same name is not
a hijack, it is the error message's own prescribed repair ("pass the value
in as a parameter instead"). `tests/test_functions.py`'s pre-existing
`function lead(actor : Player) = score[actor]` pins exactly this shape and
was the first-draft version of this wall's regression: a too-broad
reservation rejected it. `state`/`active_rules` stay reserved for function
parameters (both remain READABLE inside a function body); all five stay
reserved for move-type/rule parameters (neither body is hermetic — both
read `actor`/`action`/`outcome` directly as live pronouns).

Residual: `card`/`player` are deliberately EXCLUDED from
`RESERVED_VALUE_NAMES` — both are established, corpus-wide LEXICAL shadow
idioms (`_BINDER_SCOPE_FIELDS` scopes a card-query/quantifier's fixed
binder strictly narrower than any same-named outer declaration), matching
`_check_duplicate_names`'s own "legitimately shadow ACROSS levels" carve-out
— not a defect this reservation needs to close. Probed directly below
(`test_card_and_player_shadowing_stays_legal`): a declared `card`/`player`
name resolves clean and does not misbehave, so no roadmap.md line is
needed for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.resolve import RESERVED_VALUE_NAMES

GAMES = Path(__file__).parent.parent / "docs" / "games"


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


# --- executed evidence of the pre-fix hijack (both now walled) -------------


def test_reserved_value_names_registry_is_exactly_the_documented_set() -> None:
    assert RESERVED_VALUE_NAMES == frozenset(
        {"none", "empty", "true", "false", "state", "action", "outcome", "active_rules", "actor"}
    )


def test_declared_empty_zone_is_rejected_not_silently_hijacked() -> None:
    # Pre-fix this resolved CLEAN and `hand[0] is empty` parsed as the
    # built-in emptiness check, never a reference to this zone (module
    # docstring, evidence #1).
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player>  empty : TrickPile }
  state { score[player] : Integer = 0 }
  phase play { let x = hand[0] is empty }
  winner: highest score
}
""",
        "zone 'empty' is a reserved word",
    )


def test_declared_true_state_var_is_rejected_not_silently_unreachable() -> None:
    # Pre-fix this resolved CLEAN and `true` classified as the bool literal,
    # never as a reference to this state var (module docstring, evidence #2).
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0  true : Boolean = false }
  phase play { let x = true }
  winner: highest score
}
""",
        "state variable 'true' is a reserved word",
    )


# --- one rejection per declaration kind -------------------------------------


def test_zone_named_none_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { none : Deck }
  state { score[player] : Integer = 0 }
  phase play { }
  winner: highest score
}
""",
        "zone 'none' is a reserved word",
    )


def test_function_named_state_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { let x = state(0) }
  winner: highest score
}
function state(p: Player) = 1
""",
        "function 'state' is a reserved word",
    )


def test_type_named_action_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { }
  winner: highest score
}
type action = { x : Integer }
""",
        "type 'action' is a reserved word",
    )


def test_function_parameter_named_state_rejected() -> None:
    # `state` stays reserved for a function parameter: it remains READABLE
    # inside a function body (unlike `actor`/`action`/`outcome`, see the
    # acceptance pin below), so a same-named parameter would still shadow it.
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { let x = f(1) }
  winner: highest score
}
function f(state: Integer) = state
""",
        "function parameter 'state' is a reserved word",
    )


def test_function_parameter_named_actor_action_outcome_stays_legal() -> None:
    # The one exception to `RESERVED_VALUE_NAMES` (module docstring, and
    # `_check_reserved_params`'s docstring in resolve.py): a function body is
    # already forbidden from READING `actor`/`action`/`outcome` (the runtime
    # clears them before a hermetic call), so naming a parameter after one of
    # them is not a hijack — it is the prescribed fix for that hermeticity
    # error ("pass the value in as a parameter instead"). Regression pin:
    # without the exception the rule would reject `tests/test_functions.py`'s
    # `function lead(actor : Player) = score[actor]`.
    game = check_dsl(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { let x = f(1, 1, 1) }
  winner: highest score
}
function f(actor: Integer, action: Integer, outcome: Integer) = actor + action + outcome
""",
        "mini.cardlang",
    )
    fn = next(f for f in game.functions if f.name == "f")
    assert [p.name for p in fn.params] == ["actor", "action", "outcome"]


def test_move_type_parameter_named_actor_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 4
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { done : Integer = 0 }
  phase play { offer to 0 one of [ask] done := 1 }
  winner: highest done
}
move_type ask(actor : Player) { effect { done := 1 } }
""",
        "move-type parameter 'actor' is a reserved word",
    )


def test_rule_parameter_named_state_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 4
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0  leader : Player? = none }
  phase play {
    active_rules: [Foo(hearts)]
    legal_moves: [play_to_trick]
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
  }
  winner: highest score
}
rule Foo(state: Suit) {
  constrains: play_to_trick
  demands: cards in hand where card.suit is not state
  if_impossible: hand
}
""",
        "rule parameter 'state' is a reserved word",
    )


def test_let_name_named_outcome_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play {
    let outcome = 1
    score[0] := outcome
  }
  winner: highest score
}
""",
        "binder 'outcome' is a reserved word",
    )


def test_for_each_binder_named_actor_rejected() -> None:
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play {
    for each player actor: score[actor] := 1
  }
  winner: highest score
}
""",
        "binder 'actor' is a reserved word",
    )


def test_each_simultaneous_binder_named_empty_rejected() -> None:
    report_needle = "binder 'empty' is a reserved word"
    _rejects(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play {
    each empty simultaneously: score[actor] := 1
  }
  winner: highest score
}
""",
        report_needle,
    )


# --- acceptance pins ---------------------------------------------------


def test_is_empty_and_empty_count_stay_legal_ordinary_names() -> None:
    # A reserved word as a SUBSTRING of a longer identifier is unaffected —
    # only the exact bare spelling is reserved.
    game = check_dsl(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0  is_empty : Boolean = false  empty_count : Integer = 0 }
  phase play { score[0] := empty_count }
  winner: highest score
}
""",
        "mini.cardlang",
    )
    names = {d.name for d in game.state.decls} if game.state else set()
    assert {"is_empty", "empty_count"} <= names


def test_card_and_player_shadowing_stays_legal() -> None:
    # decisions.md's "legitimately shadow ACROSS levels" carve-out
    # (`_check_duplicate_names`'s docstring): a `let` literally named `card`
    # is a deliberate, established idiom, not reserved.
    game = check_dsl(
        """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  zones { hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play {
    let card = 3
    score[0] := card
  }
  winner: highest score
}
""",
        "mini.cardlang",
    )
    stmt = game.phases[0].items[-2]
    assert isinstance(stmt, n.LetStmt) and stmt.name == "card"


@pytest.mark.parametrize("path", sorted(GAMES.glob("*.cardlang")), ids=lambda p: p.stem)
def test_corpus_declares_no_reserved_names(path: Path) -> None:
    # The corpus uses none of RESERVED_VALUE_NAMES as a declaration — this
    # wall changes no game's resolve outcome.
    check_source(path)
