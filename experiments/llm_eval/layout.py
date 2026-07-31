"""Where a run's output goes.

Two tiers, because they answer different questions.

RUNS — `results/runs/<UTC timestamp>/` holds one invocation: its `summary.json`,
its transcripts, its figure. One directory per `run_eval` invocation, never
overwritten. Before this existed, `summary.json` lived at the top of
`results/` and every run clobbered the last one, so the derived numbers for all
but the most recent invocation were simply gone — the cost accounting for a
twelve-invocation session had to be reconstructed by summing transcripts by hand.

ARCHIVE — `results/transcripts/*.jsonl.gz` is the curated, committed record
behind the published result. Promotion into it is a deliberate act (gzip, commit)
because it is a claim that the data backs a number someone will read, and it is
what `AUDIT.txt` and the README's repro commands address. A run directory is
working output; the archive is evidence.

The timestamp is UTC and filename-safe, and it is chosen so that lexicographic
order IS chronological order — `sorted()` on directory names is a valid
"most recent" without stat-ing anything or trusting mtimes, which copying and
checkout both destroy.

Contract
--------
Assumes: `results_dir` exists or can be created.
Establishes: a fresh, empty run directory whose name sorts chronologically.
Illegal after: writing a run's summary anywhere but inside its own run directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

RUNS = "runs"
ARCHIVE = "transcripts"

# `:` is illegal in filenames on Windows and awkward everywhere; `-` keeps the
# field widths fixed, which is what makes the lexicographic sort correct.
STAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"


def stamp(now: datetime | None = None) -> str:
    """A UTC run name. `now` is injectable so tests need not wait a second."""
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).strftime(STAMP_FORMAT)


def new_run_dir(results_dir: Path, now: datetime | None = None) -> Path:
    """Create and return this invocation's directory.

    Collisions matter: two invocations started in the same second would
    otherwise share a directory and interleave their transcripts, which looks
    like one run with twice the data. A suffix is appended rather than reusing
    the directory, so a run's contents always come from exactly one invocation.
    """
    base = results_dir / RUNS
    name = stamp(now)
    candidate = base / name
    serial = 1
    while candidate.exists():
        serial += 1
        candidate = base / f"{name}-{serial}"
    candidate.mkdir(parents=True)
    return candidate


def list_runs(results_dir: Path) -> list[Path]:
    """Every run directory, oldest first. Empty when none have been made."""
    base = results_dir / RUNS
    if not base.is_dir():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name)


def latest_run(results_dir: Path) -> Path | None:
    runs = list_runs(results_dir)
    return runs[-1] if runs else None


def archive_dir(results_dir: Path) -> Path:
    """The curated, committed transcripts — the audit path's default target."""
    return results_dir / ARCHIVE
