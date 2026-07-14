"""The zone-index-role registry (`domains.ZONE_INDEX_ROLES`) and its three
consumer walls: zone index (`hand[<role>]`), zone owner (`Hand<role>`), and
state-variable index (`state { x[<role>] }`).

The registry used to be a hand-written `_KNOWN_ROLES = {"player", "team"}` in
resolve, re-spelled as `== "team"` at four more sites (typecheck key typing,
the zone store's key sets, the driver's state keying, the observation layer's
ownership test) — each of which silently defaulted every non-team role to
player keying. It is now the `zone_key_of` column of the domain table: a
domain may index a zone exactly when an observer has a key of their own in it
(their seat, their team), and all five sites read the table.

The state-index wall is new. Before it, `state { x[suit] : Integer = 0 }`
checked clean and the runtime keyed it BY PLAYERS — the declared index was
accepted and ignored, the repo's worst defect class.

property:   a declared index/owner role is either a `zone_key_of` domain,
            honored identically at every consumer, or rejected at resolve
            with the legal roles named
domain:     declaration site {zone index, zone owner arg, state index}
            × role {every domain-table row, plus an unknown name}
registry:   `cardlang.domains.DOMAINS` (the `zone_key_of` column) for roles;
            the three grammar sites for positions
covered:    every cell: accepted roles are proven by corpus games (bridge:
            `captured[team] : TeamPile<team>`, `score[team]`; every game:
            `hand[player]`) and by the parametrized accepts below; rejected
            roles by the parametrized rejects (each site × each non-indexable
            row × unknown)
sampled:    none
residual:   value-domain-indexed state (`x[rank]` as a per-rank tally) —
            walled here, recorded in roadmap.md ("Value-domain-indexed
            state")
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DOMAINS, ZONE_INDEX_ROLES
from cardlang.pipeline import check_dsl


def _game(zones: str, state: str) -> str:
    return f"""game G {{
  players: 4
  partnerships: [[0, 2], [1, 3]]
  max_length: 100
  direction: clockwise
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  {zones} }}
  state {{ n[player] : Integer = 0  {state} }}
  phase p {{ deal 1 cards from deck to each hand }}
  winner: highest n
}}"""


def test_the_registry_is_the_zone_key_of_column() -> None:
    """Membership derives from the table column, not a list: exactly the
    domains in which an observer has a key of their own."""
    assert ZONE_INDEX_ROLES == frozenset(
        d.id for d in DOMAINS if d.zone_key_of is not None
    )
    # And today that is the two seat-anchored stores. A third indexable role
    # enters by adding `zone_key_of` to its row — which simultaneously feeds
    # resolve's wall, typecheck's key typing, both runtime key sets, and the
    # ownership projection. If this set changed on purpose, update the corpus
    # claims in this file's ledger.
    assert ZONE_INDEX_ROLES == frozenset({"player", "team"})


_NON_INDEX_ROLES = sorted(
    d.id for d in DOMAINS if d.zone_key_of is None
) + ["croupier"]  # every non-indexable table row, plus an unknown name


@pytest.mark.parametrize("role", _NON_INDEX_ROLES)
def test_a_zone_may_not_be_indexed_by_a_value_domain(role: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(f"pile[{role}] : Discard", ""), "probe.cardlang")
    assert f"unknown index role '{role}'" in str(exc.value)


@pytest.mark.parametrize("role", _NON_INDEX_ROLES)
def test_a_zone_type_may_not_be_owned_by_a_value_domain(role: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(f"h2[player] : Hand<{role}>", ""), "probe.cardlang")
    assert f"unknown owner '{role}'" in str(exc.value)


@pytest.mark.parametrize("role", _NON_INDEX_ROLES)
def test_a_state_variable_may_not_be_indexed_by_a_value_domain(role: str) -> None:
    # The wall this file exists for: before it, `state { x[suit] }` checked
    # clean and ran as a per-PLAYER store (the driver's key-set dispatch
    # defaulted every non-team role to seats).
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("", f"x[{role}] : Integer = 0"), "probe.cardlang")
    assert f"indexed by '{role}'" in str(exc.value)


@pytest.mark.parametrize("role", sorted(ZONE_INDEX_ROLES))
def test_every_indexable_role_is_accepted_at_all_three_sites(role: str) -> None:
    # The positive half of the matrix, per registry row (the corpus proves the
    # runtime semantics: bridge keys zones and state by team every hand).
    src = _game(
        f"pile[{role}] : Discard  h2[{role}] : PlayerPile<{role}>",
        f"x[{role}] : Integer = 0",
    )
    check_dsl(src, "probe.cardlang")  # must not raise
