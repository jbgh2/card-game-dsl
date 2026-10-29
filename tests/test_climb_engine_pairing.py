"""A climbing round's two queries are one engine's pair.

property:        A `round climb ... combinations L follows F` checks clean only
                 when L and F are the same combination engine's lead and
                 follows queries; any other pairing is refused at resolve,
                 naming both queries and the follows query L's engine answers
                 with. The runtime keys the engine by L alone (its reads row,
                 universe, codec, announcements, decline), so F from another
                 engine would run over the wrong engine's plays.
domain:          Every lead query in `PRIMITIVE_CLIMB_LEADS` crossed with every
                 follows query in `PRIMITIVE_CLIMB_FOLLOWS`, each written into
                 the corpus game whose round names that lead query. The
                 diagonal is the corpus as it stands; every other cell is a
                 pairing no engine owns. A game's own round is the one position
                 a pairing is written in: a family library's round may not name
                 a climb query at all (resolve's `_round_slot_primitives`).
registry:        leads, follows: `cardlang.builtins.functions`
                 (`PRIMITIVE_CLIMB_LEADS`, `PRIMITIVE_CLIMB_FOLLOWS`); the
                 pairing the guard reads: `PRIMITIVE_CLIMB_ENGINES`; the
                 pairing the expected column reads:
                 `cardlang.runtime.primitives.climb_row`, the module each query
                 dispatches to.
held by:         a single owner — `PRIMITIVE_CLIMB_ENGINES` defines the lead and
                 follows registries, so a follows query cannot exist without the
                 lead it pairs with; the resolve Owner Guard reads that one
                 table, and this grid reconciles it against the runtime's
                 dispatch.
does not prove:  That a pairing an engine owns plays correctly (each engine's
                 own combination tests and the readiness proofs do); nor
                 anything about a round pairing a registered engine's slot
                 with a game's catalogue or function
                 (tests/test_combination_catalogue.py, the slot-pairing grid).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cardlang.builtins.functions import (
    PRIMITIVE_CLIMB_ENGINES,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
)
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.primitives import climb_row

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
_SLOT = re.compile(r"combinations\s+(\w+)\s+follows\s+(\w+)")


def _game_for(lead: str) -> tuple[str, str]:
    """The corpus game whose climbing round names `lead`: (file name, source)."""
    for path in sorted(GAMES.glob("*.cardlang")):
        source = path.read_text()
        m = _SLOT.search(source)
        if m and m.group(1) == lead:
            return path.name, source
    raise AssertionError(f"no corpus game names climb lead query {lead!r}")


def _one_engine(lead: str, follows: str) -> bool:
    """The runtime's answer: both queries dispatch to one module's row."""
    return climb_row(lead) is climb_row(follows)


CELLS = [(lead, follows) for lead in sorted(PRIMITIVE_CLIMB_LEADS) for follows in sorted(PRIMITIVE_CLIMB_FOLLOWS)]


@pytest.mark.parametrize(("lead", "follows"), CELLS)
def test_a_climb_round_checks_only_with_one_engines_pair(lead: str, follows: str) -> None:
    name, source = _game_for(lead)
    m = _SLOT.search(source)
    assert m is not None
    probe = source[: m.start(2)] + follows + source[m.end(2) :]
    if _one_engine(lead, follows):
        check_dsl(probe, name)
        return
    with pytest.raises(DiagnosticError) as err:
        check_dsl(probe, name)
    message = str(err.value)
    assert f"'{lead}'" in message and f"'{follows}'" in message, message
    assert f"'{PRIMITIVE_CLIMB_ENGINES[lead]}'" in message, message


def test_the_pairing_table_defines_both_registries() -> None:
    """red under: add a follows query to `PRIMITIVE_CLIMB_FOLLOWS` that no
    `PRIMITIVE_CLIMB_ENGINES` row names."""
    assert PRIMITIVE_CLIMB_LEADS == frozenset(PRIMITIVE_CLIMB_ENGINES)
    assert PRIMITIVE_CLIMB_FOLLOWS == frozenset(PRIMITIVE_CLIMB_ENGINES.values())
    assert len(set(PRIMITIVE_CLIMB_ENGINES.values())) == len(PRIMITIVE_CLIMB_ENGINES)


@pytest.mark.parametrize(
    ("combinations", "follows", "refusal"),
    [
        # the two slots swapped
        ("tichu_follows", "tichu_lead_options", "is not a combination lead query"),
        # the lead query written in both slots
        ("tichu_lead_options", "tichu_lead_options", "is not a combination follows query"),
        # the follows query written in both slots
        ("tichu_follows", "tichu_follows", "is not a combination lead query"),
        # one character off the follows query
        ("tichu_lead_options", "tichu_follow", "is not a combination follows query"),
    ],
)
def test_the_plausible_wrong_pairings_are_refused(combinations: str, follows: str, refusal: str) -> None:
    name, source = _game_for("tichu_lead_options")
    probe = _SLOT.sub(f"combinations {combinations} follows {follows}", source, count=1)
    with pytest.raises(DiagnosticError, match=refusal):
        check_dsl(probe, name)
