"""Heads-up Hold'em's pack: the parser, the hand read, and the baseline claim.

The load-bearing test here is `test_the_baseline_beats_random_on_chips`. Every
number this game reports is "against the rule baseline", so a baseline that does
not actually beat random makes all of them unreadable — and the first version of
this policy did not: it folded 57% of the decisions where folding was legal and
won 33.8% of 400 hands against a uniform-random opponent, while finishing only
+43 chips. That is the failure a green suite cannot see, so it is asserted here
rather than assumed.
"""

from __future__ import annotations

import math
import statistics

import pytest

from ..agents import DecisionView, RandomAgent
from ..holdem import (
    FLUSH,
    FULL_HOUSE,
    HIGH_CARD,
    PAIR,
    QUADS,
    STRAIGHT,
    TRIPS,
    TWO_PAIR,
    HoldemRuleAgent,
    build_rule_agent,
    category,
    decision_facts,
    parse,
)

# A real information state, captured from the adapter at a pre-flop decision.
PREFLOP = (
    "P0|board=[];burn=?;deck=#47;muck=?;hole[0]=[4♥,8♦];hole[1]=#2;shown[0]=[];"
    "shown[1]=[]|state:acted={0:False,1:False};bet_by={0:1,1:2};bet_to_match=2;"
    "big_blind=1;button=0;committed={0:1,1:2};folded={0:False,1:False};"
    "in_hand={0:True,1:True};limit=2;net={0:0,1:0};raise_cap=4;raises=1;"
    "stack={0:99,1:98}|obs:('move', 'deck', 1, 'burn', None)"
)
FLOP = (
    "P1|board=[A♠,J♦,Q♥];burn=?;deck=#43;muck=?;hole[0]=#2;hole[1]=[5♣,5♥];"
    "shown[0]=[];shown[1]=[]|state:acted={0:False,1:False};bet_by={0:0,1:0};"
    "bet_to_match=0;big_blind=1;button=0;committed={0:2,1:2};"
    "folded={0:False,1:False};in_hand={0:True,1:True};limit=2;net={0:0,1:0};"
    "raise_cap=4;raises=0;stack={0:98,1:98}|obs:('announce', 0, 'call')"
)


def _c(text: str) -> tuple[tuple[str, str], ...]:
    """Cards from a compact spelling: `_c("A♠ K♠ Q♠ J♠ 10♠")`."""
    out = []
    for token in text.split():
        out.append((token[:-1], token[-1]))
    return tuple(out)


def test_parse_reads_only_what_the_seat_is_entitled_to() -> None:
    info = parse(PREFLOP)
    assert info.seat == 0
    assert info.hole == (("4", "♥"), ("8", "♦"))
    assert info.board == ()
    assert (info.bet_to_match, info.limit, info.raises, info.raise_cap) == (2, 2, 1, 4)
    assert info.owed == 1  # the small blind owes the big blind's extra chip
    assert info.pot == 3
    assert info.street == "preflop"

    flop = parse(FLOP)
    assert flop.seat == 1
    assert flop.hole == (("5", "♣"), ("5", "♥"))
    assert flop.board == (("A", "♠"), ("J", "♦"), ("Q", "♥"))
    assert flop.owed == 0
    assert flop.street == "flop"


def test_parse_refuses_a_state_it_does_not_understand() -> None:
    """A parser that returned defaults would surface a format change as a
    baseline that plays badly — a silent wrong answer — instead of a crash."""
    with pytest.raises(ValueError):
        parse("P0|board=[]|state:bet_to_match=2")  # no hole, no bet_by
    with pytest.raises(ValueError):
        parse("not an information state at all")


@pytest.mark.parametrize(
    ("cards", "expected"),
    [
        ("A♠ K♠ Q♠ J♠ 10♠", FLUSH),  # a straight flush ranks as its flush here
        ("7♠ 7♥ 7♦ 7♣ 2♠", QUADS),
        ("7♠ 7♥ 7♦ 2♣ 2♠", FULL_HOUSE),
        ("A♠ 9♠ 6♠ 4♠ 2♠", FLUSH),
        ("5♠ 6♥ 7♦ 8♣ 9♠", STRAIGHT),
        ("A♠ 2♥ 3♦ 4♣ 5♠", STRAIGHT),  # the wheel
        ("7♠ 7♥ 7♦ 9♣ 2♠", TRIPS),
        ("7♠ 7♥ 9♦ 9♣ 2♠", TWO_PAIR),
        ("7♠ 7♥ K♦ 9♣ 2♠", PAIR),
        ("A♠ J♥ 9♦ 6♣ 3♠", HIGH_CARD),
        # Seven cards, the real showdown size: the best five are what count.
        ("A♠ A♥ K♦ K♣ 3♠ 7♥ 2♦", TWO_PAIR),
        ("2♠ 3♠ 4♠ 5♠ 6♠ K♥ K♦", FLUSH),
    ],
)
def test_category_reads_the_best_hand_available(cards: str, expected: int) -> None:
    """Categories only — no kickers, and a straight flush is not separated from
    a flush. Both are deliberate: this ranks a holding for a BETTING decision,
    and the engine settles pots with `cardlang/runtime/poker.py`. The cases
    below pin exactly that scope, so a reader cannot mistake it for an
    evaluator."""
    assert category(_c(cards)) == expected


def test_decision_facts_record_what_was_on_offer() -> None:
    """`offered` is what makes an action rate honest: without it a fold count
    over all decisions mixes "declined to fold" with "could not fold"."""
    view = DecisionView(
        player=0,
        infostate=PREFLOP,
        legal_actions=[1, 2, 3],
        legal_strings=["call", "fold", "raise"],
    )
    facts = decision_facts(view, "raise")
    assert facts["verb"] == "raise"
    assert facts["offered"] == ["call", "fold", "raise"]
    assert facts["street"] == "preflop"
    assert facts["owed"] == 1


def test_the_baseline_only_ever_returns_a_legal_action() -> None:
    """Including the awkward tail: at the raise cap, facing a bet, a STRONG
    holding wants to raise and cannot, so none of its preferred verbs is on
    offer and the conservative fallback is the only path left.

    The infostate is varied deliberately. `PREFLOP` holds 4♥ 8♦, which the
    policy reads as weak, so `fold` is preferred and available in every case —
    the tail is never entered. Replacing the whole tail with an illegal action
    id leaves this test green if the strong fixture is dropped; that was
    measured, not assumed.
    """
    strong = PREFLOP.replace("hole[0]=[4♥,8♦]", "hole[0]=[A♠,A♥]")
    for infostate, legal in (
        (PREFLOP, ["check", "bet"]),
        (PREFLOP, ["call", "fold", "raise"]),
        (PREFLOP, ["call", "fold"]),
        (PREFLOP, ["check"]),
        # The tail: a pocket pair reads STRONG, wants raise/bet/call/check, and
        # the capped street offers only call and fold.
        (strong, ["call", "fold"]),
        (strong, ["fold"]),  # the degenerate case: nothing preferred at all
    ):
        agent = HoldemRuleAgent(seed=0)
        view = DecisionView(
            player=0,
            infostate=infostate,
            legal_actions=list(range(10, 10 + len(legal))),
            legal_strings=legal,
        )
        assert agent.choose(view) in view.legal_actions


def _match(a_factory, b_factory, n: int) -> tuple[float, float, float]:  # type: ignore[no-untyped-def]
    """Play `n` hands, alternating seats, and return (mean net, t, win rate)
    for the first factory. Seats alternate because seat 0 posts the small blind
    and acts first pre-flop — a structural asymmetry that would otherwise be
    read as skill."""
    pyspiel = pytest.importorskip("pyspiel")
    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    game = pyspiel.load_game("cardlang_holdem_heads_up")
    nets: list[float] = []
    wins = 0
    for i in range(n):
        focus = i % 2
        seats = {focus: a_factory(i * 100 + focus), 1 - focus: b_factory(i * 100 + 1 - focus)}
        state = game.new_initial_state()
        state.apply_action(i)
        while not state.is_terminal():
            p = state.current_player()
            legal = list(state.legal_actions())
            view = DecisionView(
                player=p,
                infostate=state.information_state_string(p),
                legal_actions=legal,
                legal_strings=[state.action_to_string(p, a) for a in legal],
            )
            state.apply_action(seats[p].choose(view))
        net = state.returns()[focus]
        nets.append(net)
        wins += net > 0
    mean = statistics.mean(nets)
    t = mean / (statistics.stdev(nets) / math.sqrt(len(nets)))
    return mean, t, wins / n


def test_the_baseline_beats_random_on_chips() -> None:
    """The claim every reported Hold'em number rests on.

    CHIPS, not hands won, is the assertion. Heads-up with two forced blinds, a
    player can win a minority of hands and still finish ahead by losing small
    and winning big — the first version of this policy did exactly that
    (+43 chips over 400 hands while winning 33.8% of them), which is why win
    rate alone could not have caught it. `t` is over the per-hand chip delta,
    with seats alternating so the small blind's structural disadvantage cancels.

    red under: restore the original pre-flop bands (pairs, two broadway cards
    and aces only). RUN, not predicted: the baseline finishes +0.16 chips/hand
    instead of +1.35 and this test fails on the `mean > 0.5` assertion — the
    chip-edge assertion catches it before the `t` one does.
    `test_the_baseline_wins_more_hands_than_random` fails too, at 0.352.
    """
    mean, t, _ = _match(
        lambda s: HoldemRuleAgent(seed=s), lambda s: RandomAgent(seed=s), n=400
    )
    assert mean > 0.5, f"baseline finished {mean:+.2f} chips/hand against random"
    assert t > 2.5, (
        f"baseline's chip edge over random is {t:.1f} standard errors — not a "
        f"separation, so every rate measured against this opponent is unreadable"
    )


def test_the_baseline_wins_more_hands_than_random() -> None:
    """The weaker instrument, kept because it is the headline metric the design brief
    asks for and it must at least point the right way. It is WEAK here by
    construction: forced blinds decide a large share of hands before anyone
    acts, so a real edge shows up as a few points of win rate and as a large
    chip delta."""
    _, _, win_rate = _match(
        lambda s: HoldemRuleAgent(seed=s), lambda s: RandomAgent(seed=s), n=400
    )
    assert win_rate > 0.50, f"baseline won {win_rate:.3f} of hands against random"


def test_build_rule_agent_honours_its_one_tunable() -> None:
    agent = build_rule_agent({"aggression": 0.9, "name": "tight"}, seed=3)
    assert isinstance(agent, HoldemRuleAgent)
    assert (agent.aggression, agent.name) == (0.9, "tight")
    default = build_rule_agent({}, seed=0)
    assert isinstance(default, HoldemRuleAgent)
    assert default.aggression == 0.25  # the a-priori default
