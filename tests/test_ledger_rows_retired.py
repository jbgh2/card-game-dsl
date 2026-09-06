"""A completeness ledger carries only the rows its template prints.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        no completeness ledger in the tree heads a line with a row
                 label outside the completeness template -- a retired row
                 (`covered:`, `sampled:`, `residual:`) or a class-ledger row
                 (`finding:`, `class:`, `members:`) -- and one that does is
                 refused here, naming the module and the label. A retired
                 row is a coverage claim wearing a row's name (issue #392's
                 ruling: a wrong `covered:` licenses not testing), so the
                 population that carries none stays at zero by refusal, not
                 by attrition.
domain:          every completeness ledger the referent scrape walks
                 (`_ledger_docstrings`, the one walk both modules read: a
                 docstring or a `#` comment block carrying the signature),
                 crossed with every label in `REFUSED_LABELS`. The
                 label axis is derived: the labels the class template prints
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
    CLASS_ROWS,
    COMPLETENESS_ROWS,
    _ROW_LABEL,
    _ledger_docstrings,
)

REFUSED_LABELS: frozenset[str] = (
    frozenset(CLASS_ROWS) - frozenset(COMPLETENESS_ROWS)
) | frozenset({"sampled"})

_HEAD = re.compile(rf"^[ \t]*{_ROW_LABEL}:", re.MULTILINE)


def refused_rows(doc: str) -> list[str]:
    """Every refused label heading a line of `doc`, in order."""
    return [m.group(1) for m in _HEAD.finditer(doc) if m.group(1) in REFUSED_LABELS]


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
