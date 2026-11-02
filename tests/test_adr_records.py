"""Every ruling record is well-formed, and every `ADR-NNNN` written anywhere names one that exists.

A record under `docs/adr/` is the dated artifact an operator ruling gets
(`docs/adr/README.md`). The shape is what makes the folder an index rather
than a pile: a reader who sees only the file names knows the order the
rulings were recorded and what each decided, and a citation of a record from
the law resolves to it the way a quoted section title resolves in
`tests/test_doc_references.py`.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        every record file is numbered contiguously from one, carries
                 the five header lines and the four body sections in order,
                 declares a Status from the closed set, dates itself, and
                 names an existing successor when superseded; and every
                 `ADR-NNNN` mention in the repo's prose resolves to a record
                 that exists.
domain:          every `.md` under `docs/adr/` other than `README.md`; and
                 for the mentions, `CLAUDE.md`, every `.md` under `docs/` and
                 `.claude/skills/`, every `.py` under `cardlang/`, `tests/`
                 and `tools/`, and every `.cardlang` in the repo -- the same
                 walk the section-citation check takes, plus `tools/`. This
                 module is outside the mention walk, since its probes spell
                 the mentions they refuse. `docs/research/` is outside too:
                 dated records of what was true when written.
registry:        the record directory itself, walked at test time; the status
                 vocabulary is `_STATUS`, read by the shape check and by the
                 probes alike.
held by:         Derived and Pinned -- the record set and the mention set are
                 both read from the tree when the test runs, so a record
                 added, renumbered or cited is in-domain the day it exists.
                 Whether a record states its ruling TRULY is review-enforced
                 prose: `docs/adr/**` is Merge Lane B, and the operator reads
                 the record before it stands. No scrape can hold that fact.
does not prove:  that every ruling HAS a record -- a ruling made on an issue
                 and never written up is invisible here, and the direction
                 review's read is its only catch; that a record's Governs
                 line names the right section -- a quoted title resolves (the
                 sibling check), but nothing reads whether that section
                 states the ruling; that two records do not record one
                 ruling twice.

red under: rename the second record so its number skips one (the contiguity
    pin reddens); write a Status the vocabulary lacks in any record; cite a
    record number no file carries from any doc.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS = REPO_ROOT / "docs" / "adr"

_FILE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
_TITLE = re.compile(r"^# ADR-(\d{4}): (.+)$")
_HEADER = ("Status", "Date", "Ruled by", "Record", "Governs")
_HEADER_LINE = re.compile(r"^- \*\*([A-Za-z ]+):\*\* (.+)$")
_SECTIONS = ("## Context", "## Decision", "## Alternatives", "## Consequences")
_STATUS = (re.compile(r"^Accepted$"), re.compile(r"^Superseded by ADR-(\d{4})$"))
_MENTION = re.compile(r"\bADR-(\d{4})\b")
_EXCLUDED = ("docs/research/", "tests/test_adr_records.py")


def _record_files() -> list[Path]:
    return sorted(p for p in RECORDS.glob("*.md") if p.name != "README.md")


def _numbers() -> set[int]:
    out: set[int] = set()
    for path in _record_files():
        found = _FILE.match(path.name)
        if found:
            out.add(int(found.group(1)))
    return out


def _problems(text: str, number: int, known: set[int]) -> list[str]:
    """Everything wrong with one record's shape, as sentences; empty when none."""
    lines = text.splitlines()
    problems: list[str] = []
    title = _TITLE.match(lines[0]) if lines else None
    if title is None:
        problems.append("the first line is not `# ADR-NNNN: <title>`")
    elif int(title.group(1)) != number:
        problems.append(
            f"the title says ADR-{title.group(1)} but the file is numbered {number:04d}"
        )
    header: dict[str, str] = {}
    for line in lines[1:12]:
        found = _HEADER_LINE.match(line)
        if found:
            header[found.group(1)] = found.group(2)
    for field in _HEADER:
        if field not in header:
            problems.append(f"the header has no `- **{field}:**` line")
    if "Status" in header:
        status = header["Status"]
        matches = [p.match(status) for p in _STATUS]
        if not any(matches):
            problems.append(f"Status {status!r} is not Accepted or Superseded by ADR-NNNN")
        else:
            superseded = matches[1]
            if superseded is not None:
                successor = int(superseded.group(1))
                if successor == number or successor not in known:
                    problems.append(
                        f"Status names successor ADR-{successor:04d}, which "
                        f"{'is this record' if successor == number else 'does not exist'}"
                    )
    if "Date" in header:
        try:
            date.fromisoformat(header["Date"])
        except ValueError:
            problems.append(f"Date {header['Date']!r} is not an ISO date")
    positions = [
        next((i for i, line in enumerate(lines) if line == section), None)
        for section in _SECTIONS
    ]
    for section, at in zip(_SECTIONS, positions):
        if at is None:
            problems.append(f"no `{section}` section")
        elif lines.count(section) > 1:
            problems.append(f"`{section}` appears more than once")
    present = [at for at in positions if at is not None]
    if present != sorted(present):
        problems.append("the sections are out of order")
    return problems


def _in_domain() -> list[Path]:
    paths: list[Path] = [REPO_ROOT / "CLAUDE.md"]
    for pattern in (
        "cardlang/**/*.py", "tests/**/*.py", "tools/**/*.py", "docs/**/*.md",
        ".claude/skills/**/*.md", "**/*.cardlang",
    ):
        paths.extend(REPO_ROOT.glob(pattern))
    return sorted(
        p for p in paths
        if p.is_file()
        and not any(d in p.relative_to(REPO_ROOT).as_posix() for d in _EXCLUDED)
    )


def test_records_are_numbered_contiguously_from_one() -> None:
    files = _record_files()
    assert files, "no record under docs/adr/ -- this check would be vacuous"
    misnamed = [p.name for p in files if not _FILE.match(p.name)]
    assert not misnamed, f"record files not named NNNN-<slug>.md: {misnamed}"
    numbers = sorted(int(_FILE.match(p.name).group(1)) for p in files)  # type: ignore[union-attr]
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"record numbers are not 1..{len(numbers)} without gaps or repeats: {numbers}"
    )


def test_every_record_carries_the_shape() -> None:
    known = _numbers()
    failures: list[str] = []
    for path in _record_files():
        found = _FILE.match(path.name)
        if found is None:
            continue
        for problem in _problems(path.read_text(), int(found.group(1)), known):
            failures.append(f"docs/adr/{path.name}: {problem}")
    assert not failures, "\n".join(failures)


def test_every_adr_mention_names_a_record_that_exists() -> None:
    known = _numbers()
    assert known, "no record numbers -- the resolution check would be vacuous"
    unresolved: list[str] = []
    scanned = 0
    for path in _in_domain():
        text = path.read_text()
        for found in _MENTION.finditer(text):
            scanned += 1
            number = int(found.group(1))
            if number not in known:
                line = text.count("\n", 0, found.start()) + 1
                unresolved.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: "
                    f"ADR-{number:04d} names no record under docs/adr/"
                )
    assert scanned, "no ADR mention was scanned at all -- this check validated nothing"
    assert not unresolved, "\n".join(unresolved)


# --- probes: the shape check itself cannot go vacuously green ---------------


def _first_record() -> tuple[str, int]:
    path = _record_files()[0]
    found = _FILE.match(path.name)
    assert found is not None
    return path.read_text(), int(found.group(1))


def test_a_well_formed_record_has_no_problems() -> None:
    text, number = _first_record()
    assert _problems(text, number, _numbers()) == []


def test_a_foreign_status_is_a_problem() -> None:
    text, number = _first_record()
    broken = re.sub(r"\*\*Status:\*\* .+", "**Status:** Draft", text, count=1)
    assert any("Status" in p for p in _problems(broken, number, _numbers()))


def test_a_successor_that_does_not_exist_is_a_problem() -> None:
    text, number = _first_record()
    missing = max(_numbers()) + 1
    broken = re.sub(
        r"\*\*Status:\*\* .+",
        f"**Status:** Superseded by ADR-{missing:04d}",
        text,
        count=1,
    )
    assert any("does not exist" in p for p in _problems(broken, number, _numbers()))


def test_a_missing_section_and_a_wrong_number_are_problems() -> None:
    text, number = _first_record()
    no_alternatives = text.replace("## Alternatives", "## Options", 1)
    assert any("Alternatives" in p for p in _problems(no_alternatives, number, _numbers()))
    assert any("numbered" in p for p in _problems(text, number + 1, _numbers()))


def test_the_mention_pattern_reads_a_citation_and_not_the_placeholder() -> None:
    assert _MENTION.search("ruled, see ADR-0001 and ADR-0016.") is not None
    assert _MENTION.search("the shape is ADR-NNNN") is None
