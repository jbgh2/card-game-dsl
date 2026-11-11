"""`tools/check_change.py` selects every check a diff calls for, and only those.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each selection rule CLAUDE.md "Verifying changes" and
            docs/maintaining.md state as a function of a diff fires for a
            diff in its path class and stays quiet for a diff outside it;
            each mode runs what it names (`--full` the gate exactly as
            ci.yml writes it, `--dev` the named development pass, the
            default leaving the language suite to CI); a run's status and
            summary line are the check's own; and `tools/verify.sh` takes
            its interpreter from the checkout.
domain:     every `Check` crossed with one cell per path class: every row of
            the Merge Lanes table `tools/lane-of.sh --rows` prints, plus the
            classes the rules carve inside those rows (a game, its rulebook
            twin, `_candidates.md`, a family library, a proof module, a test
            module against a helper, a `.py` against data, an `ADR-NNNN`
            citation, an unmapped root file), each at the statuses that
            change the answer. The diff reader is probed on throwaway
            repositories: no merge base, unrelated history, an empty diff, a
            detached head, a rename, a deletion, untracked files, paths with
            spaces, a committed range. The rules are the ones those two
            sources let a diff decide; the judgment rules (the audit
            trigger, two PRs green alone, whether a game edit is a RULES
            edit -- every edit of a game file is read as one) stay prose.
registry:   rules: `tools.check_change.Check`; path classes:
            `tools/lane-of.sh --rows` over docs/harness.md "The Merge Lanes";
            games, library consumers, the classifier tables, the snippet
            docs and the census modules: `tools.check_change.read_tree`;
            modes: `tools.check_change.Mode`; the gate's commands: the CI
            workflow's `check` job (`_ci_runs`).
held by:    Derived and Pinned. The rule axis is an Enum `_fires` dispatches
            over exhaustively (`_never`); the path-class axis is the lane
            table, pinned by `test_every_lane_row_has_a_cell`; the rows a
            rule keys on are refused at run time when moved
            (`check_keyed_rows`).
does not prove:  that a rule's trigger is the right one -- the expected
            column is authored from the prose, so a rule the prose states
            too narrowly is selected too narrowly here and green. Nor that
            the census scan finds every module that enumerates source
            files: it reads three spellings (`walk_packages`,
            `iter_modules`, a `*.py` string literal), and a module that
            builds its glob any other way is outside it. Nor that the local
            environment matches CI's: an interpreter without the
            `openspiel` extra skips the readiness proofs, and a venv older
            than `pyproject.toml` can hold a package the spec dropped.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest

from tools import check_change as cc

REPO = Path(__file__).resolve().parent.parent

C = cc.Check
A, M, D = cc.Status.ADDED, cc.Status.MODIFIED, cc.Status.DELETED

_ENGINE = {C.LANGUAGE_SUITE, C.TYPECHECK, C.RIGS, C.CENSUS_PINS}
_GAME = {C.LANGUAGE_SUITE, C.RIGS, C.GOLDENS_FULL, C.GAME_NAMED, C.CLASSIFIER_TABLES}
_TEST_MODULE = {C.LANGUAGE_SUITE, C.TYPECHECK, C.CENSUS_PINS, C.CHANGED_TESTS}
_NOTHING_TARGETED = {C.LANGUAGE_SUITE}

# The expected column, authored from the prose -- never computed by the
# selector. One row per cell: (status, path, cites ADR-NNNN, the rules that
# fire).
CELLS: tuple[tuple[cc.Status, str, bool, frozenset[cc.Check]], ...] = tuple(
    (status, path, cites, frozenset(expected))
    for status, path, cites, expected in (
        (M, "cardlang/grammar/cardlang.lark", False, {C.LANGUAGE_SUITE, C.RIGS}),
        (M, "cardlang/parse.py", False, _ENGINE),
        (A, "cardlang/ast/zz_probe.py", False, _ENGINE),
        (M, "cardlang/resolve.py", False, _ENGINE),
        (M, "cardlang/typecheck.py", False, _ENGINE),
        (M, "cardlang/types.py", False, _ENGINE),
        (M, "cardlang/ir.py", False, _ENGINE),
        (M, "cardlang/runtime/execute.py", False, _ENGINE),
        (D, "cardlang/openspiel/zz_probe.py", False, _ENGINE),
        (M, "cardlang/stdlib/rules.cardlang", False, {C.LANGUAGE_SUITE, C.RIGS}),
        (M, "cardlang/builtins/functions.py", False, _ENGINE),
        (M, "cardlang/cli.py", False, _ENGINE),
        (M, "docs/games/big-two.cardlang", False, _GAME),
        (D, "docs/games/big-two.cardlang", False, _GAME),
        (A, "docs/games/zz-probe-game.cardlang", False, _GAME),
        (M, "docs/games/big-two.md", False, _GAME),
        (M, "docs/games/_candidates.md", False, {C.LANGUAGE_SUITE, C.RIGS, C.GOLDENS_FULL}),
        (M, "docs/libraries/stud.cardlang", False, _GAME),
        (M, "docs/decisions.md", False, {C.LANGUAGE_SUITE, C.DOC_SNIPPETS}),
        (M, "docs/library.md", False, {C.LANGUAGE_SUITE, C.DOC_SNIPPETS}),
        (M, "docs/model.md", False, {C.LANGUAGE_SUITE, C.DOC_SNIPPETS}),
        (M, "docs/principles.md", False, _NOTHING_TARGETED),
        (M, "docs/principles.md", True, {C.LANGUAGE_SUITE, C.ADR_RECORDS}),
        (M, "docs/glossary/zz-probe.md", False, _NOTHING_TARGETED),
        (M, "CLAUDE.md", False, _NOTHING_TARGETED),
        (M, "docs/design-notes/zz-probe.md", False, _NOTHING_TARGETED),
        (M, "docs/open-questions/zz-probe.md", False, _NOTHING_TARGETED),
        (M, "docs/research/zz-probe.md", False, _NOTHING_TARGETED),
        (M, "docs/superpowers/zz-probe.md", False, _NOTHING_TARGETED),
        (A, "docs/adr/0999-zz-probe.md", False, {C.LANGUAGE_SUITE, C.ADR_RECORDS}),
        (A, "tests/test_zz_probe.py", False, _TEST_MODULE),
        (M, "tests/test_doc_references.py", False, _TEST_MODULE),
        (D, "tests/test_zz_probe.py", False, {C.LANGUAGE_SUITE, C.TYPECHECK, C.CENSUS_PINS}),
        (M, "tests/openspiel_ready/harness.py", False, {C.LANGUAGE_SUITE, C.TYPECHECK, C.CENSUS_PINS}),
        (M, "tests/openspiel_ready/test_big_two.py", False,
         _TEST_MODULE | {C.GAME_NAMED, C.CLASSIFIER_TABLES}),
        (M, "tests/zz_probe/golden.json", False, _NOTHING_TARGETED),
        (M, ".claude/skills/zz-probe/SKILL.md", False, _NOTHING_TARGETED),
        (M, ".claude/settings.json", False, _NOTHING_TARGETED),
        (M, "experiments/llm_eval/run_eval.py", False, {C.LANGUAGE_SUITE, C.TYPECHECK, C.RIGS}),
        (M, "experiments/llm_eval/tests/test_spend.py", False,
         {C.LANGUAGE_SUITE, C.TYPECHECK, C.RIGS}),
        (M, "tools/lane-of.sh", False, _NOTHING_TARGETED),
        (A, "tools/zz_probe.py", False, {C.LANGUAGE_SUITE, C.TYPECHECK, C.CENSUS_PINS}),
        (M, ".github/workflows/ci.yml", False, _NOTHING_TARGETED),
        (M, "pyproject.toml", False, {C.LANGUAGE_SUITE, C.TYPECHECK, C.RIGS}),
        (M, "README.md", False, _NOTHING_TARGETED),
        (M, "LICENSE", False, _NOTHING_TARGETED),
        (M, "conftest.py", False, {C.LANGUAGE_SUITE, C.TYPECHECK}),
    )
)


@cache
def _classes() -> dict[str, tuple[str, ...]]:
    return cc.lane_classes(str(REPO), tuple(sorted({path for _, path, _, _ in CELLS})))


@cache
def _tree() -> cc.Tree:
    return cc.read_tree(str(REPO))


def _fired(status: cc.Status, path: str, cites: bool) -> frozenset[cc.Check]:
    change = cc.Change(status, path, _classes().get(path, ()), cites)
    return frozenset(cc.triggered((change,), _tree()))


@pytest.mark.parametrize(
    ("status", "path", "cites", "check"),
    [
        pytest.param(s, p, c, check, id=f"{s.value}-{p}{'-adr' if c else ''}-{check.value}")
        for s, p, c, _ in CELLS
        for check in cc.Check
    ],
)
def test_a_rule_fires_exactly_on_its_path_class(
    status: cc.Status, path: str, cites: bool, check: cc.Check
) -> None:
    expected = next(e for s, p, c, e in CELLS if (s, p, c) == (status, path, cites))
    assert (check in _fired(status, path, cites)) == (check in expected)


def test_every_lane_row_has_a_cell() -> None:
    rows = cc.lane_rows(str(REPO))
    assert rows, "lane-of.sh --rows printed no rows"
    covered = {cls for classes in _classes().values() for cls in classes}
    missing = sorted({cls for _, _, cls in rows} - covered)
    assert not missing, f"lane-table rows with no grid cell: {missing}"


@pytest.mark.parametrize("check", list(cc.Check), ids=[c.value for c in cc.Check])
def test_every_rule_fires_somewhere_and_is_quiet_somewhere(check: cc.Check) -> None:
    """Red under: a new `Check` member with no cell that expects it."""
    assert any(check in expected for _, _, _, expected in CELLS)
    if check is not cc.Check.LANGUAGE_SUITE:
        assert any(check not in expected for _, _, _, expected in CELLS)


# --- the facts the rules read from the tree ---------------------------------


def test_the_hook_named_census_pins_are_in_the_scanned_census() -> None:
    """Red under: narrowing `_CENSUS_SCAN` to `walk_packages` alone."""
    census = set(_tree().census_modules)
    assert {"tests/test_optional_pyspiel.py", "tests/test_empty_axis_guard.py"} <= census


def test_the_classifier_tables_are_the_ones_maintaining_names() -> None:
    modules = set(_tree().classifier_modules)
    assert "tests/openspiel_ready/test_<stem>.py" in modules
    assert {
        "tests/openspiel_ready/test_coverage.py",
        "tests/openspiel_ready/test_conformance_bounds.py",
        "tests/openspiel_ready/test_provenance_openings.py",
        "tests/test_typecheck_corpus.py",
        "tests/test_chance_free.py",
        "tests/metamorphic/test_inline.py",
    } <= modules


def test_the_snippet_docs_are_the_ones_maintaining_names() -> None:
    assert _tree().snippet_docs == {"docs/decisions.md", "docs/library.md", "docs/model.md"}


def test_a_library_reaches_its_consumer_games_and_not_libraries(tmp_path: Path) -> None:
    for d, name, text in (
        ("docs/libraries", "base", ""),
        ("docs/libraries", "mid", "  uses base\n"),
        ("docs/games", "deep", "game x {\n  uses mid\n}\n"),
        ("docs/games", "near", "  uses base\n"),
        ("docs/games", "other", "// uses base in a comment\n"),
    ):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        (tmp_path / d / f"{name}.cardlang").write_text(text)
    consumers = cc._consumers(tmp_path)
    assert consumers["base"] == {"deep", "near"}
    assert consumers["mid"] == {"deep"}


def test_the_real_libraries_reach_their_games() -> None:
    consumers = _tree().library_consumers
    assert {"five-card-stud", "seven-card-stud"} <= consumers["stud"]
    assert {"holdem", "kuhn-poker"} <= consumers["poker_betting"]


def test_a_game_change_runs_every_module_naming_it_in_either_spelling() -> None:
    change = cc.Change(M, "docs/games/big-two.cardlang", _classes()["docs/games/big-two.cardlang"])
    steps = cc.plan((change,), _tree(), cc.Mode.TARGETED, str(REPO))
    run = {a for s in steps for a in s.argv}
    named = set(_tree().tests_naming("big-two"))
    assert "tests/openspiel_ready/test_big_two.py" in named
    assert named <= run


# --- what each mode does with what fired ------------------------------------


def _steps(path: str, mode: cc.Mode, status: cc.Status = M) -> dict[cc.Check, cc.Step]:
    classes = _classes()[path] if path in _classes() else cc.lane_classes(str(REPO), (path,))[path]
    change = cc.Change(status, path, classes)
    return {s.check: s for s in cc.plan((change,), _tree(), mode, str(REPO))}


def _ci_runs() -> list[str]:
    import yaml

    workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    runs = [step["run"].strip() for step in workflow["jobs"]["check"]["steps"] if "run" in step]
    return [r for r in runs if r.startswith(("mypy", "pytest"))]


def test_full_runs_the_gate_exactly_as_ci_writes_it() -> None:
    """Red under: `_gate_argv` returning `-n auto` for the full mode."""
    steps = _steps("docs/principles.md", cc.Mode.FULL)
    gate = (C.TYPECHECK, C.LANGUAGE_SUITE, C.RIGS)
    assert [" ".join(steps[c].argv) for c in gate] == _ci_runs()
    assert all(steps[c].disposition is cc.Disposition.RUN for c in gate)


@pytest.mark.parametrize("mode", list(cc.Mode), ids=[m.value for m in cc.Mode])
def test_every_mode_sweeps_the_goldens_at_full_width(mode: cc.Mode) -> None:
    step = _steps("docs/games/big-two.cardlang", mode)[C.GOLDENS_FULL]
    assert step.disposition is cc.Disposition.RUN
    assert step.env == (("CARDLANG_GOLDEN_SEEDS", "full"),)
    assert step.argv == ("pytest", "tests/test_migration_characterization.py", "-q")


def test_full_leaves_the_module_checks_inside_the_suite() -> None:
    steps = _steps("docs/games/big-two.cardlang", cc.Mode.FULL)
    for check in (C.GAME_NAMED, C.CLASSIFIER_TABLES):
        assert steps[check].disposition is cc.Disposition.IN_SUITE


@pytest.mark.parametrize("path", ["cardlang/parse.py", "docs/principles.md"])
def test_the_default_leaves_the_language_suite_to_ci_and_runs_no_dev_pass(path: str) -> None:
    steps = _steps(path, cc.Mode.TARGETED)
    assert steps[C.LANGUAGE_SUITE].disposition is cc.Disposition.IN_CI
    assert all("not slow" not in s.argv for s in steps.values())


def test_the_default_leaves_unreached_gate_checks_to_ci() -> None:
    steps = _steps("docs/principles.md", cc.Mode.TARGETED)
    assert steps[C.TYPECHECK].disposition is cc.Disposition.IN_CI
    assert steps[C.RIGS].disposition is cc.Disposition.IN_CI


def test_dev_is_the_named_development_pass() -> None:
    step = _steps("docs/principles.md", cc.Mode.DEV)[C.LANGUAGE_SUITE]
    assert step.argv == ("pytest", "-q", "-m", "not slow", "-n", "auto")


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("tests/openspiel_ready/test_big_two.py", "tests/openspiel_ready/test_big_two.py"),
        ("docs/games/hearts.cardlang", "tests/test_migration_characterization.py"),
    ],
)
def test_a_module_runs_once_however_many_checks_select_it(path: str, module: str) -> None:
    """Red under: dropping the goldens module from `taken` in `plan`."""
    steps = _steps(path, cc.Mode.TARGETED)
    modules = [a for s in steps.values() if s.argv[:1] == ("pytest",) for a in s.argv if a.endswith(".py")]
    assert len(modules) == len(set(modules))
    assert module in modules


def test_a_deleted_game_names_no_proof_module() -> None:
    change = cc.Change(D, "docs/games/zz-gone.cardlang", _classes()["docs/games/big-two.cardlang"])
    steps = {s.check: s for s in cc.plan((change,), _tree(), cc.Mode.TARGETED, str(REPO))}
    assert C.CLASSIFIER_TABLES in cc.triggered((change,), _tree())
    assert "tests/openspiel_ready/test_zz_gone.py" not in steps[C.CLASSIFIER_TABLES].argv


def test_the_keyed_rows_are_in_the_real_table() -> None:
    cc.check_keyed_rows(cc.lane_rows(str(REPO)))


@pytest.mark.parametrize(
    "rows",
    [(), (("C", "a/**", cc.CORPUS_ROW + " x"), ("C", "b/**", cc.CORPUS_ROW + " y"))],
    ids=["moved", "doubled"],
)
def test_a_moved_or_doubled_keyed_row_is_refused(rows: tuple[tuple[str, str, str], ...]) -> None:
    with pytest.raises(cc.SelectionError, match="The Merge Lanes"):
        cc.check_keyed_rows(rows)


# --- misuse probes: reading the diff ----------------------------------------


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repo, origin/main at its first commit, isolated from user git config."""
    for key, value in (
        ("GIT_CONFIG_GLOBAL", "/dev/null"), ("GIT_CONFIG_NOSYSTEM", "1"),
        ("GIT_AUTHOR_NAME", "probe"), ("GIT_AUTHOR_EMAIL", "probe@example.invalid"),
        ("GIT_COMMITTER_NAME", "probe"), ("GIT_COMMITTER_EMAIL", "probe@example.invalid"),
    ):
        monkeypatch.setenv(key, value)
    root = tmp_path / "a repo with spaces"
    for d in ("tools", "docs/games", "tests"):
        (root / d).mkdir(parents=True)
    shutil.copy(REPO / "tools/lane-of.sh", root / "tools/lane-of.sh")
    shutil.copy(REPO / "docs/harness.md", root / "docs/harness.md")
    (root / "docs/games/old-game.cardlang").write_text("game {}\n")
    (root / "tests/test_kept.py").write_text("")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(root)
    return root


def _entries(root: Path, range_: str | None = None) -> set[tuple[cc.Status, str]]:
    return set(cc.read_diff(str(root), range_).entries)


def test_no_merge_base_is_refused_naming_the_fetch(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    assert cc.main(["--list"]) == 2
    assert "git fetch" in capsys.readouterr().err


def test_unrelated_history_is_refused_naming_the_fetch(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(repo, "checkout", "-q", "--orphan", "elsewhere")
    _git(repo, "commit", "-q", "-m", "orphan")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "checkout", "-q", "main")
    assert cc.main(["--list"]) == 2
    assert "git fetch" in capsys.readouterr().err


def test_an_empty_diff_is_refused(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cc.main(["--list"]) == 2
    assert "empty diff" in capsys.readouterr().err


def test_a_detached_head_reads_its_commits(repo: Path) -> None:
    (repo / "tests/test_new.py").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    _git(repo, "checkout", "-q", "--detach")
    assert _entries(repo) == {(A, "tests/test_new.py")}


def test_a_renamed_game_contributes_both_names(repo: Path) -> None:
    _git(repo, "mv", "docs/games/old-game.cardlang", "docs/games/new-game.cardlang")
    _git(repo, "commit", "-q", "-m", "rename")
    assert _entries(repo) == {(D, "docs/games/old-game.cardlang"), (A, "docs/games/new-game.cardlang")}
    fired = cc.triggered(cc.changes_of(str(repo), cc.read_diff(str(repo), None)), _tree())
    named = " ".join(fired[C.GAME_NAMED])
    assert "old-game" in named and "new-game" in named
    assert C.GOLDENS_FULL in fired


def test_a_deleted_test_module_fires_the_census_and_does_not_run_itself(repo: Path) -> None:
    (repo / "tests/test_kept.py").unlink()
    changes = cc.changes_of(str(repo), cc.read_diff(str(repo), None))
    assert [(c.status, c.path) for c in changes] == [(D, "tests/test_kept.py")]
    fired = cc.triggered(changes, _tree())
    assert C.CENSUS_PINS in fired and C.CHANGED_TESTS not in fired


def test_paths_with_spaces_and_untracked_files_are_read_whole(repo: Path) -> None:
    (repo / "tests/sub dir").mkdir()
    (repo / "tests/sub dir/test_a b.py").write_text("# ADR-0001\n")
    (repo / "docs/design-notes").mkdir()
    (repo / "docs/design-notes/a b.md").write_text("")
    changes = {c.path: c for c in cc.changes_of(str(repo), cc.read_diff(str(repo), None))}
    assert set(changes) == {"tests/sub dir/test_a b.py", "docs/design-notes/a b.md"}
    assert changes["tests/sub dir/test_a b.py"].cites_adr
    assert any(cls.startswith("Docs — exploratory") for cls in changes["docs/design-notes/a b.md"].lane_classes)
    fired = cc.triggered(tuple(changes.values()), _tree())
    assert fired[C.CHANGED_TESTS] == ("tests/sub dir/test_a b.py",)


def test_a_range_reads_only_its_commits(repo: Path) -> None:
    (repo / "tests/test_new.py").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    (repo / "tests/test_uncommitted.py").write_text("")
    assert _entries(repo, "HEAD^..HEAD") == {(A, "tests/test_new.py")}
    assert _entries(repo) == {(A, "tests/test_new.py"), (A, "tests/test_uncommitted.py")}


# --- running: the evidence is the suite's own --------------------------------


@pytest.fixture
def fake_verify(tmp_path: Path) -> Path:
    (tmp_path / "tools").mkdir()
    script = tmp_path / "tools/verify.sh"
    script.write_text('#!/usr/bin/env bash\necho "$FAKE_OUT"\nexit "$FAKE_STATUS"\n')
    script.chmod(0o755)
    return tmp_path


@pytest.mark.parametrize(
    ("out", "status", "summary"),
    [
        ("3 passed in 0.10s", 0, "3 passed in 0.10s"),
        ("1 failed, 2 passed in 1.00s", 1, "1 failed, 2 passed in 1.00s"),
        ("Success: no issues found in 590 source files", 0, "Success: no issues found in 590 source files"),
        ("Found 2 errors in 1 file (checked 590 source files)", 1,
         "Found 2 errors in 1 file (checked 590 source files)"),
        ("Killed", 137, None),
        ("collected nothing useful", 0, None),
    ],
)
def test_a_run_reports_its_own_status_and_summary_line(
    fake_verify: Path, monkeypatch: pytest.MonkeyPatch, out: str, status: int, summary: str | None
) -> None:
    monkeypatch.setenv("FAKE_OUT", out)
    monkeypatch.setenv("FAKE_STATUS", str(status))
    step = cc.Step(C.TYPECHECK, cc.Disposition.RUN, (), ("mypy",))
    assert cc.run_step(str(fake_verify), step) == (status, summary)


@pytest.mark.parametrize(
    ("results", "status"),
    [
        ([(0, "3 passed in 0.1s")], 0),
        ([(0, "3 passed in 0.1s"), (1, "1 failed in 0.1s"), (4, None)], 1),
        ([(0, None)], 1),
        ([(137, None)], 137),
    ],
)
def test_the_exit_status_is_the_first_failing_check(results: list[tuple[int, str | None]], status: int) -> None:
    step = cc.Step(C.TYPECHECK, cc.Disposition.RUN, (), ("mypy",))
    assert cc.exit_status([(step, rc, line) for rc, line in results]) == status


def test_the_module_parses_as_the_oldest_python3_it_meets() -> None:
    """`python3 tools/check_change.py` meets macOS's system 3.9, so no newer syntax."""
    source = (REPO / "tools/check_change.py").read_text()
    ast.parse(source, feature_version=(3, 9))
    assert "from __future__ import annotations" in source


# --- tools/verify.sh: the interpreter comes from the checkout ----------------


def _fake_python(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/usr/bin/env bash\necho "{label} $*"\n')
    path.chmod(0o755)


@pytest.fixture
def verify_repo(repo: Path) -> Path:
    shutil.copy(REPO / "tools/verify.sh", repo / "tools/verify.sh")
    return repo


def _verify(cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(cwd / "tools/verify.sh"), "mypy", "--strict"],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def test_verify_takes_the_venv_beside_the_main_worktree_from_a_linked_one(verify_repo: Path) -> None:
    _fake_python(verify_repo / ".venv/bin/python", "main-venv")
    _git(verify_repo, "add", "tools/verify.sh")
    _git(verify_repo, "commit", "-q", "-m", "verify")
    linked = verify_repo.parent / "linked worktree"
    _git(verify_repo, "worktree", "add", "-q", "--detach", str(linked))
    done = _verify(linked, dict(os.environ, VIRTUAL_ENV="/nonexistent"))
    assert done.stdout.strip() == "main-venv -m mypy --strict"
    assert "the .venv beside the main worktree" in done.stderr


def test_verify_falls_back_to_virtual_env_then_python3(verify_repo: Path, tmp_path: Path) -> None:
    _fake_python(tmp_path / "ve/bin/python", "virtual-env")
    done = _verify(verify_repo, dict(os.environ, VIRTUAL_ENV=str(tmp_path / "ve")))
    assert (done.stdout.strip(), "$VIRTUAL_ENV" in done.stderr) == ("virtual-env -m mypy --strict", True)
    _fake_python(tmp_path / "bin/python3", "path-python3")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    done = _verify(verify_repo, env)
    assert (done.stdout.strip(), "python3 on PATH" in done.stderr) == ("path-python3 -m mypy --strict", True)


def test_verify_runs_mypy_without_pythonpath_and_pytest_with_the_worktree(
    verify_repo: Path, tmp_path: Path
) -> None:
    """mypy reads a PYTHONPATH entry as installed packages and silences what it follows there.

    Red under: `PYTHONPATH="$PWD"` restored on the mypy branch of verify.sh.
    """
    ve = tmp_path / "ve/bin/python"
    ve.parent.mkdir(parents=True)
    ve.write_text('#!/usr/bin/env bash\necho "PYTHONPATH=${PYTHONPATH-unset} $*"\n')
    ve.chmod(0o755)
    env = dict(os.environ, VIRTUAL_ENV=str(tmp_path / "ve"), PYTHONPATH="/elsewhere")
    for tool, expected in (("mypy", "PYTHONPATH=unset -m mypy"), ("pytest", f"PYTHONPATH={verify_repo} -m pytest")):
        done = subprocess.run(
            ["bash", str(verify_repo / "tools/verify.sh"), tool], cwd=verify_repo, env=env,
            capture_output=True, text=True,
        )
        assert done.stdout.strip() == expected


def test_verify_refuses_an_unchartered_tool(verify_repo: Path) -> None:
    done = subprocess.run(
        ["bash", str(verify_repo / "tools/verify.sh"), "ruff"], cwd=verify_repo, capture_output=True, text=True,
    )
    assert done.returncode == 2 and "only mypy and pytest are chartered" in done.stderr
