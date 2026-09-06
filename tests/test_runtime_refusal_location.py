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
            domain; the driver positions: `cardlang.runtime.driver.play_game`
            and `run_phase`. Where each class SITS in the failure tree is
            pinned at tests/test_failure_taxonomy.py, and that every raise
            site names a class with a recorded Author at
            tests/test_guard_role_sites.py; neither enumeration is re-copied
            here.
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
    phase: str
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


@pytest.mark.parametrize("case", _CASES, ids=[c.path.stem for c in _CASES])
def test_the_refusal_names_the_phase(
    case: _Refusal, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sentence's line is not enough on its own: a procedure body, and any
    text a library supplies, run in phases named somewhere else entirely."""
    _, err = _play(case.path, capsys)
    assert f"phase {case.phase}" in err, err


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
