from cardlang.pipeline import check_dsl
from tests.test_round_parse import EARLY_SRC, SRC


def test_round_resolves_clean() -> None:
    game = check_dsl(SRC, "g.cardlang")
    assert game.name == "G"


def test_round_early_termination_resolves_clean() -> None:
    game = check_dsl(EARLY_SRC, "g.cardlang")
    assert game.name == "G"


def test_round_unknown_early_predicate_errors() -> None:
    bad = EARLY_SRC.replace("early on_play_of_tochoo", "early nope_predicate")
    try:
        check_dsl(bad, "g.cardlang")
        assert False
    except Exception as exc:
        assert "nope_predicate" in str(exc)


def test_round_outcome_fn_rejected_as_early_predicate() -> None:
    # An outcome callback (signature (played, led_suit, trump, rank) -> Player) is
    # not a valid early predicate ((card, led_suit) -> Boolean). The namespaces are
    # separate, so misusing one for the other is caught at resolve, not at runtime.
    bad = EARLY_SRC.replace("early on_play_of_tochoo", "early highest_of_led_suit")
    try:
        check_dsl(bad, "g.cardlang")
        assert False
    except Exception as exc:
        assert "highest_of_led_suit" in str(exc)


def test_round_unknown_zone_errors() -> None:
    bad = SRC.replace("source hand", "source nope")
    try:
        check_dsl(bad, "g.cardlang")
        assert False
    except Exception as exc:
        assert "nope" in str(exc)
