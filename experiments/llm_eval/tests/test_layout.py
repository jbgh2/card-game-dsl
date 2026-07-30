"""Per-run output directories.

The defect these exist for is not hypothetical. `summary.json` used to live at the
top of `results/`, and every invocation overwrote the last one — so after a
twelve-invocation session, eleven runs' derived numbers were gone and the cost
accounting had to be rebuilt by summing transcripts by hand.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from experiments.llm_eval import layout
from experiments.llm_eval.run_eval import main

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

FAKE_MODEL: dict[str, Any] = {
    "kind": "fake",
    "model": "fake",
    "replies": ['{"action": 0, "reasoning": "x"}'],
}


def _config_file(tmp_path: Path, **matchup: Any) -> Path:
    import yaml

    spec = {
        "game": "cardlang_cheat",
        "max_decisions": 200,
        "results_dir": str(tmp_path),
        "models": {"m": FAKE_MODEL},
        "matchups": [
            {
                "name": "offline",
                "n": 1,
                "rotate": True,
                "agents": [{"kind": "rule"}] + [{"kind": "random"}] * 3,
                **matchup,
            }
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


# --- the naming property ----------------------------------------------------


def test_stamp_sorts_chronologically() -> None:
    """Lexicographic order IS chronological order, which is what makes
    `latest_run` correct without stat-ing anything. mtimes do not survive a copy
    or a fresh checkout; the name does."""
    base = datetime(2026, 7, 29, 15, 40, 12, tzinfo=timezone.utc)
    names = [
        layout.stamp(base + timedelta(seconds=s))
        for s in (0, 1, 59, 60, 3600, 86400, 86400 * 40)
    ]
    assert names == sorted(names), names
    # Zero-padded fixed width is the reason it holds; a %-d month would not.
    assert layout.stamp(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)) == (
        "2026-01-02T03-04-05Z"
    )


def test_stamp_is_utc_regardless_of_the_local_zone() -> None:
    """Two machines in different zones must not produce names that interleave
    wrongly when their runs are compared."""
    moment = datetime(2026, 7, 29, 23, 30, 0, tzinfo=timezone(timedelta(hours=10)))
    assert layout.stamp(moment) == "2026-07-29T13-30-00Z"


def test_two_runs_in_the_same_second_get_separate_directories(tmp_path: Path) -> None:
    """Sharing a directory would interleave two invocations' transcripts, which
    reads as one run with twice the data rather than as an error."""
    fixed = datetime(2026, 7, 29, 15, 40, 12, tzinfo=timezone.utc)
    first = layout.new_run_dir(tmp_path, fixed)
    second = layout.new_run_dir(tmp_path, fixed)
    third = layout.new_run_dir(tmp_path, fixed)
    assert first != second != third
    assert len({first, second, third}) == 3
    assert len(layout.list_runs(tmp_path)) == 3


def test_list_runs_is_empty_before_any_run(tmp_path: Path) -> None:
    assert layout.list_runs(tmp_path) == []
    assert layout.latest_run(tmp_path) is None


def test_latest_run_is_the_newest_by_name(tmp_path: Path) -> None:
    base = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
    made = [layout.new_run_dir(tmp_path, base + timedelta(hours=h)) for h in (0, 5, 2)]
    assert layout.latest_run(tmp_path) == made[1]


def test_list_runs_ignores_stray_files(tmp_path: Path) -> None:
    """A file dropped in `runs/` must not be reported as a run."""
    layout.new_run_dir(tmp_path, datetime(2026, 7, 29, tzinfo=timezone.utc))
    (tmp_path / layout.RUNS / "notes.txt").write_text("x", encoding="utf-8")
    assert [p.name for p in layout.list_runs(tmp_path)] == ["2026-07-29T00-00-00Z"]


# --- what the runner actually writes ----------------------------------------


def test_a_run_writes_its_summary_inside_its_own_directory(tmp_path: Path) -> None:
    config_path = _config_file(tmp_path)
    assert main(["--config", str(config_path)]) == 0
    runs = layout.list_runs(tmp_path)
    assert len(runs) == 1
    assert (runs[0] / "summary.json").is_file()
    assert (runs[0] / "transcripts" / "offline.jsonl").is_file()
    # And NOT at the top level, which is the layout being replaced.
    assert not (tmp_path / "summary.json").exists()


def test_a_second_run_does_not_overwrite_the_first(tmp_path: Path) -> None:
    """The whole point. Both summaries survive, and each names its own run."""
    config_path = _config_file(tmp_path)
    assert main(["--config", str(config_path)]) == 0
    first = layout.latest_run(tmp_path)
    assert first is not None
    before = (first / "summary.json").read_text(encoding="utf-8")

    assert main(["--config", str(config_path)]) == 0
    runs = layout.list_runs(tmp_path)
    assert len(runs) == 2, "the second invocation reused the first's directory"
    assert (first / "summary.json").read_text(encoding="utf-8") == before
    for run in runs:
        payload = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        assert payload["run"] == run.name, "a summary must name its own run"


def test_run_dir_override_writes_where_told(tmp_path: Path) -> None:
    config_path = _config_file(tmp_path)
    target = tmp_path / "chosen"
    assert main(["--config", str(config_path), "--run-dir", str(target)]) == 0
    assert (target / "summary.json").is_file()
    assert layout.list_runs(tmp_path) == [], "a timestamped directory was made anyway"


def test_resume_without_a_run_dir_is_refused(tmp_path: Path) -> None:
    """A resume appends to a transcript an earlier invocation wrote. In a fresh
    timestamped directory there is nothing to append to, and the failure would
    land only after the roster and providers were already up."""
    config_path = _config_file(tmp_path, n=2, resume_from=1)
    assert main(["--config", str(config_path)]) == 2
    assert layout.list_runs(tmp_path) == [], "a directory was created before refusing"


def test_resume_into_the_original_run_directory_works(tmp_path: Path) -> None:
    """The supported path: name the run whose transcript is being continued."""
    target = tmp_path / "run-a"
    first = _config_file(tmp_path, n=1)
    assert main(["--config", str(first), "--run-dir", str(target)]) == 0

    from experiments.llm_eval.metrics import iter_jsonl

    resumed = _config_file(tmp_path, n=2, resume_from=1)
    assert main(["--config", str(resumed), "--run-dir", str(target)]) == 0
    records = list(iter_jsonl(str(target / "transcripts" / "offline.jsonl")))
    assert [r["seed"] for r in records] == [0, 1]


# --- the readers -------------------------------------------------------------


def test_resolve_dir_defaults_to_the_curated_archive() -> None:
    """The documented audit command must keep covering the PUBLISHED evidence,
    not whichever run finished last."""
    from experiments.llm_eval.verify import DEFAULT_RESULTS, resolve_dir

    assert resolve_dir(None, None) == DEFAULT_RESULTS / layout.ARCHIVE


def test_resolve_dir_honours_an_explicit_directory() -> None:
    from experiments.llm_eval.verify import resolve_dir

    assert resolve_dir("/tmp/somewhere", None) == Path("/tmp/somewhere")


def test_resolve_dir_refuses_both_at_once() -> None:
    """Not a precedence question: honouring one silently would report a
    different body of data under a heading naming what was asked for."""
    from experiments.llm_eval.verify import resolve_dir

    with pytest.raises(SystemExit, match="not both"):
        resolve_dir("/tmp/x", "latest")


def test_resolve_dir_names_the_available_runs_when_one_is_missing() -> None:
    from experiments.llm_eval.verify import resolve_dir

    with pytest.raises(SystemExit, match="no run named 'nope'"):
        resolve_dir(None, "nope")


# --- the study summary -------------------------------------------------------


def test_study_summary_covers_every_archived_matchup(tmp_path: Path) -> None:
    """Derived from the archive, so it cannot disagree with the transcripts it
    claims to summarize. The old top-level summary was a side effect of whichever
    invocation ran last, which after a partial 2-game run said the whole study
    was two games."""
    from experiments.llm_eval.study import study_summary

    archive = tmp_path / layout.ARCHIVE
    archive.mkdir(parents=True)
    for name, seeds in (("alpha", [0, 1, 2]), ("beta", [0])):
        (archive / f"{name}.jsonl").write_text(
            "".join(json.dumps(_bare_record(s)) + "\n" for s in seeds), encoding="utf-8"
        )
    summary = study_summary(archive)
    assert [b["matchup"] for b in summary["matchups"]] == ["alpha", "beta"]
    assert [b["n_completed"] for b in summary["matchups"]] == [3, 1]
    assert summary["source"] == str(archive)
    # Spend is a property of an invocation; summing it across an archive built
    # over many invocations would invent a number no run ever reported.
    assert "run_totals" not in summary


def test_study_summary_refuses_an_empty_archive(tmp_path: Path) -> None:
    """Writing an empty summary would report a study with no data as a study
    that measured nothing, which reads the same as a clean result."""
    from experiments.llm_eval.study import study_summary

    archive = tmp_path / layout.ARCHIVE
    archive.mkdir(parents=True)
    with pytest.raises(SystemExit, match="nothing to summarize"):
        study_summary(archive)


def test_study_summary_ignores_a_run_summary(tmp_path: Path) -> None:
    """A run directory sitting beside the archive must not leak into the study
    summary — the two tiers answer different questions."""
    from experiments.llm_eval.study import study_summary

    archive = tmp_path / layout.ARCHIVE
    archive.mkdir(parents=True)
    (archive / "alpha.jsonl").write_text(
        json.dumps(_bare_record(0)) + "\n", encoding="utf-8"
    )
    run = layout.new_run_dir(tmp_path, datetime(2026, 7, 29, tzinfo=timezone.utc))
    (run / "transcripts").mkdir()
    (run / "transcripts" / "beta.jsonl").write_text(
        json.dumps(_bare_record(9)) + "\n", encoding="utf-8"
    )
    assert [b["matchup"] for b in study_summary(archive)["matchups"]] == ["alpha"]


def _bare_record(seed: int) -> dict[str, Any]:
    return {
        "matchup": "x",
        "seed": seed,
        "game_index": seed,
        "terminal": True,
        "truncated": False,
        "returns": [1.0, -1.0, -1.0, -1.0],
        "seats": {"0": "rule", "1": "random", "2": "random", "3": "random"},
        "history": [],
        "decisions": [],
        "usage": {},
        "num_decisions": 0,
        "wall_seconds": 0.0,
    }
