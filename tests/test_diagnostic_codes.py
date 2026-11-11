"""The Diagnostic Codes: every code is shipped, stable, and raised by a witness.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every member of `cardlang.diagnostic_codes.Code` is told by
                 an executed witness -- a rejection case, a game or library
                 text checked here, a command line run, or a runtime refusal
                 rendered -- and no code shipped is renamed or removed: the
                 blessed list and the registry are one set.
domain:          the registry crossed with one witness per member, the axis
                 derived from `Code` itself, so a member added without a
                 witness is a red cell rather than an unlisted one. The
                 witnesses reach the checker through `check_dsl`,
                 `parse_library` and `check_source`, the command line
                 through `cardlang.cli.main`, and the runtime through
                 `cardlang.records.refusal_diagnostic`.
registry:        the axis -- `Code`; the blessed spellings -- `SHIPPED`;
                 the rejection corpus -- tests/test_rejections.py::case_paths.
held by:         Derived and Pinned. A code's spelling is a string a tool
                 keys on outside the type checker, so the blessed list holds
                 it; that every refusal carries a code is held a rung higher,
                 by `Diagnostic.code` being a required field.
does not prove:  that every report site sharing a code asks for the same
                 kind of fix. One witness per code shows the code is told;
                 the naming review of the registry, read whole, is what
                 judges a site's code.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import DiagnosticError

# Every code ever shipped, in registry order. A code is never removed or
# renamed once it is here: a tool may key on it.
SHIPPED: tuple[str, ...] = ()


def test_the_blessed_list_is_the_registry() -> None:
    """red under: a member renamed in `cardlang/diagnostic_codes.py`."""
    assert tuple(code.slug for code in Code) == SHIPPED


def test_every_code_is_spelled_in_words() -> None:
    """A slug is lower-case words joined by hyphens, a meaning one ASCII
    line. red under: a member spelled `UNKNOWN_ZONE = ("UnknownZone", ...)`."""
    for code in Code:
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", code.slug), code
        assert code.meaning and code.meaning.isascii() and "\n" not in code.meaning, code
    assert len({code.slug for code in Code}) == len(Code)


@dataclass(frozen=True)
class Witness:
    """How a code is told: a callable returning every code it told."""

    tells: Callable[[], frozenset[Code]]


WITNESSES: dict[Code, Witness] = {}


@pytest.mark.parametrize("code", list(Code), ids=lambda c: c.slug)
def test_every_code_has_a_witness_that_tells_it(code: Code) -> None:
    witness = WITNESSES.get(code)
    assert witness is not None, f"`{code.slug}` has no witness"
    assert code in witness.tells()


def _codes_of(exc: DiagnosticError) -> frozenset[Code]:
    return frozenset(told.diagnostic.code for told in exc.told)


_ROOT = Path(__file__).resolve().parent.parent
