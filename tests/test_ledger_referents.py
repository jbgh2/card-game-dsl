"""Every reference a completeness ledger writes still resolves.

A completeness ledger (decisions.md "Closed-domain completeness") is prose
asserting facts about code, and the things those sentences NAME go stale in
silence. `tests/test_movement_verbs.py` cited a test its own rename had moved
out from under it (commit 568297f) and went on reading as authoritative;
`tests/test_cell_queries.py` cited a module by a name no file has ever
carried.

Deleting the coverage rows concentrates this hazard rather than removing it.
What survives in `registry:` is locators, and a locator's whole value is that
it resolves -- including the cross-module kind, where a module cites a
sibling's pin instead of re-copying its enumeration.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a reference written inside a completeness ledger resolves to
                 something the tree holds -- a defined test, a tracked file,
                 an importable attribute. One that stopped resolving fails
                 loudly, in the layer that owns ledger prose: this test. And
                 what the forms do not classify is counted rather than
                 assumed, so the reach of the module as a whole is a number
                 that can move.
domain:          every module-level ledger docstring in the tree, crossed
                 with every reference form in `REFERENCE_FORMS`, with the row
                 the reference sits in, and with MARKUP -- whether the
                 referent sits in a code span or bare. The row axis is total
                 by construction: a label outside the derived set is not a
                 ledger row and its prose is not read. It carries the
                 class-ledger labels because the skill's template defines
                 them, not because any docstring holds one -- the walk finds
                 zero class ledgers, so those cells are forward coverage.
                 Markup is an axis because it was the defect: three forms held
                 three policies on a backtick and the disagreement hid 218
                 referents. Rows are MUST-EXIST prose, so a `red under:` BLOCK
                 -- which states a mutation deliberately NOT made -- ends the
                 row it sits in (`_RED_UNDER`); an inline one stays in domain
                 on purpose, measured, in `_RED_UNDER`'s note.

                 Four things sit deliberately outside, and each is a boundary
                 rather than a gap. A reference form resolves against a
                 tracked file, a collected name or an import, so a shape whose
                 oracle is none of those is out: a single-word identifier with
                 no module prefix (`ZONE_INDEX_ROLES`, `RANK_DIR`) -- markup
                 does not change this, since a name means the same thing in a
                 code span and out of one, and a form reading the backtick as
                 evidence would be inventing an oracle out of typography; a
                 path outside this tree, admitted only under a tracked
                 top-level directory or as a bare `test_*.py` (`_claims`); and
                 the shapes the framing check inventoried -- a pytest node id,
                 `path:LINE`, a brace expansion, a glob or template path, an
                 elided-prefix continuation, a `.lark` production name, a
                 `docs/` path -- each of which is a distinct oracle that
                 admits its own false-positive population. Widening to them
                 needs the declared exception list issue #110 designs; a
                 second one built here would give one domain two definition
                 sites. Fourth, the population is MODULE-level ledgers: 208 of
                 the tree's 231 `red under:` lines sit in function docstrings
                 and are the inverted-polarity prose this module cuts rather
                 than reads, so the exclusion loses no must-exist claim.
registry:        the row axis is DERIVED by `_fence_labels` from the two
                 templates that define it, the `decisions.md` fence under "the
                 **completeness ledger** in the grid module's docstring:" and
                 the `surface-totality-audit` skill's two fences -- reconciled
                 by `test_the_row_axis_is_derived_from_its_two_templates` and
                 pinned as a SET by
                 `test_the_row_axis_is_the_set_the_templates_print`, so a row
                 added to a template joins the sweep with no edit here and a
                 row dropped from both cannot shrink it in silence. The
                 label pattern is `_ROW_LABEL`, one definition read by both
                 the fence scrape and `_rows`. The resolution universes are
                 derived from the tree, not listed: `_defined_test_names`
                 walks every tracked `.py` for `test*` functions, `_tracked`
                 is `git ls-files`, and `_top_level_dirs` is that walk's own
                 first path segments. `REFERENCE_FORMS` is derived from
                 `_FORMS`, the one table pairing each form's pattern with its
                 resolution oracle, so a form cannot be matched in one place
                 and forgotten in another; `_references` is the single answer
                 to "what do the forms reach" that both the sweep and the
                 census read. A form's SHAPE stays hand-listed, defended by a
                 reach probe each rather than by derivation: calibrating
                 citation shapes on today's ledgers would be this module's own
                 defect one level up.
does not prove:  a green here does not mean a ledger is TRUE. The forms
                 resolve names; nothing reads what a row asserts. A row naming
                 a real test that does not test what the row says passes
                 every check in this module -- that is the shape issue #389
                 was filed over, no matcher reaches it, and the mechanism is
                 review at the `surface-totality-audit` skill's Step 3.
                 Likewise a `does not prove:` row holding deferred work in
                 disguise: the row's name is the only thing standing there.

                 The line-wrap rejoin (`_join_rows`) is proven on two
                 examples, not over a derived set of wrapping shapes -- the
                 shapes a docstring can produce are a formatting space, not a
                 registry. What the two probes pin is the property that
                 matters, that rejoining neither invents a resolution nor
                 hides a dangling one. The `/` arm is the weaker: a `/`
                 ending a line is read as a PATH continuation, so a prose
                 separator sitting there ("a.py / b.py" wrapping after the
                 slash) concatenates two filenames into one. The census found
                 the one live instance, in `tests/test_let_typing.py`, and the
                 prose was reflowed rather than the heuristic re-tuned on it
                 -- the failure is loud either way, as a dangling path or as a
                 census-residue token, which is why the heuristic is left
                 alone. The largest known SILENT miss is a reference wrapping
                 at neither an underscore nor a slash: a hyphenated path
                 splitting at the hyphen can leave a fragment that resolves to
                 a DIFFERENT real file.

                 The census's UNRESOLVABLE bucket is counted, never pinned
                 equal, and a count cannot tell the tokenizer narrowing from
                 the ledgers shrinking. It is dominated by things that are not
                 references at all -- DSL surface quoted in prose
                 (`ranking:`, `for each cell`), type names, `.lark`
                 production names, English -- and no oracle here separates a
                 dangling reference sitting in it from correct prose. So what
                 is asserted is the RESOLVING bucket, as a set
                 (`CENSUS_RESIDUE`), and the direction a bare count would miss
                 is held instead by
                 `test_the_census_sees_every_token_the_forms_claim` and
                 `test_the_census_population_is_non_empty`. Bucket sizes are
                 MEASUREMENTS, not pins -- a dated snapshot that moves
                 whenever any ledger is edited, this module's own included
                 (2026-08-20, 89 ledgers): 2139 compound candidates, 551
                 claimed, 13 resolving-but-unclaimed over the 3 tokens in
                 `CENSUS_RESIDUE`, 1575 unresolvable; 1330 of the candidates
                 sit in a code span and 809 bare.

No form here reads the PROSE of a row, only the names in it. A matcher
holding a quantified sentence to naming its set beside it flags eight
sentences across this tree, all eight of them correct English (measured
2026-08-20, 90 ledgers) -- and a matcher with no doctrine behind it enforces
its author's taste. decisions.md "Every reference a ledger writes resolves"
owns the rule this module mechanizes.

red under: revert the citation in `tests/test_domain_registry.py` to the
    truncated form it carried before this change -- the row is row-agnostic
    here, as the sweep is, and that module has not migrated yet -- `test_every_row_is_`
    plus `quantifiable`, wrapping across two lines inside one code span, where
    the function is `test_every_row_is_quantifiable_in_both_forms`. It was
    invisible to every form for as long as it sat in backticks.
    `test_every_ledger_reference_resolves` names it, and its `assert not
    found` is the assertion that reddens -- alone, 1 failed of 167, naming
    the truncated token. Re-executed 2026-08-20 against this format.
"""

from __future__ import annotations

import ast
import functools
import pathlib
import re
import subprocess
from collections.abc import Callable
from typing import NamedTuple

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_SELF = pathlib.Path(__file__).resolve()


# --- the row axis, derived from the templates that define it ----------------


# A row label is one or more lowercase words. The multi-word form is not
# hypothetical -- `does not prove:` is a row -- and a single-token pattern
# drops it SILENTLY: the fence scrape returns three labels instead of four,
# `_rows` never collects the row, and every check keyed on the axis narrows
# to fit while staying green. That is the empty-input-set class, and the
# template edit that renamed the row is exactly the edit that triggers it.
# So the pattern is defined once, read by both sites, and the resulting set
# is pinned by `test_the_row_axis_is_the_set_the_templates_print`.
_ROW_LABEL = r"([a-z][a-z _]*[a-z])"


def _fence_labels(path: str, anchor: str) -> tuple[str, ...]:
    """The `label:` lines of the first fenced block after `anchor`.

    Anchored at the line start with no leading-whitespace class, which is
    what keeps an indented CONTINUATION line out of the label set.
    """
    text = (ROOT / path).read_text()
    at = text.index(anchor)
    block = re.search(r"```[a-z]*\n(.*?)\n```", text[at:], re.S)
    assert block is not None, f"no fenced template after {anchor!r} in {path}"
    return tuple(
        m.group(1)
        for line in block.group(1).splitlines()
        if (m := re.match(rf"^{_ROW_LABEL}:", line))
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
# `covered` was one of them until the format deleted that row; `domain` takes
# its place because `domain` is in BOTH the old template and the new one, so
# the population does not move while the modules migrate one at a time -- a
# signature naming a row only one format carries would shrink the sweep on
# every migration commit, which is the same silent narrowing one level up.
# Re-measured under the new pair (2026-08-20): the same 90 ledgers, and
# nothing in the tree sits just below the bar (no docstring carries three or
# more completeness rows without both of these), so the signature is still
# the population rather than a cut through it.
_LEDGER_SIGNATURE = frozenset({"property", "domain"})


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


# --- markup: one policy ------------------------------------------------------

# A backtick pair delimits a CODE SPAN, and that single fact settles markup for
# every form here. Each form used to carry its own policy, written against the
# examples in front of it -- `test_...` and the glob EXCLUDED a leading
# backtick, the module form REQUIRED one, and the file form admitted one by
# omission -- so the same referent was a reference to one form and invisible to
# another. 218 backticked test names over 49 modules sat outside every form,
# and one of them had been dangling since a rename.
#
# The policy has two halves, each stated where it is enforced:
#
#   A reference form NAMES NO MARKUP. A backtick is outside every token
#   character class these patterns use, so a code span's delimiters are already
#   boundaries; the forms disagreed only because three of them went out of
#   their way to mention the character. Silence is the agreement, and it needs
#   no normalizing pass -- one was written and then measured to change no
#   finding and no census bucket, so it is not here. What the policy needs is a
#   guard against the mention coming back, and that is
#   `test_no_reference_form_names_a_backtick`, derived from `_FORMS`.
#
#   A code span is a BUCKET, not a boundary. The census reports each token as
#   marked or bare, so `_code_spans` stays the one place that decides where a
#   span is -- the same single fact the forms are silent about, read here for
#   classification rather than for matching.

_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Every code span's extent. The one place that decides where they are."""
    return [(m.start(), m.end()) for m in _CODE_SPAN.finditer(text)]


# --- the reference forms ----------------------------------------------------

_MODULE_SHAPE = r"(?:cardlang|tests)(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
_TEST_REF = re.compile(r"(?<![\w./*-])(test_[A-Za-z0-9_]+)(?![\w*(]|\.[a-z])")
_TEST_GLOB = re.compile(r"(?<![\w./-])(test_[A-Za-z0-9_]*)\*")
_FILE_REF = re.compile(r"(?<![\w./-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_-]+\.[a-z]+)\b")
_MODULE_REF = re.compile(rf"(?<![\w.])({_MODULE_SHAPE})")
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


# form -> (its pattern, its resolution oracle, the sentence a failure reads).
# One table: `REFERENCE_FORMS` is derived from it, `_references` matches from
# it, and `unresolved` resolves from it, so a form cannot exist in one of the
# three and be missing from another.
_FORMS: dict[str, tuple[re.Pattern[str], Callable[[str], bool], str]] = {
    "test-id-glob": (_TEST_GLOB, _resolves_glob, "no test carries this prefix"),
    "test-id": (_TEST_REF, _resolves_test,
                "no test function and no module of this name"),
    "file-path": (_FILE_REF, _resolves_file, "no tracked file"),
    "module-attr": (_MODULE_REF, _resolves_module,
                    "does not import, or the attribute is gone"),
}
REFERENCE_FORMS: tuple[str, ...] = tuple(_FORMS)


def _claims(form: str, token: str) -> bool:
    """Whether `form` owns this token at all, before any resolution. Each
    form's domain rule, at the one site that decides it."""
    if form == "file-path":
        # A path outside this tree -- pytest's own `python.py`, a synthetic
        # `pkg/domains.py` -- is a foreign reference, residual (d).
        return _in_this_tree(token)
    if form == "module-attr":
        # `cardlang.lark` is a FILE written dotted, not a module path.
        return pathlib.PurePosixPath(token).suffix not in _FILE_SUFFIXES
    return True


def _references(text: str) -> list[tuple[str, str]]:
    """Every token a reference form CLAIMS in one row, form-tagged. The sweep
    and the census both read this, so "what the forms reach" is decided once
    -- a census computing its own answer could not measure the forms."""
    return [
        (form, m.group(1))
        for form, (pattern, _, _) in _FORMS.items()
        for m in pattern.finditer(text)
        if _claims(form, m.group(1))
    ]


def unresolved(row: str, text: str) -> list[Finding]:
    """Every reference in one ledger row that resolves to nothing."""
    out: list[Finding] = []
    for form, token in _references(text):
        _, resolves, why = _FORMS[form]
        if not resolves(token):
            # The glob's oracle takes the prefix; the finding shows the glob.
            shown = token + "*" if form == "test-id-glob" else token
            out.append(Finding(form, row, shown, why))

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
# ledger row (the space defeats the row pattern), but a `red under:` BLOCK
# runs straight on from a row in eight modules with no blank line between, so
# it ends the row exactly as a blank line does. Reading it would make a
# well-written reddening witness the thing that reddens this sweep.
#
# The cut is the block form ONLY. An INLINE "red under" is deliberately left
# in domain: measured over the 87 ledgers, cutting from an inline occurrence
# to the end of the row removes 1.5% of all ledger prose and up to 90% of one
# row (`tests/test_zone_capacity.py`'s `covered:`, 944 characters to 87), it
# fires on four rows where "red under" is ordinary prose ("proven red under
# `xfail(strict=True)`"), and it changes no finding -- zero, either way
# (measured 2026-08-20). A cut that removes prose and catches nothing is this
# sweep going quiet, which is the direction that fails silently; an inline
# `red under:` naming something absent will redden here instead, loudly.
_RED_UNDER = re.compile(r"^[ \t]*red under\b", re.I)


def _rows(doc: str) -> dict[str, str]:
    collected: dict[str, list[str]] = {}
    current: str | None = None
    for line in doc.splitlines():
        if _RED_UNDER.match(line):
            current = None
            continue
        head = re.match(rf"^[ \t]*{_ROW_LABEL}:(.*)$", line)
        if head is not None:
            # EVERY labelled block is collected, not only the labels the
            # templates define. Gating on `LEDGER_ROWS` made the sweep's reach
            # depend on the row axis: a label the templates no longer print --
            # a row mid-migration, or a typo (`registy:`) -- ended the previous
            # row at its blank line and its prose was then read by nothing.
            # Measured at the format change: 4 references over 3 modules fell
            # out that way. Row identity is diagnostic only (nothing branches
            # on it), so widening costs a little row attribution and buys the
            # property the module claims -- every reference a ledger writes.
            current = head.group(1)
            # A KNOWN label is structure, so the row's text is its content.
            # An unknown one is prose that merely looks like a label -- a
            # ledger writes `test_chained_offset_by_start: offset no-op` as
            # an inline gloss, and that token is reference-shaped, so
            # dropping the head would swallow the one thing this module
            # exists to resolve. Widening the parse must not narrow the text.
            keep = head.group(2) if current in LEDGER_ROWS else line
            collected.setdefault(current, []).append(keep.strip())
        elif current is not None:
            if line.strip() == "":
                current = None
            else:
                collected[current].append(line.strip())
    return {k: _join_rows(v) for k, v in collected.items()}


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
#
# Each is a frame plus the referent that goes in it, so the MARKED variant is
# derived by wrapping rather than written out a second time -- a hand-written
# pair could disagree about everything except the backticks, which is the
# defect this axis exists to catch.
_GOOD: dict[str, tuple[str, str]] = {
    "test-id": ("proven by {} below", "test_the_walk_sees_this_module"),
    "test-id-glob": ("the family {} covers the rejoin", "test_a_wrapped_*"),
    "file-path": ("the walk is {}", "tests/test_ledger_referents.py"),
    "module-attr": ("the axis reads {}", "cardlang.builtins.functions"),
}
_BAD: dict[str, tuple[str, str]] = {
    "test-id": ("proven by {} below", "test_the_walk_sees_a_module_that_is_not_here"),
    "test-id-glob": ("the family {} covers it", "test_no_such_prefix_at_all_*"),
    "file-path": ("the walk is {}", "tests/test_no_such_module_here.py"),
    "module-attr": ("the axis reads {}", "cardlang.builtins.no_such_attribute"),
    # No referent to mark: the claim is bad by naming nothing at all, so the
    # markup axis is a no-op here and the cell reads the same in both columns.
}


def _probe(form: str, bad: bool, marked: bool) -> str:
    frame, token = (_BAD if bad else _GOOD)[form]
    return frame.format(f"`{token}`" if marked and token else token)


def _cells() -> list[tuple[str, str, bool, bool]]:
    """form x row x polarity x markup, crossed in code. Markup is an axis
    because it was the defect: three forms held three different policies on a
    backtick, and 218 backticked test names over 49 modules were invisible to
    all of them."""
    return [
        (form, row, bad, marked)
        for form in REFERENCE_FORMS
        for row in LEDGER_ROWS
        for bad in (False, True)
        for marked in (False, True)
    ]


def _expected_flagged(form: str, row: str, bad: bool) -> bool:
    """The expected column, authored from the law.

    A resolving reference is never flagged. A dangling one is flagged in every
    ledger row -- the class sweep, not the two rows the rule named. Markup
    never appears here: that a referent reads the same inside and outside a
    code span IS the policy, so the axis crosses the grid without an arm of
    its own. There is no longer an exception on the row axis: the one form
    that carried one, `quantified-claim`, retired with the `covered:` row
    whose definition gave it a law to enforce.
    """
    return bad


@pytest.mark.parametrize("form,row,bad,marked", _cells(), ids=lambda v: str(v))
def test_grid(form: str, row: str, bad: bool, marked: bool) -> None:
    sentence = _probe(form, bad, marked)
    findings = unresolved(row, sentence)
    hit = any(f.form == form for f in findings)
    assert hit == _expected_flagged(form, row, bad), (
        f"{form} in {row} (marked={marked}): expected "
        f"flagged={_expected_flagged(form, row, bad)}, got {findings} "
        f"for {sentence!r}"
    )


@pytest.mark.parametrize("form", REFERENCE_FORMS)
@pytest.mark.parametrize("marked", (False, True))
def test_each_form_is_matched(form: str, marked: bool) -> None:
    """Every form in `REFERENCE_FORMS` is proven to fire, on a sentence
    carrying a KNOWN-bad referent, in both markup columns. Without this, a
    form whose pattern drifted would stop matching and the sweep would keep
    reporting clean -- green because it had stopped looking.

    red under: break the named form's pattern; or, for the `marked` column,
        restore a backtick to `_TEST_REF`'s lookbehind, which is the defect
        this module was reviewed for. (Executed 2026-08-20: that plant reddens
        the four `marked` `test-id` cells here and nothing else in this test.)
    """
    row = "covered"
    sentence = _probe(form, True, marked)
    findings = unresolved(row, sentence)
    assert any(f.form == form for f in findings), (
        f"the {form!r} form matched nothing in {sentence!r} -- got {findings}"
    )


def test_no_reference_form_names_a_backtick() -> None:
    """The markup policy, enforced where it is owned -- in `_FORMS`, over every
    form at once rather than at the site of whichever one drifted.

    A backtick is outside every token character class these patterns use, so a
    form that stays silent about the character treats a code span's delimiters
    as boundaries. Three forms did not stay silent, in two different
    directions, and the disagreement is what hid 218 referents. The rule that
    makes them agree is that NO form may mention it -- which also catches the
    other direction, a form that requires markup and so cannot see a bare
    reference.

    A new form joins this check by being in `_FORMS`; there is nothing to add.

    red under: restore the backtick to `_TEST_REF`'s lookbehind, or the
        leading `` ` `` anchor to `_MODULE_REF`.
    """
    named = {form: pattern.pattern for form, (pattern, _, _) in _FORMS.items()
             if "`" in pattern.pattern}
    assert not named, (
        f"a reference form names a backtick: {named}. Markup is not part of a "
        "token; a pattern that mentions it either excludes a backticked "
        "reference or requires one, and either way it disagrees with the "
        "forms that stay silent."
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


def test_the_row_axis_is_the_set_the_templates_print() -> None:
    """The row axis is DERIVED, which is what lets a doctrine edit re-scope
    this module with no edit here -- and is also how the axis can shrink
    without anything going red. A label dropped or renamed leaves
    `COMPLETENESS_ROWS` shorter, `_rows` stops collecting that row, and every
    check keyed on the axis quietly covers less: the empty-input-set class,
    whose mark is that the narrowed check still passes.

    The sibling above reconciles the two SITES against each other, which does
    not reach this: two templates edited together agree with each other while
    both being wrong. So the set itself is pinned, and `does not prove` is
    the reason it had to be. It is the first multi-word label, and the
    single-token pattern that predated it scraped three rows instead of four
    -- no exception, no diagnostic, just a sweep that had stopped reading a
    row.

    red under: delete, rename or reorder any `label:` line in BOTH
    completeness fences at once (one alone reddens the sibling).
    """
    assert COMPLETENESS_ROWS == ("property", "domain", "registry", "does not prove")
    assert CLASS_ROWS == ("finding", "class", "members", "covered", "residual")


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


def test_a_red_under_block_is_not_read_as_a_reference() -> None:
    """A `red under:` block runs on from a row with no blank line between in
    eight modules, and it names the mutation that has NOT been made -- the
    opposite polarity from every ledger row. It ends the row.

    red under: drop the `_RED_UNDER` cut from `_rows`.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    proven by test_the_walk_sees_this_module\n"
        "red under: rename it to test_the_walk_sees_no_such_module_at_all\n"
    )
    assert not unresolved("covered", rows["covered"])


def test_the_red_under_cut_keeps_the_row_it_ends() -> None:
    """The cut ends the row and removes nothing from it, or a reference
    already written would vanish along with the mutation prose.

    red under: replace the `continue` in `_rows`' `_RED_UNDER` arm with a
        `break`, which drops every later row too.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    proven by test_no_such_test_was_ever_written\n"
        "red under: rename test_the_walk_sees_this_module\n"
        "residual:   none\n"
    )
    assert [f.token for f in unresolved("covered", rows["covered"])] == [
        "test_no_such_test_was_ever_written"
    ]
    assert rows["residual"] == "none"


def test_prose_under_an_unknown_label_is_still_swept() -> None:
    """The sweep's reach must not depend on the ROW AXIS. While `_rows` would
    start a row only for a label in `LEDGER_ROWS`, a label the templates do
    not print -- a row mid-migration, or a typo (`registy:`) -- did not start
    one, and the blank line before it had already ended the row above, so its
    prose was read by nothing and a dangling reference in it passed.

    Measured when this format landed: 4 references over 3 modules
    (`tests/test_domain_registry.py`, `tests/test_procedures.py`,
    `tests/test_winner_target.py`) sat outside the sweep exactly this way.

    red under: restore the `head.group(1) in LEDGER_ROWS` condition on
        STARTING a row; the blank line then orphans the unknown label's prose
        and this finding disappears.
    """
    rows = _rows(
        "property:   x\n"
        "domain:     y\n"
        "\n"
        "sampled:    proven by test_no_such_test_was_ever_written\n"
    )
    found = [f.token for row, text in rows.items() for f in unresolved(row, text)]
    assert found == ["test_no_such_test_was_ever_written"], rows


def test_a_reference_shaped_label_is_not_swallowed_by_being_a_label() -> None:
    """The other side of widening the parse: a ledger writes an inline gloss
    keyed by a test name (`test_chained_offset_by_start: offset no-op`), and
    that head is reference-shaped. Keeping only the tail of an unknown label's
    line would drop the very token this module resolves -- widening what the
    parse ADMITS must not narrow what it READS.

    red under: store `head.group(2)` for an unknown label too, instead of the
        whole line.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    ok\n"
        "test_no_such_test_was_ever_written: an inline gloss\n"
    )
    found = [f.token for row, text in rows.items() for f in unresolved(row, text)]
    assert found == ["test_no_such_test_was_ever_written"], rows


def test_an_inline_red_under_stays_in_domain() -> None:
    """The deliberate half of the polarity decision, pinned so it is not
    quietly "fixed" into a cut. Cutting from an inline "red under" to the end
    of the row removes up to 90% of one real row and fires on four rows using
    the words as ordinary prose, while changing no finding (see `_RED_UNDER`'s
    note). So an inline mutation name is read, and reddens.

    red under: restore an inline cut -- `re.sub(r"\\bred under\\b.*$", "", ...)`
        over each joined row in `_rows`.
    """
    rows = _rows(
        "property:   x\n"
        "covered:    the pin -- NOT vacuous: red under: rename it to\n"
        "            test_the_walk_sees_no_such_module_at_all\n"
    )
    assert [f.token for f in unresolved("covered", rows["covered"])] == [
        "test_the_walk_sees_no_such_module_at_all"
    ]


# --- the skipped-token census -----------------------------------------------

# The forms say what they reach; nothing said what they SKIP. That is why 218
# backticked test names sat outside every form unnoticed, and why the review
# found it before the sweep did -- a matcher reports what it matches, and a
# matcher that has stopped looking reports the same thing as a clean tree.
#
# The census closes that by accounting for every COMPOUND token in a ledger
# row -- one built from parts with `_`, `.` or `/`. A bare single word is out
# by construction: nothing here can tell `unify` the function from "unify" the
# verb, which is residual (c). Each candidate lands in exactly one bucket:
#
#   claimed               a form matched it, and resolution ruled on it.
#   unclaimed-resolving   no form matched it, yet one of THIS module's own
#                         oracles resolves it -- a reference we could have
#                         ruled on and did not. The actionable bucket, pinned
#                         below as a set so a new member is NAMED, not a
#                         count that moved.
#   unclaimed-unresolvable  no form, no oracle: DSL surface, grammar terms,
#                         type names, English. Counted, never asserted equal
#                         -- an exact figure here would redden on every
#                         ordinary ledger edit while proving nothing.

_CANDIDATE = re.compile(r"[A-Za-z0-9_./*-]+")


class Census(NamedTuple):
    claimed: int
    resolving: dict[str, int]
    unresolvable: int
    in_code_span: int
    bare: int

    @property
    def total(self) -> int:
        return self.claimed + sum(self.resolving.values()) + self.unresolvable


def _candidates(text: str) -> list[tuple[str, bool]]:
    """Every compound token in one row, with whether it sat in a code span.
    Both sides are counted: the defect WAS a markup asymmetry, so a census
    blind to one side of it could not have measured its own subject."""
    spans = _code_spans(text)
    out: list[tuple[str, bool]] = []
    for m in _CANDIDATE.finditer(text):
        token = m.group(0).strip("./-*")
        if token and any(ch in token for ch in "_./"):
            out.append((token, any(a < m.start() < b for a, b in spans)))
    return out


def _resolves_by_any_oracle(token: str) -> bool:
    """Whether ANY universe this module already owns rules on the token. The
    census must not invent a universe of its own: one that did could not
    measure the forms, and it would give one domain two definition sites."""
    if _resolves_test(token):
        return True
    if _in_this_tree(token) and _resolves_file(token):
        return True
    return re.fullmatch(_MODULE_SHAPE, token) is not None and _resolves_module(token)


@functools.cache
def _census() -> Census:
    claimed = unresolvable = in_span = bare = 0
    resolving: dict[str, int] = {}
    for _, rows in _ledgers():
        for _, text in rows.items():
            owned = {token for _, token in _references(text)}
            for token, marked in _candidates(text):
                if marked:
                    in_span += 1
                else:
                    bare += 1
                if token in owned or token + "*" in owned:
                    claimed += 1
                elif _resolves_by_any_oracle(token):
                    resolving[token] = resolving.get(token, 0) + 1
                else:
                    unresolvable += 1
    return Census(claimed, resolving, unresolvable, in_span, bare)


# The whole actionable residue, each member with the reason it is not a
# reference. All three are the same shape -- a word that is prose or DSL
# surface here and ALSO happens to be a tracked module's stem, so
# `_module_stems` resolves it by coincidence. Naming them beats narrowing the
# oracle until the number looks good: a coincidence recorded is a coincidence
# a reader can check, and a fourth one arriving has to be ruled on.
CENSUS_RESIDUE: dict[str, str] = {
    "__init__": "the dunder discussed as prose; collides with the `__init__` stem",
    "active_rules": "the DSL clause `active_rules:`; collides with a module stem",
    "trick_order": "the DSL block and the mechanic; collides with a module stem",
}


def test_the_skipped_token_census_is_pinned() -> None:
    """What the forms do NOT classify, as an assertion rather than a claim.

    Run against the matcher this module carried before its markup policy was
    made one, this bucket held 247 occurrences over 226 distinct tokens --
    the 218 backticked test names plus the dotted paths the module form's
    backtick anchor turned away. It now holds the three below. That is the
    number the census exists to move, measured on the exact defect it was
    built for (2026-08-20).

    red under: restore the backtick to `_TEST_REF`'s lookbehind. Every
        backticked test name leaves `claimed` and lands here, so the pin
        fails naming them rather than reporting a count that shifted.
    """
    census = _census()
    assert census.resolving.keys() == CENSUS_RESIDUE.keys(), (
        "the residue of ledger tokens that resolve but no form claims has "
        f"changed.\n  gained: {sorted(census.resolving.keys() - CENSUS_RESIDUE.keys())}"
        f"\n  lost:   {sorted(CENSUS_RESIDUE.keys() - census.resolving.keys())}\n\n"
        "A token here names something this tree holds and went through no "
        "form. Either a reference form's reach is short -- fix the form -- or "
        "it is a new coincidence with a module stem, which goes in "
        "`CENSUS_RESIDUE` with the reason it is not a reference."
    )


def test_the_census_sees_every_token_the_forms_claim() -> None:
    """The census's totality property: every token a form claims is carried by
    some candidate. A tokenizer narrower than the forms would drop claimed
    tokens out of the population and shrink the residue for a reason that has
    nothing to do with reach -- the census going quiet about itself, which is
    the failure it exists to prevent.

    Containment, not equality: a glob claims the PREFIX `test_a_wrapped_` of
    the candidate `test_a_wrapped_*`, and an elided citation claims the head
    of a longer token. Both are carried by the candidate that holds them.

    red under: drop `/` from `_CANDIDATE`, or from `_candidates`' compound
        test, and every file path breaks into pieces no candidate contains.
    """
    missing: list[str] = []
    for name, rows in _ledgers():
        for row, text in rows.items():
            seen = {token for token, _ in _candidates(text)}
            for form, token in _references(text):
                if not any(token in candidate for candidate in seen):
                    missing.append(f"  {name} [{row}] {token} ({form})")
    assert not missing, (
        "a form claims a token the census does not count:\n" + "\n".join(missing)
    )


def test_the_census_population_is_non_empty() -> None:
    """Vacuity guard: an empty population would make the residue pin pass by
    counting nothing, and both halves of the markup split must be live or the
    census cannot see the asymmetry that produced it.

    red under: filter `_candidates` to tokens containing `zzz`.
    """
    census = _census()
    assert census.total > 1000, census
    assert census.claimed > 100, census
    assert census.in_code_span > 100 and census.bare > 100, census
    assert census.in_code_span + census.bare == census.total, census


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
