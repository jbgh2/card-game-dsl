"""The partition-coverage record is executor-invariant.

Contract under test: a serial run and a pytest-xdist run of the same
selection render the IDENTICAL partition-coverage record — same section,
same lines, same order. Two mechanisms compose to make that true, and this
module is the pin for both:

- worker shipping (tests/openspiel_ready/conftest.py): proofs record in
  worker processes, the summary renders on the controller, and without the
  `workeroutput` hand-off a parallel run prints nothing — a smaller record
  that reads as a complete one, the defect class this repo names
  "vacuously green".
- canonical rendering (tests/openspiel_ready/partition.py `_canonical` +
  `record()` JSON-normalization): arrival order is scheduling, so the
  renderers sort, and `detail` is stored JSON-normalized so a record is the
  same object whether or not it crossed the worker boundary.

The expected section is authored literally below, not derived, so a
canonical-order regression fails even if both modes regress identically.

red under — RUN, not predicted (each verified by hand, then reverted):
  the `RECORDS.extend` in `pytest_testnodedown` dropped -> the parallel
    section is empty and `test_parallel_and_serial_render_identically`
    fails on the missing lines
  `_canonical` returning its input unsorted -> the parallel run's
    interleaving diverges from the authored order and the same test fails
    on line order
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

# The mini-suite: two modules so xdist has something to distribute, three
# records landing in ONE game plus a second game, so both the cross-module
# merge and the within-game canonical order are exercised. `pairs` is a
# tuple on purpose: it exercises the JSON normalization (tuple -> list) that
# keeps the serial and shipped-over-the-wire renderings identical.
_CONFTEST = """
import sys

sys.path.insert(0, {repo_root!r})

from tests.openspiel_ready.conftest import (
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


def _section_lines(stdout_lines: list[str]) -> list[str]:
    return [ln for ln in stdout_lines if ln.startswith("game_")]


def test_parallel_and_serial_render_identically(pytester: pytest.Pytester) -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pytester.makeconftest(_CONFTEST.format(repo_root=repo_root))
    pytester.makepyfile(
        test_mod_a=_MODULE_A.format(repo_root=repo_root),
        test_mod_b=_MODULE_B.format(repo_root=repo_root),
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
