"""The decisions spec is one file per decision, and its index is what they generate.

property:        every section file under `docs/decisions/` is one whole
                 `##` decision, read in one place in `_order.txt`, reachable
                 under a basename no other doc shares, and listed in
                 `docs/decisions.md` exactly as `tools.decisions_index.render`
                 prints it -- title, first sentence, and every sub-heading.
domain:          every `.md` under `docs/decisions/` not named with a leading
                 `_` (the index's own parts, `_preamble.md` and
                 `_order.txt`), crossed with the section-file properties
                 below; and the order registry, both directions.
registry:        section axis: the directory glob, `_section_files`, never
                 `_order.txt` -- the order is the thing the glob holds to
                 account. Citation resolution through the index:
                 `tests/test_doc_references.py::test_an_index_reaches_every_file_in_its_directory`.
held by:         Derived and Pinned -- the section set is the directory and
                 the index is a function of it; a pin, not a type, because
                 the files are prose a type checker never reads.
does not prove:  that a section's first sentence summarizes it well, or that
                 a decision sits in the section that bounds it. Both are the
                 author's judgment; the generator reads, it does not judge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import decisions_index
from tools.decisions_index import (
    INDEX,
    ROOT,
    SECTIONS,
    SectionError,
    load,
    parse_section,
    rebase_link,
    render,
    section_paths,
)


def _section_files() -> list[Path]:
    files = sorted(p for p in SECTIONS.glob("*.md") if not p.name.startswith("_"))
    assert files, f"no section file in {SECTIONS} -- every pin below would be vacuous"
    return files


@pytest.mark.parametrize("path", _section_files(), ids=lambda p: p.stem)
def test_every_section_file_is_one_whole_decision(path: Path) -> None:
    section = parse_section(path)
    assert section.title
    assert section.summary


@pytest.mark.parametrize("path", _section_files(), ids=lambda p: p.stem)
def test_every_section_file_is_read_once_in_order(path: Path) -> None:
    assert section_paths().count(path) == 1


@pytest.mark.parametrize("path", _section_files(), ids=lambda p: p.stem)
def test_no_other_doc_shares_a_section_files_basename(path: Path) -> None:
    """A citation may name a doc by basename, and two files sharing one make
    it unresolvable -- `tests/test_doc_references.py` `_resolve_doc` refuses
    to guess. So a section file's name is its own across `docs/`.

    red under: copy `docs/decisions/zone-capacity.md` to
    `docs/design-notes/zone-capacity.md`.
    """
    twins = [p for p in (ROOT / "docs").rglob(path.name) if p != path]
    assert not twins, f"{path.name} is also {twins}"


def test_the_index_is_exactly_what_the_sections_generate() -> None:
    """red under: edit a section's first sentence without regenerating."""
    assert INDEX.read_text() == render(load()), (
        "docs/decisions.md is stale -- run `python -m tools.decisions_index --write`"
    )


def test_every_heading_of_the_spec_is_listed_in_the_index() -> None:
    text = render(load())
    for section in load():
        for title in (section.title, *section.subheadings):
            assert f"[{title}](decisions/{section.slug}.md" in text, title


# --- misuse probes: each malformed layout is refused naming the file -------


def _plant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
           files: dict[str, str], order: list[str]) -> None:
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    (tmp_path / "_order.txt").write_text("\n".join(order) + "\n")
    (tmp_path / "_preamble.md").write_text("# Spec\n")
    monkeypatch.setattr(decisions_index, "SECTIONS", tmp_path)
    monkeypatch.setattr(decisions_index, "ORDER", tmp_path / "_order.txt")
    monkeypatch.setattr(decisions_index, "PREAMBLE", tmp_path / "_preamble.md")


_ONE = "## One\n\nThe first decision. More.\n"
_TWO = "## Two\n\nThe second decision.\n"


@pytest.mark.parametrize(
    ("files", "order", "message"),
    [
        ({"one.md": _ONE, "two.md": _TWO}, ["one"], "not in _order.txt"),
        ({"one.md": _ONE}, ["one", "two"], "have no file"),
        ({"one.md": _ONE}, ["one", "one"], "more than once"),
        ({}, [], "an empty index covers nothing"),
    ],
    ids=["unlisted-file", "listed-without-file", "listed-twice", "empty"],
)
def test_the_order_registry_holds_the_directory_both_ways(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str], order: list[str], message: str,
) -> None:
    _plant(tmp_path, monkeypatch, files, order)
    with pytest.raises(SectionError, match=message):
        load()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("Intro.\n\n## One\n\nBody.\n", "first line is not"),
        ("### One\n\nBody.\n", "first line is not"),
        ("## One\n\nBody.\n\n## Two\n\nMore.\n", "one decision per file"),
        ("## One\n\nBody.\n\n# Top\n", "one decision per file"),
        ("## One\n\n- a list first\n", "not prose"),
        ("## One\n\n```text\nx\n```\n", "not prose"),
        ("## One\n", "not prose"),
        ("## One [x]\n\nBody.\n", "bracket"),
    ],
    ids=["text-above-heading", "h3-opening", "second-h2", "h1-inside",
         "list-first", "fence-first", "no-body", "bracket-title"],
)
def test_a_malformed_section_file_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, message: str,
) -> None:
    _plant(tmp_path, monkeypatch, {"one.md": text}, ["one"])
    with pytest.raises(SectionError, match=message):
        load()


def test_a_heading_inside_a_code_fence_is_not_a_heading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plant(tmp_path, monkeypatch,
           {"one.md": "## One\n\nBody.\n\n```text\n## not a heading\n```\n"}, ["one"])
    assert load()[0].subheadings == ()


def test_a_heading_in_two_section_files_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = {"one.md": _ONE + "\n### Shared\n\nx.\n", "two.md": _TWO + "\n### Shared\n\ny.\n"}
    _plant(tmp_path, monkeypatch, files, ["one", "two"])
    with pytest.raises(SectionError, match="'Shared' is in both one.md and two.md"):
        load()


@pytest.mark.parametrize(
    ("paragraph", "sentence"),
    [
        ("One. Two.", "One."),
        ("Ends with a colon:", "Ends with a colon:"),
        ("Uses `a.b` inside code. Then more.", "Uses `a.b` inside code."),
        ("Abbreviates, e.g. this, and ends. Next.", "Abbreviates, e.g. this, and ends."),
        ("**A bold ruling.** Its gloss.", "**A bold ruling.**"),
        ("A version 1.2 number. Next.", "A version 1.2 number."),
    ],
)
def test_the_summary_is_the_first_sentence(paragraph: str, sentence: str) -> None:
    assert decisions_index._first_sentence(paragraph) == sentence


@pytest.mark.parametrize(
    ("target", "rebased"),
    [
        ("../library.md", "library.md"),
        ("../open-questions/", "open-questions/"),
        ("../games/hex.md#rules", "games/hex.md#rules"),
        ("mutation-semantics.md#mutation-semantics",
         "decisions/mutation-semantics.md#mutation-semantics"),
        ("#observation-events", "decisions/here.md#observation-events"),
        ("https://www.pagat.com/", "https://www.pagat.com/"),
    ],
)
def test_a_summary_link_names_the_same_file_from_the_index(target: str, rebased: str) -> None:
    assert rebase_link(target, "here") == rebased
