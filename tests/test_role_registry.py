"""Pin test for the unified iteration-role registry (`cardlang/roles.py`).

Before this module existed, the closed role set `{player, team, suit, rank}`
that `for each <role>`/quantifier constructs range over was hand-duplicated
across four sites — resolve.py's `_ITERATION_ROLES`, typecheck.py's
`_role_type`, runtime/evaluate.py's `_role_domain`, and a verbatim-duplicate
`_enum_role_domain` in runtime/execute.py — with nothing pinning them equal.
`cardlang.roles` is now the one place the set and the per-role binder type
are spelled; resolve and typecheck import from it directly, and
runtime/execute.py imports runtime/evaluate.py's `_role_domain` (the single
runtime accessor) instead of re-deriving suit/rank domains itself.

This module pins three things staying true:

1. resolve's accepted iteration-role set IS `cardlang.roles.ROLES` (same
   object, not just an equal copy that could re-drift).
2. typecheck's per-role binder-type mapping covers `ROLES` exactly — every
   registry member maps to a concrete `Type`, and nothing outside the
   registry does (the closed-domain completeness argument, decisions.md).
3. the runtime accessor (`runtime.evaluate._role_domain`, imported — not
   re-implemented — by `runtime.execute`) returns a non-empty domain for
   every registry member, on a built game exercising all four (a 4-player
   partnership game covers `team` too, not just `player`/`suit`/`rank`).

Completeness ledger
--------------------
property:  the four call sites agree on both membership (`ROLES`) and, where
           applicable, the per-role type/domain they derive from a role name
           — no site can silently drift from the other three.
domain:    `cardlang.roles.ROLES` (the closed 4-name set) crossed with each
           of the three consuming sites (resolve membership check, typecheck
           binder typing, runtime domain accessor).
registry:  `cardlang.roles.ROLES` / `cardlang.roles.ROLE_TYPES`.
covered:   all 4 roles at both typecheck (`role_type`) and runtime
           (`_role_domain`); resolve's set-identity is checked once (it is
           the same frozenset object, not a per-role property).
sampled:   none — the domain is 4 elements, fully enumerated below.
residual:  none.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang import resolve, typecheck
from cardlang.pipeline import check_dsl
from cardlang.roles import ROLE_TYPES, ROLES, role_type
from cardlang.runtime import execute as execute_mod
from cardlang.runtime import evaluate as evaluate_mod
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import Ctx
from cardlang.types import TAny

# A 4-player partnership game with one decision point, so `on_first_decision`
# can capture a fully-built `RuntimeState` — `rs.teams` is only populated for
# partnership games (`driver.play_game`), so this is the minimal shape that
# exercises `team` alongside `player`/`suit`/`rank`.
ROLE_DOMAIN_SRC = """
game G {
  players: 4
  max_length: 1000
  cards: standard52
  partnerships: [[0, 2], [1, 3]]
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


def test_resolve_iteration_roles_is_the_shared_registry() -> None:
    # Not just equal — the SAME object, so resolve can never quietly diverge
    # by reassigning its own local copy. `getattr` (rather than dotted
    # attribute access) sidesteps mypy strict's `--no-implicit-reexport`:
    # `_ITERATION_ROLES` is an imported alias, not defined in resolve.py, so
    # it is deliberately not part of the module's typed public interface —
    # this test still reaches the real runtime binding.
    assert getattr(resolve, "_ITERATION_ROLES") is ROLES


def test_typecheck_role_type_is_the_shared_registry_function() -> None:
    assert getattr(typecheck, "_role_type") is role_type


def test_role_types_mapping_covers_roles_exactly() -> None:
    assert set(ROLE_TYPES) == ROLES


def test_role_type_is_concrete_for_every_registry_member() -> None:
    for role in ROLES:
        t = role_type(role)
        assert not isinstance(t, TAny), f"role {role!r} maps to TAny, expected a concrete Type"


def test_role_type_falls_back_to_any_outside_the_registry() -> None:
    assert isinstance(role_type("bogus"), TAny)


def test_execute_imports_evaluates_role_domain_accessor() -> None:
    # runtime/execute.py must import evaluate's `_role_domain` rather than
    # re-implement it — the defect this task removes (`_enum_role_domain`
    # was a verbatim duplicate of the suit/rank arms).
    assert getattr(execute_mod, "_role_domain") is evaluate_mod._role_domain
    assert not hasattr(execute_mod, "_enum_role_domain")


def test_role_domain_is_non_empty_for_every_registry_member() -> None:
    game = check_dsl(ROLE_DOMAIN_SRC, "g.cardlang")
    captured: dict[str, Any] = {}

    def snapshot(rs: Any) -> None:
        captured["rs"] = rs

    play_game(game, random.Random(0), on_first_decision=snapshot)

    rs = captured["rs"]
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k])).acting_as(0)

    for role in ROLES:
        domain = evaluate_mod._role_domain(role, ctx)
        assert domain, f"role {role!r} produced an empty runtime domain"
