"""Every vocabulary reference resolves to a glossary entry.

property:   a term named in code or docs can be looked up. Concretely: every
            entry parses and declares fields from closed sets, every term is
            unique, the index is exactly what the entries generate, and every
            wiki link and `docs/glossary/` link anywhere in the repo names an
            entry that exists.
domain:     every file under `docs/glossary/`, and every wiki link or
            `docs/glossary/<slug>.md` reference in any tracked `.py` or `.md`.
registry:   the entry directory itself, walked -- there is no hand-listed term
            list anywhere, so a term added or removed arrives here without
            anyone updating a fixture. Field vocabularies come from
            `tools.glossary_index.LAYERS` / `.STATUSES`.
covered:    entry parse + field closure + slug/term uniqueness + index equality
            + reference resolution, each over the full walk.
sampled:    none.
residual:   Resolution only, deliberately -- issue #214 D4. Nothing here checks
            that prose USES a reserved word correctly, or that a docstring
            mentioning a concept links it. Those are review judgment (and the
            direction review's job); a linter that guessed at them would fail on
            ordinary English. The consequence is that an unlinked mention is
            invisible to this gate: it guarantees that references RESOLVE, never
            that references EXIST. R4, and recorded here rather than filed --
            #214 D4 rules it deliberate, not deferred.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

from tools.glossary_index import (
    ENTRIES,
    INDEX,
    LAYERS,
    ROOT,
    STATUSES,
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
# The discriminator against Python's `Callable[[int], str]` is the character
# BEFORE the brackets, not the shape of what is inside: a subscript's `[[` always
# follows an identifier or a closing bracket, a reference never does.
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

    Four words are BOTH a concept and a reserved word (`round`, `rule`,
    `library`, `outcome`). They are one entry carrying `reserved: true`, not
    two entries, which is why reservation is a field rather than a status.

    red under: copy any entry file to a new slug keeping its `term:`.
    """
    entries = load()
    terms = [e["term"].lower() for e in entries]
    slugs = [e["_slug"] for e in entries]
    assert len(set(terms)) == len(terms), (
        f"duplicate term: {sorted({t for t in terms if terms.count(t) > 1})}"
    )
    assert len(set(slugs)) == len(slugs)


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
    known = {e["_slug"] for e in load()} | {e["term"].lower() for e in load()}
    bad: list[str] = []
    for path in _tracked_text_files():
        for match in re.findall(_WIKI_LINK, path.read_text()):
            if "," in match or not any(c.isalpha() for c in match):
                continue  # a nested list literal, not a reference
            if match.lower() not in known and match.lower().replace(" ", "-") not in known:
                bad.append(f"{path.relative_to(ROOT)}: doubled-bracket {match!r}")
    assert not bad, "wiki links naming no entry:\n  " + "\n  ".join(bad)


def test_every_glossary_link_resolves_to_an_entry() -> None:
    """The markdown spelling of the same reference, for surfaces where a link
    renders (docs, issues, PR bodies) -- issue #214 D3.

    red under: link a glossary path whose entry does not exist, from any doc.
    (Stated rather than written: this module is itself in the walk, so a
    literal broken link here would redden the check permanently.)
    """
    known = {p.stem for p in ENTRIES.glob("*.md")}
    bad: list[str] = []
    for path in _tracked_text_files():
        for match in re.findall(_GLOSSARY_LINK, path.read_text()):
            if match.startswith("_"):
                continue
            if match not in known:
                bad.append(f"{path.relative_to(ROOT)}: glossary/{match}.md")
    assert not bad, "glossary links naming no entry:\n  " + "\n  ".join(bad)


def test_the_entry_directory_is_not_empty() -> None:
    """The emptiness guard, at the producer. Every check above quantifies over
    `load()`; an empty directory would pass all of them vacuously, which is the
    defect class this repo ranks beside accepted-but-ignored.

    red under: point `ENTRIES` at an empty directory.
    """
    assert len(load()) > 50, "the entry walk collapsed -- every check above is vacuous"
