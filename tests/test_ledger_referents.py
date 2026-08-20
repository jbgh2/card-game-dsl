"""Every reference a completeness ledger writes still resolves.

A completeness ledger (decisions.md "Closed-domain completeness") is prose
asserting facts about code, and its `covered:` row is defined as an executed
grid row -- so every sentence in it reads as backed. Nothing checked that the
things those sentences NAME still exist. `tests/test_movement_verbs.py` cited
a test its own rename had moved out from under it (commit 568297f) and went on
reading as authoritative; `tests/test_cell_queries.py` cited a module by a name
no file has ever carried.

This module holds the half of decisions.md "A quantified `covered` sentence
names its set" that a matcher reaches: a reference must resolve, and a
quantified completeness claim must name the set it quantifies over. It does
NOT reach the claim that names a real test which does not test what the row
says -- see `residual`.

The rule names `registry:` and `covered:`; the sweep here covers every row of
both ledger templates. Restricting it to two would be a hand-picked subset of
a class whose other members were already drifting (danglers were found in
`domain:`, `sampled:` and `residual:` too) -- completeness by superset, never
by judgment (CLAUDE.md).

Completeness ledger (decisions.md "Closed-domain completeness"):

property:   a reference written inside a completeness ledger resolves to
            something the tree holds -- a defined test, a tracked file, an
            importable attribute -- and a quantified completeness claim in a
            `covered:` row names its set with one of them. A reference that
            stopped resolving fails loudly, in the layer that owns ledger
            prose: this test.
domain:     every ledger docstring in the tree, crossed with every reference
            form in `REFERENCE_FORMS` and with the row the reference sits in.
            The row axis is total by construction -- a row label outside the
            derived set is not a ledger row and its prose is not read. Rows
            are MUST-EXIST prose only: `red under:` states the mutation that
            has deliberately NOT been made, so its referents must not
            resolve, and `_rows` cuts it -- as a block and inline, because it
            runs on inside a row in eight modules.
registry:   the row axis is DERIVED by `_fence_labels` from the two templates
            that define it, the `decisions.md` fence under "the **completeness
            ledger** in the grid module's docstring:" and the
            `surface-totality-audit` skill's two fences, reconciled by
            `test_the_row_axis_is_derived_from_its_two_templates` (one domain,
            three sites, and a row added to a template joins the sweep without
            an edit here). The resolution universes are derived from the tree,
            not listed: `_defined_test_names` walks every tracked `.py` for
            `test*` functions, `_tracked` is `git ls-files`, and
            `_top_level_dirs` is that walk's own first path segments. The
            reference forms are `REFERENCE_FORMS`, hand-listed and defended by
            a reach probe per form rather than by derivation -- the same
            structure, and the same reason, as `_ADJACENCY` in
            `tests/test_native_classification_prose.py`.
covered:    the grid IS the coverage -- `test_grid` over `_cells`, which
            crosses `REFERENCE_FORMS` x `LEDGER_ROWS` x {resolving,
            dangling} in code, reading its sentences from `_GOOD` and `_BAD`
            and its expected column from `_expected_flagged`, authored from
            the law before the matcher existed (run red: 43 failed, 60
            passed, 2026-08-20). `test_each_form_is_matched` adds one row
            per member of `REFERENCE_FORMS`, on a sentence carrying a
            KNOWN-bad referent, so a drifted pattern cannot leave the sweep
            reporting clean. The polarity cut has both its shapes probed
            (`test_red_under_prose_is_not_read_as_a_reference`) and its
            over-reach probed against
            (`test_the_red_under_cut_does_not_swallow_the_row`).
            `test_every_ledger_reference_resolves` runs the matcher over
            every ledger `_ledgers` finds; its vacuity is guarded by
            `test_the_walk_sees_this_module`,
            `test_the_ledger_population_is_non_empty` and
            `test_the_resolution_universes_are_non_empty`.
sampled:    the line-wrap rejoin (`_join_rows`) is proven on two examples
            rather than over a derived set of wrapping shapes:
            `test_a_wrapped_reference_resolves` and
            `test_a_wrapped_reference_can_still_dangle`. The wrapping shapes a
            docstring can produce are a formatting space, not a registry; what
            the two probes pin is the property that matters, that rejoining
            neither invents a resolution nor hides a dangling one. The rejoin
            covers the two continuation characters a reference is split on
            here, `_` and `/`; a split elsewhere is residual (e).
residual:   (a) SEMANTIC overclaim -- a `covered:` row naming a real test that
            does not test what the row says -- is out of domain. Every claim
            this module makes about such a row is true. It is the shape that
            issue #389 was filed over, and no matcher reaches it; the
            mechanism is review, and the write-time step is the
            `surface-totality-audit` skill's Step 3. R3, this ledger owns the
            record: the guard is the skill step, and the reachability is the
            same as #389's.
            (b) A quantifier at a DISTANCE from its set -- named a sentence
            away, as "the arms are enumerated below. Every one is probed" --
            is out of the `quantified-claim` form: the form matches a
            quantifier, its noun phrase and a coverage predicate in one span,
            and `_sentence_at` then looks for the set across the sentence
            that span sits in, no further. Matching the
            unnamed-quantifier population generally was measured and refused:
            `covered:` rows carry 299 quantifier occurrences over 87 ledgers,
            and requiring a nearby identifier flags 40 to 76 modules depending
            on the window -- at the tightest positional anchoring, still 30
            occurrences across 24 modules, nearly all correct prose that names
            its set in English ("all 28 French cells (7 decks x 4 conventions,
            frozen expected tuples)"). A matcher that reddens those is
            stricter than the law it mechanizes (measured 2026-08-20, `main`
            at `591e44f`). R3, guarded by the same skill step as (a); the
            standing question of whether `covered:` may hold navigational
            prose at all is issue #392.
            (c) A bare UPPERCASE identifier in backticks (`ZONE_INDEX_ROLES`,
            `RANK_DIR`) is not resolved here. Measured over these ledgers,
            those tokens span at least four namespaces -- Python constants,
            `.lark` terminals, environment variables and prefix families like
            `BUILTIN_` -- so 23 of them resolve to no Python name while being
            correct prose. Admitting them needs the declared exception list
            issue #110 designs, and building a second one here would give one
            domain two definition sites. R4, issue #110.
            (d) A file reference outside this tree -- pytest's own
            `python.py`, a synthetic fixture path (`pkg/domains.py`), a
            deliberately-retired path (`runtime/stdlib.py`) -- is out of
            domain by `_FILE_REF`, which admits a path only under a tracked
            top-level directory or a bare `test_*.py`. This is the same
            forward-reference problem as (c) and has the same answer. R4,
            issue #110.
            (e) Reference SHAPES outside `REFERENCE_FORMS`, from the framing
            check's inventory: a pytest node id (which needs collection, not
            a scrape), `path:LINE`, a brace expansion, a glob or template
            path, an elided-prefix continuation (`.board_entry` after
            `BoardEntry`), a `.lark` terminal or production name, an
            unbackticked bare basename, and a `docs/` path. Each is a
            distinct resolution oracle, and admitting one admits its
            false-positive population with it; the forms here are the ones
            whose oracle is a tracked file, a collected name or an import.
            The largest known miss is a reference wrapping a line break
            somewhere other than an underscore or a slash -- a hyphenated
            path splitting at the hyphen can leave a fragment that resolves
            to a DIFFERENT real file, which is a silent miss rather than a
            loud one. R4, issue #110 owns the general scrape.
            (f) Ledger prose in a FUNCTION or class docstring, and a class
            ledger written into a commit message or PR body, are outside the
            walk: the population is module-level ledgers, and 208 of the
            tree's 231 `red under:` lines sit in function docstrings. Those
            are the inverted-polarity prose this module cuts rather than
            reads, so the exclusion loses no must-exist claim. R4, this
            ledger owns the record.

red under: revert the `covered:` row of `tests/test_movement_verbs.py` to the
    name it carried before this change -- the one ending `_backstop_raises`
    rather than `_shadow_guard_raises` (commit 568297f renamed the function
    and left the row behind). `test_every_ledger_reference_resolves` names it.
    Executed 2026-08-20.
"""

from __future__ import annotations

import ast
import functools
import pathlib
import re
import subprocess
from typing import NamedTuple

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_SELF = pathlib.Path(__file__).resolve()


# --- the row axis, derived from the templates that define it ----------------


def _fence_labels(path: str, anchor: str) -> tuple[str, ...]:
    """The `label:` lines of the first fenced block after `anchor`."""
    text = (ROOT / path).read_text()
    at = text.index(anchor)
    block = re.search(r"```[a-z]*\n(.*?)\n```", text[at:], re.S)
    assert block is not None, f"no fenced template after {anchor!r} in {path}"
    return tuple(
        m.group(1)
        for line in block.group(1).splitlines()
        if (m := re.match(r"^([a-z_]+):", line))
    )


_DECISIONS = "docs/decisions.md"
_SKILL = ".claude/skills/surface-totality-audit/SKILL.md"

COMPLETENESS_ROWS = _fence_labels(
    _DECISIONS, "the **completeness ledger** in the grid module's\ndocstring:"
)
_SKILL_COMPLETENESS_ROWS = _fence_labels(
    _SKILL, "module — next to the code it describes, nowhere else:"
)
CLASS_ROWS = _fence_labels(
    _SKILL, "**class ledger** BEFORE the fix, in the commit message or the PR body:"
)
LEDGER_ROWS: tuple[str, ...] = tuple(sorted(set(COMPLETENESS_ROWS) | set(CLASS_ROWS)))

# A ledger is recognized by the two rows every completeness ledger carries.
# Measured: nothing in the tree sits just below this bar (no docstring carries
# three or more completeness rows without both of these), so the signature is
# the population rather than a cut through it.
_LEDGER_SIGNATURE = frozenset({"property", "covered"})


# --- the tree the references resolve against --------------------------------


@functools.cache
def _tracked() -> tuple[str, ...]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    out = tuple(n for n in listing.split("\0") if n)
    assert out, "the file walk found nothing -- this check would pass vacuously"
    assert str(_SELF.relative_to(ROOT)) in out, (
        "this module is not in the walk, so the walk is not seeing tracked "
        "files -- exactly how the first version of a pin of this shape passed "
        "locally three times and failed CI (test_native_classification_prose)"
    )
    return out


@functools.cache
def _top_level_dirs() -> frozenset[str]:
    """This repo's own top-level directories, from the walk itself."""
    return frozenset(n.split("/", 1)[0] for n in _tracked() if "/" in n)


@functools.cache
def _defined_test_names() -> frozenset[str]:
    """Every `test*` function defined anywhere in the tree."""
    names: set[str] = set()
    for name in _tracked():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse((ROOT / name).read_text())
        except SyntaxError:  # pragma: no cover - a broken tree fails elsewhere
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    names.add(node.name)
    return frozenset(names)


@functools.cache
def _module_stems() -> frozenset[str]:
    """Tracked `.py` stems -- a ledger may cite a sibling module bare."""
    return frozenset(pathlib.Path(n).stem for n in _tracked() if n.endswith(".py"))


# --- the reference forms ----------------------------------------------------

_QUANTIFIER = r"(?:every|each|all)"
# The coverage nouns and frames these ledgers actually use. Hand-listed, like
# `_ADJACENCY`; each form carries its own reach probe below, and the
# unmatched population is recorded in `residual` (b) rather than implied.
_COVERAGE_NOUN = (
    r"(?:probe|probed|pin|pinned|row|cell|test|tested|guard|guarded|witness"
    r"|cover|covered|exercised|reconciled|enumerated|checked|parametrized)"
)
_COVERAGE_FRAME = (
    rf"(?:has|have|gets?|carr(?:ies|y))\s+(?:an?\s+|its\s+|their\s+|one\s+)?{_COVERAGE_NOUN}"
    rf"|(?:is|are)\s+(?:been\s+)?{_COVERAGE_NOUN}"
)
# An identifier a prose sentence can NAME a set with.
_IDENTIFIER = r"(?:`[^`\n]+`|\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]*\b)"

_TEST_REF = re.compile(r"(?<![\w./`*-])(test_[A-Za-z0-9_]+)(?![\w*(]|\.[a-z])")
_TEST_GLOB = re.compile(r"(?<![\w./`-])(test_[A-Za-z0-9_]*)\*")
_FILE_REF = re.compile(r"(?<![\w./-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_-]+\.[a-z]+)\b")
_MODULE_REF = re.compile(r"`((?:cardlang|tests)(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")
_QUANTIFIED = re.compile(
    rf"\b{_QUANTIFIER}\b[^.;\n]{{0,60}}?\b(?:{_COVERAGE_FRAME})", re.I
)
_FILE_SUFFIXES = frozenset({".py", ".lark", ".md", ".cardlang", ".yml", ".toml", ".sh"})


class Finding(NamedTuple):
    form: str
    row: str
    token: str
    why: str


def _resolves_test(token: str) -> bool:
    return token in _defined_test_names() or token in _module_stems()


def _resolves_glob(prefix: str) -> bool:
    return any(n.startswith(prefix) for n in _defined_test_names())


def _in_this_tree(ref: str) -> bool:
    """A file reference this repo could own: under a tracked top-level
    directory, or a bare `test_*.py`. Everything else -- pytest's own
    `python.py`, a synthetic `pkg/domains.py`, a retired `runtime/stdlib.py`
    -- is a forward or foreign reference and out of domain (residual (d))."""
    if pathlib.Path(ref).suffix not in _FILE_SUFFIXES:
        return False
    head = ref.split("/", 1)[0]
    if "/" in ref:
        return head in _top_level_dirs()
    return ref.startswith("test_") and ref.endswith(".py")


def _resolves_file(ref: str) -> bool:
    return any(t == ref or t.endswith("/" + ref) for t in _tracked())


def _resolves_module(dotted: str) -> bool:
    import importlib

    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            mod = importlib.import_module(".".join(parts[:cut]))
        except Exception:
            continue
        obj = mod
        for attr in parts[cut:]:
            if not hasattr(obj, attr):
                return False
            obj = getattr(obj, attr)
        return True
    return False


def _sentence_at(text: str, start: int, end: int) -> str:
    """The sentence a matched span sits in. decisions.md scopes the rule to
    the SENTENCE ("a `covered` sentence that quantifies ... names the set"),
    so the set may be named before the quantifier -- "`harness.verb_status`
    is total over the 2x2 ... and all four of its cells are probed below"
    names its set and is not a finding."""
    left = max((m.end() for m in re.finditer(r"[.;] ", text[:start])), default=0)
    right = re.search(r"[.;] ", text[end:])
    return text[left:end + (right.start() if right else len(text) - end)]


REFERENCE_FORMS: tuple[str, ...] = (
    "test-id",
    "test-id-glob",
    "file-path",
    "module-attr",
    "quantified-claim",
)


def unresolved(row: str, text: str) -> list[Finding]:
    """Every reference in one ledger row that resolves to nothing, plus every
    quantified completeness claim in a `covered:` row that names no set."""
    out: list[Finding] = []

    for m in _TEST_GLOB.finditer(text):
        prefix = m.group(1)
        if not _resolves_glob(prefix):
            out.append(Finding("test-id-glob", row, prefix + "*",
                               "no test carries this prefix"))
    for m in _TEST_REF.finditer(text):
        token = m.group(1)
        if not _resolves_test(token):
            out.append(Finding("test-id", row, token,
                               "no test function and no module of this name"))
    for m in _FILE_REF.finditer(text):
        ref = m.group(1)
        if _in_this_tree(ref) and not _resolves_file(ref):
            out.append(Finding("file-path", row, ref, "no tracked file"))
    for m in _MODULE_REF.finditer(text):
        dotted = m.group(1)
        # `cardlang.lark` is a FILE written dotted, not a module path; the
        # file forms own it (and `_in_this_tree` rules on whether it is ours).
        if pathlib.PurePosixPath(dotted).suffix in _FILE_SUFFIXES:
            continue
        if not _resolves_module(dotted):
            out.append(Finding("module-attr", row, dotted,
                               "does not import, or the attribute is gone"))

    if row == "covered":
        for m in _QUANTIFIED.finditer(text):
            if not re.search(_IDENTIFIER, _sentence_at(text, m.start(), m.end())):
                out.append(Finding("quantified-claim", row, m.group(0).strip(),
                                   "quantifies over a set it does not name"))
    return out


# --- the ledger population --------------------------------------------------


def _join_rows(parts: list[str]) -> str:
    """Fold a row's continuation lines. An identifier wrapped across lines
    ends the line on `_` or `/`; joining those with a space would split the
    name and manufacture a dangling reference (proven both ways below)."""
    out = parts[0]
    for nxt in parts[1:]:
        out = out + nxt if out.endswith(("_", "/")) else out + " " + nxt
    return out


# `red under:` prose has the OPPOSITE polarity: it names the mutation that has
# deliberately NOT been made, so its referents must not resolve. It is not a
# ledger row (the space defeats the row pattern) but it runs on inside one in
# eight modules, inline and as an unseparated block. Reading it would make a
# well-written reddening witness the thing that reddens this sweep.
_RED_UNDER = re.compile(r"^[ \t]*red under\b", re.I)
_RED_UNDER_INLINE = re.compile(r"\bred under\b.*$", re.I | re.S)


def _rows(doc: str) -> dict[str, str]:
    collected: dict[str, list[str]] = {}
    current: str | None = None
    for line in doc.splitlines():
        if _RED_UNDER.match(line):
            current = None
            continue
        head = re.match(r"^[ \t]*([a-z_]+):(.*)$", line)
        if head is not None and head.group(1) in LEDGER_ROWS:
            current = head.group(1)
            collected.setdefault(current, []).append(head.group(2).strip())
        elif current is not None:
            if line.strip() == "":
                current = None
            else:
                collected[current].append(line.strip())
    return {
        k: _RED_UNDER_INLINE.sub("", _join_rows(v)) for k, v in collected.items()
    }


@functools.cache
def _ledgers() -> tuple[tuple[str, dict[str, str]], ...]:
    found: list[tuple[str, dict[str, str]]] = []
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for name in _tracked():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse((ROOT / name).read_text())
        except SyntaxError:  # pragma: no cover - a broken tree fails elsewhere
            continue
        for node in ast.walk(tree):
            if not isinstance(node, holders):
                continue
            doc = ast.get_docstring(node, clean=False)
            if doc is None:
                continue
            rows = _rows(doc)
            if _LEDGER_SIGNATURE <= set(rows):
                found.append((name, rows))
    return tuple(found)


# --- the grid ---------------------------------------------------------------

# Probe sentences live in module-level constants, NOT in docstrings, so this
# module stays inside its own walk: a ledger that documented its own bad
# referents in prose would have to be excluded from the sweep it runs.
_GOOD: dict[str, str] = {
    "test-id": "proven by test_the_walk_sees_this_module below",
    "test-id-glob": "the family test_a_wrapped_* covers the rejoin",
    "file-path": "the walk is tests/test_ledger_referents.py",
    "module-attr": "the axis reads `cardlang.builtins.functions`",
    "quantified-claim": "every row of `LEDGER_ROWS` has a probe",
}
_BAD: dict[str, str] = {
    "test-id": "proven by test_the_walk_sees_a_module_that_is_not_here below",
    "test-id-glob": "the family test_no_such_prefix_at_all_* covers it",
    "file-path": "the walk is tests/test_no_such_module_here.py",
    "module-attr": "the axis reads `cardlang.builtins.no_such_attribute`",
    "quantified-claim": "every refusal arm has a probe",
}


def _cells() -> list[tuple[str, str, bool]]:
    """form x row x polarity, crossed in code."""
    return [
        (form, row, bad)
        for form in REFERENCE_FORMS
        for row in LEDGER_ROWS
        for bad in (False, True)
    ]


def _expected_flagged(form: str, row: str, bad: bool) -> bool:
    """The expected column, authored from the law.

    A resolving reference is never flagged. A dangling one is flagged in every
    ledger row -- the class sweep, not the two rows the ruling named. The
    `quantified-claim` form is the exception: decisions.md scopes the
    quantifier rule to `covered:`, so the same sentence in `sampled:` or
    `residual:` is a judgment sitting where the register warns the reader, and
    flagging it would be the mechanism overreaching its own law.
    """
    if not bad:
        return False
    if form == "quantified-claim":
        return row == "covered"
    return True


@pytest.mark.parametrize("form,row,bad", _cells(), ids=lambda v: str(v))
def test_grid(form: str, row: str, bad: bool) -> None:
    sentence = (_BAD if bad else _GOOD)[form]
    findings = unresolved(row, sentence)
    hit = any(f.form == form for f in findings)
    assert hit == _expected_flagged(form, row, bad), (
        f"{form} in {row}: expected flagged={_expected_flagged(form, row, bad)}, "
        f"got {findings} for {sentence!r}"
    )


@pytest.mark.parametrize("form", REFERENCE_FORMS)
def test_each_form_is_matched(form: str) -> None:
    """Every form in `REFERENCE_FORMS` is proven to fire, on a sentence
    carrying a KNOWN-bad referent. Without this, a form whose pattern drifted
    would stop matching and the sweep would keep reporting clean -- green
    because it had stopped looking.

    red under: break the named form's pattern.
    """
    row = "covered"
    findings = unresolved(row, _BAD[form])
    assert any(f.form == form for f in findings), (
        f"the {form!r} form matched nothing in {_BAD[form]!r} -- got {findings}"
    )


# --- self-defense -----------------------------------------------------------


def test_the_row_axis_is_derived_from_its_two_templates() -> None:
    """One domain, three definition sites. `decisions.md` and the skill print
    the completeness template; the skill also prints the class-ledger
    template. The first two must agree -- two sources with no reconciliation
    check is a residual, not background.

    red under: change any `label:` in either completeness fence.
    """
    assert COMPLETENESS_ROWS, "the completeness template scraped no rows"
    assert CLASS_ROWS, "the class-ledger template scraped no rows"
    assert COMPLETENESS_ROWS == _SKILL_COMPLETENESS_ROWS, (
        "decisions.md and the surface-totality-audit skill print different "
        f"completeness templates: {COMPLETENESS_ROWS} vs {_SKILL_COMPLETENESS_ROWS}"
    )
    assert _LEDGER_SIGNATURE <= set(COMPLETENESS_ROWS)


def test_the_walk_sees_this_module() -> None:
    """`git ls-files` lists TRACKED files, so a pin of this shape can be blind
    to itself while it is still untracked -- and pass, three times, locally.

    red under: `git rm --cached tests/test_ledger_referents.py`.
    """
    assert str(_SELF.relative_to(ROOT)) in _tracked()


def test_the_ledger_population_is_non_empty() -> None:
    """The sweep's vacuity guard: a signature that matched nothing would make
    every claim below pass over an empty set.

    red under: change `_LEDGER_SIGNATURE` to a label no template prints.
    """
    ledgers = _ledgers()
    assert ledgers, "found no completeness ledger -- the sweep would be vacuous"
    assert any(name == str(_SELF.relative_to(ROOT)) for name, _ in ledgers), (
        "this module's own ledger is not in the population, so the sweep does "
        "not hold this module to the rule it enforces"
    )


def test_the_resolution_universes_are_non_empty() -> None:
    """Each universe a form resolves against, guarded against matching
    nothing -- an empty universe would flag every reference, not none, but a
    universe that silently narrowed would still be the wrong domain.

    red under: filter `_defined_test_names` to names starting `zzz`.
    """
    assert len(_defined_test_names()) > 1000
    assert len(_module_stems()) > 100
    assert {"tests", "cardlang", "docs"} <= _top_level_dirs()


def test_a_wrapped_reference_resolves() -> None:
    """A reference split across two docstring lines is one name, not two.

    red under: join with `" "` unconditionally in `_join_rows`.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    proven by test_the_resolution_universes_are_\n"
        "            non_empty below\n"
    )
    assert "test_the_resolution_universes_are_non_empty" in rows["covered"]
    assert not unresolved("covered", rows["covered"])


def test_a_wrapped_reference_can_still_dangle() -> None:
    """The rejoin must not manufacture a resolution: a wrapped name that
    resolves to nothing is still flagged.

    red under: make `_join_rows` drop continuation lines.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    proven by test_the_resolution_universes_are_\n"
        "            never_written below\n"
    )
    assert "test_the_resolution_universes_are_never_written" in rows["covered"]
    assert unresolved("covered", rows["covered"])


def test_red_under_prose_is_not_read_as_a_reference() -> None:
    """`red under:` names the mutation that has NOT been made, so its
    referents must not resolve -- the opposite polarity from every ledger
    row. It is not a row, but it runs on inside one in eight modules, both
    inline and as an unseparated block, so both shapes are cut.

    red under: drop the `_RED_UNDER` / `_RED_UNDER_INLINE` cuts in `_rows`.
    """
    block = _rows(
        "property:   x\n"
        "covered:    proven by test_the_walk_sees_this_module\n"
        "red under: rename it to test_the_walk_sees_no_such_module_at_all\n"
    )
    assert not unresolved("covered", block["covered"])
    inline = _rows(
        "property:   x\n"
        "covered:    the pin -- NOT vacuous: red under: rename it to\n"
        "            test_the_walk_sees_no_such_module_at_all\n"
    )
    assert not unresolved("covered", inline["covered"])


def test_the_red_under_cut_does_not_swallow_the_row() -> None:
    """The cut must remove the mutation prose and nothing before it, or a
    dangling reference could hide behind a later `red under:`.

    red under: make `_RED_UNDER_INLINE` match from the start of the row.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    proven by test_no_such_test_was_ever_written; red under:\n"
        "            rename test_the_walk_sees_this_module\n"
    )
    found = unresolved("covered", rows["covered"])
    assert [f.token for f in found] == ["test_no_such_test_was_ever_written"]


def test_the_quantified_form_does_not_match_inside_an_identifier() -> None:
    """A compliant ledger cites the reconciliation it wrote, and that test's
    NAME carries the quantifier: PR #388's row cites
    `test_every_refusal_arm_of_opening_actions_has_a_probe`. Reading the
    identifier as a quantified claim would flag the exact form the rule is
    written to produce.

    The property is pinned on `_QUANTIFIED` rather than through `unresolved`,
    because at that level it is unfalsifiable: the cited identifier is itself
    what `_IDENTIFIER` looks for, so the sentence names a set either way and
    no mutation of the matcher can redden it. A pin with no reachable red is
    the vacuously-green class (decisions.md), so this one is placed where its
    red is reachable.

    red under (executed 2026-08-20): widen every `\\s+` in `_COVERAGE_FRAME`
        to `[\\s_]+` AND drop all three `\\b` from `_QUANTIFIED` (both around
        `_QUANTIFIER` and the one before the frame group). No subset of those
        reddens it -- the snake_case is unreachable while any one survives --
        so the fault is planted as one edit to the matcher, never to this
        assertion.
    """
    assert not _QUANTIFIED.search("test_every_refusal_arm_of_opening_actions_has_a_probe")
    assert not _QUANTIFIED.search("each_cell_is_probed")
    # ...and it still fires on the same words written as prose.
    assert _QUANTIFIED.search("every refusal arm has a probe")


def test_a_set_named_before_the_quantifier_is_not_flagged() -> None:
    """decisions.md scopes the rule to the SENTENCE, so a set named earlier in
    it is named. `tests/openspiel_ready/test_conformance_bounds.py` is the
    live example, and a span-scoped test would flag its correct prose --
    the mechanism would then be stricter than the law it mechanizes.

    red under: search `m.group(0)` instead of `_sentence_at(...)`.
    """
    text = (
        "`harness.verb_status` is total over the 2x2 of (applied, "
        "recorded-unreached) and all four of its cells are probed below."
    )
    assert not [f for f in unresolved("covered", text) if f.form == "quantified-claim"]


def test_the_previous_sentence_does_not_name_this_one_s_set() -> None:
    """The sentence scope must be a scope, not a window that drifts back into
    a neighbouring sentence and finds any identifier at all.

    red under: drop the `[.;] ` left boundary in `_sentence_at`.
    """
    text = "the grid reads `LEDGER_ROWS`. Every refusal arm has a probe."
    assert [f for f in unresolved("covered", text) if f.form == "quantified-claim"]


# --- the sweep --------------------------------------------------------------


def test_every_ledger_reference_resolves() -> None:
    """red under: see the module docstring."""
    found: list[str] = []
    scanned = 0
    for name, rows in _ledgers():
        for row, text in rows.items():
            scanned += len(text)
            for f in unresolved(row, text):
                found.append(f"  {name} [{row}] {f.token}: {f.why} ({f.form})")
    assert scanned, "scanned no ledger prose -- this check would pass vacuously"
    assert not found, (
        "a completeness ledger names something that does not resolve:\n"
        + "\n".join(sorted(found))
        + "\n\nA ledger row is read as backed (decisions.md \"Closed-domain "
        "completeness\"); a reference that stopped resolving reads as "
        "authoritative forever."
    )
