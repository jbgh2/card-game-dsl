"""`enumerate_domain` — the static (declaration-time) member enumerator of the
quantifiable-domain registry — pinned against the gate that admits its inputs.

`_FIXED_DOMAINS` (cardlang/resolve.py) is the static totality gate: it decides
which move-parameter domain spellings reach a real game at all (a
`_check_move_params` diagnostic rejects anything else before a game ever plays).
`enumerate_domain` (cardlang/domains.py) is what actually enumerates each
admitted spelling. Both are now derived from the SAME registry rows — the gate
is the union of the rows' `param_domains`, and the enumerator is a lookup into
those same rows — so this module pins that the derivation really is shared, and
that every admitted spelling reaches a live row rather than a `NotImplementedError`.

The one-sided-drift defect this guards (docs/decisions.md, "Closed-domain
completeness"): if resolve admits a domain the enumerator does not implement, a
game passes the static gate and then dies mid-playout, past resolve's own
totality check; if the enumerator implements a domain resolve never admits,
that's a dead arm masquerading as coverage.

`Card` is deliberately excluded from both sides: resolve admits it as a
move-parameter type, but it is not a registry row — its domain is
state-dependent (the live hand) and it is enumerated by
`mechanics.param_domain`, ahead of this table.
"""

from __future__ import annotations

import pytest

from cardlang import resolve
from cardlang.domains import (
    BY_ID,
    BY_PARAM_DOMAIN,
    PARAM_DOMAIN_ORDER,
    PARAM_DOMAINS,
    DomainSources,
    enumerate_domain,
)

# resolve's gate, reached through `getattr` rather than a direct import: it is
# now an imported ALIAS of the registry's view (that is the point of this
# module), and mypy strict's `--no-implicit-reexport` refuses to import an alias
# from the module that re-exports it. This still reaches the real binding — and
# the identity assertions below are what prove it IS the registry's.
_FIXED_DOMAINS: frozenset[str] = getattr(resolve, "_FIXED_DOMAINS")

SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
PLAYERS = [0, 1, 2, 3]

SOURCES = DomainSources(suits=SUITS, ranks=RANKS, players=PLAYERS)


def test_suit_domain_unchanged() -> None:
    assert enumerate_domain("Suit", SOURCES) == SUITS


def test_optional_suit_appends_none() -> None:
    assert enumerate_domain("Suit?", SOURCES) == SUITS + [None]


def test_rank_domain() -> None:
    assert enumerate_domain("Rank", SOURCES) == RANKS


def test_player_domain() -> None:
    assert enumerate_domain("Player", SOURCES) == PLAYERS


def test_optional_rank_raises() -> None:
    # Only `Suit?` is listed by a registry row, so only it has a real nullable
    # enumeration; `Rank?` must not silently fall through to the plain `Rank`
    # row by stripping the `?` (resolve's gate already rejects `Rank?` at the
    # surface, but the enumerator must defend itself too, rather than relying
    # solely on that gate).
    with pytest.raises(NotImplementedError):
        enumerate_domain("Rank?", SOURCES)


def test_optional_player_raises() -> None:
    with pytest.raises(NotImplementedError):
        enumerate_domain("Player?", SOURCES)


# --- the enumerator and resolve's gate are the same registry ----------------


def test_resolve_fixed_domains_is_the_registrys_param_domain_union() -> None:
    # Not merely equal — the SAME frozenset object, so resolve cannot quietly
    # diverge by reassigning its own local copy.
    assert _FIXED_DOMAINS is PARAM_DOMAINS


def test_the_enumerators_lookup_table_covers_exactly_the_admitted_domains() -> None:
    # The other side of the two-sided pin: the spellings the enumerator can
    # resolve to a row are exactly the spellings resolve admits. Adding a
    # `param_domains` entry to one side without the other is now impossible by
    # construction (both are derived from the rows) — this test is what makes
    # that "by construction" a checked claim rather than an assertion.
    assert frozenset(BY_PARAM_DOMAIN) == _FIXED_DOMAINS
    assert frozenset(PARAM_DOMAIN_ORDER) == _FIXED_DOMAINS
    assert len(PARAM_DOMAIN_ORDER) == len(BY_PARAM_DOMAIN)  # no duplicate spelling


def test_enumerate_domain_handles_every_admitted_domain() -> None:
    # The load-bearing half: actually invoke the enumerator for every domain
    # resolve's gate admits, and confirm each reaches a real row (returns a
    # non-empty list) rather than the `NotImplementedError` default — a
    # static-set comparison alone would never call the function under test.
    for domain in _FIXED_DOMAINS:
        result = enumerate_domain(domain, SOURCES)
        assert isinstance(result, list)
        assert result  # every admitted domain enumerates at least one value


def test_enumerate_domain_rejects_card() -> None:
    # `Card` is resolve-admitted as a move-parameter type but deliberately not a
    # registry row (state-dependent domain, enumerated by `param_domain`) —
    # confirms "exactly" is bidirectional: not just that every admitted domain
    # is handled, but that the one resolve-allowed type which is NOT meant to
    # reach this table is refused, not silently accepted.
    with pytest.raises(NotImplementedError):
        enumerate_domain("Card", SOURCES)


def test_a_domain_with_no_param_spelling_is_walled_at_the_param_column() -> None:
    """`team` is a registry row with `param_domains=()` — quantifiable and iterable,
    but not a declarable parameter domain. The wall lives in that column, and it is
    the right place for it: `enumerate_domain` refuses the spelling outright, so a
    `Team`-parameterized move can never enumerate zero candidates and die mid-decision
    (an offer with no legal move).

    Its `static_members`, by contrast, must be REAL — the deck-capacity gate reads it
    to know how many times a `for each team` body runs. It used to be a wall too, on
    the theory that a domain with no parameter spelling had no static domain at all.
    That conflated two different questions ("can a move range over this?" and "how big
    is this?"), and the gate paid for it: it assumed every non-player loop ran once, so
    a loop over a value domain demanded more cards than it checked."""
    with pytest.raises(NotImplementedError):
        enumerate_domain("Team", SOURCES)
    # ...but its size is a fact the table knows.
    assert BY_ID["team"].static_members(SOURCES) == list(SOURCES.teams)
