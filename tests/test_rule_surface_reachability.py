"""Every rule clause the checker accepts must reach a runtime reader.

property:   A `rule` declaration is accepted only if some decision site can
            actually consult it. Rule enforcement has exactly ONE runtime
            consumer — `rules.legal_cards`, called from exactly one site
            (`mechanics.py`, with the move type fixed to `play_to_trick`) —
            so a rule affects play iff its `constrains:` names that move
            type AND it carries something enforceable there (a `demands:`
            card set, or an `exempts` set). Everything else parses, resolves,
            type-checks, serializes to IR, and is then silently dropped.
            That is the accepted-but-ignored class (decisions.md "Surface
            totality"), and this grid pins that each such shape is rejected
            loudly instead.
domain:     constrains-target x demands-presence x exempts-presence.
            Three things sit outside the axes, and none is a gap.
            `applies_when:` and `if_impossible:` affect nothing about whether
            a rule reaches a reader, so every inert combination involving
            them already falls inside a cell: a rule carrying `if_impossible`
            with no `demands` is inert for the reason the demands axis states, and an `applies_when` on an
            otherwise-inert rule is unreachable for the reason the constrains
            axis states -- crossing them would double the cell count and
            change no outcome. And `legal_moves:` is a separate surface with
            no runtime reader at all, owned by
            open-questions/phase-legal-moves.md.
registry:   constrains -- `stdlib.moves.LIBRARY_MOVE_TYPES`, plus the
                          clause-absent case (`constrains` is optional).
                          Its pin: `test_constrains_axis_is_the_move_registry`.
            demands    -- presence/absence of an optional clause.
            exempts    -- presence/absence of an optional clause.

The vacuous rule (`constrains: play_to_trick`, no `demands:`, no `exempts:`) is
REJECTED, and that is a judgment call rather than a consequence of the
reachability condition — such a rule is well-formed and reaches the reader; it
simply gives that reader nothing to do. It is rejected because a designer who
writes `rule X { constrains: play_to_trick  applies_when: <pred> }` believes
they have constrained something, which is the accepted-but-ignored experience
even though the mechanism differs. No corpus or stdlib rule is vacuous, so
nothing is lost; the cell is decided on judgment and reads as decided.
does not prove:  that an accepted rule changes play. Every cell stops at
            `check_dsl`, and the acceptance predicate `_reaches_a_reader` is
            AUTHORED from `rules.legal_cards`'s guards rather than read off
            them -- so what a green establishes is that the checker agrees
            with that reading of the reader, not that the reader, at its one
            call site in `mechanics.py`, then acts on the rule. Nothing here
            runs a game.

Framing check: RAN, and changed the domain. A fresh-context subagent given
only the definition sources (grammar, AST unions, the whole `cardlang/`
package) enumerated the rule surface and its readers. Its findings absent
from the author's derivation:
  - three separately-filed defects (issues #173, #174, #175), none of which
    the author's reachability framing would have surfaced.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES

# --- axes, each derived from the registry that defines it ---

CLAUSE_ABSENT = None

# The one move type any decision site passes to `rules.legal_cards`.
ENFORCED_MOVE_TYPE = "play_to_trick"

CONSTRAINS: tuple[str | None, ...] = (*sorted(LIBRARY_MOVE_TYPES), CLAUSE_ABSENT)
DEMANDS: tuple[bool, ...] = (False, True)
EXEMPTS: tuple[bool, ...] = (False, True)


def _reaches_a_reader(constrains: str | None, demands: bool, exempts: bool) -> bool:
    """The acceptance predicate, authored from `rules.legal_cards`'s guards —
    NOT read off the guard it is about to check. A rule is accepted iff it
    constrains the one enforced move type and carries something that site can
    act on: a card-set demand, or an exempt set."""
    if constrains != ENFORCED_MOVE_TYPE:
        return False
    return demands or exempts


# --- axis-derivation pins ---


def test_constrains_axis_is_the_move_registry() -> None:
    assert set(CONSTRAINS) == set(LIBRARY_MOVE_TYPES) | {CLAUSE_ABSENT}
    assert ENFORCED_MOVE_TYPE in LIBRARY_MOVE_TYPES


# --- the fixture ---

GAME = """
game G {{
  players: 4
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  waste : Discard }}
  state {{ x[player] : Integer = 0 }}
  phase play {{
    active_rules: [R]
    deal 5 cards from deck to each hand
    round play_to_trick from 0 over all players
          source hand into trick_pile winner highest_of_led_suit
    move all cards from trick_pile to waste
  }}
  winner: highest x
}}
rule R {{
{clauses}
}}
"""

CARD_SET = "cards in hand where card.suit is hearts"


def _source(constrains: str | None, demands: bool, exempts: bool) -> str:
    clauses = []
    if constrains is not CLAUSE_ABSENT:
        clauses.append(f"  constrains: {constrains}")
    if demands:
        # A demand carries its own mandatory `if_impossible` (a separate
        # guard). Supplying it keeps every rejection in this grid
        # attributable to reachability rather than to that guard.
        clauses.append(f"  demands: {CARD_SET}")
        clauses.append("  if_impossible: hand")
    if exempts:
        clauses.append(f"  exempts: {CARD_SET}")
    if not clauses:
        clauses.append("  applies_when: true")
    return GAME.format(clauses="\n".join(clauses))


# --- the grid ---


@pytest.mark.parametrize("exempts", EXEMPTS)
@pytest.mark.parametrize("demands", DEMANDS)
@pytest.mark.parametrize("constrains", CONSTRAINS)
def test_rule_surface_grid(
    constrains: str | None, demands: bool, exempts: bool
) -> None:
    src = _source(constrains, demands, exempts)

    if _reaches_a_reader(constrains, demands, exempts):
        check_dsl(src, "rule.cardlang")  # accepted: some reader can consult it
        return

    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "rule.cardlang")
    message = str(excinfo.value)

    # Each cell asserts the SPECIFIC guard it must trip. Bare rejection would
    # pass for a neighbouring guard and prove nothing about this cell.
    if constrains != ENFORCED_MOVE_TYPE:
        assert "no decision site" in message, message
    else:
        assert "enforces nothing" in message, message


# --- misuse probes: the sentences an author most plausibly writes instead ---


@pytest.mark.parametrize(
    ("label", "clauses", "needle"),
    [
        # A bring-in amount stated as a rule on the betting move.
        (
            "rule_on_a_betting_move",
            "  constrains: submit_bid\n"
            f"  demands: {CARD_SET}\n  if_impossible: hand",
            "no decision site",
        ),
        # Omitting `constrains:` reads as "applies everywhere", not "nowhere".
        (
            "constrains_omitted_with_a_valid_demand",
            f"  demands: {CARD_SET}\n  if_impossible: hand",
            "no decision site",
        ),
        # `applies_when` mistaken for the enforcing clause.
        (
            "applies_when_mistaken_for_the_constraint",
            "  constrains: play_to_trick\n  applies_when: true",
            "enforces nothing",
        ),
    ],
)
def test_misuse_probe_is_rejected_in_the_right_channel(
    label: str, clauses: str, needle: str
) -> None:
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(GAME.format(clauses=clauses), "probe.cardlang")
    assert needle in str(excinfo.value), str(excinfo.value)


def test_duplicate_clause_misread_is_not_closed_by_these_guards() -> None:
    """Issue #173, pinned as an ACCEPTED defect so the grid above cannot be
    read as closing it. Clauses are last-wins, so a duplicate `constrains:`
    whose LAST value is the enforced move type sails through — the guards
    narrow this defect's blast radius without closing it, and saying so in a
    test is what keeps the grid from reading as a closure it is not.

    Delete this test when #173 lands; it will fail there, which is the point.
    """
    src = GAME.format(
        clauses=(
            "  constrains: submit_bid\n"
            "  constrains: play_to_trick\n"
            f"  demands: {CARD_SET}\n"
            "  if_impossible: hand"
        )
    )
    check_dsl(src, "dup.cardlang")  # accepted today: the second clause wins
