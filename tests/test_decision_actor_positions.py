"""A decision, or a read of `actor`, is written where a player is acting.

property:   a `choose`, a `chosen` movement to one zone, or a read of the
            `actor` pronoun written at a position where no player is acting is
            refused at check time, at the decision, with a fix that position
            can take; one written under a binder that names the acting player
            checks clean and plays
domain:     position {phase statement, phase `when`, phase `repeat until`,
            `before_each`, `after_each`, `loser:`, a function called from
            `loser:`, a procedure run from a phase statement, an `if` in a
            phase, an `offer`'s player, a `turns` leader, a mode's
            `transition_to` trigger and a Delegated Play helper where a trick
            round stands outside any binder, a state default} x need {`choose
            integer`, `chosen` movement, `actor`} where the position holds it
            (a function never reads `actor`: functions are hermetic; a state
            default's `choose` and `actor` are `_check_state_default_scope`'s);
            and the acting positions {`as`, `for each player`, `turns`, an
            offered move type's effect and `when:`, a procedure run under
            `as`, a function called under `for each`, a chosen deal `to each`}
            as controls that play
registry:   the acting-seat scope of `resolve._HiddenReads` (`_ReadScope.acting`),
            set by the binders `_seat_rebinding` names; the differentials below
            hold each refused decision against the runtime's own refusal
            (`Ctx.require_actor`) by execution
does not prove:  that a trick round under a binder reads its mode triggers
            under that binder's seat: the trick-context positions are judged
            acting only where every trick round of the game stands under one.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.execute import REFUSALS

CHOOSE = "choose integer in 0 .. 1"


def _game(
    *,
    phase_head: str = "phase play",
    pre: str = "",
    body: str = "as 0 { move chosen 1 card from hand[0] to pile }",
    result: str = "winner: highest score",
    defs: str = "",
) -> str:
    return f"""game G {{
  players: 2
  max_length: 50
  cards: standard52
  zones {{
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }}
  state {{ score[player] : Integer = 0  bid : Integer = 0  done : Boolean = false }}
  {phase_head} {{
    {pre}
    shuffle deck
    deal 1 card from deck to each hand
    {body}
  }}
  {result}
}}
{defs}
"""


_PICK = "move_type pick { effect { done := true } }"

UNACTING: dict[str, str] = {
    "loser": _game(result=f"loser: {CHOOSE}"),
    "loser via function": _game(
        result="loser: pick_one()", defs=f"function pick_one() = {CHOOSE}"
    ),
    "phase statement choose": _game(body=f"bid := {CHOOSE}"),
    "phase statement chosen move": _game(
        body="move chosen 1 card from pile to deck"
    ),
    "phase when": _game(phase_head=f"phase play when ({CHOOSE}) is 1"),
    "phase repeat until": _game(
        phase_head=f"phase play repeat until ({CHOOSE}) is 1"
    ),
    "before_each": _game(
        phase_head="phase play repeat until done",
        pre=f"before_each {{ score[1] += {CHOOSE} }}",
        body="done := true",
    ),
    "after_each": _game(
        phase_head="phase play repeat until done",
        pre=f"after_each {{ score[1] += {CHOOSE} }}",
        body="done := true",
    ),
    "procedure run from a phase statement": _game(
        body="run decide()",
        defs=f"procedure decide() {{ bid := {CHOOSE} }}",
    ),
    "if statement in a phase": _game(body=f"if ({CHOOSE}) is 1 {{ done := true }}"),
    "offer's player": _game(
        body=f"offer to ({CHOOSE}) one of [pick]", defs=_PICK
    ),
    "turns leader": _game(
        body=f"turns t from ({CHOOSE}) over all players until done {{ done := true }}"
    ),
    "actor in loser": _game(result="loser: actor"),
    "actor in a phase statement": _game(body="score[actor] += 1"),
    "actor in a phase gate": _game(phase_head="phase play when actor is 0"),
}

# The `actor` cells: a read, not a decision. The runtime reads None there --
# refused where it indexes a store or selects the loser, silent where it is
# compared (`when actor is 0` skips the phase), so the checker is the one wall.
ACTOR_READS = frozenset(k for k in UNACTING if k.startswith("actor "))

ACTING: dict[str, str] = {
    "as": _game(body=f"as 0 {{ bid := {CHOOSE} }}"),
    "for each player": _game(body=f"for each player p: score[p] := {CHOOSE}"),
    "turns": _game(
        body=f"turns t from 0 over all players until done {{ bid := {CHOOSE}\n done := true }}"
    ),
    "offered effect": _game(
        body="offer to 0 one of [decide]",
        defs=f"move_type decide {{ effect {{ bid := {CHOOSE} }} }}",
    ),
    "offered when": _game(
        body="offer to 0 one of [decide, pick]",
        defs=f"move_type decide {{ when: ({CHOOSE}) is 1\n effect {{ done := true }} }}\n{_PICK}",
    ),
    "procedure run under as": _game(
        body="as 1 { run decide() }",
        defs=f"procedure decide() {{ bid := {CHOOSE} }}",
    ),
    "function called under for each": _game(
        body="for each player p: score[p] := pick_one()",
        defs=f"function pick_one() = {CHOOSE}",
    ),
    "actor under as": _game(body="as 1 { score[actor] += 1 }"),
}


@pytest.mark.parametrize("position", list(UNACTING))
def test_a_decision_with_no_acting_player_is_refused(position: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(UNACTING[position], "g.cardlang")
    assert "no player is acting" in str(ei.value), str(ei.value)


@pytest.mark.parametrize("position", list(ACTING))
def test_a_decision_under_an_acting_binder_checks_clean_and_plays(position: str) -> None:
    play_game(check_dsl(ACTING[position], "g.cardlang"), random.Random(0))


@pytest.mark.parametrize("position", sorted(set(UNACTING) - ACTOR_READS))
def test_each_refused_decision_is_one_the_runtime_refuses(
    position: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The planted fault: with the static refusal silenced, every refused
    position checks clean and the playout is refused where it reaches the
    decision -- the state each issue measured, held by execution. A position
    the walker refused while the runtime binds a player plays here instead,
    and reddens.

    red under: drop `Ctx.require_actor`'s refusal -- a silenced position then
    plays to completion."""
    monkeypatch.setattr(
        "cardlang.resolve._HiddenReads._report_no_actor", lambda *a, **k: None
    )
    # A distinct game name: `check_dsl` memoizes on the tree, and a silenced
    # check must not answer for the guarded one.
    game = check_dsl(UNACTING[position].replace("game G {", "game Unguarded {", 1), "g.cardlang")
    with pytest.raises((*REFUSALS, OwnerGuardError), match="no acting player"):
        play_game(game, random.Random(0))


def test_the_loser_refusal_names_a_fix_the_clause_can_take() -> None:
    """`loser:` holds one expression, read after the last phase: the fix is
    to decide during play and name the result, never `as <player> { }`."""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(UNACTING["loser"], "g.cardlang")
    msg = str(ei.value)
    assert "after the last phase" in msg and "state variable" in msg, msg
    assert "for each player" not in msg, msg


def test_a_chosen_deal_to_each_is_decided_by_each_receiver() -> None:
    """`chosen ... to each` needs no acting seat: each receiving seat picks
    its own share, so a phase statement holds it and it plays."""
    play_game(
        check_dsl(
            _game(body="move all cards from deck to pile\n    deal chosen 1 card from pile to each hand"),
            "g.cardlang",
        ),
        random.Random(0),
    )


def test_a_choose_inside_a_chosen_deal_to_each_is_refused() -> None:
    """The deal's own clauses are evaluated before any receiver picks."""
    with pytest.raises(DiagnosticError, match="no player is acting"):
        check_dsl(
            _game(body=f"deal chosen ({CHOOSE}) card from pile to each hand"),
            "g.cardlang",
        )


_HEARTS = open("docs/games/hearts.cardlang").read()
_BRIDGE = open("docs/games/bridge.cardlang").read()
_TRIGGER = "where action.card.suit is hearts"
_HELPER = "function chooser_for(p : Player) = if p is dummy then declarer else p"

# Positions the trick round evaluates in its own context: a mode's
# `transition_to` trigger and a Delegated Play helper's body. Each corpus
# game's trick round stands outside any binder that names who acts.
TRICK_CONTEXT: dict[str, str] = {
    "mode trigger choose": _HEARTS.replace(
        _TRIGGER, f"where action.card.suit is hearts and ({CHOOSE}) is 0", 1
    ),
    "mode trigger actor": _HEARTS.replace(
        _TRIGGER, "where action.card.suit is hearts and actor is 0", 1
    ),
    "delegated play helper choose": _BRIDGE.replace(
        _HELPER,
        f"function chooser_for(p : Player) = if ({CHOOSE}) is 0 then p else p",
        1,
    ),
}


@pytest.mark.parametrize("position", list(TRICK_CONTEXT))
def test_a_trick_round_context_with_no_acting_player_refuses_a_decision(
    position: str,
) -> None:
    assert TRICK_CONTEXT[position] not in (_HEARTS, _BRIDGE)
    with pytest.raises(DiagnosticError, match="no player is acting"):
        check_dsl(TRICK_CONTEXT[position], f"{position}.cardlang")


@pytest.mark.parametrize("default", ["who : Player? = actor", "y : Integer = if actor is 1 then 1 else 0"])
def test_a_state_default_cannot_read_actor(default: str) -> None:
    """A default is evaluated outside any turn (`_check_state_default_scope`,
    the Owner Guard of defaults, beside its `choose` arm)."""
    src = _game().replace("done : Boolean = false", f"done : Boolean = false  {default}")
    with pytest.raises(DiagnosticError, match="cannot read `actor`"):
        check_dsl(src, "g.cardlang")


def test_the_gate_refusal_points_before_the_gate() -> None:
    """A `when` gate is read before its phase's body, so a decision made in
    that body can never open it: the fix names an earlier phase."""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(UNACTING["phase when"], "g.cardlang")
    assert "earlier phase" in str(ei.value), str(ei.value)


@pytest.mark.parametrize("position", ["actor in loser", "actor in a phase gate"])
def test_an_actor_refusal_at_an_expression_slot_names_a_writable_fix(position: str) -> None:
    """`loser:` and a gate hold one expression; no binder can be written there."""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(UNACTING[position], "g.cardlang")
    msg = str(ei.value)
    assert "state variable" in msg and "as <player>" not in msg, msg


@pytest.mark.parametrize("position", ["mode trigger choose", "delegated play helper choose"])
def test_each_refused_trick_context_decision_is_one_the_runtime_refuses(
    position: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The planted fault for the trick-context cells, as for the others: with
    the refusal silenced, the round reaches the decision and refuses it.

    red under: drop `Ctx.require_actor`'s refusal."""
    monkeypatch.setattr(
        "cardlang.resolve._HiddenReads._report_no_actor", lambda *a, **k: None
    )
    src = TRICK_CONTEXT[position].replace("game Hearts {", "game UnguardedHearts {", 1)
    src = src.replace("game Bridge {", "game UnguardedBridge {", 1)
    game = check_dsl(src, f"{position}.cardlang")
    with pytest.raises((*REFUSALS, OwnerGuardError), match="no acting player"):
        play_game(game, random.Random(0))
