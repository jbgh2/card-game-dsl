"""The zero-consumer report (issue #653): every construct the grammar defines
that no corpus game, library or stdlib rule uses, derived on demand from the
grammar file and the source globs. It is PRINTED, never written -- a
checked-in copy would be the rot this report measures -- and it is a report,
never a gate: surface may land ahead of its first game (decisions.md, the
register-symmetry ruling on the subset folds), so a red here is a row for the
direction review, not a failure.

Run: `python -m tools.dead_surface`

Two sections, each derived:

- Rules and aliases no live file produces. The rule axis is read from the
  compiled grammar, walking from its start symbols, and names each node as
  lark's tree builder does: every alias, plus every rule (a template by its
  own name) that is neither filtered (`_name`) nor a precedence level
  (`?name`, which names a level and not a construct -- the constructs at that
  level are its aliases) and has an un-aliased alternative. The walk never
  takes a node the parse builder only refuses -- a reject-with-replacement
  twin (`*_reject`), or any node whose builder method raises on every path --
  so neither it nor a rule only it leads to is on the axis. A rule or
  template no start symbol reaches is a row, since nothing can produce it. A
  rule's consumers are the files whose parse tree contains it. A row is dead
  when no CORPUS or SHARED file produces it; OTHER consumers (experiment
  games, test fixtures) are named beside the row so the review sees "only a
  fixture uses it".
- Keywords no live file writes: every `_X_KW` terminal's word, and every
  alphabetic word of an alternation terminal (`TRANSFER_VERB`'s verbs,
  `RANK_DIR`'s directions), sought as a whole token in each file with
  comments and string literals stripped.

Every dead row carries a class, derived like the row (decisions.md "Surface
totality", minimal and complete): SIBLING -- a dead alternative of a rule, or
word of a terminal, with a live alternative beside it, kept whole with its
family under the direction review's sunset; PLACEHOLDER -- a row whose only
consumers are rejection fixtures, kept for the located message they pin;
REJECT -- a keyword only a reject-with-replacement twin uses; DEAD -- none of
these, surface with no writer and no reason. tests/test_dead_surface_report.py
pins the DEAD class empty on the real tree; the other three are rows for the
review, never failures.

Whether a live construct's consumers are only scoring sentences is a
semantic question this report does not ask; it belongs on the checked game,
not the parse tree (issue #664).

Contract (decisions.md "Closed-domain completeness")
---------------------------------------------------
Assumes:      the grammar file, the parser's start symbols and parse builder,
              and the source globs, nothing else -- no list maintained by
              hand anywhere.
Establishes:  a deterministic text, sorted in every section, identical across
              runs on an unchanged tree.
Now illegal:  a copy of this output under version control.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import inspect
import pathlib
import re
import sys
import textwrap
from collections import defaultdict
from collections.abc import Iterable, Sequence

from lark import Lark, Token, Tree
from lark.grammar import Rule

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _Builder, _parser, parse_to_tree
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

_KEYWORD = re.compile(r'^_([A-Z0-9_]+)_KW:\s*"([^"]+)"', re.M)
# An alternation terminal of alphabetic words: `NAME: /(?:a|b|c)(?![A-Za-z0-9_])/`.
_ALTERNATION = re.compile(
    r"^([A-Z][A-Z0-9_]*):\s*/\(\?:([a-z_]+(?:\|[a-z_]+)+)\)\(\?!\[A-Za-z0-9_\]\)/", re.M
)


def refusing_methods(builder: type) -> frozenset[str]:
    """The builder's node methods that raise on every path: no `return`
    anywhere, and a body that ends in a `raise` or in a call to a `self`
    method that does. Filtered helpers are followed but never named, since no
    node dispatches to them."""
    module = ast.parse(textwrap.dedent(inspect.getsource(builder)))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef))
    methods = {f.name: f for f in cls.body if isinstance(f, ast.FunctionDef)}

    def refuses(name: str, via: frozenset[str]) -> bool:
        method = methods.get(name)
        if method is None or name in via or any(isinstance(x, ast.Return) for x in ast.walk(method)):
            return False
        last = method.body[-1]
        if isinstance(last, ast.Raise):
            return True
        call = last.value if isinstance(last, ast.Expr) else None
        return (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "self"
            and refuses(call.func.attr, via | {name})
        )

    return frozenset(name for name in methods if not name.startswith("_") and refuses(name, frozenset()))


def rule_axis(grammar: str, builder: type = _Builder) -> frozenset[str]:
    """Every name a valid parse tree could carry, read from the compiled
    grammar and named as lark's tree builder names a node: walking from the
    start symbols, each alternative contributes its alias, or its rule (a
    template by its own name) when that rule is neither filtered nor a
    precedence level. The walk never takes a node the parse builder only
    refuses -- a `*_reject` twin, or a node whose builder method raises on
    every path -- so it never reaches a rule only a refusal leads to. A rule
    or template no start symbol reaches is on the axis too, since nothing can
    produce it."""
    start = list(_parser().options.start)
    compiled = Lark(grammar, parser=None, lexer="basic", start=start)
    refusing = refusing_methods(builder)
    alternatives: dict[str, list[Rule]] = defaultdict(list)
    for rule in compiled.rules:
        alternatives[rule.origin.name].append(rule)

    def defined(rule: Rule) -> str:
        return str(rule.options.template_source or rule.origin.name)

    def node(rule: Rule) -> str:
        return str(rule.alias or defined(rule))

    def walk(*, through_refusals: bool) -> list[Rule]:
        taken: list[Rule] = []
        seen: set[str] = set()
        pending = list(start)
        while pending:
            origin = pending.pop()
            if origin in seen:
                continue
            seen.add(origin)
            for rule in alternatives[origin]:
                if not through_refusals and (node(rule).endswith("_reject") or node(rule) in refusing):
                    continue
                taken.append(rule)
                pending.extend(s.name for s in rule.expansion if not s.is_term)
        return taken

    names = {
        node(rule)
        for rule in walk(through_refusals=False)
        if rule.alias or not (rule.origin.name.startswith("_") or rule.options.expand1)
    }
    reached = {defined(rule) for rule in walk(through_refusals=True)}
    unreached = {str(name) for name, *_ in compiled.grammar.rule_defs if name not in reached and not name.startswith("_")}
    return frozenset(names | unreached)


def keyword_axis(grammar: str) -> dict[str, str]:
    """Terminal name -> the word a designer writes."""
    return {name: word for name, word in _KEYWORD.findall(grammar)}


def word_axis(grammar: str) -> dict[str, str]:
    """`TERMINAL:word` -> the word, for every alphabetic word of an alternation
    terminal: a designer's word with no `_X_KW` terminal of its own, sought
    and classed like one, its siblings the terminal's other words."""
    return {
        f"{name}:{word}": word
        for name, body in _ALTERNATION.findall(grammar)
        for word in body.split("|")
    }


@dataclasses.dataclass(frozen=True)
class Structure:
    """What the compiled grammar says about each node's neighbours."""

    siblings: dict[str, frozenset[str]]  # node -> the other producible nodes of its rule
    terminal_nodes: dict[str, frozenset[str]]  # terminal -> every node whose expansion names it
    refused: frozenset[str]  # reject twins and nodes the builder only refuses


def structure(grammar: str, builder: type = _Builder) -> Structure:
    """The sibling and terminal relations over the compiled grammar, named as
    `rule_axis` names nodes; a precedence level's own name is no sibling of
    its aliases, since it names the level and not a construct."""
    start = list(_parser().options.start)
    compiled = Lark(grammar, parser=None, lexer="basic", start=start)
    refusing = refusing_methods(builder)
    by_origin: dict[str, list[Rule]] = defaultdict(list)
    for rule in compiled.rules:
        by_origin[rule.origin.name].append(rule)

    def node(rule: Rule) -> str:
        return str(rule.alias or rule.options.template_source or rule.origin.name)

    def refused(rule: Rule) -> bool:
        name = node(rule)
        return name.endswith("_reject") or name in refusing

    siblings: dict[str, frozenset[str]] = {}
    for origin, rules in by_origin.items():
        names = {node(r) for r in rules if not refused(r)} - {origin}
        for name in names:
            siblings[name] = frozenset(names - {name})
    terminal_nodes: dict[str, set[str]] = defaultdict(set)
    for rule in compiled.rules:
        for symbol in rule.expansion:
            if symbol.is_term:
                terminal_nodes[str(symbol.name)].add(node(rule))
    return Structure(
        siblings=siblings,
        terminal_nodes={t: frozenset(n) for t, n in terminal_nodes.items()},
        refused=frozenset(node(r) for r in compiled.rules if refused(r)),
    )


# --- reading consumers ---------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _Read:
    """What one parsed source contributes."""

    produced: frozenset[str]  # rule and alias names its parse tree carries
    written: frozenset[str]  # keyword terminal names written as whole words


def _read(tree: Tree[Token], text: str, keywords: dict[str, str]) -> _Read:
    produced = frozenset(str(sub.data) for sub in tree.iter_subtrees())
    # A keyword is written where it stands as a whole word in CODE -- outside
    # comments and strings as the grammar defines them, which is what the
    # fusion sweep's scanner reads; masked characters become spaces so word
    # boundaries and offsets survive. The grammar's standalone lexer is not a
    # substitute: it is context-free and splits `as-equally-as-possible`.
    code = "".join(ch if keep else " " for ch, keep in zip(text, code_mask(text)))
    written = frozenset(
        name
        for name, word in keywords.items()
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", code)
    )
    return _Read(produced, written)


# --- the report ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Report:
    parsed: tuple[str, ...]
    unparsed: tuple[str, ...]
    rules: frozenset[str]
    keywords: dict[str, str]
    rule_consumers: dict[str, dict[str, tuple[str, ...]]]  # rule -> tier -> files
    keyword_consumers: dict[str, dict[str, tuple[str, ...]]]
    shape: Structure

    def dead_rules(self) -> list[str]:
        return sorted(r for r in self.rules if not self._live(self.rule_consumers.get(r, {})))

    def dead_keywords(self) -> list[str]:
        """Terminal names, in the order of the words a designer writes."""
        dead = (k for k in self.keywords if not self._live(self.keyword_consumers.get(k, {})))
        return sorted(dead, key=lambda k: self.keywords[k])

    @staticmethod
    def _live(consumers: dict[str, tuple[str, ...]]) -> bool:
        return any(consumers.get(t) for t in LIVE_TIERS)

    def rule_classes(self) -> dict[str, tuple[str, str]]:
        """Each dead rule's class and the reason it names: a live sibling, the
        fixture that pins its message, or nothing."""
        out: dict[str, tuple[str, str]] = {}
        for rule in self.dead_rules():
            live = sorted(
                s for s in self.shape.siblings.get(rule, ()) if self._live(self.rule_consumers.get(s, {}))
            )
            if live:
                out[rule] = ("sibling", live[0])
                continue
            others = self.rule_consumers.get(rule, {}).get("other", ())
            fixtures = [f for f in others if f.startswith("tests/rejections/")]
            if fixtures and len(fixtures) == len(others):
                out[rule] = ("placeholder", fixtures[0])
                continue
            out[rule] = ("dead", "")
        return out

    def keyword_classes(self) -> dict[str, tuple[str, str]]:
        """Each dead keyword's class: a word takes the class of the live word
        beside it in its terminal, and a keyword the class of the rules that
        name it -- a sibling row first, then a reject arm (every node naming
        the terminal is a refused one), then a placeholder, else dead."""
        rules = self.rule_classes()
        out: dict[str, tuple[str, str]] = {}
        for key in self.dead_keywords():
            # A `_X_KW` keyword is keyed by its bare name; a word by `TERMINAL:word`.
            terminal, _, word = key.partition(":")
            if not word:
                terminal = f"_{key}_KW"
            if word:
                live_words = sorted(
                    self.keywords[k]
                    for k in self.keywords
                    if k.startswith(terminal + ":") and k != key and self._live(self.keyword_consumers.get(k, {}))
                )
                if live_words:
                    out[key] = ("sibling", live_words[0])
                    continue
            nodes = sorted(self.shape.terminal_nodes.get(terminal, ()))
            classed = [rules[n] for n in nodes if n in rules]
            sibling = next((c for c in classed if c[0] == "sibling"), None)
            # A reject arm is a keyword ONLY refused nodes name: one accepted
            # node beside the twins makes it accepted surface nobody writes.
            twin = nodes[0] if nodes and all(n in self.shape.refused for n in nodes) else None
            placeholder = next((c for c in classed if c[0] == "placeholder"), None)
            out[key] = sibling or (("reject", twin) if twin else None) or placeholder or ("dead", "")
        return out

    @staticmethod
    def _note(cls: str, why: str) -> str:
        return {
            "sibling": f"[sibling of {why}]",
            "placeholder": f"[placeholder, message pinned by {why}]",
            "reject": f"[reject arm: {why}]",
            "dead": "[dead]",
        }[cls]

    def render(self) -> str:
        lines = [
            "# Dead surface -- derived, never maintained (issue #653)",
            f"files parsed: {len(self.parsed)}; unparsed (skipped): {len(self.unparsed)}",
            "",
            f"## Rules and aliases no corpus, library or stdlib file produces "
            f"({len(self.dead_rules())} of {len(self.rules)})",
        ]
        rule_classes = self.rule_classes()
        for rule in self.dead_rules():
            others = self.rule_consumers.get(rule, {}).get("other", ())
            suffix = f"  (only in: {', '.join(others)})" if others else ""
            lines.append(f"- {rule}  {self._note(*rule_classes[rule])}{suffix}")
        lines += [
            "",
            f"## Keywords no corpus, library or stdlib file writes "
            f"({len(self.dead_keywords())} of {len(self.keywords)})",
        ]
        keyword_classes = self.keyword_classes()
        for name in self.dead_keywords():
            others = self.keyword_consumers.get(name, {}).get("other", ())
            suffix = f"  (only in: {', '.join(others)})" if others else ""
            lines.append(f"- `{self.keywords[name]}`  {self._note(*keyword_classes[name])}{suffix}")
        return "\n".join(lines) + "\n"


def report(grammar: str, sources: Iterable[Source]) -> Report:
    rules = rule_axis(grammar)
    keywords = keyword_axis(grammar) | word_axis(grammar)
    parsed: list[str] = []
    unparsed: list[str] = []
    rule_consumers: dict[str, dict[str, list[str]]] = {}
    keyword_consumers: dict[str, dict[str, list[str]]] = {}
    for source in sorted(sources, key=lambda s: s.name):
        try:
            tree = parse_to_tree(source.text, source.name, start=source.start)
        except DiagnosticError:
            unparsed.append(source.name)
            continue
        parsed.append(source.name)
        read = _read(tree, source.text, keywords)
        for rule in read.produced:
            rule_consumers.setdefault(rule, {}).setdefault(source.tier, []).append(source.name)
        for name in read.written:
            keyword_consumers.setdefault(name, {}).setdefault(source.tier, []).append(source.name)
    return Report(
        parsed=tuple(parsed),
        unparsed=tuple(unparsed),
        rules=rules,
        keywords=keywords,
        rule_consumers={r: {t: tuple(sorted(f)) for t, f in by.items()} for r, by in rule_consumers.items()},
        keyword_consumers={k: {t: tuple(sorted(f)) for t, f in by.items()} for k, by in keyword_consumers.items()},
        shape=structure(grammar),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.parse_args(argv)
    sys.stdout.write(report(GRAMMAR.read_text(), default_sources()).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
