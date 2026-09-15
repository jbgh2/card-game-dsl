"""The zero-consumer report (issue #653): every construct the grammar defines
that no corpus game, library or stdlib rule uses, derived on demand from the
grammar file and the source globs. It is PRINTED, never written -- a
checked-in copy would be the rot this report measures -- and it is a report,
never a gate: surface may land ahead of its first game (decisions.md, the
register-symmetry ruling on the subset folds), so a red here is a row for the
direction review, not a failure.

Run: `python -m tools.dead_surface`

Two sections, each derived:

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

Whether a live construct's consumers are only scoring sentences is a
semantic question this report does not ask; it belongs on the checked game,
not the parse tree (issue #664).

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
