"""Render the partition-coverage record after a run (structural-infoset-proofs:
'a passing run must record what it covered ... that record is what any
external claim about the partition cites'). Printed as a pytest terminal
summary whenever any readiness proof ran; dumped as JSON when
CARDLANG_PARTITION_REPORT names a path.

Deliberately import-light: partition.py does not import pyspiel, so collection
works even where open_spiel is absent (the proofs themselves importorskip)."""

from __future__ import annotations

import os
from typing import Any

from tests.openspiel_ready.partition import RECORDS, dump_json, summary_lines


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
