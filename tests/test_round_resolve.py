from cardlang.pipeline import check_dsl
from tests.test_round_parse import SRC


def test_round_resolves_clean():
    game = check_dsl(SRC, "g.cardlang")
    assert game.name == "G"


def test_round_unknown_zone_errors():
    bad = SRC.replace("source hand", "source nope")
    try:
        check_dsl(bad, "g.cardlang")
        assert False
    except Exception as exc:
        assert "nope" in str(exc)
