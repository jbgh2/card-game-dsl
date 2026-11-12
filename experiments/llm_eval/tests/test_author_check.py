"""The authoring benchmark's checker reader: what `cardlang check` printed,
read into verdicts and records.

The real checker runs where the verdict is the checker's (green, refused,
cannot proceed); a stand-in command runs where the verdict is about a
checker misbehaving (a crash, a hang, output nobody can read), because no
real crash exists to point at and the reader must not depend on one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..author_check import (
    CHECK_FORMS,
    DRAFT_NAME,
    Checker,
    CheckVerdict,
    Refusal,
    checker_import_root,
    parse_text,
    read_check,
    refusal_key,
    repo_root,
)

HIGH_CARD = """\
game HighCard {

  players: 2
  max_length: 20

  cards: standard52
  ranking: aces high

  zones {
    deck          : Deck
    hand[player]  : Hand<player>
    shown[player] : PublicHand<player>
  }

  state {
    score[player] : Integer = 0
  }

  phase deal {
    shuffle deck
    for each player p: deal 2 cards from deck to hand[p]
  }

  phase showdown {
    each player simultaneously:
      move chosen 1 card from hand[player] to shown[player]

    let a = sum of rank_value(card) over cards in shown[0]
    let b = sum of rank_value(card) over cards in shown[1]
    if a > b { score[0] += 1 } else { score[1] += 1 }
  }

  winner: highest score
}
"""

TWO_TYPOS = HIGH_CARD.replace("to hand[p]", "to hnad[p]").replace("score[0] += 1", "scroe[0] += 1")


def _stand_in(code: str, timeout: float = 30.0) -> Checker:
    """A checker whose command is a Python one-liner, for the verdicts only a
    misbehaving checker produces."""
    return Checker(argv=(sys.executable, "-c", code), timeout_seconds=timeout)


def test_the_checker_runs_this_checkout() -> None:
    assert checker_import_root(sys.executable, repo_root()) == repo_root()


def test_a_correct_draft_is_green(tmp_path: Path) -> None:
    result = Checker().check(HIGH_CARD, tmp_path)
    assert result.verdict is CheckVerdict.GREEN, result.said
    assert result.refusals == ()
    assert (tmp_path / DRAFT_NAME).read_text() == HIGH_CARD


def test_two_refusals_read_as_two_records_each_once(tmp_path: Path) -> None:
    result = Checker().check(TWO_TYPOS, tmp_path)
    assert result.verdict is CheckVerdict.REFUSED
    # The text form prints the first of several diagnostics twice (issue
    # #606); the reader keeps one of each.
    assert result.said.count("unresolved name 'hnad'") == 2
    assert [(r.line, r.message, r.near_misses) for r in result.refusals] == [
        (21, "unresolved name 'hnad'", ("hand",)),
        (30, "unresolved name 'scroe'", ("score",)),
    ]
    assert {r.file for r in result.refusals} == {DRAFT_NAME}


def test_a_syntax_error_is_a_refusal(tmp_path: Path) -> None:
    result = Checker().check(HIGH_CARD.replace("zones {", "zones {{"), tmp_path)
    assert result.verdict is CheckVerdict.REFUSED
    assert result.refusals[0].message.startswith("syntax error")


def test_an_invocation_the_checker_cannot_carry_out_is_the_rigs_fault(tmp_path: Path) -> None:
    checker = Checker(argv=("{python}", "-m", "cardlang", "check", "elsewhere.cardlang"))
    result = checker.check(HIGH_CARD, tmp_path)
    assert result.verdict is CheckVerdict.CANNOT_PROCEED
    assert result.exit_code == 2


def test_a_crash_is_never_a_refusal(tmp_path: Path) -> None:
    # A diagnostic-shaped line before the traceback: the crash still wins.
    code = (
        "import sys; print('game.cardlang:1:1: error: looks like a refusal', file=sys.stderr); "
        "raise RuntimeError('the checker fell over')"
    )
    result = _stand_in(code).check(HIGH_CARD, tmp_path)
    assert result.verdict is CheckVerdict.CRASHED
    assert result.exit_code == 1


def test_an_undocumented_exit_is_a_crash(tmp_path: Path) -> None:
    result = _stand_in("raise SystemExit(7)").check(HIGH_CARD, tmp_path)
    assert result.verdict is CheckVerdict.CRASHED


def test_exit_one_with_nothing_readable_is_unreadable(tmp_path: Path) -> None:
    result = _stand_in("import sys; print('something went wrong'); sys.exit(1)").check(
        HIGH_CARD, tmp_path
    )
    assert result.verdict is CheckVerdict.UNREADABLE


def test_a_hang_is_timed_out(tmp_path: Path) -> None:
    result = _stand_in("import time; time.sleep(30)", timeout=1.0).check(HIGH_CARD, tmp_path)
    assert result.verdict is CheckVerdict.TIMED_OUT


#: Every verdict, and output that reads as it. Keyed by the enum so a verdict
#: added without a row fails `test_every_verdict_has_a_row`.
VERDICT_ROWS: dict[CheckVerdict, tuple[int | None, str, bool]] = {
    CheckVerdict.GREEN: (0, "", False),
    CheckVerdict.REFUSED: (1, "game.cardlang:3:4: error: no such zone", False),
    CheckVerdict.CRASHED: (1, "Traceback (most recent call last):\n  boom", False),
    CheckVerdict.UNREADABLE: (1, "cardlang: something", False),
    CheckVerdict.CANNOT_PROCEED: (2, "cardlang: cannot read x", False),
    CheckVerdict.TIMED_OUT: (None, "", True),
}


def test_every_verdict_has_a_row() -> None:
    assert set(VERDICT_ROWS) == set(CheckVerdict)


@pytest.mark.parametrize("verdict", list(CheckVerdict), ids=lambda v: v.value)
def test_read_check_reaches_every_verdict(verdict: CheckVerdict) -> None:
    exit_code, stderr, timed_out = VERDICT_ROWS[verdict]
    assert read_check(exit_code, "", stderr, timed_out=timed_out).verdict is verdict


def test_notes_and_continuations_attach_to_their_diagnostic() -> None:
    text = (
        "game.cardlang:5:1: error: first line\n"
        "  more of the first\n"
        "lib.cardlang:9:2: note: where it stands\n"
        "error: an unlocated one\n"
    )
    first, second = parse_text(text)
    assert first.message == "first line\n  more of the first"
    assert [(n.file, n.line, n.message) for n in first.notes] == [("lib.cardlang", 9, "where it stands")]
    assert (second.file, second.line, second.message) == (None, None, "an unlocated one")


def test_the_same_refusal_is_keyed_on_its_code_once_it_has_one() -> None:
    plain = Refusal("game.cardlang", 1, 1, "error", "unresolved name 'x'", ("y",))
    offered_otherwise = Refusal("game.cardlang", 9, 9, "error", "unresolved name 'x'", ("z",))
    assert refusal_key(plain) == refusal_key(offered_otherwise)
    coded = Refusal("game.cardlang", 1, 1, "error", "reworded", code="unknown-name")
    recoded = Refusal("game.cardlang", 1, 1, "error", "worded again", code="unknown-name")
    assert refusal_key(coded) == refusal_key(recoded) != refusal_key(plain)


def test_the_json_form_waits_on_its_issue() -> None:
    assert "json" in CHECK_FORMS
    with pytest.raises(NotImplementedError, match="#1046"):
        read_check(0, "{}", "", form="json")
    with pytest.raises(ValueError, match="unknown checker form"):
        read_check(0, "", "", form="xml")
