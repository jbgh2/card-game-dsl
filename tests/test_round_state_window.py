"""A finished round's `state.` is read only until its window closes.

property:   after a `round` returns, the surrounding text reads its terminal
            frame through `state.` until either a decision other than a
            round's is asked or the phase that ran the round ends; a read
            after that is refused at play, never served the old frame. A
            live round's frame is never ended by these.
domain:     reader position x what stands between it and the round. The
            positions: directly after the round in its phase (read), an
            `offer` in a later phase, a `for each` poll and a `repeat until`
            poll in a later phase, an offer in the same phase whose move's
            `when:` reads the frame, a later phase's plain read, and the next
            hand's bid; the decision-site axis is every caller of
            `chooser.decide`, pinned below against the window's one entry.
registry:   decision sites: `cardlang.runtime.delegation.DECISION_POINTS`;
            the window: `RuntimeState.end_round_window`; the ring's own cell:
            tests/test_round_execute.py::test_a_ring_ends_the_just_completed_rounds_window.
does not prove:  a Primitive's read of the frame through `engine_facts`: it
            meets the same field, but no cell here calls one past the window.
"""

from __future__ import annotations

import ast
import random
import re
from pathlib import Path

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.delegation import DECISION_POINTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError

_HOST = """game W {{
  players: 4
  max_length: 200
  cards: standard52
  ranking: aces high
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }}
  state {{ won[player] : Integer = 0  asked : Integer = 0  hands : Integer = 0 }}
  phase deal {{ shuffle deck }}
  {phases}
  winner: highest won
}}
{moves}
"""

# The move types a cell may offer; each cell defines the ones it names.
_MOVES: dict[str, str] = {
    "peek": "move_type peek { effect { asked += 1  if state.led_suit is not none { won[actor] += 100 } } }",
    "peek_when": "move_type peek_when { when: state.led_suit is not none  effect { won[actor] += 1 } }",
    "skip": "move_type skip { effect { asked += 1 } }",
}


def _game(phases: str) -> str:
    offered = set(re.findall(r"one of \[([^\]]*)\]", phases))
    names = {m.strip() for group in offered for m in group.split(",")}
    return _HOST.format(phases=phases, moves="\n".join(_MOVES[m] for m in sorted(names)))

_TRICK = (
    "    deal 1 card from deck to each hand\n"
    "    round play_to_trick from 0 over all players source hand into trick_pile "
    "winner highest_of_led_suit\n"
)


def _play_phase(after: str = "") -> str:
    return f"phase play {{\n{_TRICK}    {after}\n    move all cards from trick_pile to waste\n  }}"


ENDED: dict[str, str] = {
    "offer in a later phase": _play_phase() + "\n  phase after { offer to 0 one of [peek] }",
    "for each poll in a later phase": _play_phase()
    + "\n  phase after { for each player p: offer to p one of [peek] }",
    "repeat until poll in a later phase": _play_phase()
    + "\n  phase after { repeat until asked >= 1 { offer to 1 one of [peek] } }",
    "offer in the same phase reading it in `when:`": _play_phase(
        "offer to 0 one of [peek_when, skip]"
    ),
    "plain read in a later phase": _play_phase()
    + "\n  phase after { if state.led_suit is not none { won[0] += 1 } }",
    "the next hand's bid": (
        "phase hand repeat until hands >= 2 {\n"
        "    phase bid { if hands > 0 { offer to 0 one of [peek] } }\n"
        "    phase play {\n" + _TRICK + "    move all cards from trick_pile to waste\n"
        "    hands += 1\n  }\n  }"
    ),
}


@pytest.mark.parametrize("position", list(ENDED))
def test_a_read_past_the_window_is_refused(position: str) -> None:
    """red under: drop `end_round_window` from the decision sites and from
    the phase exit (each cell then reads the old trick's led suit)."""
    game = check_dsl(_game(ENDED[position]), "w.cardlang")
    with pytest.raises(OwnerGuardError, match="no active or just-completed round"):
        play_game(game, random.Random(0))


def test_a_read_directly_after_the_round_sees_it() -> None:
    """The corpus shape: the round's own phase reads its frame before any
    other decision is asked.

    red under: end the window when the round returns."""
    game = check_dsl(
        _game(_play_phase("if state.led_suit is not none { won[0] += 1 }")),
        "w.cardlang",
    )
    assert play_game(game, random.Random(0)).scores[0] == 1


def _decide_callers() -> set[tuple[str, str]]:
    root = Path("cardlang/runtime")
    found: set[tuple[str, str]] = set()
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            calls = {
                c.func.id
                for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
            }
            attrs = {
                c.func.attr
                for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            }
            if "decide" in calls and path.stem != "chooser":
                found.add((f"{path.stem}.{fn.name}", "ends" if "end_round_window" in attrs else "keeps"))
    return found


def test_every_non_round_decision_site_ends_the_window() -> None:
    """A round's own decision keeps its live frame; every other site ends a
    finished round's window before it computes what it offers.

    red under: drop `end_round_window` from `execute._offer`."""
    callers = _decide_callers()
    assert {site for site, _ in callers} == set(DECISION_POINTS)
    for site, verdict in callers:
        want = "keeps" if DECISION_POINTS[site].construct in ("trick",) else "ends"
        assert verdict == want, (site, verdict)
