"""The Hosted Poll: `before asking <binder> { … }` on a climbing round.

The surface-totality audit for the clause (decisions.md "Off-the-clock
windows", "The climbing form of `round`", "Surface totality").

    property:   A climbing round's Hosted Poll runs its body exactly once
                before every turn and Interrupt Window ask, with its binder
                bound to the seat about to be asked, and never before a Play
                Announcement or once the round has ended; a body whose writes
                end the round is followed by no ask. Every sentence the clause
                accepts is either run so, or refused at resolve: anywhere in
                what the body can execute — its text and every definition it
                reaches by name — a statement outside the allow-list, the
                `state` pronoun wherever it
                stands, and a call of a Primitive the game's own namespace
                holds; and a binder spelled like a name already classifiable
                where the clause is written.

    domain:     Eight axes, each derived from its registry in code:
                  A. body statement kind — every member of the `Stmt` union,
                     split three ways: admitted, refused, synthetic;
                  B. nesting — every refused kind inside every admitted
                     container that holds statements (`if`, `as`,
                     `for each`), and inside a procedure the body runs,
                     for the refused kinds a procedure body itself admits;
                  C. pronoun reads — every name in `resolve._PRONOUNS`, read
                     in the body and read by the same statement written
                     before the round, with the round at a phase's top level
                     and inside `as 0 { }`: the two agree, but for `state`,
                     which the body refuses — crossed, for `state`, with
                     the positions a value stands in (`STATE_POSITIONS`:
                     a member receiver, a `let`, an `is` operand, a function
                     and a procedure argument, a list element, and bare in a
                     reached function), each admitted before the round;
                  D. binder spelling — every classification `_classify`
                     can answer for a bare name, spelled as the binder;
                  E. ask moment — every member of `CLIMB_ASK_KINDS`, plus the
                     two moments no ask is made at (after termination, and
                     after a body whose writes end the round), each executed
                     on the miniature fixture below and reached by playout;
                  F. reached through — every route by which a body names a
                     definition whose text then runs (its own text, a `run`,
                     an offered move type's effect and guard by `offer`, alone
                     and in a `turns` ring, a function call, a function's call,
                     and a `run` that offers), crossed with every payload the
                     route can hold: the refused statement kinds where it
                     holds statements, the `state`
                     read and the Primitive call everywhere. The routes are
                     the naming slots on statement and expression nodes whose
                     namespace is in `HOSTED_REACH_POOLS`, and every other
                     such slot is filed inert, refused, or on a refused
                     statement (`test_the_routes_are_every_definition_a_body_can_name`).
                  G. call namespace — every `primitives_block.Regime`,
                     crossed with what the called name is in that game: a
                     Primitive, or a designer function spelled like one;
                  H. the runtime agrees — every row of A, F and C's `state`
                     positions, and G's declared-regime cells, played with
                     resolve's `_check_hosted_polls` switched off: a row
                     resolve refuses trips the runtime's Shadow Guard when it
                     executes, a row it admits plays through, and a refused
                     row no game can run (`_refused_elsewhere`, authored by
                     rule) is still refused by another check.
                The clause is written on `round climb` only: the trick
                form carries no Hosted Poll by grammar
                (`test_the_clause_is_a_climb_clause_only`).

    registry:   A, B. `typing.get_args(cardlang.ast.nodes.Stmt)` against
                   `stdlib.hosted_poll.HOSTED_POLL_ALLOWED` / `stdlib.hosted_poll.HOSTED_POLL_REFUSED`
                C. `cardlang.resolve._PRONOUNS`
                D. the string literals `cardlang.resolve._classify` returns,
                   scraped from its source
                E. `cardlang.runtime.mechanics.CLIMB_ASK_KINDS`
                F. `cardlang.resolve._NAMING_SLOTS_BY_TYPE` over
                   `typing.get_args(n.Stmt)` and `typing.get_args(n.Expr)`,
                   against `resolve.HOSTED_REACH_POOLS` and
                   `resolve.HOSTED_REACH_INERT_SLOTS`
                G. `cardlang.primitives_block.Regime`
                H. the rows of A, C, F and G above; the runtime half's tables
                   are `cardlang/stdlib/hosted_poll.py`'s, shared with resolve
                Procedure-body refusals: tests/test_procedures.py.
                A synthetic `Block` is unwritable from source:
                tests/test_procedures.py::test_a_synthetic_block_is_not_writable_from_source.
                The Hosted Poll in the corpus, end to end and against the
                rules: tests/test_playout_tichu.py,
                tests/openspiel_ready/test_tichu.py.

    does not prove:  that axis E's reach is total over the orders in which
                the regimes can meet. Each ask kind is reached and held to
                the body-once rule on every one of its occurrences over the
                sampled playouts, but the playouts are uniform draws on one
                engine, so a sequence the engine makes rare (a bomb taken in
                the window after a trick's last pass, straight after a Play
                Announcement) is
                sampled rather than enumerated. Nor that axis C's positions
                are every place an expression can stand: the refusal keys
                on the pronoun itself, never on what holds it, so the rows
                sample positions to witness that, and a position a later
                node kind adds is covered by the same arm unwitnessed. Nor
                that axes C and F name every route from an expression to the
                live frame: the routes are the readers of `mech_state` that
                `cardlang/runtime/` holds — the pronoun's evaluation and a
                Primitive's `EngineFacts.round_state` — and a reader added
                there is a route no row names. Nor that axis H's agreement
                is total: its verdicts sample the seeds in `AGREEMENT_SEEDS`,
                so an offered move's effect executes only when a uniform
                draw picks it, and the non-local control kinds reach the
                runtime's statement arm on no row — the miniature has no
                outcome phase, later sibling, or hand loop to make them
                legal in the body; the arm reads the same table for them as
                for the kinds that do.

red under (each planted in the code under guard, run, and reverted):
- axis A/B: delete `n.AsBlock` from `stdlib.hosted_poll.HOSTED_POLL_ALLOWED` — the
  admitted `AsBlock` cell reddens;
- axis A/B: drop the `"procedure"` row of `resolve.HOSTED_REACH_POOLS` —
  every `via_procedure` cell reddens;
- axis C: delete the `state` arm of `resolve._check_hosted_node`; key it on
  a `Member` whose receiver is the pronoun — every `STATE_POSITIONS` row but
  `member_receiver` reddens;
- axis D: return early from `resolve._check_hosted_binder`;
- axis E: add "announcement" to `mechanics.HOSTED_ASK_KINDS` — the
  announcement cell reddens; drop the second `form.terminated` check in
  `run_decision_round` — the body-ends-the-round cell reddens;
- axis F: delete the `"move_type"` row of `resolve.HOSTED_REACH_POOLS` — every
  offered-effect and offered-guard cell reddens; delete its `"function"` row —
  the function cells redden;
  empty the Primitive set in `resolve._check_hosted_polls` — the
  `primitive_call` cells redden; skip a move type's `when` field there — the
  guard cells redden; stop `resolve._definition_closure` pushing a reached
  definition onto its frontier — the `function_of_function` and
  `run_then_offer` cells redden;
- axis G: judge the Primitive refusal against `PRIMITIVE_CALL_FUNCS` instead
  of the game's `call_namespace` — the declared `designer_function` cell
  reddens;
- axis H: drop the `hosting` arm of `execute.execute` — every statement row
  reddens; of the `state` pronoun's evaluation — the `state` rows redden; of
  `narrowing.engine_facts` — the Primitive rows redden; drop the `finally`
  that clears `RuntimeState.hosting` in `mechanics._run_hosted_poll` — the
  admitted rows redden.
"""

from __future__ import annotations

import ast
import inspect
import random
import re
import textwrap
import typing
from collections import Counter
from typing import Any

import pytest

import cardlang.ast.nodes as n
import cardlang.resolve as resolve_module
import cardlang.stdlib.hosted_poll as hosted_registry
from cardlang.builtins.functions import PRIMITIVE_CALL_FUNCS
from cardlang.diagnostics import DiagnosticError
from cardlang.runtime.errors import ShadowGuardError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import Regime
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.mechanics import CLIMB_ASK_KINDS
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.tichu_combinations import INTERRUPT_DECLINE, WISH_TOKENS
from cardlang.runtime.values import Player

# The miniature: one hand of Tichu-engine climbing tricks, whose Hosted Poll
# counts its own runs and records the seat it was run for. `{prelude}` sits
# before the trick loop, `{binder}` and `{body}` fill the clause, `{procs}` and
# `{extra}` add top-level definitions. `{acting}`, when given, is a seat whose
# `as` block holds the prelude and the trick loop, so a player is acting where
# the round and its Hosted Poll stand. The helper move type `nop` is defined
# only in a sentence that names it, because a move type no reachable offering
# presents is refused.
GAME = """
game HostedMini {{
  players: 4
  teams: [[0, 2], [1, 3]]
  direction: counterclockwise
  max_length: 5000
  cards: tichu56
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
{clauses}
  zones {{
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }}
  state {{
    score[player] : Integer = 0
    wish          : Integer = 0
    leader        : Player = 0
    runs          : Integer = 0
    asked_last    : Player = 0
    nops          : Integer = 0
    stop          : Boolean = false
    pass_dir      : SeatDirection = left
  }}
  phase play {{
    legal_moves: [play_combination]
    shuffle deck
    deal 14 cards from deck to each hand
    leader := player_holding(Mahjong of special)
{acting_open}
{prelude}
    repeat until (number of players where hand[player] is not empty) <= 1 {{
      stop := false
      round climb play_combination from leader
            over players where hand[player] is not empty
            source hand into trick_pile
            combinations tichu_lead_options follows tichu_follows
            until (number of players where hand[player] is not empty) <= 1 or stop
            before asking {binder} {{
{body}
            }}
      move all cards from trick_pile to captured[winner]
      leader := winner
      if any player where hand[player] is not empty {{
        leader := the first player from leader where hand[player] is not empty
      }}
    }}
{acting_close}
    for each player q: score[q] += runs
  }}
  winner: highest score
}}
{nop}
function seat_zero() = 0
{procs}
{extra}
"""

COUNTING = "              runs += 1\n              asked_last := p"


NOP = "move_type nop { effect { nops += 1 } }"


def source(
    body: str = COUNTING, binder: str = "p", prelude: str = "", procs: str = "", extra: str = "",
    clauses: str = "", acting: str = "",
) -> str:
    names_nop = re.search(r"\bnop\b", "\n".join((body, prelude, procs, extra))) is not None
    return GAME.format(
        body=body, binder=binder, prelude=prelude, procs=procs, extra=extra, clauses=clauses,
        nop=NOP if names_nop else "",
        acting_open=f"    as {acting} {{" if acting else "",
        acting_close="    }" if acting else "",
    )


def check(**kw: str) -> n.Game:
    return check_dsl(source(**kw), "hosted")


def refusal(**kw: str) -> str:
    with pytest.raises(DiagnosticError) as excinfo:
        check(**kw)
    return str(excinfo.value) + "".join(getattr(excinfo.value, "__notes__", []))


def indent(stmt: str) -> str:
    return textwrap.indent(textwrap.dedent(stmt).strip(), " " * 14)


def test_the_counting_miniature_checks_and_plays() -> None:
    game = check()
    play_game(game, random.Random(0), None, random_chooser(random.Random(0)), None)


# ---------------------------------------------------------------------------
# Axis A — body statement kind
# ---------------------------------------------------------------------------

# One sentence per statement kind, written as a designer would inside the
# body, beside the prelude or definitions it needs to be otherwise sound.
SNIPPETS: dict[str, tuple[str, dict[str, str]]] = {
    "Transfer": ("move all cards from trick_pile to captured[p]", {}),
    "EpistemicOp": ("reveal one card from hand[p]", {}),
    "RotateStmt": ("rotate pass_dir through [left, across, right, hold]", {}),
    "EachSimultaneous": (
        "each player simultaneously: move chosen 1 cards from hand[player] to trick_pile",
        {},
    ),
    "ForEach": ("for each player q: score[q] += 0", {}),
    "RepeatUntil": ("repeat until runs > 0 { runs += 1 }", {}),
    "IfStmt": ("if runs > 0 { runs += 1 }", {}),
    "AsBlock": ("as p { runs += 1 }", {}),
    "Turns": ("turns w from p over all players until runs > 100 { runs += 1 }", {}),
    "LetStmt": ("let seat = p\nasked_last := seat", {}),
    "AssignStmt": ("runs += 1", {}),
    "Offer": ("offer to p one of [nop]", {}),
    "TrickRound": (
        "round play_to_trick from p over all players source hand into trick_pile "
        "winner highest_of_led_suit",
        {},
    ),
    "ClimbRound": (
        "round climb play_combination from p over all players source hand into trick_pile "
        "combinations tichu_lead_options follows tichu_follows until runs > 0",
        {},
    ),
    "Produce": ("produce Done", {}),
    "Produces": (
        "decide produces:\n  Won(w) { score[w] += 1 }\n  Lost { score[0] += 0 }",
        {"prelude": "    phase decide -> outcome {\n      Won(Player) | Lost\n    } {\n      produce Won(0)\n    }"},
    ),
    "ContinueTo": ("continue to play", {}),
    "SkipToNextHand": ("skip to next hand", {}),
    "RunStmt": (
        "run note(p)",
        {"procs": "procedure note(who : Player) { score[who] += 1 }"},
    ),
}

# The kind no source program can write: `expand` builds it from a `run`.
SYNTHETIC = {"Block"}

STMT_KINDS = sorted(t.__name__ for t in typing.get_args(n.Stmt))
ALLOWED = {t.__name__ for t in hosted_registry.HOSTED_POLL_ALLOWED}
REFUSED = {t.__name__ for t in hosted_registry.HOSTED_POLL_REFUSED}

# The expected column, authored as the operator's ruling on issue #776 reads
# it, never read off the implementation's sets above.
EXPECTED_ADMITTED = {
    "IfStmt", "LetStmt", "AssignStmt", "Offer", "AsBlock",
    "ForEach", "RunStmt", "Turns",
}


def test_the_stmt_union_is_partitioned() -> None:
    """Every statement kind is admitted, refused, or synthetic, and the
    ruling's admitted set is the implementation's. A new `Stmt` member fails
    here until someone decides which it is.

    red under: delete any row of `stdlib.hosted_poll.HOSTED_POLL_REFUSED`."""
    union = set(STMT_KINDS)
    assert ALLOWED | REFUSED == union
    assert not ALLOWED & REFUSED
    assert ALLOWED - SYNTHETIC == EXPECTED_ADMITTED
    assert set(SNIPPETS) | SYNTHETIC == union


@pytest.mark.parametrize("kind", sorted(set(STMT_KINDS) - SYNTHETIC))
def test_body_statement_kind(kind: str) -> None:
    stmt, needs = SNIPPETS[kind]
    kw = {"body": indent(stmt), **needs}
    if kind in EXPECTED_ADMITTED:
        check(**kw)
        parsed = parse_text(source(**kw), "hosted")
        polls = [nd for nd in _walk(parsed) if isinstance(nd, n.HostedPoll)]
        assert any(type(s).__name__ == kind for p in polls for s in p.body)
    else:
        message = refusal(**kw)
        assert "the Hosted Poll (`before asking p`) may not hold" in message, message


# ---------------------------------------------------------------------------
# Axis B — nesting
# ---------------------------------------------------------------------------

CONTAINERS = {
    "IfStmt": "if runs > 0 {{ {stmt} }}",
    "AsBlock": "as p {{ {stmt} }}",
    "ForEach": "for each player q: {stmt}",
    "Turns": "turns w from p over all players until runs > 100 {{ {stmt} }}",
}

# The refused kinds a procedure body admits of its own accord; the others are
# `_check_procedures`'s refusals, which fire first and name themselves.
PROC_OWN_REFUSALS = {
    t.__name__
    for t in (*resolve_module._NON_LOCAL_STMTS, *resolve_module._WINNER_BINDING_STMTS)
}


def test_the_containers_are_every_admitted_statement_holder() -> None:
    """Axis B's container list is every admitted kind that holds statements
    in a body a designer writes: `RunStmt` is the procedure cell below, and
    the rest hold none (`Offer`'s decision is a move type, whose effect the
    clause does not reach into)."""
    holders = {
        k for k in EXPECTED_ADMITTED
        if any(
            f.type is not None and "Stmt" in str(f.type)
            for f in getattr(getattr(n, k), "__dataclass_fields__", {}).values()
        )
    }
    assert holders == set(CONTAINERS)


@pytest.mark.parametrize("container", sorted(CONTAINERS))
@pytest.mark.parametrize("kind", sorted(REFUSED - {"Produces"}))
def test_a_refused_kind_nested_in_an_admitted_container(container: str, kind: str) -> None:
    stmt, needs = SNIPPETS[kind]
    wrapped = CONTAINERS[container].format(stmt=stmt)
    message = refusal(body=indent(wrapped), **needs)
    assert "the Hosted Poll (`before asking p`) may not hold" in message, message


@pytest.mark.parametrize("kind", sorted(REFUSED - PROC_OWN_REFUSALS - {"Produces"}))
def test_a_refused_kind_via_procedure(kind: str) -> None:
    stmt, needs = SNIPPETS[kind]
    stmt = stmt.replace("[p]", "[who]").replace(" p ", " who ").replace("from p", "from who")
    procs = f"procedure bad(who : Player) {{\n{stmt}\n}}"
    message = refusal(body=indent("run bad(p)"), procs=procs, **needs)
    assert "may not hold" in message and "reached through procedure 'bad'" in message, message


def test_a_produces_over_an_outcome_is_refused_in_the_body() -> None:
    stmt, needs = SNIPPETS["Produces"]
    message = refusal(body=indent(f"if runs > 0 {{\n{stmt}\n}}"), **needs)
    assert "may not hold `produces:`" in message, message


# ---------------------------------------------------------------------------
# Axis C — pronoun reads
# ---------------------------------------------------------------------------

PRONOUN_READS = {
    "state": "if state.lead_ended_trick { runs += 1 }",
    "action": "let seen = action\nruns += 1",
    "winner": "asked_last := winner",
    "actor": "asked_last := actor",
    "active_rules": "if active_rules is none { runs += 1 }",
}


def test_the_pronoun_axis_is_every_pronoun() -> None:
    assert set(PRONOUN_READS) == set(resolve_module._PRONOUNS)


def _verdict(**kw: str) -> bool:
    try:
        check(**kw)
    except DiagnosticError:
        return False
    return True


# Whether each read is admitted where the round stands, at a phase's top level
# and inside `as 0 { }`. `actor` names no one where no player is acting.
EXPECTED_PRONOUN_VERDICT: dict[str, dict[str, bool]] = {
    "action": {"": True, "0": True},
    "winner": {"": True, "0": True},
    "actor": {"": False, "0": True},
    "active_rules": {"": True, "0": True},
}


@pytest.mark.parametrize("acting", ["", "0"], ids=["phase_top_level", "as_0"])
@pytest.mark.parametrize("pronoun", sorted(PRONOUN_READS))
def test_a_pronoun_read_in_the_body(pronoun: str, acting: str) -> None:
    read = PRONOUN_READS[pronoun]
    if pronoun == "state":
        message = refusal(body=indent(read), acting=acting)
        assert "may not read `state`" in message, message
        return
    # The body runs in the round statement's own context, so a read there is
    # judged as the same statement written just before the round.
    want = EXPECTED_PRONOUN_VERDICT[pronoun][acting]
    assert _verdict(body=indent(read), acting=acting) is want
    assert _verdict(body=COUNTING, prelude="    " + read, acting=acting) is want


def test_a_state_read_via_procedure_is_refused() -> None:
    message = refusal(
        body=indent("run peek()"),
        procs="procedure peek() { if state.lead_ended_trick { runs += 1 } }",
    )
    assert "may not read `state`, reached through procedure 'peek'" in message, message


# Where the `state` pronoun can stand as a value: the live frame it evaluates
# to escapes through any of them, so the refusal is the pronoun's wherever it
# stands, never the `state.field` shape alone. Each row is (body, extra
# top-level text).
STATE_POSITIONS: dict[str, tuple[str, str]] = {
    "member_receiver": ("if state.lead_ended_trick { runs += 1 }", ""),
    "let_alias": ("let live = state\nasked_last := live.leader", ""),
    "is_operand": ("if state is none { runs += 1 }", ""),
    "function_argument": ("if peek(state) { runs += 1 }", "function peek(s : Integer) = true"),
    "run_argument": ("run peek(state)", "procedure peek(s : Integer) { runs += 1 }"),
    "list_element": ("let frames = [state]\nruns += 1", ""),
    "bare_in_reached_function": ("if peek() { runs += 1 }", "function peek() = state is none"),
}


@pytest.mark.parametrize("position", sorted(STATE_POSITIONS))
def test_the_state_pronoun_is_refused_wherever_it_stands(position: str) -> None:
    """red under: key `resolve._check_hosted_node`'s `state` arm on a
    `Member` whose receiver is the pronoun instead of on the pronoun itself —
    every row but `member_receiver` reddens."""
    body, extra = STATE_POSITIONS[position]
    message = refusal(body=indent(body), extra=extra)
    assert "the Hosted Poll (`before asking p`) may not read `state`" in message, message


@pytest.mark.parametrize("position", sorted(STATE_POSITIONS))
def test_each_state_position_is_admitted_before_the_round(position: str) -> None:
    """The control: every position is a sentence the language accepts written
    before the round, so a refusal above is the Hosted Poll's and never the
    fixture's."""
    body, extra = STATE_POSITIONS[position]
    check(prelude=textwrap.indent(body, "    "), extra=extra)


# ---------------------------------------------------------------------------
# Axis D — binder spelling
# ---------------------------------------------------------------------------


def _classify_kinds() -> set[str]:
    """The kinds `_classify` can answer, scraped from its own returns."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(resolve_module._classify)))
    return {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


# kind -> (the binder spelling, what the sentence also needs, the refusal)
BINDER_SPELLINGS: dict[str, tuple[str, dict[str, str], str]] = {
    "null": ("none", {}, ""),
    "bool": ("true", {}, "is a reserved word"),
    "pronoun": ("actor", {}, "is a reserved word"),
    "local": ("seat", {"prelude": "    let seat = 0"}, "shadows a name already bound here"),
    "state_var": ("runs", {}, "shadows a state variable"),
    "zone": ("deck", {}, "shadows a zone"),
    "enum_value": ("left", {}, "shadows an enum value"),
}


def test_the_binder_axis_is_every_classification() -> None:
    assert set(BINDER_SPELLINGS) == _classify_kinds()


@pytest.mark.parametrize("kind", sorted(BINDER_SPELLINGS))
def test_a_binder_spelled_like_a_classifiable_name_is_refused(kind: str) -> None:
    spelling, needs, words = BINDER_SPELLINGS[kind]
    body = indent(f"asked_last := {spelling}") if kind not in ("null", "bool", "zone") else indent("runs += 1")
    message = refusal(binder=spelling, body=body, **needs)
    assert words in message, message


def test_a_fresh_binder_is_admitted() -> None:
    check(binder="seat", body=indent("asked_last := seat"))


# ---------------------------------------------------------------------------
# Axis F — reached through: everything the body can execute, not its text
# ---------------------------------------------------------------------------

# How a payload reaches the body, one row per way a body names a definition
# that then runs: its own text, a procedure it runs, the effect and the guard
# of a move type it offers (by `offer`, alone or in a `turns` ring), a function it
# calls, and a function that function calls. `{x}` is the payload. Each route
# is (body, extra top-level text, whether it holds statements).
ROUTES: dict[str, tuple[str, str, bool]] = {
    "direct": ("{x}", "", True),
    "run": ("run via(p)", "procedure via(who : Player) {{\n{x}\n}}", True),
    "offer_effect": ("offer to p one of [via]", "move_type via {{ effect {{\n{x}\n}} }}", True),
    "ring_offer_effect": (
        "nops := 0\nturns w from p over all players until nops > 0 {{ offer to w one of [via, nop] }}",
        "move_type via {{ effect {{\n{x}\n}} }}",
        True,
    ),
    "offer_guard": ("offer to p one of [via, nop]", "move_type via {{ when: {e} effect {{ }} }}", False),
    "ring_offer_guard": (
        "nops := 0\nturns w from p over all players until nops > 0 {{ offer to w one of [via, nop] }}",
        "move_type via {{ when: {e} effect {{ }} }}",
        False,
    ),
    "function": ("if via() {{ runs += 1 }}", "function via() = {e}", False),
    "function_of_function": ("if via() {{ runs += 1 }}", "function via() = inner()\nfunction inner() = {e}", False),
    "run_then_offer": (
        "run via(p)",
        "procedure via(who : Player) {{ offer to who one of [deep] }}\n"
        "move_type deep {{ effect {{\n{x}\n}} }}",
        True,
    ),
}

# What must not be reached. An expression payload is a Boolean read (so it
# fits a `when:` and an `if`); a statement payload is a statement. The
# Primitive is declared in the game's `primitives { }` block, because a game
# module reads the live round frame through `EngineFacts.round_state`.
PRIMITIVE_CLAUSE = "  primitives { tichu_dragon_won() : Boolean }"
EXPR_PAYLOADS: dict[str, tuple[str, str]] = {
    "state_read": ("state.lead_ended_trick", "may not read `state`"),
    "primitive_call": ("tichu_dragon_won()", "may not call the Primitive `tichu_dragon_won`"),
}
STMT_PAYLOADS: dict[str, tuple[str, str]] = {
    **{
        kind: (SNIPPETS[kind][0], "may not hold")
        for kind in sorted(REFUSED - {"Produces", "RunStmt"})
    },
}


# The name the asked seat goes by where a route's payload is written: the
# parameter a run procedure takes it as, and the acting player inside an
# offered move type's effect. A payload naming `p` there would be an unbound
# name — refused, but not by the Hosted Poll.
SEAT_IN_ROUTE = {
    "run": "who",
    "offer_effect": "actor",
    "ring_offer_effect": "actor",
    "run_then_offer": "actor",
}


def _route_source(route: str, payload: str, is_stmt: bool) -> dict[str, str]:
    body, extra, _ = ROUTES[route]
    if is_stmt:
        stmt = re.sub(r"\bp\b", SEAT_IN_ROUTE.get(route, "p"), payload)
        filled_body = body.format(x=stmt) if route == "direct" else body.format()
        filled_extra = extra.format(x=stmt)
    else:
        read = f"if {payload} {{ runs += 1 }}" if route == "direct" else payload
        filled_body = body.format(x=read) if route == "direct" else body.format()
        filled_extra = extra.format(e=payload, x=f"if {payload} {{ score[0] += 0 }}")
    return {"body": indent(filled_body), "extra": filled_extra, "clauses": PRIMITIVE_CLAUSE}


REACH_CELLS = [
    pytest.param(route, name, id=f"{route}-{name}")
    for route, (_, _, holds_stmts) in ROUTES.items()
    for name in (
        [*EXPR_PAYLOADS, *(STMT_PAYLOADS if holds_stmts else ())]
    )
]


def test_the_routes_are_every_definition_a_body_can_name() -> None:
    """Axis F's routes are derived, not listed: every reference slot on a
    statement or expression node that names a definition whose body RUNS
    (a procedure, a move type, a function) is followed, and every other slot
    on those nodes names something that runs no DSL text of the game's
    (a zone, a phase, a kernel move type, a Primitive query, a deck value, a
    role) or sits on a statement the allow-list refuses outright.

    red under: delete the `"procedure"` row of `resolve.HOSTED_REACH_POOLS`."""
    stmt_expr = set(typing.get_args(n.Stmt)) | set(typing.get_args(n.Expr))
    slots = {
        (cls, field): resolve_module._REFERENCE_SLOTS.get((cls, field))
        for cls, fields in resolve_module._NAMING_SLOTS_BY_TYPE.items()
        if cls in stmt_expr
        for field in fields
    }
    followed = {k for k, ns in slots.items() if ns in resolve_module.HOSTED_REACH_POOLS}
    inert = set(resolve_module.HOSTED_REACH_INERT_SLOTS)
    refused_owner = {k for k in slots if k[0] in hosted_registry.HOSTED_POLL_REFUSED}
    classified = [followed, inert, refused_owner]
    assert set().union(*classified) == set(slots), set(slots) - set().union(*classified)
    assert sum(map(len, classified)) == len(set().union(*classified)), "a slot filed twice"
    assert {(cls.__name__, f) for cls, f in followed} == {
        ("RunStmt", "name"), ("Offer", "offering"), ("Call", "func"),
    }


@pytest.mark.parametrize(("route", "payload"), REACH_CELLS)
def test_a_payload_reached_through_a_route_is_refused(route: str, payload: str) -> None:
    if payload in EXPR_PAYLOADS:
        text, words = EXPR_PAYLOADS[payload]
        kw = _route_source(route, text, is_stmt=False)
    else:
        text, words = STMT_PAYLOADS[payload]
        kw = _route_source(route, text, is_stmt=True)
    message = refusal(**kw)
    assert f"the Hosted Poll (`before asking p`) {words}" in message, message
    if route != "direct":
        assert "reached through" in message, message


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_each_route_with_a_clean_payload_is_admitted(route: str) -> None:
    """The control: every route's fixture is valid with nothing refused in it,
    so a refusal above is the payload's and never the fixture's."""
    body, extra, holds_stmts = ROUTES[route]
    kw = _route_source(route, "runs > 0", is_stmt=False)
    if holds_stmts and route != "direct":
        kw = _route_source(route, "score[0] += 0", is_stmt=True)
    kw["clauses"] = ""
    check(**kw)


# Which calls the Primitive refusal speaks for, by the game's Primitive regime
# (`primitives_block.Regime`) and by what the called name is in that game: a
# Primitive the game can call, or a designer function spelled like a
# Primitive. A call dispatches to the designer's function first, so the
# refusal follows the game's own native namespace (`call_namespace`), never
# the corpus-wide registry. Each cell is (clauses, body, extra, the words the
# diagnostic carries, or None when the sentence is admitted).
SHADOW_PRIMITIVE = "gin_can_knock"
PRIMITIVE_NAMESPACE_CELLS: dict[tuple[str, str], tuple[str, str, str, str | None]] = {
    ("declared", "primitive"): (
        PRIMITIVE_CLAUSE,
        "if tichu_dragon_won() { runs += 1 }",
        "",
        "may not call the Primitive `tichu_dragon_won`",
    ),
    ("declared", "designer_function"): (
        PRIMITIVE_CLAUSE,
        f"if {SHADOW_PRIMITIVE}() {{ runs += 1 }}",
        f"function {SHADOW_PRIMITIVE}() = runs > 0",
        None,
    ),
    ("legacy", "primitive"): (
        "",
        "if tichu_dragon_won() { runs += 1 }",
        "",
        "is a Primitive a game reaches only by declaring it",
    ),
    ("legacy", "designer_function"): (
        "",
        f"if {SHADOW_PRIMITIVE}() {{ runs += 1 }}",
        f"function {SHADOW_PRIMITIVE}() = runs > 0",
        "shadows the native function of the same name",
    ),
}


def test_the_primitive_namespace_axis_is_every_regime() -> None:
    assert {regime for regime, _ in PRIMITIVE_NAMESPACE_CELLS} == {r.value for r in Regime}
    assert SHADOW_PRIMITIVE in PRIMITIVE_CALL_FUNCS
    assert SHADOW_PRIMITIVE not in PRIMITIVE_CLAUSE


@pytest.mark.parametrize(("regime", "name"), sorted(PRIMITIVE_NAMESPACE_CELLS))
def test_a_call_in_the_body_by_regime_and_name(regime: str, name: str) -> None:
    """red under: judge the Primitive refusal in
    `resolve._check_hosted_polls` against `PRIMITIVE_CALL_FUNCS` instead of
    the game's `call_namespace` — the declared designer-function cell
    reddens."""
    clauses, body, extra, words = PRIMITIVE_NAMESPACE_CELLS[(regime, name)]
    if words is None:
        check(body=indent(body), extra=extra, clauses=clauses)
        return
    message = refusal(body=indent(body), extra=extra, clauses=clauses)
    assert words in message, message


def test_a_move_type_offered_outside_the_poll_is_not_judged_by_it() -> None:
    """Reach is the Hosted Poll's: a move type that moves cards is refused
    only when the poll offers it."""
    check(
        prelude="    offer to 0 one of [mover]",
        extra="move_type mover { effect { move all cards from trick_pile to captured[actor] } }",
    )


# ---------------------------------------------------------------------------
# Axis E — ask moments, by execution
# ---------------------------------------------------------------------------

# The expected column: whether the body runs before an ask of each kind.
EXPECTED_HOSTED = {
    "lead": True,
    "follow": True,
    "window": True,
    "announcement": False,
}

SEEDS = range(12)


def test_the_moment_axis_is_every_ask_kind() -> None:
    assert set(EXPECTED_HOSTED) == set(CLIMB_ASK_KINDS)


class _Recorder:
    """Classifies each climb ask from what the seat is offered and the live
    frame, and holds the body-once rule to it."""

    def __init__(self, seed: int) -> None:
        self.base = random_chooser(random.Random(seed))
        self.rs: RuntimeState | None = None
        self.seen: Counter[str] = Counter()
        self.failures: list[str] = []
        self.runs_at_last = 0
        self.hosted_asks = 0
        self.stopped_asks = 0
        self.stopped_leads = 0

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def kind(self, candidates: list[Any]) -> str:
        assert self.rs is not None
        frame = self.rs.mech_state[-1]
        if candidates and all(isinstance(c, str) and c in WISH_TOKENS for c in candidates):
            return "announcement"
        if INTERRUPT_DECLINE in candidates:
            return "window"
        return "lead" if frame["current"] is None else "follow"

    def __call__(self, player: Player, candidates: list[Any], k: int) -> list[Any]:
        rs = self.rs
        assert rs is not None
        kind = self.kind(candidates)
        self.seen[kind] += 1
        runs = int(rs.get("runs"))
        ran = runs - self.runs_at_last
        want = 1 if EXPECTED_HOSTED[kind] else 0
        if ran != want:
            self.failures.append(f"{kind}: body ran {ran} times before the ask, want {want}")
        if want and rs.get("asked_last") != player:
            self.failures.append(f"{kind}: binder bound {rs.get('asked_last')}, asked {player}")
        if bool(rs.get("stop")):
            if kind == "lead":
                self.stopped_leads += 1
            else:
                self.stopped_asks += 1
        self.hosted_asks += want
        self.runs_at_last = runs
        return self.base(player, candidates, k)


def _drive(body: str = COUNTING) -> list[_Recorder]:
    game = check(body=body)
    out = []
    for seed in SEEDS:
        rec = _Recorder(seed)
        result = play_game(game, random.Random(seed), None, rec, None, on_first_decision=rec.attach)
        final_runs = result.scores[0]  # the miniature scores every seat its run count
        if final_runs != rec.hosted_asks:
            rec.failures.append(
                f"the body ran {final_runs} times over {rec.hosted_asks} hosted asks — "
                f"a run with no ask after it"
            )
        out.append(rec)
    return out


@pytest.fixture(scope="module")
def counted() -> list[_Recorder]:
    return _drive()


@pytest.mark.parametrize("kind", CLIMB_ASK_KINDS)
def test_the_body_runs_before_each_ask_of_its_kinds(counted: list[_Recorder], kind: str) -> None:
    assert sum(r.seen[kind] for r in counted) > 0, f"no {kind} ask reached"
    failures = [f for r in counted for f in r.failures if f.startswith(kind + ":")]
    assert not failures, failures[:5]


def test_the_body_never_runs_after_termination(counted: list[_Recorder]) -> None:
    failures = [f for r in counted for f in r.failures if f.startswith("the body ran")]
    assert not failures, failures[:5]


def test_a_body_that_ends_the_round_is_followed_by_no_ask() -> None:
    """The body's write satisfies `until`; the loop consults it again, so
    the seat the round had chosen is never asked. The lead is the one ask
    `until` never precedes — a climbing trick is led whatever the predicate
    says — so a body run before the lead sets the flag, the lead is asked,
    and the body run before the next ask ends the trick: those leads are the
    reach witness."""
    body = indent("runs += 1\nasked_last := p\nif runs > 5 { stop := true }")
    recs = []
    game = check(body=body)
    for seed in SEEDS:
        rec = _Recorder(seed)
        play_game(game, random.Random(seed), None, rec, None, on_first_decision=rec.attach)
        recs.append(rec)
    assert sum(r.stopped_leads for r in recs) > 0
    assert sum(r.stopped_asks for r in recs) == 0


# ---------------------------------------------------------------------------
# Misuse probes, and the clause's place in the grammar
# ---------------------------------------------------------------------------


def test_a_clause_without_its_binder_is_a_syntax_error() -> None:
    with pytest.raises(DiagnosticError):
        check_dsl(source().replace("before asking p {", "before asking {"), "hosted")


def test_the_clause_before_until_is_a_syntax_error() -> None:
    src = source().replace(
        "            until (number of players where hand[player] is not empty) <= 1 or stop\n"
        "            before asking p {\n" + COUNTING + "\n            }",
        "            before asking p {\n" + COUNTING + "\n            }\n"
        "            until (number of players where hand[player] is not empty) <= 1 or stop",
    )
    assert "before asking p" in src
    with pytest.raises(DiagnosticError):
        check_dsl(src, "hosted")


def test_a_fused_keyword_is_a_syntax_error() -> None:
    with pytest.raises(DiagnosticError):
        check_dsl(source().replace("before asking p", "beforeasking p"), "hosted")
    with pytest.raises(DiagnosticError):
        check_dsl(source().replace("before asking p", "before askingp"), "hosted")


def test_the_until_stops_at_the_clause() -> None:
    """An `or`-chained `until` does not absorb `before`."""
    game = parse_text(source(), "hosted")
    climbs = [nd for nd in _walk(game) if isinstance(nd, n.ClimbRound)]
    assert len(climbs) == 1 and climbs[0].hosted is not None
    assert isinstance(climbs[0].until, n.BinOp) and climbs[0].until.op == "or"


def test_before_and_asking_stay_ordinary_names() -> None:
    """The two keywords are contextual: a local may still be named either."""
    check(prelude="    let before = 1\n    let asking = before\n    runs := asking")


@pytest.mark.parametrize(
    "form",
    [
        "turns t from 0 over all players until runs > 0 before asking p { runs += 1 } "
        "{ offer to t one of [nop] }",
        "round play_combination from 0 over all players source hand into trick_pile "
        "winner highest_by_trick_order before asking p { runs += 1 }",
    ],
)
def test_the_clause_is_a_climb_clause_only(form: str) -> None:
    with pytest.raises(DiagnosticError):
        check(prelude="    " + form)


def test_the_asked_seat_is_the_binder_not_the_actor() -> None:
    """The plausible misreading `turns w from actor …` inside the body:
    the body is no seat's action, so `actor` there is what it is at the ring
    statement — at a phase's top level, no seat — and never the asked seat.
    The checker refuses it there, exactly as it refuses the same sentence
    written just before the ring."""
    poll = "runs += 1\nturns w from actor over all players until runs > 0 { offer to w one of [nop] }"
    for kw in ({"body": indent(poll)}, {"body": COUNTING, "prelude": "    " + poll}):
        message = refusal(**kw)
        assert "no player is acting" in message, message


def test_under_an_acting_seat_actor_in_the_body_is_that_seat_not_the_asked_one() -> None:
    """Where a player is acting, `actor` in the body names that player at
    every ask, while the binder names each seat as it is asked."""
    game = check(body=indent("runs += 1\nasked_last := actor"), acting="1")
    rec = _Recorder(0)
    pairs: list[tuple[Player, Player]] = []

    def chooser(player: Player, candidates: list[Any], k: int) -> list[Any]:
        assert rec.rs is not None
        if EXPECTED_HOSTED[rec.kind(candidates)]:
            pairs.append((rec.rs.get("asked_last"), player))
        return rec.base(player, candidates, k)

    play_game(game, random.Random(0), None, chooser, None, on_first_decision=rec.attach)
    assert pairs
    assert {read for read, _ in pairs} == {1}
    assert {asked for _, asked in pairs} - {1}


def test_a_gate_reading_a_concealed_hand_is_judged_as_at_the_phase() -> None:
    """A gate is a control position — it decides who is asked, not what they
    may do — and the Hidden Read Owner Guard does not judge control
    positions (issue #755). The body's gate is judged as the same gate
    written before the round, and both are admitted today."""
    gate = "if (number of cards in hand[p] where card.rank is Dragon) > 0 { offer to p one of [nop] }"
    assert _verdict(body=indent(gate)) is True
    outer = gate.replace("hand[p]", "hand[0]").replace("to p", "to 1")
    assert _verdict(body=COUNTING, prelude="    " + outer) is True


def _walk(node: object) -> typing.Iterator[object]:
    if hasattr(node, "__dataclass_fields__"):
        yield node
        for name in node.__dataclass_fields__:
            yield from _walk(getattr(node, name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


# ---------------------------------------------------------------------------
# Axis H — the runtime agrees with resolve, by execution
# ---------------------------------------------------------------------------

# Every row the grid above judges statically, played with resolve's
# `_check_hosted_polls` switched off: a sentence resolve refuses must be
# refused by the runtime's Shadow Guard the moment it executes, and a sentence
# resolve admits must play through with no Shadow Guard firing. Resolve judges
# a static model of what the body executes; the runtime refuses what actually
# executes; a row where the two disagree is a route the model does not hold.
# Each row is (keyword arguments to `source`, whether resolve refuses it).
AGREEMENT_SEEDS = range(6)


def _agreement_rows() -> dict[str, tuple[dict[str, str], bool]]:
    rows: dict[str, tuple[dict[str, str], bool]] = {}
    for kind in STMT_KINDS:
        if kind in SYNTHETIC:
            continue
        stmt, needs = SNIPPETS[kind]
        rows[f"kind-{kind}"] = ({"body": indent(stmt), **needs}, kind in REFUSED)
    for param in REACH_CELLS:
        route, payload = typing.cast(tuple[str, str], param.values)
        if payload in EXPR_PAYLOADS:
            kw = _route_source(route, EXPR_PAYLOADS[payload][0], is_stmt=False)
        else:
            kw = _route_source(route, STMT_PAYLOADS[payload][0], is_stmt=True)
        rows[f"reach-{route}-{payload}"] = (kw, True)
    for route, (_, _, holds_stmts) in ROUTES.items():
        kw = _route_source(route, "runs > 0", is_stmt=False)
        if holds_stmts and route != "direct":
            kw = _route_source(route, "score[0] += 0", is_stmt=True)
        kw["clauses"] = ""
        rows[f"clean-{route}"] = (kw, False)
    for position, (body, extra) in STATE_POSITIONS.items():
        rows[f"state-{position}"] = ({"body": indent(body), "extra": extra}, True)
    for (regime, name), (clauses, body, extra, words) in PRIMITIVE_NAMESPACE_CELLS.items():
        if regime == "declared":
            rows[f"call-{regime}-{name}"] = (
                {"body": indent(body), "extra": extra, "clauses": clauses}, words is not None,
            )
    return rows


AGREEMENT_ROWS = _agreement_rows()

# The refused rows no game can run even with the Hosted Poll judgement off,
# authored by rule. Non-local control (`produce`, `continue to`, `skip to next
# hand`) is refused by its own position Owner Guards in a move type's effect
# and a procedure, and written in the body itself it needs an outcome phase,
# a later sibling phase, and a hand loop the miniature does not have; a
# procedure holds no `round` of any form. Every other refused row executes.
NON_LOCAL = {"Produce", "ContinueTo", "SkipToNextHand"}
ROUND_PAYLOADS = {"TrickRound", "ClimbRound", "outcome_clause"}


def _refused_elsewhere(row: str) -> bool:
    payload = row.rsplit("-", 1)[-1]
    return payload in NON_LOCAL or (row.startswith("reach-run-") and payload in ROUND_PAYLOADS)


def _runtime_verdict(kw: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> str:
    """Play the row with resolve's Hosted Poll judgement off: "static" when
    another check still refuses it, "refused" when the Shadow Guard fires,
    "played" when every seed runs to its end."""
    monkeypatch.setattr(resolve_module, "_check_hosted_polls", lambda game, bag: None)
    try:
        game = check(**kw)
    except DiagnosticError:
        return "static"
    for seed in AGREEMENT_SEEDS:
        try:
            play_game(game, random.Random(seed), None, random_chooser(random.Random(seed)), None)
        except ShadowGuardError as exc:
            assert exc.leaked == "resolve._check_hosted_polls", exc
            return "refused"
    return "played"


def test_the_agreement_rows_cover_every_static_row() -> None:
    """The rows are the grid's own: every statement kind, every reach cell,
    every route's clean control, every `state` position, every declared-regime
    call cell."""
    names = set(AGREEMENT_ROWS)
    assert {f"kind-{k}" for k in STMT_KINDS if k not in SYNTHETIC} <= names
    assert {f"reach-{p.values[0]}-{p.values[1]}" for p in REACH_CELLS} <= names
    assert {f"state-{p}" for p in STATE_POSITIONS} <= names
    assert any(not refused for _, refused in AGREEMENT_ROWS.values())


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize(
    "row", sorted(k for k, (_, refused) in AGREEMENT_ROWS.items() if refused)
)
def test_a_sentence_resolve_refuses_is_refused_when_it_runs(
    row: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row `_refused_elsewhere` names must still be refused by another
    check with the Hosted Poll judgement off, so the set cannot hide a
    sentence that would run.

    red under: drop the `hosting` arm of `execute.execute`, of the `state`
    pronoun's evaluation, or of `narrowing.engine_facts` — the statement, the
    `state`, or the Primitive rows redden."""
    kw, _ = AGREEMENT_ROWS[row]
    expected = "static" if _refused_elsewhere(row) else "refused"
    assert _runtime_verdict(kw, monkeypatch) == expected


@pytest.mark.parametrize(
    "row", sorted(k for k, (_, refused) in AGREEMENT_ROWS.items() if not refused)
)
def test_a_sentence_resolve_admits_plays_through(
    row: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unmarked, so the suite-wide Pin (tests/conftest.py) also fails this
    test on any Shadow Guard constructed and caught on the way.

    red under: leave `RuntimeState.hosting` set once a body has run (drop the
    `finally` of `mechanics._run_hosted_poll`) — the next ask's own statements
    trip the Shadow Guard."""
    kw, _ = AGREEMENT_ROWS[row]
    assert _runtime_verdict(kw, monkeypatch) == "played"
