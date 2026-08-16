"""Every statement of the surface-totality audit's trigger says the same thing.

property:   the sentence naming WHAT FIRES the completeness gate is spelled
            identically wherever it is stated. It is law in CLAUDE.md and
            restated in the skills that implement it, and the skills are what
            an agent actually reads before deciding whether the gate applies.
domain:     every tracked file stating the trigger -- found by its tail phrase
            rather than by a hand-written file list, so a fourth copy joins the
            pin the day it is written.
registry:   `_TAIL` locates the sentence; `git ls-files` bounds the walk. There
            is no list of copies anywhere in this module.
covered:    `test_every_statement_of_the_trigger_agrees` over the derived set,
            which also asserts it found more than one copy -- a pin over a
            single statement compares nothing and would pass forever.
sampled:    none.
residual:   Dated snapshots under `docs/plans/` and `docs/superpowers/` are
            excluded: they record what the trigger said when they were
            written, and rule 1 (spec, not history) keeps them frozen. Also
            out of scope: whether the trigger is RIGHT. This pin holds the
            copies together, not the doctrine to any standard.
            One file carries the tail phrase without stating the trigger --
            `decisions.md` uses "a closed-domain mechanism" in the class-ledger
            rule, a different sentence -- and is correctly not a copy. That is
            why the pattern anchors on "adds or extends" rather than on the
            tail alone: the tail names the CATEGORY, the opening names the
            TRIGGER, and only the second is what these files must agree on.

Why this exists. On PR #332 two vocabulary passes hit different copies of this
one sentence: CLAUDE.md ended up firing the gate for "a kernel table" while
three skills fired it for "a native registry". Neither is right alone -- the
audit fires for both -- so for a while the law and its implementation
disagreed about WHEN the repo's completeness gate applies, silently, with
every check green. That is the accepted-but-ignored class reaching the
machinery meant to catch it.

red under: change any one copy of the trigger sentence -- drop "or kernel
    table" from CLAUDE.md, or write "checker guard" for "checker Owner Guard"
    in `.claude/skills/surface-totality-audit/SKILL.md`.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The trigger's tail. Locating the sentence by its own words is what makes the
# copy set DERIVED: a new restatement is found because it says this, not
# because someone remembered to add a path here.
_TAIL = "closed-domain mechanism"
_SENTENCE = re.compile(r"adds or extends[^.]*?" + re.escape(_TAIL))

# Frozen records, excluded by rule 1 (spec, not history): they say what the
# trigger said when they were written and must not be edited to match today.
_SNAPSHOTS = ("docs/plans/", "docs/superpowers/")


def _normalize(text: str) -> str:
    """Collapse whitespace runs. The copies wrap at different widths -- one is
    a YAML `description:` on a single long line, another is prose wrapped to
    the file's column -- and a line break is formatting, not a difference in
    what the trigger SAYS. Comparing raw text instead makes this pin fail on
    a reflow, which is the line-wrap blindness that let the divergence this
    module exists for survive three passes of a line-based sweep."""
    return " ".join(text.split())


def _statements() -> dict[str, str]:
    """Every tracked file's statement of the trigger, keyed by repo path."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    names = [n for n in listing.split("\0") if n and not n.startswith(_SNAPSHOTS)]
    assert names, "the file walk found nothing -- this pin would compare nothing"
    out: dict[str, str] = {}
    for name in names:
        for m in _SENTENCE.finditer((ROOT / name).read_text()):
            out.setdefault(name, _normalize(m.group(0)))
    return out


def test_every_statement_of_the_trigger_agrees() -> None:
    """red under: see the module docstring -- edit any one copy."""
    found = _statements()
    assert len(found) > 1, (
        f"found {len(found)} statement(s) of the audit trigger: {sorted(found)}. "
        "A pin over fewer than two copies compares nothing and would pass "
        "forever -- if the trigger genuinely moved to one home, delete this "
        "module rather than leaving it green over nothing."
    )
    spellings = {text: sorted(p for p, t in found.items() if t == text)
                 for text in set(found.values())}
    assert len(spellings) == 1, (
        "the audit trigger is spelled differently in different places, so the "
        "law and the skills that implement it disagree about when the "
        "completeness gate fires:\n"
        + "\n".join(f"  {paths}\n    {text!r}" for text, paths in sorted(spellings.items()))
    )


def test_the_trigger_names_both_registry_classes() -> None:
    """The specific content that drifted, pinned by name. The gate fires for
    the callable native registries AND for the kernel tables; a sweep that
    replaces one word with the other silently narrows it.

    red under: drop "or kernel table" (or "a native registry") from the
        trigger in CLAUDE.md.
    """
    text = next(iter(_statements().values()))
    for phrase in ("grammar surface", "Owner Guard", "diagnostic",
                   "native registry", "kernel table", "closed-domain mechanism"):
        assert phrase in text, (
            f"the audit trigger no longer names {phrase!r}: {text!r}"
        )
