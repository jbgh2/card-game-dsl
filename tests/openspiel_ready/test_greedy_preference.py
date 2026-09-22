"""Every `greedy_prefers` is a measurement judgment with a CHECKED claim.

`GameSpec.greedy_prefers` names verbs the greedy line takes wherever a node
offers them, in place of `legal[0]`. Pinochle is the case that created the
field: `throw_in` sorts below `play_on`, so the plain line concedes every hand,
no side ever takes a trick point, each is set by its bid in turn as the deal
rotates the declarer, and the scores fall without bound — a line that neither
terminates nor plays a card.

`legal[0]` is a measurement policy, not a fact about the game, so the fix for
that belongs in the instrument (CLAUDE.md, "The game does not bend to the
harness"). But a preference can be wrong in ways the proofs it serves cannot
see. The adapter proof asks only "did the line reach TerminalNode within the
cap"; it cannot ask whether the preference was NEEDED, nor whether it names a
verb this game has at all — a verb the action space lacks matches nothing and
leaves the plain line in place, silently. Each of those is a cell below.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every registered game's `greedy_prefers` names verbs that game's
           action space encodes, and is declared exactly where the plain
           `legal[0]` line fails to reach TerminalNode within the game's own
           declared cap while the preferred line reaches it — and every one of
           those claims FAILS LOUDLY.
domain:    `harness.REGISTERED_GAMES` — the adapter's own registry, so a newly
           registered game is in-domain the day it registers — crossed with
           {declares a preference, declares none} (total by construction: the
           field is a tuple, empty or not) and with the two properties a
           declaration can get wrong: every verb it names must be one the game
           ENCODES, and the preference must be NEEDED (`preference_status`'s
           2x2 over needed x declared). The cap gate is the third arm: a game
           whose `adapter_terminal_steps` is None walks no bounded line, so
           "needed" has no measurement and a preference there steers only the
           perfect-recall walk, which is the one cell this module declares
           rather than measures.
registry:  `harness.REGISTERED_GAMES` for the game axis, resolved to each
           module's real `TestReadiness.spec` the way `test_coverage.py` and
           `test_provenance_openings.py` already resolve it (a
           default-constructed spec would read every field as its default and
           check nothing);
           `cardlang.openspiel.encoding.ActionSpace.verbs()` for what a verb
           name may be, consulted rather than re-listed here;
           `harness.greedy_line` for both measurements, so the line this module
           calls needed-or-not is the very line the adapter proof walks.
does not prove:  four things, each about what a green over the registered games
           leaves open.
           (a) The needed/declared square is measured at ONE seed, the manifest
           head. Whether a preference is needed is a property of the greedy
           line's SHAPE — which action id sorts first at each turn — and the
           deal moves neither the action ids nor the sort. Measured rather than
           argued for the one declaring game: over the whole manifest
           Pinochle's plain line is non-terminal and its preferred line is 76
           steps on every seed (2026-09-21). A game whose sort DID move with
           the deal would pass here on the head seed alone.
           (b) A preference naming SEVERAL verbs is implemented and only
           degenerately executed on a registered game: no spec declares more
           than one. The probe below drives the multi-verb arm on a synthetic
           spec.
           (c) A NEEDED BUT WRONG preference — a different verb that also makes
           the line terminate — passes every cell here, because every claim
           this module makes is about reaching TerminalNode and not about
           which line reached it. What the line is worth as coverage is the
           adapter proof's own business.
           (d) The perfect-recall walk also reads this field, and nothing here
           measures what it changes there: that walk is a fixed 40 steps with
           no termination claim, so it has no needed/stale square to check.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from .harness import (
    ONE_SEED,
    REGISTERED_GAMES,
    GameSpec,
    greedy_line,
    greedy_pick,
    preference_status,
)
from cardlang.openspiel.replay import load


def _spec(short_name: str) -> GameSpec:
    """The game's REAL spec, importlib-resolved. A default-constructed
    `GameSpec(short, filename)` reads every judgment field as its default and
    would check nothing — `test_provenance_openings.py` makes the same move for
    the same reason."""
    mod = importlib.import_module(
        ".test_" + short_name.removeprefix("cardlang_"), package=__package__
    )
    spec: GameSpec = mod.TestReadiness.spec
    return spec


_ALL: list[GameSpec] = [_spec(short) for short, _ in REGISTERED_GAMES]


def _params(specs: list[GameSpec]) -> list[Any]:
    return [pytest.param(s, id=s.short_name.removeprefix("cardlang_")) for s in specs]


SPECS: list[Any] = _params(_ALL)
# The two arms of the cap gate, DERIVED rather than listed: a game with no
# `adapter_terminal_steps` walks no bounded line, so the needed/declared square
# has nothing to measure and the gate cell owns it instead. Splitting the
# parametrization rather than skipping inside one keeps every cell a cell that
# runs.
WITH_CAP: list[Any] = _params([s for s in _ALL if s.adapter_terminal_steps is not None])
WITHOUT_CAP: list[Any] = _params([s for s in _ALL if s.adapter_terminal_steps is None])
SEED = ONE_SEED[0]


@pytest.mark.parametrize("spec", SPECS)
def test_a_declared_preference_names_verbs_the_game_encodes(spec: GameSpec) -> None:
    """A verb the action space lacks matches no candidate, so the line silently
    stays `legal[0]` and the declaration reads as doing work it never did.

    The empty arm asserts emptiness; the declared arm is checked against the
    space's own verb set.

    red under (executed 2026-09-21 and reverted): pinochle's `greedy_prefers`
    set to `("play_onn",)` — "cardlang_pinochle: `greedy_prefers` names
    ['play_onn'], which this game's action space does not encode".
    """
    _game, space = load(spec.path)
    unknown = sorted(set(spec.greedy_prefers) - set(space.verbs()))
    assert not unknown, (
        f"{spec.short_name}: `greedy_prefers` names {unknown}, which this "
        f"game's action space does not encode — it would match no candidate "
        f"and leave the plain line in place"
    )


@pytest.mark.parametrize("spec", WITH_CAP)
def test_a_preference_is_declared_exactly_where_the_greedy_line_needs_one(
    spec: GameSpec,
) -> None:
    """The needed/declared square, per game. `needed` is MEASURED: the plain
    line is walked with no preference and asked whether it reached TerminalNode
    within this game's own cap.

    The `stale` direction is the one nothing else in this package covers — the
    adapter proof stays green over a preference that stopped being necessary,
    because a line that terminates terminates either way.

    red under (executed 2026-09-21 and reverted): pinochle's `greedy_prefers`
    emptied — this cell reads `missing` and fails naming the game, alongside
    the adapter proof's own terminal assertion.
    """
    cap = spec.adapter_terminal_steps
    assert cap is not None  # the parametrization's own gate
    _plain, plain_returns = greedy_line(spec.path, seed=SEED, cap=cap, prefers=())
    status = preference_status(
        needed=plain_returns is None, declared=bool(spec.greedy_prefers)
    )
    assert status == ("covered" if spec.greedy_prefers else "none"), {
        "stale": (
            f"{spec.short_name} declares `greedy_prefers="
            f"{spec.greedy_prefers!r}`, but the plain `legal[0]` line already "
            f"reaches TerminalNode within adapter_terminal_steps={cap} — the "
            f"preference has outlived its reason; drop it"
        ),
        "missing": (
            f"{spec.short_name}: the plain `legal[0]` line does not reach "
            f"TerminalNode within adapter_terminal_steps={cap}, so the cap is "
            f"unmeetable — either declare a `greedy_prefers` that carries the "
            f"line past whatever settles it, or set the cap to None"
        ),
    }[status]


@pytest.mark.parametrize("spec", WITHOUT_CAP)
def test_an_uncapped_game_has_no_needed_square_to_check(spec: GameSpec) -> None:
    """The cap gate's other arm, asserted rather than skipped.

    A game with no `adapter_terminal_steps` walks no bounded line, so "did the
    plain line terminate" has no measurement and the square above is
    meaningless for it. What remains true is that a preference there still
    steers the perfect-recall walk — declaring one is legal, and this cell
    exists so that the uncapped games are counted rather than silently absent
    from the module's domain.
    """
    assert spec.adapter_terminal_steps is None  # the parametrization's own gate
    assert isinstance(spec.greedy_prefers, tuple)


# --- the arms no registered game executes ------------------------------------


def test_preference_status_covers_the_needed_declared_square() -> None:
    """All four cells of the 2x2, named. Two of them no registered game
    reaches: `stale` needs a game that declares a preference its plain line no
    longer needs, and `missing` a game whose cap is unmeetable without one —
    both are states the corpus is supposed never to be in, which is exactly why
    the classifier's own square is checked here rather than left to whichever
    game happens to be misdeclared.

    A classifier that collapsed `stale` into `covered` would let a preference
    outlive its reason silently, and one that collapsed `missing` into `none`
    would leave an unmeetable cap reading as a game that needs nothing."""
    assert preference_status(needed=True, declared=True) == "covered"
    assert preference_status(needed=False, declared=False) == "none"
    assert preference_status(needed=False, declared=True) == "stale"
    assert preference_status(needed=True, declared=False) == "missing"


class _Space:
    """The two methods `greedy_pick` reads, over a fixed id -> verb table."""

    def __init__(self, verbs: dict[int, str]) -> None:
        self._verbs = verbs

    def verb_of(self, aid: int) -> str:
        return self._verbs[aid]


def test_a_multi_verb_preference_takes_the_lowest_id_among_all_of_them() -> None:
    """`greedy_prefers` is a tuple, so a spec may name several verbs; no
    registered game does, which is ledger item (b).

    The rule is one rule at any width: among the candidates whose verb is
    preferred, the lowest id — never the first verb in the tuple's own order,
    which would make the declaration's ORDER load-bearing and silently
    unstated.
    """
    space = _Space({10: "settle", 11: "play_on", 12: "throw_in", 13: "play_on"})
    assert greedy_pick(space, [13, 12, 11, 10], ("play_on",)) == 11
    # Two preferred verbs present: the lowest id across both, not the tuple's
    # head. `throw_in` is named second and wins on id.
    assert greedy_pick(space, [13, 12], ("play_on", "throw_in")) == 12
    assert greedy_pick(space, [13, 12], ("throw_in", "play_on")) == 12


def test_a_preference_that_matches_nothing_here_leaves_the_plain_line() -> None:
    """The degradation is deliberate and total: a node offering none of the
    preferred verbs is `legal[0]`, which is what makes the field safe to
    declare on a game that offers its verb at one node in a hundred."""
    space = _Space({10: "settle", 11: "bid"})
    assert greedy_pick(space, [11, 10], ("play_on",)) == 10
    assert greedy_pick(space, [11, 10], ()) == 10
