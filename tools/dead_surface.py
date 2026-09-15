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
  compiled grammar, walking from its start symbols: every alias, plus every
  rule that is neither filtered (`_name`) nor a precedence level (`?name`,
  which names a level and not a construct -- the constructs at that level are
  its aliases) and has an un-aliased alternative. The walk never takes a
  reject-with-replacement twin (`*_reject`), so neither a twin nor a rule
  only a twin leads to is on the axis: both are produced only to refuse. A
  rule no start symbol reaches is a row, since nothing can produce it. A
  rule's consumers are the files whose parse tree contains it. A row is dead
  when no CORPUS or SHARED file produces it; OTHER consumers (experiment
  games, test fixtures) are named beside the row so the review sees "only a
  fixture uses it".
- Keywords no live file writes: every `_X_KW` terminal's word, sought as a
  whole token in each file with comments and string literals stripped.

Whether a live construct's consumers are only scoring sentences is a
semantic question this report does not ask; it belongs on the checked game,
not the parse tree (issue #664).

Contract (decisions.md "Closed-domain completeness")
---------------------------------------------------
Assumes:      the grammar file, the parser's start symbols and the source
              globs, nothing else -- no list maintained by hand anywhere.
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
from collections import defaultdict
from collections.abc import Iterable, Sequence

from lark import Lark, Token, Tree
from lark.grammar import Rule

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _parser, parse_to_tree
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


def rule_axis(grammar: str) -> frozenset[str]:
    """Every name a valid parse tree could carry, read from the compiled
    grammar: walking from the start symbols, each alternative contributes its
    alias, or its rule when that rule is neither filtered nor a precedence
    level. The walk never takes a reject twin, because a twin is produced only
    to refuse and so is every rule only a twin leads to. A rule no start
    symbol reaches is on the axis too, since nothing can produce it."""
    start = list(_parser().options.start)
    compiled = Lark(grammar, parser=None, lexer="basic", start=start)
    alternatives: dict[str, list[Rule]] = defaultdict(list)
    for rule in compiled.rules:
        alternatives[rule.origin.name].append(rule)

    def walk(*, through_twins: bool) -> list[Rule]:
        taken: list[Rule] = []
        seen: set[str] = set()
        pending = list(start)
        while pending:
            origin = pending.pop()
            if origin in seen:
                continue
            seen.add(origin)
            for rule in alternatives[origin]:
                if not through_twins and (rule.alias or "").endswith("_reject"):
                    continue
                taken.append(rule)
                pending.extend(s.name for s in rule.expansion if not s.is_term)
        return taken

    names = {
        str(rule.alias or rule.origin.name)
        for rule in walk(through_twins=False)
        if rule.alias or not (rule.origin.name.startswith("_") or rule.options.expand1)
    }
    reached = {str(rule.origin.name) for rule in walk(through_twins=True)}
    unreached = {str(name) for name, *_ in compiled.grammar.rule_defs if name not in reached and not name.startswith("_")}
    return frozenset(names | unreached)


def keyword_axis(grammar: str) -> dict[str, str]:
    """Terminal name -> the word a designer writes."""
    return {name: word for name, word in _KEYWORD.findall(grammar)}


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
        return "\n".join(lines) + "\n"


def report(grammar: str, sources: Iterable[Source]) -> Report:
    rules = rule_axis(grammar)
    keywords = keyword_axis(grammar)
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
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.parse_args(argv)
    sys.stdout.write(report(GRAMMAR.read_text(), default_sources()).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
