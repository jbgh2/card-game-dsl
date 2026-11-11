"""The authoring benchmark's real-game check: facts that survive
relabelling, and the differential over them.

Known-positive controls come first, because a differential that always says
"diverges" would pass every reduced-game test: a file agrees with itself
under other seeds, and with a copy whose zones are renamed and whose layout
is redone. Then the files it must refuse: a reduced deal, a different
variant, and hands made public, the last being the fact the language exists
to derive.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from ..author_check import repo_root
from ..author_facts import (
    PLAYOUT_FACTS,
    DifferentialVerdict,
    FactsRecord,
    FactsRunner,
    FactsStatus,
    PlayoutFacts,
    _known_identities,
    compare,
    extract,
    ks_two_sample,
)
from .test_author_check import HIGH_CARD

GO_FISH = repo_root() / "docs" / "games" / "go-fish.cardlang"

#: HighCard with every zone renamed and the file laid out differently: the
#: same game, so every fact must agree.
RELABELLED = (
    HIGH_CARD.replace("hand", "holding")
    .replace("shown", "faceup")
    .replace("deck ", "stock ")
    .replace("deck\n", "stock\n")
    .replace("from deck", "from stock")
    .replace("  ", "    ")
)

#: HighCard dealing one card instead of two: it checks, it plays, and no
#: seat ever has a choice. A smaller game.
REDUCED = HIGH_CARD.replace("deal 2 cards", "deal 1 card")


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_registry_is_the_record() -> None:
    assert tuple(f.name for f in fields(PlayoutFacts) if f.name != "seed") == PLAYOUT_FACTS


def test_ks_on_identical_and_disjoint_samples() -> None:
    assert ks_two_sample([1.0, 2.0, 3.0] * 10, [1.0, 2.0, 3.0] * 10) == (0.0, 1.0)
    statistic, p_value = ks_two_sample([0.0] * 40, [1.0] * 40)
    assert statistic == 1.0
    assert p_value < 1e-12


def test_high_card_agrees_with_itself_under_other_seeds(tmp_path: Path) -> None:
    path = _write(tmp_path, "game.cardlang", HIGH_CARD)
    ref = extract(path, playouts=30, seed_start=0)
    other = extract(path, playouts=30, seed_start=500)
    assert compare(ref, other).verdict is DifferentialVerdict.AGREES


def test_a_relabelled_copy_agrees(tmp_path: Path) -> None:
    ref = extract(_write(tmp_path, "a.cardlang", HIGH_CARD), playouts=30, seed_start=0)
    copy = extract(_write(tmp_path, "b.cardlang", RELABELLED), playouts=30, seed_start=0)
    assert copy.status is FactsStatus.OK, copy.detail
    assert "holding" in RELABELLED and "hand" not in RELABELLED
    assert compare(ref, copy).verdict is DifferentialVerdict.AGREES


def test_a_reduced_copy_diverges(tmp_path: Path) -> None:
    ref = extract(_write(tmp_path, "a.cardlang", HIGH_CARD), playouts=30, seed_start=0)
    reduced = extract(_write(tmp_path, "b.cardlang", REDUCED), playouts=30, seed_start=0)
    assert reduced.status is FactsStatus.OK, reduced.detail
    result = compare(ref, reduced)
    assert result.verdict is DifferentialVerdict.DIVERGES
    assert {c.fact for c in result.comparisons if not c.agrees} >= {"choices"}


@pytest.fixture(scope="module")
def go_fish_reference() -> FactsRecord:
    return extract(GO_FISH, playouts=20, seed_start=0)


def test_go_fish_agrees_with_itself_under_other_seeds(go_fish_reference: FactsRecord) -> None:
    other = extract(GO_FISH, playouts=20, seed_start=1000)
    assert compare(go_fish_reference, other).verdict is DifferentialVerdict.AGREES


@pytest.mark.parametrize(
    ("old", "new", "fact"),
    [
        ("deal 5 cards from deck to each hand", "deal 7 cards from deck to each hand", "choices"),
        ("hand[player] : Hand<player> ", "hand[player] : PublicHand<player> ", "known_at_choice"),
    ],
    ids=["seven-card deal", "hands made public"],
)
def test_a_changed_go_fish_diverges_on_the_fact_it_moved(
    tmp_path: Path, go_fish_reference: FactsRecord, old: str, new: str, fact: str
) -> None:
    text = GO_FISH.read_text(encoding="utf-8")
    assert old in text
    changed = extract(_write(tmp_path, "g.cardlang", text.replace(old, new)), playouts=20, seed_start=0)
    assert changed.status is FactsStatus.OK, changed.detail
    result = compare(go_fish_reference, changed)
    assert result.verdict is DifferentialVerdict.DIVERGES
    assert fact in {c.fact for c in result.comparisons if not c.agrees}


def test_a_green_file_that_refuses_at_play_does_not_play(tmp_path: Path) -> None:
    path = _write(tmp_path, "game.cardlang", HIGH_CARD.replace("move chosen 1 card", "move chosen 3 cards"))
    candidate = FactsRunner(repo_root=repo_root(), playouts=3).run(path)
    assert candidate.status is FactsStatus.PLAY_REFUSED
    ref = extract(_write(tmp_path, "ref.cardlang", HIGH_CARD), playouts=3, seed_start=0)
    assert compare(ref, candidate).verdict is DifferentialVerdict.DOES_NOT_PLAY


def test_the_subprocess_reports_a_crash_and_a_hang(tmp_path: Path) -> None:
    runner = FactsRunner(repo_root=repo_root(), playouts=3)
    assert runner.run(tmp_path / "missing.cardlang").status is FactsStatus.CRASHED
    slow = FactsRunner(repo_root=repo_root(), playouts=3, timeout_seconds=0.01)
    assert slow.run(_write(tmp_path, "game.cardlang", HIGH_CARD)).status is FactsStatus.TIMED_OUT


def test_a_reference_without_facts_compares_nothing() -> None:
    nothing = FactsRecord(FactsStatus.CRASHED, detail="boom")
    some = FactsRecord(FactsStatus.OK, 2, "standard52", (PlayoutFacts(0, 1, 0, 1, 2.0),))
    assert compare(nothing, some).verdict is DifferentialVerdict.NOT_COMPARABLE


def test_a_seat_knows_the_cards_its_log_names_as_well_as_those_it_sees() -> None:
    from cardlang.openspiel.infostate import SeatView
    from cardlang.runtime.values import Card

    view = SeatView(
        player=0,
        zones=(("hand[0]", (Card("A", "spades"), Card("2", "hearts"))), ("hand[1]", 2), ("deck", None)),
        state=(),
        obs_log=(
            ("move", "hand[1]", 1, "trick", ("5♣",)),
            ("move", "hand[0]", 1, "trick", ("A♠",)),
            ("announce", 1, "pass"),
        ),
    )
    names = frozenset({"A♠", "2♥", "5♣", "9♦"})
    # Two in the hand and one more the log names; the hand's ace is not
    # counted twice, and a word that is no card is not a card.
    assert _known_identities(view, names) == 3
