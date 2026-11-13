"""A misspelling is told once, at its cause.

When the checker refuses a spelling, a later check that reads the refused
text as written can refuse correct text as a consequence: a procedure the
misspelled `run` meant is told it is never run, every card literal is told
its rank is unknown under a misspelled deck, a query's body is told its
correct binder is unresolved. The consequence reaches the designer beside its
cause and names the wrong fix. A refused spelling marks the slot it stands
in and the set it was looked up in; a check refusing on a fact read from a
slot marks what clears it; and `DiagnosticBag.settle` withholds a group of
marked refusals only when one fix of each refused spelling, drawn from that
set and never from the Near Misses, clears them all.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a refused spelling's consequences are not told where one
                 assignment of fixes, each drawn from the set its spelling
                 was looked up in, clears every one of them, nor where they
                 read the binder the spelling as written would bind; the
                 cause is told in the same words at the same position; and a
                 mistake no such assignment clears is still told.
domain:          (a) the binders a node introduces from designer text a check
                 can refuse, over the node kinds `_BINDER_SCOPE_FIELDS` scopes
                 (axis `BINDER_SOURCES`, keyed by the registry); (b) the
                 checks that compute a fact from references or declarations
                 as written, so that one refused spelling refuses correct
                 text elsewhere: the mode-role invariant and `MEMBERS`, each
                 with its whole ordered list, its fix applied, and an
                 independent mistake of the kind it withholds planted beside
                 it; `WIDTH`, a slip with no consequence of its own beside a
                 real mistake each clearing set leaves told and a wider one
                 would withhold, one row per clearing set or cause set a
                 member narrows; the members whose checks mark nothing yet
                 are `UNJOINED`, and the mistakes only a fix the slip's site
                 refuses would clear are `WAITS_FOR_THE_FIX`, each a strict
                 xfail.
registry:        axis (a) is `cardlang.resolve._BINDER_SCOPE_FIELDS`,
                 pinned equal to `BINDER_SOURCES`'s keys; axis (b) has no
                 defining registry -- a fact computed from references is a
                 property of a check's body -- so its members are the
                 framing check's list: `MEMBERS`, joined, and `UNJOINED`,
                 executed and not yet joined; the slot kinds are
                 `cardlang.diagnostics.SlotKind`.
held by:         Derived and Pinned: the decision has one owner
                 (`DiagnosticBag.settle`), run at every raise
                 (`cardlang.attribution`); a withheld binder name is one
                 lexical field of `_Categories`, read by the one
                 unresolved-name arm. Which fixes clear a marked refusal is
                 a fact of the marking check's body, held by its member's
                 rows, which apply the fix and plant the independent
                 mistake, and by its `WIDTH` row, which reddens under the
                 widening its last column names; the overshoot rows are
                 Born-Green Pins, each naming its reddening mutation. A
                 clearing set holding the mistake's own name, which every
                 slip of that kind may be fixed to (an offer's move type, a
                 reader call's clause, a library's contract row), has no
                 width a row can show. Not higher: what a check
                 reads is a property of its body, which no union states.
does not prove:  that a withheld refusal is a consequence in fact. A refusal
                 some fix of a refused spelling clears is withheld beside
                 that spelling though it is a real mistake whenever the
                 designer meant another fix: any one procedure never run
                 beside a `run` slip of its arity, any one move type never
                 offered beside an offer slip, any one clause read by
                 nothing beside a call slip, a card literal another deck
                 holds beside a deck slip, a `ranking:` clause wrong as cards
                 too beside a `pieces:` written for a card deck, a name some
                 fix of a refused binder source would bind. Each is told on
                 the check after the slip is fixed, and the check fails
                 meanwhile. Measured 2026-11-12 by an independent review: 105
                 of 1,500 sampled (slip, real mistake) pairs lost the real
                 mistake's refusal until the slip was fixed. A fix the
                 slip's own site would refuse is counted as a fix wherever
                 the cause's set is not narrowed to what may stand there
                 (`WAITS_FOR_THE_FIX`). Nor that a joined
                 check's clearing set is exact where no member plants a
                 mistake against it. Nor that axis (b) is complete: a check
                 reading references as written that no cell here executes,
                 the framing check's other witnesses among them, is absent,
                 not red. A group of more causes than `SETTLE_CAUSES`, or
                 whose search outruns `SETTLE_LIMIT`, is told whole: the
                 bound on causes has its row, and no row reaches the bound
                 on work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import _check, check_dsl

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
    under: `settle` withholding every marked refusal whenever the bag holds a
    cause (`withheld = set(marked) if roots else set()`)."""
    scoring = "    phase scoring {"
    got = errors(_HEARTS, _TARGET_SLIP, (scoring, scoring + "\n      mode lonely { }"))
    assert any("transition_to target 'hearts_brokn'" in line for line in got), got
    assert any("mode 'lonely' is never active" in line for line in got), got


def test_an_orphan_beside_the_mode_a_refused_target_meant_is_still_told() -> None:
    """One refused target is one fix, so two modes it could have named are
    not both its consequences: both are told. red under: `_assignable`
    answering True for every group (each refusal read alone)."""
    got = errors(
        _HEARTS, _TARGET_SLIP, ("      mode hearts_broken { }", "      mode hearts_broken { }\n      mode lonely { }")
    )
    assert got[0].startswith(_TARGET_REFUSAL.split("; did you mean")[0]), got
    assert any("mode 'lonely' is never active" in line for line in got), got


def test_two_sources_naming_one_real_target_are_still_told() -> None:
    """red under: `_check_modes`' shared-target arm skipped in a phase that
    holds a refused target (`if refused_targets: break` above its loop)."""
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
# `cards:` or `pieces:` clause, or derived text (a `Withheld`). A content
# noun refused under a `cards:`/`pieces:` clause written for the other kind is
# a member of `MEMBERS`.
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
# Axis (b): the checks computing a fact from references as written.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Member:
    """A slip whose only cause is its `cause` refusals, every refusal after
    them a consequence the slip's fix clears; and `independent`, a real
    mistake of the kind the withheld refusals report, planted beside it and
    told with it. `library` names the family library the slip and the
    mistake are edits of, checked through the game `source` that uses it."""

    source: str
    slip: tuple[str, str]
    cause: tuple[str, ...]
    independent: tuple[tuple[str, str], ...]
    library: str | None = None


_CHEAT = "docs/games/cheat.cardlang"
_BRIDGE = "docs/games/bridge.cardlang"
_SCORING = "    phase scoring {"
_LOCAL_TEMPLATE = ("move_type charge_the_others {", (
    "rule NoLead(s : Suit) {\n  constrains: play_to_trick\n  applies_when: state.led_suit is none\n"
    "  demands: cards in hand where card.suit is not s\n  if_impossible: hand\n}\n\n"
    "move_type charge_the_others {"))
_LOCAL_TEMPLATE_UNUSED = ("move_type charge_the_others {", (
    "rule NoLead2(s : Suit) {\n  constrains: play_to_trick\n  applies_when: state.led_suit is none\n"
    "  demands: cards in hand where card.suit is not s\n  if_impossible: hand\n}\n\n"
    "move_type charge_the_others {"))
_LOCAL_ACTIVATION = (
    "active_rules: [+ NoLeadingSuitUntilBroken(hearts)]",
    "active_rules: [+ NoLeadingSuitUntilBroken(hearts), + NoLead(hearts)]",
)
_PASS = (
    "      each player simultaneously:\n        move chosen 3 cards\n          from hand[player]\n"
    "          to   hand[player offset_by pass_direction]",
    "      for each player p:\n        as p {\n          move chosen 3 cards\n            from hand[p]\n"
    "            to   hand[p offset_by pass_direction]\n        }",
)
_REMOVAL = ("mode hearts_broken { }", "mode hearts_broken { active_rules: [- MustLeadTwoOfClubs] }")
_FOLD_OFFER = "offer to seat one of [check, bet, bet_big, call, fold, raise, raise_big]"

MEMBERS: dict[str, Member] = {
    "a `run` misspelled leaves its procedure never run": Member(
        _CHEAT, ("run resolve_play(actor)", "run resolve_ply(actor)"),
        ("docs/games/cheat.cardlang:138:5: error: run of unknown procedure 'resolve_ply'",),
        (("move_type allow {", "procedure zzz(who : Player) {\n  challenged := false\n}\n\nmove_type allow {"),)),
    "an offer misspelled leaves its move type never offered": Member(
        _HEARTS, ("[charge_the_others, credit_the_shooter]", "[charge_the_othrs, credit_the_shooter]"),
        ("docs/games/hearts.cardlang:107:9: error: offer names unknown move type 'charge_the_othrs'",),
        (("move_type credit_the_shooter {", "move_type xyz {\n  effect {\n  }\n}\n\nmove_type credit_the_shooter {"),)),
    "a template argument misspelled is also an unresolved name": Member(
        _HEARTS, ("NoLeadingSuitUntilBroken(hearts)", "NoLeadingSuitUntilBroken(heart)"),
        ("docs/games/hearts.cardlang:80:24: error: argument for rule parameter 'suit: Suit' of the standard "
         "library's rule `NoLeadingSuitUntilBroken` must be a suit literal (one of the deck's suits)",),
        (("where action.card.suit is hearts", "where action.card.suit is heartz"),)),
    "a deck misspelled leaves every card and suit unknown": Member(
        _HEARTS, ("cards: standard52", "cards: standard53"),
        ("docs/games/hearts.cardlang:22:1: error: unknown deck 'standard53' — known decks: canasta108, coup15, "
         "doppelkopf48, five_hundred43, kuhn3, leduc6, pinochle48, schnapsen20, scopa40, skat32, standard52, "
         "standard54, tarot78, tichu56",),
        (("where action.card.suit is hearts", "where action.card.suit is heartz"),
         ("elif card is Q of spades", "elif card is Z of spades"))),
    "a zone index misspelled leaves every bare use of the family refused": Member(
        _HEARTS, ("hand[player]     : Hand<player>", "hand[playr]     : Hand<player>"),
        ("docs/games/hearts.cardlang:33:5: error: unknown index role 'playr'",),
        (("captured[player] : PlayerPile<player>", "captured[player] : PlayerPile<team>"),)),
    "a `pieces:` written for a card deck refuses every clause reading a card": Member(
        _HEARTS, ("cards: standard52", "pieces: standard52"),
        ("docs/games/hearts.cardlang:22:1: error: 'standard52' is a card deck — declare it with "
         "`cards: standard52`, not `pieces:`",),
        (("ranking: aces high", "ranking: aces hgih"),)),
    "a simultaneous role misspelled leaves its body with no acting seat": Member(
        _HEARTS, ("each player simultaneously:", "each playr simultaneously:"),
        ("docs/games/hearts.cardlang:64:7: error: `each playr simultaneously` is not runnable — "
         "simultaneous moves are per player",),
        ((_SCORING, _SCORING + "\n      move chosen 1 cards from deck to trick_pile"),)),
    "a misspelled rule leaves its removal removing nothing": Member(
        _HEARTS, ("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, MustLeadTwoOfClub]"),
        ("docs/games/hearts.cardlang:76:38: error: active_rules names undefined rule 'MustLeadTwoOfClub'",),
        ((_SCORING, _SCORING + "\n      active_rules: [- MustFollowSuit]"),)),
    "a misspelled `+X` leaves its removal removing nothing": Member(
        _HEARTS, ("[MustFollowSuit, + MustLeadTwoOfClubs]", "[MustFollowSuit, + MustLeadTwoOfClub]"),
        ("docs/games/hearts.cardlang:76:38: error: active_rules names undefined rule 'MustLeadTwoOfClub'",),
        ((_SCORING, _SCORING + "\n      active_rules: [- MustFollowSuit]"),)),
    "a misspelled activation leaves its template never instantiated": Member(
        _HEARTS, ("+ NoLead(hearts)]", "+ NoLaed(hearts)]"),
        ("docs/games/hearts.cardlang:80:60: error: active_rules names undefined rule 'NoLaed'",),
        (_LOCAL_TEMPLATE_UNUSED,)),
    "a misspelled template argument leaves its template never instantiated": Member(
        _HEARTS, ("+ NoLead(hearts)]", "+ NoLead(heart)]"),
        ("docs/games/hearts.cardlang:80:60: error: argument for rule parameter 's: Suit' must be a suit "
         "literal (one of the deck's suits)",),
        (_LOCAL_TEMPLATE_UNUSED,)),
    "a misspelled reader leaves its clause read by nothing": Member(
        _BRIDGE, ("else suit_value(s)", "else suit_valu(s)"),
        ("docs/games/bridge.cardlang:267:60: error: call to unknown function 'suit_valu'",),
        (("  suit ranking: spades hearts diamonds clubs",
          "  suit ranking: spades hearts diamonds clubs\n  card_points {\n    A: 4\n  }"),)),
    "a misspelled `as` seat leaves its decision unseen": Member(
        _HEARTS, ("        as p {", "        as pp {"),
        ("docs/games/hearts.cardlang:65:12: error: unresolved name 'pp'",),
        ((_SCORING, _SCORING + "\n      for each player q:\n        as q {\n"
          "          move chosen 1 cards from hand[q offset_by left] to deck\n        }"),)),
    "a misspelled subscript leaves its read unseen": Member(
        _HEARTS, ("          from hand[player]\n", "          from hand[playr]\n"),
        ("docs/games/hearts.cardlang:66:21: error: unresolved name 'playr'",),
        ((_SCORING, _SCORING + "\n      for each player q:\n        as q {\n"
          "          move chosen 1 cards from hand[q offset_by left] to deck\n        }"),)),
    "a misspelled `when:` seat leaves its read unseen": Member(
        "docs/games/belote.cardlang",
        ("  when: belote_best_is(actor, 4, r, false)", "  when: belote_best_is(acotr, 4, r, false)"),
        ("docs/games/belote.cardlang:464:24: error: unresolved name 'acotr'",),
        ((", 4, r, false)\n", ", 4, r, false) and (number of cards in hand[actor offset_by left] where card.rank is r) > 0\n"),)),
    "a misspelled `as` seat leaves a read through a function unseen": Member(
        "docs/games/schnapsen.cardlang", ("          as fol {", "          as fl {"),
        ("docs/games/schnapsen.cardlang:100:14: error: unresolved name 'fl'",),
        (("    phase scoring {", "    phase scoring {\n      for each player q:\n        as q {\n"
          "          move chosen one card from hand[q offset_by left] to trick_pile\n        }"),)),
    "a misspelled board leaves its minted domains unknown": Member(
        _TTT, ("board: grid(3, 3)", "board: gird(3, 3)"),
        ("docs/games/tic-tac-toe.cardlang:20:3: error: unknown board family 'gird' (registered families: "
         "['draughts', 'grid', 'hex_rhombus', 'morris9'])",
         "docs/games/tic-tac-toe.cardlang:56:20: error: unknown board family 'gird' (registered families: "
         "['draughts', 'grid', 'hex_rhombus', 'morris9'])"),
        (("    square[cell]    : Cell<cell>", "    square[cell]    : Cell<cell>\n    other[cel]      : Cell<cel>"),)),
    "a library's misspelled offer leaves its contract row never offered": Member(
        "docs/games/five-card-draw.cardlang", (_FOLD_OFFER, _FOLD_OFFER.replace("fold,", "fodl,")),
        ("docs/libraries/poker_betting.cardlang:153:7: error: library 'poker_betting' names the move type "
         "'fodl', which the library does not have — it would resolve against whichever game imports this, "
         "so the library is not self-contained: define the move type in the library, contract for it with "
         "`<name> : Move` in `requires { }` so the including game defines it, or keep this definition in the game",),
        (("    fold              : Move", "    fold              : Move\n    muck              : Move"),),
        library="poker_betting"),
    "a `pieces:` written for a card deck leaves its card binder unresolved": Member(
        "docs/games/belote.cardlang", ("cards: skat32", "pieces: skat32"),
        ("docs/games/belote.cardlang:40:1: error: 'skat32' is a card deck — declare it with "
         "`cards: skat32`, not `pieces:`",),
        (("reveal one card from hand[bp] where is_royal(card)", "reveal one card from hand[bp] where is_royal(cardd)"),)),
    "a `cards:` written for a piece set leaves its board unminted": Member(
        _TTT, ("pieces: xo_marks", "cards: xo_marks"),
        ("docs/games/tic-tac-toe.cardlang:14:1: error: 'xo_marks' is a piece set — declare it with "
         "`pieces: xo_marks`, not `cards:`",),
        (("    square[cell]    : Cell<cell>", "    square[cell]    : Cell<cell>\n    other[cel]      : Cell<cel>"),)),
    "a misspelled board leaves its minted types unknown": Member(
        "docs/games/english-draughts.cardlang", ("board: draughts(8, 8)", "board: draugcts(8, 8)"),
        ("docs/games/english-draughts.cardlang:35:3: error: unknown board family 'draugcts' "
         "(registered families: ['draughts', 'grid', 'hex_rhombus', 'morris9'])",),
        (("function mine(c : cell, p : Player) =", "function mine(c : cel, p : Player) ="),)),
    "a misspelled hex board leaves its minted type unknown": Member(
        "docs/games/hex.cardlang", ("board: hex_rhombus(11)", "board: hex_rhmbus(11)"),
        ("docs/games/hex.cardlang:26:3: error: unknown board family 'hex_rhmbus' "
         "(registered families: ['draughts', 'grid', 'hex_rhombus', 'morris9'])",),
        (("    tile[cell]      : Cell<cell>", "    tile[cell]      : Cell<cell>\n    other[cel]      : Cell<cel>"),)),
    "a zone index misspelled leaves a Card parameter's hand undeclared": Member(
        "docs/games/schnapsen.cardlang", ("hand[player]", "hand[playeb]"),
        ("docs/games/schnapsen.cardlang:33:5: error: unknown index role 'playeb'",),
        (("    phase scoring {", "    phase scoring {\n      for each player q:\n        as q {\n"
          "          move chosen one card from hand[q offset_by left] to trick_pile\n        }"),)),
    "an offer misspelled leaves a move type's scope unestablished": Member(
        "docs/games/canasta.cardlang", ("[stage_card, close_meld]", "[stagk_card, close_meld]"),
        ("docs/games/canasta.cardlang:253:17: error: offer names unknown move type 'stagk_card'",),
        (("move_type stage_card {", "move_type xyz {\n  effect {\n  }\n}\n\nmove_type stage_card {"),)),
    "a misspelled subscript in a function a `when:` reads leaves its read unseen": Member(
        "docs/games/canasta.cardlang",
        ("  and ((number of cards in hand[p] where canasta_is_black3(card)) is 3",
         "  and ((number of cards in hand[pq] where canasta_is_black3(card)) is 3"),
        ("docs/games/canasta.cardlang:464:33: error: unresolved name 'pq'",),
        (("       or (number of cards in hand[p] where canasta_is_black3(card)) is 4",
          "       or (number of cards in hand[p offset_by left] where canasta_is_black3(card)) is 4"),)),
    "a deck misspelled in a game with a combination catalogue": Member(
        "docs/games/big-two.cardlang", ("cards: standard52", "cards: standard53"),
        ("docs/games/big-two.cardlang:29:1: error: unknown deck 'standard53' — known decks: canasta108, coup15, doppelkopf48, five_hundred43, kuhn3, leduc6, pinochle48, schnapsen20, scopa40, skat32, standard52, standard54, tarot78, tichu56",),
        (("any player where score[player] >= 100", "any player where scor[player] >= 100"),)),
    "a deck misspelled in a climbing game": Member(
        "docs/games/president.cardlang", ("cards: standard52", "cards: standard53"),
        ("docs/games/president.cardlang:30:1: error: unknown deck 'standard53' — known decks: canasta108, coup15, doppelkopf48, five_hundred43, kuhn3, leduc6, pinochle48, schnapsen20, scopa40, skat32, standard52, standard54, tarot78, tichu56",),
        (("any player where score[player] >= 11", "any player where scor[player] >= 11"),)),
    "a suit ranking misspelled leaves its suit left out": Member(
        _BRIDGE, ("suit ranking: spades hearts diamonds clubs", "suit ranking: spades hearts diamonds clbs"),
        ("docs/games/bridge.cardlang:37:3: error: suit ranking: 'clbs' is not a suit of deck 'standard52' — "
         "list the deck's suits (clubs, diamonds, hearts, spades) strongest first",),
        (("suit ranking: spades hearts diamonds", "suit ranking: spades hearts"),)),
    "a ranking convention misspelled refuses its correct word": Member(
        _HEARTS, ("ranking: aces high", "ranking: aces hgih"),
        ("docs/games/hearts.cardlang:22:1: error: ranking: names unknown rank 'hgih' — not a rank of deck "
         "'standard52' (known ranks: 10, 2, 3, 4, 5, 6, 7, 8, 9, A, J, K, Q)",),
        (("elif card is Q of spades", "elif card is Z of spades"),)),
    "a state type misspelled leaves the `winner:` target unrankable": Member(
        _HEARTS, ("    cumulative_score[player] : Integer = 0", "    cumulative_score[player] : Integr = 0"),
        ("docs/games/hearts.cardlang:40:5: error: unknown type 'Integr' in declaration of 'cumulative_score'",),
        (("offset_by pass_direction]", "offset_by pass_dirction]"),)),
    "a parameter type misspelled leaves a kernel answer's signature wrong": Member(
        "docs/games/belote.cardlang",
        ("function is_trump(card : Card) = card.suit is trump_suit", "function is_trump(card : Crad) = card.suit is trump_suit"),
        ("docs/games/belote.cardlang:345:1: error: unknown type 'Crad' in parameter 'card' of function 'is_trump'",),
        (("reveal one card from hand[bp] where is_royal(card)", "reveal one card from hand[bp] where is_royal(cardd)"),)),
}

# The edits each member's host needs before its slip.
_HOSTED: dict[str, tuple[tuple[str, str], ...]] = {
    "a misspelled activation leaves its template never instantiated": (_LOCAL_TEMPLATE, _LOCAL_ACTIVATION),
    "a misspelled template argument leaves its template never instantiated": (_LOCAL_TEMPLATE, _LOCAL_ACTIVATION),
    "a misspelled `as` seat leaves its decision unseen": (_PASS,),
    "a misspelled rule leaves its removal removing nothing": (_REMOVAL,),
    "a misspelled `+X` leaves its removal removing nothing": (
        ("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, + MustLeadTwoOfClubs]"), _REMOVAL),
}

_OFFER = re.compile(r"; did you mean .*\?$")


def _unoffered(lines: list[str]) -> list[str]:
    """`lines` without their Near Misses: these rows pin which refusals are
    told, never what a refusal offers."""
    return [_OFFER.sub("", line) for line in lines]


def _member_errors(
    monkeypatch: pytest.MonkeyPatch, member: Member, *edits: tuple[str, str], library_edits: tuple[tuple[str, str], ...] = ()
) -> list[str]:
    if member.library is not None:
        from cardlang.libraries import library_source_name, load_library
        from cardlang.parse import parse_library
        from tests.resolver_package import patch_resolver

        text = (_ROOT / library_source_name(member.library)).read_text()
        for old, new in library_edits:
            assert old in text, f"{member.library} no longer holds {old!r}: re-plant this edit"
            text = text.replace(old, new, 1)
        edited = parse_library(text, library_source_name(member.library))
        real = load_library
        patch_resolver(monkeypatch, "load_library", lambda name: edited if name == member.library else real(name))
        # The checked game is memoized on its own tree, which a library edit
        # leaves as it is.
        _check.cache_clear()
        try:
            return errors(member.source, *edits)
        finally:
            _check.cache_clear()
    return errors(member.source, *edits, *library_edits)


def _slipped(monkeypatch: pytest.MonkeyPatch, member: Member, *also: tuple[str, str]) -> list[str]:
    hosted = _HOSTED.get(_name(member), ())
    if member.library is not None:
        return _member_errors(monkeypatch, member, library_edits=(member.slip, *also))
    return _member_errors(monkeypatch, member, *hosted, member.slip, *also)


def _unslipped(monkeypatch: pytest.MonkeyPatch, member: Member, *also: tuple[str, str]) -> list[str]:
    hosted = _HOSTED.get(_name(member), ())
    if member.library is not None:
        return _member_errors(monkeypatch, member, library_edits=also)
    return _member_errors(monkeypatch, member, *hosted, *also)


def _name(member: Member) -> str:
    return next(name for name, m in MEMBERS.items() if m is member)


@pytest.mark.parametrize("member", sorted(MEMBERS))
def test_a_member_s_fix_clears_every_refusal_it_withholds(member: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The execution half of the oracle: the slip's fix, applied, leaves the
    host clean, so every refusal the slip adds is cleared by it."""
    assert _unslipped(monkeypatch, MEMBERS[member]) == []


@pytest.mark.parametrize("member", sorted(MEMBERS))
def test_a_reference_misspelled_elsewhere_refuses_no_correct_text(member: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole ordered list a slip renders is its cause, as told before
    any withholding, at the same position."""
    got = _unoffered(_slipped(monkeypatch, MEMBERS[member]))
    assert got == list(MEMBERS[member].cause), got


@pytest.mark.parametrize("member", sorted(MEMBERS))
def test_an_independent_mistake_beside_a_member_is_still_told(member: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every refusal of the independent mistake alone is told beside the
    slip, in the same words at the same position. red under: `_assignable`
    answering True for every group (each refusal read alone)."""
    m = MEMBERS[member]
    alone = _unoffered(_unslipped(monkeypatch, m, *m.independent))
    assert alone and all("syntax error" not in line for line in alone), f"{member}: the independent mistake is no mistake"
    beside = _unoffered(_slipped(monkeypatch, m, *m.independent))
    assert [line for line in alone if line not in beside] == [], beside


def test_a_card_no_deck_holds_is_told_beside_a_refused_content_kind() -> None:
    """A card literal naming no card of the set is wrong as cards too, so a
    `pieces:` written for a card deck withholds nothing for it. red under:
    the piece-literal arm marking every literal cleared by `cards:`."""
    got = errors(_HEARTS, ("cards: standard52", "pieces: standard52"), ("elif card is Q of spades", "elif card is Z of spades"))
    assert got[0].endswith("declare it with `cards: standard52`, not `pieces:`"), got
    assert any(":100:42: error:" in line and "`Z of spades`" in line for line in got), got
    assert all("`2 of clubs`" not in line for line in got), got



def test_a_card_literal_s_rank_and_suit_are_told_apart_under_a_refused_deck() -> None:
    """A rank no deck holds is told; the suit beside it, which a fix holds,
    is not. red under: the unknown-suit arm's `Unless` reading the whole
    literal (`sets_holding(nd.rank, nd.suit)`)."""
    got = errors(_HEARTS, ("cards: standard52", "cards: standard53"), ("elif card is Q of spades", "elif card is Z of spades"))
    assert any(":100:42: error: unknown rank 'Z' in card literal" in line for line in got), got
    assert all("unknown suit 'spades'" not in line for line in got), got


_AS_SEAT_OFFSET = (
    "      for each player q:\n        as qq {\n          move chosen 3 cards\n"
    "            from hand[q offset_by left]\n            to   hand[q offset_by pass_direction]\n        }"
)

# A read hidden under every fix of the slip beside it, at the read the slip
# leaves undecided: each slip, the mistake, and the refusal of the mistake.
HIDDEN_UNDER_EVERY_FIX: dict[str, tuple[str, tuple[tuple[str, str], ...], str]] = {
    "a family's index misspelled beside a read of another seat's instance": (
        _HEARTS,
        (("hand[player]     : Hand<player>", "hand[playr]     : Hand<player>"),
         ("          from hand[player]\n", "          from hand[player offset_by left]\n")),
        "docs/games/hearts.cardlang:66:16: error: a chosen movement's source is the pool seat `player` picks from",
    ),
    "a subscript misspelled inside an offset": (
        _CHEAT,
        (("move chosen claim_count cards from hand[actor] to played",
          "move chosen claim_count cards from hand[actr offset_by left] to played"),),
        "docs/games/cheat.cardlang:137:40: error: a chosen movement's source is the pool the acting seat picks from",
    ),
    "an `as` seat misspelled around a read of another seat's instance": (
        _HEARTS,
        ((_PASS[0], _AS_SEAT_OFFSET),),
        "docs/games/hearts.cardlang:67:18: error: a chosen movement's source is the pool seat `qq` picks from",
    ),
}


@pytest.mark.parametrize("cell", sorted(HIDDEN_UNDER_EVERY_FIX))
def test_a_read_no_fix_shows_is_told_beside_the_slip(cell: str) -> None:
    """red under: `_undecided_by` marking a read of a family with a refused
    index whatever the read (`if True:` for its `_own_reason` test), or
    marking every name in a subscript (`bare` taken from `_walk` of each
    spelling)."""
    source, edits, mistake = HIDDEN_UNDER_EVERY_FIX[cell]
    got = errors(source, *edits)
    assert any(line.startswith(mistake) for line in got), got


_SMUGGLING = "docs/libraries/smuggling.cardlang"
_SMUGGLING_RUN = ("        run settle_false_alarm()", "        run settle_flase_alarm()")
_SMUGGLING_ROW = (
    "    settle_false_alarm() : Procedure       // what an innocent shipment costs",
    "    settle_false_alarm() : Procedure       // what an innocent shipment costs\n    settle_other() : Procedure",
)


def _library_errors(path: str, *edits: tuple[str, str]) -> list[str]:
    """Every error line a library checked alone tells after `edits`, in
    report order, settled as its raise settles it."""
    from cardlang.diagnostics import DiagnosticBag
    from cardlang.parse import parse_library
    from cardlang.resolve import check_library_alone

    text = (_ROOT / path).read_text()
    for old, new in edits:
        assert old in text, f"{path} no longer holds {old!r}: re-plant this edit"
        text = text.replace(old, new, 1)
    bag = DiagnosticBag()
    check_library_alone(parse_library(text, path), bag)
    bag.settle()
    return [d.format().splitlines()[0] for d in bag.items]


def test_a_library_s_misspelled_run_leaves_no_row_never_run() -> None:
    """The library checked alone, as its own raise tells it (no game uses
    this library, so no game's check reaches it)."""
    assert _library_errors(_SMUGGLING) == []
    got = _library_errors(_SMUGGLING, _SMUGGLING_RUN)
    assert len(got) == 1 and "names the procedure 'settle_flase_alarm'" in got[0], got


def test_a_row_never_run_beside_a_library_s_misspelled_run_is_still_told() -> None:
    """red under: `_assignable` answering True for every group."""
    alone = _library_errors(_SMUGGLING, _SMUGGLING_ROW)
    assert len(alone) == 1 and "`settle_other() : Procedure` but never runs it" in alone[0], alone
    got = _library_errors(_SMUGGLING, _SMUGGLING_RUN, _SMUGGLING_ROW)
    assert any("`settle_other() : Procedure` but never runs it" in line for line in got), got


def test_two_refusals_of_one_text_with_no_other_cause_are_both_told() -> None:
    """A spelling refused twice, each refusal clearable by the other's fix,
    is still told: a cause is withheld only by a cause that is told. red
    under: `settle` giving every marked refusal clearers
    (`if items[c].refuses is None or c in doubles` dropped)."""
    from cardlang.diagnostic_codes import Code
    from cardlang.diagnostics import DiagnosticBag, SlotKind, Span, Unless, text_slot

    at = Span("g.cardlang", 10, 14, 1, 11)
    slot = text_slot(at)
    bag = DiagnosticBag()
    for _ in range(2):
        bag.unknown(
            "unresolved name 'hart'", "hart", ("hearts",), at, code=Code.UNKNOWN_NAME,
            slot=slot, unless=Unless(SlotKind.TEXT, frozenset({"hearts"}), frozenset({slot.name})),
        )
    bag.settle()
    assert [d.message for d in bag.items] == ["unresolved name 'hart'"] * 2
    assert all(d.refuses is None and d.unless == () for d in bag.items)

# The members the framing check listed whose consequence checks mark nothing
# yet: each slip, its cause, and the failure its cell is designed to meet.
UNJOINED: dict[str, tuple[str, tuple[str, str], str, type[BaseException]]] = {
    "a `pieces:` written for a card deck in a game its splice refuses first": (
        "docs/games/five-card-stud.cardlang", ("cards: standard52", "pieces: standard52"),
        "is a card deck", AssertionError),
}


@pytest.mark.parametrize(
    "member",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(strict=True, raises=UNJOINED[name][3], reason="issue #1131"),
        )
        for name in sorted(UNJOINED)
    ],
)
def test_an_unjoined_member_tells_its_cause_alone(member: str) -> None:
    source, slip, cause, _fails = UNJOINED[member]
    got = errors(source, slip)
    assert got and cause in got[0], got
    assert got == [got[0]], got


# A real mistake a fix of the refused spelling beside it would clear, where
# that fix is one the spelling's own site refuses: the cause's set is not
# narrowed to what may stand there, so the mistake waits for the cause's fix.
WAITS_FOR_THE_FIX: dict[str, tuple[str, tuple[tuple[str, str], ...], str]] = {
    "a call misspelled beside a table whose reader takes a Card": (
        _BRIDGE,
        (("  when: next_level(strain) <= 7", "  when: next_levl(strain) <= 7"),
         ("  suit ranking: spades hearts diamonds clubs",
          "  suit ranking: spades hearts diamonds clubs\n  card_points {\n    A: 4\n  }")),
        "card_points { } is read by nothing"),
    "a deck misspelled beside a card only a deck its `ranking:` refuses holds": (
        _HEARTS,
        (("cards: standard52", "cards: standard53"), ("elif card is Q of spades", "elif card is Joker of spades")),
        "Joker"),
}


@pytest.mark.parametrize(
    "cell",
    [
        pytest.param(name, marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #1131"))
        for name in sorted(WAITS_FOR_THE_FIX)
    ],
)
def test_a_mistake_only_a_refused_fix_clears_is_told(cell: str) -> None:
    source, edits, mistake = WAITS_FOR_THE_FIX[cell]
    got = errors(source, *edits)
    assert any(mistake in line for line in got[1:]), got


def test_a_check_with_a_withheld_refusal_never_passes() -> None:
    """A group is withheld only through a cause that is told, so settling
    leaves a bag holding an error whenever it held one. red under: `settle`
    withholding the roots of every group it withholds."""
    from cardlang.diagnostic_codes import Code
    from cardlang.diagnostics import DiagnosticBag, Slot, SlotKind, Span, Unless

    at = Span("g.cardlang", 0, 4, 1, 1)
    bag = DiagnosticBag()
    bag.unknown("unknown deck 'x'", "x", ("standard52",), at, code=Code.UNKNOWN_DECK, slot=Slot(SlotKind.DECK, ""))
    bag.error("a consequence", at, code=Code.UNKNOWN_NAME, unless=Unless(SlotKind.DECK, frozenset({"standard52"})))
    bag.settle()
    assert bag.has_errors and [d.message for d in bag.items] == ["unknown deck 'x'"]
    for name in sorted(MEMBERS):
        member = MEMBERS[name]
        if member.library is None:
            assert errors(member.source, *_HOSTED.get(name, ()), member.slip), name



# --------------------------------------------------------------------------
# Width: a slip with no consequence of its own, beside a real mistake that a
# member's clearing set leaves told and a wider one would withhold.
# --------------------------------------------------------------------------

_FCS = "docs/games/five-card-stud.cardlang"
_FCS_RUN = ("          run betting_street(best_showing_seat(), 20, 0)", "          run betting_streat(best_showing_seat(), 20, 0)")
_PASS_DIRCTION = ("offset_by pass_direction]", "offset_by pass_dirction]")

# Each row: the host, its edits (the slip first), the refusal of the real
# mistake, and the widening that withholds it.
WIDTH: dict[str, tuple[str, tuple[tuple[str, str], ...], str, str]] = {
    "a `run` misspelled beside a procedure of another arity never run": (
        _FCS, (_FCS_RUN, ("move_type fold {", "procedure zzz(who : Player) {\n  who := who\n}\n\nmove_type fold {")),
        "procedure 'zzz' is never run", "the `run` cause's fixes taken from every procedure"),
    "a `run` misspelled beside a move type no procedure offers": (
        _FCS, (_FCS_RUN, ("move_type fold {", "move_type xyz {\n  effect {\n  }\n}\n\nmove_type fold {")),
        "move type `xyz` is never offered", "the never-offered arm's procedures taken as every procedure"),
    "a template argument misspelled beside an unrelated unresolved name": (
        _HEARTS, (("NoLeadingSuitUntilBroken(hearts)", "NoLeadingSuitUntilBroken(heart)"), _PASS_DIRCTION),
        "unresolved name 'pass_dirction'", "the unresolved-name arm's text `Unless` reaching every text slot"),
    "a deck misspelled beside a name no deck holds": (
        _HEARTS, (("cards: standard52", "cards: standard53"), ("where action.card.suit is hearts", "where action.card.suit is heartz")),
        "unresolved name 'heartz'", "the deck `Unless` of an unresolved name reaching every set"),
    "a zone index misspelled beside a round source of another family": (
        _HEARTS, (("hand[player]     : Hand<player>", "hand[playr]     : Hand<player>"), ("source hand", "source trick_pile")),
        "a round's `source` names the zone each player plays from", "`kept_per_player` naming every zone"),
    "a zone index misspelled beside an owner no role of the game names": (
        _HEARTS, (("captured[player]", "captured[playr]"), ("PlayerPile<player>", "PlayerPile<team>")),
        "typed 'PlayerPile<team>'", "the index cause's fixes keeping `team` in a game with no `teams:`"),
    "a subscript misspelled in a function another seat's instance is passed to": (
        "docs/games/canasta.cardlang",
        (("  and ((number of cards in hand[p] where canasta_is_black3(card)) is 3",
          "  and ((number of cards in hand[pq] where canasta_is_black3(card)) is 3"),
         ("  when: canasta_black3_ok(actor)", "  when: canasta_black3_ok(actor offset_by left)")),
        "reads the cards in `hand[pq]`", "`_seat_names` taking every name in scope unjudged"),
    "a rule misspelled beside a removal in another phase": (
        _HEARTS, (("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, MustLeadTwoOfClub]"),
                  (_SCORING, _SCORING + "\n      active_rules: [- MustFollowSuit]")),
        "`-MustFollowSuit` removes a rule that is never added", "the removal's `Unless` reaching every rule slot"),
    "a `+X` misspelled beside a removal in another phase": (
        _HEARTS, (("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, + MustLeadTwoOfClub]"),
                  (_SCORING, _SCORING + "\n      active_rules: [- MustFollowSuit]")),
        "`-MustFollowSuit` removes a rule that is never added", "the removal's `Unless` reaching every rule slot"),
    "a rule misspelled beside the removal of a template it cannot name": (
        _HEARTS, (("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, MustLeadTwoOfClub]"),
                  ("mode hearts_broken { }", "mode hearts_broken { active_rules: [- NoLeadingSuitUntilBroken] }")),
        "`-NoLeadingSuitUntilBroken` removes a rule that is never added", "the rule cause's fixes taken from every rule"),
    "a rule misspelled beside a template of another arity never instantiated": (
        _HEARTS, (("[MustFollowSuit, MustLeadTwoOfClubs]", "[MustFollowSuit, MustLeadTwoOfClub]"), _LOCAL_TEMPLATE_UNUSED),
        "rule 'NoLead2' is parameterized but never instantiated", "the rule cause's fixes taken from every rule"),
    "an unresolved name beside a template whose arguments no slip refused": (
        _HEARTS, (_PASS_DIRCTION, _LOCAL_TEMPLATE_UNUSED),
        "rule 'NoLead2' is parameterized but never instantiated", "the never-instantiated text `Unless` reaching every text slot"),
    "a simultaneous role misspelled beside a decision outside its block": (
        _HEARTS, (("each player simultaneously:", "each playr simultaneously:"),
                  (_SCORING, _SCORING + "\n      move chosen 1 cards from deck to trick_pile")),
        "a chosen movement is written where no player is acting", "the block's mark left on after the block"),
    "a simultaneous role misspelled around a seat its body binds anew": (
        _HEARTS, (("each player simultaneously:", "each playr simultaneously:"),
                  ("        move chosen 3 cards\n          from hand[player]\n          to   hand[player offset_by pass_direction]",
                   "        as 1 { move chosen one card from hand[actor offset_by left] to deck }")),
        "a chosen movement's source is the pool seat 1 picks from", "an enclosing seat's marks kept inside a seat bound anew"),
    "a board misspelled beside a zone of a domain no board mints": (
        _TTT, (("board: grid(3, 3)", "board: gird(3, 3)"),
               ("    square[cell]    : Cell<cell>", "    square[cell]    : Cell<cell>\n    other[cel]      : Cell<cel>")),
        "unknown index role 'cel'", "`board_mints` answering for every name"),
    "a board misspelled beside a parameter type no board mints": (
        "docs/games/english-draughts.cardlang", (("board: draughts(8, 8)", "board: draugcts(8, 8)"),
                                                 ("function mine(c : cell, p : Player) =", "function mine(c : cel, p : Player) =")),
        "unknown type 'cel' in parameter 'c' of function 'mine'", "`board_mints` answering for every name"),
    "a `pieces:` written for a card deck beside a name no content kind spells": (
        "docs/games/belote.cardlang", (("cards: skat32", "pieces: skat32"),
                                       ("reveal one card from hand[bp] where is_royal(card)", "reveal one card from hand[bp] where is_royal(cardd)")),
        "unresolved name 'cardd'", "`content_nouns_naming` answering every content kind"),
    "a `pieces:` written for a card deck beside a card the deck lacks": (
        _HEARTS, (("cards: standard52", "pieces: standard52"), ("elif card is Q of spades", "elif card is Z of spades")),
        "`Z of spades`", "the piece-literal arm marking every literal cleared by `cards:`"),
    "an unresolved name beside a suit really left out": (
        _BRIDGE, (("let required = 6 + contract_level", "let required = 6 + contract_levl"),
                  ("suit ranking: spades hearts diamonds clubs", "suit ranking: spades hearts diamonds")),
        "suit ranking: leaves out clubs", "the left-out arm's text `Unless` reaching every text slot"),
    "a `cards:` written for a piece set beside a zone of a domain no board mints": (
        _TTT, (("pieces: xo_marks", "cards: xo_marks"),
               ("    square[cell]    : Cell<cell>", "    square[cell]    : Cell<cell>\n    other[cel]      : Cell<cel>")),
        "unknown index role 'cel'", "`board_mints` answering for every name"),
    "a state type misspelled beside a `winner:` target of a known unrankable type": (
        _HEARTS, (("      pass_direction : SeatDirection = hold", "      pass_direction : SeatDirecton = hold"),
                  ("    cumulative_score[player] : Integer = 0", "    cumulative_score[player] : Player = 0")),
        "`winner:` ranks the game on state variable 'cumulative_score', declared `Player`",
        "the winner arm's type `Unless` reaching every type slot"),
    "a parameter type misspelled beside a kernel answer of a known wrong type": (
        "docs/games/belote.cardlang", (("function bel_card_points(c : Card) =", "function bel_card_points(c : Crad) ="),
                                       ("function is_trump(card : Card) = card.suit is trump_suit",
                                        "function is_trump(card : Rank) = card.suit is trump_suit")),
        "answers the kernel's `is_trump(card : Card) : Boolean`, so it takes exactly one Card",
        "the kernel-answer arm's type `Unless` reaching every type slot"),
}


@pytest.mark.parametrize("cell", sorted(WIDTH))
def test_a_mistake_a_wider_clearing_set_would_withhold_is_told(cell: str) -> None:
    """Each row reddens under its own widening (`WIDTH`'s last column),
    planted and run per row."""
    source, edits, mistake, _widening = WIDTH[cell]
    slip_alone = errors(source, edits[0])
    assert len(slip_alone) >= 1 and mistake not in " ".join(slip_alone), slip_alone
    got = errors(source, *edits)
    assert any(mistake in line for line in got), got



def test_a_group_of_more_causes_than_the_search_takes_is_told_whole() -> None:
    """A thousand refused spellings reaching one consequence are told with
    it, the search never deeper than `SETTLE_CAUSES`. red under: `_assignable`
    searching any number of causes (its `SETTLE_CAUSES` test dropped), which
    recurses once per cause."""
    from cardlang.diagnostic_codes import Code
    from cardlang.diagnostics import DiagnosticBag, Slot, SlotKind, Span, Unless

    at = Span("g.cardlang", 0, 4, 1, 1)
    bag = DiagnosticBag()
    for i in range(1000):
        bag.unknown(
            f"run of unknown procedure 'p{i}'", f"p{i}", ("zzz",), at,
            code=Code.UNKNOWN_PROCEDURE, slot=Slot(SlotKind.PROCEDURE, str(i)),
        )
    bag.error("procedure 'zzz' is never run", at, code=Code.UNUSED_DECLARATION,
              unless=Unless(SlotKind.PROCEDURE, frozenset({"zzz"})))
    bag.settle()
    assert len(bag.items) == 1001 and bag.items[-1].message == "procedure 'zzz' is never run"
