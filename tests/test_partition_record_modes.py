"""The partition-coverage record is executor-invariant — and only because
its session hooks live in the ROOT conftest.

Contract under test, positive half: a serial run and a pytest-xdist run of
the same selection render the IDENTICAL partition-coverage record — same
section, same lines, same order. Two mechanisms compose to make that true:

- worker shipping (tests/conftest.py): proofs record in worker processes,
  the summary renders on the controller, and without the `workeroutput`
  hand-off a parallel run prints nothing — a smaller record that reads as a
  complete one, the defect class this repo names "vacuously green".
- canonical rendering (tests/openspiel_ready/partition.py `_canonical` +
  `record()` JSON-normalization): arrival order is scheduling, so the
  renderers sort, and `detail` is stored JSON-normalized so a record is the
  same object whether or not it crossed the worker boundary.

Negative half, the placement constraint: the xdist CONTROLLER loads only
the conftest chain of the initial command-line paths, while workers (which
collect everything) load the deeper ones — so the same hooks hosted in a
SUBDIRECTORY conftest ship records nobody receives, and the bare parallel
run loses the record while serial and subset runs keep printing it. That is
exactly how the gate lost the record on 2026-08-06 (PR #267's first run),
so the wrong topology is pinned as wrong. If this negative test ever FAILS,
pytest/xdist started loading subdirectory conftests on the controller and
the hooks may move home to tests/openspiel_ready/.

The expected section is authored literally below, not derived, so a
canonical-order regression fails even if both modes regress identically.

red under — RUN, not predicted (each verified by hand, then reverted):
  the `RECORDS.extend` in `pytest_testnodedown` dropped -> the parallel
    section is empty and `test_parallel_and_serial_render_identically`
    fails on the missing lines
  `_canonical` returning its input unsorted -> the section diverges from
    the authored order and the same test fails on line order
"""

from __future__ import annotations

import os

import pytest

pytest_plugins = ["pytester"]

pytest.importorskip(
    "xdist",
    reason="the parallel half of the executor-invariance contract needs "
    "pytest-xdist; it is a declared dev dependency, so a skip here means "
    "the environment was not installed from the spec",
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The mini-suite mirrors production topology: the HOOKS in the root
# conftest (re-exported from the real tests/conftest.py), two modules so
# xdist has something to distribute, three records landing in one game plus
# a second game, so both the cross-module merge and the within-game
# canonical order are exercised. `pairs` is a tuple on purpose: it
# exercises the JSON normalization (tuple -> list) that keeps the serial
# and shipped-over-the-wire renderings identical.
_HOOKS_CONFTEST = """
import sys

sys.path.insert(0, {repo_root!r})

from tests.conftest import (
    pytest_sessionfinish,
    pytest_terminal_summary,
    pytest_testnodedown,
)
"""

_MODULE_A = """
import sys

sys.path.insert(0, {repo_root!r})

from tests.openspiel_ready import partition


def test_records_two() -> None:
    partition.record("game_b", "swap", seed=3, pairs=("2d", "10s"))
    partition.record("game_a", "facts", observers=2)
"""

_MODULE_B = """
import sys

sys.path.insert(0, {repo_root!r})

from tests.openspiel_ready import partition


def test_records_one() -> None:
    partition.record("game_b", "rng", seed=3, reseeded=True)
"""

# Authored, not derived: games sorted, records within a game sorted by
# (proof, detail), kv pairs in CALL order — the recording site's chosen
# presentation, which JSON preserves across the worker wire — and the tuple
# rendered as its JSON-normalized list.
_EXPECTED_SECTION = [
    "game_a: facts[observers=2]",
    "game_b: rng[seed=3,reseeded=True] swap[seed=3,pairs=['2d', '10s']]",
]

_SECTION_HEADER = "openspiel_ready partition coverage"


def _section_lines(stdout_lines: list[str]) -> list[str]:
    return [ln for ln in stdout_lines if ln.startswith("game_")]


def test_parallel_and_serial_render_identically(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(_HOOKS_CONFTEST.format(repo_root=_REPO_ROOT))
    pytester.makepyfile(
        test_mod_a=_MODULE_A.format(repo_root=_REPO_ROOT),
        test_mod_b=_MODULE_B.format(repo_root=_REPO_ROOT),
    )

    serial = pytester.runpytest_subprocess("-q")
    serial.assert_outcomes(passed=2)
    parallel = pytester.runpytest_subprocess("-q", "-n", "2")
    parallel.assert_outcomes(passed=2)

    assert _section_lines(serial.outlines) == _EXPECTED_SECTION, (
        "the serial run's partition record does not match the authored "
        "canonical section"
    )
    assert _section_lines(parallel.outlines) == _EXPECTED_SECTION, (
        "the parallel run's partition record does not match the serial one — "
        "either worker records were not shipped to the controller, or the "
        "renderers are ordering by arrival rather than canonically"
    )


def test_subdirectory_conftest_hooks_lose_the_record_under_xdist(
    pytester: pytest.Pytester,
) -> None:
    """The constraint that forces the hooks into the root conftest, kept
    executable so nobody tidies them back down: with the SAME hooks hosted
    in a subdirectory conftest, a bare serial run still prints the section
    (the collecting process loads the conftest) and a bare parallel run
    LOSES it (the controller never loads it, so worker payloads go unread).
    A failure here means the controller started loading subdirectory
    conftests — revisit the hooks' placement, the guard may be removable."""
    sub = pytester.mkpydir("sub")
    (sub / "conftest.py").write_text(_HOOKS_CONFTEST.format(repo_root=_REPO_ROOT))
    (sub / "test_sub_mod.py").write_text(_MODULE_B.format(repo_root=_REPO_ROOT))

    serial = pytester.runpytest_subprocess("-q")
    serial.assert_outcomes(passed=1)
    assert any(_SECTION_HEADER in ln for ln in serial.outlines), (
        "the serial run should print the section even from a subdirectory "
        "conftest — the collecting process loads it"
    )

    parallel = pytester.runpytest_subprocess("-q", "-n", "2")
    parallel.assert_outcomes(passed=1)
    assert not any(_SECTION_HEADER in ln for ln in parallel.outlines), (
        "a bare parallel run PRINTED the record from subdirectory-conftest "
        "hooks — the xdist controller has started loading subdirectory "
        "conftests, so the placement guard in tests/conftest.py may be "
        "removable; re-read its module docstring before acting"
    )
