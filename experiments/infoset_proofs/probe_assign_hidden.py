"""Which State Variable writes publish what some seat cannot see, per corpus game.

Issue #1041: an assignment is not judged by the Hidden Read Owner Guard
(`AssignStmt.value` is `READ_POSITION_OUTSIDE`) and emits no observation event,
so a value read from a concealed zone, shown at a decision and overwritten
before the seat's next one, is forgotten. This probe measures the corpus for
the fix options.

Static half: the checker's own walk (`resolve._HiddenReads`) with each write
site judged the way a `READ_POSITION_NO_SEAT` position is (`_judge` against
`_NO_SEAT`, the `stdlib.zones.reveals` verdict "every seat must see what the
read needs"). The write sites are `resolve._STATE_WRITE_SITES` plus a phase's
`state` defaults, which are evaluated at phase entry. Each site also records
whether an enclosing statement-level control position (an `if` condition, a
`repeat until`, an `as`, a `turns` clause) reads what some seat cannot see:
the implicit flow, where the value written is public but which value is
written is not.

Dynamic half: seeded uniform lines (`replay.LiveLine`), recording at each
decision the State Variables the deciding seat is shown and which write site
last set each. A forgetting precondition is a value shown to a seat at one of
its decisions and changed, or out of scope, at its next.

What a green here does not prove: the walk covers the write sites the checker
reaches (a library procedure no game runs is not walked); the control flag
follows statement nesting only (not a move type's effect under the round that
offers it, nor a `produce` tag into its `produces:` arm); the dynamic half is
sampled, and a precondition is not a recall failure when the value is
derivable from the seat's log.

Run: python experiments/infoset_proofs/probe_assign_hidden.py [--lines N] [game ...]
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cardlang import resolve as r
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load, run
from cardlang.parse import parse_text
from cardlang.runtime import execute
from cardlang.runtime.evaluate import evaluate
from cardlang.stdlib.zones import ZONE_PROJECTIONS, reveals

ROOT = Path(__file__).resolve().parents[2]
GAMES_DIR = ROOT / "docs" / "games"
WITNESSES = tuple(
    Path(__file__).resolve().parent / "witnesses" / name
    for name in ("state_recall.cardlang", "state_recall_branch.cardlang")
)

SiteKey = tuple[str, int, int]

# The control positions of statements whose bodies run under them: the
# `_CONTROL` rows of `HIDDEN_READ_POSITIONS` that guard a nested body.
_CONTROL_FIELDS: dict[type, tuple[str, ...]] = {
    n.IfStmt: ("cond",),
    n.RepeatUntil: ("until",),
    n.AsBlock: ("player",),
    n.Turns: ("leader", "participants", "until"),
}


@dataclass
class Site:
    """One State Variable write site, as the walk met it."""

    key: SiteKey
    kind: str
    target: str
    indexed: bool
    hidden: set[tuple[str, str, str]] = field(default_factory=set)
    control_hidden: set[tuple[str, str, str]] = field(default_factory=set)
    unjudged: set[str] = field(default_factory=set)


def _key(span: Any) -> SiteKey | None:
    if span is None:
        return None
    return (Path(str(span.source_name)).name, int(span.line), int(span.column))


def _hides_from(walker: r._HiddenReads, read: r.ZoneRead) -> str:
    """Which seats a refused read hides from, in words."""
    decl = walker.zones[read.zone]
    ztype = decl.type_ref.name
    to_others = reveals(ztype, read.need, False)
    to_owner = reveals(ztype, read.need, True)
    if not to_owner:
        return "every seat"
    index = "" if read.index is None else r._spell(read.index)
    if not to_others:
        return f"every seat but the owner of {read.zone}[{index}]" if index else (
            f"every seat but each {read.zone}'s owner"
        )
    return "the owner"


class _Measure(r._HiddenReads):
    """The checker's walk, judging every State Variable write as a position
    where no seat decides, without reporting."""

    def __init__(self, game: n.Game) -> None:
        super().__init__(game, DiagnosticBag())
        self.sites: dict[SiteKey, Site] = {}
        self.control: list[set[tuple[str, str, str]]] = []

    def _refused(self, expr: object, scope: r._ReadScope) -> tuple[
        set[tuple[str, str, str]], set[str]
    ]:
        reads = list(self.reads_of(expr, scope))
        saved = (self.bag, self.verdicts, self._reported, self.told)
        self.bag, self.verdicts, self._reported = DiagnosticBag(), [], set(saved[2])
        try:
            self._judge("a State Variable write", iter(reads), r._NO_SEAT, None, skip_choose=True)
            verdicts = self.verdicts
        finally:
            self.bag, self.verdicts, self._reported, self.told = saved
        refused = {
            (v.read.zone, v.read.need, _hides_from(self, v.read))
            for v in verdicts if not v.accepted
        }
        unjudged = {
            rd.zone for rd in reads
            if rd.choose is None and (
                rd.zone not in self.zones
                or self.zones[rd.zone].type_ref.name not in ZONE_PROJECTIONS
            )
        }
        return refused, unjudged

    def _site(self, key: SiteKey, kind: str, target: str, indexed: bool) -> Site:
        site = self.sites.get(key)
        if site is None:
            site = self.sites[key] = Site(key, kind, target, indexed)
        return site

    def _note(self, site: Site, expr: object, scope: r._ReadScope) -> None:
        refused, unjudged = self._refused(expr, scope)
        site.hidden |= refused
        site.unjudged |= unjudged
        for level in self.control:
            site.control_hidden |= level

    def _stmt(self, stmt: n.Stmt, scope: r._ReadScope, seat: r._Seat) -> r._ReadScope:
        if isinstance(stmt, n.AssignStmt):
            key = _key(stmt.span)
            if key is not None:
                site = self._site(key, "assign", stmt.target.name, stmt.index is not None)
                self._note(site, stmt.value, scope)
                if stmt.index is not None:
                    self._note(site, stmt.index, scope)
        guarded = _CONTROL_FIELDS.get(type(stmt))
        if guarded is None:
            return super()._stmt(stmt, scope, seat)
        level: set[tuple[str, str, str]] = set()
        for name in guarded:
            refused, _ = self._refused(getattr(stmt, name), scope)
            level |= refused
        self.control.append(level)
        try:
            return super()._stmt(stmt, scope, seat)
        finally:
            self.control.pop()

    def _phase(self, phase: n.Phase, scope: r._ReadScope) -> None:
        for item in phase.items:
            if isinstance(item, n.StateBlock):
                for decl in item.decls:
                    key = _key(decl.span)
                    if key is not None:
                        site = self._site(key, "phase state default", decl.name, decl.index is not None)
                        self._note(site, decl.default, r._ACTOR_SCOPE)
        super()._phase(phase, scope)


def static_sites(path: Path) -> tuple[dict[SiteKey, Site], int]:
    """Every write site the walk reaches, and the count of AssignStmt nodes in
    the resolved tree (reached or not)."""
    game = r.resolve(parse_text(path.read_text(), str(path)))
    walker = _Measure(game)
    walker.run()
    every = sum(1 for nd in r._walk(game) if isinstance(nd, n.AssignStmt))
    return walker.sites, every


# --- the dynamic half --------------------------------------------------------


@dataclass
class Dynamic:
    lines: int = 0
    decisions: int = 0
    assigns_before_a_decision: int = 0
    hidden_writes_before_a_decision: int = 0
    tainted_shown: dict[SiteKey, int] = field(default_factory=lambda: defaultdict(int))
    tainted_shown_then_changed: dict[SiteKey, int] = field(default_factory=lambda: defaultdict(int))
    # A tainted value overwritten by a different one before any seat decided:
    # an announcement no decision-time view ever showed.
    transient: dict[SiteKey, int] = field(default_factory=lambda: defaultdict(int))
    assigns: int = 0
    changing_assigns: int = 0
    # Consecutive decisions of one seat between which some shown slot changed.
    own_view_moved: int = 0
    own_decision_pairs: int = 0
    # Consecutive decision nodes (any decider) between which the public state
    # changed: where a per-node state delta would be logged to every seat.
    node_state_moved: int = 0
    terminal_log_events: int = 0
    errors: list[str] = field(default_factory=list)


Slot = tuple[str, Any]


def _state_reads(
    expr: object, ctx: Any, functions: dict[str, n.FunctionDef], seen: frozenset[str] = frozenset()
) -> set[Slot | tuple[str, str]]:
    """The State Variable slots `expr` reads: `(name, key)` where a subscript's
    key evaluates, `(name, "*")` for the whole variable otherwise, a designer
    function's body included. A Primitive's own state reads are not followed."""
    slots: set[Slot | tuple[str, str]] = set()
    keyed: set[int] = set()
    for nd in r._walk(expr):
        if (
            isinstance(nd, n.Subscript) and isinstance(nd.obj, n.NameRef)
            and nd.obj.ref_kind == "state_var" and not seen
        ):
            try:
                slots.add((nd.obj.name, evaluate(nd.index, ctx)))
                keyed.add(id(nd.obj))
            except Exception:
                pass
        if isinstance(nd, n.NameRef) and nd.ref_kind == "state_var" and id(nd) not in keyed:
            slots.add((nd.name, "*"))
        if isinstance(nd, n.Call) and nd.func in functions and nd.func not in seen:
            slots |= _state_reads(functions[nd.func].body, ctx, functions, seen | {nd.func})
    return slots


def _slot_value(ctx: Any, slot: Slot) -> str:
    name, key = slot
    value = ctx.rs.get(name)
    return repr(value if key is None else value.get(key))


def dynamic(path: Path, hidden: set[SiteKey], lines: int) -> Dynamic:
    """Seeded uniform lines with a taint over State Variable slots: a slot is
    tainted by a hidden-reading write site when that site wrote it, or wrote a
    slot its value was computed from (`+=`/`-=` keep the slot's own taint)."""
    out = Dynamic()
    game, _ = load(str(path))
    players = game.players.count
    functions = {f.name: f for f in game.functions}
    taint: dict[Slot, frozenset[SiteKey]] = {}
    pending = {"assign": 0, "hidden": 0}
    unshown: set[Slot] = set()
    original = execute._assign

    def taint_of(slot: Slot | tuple[str, str]) -> frozenset[SiteKey]:
        name, key = slot
        if key == "*":
            return frozenset().union(*(t for (nm, _), t in taint.items() if nm == name))
        return taint.get((name, key), frozenset())

    def tracked(stmt: n.AssignStmt, ctx: Any) -> None:
        key = _key(stmt.span)
        slot: Slot = (
            stmt.target.name, None if stmt.index is None else evaluate(stmt.index, ctx)
        )
        flows: frozenset[SiteKey] = frozenset().union(
            *(taint_of(s) for s in _state_reads(stmt.value, ctx, functions))
        )
        if stmt.op != ":=":
            flows |= taint.get(slot, frozenset())
        if key in hidden:
            flows |= {key}
            pending["hidden"] += 1
        before = _slot_value(ctx, slot)
        original(stmt, ctx)
        after = _slot_value(ctx, slot)
        out.assigns += 1
        if after != before:
            out.changing_assigns += 1
            old = taint.get(slot, frozenset())
            if slot in unshown:
                # The old value's taint not carried into the new one is lost.
                for site in old - flows:
                    out.transient[site] += 1
        taint[slot] = flows
        if flows:
            unshown.add(slot)
        else:
            unshown.discard(slot)
        pending["assign"] += 1

    execute._assign = tracked
    try:
        for line in range(lines):
            taint.clear()
            unshown.clear()
            last: dict[int, dict[Slot, tuple[str, frozenset[SiteKey]]]] = {}
            node: list[tuple[tuple[str, Any], ...]] = []
            rnd = random.Random(f"{path.name}:{line}")

            def policy(view: SeatView, legal: Sequence[int]) -> int:
                out.decisions += 1
                out.assigns_before_a_decision += pending["assign"]
                out.hidden_writes_before_a_decision += pending["hidden"]
                pending["assign"] = pending["hidden"] = 0
                unshown.clear()
                shown: dict[Slot, tuple[str, frozenset[SiteKey]]] = {}
                for name, value in view.state:
                    items = value.items() if isinstance(value, Mapping) else [(None, value)]
                    for k, v in items:
                        t = taint.get((name, k), frozenset())
                        shown[(name, k)] = (repr(v), t)
                        for site in t:
                            out.tainted_shown[site] += 1
                public = tuple((nm, repr(v)) for nm, v in view.state)
                if node and node[0] != public:
                    out.node_state_moved += 1
                node[:] = [public]
                before = last.get(view.player)
                if before is not None:
                    out.own_decision_pairs += 1
                    if {k: v for k, (v, _) in before.items()} != {k: v for k, (v, _) in shown.items()}:
                        out.own_view_moved += 1
                    for slot, (value, t) in before.items():
                        now = shown.get(slot)
                        if t and (now is None or now[0] != value):
                            for site in t:
                                out.tainted_shown_then_changed[site] += 1
                last[view.player] = shown
                return rnd.choice(legal)

            try:
                end = LiveLine(str(path), rnd.randrange(4096)).play(
                    {p: policy for p in range(players)}
                )
                out.terminal_log_events += sum(len(v.obs_log) for v in end.views.values())
                out.lines += 1
            except Exception as exc:  # a line the engine refuses is reported, not hidden
                out.errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
            pending["assign"] = pending["hidden"] = 0
    finally:
        execute._assign = original
    return out


def first_decision_writes(path: Path, hidden: set[SiteKey]) -> tuple[int, int]:
    """Assignments, and hidden-reading ones, executed before seed 0's first
    decision: the position `tests/golden/infostate_format.json` pins."""
    counts = [0, 0]
    original = execute._assign

    def counted(stmt: n.AssignStmt, ctx: Any) -> None:
        original(stmt, ctx)
        counts[0] += 1
        if _key(stmt.span) in hidden:
            counts[1] += 1

    execute._assign = counted
    try:
        run(str(path), 0, ())
    finally:
        execute._assign = original
    return counts[0], counts[1]


def dyn_players(path: Path) -> int:
    return load(str(path))[0].players.count


def _games(names: list[str]) -> Iterator[Path]:
    if names:
        for name in names:
            yield Path(name) if name.endswith(".cardlang") else GAMES_DIR / f"{name}.cardlang"
        return
    yield from WITNESSES
    for filename in sorted(GAMES.values()):
        yield GAMES_DIR / filename


def _fmt(items: set[tuple[str, str, str]]) -> str:
    return "; ".join(f"{z} ({need}) hidden from {who}" for z, need, who in sorted(items))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=6)
    ap.add_argument("games", nargs="*")
    args = ap.parse_args()
    registered = set(GAMES.values())
    unregistered = sorted(p.name for p in GAMES_DIR.glob("*.cardlang") if p.name not in registered)
    if unregistered and not args.games:
        print(f"NOT REGISTERED (not measured): {', '.join(unregistered)}")
    for path in _games(args.games):
        try:
            sites, every = static_sites(path)
        except DiagnosticError as exc:
            print(f"== {path.name}: REFUSED BY THE CHECKER: {str(exc)[:200]}")
            continue
        assigns = [s for s in sites.values() if s.kind == "assign"]
        explicit = {k for k, s in sites.items() if s.hidden}
        implicit = {k for k, s in sites.items() if s.control_hidden and not s.hidden}
        by_target: dict[str, int] = defaultdict(int)
        for s in sites.values():
            by_target[s.target] += 1
        dyn = dynamic(path, explicit | implicit, args.lines)
        first_all, first_hidden = first_decision_writes(path, explicit)
        print(
            f"== {path.stem}: assign nodes {every}, assign sites reached {len(assigns)}, "
            f"explicit-hidden sites {len(explicit)}, implicit-hidden sites {len(implicit)} | "
            f"lines {dyn.lines}/{args.lines}, decisions {dyn.decisions}, "
            f"assigns executed before a decision {dyn.assigns_before_a_decision}, "
            f"hidden-site writes before a decision {dyn.hidden_writes_before_a_decision} | "
            f"before seed 0's first decision: assigns {first_all}, explicit-hidden {first_hidden}"
        )
        print(
            f"   volume: assigns {dyn.assigns}, value-changing {dyn.changing_assigns}, "
            f"terminal log events (all seats) {dyn.terminal_log_events}; own-decision pairs "
            f"{dyn.own_decision_pairs}, with a shown state change {dyn.own_view_moved}; "
            f"decision nodes after a state change {dyn.node_state_moved} (x{dyn_players(path)} seats)"
        )
        for err in dyn.errors[:2]:
            print(f"   line error: {err}")
        for k in sorted(explicit | implicit):
            s = sites[k]
            tag = "EXPLICIT" if s.hidden else "IMPLICIT"
            writers = by_target[s.target]
            shown = dyn.tainted_shown.get(k, 0)
            changed = dyn.tainted_shown_then_changed.get(k, 0)
            print(
                f"   {tag} {s.kind} {k[0]}:{k[1]}:{k[2]} `{s.target}`"
                f"{'[]' if s.indexed else ''} (write sites for it: {writers}; "
                f"tainted slot shown {shown}, then changed {changed}; "
                f"transient {dyn.transient.get(k, 0)})"
            )
            if s.hidden:
                print(f"      value reads: {_fmt(s.hidden)}")
            if s.control_hidden:
                print(f"      under control reading: {_fmt(s.control_hidden)}")
        for s in sites.values():
            if s.unjudged:
                print(f"   UNJUDGED zone type at {s.key}: {sorted(s.unjudged)}")


if __name__ == "__main__":
    main()
