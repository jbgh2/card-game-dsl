"""A misspelling is told once, at its cause.

When the checker refuses a spelling, a later check that reads the refused
text as written can refuse correct text as a consequence: a mode the
misspelled target meant is told it is never active, a query's body is told
its correct binder is unresolved and offered the misspelling to copy. The
consequence reaches the designer before or beside its cause and names the
wrong fix. A refusal a fix of the refused spelling could clear is withheld;
the fixes counted are the set the spelling was looked up in, never the Near
Misses, which are only offered.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a refused spelling's consequences are not told where a fix
                 drawn from the set the spelling was looked up in could clear
                 them, nor where they read the binder the spelling as written
                 would bind, and a mistake no such fix clears is still told.
domain:          (a) the binders a node introduces from designer text a check
                 can refuse, over the node kinds `_BINDER_SCOPE_FIELDS` scopes
                 (axis `BINDER_SOURCES`, keyed by the registry); (b) the
                 checks that compute a fact from references as written, so
                 that one refused reference refuses correct text elsewhere:
                 the mode-role invariant, and the members `RESIDUAL` names,
                 each a strict xfail naming its issue. Each suppression is
                 crossed with a probe that an independent slip beside it is
                 still told.
registry:        axis (a) is `cardlang.resolve._BINDER_SCOPE_FIELDS`,
                 pinned equal to `BINDER_SOURCES`'s keys; axis (b) has no
                 defining registry -- a fact computed from references is a
                 property of a check's body -- so its members are the
                 framing check's list, each executed (`RESIDUAL`).
held by:         Derived and Pinned: a withheld name is one lexical field
                 of `_Categories`, set where a binder is scoped and read by
                 the one unresolved-name arm, so no second site decides it;
                 the overshoot rows are Born-Green Pins, each naming its
                 reddening mutation. Not higher: which text a refusal's fix
                 could reach is a fact of each refusing check, and no union
                 states it.
does not prove:  that a withheld refusal is a consequence in fact. A mode no
                 sibling targets, in a phase whose other transition names no
                 sibling, is withheld although the designer may have meant
                 another mode; and in the body of a refused query or
                 simultaneous block, an unresolved name spelled as a binder
                 some fix would bind (a body `player` the designer got wrong)
                 is withheld although it may be a mistake of its own. Each is
                 told once the refused spelling is fixed. Nor that axis (b) is
                 complete: a check reading references as written that the
                 framing check did not list is absent, not red.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_ROOT = Path(__file__).resolve().parent.parent


def errors(source: str, *edits: tuple[str, str]) -> list[str]:
    """Every error line a game renders after `edits`, in report order, each
    once: the bag's whole list when it holds more than one, else the one."""
    text = (_ROOT / source).read_text()
    for old, new in edits:
        assert old in text, f"{source} no longer holds {old!r}: re-plant this edit"
        text = text.replace(old, new, 1)
    try:
        check_dsl(text, source)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", [])
        rendered = notes[0] if notes else exc.diagnostic.format()
        return [line for line in rendered.splitlines() if ": error: " in line]
    return []


_HEARTS = "docs/games/hearts.cardlang"
_TTT = "docs/games/tic-tac-toe.cardlang"
_TARGET_SLIP = ("transition_to: hearts_broken when", "transition_to: hearts_brokn when")
_TARGET_REFUSAL = (
    "docs/games/hearts.cardlang:81:9: error: transition_to target 'hearts_brokn' is not "
    "a sibling mode of this phase — a transition ends one condition and begins another, "
    "so its target is a `mode` declared beside this one; did you mean `hearts_broken`?"
)
_NOUN_SLIP = ("all cells where", "all cels where")
_NOUN_REFUSAL = (
    "docs/games/tic-tac-toe.cardlang:41:21: error: unknown position domain 'cel' -- "
    "declared position domains: cell; the board direction domain: dir; did you mean `cells`?"
)


# --------------------------------------------------------------------------
# The witnesses (issues #1059, #1062).
# --------------------------------------------------------------------------


def test_a_misspelled_transition_target_is_told_alone() -> None:
    """Issue #1059: the mode the target meant is not told it is never
    active."""
    assert errors(_HEARTS, _TARGET_SLIP) == [_TARGET_REFUSAL]


def test_a_misspelled_query_noun_is_told_alone() -> None:
    """Issue #1062: the body's correct `cell` is not refused, and nothing
    offers the misspelling."""
    assert errors(_TTT, _NOUN_SLIP) == [_NOUN_REFUSAL]


# --------------------------------------------------------------------------
# Overshoot: a mistake no fix of the refused spelling clears is still told.
# --------------------------------------------------------------------------


def test_an_independent_mistake_in_the_mode_is_still_told() -> None:
    """red under: `_resolve_phase_item`'s mode arm resolving none of the
    mode's `active_rules:` blocks."""
    got = errors(
        _HEARTS,
        _TARGET_SLIP,
        ("mode hearts_broken { }", "mode hearts_broken { active_rules: [MustFolowSuit] }"),
    )
    assert got[0] == _TARGET_REFUSAL
    assert len(got) == 2 and "undefined rule 'MustFolowSuit'" in got[1], got


def test_an_orphan_in_another_phase_is_still_told() -> None:
    """The withholding is the phase's own: an orphan whose siblings name no
    unresolved target is told, in a phase judged after the refusal. red
    under: `_check_modes`' never-active arm withheld whenever the bag holds a
    refusal (`and not bag.has_errors`)."""
    scoring = "    phase scoring {"
    got = errors(_HEARTS, _TARGET_SLIP, (scoring, scoring + "\n      mode lonely { }"))
    assert any("transition_to target 'hearts_brokn'" in line for line in got), got
    assert any("mode 'lonely' is never active" in line for line in got), got


def test_two_sources_naming_one_real_target_are_still_told() -> None:
    """red under: `_check_modes`' shared-target arm skipped in a phase that
    holds an unresolved target (`if undecided: break` above its loop)."""
    got = errors(
        _HEARTS,
        _TARGET_SLIP,
        (
            "      mode hearts_broken { }",
            "      mode hearts_broken { }\n      mode spades_out {\n"
            "        transition_to: hearts_broken when play_to_trick where action.card.suit is spades\n"
            "      }\n      mode clubs_out {\n"
            "        transition_to: hearts_broken when play_to_trick where action.card.suit is clubs\n"
            "      }",
        ),
    )
    assert any("modes 'spades_out' and 'clubs_out' both transition to 'hearts_broken'" in line for line in got), got


def test_an_independent_slip_in_the_query_body_is_still_told() -> None:
    """red under: the unresolved-name arm withholding every unresolved name
    in a refused query's body (`node.name in cats.withheld or cats.withheld`)
    rather than the names its noun's fixes bind."""
    got = errors(_TTT, _NOUN_SLIP, ("square[cell] is not empty)", "squre[cell] is not empty)"))
    assert got[0] == _NOUN_REFUSAL
    assert len(got) == 2 and "unresolved name 'squre'; did you mean `square`?" in got[1], got
    assert all("`cel`" not in line for line in got), got


_CAPTURE = (
    "demands: cards in hand where card is 2 of clubs",
    "demands: crad in hand where card is 2 of clubs",
)
# `crad` bound where the clause stands, so the collection set may be a
# membership and the capture check reads it.
_CRAD_BOUND = ("let shooter = actor", "let shooter = actor\n    let crad = actor")


def test_a_refused_collection_noun_withholds_its_body() -> None:
    """The membership capture's refusal: the body's correct `card` is not
    refused."""
    got = errors(_HEARTS, _CAPTURE, _CRAD_BOUND)
    assert len(got) == 1 and "unknown collection noun 'crad'" in got[0], got


def test_an_independent_slip_beside_a_refused_collection_noun_is_still_told() -> None:
    """red under: the unresolved-name arm withholding every unresolved name
    in a refused query's body (`node.name in cats.withheld or cats.withheld`)."""
    slipped = (_CAPTURE[0], _CAPTURE[1] + " and pass_dirction is left")
    got = errors(_HEARTS, slipped, _CRAD_BOUND)
    assert "unknown collection noun 'crad'" in got[0], got
    assert len(got) == 2 and "unresolved name 'pass_dirction'; did you mean `pass_direction`" in got[1], got
    assert all("`crad`" not in line for line in got), got


def test_an_independent_slip_beside_a_singular_count_noun_is_still_told() -> None:
    """A query told to pluralize its noun withholds nothing but its fixes'
    binders. red under: the withholding mutation above."""
    got = errors(
        _TTT,
        ("(all cells where square[cell] is not empty)", "(number of cell in cells where squre[cell] is empty) is 0"),
    )
    assert "needs the plural noun" in got[0], got
    assert any("unresolved name 'squre'; did you mean `square`?" in line for line in got), got


def test_an_independent_slip_in_a_refused_simultaneous_body_is_still_told() -> None:
    """red under: the withholding mutation above."""
    got = errors(
        _HEARTS,
        ("each player simultaneously:", "each playr simultaneously:"),
        ("to   hand[player offset_by pass_direction]", "to   hand[player offset_by pass_dirction]"),
    )
    assert "`each playr simultaneously` is not runnable" in got[0], got
    assert any("unresolved name 'pass_dirction'; did you mean `pass_direction`" in line for line in got), got
    assert all("`playr`" not in line for line in got), got


def test_a_refused_noun_withholds_the_binder_it_spells() -> None:
    """A body using the binder the designer's own noun spells is not told
    for the noun's refusal."""
    got = errors(_TTT, ("all cells where square[cell] is not empty", "all spaces where square[space] is not empty"))
    assert len(got) == 1 and "unknown position domain 'space'" in got[0], got


def test_an_independent_slip_beside_a_spelled_binder_is_still_told() -> None:
    """red under: the withholding mutation above."""
    got = errors(_TTT, ("all cells where square[cell] is not empty", "all spaces where squre[space] is not empty"))
    assert "unknown position domain 'space'" in got[0], got
    assert len(got) == 2 and "unresolved name 'squre'; did you mean `square`?" in got[1], got


_SUIT_BODY = ("          from hand[player]\n", "          from hand[player]\n          where card.suit is suit\n")


def test_a_refused_simultaneous_role_withholds_the_binder_it_spells() -> None:
    got = errors(_HEARTS, ("each player simultaneously:", "each suit simultaneously:"), _SUIT_BODY)
    assert "`each suit simultaneously` is not runnable" in got[0], got
    assert [line for line in got if "unresolved name" in line] == [], got


def test_an_independent_slip_beside_a_spelled_role_is_still_told() -> None:
    """red under: the withholding mutation above."""
    got = errors(
        _HEARTS,
        ("each player simultaneously:", "each suit simultaneously:"),
        _SUIT_BODY,
        ("to   hand[player offset_by pass_direction]", "to   hand[player offset_by pass_dirction]"),
    )
    assert "`each suit simultaneously` is not runnable" in got[0], got
    assert [line for line in got if "unresolved name" in line] == [
        line for line in got if "unresolved name 'pass_dirction'; did you mean `pass_direction`" in line
    ] != [], got


# --------------------------------------------------------------------------
# Axis (a): every binder-scoping node kind, by where its binder comes from.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Withheld:
    """A node kind whose binder is derived from text a check can refuse: a
    slip of that text, and the refusal that must stand alone."""

    source: str
    old: str
    new: str
    cause: str


# Where each binder-scoping node kind's binder comes from: a name the designer
# chooses, a fixed keyword the grammar spells, the content noun of the game's
# `cards:` or `pieces:` clause, or derived text (a `Withheld`). A refused
# `cards:`/`pieces:` clause is `RESIDUAL`'s.
BINDER_SOURCES: dict[str, str | Withheld] = {
    "Quantifier": "fixed",
    "Comprehension": "fixed",
    "CardQuery": "fixed",
    "PlayerQuery": "fixed",
    "DomainQuery": Withheld(_TTT, *_NOUN_SLIP, "unknown position domain 'cel'"),
    "SubsetQuery": "fixed",
    "Transfer": "flavor",
    "EpistemicOp": "flavor",
    "ForEach": "chosen",
    "EachSimultaneous": Withheld(
        _HEARTS, "each player simultaneously:", "each playr simultaneously:",
        "`each playr simultaneously` is not runnable",
    ),
    "Turns": "chosen",
    "HostedPoll": "chosen",
}


def test_the_binder_axis_is_the_scoping_registry() -> None:
    """red under: a node kind added to `_BINDER_SCOPE_FIELDS`."""
    from cardlang.resolve import _BINDER_SCOPE_FIELDS

    assert set(BINDER_SOURCES) == {kind.__name__ for kind in _BINDER_SCOPE_FIELDS}


def _withheld_cells() -> list[object]:
    cells: list[object] = []
    for kind, source in sorted(BINDER_SOURCES.items()):
        if not isinstance(source, Withheld):
            continue
        cells.append(pytest.param(source, id=kind))
    return cells


@pytest.mark.parametrize("cell", _withheld_cells())
def test_a_refused_binder_source_binds_nothing_and_withholds_its_body(cell: Withheld) -> None:
    got = errors(cell.source, (cell.old, cell.new))
    assert got and cell.cause in got[0], got
    unresolved = [line for line in got if "unresolved name" in line]
    assert unresolved == [], got


# --------------------------------------------------------------------------
# Axis (b): the checks reading references as written beyond the mode roles.
# --------------------------------------------------------------------------

# Each a slip whose only cause is its first refusal; every refusal after the
# first is a consequence the slip's fix clears.
RESIDUAL: dict[str, tuple[str, str, str, str]] = {
    "a `run` misspelled leaves its procedure never run": (
        "docs/games/cheat.cardlang", "run resolve_play(actor)", "run resolve_ply(actor)",
        "unknown procedure 'resolve_ply'"),
    "an offer misspelled leaves its move type never offered": (
        _HEARTS, "[charge_the_others, credit_the_shooter]", "[charge_the_othrs, credit_the_shooter]",
        "unknown move type 'charge_the_othrs'"),
    "a template argument misspelled is also an unresolved name": (
        _HEARTS, "NoLeadingSuitUntilBroken(hearts)", "NoLeadingSuitUntilBroken(heart)",
        "must be a suit literal"),
    "a deck misspelled leaves every card and suit unknown": (
        _HEARTS, "cards: standard52", "cards: standard53", "unknown deck 'standard53'"),
    "a zone index misspelled leaves every bare use of the family refused": (
        _HEARTS, "hand[player]     : Hand<player>", "hand[playr]     : Hand<player>",
        "unknown index role 'playr'"),
    "a `pieces:` written for a card deck refuses every clause reading a card": (
        _HEARTS, "cards: standard52", "pieces: standard52", "is a card deck"),
    "a simultaneous role misspelled leaves its body with no acting seat": (
        _HEARTS, "each player simultaneously:", "each playr simultaneously:",
        "is not runnable"),
}


@pytest.mark.parametrize(
    "member",
    [
        pytest.param(name, marks=pytest.mark.xfail(strict=True, reason="issue #1087"))
        for name in sorted(RESIDUAL)
    ],
)
def test_a_reference_misspelled_elsewhere_refuses_no_correct_text(member: str) -> None:
    source, old, new, cause = RESIDUAL[member]
    got = errors(source, (old, new))
    assert got and cause in got[0], got
    assert got == [got[0]], got
