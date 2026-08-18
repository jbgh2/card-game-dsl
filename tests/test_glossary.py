"""Every vocabulary reference resolves to a glossary entry.

property:   a term named in code or docs can be looked up. Concretely: every
            entry parses and declares fields from closed sets, every term is
            unique, the index is exactly what the entries generate, and every
            wiki link and `docs/glossary/` link anywhere in the repo names an
            entry that exists.
domain:     every file under `docs/glossary/`, and every wiki link or
            `docs/glossary/<slug>.md` reference in the PROSE of any tracked `.py`
            or `.md` -- Python comments and docstrings, Markdown outside a fence.
            Code, and DSL fixtures written as Python strings, are not prose and
            are out of the domain by construction (`_prose_text`).
registry:   the entry directory itself, walked -- there is no hand-listed term
            list anywhere, so a term added or removed arrives here without
            anyone updating a fixture. Field vocabularies come from
            `tools.glossary_index.LAYERS` / `.STATUSES`.
covered:    entry parse + field closure + slug/term uniqueness + index equality
            + reference resolution, each over the full walk; and the prose/code
            boundary itself, as the parametrized rows of
            `test_only_prose_positions_are_scanned_for_references`. Both
            resolution checks assert they scanned a reference at all, so neither
            can pass by reading nothing.
sampled:    none.
note:       This module is inside its own walk, so its comments and docstrings
            never spell a live reference -- every example spelling lives in a
            parametrized row, which is a string literal and therefore code.
residual:   TWO ENTRIES MAY MEAN THE SAME THING and nothing here notices. The
            names are guaranteed distinct; the meanings are not. This is not a
            gap waiting for a check -- it was measured: lexical similarity scores
            0.13 on a real instance (Hand Loop defined as Hand, caught in review
            on PR #323), and "a compound must link its head" fails too, because
            that entry did link `[[hand]]`. Semantic duplication is review
            judgment, the same ruling #214 D4 makes for prose usage. R4, recorded
            here rather than filed: the mechanism is the reviewer, and a check
            that cannot fire would only look like coverage.
            Resolution only, deliberately -- issue #214 D4. Nothing here checks
            that prose USES a reserved word correctly, or that a docstring
            mentioning a concept links it. Those are review judgment (and the
            direction review's job); a linter that guessed at them would fail on
            ordinary English. The consequence is that an unlinked mention is
            invisible to this gate: it guarantees that references RESOLVE, never
            that references EXIST. R4, and recorded here rather than filed --
            #214 D4 rules it deliberate, not deferred.
"""

from __future__ import annotations

import ast
import io
import pathlib
import re
import subprocess
import tokenize

import pytest

from tools.glossary_index import (
    ENTRIES,
    INDEX,
    LAYERS,
    ROOT,
    STATUSES,
    EntryError,
    load,
    parse_entry,
    render,
)

# A wiki link, captured WIDE and validated after -- never narrowed to the
# well-formed spelling. Narrowing is what a typo escapes through: a pattern
# matching only `[a-z0-9-]+` does not match a capitalised or
# underscored spelling at all, so the check whose entire job is catching
# mistyped references reports success on precisely those.
#
# Capturing wide means the pattern alone cannot tell a reference from Python's
# own doubled brackets, and it must not try: narrowing the SPELLING to exclude a
# one-element nested list would re-admit every typo. So the discrimination is by
# POSITION -- `_prose_text` hands these patterns only the regions where doubled
# brackets mean a reference. What survives inside those regions is the lookbehind
# against a subscript like `Callable` applied to a list, written in a docstring:
# a subscript's brackets always follow an identifier or a closing bracket, a
# reference's never do.
_WIKI_LINK = r"(?<![\w\]])\[\[([^\[\]\n]+)\]\]"

# Same discipline for the path spelling: accept any filename shape, then check
# it, so an uppercase or underscored path is reported rather than skipped.
_GLOSSARY_LINK = r"glossary/([A-Za-z0-9_.-]+)\.md"

BOOLS = ("true", "false")
REQUIRED = {"term", "definition", "layer", "status", "reserved", "home",
            "see", "retired_spellings", "findings"}


def _tracked_text_files() -> list[pathlib.Path]:
    """Every `.py` and `.md` file git tracks.

    Asking git rather than walking the tree is the whole point: a hand-written
    exclusion list gets this wrong in both directions. It first excluded the
    ENTIRE repository, because it matched directory names against the absolute
    path and this checkout lives under `.claude/worktrees/` -- both reference
    checks passed while reading nothing. Correcting that to a relative match
    then still dropped `.claude/skills/`, which git tracks and which is exactly
    where a broken reference would mislead an agent. `git ls-files` has no
    opinion to get wrong: tracked is tracked.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z", "*.py", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    out = [ROOT / name for name in listing.split("\0") if name]
    assert out, "the file walk found nothing -- both reference checks are vacuous"
    return out


def _spellings(entry: dict[str, str]) -> list[str]:
    """The `retired_spellings` list, parsed. The frontmatter is a hand format
    (see `parse_entry`), so the list is a hand parse too: `[a, b]` or `[]`."""
    raw = entry["retired_spellings"].strip()
    if not raw.startswith("[") or not raw.endswith("]"):
        raise EntryError(
            f"{entry['_slug']}.md: retired_spellings must be a [bracketed, list], "
            f"got {raw!r}"
        )
    return [s.strip().strip("`") for s in raw[1:-1].split(",") if s.strip()]


def _prose_text(suffix: str, text: str) -> str:
    """The regions of a file where a doubled bracket MEANS a reference.

    A reference is prose, so the discriminator is position, not spelling. Python
    holds prose in exactly two places, comments and docstrings, and this takes
    both and nothing else. A one-element nested list is code; a DSL fixture
    written as a Python string is source in another language; neither reaches
    the patterns, while a link in a docstring or a `#` comment does -- misspelled
    exactly as written, which is the whole point of capturing wide. In Markdown
    it is everything outside a fenced block, so a Python example in a fence gets
    the same answer as the Python file it was copied from.

    A tracked `.py` that will not parse raises here rather than being skipped: a
    file silently dropped from the walk is the defect this module already had
    once.
    """
    if suffix == ".py":
        holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        prose = [
            doc
            for node in ast.walk(ast.parse(text))
            if isinstance(node, holders) and (doc := ast.get_docstring(node, clean=False))
        ]
        prose += [
            tok.string
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type == tokenize.COMMENT
        ]
        return "\n".join(prose)
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept)


def _scannable() -> list[tuple[pathlib.Path, str]]:
    out = []
    for path in _tracked_text_files():
        try:
            out.append((path, _prose_text(path.suffix, path.read_text())))
        except (SyntaxError, tokenize.TokenError) as exc:  # pragma: no cover - loud by design
            raise AssertionError(f"{path.relative_to(ROOT)} will not parse: {exc}") from exc
    return out


def test_every_entry_parses_and_declares_the_required_fields() -> None:
    """red under: delete a frontmatter line from any entry."""
    for entry in load():
        missing = REQUIRED - entry.keys()
        assert not missing, f"{entry['_slug']}.md is missing {sorted(missing)}"


@pytest.mark.parametrize("field,allowed", [("layer", LAYERS), ("status", STATUSES),
                                           ("reserved", BOOLS)])
def test_closed_fields_take_only_their_declared_values(field: str, allowed: tuple[str, ...]) -> None:
    """The three enumerated fields are closed sets. A new value is a design
    decision -- it widens the index's section list or the reservation rule --
    so it arrives here rather than silently becoming a category of one.

    red under: set `layer: nonsense` in any entry.
    """
    for entry in load():
        assert entry[field] in allowed, (
            f"{entry['_slug']}.md has {field}={entry[field]!r}, not one of {list(allowed)}"
        )


def test_terms_and_slugs_are_unique() -> None:
    """One name, one entry -- the glossary's own rule applied to itself.

    Shadow Guard. `test_every_lookup_name_reaches_exactly_one_entry` owns this
    class and is strictly wider: it canonicalises before comparing and covers
    retired spellings too, so anything caught here is caught there. This stays
    because a bare duplicate term is the common case and deserves to say so in
    its own words, and it normalises the same way rather than a third way.

    Four words are BOTH a concept and a reserved word (`round`, `rule`,
    `library`, `outcome`). They are one entry carrying `reserved: true`, not
    two entries, which is why reservation is a field rather than a status.

    red under: copy any entry file to a new slug keeping its `term:`.
    """
    entries = load()
    terms = [_canon(e["term"]) for e in entries]
    slugs = [e["_slug"] for e in entries]
    assert len(set(terms)) == len(terms), (
        f"duplicate term: {sorted({t for t in terms if terms.count(t) > 1})}"
    )
    assert len(set(slugs)) == len(slugs)


def test_a_stated_retirement_is_also_a_structured_one() -> None:
    """An entry that SAYS a spelling is retired carries it in `retired_spellings`.

    The field is the half a reader greps: someone meeting `partnership` in a
    closed issue lands on Team by finding the spelling, not by reading Team's
    prose and recognising it. Prose alone leaves that lookup broken while
    looking complete, so the two cannot be allowed to drift apart.

    Deliberately checks PRESENCE, not contents: parsing which spellings a
    sentence retires needs a regex over English, and that regex is the part
    that would quietly stop matching. The entry corpus supplies the domain --
    nothing here is hand-listed.

    red under: empty any populated `retired_spellings` whose entry says
    "Retired" (before this pin was satisfied, all ten were empty).
    """
    bad = [
        e["_slug"]
        for e in load()
        if "Retired" in (e["definition"] + e.get("_body", ""))
        and e["retired_spellings"].strip() in ("[]", "")
    ]
    assert not bad, (
        "these entries state a retirement in prose but carry no "
        f"`retired_spellings`: {sorted(bad)}"
    )


def _canon(name: str) -> str:
    """The ONE normalisation a name gets before it is compared to anything.

    Both the reference checks and the uniqueness check route through this, and
    that is the point: when they normalised separately they disagreed, and the
    disagreement was invisible. `[[card piece]]` resolved to `card-piece.md`
    because the resolver dashed its input, while the namespace stored retired
    spellings raw -- so a second entry could retire `card piece`, the reference
    would still reach the first entry, and the collision check stayed green.
    Two spellings of one rule is the defect; one function is the fix.
    """
    return name.strip().lower().replace(" ", "-")


def _names_reaching(entry: dict[str, str]) -> set[str]:
    """The canonical names a wiki link or glossary link may use for this entry."""
    return {_canon(entry["_slug"]), _canon(entry["term"])}


def _lookup_namespace() -> dict[str, list[str]]:
    """Every name the glossary can be looked up BY, mapped to the entries
    claiming it: the names a reference resolves by, plus the retired spellings a
    reader greps. One namespace, so one uniqueness check -- and every member
    normalised by `_canon`, exactly as the resolver normalises its input.
    """
    ns: dict[str, list[str]] = {}
    for e in load():
        for name in _names_reaching(e) | {_canon(s) for s in _spellings(e)}:
            ns.setdefault(name, []).append(e["_slug"])
    assert ns, "the namespace is empty -- this check would pass over nothing"
    return ns


def test_every_lookup_name_reaches_exactly_one_entry() -> None:
    """One name, one meaning, over the WHOLE namespace a reader can arrive by.

    A name that two entries claim sends the reader to two authorities of equal
    standing -- the defect the glossary exists to remove -- and it does not
    matter which kind of name it is. Slug against slug, term against term,
    retired spelling against live term, retired spelling against retired
    spelling, and term against another entry's slug are one class, so they get
    one check rather than the two-of-five this covered when the review found it.

    red under: copy any entry to a new slug keeping its `term:`; or add a live
    term (`team`, `transfer`) to another entry's `retired_spellings`; or list one
    retired spelling on two entries.
    """
    clashes = [
        f"{name!r} is claimed by {sorted(set(slugs))}"
        for name, slugs in sorted(_lookup_namespace().items())
        if len(set(slugs)) > 1
    ]
    assert not clashes, (
        "these names reach more than one entry:\n  " + "\n  ".join(clashes)
    )


def test_the_index_is_exactly_what_the_entries_generate() -> None:
    """`docs/glossary.md` is derived, so it is pinned like a golden: edit an
    entry without regenerating and this fails, naming the command.

    red under: change any `definition:` and do not regenerate.
    """
    assert INDEX.read_text() == render(load()), (
        "docs/glossary.md is stale -- regenerate it with "
        "`python -m tools.glossary_index --write`"
    )


def test_every_wiki_link_resolves_to_an_entry() -> None:
    """A wiki link in a docstring or comment names an entry. This is the half of
    the linter that will actually fire as the docstring pass lands: a term
    linked before its entry exists, or after a retirement, fails here.

    red under: write a wiki link to a term that has no entry -- including
    a MISSPELLED one (capitals, an underscore), which is the case a
    narrower pattern would skip instead of report.
    """
    known = {n for e in load() for n in _names_reaching(e)}
    bad: list[str] = []
    seen = 0
    for path, prose in _scannable():
        for match in re.findall(_WIKI_LINK, prose):
            seen += 1
            if _canon(match) not in known:
                bad.append(f"{path.relative_to(ROOT)}: doubled-bracket {match!r}")
    assert not bad, "wiki links naming no entry:\n  " + "\n  ".join(bad)
    assert seen, "no wiki link was scanned at all -- this check validated nothing"


def test_every_glossary_link_resolves_to_an_entry() -> None:
    """The markdown spelling of the same reference, for surfaces where a link
    renders (docs, issues, PR bodies) -- issue #214 D3.

    red under: link a glossary path whose entry does not exist, from any doc.
    (Stated rather than written: this module is itself in the walk, so a
    literal broken link here would redden the check permanently.)
    """
    known = {p.stem for p in ENTRIES.glob("*.md")}
    bad: list[str] = []
    seen = 0
    for path, prose in _scannable():
        for match in re.findall(_GLOSSARY_LINK, prose):
            if match.startswith("_"):
                continue
            seen += 1
            if match not in known:
                bad.append(f"{path.relative_to(ROOT)}: glossary/{match}.md")
    assert not bad, "glossary links naming no entry:\n  " + "\n  ".join(bad)
    assert seen, "no glossary link was scanned at all -- this check validated nothing"


@pytest.mark.parametrize("suffix,source,found", [
    # Python code is not prose: these are list literals, and flagging them would
    # redden the suite on valid code that never mentioned the glossary.
    (".py", "rows = [[item]]\n", []),
    (".py", "def f():\n    return [[value]]\n", []),
    (".py", "x = ([[a]], [[b]])\n", []),
    # A DSL fixture written as a string literal is source in another language,
    # not prose -- the case that decided comments-and-docstrings over all strings.
    (".py", 'SRC = """game { zones [[0, 1]] }"""\n', []),
    # ... but a reference in a comment or a docstring is, misspelling included.
    (".py", "# see [[owner-guard]]\n", ["owner-guard"]),
    (".py", '"""doc [[Missing Term]]"""\n', ["Missing Term"]),
    (".py", 'x = 1  # [[permissive_top]]\n', ["permissive_top"]),
    # A type signature written inside a docstring: the lookbehind still earns
    # its place, because tokenising cannot tell prose from a signature.
    (".py", '"""Takes Callable[[int], str]."""\n', []),
    # Markdown is prose except inside a fence -- a Python example pasted into a
    # doc gets the same answer as the Python file it came from.
    (".md", "See [[owner-guard]].\n", ["owner-guard"]),
    (".md", "```python\nrows = [[item]]\n```\n", []),
    (".md", "```\n[[x]]\n```\nand [[hand]] after\n", ["hand"]),
])
def test_only_prose_positions_are_scanned_for_references(
    suffix: str, source: str, found: list[str]
) -> None:
    """The position discriminator, probed with the sentences it exists to tell
    apart. Capturing wide (so typos are reported) is only safe because the text
    handed to the pattern is prose; these rows pin both halves.

    red under: make `_prose_text` return `text` unchanged -- the three Python
    list-literal rows flag `item`/`value`/`a`.
    """
    assert re.findall(_WIKI_LINK, _prose_text(suffix, source)) == found


def test_the_entry_directory_is_not_empty() -> None:
    """The emptiness guard, at the producer. Every check above quantifies over
    `load()`; an empty directory would pass all of them vacuously, which is the
    defect class this repo ranks beside accepted-but-ignored.

    red under: point `ENTRIES` at an empty directory.
    """
    assert len(load()) > 50, "the entry walk collapsed -- every check above is vacuous"


def test_a_retired_spelling_is_actually_retired() -> None:
    """`retired_spellings:` is a claim ABOUT THE TREE, and until now nothing
    checked it against one: the index pin reconciles prose to field, so an
    entry could name a spelling that is still live everywhere and stay green.

    The instance that motivated this: Card Strength listed
    `belote_trump_height` / `tarot_trump_height` as retired while two corpus
    games called them (they retire when those games migrate, issue #250 PRs
    4-5). A retired-spelling claim a reader trusts is how a rename gets
    declared finished before it is.

    Scope: a spelling that looks like a code identifier (no spaces) must not
    survive as a NAME the engine or the corpus still uses. Prose spellings
    (retired English phrasings) are not identifiers and are skipped -- they
    have no tree to check against.

    red under (executed, reverted): restore either height Primitive to Card
    Strength's `retired_spellings` -- this fails naming it and the corpus
    files that still call it."""
    import re
    from pathlib import Path as _P

    roots = [_P("cardlang"), _P("docs/games")]
    live: dict[str, list[str]] = {}
    for entry in load():
        for spelling in _spellings(entry):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", spelling):
                continue  # a prose spelling, not an identifier
            hits = [
                str(f)
                for root in roots
                for f in root.rglob("*")
                if f.is_file()
                and f.suffix in (".py", ".cardlang", ".lark")
                and re.search(rf"\b{re.escape(spelling)}\b", f.read_text())
            ]
            if hits:
                live[f"{entry['_slug']}.md: {spelling}"] = sorted(hits)[:4]
    assert not live, (
        "entries claim a spelling is retired while the tree still uses it:\n"
        + "\n".join(f"  {k} -> {v}" for k, v in sorted(live.items()))
    )
