"""The prompt's cache partition: the same bytes, cut where a cache can hit.

`prompts.cache_partition` cuts one decision prompt into content blocks so the
API's prompt cache can serve the part that repeats between a seat's calls —
the static rules and the append-only event log — and re-reads only what
changed. The model reads the concatenation, and the API tokenizes a
multi-block message as its exact concatenation (`count_tokens` agrees byte
for byte; a separator would move the count), so the cut is invisible to the
stimulus and the treatment record, and everything it does is billing.

property:        `Prompt.text == prompt` for every prompt (the cut adds and
                 drops nothing); every block is non-empty; the rendered
                 arm's log is cut at every `chunk`-th event separator into
                 COMPLETE chunks — text that no later call of the same seat
                 in the same game can change — with the breakpoint on the
                 last complete chunk, so the next call reproduces every
                 boundary the previous call wrote at; the raw arm is one
                 block with no breakpoint.
domain:          log sizes crossing every boundary of the chunk arithmetic
                 (`_log_sizes`: empty, one event, one short of a chunk, an
                 exact chunk, one over, two chunks, one over two) at chunk
                 sizes 1, 2 and the shipped `LOG_CHUNK_EVENTS`; both arms;
                 the prompt with and without the retry note appended; and
                 the growth witness — every seat-0 decision of the committed
                 null control's first game, rendered log-first and cut, each
                 call's boundaries checked against the call before it.
registry:        log header and terminator: `render.LOG_HEADER`,
                 `render.LOG_END`; chunk size: `prompts.LOG_CHUNK_EVENTS`;
                 render order (log before the table view):
                 experiments/llm_eval/tests/test_render.py::test_the_log_precedes_the_table_view
does not prove:  that the live API serves a read at those boundaries — the
                 cache minimum per model and the five-minute TTL are the
                 API's, and the witness for a live hit is
                 `cache_read_input_tokens > 0` in a real run's spend record.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from ..prompts import (
    LOG_CHUNK_EVENTS,
    RESPONSE_ARMS,
    RULES_RAW,
    RULES_RENDERED,
    Prompt,
    build_prompt,
    cache_partition,
)
from ..render import LOG_END, LOG_HEADER, render_state

#: Log sizes, in events, around every boundary of the chunk arithmetic for a
#: chunk of `k` events — derived per `k` so a cell cannot sit on the wrong
#: side of a boundary when the chunk size changes.
def _log_sizes(k: int) -> list[int]:
    return sorted({0, 1, k - 1, k, k + 1, 2 * k, 2 * k + 1})


CHUNKS = (1, 2, LOG_CHUNK_EVENTS)
LEGAL = ["allow", "call_cheat"]
RESPONSE = RESPONSE_ARMS["reasoning"].instruction
RETRY = RESPONSE_ARMS["reasoning"].retry.format(error="no JSON object in response")


def _event(i: int) -> str:
    return f"('announce', {i % 4}, 'allow')"


def _rendered(n_events: int) -> str:
    """A rendered state carrying exactly `n_events` log events, log-first."""
    log = ";".join(_event(i) for i in range(n_events))
    return (
        "You are seat 0, of 4 players.\n\n"
        f"{LOG_HEADER}{log}{LOG_END}"
        "Your hand holds 2 cards: A♠ K♠\n"
        "Seat 1 holds 3 cards, which you cannot see.\n"
    )


def _raw(n_events: int) -> str:
    log = ";".join(_event(i) for i in range(n_events))
    return f"P0|hand[0]=[A♠,K♠];hand[1]=#3|state:claim_rank=A|obs:{log}"


def _expected_complete(n_events: int, k: int) -> int:
    """Complete chunks: a chunk is complete when the separator closing its
    last event exists, so it is `(separators) // k` with `n - 1` separators."""
    return 0 if n_events == 0 else (n_events - 1) // k


def _cells() -> list[tuple[int, int, bool]]:
    return [(k, n, retry) for k in CHUNKS for n in _log_sizes(k) for retry in (False, True)]


@pytest.mark.parametrize(("k", "n", "retry"), _cells())
def test_rendered_partition_cell(k: int, n: int, retry: bool) -> None:
    text = build_prompt(RULES_RENDERED, _rendered(n), LEGAL, RESPONSE)
    if retry:
        text += RETRY
    prompt = cache_partition(text, chunk=k)
    assert isinstance(prompt, Prompt)
    assert prompt.text == text
    assert all(prompt.blocks), "an empty text block is an API error, not a cut"
    m = _expected_complete(n, k)
    # head, the complete chunks, and one block holding the partial chunk and
    # everything after the log.
    assert len(prompt.blocks) == 1 + m + 1
    head = prompt.blocks[0]
    assert head.endswith(LOG_HEADER)
    assert head.startswith(RULES_RENDERED)
    for chunk in prompt.blocks[1 : 1 + m]:
        assert chunk.count(";") == k and chunk.endswith(";")
    assert prompt.cache_at == (m if m else 0)
    assert LOG_END in prompt.blocks[-1]
    if retry:
        assert prompt.blocks[-1].endswith(RETRY)


@pytest.mark.parametrize(("k", "n"), [(k, n) for k in CHUNKS for n in _log_sizes(k)])
def test_raw_partition_is_one_block_without_a_breakpoint(k: int, n: int) -> None:
    text = build_prompt(RULES_RAW, _raw(n), LEGAL, RESPONSE)
    prompt = cache_partition(text, chunk=k)
    assert prompt.blocks == (text,)
    assert prompt.cache_at is None
    assert prompt.text == text


@pytest.mark.parametrize("k", CHUNKS)
def test_growth_keeps_every_written_boundary(k: int) -> None:
    """Between two calls the log only grows, so every boundary the earlier
    call put its breakpoint at is a boundary of the later call, at the same
    offset, with the same text before it — the condition for a cache read."""
    sizes = _log_sizes(k)
    for n1, n2 in zip(sizes, sizes[1:]):
        p1 = cache_partition(build_prompt(RULES_RENDERED, _rendered(n1), LEGAL, RESPONSE), chunk=k)
        p2 = cache_partition(build_prompt(RULES_RENDERED, _rendered(n2), LEGAL, RESPONSE), chunk=k)
        assert p1.cache_at is not None
        written = "".join(p1.blocks[: p1.cache_at + 1])
        boundaries = {"".join(p2.blocks[: i + 1]) for i in range(len(p2.blocks))}
        assert written in boundaries


@pytest.mark.parametrize("k", [0, -1])
def test_a_chunk_below_one_event_is_refused(k: int) -> None:
    with pytest.raises(ValueError, match="chunk"):
        cache_partition(build_prompt(RULES_RENDERED, _rendered(3), LEGAL, RESPONSE), chunk=k)


def test_prompt_invariants_are_owned_by_the_type() -> None:
    with pytest.raises(ValueError):
        Prompt(blocks=(), cache_at=None)
    with pytest.raises(ValueError):
        Prompt(blocks=("a", ""), cache_at=None)
    with pytest.raises(ValueError):
        Prompt(blocks=("a", "b"), cache_at=2)
    assert Prompt.single("abc") == Prompt(blocks=("abc",), cache_at=None)


ARCHIVE = Path(__file__).resolve().parents[1] / "results_cheat_gap" / "transcripts" / "rule_table.jsonl.gz"


def test_growth_witness_on_an_archived_game() -> None:
    """The arithmetic cells above use synthetic logs; this walks a real line
    — the committed null control's first game, every seat-0 decision
    rendered log-first and cut at the shipped chunk — and checks the same
    boundary condition call over call, plus join identity on every prompt."""
    pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")
    from ..referee import load_game, replay_views

    with gzip.open(ARCHIVE, "rt") as f:
        record: dict[str, Any] = json.loads(f.readline())
    game = load_game("cardlang_cheat")
    views = replay_views(game, record["seed"], record["history"], expected_digest=record["game_digest"])
    previous: Prompt | None = None
    calls = 0
    for view in views:
        if view.player != 0 or len(view.legal_actions) == 1:
            continue
        text = build_prompt(RULES_RENDERED, render_state(view.infostate), view.legal_strings, RESPONSE)
        prompt = cache_partition(text)
        assert prompt.text == text
        if previous is not None:
            assert previous.cache_at is not None
            written = "".join(previous.blocks[: previous.cache_at + 1])
            boundaries = {"".join(prompt.blocks[: i + 1]) for i in range(len(prompt.blocks))}
            assert written in boundaries, f"call {calls}: the previous breakpoint is not a boundary"
        previous = prompt
        calls += 1
    assert calls > 20, "the witness game offered too few open decisions to mean anything"
    assert previous is not None and len(previous.blocks) > 3, "the line never grew past one chunk"
