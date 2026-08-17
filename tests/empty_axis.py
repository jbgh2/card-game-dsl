"""Authorize a parametrization axis to derive to nothing, at its call site.

`pyproject.toml` sets `empty_parameter_set_mark = "fail_at_collect"`, so an
axis that derives to nothing stops the build instead of retiring itself as a
skip. A few axes are legitimately empty — the live docs hold zero
`cardlang`-tagged blocks today, and those code paths are proven by synthetic
fixtures instead — and this is the only sanctioned way to say so. The reason
rides beside the axis; `tests/test_empty_axis_guard.py` pins the set of call
sites, so a new authorization cannot land unnoticed.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest


def may_be_empty(
    values: Sequence[object], *, reason: str, argcount: int = 1
) -> Sequence[object]:
    """A single skipped placeholder standing in for an empty `values`.

    `reason` says why nothing is a legitimate answer today, and names what
    carries the guarantee meanwhile. `argcount` matches the number of names the
    parametrization declares — a mismatch is loud in pytest's own channel
    ("the number of names must be equal to the number of values").

    A NONEMPTY `values` is refused rather than passed through. An authorization
    is a claim about today ("the live docs hold zero `cardlang` blocks"); the
    day that stops being true the test simply starts doing its job, with a
    stale claim beside it and nothing anywhere to say so. Refusing is the same
    bargain `xfail_strict` strikes: closing a gap must force the record of it
    to be updated in the same change.
    """
    if not reason.strip():
        # A blank reason is not a reason. The whole cost of this door is that
        # someone has to write down why nothing is a legitimate answer; a
        # placeholder pays it in appearance only.
        pytest.fail(
            "may_be_empty() needs a reason saying why the axis is legitimately "
            "empty today and what carries the guarantee meanwhile.",
            pytrace=False,
        )
    if values:
        pytest.fail(
            f"authorized empty axis is no longer empty ({len(values)} value(s)) — "
            f"the authorization said {reason!r}. Drop the may_be_empty() wrapper "
            "and its row in tests/test_empty_axis_guard.py's "
            "_AUTHORIZED_EMPTY_AXES; the axis can stand on its own now.",
            pytrace=False,
        )
    return [
        pytest.param(
            *(None,) * argcount,
            marks=pytest.mark.skip(reason=f"authorized empty axis: {reason}"),
        )
    ]
