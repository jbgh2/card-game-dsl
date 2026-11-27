"""Cache-aware token accounting: the split is carried everywhere a token
quantity is carried, and dollars come from the split.

A cached prompt bills four ways: the uncached remainder at list price,
cache reads at `providers.CACHE_READ_RATE`, five-minute cache writes at
`providers.CACHE_WRITE_RATE`, and one-hour cache writes at
`providers.CACHE_WRITE_1H_RATE`. A cost computed from `input_tokens` alone
is wrong in both directions. `input_tokens` stays the TOTAL prompt size
(every cap, rate and per-game figure keeps its meaning) and the two cache
fields ride beside it from the API reply to the spend log; the one-hour
part of the writes, `cache_creation_1h_input_tokens`, is a subset of
`cache_creation_input_tokens` and rides beside it on the path to the spend
ceiling.

property:        every carrier of `input_tokens` in the rig carries
                 `cache_read_input_tokens` and `cache_creation_input_tokens`
                 beside it (`test_every_token_carrier_carries_the_split`, a
                 source scrape), and every such carrier on the ceiling's path
                 carries the one-hour part too
                 (`test_every_cache_write_carrier_on_the_ceilings_path_carries_the_one_hour_part`);
                 `Usage.cost` is the hand-computed split price, the one-hour
                 part at its own rate; the split survives the reply -> usage
                 -> summary delta, the reply -> attempt -> tally -> aggregate
                 chain, and the snapshot -> spend-log line -> reader chain;
                 the API request carries one text block per partition block
                 and the breakpoint on `cache_at`.
domain:          every module of `experiments/llm_eval` except its tests, the
                 three carrier shapes the scrape reads (dataclass fields, dict
                 literal keys, tuples of key names); for the one-hour part,
                 the modules on the ceiling's path (`ONE_HOUR_PATH`) less the
                 playing rigs' summary shape (`ONE_HOUR_EXEMPT`); the priced
                 models in `providers.PRICES`; a reply with and without cache
                 fields (an API usage block reports them as `None` when
                 caching was not requested), and with and without the
                 lifetime breakdown.
registry:        carriers: the scrape in this module; line shape:
                 `spend.ENTRY_FIELDS`; prices and rates: `providers.PRICES`,
                 `providers.CACHE_READ_RATE`, `providers.CACHE_WRITE_RATE`,
                 `providers.CACHE_WRITE_1H_RATE`; line-shape damage sweep:
                 experiments/llm_eval/tests/test_spend.py::test_a_damaged_line_cannot_reach_the_default_window
does not prove:  that the API bills at these rates (they are the published
                 list rates, copied); that the playing rigs' carriers would
                 hold a one-hour part, since none of their requests asks for
                 one; and nothing about whether a live request hits, which
                 only a real run's `cache_read_input_tokens` shows.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from ..agents import DecisionView, LLMAgent
from ..metrics import aggregate
from ..prompts import Prompt
from .. import providers as providers_mod
from ..providers import (
    CACHE_READ_RATE,
    CACHE_WRITE_RATE,
    PRICES,
    AnthropicProvider,
    FakeProvider,
    Reply,
    Usage,
)
from ..spend import ENTRY_FIELDS, Billed, Spend, billed_since, snapshot

SPLIT = ("cache_read_input_tokens", "cache_creation_input_tokens")
PACKAGE = Path(__file__).resolve().parents[1]


# --- the carrier class ------------------------------------------------------


def _carriers(tree: ast.AST) -> list[tuple[int, set[str]]]:
    """Every site that names `input_tokens` as a field or key, with the names
    beside it: dataclass fields, dict-literal keys, and tuples/lists of key
    names. The shapes a token quantity travels in through this package."""
    out: list[tuple[int, set[str]]] = []
    for node in ast.walk(tree):
        names = _site_names(node)
        if "input_tokens" in names:
            out.append((int(getattr(node, "lineno", 0)), names))
    return out


def _site_names(node: ast.AST) -> set[str]:
    """The field or key names one node carries, in the three carrier shapes."""
    if isinstance(node, ast.ClassDef):
        return {
            s.target.id
            for s in node.body
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
        }
    if isinstance(node, ast.Dict):
        return {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return set()


def test_every_token_carrier_carries_the_split() -> None:
    """A carrier that drops the split makes a cached run's dollars wrong
    silently somewhere downstream of it. red under: removing one cache field
    from any carrier the scrape lists."""
    missing: list[str] = []
    seen = 0
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for line, names in _carriers(tree):
            seen += 1
            if not set(SPLIT) <= names:
                missing.append(f"{path.name}:{line} carries {sorted(names)}")
    assert seen >= 8, f"the scrape found only {seen} carriers; its shapes no longer match the package"
    assert not missing, "carriers without the cache split:\n  " + "\n  ".join(missing)


# --- the price of a split ---------------------------------------------------


def test_usage_cost_is_the_split_price() -> None:
    usage = Usage(
        calls=1,
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=600_000,
        cache_creation_input_tokens=200_000,
    )
    per_in, per_out = PRICES["claude-haiku-4-5"]
    expected = (
        200_000 * per_in
        + 600_000 * per_in * CACHE_READ_RATE
        + 200_000 * per_in * CACHE_WRITE_RATE
        + 100_000 * per_out
    ) / 1_000_000
    assert usage.cost("claude-haiku-4-5") == pytest.approx(expected)
    assert usage.cost("claude-haiku-4-5") == pytest.approx(0.2 + 0.06 + 0.25 + 0.5)
    assert set(SPLIT) <= set(usage.as_dict("claude-haiku-4-5"))


def test_an_uncached_usage_costs_what_it_always_did() -> None:
    usage = Usage(calls=1, input_tokens=1_000_000, output_tokens=0)
    assert usage.cost("claude-haiku-4-5") == pytest.approx(1.0)


def test_a_reply_whose_split_exceeds_its_total_is_refused() -> None:
    with pytest.raises(ValueError, match="cache"):
        Reply(text="x", input_tokens=10, output_tokens=1, cache_read_input_tokens=11)
    with pytest.raises(ValueError, match="cache"):
        Reply(
            text="x", input_tokens=10, output_tokens=1,
            cache_read_input_tokens=6, cache_creation_input_tokens=5,
        )


def test_usage_add_and_difference_carry_the_split() -> None:
    usage = Usage()
    usage.add(Reply(text="", input_tokens=10, output_tokens=1, cache_read_input_tokens=4, cache_creation_input_tokens=3))
    usage.add(Reply(text="", input_tokens=20, output_tokens=2, cache_read_input_tokens=12))
    assert (usage.input_tokens, usage.cache_read_input_tokens, usage.cache_creation_input_tokens) == (30, 16, 3)
    before = Usage(calls=1, input_tokens=10, output_tokens=1, cache_read_input_tokens=4, cache_creation_input_tokens=3)
    delta = usage.since(before)
    assert (delta.calls, delta.input_tokens, delta.output_tokens) == (1, 20, 2)
    assert (delta.cache_read_input_tokens, delta.cache_creation_input_tokens) == (12, 0)


# --- the spend log ----------------------------------------------------------


def test_spend_and_the_log_line_carry_the_split() -> None:
    assert set(SPLIT) <= set(ENTRY_FIELDS)
    assert all(ENTRY_FIELDS[f] == "count" for f in SPLIT)
    total = Spend(10, 2, 0.5, 6, 1) + Spend(1, 1, 0.1, 1, 1)
    assert (total.cache_read_input_tokens, total.cache_creation_input_tokens) == (7, 2)
    assert (total - Spend(1, 1, 0.1, 1, 1)) == Spend(10, 2, 0.5, 6, 1)


def test_snapshot_and_billed_since_carry_the_split() -> None:
    provider = FakeProvider(replies=['{"action": 0}'])
    provider.usage = Usage(calls=2, input_tokens=100, output_tokens=10, cache_read_input_tokens=40, cache_creation_input_tokens=20)
    before = snapshot({"m": provider})
    assert before["m"].spend.cache_read_input_tokens == 40
    provider.usage = Usage(calls=3, input_tokens=160, output_tokens=15, cache_read_input_tokens=90, cache_creation_input_tokens=25)
    [row] = billed_since({"m": provider}, before)
    assert isinstance(row, Billed)
    assert row.spend == Spend(60, 5, 0.0, 50, 5)


# --- the transcript chain ---------------------------------------------------


class SplitProvider:
    """A provider whose replies carry a cache split, so the chain from the
    attempt record to the aggregate can be walked without the API."""

    model = "fake"
    params: dict[str, Any] = {}

    def __init__(self) -> None:
        self.usage = Usage()

    def complete(self, prompt: Prompt) -> Reply:
        reply = Reply(
            text='{"action": 0, "reasoning": "x"}',
            input_tokens=100,
            output_tokens=5,
            cache_read_input_tokens=70,
            cache_creation_input_tokens=10,
        )
        self.usage.add(reply)
        return reply


INFO = (
    "P1|hand[0]=#13;hand[1]=[A♠,K♠];hand[2]=#13;hand[3]=#13;played=#2;pile=#0;"
    "flipped=[];deck=#0|state:claim_rank=A;claimant=0;claim_count=2;challenged=False;"
    "challenger=None;responder=1;window_open=True;won={0:False,1:False,2:False,3:False}"
    "|obs:('announce', 0, 'play_cards')"
)


def test_the_attempt_record_carries_the_split() -> None:
    agent = LLMAgent(provider=SplitProvider(), seed=0, render=True)
    agent.choose(DecisionView(1, INFO, [54, 55], ["allow", "call_cheat"]))
    [attempt] = agent.pop_trace()["attempts"]
    assert (attempt["input_tokens"], attempt["cache_read_input_tokens"], attempt["cache_creation_input_tokens"]) == (100, 70, 10)


def test_the_game_tally_and_the_aggregate_carry_the_split() -> None:
    pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")
    from ..agents import RuleAgent
    from ..referee import load_game, play_game

    game = load_game("cardlang_cheat")
    seats: dict[int, Any] = {p: RuleAgent(seed=p) for p in range(4)}
    seats[0] = LLMAgent(provider=SplitProvider(), seed=0, render=True, name="llm")
    record = play_game(game, seats, seed=0, matchup="m", game_index=0, max_decisions=60)
    tally = record.usage["llm"]
    assert tally["input_tokens"] == 100 * tally["llm_calls"]
    assert tally["cache_read_input_tokens"] == 70 * tally["llm_calls"]
    assert tally["cache_creation_input_tokens"] == 10 * tally["llm_calls"]
    stats = aggregate([record.as_dict()])["agents"]["llm"]
    assert stats["cache_read_input_tokens"] == tally["cache_read_input_tokens"]
    assert stats["cache_creation_input_tokens"] == tally["cache_creation_input_tokens"]
    assert stats["cache_read_share"] == pytest.approx(0.7)


# --- the request shape ------------------------------------------------------


class _Usage:
    def __init__(self, **fields: Any) -> None:
        self.input_tokens = fields.get("input_tokens", 0)
        self.output_tokens = fields.get("output_tokens", 0)
        self.cache_read_input_tokens = fields.get("cache_read_input_tokens")
        self.cache_creation_input_tokens = fields.get("cache_creation_input_tokens")
        self.cache_creation = fields.get("cache_creation")


class _CacheCreation:
    """The usage block's breakdown of cache writes by lifetime."""

    def __init__(self, one_hour: int, five_minute: int) -> None:
        self.ephemeral_1h_input_tokens = one_hour
        self.ephemeral_5m_input_tokens = five_minute


class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Response:
    def __init__(self, usage: _Usage) -> None:
        self.content = [_Block('{"action": 0}')]
        self.stop_reason = "end_turn"
        self.usage = usage


class _Messages:
    def __init__(self, usage: _Usage) -> None:
        self.calls: list[dict[str, Any]] = []
        self._usage = usage

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return _Response(self._usage)


class _Client:
    def __init__(self, usage: _Usage) -> None:
        self.messages = _Messages(usage)


def _provider(usage: _Usage) -> tuple[AnthropicProvider, _Messages]:
    pytest.importorskip("anthropic")
    provider = AnthropicProvider(model="claude-haiku-4-5", params={"max_tokens": 8})
    client = _Client(usage)
    provider._client = client  # type: ignore[assignment]
    return provider, client.messages


def test_the_request_carries_the_blocks_and_the_breakpoint() -> None:
    provider, messages = _provider(_Usage(input_tokens=3, cache_read_input_tokens=20, cache_creation_input_tokens=7))
    reply = provider.complete(Prompt(blocks=("rules ", "log;", "tail"), cache_at=1))
    [call] = messages.calls
    [message] = call["messages"]
    assert message["role"] == "user"
    assert [b["text"] for b in message["content"]] == ["rules ", "log;", "tail"]
    assert [b.get("cache_control") for b in message["content"]] == [None, {"type": "ephemeral"}, None]
    assert (reply.input_tokens, reply.cache_read_input_tokens, reply.cache_creation_input_tokens) == (30, 20, 7)


def test_a_single_block_prompt_asks_for_no_cache() -> None:
    provider, messages = _provider(_Usage(input_tokens=9))
    reply = provider.complete(Prompt.single("hello"))
    [call] = messages.calls
    [block] = call["messages"][0]["content"]
    assert block == {"type": "text", "text": "hello"}
    assert (reply.input_tokens, reply.cache_read_input_tokens, reply.cache_creation_input_tokens) == (9, 0, 0)


# --- the one-hour part of the cache writes -----------------------------------

ONE_HOUR = "cache_creation_1h_input_tokens"

#: The modules a conversation's dollars pass through on their way to the spend
#: ceiling: the reply and its usage, the authoring rig's round and attempt
#: records, and the spend log. The playing rigs' carriers sit outside it: none
#: of their requests asks for the one-hour cache.
ONE_HOUR_PATH = ("providers.py", "author_run.py", "spend.py")

#: Carriers on that path that hold the cache split and not the one-hour part:
#: `Usage.as_dict` is the playing rigs' summary shape.
ONE_HOUR_EXEMPT = {("providers.py", "Usage.as_dict")}


def _scoped_carriers(tree: ast.Module) -> list[tuple[str, int, set[str]]]:
    """Every carrier site, with the dotted names of the classes and
    functions it sits in."""
    out: list[tuple[str, int, set[str]]] = []

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = f"{scope}.{child.name}" if scope else child.name
            names = _site_names(child)
            if "input_tokens" in names:
                out.append((inner, int(getattr(child, "lineno", 0)), names))
            walk(child, inner)

    walk(tree, "")
    return out


def test_every_cache_write_carrier_on_the_ceilings_path_carries_the_one_hour_part() -> None:
    """A carrier that drops the one-hour part prices those writes at the
    five-minute rate, an under-count the spend ceiling then inherits.
    red under: removing `cache_creation_1h_input_tokens` from any carrier
    this scrape lists."""
    missing: list[str] = []
    seen = 0
    for name in ONE_HOUR_PATH:
        tree = ast.parse((PACKAGE / name).read_text(), filename=name)
        for scope, line, names in _scoped_carriers(tree):
            if "cache_creation_input_tokens" not in names or (name, scope) in ONE_HOUR_EXEMPT:
                continue
            seen += 1
            if ONE_HOUR not in names:
                missing.append(f"{name}:{line} ({scope or 'module'}) carries {sorted(names)}")
    assert seen >= 6, f"the scrape found only {seen} carriers on the ceiling's path"
    assert not missing, "carriers without the one-hour part:\n  " + "\n  ".join(missing)


def test_one_hour_writes_are_priced_at_their_own_rate() -> None:
    usage = Usage(
        calls=1,
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=600_000,
        cache_creation_input_tokens=200_000,
        cache_creation_1h_input_tokens=150_000,
    )
    per_in, per_out = PRICES["claude-haiku-4-5"]
    expected = (
        200_000 * per_in
        + 600_000 * per_in * CACHE_READ_RATE
        + 50_000 * per_in * CACHE_WRITE_RATE
        + 150_000 * per_in * providers_mod.CACHE_WRITE_1H_RATE
        + 100_000 * per_out
    ) / 1_000_000
    assert usage.cost("claude-haiku-4-5") == pytest.approx(expected)
    assert usage.cost("claude-haiku-4-5") == pytest.approx(0.2 + 0.06 + 0.0625 + 0.3 + 0.5)
    assert providers_mod.CACHE_WRITE_1H_RATE == 2.0


def test_a_usage_with_no_one_hour_part_costs_what_it_did() -> None:
    """A record without the one-hour part, and every playing rig, leaves it at
    its default and prices every write at the five-minute rate."""
    old = Usage(1, 1_000_000, 100_000, 600_000, 200_000)
    assert old.cost("claude-haiku-4-5") == pytest.approx(0.2 + 0.06 + 0.25 + 0.5)
    reply = Reply(text="", input_tokens=10, output_tokens=1, cache_creation_input_tokens=4)
    assert reply.cache_creation_1h_input_tokens == 0


def test_a_one_hour_part_beyond_the_writes_is_refused() -> None:
    with pytest.raises(ValueError, match="one-hour"):
        Reply(
            text="x", input_tokens=10, output_tokens=1,
            cache_creation_input_tokens=3, cache_creation_1h_input_tokens=4,
        )
    with pytest.raises(ValueError, match="one-hour"):
        Reply(text="x", input_tokens=10, output_tokens=1, cache_creation_1h_input_tokens=-1)


def test_usage_and_spend_carry_the_one_hour_part() -> None:
    usage = Usage()
    usage.add(Reply(text="", input_tokens=10, output_tokens=1, cache_creation_input_tokens=6, cache_creation_1h_input_tokens=5))
    usage.add(Reply(text="", input_tokens=10, output_tokens=1, cache_creation_input_tokens=2))
    assert usage.cache_creation_1h_input_tokens == 5
    assert usage.since(Usage(cache_creation_1h_input_tokens=2)).cache_creation_1h_input_tokens == 3
    total = Spend(10, 2, 0.5, 6, 3, 2) + Spend(1, 1, 0.1, 1, 1, 1)
    assert total.cache_creation_1h_input_tokens == 3
    assert (total - Spend(1, 1, 0.1, 1, 1, 1)) == Spend(10, 2, 0.5, 6, 3, 2)
    assert ENTRY_FIELDS[ONE_HOUR] == "count"
    provider = FakeProvider(replies=['{"action": 0}'])
    provider.usage = Usage(calls=1, input_tokens=100, cache_creation_input_tokens=40, cache_creation_1h_input_tokens=30)
    before = snapshot({"m": provider})
    assert before["m"].spend.cache_creation_1h_input_tokens == 30
    provider.usage = Usage(calls=2, input_tokens=200, cache_creation_input_tokens=90, cache_creation_1h_input_tokens=70)
    [row] = billed_since({"m": provider}, before)
    assert row.spend.cache_creation_1h_input_tokens == 40


def test_the_provider_reads_the_one_hour_part_of_the_writes() -> None:
    provider, _ = _provider(
        _Usage(
            input_tokens=3, cache_read_input_tokens=20, cache_creation_input_tokens=7,
            cache_creation=_CacheCreation(5, 2),
        )
    )
    reply = provider.complete(Prompt.single("hello"))
    assert (reply.cache_creation_input_tokens, reply.cache_creation_1h_input_tokens) == (7, 5)
    provider, _ = _provider(_Usage(input_tokens=3, cache_creation_input_tokens=7))
    assert provider.complete(Prompt.single("hello")).cache_creation_1h_input_tokens == 0
