"""A completeness ledger carries only the rows its template prints.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        no completeness ledger in the tree heads a line with a row
                 label outside the completeness template -- a retired row
                 (`covered:`, `sampled:`, `residual:`), a class-ledger row
                 (`finding:`, `class:`, `members:`), or any fifth row at the
                 ledger's own row indent -- and one that does is refused
                 here, naming the module and the label. A retired
                 row is a coverage claim wearing a row's name (issue #392's
                 ruling: a wrong `covered:` licenses not testing), so the
                 population that carries none stays at zero by refusal, not
                 by attrition.
domain:          every completeness ledger the referent scrape walks
                 (`_ledger_docstrings`, the one walk both modules read: a
                 docstring or a `#` comment block carrying the signature),
                 crossed with every label in `REFUSED_LABELS` anywhere in
                 the text, and with every label at the row indent inside
                 the ledger region (`refused_rows`). The named-label axis
                 is derived: the labels the class template prints
                 that the completeness template does not, plus the one label
                 no template prints any more (`sampled`), hand-named because
                 a label outside every template is invisible to the row
                 parse by design and only a memory of it can refuse it. A
                 class ledger itself is outside: it lives in a commit
                 message or PR body, never in a docstring, and the walk's
                 signature (`property` + `domain`) does not match it. Prose
                 that merely contains one of the words is outside too: the
                 scan reads a label heading a line, the same shape the row
                 parse reads, so "see residual" in a sentence is not a row.
registry:        the completeness rows -- `COMPLETENESS_ROWS`; the class
                 rows -- `CLASS_ROWS`; both scraped from their templates in
                 tests/test_ledger_referents.py. The label shape --
                 `_ROW_LABEL`, the same definition the row parse reads. The
                 population -- `_ledger_docstrings`.
does not prove:  a green here says nothing about what the surviving rows
                 SAY. A `does not prove:` row holding a coverage claim, or
                 deferred work, or a history, passes this scan unread; the
                 row's name is what stands there, and the reviewer at the
                 `surface-totality-audit` skill's Step 3 is the mechanism.
                 And a label misspelt past `_ROW_LABEL`'s shape (`covered :`
                 with a space, `Covered:` capitalised) is not a row to the
                 parse and not a row to this scan, in the same breath.
"""

from __future__ import annotations

import re

import pytest

from tests.test_ledger_referents import (
    _RED_UNDER,
    _ROW_LABEL,
    CLASS_ROWS,
    COMPLETENESS_ROWS,
    _ledger_docstrings,
)

REFUSED_LABELS: frozenset[str] = (
    frozenset(CLASS_ROWS) - frozenset(COMPLETENESS_ROWS)
) | frozenset({"sampled"})

_HEAD = re.compile(rf"^[ \t]*{_ROW_LABEL}:", re.MULTILINE)
_ROW_HEAD = re.compile(rf"^([ \t]*){_ROW_LABEL}:")


def refused_rows(doc: str) -> list[str]:
    """Every refused label heading a line of `doc`, in order, plus every
    FIFTH row: a label-shaped line at the ledger's own row indent, inside
    the ledger region, that is not one of the template's rows. The region
    runs from the `property:` line to the blank line after the last
    template row; a label-shaped line indented deeper is a sentence that
    happens to wrap onto `word:` and stays prose, and a paragraph after
    the blank line is outside the ledger."""
    found = [m.group(1) for m in _HEAD.finditer(doc) if m.group(1) in REFUSED_LABELS]
    lines = doc.splitlines()
    heads = [(i, _ROW_HEAD.match(l)) for i, l in enumerate(lines)]
    template = [(i, m) for i, m in heads if m and m.group(2) in COMPLETENESS_ROWS]
    if not template:
        return found
    indent, start, end = template[0][1].group(1), template[0][0], template[-1][0]
    while end + 1 < len(lines) and lines[end + 1].strip() and not _RED_UNDER.match(lines[end + 1]):
        end += 1
    for i in range(start, end + 1):
        m = _ROW_HEAD.match(lines[i])
        if m and m.group(1) == indent and m.group(2) not in COMPLETENESS_ROWS and not _RED_UNDER.match(lines[i]):
            if m.group(2) not in found:
                found.append(m.group(2))
    return found


def test_the_refused_set_is_derived_and_non_empty() -> None:
    assert {"covered", "residual", "sampled"} <= REFUSED_LABELS
    assert not (REFUSED_LABELS & frozenset(COMPLETENESS_ROWS))


_FOUR_ROWS = (
    "property:   p\n"
    "domain:     d\n"
    "registry:   r\n"
    "does not prove:  a green here does not establish x; the words\n"
    "            covered, sampled: and residual mid-line are prose.\n"
)


@pytest.mark.parametrize("label", sorted(REFUSED_LABELS))
def test_a_refused_label_heading_a_line_is_seen(label: str) -> None:
    assert refused_rows(_FOUR_ROWS + f"{label}:    anything\n") == [label]


def test_the_four_rows_alone_are_clean() -> None:
    assert refused_rows(_FOUR_ROWS) == []


def test_a_fifth_row_at_the_row_indent_is_refused() -> None:
    assert refused_rows(_FOUR_ROWS + "note:   a fifth row\n") == ["note"]
    assert refused_rows(_FOUR_ROWS.replace("registry:   r\n", "registry:   r\nnaming:     n\n")) == ["naming"]


def test_a_wrapped_sentence_and_a_trailing_paragraph_are_not_rows() -> None:
    deeper = _FOUR_ROWS.replace("domain:     d\n", "domain:     d, and\n            by construction: this is prose\n")
    assert refused_rows(deeper) == []
    after = _FOUR_ROWS + "\nnote: a paragraph after the ledger is outside it\n"
    assert refused_rows(after) == []
    red_under = _FOUR_ROWS + "red under: a dated block ends the ledger\n"
    assert refused_rows(red_under) == []


def test_every_completeness_ledger_carries_only_template_rows() -> None:
    bad = [
        f"{name}: {', '.join(labels)}"
        for name, doc in _ledger_docstrings()
        if (labels := refused_rows(doc))
    ]
    assert not bad, (
        f"{len(bad)} completeness ledger(s) head a line with a retired or "
        "class-ledger row label; route the row per decisions.md "
        "\"Closed-domain completeness\" (issue #392):\n  " + "\n  ".join(bad)
    )
