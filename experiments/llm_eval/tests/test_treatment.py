"""The treatment record covers the code that builds the prompt, not only the config.

A resume refuses to append when the treatment changed, so that two experiments
are never aggregated as one matchup — the worst failure this rig has, because
the resulting number still looks fine. The record is `treatment()`'s dict,
written beside every transcript. Its config half is the roster and the knobs;
its prompt half is `agents.prompt_fingerprint`, a digest of everything static
the model is shown for one (game, arm, render) shape.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a resume is refused, naming the component that moved, whenever
                 any static input to what an LLM seat is shown differs from
                 what the recorded games were shown: the rules text of the arm
                 in use, the arm's instruction, the arm's retry note, the
                 source of every rig function and class on the prompt path
                 from `LLMAgent.choose` (the builder, its callees, the
                 response parser whose wording rides inside a retry), or the
                 source of the renderer's module and of every rig module it
                 delegates to. A matching
                 fingerprint is stable across invocations, so a legitimate
                 resume is not refused; a sidecar with no `prompt` block is
                 refused rather than reconstructed; and the override that
                 accepts a difference records what differed, both values, when
                 and at which game, carried across every later rewrite and
                 excluded from every later comparison.
domain:          `GAME_TEXT` x {raw, rendered} x `RESPONSE_ARMS`, each cell
                 crossed with the components the shape uses (`prompt`,
                 `retry`, `builder`, `renderer`) and, per present component,
                 with a mutation of exactly the input it names — proving the
                 component moves under that input and no other. The builder
                 and renderer rows mutate real source through the registry
                 and the module globals, since a registry-level row cannot
                 see a source file; the builder's witness is a branch the
                 probe never reaches. The resume
                 gate is then exercised end to end through `main()` on the
                 raw and rendered shapes, with the fake provider.
registry:        agents.py::GAME_TEXT (the game axis and each game's renderer);
                 prompts.py::RESPONSE_ARMS (the arm axis); the component set
                 is no registry — it is pinned by set-equality against
                 `prompt_fingerprint`'s own keys, so a fourth component
                 reddens rather than going stale;
                 agents.py::rig_closure (the renderer's transitive rig
                 modules, derived from module globals);
                 agents.py::code_closure (the prompt path's transitive rig
                 functions and classes, derived from code-object names);
                 agents.py::DEFAULT_RENDER / DEFAULT_ARM (the shape an entry
                 takes when it says nothing, read by `llm_shape` and by
                 `LLMAgent`'s defaults alike);
                 run_eval.py::SIDECAR_ONLY (the keys outside the comparison).
does not prove:  the baseline agents' policy code; the engine's rules and
                 action strings; the provider's hard-coded request defaults
                 and its single-user-turn message shape (its `params` are in
                 the config half). Two over-refusals, accepted with the flag
                 and never a miss: where a game's module holds both its rules
                 texts and its renderer (`kuhn.py`), the renderer digest also
                 moves under an edit to the raw arm's text; and the builder
                 digest moves under any edit to `LLMAgent.choose` or its
                 callees, the trace bookkeeping included. Each source is
                 digested once per
                 process from what the process loaded, so an edit to a file
                 during a run is invisible until the next process — by
                 design, and a row below pins it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from .. import agents, infostate, prompts, render
from ..agents import (
    GAME_TEXT,
    builder_digest,
    code_closure,
    prompt_fingerprint,
    renderer_digest,
    rig_closure,
    rig_name,
)
from ..prompts import RESPONSE_ARMS

GAMES = sorted(GAME_TEXT)
ARMS = sorted(RESPONSE_ARMS)
RENDER = (False, True)
COMPONENTS = ("prompt", "retry", "builder", "renderer")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _only_moved(before: dict[str, str | None], after: dict[str, str | None], *moved: str) -> None:
    """Exactly the named components differ; every other one is unchanged."""
    for component in COMPONENTS:
        if component in moved:
            assert after[component] != before[component], component
        else:
            assert after[component] == before[component], component


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str) -> ModuleType:
    """A rig-package module from a temp file, so a renderer's SOURCE can be a
    test input. Registered under the rig package name, because that is what
    makes it a member of a renderer's closure."""
    path = tmp_path / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    full = f"{agents.RIG_PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(full, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full, module)
    spec.loader.exec_module(module)
    return module


RENDERER_A = "def render_state(s: str) -> str:\n    return s + ' a'\n"
RENDERER_B = "def render_state(s: str) -> str:\n    return s + ' b'\n"
RENDERER_DELEGATING = (
    f"from {agents.RIG_PACKAGE} import infostate\n"
    "def render_state(s: str) -> str:\n    return str(infostate.parse(s))\n"
)
# A builder the probe cannot tell from the real one: the extra framing fires
# only past two legal actions, and the probe offers exactly two.
BUILDER_BRANCHING = (
    f"from {agents.RIG_PACKAGE}.prompts import build_prompt as _real\n"
    "def build_prompt(rules: str, infostate: str, legal_actions: list[str], response: str) -> str:\n"
    "    text = _real(rules, infostate, legal_actions, response)\n"
    "    if len(legal_actions) > 2:\n"
    "        text += '\\nChoose carefully.'\n"
    "    return text\n"
)


# --- the grid ----------------------------------------------------------------


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
        assert fp["renderer"] == renderer_digest(renderer)
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
    _only_moved(before, prompt_fingerprint(game, render, arm), "prompt")


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_the_other_arm_of_the_rules_text_is_not_in_the_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the registry, the fingerprint is what THIS shape shows: the
    other arm's text moving in `GAME_TEXT` changes nothing. (A source edit to
    a module that holds both texts and the renderer is the over-refusal the
    ledger names; this row is the registry-level claim only.)"""
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
    _only_moved(before, prompt_fingerprint(game, render, arm), "prompt")


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_a_changed_retry_note_moves_only_the_retry_digest(
    game: str, render: bool, arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = prompt_fingerprint(game, render, arm)
    spec = RESPONSE_ARMS[arm]
    monkeypatch.setitem(RESPONSE_ARMS, arm, replace(spec, retry=spec.retry + "\nx"))
    _only_moved(before, prompt_fingerprint(game, render, arm), "retry")


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_changed_prompt_scaffolding_moves_the_prompt_and_builder_digests(
    game: str, render: bool, arm: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`build_prompt`'s own framing lines are part of what the model is shown
    and live in no constant: a builder whose framing differs moves the
    composed prompt, and being code on the prompt path, the builder digest."""
    before = prompt_fingerprint(game, render, arm)
    framed = _load(
        tmp_path,
        monkeypatch,
        "probe_builder_framed",
        f"from {agents.RIG_PACKAGE}.prompts import build_prompt as _real\n"
        "def build_prompt(*args, **kwargs):\n    return _real(*args, **kwargs) + '\\nx'\n",
    )
    monkeypatch.setattr(agents, "build_prompt", framed.build_prompt)
    _only_moved(before, prompt_fingerprint(game, render, arm), "prompt", "builder")


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("render", RENDER, ids=("raw", "rendered"))
@pytest.mark.parametrize("game", GAMES)
def test_a_builder_branch_the_probe_never_reaches_moves_only_the_builder_digest(
    game: str, render: bool, arm: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row the probe alone cannot hold: a builder that frames the prompt
    differently only past two legal actions composes the probe byte-for-byte
    as before, so `prompt` holds — and the builder digest, being source,
    moves. This is what keeps a code edit on the prompt path from resuming."""
    before = prompt_fingerprint(game, render, arm)
    branching = _load(tmp_path, monkeypatch, "probe_builder_branching", BUILDER_BRANCHING)
    monkeypatch.setattr(agents, "build_prompt", branching.build_prompt)
    _only_moved(before, prompt_fingerprint(game, render, arm), "builder")


def test_the_builder_closure_is_the_prompt_path_from_choose() -> None:
    """Derived from code-object names, so the response parser (whose error
    wording rides inside a retry) and the builder are both inside, and a
    helper a future edit introduces on the path joins without being listed."""
    names = {f"{rig_name(sys.modules[o.__module__])}.{o.__qualname__}" for o in code_closure(agents.LLMAgent.choose)}
    assert {"agents.LLMAgent.choose", "prompts.build_prompt", "prompts.parse_response"} <= names
    assert builder_digest() == builder_digest()


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("game", GAMES)
def test_a_changed_renderer_source_moves_only_the_renderer_digest(
    game: str, arm: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The renderer row proper: two renderers differing only in source give
    the rendered shape two renderer digests and one prompt and retry digest.
    Run for every game's rendered arm, so a game with no renderer of its own
    is proven to take one through the registry like any other."""
    raw, rendered, _ = GAME_TEXT[game]
    a = _load(tmp_path, monkeypatch, "probe_renderer_a", RENDERER_A)
    b = _load(tmp_path, monkeypatch, "probe_renderer_b", RENDERER_B)
    monkeypatch.setitem(GAME_TEXT, game, (raw, rendered, a.render_state))
    with_a = prompt_fingerprint(game, True, arm)
    monkeypatch.setitem(GAME_TEXT, game, (raw, rendered, b.render_state))
    with_b = prompt_fingerprint(game, True, arm)
    _only_moved(with_a, with_b, "renderer")
    assert with_a["renderer"] is not None and with_b["renderer"] is not None


def test_the_renderer_digest_covers_the_modules_the_renderer_delegates_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renderer that builds its sentences from a sibling module is shaped by
    that module's source; the closure is derived from the globals, not listed.
    Cheat's own renderer is the corpus case: `render.render_state` parses
    through `infostate`."""
    assert rig_closure(render) == [infostate, render]
    delegating = _load(tmp_path, monkeypatch, "probe_renderer_c", RENDERER_DELEGATING)
    alone = _load(tmp_path, monkeypatch, "probe_renderer_a", RENDERER_A)
    both = sorted((delegating, infostate), key=lambda m: m.__name__)
    assert rig_closure(delegating) == both
    assert rig_closure(alone) == [alone]
    assert renderer_digest(delegating.render_state) == _sha(
        "\n".join(f"{rig_name(m)} {_sha(inspect.getsource(m))}" for m in both)
    )
    # Relative names, so the record is the same under either package spelling.
    assert rig_name(infostate) == "infostate"


def test_the_renderer_digest_is_of_the_code_the_process_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edit to the file on disk during a run does not move the digest: the
    record describes what the process is running, which is what the games
    were shown. The next process digests the new source."""
    module = _load(tmp_path, monkeypatch, "probe_renderer_a", RENDERER_A)
    before = renderer_digest(module.render_state)
    (tmp_path / "probe_renderer_a.py").write_text(RENDERER_B, encoding="utf-8")
    assert renderer_digest(module.render_state) == before


def test_a_renderer_outside_the_rig_is_refused() -> None:
    """A builtin or a partial has no rig module to digest; silently recording
    the wrong module (or `None`, the raw arm's value) would be a fingerprint
    that cannot move. Refused at fingerprint time, before any run spends."""
    with pytest.raises(ValueError, match="not a function defined in"):
        renderer_digest(str.upper)


def test_an_unknown_arm_or_game_is_refused_before_any_digest() -> None:
    with pytest.raises(ValueError, match="unknown response arm"):
        prompt_fingerprint("cheat", False, "no-such-arm")
    with pytest.raises(ValueError, match="unknown game"):
        prompt_fingerprint("no-such-game", False, "reasoning")


def test_the_agent_and_the_fingerprint_read_one_prompt_shape() -> None:
    """The agent's rules text, renderer and arm come from the same lookup the
    fingerprint digests, and an agent constructed with no arguments takes the
    shape a roster entry that says nothing takes — one default site."""
    from ..providers import FakeProvider

    default_render, default_arm = agents.llm_shape({})
    for game in GAMES:
        for render in RENDER:
            agent = agents.LLMAgent(
                provider=FakeProvider(replies=["{}"]), seed=0, render=render, game=game
            )
            assert agent.arm == default_arm
            rules, renderer, arm = agents.prompt_shape(game, render, default_arm)
            assert agent.rules == rules
            assert arm is agent._arm
            assert renderer is None or agent._render is renderer
            if renderer is None:
                assert agent._render("probe") == "probe"
    bare = agents.LLMAgent(provider=FakeProvider(replies=["{}"]), seed=0)
    assert (bare.render, bare.arm) == (default_render, default_arm)


# --- the resume gate, end to end ---------------------------------------------

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

from ..run_eval import ABSENT, SIDECAR_ONLY, differing, main, read_treatment  # noqa: E402

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


def _first_run(
    tmp_path: Path, spec: dict[str, Any] | None = None
) -> tuple[Path, dict[str, Any], Path]:
    target = tmp_path / "run-a"
    spec = spec or _spec(tmp_path)
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


def test_differences_travel_with_both_values() -> None:
    """A moved value is reported with what it was and what it is, at a path
    that is display only — so a key holding a "." (an operator's model name
    like `haiku-4.5`) and a value one side lacks are both shown faithfully."""
    recorded = {"models": {"haiku-4.5": {"model": "x"}}, "prompt": {"s": {"renderer": None}}}
    now = {"models": {"haiku-4.5": {"model": "y"}}, "prompt": {"s": {"renderer": "d"}}, "k": 1}
    assert differing(recorded, now) == [
        ("k", ABSENT, 1),
        ("models.haiku-4.5.model", "x", "y"),
        ("prompt.s.renderer", None, "d"),
    ]
    assert differing(recorded, recorded) == []


def test_the_record_carries_a_prompt_fingerprint_per_llm_shape(tmp_path: Path) -> None:
    target, _, _ = _first_run(tmp_path)
    recorded = read_treatment(_sidecar(target))
    assert recorded is not None
    assert recorded["prompt"] == {
        "cheat:raw:reasoning": prompt_fingerprint("cheat", False, "reasoning")
    }
    assert not SIDECAR_ONLY & set(recorded)


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


def test_resume_refuses_a_changed_renderer_on_the_rendered_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rendered shape through the runner: the same games, the same config,
    a renderer whose source differs — refused at the renderer component."""
    raw, rendered, _ = GAME_TEXT["cheat"]
    a = _load(tmp_path, monkeypatch, "probe_renderer_a", RENDERER_A)
    b = _load(tmp_path, monkeypatch, "probe_renderer_b", RENDERER_B)
    monkeypatch.setitem(GAME_TEXT, "cheat", (raw, rendered, a.render_state))
    spec = _spec(tmp_path)
    spec["matchups"][0]["agents"][0]["render"] = True
    target, _, config = _first_run(tmp_path, spec)
    recorded = read_treatment(_sidecar(target))
    assert recorded is not None and set(recorded["prompt"]) == {"cheat:rendered:reasoning"}
    assert _resume(config, target) == 0, "an unchanged rendered shape resumes"
    spec["matchups"][0]["n"] = 3
    spec["matchups"][0]["resume_from"] = 2
    _write(config, spec)
    monkeypatch.setitem(GAME_TEXT, "cheat", (raw, rendered, b.render_state))
    with pytest.raises(ValueError, match=r"prompt\.cheat:rendered:reasoning\.renderer"):
        _resume(config, target)


def test_resume_refuses_a_builder_branch_the_games_would_meet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the runner: the same config, the same composed probe, a
    builder that frames real decisions differently — refused at `builder`."""
    target, _, config = _first_run(tmp_path)
    branching = _load(tmp_path, monkeypatch, "probe_builder_branching", BUILDER_BRANCHING)
    monkeypatch.setattr(agents, "build_prompt", branching.build_prompt)
    with pytest.raises(ValueError, match=r"prompt\.cheat:raw:reasoning\.builder"):
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
    assert "prompt" in str(caught.value) and ABSENT in str(caught.value)


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


def test_the_override_also_covers_the_config_half(tmp_path: Path) -> None:
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
