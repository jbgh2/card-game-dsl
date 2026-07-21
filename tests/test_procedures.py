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
                    of which `Player`, `Rank`, `Rank?` and `Integer` are accepted
                    and the other 14 (plus an unknown name) are rejected at
                    resolve. That sweep READS the registry to decide each cell, so
                    the registry itself is commanded separately by
                    `test_the_supported_domains_are_exactly_player_rank_and_integer`
                    — a member may not join by editing one line. A new entry in
                    KNOWN_TYPE_NAMES fails this test until it is classified.
                B — exhaustive, pinned by `test_stmt_union_is_fully_classified`:
                    11 accepted, 5 rejected, 16 total, and every accepted kind is
                    actually exercised in a body. A new `Stmt` member fails that test
                    until it is classified. `Produces` is accepted with a SPLIT: over
                    a `define` (safe — invoked fresh at each site) but not over a
                    phase outcome (see residual).
                C — exhaustive: all 10 sequence sites and both single-statement
                    slots are exercised; the slots are probed at body length 1
                    (splices) and >1 (walled).
                Hygiene — closed BY CONSTRUCTION, not by walls, and each former
                    defect is pinned as a behaviour: an argument is evaluated once
                    in the caller's context (so one written decision stays one
                    decision; an unused parameter still evaluates its argument; an
                    argument is not re-read after the body mutates it; an argument
                    naming the actor survives an actor-rebinding body), and the body
                    runs in a block (so its bindings do not leak into the caller).
                    The single remaining wall — a body binder shadowing a PARAMETER
                    name, which classification cannot disambiguate — is tested.
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
                  - Every other domain (Suit, Card, Boolean, String, Team,
                    Direction, and the optional form of each bar `Rank?`). Same
                    wall. `Rank?` rather than `Rank` is what the corpus forces:
                    there is no flow narrowing, so a bare `Rank` parameter would
                    reject `block_claim` at the very sites that must pass it.
                    `Integer` LEFT this list when poker_betting's `open_street`
                    forced it — the set grows one forcing game at a time, which
                    is the deferral working rather than a hole closing.
                  - a `round` in a body. It binds its own `outcome`, which the
                    body's pronoun wall cannot yet tell from the caller's.
                  - a `produces:` over a PHASE OUTCOME in a body. Its consumer must be
                    an earlier-executed sibling of the producing phase, and must be the
                    only one — both are facts about where the statement sits, which a
                    splice moves. Same class as the `round` cell: a construct whose
                    validity is positional. (A `produces:` over a `define` is fine.)
                  - a procedure running another procedure (no call graph in v1).
                  - `produce` / `continue to` / `skip to next hand` in a body
                    (non-local control flow out of a spliced block).
                  - `actor` / `action` in a body: rejected unconditionally, even
                    where a `for each player` in the body would bind one, because
                    it would silently mean the loop's player.
                  (The former residual here — a `let`-laundered argument type,
                  `let z = hearts` then `run bump(z)` passing a `Player`
                  parameter — is CLOSED: lets are typed at declaration and the
                  `run`-site check fires through them, pinned by
                  `test_a_run_argument_is_typed_through_a_let` below and the
                  ledger in tests/test_let_typing.py.)
"""

from __future__ import annotations

import random
import typing

import pytest

import cardlang.ast.nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
import cardlang.resolve as resolve_module
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
  state {{ score[player] : Integer = 0  turn : Player = 0  pass_dir : Direction = left }}
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
    # One `run` becomes exactly one statement: a block holding the argument
    # bindings and then the body. One shape serves every statement position.
    stmts = [type(s).__name__ for s in game.phases[0].items]
    assert stmts == ["Movement", "Block"]
    block = game.phases[0].items[1]
    assert isinstance(block, n.Block)
    assert [type(s).__name__ for s in block.body] == [
        "LetStmt", "AssignStmt", "AssignStmt",
    ]
    assert not any(isinstance(nd, n.RunStmt) for nd in _walk(game))


def test_ir_holds_no_trace_of_the_procedure() -> None:
    """A `run` has no IR node, by design: the IR records what runs, not how it was
    spelled. Emitting a placeholder would teach every IR consumer that procedures
    survive the front end."""
    ir = emit(check("    run bump(0)", "procedure bump(who : Player) { score[who] += 1 }"))
    assert "procedures" not in ir
    assert "run" not in repr(ir)


def test_a_procedure_run_twice_expands_twice_and_neither_leaks() -> None:
    """Two expansions in one block are two independent blocks. Each binds its own
    arguments and its own `let`s, and neither can see the other's — which is what a
    procedure means, and what a paste would NOT have given."""
    game = check(
        body="    run bump(0)\n    run bump(1)",
        procs="procedure bump(who : Player) { let step = 1  score[who] += step }",
    )
    assert [type(s).__name__ for s in game.phases[0].items] == [
        "Movement", "Block", "Block",
    ]


def test_a_body_decision_site_is_not_counted_twice() -> None:
    """The pairwise cell that matters: a procedure body holding a decision site, run
    at N places, must contribute N decision sites — not N+1. It is `game.procedures`
    being emptied that makes this true: `openspiel.encoding` walks every dataclass
    field of the `Game`, so a surviving body would be counted on top of the copies
    spliced at the call sites.

    Counting `num_distinct_actions` does NOT test this — the encoder dedupes move
    names and vocab entries, so the width is invariant under duplication and the
    assertion could not fail. Count the decision NODES the walk actually sees."""
    procs = "procedure poll(who : Player) { offer to who one of [pass_move] }"
    viaproc = check("    run poll(0)\n    run poll(1)", procs)
    inline = check(
        "    offer to 0 one of [pass_move]\n    offer to 1 one of [pass_move]", ""
    )
    def offers(g: n.Game) -> int:
        return sum(1 for nd in _walk(g) if isinstance(nd, n.Offer))

    assert offers(viaproc) == offers(inline) == 2
    assert viaproc.procedures == ()


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
_SAMPLE_ARG = {"Player": "0", "Rank": "A", "Rank?": "A", "Integer": "1"}


@pytest.mark.parametrize(
    "type_name", sorted({f"{t}{o}" for t in KNOWN_TYPE_NAMES for o in ("", "?")})
)
def test_every_declarable_type_name_as_a_parameter(type_name: str) -> None:
    """The closed-domain sweep, derived from the registry that defines the universe
    of declarable type names — NOT from the domains the wall happens to handle.
    `payload_type` makes every name generically optional-able, so the domain is
    KNOWN_TYPE_NAMES x {plain, optional}: 18 cells, of which exactly four are
    supported. A new entry in KNOWN_TYPE_NAMES lands here as a failure until it is
    classified as supported or walled."""
    procs = f"procedure f(p : {type_name}) {{ score[0] += 1 }}"
    if type_name in _PROCEDURE_PARAM_DOMAINS:
        check(f"    run f({_SAMPLE_ARG[type_name]})", procs)  # accepted
    else:
        rejects("    run f(0)", procs, "has an unsupported domain")


def test_the_supported_domains_are_exactly_player_rank_and_integer() -> None:
    """The commanded column for the sweep above, which reads the registry to
    decide each cell and so cannot command it. Every member is here because a
    corpus game forces it; the set grows one forcing game at a time.

    `Rank?` is the form the corpus forces, not `Rank`: Coup's proven-claim swap
    takes both a literal character (`run prove_claim(actor, Duke)`) and the block
    claim, which is `Rank?` because "no block" is a real state. The call sites sit
    inside `if block_claim is not none`, but there is no flow narrowing, so a bare
    `Rank` parameter would reject the very argument the block sites must pass.

    `Integer` is forced by `poker_betting`'s `open_street(bet_size)`, the
    procedure that opens a betting street at a given bet size — the five street
    resets across Leduc and Stud are one shape differing in one integer, which is
    a parameter or it is nothing. Nothing about an Integer argument strains the
    construct: a procedure argument is an arbitrary expression the caller
    evaluates once, never a value an action space enumerates, and a `function`
    parameter has always accepted Integer. The gap was which games existed, not a
    design position."""
    assert _PROCEDURE_PARAM_DOMAINS == {"Player", "Rank", "Rank?", "Integer"}


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
    "RepeatUntil", "IfStmt", "AsBlock", "Turns", "LetStmt", "AssignStmt",
    "Offer", "Produces",
}
_BODY_REJECTED = {"Produce", "ContinueTo", "SkipToNextHand", "RunStmt", "Round"}

# Synthetic: no grammar production builds these, so no source program — and no
# procedure body — can contain one. `Block` is what `expand` turns a `run` INTO.
_BODY_SYNTHETIC = {"Block"}


def test_stmt_union_is_fully_classified() -> None:
    """The static pin that makes Axis B exhaustive rather than a sample: every
    statement kind is accepted in a body, walled out of one, or synthetic (not
    writable at all). A new `Stmt` member fails here until someone decides which.

    The three-way split matters. `Block` is a real `Stmt` the runtime and the IR must
    handle, but it is unreachable from source — folding it into "accepted" would
    claim a body-content cell that no test could ever exercise, and folding it into
    "rejected" would claim a wall that can never fire. Both are the vacuous-ledger
    trap this file exists to avoid."""
    union = {t.__name__ for t in typing.get_args(n.Stmt)}
    assert _BODY_ACCEPTED | _BODY_REJECTED | _BODY_SYNTHETIC == union
    assert not (_BODY_ACCEPTED & _BODY_REJECTED)
    assert not (_BODY_SYNTHETIC & (_BODY_ACCEPTED | _BODY_REJECTED))


def test_a_synthetic_block_is_not_writable_from_source() -> None:
    """The claim `_BODY_SYNTHETIC` makes, checked rather than asserted."""
    from cardlang.parse import parse_text

    for spelling in ("block { score[0] += 1 }", "{ score[0] += 1 }"):
        with pytest.raises(DiagnosticError):
            parse_text(GAME.format(body=f"    {spelling}", procs=""), "probe")


def test_a_run_is_capacity_checked_exactly_as_the_inline_text() -> None:
    """The property this whole file names, at the one gate that reasons about the
    SHAPE of a statement rather than its contents.

    Encoding an expansion as `if true { … }` would tell the deck-capacity gate the
    body was CONDITIONAL — it carries `max(then, else)` across a conditional, because
    one may be skipped. So a procedure that refilled the deck would not reset the
    gate's running total, and the same program would be ACCEPTED written inline and
    REJECTED written as a `run`. A real `Block` node says what is true: an
    unconditional sequence."""
    game = """
game G {{
  players: 4
  direction: clockwise
  max_length: 20
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    deal 13 cards from deck to each hand
{reset}
    deal 13 cards from deck to each hand
  }}
  winner: highest score
}}
{procs}
"""
    # A deck refill resets usage — inline, and identically through a `run`.
    check_dsl(game.format(reset="    move all cards to deck", procs=""), "probe")
    check_dsl(
        game.format(
            reset="    run reset_deck()",
            procs="procedure reset_deck() { move all cards to deck }",
        ),
        "probe",
    )
    # ...and the gate still SEES the deals inside a body: falling through to the
    # default would have made it blind to them, which is the same defect pointing the
    # other way.
    with pytest.raises(DiagnosticError):
        check_dsl(
            game.format(
                reset="    run greedy()",
                procs="procedure greedy() { deal 13 cards from deck to each hand }",
            ),
            "probe",
        )


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


def test_every_accepted_body_statement_kind_is_exercised() -> None:
    """The accepted side of Axis B, ALL of it. `test_stmt_union_is_fully_classified`
    proves the two sets partition the union; this proves the accepted set is really
    accepted. Without it the 11 "accepted" rows were a whitelist read off the
    implementation, with only 7 of them ever executed — the pattern the audit skill
    names explicitly (a domain measured against the wall that implements it)."""
    game = check(
        body="    run window(0)",
        procs="""
procedure window(who : Player) {
  let seat = who
  repeat until score[seat] > 0 {
    offer to seat one of [pass_move]
    score[seat] += 1
  }
  if score[seat] > 0 { score[seat] += 0 } else { score[seat] += 1 }
  as seat { move chosen one card from hand[seat] to pile }
  turns w from seat over all players until score[seat] > 100 { score[w] += 0 }
  for each player q: score[q] += 0
  for each suit s: score[0] += 0
  each player simultaneously: move chosen 1 cards from hand[player] to pile
  rotate pass_dir through [left, across, right, hold]
  reveal one card from hand[seat]
  shuffle deck
}
""",
    )
    exercised = {type(nd).__name__ for nd in _walk(game) if isinstance(nd, typing.get_args(n.Stmt))}
    # Produces needs a `define`, so it gets its own body below; everything else here.
    assert _BODY_ACCEPTED - {"Produces"} <= exercised, _BODY_ACCEPTED - {"Produces"} - exercised


def test_a_produces_over_a_define_is_accepted_in_a_body() -> None:
    """The 11th accepted kind — but only over a DEFINE. A define is invoked fresh at
    each site and carries no ordering or uniqueness rule, so a splice cannot break it.
    A `produces:` over a PHASE OUTCOME is a different animal; see the test below."""
    check(
        body="    run pick(0)",
        procs="""
define d -> { Won(Player) | Lost } { produce Won(0) }
procedure pick(who : Player) {
  d produces:
    Won(w) { score[w] += 1 }
    Lost { score[who] += 0 }
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
    assert [type(s).__name__ for s in game.move_types[0].effect] == ["Block"]


def test_any_procedure_fits_a_for_each_slot() -> None:
    """`for each <role> <b>: <stmt>` holds ONE statement, not a braced block. That
    does not constrain what can be run there, because an expansion IS one statement
    — a block. A procedure of any length fits, with no special case and no wall."""
    game = check(
        "    for each player q: run bump(q)",
        "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
    )
    assert game.procedures == ()


def test_a_run_may_not_be_an_each_simultaneously_body() -> None:
    """...but NOT `each <role> simultaneously:`, and that is not a special case for
    procedures — it is the form's own body rule, enforced at the surface.

    The form runs exactly one chosen movement per player: it must snapshot every
    player's selection against the state BEFORE the block and apply them together
    (that is what makes a Hearts pass atomic — nobody sees a passed card before
    choosing their own), and a snapshot is only defined for a chosen movement. The
    executor asserts that; without this wall nothing would check it, so any other
    body would compile and die on a bare assert. An expansion is a block, never a
    bare movement, so `run` makes that reachable from a program that looks entirely
    reasonable: `each player simultaneously: run pass_card(player)`.

    Pinning that exact line as COMPILING — and never running it — would pin the
    bug. A test that pins the bug is worse than no test."""
    rejects(
        "    each player simultaneously: run bump(player)",
        "procedure bump(who : Player) { score[who] += 1 }",
        "runs one chosen movement per player and nothing else",
    )


# Every body shape `each <role> simultaneously:` can be given, and what must happen.
# The legal one is Hearts'; the rest are the executor's five requirements, one per
# row, each naming the requirement it violates.
_SIMULTANEOUS_BODIES = [
    ("move chosen 3 cards from hand[player] to pile", None),
    ("score[player] += 1", "it must be a movement"),
    ("move 3 cards from hand[player] to pile", "must be `chosen`"),
    ("move chosen one card from hand[player] to pile", "countable number"),
    ("move chosen all cards from hand[player] to pile", "countable number"),
]


@pytest.mark.parametrize("body,why", _SIMULTANEOUS_BODIES)
def test_each_simultaneously_body_shapes(body: str, why: str | None) -> None:
    """The wall is the FORM's, not the procedure's: `each player simultaneously:
    score[player] += 1` was equally broken, and equally accepted, long before `run`
    existed — it just died on a bare assert instead of getting a diagnostic.

    The keyword-amount rows are why this table exists. The first version of this wall
    was hand-written against the FIRST of the executor's five requirements
    (`isinstance(Movement) and mode == "chosen"`), so `move chosen one card …` sailed
    through the checker and hit the assert anyway. The requirement now lives in ONE
    place — `nodes.simultaneous_body_error` — which resolve rejects with and the
    executor asserts against, so the two cannot drift. A checker that mirrors an
    executor's asserts by hand will always mirror some of them."""
    src = GAME.format(body=f"    each player simultaneously: {body}", procs="")
    if why is None:
        check_dsl(src, "probe")
    else:
        with pytest.raises(DiagnosticError) as excinfo:
            check_dsl(src, "probe")
        assert why in str(excinfo.value)


def test_the_wall_and_the_executor_read_the_same_requirement() -> None:
    """The pin that keeps them from drifting apart again: both consult the one
    predicate, and neither restates it."""
    import inspect

    from cardlang.runtime import execute

    assert "simultaneous_body_error" in inspect.getsource(execute._pass_selection)
    assert "simultaneous_body_error" in inspect.getsource(resolve_module._validate_refs)


def test_a_run_in_a_single_statement_slot_still_runs_the_whole_body() -> None:
    """...and every statement of it. A slot that silently kept only the first would
    be the accepted-but-ignored class."""
    game = check(
        "    for each player q: run bump(q)",
        "procedure bump(who : Player) { score[who] += 1  score[who] += 2 }",
    )
    result = play_game(game, random.Random(0), None)
    assert result.scores == {0: 3, 1: 3, 2: 3}


# ---------------------------------------------------------------------------
# Hygiene — by construction, not by wall
#
# Arguments are bound by VALUE, once, in the caller's context, and the body runs
# in a block. Between them those two facts close a class of silent-wrong-answer
# defects that a by-name splice has and that no set of walls covers cleanly. Each
# test below is a defect that WAS reachable and is now impossible.
# ---------------------------------------------------------------------------


def _choose_nodes(game: n.Game) -> int:
    return sum(1 for nd in _walk(game) if isinstance(nd, n.Choose))


def test_one_written_decision_stays_one_decision() -> None:
    """The load-bearing one. A by-name splice copies the argument EXPRESSION to
    every place the body reads its parameter — so one written `choose` became one
    decision PER READ, polled independently, with answers that could differ. The
    author wrote "pick a player"; the runtime asked twice and credited two.

    This is not a style point: it silently changes the game's decision count
    relative to the written text, which is the one thing CLAUDE.md says bounds
    every design choice here."""
    game = check_dsl(
        GAME.format(body="    offer to 0 one of [donate]", procs="")
        .replace(
            "move_type pass_move { effect { } }",
            "move_type donate { effect { run bump(choose integer in 0 .. 1) } }\n"
            "procedure bump(p : Player) { score[p] += 1  score[p] += 2 }",
        ),
        "probe",
    )
    assert _choose_nodes(game) == 1
    # ...and the whole 3 points land on ONE player, every seed.
    for seed in range(6):
        scores = play_game(game, random.Random(seed), None).scores
        assert sorted(scores.values()) == [0, 0, 3], scores


def test_an_unused_parameter_still_evaluates_its_argument() -> None:
    """The mirror of the above: a parameter read ZERO times dropped the argument,
    and its decision, entirely — a written decision that never happened."""
    game = check_dsl(
        GAME.format(body="    offer to 0 one of [donate]", procs="")
        .replace(
            "move_type pass_move { effect { } }",
            "move_type donate { effect { run bump(choose integer in 0 .. 1) } }\n"
            "procedure bump(p : Player) { score[0] += 1 }",
        ),
        "probe",
    )
    assert _choose_nodes(game) == 1


def test_an_argument_is_not_re_read_after_the_body_mutates_it() -> None:
    """By-name substitution re-evaluates the argument at each read, so an argument
    naming state the body then assigns denoted a DIFFERENT player on its second
    read than its first — one argument, two players, inside one call."""
    game = check(
        "    turn := 1\n    run award(turn)",
        "procedure award(p : Player) { score[p] += 10  turn := 0  score[p] += 1 }",
    )
    scores = play_game(game, random.Random(0), None).scores
    assert scores[1] == 11 and scores[0] == 0


def test_a_body_binding_does_not_leak_into_the_caller() -> None:
    """The body runs in a block, so its `let`s scope to it. A bare splice put them
    into the caller's statement sequence, where they shadow forward — a procedure
    binding `target` would silently capture the caller's own `target`, read AFTER
    the `run` site. (State assignments and card movements still persist, of course;
    only the bindings are scoped. That is the difference between a procedure and a
    paste.)"""
    game = check(
        "    let target = 0\n    run bump(1)\n    score[target] += 100",
        "procedure bump(p : Player) { let target = p  score[target] += 1 }",
    )
    scores = play_game(game, random.Random(0), None).scores
    assert scores == {0: 100, 1: 1, 2: 0}


def test_an_argument_naming_the_actor_survives_an_actor_rebinding_body() -> None:
    """`for each player q:` rebinds the acting player — that is how the bound player
    becomes the chooser of a decision in the body — and `actor` READS the acting
    player, so `if q is actor` inside such a loop is true for EVERY q. That trap is
    real and still live for inline text (decisions.md "Single-actor decisions:
    the `as` block", which gives the first-class binder that forecloses it).

    A procedure is immune, and not because of a wall: the argument is evaluated in
    the CALLER's context, before the loop exists, so `run mark(actor)` passes the
    move's actor and the loop cannot shadow it. Coup depends on this at four
    sites."""
    game = check_dsl(
        GAME.format(body="    offer to 0 one of [go]", procs="")
        .replace(
            "move_type pass_move { effect { } }",
            "move_type go { effect { run mark(actor) } }\n"
            "procedure mark(who : Player) "
            "{ for each player q: if q is who { score[q] += 1 } }",
        ),
        "probe",
    )
    scores = play_game(game, random.Random(0), None).scores
    assert scores == {0: 1, 1: 0, 2: 0}  # the actor alone, not all three


def test_a_body_binder_may_not_shadow_a_parameter_name() -> None:
    """The one hygiene wall expansion cannot replace. A body binder sharing a
    PARAMETER's name is ambiguous at classification time — both are `local` — so
    substitution cannot tell them apart. Rejected outright."""
    rejects(
        "    run f(0)",
        "procedure f(who : Player) { let who = 1  score[0] += who }",
        "shadowing its own parameter",
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


def test_a_run_argument_is_typed_through_a_let() -> None:
    """Without typed lets, `let z = hearts` would launder the argument to
    `TAny` and the `run`-site check would pass it — the same wall that had
    just rejected the inline spelling. Lets are typed at declaration, so the
    two spellings agree."""
    rejects(
        "    let z = hearts\n    run f(z)",
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


def test_a_produces_over_a_phase_outcome_is_rejected_in_a_body() -> None:
    """The member of the position-dependent class a first pass missed.

    A phase outcome's consumer must be an EARLIER-executed sibling of the producing
    phase, and there must be exactly ONE of them. Both are facts about *where the
    statement sits* — and a procedure body is spliced into sites the checker cannot
    see when it checks the body, because expansion runs after typecheck.

    Inline, both rules are enforced and both shapes are correctly rejected. Inside a
    procedure they were accepted and then died on a bare assert at play time: run the
    consumer before its producer, or run it twice, and the outcome is missing or
    already popped. Same class as the `round` wall above (a construct whose validity
    depends on position, which a splice moves) — I wrote that wall and classified
    `Produces` as plainly accepted, which was the miss."""
    src = """
game G {
  players: 2
  direction: clockwise
  max_length: 20
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase top {
    deal 2 cards from deck to each hand
    phase decide -> outcome {
      Won(Player) | Lost
    } {
      produce Won(0)
    }
    run consume()
  }
  winner: highest score
}
procedure consume() {
  decide produces:
    Won(w) { score[w] += 1 }
    Lost { score[0] += 0 }
}
"""
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "probe")
    assert "consumes the phase outcome of 'decide'" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Write targets — the last name-bearing field with no wall
# ---------------------------------------------------------------------------


def test_a_write_target_must_classify_as_a_state_variable() -> None:
    """One rule in place of three bespoke walls — one of which nobody had written.

    `:=` / `+=` / `rotate` write persistent state, and that is the only thing they can
    write. Since `AssignStmt.target` is now a `NameRef`, it is classified like every
    read, so the question "what is this name?" is already answered: a binder, a zone, a
    deck value or an unknown name is simply not a state variable, and each is rejected
    by the same rule with the same words.

    Each row below was its own defect before the target was an ordinary name:

    - the TYPO reached the runtime as a bare `KeyError`, because `AssignStmt.name` was
      a bare `str` that no name check in resolve ever walked — it was the only
      name-bearing field in the AST with no wall at all;
    - a binder SHADOWING a state variable made one name mean two things: a read of `x`
      found the binder while `x := 1` wrote the state variable, silently. Classifying
      the target makes that impossible rather than merely detected — the target
      resolves to the binder, and a binder is not assignable;
    - and inside a procedure the split was starker still, because expansion rewrites
      `NameRef`s: it rewrote every READ of a parameter and left the WRITE pointing at a
      global of the same name."""
    check("    turn := 1", "")  # the legal shape
    check("    score[0] += 1", "")  # ...and the indexed one

    rejects("    totaly_score := 1", "", "unresolved name 'totaly_score'")
    for body, procs, what in (
        ("    let x = 1\n    x := 2", "", "it is a binder"),
        ("    let turn = 1\n    turn := 2", "", "it is a binder"),  # shadows a state var
        ("    for each player turn: turn := 1", "", "it is a binder"),
        ("    run f(0)", "procedure f(p : Player) { p := 1 }", "it is a binder"),
        # ...and the one that started this: a parameter shadowing a state variable.
        ("    run f(0)", "procedure f(turn : Player) { turn := 1 }", "it is a binder"),
        (
            "    offer to 0 one of [m]",
            "move_type m(turn : Player) { effect { turn := 1 } }",
            "it is a binder",
        ),
        ("    deck := 1", "", "it is a zone"),  # a cell nobody had considered
    ):
        with pytest.raises(DiagnosticError) as excinfo:
            check(body, procs)
        assert what in str(excinfo.value), body
