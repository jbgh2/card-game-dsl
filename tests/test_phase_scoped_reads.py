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
            phase's subtree, or at a `run` site inside it, or in a game move
            type every POSITION of which sits inside it — so the runtime's
            innermost-frame walk returns the declared phase's value by
            construction rather than by luck. A position is where an offer
            HAPPENS, never where its text sits: an offer written in a procedure
            body happens at each `run` of that procedure, because expansion is
            by value. Claim (3) is bounded by which offers this analysis can
            position at all — an offer made from inside another move type's
            body — or from a `define`'s — is REFUSED, not judged, and the
            wall says so rather than speaking about where state stands.
domain:     the tail's own surface, crossed: SPELLING x {bare, `[binder]`} x
            {no tail, `in P`} (four accepted combinations, all implemented)
            plus the malformed spellings the grammar must refuse loud;
            REFERENT MEMBERSHIP — where the tailed name is declared, over the
            same four namespaces the untailed product uses
            (tests/test_primitives_block.py owns that product; this module
            crosses it with the tail) plus the two ancestry relations a flat
            membership set cannot see, "declared by a sibling phase only" and
            "re-declared by a STRICT DESCENDANT of the named phase";
            CLAUSE COMPOSITION x {game-level names beside scoped ones, a
            scoped read on a PURE entry, one name written both bare and
            scoped, one name written under two tails, a binder beside a second
            phase's tail, one misspelled tail beside a good one}; PHASE-SET
            SHAPE — every subset of at most three phases of an authored
            five-phase fixture, classified by prefix order into the shape
            classes the law distinguishes and crossed with the call sitting in
            the innermost named phase; the nested pair crossed with the whole
            CONTAINMENT POSITION taxonomy below, where the enclosing phase's
            own body and hooks are outside the region while its frame stands; CONTAINMENT POSITION — every
            syntactic position a `Call` to a declared Primitive can occupy,
            classified by the `n.Game` field its container hangs off and by
            the `PhaseItem` union inside a phase, both pinned TOTAL so a new
            field or item forces a decision rather than defaulting to
            "allowed"; the OFFERING SURFACE — the move-type-naming slots of
            resolve's `_REFERENCE_SLOTS`, classified offering / non-offering
            in one table pinned total against the derived candidates, so a
            slot added there arrives unclassified and reddens; the OFFERING
            CONTAINER, which is what decides where an offer's position IS —
            the statement-holding productions of the grammar, derived by
            subtracting the forms reachable from `?statement` and
            `?phase_item`: a phase, a procedure body (crossed with that
            procedure's `run` sites: inside, both sides, none), another move
            type's body, a `define`'s body; and the three
            standing collision arms plus the repeat guard, each re-probed WITH
            a tail present, and again with TWO tails present, so neither the
            tail nor the nest can lift them silently.
registry:   `cardlang/grammar/cardlang.lark` (the `primitive_read`
            production and its reject twin, read as text by the spelling
            axis); `cardlang.ast.nodes.Game`'s field set and
            `cardlang.ast.nodes.PhaseItem`'s union (the containment
            taxonomy's totality); `cardlang.resolve._REFERENCE_SLOTS` (the
            offering-surface candidates) and
            `cardlang.resolve._MOVE_TYPE_SLOT_OFFERS` (their
            classification); `cardlang/grammar/cardlang.lark`'s
            `statement*`-holding productions (the offering-container
            candidates); `_SHAPE_PHASE_PATHS` below, the AUTHORED phase-path
            table the shape axis derives its subsets and its classes from —
            authored rather than read off `cardlang.primitives_block`'s walk,
            so the
            axis crosses a classification with the law instead of comparing a
            derivation with itself;
            and `cardlang.resolve._UNPOSITIONED_CONTAINERS` (which
            of them yield no position);
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
            Two containment vectors are cited to their Owners rather than
            covered: a procedure NO statement runs is `_check_procedures`'
            never-run refusal (both the call and the offer rows carry its
            message), and a phase's own `state { }` default cannot hold a call
            at all. The plan's grid frame lists `demands:` among the move-type
            offering surfaces; it is a RULE clause, not a move type's, and
            rules are a REFUSED container — the `rule-applies-when` row samples
            them — so there is no move-type `demands:` cell to write.
sampled:    the ACCEPT half's call positions are the ones five corpus games
            carry (seven-card-stud, holdem, pinochle, french-tarot,
            canasta) — the shapes each cell below is built to, read off those
            games rather than invented; which of them declare a block is a
            query (`rg -lF 'primitives {' docs/games/`), never this ledger's
            claim. The positions no corpus game reaches — a phase's own
            qualifier, `before_each` and `after_each` — are carried by one
            synthetic nested fixture whose playout records which position
            each scoped call came from, rather than by a fixture that merely
            resolves. Every REFUSAL cell is synthetic, because the corpus
            correctly holds no violation, and each ships with its accept twin
            (the same game with the offending element removed) so the arm is
            proven discriminating rather than merely loud.
does not prove: a green here says nothing about whether the runtime premise
            the containment guard leans on still holds — that a game move
            type's body executes only inside the dynamic extent of an
            offering site. That premise is a fact about the runtime, not
            about this guard, and `test_the_move_type_index_readers_are_the_
            pinned_census` prices it: it pins the consumer sites, so a new
            execution channel reddens there rather than making this guard
            silently unsound. The asymmetry inside that premise is worth
            stating: of the offering slots, the KERNEL-namespaced ones are
            execution-inert for a game move type's body — the runtime reaches a
            move-type definition by name only at the sites
            `test_the_move_type_index_readers_are_the_pinned_census` pins, and
            `legal_moves:` is not among them — so those edges guard a future
            consumer rather than a live one, and a green over them proves the
            relation is derived, not that it is exercised.
            Nor does a green say a scoped entry is ever
            CALLED: an entry with a scoped read and zero calls passes
            containment vacuously, and what keeps a block naming only names
            the game calls is the 3b recipe's discipline, not this grid.
            And `_SUBTREE_PHASE_ITEMS` records a JUDGMENT the analysis does
            not consult: the subtree is `_walk(phase)`, unconditionally, so a
            future `PhaseItem` that ran outside the push/pop window would be
            admitted while its pin was satisfied by adding a row. The pin
            makes the decision visible; it does not enforce it.
            And a green says nothing about whether a declared read SUFFICES
            for its implementation — that is a fact about Python, proven only
            by a playout (tests/test_primitives_block.py's witness owns it).
walls:      the refusals here are not one kind, and the ledger says which is
            which so a reader can tell an unbuilt feature from a built wall.
            DEFERRALS, each with a tracker record naming the game shape that
            unblocks it: a spelling two declarations answer to — the shadowed
            pair and the phase-and-zone pair alike (issue #516); a scoped call
            in a function, define or
            rule body (issue #518); an offer made from inside another move
            type's body, which the analysis refuses rather than positioning,
            since following it means judging the OFFERING move type's own
            containment up a chain that can cycle — a move type's own body
            and a `define`'s alike (issue #521 — coup's move-type effects hold
            three such offers, and it is the game that decides what the wall
            costs). DESIGNED constraints, recorded at their
            construct rather than filed: a library cannot declare a phase for
            a tail to name (unconstructible off the grammar); a move type
            nothing offers is refused rather than passing containment
            vacuously; a strict descendant re-declaring the name is
            refused rather than resolved by tagging frames at run time; and an
            entry naming phases that do NOT nest is refused rather than
            deferred, because a phase's frame is popped when the phase ends —
            no position in the game runs both, so nothing anyone could build
            makes such an entry callable. That last premise is a fact about
            the runtime rather than about this guard, so it is pinned
            (`test_a_phases_frame_does_not_outlive_the_phase`) rather than
            argued.

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
written for. Its 17 passes are three kinds, not two: TEN are refusals whose
arm already existed and which the tail must not lift; FOUR are pins born green
by construction, each carrying its reddening mutation in its own docstring
(the grammar production, the `move_type_index` census, the library-phase
absence, the reference-slot row); and THREE are neither — the `bare-untailed`
spelling, which writes no tail at all and so is the legacy sentence this
change must leave undisturbed while the three tailed rows beside it are red,
and the offer-edge and anti-vacuity pins, which now carry reddening mutations
of their own.

Both counts are of the module AS TAKEN, and the module has since grown. Every
cell written against a built guard says so where it sits rather than joining a
number measured before it: the co-report cell below, the offering-container
and `produces:` rows and the never-run row of `_CONTAINMENT_CELLS` (the dict's
own comments carry which was red against what), and the statement-holding
container pin. A cell added after a take says so rather than being absorbed
into a count that predates it.

The NEST law's own two takes (a later change, its own record, counted
separately for the same reason). The cells are the phase-set-shape axis, the
nested position crossing, the two-tail composition rows, the standing arms
re-probed under two tails, and the enclosure register's ancestor/sibling pair.
Command: `.venv/bin/pytest tests/test_phase_scoped_reads.py -q`.

    take 1 (2026-09-04, the cells against the one-phase arm):  53 failed, 76 passed
    take 2 (2026-09-04, that arm lifted alone, nothing else):  30 failed, 99 passed

Take 1's reds are two kinds and no third: every accept cell naming two phases
dies on the one-phase arm, and every refusal cell dies because that arm's text
carries none of the new law's fragments. Its passes include the five singleton
shape cells (one phase is the degenerate chain, accepted before and after), the
ancestor-also-declares accept (one tail), and the born-green pins, each of
which carries its reddening mutation where it sits.

TAKE 2 is the load-bearing one, and it is a measurement of the WINDOW rather
than of a candidate implementation: the refusal arm deleted and nothing else
touched — the containment analysis still skipping every entry that names more
than one phase. The accepts go green, including the three-chain and the inner
phase's own hooks, which is what says the runtime needs no line changed. Of
the 30 reds, 27 are DID NOT RAISE: every outer-side refusal under the nest
(the outer's body before and after the inner, its qualifier and both hooks, a
sibling of the outer, a function body, `loser:`, both leaked-offer shapes,
both leaked-run shapes, the three-chain's middle and outer positions) and
every non-nesting shape cell CHECK CLEAN in that state. That is the
accepted-and-unchecked class, executed — a designer's call refused by nothing
and crashing at playout in the runtime's shadow guard — and it is why these
cells exist before the arm moves rather than after. The other three reds are
owned elsewhere and stay red through take 2: the enclosure register's pair and
the repeat guard's wording, whose owners are `_outside` and the repeat arm.
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
    the fourth predicate needs a PATH-aware walk. What this cell owns is the
    ancestry the flat name set cannot express: a path from a top-level phase
    down to the declarer. That the walk agrees with the engine's own
    (`n.state_blocks`) is next door's —
    tests/test_primitives_block.py's `test_the_phase_carrying_walk_agrees_with_
    the_engines`, over a game of this same nested shape — and asserting it here
    would compare a derivation with itself, since the attribution IS the paths
    with each path's last element taken.

    red under: drop the nesting recursion from
    `primitives_block._phase_state_decls`, the ONE walk the paths derive
    from."""
    from cardlang.primitives_block import _phase_state_paths

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


def test_two_phases_that_do_not_nest_are_refused() -> None:
    """A designed constraint, not a wall. `run_phase` pops a phase's frame when
    the phase ends, so no position in the game runs two phases neither of which
    is inside the other — an entry reading from both could never be called
    anywhere, and "split the entry" is no fix, since the caller would need both
    values in one place that does not exist."""
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
    assert "do not nest" in message, message
    assert "no place in this game runs both" in message, message
    assert "split the entry" not in message, message


def test_two_phases_that_do_not_nest_has_its_accept_twin() -> None:
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


# --- the nested probe: two phases on one ancestor path -----------------------
#
# `outer` is a top-level phase and `inner` sits inside it — cribbage's own
# shape (`hand_sequence` > `play`). The entry names a state variable of each,
# so its region is `inner`'s subtree: the innermost named phase's, which is the
# intersection of the two named subtrees. `deep` is over-declared and the
# implementation ignores it, exactly as the binder-and-tail cell's `seen[p]` is.

_NESTED_ENTRY = (
    "pinochle_meld_value(p : Player) : Integer\n"
    "        reads hand[p], trump_suit in outer, deep in inner"
)

_NDEAL = "    shuffle deck\n    deal 12 cards from deck to each hand\n"


def _call_at(indent: int) -> str:
    return " " * indent + "meld[0] := pinochle_meld_value(0)\n"


def _nested(
    *,
    block: str | None = _NESTED_ENTRY,
    top: str = "",
    game_state: str = "",
    outer_qualifier: str = "",
    outer_state: str = "trump_suit : Suit? = spades",
    outer_items: str = "",
    outer_before: str = "",
    inner_qualifier: str = "",
    inner_state: str = "deep : Integer = 0",
    inner_items: str = "",
    inner_body: str = _call_at(6),
    outer_after: str = "",
    after_outer: str = "",
    winner: str = "  winner: highest meld\n",
) -> str:
    """A probe game with `outer` enclosing `inner`, both declaring state.

    Every slot is a string spliced at one place, as `_probe`'s are, so each
    cell reads as the ONE thing it varies from the accept baseline — a call in
    `inner`'s body."""
    outer_sb = f"    state {{ {outer_state} }}\n" if outer_state else ""
    inner_sb = f"      state {{ {inner_state} }}\n" if inner_state else ""
    return (
        top
        + "game Probe {\n"
        "  players: 2\n"
        "  max_length: 100\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        + ("  primitives { " + block + " }\n" if block is not None else "")
        + "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { meld[player] : Integer = 0" + game_state + " }\n"
        + f"  phase outer {outer_qualifier}{{\n"
        + outer_sb
        + outer_items
        + _NDEAL
        + outer_before
        + f"    phase inner {inner_qualifier}{{\n"
        + inner_sb
        + inner_items
        + inner_body
        + "    }\n"
        + outer_after
        + "  }\n"
        + after_outer
        + winner
        + "}\n"
    )


# --- axis: PHASE-SET SHAPE — which sets of phases one clause may name --------
#
# The phases an entry's `reads` clause names must NEST, one inside the next,
# and the entry is callable only where the innermost of them runs. The shape
# axis is derived from the AUTHORED path table below rather than read off
# `primitives_block`'s walk, so the pin crosses a classification with the
# language's rule instead of comparing a derivation with itself.

_SHAPE_PHASE_PATHS: dict[str, tuple[str, ...]] = {
    "top": ("top",),
    "outer": ("top", "outer"),
    "inner": ("top", "outer", "inner"),
    "later": ("top", "later"),
    "cousin": ("top", "later", "cousin"),
}

# The isomorphism classes the table above realises over its subsets of at most
# three phases. AUTHORED from the shapes the law distinguishes, and pinned
# equal to what the derivation finds, which is what keeps the list checkable.
# The skip-level class carries its GAP so a deeper fixture lands as a class
# with no row rather than joining this one silently.
_SHAPE_CLASSES: frozenset[str] = frozenset(
    {
        "singleton",
        "adjacent pair",
        "top-level-outer pair",
        "skip-level pair (gap 2)",
        "three-chain",
        "sibling pair",
        "cousin pair",
        "mixed triple",
    }
)


def _shape_class(members: tuple[str, ...]) -> tuple[bool, str]:
    """(do these phases lie on one ancestor path, which shape class they are).

    Prefix order over the authored paths IS the nesting question: a set nests
    exactly when, sorted by depth, each path is a prefix of the next."""
    paths = sorted((_SHAPE_PHASE_PATHS[m] for m in members), key=len)
    chain = all(
        paths[i] == paths[i + 1][: len(paths[i])] for i in range(len(paths) - 1)
    )
    if not chain:
        if len(paths) > 2:
            return False, "mixed triple"
        first, second = paths
        return False, ("sibling pair" if first[:-1] == second[:-1] else "cousin pair")
    if len(paths) == 1:
        return True, "singleton"
    if len(paths) == 3:
        return True, "three-chain"
    first, second = paths
    gap = len(second) - len(first)
    if gap > 1:
        return True, f"skip-level pair (gap {gap})"
    return True, ("top-level-outer pair" if len(first) == 1 else "adjacent pair")


def _shape_subsets() -> list[tuple[str, ...]]:
    """Every subset of at most three of the fixture's phases, ordered so the
    parametrized ids are stable."""
    import itertools

    names = sorted(_SHAPE_PHASE_PATHS)
    return [
        combo
        for size in (1, 2, 3)
        for combo in itertools.combinations(names, size)
    ]


def _shape_source(members: tuple[str, ...]) -> str:
    """The fixture with one read tailed to each named phase, and the call in the
    innermost of them — or, for a set that does not nest, in `top`, which the
    entry-grain arm refuses whatever position the call takes."""
    nests, _ = _shape_class(members)
    innermost = (
        max(members, key=lambda m: len(_SHAPE_PHASE_PATHS[m])) if nests else "top"
    )
    tails = "".join(f", s_{m} in {m}" for m in sorted(members))

    def body(phase: str, indent: int) -> str:
        own = " " * indent + f"s_{phase} := s_{phase}\n"
        return own + (_call_at(indent) if phase == innermost else "")

    def state(phase: str, indent: int) -> str:
        return " " * indent + f"state {{ s_{phase} : Integer = 0 }}\n"

    return (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 100\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer\n"
        f"      reads hand[p], trump_suit{tails} }}\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { meld[player] : Integer = 0  trump_suit : Suit? = spades }\n"
        "  phase top {\n"
        + state("top", 4)
        + "    shuffle deck\n"
        "    deal 12 cards from deck to each hand\n"
        + body("top", 4)
        + "    phase outer {\n"
        + state("outer", 6)
        + body("outer", 6)
        + "      phase inner {\n"
        + state("inner", 8)
        + body("inner", 8)
        + "      }\n"
        "    }\n"
        "    phase later {\n"
        + state("later", 6)
        + body("later", 6)
        + "      phase cousin {\n"
        + state("cousin", 8)
        + body("cousin", 8)
        + "      }\n"
        "    }\n"
        "  }\n"
        "  winner: highest meld\n"
        "}\n"
    )


@pytest.mark.parametrize(
    "members", _shape_subsets(), ids=lambda m: "+".join(m)
)
def test_the_phase_set_shape_axis(members: tuple[str, ...]) -> None:
    """One cell per phase set the fixture can name. A set that nests is
    ACCEPTED and PLAYS with the call in its innermost; a set that does not is
    refused at entry grain with the designed constraint's reason, and the
    containment analysis says nothing about it — a call site reported beside it
    would make one defect look like two."""
    source = _shape_source(members)
    nests, _ = _shape_class(members)
    if nests:
        _plays(source)
        return
    message = _refused(source)
    assert "do not nest" in message, message
    assert "callable only where" not in message, message


def test_the_shape_classes_the_fixture_realises_are_the_authored_rows() -> None:
    """The authored class list, held equal to what the fixture's own subsets
    realise — the derivation that keeps the list from going stale silently, and
    the reason the shape axis is a domain rather than a hand-picked sample.

    Born green: the table and the list are authored together. red under: add a
    fourth level to `_SHAPE_PHASE_PATHS` (a `deeper` under `inner`) without a
    row — its pairs with `top` realise a gap-3 skip class no row names."""
    realised = {_shape_class(members)[1] for members in _shape_subsets()}
    assert realised == _SHAPE_CLASSES, sorted(realised ^ _SHAPE_CLASSES)


# --- axis: CLAUSE COMPOSITION under two tails --------------------------------


def test_two_nested_phases_in_one_clause_play() -> None:
    """The ruled sentence's shape: two phases on one ancestor path, the entry
    called where the innermost runs."""
    _plays(_nested())


def test_a_binder_rides_beside_a_second_phases_tail() -> None:
    """The binder axis crossed with the nest: an indexed phase-local read keyed
    by a parameter, beside a read tailed to the enclosing phase."""
    _plays(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], trump_suit in outer, stage[p] in inner",
            inner_state="stage[player] : Integer = 0",
        )
    )


def test_two_nested_phases_sit_beside_game_level_names() -> None:
    """Canasta's mixing shape crossed with the nest: game-level names in the
    same clause as two scoped ones."""
    _plays(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], meld[p], trump_suit in outer, deep in inner"
        )
    )


def test_an_inner_phase_redeclaring_an_outer_tails_name_is_the_descendant_arms(
) -> None:
    """The fourth predicate speaks per READ, so it is what refuses the inner
    phase re-declaring a name the outer tail names — the innermost frame would
    win at run time while the declaration names the ancestor's."""
    message = _refused(
        _nested(
            inner_state="deep : Integer = 0  trump_suit : Suit? = hearts",
        )
    )
    assert "inner" in message, message
    assert "declares `trump_suit` too" in message, message


def test_an_ancestor_declaring_the_tailed_name_too_plays() -> None:
    """The converse, and an accept: the tail names the DESCENDANT and an
    ancestor declares the name as well. The innermost walk returns the
    descendant's value, which is what the declaration names — and the
    ancestor's variable stays readable by an entry callable outside the
    descendant, which is why this pair is not the game-and-phase shadow."""
    _plays(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], trump_suit in inner",
            inner_state="deep : Integer = 0  trump_suit : Suit? = hearts",
        )
    )


def test_one_misspelled_tail_beside_a_good_one_reports_once() -> None:
    """One defect, one diagnostic, with two tails present. A misspelled tail has
    no phase path, so asking "do these nest?" first would co-report the
    composition error on top of the typo — which is why the nest arm sits after
    every per-read tail has validated."""
    message = _refused(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], trump_suit in outer, deep in nowhere"
        )
    )
    assert "no phase `nowhere`" in message, message
    assert "do not nest" not in message, message
    assert "callable only where" not in message, message


def test_the_same_name_under_two_tails_is_the_repeat_guards() -> None:
    """Two declarations of ONE spelling. The bundle is keyed by bare name, so it
    cannot carry both — the repeat guard owns it, and its message says which
    fact makes the pair unrepresentable rather than only that a repeat replaces
    the first."""
    message = _refused(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], trump_suit in outer, trump_suit in inner",
            inner_state="deep : Integer = 0  trump_suit : Suit? = hearts",
        )
    )
    assert "more than once" in message, message
    assert "each spelling at most once" in message, message


def test_a_repeat_beside_two_tails_is_still_the_repeat_guards() -> None:
    """The same guard where a designer meets it: two nested tails and one name
    written twice."""
    message = _refused(
        _nested(
            block="pinochle_meld_value(p : Player) : Integer\n"
            "        reads hand[p], trump_suit in outer, deep in inner, deep"
        )
    )
    assert "`deep` more than once" in message, message


@pytest.mark.parametrize(
    "extra,fragment",
    [
        ("  trump_suit : Suit? = hearts", "trump_suit"),
        ("", "trump_suit"),
    ],
    ids=["shadowed-pair", "phase-and-zone"],
)
def test_the_standing_collision_arms_still_speak_under_two_tails(
    extra: str, fragment: str
) -> None:
    """The lift must not loosen a standing refusal. #516's two arms are
    re-probed with a second tail present: the game-and-phase shadow, and a name
    a phase declares as state while the game declares it as a zone."""
    if extra:
        source = _nested(game_state=extra)
    else:
        source = _nested().replace(
            "  zones { deck : Deck  hand[player] : Hand<player> }",
            "  zones { deck : Deck  hand[player] : Hand<player>  "
            "trump_suit : Discard }",
        )
    message = _refused(source)
    assert fragment in message, message
    assert "do not nest" not in message, message


def test_a_pure_entry_under_two_tails_is_still_the_pure_guards() -> None:
    """The pure-reads guard speaks before the nest arm: an implementation that
    never receives the bundle cannot honour a `reads` clause, whatever its tails
    name."""
    message = _refused(
        _nested(
            block="skat_next_bid(x : Integer) : Integer\n"
            "        reads trump_suit in outer, deep in inner",
            inner_body="      meld[0] := skat_next_bid(0)\n",
        )
    )
    assert "pure" in message, message


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
    "ancestor-phase": ("outer", "pinochle_meld_value", "encloses"),
    "function-body": ("outer", "pinochle_meld_value"),
    "rule-applies-when": ("outer", "pinochle_meld_value"),
    "loser-expression": ("outer", "pinochle_meld_value"),
    "move-type-offered-inside": None,
    "move-type-offered-outside": ("note", "outer"),
    "move-type-offered-nowhere": ("note", "offers"),
    "procedure-run-inside": None,
    "procedure-run-outside": ("bump", "outer"),
    "procedure-run-both-sides": ("bump", "outer"),
    # A procedure NO statement runs is `_check_procedures`' — it refuses every
    # uninvoked procedure game-wide, so both the call and the offer rows below
    # carry that message rather than a scope-flavoured copy of it. Cited, not
    # re-covered; the row exists so the fourth vector of the `run`-site axis is
    # in the record with its Owner named.
    "procedure-never-run": ("bump", "never run"),
    # An offering site is judged at its POSITION, not where its text sits, so
    # the container an offer is written in crosses the offering axis: written
    # in a phase (the three `move-type-offered-*` rows above), in a procedure
    # body (run inside, run both sides, never run), or inside another move type
    # — where the analysis has no position to name and says so. The `produces:`
    # arm rows are the plan's promised handler cells.
    #
    # Added after both takes, so they sit in neither born-red count. The four
    # offering-container rows were RED against the arm this change replaces,
    # which judged an offer where its text sits: the run-inside accept was
    # refused as a leak, and the other three were refused with a message about
    # state not standing rather than about the position the analysis lacks.
    # The two `produces:` rows are born green — the arm body is inside
    # `_walk(phase)` and the sibling call is a direct one — and redden under
    # building `inside` from a phase's statements rather than its whole extent.
    "move-type-offered-by-a-run-inside": None,
    "move-type-offered-by-a-run-both-sides": ("note", "show", "outer"),
    "move-type-offered-by-an-unrun-procedure": ("show", "never run"),
    "move-type-offered-from-a-move-type": (
        "note",
        "relay",
        "does not follow offers made from inside another move type",
    ),
    "move-type-offered-from-a-define": (
        "note",
        "define pick",
        "does not follow offers made from inside a `define` body",
    ),
    "produces-arm-inside": None,
    "produces-arm-sibling": ("outer", "pinochle_meld_value"),
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
# A procedure that OFFERS rather than calls: coup's `challenge_window` shape,
# and the reason an offering site's position is its `run` site.
_SHOW = "procedure show() {\n  offer to 0 one of [note]\n}\n"
# A move type whose effect offers another: coup's `foreign_aid` shape, and the
# offering container this analysis declines to follow.
_RELAY = "move_type relay {\n  when: true\n  effect { offer to 0 one of [note] }\n}\n"
_PICK = "define pick -> { won(Player) } {\n  produce won(0)\n}\n"
# A define whose body OFFERS: `_run_define` runs it at the `produces:` site, so
# its position is that site — the fourth statement-holding container, and the
# second the analysis walls.
_PICK_OFFERS = (
    "define pick -> { won(Player) } {\n"
    "  offer to 0 one of [note]\n"
    "  produce won(0)\n"
    "}\n"
)
_ARM = "    pick produces:\n      won(q) { meld[q] := pinochle_meld_value(q) }\n"


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
        case "procedure-never-run":
            return _probe(top=_BUMP, outer_body=_DEAL)
        case "move-type-offered-by-a-run-inside":
            return _probe(top=_NOTE + _SHOW, outer_body=_DEAL + "    run show()\n")
        case "move-type-offered-by-a-run-both-sides":
            return _probe(
                top=_NOTE + _SHOW,
                outer_body=_DEAL + "    run show()\n",
                after_outer="  phase later {\n    run show()\n  }\n",
            )
        case "move-type-offered-by-an-unrun-procedure":
            return _probe(top=_NOTE + _SHOW, outer_body=_DEAL)
        case "move-type-offered-from-a-move-type":
            return _probe(
                top=_NOTE + _RELAY,
                outer_body=_DEAL + "    offer to 0 one of [relay]\n",
            )
        case "move-type-offered-from-a-define":
            return _probe(
                top=_NOTE + _PICK_OFFERS,
                outer_body=_DEAL
                + "    pick produces:\n      won(q) { meld[q] := meld[q] }\n",
            )
        case "produces-arm-inside":
            return _probe(top=_PICK, outer_body=_DEAL + _ARM)
        case "produces-arm-sibling":
            return _probe(
                top=_PICK,
                outer_body=_DEAL,
                after_outer="  phase later {\n" + _ARM + "  }\n",
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


def test_a_wrong_tail_and_a_wrong_call_site_report_once() -> None:
    """One defect, one diagnostic. A tail that does not resolve leaves the
    entry out of the containment analysis entirely — otherwise a designer who
    misspelled the phase would be told BOTH that the tail is wrong and that
    every call of the entry is in the wrong place, and would have to work out
    which of the two is the actual mistake.

    Written after the guard it measures, so it sits in neither born-red count.
    red under: drop the classifier question from
    `resolve._scoped_entry_phases` — the containment arm then speaks over the
    tail arm and this probe sees it."""
    # The tail names `later`, which declares nothing; `outer` is the declarer,
    # and the call sits in `outer` — so a containment analysis that ran anyway
    # would refuse the call for being outside `later` as well.
    source = _probe(
        block="pinochle_meld_value(p : Player) : Integer "
        "reads hand[p], trump_suit in later",
        outer_body=_DEAL + "    meld[0] := pinochle_meld_value(0)\n",
        after_outer="  phase later {\n    meld[1] := 0\n  }\n",
    )
    message = _refused(source)
    assert "declares no state" in message, message
    # Anchored on the containment sentence's INVARIANT half. The phase it names
    # is interpolated, so a fragment carrying "that phase" would name text no
    # diagnostic can produce and could never fail again.
    assert "callable only where" not in message, message


def test_the_enclosure_register_separates_an_ancestor_from_a_sibling() -> None:
    """An ENCLOSING phase runs outside the region for a different reason than a
    sibling does — its frame is standing, the region's is not — and the
    diagnostic says which, because the fixes differ: move the call in, versus
    the call is nowhere near. The pair is what pins the enclosure branch;
    either sentence alone would pass a guard that said "encloses" of every
    outside phase."""
    ancestor = _refused(_containment_source("ancestor-phase"))
    sibling = _refused(_containment_source("sibling-phase"))
    assert "encloses `outer` but runs outside it" in ancestor, ancestor
    assert "encloses" not in sibling, sibling
    assert "runs outside it" in sibling, sibling


# --- the position taxonomy crossed with the nested pair ----------------------
#
# The region of an entry naming two nested phases is the INNERMOST one's
# subtree, so the outer phase's own body and hooks are outside it even though
# the outer's frame is standing there. That is the position the lift makes
# newly refusable, and the register separates it from a phase that is merely
# elsewhere.

_BINDING = "reads `deep in inner`"
_REGION = "callable only where `inner` runs"
_ENCLOSED = "encloses `inner` but runs outside it"

_ENCLOSURE = (_BINDING, _REGION, _ENCLOSED)

_NEST_CONTAINMENT_CELLS: dict[str, tuple[tuple[str, ...], tuple[str, ...]] | None] = {
    # vector -> (fragments the refusal carries, fragments it must NOT), or None
    # for an accepted position, which PLAYS.
    "inner-body": None,
    "inner-hooks": None,
    "child-of-the-inner": None,
    "outer-body-before-the-inner": (_ENCLOSURE, ()),
    "outer-body-after-the-inner": (_ENCLOSURE, ()),
    "outer-qualifier": (_ENCLOSURE, ()),
    "outer-before-each": (_ENCLOSURE, ()),
    "outer-after-each": (_ENCLOSURE, ()),
    "sibling-of-the-outer": (
        (_BINDING, _REGION, "in `later`, which runs outside it"),
        ("encloses",),
    ),
    "function-body": ((_BINDING, _REGION), ("encloses",)),
    "loser-expression": ((_BINDING, _REGION), ("encloses",)),
    "move-type-offered-inside-the-inner": None,
    "move-type-offered-in-the-outer": (("note", "inner"), ()),
    "move-type-offered-both-sides": (("note", "inner"), ()),
    "procedure-run-inside-the-inner": None,
    "procedure-run-in-the-outer": (("bump", "inner"), ()),
    "procedure-run-both-sides": (("bump", "inner"), ()),
    "three-chain-innermost": None,
    "three-chain-middle": (
        ("reads `deepest_v in deepest`", "callable only where `deepest` runs"),
        (),
    ),
    "three-chain-outer": (
        ("reads `deepest_v in deepest`", "callable only where `deepest` runs"),
        (),
    ),
}

_INERT_INNER = "      deep := deep\n"

# The three positions no corpus game reaches, one level deeper than the
# single-phase fixture's: the INNER phase's own qualifier, `before_each` and
# `after_each`, all of which run between its push and its pop and are therefore
# inside the region — proven by which `stage` value each call presents.
_NESTED_INNER_HOOKS_FIXTURE = (
    "game Probe {\n"
    "  players: 2\n"
    "  max_length: 100\n"
    "  cards: pinochle48\n"
    "  ranking: A 10 K Q J 9\n"
    "  primitives {\n"
    "    pinochle_meld_value(p : Player) : Integer\n"
    "        reads hand[p], stage, trump_suit in outer, deep in inner\n"
    "  }\n"
    "  zones { deck : Deck  hand[player] : Hand<player> }\n"
    "  state { meld[player] : Integer = 0  stage : Integer = 0 }\n"
    "  phase outer {\n"
    "    state { trump_suit : Suit? = spades }\n"
    "    shuffle deck\n"
    "    deal 12 cards from deck to each hand\n"
    "    phase inner repeat until (pinochle_meld_value(0) >= 0 and done) {\n"
    "      state { deep : Integer = 0  done : Boolean = false }\n"
    "      before_each { stage := 1  meld[0] := pinochle_meld_value(0) }\n"
    "      after_each  { stage := 3  meld[1] := pinochle_meld_value(1) }\n"
    "      stage := 2\n"
    "      meld[0] := pinochle_meld_value(0)\n"
    "      done := true\n"
    "    }\n"
    "  }\n"
    "  winner: highest meld\n"
    "}\n"
)


def _three_chain(call_in: str) -> str:
    """`outer` > `inner` > `deepest`, each declaring state the entry names, with
    the call in one of the three — the no-depth-cap claim, sampled."""

    def body(phase: str, indent: int) -> str:
        return _call_at(indent) if phase == call_in else ""

    return (
        "game Probe {\n"
        "  players: 2\n"
        "  max_length: 100\n"
        "  cards: pinochle48\n"
        "  ranking: A 10 K Q J 9\n"
        "  primitives { pinochle_meld_value(p : Player) : Integer\n"
        "      reads hand[p], trump_suit in outer, deep in inner, "
        "deepest_v in deepest }\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { meld[player] : Integer = 0 }\n"
        "  phase outer {\n"
        "    state { trump_suit : Suit? = spades }\n"
        "    shuffle deck\n"
        "    deal 12 cards from deck to each hand\n"
        + body("outer", 4)
        + "    phase inner {\n"
        "      state { deep : Integer = 0 }\n"
        + body("inner", 6)
        + "      phase deepest {\n"
        "        state { deepest_v : Integer = 0 }\n"
        "        deepest_v := deepest_v\n"
        + body("deepest", 8)
        + "      }\n"
        "    }\n"
        "  }\n"
        "  winner: highest meld\n"
        "}\n"
    )


def _nest_containment_source(cell: str) -> str:
    match cell:
        case "inner-body":
            return _nested()
        case "inner-hooks":
            return _NESTED_INNER_HOOKS_FIXTURE
        case "child-of-the-inner":
            return _nested(
                inner_body=_INERT_INNER
                + "      phase deeper {\n"
                + _call_at(8)
                + "      }\n"
            )
        case "outer-body-before-the-inner":
            return _nested(inner_body=_INERT_INNER, outer_before=_call_at(4))
        case "outer-body-after-the-inner":
            return _nested(inner_body=_INERT_INNER, outer_after=_call_at(4))
        case "outer-qualifier":
            return _nested(
                outer_qualifier="repeat until (pinochle_meld_value(0) >= 0) ",
                inner_body=_INERT_INNER,
            )
        case "outer-before-each":
            return _nested(
                outer_qualifier="repeat until (done) ",
                outer_state="trump_suit : Suit? = spades  done : Boolean = true",
                outer_items="    before_each { meld[0] := pinochle_meld_value(0) }\n",
                inner_body=_INERT_INNER,
            )
        case "outer-after-each":
            return _nested(
                outer_qualifier="repeat until (done) ",
                outer_state="trump_suit : Suit? = spades  done : Boolean = true",
                outer_items="    after_each { meld[0] := pinochle_meld_value(0) }\n",
                inner_body=_INERT_INNER,
            )
        case "sibling-of-the-outer":
            return _nested(
                inner_body=_INERT_INNER,
                after_outer="  phase later {\n" + _call_at(4) + "  }\n",
            )
        case "function-body":
            return _nested(
                top="function meld_of(q : Player) = pinochle_meld_value(q)\n",
                inner_body="      for each player p: meld[p] := meld_of(p)\n",
            )
        case "loser-expression":
            return _nested(
                inner_body=_INERT_INNER,
                winner="  loser: the player where pinochle_meld_value(player) >= 0\n",
            )
        case "move-type-offered-inside-the-inner":
            return _nested(top=_NOTE, inner_body="      offer to 0 one of [note]\n")
        case "move-type-offered-in-the-outer":
            return _nested(
                top=_NOTE,
                inner_body=_INERT_INNER,
                outer_after="    offer to 0 one of [note]\n",
            )
        case "move-type-offered-both-sides":
            return _nested(
                top=_NOTE,
                inner_body="      offer to 0 one of [note]\n",
                outer_after="    offer to 1 one of [note]\n",
            )
        case "procedure-run-inside-the-inner":
            return _nested(top=_BUMP, inner_body="      run bump()\n")
        case "procedure-run-in-the-outer":
            return _nested(
                top=_BUMP, inner_body=_INERT_INNER, outer_after="    run bump()\n"
            )
        case "procedure-run-both-sides":
            return _nested(
                top=_BUMP,
                inner_body="      run bump()\n",
                outer_after="    run bump()\n",
            )
        case "three-chain-innermost":
            return _three_chain("deepest")
        case "three-chain-middle":
            return _three_chain("inner")
        case "three-chain-outer":
            return _three_chain("outer")
    raise AssertionError(f"no source for nested containment cell {cell!r}")


@pytest.mark.parametrize("cell", sorted(_NEST_CONTAINMENT_CELLS), ids=lambda c: c)
def test_the_containment_position_taxonomy_under_the_nest(cell: str) -> None:
    """One cell of the position taxonomy, crossed with two nested phases. An
    admitted position PLAYS; a refused one names the read that binds the region
    and the phase the call sits in — and says whether that phase encloses the
    region, since a call inside the enclosing phase moves in while a call
    elsewhere does not."""
    expected = _NEST_CONTAINMENT_CELLS[cell]
    source = _nest_containment_source(cell)
    if expected is None:
        _plays(source)
        return
    present, absent = expected
    message = _refused(source)
    for fragment in present:
        assert fragment in message, message
    for fragment in absent:
        assert fragment not in message, message


def test_the_admitted_inner_hook_positions_are_reached_by_a_playout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The accept row says the inner phase's hooks are ADMITTED; this says they
    are REACHED, with both frames standing — the same discharge the
    single-phase fixture makes one level up, since the outer frame's standing
    is what a nested region's admission rests on.

    stage 0 is reachable only by the qualifier (its first evaluation runs
    before any statement), 1 only by `before_each`, 2 by the body, 3 by
    `after_each` and by the qualifier's later evaluations."""
    from cardlang.runtime import pinochle as pinochle_mod

    seen: list[tuple[int, object]] = []
    real = pinochle_mod.pinochle_meld_value

    def spy(facts: object, gr: object, player: object) -> int:
        state = gr.state  # type: ignore[attr-defined]
        seen.append((int(state["stage"]), state["trump_suit"]))
        return real(facts, gr, player)  # type: ignore[arg-type]

    monkeypatch.setattr(pinochle_mod, "pinochle_meld_value", spy)
    play_game(_checks(_NESTED_INNER_HOOKS_FIXTURE), random.Random(0))
    stages = {stage for stage, _ in seen}
    assert {0, 1, 2, 3} <= stages, seen
    assert all(trump == "spades" for _, trump in seen), seen


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


def test_a_procedure_run_inside_the_subtree_really_offers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The accept row says the position is ADMITTED; this says it is REACHED.
    That fixture's only caller of the scoped entry is the offered move type's
    `when:`, so a call proves the spliced offer put `note` in play and the
    entry ran with the declaring frame standing — which `_plays`' score-key
    assertion holds whether or not the offer ever fired.

    Written against a built analysis, so it sits in neither born-red count.
    red under: guard the fixture's run site with `if false { run show() }` —
    the containment row stays GREEN under that edit, which is the whole reason
    this cell exists beside it. (Deleting the run site instead reddens on
    `_check_procedures`' never-run refusal, a different claim.)"""
    from cardlang.runtime import pinochle as pinochle_mod

    callers: list[object] = []
    real = pinochle_mod.pinochle_meld_value

    def spy(facts: object, gr: object, player: object) -> int:
        callers.append(player)
        return real(facts, gr, player)  # type: ignore[arg-type]

    monkeypatch.setattr(pinochle_mod, "pinochle_meld_value", spy)
    _plays(_containment_source("move-type-offered-by-a-run-inside"))
    assert callers, "the spliced offer never put `note` in play"


def test_the_statement_holding_containers_are_classified_total() -> None:
    """An offering site's POSITION is decided by the container its text sits
    in, so the container set is the offering arm's other domain — and it is the
    grammar's, not the analysis's. Every production holding `statement*` is
    either a statement form (reached from `?statement` or `?phase_item`, and so
    inheriting whichever container encloses it) or a DEFINITION form that
    introduces one; the definition forms are derived here by subtracting the
    first set from the second, and each is classified.

    Two of the four yield positions — a phase's statements run where they are
    written, a procedure's wherever it is run — and two do not, which is what
    `resolve._UNPOSITIONED_CONTAINERS` records. A statement-holding production
    added without a row lands in the wall's safe direction at run time and
    reddens here at once.

    Written against a built analysis, so it sits in neither born-red count and
    carries a reddening mutation per claim: for the DERIVATION, add an inert
    `statement*` production to the grammar (`spare_block: _EFFECT_KW "{"
    statement* "}"`) — the parser still builds and `spare_block` arrives
    undecided; for the CLASSIFICATION, drop the `defines` row from
    `_UNPOSITIONED_CONTAINERS`."""
    from cardlang.resolve import _UNPOSITIONED_CONTAINERS

    grammar = (ROOT_DIR / "cardlang" / "grammar" / "cardlang.lark").read_text()
    holds_statements = {
        m.group(1)
        for m in re.finditer(r"^\??(\w+):[^\n]*(?:\n\s+\|[^\n]*)*", grammar, re.M)
        if re.search(r"statement[*+]", m.group(0))
    }
    # Reachability from the two statement roots: anything a statement form can
    # nest inside inherits its enclosing container and introduces none.
    refs = {
        m.group(1): set(re.findall(r"\b([a-z_]\w*)\b", m.group(0)))
        for m in re.finditer(r"^\??(\w+):[^\n]*(?:\n\s+\|[^\n]*)*", grammar, re.M)
    }
    nested: set[str] = set()
    frontier = {"statement", "phase_item"}
    while frontier:
        name = frontier.pop()
        for child in refs.get(name, ()):
            if child not in nested and child != name:
                nested.add(child)
                frontier.add(child)
    definitions = holds_statements - nested
    assert definitions == {"procedure_def", "move_effect", "define_def"}, sorted(
        definitions
    )
    # Plus `phase`, which holds statements through `?phase_item` rather than
    # directly, and is the one container whose statements ARE their position.
    assert "statement" in refs["phase_item"]
    assert set(_UNPOSITIONED_CONTAINERS) == {"move_types", "defines"}


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
    game's own move type. Edges match by name across both.

    Born green: the overlap is a corpus fact this cell records, not a claim
    about the analysis, so what it proves is that `_offers_move_type`'s
    cross-namespace match has a live witness rather than a hypothetical one.

    red under: drop `declare_trump_suit` from pinochle's `legal_moves:` line,
    or from the game's own move-type definitions."""
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


def test_a_phases_frame_does_not_outlive_the_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The premise the non-nesting refusal rests on, as a checked fact rather
    than a comment. `run_phase` pops what it pushed, so a phase's state stands
    nowhere outside that phase's extent — which is why no position in a game
    runs two phases neither of which is inside the other, and why an entry
    reading from both is refused as a designed constraint rather than deferred
    as a wall. If the premise ever went false the refusal would become the
    wrong answer silently, so it is pinned rather than argued.

    Born green. red under: drop the `finally: ctx.rs.pop_frame()` from
    `runtime/driver.run_phase` — every enclosing phase's depth then differs
    across its own call, and a sibling's frame survives into the phase after
    it."""
    from cardlang.runtime import driver as driver_mod

    real = driver_mod.run_phase
    depths: list[tuple[str, int, int]] = []

    def spy(phase: n.Phase, ctx: typing.Any, hands: typing.Any) -> None:
        before = len(ctx.rs.frames)
        real(phase, ctx, hands)
        depths.append((phase.name, before, len(ctx.rs.frames)))

    monkeypatch.setattr(driver_mod, "run_phase", spy)
    play_game(_checks(_shape_source(("inner",))), random.Random(0))
    assert depths, "no phase ran"
    assert all(before == after for _, before, after in depths), depths
    # And the frames were genuinely pushed, so the equality above is not the
    # trivial one a runtime that pushed nothing would satisfy.
    entered = {name: before for name, before, _ in depths}
    assert entered["inner"] > entered["outer"] > entered["top"], depths
    assert entered["later"] == entered["outer"], depths


def test_the_move_type_index_readers_are_the_pinned_census() -> None:
    """The containment guard is sound only if a game move type's body executes
    inside an offering site's dynamic extent and nowhere else. No static pass
    can see that; what prices it is this census of the runtime sites that
    reach a move-type definition BY NAME, read the two-readers way — the pin
    reads the consumer sites, not the guard's own output, so a new execution
    channel reddens here rather than making the guard silently unsound.

    The matcher is the BARE name, not the subscript spelling: a consumer
    reaching a definition through `.get(name)` or `.values()` is exactly the new
    channel the premise would not survive, and a subscript-shaped scrape would
    let it land silently while claiming to census sites that reach a definition
    by name. Widening it admits the two sites that are not readers at all, and
    they are named here so the pin discriminates rather than merely counting:
    the constructor write in `driver.py` (which BUILDS the index) and the
    attribute's declaration in `state.py`. Everything else is a reader, and the
    two channels are the offer interpreter (`runtime/execute.py`) and the
    auction form (`runtime/mechanics.py`).

    red under: add a `move_type_index` mention anywhere else under
    `cardlang/runtime/` — a `.get(name)` consumer included."""
    hits: dict[str, int] = {}
    for path in (ROOT_DIR / "cardlang" / "runtime").rglob("*.py"):
        count = len(re.findall(r"move_type_index", path.read_text()))
        if count:
            hits[path.name] = count
    assert hits == {
        # readers — the two execution channels the premise is about
        "execute.py": 2,
        "mechanics.py": 2,
        # non-readers, admitted by the wider matcher and excluded by name
        "driver.py": 1,
        "state.py": 1,
    }, hits


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
    A designed constraint of the library tier, not a deferral — there is
    nothing to build and no issue to file. Stated off the grammar so the day a
    library may declare a phase, this reddens rather than the gap going
    unnoticed.

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
    """A floor under the two authored cell dicts, and the honest statement of
    what a floor is worth: the dicts are AUTHORED, not derived, so this catches
    an edit that empties one or drops a whole polarity — never a domain gone
    unexamined. The pins that would catch THAT are the derived ones (the game
    fields, the phase items, the offering slots), each of which reddens on its
    own registry.

    Born green, like every floor. red under: empty either dict, or delete every
    accept row from `_CONTAINMENT_CELLS`, leaving a taxonomy that only ever
    proves the guard fires. The shape axis needs no floor here: its cells are
    DERIVED from `_SHAPE_PHASE_PATHS`, and the class pin beside it is what
    catches a table that stopped realising a class."""
    assert len(_MEMBERSHIP_CELLS) >= 11
    assert len(_CONTAINMENT_CELLS) >= 22
    assert len(_NEST_CONTAINMENT_CELLS) >= 20
    for cells in (_CONTAINMENT_CELLS, _NEST_CONTAINMENT_CELLS):
        assert any(v is None for v in cells.values())
        assert any(v is not None for v in cells.values())
