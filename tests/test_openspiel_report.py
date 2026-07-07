"""The playtest report (cardlang.openspiel.report) — shape smoke test."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspiel")

import cardlang.openspiel.game  # noqa: E402,F401  (registers on import)


def test_playtest_report_shape() -> None:
    from cardlang.openspiel.report import playtest_report

    rep = playtest_report("cardlang_getaway", num_games=2, seed=1)
    assert rep["num_games"] == 2
    assert rep["mean_length"] > 0 and rep["mean_branching"] >= 1
    assert len(rep["mean_returns"]) == 4
    assert sum(rep["best_seat_counts"]) == 2
