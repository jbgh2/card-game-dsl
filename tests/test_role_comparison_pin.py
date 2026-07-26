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

Two guarantees, two mechanisms
------------------------------
A role literal in a DISPATCH position must be marked. A role literal OUTSIDE
one is data -- a key in a mapping table, an axis name -- and selects nothing,
so demanding a reason for each of the 54 would dilute the marker exactly where
it carries weight. But "outside a dispatch position" is a PROXY (is the literal
enclosed in a `Compare` or a `match_case`), and a proxy errs both ways: hoist
`_KEYED = {"player", "team"}` to a module constant and `role in _KEYED`
branches on two role literals that no longer sit inside any comparison. So the
data band is not left silent -- it is walled as a per-module multiset. The wall
does not classify a literal; it forces a new one to be looked at, which is the
judgement the proxy cannot make.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   every construct in `cardlang/` that BRANCHES on a role-id string
            literal is either inside `cardlang/domains.py` (the table itself) or
            carries a `# role-compare-ok: <reason>` marker; and every role-id
            literal that does NOT branch is accounted for in a walled per-module
            multiset. The marker is read from the token stream, so the text
            inside a string literal licenses nothing.
domain:     the branching POSITION, not one spelling of it (`_dispatch_nodes`):
            a role literal anywhere inside a comparison's operands under ANY
            operator -- equality, inequality, membership, and at any depth, so a
            role inside a container literal counts -- and a role literal in a
            `match` pattern, which is not a `Compare` at all and is this repo's
            house dispatch style. Crossed with every `.py`/`.pyi` module under
            `cardlang/`. All three axes are DERIVED: the node set by walking each
            module's AST (so a comment mentioning `== "team"` is not a hit, and a
            new module is covered the day it lands), the role ids from
            `domains.DOMAINS` (so adding a domain widens the pin without editing
            it), the module set from the filesystem glob.
registry:   `cardlang.domains.DOMAINS` for the role ids; `cardlang/**/*.py[i]`
            for the modules; `_dispatch_nodes` for the position axis.
covered:    the marker scrape, over every module, every role id and every
            branching shape; the data-position multiset wall, over every role
            literal the scrape does NOT reach; and three pins that each guard
            one way the scrape could go quietly green --
            `test_the_scrape_can_see_an_unmarked_comparison` feeds it eleven
            shapes and requires exactly the nine unmarked lines back;
            `test_the_role_axis_follows_whatever_registry_it_is_given` calls the
            derivation with a SYNTHETIC registry, so a hand-written set fails
            even when it happens to equal today's `DOMAINS`;
            `test_only_the_top_level_domains_module_is_exempt` builds a tree
            carrying both `pkg/domains.py` and `pkg/sub/domains.py`.
sampled:    none -- the scrape is exhaustive over its derived domain, and the
            band outside that domain is walled rather than sampled.
residual:   THREE, each a wall this mechanism cannot build:
            (1) a role id reached through a VARIABLE rather than a literal is
            out of reach of any scrape (roadmap.md, "Not yet migrated").
            (2) a marker's REASON is prose. `.` satisfies "nonempty", and a
            reason asserting a registry pin ("pinned against SIMULTANEOUS_ROLES
            beside it") stays green when that pin is later deleted. The
            tag-vocabulary upgrade that would make the reason's CLASS
            machine-checkable is recorded in roadmap.md, "Not yet migrated".
            (3) `tests/` is NOT swept, though it carries 37 branching sites --
            more than production's 14 -- including `openspiel_ready/harness.py`,
            the proof layer. Sweeping it is a new domain needing its own framing
            check and probes, so it is deferred loudly rather than bolted on
            (roadmap.md, "Not yet migrated"). The precedent cuts the other
            way and is recorded as
            such: mypy holds `tests/` to the same strict bar.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import tokenize
from collections.abc import Iterable
from dataclasses import replace

import pytest

from cardlang.domains import DOMAINS, Domain

_MARKER = "role-compare-ok"
# A marker is a COMMENT, carrying a NONEMPTY reason, at a token boundary. Each
# clause earns its place: a bare `# role-compare-ok` would let a placeholder
# stand in for the reasoning the marker exists to force, and an unanchored match
# would let `# not-role-compare-ok:` -- prose SAYING the opposite -- license the
# very thing it denies. Both are the "a check that cannot fail" defect this
# module guards against, one level down.
_MARKER_RE = re.compile(rf"(?<![\w-]){_MARKER}\s*:\s*\S")
_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "cardlang"


def _role_ids(domains: Iterable[Domain]) -> frozenset[str]:
    """The role axis, derived from whatever registry it is handed.

    A FUNCTION rather than a module-level comprehension so the derivation can
    be called with a registry that is not today's. Checking the source text
    instead -- does the assignment mention `DOMAINS`? -- was the earlier form of
    this pin, and a mention is all it asked for: `frozenset({"player", "team",
    "suit", "rank"}) if DOMAINS else frozenset()` passed it while freezing the
    axis at today's four rows."""
    return frozenset(d.id for d in domains)


_ROLE_IDS = _role_ids(DOMAINS)


def _modules(root: pathlib.Path = _PACKAGE) -> list[pathlib.Path]:
    """Every module under `root` except the domain table itself.

    The table is where a role id is DEFINED, so comparing one there is the
    point, not a re-spelling. Matched by FULL PATH, not basename -- only
    `<root>/domains.py` is the table, and a subpackage's own `domains.py` is an
    ordinary module that a name match would drop from the sweep while the ledger
    still claimed every module.

    `.pyi` counts: a stub carrying a role comparison is source the sweep would
    otherwise never open. The suffixes are listed rather than globbed as
    `*.py*`, which would sweep in `__pycache__/*.pyc` and crash `ast.parse`."""
    table = root / "domains.py"
    return sorted(
        p for suffix in ("*.py", "*.pyi") for p in root.rglob(suffix) if p != table
    )


def _comment_lines(source: str) -> tuple[set[int], set[int]]:
    """(lines carrying a well-formed marker, lines that are a STANDALONE comment).

    The MARKER half is read from the token stream rather than from the text, so
    it is not satisfied by something that merely looks the part: the marker text
    inside a string literal is not a comment and licenses nothing. That property
    is pinned (probe shapes 6 and 11).

    The STANDALONE half reads from the token stream too, but is honest about
    what that buys: measured against a plain `startswith("#")` text scan it is
    INERT -- zero differences across all 63 real modules and 10,997 generated
    sources -- because a standalone comment is a subset of `#`-leading text, so
    the block chain is only ever shorter, and a string's opening line is never
    `#`-leading, so it breaks the chain before reaching a real marker. It is
    retained as the structurally correct reading of "a comment", NOT because it
    catches a case the marker half misses, and the ledger credits it with no
    witness."""
    text = source.splitlines()
    markers: set[int] = set()
    standalone: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        row, col = tok.start
        if _MARKER_RE.search(tok.string):
            markers.add(row)
        if row <= len(text) and not text[row - 1][:col].strip():
            standalone.add(row)
    return markers, standalone


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

    This is a PROXY for "the literal participates in a decision", and it errs
    both ways. It over-reports: a mapping table that happens to sit inside a
    comparison (`{"player": 1, "team": 2}.get(role, 0) > 1`) is flagged and
    wants a marker -- loud, so it costs a reader a minute. It under-reports: a
    role set hoisted to a module constant, or `role.startswith("team")`, is a
    decision this function cannot see. That direction is silent, which is why
    everything outside it is walled by count rather than left unexamined (see
    `_data_position_role_literals`)."""
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
    markers, standalone = _comment_lines(source)
    found: list[tuple[int, str]] = []
    for node in _dispatch_nodes(ast.parse(source)):
        end = node.end_lineno or node.lineno
        marked = any(ln in markers for ln in range(node.lineno, min(end, len(lines)) + 1))
        # A reason worth reading rarely fits on the comparison's own line, so the
        # contiguous comment block immediately above it counts too.
        ln = node.lineno - 1
        while not marked and ln in standalone:
            marked = ln in markers
            ln -= 1
        if not marked:
            found.append((node.lineno, lines[node.lineno - 1].strip()))
    return found


def _data_position_role_literals(root: pathlib.Path = _PACKAGE) -> dict[str, list[str]]:
    """Every role literal the dispatch proxy does NOT reach, per module.

    Sorted, and a multiset rather than a count: a count lets one table row be
    added and another removed inside the same module without moving."""
    out: dict[str, list[str]] = {}
    for path in _modules(root):
        tree = ast.parse(path.read_text())
        inside = {id(sub) for node in _dispatch_nodes(tree) for sub in ast.walk(node)}
        data = sorted(
            str(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and _is_role_literal(node)
            and id(node) not in inside
        )
        if data:
            out[str(path.relative_to(root))] = data
    return out


# The 54 role literals that select nothing today. Authorized one by one: each is
# a mapping-table key, a parser keyword row or an axis name. The band is walled
# rather than trusted because the proxy above cannot see a decision that moved
# out of a comparison -- so a role set hoisted to a module constant adds two
# entries here, and `role.startswith("team")` adds one, either of which reddens.
_DATA_POSITION_ROLE_LITERALS: dict[str, list[str]] = {
    "ir.py": ["player", "player", "rank", "suit"],
    "openspiel/replay.py": ["player", "team"],
    "parse.py": ["player", "player", "rank", "rank", "suit", "suit", "team", "team"],
    "resolve.py": ["player", "player"],
    "runtime/evaluate.py": ["player"],
    "runtime/skat.py": ["suit"],
    "runtime/state.py": ["rank", "rank", "suit", "suit"],
    "runtime/values.py": ["rank"] * 13 + ["suit"] * 13,
    "typecheck.py": ["player", "player", "rank", "suit", "team", "team"],
}


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


def test_role_literals_outside_a_dispatch_position_are_walled() -> None:
    """The band the dispatch proxy cannot see is authorized, not assumed.

    This is also what makes the parametrized sweep above non-vacuous. That sweep
    is one row per module, so a `_PACKAGE` that resolves to nothing yields an
    EMPTY parametrization -- which pytest reports as a skip, exit 0, with the
    module's whole guarantee silently retired. Here an empty derivation is
    compared against a nonempty baseline and fails by name.

    red under: (a) point `_PACKAGE` at a directory that does not exist -- the
    derived side comes back empty; (b) hoist a role set out of its comparison
    (`_KEYED = {"player", "team"}` beside `if role in _KEYED:`) -- the two
    literals leave the dispatch position and land here."""
    assert _data_position_role_literals() == _DATA_POSITION_ROLE_LITERALS


def test_the_role_axis_follows_whatever_registry_it_is_given() -> None:
    """The role axis must be READ from the registry, not re-spelled here -- a
    hand-written set would freeze the axis at today's rows and this whole module
    would be the drift it forbids.

    Called with a SYNTHETIC registry on purpose. Every check that reads the
    real one is satisfiable by a frozen set that happens to equal it today:
    `_ROLE_IDS == {d.id for d in DOMAINS}` is two readings of one source, and
    even an AST check that the derivation MENTIONS `DOMAINS` passes for
    `frozenset({"player", ...}) if DOMAINS else frozenset()`. Both go green
    while the pin silently stops covering the fifth domain the day it lands.

    red under: `return frozenset({"player", "team", "suit", "rank"})` -- ignore
    the argument, in any of the shapes above."""
    synthetic = [replace(DOMAINS[0], id="strain"), replace(DOMAINS[1], id="gambit")]
    assert _role_ids(synthetic) == {"strain", "gambit"}
    # Backstop, not a wall: an empty real registry is already caught by the
    # multiset wall above (no role ids -> no data literals -> empty derivation),
    # but that failure reads as a table diff. This one names the cause.
    assert _ROLE_IDS, "the registry yielded no roles — the derivation is broken"


def test_only_the_top_level_domains_module_is_exempt(tmp_path: pathlib.Path) -> None:
    """`domains.py` is exempt because it is the TABLE, and only one file is.

    red under: match the exemption by basename (`_REGISTRY_MODULE = "domains.py"`
    with `p.name != _REGISTRY_MODULE`) -- `sub/domains.py` vanishes from the
    sweep while the ledger still claims every module. That form shipped, and no
    test in the suite noticed it."""
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    for rel in ("domains.py", "other.py", "sub/domains.py", "sub/__init__.pyi"):
        (pkg / rel).write_text("")
    assert [str(p.relative_to(pkg)) for p in _modules(pkg)] == [
        "other.py",
        "sub/__init__.pyi",
        "sub/domains.py",
    ]


def test_the_scrape_can_see_an_unmarked_comparison() -> None:
    """The scrape itself is load-bearing, so prove it FIRES rather than trusting
    a green run over the swept tree (a scrape that matched nothing would also be
    green). Feeds it a synthetic module of eleven shapes -- nine that must be
    reported and two that must not -- and requires exactly the nine lines back.

    Every shape here DISCRIMINATES: each one comes back differently under the
    implementation it guards against, which two earlier shapes did not. A marker
    string sitting on its own line above the node was credited with pinning the
    token-stream read, but a per-line substring scan reports that case
    identically -- the block chain stops at the string's line either way. The
    two shapes that do discriminate put the marker text inside a string ON the
    node's own line, and INSIDE the node's multi-line span, which is the range
    `marked` scans directly."""
    probe = (
        "def f(role, supported):\n"
        '    if role == "team":\n'                       # plain, unmarked
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
        # Marker text in a STRING on the node's OWN line: a substring scan reads
        # this line as marked, the token stream does not.
        '    if role == "player": return "role-compare-ok: a string, not a marker"\n'
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
        # A NEGATED marker: contains the token as a substring, licenses nothing.
        '    if role == "suit":  # not-role-compare-ok: accidental\n'
        "        return 9\n"
        # Marker text in a string INSIDE the node's own multi-line span, which
        # is the range `marked` scans before it ever walks the block above.
        "    if role in {\n"
        '        "rank": "role-compare-ok: a dict value, not a comment",\n'
        "    }:\n"
        "        return 10\n"
        "    return 0\n"
    )
    tmp = pathlib.Path(__file__).resolve().parent / "_role_pin_probe.py.txt"
    tmp.write_text(probe)
    try:
        found = _unmarked_role_comparisons(tmp)
    finally:
        tmp.unlink()
    # 2 plain, 9 mixed chain, 11 bare marker, 13 marker-string on the node's own
    # line, 14 membership, 16 container operand, 19 match pattern, 21 negated
    # marker (`not-role-compare-ok`), 23 marker-string inside the node's span.
    assert [ln for ln, _ in found] == [2, 9, 11, 13, 14, 16, 19, 21, 23], found
