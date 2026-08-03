"""Corpus sweep for the keyword-fusion class: delete a space, does the meaning
survive?

The derivation evidence behind tests/test_keyword_anchoring.py, kept runnable
rather than described. That module's grid is a property of REGEXES over Lark's
terminal table — it proves every terminal is anchored. This proves the thing a
designer actually experiences: that no space in a real game file can be dropped
and still compile to the same program. The two fail on different mistakes. A
grid row appears the moment a new terminal exists; this sweep is what would
catch a fusion the terminal table cannot see at all — a new PRODUCTION shape,
say, or a lexer setting changed underneath both.

Not a test, and deliberately not collected as one: it is ~7.8k Earley parses of
whole games (minutes, not seconds), which is why test_keyword_anchoring.py pins
the fast property and this stays a hand-run tool. Run it when the grammar's
lexical layer changes:

    python -m tests.keyword_fusion_sweep

It exits non-zero if any deletion still parses to an identical tree, so it can
also be dropped into a one-off check without reading the output.

Method: for every whitespace run between two word characters in every
`docs/games/*.cardlang`, delete it and re-parse, then compare normalized trees.
Comment bodies and string literals are masked out first — `%ignore
LINE_COMMENT` means a comment-internal deletion is IDENTICAL by construction
and measures nothing, and before masking they were about 60% of the hits.

Three verdicts:

    IDENTICAL - parses to the same tree: the defect. The engine read a
                sentence the reader did not write.
    DIFFERENT - parses to another tree. Healthy: the fused text is a legal
                identifier (`not acted` -> `notacted`), so the reader reads it
                the way the engine does, and the next pass reports the
                unresolved name.
    REJECTED  - syntax error. The intended outcome for a dropped space.

Against the grammar as it stands every code position is REJECTED or DIFFERENT.
Against the merge base of the change that closed the class (#223/#101), 4761 of
7776 were IDENTICAL. To reproduce that comparison, run the sweep from a
worktree checked out at the older revision — the base grammar is a property of
the tree, so this script needs no revision flag to express it.

red under: drop the `/(?![A-Za-z0-9_])/` lookahead from any keyword terminal in
cardlang.lark. Verified on `_WHERE_KW`, which reddens to 316 IDENTICAL sites —
every `where` in the corpus — attributed to `where` by name, and exit 1. A tool
whose failure path has never run is not evidence, and this one's whole job is
to be evidence.
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from lark import Token, Tree

from cardlang.parse import parse_to_tree

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"
# A whitespace run with a word character on both sides — the gaps a reader sees
# as separating two words, and the only ones a deletion can fuse.
GAP = re.compile(r"(?<=[A-Za-z0-9_])\s+(?=[A-Za-z0-9_])")
# ASCII only, matching the grammar's NAME/INT shapes — `str.isalnum()` would
# admit non-ASCII letters the lexer never accepts.
IS_WORD = re.compile(r"[A-Za-z0-9_]").fullmatch


def code_mask(text: str) -> list[bool]:
    """True where the character is CODE — outside a `//` comment body and
    outside a STRING literal. Scanned rather than regexed so a `//` INSIDE a
    string does not open a comment (grammar: `STRING: /"[^"]*"/`,
    `LINE_COMMENT: /\\/\\/[^\\n]*/`)."""
    mask = [True] * len(text)
    i = 0
    while i < len(text):
        if text[i] == '"':
            end = text.find('"', i + 1)
            end = len(text) - 1 if end < 0 else end
            for k in range(i, end + 1):
                mask[k] = False
            i = end + 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            for k in range(i, end):
                mask[k] = False
            i = end
        else:
            i += 1
    return mask


def normalize(node: object) -> object:
    """A parse tree as plain nested lists — rule names and token type/value
    pairs, no spans. Spans shift when a character is deleted, so comparing them
    would call every mutant different and the sweep would find nothing."""
    if isinstance(node, Tree):
        return [str(node.data)] + [normalize(child) for child in node.children]
    if isinstance(node, Token):
        return [str(node.type), str(node.value)]
    return repr(node)


def word_before(text: str, index: int) -> str:
    start = index
    while start > 0 and IS_WORD(text[start - 1]):
        start -= 1
    return text[start:index]


def word_after(text: str, index: int) -> str:
    end = index
    while end < len(text) and IS_WORD(text[end]):
        end += 1
    return text[index:end]


_TEXTS: dict[str, str] = {}
_BASELINES: dict[str, object] = {}


def _text(game: str) -> str:
    if game not in _TEXTS:
        _TEXTS[game] = (GAMES_DIR / f"{game}.cardlang").read_text()
    return _TEXTS[game]


def _baseline(game: str) -> object:
    if game not in _BASELINES:
        _BASELINES[game] = normalize(parse_to_tree(_text(game), f"{game}.cardlang"))
    return _BASELINES[game]


def sweep_one(job: tuple[str, int, int]) -> tuple[str, str, int, str, str]:
    """One deletion: (verdict, game, line, word before the gap, word after)."""
    game, start, end = job
    text = _text(game)
    mutant = text[:start] + text[end:]
    try:
        got = normalize(parse_to_tree(mutant, f"{game}.cardlang"))
        verdict = "IDENTICAL" if got == _baseline(game) else "DIFFERENT"
    except Exception:
        verdict = "REJECTED"
    return (
        verdict,
        game,
        text.count("\n", 0, start) + 1,
        word_before(text, start),
        word_after(text, end),
    )


def jobs() -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for path in sorted(GAMES_DIR.glob("*.cardlang")):
        text = path.read_text()
        mask = code_mask(text)
        for match in GAP.finditer(text):
            if mask[match.start() - 1] and mask[match.end()]:
                out.append((path.stem, match.start(), match.end()))
    return out


def main() -> int:
    work = jobs()
    if not work:
        print("no corpus gaps found — is docs/games/ populated?", file=sys.stderr)
        return 2
    print(f"sweeping {len(work)} code-position deletions ...", file=sys.stderr)

    results: list[tuple[str, str, int, str, str]] = []
    with Pool(processes=max(1, (os.cpu_count() or 4) - 2)) as pool:
        for i, row in enumerate(pool.imap_unordered(sweep_one, work, chunksize=8)):
            results.append(row)
            if i and i % 1000 == 0:
                print(f"  {i}/{len(work)}", file=sys.stderr, flush=True)

    counts = Counter(verdict for verdict, *_ in results)
    for verdict in ("REJECTED", "DIFFERENT", "IDENTICAL"):
        print(f"{verdict:10} {counts[verdict]:5}")

    fused = [row for row in results if row[0] == "IDENTICAL"]
    if not fused:
        print("\nno fused spelling survives — every dropped space is refused.")
        return 0

    print(f"\n{len(fused)} deletion(s) still parse to an IDENTICAL tree:")
    for word, n in Counter(row[3] for row in fused).most_common():
        print(f"  after {word!r}: {n}")
    print("\nfirst sites:")
    for _, game, line, before, after in sorted(fused, key=lambda r: (r[1], r[2]))[:20]:
        print(f"  {game}:{line}  {before}|{after}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
