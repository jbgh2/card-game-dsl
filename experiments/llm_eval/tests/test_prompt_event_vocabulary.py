"""Every event a seat's log can carry is one its own prompt explains.

property:        For each game the rig runs, the raw arm's static guide names
                 every observation-event kind that game actually emits. A model
                 handed a tuple its guide does not describe is reading
                 undocumented data, and the run records a treatment fingerprint
                 that says the prompt is unchanged.
domain:          The games are the rows of `agents.GAME_TEXT`, which is the
                 registry mapping a rig game to its raw and rendered guides.
                 The kinds are what each game EMITS along a seeded line, not
                 every kind the engine declares — a guide owes no sentence about
                 an event its game never produces.
registry:        the games and their guides,
                 `experiments.llm_eval.agents.GAME_TEXT`; the declared kinds,
                 `cardlang.runtime.observe.EVENT_PAYLOADS`; the games' sources,
                 `cardlang.openspiel.registry.GAMES`.
does not prove:  That a guide's sentence about a kind is CORRECT, only that it
                 names it — prose accuracy is nobody's matcher. Nor that the
                 rendered arm covers them: a renderer turns the log into
                 English and the raw tuple never reaches that prompt.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from cardlang.openspiel.registry import GAMES
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from experiments.llm_eval.agents import GAME_TEXT

REPO = Path(__file__).resolve().parents[3]

# Each rig game and the corpus game it plays. Authored, and the cell below
# proves it covers every row of the guide registry, so a rig game added
# without one fails rather than going unchecked.
RIG_TO_CORPUS: dict[str, str] = {
    "cheat": "cardlang_cheat",
    "kuhn": "cardlang_kuhn_poker",
    "holdem_hu": "cardlang_holdem_heads_up",
}


def test_every_rig_game_names_the_corpus_game_it_plays() -> None:
    """red under: add a row to `agents.GAME_TEXT` without one here."""
    assert set(RIG_TO_CORPUS) == set(GAME_TEXT)
    assert set(RIG_TO_CORPUS.values()) <= set(GAMES)


def _kinds_emitted(corpus_key: str, seed: int = 7) -> set[str]:
    game = check_source(REPO / "docs" / "games" / GAMES[corpus_key])
    rng = random.Random(seed)
    kinds: set[str] = set()
    try:
        play_game(game, rng, observer=lambda _p, e: kinds.add(str(e[0])))
    except Exception:  # noqa: BLE001 - a line that ends early still emitted
        pass
    return kinds


@pytest.mark.parametrize("rig_game", sorted(RIG_TO_CORPUS))
def test_the_raw_guide_names_every_kind_its_game_emits(rig_game: str) -> None:
    """A tuple in the prompt that the guide does not describe is undocumented
    data, and it reaches the model with the treatment fingerprint unchanged.

    red under: delete the `asked` line from any raw guide — that game's cell
    fails, because its log carries one at every decision."""
    raw_guide = GAME_TEXT[rig_game][0]
    emitted = _kinds_emitted(RIG_TO_CORPUS[rig_game])
    assert emitted, f"{rig_game}: its corpus game emitted no observation event"
    missing = sorted(kind for kind in emitted if f"'{kind}'" not in raw_guide)
    assert not missing, (
        f"{rig_game}'s raw prompt guide explains no {missing} event, but its "
        f"log carries one — the model reads a tuple nothing told it about"
    )
