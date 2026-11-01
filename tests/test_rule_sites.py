"""The one-site law: a rule binds at the trick round's card decision and
nowhere else (decisions.md "Rule demand forms").

Every other decision is legal or not by the construct that makes it, so the
rule cascade (`cardlang.runtime.rules`) has exactly one consumer in the
engine, and the move type that cascade is asked about
(`cardlang.stdlib.moves.RULE_ENFORCED_MOVE_TYPE`) has exactly two readers:
that consumer and the resolver's reachability Owner Guard, which refuses a
rule no site consults. The pins below read `cardlang/`'s AST, the sibling of
the chooser-site census in tests/test_delegated_play.py.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        the call sites of `rules.legal_cards` are exactly the trick
                 form's candidate hook; of every decision point, only the
                 trick form's code names the rule cascade's module; and the
                 readers of `RULE_ENFORCED_MOVE_TYPE` are exactly the trick
                 form's candidate hook and the resolver's reachability Owner
                 Guard.
domain:          every function and method under `cardlang/`, keyed by
                 module and class-qualified name. The decision-point axis is
                 `cardlang.runtime.delegation.DECISION_POINTS`, the round
                 site fanned out over the round forms `build_form`
                 dispatches to and reconciled against
                 `cardlang.runtime.delegation.FORM_CONSTRUCTS`; a name
                 refers to the rule cascade's module when it is a load of a
                 binding the file's imports make to `cardlang.runtime.rules`
                 or to one of its members.
registry:        decision points: `cardlang.runtime.delegation.DECISION_POINTS`
                 (call-site census: tests/test_delegated_play.py::test_every_decision_point_is_classified);
                 round forms: `cardlang.runtime.delegation.FORM_CONSTRUCTS`
                 and `cardlang.runtime.mechanics.build_form`'s match arms;
                 the trick form's construct: `FORM_CONSTRUCTS[n.TrickRound.__name__]`.
held by:         Derived and Pinned. Which code may consult the cascade is a
                 fact about call graphs, which no type in the engine holds,
                 so the scrape is the highest rung the fact admits.
does not prove:  that the one caller applies every active rule, or applies it
                 correctly -- tests/test_legal_cards.py and the corpus
                 goldens carry that; and a call reaching the cascade through
                 an alias the file's imports do not bind (a module object
                 passed as a value) is outside the scrape.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

from cardlang.ast import nodes as n
from cardlang.runtime.delegation import DECISION_POINTS, FORM_CONSTRUCTS

CARDLANG = pathlib.Path(__file__).resolve().parent.parent / "cardlang"
RULES_MODULE = "cardlang.runtime.rules"
MOVES_MODULE = "cardlang.stdlib.moves"
CONSTANT = "RULE_ENFORCED_MOVE_TYPE"


def _module_of(path: pathlib.Path) -> str:
    return path.stem


def _scopes(tree: ast.Module) -> Iterator[tuple[str, ast.AST]]:
    """Every function and method in a module, with its class-qualified name
    (`TrickForm.candidates`), outermost first; a nested function is named
    for its enclosing chain."""

    def walk(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.AST]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                yield name, child
                yield from walk(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, f"{prefix}{child.name}.")

    yield from walk(tree, "")


def _own_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """The nodes of one function body, not of the functions nested in it, so
    each reference is credited to its innermost scope."""
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield child
        yield from _own_nodes(child)


def _bindings(tree: ast.Module, module: str) -> tuple[set[str], dict[str, str]]:
    """The local names a file's imports bind to `module` itself, and to each
    of its members (local name -> member name)."""
    package, _, leaf = module.rpartition(".")
    whole: set[str] = set()
    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == package:
            whole |= {a.asname or a.name for a in node.names if a.name == leaf}
        elif isinstance(node, ast.ImportFrom) and node.module == module:
            members |= {a.asname or a.name: a.name for a in node.names}
        elif isinstance(node, ast.Import):
            whole |= {a.asname for a in node.names if a.name == module and a.asname}
    return whole, members


def _trees() -> Iterator[tuple[str, ast.Module]]:
    for path in sorted(CARDLANG.rglob("*.py")):
        yield _module_of(path), ast.parse(path.read_text())


def _member_loads(scope: ast.AST, whole: set[str], members: dict[str, str]) -> set[str]:
    """The members of the module a scope reads: `rules.legal_cards` and a
    bare imported `legal_cards` both read `legal_cards`."""
    read: set[str] = set()
    for node in _own_nodes(scope):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in whole
        ):
            read.add(node.attr)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in members:
            read.add(members[node.id])
    return read


def _module_references(module: str) -> dict[str, set[str]]:
    """Every `<module>.<scope>` under `cardlang/` that loads a binding to
    `module` or to one of its members, with the members it reads (a load of
    the module object alone reads the empty name)."""
    found: dict[str, set[str]] = {}
    for stem, tree in _trees():
        whole, members = _bindings(tree, module)
        if not (whole or members):
            continue
        for qualname, scope in _scopes(tree):
            read = _member_loads(scope, whole, members)
            if any(
                isinstance(nd, ast.Name) and isinstance(nd.ctx, ast.Load) and nd.id in whole
                for nd in _own_nodes(scope)
            ):
                read.add("")
            if read:
                found[f"{stem}.{qualname}"] = read
    return found


def _legal_cards_callers() -> set[str]:
    callers: set[str] = set()
    for stem, tree in _trees():
        whole, members = _bindings(tree, RULES_MODULE)
        for qualname, scope in _scopes(tree):
            for node in _own_nodes(scope):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                if (
                    isinstance(f, ast.Attribute)
                    and f.attr == "legal_cards"
                    and isinstance(f.value, ast.Name)
                    and f.value.id in whole
                ) or (isinstance(f, ast.Name) and members.get(f.id) == "legal_cards"):
                    callers.add(f"{stem}.{qualname}")
    return callers


def _form_classes() -> dict[str, str]:
    """`build_form`'s dispatch, read off its match arms: round node class
    name -> the form class it builds."""
    tree = ast.parse((CARDLANG / "runtime" / "mechanics.py").read_text())
    build = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_form"
    )
    arms: dict[str, str] = {}
    for case in (c for m in ast.walk(build) if isinstance(m, ast.Match) for c in m.cases):
        pattern = case.pattern
        assert isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Attribute)
        ret = next(s for s in case.body if isinstance(s, ast.Return))
        assert isinstance(ret.value, ast.Call) and isinstance(ret.value.func, ast.Name)
        arms[pattern.cls.attr] = ret.value.func.id
    return arms


def _round_site() -> str:
    """The decision point a `round` runs at: the one whose function asks a
    form for its candidates."""
    sites = set()
    for stem, tree in _trees():
        for qualname, scope in _scopes(tree):
            key = f"{stem}.{qualname}"
            if key in DECISION_POINTS and any(
                isinstance(nd, ast.Call)
                and isinstance(nd.func, ast.Attribute)
                and nd.func.attr == "candidates"
                for nd in _own_nodes(scope)
            ):
                sites.add(key)
    assert len(sites) == 1, sites
    return sites.pop()


def test_the_rule_cascade_has_one_caller() -> None:
    """The legal card list is computed from rules at the trick form's
    candidate hook and at no other site.

    red under: add `from cardlang.runtime import rules` to
    `cardlang/runtime/execute.py` and a `rules.legal_cards(...)` call in
    `execute._offer` -- the caller set gains `execute._offer`."""
    assert _legal_cards_callers() == {"mechanics.TrickForm.candidates"}


def test_only_the_trick_forms_decision_names_the_rule_cascade() -> None:
    """Of every decision point, fanned out over the round forms, the code
    names `cardlang.runtime.rules` iff the point is the trick form's.

    red under: add `from cardlang.runtime import rules` to
    `cardlang/runtime/execute.py` and a `rules.legal_cards(...)` call in
    `execute._offer` -- the actor-only offer site names the cascade; or a
    load of `rules.legal_cards` in `mechanics.ClimbForm.candidates` -- the
    climb form names the cascade."""
    arms = _form_classes()
    assert set(arms) == set(FORM_CONSTRUCTS), (arms, FORM_CONSTRUCTS)
    trick = FORM_CONSTRUCTS[n.TrickRound.__name__]
    round_site = _round_site()
    references = _module_references(RULES_MODULE)

    def names_cascade(prefix: str) -> bool:
        return any(key == prefix or key.startswith(f"{prefix}.") for key in references)

    seen: dict[str, bool] = {}
    for key, point in DECISION_POINTS.items():
        if key == round_site:
            continue
        seen[key] = names_cascade(key)
        assert seen[key] is (point.construct == trick), (key, point)
    for node_class, form in arms.items():
        seen[form] = names_cascade(f"mechanics.{form}")
        assert seen[form] is (FORM_CONSTRUCTS[node_class] == trick), (form, seen)
    assert names_cascade(round_site) is False, round_site
    assert sum(seen.values()) == 1, seen


def test_the_enforced_move_type_has_two_readers() -> None:
    """The constant naming the move type the cascade is asked about is read
    by its one consumer and by the resolver Owner Guard that refuses a rule
    no site consults, so the Owner Guard cannot drift from the consumer.

    red under: read `RULE_ENFORCED_MOVE_TYPE` in `mechanics.ClimbForm.candidates`
    (import it there and compare a value with it) -- the reader set gains
    `mechanics.ClimbForm.candidates`."""
    readers = {
        key for key, read in _module_references(MOVES_MODULE).items() if CONSTANT in read
    }
    assert readers == {
        "resolve._check_rule_reaches_a_reader",
        "mechanics.TrickForm.candidates",
    }
