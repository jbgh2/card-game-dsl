"""The agents. Every one of them decides from a `DecisionView` of strings.

`DecisionView` is the enforcement mechanism for the leak-freeness invariant
(BUILDLOG, "Leak-freeness"): it carries the acting player's information-state string and the
rendered legal actions, and nothing else. No agent — LLM or baseline — holds a
reference to a `pyspiel.State` or a `RuntimeState`, so none of them *can* read
hidden information, whatever their policy does.

That is stronger than the spec's `choose(state)`, and deliberately so: it puts
the baselines under the same guarantee as the model, which is what makes a
head-to-head number meaningful.

Contract
--------
Assumes: `view.legal_actions` and `view.legal_strings` are index-aligned, in the
engine's own order.
Establishes: an action id drawn from `view.legal_actions`.
Illegal after: an agent method taking a game state.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import holdem, infostate as istate
from . import kuhn
from .prompts import (
    ResponseArm,
    RULES_RAW,
    RULES_RENDERED,
    build_prompt,
    parse_response,
    response_arm,
)
from .render import render_state
from .providers import Provider


@dataclass(frozen=True)
class DecisionView:
    """Everything an agent is allowed to see at one decision point.

    Game-neutral by construction: seat number, information-state string, and the
    legal actions with their renderings. Nothing here knows which game is being
    played, which is what lets the leak-freeness guarantee cover a second one
    without being restated. Cheat's decision-shape classifier lives in
    `infostate.decision_kind`, not here.
    """

    player: int
    infostate: str
    legal_actions: list[int]
    legal_strings: list[str]


# The per-game static text a decision reads. Two entries, so the structure that
# keeps them apart is exercised rather than asserted: an agent's rules text is a
# function of (game, arm) and of nothing a run can configure, which is what makes
# two arms' numbers comparable and two GAMES' numbers not silently mixed.
#
# `render` is the arm that hands the model English instead of the engine's raw
# string. Both entries' renderers are pure functions of the same information
# state, so the leak-freeness argument is per-game unchanged.
GAME_TEXT: dict[str, tuple[str, str, Callable[[str], str]]] = {
    # game: (rules for the raw arm, rules for the rendered arm, renderer)
    "cheat": (RULES_RAW, RULES_RENDERED, render_state),
    "kuhn": (kuhn.RULES_RAW, kuhn.RULES_RENDERED, kuhn.render_state),
    # Heads-up Hold'em has no rendered arm: that arm exists to ask whether
    # English helps comprehension, which was answered on Cheat and is not
    # re-asked here. The raw text stands in both slots rather than `None`, so
    # `render: true` reads the same state it would anyway instead of failing
    # a run mid-flight; the config never sets it.
    "holdem_hu": (holdem.RULES_RAW, holdem.RULES_RAW, lambda s: s),
}


def game_text(name: str) -> tuple[str, str, Callable[[str], str]]:
    """Look up a game's static text, refusing anything not in the registry.

    A silently-ignored game name would be this harness's worst failure: the run
    would complete, cost real money, and report one game's numbers having shown
    the model another game's rules.
    """
    try:
        return GAME_TEXT[name]
    except KeyError:
        raise ValueError(
            f"unknown game {name!r} (expected one of {sorted(GAME_TEXT)})"
        ) from None


class Agent(Protocol):
    name: str

    def choose(self, view: DecisionView) -> int: ...

    def pop_trace(self) -> dict[str, Any]:
        """Agent-specific detail about the decision just made, for the
        transcript. Empty for agents with nothing to add."""
        ...


@dataclass
class RandomAgent:
    """Uniform over legal actions. The floor."""

    seed: int
    name: str = "random"
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: DecisionView) -> int:
        return self._rng.choice(view.legal_actions)

    def pop_trace(self) -> dict[str, Any]:
        return {}


@dataclass
class RuleAgent:
    """A competent non-learning baseline, decided entirely from the info state.

    Play policy: announce the largest count you can back TRUTHFULLY (which also
    sheds fastest, and goes out when the whole hand matches), and lie with a
    single card when the cycle leaves you no truthful play. When choosing which
    cards to put down, play the claimed rank if you hold it, otherwise dump the
    rank you hold fewest of — singletons are the least useful cards to keep.

    Challenge policy: call "Cheat!" whenever the claim is *provably* false from
    your own hand (`infostate.provably_false`), plus a fixed independent chance
    otherwise. The random component is not noise for its own sake: a pure
    provable-only challenger never punishes an ordinary bluff, so an opponent
    that always lies would never be caught and the baseline would be trivially
    exploitable. `challenge_prob` is recorded in every run's summary.
    """

    seed: int
    challenge_prob: float = 0.1
    # Probability of ELECTING to over-claim when a truthful play was available.
    # 0.0 (the default) is the truthful-when-possible policy the baseline shipped
    # with. Raising it makes the opponent a tunable source of detectable lies:
    # see `BUILDLOG.md`, "Choosing an opponent", for why neither an all-truthful
    # nor an all-random table lets challenge precision and provable-lie volume
    # be measured at the same time.
    bluff_prob: float = 0.0
    name: str = "rule"
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: DecisionView) -> int:
        info = istate.parse(view.infostate)
        kind = istate.decision_kind(view.legal_strings)
        if kind == "window":
            return self._challenge(view, info)
        if kind == "announce":
            return self._announce(view, info)
        if kind == "count":
            return self._count(view, info)
        return self._card(view, info)

    def _challenge(self, view: DecisionView, info: istate.Info) -> int:
        provable = istate.provably_false(info, info.claim_rank, info.claim_count)
        call = provable or self._rng.random() < self.challenge_prob
        return view.legal_actions[view.legal_strings.index("call_cheat" if call else "allow")]

    def _announce(self, view: DecisionView, info: istate.Info) -> int:
        # Opening a play is forced — `play_cards` is the only legal action, and
        # the size of the play is the next decision. Kept as its own branch so
        # that a second play-opening move would surface here rather than fall
        # through to the card policy.
        return view.legal_actions[0]

    def _count(self, view: DecisionView, info: istate.Info) -> int:
        """How many cards to claim — the public half of the claim, and so
        where this agent's bluff lives."""
        truthful = info.count_of_rank(info.claim_rank)
        counts = [int(s) for s in view.legal_strings]
        if truthful and self._rng.random() < self.bluff_prob:
            # Over-claim by the SMALLEST margin that is still a lie: the card
            # policy below plays every truthful card first and pads with junk,
            # so claiming one more than we hold yields a minimally-implausible
            # bluff rather than an obvious dump.
            over = [n for n in counts if n > truthful]
            if over:
                return view.legal_actions[view.legal_strings.index(str(min(over)))]
        # The largest count we can back truthfully; 1 when we hold none of the
        # claimed rank (a count of 1 is always legal, so this never falls
        # through).
        best = max((n for n in counts if n <= truthful), default=1)
        return view.legal_actions[view.legal_strings.index(str(best))]

    def _card(self, view: DecisionView, info: istate.Info) -> int:
        want = info.claim_rank
        pool = view.legal_strings
        truthful = [c for c in pool if istate.rank_of(c) == want]
        if truthful:
            pick = truthful[0]
        else:
            held: dict[str, int] = {}
            for c in pool:
                held[istate.rank_of(c)] = held.get(istate.rank_of(c), 0) + 1
            # Fewest copies first, then lowest rank in the cycle — a total order,
            # so the policy is deterministic given the seed.
            pick = min(pool, key=lambda c: (held[istate.rank_of(c)], istate.RANKS.index(istate.rank_of(c)), c))
        return view.legal_actions[pool.index(pick)]

    def pop_trace(self) -> dict[str, Any]:
        return {}


@dataclass
class NashAgent:
    """Kuhn's exact equilibrium — the baseline the Cheat harness could not have.

    Cheat has no solution, so its baseline was a hand-written heuristic and
    "beat the baseline" meant "beat somebody's guess at competent play". Kuhn is
    solved, so the baseline is the game-theoretic optimum: it is unexploitable by
    construction, it concedes exactly 1/18 of a chip per hand as seat 0, and no
    policy can do better against it. A model measured against this is measured
    against the ceiling, not against a person's idea of one.

    `alpha` selects a member of the equilibrium family. Every member is
    unexploitable and every member has the same value, so this is a free choice
    among optima — it is recorded in the run summary because it changes the
    opponent's observable BEHAVIOUR (how often it bluffs a Jack) without
    changing its strength, and the model's best response to it therefore
    differs.

    Decides from the `DecisionView` like every other agent: it reads the
    information state, not the state.
    """

    seed: int
    alpha: float = 1.0 / 6.0
    name: str = "nash"
    _rng: random.Random = field(init=False)
    _policy: kuhn.Policy = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        # Resolve at construction: an out-of-range alpha must fail before a run
        # starts, not on move one after the roster is already up.
        self._policy = kuhn.nash_policy(self.alpha)

    def choose(self, view: DecisionView) -> int:
        info = kuhn.parse(view.infostate)
        dist = self._policy[info.key]
        # Sample over the ENGINE's own action order, so the draw does not depend
        # on dictionary ordering anywhere in this file.
        roll = self._rng.random()
        cumulative = 0.0
        for index, action in enumerate(view.legal_strings):
            cumulative += dist.get(action, 0.0)
            if roll < cumulative:
                return view.legal_actions[index]
        return view.legal_actions[-1]

    def pop_trace(self) -> dict[str, Any]:
        return {}


@dataclass
class LLMAgent:
    """A frontier model, reading the raw information state.

    Failure policy (spec §3): one retry with the parse error appended, then a
    uniform-random fallback, logged loudly. The fallback rate is reported as a
    first-class metric — above roughly 2% of moves the result is not
    publishable, and the fix is the prompt, not a quieter log.
    """

    provider: Provider
    seed: int
    name: str = "llm"
    # The experimental arm. False: the engine's raw information-state string.
    # True: `render.render_state` of it — still a pure function of the same
    # string, so the leak-freeness argument is unchanged (BUILDLOG, "Leak-
    # freeness"), with a correspondingly shorter format guide.
    render: bool = False
    # The RESPONSE-FORMAT arm, by name from `prompts.RESPONSE_ARMS`. Selects the
    # answer instruction and its matching retry note together. A name rather
    # than a flag per arm: `neutral` and `reason_first` are mutually exclusive
    # (one removes the reasoning field, the other moves it), and as two booleans
    # their both-true combination would be accepted and silently resolved.
    arm: str = "reasoning"
    # Which game's rules text and renderer to use. A name from `GAME_TEXT`, so an
    # unrecognized game is refused rather than silently defaulting to Cheat's
    # rules — which would produce a complete, expensive, entirely meaningless run.
    game: str = "cheat"
    # DERIVED from `game` and `render`, never constructor parameters: the two
    # arms' rules texts differ only in their format guide, so a caller-supplied
    # third text would make the two arms' numbers incomparable — and no config
    # path ever supplied one.
    rules: str = field(init=False)
    _render: Callable[[str], str] = field(init=False)
    _rng: random.Random = field(init=False)
    _arm: ResponseArm = field(init=False)
    _trace: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        raw, rendered, renderer = game_text(self.game)
        self.rules = rendered if self.render else raw
        self._render = renderer
        # Resolve at construction, not at the first decision: an unknown arm
        # name must fail before a run starts spending, not on move one of game
        # one after the roster and providers are already up.
        self._arm = response_arm(self.arm)

    def choose(self, view: DecisionView) -> int:
        if len(view.legal_actions) == 1:
            # A FORCED decision: there is nothing to choose. Asking anyway
            # spends a billed call (two, when the first reply needs a retry),
            # and lands in `llm_calls_per_game` and `fallback_rate` as though a
            # choice had been made — inflating the cost of a run and diluting
            # the very rates that decide whether it is publishable. Cheat opens
            # every play with one of these: the `play_cards` announce, whose
            # actual content is the count decision that follows it.
            #
            # An EMPTY trace, like the non-LLM agents': a trace is what makes a
            # decision count as this agent's in the transcript, so recording one
            # here would put forced moves back into `llm_decisions` and
            # `llm_calls_per_game` — the same distortion, one field along. That
            # the move was forced stays derivable from its own record, whose
            # legal-action list has exactly one entry.
            self._trace = {}
            return view.legal_actions[0]
        state = self._render(view.infostate) if self.render else view.infostate
        prompt = build_prompt(
            self.rules, state, view.legal_strings, self._arm.instruction
        )
        attempts: list[dict[str, Any]] = []
        text = prompt
        for attempt in range(2):
            reply = self.provider.complete(text)
            result = parse_response(reply.text, len(view.legal_actions))
            attempts.append(
                {
                    "attempt": attempt,
                    "response": reply.text,
                    "stop_reason": reply.stop_reason,
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "error": result.error,
                    "reasoning": result.reasoning,
                }
            )
            if result.index is not None:
                self._trace = {
                    "prompt": prompt,
                    "arm": self._arm.name,
                    "attempts": attempts,
                    "fallback": False,
                    "chosen_index": result.index,
                    "reasoning": result.reasoning,
                }
                return view.legal_actions[result.index]
            text = prompt + self._arm.retry.format(error=result.error)

        action = self._rng.choice(view.legal_actions)
        print(
            f"[llm_eval] FALLBACK: P{view.player} — {attempts[-1]['error']} "
            f"after 2 attempts; playing uniformly at random"
        )
        self._trace = {
            "prompt": prompt,
            "arm": self._arm.name,
            "attempts": attempts,
            "fallback": True,
            "chosen_index": view.legal_actions.index(action),
            "reasoning": "",
        }
        return action

    def pop_trace(self) -> dict[str, Any]:
        trace, self._trace = self._trace, {}
        return trace


def build_agent(
    spec: dict[str, Any], seed: int, provider: Provider | None, game: str = "cheat"
) -> Agent:
    """Construct one agent from a config block."""
    kind = spec["kind"]
    if kind == "random":
        return RandomAgent(seed=seed, name=spec.get("name", "random"))
    if kind == "rule":
        # The baseline is the one agent kind that cannot be game-generic: it
        # plays. Cheat's is a lie/challenge heuristic, Hold'em's a
        # tight-aggressive band policy; Kuhn's baseline is `nash`, exact.
        if game == "holdem_hu":
            return holdem.build_rule_agent(spec, seed)
        return RuleAgent(
            seed=seed,
            challenge_prob=float(spec.get("challenge_prob", 0.1)),
            bluff_prob=float(spec.get("bluff_prob", 0.0)),
            name=spec.get("name", "rule"),
        )
    if kind == "nash":
        return NashAgent(
            seed=seed,
            alpha=float(spec.get("alpha", 1.0 / 6.0)),
            name=spec.get("name", "nash"),
        )
    if kind == "llm":
        if provider is None:
            raise ValueError("an 'llm' agent needs a provider")
        return LLMAgent(
            provider=provider,
            seed=seed,
            name=spec.get("name", "llm"),
            render=bool(spec.get("render", False)),
            arm=str(spec.get("arm", "reasoning")),
            game=game,
        )
    raise ValueError(
        f"unknown agent kind {kind!r} (expected random | rule | nash | llm)"
    )


def seat_agents(agents: Sequence[Agent]) -> dict[int, Agent]:
    return dict(enumerate(agents))
