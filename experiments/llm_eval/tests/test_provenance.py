"""The digest that pins a transcript to the game source it was recorded
against.

A transcript's `history` is a sequence of action ids, meaningful only against
the `.cardlang` source that assigned them — Cheat's own archive shows what
goes wrong otherwise: recorded ids from before the four-card play cap was
removed silently misdecode, or fail, against today's action space, and
nothing in the record itself said so (`REVIEWER.md`, "Which Cheat these
transcripts play"). `game_digest` and `replay_views`'s `expected_digest` are
the general guard: a transcript that carries its game's source digest can be
refused loudly, by every future game, without a hand-rolled legacy check per
archive.

These need `pyspiel` (the `openspiel` extra) and the corpus directory, same as
`tests/test_game.py`.
"""

from __future__ import annotations

import hashlib

import pytest

from ..agents import RandomAgent
from ..referee import ProvenanceError, game_digest, load_game, play_game, replay_views

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")


@pytest.fixture(scope="module")
def game() -> object:
    return load_game("cardlang_cheat")


def _seats(seed: int) -> dict[int, object]:
    return {i: RandomAgent(seed=seed + i) for i in range(4)}


def test_a_played_record_carries_the_loaded_games_digest(game: object) -> None:
    record = play_game(game, _seats(1), seed=1, matchup="t", game_index=0, max_decisions=20)  # type: ignore[arg-type]
    expected = game_digest("cardlang_cheat")
    assert record.game_digest == expected
    assert record.as_dict()["game_digest"] == expected


def test_replay_with_the_matching_digest_matches_replay_without_one(game: object) -> None:
    record = play_game(game, _seats(2), seed=2, matchup="t", game_index=0, max_decisions=20)  # type: ignore[arg-type]
    plain = replay_views(game, record.seed, record.history)
    pinned = replay_views(
        game, record.seed, record.history, expected_digest=record.game_digest
    )
    assert len(plain) == len(pinned) == len(record.decisions)
    for a, b in zip(plain, pinned, strict=True):
        assert a.player == b.player
        assert a.infostate == b.infostate
        assert a.legal_actions == b.legal_actions
        assert a.legal_strings == b.legal_strings


def test_replay_with_an_altered_digest_raises_provenance_error(game: object) -> None:
    record = play_game(game, _seats(3), seed=3, matchup="t", game_index=0, max_decisions=20)  # type: ignore[arg-type]
    wrong_digest = "0" * 64
    assert wrong_digest != record.game_digest, "the wrong digest must actually differ"
    with pytest.raises(ProvenanceError, match="cardlang_cheat"):
        replay_views(game, record.seed, record.history, expected_digest=wrong_digest)


def test_the_digest_changes_when_the_game_source_changes(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Proves `game_digest` reads the file at call time, not a cached object:
    the same short name digests differently once the registry is pointed at a
    one-byte-altered copy of the source, and the new digest is exactly the
    SHA-256 of that copy's bytes — the same function the digest itself uses.
    """
    from cardlang.openspiel import registry

    original_bytes = (registry._GAMES_DIR / registry.GAMES["cardlang_cheat"]).read_bytes()
    original_digest = game_digest("cardlang_cheat")

    mutated = bytearray(original_bytes)
    mutated[0] ^= 0xFF
    (tmp_path / "cheat.cardlang").write_bytes(bytes(mutated))

    monkeypatch.setattr(registry, "_GAMES_DIR", tmp_path)
    monkeypatch.setattr(registry, "GAMES", {"cardlang_cheat": "cheat.cardlang"})

    mutated_digest = game_digest("cardlang_cheat")
    assert mutated_digest == hashlib.sha256(bytes(mutated)).hexdigest()
    assert mutated_digest != original_digest
