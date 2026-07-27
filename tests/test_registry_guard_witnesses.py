"""Every registry-reconciliation guard can be seen to fire.

`docs/decisions.md`, "Allow-list, never deny-list" names the remedy for a
consumer that can only implement ONE row of a closed domain: pin the hard-coded
row against the registry's derived view, so widening the registry fails by name
here rather than silently giving the new member the implemented row's
behaviour. The repo practises it in two places, and
`tests/test_role_comparison_pin.py` calls the executor one "the remedy
practised correctly exactly once".

Neither had a witness, and the reason is structural rather than an oversight:
**both conjuncts are tautologically true against today's registry**, and no
test widens the registry. Deleting `SIMULTANEOUS_ROLES == {"player"}` from that
`and` leaves an expression that evaluates identically on every input any test
can construct. That is not "the suite happens not to catch it" — it is
*provably* unobservable, so running the suite is evidence of nothing either
way. Both were born-green pins with no reddening mutation, the class
`docs/decisions.md` "Closed-domain completeness" and the
`surface-totality-audit` skill require to carry one.

The unit is the CONJUNCT, not the guard
---------------------------------------
Witnessing "the assert fires" is not the property. Widening the registry
reddens `SIMULTANEOUS_ROLES == {"player"}` and short-circuits before
`stmt.role == "player"` is ever evaluated — so a guard-level witness leaves the
second conjunct exactly as unobservable as it was, while reporting the guard as
covered. The domain is therefore every conjunct of every reconciliation guard,
derived by walking the `and` apart, and each conjunct names the witness that
makes it fire alone.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      resolve walls a declared role against the registry before the
              runtime sees it, so a guard here is a backstop against registry
              drift, never against a game description.
Establishes:  every conjunct of every registry-reconciliation guard in
              `cardlang/` has a named witness that makes it fire; a new guard,
              or a new conjunct in an existing one, fails until it has one.
Now illegal:  a reconciliation guard whose capacity to fire is unproven; a
              registry-referencing guard in a shape the census cannot classify.

Completeness ledger
--------------------
property:   every conjunct of every registry-reconciliation guard in
            `cardlang/` is proven to fire, by a witness that widens the
            registry (or reaches the guard with an out-of-row value) and
            requires the guard's own message back.
domain:     DERIVED, not the two sites the issue named. The vocabulary is
            every module-level ALL-CAPS constant defined anywhere in
            `cardlang/` — completeness by superset, so a registry
            that is not the role table is in scope the day it exists. A guard
            is an `assert`, or an `if` whose body raises, whose test compares
            one of those constants against a LITERAL collection ANYWHERE inside
            it — at any depth, so a comparison parenthesised into a nested
            group still qualifies its guard. Both operand positions, any
            operator, and the constant may be reached as a bare name or through
            its module (`n.ROUND_ORDER_MODES`). The cells are the guard's
            `and`-conjuncts, flattened RECURSIVELY; `or` and `not` are one cell
            each, because neither side of a disjunction has a witness that
            fires it alone. A cell is identified by `(module, enclosing
            function, conjunct text)` — never by line number, which is unique
            but rewritten by every edit above it — and a genuine collision of
            that key is refused rather than resolved.
registry:   `_registry_constants()` derives the vocabulary from
            `cardlang/**/*.py` by AST; `_reconciliation_conjuncts()` derives
            the cells from it. `_WITNESSES` maps cell to witness.
covered:    the grid — `test_every_conjunct_has_a_witness`, parametrized over
            the DERIVED conjuncts, one row each. That parametrization is born
            under #150's wall: were the walk to match nothing, collection now
            fails rather than reporting a skip, which is the sequencing #143
            ordered these two issues for. The classifier itself is pinned
            against a synthetic module carrying every shape it must accept and
            every near-miss it must reject
            (`test_the_census_classifies_each_shape`), so the derived class is
            a claim about the repo rather than about this walk. The band the literal-collection predicate excludes is walled
            as a per-module multiset
            (`test_registry_guards_outside_the_literal_shape_are_walled`)
            rather than left silent. The witness key's own assumption — that
            it names one site — is walled by
            `test_no_two_cells_share_a_witness_key`, since a collision is
            silent in the worst way: the second site inherits the first's
            witness and goes green untested. The witnesses themselves are the
            three `test_widening_*` / `test_a_non_player_*` tests below.
sampled:    none. Every derived conjunct is an executed row.
residual:   THREE:
            (1) the INVERSE class — code implementing one row of a closed
            domain that pins itself against nothing — is not covered. It is
            not #149's class (there is no guard to witness), it is unbounded
            without its own framing check, and the census cannot see it: a
            missing guard has no syntax. The one member found while deriving
            this class is `runtime/mechanics.py`'s round-order dispatch, filed
            as issue #165 (R3) rather than fixed here.
            (2) a witness proves a conjunct CAN fire; it cannot prove the
            message names the right remedy, which is prose. Each witness
            asserts on the message text, so a reworded message that stops
            naming the registry reddens — the class of the reason is not
            machine-checked. R4, this ledger owns the record.
            (3) a reconciliation guard written with no literal collection at
            all (`assert set(VIEW) == set(_LOCAL_COPY)`) is outside the
            predicate and lands in the walled band instead, where it is
            authorized by hand rather than witnessed. R4, this ledger owns the
            record.
"""

from __future__ import annotations

import ast
import pathlib
import random
import subprocess
import sys
from dataclasses import replace

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime import execute
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating

_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "cardlang"


def _registry_constants(root: pathlib.Path = _PACKAGE) -> frozenset[str]:
    """Every module-level ALL-CAPS constant defined under `root`.

    Deliberately a SUPERSET of "registry view": narrowing it to
    collection-valued constants would need a judgement per constant, and the
    judgement that matters is made below by the literal-collection predicate.
    Completeness by superset, never by judgement — a stdlib registry or an AST
    union's mode set is in the vocabulary the day it lands, with nobody
    deciding it belongs."""
    out: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            out |= {
                t.id
                for t in targets
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 2
            }
    return frozenset(out)


def _is_literal_collection(node: ast.AST) -> bool:
    """A set/list/tuple/dict displayed literally, or `frozenset({...})`.

    This is the discriminator between the two shapes a registry can appear in.
    A guard that compares the view against a LITERAL is reconciling a
    hard-coded row against the table (`ZONE_INDEX_ROLES == {"player","team"}`);
    a guard that compares it against a VARIABLE is validating input
    (`decl.index not in ZONE_INDEX_ROLES`) and widens correctly with the table
    on its own, so it has no row to witness."""
    if isinstance(node, ast.Set | ast.List | ast.Tuple | ast.Dict):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("frozenset", "set", "tuple")
        and bool(node.args)
        and _is_literal_collection(node.args[0])
    )


def _referenced_constants(node: ast.AST, vocab: frozenset[str]) -> set[str]:
    """Registry constants named in `node`, as a bare name or through a module.

    `n.ROUND_ORDER_MODES` is the same constant as `ROUND_ORDER_MODES`; matching
    only the bare name would drop every guard in a module that imports its
    registry wholesale."""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in vocab:
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute) and sub.attr in vocab:
            out.add(sub.attr)
    return out


def _guard_tests(
    node: ast.AST, function: str = "<module>"
) -> list[tuple[str, ast.expr]]:
    """`(enclosing function, condition)` for every `assert` and raising `if`.

    Both statement shapes, because the currency is not the point — a
    reconciliation guard written as `if VIEW != {...}: raise` is the same guard.
    `orelse` is excluded: a raise in the else branch is not guarded by this test.

    Descended recursively rather than by `ast.walk`, so the enclosing function
    is the INNERMOST one. `ast.walk` is breadth-first, so a nested definition
    would be attributed to its outer function — which would then key two
    distinct sites the same way."""
    out: list[tuple[str, ast.expr]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            out += _guard_tests(child, child.name)
            continue
        if isinstance(child, ast.Assert) or (
            isinstance(child, ast.If)
            and any(isinstance(s, ast.Raise) for b in child.body for s in ast.walk(b))
        ):
            out.append((function, child.test))
        out += _guard_tests(child, function)
    return out


def _conjuncts(test: ast.expr) -> list[ast.expr]:
    """A guard's `and`-operands, flattened through nesting.

    RECURSIVE, because `(A and B) and C` is a nested `BoolOp` — Python only
    flattens `A and B and C` written without parentheses. Splitting one level
    would return `A and B` as a single cell, so the conjunct this module exists
    to witness would ride inside another cell's witness.

    `or` and `not` are deliberately NOT split: an `assert A or B` fires only
    when both sides are false, so neither side has a witness that fires it
    alone, and one cell is the honest unit. Same for a negation, whose operands
    are disjunctive after De Morgan."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return [part for value in test.values for part in _conjuncts(value)]
    return [test]


def _reconciles(test: ast.expr, vocab: frozenset[str]) -> bool:
    """Does this guard compare a registry constant against a literal collection?

    Searched at ANY depth in the test, not across its top-level conjuncts: the
    qualifying comparison can sit inside a parenthesised group, a negation or a
    call, and a guard that qualifies only deeper down is exactly the one that
    would otherwise escape the census entirely rather than merely be split
    coarsely."""
    return any(
        isinstance(node, ast.Compare)
        and _referenced_constants(node, vocab)
        and any(
            _is_literal_collection(side)
            for side in (node.left, *node.comparators)
        )
        for node in ast.walk(test)
    )


def _reconciliation_conjuncts(
    root: pathlib.Path = _PACKAGE,
) -> list[tuple[str, str, int, str]]:
    """Every cell: `(module, enclosing function, line, conjunct source)`.

    A guard qualifies when its test compares a registry constant against a
    literal collection anywhere inside it; every conjunct of that guard is then
    a cell, including the ones that name no registry. That is deliberate: the
    sibling conjunct is the one #149 proves is unobservable, and scoping the
    domain to conjuncts that mention a registry would drop exactly it.

    The enclosing function rides in the cell because the witness map is keyed by
    SITE, and conjunct text alone does not identify one: two guards in the same
    module can carry identical text, and the second would then inherit the
    first's witness while no test ever reaches it."""
    cells: list[tuple[str, str, int, str]] = []
    vocab = _registry_constants(root)
    for path in sorted(root.rglob("*.py")):
        module = str(path.relative_to(root))
        for function, test in _guard_tests(ast.parse(path.read_text())):
            if not _reconciles(test, vocab):
                continue
            for part in _conjuncts(test):
                cells.append((module, function, part.lineno, ast.unparse(part)))
    return cells


def _registry_guards_outside_the_shape(
    root: pathlib.Path = _PACKAGE,
) -> dict[str, list[str]]:
    """Registry-referencing guards the literal-collection predicate excludes.

    The predicate is a PROXY for "this guard reconciles a hard-coded row", and
    a proxy errs both ways. This is the band it excludes — walled as a
    per-module multiset rather than left silent, so a reconciliation written in
    a shape the predicate misses forces a look instead of passing unnoticed."""
    out: dict[str, list[str]] = {}
    vocab = _registry_constants(root)
    for path in sorted(root.rglob("*.py")):
        module = str(path.relative_to(root))
        for _function, test in _guard_tests(ast.parse(path.read_text())):
            if not _referenced_constants(test, vocab):
                continue
            if _reconciles(test, vocab):
                continue
            out.setdefault(module, []).append(ast.unparse(test)[:70])
    return {k: sorted(v) for k, v in sorted(out.items())}


# Every cell, and the witness that makes it fire ALONE.
_WITNESSES: dict[tuple[str, str, str], str] = {
    (
        "resolve.py",
        "<module>",
        "ZONE_INDEX_ROLES == {'player', 'team'}",
    ): "test_widening_zone_index_roles_fails_resolve_at_import",
    (
        "runtime/execute.py",
        "_each_simultaneous",
        "SIMULTANEOUS_ROLES == {'player'}",
    ): "test_widening_simultaneous_roles_fails_the_executor",
    (
        "runtime/execute.py",
        "_each_simultaneous",
        "stmt.role == 'player'",
    ): "test_a_non_player_simultaneous_block_fails_the_executor",
}


_CELLS = _reconciliation_conjuncts()


@pytest.mark.parametrize(
    ("module", "function", "line", "source"),
    _CELLS,
    ids=[f"{m}:{fn}:{ln}" for m, fn, ln, _ in _CELLS],
)
def test_every_conjunct_has_a_witness(
    module: str, function: str, line: int, source: str
) -> None:
    """Each conjunct of each reconciliation guard names a test that fires it.

    Parametrized over the DERIVED cells, so a new guard — or a new conjunct
    grafted onto an existing one — arrives as a red row rather than as silence.
    Born under #150's wall: a walk that matched nothing would once have been a
    skip and a green suite; it is now a collection error."""
    witness = _WITNESSES.get((module, function, source))
    assert witness is not None, (
        f"{module}:{line} ({function}) — conjunct `{source}` has no witness. It "
        "pins a hard-coded row against a registry, so it can only be seen to "
        "work by widening that registry (or reaching the guard with an "
        "out-of-row value) and requiring the guard's message back. Add the test "
        "and map it here; a guard nobody has watched fire is a claim, not a wall."
    )
    assert witness in globals(), (
        f"{module}:{line} — witness {witness!r} is named here but not defined "
        "in this module."
    )


def test_no_two_cells_share_a_witness_key() -> None:
    """A key must identify one SITE, and the site key is a proxy.

    `(module, function, conjunct text)` distinguishes every cell today, but two
    guards carrying identical text inside one function would collide — and a
    collision is silent in the worst way: the second site inherits the first's
    witness and its census row goes green with no test ever reaching it. So the
    ambiguity is refused rather than resolved by a rule nobody would remember.
    A line number would be unique but not stable; every edit above a guard
    would rewrite the map.

    red under: duplicate any guard inside its own function."""
    keys = [(m, fn, src) for m, fn, _, src in _CELLS]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    assert not duplicates, (
        f"two guard sites share the witness key {duplicates} — the map cannot "
        "tell them apart, so one would inherit the other's witness. Give them "
        "distinguishable conjunct text, or key the map by something narrower."
    )


# ---------------------------------------------------------------------------
# The witnesses.
# ---------------------------------------------------------------------------

_MINI = """
game Mini {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase p {
    each player simultaneously:
      transfer chosen 1 cards
        from hand[player]
        to   hand[player offset_by left]
  }
  winner: highest score
}
"""


def _unused_chooser(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("the guard fires before any decision is reached")


def _simultaneous_stmt_and_ctx() -> tuple[n.EachSimultaneous, Ctx]:
    """A REAL `each player simultaneously:` statement, checker-approved.

    Built through the front end rather than by hand: a hand-assembled node
    could satisfy the guard for reasons the real one does not, and the point of
    a witness is that the guard fires on the thing that actually reaches it."""
    game = check_dsl(_MINI, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.EachSimultaneous)
    rs = RuntimeState(Seating(2), ZoneStore(game.zones, (0, 1)), random.Random(0))
    return stmt, Ctx(rs=rs, chooser=_unused_chooser).acting_as(0)


def test_widening_simultaneous_roles_fails_the_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conjunct 1: the executor implements the player row, and says so when the
    registry grows a second simultaneous domain.

    This is the mutation that was impossible to observe before: today's
    `SIMULTANEOUS_ROLES` IS `{"player"}`, so the conjunct is tautologically
    true and deleting it changes nothing any test could see.

    red under: delete `SIMULTANEOUS_ROLES == {"player"} and` from
    `runtime/execute.py::_each_simultaneous` — the widened registry then walks
    straight into the player loop."""
    stmt, ctx = _simultaneous_stmt_and_ctx()
    monkeypatch.setattr(
        execute, "SIMULTANEOUS_ROLES", frozenset({"player", "team"})
    )
    with pytest.raises(AssertionError) as excinfo:
        execute._each_simultaneous(stmt, ctx)
    message = str(excinfo.value)
    assert "implements the player row only" in message, message
    assert "['player', 'team']" in message, message


def test_a_non_player_simultaneous_block_fails_the_executor() -> None:
    """Conjunct 2: the SAME guard, reached the other way — registry untouched,
    the block naming a role the executor does not implement.

    Widening the registry short-circuits at conjunct 1 and never evaluates this
    one, so a guard-level witness would report the guard covered while leaving
    this conjunct exactly as unobservable as it was. Resolve walls a non-player
    simultaneous block, which is why the statement is rebuilt here rather than
    written in the DSL: the guard is a backstop against a construction path
    that bypasses resolve, and that is the path being simulated.

    red under: delete `and stmt.role == "player"` from the guard — the block
    then iterates seats while binding the name `team` to each of them."""
    stmt, ctx = _simultaneous_stmt_and_ctx()
    with pytest.raises(AssertionError) as excinfo:
        execute._each_simultaneous(replace(stmt, role="team"), ctx)
    message = str(excinfo.value)
    assert "implements the player row only" in message, message
    assert "names 'team'" in message, message


def test_widening_zone_index_roles_fails_resolve_at_import() -> None:
    """resolve's guard is MODULE-level, so the witness is an import.

    In a subprocess, and importing rather than reloading: the guard runs once,
    at first import, and this suite has already imported resolve by the time
    any test runs. A reload in-process would also rebind every class resolve
    exports, which other modules hold by identity.

    red under: delete the `assert ZONE_INDEX_ROLES == {...}` from
    `resolve.py` — the widened registry then reaches the empty-domain walls,
    which implement the `team` row only."""
    script = (
        "import cardlang.domains as d\n"
        "d.ZONE_INDEX_ROLES = frozenset({'player', 'team', 'strain'})\n"
        "try:\n"
        "    import cardlang.resolve  # noqa: F401\n"
        "except AssertionError as exc:\n"
        "    print('GUARD-FIRED', exc)\n"
        "else:\n"
        "    print('NO-GUARD')\n"
    )
    proc = subprocess.run(  # noqa: PLW1510 -- the stdout assert below carries proc.stderr
        [sys.executable, "-c", script],
        cwd=_PACKAGE.parent,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("GUARD-FIRED"), (
        "widening ZONE_INDEX_ROLES did not fail resolve's import — its "
        f"empty-domain walls implement the `team` row only.\n{proc.stdout}{proc.stderr}"
    )
    assert "empty-domain walls" in proc.stdout, proc.stdout


# The registry-referencing guards the literal-collection predicate excludes.
# Authorized one by one: each either validates a value AGAINST the registry
# (widening the table widens the guard, so there is no hard-coded row to
# witness) or reconciles two derived views against each other, which likewise
# has no literal to go stale. Walled rather than trusted, because the predicate
# is a proxy: a reconciliation written without a literal collection lands here,
# and must be looked at rather than pass unnoticed.
_GUARDS_OUTSIDE_THE_SHAPE: dict[str, list[str]] = {
    "libraries.py": ["not _LIBRARIES_DIR.is_dir()"],
    "openspiel/encoding.py": ["not 0 <= action < NUM_DISTINCT_ACTIONS"],
    "openspiel/replay.py": ["game.winner.rank_dir not in RANK_DIR_TO_SIGN"],
    "parse.py": ["direction not in RANK_DIR_TO_AGG"],
    "runtime/driver.py": ["game.winner.rank_dir not in RANK_DIR_TO_PICK"],
    "runtime/execute.py": ["len(pool) > _JOINT_ENUMERATION_BOUND"],
    # The one latent deny-list the census surfaced: the dispatch implements
    # `priority` and defaults every other mode to ring. Excluded from the class
    # correctly (it pins itself against nothing, so there is no guard to
    # witness) and filed as issue #165.
    "runtime/mechanics.py": ["self.stmt.order_mode == n.ROUND_ORDER_PRIORITY"],
    "runtime/reads.py": ["len(_BY_KEY) == len(PRIMITIVE_READS)"],
    "runtime/state.py": [
        "decl.index not in ZONE_INDEX_ROLES and decl.index not in positions"
    ],
    "runtime/tichu.py": ["index < _BASE_PAIRSEQ"],
    "stdlib/boards.py": ["set(_GRID_DIRECTION_OFFSETS) != set(dirs)"],
}


def test_registry_guards_outside_the_literal_shape_are_walled() -> None:
    """The band the predicate excludes is authorized, not assumed.

    This is also what makes the derived parametrization above non-vacuous from
    a second direction: an empty derivation here fails against a nonempty
    baseline and names what went missing.

    red under: rewrite any guard above to compare its registry against a
    literal collection (`runtime/state.py`'s membership test is the clearest) —
    it leaves this band and arrives as a witness-less cell in the grid, so both
    this wall and the grid redden together.

    Pointing `_PACKAGE` at a directory that does not exist does NOT reach this
    test: the cell axis empties first and #150's wall stops collection outright.
    That is the layering working, not a gap — recorded so a reader does not
    mistake the missing failure here for a missing check."""
    assert _registry_guards_outside_the_shape() == _GUARDS_OUTSIDE_THE_SHAPE


_PROBE = '''
VIEW = frozenset({"a", "b"})
SCALAR = "priority"

def accepted_equality(x):
    assert VIEW == {"a", "b"}, "reconciliation"

def accepted_two_conjuncts(x):
    assert VIEW == {"a"} and x.role == "a", "reconciliation with a sibling"

def accepted_if_raise(x):
    if VIEW != {"a"}:
        raise ValueError("the same guard in the other currency")

def accepted_frozenset_call(x):
    assert VIEW == frozenset({"a"}), "the constructor form"

def accepted_literal_on_the_left(x):
    assert {"a"} == VIEW, "operand order is not the point"

def accepted_nested_and(x):
    assert (VIEW == {"a"} and x.p) and x.q, "parenthesised on the left"

def accepted_nested_and_on_the_right(x):
    assert x.p and (VIEW == {"b"} and x.q), "parenthesised on the right"

def accepted_or_stays_one_cell(x):
    assert VIEW == {"c"} or x.p, "neither side fires alone"

def accepted_negation_stays_one_cell(x):
    assert not (VIEW == {"d"} and x.p), "disjunctive after De Morgan"

def outer_holding_a_nested_guard(x):
    def inner(y):
        assert VIEW == {"e"}, "attributed to inner, not outer"
    return inner

def rejected_registry_vs_variable(x):
    assert x not in VIEW, "validates input; widens with the table"

def rejected_scalar_dispatch(x):
    if x.mode == SCALAR:
        if x.broken:
            raise ValueError("a nested raise does not make this a guard")

def rejected_no_registry(x):
    assert x.role == {"a"}, "no registry constant on either side"

def rejected_text_only(x):
    return 'VIEW == {"a"}'
'''


def test_the_census_classifies_each_shape(tmp_path: pathlib.Path) -> None:
    """The classifier is the load-bearing artifact, so prove it discriminates.

    "The class is exactly the pinned table" must be a claim about the repo, not
    about this walk. The probe carries a shape for every accepted form and a
    near-miss for every way one could be mistaken for it; the expected list
    below is the assertion, so neither a count here nor a count in the ledger
    can drift away from it.

    Two of the rejections are the real exclusions, written the way the real
    sites are — `runtime/state.py`'s registry-vs-variable membership test, and
    `runtime/mechanics.py`'s scalar dispatch whose `if` body happens to contain
    a raise further down. The second matters: whether `_guard_tests` scans the
    direct body or the whole subtree should not change the verdict, because the
    literal-collection predicate is what excludes it.

    Three of the acceptances answer PR #166 review findings. The parenthesised
    `and` shapes are the severe one: a nested `BoolOp` is not a `Compare`, so
    the earlier one-level split did not merely coarsen the cell — the guard
    failed to qualify at all and left the census entirely. The `or` and
    negation shapes pin the other half of that decision, that only `and` is
    split. The nested-function shape pins attribution to the INNERMOST
    function, which is what keeps two sites from sharing a witness key."""
    (tmp_path / "probe.py").write_text(_PROBE)
    assert [
        (function, source) for _, function, _, source in _reconciliation_conjuncts(tmp_path)
    ] == [
        ("accepted_equality", "VIEW == {'a', 'b'}"),
        ("accepted_two_conjuncts", "VIEW == {'a'}"),
        ("accepted_two_conjuncts", "x.role == 'a'"),
        ("accepted_if_raise", "VIEW != {'a'}"),
        ("accepted_frozenset_call", "VIEW == frozenset({'a'})"),
        ("accepted_literal_on_the_left", "{'a'} == VIEW"),
        ("accepted_nested_and", "VIEW == {'a'}"),
        ("accepted_nested_and", "x.p"),
        ("accepted_nested_and", "x.q"),
        ("accepted_nested_and_on_the_right", "x.p"),
        ("accepted_nested_and_on_the_right", "VIEW == {'b'}"),
        ("accepted_nested_and_on_the_right", "x.q"),
        ("accepted_or_stays_one_cell", "VIEW == {'c'} or x.p"),
        ("accepted_negation_stays_one_cell", "not (VIEW == {'d'} and x.p)"),
        ("inner", "VIEW == {'e'}"),
    ]
