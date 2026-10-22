"""A phase's rules and modes apply at the trick rounds its subtree runs.

property:   the rules asked at a trick round's card decision are the round's
            own phase's set, built down the chain of enclosing phases: each
            phase starts from its parent's set (a slot holding any plain entry
            starts empty instead), applies its own `active_rules:` and then its
            holding modes' deltas. An ancestor's mode is ended by a play in a
            nested phase's trick. The set is read at every play, so a mode
            that ends mid-trick stops constraining the plays after it. A mode's
            condition resets when the phase declaring it is entered, and
            nowhere else. A phase whose `active_rules:` or modes no trick round
            in its subtree can ask is refused at check time.
domain:     four axes.
            Inheritance: the four ways a slot meets its parent's set (none, a
            `+`, a `-`, a plain entry), at depth one and two, plus an
            ancestor's mode.
            Reset: every way the declaring phase is reached again or not (a
            parent's loop re-entering it, a `when` guard re-entering it, its
            own `repeat until`, a statement loop inside it, an unrelated nested
            looping phase inside it).
            Read time: the play after the one that ends a mode, in the same
            trick.
            Reach: where a trick round can stand relative to the phase that
            holds the rules (its own body, a statement nested in it, a hook, a
            nested phase, a sibling, a parent), crossed with the two holders
            (`active_rules:`, a mode), and the two round forms, of which only
            the trick form asks rules. A round in an offered move type's effect
            runs at the offering site, so it counts for the phase that offers.
            A trigger's decisions are judged against every trick round that
            reads it.
            A `-X` removal reaches what its ancestors add.
registry:   the rule set and live exits: `cardlang.runtime.active_rules`; the
            reset: `cardlang.runtime.driver.run_phase`; the refusal:
            `cardlang.resolve._check_rules_reach_a_trick` over
            `cardlang.resolve._reaches_a_trick_round`; removal reach:
            `cardlang.resolve._check_rule_removes`; trigger decisions:
            `cardlang.resolve._HiddenReads._judge_trick_context_positions`;
            round forms: `cardlang.runtime.mechanics.build_form`'s arms;
            phase items: tests/mode_axes.py; mode roles and mode-set shapes:
            tests/test_mode_surface.py; rules bind at the trick form's card
            decision alone: `cardlang.runtime.mechanics.TrickForm.candidates`.
does not prove:  that the corpus nests rules anywhere: every rule-bearing
            corpus phase runs its own round and holds no sub-phase, so the
            inheritance arms run on these fixtures alone.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cardlang import pipeline
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime import rules as rules_module
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"

RULES = """
rule MustFollow {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand[actor] where card.suit is state.led_suit
  if_impossible: hand[actor]
}
rule AlsoRule {
  constrains: play_to_trick
  demands: cards in hand[actor] where true
  if_impossible: hand[actor]
}
"""

TRICKS = """      repeat until (all players where hand[player] is empty) {
        round play_to_trick from ldr over all players source hand into pile
              winner highest_of_led_suit
        move all cards from pile to deck
        ldr := winner
      }"""


def _game(body: str, state: str = "") -> str:
    return f"""
game Reach {{
  players: 2
  max_length: 2000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0  ldr : Player = 0  hands : Integer = 0  done : Boolean = false{state} }}
  phase root {{
{body}
  }}
  winner: highest score
}}
{RULES}
"""


@contextmanager
def _asked() -> Iterator[list[tuple[tuple[str, ...], tuple[str, ...], int]]]:
    """Each trick decision's (rules asked, fired transitions, plays so far in
    the trick), in play order."""
    seen: list[tuple[tuple[str, ...], tuple[str, ...], int]] = []
    real = rules_module.legal_cards

    def spy(actor, move_type, ctx):  # type: ignore[no-untyped-def]
        played = len(ctx.rs.zones.single("pile").cards)
        seen.append(
            (
                tuple(r.name for r in ctx.active_rules),
                tuple(sorted(ctx.rs.fired_transitions)),
                played,
            )
        )
        return real(actor, move_type, ctx)

    rules_module.legal_cards = spy
    try:
        yield seen
    finally:
        rules_module.legal_cards = real


Asked = list[tuple[tuple[str, ...], tuple[str, ...], int]]


def _games(src: str, seeds: range = range(3)) -> list[Asked]:
    """One game's trick decisions per seed, in play order."""
    pipeline._check.cache_clear()
    game = check_dsl(src, "reach.cardlang")
    out: list[Asked] = []
    for seed in seeds:
        with _asked() as seen:
            play_game(game, random.Random(seed))
        assert seen, "no trick decision was asked"
        out.append(seen)
    return out


def _play(src: str, seeds: range = range(3)) -> Asked:
    return [ask for game in _games(src, seeds) for ask in game]


DEAL = "    shuffle deck\n    deal 5 cards from deck to each hand"


# --- inheritance -------------------------------------------------------------

INHERITANCE = {
    "no slot": ("active_rules: [MustFollow]", "", {("MustFollow",)}),
    "add": ("active_rules: [MustFollow]", "active_rules: [+ AlsoRule]", {("MustFollow", "AlsoRule")}),
    "remove": ("active_rules: [MustFollow, AlsoRule]", "active_rules: [- AlsoRule]", {("MustFollow",)}),
    "plain shadows": ("active_rules: [MustFollow]", "active_rules: [AlsoRule]", {("AlsoRule",)}),
}


@pytest.mark.parametrize("case", sorted(INHERITANCE))
def test_a_nested_trick_phase_inherits_its_parent_s_rules(case: str) -> None:
    """red under (plain shadows): drop the empty start for a slot holding a
    plain entry in `runtime/active_rules.compute_active_rules`."""
    parent, child, expected = INHERITANCE[case]
    src = _game(
        f"    {parent}\n{DEAL}\n    phase tricks {{\n      {child}\n{TRICKS}\n    }}"
    )
    assert {asked for asked, _f, _p in _play(src)} == expected


def test_inheritance_reaches_through_two_levels() -> None:
    src = _game(
        f"    active_rules: [MustFollow]\n{DEAL}\n    phase middle {{\n"
        f"      phase tricks {{\n{TRICKS}\n      }}\n    }}"
    )
    assert {asked for asked, _f, _p in _play(src)} == {("MustFollow",)}


def test_an_ancestor_s_mode_applies_and_ends_in_a_nested_trick() -> None:
    """The mode holds at the first play and is ended by a nested trick's play;
    afterwards its rule is gone."""
    src = _game(
        "    mode strict {\n      active_rules: [+ MustFollow]\n"
        "      transition_to: loose when play_to_trick where action.card.rank is A\n"
        "    }\n    mode loose { }\n"
        f"{DEAL}\n    phase tricks {{\n{TRICKS}\n    }}",
    )
    games = _games(src, range(8))
    assert all(game[0][0] == ("MustFollow",) for game in games)
    seen = [ask for game in games for ask in game]
    assert any(fired == ("loose",) for _a, fired, _p in seen)
    assert all(asked == () for asked, fired, _p in seen if fired == ("loose",))


# --- read time -----------------------------------------------------------------


def test_a_mode_ended_by_the_lead_stops_constraining_the_follow() -> None:
    src = _game(
        "    mode strict {\n      active_rules: [+ MustFollow]\n"
        "      transition_to: loose when play_to_trick\n    }\n    mode loose { }\n"
        f"{DEAL}\n{TRICKS}",
    )
    seen = _play(src)
    follows = [asked for asked, _f, played in seen if played == 1]
    assert follows and all(asked == () for asked in follows)


# --- reset ---------------------------------------------------------------------

MODES = (
    "      mode before {\n        active_rules: [+ MustFollow]\n"
    "        transition_to: after when play_to_trick\n      }\n      mode after { }\n"
)


def _assert_two_hands_each_open_unended(game: Asked) -> None:
    """Five tricks a hand: the first trick of each hand opens with nothing
    fired, and every later trick of that hand opens with it fired."""
    opens = [(asked, fired) for asked, fired, played in game if played == 0]
    assert len(opens) == 10, opens
    for hand in (opens[:5], opens[5:]):
        assert hand[0] == (("MustFollow",), ())
        assert all(f == ("after",) for _a, f in hand[1:])


def test_a_parent_s_loop_re_entering_the_declaring_phase_resets_it() -> None:
    """red under: drop the entry reset in `runtime/driver.run_phase`."""
    src = _game(
        "    phase hand_loop repeat until hands >= 2 {\n"
        "      before_each { move all cards to deck  shuffle deck  deal 5 cards from deck to each hand }\n"
        f"      phase play {{\n{MODES}{TRICKS}\n        hands += 1\n      }}\n    }}"
    )
    for game in _games(src):
        # The trick after the second hand's deal opens in `before` again.
        _assert_two_hands_each_open_unended(game)


def test_a_when_guard_re_entering_the_declaring_phase_resets_it() -> None:
    """red under: drop the entry reset in `runtime/driver.run_phase`."""
    src = _game(
        "    phase hand_loop repeat until hands >= 2 {\n"
        "      before_each { move all cards to deck  shuffle deck  deal 5 cards from deck to each hand }\n"
        f"      phase play when true {{\n{MODES}{TRICKS}\n        hands += 1\n      }}\n    }}"
    )
    for game in _games(src):
        _assert_two_hands_each_open_unended(game)


def test_the_declaring_phase_s_own_loop_keeps_the_condition() -> None:
    """A `repeat until` on the phase declaring the modes iterates inside one
    entry, so a condition ended in one iteration stays ended in the next."""
    src = _game(
        f"{DEAL}\n    phase play repeat until (all players where hand[player] is empty) {{\n"
        f"{MODES}"
        "      round play_to_trick from ldr over all players source hand into pile\n"
        "            winner highest_of_led_suit\n"
        "      move all cards from pile to deck\n"
        "      ldr := winner\n    }"
    )
    for game in _games(src):
        later_tricks = [(asked, fired) for asked, fired, played in game if played == 0][1:]
        assert later_tricks and all(f == ("after",) and a == () for a, f in later_tricks)


def test_a_statement_loop_inside_the_declaring_phase_keeps_the_condition() -> None:
    """red under: clear the declaring phase's conditions on each iteration of a
    statement `repeat until`."""
    src = _game(
        f"    phase play {{\n{MODES}"
        "      repeat until hands >= 2 {\n"
        "        move all cards to deck  shuffle deck  deal 5 cards from deck to each hand\n"
        f"{TRICKS}\n        hands += 1\n      }}\n    }}"
    )
    for game in _games(src):
        opens = [(asked, fired) for asked, fired, played in game if played == 0]
        assert opens[0] == (("MustFollow",), ())
        assert all(f == ("after",) for _a, f in opens[1:])


def test_an_unrelated_nested_loop_leaves_the_condition_alone() -> None:
    src = _game(
        f"{DEAL}\n    phase play {{\n{MODES}"
        "      round play_to_trick from ldr over all players source hand into pile\n"
        "            winner highest_of_led_suit\n"
        "      move all cards from pile to deck\n"
        "      ldr := winner\n"
        "      phase side repeat until done { done := true }\n"
        f"{TRICKS}\n    }}"
    )
    for game in _games(src):
        opens = [(asked, fired) for asked, fired, played in game if played == 0]
        assert opens[0] == (("MustFollow",), ())
        assert all(f == ("after",) for _a, f in opens[1:])


# --- reach (the refusal) ---------------------------------------------------------

HOLDERS = {
    "active_rules": "active_rules: [MustFollow]",
    "mode": (
        "mode strict {\n        active_rules: [+ MustFollow]\n"
        "        transition_to: loose when play_to_trick\n      }\n      mode loose { }"
    ),
}

ROUND_STMT = (
    "round play_to_trick from ldr over all players source hand into pile\n"
    "            winner highest_of_led_suit"
)

# Where the round stands relative to phase `holder`, and whether the holder's
# rules reach it.
PLACEMENTS: dict[str, tuple[str, bool]] = {
    "own body": (f"{DEAL}\n    phase holder {{\n      {{held}}\n      {ROUND_STMT}\n    }}", True),
    "nested statement": (
        f"{DEAL}\n    phase holder {{\n      {{held}}\n      if true {{\n        {ROUND_STMT}\n      }}\n    }}",
        True,
    ),
    "nested phase": (
        f"{DEAL}\n    phase holder {{\n      {{held}}\n      phase inner {{\n        {ROUND_STMT}\n      }}\n    }}",
        True,
    ),
    "hook": (
        "    phase holder repeat until hands >= 1 {\n      {held}\n"
        f"      before_each {{ deal 5 cards from deck to each hand  {ROUND_STMT} }}\n"
        "      hands += 1\n    }",
        True,
    ),
    "sibling": (f"{DEAL}\n    phase holder {{\n      {{held}}\n    }}\n    phase other {{\n      {ROUND_STMT}\n    }}", False),
    "parent": (f"{DEAL}\n    phase holder {{\n      {{held}}\n    }}\n    {ROUND_STMT}", False),
    "offered move's effect": (
        f"{DEAL}\n    phase holder {{\n      {{held}}\n"
        "      repeat until (all players where hand[player] is empty) { offer to ldr one of [go] }\n    }",
        True,
    ),
    "nowhere": (f"{DEAL}\n    phase holder {{\n      {{held}}\n    }}", False),
}

GO = f"""
move_type go {{
  effect {{
    {ROUND_STMT}
    move all cards from pile to deck
    ldr := winner
  }}
}}
"""


@pytest.mark.parametrize("holder", sorted(HOLDERS))
@pytest.mark.parametrize("placement", sorted(PLACEMENTS))
def test_rules_are_refused_where_no_trick_round_can_ask_them(holder: str, placement: str) -> None:
    template, reaches = PLACEMENTS[placement]
    src = _game(template.replace("{held}", HOLDERS[holder]))
    if "offer to ldr one of [go]" in src:
        src += GO
    pipeline._check.cache_clear()
    if reaches:
        check_dsl(src, "reach.cardlang")
        return
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "reach.cardlang")
    message = str(excinfo.value)
    assert "'holder'" in message and "trick round" in message


def test_a_climbing_round_asks_no_rule() -> None:
    src = (GAMES / "big-two.cardlang").read_text()
    climbing = src.replace(
        "      legal_moves: [play_combination]\n",
        "      legal_moves: [play_combination]\n      active_rules: [AlsoRule]\n",
        1,
    )
    assert climbing != src
    climbing += "\nrule AlsoRule {\n  constrains: play_to_trick\n  demands: cards in hand[actor] where true\n  if_impossible: hand[actor]\n}\n"
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(climbing, "big-two-rules.cardlang")
    assert "trick round" in str(excinfo.value)


def test_the_refusal_names_the_spellings_that_bind_a_hand_rolled_trick() -> None:
    src = _game(f"{DEAL}\n    phase holder {{\n      active_rules: [MustFollow]\n    }}")
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "reach.cardlang")
    message = str(excinfo.value)
    assert "where" in message and "follows_lead" in message


# --- the trigger's own readers ----------------------------------------------------

TRIGGER_WITH_A_DECISION = (
    "    mode strict {\n      active_rules: [+ MustFollow]\n"
    "      transition_to: loose when play_to_trick where (choose integer in 0 .. 1) is 0\n"
    "    }\n    mode loose { }\n"
)


@pytest.mark.parametrize("nested", [False, True], ids=["own phase", "nested phase"])
def test_a_trigger_decision_is_refused_wherever_the_reading_trick_stands(nested: bool) -> None:
    """A trigger is read by every trick round in its phase's subtree, so a
    `choose` in it is judged against each of them."""
    tricks = f"    phase tricks {{\n{TRICKS}\n    }}" if nested else TRICKS
    src = _game(TRIGGER_WITH_A_DECISION + f"{DEAL}\n{tricks}")
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "reach.cardlang")
    assert "no player is acting" in str(excinfo.value)


# --- a removal reaches what the ancestors add -------------------------------------


def test_a_child_removes_a_rule_its_parent_adds() -> None:
    src = _game(
        f"    active_rules: [MustFollow, AlsoRule]\n{DEAL}\n"
        f"    phase tricks {{\n      active_rules: [- AlsoRule]\n{TRICKS}\n    }}"
    )
    pipeline._check.cache_clear()
    check_dsl(src, "reach.cardlang")


def test_a_child_removing_a_rule_nothing_adds_is_refused() -> None:
    src = _game(
        f"    active_rules: [MustFollow]\n{DEAL}\n"
        f"    phase tricks {{\n      active_rules: [- AlsoRule]\n{TRICKS}\n    }}"
    )
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "reach.cardlang")
    assert "-AlsoRule" in str(excinfo.value)
