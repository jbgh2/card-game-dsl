"""Kuhn poker: the solver, the parser, and the leak-freeness pins for a second
game.

The load-bearing tests here are the ones that check the solver against something
that does not share its assumptions:

- `test_payoff_table_matches_the_engine` walks the ENGINE's tree and compares
  every leaf. The payoff table is hand-written; without this it could drift from
  the DSL description silently and every number in this file would move.
- `test_the_nash_family_is_unexploitable` computes the exploitability of the
  hard-coded equilibrium constants using the independent best-response code. If
  either the constants or the best response is wrong, they disagree. Neither is
  trusted on its own.
- `test_dominated_actions_are_actually_dominated` derives the domination claim
  from the payoff table rather than restating it, so `decision_facts` cannot
  quietly flag the wrong pair.

Offline throughout: no API key, no network. The engine-facing tests skip without
the `openspiel` extra, and the solver tests do not need it at all.
"""

from __future__ import annotations

import itertools
import json
import os
from typing import Any

import pytest

from .. import kuhn as K
from ..agents import DecisionView, NashAgent, build_agent, game_text
from ..metrics import decision_facts, game_key
from ..providers import FakeProvider

pyspiel = pytest.importorskip("pyspiel", reason="the engine tests need the openspiel extra")

SHORT_NAME = "cardlang_kuhn_poker"


@pytest.fixture(scope="module")
def game() -> Any:
    from ..referee import load_game

    return load_game(SHORT_NAME)


def _walk(state: Any, path: list[str]) -> list[tuple[tuple[str, ...], list[float]]]:
    if state.is_terminal():
        return [(tuple(path), list(state.returns()))]
    out = []
    player = state.current_player()
    for action in state.legal_actions():
        nxt = state.clone()
        name = nxt.action_to_string(player, action)
        nxt.apply_action(action)
        out.extend(_walk(nxt, path + [name]))
    return out


def _deal_seeds(game: Any) -> dict[tuple[str, str], int]:
    """One seed per deal — enough to reach every deal exactly once."""
    found: dict[tuple[str, str], int] = {}
    for seed in range(256):
        state = game.new_initial_state()
        state.apply_action(seed)
        deal = (
            K.parse(state.information_state_string(0)).card,
            K.parse(state.information_state_string(1)).card,
        )
        found.setdefault(deal, seed)
        if len(found) == len(K.DEALS):
            break
    return found


# --- the solver -------------------------------------------------------------


def test_payoff_table_matches_the_engine(game: Any) -> None:
    """Every leaf of every deal, against the engine's own `returns()`.

    This is what stops `payoff` from being a second, drifting description of the
    game. The DSL file is the description; this asserts the solver agrees with
    it at all thirty leaves.
    """
    seeds = _deal_seeds(game)
    assert len(seeds) == len(K.DEALS), f"only reached {sorted(seeds)}"
    checked = 0
    for deal, seed in seeds.items():
        state = game.new_initial_state()
        state.apply_action(seed)
        for history, returns in _walk(state, []):
            assert returns[0] == pytest.approx(K.payoff(deal, history)), (
                f"deal {deal} line {history}: engine says {returns[0]}, "
                f"the solver's table says {K.payoff(deal, history)}"
            )
            assert returns[1] == pytest.approx(-returns[0]), "Kuhn is zero-sum"
            checked += 1
    assert checked == 30, f"expected 5 lines x 6 deals; walked {checked}"


def test_the_tree_shape_matches_the_engine(game: Any) -> None:
    """`_TO_ACT` and `_OFFERED` describe the engine's tree, not a parallel one:
    the same terminal histories, the same actor at each node, the same options."""
    seeds = _deal_seeds(game)
    terminal = {h for _, seed in seeds.items() for h, _ in _walk(_state(game, seed), [])}
    assert terminal == {h for h, actor in K._TO_ACT.items() if actor is None}

    for seed in seeds.values():
        state = _state(game, seed)
        _assert_node(state, ())


def _state(game: Any, seed: int) -> Any:
    state = game.new_initial_state()
    state.apply_action(seed)
    return state


def _assert_node(state: Any, history: tuple[str, ...]) -> None:
    if state.is_terminal():
        assert K._TO_ACT[history] is None
        return
    player = state.current_player()
    assert K._TO_ACT[history] == player, f"at {history} the engine has P{player} to act"
    names = [state.action_to_string(player, a) for a in state.legal_actions()]
    assert set(names) == set(K._OFFERED[history]), (
        f"at {history} the engine offers {names}, the solver {K._OFFERED[history]}"
    )
    for action in state.legal_actions():
        nxt = state.clone()
        name = nxt.action_to_string(player, action)
        nxt.apply_action(action)
        _assert_node(nxt, history + (name,))


@pytest.mark.parametrize("alpha", [0.0, 1 / 12, 1 / 6, 0.25, 1 / 3])
def test_the_nash_family_is_unexploitable(alpha: float) -> None:
    """The equilibrium constants and the best-response code check each other.

    The constants in `nash_policy` are hand-written from the literature; the
    best response is an independent brute force over the responder's pure
    strategies. If either is wrong they disagree, and a misremembered frequency
    would otherwise shift every comparison in the experiment silently.
    """
    policy = K.nash_policy(alpha)
    for seat in (0, 1):
        assert K.exploitability(policy, seat) == pytest.approx(0.0, abs=1e-12)


def test_the_game_value_is_minus_one_eighteenth() -> None:
    """Kuhn's first player is structurally behind by exactly 1/18 of a chip."""
    assert K.game_value(K.nash_policy()) == pytest.approx(-1 / 18)
    assert K.NASH_VALUE == pytest.approx((-1 / 18, 1 / 18))


def test_the_unexploitability_check_is_not_vacuous() -> None:
    """Something must be exploitable, or the check above proves nothing.

    A `best_response` that always returned the equilibrium value would pass
    every test in this file except this one.
    """
    for seat in (0, 1):
        assert K.exploitability(K.uniform_policy(seat), seat) > 0.3
    always_fold: K.Policy = {}
    for card in K.CARDS:
        always_fold[K.infoset(0, card, ())] = {"check": 1.0, "bet": 0.0}
        always_fold[K.infoset(0, card, ("check", "bet"))] = {"fold": 1.0, "call": 0.0}
    # Folding everything to a bet concedes the whole game: a best responder bets
    # every hand and takes the ante every time it is checked to.
    assert K.exploitability(always_fold, 0) > 0.9


def test_alpha_outside_the_family_is_refused() -> None:
    for bad in (-0.01, 0.34, 1.0):
        with pytest.raises(ValueError, match="alpha"):
            K.nash_policy(bad)


def test_best_response_refuses_an_incomplete_policy() -> None:
    """A missing information set must be a loud refusal, not an implicit fill:
    which fill is used moves the exploitability number materially."""
    policy = {k: v for k, v in K.nash_policy().items() if k.startswith("P0|")}
    del policy[K.infoset(0, "K", ())]
    with pytest.raises(ValueError, match="incomplete"):
        K.best_response(policy, 0)


def test_the_noise_floor_is_positive_and_shrinks_with_sample_size() -> None:
    """Exploitability of an ESTIMATED policy is biased upward, so a perfect
    player scores above zero at any finite N. The floor must therefore be
    positive, and must fall as the sample grows — otherwise the published
    comparison has no null to sit against."""
    keys = K.infoset_keys(0)
    floors = []
    for n in (25, 200, 1600):
        visits = {k: {a: n // 2 for a in K.offered(k)} for k in keys}
        mean, p95 = K.noise_floor(visits, 0, trials=60)
        assert mean > 0.0
        assert p95 >= mean
        floors.append(mean)
    assert floors[0] > floors[1] > floors[2], f"floor did not shrink: {floors}"


# --- reading the information state ------------------------------------------


def test_parse_agrees_with_the_engine_at_every_node(game: Any) -> None:
    """`parse` recovers the acting seat, its own card and the public history at
    every decision node of every deal — checked against what the engine dealt."""
    seen = 0
    for deal, seed in _deal_seeds(game).items():
        stack: list[tuple[Any, tuple[str, ...]]] = [(_state(game, seed), ())]
        while stack:
            node, history = stack.pop()
            if node.is_terminal():
                continue
            player = node.current_player()
            info = K.parse(node.information_state_string(player))
            assert info.player == player
            assert info.card == deal[player], "a seat read the wrong card"
            assert info.history == history
            seen += 1
            for action in node.legal_actions():
                nxt = node.clone()
                name = nxt.action_to_string(player, action)
                nxt.apply_action(action)
                stack.append((nxt, history + (name,)))
    # Four decision histories — (), (check), (bet), (check, bet) — per deal,
    # derived rather than written down so the count cannot drift from the tree.
    per_deal = sum(1 for actor in K._TO_ACT.values() if actor is not None)
    assert seen == per_deal * len(K.DEALS) == 24, (
        f"expected {per_deal} decision nodes per deal; saw {seen}"
    )


def test_the_parser_never_sees_the_opponents_card(game: Any) -> None:
    """The acting seat's information state identifies exactly one card — its
    own. The opponent's hand renders as a bare count, so a leak would show up
    here as a parse failure rather than a silently richer view.

    Stated over the ENGINE's strings rather than a fixture, because the claim is
    about what the adapter emits.
    """
    for deal, seed in _deal_seeds(game).items():
        state = _state(game, seed)
        for player in (0, 1):
            raw = state.information_state_string(player)
            info = K.parse(raw)
            other = deal[1 - player]
            # The opponent's card may coincide in name only if the deal repeats
            # a rank, which Kuhn's three-card deck makes impossible.
            assert info.card == deal[player]
            assert f"hand[{1 - player}]=[{other}" not in raw


def test_render_state_says_less_than_its_input(game: Any) -> None:
    """The rendered arm is a pure function of the same string and can only ever
    say less. Every card name it prints is the seat's own."""
    for deal, seed in _deal_seeds(game).items():
        state = _state(game, seed)
        for player in (0, 1):
            english = K.render_state(state.information_state_string(player))
            assert f"Your card: {deal[player]}." in english
            for card in K.CARDS:
                if card != deal[player]:
                    assert f"Your card: {card}" not in english
            assert "You have not seen the other player's card." in english


def test_render_state_is_deterministic(game: Any) -> None:
    raw = _state(game, 0).information_state_string(0)
    assert len({K.render_state(raw) for _ in range(5)}) == 1


# --- the facts --------------------------------------------------------------


def test_dominated_actions_are_actually_dominated() -> None:
    """Derive the domination claim from the payoff table instead of restating it.

    Folding a King to a bet and calling a bet with a Jack lose chips against
    EVERY opponent strategy — that is what makes `dominated_action_rate`
    quotable without any equilibrium reference. This test enumerates the deals
    the information set is consistent with and checks the alternative is better
    in every one of them, so a wrong pair in `decision_facts` reddens here.
    """
    for card, dominated, better in (("K", "fold", "call"), ("J", "call", "fold")):
        for history in (("bet",), ("check", "bet")):
            seat = K._TO_ACT[history]
            assert seat is not None
            consistent = [d for d in K.DEALS if d[seat] == card]
            assert consistent, f"no deal gives seat {seat} a {card}"
            for deal in consistent:
                bad = K.payoff(deal, history + (dominated,))
                good = K.payoff(deal, history + (better,))
                sign = 1.0 if seat == 0 else -1.0
                assert sign * good > sign * bad, (
                    f"{dominated} with a {card} is not dominated in {deal}: "
                    f"{dominated}={sign * bad}, {better}={sign * good}"
                )


def test_decision_facts_flags_exactly_the_dominated_actions(game: Any) -> None:
    """Over every decision node of every deal and both available actions."""
    flagged: set[tuple[str, str]] = set()
    offered_count = 0
    for seed in _deal_seeds(game).values():
        stack = [_state(game, seed)]
        while stack:
            node = stack.pop()
            if node.is_terminal():
                continue
            player = node.current_player()
            raw = node.information_state_string(player)
            for action in node.legal_actions():
                name = node.action_to_string(player, action)
                facts = K.decision_facts(player, raw, name)
                if facts["dominated_offered"]:
                    offered_count += 1
                if facts["dominated"]:
                    flagged.add((facts["card"], facts["action"]))
                    assert facts["dominated_offered"], (
                        "a dominated action was flagged at a decision that "
                        "reports no dominated action on offer — the rate's "
                        "numerator would exceed its denominator"
                    )
                nxt = node.clone()
                nxt.apply_action(action)
                stack.append(nxt)
    assert flagged == {("K", "fold"), ("J", "call")}
    assert offered_count > 0


def test_facts_reach_the_transcript_through_the_referee(game: Any) -> None:
    """`decision_facts` dispatches on the game key, and the key is derived from
    the loaded game — so a Kuhn run cannot record Cheat's facts."""
    assert game_key(SHORT_NAME) == "kuhn"
    state = _state(game, 0)
    player = state.current_player()
    view = DecisionView(
        player=player,
        infostate=state.information_state_string(player),
        legal_actions=list(state.legal_actions()),
        legal_strings=[
            state.action_to_string(player, a) for a in state.legal_actions()
        ],
    )
    facts = decision_facts(view, view.legal_strings[0], "kuhn")
    assert facts["kind"] in ("open", "response")
    assert facts["card"] in K.CARDS
    with pytest.raises(ValueError, match="no metrics are defined"):
        game_key("cardlang_not_a_game")


# --- the agents -------------------------------------------------------------


def test_nash_agent_never_takes_a_dominated_action(game: Any) -> None:
    """The baseline is the ceiling, so it had better not blunder — at any seed,
    over every information set it can be placed in."""
    agent = NashAgent(seed=1)
    for seed in _deal_seeds(game).values():
        stack = [_state(game, seed)]
        while stack:
            node = stack.pop()
            if node.is_terminal():
                continue
            player = node.current_player()
            raw = node.information_state_string(player)
            legal = list(node.legal_actions())
            strings = [node.action_to_string(player, a) for a in legal]
            view = DecisionView(player, raw, legal, strings)
            for _ in range(40):
                chosen = strings[legal.index(agent.choose(view))]
                assert not K.decision_facts(player, raw, chosen)["dominated"]
            for action in legal:
                nxt = node.clone()
                nxt.apply_action(action)
                stack.append(nxt)


def test_nash_agent_plays_the_declared_frequencies(game: Any) -> None:
    """The agent samples its declared policy, at EVERY information set, over the
    engine's own action order.

    Sampled rather than asserted structurally, because the mapping from a
    policy to a draw runs through `view.legal_strings` — the engine's action
    order — and a mismatch there would swap two frequencies while every
    structural check stayed green. A mixed information set is the one that
    catches it: `P0|K|open` at the default alpha is a 50/50, so transposing the
    two actions is invisible there, which is why all twelve are checked and the
    lopsided ones (1/6, 1/3) carry the test.

    This is also what establishes that a NashAgent measuring non-zero
    exploitability over a few hundred hands is sampling noise and not a defect:
    the policy it draws from is correct to three decimal places.
    """
    agent = NashAgent(seed=5)
    declared = K.nash_policy()
    nodes: dict[str, tuple[str, list[int], list[str]]] = {}
    for seed in range(64):
        stack = [_state(game, seed)]
        while stack:
            node = stack.pop()
            if node.is_terminal():
                continue
            player = node.current_player()
            raw = node.information_state_string(player)
            legal = list(node.legal_actions())
            nodes.setdefault(
                K.parse(raw).key,
                (raw, legal, [node.action_to_string(player, a) for a in legal]),
            )
            for action in legal:
                nxt = node.clone()
                nxt.apply_action(action)
                stack.append(nxt)
    assert len(nodes) == 12, f"reached {len(nodes)} of 12 information sets"

    draws = 6000
    for key, (raw, legal, strings) in sorted(nodes.items()):
        view = DecisionView(int(key[1]), raw, legal, strings)
        counts = {a: 0 for a in strings}
        for _ in range(draws):
            counts[strings[legal.index(agent.choose(view))]] += 1
        for action in strings:
            want = declared[key].get(action, 0.0)
            got = counts[action] / draws
            # 4 standard errors of a binomial at this n, floored so the pure
            # 0/1 entries are held exactly.
            tolerance = 4.0 * (want * (1 - want) / draws) ** 0.5
            assert abs(got - want) <= tolerance, (
                f"{key} {action}: sampled {got:.4f}, declared {want:.4f}"
            )


def test_the_agent_registry_refuses_an_unknown_game() -> None:
    """A silently-ignored game name would run to completion having shown the
    model the wrong rules."""
    with pytest.raises(ValueError, match="unknown game"):
        game_text("bridge")


@pytest.mark.parametrize("render", [False, True])
def test_llm_agent_gets_kuhn_rules_for_a_kuhn_run(render: bool) -> None:
    """The rules text is a function of (game, arm) and of nothing a config can
    override — the pin `test_prompt_purity` makes for Cheat, made for Kuhn."""
    from ..agents import LLMAgent

    agent = build_agent(
        {"kind": "llm", "render": render},
        seed=0,
        provider=FakeProvider(replies=[]),
        game="kuhn",
    )
    assert isinstance(agent, LLMAgent)
    assert agent.rules == (K.RULES_RENDERED if render else K.RULES_RAW)
    assert "KUHN POKER" in agent.rules
    assert "CHEAT" not in agent.rules


def test_kuhn_prompt_carries_only_the_entitled_view(game: Any) -> None:
    """What the provider receives is `build_prompt` of the entitled arguments and
    nothing else — in particular it never names the opponent's card or the seed."""
    from ..agents import LLMAgent
    from ..prompts import RESPONSE_ARMS, build_prompt

    for deal, seed in _deal_seeds(game).items():
        state = _state(game, seed)
        player = state.current_player()
        raw = state.information_state_string(player)
        legal = list(state.legal_actions())
        strings = [state.action_to_string(player, a) for a in legal]
        provider = FakeProvider(replies=['{"action": 0, "reasoning": "x"}'])
        LLMAgent(provider=provider, seed=4242, game="kuhn").choose(
            DecisionView(player, raw, legal, strings)
        )
        assert provider.prompts == [
            build_prompt(
                K.RULES_RAW, raw, strings, RESPONSE_ARMS["reasoning"].instruction
            )
        ]
        assert "4242" not in provider.prompts[0]


# --- aggregation ------------------------------------------------------------


def _record(seats: dict[int, str], facts: list[dict[str, Any]], returns: list[float]) -> dict[str, Any]:
    return {
        "seats": {str(k): v for k, v in seats.items()},
        "terminal": True,
        "returns": returns,
        "decisions": [
            {"player": f["seat"], "facts": f, "llm": {}} for f in facts
        ],
        "usage": {},
    }


def test_aggregate_reports_a_rate_over_no_opportunities_as_null() -> None:
    """"Never did it" and "was never asked" are different claims — the rule the
    Cheat harness established, held for Kuhn's rates too."""
    facts = [K.decision_facts(0, _fake_infostate(0, "Q", ()), "check")]
    out = K.aggregate([_record({0: "a", 1: "b"}, facts, [1.0, -1.0])])
    stats = out["agents"]["a"]
    # A Queen opening offers no dominated action, so the denominator is zero.
    assert stats["dominated_offered"] == 0
    assert stats["dominated_action_rate"] is None
    assert stats["bluff_rate"] is None


def test_aggregate_records_the_deal_mix() -> None:
    """The adapter addresses 4096 seeds over SIX deals, so distinct seeds do not
    mean a uniform deal mix. Reported rather than assumed."""
    facts = [
        K.decision_facts(0, _fake_infostate(0, "J", ()), "check"),
        K.decision_facts(1, _fake_infostate(1, "K", ("check",)), "bet"),
    ]
    out = K.aggregate([_record({0: "a", 1: "b"}, facts, [-1.0, 1.0])])
    assert out["deals"] == {"JK": 1}


def test_exploitability_is_none_when_the_agent_never_acted() -> None:
    """A zero would read as "played perfectly"."""
    out = K.aggregate([_record({0: "a", 1: "b"}, [], [1.0, -1.0])])
    assert out["agents"]["b"]["exploitability"] is None
    assert out["agents"]["b"]["infoset_coverage"] is None


def _fake_infostate(seat: int, card: str, history: tuple[str, ...]) -> str:
    """A minimal information state in the adapter's format, for aggregation
    tests that must not need the engine."""
    hands = ";".join(
        f"hand[{p}]=[{card}♠]" if p == seat else f"hand[{p}]=#1" for p in (0, 1)
    )
    obs = ";".join(
        f"('announce', {i % 2}, '{a}')" for i, a in enumerate(history)
    )
    return f"P{seat}|deck=#1;{hands}|state:x=0|obs:{obs}"


def test_the_fake_infostate_matches_the_engines(game: Any) -> None:
    """The fixture above is only usable if it parses to the same thing the
    engine's own string does. Without this, the aggregation tests could be
    exercising a format nothing produces."""
    for seed in _deal_seeds(game).values():
        state = _state(game, seed)
        player = state.current_player()
        real = K.parse(state.information_state_string(player))
        fake = K.parse(_fake_infostate(real.player, real.card, real.history))
        assert fake == real


def test_policy_fill_is_a_stated_choice_that_moves_the_number() -> None:
    """Uniform and Nash fills give different exploitability, which is why both
    are reported. A test asserting they agree would be asserting the fill does
    not matter — and then reporting two numbers would be noise."""
    stats = K.KuhnStats(agent="a")
    stats.observe(K.decision_facts(0, _fake_infostate(0, "K", ()), "bet"))
    assert stats.infoset_coverage() == pytest.approx(1 / 6)
    uniform = stats.exploitability(fill_with_nash=False)
    nash = stats.exploitability(fill_with_nash=True)
    assert uniform is not None and nash is not None
    assert uniform > nash, "the uniform fill should charge for what was not measured"


def test_dominated_action_rate_is_one_for_a_player_that_always_blunders() -> None:
    """The metric's top end, so a rate that could only ever read low is caught."""
    facts = [
        K.decision_facts(0, _fake_infostate(0, "K", ("check", "bet")), "fold"),
        K.decision_facts(1, _fake_infostate(1, "J", ("bet",)), "call"),
    ]
    out = K.aggregate([_record({0: "a", 1: "a"}, facts, [-1.0, 1.0])])
    assert out["agents"]["a"]["dominated_action_rate"] == pytest.approx(1.0)


def test_every_infoset_key_is_reachable_and_offered_two_actions() -> None:
    """The key space is closed: twelve information sets, each with exactly the
    two actions the tree offers there, and no key that `offered` cannot read."""
    keys = [k for seat in (0, 1) for k in K.infoset_keys(seat)]
    assert len(keys) == 12 == len(set(keys))
    for key in keys:
        assert len(set(K.offered(key))) == 2
    assert set(K.nash_policy()) == set(keys)
    for seat in (0, 1):
        assert set(K.uniform_policy(seat)) == set(K.infoset_keys(seat))


def test_a_bluff_is_a_bet_and_never_a_dominated_call() -> None:
    """The two metric families are disjoint.

    Calling a bet with a Jack is a dominated action, not a bluff. Counting it as
    both reported a blunder as deception AND made the rate move with the
    opponent: the identical policy scored one number against one opponent and a
    different one against another, purely because they put it in front of a bet
    at different rates. Pinned as disjointness, which is the property that fails
    if the definitions ever drift back together.
    """
    for card in K.CARDS:
        for history in ((), ("check",), ("bet",), ("check", "bet")):
            for action in K._OFFERED[history]:
                flags = K.classify(card, history, action)
                assert not (flags["bluff"] and flags["dominated"])
                assert not (flags["bluff_offered"] and flags["dominated_offered"])
                if flags["bluff"]:
                    assert action == "bet" and card == "J"


def test_the_bluff_rate_does_not_move_with_the_opponent() -> None:
    """The regression this metric actually had.

    The SAME policy must score the same bluff rate whoever it faces. The broken
    definition pooled facing-a-bet decisions into the denominator, so an
    opponent that bet more changed the number without the policy changing at
    all. Simulated here by aggregating one fixed set of decisions twice, once
    with extra facing-a-bet decisions appended.
    """
    base = [
        K.decision_facts(0, _fake_infostate(0, "J", ()), "bet"),
        K.decision_facts(0, _fake_infostate(0, "J", ()), "check"),
    ]
    facing = [
        K.decision_facts(0, _fake_infostate(0, "J", ("check", "bet")), "fold"),
        K.decision_facts(0, _fake_infostate(0, "J", ("check", "bet")), "fold"),
        K.decision_facts(0, _fake_infostate(0, "J", ("check", "bet")), "fold"),
    ]
    quiet = K.aggregate([_record({0: "a", 1: "b"}, base, [1.0, -1.0])])
    noisy = K.aggregate([_record({0: "a", 1: "b"}, base + facing, [1.0, -1.0])])
    assert quiet["agents"]["a"]["bluff_rate"] == pytest.approx(0.5)
    assert noisy["agents"]["a"]["bluff_rate"] == pytest.approx(0.5)


def test_the_named_frequencies_read_the_equilibrium_targets() -> None:
    """`bluff_rate_first_to_act` and friends are per-information-set, so they
    have exact Nash targets and nothing outside the agent's own policy can move
    them. Checked against a policy built to hit them."""
    stats = K.KuhnStats(agent="a")
    for _ in range(3):
        stats.observe(K.decision_facts(0, _fake_infostate(0, "J", ()), "check"))
    stats.observe(K.decision_facts(0, _fake_infostate(0, "J", ()), "bet"))
    assert stats.rates()["bluff_rate_first_to_act"] == pytest.approx(0.25)
    # Never in the other three, so each is null rather than zero.
    for key in (
        "bluff_rate_after_a_check",
        "folds_the_best_hand_rate",
        "calls_with_the_worst_hand_rate",
    ):
        assert stats.rates()[key] is None

    blunder = K.KuhnStats(agent="b")
    blunder.observe(K.decision_facts(1, _fake_infostate(1, "K", ("bet",)), "fold"))
    assert blunder.rates()["folds_the_best_hand_rate"] == pytest.approx(1.0)


def test_balanced_seating_cancels_the_card_advantage(game: Any) -> None:
    """The confound that made a model "beat" a provably unbeatable opponent.

    Under the original scheme the seed and the focus seat are the same number,
    so which seat an agent takes is a function of which deal was drawn — and the
    adapter's seed-to-deal map is not balanced across seed parities. A real
    300-game run had the model holding a King 112 times to the baseline's 97,
    and reporting +0.09 chips per hand against an exact equilibrium.

    Balanced seating plays every deal in every seating, so the advantage cancels
    by construction. Asserted as an EXACT tie in total card rank, because
    "cancels by construction" is a stronger claim than "averages out", and only
    the exact form would catch the scheme silently reverting.
    """
    from ..run_eval import seat_plan

    rank = {c: i for i, c in enumerate(K.CARDS)}

    def advantage(balanced: bool, games: int) -> tuple[int, int]:
        held = [0, 0]
        for index in range(games):
            offset, focus = seat_plan(index, 2, rotate=True, balanced=balanced)
            state = _state(game, offset)
            cards = [K.parse(state.information_state_string(s)).card for s in (0, 1)]
            # The roster's first entry sits at `focus`; the second takes the rest.
            held[0] += rank[cards[focus]]
            held[1] += rank[cards[1 - focus]]
        return held[0], held[1]

    first, second = advantage(balanced=True, games=300)
    assert first == second, (
        f"balanced seating still favours a roster position: {first} vs {second}"
    )

    # And the check is not vacuous: the original scheme really is skewed on the
    # same seeds, which is what makes the fix necessary rather than cosmetic.
    skew_first, skew_second = advantage(balanced=False, games=300)
    assert skew_first != skew_second, (
        "the unbalanced scheme came out even on these seeds, so this test "
        "cannot tell the two schemes apart and proves nothing"
    )


def test_balanced_seating_covers_each_deal_in_every_seating() -> None:
    """`n` games cover `n / num_players` deals, each played in every seating."""
    from ..run_eval import seat_plan

    plans = [seat_plan(i, 2, rotate=True, balanced=True) for i in range(8)]
    assert plans == [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)]
    # Unbalanced keeps the original mapping exactly, so Cheat's committed
    # archive stays comparable with anything measured after this change.
    assert [seat_plan(i, 4, rotate=True, balanced=False) for i in range(5)] == [
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 0),
    ]
    # `rotate: false` pins the roster to its seats under either scheme.
    assert [seat_plan(i, 2, rotate=False, balanced=True) for i in range(3)] == [
        (0, 0),
        (1, 0),
        (2, 0),
    ]


def test_an_unreachable_infoset_cannot_move_exploitability() -> None:
    """The reason partial coverage does not always invalidate the number.

    An information set the agent never visited BECAUSE its own earlier choices
    never lead there is unreachable for a best responder too, so whatever is
    filled in there contributes zero. A policy that always bets its King never
    reaches "checked with a King and got bet at" — and the two fills must
    therefore agree exactly, which is what `exploitability_fill_sensitivity`
    reports.

    Contrast with a MIXING policy, where the unvisited set is genuinely
    reachable and the fill moves the number a lot. Both halves are asserted, so
    the metric cannot degenerate into always reporting zero.
    """
    def build(opening: dict[str, str], responses: dict[str, str]) -> K.KuhnStats:
        stats = K.KuhnStats(agent="a")
        for card, action in opening.items():
            for _ in range(20):
                stats.observe(K.decision_facts(0, _fake_infostate(0, card, ()), action))
        for card, action in responses.items():
            for _ in range(20):
                stats.observe(
                    K.decision_facts(
                        0, _fake_infostate(0, card, ("check", "bet")), action
                    )
                )
        return stats

    # Always bets the King, so P0|K|check-bet is the ONE unvisited set and it is
    # unreachable: no line of play puts this policy there.
    deterministic = build(
        {"J": "check", "Q": "check", "K": "bet"}, {"J": "fold", "Q": "call"}
    )
    unreachable = K.infoset(0, "K", ("check", "bet"))
    assert not deterministic.visits.get(unreachable)
    coverage = deterministic.infoset_coverage()
    assert coverage is not None and coverage == pytest.approx(5 / 6)
    assert deterministic.rates()["exploitability_fill_sensitivity"] == pytest.approx(0.0)

    # Same unvisited set, but this policy sometimes CHECKS its King — so the set
    # is genuinely reachable, and what happens there is load-bearing.
    mixing = build({"J": "check", "Q": "check"}, {"J": "fold", "Q": "call"})
    for _ in range(10):
        mixing.observe(K.decision_facts(0, _fake_infostate(0, "K", ()), "check"))
        mixing.observe(K.decision_facts(0, _fake_infostate(0, "K", ()), "bet"))
    assert not mixing.visits.get(unreachable)
    assert mixing.infoset_coverage() == pytest.approx(5 / 6)
    sensitivity = mixing.rates()["exploitability_fill_sensitivity"]
    assert sensitivity is not None and sensitivity > 0.0, (
        "a reachable unvisited information set must show the fill mattering, or "
        "the sensitivity metric reports zero for everything and means nothing"
    )


def test_kuhn_has_no_pure_equilibrium_and_the_bound_says_what_that_costs() -> None:
    """The benchmark a deterministic player must be read against.

    Every Kuhn optimum bluffs a Jack and calls a Queen at a frequency strictly
    between 0 and 1, so no pure strategy is unexploitable. `best_pure_
    exploitability` is the exact floor on that, and it must be strictly positive
    — if it were zero the whole "determinism is what costs them" reading would
    be unsupported.
    """
    for seat in (0, 1):
        bound = K.best_pure_exploitability(seat)
        assert bound > 0.0, "a pure strategy reached equilibrium — no it did not"
        # And it really is a MINIMUM over the pure strategies, not one of them.
        keys = K.infoset_keys(seat)
        for choices in itertools.product(*(K.offered(k) for k in keys)):
            policy = {
                k: {a: (1.0 if a == c else 0.0) for a in K.offered(k)}
                for k, c in zip(keys, choices, strict=True)
            }
            assert K.exploitability(policy, seat) >= bound - 1e-12
    assert K.best_pure_exploitability(0) == pytest.approx(1 / 9)
    assert K.best_pure_exploitability(1) == pytest.approx(2 / 9)
    # A mixed policy CAN do better — otherwise the bound would not be a bound on
    # determinism specifically, just on play.
    assert K.exploitability(K.nash_policy(), 0) < K.best_pure_exploitability(0)


def test_purity_is_judged_on_visited_infosets_only() -> None:
    """An unvisited information set carries the uniform fill, which is mixed.
    Counting it would report every partially-covered agent as randomising when
    the property being claimed is about decisions it actually made."""
    stats = K.KuhnStats(agent="a")
    for _ in range(5):
        stats.observe(K.decision_facts(0, _fake_infostate(0, "K", ()), "bet"))
    assert stats.infoset_coverage() == pytest.approx(1 / 6)
    assert stats.rates()["policy_is_pure"] is True

    stats.observe(K.decision_facts(0, _fake_infostate(0, "J", ()), "bet"))
    stats.observe(K.decision_facts(0, _fake_infostate(0, "J", ()), "check"))
    assert stats.rates()["policy_is_pure"] is False


def test_pairing_keeps_every_game_under_balanced_seating(tmp_path: Any) -> None:
    """The A/B's experimental unit is (deal, seat), not the deal alone.

    Balanced seating plays each seed once per seating, so keying the paired
    analysis on the seed silently keeps whichever game came last — half the run,
    and always the same seating, so the survivors are not a random half. Measured
    before this was keyed properly: 150 of 300 games dropped, every survivor with
    the model at seat 1.

    This is the repo's named silent-cap defect: coverage bounded with nothing
    saying what was dropped. The fix refuses rather than truncates.
    """
    from ..verify_kuhn import compare_arms

    def write(path: Any, actions: dict[tuple[int, int], str]) -> str:
        lines = []
        for (seed, llm_seat), action in actions.items():
            facts = K.decision_facts(
                llm_seat, _fake_infostate(llm_seat, "J", ("bet",)), action
            )
            lines.append(
                json.dumps(
                    {
                        "seed": seed,
                        "seats": {
                            str(llm_seat): "llm_x",
                            str(1 - llm_seat): "nash",
                        },
                        "terminal": True,
                        "returns": [0.0, 0.0],
                        "decisions": [
                            {"player": llm_seat, "facts": facts, "llm": {}}
                        ],
                        "usage": {},
                    }
                )
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    # Two seeds, each played in both seatings. The model blunders at seat 0 only,
    # which is precisely what a seed-keyed pairing would have thrown away.
    control = write(
        tmp_path / "c.jsonl",
        {(0, 0): "call", (0, 1): "fold", (1, 0): "call", (1, 1): "fold"},
    )
    arm = write(
        tmp_path / "a.jsonl",
        {(0, 0): "fold", (0, 1): "fold", (1, 0): "fold", (1, 1): "fold"},
    )
    out = compare_arms(control, arm)
    assert out["units_shared"] == 4, "a game was dropped from the paired analysis"
    assert out["games_control"] == 4 and out["games_arm"] == 4
    assert out["control"]["taken"] == 2, (
        "the seat-0 blunders vanished — the pairing is keyed on the seed alone"
    )
    assert out["paired_sign_test"]["down"] == 2


def test_pairing_refuses_a_transcript_with_repeated_units() -> None:
    """If two games ever share a (seed, seat) the pairing would drop one, so it
    raises instead. A silent drop is the failure this whole unit exists to
    prevent, and it must not be reintroduced by a config nobody anticipated."""
    from ..verify_kuhn import compare_arms
    import tempfile

    record = {
        "seed": 0,
        "seats": {"0": "llm_x", "1": "nash"},
        "terminal": True,
        "returns": [0.0, 0.0],
        "decisions": [],
        "usage": {},
    }
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "dupe.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
            handle.write(json.dumps(record) + "\n")
        with pytest.raises(ValueError, match="repeated"):
            compare_arms(path, path)


def test_the_deal_space_is_the_six_kuhn_deals() -> None:
    assert len(K.DEALS) == 6
    assert all(a != b for a, b in K.DEALS)
    assert {c for deal in K.DEALS for c in deal} == set(K.CARDS)
    assert sorted(K.DEALS) == sorted(
        (a, b) for a, b in itertools.permutations(K.CARDS, 2)
    )
