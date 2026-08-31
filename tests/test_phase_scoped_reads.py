"""The phase-scoped read declaration's coverage grid: `reads X in <phase>`.

A `primitives { }` entry may declare a read of state a PHASE declares, by
naming that phase (docs/plans/2026-08-30-phase-scoped-reads.md; issue #504).
The tail is declaration-only surface — nothing new is emitted — and it buys
one static obligation in exchange: an entry with a scoped read is callable
only where the named phase runs. This module is that change's grid, authored
red before the implementation: the born-red counts at the foot of this
docstring are its provenance.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   (1) every combination the extended `primitive_read` grammar
            accepts is implemented or refused with a named diagnostic in the
            layer that owns the class — never parsed and ignored; (2) a
            scoped read's tail names exactly ONE declaration: the named
            phase's own `state { }` entry, with no game-level, zone, sibling-
            phase or strict-descendant declaration of that name left able to
            answer instead; and (3) every call of an entry carrying a scoped
            read sits where the named phase's frame stands — inside that
            phase's subtree, or in a game move type every offering mention of
            which sits inside it, or at a `run` site inside it — so the
            runtime's innermost-frame walk returns the declared phase's value
            by construction rather than by luck.
domain:     the tail's own surface, crossed: SPELLING x {bare, `[binder]`} x
            {no tail, `in P`} (four accepted combinations, all implemented)
            plus the malformed spellings the grammar must refuse loud;
            REFERENT MEMBERSHIP — where the tailed name is declared, over the
            same four namespaces the untailed product uses
            (tests/test_primitives_block.py owns that product; this module
            crosses it with the tail) plus the two ancestry relations a flat
            membership set cannot see, "declared by a sibling phase only" and
            "re-declared by a STRICT DESCENDANT of the named phase";
            CLAUSE COMPOSITION x {game-level names beside scoped ones, two
            distinct phases in one clause, a scoped read on a PURE entry, one
            name written both bare and scoped}; CONTAINMENT POSITION — every
            syntactic position a `Call` to a declared Primitive can occupy,
            classified by the `n.Game` field its container hangs off and by
            the `PhaseItem` union inside a phase, both pinned TOTAL so a new
            field or item forces a decision rather than defaulting to
            "allowed"; the OFFERING SURFACE — the move-type-naming slots of
            resolve's `_REFERENCE_SLOTS`, classified offering / non-offering
            in one table pinned total against the derived candidates, so an
            eighth slot arrives unclassified and reddens; and the three
            standing collision arms, each re-probed WITH a tail present so
            the new surface cannot lift them silently.
registry:   `cardlang/grammar/cardlang.lark` (the `primitive_read`
            production and its reject twin, read as text by the spelling
            axis); `cardlang.ast.nodes.Game`'s field set and
            `cardlang.ast.nodes.PhaseItem`'s union (the containment
            taxonomy's totality); `cardlang.resolve._REFERENCE_SLOTS` (the
            offering-surface candidates) and
            `cardlang.resolve._MOVE_TYPE_SLOT_OFFERS` (their classification);
            `cardlang.primitives_block.PRIMITIVE_IMPLEMENTATIONS` (every
            fixture declares a REAL registered implementation);
            `cardlang.runtime.driver.run_phase` (the frame-liveness order the
            admitted positions rest on).
covered:    the parametrized cells below. The untailed membership product,
            the binder's domain identity, the reads clause as a multiset and
            the block's own shape axes are
            tests/test_primitives_block.py's and are cited, not re-run: this
            module crosses the tail with them and owns nothing they own. The
            rendered text of each new diagnostic is
            tests/test_rejections.py's, whose corpus this change extends.
sampled:    the ACCEPT half's call positions are carried by five corpus
            games (seven-card-stud, holdem, pinochle, french-tarot,
            canasta), of which pinochle lands in this change and the other
            four follow one PR each; the positions no corpus game reaches —
            a phase's own qualifier, `before_each` and `after_each` — are
            carried by one synthetic nested fixture whose playout records
            which position each scoped call came from, rather than by a
            fixture that merely resolves. Every REFUSAL cell is synthetic,
            because the corpus correctly holds no violation, and each ships
            with its accept twin (the same game with the offending element
            removed) so the arm is proven discriminating rather than merely
            loud.
does not prove: a green here says nothing about whether the runtime premise
            the containment guard leans on still holds — that a game move
            type's body executes only inside the dynamic extent of an
            offering site. That premise is a fact about the runtime, not
            about this guard, and `test_the_move_type_index_readers_are_the_
            pinned_census` prices it: it pins the consumer sites, so a new
            execution channel reddens there rather than making this guard
            silently unsound. Nor does a green say a scoped entry is ever
            CALLED: an entry with a scoped read and zero calls passes
            containment vacuously, and what keeps a block naming only names
            the game calls is the 3b recipe's discipline, not this grid.
            And a green says nothing about whether a declared read SUFFICES
            for its implementation — that is a fact about Python, proven only
            by a playout (tests/test_primitives_block.py's witness owns it).

Born red (this branch, before any of the tail's grammar, AST, resolve or
runtime existed): recorded at the foot of this docstring in two takes, because
one take would not discriminate. TAKE 1, the whole module against a tree with
no `in` tail in the grammar at all: every tail-bearing cell dies at the
lexer, which proves nothing about the arms it names. TAKE 2 — the
load-bearing one — after the grammar, AST and IR carry the tail and before a
single guard exists: the accept cells fail on a name nothing classifies, and
each refusal cell fails because no diagnostic fires, which is the red each
cell was written to record.

    take 1 (no grammar, 2026-08-30):      50 failed, 9 passed
    take 2 (grammar, no guards):          42 failed, 17 passed

Take 2 is the record that counts. Its accept cells die on a name nothing
classifies and its membership cells die because the untailed phase-local arm
answers a sentence that now names its phase — each the red the cell was
written for. Of take 2's 17 passes, four are born green and carry their
reddening mutation in their own docstring; the rest are refusals whose arm
already existed and which the tail must not lift.
"""

from __future__ import annotations

import dataclasses
import pathlib
import random
import re
import typing

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent


# --- the probe game ----------------------------------------------------------
#
# A complete, PLAYABLE two-seat game whose result is computed BY the declared
# Primitive, so a cell that merely resolves cannot pass for one that runs
# (tests/test_state_default_scope.py's recorded lesson, which both counsels
# cite). `pinochle_meld_value` is a real registered implementation, borrowed
# rather than minted: a fixture needing its own Python would prove the
# construct against an implementation written to suit it.

_ENTRY = (
    "pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit in outer"
)

# The declaring phase's body, dealing before it calls: the implementation
# raises on an undeclared trump, so every cell that calls it needs one, and
# `outer`'s own state default is where the scoped cells get it.
_DEAL = "    shuffle deck\n    deal 12 cards from deck to each hand\n"
_CALL = "    for each player p: meld[p] := pinochle_meld_value(p)\n"


def _probe(
    *,
    block: str | None = _ENTRY,
    top: str = "",
    zones: str = "",
    game_state: str = "",
    game_items: str = "",
    outer_qualifier: str = "",
    outer_state: str = "trump_suit : Suit? = spades",
    outer_items: str = "",
    outer_body: str = _DEAL + _CALL,
    after_outer: str = "",
    winner: str = "  winner: highest meld\n",
) -> str:
    """A probe game with `outer` as the declaring phase.

    Every slot is a string spliced at one place, so a cell reads as the ONE
    thing it varies from the accept baseline — which is what makes each
    refusal cell's accept twin the same call with the offending element
    removed."""
    state_block = f"    state {{ {outer_state} }}\n" if outer_state else ""
    return (
        top
        + "game Probe {\n"
        "  players: 2\n"
        "  max_length: 100\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        + ("  primitives { " + block + " }\n" if block is not None else "")
        + "  zones { deck : Deck  hand[player] : Hand<player>" + zones + " }\n"
        "  state { meld[player] : Integer = 0" + game_state + " }\n"
        + game_items
        + f"  phase outer {outer_qualifier}{{\n"
        + state_block
        + outer_items
        + outer_body
        + "  }\n"
        + after_outer
        + winner
        + "}\n"
    )


def _checks(source: str) -> n.Game:
    return check_dsl(source, "probe.cardlang")


def _refused(source: str) -> str:
    """Every diagnostic a refused probe produces, rendered. The whole bag, not
    the first item: a probe that trips two guards would otherwise be read
    against whichever spoke first, and which that is is not the cell's
    claim."""
    with pytest.raises(DiagnosticError) as excinfo:
        _checks(source)
    notes = list(getattr(excinfo.value, "__notes__", None) or [])
    return "\n".join([str(excinfo.value), *notes])


def _plays(source: str) -> object:
    """Check AND play. An accept cell that only resolved would assert exactly
    the property that hid the `test_state_default_scope` defect."""
    result = play_game(_checks(source), random.Random(0))
    assert set(result.scores) == {0, 1}, result.scores
    return result


# --- axis: SPELLING — {bare, binder} x {no tail, tail} -----------------------


def test_the_grammar_carries_the_tail_on_the_read_production() -> None:
    """The surface, read off the grammar rather than remembered: the tail is
    per-READ (so one clause may mix scoped and unscoped names), optional, and
    followed by a bare NAME.

    red under: move the tail onto `primitive_reads`, or drop it."""
    grammar = (ROOT_DIR / "cardlang" / "grammar" / "cardlang.lark").read_text()
    production = re.search(r"^primitive_read:.*?(?=\n\S|\n\n)", grammar, re.S | re.M)
    assert production is not None, "the `primitive_read` production is gone"
    text = production.group(0)
    assert "[_IN_KW NAME]" in text, text
    clause = re.search(r"^primitive_reads:.*$", grammar, re.M)
    assert clause is not None and "_IN_KW" not in clause.group(0)


@pytest.mark.parametrize(
    "clause,scoped",
    [
        ("hand[p], trump_suit", ()),
        ("hand[p], trump_suit in outer", ("trump_suit",)),
        ("hand[p], seen[p] in outer, trump_suit in outer", ("seen", "trump_suit")),
        ("hand[p], trump_suit in outer, meld[p]", ("trump_suit",)),
    ],
    ids=["bare-untailed", "bare-tailed", "binder-tailed", "mixed-order"],
)
def test_the_four_accepted_spellings_play(clause: str, scoped: tuple[str, ...]) -> None:
    """The 2x2 of {bare, `[binder]`} x {no tail, `in P`}, every combination the
    grammar accepts, each PLAYED. The binder-and-tail cell (`seen[p] in outer`)
    is the one Hoyle's derivation found no corpus witness for and the
    Architect's found live in stud/holdem; pinochle settles neither, so it is
    carried here as a played synthetic — an over-declared read the
    implementation ignores, which is how
    `test_an_indexed_state_read_narrows_to_the_instance` already carries the
    untailed twin of this cell."""
    outer_state = "trump_suit : Suit? = spades"
    if any(s == "seen" for s in scoped):
        outer_state += "  seen[player] : Integer = 0"
    entry = f"pinochle_meld_value(p : Player) : Integer reads {clause}"
    source = _probe(
        block=entry,
        outer_state=outer_state,
        # An untailed `trump_suit` must denote a GAME-level declaration.
        game_state=("  trump_suit : Suit? = spades" if not scoped else ""),
    )
    if not scoped:
        source = source.replace("    state { trump_suit : Suit? = spades }\n", "")
    game = _checks(source)
    assert game.primitives is not None
    read_phases = {
        r.name: r.phase for d in game.primitives.decls for r in d.reads
    }
    assert {k for k, v in read_phases.items() if v is not None} == set(scoped)
    _plays(source)


@pytest.mark.parametrize(
    "clause,fragment",
    [
        ("trump_suit in outer[p]", "binder rides the variable"),
        ("trump_suit in", None),
        ("trump_suit in outer in outer", None),
        ("trump_suit in 3", None),
    ],
    ids=["transposed-binder", "dangling-in", "doubled-tail", "non-name-tail"],
)
def test_the_malformed_tails_are_refused(clause: str, fragment: str | None) -> None:
    """The spellings the grammar must NOT accept. The transposed binder is the
    one transposition a designer plausibly writes, so it earns a
    reject-with-replacement twin naming the fix; the other three are
    ill-formed in a way no replacement can guess, and fail as parse errors.

    red under: delete the reject alternative from the `primitive_read`
    production — the transposed cell then parses as something else or dies
    without its replacement."""
    entry = f"pinochle_meld_value(p : Player) : Integer reads hand[p], {clause}"
    message = _refused(_probe(block=entry))
    if fragment is not None:
        assert fragment in message, message
        assert "trump_suit[p] in outer" in message, message


# --- axis: REFERENT MEMBERSHIP — what `X in P` finds -------------------------
#
# The untailed membership product over the four namespaces is
# tests/test_primitives_block.py's. What the tail adds is a NAMED phase, which
# makes two relations the flat product cannot see decisive: whether the named
# phase is the one that declares the name, and whether a STRICT DESCENDANT of
# it re-declares the name (where the runtime's innermost-frame walk would
# return the descendant's value while the declaration names the ancestor's).

_MEMBERSHIP_CELLS: dict[str, tuple[str, ...] | None] = {
    # vector -> the fragments a refusal must carry, or None for accept.
    "named-phase-declares-it": None,
    "two-phases-declare-it": None,
    "also-game-level": ("trump_suit", "game"),
    "also-a-zone": ("trump_suit", "zone"),
    "other-phase-declares-it": ("trump_suit", "later"),
    "declared-nowhere": ("trump_suit", "declares no state"),
    "no-such-phase": ("nowhere", "no phase"),
    "phase-names-a-zone": ("hand", "zone"),
    "phase-names-a-state-variable": ("meld", "state variable"),
    "game-level-only-name-wearing-a-tail": ("meld", "drop the tail"),
    "descendant-redeclares-it": ("trump_suit", "inner"),
}


def _membership_source(cell: str) -> str:
    """One probe per membership vector. Each varies exactly one thing from the
    accept baseline, so a refusal cell IS its accept twin plus the offending
    declaration."""
    match cell:
        case "named-phase-declares-it":
            return _probe()
        case "two-phases-declare-it":
            # Sibling phases may legally declare the same name (uniqueness is
            # per declaration list), which is precisely why the tail is
            # explicit rather than inferred.
            return _probe(
                after_outer="  phase later {\n"
                "    state { trump_suit : Suit? = hearts }\n"
                "    meld[0] := meld[0]\n"
                "  }\n"
            )
        case "also-game-level":
            return _probe(game_state="  trump_suit : Suit? = hearts")
        case "also-a-zone":
            return _probe(zones="  trump_suit : Discard")
        case "other-phase-declares-it":
            # The near miss: `outer` is a real phase and the tail names it, but
            # `later` is what declares the name. The diagnostic must say so.
            return _probe(
                outer_state="",
                outer_body="    meld[0] := meld[0]\n",
                after_outer="  phase later {\n"
                "    state { trump_suit : Suit? = hearts }\n"
                "    meld[0] := meld[0]\n"
                "  }\n",
            )
        case "declared-nowhere":
            return _probe(outer_state="", outer_body="    meld[0] := meld[0]\n")
        case "no-such-phase":
            return _probe(block=_ENTRY.replace("in outer", "in nowhere"))
        case "phase-names-a-zone":
            return _probe(block=_ENTRY.replace("in outer", "in hand"))
        case "phase-names-a-state-variable":
            return _probe(block=_ENTRY.replace("in outer", "in meld"))
        case "game-level-only-name-wearing-a-tail":
            return _probe(
                block="pinochle_meld_value(p : Player) : Integer "
                "reads hand[p], trump_suit, meld[p] in outer"
            )
        case "descendant-redeclares-it":
            return _probe(
                outer_body=_DEAL,
                outer_items="    phase inner {\n"
                "      state { trump_suit : Suit? = hearts }\n"
                + _CALL
                + "    }\n",
            )
    raise AssertionError(f"no source for membership cell {cell!r}")


@pytest.mark.parametrize("cell", sorted(_MEMBERSHIP_CELLS), ids=lambda c: c)
def test_the_referent_membership_product(cell: str) -> None:
    """One cell of the referent product. An accepted vector PLAYS; a refused
    one names the read and carries the fragment of the arm that owns it —
    including, for a tail that names something which is not a phase, the word
    for what it IS, so the diagnostic does not mislead."""
    expected = _MEMBERSHIP_CELLS[cell]
    source = _membership_source(cell)
    if expected is None:
        _plays(source)
        return
    message = _refused(source)
    for fragment in expected:
        assert fragment in message, message


def test_a_shadowed_pair_with_a_tail_does_not_say_cannot_say_which() -> None:
    """The shadowed pair stays refused WITH a tail — `in` does not lift it, and
    the reason changes. Untailed, the declaration cannot say which of the two
    it means; tailed, it does say, and the refusal stands because the
    game-level variable would then be unreadable by any declaration with
    nothing saying so. A message still claiming the declaration cannot say
    which would be false about the text in front of the designer."""
    message = _refused(_membership_source("also-game-level"))
    assert "cannot say which" not in message, message


def test_the_descendant_predicate_is_what_keeps_the_innermost_walk_correct(
) -> None:
    """The fourth collision predicate's reason, stated as its accept twin: the
    SAME game with the descendant's re-declaration removed plays, and the
    scoped read resolves to the declaring phase's value. Without the
    predicate, the innermost-frame walk would return the descendant's value at
    a call inside it — a wrong answer with no failure anywhere."""
    twin = _probe(
        outer_body=_DEAL,
        outer_items="    phase inner {\n" + _CALL + "    }\n",
    )
    _plays(twin)


def test_the_phase_walk_carries_ancestry() -> None:
    """The leaf's phase attribution is name-keyed and cannot see ancestry, so
    the fourth predicate needs a PATH-aware walk. It is pinned against the
    engine-wide walk the way the name-keyed one already is — equal on the flat
    name set, and additionally answering the ancestor question the flat set
    cannot.

    red under: drop the nesting recursion from
    `primitives_block._phase_state_paths`."""
    from cardlang.primitives_block import (
        _phase_state_declarations,
        _phase_state_paths,
    )

    game = _checks(
        _probe(
            block=None,
            outer_body=_DEAL,
            outer_items="    phase inner {\n"
            "      state { deep : Integer = 0 }\n"
            "      meld[0] := deep\n"
            "    }\n",
            winner="  winner: highest meld\n",
        )
    )
    paths = _phase_state_paths(game)
    assert {(p[-1], name) for p, name in paths} == set(_phase_state_declarations(game))
    assert (("outer",), "trump_suit") in paths
    assert (("outer", "inner"), "deep") in paths


# --- axis: CLAUSE COMPOSITION ------------------------------------------------


def test_a_clause_may_mix_game_level_and_scoped_reads() -> None:
    """Canasta's shape, and the witness that forces a per-READ tail rather than
    a clause-wide one: a game-level name beside a phase-scoped one in the same
    clause."""
    _plays(
        _probe(
            block="pinochle_meld_value(p : Player) : Integer "
            "reads hand[p], meld[p], trump_suit in outer"
        )
    )


def test_two_phases_in_one_clause_are_refused() -> None:
    """A wall. One entry has ONE containment region, because the entry is
    callable only where its phase runs and two phases' extents are not one
    place; the refusal names both phases and the two fixes."""
    source = _probe(
        block="pinochle_meld_value(p : Player) : Integer "
        "reads hand[p], trump_suit in outer, extra in later",
        after_outer="  phase later {\n"
        "    state { extra : Integer = 0 }\n"
        "    meld[0] := meld[0]\n"
        "  }\n",
    )
    message = _refused(source)
    assert "outer" in message and "later" in message, message


def test_two_phases_in_one_clause_has_its_accept_twin() -> None:
    """The same game with the second phase's read dropped — so the arm above is
    proven to discriminate rather than merely to fire."""
    _plays(
        _probe(
            block="pinochle_meld_value(p : Player) : Integer "
            "reads hand[p], trump_suit in outer",
            after_outer="  phase later {\n"
            "    state { extra : Integer = 0 }\n"
            "    meld[0] := extra\n"
            "  }\n",
        )
    )


def test_a_scoped_read_on_a_pure_entry_is_still_the_pure_guards() -> None:
    """The existing pure-reads guard OWNS a `reads` clause on an implementation
    that never receives the bundle, and the tail does not change whose it is —
    cited rather than re-covered, and probed to prove the tail did not move
    the arm."""
    source = _probe(
        block="skat_next_bid(x : Integer) : Integer reads trump_suit in outer",
        outer_body=_DEAL + "    meld[0] := skat_next_bid(0)\n",
    )
    message = _refused(source)
    assert "pure" in message, message


def test_a_name_written_bare_and_scoped_is_the_repeat_guards() -> None:
    """A clause is a SET keyed by NAME, so `X, X in P` is a repeat whichever
    tail each copy wears — the repeat guard keys by name and must still refuse,
    rather than reading the two spellings as two declarations."""
    source = _probe(
        block="pinochle_meld_value(p : Player) : Integer "
        "reads hand[p], trump_suit, trump_suit in outer",
        game_state="  trump_suit : Suit? = spades",
    )
    message = _refused(source)
    assert "trump_suit" in message, message
    assert "once" in message or "repeat" in message, message


# --- axis: CONTAINMENT POSITION ----------------------------------------------
#
# Where a `Call` to a scoped entry may sit. The taxonomy is TOTAL over the
# containers the language has, pinned in two directions — the `n.Game` field
# a container hangs off, and the `PhaseItem` union inside a phase — so a new
# field or item forces a decision rather than defaulting to "allowed", which
# is the direction a missing arm would fail in.


def test_the_containment_taxonomy_is_total_over_the_game_fields() -> None:
    """Every field of `n.Game` is classified by the containment analysis: the
    three that hold judged containers (phases, move types, procedures) and
    every other, whose contents run outside any phase and are therefore
    refused.

    red under: add a field to `n.Game` without classifying it."""
    from cardlang.resolve import _CONTAINMENT_BY_GAME_FIELD

    fields = {f.name for f in dataclasses.fields(n.Game)} - {"span"}
    assert set(_CONTAINMENT_BY_GAME_FIELD) == fields, sorted(
        set(_CONTAINMENT_BY_GAME_FIELD) ^ fields
    )
    assert {
        f for f, arm in _CONTAINMENT_BY_GAME_FIELD.items() if arm != "refused"
    } == {"phases", "move_types", "procedures"}


def test_the_containment_taxonomy_is_total_over_the_phase_items() -> None:
    """Inside a phase every item of the `PhaseItem` union is in the subtree —
    the whole extent of the `Phase` node, hooks and nested phases included —
    with exactly one exception, whose Owner is cited rather than re-covered:
    a phase's own `state { }` defaults cannot hold a `Call` at all
    (`_check_state_default_scope`'s Call ban).

    red under: add a member to `PhaseItem` without deciding it."""
    from cardlang.resolve import _SUBTREE_PHASE_ITEMS

    members = {m.strip() for m in str(n.PhaseItem).split("|")}
    assert set(_SUBTREE_PHASE_ITEMS) == members, sorted(
        set(_SUBTREE_PHASE_ITEMS) ^ members
    )
    assert _SUBTREE_PHASE_ITEMS["StateBlock"] == "owned by _check_state_default_scope"


_CONTAINMENT_CELLS: dict[str, tuple[str, ...] | None] = {
    "declaring-phase-body": None,
    "descendant-phase": None,
    "declaring-phase-qualifier": None,
    "sibling-phase": ("outer", "pinochle_meld_value"),
    "ancestor-phase": ("outer", "pinochle_meld_value"),
    "function-body": ("outer", "pinochle_meld_value"),
    "rule-applies-when": ("outer", "pinochle_meld_value"),
    "loser-expression": ("outer", "pinochle_meld_value"),
    "move-type-offered-inside": None,
    "move-type-offered-outside": ("note", "outer"),
    "move-type-offered-nowhere": ("note", "offers"),
    "procedure-run-inside": None,
    "procedure-run-outside": ("bump", "outer"),
    "procedure-run-both-sides": ("bump", "outer"),
}

# Definitions are TOP-LEVEL forms, not game items — so each rides the `top`
# slot, exactly as the corpus writes them.
_NOTE = (
    "move_type note {\n"
    "  when: pinochle_meld_value(0) >= 0\n"
    "  effect { meld[0] := meld[0] }\n"
    "}\n"
)
_BUMP = "procedure bump() {\n" + _CALL + "}\n"


def _containment_source(cell: str) -> str:
    match cell:
        case "declaring-phase-body":
            return _probe()
        case "descendant-phase":
            return _probe(
                outer_body=_DEAL,
                outer_items="    phase inner {\n" + _CALL + "    }\n",
            )
        case "declaring-phase-qualifier":
            return _NESTED_HOOKS_FIXTURE
        case "sibling-phase":
            return _probe(
                outer_body=_DEAL,
                after_outer="  phase later {\n" + _CALL + "  }\n",
            )
        case "ancestor-phase":
            # `outer` nested inside `top`, the call in `top` after it.
            return _probe(
                block=_ENTRY,
                outer_body=_DEAL,
                outer_items="",
            ).replace(
                "  phase outer {\n",
                "  phase top {\n    phase outer {\n",
            ).replace(
                "  }\n  winner:", "    }\n" + _CALL + "  }\n  winner:"
            )
        case "function-body":
            return _probe(
                top="function meld_of(q : Player) = pinochle_meld_value(q)\n",
                outer_body=_DEAL + "    for each player p: meld[p] := meld_of(p)\n",
            )
        case "rule-applies-when":
            return _probe(
                top="rule r {\n"
                "  constrains: play_to_trick\n"
                "  applies_when: pinochle_meld_value(0) >= 0\n"
                "  demands: cards in hand where true\n"
                "}\n",
                outer_body=_DEAL,
            )
        case "loser-expression":
            return _probe(
                outer_body=_DEAL,
                winner="  loser: the player where pinochle_meld_value(player) >= 0\n",
            )
        case "move-type-offered-inside":
            return _probe(
                top=_NOTE,
                outer_body=_DEAL + "    offer to 0 one of [note]\n",
            )
        case "move-type-offered-outside":
            return _probe(
                top=_NOTE,
                outer_body=_DEAL + "    offer to 0 one of [note]\n",
                after_outer="  phase later {\n    offer to 1 one of [note]\n  }\n",
            )
        case "move-type-offered-nowhere":
            return _probe(top=_NOTE, outer_body=_DEAL)
        case "procedure-run-inside":
            return _probe(top=_BUMP, outer_body=_DEAL + "    run bump()\n")
        case "procedure-run-outside":
            return _probe(
                top=_BUMP,
                outer_body=_DEAL,
                after_outer="  phase later {\n    run bump()\n  }\n",
            )
        case "procedure-run-both-sides":
            return _probe(
                top=_BUMP,
                outer_body=_DEAL + "    run bump()\n",
                after_outer="  phase later {\n    run bump()\n  }\n",
            )
    raise AssertionError(f"no source for containment cell {cell!r}")


@pytest.mark.parametrize("cell", sorted(_CONTAINMENT_CELLS), ids=lambda c: c)
def test_the_containment_position_taxonomy(cell: str) -> None:
    """One cell of the position taxonomy. An admitted position PLAYS — the
    scoped read materializes from a frame that is genuinely standing — and a
    refused one names the entry and the phase whose extent the call left."""
    expected = _CONTAINMENT_CELLS[cell]
    source = _containment_source(cell)
    if expected is None:
        _plays(source)
        return
    message = _refused(source)
    for fragment in expected:
        assert fragment in message, message


def test_an_offer_outside_the_subtree_points_at_the_offer() -> None:
    """P7: the addressee of a leaked move type is whoever wrote the offending
    OFFER, not whoever wrote the entry — so the span is the offer's, and one
    diagnostic is emitted per offending site rather than one for the move
    type."""
    with pytest.raises(DiagnosticError) as excinfo:
        _checks(_containment_source("move-type-offered-outside"))
    span = excinfo.value.diagnostic.span
    text = _containment_source("move-type-offered-outside").splitlines()
    assert span is not None
    assert "offer to 1" in text[span.line - 1], text[span.line - 1]


# --- the offering surface, derived -------------------------------------------


def test_the_offering_surface_is_derived_and_classified_total() -> None:
    """Which reference slots NAME a move type is read off resolve's own
    registry, and every one of them is classified offering or non-offering in
    one table pinned total against those candidates — so an eighth
    move-type-naming slot arrives unclassified and reddens here rather than
    silently widening or narrowing the containment relation.

    red under: add a `move_type`-namespaced slot to `_REFERENCE_SLOTS` without
    classifying it."""
    from cardlang.resolve import _MOVE_TYPE_SLOT_OFFERS, _REFERENCE_SLOTS

    candidates = {
        slot
        for slot, ns in _REFERENCE_SLOTS.items()
        if ns in ("move_type", "kernel_move_type")
    }
    assert set(_MOVE_TYPE_SLOT_OFFERS) == candidates, sorted(
        {f"{c.__name__}.{f}" for c, f in set(_MOVE_TYPE_SLOT_OFFERS) ^ candidates}
    )
    offering = {s for s, offers in _MOVE_TYPE_SLOT_OFFERS.items() if offers}
    assert {c.__name__ + "." + f for c, f in offering} == {
        "Offer.offering",
        "AuctionRound.offering",
        "TrickRound.move_type",
        "ClimbRound.move_type",
        "LegalMoves.move_types",
    }


def test_offer_edges_match_by_name_across_both_move_type_namespaces() -> None:
    """The two move-type namespaces overlap in the corpus — pinochle's
    `declare_trump_suit` is kernel-listed AND game-defined — so an edge
    collected by slot NAMESPACE would miss the `legal_moves:` mention of a
    game's own move type. Edges match by name across both."""
    from cardlang.pipeline import check_source

    game = check_source(ROOT_DIR / "docs" / "games" / "pinochle.cardlang")
    defined = {m.name for m in game.move_types}
    kernel_mentions = {
        name
        for nd in _walk_all(game)
        if isinstance(nd, n.LegalMoves)
        for name in nd.move_types
    }
    assert "declare_trump_suit" in defined & kernel_mentions


def _walk_all(node: object) -> list[object]:
    from cardlang.resolve import _walk

    return list(_walk(node))


# --- the runtime premise the guard leans on ----------------------------------


def test_the_move_type_index_readers_are_the_pinned_census() -> None:
    """The containment guard is sound only if a game move type's body executes
    inside an offering site's dynamic extent and nowhere else. No static pass
    can see that; what prices it is this census of the runtime sites that
    reach a move-type definition BY NAME, read the two-readers way — the pin
    reads the consumer sites, not the guard's own output, so a new execution
    channel reddens here rather than making the guard silently unsound.

    Two channels, four sites: the offer interpreter (`runtime/execute.py`) and
    the auction form (`runtime/mechanics.py`).

    red under: add a `move_type_index[` read anywhere else under
    `cardlang/runtime/`."""
    hits: dict[str, int] = {}
    for path in (ROOT_DIR / "cardlang" / "runtime").rglob("*.py"):
        count = len(re.findall(r"move_type_index\[", path.read_text()))
        if count:
            hits[path.name] = count
    assert hits == {"execute.py": 2, "mechanics.py": 2}, hits


# --- the three standing collision arms, with a tail present ------------------


@pytest.mark.parametrize(
    "cell",
    ["also-game-level", "also-a-zone"],
    ids=["shadowed-pair", "phase-and-zone"],
)
def test_the_standing_collision_arms_still_speak_with_a_tail(cell: str) -> None:
    """The new surface must not lift a standing refusal silently. Each arm is
    re-probed with the tail present; the legacy regime (no block, no tail) is
    untouched by construction, since neither exists there."""
    message = _refused(_membership_source(cell))
    assert "trump_suit" in message, message


def test_the_untailed_phase_local_message_teaches_the_tail() -> None:
    """The phase-local arm's message is living spec, and one third of it just
    became false: a phase-declared name IS readable by a declaration now. The
    message gains the tail as a fix and names the declaring phase, so a
    designer meeting it is told the sentence to write."""
    source = _probe(
        block="pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit"
    )
    message = _refused(source)
    assert "trump_suit in outer" in message, message


def test_the_phase_and_zone_parenthetical_no_longer_claims_unreadability() -> None:
    """The phase-x-zone arm's parenthetical asserted that a phase-local
    variable is unreadable by a declaration either way. That sentence is false
    the moment the tail lands, so it rewrites in the same change."""
    message = _refused(_membership_source("also-a-zone"))
    assert "unreadable by a declaration either way" not in message, message


# --- the library axis, off the grammar ---------------------------------------


def test_no_library_can_declare_a_phase_for_a_tail_to_name() -> None:
    """The `in` slot resolves against the game's own phase tree, which is the
    only phase tree there is: `?library_item` admits no phase production, so a
    library-declared phase is unconstructible rather than merely unwitnessed.
    Stated off the grammar so the day a library may declare one, this reddens
    rather than the gap going unnoticed.

    red under: add `phase` to `?library_item`."""
    grammar = (ROOT_DIR / "cardlang" / "grammar" / "cardlang.lark").read_text()
    body = re.search(r"\?library_item:(.*?)\n\n", grammar, re.S)
    assert body is not None
    alternatives = {a.strip().lstrip("| ") for a in body.group(1).split("\n")}
    assert "phase" not in alternatives, sorted(alternatives)


def test_library_provided_state_is_game_level_so_a_tail_on_it_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A library provides STATE, and provided state splices into the game's own
    `state { }` before the block is checked — so it is game-level, and a tail
    on it hits the game-level refusal. Which wall answers is stated off the
    splice rather than assumed."""
    from cardlang.parse import parse_library
    from tests.test_family_libraries import _patch_libraries

    _patch_libraries(
        monkeypatch,
        {
            "provider": parse_library(
                "library provider { state { provided : Integer = 0 } }",
                "docs/libraries/provider.cardlang",
            )
        },
    )
    source = _probe(
        block="pinochle_meld_value(p : Player) : Integer "
        "reads hand[p], trump_suit in outer, provided in outer"
    ).replace("game Probe {\n", "game Probe {\n  uses provider\n", 1)
    message = _refused(source)
    assert "provided" in message, message
    assert "drop the tail" in message, message


# --- the IR row and the coordinated tables -----------------------------------


def test_the_ir_read_row_carries_the_phase_always() -> None:
    """The emitted row gains `phase`, ALWAYS present and null when absent — the
    `binder` key's exact shape. An IGNORED new AST field would drop out of the
    IR silently, which is the whole reason the key is emitted rather than
    conditionally added.

    The schema pin (`tests/test_ir_schema_version.py`) does NOT catch this
    addition, because `key:phase` is already emitted by other nodes and its
    scrape is over key NAMES — so this cell is the loud channel for the row's
    shape, and pinochle's `.ir.json` golden is the second."""
    import json

    from cardlang.ir import emit

    game = _checks(
        _probe(
            block="pinochle_meld_value(p : Player) : Integer "
            "reads hand[p], trump_suit in outer"
        )
    )
    # Round-tripped through JSON, which is the form a consumer reads and the
    # form the goldens hold — and which types as plain data rather than as the
    # emitter's own recursive union.
    rows = json.loads(json.dumps(emit(game)))["primitives"]["entries"][0]["reads"]
    assert [r["name"] for r in rows] == ["hand", "trump_suit"]
    assert [r["phase"] for r in rows] == [None, "outer"]
    assert all("phase" in r for r in rows)


def test_the_phase_tail_is_a_registered_reference_slot() -> None:
    """The tail is a name held as a plain string, invisible to any pass built
    on `NameRef` — exactly what the reference-slot registry exists to record.
    Registered beside `ContinueTo.phase`, so a future phase-renaming transform
    learns of it from the registry rather than from an author remembering.

    red under: delete the row."""
    from cardlang.resolve import _REFERENCE_SLOTS

    assert _REFERENCE_SLOTS[(n.PrimitiveRead, "phase")] == "phase"


def test_the_twin_block_facts_carry_the_tail() -> None:
    """The `.md` fence and the `.cardlang` are held in lockstep by a fact
    tuple; a tail present in one and absent (or different) in the other checks
    clean on both sides, so the tuple must carry it or the drift is invisible.

    red under: drop `r.phase` from `_block_facts`' tuple."""
    from tests.test_typecheck_corpus import _block_facts

    scoped = _checks(
        _probe(
            block="pinochle_meld_value(p : Player) : Integer "
            "reads hand[p], trump_suit in outer"
        )
    )
    unscoped = _checks(
        _probe(
            block="pinochle_meld_value(p : Player) : Integer "
            "reads hand[p], trump_suit",
            game_state="  trump_suit : Suit? = spades",
            outer_state="",
        )
    )
    assert _block_facts(scoped) != _block_facts(unscoped)


# --- the nested fixture: the three positions no corpus game reaches ----------
#
# The declaring phase's own qualifier, `before_each` and `after_each` all run
# strictly between `_declare_state` and `pop_frame` (runtime/driver.run_phase),
# so the frame stands and the positions are ADMITTED. No corpus game calls a
# scoped entry from any of them, so one synthetic fixture carries all three —
# and it proves WHICH position each call came from rather than asserting that
# the game played, by giving each position a distinct value of a game-level
# `stage` the entry also reads.

_NESTED_HOOKS_FIXTURE = (
    "game Probe {\n"
    "  players: 2\n"
    "  max_length: 100\n"
    "  cards: pinochle48\n"
    "  ranking: A 10 K Q J 9\n"
    "  primitives {\n"
    "    pinochle_meld_value(p : Player) : Integer\n"
    "        reads hand[p], stage, trump_suit in outer\n"
    "  }\n"
    "  zones { deck : Deck  hand[player] : Hand<player> }\n"
    "  state { meld[player] : Integer = 0  stage : Integer = 0 }\n"
    "  phase outer repeat until (pinochle_meld_value(0) >= 0 and done) {\n"
    "    state { trump_suit : Suit? = spades  done : Boolean = false }\n"
    "    before_each { stage := 1  meld[0] := pinochle_meld_value(0) }\n"
    "    after_each  { stage := 3  meld[1] := pinochle_meld_value(1) }\n"
    "    stage := 2\n"
    "    shuffle deck\n"
    "    deal 12 cards from deck to each hand\n"
    "    meld[0] := pinochle_meld_value(0)\n"
    "    done := true\n"
    "  }\n"
    "  winner: highest meld\n"
    "}\n"
)


def test_the_admitted_hook_positions_are_reached_by_a_playout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The frame-liveness obligation the info-set bound names, discharged by
    execution rather than by reading `run_phase`: a playout that reaches a
    scoped call from the qualifier, from `before_each` and from `after_each`,
    each identified by the `stage` value only that position can present.

    stage 0 is reachable only by the qualifier (its first evaluation runs
    before any statement), 1 only by `before_each`, 2 by the body, 3 by
    `after_each` and by the qualifier's later evaluations."""
    from cardlang.runtime import pinochle as pinochle_mod

    seen: list[int] = []
    real = pinochle_mod.pinochle_meld_value

    def spy(facts: object, gr: object, player: object) -> int:
        seen.append(int(gr.state["stage"]))  # type: ignore[attr-defined]
        return real(facts, gr, player)  # type: ignore[arg-type]

    monkeypatch.setattr(pinochle_mod, "pinochle_meld_value", spy)
    play_game(_checks(_NESTED_HOOKS_FIXTURE), random.Random(0))
    assert 0 in seen, seen  # the qualifier
    assert 1 in seen, seen  # before_each
    assert 2 in seen, seen  # the body
    assert 3 in seen, seen  # after_each


# --- anti-vacuity ------------------------------------------------------------


def test_the_grid_is_not_empty() -> None:
    """The parametrized axes above are derived from registries and from the
    grammar; a read gone wrong would silently shrink them to nothing."""
    assert len(_MEMBERSHIP_CELLS) >= 11
    assert len(_CONTAINMENT_CELLS) >= 14
    assert any(v is None for v in _CONTAINMENT_CELLS.values())
    assert any(v is not None for v in _CONTAINMENT_CELLS.values())
