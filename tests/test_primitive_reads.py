"""The declared-reads registry's two-way pins — completeness ledger.

property:   every zone/state name a game-local Python primitive reads is
            declared in `PRIMITIVE_READS` (cardlang/runtime/reads.py),
            agrees exactly with both the module's source and the game
            file's declarations, and every failed read is a typed
            `PrimitiveReadError` naming the registry — a rename on either
            side of the coupling fails a static test here, never a bare
            `KeyError` mid-playout.
domain:     name-keyed `RuntimeState`/`ZoneStore` access (`get`/`set`/
            `declare`/`single`/`instance`/`is_family`/`families[...]`/
            `singles[...]`, from `state.py`'s API — the forbidden-pattern
            axis derives from the API, not from the patterns modules
            happen to use today) × every module under `cardlang/runtime/`
            (default-scanned glob; exemptions explicit and pinned
            non-stale) × every registry row's game file.
registry:   `PRIMITIVE_READS` (rows), `cardlang/runtime/*.py` (module
            axis), `docs/games/*.cardlang` declarations (validation side).
covered:    (a) registry↔game-file: every row's every name against the
            parsed game's state/zone declarations, per kind, with
            kind-mismatch detection — exhaustive over rows;
            (b) registry↔module-source: AST scan of every runtime module,
            exact per-kind set equality of accessor-call literals against
            the module's rows, `row()` lookups against the module's
            declared (module, game) keys, raw name-keyed access forbidden
            outside the pinned exemption list, `from …reads import …`
            forbidden (it would blind the scan), non-literal name
            arguments refused loud;
            (c) runtime refusal: the accessor behavior matrix — unknown
            row / undeclared name / declared-and-present / declared-but-
            missing — exercised for every accessor, plus the magic-hand
            Shadow Guard;
            (d) misuse probes for each defect the pins exist to catch
            (game-side rename, stale row, undeclared read, raw-access
            bypass per forbidden pattern, non-literal name, kind
            confusion, unknown row).
sampled:    end-to-end playout identity through the accessors rides the
            existing goldens and the metamorphic pairing suite (seed/step
            CI budget as before). Attribution of a name to the right row
            WITHIN a multi-row module (stdlib.py) is pinned per game file
            by (a) and per call site by the runtime refusal under the
            playout suite — the module-level scan (b) checks the union,
            not per-function attribution.
residual:   kernel round-state keys (`state["played"]`, `st.get("current")`
            in tarot.py/tichu.py) are the round machinery's own vocabulary,
            not game-declared names — a game author cannot rename them, so
            they are outside this property's domain (reads.py's docstring
            says so); the exempted engine-core modules read names off the
            AST, where resolve's guards own the class (each exemption row
            names that rationale and fails if the file stops tripping the
            scan).
"""

from __future__ import annotations

import ast
import random
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.resolve import _walk as _resolve_walk
from cardlang.runtime import reads
from cardlang.runtime.reads import PRIMITIVE_READS, PrimitiveReadError, PrimitiveReads
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Seating
from tests.metamorphic.pairing import GAMES_DIR, parse_corpus_game

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "cardlang" / "runtime"

# Engine-core modules where raw name-keyed access is sound: they read names
# off the parsed tree (`NameRef.name`, movement endpoints, …), where resolve's
# guards own the name↔declaration agreement — the coupling this registry
# declares does not exist there. reads.py is the accessor implementation:
# the one place that touches the raw API on the primitives' behalf.
# `test_raw_access_is_confined_to_the_exemptions` pins the list non-stale
# (an exempted file that stops using raw access must leave this table).
_EXEMPT_RAW_ACCESS: dict[str, str] = {
    "driver.py": "engine core — names come from the AST, resolve-guarded",
    "evaluate.py": "engine core — names come from the AST, resolve-guarded",
    "execute.py": "engine core — names come from the AST, resolve-guarded",
    "mechanics.py": "engine core — names from the AST plus the magic `hand`"
    " (decisions.md \"Declared parameter domains\")",
    "rules.py": "engine core — the magic `hand` read of `legal_cards`"
    " (decisions.md \"Declared parameter domains\")",
    "reads.py": "the accessor implementation — the sanctioned raw-access site",
}

_ALL_RUNTIME_MODULES: tuple[Path, ...] = tuple(sorted(RUNTIME_DIR.glob("*.py")))
_REGISTRY_MODULES: tuple[str, ...] = tuple(sorted({r.module for r in PRIMITIVE_READS}))


# --- the registry↔game-file pin -------------------------------------------


@dataclass(frozen=True)
class DeclaredNames:
    """One parsed game's declarations, split the way the registry splits."""

    state_vars: frozenset[str]
    zone_families: frozenset[str]  # declared with an index
    single_zones: frozenset[str]  # declared without one


@cache
def _declared_names(game_file: str) -> DeclaredNames:
    game = parse_corpus_game(GAMES_DIR / game_file)
    return DeclaredNames(
        state_vars=frozenset(
            sd.name
            for nd in _resolve_walk(game)
            if isinstance(nd, n.StateBlock)
            for sd in nd.decls
        ),
        zone_families=frozenset(z.name for z in game.zones if z.index is not None),
        single_zones=frozenset(z.name for z in game.zones if z.index is None),
    )


def _kind_of(decls: DeclaredNames, name: str) -> str | None:
    if name in decls.state_vars:
        return "state variable"
    if name in decls.zone_families:
        return "zone family"
    if name in decls.single_zones:
        return "single zone"
    return None


def _row_problems(row: PrimitiveReads, decls: DeclaredNames) -> list[str]:
    """Every disagreement between one registry row and the game file's actual
    declarations — the static form of the rename reproducer (rename a zone in
    the `.cardlang` and the row's name dangles here)."""
    problems: list[str] = []
    wanted: tuple[tuple[str, frozenset[str], frozenset[str]], ...] = (
        ("state variable", row.state_vars, decls.state_vars),
        ("zone family", row.zone_families, decls.zone_families),
        ("single zone", row.single_zones, decls.single_zones),
    )
    for kind, declared_reads, declared_in_game in wanted:
        for name in sorted(declared_reads - declared_in_game):
            actual = _kind_of(decls, name)
            if actual is None:
                problems.append(
                    f"{row.module} declares a read of {kind} {name!r}, but "
                    f"{row.game_file} declares no such name — renamed or "
                    f"removed in the game file? Update PRIMITIVE_READS "
                    f"(cardlang/runtime/reads.py) and the module together."
                )
            else:
                problems.append(
                    f"{row.module} lists {name!r} as a {kind}, but "
                    f"{row.game_file} declares it as a {actual} — fix the "
                    f"row's kind in PRIMITIVE_READS (cardlang/runtime/reads.py)."
                )
    return problems


@pytest.mark.parametrize(
    "row", PRIMITIVE_READS, ids=lambda r: f"{Path(r.module).stem}:{r.game_file}"
)
def test_registry_row_agrees_with_game_declarations(row: PrimitiveReads) -> None:
    assert (REPO_ROOT / row.module).exists(), (
        f"PRIMITIVE_READS names module {row.module!r}, which does not exist"
    )
    assert (GAMES_DIR / row.game_file).exists(), (
        f"PRIMITIVE_READS names game file {row.game_file!r}, which is not in "
        f"docs/games/"
    )
    problems = _row_problems(row, _declared_names(row.game_file))
    assert not problems, "\n".join(problems)


# --- the registry↔module-source pin (the AST scan) -------------------------


@dataclass
class ScanResult:
    raw_hits: list[str] = field(default_factory=list)
    # accessor-call literals: "state" / "family" / "instance" / "single"
    reads: dict[str, set[str]] = field(
        default_factory=lambda: {"state": set(), "family": set(), "instance": set(), "single": set()}
    )
    rows: set[tuple[str, str]] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)


# The GameReads bundle's fields, mapped to the declaration kind each holds.
# A narrowed primitive reads `gr.state["x"]` / `gr.families["x"][k]` /
# `gr.singles["x"]` where it used to call `reads.state(...)` etc.
_BUNDLE_KINDS: dict[str, str] = {
    "state": "state",
    "families": "family",
    "singles": "single",
}

# The bundle parameter's mandated name. The scan keys on it, because these
# field names are ordinary English that other classes use too (`ZoneStore`
# has its own `.singles`/`.families`), and a scan that matched every such
# subscript anywhere would report the engine's internals as declared reads.
# Keying on a name would normally open a silent hole — a primitive that named
# its bundle something else would go unscanned — so
# `test_bundle_parameter_is_named_consistently` closes it: any parameter
# annotated `GameReads` MUST be spelled this.
_BUNDLE_PARAM = "gr"


def _is_named(node: ast.expr, name: str) -> bool:
    """Is this expression a reference spelled `name` (bare or as the last
    attribute of a chain) — `rs` / `ctx.rs` / `self.rs`, `zones` / `rs.zones`?"""
    return (isinstance(node, ast.Name) and node.id == name) or (
        isinstance(node, ast.Attribute) and node.attr == name
    )


def _scan_source(source: str, where: str) -> ScanResult:
    """Classify every name-keyed state access in one module's source. The
    forbidden patterns enumerate `state.py`'s name-keyed API (RuntimeState
    `get`/`set`/`declare`; ZoneStore `single`/`instance`/`is_family` and the
    `families`/`singles` dicts) — the whole axis, not just the shapes modules
    currently use."""
    result = ScanResult()
    tree = ast.parse(source, filename=where)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "cardlang.runtime.reads":
            result.problems.append(
                f"{where}:{node.lineno}: `from cardlang.runtime.reads import …` "
                f"— import the module and call `reads.<accessor>` so this scan "
                f"can attribute the reads"
            )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            f = node.func
            if isinstance(f.value, ast.Name) and f.value.id == "reads":
                if f.attr in ("state", "family", "instance", "single"):
                    name_arg = node.args[2] if len(node.args) > 2 else None
                    if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
                        result.reads[f.attr].add(name_arg.value)
                    else:
                        result.problems.append(
                            f"{where}:{node.lineno}: reads.{f.attr}(...) whose "
                            f"name argument is not a string literal — the scan "
                            f"cannot pin it against PRIMITIVE_READS"
                        )
                elif f.attr == "row":
                    lits = [
                        a.value
                        for a in node.args
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)
                    ]
                    if len(lits) == 2:
                        result.rows.add((lits[0], lits[1]))
                    else:
                        result.problems.append(
                            f"{where}:{node.lineno}: reads.row(...) whose "
                            f"arguments are not two string literals"
                        )
            elif f.attr in ("get", "set", "declare") and _is_named(f.value, "rs"):
                result.raw_hits.append(f"{where}:{node.lineno}: rs.{f.attr}(...)")
            elif f.attr in ("single", "instance", "is_family") and _is_named(f.value, "zones"):
                result.raw_hits.append(f"{where}:{node.lineno}: zones.{f.attr}(...)")
            elif (
                f.attr == "get"
                and isinstance(f.value, ast.Attribute)
                and f.value.attr in ("families", "singles")
                and _is_named(f.value.value, "zones")
            ):
                result.raw_hits.append(
                    f"{where}:{node.lineno}: zones.{f.value.attr}.get(...)"
                )
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr in ("families", "singles")
            and _is_named(node.value.value, "zones")
        ):
            result.raw_hits.append(
                f"{where}:{node.lineno}: zones.{node.value.attr}[...]"
            )
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr in _BUNDLE_KINDS
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == _BUNDLE_PARAM
        ):
            # A NARROWED primitive's read: `gr.singles["trick_pile"]` off the
            # GameReads bundle the binder built. Same coupling to the game
            # file's declared names as the accessor call it replaces, so the
            # same pin applies — the spelling changed, the property did not.
            kind = _BUNDLE_KINDS[node.value.attr]
            idx = node.slice
            if isinstance(idx, ast.Constant) and isinstance(idx.value, str):
                result.reads[kind].add(idx.value)
            else:
                result.problems.append(
                    f"{where}:{node.lineno}: {node.value.attr}[...] whose key "
                    f"is not a string literal — the scan cannot pin it against "
                    f"PRIMITIVE_READS"
                )
    return result


@cache
def _scan_module(path: Path) -> ScanResult:
    return _scan_source(path.read_text(encoding="utf-8"), path.name)


def _expected_for_module(module: str) -> tuple[dict[str, frozenset[str]], set[tuple[str, str]]]:
    """What the registry says one module reads: per-kind name unions over its
    rows, and the exact (module, game) keys it must look up."""
    rows = [r for r in PRIMITIVE_READS if r.module == module]
    state: set[str] = set()
    families: set[str] = set()
    singles: set[str] = set()
    for r in rows:
        state |= r.state_vars
        families |= r.zone_families
        singles |= r.single_zones
    return (
        {
            "state": frozenset(state),
            "family": frozenset(families),
            "single": frozenset(singles),
        },
        {(r.module, r.game_file) for r in rows},
    )


@pytest.mark.parametrize("path", _ALL_RUNTIME_MODULES, ids=lambda p: p.name)
def test_module_source_agrees_with_registry(path: Path) -> None:
    """Both directions at once, for EVERY runtime module: an undeclared read
    (a literal the registry lacks) and a stale row entry (a declared name the
    module no longer reads) both fail; a module with no registry rows must
    make no accessor reads at all."""
    if path.name in _EXEMPT_RAW_ACCESS:
        return  # raw access covered by test_raw_access_is_confined_to_the_exemptions
    scan = _scan_module(path)
    assert not scan.problems, "\n".join(scan.problems)
    assert not scan.raw_hits, (
        "raw name-keyed state access outside cardlang/runtime/reads.py — "
        "route it through the reads accessors and declare it in "
        "PRIMITIVE_READS:\n" + "\n".join(scan.raw_hits)
    )
    module_key = f"cardlang/runtime/{path.name}"
    expected, expected_rows = _expected_for_module(module_key)
    scanned = {
        "state": frozenset(scan.reads["state"]),
        # `instance` reads a keyed member of a family: one declaration kind.
        "family": frozenset(scan.reads["family"] | scan.reads["instance"]),
        "single": frozenset(scan.reads["single"]),
    }
    assert scanned == expected, (
        f"{module_key}: accessor-call literals disagree with PRIMITIVE_READS "
        f"(cardlang/runtime/reads.py).\n  scanned:  {scanned}\n"
        f"  declared: {expected}\n"
        f"An undeclared read: declare it in the module's row. A stale entry: "
        f"remove it from the row (or the metamorphic rename suite loses a "
        f"renamable name for no reason)."
    )
    assert scan.rows == expected_rows, (
        f"{module_key}: reads.row(...) lookups {sorted(scan.rows)} disagree "
        f"with the registry's rows for this module {sorted(expected_rows)}"
    )


def _bundle_param_problems(source: str, where: str) -> list[str]:
    """Every parameter annotated `GameReads` that is not spelled `gr`."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source, filename=where)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for arg in [*node.args.args, *node.args.kwonlyargs]:
            ann = arg.annotation
            name = (
                ann.attr
                if isinstance(ann, ast.Attribute)
                else ann.id
                if isinstance(ann, ast.Name)
                else None
            )
            if name == "GameReads" and arg.arg != _BUNDLE_PARAM:
                problems.append(
                    f"{where}:{node.lineno}: {node.name}() names its GameReads "
                    f"parameter {arg.arg!r}; it must be {_BUNDLE_PARAM!r} so the "
                    f"declared-reads scan can attribute its reads"
                )
    return problems


@pytest.mark.parametrize("path", _ALL_RUNTIME_MODULES, ids=lambda p: p.name)
def test_bundle_parameter_is_named_consistently(path: Path) -> None:
    """The scan keys the bundle reads on the parameter's NAME, so an
    off-convention name would be silently unscanned — a read escaping the
    registry, which is the whole class this module exists to prevent."""
    problems = _bundle_param_problems(path.read_text(encoding="utf-8"), path.name)
    assert not problems, "\n".join(problems)


def test_probe_off_convention_bundle_name_is_refused_loud() -> None:
    """The misuse probe for the guard above: naming the bundle anything else
    fails loudly rather than quietly dropping that function's reads."""
    problems = _bundle_param_problems(
        "def f(facts, bundle: reads.GameReads) -> int:\n"
        '    return bundle.state["x"]\n',
        "probe.py",
    )
    assert problems and "must be 'gr'" in problems[0]
    # and the reads of an off-convention bundle are indeed invisible to the
    # scan — which is exactly why the guard above has to exist.
    scan = _scan_source(
        'def f(facts, bundle):\n    return bundle.state["x"]\n', "probe.py"
    )
    assert scan.reads["state"] == set()


def test_raw_access_is_confined_to_the_exemptions() -> None:
    """The exemption table, pinned both ways: every exempted file exists and
    still trips the scan (a stale exemption fails), and — the other
    direction, covered per-file above — no other file trips it."""
    names = {p.name for p in _ALL_RUNTIME_MODULES}
    for exempt, why in _EXEMPT_RAW_ACCESS.items():
        assert exempt in names, f"exempted file {exempt!r} no longer exists ({why})"
        scan = _scan_module(RUNTIME_DIR / exempt)
        assert scan.raw_hits, (
            f"{exempt} is exempted from the raw-access scan ({why}) but no "
            f"longer contains any raw name-keyed access — remove the stale "
            f"exemption so the default scan covers it"
        )


def test_every_registry_module_is_scanned() -> None:
    """Every module the registry names is inside the scanned glob (a row for
    a file outside cardlang/runtime/ would silently escape the source pin)."""
    scanned = {f"cardlang/runtime/{p.name}" for p in _ALL_RUNTIME_MODULES}
    for module in _REGISTRY_MODULES:
        assert module in scanned, (
            f"PRIMITIVE_READS row names {module!r}, which the source scan "
            f"does not cover"
        )
        assert module != "cardlang/runtime/reads.py", (
            "reads.py cannot declare rows for itself — it is the accessor "
            "implementation, exempt from its own scan"
        )


# --- the runtime refusal (the accessor behavior matrix) ---------------------


_COUP_ROW = reads.row("cardlang/runtime/coup.py", "coup.cardlang")


def _coup_like_state() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="influence", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="revealed", index="player", type_ref=n.TypeRef(name="Pile")),
        n.ZoneDecl(name="court_deck", index=None, type_ref=n.TypeRef(name="Deck")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    rs.declare("coins", False, {0: 2, 1: 2})
    return rs


def _bare_state() -> RuntimeState:
    """A live state whose game declares NONE of the row's names — the shape a
    game-file rename produces if it ever got past the static pins."""
    return RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))


def test_unknown_row_is_refused() -> None:
    with pytest.raises(PrimitiveReadError, match="no declared-reads row"):
        reads.row("cardlang/runtime/nonexistent.py", "nonexistent.cardlang")


def test_undeclared_name_is_refused_by_every_accessor() -> None:
    rs = _coup_like_state()
    for read in (
        lambda: reads.state(rs, _COUP_ROW, "not_declared"),
        lambda: reads.family(rs, _COUP_ROW, "not_declared"),
        lambda: reads.single(rs, _COUP_ROW, "not_declared"),
        lambda: reads.instance(rs, _COUP_ROW, "not_declared", 0),
    ):
        with pytest.raises(PrimitiveReadError, match="PRIMITIVE_READS"):
            read()


def test_declared_and_present_reads_pass_through() -> None:
    rs = _coup_like_state()
    assert reads.state(rs, _COUP_ROW, "coins") == {0: 2, 1: 2}
    assert set(reads.family(rs, _COUP_ROW, "influence")) == {0, 1}
    assert reads.single(rs, _COUP_ROW, "court_deck").cards == []
    assert reads.instance(rs, _COUP_ROW, "revealed", 1).cards == []


def test_declared_but_missing_names_fail_typed_not_keyerror() -> None:
    """The rename reproducer's runtime Shadow Guard: rename `influence` in
    coup.cardlang and (were the static pins somehow skipped) the playout
    fails as a PrimitiveReadError naming the registry and the game file —
    never the bare KeyError the metamorphic suite first surfaced."""
    rs = _bare_state()
    for read in (
        lambda: reads.state(rs, _COUP_ROW, "coins"),
        lambda: reads.family(rs, _COUP_ROW, "influence"),
        lambda: reads.single(rs, _COUP_ROW, "court_deck"),
        lambda: reads.instance(rs, _COUP_ROW, "influence", 0),
    ):
        with pytest.raises(PrimitiveReadError, match="coup.cardlang"):
            read()


def test_instance_key_miss_fails_typed() -> None:
    rs = _coup_like_state()
    with pytest.raises(PrimitiveReadError, match="no instance keyed 7"):
        reads.instance(rs, _COUP_ROW, "influence", 7)


def test_magic_hand_guard() -> None:
    rs = _bare_state()
    with pytest.raises(PrimitiveReadError, match="Declared parameter domains"):
        reads.magic_hand(rs)
    decls = (n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),)
    rs2 = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    assert set(reads.magic_hand(rs2)) == {0, 1}


# --- misuse probes (the adversarial pass) -----------------------------------
#
# One probe per defect the pins exist to catch. Each proves the failure is
# LOUD and lands in the right layer's channel (a test assertion here; a
# PrimitiveReadError at runtime) — never a silently-narrowed rename domain or
# a KeyError three phases later.


def test_probe_game_side_rename_fails_the_row_pin() -> None:
    """The rename reproducer, statically: a game file that no longer
    declares `influence` (renamed) makes coup's row dangle."""
    decls = _declared_names("coup.cardlang")
    renamed = DeclaredNames(
        state_vars=decls.state_vars,
        zone_families=frozenset(decls.zone_families - {"influence"} | {"influence2"}),
        single_zones=decls.single_zones,
    )
    problems = _row_problems(_COUP_ROW, renamed)
    assert any("influence" in p and "renamed or removed" in p for p in problems)


def test_probe_stale_registry_entry_fails_the_source_pin() -> None:
    """P2 — a row declaring a name the module never reads is a scan
    mismatch, not a quiet over-declaration."""
    doctored = replace(_COUP_ROW, state_vars=_COUP_ROW.state_vars | {"ghost_var"})
    scan = _scan_module(RUNTIME_DIR / "coup.py")
    scanned_state = frozenset(scan.reads["state"])
    assert scanned_state == _COUP_ROW.state_vars  # the real pin, green today
    assert scanned_state != doctored.state_vars  # the doctored row would fail it


def test_probe_undeclared_read_fails_the_source_pin() -> None:
    """P3 — a module reading a literal its row lacks (static half; the
    runtime half is test_undeclared_name_is_refused_by_every_accessor)."""
    scan = _scan_source(
        'import x\ndef f(ctx, r):\n    return reads.state(ctx.rs, r, "sneaky")\n',
        "probe.py",
    )
    assert scan.reads["state"] == {"sneaky"}  # the scan sees it; the set
    # comparison against a row without "sneaky" then fails, as P2 shows.


_RAW_BYPASS_SNIPPETS: tuple[tuple[str, str], ...] = (
    ("rs_get", 'v = ctx.rs.get("x")'),
    ("rs_set", 'ctx.rs.set("x", 1)'),
    ("rs_declare", 'ctx.rs.declare("x", False, 0)'),
    ("families_subscript", 'z = ctx.rs.zones.families["x"]'),
    ("families_get", 'z = ctx.rs.zones.families.get("x")'),
    ("singles_subscript", 'z = ctx.rs.zones.singles["x"]'),
    ("singles_get", 'z = ctx.rs.zones.singles.get("x")'),
    ("zones_single", 'z = ctx.rs.zones.single("x")'),
    ("zones_instance", 'z = ctx.rs.zones.instance("x", 0)'),
    ("zones_is_family", 'b = ctx.rs.zones.is_family("x")'),
    ("bare_rs_get", 'v = rs.get("x")'),
)


@pytest.mark.parametrize(
    "snippet", [s for _, s in _RAW_BYPASS_SNIPPETS], ids=[i for i, _ in _RAW_BYPASS_SNIPPETS]
)
def test_probe_every_raw_bypass_spelling_is_flagged(snippet: str) -> None:
    """P4 — the forbidden-pattern axis, exhaustively: one probe per
    name-keyed entry point of `state.py`'s API, each flagged by the scan."""
    scan = _scan_source(f"def f(ctx, rs):\n    {snippet}\n", "probe.py")
    assert scan.raw_hits, f"raw access not flagged: {snippet!r}"


def test_probe_non_literal_name_is_refused_loud() -> None:
    """P5 — a computed name defeats the static pin, so the scan refuses it
    rather than skipping it."""
    scan = _scan_source(
        "def f(ctx, r, which):\n    return reads.state(ctx.rs, r, which)\n",
        "probe.py",
    )
    assert scan.problems and "not a string literal" in scan.problems[0]


def test_probe_from_import_is_refused_loud() -> None:
    """P5b — `from …reads import state` would blind the `reads.`-prefix
    scan; refused at the import, not silently unscanned."""
    scan = _scan_source("from cardlang.runtime.reads import state\n", "probe.py")
    assert scan.problems and "import the module" in scan.problems[0]


def test_probe_kind_confusion_fails_the_row_pin() -> None:
    """P6 — a name declared as a single zone but listed as a state variable
    is a kind mismatch with its own message, not a missing-name report."""
    doctored = replace(
        _COUP_ROW,
        state_vars=_COUP_ROW.state_vars | {"court_deck"},
        single_zones=frozenset(),
    )
    problems = _row_problems(doctored, _declared_names("coup.cardlang"))
    assert any("kind" in p and "court_deck" in p for p in problems)
