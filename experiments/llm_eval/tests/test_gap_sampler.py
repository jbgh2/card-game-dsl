"""The literal-posterior sampler, against oracles that can disagree with it.

Five of the checks here are execution oracles rather than assertions about the
sampler's internals, because an estimator's defect is a number that is quietly
wrong:

1. **A closed form.** At the opening window nothing has happened yet, so the
   posterior is `1 - C(4-j, c) / C(39, c)` for an observer holding `j` of the
   claimed rank against a claim of `c` cards. Swept over deals that give
   several values of `j`.
2. **A naive sampler.** Label all thirty-nine hidden deal positions by one
   uniform permutation, choose every hidden play uniformly, reject on any
   violated observation — trivially uniform over consistent worlds, and
   hopeless past a few constraints. On a short line it is the oracle the
   weighted sampler answers to.
3. **The provable subset.** Where `infostate.provably_false` fires, every
   consistent world is a lie, so the estimate is exactly 1.0.
4. **Information-state measurability.** Two lines whose observer sees the same
   bytes and whose ground truths differ estimate identically — the executable
   form of the guarantee that makes the comparison belief-vs-belief.
5. **The replay.** Every accepted world is materialized, injected as a deal,
   replayed through the engine, and required to render the observer the same
   information state with the same legal actions. A world that fails is not
   one of the worlds the observer cannot rule out.

The negative controls matter as much: a sweep that covers one `j`, a naive
sampler that accepts nothing, and a replay check that passes a wrong world are
each a green that proves nothing, so each has its own assertion.
"""

from __future__ import annotations

import ast
import inspect
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from .. import gap_sampler as gs
from ..agents import DecisionView, RuleAgent
from ..gap_replay import ENGINE_IMPORTS, make_checker
from ..infostate import decision_kind, parse, parse_events, provably_false, rank_of
from ..referee import load_game, play_game, replay_views
from .test_prompt_purity import ENGINE_ROOTS, _canonical, _graph

#: The corpus game this sampler is written against, and the file the replay
#: check drives. Derived from this module's own location so the tests do not
#: depend on the working directory.
REPO_ROOT = Path(__file__).resolve().parents[3]
CHEAT = str(REPO_ROOT / "docs" / "games" / "cheat.cardlang")

#: The oracle of test 2: one uniform labelling of every hidden deal position up
#: front, no lookahead, and rejection as the only mechanism. Every accepted
#: sample carries the same weight, so its estimate is a plain frequency — which
#: is what makes it an oracle rather than a second implementation of the thing
#: under test.
NAIVE = gs.Proposal(label_up_front=True, lookahead=False)

WINDOW = ["allow", "call_cheat"]


@pytest.fixture(scope="module")
def game() -> Any:
    pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")
    return load_game("cardlang_cheat")


# --- driving specific lines --------------------------------------------------


@dataclass
class ScriptedAgent:
    """A seat with no policy of its own: every decision is read off the script.

    `counts` gives the claimed count of this seat's successive plays (a play
    past the end of the list claims every card of the cycle's rank it holds, or
    one card when it holds none); `challenges` names the ordinals of this
    seat's own challenge windows at which it calls "Cheat!"; `bluffs` names the
    ordinals of its own plays whose cards avoid the claimed rank even when it
    holds that rank.

    Scripted rather than seeded because these tests need a NAMED line — a flip
    here, a pile pickup there — and a probability cannot name one.
    """

    counts: tuple[int, ...] = ()
    challenges: frozenset[int] = frozenset()
    bluffs: frozenset[int] = frozenset()
    name: str = "scripted"
    windows_seen: int = 0
    plays_made: int = 0

    def choose(self, view: DecisionView) -> int:
        info = parse(view.infostate)
        kind = decision_kind(view.legal_strings)
        if kind == "window":
            ordinal = self.windows_seen
            self.windows_seen += 1
            want = "call_cheat" if ordinal in self.challenges else "allow"
            return view.legal_actions[view.legal_strings.index(want)]
        if kind == "announce":
            return view.legal_actions[0]
        if kind == "count":
            ordinal = self.plays_made
            self.plays_made += 1
            count = (
                self.counts[ordinal]
                if ordinal < len(self.counts)
                else max(1, info.count_of_rank(info.claim_rank))
            )
            return view.legal_actions[view.legal_strings.index(str(count))]
        pool = view.legal_strings
        truthful = [c for c in pool if rank_of(c) == info.claim_rank]
        lying = (self.plays_made - 1) in self.bluffs
        if truthful and not lying:
            pick = truthful[0]
        else:
            junk = [c for c in pool if rank_of(c) != info.claim_rank]
            pick = (junk or pool)[0]
        return view.legal_actions[pool.index(pick)]

    def pop_trace(self) -> dict[str, Any]:
        return {}


def _seats(*agents: Any) -> dict[int, Any]:
    return dict(enumerate(agents))


def _views(
    game: Any, seed: int, seats: dict[int, Any], *, max_decisions: int = 0
) -> tuple[list[str], list[DecisionView]]:
    """Play one line and reconstruct every decision's view.

    Returns the recorded action strings beside the views, so a test can name
    the ground truth of a play whose cards the observer never saw.
    """
    record = play_game(
        game,
        seats,
        seed=seed,
        matchup="gap_sampler",
        game_index=0,
        max_decisions=max_decisions,
    )
    return [d.action for d in record.decisions], replay_views(game, seed, record.history)


def _windows(views: list[DecisionView]) -> list[tuple[int, DecisionView]]:
    return [(i, v) for i, v in enumerate(views) if v.legal_strings == WINDOW]


def _has_flip(infostate: str) -> bool:
    return any(
        e[0] == "move" and e[3] == "flipped" for e in parse_events(parse(infostate).obs)
    )


def _has_own_pickup(infostate: str) -> bool:
    info = parse(infostate)
    own = f"hand[{info.player}]"
    return any(
        e[0] == "move" and e[1] == "pile" and e[3] == own and isinstance(e[4], tuple)
        for e in parse_events(info.obs)
    )


# --- 1. the closed form at the opening window --------------------------------

#: Deals whose seat-1 ace counts differ — the axis the closed form is swept
#: over. `test_the_closed_form_sweep_is_not_vacuous` holds them to that.
OPENING_SEEDS = (0, 1, 3, 13, 22)


def _opening_window(game: Any, seed: int, count: int) -> DecisionView:
    _, views = _views(
        game,
        seed,
        _seats(
            ScriptedAgent(counts=(count,)),
            ScriptedAgent(),
            ScriptedAgent(),
            ScriptedAgent(),
        ),
        max_decisions=count + 3,
    )
    view = views[count + 2]
    assert view.legal_strings == WINDOW and view.player == 1
    return view


def _opening_closed_form(view: DecisionView) -> float:
    info = parse(view.infostate)
    held = info.count_of_rank(info.claim_rank)
    return 1.0 - math.comb(4 - held, info.claim_count) / math.comb(39, info.claim_count)


@pytest.mark.parametrize("seed", OPENING_SEEDS)
@pytest.mark.parametrize("count", [1, 2, 3])
def test_the_opening_window_matches_the_closed_form(
    game: Any, seed: int, count: int
) -> None:
    """No event has constrained anything yet, so the posterior is a ratio of
    binomials over the thirty-nine cards the observer does not hold.

    Asserted to floating-point equality, not to a Monte Carlo tolerance: the
    labelling of the standing play is integrated analytically over the
    remaining identities rather than sampled, so at a window with no prior
    reveal every sample reports the same conditional and the estimator is
    exact. The tolerance the sample count would justify (three standard errors
    of a Bernoulli mean at n=64, about 0.19) is asserted too — it is the
    criterion the design states, and a change that makes the estimate merely
    approximate here must still meet it.
    """
    view = _opening_window(game, seed, count)
    expected = _opening_closed_form(view)
    est = gs.estimate(view.infostate, seed=11, samples=64)
    assert est.n_accepted == est.n_proposed, "nothing constrains the opening window"
    assert abs(est.p_lie - expected) <= 0.19
    assert est.p_lie == pytest.approx(expected, abs=1e-12)


def test_the_closed_form_sweep_is_not_vacuous(game: Any) -> None:
    """The swept deals really do differ in the observer's own holding, and the
    expected answers are not all certainty.

    Without this, a sweep over five deals that all gave `j = 0` would read as
    coverage of the formula while exercising one cell of it.
    """
    held = set()
    answers = set()
    for seed in OPENING_SEEDS:
        view = _opening_window(game, seed, 2)
        held.add(parse(view.infostate).count_of_rank("A"))
        answers.add(_opening_closed_form(view))
    assert len(held) >= 3, f"the sweep covers only {held} of the claimed rank"
    assert any(answer < 1.0 for answer in answers)


# --- 2. the naive oracle ------------------------------------------------------


def _flip_and_pickup_line(game: Any) -> DecisionView:
    """A short line carrying both labelling events, and a window after them.

    Seat 0 opens with one card, which nobody challenges, so it lies unseen in
    the pile. Seat 1 then plays its single two truthfully and seat 2 — the
    observer — challenges: the flip names seat 1's card to the whole table, the
    honest claim sends the flipped card AND the pile into the wrong
    challenger's own hand, and that pickup names seat 0's opening card too.
    Seat 2 plays, seat 3 plays, and seat 2 is offered the window on it.
    """
    _, views = _views(
        game,
        0,
        _seats(
            ScriptedAgent(counts=(1,)),
            ScriptedAgent(counts=(1,)),
            ScriptedAgent(challenges=frozenset({1})),
            ScriptedAgent(counts=(1,)),
        ),
        max_decisions=24,
    )
    view = next(
        v
        for _, v in _windows(views)
        if v.player == 2 and _has_flip(v.infostate) and _has_own_pickup(v.infostate)
    )
    info = parse(view.infostate)
    assert info.claimant == 3 and info.claim_rank == "4"
    return view


def test_the_naive_sampler_agrees_with_the_weighted_one(game: Any) -> None:
    """Two estimators of the same posterior, sharing no proposal.

    The naive one is uniform over consistent worlds by construction and needs
    no weights; the weighted one proposes with lookahead and corrects. They
    answer the same question, so they must answer it alike — and the naive
    acceptance count is asserted, because a naive sampler that accepted nothing
    would agree with anything.
    """
    view = _flip_and_pickup_line(game)
    smart = gs.estimate(view.infostate, seed=3, samples=256)
    naive = gs.estimate(view.infostate, seed=5, samples=40_000, proposal=NAIVE)
    assert naive.n_accepted >= 100, (
        f"the naive oracle accepted {naive.n_accepted} of {naive.n_proposed} "
        f"proposals — too few to be an oracle"
    )
    assert 0.0 < smart.p_lie < 1.0, "a degenerate window proves nothing about agreement"
    tolerance = 4.0 * math.sqrt(0.25 / naive.n_accepted)
    assert abs(smart.p_lie - naive.p_lie) <= tolerance


def test_dropping_the_lookahead_leaves_the_answer_alone(game: Any) -> None:
    """A third proposal, weighted like the first but blind: it chooses hidden
    plays from the whole hand and rejects what the reveals contradict.

    Where the smart proposal's eligible sets differ from the blind one's, the
    two runs' importance weights differ — so this is the check that the weights
    are computed from the proposal that was actually used, on a real line
    rather than a constructed one.
    """
    view = _flip_and_pickup_line(game)
    smart = gs.estimate(view.infostate, seed=3, samples=256)
    blind = gs.estimate(
        view.infostate, seed=4, samples=2_000, proposal=gs.Proposal(lookahead=False)
    )
    assert blind.n_accepted >= 100
    tolerance = 4.0 * math.sqrt(0.25 / blind.ess)
    assert abs(smart.p_lie - blind.p_lie) <= tolerance


# --- 3. the provable subset ---------------------------------------------------


def _rule_line(
    game: Any, seed: int, *, max_decisions: int = 200
) -> tuple[list[str], list[DecisionView]]:
    return _views(
        game,
        seed,
        {p: RuleAgent(seed=100 * seed + p, bluff_prob=0.35) for p in range(4)},
        max_decisions=max_decisions,
    )


def test_a_provable_lie_is_certain(game: Any) -> None:
    """Where the observer's own cards plus the public flip record already
    disprove the claim, no consistent world makes it true — so the estimate is
    exactly 1.0 and every accepted sample says so."""
    found = 0
    for seed in range(6):
        _, views = _rule_line(game, seed, max_decisions=150)
        for _, view in _windows(views):
            info = parse(view.infostate)
            if not provably_false(info, info.claim_rank, info.claim_count):
                continue
            est = gs.estimate(view.infostate, seed=17, samples=32)
            assert est.p_lie == 1.0, f"a provable lie estimated at {est.p_lie}"
            for sample in gs.draw(view.infostate, seed=17, samples=32):
                if sample.reject is None:
                    assert sample.p_lie == 1.0
            found += 1
            if found == 4:
                return
    assert found >= 1, "no provable-lie window in the swept lines — the check is vacuous"


# --- 4. information-state measurability --------------------------------------


def test_one_information_state_gives_one_estimate_whatever_was_played(
    game: Any,
) -> None:
    """The same seed, the same claim, a different card under it.

    Seat 0 holds two aces at this deal, so it can open with one card that is an
    ace or one that is not; the count is announced either way and the card is
    not, so seat 1's information state is byte-identical and the ground truth
    is opposite. The estimate cannot tell them apart — which is the point: a
    sampler that read the history's action ids instead of the string would
    return 0.0 and 1.0 here, and that is the decode-pin leak this asserts the
    absence of.
    """
    honest = _seats(
        ScriptedAgent(counts=(1,)), ScriptedAgent(), ScriptedAgent(), ScriptedAgent()
    )
    lying = _seats(
        ScriptedAgent(counts=(1,), bluffs=frozenset({0})),
        ScriptedAgent(),
        ScriptedAgent(),
        ScriptedAgent(),
    )
    truth_actions, truth_views = _views(game, 0, honest, max_decisions=4)
    lie_actions, lie_views = _views(game, 0, lying, max_decisions=4)
    assert rank_of(truth_actions[2]) == "A"
    assert rank_of(lie_actions[2]) != "A"

    a, b = truth_views[3].infostate, lie_views[3].infostate
    assert a == b, "the two lines are distinguishable — the test's premise is gone"
    assert gs.estimate(a, seed=9, samples=48) == gs.estimate(b, seed=9, samples=48)


# --- 5. the replay ------------------------------------------------------------


def _deep_windows(game: Any, seed: int) -> list[tuple[int, DecisionView]]:
    _, views = _rule_line(game, seed, max_decisions=220)
    return _windows(views)


def test_every_accepted_world_replays_to_the_same_information_state(
    game: Any,
) -> None:
    """The safety net: a sampled world is injected as a deal, its reconstructed
    action line is replayed, and the observer's rendered information state must
    come back byte-identical with the same legal actions.

    Run at the opening window, at the first window past a flip, at the first
    past a pickup into the observer's own hand, and as deep as the line goes —
    so the structure the sampler invents is checked where it has had the most
    room to go wrong.
    """
    windows = _deep_windows(game, 3)
    assert windows, "no window in the line"
    by_depth = {
        "opening": windows[0],
        "flip": next(w for w in windows if _has_flip(w[1].infostate)),
        "pickup": next(w for w in windows if _has_own_pickup(w[1].infostate)),
        "deepest": windows[-1],
    }
    for name, (depth, view) in by_depth.items():
        checker = make_checker(view.infostate, CHEAT, legal=view.legal_actions)
        est = gs.estimate(
            view.infostate, seed=depth, samples=8, check=checker, check_count=3
        )
        assert est.n_checked == 3, f"{name} at depth {depth}: {est}"


def test_the_replay_check_refuses_a_world_the_observer_can_see_is_wrong(
    game: Any,
) -> None:
    """The negative control on the net above.

    Swapping two cards between the observer's own hand and another seat's
    changes what the observer is dealt, so the replayed information state
    cannot match. A check that passed this would pass anything.
    """
    windows = _deep_windows(game, 3)
    depth, view = next(w for w in windows if _has_flip(w[1].infostate))
    sample = next(
        s
        for s in gs.draw(view.infostate, seed=depth, samples=8, materialize=True)
        if s.world is not None
    )
    world = sample.world
    assert world is not None
    observer = parse(view.infostate).player
    other = next(p for p in range(4) if p != observer)
    deal = [list(hand) for hand in world.deal]
    deal[observer][0], deal[other][0] = deal[other][0], deal[observer][0]
    wrong = replace(world, deal=tuple(tuple(hand) for hand in deal))
    checker = make_checker(view.infostate, CHEAT, legal=view.legal_actions)
    with pytest.raises((AssertionError, ValueError)):
        checker(wrong)


# --- 6. purity, and the deck the sampler assumes -----------------------------


def test_the_sampler_never_reaches_the_engine() -> None:
    """No chain of imports leads from `gap_sampler` to the engine.

    The estimator's claim is that it is a function of the information-state
    string; the string is the only input it has if the engine is not reachable
    from it at all. Same graph, same helpers as the play harness's leak-freeness
    pin — a second derivation of Python's import resolution is exactly what
    that module records as having cost five defects.
    """
    graph = _graph()
    entry = _canonical(gs)
    assert entry in graph.modules, f"{entry} is absent from the import graph"
    for engine in sorted(ENGINE_ROOTS):
        if engine not in graph.modules:
            continue
        chain = graph.find_shortest_chain(importer=entry, imported=engine)
        assert chain is None, f"the sampler can reach the engine: {' -> '.join(chain)}"


def test_the_replay_check_imports_only_the_replay_seam() -> None:
    """The checker is the one module here that must reach the engine, and it
    reaches exactly two of its modules.

    Read off the source rather than the import graph, because the claim is
    about which seam this code is written against: the re-simulation entry
    point and the information-state renderer, and nothing else — no runtime
    internals, no adapter, no `pyspiel`.
    """
    from .. import gap_replay

    source = Path(inspect.getsourcefile(gap_replay) or "").read_text(encoding="utf-8")
    reached = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            reached.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            reached.add(node.module)
    engine = {m for m in reached if m.split(".")[0] in ENGINE_ROOTS}
    assert engine == set(ENGINE_IMPORTS), f"the checker imports {sorted(engine)}"


def test_the_deck_is_the_engines() -> None:
    """The hidden pool is the deck minus what the observer holds, so the
    sampler needs the deck's renderings — held as a literal, like
    `infostate.RANKS`, and reconciled here so a deck change reddens instead of
    silently shrinking the pool."""
    values = pytest.importorskip("cardlang.runtime.values")
    assert set(gs.DECK) == {str(c) for c in values.build_deck("standard52")}
    assert len(gs.DECK) == 52


# --- misuse probes -----------------------------------------------------------


def test_a_decision_that_is_not_a_window_is_refused(game: Any) -> None:
    """The posterior is about a standing claim. Asked at a count decision or a
    card decision — where a claim is being assembled, not standing — the
    sampler raises rather than answering about whatever `played` happens to
    hold."""
    _, views = _views(
        game,
        0,
        _seats(
            ScriptedAgent(counts=(2,)),
            ScriptedAgent(),
            ScriptedAgent(),
            ScriptedAgent(),
        ),
        max_decisions=4,
    )
    for view in views[:3]:  # play_cards, the count, the first card
        assert view.legal_strings != WINDOW
        with pytest.raises(ValueError, match="window"):
            gs.estimate(view.infostate, seed=1, samples=4)


def test_an_unreadable_observation_log_is_refused() -> None:
    """An event the walk does not model stops the estimate rather than being
    skipped. A dropped event is a silently wrong posterior — the same
    unsoundness-by-omission `infostate.parse_events` refuses."""
    view = (
        "P1|deck=#0;flipped=[];pile=#0;played=#1;hand[0]=#12;"
        "hand[1]=[A♣];hand[2]=#13;hand[3]=#13"
        "|state:challenged=False;challenger=None;claim_count=1;claim_rank=A;"
        "claimant=0;responder=1;window_open=True;won={0:False}"
        "|obs:('reveal', 'pile', 'A♥')"
    )
    with pytest.raises(ValueError, match="reveal"):
        gs.estimate(view, seed=1, samples=4)


def test_a_checker_with_nothing_to_check_is_refused(game: Any) -> None:
    """`check_count` without a checker is a request to replay nothing, and a
    run that recorded `n_checked=0` while asking for checks would read as
    checked."""
    view = _opening_window(game, 0, 1)
    with pytest.raises(ValueError, match="check"):
        gs.estimate(view.infostate, seed=1, samples=4, check_count=2)
