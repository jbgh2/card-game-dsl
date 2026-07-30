"""The arm-delta report, and the statistics under it.

`fisher_exact` is the only piece of this harness that computes a number nobody
can eyeball. A p-value that is wrong by a factor of two still looks like a
p-value, and it would be quoted in a grant proposal — so it is checked against an
independent implementation over an exhaustively enumerated domain, not against a
handful of cases its author chose.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from experiments.llm_eval.compare import DERIVED, enrich, fisher_exact, main, wald_ci

# Every 2x2 table with each cell in 0..MAX. Closed and enumerable, so the
# differential covers the domain rather than sampling it.
MAX = 6
TABLES = [
    (a, b, c, d)
    for a in range(MAX + 1)
    for b in range(MAX + 1)
    for c in range(MAX + 1)
    for d in range(MAX + 1)
]


def test_the_table_domain_is_not_empty() -> None:
    """The differential below is parametrized off `TABLES`; an empty list would
    make it pass by covering nothing."""
    assert len(TABLES) == (MAX + 1) ** 4 == 2401


def test_fisher_matches_an_independent_implementation_exhaustively() -> None:
    """Differential against scipy over all 2401 small tables.

    scipy is a test-only dependency on purpose: shipping it would put the audit
    path behind an install, and hand-rolling it without a differential would put
    a grant number behind an unverified 20 lines. This gets both.
    """
    stats = pytest.importorskip(
        "scipy.stats", reason="the Fisher differential needs scipy"
    )
    worst = 0.0
    for a, b, c, d in TABLES:
        mine = fisher_exact(a, b, c, d)
        theirs = float(stats.fisher_exact([[a, b], [c, d]])[1])
        worst = max(worst, abs(mine - theirs))
        assert mine == pytest.approx(theirs, abs=1e-9), f"table {(a, b, c, d)}"
    # A comparison that never saw a non-trivial p-value would pass vacuously.
    assert worst < 1e-9


def test_fisher_reproduces_the_textbook_case() -> None:
    """Fisher's tea-tasting table, whose two-sided p is 0.4857 in every
    textbook. Pins the orientation as well as the arithmetic: a transposed
    implementation still agrees with scipy, because scipy would be handed the
    same transposition."""
    assert fisher_exact(3, 1, 1, 3) == pytest.approx(0.4857, abs=5e-5)


def test_fisher_is_symmetric_under_swapping_the_arms() -> None:
    """Which run is called `control` cannot change the p-value."""
    for a, b, c, d in TABLES[::37]:
        assert fisher_exact(a, b, c, d) == pytest.approx(fisher_exact(c, d, a, b))


@pytest.mark.parametrize(
    "table", [(0, 0, 0, 0), (5, 3, 0, 0), (0, 0, 2, 7), (4, 0, 6, 0), (0, 4, 0, 6)]
)
def test_fisher_returns_one_for_a_degenerate_margin(table: tuple[int, ...]) -> None:
    """An empty row or column carries no information. Returning 1.0 rather than
    raising matters because a rate with no opportunities is normal in a short
    run — `improbable_faced` can legitimately be 0."""
    assert fisher_exact(*table) == 1.0


def test_a_clean_separation_is_significant_and_a_tie_is_not() -> None:
    """Non-vacuity for the tests above: the function must be able to say both
    things."""
    assert fisher_exact(20, 0, 0, 20) < 1e-9
    assert fisher_exact(10, 10, 10, 10) == pytest.approx(1.0)


@pytest.mark.parametrize("den", [0, 1, 10, 1000])
def test_wald_ci_brackets_the_rate_and_stays_in_range(den: int) -> None:
    for num in range(den + 1):
        lo, hi = wald_ci(num, den)
        assert 0.0 <= lo <= hi <= 1.0
        if den:
            assert lo <= num / den <= hi


def test_wald_ci_narrows_with_the_denominator() -> None:
    """The reason it is printed at all: a rate over 20 windows and a rate over
    600 must not read the same."""
    narrow = wald_ci(300, 600)
    wide = wald_ci(10, 20)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_enrich_derives_wrong_accusations_from_the_recorded_counts() -> None:
    """The per-game figure that explained why better lie detection still lost:
    a wrong call costs the whole pile."""
    c: Counter[str] = Counter({"challenges_made": 17, "challenges_correct": 5})
    assert enrich(c)["wrong_accusations"] == 12
    assert [key for _, key in DERIVED if key == "wrong_accusations"]


# --- end to end, on synthetic transcripts -----------------------------------


def _seat_record(seed: int, llm_name: str) -> dict[str, Any]:
    """The smallest record `verify.tally` accepts: one seat, no decisions. Enough
    to exercise seed reporting and agent selection, which is what the CLI adds
    over the pure functions."""
    return {
        "matchup": "x",
        "seed": seed,
        "game_index": seed,
        "terminal": True,
        "truncated": False,
        "returns": [1.0, -1.0],
        "seats": {"0": llm_name, "1": "rule"},
        "history": [],
        "decisions": [],
        "usage": {},
        "num_decisions": 0,
        "wall_seconds": 0.0,
    }


def _write(root: Path, name: str, records: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )


def test_compare_reports_both_matchups(tmp_path: Path, capsys: Any) -> None:
    _write(tmp_path, "ctl", [_seat_record(s, "llm_x") for s in (0, 1, 2)])
    _write(tmp_path, "arm", [_seat_record(s, "llm_x") for s in (0, 1, 2)])
    assert main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"]) == 0
    out = capsys.readouterr().out
    assert "agent      llm_x" in out
    assert "seeds=[0, 1, 2]" in out
    assert "SEED SETS DIFFER" not in out


def test_compare_warns_loudly_when_the_arms_are_different_games(
    tmp_path: Path, capsys: Any
) -> None:
    """The comparison's central assumption is one this module cannot enforce —
    it lives in `config.yaml`. Unenforceable and unstated would make every delta
    quietly uninterpretable, so it is stated from the data."""
    _write(tmp_path, "ctl", [_seat_record(s, "llm_x") for s in (0, 1, 2)])
    _write(tmp_path, "arm", [_seat_record(s, "llm_x") for s in (5, 6, 7)])
    main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])
    assert "SEED SETS DIFFER" in capsys.readouterr().out


def test_compare_refuses_an_ambiguous_agent(tmp_path: Path) -> None:
    """Two different LLM labels cannot be compared by guessing which pairs with
    which — that would silently compare Haiku's control against Sonnet's arm."""
    _write(tmp_path, "ctl", [_seat_record(0, "llm_cheap")])
    _write(tmp_path, "arm", [_seat_record(0, "llm_mid")])
    with pytest.raises(SystemExit, match="cannot pick an agent automatically"):
        main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])


def test_compare_refuses_a_missing_matchup(tmp_path: Path) -> None:
    _write(tmp_path, "ctl", [_seat_record(0, "llm_x")])
    with pytest.raises(SystemExit, match="no transcript for matchup 'nope'"):
        main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "nope"])


# --- the pre-registered endpoint --------------------------------------------


def test_the_primary_endpoint_is_one_of_the_reported_rates() -> None:
    """A `PRIMARY_ENDPOINT` naming a rate that is never computed would silently
    demote every rate to exploratory, and the `*` would never appear."""
    from experiments.llm_eval.compare import PRIMARY_ENDPOINT
    from experiments.llm_eval.verify import RATES

    assert PRIMARY_ENDPOINT in {name for name, _, _ in RATES}


def test_a_hugely_significant_exploratory_rate_does_not_get_a_star(
    tmp_path: Path, capsys: Any
) -> None:
    """`*` is reserved for the pre-registered endpoint, however small another
    rate's p-value is.

    Constructed so `win_rate` separates perfectly (0/10 against 10/10, p ~ 1e-6)
    while `challenge_rate` — the endpoint — has no opportunities at all and is
    skipped. If the marking were driven by p alone, this would print a `*`.
    """
    lose = [{**_seat_record(s, "llm_x"), "returns": [-1.0, 1.0]} for s in range(10)]
    win = [{**_seat_record(s, "llm_x"), "returns": [1.0, -1.0]} for s in range(10)]
    _write(tmp_path, "ctl", lose)
    _write(tmp_path, "arm", win)
    main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])
    out = capsys.readouterr().out
    rows = [ln for ln in out.splitlines() if ln.startswith("win_rate")]
    assert len(rows) == 1, out
    assert rows[0].rstrip().endswith("~"), f"exploratory rate not marked `~`: {rows[0]}"
    assert not rows[0].rstrip().endswith("*")
    assert "exploratory, p <" in out, "the legend explaining `~` is missing"
    assert "a hypothesis, not a result" in out


def test_the_exploratory_threshold_is_bonferroni_over_the_reported_rates() -> None:
    """Derived from `RATES`, not written as a literal: adding a rate must tighten
    the threshold automatically, or the correction silently decays as the report
    grows."""
    from experiments.llm_eval.compare import ALPHA_EXPL
    from experiments.llm_eval.verify import RATES

    assert ALPHA_EXPL == pytest.approx(0.05 / len(RATES))
    assert ALPHA_EXPL < 0.05, "the correction is not correcting anything"


def test_a_small_run_warns_that_pooled_p_values_are_optimistic(
    tmp_path: Path, capsys: Any
) -> None:
    """A `*` on a one-game row and a `*` on a ten-game row look identical, and the
    p-values behind them are not comparable: decisions within a game share a hand,
    a pile and a claim cycle, so the effective N is the game count."""
    from experiments.llm_eval.compare import CLUSTER_WARN_GAMES

    few = CLUSTER_WARN_GAMES - 1
    _write(tmp_path, "ctl", [_seat_record(s, "llm_x") for s in range(few)])
    _write(tmp_path, "arm", [_seat_record(s, "llm_x") for s in range(few)])
    main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])
    out = capsys.readouterr().out
    assert "POOLED p-VALUES ARE OPTIMISTIC" in out
    assert f"control {few}, arm {few}" in out


def test_a_large_enough_run_does_not_warn(tmp_path: Path, capsys: Any) -> None:
    """Non-vacuity: the warning must be capable of staying silent, or it is
    decoration rather than a signal."""
    from experiments.llm_eval.compare import CLUSTER_WARN_GAMES

    enough = CLUSTER_WARN_GAMES
    _write(tmp_path, "ctl", [_seat_record(s, "llm_x") for s in range(enough)])
    _write(tmp_path, "arm", [_seat_record(s, "llm_x") for s in range(enough)])
    main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])
    assert "POOLED p-VALUES ARE OPTIMISTIC" not in capsys.readouterr().out


def test_the_warning_fires_when_only_ONE_arm_is_small(
    tmp_path: Path, capsys: Any
) -> None:
    """The real case: a 10-game control against a 1-game arm. Keyed on the
    SMALLER of the two, since that is what bounds the evidence.

    Deliberately WITHOUT `--common-seeds`. With it, both arms are restricted to
    the shared seed and end up at one game each, so `min` and `max` agree and the
    test cannot tell them apart — which is how it first shipped, and a plant
    keying the warning on `max` passed it.
    """
    _write(tmp_path, "ctl", [_seat_record(s, "llm_x") for s in range(10)])
    _write(tmp_path, "arm", [_seat_record(0, "llm_x")])
    main(["--dir", str(tmp_path), "--control", "ctl", "--arm", "arm"])
    out = capsys.readouterr().out
    assert "POOLED p-VALUES ARE OPTIMISTIC" in out
    assert "control 10, arm 1" in out, "the counts must be reported, not just the flag"
