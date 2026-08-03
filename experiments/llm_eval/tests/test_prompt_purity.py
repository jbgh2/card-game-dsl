"""The leak-freeness pins.

Three layers, because the claim has three halves and no one technique covers
them:

1. **`build_prompt` is a pure function of its arguments** — same inputs,
   identical bytes; different inputs, different bytes. Behavioural, and enough,
   because the function has no other inputs to vary.
2. **The agent reaches the game only through the entitled accessors** — a
   property of the SOURCE, not of any single run. A scrape, because a run only
   proves the branches it took, and the leaking branch is exactly the one a
   test might not exercise.
3. **Nothing a decision executes imports the engine** — measured by importing
   the entry points in a clean subprocess and reading `sys.modules`, so the
   interpreter resolves the graph and there is no resolution of ours to get
   wrong. Paired with a scrape for imports deferred inside function bodies,
   which execution structurally cannot see.

Layers 2 and 3 are the same claim approached from opposite directions, and each
is blind where the other sees: execution knows exactly what was loaded but not
what a function would load if called; the scrape reads every branch but has to
resolve names itself. Neither alone is the check.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import get_type_hints

import pytest

from .. import agents as agents_mod
from .. import prompts as prompts_mod
from ..agents import DecisionView, LLMAgent
from ..prompts import (
    RESPONSE_ARMS,
    RULES_RAW,
    RULES_RENDERED,
    RULES_TEXT,
    build_prompt,
)
from ..providers import FakeProvider
from ..render import render_state

# A complete Cheat information state — every state variable the game declares,
# so the rendered arm can be driven from the same pair as the raw one.
INFO_A = (
    "P1|deck=#0;flipped=[];pile=#0;played=#1;hand[0]=#12;"
    "hand[1]=[10♥,2♥,A♣];hand[2]=#13;hand[3]=#13"
    "|state:challenged=False;challenger=0;claim_count=1;claim_rank=A;claimant=0;"
    "responder=1;window_open=True;won={0:False,1:False,2:False,3:False}"
    "|obs:('announce', 0, 'play_one')"
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
    """Enforcement by signature (spec §1): strings, nothing else.

    Pinned as a PROPERTY rather than a fixed parameter list. The guarantee is
    that no argument can carry a game state — not that there are exactly three
    of them. Naming the list froze an experimental variable: the response
    boilerplate was a module constant purely because this test made adding a
    parameter look like a violation, and it is spec §1's fourth input. A new
    parameter of any non-string type still reddens this, which is the property
    that matters.
    """
    hints = get_type_hints(build_prompt)
    assert hints.pop("return") is str
    assert hints, "build_prompt takes no arguments — the check is vacuous"
    for name, annotation in hints.items():
        assert annotation in (str, list[str]), (
            f"build_prompt parameter {name!r} is {annotation!r}; only strings "
            f"may reach the prompt, or a game state could be passed in"
        )
    # The information state must still be one of them, by name — it is the
    # artifact the indistinguishability proofs cover.
    assert "infostate" in hints


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
    allowed = set(DecisionView.__dataclass_fields__)
    entitled = {
        id(node.value)
        for node in ast.walk(method)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "view"
        and node.attr in allowed
    }
    read = {
        node.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "view"
    }
    # Bare `view` escapes the field check entirely: `helper(view)` reads no
    # attribute here, so a scrape over attribute names alone passes it while the
    # callee holds the whole view. `DecisionView` carries only strings today, so
    # this is a narrower leak than the renderer's — but the check is claimed over
    # what `choose` may reach, and a callee reaches everything it is handed.
    escapes = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.Name) and node.id == "view" and id(node) not in entitled
    ]
    assert read, "the scrape found no `view.*` reads — it has stopped checking anything"
    assert read <= allowed, f"LLMAgent.choose reads non-entitled fields: {read - allowed}"
    assert not escapes, (
        f"LLMAgent.choose passes bare `view` at line(s) "
        f"{sorted({n.lineno for n in escapes})} — the callee then holds fields "
        f"this scrape is claimed to police. Pass the entitled fields instead."
    )


def test_decision_view_carries_no_state_object() -> None:
    """`DecisionView`'s fields are strings, ints and lists thereof. Nothing an
    agent holds can be a `pyspiel.State` or a `RuntimeState`."""
    assert get_type_hints(DecisionView) == {
        "player": int,
        "infostate": str,
        "legal_actions": list[int],
        "legal_strings": list[str],
    }


# --- the engine is off the decision path ------------------------------------
#
# The decision path is not one module: `agents.py` imports `.render`,
# `.infostate` and `.providers`, and the rendered arm calls `render_state` on
# every decision — so a per-module scrape reads green while an engine import
# sits one edge away, in code that runs on every prompt. What has to be
# engine-free is everything a decision EXECUTES.
#
# Two checks, because neither is sufficient and each covers the other's blind
# spot:
#
# - IMPORT AND LOOK (`test_the_decision_path_never_imports_the_engine`). Import
#   the entry points in a clean subprocess and read `sys.modules`. The
#   interpreter resolves the graph, so there is no resolution left to get wrong.
#   This replaced a hand-rolled AST walk over the import graph, which accreted
#   five distinct defects — non-transitivity, invisible relative imports, a
#   wrong anchor inside `__init__.py`, skipped intermediate package
#   initializers, and a reach that depended on pytest's import alias. Every one
#   was a way Python resolves imports that the reimplementation got wrong;
#   asking Python removes the whole class rather than the five instances.
# - READ THE SOURCE (`test_no_module_on_the_decision_path_defers_an_engine_import`).
#   Execution only shows what the import DID. A `def choose(): import pyspiel`
#   never runs at import time, so `sys.modules` stays clean while the engine is
#   one call away — exactly the branch-a-run-did-not-take case the scrape exists
#   for. Grep the executed files' ASTs for engine imports anywhere, including
#   inside function bodies.
#
# The module set the second check reads comes from the first, so it covers what
# actually executes rather than what a walk guessed would.

ENGINE_ROOTS = frozenset({"cardlang", "pyspiel"})

# The decision path's entry points — `LLMAgent.choose` lives in the first and
# calls into the second.
ENTRY_MODULES = (agents_mod, prompts_mod)
PACKAGE = agents_mod.__package__ or ""
PACKAGE_DIR = Path(inspect.getsourcefile(agents_mod) or "").parent
REPO_ROOT = PACKAGE_DIR.parent.parent


def _engine_roots(node: ast.AST) -> set[str]:
    """The engine packages an import statement names, or empty for any other
    node. One definition, because both the deferred-import scrape and the
    not-a-tautology check ask the same question and two spellings would drift.

    A relative import (`node.level > 0`) can never name an engine package: it
    resolves inside this package by construction.
    """
    if isinstance(node, ast.Import):
        return {alias.name.split(".")[0] for alias in node.names} & ENGINE_ROOTS
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return {node.module.split(".")[0]} & ENGINE_ROOTS
    return set()


@cache
def _executed_modules() -> dict[str, str]:
    """`{module name: source file}` for everything importing the entry points
    executes, from a clean interpreter.

    A SUBPROCESS, not this one: pytest has already imported half the repo, so
    `sys.modules` here proves nothing about what a decision alone pulls in.
    """
    names = ", ".join(repr(m.__name__) for m in ENTRY_MODULES)
    probe = (
        "import importlib, json, sys\n"
        f"for n in ({names},):\n"
        "    importlib.import_module(n)\n"
        "print(json.dumps({n: getattr(m, '__file__', '') or ''"
        " for n, m in sys.modules.items()}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "experiments")},
    )
    assert proc.returncode == 0, (
        f"importing the decision path failed, so the check proves nothing:\n{proc.stderr}"
    )
    loaded: dict[str, str] = json.loads(proc.stdout)
    for entry in ENTRY_MODULES:
        assert entry.__name__ in loaded, (
            f"the probe did not import {entry.__name__} — it is measuring the "
            f"wrong thing"
        )
    return loaded


def test_the_decision_path_never_imports_the_engine() -> None:
    """Nothing a decision executes may import `cardlang` or `pyspiel`.

    The import list is the coarsest possible proof that no agent can reach the
    state, and the only one that holds for branches no run took. Taken over what
    the interpreter actually loads, so transitive edges, relative imports,
    package initializers and absolute self-imports are all covered by
    construction rather than by a resolver of mine.
    """
    loaded = _executed_modules()
    offenders = sorted(n for n in loaded if n.split(".")[0] in ENGINE_ROOTS)
    assert not offenders, (
        "importing the decision path loads the engine: "
        + ", ".join(offenders)
        + " — an agent could reach hidden state through it"
    )


def test_no_module_on_the_decision_path_defers_an_engine_import() -> None:
    """...and none of them hides one inside a function.

    `sys.modules` cannot see a deferred import: `def choose(): import pyspiel`
    leaves the check above green while putting the engine one call away. This is
    the half execution cannot do, so it is a scrape — over the files execution
    proved are on the path, at any depth, function bodies included.
    """
    own = {
        name: Path(path)
        for name, path in _executed_modules().items()
        if path and Path(path).is_relative_to(PACKAGE_DIR)
    }
    assert own, "no package module was executed — the check has stopped checking"
    deferred = [
        f"{name}:{node.lineno} imports {root}"
        for name, path in sorted(own.items())
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for root in sorted(_engine_roots(node))
    ]
    assert not deferred, (
        "a module on the decision path imports the engine:\n  " + "\n  ".join(deferred)
    )


def test_the_engine_check_is_a_filter_not_a_tautology() -> None:
    """The checks above are only worth their name if this package HAS
    engine-facing modules they exclude.

    `referee.py` drives a `pyspiel.State`; it imports `agents`, not the other
    way round, so it never executes on the decision path — and the day
    something there reaches for it, both checks turn red. Without this, a
    package whose every module was engine-free would pass while proving nothing.
    """
    engine_facing = {
        path.name
        for path in sorted(PACKAGE_DIR.glob("*.py"))
        if any(
            _engine_roots(node)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    }
    assert engine_facing, (
        "no module in this package imports the engine, so the checks above "
        "cannot distinguish a real filter from a vacuous one"
    )
    executed = {
        Path(path).name for path in _executed_modules().values()
        if path and Path(path).is_relative_to(PACKAGE_DIR)
    }
    assert executed, "nothing executed — the comparison is empty on both sides"
    inside = sorted(engine_facing & executed)
    assert not inside, (
        f"engine-facing modules are on the decision path: {inside} — the checks "
        f"above are now reporting a real violation, fix that first"
    )


@pytest.mark.parametrize("render", [False, True])
def test_llm_agent_prompt_is_the_canonical_artifact(render: bool) -> None:
    """What the provider actually receives is exactly `build_prompt`'s output —
    so the purity pins above constrain the real request, not a parallel one.

    Both arms, byte-exact. The rendered arm's own tests check that the English
    CONTAINS the right facts; containment cannot see an extra sentence appended
    on the way to the provider, and the rendered arm is the one with a
    transformation between the information state and the prompt.

    The response instruction is passed explicitly rather than left to
    `build_prompt`'s default: the default happens to equal the `reasoning`
    arm's, so an omission here would pass while stating less than it looks.
    """
    legal = ["allow", "call_cheat"]
    provider = FakeProvider(replies=['{"action": 0, "reasoning": "x"}'])
    agent = LLMAgent(provider=provider, seed=0, render=render)
    agent.choose(DecisionView(1, INFO_A, [54, 55], legal))
    rules = RULES_RENDERED if render else RULES_RAW
    state = render_state(INFO_A) if render else INFO_A
    assert provider.prompts == [
        build_prompt(rules, state, legal, RESPONSE_ARMS["reasoning"].instruction)
    ]


def test_prompt_carries_nothing_but_its_arguments() -> None:
    """The prompt is its arguments and the harness's own static text — nothing
    else, and in particular nothing naming the world (a seed) rather than the
    observer's view of it.

    Stated as equality with `build_prompt`'s output rather than as a grep for
    the word "seed". A grep passes on a prompt carrying the world's identity
    under any other name; equality with the pure function of the entitled
    arguments admits no such prompt at all.
    """
    legal = ["allow", "call_cheat"]
    for info in (INFO_A, INFO_B):
        provider = FakeProvider(replies=['{"action": 0, "reasoning": "x"}'])
        LLMAgent(provider=provider, seed=4242).choose(DecisionView(1, info, [54, 55], legal))
        assert provider.prompts == [
            build_prompt(RULES_RAW, info, legal, RESPONSE_ARMS["reasoning"].instruction)
        ]
        assert "4242" not in provider.prompts[0]


def test_the_built_agent_carries_the_modules_rules_text() -> None:
    """Every agent a config can build reads the module's own rules constant for
    its arm. `rules` is resolved at construction and is not reachable from
    `build_agent`, so nothing a run can configure substitutes a different rules
    text — which would make two arms' numbers incomparable while every other
    pin stayed green."""
    from ..agents import build_agent

    for render, expected in ((False, RULES_RAW), (True, RULES_RENDERED)):
        agent = build_agent(
            {"kind": "llm", "render": render}, seed=0, provider=FakeProvider(replies=[])
        )
        assert isinstance(agent, LLMAgent)
        assert agent.rules == expected
