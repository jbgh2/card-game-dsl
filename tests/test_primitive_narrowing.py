"""The narrow primitive interface — completeness ledger.

property:   a game-local primitive sees VALUES, never an engine handle. Its
            implementation names no `Ctx` and no `RuntimeState`; everything
            it may read arrives as the two bundles the binder builds — its
            module's declared name-keyed reads (`GameReads`, bounded by
            `PRIMITIVE_READS`) and the engine-structural facts
            (`EngineFacts`) — so "this primitive cannot mutate state, make a
            decision, or observe an undeclared name" is structural, not a
            property of review.
domain:     every game-local primitive (derived: the dispatch tables in
            `cardlang/runtime/stdlib.py`, mapped name -> implementing
            module by AST, restricted to modules outside the engine core)
            x every forbidden engine handle (derived: `Ctx`'s own field set
            plus the engine types, NOT the handles modules happen to use
            today) x every `EngineFacts` field (derived: the dataclass).
registry:   `_ENGINE_CORE` (the module axis's only hand-authored half, and
            the safe polarity — a NEW runtime module is a game module by
            default and must pass the wall); `MIGRATED` (stage-2 progress);
            `EMITS_TRACE` (primitives returning events alongside a value);
            `STDLIB_*` in `cardlang/stdlib/functions.py` (the name axis).
covered:    (a) per-primitive: the implementation's signature names no
            forbidden handle — exhaustive over the derived name set, one
            cell per primitive, `xfail(strict=True)` until migrated so a
            migration that lands without updating `MIGRATED` fails LOUD as
            an unexpected pass;
            (b) per-module x per-handle: the whole crossed grid, so a
            module that drops `Ctx` from its signatures but keeps an
            import, a `.chooser` reach, or a `RuntimeState` annotation
            still fails its own cell;
            (c) `EngineFacts`: every field populated from a NAMED engine
            expression, each pinned against a live `RuntimeState`, with
            the two round-state views proven distinct (collapsing them is
            a behavior change, not a refactor);
            (d) `GameReads`: the bundle carries exactly the module's
            declared row and nothing else — an undeclared name is absent,
            not merely unfetched;
            (e) `EMITS_TRACE` two ways: every listed primitive returns
            `(value, events)`, no unlisted migrated primitive does.
sampled:    behavioral identity rides the byte-identical goldens and the
            playout suites, which is the whole gauge for this stage — a
            moved golden means the refactor changed behavior.
residual:   (1) the three auction outcomes (`bridge_`/`pinochle_`/
            `tarot_auction_outcome`) are implemented INSIDE
            `cardlang/runtime/stdlib.py`, which is engine core, so the
            game-module wall does not reach them; they are game knowledge
            in the language package and stage 4 (co-location) owns their
            move. Wall: `test_engine_core_game_knowledge_is_named`, which
            fails if that set changes without this ledger changing.
            Record: docs/roadmap.md, "Primitive sidecars".
            (2) `EngineFacts` is MODULE-granular by ratified stage-2 scope
            (2A): a primitive receives the facts bundle whole rather than
            the per-primitive `reads` clause of the design note's §2. The
            narrowing that remains is stage 3's, and until it lands a
            primitive can read a fact it does not need. Wall: the field set
            is closed and every field is consumed (c), so the bundle cannot
            grow speculatively.

red under (born-green cells):
- `combinations.py` passes (b) on arrival: it is the Tichu combination
  engine, already pure. Reddening mutation: annotate any of its functions
  `ctx: Ctx` and its row of (b) fails. Demonstrated and reverted.
"""

from __future__ import annotations

import ast
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.runtime.reads import PRIMITIVE_READS
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating
from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_CLIMB_FOLLOWS,
    STDLIB_CLIMB_LEADS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "cardlang" / "runtime"

# --- axis 1: the game-module set -------------------------------------------
#
# Hand-authored as the EXCLUSION half only, so the polarity is safe: a new
# file under cardlang/runtime/ is a game module until someone argues it into
# this table, and therefore has to pass the wall. Each row names why the
# engine core legitimately holds an engine handle.
_ENGINE_CORE: dict[str, str] = {
    "__init__.py": "package init",
    "chooser.py": "the decision seam itself",
    "driver.py": "engine core — builds and threads Ctx",
    "evaluate.py": "engine core — the expression interpreter",
    "execute.py": "engine core — the statement interpreter",
    "mechanics.py": "engine core — the round machinery",
    "observe.py": "engine core — the projection substrate",
    "phases.py": "engine core — phase sequencing",
    "reads.py": "the declared-reads accessors (the sanctioned raw-access site)",
    "rules.py": "engine core — rule application",
    "state.py": "engine core — defines RuntimeState and Ctx",
    "stdlib.py": "engine core — the dispatch layer that BUILDS the bundles",
    "values.py": "engine core — the value types",
}

_GAME_MODULES: tuple[str, ...] = tuple(
    sorted(p.name for p in RUNTIME_DIR.glob("*.py") if p.name not in _ENGINE_CORE)
)


def test_engine_core_exemptions_are_live() -> None:
    """The exclusion table pinned non-stale: every named file exists. A
    deleted engine-core module must leave this table, or the next file to
    take its name inherits an exemption nobody argued for."""
    names = {p.name for p in RUNTIME_DIR.glob("*.py")}
    for exempt, why in _ENGINE_CORE.items():
        assert exempt in names, f"stale exemption {exempt!r} ({why}) — file is gone"


# --- axis 2: the primitive name -> implementing module map ------------------


@dataclass(frozen=True)
class Impl:
    """One primitive's implementation site, as the dispatch layer names it."""

    primitive: str
    module: str  # bare file name, e.g. "gin.py"
    func: str  # the implementation's own name, which may differ


def _dispatch_imports(body: list[ast.stmt]) -> list[tuple[str, str]]:
    """Every `from cardlang.runtime.<mod> import <f>` inside one match arm."""
    out: list[tuple[str, str]] = []
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.ImportFrom) and (sub.module or "").startswith(
                "cardlang.runtime."
            ):
                mod = (sub.module or "").rsplit(".", 1)[-1]
                out.extend((f"{mod}.py", a.name) for a in sub.names)
    return out


@lru_cache(maxsize=None)
def _implementations() -> tuple[Impl, ...]:
    """Derive name -> implementation by parsing the dispatch layer's `match`
    arms. Derived, not listed: a primitive added to the dispatch enters this
    grid automatically, which is what stops the coverage domain from being
    whatever someone remembered to type."""
    tree = ast.parse((RUNTIME_DIR / "stdlib.py").read_text(encoding="utf-8"))
    found: list[Impl] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            pat = case.pattern
            if not (
                isinstance(pat, ast.MatchValue)
                and isinstance(pat.value, ast.Constant)
                and isinstance(pat.value.value, str)
            ):
                continue
            name = pat.value.value
            for mod, func in _dispatch_imports(case.body):
                found.append(Impl(primitive=name, module=mod, func=func))
    return tuple(sorted(found, key=lambda i: (i.primitive, i.module, i.func)))


_ALL_REGISTERED: frozenset[str] = (
    STDLIB_CALL_FUNCS
    | STDLIB_TRICK_OUTCOMES
    | STDLIB_AUCTION_OUTCOMES
    | STDLIB_EARLY_PREDICATES
    | STDLIB_CLIMB_LEADS
    | STDLIB_CLIMB_FOLLOWS
)

_GAME_IMPLS: tuple[Impl, ...] = tuple(
    i for i in _implementations() if i.module in _GAME_MODULES
)


def test_every_dispatched_primitive_is_a_registered_name() -> None:
    """The derivation's own sanity pin: the dispatch cannot route a name the
    front end never signatured (that would be unreachable code claiming
    coverage)."""
    unknown = sorted({i.primitive for i in _implementations()} - _ALL_REGISTERED)
    assert not unknown, f"dispatch arms for unregistered names: {unknown}"


def test_the_derived_axis_is_not_empty() -> None:
    """A scraper that silently matches nothing would make every grid below
    vacuously green — the failure mode this repo ranks with
    accepted-but-ignored."""
    assert len(_GAME_IMPLS) > 50, (
        f"derived only {len(_GAME_IMPLS)} game primitives — the dispatch "
        f"scraper has stopped matching; every cell below would be vacuous"
    )


# --- stage-2 progress registries -------------------------------------------

# Implementation SITES (`module::func`) that take no engine handle. Cells for
# anything not here are xfail(strict=True): narrowing a site without adding it
# fails as an unexpected pass, so the grid cannot silently under-report.
#
# Seeded with the sites that already qualify — the pure card-math scorers and
# the two climb helpers the OpenSpiel adapter calls. They are not stage-2 work;
# they are the shape stage 2 generalises, and pinning them now means a later
# change cannot quietly give one of them a handle.
NARROWED: frozenset[str] = frozenset(
    {
        "belote.py::belote_trick_winner",
        "belote.py::belote_trump_height",
        "bigtwo.py::bigtwo_universe",
        "cribbage.py::peg_pair_points",
        "cribbage.py::peg_run_points",
        "cribbage.py::value",
        "five_hundred.py::five_hundred_bid_level",
        "five_hundred.py::five_hundred_bid_value",
        "five_hundred.py::five_hundred_next_bid",
        "gin.py::card_points",
        "president.py::president_universe",
        "skat.py::skat_effective_loss",
        "skat.py::skat_next_bid",
        "tarot.py::tarot_card_points",
        "tarot.py::tarot_trick_winner",
        "tarot.py::tarot_trump_height",
        "tichu.py::TICHU_COMBO_CODEC",
    }
)

# Primitives narrowed by stage 2 so far, for the module-level wall below.
MIGRATED: frozenset[str] = frozenset()

# Primitives that return `(value, events)` — they compute a real value AND
# emit the engine's own trace vocabulary from a game-local site, so the
# emission travels back as data and the dispatch layer performs it.
EMITS_TRACE: frozenset[str] = frozenset(
    {
        "schnapsen_trick_winner",
        "doko_trick_winner",
        "skat_trick_winner",
        "five_hundred_trick_winner",
        "coup_game_summary",
    }
)


def test_progress_registries_name_real_things() -> None:
    """No progress claimed for a site or name the dispatch does not route."""
    known = {i.primitive for i in _GAME_IMPLS}
    assert MIGRATED <= known, f"MIGRATED names nothing real: {sorted(MIGRATED - known)}"
    sites = {s.key for s in _SITES}
    assert NARROWED <= sites, f"NARROWED names no site: {sorted(NARROWED - sites)}"


def test_emits_trace_names_are_real_primitives() -> None:
    known = {i.primitive for i in _GAME_IMPLS}
    assert EMITS_TRACE <= known, (
        f"EMITS_TRACE names nothing real: {sorted(EMITS_TRACE - known)}"
    )


# --- axis 3: the forbidden handles -----------------------------------------
#
# Derived from what `Ctx` actually offers, not from what game modules happen
# to reach for today: every public field of the dataclass, its two methods
# that hand out engine power, and the engine types themselves. A handle that
# is added to Ctx later joins this axis automatically.


@lru_cache(maxsize=None)
def _ctx_surface() -> tuple[str, ...]:
    """`Ctx`'s own attribute names, read off state.py's class body."""
    tree = ast.parse((RUNTIME_DIR / "state.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Ctx":
            fields = [
                s.target.id
                for s in node.body
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            ]
            methods = [s.name for s in node.body if isinstance(s, ast.FunctionDef)]
            return tuple(sorted(set(fields + methods)))
    raise AssertionError("Ctx not found in state.py — the handle axis lost its source")


_FORBIDDEN_TYPES: tuple[str, ...] = ("Ctx", "RuntimeState", "ZoneStore", "Chooser")


def test_ctx_surface_is_derived_not_empty() -> None:
    surface = _ctx_surface()
    # The fields this grid was authored against; a NEW one is not an error
    # (the axis is derived) but losing one silently would shrink the domain.
    for expected in ("rs", "chooser", "tracer", "locals", "observer", "acting_as"):
        assert expected in surface, (
            f"Ctx no longer exposes {expected!r} — if it moved, the handle "
            f"axis must follow it; if it is gone, drop it from this pin"
        )


# --- the scan ---------------------------------------------------------------


@dataclass
class ModuleScan:
    """One module's engine-handle contacts, by handle name."""

    hits: dict[str, list[str]]
    ctx_params: dict[str, str]  # function name -> where it takes a handle
    symbols: dict[str, str]  # top-level name -> "function" | "data"


def _scan(path: Path) -> ModuleScan:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=path.name)
    hits: dict[str, list[str]] = {}
    ctx_params: dict[str, str] = {}
    symbols: dict[str, str] = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[top.name] = "function"
        elif isinstance(top, ast.ClassDef):
            symbols[top.name] = "data"
        elif isinstance(top, ast.Assign):
            for t in top.targets:
                if isinstance(t, ast.Name):
                    symbols[t.id] = "data"
        elif isinstance(top, ast.AnnAssign) and isinstance(top.target, ast.Name):
            symbols[top.target.id] = "data"

    def note(handle: str, lineno: int) -> None:
        hits.setdefault(handle, []).append(f"{path.name}:{lineno}")

    for node in ast.walk(tree):
        # A forbidden TYPE named anywhere: annotation, import, isinstance.
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_TYPES:
            note(node.id, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in _FORBIDDEN_TYPES:
                    note(a.name, node.lineno)
        # A reach through a value spelled `ctx` for any of Ctx's own surface.
        elif isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id == "ctx":
                if node.attr in _ctx_surface():
                    note(f"ctx.{node.attr}", node.lineno)
        # A parameter annotated with a forbidden type.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                ann = arg.annotation
                if isinstance(ann, ast.Name) and ann.id in _FORBIDDEN_TYPES:
                    ctx_params[node.name] = f"{path.name}:{node.lineno} ({arg.arg})"
    return ModuleScan(hits=hits, ctx_params=ctx_params, symbols=symbols)


@lru_cache(maxsize=None)
def _scan_module(name: str) -> ModuleScan:
    return _scan(RUNTIME_DIR / name)


# --- grid (a): per-primitive, the implementation takes no handle ------------


@dataclass(frozen=True)
class Site:
    """One implementation SITE: `module::func`. The cell key is the site, not
    the primitive name, because the dispatch layer routes one name to several
    implementations — `climb_universe_function` sends `bigtwo_lead_options` to
    `bigtwo_universe`, `climb_codec_function` sends `tichu_lead_options` to
    `TICHU_COMBO_CODEC`. Keying by name let a handle-free sibling mask a
    `Ctx`-taking function, so the name is NOT the domain."""

    module: str
    func: str

    @property
    def key(self) -> str:
        return f"{self.module}::{self.func}"


_SITES: tuple[Site, ...] = tuple(
    sorted(
        {Site(module=i.module, func=i.func) for i in _GAME_IMPLS},
        key=lambda s: s.key,
    )
)


def _pending(reason: str) -> tuple[Any, ...]:
    """A not-yet-migrated cell. DECLARATIVE `xfail(strict=True)`, never the
    imperative `pytest.xfail()`: the imperative form aborts the test body, so
    it reports xfail whether or not the cell would now pass — a check that
    cannot fail. Strict marks run the body and turn an unexpected pass into a
    FAILURE, which is what forces `MIGRATED` to be updated in the same change
    that narrows a primitive."""
    return (pytest.mark.xfail(strict=True, reason=reason),)


_STAGE2 = "not yet narrowed (stage 2, by family)"


@pytest.mark.parametrize(
    "site",
    [
        pytest.param(
            s,
            marks=() if s.key in NARROWED else _pending(f"{s.key} {_STAGE2}"),
            id=s.key,
        )
        for s in _SITES
    ],
)
def test_implementation_site_takes_no_engine_handle(site: Site) -> None:
    """One cell per implementation site: it does not take `Ctx` (or any other
    engine handle) as a parameter. A site the scan cannot classify fails
    LOUD rather than passing by absence — an unresolvable symbol is exactly
    how a handle-taking implementation would slip through unanalysed."""
    scan = _scan_module(site.module)
    kind = scan.symbols.get(site.func)
    assert kind is not None, (
        f"{site.key}: the dispatch routes to this name but the module defines "
        f"no top-level symbol by it — the scan cannot analyse it, so this cell "
        f"would otherwise pass vacuously"
    )
    if kind == "data":
        # A dispatched constant (a codec object). It takes no parameters at
        # all, so the parameter property is trivially true; the handle it
        # could still hold is its CLASS's, which grid (b) covers module-wide.
        return
    where = scan.ctx_params.get(site.func)
    assert where is None, (
        f"{site.key} still takes an engine handle at {where}. The binder "
        f"passes values: the module's declared reads (GameReads) and the "
        f"engine facts (EngineFacts)."
    )


# --- grid (b): per-module x per-handle --------------------------------------


_HANDLES: tuple[str, ...] = (
    *_FORBIDDEN_TYPES,
    *(f"ctx.{a}" for a in _ctx_surface()),
)

# The stage-2 work list, authored per CELL rather than per module. Marking a
# whole module pending would assert nonsense — that `belote.py` must contain
# `ctx.chooser` — and would hide a real regression behind an expected failure.
# Only these (module, handle) pairs are red today; the other 332 cells are
# pinned GREEN right now, which is what stops a migration from introducing a
# handle a module never had.
_STILL_REACHES: dict[str, tuple[str, ...]] = {
    "belote.py": ("Ctx", "ctx.current_player", "ctx.rs"),
    "bigtwo.py": ("Ctx", "ctx.rs"),
    "canasta.py": ("Ctx", "ctx.rs"),
    "coup.py": ("Ctx", "ctx.rs", "ctx.trace"),
    "cribbage.py": ("Ctx", "ctx.rs"),
    "doko.py": ("Ctx", "ctx.rs", "ctx.trace"),
    "five_hundred.py": ("Ctx", "ctx.rs", "ctx.trace"),
    "gin.py": ("Ctx", "ctx.rs"),
    "pinochle.py": ("Ctx", "ctx.rs"),
    "president.py": ("Ctx", "ctx.rs"),
    "schnapsen.py": ("Ctx", "ctx.rs", "ctx.trace"),
    "skat.py": ("Ctx", "ctx.rs", "ctx.trace"),
    "stud.py": ("Ctx", "ctx.rs"),
    "tarot.py": ("Ctx", "ctx.rs"),
    "tichu.py": ("Ctx", "ctx.rs"),
}


def test_the_work_list_names_real_modules() -> None:
    """`_STILL_REACHES` cannot outlive its modules: a stale key would quietly
    shrink the red set to nothing."""
    unknown = sorted(set(_STILL_REACHES) - set(_GAME_MODULES))
    assert not unknown, f"work list names non-game-modules: {unknown}"


_MODULE_HANDLE_CELLS = [
    pytest.param(
        m,
        h,
        marks=()
        if h not in _STILL_REACHES.get(m, ())
        else _pending(f"{m} still reaches {h} (stage 2, by family)"),
        id=f"{m}-{h}",
    )
    for m in _GAME_MODULES
    for h in _HANDLES
]


@pytest.mark.parametrize(("module", "handle"), _MODULE_HANDLE_CELLS)
def test_game_module_is_free_of_engine_handle(module: str, handle: str) -> None:
    """The crossed wall. A module is only green once EVERY primitive it
    implements is migrated; until then each of its cells is a strict xfail,
    so finishing a module without updating MIGRATED fails loudly."""
    scan = _scan_module(module)
    where = scan.hits.get(handle, [])
    assert not where, (
        f"{module} still reaches the engine handle {handle!r} at "
        f"{', '.join(where)} — a game module sees values only."
    )


# --- grid (c): EngineFacts ---------------------------------------------------


def _sidecar() -> Any:
    """The mechanism under test. Imported lazily so that, before it exists,
    the cells below fail with this message rather than collapsing the whole
    module into a collection error."""
    try:
        from cardlang.runtime import sidecar
    except ImportError as exc:  # pragma: no cover - the red state
        pytest.fail(
            f"cardlang/runtime/sidecar.py does not exist yet: {exc}. It owns "
            f"EngineFacts, GameReads and the binder."
        )
    return sidecar


# The engine expression each field mirrors. This IS the field axis: a field
# added to EngineFacts without a row here fails `test_every_engine_fact_is_
# pinned`, and a row naming a field that does not exist fails too.
_FACT_SOURCES: dict[str, str] = {
    "seating": "rs.seating",
    "teams": "rs.teams",
    "team_of": "rs.team_of",
    "rank_index": "rs.rank_index",
    "round_state": "rs.mech_state[-1] if rs.mech_state else rs.last_round_state",
    "last_round_state": "rs.last_round_state",
    "actor": "ctx.current_player",
}


def _live_state() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="Pile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    rs.teams = (0, 1)
    rs.team_of = {0: 0, 1: 1}
    rs.rank_index = {"7": 0, "8": 1}
    rs.last_round_state = {"played": [], "marker": "terminal"}
    return rs


def test_every_engine_fact_is_pinned() -> None:
    """The field axis, both ways: EngineFacts' fields and `_FACT_SOURCES`'
    keys are the same set. A field with no named engine source cannot be
    reviewed for whether it is the RIGHT value."""
    facts_cls = _sidecar().EngineFacts
    fields = frozenset(facts_cls.__dataclass_fields__)
    assert fields == frozenset(_FACT_SOURCES), (
        f"EngineFacts fields {sorted(fields)} disagree with the pinned "
        f"sources {sorted(_FACT_SOURCES)}"
    )


@pytest.mark.parametrize("field", sorted(_FACT_SOURCES), ids=lambda f: f)
def test_engine_fact_carries_the_engine_value(field: str) -> None:
    """One cell per fact: the binder's bundle equals the engine expression
    `_FACT_SOURCES` names."""
    sidecar = _sidecar()
    rs = _live_state()
    facts = sidecar.engine_facts(rs, actor=1)
    expected: dict[str, Any] = {
        "seating": rs.seating,
        "teams": rs.teams,
        "team_of": rs.team_of,
        "rank_index": rs.rank_index,
        "round_state": rs.last_round_state,
        "last_round_state": rs.last_round_state,
        "actor": 1,
    }
    assert getattr(facts, field) == expected[field]


def test_the_two_round_state_views_are_distinct() -> None:
    """`round_state` is the `state` pronoun's view (the LIVE frame while a
    round runs); `last_round_state` is the terminal frame. Tarot and Belote
    read the first, Tichu's `tichu_dragon_won` the second — collapsing them
    changes behavior while a round is active, which is exactly what this
    stage must not do."""
    sidecar = _sidecar()
    rs = _live_state()
    rs.mech_state.append({"marker": "live"})
    facts = sidecar.engine_facts(rs, actor=None)
    assert facts.round_state == {"marker": "live"}
    assert facts.last_round_state == {"marker": "terminal"}


def test_engine_facts_is_frozen() -> None:
    """Structural, not conventional: a primitive cannot write back."""
    sidecar = _sidecar()
    facts = sidecar.engine_facts(_live_state(), actor=None)
    with pytest.raises((AttributeError, TypeError)):
        facts.actor = 3  # type: ignore[misc]


# --- grid (d): GameReads carries exactly the declared row -------------------


def test_game_reads_carries_exactly_the_declared_row() -> None:
    """The bundle is bounded by PRIMITIVE_READS: every declared name present,
    no undeclared name reachable. This is the property that makes the binder
    a narrowing rather than a rename of `Ctx`."""
    sidecar = _sidecar()
    rs = _live_state()
    row = next(
        r for r in PRIMITIVE_READS if r.module == "cardlang/runtime/schnapsen.py"
    )
    bundle = sidecar.game_reads(rs, row)
    assert frozenset(bundle.singles) == row.single_zones
    assert frozenset(bundle.families) == row.zone_families
    assert frozenset(bundle.state) == row.state_vars
    assert "hand" not in bundle.families, (
        "the bundle exposed a zone the row does not declare — the binder is "
        "handing over more than the declaration bounds"
    )


def test_game_reads_cards_are_immutable() -> None:
    """Zone cards arrive as tuples: a primitive cannot mutate a live zone
    through the bundle (today it receives the Zone's own mutable list)."""
    sidecar = _sidecar()
    rs = _live_state()
    rs.zones.single("trick_pile").cards.append(Card("7", "hearts"))
    row = next(
        r for r in PRIMITIVE_READS if r.module == "cardlang/runtime/schnapsen.py"
    )
    bundle = sidecar.game_reads(rs, row)
    assert isinstance(bundle.singles["trick_pile"], tuple)


# --- grid (e): the trace-returning registry, two ways -----------------------


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            nm,
            marks=() if nm in MIGRATED else _pending(f"{nm} {_STAGE2}"),
            id=nm,
        )
        for nm in sorted(EMITS_TRACE)
    ],
)
def test_tracing_primitive_returns_events(name: str) -> None:
    """A listed primitive hands its events back as data. Until it is
    migrated it still emits through `ctx.trace`, so the cell is a strict
    xfail — the same self-closing shape as the walls above."""
    impl = next(i for i in _GAME_IMPLS if i.primitive == name)
    scan = _scan_module(impl.module)
    assert "ctx.trace" not in scan.hits, (
        f"{name} still emits through ctx.trace — a narrowed primitive returns "
        f"(value, events) and the dispatch layer performs the emission"
    )


def test_no_unlisted_migrated_primitive_emits_traces() -> None:
    """The other direction: a module that still touches `ctx.trace` after
    migration means a tracing primitive escaped EMITS_TRACE."""
    for impl in _GAME_IMPLS:
        if impl.primitive not in MIGRATED or impl.primitive in EMITS_TRACE:
            continue
        scan = _scan_module(impl.module)
        assert "ctx.trace" not in scan.hits, (
            f"{impl.module} still reaches ctx.trace but {impl.primitive} is "
            f"not in EMITS_TRACE — list it, or route the emission back as data"
        )


# --- residual (1): the game knowledge that stays in engine core -------------

_ENGINE_CORE_GAME_KNOWLEDGE: frozenset[str] = frozenset(
    {
        "bridge_auction_outcome",
        "pinochle_auction_outcome",
        "tarot_auction_outcome",
    }
)


def test_engine_core_game_knowledge_is_named() -> None:
    """The residual, pinned so it cannot grow quietly. These primitives are
    implemented inside stdlib.py — engine core — so the game-module wall
    does not reach them; stage 4 (co-location) owns their move. A NEW
    per-game function added to stdlib.py fails here."""
    rows = {r.game_file for r in PRIMITIVE_READS if r.module == "cardlang/runtime/stdlib.py"}
    assert rows == {
        "bridge.cardlang",
        "cribbage.cardlang",
        "pinochle.cardlang",
        "french-tarot.cardlang",
    }, (
        f"stdlib.py's per-game declared-reads rows changed to {sorted(rows)} — "
        f"engine core is holding game knowledge for a different set of games "
        f"than this ledger's residual (1) records"
    )
    dispatched = {i.primitive for i in _implementations()}
    assert not (_ENGINE_CORE_GAME_KNOWLEDGE & dispatched), (
        "a residual primitive is now dispatched to a game module — move it "
        "out of this table and into the grid proper"
    )
