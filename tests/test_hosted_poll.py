"""The Hosted Poll: `before asking <binder> { … }` on a climbing round.

The surface-totality audit for the clause (decisions.md "Off-the-clock
windows", "The climbing form of `round`", "Surface totality").

    property:   A climbing round's Hosted Poll runs its body exactly once
                before every turn and Interrupt Window ask, with its binder
                bound to the seat about to be asked, and never before a Play
                Announcement or once the round has ended; a body whose writes
                end the round is followed by no ask. Every sentence the clause
                accepts is either run so, or refused at resolve: a body
                statement outside the allow-list, a `state.` read, and a
                binder spelled like a name already classifiable where the
                clause is written.

    domain:     Five axes, each derived from its registry in code:
                  A. body statement kind — every member of the `Stmt` union,
                     split three ways: admitted, refused, synthetic;
                  B. nesting — every refused kind inside every admitted
                     container that holds statements (`if`, `as`,
                     `for each`), and inside a procedure the body runs,
                     for the refused kinds a procedure body itself admits;
                  C. pronoun reads — every name in `resolve._PRONOUNS`, read
                     in the body and read by the same statement written
                     before the round: the two agree, but for `state.`,
                     which the body refuses;
                  D. binder spelling — every classification `_classify`
                     can answer for a bare name, spelled as the binder;
                  E. ask moment — every member of `CLIMB_ASK_KINDS`, plus the
                     two moments no ask is made at (after termination, and
                     after a body whose writes end the round), each executed
                     on the miniature fixture below and reached by playout.
                The clause is written on `round climb` only: the trick and
                auction forms carry no Hosted Poll by grammar
                (`test_the_clause_is_a_climb_clause_only`).

    registry:   A, B. `typing.get_args(cardlang.ast.nodes.Stmt)` against
                   `resolve.HOSTED_POLL_ALLOWED` / `resolve.HOSTED_POLL_REFUSED`
                C. `cardlang.resolve._PRONOUNS`
                D. the string literals `cardlang.resolve._classify` returns,
                   scraped from its source
                E. `cardlang.runtime.mechanics.CLIMB_ASK_KINDS`
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
                sampled rather than enumerated.

red under (each planted in the code under guard, run, and reverted):
- axis A/B: delete `n.AsBlock` from `resolve.HOSTED_POLL_ALLOWED` — the
  admitted `AsBlock` cell reddens;
- axis A/B: drop the `_child_nodes` walk into procedure bodies in
  `resolve._check_hosted_polls` — every `via_procedure` cell reddens;
- axis C: delete the `state.` arm of `resolve._check_hosted_polls`;
- axis D: return early from `resolve._check_hosted_binder`;
- axis E: add "announcement" to `mechanics.HOSTED_ASK_KINDS` — the
  announcement cell reddens; drop the second `form.terminated` check in
  `run_decision_round` — the body-ends-the-round cell reddens.
"""

from __future__ import annotations

import ast
import inspect
import random
import textwrap
import typing
from collections import Counter
from typing import Any

import pytest

import cardlang.ast.nodes as n
import cardlang.resolve as resolve_module
from cardlang.diagnostics import DiagnosticError
from cardlang.runtime.errors import OwnerGuardError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.mechanics import CLIMB_ASK_KINDS
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.tichu_combinations import INTERRUPT_DECLINE, WISH_TOKENS
from cardlang.runtime.values import Player

# The miniature: one hand of Tichu-engine climbing tricks, whose Hosted Poll
# counts its own runs and records the seat it was run for. `{prelude}` sits
# before the trick loop, `{binder}` and `{body}` fill the clause, `{procs}` and
# `{extra}` add top-level definitions.
GAME = """
game HostedMini {{
  players: 4
  teams: [[0, 2], [1, 3]]
  direction: counterclockwise
  max_length: 5000
  cards: tichu56
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
    stop          : Boolean = false
    pass_dir      : SeatDirection = left
  }}
  phase play {{
    legal_moves: [play_combination]
    shuffle deck
    deal 14 cards from deck to each hand
    leader := player_holding(Mahjong of special)
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
    for each player q: score[q] += runs
  }}
  winner: highest score
}}
move_type nop {{ effect {{ }} }}
function seat_zero() = 0
{procs}
{extra}
"""

COUNTING = "              runs += 1\n              asked_last := p"


def source(
    body: str = COUNTING, binder: str = "p", prelude: str = "", procs: str = "", extra: str = ""
) -> str:
    return GAME.format(body=body, binder=binder, prelude=prelude, procs=procs, extra=extra)


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
        "round play_combination from p over all players source hand into trick_pile "
        "winner highest_by_trick_order",
        {},
    ),
    "AuctionRound": ("round offering [nop] from p over all players until runs > 0", {}),
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
ALLOWED = {t.__name__ for t in resolve_module.HOSTED_POLL_ALLOWED}
REFUSED = {t.__name__ for t in resolve_module.HOSTED_POLL_REFUSED}

# The expected column, authored as the operator's ruling on issue #776 reads
# it, never read off the implementation's sets above.
EXPECTED_ADMITTED = {
    "IfStmt", "LetStmt", "AssignStmt", "Offer", "AuctionRound", "AsBlock",
    "ForEach", "RunStmt",
}


def test_the_stmt_union_is_partitioned() -> None:
    """Every statement kind is admitted, refused, or synthetic, and the
    ruling's admitted set is the implementation's. A new `Stmt` member fails
    here until someone decides which it is.

    red under: delete any row of `resolve.HOSTED_POLL_REFUSED`."""
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
    the rest hold none (`AuctionRound`'s decisions are move types, whose
    effects the clause does not reach into)."""
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
    assert "may not hold" in message and "(in procedure 'bad')" in message, message


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


@pytest.mark.parametrize("pronoun", sorted(PRONOUN_READS))
def test_a_pronoun_read_in_the_body(pronoun: str) -> None:
    read = PRONOUN_READS[pronoun]
    if pronoun == "state":
        message = refusal(body=indent(read))
        assert "may not read `state.lead_ended_trick`" in message, message
        return
    # The body runs in the round statement's own context, so a read there is
    # judged as the same statement written just before the round: admitted.
    assert _verdict(body=indent(read)) is True
    assert _verdict(body=COUNTING, prelude="    " + read) is True


def test_a_state_read_via_procedure_is_refused() -> None:
    message = refusal(
        body=indent("run peek()"),
        procs="procedure peek() { if state.lead_ended_trick { runs += 1 } }",
    )
    assert "may not read `state.lead_ended_trick` (in procedure 'peek')" in message, message


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
    "function": ("highest_by_trick_order", {}, "shadows a function"),
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
        "round offering [nop] from 0 over all players until runs > 0 before asking p { runs += 1 }",
        "round play_combination from 0 over all players source hand into trick_pile "
        "winner highest_by_trick_order before asking p { runs += 1 }",
    ],
)
def test_the_clause_is_a_climb_clause_only(form: str) -> None:
    with pytest.raises(DiagnosticError):
        check(prelude="    " + form)


def test_the_asked_seat_is_the_binder_not_the_actor() -> None:
    """The plausible misreading `round offering … from actor` inside the body:
    the body is no seat's action, so `actor` there is what it is at the round
    statement — at a phase's top level, no seat — and never the asked seat.
    The poll's `from` then names no seat, and the runtime's seat Owner Guard
    refuses it loudly, exactly as it refuses the same sentence written just
    before the round."""
    poll = "runs += 1\nround offering [nop] from actor over all players until runs > 0"
    for kw in ({"body": indent(poll)}, {"body": COUNTING, "prelude": "    " + poll}):
        game = check(**kw)
        with pytest.raises(OwnerGuardError, match="cannot start a round from None"):
            play_game(game, random.Random(0), None, random_chooser(random.Random(0)), None)


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
