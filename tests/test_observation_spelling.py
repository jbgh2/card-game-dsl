"""Every Observation Event a seat is delivered, along the whole line, spelled
as the information state spells it, pinned per game and seed.

The information-state string embeds each seat's Observation Log verbatim, each
event by the `repr` of its spelling (`spelled()`, read by
`infostate.render_information_state`), so an event's spelling is part of the string OpenSpiel keys on, at every position and not
only the first. tests/golden/infostate_format.json holds that string byte for
byte at each game's first decision; this module holds the spelling of every
event a seat is delivered on the whole line. It is the oracle the
Observation-boundary parts are measured against (ADR-0026): a part that moves
where an event is made, or what type carries it, claims that no seat's log
changes, and this golden is what that claim fails against.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        for every game and seed of the domain, the sequence of
                 (seat, `repr` of the event's `spelled()`) pairs `Ctx.observe`
                 delivers over a whole
                 played line hashes to the value captured in
                 tests/golden/observation_spelling.json.
domain:          every game in the adapter registry
                 (`cardlang.openspiel.registry.GAMES`, derived from
                 `docs/games/*.cardlang` by glob), plus `WITNESSES` below,
                 crossed with `SEEDS`, played by `play_game` under
                 `random_chooser` from the seed's generator.
registry:        `GAMES`; `WITNESSES`, one row per emission site the corpus
                 does not reach, naming the site; the golden, regenerated with
                 `CARDLANG_UPDATE_SPELLING_GOLDEN=1` -- only on a tree whose
                 spelling is meant to move, and never to quiet a diff.
held by:         Born-Green Pin. The capture was taken on the tree before any
                 Observation-boundary part moved emission, so its provenance
                 is the git log.
does not prove:  that a line outside `SEEDS` spells the same, or that an
                 emission site no game and no witness reaches is unchanged;
                 that the spelling is the right one (it was captured, not
                 designed); anything about the zone and state parts of the
                 information-state string, which the infostate golden and the
                 proofs under tests/openspiel_ready/ hold. Which sites a line
                 reaches is a measurement, not a guarantee: the corpus reaches
                 every `observe.movement` site except the filtered
                 as-equally-as-possible deal, which `WITNESSES` covers.
red under:       respelling one kind -- the `move` tuple's two labels
                 swapped in `observe.movement` -- reddens every row that
                 delivers a movement (executed 2026-11-15, before the first
                 Observation-boundary part: all 37 corpus rows and the witness
                 at seed 0).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.registry import GAMES
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.observe import ObservationEvent
from cardlang.runtime.values import Player

REPO = Path(__file__).parent.parent
GAMES_DIR = REPO / "docs" / "games"
GOLDEN = REPO / "tests" / "golden" / "observation_spelling.json"
BLESS = os.environ.get("CARDLANG_UPDATE_SPELLING_GOLDEN") == "1"

SEEDS: tuple[int, ...] = (0, 1, 2)

# An emission site no corpus game reaches, each as the smallest game that
# reaches it, keyed by the site it witnesses.
WITNESSES: dict[str, str] = {
    "witness_filtered_equal_deal": """
game FilteredEqualDeal {
  players: 2
  max_length: 20
  cards: standard52
  ranking: aces high
  zones {
    deck          : Deck
    hand[player]  : Hand<player>
    shown[player] : PublicHand<player>
  }
  state {
    score[player] : Integer = 0
  }
  phase deal {
    shuffle deck
    deal all cards from deck where card.suit is hearts as-equally-as-possible to each hand
  }
  phase showdown {
    each player simultaneously:
      move chosen 1 card from hand[player] to shown[player]
    let a = sum of rank_value(card) over cards in shown[0]
    let b = sum of rank_value(card) over cards in shown[1]
    if a > b { score[0] += 1 } else { score[1] += 1 }
  }
  winner: highest score
}
""",
}


def _game(name: str) -> n.Game:
    if name in WITNESSES:
        return check_dsl(WITNESSES[name], f"{name}.cardlang")
    return check_source(GAMES_DIR / GAMES[name])


def _digest(name: str, seed: int) -> str:
    rng = random.Random(seed)
    delivered: list[tuple[Player, ObservationEvent]] = []

    def observer(player: Player, event: ObservationEvent) -> None:
        delivered.append((player, event))

    play_game(_game(name), rng, lambda _name, _data: None, random_chooser(rng), observer=observer)
    rendering = "\n".join(f"{p} {event.spelled()!r}" for p, event in delivered)
    return hashlib.sha256(rendering.encode("utf-8")).hexdigest()


def _names() -> list[str]:
    return sorted(GAMES) + sorted(WITNESSES)


def _load() -> dict[str, dict[str, str]]:
    data = json.loads(GOLDEN.read_text())
    assert isinstance(data, dict)
    return {str(g): {str(s): str(h) for s, h in row.items()} for g, row in data.items()}


def _cells() -> list[Any]:
    return [
        pytest.param(name, seed, id=f"{name}-{seed}", marks=() if seed == SEEDS[0] else pytest.mark.slow)
        for name in _names()
        for seed in SEEDS
    ]


@pytest.mark.skipif(not BLESS, reason="regenerates the golden only when asked")
def test_regenerate_the_golden() -> None:
    GOLDEN.write_text(
        json.dumps(
            {name: {str(seed): _digest(name, seed) for seed in SEEDS} for name in _names()},
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )


@pytest.mark.parametrize(("name", "seed"), _cells())
def test_every_delivered_event_is_spelled_as_captured(name: str, seed: int) -> None:
    if BLESS:
        pytest.skip("blessing")
    expected = _load()[name][str(seed)]
    assert _digest(name, seed) == expected, (
        f"{name} at seed {seed}: the Observation Events its seats are delivered "
        "no longer spell as captured, so the information-state string past the "
        "first decision has moved"
    )


def test_the_golden_covers_the_domain() -> None:
    """The golden names exactly the registry's games and the witnesses, each at
    exactly `SEEDS`, so a game added to the corpus without a capture, or a
    stale row, is red rather than unchecked."""
    if BLESS:
        pytest.skip("blessing")
    golden = _load()
    assert set(golden) == set(_names())
    assert all(set(row) == {str(s) for s in SEEDS} for row in golden.values())
