"""Every runtime guard on a computed seat asks one predicate, `Seating.is_seat`.

A seat reaching the runtime through the permissive top is runtime data, so
the guards that refuse a non-seat -- `as`, a round's `from`, a frame verb's
player argument, a delegated decider, the `loser:` selection, a seat view --
are Owner Guards over a value the checker cannot see. Membership in
`Seating.players` is not the test they need: `True == 1`, so a flag passes it
as seat 1.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a runtime value is a seat exactly when it is an `int`, not a
            `bool`, in `0 <= value < count`, and no guard in `cardlang/`
            tests seat-ness by membership in the seat ring.
domain:     the predicate over one value per runtime shape a computed seat
            can take (both Booleans, the table's first and last seats, one
            below and one past it, a string, `none`); and every membership
            test against a seat ring written in the package source.
registry:   the package source, scraped by `_membership_sites`.
            Executed through a sentence: the `as` bind,
            `tests/test_as_block.py::test_a_boolean_bound_as_actor_is_a_loud_runtime_error`;
            the `loser:` selection, `tests/test_loser_selection.py`.
does not prove:  that each guard calls the predicate on the value it then
            uses; the scrape sees a membership test, not the data flow.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cardlang.runtime.values import Seating

PACKAGE = Path(__file__).resolve().parent.parent / "cardlang"

# A membership test against a seat ring: `x in seating.players`,
# `x not in self.players`.
_MEMBERSHIP = re.compile(r"\bin\s+[\w.]*\bplayers\b(?!\s*(?:if|for)\b)")


@pytest.mark.parametrize(
    ("value", "seat"),
    [
        pytest.param(True, False, id="true"),
        pytest.param(False, False, id="false"),
        pytest.param(0, True, id="first-seat"),
        pytest.param(3, True, id="last-seat"),
        pytest.param(-1, False, id="below-the-table"),
        pytest.param(4, False, id="one-past-the-table"),
        pytest.param("0", False, id="string"),
        pytest.param(None, False, id="none"),
    ],
)
def test_is_seat(value: object, seat: bool) -> None:
    """red under: `Seating.is_seat` as `value in range(self.count)` -- both
    Booleans then read as seats."""
    assert Seating(4).is_seat(value) is seat


def _membership_sites() -> list[str]:
    sites = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if _MEMBERSHIP.search(code) and not re.search(r"\bfor\b", code):
                sites.append(f"{path.relative_to(PACKAGE.parent)}:{number}: {line.strip()}")
    return sites


def test_no_guard_tests_seat_ness_by_ring_membership() -> None:
    """red under: `Ctx.acting_as` testing `player not in self.rs.seating.players`."""
    assert _membership_sites() == []
