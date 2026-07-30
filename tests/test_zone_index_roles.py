"""The zone-index-role registry (`domains.ZONE_INDEX_ROLES`) and its three
consumer walls: zone index (`hand[<role>]`), zone owner (`Hand<role>`), and
state-variable index (`state { x[<role>] }`).

The defect class this closes: a hand-written `_KNOWN_ROLES = {"player",
"team"}` in resolve, re-spelled as `== "team"` at five more sites (typecheck
key typing, the zone store's key sets, the driver's state keying, the
observation layer's ownership test, and the openspiel proof harness's own
ownership oracle in tests/openspiel_ready/partition.py) — each of which would
silently default every non-team role to player keying. The registry is
instead the `zone_key_of` column of the domain table: a domain may index a
zone exactly when an observer has a key of their own in it (their seat, their
team), and all six sites read the table —
the proof-harness site matters doubly, since an oracle with a private copy of
the rule proves the corpus against the copy, not the rule.

Without the state-index wall, `state { x[suit] : Integer = 0 }` would check
clean and the runtime would key it BY PLAYERS — the declared index accepted
and ignored, the repo's worst defect class.

The owner-agreement wall is a separate axis. A validity check ("is the owner a
known role?") is not an agreement check ("does the owner match the index?"):
without it, `hand[player] : Hand<team>` would check clean because `team` is a
valid role — but the runtime keys the family by the INDEX (`zone_observer_key`
reads `ZoneDecl.index`; the argument's domain is never consulted), so the
`<team>` would be accepted and then ignored, the same worst class. An owned
type also has no key for its owner when it has no index at all. Both are
rejected.

property:   a declared index/owner role is either a `zone_key_of` domain,
            honored identically at every consumer, or rejected at resolve
            with the legal roles named; and on an owned zone type the owner
            argument names the SAME domain as the index (and an owned type has
            an index), since the family is keyed by the index and a differing
            argument domain is otherwise accepted-but-ignored
domain:     declaration site {zone index, zone owner arg, state index}
            × role {every domain-table row, plus an unknown name}; and, at the
            owner-argument site, the (owner domain, index domain) pair —
            {equal, unequal, index-absent}
registry:   `cardlang.domains.DOMAINS` (the `zone_key_of` column) for roles;
            `cardlang.stdlib.zones.LIBRARY_ZONE_TYPES` (`takes_owner`) for
            which types carry an owner; the three grammar sites for positions
covered:    every role-validity cell: accepted roles are proven by corpus
            games (bridge: `captured[team] : TeamPile<team>`, `score[team]`;
            every game: `hand[player]`) and by the parametrized accepts below;
            rejected roles by the parametrized rejects (each site × each
            non-indexable row × unknown). Owner==index agreement: both unequal
            role/role directions and the index-absent case rejected below; the
            position directions (owner a different position, or a role) in
            tests/test_positions.py and the rejection corpus
            (tests/rejections/{zone_owner_arg_domain_mismatch,
            positions_zone_owner_arg_mismatch, zone_owned_type_without_index})
sampled:    the owner==index rule is uniform over domains, so the unequal case
            is probed by representative pairs per category (role/role,
            position/position, position/role, role/position), not every pair
residual:   value-domain-indexed state (`x[rank]` as a per-rank tally) —
            walled here, recorded in
            roadmap.md, "Grammar surface deferred by the checker"
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DOMAINS, ZONE_INDEX_ROLES, Role, role_names
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
    assert ZONE_INDEX_ROLES == frozenset({Role.PLAYER, Role.TEAM})


_NON_INDEX_ROLES = sorted(
    d.id.value for d in DOMAINS if d.zone_key_of is None
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


@pytest.mark.parametrize(
    "zones,index",
    [
        ("h2[player] : Hand<team>", "player"),  # valid role, wrong domain
        ("won[team] : TeamPile<player>", "team"),  # the other direction
    ],
)
def test_owned_zone_owner_arg_must_match_its_index(zones: str, index: str) -> None:
    # Validity is not agreement: `team` and `player` are both indexable roles,
    # so the owner passes the value-domain check above — but the runtime keys
    # the family by the INDEX, so an owner naming the other role is
    # accepted-but-ignored. Rejected at the site (the accepted counterpart is
    # the base game's `hand[player] : Hand<player>`).
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(zones, ""), "probe.cardlang")
    msg = str(exc.value)
    assert f"indexed by '{index}'" in msg
    assert "must name the same domain as the index" in msg


def test_an_owned_zone_type_must_be_indexed() -> None:
    # The index-absent cell: an owned type with no index has no key for its
    # owner, so the argument is again accepted-but-ignored.
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("solo : Hand<player>", ""), "probe.cardlang")
    assert "must be indexed by its owner" in str(exc.value)


@pytest.mark.parametrize("role", _NON_INDEX_ROLES)
def test_a_state_variable_may_not_be_indexed_by_a_value_domain(role: str) -> None:
    # The wall this file exists for: before it, `state { x[suit] }` checked
    # clean and ran as a per-PLAYER store (the driver's key-set dispatch
    # defaulted every non-team role to seats).
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("", f"x[{role}] : Integer = 0"), "probe.cardlang")
    assert f"indexed by '{role}'" in str(exc.value)


@pytest.mark.parametrize("role", role_names(ZONE_INDEX_ROLES))
def test_every_indexable_role_is_accepted_at_all_three_sites(role: str) -> None:
    # The positive half of the matrix, per registry row (the corpus proves the
    # runtime semantics: bridge keys zones and state by team every hand).
    src = _game(
        f"pile[{role}] : Discard  h2[{role}] : PlayerPile<{role}>",
        f"x[{role}] : Integer = 0",
    )
    check_dsl(src, "probe.cardlang")  # must not raise


def test_team_indexing_needs_partnerships() -> None:
    # A team-indexed store in a game with no `partnerships:` has an EMPTY key
    # set — without these walls it would declare fine, hold nothing, and fail
    # far away on the first write. Both declaration sites are rejected at the
    # cause.
    src_zone = _game("won[team] : TeamPile<team>", "").replace(
        "  partnerships: [[0, 2], [1, 3]]\n", ""
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src_zone, "probe.cardlang")
    assert "no `partnerships:`" in str(exc.value)
    src_state = _game("", "t[team] : Integer = 0").replace(
        "  partnerships: [[0, 2], [1, 3]]\n", ""
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src_state, "probe.cardlang")
    assert "no `partnerships:`" in str(exc.value)


_LET_INDEX_NOUNS = sorted(
    d.id.value for d in DOMAINS if d.iterable and d.id is not Role.PLAYER
)


@pytest.mark.parametrize("noun", _LET_INDEX_NOUNS)
def test_an_indexed_let_may_not_borrow_a_value_domain_noun(noun: str) -> None:
    # The third site of the `index` grammar production (after zone and state
    # declarations): `let x[i] = …` builds a per-PLAYER map — the index is a
    # binder, not a domain — so a binder named `suit`/`rank`/`team` reads as a
    # per-value store the form does not build (`let x[suit] = 1` then
    # `x[hearts]` key-errored; a team read silently landed on a seat).
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game("", "").replace(
            "deal 1 cards from deck to each hand",
            f"let q[{noun}] = 1\n    n[0] := q[0]",
        ), "probe.cardlang")
    assert f"per-{noun} store" in str(exc.value)


def test_an_indexed_let_with_an_ordinary_binder_still_checks() -> None:
    check_dsl(_game("", "").replace(
        "deal 1 cards from deck to each hand",
        "let q[p] = 1\n    n[0] := q[0]",
    ), "probe.cardlang")


def test_team_ownership_follows_the_observers_team() -> None:
    """The ownership DIRECTION, pinned directly: the observer's OWN team decides
    whether they own a team-keyed family instance. Every corpus team zone
    (TeamPile) projects identically for owners and non-owners, so an inverted
    ownership function (reading the key's members instead of the observer's
    team) would keep the whole suite — including the partnership openspiel
    proofs — green. This test is the one place the bit itself is asserted."""
    import random

    from cardlang.ast import nodes as n
    from cardlang.domains import zone_observer_key
    from cardlang.runtime.observe import _is_owner
    from cardlang.runtime.state import RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating

    decls = (
        n.ZoneDecl(
            name="won",
            index="team",
            type_ref=n.TypeRef(name="TeamPile", args=(n.TypeArg(name="team"),)),
        ),
    )
    rs = RuntimeState(
        Seating(4), ZoneStore(decls, (0, 1, 2, 3), teams=(0, 1)), random.Random(0)
    )
    rs.team_of = {0: 0, 2: 0, 1: 1, 3: 1}
    assert [zone_observer_key("team", rs, obs) for obs in (0, 1, 2, 3)] == [0, 1, 0, 1]
    assert zone_observer_key("player", rs, 3) == 3
    # Ownership of the instance keyed by team 0: partners 0 and 2, nobody else.
    assert [_is_owner(rs, "won", 0, obs) for obs in (0, 1, 2, 3)] == [
        True,
        False,
        True,
        False,
    ]
    # An observer with no team owns nothing and crashes nothing.
    rs.team_of = {}
    assert _is_owner(rs, "won", 0, 0) is False
