"""T2: alpha-rename (docs/design-notes/metamorphic-suite.md, item 1).

Renames every ZONE and STATE VARIABLE declaration, and every reference to
one, through a generated map. This DSL has no separate player/team
IDENTIFIER syntax to rename alongside them — a named role like `dealer` or
`declarer` (Bridge) is a plain state variable of type `Player`
(`cardlang/ast/nodes.py`, `StateDecl`), so it is already covered by the
state-variable case; there is nothing left over for a third category.

Why a blind textual rename of every matching `NameRef` is sound here, pre-
resolve, with no scope information available yet: `resolve._classify`
(`cardlang/resolve.py`) resolves a bare name against ONE flat, ordered set of
namespaces — locals, then state vars, then zones, then enum values, then
pronouns, then stdlib functions — and only ZONES and STATE VARIABLES are
declared here (rule/move-type/procedure/function/define/type names live in
their own dedicated syntactic slots — `constrains:`, `active_rules:`,
`x.field`, `transition_to:` — never reachable as a bare `NameRef`; see
`resolve._check_duplicate_names`'s docstring). So the only way a blanket
rename of a zone/state name could change what some OTHER `NameRef` of the
same spelling denotes is if that other spelling is a LOCAL BINDER (a `let`,
a loop variable, a move/function/procedure parameter, a struct field)
somewhere in the same game shadowing the zone/state var being renamed — a
local's classification always wins under `_classify`'s ordering, so a
same-spelled local reference would otherwise get swept into the rename too,
denoting something it never denoted.

Two defenses close that gap:

1. Every rename TARGET is chosen fresh with respect to the WHOLE game — not
   just its other declarations, but every string that appears ANYWHERE in
   the parsed tree (`_all_string_tokens`). A target nothing in the game
   already spells cannot be captured by an existing binder, so applying the
   map cannot introduce a NEW shadow that did not exist before.
2. Every rename SOURCE is checked against every name ANY construct in the
   game binds locally, ANYWHERE (`_locally_bound_names` — a flat, not
   scope-precise, union; the same shape as `resolve._template_binders`'s own
   flat collision check, at game scope rather than one rule's, and reusing
   `resolve._walk`/`_introduced_binders` directly rather than
   re-enumerating the binder registry — CLAUDE.md "Stop-and-fix at write
   time": the resolver already owns this table). A source name present in
   that set is excluded from the rename (`RenamePlan.unsafe`) rather than
   renamed unsoundly: somewhere in the game a local of the identical
   spelling could shadow it, and pre-resolve there is no scope information
   to tell which occurrences are the zone/state var and which are the
   local.

`unsafe` is empty across the whole corpus today (test_rename.py pins this
with a test that can fail); a future corpus game that trips it renames
everything else and leaves that one name alone, which is safe, not silent —
the excluded names are on `RenamePlan.unsafe`, not swallowed.

Three more exclusions, found empirically by running this transform and
reading the resulting failures — all real, all OUT of T2's domain (the
spec does not say these names are meaningless), none a bug in this
transform:

**A `requires`d name is a contract, not a game-private spelling.** A game
that `uses` a family library shares a state namespace with library text
this transform does not rewrite, and the spelling IS the interface
(decisions.md "Family libraries"). Renaming one would break the contract —
a real semantic change, so T2's premise does not hold for it and the name
is excluded (`RenamePlan.excluded_contract`) rather than renamed. Note this
exclusion is derived from the library's own `requires` block, not a
hand-listed set, so it tracks the libraries automatically.

**`hand` is a language-wide magic name, not a renamable zone.** decisions.md
"Declared parameter domains": a `Card`-typed move parameter enumerates "the
acting player's live hand" and "a Card parameter in a game with no
`hand[player]` zone" is rejected with a message — `resolve.py` enforces this
structurally (`z.name == "hand" and z.index == "player"`), and the kernel's
legal-move engine (`runtime/rules.py::legal_cards`) and move-parameter
enumerator (`runtime/mechanics.py::param_domain`) both look it up by that
exact name. Renaming it produces a tree the PIPELINE rejects (or, if the game
declares no Card-parameterized move, one the RUNTIME cannot serve
`Card`-typed candidates for) — squarely a spec-documented exception, the same
shape as T5 excluding an order-sensitive declaration with a citation, not a
defect this transform papers over. `_GLOBAL_EXCLUSIONS` below excludes it
corpus-wide.

**Game-local runtime primitives are written against ONE game's specific
declared spelling.** A corpus game with a bespoke mechanic ships a
`cardlang/runtime/<game>.py` module of Python (kernel-migration.md's sanctioned "game-local
stdlib primitive" pattern — Stud's `pot_share`, Skat's `skat_matadors`,
Tichu's `tichu_mahjong_holder`, …) that reads live `RuntimeState` by the
zone/state-variable name ITS AUTHOR gave it — a Python string literal, never
derived from the AST the way `execute.py`/`evaluate.py` read a
`NameRef.name` off the tree. This transform's own pairing run is what FIRST
surfaced that coupling, empirically, as a `KeyError` at PLAYOUT time (the
tree passes resolve/typecheck/expand — the pipeline has no way to know). The
coupling is now DECLARED rather than latent: every such read goes through
the typed accessors of `cardlang/runtime/reads.py`, whose `PRIMITIVE_READS`
registry is pinned two ways by tests/test_primitive_reads.py — every
declared name against the game file's actual declarations, and every
module's accessor-call literals against its rows, exactly. This transform
derives its exclusions from that registry (`_coupled_names` below) instead
of keeping a copy that could drift: a primitive that starts or stops reading
a name updates the registry (the source pin forces it), and the exclusion
set follows automatically. Because the registry is pinned EXACT in both
directions, the exclusion is never generous — every excluded name really is
read by some primitive — and never short: a missing declaration fails the
static pin before this suite would meet it at playout.
Were some future game's SAFE set ever empty after every exclusion,
`test_every_game_renames_something` (test_rename.py) fails LOUDLY rather
than the pairing test passing vacuously over nothing renamed — a hard
failure, deliberately, rather than a quieter skip: an empty safe set means
this transform cannot exercise that game AT ALL, which is worth blocking on,
not stepping around — see `test_rename.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import cast

from cardlang.ast import nodes as n
from cardlang.diagnostics import Span
from cardlang.libraries import library_names, load_library
from cardlang.resolve import _introduced_binders
from cardlang.resolve import _walk as _resolve_walk
from cardlang.runtime.reads import PRIMITIVE_READS
from tests.metamorphic.pairing import Event

_PREFIX = "_mt_"

# The zone `Card`-typed move parameters are structurally required to name
# (decisions.md "Declared parameter domains"; resolve.py's
# `_check_card_vocabulary`: `z.name == "hand" and z.index == "player"`;
# `runtime/rules.py::legal_cards`; `runtime/mechanics.py::param_domain`'s
# Card branch). A language-wide magic name, not a per-game renamable zone —
# see the module docstring.
_GLOBAL_EXCLUSIONS: frozenset[str] = frozenset({"hand"})

def _coupled_names(game_file: str) -> frozenset[str]:
    """Every zone/state name a game-local primitive reads for `game_file` —
    derived from the declared-reads registry (`PRIMITIVE_READS`,
    cardlang/runtime/reads.py), unioned over the game's rows (a game may be
    served by its own module AND stdlib.py). See the module docstring's
    second exclusion."""
    names: set[str] = set()
    for row in PRIMITIVE_READS:
        if row.game_file == game_file:
            names |= row.state_vars | row.zone_families | row.single_zones
    return frozenset(names)


def _all_string_tokens(game: n.Game) -> frozenset[str]:
    """Every string appearing anywhere in the parsed tree — deliberately
    broader than "every declared name": a maximally conservative freshness
    check (also sweeps `StrLit`/`CardLiteral` contents, phase names, move-type
    names, …), cheap at corpus scale."""
    tokens: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, str):
            tokens.add(node)
        elif isinstance(node, tuple):
            for item in node:
                walk(item)
        elif is_dataclass(node) and not isinstance(node, Span):
            for f in fields(node):
                walk(getattr(node, f.name))

    walk(game)
    return frozenset(tokens)


def _locally_bound_names(game: n.Game) -> frozenset[str]:
    """Every name bound by a local-introducing construct anywhere in the
    game — see the module docstring, defense 2."""
    names: set[str] = set()
    for nd in _resolve_walk(game):
        names.update(_introduced_binders(nd))
        if isinstance(nd, (n.MoveTypeDef, n.FunctionDef, n.ProcedureDef, n.RuleDef)):
            names.update(p.name for p in nd.params)
        if isinstance(nd, n.TypeDef):
            names.update(f.name for f in nd.fields)
    return frozenset(names)


@dataclass(frozen=True)
class RenamePlan:
    """The rename this transform will apply. `name_map` covers both zones
    and state variables (safe to share one flat map — see the module
    docstring: their namespaces never collide, asserted below). `zone_map`
    is the subset the trace-level hook needs: state-variable names never
    appear inside an observation event (only VALUES are rendered, never a
    declaring variable's own name — `runtime/observe.py`'s closed event
    vocabulary), so only zone labels ever need translating back.

    `unsafe`, `excluded_global`, and `excluded_coupled` partition every name
    NOT in `name_map`, each for a different, documented reason (module
    docstring) — never a silent drop."""

    name_map: dict[str, str]
    zone_map: dict[str, str]
    unsafe: frozenset[str]
    excluded_global: frozenset[str]
    excluded_coupled: frozenset[str]
    excluded_contract: frozenset[str]


def _contract_names(game: n.Game) -> frozenset[str]:
    """State names a `uses`d library REQUIRES. These are not game-private: the
    spelling is the interface between the game and the library (decisions.md
    "Family libraries"), and the library text is not part of the rename domain.
    Renaming one would not be a meaning-preserving transform — it would break the
    contract, which is a real semantic change, so the name is excluded rather
    than renamed-and-patched.

    A library's PROVIDED state is interface for the same reason, and needs no
    entry here: it cannot reach the rename domain at all. The domain is built
    from DECLARATIONS the game holds, provided state is declared by the library
    and spliced in during resolve, and this plan is built from the parsed game
    (`_contract_names` reads `game.uses`, which `_apply_uses` empties). A game
    that merely READS a provided name is safe for the same reason — `_rewrite`
    only rewrites names in the map, and an undeclared name never enters it."""
    names: set[str] = set()
    for use in game.uses:
        if use.name in library_names():
            names.update(r.name for r in load_library(use.name).requires)
    return frozenset(names)


def build_rename_plan(game: n.Game) -> RenamePlan:
    zone_names = {z.name for z in game.zones}
    state_names = {
        sd.name for nd in _resolve_walk(game) if isinstance(nd, n.StateBlock) for sd in nd.decls
    }
    overlap = zone_names & state_names
    assert not overlap, (
        f"zone and state-variable namespaces share {sorted(overlap)} — T2's "
        "single flat rename map cannot tell which declaration a NameRef of "
        "that spelling denotes without resolving scope; this backstop has "
        "not fired against the current corpus (rename.py's module docstring)"
    )
    domain = zone_names | state_names
    unsafe = domain & _locally_bound_names(game)

    filename = Path(game.span.source_name).name if game.span is not None else ""
    excluded_global = domain & _GLOBAL_EXCLUSIONS
    # Subtracting the global exclusions keeps the three excluded sets a
    # partition: `hand` is primitive-coupled too (Tichu/Skat/... rows declare
    # it) but is already excluded corpus-wide as the magic name.
    excluded_coupled = (domain & _coupled_names(filename)) - excluded_global
    # Subtracted like the others so the excluded sets stay a partition.
    excluded_contract = (
        (domain & _contract_names(game)) - excluded_global - excluded_coupled
    )

    safe = sorted(
        domain - unsafe - excluded_global - excluded_coupled - excluded_contract
    )

    used = set(_all_string_tokens(game))
    name_map: dict[str, str] = {}
    counter = 0
    for old in safe:
        while True:
            candidate = f"{_PREFIX}{counter}"
            counter += 1
            if candidate not in used:
                used.add(candidate)
                name_map[old] = candidate
                break
    zone_map = {old: new for old, new in name_map.items() if old in zone_names}
    return RenamePlan(
        name_map=name_map,
        zone_map=zone_map,
        unsafe=frozenset(unsafe),
        excluded_global=frozenset(excluded_global),
        excluded_coupled=frozenset(excluded_coupled),
        excluded_contract=frozenset(excluded_contract),
    )


def _rewrite(node: object, name_map: dict[str, str]) -> object:
    if isinstance(node, n.NameRef):
        new = name_map.get(node.name)
        return node if new is None else replace(node, name=new)
    if isinstance(node, (n.ZoneDecl, n.StateDecl)):
        new = name_map.get(node.name)
        if new is not None:
            node = replace(node, name=new)
    elif isinstance(node, n.Winner):
        # `winner: lowest/highest <target>` names its score state variable as
        # a bare string too (the grammar production has no room for a general
        # expression here), not a `NameRef`.
        new = name_map.get(node.target)
        if new is not None:
            node = replace(node, target=new)
    elif isinstance(node, n.Turns):
        # `turns … again <var>` names its go-again state variable as a bare
        # string (the grammar takes a NAME there) — the `Winner.target`
        # class, one construct over.
        if node.again is not None:
            new = name_map.get(node.again)
            if new is not None:
                node = replace(node, again=new)
    elif isinstance(node, n.Round):
        # The climbing/trick forms name their source/play zones as bare
        # strings (`source_zone`/`play_zone`), not a `NameRef` — the one
        # place a zone reference bypasses the expression sublanguage (every
        # other zone reference — `Movement.source/dest`, `CardQuery.source`,
        # `EpistemicOp`'s target — is an `Expr`, so a `NameRef` occurrence).
        sz = None if node.source_zone is None else name_map.get(node.source_zone, node.source_zone)
        pz = None if node.play_zone is None else name_map.get(node.play_zone, node.play_zone)
        if sz != node.source_zone or pz != node.play_zone:
            node = replace(node, source_zone=sz, play_zone=pz)
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value, name_map)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(value: object, name_map: dict[str, str]) -> object:
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item, name_map) for item in value)
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, name_map)
    return value


def alpha_rename(game: n.Game) -> n.Game:
    """The T2 transform proper: `Game -> Game`, matching `pairing.Transform`."""
    plan = build_rename_plan(game)
    return cast(n.Game, _rewrite(game, plan.name_map))


def trace_rename(zone_map: dict[str, str]) -> Callable[[Event], Event]:
    """The trace-level `rename` hook `pairing.compare_traces` wants: labels
    in the TRANSFORMED side's "move"/"reveal" events carry the NEW zone
    spelling (`_label` in `runtime/observe.py`: `name` or `name[key]`); this
    maps them back to the original so the transformed side's trace compares
    byte-for-byte against the untransformed side's."""
    inverse = {new: old for old, new in zone_map.items()}

    def relabel(label: str) -> str:
        if "[" in label:
            base, rest = label.split("[", 1)
            return inverse.get(base, base) + "[" + rest
        return inverse.get(label, label)

    def rename(event: Event) -> Event:
        tag = event[0]
        if tag == "move":
            _, src, src_view, dst, dst_view = event
            return (tag, relabel(src), src_view, relabel(dst), dst_view)
        if tag == "reveal":
            _, label, card = event
            return (tag, relabel(label), card)
        return event

    return rename
