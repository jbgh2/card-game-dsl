"""T3: inline-vs-`run` (docs/design-notes/metamorphic-suite.md, item 2).

For every `run NAME(args)` call site, splices the named `procedure`'s body in
at SOURCE-TEXT level — never touching the parsed AST, and in particular never
calling `cardlang.expand` or its `substitute` helper. The plan is explicit
about why: "the choice is confirmed at implementation time" to prefer the
source splice over comparing against `expand`'s own output, "which would
share code with the thing under test." A text-level reimplementation is a
genuinely independent check: if this module's splice and `cardlang.expand`
ever disagree, that is real information, not a shared bug replaying itself
twice.

Domain: exactly two corpus games. `docs/games/coup.cardlang` and
`docs/games/cheat.cardlang` are the only `.cardlang` files declaring a
`procedure` or using `run` (grepped, not assumed —
`test_inline.py::test_run_and_procedure_domain_is_pinned` pins the set, so
this residual is a falsifiable fact, not a guess). Cheat's one procedure
(`resolve_play`, called from its four play effects with the bare argument
`actor`) sits inside the same shape envelope Coup established — every
soundness condition below holds for it verbatim, checked by the same
parametrized tests, so no splice generalization was needed when it joined;
a third game outside the envelope still triggers one.

The splice, and why it is sound for this specific shape (not a general
`run`-inlining engine): each call site becomes

    let <fresh>_<param1> = <arg1>
    let <fresh>_<param2> = <arg2>
    <body, with each bare occurrence of a parameter name rewritten to the
     matching `<fresh>_<param>`>

mirroring `cardlang.expand`'s own documented hygiene (decisions.md "Named
procedures"; `cardlang/expand.py`'s module docstring) — each argument
evaluated exactly once, in the caller's context, before the body runs. The
AST version uses an unspellable `@name.param` temporary (`@`/`.` are outside
the NAME terminal, cardlang.lark); a SOURCE-TEXT splice must stay lexable, so
the temporary here is instead a long, corpus-checked-fresh identifier
(`_t3_<proc>_<param>`, verified absent from the source text before use — the
same freshness discipline `rename.py` uses for T2, applied to source
characters instead of AST tokens).

This is sound for the pinned two-game domain specifically because: no
procedure body itself contains a `run` — a LANGUAGE-LEVEL guarantee, not
merely true of these games' text: `resolve.py`'s `_check_procedures` rejects
"a procedure may not invoke another (v1 — expansion is a single splice, not
a call graph)", so no corpus game that passes resolve (all of them) could
have nested calls to splice in sequence. Every
argument is a bare identifier or bare enum literal (checked by
`test_inline.py`, since nothing guards this the way nesting is guarded) — no
argument expression has a side effect a naive re-evaluation could duplicate
(moot here regardless, since this transform binds each argument via `let`
exactly once, matching expand.py), and a bare-name/literal argument also
means the WHOLE-WORD parameter-name rewrite inside a call site's OWN
argument list can never accidentally rewrite the thing being passed in.
Every call site already sits inside a `{ }` block (a move-type effect or an
`if` body — also checked, not guarded), so splicing multiple `let` + body
statements in place of one `run` line never needs to introduce braces of its
own. A general inliner would additionally need to: parse arbitrary argument
expressions (balanced-paren/bracket comma splitting, implemented here
defensively even though no pinned game exercises it); and wrap
multi-statement splices in a brace pair for the single-statement grammar
slots (`for each <role> <binder>: <stmt>`) this transform does not attempt,
because no pinned game calls `run` from one. Extending to a game outside
this envelope is future work, not assumed to be free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PROCEDURE_HEADER = re.compile(r"\bprocedure\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{")
_RUN_CALL = re.compile(r"\brun\s+([A-Za-z_]\w*)\s*\(")


def _strip_comment(line: str) -> str:
    """A line with any `//`-comment tail removed, for brace-counting only —
    never applied to text that ends up in the output."""
    idx = line.find("//")
    return line if idx == -1 else line[:idx]


def _match_brace(text: str, open_brace: int) -> int:
    """The index of the `{` at `open_brace`'s matching `}`, counting braces
    line by line with comment tails stripped (this grammar has no multi-line
    comments and no string literals, so a per-line strip is exact, not a
    heuristic)."""
    assert text[open_brace] == "{"
    depth = 0
    i = open_brace
    n = len(text)
    while i < n:
        # Find the end of the current line, strip its comment tail once, and
        # only count braces within the stripped portion actually reached.
        eol = text.find("\n", i)
        line_end = n if eol == -1 else eol
        line = text[i:line_end]
        stripped = _strip_comment(line)
        for j, ch in enumerate(stripped):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + j
        i = line_end + 1
    raise ValueError(f"unbalanced braces starting at offset {open_brace}")


def _split_args(text: str) -> list[str]:
    """Top-level comma split, depth-aware over `()[]`  — defensive (Coup's
    own arguments are always bare names/literals with no nested punctuation),
    matching the general shape a `run` argument list could take."""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


@dataclass(frozen=True)
class _Procedure:
    name: str
    params: tuple[str, ...]
    body: str  # source text strictly between the outer `{` and `}`, exclusive


def _parse_procedures(text: str) -> dict[str, _Procedure]:
    procs: dict[str, _Procedure] = {}
    for m in _PROCEDURE_HEADER.finditer(text):
        name = m.group(1)
        params = tuple(
            p.split(":")[0].strip() for p in _split_args(m.group(2)) if p.strip()
        )
        open_brace = m.end() - 1
        close_brace = _match_brace(text, open_brace)
        procs[name] = _Procedure(name=name, params=params, body=text[open_brace + 1 : close_brace])
    return procs


def _fresh_prefix(text: str, proc: str, param: str) -> str:
    base = f"_t3_{proc}_{param}"
    candidate = base
    counter = 0
    # `\b` word-boundary containment check: `candidate` must not appear as a
    # substring-with-word-boundaries anywhere in the ORIGINAL text, so it
    # cannot collide with anything a human wrote (mirrors rename.py's
    # freshness discipline).
    while re.search(rf"\b{re.escape(candidate)}\b", text):
        counter += 1
        candidate = f"{base}_{counter}"
    return candidate


def _substitute_params(body: str, params: tuple[str, ...], fresh: dict[str, str]) -> str:
    out = body
    for p in params:
        out = re.sub(rf"\b{re.escape(p)}\b", fresh[p], out)
    return out


def splice_procedures(text: str) -> str:
    """The T3 transform proper: source text -> source text. Removes every
    `procedure` declaration and replaces every `run NAME(args)` call with a
    `let`-bound prologue plus the named procedure's body, substituted
    hygienically (module docstring)."""
    procs = _parse_procedures(text)
    if not procs:
        return text  # nothing to splice; caller decides whether that's a problem

    # Splice call sites first (procedure bodies are still present in `text`
    # at this point, but no call site lies WITHIN a procedure body — that
    # would be a nested `run`, which resolve's `_check_procedures` guard
    # rejects language-wide — so processing them in file order and
    # patching from the end backward is safe and simple).
    edits: list[tuple[int, int, str]] = []  # (start, end, replacement), any order
    for m in _RUN_CALL.finditer(text):
        name = m.group(1)
        if name not in procs:
            continue  # not a procedure call this transform knows about
        proc = procs[name]
        args_start = m.end()
        close_paren = _find_matching_paren(text, args_start - 1)
        args = _split_args(text[args_start:close_paren])
        if len(args) != len(proc.params):
            raise ValueError(
                f"run {name}(...): {len(args)} argument(s) for "
                f"{len(proc.params)} declared parameter(s) — the game and "
                f"this splicer's argument count disagree"
            )
        fresh = {p: _fresh_prefix(text, name, p) for p in proc.params}
        prologue = "".join(
            f"let {fresh[p]} = {arg}\n" for p, arg in zip(proc.params, args)
        )
        spliced_body = _substitute_params(proc.body, proc.params, fresh)
        edits.append((m.start(), close_paren + 1, prologue + spliced_body))

    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + replacement + text[end:]

    # Now remove every procedure declaration itself — re-locate headers in
    # the (call-site-spliced) text, since earlier edits may have shifted
    # offsets found by the first `_parse_procedures` pass.
    proc_edits: list[tuple[int, int]] = []
    for m in _PROCEDURE_HEADER.finditer(text):
        open_brace = m.end() - 1
        close_brace = _match_brace(text, open_brace)
        proc_edits.append((m.start(), close_brace + 1))
    for start, end in sorted(proc_edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + text[end:]

    return text


def _find_matching_paren(text: str, open_paren: int) -> int:
    assert text[open_paren] == "("
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced parens starting at offset {open_paren}")
