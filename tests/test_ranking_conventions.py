"""Ranking conventions: the closed `RANKING_CONVENTIONS` registry, its
grammar surface, and its per-deck expansion.

A convention (`ranking: aces high` / `aces low` / `ace-ten` / `twos high`)
is recognized at parse time — the space forms by exact spelling against the
registry (a grammar alternative would be a real Earley ambiguity against
`card_rank+`; see the grammar's `ranking` comment), the hyphenated
`ace-ten` by the RANK_CONV terminal — and expanded at resolve time against
the declared deck (`resolve._expand_ranking` →
`values.expand_ranking_convention`). This module is the completeness gate
for that surface.

Completeness ledger (decisions.md "Surface totality" /
"Closed-domain completeness")
-----------------------------------------------------------------
property:   every (convention, deck) pair either expands to the frozen
            expected strongest-first tuple or is rejected with a spanned
            diagnostic naming the offending ranks; every registry key is
            reachable from source text and every parseable convention
            spelling is a registry key; each corpus migration's expansion
            equals the enumeration it replaced.
domain:     RANKING_CONVENTIONS keys x (DECKS ∪ {unknown deck}) — plus the
            clause-form misuse space (misspelling, word flip, case flip,
            space-for-hyphen, mixed convention+ranks).
registry:   `cardlang.runtime.values.RANKING_CONVENTIONS` and
            `cardlang.runtime.values.DECKS` — both axes iterated from the
            registries in `test_every_deck_convention_cell_is_classified`,
            so a new deck or convention fails loudly until classified in
            _FRENCH_EXPANSIONS / _NON_FRENCH_DECKS below (the two-way pin
            idiom).
covered:    all 28 French cells (7 decks x 4 conventions, frozen expected
            tuples); all 20 non-French cells (5 decks x 4 conventions, wall
            probed through real source per deck and per convention); the
            unknown-deck degrade; registry↔grammar reconciliation in both
            directions; the reserved-spelling pin; the 14 corpus migration
            equivalences (pre-migration literals frozen here verbatim).
sampled:    the "did you mean" hint is probed on four representative
            misspellings (word flip, case flip, space-for-hyphen, plausible
            non-convention), not on every string within edit distance of a
            key — the hint is advisory text on an already-loud diagnostic.
residual:   partial-enumeration runtime KeyError (`rank_value` on a rank
            outside a partial `ranking:`) is the standing recorded residual
            (the ledger in tests/test_ranking_wall.py) and is
            unreachable from a convention, which is always a full
            permutation of its deck by construction. (A duplicated
            `ranking:` clause — convention or enumeration — is walled at
            parse by the game-clause `once` sweep,
            tests/test_game_clause_walls.py, so it is that ledger's cell,
            not a residual here.)

Rendered-diagnostic goldens for the walls live in `tests/rejections/`
(ranking_unknown_convention, ranking_convention_non_french_deck,
ranking_mixed_convention_and_ranks).
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.resolve import resolve
from cardlang.runtime.values import (
    DECKS,
    RANKING_CONVENTIONS,
    expand_ranking_convention,
)

GAMES = Path(__file__).parent.parent / "docs" / "games"

# One corpus file per deck — the probe vehicle: real source with the
# `ranking:` line swapped (or inserted after `cards:` for the games that
# declare none). Pinned two-way against DECKS below.
_DECK_GAME: dict[str, str] = {
    "standard52": "hearts.cardlang",
    "schnapsen20": "schnapsen.cardlang",
    "pinochle48": "pinochle.cardlang",
    "doppelkopf48": "doppelkopf.cardlang",
    "skat32": "skat.cardlang",
    "tarot78": "french-tarot.cardlang",
    "tichu56": "tichu.cardlang",
    "five_hundred43": "five-hundred.cardlang",
    "coup15": "coup.cardlang",
    "canasta108": "canasta.cardlang",
    "kuhn3": "kuhn-poker.cardlang",
    "leduc6": "leduc-poker.cardlang",
}

# The frozen expansion table: every (deck, convention) cell for the decks
# whose ranks are all French. Literal tuples, never derived — deriving them
# through the template filter would measure the implementation against
# itself.
_FRENCH_EXPANSIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("standard52", "aces high"): ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"),
    ("standard52", "aces low"): ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A"),
    ("standard52", "ace-ten"): ("A", "10", "K", "Q", "J", "9", "8", "7", "6", "5", "4", "3", "2"),
    ("standard52", "twos high"): ("2", "A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3"),
    ("schnapsen20", "aces high"): ("A", "K", "Q", "J", "10"),
    ("schnapsen20", "aces low"): ("K", "Q", "J", "10", "A"),
    ("schnapsen20", "ace-ten"): ("A", "10", "K", "Q", "J"),
    ("schnapsen20", "twos high"): ("A", "K", "Q", "J", "10"),
    ("pinochle48", "aces high"): ("A", "K", "Q", "J", "10", "9"),
    ("pinochle48", "aces low"): ("K", "Q", "J", "10", "9", "A"),
    ("pinochle48", "ace-ten"): ("A", "10", "K", "Q", "J", "9"),
    ("pinochle48", "twos high"): ("A", "K", "Q", "J", "10", "9"),
    ("doppelkopf48", "aces high"): ("A", "K", "Q", "J", "10", "9"),
    ("doppelkopf48", "aces low"): ("K", "Q", "J", "10", "9", "A"),
    ("doppelkopf48", "ace-ten"): ("A", "10", "K", "Q", "J", "9"),
    ("doppelkopf48", "twos high"): ("A", "K", "Q", "J", "10", "9"),
    ("skat32", "aces high"): ("A", "K", "Q", "J", "10", "9", "8", "7"),
    ("skat32", "aces low"): ("K", "Q", "J", "10", "9", "8", "7", "A"),
    ("skat32", "ace-ten"): ("A", "10", "K", "Q", "J", "9", "8", "7"),
    ("skat32", "twos high"): ("A", "K", "Q", "J", "10", "9", "8", "7"),
    # The poker-toy decks. Both are all-French (J/Q/K only), so all eight
    # cells expand rather than reject — and all four conventions COLLAPSE to
    # the same tuple on each, because every convention is the aces-high
    # template with A, 10 or 2 moved, and a J/Q/K deck holds none of those
    # three ranks. The cells are frozen individually anyway (never derived
    # from one another): the collapse is a fact about these decks that the
    # table should record, not an invariant to assume — a convention that
    # reordered the face cards would break it, and these rows are where that
    # would show up.
    ("kuhn3", "aces high"): ("K", "Q", "J"),
    ("kuhn3", "aces low"): ("K", "Q", "J"),
    ("kuhn3", "ace-ten"): ("K", "Q", "J"),
    ("kuhn3", "twos high"): ("K", "Q", "J"),
    ("leduc6", "aces high"): ("K", "Q", "J"),
    ("leduc6", "aces low"): ("K", "Q", "J"),
    ("leduc6", "ace-ten"): ("K", "Q", "J"),
    ("leduc6", "twos high"): ("K", "Q", "J"),
}

# The decks a convention must REJECT (ranks outside the French set). One
# non-French rank rejects the whole convention (the game enumerates
# explicitly instead): five_hundred43 and canasta108 are otherwise French
# but for the Joker (canasta108 an otherwise-French double pack).
_NON_FRENCH_DECKS = frozenset(
    {"tarot78", "tichu56", "coup15", "five_hundred43", "canasta108"}
)


def _probe_source(deck: str, ranking_clause: str) -> str:
    """The deck's corpus game with its `ranking:` clause replaced by (or, for
    the games that declare none, inserted as) `ranking_clause`."""
    text = (GAMES / _DECK_GAME[deck]).read_text()
    if re.search(r"^\s*ranking:.*$", text, flags=re.MULTILINE):
        return re.sub(r"^(\s*)ranking:.*$", rf"\g<1>{ranking_clause}", text, count=1, flags=re.MULTILINE)
    return text.replace(f"cards: {deck}", f"cards: {deck}\n  {ranking_clause}", 1)


# --- the DECKS x RANKING_CONVENTIONS matrix, both axes from the registry ---


def test_every_deck_convention_cell_is_classified() -> None:
    """The two-way pin: every deck in DECKS is either in the frozen French
    expansion table (for all four conventions) or in _NON_FRENCH_DECKS, and
    has a probe vehicle — so adding a deck or a convention fails HERE until
    the new cells are classified, rather than going silently uncovered."""
    for deck in DECKS:
        assert deck in _DECK_GAME, f"no probe vehicle for deck {deck!r}"
        if deck in _NON_FRENCH_DECKS:
            # Its 12 wall cells are exercised by
            # test_non_french_cell_rejects_through_real_source.
            continue
        for conv in RANKING_CONVENTIONS:
            assert (deck, conv) in _FRENCH_EXPANSIONS, (
                f"unclassified cell ({deck!r}, {conv!r}) — freeze its expected "
                f"expansion in _FRENCH_EXPANSIONS or classify the deck non-French"
            )
    for deck, conv in _FRENCH_EXPANSIONS:
        assert deck in DECKS and conv in RANKING_CONVENTIONS
    assert _NON_FRENCH_DECKS <= set(DECKS)
    assert set(_DECK_GAME) == set(DECKS)


@pytest.mark.parametrize(("deck", "conv"), sorted(_FRENCH_EXPANSIONS))
def test_french_cell_expands_to_frozen_tuple(deck: str, conv: str) -> None:
    assert expand_ranking_convention(conv, deck) == _FRENCH_EXPANSIONS[(deck, conv)]


@pytest.mark.parametrize("deck", sorted(_NON_FRENCH_DECKS))
@pytest.mark.parametrize("conv", sorted(RANKING_CONVENTIONS))
def test_non_french_cell_rejects_through_real_source(deck: str, conv: str) -> None:
    """Every non-French wall cell, through the full pipeline: the diagnostic
    names the convention and says to enumerate instead."""
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(_probe_source(deck, f"ranking: {conv}"), "probe.cardlang"))
    assert "outside the standard A..2 set" in str(exc.value)
    assert conv in str(exc.value)


def test_convention_with_unknown_deck_degrades_to_the_deck_diagnostic() -> None:
    """No expansion is attempted for a deck the registry doesn't know: the
    author sees the unknown-deck error, never a KeyError or a convention
    error about a deck that doesn't exist."""
    src = _probe_source("standard52", "ranking: aces high").replace(
        "cards: standard52", "cards: nosuchdeck"
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(src, "probe.cardlang"))
    assert "unknown deck 'nosuchdeck'" in str(exc.value)


# --- registry <-> grammar reconciliation, both directions ---


def test_every_registry_key_parses_to_its_convention() -> None:
    """Accepting direction: each RANKING_CONVENTIONS key, written in source,
    parses to the convention form (empty ranks) — which is also the
    reserved-spelling pin: these spellings can never be read as an
    enumeration of same-named ranks."""
    for key in RANKING_CONVENTIONS:
        g = parse_text(_probe_source("standard52", f"ranking: {key}"), "probe.cardlang")
        assert g.ranking_convention == key and g.ranking == (), key


def test_every_grammar_convention_terminal_is_a_registry_key() -> None:
    """Rejecting direction of the two-source pin: the RANK_CONV terminal in
    the grammar file is the ONLY convention spelling source besides the
    registry (space forms are recognized FROM the registry, so they cannot
    drift). Extract its literal alternatives and require each to be a
    registry key — a terminal spelling the registry doesn't know would
    parse to a convention `_expand_ranking` KeyErrors on."""
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    m = re.search(r"^RANK_CONV[^:]*:\s*/(.+)/\s*$", grammar, flags=re.MULTILINE)
    assert m is not None, "RANK_CONV terminal not found in grammar"
    body = re.sub(r"\(\?!.*?\)", "", m.group(1))  # strip the anchor lookahead
    literals = {w for w in re.split(r"[^A-Za-z0-9-]+", body) if w}
    assert literals, "RANK_CONV terminal matched no literal spellings"
    for lit in literals:
        assert lit in RANKING_CONVENTIONS, (
            f"grammar RANK_CONV spelling {lit!r} has no RANKING_CONVENTIONS entry"
        )


@pytest.mark.parametrize(
    "clause",
    ["aces sideways", "high aces", "Aces High", "ace ten", "twos low"],
)
def test_misspelled_convention_rejects_with_the_hint(clause: str) -> None:
    """Misuse probes: word flip, case flip, space-for-hyphen, and plausible
    non-conventions all fall to the enumeration arm and reject as unknown
    ranks WITH the hint naming the closed convention set."""
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(_probe_source("standard52", f"ranking: {clause}"), "probe.cardlang"))
    msg = str(exc.value)
    assert "names unknown rank" in msg
    assert "did you mean a ranking convention" in msg


def test_plain_unknown_rank_gets_no_convention_hint() -> None:
    """The hint keys on convention vocabulary — an ordinary rank typo keeps
    the plain unknown-rank message (asserting the hint's absence pins that
    it is conditional, not blanket noise)."""
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(_probe_source("standard52", "ranking: A K Q 11"), "probe.cardlang"))
    msg = str(exc.value)
    assert "names unknown rank '11'" in msg
    assert "did you mean a ranking convention" not in msg


# --- the corpus migrations: expansion == the enumeration each replaced ---

# The pre-migration `ranking:` literals, frozen verbatim from the corpus as
# it stood before the conventions change (git history is the provenance).
# Byte-identical playout/openspiel goldens prove behavior; this pins the
# expansions themselves, so a template edit that happened to keep traces
# stable on today's seeds still fails loudly.
_PRE_MIGRATION: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "bridge": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "getaway": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "go-fish": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "hearts": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "oh-hell": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "seven-card-stud": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "spades": ("aces high", "standard52", ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")),
    "gops": ("aces low", "standard52", ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A")),
    "president": ("twos high", "standard52", ("2", "A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3")),
    "skat": ("ace-ten", "skat32", ("A", "10", "K", "Q", "J", "9", "8", "7")),
    # Belote postdates the migration (born on the convention): its row
    # freezes the expansion it was written against — the plain-suit play
    # order; the within-trump J-9 reorder is suit-contextual, outside
    # `ranking:`'s scope, and lives in the belote_* primitives.
    "belote": ("ace-ten", "skat32", ("A", "10", "K", "Q", "J", "9", "8", "7")),
    "doppelkopf": ("ace-ten", "doppelkopf48", ("A", "10", "K", "Q", "J", "9")),
    "pinochle": ("ace-ten", "pinochle48", ("A", "10", "K", "Q", "J", "9")),
    "schnapsen": ("ace-ten", "schnapsen20", ("A", "10", "K", "Q", "J")),
    # Cribbage's old line was `A 2 3 ... K` — an ascending order-only device
    # whose rank_index nothing read (the run scorers used a private table,
    # since deleted). Its migration target `aces low` is the REVERSE, whose
    # adjacency structure is identical (dense consecutive strengths, A next
    # to 2, no wraparound) and whose strength direction finally matches the
    # game's own "A low" intent; equivalence is behavioral (byte-identical
    # playout goldens + the scorer unit tests), not tuple-equality, so its
    # row freezes the NEW expansion.
    "cribbage": ("aces low", "standard52", ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A")),
    # Cheat is convention-BORN, not migrated: it joined the corpus already
    # declaring `aces low` (no pre-migration literal exists; the game never
    # compares rank strength — the convention only fixes the Rank
    # enumeration order, which its claim cycle reads A -> K). Its row
    # freezes the expansion it was born onto, so the two-way pin below
    # keeps covering it like every other convention game.
    "cheat": ("aces low", "standard52", ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A")),
    # Klondike and FreeCell post-date the migration (no pre-migration
    # literal exists); like cribbage's row, theirs freeze the expansion the
    # games were BUILT against — the A=0..K=12 scale every foundation/build
    # guard's rank arithmetic assumes — so a template edit that kept other
    # games stable still fails loudly here.
    "klondike": ("aces low", "standard52", ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A")),
    "freecell": ("aces low", "standard52", ("K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "A")),
    # The poker toys are convention-BORN too, on the only decks in the corpus
    # whose four conventions coincide (see the kuhn3/leduc6 block above).
    # Their rows freeze the expansion the games were built against — the
    # J<Q<K strength order both showdowns compare through `rank_value` — so a
    # template edit that reordered the face cards fails here even though the
    # games' declared `aces high` would still parse.
    "kuhn-poker": ("aces high", "kuhn3", ("K", "Q", "J")),
    "leduc-poker": ("aces high", "leduc6", ("K", "Q", "J")),
}


def test_every_corpus_convention_matches_its_frozen_migration_row() -> None:
    """Two-way: every corpus game declaring a convention has a frozen row
    whose (convention, deck, expansion) all match, and every frozen row
    names a real corpus game still declaring that convention."""
    seen: set[str] = set()
    for path in sorted(GAMES.glob("*.cardlang")):
        g = parse_text(path.read_text(), str(path))
        if g.ranking_convention is None:
            continue
        assert path.stem in _PRE_MIGRATION, f"unfrozen convention game {path.stem}"
        conv, deck, expected = _PRE_MIGRATION[path.stem]
        assert g.ranking_convention == conv, path.stem
        assert g.deck == deck, path.stem
        assert expand_ranking_convention(conv, deck) == expected, path.stem
        seen.add(path.stem)
    assert seen == set(_PRE_MIGRATION), (
        f"frozen rows without a corpus witness: {set(_PRE_MIGRATION) - seen}"
    )
