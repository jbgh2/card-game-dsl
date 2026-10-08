"""The distance to each Destination -- derived, never maintained.

`python -m tools.destinations [--tracker]` prints, for each Destination in
`docs/roadmap.md` ("Destinations"), the facts the tree and the tracker hold
today that read how far the project is from it. The direction review runs it
as a trend check and judges the distances; this module measures and never
ranks.

What it derives, and from where:

* **OpenSpiel plays every game** -- the registered corpus (`docs/games/`),
  the adapter's declared information-state tensor and its determinization
  hook (`cardlang/openspiel/game.py`, read with `ast`), and, under
  `--tracker`, the read ledger in the generator issue's checkboxes.
* **Python only scores** -- every game-local native function a corpus game
  names: the entries of its `primitives { }` block, and the names in the
  `PRIMITIVE_*` registries of `cardlang/builtins/functions.py` that the
  game writes in code (the `BUILTIN_*` registries are generic natives and
  are not game-local). Each is printed with the module defining it and its
  call sites in the game, so the reader can judge whether the site scores
  or decides legality. The judgment is the review's; the sites are the
  facts.
* **One meaning, written once** -- the grammar's defined rules and keywords
  against the corpus size at every direction-review date (the newest commit
  on main at or before each verdict), compiled with lark. A keyword is a
  distinct spelling: the word a `_KW` terminal names, or a compiled plain
  string terminal that spells a word. Rules added per game added is the
  trend to read.
* **Boards** -- the topology witness ladder in `docs/games/_candidates.md`
  against the corpus games declaring a `grid(` Component Set.

Contract
--------
assumes:     a checkout with the corpus under `docs/games/`, the grammar at
             `cardlang/grammar/cardlang.lark`, and git history reachable from
             `origin/main` (falling back to `main`, then `HEAD`).
establishes: a text report; nothing is written anywhere.
illegal after: nothing -- the module has no side effects.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from lark import Lark

from cardlang.builtins import functions as builtin_registries
from tests.keyword_fusion_sweep import code_mask
from tools.dead_surface import keyword_axis

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "docs" / "games"
GRAMMAR = ROOT / "cardlang" / "grammar" / "cardlang.lark"
RUNTIME = ROOT / "cardlang" / "runtime"
ADAPTER = ROOT / "cardlang" / "openspiel" / "game.py"
CANDIDATES = GAMES_DIR / "_candidates.md"
VERDICTS = ROOT / "docs" / "superpowers" / "direction-reviews"
READ_LEDGER_ISSUE = 469
REPO = "jbgh2/card-game-dsl"


# --- Python only scores -----------------------------------------------------------

_BLOCK_OPEN = re.compile(r"^\s*primitives\s*\{\s*$")
_ENTRY = re.compile(r"^\s*([a-z][a-z0-9_]*)\s*\(")


def declared_primitives(text: str) -> list[str]:
    """The entry names of a game file's `primitives { }` block, in order; empty
    when the file declares none. An entry is a line opening `name(` inside the
    block; continuation lines (`reads ...`) are not entries."""
    names: list[str] = []
    inside = False
    for line in text.splitlines():
        if not inside:
            inside = bool(_BLOCK_OPEN.match(line))
            continue
        if line.strip() == "}":
            break
        m = _ENTRY.match(line)
        if m:
            names.append(m.group(1))
    return names


def registry_natives(registries: object = builtin_registries) -> frozenset[str]:
    """Every name the `PRIMITIVE_*` registries hold -- the game-local natives
    the kernel's slots reach without a declared block. The prefix is the
    registry module's own split between generic and game-local."""
    found: set[str] = set()
    for attr in dir(registries):
        if attr.startswith("PRIMITIVE_"):
            value = getattr(registries, attr)
            if isinstance(value, frozenset):
                found.update(v for v in value if isinstance(v, str))
    return frozenset(found)


def defining_modules(runtime_dir: pathlib.Path) -> dict[str, str]:
    """Function name -> the runtime module (stem) whose top level defines it.
    A name defined twice keeps the first module in path order."""
    out: dict[str, str] = {}
    for path in sorted(runtime_dir.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                out.setdefault(node.name, path.stem)
    return out


@dataclass(frozen=True)
class NativeUse:
    game: str
    name: str
    module: str  # "?" when no runtime module defines the name
    sites: tuple[str, ...]  # the code lines naming it, declaration excluded


def _code_lines(text: str) -> list[str]:
    """The file's lines with comment and string bodies blanked, so a name in
    prose does not count as a site."""
    mask = code_mask(text)
    masked = "".join(ch if keep or ch == "\n" else " " for ch, keep in zip(text, mask, strict=True))
    return masked.splitlines()


def native_uses(game: str, text: str, natives: frozenset[str], modules: dict[str, str]) -> list[NativeUse]:
    """Every game-local native function one game names, with its sites."""
    lines = _code_lines(text)
    declared = declared_primitives(text)
    words = {w for line in lines for w in re.findall(r"[a-z][a-z0-9_]*", line)}
    names = list(declared) + sorted(n for n in natives & words if n not in declared)
    uses: list[NativeUse] = []
    for name in names:
        pattern = re.compile(rf"(?<![a-z0-9_]){re.escape(name)}(?![a-z0-9_])")
        sites = tuple(
            raw.strip()
            for raw, code in zip(text.splitlines(), lines, strict=True)
            if pattern.search(code) and not _ENTRY.match(code)
        )
        uses.append(NativeUse(game, name, modules.get(name, "?"), sites))
    return uses


def corpus_native_uses(
    games_dir: pathlib.Path = GAMES_DIR,
    runtime_dir: pathlib.Path = RUNTIME,
) -> list[NativeUse]:
    natives = registry_natives()
    modules = defining_modules(runtime_dir)
    out: list[NativeUse] = []
    for path in sorted(games_dir.glob("*.cardlang")):
        out.extend(native_uses(path.stem, path.read_text(), natives, modules))
    return out


# --- OpenSpiel plays every game ----------------------------------------------------


def adapter_facts(source: str) -> dict[str, bool | None]:
    """What the adapter declares, read from its source with `ast`: whether the
    game type provides an information-state tensor (None when the keyword is
    not a literal), and whether the state class defines the determinization
    hook OpenSpiel's IS-MCTS family calls."""
    tree = ast.parse(source)
    tensor: bool | None = None
    resample = False
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "provides_information_state_tensor":
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                tensor = node.value.value
        if isinstance(node, ast.ClassDef) and node.name == "CardlangState":
            resample = any(
                isinstance(item, ast.FunctionDef) and item.name == "resample_from_infostate" for item in node.body
            )
    return {"information_state_tensor": tensor, "resample_from_infostate": resample}


_BOX = re.compile(r"^- \[([ x])\] \*\*([a-z0-9-]+)\*\*")


def read_ledger(body: str) -> tuple[list[str], list[str]]:
    """(read, unread) game names from the generator issue's checkboxes."""
    read: list[str] = []
    unread: list[str] = []
    for line in body.splitlines():
        m = _BOX.match(line)
        if m:
            (read if m.group(1) == "x" else unread).append(m.group(2))
    return read, unread


def fetch_issue_body(number: int, repo: str = REPO) -> str:
    out = subprocess.run(
        ["gh", "issue", "view", str(number), "--repo", repo, "--json", "body"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    body = json.loads(out)["body"]
    assert isinstance(body, str)
    return body


# --- One meaning, written once -----------------------------------------------------


@dataclass(frozen=True)
class GrammarPoint:
    label: str
    sha: str
    games: int
    rules: int
    keywords: int


_WORD = re.compile(r"[a-z][a-z_0-9]*")


def keyword_count(grammar: str, compiled: Lark) -> int:
    """Distinct keyword spellings: the words the `_KW` terminals name, together
    with the compiled plain-string terminals that spell a word (the shape a
    keyword has before it is given a `_KW` terminal)."""
    words = set(keyword_axis(grammar).values())
    words.update(
        t.pattern.value for t in compiled.terminals if t.pattern.type == "str" and _WORD.fullmatch(t.pattern.value)
    )
    return len(words)


def grammar_point(label: str, sha: str, grammar: str, game_files: Iterable[str]) -> GrammarPoint:
    compiled = Lark(grammar, parser=None, lexer="basic", start="start")
    rules = len(compiled.grammar.rule_defs)
    games = sum(1 for f in game_files if f.endswith(".cardlang") and not pathlib.Path(f).name.startswith("_"))
    return GrammarPoint(label, sha[:8], games, rules, keyword_count(grammar, compiled))


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def _main_ref() -> str:
    for ref in ("origin/main", "main"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=ROOT, capture_output=True).returncode == 0:
            return ref
    return "HEAD"


def verdict_dates(verdicts: pathlib.Path = VERDICTS) -> list[str]:
    return sorted(p.stem for p in verdicts.glob("????-??-??.md"))


def grammar_history(dates: Sequence[str]) -> list[GrammarPoint]:
    """One point per verdict date (the newest main commit at or before it) and
    one for the checkout's HEAD."""
    ref = _main_ref()
    points: list[GrammarPoint] = []
    grammar_rel = GRAMMAR.relative_to(ROOT).as_posix()
    for date in dates:
        sha = _git("rev-list", "-1", f"--before={date} 23:59:59", ref).strip()
        if not sha:
            continue
        files = _git("ls-tree", "-r", "--name-only", sha, "--", "docs/games").split()
        grammar = _git("show", f"{sha}:{grammar_rel}")
        points.append(grammar_point(date, sha, grammar, files))
    head = _git("rev-parse", "HEAD").strip()
    points.append(
        grammar_point("HEAD", head, GRAMMAR.read_text(), [p.name for p in GAMES_DIR.glob("*.cardlang")])
    )
    return points


# --- Boards ---------------------------------------------------------------------------


def ladder(candidates_text: str) -> list[str]:
    """The `### ` headings under the candidates file's Boards section."""
    rungs: list[str] = []
    inside = False
    for line in candidates_text.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## Boards")
            continue
        if inside and line.startswith("### "):
            rungs.append(line[4:].strip())
    return rungs


def board_games(games_dir: pathlib.Path = GAMES_DIR) -> list[str]:
    out: list[str] = []
    for path in sorted(games_dir.glob("*.cardlang")):
        if any("grid(" in line for line in _code_lines(path.read_text())):
            out.append(path.stem)
    return out


# --- rendering --------------------------------------------------------------------------


def render(
    *,
    uses: Sequence[NativeUse],
    facts: dict[str, bool | None],
    registered: int,
    ledger: tuple[list[str], list[str]] | None,
    history: Sequence[GrammarPoint],
    rungs: Sequence[str],
    boards: Sequence[str],
) -> str:
    out: list[str] = ["# Distance to each Destination -- derived, never maintained", ""]

    out.append("== OpenSpiel plays every game ==")
    out.append(f"registered corpus games: {registered}")
    out.append(f"information-state tensor declared: {facts['information_state_tensor']}")
    out.append(f"determinization hook (resample_from_infostate) defined: {facts['resample_from_infostate']}")
    if ledger is None:
        out.append(f"rules-source reads: not fetched (pass --tracker to read issue #{READ_LEDGER_ISSUE})")
    else:
        read, unread = ledger
        out.append(f"rules-source reads: {len(read)} read, {len(unread)} unread -- unread: {', '.join(unread) or '-'}")
    out.append("")

    out.append("== Python only scores ==")
    by_game: dict[str, list[NativeUse]] = {}
    for use in uses:
        by_game.setdefault(use.game, []).append(use)
    out.append(
        f"games naming native functions: {len(by_game)}; native functions named: {len(uses)}; "
        f"modules: {', '.join(sorted({u.module for u in uses}))}"
    )
    for game, group in sorted(by_game.items()):
        out.append(f"- {game}:")
        for use in group:
            first = use.sites[0] if use.sites else "(declared, never called)"
            if len(first) > 80:
                first = first[:77] + "..."
            out.append(f"    {use.name}  [{use.module}]  sites={len(use.sites)}  e.g. {first}")
    out.append("")

    out.append("== One meaning, written once ==")
    out.append(f"{'verdict':<12}{'commit':<10}{'games':>6}{'rules':>7}{'keywords':>10}")
    for p in history:
        out.append(f"{p.label:<12}{p.sha:<10}{p.games:>6}{p.rules:>7}{p.keywords:>10}")
    out.append("")

    out.append("== Boards ==")
    out.append(f"corpus games on a grid: {', '.join(boards) or '-'}")
    landed = [r for r in rungs if r in boards]
    out.append(f"topology ladder: {len(rungs)} rungs, {len(landed)} in the corpus -- {', '.join(rungs)}")
    return "\n".join(out) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tracker", action="store_true", help="also read the rules-source ledger from the tracker")
    args = parser.parse_args(argv)
    ledger = read_ledger(fetch_issue_body(READ_LEDGER_ISSUE)) if args.tracker else None
    sys.stdout.write(
        render(
            uses=corpus_native_uses(),
            facts=adapter_facts(ADAPTER.read_text()),
            registered=len(list(GAMES_DIR.glob("*.cardlang"))),
            ledger=ledger,
            history=grammar_history(verdict_dates()),
            rungs=ladder(CANDIDATES.read_text()),
            boards=board_games(),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
