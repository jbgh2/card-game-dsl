"""The treatment record covers the code that builds the prompt, not only the config.

A resume refuses to append when the treatment changed, so that two experiments
are never aggregated as one matchup — the worst failure this rig has, because
the resulting number still looks fine. The record is `treatment()`'s dict,
written beside every transcript. Its config half is the roster and the knobs;
its prompt half is `agents.prompt_fingerprint`, a digest of everything static
the model is shown for one (game, arm, render) shape.

Grid
----
Axes, derived from the registries that define them: `game` from `GAME_TEXT`,
`render` over its two arms, `arm` from `RESPONSE_ARMS`. Components per cell:

- `prompt`: the decision prompt for a fixed probe state — covers
  `build_prompt`'s scaffolding, the game's rules text for the arm, and the
  arm's instruction;
- `retry`: the arm's retry note for a fixed probe error;
- `renderer`: the source of the module defining the rendered arm's renderer;
  `None` when the raw arm is in use or the game has no rendered arm.

Each present component is proven to redden under a mutation of exactly the
input it names and no other, so the fingerprint can neither miss an input
nor conflate two.

does not prove: the wording of a parse error, which rides inside a retry and
  comes from `parse_response`; the baseline agents' policy code; the engine's
  rules and action strings; the provider's request shape beyond `params`,
  which the config half already records.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from .. import agents, prompts
from ..agents import GAME_TEXT, prompt_fingerprint
from ..prompts import RESPONSE_ARMS

GAMES = sorted(GAME_TEXT)
ARMS = sorted(RESPONSE_ARMS)
RENDER = (False, True)
COMPONENTS = ("prompt", "retry", "renderer")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_the_fingerprint_has_exactly_the_components_the_shape_uses(
    game: str, render: bool, arm: str
) -> None:
    """One key per component, and the renderer digest is present exactly when a
    renderer shapes the prompt: the rendered arm of a game that has one."""
    fp = prompt_fingerprint(game, render, arm)
    assert set(fp) == set(COMPONENTS)
    renderer = GAME_TEXT[game][2]
    if render and renderer is not None:
        module = inspect.getmodule(renderer)
        assert module is not None
        assert fp["renderer"] == _sha(inspect.getsource(module))
    else:
        assert fp["renderer"] is None
    assert fp["prompt"] and fp["retry"]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_a_changed_rules_text_moves_only_the_prompt_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = prompt_fingerprint(game, render, arm)
    raw, rendered, renderer = GAME_TEXT[game]
    changed = (raw, rendered + "\nx", renderer) if render else (raw + "\nx", rendered, renderer)
    monkeypatch.setitem(GAME_TEXT, game, changed)
    after = prompt_fingerprint(game, render, arm)
    assert after["prompt"] != before["prompt"]
    assert after["retry"] == before["retry"]
    assert after["renderer"] == before["renderer"]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_the_other_arm_of_the_rules_text_is_not_in_the_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing the format guide of the arm NOT in use must not block a resume:
    the fingerprint is what this shape shows, not the module's whole text."""
    before = prompt_fingerprint(game, render, arm)
    raw, rendered, renderer = GAME_TEXT[game]
    other = (raw + "\nx", rendered, renderer) if render else (raw, rendered + "\nx", renderer)
    monkeypatch.setitem(GAME_TEXT, game, other)
    assert prompt_fingerprint(game, render, arm) == before


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_a_changed_instruction_moves_only_the_prompt_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = prompt_fingerprint(game, render, arm)
    spec = RESPONSE_ARMS[arm]
    monkeypatch.setitem(
        RESPONSE_ARMS, arm, replace(spec, instruction=spec.instruction + "\nx")
    )
    after = prompt_fingerprint(game, render, arm)
    assert after["prompt"] != before["prompt"]
    assert after["retry"] == before["retry"]
    assert after["renderer"] == before["renderer"]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_a_changed_retry_note_moves_only_the_retry_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = prompt_fingerprint(game, render, arm)
    spec = RESPONSE_ARMS[arm]
    monkeypatch.setitem(RESPONSE_ARMS, arm, replace(spec, retry=spec.retry + "\nx"))
    after = prompt_fingerprint(game, render, arm)
    assert after["retry"] != before["retry"]
    assert after["prompt"] == before["prompt"]
    assert after["renderer"] == before["renderer"]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_changed_prompt_scaffolding_moves_only_the_prompt_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`build_prompt`'s own framing lines are part of what the model is shown
    and live in no constant; the digest goes through the function itself."""
    before = prompt_fingerprint(game, render, arm)
    original = prompts.build_prompt

    def framed(*args: Any, **kwargs: Any) -> str:
        return original(*args, **kwargs) + "\nx"

    monkeypatch.setattr(agents, "build_prompt", framed)
    after = prompt_fingerprint(game, render, arm)
    assert after["prompt"] != before["prompt"]
    assert after["retry"] == before["retry"]
    assert after["renderer"] == before["renderer"]


def test_an_unknown_arm_or_game_is_refused_before_any_digest() -> None:
    with pytest.raises(ValueError, match="unknown response arm"):
        prompt_fingerprint("cheat", False, "no-such-arm")
    with pytest.raises(ValueError, match="unknown game"):
        prompt_fingerprint("no-such-game", False, "reasoning")


def test_the_agent_and_the_fingerprint_read_one_prompt_shape() -> None:
    """The agent's rules text and renderer come from the same lookup the
    fingerprint digests, so the two cannot disagree about a shape."""
    from ..providers import FakeProvider

    for game in GAMES:
        for render in RENDER:
            agent = agents.LLMAgent(
                provider=FakeProvider(replies=["{}"]), seed=0, render=render, game=game
            )
            rules, renderer, arm = agents.prompt_shape(game, render, "reasoning")
            assert agent.rules == rules
            assert arm is agent._arm
            assert renderer is None or agent._render is renderer
            if renderer is None:
                assert agent._render("probe") == "probe"


# --- the resume gate, end to end ---------------------------------------------

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

from ..run_eval import main, read_treatment  # noqa: E402

FAKE_MODEL: dict[str, Any] = {
    "kind": "fake",
    "model": "fake",
    "replies": ['{"action": 0, "reasoning": "x"}'],
}


def _spec(tmp_path: Path, **matchup: Any) -> dict[str, Any]:
    return {
        "game": "cardlang_cheat",
        "max_decisions": 200,
        "results_dir": str(tmp_path),
        "models": {"m": FAKE_MODEL},
        "matchups": [
            {
                "name": "llm",
                "n": 1,
                "rotate": True,
                "agents": [{"kind": "llm", "model": "m", "arm": "reasoning"}]
                + [{"kind": "random"}] * 3,
                **matchup,
            }
        ],
    }


def _write(path: Path, spec: dict[str, Any]) -> Path:
    import yaml

    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


def _first_run(tmp_path: Path) -> tuple[Path, dict[str, Any], Path]:
    target = tmp_path / "run-a"
    spec = _spec(tmp_path)
    config = _write(tmp_path / "c.yaml", spec)
    assert main(["--config", str(config), "--run-dir", str(target)]) == 0
    spec["matchups"][0]["n"] = 2
    spec["matchups"][0]["resume_from"] = 1
    _write(config, spec)
    return target, spec, config


def _sidecar(target: Path) -> Path:
    return target / "transcripts" / "llm.treatment.json"


def _resume(config: Path, target: Path, *flags: str) -> int:
    return main(["--config", str(config), "--run-dir", str(target), *flags])


def test_the_record_carries_a_prompt_fingerprint_per_llm_shape(tmp_path: Path) -> None:
    target, _, _ = _first_run(tmp_path)
    recorded = read_treatment(_sidecar(target))
    assert recorded is not None
    assert recorded["prompt"] == {
        "cheat:raw:reasoning": prompt_fingerprint("cheat", False, "reasoning")
    }


def test_an_all_baseline_roster_records_no_prompt_shape(tmp_path: Path) -> None:
    """No model is shown anything, so there is nothing to fingerprint — and an
    empty block rather than an absent key, so a reader can tell "no LLM" from
    a record that lacks the block."""
    target = tmp_path / "run-a"
    spec = _spec(tmp_path, agents=[{"kind": "rule"}] + [{"kind": "random"}] * 3)
    config = _write(tmp_path / "c.yaml", spec)
    assert main(["--config", str(config), "--run-dir", str(target)]) == 0
    recorded = read_treatment(_sidecar(target))
    assert recorded is not None and recorded["prompt"] == {}


def test_resume_refuses_a_changed_instruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect: seeds match, config matches, and the model is shown different
    text. The refusal names the component that moved, not just "prompt"."""
    target, _, config = _first_run(tmp_path)
    spec = RESPONSE_ARMS["reasoning"]
    monkeypatch.setitem(
        RESPONSE_ARMS, "reasoning", replace(spec, instruction=spec.instruction + "\nx")
    )
    with pytest.raises(ValueError, match=r"prompt\.cheat:raw:reasoning\.prompt"):
        _resume(config, target)


def test_resume_refuses_a_changed_retry_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, _, config = _first_run(tmp_path)
    spec = RESPONSE_ARMS["reasoning"]
    monkeypatch.setitem(RESPONSE_ARMS, "reasoning", replace(spec, retry=spec.retry + "\nx"))
    with pytest.raises(ValueError, match=r"prompt\.cheat:raw:reasoning\.retry"):
        _resume(config, target)


def test_resume_accepts_an_unchanged_llm_treatment(tmp_path: Path) -> None:
    """Non-vacuity for the prompt half: the digests are stable across
    invocations, so a legitimate resume is not refused."""
    target, _, config = _first_run(tmp_path)
    assert _resume(config, target) == 0
    from ..metrics import iter_jsonl

    records = list(iter_jsonl(str(target / "transcripts" / "llm.jsonl")))
    assert [r["seed"] for r in records] == [0, 1]


def test_a_record_with_no_prompt_block_is_refused(tmp_path: Path) -> None:
    """A sidecar without a `prompt` block is not reconstructed: nothing can say
    what those games were shown, so the resume is refused and the refusal
    names the override that accepts the gap deliberately."""
    target, _, config = _first_run(tmp_path)
    sidecar = _sidecar(target)
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    del record["prompt"]
    sidecar.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="--accept-changed-treatment") as caught:
        _resume(config, target)
    assert "prompt" in str(caught.value)


def test_the_override_resumes_and_records_itself_in_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mismatch the operator judges harmless is accepted with the flag, and
    the sidecar keeps the judgment: what differed, both values, when, and at
    which game — so the transcript never reads as one clean treatment."""
    target, _, config = _first_run(tmp_path)
    old = read_treatment(_sidecar(target))
    assert old is not None
    spec = RESPONSE_ARMS["reasoning"]
    monkeypatch.setitem(
        RESPONSE_ARMS, "reasoning", replace(spec, instruction=spec.instruction + "\nx")
    )
    assert _resume(config, target, "--accept-changed-treatment") == 0

    record = json.loads(_sidecar(target).read_text(encoding="utf-8"))
    (override,) = record["overrides"]
    path = "prompt.cheat:raw:reasoning.prompt"
    assert override["differing"] == [path]
    assert override["recorded"] == {path: old["prompt"]["cheat:raw:reasoning"]["prompt"]}
    assert override["now"] == {path: record["prompt"]["cheat:raw:reasoning"]["prompt"]}
    assert override["resumed_from"] == 1
    assert override["at"].endswith("Z")
    # The treatment half of the record is the NEW treatment: the next resume is
    # measured against what the latest games were shown.
    assert record["prompt"] == {
        "cheat:raw:reasoning": prompt_fingerprint("cheat", False, "reasoning")
    }


def test_after_an_override_an_unchanged_resume_needs_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The override record is not part of the comparison, and it is carried
    forward rather than dropped by the rewrite every invocation performs."""
    target, spec, config = _first_run(tmp_path)
    arm = RESPONSE_ARMS["reasoning"]
    monkeypatch.setitem(RESPONSE_ARMS, "reasoning", replace(arm, instruction=arm.instruction + "\nx"))
    assert _resume(config, target, "--accept-changed-treatment") == 0
    spec["matchups"][0]["n"] = 3
    spec["matchups"][0]["resume_from"] = 2
    _write(config, spec)
    assert _resume(config, target) == 0
    record = json.loads(_sidecar(target).read_text(encoding="utf-8"))
    assert len(record["overrides"]) == 1


def test_the_flag_records_nothing_when_nothing_differs(tmp_path: Path) -> None:
    target, _, config = _first_run(tmp_path)
    assert _resume(config, target, "--accept-changed-treatment") == 0
    record = json.loads(_sidecar(target).read_text(encoding="utf-8"))
    assert "overrides" not in record


def test_the_override_also_covers_the_config_half(
    tmp_path: Path,
) -> None:
    """One flag, one mechanism: a config-side change is accepted and recorded
    the same way, with its path named at the key that moved."""
    target, spec, config = _first_run(tmp_path)
    spec["matchups"][0]["agents"][1] = {"kind": "rule", "bluff_prob": 0.4}
    _write(config, spec)
    with pytest.raises(ValueError, match=r"agents"):
        _resume(config, target)
    assert _resume(config, target, "--accept-changed-treatment") == 0
    record = json.loads(_sidecar(target).read_text(encoding="utf-8"))
    (override,) = record["overrides"]
    assert override["differing"] == ["agents"]
