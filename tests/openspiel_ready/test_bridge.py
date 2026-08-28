"""Bridge — OpenSpiel readiness.

Depth 3: Bridge redeals the hand outright on a 4-pass "passed out" auction
(real rule), and the harness's greedy `_advance` (always `legal[0]`) always
picks "pass" first, so any depth >= 4 crosses into a *second* deal — a fresh
shuffle unrelated to the hands `on_first_decision` mutates (that hook always
fires at the game's very first-ever decision, i.e. deal #1). At depth >= 4
the swap was confirmed (field-by-field diff, see task-10 report) to change
ONLY P0's own re-shuffled `hand[0]` — hidden hands stayed `#13` in both
worlds and no opponent card identity appeared in the obs log — i.e. an
ill-posed experiment (mutated hands != examined hands), not a leak. Depth 3
stays inside deal #1, where the mutated hands and the examined hands
coincide, so the property is checked in the pre-play auction phase (this
seed's greedy policy never reaches trick play for bridge).

The delegated-trick probe (`test_a_delegated_decision_node_belongs_to_declarer`)
is this module's own reach past the greedy auction: it drives a bid line by
action id into trick play and pauses at dummy's turn, where the Delegated
Play surface this game witnesses (decisions.md "Delegated play") is asserted
at the node — the decision node is DECLARER's, every seat's information
state carries dummy's exposed identities, and the `chose` recall lands in
declarer's log while the played card still moves from dummy's zone.

Bounded conformance walk: the full `pyspiel.random_sim_test` measured 14s
locally (a rubber plays multiple deals to a target score — the same O(n^2)
re-simulation cost as Stud/French Tarot/Tichu, just a shorter game). This
game's full-game-to-TerminalNode coverage through the actual pyspiel `State`
wrapper lives in `test_openspiel_replay.py`'s KERNEL_GAMES list, so
bounding this walk drops no real coverage.
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_bridge", "bridge.cardlang", depth=3, conformance_steps=120)


# --- the delegated-trick probe -----------------------------------------------

from typing import Any

from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR

PATH = str(GAMES_DIR / "bridge.cardlang")


def _first(space: ActionSpace, legal: list[int], word: str) -> int:
    """The first legal action whose rendering carries `word`."""
    for aid in legal:
        if word in space.to_string(aid):
            return aid
    raise AssertionError(f"no legal action renders with {word!r}: "
                         f"{[space.to_string(a) for a in legal]}")


def test_a_delegated_decision_node_belongs_to_declarer() -> None:
    """Drive one bid and three passes into trick play, then walk the first
    trick to dummy's turn. At that pause the whole delegated surface shows at
    once: the node's player is DECLARER (the Decider), the offered candidates
    decode to cards of dummy's exposed hand, all four seats' information
    states carry those identities (the exposure movement is the observation),
    and applying the action lands the `chose` in declarer's log while the
    movement leaves dummy's zone. Seed 3 is from the shared manifest; the
    line is deterministic given the ids, so the probe is replayable."""
    _, space = load(PATH)
    seed = 3
    r: Any = run(PATH, seed, ())
    assert isinstance(r, DecisionNode)
    history = [_first(space, r.legal, "submit_bid")]
    for _ in range(3):
        r = run(PATH, seed, tuple(history))
        assert isinstance(r, DecisionNode)
        history.append(_first(space, r.legal, "pass"))
    # Into trick play. Phase-frame state (declarer/dummy) does not survive a
    # pause — run_phase's finally pops frames on the ChooserAbort unwind — so
    # both seats are read from the WORLD: dummy is the seat whose exposed
    # hand is populated, and declarer sits across (partners: [[0,2],[1,3]]).
    for _ in range(6):
        r = run(PATH, seed, tuple(history))
        assert isinstance(r, DecisionNode), "the bid line ended before a trick"
        populated = [
            (seat, r.rs.zones.instance("dummy_hand", seat))
            for seat in range(4)
            if r.rs.zones.instance("dummy_hand", seat).cards
        ]
        assert len(populated) == 1, (
            f"exactly one dummy_hand is populated in play; got "
            f"{[s for s, _ in populated]}"
        )
        dummy, exposed = populated[0]
        declarer = (int(dummy) + 2) % 4
        offered = {space.to_string(aid) for aid in r.legal}
        exposed_ids = {space.to_string(space.encode(c)) for c in exposed.cards}
        if offered <= exposed_ids:
            break  # every offered action is a card of dummy's exposed hand
        history.append(r.legal[0])
    else:
        raise AssertionError("no pause offered dummy's exposed hand within a trick")

    assert int(r.player) == declarer != int(dummy), (
        f"the delegated node's player is {r.player}; the Decider is declarer "
        f"{declarer} (dummy is {dummy})"
    )
    shown = sorted(str(c) for c in exposed.cards)
    for seat in range(len(r.obs_logs)):
        info = information_state(seat, r.rs, r.obs_logs[seat])
        missing = [c for c in shown if c not in info]
        assert not missing, (
            f"P{seat}'s information state lacks dummy's exposed {missing}"
        )
    history.append(r.legal[0])
    after: Any = run(PATH, seed, tuple(history))
    assert isinstance(after, DecisionNode)
    declarer_chose = [e for e in after.obs_logs[declarer] if e[0] == "chose"]
    dummy_moves = [e for e in after.obs_logs[dummy]
                   if e[0] == "move" and f"dummy_hand[{dummy}]" in str(e[1])]
    assert declarer_chose, "declarer holds no chose recall for the delegated draw"
    assert dummy_moves, "no movement left dummy's exposed hand"
