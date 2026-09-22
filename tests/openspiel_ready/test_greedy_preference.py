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
           (b) Each declared verb is proved necessary INDIVIDUALLY, so a
           tuple cannot carry a passenger; what no cell proves is that the
           SET is sufficient in some minimal sense beyond that, since a pair
           of verbs neither of which is redundant can still be one of several
           pairs that work.
           (c) A NEEDED BUT WRONG preference — a different verb that also makes
           the line terminate — passes every cell here, because every claim
           this module makes is about reaching TerminalNode and not about
           which line reached it. What the line is worth as coverage is the
           adapter proof's own business.
           (d) The reach criterion reads one seed and the recall walk's own
           40-step bound, so a preference that buys reach only later, or only
           on another deal, reads as stale here.
           (e) For a game with NO cap that declares NO preference, nothing
           detects a preference it ought to have. Deciding that would mean
           searching the verb subsets for one that buys reach, which is not a
           measurement but a design question; the capped games get it free from
           the adapter proof's own terminal assertion. Pinochle sat in exactly
           this cell before the field existed.
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
from cardlang.openspiel.replay import DecisionNode, load, run

# The perfect-recall proof's own bound, which is the walk `greedy_prefers`
# steers for a game with no `adapter_terminal_steps`. Read from there rather
# than chosen here, so the reach criterion below measures the walk that
# actually exists.
RECALL_STEPS = 40


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


def _of(param: Any) -> GameSpec:
    """The spec inside a `pytest.param`, so a derived parametrization can filter
    on it without a second list of specs to keep in step."""
    spec: GameSpec = param.values[0]
    return spec


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

    red under (executed 2026-09-21 and reverted, while pinochle still carried a
    cap): its `greedy_prefers` emptied — this cell read `missing` and failed
    naming the game, alongside the adapter proof's own terminal assertion. No
    registered game carries both a cap and a preference today, so the cell runs
    over the capped games' `none` arm and the classifier's own square below
    carries the other three.
    """
    cap = spec.adapter_terminal_steps
    assert cap is not None  # the parametrization's own gate
    status = preference_status(
        needed=_needed(spec, ()), declared=bool(spec.greedy_prefers)
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


DECLARING: list[Any] = [s for s in SPECS if _of(s).greedy_prefers]


def _reaches(spec: GameSpec, prefers: tuple[str, ...]) -> frozenset[str]:
    """The verbs the bounded recall walk applies under `prefers`.

    The criterion for a game with no `adapter_terminal_steps`, where "did the
    line terminate" has no measurement: what a preference buys such a game is
    REACH — the walk that would otherwise stall in one stretch of the game gets
    past it. Bounded by the same 40 steps the perfect-recall proof walks, since
    that is the walk this field steers there.
    """
    _game, space = load(spec.path)
    verbs: set[str] = set()
    for seed in ONE_SEED:
        history: list[int] = []
        node = run(spec.path, seed, ())
        for _ in range(RECALL_STEPS):
            if not isinstance(node, DecisionNode):
                break
            aid = greedy_pick(space, list(node.legal), prefers)
            verbs.add(space.verb_of(aid))
            history.append(aid)
            node = run(spec.path, seed, tuple(history))
    return frozenset(verbs)


def _needed(spec: GameSpec, prefers: tuple[str, ...]) -> bool:
    """Whether the line is worse off without `prefers`, by whichever criterion
    this game's cap arm makes measurable."""
    cap = spec.adapter_terminal_steps
    if cap is not None:
        _line, returns = greedy_line(spec.path, seed=SEED, cap=cap, prefers=prefers)
        return returns is None
    return bool(_reaches(spec, spec.greedy_prefers) - _reaches(spec, prefers))


@pytest.mark.parametrize("spec", DECLARING)
def test_no_declared_verb_is_a_passenger(spec: GameSpec) -> None:
    """Each verb carries its own weight: dropping any ONE of them leaves a line
    that no longer reaches TerminalNode within the cap.

    The cell above proves the tuple as a whole is needed, which a tuple with a
    passenger passes — the passenger rides on its neighbour's necessity and
    nothing ever reads it. Pinochle declares two, so this arm runs on a
    registered game rather than a synthetic one.

    red under (executed 2026-09-21 and reverted): pinochle's `greedy_prefers`
    set to `("submit_bid",)` — "dropping 'submit_bid' ... leaves the line no
    worse off". Earlier, while pinochle still carried a cap, appending
    `"pass_with_help"` reddened it naming `pass` rather than the verb added:
    the two are interchangeable ways out of the auction, so adding one makes
    the OTHER the passenger. Which of a redundant pair is named is the loop's
    order; that one of them is redundant is the finding.
    """
    for verb in spec.greedy_prefers:
        without = tuple(v for v in spec.greedy_prefers if v != verb)
        assert _needed(spec, without), (
            f"{spec.short_name}: dropping {verb!r} from `greedy_prefers` leaves "
            f"the line no worse off, so it changes nothing — drop it, or "
            f"replace the whole declaration with the verbs that do the work"
        )


@pytest.mark.parametrize("spec", WITHOUT_CAP)
def test_an_uncapped_declaration_buys_reach(spec: GameSpec) -> None:
    """The cap gate's other arm. "Did the line terminate" has no measurement
    for a game with no `adapter_terminal_steps`, so what a preference must
    show there is REACH: verbs the bounded recall walk applies with it and
    would not without.

    red under (executed 2026-09-21 and reverted): pinochle's `greedy_prefers`
    set to `("submit_bid",)`, a verb `legal[0]` already takes — "the plain
    `legal[0]` walk already applies every verb the preferred one does".
    EMPTYING the field does NOT redden this cell, and that is ledger item (e)
    rather than a hole in the plant: with nothing declared there is no claim
    here to be wrong.
    """
    assert spec.adapter_terminal_steps is None  # the parametrization's own gate
    if not spec.greedy_prefers:
        return  # nothing declared, nothing to hold to account — ledger item (e)
    gained = _reaches(spec, spec.greedy_prefers) - _reaches(spec, ())
    assert gained, (
        f"{spec.short_name} declares `greedy_prefers={spec.greedy_prefers!r}` "
        f"but the plain `legal[0]` walk already applies every verb the "
        f"preferred one does — the preference has outlived its reason; drop it"
    )


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
