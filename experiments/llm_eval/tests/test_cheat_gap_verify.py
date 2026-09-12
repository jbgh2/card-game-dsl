"""`verify_cheat_gap`'s arithmetic, against a tiny hand-written fixture — and
its purity, against an `ast` scrape.

No engine, no sampler, no sibling module of this package: every number in the
report is computed from two lists of plain dicts, which is what the hand
fixtures below stand in for.
"""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path
from typing import Any

import pytest

from .. import verify_cheat_gap as vcg


def _window(
    matchup: str = "m",
    seed: int = 0,
    step: int = 0,
    observer_agent: str = "rule",
    action: str = "call_cheat",
    lie: bool = True,
    r1_widened: bool = False,
    p_lie: float = 0.5,
) -> dict[str, Any]:
    return {
        "matchup": matchup,
        "seed": seed,
        "step": step,
        "observer_agent": observer_agent,
        "action": action,
        "lie": lie,
        "r1_widened": r1_widened,
        "p_lie": p_lie,
    }


# --- arithmetic on a known fixture --------------------------------------------


def test_gap_stat_on_known_counts() -> None:
    """4 windows, 3 lies, mean p_lie=0.5 -> rate=0.75, gap=+25pp."""
    rows = [
        _window(seed=1, step=0, lie=True, p_lie=0.5),
        _window(seed=1, step=1, lie=True, p_lie=0.5),
        _window(seed=2, step=0, lie=True, p_lie=0.5),
        _window(seed=2, step=1, lie=False, p_lie=0.5),
    ]
    assert vcg.gap_stat(rows) == pytest.approx(25.0)


def test_gap_stat_matches_by_hand() -> None:
    rows = [
        _window(seed=1, step=0, lie=True, p_lie=0.5),
        _window(seed=1, step=1, lie=True, p_lie=0.5),
        _window(seed=2, step=0, lie=True, p_lie=0.5),
        _window(seed=2, step=1, lie=False, p_lie=0.5),
    ]
    rate = 3 / 4
    mean_r = 0.5
    expected = (rate - mean_r) * 100.0
    got = vcg.gap_stat(rows)
    assert got is not None
    assert abs(got - expected) < 1e-9


def test_rate_str_and_rate_are_null_over_zero_denominator() -> None:
    assert vcg._rate_str(0, 0) == "0 / 0 = null"
    assert vcg._rate(0, 0) is None
    assert vcg._rate(3, 4) == 0.75


def test_gap_stat_is_none_with_no_windows() -> None:
    assert vcg.gap_stat([]) is None


def test_bucket_selects_exactly_the_matching_cell() -> None:
    rows = [
        _window(matchup="a", observer_agent="rule", action="call_cheat", r1_widened=True),
        _window(matchup="a", observer_agent="rule", action="allow", r1_widened=True),
        _window(matchup="a", observer_agent="rule", action="call_cheat", r1_widened=False),
        _window(matchup="b", observer_agent="rule", action="call_cheat", r1_widened=True),
        _window(matchup="a", observer_agent="llm", action="call_cheat", r1_widened=True),
    ]
    got = vcg.bucket(rows, "a", "rule", "fires", "challenged")
    assert got == [rows[0]]
    got_all = vcg.bucket(rows, "a", "rule", "all", "challenged")
    assert got_all == [rows[0], rows[2]]
    # rows[1] is the only "allow" row, but it is an R1-fire, so the
    # abstains/allowed cell is empty.
    got_abstain = vcg.bucket(rows, "a", "rule", "abstains", "allowed")
    assert got_abstain == []


def test_residual_summary_on_a_known_fixture() -> None:
    rows = [
        _window(lie=True, p_lie=1.0),
        _window(lie=False, p_lie=0.0),
    ]
    summary = vcg.residual_summary(rows)
    assert summary is not None
    mean, sd = summary
    assert abs(mean - 0.0) < 1e-9
    assert abs(sd - 0.0) < 1e-9


# --- bootstrap: the interval contains the point estimate ----------------------


def test_bootstrap_interval_contains_the_point_estimate() -> None:
    rows = []
    for seed in range(20):
        for step in range(3):
            rows.append(
                _window(seed=seed, step=step, lie=(step != 2), p_lie=0.4)
            )
    point = vcg.gap_stat(rows)
    ci = vcg.bootstrap_gap(rows, n_resamples=500, seed=0)
    assert point is not None and ci is not None
    lo, hi = ci
    assert lo <= point <= hi


def test_bootstrap_is_none_with_no_windows() -> None:
    assert vcg.bootstrap_gap([]) is None


# --- the sign test matches a hand-computed case -------------------------------


def test_sign_test_matches_a_hand_computed_case() -> None:
    # 5 up, 1 down: exact two-sided binomial tail at k=1, n=6.
    pairs = [(0.0, 1.0)] * 5 + [(1.0, 0.0)] * 1
    up, down, tied, p = vcg.sign_test(pairs)
    assert (up, down, tied) == (5, 1, 0)
    expected = min(1.0, 2 * sum(math.comb(6, i) for i in range(2)) / (2**6))
    assert abs(p - expected) < 1e-12


def test_sign_test_is_one_with_no_untied_pairs() -> None:
    pairs = [(1.0, 1.0), (2.0, 2.0)]
    up, down, tied, p = vcg.sign_test(pairs)
    assert (up, down, tied, p) == (0, 0, 2, 1.0)


def test_paired_seed_comparison_pairs_by_shared_seed_only() -> None:
    a = [_window(seed=1, step=0, lie=True, p_lie=0.0), _window(seed=2, step=0, lie=False, p_lie=0.0)]
    b = [_window(seed=1, step=0, lie=False, p_lie=0.0), _window(seed=3, step=0, lie=True, p_lie=0.0)]
    result = vcg.paired_seed_comparison(a, b)
    assert result["shared_seeds"] == 1
    assert len(result["pairs"]) == 1


# --- report() runs over a tiny end-to-end fixture -----------------------------


def test_report_runs_and_names_the_null_control() -> None:
    windows = [
        {"matchup": "m", "seed": s, "step": 0} for s in range(3)
    ] + [
        {"matchup": "m", "seed": s, "step": 1} for s in range(3)
    ]
    posterior = [
        _window(matchup="m", seed=s, step=0, observer_agent="rule",
                action="call_cheat", lie=(s % 2 == 0), r1_widened=False, p_lie=0.3)
        for s in range(3)
    ]
    lines = vcg.report(windows, posterior)
    text = "\n".join(lines)
    assert "m" in text
    assert "NULL CONTROL" in text
    assert "rule" in text


# --- purity: stdlib only, nothing from the engine or the sampler -------------


def test_verify_cheat_gap_imports_nothing_of_this_package_or_the_engine() -> None:
    source = Path(inspect.getsourcefile(vcg) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    relative: set[str] = set()
    absolute: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level >= 1:
                if node.module:
                    relative.add(node.module.split(".")[0])
                else:
                    relative.update(alias.name for alias in node.names)
            elif node.module:
                absolute.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            absolute.update(alias.name.split(".")[0] for alias in node.names)
    assert relative == set(), (
        f"verify_cheat_gap imports sibling module(s) {relative} — it must "
        f"share no code with either producer"
    )
    forbidden = {"cardlang", "pyspiel", "gap_sampler", "gap_replay", "gap_windows", "gap_posterior"}
    assert not (absolute & forbidden), f"verify_cheat_gap reaches {absolute & forbidden}"
