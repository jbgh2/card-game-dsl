"""Select, from a change's diff, the checks it calls for, and run them.

    python3 tools/check_change.py [--list] [--full | --dev] [--range A..B]

The diff is the branch against its merge base with `origin/main`, plus the
working tree and untracked files; `--range A..B` reads a committed range
instead (`C^1..C` for one merged commit). Every rule CLAUDE.md "Verifying
changes" and docs/maintaining.md state as a function of a diff is a
`Check`, and every run prints every `Check` with what became of it.

Three modes, one selection:

* the default runs the checks the diff calls for that a local run owes
  before pushing -- the type check, the full-width goldens, the test
  modules that name a changed game, the classifier tables, the census
  pins, the doc-snippet and ADR pins, and the changed test modules --
  while the language suite and, unless the diff reaches them, the rigs
  are left to CI and printed as such;
* `--full` runs the three gate checks in the form `.github/workflows/ci.yml`
  writes them, plus the full-width goldens CI never sweeps; it is the
  local evidence when CI is unavailable;
* `--dev` swaps the language suite for the development pass
  (`-m "not slow"`), and says on every run that it is not evidence.

`--list` prints the selection and runs nothing. Every check runs through
`tools/verify.sh`, which owns the interpreter choice, unpiped: its output
passes through, its exit status is the run's, and the run's summary line
is quoted as the evidence. A run that prints no summary line fails. CI
stays the authority; this decides what to run locally and is no second
gate.

Contract
--------
Assumes:      docs/harness.md "The Merge Lanes" is the one owner of path
              classes, read through `tools/lane-of.sh`; docs/maintaining.md
              "The pins a new game joins" and "Doc snippet tagging" name the
              modules and docs those rules cover; the corpus is
              `docs/games/*.cardlang` and the family libraries
              `docs/libraries/*.cardlang`.
Establishes:  for every `Check`, whether the diff fires it and why, from
              `triggered`, which dispatches over every member.
Illegal after: a lane-table row this module keys on that no longer exists
              (`_row`), a maintaining.md section that names no module, and a
              named module that does not exist, each refused before
              anything runs.

Held by: Derived and Pinned (tests/test_check_change.py).
"""

from __future__ import annotations

import argparse
import enum
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, NoReturn, Sequence


class Check(enum.Enum):
    TYPECHECK = "typecheck"
    LANGUAGE_SUITE = "language-suite"
    RIGS = "rigs"
    GOLDENS_FULL = "goldens-full-width"
    GAME_NAMED = "game-named-modules"
    CLASSIFIER_TABLES = "classifier-tables"
    CENSUS_PINS = "census-pins"
    DOC_SNIPPETS = "doc-snippets"
    ADR_RECORDS = "adr-records"
    CHANGED_TESTS = "changed-test-modules"


class Status(enum.Enum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"


class Mode(enum.Enum):
    TARGETED = "targeted"
    FULL = "full"
    DEV = "dev"


class Disposition(enum.Enum):
    RUN = "run"
    IN_CI = "left to CI"
    IN_SUITE = "inside a suite this run runs"
    NOTHING_NAMED = "fired, but no module to run"
    COVERED = "its modules run under an earlier check"
    NOT_SELECTED = "not selected"


def _never(value: NoReturn) -> NoReturn:
    raise AssertionError(f"unhandled member: {value!r}")


class SelectionError(Exception):
    """A fact the selection reads is missing or moved; nothing runs."""


@dataclass(frozen=True)
class Change:
    status: Status
    path: str
    lane_classes: tuple[str, ...]
    cites_adr: bool = False


@dataclass(frozen=True)
class Tree:
    games: frozenset[str]
    library_consumers: Mapping[str, frozenset[str]]
    snippet_docs: frozenset[str]
    classifier_modules: tuple[str, ...]
    census_modules: tuple[str, ...]
    tests_naming: Callable[[str], tuple[str, ...]]


# Rows of docs/harness.md "The Merge Lanes" a rule keys on, by the start of
# the row's class as tools/lane-of.sh prints it.
CORPUS_ROW = "docs/games/ corpus and family libraries"
RIGS_ROW = "experiments/ rigs"
RULINGS_ROW = "Docs — rulings"
KEYED_ROWS = (CORPUS_ROW, RIGS_ROW, RULINGS_ROW)

_ADR_CITATION = re.compile(r"ADR-[0-9]{4}")
_CENSUS_SCAN = re.compile(r"walk_packages|iter_modules|\*\.py[\"']")
_GAME = re.compile(r"docs/games/([^/]+)\.(cardlang|md)")
_LIBRARY = re.compile(r"docs/libraries/([^/]+)\.cardlang")
_PROOF_MODULE = re.compile(r"tests/openspiel_ready/test_([^/]+)\.py")
_TEST_MODULE = re.compile(r"tests/(.+/)?test_[^/]*\.py")


def fold(stem: str) -> str:
    """A game's stem as a Python identifier (`big-two` -> `big_two`)."""
    return stem.replace("-", "_")


def _in_row(change: Change, row: str) -> bool:
    return any(cls.startswith(row) for cls in change.lane_classes)


def _is_python(path: str) -> bool:
    return path.endswith((".py", ".pyi"))


def _affected_names(changes: Sequence[Change], tree: Tree) -> dict[str, str]:
    """Every game or library whose rules the diff changes, with why."""
    games = set(tree.games) | {
        m.group(1) for c in changes
        if (m := _GAME.fullmatch(c.path)) and m.group(2) == "cardlang"
    }
    by_fold = {fold(g): g for g in games}
    names: dict[str, str] = {}
    for c in changes:
        if (m := _GAME.fullmatch(c.path)) and m.group(1) in games:
            names.setdefault(m.group(1), c.path)
        elif m := _LIBRARY.fullmatch(c.path):
            names.setdefault(m.group(1), c.path)
            for consumer in sorted(tree.library_consumers.get(m.group(1), frozenset())):
                names.setdefault(consumer, f"{c.path} (uses {m.group(1)})")
        elif (m := _PROOF_MODULE.fullmatch(c.path)) and m.group(1) in by_fold:
            names.setdefault(by_fold[m.group(1)], c.path)
    return names


def _fires(check: Check, changes: Sequence[Change], tree: Tree) -> tuple[str, ...]:
    """Why `check` fires for this diff; empty when it does not."""
    if check is Check.TYPECHECK:
        return tuple(c.path for c in changes if _is_python(c.path) or c.path == "pyproject.toml")
    if check is Check.LANGUAGE_SUITE:
        return ("the gate runs it on every change",) if changes else ()
    if check is Check.RIGS:
        return tuple(
            c.path for c in changes
            if _in_row(c, RIGS_ROW) or _in_row(c, CORPUS_ROW)
            or c.path.startswith("cardlang/") or c.path == "pyproject.toml"
        )
    if check is Check.GOLDENS_FULL:
        return tuple(c.path for c in changes if _in_row(c, CORPUS_ROW))
    if check is Check.GAME_NAMED or check is Check.CLASSIFIER_TABLES:
        return tuple(f"{name}: {why}" for name, why in _affected_names(changes, tree).items())
    if check is Check.CENSUS_PINS:
        return tuple(
            c.path for c in changes
            if _is_python(c.path) and c.path.startswith(("cardlang/", "tests/", "tools/"))
        )
    if check is Check.DOC_SNIPPETS:
        return tuple(c.path for c in changes if c.path in tree.snippet_docs)
    if check is Check.ADR_RECORDS:
        return tuple(
            c.path + (" cites ADR-NNNN" if c.cites_adr else "")
            for c in changes if _in_row(c, RULINGS_ROW) or c.cites_adr
        )
    if check is Check.CHANGED_TESTS:
        return tuple(
            c.path for c in changes
            if c.status is not Status.DELETED and _TEST_MODULE.fullmatch(c.path)
        )
    _never(check)


def triggered(changes: tuple[Change, ...], tree: Tree) -> dict[Check, tuple[str, ...]]:
    """Every `Check` the diff fires, each with the reasons it fired."""
    fired = {check: _fires(check, changes, tree) for check in Check}
    return {check: why for check, why in fired.items() if why}


# --- the plan: what each mode does with what fired --------------------------


@dataclass(frozen=True)
class Step:
    check: Check
    disposition: Disposition
    reasons: tuple[str, ...]
    argv: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()


_GATE = (Check.TYPECHECK, Check.LANGUAGE_SUITE, Check.RIGS)
_GOLDENS_MODULE = "tests/test_migration_characterization.py"


def _modules(
    check: Check, why: tuple[str, ...], changes: Sequence[Change], tree: Tree, root: str
) -> tuple[str, ...]:
    """The test modules a module-list check runs, before deduplication.

    A classifier table's `<stem>` entry is the proof module of each affected
    game whose `.cardlang` is in the tree: a deleted game has none, and an
    added game without one is left for pytest to refuse by name.
    """
    if check is Check.GAME_NAMED:
        names = _affected_names(changes, tree)
        return tuple(sorted({m for name in names for m in tree.tests_naming(name)}))
    if check is Check.CLASSIFIER_TABLES:
        folded = sorted(
            fold(n) for n in _affected_names(changes, tree)
            if (Path(root) / "docs/games" / f"{n}.cardlang").is_file()
        )
        out: set[str] = set()
        for module in tree.classifier_modules:
            if "<stem>" in module:
                out.update(module.replace("<stem>", f) for f in folded)
            else:
                out.add(module)
        return tuple(sorted(out))
    if check is Check.CENSUS_PINS:
        return tree.census_modules
    if check is Check.DOC_SNIPPETS:
        return ("tests/test_doc_snippets.py",)
    if check is Check.ADR_RECORDS:
        return ("tests/test_adr_records.py",)
    if check is Check.CHANGED_TESTS:
        return tuple(sorted(r for r in why))
    raise AssertionError(f"{check} runs no module list")


def _gate_argv(check: Check, mode: Mode) -> tuple[str, ...]:
    if check is Check.TYPECHECK:
        return ("mypy",)
    if check is Check.LANGUAGE_SUITE:
        if mode is Mode.DEV:
            return ("pytest", "-q", "-m", "not slow", "-n", "auto")
        return ("pytest", "-q", "-n", "8")
    if check is Check.RIGS:
        return ("pytest", "experiments/llm_eval/tests", "-q")
    raise AssertionError(f"{check} is not a gate check")


def plan(changes: tuple[Change, ...], tree: Tree, mode: Mode, root: str) -> tuple[Step, ...]:
    """One `Step` per `Check`, in `Check` order."""
    fired = triggered(changes, tree)
    taken: dict[str, Check] = {}
    steps: list[Step] = []
    for check in Check:
        why = fired.get(check, ())
        if check in _GATE:
            in_ci = mode is Mode.TARGETED and (check is Check.LANGUAGE_SUITE or not why)
            if in_ci:
                steps.append(Step(check, Disposition.IN_CI if changes else Disposition.NOT_SELECTED, why))
            else:
                reasons = why or ("the gate runs it on every change",)
                steps.append(Step(check, Disposition.RUN, reasons, _gate_argv(check, mode)))
            continue
        if not why:
            steps.append(Step(check, Disposition.NOT_SELECTED, ()))
            continue
        if check is Check.GOLDENS_FULL:
            # The full-width run is a superset of the module's sampled run.
            taken[_GOLDENS_MODULE] = check
            steps.append(Step(
                check, Disposition.RUN, why,
                ("pytest", _GOLDENS_MODULE, "-q"),
                (("CARDLANG_GOLDEN_SEEDS", "full"),),
            ))
            continue
        if mode is not Mode.TARGETED:
            steps.append(Step(check, Disposition.IN_SUITE, why))
            continue
        modules = _modules(check, why, changes, tree, root)
        if not modules:
            steps.append(Step(check, Disposition.NOTHING_NAMED, why))
            continue
        fresh = tuple(m for m in modules if m not in taken)
        for m in fresh:
            taken[m] = check
        if not fresh:
            steps.append(Step(check, Disposition.COVERED, why))
            continue
        steps.append(Step(check, Disposition.RUN, why, ("pytest", *fresh, "-q")))
    return tuple(steps)


# --- reading the repository -------------------------------------------------


def _git(root: str, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if done.returncode != 0:
        raise SelectionError(f"`git {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise SelectionError(f"docs/maintaining.md has no `{heading}` section") from None
    depth = len(heading) - len(heading.lstrip("#"))
    body: list[str] = []
    for line in lines[start + 1:]:
        stripped = line.lstrip("#")
        if line.startswith("#") and len(line) - len(stripped) <= depth and stripped.startswith(" "):
            break
        body.append(line)
    return "\n".join(body)


def _classifier_modules(root: Path) -> tuple[str, ...]:
    section = _section((root / "docs/maintaining.md").read_text(), "### The pins a new game joins")
    named = sorted(set(re.findall(r"`((?:tests/(?:[^`]*/)?)?test_[^`/]*\.py)`", section)))
    if not named:
        raise SelectionError("docs/maintaining.md, `The pins a new game joins`, names no test module")
    resolved: set[str] = set()
    for name in named:
        if name.startswith("tests/"):
            resolved.add(name)
            continue
        found = sorted(str(p.relative_to(root)) for p in (root / "tests").rglob(name))
        if len(found) != 1:
            raise SelectionError(
                f"docs/maintaining.md names `{name}`, which resolves to {found or 'no file'} under tests/"
            )
        resolved.add(found[0])
    for module in resolved:
        if "<stem>" not in module and not (root / module).is_file():
            raise SelectionError(f"docs/maintaining.md names `{module}`, which does not exist")
    return tuple(sorted(resolved))


def _snippet_docs(root: Path) -> frozenset[str]:
    section = _section((root / "docs/maintaining.md").read_text(), "## Doc snippet tagging")
    first = section.strip().split("\n\n", 1)[0]
    docs = frozenset(f"docs/{target}" for target in re.findall(r"\]\(([^)]+\.md)\)", first))
    if not docs:
        raise SelectionError("docs/maintaining.md, `Doc snippet tagging`, names no doc")
    return docs


def _census_modules(root: Path) -> tuple[str, ...]:
    found = sorted(
        str(p.relative_to(root)) for p in (root / "tests").rglob("*.py")
        if p.name.startswith("test_") and _CENSUS_SCAN.search(p.read_text(errors="replace"))
    )
    if not found:
        raise SelectionError("no test module under tests/ enumerates source files")
    return tuple(found)


def _consumers(root: Path) -> dict[str, frozenset[str]]:
    sources = {
        p.stem: (p.read_text(errors="replace"), p.parent.name == "libraries")
        for d in ("docs/games", "docs/libraries") for p in sorted((root / d).glob("*.cardlang"))
    }
    direct: dict[str, set[str]] = {}
    for name, (text, _) in sources.items():
        for lib in re.findall(r"^\s*uses\s+([A-Za-z0-9_]+)", text, re.MULTILINE):
            direct.setdefault(lib, set()).add(name)
    out: dict[str, frozenset[str]] = {}
    for lib in direct:
        seen: set[str] = set()
        todo = [lib]
        while todo:
            for user in direct.get(todo.pop(), set()):
                if user not in seen:
                    seen.add(user)
                    todo.append(user)
        out[lib] = frozenset(u for u in seen if not sources[u][1])
    return out


def read_tree(root: str) -> Tree:
    base = Path(root)

    @lru_cache(maxsize=None)
    def naming(name: str) -> tuple[str, ...]:
        done = subprocess.run(
            ["git", "grep", "-lF", "--untracked", "-e", name, "-e", fold(name), "--", "tests"],
            cwd=root, capture_output=True, text=True,
        )
        if done.returncode not in (0, 1):
            raise SelectionError(f"`git grep` for {name!r} failed: {done.stderr.strip()}")
        return tuple(sorted(
            p for p in done.stdout.splitlines()
            if Path(p).name.startswith("test_") and p.endswith(".py")
        ))

    return Tree(
        games=frozenset(p.stem for p in (base / "docs/games").glob("*.cardlang")),
        library_consumers=_consumers(base),
        snippet_docs=_snippet_docs(base),
        classifier_modules=_classifier_modules(base),
        census_modules=_census_modules(base),
        tests_naming=naming,
    )


def _lane_of(root: str, *args: str) -> str:
    done = subprocess.run(
        ["bash", str(Path(root) / "tools/lane-of.sh"), *args], cwd=root, capture_output=True, text=True,
    )
    if done.returncode != 0:
        raise SelectionError(f"tools/lane-of.sh failed: {done.stderr.strip()}")
    return done.stdout


def lane_rows(root: str) -> tuple[tuple[str, str, str], ...]:
    """The Merge Lanes table as tools/lane-of.sh parses it: (lane, glob, class)."""
    rows = []
    for line in _lane_of(root, "--rows").splitlines():
        lane, glob, cls = line.split("\t", 2)
        rows.append((lane, glob, cls))
    return tuple(rows)


def lane_classes(root: str, paths: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Each path's matched Merge Lanes rows, as tools/lane-of.sh classifies it."""
    if not paths:
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for line in _lane_of(root, *paths).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        _, path, matched = parts
        # A class may itself hold "; ", so a match ends only at " -> LANE".
        out[path] = () if matched.startswith("unmapped->") else tuple(
            re.findall(r"(?:^|; )(.+?) -> [A-D](?=; |$)", matched)
        )
    return out


def check_keyed_rows(rows: Sequence[tuple[str, str, str]]) -> None:
    """Refuse a lane table in which a row this module keys on is gone or doubled."""
    classes = {cls for _, _, cls in rows}
    for key in KEYED_ROWS:
        hits = sorted(cls for cls in classes if cls.startswith(key))
        if len(hits) != 1:
            raise SelectionError(
                f"docs/harness.md, `The Merge Lanes`: expected one row whose class starts "
                f"`{key}`, found {hits or 'none'}; tools/check_change.py keys a rule on it"
            )


# --- reading the diff -------------------------------------------------------


@dataclass(frozen=True)
class Diff:
    description: str
    entries: tuple[tuple[Status, str], ...]
    reader: Callable[[str], str]


def _parse_name_status(raw: str) -> list[tuple[Status, str]]:
    fields = raw.split("\0")
    out: list[tuple[Status, str]] = []
    i = 0
    while i + 1 < len(fields) and fields[i]:
        code, path = fields[i], fields[i + 1]
        i += 2
        status = {"A": Status.ADDED, "D": Status.DELETED}.get(code[0], Status.MODIFIED)
        out.append((status, path))
    return out


def read_diff(root: str, range_: str | None) -> Diff:
    if range_ is not None:
        right = range_.split("...")[-1] if "..." in range_ else range_.split("..")[-1]
        right = right or "HEAD"
        raw = _git(root, "diff", "--name-status", "-z", "--no-renames", range_)

        def from_commit(path: str) -> str:
            done = subprocess.run(["git", "show", f"{right}:{path}"], cwd=root, capture_output=True)
            return done.stdout.decode(errors="replace")

        return Diff(f"range {range_}", tuple(_parse_name_status(raw)), from_commit)
    done = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"], cwd=root, capture_output=True, text=True,
    )
    if done.returncode != 0:
        raise SelectionError(
            "no merge base with origin/main -- run `git fetch origin main` "
            "(a shallow clone needs `git fetch --unshallow origin`), or pass --range A..B"
        )
    base = done.stdout.strip()
    entries = _parse_name_status(_git(root, "diff", "--name-status", "-z", "--no-renames", base))
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    entries += [(Status.ADDED, p) for p in untracked if p]

    def from_tree(path: str) -> str:
        try:
            return (Path(root) / path).read_text(errors="replace")
        except OSError:
            return ""

    return Diff(f"working tree against merge base {base[:12]} with origin/main", tuple(entries), from_tree)


def changes_of(root: str, diff: Diff) -> tuple[Change, ...]:
    classes = lane_classes(root, tuple(p for _, p in diff.entries))
    return tuple(
        Change(
            status, path, classes.get(path, ()),
            status is not Status.DELETED and bool(_ADR_CITATION.search(diff.reader(path))),
        )
        for status, path in diff.entries
    )


# --- running ----------------------------------------------------------------

_SUMMARY = re.compile(
    r"^(=+ )?((\d+ \w+)(, \d+ \w+)*|no tests ran) in [\d.]+s\b.*"
    r"|^Success: no issues found in \d+ source files?$"
    r"|^Found \d+ errors? in \d+ files?.*"
)


def run_step(root: str, step: Step) -> tuple[int, str | None]:
    """Run one step unpiped: its output passes through; returns (status, summary line)."""
    env = dict(os.environ, PYTHONUNBUFFERED="1", **dict(step.env))
    argv = [str(Path(root) / "tools/verify.sh"), *step.argv]
    proc = subprocess.Popen(argv, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    summary: str | None = None
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if _SUMMARY.match(line.strip()):
            summary = line.strip()
    return proc.wait(), summary


def _command(step: Step) -> str:
    env = " ".join(f"{k}={v}" for k, v in step.env)
    args = " ".join(f'"{a}"' if " " in a else a for a in step.argv)
    return f"{env + ' ' if env else ''}tools/verify.sh {args}"


def render(diff: Diff, changes: Sequence[Change], steps: Sequence[Step], mode: Mode) -> str:
    lines = [f"check_change: {diff.description}, {len(changes)} changed paths, mode {mode.value}"]
    for step in steps:
        lines.append(f"  {step.check.value}: {step.disposition.value}")
        for why in step.reasons[:8]:
            lines.append(f"      because {why}")
        if len(step.reasons) > 8:
            lines.append(f"      and {len(step.reasons) - 8} more paths")
        if step.disposition is Disposition.RUN:
            lines.append(f"      runs: {_command(step)}")
    return "\n".join(lines)


_AUTHORITY = (
    "CI is the authority (CLAUDE.md, \"Verifying changes\"): this run selects "
    "checks locally and is not a second gate."
)
_NOT_EVIDENCE = "The development pass (-m \"not slow\") is NOT evidence; quote only CI or a --full run."


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--list", action="store_true", help="print the selection; run nothing")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--full", action="store_true", help="the gate's checks in CI form, plus the goldens")
    which.add_argument("--dev", action="store_true", help="the development pass; never evidence")
    parser.add_argument("--range", dest="range_", metavar="A..B", help="a committed range instead of the branch")
    args = parser.parse_args(argv)
    mode = Mode.FULL if args.full else Mode.DEV if args.dev else Mode.TARGETED

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
    ).stdout.strip()
    if not root:
        print("check_change: not inside a git checkout", file=sys.stderr)
        return 2
    try:
        check_keyed_rows(lane_rows(root))
        diff = read_diff(root, args.range_)
        if not diff.entries:
            print(f"check_change: empty diff ({diff.description}) -- nothing to check", file=sys.stderr)
            return 2
        changes = changes_of(root, diff)
        steps = plan(changes, read_tree(root), mode, root)
    except SelectionError as err:
        print(f"check_change: {err}", file=sys.stderr)
        return 2

    print(render(diff, changes, steps, mode))
    if mode is Mode.DEV:
        print(_NOT_EVIDENCE)
    if args.list:
        print(_AUTHORITY)
        return 0

    results: list[tuple[Step, int, str | None]] = []
    for step in steps:
        if step.disposition is Disposition.RUN:
            print(f"\ncheck_change: running {step.check.value}: {_command(step)}", flush=True)
            status, summary = run_step(root, step)
            results.append((step, status, summary))

    print("\ncheck_change: results")
    for step, status, summary in results:
        verdict = "ok" if status == 0 and summary else "FAILED"
        quoted = summary if summary else "no summary line printed -- counted as a failure"
        print(f"  {step.check.value}: {verdict} (exit {status}) -- {quoted}")
    if not results:
        print("  nothing ran here; the gate's checks run in CI")
    if mode is Mode.DEV:
        print(_NOT_EVIDENCE)
    print(_AUTHORITY)
    return exit_status(results)


def exit_status(results: Sequence[tuple[Step, int, str | None]]) -> int:
    """The first failing check's own status; a run with no summary line fails with 1."""
    for _, status, summary in results:
        if status != 0:
            return status
        if summary is None:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
