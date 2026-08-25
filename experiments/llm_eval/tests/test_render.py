"""The rendered arm: what keeps a re-rendering from becoming an interpretation.

The rendered arm carries the same leak-freeness guarantee as the raw one — both
are pure functions of the information-state string — but only if the rendering
adds nothing and loses nothing. That is not something to take on trust from the
author of the renderer, so it is pinned three ways:

- ROUND-TRIP, over states drawn from real games: `recover()` must reproduce
  exactly what `infostate.parse` reads from the raw string.
- NO STRATEGY: the output may not contain evaluative vocabulary. Formatting help
  is in scope; advice would silently become part of the measured policy.
- PURITY: same bytes in, same bytes out, and indistinguishable states still
  produce indistinguishable prompts.
"""

from __future__ import annotations

from typing import Any

import pytest

from .. import infostate as istate
from ..agents import DecisionView, LLMAgent, RandomAgent, RuleAgent
from ..prompts import (
    RESPONSE_ARMS,
    RESPONSE_TEXT,
    RULES_RAW,
    RULES_RENDERED,
    build_prompt,
)
from ..providers import FakeProvider
from ..render import RANK_PLURAL, recover, render_state

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")


@pytest.fixture(scope="module")
def states() -> list[str]:
    """Information states from real games — every decision shape, both window
    states, early and late logs."""
    from ..referee import load_game, play_game, replay_views

    game = load_game("cardlang_cheat")
    out: list[str] = []
    for seed in range(4):
        seats: dict[int, Any] = {p: RandomAgent(seed=seed * 10 + p) for p in range(4)}
        seats[0] = RuleAgent(seed=seed, challenge_prob=0.3, bluff_prob=0.4)
        rec = play_game(game, seats, seed=seed, matchup="r", game_index=0, max_decisions=140)
        out.extend(v.infostate for v in replay_views(game, rec.seed, rec.history))
    assert len(out) > 300
    return out


def test_round_trip_preserves_every_fact(states: list[str]) -> None:
    """THE pin. For every real state, the English must carry exactly what the
    raw string does — no fact added, none lost."""
    seen_open = seen_closed = 0
    for raw in states:
        info = istate.parse(raw)
        got = recover(render_state(raw))
        assert got["player"] == info.player
        assert got["hand"] == info.hand
        assert got["claim_rank"] == info.claim_rank
        assert got["claim_count"] == info.claim_count
        assert got["claimant"] == info.claimant
        assert got["window_open"] == (info.state["window_open"] == "True")
        raw_responder = info.state["responder"]
        assert got["responder"] == (
            None if raw_responder == "None" else int(raw_responder)
        )
        assert got["pile"] == info.zones["pile"]
        assert got["played"] == info.zones["played"]
        assert got["deck"] == info.zones["deck"]
        assert got["flipped"] == info.zones["flipped"]
        assert got["obs"] == info.obs, "the event log must pass through unchanged"
        for seat in range(4):
            assert got["hand_sizes"][seat] == info.hand_size(seat)  # type: ignore[index]
        won = sorted(
            int(s) for s in ("0", "1", "2", "3") if f"{s}:True" in info.state["won"]
        )
        assert got["won"] == won
        seen_open += got["window_open"] is True
        seen_closed += got["window_open"] is False
    assert seen_open > 20 and seen_closed > 20, (
        "the corpus of states did not exercise both window states — the "
        "context-sensitive branch is the whole point of this arm"
    )


def test_rendering_states_no_strategy(states: list[str]) -> None:
    """A rendering describes; it must not advise. Evaluative vocabulary would
    become part of the policy being measured."""
    banned = (
        "should", "safe", "risky", "risk", "better", "best", "advantage",
        "recommend", "consider", "likely", "probably", "suspicious", "bluff",
        "honest", "wise", "avoid", "prefer",
    )
    for raw in states[:120]:
        text = render_state(raw).lower()
        # The event log passes through verbatim and is not the renderer's prose.
        prose = text.split("your complete event log")[0]
        for word in banned:
            assert word not in prose, f"renderer prose contains advice word {word!r}"


def test_render_is_deterministic_and_pure(states: list[str]) -> None:
    for raw in states[:40]:
        assert render_state(raw) == render_state(raw)


def test_indistinguishable_states_render_identically() -> None:
    """The property the whole guarantee rests on, at this layer: the rendering
    is a function of the info-state alone, so equal states render equally and
    different ones do not collapse together."""
    a = (
        "P1|deck=#0;flipped=[];pile=#3;played=#2;hand[0]=#12;hand[1]=[A♠,2♥,K♣];"
        "hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;claim_count=2;"
        "claim_rank=9;claimant=0;responder=1;window_open=True;"
        "won={0:False,1:False,2:False,3:False}|obs:('announce', 0, 'play_two')"
    )
    b = a.replace("hand[1]=[A♠,2♥,K♣]", "hand[1]=[A♠,2♥,K♦]")
    assert render_state(a) == render_state(a)
    assert render_state(a) != render_state(b)
    assert build_prompt(RULES_RENDERED, render_state(a), ["allow", "call_cheat"]) != \
        build_prompt(RULES_RENDERED, render_state(b), ["allow", "call_cheat"])


def test_each_decision_context_is_named() -> None:
    """Three moments share the `state:` vocabulary, and the rendering says
    which one the reader is in.

    `claim_rank` is the cycle's position at all three, which is what a reader
    taking the record as one moment gets wrong: it names the standing play's
    call while a play stands, and the reader's OWN required call between
    plays. The other fields distinguish the moments rather than describing a
    play that has already resolved.
    """
    zones = (
        "P0|deck=#0;flipped=[];pile=#4;played=#0;hand[0]=[9♣,9♥,Q♠];hand[1]=#11;"
        "hand[2]=#16;hand[3]=#13|state:"
    )
    won = ";won={0:False,1:False,2:False,3:False}|obs:('announce', 3, 'play_two')"

    announce = render_state(
        zones + "challenged=False;challenger=None;claim_count=0;claim_rank=9;"
        "claimant=None;responder=None;window_open=False" + won
    )
    assert "it is your play. You must call your cards as Nines." in announce
    assert "No play stands" in announce

    picking = render_state(
        zones.replace("played=#0", "played=#1")
        + "challenged=False;challenger=None;claim_count=2;claim_rank=9;"
        "claimant=0;responder=None;window_open=False" + won
    )
    assert "seat 0 has announced 2 cards as Nines and is choosing" in picking

    window = render_state(
        zones.replace("played=#0", "played=#2")
        + "challenged=False;challenger=None;claim_count=2;claim_rank=9;"
        "claimant=3;responder=0;window_open=True" + won
    )
    assert "seat 3 has played 2 cards face down, claiming they are Nines" in window

    for text, claimant, count in ((announce, None, 0), (picking, 0, 2), (window, 3, 2)):
        got = recover(text)
        assert got["claim_rank"] == "9"
        assert got["claimant"] == claimant and got["claim_count"] == count


@pytest.mark.parametrize(
    ("field", "value"),
    [("challenged", "True"), ("challenger", "1"), ("responder", "0")],
)
def test_a_state_carrying_assumed_bookkeeping_is_refused(field: str, value: str) -> None:
    """The three fields the rendering states by assumption, one probe each.

    `challenged`/`challenger` are set only between a call and its
    adjudication, where nobody is asked to decide; `responder` is a cursor
    only an open window has. None reaches a prompt, so `recover` reads them
    off the prose shape — and a state that contradicts the assumption would
    lose the field silently, which is why it refuses instead.
    """
    raw = (
        "P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[9♣];hand[1]=#11;"
        "hand[2]=#16;hand[3]=#13|state:challenged=False;challenger=None;"
        "claim_count=0;claim_rank=9;claimant=None;responder=None;"
        "window_open=False;won={0:False,1:False,2:False,3:False}"
        "|obs:('announce', 3, 'play_two')"
    ).replace(f"{field}=" + {"challenged": "False", "challenger": "None", "responder": "None"}[field],
              f"{field}={value}")
    with pytest.raises(ValueError, match="no decision point in Cheat exhibits"):
        render_state(raw)


def test_open_window_names_the_claimant_and_rank() -> None:
    raw = (
        "P1|deck=#0;flipped=[];pile=#5;played=#3;hand[0]=#12;hand[1]=[A♠,2♥];"
        "hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;claim_count=3;"
        "claim_rank=K;claimant=0;responder=1;window_open=True;"
        "won={0:False,1:False,2:False,3:False}|obs:('announce', 0, 'play_three')"
    )
    text = render_state(raw)
    assert 'seat 0 has played 3 cards face down, claiming they are Kings' in text
    assert 'whether to call "Cheat!"' in text


def test_unknown_state_vocabulary_raises() -> None:
    """Closed-domain completeness: a field the renderer does not know is a fact
    it would silently drop from the prompt."""
    raw = (
        "P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[9♣]|state:challenged=False;"
        "challenger=None;claim_count=1;claim_rank=9;claimant=0;responder=0;"
        "window_open=False;won={0:False};mystery=7|obs:"
    )
    with pytest.raises(ValueError, match="unknown="):
        render_state(raw)


def test_missing_state_vocabulary_raises() -> None:
    raw = (
        "P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[9♣]|state:challenged=False;"
        "claim_count=1;claim_rank=9;claimant=0;responder=0;window_open=False;"
        "won={0:False}|obs:"
    )
    with pytest.raises(ValueError, match="missing="):
        render_state(raw)


def test_every_rank_has_a_plural_name() -> None:
    assert set(RANK_PLURAL) == set(istate.RANKS)


def test_rendered_arm_prompt_is_shorter(states: list[str]) -> None:
    """The mechanism behind the hypothesis: rendering the state lets most of the
    format guide go, so the arm is cheaper as well as clearer."""
    legal = ["allow", "call_cheat"]
    assert len(RULES_RENDERED) < len(RULES_RAW)
    shorter = sum(
        len(build_prompt(RULES_RENDERED, render_state(s), legal))
        < len(build_prompt(RULES_RAW, s, legal))
        for s in states[:80]
    )
    assert shorter >= 60, f"only {shorter}/80 rendered prompts were shorter"


def test_agent_arm_switch_selects_the_right_prompt() -> None:
    view = DecisionView(
        player=1,
        infostate=(
            "P1|deck=#0;flipped=[];pile=#0;played=#2;hand[0]=#12;hand[1]=[A♠,2♥];"
            "hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;"
            "claim_count=2;claim_rank=A;claimant=0;responder=1;window_open=True;"
            "won={0:False,1:False,2:False,3:False}|obs:('announce', 0, 'play_two')"
        ),
        legal_actions=[54, 55],
        legal_strings=["allow", "call_cheat"],
    )
    reply = '{"action": 0, "reasoning": "x"}'

    raw_provider = FakeProvider(replies=[reply])
    LLMAgent(provider=raw_provider, seed=0, render=False).choose(view)
    rendered_provider = FakeProvider(replies=[reply])
    LLMAgent(provider=rendered_provider, seed=0, render=True).choose(view)

    assert view.infostate in raw_provider.prompts[0]
    assert view.infostate not in rendered_provider.prompts[0]
    assert "You are seat 1" in rendered_provider.prompts[0]
    assert "claiming they are Aces" in rendered_provider.prompts[0]
    assert len(rendered_provider.prompts[0]) < len(raw_provider.prompts[0])


# --- the response-format arms -----------------------------------------------
#
# Parametrized over `RESPONSE_ARMS` rather than naming the arms, and asserting
# PROPERTIES rather than the text. Naming them is the trap this suite has already
# been caught by once (see `test_build_prompt_signature_takes_no_state`): a test
# that enumerates the current arms makes adding the next one look like a
# violation, which is how an experimental variable gets frozen by its own pin.

ARM_NAMES = sorted(RESPONSE_ARMS)
# The closed set of reply keys any arm may ask for. Derived, so an arm
# introducing a new key has to come past this line deliberately.
ALL_KEYS = {key for arm in RESPONSE_ARMS.values() for key in arm.keys}

INFO_WINDOW = (
    "P1|deck=#0;flipped=[];pile=#0;played=#2;hand[0]=#12;hand[1]=[A♠,2♥];"
    "hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;"
    "claim_count=2;claim_rank=A;claimant=0;responder=1;window_open=True;"
    "won={0:False,1:False,2:False,3:False}|obs:('announce', 0, 'play_two')"
)


def test_the_arm_registry_is_self_consistent() -> None:
    """Registry key and `arm.name` agree — otherwise a run records one arm's name
    while sending another's instruction, and the transcript lies."""
    assert ARM_NAMES, "the arm registry is empty — every test below is vacuous"
    for key, arm in RESPONSE_ARMS.items():
        assert key == arm.name


@pytest.mark.parametrize("name", ARM_NAMES)
def test_arm_instruction_asks_for_exactly_its_keys_in_order(name: str) -> None:
    """The instruction's JSON template must show precisely `arm.keys`, in that
    order. `keys` is what the audit and the retry note are derived from, so a
    template that disagrees with it silently mislabels the arm.

    Quoted form (`"action"`) targets the template; the prose refers to fields in
    backticks, so it does not perturb the positions compared here.
    """
    arm = RESPONSE_ARMS[name]
    positions = [arm.instruction.find(f'"{key}"') for key in arm.keys]
    assert all(p >= 0 for p in positions), (
        f"arm {name!r} declares keys {arm.keys} but its instruction does not "
        f"show them all in its JSON template"
    )
    assert positions == sorted(positions), (
        f"arm {name!r} declares key order {arm.keys}, but its instruction shows "
        f"them in a different order — the order IS the manipulation"
    )
    for absent in ALL_KEYS - set(arm.keys):
        assert f'"{absent}"' not in arm.instruction, (
            f"arm {name!r} does not declare key {absent!r} but asks for it"
        )


@pytest.mark.parametrize("name", ARM_NAMES)
def test_arm_retry_note_agrees_with_its_instruction(name: str) -> None:
    """The retry note must ask for the same keys in the same order.

    This is the confound the neutral arm shipped with: its retry note asked for
    the `reasoning` field the arm existed to remove, and at 1.85 calls per
    decision roughly 46% of its decisions were shown that note. A retry note is
    not cosmetic — it is the prompt that produced a large minority of the arm's
    actual decisions.
    """
    arm = RESPONSE_ARMS[name]
    assert "{error}" in arm.retry, f"arm {name!r} cannot report the parse error"
    filled = arm.retry.format(error="test")
    assert "{" in filled and "}" in filled, (
        f"arm {name!r} lost its JSON braces to `.format` — they must be doubled"
    )
    positions = [filled.find(f'"{key}"') for key in arm.keys]
    assert all(p >= 0 for p in positions), (
        f"arm {name!r} retry note omits one of its keys {arm.keys}"
    )
    assert positions == sorted(positions), (
        f"arm {name!r} retry note shows its keys in a different order from its "
        f"instruction — the retry would revert the variable under test"
    )
    for absent in ALL_KEYS - set(arm.keys):
        assert f'"{absent}"' not in filled, (
            f"arm {name!r} retry note asks for undeclared key {absent!r} — the "
            f"retry reintroduces what the arm removed"
        )


@pytest.mark.parametrize("name", ARM_NAMES)
def test_arm_changes_only_the_response_instruction(name: str) -> None:
    """Everything before HOW TO ANSWER is byte-identical across arms, or the
    comparison measures more than the response format."""
    legal = ["allow", "call_cheat"]
    state = render_state(INFO_WINDOW)
    head = "HOW TO ANSWER"
    baseline = build_prompt(RULES_RENDERED, state, legal, RESPONSE_TEXT)
    other = build_prompt(RULES_RENDERED, state, legal, RESPONSE_ARMS[name].instruction)
    assert baseline[: baseline.index(head)] == other[: other.index(head)]
    # And the arms are actually distinct, or the grid is comparing a constant.
    if name != "reasoning":
        assert baseline != other


@pytest.mark.parametrize("name", ARM_NAMES)
def test_agent_sends_its_own_arms_instruction(name: str) -> None:
    """The arm reaches the provider. A selector that resolved to the default
    would produce a complete, plausible, expensive run of the control under the
    arm's name — the worst failure this harness can have."""
    view = DecisionView(
        player=1,
        infostate=INFO_WINDOW,
        legal_actions=[54, 55],
        legal_strings=["allow", "call_cheat"],
    )
    arm = RESPONSE_ARMS[name]
    provider = FakeProvider(replies=['{"action": 1, "reasoning": "x"}'])
    agent = LLMAgent(provider=provider, seed=0, render=True, arm=name)
    assert agent.choose(view) == 55
    assert arm.instruction in provider.prompts[0]
    for absent in ALL_KEYS - set(arm.keys):
        assert absent not in provider.prompts[0].split("HOW TO ANSWER")[1]


@pytest.mark.parametrize("name", ARM_NAMES)
def test_agent_retry_uses_its_own_arms_note(name: str) -> None:
    """A failed parse must retry in the arm's own format. Checked through the
    agent, not against the constant: the note is only load-bearing if the retry
    path actually reaches for it."""
    view = DecisionView(
        player=1,
        infostate=INFO_WINDOW,
        legal_actions=[54, 55],
        legal_strings=["allow", "call_cheat"],
    )
    arm = RESPONSE_ARMS[name]
    provider = FakeProvider(replies=["not json at all", '{"action": 0}'])
    agent = LLMAgent(provider=provider, seed=0, render=True, arm=name)
    assert agent.choose(view) == 54
    assert len(provider.prompts) == 2, "the retry never happened"
    tail = provider.prompts[1][len(provider.prompts[0]) :]
    assert tail == arm.retry.format(error="no JSON object in response")


def test_an_unknown_arm_is_refused_at_construction() -> None:
    """Loud, and before the run spends: an ignored arm name would complete a
    multi-hour run and report the control's numbers under the arm's name."""
    with pytest.raises(ValueError, match="unknown response arm"):
        LLMAgent(provider=FakeProvider(replies=[]), seed=0, arm="reason-first")


def test_reason_first_is_invisible_to_the_parser() -> None:
    """Why `verify.py --order` exists. `json.loads` discards key order, so the
    reason-first arm and the default parse to the SAME result — the manipulation
    lives entirely in what the model generated first, which can only be measured
    against the raw reply text.

    If this ever fails, the audit is redundant and should be simplified. While it
    passes, a behavioural comparison between the two arms is unfalsifiable
    without the raw-text check.
    """
    from ..prompts import parse_response

    last = parse_response('{"action": 1, "reasoning": "because"}', num_actions=2)
    first = parse_response('{"reasoning": "because", "action": 1}', num_actions=2)
    assert last == first


def test_a_reply_without_reasoning_parses_and_is_not_a_fallback() -> None:
    """The neutral arm's replies carry no `reasoning` key; that is the expected
    shape, not a malformed response, and must not inflate the fallback rate."""
    from ..prompts import parse_response

    result = parse_response('{"action": 1}', num_actions=2)
    assert result.ok and result.index == 1 and result.reasoning == ""


# The committed config's arm names are checked in `test_runner.py`, beside the
# other shipped-config pin.
