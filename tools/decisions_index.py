"""Generate `docs/decisions.md` -- the index -- from the sections in `docs/decisions/`.

The spec is one file per decision: each file under `docs/decisions/` holds one
whole `##` section, with the `###` sub-sections and bold-lead rulings that
bound it. The index is derived, never edited: one row per decision, giving its
title, its file and the first sentence of its body, with its sub-section
titles nested beneath so a search for any heading lands on the file that
holds it. `tests/test_decisions_index.py` pins the index against this
generator, as `tests/test_glossary.py` pins the glossary's.

Reading order is `_order.txt`, one slug per line. It is a registry the pins
hold both ways against the directory: every section file is listed exactly
once and every listed slug has a file. `_preamble.md` is the text above the
rows. Files whose name starts with `_` are the index's own parts, never
sections.

Contract
  assumes:      each section file opens with its `## ` heading and holds no
                other `## ` or `# ` heading outside a code fence; its first
                paragraph is prose.
  establishes:  `load()` returns the sections in reading order, each with
                its title, sub-headings, summary and text; `render()` is the
                one spelling of the index.
  illegal after: a section file missing from `_order.txt`, a listed slug
                with no file, a duplicate heading across the spec, a section
                whose first paragraph is not prose -- each raises
                `SectionError` naming the file.

Run: `python -m tools.decisions_index --write`
"""

from __future__ import annotations

import argparse
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ROOT / "docs" / "decisions"
INDEX = ROOT / "docs" / "decisions.md"
PREAMBLE = SECTIONS / "_preamble.md"
ORDER = SECTIONS / "_order.txt"

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6}) (.+?)\s*$")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
# A paragraph that opens with one of these is not a sentence to summarize.
_NOT_PROSE = re.compile(r"^\s*(```|~~~|\||#|[-*+] |\d+[.)] |>)")
# Tokens a period ends without ending the sentence.
_ABBREVIATIONS = ("e.g", "i.e", "vs", "cf", "etc")


class SectionError(AssertionError):
    """A section file or the order registry is malformed. `AssertionError` so
    the pins redden uniformly, as `tools.glossary_index.EntryError` does."""


@dataclass(frozen=True, slots=True)
class Section:
    slug: str
    path: Path
    title: str
    subheadings: tuple[str, ...]
    summary: str
    text: str


def github_anchor(title: str) -> str:
    """The fragment GitHub's renderer gives a heading."""
    return re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")


def _headings(text: str) -> list[tuple[int, str]]:
    """(depth, title) of every heading outside a code fence."""
    out: list[tuple[int, str]] = []
    fenced = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        found = _HEADING.match(line)
        if found and not fenced:
            out.append((len(found.group(1)), found.group(2)))
    return out


def _first_sentence(paragraph: str) -> str:
    """The paragraph up to the first sentence end outside a code span."""
    in_code = False
    for at, char in enumerate(paragraph):
        if char == "`":
            in_code = not in_code
            continue
        if in_code or char not in ".?!":
            continue
        end = at + 1
        while end < len(paragraph) and paragraph[end] in "*_)\"'":
            end += 1
        if end < len(paragraph) and not paragraph[end].isspace():
            continue
        if paragraph[:at].endswith(_ABBREVIATIONS):
            continue
        return paragraph[:end]
    return paragraph


def rebase_link(target: str, slug: str) -> str:
    """A link target written in `docs/decisions/<slug>.md`, rewritten for a
    file in `docs/` -- the index quotes a section's first sentence, and its
    links must keep naming the same files."""
    if re.match(r"^[a-z]+:", target) or target.startswith("/"):
        return target
    path, hash_, fragment = target.partition("#")
    if not path:
        return f"decisions/{slug}.md#{fragment}"
    trailing = "/" if path.endswith("/") else ""
    return posixpath.normpath(posixpath.join("decisions", path)) + trailing + hash_ + fragment


def parse_section(path: Path) -> Section:
    text = path.read_text()
    lines = text.splitlines()
    opening = _HEADING.match(lines[0]) if lines else None
    if opening is None or len(opening.group(1)) != 2:
        raise SectionError(f"{path.name}: the first line is not the section's `## ` heading")
    title = opening.group(2)
    if "[" in title or "]" in title:
        raise SectionError(f"{path.name}: a title holding a bracket breaks its index link")
    headings = _headings(text)
    tops = [h for depth, h in headings if depth <= 2]
    if tops != [title]:
        raise SectionError(
            f"{path.name}: holds `#`/`##` headings {tops[1:]} besides its own -- "
            f"one decision per file; split it into its own section file"
        )
    paragraph: list[str] = []
    for line in lines[1:]:
        if not line.strip():
            if paragraph:
                break
            continue
        paragraph.append(line.strip())
    if not paragraph or _NOT_PROSE.match(paragraph[0]):
        raise SectionError(
            f"{path.name}: the section's first paragraph is not prose, so the "
            f"index has no sentence to summarize it with -- open the section "
            f"with a sentence stating the decision"
        )
    summary = _LINK.sub(
        lambda m: f"]({rebase_link(m.group(1), path.stem)})",
        _first_sentence(" ".join(paragraph)),
    )
    return Section(
        slug=path.stem,
        path=path,
        title=title,
        subheadings=tuple(h for depth, h in headings if depth > 2),
        summary=summary,
        text=text,
    )


def section_paths() -> list[Path]:
    """Every section file, in reading order -- the one owner of that list."""
    listed = ORDER.read_text().split()
    on_disk = {p.stem for p in SECTIONS.glob("*.md") if not p.name.startswith("_")}
    twice = sorted({s for s in listed if listed.count(s) > 1})
    if twice:
        raise SectionError(f"_order.txt lists {twice} more than once")
    if missing := sorted(set(listed) - on_disk):
        raise SectionError(f"_order.txt lists {missing}, which have no file in {SECTIONS}")
    if unlisted := sorted(on_disk - set(listed)):
        raise SectionError(
            f"{unlisted} sit in {SECTIONS} but not in _order.txt -- add each "
            f"slug at the place the decision belongs in reading order"
        )
    if not listed:
        raise SectionError(f"no sections in {SECTIONS} -- an empty index covers nothing")
    return [SECTIONS / f"{slug}.md" for slug in listed]


def load() -> list[Section]:
    sections = [parse_section(p) for p in section_paths()]
    home: dict[str, str] = {}
    for section in sections:
        for title in (section.title, *section.subheadings):
            if title in home:
                raise SectionError(
                    f"the heading {title!r} is in both {home[title]}.md and "
                    f"{section.slug}.md -- a cited title must name one place"
                )
            home[title] = section.slug
    return sections


def spec_text() -> str:
    """The whole spec as one text, sections in reading order -- for a reader
    that searches the spec for a passage rather than citing one file."""
    return "\n".join(section.text for section in load())


def render(sections: list[Section]) -> str:
    out = [PREAMBLE.read_text().rstrip(), ""]
    for section in sections:
        link = f"decisions/{section.slug}.md"
        out.append(f"- [{section.title}]({link}) -- {section.summary}")
        for sub in section.subheadings:
            out.append(f"  - [{sub}]({link}#{github_anchor(sub)})")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    sections = load()
    text = render(sections)
    if args.write:
        INDEX.write_text(text)
        print(f"wrote {INDEX.relative_to(ROOT)} ({len(sections)} sections)")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
