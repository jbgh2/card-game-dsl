"""The leak-freeness pins.

Two layers, because the claim has two halves. The first is that `build_prompt`
is a pure function of its arguments — same inputs, identical bytes; different
inputs, different bytes. The second is that the LLM agent reaches the game only
through the three entitled accessors, which is a property of the SOURCE, not of
any single run: an `ast` scrape is the only check that cannot be satisfied by a
test that happens not to exercise the leaking branch.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from experiments.llm_eval import agents as agents_mod
from experiments.llm_eval import prompts as prompts_mod
from experiments.llm_eval.agents import DecisionView, LLMAgent
from experiments.llm_eval.prompts import RULES_RAW, RULES_TEXT, build_prompt
from experiments.llm_eval.providers import FakeProvider

INFO_A = (
    "P1|deck=#0;flipped=[];pile=#0;played=#1;hand[0]=#12;"
    "hand[1]=[10♥,2♥,A♣];hand[2]=#13;hand[3]=#13"
    "|state:challenged=False;claim_count=1;claim_rank=A;claimant=0;"
    "responder=1;window_open=True|obs:('announce', 0, 'play_one')"
)
INFO_B = INFO_A.replace("hand[1]=[10♥,2♥,A♣]", "hand[1]=[10♥,2♥,K♣]")


def test_build_prompt_is_deterministic() -> None:
    """Same inputs, byte-identical output — across repeated calls."""
    first = build_prompt(RULES_TEXT, INFO_A, ["allow", "call_cheat"])
    for _ in range(5):
        assert build_prompt(RULES_TEXT, INFO_A, ["allow", "call_cheat"]) == first


def test_build_prompt_depends_only_on_its_arguments() -> None:
    """Indistinguishable info states produce identical prompts; distinguishable
    ones do not. The first half is the inheritance claim; the second is what
    keeps it from being vacuous (a constant function would pass the first)."""
    legal = ["allow", "call_cheat"]
    assert build_prompt(RULES_TEXT, INFO_A, legal) == build_prompt(RULES_TEXT, INFO_A, legal)
    assert build_prompt(RULES_TEXT, INFO_A, legal) != build_prompt(RULES_TEXT, INFO_B, legal)
    assert build_prompt(RULES_TEXT, INFO_A, legal) != build_prompt(
        RULES_TEXT, INFO_A, ["allow", "call_cheat", "play_one"]
    )


def test_build_prompt_signature_takes_no_state() -> None:
    """Enforcement by signature (spec §1): three strings, nothing else. A
    future parameter that could carry a state object reddens this."""
    sig = inspect.signature(build_prompt)
    assert list(sig.parameters) == ["rules", "infostate", "legal_actions"]
    # `from __future__ import annotations` makes raw annotations strings;
    # resolve them so the check is about types, not spelling.
    hints = get_type_hints(build_prompt)
    assert hints == {"rules": str, "infostate": str, "legal_actions": list[str], "return": str}


def test_prompt_contains_the_infostate_verbatim() -> None:
    """The raw state string is passed through, never paraphrased — it is the
    artifact the indistinguishability proofs cover."""
    prompt = build_prompt(RULES_TEXT, INFO_A, ["allow", "call_cheat"])
    assert INFO_A in prompt


def test_llm_agent_reads_only_entitled_fields() -> None:
    """An `ast` scrape of `LLMAgent.choose`: every attribute it reads off its
    `view` argument must be a `DecisionView` field.

    This is the check a behavioural test cannot make. A run only proves the
    branches it took; the scrape proves no branch exists that could read
    anything else, because `DecisionView` carries nothing else to read.
    """
    source = Path(inspect.getsourcefile(agents_mod) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "LLMAgent"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "choose"
    )
    read = {
        node.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "view"
    }
    assert read, "the scrape found no `view.*` reads — it has stopped checking anything"
    allowed = set(DecisionView.__dataclass_fields__)
    assert read <= allowed, f"LLMAgent.choose reads non-entitled fields: {read - allowed}"


def test_decision_view_carries_no_state_object() -> None:
    """`DecisionView`'s fields are strings, ints and lists thereof. Nothing an
    agent holds can be a `pyspiel.State` or a `RuntimeState`."""
    assert get_type_hints(DecisionView) == {
        "player": int,
        "infostate": str,
        "legal_actions": list[int],
        "legal_strings": list[str],
    }


def test_agent_module_never_imports_the_engine() -> None:
    """`agents.py` may import the harness's own string helpers and nothing from
    `cardlang` or `pyspiel` — the import list is the coarsest possible proof
    that no agent can reach the state."""
    source = Path(inspect.getsourcefile(agents_mod) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    forbidden = {m for m in modules if m.split(".")[0] in {"cardlang", "pyspiel"}}
    assert not forbidden, f"agents.py imports the engine: {sorted(forbidden)}"


def test_prompts_module_never_imports_the_engine() -> None:
    source = Path(inspect.getsourcefile(prompts_mod) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        root = None
        if isinstance(node, ast.Import):
            root = node.names[0].name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
        assert root not in {"cardlang", "pyspiel"}, f"prompts.py imports {root}"


def test_llm_agent_prompt_is_the_canonical_artifact() -> None:
    """What the provider actually receives is exactly `build_prompt`'s output —
    so the purity pins above constrain the real request, not a parallel one."""
    provider = FakeProvider(replies=['{"action": 0, "reasoning": "x"}'])
    agent = LLMAgent(provider=provider, seed=0)
    view = DecisionView(1, INFO_A, [54, 55], ["allow", "call_cheat"])
    agent.choose(view)
    # `RULES_RAW` is the raw arm's default (rules + the machine-format guide);
    # the rendered arm is pinned separately in `test_render.py`.
    assert provider.prompts == [build_prompt(RULES_RAW, INFO_A, ["allow", "call_cheat"])]


@pytest.mark.parametrize("info", [INFO_A, INFO_B])
def test_prompt_never_mentions_the_seed(info: str) -> None:
    """A seed in the prompt would break the whole argument: it names the world,
    not the observer's view of it."""
    prompt = build_prompt(RULES_TEXT, info, ["allow", "call_cheat"])
    assert "seed" not in prompt.lower()
