import random
from pathlib import Path

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

FIXTURE = Path(__file__).parent / "fixtures" / "offer_skeleton.cardlang"


def test_offer_skeleton_checks_and_plays() -> None:
    game = check_source(FIXTURE)
    assert game.name == "OfferSkeleton"
    seen_one = seen_two = False
    for seed in range(50):
        result = play_game(game, random.Random(seed))
        for p in (0, 1):
            assert 10 <= result.scores[p] <= 20  # 10 offers of +1 or +2 each
        if any(result.scores[p] < 20 for p in (0, 1)):
            seen_one = True
        if any(result.scores[p] > 10 for p in (0, 1)):
            seen_two = True
    assert seen_one and seen_two  # both move-types actually get chosen
