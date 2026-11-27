"""Model-API abstraction: a request in, a `Reply` out, plus usage accounting.

`complete` sends a `Prompt` as one user message, the form every playing rig
uses; `converse` sends a `Conversation`, earlier replies as assistant turns
(`ConversingProvider`, which the authoring rig needs). Two implementations.
`AnthropicProvider` is the real one; `FakeProvider` serves canned replies and
is the only provider the unit tests use: there is no network in tests.

Contract
--------
Assumes: `ANTHROPIC_API_KEY` (or an `ant auth login` profile) is present before
`AnthropicProvider` sends a request; nothing is read from the environment at
import time.
Establishes: a `Reply` carrying the text, the exact token counts billed, the
reply's content blocks for replay, and a decline's stop details and request
id; a running `Usage` total per provider instance; and one wire form for a
conversation (`conversation_messages`) that both implementations send.
Illegal after: reading token counts from anywhere but `Usage` — the dollar
figures in the summary are derived from it and nothing else.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

from .prompts import Conversation, Prompt

if TYPE_CHECKING:
    from anthropic.types import Message

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

#: Prompt-cache rates as multiples of the model's input price: a read is
#: billed at a tenth, a five-minute write at a quarter over, and a one-hour
#: write at double. The playing rigs ask for the five-minute cache, the
#: authoring rig's conversations for the one-hour cache. Cache reads on
#: `claude-fable-5-1` are cheaper still and that model is not priced here.
CACHE_READ_RATE = 0.10
CACHE_WRITE_RATE = 1.25
CACHE_WRITE_1H_RATE = 2.0

#: The breakpoint the authoring rig's conversations carry: the one-hour
#: lifetime outlasts a first reply that takes longer than five minutes.
CONVERSATION_CACHE: Final[Mapping[str, str]] = {"type": "ephemeral", "ttl": "1h"}


@dataclass
class Usage:
    """Cumulative token and call counts for one provider instance.

    `input_tokens` is the whole prompt, every call; the two cache fields say
    how much of it the cache read and wrote, and the uncached remainder is
    the difference. Kept that way so a cap, a per-game rate and a summary
    figure all mean "prompt tokens" whether or not a call hit the cache.
    `cache_creation_1h_input_tokens` is the part of the writes made with the
    one-hour lifetime; the rest are five-minute writes.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_creation_1h_input_tokens: int = 0

    def add(self, reply: Reply) -> None:
        self.calls += 1
        self.input_tokens += reply.input_tokens
        self.output_tokens += reply.output_tokens
        self.cache_read_input_tokens += reply.cache_read_input_tokens
        self.cache_creation_input_tokens += reply.cache_creation_input_tokens
        self.cache_creation_1h_input_tokens += reply.cache_creation_1h_input_tokens

    def since(self, before: Usage) -> Usage:
        """This usage beyond an earlier snapshot of the same provider."""
        return Usage(
            calls=self.calls - before.calls,
            input_tokens=self.input_tokens - before.input_tokens,
            output_tokens=self.output_tokens - before.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens - before.cache_read_input_tokens,
            cache_creation_input_tokens=(
                self.cache_creation_input_tokens - before.cache_creation_input_tokens
            ),
            cache_creation_1h_input_tokens=(
                self.cache_creation_1h_input_tokens - before.cache_creation_1h_input_tokens
            ),
        )

    def cost(self, model: str) -> float:
        """Dollars, or 0.0 for a model with no published price (the fake one).

        An unknown *real* model id would silently cost nothing here, so
        `AnthropicProvider.__init__` refuses one up front rather than letting a
        typo turn into a zero in `summary.json`.
        """
        if model not in PRICES:
            return 0.0
        per_in, per_out = PRICES[model]
        uncached = self.input_tokens - self.cache_read_input_tokens - self.cache_creation_input_tokens
        five_minute = self.cache_creation_input_tokens - self.cache_creation_1h_input_tokens
        return (
            uncached * per_in
            + self.cache_read_input_tokens * per_in * CACHE_READ_RATE
            + five_minute * per_in * CACHE_WRITE_RATE
            + self.cache_creation_1h_input_tokens * per_in * CACHE_WRITE_1H_RATE
            + self.output_tokens * per_out
        ) / 1_000_000

    def as_dict(self, model: str) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cost_usd": round(self.cost(model), 4),
        }


@dataclass(frozen=True)
class StopDetails:
    """Why the API declined a request (`stop_reason == "refusal"`): its
    policy category and explanation, either of which the API may leave
    null."""

    category: str | None
    explanation: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"category": self.category, "explanation": self.explanation}


@dataclass(frozen=True)
class Reply:
    """One completion, with the tokens it was billed for.

    `input_tokens` is the whole prompt; the cache fields are the part of it
    served from and written to the prompt cache, so they never exceed it.
    `content` is the reply's content blocks as the API returned them, for a
    later request to replay unchanged; `text` is its text blocks joined.
    `stop_details` is read only from a declined reply.
    `cache_creation_1h_input_tokens` is the one-hour part of the writes.
    """

    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    stop_details: StopDetails | None = None
    request_id: str | None = None
    content: tuple[Any, ...] = ()
    cache_creation_1h_input_tokens: int = 0

    def __post_init__(self) -> None:
        cached = self.cache_read_input_tokens + self.cache_creation_input_tokens
        if cached > self.input_tokens:
            raise ValueError(
                f"cache fields ({self.cache_read_input_tokens} read + "
                f"{self.cache_creation_input_tokens} written) exceed the prompt's "
                f"{self.input_tokens} input tokens"
            )
        if not 0 <= self.cache_creation_1h_input_tokens <= self.cache_creation_input_tokens:
            raise ValueError(
                f"the one-hour part of the cache writes "
                f"({self.cache_creation_1h_input_tokens}) is not within the "
                f"{self.cache_creation_input_tokens} written"
            )


class Provider(Protocol):
    """The whole model interface the harness needs."""

    model: str
    usage: Usage
    params: dict[str, Any]

    def complete(self, prompt: Prompt) -> Reply: ...


@runtime_checkable
class ConversingProvider(Provider, Protocol):
    """A provider that can also send a `Conversation`."""

    def converse(self, conversation: Conversation) -> Reply: ...


def conversation_messages(conversation: Conversation) -> list[dict[str, Any]]:
    """The `messages` list a conversation is sent as: each user block a
    text block, each assistant turn its content as returned, and two
    one-hour cache breakpoints (`CONVERSATION_CACHE`): on the first block of
    the first turn, the prefix conversations share, and on the last block of
    the last turn. Both are user blocks, so no returned block is touched."""
    messages: list[dict[str, Any]] = []
    for turn in conversation.turns:
        if turn.role == "user":
            content: list[Any] = [{"type": "text", "text": block} for block in turn.content]
        else:
            content = list(turn.content)
        messages.append({"role": turn.role, "content": content})
    messages[0]["content"][0]["cache_control"] = dict(CONVERSATION_CACHE)
    messages[-1]["content"][-1]["cache_control"] = dict(CONVERSATION_CACHE)
    return messages


def _stop_details(response: Any) -> StopDetails | None:
    """A declined response's stop details; None for any other response, and
    for a decline the API gave none for."""
    if response.stop_reason != "refusal":
        return None
    details = getattr(response, "stop_details", None)
    if details is None:
        return None
    return StopDetails(
        category=getattr(details, "category", None),
        explanation=getattr(details, "explanation", None),
    )


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
    #: Each conversation's `messages` list, as `AnthropicProvider` sends it.
    requests: list[list[dict[str, Any]]] = field(default_factory=list)

    def complete(self, prompt: Prompt) -> Reply:
        if not self.replies:
            raise ValueError("FakeProvider needs at least one canned reply")
        self.prompts.append(prompt.text)
        text = self.replies[(self.usage.calls) % len(self.replies)]
        reply = Reply(text=text, input_tokens=len(prompt.text) // 4, output_tokens=16)
        self.usage.add(reply)
        return reply

    def converse(self, conversation: Conversation) -> Reply:
        """The next canned reply, its content one text block, or no block
        for an empty reply."""
        if not self.replies:
            raise ValueError("FakeProvider needs at least one canned reply")
        self.prompts.append(conversation.text)
        self.requests.append(conversation_messages(conversation))
        text = self.replies[(self.usage.calls) % len(self.replies)]
        reply = Reply(
            text=text,
            input_tokens=len(conversation.text) // 4,
            output_tokens=16,
            stop_reason="end_turn",
            content=({"type": "text", "text": text},) if text else (),
        )
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

    Three keys of `params` are the provider's and never reach the request:
    `max_tokens`, `max_retries`, and `streaming`, which sends the request
    through `messages.stream` and reads its final message, as the SDK
    requires of a request whose output limit it estimates would outlast a
    non-streaming call.
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
        # recipe, so it keeps every knob, including the ones consumed here.
        # Reporting the post-`pop` remainder would omit `max_tokens` from the
        # record of a run it materially shaped.
        self.params = dict(params or {})
        request = dict(self.params)
        self.usage = Usage()
        self._max_tokens = int(request.pop("max_tokens", 512))
        self._streaming = bool(request.pop("streaming", False))
        self._request_params = request
        self._client = anthropic.Anthropic(
            max_retries=int(request.pop("max_retries", 5)),
        )

    def complete(self, prompt: Prompt) -> Reply:
        # One text block per partition block, the five-minute cache breakpoint
        # on the block the partition names. The API reads the blocks as their
        # exact concatenation, so the model sees `prompt.text`.
        content: list[Any] = [
            {"type": "text", "text": block} for block in prompt.blocks
        ]
        if prompt.cache_at is not None:
            content[prompt.cache_at]["cache_control"] = {"type": "ephemeral"}
        return self._send([{"role": "user", "content": content}])

    def converse(self, conversation: Conversation) -> Reply:
        return self._send(conversation_messages(conversation))

    def _send(self, messages: list[dict[str, Any]]) -> Reply:
        response: Message
        request_id: str | None
        if self._streaming:
            with self._client.messages.stream(
                model=self.model,
                max_tokens=self._max_tokens,
                messages=messages,  # type: ignore[arg-type]
                **self._request_params,
            ) as stream:
                response = stream.get_final_message()
                # The accumulated message carries no request id; the stream's
                # response headers do.
                request_id = stream.request_id
        else:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                messages=messages,  # type: ignore[arg-type]
                **self._request_params,
            )
            request_id = getattr(response, "_request_id", None)
        # A safety classifier can decline with HTTP 200 and an empty `content`;
        # indexing blindly would raise here instead of being counted as the
        # fallback it is.
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        # The API's `input_tokens` is the uncached remainder, and its cache
        # fields, the lifetime breakdown among them, are absent (`None`) on a
        # request that asked for no caching.
        usage = response.usage
        cache_read = int(getattr(usage, "cache_read_input_tokens", None) or 0)
        cache_creation = int(getattr(usage, "cache_creation_input_tokens", None) or 0)
        breakdown = getattr(usage, "cache_creation", None)
        one_hour = int(getattr(breakdown, "ephemeral_1h_input_tokens", None) or 0)
        reply = Reply(
            text=text,
            input_tokens=usage.input_tokens + cache_read + cache_creation,
            output_tokens=usage.output_tokens,
            stop_reason=response.stop_reason,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
            stop_details=_stop_details(response),
            request_id=request_id,
            content=tuple(response.content),
            cache_creation_1h_input_tokens=one_hour,
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
