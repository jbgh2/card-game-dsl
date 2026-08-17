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
            (inherit / override / none) x every card deck's suit domain;
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
            (see `sampled`).
covered:    `test_game_trump_value` (every deck x every suit of the deck +
            three non-suit shapes), `test_game_trump_consumption`
            (TRICK_WINNER_NAMES x {inherit, override} squared, plus no
            round), `test_round_trump_clause` (TRICK_WINNER_NAMES x
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
            Accepted: it IS a suit of the deck, the same domain the `Suit`
            type and the `Suit?` move-parameter domain range over, and the
            winner reads it faithfully. Whether a pseudo-suit may be a trump
            is a design decision with no witness (the framing check's C6);
            the grid captures the current behaviour (accept), the guard is
            the deck-membership check itself, and the record is the change's
            report, which puts the ruling to the operator (an issue follows
            the ruling if it is "refuse") -- R3, a designer meets it only by
            naming a pseudo-suit on purpose. (2) A Primitive winner named
            in a game whose deck its OWN order table cannot rank
            (`belote_trick_winner`'s `_TRUMP_HEIGHT[...]` on a non-skat32
            trump, `tarot_trick_winner`'s `int(rank)` on a non-numeral led
            card) dies on a bare KeyError/ValueError -- a game-LOCAL order
            table, not the declared ranking, so outside this class; both
            retire with their Primitives under issue #250 (PRs 4-5), which
            is the record.
            (3) A static guard for the rank-to-order class was weighed and
            not built: refusing a partial `ranking:` breaks a pinned
            feature (test_ranking_guard.py, Canasta), and refusing
            "partial ranking + a strength reader named" would refuse
            issue #250's planned French Tarot (Excuse unranked, default
            strength `rank_value`) while proving nothing about which cards
            reach the read -- so the runtime Owner Guard is the honest
            layer; the strict xfail that recorded the gap in
            tests/test_ranking_guard.py is retired in the same change.

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

Born red (before the guards existed): `150 failed, 95 passed in 4.22s` --
the game-clause value rejects, every dead-trump reject, every blind-winner
round clause, every non-`Suit?` round clause, the registry reconciliation,
and every rank-to-order cell (bare KeyError / TypeError / ImportError, not
the typed channel); the 95 green were the accept cells and the
already-gated call-form / `state.trump` / piece cells.

red under -- executed, each edit reddening exactly its own cells:
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

import random
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

WINNERS: tuple[str, ...] = tuple(sorted(F.TRICK_WINNER_NAMES))


# --- the executed body partition ---------------------------------------------
#
# One pile, ranks every winner body can evaluate (skat32 ranks for
# belote_trick_winner, numerals for tarot_trick_winner, ranked here for the
# two Builtins): the leader plays 9 of clubs, the second player 8 of hearts.
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


def test_trump_reading_registry_matches_the_bodies() -> None:
    """The registry the guards read is reconciled against the executed
    bodies -- red under moving any winner across the partition."""
    assert F.TRUMP_READING_WINNERS <= F.TRICK_WINNER_NAMES
    assert F.TRUMP_READING_WINNERS == {w for w in WINNERS if reads_trump(w)}


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


def _drive_belote_opp_winning() -> None:
    from cardlang.runtime import belote, reads
    from cardlang.runtime.narrowing import EngineFacts

    facts = EngineFacts(
        seating=Seating(4),
        team_of=MappingProxyType({0: 0, 1: 1, 2: 0, 3: 1}),
        rank_index=_PARTIAL,
        round_state=MappingProxyType(
            {"played": ((0, Card("2", "clubs")),), "trump": None}
        ),
        last_round_state=None,
        actor=1,
    )
    gr = reads.GameReads(
        state=MappingProxyType({}),
        families=MappingProxyType({}),
        singles=MappingProxyType({}),
    )
    belote.belote_opp_winning(facts, gr)


def _drive_peg_run_points() -> None:
    from cardlang.runtime import cribbage

    cribbage.peg_run_points(
        [Card("2", "clubs"), Card("3", "hearts"), Card("4", "spades")], _PARTIAL
    )


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
    "belote_trick_winner": _drive_slot("belote_trick_winner"),
    "belote_opp_winning": _drive_belote_opp_winning,
    "peg_run_points": _drive_peg_run_points,
    "cribbage_show_value": _drive_cribbage_show(False),
    "cribbage_crib_value": _drive_cribbage_show(True),
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
