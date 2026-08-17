"""A string that merely SPELLS a role is not a role.

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

**The guard is now the type.** `domains.Role` is a plain `Enum`, so under
`mypy --strict` a role compared against a string literal is a
`comparison-overlap` error, and so is `role in ("team", "player")`; a role
reached through a VARIABLE is caught the same way, which no scrape could do.
Every consumer that dispatches on a role takes a `Role`, and the one bridge
from parsed text (`domains.role_of`) returns `Role | None` so a caller must
say what a miss means. That is the rung-1 form of this module's original
guarantee (decisions.md "Prefer the guard you cannot need"), and it retired the
marker scrape this module used to be: markers, marker reasons, and the
"is this literal in a dispatch position" proxy are all gone, because mypy
answers the question they approximated.

What the type CANNOT see is what is left here
---------------------------------------------
`"player"` is also an ordinary English word this codebase writes for reasons
that have nothing to do with the registry: an unresolved NAME the author typed,
a component-set AXIS spelling, a parser keyword row, a reference-slot registry
KEY. Those are `str` and must stay `str` -- there is no role to promote. But
they are also exactly what a future role dispatch would look like on its way
in, spelled as a string because nobody classified it.

So the coincidence band is guarded by multiset: every string literal under
`cardlang/` that COINCIDES with a role spelling is authorized, per module. The
guard does not classify a literal; it forces a new one to be looked at, and the
question it forces is the useful one -- *is this a role, and should it be a
`Role`?*

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a role that participates in a decision is a `domains.Role`, and
            every remaining string literal in `cardlang/` that spells a role id
            is an authorized coincidence rather than an unclassified role.
domain:     the first half is mypy's, over every expression in the package --
            not this module's to enumerate, and not sampled by it either.
            The second half is every `str` constant under `cardlang/**/*.py[i]`
            whose value equals a role spelling, crossed with the module it sits
            in. Both axes DERIVED: the role ids from `domains.Role` (so adding
            a row widens the guard without editing it), the module set from the
            filesystem glob (so a new module is covered the day it lands).
registry:   `cardlang.domains.Role` for the spellings; `cardlang/**/*.py[i]`
            for the modules.
covered:    the multiset guard over every coincident literal in every module
            (`test_role_spellings_outside_the_type_are_guarded`); the derivation
            pin (`test_the_role_axis_follows_whatever_registry_it_is_given`),
            which calls the derivation with a SYNTHETIC registry so a
            hand-written set fails even when it happens to equal today's; and
            the exemption pin (`test_only_the_top_level_domains_module_is_
            exempt`), which builds a tree carrying both `pkg/domains.py` and
            `pkg/sub/domains.py`.
sampled:    none.
residual:   ONE, down from three. The `tests/` tree is not swept. mypy DOES
            hold it to the same `--strict` bar, so the type half of the
            property covers it exactly as it covers the package -- a test
            comparing a `Role` to a string literal fails the build. What is
            unswept there is only the coincidence band, whose members in test
            code are overwhelmingly game SOURCE text (`hand[player]` inside a
            DSL fixture), where a role spelling is the thing under test rather
            than a classification anyone could have got wrong. R4 --
            auditor-only, and it guards no information-set guarantee. Recorded
            in issue #152, which stays open for it and for the `tests/` sweep's
            own framing check. The other two residuals this module used to
            carry are CLOSED by the type: a role reached through a variable is
            now a type error at every consumer, and marker reasons no longer
            exist to be unreadable prose.
"""
from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterable
from dataclasses import replace

from cardlang.domains import DOMAINS, Domain

_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "cardlang"


def _role_ids(domains: Iterable[Domain]) -> frozenset[str]:
    """The role axis, derived from whatever registry it is handed.

    A FUNCTION rather than a module-level comprehension so the derivation can
    be called with a registry that is not today's. Checking the source text
    instead -- does the assignment mention `DOMAINS`? -- was the earlier form of
    this pin, and a mention is all it asked for: `frozenset({"player", "team",
    "suit", "rank"}) if DOMAINS else frozenset()` passed it while freezing the
    axis at today's four rows."""
    return frozenset(d.id.value for d in domains)


_ROLE_IDS = _role_ids(DOMAINS)


def _modules(root: pathlib.Path = _PACKAGE) -> list[pathlib.Path]:
    """Every module under `root` except the domain table itself.

    The table is where a role id is DEFINED, so spelling one there is the
    point, not a re-spelling. Matched by FULL PATH, not basename -- only
    `<root>/domains.py` is the table, and a subpackage's own `domains.py` is an
    ordinary module that a name match would drop from the sweep while the ledger
    still claimed every module.

    `.pyi` counts: a stub carrying a role spelling is source the sweep would
    otherwise never open. The suffixes are listed rather than globbed as
    `*.py*`, which would sweep in `__pycache__/*.pyc` and crash `ast.parse`."""
    table = root / "domains.py"
    return sorted(
        p for suffix in ("*.py", "*.pyi") for p in root.rglob(suffix) if p != table
    )


def _coincident_role_literals(root: pathlib.Path = _PACKAGE) -> dict[str, list[str]]:
    """Every string literal that spells a role id, per module.

    Read from the AST, not the text, so a role id inside a COMMENT is not a hit
    (this module's own prose would otherwise guard itself) while a role id
    inside a string literal is -- which is the right way round: the comment
    cannot become a dispatch, the literal can.

    Sorted, and a multiset rather than a count: a count lets one table row be
    added and another removed inside the same module without moving."""
    out: dict[str, list[str]] = {}
    for path in _modules(root):
        tree = ast.parse(path.read_text())
        found = sorted(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _ROLE_IDS
        )
        if found:
            out[str(path.relative_to(root))] = found
    return out


# The role spellings that are NOT roles. Authorized one by one; each is an
# English word, a mapping-table key, a parser keyword row, or an axis name.
#
# resolve's `rank`/`suit` are the reference-slot registry's KEYS -- the AST field
# names `CardLiteral.rank` and `CardLiteral.suit`, which coincide with two role
# ids and select nothing. The namespaces those rows map TO are spelled
# `deck_rank`/`deck_suit` precisely so the value half stays out of this band.
# resolve's `player` is the unresolved-NAME hint (`player` is bound only inside
# a player query) -- the word the author typed, not a role the pass dispatches
# on. `runtime/evaluate.py`'s pair are the player-query family's fixed BINDER
# name used as a locals-environment key (`with_local("player", ...)`) at the
# eager kinds' scan and at the ring search's lap -- an environment key, never
# a role dispatch. `runtime/values.py` holds the card flavor's AXIS spellings,
# reserved against a piece set claiming them, plus the deck's own rank and
# suit names.
# `openspiel/replay.py`'s pair is `_RETURNS_KEYED_ROLES`, the NAMES that
# module's diagnostic lists; the dispatch beside it is over `Role`, and the two
# are reconciled against `ZONE_INDEX_ROLES` by
# tests/test_openspiel_returns_keying.py.
_COINCIDENT_ROLE_LITERALS: dict[str, list[str]] = {
    "ir.py": ["player", "player", "rank", "rank", "suit"],
    "openspiel/replay.py": ["player", "team"],
    "parse.py": ["player", "player", "rank", "rank", "suit", "suit", "team", "team"],
    "resolve.py": ["player", "player", "rank", "rank", "suit"],
    "runtime/evaluate.py": ["player", "player"],
    "runtime/skat.py": ["suit", "suit"],
    "runtime/state.py": ["rank", "rank", "suit", "suit"],
    "runtime/values.py": ["rank"] * 14 + ["suit"] * 14,
    "typecheck.py": ["player", "player", "rank", "suit", "team", "team"],
}


def test_role_spellings_outside_the_type_are_guarded() -> None:
    """Every string that spells a role is an authorized coincidence.

    This is also what makes the guard non-vacuous in the deleting direction: an
    empty derivation is compared against a nonempty baseline and fails by name,
    so a `_PACKAGE` that resolves to nothing cannot pass.

    red under: (a) point `_PACKAGE` at a directory that does not exist -- the
    derived side comes back empty; (b) add `if index == "team":` anywhere in
    `cardlang/` over a plain `str` -- the literal lands here."""
    assert _coincident_role_literals() == _COINCIDENT_ROLE_LITERALS


def test_the_role_axis_follows_whatever_registry_it_is_given() -> None:
    """The role axis must be READ from the registry, not re-spelled here -- a
    hand-written set would freeze the axis at today's rows and this whole module
    would be the drift it forbids.

    Called with a SYNTHETIC registry on purpose. Every check that reads the
    real one is satisfiable by a frozen set that happens to equal it today:
    `_ROLE_IDS == {d.id.value for d in DOMAINS}` is two readings of one source,
    and even an AST check that the derivation MENTIONS `DOMAINS` passes for
    `frozenset({"player", ...}) if DOMAINS else frozenset()`. Both go green
    while the pin silently stops covering the fifth domain the day it lands.

    red under: `return frozenset({"player", "team", "suit", "rank"})` -- ignore
    the argument, in any of the shapes above."""

    class _Fake:
        def __init__(self, value: str) -> None:
            self.value = value

    synthetic = [
        replace(DOMAINS[0], id=_Fake("strain")),  # type: ignore[arg-type]
        replace(DOMAINS[1], id=_Fake("gambit")),  # type: ignore[arg-type]
    ]
    assert _role_ids(synthetic) == {"strain", "gambit"}
    # Shadow Guard, not a guard: an empty real registry is already caught by the
    # multiset guard above (no role ids -> no literals -> empty derivation), but
    # that failure reads as a table diff. This one names the cause.
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
