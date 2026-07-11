import pytest

from cardlang.runtime.mechanics import enumerate_domain

# `_FIXED_DOMAINS` (cardlang/resolve.py, ~line 548) is the static totality gate:
# it decides which move-parameter domain names reach a real game at all (a
# `_check_move_params` diagnostic rejects anything else before a game ever
# plays). It has no leading-underscore-avoiding public alias, but it is a
# module-level name (not function-local), so it is directly importable — same
# precedent as `_walk` in tests/test_functions.py and tests/test_names.py.
from cardlang.resolve import _FIXED_DOMAINS

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


def test_optional_rank_raises() -> None:
    # Only `Suit?` has a real nullable enumeration (`Suit`'s branch appends
    # `None`); `Rank?` must not silently fall through to the plain `Rank`
    # branch by stripping the `?` (resolve.py's gate already rejects `Rank?`
    # at the surface, but `enumerate_domain` must defend itself too, rather
    # than relying solely on that gate).
    with pytest.raises(NotImplementedError):
        enumerate_domain("Rank?", suits=SUITS, ranks=RANKS, players=PLAYERS)


def test_optional_player_raises() -> None:
    with pytest.raises(NotImplementedError):
        enumerate_domain("Player?", suits=SUITS, ranks=RANKS, players=PLAYERS)


# --- enumerate_domain pinned against resolve.py's declared-domain gate ---
#
# `_FIXED_DOMAINS` is resolve.py's static totality gate; `enumerate_domain` is
# the runtime dispatch that actually enumerates each admitted domain. These
# are two hand-written sets that must name the same domains — the
# closed-domain completeness doctrine's "arms of a dispatch over a registry"
# case (docs/decisions.md, "Closed-domain completeness"): if resolve admits a
# domain `enumerate_domain` doesn't implement, a game would pass the static
# gate and then NotImplementedError mid-playout, past resolve's own totality
# check. If `enumerate_domain` implements a domain resolve never admits,
# that's a dead arm masquerading as coverage. `Card` is deliberately excluded
# from both sides: resolve admits it as a move-parameter type, but its
# domain is state-dependent (the live hand) and it is enumerated separately
# by `param_domain`/`candidates`, never by `enumerate_domain`.

# The domains enumerate_domain's own dispatch (its if/elif chain) admits.
# Hand-derived by reading the function: unlike STDLIB_CALL_FUNCS/ZONE_METHODS,
# enumerate_domain has no name-set constant of its own to import, so this
# literal is the other side of the two-sided pin the test below enforces.
ENUMERATE_DOMAIN_HANDLED = frozenset({"Suit", "Suit?", "Rank", "Player"})


def test_enumerate_domain_matches_resolves_fixed_domains() -> None:
    # The two hand-written sets must agree exactly: adding a domain to either
    # side without the other is exactly the drift this pin exists to catch.
    assert ENUMERATE_DOMAIN_HANDLED == _FIXED_DOMAINS


def test_enumerate_domain_handles_every_admitted_domain() -> None:
    # The load-bearing half: actually invoke enumerate_domain for every domain
    # resolve's gate admits, and confirm each reaches a real dispatch arm
    # (returns a list) rather than falling through to the `NotImplementedError`
    # default — a static-set comparison alone would never call the function
    # under test.
    for domain in ENUMERATE_DOMAIN_HANDLED:
        result = enumerate_domain(domain, suits=SUITS, ranks=RANKS, players=PLAYERS)
        assert isinstance(result, list)
        assert result  # every admitted domain enumerates at least one value


def test_enumerate_domain_rejects_card() -> None:
    # `Card` is resolve-admitted as a move-parameter type but deliberately
    # absent from enumerate_domain's dispatch (state-dependent domain,
    # enumerated elsewhere) — confirms "exactly" is bidirectional: not just
    # every admitted domain is handled, but the one resolve-allowed type
    # that ISN'T meant to reach this dispatch is refused, not silently
    # accepted.
    with pytest.raises(NotImplementedError):
        enumerate_domain("Card", suits=SUITS, ranks=RANKS, players=PLAYERS)
