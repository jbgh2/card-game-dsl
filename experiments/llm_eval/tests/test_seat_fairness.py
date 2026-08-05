"""Seat fairness: no roster position may be dealt better cards than another.

The guarantee a head-to-head number in this harness rests on is that it compares
POLICIES, not access to better cards. Nothing checked that until a Kuhn run
reported a model beating an opponent that is provably unbeatable — seat rotation
and the deal were both functions of the game index, and the adapter's
seed-to-deal map is not balanced across seed parities (issue #233).

The check here is **exact, not statistical**, and does not play a single game.
Under balanced seating every deal is played in every seating, so across a whole
matchup each roster position sits in every seat of every deal exactly once — and
therefore sees an *identical multiset of dealt hands*. That is a property of the
seating scheme alone, so it can be asserted as equality rather than estimated
from outcomes.

That matters for how this generalises. Detecting the confound from RESULTS needed
an opponent whose value is known — Kuhn's equilibrium, where "+0.09 chips against
unbeatable" is a contradiction rather than a surprise. Hold'em has no such
oracle, so a results-based check there would see a seat advantage as the model
simply doing well. This check needs no oracle, no policy, and no sample size, so
it guards games that arrive later without their author having to know any of
this.

Contract
--------
Assumes: `metrics.GAME_KEYS` names every game the harness can run, and the
adapter renders a seat's own zones as `<zone>[<seat>]=[<cards>]`.
Establishes: for every such game, balanced seating deals each roster position the
same cards; and the unbalanced scheme demonstrably does not, so the check is a
filter rather than a tautology.
Illegal after: adding a game to the harness without it appearing here — the
parametrisation is derived from the registry, so a new game joins automatically.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pytest

from ..metrics import GAME_KEYS
from ..run_eval import seat_plan

pyspiel = pytest.importorskip("pyspiel", reason="needs the openspiel extra")

#: Deals per game. Small on purpose: the property is exact, so this is about
#: covering enough distinct deals that an accidental symmetry cannot hide an
#: imbalance — not about statistical power, of which none is needed.
DEALS = 24

_OWN_ZONE = r"\w+\[{seat}\]=\[([^\]]*)\]"


def _cards_of(state: Any, seat: int) -> tuple[str, ...]:
    """Every card `seat` can identify in its own zones at the root.

    Read from that seat's OWN information state, so it is exactly what the seat
    was entitled to see of its own deal — the same artifact the leak-freeness
    argument covers. Zone-name agnostic: any `<zone>[<seat>]=[...]` counts, so a
    game whose private zone is called `pocket` rather than `hand` is covered
    without this file naming it.
    """
    zones = state.information_state_string(seat).split("|state:")[0]
    cards: list[str] = []
    for chunk in re.findall(_OWN_ZONE.format(seat=seat), zones):
        cards.extend(card for card in chunk.split(",") if card)
    return tuple(sorted(cards))


def _hands_per_deal(game: Any, seed: int, num_players: int) -> list[tuple[str, ...]]:
    state = game.new_initial_state()
    state.apply_action(seed)
    return [_cards_of(state, seat) for seat in range(num_players)]


def _by_roster_position(
    game: Any, num_players: int, balanced: bool
) -> list[Counter[tuple[str, ...]]]:
    """What each roster position is dealt, over a whole matchup.

    Mirrors `run_eval`: the roster fills in order around the table from the focus
    seat, so entry `k` sits at `(focus + k) % num_players`.
    """
    games = DEALS * num_players
    cache: dict[int, list[tuple[str, ...]]] = {}
    seen: list[Counter[tuple[str, ...]]] = [Counter() for _ in range(num_players)]
    for index in range(games):
        offset, focus = seat_plan(index, num_players, rotate=True, balanced=balanced)
        hands = cache.setdefault(offset, _hands_per_deal(game, offset, num_players))
        for position in range(num_players):
            seen[position][hands[(focus + position) % num_players]] += 1
    return seen


@pytest.fixture(scope="module", params=sorted(GAME_KEYS))
def loaded(request: Any) -> tuple[str, Any]:
    from ..referee import load_game

    return request.param, load_game(request.param)


def test_balanced_seating_deals_every_roster_position_the_same_cards(
    loaded: tuple[str, Any],
) -> None:
    """The property, stated exactly.

    Every roster position sees every seat of every deal exactly once, so the
    multisets are equal — not merely close. An imbalance of a single hand fails
    this, which is why it needs no sample size and no opponent of known value.
    """
    short_name, game = loaded
    num_players = game.num_players()
    if num_players < 2:
        pytest.skip(f"{short_name} is single-seat; rotation cannot favour anyone")

    seen = _by_roster_position(game, num_players, balanced=True)
    assert sum(seen[0].values()), (
        f"{short_name}: no hands were extracted, so this check passed without "
        f"examining anything. The adapter's zone rendering has changed, or the "
        f"game deals no cards — either way `_cards_of` needs to say so."
    )
    for position in range(1, num_players):
        assert seen[position] == seen[0], (
            f"{short_name}: roster position {position} is dealt a different "
            f"multiset of hands from position 0 under BALANCED seating, which "
            f"should be impossible — every position sits in every seat of every "
            f"deal exactly once. See issue #233."
        )


def test_the_unbalanced_scheme_really_does_favour_a_position(
    loaded: tuple[str, Any],
) -> None:
    """The non-vacuity half, and the reason the flag exists.

    Without this, a harness in which the two schemes happened to agree would pass
    the check above while proving nothing. Under the coupled scheme the seat is a
    function of the seed, so roster position 0 sees seat `i % P` of deal `i` while
    position 1 sees seat `(i+1) % P` — different multisets, and the imbalance the
    Kuhn run measured as a King held 112 times to the baseline's 97.

    This asserts the DEFECT is present in the old scheme, so it is the one test
    here that would go red if someone "fixed" the default. That is intended: the
    default is deliberate for Cheat (issue #233 records why), and changing it
    should require changing this test on purpose.
    """
    short_name, game = loaded
    num_players = game.num_players()
    if num_players < 2:
        pytest.skip(f"{short_name} is single-seat; rotation cannot favour anyone")

    seen = _by_roster_position(game, num_players, balanced=False)
    assert any(seen[position] != seen[0] for position in range(1, num_players)), (
        f"{short_name}: the unbalanced scheme deals every roster position the "
        f"same cards, so the balanced check cannot tell the two schemes apart "
        f"and is proving nothing about either."
    )


def test_every_harness_game_is_covered() -> None:
    """The parametrisation is derived from the registry, not written down.

    A game added to `GAME_KEYS` is seat-checked without anyone remembering to add
    it here — which is the whole point, since the confound this guards against is
    exactly what a new game's author would not know to look for.
    """
    from .. import agents

    assert set(GAME_KEYS.values()) == set(agents.GAME_TEXT), (
        "the metrics registry and the rules-text registry name different games; "
        "one of them would be running unchecked"
    )
    assert len(GAME_KEYS) >= 2, (
        "with one game this parametrisation cannot show it generalises"
    )
