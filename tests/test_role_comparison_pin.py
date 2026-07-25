"""A role id is compared against the registry, or the comparison says why not.

The domain table (`cardlang/domains.py`) exists because the same fact -- what a
`player`/`team`/`suit`/`rank` role means to a consumer -- was re-spelled as
`== "team"` at site after site, and each re-spelling silently defaulted every
OTHER role to player behaviour. The table's own comment records the cleanup:
`zone_key_of` "replaces an `== "team"` re-spelling at five consumer sites
(resolve, typecheck, state, driver, observe), each of which silently defaulted
every non-team role to player keying."

That cleanup fixed the instances and left no guard, so the class regenerated:
three review findings in a row were one shape -- a closed domain consulted by
ad-hoc local logic that silently defaults for the members it does not handle
(PR #92's per-site position hooks, #93's empty team domain read as an unknown
bound, #94's `decl.index == "team"` reading every future role as player-keyed).
Five separate files carry comments narrating past cleanups of this same
anti-pattern; the remedy was practiced correctly exactly once
(`runtime/execute.py`, which pins a hard-coded `player` branch against
`SIMULTANEOUS_ROLES` so widening the registry fails by name).

This module is the missing mechanism. It does not forbid comparing a role id --
some comparisons are intrinsic, and one row of a registry is often the only row
a consumer can implement. It forbids doing so SILENTLY: every comparison outside
the table itself carries a `# role-compare-ok:` marker naming why, and the
honest reasons are few (the fact is intrinsic to the construct; the string is
not a role at all; or the branch is pinned against the registry beside it, so
widening the table fails loudly here).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   every `==`/`!=` comparison in `cardlang/` whose operand is a string
            literal naming a domain-registry role is either inside
            `cardlang/domains.py` (the table itself) or carries a
            `# role-compare-ok: <reason>` marker on one of its lines.
domain:     the `ast.Compare` nodes of every module under `cardlang/`, crossed
            with the registry's role ids. Both axes are DERIVED: the node set by
            walking each module's AST (so a comment mentioning `== "team"` is
            not a hit, and a new module is covered the day it lands), the role
            ids by reading `domains.DOMAINS` (so adding a domain widens what
            this pin watches without editing it).
registry:   `cardlang.domains.DOMAINS` for the role ids; the filesystem glob
            `cardlang/**/*.py` for the module set.
covered:    the scrape below, over every module and every role id.
sampled:    none -- the scrape is exhaustive over its derived domain.
residual:   a role id reached WITHOUT a literal comparison -- held in a variable,
            a dict key, or compared via `in {...}` -- is not flagged. The pin
            catches the shape that actually recurred (the bare literal test); a
            set-membership test against a hand-written role set is the same
            defect wearing different syntax, and is left to review. Recorded in
            roadmap.md.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from cardlang.domains import DOMAINS

_MARKER = "role-compare-ok"
_ROLE_IDS = frozenset(d.id for d in DOMAINS)
_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "cardlang"
# The table itself: it is where a role id is DEFINED, so comparing one there is
# the point, not a re-spelling.
_REGISTRY_MODULE = "domains.py"


def _modules() -> list[pathlib.Path]:
    return sorted(p for p in _PACKAGE.rglob("*.py") if p.name != _REGISTRY_MODULE)


def _unmarked_role_comparisons(path: pathlib.Path) -> list[tuple[int, str]]:
    source = path.read_text()
    lines = source.splitlines()
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare):
            continue
        if not all(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        if not any(
            isinstance(o, ast.Constant)
            and isinstance(o.value, str)
            and o.value in _ROLE_IDS
            for o in operands
        ):
            continue
        end = node.end_lineno or node.lineno
        on_the_comparison = range(node.lineno, min(end, len(lines)) + 1)
        marked = any(_MARKER in lines[ln - 1] for ln in on_the_comparison)
        # A reason worth reading rarely fits on the comparison's own line, so the
        # contiguous comment block immediately above it counts too.
        ln = node.lineno - 1
        while not marked and ln >= 1 and lines[ln - 1].strip().startswith("#"):
            marked = _MARKER in lines[ln - 1]
            ln -= 1
        if not marked:
            found.append((node.lineno, lines[node.lineno - 1].strip()))
    return found


@pytest.mark.parametrize("path", _modules(), ids=lambda p: str(p.name))
def test_role_comparisons_are_marked(path: pathlib.Path) -> None:
    """A bare role-id comparison must say why it is not registry drift.

    red under: delete a `# role-compare-ok:` marker from any comparison the
    sweep annotated (e.g. resolve's team-declaration walls) -- that module's row
    reddens, naming the line."""
    unmarked = _unmarked_role_comparisons(path)
    assert not unmarked, (
        f"{path}: role-id comparison(s) without a '# {_MARKER}: <reason>' marker "
        f"at line(s) {[ln for ln, _ in unmarked]}:\n"
        + "\n".join(f"    {ln}: {src}" for ln, src in unmarked)
        + "\n  Consult the domain table instead, or mark the line with the reason "
          "it is not drift (the fact is intrinsic to the construct; the string is "
          "not a role; or the branch is pinned against the registry beside it)."
    )


def test_the_pin_watches_a_registry_derived_role_set() -> None:
    """The role axis is read from `DOMAINS`, not re-spelled here -- otherwise
    this pin would be the very thing it forbids.

    red under: replace `_ROLE_IDS` with a hand-written literal set and add a
    domain to `DOMAINS`; the sets diverge and this reddens."""
    assert _ROLE_IDS == {d.id for d in DOMAINS}
    assert _ROLE_IDS, "the registry yielded no roles — the derivation is broken"


def test_the_scrape_can_see_an_unmarked_comparison() -> None:
    """The scrape itself is load-bearing, so prove it FIRES rather than trusting
    a green run over the swept tree (a scrape that matched nothing would also be
    green). Feeds it a synthetic module containing one unmarked comparison and
    one marked one, and requires exactly the unmarked line back."""
    probe = (
        "def f(role):\n"
        '    if role == "team":\n'
        "        return 1\n"
        '    if role == "player":  # role-compare-ok: marked inline\n'
        "        return 2\n"
        "    # role-compare-ok: marked by the comment block above\n"
        '    if role == "suit":\n'
        "        return 3\n"
        "    return 0\n"
    )
    tmp = pathlib.Path(__file__).resolve().parent / "_role_pin_probe.py.txt"
    tmp.write_text(probe)
    try:
        found = _unmarked_role_comparisons(tmp)
    finally:
        tmp.unlink()
    assert [ln for ln, _ in found] == [2], found
