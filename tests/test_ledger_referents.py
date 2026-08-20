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
            `covered:` row names its set POSITIONALLY, inside the phrase the
            quantifier ranges over. A reference that stopped resolving fails
            loudly, in the layer that owns ledger prose: this test. And what
            the forms do not classify is counted rather than assumed, so the
            reach of the module as a whole is a number that can move.
domain:     every ledger docstring in the tree, crossed with every reference
            form in `REFERENCE_FORMS`, with the row the reference sits in, and
            with MARKUP -- whether the referent sits in a code span or bare.
            The row axis is total by construction -- a row label outside the
            derived set is not a ledger row and its prose is not read. The
            row axis carries the class-ledger labels because the skill's
            template defines them, not because any docstring holds one: the
            walk finds zero class ledgers in docstrings, so those grid cells
            are forward coverage. Markup is an axis because it was the defect:
            three forms held three policies on a backtick and the disagreement
            hid 218 referents. Rows are MUST-EXIST prose:
            a `red under:` BLOCK states the mutation deliberately not made,
            so it ends the row (`_RED_UNDER`); an inline one is left in
            domain on purpose, measured, in `_RED_UNDER`'s note.
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
            quantifier vocabulary is DERIVED from the rule's own sentence by
            `_law_quantifiers`, so the matcher cannot enforce a subset of the
            law in silence -- and so the probe row survives the word being
            taken away, which a hand-list cannot do. `REFERENCE_FORMS` is
            derived from `_FORMS`, the one table pairing each form's pattern
            with its resolution oracle, so a form cannot be matched in one
            place and forgotten in another, and `_references` is the single
            answer to "what do the forms reach" that both the sweep and the
            census read. A form's SHAPE stays hand-listed, defended by a reach
            probe each rather than by derivation: calibrating citation shapes
            on today's ledgers would be this module's own defect one level up.
            The coverage frames (`_COVERAGE_FRAME`) are hand-listed on the
            same terms, as `_ADJACENCY` is in
            `tests/test_native_classification_prose.py`.
covered:    the grid IS the coverage -- `test_grid` over `_cells`, which
            crosses `REFERENCE_FORMS` x `LEDGER_ROWS` x {resolving, dangling}
            x {bare, in a code span} in code, reading its sentences from
            `_GOOD` and `_BAD` and its expected column from
            `_expected_flagged`, authored from the law before the matcher
            existed (run red: 43 failed, 60 passed, 2026-08-20). The markup
            axis was added in the review round that found the three-policy
            defect, so its red is MEASURED rather than historical: run against
            the pre-review matcher, 27 of the 180 cells fail -- 18 in the
            marked column, and 9 in the bare column, which is `module-attr`
            failing in the opposite direction because it REQUIRED the markup
            the others excluded (measured 2026-08-20).
            The marked column is derived by wrapping the same referent
            rather than written out again, so a cell cannot differ from its
            twin in anything but markup. `test_each_form_is_matched` adds a
            row per member of `REFERENCE_FORMS` in each markup column, on a
            sentence carrying a KNOWN-bad referent, so a drifted pattern
            cannot leave the sweep reporting clean.
            `test_each_quantifier_word_is_matched` does the same over
            `QUANTIFIER_WORDS` and `test_each_coverage_frame_is_matched` over
            the frame shapes, so the vocabularies inside the
            `quantified-claim` form are reached rather than assumed.
            The markup policy carries both of its halves as rows:
            no form may name a backtick
            (`test_no_reference_form_names_a_backtick`, derived from `_FORMS`,
            so a new form joins with no edit), and a code span is not prose
            (`test_a_quantifier_inside_a_code_span_is_not_a_prose_quantifier`).
            The positional bind carries both of its sides:
            `test_an_identifier_outside_the_quantified_span_does_not_name_the_set`
            parametrizes the five places an identifier can sit and be the
            wrong one, and
            `test_a_set_named_inside_the_quantified_span_is_not_flagged`
            holds the other direction, backticked and bare.
            The polarity cut carries all three of its
            decisions as rows: the block is cut
            (`test_a_red_under_block_is_not_read_as_a_reference`), the row it
            ends survives it (`test_the_red_under_cut_keeps_the_row_it_ends`),
            and the inline form is deliberately NOT cut
            (`test_an_inline_red_under_stays_in_domain`).
            `test_every_ledger_reference_resolves` runs the matcher over
            every ledger `_ledgers` finds; its vacuity is guarded by
            `test_the_walk_sees_this_module`,
            `test_the_ledger_population_is_non_empty` and
            `test_the_resolution_universes_are_non_empty`.
            What the forms do NOT classify is the census: every compound token
            in a ledger row lands in exactly one of {claimed, resolving-but-
            unclaimed, unresolvable}. The middle bucket holds a token that one
            of this module's own oracles resolves while no form of
            `REFERENCE_FORMS` claimed it, and `CENSUS_RESIDUE` pins it as a
            SET rather than a count -- `test_the_skipped_token_census_is_pinned`
            names a new member instead of reporting a figure that shifted;
            `test_the_census_sees_every_token_the_forms_claim` holds the
            candidate population to covering every token `_references`
            returns, and `test_the_census_population_is_non_empty` guards its
            vacuity and keeps both markup columns live.
sampled:    the line-wrap rejoin (`_join_rows`) is proven on two examples
            rather than over a derived set of wrapping shapes:
            `test_a_wrapped_reference_resolves` and
            `test_a_wrapped_reference_can_still_dangle`. The wrapping shapes a
            docstring can produce are a formatting space, not a registry; what
            the two probes pin is the property that matters, that rejoining
            neither invents a resolution nor hides a dangling one. The rejoin
            covers the two continuation characters a reference is split on
            here, `_` and `/`; a split elsewhere is residual (e). The `/` arm
            is the weaker of the two and is now measured rather than assumed:
            a `/` ending a line is read as a PATH continuation, so a prose
            separator sitting there ("a.py / b.py" wrapping after the slash)
            concatenates two filenames into one. The census found the one live
            instance, in `tests/test_let_typing.py`, and the prose was
            reflowed rather than the rejoin heuristic re-tuned on it -- the
            failure is loud either way, as a dangling path in the sweep or as
            a census-residue token, which is why the heuristic is left alone.
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
            is out of the `quantified-claim` form, and so is a set named
            elsewhere in the SAME sentence: the identifier must sit inside the
            span running from the quantifier to the coverage predicate. That
            bind is what makes the check able to fail at all. Sentence scope
            was the earlier reading, and it could not fail: over 89 ledgers it
            emitted zero findings, and it could not have fired even on the two
            sentences it matched, because any identifier at all satisfied it
            -- a row that cited its own verifier beside an unnamed set passed.
            The five places an identifier can sit and be the wrong one are
            parametrized in
            `test_an_identifier_outside_the_quantified_span_does_not_name_the_set`,
            where the sentences are executable rather than quoted here: a
            ledger row illustrating a bad reference by writing one would be
            inverted-polarity prose, which this module reads straight.
            The law is not overreached by the
            tightening: its own exemplar names the set inside the noun phrase
            ("Every arm of `opening_actions` has a probe"), and its stated
            purpose is that the claim be reconcilable, which a pronoun is not
            without a reader to follow it. The tightening flagged exactly one
            row in the tree (`tests/openspiel_ready/test_conformance_bounds.py`,
            "all four of its cells"), which was rewritten to name its set --
            and which was also stating a cardinality, against "Prose names the
            registry, never the cardinality". Matching the
            unnamed-quantifier population generally was measured and refused:
            `covered:` rows carry 299 quantifier occurrences over 87 ledgers,
            and requiring a nearby identifier flags 40 to 76 modules depending
            on the window -- at the tightest positional anchoring, still 30
            occurrences across 24 modules, nearly all correct prose that names
            its set in English ("all 28 French cells (7 decks x 4 conventions,
            frozen expected tuples)"). A matcher that reddens those is
            stricter than the law it mechanizes (measured 2026-08-20, `main`
            at `591e44f`). The frame vocabulary bounds the form the same way:
            `tests/openspiel_ready/test_provenance_openings.py` writes two
            claims outside it -- a participle ("each asserting its needle
            from that table") and a negated adjective ("no scraped message is
            needle-free") -- which `_COVERAGE_FRAME` does not match. Both
            name their sets, so the rule holds and a match would change
            nothing; the reach limit is real anyway, and the same phrasing
            over an UNNAMED set would pass unseen. R3, guarded by the same
            skill step as (a); the standing question of whether `covered:`
            may hold navigational prose at all is issue #392.
            (c) A bare identifier with no module prefix (`ZONE_INDEX_ROLES`,
            `RANK_DIR`, `_ITERATION_ROLES`) is not resolved here -- because no
            form has that SHAPE, which markup does not change: a name means the
            same thing in a code span and out of one, and a form that read the
            backtick as evidence would be inventing an oracle out of
            typography. Measured over these ledgers,
            those tokens span at least four namespaces -- Python constants,
            `.lark` terminals, environment variables and prefix families like
            `BUILTIN_` -- so 23 of them resolve to no Python name while being
            correct prose. Admitting them needs the declared exception list
            issue #110 designs, and building a second one here would give one
            domain two definition sites. R4, issue #110.
            (d) A file reference outside this tree -- pytest's own
            `python.py`, a synthetic fixture path (`pkg/domains.py`), a
            deliberately-retired path (`runtime/stdlib.py`) -- is out of
            domain by `_claims`, which admits a path only under a tracked
            top-level directory or a bare `test_*.py`. This is the same
            forward-reference problem as (c) and has the same answer. R4,
            issue #110.
            (e) Reference SHAPES outside `REFERENCE_FORMS`, from the framing
            check's inventory: a pytest node id (which needs collection, not
            a scrape), `path:LINE`, a brace expansion, a glob or template
            path, an elided-prefix continuation (`.board_entry` after
            `BoardEntry`), a `.lark` terminal or production name, and a
            `docs/` path. Each is a
            distinct resolution oracle, and admitting one admits its
            false-positive population with it; the forms here are the ones
            whose oracle is a tracked file, a collected name or an import.
            An ELIDED citation -- two test names compressed into one token by
            sharing a prefix across a slash -- is in this class and fails LOUD
            rather than silent: the head resolves to nothing and the sweep
            names it, which is how the one live instance, in
            `tests/test_player_literal_range.py`, was found and written out.
            The largest known SILENT miss is a reference
            wrapping a line break somewhere other than an underscore or a
            slash -- a hyphenated path splitting at the hyphen can leave a
            fragment that resolves to a DIFFERENT real file. R4, issue #110
            owns the general scrape.
            (f) Ledger prose in a FUNCTION or class docstring, and a class
            ledger written into a commit message or PR body, are outside the
            walk: the population is module-level ledgers, and 208 of the
            tree's 231 `red under:` lines sit in function docstrings. Those
            are the inverted-polarity prose this module cuts rather than
            reads, so the exclusion loses no must-exist claim. R4, this
            ledger owns the record.
            (g) The census's UNRESOLVABLE bucket is counted, never pinned
            equal. It is dominated by things that are not references at all --
            DSL surface quoted in prose (`ranking:`, `for each cell`), type
            names, `.lark` production names, English -- and no oracle here
            separates a dangling reference sitting in it from correct prose,
            which is (c) and (e) restated as a number. Asserting an exact
            figure would redden on ordinary ledger edits while proving
            nothing, so what is asserted is the RESOLVING bucket, as a set.
            Bucket sizes are MEASUREMENTS, not pins (2026-08-20, 89 ledgers):
            2115 compound candidates, 538 claimed, 13 resolving-but-unclaimed
            over the 3 tokens in `CENSUS_RESIDUE`, 1564 unresolvable; 1308 of
            the candidates sit in a code span and 807 bare. Against the
            pre-review matcher the resolving bucket held 249 occurrences over
            228 distinct tokens -- that delta is the defect this round fixed,
            and it is the census's own witness that the bucket is the right
            one. Single-word tokens are outside the candidate population by
            construction, which is (c)'s population; R4, issue #110.
            (h) A bare COUNT of candidates cannot distinguish the census
            tokenizer narrowing from the ledgers shrinking. What guards that
            is `test_the_census_sees_every_token_the_forms_claim` (the
            population covers everything `_references` returns) plus
            `test_the_census_population_is_non_empty`; a tokenizer that stayed
            wide but classified wrongly would still need review. R4, this
            ledger owns the record.

red under: revert the `covered:` row of `tests/test_domain_registry.py` to the
    truncated citation it carried before this change -- `test_every_row_is_`
    plus `quantifiable`, wrapping across two lines inside one code span, where
    the function is `test_every_row_is_quantifiable_in_both_forms`. It was
    invisible to every form for as long as it sat in backticks.
    `test_every_ledger_reference_resolves` names it, and its `assert not
    found` is the assertion that reddens -- alone, 1 failed of 219.
    Executed 2026-08-20.
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
#   A code span is NOT PROSE. The quantified-claim form reads sentence
#   structure rather than tokens, so it runs on `_prose`, where each span is
#   one opaque identifier-shaped atom. That view is load-bearing, and its
#   probe is `test_a_quantifier_inside_a_code_span_is_not_a_prose_quantifier`.

_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Every code span's extent. The one place that decides where they are."""
    return [(m.start(), m.end()) for m in _CODE_SPAN.finditer(text)]


def _prose(text: str) -> str:
    """Each code span replaced by an underscore run of its own length -- an
    identifier-shaped opaque atom. A quantifier inside quoted surface
    (`each color simultaneously`) is then not a prose quantifier, and a code
    span anywhere reads as a named set. Offset-preserving, so a match indexes
    back into the original text."""
    out = list(text)
    for start, end in _code_spans(text):
        out[start:end] = "_" * (end - start)
    return "".join(out)


# --- the reference forms ----------------------------------------------------

def _law_quantifiers() -> tuple[str, ...]:
    """The quantifier words the RULE names, read from the rule. Hand-listing
    them here would let the matcher enforce a subset of the law and say
    nothing -- and a hand-list is also unreddenable, because a parametrization
    derived from it loses the row along with the word."""
    text = (ROOT / _DECISIONS).read_text()
    said = re.search(r"quantifies\s*—\s*([^—]+?)\s*—\s*names", text)
    assert said is not None, (
        "the quantifier rule's word list is not where this scrape looks; "
        "decisions.md \"A quantified `covered` sentence names its set\" owns it"
    )
    return tuple(w.strip() for w in said.group(1).split(",") if w.strip())


# The rule's own four words, so the matcher's vocabulary cannot narrow below
# the law's in silence. `no` costs nothing measurable -- zero extra matches
# over the 87 ledgers (2026-08-20) -- and its reach is probed like the rest.
QUANTIFIER_WORDS: tuple[str, ...] = _law_quantifiers()
_QUANTIFIER = f"(?:{'|'.join(QUANTIFIER_WORDS)})"
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
# An identifier a prose sentence can NAME a set with. On the `_prose` view a
# code span is already an underscore run, so one alternative covers both a
# backticked name and a bare snake_case one.
_IDENTIFIER = r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]*\b"

_MODULE_SHAPE = r"(?:cardlang|tests)(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
_TEST_REF = re.compile(r"(?<![\w./*-])(test_[A-Za-z0-9_]+)(?![\w*(]|\.[a-z])")
_TEST_GLOB = re.compile(r"(?<![\w./-])(test_[A-Za-z0-9_]*)\*")
_FILE_REF = re.compile(r"(?<![\w./-])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_-]+\.[a-z]+)\b")
_MODULE_REF = re.compile(rf"(?<![\w.])({_MODULE_SHAPE})")
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
REFERENCE_FORMS: tuple[str, ...] = (*_FORMS, "quantified-claim")


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
    """Every reference in one ledger row that resolves to nothing, plus every
    quantified completeness claim in a `covered:` row that names no set."""
    out: list[Finding] = []
    for form, token in _references(text):
        _, resolves, why = _FORMS[form]
        if not resolves(token):
            # The glob's oracle takes the prefix; the finding shows the glob.
            shown = token + "*" if form == "test-id-glob" else token
            out.append(Finding(form, row, shown, why))

    if row == "covered":
        prose = _prose(text)
        for m in _QUANTIFIED.finditer(prose):
            # The identifier must sit in the QUANTIFIED SPAN -- the quantifier,
            # its noun phrase and the coverage predicate. An identifier
            # elsewhere in the sentence is not the set being quantified over,
            # and accepting one made this check unfailable: "`test_some_probe`
            # proves every refusal arm has a probe" passed by citing its own
            # verifier. The law's exemplar is positional too -- "Every arm of
            # `opening_actions` has a probe" names the set inside the phrase.
            if not re.search(_IDENTIFIER, m.group(0)):
                out.append(Finding("quantified-claim", row,
                                   text[m.start():m.end()].strip(),
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
        head = re.match(r"^[ \t]*([a-z_]+):(.*)$", line)
        if head is not None and head.group(1) in LEDGER_ROWS:
            current = head.group(1)
            collected.setdefault(current, []).append(head.group(2).strip())
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
    "quantified-claim": ("every row of {} has a probe", "LEDGER_ROWS"),
}
_BAD: dict[str, tuple[str, str]] = {
    "test-id": ("proven by {} below", "test_the_walk_sees_a_module_that_is_not_here"),
    "test-id-glob": ("the family {} covers it", "test_no_such_prefix_at_all_*"),
    "file-path": ("the walk is {}", "tests/test_no_such_module_here.py"),
    "module-attr": ("the axis reads {}", "cardlang.builtins.no_such_attribute"),
    # No referent to mark: the claim is bad by naming nothing at all, so the
    # markup axis is a no-op here and the cell reads the same in both columns.
    "quantified-claim": ("every refusal arm has a probe", ""),
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
    ledger row -- the class sweep, not the two rows the ruling named. Markup
    never appears here: that a referent reads the same inside and outside a
    code span IS the policy, so the axis crosses the grid without an arm of
    its own. The `quantified-claim` form is the exception on the row axis:
    decisions.md scopes the quantifier rule to `covered:`, so the same
    sentence in `sampled:` or `residual:` is a judgment sitting where the
    register warns the reader, and flagging it would be the mechanism
    overreaching its own law.
    """
    if not bad:
        return False
    if form == "quantified-claim":
        return row == "covered"
    return True


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


def test_a_quantifier_inside_a_code_span_is_not_a_prose_quantifier() -> None:
    """The other half of the markup policy. `tests/test_domain_registry.py`
    quotes DSL surface -- "Non-row nouns (`for each color`, `each color
    simultaneously`) are guarded against ..." -- and reading `each` there as a
    prose quantifier made the sweep's one live match an accident: it went
    clean only because the quoted phrase beside it counted as a named set.

    red under: run `_QUANTIFIED` over `text` instead of `_prose(text)`.
    """
    quoted = "Non-row nouns (`for each color`, `each color simultaneously`) are guarded"
    assert not [f for f in unresolved("covered", quoted)
                if f.form == "quantified-claim"]
    # ...and the same words as PROSE still match.
    assert [f.form for f in unresolved("covered", "each color is guarded")] == [
        "quantified-claim"
    ]


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


@pytest.mark.parametrize("word", QUANTIFIER_WORDS)
def test_each_quantifier_word_is_matched(word: str) -> None:
    """The axis is `_law_quantifiers`, read from the rule in decisions.md, so
    a matcher covering fewer words than the law names fails here rather than
    quietly enforcing a subset. `every` currently has no live instance in the
    tree -- it is the primary word, so its reach is proven here rather than
    by the population.

    red under: narrow `_QUANTIFIER` to a literal `(?:every|all|each)` while
        the rule still names four -- the axis stays four rows and the `no`
        row goes red. (Deleting a word from the LAW instead is not a
        reddening edit: the row disappears with it, which is why the axis is
        derived rather than listed.)
    """
    findings = unresolved("covered", f"{word} refusal arm has a probe")
    assert [f.form for f in findings] == ["quantified-claim"]


@pytest.mark.parametrize(
    "frame,probe",
    [
        ("has-a-noun", "every refusal arm has a probe"),
        ("carries-its-noun", "every refusal arm carries its witness"),
        ("is-noun", "every refusal arm is probed"),
        ("are-noun", "all refusal arms are covered"),
    ],
)
def test_each_coverage_frame_is_matched(frame: str, probe: str) -> None:
    """`_COVERAGE_FRAME` is two alternatives with several fillers, hand-listed
    like `_ADJACENCY`. Each shape is proven to fire, so one drifting cannot
    leave the sweep looking clean on claims it stopped reading.

    red under: delete the named alternative from `_COVERAGE_FRAME`.
    """
    assert [f.form for f in unresolved("covered", probe)] == ["quantified-claim"]


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


@pytest.mark.parametrize(
    "where,text",
    [
        ("a cited verifier", "`test_some_probe` proves every refusal arm has a probe"),
        ("an earlier clause", "the grid reads `LEDGER_ROWS`; every refusal arm has a probe"),
        ("a previous sentence", "the grid reads `LEDGER_ROWS`. Every refusal arm has a probe."),
        ("an anaphor", "`harness.verb_status` is total, and all four of its cells are probed"),
        ("the reconciliation", "every refusal arm has a probe in `_PROBED_ARMS`"),
    ],
)
def test_an_identifier_outside_the_quantified_span_does_not_name_the_set(
    where: str, text: str
) -> None:
    """The identifier must be POSITIONALLY bound to the quantified set. An
    identifier merely present in the sentence is what made this check
    unfailable: it emitted zero findings over 89 ledgers and could not have
    fired even on the two sentences it matched, because citing the verifier
    ("`test_some_probe` proves every refusal arm has a probe") satisfied it.

    The law is served, not overreached. Its own exemplar is positional --
    "Every arm of `opening_actions` has a probe in `_PROBED_ARMS`" names the
    set INSIDE the noun phrase -- and its stated purpose is that the claim be
    reconcilable, which "all four of its cells" is not without a reader to
    follow the anaphor. A sentence flagged here is not condemned: the rule's
    own remedy is to name the set, or to move the claim to `sampled`.

    red under: search the sentence around the span instead of `m.group(0)`.
    """
    assert [f.form for f in unresolved("covered", text)
            if f.form == "quantified-claim"] == ["quantified-claim"], where


def test_a_set_named_inside_the_quantified_span_is_not_flagged() -> None:
    """The other side of the same cut: named in the noun phrase, and clean --
    backticked or bare, since markup is not what makes a name.

    red under: require the identifier to follow the coverage frame.
    """
    for named in ("every cell of `harness.verb_status` is probed",
                  "every cell of harness_verb_status is probed"):
        assert not [f for f in unresolved("covered", named)
                    if f.form == "quantified-claim"], named


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
