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

property:        the one module under `cardlang/` importing the rule
                 cascade, in any import form, is the round forms' module;
                 the call sites of `legal_cards` are exactly the trick
                 form's candidate hook; of every decision point, only the
                 trick form's code names the cascade; and every occurrence
                 of `RULE_ENFORCED_MOVE_TYPE` outside its definition -- a
                 name, an attribute, an import under any alias and that
                 alias's reads -- is in the trick form's candidate hook, the
                 resolver's reachability Owner Guard, or the import of it
                 in those two modules.
domain:          every Python module under `cardlang/`, keyed by its dotted
                 module path; every scope in it -- function, method, and the
                 module and class bodies as scopes of their own -- keyed by
                 its qualified name. A name refers to the cascade when it
                 resolves, through the file's imports (absolute, relative,
                 aliased or not) and its module-level assignments, and
                 through another `cardlang` module's own imports when read
                 as that module's attribute, to `cardlang.runtime.rules` or
                 a member of it. The decision-point axis is
                 `cardlang.runtime.delegation.DECISION_POINTS`, the round
                 site fanned out over the round forms `build_form`
                 dispatches to and reconciled against
                 `cardlang.runtime.delegation.FORM_CONSTRUCTS`.
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
                 goldens carry that; and a reach the scrape cannot resolve
                 statically: a name bound by assignment inside a function, a
                 `getattr` or `importlib` lookup, a module object passed as a
                 value, or a call to a private member of the cascade
                 (`rules._applies`) from the round forms' module outside a
                 decision point.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

from cardlang.ast import nodes as n
from cardlang.runtime.delegation import DECISION_POINTS, FORM_CONSTRUCTS

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDLANG = ROOT / "cardlang"
RULES_MODULE = "cardlang.runtime.rules"
MECHANICS = "cardlang.runtime.mechanics"
CONSTANT = "RULE_ENFORCED_MOVE_TYPE"
CONSTANT_HOME = "cardlang.stdlib.moves"
MODULE_SCOPE = "<module>"


def _dotted(path: pathlib.Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> dict[str, tuple[pathlib.Path, ast.Module]]:
    return {
        _dotted(path): (path, ast.parse(path.read_text()))
        for path in sorted(CARDLANG.rglob("*.py"))
    }


def _package_of(module: str, path: pathlib.Path) -> str:
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _absolute(node: ast.ImportFrom, module: str, path: pathlib.Path) -> str:
    """The absolute module an `ImportFrom` reads from, its relative level
    resolved against the importing module's package."""
    if node.level == 0:
        return node.module or ""
    base = _package_of(module, path).split(".")
    base = base[: len(base) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _import_bindings(tree: ast.Module, module: str, path: pathlib.Path) -> dict[str, str]:
    """Every local name a file's imports bind, anywhere in the file, to the
    dotted name it stands for."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    bound[a.asname] = a.name
                else:
                    root = a.name.split(".")[0]
                    bound[root] = root
        elif isinstance(node, ast.ImportFrom):
            source = _absolute(node, module, path)
            for a in node.names:
                bound[a.asname or a.name] = f"{source}.{a.name}"
    return bound


def _chain(node: ast.expr) -> list[str] | None:
    """`a.b.c` as `["a", "b", "c"]`, or None for any other expression."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return parts[::-1]


class _Resolver:
    """Dotted names for the names a module reads: its imports, its
    module-level assignments, and an attribute of another `cardlang`
    module read through that module's own bindings."""

    def __init__(self, modules: dict[str, tuple[pathlib.Path, ast.Module]]) -> None:
        self.modules = modules
        self.bindings: dict[str, dict[str, str]] = {}
        for module, (path, tree) in modules.items():
            bound = _import_bindings(tree, module, path)
            for _ in range(len(tree.body)):
                before = dict(bound)
                for stmt in tree.body:
                    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                        target = stmt.targets[0]
                        parts = _chain(stmt.value)
                        if isinstance(target, ast.Name) and parts is not None:
                            resolved = self._expand(bound, parts)
                            if resolved is not None:
                                bound[target.id] = resolved
                if bound == before:
                    break
            self.bindings[module] = bound

    def _expand(self, bound: dict[str, str], parts: list[str]) -> str | None:
        if parts[0] not in bound:
            return None
        return self.canonical(".".join([bound[parts[0]], *parts[1:]]))

    def canonical(self, dotted: str) -> str:
        """Rewrite a prefix naming a `cardlang` module's attribute through
        that module's own bindings, until nothing changes."""
        for _ in range(16):
            parts = dotted.split(".")
            for i in range(len(parts) - 1, 0, -1):
                owner = ".".join(parts[:i])
                bound = self.bindings.get(owner) if owner in self.modules else None
                if bound is not None and parts[i] in bound:
                    rewritten = ".".join([bound[parts[i]], *parts[i + 1 :]])
                    if rewritten != dotted:
                        dotted = rewritten
                        break
            else:
                return dotted
        return dotted

    def resolve(self, module: str, node: ast.expr) -> str | None:
        parts = _chain(node)
        return None if parts is None else self._expand(self.bindings[module], parts)


def _scopes(tree: ast.Module) -> Iterator[tuple[str, ast.AST]]:
    """Every scope in a module with its qualified name: the module body
    (`<module>`), each class body, each function and method."""
    yield MODULE_SCOPE, tree

    def walk(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.AST]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                yield name, child
                yield from walk(child, f"{name}.")
            else:
                yield from walk(child, prefix)

    yield from walk(tree, "")


def _own_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """The nodes of one scope, not of the scopes nested in it."""
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield child
        yield from _own_nodes(child)


def _outermost(nodes: list[ast.AST]) -> Iterator[ast.expr]:
    """The Name/Attribute chains of a scope, each counted once at its
    longest form."""
    inner: set[int] = set()
    for nd in nodes:
        if isinstance(nd, ast.Attribute):
            inner.add(id(nd.value))
    for nd in nodes:
        if isinstance(nd, (ast.Name, ast.Attribute)) and id(nd) not in inner:
            if isinstance(nd, ast.Name) and not isinstance(nd.ctx, ast.Load):
                continue
            yield nd


def _references(target: str) -> dict[str, set[str]]:
    """Every `<module>.<scope>` under `cardlang/` reading a name that
    resolves to `target` or a member of it, with what it reads."""
    modules = _modules()
    resolver = _Resolver(modules)
    found: dict[str, set[str]] = {}
    for module, (_path, tree) in modules.items():
        for qualname, scope in _scopes(tree):
            for nd in _outermost(list(_own_nodes(scope))):
                dotted = resolver.resolve(module, nd)
                if dotted is not None and (dotted == target or dotted.startswith(f"{target}.")):
                    found.setdefault(f"{module}.{qualname}", set()).add(dotted)
    return found


def _legal_cards_callers() -> set[str]:
    modules = _modules()
    resolver = _Resolver(modules)
    callers: set[str] = set()
    for module, (_path, tree) in modules.items():
        for qualname, scope in _scopes(tree):
            for nd in _own_nodes(scope):
                if isinstance(nd, ast.Call) and resolver.resolve(module, nd.func) == (
                    f"{RULES_MODULE}.legal_cards"
                ):
                    callers.add(f"{module}.{qualname}")
    return callers


def _importers(target: str) -> set[str]:
    """The modules under `cardlang/` importing `target`, in any form."""
    found: set[str] = set()
    package, _, leaf = target.rpartition(".")
    for module, (path, tree) in _modules().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                a.name == target or a.name.startswith(f"{target}.") for a in node.names
            ):
                found.add(module)
            elif isinstance(node, ast.ImportFrom):
                source = _absolute(node, module, path)
                if source == target or source.startswith(f"{target}.") or (
                    source == package and any(a.name == leaf for a in node.names)
                ):
                    found.add(module)
    return found


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


def _decision_point_scopes() -> dict[str, str]:
    """Each `DECISION_POINTS` key ("stem.function") -> the dotted scope it
    names; a stem that names more than one module defining the function is
    a failure here, not a guess."""
    resolved: dict[str, str] = {}
    modules = _modules()
    for key in DECISION_POINTS:
        stem, _, function = key.partition(".")
        matches = [
            f"{module}.{qualname}"
            for module, (_path, tree) in modules.items()
            if module.rpartition(".")[2] == stem
            for qualname, _scope in _scopes(tree)
            if qualname == function
        ]
        assert len(matches) == 1, (key, matches)
        resolved[key] = matches[0]
    return resolved


def _round_site(points: dict[str, str]) -> str:
    """The decision point a `round` runs at: the one whose function asks a
    form for its candidates."""
    modules = _modules()
    sites = set()
    for key, dotted in points.items():
        module, _, qualname = dotted.rpartition(".")
        tree = modules[module][1]
        scope = next(s for q, s in _scopes(tree) if q == qualname)
        if any(
            isinstance(nd, ast.Call)
            and isinstance(nd.func, ast.Attribute)
            and nd.func.attr == "candidates"
            for nd in _own_nodes(scope)
        ):
            sites.add(key)
    assert len(sites) == 1, sites
    return sites.pop()


def test_one_module_imports_the_rule_cascade() -> None:
    """red under: add `from . import rules` (or `import
    cardlang.runtime.rules`) to `cardlang/runtime/execute.py` -- the
    importer set gains `cardlang.runtime.execute`."""
    assert _importers(RULES_MODULE) == {MECHANICS}


def test_the_rule_cascade_has_one_caller() -> None:
    """The legal card list is computed from rules at the trick form's
    candidate hook and at no other site.

    red under: in `cardlang/runtime/execute.py`, bind `_LEGAL =
    rules.legal_cards` at module level (with `from cardlang.runtime import
    rules`) and call `_LEGAL(...)` in `execute._offer` -- the caller set
    gains `cardlang.runtime.execute._offer`."""
    assert _legal_cards_callers() == {f"{MECHANICS}.TrickForm.candidates"}


def test_only_the_trick_forms_decision_names_the_rule_cascade() -> None:
    """Of every decision point, fanned out over the round forms, the code
    names `cardlang.runtime.rules` iff the point is the trick form's.

    red under: add `from . import rules` to `cardlang/runtime/execute.py`
    and a `rules.legal_cards(...)` call in `execute._offer` -- the
    actor-only offer site names the cascade; or a load of
    `rules.legal_cards` in `mechanics.ClimbForm.candidates` -- the climb
    form names the cascade."""
    arms = _form_classes()
    assert set(arms) == set(FORM_CONSTRUCTS), (arms, FORM_CONSTRUCTS)
    trick = FORM_CONSTRUCTS[n.TrickRound.__name__]
    points = _decision_point_scopes()
    round_site = _round_site(points)
    references = _references(RULES_MODULE)

    def names_cascade(prefix: str) -> bool:
        return any(key == prefix or key.startswith(f"{prefix}.") for key in references)

    seen: dict[str, bool] = {}
    for key, point in DECISION_POINTS.items():
        if key == round_site:
            continue
        seen[key] = names_cascade(points[key])
        assert seen[key] is (point.construct == trick), (key, point)
    for node_class, form in arms.items():
        seen[form] = names_cascade(f"{MECHANICS}.{form}")
        assert seen[form] is (FORM_CONSTRUCTS[node_class] == trick), (form, seen)
    assert names_cascade(points[round_site]) is False, round_site
    assert sum(seen.values()) == 1, seen


def _constant_occurrences() -> set[str]:
    """Every scope under `cardlang/` where `RULE_ENFORCED_MOVE_TYPE` occurs:
    as a name, an attribute, or an import of it -- under any alias, whose
    names are then followed too -- its definition in its home module
    aside."""
    found: set[str] = set()
    for module, (_path, tree) in _modules().items():
        aliases = {CONSTANT} | {
            a.asname
            for nd in ast.walk(tree)
            if isinstance(nd, ast.ImportFrom)
            for a in nd.names
            if a.name == CONSTANT and a.asname
        }
        for qualname, scope in _scopes(tree):
            for nd in _own_nodes(scope):
                hit = (
                    (isinstance(nd, ast.Name) and nd.id in aliases)
                    or (isinstance(nd, ast.Attribute) and nd.attr == CONSTANT)
                    or (isinstance(nd, ast.alias) and nd.name == CONSTANT)
                )
                if not hit:
                    continue
                defining = (
                    module == CONSTANT_HOME
                    and qualname == MODULE_SCOPE
                    and isinstance(nd, ast.Name)
                    and isinstance(nd.ctx, ast.Store)
                )
                if not defining:
                    found.add(f"{module}.{qualname}")
    return found


def test_the_enforced_move_type_has_two_readers() -> None:
    """The constant naming the move type the cascade is asked about is read
    by its one consumer and by the resolver Owner Guard that refuses a rule
    no site consults, so the Owner Guard cannot drift from the consumer.

    red under: read `RULE_ENFORCED_MOVE_TYPE` in `mechanics.ClimbForm.candidates`
    (compare a value with it) -- the reader set gains
    `cardlang.runtime.mechanics.ClimbForm.candidates`; or bind
    `_ENFORCED = moves.RULE_ENFORCED_MOVE_TYPE` at module level in
    `cardlang/runtime/execute.py` -- the set gains `cardlang.runtime.execute.<module>`;
    or `from cardlang.stdlib.moves import RULE_ENFORCED_MOVE_TYPE as _K` inside
    `execute._offer`, reading `_K` there -- the set gains
    `cardlang.runtime.execute._offer`. The two modules' imports of it are
    their `<module>` scopes."""
    assert _constant_occurrences() == {
        f"cardlang.resolve.{MODULE_SCOPE}",
        "cardlang.resolve._check_rule_reaches_a_reader",
        f"{MECHANICS}.{MODULE_SCOPE}",
        f"{MECHANICS}.TrickForm.candidates",
    }
