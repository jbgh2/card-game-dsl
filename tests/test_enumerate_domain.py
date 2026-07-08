from cardlang.runtime.mechanics import enumerate_domain

SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
PLAYERS = [0, 1, 2, 3]


def test_suit_domain_unchanged() -> None:
    assert enumerate_domain("Suit", suits=SUITS, ranks=RANKS, players=PLAYERS) == SUITS


def test_optional_suit_appends_none() -> None:
    assert enumerate_domain("Suit?", suits=SUITS, ranks=RANKS, players=PLAYERS) == SUITS + [None]


def test_rank_domain() -> None:
    assert enumerate_domain("Rank", suits=SUITS, ranks=RANKS, players=PLAYERS) == RANKS


def test_player_domain() -> None:
    assert enumerate_domain("Player", suits=SUITS, ranks=RANKS, players=PLAYERS) == PLAYERS
