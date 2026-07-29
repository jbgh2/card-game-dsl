"""The agents. Every one of them decides from a `DecisionView` of strings.

`DecisionView` is the enforcement mechanism for the leak-freeness invariant
(README): it carries the acting player's information-state string and the
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
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import infostate as istate
from .prompts import (
    RESPONSE_NEUTRAL,
    RESPONSE_TEXT,
    RETRY_NOTE,
    RULES_RAW,
    RULES_RENDERED,
    build_prompt,
    parse_response,
)
from .render import render_state
from .providers import Provider


@dataclass(frozen=True)
class DecisionView:
    """Everything an agent is allowed to see at one decision point."""

    player: int
    infostate: str
    legal_actions: list[int]
    legal_strings: list[str]

    def kind(self) -> str:
        """Which of Cheat's three decision shapes this is, from the legal moves
        alone. Raises on anything else rather than guessing: a new decision
        shape must be handled deliberately, not silently routed to the card
        branch."""
        if self.legal_strings == ["allow", "call_cheat"]:
            return "window"
        if all(s.startswith("play_") for s in self.legal_strings):
            return "announce"
        if all(istate.rank_of(s) in istate.RANKS for s in self.legal_strings):
            return "card"
        raise ValueError(f"unrecognized decision shape: {self.legal_strings}")


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
    # see `README.md`, "Choosing an opponent", for why neither an all-truthful
    # nor an all-random table lets challenge precision and provable-lie volume
    # be measured at the same time.
    bluff_prob: float = 0.0
    name: str = "rule"
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: DecisionView) -> int:
        info = istate.parse(view.infostate)
        kind = view.kind()
        if kind == "window":
            return self._challenge(view, info)
        if kind == "announce":
            return self._announce(view, info)
        return self._card(view, info)

    def _challenge(self, view: DecisionView, info: istate.Info) -> int:
        provable = istate.provably_false(info, info.claim_rank, info.claim_count)
        call = provable or self._rng.random() < self.challenge_prob
        return view.legal_actions[view.legal_strings.index("call_cheat" if call else "allow")]

    def _announce(self, view: DecisionView, info: istate.Info) -> int:
        truthful = info.count_of_rank(info.claim_rank)
        counts = {"play_one": 1, "play_two": 2, "play_three": 3, "play_four": 4}
        # The largest legal announce we can back truthfully; `play_one` when we
        # hold none of the claimed rank (it is always legal, so this never
        # falls through).
        legal = {nm: n for nm, n in counts.items() if nm in view.legal_strings}
        if truthful and self._rng.random() < self.bluff_prob:
            # Over-claim by the SMALLEST margin that is still a lie: the card
            # policy below plays every truthful card first and pads with junk,
            # so announcing one more than we hold yields a minimally-implausible
            # bluff rather than an obvious four-card dump.
            over = sorted(nm for nm, n in legal.items() if n > truthful)
            if over:
                pick = min(over, key=lambda nm: counts[nm])
                return view.legal_actions[view.legal_strings.index(pick)]
        best = "play_one"
        for name, n in legal.items():
            if n <= truthful and n > counts[best]:
                best = name
        return view.legal_actions[view.legal_strings.index(best)]

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
    # string, so the leak-freeness argument is unchanged (README, "Leak-
    # freeness"), with a correspondingly shorter format guide.
    render: bool = False
    # The NEUTRAL arm: ask for the action alone, with no justification. Tests
    # whether requiring a justification biases the model toward acting. Costs
    # the reasoning diagnostics, which is why it is an arm and not the default
    # (`prompts.RESPONSE_NEUTRAL`).
    neutral: bool = False
    rules: str | None = None
    _rng: random.Random = field(init=False)
    _trace: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if self.rules is None:
            self.rules = RULES_RENDERED if self.render else RULES_RAW

    def choose(self, view: DecisionView) -> int:
        state = render_state(view.infostate) if self.render else view.infostate
        assert self.rules is not None  # set in __post_init__
        response = RESPONSE_NEUTRAL if self.neutral else RESPONSE_TEXT
        prompt = build_prompt(self.rules, state, view.legal_strings, response)
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
                    "attempts": attempts,
                    "fallback": False,
                    "chosen_index": result.index,
                    "reasoning": result.reasoning,
                }
                return view.legal_actions[result.index]
            text = prompt + RETRY_NOTE.format(error=result.error)

        action = self._rng.choice(view.legal_actions)
        print(
            f"[llm_eval] FALLBACK: P{view.player} — {attempts[-1]['error']} "
            f"after 2 attempts; playing uniformly at random"
        )
        self._trace = {
            "prompt": prompt,
            "attempts": attempts,
            "fallback": True,
            "chosen_index": view.legal_actions.index(action),
            "reasoning": "",
        }
        return action

    def pop_trace(self) -> dict[str, Any]:
        trace, self._trace = self._trace, {}
        return trace


def build_agent(spec: dict[str, Any], seed: int, provider: Provider | None) -> Agent:
    """Construct one agent from a config block."""
    kind = spec["kind"]
    if kind == "random":
        return RandomAgent(seed=seed, name=spec.get("name", "random"))
    if kind == "rule":
        return RuleAgent(
            seed=seed,
            challenge_prob=float(spec.get("challenge_prob", 0.1)),
            bluff_prob=float(spec.get("bluff_prob", 0.0)),
            name=spec.get("name", "rule"),
        )
    if kind == "llm":
        if provider is None:
            raise ValueError("an 'llm' agent needs a provider")
        return LLMAgent(
            provider=provider,
            seed=seed,
            name=spec.get("name", "llm"),
            render=bool(spec.get("render", False)),
            neutral=bool(spec.get("neutral", False)),
        )
    raise ValueError(f"unknown agent kind {kind!r} (expected random | rule | llm)")


def seat_agents(agents: Sequence[Agent]) -> dict[int, Agent]:
    return dict(enumerate(agents))
