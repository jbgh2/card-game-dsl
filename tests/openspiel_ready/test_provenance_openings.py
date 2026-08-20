"""Every `provenance_opening` is a driving judgment with a CHECKED claim.

`GameSpec.provenance_opening` names moves the provenance walk plays before it
goes greedy, for the game whose greedy line provably never reaches a zone whose
[[arrival-record]] a consumer reads. French Tarot is the case that created the
field: `pass` sorts below every bid, so `legal[0]` throws all 36 hands in and no
card is ever played, and the migration that gave `trick_pile` an AST-visible
consumer (issue #250 PR 5) turned that from a vacuous certificate into a RED
one. The field converts it into a real certificate.

A driving judgment can be wrong in ways the proof it serves cannot see, which
is what this module is for. The proof asks only "did the line reach the zone";
it cannot ask whether the opening was NEEDED, whether it names moves this game
has, or whether it is doing anything at all. Each of those is a cell below.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every registered game's `provenance_opening` is legal where it is
           played, is needed, and is declared only where a provenance domain
           exists to need it -- and every one of those claims FAILS LOUDLY.
domain:    `harness.REGISTERED_GAMES` -- the adapter's own registry, so a newly
           registered game is in-domain the day it registers -- crossed with
           {declares an opening, declares none} (total by construction: the
           field is a tuple, empty or not) and with the two properties a
           declaration can get wrong: it must ENCODE AND BE LEGAL at each of
           its own turns, and it must be NEEDED (`harness.opening_status`'s
           2x2 over needed x declared). The provenance-domain gate is the
           third arm: `GameSpec.all_provenance_zones` empty means the field is
           never consulted at all, so an opening there is dead.
registry:  `harness.REGISTERED_GAMES` for the game axis, resolved to each
           module's real `TestReadiness.spec` the way `test_coverage.py`
           already resolves it (a default-constructed spec would read every
           field as its default and check nothing);
           `GameSpec.all_provenance_zones` for the domain gate, itself derived
           from `ARRIVAL_RECORD_CALLS` + `PRIMITIVE_READS`;
           `cardlang.openspiel.encoding.ActionSpace` for what a move name may
           be, consulted through `encode` rather than re-listed here.
covered:   the grid IS the coverage -- one cell per game in
           `harness.REGISTERED_GAMES` for the opening's legality, one per game
           for the needed/declared square, one per game for the domain gate;
           plus `harness.opening_status`'s own 2x2, and a refusal probe per
           entry in `_PROBED_ARMS` over a synthetic spec, each asserting its
           needle from that table, with their control. That last is a
           completeness claim over a closed set, so it is CHECKED against the
           code rather than asserted in prose: `_PROBED_ARMS` is reconciled
           with the refusal messages `_refusal_messages` reads off
           `harness.opening_actions`, in both directions
           (`test_every_refusal_arm_of_opening_actions_has_a_probe`) -- no
           scraped message is needle-free, and no `_PROBED_ARMS` needle goes
           unused. Those emptiness facts are what the cell establishes.
           Reading them as one probe per refusal ARM of the function is the
           step they do not license -- residual (f).
sampled:   the needed/declared square is measured at ONE seed (the manifest
           head). Whether an opening is needed is a property of the greedy
           line's SHAPE -- which action id sorts first at each turn -- and the
           deal moves neither the action ids nor the sort. Measured rather
           than argued: over the whole manifest French Tarot's first decider
           is P2 with the same five legal ids and the same `legal[0]=78` on
           every seed (2026-08-19). The LEGALITY arm is not sampled at all:
           the provenance proof is the only caller of `opening_actions` in the
           harness (checked, not asserted -- the same scrape as the scoping
           cell) and runs once per manifest seed under the shared
           `ReadinessProofs` parametrization, so a seat or a guard that moved
           with the deal reddens there. The manifest's BREADTH is that shared
           decorator's, pinned for the swap proof by
           `test_coverage.py::test_every_swap_proof_runs_the_seed_manifest`
           and not re-pinned here.
residual:  (a) An opening of length >= 2, and the `provenance_depth` offset it
           crosses with, are implemented and only degenerately executed: no
           spec declares either shape beside the other, and `replay.run` is
           uncached, so each extra opening move is a full re-simulation per
           seed. The probes below drive both multi-move arms on a synthetic
           spec, which is where the cost is one game rather than the manifest.
           R4, this ledger owns the record.
           (b) A LEGAL BUT WRONG opening -- a different move that also reaches
           the zone -- passes every cell here, because every claim this module
           can make about it is true. Guarded by disclosure instead: the
           coverage record carries the MOVES (`harness.render_opening`), so
           which line was certified is citable rather than inferred from a
           count. That the record still carries them is ASSUMED, not checked:
           the caller scrape in
           `test_only_the_provenance_walk_is_given_an_opening` establishes
           that the provenance proof is the only function in `harness.py`
           calling `render_opening`, so a call that moves or vanishes reddens
           -- a rendered value that stops reaching `record(..., opening=...)`
           from inside that proof does not, and by (e) nothing else catches it
           either. Measured, not argued: dropping the `opening=` key while
           leaving the call in the proof's body left this module,
           `test_coverage.py` and `test_partition_record_modes.py` green
           (2026-08-20). R4; this ledger owns the declined case, issue #390
           owns the guard's narrowness.
           (c) The opening-prefixed line is walked by the DSL replay only; the
           adapter-agreement proof walks the plain greedy line, so for a game
           whose greedy line never plays a card the DSL/pyspiel agreement is
           proven over the all-pass line alone. That is the adapter proof's
           own scope rather than this field's, and it is unchanged by the
           field's existence. R4, this ledger owns the record.
           (d) Parameter shapes the field's `tuple[str, str | None]` type
           cannot express (a Card-, Player- or position-valued move parameter,
           or an arity >= 2 move) are refused by strict mypy at the spec site
           rather than by a designed diagnostic. Deliberate: the field drives
           an OPENING, and the moves that open a game are the nullary and
           string-parameterized ones. A recorded constraint, not work -- this
           ledger owns it, per CLAUDE.md's carve-out.
           (e) The provenance record has two shapes -- a vacuous cell carries
           `{seed, zones, vacuous}`, a real one adds `{opening, depth, nodes,
           entries_compared}` -- and `test_partition_record_modes.py` pins the
           record's executor-invariance, not its key sets, so a key dropped
           from one branch reddens nothing. Pre-dates this field and is a
           property of `partition.record`'s free-form `**detail`; R4, this
           ledger owns the record.
           (f) The reconciliation matches a needle to an arm by SUBSTRING and
           guards the site count with `>=`, so a refusal arm added to
           `harness.opening_actions` whose message contains a needle another
           arm already answers reads as probed while no probe drives it.
           Measured, not argued: a fourth arm worded "opening move {move} is
           not legal at P{r.player} — the parameter names no available target"
           left `test_every_refusal_arm_of_opening_actions_has_a_probe` green,
           the needle `is not legal at P` covering two arms at once, at four
           scraped sites against three needles (2026-08-20). A needle added to
           `_PROBED_ARMS` without a probe hides the same way. The scraped arms,
           the `_PROBED_ARMS` needles and the probes did pair off one-to-one
           when that was measured; nothing here holds them paired. R4, issue
           #391.

Born red: the classifier's square was authored against a stub returning
`"covered"` for every cell and run before `opening_status` existed --
"AssertionError: assert 'covered' == 'stale'", the cell whose collapse is the
whole failure class (executed 2026-08-19). The per-game cells' capacity to
fail is the commanded mutation recorded on each.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from pathlib import Path
from typing import Any

import pytest

from .harness import (
    ONE_SEED,
    REGISTERED_GAMES,
    GameSpec,
    opening_actions,
    opening_status,
    provenance_walk,
    render_opening,
)


def _spec(short_name: str) -> GameSpec:
    """The game's REAL spec, importlib-resolved. A default-constructed
    `GameSpec(short, filename)` reads every judgment field as its default and
    would check nothing -- `test_coverage.py` makes the same move for the same
    reason."""
    mod = importlib.import_module(
        ".test_" + short_name.removeprefix("cardlang_"), package=__package__
    )
    spec: GameSpec = mod.TestReadiness.spec
    return spec


_ALL: list[GameSpec] = [_spec(short) for short, _ in REGISTERED_GAMES]


def _params(specs: list[GameSpec]) -> list[Any]:
    return [
        pytest.param(s, id=s.short_name.removeprefix("cardlang_")) for s in specs
    ]


SPECS: list[Any] = _params(_ALL)
# The two arms of the domain gate, DERIVED rather than listed: a game whose
# `all_provenance_zones` is empty never reaches `opening_actions` at all, so the
# needed/declared square is meaningless for it and the gate cell owns it
# instead. Splitting the parametrization rather than skipping inside one keeps
# every cell a cell that runs.
WITH_DOMAIN: list[Any] = _params([s for s in _ALL if s.all_provenance_zones])
WITHOUT_DOMAIN: list[Any] = _params([s for s in _ALL if not s.all_provenance_zones])
SEED = ONE_SEED[0]


@pytest.mark.parametrize("spec", SPECS)
def test_a_declared_opening_is_legal_at_every_one_of_its_turns(spec: GameSpec) -> None:
    """The empty arm asserts emptiness; the declared arm drives the opening and
    lets `opening_actions`' three refusals fire.

    red under (commanded, executed 2026-08-19 and reverted): french-tarot's
    `provenance_opening` set to a second `bid_petite`, illegal once a bid
    stands -- "cardlang_french_tarot: opening move ('bid_petite', None) is not
    legal at P1's turn 1"."""
    actions = opening_actions(spec, SEED)
    assert len(actions) == len(spec.provenance_opening), (
        f"{spec.short_name}: the opening encoded {len(actions)} actions for "
        f"{len(spec.provenance_opening)} declared moves"
    )


@pytest.mark.parametrize("spec", WITH_DOMAIN)
def test_an_opening_is_declared_exactly_where_the_greedy_line_needs_one(
    spec: GameSpec,
) -> None:
    """The needed/declared square, per game. `needed` is MEASURED: the plain
    greedy line is walked with no opening and its compared-entry count read.

    The `stale` direction is the one nothing else in this package covers -- the
    proof stays green over an opening that stopped being necessary, because a
    line that reaches the zone reaches it either way.

    red under (commanded, executed 2026-08-19 and reverted): french-tarot's
    `provenance_opening` emptied -- this cell reads `missing` and fails naming
    the game, alongside the proof's own vacuity guard."""
    zones = spec.all_provenance_zones
    without = provenance_walk(spec, SEED, zones, [])
    status = opening_status(
        needed=without.entries_compared == 0, declared=bool(spec.provenance_opening)
    )
    assert status == ("covered" if spec.provenance_opening else "none"), {
        "stale": (
            f"{spec.short_name} declares `provenance_opening="
            f"{render_opening(spec)}`, but the plain greedy line already "
            f"compares {without.entries_compared} record entries in "
            f"{without.nodes} nodes — the opening has outlived its reason; "
            f"drop it"
        ),
        "missing": (
            f"{spec.short_name}: the plain greedy line reaches "
            f"{zones} never within {without.nodes} nodes, so the provenance "
            f"certificate is vacuous — declare a `provenance_opening` that "
            f"drives the game to a state where the zone fills"
        ),
    }[status]


@pytest.mark.parametrize("spec", WITHOUT_DOMAIN)
def test_an_opening_is_declared_only_where_something_would_consult_it(
    spec: GameSpec,
) -> None:
    """The domain gate. With no provenance domain the proof returns before
    `opening_actions` is ever called, so a declared opening is never encoded,
    never legality-checked, and never recorded — a dead knob, and the one
    state in which every other cell here is silent.

    Since the domain is AST-derived, a DSL edit that drops the last
    Arrival-Record consumer kills the field without touching it, which is
    exactly how this cell goes from impossible to live.

    red under (commanded, executed 2026-08-19 and reverted): the same
    `("bid_petite", None)` opening copied onto `test_bridge.py`'s spec, a game
    with no provenance consumer."""
    assert not spec.provenance_opening, (
        f"{spec.short_name} declares `provenance_opening="
        f"{render_opening(spec)}` but derives no provenance domain, so the "
        f"proof returns before the opening is read — nothing encodes it, "
        f"nothing checks it is legal, and nothing records it"
    )


# Every judgment-carrying `GameSpec` field, classified. The CLASS this module's
# fix belongs to is "a spec field whose value is an authored judgment about one
# game rather than a fact the harness derives" — the fields that can be wrong,
# stale, or unnecessary with no run noticing — and the class ledger claimed its
# members were derived from the dataclass. They were not: the claim was prose
# asserting itself an artifact, which is the very defect this module was added
# to answer, one level up. The reconciliation below performs it.
#
# IDENTITY is not a judgment: the two fields that NAME the game.
_IDENTITY: frozenset[str] = frozenset({"short_name", "filename"})
# Judgment fields with a grid that would fail if the value went stale.
_COVERED: dict[str, str] = {
    "provenance_opening": "this module",
    "conformance_steps": "test_conformance_bounds.py",
    "conformance_verbs_unreached": "test_conformance_bounds.py",
}
# Judgment fields with no staleness grid. Each is consumed by a proof that
# asserts over it, so a value that breaks the proof reddens there; what none of
# them has is a check that the value is still NEEDED or still tight. R4 — no
# designer or info-set consequence, and this ledger owns the record.
_RESIDUAL: frozenset[str] = frozenset(
    {
        "hidden_zone",
        "depth",
        "stock_zone",
        "stock_swap_skip",
        "swap_axis",
        "provenance_depth",
        "adapter_terminal_steps",
    }
)


def test_every_spec_field_is_classified_as_driving_or_not() -> None:
    """The class ledger's `members:` row, DERIVED and reconciled — both
    directions, so neither half can drift.

    A new or renamed judgment field lands UNCLASSIFIED and fails here, instead
    of joining a class whose ledger says it was enumerated. A classification
    naming a field the dataclass no longer has fails too, so a rename cannot
    leave a row pointing at nothing.

    red under, both directions (executed 2026-08-19, reverted): a dummy
    `provenance_dummy: int = 0` added to `GameSpec` — "GameSpec fields no
    classification names: ['provenance_dummy']"; and `swap_axis` dropped from
    `_RESIDUAL` — the same assertion naming `['swap_axis']`."""
    import dataclasses

    declared = {f.name for f in dataclasses.fields(GameSpec)}
    classified = _IDENTITY | set(_COVERED) | _RESIDUAL
    assert not sorted(declared - classified), (
        f"GameSpec fields no classification names: "
        f"{sorted(declared - classified)} — a judgment field with no row is a "
        f"field this ledger's `members:` silently under-reports; add it to "
        f"`_COVERED` with the grid that checks it, to `_RESIDUAL` with why it "
        f"has none, or to `_IDENTITY` if it names the game rather than judging "
        f"it"
    )
    assert not sorted(classified - declared), (
        f"classifications naming no GameSpec field: "
        f"{sorted(classified - declared)} — a row that survived a rename "
        f"points at nothing and reads as covered"
    )


def test_opening_status_covers_the_needed_declared_square() -> None:
    """All four cells of the 2x2, named. A classifier that collapsed `stale`
    into `covered` would let an opening outlive its reason silently — the
    failure class this module exists to remove, and the one the sibling
    conformance pin already refuses for its own declarations.

    Born red against a stub returning `"covered"` for every cell:
    "AssertionError: assert 'covered' == 'stale'"."""
    assert opening_status(needed=True, declared=True) == "covered"
    assert opening_status(needed=False, declared=True) == "stale"
    assert opening_status(needed=True, declared=False) == "missing"
    assert opening_status(needed=False, declared=False) == "none"


def _callers(src: str, callee: str, opening_arity: int = 0) -> dict[str, tuple[int, int]]:
    """Every function in the harness that calls `callee`, mapped to (calls,
    calls passing more than `opening_arity` arguments) — attribution by NEAREST
    ENCLOSING FUNCTION.

    Not a count over the file. The claim is about WHICH proof may drive a line,
    and a count is satisfied by moving the fourth argument to the wrong caller:
    the opening then moves the swap pause instead of the provenance walk, which
    is exactly the regression the cell below is named for, and the count never
    changes."""
    owner: dict[str, list[int]] = {}

    def visit(node: ast.AST, fname: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == callee
            ):
                row = owner.setdefault(fname, [0, 0])
                row[0] += 1
                if len(child.args) + len(child.keywords) > opening_arity:
                    row[1] += 1
            visit(child, fname)

    visit(ast.parse(src), "<module>")
    return {name: (n, k) for name, [n, k] in owner.items()}


def test_only_the_provenance_walk_is_given_an_opening() -> None:
    """The field's scoping, derived from the code rather than asserted in its
    comment. The swap, facts, rng and wash proofs pause at `spec.depth`, whose
    per-game value is reasoned about the greedy line as it stands (French
    Tarot's depth-3 sits inside the still-open first auction, before the
    thrown-in hand's reshuffle), so an opening reaching those call sites would
    silently move every one of those pauses.

    Read off the parsed harness by CALLER, so the answer is which function
    drives an opening rather than how many calls do. An earlier form of this
    cell counted arities and passed while the opening sat on the swap proof —
    the same shape as the thing it guards.

    red under (executed 2026-08-19, reverted): move the fourth argument out of
    `provenance_walk` and onto the swap proof's `_advance` — "the opening is
    driven by ['test_indistinguishability_under_hidden_swap'], not
    ['provenance_walk']". Under the arity-counting form the same plant
    PASSED."""
    src = Path(inspect.getsourcefile(provenance_walk) or "").read_text()
    callers = _callers(src, "_advance", opening_arity=3)
    assert len(callers) > 1, (
        f"the scrape found `_advance` called from {sorted(callers)} — a single "
        f"caller means the walk drifted and this cell proves nothing"
    )
    driving = sorted(name for name, (_, k) in callers.items() if k)
    assert driving == ["provenance_walk"], (
        f"the opening is driven by {driving}, not ['provenance_walk'] — only "
        f"the provenance walk may take one, or a declared opening moves the "
        f"swap/facts/rng/wash pauses too (callers: "
        f"{ {n: k for n, (_, k) in sorted(callers.items())} })"
    )

    # And who may ASK for one. `opening_actions` is what turns the declared
    # moves into a line; a second caller inside the harness would drive an
    # opening somewhere this cell's first half cannot see, because it would
    # not be an `_advance` argument at all.
    askers = sorted(_callers(src, "opening_actions"))
    assert askers == ["test_provenance_is_derivable_from_every_observers_stream"], (
        f"`opening_actions` is called from {askers} inside the harness — only "
        f"the provenance proof may ask for an opening"
    )

    # Residual (b)'s guard, which is DISCLOSURE: a legal-but-wrong opening
    # passes every cell here, and what makes it reviewable is that the citable
    # record names the moves. That guard is one call site, so a change back to
    # a count would silently un-guard the residual — the ledger would still say
    # "guarded by disclosure" while nothing disclosed anything. What it pins is
    # WHOSE call site it is, not where the rendered value goes: the message
    # below says "feeds the provenance record", but a rendered opening that
    # stops reaching `record(..., opening=...)` from inside the proof passes
    # here — ledger residual (b), issue #390.
    assert sorted(_callers(src, "render_opening")) == [
        "test_provenance_is_derivable_from_every_observers_stream"
    ], (
        "`render_opening` no longer feeds the provenance record — residual (b) "
        "is guarded by disclosure alone, so the record must keep naming the "
        "moves it certified"
    )


# --- misuse probes ---------------------------------------------------------
#
# `opening_actions`' refusals fire on no registered spec — the corpus's one
# opening is well-formed — so each gets a synthetic spec that trips exactly it.
# A guard nothing executes is not a guard (`harness.pin_failures`' own rule,
# applied to this field's guards).
#
# ONE source for both halves of that claim: each probe asserts its needle from
# this table, and `test_every_refusal_arm_of_opening_actions_has_a_probe`
# reconciles the table against the refusal sites SCRAPED from the function. The
# ledger used to say "every arm has a probe" in prose. The reconciliation
# reddens on an arm worded unlike every needle in this table; an arm worded LIKE
# one still passes, which is ledger residual (f) and issue #391.
_PROBED_ARMS: dict[str, str] = {
    "does not encode": "a move name the action space cannot encode",
    "is not legal at P": "a move illegal at its own turn",
    "the game ended after": "an opening longer than the line it drives",
}


def _refusal_messages(fn: Any) -> list[str]:
    """Every refusal site in `fn`, as the literal text of its message — `raise`
    and `assert` alike, read off the parsed function rather than listed. The
    f-string holes are dropped and the constant spans kept, which is what a
    needle can match against."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))

    def literal(node: ast.AST | None) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(
                v.value
                for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        return None

    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            msg = literal(node.msg)
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            msg = literal(node.exc.args[0]) if node.exc.args else None
        else:
            continue
        if msg:
            out.append(msg)
    return out


def test_every_refusal_arm_of_opening_actions_has_a_probe() -> None:
    """The `covered:` row's reconciliation, DERIVED — the refusal messages
    scraped from `opening_actions`, the needles read from `_PROBED_ARMS`, and
    the two sets reconciled in both directions: no scraped message is
    needle-free, no `_PROBED_ARMS` needle unused. Both directions match by
    SUBSTRING, so what this establishes is coverage over those two sets and not
    a pairing of probes to refusal ARMS — an arm worded like a needle another
    arm already answers passes (ledger residual (f), issue #391).

    Prose could say this and did. A completeness claim over a closed set that
    no code enumerates is the defect this whole module answers, and the ledger
    is the easiest place in the repo to write one — rigor-shaped prose sitting
    next to real machinery, reading as if it were the machinery.

    red under, both directions (executed 2026-08-19, reverted): a fourth
    refusal added to `opening_actions` (`assert seed >= 0, "a negative seed"`)
    — "refusal arms of `opening_actions` no probe covers: ['a negative
    seed']"; and the encode arm's needle reworded to `"cannot be encoded"`,
    which reddens BOTH complaints at once (the arm is unprobed, the needle
    unused) plus the probe that asserts it. Deleting an arm outright trips the
    site-count guard first — "the scrape found 2 refusal sites in
    `opening_actions` for 3 probes" — which is the scrape defending itself
    rather than the function."""
    sites = _refusal_messages(opening_actions)
    assert len(sites) >= len(_PROBED_ARMS), (
        f"the scrape found {len(sites)} refusal sites in `opening_actions` for "
        f"{len(_PROBED_ARMS)} probes — the scrape has drifted, not the function"
    )
    # BOTH complaints in one assertion, not two: a reworded message makes its
    # arm unprobed AND its needle unused at the same time, and asserting them
    # in sequence let the first shadow the second — so the second had no
    # reachable witness of its own. The sibling's `pin_failures` collects for
    # the same reason.
    unprobed = sorted(m for m in sites if not any(n in m for n in _PROBED_ARMS))
    unused = sorted(n for n in _PROBED_ARMS if not any(n in m for m in sites))
    assert not (unprobed or unused), "; ".join(
        c
        for c in (
            f"refusal arms of `opening_actions` no probe covers: {unprobed} — "
            f"a guard nothing executes is not a guard; add a probe and its "
            f"needle to `_PROBED_ARMS`"
            if unprobed
            else "",
            f"probe needles matching no refusal arm: {unused} — the arm was "
            f"removed or its message reworded, so the probe now asserts a "
            f"string the function never produces"
            if unused
            else "",
        )
        if c
    )


def _probe(*moves: tuple[str, str | None]) -> list[int]:
    return opening_actions(
        GameSpec(
            "cardlang_probe", "french-tarot.cardlang", provenance_opening=moves
        ),
        SEED,
    )


def test_a_well_formed_opening_has_no_complaints() -> None:
    """The control: without it, an `opening_actions` that refused everything
    would pass all three probes below. Two moves, so the multi-move arm the
    corpus does not reach is executed here (ledger residual (a))."""
    assert len(_probe(("bid_petite", None), ("pass", None))) == 2


def test_an_opening_naming_a_move_the_space_cannot_encode_is_refused() -> None:
    """The renamed / mistyped move type, through the action space's own
    channel — but carrying this package's voice, which the bare `KeyError:
    ('bid_nonesuch', None)` did not."""
    with pytest.raises(KeyError) as ei:
        _probe(("bid_nonesuch", None))
    needle = next(n for n in _PROBED_ARMS if "encode" in n)
    assert needle in str(ei.value) and "cardlang_probe" in str(ei.value)


def test_an_opening_move_illegal_at_its_turn_is_refused() -> None:
    """`bid_petite` twice: legal at the opener's turn, guarded off at the
    next seat's once a bid stands."""
    with pytest.raises(AssertionError) as ei:
        _probe(("bid_petite", None), ("bid_petite", None))
    assert next(n for n in _PROBED_ARMS if "legal" in n) in str(ei.value)


def test_an_opening_that_outlives_the_game_is_refused() -> None:
    """The third arm, which had no executed record: an opening longer than the
    line it drives. Four passes throw the hand in and the auction's ring
    closes, so a fifth move has no decision node to be played at.

    French Tarot re-deals rather than ending, so this probe uses the shortest
    line the corpus has: Kuhn Poker, where check-check is a showdown and the
    whole game is two decisions."""
    with pytest.raises(AssertionError) as ei:
        opening_actions(
            GameSpec(
                "cardlang_probe",
                "kuhn-poker.cardlang",
                provenance_opening=(("check", None),) * 3,
            ),
            SEED,
        )
    assert next(n for n in _PROBED_ARMS if "ended" in n) in str(ei.value)
    assert "2 of the 3 opening moves" in str(ei.value)
