"""`gap_windows` and `gap_posterior`, against a generated rule-agent
transcript.

No archive is committed for this study yet, so one small transcript is
generated ONCE per test session with `referee.play_game` over four
`RuleAgent` seats — enough to exercise real challenge windows, including ones
the widened provable-lie criterion fires on, without depending on any
external data. Every test below reads that one archive rather than
generating its own: `enumerate_windows` replays every game to recompute its
facts, so a per-test archive would pay that cost once per test rather than
once per file.
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from .. import gap_posterior, gap_sampler, gap_windows, metrics
from ..agents import Agent, RuleAgent
from ..infostate import parse
from ..referee import GameRecord, ProvenanceError, load_game, play_game

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

REPO_ROOT = Path(__file__).resolve().parents[3]
CHEAT_PATH = str(REPO_ROOT / "docs" / "games" / "cheat.cardlang")

#: How many of the shallowest windows a sampler-touching test uses. Shallow
#: windows are cheap (`gap_sampler`'s own docstring: acceptance is ~1.0 at
#: shallow depth and falls with the line length), so this bounds every such
#: test's cost regardless of how deep the generated games ran.
SHALLOW = 6


@pytest.fixture(scope="module")
def game() -> Any:
    return load_game("cardlang_cheat")


def _seats(seed: int, bluff_prob: float = 0.4) -> dict[int, Agent]:
    return {
        i: RuleAgent(seed=seed * 4 + i, challenge_prob=0.1, bluff_prob=bluff_prob)
        for i in range(4)
    }


def _play(
    game: Any, seed: int, matchup: str, game_index: int, max_decisions: int = 110
) -> GameRecord:
    return play_game(
        game, _seats(seed), seed=seed, matchup=matchup, game_index=game_index,
        max_decisions=max_decisions,
    )


def _write(path: Path, records: list[GameRecord]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory, game: Any) -> Path:
    """One 20-game transcript, generated once for the whole module."""
    root = tmp_path_factory.mktemp("cg_archive")
    records = [_play(game, seed, "cg", i, max_decisions=110) for i, seed in enumerate(range(20))]
    _write(root / "cg.jsonl", records)
    return root


@pytest.fixture(scope="module")
def windows(archive: Path) -> list[gap_windows.WindowRecord]:
    out = gap_windows.enumerate_windows(archive, None)
    assert out, "no challenge windows were generated at all — widen the fixture"
    return out


@pytest.fixture(scope="module")
def windows_dicts(windows: list[gap_windows.WindowRecord]) -> list[dict[str, Any]]:
    return [asdict(w) for w in windows]


# --- enumeration --------------------------------------------------------------


def test_window_facts_match_reconstructed_plays(archive: Path, windows: list[Any]) -> None:
    """`lie`, `forced_lie` and `window_position` agree with an INDEPENDENT
    grouping of the same transcript by `metrics.reconstruct_plays` — the check
    that `gap_windows` threads windows back to the right play."""
    records = list(metrics.iter_jsonl(str(archive / "cg.jsonl")))

    by_seed: dict[int, list[Any]] = {}
    for w in windows:
        by_seed.setdefault(w.seed, []).append(w)

    for record in records:
        plays = metrics.reconstruct_plays(record["decisions"])
        expected = [
            (play.lied, play.forced, position)
            for play in plays
            for position in range(len(play.windows))
        ]
        got = sorted(by_seed.get(record["seed"], []), key=lambda w: w.step)
        assert len(got) == len(expected)
        for w, (lied, forced, position) in zip(got, expected, strict=True):
            assert w.lie == lied
            assert w.forced_lie == forced
            assert w.window_position == position


def test_window_position_never_exceeds_two(windows: list[Any]) -> None:
    """Four players, one claimant: at most three responders, positions 0-2."""
    assert all(0 <= w.window_position <= 2 for w in windows)


def test_r1_hand_only_implies_r1_widened(windows: list[Any]) -> None:
    """The widened criterion counts everything the narrow one does, plus the
    public challenge record, so it can only fire MORE often."""
    for w in windows:
        if w.r1_hand_only:
            assert w.r1_widened, (
                f"seed={w.seed} step={w.step}: r1_hand_only fired but r1_widened "
                f"did not, which is a widening that narrowed"
            )
    assert any(w.r1_widened for w in windows), (
        "no window fired R1 at all — the sweep below needs at least one"
    )


def test_every_infostate_parses_and_names_the_claimant(windows: list[Any]) -> None:
    for w in windows:
        info = parse(w.infostate)
        assert info.claimant == w.claimant
        assert info.player == w.observer


def test_refuses_a_record_with_no_game_digest(tmp_path: Path, game: Any) -> None:
    record = _play(game, seed=1, matchup="nodigest", game_index=0, max_decisions=40)
    payload = record.as_dict()
    del payload["game_digest"]
    path = tmp_path / "nodigest.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="nodigest"):
        gap_windows.enumerate_windows(tmp_path, None)


def test_refuses_a_record_with_a_mismatched_digest(tmp_path: Path, game: Any) -> None:
    record = _play(game, seed=2, matchup="baddigest", game_index=0, max_decisions=40)
    payload = record.as_dict()
    wrong = "0" * 64
    assert wrong != payload["game_digest"]
    payload["game_digest"] = wrong
    path = tmp_path / "baddigest.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="baddigest"):
        gap_windows.enumerate_windows(tmp_path, None)


# --- purity: gap_windows / gap_posterior may only reach each other's half ----


def _import_names(module: Any) -> tuple[set[str], set[str]]:
    """`(relative sibling modules, absolute top-level modules)` imported
    anywhere in `module`'s source — deferred imports included, since a
    restriction checked only at module level would miss one hidden in a
    function body."""
    source = Path(inspect.getsourcefile(module) or "").read_text(encoding="utf-8")
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
    return relative, absolute


def test_gap_windows_reaches_only_referee_infostate_metrics() -> None:
    relative, absolute = _import_names(gap_windows)
    assert relative <= {"referee", "infostate", "metrics"}, (
        f"gap_windows imports {relative - {'referee', 'infostate', 'metrics'}} "
        f"beyond its declared half"
    )
    assert "cardlang" not in absolute and "pyspiel" not in absolute


def test_gap_posterior_reaches_only_gap_sampler_gap_replay() -> None:
    relative, absolute = _import_names(gap_posterior)
    assert relative <= {"gap_sampler", "gap_replay"}, (
        f"gap_posterior imports {relative - {'gap_sampler', 'gap_replay'}} "
        f"beyond its declared half"
    )


# --- posterior ----------------------------------------------------------------


def _shallowest(windows_dicts: list[dict[str, Any]], n: int, only_fires: bool = False) -> list[dict[str, Any]]:
    pool = [w for w in windows_dicts if w["r1_widened"]] if only_fires else windows_dicts
    return sorted(pool, key=lambda w: (w["step"], w["seed"]))[:n]


def test_the_subsample_is_deterministic_for_a_fixed_seed(
    windows_dicts: list[dict[str, Any]]
) -> None:
    shallow = _shallowest(windows_dicts, 4 * SHALLOW)
    kwargs: dict[str, Any] = dict(
        per_cell=6, subsample_seed=42, ess_floor=20.0,
        min_proposals=200, max_proposals=800, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    first, log_a = gap_posterior.run(shallow, **kwargs)
    second, log_b = gap_posterior.run(shallow, **kwargs)
    assert first == second
    assert log_a == log_b
    assert first, "nothing was selected at all — the fixture has no windows"


def test_the_adaptive_budget_stops_at_the_floor_or_the_cap(
    windows_dicts: list[dict[str, Any]]
) -> None:
    shallow = _shallowest(windows_dicts, SHALLOW)

    # An easy floor: converges at (or before) min_proposals, honestly.
    easy, _ = gap_posterior.run(
        shallow, per_cell=10, subsample_seed=1, ess_floor=1.0,
        min_proposals=200, max_proposals=800, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    assert easy
    for r in easy:
        assert r["converged"] is True
        assert r["ess"] >= 1.0
        assert r["n_proposed"] <= 800

    # An impossible floor: never converges, capped at max_proposals, and the
    # record says so rather than reading as covered.
    hard, log = gap_posterior.run(
        shallow, per_cell=10, subsample_seed=1, ess_floor=1e9,
        min_proposals=200, max_proposals=400, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    for r in hard:
        assert r["converged"] is False
        assert r["n_proposed"] == 400
    assert any("NOT CONVERGED" in line for line in log)


def test_the_provable_subset_pin_holds_end_to_end(
    windows_dicts: list[dict[str, Any]]
) -> None:
    fires = _shallowest(windows_dicts, SHALLOW, only_fires=True)
    assert fires, "no R1-firing window was generated — widen the fixture"

    records, _ = gap_posterior.run(
        fires, per_cell=len(fires), subsample_seed=7, ess_floor=1.0,
        min_proposals=100, max_proposals=100, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    assert len(records) == len(fires)
    for r in records:
        assert r["p_lie"] == 1.0


def test_check_count_performs_replay_checks(windows_dicts: list[dict[str, Any]]) -> None:
    shallow = _shallowest(windows_dicts, 3)
    records, _ = gap_posterior.run(
        shallow, per_cell=10, subsample_seed=3, ess_floor=5.0,
        min_proposals=200, max_proposals=800, check_count=2,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    assert records
    assert sum(r["n_checked"] for r in records) > 0


def test_zero_acceptance_at_the_first_budget_escalates_rather_than_drops(
    monkeypatch: pytest.MonkeyPatch, windows_dicts: list[dict[str, Any]]
) -> None:
    """A budget that accepts nothing is the same signal as a low ESS — too
    small for this depth — and gets the same answer. Only the cap drops."""
    shallow = _shallowest(windows_dicts, 1)
    real = gap_sampler.estimate
    seen: list[int] = []

    def flaky(infostate: str, *, samples: int, **kw: Any) -> Any:
        seen.append(samples)
        if samples < 800:
            raise ValueError("no consistent world (simulated)")
        return real(infostate, samples=samples, **kw)

    monkeypatch.setattr(gap_sampler, "estimate", flaky)
    records, log = gap_posterior.run(
        shallow, per_cell=1, subsample_seed=1, ess_floor=1.0,
        min_proposals=200, max_proposals=800, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    assert seen == [200, 400, 800], seen
    assert len(records) == 1 and records[0]["n_proposed"] == 800
    assert not any("DROPPED" in line for line in log)

    # The cap itself accepting nothing is the drop, and it is logged.
    seen.clear()
    records, log = gap_posterior.run(
        shallow, per_cell=1, subsample_seed=1, ess_floor=1.0,
        min_proposals=200, max_proposals=400, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None,
    )
    assert seen == [200, 400]
    assert records == []
    assert any("DROPPED" in line for line in log)


def test_max_depth_bounds_eligibility(windows_dicts: list[dict[str, Any]]) -> None:
    depths = sorted({int(w["depth"]) for w in windows_dicts})
    assert len(depths) >= 2, "the fixture has windows at one depth only"
    bound = depths[len(depths) // 2]
    records, log = gap_posterior.run(
        windows_dicts, per_cell=10_000, subsample_seed=1, ess_floor=1.0,
        min_proposals=50, max_proposals=50, check_count=0,
        game_path=CHEAT_PATH, observer_agent=None, max_depth=bound,
    )
    assert records
    assert all(int(r["depth"]) <= bound for r in records)
    assert len(records) == sum(1 for w in windows_dicts if int(w["depth"]) <= bound)
    assert any(f"max_depth={bound}" in line for line in log)

