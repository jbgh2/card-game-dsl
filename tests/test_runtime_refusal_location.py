"""A runtime refusal names the sentence that refused.

Every compile diagnostic reaches the game author at `file:line:column`
(`cardlang/diagnostics.py`, `Diagnostic.format`). A refusal raised while the
game is PLAYING reaches them as a message and nothing else, so a designer
whose playout dies bisects their own file to find the line a span already
knows. The two halves of one [[failure-channel]] address the same [[author]]
and only one of them says where.

The location is stamped as the refusal unwinds, innermost first, and two
passes own the class between them. The statement executor owns the sentences:
every statement a game runs passes through it holding its own span, and the
[[context]] it is handed holds the phase. The driver owns what no statement
encloses — a phase's qualifier, a `state { }` default, the `loser:` selection,
a `trick_order { }` row — and carries its own `Contract` saying so.

A gap sits inside each half, and each is an axis below. A statement form that
runs an embedded sentence ITSELF instead of handing it back leaves the
executor's span on the wrapper's line while the refusal happened on the line
inside it; that axis is derived from the `n.Stmt` union rather than read off
the executor, because reading it off the executor would measure the stamp
against itself. A position the driver evaluates and nothing stamps reaches a
designer with no line at all.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a refusal a game sentence can raise renders, to the designer, at
            the smallest span that signifies it — the sentence that refused,
            never the form enclosing it — and names the phase it was running
            in when one was running, and the source zone when a movement is
            what refused. Every
            cell asserts the RENDERED text a caller prints, not that an
            attribute was set: the attribute is reachable from Python and the
            designer is not.
domain:     three axes, each read off its own registry.

            (1) The STATEMENT-FORM axis: the `n.Stmt` union, every member
            classified by how its embedded sentences are run — a leaf, a form
            that hands its body back to the executor, or a form that runs an
            embedded sentence itself (`_LEAF_FORMS`, `_REENTERING_FORMS`,
            `_SELF_RUNNING_FORMS`, pinned equal to the union). The third set
            is the one that needs a stamp of its own, and a new arm joining
            the union fails the partition until it is classified.

            (2) The REFUSAL-CLASS axis: every exception class the engine
            defines, derived by importing the package, each classified as a
            refusal a game sentence can raise or as something else — a
            control-flow signal, or a failure addressed to somebody who is
            not the game author. Deriving the whole set rather than the two
            classes the stamp catches is what makes a new exception class
            arrive as an uncovered cell instead of silently outside.

            (3) The DRIVER-POSITION axis: the game text the DRIVER evaluates
            itself. A phase's `when` guard and `repeat until` condition, a
            `state { }` default, the `loser:` selection and a `trick_order { }`
            row body are expressions no statement encloses, so the executor's
            stamp never reaches them. The axis is derived as the driver's own
            calls to the evaluator, each keyed by the function it sits in and
            the expression it reads, and every one of them goes through the
            module's single stamping helper — so a position added around that
            helper is what the derivation names. The two positions a designer
            can write more than one way — a qualifier's two arms, a `state { }`
            block at either scope — are held to their own registries: the
            parser's qualifier kinds, and the driver's callers of the state
            declarer.

            Crossed with WHERE the position runs: inside a phase, or outside
            every phase. A refusal outside every phase carries its expression
            and names no phase, because none is running, and the grid asserts
            that absence rather than leaving it to inference.

            The axis reads ONE module, and `_EVALUATING_MODULES` is what makes
            that a scope: every module that hands game text to the evaluator
            says what stamps a refusal escaping it, and the others are all
            reached from a statement the executor dispatched — a coarser span
            than the expression, never an absent one.

            The classes quantified over are the ones the ENGINE DEFINES, and
            that is the boundary: a builtin Python exception the engine raises
            is not a class with a position to record, which is the same line
            tests/test_failure_taxonomy.py draws. A defaultless `next()`
            reaching a caller as an empty-message `StopIteration` is that
            other class, and issue #610 owns it.

            A body reached through an INDEX rather than a field — a move
            type's `effect`, a `define`'s body, a procedure spliced by
            `cardlang/expand.py`, anything a family library supplies — carries
            its OWN span, so the sentence a refusal names can sit far from the
            statement that ran it, or in another file. That is the smallest
            span that signifies, and the phase is what ties it back to where
            the game was.
registry:   the statement axis: `typing.get_args(cardlang.ast.nodes.Stmt)`;
            the refusal-class axis: an import walk over the `cardlang`
            package, the same derivation shape
            tests/test_failure_taxonomy.py uses for the taxonomy's own
            domain; the driver positions: the evaluator calls in
            `cardlang/runtime/driver.py`, scraped below, with the qualifier
            kinds read off `cardlang/parse.py` (the only minter of one) and
            the state-declaration scopes off the driver's own callers of
            `_declare_state`; where each class sits in the failure tree:
            tests/test_failure_taxonomy.py; the recorded Author at every
            raise site: tests/test_guard_role_sites.py. Neither of those two
            enumerations is re-copied here.
does not prove:  nothing here says the refusal MESSAGES are the right words
            for a designer — the wording of the runtime's refusals is issue
            #329, and a green here holds whatever text those raise sites
            carry. It equally says nothing about what a caller other than the
            command line DOES with a located refusal: the OpenSpiel adapter
            catches only a chooser suspending a playout, so a refusal crosses
            the pybind boundary out of whichever method triggered it, and the
            span it now carries is read by nobody on that path.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import random
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import get_args

import pytest

import cardlang
from cardlang.ast import nodes as n
from cardlang.cli import main
from cardlang.diagnostics import Diagnostic, Severity, Span
from cardlang.pipeline import check_source
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating

REPO = Path(__file__).parent.parent
FIXTURES = REPO / "tests" / "fixtures"
DRIVER = REPO / "cardlang" / "runtime" / "driver.py"
PARSE = REPO / "cardlang" / "parse.py"
# The driver's one stamping site for the expressions it evaluates itself.
STAMP = "_evaluate_stamped"

# A hand emptied before the statement that asks it for a card. The refusal
# rises through the executor holding the movement's own span.
EMPTY_ZONE = FIXTURES / "empty_zone_choice.cardlang"
# The same movement one line inside `each … simultaneously`, which runs it
# without handing it back — so the executor's span is the wrapper's line.
SIMULTANEOUS = FIXTURES / "simultaneous_empty_zone_choice.cardlang"
# A dealt movement, so the shortage is refused where the cards are taken
# rather than where a player chooses them.
DEAL_DRAINED = FIXTURES / "deal_from_drained_source.cardlang"
# A rule whose `if_impossible:` refuses every card the player holds.
RULE_REFUSES = FIXTURES / "rule_refuses_every_card.cardlang"
# Checks clean, then outruns its declared `max_length` on every seed.
OVERRUNS = FIXTURES / "exceeds_max_length.cardlang"
# The two arms of a phase qualifier, each reading an empty zone's suit.
WHEN_GUARD = FIXTURES / "when_qualifier_empty_zone.cardlang"
REPEAT_CONDITION = FIXTURES / "repeat_until_qualifier_empty_zone.cardlang"
# A `state { }` default whose query matches no seat, at either scope: a
# phase's own block runs inside the phase, the game's before the first one.
PHASE_STATE = FIXTURES / "phase_state_default_no_match.cardlang"
GAME_STATE = FIXTURES / "game_state_default_no_match.cardlang"
# The `loser:` selection, read after the last phase has run.
LOSER_SELECTION = FIXTURES / "loser_selection_no_holder.cardlang"
# A `trick_order { }` row asking for an unranked rank's strength, reached from
# inside a round — so a location taken where the executor dispatched names the
# round rather than the row.
TRICK_ORDER_ROW = FIXTURES / "trick_order_row_unranked.cardlang"


# ---------------------------------------------------------------------------
# Axis 1 — the statement forms, derived from the `n.Stmt` union.
# ---------------------------------------------------------------------------

# Runs no embedded sentence at all: whatever refuses under one of these
# refuses under the statement the executor dispatched, so its own span is
# already the smallest that signifies. The trick and climbing rounds belong
# here and the auction does not — their `apply` moves cards itself, while the
# auction's runs the chosen move type's `effect`.
_LEAF_FORMS: frozenset[str] = frozenset(
    {
        "Transfer",
        "EpistemicOp",
        "RotateStmt",
        "LetStmt",
        "AssignStmt",
        "Produce",
        "ContinueTo",
        "SkipToNextHand",
        "RunStmt",
        "TrickRound",
        "ClimbRound",
    }
)

# Hands its embedded sentences back to the executor, which stamps each in
# turn — so the innermost stamp wins and these need nothing of their own.
# Three of them reach that body through an INDEX rather than a field of their
# own node — a move type's `effect`, a `define`'s body — so the sentence that
# refuses can sit anywhere in the file, or in a library, and the phase is what
# ties it back to where the game was.
_REENTERING_FORMS: frozenset[str] = frozenset(
    {
        "IfStmt",
        "Block",
        "ForEach",
        "AsBlock",
        "Offer",
        "Produces",
        "RepeatUntil",
        "Turns",
        "AuctionRound",
    }
)

# Runs an embedded sentence ITSELF. The executor's stamp names this form's
# line, and the sentence that refused is on another one, so each member is a
# stamping site in its own right.
_SELF_RUNNING_FORMS: frozenset[str] = frozenset({"EachSimultaneous"})


def test_the_statement_axis_is_the_whole_union() -> None:
    """The three sets partition `n.Stmt`, so a new arm cannot join the
    language without being classified here.

    red under: delete `"Turns"` from `_REENTERING_FORMS`."""
    classified = _LEAF_FORMS | _REENTERING_FORMS | _SELF_RUNNING_FORMS
    assert classified == {t.__name__ for t in get_args(n.Stmt)}
    assert len(classified) == len(_LEAF_FORMS) + len(_REENTERING_FORMS) + len(
        _SELF_RUNNING_FORMS
    )


def _arm_dispatch() -> dict[str, set[str]]:
    """Each `n.Stmt` arm of the executor's dispatch, and the names it calls.

    The dispatching function is FOUND — the one whose `match` cases name the
    statement union — rather than called by name, so renaming it or moving
    the match behind a wrapper cannot quietly empty this derivation. Read from
    source, so the sets above are a claim about the executor rather than a
    restatement of themselves.
    """
    tree = ast.parse((REPO / "cardlang" / "runtime" / "execute.py").read_text())
    union = {t.__name__ for t in get_args(n.Stmt)}
    arms: dict[str, set[str]] = {}
    for match in ast.walk(tree):
        if not isinstance(match, ast.Match):
            continue
        found: dict[str, set[str]] = {}
        for case in match.cases:
            names = [
                token.split(".")[-1].removesuffix("()")
                for token in ast.unparse(case.pattern).replace("|", " ").split()
                if token.startswith("n.")
            ]
            calls = {
                ast.unparse(c.func)
                for c in ast.walk(ast.Module(body=case.body, type_ignores=[]))
                if isinstance(c, ast.Call) and isinstance(c.func, (ast.Name, ast.Attribute))
            }
            for name in names:
                found[name] = calls
        if union <= set(found):
            arms = found
    assert union <= set(arms), (
        "no `match` in cardlang/runtime/execute.py covers the `n.Stmt` union — "
        "the statement dispatch moved, and this derivation reads nothing"
    )
    return arms


def _hands_a_sentence_onward(func_name: str, funcs: Mapping[str, ast.FunctionDef]) -> set[str]:
    """Functions this one hands a statement-shaped AST node to."""
    fn = funcs.get(func_name)
    if fn is None:
        return set()
    onward: set[str] = set()
    for call in ast.walk(fn):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
            continue
        callee = funcs.get(call.func.id)
        if callee is None:
            continue
        annotations = [
            ast.unparse(a.annotation) for a in callee.args.args if a.annotation is not None
        ]
        if any(a.startswith(("n.Stmt", "tuple[n.Stmt")) for a in annotations):
            onward.add(call.func.id)
    return onward


def test_the_self_running_set_is_read_off_the_executor() -> None:
    """A form whose handler hands an embedded statement to something OTHER
    than the executor is a self-running form, and the code says which — so
    the set cannot drift from the executor it describes.

    red under: in `cardlang/runtime/execute.py`, make `_each_simultaneous`
    call `run_body((stmt.body,), body_ctx)` instead of `_pass_selection`,
    and this cell reports `EachSimultaneous` as no longer self-running."""
    tree = ast.parse((REPO / "cardlang" / "runtime" / "execute.py").read_text())
    funcs = {f.name: f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    reentry = {"execute", "run_body"}
    derived: set[str] = set()
    for arm, calls in _arm_dispatch().items():
        handler = next((c for c in calls if c in funcs), None)
        if handler is None:
            continue  # the arm is written inline in the match
        onward = _hands_a_sentence_onward(handler, funcs)
        if onward and not (onward & reentry):
            derived.add(arm)
    assert derived == _SELF_RUNNING_FORMS


def test_no_module_runs_game_text_around_the_executor() -> None:
    """A form can reach a body through an INDEX instead of a field — a move
    type's `effect`, a `define`'s body — and the module that fetches it is not
    the executor. Those modules take only the two entry points that stamp, so
    the way AROUND the stamp is closed at the import: reaching the dispatch
    itself, or any helper below it, is what this refuses.

    It says nothing about what a module does with a body once `run_body` has
    handed it back — interpreting an embedded node directly, the way the
    simultaneous pass does, needs the arm's own stamp and is the cell above.

    red under: in `cardlang/runtime/mechanics.py`, import `_dispatch` from the
    executor and call it in place of `run_body`."""
    entry_points = {"execute", "run_body", "REFUSALS", "phase_name", "zone_label"}
    for path in sorted((REPO / "cardlang").rglob("*.py")):
        if path.name == "execute.py":
            continue
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.ImportFrom)
                and node.module == "cardlang.runtime.execute"
            ):
                continue
            taken = {alias.name for alias in node.names}
            assert taken <= entry_points, (
                f"{path.relative_to(REPO)} imports {sorted(taken - entry_points)} "
                f"from the statement executor. Game text runs through `execute` "
                f"or `run_body`, which stamp the sentence a refusal escaped; "
                f"anything else reaches a body around the stamp"
            )


# ---------------------------------------------------------------------------
# Axis 2 — the refusal classes, derived by importing the package.
# ---------------------------------------------------------------------------


@cache
def engine_exception_classes() -> Mapping[str, type[BaseException]]:
    """Every exception class DEFINED in the `cardlang` package, by name.

    The walk's module list is the domain, never `sys.modules`, so a solo run
    and a full-suite run derive the same set. A module needing an absent
    OPTIONAL extra is skipped; a `ModuleNotFoundError` naming something inside
    `cardlang` is a broken import and still propagates.
    """
    found: dict[str, type[BaseException]] = {}
    walked = [
        "cardlang",
        *(i.name for i in pkgutil.walk_packages(cardlang.__path__, prefix="cardlang.")),
    ]
    for mod_name in walked:
        try:
            module = importlib.import_module(mod_name)
        except ModuleNotFoundError as exc:
            if exc.name is not None and not exc.name.startswith("cardlang"):
                continue
            raise
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseException)
                and getattr(obj, "__module__", "").startswith("cardlang")
            ):
                found[obj.__name__] = obj
    return found


# A game sentence can raise these, and a designer is the one who must act.
_REFUSALS: frozenset[str] = frozenset(
    {"GameDescriptionError", "OwnerGuardError", "ShadowGuardError", "IllegalMove"}
)

# Unwinding, not failing: `produce`, `continue to`, `skip to next hand`, and a
# chooser suspending a steppable playout. Locating one would be locating an
# ordinary control transfer.
_SIGNALS: frozenset[str] = frozenset(
    {"_ProduceSignal", "_ContinueTo", "_SkipHand", "ChooserAbort"}
)

# Real failures addressed to somebody other than the game author, so a game
# file's line is not where their reader must look: the primitive maintainer,
# whoever installed the checkout, whoever chose the files a process registers,
# and the compile channel, which already carries its own span.
_ADDRESSED_ELSEWHERE: frozenset[str] = frozenset(
    {
        "PrimitiveReadError",
        "InstallationError",
        "GameRegistrationError",
        "DiagnosticError",
    }
)

# The carrier the stamp writes through. Not itself raised.
_CARRIERS: frozenset[str] = frozenset({"Located"})


def test_every_engine_exception_is_classified_for_location() -> None:
    """A new exception class cannot join the engine without a decision about
    whether a game sentence can raise it — and so whether it must name one.

    red under: drop `"ChooserAbort"` from `_SIGNALS`."""
    from cardlang.runtime.errors import Located

    classified = _REFUSALS | _SIGNALS | _ADDRESSED_ELSEWHERE
    assert classified == set(engine_exception_classes())
    # The carrier does not appear above, and that is the design: an exception
    # by that name would put one catchable relation over two trees whose
    # separation is the point (`cardlang/runtime/errors.py`, Contract).
    assert _CARRIERS.isdisjoint(classified)
    assert not issubclass(Located, BaseException)


def test_every_refusal_can_carry_a_location() -> None:
    """The classes a game sentence raises accept the stamp; the ones outside
    that set do not silently gain it.

    red under: remove `Located` from `IllegalMove`'s bases."""
    from cardlang.runtime.errors import Located

    classes = engine_exception_classes()
    carries = {name for name, cls in classes.items() if issubclass(cls, Located)}
    assert carries == _REFUSALS


# ---------------------------------------------------------------------------
# Axis 3 — the driver's own evaluation positions, derived from the driver.
# ---------------------------------------------------------------------------


def _enclosing_functions(tree: ast.Module) -> list[tuple[int, int, str]]:
    """Every function's line span and name, innermost last for a given line."""
    return [
        (f.lineno, max(getattr(f, "end_lineno", f.lineno) or f.lineno, f.lineno), f.name)
        for f in ast.walk(tree)
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _calls_to(tree: ast.Module, callee: str) -> list[tuple[str, ast.Call]]:
    """Each call to `callee` in this module, with the function it sits in."""
    spans = _enclosing_functions(tree)
    found: list[tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and ast.unparse(node.func) == callee):
            continue
        enclosing = [name for lo, hi, name in spans if lo <= node.lineno <= hi]
        found.append((enclosing[-1] if enclosing else "<module>", node))
    return found


def _driver_evaluation_sites() -> set[str]:
    """Every game expression the driver evaluates itself, as
    "enclosing_function:expression". Read off the calls to the stamping helper
    rather than listed, so a position added to the driver arrives here."""
    tree = ast.parse(DRIVER.read_text())
    return {f"{where}:{ast.unparse(call.args[0])}" for where, call in _calls_to(tree, STAMP)}


# Which fixture reaches each position. The value is a SET because two of them
# can be written more than one way, and each way is a case of its own; the two
# cells below hold those splits to their own registries.
_DRIVER_WITNESSES: dict[str, frozenset[str]] = {
    "run_phase:q.expr": frozenset({WHEN_GUARD.stem, REPEAT_CONDITION.stem}),
    "_declare_state:decl.default": frozenset({PHASE_STATE.stem, GAME_STATE.stem}),
    "play_game:game.loser.selection": frozenset({LOSER_SELECTION.stem}),
    "read:body": frozenset({TRICK_ORDER_ROW.stem}),
}

# The qualifier's arms, and the state declarer's two callers — the sub-axes
# one derived position each hides, keyed to the registry that mints them.
_QUALIFIER_WITNESSES: dict[str, str] = {
    "when": WHEN_GUARD.stem,
    "repeat_until": REPEAT_CONDITION.stem,
}
_STATE_SCOPE_WITNESSES: dict[str, str] = {
    "play_game": GAME_STATE.stem,
    "run_phase": PHASE_STATE.stem,
}


def test_the_driver_evaluates_no_game_text_around_the_stamp() -> None:
    """The driver hands game text to the evaluator through ONE function, which
    stamps the expression. That is what makes the axis below a derivation
    rather than a list: a position added anywhere in the module is either
    stamped or is the call this cell names.

    red under: in `cardlang/runtime/driver.py`, restore `run_phase`'s `when`
    arm to `evaluate(q.expr, ctx)`."""
    tree = ast.parse(DRIVER.read_text())
    bound = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "cardlang.runtime.evaluate"
        for alias in node.names
        if alias.name == "evaluate"
    }
    assert bound == {"evaluate"}, (
        f"the driver binds the evaluator as {sorted(bound)}; this scrape reads "
        f"the name `evaluate`, and an alias would empty it"
    )
    outside = sorted(
        f"line {call.lineno}"
        for where, call in _calls_to(tree, "evaluate")
        if where != STAMP
    )
    assert not outside, (
        f"cardlang/runtime/driver.py evaluates game text at {outside} without "
        f"`{STAMP}`. A refusal from there reaches the designer with no line at "
        f"all — the executor stamps the sentences it dispatches, and never sees "
        f"an expression the driver reads itself"
    )


# Every module that hands game text to the evaluator, and what stamps a
# refusal from it. The driver is one of a closed few, and the axis above is
# scoped to it because the others are all reached from a statement the
# executor dispatched — coarser than the expression, never absent.
_EVALUATING_MODULES: dict[str, str] = {
    "runtime/evaluate.py": "the evaluator's own recursion into subexpressions",
    "runtime/execute.py": "statements, each stamped by the `execute` that dispatched it",
    "runtime/driver.py": f"the phase tree, each expression stamped by `{STAMP}`",
    "runtime/mechanics.py": (
        "a round form's own clauses — leader, participants, trump, a move "
        "type's `when` — run from inside the round statement, which carries "
        "the span the executor stamped"
    ),
    "runtime/rules.py": (
        "a rule's card sets, consulted at a round's card decision, likewise "
        "inside that round statement"
    ),
}


def test_the_engine_evaluates_game_text_only_where_something_stamps() -> None:
    """The axis above reads one module, and this is what makes that a scope
    rather than a blind spot: a module joining the set must say what stamps a
    refusal escaping it, and a module that leaves the set stops claiming to.

    red under: add `evaluate(stmt.when, ctx)` to
    `cardlang/runtime/active_rules.py` — modes are phase configuration, read
    outside every statement, so that module is where an unstamped position
    would most plausibly arrive."""
    found = {
        str(path.relative_to(REPO / "cardlang"))
        for path in sorted((REPO / "cardlang").rglob("*.py"))
        if any(
            isinstance(node, ast.Call) and ast.unparse(node.func) == "evaluate"
            for node in ast.walk(ast.parse(path.read_text(), str(path)))
        )
    }
    assert found == set(_EVALUATING_MODULES), (
        f"modules evaluating game text with no stamping story: "
        f"{sorted(found - set(_EVALUATING_MODULES))}; recorded but no longer "
        f"evaluating: {sorted(set(_EVALUATING_MODULES) - found)}"
    )


def test_every_driver_evaluation_position_has_a_witness() -> None:
    """A position the driver evaluates and no fixture reaches is a stamp
    nobody has watched render. Both directions: a new position arrives with no
    witness, and a witness naming a position the driver no longer has fails
    rather than passing on the rest.

    red under: drop the `read:body` row — the derivation still finds the
    trick-order row and this cell names it."""
    assert set(_DRIVER_WITNESSES) == _driver_evaluation_sites()
    named = {stem for stems in _DRIVER_WITNESSES.values() for stem in stems}
    assert named <= {case.path.stem for case in _CASES}, (
        f"witnesses named for a driver position but absent from the case list: "
        f"{sorted(named - {c.path.stem for c in _CASES})}"
    )


def test_both_phase_qualifier_arms_have_a_witness() -> None:
    """The `run_phase:q.expr` position is two arms of the driver's own `if`,
    and a designer writes them as two different phase headers. The kinds come
    from the parser, the only place one is minted, so an arm added to the
    language arrives here unwitnessed.

    red under: drop the `"when"` row."""
    tree = ast.parse(PARSE.read_text())
    minted = {
        call.args[0].value
        for _, call in _calls_to(tree, "n.PhaseQualifier")
        if call.args and isinstance(call.args[0], ast.Constant)
    }
    assert minted, "no `n.PhaseQualifier` is built in cardlang/parse.py"
    assert set(_QUALIFIER_WITNESSES) == minted
    assert set(_QUALIFIER_WITNESSES.values()) <= {case.path.stem for case in _CASES}


def test_both_state_declaration_scopes_have_a_witness() -> None:
    """`_declare_state` runs a `state { }` block at either scope, and the two
    differ in what a refusal from them can name: a phase's block names the
    phase, the game's names none. The callers are read off the driver, so a
    third scope arrives here rather than riding the other two.

    red under: drop the `play_game` row."""
    tree = ast.parse(DRIVER.read_text())
    callers = {where for where, _ in _calls_to(tree, "_declare_state")}
    assert set(_STATE_SCOPE_WITNESSES) == callers
    assert set(_STATE_SCOPE_WITNESSES.values()) <= {case.path.stem for case in _CASES}


# ---------------------------------------------------------------------------
# The rendering — what a designer reads when their playout dies.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Refusal:
    """One game that dies, and the sentence a reader must be taken to."""

    name: str
    path: Path
    # The source text of the sentence that refuses. The expected line is
    # searched for rather than written down, so editing a fixture above the
    # sentence cannot leave a stale number pinned here.
    sentence: str
    occurrence: int
    # The phase the game was in, or None where the refusal escapes outside
    # every phase — a game-level `state { }` default, the `loser:` selection.
    phase: str | None
    zone: str | None
    # A line the refusal must NOT be reported at: the form enclosing the
    # sentence, where one encloses it on another line.
    not_at: str | None = None


_CASES: tuple[_Refusal, ...] = (
    _Refusal(
        name="a hand emptied before the movement that asks it for a card",
        path=EMPTY_ZONE,
        sentence="move chosen 1 card from hand[p] to discards",
        occurrence=-1,
        phase="discard_again",
        zone="hand[0]",
    ),
    _Refusal(
        name="the same movement, run by the wrapper form itself",
        path=SIMULTANEOUS,
        sentence="move chosen 1 card from hand[player] to discards",
        occurrence=-1,
        phase="discard_again",
        zone="hand[0]",
        not_at="each player simultaneously:",
    ),
    _Refusal(
        name="a dealt movement whose source an earlier phase drained",
        path=DEAL_DRAINED,
        sentence="move 1 card from hand[p] to discards",
        occurrence=-1,
        phase="discard_again",
        zone="hand[0]",
    ),
    _Refusal(
        name="a rule whose `if_impossible:` refuses every card held",
        path=RULE_REFUSES,
        sentence="round play_to_trick from leader over all players",
        occurrence=0,
        phase="play",
        zone=None,
    ),
    _Refusal(
        name="a game that outruns its declared max_length",
        path=OVERRUNS,
        sentence="for each player p: offer to p one of [take_one, take_two]",
        occurrence=0,
        phase="play",
        zone=None,
    ),
    _Refusal(
        name="a phase's `when` guard reading an empty zone's suit",
        path=WHEN_GUARD,
        sentence="phase guarded when suit_of(indicator) is hearts {",
        occurrence=0,
        phase="guarded",
        zone=None,
    ),
    _Refusal(
        name="the same read in a phase's `repeat until` condition",
        path=REPEAT_CONDITION,
        sentence="phase looped repeat until suit_of(indicator) is hearts {",
        occurrence=0,
        phase="looped",
        zone=None,
    ),
    _Refusal(
        name="a phase's own `state { }` default, matching two seats",
        path=PHASE_STATE,
        sentence="singleton : Player? = the player where",
        occurrence=0,
        phase="guarded",
        zone=None,
    ),
    _Refusal(
        name="the game's `state { }` default, declared before any phase",
        path=GAME_STATE,
        sentence="singleton     : Player? = the player where",
        occurrence=0,
        phase=None,
        zone=None,
    ),
    _Refusal(
        name="a `loser:` selection asking who holds an undealt card",
        path=LOSER_SELECTION,
        sentence="loser: player_holding(A of spades)",
        occurrence=0,
        phase=None,
        zone=None,
    ),
    _Refusal(
        name="a `trick_order { }` row asking an unranked rank's strength",
        path=TRICK_ORDER_ROW,
        sentence="card_strength: rank_value(card)",
        occurrence=0,
        phase="play",
        zone=None,
        not_at="round play_to_trick from 0 over all players source hand",
    ),
)


def _bare_state(game: n.Game) -> RuntimeState:
    """A world with the game's zones and nothing played, so a zone the store
    holds and one it does not can be handed to the same helper."""
    seating = Seating(game.players.low, clockwise=True)
    zones = ZoneStore(game.zones, seating.players)
    return RuntimeState(seating, zones, random.Random(0))


def _line_of(path: Path, sentence: str, occurrence: int) -> int:
    """The 1-based line the sentence sits on."""
    hits = [
        i for i, line in enumerate(path.read_text().splitlines(), 1) if sentence in line
    ]
    assert hits, f"{path.name} holds no line containing {sentence!r}"
    return hits[occurrence]


def _play(path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(["play", str(path)])
    return code, capsys.readouterr().err


@pytest.mark.parametrize("case", _CASES, ids=[c.path.stem for c in _CASES])
def test_the_refusal_names_the_sentence_that_refused(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """`file:line:` — the same locator a checker diagnostic prints, pointing
    at the smallest sentence that signifies rather than the form enclosing
    it."""
    _, err = _play(case.path, capsys)
    line = _line_of(case.path, case.sentence, case.occurrence)
    assert f"{case.path}:{line}:" in err, err


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.not_at is not None],
    ids=[c.path.stem for c in _CASES if c.not_at is not None],
)
def test_the_enclosing_form_is_not_reported_instead(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """The discriminating cell. `each … simultaneously` runs its embedded
    movement itself, so a location taken where the executor dispatched names
    the wrapper — a line at which the game asked for nothing."""
    _, err = _play(case.path, capsys)
    assert case.not_at is not None
    wrapper = _line_of(case.path, case.not_at, -1)
    assert f"{case.path}:{wrapper}:" not in err, err


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.phase is not None],
    ids=[c.path.stem for c in _CASES if c.phase is not None],
)
def test_the_refusal_names_the_phase(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sentence's line is not enough on its own: a procedure body, and any
    text a library supplies, run in phases named somewhere else entirely."""
    _, err = _play(case.path, capsys)
    assert f"phase {case.phase}" in err, err


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.phase is None],
    ids=[c.path.stem for c in _CASES if c.phase is None],
)
def test_a_refusal_outside_every_phase_names_no_phase(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """The position axis's third arm, asserted rather than inferred. A game's
    `state { }` is declared before the first phase and the `loser:` selection
    is read after the last, so there is no phase to name — and naming one
    would send the reader to a phase that was not running.

    red under: in `cardlang/runtime/driver.py`, stamp
    `phase=game.phases[0].name` beside the `loser:` evaluation."""
    _, err = _play(case.path, capsys)
    assert "in phase" not in err, err


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.zone is not None],
    ids=[c.path.stem for c in _CASES if c.zone is not None],
)
def test_a_movement_names_the_zone_it_moved_from(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """Named at the instance the movement resolved, so the message says which
    seat's zone was short rather than repeating the reference on the line."""
    _, err = _play(case.path, capsys)
    assert case.zone is not None and case.zone in err, err


@pytest.mark.parametrize("case", _CASES, ids=[c.path.stem for c in _CASES])
def test_a_refusal_never_arrives_as_a_traceback(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every refusal a game sentence raises is rendered by the caller. A
    traceback addresses the engine maintainer, who is not who must act."""
    code, err = _play(case.path, capsys)
    assert "Traceback" not in err, err
    assert code == 1


def test_a_zone_the_store_cannot_address_leaves_the_refusal_intact() -> None:
    """The stamp is metadata on a refusal already in flight, so a zone the
    store cannot address costs the message its zone and nothing else.

    Every fixture above moves cards between zones the store holds, so the miss
    is unreachable through them and this is the cell that reaches it.

    red under: in `cardlang/runtime/execute.py`, make `_stamped_zone` call
    `zone_label` directly — the loud form — and this raises `KeyError` in
    place of returning None."""
    from cardlang.runtime.execute import _stamped_zone
    from cardlang.runtime.state import Zone

    game = check_source(EMPTY_ZONE)
    rs = _bare_state(game)
    ctx = Ctx(rs=rs, chooser=lambda p, c, n: c[:n])
    stray = Zone()  # never added to the store
    assert _stamped_zone(ctx, stray) is None
    assert _stamped_zone(ctx, rs.zones.instance("hand", 0)) == "hand[0]"


def test_the_runtime_locator_reads_as_the_checker_locator_does(
    capsys: pytest.CaptureFixture[str]
) -> None:
    """One shape for both halves of the failure channel — rendered through
    the checker's own formatter, so the two cannot drift into two spellings
    of a file position."""
    _, err = _play(EMPTY_ZONE, capsys)
    line = _line_of(EMPTY_ZONE, "move chosen 1 card from hand[p] to discards", -1)
    located = next(
        (row for row in err.splitlines() if row.startswith(f"{EMPTY_ZONE}:")), None
    )
    assert located is not None, err
    span = Span(str(EMPTY_ZONE), 0, 0, line, int(located.split(":")[2]))
    expected = Diagnostic(Severity.ERROR, "cannot choose 1 of 0 candidates", span)
    assert located == expected.format()
