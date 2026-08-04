"""Suite-wide Pin: a `ShadowGuardError` anywhere in the run is a failure.

A Shadow Guard is defined as unreachable while the Owner Guard it names is
correct (docs/glossary.md section 5). That is a guarantee only while something
enforces it; unenforced, it decays into a comment. This module is the
enforcement.

Why it hooks CONSTRUCTION rather than propagation: a raised `ShadowGuardError`
can be caught and dropped on the way out — `tests/fuzz/oracle.py` classifies
broad exceptions, `tests/openspiel_ready/harness.py` skips a probe pair on
`ValueError`, `runtime/driver.py` swallows a control-flow signal. Watching what
reaches the test would make the Pin's reach depend on who catches what, which
is exactly the seam the guarantee is about. Constructing one is the observable
event, so that is what is counted.

The precedent this exists to avoid is in-tree: `diagnostics.Severity.WARNING`
is the only other typed classification of a failure this repo has, and it has
zero producers repo-wide. A typed role that nothing enforces is decoration.

Opting out: a test that deliberately exercises a Shadow Guard marks itself
`@pytest.mark.expects_shadow_guard`. The mark is per-test and the count is
reset around it, so an unmarked neighbour cannot inherit the exemption.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from cardlang.runtime.errors import ShadowGuardError

_constructed: list[str] = []
_original_init = ShadowGuardError.__init__


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "expects_shadow_guard: this test deliberately raises a ShadowGuardError; "
        "the suite-wide Pin (tests/conftest.py) is waived for it",
    )

    def _recording_init(self: ShadowGuardError, leaked: str, message: str) -> None:
        _constructed.append(f"{leaked}: {message}")
        _original_init(self, leaked, message)

    # Patched for the whole session rather than per-test: a ShadowGuardError
    # constructed during collection or in a fixture is as much an engine gap as
    # one constructed inside a test body.
    ShadowGuardError.__init__ = _recording_init  # type: ignore[method-assign]


def pytest_unconfigure(config: pytest.Config) -> None:
    ShadowGuardError.__init__ = _original_init  # type: ignore[method-assign]


@pytest.fixture(autouse=True)
def _shadow_guard_pin(request: pytest.FixtureRequest) -> Iterator[None]:
    """Fail the test that constructed a `ShadowGuardError`, naming the guard
    that leaked. Failing at the test rather than at session end is what makes
    the report actionable: the engine gap is attributed to the run that found
    it, not to the suite as a whole.

    Reported shape: because the check runs after the test body, pytest attributes
    it to TEARDOWN, so a tripping test summarises as `1 passed, 1 error` rather
    than as a failure. The run still exits non-zero and the message still names
    the leaked guard; do not read the "passed" as the verdict.

    red under: raise `ShadowGuardError("resolve", "x")` inside any unmarked
    test. Verified by doing so.
    """
    before = len(_constructed)
    yield
    leaked = _constructed[before:]
    if leaked and request.node.get_closest_marker("expects_shadow_guard") is None:
        raise AssertionError(
            f"{len(leaked)} ShadowGuardError(s) constructed during this test — a "
            f"Shadow Guard is unreachable while the Owner Guard it names is "
            f"correct, so each of these is an ENGINE gap, not a bad game:\n  "
            + "\n  ".join(leaked)
            + "\nFix the Owner Guard that leaked, or mark the test "
            "`@pytest.mark.expects_shadow_guard` if it exercises one on purpose."
        )
