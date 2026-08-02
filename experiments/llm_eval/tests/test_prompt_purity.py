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


# --- the import closure ----------------------------------------------------
#
# The decision path is not one module. `agents.py` imports `.render`,
# `.infostate` and `.providers`, and the rendered arm calls `render_state` on
# every decision — so a per-module scrape of `agents.py` and `prompts.py` reads
# green while an engine import sits one edge away, in code that runs on every
# prompt. What has to be engine-free is the TRANSITIVE CLOSURE of what a
# decision executes, and the closure is derived here rather than listed: a new
# import edge is covered the day it appears, which a hard-coded module list is
# exactly what fails to do.

ENGINE_ROOTS = frozenset({"cardlang", "pyspiel"})

# The decision path's entry points, as module objects — `LLMAgent.choose` lives
# in the first and calls into the second.
ENTRY_MODULES = (agents_mod, prompts_mod)
PACKAGE = agents_mod.__package__ or ""
PACKAGE_DIR = Path(inspect.getsourcefile(agents_mod) or "").parent


def _source_of(module: str) -> Path | None:
    """The file `module` would execute, or None if it names nothing this package
    defines. Resolved against the directory rather than through `importlib`, so
    an attribute mistaken for a submodule (`...prompts.RULES_RAW`, which
    `from .prompts import RULES_RAW` cannot be distinguished from an import of a
    submodule by syntax alone) simply misses instead of raising."""
    if module != PACKAGE and not module.startswith(PACKAGE + "."):
        return None
    rel = module[len(PACKAGE) :].lstrip(".")
    if not rel:
        return PACKAGE_DIR / "__init__.py"
    parts = rel.split(".")
    for candidate in (
        PACKAGE_DIR.joinpath(*parts).with_suffix(".py"),
        PACKAGE_DIR.joinpath(*parts) / "__init__.py",
    ):
        if candidate.exists():
            return candidate
    return None


def _anchor(module: str, source: Path, level: int) -> str:
    """The package a level-`level` relative import resolves against.

    Python anchors a relative import at `__package__`, which for a module is its
    parent but for a PACKAGE's `__init__.py` is the package itself. Stripping
    `level` components off the name unconditionally gets the second case wrong —
    inside `experiments/llm_eval/__init__.py`, `from . import render` would
    resolve to `experiments.render`, which names no file, so `_source_of`
    discards it and the edge vanishes from the closure. Since `_closure`
    deliberately walks `__init__.py`, that is a silent hole in exactly the file
    a future import is most likely to be added to.
    """
    parts = module.split(".")
    if source.name != "__init__.py":
        parts = parts[:-1]
    return ".".join(parts[: len(parts) - (level - 1)])


def _imports_of(source: Path, module: str) -> set[str]:
    """Every module name `module` imports, relative imports resolved to absolute.

    Two things the per-module scrapes this replaced could not see. `import a, b`
    binds EVERY alias, not just the first. And a relative import carries its
    target in `node.level` plus `node.names`, not in `node.module` — `from .
    import infostate` has `node.module is None`, so a scrape keyed on
    `node.module` skips the whole intra-package edge set, which is the edge set
    that matters here.

    `from X import Y` is ambiguous by syntax: `Y` may be a submodule or an
    attribute. Both readings are emitted; `_source_of` discards the one that
    names no file.
    """
    out: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = _anchor(module, source, node.level)
                base = f"{anchor}.{node.module}" if node.module else anchor
            elif node.module:
                base = node.module
            else:
                continue
            out.add(base)
            out.update(f"{base}.{alias.name}" for alias in node.names)
    return out


def _closure() -> tuple[dict[str, str | None], list[tuple[str, str]]]:
    """Breadth-first over intra-package import edges from the entry modules to
    fixpoint. Returns the reached modules (each mapped to its importer, so a
    failure can print the edge path) and every (engine module, importer) pair
    found anywhere in the closure."""
    reached: dict[str, str | None] = {m.__name__: None for m in ENTRY_MODULES}
    frontier = list(reached)
    offenders: list[tuple[str, str]] = []
    while frontier:
        module = frontier.pop(0)
        source = _source_of(module)
        if source is None:
            continue
        # Importing any submodule executes the package body first, so
        # `__init__.py` is on the decision path however it is reached.
        edges = _imports_of(source, module) | ({PACKAGE} if module != PACKAGE else set())
        for imported in sorted(edges):
            if imported.split(".")[0] in ENGINE_ROOTS:
                offenders.append((imported, module))
            if imported not in reached and _source_of(imported) is not None:
                reached[imported] = module
                frontier.append(imported)
    return reached, offenders


def _path_to(reached: dict[str, str | None], module: str) -> str:
    chain = [module]
    while reached.get(chain[-1]) is not None:
        chain.append(str(reached[chain[-1]]))
    return " -> ".join(reversed(chain))


def test_the_decision_path_never_imports_the_engine() -> None:
    """No module the decision path executes — transitively — may import
    `cardlang` or `pyspiel`.

    The import list is the coarsest possible proof that no agent can reach the
    state, and the only one that holds for branches no run took. Taken over the
    closure rather than per module, because `LLMAgent.choose` runs `render.py`
    on every rendered-arm decision: an engine import there is an engine import
    on the decision path.
    """
    reached, offenders = _closure()
    assert not offenders, "the decision path imports the engine:\n" + "\n".join(
        f"  {imported}  via  {_path_to(reached, importer)}"
        for imported, importer in sorted(offenders)
    )
    assert set(reached) > {m.__name__ for m in ENTRY_MODULES}, (
        "the walk followed no intra-package edge — it has stopped checking "
        "anything the per-module scrapes did not already check"
    )


def test_the_import_closure_is_a_filter_not_a_tautology() -> None:
    """The closure test above is only worth its name if this package HAS
    engine-facing modules that the closure excludes.

    `referee.py` drives a `pyspiel.State`; it imports `agents`, not the other
    way round, so it sits outside the closure — and the day something on the
    decision path reaches for it, the test above turns red. Without this check,
    a package whose every module was engine-free would pass the closure test
    while proving nothing about the closure.
    """
    reached, _ = _closure()
    engine_facing = {
        path.stem
        for path in sorted(PACKAGE_DIR.glob("*.py"))
        if any(
            name.split(".")[0] in ENGINE_ROOTS
            for name in _imports_of(path, f"{PACKAGE}.{path.stem}")
        )
    }
    assert engine_facing, (
        "no module in this package imports the engine, so the closure test "
        "cannot distinguish a real filter from a vacuous one"
    )
    inside = sorted({f"{PACKAGE}.{stem}" for stem in engine_facing} & set(reached))
    assert not inside, (
        f"engine-facing modules are on the decision path: {inside} — the "
        f"closure test above is now reporting a real violation, fix that first"
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
