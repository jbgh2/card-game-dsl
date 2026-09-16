"""The settled-code report (`tools/settled_code.py`) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   every engine module appears exactly once with three facts derived
            from their sources and nothing else: its two ages from git (any
            commit; focused commits, a sweep touching SWEEP_FILES+ modules
            excluded), its statements executed per oracle from a coverage
            JSON with contexts, and the open issues naming it by path or
            dotted module; a settled module is one whose focused age reaches
            SETTLED_DAYS, and thin is under THIN_COVERAGE of its statements
            under any context.
domain:     synthetic git logs, issue lists and coverage JSONs built here, so
            no cell depends on what the tree or the tracker holds today; the
            tree-facing pins are that the real tree renders offline with
            every engine file once, and that every ORACLES selection resolves
            to files that exist, so the registry cannot name a suite that
            moved.
registry:   engine modules: `tools.settled_code.engine_files`; oracles:
            `tools.settled_code.ORACLES`; the git log parser:
            `tools.settled_code.parse_git_log`; the coverage reader:
            `tools.settled_code.parse_coverage`; citations:
            `tools.settled_code.cited_files`.
does not prove:  that a settled, thin, named module SHOULD be refactored --
            the report is an input to the direction review, which owns that
            call; nor that the oracle columns are exact beyond what the
            coverage JSON records (a line executed only in a `-n` worker is
            unmeasured, which is why `measure` runs serially); nor that a
            citation by bare basename is meant -- it is deliberately not a
            citation, so an issue that names `observe.py` alone is not
            counted, and that cell is the wall this ledger names rather than
            a gap; nor that SWEEP_FILES draws the line where a reader would:
            a doc-link pass one module short of it counts as focused and
            makes its files read younger, which errs toward "not settled",
            the safe side for a refactor decision, and is the wall.
"""

from __future__ import annotations

import json
import pathlib

from tools import settled_code as sc

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAY = 86400
NOW = 1_800_000_000

FILES = ["cardlang/a.py", "cardlang/pkg/__init__.py", "cardlang/pkg/b.py"]


def _log(*commits: tuple[int, list[str]]) -> str:
    return "\n".join(f"{ts}\n\n" + "\n".join(paths) + "\n" for ts, paths in commits)


def test_git_log_two_ages_and_sweeps_do_not_count() -> None:
    sweep = [f"cardlang/s{i}.py" for i in range(sc.SWEEP_FILES - 1)] + ["cardlang/a.py"]
    files = FILES + sweep
    text = _log(
        (NOW - 1 * DAY, sweep),  # a sweep: touches SWEEP_FILES engine modules
        (NOW - 200 * DAY, ["cardlang/a.py", "old/renamed.py"]),
        (NOW - 10 * DAY, ["cardlang/pkg/b.py"]),
    )
    h = sc.parse_git_log(text, files, NOW)
    assert h["cardlang/a.py"].last_change == NOW - 1 * DAY
    assert h["cardlang/a.py"].last_focused == NOW - 200 * DAY
    assert h["cardlang/a.py"].commits_recent == 0
    assert h["cardlang/a.py"].commits_total == 2
    assert h["cardlang/pkg/b.py"].commits_recent == 1
    assert "cardlang/pkg/__init__.py" not in h  # no commit names it: absent, not new
    assert "old/renamed.py" not in h


def test_a_file_touched_only_by_sweeps_has_no_focused_age() -> None:
    sweep = [f"cardlang/s{i}.py" for i in range(sc.SWEEP_FILES)]
    h = sc.parse_git_log(_log((NOW - 5 * DAY, sweep)), sweep, NOW)
    row = sc.Row(sweep[0], 1, h[sweep[0]], None, ())
    assert row.age_days(NOW) == 5
    assert row.focused_age_days(NOW) is None


def test_citations_by_path_and_dotted_module_never_by_basename() -> None:
    text = (
        "see cardlang/a.py and `cardlang.pkg.b` and the package cardlang.pkg; "
        "b.py alone is not a citation, nor is cardlang/missing.py"
    )
    assert sc.cited_files(text, FILES) == {
        "cardlang/a.py",
        "cardlang/pkg/b.py",
        "cardlang/pkg/__init__.py",
    }
    issues = [
        {"number": 7, "title": "cardlang/a.py again", "body": ""},
        {"number": 3, "title": "", "body": "cardlang.pkg.b"},
        {"number": 5, "title": "", "body": "cardlang/a.py"},
    ]
    assert sc.issue_citations(issues, FILES) == {
        "cardlang/a.py": [5, 7],
        "cardlang/pkg/b.py": [3],
    }


def _cov(
    path: str,
    statements: int,
    lines: dict[int, list[str]],
    executed: list[int] | None = None,
) -> dict[str, object]:
    return {
        "files": {
            path: {
                "summary": {"num_statements": statements},
                "executed_lines": sorted(lines) if executed is None else executed,
                "contexts": {str(k): v for k, v in lines.items()},
            }
        }
    }


def test_coverage_counts_per_oracle_and_ignores_unknown_contexts() -> None:
    first = next(iter(sc.ORACLES))
    data = _cov(
        "cardlang/a.py", 10, {1: [first], 2: [first, "stray"], 3: [""], 4: ["stray"]}
    )
    cov = sc.parse_coverage(data, FILES)["cardlang/a.py"]
    assert cov.statements == 10
    assert cov.executed == 4  # every executed line counts toward the total
    assert cov.by_oracle[first] == 2  # only the named oracle's column grows
    assert all(cov.by_oracle[n] == 0 for n in sc.ORACLES if n != first)


def test_only_executed_statements_count_not_every_traced_line() -> None:
    """Reddened by counting the contexts map's keys: coverage keys it by every
    physical line the tracer saw -- a docstring's first line, a continuation
    line -- so the count exceeds the statement total (measured 2026-09-16 on
    the real tree: a module rendering 215% executed)."""
    first = next(iter(sc.ORACLES))
    data = _cov(
        "cardlang/a.py",
        3,
        {1: [first], 2: [first], 3: [first], 4: [first]},
        executed=[2, 3],
    )
    cov = sc.parse_coverage(data, FILES)["cardlang/a.py"]
    assert cov.executed == 2 and cov.by_oracle[first] == 2
    row = sc.Row("cardlang/a.py", 4, None, cov, ())
    fraction = row.covered_fraction()
    assert fraction is not None and fraction <= 1.0


def test_coverage_keys_relative_to_another_cwd_still_match() -> None:
    data = _cov("/somewhere/else/cardlang/a.py", 2, {1: ["proofs"]})
    assert "cardlang/a.py" in sc.parse_coverage(data, FILES)


def test_settled_is_focused_age_and_thin_is_any_context() -> None:
    old = sc.History(NOW - 1 * DAY, NOW - (sc.SETTLED_DAYS + 1) * DAY, 0, 3)
    young = sc.History(NOW - 1 * DAY, NOW - 1 * DAY, 1, 1)
    thin = sc.Coverage(10, 4, {n: 0 for n in sc.ORACLES})
    thick = sc.Coverage(10, 9, {n: 0 for n in sc.ORACLES})
    rows = (
        sc.Row("cardlang/a.py", 10, old, thin, (5,)),
        sc.Row("cardlang/pkg/b.py", 10, old, thick, ()),
        sc.Row("cardlang/pkg/__init__.py", 1, young, thin, (9,)),
    )
    rep = sc.Report(rows, NOW, measured=True)
    assert [r.path for r in rep.settled()] == ["cardlang/a.py", "cardlang/pkg/b.py"]
    text = rep.render()
    assert (
        "both thin and named -- a refactor here has a reason and thin oracle cover (1): cardlang/a.py"
        in text
    )
    assert "thin under the oracles (1): cardlang/a.py" in text
    assert "named by an open issue (1): cardlang/a.py" in text
    assert text == rep.render()  # deterministic


def test_rows_render_in_path_order_never_by_age() -> None:
    old = sc.History(NOW - 300 * DAY, NOW - 300 * DAY, 0, 1)
    young = sc.History(NOW - 1 * DAY, NOW - 1 * DAY, 1, 1)
    rows = (
        sc.Row("cardlang/z.py", 1, old, None, ()),
        sc.Row("cardlang/a.py", 1, young, None, ()),
    )
    text = sc.Report(rows, NOW, measured=False).render()
    assert text.index("| cardlang/a.py |") < text.index("| cardlang/z.py |")


def test_every_oracle_run_measures_its_child_processes(tmp_path: pathlib.Path) -> None:
    """Reddened by dropping `patch = subprocess` from the configuration: the
    goldens' capture interpreter and every `-n` worker would then go
    unmeasured, and a column would count the parent process alone (measured
    2026-09-16 on the goldens: 6% of the engine from the parent, 65% with
    the children)."""
    for name in sc.ORACLES:
        cfg = sc.coverage_config(name, tmp_path)
        assert "patch = subprocess" in cfg
        assert f"context = {name}" in cfg
        assert "parallel = true" in cfg


def test_unmeasured_report_says_so_instead_of_deriving_thin() -> None:
    row = sc.Row("cardlang/a.py", 3, sc.History(NOW, NOW, 1, 1), None, ())
    text = sc.Report((row,), NOW, measured=False).render()
    assert "UNMEASURED" in text
    assert "thin under the oracles" not in text


def test_real_tree_renders_offline_with_every_engine_file_once() -> None:
    files = sc.engine_files(ROOT)
    assert files == sorted(set(files)) and "cardlang/parse.py" in files
    rep = sc.report(ROOT, issues=[], coverage=None, now=NOW)
    assert [r.path for r in rep.rows] == files
    text = rep.render()
    assert all(f"| {f} |" in text for f in files)


def test_every_oracle_selection_resolves_to_files_on_disk() -> None:
    for name, selection in sc.ORACLES.items():
        paths = [
            s for s in selection if not s.startswith("-") and s not in ("not slow",)
        ]
        for pat in paths:
            hits = list(ROOT.glob(pat))
            assert hits, f"oracle {name!r}: {pat} names nothing on disk"


def test_main_renders_from_a_coverage_file(
    tmp_path: pathlib.Path, capsys: object
) -> None:
    import pytest

    cap = capsys
    assert isinstance(cap, pytest.CaptureFixture)
    cov = tmp_path / "coverage.json"
    cov.write_text(json.dumps(_cov("cardlang/parse.py", 1, {1: ["proofs"]})))
    assert sc.main(["--no-issues", "--coverage-json", str(cov)]) == 0
    out = cap.readouterr().out
    assert "| cardlang/parse.py |" in out and "UNMEASURED" not in out
