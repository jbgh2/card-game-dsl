"""The authoring rig's conversation and its declined replies, against fakes.

No test here calls a model. A scripted provider serves `Reply` objects, a
stub client stands in for the SDK's, and `smoke` is driven through a
patched `make_provider`. A declined reply is the API's `stop_reason:
"refusal"`; "refusal" alone names the checker's diagnostics in this rig.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        every reply is read as exactly one `ReplyKind`, a decline
                 before anything its text holds; a declined reply ends its
                 attempt with no further request, and `decline_limit` declined
                 attempts end the run; a config whose `decline_limit` is not a
                 whole number of attempts is refused before any call; a later
                 round's request is the conversation so far, under two
                 one-hour cache breakpoints, on the references block every
                 game shares and on the last block; a reply cut off at the
                 output limit is never
                 replayed, and every other reply that holds content is
                 replayed as returned.
domain:          `ReplyKind` crossed with its reader and the report's tally,
                 and `AttemptOutcome` crossed with the report's words, each
                 enumerated from the enum; the position of a decline in an
                 attempt (the first reply, after drafts); the `decline_limit`
                 values a config author plausibly writes.
held by:         a type where one can hold it: `run_attempt`, `stops_run`,
                 `outcome_words` and `reply_kind_words` match exhaustively
                 under `assert_never`. The rest is these pins.
does not prove:  anything about the API. No test here reaches it, so that it
                 accepts a replayed thinking block, streams this request, or
                 declines the conversation less often than the single message
                 is witnessed only by a run.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from .. import run_eval
from ..author_check import Checker
from ..author_prompt import ReplyKind, read_reply, task_text
from ..author_report import outcome_words, report
from ..author_run import AttemptOutcome
from ..prompts import Prompt
from ..providers import AnthropicProvider, FakeProvider, Reply, Usage
from ..spend import SpendLog
from .test_author_check import HIGH_CARD, TWO_TYPOS
from .test_author_run import ROOT, bench, block, config, rules, tree  # noqa: F401 -- fixtures

#: A checker whose every run is a crash, so a round it checked records a
#: check; the tests that use it assert no round has one.
NEVER_CHECKED = Checker(argv=("{python}", "-c", "raise SystemExit('the checker was called')"))


def declined(category: str | None = "reasoning_extraction", request_id: str = "req_decline") -> Reply:
    from ..providers import StopDetails

    return Reply(
        text="",
        input_tokens=40,
        output_tokens=0,
        stop_reason="refusal",
        stop_details=StopDetails(category=category, explanation="asked for its reasoning"),
        request_id=request_id,
    )


def answered(text: str) -> Reply:
    return Reply(
        text=text,
        input_tokens=40,
        output_tokens=16,
        stop_reason="end_turn",
        request_id="req_answer",
        content=({"type": "text", "text": text},),
    )


@dataclass
class ScriptedProvider:
    """Serves the scripted replies in order, the last one repeated."""

    replies: Sequence[Reply]
    model: str = "fake"
    usage: Usage = field(default_factory=Usage)
    params: dict[str, Any] = field(default_factory=dict)
    conversations: list[Any] = field(default_factory=list)

    def complete(self, prompt: Prompt) -> Reply:
        raise AssertionError("the authoring rig sends a conversation, never a one-message prompt")

    def converse(self, conversation: Any) -> Reply:
        self.conversations.append(conversation)
        reply = self.replies[min(self.usage.calls, len(self.replies) - 1)]
        self.usage.add(reply)
        return reply


# --- a declined reply ends its attempt ----------------------------------------


def test_a_declined_reply_ends_the_attempt_unchecked(tmp_path: Path, tree: Path, rules: Path) -> None:
    provider = ScriptedProvider([declined()])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider, checker=NEVER_CHECKED)
    assert provider.usage.calls == 1
    assert attempt["outcome"] == AttemptOutcome("declined").value
    assert "reasoning_extraction" in attempt["detail"]
    [row] = attempt["rounds"]
    assert row["reply_kind"] == ReplyKind("declined").value
    assert row["check"] is None and row["draft"] is None
    assert row["stop_reason"] == "refusal"
    assert row["stop_details"] == {
        "category": "reasoning_extraction",
        "explanation": "asked for its reasoning",
    }
    assert row["request_id"] == "req_decline"
    assert attempt["real_game"]["verdict"] == "not_reached"


def test_a_decline_after_a_draft_ends_the_attempt_there(tmp_path: Path, tree: Path, rules: Path) -> None:
    provider = ScriptedProvider([answered(block(TWO_TYPOS)), declined(category=None)])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider, round_limit=4)
    assert provider.usage.calls == 2
    assert attempt["outcome"] == "declined"
    assert [r["reply_kind"] for r in attempt["rounds"]] == ["draft", "declined"]
    assert attempt["rounds"][0]["check"]["verdict"] == "refused"
    assert attempt["rounds"][0]["request_id"] == "req_answer"
    assert attempt["rounds"][0]["stop_details"] is None
    assert attempt["rounds"][1]["stop_details"] == {"category": None, "explanation": "asked for its reasoning"}


def test_the_run_stops_at_the_decline_limit(tmp_path: Path, tree: Path, rules: Path) -> None:
    provider = ScriptedProvider([declined()])
    run_dir, _, attempts = bench(
        tmp_path, tree, rules, [], provider=provider, checker=NEVER_CHECKED, attempts=5, decline_limit=2
    )
    assert run_dir is not None
    assert provider.usage.calls == 2
    assert [a["outcome"] for a in attempts] == ["declined", "declined"]
    stopped = json.loads((run_dir / "run.json").read_text())["stopped"]
    assert stopped.startswith("declined")
    printed = io.StringIO()
    report(run_dir, printed)
    assert f"RUN STOPPED: {stopped}" in printed.getvalue()
    assert "Attempts: 2 recorded of 5 planned (games x models x attempts), a partial N" in printed.getvalue()


def test_the_planned_n_is_the_filtered_runs(tmp_path: Path, tree: Path, rules: Path) -> None:
    from ..author_facts import FactsRunner
    from ..author_run import run

    lowcard = {
        "slug": "lowcard",
        "name": "Low Card",
        "variant": "2 players",
        "source_url": "https://example.invalid/lowcard",
        "rules_file": "lowcard.txt",
    }
    cfg = config(tmp_path, attempts=2)
    cfg["games"] = [*cfg["games"], lowcard]
    run_dir = run(
        cfg,
        tmp_path / "config.yaml",
        rules,
        games_filter=["highcard"],
        registry={"fake": FakeProvider(replies=[block(HIGH_CARD)])},
        facts=FactsRunner(repo_root=ROOT, playouts=2),
        tree=tree,
        out=io.StringIO(),
    )
    assert run_dir is not None
    assert json.loads((run_dir / "run.json").read_text())["planned_attempts"] == 2
    printed = io.StringIO()
    report(run_dir, printed)
    assert "Attempts: 2 recorded of 2 planned (games x models x attempts)\n" in printed.getvalue()


def test_a_record_without_a_planned_n_says_so(tmp_path: Path) -> None:
    _record(tmp_path / "run", [_attempt("green", [_round("draft")])])
    printed = io.StringIO()
    report(tmp_path / "run", printed)
    assert "Attempts: 1 recorded; the planned N is not recorded" in printed.getvalue()


@pytest.mark.parametrize("limit", ["absent", 0, -1, "2", True, 2.0], ids=repr)
def test_a_config_without_a_usable_decline_limit_is_refused_before_any_call(
    tmp_path: Path, tree: Path, rules: Path, limit: object
) -> None:
    provider = FakeProvider(replies=[block(HIGH_CARD)])
    cfg = config(tmp_path)
    if limit == "absent":
        del cfg["decline_limit"]
    else:
        cfg["decline_limit"] = limit
    from ..author_facts import FactsRunner
    from ..author_run import run

    for dry_run in (True, False):
        with pytest.raises(ValueError, match="decline_limit"):
            run(
                cfg,
                tmp_path / "config.yaml",
                rules,
                registry={"fake": provider},
                facts=FactsRunner(repo_root=ROOT, playouts=2),
                tree=tree,
                dry_run=dry_run,
                out=io.StringIO(),
            )
    assert provider.usage.calls == 0


# --- later rounds are a conversation ------------------------------------------


HOUR = {"type": "ephemeral", "ttl": "1h"}


def marks(request: list[dict[str, Any]]) -> dict[tuple[int, int], Any]:
    """Every cache breakpoint of a request, by (message, block)."""
    return {
        (i, j): b["cache_control"]
        for i, message in enumerate(request)
        for j, b in enumerate(message["content"])
        if "cache_control" in b
    }


def test_round_two_is_the_conversation_so_far(tmp_path: Path, tree: Path, rules: Path) -> None:
    provider = FakeProvider(replies=[block(TWO_TYPOS), block(HIGH_CARD)])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert attempt["outcome"] == "green"
    first, second = provider.requests
    assert [m["role"] for m in first] == ["user"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    # The model's reply goes back as the provider returned it.
    assert second[1]["content"] == [{"type": "text", "text": block(TWO_TYPOS)}]
    # What the checker printed for draft 1 is the last user turn, verbatim.
    check = attempt["rounds"][0]["check"]
    said = (check["stdout"] + check["stderr"]).strip()
    last = "".join(b["text"] for b in second[2]["content"])
    assert said and said in last
    assert "Write file 2" in last
    # The first user turn is round 1's, the moved breakpoint its one change.
    def unmarked(message: dict[str, Any]) -> list[dict[str, Any]]:
        return [{k: v for k, v in b.items() if k != "cache_control"} for b in message["content"]]

    assert unmarked(second[0]) == unmarked(first[0])
    assert marks(first) == {(0, 0): HOUR, (0, 2): HOUR}, (
        "round 1: one-hour breakpoints on the references block and the request's last block"
    )
    assert marks(second) == {(0, 0): HOUR, (2, 1): HOUR}, (
        "round 2: the references breakpoint in place, the other moved to the last block"
    )
    # The digest covers the whole message list, so the two rounds differ.
    digests = [r["prompt_sha256"] for r in attempt["rounds"]]
    assert len(set(digests)) == 2
    assert attempt["rounds"][1]["prompt_blocks"] == sum(len(m["content"]) for m in second)


def test_a_long_conversation_keeps_its_two_breakpoints(tmp_path: Path, tree: Path, rules: Path) -> None:
    provider = FakeProvider(replies=["I would rather explain."])
    bench(tmp_path, tree, rules, [], provider=provider, round_limit=6)
    assert len(provider.requests) == 6
    for request in provider.requests:
        held = marks(request)
        assert len(held) <= 4, "the API takes at most four breakpoints in a request"
        assert held == {(0, 0): HOUR, (len(request) - 1, len(request[-1]["content"]) - 1): HOUR}, (
            "the references block and the last block, both one-hour"
        )


def test_every_game_shares_the_first_block(tmp_path: Path, tree: Path, rules: Path) -> None:
    lowcard = {
        "slug": "lowcard",
        "name": "Low Card",
        "variant": "2 players",
        "source_url": "https://example.invalid/lowcard",
        "rules_file": "lowcard.txt",
    }
    games = [*config(tmp_path)["games"], lowcard]
    provider = FakeProvider(replies=["CANNOT EXPRESS: nothing, this pins the shared prefix"])
    bench(tmp_path, tree, rules, [], provider=provider, games=games)
    high, low = provider.requests
    assert high[0]["content"][0] == low[0]["content"][0], (
        "the marked references block is byte-identical across games, so its cache entry is shared"
    )
    assert high[0]["content"][1] != low[0]["content"][1]


def test_a_reply_with_nothing_to_replay_leaves_no_empty_assistant_turn(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    provider = FakeProvider(replies=["", block(HIGH_CARD)])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert attempt["outcome"] == "green"
    _, second = provider.requests
    assert [m["role"] for m in second] == ["user", "user"]
    assert all(m["content"] for m in second)
    assert "held no file" in "".join(b["text"] for b in second[1]["content"])


SIGNED = {"type": "thinking", "thinking": "", "signature": "sig-1"}


def replied(text: str, content: tuple[Any, ...], stop_reason: str = "end_turn") -> Reply:
    return Reply(text=text, input_tokens=40, output_tokens=16, stop_reason=stop_reason, content=content)


def _sent(provider: ScriptedProvider) -> list[list[dict[str, Any]]]:
    from ..providers import conversation_messages

    return [conversation_messages(c) for c in provider.conversations]


def test_a_signed_thinking_block_reaches_the_next_request_unchanged(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    text = {"type": "text", "text": block(TWO_TYPOS)}
    provider = ScriptedProvider([replied(block(TWO_TYPOS), (SIGNED, text)), answered(block(HIGH_CARD))])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert attempt["outcome"] == "green"
    _, second = _sent(provider)
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"] == [SIGNED, text]
    assert second[1]["content"][0] is SIGNED


def test_a_complete_reply_without_a_file_is_replayed_as_returned(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    content = (SIGNED, {"type": "text", "text": "I would rather explain."})
    provider = ScriptedProvider([replied("I would rather explain.", content), answered(block(HIGH_CARD))])
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert attempt["rounds"][0]["reply_kind"] == "no_draft"
    _, second = _sent(provider)
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"] == list(content)


def test_a_reply_cut_off_at_the_output_limit_is_never_replayed(
    tmp_path: Path, tree: Path, rules: Path
) -> None:
    unsigned = {"type": "thinking", "thinking": ""}
    provider = ScriptedProvider(
        [replied("", (unsigned,), stop_reason="max_tokens"), answered(block(HIGH_CARD))]
    )
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert attempt["outcome"] == "green"
    _, second = _sent(provider)
    assert [m["role"] for m in second] == ["user", "user"]
    assert "cut off at the output limit" in "".join(b["text"] for b in second[1]["content"])


def test_each_round_records_what_it_replayed_and_no_block(tmp_path: Path, tree: Path, rules: Path) -> None:
    text = {"type": "text", "text": block(TWO_TYPOS)}
    unsigned = {"type": "thinking", "thinking": ""}
    provider = ScriptedProvider(
        [
            replied(block(TWO_TYPOS), (SIGNED, text)),
            replied("", (unsigned,), stop_reason="max_tokens"),
            answered(block(HIGH_CARD)),
        ]
    )
    run_dir, _, [attempt] = bench(tmp_path, tree, rules, [], provider=provider)
    assert run_dir is not None
    rounds = attempt["rounds"]
    assert [r["content_types"] for r in rounds] == [["thinking", "text"], ["thinking"], ["text"]]
    assert [r["replayed"] for r in rounds] == [True, False, False]
    record = (run_dir / "attempts.jsonl").read_text(encoding="utf-8")
    assert "sig-1" not in record and "signature" not in record


def test_a_round_records_its_one_hour_cache_writes(tmp_path: Path, tree: Path, rules: Path) -> None:
    written = Reply(
        text=block(HIGH_CARD),
        input_tokens=100,
        output_tokens=16,
        stop_reason="end_turn",
        cache_creation_input_tokens=60,
        cache_creation_1h_input_tokens=45,
    )
    _, _, [attempt] = bench(tmp_path, tree, rules, [], provider=ScriptedProvider([written]))
    assert attempt["rounds"][0]["usage"]["cache_creation_1h_input_tokens"] == 45
    assert attempt["usage"]["cache_creation_1h_input_tokens"] == 45


# --- the closed domains: every member is read --------------------------------

#: A reply of each kind, by the kind's value: the text and the stop reason.
REPLY_WITNESS: dict[str, tuple[str, str | None]] = {
    "draft": (block(HIGH_CARD), "end_turn"),
    "gave_up": ("CANNOT EXPRESS: a card that changes suit", "end_turn"),
    "no_draft": ("I would rather explain.", "end_turn"),
    "truncated": ("```cardlang\ngame X {", "max_tokens"),
    "declined": ("", "refusal"),
}


def test_every_reply_kind_has_a_witness() -> None:
    assert set(REPLY_WITNESS) == {kind.value for kind in ReplyKind}


@pytest.mark.parametrize("kind", list(ReplyKind), ids=lambda k: k.value)
def test_the_reader_yields_every_reply_kind(kind: ReplyKind) -> None:
    text, stop_reason = REPLY_WITNESS[kind.value]
    assert read_reply(text, stop_reason).kind is kind


def test_a_decline_is_read_before_anything_the_text_holds() -> None:
    assert read_reply(block(HIGH_CARD), "refusal").kind is ReplyKind("declined")
    assert read_reply("CANNOT EXPRESS: x", "refusal").kind is ReplyKind("declined")


def _record(run_dir: Path, attempts: Sequence[dict[str, Any]]) -> None:
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps({"git_head": "0" * 40, "checker": {}}))
    (run_dir / "attempts.jsonl").write_text("".join(json.dumps(a) + "\n" for a in attempts))


def _attempt(outcome: str, rounds: Sequence[dict[str, Any]], detail: str = "") -> dict[str, Any]:
    return {
        "game": "highcard",
        "held_out": "corpus_withheld",
        "model_ref": "fake",
        "model": "fake",
        "attempt": 0,
        "round_limit": 4,
        "outcome": outcome,
        "detail": detail,
        "summary": {
            "rounds": len(rounds),
            "drafts": 0,
            "first_draft_green": False,
            "fix_rounds_to_green": None,
            "could_not_act_on": 0,
        },
        "real_game": {"verdict": "not_reached"},
        "usage": {"cost_usd": 0.0},
        "rounds": list(rounds),
    }


def _round(kind: str, stop_reason: str | None = "end_turn", **extra: Any) -> dict[str, Any]:
    return {"round": 1, "reply_kind": kind, "stop_reason": stop_reason, "draft": None, "check": None, **extra}


@pytest.mark.parametrize("outcome", list(AttemptOutcome), ids=lambda o: o.value)
def test_the_report_names_every_outcome(tmp_path: Path, outcome: AttemptOutcome) -> None:
    _record(tmp_path / "run", [_attempt(outcome.value, [_round("no_draft")])])
    printed = io.StringIO()
    report(tmp_path / "run", printed)
    row = next(line for line in printed.getvalue().splitlines() if line.startswith("highcard"))
    assert outcome_words(outcome) in row


@pytest.mark.parametrize("kind", list(ReplyKind), ids=lambda k: k.value)
def test_the_report_counts_every_reply_kind(tmp_path: Path, kind: ReplyKind) -> None:
    from ..author_report import reply_kind_words

    _record(tmp_path / "run", [_attempt("round_limit", [_round(kind.value)])])
    printed = io.StringIO()
    report(tmp_path / "run", printed)
    assert f"{reply_kind_words(kind)} 1" in printed.getvalue()


def test_the_report_calls_out_declines_apart_from_checker_findings(tmp_path: Path) -> None:
    rounds = [
        _round(
            "declined",
            "refusal",
            stop_details={"category": "reasoning_extraction", "explanation": "x"},
            request_id="req_1",
        )
    ]
    # A refusal round stored as no_draft, with no stop details: the decline
    # is read from its stop reason, its category not recorded.
    earlier = [_round("no_draft", "refusal")]
    _record(
        tmp_path / "run",
        [
            _attempt("declined", rounds, detail="reasoning_extraction"),
            {**_attempt("round_limit", earlier), "attempt": 1},
        ],
    )
    printed = io.StringIO()
    report(tmp_path / "run", printed)
    text = printed.getvalue()
    assert "Declined replies: 2 in 2 attempt(s), 1 of them ending its attempt" in text
    assert "highcard/fake/0 round 1: reasoning_extraction (request req_1)" in text
    assert "highcard/fake/1 round 1: category not recorded (request not recorded)" in text
    assert "Decline categories: reasoning_extraction 1, not recorded 1" in text
    assert "Refusals a model could not act on: 0 occurrence(s)" in text


def test_the_kind_tally_reads_a_refusal_round_stored_as_no_draft_as_declined(tmp_path: Path) -> None:
    rounds = [_round("no_draft", "refusal"), {**_round("no_draft", "end_turn"), "round": 2}]
    _record(tmp_path / "run", [_attempt("round_limit", rounds)])
    printed = io.StringIO()
    report(tmp_path / "run", printed)
    text = printed.getvalue()
    assert "Replies by kind: draft 0, gave up 0, no file 1, cut off 0, declined 1" in text
    assert "Declined replies: 1 in 1 attempt(s)" in text


# --- the provider ---------------------------------------------------------------


class _Usage:
    input_tokens = 30
    output_tokens = 5
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 30


@dataclass
class _Block:
    type: str
    text: str = ""
    thinking: str = ""
    signature: str = ""


@dataclass
class _StopDetails:
    category: str | None
    explanation: str | None


class _Response:
    def __init__(self, stop_reason: str = "end_turn", stop_details: _StopDetails | None = None) -> None:
        self.content = [_Block("thinking", signature="sig"), _Block("text", text="the reply")]
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.usage = _Usage()
        self._request_id: str | None = "req_created"


class _Stream:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.request_id = "req_streamed"

    def __enter__(self) -> _Stream:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_final_message(self) -> _Response:
        self._response._request_id = None
        return self._response


class _Messages:
    def __init__(self, response: _Response) -> None:
        self.created: list[dict[str, Any]] = []
        self.streamed: list[dict[str, Any]] = []
        self._response = response

    def create(self, **kwargs: Any) -> _Response:
        self.created.append(kwargs)
        return self._response

    def stream(self, **kwargs: Any) -> _Stream:
        self.streamed.append(kwargs)
        return _Stream(self._response)


class _Client:
    def __init__(self, response: _Response) -> None:
        self.messages = _Messages(response)


def _stubbed(params: dict[str, Any], response: _Response | None = None) -> tuple[AnthropicProvider, _Messages]:
    pytest.importorskip("anthropic")
    provider = AnthropicProvider(model="claude-opus-5", params=params)
    client = _Client(response or _Response())
    provider._client = client  # type: ignore[assignment]
    return provider, client.messages


#: What `AnthropicProvider.complete` sends for these two prompts under these
#: params, as a literal; `complete` sends exactly this.
#: Born green; moving the breakpoint, or reshaping the one user message,
#: reddens it.
PLAYING_PARAMS: dict[str, Any] = {
    "max_tokens": 4000,
    "thinking": {"type": "disabled"},
    "output_config": {"effort": "high"},
    "max_retries": 2,
}
PLAYING_REQUESTS: list[dict[str, Any]] = [
    {
        "max_tokens": 4000,
        "messages": [
            {
                "content": [
                    {"text": "rules ", "type": "text"},
                    {"cache_control": {"type": "ephemeral"}, "text": "log;", "type": "text"},
                    {"text": "tail", "type": "text"},
                ],
                "role": "user",
            }
        ],
        "model": "claude-opus-5",
        "output_config": {"effort": "high"},
        "thinking": {"type": "disabled"},
    },
    {
        "max_tokens": 4000,
        "messages": [{"content": [{"text": "hello", "type": "text"}], "role": "user"}],
        "model": "claude-opus-5",
        "output_config": {"effort": "high"},
        "thinking": {"type": "disabled"},
    },
]


def test_the_playing_rigs_request_is_unchanged() -> None:
    provider, messages = _stubbed(dict(PLAYING_PARAMS))
    provider.complete(Prompt(blocks=("rules ", "log;", "tail"), cache_at=1))
    provider.complete(Prompt.single("hello"))
    assert messages.created == PLAYING_REQUESTS
    assert messages.streamed == []
    assert provider.params == PLAYING_PARAMS


def test_the_non_streaming_path_reads_the_decline_and_the_request_id() -> None:
    response = _Response("refusal", _StopDetails("reasoning_extraction", "why"))
    provider, messages = _stubbed({"max_tokens": 64}, response)
    reply = provider.complete(Prompt.single("hello"))
    assert len(messages.created) == 1 and messages.streamed == []
    assert reply.stop_reason == "refusal"
    assert reply.stop_details is not None
    assert (reply.stop_details.category, reply.stop_details.explanation) == ("reasoning_extraction", "why")
    assert reply.request_id == "req_created"
    assert reply.content == tuple(response.content)
    assert reply.text == "the reply"


def test_stop_details_are_read_only_from_a_decline() -> None:
    response = _Response("end_turn", _StopDetails("cyber", "stale"))
    provider, _ = _stubbed({"max_tokens": 64}, response)
    assert provider.complete(Prompt.single("hello")).stop_details is None
    bare = _Response("refusal", None)
    provider, _ = _stubbed({"max_tokens": 64}, bare)
    reply = provider.complete(Prompt.single("hello"))
    assert reply.stop_reason == "refusal" and reply.stop_details is None


def test_the_streaming_path_is_opt_in_and_reads_the_streams_request_id() -> None:
    from ..prompts import Conversation, Turn

    params = {"max_tokens": 64000, "streaming": True, "thinking": {"type": "adaptive"}}
    provider, messages = _stubbed(dict(params))
    earlier = (_Block("thinking", signature="sig-1"), _Block("text", text="draft 1"))
    conversation = Conversation(
        turns=(
            Turn("user", ("static ", "request 1")),
            Turn("assistant", earlier),
            Turn("user", ("checker said", "request 2")),
        )
    )
    reply = provider.converse(conversation)
    assert messages.created == []
    [call] = messages.streamed
    assert "streaming" not in call
    assert call["max_tokens"] == 64000 and call["thinking"] == {"type": "adaptive"}
    assert call["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "static ", "cache_control": HOUR},
                {"type": "text", "text": "request 1"},
            ],
        },
        {"role": "assistant", "content": list(earlier)},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "checker said"},
                {"type": "text", "text": "request 2", "cache_control": HOUR},
            ],
        },
    ]
    assert call["messages"][1]["content"][0] is earlier[0]
    assert reply.request_id == "req_streamed"
    assert provider.params == params


@pytest.mark.parametrize(
    "turns",
    [
        (),
        (("assistant", ("x",)),),
        (("user", ("x",)), ("assistant", ("y",))),
        (("user", ("x",)), ("assistant", ()), ("user", ("z",))),
        (("user", ("",)),),
        (("system", ("x",)),),
    ],
    ids=["empty", "starts with the model", "ends with the model", "an empty turn", "an empty block", "a system turn"],
)
def test_a_malformed_conversation_is_refused(turns: tuple[tuple[str, tuple[Any, ...]], ...]) -> None:
    from ..prompts import Conversation, Turn

    with pytest.raises(ValueError):
        Conversation(turns=tuple(Turn(role, content) for role, content in turns))  # type: ignore[arg-type]


# --- smoke and the task text -----------------------------------------------------


@dataclass
class _DecliningProvider:
    model: str = "claude-opus-5"
    usage: Usage = field(default_factory=Usage)
    params: dict[str, Any] = field(default_factory=dict)

    def complete(self, prompt: Prompt) -> Reply:
        reply = declined()
        self.usage.add(reply)
        return reply


@pytest.fixture
def no_real_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(run_eval, "make_provider", lambda spec: _DecliningProvider())
    yield


def test_smoke_prints_a_declines_category(
    tmp_path: Path, no_real_provider: None, capsys: pytest.CaptureFixture[str]
) -> None:
    config = {"models": {"frontier": {"kind": "anthropic", "model": "claude-opus-5"}}}
    log = SpendLog(tmp_path / "spend" / "log.jsonl")
    run_eval.smoke(config, [{"name": "smoke", "agents": [{"model": "frontier"}]}], log)
    # Every line but `declined` is the one a reply that is not declined prints.
    assert capsys.readouterr().out.splitlines() == [
        "",
        "--- frontier (claude-opus-5) params={}",
        "    text        ''",
        "    stop_reason refusal",
        "    declined    reasoning_extraction",
        "    tokens      40 in / 0 out",
        "    cost        $0.000200",
        "    parse       FAILED: no JSON object in response",
        "",
        "0/1 model(s) usable",
    ]


def test_the_give_up_line_asks_for_the_missing_construct_not_the_process() -> None:
    text = task_text(8)
    assert "CANNOT EXPRESS: <the rule, and the construct the language lacks for it>" in text
    assert "what you tried" not in text
