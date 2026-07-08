"""Resolve-time acceptance of the extended move-parameter domains
(`Rank`/`Player`/multi-parameter) plus the totality rejections that keep the
domain set closed (docs/decisions.md "Surface totality"): a `Card` parameter
combined with any other parameter, a bounded-`Integer` parameter (deferred),
and any other unsupported domain string. `_check_move_params`
(cardlang/resolve.py) is the shared gate called from both the `offer`
statement and the auction `round offering` vocabulary.
"""

from __future__ import annotations

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _diags(
    move_src: str,
    offer_or_round: str,
    zones: str = "zones { hand[player] : Hand<player> }",
) -> list[str]:
    src = (
        "game G {\n"
        "  players: 4\n  max_length: 50\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        f"  {zones}\n"
        "  state { done : Integer = 0 }\n"
        f"  phase play {{ {offer_or_round} done := 1 }}\n"
        "  winner: highest done\n}\n"
        f"{move_src}\n"
    )
    # `check_source` dispatches on a real path on disk (single arg, reads the
    # file); it has no (text, source_name) form and returns the resolved
    # `Game`, not a diagnostics collection — it raises `DiagnosticError` on any
    # stage's failure. `check_dsl(text, source_name)` is the actual two-arg
    # entry point for in-memory source (mirrors cardlang.pipeline.check_source
    # dispatch for a `.cardlang` suffix).
    try:
        check_dsl(src, "g.cardlang")
    except DiagnosticError as exc:
        # `_raise_if_errors` (resolve.py) raises the first diagnostic and, only
        # when there is more than one, attaches the rest as a formatted note —
        # collect both so a message isn't missed if it isn't bag.items[0].
        return [exc.diagnostic.message, *getattr(exc, "__notes__", [])]
    return []


def test_player_rank_offer_accepted() -> None:
    diags = _diags(
        "move_type ask(target : Player, rank : Rank) { when: target != actor effect { done := 1 } }",
        "offer to 0 one of [ask]",
    )
    assert not any("parameter" in d for d in diags), diags


def test_integer_parameter_rejected_as_deferred() -> None:
    diags = _diags(
        "move_type bet(amount : Integer) { effect { done := 1 } }",
        "offer to 0 one of [bet]",
    )
    assert any("Integer" in d and "defer" in d.lower() for d in diags), diags


def test_card_with_other_param_rejected() -> None:
    diags = _diags(
        "move_type play(c : Card, s : Suit) { effect { done := 1 } }",
        "offer to 0 one of [play]",
    )
    assert any("Card" in d and "combin" in d.lower() for d in diags), diags


def test_optional_rank_parameter_rejected() -> None:
    # `Rank?` parses fine (payload types are generically optional-able), but
    # `enumerate_domain` only appends the `None` candidate in the `Suit`
    # branch — a nullable Rank/Player domain has no enumeration, so accepting
    # it here would be accepted-but-silently-ignored at runtime. Reject it
    # exactly like any other unsupported domain string, rather than stripping
    # the `?` and letting it through as bare `Rank`.
    diags = _diags(
        "move_type peek(r : Rank?) { effect { done := 1 } }",
        "offer to 0 one of [peek]",
    )
    assert any("Rank?" in d for d in diags), diags


def test_player_rank_round_offering_accepted() -> None:
    # The interface requires acceptance under *either* enumeration site; the
    # auction `round offering` vocabulary is the other one (`offer` above).
    diags = _diags(
        "move_type ask(target : Player, rank : Rank) { when: target != actor effect { done := 1 } }",
        "round offering [ask] from 0 over all players until done == 1",
    )
    assert not any("parameter" in d for d in diags), diags


# --- the two Card-vocabulary guards apply to `offer` too, not just `round` --
# `offer` used to reject every parameterized move outright, so a single Card
# param via `offer` (accepted as of this change, "as today") never reached
# these checks before; both are load-bearing (a missing `hand[player]` zone
# crashes `param_domain` at runtime; two Card-parameterized moves in one
# vocabulary collapse onto the same OpenSpiel action id, per
# cardlang/openspiel/encoding.py's handling of `n.Offer`).


def test_offer_of_a_card_param_without_a_hand_zone_rejected() -> None:
    diags = _diags(
        "move_type play_card(c : Card) { effect { done := 1 } }",
        "offer to 0 one of [play_card]",
        zones="zones { stash[player] : Hand<player> }",
    )
    assert any("hand[player]" in d for d in diags), diags


def test_offer_of_two_card_parameterized_moves_rejected() -> None:
    diags = _diags(
        "move_type play_one(c : Card) { effect { done := 1 } }\n"
        "move_type play_two(c : Card) { effect { done := 1 } }",
        "offer to 0 one of [play_one, play_two]",
    )
    assert any("more than one Card-parameterized move" in d for d in diags), diags
