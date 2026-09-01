"""The grid: every TOTAL position refuses a wrong value, however it is spelled.

`tests/test_typed_positions.py` classifies each expression position by what the
runtime does with a wrong value there. This module is the executed half for the
positions it classes TOTAL -- the ones whose wrong value is SILENT, so nothing
downstream can catch it and the checker is the only wall there is.

Two producers per position, because a guard that catches one and not the other
is the hole this grid exists to close:

- CONCRETE -- an Integer literal where the position requires something else. A
  guard that reads the inferred type catches this.
- LAUNDERED -- the same wrongness behind the permissive top, `(if true then
  hearts else 1)`, whose branches do not join. A guard that admits `TAny` (the
  `isinstance(t, (TBoolean, TAny))` shape) does NOT catch this, and the game
  then plays on: issue #515 measures a laundered trump scoring a whole different
  hand with nothing raised.

Both must be refused, at check time, with a diagnostic. That is the expected
column, and it was authored before any guard existed.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      `test_typed_positions.TREATMENT` classifies every position, and its
              own completeness pin keeps that table equal to the derived
              population.
Establishes:  every TOTAL position rejects both producers through `check_dsl`.
Illegal after: a TOTAL position that admits a wrongly-typed expression in either
              spelling.

Ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------
property:        every position classified TOTAL refuses a wrong-typed
                 expression, both as a concrete literal and laundered through
                 the permissive top.
domain:          the TOTAL rows of `test_typed_positions.TREATMENT`, crossed
                 with both producers. GRADUAL and CONTEXTUAL positions are
                 outside it by design -- their wrong values raise downstream,
                 which is the classification module's subject.
registry:        positions: `test_typed_positions.TREATMENT`, itself pinned
                 equal to the derived population by
                 tests/test_typed_positions.py::test_every_position_is_classified;
                 producers: `PRODUCERS` below;
                 message shape: tests/rejections/boolean_position_laundered_any,
                 round_trump_laundered_any, rule_if_impossible_not_a_card_set.
does not prove:  that a refused spelling is refused for the right REASON -- the
                 grid asserts that a diagnostic is raised, not which one. A
                 guard firing for an unrelated reason would satisfy a cell
                 here; the rejection goldens above are where the wording a
                 designer reads is pinned.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.typecheck import OP_CLASSES, OpClass
from tests.test_typed_positions import TOTAL, TREATMENT

# The two spellings of the same wrongness. `3` is an Integer literal; the second
# types as `TAny` because the branches do not join.
PRODUCERS = {
    "concrete": "3",
    "laundered": "(if true then hearts else 1)",
}

_BASE = """%s
game G {
  players: 2
  direction: clockwise
  max_length: 100
  cards: standard52
  zones {
    deck         : Deck
    hand[player] : Hand<player>
    pile         : Discard
  }
  state { score[player] : Integer = 0 }
  phase setup {
    shuffle deck
    deal 2 cards from deck to each hand
%s
  }
  winner: highest score
}
"""

# (top-level declarations, phase body). Exactly one carries the `{W}` slot.
SYNTHETIC: dict[tuple[str, str], tuple[str, str]] = {
    ("IfStmt", "cond"): ("", "    if {W} { score[0] += 1 }"),
    ("RepeatUntil", "until"): ("", "    repeat until {W} { score[0] += 1 }"),
    ("Transfer", "where"): ("", "    move all cards from deck where {W} to pile"),
    ("Not", "operand"): ("", "    if not {W} { score[0] += 1 }"),
    ("IfExpr", "cond"): ("", "    score[0] := if {W} then 1 else 2"),
    ("Comprehension", "where"): ("", "    score[0] := sum of 1 over cards in deck where {W}"),
    ("DomainQuery", "where"): ("", "    if any suit where {W} { score[0] += 1 }"),
    ("Quantifier", "body"): ("", "    if any card in deck where {W} { score[0] += 1 }"),
    ("CardQuery", "where"): ("", "    move all cards from deck where {W} to pile"),
    ("PlayerQuery", "where"): ("", "    if any player where {W} { score[0] += 1 }"),
    ("Turns", "until"): ("", "    turns t from 0 over all players until {W} { score[t] += 1 }"),
    ("EpistemicOp", "where"): ("", "    reveal one card from deck where {W}"),
    ("PhaseQualifier", "expr"): (
        "",
        "    score[0] += 1",
    ),
    ("MoveTypeDef", "when"): (
        "move_type m {\n  when: {W}\n  effect { score[actor] += 1 }\n}\n",
        "    score[0] += 1",
    ),
}

# Positions needing a construct too large to synthesize: substituted into a
# corpus game that already has one. The anchor is asserted present, so a corpus
# edit that moves it fails this module loudly instead of silently skipping.
CORPUS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("TrickRound", "trump"): ("oh-hell.cardlang", "trump trump_suit", "trump {W}"),
    ("RuleDef", "if_impossible"): ("hearts.cardlang", "if_impossible: hand", "if_impossible: {W}"),
    ("AppliesWhen", "pred"): (
        "hearts.cardlang",
        "applies_when: state.led_suit is none",
        "applies_when: {W}",
    ),
    ("MoveEvent", "where"): (
        "hearts.cardlang",
        "when play_to_trick where action.card.suit is hearts",
        "when play_to_trick where {W}",
    ),
    # The whole `until` expression, not its first operand: replacing only
    # `taker is not none` would leave the `or (...)` behind, and `TAny or
    # Boolean` types Boolean -- the probe would pass while testing nothing.
    ("AuctionRound", "until"): (
        "belote.cardlang",
        "until taker is not none\n"
        "                  or (number of players where not acted[player]) is 0",
        "until {W}",
    ),
    ("ClimbRound", "until"): (
        "big-two.cardlang",
        "until (any player where hand[player] is empty)\n        opened := true",
        "until {W}\n        opened := true",
    ),
    # S3: total before this module existed, so both cells are expected GREEN and
    # this row is the grid's own control -- a guard that stopped refusing `TAny`
    # would surface here rather than in a cell nobody watches.
    ("TrickOrderRow", "body"): (
        "belote.cardlang",
        "trump:         card.suit is trump_suit",
        "trump:         {W}",
    ),
}


# The phase qualifier sits in the phase HEADER, so it cannot be injected into
# the shared skeleton's body the way the other synthetic probes are.
_QUALIFIER_BASE = """game G {
  players: 2
  direction: clockwise
  max_length: 100
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase setup repeat until %s {
    shuffle deck
    score[0] += 1
  }
  winner: highest score
}
"""


def _source(position: tuple[str, str], wrong: str) -> str:
    if position == ("PhaseQualifier", "expr"):
        return _QUALIFIER_BASE % wrong
    if position in SYNTHETIC:
        decls, body = SYNTHETIC[position]
        return _BASE % (decls.replace("{W}", wrong), body.replace("{W}", wrong))
    game, anchor, replacement = CORPUS[position]
    from pathlib import Path

    path = Path(__file__).parent.parent / "docs" / "games" / game
    text = path.read_text()
    assert anchor in text, f"{game} no longer contains the anchor {anchor!r}"
    return text.replace(anchor, replacement.replace("{W}", wrong), 1)


_TOTAL_POSITIONS = sorted(pos for pos, (t, _) in TREATMENT.items() if t == TOTAL)
_PROBED = set(SYNTHETIC) | set(CORPUS)


def test_every_total_position_has_a_probe() -> None:
    """No TOTAL position may sit outside the grid unnoticed.

    red under: add a TOTAL row to `TREATMENT` without adding its probe.
    """
    missing = [p for p in _TOTAL_POSITIONS if p not in _PROBED]
    assert not missing, f"TOTAL positions with no probe: {missing}"


# Cells this tree does not yet refuse. Each is a guard to write, not a design
# question: the expected column above says every one of them must reject. The
# marks are strict, so a cell that starts passing while still listed here fails
# loudly rather than being forgotten -- the entry comes out with the guard that
# closes it, and an empty set is the finished state.
#
# `concrete` entries are positions with no static check at all; `laundered`
# entries are guards that admit the permissive top. `TrickOrderRow.body` is in
# neither list, which is what makes it this grid's control.
# Cells this tree does not yet refuse. The expected column above says every
# TOTAL position must reject both spellings, so an entry here is a guard still
# to write, never a design question. The marks are strict: a cell that starts
# passing while still listed fails loudly rather than being forgotten. Empty is
# the finished state, and it is where this grid now stands.
RED_TODAY: frozenset[tuple[str, tuple[str, str]]] = frozenset()


def _refuses(source: str) -> bool:
    """Whether `check_dsl` refuses `source` in its own failure channel.

    Only `DiagnosticError` counts. A probe that breaks some other way raises out
    of here rather than being counted as a refusal -- a broken probe reporting
    success is the way this grid would go vacuously green.
    """
    try:
        check_dsl(source, "grid.cardlang")
    except DiagnosticError:
        return True
    return False


@pytest.mark.parametrize("position", _TOTAL_POSITIONS, ids=lambda p: f"{p[0]}.{p[1]}")
@pytest.mark.parametrize("producer", sorted(PRODUCERS), ids=lambda k: k)
def test_total_position_refuses_a_wrong_value(
    request: pytest.FixtureRequest, position: tuple[str, str], producer: str
) -> None:
    """A TOTAL position refuses a wrong-typed expression in both spellings."""
    if (producer, position) in RED_TODAY:
        request.node.add_marker(
            pytest.mark.xfail(strict=True, raises=AssertionError, reason="guard not written yet")
        )
    assert _refuses(_source(position, PRODUCERS[producer])), (
        f"{position[0]}.{position[1]} accepted a {producer} wrong value"
    )


# --- the operator axis --------------------------------------------------------
#
# An operand is a position too, and the operator decides what type it requires.
# `OP_CLASSES` is that registry, so the axis derives rather than being listed: a
# new operator joins the sweep by joining the table.
#
# Which classes must be TOTAL follows the same rule as the positions -- whether
# the runtime's consumption of a wrong value can fail. Measured 2026-08-31 by
# injecting a laundered operand into a corpus game and playing it:
#
#   LOGICAL     `and`/`or`     -> silent, different scores   -> total
#   MEMBERSHIP  `in`           -> silent, different scores   -> total (left)
#   EQUALITY    `is`/`is not`  -> silent, different scores   -> issue #520
#   ORDERING    `<` `>` ...    -> raises TypeError           -> loud, gradual
#   ARITHMETIC  `+` `-` ...    -> raises TypeError           -> loud, gradual
#
# EQUALITY is silent and is NOT closed here: refusing the permissive top there
# rejects three corpus games that legitimately compare an unrefined value, so it
# needs `infer`'s unrefined arms narrowed first rather than a guard bolted on.
TOTAL_OP_CLASSES = {OpClass.LOGICAL, OpClass.MEMBERSHIP}

_TOTAL_OPS = sorted(op for op, cls in OP_CLASSES.items() if cls in TOTAL_OP_CLASSES)


@pytest.mark.parametrize("op", _TOTAL_OPS)
def test_operator_of_a_total_class_refuses_a_laundered_operand(op: str) -> None:
    """An operator whose result types Boolean whatever its operands are cannot
    let a laundered operand through: the enclosing position's total check sees
    only the Boolean result, so the operator is where the value escapes.

    red under: restore `_check_logical_operands`'s pre-change arm --
    `if not isinstance(bare, (TAny, TBoolean))` -- which admitted the top. The
    `and` and `or` rows fail; `in` stays green, since the membership guard is
    its own. Note the narrower plant does NOT redden this: disabling only the
    TAny branch falls through to the generic arm, which still rejects.
    """
    right = "[hearts]" if OP_CLASSES[op] is OpClass.MEMBERSHIP else "true"
    surface = "is not" if op == "is_not" else op
    cond = f"{PRODUCERS['laundered']} {surface} {right}"
    body = "    if " + cond + " { score[0] += 1 }"
    assert _refuses(_BASE % ("", body)), f"'{op}' accepted a laundered operand"
