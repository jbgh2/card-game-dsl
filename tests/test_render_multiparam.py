from cardlang.runtime.observe import render


def test_multiparam_renders_each_value() -> None:
    assert render(("ask", (1, "K"))) == "ask(1,K)"


def test_single_param_unchanged() -> None:
    assert render(("submit_bid", "hearts")) == "submit_bid(hearts)"


def test_nullary_unchanged() -> None:
    assert render(("pass", None)) == "pass"
