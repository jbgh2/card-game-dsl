"""`tools/check_change.py` selects every check a diff calls for, and only those.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each selection rule CLAUDE.md "Verifying changes" and
            docs/maintaining.md state as a function of a diff fires for a
            diff in its path class and stays quiet for a diff outside it.
domain:     every `Check` crossed with one cell per path class: every row of
            the Merge Lanes table `tools/lane-of.sh --rows` prints, plus the
            classes the rules carve inside those rows (a game, its rulebook
            twin, `_candidates.md`, a family library, a proof module, a test
            module against a helper, a `.py` against data, an `ADR-NNNN`
            citation, an unmapped root file), each at the statuses that
            change the answer.
registry:   rules: `tools.check_change.Check`; path classes:
            `tools/lane-of.sh --rows` over docs/harness.md "The Merge Lanes";
            games and library consumers: `tools.check_change.read_tree`.
held by:    Derived and Pinned. The rule axis is an Enum the selector
            dispatches over exhaustively; the path-class axis is the lane
            table, pinned here by `test_every_lane_row_has_a_cell`.
does not prove:  that a rule's trigger is the right one -- the expected
            column is authored from the prose, so a rule the prose states
            too narrowly is selected too narrowly here and green.
"""

from __future__ import annotations

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


_RED = pytest.mark.xfail(raises=AssertionError, strict=True, reason="selection not written")


@pytest.mark.parametrize(
    ("status", "path", "cites", "check"),
    [
        pytest.param(
            s, p, c, check,
            id=f"{s.value}-{p}{'-adr' if c else ''}-{check.value}",
            marks=[_RED] if check in e else [],
        )
        for s, p, c, e in CELLS
        for check in cc.Check
    ],
)
def test_a_rule_fires_exactly_on_its_path_class(
    status: cc.Status, path: str, cites: bool, check: cc.Check
) -> None:
    expected = next(e for s, p, c, e in CELLS if (s, p, c) == (status, path, cites))
    assert (check in _fired(status, path, cites)) == (check in expected)


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="lane-of has no --rows yet")
def test_every_lane_row_has_a_cell() -> None:
    rows = cc.lane_rows(str(REPO))
    assert rows, "lane-of.sh --rows printed no rows"
    covered = {cls for classes in _classes().values() for cls in classes}
    missing = sorted({cls for _, _, cls in rows} - covered)
    assert not missing, f"lane-table rows with no grid cell: {missing}"


@pytest.mark.parametrize("check", list(cc.Check), ids=[c.value for c in cc.Check])
def test_every_rule_is_expected_somewhere(check: cc.Check) -> None:
    """Red under: deleting every cell whose expected set holds the rule."""
    assert any(check in expected for _, _, _, expected in CELLS)
