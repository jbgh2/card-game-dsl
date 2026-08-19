"""The `trick_order { }` construct -- the grid, authored red before the grammar.

Issue #250, PR 1: the game-level Trick Order block (rows `trump:` /
`follow_class:` / `card_strength:` over the implicit `card` binder), the
readers the language mints from it (`is_trump(card)`, `follow_class(card)`,
`card_strength(card)`), the two Builtins over the declaration
(`highest_by_trick_order` -- the winner, bare in a round's `winner` slot or
called over a public pile's Arrival Record; `follows_lead(card, pile)` -- the
winner's candidate test made callable), the presence partition guarded in
both directions, and the algorithm (Effective Lead, candidates, First of
Equals). The design is ruled (issue #250: the design proposal and the operator
rulings); the cut-level choices this grid pins follow Hoyle's and the
Architect's PR-1 counsels (issue #250, "Hoyle counsel -- #250 PR 1" and
"Architect counsel -- #250 PR 1"), and the cells that rest on a point still
open for the operator are named under `provisional` below so a different
ruling flips a NAMED set of cells, not a guessed one.

The plan this grid is the work list of: docs/superpowers/plans/2026-08-17-trick-order-pr1.md.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   (1) every combination the `trick_order` grammar accepts is
            implemented (rows typed strictly, readers minted, both Builtins
            in both positions) or refused with the named diagnostic; (2) a
            Trick Order is a pure function of the card and public state
            (rows may read no pronoun, no concealed or actor-relative zone,
            make no choice, call only the row-callable Builtins and the
            readers of earlier rows); (3) the winner vocabulary partitions
            strictly on the block's presence, in both directions; (4) the
            algorithm names the first-played strongest candidate (First of
            Equals) among the trumps if any, else the Effective Lead's class,
            never evaluating strength on a non-candidate, and `follows_lead`
            is that candidate test; (5) every Arrival-Record read names a
            fully public zone statically, and every trick round plays into
            one.
domain:     rows x body type x binder reads x reference direction x call
            target x zone visibility (direct and through a designer
            function); consumer position {slot, call, follows_lead, each
            reader} x block presence; coexistence with game `trump:`, round
            `trump`, every non-gated winner, the excluded call, `early`;
            row presence subsets and the two defaults; the grammar's
            reject-with-replacement twins and absorbers; the pile argument
            shapes x the Arrival-Record calls; the play zone x every
            library zone type; the algorithm's value cells (lead shape x
            trumps played x ties x pile state) and `follows_lead`'s (lead
            state x candidate class); slot/call agreement and the
            metamorphic pin against `highest_trump_or_led_suit`.
registry:   rows -- `TRICK_ORDER_ROWS` (cardlang.builtins.functions), pinned
            equal to `_ROWS` here and to the node's row-key literal
            (`test_row_registry_matches_the_grid`); readers' types --
            `CALL_SIGS[reader].ret`; the winner namespace --
            `TRICK_WINNER_NAMES` partitioned by `TRICK_ORDER_GATED_WINNERS`
            (the excluded set by subtraction); the call namespace --
            `BUILTIN_CALL_FUNCS` partitioned by `TRICK_ORDER_GATED_FUNCS`,
            `TRICK_ORDER_ROW_CALLS` / `TRICK_ORDER_ROW_UNCALLABLE` (every
            member classified, `test_row_callable_partition_is_total`);
            Arrival-Record calls -- `ARRIVAL_RECORD_CALLS` (name -> pile
            argument index); pronouns -- `resolve._PRONOUNS`; zone types --
            `stdlib.zones.LIBRARY_ZONE_TYPES` x `ZONE_PROJECTIONS`
            (`identity_to_all`); early predicates --
            `PRIMITIVE_EARLY_PREDICATES` minus `TRICK_ORDER_EARLY_PREDICATES`;
            the body-type axis is `_BODY_SPELLINGS`, authored (see sampled).
covered:    `test_grammar_cell` (twins, absorbers, placement, empty block,
            duplicate rows/blocks, `trump: 5` / `trump: "spades"`, row order
            and the boundary sentences), `test_row_type_cell` (rows x
            `_BODY_SPELLINGS`), `test_row_hermeticity_cell` (pronouns direct
            + through a function, `choose`, zone reads over every library
            zone type direct + through a function, bare families, count of a
            concealed zone, every `BUILTIN_CALL_FUNCS` member as a row call,
            a Primitive, reader references self/upward/downward direct +
            through a function, the two consumers in a row),
            `test_partition_cell` (with a block: game `trump:`, round
            `trump`, every non-gated winner, the excluded call, `early`, a
            dead block two ways, a live block via each consumer position;
            without: the gated winner bare and with `trump`, every gated
            call, and the existing winners/calls as controls),
            `test_defaults_cell` (missing `trump:` row, `trump: false`, the
            default-strength ranking gate, explicit `rank_value` with no
            ranking, the reworded ranking-gate remedy),
            `test_pile_argument_cell` (`ARRIVAL_RECORD_CALLS` x argument
            shapes), `test_play_zone_cell` (every library zone type as a
            trick round's `into`), the registry pins, the algorithm grid
            (`test_winner_cell`, `test_follows_lead_cell`,
            `test_strength_is_never_read_on_a_non_candidate`,
            `test_first_of_equals_is_the_kernel_rule_for_every_winner`), and
            the end-to-end cells (`test_slot_and_call_agree`,
            `test_block_agrees_with_the_standard_winner`, `test_readers_end_to_end`,
            `test_no_candidate_is_loud_end_to_end`, `test_dealt_pile_has_no_winner`,
            `test_follows_lead_on_the_empty_pile_is_false`), plus the
            ambiguity budget over every accept source
            (tests/test_grammar_ambiguity.py, derived from `_grammar_cells`).
            Skat (issue #250 PR 2) adds no cell and needs none: it is the
            CORPUS witness for cells this grid only spelled synthetically --
            a row reading declared state (`state-var-named-trump`) and a row
            calling a designer function -- executed against a byte-identity
            oracle (tests/test_trick_order_migration.py) rather than against
            an authored expectation.
            A post-grammar framing check over the definition sources alone
            (issue #250) added the crossed reject-habit cells, the
            `trick_order`-as-a-NAME cell and the ambiguity budget; everything
            else it enumerated was already a cell here or a guard in the
            tree.
sampled:    the body-type axis is one spelling per representative
            `cardlang.types` shape (Boolean, Boolean?, Suit, Suit?, none,
            Integer, Integer?, String, Rank, Card, Player, Collection, the
            top) rather than the whole lattice: strict rows compare by type
            equality, the `follow_class:` row routes through
            `typecheck._check_operand` whose coercion domain has its own
            tests. The through-a-function cells use one helper level; deeper
            chains ride the same call-graph walk (`_check_functions`' call
            map). A consumer inside a spliced family-library function is not
            spelled (no library fixture); the guard runs over the resolved
            game after the splice, pinned by the direct cells.
residual:   (1) `trump: card.rank is J` written at GAME level (the row
            outside its block) dies as a bare syntax error at `.` -- loud,
            wrong voice; no reject arm is cheap here (Hoyle counsel PR 1,
            section 1). R4, this ledger owns the record. (2) `trump:
            trick_order { ... }` (the suit dropped) dies at `{` -- loud, wrong
            voice; `trick_order` is not added to NAME's exclusion (a dead
            first parse, not a second parse). R4, ledger. (3) A count read of
            a count-projected zone inside a row (`number of cards in deck`)
            is refused with the concealed-zone guard although the count is
            public by projection -- conservative, no witness; R4, ledger.
            (4) `trick_order { trump: card.suit is spades }` beside `winner
            highest_by_trick_order` is a second spelling of `trump: spades` +
            `highest_trump_or_led_suit` -- both loud about what they mean; the
            glossary's Trick Order entry says which to prefer, no guard; R4,
            ledger. (5) `follows_lead(card, pile)` written bare as the
            LEADER's `where` filter yields no candidate on the empty pile and
            fails in the chooser's channel ("cannot choose 1 of 0
            candidates") -- accepted and recorded, the `follow_ok` shape
            documented as the pattern; the empty-candidate guard belongs to
            the movement, not to this construct (issue #250 framing check
            C24). R3, this ledger owns the record (the movement guard is
            not this change's). (6) `choose` inside a designer function used
            as a `where` filter, and inside a filter directly, is accepted
            today outside any Trick Order (a decision site inside a
            legality computation) -- pre-existing, its own class; `issue #370`. (7) The Tarot Pagat correction
            (#357), named alternate rankings (#360), the two R2s the design
            phase found (#358 the `winner` pronoun mid-trick, #359
            `active_rules` in a hand-rolled phase), and a Primitive winner's
            own order table on a foreign deck (#364) are outside this grid
            by their issues; #350 closes with this construct (mid-trick
            reads of the pile winner are designed surface, pinned by the
            winner-so-far cells). (9) The three reject-with-replacement
            habits -- the colon, the commas, the `=`/`:=` rows -- each have a
            named arm, but the four CROSSED combinations match no arm and die
            as a bare syntax error: loud, in the lexer's voice rather than the
            block's, the same class as residuals (1) and (2). Pinned loud by
            the `habits-*` cells rather than assumed. R4, this ledger owns the
            record: a crossed arm buys a better voice on a sentence nobody has
            written, and the cells fail if one is ever added without the voice
            improving. (10) `TRICK_ORDER_EARLY_PREDICATES` is EMPTY, so the
            admission direction of the `early` gate cannot be exercised --
            only its refusal, which the `with-block-early` cell pins. Recorded
            rather than papered over: a test iterating the empty set would
            pass over zero rows and read as coverage. R4, this ledger owns the
            record; the direction opens when a predicate joins the set with a
            witness. (11) `TRICK_ORDER_EQ: ":=" | "="` is a NAMED terminal
            whose alternatives overlap `ASSIGN_OP`'s `:=` and every anonymous
            `"="` in the grammar (`state_decl`, `let_stmt`, `derived_field`,
            `type_def`, `function_def`, `vis_clause`, `named_arg`). Under
            Earley with the dynamic lexer this resolves by position, and the
            `eq-row-*` cells plus the ambiguity budget exercise it clean; it is
            a stated FORWARD hazard for the LALR tightening the grammar header
            announces, where a named terminal overlapping anonymous literals is
            precisely what breaks. R4, this ledger owns the record: a recorded
            trap, not work -- the reject arm is the point of the terminal, and
            the tightening re-decides it with the rest of the grammar.
            (8) Row-evaluation cost on the legality path: MEASURED, see
            `cost:` below; no memo is built (the epoch-counter memo the repo
            reverted); re-measured by PRs 2 and 3. (12) Three cells assert
            only "syntax error" (`empty-block`,
            `struct-literal-does-not-absorb-the-block`,
            `block-in-phase-body`), which a tree WITHOUT the construct also
            produces -- so none can tell "refused by design" from "not
            implemented", and each passed at base for that reason. Kept,
            because the sentence must stay refused, and recorded here rather
            than counted as coverage: what discriminates is the ACCEPT cells
            beside them, which base cannot pass. R4, this ledger owns the
            record.
ruled:      every cut-level point this grid's cells rest on is ruled (issue
            #250, the operator's PR-1 ruling 5321676867), and each was ruled
            as the cells were authored, so no cell flipped: the `trump:` row
            is REQUIRED and `trump: false` is the no-trump spelling; `trump:`
            and `card_strength:` type strictly, only `follow_class:` coerces,
            `TAny` refused; a row reads no `_PRONOUNS` member and makes no
            `choose`, directly or through a helper, while declared state
            variables stay readable; the row-callable Builtin surface is an
            allow-list with its complement listed; the pile argument of every
            Arrival-Record call is a static identity-to-all zone reference at
            resolve and every trick round's play zone is one, both tightening
            the EXISTING call form; `early` is refused beside the block
            winner; the winner slot has two contracts keyed by
            `TRICK_ORDER_GATED_WINNERS`, both dispatched by `value_function`;
            the call form emits no `trick` trace.
cost:       the legality path evaluates a row per candidate per decision.
            MEASURED per Doppelkopf playout, base and head INTERLEAVED (three
            alternating reps of 20 games each on one machine, front end
            outside the clock, median): base 61.4 ms/game, head 94.7 --
            **1.54x**, against the 1.5x the Architect's prototype measured
            (62 -> 92) and the operator accepted.
            The dominant cost is the number of ROW EVALUATIONS on the follow
            filter, not the weight of any one row: `follow_ok` asks
            `follows_lead` once per candidate per decision, and each ask
            walks the pile. Counted over three games: 34,899 row evaluations,
            of which 33,307 are the follows path. `card_strength` runs 440
            times and NEVER on that path -- strength is a winner-path fact,
            which is why the banded row a designer writes does not drive the
            cost. An earlier reading of this ledger said it did; it was wrong,
            and the number it explained (1.85x) was the cost of projecting
            each arrival through BOTH rows on every ask, before the lazy
            Effective Lead landed.
            No memo is built -- none is sound without an epoch counter, and
            this repo built and reverted that one already; the measurement is
            the record.
            RE-MEASURED on Skat (issue #250 PR 2, the same method: three
            alternating reps of 6 games, medians): base 212.7 ms/game, head
            220.4 -- **1.04x**, on rows that READ STATE, which Doppelkopf's do
            not, and 55,585 row evaluations per game (30,330 `trump:`, 24,529
            `follow_class:`, 726 `card_strength:` -- again almost none on the
            follows path's account of strength) against Doppelkopf's 34,899
            over three games. Two things make the ratio smaller rather than
            larger, and neither is the construct getting cheaper. Skat's
            playout is mostly NOT tricks -- thirty-six hands of Reizen
            auction, declaration offers and scoring dilute the legality path
            that Doppelkopf's playout is nearly all of. And Skat's baseline
            was not a cheap read: `skat_follow_ok` scanned the whole hand
            natively on every candidate, so the delta measures rows against a
            comparable scan rather than against nothing. 1.54x stands as the
            figure for a trick-dominated game; neither number motivates a
            memo.
Born red (the bare run, `TRICK_ORDER_GRID_BARE=1`, on main 8a722cd before any
implementation): `285 failed, 13 passed in 4.57s` -- every block-bearing cell
dies at the block's own line (verified: each syntax error's line is the line
holding `trick_order` or `trump: 5` / `trump: "spades"`), the without-block
gated cells die as "call to unknown function" / "is not a trick winner
function", the two ranking-gate remedy cells lack the block's name, and the
eleven tightening cells (the existing call form over a computed or concealed
pile, a trick round into a non-public zone) check CLEAN today -- accepted-
then-crashes and an unwitnessed leak, the reason they are cells. The 13 green
are the controls, the placement cells whose refusal predates the construct,
the existing call form's accept cells, and the First of Equals sweep (whose
red-under is executed in its docstring). The designed-to-flip cells ride
strict xfail marks constrained to their designed failure
(`raises=AssertionError` for a static cell, `DiagnosticError` for an
end-to-end cell whose fixture could not parse yet, `ImportError` /
`AttributeError` for a cell over an engine API that did not exist yet). Every
cell has flipped, so no mark remains: the grid is green unmarked, and the
born-red counts above are its provenance, carried in the git log rather than
in a skip.
"""

from __future__ import annotations

import importlib
import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pytest

from cardlang.builtins import functions as F
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.resolve import _PRONOUNS
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import Card
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, identity_to_all

# --- the row table, authored; reconciled against the registry once it exists --

# (row key, reader). The row's required body type is CALL_SIGS[reader].ret.
_ROWS: tuple[tuple[str, str], ...] = (
    ("trump", "is_trump"),
    ("follow_class", "follow_class"),
    ("card_strength", "card_strength"),
)
_ROW_KEYS = tuple(k for k, _ in _ROWS)
_READERS = tuple(r for _, r in _ROWS)
_ORDER = {k: i for i, k in enumerate(_ROW_KEYS)}

# The two Builtins over the declaration, and the winner slot's gated member.
_CONSUMERS = ("highest_by_trick_order", "follows_lead")
_GATED_WINNERS = frozenset({"highest_by_trick_order"})
_GATED_FUNCS = frozenset(_CONSUMERS) | frozenset(_READERS)
# The five names as they will stand in BUILTIN_CALL_FUNCS.
_NEW_BUILTINS = _GATED_FUNCS

# Builtins a row may call (pure over their arguments plus a public table;
# read no zone their arguments do not name) and those it may not. Authored
# here from today's BUILTIN_CALL_FUNCS plus the five new names; pinned equal
# to the registry pair once it exists, and total over BUILTIN_CALL_FUNCS.
_ROW_CALLABLE = frozenset(
    {"rank_value", "card_points", "suit_of", "strain_index", "team_of", "top_of", "bottom_of"}
)
_ROW_UNCALLABLE = frozenset(
    {
        "player_holding",  # walks every hand
        "error",  # not a value
        "lines", "neighbor", "has_step", "is_diagonal", "home", "far_row",  # the board
        "highest_trump_or_led_suit",  # the standard winner, excluded beside a block anyway
        "highest_by_trick_order",  # a consumer of every row
        "follows_lead",  # a consumer of every row
    }
)
# name -> the index of its pile argument (the Arrival-Record calls).
_ARRIVAL_RECORD_CALLS = {"highest_by_trick_order": 0, "follows_lead": 1, "highest_trump_or_led_suit": 0}


# --- diagnostics: the needles ------------------------------------------------

P1 = "takes no colon"
P2 = "never comma-separated"
P3_EQ = "not `trump = <expr>`"
P3_ASSIGN = "not `trump := <expr>`"
P4 = "is not a row of `trick_order`"
P5 = "declares one `{key}:` row"
P6 = "a game declares one `trick_order { }` block"
P7 = "by its bare name"
P8 = "declares no `trump:` row"
R1 = "beside a `trick_order { }` block"
R1_FIX = "drop the game-level clause"
# `_resolve_trump`'s dead-clause message. FORBIDDEN beside R1: both guards can
# see a block game's `trump:` clause, and two messages about one defect send
# the designer looking for two problems. R1 owns the cell, so `_resolve_trump`
# returns early on a block game -- and this needle is what makes dropping that
# early return redden something.
DEAD_TRUMP = "is read by no trick round"
R2 = "round `trump` clause beside a `trick_order { }` block"
R3 = "round winner {name} beside a `trick_order {{ }}` block"
R4 = "`highest_trump_or_led_suit(...)` beside a `trick_order { }` block"
R4E = "`early` predicates read the literal led suit"
R5 = "reads the game's `trick_order { }` block, but this game declares none"
R6 = R5
R7 = "is read by nothing"
R8_UP = "the reader of a row that comes after it"
R8_SELF = "reads its own reader"
R8_CONSUMER = "may not read the Trick Order it defines"
R9 = "reads the pronoun"
R9_CALLSITE = "reads the call-site pronoun"  # the existing `_check_functions` guard, through a helper
R9_CHOOSE = "may not choose"
R10 = "may read only fully public zones"
R11 = "has no acting player"
R12 = "which a piece set has no notion of"
R13 = "may not be called from a Trick Order row"
R14 = "must name a zone"
R14_ID = "does not project identity to every observer"
R15 = "play zone must project identity to every observer"
THROUGH = "through function"
T1_TRUMP = "`trump:` row must type Boolean"
T1_TRUMP_SUIT = "for a fixed trump suit write `trump: card.suit is"
T1_CLASS = "`follow_class:` row must type Suit?"
T1_CLASS_STRING = "never by a class value"
T1_STRENGTH = "`card_strength:` row must type Integer"
T1_ANY = "types as `Any`"
T2 = "declares no `card_strength:` row"
RANKING_GATE = "reads a card's rank strength from ranking:"
RANKING_GATE_BLOCK = "trick_order"
SHADOW_HINT = "move the body into the row"
BOARD = "reads the board"
W1 = "the pile is empty"
W2 = "no card can win"
W_NO_ACTOR = "no deciding actor"


# --- fixtures ----------------------------------------------------------------

_GAME = """
game G {{
  players: 4
  max_length: 2000
  cards: {deck}
  {ranking}
  {clauses}
  {positions}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile  won[player] : PlayerPile<player>{zones} }}
  state {{ score[player] : Integer = 0  leader : Player = 0{state} }}
  phase play {{
    {body}
    score[0] += 1
  }}
  winner: highest score
}}
{tail}
"""

BLOCK = "trick_order { trump: card.suit is hearts }"
# A consumer outside the block, so the block is live (never R7) in cells that
# are about something else.
LIVE = "let w = highest_by_trick_order(pile)\n    score[w] += 1"


def _source(
    *,
    deck: str = "standard52",
    ranking: str = "ranking: aces high",
    clauses: str = "",
    positions: str = "",
    zones: str = "",
    state: str = "",
    body: str = LIVE,
    tail: str = "",
) -> str:
    return _GAME.format(
        deck=deck, ranking=ranking, clauses=clauses, positions=positions,
        zones=zones, state=state, body=body, tail=tail,
    )


def _block(rows: str) -> str:
    return f"trick_order {{ {rows} }}"


def _diagnostics(source: str) -> str | None:
    """None when the source checks clean; else the primary message plus every
    co-reported note, so a cell can pin its own message without depending on
    bag order."""
    try:
        check_dsl(source, "trick_order.cardlang")
    except DiagnosticError as exc:
        assert exc.diagnostic.span is not None, "a diagnostic without a span"
        parts = [exc.diagnostic.message]
        parts.extend(getattr(exc, "__notes__", []) or [])
        return "\n".join(parts)
    return None


def _expect(source: str, *needles: str, forbidden: Iterable[str] = ()) -> None:
    """Empty `needles` means the source must check clean; otherwise every
    needle must appear in the diagnostic text, and no `forbidden` one may."""
    text = _diagnostics(source)
    if not needles:
        assert text is None, f"expected a clean check, got:\n{text}"
        return
    assert text is not None, "expected a diagnostic, the source checked clean"
    for needle in needles:
        assert needle in text, f"expected {needle!r} in:\n{text}"
    for needle in forbidden:
        assert needle not in text, f"did not expect {needle!r} in:\n{text}"


def _expect_any(source: str, *needles: str) -> None:
    """A refusal whose channel is one of several existing guards: at least one
    needle must appear."""
    text = _diagnostics(source)
    assert text is not None, "expected a diagnostic, the source checked clean"
    assert any(n in text for n in needles), f"expected one of {needles!r} in:\n{text}"


@dataclass(frozen=True)
class Cell:
    id: str
    source: str
    needles: tuple[str, ...]  # empty = accept
    forbidden: tuple[str, ...] = ()
    any_of: bool = False  # `needles` are alternatives (one suffices)


def _params(cells: Iterable[Cell]) -> list[Any]:
    return [pytest.param(c, id=c.id) for c in cells]


def _run(cell: Cell) -> None:
    if cell.any_of:
        _expect_any(cell.source, *cell.needles)
    else:
        _expect(cell.source, *cell.needles, forbidden=cell.forbidden)


# =============================================================================
# 1. Grammar and parse: the twins, the absorbers, placement, presence
# =============================================================================


def _grammar_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    add(Cell("colon-block", _source(clauses="trick_order: { trump: card.suit is hearts }"), (P1,)))
    add(Cell("colon-empty-block", _source(clauses="trick_order: { }"), (P1,)))
    add(Cell("comma-two-rows", _source(clauses="trick_order { trump: card.suit is hearts, card_strength: 3 }"), (P2,)))
    add(Cell("comma-one-among-three",
             _source(clauses="trick_order { trump: card.suit is hearts  card_strength: 3, follow_class: card.suit }"), (P2,)))
    add(Cell("eq-row-all", _source(clauses="trick_order { trump = card.suit is hearts }"), (P3_EQ,)))
    add(Cell("eq-row-mixed", _source(clauses="trick_order { trump: card.suit is hearts  card_strength = 3 }"), ("not `card_strength = <expr>`",)))
    add(Cell("assign-row", _source(clauses="trick_order { trump := card.suit is hearts }"), (P3_ASSIGN,)))
    # Separator slips, one cell each. The TRAILING comma is the likeliest --
    # a list habit produces it, and it used to miss the comma arm because the
    # arm's tail demanded a row AFTER the comma -- so it earns the designer's
    # voice; the other three are rarer and stay in the lexer's, recorded in
    # residual (9)'s family rather than assumed.
    add(Cell("separator-trailing-comma",
             _source(clauses="trick_order { trump: card.suit is hearts, }"), (P2,)))
    add(Cell("separator-leading-comma",
             _source(clauses="trick_order { , trump: card.suit is hearts }"),
             ("syntax error",)))
    add(Cell("separator-semicolon",
             _source(clauses="trick_order { trump: card.suit is hearts; card_strength: 3 }"),
             ("syntax error",)))
    add(Cell("row-with-an-empty-body",
             _source(clauses="trick_order { trump: card.suit is hearts  card_strength: }"),
             ("syntax error",)))
    # The three habits CROSSED. Each alone has a named reject arm above; the
    # four combinations match no arm and die as a bare syntax error -- loud,
    # but in the lexer's voice rather than the block's (residual (9)). Pinned
    # LOUD here so the cells are recorded rather than assumed, and so a future
    # crossed arm makes them fail rather than pass silently.
    add(Cell("habits-colon-and-comma",
             _source(clauses="trick_order: { trump: card.suit is hearts, card_strength: 3 }"),
             ("syntax error",)))
    add(Cell("habits-colon-and-eq",
             _source(clauses="trick_order: { trump = card.suit is hearts }"),
             ("syntax error",)))
    add(Cell("habits-comma-and-eq",
             _source(clauses="trick_order { trump: card.suit is hearts, card_strength = 3 }"),
             ("syntax error",)))
    add(Cell("habits-all-three",
             _source(clauses="trick_order: { trump = card.suit is hearts, card_strength := 3 }"),
             ("syntax error",)))
    # `trick_order` is an ordinary NAME outside the clause position (it is not
    # in NAME's exclusion): a zone may be called it, and the clause still
    # resolves. One reading, accepted.
    add(Cell("zone-named-trick_order",
             _source(clauses=BLOCK, zones="  trick_order : Discard"), ()))
    for bad in ("strength", "class", "order", "trumps", "rank", "is_trump", "trumpx", "follow_classcard_strength"):
        add(Cell(f"bad-key-{bad}", _source(clauses=f"trick_order {{ trump: card.suit is hearts  {bad}: 3 }}"), (P4,)))
    for key, body in (("trump", "card.suit is hearts"), ("follow_class", "card.suit"), ("card_strength", "3")):
        rows = "trump: card.suit is hearts  " if key != "trump" else ""
        add(Cell(f"duplicate-row-{key}", _source(clauses=_block(f"{rows}{key}: {body}  {key}: {body}")), (P5.format(key=key),)))
    add(Cell("two-blocks", _source(clauses=f"{BLOCK}\n  {BLOCK}"), (P6,)))
    # The game clause's non-name values (PR 0's residual (4), the grammar's channel today).
    add(Cell("game-trump-int", _source(clauses="trump: 5", body="score[1] += 1"), (P7,)))
    add(Cell("game-trump-string", _source(clauses='trump: "spades"', body="score[1] += 1"), (P7,)))
    # The empty block is entry-plus: a syntax error, the card_points precedent.
    # This and the two placement cells below assert only "syntax error", which
    # is what a tree WITHOUT the construct also produces -- so each passed at
    # base for the wrong reason, and none can distinguish "refused by design"
    # from "not implemented". They are kept (the sentence must stay refused)
    # and recorded in residual (12); their discriminating power comes from the
    # accept cells beside them, which base cannot pass.
    add(Cell("empty-block", _source(clauses="trick_order { }"), ("syntax error",)))
    # Any row order accepts; the reference order is the language's, not the text's.
    add(Cell("row-order-strength-first",
             _source(clauses=_block("card_strength: rank_value(card)  trump: card.suit is hearts")), ()))
    add(Cell("row-order-class-first",
             _source(clauses=_block("follow_class: card.suit  trump: card.suit is hearts  card_strength: 3")), ()))
    # Row boundaries: an expression cannot absorb the next key.
    add(Cell("boundary-else-then-key",
             _source(clauses=_block("follow_class: if card.rank is Q then none else card.suit  trump: card.suit is hearts")), ()))
    add(Cell("boundary-or-then-key",
             _source(clauses=_block("trump: card.suit is hearts or card.rank is Q  card_strength: rank_value(card)")), ()))
    add(Cell("boundary-elif-chain-then-key",
             _source(clauses=_block(
                 "card_strength: if card.rank is Q then 3 elif card.rank is J then 2 else rank_value(card)  "
                 "trump: card.suit is hearts")), ()))
    add(Cell("boundary-call-then-key",
             _source(clauses=_block("trump: card.suit is hearts  card_strength: rank_value(card)  follow_class: card.suit")), ()))
    add(Cell("boundary-suit-literal-then-key",
             _source(clauses=_block("trump: card.suit is spades  follow_class: card.suit")), ()))
    # A state variable named `trump` read inside a row: one reading, accepted.
    add(Cell("state-var-named-trump",
             _source(clauses=_block("trump: card.suit is trump"), state="  trump : Suit? = none"), ()))
    # The absorbers: `card_rank+` and the struct literal.
    add(Cell("ranking-does-not-absorb-the-block",
             _source(ranking="ranking: A K Q J 10 9 8 7 6 5 4 3 2", clauses=BLOCK), ()))
    # Born green (the game-level block fails to parse today, so the body is
    # never reached); its witness: red under dropping `trick_order` from
    # STRUCT_TYPE_NAME's exclusion once the block parses -- the body's
    # one-row block then absorbs as a struct literal and dies as
    # "unknown type 'trick_order'" / "unresolved name 'card'".
    add(Cell("struct-literal-does-not-absorb-the-block",
             _source(clauses=BLOCK, body=f"let x = {BLOCK}\n    {LIVE}"),
             ("syntax error",), forbidden=("unresolved name 'card'", "unknown type")))
    # Placement: a phase body, a piece game, a library.
    add(Cell("block-in-phase-body", _source(body=f"{BLOCK}\n    {LIVE}"), ("syntax error",)))
    # R12 names the kind, and the partition must stay SILENT: a piece game has
    # no gated consumer, so `_check_trick_order_partition` would otherwise
    # co-report R7 on top of it and send the designer after two problems.
    add(Cell("block-in-piece-game",
             "game P {\n  players: 2\n  pieces: xo_marks\n  max_length: 60\n"
             "  trick_order { trump: true }\n"
             "  zones { box : Deck  reserve[player] : PlayerPile<player> }\n"
             "  state { score[player] : Integer = 0 }\n"
             "  phase play {\n    move all pieces from box where piece.side is x to reserve[0]\n"
             "    score[0] += 1\n  }\n  winner: highest score\n}\n",
             (R12,), forbidden=(R7,)))
    return cells


def test_block_in_a_library_is_inexpressible() -> None:
    """`?library_item` has no arm for the block (a game clause, like every
    other): a family library that writes one dies at parse. Green today and
    after; red under: adding `trick_order` to `?library_item`."""
    from cardlang.parse import parse_library

    with pytest.raises(DiagnosticError) as exc:
        parse_library("library L {\n  trick_order { trump: true }\n  function f(c : Card) = c.rank is Q\n}\n", "L.cardlang")
    assert "syntax error" in exc.value.diagnostic.message


@pytest.mark.parametrize("cell", _params(_grammar_cells()))
def test_grammar_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 2. Row typing: rows x body spellings (strict for trump/card_strength,
#    coercion for follow_class, the top refused everywhere)
# =============================================================================

# (type name, spelling, extra state) -- one spelling per representative shape.
_BODY_SPELLINGS: tuple[tuple[str, str, str], ...] = (
    ("Boolean", "card.rank is Q", ""),
    ("Boolean-literal", "true", ""),
    ("Boolean?", "maybe", "  maybe : Boolean? = none"),
    ("Suit", "card.suit", ""),
    ("Suit-literal", "hearts", ""),
    ("Suit?", "if card.rank is Q then none else card.suit", ""),
    ("none", "none", ""),
    ("Integer", "rank_value(card)", ""),
    ("Integer-literal", "3", ""),
    ("Integer?", "n", "  n : Integer? = none"),
    ("String", '"trump"', ""),
    ("Rank", "card.rank", ""),
    ("Card", "card", ""),
    ("Player", "leader", ""),
    # A PUBLIC collection: `hand[0]` types the same but is a concealed read,
    # which resolve's hermeticity guard refuses BEFORE typecheck runs -- the
    # cell would then pin R10 and never observe the type message it exists for.
    # One axis per cell; the concealed-read cells are section 3's.
    ("Collection", "won[0]", ""),
    ("Any", 'if card.rank is Q then "trump" else card.suit', ""),
)

_ACCEPTS = {
    "trump": {"Boolean", "Boolean-literal"},
    "follow_class": {"Suit", "Suit-literal", "Suit?", "none"},
    "card_strength": {"Integer", "Integer-literal"},
}
_TYPE_NEEDLE = {"trump": T1_TRUMP, "follow_class": T1_CLASS, "card_strength": T1_STRENGTH}


def _row_type_cells() -> list[Cell]:
    cells: list[Cell] = []
    for key in _ROW_KEYS:
        for tname, spelling, state in _BODY_SPELLINGS:
            rows = f"{key}: {spelling}" if key == "trump" else f"trump: card.suit is hearts  {key}: {spelling}"
            src = _source(clauses=_block(rows), state=state)
            if tname in _ACCEPTS[key]:
                cells.append(Cell(f"{key}-{tname}", src, ()))
                continue
            needles: tuple[str, ...]
            if tname == "Any":
                needles = (T1_ANY,)
            elif key == "trump" and tname in ("Suit", "Suit-literal"):
                needles = (T1_TRUMP, T1_TRUMP_SUIT)
            elif key == "follow_class" and tname == "String":
                needles = (T1_CLASS, T1_CLASS_STRING)
            else:
                needles = (_TYPE_NEEDLE[key],)
            cells.append(Cell(f"{key}-{tname}", src, needles))
    return cells


@pytest.mark.parametrize("cell", _params(_row_type_cells()))
def test_row_type_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 3. Row hermeticity: pronouns, choose, zones, bare families, calls,
#    reference direction -- direct and through a designer function
# =============================================================================

# One spelling per pronoun, in a Boolean position.
_PRONOUN_SPELLING = {
    "actor": "actor is 0",
    "action": "action.card is card",
    "winner": "winner is 0",
    "state": "state.led_suit is none",
    "active_rules": "active_rules is empty",
}
_HELPER = "function helper(c : Card) = {body}"


def _zone_decl(ztype: str) -> tuple[str, str, str, str]:
    """(positions clause, zone declaration, subscripted/single read, bare read
    or "") for a library zone type."""
    if not LIBRARY_ZONE_TYPES[ztype]:
        return "", f"  z : {ztype}", "z", ""
    if ztype in ("Cascade", "HiddenStack", "Foundation", "Cell"):
        return "positions { col : 1..2 }", f"  z[col] : {ztype}<col>", "z[1]", ""
    return "", f"  z[player] : {ztype}<player>", "z[0]", "z"


def _row_hermeticity_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    # (a) pronouns -- the axis is resolve._PRONOUNS; every member spelled.
    assert set(_PRONOUN_SPELLING) == set(_PRONOUNS), sorted(_PRONOUNS)
    for name in sorted(_PRONOUNS):
        spelling = _PRONOUN_SPELLING[name]
        add(Cell(f"pronoun-{name}-direct", _source(clauses=_block(f"trump: {spelling}")), (R9, f"'{name}'")))
        through = _source(clauses=_block("trump: helper(card)"), tail=_HELPER.format(body=spelling))
        if name in ("actor", "action", "winner"):
            # The existing function hermeticity guard fires first; the cell is
            # already refused today (green), pinned as a member of the class.
            add(Cell(f"pronoun-{name}-through-function", through, (R9_CALLSITE,)))
        else:
            add(Cell(f"pronoun-{name}-through-function", through, (R9, THROUGH)))
    # (b) choose -- direct and through a function.
    add(Cell("choose-direct", _source(clauses=_block("trump: (choose integer in 0 .. 3) > 1")), (R9_CHOOSE,)))
    add(Cell("choose-through-function",
             _source(clauses=_block("trump: helper(card)"), tail=_HELPER.format(body="(choose integer in 0 .. 3) > 1")),
             (R9_CHOOSE, THROUGH)))
    # (c) zone reads over every library zone type: accept iff identity to all.
    for ztype in sorted(LIBRARY_ZONE_TYPES):
        positions, decl, read, bare = _zone_decl(ztype)
        row = f"trump: any card in {read} where card.rank is Q"
        needles: tuple[str, ...] = () if identity_to_all(ztype) else (R10,)
        add(Cell(f"zone-{ztype}-direct", _source(clauses=_block(row), positions=positions, zones=decl), needles))
        through = _source(clauses=_block("trump: helper(card)"), positions=positions, zones=decl,
                          tail=_HELPER.format(body=f"any card in {read} where card.rank is Q"))
        add(Cell(f"zone-{ztype}-through-function", through, needles if not needles else (R10, THROUGH)))
        if bare and identity_to_all(ztype):
            add(Cell(f"zone-{ztype}-bare-direct",
                     _source(clauses=_block(f"trump: any card in {bare} where card.rank is Q"), zones=decl), (R11,)))
            add(Cell(f"zone-{ztype}-bare-through-function",
                     _source(clauses=_block("trump: helper(card)"), zones=decl,
                             tail=_HELPER.format(body=f"any card in {bare} where card.rank is Q")), (R11, THROUGH)))
    # A count read of a count-projected zone: refused (conservative; residual (3)).
    add(Cell("count-of-concealed-zone", _source(clauses=_block("trump: (number of cards in deck) > 10")), (R10,)))
    # (d) every BUILTIN_CALL_FUNCS member as a row call (the axis grows by the
    # five new names; the census pin below keeps the classification total).
    call_spelling = {
        "rank_value": "rank_value(card) > 3",
        "card_points": "card_points(card) > 3",
        "suit_of": "suit_of(card) is hearts",
        "strain_index": "strain_index(card.suit) > 0",
        "team_of": "team_of(0) is 0",
        "top_of": "top_of(pile) is card",
        "bottom_of": "bottom_of(pile) is card",
        "player_holding": "player_holding(card) is 0",
        "error": 'error("no")',
        "lines": "lines(3) is empty",
        "neighbor": "neighbor(0, 0, 0) is 0",
        "has_step": "has_step(0, 0, 0)",
        "is_diagonal": "is_diagonal(0)",
        "home": "home(0) is empty",
        "far_row": "far_row(0) is 0",
        "highest_trump_or_led_suit": "highest_trump_or_led_suit(pile, hearts) is 0",
        "highest_by_trick_order": "highest_by_trick_order(pile) is 0",
        "follows_lead": "follows_lead(card, pile)",
    }
    extra_clause = {"card_points": "card_points { A: 1 }", "team_of": "teams: [[0, 2], [1, 3]]"}
    for name in sorted(_ROW_CALLABLE | _ROW_UNCALLABLE):
        spelling = call_spelling[name]
        clauses = f"{extra_clause.get(name, '')}\n  {_block(f'trump: {spelling}')}"
        if name in _ROW_CALLABLE:
            add(Cell(f"call-{name}", _source(clauses=clauses), ()))
        elif name in _CONSUMERS:
            add(Cell(f"call-{name}", _source(clauses=clauses), (R8_CONSUMER,)))
        elif name in F.BOARD_ONLY_CALL_FUNCS:
            add(Cell(f"call-{name}", _source(clauses=clauses), (R13, BOARD), any_of=True))
        else:
            add(Cell(f"call-{name}", _source(clauses=clauses), (R13,)))
        # through a helper: the same classification, the walk names the function
        if name in ("player_holding", "highest_by_trick_order", "follows_lead"):
            needle = R8_CONSUMER if name in _CONSUMERS else R13
            add(Cell(f"call-{name}-through-function",
                     _source(clauses=_block("trump: helper(card)"), tail=_HELPER.format(body=spelling.replace("card", "c"))),
                     (needle, THROUGH)))
    # A Primitive in a row: uncallable by construction.
    add(Cell("call-primitive", _source(clauses=_block("trump: skat_next_bid(0) > 3")), (R13,)))
    # (e) reader references: self, upward, downward -- direct and through a function.
    add(Cell("reader-self-trump", _source(clauses=_block("trump: is_trump(card)")), (R8_SELF,)))
    add(Cell("reader-self-strength",
             _source(clauses=_block("trump: card.suit is hearts  card_strength: card_strength(card) + 1")), (R8_SELF,)))
    add(Cell("reader-upward-trump-reads-strength", _source(clauses=_block("trump: card_strength(card) > 3")), (R8_UP,)))
    add(Cell("reader-upward-trump-reads-class", _source(clauses=_block("trump: follow_class(card) is hearts")), (R8_UP,)))
    add(Cell("reader-upward-class-reads-strength",
             _source(clauses=_block("trump: card.suit is hearts  follow_class: if card_strength(card) > 3 then none else card.suit")),
             (R8_UP,)))
    add(Cell("reader-downward-strength-reads-trump",
             _source(clauses=_block("trump: card.suit is hearts  card_strength: if is_trump(card) then 100 else rank_value(card)")), ()))
    add(Cell("reader-downward-strength-reads-class",
             _source(clauses=_block("trump: card.suit is hearts  follow_class: card.suit  card_strength: if follow_class(card) is hearts then 9 else 1")), ()))
    add(Cell("reader-downward-class-reads-trump",
             _source(clauses=_block("trump: card.suit is hearts  follow_class: if is_trump(card) then none else card.suit")), ()))
    add(Cell("reader-upward-through-function",
             _source(clauses=_block("trump: helper(card)"), tail=_HELPER.format(body="card_strength(c) > 3")), (R8_UP, THROUGH)))
    add(Cell("reader-self-through-function",
             _source(clauses=_block("trump: helper(card)"), tail=_HELPER.format(body="is_trump(c)")), (R8_SELF, THROUGH)))
    # A designer function named after a reader: the shadowing guard with the block hint.
    add(Cell("designer-function-named-is_trump",
             _source(clauses=BLOCK, tail="function is_trump(c : Card) = c.rank is Q"), ("shadows the native function", SHADOW_HINT)))
    # The binder is `card`: a function's habit `c.rank` is an unresolved name.
    add(Cell("row-binder-is-card", _source(clauses=_block("trump: c.rank is Q")), ("unresolved name 'c'",)))
    return cells


@pytest.mark.parametrize("cell", _params(_row_hermeticity_cells()))
def test_row_hermeticity_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 4. The presence partition, both directions
# =============================================================================

_ROUND = "round play_to_trick from leader over all players source hand into pile winner {winner}{extra}\n    score[winner] += 1"


def _partition_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    excluded_winners = sorted(F.TRICK_WINNER_NAMES - _GATED_WINNERS)
    # WITH a block --------------------------------------------------------------
    add(Cell("with-block-game-trump", _source(clauses=f"trump: spades\n  {BLOCK}"),
             (R1, R1_FIX), forbidden=(DEAD_TRUMP,)))
    add(Cell("with-block-game-trump-non-suit", _source(clauses=f"trump: is_trump\n  {BLOCK}"),
             (R1,), forbidden=("card.suit is is_trump", DEAD_TRUMP)))
    # A block game whose trump clause WOULD have been read by a round, had the
    # round not been a block round: the shape on which `_resolve_trump` has
    # most to say, and must still say nothing.
    add(Cell("with-block-game-trump-and-round",
             _source(clauses=f"trump: spades\n  {BLOCK}",
                     body=_ROUND.format(winner="highest_by_trick_order", extra="")),
             (R1,), forbidden=(DEAD_TRUMP,)))
    add(Cell("with-block-round-trump",
             _source(clauses=BLOCK, body=_ROUND.format(winner="highest_by_trick_order", extra=" trump hearts")),
             (R2,), forbidden=("reads no trump",)))
    for w in excluded_winners:
        add(Cell(f"with-block-winner-{w}", _source(clauses=BLOCK, body=_ROUND.format(winner=w, extra="")),
                 (R3.format(name=w),)))
    # A climbing query beside the block: two card orders in one game, and the
    # engine runs both. PARAMETRIZED over the whole climb registry -- every
    # query carries its own order, whether it reads `ranking:` (president's)
    # or hard-codes one (bigtwo, tichu) -- so a query added to either registry
    # gets a cell without an edit here. The pairing is by game prefix, which is
    # how the two registries are written.
    _CLIMB = ("round climb play_combination from leader over all players "
              "source hand into pile combinations {combos} follows {follows} "
              "until (number of players where hand[player] is not empty) <= 1")
    _CLIMB_NEEDLE = "the climbing round's queries carry their own order"
    for combos in sorted(F.PRIMITIVE_CLIMB_LEADS):
        family = combos.rsplit("_lead_options", 1)[0]
        follows = next(
            f for f in sorted(F.PRIMITIVE_CLIMB_FOLLOWS) if f.startswith(family)
        )
        add(Cell(f"with-block-climb-{combos}",
                 _source(clauses=BLOCK,
                         body=_CLIMB.format(combos=combos, follows=follows) + "\n    " + LIVE),
                 (_CLIMB_NEEDLE, combos)))
        # ... and the same round without a block is untouched by this guard.
        add(Cell(f"without-block-climb-{combos}",
                 _source(body=_CLIMB.format(combos=combos, follows=follows)),
                 (), forbidden=(_CLIMB_NEEDLE,)))
    add(Cell("with-block-excluded-call",
             _source(clauses=BLOCK, body="let w = highest_trump_or_led_suit(pile, hearts)\n    score[w] += 1"), (R4,)))
    add(Cell("with-block-early",
             _source(clauses=BLOCK, body=_ROUND.format(winner="highest_by_trick_order", extra=" early on_play_off_led_suit")),
             (R4E,)))
    add(Cell("with-block-dead", _source(clauses=BLOCK, body="score[1] += 1"), (R7,)))
    add(Cell("with-block-dead-self-referencing-rows",
             _source(clauses=_block("trump: card.suit is hearts  card_strength: if is_trump(card) then 9 else 1"),
                     body="score[1] += 1"), (R7,)))
    # The block's only consumer sits in a procedure nothing runs, so the game
    # never REACHES it: the block is dead, and counting the text rather than
    # what runs would call it live -- `_resolve_trump`'s dead-clause guard
    # takes the same care over the same question.
    add(Cell("with-block-consumer-only-in-an-unreached-procedure",
             _source(clauses=BLOCK, body="score[1] += 1",
                     tail="procedure p() {\n  let w = highest_by_trick_order(pile)\n  score[w] += 1\n}"),
             (R7,)))
    # A consumer in a GAME-LEVEL evaluated position, outside every phase body:
    # the `loser:` terminal selection, which the driver evaluates after the
    # phases finish. Accepted -- it is read, by the engine, every game.
    add(Cell("consumer-only-in-the-loser-selection",
             _source(clauses=BLOCK, body="score[1] += 1",
                     tail="").replace(
                 "  winner: highest score",
                 "  loser: if is_trump(A of hearts) then 0 else 1"),
             ()))

    # --- the refusal half validates WHERE WRITTEN ------------------------
    # A gated or excluded name inside a container nothing invokes is still
    # refused: the refusal guards walk the text, so a dead container's mistake
    # is reported where it sits rather than waiting for someone to invoke it.
    # Both directions of the partition, so the two halves cannot drift into
    # disagreeing about which question they are asking.
    def _dead_define(winner: str) -> str:
        return (
            "define d -> { done }\n{\n  round play_to_trick from leader "
            f"over all players source hand into pile winner {winner}\n"
            "  score[winner] += 1\n  produce done\n}"
        )

    add(Cell("with-block-excluded-winner-in-a-dead-define",
             _source(clauses=BLOCK, body=LIVE, tail=_dead_define("highest_of_led_suit")),
             (R3.format(name="highest_of_led_suit"),)))
    add(Cell("without-block-gated-winner-in-a-dead-define",
             _source(body="score[1] += 1", tail=_dead_define("highest_by_trick_order")),
             (R5,)))

    # --- consumption x reachability -------------------------------------
    # R7 asks "does anything RUN that reads this block", so the answer must
    # follow calls into function and rule bodies -- a consumer in a helper is a
    # consumer -- while an UNREACHED container holds no consumer at all. Both
    # directions, for each container kind, so the reachability notion is pinned
    # rather than the one shape the corpus happens to use.
    _CALL = "let w = highest_by_trick_order(pile)\n    score[w] += 1"
    add(Cell("consumer-in-a-called-function",
             _source(clauses=BLOCK,
                     body="if helper(0) { score[1] += 1 }",
                     tail="function helper(p : Player) = any card in hand[p] where is_trump(card)"),
             ()))
    add(Cell("consumer-in-an-uncalled-function",
             _source(clauses=BLOCK, body="score[1] += 1",
                     tail="function helper(p : Player) = any card in hand[p] where is_trump(card)"),
             (R7,)))
    add(Cell("consumer-in-a-called-function-through-a-second",
             _source(clauses=BLOCK,
                     body="if outer(0) { score[1] += 1 }",
                     tail="function outer(p : Player) = helper(p)\n"
                          "function helper(p : Player) = any card in hand[p] where is_trump(card)"),
             ()))
    _RULE = ("rule OnlyTrumps {\n"
             "  constrains: play_to_trick\n"
             "  applies_when: always\n"
             "  demands: cards in hand where is_trump(card)\n"
             "  if_impossible: hand\n}")
    add(Cell("consumer-in-an-active-rule",
             _source(clauses=BLOCK,
                     body="active_rules: [OnlyTrumps]\n    score[1] += 1",
                     tail=_RULE),
             ()))
    add(Cell("consumer-in-a-never-activated-rule",
             _source(clauses=BLOCK, body="score[1] += 1", tail=_RULE),
             (R7,)))
    # live via each consumer position
    add(Cell("with-block-live-slot", _source(clauses=BLOCK, body=_ROUND.format(winner="highest_by_trick_order", extra="")), ()))
    add(Cell("with-block-live-call", _source(clauses=BLOCK, body=LIVE), ()))
    add(Cell("with-block-live-follows_lead",
             _source(clauses=BLOCK, body="if any card in hand[0] where follows_lead(card, pile) { score[1] += 1 }"), ()))
    for reader, use in (("is_trump", "if any card in hand[0] where is_trump(card) { score[1] += 1 }"),
                        ("follow_class", "if any card in hand[0] where follow_class(card) is hearts { score[1] += 1 }"),
                        ("card_strength", "if any card in hand[0] where card_strength(card) > 3 { score[1] += 1 }")):
        add(Cell(f"with-block-live-{reader}", _source(clauses=BLOCK, body=use), ()))
    # WITHOUT a block -----------------------------------------------------------
    add(Cell("without-block-slot", _source(body=_ROUND.format(winner="highest_by_trick_order", extra="")), (R5,)))
    add(Cell("without-block-slot-with-trump",
             _source(body=_ROUND.format(winner="highest_by_trick_order", extra=" trump hearts")),
             (R5,), forbidden=("reads no trump",)))
    for name in sorted(_GATED_FUNCS):
        use = {
            "highest_by_trick_order": "let w = highest_by_trick_order(pile)\n    score[w] += 1",
            "follows_lead": "if any card in hand[0] where follows_lead(card, pile) { score[1] += 1 }",
            "is_trump": "if any card in hand[0] where is_trump(card) { score[1] += 1 }",
            "follow_class": "if any card in hand[0] where follow_class(card) is hearts { score[1] += 1 }",
            "card_strength": "if any card in hand[0] where card_strength(card) > 3 { score[1] += 1 }",
        }[name]
        add(Cell(f"without-block-call-{name}", _source(body=use), (R6,)))
    # controls: the existing vocabulary, unchanged without a block
    add(Cell("control-standard-winner-inherits-game-trump",
             _source(clauses="trump: hearts", body=_ROUND.format(winner="highest_trump_or_led_suit", extra="")), ()))
    add(Cell("control-no-trump-winner",
             _source(body=_ROUND.format(winner="highest_of_led_suit", extra="")), ()))
    add(Cell("control-standard-call",
             _source(body="let w = highest_trump_or_led_suit(pile, hearts)\n    score[w] += 1"), ()))
    return cells


@pytest.mark.parametrize("cell", _params(_partition_cells()))
def test_partition_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 5. Required row, defaults, the ranking gates
# =============================================================================


def _defaults_cells() -> list[Cell]:
    cells: list[Cell] = []
    add = cells.append
    # P8: the `trump:` row is required (provisional -- see the ledger).
    add(Cell("no-trump-row-class-only", _source(clauses=_block("follow_class: card.suit")), (P8,)))
    add(Cell("no-trump-row-strength-only", _source(clauses=_block("card_strength: rank_value(card)")), (P8,)))
    add(Cell("no-trump-row-class-and-strength",
             _source(clauses=_block("follow_class: card.suit  card_strength: rank_value(card)")), (P8,)))
    add(Cell("trump-false-is-the-no-trump-spelling",
             _source(clauses=_block("trump: false  follow_class: if card.rank is Q then none else card.suit")), ()))
    # T2: the default strength reads ranking:
    add(Cell("default-strength-without-ranking", _source(ranking="", clauses=BLOCK), (T2,)))
    add(Cell("default-strength-with-ranking", _source(clauses=BLOCK), ()))
    add(Cell("explicit-strength-without-ranking",
             _source(ranking="", clauses=_block("trump: card.suit is hearts  card_strength: if card.rank is A then 2 else 1")), ()))
    add(Cell("explicit-rank_value-without-ranking",
             _source(ranking="", clauses=_block("trump: card.suit is hearts  card_strength: rank_value(card)")), (RANKING_GATE,)))
    # The ranking gate's remedy now names the block (the design's C13).
    add(Cell("standard-winner-without-ranking-names-the-block",
             _source(ranking="", clauses="trump: hearts", body=_ROUND.format(winner="highest_trump_or_led_suit", extra="")),
             (RANKING_GATE, RANKING_GATE_BLOCK)))
    add(Cell("rank_value-without-ranking-names-the-block",
             _source(ranking="", body="if any card in hand[0] where rank_value(card) > 3 { score[1] += 1 }"),
             (RANKING_GATE, RANKING_GATE_BLOCK)))
    return cells


@pytest.mark.parametrize("cell", _params(_defaults_cells()))
def test_defaults_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 6. The pile argument (Arrival-Record calls) and every trick round's play zone
# =============================================================================

# (label, argument spelling, zone declaration, expected needle or None)
_PILE_SHAPES: tuple[tuple[str, str, str, str | None], ...] = (
    ("trickpile", "pile", "", None),
    ("playerpile-subscripted", "won[0]", "", None),
    ("discard-single", "z", "  z : Discard", None),
    ("hand-subscripted", "hand[0]", "", R14_ID),
    ("deck", "deck", "", R14_ID),
    ("facedown", "z", "  z : FaceDownPile", R14_ID),
    ("top_of", "top_of(pile)", "", R14),
    ("literal", "5", "", R14),
    ("state-variable", "leader", "", R14),
    ("card-query-count", "number of cards in pile", "", R14),
)


def _pile_argument_cells() -> list[Cell]:
    cells: list[Cell] = []
    for name, idx in sorted(_ARRIVAL_RECORD_CALLS.items()):
        clauses = "" if name == "highest_trump_or_led_suit" else BLOCK
        for label, arg, zdecl, needle in _PILE_SHAPES:
            if name == "highest_by_trick_order":
                body = f"let w = highest_by_trick_order({arg})\n    score[w] += 1"
            elif name == "follows_lead":
                body = f"if any card in hand[0] where follows_lead(card, {arg}) {{ score[1] += 1 }}"
            else:
                body = f"let w = highest_trump_or_led_suit({arg}, hearts)\n    score[w] += 1"
            src = _source(clauses=clauses, zones=zdecl, body=body)
            # The EXISTING call form is tightened by the same guard, which is
            # why it is an axis member and not a control: before issue #250 PR
            # 1 its computed and concealed piles checked clean and died at play
            # time.
            cells.append(Cell(f"{name}-{label}", src, () if needle is None else (needle,)))
    return cells


@pytest.mark.parametrize("cell", _params(_pile_argument_cells()))
def test_pile_argument_cell(cell: Cell) -> None:
    _run(cell)


def _play_zone_cells() -> list[Cell]:
    cells: list[Cell] = []
    for ztype in sorted(LIBRARY_ZONE_TYPES):
        _positions, decl, _read, _bare = _zone_decl(ztype)
        # A round's `into` names a single zone; families need an instance --
        # the trick form's `into NAME` takes a single zone name only, so
        # owner-indexed types are spelled through a single-zone alias where
        # the type allows none... they do not: the round form's play zone is
        # grammatically a bare NAME, so only the singleton types are spellable
        # here; owner-indexed types are covered by the pile-argument cells.
        if LIBRARY_ZONE_TYPES[ztype]:
            continue
        body = ("round play_to_trick from leader over all players source hand "
                "into z winner highest_of_led_suit\n    score[winner] += 1")
        src = _source(zones=decl, body=body)
        ok = identity_to_all(ztype)
        cells.append(Cell(f"into-{ztype}", src, () if ok else (R15,)))
    return cells


@pytest.mark.parametrize("cell", _params(_play_zone_cells()))
def test_play_zone_cell(cell: Cell) -> None:
    _run(cell)


# =============================================================================
# 7. Registry reconciliation (the tables the guards read, pinned by census)
# =============================================================================


def _reg(name: str) -> Any:
    """A registry that does not exist before the implementation: reached by
    name so this module type-checks on the pre-implementation tree and the
    cell fails with AttributeError (the constrained red) until it lands."""
    return getattr(F, name)


def test_every_game_field_is_classified_for_consumption() -> None:
    """`_GAME_FIELD_ROLES` is exhaustive over `n.Game`'s fields, and its
    "root" half is what a consumption question walks.

    The roots were once a list -- the phase bodies, and nothing else -- so a
    game whose only consumer sat in `loser:` (evaluated after the phases
    finish) or in a game-level `state` default (evaluated at setup) was told
    its declaration was read by nothing. A field added to `Game` must land in
    this table, or it silently rejoins that class.

    red under (executed, reverted): drop any key from `_GAME_FIELD_ROLES` --
    this fails naming it."""
    import dataclasses

    from cardlang.ast import nodes as n
    from cardlang.resolve import _GAME_FIELD_ROLES

    fields = {f.name for f in dataclasses.fields(n.Game)}
    assert set(_GAME_FIELD_ROLES) == fields, (
        f"unclassified: {sorted(fields - set(_GAME_FIELD_ROLES))}; "
        f"stale: {sorted(set(_GAME_FIELD_ROLES) - fields)}"
    )
    assert set(_GAME_FIELD_ROLES.values()) == {"root", "phase", "definition", "declared"}
    # The three non-root roles are the ones with a reason to be excluded; every
    # other field is walked, so an inert field can never cost a consumer.
    assert _GAME_FIELD_ROLES["phases"] == "phase"
    assert _GAME_FIELD_ROLES["trick_order"] == "declared"
    assert _GAME_FIELD_ROLES["loser"] == "root"


def test_row_registry_matches_the_grid() -> None:
    """One row table: the registry, the node's key literal, the readers'
    signatures. red under (once green): reorder or rename a row in
    `TRICK_ORDER_ROWS`."""
    from typing import get_args

    from cardlang.ast import nodes as n

    rows = tuple(_reg("TRICK_ORDER_ROWS"))
    assert rows == _ROWS
    assert tuple(get_args(getattr(n, "TrickOrderRowKey"))) == _ROW_KEYS
    for _, reader in rows:
        assert reader in F.BUILTIN_CALL_FUNCS
        assert CALL_SIGS[reader].params == CALL_SIGS["rank_value"].params  # (Card,)


def test_gated_registries_match_the_grid() -> None:
    assert _reg("TRICK_ORDER_GATED_WINNERS") == _GATED_WINNERS
    assert _reg("TRICK_ORDER_GATED_FUNCS") == _GATED_FUNCS
    assert _reg("TRICK_ORDER_GATED_WINNERS") <= F.BUILTIN_TRICK_WINNERS
    assert _reg("TRICK_ORDER_GATED_FUNCS") <= F.BUILTIN_CALL_FUNCS
    # NOT `TRICK_WINNER_NAMES - GATED` -- that restates the expression the
    # registry is DEFINED by and cannot fail. The claim worth pinning is what
    # the subtraction is FOR: the two sides partition the winner namespace,
    # every excluded member is a real registered winner, and the gated one is
    # not among them.
    excluded = _reg("TRICK_ORDER_EXCLUDED_WINNERS")
    assert excluded | _reg("TRICK_ORDER_GATED_WINNERS") == F.TRICK_WINNER_NAMES
    assert not (excluded & _reg("TRICK_ORDER_GATED_WINNERS"))
    assert excluded == {
        "highest_of_led_suit", "highest_trump_or_led_suit",
        "tarot_trick_winner", "belote_trick_winner",
    }
    assert _reg("TRICK_ORDER_EXCLUDED_FUNCS") == {"highest_trump_or_led_suit"}
    assert _reg("TRICK_ORDER_EARLY_PREDICATES") == frozenset()
    assert dict(_reg("ARRIVAL_RECORD_CALLS")) == _ARRIVAL_RECORD_CALLS


def test_row_callable_partition_is_total() -> None:
    """Every Builtin call is classified callable-from-a-row or not; the two
    sets partition BUILTIN_CALL_FUNCS minus the readers (whose callability is
    the reference-order rule) with nothing in both."""
    callable_ = _reg("TRICK_ORDER_ROW_CALLS")
    uncallable = _reg("TRICK_ORDER_ROW_UNCALLABLE")
    assert callable_ == _ROW_CALLABLE
    assert uncallable == _ROW_UNCALLABLE
    assert not (callable_ & uncallable)
    assert callable_ | uncallable | set(_READERS) == F.BUILTIN_CALL_FUNCS


def test_every_arrival_record_call_takes_a_top_pile() -> None:
    """`ARRIVAL_RECORD_CALLS`' comment claims every member carries a `TAny`
    parameter at its pile index -- the Zone handle, uncoerced, so the record
    rides along. Pinned here, because that claim had no test: a member whose
    pile argument were declared `TCollection` would be coerced to elements at
    the boundary and the record would be stripped before the adapter saw it.

    red under (executed, reverted): declare `follows_lead`'s pile
    `TCollection(TCard())` in CALL_SIGS -- this fails naming it."""
    from cardlang.types import TAny

    for name, idx in F.ARRIVAL_RECORD_CALLS.items():
        assert name in F.BUILTIN_CALL_FUNCS, name
        params = CALL_SIGS[name].params
        assert len(params) > idx, f"{name} has no parameter at index {idx}"
        assert isinstance(params[idx], TAny), (
            f"{name}'s pile parameter is {params[idx]}, not the permissive top "
            f"-- the boundary would coerce it and strip the Arrival Record"
        )


def test_new_builtins_are_registered_and_deck_only() -> None:
    """red under (once green): drop one of the five from DECK_ONLY_CALL_FUNCS."""
    assert _NEW_BUILTINS <= F.BUILTIN_CALL_FUNCS
    assert _NEW_BUILTINS <= F.DECK_ONLY_CALL_FUNCS
    assert "highest_by_trick_order" in F.BUILTIN_TRICK_WINNERS
    assert "highest_by_trick_order" not in getattr(F, "TRUMP_READING_WINNERS", frozenset())
    for name in _NEW_BUILTINS:
        assert name in CALL_SIGS


def test_winner_slot_has_two_contracts_keyed_by_registry() -> None:
    """The gated winner is dispatched by `value_function` under the block
    contract (a marker callable over (played, ctx)); every other member of
    TRICK_WINNER_NAMES keeps the uniform contract."""
    from cardlang.runtime import primitives

    marker = getattr(importlib.import_module("cardlang.runtime.trick_order"), "TrickOrderWinner")
    block_contract = {w for w in F.TRICK_WINNER_NAMES if isinstance(primitives.value_function(w), marker)}
    assert block_contract == _reg("TRICK_ORDER_GATED_WINNERS")


# =============================================================================
# 8. The algorithm -- the solved miniature at the Python entry
# =============================================================================


def _api() -> Any:
    from cardlang.runtime import winners

    return winners


def _c(rank: str, suit: str) -> Card:
    return Card(rank, suit)


# Strengths for the fixture: trumps 100+, plain by rank; the Excuse and any
# card the test declares class-less must NEVER be asked (see the guard cell).
_STRENGTH = {"A": 5, "K": 4, "Q": 3, "J": 2, "9": 1, "7": 0}


def _strength_of(card: Card) -> int:
    if card.rank == "Excuse":
        raise AssertionError("strength read on a class-less card")
    if card.suit == "diamonds":  # the fixture's trump suit
        return 100 + _STRENGTH[card.rank]
    return _STRENGTH[card.rank]


def _arr(w: Any, actor: int, card: Card, **kw: Any) -> Any:
    """An `Arrival` for the fixture: `trump` overrides the fixture's trump
    suit (diamonds); `cls` overrides the printed suit (None = class-less)."""
    trump = kw.get("trump")
    cls = kw.get("cls", "printed")
    is_trump = (card.suit == "diamonds") if trump is None else bool(trump)
    follow_class = card.suit if cls == "printed" else cls
    return w.Arrival(actor, card, is_trump, follow_class)


# (id, plays [(actor, card, kwargs)], expected winner | exception needle)
_WINNER_CELLS: tuple[tuple[str, list[tuple[int, Card, dict[str, Any]]], int | str], ...] = (
    ("classed-lead-no-trumps", [(0, _c("A", "hearts"), {}), (1, _c("K", "hearts"), {}), (2, _c("Q", "spades"), {}), (3, _c("J", "hearts"), {})], 0),
    ("classed-lead-no-trumps-later-high", [(0, _c("9", "hearts"), {}), (1, _c("A", "hearts"), {}), (2, _c("K", "hearts"), {})], 1),
    ("classed-lead-tie-first-of-equals", [(0, _c("K", "hearts"), {}), (1, _c("K", "hearts"), {}), (2, _c("9", "hearts"), {})], 0),
    ("classed-lead-tie-later-pair", [(0, _c("9", "hearts"), {}), (1, _c("K", "hearts"), {}), (2, _c("K", "hearts"), {})], 1),
    ("classed-lead-trumps-played", [(0, _c("A", "hearts"), {}), (1, _c("7", "diamonds"), {}), (2, _c("K", "hearts"), {}), (3, _c("9", "diamonds"), {})], 3),
    ("classed-lead-trumps-tie", [(0, _c("A", "hearts"), {}), (1, _c("J", "diamonds"), {}), (2, _c("J", "diamonds"), {})], 1),
    ("trump-lead", [(0, _c("Q", "diamonds"), {}), (1, _c("A", "hearts"), {}), (2, _c("J", "diamonds"), {})], 0),
    ("trump-lead-overtrumped", [(0, _c("J", "diamonds"), {}), (1, _c("A", "hearts"), {}), (2, _c("Q", "diamonds"), {})], 2),
    ("classless-then-classed", [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("K", "hearts"), {}), (2, _c("A", "hearts"), {})], 2),
    ("classless-then-classed-then-trump", [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("K", "hearts"), {}), (2, _c("7", "diamonds"), {})], 2),
    ("classless-then-trump", [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("7", "diamonds"), {}), (2, _c("A", "hearts"), {})], 1),
    ("classed-lead-classless-follower", [(0, _c("K", "hearts"), {}), (1, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (2, _c("9", "hearts"), {})], 0),
    ("all-classless-no-trump", [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("Excuse", "excuse"), {"trump": False, "cls": None})], W2),
    ("single-classless-arrival", [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None})], W2),
    ("empty", [], W1),
    ("mid-trick-winner-so-far", [(0, _c("9", "hearts"), {}), (1, _c("A", "hearts"), {})], 1),
    ("class-remap-follows-as-trump-class",
     # a jack printed spades that the rows call a trump: it beats the led hearts as a trump
     [(0, _c("A", "hearts"), {}), (1, _c("J", "spades"), {"trump": True})], 1),
)


@pytest.mark.parametrize(("plays", "expected"), [(p, e) for _, p, e in _WINNER_CELLS], ids=[i for i, _, _ in _WINNER_CELLS])
def test_winner_cell(plays: list[tuple[int, Card, dict[str, Any]]], expected: int | str) -> None:
    w = _api()
    arrivals = [_arr(w, a, c, **kw) for a, c, kw in plays]
    if isinstance(expected, str):
        with pytest.raises(OwnerGuardError, match=expected):
            w.highest_by_trick_order(arrivals, _strength_of, "highest_by_trick_order")
        return
    assert w.highest_by_trick_order(arrivals, _strength_of, "highest_by_trick_order") == expected


# follows_lead: lead state x candidate. Candidate = (is_trump, follow_class).
_LEADS: dict[str, list[tuple[int, Card, dict[str, Any]]]] = {
    "nothing-led": [],
    "only-classless-led": [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None})],
    "trump-led": [(0, _c("Q", "diamonds"), {})],
    "plain-led": [(0, _c("K", "hearts"), {})],
    "classless-then-plain-led": [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("K", "hearts"), {})],
}
_CANDIDATES: dict[str, tuple[bool, str | None]] = {
    "trump": (True, "diamonds"),
    "same-class-non-trump": (False, "hearts"),
    "other-class": (False, "spades"),
    "classless": (False, None),
    "trump-printed-hearts": (True, "hearts"),  # a class-remapped trump never follows as a heart
}
_FOLLOWS = {
    ("nothing-led", "*"): False,
    ("only-classless-led", "*"): False,
    ("trump-led", "trump"): True,
    ("trump-led", "trump-printed-hearts"): True,
    ("trump-led", "same-class-non-trump"): False,
    ("trump-led", "other-class"): False,
    ("trump-led", "classless"): False,
    ("plain-led", "trump"): False,
    ("plain-led", "trump-printed-hearts"): False,
    ("plain-led", "same-class-non-trump"): True,
    ("plain-led", "other-class"): False,
    ("plain-led", "classless"): False,
    ("classless-then-plain-led", "same-class-non-trump"): True,
    ("classless-then-plain-led", "trump"): False,
    ("classless-then-plain-led", "trump-printed-hearts"): False,
    ("classless-then-plain-led", "other-class"): False,
    ("classless-then-plain-led", "classless"): False,
}


def _follows_cells() -> list[Any]:
    out = []
    for lead in _LEADS:
        for cand in _CANDIDATES:
            expected = _FOLLOWS.get((lead, cand), _FOLLOWS.get((lead, "*")))
            assert expected is not None, (lead, cand)
            out.append(pytest.param(lead, cand, expected, id=f"{lead}-{cand}"))
    return out


@pytest.mark.parametrize(("lead", "cand", "expected"), _follows_cells())
def test_follows_lead_cell(lead: str, cand: str, expected: bool) -> None:
    w = _api()
    arrivals = [_arr(w, a, c, **kw) for a, c, kw in _LEADS[lead]]
    is_trump, cls = _CANDIDATES[cand]
    assert w.follows_lead(is_trump, cls, arrivals) is expected


_SUBSCRIPTED_PILE_GAME = """
game G {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  trick_order { trump: card.suit is hearts }
  zones { deck : Deck  hand[player] : Hand<player>  piles[player] : PlayerPile<player> }
  state { score[player] : Integer = 0 }
  phase play {
    move all cards to deck
    shuffle deck
    deal 1 cards from deck to each hand
    as 0 { move chosen one card from hand[0] to piles[0] }
    as 1 { move chosen one card from hand[1] to piles[0] }
    let w = highest_by_trick_order(piles[0])
    score[w] += 1
  }
  winner: highest score
}
"""


def test_a_subscripted_pile_is_named_and_played() -> None:
    """A FAMILY-subscripted pile is designed surface (the
    `*-playerpile-subscripted` accept cells), and the harness's provenance
    derivation can only see the family NAME -- which instance a call reads is
    a runtime value. So the family has to be expanded into instances before it
    reaches `derive_arrivals`, which refuses a bare family loudly rather than
    deriving [] in silence and certifying nothing.

    This is the executable end of that: a minimal game whose winner is named
    over `piles[0]`, checked and PLAYED, so the subscripted path is exercised
    rather than assumed from the accept cells alone.

    red under (executed, reverted): drop the `is_family` expansion from
    `harness._instance_labels` -- `derive_arrivals`' assert fires on the bare
    family name instead of the proof passing vacuously."""
    result = _play(_SUBSCRIPTED_PILE_GAME, 0)
    assert sum(result.scores.values()) == 1


def test_the_lazy_lead_agrees_with_the_eager_one() -> None:
    """The legality path runs `follows_lead_lazily`, which asks each row only
    where the answer can still change; the grid's cells above test the EAGER
    `follows_lead` over already-projected arrivals. That is two implementations
    of one rule, so their agreement is proven here over the same crossed domain
    rather than assumed -- and the laziness is only sound because a row is
    hermetic, which makes "how many rows ran" unobservable.

    Also counts the row asks, so the saving is a measured fact and not a hope:
    the eager form projects both rows for every arrival, the lazy one stops at
    the Effective Lead.

    red under (executed, reverted): drop the `if cand_is_trump(): return False`
    arm from `winners.follows_lead_lazily` -- `plain-led-trump` and
    `classless-then-plain-led-trump` disagree and this fails naming them."""
    w = _api()
    for lead in _LEADS:
        arrivals = [_arr(w, a, c, **kw) for a, c, kw in _LEADS[lead]]
        plays = [(a.actor, a.card) for a in arrivals]
        by_card = {(a.card.rank, a.card.suit): a for a in arrivals}

        # Each closure binds the loop's value as a DEFAULT, not by capture:
        # a late-binding closure here would silently compare the last
        # candidate against every lead and the pin would prove one cell.
        def is_trump_of(card: Card, table: Any = by_card) -> bool:
            # `_api()` is reached by name so this module imports on a tree
            # without the construct, which leaves `Arrival` untyped here.
            return bool(table[(card.rank, card.suit)].is_trump)

        def class_of(card: Card, table: Any = by_card) -> str | None:
            cls = table[(card.rank, card.suit)].follow_class
            return None if cls is None else str(cls)

        for cand, (cand_trump, cand_cls) in _CANDIDATES.items():
            eager = w.follows_lead(cand_trump, cand_cls, arrivals)
            lazy = w.follows_lead_lazily(
                lambda t=cand_trump: t, lambda c=cand_cls: c,
                plays, is_trump_of, class_of,
            )
            assert eager is lazy, f"{lead} x {cand}: eager={eager} lazy={lazy}"


def test_the_lazy_lead_asks_fewer_rows_than_the_eager_one() -> None:
    """The saving, as a number. A trump lead settles on the first arrival, so
    a pile of any depth costs one `trump` ask and no `follow_class` ask at
    all -- against the eager form's two per arrival.

    red under (executed, reverted): make `effective_lead_facts` project every
    play before scanning -- the counts equalize and this fails."""
    w = _api()
    asked: list[str] = []
    plays = [
        (0, _c("Q", "diamonds")),  # the trump lead: the scan stops here
        (1, _c("A", "hearts")),
        (2, _c("K", "hearts")),
    ]

    def is_trump_of(card: Card) -> bool:
        asked.append("trump")
        return card.suit == "diamonds"

    def class_of(card: Card) -> str | None:
        asked.append("class")
        return card.suit

    lead = w.effective_lead_facts(plays, is_trump_of, class_of)
    assert lead is not None and lead.is_trump
    assert asked == ["trump"], f"the scan asked {asked}, not one trump row"
    # and the candidate's class is never asked under a trump lead
    asked.clear()
    assert w.follows_lead_lazily(
        lambda: True, lambda: (_ for _ in ()).throw(AssertionError("class asked")),
        plays, is_trump_of, class_of,
    ) is True


def test_strength_is_never_read_on_a_non_candidate() -> None:
    """Strength is a candidate's property: the Excuse (class-less) and an
    off-class card are never asked -- PR 5's Tarot leaves the Excuse unranked
    under the default strength, so a read on it would fire `rank_strength`'s
    Owner Guard on a card that can neither lead nor win."""
    w = _api()
    asked: list[Card] = []

    def strength(card: Card) -> int:
        asked.append(card)
        return _strength_of(card)

    plays = [(0, _c("Excuse", "excuse"), {"trump": False, "cls": None}), (1, _c("K", "hearts"), {}),
             (2, _c("Q", "spades"), {}), (3, _c("A", "hearts"), {})]
    arrivals = [_arr(w, a, c, **kw) for a, c, kw in plays]
    assert w.highest_by_trick_order(arrivals, strength, "highest_by_trick_order") == 3
    assert {(c.rank, c.suit) for c in asked} == {("K", "hearts"), ("A", "hearts")}
    # and follows_lead never reads strength at all
    assert w.follows_lead(False, "hearts", arrivals) is True
    assert len(asked) == 2


def test_first_of_equals_is_the_kernel_rule_for_every_winner() -> None:
    """Sweep the class: the two existing Builtin winners get First of Equals
    from `max` keeping the first maximal element -- stated here as the rule
    (a double-pack tie names the EARLIER play), so a rewrite that loses it is
    caught. red under (executed, reverted): `max(reversed(of_suit), ...)` in
    `winners.highest_of_led_suit` -- `1 failed`; on PR #365's tree the same
    plant goes in `winners._strongest`."""
    from cardlang.runtime import winners

    played = [(0, Card("K", "hearts")), (1, Card("K", "hearts")), (2, Card("9", "hearts"))]
    ranks = {"K": 2, "9": 1}
    assert winners.highest_of_led_suit(played, "hearts", None, ranks) == 0
    assert winners.highest_trump_or_led_suit(played, "hearts", None, ranks) == 0
    trumps = [(0, Card("9", "hearts")), (1, Card("K", "clubs")), (2, Card("K", "clubs"))]
    assert winners.highest_trump_or_led_suit(trumps, "hearts", "clubs", ranks) == 1


# =============================================================================
# 9. End to end: slot/call agreement, the metamorphic pin, readers, guards
# =============================================================================

_HAND_ROLLED = """
game G {{
  players: 4
  max_length: 2000
  cards: {deck}
  ranking: {ranking}
  {clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile  won[player] : PlayerPile<player> }}
  state {{ score[player] : Integer = 0  leader : Player = 0 }}
  phase play {{
    move all cards to deck
    shuffle deck
    deal {cards_each} cards from deck to each hand
    repeat until (all players where hand[player] is empty) {{
      let s2 = leader offset_by left
      let s3 = s2 offset_by left
      let s4 = s3 offset_by left
      as leader {{ move chosen one card from hand[leader] to pile }}
      as s2 {{ move chosen one card from hand[s2] where follow_ok(s2, card) to pile }}
      as s3 {{ move chosen one card from hand[s3] where follow_ok(s3, card) to pile }}
      as s4 {{ move chosen one card from hand[s4] where follow_ok(s4, card) to pile }}
      let w = {winner_call}
      score[w] += 1
      move all cards from pile to won[w]
      leader := w
    }}
  }}
  winner: highest score
}}
{functions}
"""

_ROUND_FORM = """
game G {{
  players: 4
  max_length: 2000
  cards: {deck}
  ranking: {ranking}
  {clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile  won[player] : PlayerPile<player> }}
  state {{ score[player] : Integer = 0  leader : Player = 0 }}
  phase play {{
    active_rules: [MustFollowSuit]
    move all cards to deck
    shuffle deck
    deal {cards_each} cards from deck to each hand
    repeat until (all players where hand[player] is empty) {{
      round play_to_trick from leader over all players source hand into pile winner {winner}{extra}
      score[winner] += 1
      move all cards from pile to won[winner]
      leader := winner
    }}
  }}
  winner: highest score
}}
"""

_FOLLOW_OK_STANDARD = """
function follow_ok(p : Player, c : Card) =
  if any card in hand[p] where card.suit is suit_of(pile) then c.suit is suit_of(pile) else true
"""
_FOLLOW_OK_TRICK_ORDER = """
function follow_ok(p : Player, c : Card) =
  if any card in hand[p] where follows_lead(card, pile) then follows_lead(c, pile) else true
"""


def _play(source: str, seed: int) -> Any:
    game = check_dsl(source, "e2e.cardlang")
    rng = random.Random(seed)
    return play_game(game, rng, None, random_chooser(rng))


_SEEDS = range(6)


@pytest.mark.parametrize("deck", ["standard52", "pinochle48"])
def test_slot_and_call_agree(deck: str) -> None:
    """One fixture written twice -- round form (the slot) and hand-rolled (the
    call over the Arrival Record) -- names the same winners on the same seeds
    (the candidate order is hand order in both, so the RNG draws agree).
    `pinochle48` is the double pack: First of Equals is exercised."""
    block = "trick_order { trump: card.suit is hearts  card_strength: rank_value(card) }"
    slot = _ROUND_FORM.format(deck=deck, ranking="aces high", clauses=block, cards_each=3,
                              winner="highest_by_trick_order", extra="")
    call = _HAND_ROLLED.format(deck=deck, ranking="aces high", clauses=block, cards_each=3,
                               winner_call="highest_by_trick_order(pile)", functions=_FOLLOW_OK_TRICK_ORDER)
    for seed in _SEEDS:
        assert _play(slot, seed).scores == _play(call, seed).scores, f"seed {seed}"


@pytest.mark.parametrize("deck", ["standard52", "pinochle48"])
def test_block_agrees_with_the_standard_winner(deck: str) -> None:
    """The metamorphic pin: a block `trump: card.suit is X` with the default
    strength is the standard trump game, so it names the same winners as
    `trump: X` + `highest_trump_or_led_suit`, slot and call, on every seed --
    which also pins First of Equals against `_strongest`'s `max`."""
    block = "trick_order { trump: card.suit is hearts }"
    std_slot = _ROUND_FORM.format(deck=deck, ranking="aces high", clauses="trump: hearts", cards_each=3,
                                  winner="highest_trump_or_led_suit", extra="")
    new_slot = _ROUND_FORM.format(deck=deck, ranking="aces high", clauses=block, cards_each=3,
                                  winner="highest_by_trick_order", extra="")
    std_call = _HAND_ROLLED.format(deck=deck, ranking="aces high", clauses="", cards_each=3,
                                   winner_call="highest_trump_or_led_suit(pile, hearts)", functions=_FOLLOW_OK_STANDARD)
    new_call = _HAND_ROLLED.format(deck=deck, ranking="aces high", clauses=block, cards_each=3,
                                   winner_call="highest_by_trick_order(pile)", functions=_FOLLOW_OK_TRICK_ORDER)
    for seed in _SEEDS:
        expected = _play(std_slot, seed).scores
        assert _play(new_slot, seed).scores == expected, f"slot, seed {seed}"
        assert _play(std_call, seed).scores == expected, f"standard call, seed {seed}"
        assert _play(new_call, seed).scores == expected, f"block call, seed {seed}"


_READERS_GAME = """
game G {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  trick_order {
    trump: card.rank is J or card.suit is spades
    follow_class: if card.rank is Q then none else card.suit
    card_strength: if card.rank is J then 100 else rank_value(card)
  }
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0  t : Integer = 0  s : Integer = 0  q : Integer = 0 }
  phase play {
    move all cards to deck
    shuffle deck
    deal 1 cards from deck to each hand
    let c = top_of(hand[0])
    t := if is_trump(c) then 1 else 0
    s := card_strength(c)
    q := if follow_class(c) is none then 1 else 0
    score[0] := t * 1000 + s * 10 + q
    score[1] += 1
  }
  winner: highest score
}
"""


def test_readers_end_to_end() -> None:
    """The three readers answer the rows for a dealt card, recomputed here in
    Python from the same rows over the observed deal."""
    game = check_dsl(_READERS_GAME, "readers.cardlang")
    for seed in range(8):
        rng = random.Random(seed)
        seen: list[tuple[int, tuple[Any, ...]]] = []

        def watch(p: int, e: tuple[Any, ...], log: Any = seen) -> None:
            log.append((p, e))

        result = play_game(game, rng, None, random_chooser(rng), observer=watch)
        deal = next(e for p, e in seen if p == 0 and e[0] == "move" and e[3] == "hand[0]")
        rank, suit = _parse(deal[4][0])
        ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
        rank_value = ranks.index(rank)
        t = 1 if (rank == "J" or suit == "spades") else 0
        s = 100 if rank == "J" else rank_value
        q = 1 if rank == "Q" else 0
        assert result.scores[0] == t * 1000 + s * 10 + q, f"seed {seed}: {deal}"


_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _parse(card_str: str) -> tuple[str, str]:
    return card_str[:-1], _SUITS[card_str[-1]]


_NO_CANDIDATE_GAME = """
game G {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  trick_order { trump: false  follow_class: none }
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase play {
    move all cards to deck
    shuffle deck
    deal 1 cards from deck to each hand
    as 0 { move chosen one card from hand[0] to pile }
    as 1 { move chosen one card from hand[1] to pile }
    let w = highest_by_trick_order(pile)
    score[w] += 1
  }
  winner: highest score
}
"""


def test_no_candidate_is_loud_end_to_end() -> None:
    """Every card class-less and none a trump: the pile has no Effective Lead
    and no card can win -- the runtime's typed channel, naming the fix."""
    with pytest.raises(OwnerGuardError, match=W2):
        _play(_NO_CANDIDATE_GAME, 0)


_DEALT_PILE_GAME = """
game G {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  trick_order { trump: card.suit is hearts }
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase play {
    move all cards to deck
    shuffle deck
    deal 2 cards from deck to pile
    let w = highest_by_trick_order(pile)
    score[w] += 1
  }
  winner: highest score
}
"""


def test_dealt_pile_has_no_winner() -> None:
    with pytest.raises(OwnerGuardError, match=W_NO_ACTOR):
        _play(_DEALT_PILE_GAME, 0)


_LEADER_FILTER_GAME = """
game G {
  players: 2
  max_length: 100
  cards: standard52
  ranking: aces high
  trick_order { trump: card.suit is hearts }
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state { score[player] : Integer = 0 }
  phase play {
    move all cards to deck
    shuffle deck
    deal 1 cards from deck to each hand
    as 0 { move chosen one card from hand[0] where follows_lead(card, pile) to pile }
    let w = highest_by_trick_order(pile)
    score[w] += 1
  }
  winner: highest score
}
"""


def test_follows_lead_on_the_empty_pile_is_false() -> None:
    """`follows_lead` on a pile with nothing led is the value false (issue
    #345's ruling), so a bare `where follows_lead(...)` on the LEADER admits no
    candidate and fails in the movement's channel -- recorded (residual (5)),
    the `follow_ok` shape (void => any card) is the pattern."""
    with pytest.raises(OwnerGuardError, match="cannot choose 1 of 0 candidates"):
        _play(_LEADER_FILTER_GAME, 0)
