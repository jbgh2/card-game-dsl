"""Promote one or more runs into a results tree's committed archive.

`layout.py` describes two tiers — a run directory is working output, the archive
is evidence — and until now nothing implemented the transition between them.
Every archive in this repo was promoted by a hand-typed `cp`, and each one lost
something different:

- Kuhn's archive kept its transcripts and left the `.treatment.json` sidecars
  behind in the run directory, so nothing in it named the game. `verify.py` fell
  through to the Cheat default and printed a real Kuhn win rate beside
  `0 / 0 = None` for every deception metric, exit 0.
- Kuhn's promoted summary still pointed at the gitignored run directory it came
  from, so its `transcript` paths named files a fresh clone does not have.
- Hold'em's archive kept its sidecars — by luck, not design — and had no
  archive-level summary and no `AUDIT.txt` at all.

Each is the same shape: the run wrote the fact, the copy dropped it. A hand copy
carries whatever the person remembered; this module carries what the archive
needs to stand alone, and REFUSES rather than promoting something that cannot.

    python -m experiments.llm_eval.promote --results experiments/llm_eval/results_holdem \\
        --run 2026-08-04T06-09-30Z

Contract
--------
Assumes: each named run directory holds `summary.json` and a `transcripts/`
with a `.jsonl` and a `.treatment.json` per matchup.
Establishes: an archive that identifies its own game with every run directory
deleted, whose summary's transcript pointers are archive-relative, and whose
`AUDIT.txt` carries a SHA-256 per archived file.
Illegal after: promoting by hand.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from . import layout


class PromotionError(RuntimeError):
    """A run cannot be promoted without losing something the archive needs."""


def _matchups_of(run: Path) -> dict[str, Path]:
    """The `.jsonl` transcript per matchup in one run directory."""
    return {p.stem: p for p in sorted((run / layout.ARCHIVE).glob("*.jsonl"))}


def _read_summary(run: Path) -> dict[str, Any]:
    summary = run / "summary.json"
    if not summary.is_file():
        raise PromotionError(
            f"{run} has no summary.json — it records what the invocation spent "
            f"and which game it played, and the archive has no other source for "
            f"either once the run directory is gone"
        )
    return dict(json.loads(summary.read_text()))


def plan(runs: list[Path]) -> tuple[str, dict[str, tuple[Path, Path]]]:
    """The game these runs share, and one (transcript, sidecar) pair per matchup.

    Takes a LIST because one experiment is not always one invocation — a
    replication split across parallel streams lives in several run directories,
    and promoting only the last would publish half an experiment while looking
    complete. The refusals below are the cases where combining them would
    silently misrepresent what was run.
    """
    if not runs:
        raise PromotionError("no runs given — nothing to promote")

    games = {}
    for run in runs:
        summary = _read_summary(run)
        game = summary.get("game")
        if not game:
            raise PromotionError(f"{run}/summary.json does not name a game")
        games[str(game)] = run
    if len(games) > 1:
        raise PromotionError(
            f"these runs are of different games: "
            f"{ {g: str(r) for g, r in games.items()} } — one archive holds one "
            f"game, or `verify.py` cannot pick a recomputation for it"
        )
    game = next(iter(games))

    pairs: dict[str, tuple[Path, Path]] = {}
    seen_in: dict[str, Path] = {}
    for run in runs:
        for matchup, transcript in _matchups_of(run).items():
            if matchup in seen_in:
                raise PromotionError(
                    f"matchup {matchup!r} appears in both {seen_in[matchup]} and "
                    f"{run} — promoting either alone publishes part of an "
                    f"experiment as if it were the whole; resume into one run "
                    f"directory, or promote them under distinct matchup names"
                )
            sidecar = transcript.with_suffix(".treatment.json")
            if not sidecar.is_file():
                raise PromotionError(
                    f"{transcript} has no {sidecar.name} beside it — the sidecar "
                    f"is what tells a reader which treatment produced the data, "
                    f"and an archive without it cannot be checked against the "
                    f"config that made it"
                )
            seen_in[matchup] = run
            pairs[matchup] = (transcript, sidecar)
    if not pairs:
        raise PromotionError(f"no transcripts under {[str(r) for r in runs]}")
    return game, pairs


def promote(results_dir: Path, runs: list[Path]) -> dict[str, Any]:
    """Copy every run's transcripts into the archive, with what they need.

    Transcripts already present with identical CONTENT are left untouched rather
    than rewritten: gzip output is not byte-stable across implementations, and
    rewriting a committed archive's bytes would churn its SHA manifest for data
    that did not change.
    """
    game, pairs = plan(runs)
    archive = layout.archive_dir(results_dir)
    archive.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for matchup, (transcript, sidecar) in sorted(pairs.items()):
        target = archive / f"{matchup}.jsonl.gz"
        payload = transcript.read_bytes()
        if not (target.is_file() and gzip.decompress(target.read_bytes()) == payload):
            target.write_bytes(gzip.compress(payload, 9))
            written.append(target.name)
        shutil.copyfile(sidecar, archive / sidecar.name)

    summary = _archive_summary(game, runs, sorted(pairs), archive)
    (results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (results_dir / "AUDIT.txt").write_text(_manifest(archive), encoding="utf-8")
    return {"game": game, "matchups": sorted(pairs), "rewritten": written}


#: The repo root, derived from this module's own location rather than the
#: working directory — a promoted summary must read the same whichever
#: directory `promote` was invoked from.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _archive_summary(
    game: str, runs: list[Path], matchups: list[str], archive: Path
) -> dict[str, Any]:
    """The archive's own summary: what it holds, and what producing it cost.

    Transcript pointers are REPO-ROOT-relative, which is the convention
    `tests/test_layout.py::test_a_promoted_summary_points_at_committed_files`
    enforces over every `results*/summary.json` — it resolves each pointer from
    the repo root AND asserts git tracks it, so a pointer into a gitignored run
    directory fails there rather than on somebody else's clone. That check found
    this function's first version, which wrote archive-relative pointers, on the
    day the file appeared.
    """
    per_matchup: dict[str, Any] = {}
    totals: dict[str, dict[str, Any]] = {}
    for run in runs:
        summary = _read_summary(run)
        for block in summary.get("matchups", []):
            name = str(block.get("matchup"))
            if name in matchups:
                kept = {k: v for k, v in block.items() if k != "transcript"}
                kept["transcript"] = _pointer(archive, name)
                per_matchup[name] = kept
        for model, spend in (summary.get("run_totals") or {}).items():
            into = totals.setdefault(model, {k: 0 for k in spend if k != "model"})
            into["model"] = spend.get("model")
            for key, value in spend.items():
                if key != "model":
                    into[key] = round(into.get(key, 0) + value, 6)
    return {
        "game": game,
        "promoted_from_runs": [r.name for r in runs],
        "matchups": [per_matchup[m] for m in matchups if m in per_matchup],
        "totals": totals,
    }


def _pointer(archive: Path, matchup: str) -> str:
    """A summary's transcript pointer: repo-root-relative where that is
    meaningful, archive-relative where it is not.

    An archive under the repo root — every committed one — gets the form
    `test_layout.py` resolves and checks `git ls-files` against. An archive
    outside it has no repo-root form at all (a tmpdir in a test), and inventing
    one with `..` segments would produce a pointer that resolves nowhere.
    """
    target = (archive / f"{matchup}.jsonl.gz").resolve()
    try:
        return str(target.relative_to(_REPO_ROOT))
    except ValueError:
        return f"{layout.ARCHIVE}/{matchup}.jsonl.gz"


def _manifest(archive: Path) -> str:
    lines = [
        "# SHA-256 manifest of the committed archive.",
        "# Regenerate with: python -m experiments.llm_eval.promote --results <dir> --run <stamp>",
        "",
    ]
    for path in sorted(archive.iterdir()):
        if path.is_file() and path.name != "AUDIT.txt":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.stat().st_size:>10,}  {path.name}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--results", required=True, help="the results tree to promote into")
    ap.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="STAMP",
        help="a run directory name under <results>/runs (repeatable — one "
        "experiment may span several invocations)",
    )
    args = ap.parse_args(argv)

    results = Path(args.results)
    runs = [results / layout.RUNS / stamp for stamp in args.run]
    for run in runs:
        if not run.is_dir():
            raise SystemExit(f"no run directory {run}")
    try:
        done = promote(results, runs)
    except PromotionError as exc:
        raise SystemExit(f"refusing to promote: {exc}") from None
    print(f"promoted {len(done['matchups'])} matchup(s) of {done['game']} into {results}")
    for name in done["matchups"]:
        print(f"  {name}")
    if done["rewritten"]:
        print(f"  (wrote {len(done['rewritten'])} new transcript(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
