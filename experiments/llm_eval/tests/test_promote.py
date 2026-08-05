"""Promotion: the archive stands alone, or the promotion is refused.

Every archive in this repo was promoted by a hand-typed `cp`, and each lost
something different — Kuhn's sidecars stayed in the run directory, Kuhn's
summary pointed at gitignored files, Hold'em had no archive summary at all.
Three losses, three different hands, one shape: the run wrote the fact and the
copy dropped it.

The property that catches all three at once is the one this module leads with:
**promote, delete the run directory, and the archive still identifies its own
game.** That is exactly the state a fresh clone is in, and it is the state in
which the audit path picks a recomputation.
"""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

import pytest

from .. import layout
from ..promote import PromotionError, plan, promote
from ..verify import _load, _transcripts, game_of

GAME = "cardlang_holdem_heads_up"


def _make_run(results: Path, stamp: str, game: str, matchups: dict[str, int]) -> Path:
    """A run directory shaped like one `run_eval` writes."""
    run = results / layout.RUNS / stamp
    (run / layout.ARCHIVE).mkdir(parents=True)
    blocks = []
    for name, games in matchups.items():
        transcript = run / layout.ARCHIVE / f"{name}.jsonl"
        transcript.write_text(
            "".join(
                json.dumps(
                    {
                        "matchup": name,
                        "game_index": i,
                        "seed": i,
                        "seats": {"0": "a", "1": "b"},
                        "history": [],
                        "decisions": [],
                        "returns": [1.0, -1.0],
                        "terminal": True,
                        "truncated": False,
                        "num_decisions": 0,
                        "wall_seconds": 0.1,
                        "usage": {},
                    }
                )
                + "\n"
                for i in range(games)
            ),
            encoding="utf-8",
        )
        transcript.with_suffix(".treatment.json").write_text(
            json.dumps({"game": game, "agents": [{"kind": "random"}]}), encoding="utf-8"
        )
        blocks.append(
            {"matchup": name, "n_completed": games, "transcript": str(transcript)}
        )
    (run / "summary.json").write_text(
        json.dumps(
            {
                "game": game,
                "run": stamp,
                "run_dir": str(run),
                "matchups": blocks,
                "run_totals": {"cheap": {"model": "m", "cost_usd": 1.5, "calls": 10}},
            }
        ),
        encoding="utf-8",
    )
    return run


def test_the_archive_identifies_itself_with_the_run_directory_deleted(
    tmp_path: Path,
) -> None:
    """The property all three hand-copy losses violated.

    Identity is carried TWICE on purpose — the sidecar and the archive summary —
    so this test reddens only when BOTH are dropped, and the redundancy is the
    property rather than an accident. Established by running each mutation
    rather than reasoning about it, because the first two guesses were wrong:

    - drop the `shutil.copyfile(sidecar, ...)`: this stays GREEN;
      `test_the_manifest_covers_every_archived_file` fails instead.
    - drop the summary write: this stays GREEN;
      `test_the_summary_points_into_the_archive_not_the_run` and
      `test_several_runs_promote_into_one_archive` fail instead.
    - drop BOTH: this fails, `assert None == 'cardlang_holdem_heads_up'` — the
      exact state Kuhn's committed archive was in, where `verify.py` fell
      through to the Cheat default and audited the wrong game with exit 0.

    So the sidecar is not redundant with the summary: it carries the TREATMENT,
    which nothing else records, and identity is its side effect.
    """
    results = tmp_path / "results_x"
    run = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 3})
    promote(results, [run])

    shutil.rmtree(results / layout.RUNS)  # the state of a fresh clone

    archived = _transcripts(layout.archive_dir(results))
    assert archived, "nothing was promoted"
    for path in archived:
        assert game_of(path, _load(path)) == GAME


def test_the_summary_points_into_the_archive_not_the_run(tmp_path: Path) -> None:
    """A promoted summary that still named the run directory pointed at files a
    fresh clone does not have — the run's working copies are gitignored.

    The pointer is REPO-ROOT-relative, the convention
    `test_layout.py::test_a_promoted_summary_points_at_committed_files` enforces
    over every committed archive. It is asserted here as a shape rather than a
    literal because a tmpdir is outside the repo root, so only the tail is
    meaningful; the committed archives are what that other test checks whole.
    """
    results = tmp_path / "results_x"
    run = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 2})
    promote(results, [run])

    summary = json.loads((results / "summary.json").read_text())
    assert summary["game"] == GAME
    for block in summary["matchups"]:
        pointer = block["transcript"]
        assert pointer.endswith(f"{layout.ARCHIVE}/{block['matchup']}.jsonl.gz")
        assert layout.RUNS not in pointer


def test_promotion_is_refused_without_a_sidecar(tmp_path: Path) -> None:
    """The exact loss that left Kuhn's archive unidentifiable."""
    results = tmp_path / "results_x"
    run = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 1})
    (run / layout.ARCHIVE / "a_vs_b.treatment.json").unlink()
    with pytest.raises(PromotionError, match="no a_vs_b.treatment.json"):
        promote(results, [run])


def test_promotion_is_refused_when_a_matchup_spans_two_runs(tmp_path: Path) -> None:
    """Promoting either alone would publish half an experiment while looking
    complete — the failure that makes a LIST of runs the right input and a
    silent last-wins the wrong one."""
    results = tmp_path / "results_x"
    first = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 2})
    second = _make_run(results, "2026-01-02T00-00-00Z", GAME, {"a_vs_b": 2})
    with pytest.raises(PromotionError, match="appears in both"):
        plan([first, second])


def test_promotion_is_refused_when_runs_name_different_games(tmp_path: Path) -> None:
    """One archive holds one game, or the audit path cannot pick a
    recomputation for it."""
    results = tmp_path / "results_x"
    first = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 1})
    second = _make_run(results, "2026-01-02T00-00-00Z", "cardlang_cheat", {"c_vs_d": 1})
    with pytest.raises(PromotionError, match="different games"):
        plan([first, second])


def test_several_runs_promote_into_one_archive(tmp_path: Path) -> None:
    """One experiment is not always one invocation: a replication split across
    parallel streams must promote as a whole."""
    results = tmp_path / "results_x"
    first = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 2})
    second = _make_run(results, "2026-01-02T00-00-00Z", GAME, {"c_vs_d": 3})
    done = promote(results, [first, second])

    assert done["matchups"] == ["a_vs_b", "c_vs_d"]
    summary = json.loads((results / "summary.json").read_text())
    assert [b["matchup"] for b in summary["matchups"]] == ["a_vs_b", "c_vs_d"]
    assert summary["promoted_from_runs"] == [first.name, second.name]
    # Spend is summed across the runs, not taken from whichever came last.
    assert summary["totals"]["cheap"]["cost_usd"] == 3.0


def test_an_unchanged_transcript_is_not_rewritten(tmp_path: Path) -> None:
    """Re-promoting must not churn a committed archive's bytes for data that did
    not change — gzip output is not byte-stable, and the SHA manifest is
    evidence someone may have quoted."""
    results = tmp_path / "results_x"
    run = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 2})
    promote(results, [run])
    target = layout.archive_dir(results) / "a_vs_b.jsonl.gz"
    before = target.read_bytes()

    again = promote(results, [run])
    assert again["rewritten"] == []
    assert target.read_bytes() == before
    assert gzip.decompress(before)


def test_the_manifest_covers_every_archived_file(tmp_path: Path) -> None:
    """AUDIT.txt is the archive's own checksum record; a file missing from it is
    a file nobody can tell has changed."""
    results = tmp_path / "results_x"
    run = _make_run(results, "2026-01-01T00-00-00Z", GAME, {"a_vs_b": 1, "c_vs_d": 1})
    promote(results, [run])

    manifest = (results / "AUDIT.txt").read_text()
    archive = layout.archive_dir(results)
    listed = {line.split()[-1] for line in manifest.splitlines() if "  " in line and not line.startswith("#")}
    present = {p.name for p in archive.iterdir() if p.is_file()}
    assert present <= listed, f"unmanifested: {sorted(present - listed)}"
    assert len(present) == 4, "two transcripts and two sidecars"
