"""Attribution: which file a refusal standing in family-library text is told in.

A game's text reaches a family library's text, and a check that follows it
can refuse library text for a cause the game's text supplies. Who is told is
decided here, once, for every check (decisions.md "Family libraries"): a
library definition is sound when some game meets it, so a failure only some
games produce is the game's, and a fault in the library's own text stays the
library's.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      every diagnostic a pass collects carries the span of the text it
              refuses; a check that follows a crossing out of the game's text
              into library text attaches the crossing (`Route`) to the
              refusal it raises there; a check that knows the sentence a
              game's author should read for a refusal of library text supplies
              it (`for_game`); every spliced definition carries its
              `n.LibraryOrigin`.
Establishes:  the witnesses of a library are the corpus and family games that
              `uses` it (`witness_sources`, glob-derived).
"""

from __future__ import annotations

import re
from pathlib import Path

# Every kind of crossing a walk reports, by the game text it left by: a Trick
# Order row's call, a Hosted Poll's reach, a `run` of a library procedure (and
# a read its own arguments make), a decision position's call, and a rule's
# activation.
CROSSING_KINDS: frozenset[str] = frozenset(
    {"row", "hosted_poll", "run", "run_argument", "call", "activation"}
)

_ROOT = Path(__file__).resolve().parent.parent
# Where a library's witnesses live: the corpus, and the family-member
# directories under experiments/.
_WITNESS_GLOBS: tuple[tuple[str, str], ...] = (
    ("docs/games", "*.cardlang"),
    ("experiments", "**/*.cardlang"),
)


def witness_sources(library: str) -> tuple[tuple[str, str], ...]:
    """Every game file that `uses` `library`, as (repo-relative path, text),
    in path order: the games whose verdicts can prove the library sound."""
    line = re.compile(rf"^\s*uses\s+{re.escape(library)}\s*$", re.M)
    found: list[tuple[str, str]] = []
    for base, pattern in _WITNESS_GLOBS:
        for path in sorted((_ROOT / base).glob(pattern)):
            text = path.read_text()
            if line.search(text):
                found.append((path.relative_to(_ROOT).as_posix(), text))
    return tuple(found)
