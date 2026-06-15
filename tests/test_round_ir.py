from typing import Any

from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from tests.test_round_parse import EARLY_SRC, SRC


def test_round_ir() -> None:
    ir: Any = emit(check_dsl(SRC, "g.cardlang"))
    items = ir["phases"][0]["items"]
    rnd = next(i for i in items if i["kind"] == "round")
    assert rnd["move_type"] == "play_to_trick"
    assert rnd["source_zone"] == "hand" and rnd["play_zone"] == "trick_pile"
    assert rnd["outcome_fn"] == "highest_trump_or_led_suit"
    assert rnd["trump"]["kind"] == "name"
    assert rnd["early_termination"] is None


def test_round_early_termination_ir() -> None:
    ir: Any = emit(check_dsl(EARLY_SRC, "g.cardlang"))
    items = ir["phases"][0]["items"]
    rnd = next(i for i in items if i["kind"] == "round")
    assert rnd["early_termination"] == "on_play_of_tochoo"
    assert rnd["trump"] is None
