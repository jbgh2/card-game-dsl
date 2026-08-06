"""Render the partition-coverage record after a run (structural-infoset-proofs:
'a passing run must record what it covered ... that record is what any
external claim about the partition cites'). Printed as a pytest terminal
summary whenever any readiness proof ran; dumped as JSON when
CARDLANG_PARTITION_REPORT names a path.

Deliberately import-light: partition.py does not import pyspiel, so collection
works even where open_spiel is absent (the proofs themselves importorskip)."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from tests.openspiel_ready.partition import (
    RECORDS,
    ProofRecord,
    dump_json,
    summary_lines,
)

# The record must survive pytest-xdist: proofs run in worker processes, each
# accumulating its own RECORDS, while the terminal summary below renders on
# the controller — without shipping, a parallel run would print nothing and
# CARDLANG_PARTITION_REPORT would dump an empty list, a smaller record that
# reads as a complete one. Workers serialize their records into
# `workeroutput` (JSON, because the channel carries primitives, and lossless
# because `record()` already stores detail JSON-normalized); the controller
# collects them as each node shuts down. The pin that serial and parallel
# runs render the identical record is tests/test_partition_record_modes.py.

_WORKEROUTPUT_KEY = "cardlang_partition_records"


def pytest_sessionfinish(session: pytest.Session) -> None:
    workeroutput = getattr(session.config, "workeroutput", None)
    if workeroutput is not None:  # absent on the controller and in serial runs
        workeroutput[_WORKEROUTPUT_KEY] = json.dumps(
            [{"game": r.game, "proof": r.proof, "detail": r.detail} for r in RECORDS]
        )


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: Any, error: Any) -> None:
    # An xdist-declared hook: `optionalhook` keeps this conftest loadable
    # where pytest-xdist is not installed (the hook then simply never fires,
    # which is also the serial case).
    payload = getattr(node, "workeroutput", {}).get(_WORKEROUTPUT_KEY)
    if payload:
        RECORDS.extend(ProofRecord(**item) for item in json.loads(payload))


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    if not RECORDS:
        return
    terminalreporter.section("openspiel_ready partition coverage")
    for line in summary_lines():
        terminalreporter.write_line(line)
    out = os.environ.get("CARDLANG_PARTITION_REPORT")
    if out:
        dump_json(out)
        terminalreporter.write_line(f"partition coverage record written to {out}")
