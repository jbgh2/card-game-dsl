"""The settled-code report: for every engine module, how long it has sat
unchanged, how much of it the execution oracles run, and which open issues
name it -- derived on demand from git, the oracle suites under coverage, and
the tracker. It is PRINTED, never written, and it is a report, never a gate:
it tells the direction review where a refactor is both safe (an oracle
would catch a changed meaning) and pointed (an issue already names the
smell). Age alone says nothing -- a module is old because it is right or
because nobody dares -- so the report never ranks by age; it puts the three
facts side by side and the reader decides. Age is measured twice: by the
newest commit of any kind, and by the newest FOCUSED commit -- one touching
fewer than SWEEP_FILES engine modules -- because a repo-wide sweep (a
comment-hygiene pass, a ledger migration) rewrites every file's date while
changing no module's meaning, and "settled" means the focused age.

Run: `python -m tools.settled_code --measure DIR`   (runs the oracles under
                                                     coverage into DIR, then
                                                     reports)
     `python -m tools.settled_code --coverage-json DIR/coverage.json`
                                                    (reports from a prior
                                                     measurement)
     `python -m tools.settled_code`                 (age and issues only;
                                                     the oracle columns read
                                                     "unmeasured")

The execution oracles are the suites CLAUDE.md names as the ones that find
what enumeration cannot: the per-seed goldens, the metamorphic and fuzz
transforms, the playouts, the rejection and corpus-check goldens, and the
OpenSpiel-readiness proofs. Each is one coverage context, so a module's
column says which oracle executes it, not merely which imports it. The
proofs run under the development selection (`-m "not slow"`): the dropped
seeds replay the same lines, and this is a measurement, never a green.
Every process a suite starts is measured -- the goldens run the engine in a
child interpreter, and the workers under `-n` are children too -- through
coverage's subprocess patch, so a column counts what the oracle executes,
not what the parent pytest process happened to run.

Contract (decisions.md "Closed-domain completeness")
---------------------------------------------------
Assumes:      the git history of the working tree, the tracker's open issues
              (bodies and titles), and a coverage JSON written by
              `coverage json --show-contexts` over the ORACLES runs --
              nothing maintained by hand.
Establishes:  a deterministic text for a given tree, issue list, coverage
              file and date: every engine module exactly once, in path order
              -- the report never orders by age, since age is the fact most
              easily mistaken for a rank.
Now illegal:  a copy of this output under version control; an oracle run
              anywhere but through ORACLES, so the columns and the registry
              cannot disagree.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = "cardlang"
REPO = "jbgh2/card-game-dsl"
SETTLED_DAYS = 90
THIN_COVERAGE = 0.5
SWEEP_FILES = 20  # a commit touching this many engine modules is a sweep, not a change

# name -> pytest selection. The order is the column order in the report.
ORACLES: dict[str, tuple[str, ...]] = {
    "goldens": ("tests/test_migration_characterization.py",),
    "metamorphic": ("tests/metamorphic",),
    "fuzz": ("tests/fuzz",),
    "playouts": ("tests/test_playout_*.py",),
    "rejections": ("tests/test_rejections.py", "tests/test_typecheck_corpus.py"),
    "proofs": ("tests/openspiel_ready", "-m", "not slow"),
}


def engine_files(root: pathlib.Path = ROOT) -> list[str]:
    """Every engine module, as a path relative to the root, sorted."""
    return sorted(p.relative_to(root).as_posix() for p in (root / ENGINE).rglob("*.py"))


@dataclasses.dataclass(frozen=True)
class History:
    last_change: int  # unix seconds of the newest commit touching the file
    last_focused: (
        int | None
    )  # newest commit touching it and fewer than SWEEP_FILES modules
    commits_recent: int  # focused commits touching it in the last SETTLED_DAYS days
    commits_total: int


def parse_git_log(text: str, files: Iterable[str], now: int) -> dict[str, History]:
    """`git log --format=%ct --name-only -- <engine>` into per-file history.

    The log is blocks of one timestamp line then the paths that commit
    touched; a path not in `files` (a rename's old spelling, a deleted
    module) is ignored, and a file no commit names is absent from the
    result -- the caller renders that as unknown rather than as new.
    """
    wanted = set(files)
    commits: list[tuple[int, list[str]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            commits.append((int(line), []))
            continue
        if commits and line in wanted:
            commits[-1][1].append(line)
    last: dict[str, int] = {}
    focused: dict[str, int] = {}
    recent: dict[str, int] = {}
    total: dict[str, int] = {}
    cutoff = now - SETTLED_DAYS * 86400
    for ts, paths in commits:
        is_sweep = len(paths) >= SWEEP_FILES
        for f in paths:
            last[f] = max(last.get(f, 0), ts)
            total[f] = total.get(f, 0) + 1
            if not is_sweep:
                focused[f] = max(focused.get(f, 0), ts)
                if ts >= cutoff:
                    recent[f] = recent.get(f, 0) + 1
    return {
        f: History(last[f], focused.get(f), recent.get(f, 0), total[f]) for f in last
    }


def git_history(
    files: Sequence[str], now: int, root: pathlib.Path = ROOT
) -> dict[str, History]:
    out = subprocess.run(
        ["git", "log", "--format=%ct", "--name-only", "--", ENGINE],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return parse_git_log(out, files, now)


_PATH_RE = re.compile(r"cardlang/[A-Za-z0-9_/]+\.py")
_MODULE_RE = re.compile(r"\bcardlang(?:\.[a-z_][a-z0-9_]*)+\b")


def cited_files(text: str, files: Iterable[str]) -> set[str]:
    """The engine files a text names, by path or by dotted module name.

    A bare basename (`observe.py`) is not a citation: it is ambiguous once
    two packages hold the same name, and an issue that means a file can
    spell its path.
    """
    known = set(files)
    hits = {m for m in _PATH_RE.findall(text) if m in known}
    for m in _MODULE_RE.findall(text):
        as_path = m.replace(".", "/") + ".py"
        if as_path in known:
            hits.add(as_path)
        as_pkg = m.replace(".", "/") + "/__init__.py"
        if as_pkg in known:
            hits.add(as_pkg)
    return hits


def issue_citations(
    issues: Iterable[Mapping[str, object]], files: Iterable[str]
) -> dict[str, list[int]]:
    files = list(files)
    out: dict[str, list[int]] = {}
    for issue in issues:
        number = int(str(issue["number"]))
        text = f"{issue.get('title', '')}\n{issue.get('body', '')}"
        for f in cited_files(text, files):
            out.setdefault(f, []).append(number)
    return {f: sorted(ns) for f, ns in out.items()}


def open_issues(repo: str = REPO) -> list[dict[str, object]]:
    out = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "500",
            "--json",
            "number,title,body",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    issues: list[dict[str, object]] = json.loads(out)
    if len(issues) >= 500:
        raise SystemExit("capped: 500 open issues fill the page -- raise the limit")
    return issues


@dataclasses.dataclass(frozen=True)
class Coverage:
    statements: int
    executed: int  # under any context
    by_oracle: Mapping[str, int]  # oracle -> statements it executed


def parse_coverage(
    data: Mapping[str, object], files: Iterable[str]
) -> dict[str, Coverage]:
    """`coverage json --show-contexts` into per-file, per-oracle counts.

    A context is the `--context` name of the run that executed the line;
    coverage records the empty context for lines run outside any, and a
    context not in ORACLES is a run this tool did not make -- both are
    counted in `executed` and in no oracle column, so the total never
    understates and a column never overstates.
    """
    wanted = set(files)
    result: dict[str, Coverage] = {}
    file_map = data.get("files")
    if not isinstance(file_map, Mapping):
        raise ValueError("coverage JSON has no 'files' map")
    for raw_path, entry in file_map.items():
        path = pathlib.Path(str(raw_path)).as_posix()
        # coverage keys by the path it measured, relative to its cwd.
        if path not in wanted:
            tail = path.split(f"{ENGINE}/", 1)
            path = f"{ENGINE}/" + tail[1] if len(tail) == 2 else path
        if path not in wanted or not isinstance(entry, Mapping):
            continue
        summary = entry.get("summary")
        contexts = entry.get("contexts")
        if not isinstance(summary, Mapping) or not isinstance(contexts, Mapping):
            raise ValueError(
                f"coverage JSON for {path} lacks summary or contexts -- run with --show-contexts"
            )
        by: dict[str, int] = {name: 0 for name in ORACLES}
        executed = 0
        for names in contexts.values():
            if not isinstance(names, list):
                continue
            executed += 1
            for name in {str(n).split("|", 1)[0] for n in names}:
                if name in by:
                    by[name] += 1
        result[path] = Coverage(int(str(summary["num_statements"])), executed, by)
    return result


@dataclasses.dataclass(frozen=True)
class Row:
    path: str
    lines: int
    history: History | None
    coverage: Coverage | None
    issues: tuple[int, ...]

    def age_days(self, now: int) -> int | None:
        return (
            None if self.history is None else (now - self.history.last_change) // 86400
        )

    def focused_age_days(self, now: int) -> int | None:
        """Days since the newest focused commit; None when every commit that
        ever touched the file was a sweep, or none did."""
        if self.history is None or self.history.last_focused is None:
            return None
        return (now - self.history.last_focused) // 86400

    def covered_fraction(self) -> float | None:
        if self.coverage is None or self.coverage.statements == 0:
            return None
        return self.coverage.executed / self.coverage.statements


@dataclasses.dataclass(frozen=True)
class Report:
    rows: tuple[Row, ...]
    now: int
    measured: bool

    def settled(self) -> list[Row]:
        return [
            r for r in self.rows if (r.focused_age_days(self.now) or 0) >= SETTLED_DAYS
        ]

    def render(self) -> str:
        day = dt.datetime.fromtimestamp(self.now, dt.UTC).date().isoformat()
        cols = "".join(f" {n} |" for n in ORACLES)
        out = [
            f"# Settled code -- derived, never maintained ({day})",
            "",
            f"engine modules: {len(self.rows)}; settled = no focused commit in {SETTLED_DAYS} days "
            f"(a commit touching {SWEEP_FILES}+ modules is a sweep and does not count); "
            f"thin = under {int(THIN_COVERAGE * 100)}% of statements executed by any oracle"
            + (
                ""
                if self.measured
                else "; oracle columns UNMEASURED (run with --measure DIR)"
            ),
            "",
            "| module | lines | last commit | last focused | focused/90d | oracle % |"
            + cols
            + " open issues |",
            "|---|---:|---:|---:|---:|---:|" + "---:|" * len(ORACLES) + "---|",
        ]
        for r in sorted(self.rows, key=lambda r: r.path):
            age = r.age_days(self.now)
            focused = r.focused_age_days(self.now)
            frac = r.covered_fraction()
            per = ""
            for name in ORACLES:
                w = len(name)
                if r.coverage is None or r.coverage.statements == 0:
                    per += f" {'-':>{w}} |"
                else:
                    pct = f"{100 * r.coverage.by_oracle.get(name, 0) // r.coverage.statements}%"
                    per += f" {pct:>{w}} |"
            out.append(
                f"| {r.path} | {r.lines} | "
                f"{'?' if age is None else f'{age}d'} | "
                f"{'sweeps only' if focused is None else f'{focused}d'} | "
                f"{'?' if r.history is None else r.history.commits_recent} | "
                f"{'-' if frac is None else f'{int(100 * frac)}%'} |"
                + per
                + " "
                + (", ".join(f"#{n}" for n in r.issues) or "-")
                + " |"
            )
        settled = self.settled()
        out += ["", f"## Settled ({len(settled)} of {len(self.rows)})", ""]
        if self.measured:
            thin = [r for r in settled if (r.covered_fraction() or 0.0) < THIN_COVERAGE]
            pointed = [r for r in settled if r.issues]
            out.append(
                f"- thin under the oracles ({len(thin)}): "
                + (
                    ", ".join(r.path for r in sorted(thin, key=lambda r: r.path))
                    or "none"
                )
            )
            out.append(
                f"- named by an open issue ({len(pointed)}): "
                + (
                    ", ".join(r.path for r in sorted(pointed, key=lambda r: r.path))
                    or "none"
                )
            )
            both = sorted(r.path for r in thin if r.issues)
            out.append(
                f"- both thin and named -- a refactor here has a reason and thin oracle cover ({len(both)}): "
                + (", ".join(both) or "none")
            )
        else:
            out.append(
                "- oracle columns unmeasured, so thin/pointed are not derived; "
                "run with --measure DIR"
            )
        return "\n".join(out) + "\n"


def report(
    root: pathlib.Path,
    issues: Iterable[Mapping[str, object]],
    coverage: Mapping[str, object] | None,
    now: int,
) -> Report:
    files = engine_files(root)
    history = git_history(files, now, root)
    cites = issue_citations(issues, files)
    cov = parse_coverage(coverage, files) if coverage is not None else {}
    rows = tuple(
        Row(
            path=f,
            lines=sum(1 for _ in (root / f).open(encoding="utf-8")),
            history=history.get(f),
            coverage=cov.get(f),
            issues=tuple(cites.get(f, ())),
        )
        for f in files
    )
    return Report(rows, now, measured=coverage is not None)


def coverage_config(name: str, out_dir: pathlib.Path) -> str:
    """The coverage configuration one oracle runs under. `patch = subprocess`
    is what makes a child interpreter -- a golden's capture process, an
    xdist worker -- write its own data file, which `combine` then folds in;
    without it a column counts only the parent pytest process."""
    return (
        "[run]\n"
        f"source = {ENGINE}\n"
        f"data_file = {out_dir / ('.coverage.' + name)}\n"
        "parallel = true\n"
        f"context = {name}\n"
        "patch = subprocess\n"
    )


def measure(
    out_dir: pathlib.Path, root: pathlib.Path = ROOT, workers: int = 0
) -> pathlib.Path:
    """Run every ORACLES selection under coverage, one context each, and
    write `coverage.json` with contexts into `out_dir`. `workers` > 0 runs
    each suite under `-n workers`; the workers are measured through the
    subprocess patch like any other child."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(".coverage*"):
        old.unlink()
    py = sys.executable
    for name, selection in ORACLES.items():
        rc = out_dir / f"coveragerc.{name}"
        rc.write_text(coverage_config(name, out_dir))
        args = [
            a
            for pat in selection
            for a in (
                sorted(p.as_posix() for p in root.glob(pat))
                if any(c in pat for c in "*?[")
                else [pat]
            )
        ]
        if workers > 0:
            args += ["-n", str(workers)]
        subprocess.run(
            [
                py,
                "-m",
                "coverage",
                "run",
                f"--rcfile={rc}",
                "-m",
                "pytest",
                *args,
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=root,
            check=False,
        )
    parts = sorted(str(p) for p in out_dir.glob(".coverage.*"))
    subprocess.run(
        [
            py,
            "-m",
            "coverage",
            "combine",
            "--keep",
            f"--data-file={out_dir / '.coverage'}",
            *parts,
        ],
        cwd=root,
        check=True,
    )
    target = out_dir / "coverage.json"
    subprocess.run(
        [
            py,
            "-m",
            "coverage",
            "json",
            f"--data-file={out_dir / '.coverage'}",
            "--show-contexts",
            "-o",
            str(target),
        ],
        cwd=root,
        check=True,
    )
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--coverage-json",
        type=pathlib.Path,
        help="a coverage JSON written with --show-contexts",
    )
    parser.add_argument(
        "--measure",
        type=pathlib.Path,
        metavar="DIR",
        help="run the oracles under coverage into DIR first",
    )
    parser.add_argument(
        "--no-issues", action="store_true", help="skip the tracker (offline)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        metavar="N",
        help="run each oracle under -n N while measuring (0 = serial)",
    )
    ns = parser.parse_args(argv)
    cov_path: pathlib.Path | None = ns.coverage_json
    if ns.measure is not None:
        cov_path = measure(ns.measure, workers=ns.workers)
    coverage_data = json.loads(cov_path.read_text()) if cov_path is not None else None
    issues = [] if ns.no_issues else open_issues()
    now = int(dt.datetime.now(dt.UTC).timestamp())
    sys.stdout.write(report(ROOT, issues, coverage_data, now).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
