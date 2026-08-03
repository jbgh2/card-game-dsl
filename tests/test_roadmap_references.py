"""Every prose reference to docs/roadmap.md still resolves to a live section.

The deferred-work backlog moved to the GitHub tracker (issue #143 orders the
cross-cutting sequence); roadmap.md kept only what is not work — the
out-of-scope list, the walls ledger for grammar surface the checker defers,
and the pointers. A reference naming a section that moved to an issue is then
prose contradicting the spec, invisible because prose has no compiler: the
`ZONE_METHODS` class one currency over (issue #110, the backticked-identifier
scrape). This module is that compiler for the one file whose sections were
just redistributed.

The rule it enforces is that a reference must be CHECKABLE. Naming the file
alone (`see roadmap.md`) cannot be validated by any scrape, so a bare mention
is admitted only as a listed whole-file pointer with a reason; everything else
quotes the section it means, and the quoted title must match a heading
roadmap.md still carries. Requiring the title is what makes the pin able to
fail: it is what caught, when this module was written, four references already
naming sections that no longer existed
(``Let-bound local typing across statements``,
``Out-of-range player literals in declaration/binding positions``,
``Out-of-range seats in a `partnerships:` list``, and
``` `each … simultaneously` body shape is unchecked ```).

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every mention of roadmap.md outside roadmap.md itself either quotes
           a section title that file still carries, or is a listed whole-file
           pointer whose reason is recorded here.
domain:    every ``.py`` under ``cardlang/`` and ``tests/``, every ``.md``
           under ``docs/`` and ``.claude/skills/``, every ``.cardlang`` in the
           repo (corpus games, fixtures and rejection cases carry
           developer-facing ``//`` prose exactly as the Python and Markdown do),
           and ``CLAUDE.md`` — times every line mentioning ``roadmap.md``.
           Files are enumerated by glob, so a new module, doc or game is
           in-domain the day it exists.
registry:  roadmap.md's own headings, parsed from the file at test time (``##``
           sections and ``**bold**`` item lead-ins, at any nesting depth), so
           renaming a section reddens every reference to the old name and no
           expected-title list can drift from the file.
covered:   both reference shapes (title-quoting and bare) in both comment
           currencies (Python docstring/comment, Markdown prose and link
           text), and both dash spellings (``--`` and em dash) — each pinned by
           a synthetic-source probe below, so the classifier cannot rot
           vacuously green.
sampled:   the title match is normalized (whitespace, dash spelling, trailing
           period) and then exact. A reference quoting a *sub*-phrase of a live
           heading fails; that is deliberate, since a partial quote is what
           makes a stale reference look live.
residual:  ``docs/superpowers/plans/`` and ``docs/research/`` are outside the
           domain — both are dated records of what was true when written
           (decisions.md "Closed-domain completeness", the DATE-don't-DELETE
           carve-out), and rewriting their references would falsify the record
           rather than repair it.
           Python DIAGNOSTIC text is carved out as a DERIVED class
           (`_diagnostic_lines`): the argument of a diagnostic-bag call
           (`DIAGNOSTIC_METHODS`) or anything inside a `raise`. A designer who
           hits a wall offline can open a repo doc and cannot open a tracker
           issue, so those messages keep naming roadmap.md. Deriving the class
           keeps a new diagnostic exempt the day it is written while a new
           comment is not; a hand-list would be the partial enumeration this
           repo treats as the defect.

           The exemption waives the REQUIREMENT to name a section, never the
           CHECK on a section that is named — an exempt line quoting a dead
           heading still fails. Both halves were wrong in the first version and
           were caught by review, not by this module: the carve-out read "every
           non-docstring string literal", which swept in assertion messages,
           and it skipped exempt lines entirely, which hid a dangling
           `registry.py` pointer inside the declared domain (Codex, PR #151).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROADMAP = REPO_ROOT / "docs" / "roadmap.md"

# Paths whose roadmap references are dated records, not live spec — plus this
# module, whose every mention of roadmap.md defines the mechanism rather than
# citing the file (the stale titles in its docstring are the examples it caught).
EXCLUDED_DIRS = (
    "docs/superpowers/plans/",
    "docs/research/",
    "tests/test_roadmap_references.py",
)

# Bare mentions that legitimately name the file as a whole rather than a
# section. Each entry is (repo-relative path, a substring of the line) and
# carries its reason here; the pin below fails an entry that matches nothing,
# so this list cannot quietly grow into a blanket exemption. Python
# DIAGNOSTIC text is not listed here — it is carved out as a derived class by
# `_diagnostic_lines` below, since enumerating it would be the hand-list this
# repo treats as the defect.
WHOLE_FILE_POINTERS: tuple[tuple[str, str], ...] = (
    # The orientation map names every file in docs/ by its subject.
    ("CLAUDE.md", "Out-of-scope list + the checker's guards ledger"),
    # "Out of scope" points at the whole out-of-scope list, not one entry.
    ("CLAUDE.md", "for the full list of"),
)

# The bag methods that emit designer-facing text. A string reaching one of
# these is a diagnostic; a string anywhere else in a module is not.
DIAGNOSTIC_METHODS = frozenset({"error", "warn", "warning"})

_MENTION = re.compile(r"roadmap\.md")
# A quoted title must follow the mention closely — within the connective text
# a citation uses (", ", " (", ", item "). Anything longer is an unrelated
# quote later in the sentence, not a section name.
#
# Two delimiters, tried independently. Double quotes are the repo's citation
# convention; single quotes also count because an f-string diagnostic nests
# them inside its own double quotes (`f"... (docs/roadmap.md, 'Title')"`) — the
# shape that hid a dangling pointer in cardlang/openspiel/registry.py.
#
# Neither pattern alone is sound: the single-quote class truncates a title that
# CONTAINS an apostrophe ("A team-scored game's `winner` …"), and the
# double-quote class mis-reads the f-string shape. So both are extracted and a
# reference is live when ANY candidate resolves — a reference is only stale
# when no reading of it names a section that exists.
_QUOTED_TITLES = (
    re.compile(r"roadmap\.md[^\"“]{0,24}[\"“]([^\"”]{4,120})[\"”]"),
    re.compile(r"roadmap\.md(?!'s)[^']{0,24}'([^']{4,120})'"),
)


def _candidate_titles(window: str) -> list[str]:
    return [
        found.group(1)
        for pattern in _QUOTED_TITLES
        for found in [pattern.search(window)]
        if found is not None
    ]

_SECTION = re.compile(r"^#{2,4}\s+(.+?)\s*$")
_BOLD_LEAD = re.compile(r"^\s*(?:[-*]\s+)?\*\*(.+?)\*\*")


def _normalize(title: str) -> str:
    """Fold the spelling differences that are not identity differences."""
    text = title.replace("--", "—").replace("–", "—")
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".,:;").strip()


def _live_titles() -> set[str]:
    """The section names roadmap.md carries, parsed from the file itself."""
    titles: set[str] = set()
    for line in ROADMAP.read_text().splitlines():
        for pattern in (_SECTION, _BOLD_LEAD):
            found = pattern.match(line)
            if found:
                titles.add(_normalize(found.group(1)))
    return titles


def _in_domain() -> list[Path]:
    paths: list[Path] = [REPO_ROOT / "CLAUDE.md"]
    for pattern in ("cardlang/**/*.py", "tests/**/*.py", "docs/**/*.md",
                    ".claude/skills/**/*.md", "**/*.cardlang"):
        paths.extend(REPO_ROOT.glob(pattern))
    return sorted(
        p for p in paths
        if p.is_file()
        and p != ROADMAP
        and not any(d in p.relative_to(REPO_ROOT).as_posix() for d in EXCLUDED_DIRS)
    )


def _mentions(text: str) -> list[tuple[int, str]]:
    """Each mention, as its line joined with the two that follow it.

    Prose wraps, so a quoted section title routinely straddles a line break
    (``roadmap.md, "Family libraries — unchecked\\n    residuals in the
    `requires` contract"``). Matching one line at a time would read those as
    untitled and force the prose to be reflowed to suit the scrape; the window
    is what lets the citation be written the way prose is written. Comment
    leaders are stripped so a wrapped Python comment joins cleanly.
    """
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if not _MENTION.search(line):
            continue
        window = " ".join(
            re.sub(r"^\s*#\s?", " ", follow).strip()
            for follow in lines[index : index + 3]
        )
        out.append((index + 1, re.sub(r"\s+", " ", window)))
    return out


def _allowed(relative: str, line: str) -> bool:
    return any(
        relative == path and needle in line
        for path, needle in WHOLE_FILE_POINTERS
    )


def _diagnostic_lines(text: str) -> set[int]:
    """Line numbers spanned by user-facing DIAGNOSTIC text in a Python module.

    A diagnostic names a repo doc because a designer who hits the wall can open
    `docs/roadmap.md` from their checkout and cannot open a tracker issue
    offline. The class is DERIVED rather than enumerated, so a new diagnostic
    is carved out the day it is written — but it is derived from what makes a
    string a diagnostic, not from where it is not: the argument of a
    diagnostic-bag call (`bag.error(...)`), or anything inside a `raise`.

    Every OTHER string literal stays under the title rule. An assertion message
    telling a maintainer to keep a doc in step is developer prose that happens
    to be quoted, and treating "not a docstring" as "user-facing" swept those
    in — which let genuinely stale references sit inside the declared domain
    while the sweep reported clean.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:  # not importable Python; nothing is carved out
        return set()
    spanned: set[int] = set()

    def cover(node: ast.AST) -> None:
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Constant)
                and isinstance(inner.value, str)
                and inner.end_lineno is not None
            ):
                spanned.update(range(inner.lineno, inner.end_lineno + 1))

    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            cover(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in DIAGNOSTIC_METHODS
        ):
            for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                cover(argument)
    return spanned


def test_every_roadmap_reference_names_a_live_section() -> None:
    live = _live_titles()
    unresolved: list[str] = []
    for path in _in_domain():
        relative = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text()
        diagnostics = _diagnostic_lines(text) if path.suffix == ".py" else set()
        for number, line in _mentions(text):
            candidates = _candidate_titles(line)
            # An exemption waives the REQUIREMENT to name a section, never the
            # check on a section it does name: a diagnostic quoting a heading
            # that no longer exists is exactly the dangling pointer this module
            # exists to catch, and skipping it wholesale made the carve-out a
            # blind spot rather than a carve-out.
            if not candidates and (_allowed(relative, line) or number in diagnostics):
                continue
            if not candidates:
                unresolved.append(
                    f"{relative}:{number}: names roadmap.md with no section "
                    f"title — re-anchor it to its tracker issue, quote a "
                    f"section roadmap.md still carries, or list it in "
                    f"WHOLE_FILE_POINTERS with a reason. Write the title "
                    f"ADJACENT to the citation (roadmap.md, \"Title\") — a "
                    f"title further into the sentence is not read as one"
                    f"\n    {line.strip()}"
                )
            elif not any(_normalize(c) in live for c in candidates):
                unresolved.append(
                    f"{relative}:{number}: quotes roadmap.md section "
                    f"{candidates[0]!r}, which roadmap.md no longer carries "
                    f"— it moved to the tracker\n    {line.strip()}"
                )
    assert not unresolved, (
        f"{len(unresolved)} roadmap.md reference(s) do not resolve:\n\n"
        + "\n".join(unresolved)
    )


def test_every_whole_file_pointer_still_matches_a_real_site() -> None:
    """A listed exemption that matches nothing is a blanket in waiting."""
    dead: list[tuple[str, str]] = []
    for path, needle in WHOLE_FILE_POINTERS:
        target = REPO_ROOT / path
        text = target.read_text() if target.is_file() else ""
        if not any(needle in line for _, line in _mentions(text)):
            dead.append((path, needle))
    assert not dead, (
        "WHOLE_FILE_POINTERS entries match no roadmap.md mention — delete "
        f"them rather than leaving the exemption standing: {dead}"
    )


# --- probes: the classifier itself cannot go vacuously green ---------------


def test_the_registry_is_parsed_from_the_file_not_hand_listed() -> None:
    """A renamed section must redden its references, so titles come from disk."""
    titles = _live_titles()
    assert titles, "no headings parsed out of roadmap.md — the registry is empty"
    assert "Out of scope" in titles or "Explicitly deferred" in titles, (
        "roadmap.md carries neither of the headings this pin expects to "
        "survive; if the stub was renamed, update this probe deliberately"
    )


def test_both_dash_spellings_normalize_to_one_title() -> None:
    assert _normalize("Positional zones -- walled residuals") == _normalize(
        "Positional zones — walled residuals"
    )


def test_a_quote_far_from_the_mention_is_not_read_as_a_title() -> None:
    """The window keeps an unrelated later quote from masking a bare mention."""
    far = 'see roadmap.md, and separately the rule that a game is "complete"'
    assert _candidate_titles(far) == []
    near = 'recorded in roadmap.md, "Grammar surface deferred by the checker"'
    assert "Grammar surface deferred by the checker" in _candidate_titles(near)


def test_both_quote_delimiters_yield_a_candidate() -> None:
    """An f-string diagnostic nests single quotes; a title may contain one."""
    nested = "f\"... (docs/roadmap.md, 'Packaging the corpus for distribution').\""
    assert "Packaging the corpus for distribution" in _candidate_titles(nested)
    # A title containing an apostrophe must survive: the single-quote reading
    # truncates it, so the double-quote reading has to be offered alongside.
    apostrophe = "(roadmap.md, \"A team-scored game's `winner` is a team index\")"
    assert (
        "A team-scored game's `winner` is a team index"
        in _candidate_titles(apostrophe)
    )


def test_the_possessive_is_not_read_as_a_quote_delimiter() -> None:
    assert _candidate_titles("roadmap.md's own wording, not a cited section") == []


def test_diagnostic_text_is_carved_out_but_other_strings_are_not() -> None:
    """The carve-out separates designer-facing output from developer prose.

    The failure this pins: treating "not a docstring" as "user-facing" swept in
    assertion messages, which let stale references sit inside the declared
    domain while the sweep reported clean (Codex, PR #151).
    """
    source = (
        '"""A docstring naming roadmap.md."""\n'
        "# A comment naming roadmap.md.\n"
        "def f() -> None:\n"
        '    """An inner docstring naming roadmap.md."""\n'
        '    bag.error("resource movements are deferred — roadmap.md")\n'
        '    raise RuntimeError("not shipped — roadmap.md")\n'
        '    assert x, "keep roadmap.md in step"\n'
        '    label = "see roadmap.md"\n'
    )
    carved = _diagnostic_lines(source)
    assert 5 in carved, "a bag.error message must be carved out"
    assert 6 in carved, "a raise message must be carved out"
    assert 1 not in carved, "a module docstring must stay under the title rule"
    assert 2 not in carved, "a comment must stay under the title rule"
    assert 4 not in carved, "a function docstring must stay under the title rule"
    assert 7 not in carved, "an assertion message is developer prose, not output"
    assert 8 not in carved, "a plain string binding is not a diagnostic"


def test_a_partial_quote_of_a_live_heading_does_not_resolve() -> None:
    live = _live_titles()
    full = "Grammar surface deferred by the checker"
    assert _normalize(full) in live, "the walls ledger heading moved"
    assert _normalize("Grammar surface deferred") not in live
