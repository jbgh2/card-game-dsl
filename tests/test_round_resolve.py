import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from tests.test_round_parse import EARLY_SRC, SRC


def test_round_resolves_clean() -> None:
    game = check_dsl(SRC, "g.cardlang")
    assert game.name == "G"


def test_round_early_termination_resolves_clean() -> None:
    game = check_dsl(EARLY_SRC, "g.cardlang")
    assert game.name == "G"


def test_round_unknown_early_predicate_errors() -> None:
    bad = EARLY_SRC.replace("early on_play_off_led_suit", "early nope_predicate")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(bad, "g.cardlang")
    assert "nope_predicate" in str(ei.value)


def test_round_winner_fn_rejected_as_early_predicate() -> None:
    # A winner function (signature (played, led_suit, trump, rank) -> Player) is
    # not a valid early predicate ((card, led_suit) -> Boolean). The namespaces are
    # separate, so misusing one for the other is caught at resolve, not at runtime.
    bad = EARLY_SRC.replace("early on_play_off_led_suit", "early highest_of_led_suit")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(bad, "g.cardlang")
    assert "highest_of_led_suit" in str(ei.value)


def test_early_predicate_rejected_as_winner_fn() -> None:
    """The converse direction: an early predicate ((card, led_suit) -> Boolean)
    is not a valid trick winner function. Both directions of the partition are guarded,
    which is why the `early` set sits deliberately outside PRIMITIVE_VALUE_NAMES
    even though the runtime dispatches both through `value_function`.

    red under: add `on_play_off_led_suit` to PRIMITIVE_TRICK_WINNERS
    (cardlang/builtins/functions.py) — the tempting but wrong resolution of the
    early/winner asymmetry, which would also make it a legal bare NameRef.
    """
    bad = EARLY_SRC.replace("winner highest_of_led_suit", "winner on_play_off_led_suit")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(bad, "g.cardlang")
    assert "on_play_off_led_suit" in str(ei.value)


def test_round_unknown_zone_errors() -> None:
    bad = SRC.replace("source hand", "source nope")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(bad, "g.cardlang")
    assert "nope" in str(ei.value)
