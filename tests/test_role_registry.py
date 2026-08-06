"""Pin test: every consumer of the quantifiable-domain registry reads the ONE
table (`cardlang/domains.py`), rather than keeping a copy of it.

The role set `{player, team, suit, rank}` that `for each <role>` and the
quantifiers range over was once hand-duplicated across four sites — resolve's
`_ITERATION_ROLES`, typecheck's `_role_type`, evaluate's `_role_domain`, and a
verbatim-duplicate `_enum_role_domain` in execute — with nothing pinning them
equal. Worse, the same domains had a SECOND registry under a second namespace:
`enumerate_domain`'s capitalised move-parameter spellings (`Player`, `Suit`,
`Suit?`, `Rank`), gated by resolve's `_FIXED_DOMAINS`, with nothing relating
`player` to `Player`. `cardlang.domains` is now the one table both namespaces
are columns of.

This module pins the *identity* of each consumer's view (that it IS the
registry's, not an equal copy that could re-drift). The domain x form MATRIX —
what each row is actually legal in, and whether iterating it binds the actor —
is tests/test_domain_registry.py.

Completeness ledger
--------------------
property:  every consuming site derives its view from `cardlang.domains`, so no
           site can silently drift from the others — the identity half of the
           closed-domain completeness argument (decisions.md).
domain:    the registry's derived views (`ITERABLE_ROLES`, `SIMULTANEOUS_ROLES`,
           `PARAM_DOMAINS`, `role_type`, `role_members`) crossed with their
           consuming sites (resolve's two gates, typecheck's binder typing, the
           runtime's member enumeration).
registry:  `cardlang.domains.DOMAINS`, whose `id` column IS `domains.Role` —
           one definition site, so the enum and the table cannot disagree.
covered:   all 4 rows at typecheck (`role_type`) and at runtime (`role_members`),
           on a built game exercising all four (a 4-player team game, so
           `team` is populated too); resolve's two set-views are pinned by
           object identity (a set-level property, not a per-row one).
sampled:   none — the domain is 4 rows, fully enumerated below.
residual:  none for identity. Which FORMS each row is legal in is
           test_domain_registry.py's ledger, including the grammar-surface
           residual recorded there.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang import resolve, typecheck
from cardlang.domains import (
    DOMAINS,
    ITERABLE_ROLES,
    PARAM_DOMAINS,
    SIMULTANEOUS_ROLES,
    role_members,
    require_role,
    role_type,
)
from cardlang.pipeline import check_dsl
from cardlang.runtime import evaluate as evaluate_mod
from cardlang.runtime import execute as execute_mod
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import Ctx
from cardlang.types import TAny

# A 4-player team game with one decision point, so `on_first_decision`
# can capture a fully-built `RuntimeState` — `rs.teams` is only populated for
# team games (`driver.play_game`), so this is the minimal shape that
# exercises `team` alongside `player`/`suit`/`rank`.
ROLE_DOMAIN_SRC = """
game G {
  players: 4
  max_length: 1000
  cards: standard52
  teams: [[0, 2], [1, 3]]
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state {
    done : Boolean = false
    marker[player] : Integer = 0
  }
  phase root {
    deal 5 cards from deck to each hand
    round offering [stop] from 0
          over players where player is 0
          until done
  }
  winner: highest marker
}
move_type stop { effect { done := true } }
"""


def _rs() -> Any:
    game = check_dsl(ROLE_DOMAIN_SRC, "g.cardlang")
    captured: dict[str, Any] = {}

    def snapshot(rs: Any) -> None:
        captured["rs"] = rs

    play_game(game, random.Random(0), on_first_decision=snapshot)
    return captured["rs"]


# --- resolve's two gates ARE the registry's two views -----------------------


def test_resolve_iteration_roles_is_the_registrys_iterable_column() -> None:
    # Not just equal — the SAME object, so resolve can never quietly diverge by
    # reassigning its own local copy. `getattr` (rather than dotted attribute
    # access) sidesteps mypy strict's `--no-implicit-reexport`: `_ITERATION_ROLES`
    # is an imported alias, not defined in resolve.py, so it is deliberately not
    # part of the module's typed public interface — this test still reaches the
    # real runtime binding.
    assert getattr(resolve, "_ITERATION_ROLES") is ITERABLE_ROLES


def test_resolve_fixed_domains_is_the_registrys_param_domain_union() -> None:
    assert getattr(resolve, "_FIXED_DOMAINS") is PARAM_DOMAINS


def test_resolve_reads_the_simultaneous_column_not_a_hardcoded_player() -> None:
    # The `each … simultaneously` gate was a bare `!= "player"`. It must now be
    # the registry's `simultaneous` column, so a future seat domain lights the
    # form up (and a future value domain stays walled) from the table alone.
    assert getattr(resolve, "SIMULTANEOUS_ROLES") is SIMULTANEOUS_ROLES


# --- typecheck's binder typing IS the registry's binder_type column ----------


def test_typecheck_binder_typing_delegates_to_the_registry() -> None:
    """typecheck holds no copy of the binder-type column.

    This used to be object identity — `typecheck._role_type is role_type`.
    It cannot be now: the registry function takes a `Role` and typecheck's
    callers hold a parsed NAME, so the pass owns one classification wrapper.
    The guarantee is unchanged and is asserted where identity used to be: for
    every row, the wrapper answers exactly what the registry answers, and it
    is the registry's own object it answers with (`is`, not `==`, so a
    reconstructed-but-equal type would fail).

    red under: give `typecheck._role_type` a local table
    (`return {"player": TPlayer(), ...}[name]`) — every row still type-checks,
    every row fails this."""
    wrapper = getattr(typecheck, "_role_type")
    for row in DOMAINS:
        assert wrapper(row.id.value) is role_type(row.id) is row.binder_type


def test_role_type_is_the_binder_type_column_for_every_row() -> None:
    for row in DOMAINS:
        assert role_type(row.id) is row.binder_type


def test_role_type_is_concrete_for_every_registry_member() -> None:
    for row in DOMAINS:
        t = role_type(row.id)
        assert not isinstance(t, TAny), (
            f"role {row.id.value!r} maps to TAny, expected a concrete Type"
        )


def test_a_name_outside_the_registry_never_reaches_role_type() -> None:
    """A role outside the registry is a REGISTRY DIVERGENCE, not a program
    error — every role-bearing surface is walled against a subset of the
    registry (tests/test_permissive_top.py pins all five), so a miss means two
    registries disagree.

    `role_type` cannot be handed one at all now: it takes a `Role`. The check
    lives at the classification step instead, which is where a parsed name
    stops being a string. It used to return the permissive `TAny`, which types
    the binder as the top and silently exempts every use of it from every type
    wall (decisions.md, "`Any` means the top, never a failed lookup").

    red under: return `None` instead of raising from `domains.require_role`."""
    with pytest.raises(AssertionError) as ei:
        role_type(require_role("bogus", "binder role"))
    assert "not a binder role" in str(ei.value)


# --- the runtime has exactly ONE member enumerator ---------------------------


def test_the_runtime_has_no_private_role_domain_accessors() -> None:
    # Both runtime consumers (evaluate's quantifier, execute's `for each`) call
    # `domains.role_members`. The private per-module accessors these asserts
    # forbid — evaluate's `_role_domain` and execute's `_enum_role_domain` —
    # must not appear: a second accessor is a second place the domain order
    # can drift.
    assert not hasattr(evaluate_mod, "_role_domain")
    assert not hasattr(execute_mod, "_role_domain")
    assert not hasattr(execute_mod, "_enum_role_domain")
    assert getattr(execute_mod, "role_members") is role_members
    assert getattr(evaluate_mod, "role_members") is role_members


def test_role_members_is_non_empty_for_every_registry_member() -> None:
    ctx = Ctx(rs=_rs(), chooser=lambda p, c, k: list(c[:k])).acting_as(0)
    for row in DOMAINS:
        assert role_members(row.id, ctx), (
            f"role {row.id.value!r} produced an empty runtime domain"
        )


def test_the_two_namespaces_are_one_table() -> None:
    # The defect this registry closes: `player` and `Player` were two names for
    # one domain, held in two tables. Every capitalised move-parameter spelling
    # must now belong to a row that also owns the lowercase role noun.
    for spelling in PARAM_DOMAINS:
        owner = [row for row in DOMAINS if spelling in row.param_domains]
        assert len(owner) == 1, f"{spelling!r} is claimed by {len(owner)} rows"
        assert spelling.rstrip("?") == owner[0].type_name
        assert owner[0].type_name.lower() == owner[0].id.value


def test_a_rows_type_name_is_a_declarable_type_with_the_same_type() -> None:
    """The last unjoined axis of the "two namespaces are one table" refactor.

    `role_type(row.id)` gives a binder its type from the registry; a MOVE PARAMETER
    of the same domain is typed independently, by `type_from_name(row.type_name)`
    against typecheck's own `_SCALAR_TYPES`/`_ENUM_TYPES`. Two maps of one fact. They
    agree today, and nothing said they had to — and `type_from_name` falls back to
    `TAny` for an unknown name, so a fifth row whose `type_name` was not also a
    declarable type would make `move_type m(x : Color)` pass resolve (the domain is
    in the table) and then type as `Any`, taking every equality and ordering wall
    dark on that parameter. Silently.

    Two sites, no pin, is the finding — even while they agree."""
    from cardlang.typecheck import KNOWN_TYPE_NAMES, type_from_name

    for row in DOMAINS:
        assert row.type_name in KNOWN_TYPE_NAMES, (
            f"domain row '{row.id.value}' declares type_name '{row.type_name}', which is "
            f"not a declarable type — a move parameter of it would type as Any"
        )
        assert type_from_name(row.type_name, False, {}) == row.binder_type, (
            f"domain row '{row.id.value}': the binder types as {row.binder_type} but a "
            f"parameter of '{row.type_name}' types as "
            f"{type_from_name(row.type_name, False, {})}"
        )
