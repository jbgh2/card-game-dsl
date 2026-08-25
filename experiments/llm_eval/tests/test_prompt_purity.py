"""The leak-freeness pins.

Three layers, in descending order of how much they carry:

1. **The agent cannot be HANDED a game state.** `DecisionView`'s fields are
   `int`, `str` and lists of those (`test_decision_view_carries_no_state_object`).
   One assertion, total, and the guarantee the README's claim actually rests on.
2. **The agent reads nothing outside those fields** — a property of the SOURCE,
   not of any run, so an `ast` scrape: a run only proves the branches it took,
   and the leaking branch is the one a test might not exercise.
3. **No import chain reaches the engine from a decision** — defence-in-depth
   against an agent CONSTRUCTING access rather than being given it. Delegated
   to `grimp`, the import-graph library behind `import-linter`, because a
   hand-rolled walk of the import graph accreted five distinct resolution
   defects here (non-transitivity, invisible relative imports, a wrong anchor
   inside `__init__.py`, skipped intermediate package initializers, and a reach
   that depended on the test runner's import alias). Every one was a way Python
   resolves imports that the reimplementation got wrong, which is a library's
   job and not this file's.

`build_prompt`'s purity sits alongside them: same inputs, identical bytes;
different inputs, different bytes. Behavioural, and enough, because the
function has no other inputs to vary.
"""
from __future__ import annotations

import ast
import inspect
from functools import cache
from pathlib import Path
from typing import Any, get_type_hints

import grimp
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
    "|state:challenged=False;challenger=None;claim_count=1;claim_rank=A;claimant=0;"
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
# ONE check, and its scope stated exactly, because the previous wording outlived
# two rewrites and described evidence that no longer existed.
#
# `grimp` builds the import graph from import STATEMENTS across the package, and
# a decision must have no chain to `cardlang` or `pyspiel`. It covers what a
# hand-rolled walk here kept getting wrong — transitive edges, relative imports,
# nested packages, and imports deferred inside function bodies, all verified
# against it before adoption.
#
# What it does NOT cover, stated because a subprocess probe in the intervening
# commit did and this is a real reduction, not a wash: an import performed
# DYNAMICALLY, `importlib.import_module("pyspiel")` or `__import__`. A static
# graph cannot see a name computed at runtime; the probe saw it because the
# import had actually happened. The trade was deliberate — the probe cost five
# resolution defects and could only evaluate a tree where every module imports
# cleanly — but the residual is real. It is bounded by review: a dynamic engine
# import in six small modules is not a thing that arrives unnoticed, and the
# guarantee this backs is defence-in-depth behind `DecisionView`'s type.

ENGINE_ROOTS = frozenset({"cardlang", "pyspiel"})

# The decision path's entry points — `LLMAgent.choose` lives in the first and
# calls into the second.
ENTRY_MODULES = (agents_mod, prompts_mod)
PACKAGE = agents_mod.__package__ or ""
PACKAGE_DIR = Path(inspect.getsourcefile(agents_mod) or "").parent
REPO_ROOT = PACKAGE_DIR.parent.parent


def _canonical(module: object) -> str:
    """A module's name as PRODUCTION imports it — derived from its path under
    the repo root, not from `__name__`.

    `pytest experiments/llm_eval/tests` imports these as `llm_eval.agents`,
    while `python -m experiments.llm_eval.run_eval` imports
    `experiments.llm_eval.agents`. Probing whatever alias the test runner
    happened to produce measures a graph nobody ships; if import behaviour ever
    branches on `__name__` or `__package__`, the alias graph could stay
    engine-free while the production one does not.
    """
    path = Path(inspect.getsourcefile(module) or "").resolve()  # type: ignore[arg-type]
    rel = path.relative_to(REPO_ROOT.resolve()).with_suffix("")
    return ".".join(rel.parts)


@cache
def _graph() -> Any:
    """The package's import graph, from `grimp`, plus the edges Python implies.

    `grimp` builds the graph from import STATEMENTS, and gets right everything
    this check previously hand-rolled: transitive edges, relative imports,
    imports deferred inside function bodies, nested packages. Each was verified
    against it before adopting it — a hand-rolled walker accreted five distinct
    resolution defects here, and none of that class is ours to own now.

    One edge is not a statement, so `grimp` does not have it: importing
    `pkg.sub.leaf` also EXECUTES `pkg/__init__.py` and `pkg/sub/__init__.py`. An
    engine import in a package initializer is reachable in Python and
    unreachable in the raw graph — verified, and the reason this adds the parent
    edges itself rather than handing the contract to `import-linter`, which
    reports it KEPT. Traversal stays `grimp`'s; only the edge set is ours.
    """
    graph = grimp.build_graph(_graph_root(), include_external_packages=True)
    for module in sorted(graph.modules):
        parent = module.rpartition(".")[0]
        if parent and parent in graph.modules:
            graph.add_import(importer=module, imported=parent)
    return graph


def _package() -> str:
    return _canonical(agents_mod).rpartition(".")[0]


def _graph_root() -> str:
    """The package to root the graph at: the HIGHEST ancestor that is a regular
    package, i.e. the highest `__init__.py` that runs on the way in.

    Rooting at the package itself leaves anything above it outside the graph, so
    the parent edges added below cannot reach it — `experiments/__init__.py`
    could import the engine and execute before `agents` while every chain stayed
    clean. `experiments/` is a namespace package today, so this resolves to the
    package itself and nothing changes; the day a real one appears above, the
    root rises to meet it instead of the check quietly going blind.
    """
    parts = _package().split(".")
    for i in range(len(parts)):
        if (REPO_ROOT.joinpath(*parts[: i + 1]) / "__init__.py").exists():
            return ".".join(parts[: i + 1])
    return _package()


def test_the_decision_path_never_imports_the_engine() -> None:
    """No chain of imports leads from a decision to `cardlang` or `pyspiel`.

    The import list is the coarsest possible proof that no agent can reach the
    state, and the only one that holds for branches no run took. It is
    defence-in-depth rather than the guarantee itself: `DecisionView` carries
    only strings and ints (`test_decision_view_carries_no_state_object`), so an
    agent cannot be HANDED a game state. This is what stops one being built.
    """
    graph = _graph()
    entries = [_canonical(m) for m in ENTRY_MODULES]
    for entry in entries:
        assert entry in graph.modules, (
            f"{entry} is absent from the import graph — the check is reading the "
            f"wrong package and would pass whatever the code did"
        )
    for entry in entries:
        for engine in sorted(ENGINE_ROOTS):
            if engine not in graph.modules:
                continue  # nothing in the tree imports it at all
            chain = graph.find_shortest_chain(importer=entry, imported=engine)
            assert chain is None, (
                f"a decision can reach the engine: {' -> '.join(chain)}"
            )


def test_nothing_executable_sits_above_the_graph_root() -> None:
    """Every `__init__.py` on the way into the package is inside the graph.

    A package initializer above the root would execute on the way to a decision
    and be unreachable in a graph that does not contain it. `_graph_root` raises
    the root to cover one; this asserts the result, so the derivation is checked
    rather than trusted.
    """
    root_parts = _graph_root().split(".")
    for i in range(len(root_parts)):
        above = REPO_ROOT.joinpath(*root_parts[: i + 1])
        if above.name == root_parts[-1]:
            break
        assert not (above / "__init__.py").exists(), (
            f"{above}/__init__.py executes on the way to a decision but sits "
            f"above the graph root {_graph_root()!r} — raise the root"
        )
    assert _graph_root() in _graph().modules


def test_the_engine_check_is_a_filter_not_a_tautology() -> None:
    """The check above is only worth its name if this package HAS modules that
    reach the engine and are excluded.

    `referee.py` drives a `pyspiel.State`; it imports `agents`, not the other
    way round, so no decision reaches it — and the day one does, the check turns
    red. Without this, a package whose every module was engine-free would pass
    while proving nothing about the filter.
    """
    graph = _graph()
    prefix = _package() + "."
    engine_facing = sorted(
        m
        for m in graph.modules
        if m.startswith(prefix)
        and any(
            e in graph.modules
            and graph.find_shortest_chain(importer=m, imported=e) is not None
            for e in ENGINE_ROOTS
        )
    )
    assert engine_facing, (
        "no module in this package reaches the engine, so the check above "
        "cannot distinguish a real filter from a vacuous one"
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
