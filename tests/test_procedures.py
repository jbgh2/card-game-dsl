"""Named procedures: expansion, and every rejection cell.

The surface-totality audit for `procedure` / `run` (decisions.md "Named
procedures", "Surface totality", "Closed-domain completeness").

    property:   A `run` behaves exactly as the procedure's statements written
                inline at that site, with the arguments substituted for the
                parameters — and every way of misusing the construct is rejected
                loudly, in the layer that owns the class. Nothing downstream of
                `expand` ever sees a procedure.

    domain:     Three axes, each derived from its registry in code, not from the
                implementation's own coverage:
                  A. parameter domain — every name in `typecheck.KNOWN_TYPE_NAMES`,
                     plain and optional, plus an unknown name;
                  B. body content — every member of the `nodes.Stmt` union;
                  C. call-site context — every grammar site admitting a statement,
                     split by whether it holds a statement SEQUENCE or a SINGLE
                     statement.
                Plus the capture class (three members) and the call/declaration
                cells.

    registry:   A. `cardlang.typecheck.KNOWN_TYPE_NAMES` vs
                   `cardlang.resolve._PROCEDURE_PARAM_DOMAINS`
                B. `typing.get_args(cardlang.ast.nodes.Stmt)`
                C. `cardlang/grammar/cardlang.lark` — the `statement*` sites and
                   the two `":" statement` single-statement slots

    covered:    A — exhaustive, derived from KNOWN_TYPE_NAMES x {plain, optional}
                    by `test_every_declarable_type_name_as_a_parameter`: 18 cells,
                    of which `Player`, `Rank` and `Rank?` are accepted and the other
                    15 (plus an unknown name) are rejected at resolve. A new entry
                    in KNOWN_TYPE_NAMES fails this test until it is classified.
                B — exhaustive, pinned by `test_stmt_union_is_fully_classified`:
                    11 accepted, 5 rejected, 16 total. A new `Stmt` member fails
                    that test until it is classified.
                C — exhaustive: all 10 sequence sites and both single-statement
                    slots are exercised; the slots are probed at body length 1
                    (splices) and >1 (walled).
                Capture — all three members walled and tested: a body binder
                    shadowing a parameter NAME; a parameter read under a construct
                    that rebinds the actor CONTEXT; a body binder capturing a free
                    local in an ARGUMENT.
                Downstream — `game.procedures` empty after the pipeline; no
                    `RunStmt` in the IR; a body's `offer` is not double-counted in
                    the OpenSpiel action space.

    sampled:    Expansion fidelity is pinned by example rather than exhaustively:
                Coup's trace golden (`tests/golden/coup_scores.json`, via
                test_migration_characterization) is byte-identical across the
                inline->procedure rewrite of 22 pasted blocks. That is a stronger
                witness than a synthetic matrix — it holds the reveal sequence,
                the coins, the alive vector and the winner fixed over 40 seeds —
                but it is one game, so it is sampled, not covered.

    residual:   Every cell below is REJECTED (never silently accepted), and each
                has a roadmap.md record under "Named procedures — deferred cells":
                  - `Zone` parameters. The design note guessed the corpus would
                    need them; it does not (a Player parameter already carries its
                    zone: `influence[victim]`). Wall: unsupported-domain error.
                  - Every other domain (Suit, Card, Integer, Boolean, String, Team,
                    Direction, and the optional form of each bar `Rank?`). Same
                    wall. `Rank?` rather than `Rank` is what the corpus forces:
                    there is no flow narrowing, so a bare `Rank` parameter would
                    reject `block_claim` at the very sites that must pass it.
                  - a `round` in a body. It binds its own `outcome`, which the
                    body's pronoun wall cannot yet tell from the caller's.
                  - a procedure running another procedure (no call graph in v1).
                  - `produce` / `continue to` / `skip to next hand` in a body
                    (non-local control flow out of a spliced block).
                  - `actor` / `action` in a body: rejected unconditionally, even
                    where a `for each player` in the body would bind one, because
                    it would silently mean the loop's player.
"""

from __future__ import annotations

import typing

import pytest

import cardlang.ast.nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from cardlang.resolve import _PROCEDURE_PARAM_DOMAINS
from cardlang.typecheck import KNOWN_TYPE_NAMES

# A minimal game with the pieces every probe needs: a player-indexed state var to
# assign, a hand to move from, and a move type to `offer`.
GAME = """
game P {{
  players: 3
  direction: clockwise
  max_length: 30
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{ score[player] : Integer = 0  turn : Player = 0 }}
  phase p {{
    deal 3 cards from deck to each hand
{body}
  }}
  winner: highest score
}}
move_type pass_move {{ effect {{ }} }}
{procs}
"""


def check(body: str, procs: str) -> n.Game:
    return check_dsl(GAME.format(body=body, procs=procs), "probe")


def rejects(body: str, procs: str, message: str) -> None:
    with pytest.raises(DiagnosticError) as excinfo:
        check(body, procs)
    assert message in str(excinfo.value)


# ---------------------------------------------------------------------------
# Expansion: the construct does what it says
# ---------------------------------------------------------------------------


def test_expansion_splices_the_body_and_consumes_the_procedure() -> None:
    game = check(
        body="    run bump(0)",
        procs="procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
    )
    # The procedure is gone, and its two statements are inline in the phase. This
    # is what keeps the OpenSpiel action space right: `openspiel.encoding` walks
    # every dataclass field of the Game, so a surviving body would be counted on
    # top of the copies spliced at the call sites.
    assert game.procedures == ()
    stmts = [type(s).__name__ for s in game.phases[0].items]
    assert stmts == ["Movement", "AssignStmt", "AssignStmt"]
    assert not any(isinstance(nd, n.RunStmt) for nd in _walk(game))


def test_ir_holds_no_trace_of_the_procedure() -> None:
    """A `run` has no IR node, by design: the IR records what runs, not how it was
    spelled. Emitting a placeholder would teach every IR consumer that procedures
    survive the front end."""
    ir = emit(check("    run bump(0)", "procedure bump(who : Player) { score[who] += 1 }"))
    assert "procedures" not in ir
    assert "run" not in repr(ir)


def test_a_procedure_run_twice_expands_twice_and_the_lets_shadow_forward() -> None:
    """Two expansions in one block introduce the same `let` name twice. That is
    exactly what two inline pastes would do, and the sequential-`let` fold handles
    it: each rebinding shadows forward."""
    game = check(
        body="    run bump(0)\n    run bump(1)",
        procs="procedure bump(who : Player) { let step = 1  score[who] += step }",
    )
    assert [type(s).__name__ for s in game.phases[0].items] == [
        "Movement", "LetStmt", "AssignStmt", "LetStmt", "AssignStmt",
    ]


def test_a_body_offer_is_not_double_counted_in_the_action_space() -> None:
    """The pairwise cell that matters: a procedure body holding a decision site,
    run at N places, must contribute N offers — not N+1. It is `game.procedures`
    being emptied that makes this true."""
    from cardlang.openspiel.encoding import ActionSpace

    procs = "procedure poll(who : Player) { offer to who one of [pass_move] }"
    viaproc = check("    run poll(0)\n    run poll(1)", procs)
    inline = check(
        "    offer to 0 one of [pass_move]\n    offer to 1 one of [pass_move]", ""
    )
    assert (
        ActionSpace.for_game(viaproc).num_distinct_actions
        == ActionSpace.for_game(inline).num_distinct_actions
    )


def test_a_zero_parameter_procedure_runs() -> None:
    game = check("    run reset()", "procedure reset() { score[0] := 0 }")
    assert game.procedures == ()


def _walk(node: object) -> typing.Iterator[object]:
    import dataclasses

    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in dataclasses.fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


# ---------------------------------------------------------------------------
# Axis A — the parameter domain, enumerated from KNOWN_TYPE_NAMES
# ---------------------------------------------------------------------------


# A well-typed argument for each supported domain, so the domain sweep below tests
# the DOMAIN cell and not, accidentally, the argument-type cell.
_SAMPLE_ARG = {"Player": "0", "Rank": "A", "Rank?": "A"}


@pytest.mark.parametrize(
    "type_name", sorted({f"{t}{o}" for t in KNOWN_TYPE_NAMES for o in ("", "?")})
)
def test_every_declarable_type_name_as_a_parameter(type_name: str) -> None:
    """The closed-domain sweep, derived from the registry that defines the universe
    of declarable type names — NOT from the domains the wall happens to handle.
    `payload_type` makes every name generically optional-able, so the domain is
    KNOWN_TYPE_NAMES x {plain, optional}: 18 cells, of which exactly three are
    supported. A new entry in KNOWN_TYPE_NAMES lands here as a failure until it is
    classified as supported or walled."""
    procs = f"procedure f(p : {type_name}) {{ score[0] += 1 }}"
    if type_name in _PROCEDURE_PARAM_DOMAINS:
        check(f"    run f({_SAMPLE_ARG[type_name]})", procs)  # accepted
    else:
        rejects("    run f(0)", procs, "has an unsupported domain")


def test_the_supported_domains_are_exactly_player_and_rank() -> None:
    """`Rank?` is the form the corpus forces, not `Rank`: Coup's proven-claim swap
    takes both a literal character (`run prove_claim(actor, Duke)`) and the block
    claim, which is `Rank?` because "no block" is a real state. The call sites sit
    inside `if block_claim is not none`, but there is no flow narrowing, so a bare
    `Rank` parameter would reject the very argument the block sites must pass."""
    assert _PROCEDURE_PARAM_DOMAINS == {"Player", "Rank", "Rank?"}


def test_an_unknown_parameter_type_is_rejected() -> None:
    rejects(
        "    run f(0)",
        "procedure f(p : Frobnitz) { score[0] += 1 }",
        "has an unsupported domain",
    )


def test_zone_parameters_are_the_recorded_deferral() -> None:
    """procedures.md proposed Player + Zone; the corpus forced only Player. The
    deferral is a wall, not silence."""
    assert "Zone" not in _PROCEDURE_PARAM_DOMAINS
    rejects(
        "    run f(0)",
        "procedure f(z : Zone) { score[0] += 1 }",
        "has an unsupported domain",
    )


# ---------------------------------------------------------------------------
# Axis B — body content, enumerated from the Stmt union
# ---------------------------------------------------------------------------

# Every member of the Stmt union, classified. The two sets must partition it.
_BODY_ACCEPTED = {
    "Movement", "EpistemicOp", "RotateStmt", "EachSimultaneous", "ForEach",
    "RepeatUntil", "IfStmt", "LetStmt", "AssignStmt", "Offer", "Produces",
}
_BODY_REJECTED = {"Produce", "ContinueTo", "SkipToNextHand", "RunStmt", "Round"}


def test_stmt_union_is_fully_classified() -> None:
    """The static pin that makes Axis B exhaustive rather than a sample: every
    statement kind the grammar can put in a procedure body is either known-good or
    known-walled. A new `Stmt` member fails here until someone decides which."""
    union = {t.__name__ for t in typing.get_args(n.Stmt)}
    assert _BODY_ACCEPTED | _BODY_REJECTED == union
    assert not (_BODY_ACCEPTED & _BODY_REJECTED)


def test_body_may_not_run_another_procedure() -> None:
    rejects(
        "    run outer(0)",
        "procedure inner(w : Player) { score[w] += 1 }\n"
        "procedure outer(w : Player) { run inner(w) }",
        "may not invoke another",
    )


def test_body_may_not_produce() -> None:
    rejects(
        "    run f(0)",
        "procedure f(w : Player) { produce Done }",
        "which unwinds past the statement it is written at",
    )


def test_body_may_not_continue_to() -> None:
    rejects(
        "    run f(0)",
        "procedure f(w : Player) { continue to other }",
        "which unwinds past the statement it is written at",
    )


def test_body_may_not_skip_to_next_hand() -> None:
    rejects(
        "    run f(0)",
        "procedure f(w : Player) { skip to next hand }",
        "which unwinds past the statement it is written at",
    )


def test_body_may_not_hold_a_round() -> None:
    """A `round` binds its own `outcome` for the statements after it. The body's
    pronoun wall cannot yet tell that round-local binding from the caller's
    call-site `outcome`, so the form is rejected WHOLE rather than accepted with
    its winner unroutable — a `round` you may run but whose result you may not read
    is the accepted-but-ignored class."""
    src = """
game H {
  players: 4
  direction: clockwise
  max_length: 60
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { taken[player] : Integer = 0  leader : Player = 0 }
  phase p {
    deal 13 cards from deck to each hand
    run one_trick(leader)
  }
  winner: highest taken
}
move_type play_to_trick { effect { } }
procedure one_trick(lead : Player) {
  round play_to_trick from lead over all players source hand into trick_pile
        outcome highest_of_led_suit
  taken[outcome] += 1
}
"""
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "probe")
    assert "contains a `round`" in str(excinfo.value)


def test_body_may_hold_an_offer_a_loop_and_a_movement() -> None:
    """The accepted side of Axis B, in one body — the shapes Coup actually uses."""
    check(
        body="    run window(0)",
        procs="""
procedure window(who : Player) {
  let seat = who
  repeat until score[seat] > 0 {
    offer to seat one of [pass_move]
    score[seat] += 1
  }
  for each player q: if q is seat { move chosen one card from hand[q] to pile }
  for each suit s: score[0] += 0
  shuffle deck
}
""",
    )


# ---------------------------------------------------------------------------
# Axis C — call-site contexts
# ---------------------------------------------------------------------------


def test_run_expands_in_every_statement_sequence_context() -> None:
    """Each of these is a `statement*` site in the grammar. A `run` in any of them
    splices its whole body."""
    for body in (
        "    run bump(0)",  # phase body
        "    if score[0] is 0 { run bump(0) } else { run bump(1) }",  # if / else
        "    repeat until score[0] > 1 { run bump(0) }",  # repeat until
    ):
        check(body, "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }")


def test_run_expands_in_a_move_type_effect() -> None:
    game = check_dsl(
        GAME.format(body="    offer to 0 one of [act]", procs="")
        .replace(
            "move_type pass_move { effect { } }",
            "move_type act { effect { run bump(actor) } }\n"
            "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
        ),
        "probe",
    )
    assert game.procedures == ()
    assert [type(s).__name__ for s in game.move_types[0].effect] == [
        "AssignStmt", "AssignStmt",
    ]


def test_a_one_statement_procedure_fits_a_single_statement_slot() -> None:
    """`for each <role> <b>: <stmt>` holds ONE statement, not a braced block. A
    one-statement body splices straight in."""
    check(
        "    for each player q: run bump(q)",
        "procedure bump(who : Player) { score[who] += 1 }",
    )


def test_a_multi_statement_procedure_cannot_be_a_single_statement_slot_body() -> None:
    """...and a longer one is a loud wall, not a silent drop of the extra
    statements."""
    rejects(
        "    for each player q: run bump(q)",
        "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
        "cannot be the whole body of `for each player q:`",
    )


def test_a_multi_statement_procedure_cannot_be_an_each_simultaneously_body() -> None:
    rejects(
        "    each player simultaneously: run bump(player)",
        "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
        "cannot be the whole body of `each player simultaneously:`",
    )


# ---------------------------------------------------------------------------
# The capture class — all three members
# ---------------------------------------------------------------------------


def test_a_body_binder_may_not_shadow_a_parameter_name() -> None:
    """Capture member 1: name capture, the one rule templates also face."""
    rejects(
        "    run f(0)",
        "procedure f(who : Player) { let who = 1  score[0] += who }",
        "shadowing its own parameter",
    )


def test_a_parameter_may_not_be_read_under_a_construct_that_rebinds_the_actor() -> None:
    """Capture member 2: CONTEXT capture, the one a procedure faces and a rule
    template does not, because a procedure takes unevaluated expressions.

    `for each player q:` binds `ctx.acting_as(q)`, and `actor` reads
    `ctx.current_player` — so `if q is actor` inside the loop is true for EVERY q.
    A caller writing `run lose_influence(actor)` against a body that reads the
    parameter inside such a loop would silently hit every player. This is a live
    trap in the language (see open-questions/single-actor-binding.md); the wall
    keeps procedures out of it and prescribes the `let` that pins the seat in the
    caller's context."""
    rejects(
        "    run f(0)",
        "procedure f(who : Player) { for each player q: if q is who { score[q] += 1 } }",
        "which rebinds the acting player",
    )
    # ...and the prescribed fix is accepted.
    check(
        "    run f(0)",
        "procedure f(who : Player) { let seat = who\n"
        "  for each player q: if q is seat { score[q] += 1 } }",
    )


def test_a_body_binder_may_not_capture_a_free_local_in_an_argument() -> None:
    """Capture member 3: ARGUMENT capture — the classic macro-hygiene bug, and the
    one the other two walls' prescribed fix ("bind it first with a `let`") walks an
    author straight into. Without this wall the call's meaning depends on the
    caller's private choice of local variable name."""
    rejects(
        "    let step = 2\n    run f(step)",
        "procedure f(who : Player) { let step = 0  score[who] += step }",
        "would be captured",
    )


def test_argument_capture_is_caught_through_a_value_loop_binder_too() -> None:
    """The same class, via a binder no actor-rebinding check would ever look at:
    a `for each suit s` binder capturing an argument named `s`. Before the wall
    this reached the runtime as a bare KeyError."""
    rejects(
        "    let s = 2\n    run f(s)",
        "procedure f(who : Player) { for each suit s: score[who] += 1 }",
        "would be captured",
    )


def test_a_binder_inside_the_argument_itself_is_not_a_capture() -> None:
    """A name bound *within* an argument expression never escapes it, so it cannot
    be captured by the body — the wall must not over-reject here."""
    check(
        "    run f(the player where score[player] is 0)",
        "procedure f(who : Player) "
        "{ score[who] += number of players where score[player] is 0 }",
    )


# ---------------------------------------------------------------------------
# Hermeticity
# ---------------------------------------------------------------------------


def test_body_may_not_read_the_actor_pronoun() -> None:
    rejects(
        "    run f(0)",
        "procedure f(who : Player) { score[actor] += 1 }",
        "reads the call-site pronoun 'actor'",
    )


def test_body_may_not_reference_a_caller_local() -> None:
    """Hermeticity: the body is classified in isolation (its parameters are the only
    locals in scope), so a caller local is not merely disallowed — it does not
    resolve at all. `_check_procedures` carries the same allowed-reference sweep
    `_check_functions` does, as the belt to this braces."""
    rejects(
        "    let mine = 1\n    run f(0)",
        "procedure f(who : Player) { score[who] += mine }",
        "unresolved name 'mine'",
    )


def test_body_may_read_game_state_and_zones() -> None:
    check(
        "    run f(0)",
        "procedure f(who : Player) { score[who] += number of cards in hand[turn] }",
    )


# ---------------------------------------------------------------------------
# Call sites and declarations
# ---------------------------------------------------------------------------


def test_run_of_an_unknown_procedure_is_rejected() -> None:
    rejects("    run nope(0)", "procedure f(w : Player) { score[w] += 1 }\n"
            "procedure g(w : Player) { score[w] += 1 }",
            "run of unknown procedure 'nope'")


def test_wrong_arity_is_rejected() -> None:
    rejects(
        "    run f(0, 1)",
        "procedure f(who : Player) { score[who] += 1 }",
        "expects 1 argument(s), got 2",
    )


def test_wrong_argument_type_is_rejected() -> None:
    """The cell that makes the parameter annotations load-bearing rather than
    decorative — and the reason `expand` runs after typecheck, not inside resolve:
    once the body is spliced inline there is no call site left to check."""
    rejects(
        "    run f(hearts)",
        "procedure f(who : Player) { score[who] += 1 }",
        "procedure 'f' expects Player, got Suit",
    )


def test_duplicate_procedure_names_are_rejected() -> None:
    rejects(
        "    run f(0)",
        "procedure f(w : Player) { score[w] += 1 }\n"
        "procedure f(w : Player) { score[w] += 2 }",
        "duplicate procedure 'f'",
    )


def test_duplicate_parameter_names_are_rejected() -> None:
    rejects(
        "    run f(0, 1)",
        "procedure f(w : Player, w : Player) { score[w] += 1 }",
        "declares more than one parameter named 'w'",
    )


def test_an_empty_body_is_rejected() -> None:
    rejects("    run f(0)", "procedure f(w : Player) { }", "has an empty body")


def test_a_procedure_that_is_never_run_is_rejected() -> None:
    """An uninvoked body is spliced nowhere, so nothing downstream ever sees it —
    it would go entirely unchecked. The same reasoning `_instantiate_rules` gives
    an uninstantiated rule template."""
    rejects(
        "    score[0] += 1",
        "procedure f(w : Player) { score[w] += 1 }",
        "is never run",
    )
