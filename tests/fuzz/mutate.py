"""T2: corpus-mutation operators (grammar-fuzzing.md, "Stage 1 — corpus mutation").

Five line/token-level operators over a corpus game's raw text, matching the
plan's list exactly: delete a clause/line, duplicate a declaration, swap
adjacent tokens, rename one occurrence of an identifier, truncate a block.
Each is a pure `(text, rng) -> text | None` function — `None` means the
operator found nothing eligible in this particular file (e.g. no identifier
for `rename_identifier` to touch), which the caller treats as "no mutant
produced," not a finding.

Determinism (grammar-fuzzing.md, "CI is deterministic"). `mutate_text` seeds
`random.Random` from a `"<label>:<operator>:<seed>"` string, never from the
builtin `hash()` — `random.Random(str)` has a documented, PYTHONHASHSEED-
independent seeding algorithm (it hashes the string's bytes with its own
stable scheme), so the same triple reproduces the identical mutant across
processes and interpreters. The builtin would not: `hash(str)` carries the
`PYTHONHASHSEED` salt, so a mutant keyed on it reproduces only inside the one
process that produced it — a reproduction the environment owns rather than
this module.

These operators are deliberately syntax-unaware: they see the corpus file as
lines and tokens, not as a parse tree. That is the point — a mutation that
"knows" the grammar can only ever produce inputs the grammar already
describes, which is exactly what the corpus tests today. A mutation that
does NOT know the grammar is what finds the parser/resolver/typechecker
boundary cases nobody wrote a misuse probe for (module docstring of
`oracle.py` has the full oracle contract).

Contract (decisions.md "Closed-domain completeness", write-time triage)
-------------------------------------------------------------------------
Assumes:      `text` is a corpus game's raw `.cardlang` source (or a
              standalone DSL snippet with the same line/token shape); `rng`
              is a already-seeded `random.Random` the caller owns.
Establishes:  a mutated text, or `None` if this operator is inapplicable to
              this text. Every operator is pure — it never touches the
              filesystem or `cardlang/`.
Now illegal:  nothing downstream — this is leaf generator machinery. The
              mutated text is untrusted input to the oracle (`oracle.py`),
              never assumed parseable.
Verified by:  `test_mutate.py` (each operator individually, on a synthetic
              fixture) and `test_fuzz.py` (the full corpus sweep, T2/T3).
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable

Mutator = Callable[[str, random.Random], "str | None"]

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# A "declaration line" for `duplicate_declaration`: a top-level construct
# keyword followed by a name (phase/rule/type/define/procedure/function/
# move_type), OR a `name : Type` / `name[key] : Type` entry — the shape zone
# and state-variable declarations both take. Not grammar-exact (this module
# is deliberately syntax-unaware, see module docstring) — a heuristic wide
# enough to hit real declarations across the corpus's varied files.
_DECLARATION_LINE_RE = re.compile(
    r"^\s*("
    r"(phase|rule|type|define|procedure|function|move_type)\s+\w+"
    r"|\w+(\[\w+\])?\s*:\s*\S+"
    r")"
)


def delete_line(text: str, rng: random.Random) -> str | None:
    """Delete one non-blank line."""
    lines = text.splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines) if line.strip()]
    if not candidates:
        return None
    i = rng.choice(candidates)
    return "".join(lines[:i] + lines[i + 1 :])


def duplicate_declaration(text: str, rng: random.Random) -> str | None:
    """Insert a second copy of a declaration-shaped line right after itself —
    the shape most likely to trip a duplicate-name guard in resolve."""
    lines = text.splitlines(keepends=True)
    candidates = [i for i, line in enumerate(lines) if _DECLARATION_LINE_RE.match(line)]
    if not candidates:
        return None
    i = rng.choice(candidates)
    return "".join(lines[: i + 1] + [lines[i]] + lines[i + 1 :])


def swap_adjacent_tokens(text: str, rng: random.Random) -> str | None:
    """Swap two adjacent space-separated tokens on one line."""
    lines = text.splitlines(keepends=True)
    eligible: list[tuple[int, list[int]]] = []
    for i, line in enumerate(lines):
        body = line.removesuffix("\n")
        tokens = body.split(" ")
        nonempty = [j for j, t in enumerate(tokens) if t]
        if len(nonempty) >= 2:
            eligible.append((i, nonempty))
    if not eligible:
        return None
    i, nonempty = rng.choice(eligible)
    line = lines[i]
    eol = "\n" if line.endswith("\n") else ""
    body = line[:-1] if eol else line
    tokens = body.split(" ")
    a = rng.randrange(len(nonempty) - 1)
    j1, j2 = nonempty[a], nonempty[a + 1]
    tokens[j1], tokens[j2] = tokens[j2], tokens[j1]
    lines[i] = " ".join(tokens) + eol
    return "".join(lines)


def rename_identifier(text: str, rng: random.Random) -> str | None:
    """Rename exactly ONE occurrence of an identifier (leaving every other
    occurrence — including the declaration it may be renaming away from, or
    a sibling use it now dangles — untouched). This is the operator aimed
    squarely at resolve's undefined-name / mismatched-reference guards."""
    matches = list(_IDENTIFIER_RE.finditer(text))
    if not matches:
        return None
    m = rng.choice(matches)
    start, end = m.span()
    return text[:start] + m.group(0) + "_MUT" + text[end:]


def truncate_block(text: str, rng: random.Random) -> str | None:
    """Cut the file off partway through — the truncated tail almost always
    leaves unbalanced braces, aimed at the parser's error recovery/reporting
    rather than resolve or typecheck."""
    lines = text.splitlines(keepends=True)
    if len(lines) < 4:
        return None
    i = rng.randrange(2, len(lines) - 1)
    return "".join(lines[:i])


MUTATORS: dict[str, Mutator] = {
    "delete_line": delete_line,
    "duplicate_declaration": duplicate_declaration,
    "swap_adjacent_tokens": swap_adjacent_tokens,
    "rename_identifier": rename_identifier,
    "truncate_block": truncate_block,
}


def mutate_text(text: str, operator: str, seed: int, *, label: str) -> str | None:
    """Apply `MUTATORS[operator]` to `text` under a seed deterministically
    derived from `(label, operator, seed)` (module docstring, "Determinism")."""
    rng = random.Random(f"{label}:{operator}:{seed}")
    return MUTATORS[operator](text, rng)
