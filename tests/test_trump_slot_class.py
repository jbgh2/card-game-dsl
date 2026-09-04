"""The trump-slot class and the rank-to-order-table class, swept together.

Two classes of pre-existing accepted-but-ignored / accepted-then-crashes cells
around the language's trump surface (issue #250, PR 0 — the sweep that
precedes the `trick_order { }` construct, so the construct is not built on
top of them):

* THE TRUMP-SLOT CLASS — every position where a trump value is named or a
  trump-reading function is named. Its members, derived below from the
  grammar (`trump: NAME`, `round ... [trump expr]`), the AST (`Game.trump`,
  `TrickRound.trump`, `TrickRound.winner_fn`), the winner registry
  (`TRICK_WINNER_NAMES`) and the call registry (`CALL_SIGS`):
    (a) the game clause `trump: NAME` — its value must be a suit of the
        declared deck (resolve, `_resolve_trump`), and it must be READ by at
        least one trick round (a round whose winner reads a trump and that
        supplies no `trump` clause of its own); a `trump:` no round reads
        is refused as dead — French Tarot's `trump: atouts` beside
        `winner tarot_trick_winner` was the corpus instance;
    (b) the round clause `trump <expr>` — held to `Suit?` (typecheck,
        `_check_round_trump`), and refused on a winner whose body reads no
        trump (resolve, the winner-slot arm) — `highest_of_led_suit trump
        hearts` used to check green and play no-trumps;
    (c) the call form `highest_trump_or_led_suit(pile, trump)` — its trump
        argument is `Suit?` by `CALL_SIGS` (already gated; pinned here as
        the same class's third position);
    (d) `state.trump` — the round publishes no trump (already gated by the
        round-state registry; pinned here as the class's fourth position).
  Which winner reads its trump is decided BY BODY, executed: `reads_trump`
  runs every registered winner on one pile twice (trump = the second
  player's suit, then no trump) and asks whether the answer moves. The
  registry `TRUMP_READING_WINNERS` is reconciled against that execution,
  never trusted.

* THE RANK-TO-ORDER-TABLE CLASS — every runtime site where a card's rank
  indexes the game's declared rank-strength order (`rs.rank_index`, aliased
  `order` in cribbage.py and `strength` in president.py). A partial
  `ranking:` is a supported feature (Canasta's eleven meldable ranks;
  tests/test_ranking_guard.py's ledger), so which cards reach a strength
  read is a RUNTIME fact — zone contents — and the guard is the runtime's
  Owner Guard: `values.rank_strength`, the one lookup every consumer routes
  through, raising `OwnerGuardError` naming the reader, the rank, and the
  declared order. Its no-`ranking:` arm is a Shadow Guard behind
  typecheck's `RANKING_GATED_*` gates.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   (1) a named trump value is a suit of the deck, typed `Suit?`,
            and reaches a winner that reads it — never accepted and
            ignored; (2) a rank outside the declared `ranking:` reaching a
            strength read fails in the runtime's typed channel, naming the
            reader — never a bare KeyError.
domain:     trump-slot: {game clause, round clause, call form, state.trump}
            x TRICK_WINNER_NAMES x expression type x consumption shape
            (inherit / override / none) x every card deck's suit domain
            x -- for the game clause's consumption arm -- every name-reached
            statement CONTAINER x {reachable, unreachable};
            rank-to-order: every rank_index consumer x an unranked rank
            reaching its lookup.
registry:   winners -- `cardlang.builtins.functions.TRICK_WINNER_NAMES`
            (the winner slot's namespace) and `TRUMP_READING_WINNERS` (the
            body partition), reconciled by `test_trump_reading_registry_
            matches_the_bodies` against the executed `reads_trump`;
            decks -- `cardlang.runtime.values.DECKS` with `deck_suits` /
            `deck_ranks`; consumers -- typecheck's `RANKING_GATED_FUNCS |
            RANKING_GATED_WINNERS | RANKING_GATED_CLIMB_QUERIES` (the
            #256 census), each crossed with an authored DRIVER (a member
            with no driver fails, `test_every_ranking_reader_has_a_driver`);
            the round clause's type axis is `_TRUMP_SPELLINGS`, authored
            (see `sampled`); containers -- DERIVED from the AST by
            `_name_reached_containers` (a statement-holding dataclass that
            appears as a field type on `n.Game`), reconciled against BOTH
            `_CONTAINER_FIXTURES` and resolve's `_DEFINITION_CONTAINERS` by
            `test_every_name_reached_container_is_classified`, and each
            container paired with its reference namespace so a future
            invoking construct added to `_REFERENCE_SLOTS` reaches the sweep
            without editing it.
covered:    `test_game_trump_value` (every deck x every suit of the deck +
            three non-suit shapes), `test_game_trump_consumption`
            (TRICK_WINNER_NAMES x {inherit, override} squared, plus no
            round), `test_dead_clause_counts_reachable_rounds` (every
            name-reached container x {reachable, unreachable} x {a reading
            winner, a blind one}) with `test_every_name_reached_container_
            is_classified` pinning the container axis complete,
            `test_unreached_reader_message_names_its_container` and
            `test_a_reachable_definition_keeps_its_trump` (the
            over-reach complement), `test_round_trump_clause`
            (TRICK_WINNER_NAMES x
            `_TRUMP_SPELLINGS`), `test_call_form_trump_argument`
            (`_TRUMP_SPELLINGS`), `test_state_trump_is_unpublished`,
            `test_unranked_rank_reaches_the_typed_channel` (every
            RANKING_GATED member x its driver), the registry reconciliation
            pins, and the piece-game cell of the game clause.
sampled:    the round clause's type axis (`_TRUMP_SPELLINGS`) is a spelling
            per representative `cardlang.types` shape (Suit, Suit?, none, a
            suit literal, Integer, String, Rank, Boolean, Collection,
            Player, Card) rather than the whole `Type` lattice: the check
            routes through `typecheck._check_operand` with expected `Suit?`,
            so what stands for `Suit?` is `types.coercible`'s own domain
            (its tests), and the choke-point pin
            (tests/test_operand_choke_point.py) is what keeps the routing
            honest. Board-minted shapes (Cell/Dir/Line) and a `TAny`
            operand are not spelled: a card game mints none, and `TAny` is
            the permissive top, admitted here exactly as the call form
            admits it. The rank-to-order Primitives (belote, cribbage,
            president) are driven at their Python entry with an unranked
            rank rather than through a whole game: their DSL route is
            pinned by their own game tests, and what this grid adds is the
            lookup site's channel.
residual:   (1) `trump: excuse` on tarot78 / `trump: joker` on
            five_hundred43 -- a singleton pseudo-suit as the trump class.
            ACCEPTED, as DESIGNED surface, not as a deferral: a pseudo-suit
            is a suit by the deck's own declaration (`deck_suits`, the same
            domain the `Suit` type and the `Suit?` move-parameter domain
            range over), so a singleton trump class is the designer's to
            write -- 500's joker-beats-all at no-trumps is the shape a
            designer might reach for before issue #250's construct lands --
            and the checker does not second-guess a suit name the deck
            declares. The winner reads it faithfully. Not work: this ledger
            OWNS the record (no issue), and the accept cells of
            `test_game_trump_value` over every deck's `deck_suits` are its
            executed pin.
            (2) A Primitive winner named in a game whose deck its OWN
            order table cannot rank dies on a bare KeyError/ValueError -- a
            game-LOCAL order table, not the declared ranking, so outside this
            class. NO instance remains: Belote's `_TRUMP_HEIGHT` lookup and
            its `_round_state`'s missing `"trump"` key retired with issue #250
            PR 4, and Tarot's `int(rank)` on a non-numeral led card retired
            with PR 5, which emptied `PRIMITIVE_TRICK_WINNERS`. Issue #364
            holds the record for the shape a future game-local winner would
            revive; the guard it names (the crash is loud, never
            silent-wrong) is a property of such a winner's body, not of
            anything in the tree today.
            (3) A static guard for the rank-to-order class was weighed and
            not built: refusing a partial `ranking:` breaks a pinned
            feature (test_ranking_guard.py, Canasta), and refusing
            "partial ranking + a strength reader named" would refuse
            issue #250's planned French Tarot (Excuse unranked, default
            strength `rank_value`) while proving nothing about which cards
            reach the read -- so the runtime Owner Guard is the honest
            layer; the strict xfail that recorded the gap in
            tests/test_ranking_guard.py is retired in the same change.
            (4) `trump: 5` / `trump: "spades"` die in the grammar's channel
            as a bare "No terminal matches" (the clause is `trump: NAME`;
            an INT/String token is refused before resolve) -- loud, wrong
            voice; and the `.lark` comment on the production still says
            "(or rank-set)". Both are `.lark` edits, Merge Lane A; record:
            issue #250, whose PR 1 is the grammar change under Hoyle's
            counsel. The grid's rank cell uses a NAME-shaped rank for
            exactly this reason.
            (5) The consumption guard's reader model is the TRICK FORM's
            inheritance, but `rs.trump` is not read only there: the form
            publishes `state["trump"]` (runtime/mechanics.py), a channel a
            game-local Primitive behind a trick round can read back and
            `TRUMP_READING_WINNERS` cannot see. NO corpus game does today --
            Belote's `belote_opp_winning` and `belote_royal_player` were the
            instance, and the Trick Order migration closed both differently
            (issue #250 PR 4): the first RETIRED, the second STAYED and
            repointed onto the game's own `trump_suit` state variable, which
            is a game clause the guard's model does cover. The residual is
            what a future one would meet: a game whose ONLY reader is such a Primitive under a
            blind winner is refused -- a FALSE REFUSAL, over-reach in the
            safe direction, never a miss. Not work; this ledger owns it.
            (6) The reachability filter is the CONSUMPTION guard's alone.
            Its three siblings need none and are not shadowing one: the
            membership guard reads `game.trump`, a game clause in no
            container at all, and the round-clause guards (`_validate_refs`'
            winner-slot arm, typecheck's `_check_round_trump`) validate a
            clause WHERE IT IS WRITTEN, so a dead container's clause is
            checked too -- over-reporting in the safe direction, and unable
            to miss. Stated because the asymmetry otherwise reads as an
            oversight someone would "fix". Not work; this ledger owns it.
            (7) french-tarot's `trick_end` trace payload moves `"atouts"` to
            `null` with no trace golden. No info-set consequence: the trace
            channel (runtime/state.py, the tracer callback) is HARNESS-only
            and distinct from `observe` (the per-observer projection the
            adapter reads), so nothing a player can see changed. Not work;
            this ledger owns the record.
            (8) The library leak-sweep's `deck_suit` namespace is vacuous
            for the `(n.Game, "trump")` slot: `trump:` is a game clause
            with no library production. Recorded as a decision in
            resolve.py's `_LIBRARY_UNSWEPT` header comment (a swept
            namespace cannot carry an "unswept" row); the value's Owner
            Guard is `_resolve_trump`, over the game.
            (9) The MIXED consumption shape -- a reachable phase round with
            a trump-blind winner AND a reading round stranded in an
            unreachable container -- has no cell of its own: the
            `test_dead_clause_counts_reachable_rounds` fixture puts a round
            in the phase only for its reachable cells, so the cross of
            "reachable blind" with "stranded reader" is unreached by the
            grid. The verdict is the same either way (refused: no reachable
            round reads the trump) and the message's `parts` list is built
            uniformly, so both sentences appear in order; the PR #365 review
            probed all four (rounds, stranded) combinations and found the
            message correct in each. Not work: this ledger owns the record;
            the cell is one `_container_source` parameter away if the
            message shape ever gains a branch.

Framing check: RAN (a fresh-context subagent given the definition sources
only -- grammar, AST, registries, runtime bodies -- with no plan or diff).
Diffed against the derivation above, it added: `trump: none` (a NAME to
the grammar, parsed as the string "none" and silently a no-trump game --
now a cell, refused pointing at the omission); the call form and
`state.trump` as positions of the same class (already gated, pinned here
rather than assumed); and the per-deck suit axis (a foreign French suit on
kuhn3 is as wrong as `bogus`). Its non-cells, recorded: a `Suit?` state
variable still `none` when the trick runs is the DESIGNED no-trump
(Bridge's contract), not a defect; a rule's `Suit`-typed template argument
is already deck-checked ("must be a suit literal (one of the deck's
suits)") -- the precedent the game clause now follows; `trump: 5` /
`trump: "spades"` are refused by the grammar's own channel (an INT/string
where `trump: NAME` wants a name -- loud, and its message quality is a
`.lark` matter, out of this change's lane).

Born red, the reachability cells (authored against the head that had the
consumption guard but counted rounds by OCCURRENCE): `4 failed, 12 passed
in 0.36s` -- `test_every_name_reached_container_is_classified` (no
`_DEFINITION_CONTAINERS` yet), the two unreachable-container reject cells
(`DefineDef`/`MoveTypeDef` x unreachable x a reading winner), and
`test_unreached_reader_message_names_its_container`. The blind-winner
container cells were born GREEN and are pins, not new coverage: an
unreachable BLIND round would not read the clause even if reached, so the
refusal is unchanged and only the absence of the container needle is new.
The four `ProcedureDef` cells were likewise born green against a
PRE-EXISTING Owner Guard (a procedure may hold no `round` at all, either
arm); their reddening mutation is deleting that guard, not this change's.

Born red (before the guards existed): `150 failed, 95 passed in 4.22s` --
the game-clause value rejects, every dead-trump reject, every blind-winner
round clause, every non-`Suit?` round clause, the registry reconciliation,
and every rank-to-order cell (bare KeyError / TypeError / ImportError, not
the typed channel); the 95 green were the accept cells and the
already-gated call-form / `state.trump` / piece cells.

red under -- executed, each edit reddening exactly its own cells:
  - the consumption guard's `_reachable_nodes(game)` put back to
    `_walk(game)` (the occurrence count this change replaced): 3 -- the two
    unreachable-container reject cells and the container-message cell.
  - `_reachable_definitions`' frontier seeded `[]` instead of
    `list(game.phases)`, so no container is ever reached: 3 -- the two
    REACHABLE-container accept cells and
    `test_a_reachable_definition_keeps_its_trump`. This is the born-green
    complement's reddening mutation: reverting the filter leaves them green
    (they are accept cells), so only inverting reachability can prove they
    are not vacuous.
  - the `ProcedureDef` row dropped from `_DEFINITION_CONTAINERS`: 1 --
    `test_every_name_reached_container_is_classified`, the deleting
    direction, so the table cannot shrink out from under the AST.
  - `_resolve_trump`'s membership guard skipped: 36 `test_game_trump_value`
    reject cells (12 decks x {bogus, a rank, a foreign suit}); the `none`
    and accept cells stay green.
  - `_resolve_trump`'s consumption guard skipped: 43
    `test_game_trump_consumption` cells (every configuration with no
    reading-inheriting round) + `test_dead_trump_message_names_the_readers`.
  - the winner-slot `elif` in `_validate_refs` dropped: 22
    `test_round_trump_clause` cells (2 blind winners x 11 spellings) + 30
    `test_game_trump_consumption` cells (every configuration with a blind
    winner overriding) -- 52; a first run reddened only 30 because the
    needle "reads no trump" also occurs inside the dead-clause message, so
    `_BLIND` now pins the round-clause phrase.
  - `_check_round_trump` returning early: 14 `test_round_trump_clause`
    cells (2 reading winners x 7 non-`Suit?` spellings).
  - `rank_strength` returning `rank_index[rank]` bare: the 10 reader
    cells, the slot cell, the shadow-guard cell, and
    tests/test_ranking_guard.py's pin -- 13.
  - `highest_of_led_suit` filed into `TRUMP_READING_WINNERS`: the
    reconciliation pin + 35 grid cells whose expectation the misfiled
    registry would flip -- 36.
  - a phantom name added to `RANKING_GATED_FUNCS`: the driver census pin +
    its own parametrized cell -- 2.
  - `test_call_form_trump_argument` / `test_state_trump_is_unpublished`:
    the existing gates' own witnesses (tests/rejections/arrival_winner_*,
    tests/test_round_state_registry.py) -- these rows re-run them as
    members of this class.
"""

from __future__ import annotations

import ast
import inspect
import random
import textwrap
from collections.abc import Callable, Mapping
from types import MappingProxyType

import pytest

from cardlang.builtins import functions as F
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime import primitives
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import DECKS, SUITS, Card, Seating, deck_ranks, deck_suits
from cardlang.typecheck import (
    RANKING_GATED_CLIMB_QUERIES,
    RANKING_GATED_FUNCS,
    RANKING_GATED_WINNERS,
)

# The winner slot's namespace MINUS the winners under the Trick Order contract
# -- every winner this module can drive, derived BY SUBTRACTION so a winner
# added to either registry lands on the right side without an edit here.
#
# The excluded members answer `(played, ctx)` rather than the uniform
# `(played, led_suit, trump, rank_index)` (cardlang/builtins/functions.py,
# `TRICK_ORDER_GATED_WINNERS`), so `reads_trump`'s differential cannot be
# posed of them: they receive no trump argument to read or ignore, and the
# question this module asks -- does the body consume the round's trump? -- has
# no meaning for a winner whose trumps are the game's `trick_order { }` rows.
# Their trump-clause cells are DECIDED and live in the construct's own grid
# (tests/test_trick_order.py): without a block, every spelling is R5 (the
# winner reads a block the game does not declare); with one, a round `trump`
# clause is R2 and the game-level clause is R1.
WINNERS: tuple[str, ...] = tuple(
    sorted(F.TRICK_WINNER_NAMES - F.TRICK_ORDER_GATED_WINNERS)
)


# --- the executed body partition ---------------------------------------------
#
# One pile, ranks every winner body can evaluate: the leader plays 9 of clubs,
# the second player 8 of hearts.
# Under no trump the 9 of clubs wins; under trump hearts a winner that reads
# its trump argument names the second player. The difference IS the
# classification -- computed from the runtime body, not read off a registry.

_PILE = [(0, Card("9", "clubs")), (1, Card("8", "hearts"))]
_RANKS = MappingProxyType({"9": 1, "8": 0})


def reads_trump(winner: str) -> bool:
    fn = primitives.value_function(winner)
    trumped = fn(list(_PILE), "clubs", "hearts", dict(_RANKS))
    plain = fn(list(_PILE), "clubs", None, dict(_RANKS))
    assert plain == 0, f"{winner}: the no-trump control did not name the leader"
    return bool(trumped != plain)


def test_the_body_partition_is_a_witness_on_this_pile() -> None:
    """The fixture is load-bearing: a pile on which no registered winner
    moves would classify everything blind. At least one winner must move
    and at least one must not, or the differential proves nothing."""
    moved = {w for w in WINNERS if reads_trump(w)}
    assert moved and moved != set(WINNERS), moved


def references_trump_parameter(winner: str) -> bool:
    """Whether the winner's body READS its `trump` parameter -- a STATIC
    superset of "its answer depends on trump". Decided on the parsed body
    (a `Name` load of the parameter), not on the substring, so a comment or
    a docstring cannot over-include a winner. A body that never loads the
    parameter provably cannot read it, so this cannot miss a reader; it can
    over-include only a reader whose read is on a path some input never
    reaches -- which is exactly the case the equality below refuses to let
    the one-pile witness hide."""
    fn = primitives.value_function(winner)
    assert "trump" in inspect.signature(fn).parameters, f"{winner}: no trump parameter"
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    (func,) = (node for node in tree.body if isinstance(node, ast.FunctionDef))
    return any(
        isinstance(node, ast.Name) and node.id == "trump" and isinstance(node.ctx, ast.Load)
        for stmt in func.body
        for node in ast.walk(stmt)
    )


def test_trump_reading_registry_matches_the_bodies() -> None:
    """The registry the guards read is reconciled against the executed
    bodies -- red under moving any winner across the partition.

    Two oracles must AGREE, not merely nest. The executed one is narrow:
    `reads_trump` runs ONE pile, so it can only ever over-classify a winner
    as blind (a reader whose read sits on a path this pile never takes).
    The static scan is the superset that cannot miss. Were the check only
    `executed <= static`, such a reader would sit in `static` alone, the
    registry would be blessed without it, and the resolver would then refuse
    a VALID `trump` clause on that winner as ignored -- the false-refusal
    twin of the accepted-but-ignored cell this grid closes. So the two sets
    must be equal, and a divergence is answered by a second witness pile
    that reaches the read (or, for a winner that provably reads its trump
    only to ignore it, a per-member disposition recorded here) -- never by
    weakening this assertion. Red under, on a LIVE member each time the
    previous anchor retired -- twice now, which is what a witness costs in a
    shrinking registry, and cheaper than letting the record become history.
    Originally (2026-08-18) `belote_trick_winner`: make `reads_trump` return
    False for it AND drop it from the registry -- the shape a future author
    produces when the one pile misses a read -- so `registry == executed`
    still holds and it sits in `static` alone; that fired with
    `static-only=['belote_trick_winner']` where the subset form stayed green.
    It retired with issue #250 PR 4 and the plant moved to
    `tarot_trick_winner`; that retired with PR 5. The plant now sits on
    `highest_of_led_suit`, the surviving trump-blind winner:
    `_planted_unused = trump` added to its body puts it in `static` alone and
    this assertion reddens in its own channel -- "the static and executed
    trump-reader oracles disagree ... static-only=['highest_of_led_suit']
    executed-only=[]" (executed 2026-08-19). Note the re-anchor goes on the
    winner and NOT on the registry: `TRUMP_READING_WINNERS` has a single
    member, so emptying it to plant the old shape trips a `min()` on an empty
    set in the diagnostic below and reddens through the wrong channel. (A
    single-site plant on `_PILE` cannot witness it either: it trips the
    no-trump control or the registry pin first.)"""
    assert F.TRUMP_READING_WINNERS <= F.TRICK_WINNER_NAMES
    executed = {w for w in WINNERS if reads_trump(w)}
    assert F.TRUMP_READING_WINNERS == executed
    static = {w for w in WINNERS if references_trump_parameter(w)}
    assert static == executed, (
        "the static and executed trump-reader oracles disagree -- extend the "
        f"executed witness, do not weaken this pin: static-only={sorted(static - executed)} "
        f"executed-only={sorted(executed - static)}"
    )


# --- fixtures ----------------------------------------------------------------


def _ranking_of(deck: str) -> str:
    return " ".join(deck_ranks(deck))


_GAME = """
game G {{
  players: 2
  max_length: 100
  cards: {deck}
  ranking: {ranking}
  {clause}
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ won[player] : Integer = 0  trump_suit : Suit? = none  trump_s : Suit = {suit}  leader : Player = 0 }}
  phase play {{
    {body}
    won[0] += 1
  }}
  winner: highest won
}}
"""

_ROUND = "round play_to_trick from 0 over all players source hand into pile winner {winner}{trump}"


def _source(*, deck: str = "standard52", clause: str = "", body: str = "") -> str:
    suit = deck_suits(deck)[0]
    return _GAME.format(
        deck=deck, ranking=_ranking_of(deck), clause=clause, suit=suit, body=body
    )


def _diagnostics(source: str) -> str | None:
    """None when the source checks clean; else the full diagnostic text --
    the primary message plus every co-reported note, so a cell can pin its
    own message without depending on bag order."""
    try:
        check_dsl(source, "trump_slot.cardlang")
    except DiagnosticError as exc:
        assert exc.diagnostic.span is not None, "a diagnostic without a span"
        parts = [exc.diagnostic.message]
        parts.extend(getattr(exc, "__notes__", []) or [])
        return "\n".join(parts)
    return None


def _expect(source: str, *needles: str) -> None:
    """Empty `needles` means the source must check clean; otherwise every
    needle must appear in the diagnostic text."""
    text = _diagnostics(source)
    if not needles:
        assert text is None, f"expected a clean check, got:\n{text}"
        return
    assert text is not None, "expected a diagnostic, the source checked clean"
    for needle in needles:
        assert needle in text, f"expected {needle!r} in:\n{text}"


# --- (a) the game clause: value ---------------------------------------------

_DEAD = "is read by no trick round"
_UNKNOWN_SUIT = "names unknown suit"
_BLIND = "round `trump` clause on winner"  # the round-clause refusal, not the dead-clause one
_TYPE = "round `trump` names the trump suit"


def _game_trump_value_cells() -> list[tuple[str, str, str]]:
    """(deck, value, expectation) for every card deck: every suit of the
    deck accepts; a non-name, a rank of the deck, and a suit of some OTHER
    deck reject; and `none` -- a NAME to the grammar, so it parsed as the
    string "none" and silently played no-trumps -- rejects pointing at the
    omission that means no trump. `bogus` is a NAME the grammar admits (the
    clause is `trump: NAME`), which is exactly why the value needs a
    membership guard."""
    every_suit = sorted({s for d in DECKS for s in deck_suits(d)})
    cells: list[tuple[str, str, str]] = []
    for deck in sorted(DECKS):
        suits = deck_suits(deck)
        for s in suits:
            cells.append((deck, s, "accept"))
        cells.append((deck, "bogus", "unknown"))
        # A NAME-shaped rank: a numeral rank (`trump: 2`) never reaches
        # resolve -- the clause is `trump: NAME` and the grammar refuses the
        # INT token itself (loud, its own channel; see the ledger).
        cells.append((deck, next(r for r in deck_ranks(deck) if not r.isdigit()), "unknown"))
        foreign = next((s for s in every_suit if s not in suits), None)
        if foreign is not None:
            cells.append((deck, foreign, "unknown"))
        cells.append((deck, "none", "omit"))
    return cells


@pytest.mark.parametrize(
    ("deck", "value", "expectation"),
    _game_trump_value_cells(),
    ids=[f"{d}-{v}-{e}" for d, v, e in _game_trump_value_cells()],
)
def test_game_trump_value(deck: str, value: str, expectation: str) -> None:
    body = _ROUND.format(winner="highest_trump_or_led_suit", trump="")
    src = _source(deck=deck, clause=f"trump: {value}", body=body)
    if expectation == "accept":
        _expect(src)
    elif expectation == "omit":
        _expect(src, "trump: none", "drop `trump: none`")
    else:
        _expect(src, _UNKNOWN_SUIT, f"'{value}'", f"deck '{deck}'")


def test_game_trump_in_a_piece_game_names_the_kind() -> None:
    """The flavor cell (owned by `_reject_card_content_clauses`, pinned in
    tests/test_piece_content_guards.py): a piece set has no suits, so the
    clause is refused naming the kind, and the membership guard is not what
    speaks."""
    src = """
game G {
  players: 2
  max_length: 10
  pieces: xo_marks
  trump: x
  zones { box : Deck }
  state { score[player] : Integer = 0 }
  phase play { }
  winner: highest score
}
"""
    _expect(src, "this game declares pieces ('xo_marks')")


# --- (a) the game clause: consumption ---------------------------------------


def _round_shapes() -> list[tuple[str, str]]:
    """Every (winner, shape): a round that INHERITS the game clause (no
    `trump` of its own) or OVERRIDES it (`trump trump_suit`)."""
    return [(w, shape) for w in WINNERS for shape in ("inherit", "override")]


def _round_text(winner: str, shape: str) -> str:
    return _ROUND.format(
        winner=winner, trump=" trump trump_suit" if shape == "override" else ""
    )


def _consumption_cells() -> list[tuple[tuple[tuple[str, str], ...], tuple[str, ...]]]:
    """A game declaring `trump: spades` with zero, one, or two trick rounds
    (every pair of (winner, shape)). Expected: clean iff SOME round both
    reads a trump and inherits; otherwise the dead-clause refusal -- and,
    independently, the blind-winner refusal for every round that puts a
    `trump` clause on a winner that reads no trump."""
    shapes = _round_shapes()
    configs: list[tuple[tuple[str, str], ...]] = [()]
    configs += [(s,) for s in shapes]
    configs += [(a, b) for a in shapes for b in shapes]
    cells = []
    for config in configs:
        consumed = any(reads_trump(w) and shape == "inherit" for w, shape in config)
        blind_override = any(
            not reads_trump(w) and shape == "override" for w, shape in config
        )
        needles: list[str] = []
        if not consumed:
            needles.append(_DEAD)
        if blind_override:
            needles.append(_BLIND)
        cells.append((config, tuple(needles)))
    return cells


def _config_id(config: tuple[tuple[str, str], ...]) -> str:
    return "+".join(f"{w}:{shape}" for w, shape in config) or "no-round"


@pytest.mark.parametrize(
    ("config", "needles"),
    _consumption_cells(),
    ids=[_config_id(c) for c, _ in _consumption_cells()],
)
def test_game_trump_consumption(
    config: tuple[tuple[str, str], ...], needles: tuple[str, ...]
) -> None:
    body = "\n    ".join(_round_text(w, shape) for w, shape in config)
    _expect(_source(clause="trump: spades", body=body), *needles)


def test_dead_trump_message_names_the_readers() -> None:
    """The refusal tells the author what WOULD read the clause -- the
    trump-reading winners by name -- and, for a game with no round at all,
    that a hand-rolled trick passes its trump to the call form itself."""
    src = _source(clause="trump: spades", body="won[1] += 1")
    text = _diagnostics(src)
    assert text is not None
    for w in sorted(F.TRUMP_READING_WINNERS):
        assert w in text, text
    assert "runs no trick round" in text, text


# --- (a) the game clause: consumption is REACHABILITY, not occurrence -------
#
# The consumption guard asks whether some round READS the clause, so it must
# count the rounds the game RUNS. A `round` is a `statement`, and three
# definition forms hold `statement*` -- so a reading round written inside a
# body nothing invokes made a dead `trump:` look consumed. The container axis
# is DERIVED here (not authored): a statement-holding AST container is reached
# by NAME exactly when it is a top-level definition list on `n.Game`; every
# other statement holder sits inside a phase body, where containment reaches
# it. `_CONTAINER_FIXTURES` then supplies the DSL text per container, and
# `test_every_name_reached_container_is_classified` fails if the AST grows a
# container neither table classifies.

_UNREACHED = "sits in a definition nothing reaches"
_PROC_WALL = "contains a `round`"


def _stmt_holding_containers() -> set[type]:
    """Every AST dataclass with a `tuple[Stmt, ...]` field -- the containers a
    `round` can be written inside."""
    import dataclasses

    from cardlang.ast import nodes as ast_nodes

    out: set[type] = set()
    for name in dir(ast_nodes):
        obj = getattr(ast_nodes, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        for f in dataclasses.fields(obj):
            if "Stmt" in str(f.type) and "tuple" in str(f.type):
                out.add(obj)
    return out


def _name_reached_containers() -> set[type]:
    """The statement holders reached by NAME: those appearing as a field type
    on `n.Game`, i.e. a top-level definition list. The complement is reached by
    containment from a phase body, which `_walk` already covers."""
    import dataclasses
    import typing

    from cardlang.ast import nodes as ast_nodes

    hints = typing.get_type_hints(ast_nodes.Game)
    out: set[type] = set()
    for cls in _stmt_holding_containers():
        for f in dataclasses.fields(ast_nodes.Game):
            stack: list[object] = [hints.get(f.name)]
            while stack:
                cur = stack.pop()
                if cur is cls:
                    out.add(cls)
                    stack = []
                    break
                stack.extend(typing.get_args(cur) or ())
    return out


# DSL text per name-reached container: how to write a body holding a round,
# and how to make that body reachable. Authored -- pinned complete against the
# derived container set by the test below.
_CONTAINER_FIXTURES: dict[str, tuple[str, str]] = {
    # container class name -> (definition template holding {round}, invocation)
    "DefineDef": ("define d -> {{ ok }} {{ {round}\n  produce ok }}",
                  "d produces:\n      ok { won[1] += 1 }"),
    "MoveTypeDef": ("move_type m {{ effect {{ {round} }} }}",
                    "offer to 0 one of [m]"),
    "ProcedureDef": ("procedure p() {{ {round} }}", "run p()"),
}


def test_every_name_reached_container_is_classified() -> None:
    """The container class is DERIVED from the AST; both the grid's fixture
    table and resolve's reachability table must classify every member. A new
    statement-holding definition form fails here rather than silently
    rejoining the blind spot the reachability filter exists to end."""
    from cardlang.resolve import _DEFINITION_CONTAINERS

    derived = {c.__name__ for c in _name_reached_containers()}
    assert derived == set(_CONTAINER_FIXTURES), derived
    assert derived == {c.__name__ for c in _DEFINITION_CONTAINERS}, derived


def _container_cells() -> list[tuple[str, bool, str, tuple[str, ...], tuple[str, ...]]]:
    """(container, reachable, winner, needles, forbidden) -- every name-reached
    container x {reachable, unreachable} x {a trump-reading winner, a blind
    one}. The container holds the game's ONLY trick round, so the clause is
    consumed exactly when that round is both reachable and reading.

    A procedure is refused either way by a pre-existing Owner Guard (a
    procedure may not hold a `round` at all), so its four cells PIN that wall
    rather than adding coverage."""
    # Both picked from `WINNERS`, the uniform-contract domain, so the blind
    # representative is a winner this module can actually execute -- picking
    # from the whole namespace would select the Trick Order winner, whose
    # trump question is posed and answered elsewhere (see `WINNERS` above).
    reading = min(w for w in WINNERS if w in F.TRUMP_READING_WINNERS)
    blind = min(w for w in WINNERS if w not in F.TRUMP_READING_WINNERS)
    cells = []
    for container in sorted(_CONTAINER_FIXTURES):
        for reachable in (True, False):
            for winner in (reading, blind):
                if container == "ProcedureDef":
                    needles: tuple[str, ...] = (_PROC_WALL,)
                    forbidden: tuple[str, ...] = ()
                elif reachable and reads_trump(winner):
                    needles, forbidden = (), ()  # the clause is consumed
                elif reads_trump(winner):  # unreachable, would have read it
                    needles, forbidden = (_DEAD, _UNREACHED), ()
                else:  # blind: it would not read the clause even if reached
                    needles, forbidden = (_DEAD,), (_UNREACHED,)
                cells.append((container, reachable, winner, needles, forbidden))
    return cells


def _container_source(container: str, reachable: bool, winner: str) -> str:
    template, invocation = _CONTAINER_FIXTURES[container]
    defs = template.format(round=_ROUND.format(winner=winner, trump=""))
    body = invocation if reachable else "won[1] += 1"
    return _source(clause="trump: spades", body=body) + "\n" + defs


@pytest.mark.parametrize(
    ("container", "reachable", "winner", "needles", "forbidden"),
    _container_cells(),
    ids=[
        f"{c}-{'reachable' if r else 'unreachable'}-{w}"
        for c, r, w, _, _ in _container_cells()
    ],
)
def test_dead_clause_counts_reachable_rounds(
    container: str,
    reachable: bool,
    winner: str,
    needles: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    src = _container_source(container, reachable, winner)
    _expect(src, *needles)
    if forbidden:
        text = _diagnostics(src)
        assert text is not None
        for needle in forbidden:
            assert needle not in text, f"unexpected {needle!r} in:\n{text}"


def test_unreached_reader_message_names_its_container() -> None:
    """A reading round inside a body nothing invokes must not be told "the
    game runs no trick round" while the author looks straight at one: the
    refusal names the container kind and what would reach it."""
    for container, name in (("DefineDef", "define"), ("MoveTypeDef", "move_type")):
        reading = min(F.TRUMP_READING_WINNERS)
        text = _diagnostics(_container_source(container, False, reading))
        assert text is not None
        assert _UNREACHED in text, text
        assert name in text, text


def test_a_reachable_definition_keeps_its_trump(monkeypatch: pytest.MonkeyPatch) -> None:
    """The complement, so the filter cannot over-reach: a reading round in an
    INVOKED define / an OFFERED move type consumes the clause and the game
    checks clean. Born green -- its reddening mutation is seeding the
    reachability frontier with the definition lists inverted (making a
    reachable container read as unreachable)."""
    for container in ("DefineDef", "MoveTypeDef"):
        reading = min(F.TRUMP_READING_WINNERS)
        _expect(_container_source(container, True, reading))


# --- (b) the round clause ---------------------------------------------------

# Spelling per representative type shape, in the fixture's scope. The four
# `Suit?`-compatible shapes are the accept half; every other shape is a
# type reject on a trump-reading winner (and the blind-winner reject on a
# blind one, which comes first: resolve refuses before typecheck runs).
_TRUMP_SPELLINGS: dict[str, tuple[str, bool]] = {
    "absent": ("", True),
    "Suit?": (" trump trump_suit", True),
    "Suit": (" trump trump_s", True),
    "none": (" trump none", True),
    "suit-literal": (" trump hearts", True),
    "Integer": (" trump 3", False),
    "String": (' trump "hearts"', False),
    "Rank": (" trump J", False),
    "Boolean": (" trump true", False),
    "Collection": (" trump [clubs, spades]", False),
    "Player": (" trump leader", False),
    "Card": (" trump top_of(deck)", False),
}


def _round_clause_cells() -> list[tuple[str, str]]:
    return [(w, shape) for w in WINNERS for shape in _TRUMP_SPELLINGS]


@pytest.mark.parametrize(
    ("winner", "shape"),
    _round_clause_cells(),
    ids=[f"{w}-{s}" for w, s in _round_clause_cells()],
)
def test_round_trump_clause(winner: str, shape: str) -> None:
    spelling, suit_typed = _TRUMP_SPELLINGS[shape]
    src = _source(body=_ROUND.format(winner=winner, trump=spelling))
    if shape == "absent":
        _expect(src)
    elif not reads_trump(winner):
        _expect(src, _BLIND, winner)
    elif suit_typed:
        _expect(src)
    else:
        _expect(src, _TYPE, "expected Suit?")


# --- (c) the call form's trump argument -------------------------------------


@pytest.mark.parametrize(
    "shape", [s for s in _TRUMP_SPELLINGS if s != "absent"]
)
def test_call_form_trump_argument(shape: str) -> None:
    """The third position of the class, already gated by `CALL_SIGS`
    (`highest_trump_or_led_suit(zone, Suit?)`): pinned here so the class is
    swept as one, not left to the reader to assemble from three modules."""
    spelling, suit_typed = _TRUMP_SPELLINGS[shape]
    arg = spelling.removeprefix(" trump ")
    body = f"let w = highest_trump_or_led_suit(pile, {arg})\n    won[w] += 1"
    src = _source(body=body)
    if suit_typed:
        _expect(src)
    else:
        _expect(src, "highest_trump_or_led_suit() expects Suit?")


# --- (d) state.trump ---------------------------------------------------------


def test_state_trump_is_unpublished() -> None:
    """The fourth position: the trick form keeps its trump internal
    (`stdlib/round_state.py`, TRICK_INTERNAL), so no rule or body can read
    a round's trump back -- the round-state registry's own guard."""
    body = (
        _ROUND.format(winner="highest_trump_or_led_suit", trump="")
        + "\n    if state.trump is none { won[1] += 1 }"
    )
    _expect(_source(body=body), "a round publishes no `trump`")


# --- the rank-to-order-table class ------------------------------------------

_READERS: tuple[str, ...] = tuple(
    sorted(RANKING_GATED_FUNCS | RANKING_GATED_WINNERS | RANKING_GATED_CLIMB_QUERIES)
)
_PARTIAL = MappingProxyType({"A": 2, "K": 1, "Q": 0})  # `ranking: A K Q`

_PARTIAL_GAME = """
game G {{
  players: {players}
  max_length: 40
  {teams}
  cards: standard52
  ranking: A K Q
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0 }}
  {rules}
  phase play {{
    move all cards from deck where card is (2 of clubs) to hand[0]
    move all cards from deck where card is (3 of clubs) to hand[1]
    {body}
  }}
  winner: highest score
}}
"""


def _play(body: str, *, players: int = 2, teams: str = "", rules: str = "") -> None:
    src = _PARTIAL_GAME.format(players=players, teams=teams, rules=rules, body=body)
    game = check_dsl(src, "partial.cardlang")
    play_game(game, random.Random(0))


def _drive_rank_value() -> None:
    _play("score[0] := sum of rank_value(card) over cards in hand[0]")


def _drive_slot(winner: str) -> Callable[[], None]:
    def drive() -> None:
        _play(
            f"round play_to_trick from 0 over all players source hand into pile "
            f"winner {winner}\n    score[winner] += 1"
        )

    return drive


def _drive_call_form() -> None:
    _play(
        "as 0 { move chosen one card from hand[0] to pile }\n"
        "    as 1 { move chosen one card from hand[1] to pile }\n"
        "    let w = highest_trump_or_led_suit(pile, none)\n"
        "    score[w] += 1"
    )


def _drive_peg_run_points() -> None:
    from cardlang.runtime import cribbage, reads
    from cardlang.runtime.narrowing import EngineFacts

    facts = EngineFacts(
        seating=Seating(2),
        team_of=MappingProxyType({}),
        rank_index=_PARTIAL,
        round_state=None,
        last_round_state=None,
        actor=None,
    )
    gr = reads.GameReads(
        state=MappingProxyType({}),
        families=MappingProxyType({}),
        singles=MappingProxyType(
            {
                "play_pile": (
                    Card("2", "clubs"),
                    Card("3", "hearts"),
                    Card("4", "spades"),
                )
            }
        ),
    )
    cribbage.peg_run_points(facts, gr)


def _drive_cribbage_show(is_crib: bool) -> Callable[[], None]:
    def drive() -> None:
        from cardlang.runtime import cribbage

        cribbage.show_score(
            [Card("2", "clubs"), Card("3", "hearts"), Card("4", "spades"), Card("A", "clubs")],
            Card("K", "hearts"),
            is_crib,
            _PARTIAL,
            reader="cribbage_crib_value" if is_crib else "cribbage_show_value",
        )

    return drive


def _drive_salvo_combos() -> None:
    from cardlang.runtime import salvo

    salvo.run_bonus(
        [Card("2", "clubs"), Card("3", "hearts"), Card("4", "spades")], _PARTIAL
    )


def _drive_president(query: str) -> Callable[[], None]:
    def drive() -> None:
        from cardlang.runtime import president, reads
        from cardlang.runtime.narrowing import EngineFacts

        facts = EngineFacts(
            seating=Seating(2),
            team_of=MappingProxyType({}),
            rank_index=_PARTIAL,
            round_state=None,
            last_round_state=None,
            actor=None,
        )
        gr = reads.GameReads(
            state=MappingProxyType({}),
            families=MappingProxyType({}),
            singles=MappingProxyType({}),
        )
        hand = [Card("2", "clubs"), Card("2", "hearts")]
        if query == "president_lead_options":
            president.president_lead_options(facts, gr, hand)
        else:
            standing = president.president_lead_options(
                facts, gr, [Card("A", "spades")]
            )[0]
            president.president_follows(facts, gr, hand, standing)

    return drive


# member -> the executed route that reaches its strength lookup with a rank
# outside `ranking: A K Q`. The MEMBER axis is the registry; only this
# correspondence is authored, and a member without a row fails below.
_DRIVERS: Mapping[str, Callable[[], None]] = {
    "rank_value": _drive_rank_value,
    "highest_of_led_suit": _drive_slot("highest_of_led_suit"),
    "highest_trump_or_led_suit": _drive_call_form,
    "peg_run_points": _drive_peg_run_points,
    "cribbage_show_value": _drive_cribbage_show(False),
    "cribbage_crib_value": _drive_cribbage_show(True),
    "salvo_combos": _drive_salvo_combos,
    "president_lead_options": _drive_president("president_lead_options"),
    "president_follows": _drive_president("president_follows"),
}


def test_every_ranking_reader_has_a_driver() -> None:
    """The member axis is the registry; a member with no executed route is
    a cell nobody runs. red under: add a name to RANKING_GATED_FUNCS."""
    assert set(_READERS) == set(_DRIVERS), (
        f"readers without a driver: {set(_READERS) - set(_DRIVERS)}; "
        f"drivers naming no reader: {set(_DRIVERS) - set(_READERS)}"
    )


@pytest.mark.parametrize("reader", _READERS)
def test_unranked_rank_reaches_the_typed_channel(reader: str) -> None:
    with pytest.raises(OwnerGuardError) as exc:
        _DRIVERS[reader]()
    text = str(exc.value)
    assert reader in text, text
    assert "ranking:" in text, text
    assert "A, K, Q" in text, text  # the declared order, so the fix is in the message


def test_the_slot_winner_shares_the_call_form_lookup() -> None:
    """`highest_trump_or_led_suit` has two positions (slot and call form);
    the call form is the registry's row above, the slot is pinned here so
    neither position is assumed from the other."""
    with pytest.raises(OwnerGuardError) as exc:
        _drive_slot("highest_trump_or_led_suit")()
    assert "highest_trump_or_led_suit" in str(exc.value)


def test_a_ranked_read_is_unchanged() -> None:
    """The guard is a miss guard: a rank inside the declared order reads its
    strength exactly as before (the schnapsen/hearts playouts are the
    corpus witness; this is the unit control)."""
    from cardlang.runtime.values import rank_strength

    assert rank_strength(_PARTIAL, "K", "rank_value") == 1


@pytest.mark.expects_shadow_guard
def test_no_ranking_at_a_reader_is_the_shadow_guard() -> None:
    """The no-`ranking:` arm: typecheck's RANKING_GATED gates own that
    class, so a reader meeting an EMPTY order is an engine gap, addressed
    to the maintainer in the Shadow Guard's channel and naming the gate."""
    from cardlang.runtime.errors import ShadowGuardError
    from cardlang.runtime.values import rank_strength

    with pytest.raises(ShadowGuardError, match="RANKING_GATED"):
        rank_strength(MappingProxyType({}), "K", "rank_value")


def test_every_french_suit_is_a_deck_suit_somewhere() -> None:
    """The foreign-suit cells above lean on the union of every deck's suits
    containing more than any one deck's: pinned so a registry change that
    collapses the union to one deck's suits is noticed rather than
    silently emptying those cells."""
    every_suit = {s for d in DECKS for s in deck_suits(d)}
    assert set(SUITS) < every_suit
