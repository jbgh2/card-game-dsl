"""`tools/check_change.py` selects every check a diff calls for, and only those.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each selection rule CLAUDE.md "Verifying changes" and
            docs/maintaining.md state as a function of a diff fires for a
            diff in its path class and stays quiet for a diff outside it;
            a changed path runs the test modules that read it; each mode
            runs what it names (`--full` every check step of ci.yml's
            `check` job as its `laptop` lane runs it, a lane expression read
            for that lane and a step the reader cannot read refused, `--dev`
            the named development pass, the
            default leaving the language suite to CI); a run is ok only on
            its own exit status and a passing summary line, and the results
            name every gate step not run; and `tools/verify.sh` takes its
            interpreter from the checkout.
domain:     every `Check` crossed with one cell per path class: every row of
            the Merge Lanes table `tools/lane-of.sh --rows` prints, plus the
            classes the rules carve inside those rows (a game, its rulebook
            twin, `_candidates.md`, a family library, a proof module, the
            snippet docs, a test module against a helper, a `.py` against
            data, an `ADR-NNNN` citation, an unmapped root file), each at
            the statuses that change the answer. A row's cell, a game's, a
            library's and a snippet doc's change a file derived from the
            table or registry that owns it (`ROW_CELLS`, `_game_cells`);
            every other file this module names by a literal path is pinned
            to exist (`NAMED_FILES`), so a moved file fails as moved. The readers rule is held by anchors: paths
            crossed with one module known, by reading it, to read the path
            by name, by directory or by import (`READER_ANCHORS`). The CI
            reader is probed with workflows it must refuse. The diff reader
            is probed on throwaway
            repositories: no merge base, unrelated history, an empty diff, a
            detached head, a rename, a deletion, untracked files, paths with
            spaces, a committed range (whose tree facts are the working
            checkout's, and say so). The rules are the ones those two
            sources let a diff decide; the judgment rules (the audit
            trigger, two PRs green alone, whether a game edit is a RULES
            edit -- every edit of a game file is read as one) stay prose.
registry:   rules: `tools.check_change.Check`; path classes:
            `tools/lane-of.sh --rows` over docs/harness.md "The Merge Lanes";
            games, library consumers, the classifier tables, the snippet
            docs, the census modules, the readers of a path and mypy's
            files: `tools.check_change.read_tree`; modes:
            `tools.check_change.Mode`; the gate's steps:
            `tools.check_change.read_gate`, checked against a YAML parse of
            the CI workflow's `check` job (`_ci_runs`).
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
            builds its glob any other way is outside it. Nor that the
            readers rule finds every module that reads a path: it finds
            the ones that name the path, its basename, its directory or the
            directory's last component as a string literal, import it, or
            sit under a changed `conftest.py`; a module that reaches a path
            any other way (a glob from the repository root, a name built at
            run time) is outside it, and only the language suite in CI
            covers it. Nor that the local
            environment matches CI's: an interpreter without the
            `openspiel` extra skips the readiness proofs, and a venv older
            than `pyproject.toml` can hold a package the spec dropped.
"""

from __future__ import annotations

import ast
import os
import re
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

# Every non-empty diff fires these, whatever its paths.
_EVERY_DIFF = frozenset({C.LANGUAGE_SUITE, C.READERS, C.GATE_IMPORT})

Cell = tuple[cc.Status, str, bool, frozenset[cc.Check]]


@cache
def _tree() -> cc.Tree:
    return cc.read_tree(str(REPO))


# The expected column, authored from the prose -- never computed by the
# selector -- one entry per Merge Lanes row CLASS: (the row's class as
# `tools/lane-of.sh --rows` prints it, from its start; a pattern a file of the
# row must match; the rules a change to such a file fires). The file each
# row's cell changes is derived from the tree, so a row whose paths move keeps
# its cell; the outcome stays authored for the class.
ROW_CELLS: tuple[tuple[str, str, frozenset[cc.Check]], ...] = tuple(
    (row, pattern, frozenset(expected))
    for row, pattern, expected in (
        ("Grammar", r"\.lark$", {C.RIGS}),
        ("Parse builders", r"\.py$", _ENGINE),
        ("AST nodes", r"\.py$", _ENGINE),
        ("Resolve", r"\.py$", _ENGINE),
        ("Typecheck", r"\.py$", _ENGINE),
        ("IR", r"\.py$", _ENGINE),
        ("Runtime", r"\.py$", _ENGINE),
        ("Stdlib", r"\.cardlang$", {C.RIGS}),
        ("docs/games/ corpus", r"^docs/games/[^_/][^/]*\.cardlang$", _GAME),
        ("Docs — the spec", r"^docs/glossary/", set()),
        ("Docs — exploratory", r"\.md$", set()),
        ("Docs — rulings", r"\.md$", {C.ADR_RECORDS}),
        ("Tests / goldens — coverage-only", r"^tests/test_[^/]*\.py$", _TEST_MODULE),
        ("Tests / goldens — anything else", r"^tests/.*\.json$", set()),
        (".claude/skills/", r"\.md$", set()),
        ("experiments/ rigs", r"\.py$", {C.TYPECHECK, C.RIGS}),
        ("tools/ harness scripts — mechanical", r"\.sh$", set()),
        ("tools/ harness scripts — semantics", r"\.py$", {C.TYPECHECK, C.CENSUS_PINS}),
        ("CI and infra", r"^\.github/", set()),
        ("Public-facing", r"", set()),
    )
)


def _glob_re(glob: str) -> re.Pattern[str]:
    """A Merge Lanes glob as a regex (`**` crosses `/`, `*` does not), to shortlist files.

    tools/lane-of.sh confirms every file this shortlists
    (`test_every_lane_row_has_a_cell`), so a disagreement here fails loudly.
    """
    out = re.escape(glob).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.compile(f"^{out}$")


@cache
def _row_cells() -> tuple[tuple[Cell, ...], tuple[str, ...], dict[str, str]]:
    """Each lane row's cell, the problems deriving them met, and each derived file's row."""
    rows = cc.lane_rows(str(REPO))
    tracked = sorted(subprocess.run(
        ["git", "ls-files"], cwd=REPO, check=True, capture_output=True, text=True,
    ).stdout.splitlines())
    excluded = set(_tree().snippet_docs)
    cells: list[Cell] = []
    problems: list[str] = []
    row_of: dict[str, str] = {}
    for prefix, _, _ in ROW_CELLS:
        if not any(cls.startswith(prefix) for _, _, cls in rows):
            problems.append(f"ROW_CELLS names {prefix!r}, which no Merge Lanes row's class starts with")
    for cls in sorted({cls for _, _, cls in rows}):
        entries = [e for e in ROW_CELLS if cls.startswith(e[0])]
        if len(entries) != 1:
            problems.append(f"Merge Lanes row {cls!r} matches {len(entries)} ROW_CELLS entries; author one")
            continue
        _, pattern, expected = entries[0]
        globs = [_glob_re(g) for _, g, c in rows if c == cls]
        found = [
            f for f in tracked
            if f not in excluded and any(g.match(f) for g in globs) and re.search(pattern, f)
        ]
        if not found:
            problems.append(
                f"Merge Lanes row {cls!r} holds no tracked file matching {pattern!r}; update ROW_CELLS"
            )
            continue
        row_of[found[0]] = cls
        cells.append((M, found[0], False, expected | _EVERY_DIFF))
    return tuple(cells), tuple(problems), row_of


@cache
def _game_cells() -> tuple[Cell, ...]:
    """A game with a rulebook twin and a proof module, and a family library with a consumer game."""
    tree = _tree()
    game = next(
        g for g in sorted(tree.games)
        if (REPO / f"docs/games/{g}.md").is_file()
        and (REPO / f"tests/openspiel_ready/test_{cc.fold(g)}.py").is_file()
    )
    library = next(lib for lib in sorted(tree.library_consumers) if tree.library_consumers[lib])
    proof = _TEST_MODULE | {C.GAME_NAMED, C.CLASSIFIER_TABLES}
    return tuple(
        (status, path, False, frozenset(expected) | _EVERY_DIFF)
        for status, path, expected in (
            (M, f"docs/games/{game}.cardlang", _GAME),
            (D, f"docs/games/{game}.cardlang", _GAME),
            (M, f"docs/games/{game}.md", _GAME),
            (M, f"tests/openspiel_ready/test_{cc.fold(game)}.py", proof),
            (M, f"docs/libraries/{library}.cardlang", _GAME),
        )
    ) + tuple(
        (M, doc, False, frozenset({C.DOC_SNIPPETS}) | _EVERY_DIFF) for doc in sorted(tree.snippet_docs)
    )


# Cells whose path is a hypothetical file (`zz_probe`) or one of the named
# files `NAMED_FILES` pins to exist. One row per cell: (status, path, cites
# ADR-NNNN, the rules that fire).
_AUTHORED: tuple[Cell, ...] = tuple(
    (status, path, cites, frozenset(expected) | _EVERY_DIFF)
    for status, path, cites, expected in (
        (A, "cardlang/ast/zz_probe.py", False, _ENGINE),
        (D, "cardlang/openspiel/zz_probe.py", False, _ENGINE),
        (M, "cardlang/zz_probe.py", False, _ENGINE),
        (A, "docs/games/zz-probe-game.cardlang", False, _GAME),
        (M, "docs/games/_candidates.md", False, {C.RIGS, C.GOLDENS_FULL}),
        (M, "docs/principles.md", False, set()),
        (M, "docs/principles.md", True, {C.ADR_RECORDS}),
        (M, "docs/glossary/zz-probe.md", False, set()),
        (M, "CLAUDE.md", False, set()),
        (M, "docs/design-notes/zz-probe.md", False, set()),
        (M, "docs/open-questions/zz-probe.md", False, set()),
        (M, "docs/research/zz-probe.md", False, set()),
        (M, "docs/superpowers/zz-probe.md", False, set()),
        (A, "docs/adr/0999-zz-probe.md", False, {C.ADR_RECORDS}),
        (A, "tests/test_zz_probe.py", False, _TEST_MODULE),
        (D, "tests/test_zz_probe.py", False, {C.TYPECHECK, C.CENSUS_PINS}),
        (M, "tests/openspiel_ready/harness.py", False, {C.TYPECHECK, C.CENSUS_PINS}),
        (M, "tests/zz_probe/golden.json", False, set()),
        (M, ".claude/skills/zz-probe/SKILL.md", False, set()),
        (M, ".claude/settings.json", False, set()),
        (M, "experiments/llm_eval/tests/test_spend.py", False, {C.TYPECHECK, C.RIGS}),
        (M, "tools/lane-of.sh", False, set()),
        (A, "tools/zz_probe.py", False, {C.TYPECHECK, C.CENSUS_PINS}),
        (M, "pyproject.toml", False, {C.TYPECHECK, C.RIGS}),
        (M, "conftest.py", False, {C.TYPECHECK}),
    )
)

CELLS: tuple[Cell, ...] = tuple(
    {(c[0], c[1], c[2]): c for c in reversed(_AUTHORED + _row_cells()[0] + _game_cells())}.values()
)

# Every file of the repository this module names by a literal path, with the
# table that names it: a file that moves fails here as moved, never as a
# missing lane row or a vacuous pass.
NAMED_FILES: tuple[tuple[str, str], ...] = (
    ("docs/games/_candidates.md", "_AUTHORED"),
    ("docs/principles.md", "_AUTHORED"),
    ("CLAUDE.md", "_AUTHORED and READER_ANCHORS"),
    ("tests/openspiel_ready/harness.py", "_AUTHORED and READER_ANCHORS"),
    (".claude/settings.json", "_AUTHORED"),
    ("experiments/llm_eval/tests/test_spend.py", "_AUTHORED"),
    ("tools/lane-of.sh", "_AUTHORED, READER_ANCHORS and the misuse probes"),
    ("tools/verify.sh", "the verify.sh probes"),
    ("docs/harness.md", "the misuse probes"),
    (".github/workflows/ci.yml", "READER_ANCHORS and `_ci_runs`"),
    ("pyproject.toml", "_AUTHORED"),
    ("docs/glossary/library.md", "READER_ANCHORS"),
    ("docs/authoring.md", "READER_ANCHORS"),
    ("tests/rejections", "READER_ANCHORS"),
    ("tests/golden/belote_stream_hashes.json", "READER_ANCHORS"),
    ("tests/fixtures/blind_decisions/blind_draw.cardlang", "READER_ANCHORS"),
    ("cardlang/grammar/cardlang.lark", "READER_ANCHORS"),
    ("cardlang/stdlib/rules.cardlang", "READER_ANCHORS"),
    ("tests/native_oracle.py", "READER_ANCHORS"),
    ("tests/conftest.py", "READER_ANCHORS"),
    ("tools/review_record.py", "READER_ANCHORS"),
    ("tests/test_glossary.py", "READER_ANCHORS"),
    ("tests/test_doc_references.py", "READER_ANCHORS"),
    ("tests/test_rejections.py", "READER_ANCHORS"),
    ("tests/test_trick_order_migration.py", "READER_ANCHORS"),
    ("tests/openspiel_ready/test_blind_decisions.py", "READER_ANCHORS"),
    ("tests/test_card_points.py", "READER_ANCHORS"),
    ("tests/test_library_notes.py", "READER_ANCHORS"),
    ("tests/test_differential_hex.py", "READER_ANCHORS"),
    ("tests/openspiel_ready/test_spades.py", "READER_ANCHORS"),
    ("tests/test_parse.py", "READER_ANCHORS"),
    ("tests/test_review_record.py", "READER_ANCHORS"),
    ("docs/games/big-two.cardlang", "the game-name, goldens and dedupe pins"),
    ("tests/openspiel_ready/test_big_two.py", "the game-name and dedupe pins"),
    ("docs/games/hearts.cardlang", "the dedupe pin"),
    ("tests/test_migration_characterization.py", "the goldens and dedupe pins"),
    ("tests/test_asked_event.py", "the folded-spelling pin"),
    ("tests/openspiel_ready/test_ismcts.py", "the folded-spelling pin"),
    ("tests/test_optional_pyspiel.py", "the census pin"),
    ("tests/test_empty_axis_guard.py", "the census pin"),
)


@pytest.mark.parametrize(("path", "where"), NAMED_FILES, ids=[p for p, _ in NAMED_FILES])
def test_every_file_this_module_names_exists(path: str, where: str) -> None:
    """Red under: renaming any one of them (as the resolve split moves `cardlang/resolve.py`)."""
    assert (REPO / path).exists(), (
        f"{path} moved or was deleted: update {where} in tests/test_check_change.py"
    )


def test_the_folded_spelling_anchors_still_name_only_the_folded_spelling() -> None:
    for module in ("tests/test_asked_event.py", "tests/openspiel_ready/test_ismcts.py"):
        text = (REPO / module).read_text()
        assert "big_two" in text and "big-two" not in text, (
            f"{module} no longer names only `big_two`: re-anchor "
            "test_a_module_naming_only_the_folded_spelling_is_found"
        )


@cache
def _classes() -> dict[str, tuple[str, ...]]:
    return cc.lane_classes(str(REPO), tuple(sorted({path for _, path, _, _ in CELLS})))


def _lane(path: str) -> tuple[str, ...]:
    """A path's Merge Lanes rows, for a path no cell names as well as one that does."""
    return _classes()[path] if path in _classes() else cc.lane_classes(str(REPO), (path,))[path]


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
    """Red under: a row added to the Merge Lanes table with no ROW_CELLS entry."""
    rows = cc.lane_rows(str(REPO))
    assert rows, "lane-of.sh --rows printed no rows"
    _, problems, row_of = _row_cells()
    assert not problems, "\n".join(problems)
    for path, cls in row_of.items():
        assert cls in _classes()[path], (
            f"{path} was derived for row {cls!r}, but tools/lane-of.sh places it in {_classes()[path]}"
        )
    covered = {cls for classes in _classes().values() for cls in classes}
    missing = sorted({cls for _, _, cls in rows} - covered)
    assert not missing, f"lane-table rows with no grid cell: {missing}"


@pytest.mark.parametrize("check", list(cc.Check), ids=[c.value for c in cc.Check])
def test_every_rule_fires_somewhere_and_is_quiet_somewhere(check: cc.Check) -> None:
    """Red under: a new `Check` member with no cell that expects it."""
    assert any(check in expected for _, _, _, expected in CELLS)
    if check not in _EVERY_DIFF:
        assert any(check not in expected for _, _, _, expected in CELLS)


# Independent anchors: a changed path and one test module known, by reading
# that module, to read the path (by name, by directory, or by import). The
# selection must run the module; the anchor is never taken from the selector.
READER_ANCHORS: tuple[tuple[cc.Status, str, str], ...] = (
    (M, "docs/glossary/library.md", "tests/test_glossary.py"),
    (M, "docs/authoring.md", "tests/test_doc_references.py"),
    (M, "CLAUDE.md", "tests/test_doc_references.py"),
    (A, "tests/rejections/zz_probe.cardlang", "tests/test_rejections.py"),
    (A, "tests/rejections/zz_probe.expected", "tests/test_rejections.py"),
    (M, "tests/golden/belote_stream_hashes.json", "tests/test_trick_order_migration.py"),
    (M, "tests/fixtures/blind_decisions/blind_draw.cardlang", "tests/openspiel_ready/test_blind_decisions.py"),
    (M, "tools/lane-of.sh", "tests/test_check_change.py"),
    (M, ".github/workflows/ci.yml", "tests/test_check_change.py"),
    (M, "cardlang/grammar/cardlang.lark", "tests/test_card_points.py"),
    (M, "cardlang/stdlib/rules.cardlang", "tests/test_library_notes.py"),
    (M, "tests/native_oracle.py", "tests/test_differential_hex.py"),
    (M, "tests/openspiel_ready/harness.py", "tests/openspiel_ready/test_spades.py"),
    (M, "tests/conftest.py", "tests/test_parse.py"),
    (M, "tools/review_record.py", "tests/test_review_record.py"),
)


def _run_modules(steps: dict[cc.Check, cc.Step]) -> set[str]:
    return {a for s in steps.values() if s.argv[:1] == ("pytest",) for a in s.argv if a.endswith(".py")}


@pytest.mark.parametrize(("status", "path", "module"), READER_ANCHORS, ids=[p for _, p, _ in READER_ANCHORS])
def test_a_changed_path_runs_the_modules_that_read_it(status: cc.Status, path: str, module: str) -> None:
    assert module in _run_modules(_steps(path, cc.Mode.TARGETED, status))


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
    change = cc.Change(M, "docs/games/big-two.cardlang", _lane("docs/games/big-two.cardlang"))
    steps = cc.plan((change,), _tree(), cc.Mode.TARGETED, str(REPO))
    run = {a for s in steps for a in s.argv}
    named = set(_tree().tests_naming("big-two"))
    assert "tests/openspiel_ready/test_big_two.py" in named
    assert named <= run


def test_a_module_naming_only_the_folded_spelling_is_found() -> None:
    """Red under: dropping `-e fold(name)` from the game-name `git grep`.

    Both modules name `big_two` and never `big-two` (read by hand).
    """
    assert {"tests/test_asked_event.py", "tests/openspiel_ready/test_ismcts.py"} <= set(
        _tree().tests_naming("big-two")
    )


# --- what each mode does with what fired ------------------------------------


def _steps(path: str, mode: cc.Mode, status: cc.Status = M) -> dict[cc.Check, cc.Step]:
    change = cc.Change(status, path, _lane(path))
    return {s.check: s for s in cc.plan((change,), _tree(), mode, str(REPO))}


def _ci_runs() -> list[str]:
    """The check job's single-line `run:` lines no other lane owns, read by a YAML parser.

    The parse is independent of `read_gate`; the lane filter is the one
    fact both read, the step's `if:` naming a lane other than `laptop`.
    """
    import yaml

    workflow = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    return [
        step["run"].strip() for step in workflow["jobs"]["check"]["steps"]
        if "run" in step and "\n" not in step["run"].strip()
        and not re.fullmatch(r"needs\.route\.outputs\.lane == '(?!laptop')[^']+'", step.get("if", ""))
    ]


def test_full_runs_every_check_step_ci_writes() -> None:
    """Red under: `read_gate` skipping the `python -c "import pyspiel"` step.

    Reads the live workflow, so a check job whose shape the reader cannot
    read fails here, and at collection, by name.
    """
    steps = _steps("docs/principles.md", cc.Mode.FULL)
    gate = _tree().gate
    assert [g.ci_text for g in gate] == _ci_runs()
    for g in gate:
        assert steps[g.check].disposition is cc.Disposition.RUN
        assert steps[g.check].argv == g.argv
    assert [g.argv for g in gate] == [
        ("import", "pyspiel"), ("mypy",), ("pytest", "-q", "-n", "8"),
        ("pytest", "experiments/llm_eval/tests", "-q"),
    ]


def test_the_live_suite_step_says_it_was_read_for_the_laptop_lane() -> None:
    reasons = _steps("docs/principles.md", cc.Mode.FULL)[C.LANGUAGE_SUITE].reasons
    assert any("for the laptop lane, which a local run is" in r for r in reasons)


_CI_HEAD = "jobs:\n  check:\n    runs-on: x\n    steps:\n      - uses: actions/checkout@v4\n"
_LANE_N = "${{ needs.route.outputs.lane == 'laptop' && '8' || 'auto' }}"
_CI_GATE = (
    '      - name: Imports\n        run: python -c "import pyspiel"\n'
    "      - name: Types\n        run: mypy\n"
    f"      - name: Suite\n        run: pytest -q -n {_LANE_N}\n"
    "      - name: Rigs\n        run: pytest experiments/llm_eval/tests -q\n"
)
_HOSTED_SETUP = (
    "      - uses: actions/setup-python@v5\n        if: needs.route.outputs.lane == 'hosted'\n"
    "        with:\n          python-version: \"3.11\"\n"
    "      - name: Install\n        if: needs.route.outputs.lane == 'hosted'\n"
    '        run: python -m pip install -e ".[dev,openspiel]"\n'
)
_GUARD = (
    "      - name: The route picked a lane\n        if: needs.route.result != 'success'\n"
    "        run: |\n          echo no lane\n          exit 1\n"
)


def test_the_gate_reader_reads_setup_and_other_lanes_as_skipped() -> None:
    """Red under: `read_gate` without its other-lane branch (the hosted `Install` run is then refused)."""
    text = (
        _CI_HEAD + _GUARD
        + "      - name: Venv\n        if: needs.route.outputs.lane == 'laptop'\n"
        + "        run: |\n          pip install x\n          mypy\n"
        + _HOSTED_SETUP + _CI_GATE
    )
    gate, setup = cc.read_gate(text + "  canary:\n    steps:\n      - run: echo hi\n")
    assert [g.check for g in gate] == [C.GATE_IMPORT, C.TYPECHECK, C.LANGUAGE_SUITE, C.RIGS]
    assert setup == (
        "`actions/checkout@v4` (environment setup)",
        "`The route picked a lane` (a setup step under `if: needs.route.result != 'success'`)",
        "`Venv` (environment setup)",
        "`actions/setup-python@v5` (the hosted lane's step)",
        "`Install` (the hosted lane's step)",
    )


@pytest.mark.parametrize(
    ("expression", "argv"),
    [
        ("${{ needs.route.outputs.lane == 'laptop' && '8' || 'auto' }}", ("pytest", "-q", "-n", "8")),
        ("${{ needs.route.outputs.lane == 'hosted' && 'auto' || '4' }}", ("pytest", "-q", "-n", "4")),
    ],
    ids=["laptop-branch", "other-lane-branch"],
)
def test_a_lane_expression_is_read_for_the_laptop_lane(expression: str, argv: tuple[str, ...]) -> None:
    """Red under: `_resolve` taking the expression's first value whatever lane it names."""
    gate, _ = cc.read_gate(_CI_HEAD + _CI_GATE.replace(_LANE_N, expression))
    step = next(g for g in gate if g.check is C.LANGUAGE_SUITE)
    assert step.argv == argv
    assert "for the laptop lane" in step.note


@pytest.mark.parametrize(
    "expression",
    [
        "${{ matrix.workers }}",
        "${{ needs.route.outputs.lane == 'laptop' && '' || 'auto' }}",
        "${{ needs.route.outputs.lane != 'laptop' && 'auto' || '8' }}",
    ],
    ids=["other-context", "empty-first-value", "negated-lane"],
)
def test_an_expression_shape_the_reader_cannot_read_is_refused_by_name(expression: str) -> None:
    """Red under: `_resolve` leaving an unread expression in the command for `_gate_step` to judge."""
    with pytest.raises(cc.SelectionError, match="whose expression"):
        cc.read_gate(_CI_HEAD + _CI_GATE.replace(_LANE_N, expression))


@pytest.mark.parametrize(
    "extra",
    [
        "      - name: Lint\n        run: ruff check .\n",
        "      - name: Tools\n        run: pytest tools/tests -q\n",
        "      - name: Again\n        run: mypy\n",
        "      - name: Laptop lint\n        if: needs.route.outputs.lane == 'laptop'\n        run: ruff check .\n",
    ],
    ids=["unknown-command", "unknown-pytest-target", "doubled-step", "unknown-laptop-lane-run"],
)
def test_a_check_step_the_reader_cannot_read_is_refused(extra: str) -> None:
    with pytest.raises(cc.SelectionError, match="check job"):
        cc.read_gate(_CI_HEAD + _CI_GATE + extra)


def test_a_check_under_a_condition_the_reader_cannot_read_is_refused() -> None:
    """Red under: `read_gate` reading a single-line run under any `if:` as unconditional."""
    types = "      - name: Types\n        run: mypy\n"
    conditioned = "      - name: Types\n        if: github.event_name == 'push'\n        run: mypy\n"
    with pytest.raises(cc.SelectionError, match="a condition tools/check_change.py cannot read"):
        cc.read_gate(_CI_HEAD + _CI_GATE.replace(types, conditioned))


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


def test_the_default_runs_the_gate_checks_the_diff_reaches() -> None:
    """Red under: `in_ci = mode is Mode.TARGETED` in `plan`."""
    steps = _steps("cardlang/parse.py", cc.Mode.TARGETED)
    assert steps[C.TYPECHECK].disposition is cc.Disposition.RUN
    assert steps[C.RIGS].disposition is cc.Disposition.RUN
    assert steps[C.GATE_IMPORT].disposition is cc.Disposition.RUN


def test_the_default_leaves_unreached_gate_checks_to_ci() -> None:
    steps = _steps("docs/principles.md", cc.Mode.TARGETED)
    assert steps[C.TYPECHECK].disposition is cc.Disposition.IN_CI
    assert steps[C.RIGS].disposition is cc.Disposition.IN_CI


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("cardlang/parse.py", "cardlang/parse.py"),
        ("pyproject.toml", "pyproject.toml (mypy's configuration)"),
        ("tools/zz_probe.py", "tools/zz_probe.py (outside mypy's `files`: checked only through a module that imports it)"),
    ],
)
def test_the_type_check_never_claims_to_read_a_file_outside_its_files(path: str, reason: str) -> None:
    assert _steps(path, cc.Mode.TARGETED)[C.TYPECHECK].reasons == (reason,)


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
    change = cc.Change(D, "docs/games/zz-gone.cardlang", _lane("docs/games/big-two.cardlang"))
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


def test_a_range_says_its_tree_facts_are_the_working_checkouts(repo: Path) -> None:
    (repo / "tests/test_new.py").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    diff = cc.read_diff(str(repo), "HEAD^..HEAD")
    assert "come from the working checkout" in diff.tree_note and "not from HEAD" in diff.tree_note
    assert cc.read_diff(str(repo), None).tree_note == ""


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
    ("status", "summary", "ok"),
    [
        (0, "3 passed in 0.10s", True),
        (0, "2912 passed, 15 skipped in 897.43s (0:14:57)", True),
        (0, "3 passed, 10 deselected in 0.10s", True),
        (0, "Success: no issues found in 590 source files", True),
        (0, "import pyspiel: ok", True),
        (0, "12 skipped in 0.50s", False),
        (0, "10 deselected in 0.50s", False),
        (0, "no tests ran in 0.01s", False),
        (0, None, False),
        (1, "1 failed, 2 passed in 1.00s", False),
    ],
)
def test_a_run_is_ok_only_when_its_summary_reports_a_pass(status: int, summary: str | None, ok: bool) -> None:
    assert cc.verdict(status, summary) is ok
    step = cc.Step(C.TYPECHECK, cc.Disposition.RUN, (), ("mypy",))
    block = cc.render_results([(step, status, summary)], [step], cc.Mode.TARGETED, _tree())
    assert ("typecheck: ok" in block) is ok
    assert ("typecheck: FAILED" in block) is not ok


@pytest.mark.parametrize("mode", list(cc.Mode), ids=[m.value for m in cc.Mode])
def test_the_results_name_every_gate_step_not_run(mode: cc.Mode) -> None:
    """Red under: the results block listing only the steps that ran."""
    steps = list(cc.plan((cc.Change(M, "docs/principles.md", ()),), _tree(), mode, str(REPO)))
    ran = [s for s in steps if s.disposition is cc.Disposition.RUN]
    results = [(s, 0, "3 passed in 0.1s") for s in ran]
    block = cc.render_results(results, steps, mode, _tree())
    if mode is cc.Mode.FULL:
        assert "NOT a green of the gate" not in block
    else:
        assert "NOT RUN here: language-suite (CI runs `pytest -q -n ${{" in block
        assert "This is NOT a green of the gate" in block
    if mode is cc.Mode.DEV:
        assert "NOT evidence" in block


def test_a_run_that_ran_nothing_says_it_is_no_green() -> None:
    block = cc.render_results([], [], cc.Mode.TARGETED, _tree())
    assert "nothing ran here" in block and "This is NOT a green of the gate" in block


@pytest.mark.parametrize(
    ("results", "status"),
    [
        ([(0, "3 passed in 0.1s")], 0),
        ([(0, "3 passed in 0.1s"), (1, "1 failed in 0.1s"), (4, None)], 1),
        ([(0, None)], 1),
        ([(0, "12 skipped in 0.5s")], 1),
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


@pytest.mark.parametrize("args", [(), ("os; print(1)",), ("os", "sys")], ids=["none", "code", "two"])
def test_verify_imports_one_dotted_name_only(verify_repo: Path, args: tuple[str, ...]) -> None:
    done = subprocess.run(
        ["bash", str(verify_repo / "tools/verify.sh"), "import", *args], cwd=verify_repo,
        capture_output=True, text=True,
    )
    assert done.returncode == 2 and "import takes one dotted module name" in done.stderr


def test_verify_refuses_an_unchartered_tool(verify_repo: Path) -> None:
    done = subprocess.run(
        ["bash", str(verify_repo / "tools/verify.sh"), "ruff"], cwd=verify_repo, capture_output=True, text=True,
    )
    assert done.returncode == 2 and "only mypy, pytest and import are chartered" in done.stderr
