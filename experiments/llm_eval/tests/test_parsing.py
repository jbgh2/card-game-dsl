"""Response parsing and the failure policy.

The fallback rate is a reported metric, so a parser that quietly rescues a
malformed reply would understate it. These pin the boundary between "read" and
"named error".
"""

from __future__ import annotations

import pytest

from ..agents import DecisionView, LLMAgent
from ..prompts import parse_response
from ..providers import FakeProvider

VIEW = DecisionView(
    player=1,
    infostate=(
        "P1|hand[1]=[A♠,A♥,A♦,A♣,2♠]|state:claim_count=2;claim_rank=A;claimant=0"
        "|obs:()"
    ),
    legal_actions=[54, 55],
    legal_strings=["allow", "call_cheat"],
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"action": 1, "reasoning": "call it"}', 1),
        ('{"action": 0, "reasoning": ""}', 0),
        ('Sure!\n```json\n{"action": 1, "reasoning": "x"}\n```\n', 1),
        ('<thinking>hmm</thinking>{"action": 0, "reasoning": "y"}', 0),
        ('{"reasoning": "z", "action": 1}', 1),
        ('{"action": "1", "reasoning": "string index"}', 1),
    ],
)
def test_good_responses(text: str, expected: int) -> None:
    result = parse_response(text, num_actions=2)
    assert result.ok and result.index == expected


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("I choose to allow.", "no JSON object"),
        ('{"action": 1,}', "malformed JSON"),
        ('{"action": 7, "reasoning": "x"}', "out of range"),
        ('{"action": -1, "reasoning": "x"}', "out of range"),
        ('{"action": "allow", "reasoning": "x"}', "not an integer"),
        ('{"action": true, "reasoning": "x"}', "not an integer"),
        ('{"action": 1.5, "reasoning": "x"}', "not an integer"),
        ('{"reasoning": "forgot the action"}', "not an integer"),
        ("[1, 2, 3]", "no JSON object"),
        ("", "no JSON object"),
    ],
)
def test_bad_responses_name_their_error(text: str, fragment: str) -> None:
    result = parse_response(text, num_actions=2)
    assert not result.ok
    assert result.error is not None and fragment in result.error


def test_reasoning_survives_a_bad_action() -> None:
    """A reply whose reasoning is readable but whose index is not still logs the
    reasoning — it is evidence about the failure."""
    result = parse_response('{"action": 99, "reasoning": "I want to call"}', 2)
    assert not result.ok and result.reasoning == "I want to call"


def test_retry_then_success_is_not_a_fallback() -> None:
    """One bad reply, one good: the agent recovers and the decision is NOT
    counted as a fallback."""
    provider = FakeProvider(replies=["nonsense", '{"action": 1, "reasoning": "ok"}'])
    agent = LLMAgent(provider=provider, seed=0)
    action = agent.choose(VIEW)
    trace = agent.pop_trace()
    assert action == 55
    assert trace["fallback"] is False
    assert len(trace["attempts"]) == 2
    assert trace["attempts"][0]["error"] is not None


def test_two_bad_replies_fall_back_to_random() -> None:
    provider = FakeProvider(replies=["nonsense"])
    agent = LLMAgent(provider=provider, seed=0)
    action = agent.choose(VIEW)
    trace = agent.pop_trace()
    assert action in VIEW.legal_actions
    assert trace["fallback"] is True
    assert provider.usage.calls == 2, "the policy is exactly one retry"


def test_retry_prompt_carries_the_error_and_keeps_the_original() -> None:
    provider = FakeProvider(replies=["nonsense", '{"action": 0, "reasoning": ""}'])
    agent = LLMAgent(provider=provider, seed=0)
    agent.choose(VIEW)
    first, second = provider.prompts
    assert second.startswith(first), "the retry must repeat the original prompt"
    assert "could not be used" in second


def test_pop_trace_is_consumed_once() -> None:
    provider = FakeProvider(replies=['{"action": 0, "reasoning": ""}'])
    agent = LLMAgent(provider=provider, seed=0)
    agent.choose(VIEW)
    assert agent.pop_trace()["chosen_index"] == 0
    assert agent.pop_trace() == {}, "a stale trace would be attached to the next decision"
