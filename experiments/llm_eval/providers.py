"""Model-API abstraction: one method, plus usage accounting.

Two implementations. `AnthropicProvider` is the real one; `FakeProvider` serves
canned replies and is the only provider the unit tests use — there is no
network in tests.

Contract
--------
Assumes: `ANTHROPIC_API_KEY` (or an `ant auth login` profile) is present before
`AnthropicProvider.complete` is called; nothing is read from the environment at
import time.
Establishes: a `Reply` carrying the text and the exact token counts billed, and
a running `Usage` total per provider instance.
Illegal after: reading token counts from anywhere but `Usage` — the dollar
figures in the summary are derived from it and nothing else.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

# List prices in dollars per million tokens, as published for the Claude API.
# Sonnet 5 carries a lower introductory input/output rate through 2026-08-31;
# the list rate is used here so a cost figure quoted in the proposal is never
# an under-estimate that expires.
PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


@dataclass
class Usage:
    """Cumulative token and call counts for one provider instance."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, reply: Reply) -> None:
        self.calls += 1
        self.input_tokens += reply.input_tokens
        self.output_tokens += reply.output_tokens

    def cost(self, model: str) -> float:
        """Dollars, or 0.0 for a model with no published price (the fake one).

        An unknown *real* model id would silently cost nothing here, so
        `AnthropicProvider.__init__` refuses one up front rather than letting a
        typo turn into a zero in `summary.json`.
        """
        if model not in PRICES:
            return 0.0
        per_in, per_out = PRICES[model]
        return (self.input_tokens * per_in + self.output_tokens * per_out) / 1_000_000

    def as_dict(self, model: str) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost(model), 4),
        }


@dataclass(frozen=True)
class Reply:
    """One completion, with the tokens it was billed for."""

    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


class Provider(Protocol):
    """The whole model interface the harness needs."""

    model: str
    usage: Usage
    params: dict[str, Any]

    def complete(self, prompt: str) -> Reply: ...


@dataclass
class FakeProvider:
    """Canned replies, cycled in order. The only provider used in tests.

    `replies` may be shorter than the number of calls; it wraps. That keeps a
    full fake-provider game (hundreds of decisions) expressible as a couple of
    canned strings.
    """

    replies: Sequence[str]
    model: str = "fake"
    usage: Usage = field(default_factory=Usage)
    params: dict[str, Any] = field(default_factory=dict)
    prompts: list[str] = field(default_factory=list)

    def complete(self, prompt: str) -> Reply:
        if not self.replies:
            raise ValueError("FakeProvider needs at least one canned reply")
        self.prompts.append(prompt)
        text = self.replies[(self.usage.calls) % len(self.replies)]
        reply = Reply(text=text, input_tokens=len(prompt) // 4, output_tokens=16)
        self.usage.add(reply)
        return reply


class AnthropicProvider:
    """The Claude API, via the official SDK.

    Request shape is model-dependent and comes from `params` (the config's
    per-model block) rather than being hard-coded, because the current models
    disagree about which knobs exist: Claude Opus 5 rejects `temperature`
    outright and runs adaptive thinking unless told otherwise, while Haiku 4.5
    has no `effort` at all. Whatever is sent is recorded verbatim in every
    transcript, so a run is reproducible from its own log.
    """

    def __init__(self, model: str, params: dict[str, Any] | None = None) -> None:
        if model not in PRICES:
            raise ValueError(
                f"no published price for model {model!r} — add it to PRICES, or "
                f"the run's reported cost would silently be $0.00. Known: "
                f"{sorted(PRICES)}"
            )
        import anthropic  # imported lazily: the offline matchup needs no SDK

        self.model = model
        # `params` is what the summary reports and is the whole reproduction
        # recipe, so it keeps every knob — including the two consumed here.
        # Reporting the post-`pop` remainder would omit `max_tokens` from the
        # record of a run it materially shaped.
        self.params = dict(params or {})
        request = dict(self.params)
        self.usage = Usage()
        self._max_tokens = int(request.pop("max_tokens", 512))
        self._request_params = request
        self._client = anthropic.Anthropic(
            max_retries=int(request.pop("max_retries", 5)),
        )

    def complete(self, prompt: str) -> Reply:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **self._request_params,
        )
        # A safety classifier can decline with HTTP 200 and an empty `content`;
        # indexing blindly would raise here instead of being counted as the
        # fallback it is.
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        reply = Reply(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )
        self.usage.add(reply)
        return reply


def make_provider(spec: dict[str, Any]) -> Provider:
    """Build a provider from a config block: `{kind, model, params}`."""
    kind = spec.get("kind", "anthropic")
    if kind == "fake":
        return FakeProvider(replies=list(spec.get("replies", ['{"action": 0}'])))
    if kind == "anthropic":
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            # The SDK also resolves an `ant auth login` profile, so this is a
            # warning path, not a refusal — but a missing key is by far the
            # likeliest cause of a run dying on its first call.
            print(
                "[llm_eval] note: ANTHROPIC_API_KEY is unset; falling back to "
                "whatever credential the SDK resolves (an `ant auth login` "
                "profile, or WIF)."
            )
        return AnthropicProvider(model=spec["model"], params=dict(spec.get("params", {})))
    raise ValueError(f"unknown provider kind {kind!r} (expected 'anthropic' or 'fake')")
