"""The zero-consumer report (issue #653): every construct the grammar defines
that no corpus game, library or stdlib rule uses, derived on demand from the
grammar file and the source globs. It is PRINTED, never written -- a
checked-in copy would be the rot this report measures -- and it is a report,
never a gate: surface may land ahead of its first game (decisions.md, the
register-symmetry ruling on the subset folds), so a red here is a row for the
direction review, not a failure.

Run: `python -m tools.dead_surface`

Three sections, each derived:

- Rules and aliases no live file produces. The rule axis is scraped from the
  grammar: every alias, plus every rule that is neither filtered (`_name`) nor
  a precedence level (`?name`, which names a level and not a construct -- the
  constructs at that level are its aliases) and has at least one un-aliased
  alternative; reject-with-replacement twins (`*_reject`) are excluded, being
  produced only to refuse. A rule's consumers are the files whose parse tree
  contains it. A row is dead when no CORPUS or SHARED file produces it; OTHER
  consumers (experiment games, test fixtures) are named beside the row so the
  review sees "only a fixture uses it".
- Keywords no live file writes: every `_X_KW` terminal's word, sought as a
  whole token in each file with comments and string literals stripped.
- General constructs whose every live consumer is a scoring sentence -- the
  check decisions.md "Scoring has no constructs of its own" asks for. A
  scoring sentence is an assignment, or a `let` binding, whose target is the
  game's winner variable (`winner: highest x`) or a name whose value flows
  into it through an assignment or a binding, transitively; a function every
  call of which sits in a scoring sentence counts as one, transitively, its
  calls gathered across every source -- a library function called only from
  games' scoring sentences is scoring surface housed in the library. Names
  resolve lexically: a `let` binds for the rest of its block, a parameter
  within its function, and a state or zone name by spelling within its own
  source; a call's callee is not a read.

Contract (decisions.md "Closed-domain completeness")
---------------------------------------------------
Assumes:      the grammar file and the source globs, nothing else -- no list
              maintained by hand anywhere.
Establishes:  a deterministic text, sorted in every section, identical across
              runs on an unchanged tree.
Now illegal:  a copy of this output under version control.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import sys
from collections.abc import Iterable, Sequence

from lark import Token, Tree

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_to_tree
from tests.keyword_fusion_sweep import code_mask

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "cardlang" / "grammar" / "cardlang.lark"

# The consumer tiers, each a glob under ROOT. Live tiers decide a row; the
# other tier is named beside it.
TIERS: tuple[tuple[str, str], ...] = (
    ("corpus", "docs/games/*.cardlang"),
    ("shared", "docs/libraries/*.cardlang"),
    ("shared", "cardlang/stdlib/*.cardlang"),
    ("other", "experiments/**/*.cardlang"),
    ("other", "tests/**/*.cardlang"),
)
LIVE_TIERS: frozenset[str] = frozenset({"corpus", "shared"})


@dataclasses.dataclass(frozen=True)
class Source:
    """One file (or one synthetic text, in tests) to read consumers from."""

    name: str
    text: str
    start: str  # the grammar start symbol its kind parses under
    tier: str


def start_for(path: pathlib.Path) -> str:
    """A file's kind is its directory's: libraries parse as `library`, the
    stdlib as `stdlib_rules`, everything else as a game."""
    parts = set(path.parts)
    if "libraries" in parts:
        return "library"
    if "stdlib" in parts:
        return "stdlib_rules"
    return "start"


def default_sources(root: pathlib.Path = ROOT) -> list[Source]:
    seen: dict[pathlib.Path, Source] = {}
    for tier, pattern in TIERS:
        for path in sorted(root.glob(pattern)):
            if path in seen:
                continue
            rel = path.relative_to(root).as_posix()
            seen[path] = Source(rel, path.read_text(), start_for(path), tier)
    return [seen[p] for p in sorted(seen)]


# --- the grammar axes ---------------------------------------------------------

_RULE_BLOCK = re.compile(r"^(\??)([a-z][a-z0-9_]*)\s*:(.*?)(?=^\S|\Z)", re.M | re.S)
_ALIAS = re.compile(r"->\s*([a-z][a-z0-9_]*)")
_KEYWORD = re.compile(r'^_([A-Z0-9_]+)_KW:\s*"([^"]+)"', re.M)


def rule_axis(grammar: str) -> frozenset[str]:
    """Every name a parse tree could carry: aliases, and rules that are
    neither filtered nor precedence levels with an un-aliased alternative.
    Reject twins are produced only to refuse, so they are not surface."""
    names: set[str] = set(_ALIAS.findall(grammar))
    for inlined, name, body in _RULE_BLOCK.findall(grammar):
        if inlined or name.startswith("_"):
            continue
        alternatives = [a for a in re.split(r"^\s*\|", body, flags=re.M) if a.strip()]
        if any("->" not in a for a in alternatives):
            names.add(name)
    return frozenset(n for n in names if not n.endswith("_reject"))


def keyword_axis(grammar: str) -> dict[str, str]:
    """Terminal name -> the word a designer writes."""
    return {name: word for name, word in _KEYWORD.findall(grammar)}


# --- reading consumers ---------------------------------------------------------

# A value's identity: ("state", source, name) | ("let", source, offset) |
# ("param", source, function, name). Namespaced by source, so two games'
# `score` never meet.
Identity = tuple[str, ...]
# A function's identity: (source, name) for a game's own function, and
# ("library", name) for a library's, which every game that calls the name
# shares -- two libraries defining one name merge, conservatively.
FunctionId = tuple[str, str]

# A statement that gives a name a value: an assignment's target, or a `let`'s
# bound name. Both are read the same way -- the target is the first child, the
# value the last -- so the dataflow closure and the walk treat them alike.
_BINDING_STATEMENTS: frozenset[str] = frozenset({"assign_stmt", "let_stmt"})


@dataclasses.dataclass
class _Analysis:
    """What one parsed source contributes, before calls are resolved across
    sources: every subtree with the binding it sits in and the function it
    sits in; every call with the same context; every binding's dataflow; the
    winner variable; the functions this source defines; the keywords it
    writes."""

    sites: list[tuple[str, Identity | None, FunctionId | None]]
    calls: list[tuple[str, Identity | None, FunctionId | None]]
    flows: list[tuple[Identity, frozenset[Identity]]]
    winner: Identity | None
    functions: frozenset[str]
    written: frozenset[str]
    library: bool


def _name_tokens(tree: Tree[Token] | Token | None) -> list[str]:
    if tree is None:
        return []
    if isinstance(tree, Token):
        return [str(tree)] if tree.type == "NAME" else []
    return [t for c in tree.children for t in _name_tokens(c)]


def _target_root(target: Tree[Token] | Token | None) -> str | None:
    names = _name_tokens(target)
    return names[0] if names else None


def _analyse(tree: Tree[Token], text: str, source: Source, keywords: dict[str, str]) -> _Analysis:
    """Names resolve lexically as the walk goes: a `let` binds its name for
    the rest of its parent's children, innermost binding first; a function's
    parameters bind within its body; every other name is a state or zone name
    of this source, matched by spelling. A call's callee is not a read."""
    owner = "library" if source.start == "library" else source.name
    winner: Identity | None = None
    for sub in tree.iter_subtrees():
        if str(sub.data) == "winner":
            names = _name_tokens(sub)
            if names:
                winner = ("state", source.name, names[-1])
    sites: list[tuple[str, Identity | None, FunctionId | None]] = []
    calls: list[tuple[str, Identity | None, FunctionId | None]] = []
    flows: list[tuple[Identity, frozenset[Identity]]] = []
    functions: set[str] = set()
    frames: list[dict[str, Identity]] = []

    def resolve(name: str) -> Identity:
        for frame in reversed(frames):
            if name in frame:
                return frame[name]
        return ("state", source.name, name)

    def value_reads(node: Tree[Token] | Token | None) -> frozenset[Identity]:
        found: set[Identity] = set()

        def visit(n: Tree[Token] | Token | None) -> None:
            if n is None:
                return
            if isinstance(n, Token):
                if n.type == "NAME":
                    found.add(resolve(str(n)))
                return
            children = n.children[1:] if str(n.data) == "call" else n.children
            for child in children:
                visit(child)

        visit(node)
        return frozenset(found)

    def walk(node: Tree[Token] | Token | None, binding: Identity | None, function: FunctionId | None) -> None:
        if node is None or isinstance(node, Token):
            return
        rule = str(node.data)
        frames.append({})
        if rule == "function_def":
            names = _name_tokens(node.children[0])
            if names:
                functions.add(names[0])
                function = (owner, names[0])
                if len(node.children) > 2:
                    for param in _name_tokens(node.children[1]):
                        frames[-1][param] = ("param", source.name, names[0], param)
        if rule == "call":
            names = _name_tokens(node.children[0])
            if names:
                calls.append((names[0], binding, function))
        sites.append((rule, binding, function))
        if rule in _BINDING_STATEMENTS:
            target_name = _target_root(node.children[0])
            value = node.children[-1]
            target: Identity | None = None
            if target_name is not None:
                target = (
                    ("let", source.name, str(node.meta.start_pos))
                    if rule == "let_stmt"
                    else resolve(target_name)
                )
                flows.append((target, value_reads(value)))
            for child in node.children[:-1]:
                walk(child, binding, function)
            walk(value, target, function)
            frames.pop()
            if rule == "let_stmt" and target_name is not None and target is not None:
                frames[-1][target_name] = target
            return
        for child in node.children:
            walk(child, binding, function)
        frames.pop()

    walk(tree, None, None)
    # A keyword is written where it stands as a whole word in CODE -- outside
    # comments and strings as the grammar defines them, which is what the
    # fusion sweep's scanner reads; masked characters become spaces so word
    # boundaries and offsets survive.
    code = "".join(ch if keep else " " for ch, keep in zip(text, code_mask(text)))
    written = frozenset(
        name
        for name, word in keywords.items()
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", code)
    )
    return _Analysis(sites, calls, flows, winner, frozenset(functions), written, owner == "library")


def _scoring(analyses: dict[str, _Analysis]) -> tuple[set[Identity], set[FunctionId]]:
    """The identities whose values reach a winner variable, per source, and
    the functions every call of which -- from any source -- sits in a scoring
    sentence, to a fixpoint over both."""
    identities: set[Identity] = set()
    for analysis in analyses.values():
        if analysis.winner is None:
            continue
        reached = {analysis.winner}
        while True:
            grown = set(reached)
            for target, read in analysis.flows:
                if target in reached:
                    grown |= read
            if grown == reached:
                break
            reached = grown
        identities |= reached
    library_functions = {
        name for analysis in analyses.values() if analysis.library for name in analysis.functions
    }
    resolved: list[tuple[FunctionId, Identity | None, FunctionId | None]] = []
    for source, analysis in analyses.items():
        for callee, binding, enclosing in analysis.calls:
            if callee in analysis.functions and not analysis.library:
                resolved.append(((source, callee), binding, enclosing))
            elif callee in library_functions:
                resolved.append((("library", callee), binding, enclosing))
    functions: set[FunctionId] = set()
    while True:
        called = {f for f, _, _ in resolved}
        grown_functions = {
            f
            for f in called
            if all(b in identities or e in functions for g, b, e in resolved if g == f)
        }
        if grown_functions == functions:
            break
        functions = grown_functions
    return identities, functions


# --- the report ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Report:
    parsed: tuple[str, ...]
    unparsed: tuple[str, ...]
    rules: frozenset[str]
    keywords: dict[str, str]
    rule_consumers: dict[str, dict[str, tuple[str, ...]]]  # rule -> tier -> files
    keyword_consumers: dict[str, dict[str, tuple[str, ...]]]
    all_scoring: dict[str, tuple[str, ...]]  # rule -> live files, every consumer scoring

    def dead_rules(self) -> list[str]:
        return sorted(r for r in self.rules if not self._live(self.rule_consumers.get(r, {})))

    def dead_keywords(self) -> list[str]:
        """Terminal names, in the order of the words a designer writes."""
        dead = (k for k in self.keywords if not self._live(self.keyword_consumers.get(k, {})))
        return sorted(dead, key=lambda k: self.keywords[k])

    @staticmethod
    def _live(consumers: dict[str, tuple[str, ...]]) -> bool:
        return any(consumers.get(t) for t in LIVE_TIERS)

    def render(self) -> str:
        lines = [
            "# Dead surface -- derived, never maintained (issue #653)",
            f"files parsed: {len(self.parsed)}; unparsed (skipped): {len(self.unparsed)}",
            "",
            f"## Rules and aliases no corpus, library or stdlib file produces "
            f"({len(self.dead_rules())} of {len(self.rules)})",
        ]
        for rule in self.dead_rules():
            others = self.rule_consumers.get(rule, {}).get("other", ())
            suffix = f"  (only in: {', '.join(others)})" if others else ""
            lines.append(f"- {rule}{suffix}")
        lines += [
            "",
            f"## Keywords no corpus, library or stdlib file writes "
            f"({len(self.dead_keywords())} of {len(self.keywords)})",
        ]
        for name in self.dead_keywords():
            others = self.keyword_consumers.get(name, {}).get("other", ())
            suffix = f"  (only in: {', '.join(others)})" if others else ""
            lines.append(f"- `{self.keywords[name]}`{suffix}")
        lines += [
            "",
            f"## Constructs whose every live consumer is a scoring sentence "
            f"({len(self.all_scoring)})",
        ]
        for rule in sorted(self.all_scoring):
            lines.append(f"- {rule}  ({', '.join(self.all_scoring[rule])})")
        return "\n".join(lines) + "\n"


def report(grammar: str, sources: Iterable[Source]) -> Report:
    rules = rule_axis(grammar)
    keywords = keyword_axis(grammar)
    parsed: list[str] = []
    unparsed: list[str] = []
    analyses: dict[str, _Analysis] = {}
    tiers: dict[str, str] = {}
    for source in sorted(sources, key=lambda s: s.name):
        try:
            tree = parse_to_tree(source.text, source.name, start=source.start)
        except DiagnosticError:
            unparsed.append(source.name)
            continue
        parsed.append(source.name)
        analyses[source.name] = _analyse(tree, source.text, source, keywords)
        tiers[source.name] = source.tier
    identities, functions = _scoring(analyses)
    rule_consumers: dict[str, dict[str, list[str]]] = {}
    keyword_consumers: dict[str, dict[str, list[str]]] = {}
    scoring_by_rule: dict[str, dict[str, bool]] = {}  # rule -> live file -> all scoring there
    for name, analysis in analyses.items():
        produced: dict[str, bool] = {}
        for rule, binding, function in analysis.sites:
            is_scoring = binding in identities or function in functions
            produced[rule] = produced.get(rule, True) and is_scoring
        for rule, scoring in produced.items():
            rule_consumers.setdefault(rule, {}).setdefault(tiers[name], []).append(name)
            if tiers[name] in LIVE_TIERS:
                scoring_by_rule.setdefault(rule, {})[name] = scoring
        for keyword in analysis.written:
            keyword_consumers.setdefault(keyword, {}).setdefault(tiers[name], []).append(name)
    all_scoring = {
        rule: tuple(sorted(files))
        for rule, files in scoring_by_rule.items()
        if rule in rules and files and all(files.values())
    }
    return Report(
        parsed=tuple(parsed),
        unparsed=tuple(unparsed),
        rules=rules,
        keywords=keywords,
        rule_consumers={r: {t: tuple(sorted(f)) for t, f in by.items()} for r, by in rule_consumers.items()},
        keyword_consumers={k: {t: tuple(sorted(f)) for t, f in by.items()} for k, by in keyword_consumers.items()},
        all_scoring=all_scoring,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.parse_args(argv)
    sys.stdout.write(report(GRAMMAR.read_text(), default_sources()).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
