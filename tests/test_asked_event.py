"""What a seat is told it is being asked, at every decision the engine makes.

property:        Every decision site delivers, to the deciding seat and before
                 any Chooser is consulted, one `asked` observation naming the
                 running phase, the construct asking, how many picks it wants,
                 and the zone the picks land in where that zone is knowable
                 before the choice. The fact rides the observation log, so it
                 reaches a Seat Policy through the Seat View it already takes,
                 and every consumer of it reads the one derivation.
domain:          The decision sites are the rows of
                 `runtime.delegation.DECISION_POINTS`, which an AST scrape
                 over `cardlang/` reconciles against the tree, crossed with the
                 round forms `mechanics.build_form` dispatches over — the round
                 site asks a different construct per form. Each site is
                 witnessed by a registered game that reaches it, and every site
                 has one. The payload's fields are held to
                 `observe.PAYLOAD_SHAPES`, each shape to the values it admits.
                 Destination naming is quantified over every site, in three
                 classes stated per site below: knowable before the pick,
                 knowable only after it, and absent. The misuse probes cover
                 the three ways a decision can reach the Chooser wrongly — a
                 phase-less decision, a site the table does not hold, and an
                 undeclared construct word — each proven loud in the layer that
                 owns it: the choke point refuses the first two in the
                 runtime's channel, and the third is refused at every consumer
                 that reads it, since emission is unfenced by design.
registry:        decision sites, `cardlang.runtime.delegation.DECISION_POINTS`
                 and the scrape at
                 tests/test_delegated_play.py::test_every_decision_point_is_classified;
                 round forms, `cardlang.runtime.mechanics.build_form`; event
                 kinds and their fields,
                 `cardlang.runtime.observe.EVENT_PAYLOADS`; field shapes,
                 `cardlang.runtime.observe.PAYLOAD_SHAPES`; the person's
                 reading, `cardlang.play.events.EVENT_LINES`; the games,
                 `cardlang.openspiel.registry.GAMES`; the shapes' own member
                 and refusal cells,
                 tests/test_observation_payloads.py.
does not prove:  That the phase an ask names is one the deciding seat is
                 entitled to know. A phase guard may read a zone the seat
                 cannot see, and the ask then states that guard's value to the
                 decider; the swap proof replays one recorded history in both
                 worlds of a pair and drops the pairs where a recorded action
                 becomes illegal, so a divergence inside the replayed prefix is
                 invisible to it and one first appearing at the pause is
                 caught. The seeded witness that would redden the class is
                 epic #312's, and issue #281 owns the class itself. Nor that a
                 construct is a MEANING: a number decision's label says which
                 sentence asked, never whether the number is a bid on a hand or
                 a claim a seat may be lying about, which is issue #703's
                 class. The sweep plays each witness game along a bounded
                 seeded line, so a construct only a longer line reaches is
                 unwitnessed by it and covered by the registry cells alone.
"""

from __future__ import annotations

import ast
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.registry import GAMES
from cardlang.pipeline import check_source
from cardlang.play.events import EVENT_LINES
from cardlang.runtime.delegation import DECISION_POINTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.observe import EVENT_PAYLOADS, PAYLOAD_SHAPES

CARDLANG = Path(__file__).resolve().parent.parent / "cardlang"
GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

# The ruled payload (docs/plans/2026-09-17-decision-identity.md): the phase is
# the designer's word for the stretch of play, the construct the kernel's word
# for the kind of sentence asking, the count how many picks it wants, and the
# destination the zone they land in — None where the site cannot know it before
# the choice is made.
ASKED_ROW: tuple[str, ...] = ("phase", "construct", "count", "destination")

# Where each site's destination zone stands at the moment the seat is asked,
# derived from the code that evaluates it: a movement evaluates its destination
# before it selects, the simultaneous pass not until every seat has chosen, and
# an offer or a bare value choice moves nothing of its own.
BEFORE, AFTER, ABSENT = "before", "after", "absent"
DESTINATION_KNOWABILITY: dict[str, str] = {
    "execute._select_from": BEFORE,
    "execute._select_filtered": BEFORE,
    "execute._select_joint": BEFORE,
    "execute._pass_selection": AFTER,
    "execute._offer": ABSENT,
    "evaluate._choose": ABSENT,
    "mechanics.run_decision_round": BEFORE,
}

# The construct each site asks by, as the table spells it. A witness game
# reaches several sites, so a behavioural cell that asked only whether SOME ask
# arrived would pass on a neighbour's — the cells below look for this word.
SITE_CONSTRUCT: dict[str, str] = {
    "execute._select_from": "transfer",
    "execute._select_filtered": "transfer",
    "execute._select_joint": "joint",
    "execute._pass_selection": "simultaneous",
    "execute._offer": "offer",
    "evaluate._choose": "choose",
    "mechanics.run_decision_round": "trick",
}

# One registered game per site that reaches it, so every behavioural cell runs
# against a real game rather than a fixture. The mapping is authored and the
# cell below proves each witness reaches the site it is named for, so a game
# that stops reaching one fails loudly rather than thinning the sweep.
SITE_WITNESS: dict[str, str] = {
    "execute._select_from": "cardlang_cheat",
    "execute._select_filtered": "cardlang_cribbage",
    "execute._select_joint": "cardlang_scopa",
    "execute._pass_selection": "cardlang_hearts",
    "execute._offer": "cardlang_coup",
    "evaluate._choose": "cardlang_oh_hell",
    "mechanics.run_decision_round": "cardlang_spades",
}

SEED = 7


def _chooser_call_sites() -> set[str]:
    """Every `<expr>.chooser(...)` call site under `cardlang/`, as
    "module.enclosing_function" — the same shape-reading scrape the delegated
    play census uses, so the two agree on what a decision site is."""
    sites: set[str] = set()
    for path in sorted(CARDLANG.rglob("*.py")):
        tree = ast.parse(path.read_text())
        spans = [
            (n.lineno, max(getattr(n, "end_lineno", n.lineno) or n.lineno, n.lineno), n.name)
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "chooser"
            ):
                enclosing = [name for lo, hi, name in spans if lo <= node.lineno <= hi]
                sites.add(f"{path.stem}.{enclosing[-1] if enclosing else '<module>'}")
    return sites


def _round_forms() -> set[str]:
    """The round forms `build_form` dispatches over, read off its own signature
    rather than listed here: the annotation IS the union, so a fourth form
    arrives as an uncovered cell."""
    source = (CARDLANG / "runtime" / "mechanics.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_form":
            annotation = node.args.args[0].annotation
            assert annotation is not None, "build_form's round argument is unannotated"
            return {
                part.attr
                for part in ast.walk(annotation)
                if isinstance(part, ast.Attribute)
            }
    raise AssertionError("mechanics.build_form not found — the form axis has no defining site")


def _play_collecting(
    game_key: str, seed: int = SEED
) -> tuple[list[tuple[int, list[Any], int]], dict[int, list[tuple[Any, ...]]]]:
    """Play one registered game, recording every decision as it is asked and
    every observation event each seat receives."""
    game = check_source(GAMES_DIR / GAMES[game_key])
    rng = random.Random(seed)
    decisions: list[tuple[int, list[Any], int]] = []
    logs: dict[int, list[tuple[Any, ...]]] = {}

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs.setdefault(player, []).append(event)

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        decisions.append((player, list(candidates), n))
        return rng.sample(candidates, n)

    try:
        play_game(game, rng, chooser=chooser, observer=observe)
    except Exception:  # noqa: BLE001 - a line that ends early still carries its asks
        pass
    return decisions, logs


def _asks(log: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [event for event in log if event and event[0] == "asked"]


# =============================================================================
# The registry cells — the payload and the tables that must name it
# =============================================================================


def test_asked_is_a_declared_event_kind() -> None:
    assert "asked" in EVENT_PAYLOADS, (
        "a seat is told what it is asked through an observation, so `asked` is "
        "a declared kind of one"
    )


def test_asked_carries_the_ruled_fields() -> None:
    assert EVENT_PAYLOADS.get("asked") == ASKED_ROW


@pytest.mark.parametrize("shape", ASKED_ROW)
def test_every_asked_field_shape_is_declared(shape: str) -> None:
    assert shape in PAYLOAD_SHAPES, (
        f"an `asked` event's {shape!r} field has no declared shape, so nothing "
        f"downstream has a reading for it"
    )


@pytest.mark.parametrize("site", sorted(DECISION_POINTS))
def test_every_decision_point_names_a_construct(site: str) -> None:
    """A decision site says which construct asks there, or an ask made from it
    could not name one."""
    row = DECISION_POINTS[site]
    assert hasattr(row, "construct") and isinstance(row.construct, str) and row.construct, (
        f"{site} names no construct — an ask made there has nothing to say "
        f"about what kind of decision it is"
    )


@pytest.mark.parametrize("form", sorted(_round_forms()))
def test_every_round_form_names_a_construct(form: str) -> None:
    """The round site asks a different construct per form, so the fan-out
    covers every form `build_form` dispatches over."""
    import cardlang.runtime.delegation as delegation

    forms: dict[str, str] = getattr(delegation, "FORM_CONSTRUCTS", {})
    assert form in forms, (
        f"{form} names no construct, so a decision it asks would be reported as "
        f"some other form's"
    )


def test_the_choke_point_is_the_only_caller_of_the_chooser() -> None:
    """One route from a decision site to the Chooser, so an ask cannot be
    skipped by reaching the Chooser another way.

    red under: call `ctx.chooser(...)` from a second function under
    `cardlang/` — the scrape gains a site this set does not hold."""
    assert _chooser_call_sites() == {"chooser.decide"}, (
        "every decision reaches the Chooser through `chooser.decide`, which is "
        "what makes the ask uniform across the decision sites"
    )


def test_every_declared_kind_has_a_line() -> None:
    """A kind a seat can receive is a kind a seat's own view can read.

    `play/events.py` states this in prose; the check is here, because a kind
    declared and unlined passes `payload_refusal` and then raises where a
    person reads their log.

    red under: delete a row from `play.events.EVENT_LINES` (or declare a kind
    in `EVENT_PAYLOADS` with no line) — the key sets part."""
    assert set(EVENT_PAYLOADS) == set(EVENT_LINES), (
        "observation-event kinds and the lines a seat's view shows for them "
        "disagree — every declared kind carries a reading"
    )


def test_destination_knowability_is_stated_for_every_site() -> None:
    """Every decision site says where its destination stands when the seat is
    asked, so no site's answer is left to the emitter's judgment.

    red under: delete a row from `DESTINATION_KNOWABILITY` — the key sets
    part."""
    assert set(DESTINATION_KNOWABILITY) == set(DECISION_POINTS)
    assert set(DESTINATION_KNOWABILITY.values()) <= {BEFORE, AFTER, ABSENT}


def test_every_construct_has_a_phrase_a_person_reads() -> None:
    """Every construct word a seat can be told is one their own view can say.

    red under: delete a row from `play.events._ASK_PHRASES` — the key sets
    part, and the seat whose decision used that construct sees a raised line
    instead of its own."""
    from cardlang.play.events import _ASK_PHRASES
    from cardlang.runtime.delegation import CONSTRUCTS

    assert set(_ASK_PHRASES) == CONSTRUCTS, (
        "a construct a decision can be asked by has no phrase a person reads"
    )


def test_every_word_the_tables_name_is_a_declared_construct() -> None:
    """The two places a construct word is written agree with the closed set.

    red under: change a construct in `DECISION_POINTS` or `FORM_CONSTRUCTS` to
    a word `CONSTRUCTS` does not hold."""
    from cardlang.runtime.delegation import CONSTRUCTS, FORM_CONSTRUCTS

    written = {row.construct for row in DECISION_POINTS.values()} | set(
        FORM_CONSTRUCTS.values()
    )
    assert written <= CONSTRUCTS, f"undeclared construct words: {sorted(written - CONSTRUCTS)}"


def test_every_site_has_a_witness_game() -> None:
    """Each site is witnessed by a game that reaches it.

    red under: point a row of `SITE_WITNESS` at a game that never reaches its
    site — the reached-sites assertion below fails for that row."""
    assert set(SITE_WITNESS) == set(DECISION_POINTS)
    assert set(SITE_WITNESS.values()) <= set(GAMES)
    assert set(SITE_CONSTRUCT) == set(DECISION_POINTS)


# =============================================================================
# The behavioural cells — what a seat is actually told, per site
# =============================================================================


@pytest.mark.parametrize("site", sorted(SITE_WITNESS))
def test_a_decider_is_told_what_it_is_asked(site: str) -> None:
    """Every decision a seat makes is preceded by that seat's own ask."""
    word = SITE_CONSTRUCT[site]
    decisions, logs = _play_collecting(SITE_WITNESS[site])
    assert decisions, f"{SITE_WITNESS[site]} made no decision at seed {SEED}"
    asked = {seat: _asks(log) for seat, log in logs.items()}
    assert any(ask[2] == word for asks in asked.values() for ask in asks), (
        f"{SITE_WITNESS[site]} reaches {site} and no seat was told it was being "
        f"asked by {word!r} — an ask from a NEIGHBOURING site would pass a "
        f"weaker cell than this one"
    )
    for seat, _candidates, _n in decisions:
        assert asked.get(seat), f"seat {seat} decided without being told what it was asked"


@pytest.mark.parametrize("site", sorted(SITE_WITNESS))
def test_an_ask_names_a_phase_and_a_declared_construct(site: str) -> None:
    """An ask's phase is a name and its construct is one the tables declare —
    never None, and never a word a consumer has no reading for."""
    import cardlang.runtime.delegation as delegation

    declared: frozenset[str] = getattr(delegation, "CONSTRUCTS", frozenset())
    _decisions, logs = _play_collecting(SITE_WITNESS[site])
    seen = [ask for log in logs.values() for ask in _asks(log)]
    assert seen, f"{SITE_WITNESS[site]} emitted no ask at seed {SEED}"
    for _kind, phase, construct, count, _destination in seen:
        assert isinstance(phase, str) and phase, "an ask names the phase it is asked in"
        assert construct in declared, f"{construct!r} is not a declared construct"
        assert isinstance(count, int) and not isinstance(count, bool) and count > 0


@pytest.mark.parametrize("site", sorted(SITE_WITNESS))
def test_the_destination_is_named_exactly_where_it_is_knowable(site: str) -> None:
    """A site that knows where the picks land says so; one that cannot know it
    before the choice says nothing, rather than a plausible wrong zone."""
    word = SITE_CONSTRUCT[site]
    _decisions, logs = _play_collecting(SITE_WITNESS[site])
    seen = [ask for log in logs.values() for ask in _asks(log) if ask[2] == word]
    assert seen, f"{SITE_WITNESS[site]} emitted no {word!r} ask at seed {SEED}"
    knowable = DESTINATION_KNOWABILITY[site] is BEFORE
    named = [ask[4] for ask in seen]
    if knowable:
        assert any(label is not None for label in named), (
            f"{site} evaluates its destination before it selects, so an ask "
            f"made there names the zone the picks land in"
        )
    else:
        assert all(label is None for label in named), (
            f"{site} cannot know where its picks land before the choice is "
            f"made, so an ask made there names no zone rather than a "
            f"plausible wrong one"
        )
    assert all(label is None or isinstance(label, str) for label in named)


def test_the_ask_is_derived_in_one_place() -> None:
    """One reading of "what am I asked", so a second consumer cannot grow a
    second one beside it.

    Vacuous until the kind exists and meaningful after, so it carries its
    mutation rather than its red run.

    red under: name `"asked"` in a fifth module under `cardlang/` — say, a
    policy scanning its own log for the kind instead of asking the derivation
    — and the scrape gains a module this set does not hold."""
    readers = {
        path.relative_to(CARDLANG).as_posix()
        for path in sorted(CARDLANG.rglob("*.py"))
        if '"asked"' in path.read_text() or "'asked'" in path.read_text()
    }
    assert readers <= {
        "runtime/observe.py",  # declares the kind
        "runtime/chooser.py",  # emits it
        "play/events.py",  # spells it for a person
        "openspiel/infostate.py",  # derives it — the one reading
    }, f"a module beside the derivation reads the ask: {sorted(readers)}"


# =============================================================================
# Misuse probes — the plausible wrong ways to reach the Chooser
# =============================================================================


def _bare_ctx(phase: Any) -> Any:
    """A context holding only what `decide` reads: the phase, and a Chooser
    that answers. Built by hand rather than played out of a game, because the
    two probes below are about decisions a game cannot produce."""
    import random

    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating

    rs = RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))
    return Ctx(rs=rs, chooser=lambda _p, cands, n: cands[:n], current_phase=phase)


def test_a_decision_asked_outside_every_phase_is_refused() -> None:
    """A decision belongs to a phase, and one asked outside every phase can
    name no stretch of play. Refused in the runtime's own channel, naming the
    site — never sentinelled into a seat's information state."""
    from cardlang.runtime.chooser import decide
    from cardlang.runtime.errors import OwnerGuardError

    with pytest.raises(OwnerGuardError, match="outside every phase"):
        decide(_bare_ctx(None), 0, [1, 2], 1, "evaluate._choose")


def test_a_decision_site_the_table_does_not_hold_is_refused() -> None:
    """The construct word is the table's, not the call's, so a site absent
    from `DECISION_POINTS` cannot quietly ask by some default."""
    from cardlang.runtime.chooser import decide

    class Phase:
        name = "play"

    with pytest.raises(KeyError):
        decide(_bare_ctx(Phase()), 0, [1, 2], 1, "execute._invented_site")


def test_an_ask_carrying_an_undeclared_construct_is_refused_where_it_is_read() -> None:
    """Emission is unfenced by design, so a wrong word is refused at every
    consumer that has to read it rather than where it was made."""
    from cardlang.play.events import event_line
    from cardlang.runtime.observe import payload_refusal

    bad = ("asked", "play", "shuffle", 1, None)
    assert payload_refusal(bad) is not None
    with pytest.raises(AssertionError, match="construct"):
        event_line(bad)
