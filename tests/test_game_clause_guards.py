"""Game-clause structural guards: omission and duplication over the whole
clause domain of the `game` production, plus the content-clause axis
(`cards:` / `pieces:` — which component set a game plays with).

Seeded by the fuzz finding `missing_cards_declaration` (a missing `cards:`
escaping `check_dsl` as a raw lark ``VisitError`` around a bare assert) and
swept per decisions.md "Closed-domain completeness": the fuzzer proved two
cells (`players:`/`cards:` omission); the class is every clause of the
`game` production, on both the omission and the duplication axis, plus the
game-count cells of `start` itself.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a structurally invalid game skeleton — a mandatory clause
            omitted, a single-valued clause repeated, a source with zero or
            multiple `game { }` blocks, a `direction:` outside its value
            set, or a content clause whose name is unknown or of the wrong
            flavor — fails `check_dsl` with a located `DiagnosticError`,
            never a bare assert / raw lark error / silently different
            meaning.
domain:     the `?game_item` alternatives of the `game` production, times
            {omitted, duplicated, ABSORBED}; plus the game-count axis of
            `start` (zero / one / many); plus the `direction:` value axis;
            plus the content-clause axis — clause presence {cards only,
            pieces only, both, neither} at parse, times name flavor {card
            deck, piece set, unknown} at resolve.
            The absorption axis was added after `uses <library>` was found
            to vanish when written below `ranking:` — `ranking:` takes an
            unbounded `card_rank+` run, so a clause spelled as two bare
            names is eaten by it with no error. That is a property of the
            RANKING production, not of `uses`, so it is swept over every
            clause rather than probed on the one that was found broken.
            The axis has TWO absorbers, because the class is "an unbounded
            or empty slot completes itself from the clause below it": the
            `card_rank+` run, and an empty EXPRESSION slot. Within the
            `game` production `loser:` is the only clause whose last slot is
            a bare `expr` (`winner:` takes `rank_dir NAME`), which is where
            the empty-EXPRESSION absorber is reachable at all.
            One thing sits outside, and it is not a gap: this module owns the
            clause STRUCTURE, so the content VOCABULARY a flavor admits —
            `ranking:`/`trump:` declared in a piece game, and every other
            card-content surface — is the content-agreement guards' domain
            and the piece-game playout's, not this one's.
registry:   `cardlang/grammar/cardlang.lark` (`?game_item`) — scraped here
            by `_game_item_alternatives`, so a clause added to the grammar
            fails `test_game_item_registry_pin` until it is classified
            below; `?library_item` likewise by `library_item_alternatives`,
            which the import tier's own module reuses; `GAME_DIRECTIONS` in
            `cardlang/runtime/values.py` for the direction value set;
            `COMPONENT_SETS` (same module, the `flavor` column) for the
            content-clause name axis; `CARD_RANK_NAME`'s negative lookahead
            for the `card_rank+` absorption leg, scraped by
            `_card_rank_excluded` so both sides of the pin stay derived.
            The LIBRARY half of the empty-EXPRESSION absorber, as the
            truncation grid over `?library_item`:
            tests/test_family_libraries.py. `ranking:` omission with
            rank-dependent constructs in play, typecheck's `has_ranking`
            gate: tests/test_ranking_guard.py. The content-agreement guards:
            tests/test_piece_content_guards.py.
does not prove:  three things about cells that are argued rather than
            run here.
            That a zero-`phase` game plays its degenerate semantics — no
            decisions, the result read from the initial state. The cell in
            this module is "accepted", which is the valid-BASE probe's
            statement; nothing here runs such a game to the result.
            That both content clauses co-report with a missing `players:` in
            their own right. That pair rides the same diagnostic bag the
            neither-present probe pins, so a co-reporting path that stopped
            being shared would not be seen from here.
            That a Suit-parameterized rule in a piece game is refused.
            `_instantiate_rules` skips only the suit-membership refinement
            when `suits` is None, and what keeps the cell loud is the
            argument name failing name classification in a piece game's
            namespaces — read off the resolve path, not executed here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from lark import Tree

import cardlang
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.parse import parse_text, parse_to_tree
from cardlang.pipeline import check_dsl

GRAMMAR = (
    Path(cardlang.__file__).resolve().parent / "grammar" / "cardlang.lark"
).read_text()


def _item_alternatives(production: str) -> set[str]:
    """Scrape one `?<production>:` alternation — the clause registries this
    module's domain derives from (never hand-enumerate what a registry
    already defines)."""
    match = re.search(
        rf"^\?{production}:\s*(\w+)((?:\s*\n\s*\|\s*\w+)*)", GRAMMAR, re.MULTILINE
    )
    assert match is not None, f"grammar lost its `?{production}` production"
    names = {match.group(1)}
    names.update(re.findall(r"\|\s*(\w+)", match.group(2)))
    return names


def _game_item_alternatives() -> set[str]:
    return _item_alternatives("game_item")


def library_item_alternatives() -> set[str]:
    """The `?library_item` alternatives — a family-library file's clause
    registry (decisions.md "Family libraries"). Public because the import
    tier's own module (tests/test_family_libraries.py) derives its truncation
    grid from the same scrape, and one scrape means one place to fix."""
    return _item_alternatives("library_item")


# A production spells its keyword as an anchored terminal, never as a bare
# string literal — every keyword is a whole word (decisions.md "The expression
# register"), and a bare literal would mint an unanchored terminal that
# tests/test_keyword_anchoring.py fails on. So the scrapes below read the
# `_<WORD>_KW` form and follow it to the terminal for the word itself; there is
# no bare-literal branch to keep in step, because there can be no bare literal.
KEYWORD_REF = r"(_[A-Z0-9_]+_KW)"


def _keyword_word(terminal: str) -> str:
    """The word an anchored keyword terminal matches, from its own definition:
    `_USES_KW: "uses" /(?![A-Za-z0-9_])/` -> `uses`."""
    match = re.search(rf'^{terminal}:\s*"([a-z_-]+)"', GRAMMAR, re.MULTILINE)
    assert match is not None, f"grammar lost its `{terminal}` terminal"
    return match.group(1)


def _clause_keyword(rule_name: str) -> str:
    """The keyword a clause production opens with, read from the grammar rather
    than mapped by hand: `uses_decl: _USES_KW NAME` -> `uses`, and
    `state_block: _STATE_KW "{" ...` -> `state`, neither of which matches its
    rule name."""
    match = re.search(rf"^{rule_name}:\s*{KEYWORD_REF}", GRAMMAR, re.MULTILINE)
    assert match is not None, f"clause `{rule_name}` opens with no keyword terminal"
    return _keyword_word(match.group(1))


def _terminal_excluded(terminal: str) -> set[str]:
    """The words a terminal's negative lookahead refuses, scraped from the
    terminal itself — the other half of each pin below."""
    match = re.search(
        rf"^{terminal}:\s*/\(\?!\(\?:([^)]+)\)", GRAMMAR, re.MULTILINE
    )
    assert match is not None, f"grammar lost its `{terminal}` terminal"
    return set(match.group(1).split("|"))


def _card_rank_excluded() -> set[str]:
    return _terminal_excluded("CARD_RANK_NAME")


def test_card_rank_excludes_every_clause_keyword() -> None:
    """`ranking:` takes an unbounded `card_rank+` run, so any clause spelled as
    two bare names in a row is absorbed into it and vanishes from the AST with no
    error — the defect that let `uses <library>` be silently swallowed. The run
    is bounded by refusing clause keywords as rank names, and BOTH sides of that
    exclusion are derived: the clause list from `?game_item`, the excluded set
    from the terminal. A clause added to the grammar without an entry in
    CARD_RANK_NAME fails here rather than at a designer's desk.

    red under: delete `uses` from CARD_RANK_NAME's exclusion list in
    cardlang.lark."""
    keywords = {_clause_keyword(rule) for rule in _game_item_alternatives()}
    missing = keywords - _card_rank_excluded()
    assert not missing, (
        f"game clause keyword(s) {sorted(missing)} are still legal rank names, so "
        f"`ranking:` can absorb the clause and drop it silently — add them to "
        f"CARD_RANK_NAME's exclusion list in cardlang.lark"
    )


@pytest.mark.parametrize("rule_name", sorted(_game_item_alternatives()))
def test_no_clause_is_absorbed_when_it_follows_ranking(rule_name: str) -> None:
    """The behavioural half: every clause still parses as ITSELF when written
    after a `ranking:` enumeration. Swept over the whole clause registry rather
    than probing the one clause that was found broken (decisions.md
    "Closed-domain completeness": sweep the class, don't patch the instance).

    red under: delete `uses` from CARD_RANK_NAME's exclusion list — the
    `uses_decl` row then fails with the clause absorbed as two rank names, which
    is the defect exactly as it was found."""
    keyword = _clause_keyword(rule_name)
    clause = _CLAUSE_TEXT[rule_name]
    src = (
        "game G {\n  players: 2\n  cards: standard52\n  ranking: aces high\n"
        f"  {clause}\n  zones {{ deck : Deck }}\n}}"
    )
    tree = parse_to_tree(src, "absorb.cardlang")
    ranking = [n for n in tree.iter_subtrees() if n.data == "ranking"]
    # Each `card_rank` child is a Tree wrapping one token; a bare Token here
    # would mean the RANK_CONV arm matched, which this source does not use.
    ranks = [
        str(c.children[0]) for c in ranking[0].children if isinstance(c, Tree)
    ]
    assert ranks == ["aces", "high"], (
        f"`{keyword}` was absorbed into the ranking enumeration as {ranks} — the "
        f"clause is silently gone"
    )
    assert any(n.data == rule_name for n in tree.iter_subtrees()), (
        f"`{keyword}` did not parse as a `{rule_name}` clause"
    )


# One minimally-valid source line per clause, for the absorption sweep above.
# Keyed by grammar rule name so the parametrization above stays derived.
_CLAUSE_TEXT: dict[str, str] = {
    "uses_decl": "uses poker_betting",
    "primitives_block": "primitives { probe_fn(p : Player) : Integer reads hand }",
    "players": "players: 3",
    "direction": "direction: clockwise",
    "cards": "cards: skat32",
    "pieces": "pieces: xo_marks",
    "board": "board: grid(3, 3)",
    "ranking": "ranking: K Q J",
    "card_points_table": "card_points { A: 1 }",
    "trump": "trump: hearts",
    "trick_order": "trick_order { trump: card.suit is hearts }",
    "teams": "teams: [[0, 2], [1, 3]]",
    "max_length": "max_length: 10",
    "positions": "positions { column : 1..7 }",
    "zones": "zones { stock : Deck }",
    "state_block": "state { score[player] : Integer = 0 }",
    "phase": "phase p { }",
    "winner": "winner: highest score",
    # `loser:` takes an expr, not `winner:`'s `rank_dir NAME`.
    "loser": "loser: score",
}


# --- the second absorber: an empty expression slot ---------------------------
#
# A brace clause read as the expression an empty slot is missing would be
# dropped with no error. No expression form begins `NAME "{"`, so the grammar
# holds no such reading; the sweep below runs every game clause through the
# slot to keep it that way.


@pytest.mark.parametrize("rule_name", sorted(_game_item_alternatives()))
def test_no_clause_is_absorbed_by_an_empty_expression_slot(rule_name: str) -> None:
    """`loser:` is the one game clause whose last slot is a bare `expr`, so it
    is the game-file end of the absorption class. Left empty it must fail to
    parse — never quietly take the next clause as its expression.

    Asserted at the PARSE layer deliberately: an absorbed reading would be a
    well-formed parse, and letting a later stage reject it for some other
    reason would make this cell green while the clause still vanished.

    red under: add `| NAME "{" NAME ":" expr "}"` as a `?primary` alternative
    in cardlang.lark — `zones { stock : Deck }` is then read as the missing
    expression."""
    src = (
        "game G {\n  players: 2\n  cards: standard52\n  loser:\n"
        f"  {_CLAUSE_TEXT[rule_name]}\n}}"
    )
    with pytest.raises(DiagnosticError) as exc:
        parse_text(src, "absorb.cardlang")
    assert exc.value.diagnostic.span is not None, (
        "a parse-layer refusal must be located, not a bare error"
    )


# grammar rule name -> the clause spelling the duplicate diagnostic names.
# `phase` is the one legitimately repeatable clause and is deliberately
# absent; `test_game_item_registry_pin` forces this mapping to be revisited
# whenever the grammar grows a clause.
SINGLE_VALUED: dict[str, str] = {
    "players": "players:",
    "direction": "direction:",
    "cards": "cards:",
    "pieces": "pieces:",
    "board": "board:",
    "ranking": "ranking:",
    "card_points_table": "card_points { }",
    "trump": "trump:",
    "trick_order": "trick_order { }",
    "primitives_block": "primitives { }",
    "teams": "teams:",
    "max_length": "max_length:",
    "positions": "positions { }",
    "zones": "zones { }",
    "state_block": "state { }",
    "winner": "winner:",
    "loser": "loser:",
}

# A minimal valid game (also the acceptance probe: it omits `direction:`,
# `ranking:`, `trump:`, and `teams:`, pinning that those omissions
# are legal). Duplication probes are built by line surgery on it.
BASE_LINES: tuple[str, ...] = (
    "game Probe {",
    "  players: 2",
    "  cards: standard52",
    "  max_length: 10",
    "  zones { deck : Deck  hand[player] : Hand<player> }",
    "  state { score[player] : Integer = 0 }",
    "  phase play {",
    "    deal 3 cards from deck to each hand",
    "  }",
    "  winner: highest score",
    "}",
)
BASE = "\n".join(BASE_LINES) + "\n"

# grammar rule name -> a clause line (or block) valid enough to parse, for
# clauses BASE does not already carry. The duplicate guard fires at parse
# time, before resolve, so these only need to be grammatical.
_EXTRA_CLAUSE: dict[str, str] = {
    "positions": "  positions { column : 1..3 }",
    "card_points_table": "  card_points { A: 1 }",
    # BASE carries `cards:`, so this probe doubles as the pieces-duplicated-
    # beside-cards cell: `once()` raises before the mutual-exclusion guard.
    "pieces": "  pieces: xo_marks",
    # Likewise duplicated beside `cards:`: `once("board:")` fires at parse,
    # before resolve's board-requires-pieces guard ever runs.
    "board": "  board: grid(3, 3)",
    "direction": "  direction: clockwise",
    "ranking": "  ranking: A K Q J 10 9 8 7 6 5 4 3 2",
    "trump": "  trump: spades",
    # The duplicate probe must reach the `once` guard, so the block itself has
    # to be well-formed: a `trump:` row is required (parse's P8), and it speaks
    # first for a block that lacks one.
    "trick_order": "  trick_order { trump: card.suit is spades }",
    "teams": "  teams: [[0, 1]]",
    # An EMPTY block, which is well-formed on purpose (the presence, not the
    # contents, picks the game's Primitive regime) — so the duplicate probe
    # reaches `once` without also having to name an implemented Primitive.
    "primitives_block": "  primitives { }",
    "loser": "  loser: active",
}


def _duplicate_probe(rule_name: str) -> str:
    """BASE with the named clause appearing twice."""
    if rule_name in _EXTRA_CLAUSE:
        line = _EXTRA_CLAUSE[rule_name]
        return BASE.replace("  max_length: 10", f"{line}\n{line}\n  max_length: 10")
    marker = {
        "players": "  players: 2",
        "cards": "  cards: standard52",
        "max_length": "  max_length: 10",
        "zones": "  zones { deck : Deck  hand[player] : Hand<player> }",
        "state_block": "  state { score[player] : Integer = 0 }",
        "winner": "  winner: highest score",
    }[rule_name]
    return BASE.replace(f"{marker}\n", f"{marker}\n{marker}\n")


# The clauses a game may legitimately write MORE THAN ONCE, each with the reason
# and with where its own repeat-abuse guard lives — a clause is not exempt from
# duplication checking just by being here, it is checked somewhere else.
#
#   phase      — a game is a sequence of phases; repetition IS the construct.
#   uses_decl  — a game uses as many family libraries as it draws on
#                (decisions.md "Family libraries"). Repeating the SAME library is
#                still a defect, and is guarded in `resolve._apply_uses`, not in
#                parse: only resolve knows the library names.
REPEATABLE: dict[str, str] = {
    "phase": "a game is a sequence of phases",
    "uses_decl": "a game may use several libraries; the repeated-NAME guard is "
    "in resolve._apply_uses, which is the pass that knows library names",
}


def test_game_item_registry_pin() -> None:
    """The domain this module quantifies over IS the grammar's clause list:
    a new `?game_item` alternative must be classified here (single-valued or
    repeatable) before it can land.

    red under: add an alternative to `?game_item` in the grammar without
    listing it in SINGLE_VALUED/REPEATABLE (the scraped set then exceeds the
    classified union). Demonstrated by the merge: `board`/`pieces` entered
    `?game_item` and this pin stayed red until both were classified below."""
    alternatives = _game_item_alternatives()
    assert alternatives == set(SINGLE_VALUED) | set(REPEATABLE), (
        "the `game` production's clause list changed — classify the new "
        "clause in SINGLE_VALUED (or in REPEATABLE, with the reason and the "
        "location of its own repeat guard) and give it omission/duplication probes"
    )


def test_base_probe_is_accepted() -> None:
    check_dsl(BASE, "base.cardlang")


@pytest.mark.parametrize("rule_name", sorted(SINGLE_VALUED))
def test_duplicate_clause_rejected(rule_name: str) -> None:
    """Every single-valued clause, repeated, is rejected at the second
    occurrence — never silently last-wins (the parse.py `game()` guard,
    which spans every single-valued clause, not just `state { }`)."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_duplicate_probe(rule_name), "dup.cardlang")
    message = exc.value.diagnostic.message
    assert f"declares one `{SINGLE_VALUED[rule_name]}`" in message
    assert exc.value.diagnostic.span is not None


def test_missing_players_names_the_clause() -> None:
    text = BASE.replace("  players: 2\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message


def test_missing_content_clause_names_both_spellings() -> None:
    """A game with neither content clause is told about both, so the fix is
    visible whichever flavor the designer meant."""
    text = BASE.replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `cards: <deck>` or `pieces: <set>`" in exc.value.diagnostic.message


def test_missing_players_and_cards_reports_both() -> None:
    """The bag-first idiom: a game missing both mandatory clauses hears
    about both in one failure (second as a note), not one per round-trip."""
    text = BASE.replace("  players: 2\n", "").replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message
    notes = getattr(exc.value, "__notes__", [])
    assert any(
        "must declare `cards: <deck>` or `pieces: <set>`" in note for note in notes
    )


def test_no_game_block_rejected() -> None:
    """`start: top_item+` accepts a game-less source; without this guard it
    would escape as a StopIteration inside lark's VisitError."""
    text = "rule nothing {\n  demands: cards in hand\n}\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "declares no `game { }` block" in exc.value.diagnostic.message


def test_two_game_blocks_rejected_at_the_second() -> None:
    """Without this guard, a second game block would be silently discarded
    (first-wins)."""
    text = BASE + BASE.replace("Probe", "Probe2")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "2 `game { }` blocks" in exc.value.diagnostic.message
    span = exc.value.diagnostic.span
    assert span is not None and span.line == len(BASE_LINES) + 1


@pytest.mark.parametrize("value", ["clockwise", "counterclockwise"])
def test_known_directions_accepted(value: str) -> None:
    text = BASE.replace("  max_length", f"  direction: {value}\n  max_length")
    check_dsl(text, "probe.cardlang")


def test_unknown_direction_rejected() -> None:
    """Without this guard, `direction: anticlockwise` would be silently read as
    clockwise (driver.py's `!= "counterclockwise"` test) — the resolve guard
    names the value set instead."""
    text = BASE.replace("  max_length", "  direction: anticlockwise\n  max_length")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "unknown direction 'anticlockwise'" in exc.value.diagnostic.message


# --- the content-clause axis: `cards:` / `pieces:` -------------------------
# Rejection-corpus twins of these probes: tests/rejections/
# {pieces_and_cards_together, pieces_unknown_set, pieces_names_a_deck,
# cards_names_a_piece_set, duplicate_pieces_clause}.

# The piece mirror of BASE. Deliberately free of card-noun constructs
# (movements, card queries, ranking): the clause is live before the piece
# noun/flavor semantics, so this pins the surface that must already compile.
PIECE_BASE_LINES: tuple[str, ...] = (
    "game PieceProbe {",
    "  players: 2",
    "  pieces: xo_marks",
    "  max_length: 10",
    "  state { score[player] : Integer = 0 }",
    "  winner: highest score",
    "}",
)
PIECE_BASE = "\n".join(PIECE_BASE_LINES) + "\n"


def test_piece_probe_is_accepted() -> None:
    check_dsl(PIECE_BASE, "piece.cardlang")


def test_content_flavor_stamped_from_clause() -> None:
    """`Game.content_flavor` records WHICH clause appeared — stamped at
    parse, the single source resolve's flavor guards dispatch on. `Game.deck`
    holds the selected set name for both flavors."""
    assert parse_text(BASE, "base.cardlang").content_flavor == "card"
    game = parse_text(PIECE_BASE, "piece.cardlang")
    assert game.content_flavor == "piece"
    assert game.deck == "xo_marks"


def test_both_content_clauses_rejected() -> None:
    """`cards:` and `pieces:` both select the game's one component set; a
    game declaring both is rejected at parse, pointing at the later clause."""
    text = BASE.replace("  max_length", "  pieces: xo_marks\n  max_length")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "a game declares `cards:` or `pieces:`, not both" in message
    span = exc.value.diagnostic.span
    assert span is not None and span.line == BASE_LINES.index("  max_length: 10") + 1


def test_cards_naming_a_piece_set_rejected() -> None:
    """A piece-flavored name under `cards:` gets the cross-flavor guard with
    the right clause named — never the unknown-deck list (the name IS
    known, just not a deck)."""
    text = BASE.replace("cards: standard52", "cards: xo_marks")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "'xo_marks' is a piece set" in message
    assert "`pieces: xo_marks`" in message


def test_pieces_naming_a_card_deck_rejected() -> None:
    text = PIECE_BASE.replace("pieces: xo_marks", "pieces: standard52")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "'standard52' is a card deck" in message
    assert "`cards: standard52`" in message


def test_unknown_piece_set_lists_piece_sets_only() -> None:
    """The unknown-name diagnostic lists the sets of the CLAUSE'S flavor: a
    designer who wrote `pieces:` is choosing among piece sets, and the deck
    list would be noise."""
    text = PIECE_BASE.replace("pieces: xo_marks", "pieces: chess_men")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "unknown piece set 'chess_men'" in message
    assert "xo_marks" in message
    assert "standard52" not in message


def test_unknown_deck_lists_card_decks_only() -> None:
    """The card-side twin: the pre-`pieces:` message survives verbatim, and
    the piece sets never leak into its list."""
    text = BASE.replace("cards: standard52", "cards: nosuch99")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "unknown deck 'nosuch99'" in message
    assert "standard52" in message
    assert "xo_marks" not in message


def test_content_flavor_in_ir_only_for_piece_games() -> None:
    """The IR keys `content_flavor` only when it is "piece": the card-game
    IR predates the field and its goldens are byte-stable, so an absent key
    means "card". The deck key carries the selected set name for both
    flavors, unchanged."""
    card_ir = emit(check_dsl(BASE, "base.cardlang"))
    assert "content_flavor" not in card_ir
    assert card_ir["deck"] == "standard52"
    piece_ir = emit(check_dsl(PIECE_BASE, "piece.cardlang"))
    assert piece_ir["content_flavor"] == "piece"
    assert piece_ir["deck"] == "xo_marks"
