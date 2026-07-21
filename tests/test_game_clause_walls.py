"""Game-clause structural walls: omission and duplication over the whole
clause domain of the `game` production.

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
            multiple `game { }` blocks, or a `direction:` outside its value
            set — fails `check_dsl` with a located `DiagnosticError`, never
            a bare assert / raw lark error / silently different meaning.
domain:     the `?game_item` alternatives of the `game` production, times
            {omitted, duplicated, ABSORBED}; plus the game-count axis of
            `start` (zero / one / many); plus the `direction:` value axis.
            The absorption axis was added after `uses <library>` was found
            to vanish when written below `ranking:` — `ranking:` takes an
            unbounded `card_rank+` run, so a clause spelled as two bare
            names is eaten by it with no error. That is a property of the
            RANKING production, not of `uses`, so it is swept over every
            clause rather than probed on the one that was found broken.
            The axis has TWO absorbers, because the class is "an unbounded
            or empty slot completes itself from the clause below it": the
            `card_rank+` run, and an empty EXPRESSION slot, which reads a
            single-entry brace clause as a `struct_lit`. The second was
            found as `function f() =` swallowing a library's `requires`
            block, and holds identically for a game's `loser:` swallowing
            `zones { }`. Its fix is at the absorbed end — the keyword is
            refused as a struct-literal type name — so its domain is a
            SHAPE, not a registry membership: every keyword opening a
            `kw "{" <entry>* "}"` block whose entry begins with NAME,
            wherever in the grammar it is reachable from. Reading the domain
            off `?game_item`/`?library_item` instead was wrong twice — those
            are a coincidental superset (2 of 21 keywords are load-bearing)
            and a coincidental non-superset (a brace clause reachable as a
            `?phase_item` or `?top_item` is outside them, and `derived` was
            in fact missing). The axis is crossed with {absorbed-as-a-
            literal, declarable-as-a-type}, the second being the cost the
            exclusion imposes on `type_def`, which must stay symmetric with
            `struct_lit` or a type is declarable and unusable. That
            symmetry has a THIRD position — the type ANNOTATION slots
            (`type_name`, `type_ref`, `payload_type`, `type_arg`), all
            plain NAME — so the terminal must also stay a strict SUBSET of
            NAME, whose own lookahead it repeats.
registry:   `cardlang/grammar/cardlang.lark` (`?game_item`) — scraped here
            by `_game_item_alternatives`, so a clause added to the grammar
            fails `test_game_item_registry_pin` until it is classified
            below; `?library_item` likewise by `library_item_alternatives`,
            which the import tier's own module reuses; `GAME_DIRECTIONS` in
            `cardlang/runtime/values.py` for the direction value set;
            `CARD_RANK_NAME`'s and `STRUCT_TYPE_NAME`'s negative lookaheads
            for the two absorption legs, scraped by `_card_rank_excluded`
            and `_struct_type_excluded` so both sides of each pin stay
            derived.
covered:    duplication — exhaustively, every single-valued clause (all
            alternatives except `phase`), one probe each, parse-layer wall;
            omission — `players:`/`cards:` (parse wall, including the
            both-at-once bag rendering), `max_length:` and joint
            `winner:`/`loser:` (resolve walls, pinned by their own
            rejection fixtures), `state`/`zones`/`trump`/`partnerships`/
            `direction`/`ranking` omission is legal by design (probed by
            the valid BASE game here, which omits four of them);
            game-count — zero and two, parse wall; absorption —
            exhaustively, every clause written after a `ranking:`
            enumeration and asserted to parse as itself, and every clause
            written after an EMPTY `loser:` and asserted to be refused at
            the parse layer, plus, for STRUCT_TYPE_NAME, three static pins
            with both sides derived: the absorbable-shape domain, the
            subset-of-NAME invariant, and the belt-and-braces clause set
            declared as such so it is not mistaken for the argument. The
            LIBRARY half of the same absorber — an empty `function f() =`
            over each `?library_item` — is executed as the 49-cell
            truncation grid in tests/test_family_libraries.py, not
            re-probed here. The exclusion's cost — exhaustively, `type
            <word> = { }` refused for every word the terminal excludes.
            `loser:` is the only game clause whose last slot is a bare
            `expr`, checked against the grammar rather than assumed:
            `winner:` takes `rank_dir NAME`.
sampled:    `ranking:` omission with rank-dependent constructs in play is
            typecheck's `has_ranking` gate (tests/test_ranking_wall.py);
            zero-`phase` games are accepted with defined degenerate
            semantics (no decisions; result read from initial state —
            verified by playout while authoring this module, not pinned
            here: the cell is "accepted", and pinning acceptance is the
            valid-BASE probe's job).
residual:   the declaration/use symmetry the struct-literal exclusion
            enforces on the NAME axis is not enforced on the ARITY axis:
            `type_def` takes `struct_field*` while `struct_lit` requires at
            least one field, so `type Bid = { }` is accepted and can never
            be constructed — declarable-but-unusable, the same property, one
            axis over. Pre-existing (it parses identically before and after
            the terminal), but inside the domain this module claims, so it
            is named rather than left to look walled. Wall: the empty type
            is inert — nothing can construct it, so no game can depend on
            one silently doing something. Recorded in docs/roadmap.md,
            "An empty `type X = { }` is declarable but not constructible".
            Every other cell above is walled or legal-by-design.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from lark import Tree

import cardlang
from cardlang.diagnostics import DiagnosticError
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


def _clause_keyword(rule_name: str) -> str:
    """The literal keyword a clause production opens with, read from the grammar
    rather than mapped by hand: `uses_decl: "uses" NAME` -> `uses`, and
    `state_block: "state" "{" ...` -> `state`, neither of which matches its rule
    name."""
    match = re.search(rf'^{rule_name}:\s*"([a-z_]+)"', GRAMMAR, re.MULTILINE)
    assert match is not None, f"clause `{rule_name}` opens with no literal keyword"
    return match.group(1)


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
    "players": "players: 3",
    "direction": "direction: clockwise",
    "cards": "cards: skat32",
    "ranking": "ranking: K Q J",
    "trump": "trump: hearts",
    "partnerships": "partnerships: [[0, 2], [1, 3]]",
    "max_length": "max_length: 10",
    "positions": "positions { column : 1..7 }",
    "zones": "zones { stock : Deck }",
    "state_block": "state { score[player] : Integer = 0 }",
    "phase": "phase p { }",
    "winner": "winner: highest score",
    # `loser:` takes an expr, not `winner:`'s `rank_dir NAME`.
    "loser": "loser: score",
}


# --- the second absorber: an expression slot, via `struct_lit` ----------------
#
# `struct_lit: NAME "{" field_init ("," field_init)* "}"` with
# `field_init: NAME ":" expr` is token-identical to a single-entry brace clause
# (`zones { deck : Deck }`, `requires { y : Integer }`). So an expression slot
# left EMPTY — a `loser:` with no expression, a `function f() =` with no body —
# reads the clause written below it as a struct literal and completes, dropping
# the clause with no error and no `_ambig` node for the ambiguity budget to
# catch. The fix is at the ABSORBED end, not the absorbing one: a clause
# keyword is refused as a struct-literal type name, which closes every
# expression slot in the grammar at once, so the domain below is the clause
# KEYWORD registry rather than the set of slots that can do the absorbing.


def _clause_keywords() -> set[str]:
    """Every clause keyword a struct-literal type name must refuse, from BOTH
    sibling-sequence registries: `?game_item` (a game file) and `?library_item`
    (a family-library file)."""
    return {
        _clause_keyword(rule)
        for rule in _game_item_alternatives() | library_item_alternatives()
    }


def _struct_type_excluded() -> set[str]:
    return _terminal_excluded("STRUCT_TYPE_NAME")


def _absorbable_clause_keywords() -> set[str]:
    """The TRUE domain of the struct-literal exclusion: every keyword opening a
    `kw "{" <entry>* "}"` block whose ENTRY production begins with `NAME`, since
    those are exactly the clauses whose text can match a struct literal's
    `NAME "{" NAME ":" expr … "}"`.

    Derived from the block productions themselves rather than from the clause
    registries. `?game_item`/`?library_item` are a coincidental superset — of
    their 21 keywords only two are load-bearing — and, worse, a coincidental
    NON-superset: a brace clause reachable as a `?phase_item` or a `?top_item`
    would sit outside them entirely, so a pin over the registries can go green
    while a new clause is silently absorbed.

    One stated assumption: the scrape reads the `<entry>*` form only, not
    `<entry> ("," <entry>)*`. Every brace clause in the grammar uses the star
    form today (checked by `test_every_brace_clause_uses_the_star_form` below),
    and a comma-form clause would be MORE absorbable, not less, since
    `struct_lit`'s own field list is comma-separated."""
    required = set()
    for keyword, entry in re.findall(
        r'^\w+:\s*"([a-z_]+)"\s*"\{"\s*(\w+)\*\s*"\}"', GRAMMAR, re.MULTILINE
    ):
        if re.search(rf"^{entry}:\s*NAME\b", GRAMMAR, re.MULTILINE):
            required.add(keyword)
    assert required, "scrape found no brace-clause productions at all"
    return required


def test_every_brace_clause_uses_the_star_form() -> None:
    """The assumption `_absorbable_clause_keywords`'s scrape rests on. A brace
    clause written `kw "{" <entry> ("," <entry>)* "}"` would be invisible to that
    scrape and MORE absorbable than the star form, since `struct_lit`'s own field
    list is comma-separated — so the tripwire has to be here rather than in a
    comment nobody re-checks.

    red under: rewrite any `kw "{" X* "}"` production in the comma form."""
    comma_form = re.findall(
        r'^(\w+):\s*"[a-z_]+"\s*"\{"\s*\w+\s*\("," ?\s*\w+\)\*', GRAMMAR, re.MULTILINE
    )
    assert not comma_form, (
        f"brace clause(s) {comma_form} use the comma form, which "
        f"`_absorbable_clause_keywords` does not scrape — widen it"
    )


def test_struct_type_name_excludes_every_absorbable_clause() -> None:
    """The completeness pin, both sides derived: the keyword set from the shape
    that makes a clause absorbable, the exclusion set from the terminal. A brace
    clause added ANYWHERE in the grammar — game item, phase item, top item — with
    field-init-shaped entries fails here rather than at a designer's desk.

    red under: delete `zones` (or `derived`) from STRUCT_TYPE_NAME's exclusion
    list in cardlang.lark."""
    missing = _absorbable_clause_keywords() - _struct_type_excluded()
    assert not missing, (
        f"brace clause(s) {sorted(missing)} have field-init-shaped entries and are "
        f"still legal struct-literal type names, so an empty expression slot can "
        f"absorb one and drop it silently — add them to STRUCT_TYPE_NAME's "
        f"exclusion list in cardlang.lark"
    )


def test_struct_type_name_stays_a_subset_of_name() -> None:
    """A position-specific terminal may only ever REMOVE spellings. NAME carries
    its own negative lookahead (`always|all|one|some|…`), so a STRUCT_TYPE_NAME
    that does not repeat those words ADMITS eight spellings NAME refuses — and
    every type-ANNOTATION position (`type_name`, `type_ref`, `payload_type`,
    `type_arg`) is plain NAME and still refuses them. That is a type declarable
    and constructible but never usable: the same declarable-but-unusable defect
    the exclusion exists to prevent, reopened on the other axis.

    red under: delete any word of NAME's lookahead from STRUCT_TYPE_NAME's."""
    admitted = _terminal_excluded("NAME") - _struct_type_excluded()
    assert not admitted, (
        f"STRUCT_TYPE_NAME admits {sorted(admitted)}, which NAME refuses — a type "
        f"named for one of those could be declared and written as a literal but "
        f"never annotated, since every type-annotation slot is plain NAME"
    )


def test_the_clause_keyword_exclusions_are_belt_and_braces() -> None:
    """The clause registries are NOT this exclusion's completeness argument —
    `test_struct_type_name_excludes_every_absorbable_clause` is. They are kept
    excluded anyway, so that a clause which later grows field-init-shaped
    entries is already covered, and this test says so rather than letting a
    reader mistake the wider set for the derivation."""
    assert _clause_keywords() <= _struct_type_excluded()


@pytest.mark.parametrize("rule_name", sorted(_game_item_alternatives()))
def test_no_clause_is_absorbed_by_an_empty_expression_slot(rule_name: str) -> None:
    """`loser:` is the one game clause whose last slot is a bare `expr`, so it
    is the game-file end of the absorption class. Left empty it must fail to
    parse — never quietly take the next clause as its expression.

    Asserted at the PARSE layer deliberately: the absorbed reading is a
    well-formed parse, and letting a later stage reject it for some other
    reason (an unknown struct type) would make this cell green while the clause
    still vanished.

    One cell was open when this sweep was written: `zones { stock : Deck }`, the
    single-entry, unindexed, type-argument-free clause whose text is exactly
    `NAME "{" NAME ":" expr "}"`. The rest are refused by structure rather than
    by the fix — `state`'s decls carry `= <default>`, `positions`' carry a `..`
    range, and the others are not brace clauses at all — and are the sweep of
    the class.

    red under: delete `zones` from STRUCT_TYPE_NAME's exclusion list."""
    src = (
        "game G {\n  players: 2\n  cards: standard52\n  loser:\n"
        f"  {_CLAUSE_TEXT[rule_name]}\n}}"
    )
    with pytest.raises(DiagnosticError) as exc:
        parse_text(src, "absorb.cardlang")
    assert exc.value.diagnostic.span is not None, (
        "a parse-layer refusal must be located, not a bare error"
    )


@pytest.mark.parametrize("keyword", sorted(_struct_type_excluded()))
def test_a_type_may_not_be_declared_under_an_excluded_word(keyword: str) -> None:
    """The cost of the exclusion above, made explicit and swept over the
    exclusion set ITSELF rather than over a registry that merely overlaps it —
    so every word the terminal refuses is proven refused in declaration position
    too. A type whose name a struct literal cannot spell would be declarable but
    unusable — accepted-but-ignored one step removed — so the DECLARATION is
    refused too, keeping `type_def` and `struct_lit` symmetric about which names
    a struct type may take.

    red under: point `type_def`'s name back at plain `NAME` in cardlang.lark."""
    src = (
        f"type {keyword} = {{ x : Integer }}\n"
        "game G { players: 2 cards: standard52 zones { deck : Deck } }"
    )
    with pytest.raises(DiagnosticError) as exc:
        parse_text(src, "typename.cardlang")
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
    "ranking": "ranking:",
    "trump": "trump:",
    "partnerships": "partnerships:",
    "max_length": "max_length:",
    "positions": "positions { }",
    "zones": "zones { }",
    "state_block": "state { }",
    "winner": "winner:",
    "loser": "loser:",
}

# A minimal valid game (also the acceptance probe: it omits `direction:`,
# `ranking:`, `trump:`, and `partnerships:`, pinning that those omissions
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
# clauses BASE does not already carry. The duplicate wall fires at parse
# time, before resolve, so these only need to be grammatical.
_EXTRA_CLAUSE: dict[str, str] = {
    "positions": "  positions { column : 1..3 }",
    "direction": "  direction: clockwise",
    "ranking": "  ranking: A K Q J 10 9 8 7 6 5 4 3 2",
    "trump": "  trump: spades",
    "partnerships": "  partnerships: [[0, 1]]",
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
# and with where its own repeat-abuse wall lives — a clause is not exempt from
# duplication checking just by being here, it is checked somewhere else.
#
#   phase      — a game is a sequence of phases; repetition IS the construct.
#   uses_decl  — a game uses as many family libraries as it draws on
#                (decisions.md "Family libraries"). Repeating the SAME library is
#                still a defect, and is walled in `resolve._apply_uses`, not in
#                parse: only resolve knows the library names.
REPEATABLE: dict[str, str] = {
    "phase": "a game is a sequence of phases",
    "uses_decl": "a game may use several libraries; the repeated-NAME wall is "
    "in resolve._apply_uses, which is the pass that knows library names",
}


def test_game_item_registry_pin() -> None:
    """The domain this module quantifies over IS the grammar's clause list:
    a new `?game_item` alternative must be classified here (single-valued or
    repeatable) before it can land."""
    alternatives = _game_item_alternatives()
    assert alternatives == set(SINGLE_VALUED) | set(REPEATABLE), (
        "the `game` production's clause list changed — classify the new "
        "clause in SINGLE_VALUED (or in REPEATABLE, with the reason and the "
        "location of its own repeat wall) and give it omission/duplication probes"
    )


def test_base_probe_is_accepted() -> None:
    check_dsl(BASE, "base.cardlang")


@pytest.mark.parametrize("rule_name", sorted(SINGLE_VALUED))
def test_duplicate_clause_rejected(rule_name: str) -> None:
    """Every single-valued clause, repeated, is rejected at the second
    occurrence — never silently last-wins (the parse.py `game()` wall,
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


def test_missing_cards_names_the_clause() -> None:
    text = BASE.replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `cards: <deck>`" in exc.value.diagnostic.message


def test_missing_players_and_cards_reports_both() -> None:
    """The bag-first idiom: a game missing both mandatory clauses hears
    about both in one failure (second as a note), not one per round-trip."""
    text = BASE.replace("  players: 2\n", "").replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message
    notes = getattr(exc.value, "__notes__", [])
    assert any("must declare `cards: <deck>`" in note for note in notes)


def test_no_game_block_rejected() -> None:
    """`start: top_item+` accepts a game-less source; without this wall it
    would escape as a StopIteration inside lark's VisitError."""
    text = "rule nothing {\n  demands: actions where true\n}\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "declares no `game { }` block" in exc.value.diagnostic.message


def test_two_game_blocks_rejected_at_the_second() -> None:
    """Without this wall, a second game block would be silently discarded
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
    """Without this wall, `direction: anticlockwise` would be silently read as
    clockwise (driver.py's `!= "counterclockwise"` test) — the resolve wall
    names the value set instead."""
    text = BASE.replace("  max_length", "  direction: anticlockwise\n  max_length")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "unknown direction 'anticlockwise'" in exc.value.diagnostic.message
