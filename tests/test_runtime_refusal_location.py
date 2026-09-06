"""A runtime refusal names the sentence that refused.

Every compile diagnostic reaches the game author at `file:line:column`
(`cardlang/diagnostics.py`, `Diagnostic.format`). A refusal raised while the
game is PLAYING reaches them as a message and nothing else, so a designer
whose playout dies bisects their own file to find the line a span already
knows. The two halves of one [[failure-channel]] address the same [[author]]
and only one of them says where.

The location is stamped as the refusal unwinds, innermost first, and the
statement executor is where the class is owned: every statement a game runs
passes through it holding its own span, and the [[context]] it is handed
holds the phase. What that alone cannot see is a statement form that runs an
embedded sentence ITSELF instead of handing it back — there the executor's
span is the wrapper's line and the refusal happened on the line inside it.
That gap is this module's primary axis, and it is derived from the `n.Stmt`
union rather than read off the executor, because reading it off the executor
would measure the stamp against itself.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a refusal a game sentence can raise renders, to the designer, at
            the smallest span that signifies it — the sentence that refused,
            never the form enclosing it — and names the phase it was running
            in, and the source zone when a movement is what refused. Every
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

            (3) The DRIVER-POSITION axis: where a refusal escapes from,
            partitioned from the driver itself — under a statement, in a
            phase's qualifier or state block, and outside any phase. The
            first two carry a location; the third names no phase because none
            is running, which the grid states as its expected outcome rather
            than leaving to inference.
registry:   the statement axis: `typing.get_args(cardlang.ast.nodes.Stmt)`;
            the refusal-class axis: an import walk over the `cardlang`
            package, the same derivation shape
            tests/test_failure_taxonomy.py uses for the taxonomy's own
            domain; the driver positions: `cardlang.runtime.driver.play_game`
            and `run_phase`. Where each class SITS in the failure tree is
            pinned at tests/test_failure_taxonomy.py, and that every raise
            site names a class with a recorded Author at
            tests/test_guard_role_sites.py; neither enumeration is re-copied
            here.
does not prove:  nothing here says the refusal MESSAGES are the right words
            for a designer — the wording of the runtime's refusals is issue
            #329, and a green here holds whatever text those raise sites
            carry. It equally says nothing about a refusal reaching a caller
            that is not the command line: the adapter and the harnesses catch
            the same classes and render them themselves, and what they print
            is their own claim.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import get_args

import cardlang
from cardlang.ast import nodes as n

REPO = Path(__file__).parent.parent
FIXTURES = REPO / "tests" / "fixtures"

# A hand emptied before the statement that asks it for a card. The refusal
# rises through the executor holding the movement's own span.
EMPTY_ZONE = FIXTURES / "empty_zone_choice.cardlang"
# The same movement one line inside `each … simultaneously`, which runs it
# without handing it back — so the executor's span is the wrapper's line.
SIMULTANEOUS = FIXTURES / "simultaneous_empty_zone_choice.cardlang"
# A rule whose `if_impossible:` refuses every card the player holds.
RULE_REFUSES = FIXTURES / "rule_refuses_every_card.cardlang"
# Checks clean, then outruns its declared `max_length` on every seed.
OVERRUNS = FIXTURES / "exceeds_max_length.cardlang"


# ---------------------------------------------------------------------------
# Axis 1 — the statement forms, derived from the `n.Stmt` union.
# ---------------------------------------------------------------------------

# Runs no embedded sentence at all: whatever refuses under one of these
# refuses under the statement the executor dispatched, so its own span is
# already the smallest that signifies.
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
    }
)

# Hands its embedded sentences back to the executor, which stamps each in
# turn — so the innermost stamp wins and these need nothing of their own.
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
        "TrickRound",
        "AuctionRound",
        "ClimbRound",
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
    """Each `n.Stmt` arm of the executor's match, and the names it calls.

    Read from source rather than from the classification above, so the sets
    are a claim about the executor and not a restatement of themselves.
    """
    tree = ast.parse((REPO / "cardlang" / "runtime" / "execute.py").read_text())
    funcs = {f.name: f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    arms: dict[str, set[str]] = {}
    for match in ast.walk(funcs["execute"]):
        if not isinstance(match, ast.Match):
            continue
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
                arms[name] = calls
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
