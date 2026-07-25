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
property:   every construct in `cardlang/` that BRANCHES on a role-id string
            literal is either inside `cardlang/domains.py` (the table itself) or
            carries a `# role-compare-ok: <reason>` marker. The marker is read
            from the token stream and must carry a nonempty reason, so neither a
            bare marker nor the text inside a string literal licenses anything.
domain:     the branching POSITION, not one spelling of it (`_dispatch_nodes`):
            a role literal anywhere inside a comparison's operands under ANY
            operator -- equality, inequality, membership, and at any depth, so a
            role inside a container literal counts -- and a role literal in a
            `match` pattern, which is not a `Compare` at all and is this repo's
            house dispatch style. Crossed with every module under `cardlang/`.
            All three axes are DERIVED: the node set by walking each module's
            AST (so a comment mentioning `== "team"` is not a hit, and a new
            module is covered the day it lands), the role ids from
            `domains.DOMAINS` (so adding a domain widens the pin without editing
            it), the module set from the filesystem glob.
registry:   `cardlang.domains.DOMAINS` for the role ids; `cardlang/**/*.py` for
            the modules; `_dispatch_nodes` for the position axis.
covered:    the scrape below, over every module, every role id, and every
            branching shape -- plus `test_the_scrape_can_see_an_unmarked_
            comparison`, which feeds it all seven shapes (plain, mixed chain,
            bare marker, marker-in-a-string, membership, container operand,
            match pattern) and requires exactly the unmarked lines back.
sampled:    none -- the scrape is exhaustive over its derived domain.
residual:   a role literal in a DATA position -- a key in a mapping table, a
            keyword argument, an axis name -- is not flagged, because it selects
            nothing: it is the value being stored, not a branch on which value
            arrived. Measured, not assumed: of the role literals outside
            domains.py, 14 sit in branching positions (all marked or in the
            table) and 54 in data positions, the bulk of them in
            `runtime/values.py`'s component-set tables. The boundary is a real
            residual rather than a proof -- a mapping table CAN encode a
            per-role decision, and one that grows a wrong row would not be
            caught here. Recorded in roadmap.md; a role id reached through a
            VARIABLE rather than a literal is out of reach of any scrape and is
            recorded there too.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import tokenize

import pytest

from cardlang.domains import DOMAINS

_MARKER = "role-compare-ok"
# The marker is only a marker as a COMMENT carrying a NONEMPTY reason. A bare
# `# role-compare-ok` would let a placeholder stand in for the reasoning the
# marker exists to force, which is the same "a check that cannot fail" defect
# this module guards against one level down.
_MARKER_RE = re.compile(rf"{_MARKER}\s*:\s*\S")
_ROLE_IDS = frozenset(d.id for d in DOMAINS)
_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "cardlang"
# The table itself: it is where a role id is DEFINED, so comparing one there is
# the point, not a re-spelling.
_REGISTRY_MODULE = "domains.py"


def _modules() -> list[pathlib.Path]:
    return sorted(p for p in _PACKAGE.rglob("*.py") if p.name != _REGISTRY_MODULE)


def _marker_lines(source: str) -> set[int]:
    """The line numbers carrying a well-formed marker.

    Read from the TOKEN stream, not by substring, so the marker counts only as a
    real comment: the same text inside a string literal is not a licence, and the
    reason after the colon must be nonempty."""
    lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and _MARKER_RE.search(tok.string):
            lines.add(tok.start[0])
    return lines


def _is_role_literal(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in _ROLE_IDS
    )


def _dispatch_nodes(tree: ast.AST) -> list[ast.expr | ast.pattern]:
    """Every construct that BRANCHES on a role id, in source order.

    The domain is the position, not one syntactic spelling of it, because
    enumerating spellings is the same deny-list this module exists to forbid --
    and it silently missed four shapes before review caught it. A role id
    branches when it appears anywhere inside:

    - a COMPARISON, under any operator and at any depth in an operand, so
      `role == "team"`, `role != "team"`, `role in ("team", "player")` and
      `ZONE_INDEX_ROLES == {"player", "team"}` are all one case. Depth matters:
      a role inside a container literal is doing the same work as a bare one,
      and looking only at direct operands is how the set-literal form escaped.
    - a MATCH PATTERN (`case "team":`), which is not a `Compare` at all, and is
      this repo's house dispatch style -- so restricting to comparisons would
      have left the most idiomatic spelling of the defect unwatched.

    A role literal OUTSIDE any of these is data, not a branch -- a key in a
    mapping table, a keyword argument, an axis name -- and is a recorded
    residual rather than a silent omission (see the ledger)."""
    found: list[ast.expr | ast.pattern] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            probes: list[ast.AST] = [node.left, *node.comparators]
        elif isinstance(node, ast.match_case):
            probes = [node.pattern]
        else:
            continue
        if any(_is_role_literal(sub) for probe in probes for sub in ast.walk(probe)):
            # `match_case` is not an expr/stmt; report the pattern, which carries
            # the position the marker attaches to.
            found.append(node.pattern if isinstance(node, ast.match_case) else node)
    return sorted(found, key=lambda n: (n.lineno, n.col_offset))


def _unmarked_role_comparisons(path: pathlib.Path) -> list[tuple[int, str]]:
    source = path.read_text()
    lines = source.splitlines()
    markers = _marker_lines(source)
    found: list[tuple[int, str]] = []
    for node in _dispatch_nodes(ast.parse(source)):
        end = node.end_lineno or node.lineno
        marked = any(ln in markers for ln in range(node.lineno, min(end, len(lines)) + 1))
        # A reason worth reading rarely fits on the comparison's own line, so the
        # contiguous comment block immediately above it counts too.
        ln = node.lineno - 1
        while not marked and ln >= 1 and lines[ln - 1].strip().startswith("#"):
            marked = ln in markers
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
    one marked one, and requires exactly the unmarked line back.

    It also pins the two ways the scrape could quietly stop seeing things, both
    of which it did before review caught them: an equality inside a MIXED chained
    comparison (`role == "rank" in supported` holds an `Eq` and an `In`, and a
    gate over every operator skipped the whole node), and a marker that is not
    really one -- a bare `# role-compare-ok` with no reason, or the text sitting
    in a string literal rather than a comment. Each is a case where the pin would
    have gone green while the guarantee it states was false."""
    probe = (
        "def f(role, supported):\n"
        '    if role == "team":\n'                       # 2: plain, unmarked
        "        return 1\n"
        '    if role == "player":  # role-compare-ok: marked inline\n'
        "        return 2\n"
        "    # role-compare-ok: marked by the comment block above\n"
        '    if role == "suit":\n'
        "        return 3\n"
        # A MIXED chained comparison: the node holds an `Eq` and an `In`, so a
        # gate over every operator would skip it and let the equality through.
        '    if role == "rank" in supported:\n'
        "        return 4\n"
        # A BARE marker with no reason is not a marker.
        '    if role == "team":  # role-compare-ok\n'
        "        return 5\n"
        # The marker text inside a STRING is not a comment, so not a licence.
        '    msg = "role-compare-ok: not a real marker"\n'
        '    if role == "player": return msg\n'
        # Membership, not equality — the same branch in another spelling.
        '    if role in ("team", "suit"):\n'
        "        return 6\n"
        # A role inside a CONTAINER operand, not a direct one.
        '    if supported == {"player", "team"}:\n'
        "        return 7\n"
        # A MATCH PATTERN — not a `Compare` at all, and this repo's house style.
        "    match role:\n"
        '        case "team":\n'
        "            return 8\n"
        "    return 0\n"
    )
    tmp = pathlib.Path(__file__).resolve().parent / "_role_pin_probe.py.txt"
    tmp.write_text(probe)
    try:
        found = _unmarked_role_comparisons(tmp)
    finally:
        tmp.unlink()
    # 2 plain, 9 mixed chain, 11 bare marker, 14 marker-in-a-string,
    # 15 membership, 17 container operand, 20 match pattern.
    assert [ln for ln, _ in found] == [2, 9, 11, 14, 15, 17, 20], found
