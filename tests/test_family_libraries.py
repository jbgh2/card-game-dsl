"""Misuse probes for the `uses` family-library tier, plus its completeness pin.

The surface-totality artifact for the import tier (CLAUDE.md, decisions.md
"Surface totality" / "Closed-domain completeness"). Every guard `_apply_uses`
raises is probed here with the most plausible WRONG sentence for it, and each is
proven loud in the layer whose channel it belongs to — resolve's diagnostic bag,
carrying the game's own `uses` span, never a stray name error from inside library
text the author did not write.

Completeness ledger
-------------------
property: a family-library file parses as the items its author wrote; its
          `requires` contract is SUFFICIENT, so a game meeting it in full is
          enough; its PROVIDED state is read-only to the including game; and
          every way a `uses` line can be wrong is rejected, loudly, at resolve.
domain:   two layers. At PARSE, the library file's clause skeleton: the
          `?library_item` alternatives times {well-formed, truncated at their
          last required slot}, crossed with every alternative as the NEIGHBOUR
          written below — the cell that matters being a truncated item that
          completes itself from its neighbour and drops it. At RESOLVE, five
          products. (a) The library's ENCAPSULATION: each EXPRESSION-BEARING
          clause of `n.Library` as the site a leak is written in — the six
          definition kinds plus `state`, whose defaults are expressions — times
          the reference kinds a body can leak through (a state name, a function
          call). Beside it, the same property reached by the OTHER door: every
          reference SLOT the registry says a library can hold — a name a
          construct carries as a plain string, which no expression cell can be
          written for. The two together are the whole of "what can a library
          name", split by how the name is spelled rather than by what it means.
          (b) The `requires` contract per name: how many declarations the
          game holds {0, 1, 2} times the shape of the last one {matching, and
          one row per field `_check_requires` compares}. (c) The import tier's
          error space — the failure modes of a `uses` line (unknown library,
          repeated import) times, for each definition kind, the three-way
          collision matrix (game/library, library/library, library/kernel).
          (d) PROVIDED state's read-only rule: every node kind that writes
          persistent state, times whether the name written is provided or
          required. (e) The STATE-CLAIM space: which claims on one state name may
          coexist — a library's claim subset {requires, state, both} times
          whether the game declares it, and the two-library cross of {requires,
          state} times the same. (f) PROVIDED state's other half: every way the
          GAME introduces a name into a scope narrower than the game — a binder,
          a declaration parameter — times what the library does with that
          spelling {provides, requires, neither}. (d) is the write face of
          ownership and this is the READ face: a shadowed provided variable is
          not written, it becomes unreadable. The introduction axis runs to
          sub-positions, not node kinds: a kind whose spelling the LANGUAGE
          fixes has as many introductions as the registry fixing it has members.
          Outside (f), and each with an executed probe rather than a prose
          claim: a phase-local `state { }` block, which is narrower than the
          game but is not a binder; the pronoun rebinds, whose spellings a
          library may not provide; a Primitive's parameters, which scope no DSL
          body; and a spelling a registry admits that no game text can reach.
          The grid quantifies over WHICH sentences the bag holds, not over
          where each one points: a parameter row is reported at its own
          parameter and a binder row at the construct that introduces it, which
          for a struct or a `produces:` arm is the declaration rather than the
          field. The rendered span of one sentence is pinned where it is pinned
          at all — `tests/rejections/binder_shadows_provided_state.expected`,
          byte-for-byte, for the case the issue itself names.
registry: the ITEM axis from the grammar's `?library_item`, scraped by
          `library_item_alternatives` (shared with tests/test_game_clause_guards,
          which owns the other half of the same absorption class and pins the
          `STRUCT_TYPE_NAME` terminal against both clause registries); the
          DEFINITION-KIND axis from `resolve._LIBRARY_DEF_KINDS`, pinned to
          `n.Library`'s own fields by `test_def_kinds_covers_every_library_field`;
          the LEAK-SITE axis from `n.Library`'s fields MINUS `requires`, which is
          the only clause with no expression slot to leak through
          (`test_leak_sites_cover_every_expression_bearing_clause`) — derived by
          subtraction rather than by listing, so a clause added with an
          expression in it joins the grid without anyone remembering to add it; the SHAPE axis from `n.RequireDecl`'s own fields
          minus its key and span — the field set `_check_requires` compares —
          pinned by `test_shape_axis_covers_every_compared_field`, which is how
          the `optional` row came to exist;
          the COLLISION-SOURCE axis from the three namespaces a library name can
          land in — the game (`n.Game`'s same-named fields), another library, and
          the engine's own name registries (`stdlib_rules()`, `CALL_FUNCS`,
          `LIBRARY_MOVE_TYPES`), read through `_engine_registry_member`;
          the WRITE-SITE axis from the RUNTIME — `_state_write_node_kinds()`
          scrapes every `ctx.rs.set()` call in `cardlang/runtime/execute.py` and
          reads its handler's first-parameter annotation, because
          `runtime/state.py`'s `Store.set` is the one door onto persistent state,
          so the statements reaching it ARE the write sites. Pinned in both
          directions against `resolve._STATE_WRITE_SITES` (what the guard sweeps)
          and `_WRITE_STMT` (what this grid probes) by
          `test_write_sites_cover_every_state_writing_node`, with
          `test_every_write_site_field_exists_on_its_node` under it so a renamed
          field cannot leave the guard silently covering two forms of three;
          the CLAIM-KIND axis from `n.Library`'s state clauses — its fields minus
          its name, its span and the definition kinds — pinned by
          `test_claim_axis_covers_every_library_state_clause`;
          the INTRODUCER axis from the union of the two registries owning the
          ways a game narrows a scope — `_binding_node_kinds()` scrapes
          `resolve._node_binders`'s own match arms (an arm returning a non-empty
          tuple binds a name, which is why `Transfer`/`EpistemicOp` count through
          their guarded arms and not their plain ones), and `resolve._PARAM_
          BEARING` supplies the declaration parameters that registry deliberately
          excludes. Crossed against the grid's rows by `test_introducer_axis_
          covers_every_way_a_game_introduces_a_name`, which also asserts the two
          registries disjoint, so neither can quietly absorb the other's members.
          Under it, the SUB-POSITION axis: `_fixed_spellings()` reads each
          language-fixed kind's spellings off the registry that fixes them —
          `domains.DOMAINS` for the quantifier nouns, `SIMULTANEOUS_ROLES` for
          `each … simultaneously`, `runtime.values.content_noun` crossed with
          `types.Flavor` and singular/plural for the transfer and reveal filters,
          `resolve._COLLECTION_NOUNS` with `board_domains.BOARD_DOMAIN` for the
          position queries — pinned by `test_the_fixed_binder_spellings_come_
          from_their_registries`, with `_UNREACHABLE_SPELLINGS` carrying the one
          a registry admits and no game text reaches. The author-chosen /
          language-fixed split the guard's two diagnostics turn on is pinned to
          the same scrape by `test_the_author_chosen_split_classifies_every_
          binding_kind` — an unfiled kind would not fail, it would take the
          language-fixed branch and tell an author to edit a library over a
          binder they could have respelled;
          the DECLARATION-LEVEL axis from `resolve._game_bindings`'s own output
          over a game populating each of its buckets
          (`test_the_declaration_level_axis_covers_every_game_binding_bucket`),
          which is the domain of the names the shadow guard leaves to the
          injection guard;
          the BODY-SCOPING answer on each `_PARAM_BEARING` row read back off
          `resolve._rewrite`'s params-scoping arms
          (`test_every_param_bearing_row_agrees_with_the_pass_that_scopes_it`),
          so the row states a fact the pass owns rather than a comment with a
          type;
          the SLOT axis from `resolve._REFERENCE_SLOTS` (whose own key set is
          pinned to the AST by tests/test_reference_slots.py) intersected with
          the node kinds a library can hold — computed here by walking
          `n.Library`'s annotations, never listed — and filtered to the
          namespaces `_library_slot_names` sweeps, with every remaining
          reachable namespace pinned to a reason in `_LIBRARY_UNSWEPT`. Every axis is
          computed, never spelled: the probe NAMES come out of the registries
          too, which is the fix for how this file's first kernel move-type cell
          shipped vacuous (it probed `play_card`, which `stdlib/moves.py`
          documents as game-defined, so no edit could redden it).
covered:  the parse grid — item x neighbour, all 49 truncated cells executed by
          `test_a_truncated_library_item_may_not_absorb_its_neighbour`, all
          commanded REJECT, plus the 42 off-diagonal well-formed cells as its
          control; the diagonal's one real cell (a repeated `requires` block) is
          its own probe, the rest of the diagonal asserting nothing the
          off-diagonal does not. One truncated cell was open when this grid was
          written — `function_def` then `requires_block` — and its
          red-before-green transition is in this branch's history; the other 48
          are refused by brace structure rather than by the fix and are the
          sweep of the class. The builder's side of the same registry is
          `test_the_library_builder_files_every_item_kind` (7 cells, each item
          filed in its own `n.Library` field and no other) with
          `test_an_unhandled_library_item_is_loud` as the pin under it.
          The encapsulation grid — leak site x reference kind, all 35 cells
          executed by `test_a_library_may_not_reach_past_its_contract`, all
          commanded REJECT and all asserted to land in the LIBRARY file, each
          against a game that satisfies the contract AND happens to provide what
          the leak reaches for (without that second half the cells would be
          ordinary unresolved names and would prove nothing about the contract).
          Fourteen carry a control twin in `test_the_same_site_reaching_only_
          its_contract_is_accepted`, differing by one name; the other three
          columns have no legal counterpart to be a twin, and the two controls
          beside them establish the site.
          The SLOT grid — the same property reached through the bare-string
          door, one cell per reference slot the registry says a library can
          reach into a namespace the sweep covers
          (`test_a_library_may_not_name_what_it_does_not_have`), all commanded
          REJECT, each asserted to land in the library file AND to quote the
          leaked name — the second half is what tells the two zone cells apart,
          since they share a statement that leaks twice. Every cell was open
          before the sweep: a probe over all of them accepted, and the reddening
          edit was RUN, not reasoned about — emptying the `slot_leaks` loop
          fails exactly those cells and no others, and neutering `_slot_leaks`
          itself additionally fails the `card_literal` and `call` columns above,
          which is the evidence that the registry SUBSUMED the hand-list rather
          than landing beside it. Twelve carry a control twin
          (`test_the_same_slot_naming_what_the_library_has_is_accepted`); the
          other five have no legal counterpart, because a library declares no
          zones, no phases and no position domains. The axis is derived twice
          over — reachability from `n.Library` by walking the AST's annotations,
          intersected with the swept namespaces — and the namespaces it leaves
          out are pinned to a written reason by
          `test_every_reachable_reference_namespace_is_swept_or_excused`, so
          "not swept" cannot be spelled the same way as "not thought of".
          The MINIMALITY direction of the same sweep has its own cell
          (`test_the_bare_string_state_read_counts_toward_the_contract`): before
          it, `turns … again <var>` had no correct spelling at all — naming the
          variable in `requires` made the entry look dead to the ledger test
          below, and leaving it out was the leak. 24 cells were open before the guard and
          the `card_literal` column for a commit after it — both red-before-green
          transitions are in this branch's history. The `state` ROW was born
          green (its sweep shipped with the splice, a commit ahead of its
          cells), so it is not evidence of the same kind; its reddening edit was
          RUN rather than reasoned about — deleting `_library_reach`'s
          `provided_state` sweep fails those five cells and no others.
          The `requires` grid — multiplicity x shape, 9 cells executed by
          `test_a_requirement_is_answered_by_exactly_one_matching_declaration`,
          accepting in exactly one; the multiplicity-2 row was open and is the
          reason the grid exists. The three long-standing single-axis probes
          beside it stay, asserting the MESSAGES the grid only asserts the
          verdict of.
          The DISCRIMINATOR grid — 72 cells executed by
          `test_a_contract_entry_is_answered_from_the_block_its_type_names`,
          each commanding not just a verdict but the CURRENCY of the refusal: a
          shape no game could answer is refused against the library ALONE, and a
          well-formed entry the game does not answer lands on its `uses` line.
          57 of the 72 ran red before the implementation existed — 48 of them
          because the sentence could not be spelled at all — and the transition
          is in this branch's history. Beside it, the guard the discriminator
          RESTS on: a declared `type` or a `positions { }` name may not take a
          zone type's spelling (2 cells,
          `test_an_author_may_not_take_a_zone_type_name`, both red before the
          guard). Without it `type Hand = { … }` makes `requires { x : Hand }`
          mean two things and the classification picks one silently.
          The SHAPE-AGREEMENT grid — every `LIBRARY_ZONE_TYPES` member x
          {owner argument, none} x {indexed, not}, 64 cells executed by
          `test_a_contract_shape_is_refused_exactly_when_the_declaration_would_
          be`. `_check_contract_shapes` is a second implementation of
          `_resolve_zone`'s class rather than a call into it (different
          channels, different times), so what is pinned is that the two agree
          — 20 cells redden under disabling the owner-arity rule on one side
          alone. Position-indexed cells are absent by construction, not by
          omission: a contract cannot be position-indexed.
          The collision grid — definition kind x collision source, all 18 cells
          executed: `test_game_local_definition_may_not_shadow_a_library_one`
          (6), `test_two_libraries_may_not_define_the_same_name` (6), and
          `test_library_definition_against_the_kernel_namespace` (6, of which
          the 3 kinds with no kernel table skip with that reason named).
          Every cell's expected outcome is a commanded decision: The kernel row
          is `_ENGINE_REGISTRY_REJECTS`, where `False` is as deliberate as `True`.
          Born-green cells carry their reddening edit as `red under:` in the
          test docstring; the move-type accept was demonstrated red by extending
          `_check_library_collisions`'s engine leg to move_types.
          The read-only grid — write-site kind x state kind, 6 cells executed by
          `test_game_text_may_not_write_library_provided_state`, the 3 provided
          cells commanded REJECT (to the GAME's author, naming the variable and
          its library) and the 3 required cells commanded ACCEPT as the control
          that keeps the guard from passing by making provided state unwritable
          because unreachable. `test_game_text_may_read_library_provided_state`
          is the other control: read-only has to permit the read.
          The shadow grid — introducer sub-position x claim, every cell executed
          by `test_a_game_introduced_name_may_not_shadow_provided_state`. The
          `provided` column is commanded REJECT, except two rows that say why
          they are not: a DECLARED position domain is refused a door earlier by
          the injection guard and is commanded against that guard's sentence
          instead, and a Primitive parameter is a designed non-error commanded
          ACCEPT, because no DSL text sits inside its scope. Every commanded
          rejection ran red under `xfail(strict=True,
          raises=pytest.fail.Exception)` before the guard existed —
          constrained, so a broken fixture could not have counted as the
          designed red — and the transition is in this branch's history. The two
          accepting columns are different controls: `requires` holds the
          spelling fixed and moves only which library clause claims it, so a
          guard refusing every collision with a library NAME rather than a
          library-OWNED one fails there; `neither` proves each row's game text
          valid on its own. Both columns read the WHOLE bag (`_whole_bag`), not
          the diagnostic the stage leads with — the `already` row asserts that
          this guard adds no second sentence, and against `str(exc)` alone that
          assertion cannot fail. Around the grid, four claims it leans on, each
          executed rather than asserted, since "closed elsewhere" is the claim
          that rots: `test_a_library_may_bind_its_own_provided_name` bounds the
          guard from the other side (a library's own binders are spliced into
          the same Game the sweep walks, so a guard one line later would refuse
          a file the game's author cannot edit — its reddening edit was RUN);
          `test_a_declaration_level_collision_is_reported_by_another_guard`
          holds every bucket the guard skips to a diagnostic;
          `test_a_phase_local_declaration_of_a_provided_name_is_refused` and
          `test_no_provided_name_can_be_a_pronoun` hold the two name
          introductions that are not binders; and
          `test_a_piece_game_reveal_is_refused_before_it_binds` holds the one
          spelling a registry admits and no game text reaches. Beside them
          `test_one_node_spelling_a_name_twice_draws_one_sentence` holds what the
          grid's cells cannot see at all — how MANY times the bag says a thing,
          where a `let` binds twice from one span.
          The claim grid — 6 one-library cells
          (`test_one_library_claiming_a_state_name`) and 6 two-library cells
          (`test_two_libraries_claiming_one_state_name`), each asserting the
          MESSAGE and not merely the verdict, since three of the rejecting cells
          would also fail for the unrelated reason that the game does not declare
          the name. Two cells accept: a contract the game meets, and two
          libraries requiring one name. All 11 rejecting-or-newly-accepting cells
          across both grids were commanded before the guards existed and ran red
          under `xfail(strict=True)`; the transition is in this branch's history.
sampled:  the read-only guard's CONTAINER axis — six game-owned places a write
          can sit (`test_the_read_only_wall_reaches_every_container`), sampled
          rather than derived on purpose: the guard walks `_walk(game)`, total
          dataclass recursion over the whole Game, so reachability is one
          property of `_walk` and not a per-site dispatch that could cover some
          containers and miss others. The cells are regression evidence for that
          one property; the reddening edit was measured (narrowing the walk to
          `game.phases` fails all six).
          the `uses`-line failure modes (unknown library, repeated import) are
          one probe each — a single-axis error with no second axis to cross.
          The truncation axis takes ONE truncation per item (its last required
          slot); an item can also be cut mid-slot, but every such cut is a
          strict prefix of this one and cannot absorb more.
          Note the parse grid's counts move with `?library_item`: it is 8
          alternatives now (`state_block` joined), so 64 truncated cells and 56
          off-diagonal well-formed ones. The 30 `state_block` cells were green on
          arrival — `state` was already excluded from STRUCT_TYPE_NAME as an
          absorbable clause reachable from `?game_item` — which makes them the
          sweep of the class rather than new coverage.
residual: one on provided state, deliberate and named here so its absence from
          the probes is not read as an omission. There is no DEAD-PROVISION
          check: a `requires` entry no definition reads is dead contract and is
          guarded (`test_every_library_contracts_for_exactly_what_it_reaches`),
          but the mirror does not hold for provided state, because a provided
          variable exists precisely so it CAN be read from outside the library —
          by the importing game. Whether any game reads it is not a
          library-local question, so no library-local check can answer it, and a
          check that only asked "does the library read it?" would reject a
          legitimate provision. Not a gap the tier can close.

          none of the collision grid. The kernel row's three accepting cells are
          decisions, not gaps: kernel move types and a game's `move_type`
          definitions are disjoint consult paths that never share a namespace
          (`cardlang/stdlib/moves.py`), and types/defines/procedures have no
          kernel table at all. `test_the_accepting_move_type_cell_has_real_
          corpus_dependents` keeps the first decision honest by DERIVING its
          dependent games from the corpus — the hand-written version of that
          list named four games of which three were wrong, and named Stud, which
          the same change that wrote it had just made wrong.

          none of the shadow grid. Its one boundary is the other side of the same
          collision: a library may PROVIDE state spelled like a binder the
          language fixes, and nothing refuses it, so the grid's language-fixed
          rows prescribe a fix no guard makes the library take. That belongs at
          the library's own `state { }` declaration, addressed to its author —
          issue #499.

          ONE residual outside it, recorded in issue #138:

          1. SCOPE. The multiplicity grid proves a requirement is answered by
             exactly one declaration of the right shape; it does NOT prove that
             declaration is in scope where the library's definitions run. Moving
             Kuhn's `limit` into `phase deal` while the imported `bet` runs in
             `phase betting` passes resolve and typecheck and dies mid-playout
             on a bare KeyError. Deliberately not guarded here: the root cause is
             the general cross-phase state-scope hole (a plain game with no
             library reproduces it), and the guard bounding it is that a
             requirement declared NOWHERE is rejected, so what is unchecked is a
             declaration that exists but cannot be reached. The grid does not
             claim this cell — `_check_requires`'s docstring says what is
             checked and what is not, so the claim and the check agree.

          And ONE inside the slot grid, recorded in issue #170: `Transfer.item`
          is a game-fed slot (the item noun comes from the content flavor, which
          the component set fixes) and is NOT swept. The residual stands; its
          REASON has been replaced, because zone contracts falsified the old one.
          It used to be that every movement also names a zone, so the classified
          pass refused the statement before the noun could matter — probed with
          `move 1 coin from hand to pile` failing on `hand`. A library can now
          contract for `hand`, so that probe resolves clean and the noun IS
          reached. Re-probed, both ways: an unknown noun (`coin`) and a REAL but
          flavor-dependent one (`piece` in a card game) are each refused by
          typecheck's item-noun and flavor guards, to the LIBRARY's author. So
          the outcome holds on a guard that names the noun rather than on one that
          never got there — a stronger reason than the one it replaces. R4, and
          its `_LIBRARY_UNSWEPT` row says so.

One deliberate NON-error, recorded here so a later reader does not mistake its
absence from the probes for an omission: an imported definition a game never
uses is legal (decisions.md "Family libraries", the subset-vocabulary
paragraph). Kuhn imports `raise` and never offers it. That is the tier working
as designed — `uses` names a family, not a manifest — and its cost at the
OpenSpiel target is pinned to zero in
`tests/openspiel_ready/test_kuhn_poker.py`, not here: the claim is about the
action-space derivation, so it belongs in the channel of the adapter.
"""

from __future__ import annotations

import ast as pyast
import random
import typing
from collections.abc import Iterator
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

import pytest
from lark import Tree
from lark.exceptions import VisitError

from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN
from cardlang.builtins.functions import CALL_FUNCS, VALUE_NAMES
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.domains import DOMAINS, SIMULTANEOUS_ROLES, Role, role_names
from cardlang.libraries import library_names, load_library
from cardlang.parse import (
    _Builder,
    _transform,
    parse_library,
    parse_text,
    parse_to_tree,
)
from cardlang.resolve import (
    _AUTHOR_CHOSEN_BINDERS,
    _COLLECTION_NOUNS,
    _CONTEXTUAL_SLOTS,
    _LIBRARY_DEF_KINDS,
    _LIBRARY_UNSWEPT,
    _PARAM_BEARING,
    _REFERENCE_SLOTS,
    _STATE_WRITE_SITES,
    RESERVED_VALUE_NAMES,
    _Categories,
    _check_contract_shapes,
    _game_bindings,
    _library_reach,
    _library_slot_names,
    _resolve_zone,
    resolve,
)
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import content_noun
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.rules import stdlib_rules
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import KNOWN_TYPE_NAMES
from cardlang.types import Flavor
from tests.test_game_clause_guards import library_item_alternatives

# A minimal game that satisfies `poker_betting`'s whole `requires` contract. Every
# probe below is this game plus exactly one thing wrong, so a failure names the
# guard under test and nothing else.
#
# `acted` and `limit` are deliberately absent: the library PROVIDES those, so
# declaring them here would be the game/provided collision rather than the
# contract cell each probe means to test.
_GAME = """
game Probe {{
  uses poker_betting
  players: 2
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 2
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    level             : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 2
{extra_state}  }}
  phase play {{ {phase_state} {run} }}
  winner: highest stack
}}
{extra}
"""


def _game(
    *,
    extra: str = "",
    extra_state: str = "",
    phase_state: str = "",
    uses: str = "uses poker_betting",
) -> n.Game:
    # `poker_betting` holds a procedure, and an uninvoked procedure is its own
    # error — so a probe importing the REAL library has to run it, while one
    # importing a synthetic library must not, having no such procedure to run.
    run = "run open_street(1)" if "poker_betting" in uses else ""
    text = _GAME.format(
        extra=extra, extra_state=extra_state, phase_state=phase_state, run=run
    )
    text = text.replace("uses poker_betting", uses, 1)
    return parse_text(text, "probe.cardlang")


def _rejects(game: n.Game, *needles: str) -> None:
    """Resolve `game`, require it to fail, and require the message to say the
    thing the guard exists to say — not merely to fail somehow."""
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = str(exc.value)
    for needle in needles:
        assert needle in message, f"expected {needle!r} in:\n{message}"


def test_the_probe_game_is_otherwise_valid() -> None:
    """The control. Without it every probe below could be passing for the wrong
    reason — a vacuously-green suite is the defect class this file guards."""
    resolve(_game())


# --- the library file's own clause skeleton (parse layer) ---------------------
#
# Before a `uses` line can be wrong, the library FILE has to parse as the items
# its author wrote. `?library_item*` is a sibling sequence with no separator, so
# an item whose last required slot is left empty can complete itself from the
# item written below it — silently, with no `_ambig` node, because only one
# derivation is complete and the ambiguity budget counts ambiguity, not loss.
# The grid below is that class: every alternative, well-formed and truncated,
# crossed with every alternative as its neighbour.

# One minimally-valid source line per `?library_item` alternative, and the same
# item truncated at its last required slot. Keyed by grammar rule name so both
# grids stay derived from the registry; pinned by `test_library_item_registry_pin`.
_ITEM_WELL_FORMED: dict[str, str] = {
    "requires_block": "requires { y : Integer }",
    "state_block": "state { z : Integer = 1 }",
    "rule_def": "rule r { }",
    "move_type_def": "move_type m { effect { } }",
    "type_def": "type T = { x : Integer }",
    "define_def": "define d -> { a | b } { }",
    "function_def": "function f() = 1",
    "procedure_def": "procedure p() { }",
}

_ITEM_TRUNCATED: dict[str, str] = {
    "requires_block": "requires {",
    "state_block": "state {",
    "rule_def": "rule r {",
    "move_type_def": "move_type m {",
    "type_def": "type T = {",
    "define_def": "define d ->",
    "function_def": "function f() =",
    "procedure_def": "procedure p() {",
}

# grammar rule name -> the `n.Library` field the builder must file the item
# under. The third derived column: `parse.library()` files each child by one
# dispatch over the item kinds, so a kind with no arm is a loud stop rather
# than a clause dropped without a word.
_ITEM_FIELD: dict[str, str] = {
    "requires_block": "requires",
    "state_block": "state",
    "rule_def": "rules",
    "move_type_def": "move_types",
    "type_def": "types",
    "define_def": "defines",
    "function_def": "functions",
    "procedure_def": "procedures",
}


def test_library_item_registry_pin() -> None:
    """All three tables above are keyed by grammar rule name and must cover
    `?library_item` exactly — an eighth alternative added to the grammar fails
    here until it is given a well-formed spelling, a truncated spelling, and the
    field it is filed under.

    red under: add an alternative to `?library_item` in cardlang.lark."""
    alternatives = library_item_alternatives()
    for what, table in (
        ("well-formed", _ITEM_WELL_FORMED),
        ("truncated", _ITEM_TRUNCATED),
        ("field", _ITEM_FIELD),
    ):
        assert set(table) == alternatives, (
            f"the {what} table does not cover `?library_item`: "
            f"{sorted(set(table) ^ alternatives)}"
        )
    assert set(_ITEM_FIELD.values()) == {f.name for f in fields(n.Library)} - {
        "name",
        "span",
    }, "every `n.Library` payload field must be the home of exactly one item kind"


def _neighbour_cells(*, truncated: bool) -> list[object]:
    """The grid: every `?library_item` alternative crossed with every other as
    its neighbour."""
    items = sorted(library_item_alternatives())
    cells: list[object] = []
    for item in items:
        for follower in items:
            if not truncated and item == follower:
                # A repeat of the single-valued `requires` block is its own
                # error, probed separately below; the rest of the diagonal
                # asserts nothing the off-diagonal cells do not.
                continue
            cells.append(pytest.param(item, follower, id=f"{item}-then-{follower}"))
    return cells


@pytest.mark.parametrize("item,follower", _neighbour_cells(truncated=True))
def test_a_truncated_library_item_may_not_absorb_its_neighbour(
    item: str, follower: str
) -> None:
    """An item missing its required slot is a syntax error, always — never an
    item completed from the one below it, which would drop that one silently.

    Asserted at the PARSE layer deliberately: the absorbed reading IS a
    well-formed parse, so letting a later stage reject it for some other reason
    (an unknown struct type, an unresolved name) would leave this cell green
    while the neighbouring item had vanished.

    One cell was open when this grid was written: a `function_def` truncated to
    `function f() =`, whose empty `expr` slot read the `requires { y : Integer }`
    below it as a `struct_lit` — `NAME "{" NAME ":" expr "}"` being exactly a
    single-entry brace clause — leaving the contract silently empty. The other
    48 are refused by brace structure rather than by the fix, and are the sweep
    of the class.

    red under: delete `requires` from STRUCT_TYPE_NAME's exclusion list in
    cardlang.lark."""
    src = f"library L {{\n  {_ITEM_TRUNCATED[item]}\n  {_ITEM_WELL_FORMED[follower]}\n}}"
    with pytest.raises(DiagnosticError) as exc:
        parse_library(src, "L.cardlang")
    assert exc.value.diagnostic.span is not None, (
        "a parse-layer refusal must be located, not a bare error"
    )


@pytest.mark.parametrize("item,follower", _neighbour_cells(truncated=False))
def test_two_well_formed_library_items_both_survive(item: str, follower: str) -> None:
    """The control for the grid above. Without it every truncated cell could be
    passing because the FOLLOWER cannot appear there at all, rather than because
    the truncation is refused.

    red under: delete any dispatch arm from `parse.library()`."""
    src = (
        f"library L {{\n  {_ITEM_WELL_FORMED[item]}\n  "
        f"{_ITEM_WELL_FORMED[follower]}\n}}"
    )
    library = parse_library(src, "L.cardlang")
    for name in (item, follower):
        assert getattr(library, _ITEM_FIELD[name]), (
            f"`{_ITEM_WELL_FORMED[name]}` did not reach `Library.{_ITEM_FIELD[name]}`"
        )


def test_a_library_naming_a_card_says_why_it_may_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The message half of the grid's `card_literal` column. "Unresolved name"
    would be wrong twice over — the rank and suit are not names, and the reason
    is not that they failed to resolve but that a family has no one deck."""
    _patch_libraries(
        monkeypatch, {"leaky": _leaky("functions", "card_literal", leaking=True)}
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(_leak_host())
    message = str(exc.value)
    assert "names the card `Q of hearts`" in message, message
    assert "deck-agnostic" in message, message
    assert "docs/libraries/leaky.cardlang:" in message, message


def test_a_repeated_requires_block_is_rejected() -> None:
    """The `requires` diagonal of the control grid: `requires` is one of the
    library's two single-valued items, so a second block is the same defect a
    repeated game clause is — keeping the last would discard the first."""
    with pytest.raises(DiagnosticError) as exc:
        parse_library(
            "library L { requires { a : Integer } requires { b : Integer } }",
            "L.cardlang",
        )
    assert "one `requires` block" in str(exc.value)


def test_a_repeated_state_block_is_rejected() -> None:
    """The `state` diagonal, the other single-valued item. Swept with `requires`
    rather than left to the day a library wants two blocks: they are the two
    members of the same closed class (decisions.md "Closed-domain
    completeness").

    red under: delete the `if state is not None` arm from `parse.library()` —
    the second block then silently replaces the first."""
    with pytest.raises(DiagnosticError) as exc:
        parse_library(
            "library L { state { a : Integer = 1 } state { b : Integer = 2 } }",
            "L.cardlang",
        )
    assert "one `state` block" in str(exc.value)


@pytest.mark.parametrize("item", sorted(library_item_alternatives()))
def test_the_library_builder_files_every_item_kind(item: str) -> None:
    """Every `?library_item` the grammar accepts reaches the field it belongs
    in, and no other. `parse.library()` dispatches each child once over the item
    kinds; the `else` arm under that dispatch is what stops a kind the grammar
    grows and the builder does not know from being dropped without a word.

    red under: point any dispatch arm in `parse.library()` at the wrong list —
    the row for that kind then finds its own field empty and another populated."""
    library = parse_library(f"library L {{ {_ITEM_WELL_FORMED[item]} }}", "L.cardlang")
    home = _ITEM_FIELD[item]
    assert getattr(library, home), f"`{_ITEM_WELL_FORMED[item]}` never reached `{home}`"
    elsewhere = [f for f in _ITEM_FIELD.values() if f != home and getattr(library, f)]
    assert not elsewhere, f"it also landed in {elsewhere}"


def test_an_unhandled_library_item_is_loud() -> None:
    """The pin for the filters above: an eighth `?library_item` alternative that
    no filter matches must stop the build, not vanish. Simulated the way the
    grammar would deliver it — Lark's `Transformer` leaves a rule it has no
    callback for as a bare `Tree`, which is what an unclassified alternative
    hands the builder.

    An `AssertionError`, not a `DiagnosticError`, and matching `game()`'s arm
    exactly: a grammar alternative with no builder arm is a defect in this
    package, not a sentence the designer got wrong, so it may not be reported in
    the author-facing diagnostic channel.

    red under: delete the `else: raise AssertionError` arm from
    `parse.library()`."""
    tree = parse_to_tree("library L { }", "L.cardlang", start="library")
    tree.children.append(Tree("an_eighth_library_item", []))
    # Lark wraps a builder-callback exception in `VisitError`, and `_transform`
    # unwraps only `DiagnosticError` — deliberately, since that is the
    # author-facing channel and this is not. `game()`'s arm surfaces the same
    # way, which is what "the equivalent arm" means here.
    with pytest.raises(VisitError) as exc:
        _transform(_Builder("L.cardlang", 0), tree)
    assert isinstance(exc.value.orig_exc, AssertionError)
    assert "unexpected library item" in str(exc.value.orig_exc)


# --- the `uses` line itself ---------------------------------------------------


def test_unknown_library_is_rejected() -> None:
    _rejects(
        _game(uses="uses porker_betting"),
        "unknown library 'porker_betting'",
        "poker_betting",  # the message lists what IS available
    )


def test_repeated_uses_of_one_library_is_rejected() -> None:
    _rejects(
        _game(uses="uses poker_betting\n  uses poker_betting"),
        "already uses library 'poker_betting'",
    )


# --- the three-way collision matrix, swept over every definition kind ---------

# One minimally-valid source text per definition kind, named `collide`. The keys
# are checked against `_LIBRARY_DEF_KINDS` by the pin below, so a new kind cannot
# be added without a probe for it.
_DEF_SOURCE: dict[str, str] = {
    "rules": "rule collide { }",
    "move_types": "move_type collide { effect { } }",
    "types": "type collide = { x : Integer }",
    "defines": "define collide -> { a | b } { }",
    "functions": "function collide() = 1",
    "procedures": "procedure collide() { }",
}


def test_def_kinds_covers_every_library_field() -> None:
    """`_LIBRARY_DEF_KINDS` is the closed domain the collision guards sweep, so it
    must equal `n.Library`'s definition fields exactly. A seventh form added to
    the node without an entry there would ship unwalled; this is the static
    failure that prevents it.

    red under: add a field to `n.Library` without adding it to
    `_LIBRARY_DEF_KINDS`."""
    # `state` and `requires` are excluded because neither is a DEFINITION: they
    # are the library's two state clauses, whose own collision domain is the
    # claim grid (`_check_state_claims`), not this definition-splice one.
    node_fields = {f.name for f in fields(n.Library)} - {
        "name",
        "requires",
        "state",
        "span",
    }
    assert {field for field, _ in _LIBRARY_DEF_KINDS} == node_fields
    assert set(_DEF_SOURCE) == node_fields, (
        "every definition kind needs a collision probe below"
    )


def _kinds() -> Iterator[tuple[str, str]]:
    return iter(_LIBRARY_DEF_KINDS)


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_game_local_definition_may_not_shadow_a_library_one(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uses` imports, it does not inherit — so a game-local definition under an
    imported name is an error, not an override. This is the guard that keeps the
    tier composition rather than inheritance (decisions.md "Family libraries").

    red under: delete the `if definition.name in local` arm of
    `_check_library_collisions`."""
    library = parse_library(
        f"library probe_lib {{ {_DEF_SOURCE[field]} }}", "probe_lib.cardlang"
    )
    _patch_libraries(monkeypatch, {"probe_lib": library})
    _rejects(
        _game(uses="uses probe_lib", extra=_DEF_SOURCE[field]),
        f"{noun} 'collide' is defined by this game and also by library 'probe_lib'",
        "it does not inherit",
    )


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_two_libraries_may_not_define_the_same_name(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolution is flat, so neither library wins — silently picking one would
    make a game's meaning depend on `uses` order.

    red under: delete the `elif definition.name in from_libraries` arm of
    `_check_library_collisions`."""
    source = _DEF_SOURCE[field]
    _patch_libraries(
        monkeypatch,
        {
            "lib_a": parse_library(f"library lib_a {{ {source} }}", "lib_a.cardlang"),
            "lib_b": parse_library(f"library lib_b {{ {source} }}", "lib_b.cardlang"),
        },
    )
    _rejects(
        _game(uses="uses lib_a\n  uses lib_b"),
        f"{noun} 'collide' is defined by both library 'lib_a' and library 'lib_b'",
    )


# --- A library-injected name may not coincide with ANY game name -------------
#
# A `uses` import adds names to the game and cannot override, and the game's
# author never opens the library file. So a name the library injects that the
# game already uses for something ELSE is a silent trap: a bare reference the
# author writes meaning their own zone / suit / function resolves to the
# library's variable instead, or the other way about. The base language allows
# a game to reuse one name across its own namespaces (the author wrote both and
# can see both); the library case is refused precisely because one side is
# invisible.
#
# Completeness ledger (decisions.md "Closed-domain completeness")
# ---------------------------------------------------------------
# property:   for every way a library injects a name and every way a game binds
#             that same name, resolve refuses it, names the library, and is
#             located. One uniform verdict across the whole matrix — there is no
#             "harmless" coincidence, by design (see `residual`).
# domain:     INJECT x TARGET.
#             INJECT = the namespaces a library contributes to the game: its
#               provided `state`, plus every kind in `_LIBRARY_DEF_KINDS`.
#             TARGET = every namespace a bare name can resolve against, read off
#               `resolve._classify`'s precedence chain — state / zone / deck value
#               (suit|rank|direction) / the `function` bucket, which is
#               `VALUE_NAMES`, NOT the game's own functions (those resolve
#               as `Call`s, never bare) — plus the def kinds and position domains
#               that own a name without going through `_classify`.
# registry:   `_INJECT` is derived from `{"state"} | _LIBRARY_DEF_KINDS`. The
#               TARGET buckets are pinned two ways: `_game_bindings` is checked to
#               cover every value bucket `_categories` exposes
#               (`test_game_bindings_covers_every_resolvable_value_bucket` — the
#               pin that would have caught the `function`=VALUE_NAMES hole
#               by construction), and the grid's `_TARGET_NAME` is checked against
#               those buckets plus def kinds and positions
#               (`test_target_axis_names_every_resolvable_bucket`). Neither axis is
#               a hand-list compared to another hand-list.
# covered:    the full INJECT x TARGET cross, executed. Three guards share it and
#             the grid does not care which fires: same-kind def collisions are
#             `_check_library_collisions`, provided-vs-game-state is
#             `_check_state_claims`, and every off-diagonal cell (D3 = deck /
#             native values, D4 = zones / positions / cross-kind definitions) is
#             `_check_library_shadows_game`. All three name the library.
# sampled:    none — every cell is executed.
# residual:   library-vs-LIBRARY cross-kind. The property is injected-vs-GAME;
#             two libraries whose injected names cross KINDS (lib A provides
#             `foo`, lib B defines `function foo`) are not compared — only
#             same-kind lib-vs-lib is, by `_check_library_collisions` /
#             `_check_state_claims`. It is unreachable in the one-library corpus
#             (no game `uses` two), so it is recorded in issue #136 against the
#             shared name-registry deferral rather than guarded now: the honest
#             fix folds every library's injected names into one pool and is the
#             same table the `requires`-residual wants, not a second bolt-on.
#             The refusal that IS built is CONSERVATIVE by decision, like the
#             `Call` ban in `test_state_default_scope.py`: a coincidence is
#             refused even where precedence would make it harmless (a library
#             `function` named after a game `state` var, which `_classify` never
#             confuses), because the rule a designer holds is "a library may not
#             bring in a name you already use", not a table of safe pairs. No
#             corpus game pays for it — poker_betting's injected names touch none
#             of Kuhn/Leduc/Stud's.

# INJECT axis: name -> a library body binding NAME in that namespace. `filler`
# keeps the library non-trivial where the injected form alone would be empty.
_INJECT: dict[str, str] = {
    "state": "state {{ {n} : Integer = 0 }} function filler() = 1",
    "rules": "rule {n} {{ }} function filler() = 1",
    "move_types": "move_type {n} {{ effect {{ }} }} function filler() = 1",
    "types": "type {n} = {{ x : Integer }} function filler() = 1",
    "defines": "define {n} -> {{ a | b }} {{ }} function filler() = 1",
    "functions": "function {n}() = 1",
    "procedures": "procedure {n}() {{ }} function filler() = 1",
}


def _target_game(target: str, name: str) -> str:
    """A game that binds `name` in namespace `target`, imports `lib`, and is
    otherwise valid. Deck-value targets need a real deck value as the name and
    bind nothing extra — the clash is the injected name against the deck."""
    deck = "standard52"
    extra_zone = extra_state = extra_pos = tail = ""
    if target == "zone":
        extra_zone = f"{name} : Discard"
    elif target == "state":
        extra_state = f"{name} : Integer = 0"
    elif target == "position":
        extra_pos = f"positions {{ {name} : 1..4 }}"
    elif target in ("functions", "types", "move_types", "rules", "defines", "procedures"):
        tail = {
            "functions": f"function {name}() = 1",
            "types": f"type {name} = {{ x : Integer }}",
            "move_types": f"move_type {name} {{ effect {{ }} }}",
            "rules": f"rule {name} {{ }}",
            "defines": f"define {name} -> {{ a | b }} {{ }}",
            "procedures": f"procedure {name}() {{ }}",
        }[target]
    # target in {suit, rank, direction, native_value}: name IS a value the game
    # resolves against (deck / direction / native), and it binds nothing extra.
    return f"""
game G {{
  uses lib
  players: 2
  cards: {deck}
  max_length: 100
  {extra_pos}
  zones {{ deck : Deck  {extra_zone}  hand[player] : Hand<player> }}
  state {{ score[player] : Integer = 0  {extra_state} }}
  phase play {{ }}
  winner: highest score
}}
{tail}
"""


# TARGET axis: namespace -> the NAME to collide on. Most reuse one spelling;
# the deck-value and primitive-value targets must use a real member of the bucket
# they probe, so the name is drawn from the registry, not invented.
_VALUE_NAME = min(VALUE_NAMES)
_TARGET_NAME: dict[str, str] = {
    "state": "collide",
    "zone": "collide",
    "position": "collide",
    "functions": "collide",
    "types": "collide",
    "move_types": "collide",
    "rules": "collide",
    "defines": "collide",
    "procedures": "collide",
    "suit": "hearts",
    "rank": "Q",  # standard52 ranks are single glyphs (2..10, J, Q, K, A)
    "direction": "left",
    "native_value": _VALUE_NAME,  # `_classify`'s `function` bucket
}


def test_injectable_targets_cover_every_def_kind() -> None:
    """`_game_bindings`'s definition-kind targets must be exactly the kinds a
    library can inject, or a library could shadow the one game def kind the
    binding map forgot — which is how the `procedures` target first shipped
    unwalled here.

    red under: drop a def kind from `_INJECTABLE_TARGETS`."""
    from cardlang.resolve import _INJECTABLE_TARGETS, _LIBRARY_DEF_KINDS

    target_fields = {field for field, _ in _INJECTABLE_TARGETS}
    assert {field for field, _ in _LIBRARY_DEF_KINDS} <= target_fields
    # the two non-definition targets a bare name also resolves against
    assert {"zones", "positions"} <= target_fields
    # nouns agree, so the same-kind skip in `_check_library_shadows_game` lines up
    target_nouns = dict(_INJECTABLE_TARGETS)
    for field, noun in _LIBRARY_DEF_KINDS:
        assert target_nouns[field] == noun


def test_inject_axis_is_derived_not_listed() -> None:
    """The INJECT axis is exactly what a library can contribute: its provided
    state, plus every definition kind.

    red under: drop a kind from `_INJECT`."""
    from cardlang.resolve import _LIBRARY_DEF_KINDS as DEFS

    assert set(_INJECT) == {"state"} | {f for f, _ in DEFS}


def test_game_bindings_covers_every_resolvable_value_bucket() -> None:
    """The registry pin the TARGET axis answers to: every bare name `_categories`
    resolves for a game must appear in `_game_bindings`, so a value bucket added
    to `_categories` (a new deck-derived namespace, another kernel table wired
    into `functions`) cannot slip past the shadow guard uncovered. This is the
    check that would have caught the `functions`-bucket = `VALUE_NAMES`
    hole by construction, rather than by an audit noticing a hand-list lied.

    red under: delete the `VALUE_NAMES` loop from `_game_bindings` (drops
    the native-value bucket), or a deck-value loop (drops ranks/suits)."""
    from cardlang.resolve import _categories, _game_bindings

    probe = parse_text(
        """
game Cover {
  players: 2
  cards: standard52
  ranking: aces high
  positions { slot : 1..4 }
  zones { deck : Deck  discard : Discard  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  marker : Integer = 0 }
  phase play { }
  winner: highest score
}
""",
        "cover.cardlang",
    )
    cats = _categories(probe)
    resolvable = (
        cats.state_vars
        | cats.zones
        | cats.enums
        | cats.functions
        | cats.ranks
        | cats.suits
    )
    bindings = set(_game_bindings(probe))
    missing = resolvable - bindings
    assert not missing, f"_game_bindings misses resolvable names: {sorted(missing)}"


def test_target_axis_names_every_resolvable_bucket() -> None:
    """The grid's TARGET axis is the resolvable buckets (state / zone / deck
    values / native values) plus the def kinds and positions that own a name
    outside `_classify`. Stated against the buckets, not a bare re-listing, so a
    new target the guard gains is a failure here until the grid exercises it.

    red under: drop a namespace from `_TARGET_NAME`."""
    from cardlang.resolve import _LIBRARY_DEF_KINDS as DEFS

    resolvable = {"state", "zone", "suit", "rank", "direction", "native_value"}
    structural = {"position"} | {f for f, _ in DEFS}
    assert set(_TARGET_NAME) == resolvable | structural


@pytest.mark.parametrize("inject", sorted(_INJECT))
@pytest.mark.parametrize("target", sorted(_TARGET_NAME))
def test_a_library_may_not_inject_a_name_the_game_already_uses(
    inject: str, target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every cell of INJECT x TARGET: a library injecting NAME while the game
    already uses NAME is refused, and the message names the library — the half
    D4a got wrong, blaming the game's own declaration and never mentioning the
    import.

    red under: delete `_check_library_shadows_game` (fails every off-diagonal
    cell); the same-kind and provided-vs-state cells stay green on their own
    guards, which is why this grid does not stand in for their red-unders."""
    name = _TARGET_NAME[target]
    lib = parse_library(
        "library lib { " + _INJECT[inject].format(n=name) + " }",
        "docs/libraries/lib.cardlang",
    )
    _patch_libraries(monkeypatch, {"lib": lib})
    _rejects(parse_text(_target_game(target, name), "probe.cardlang"), "library 'lib'")


def _engine_registry_member(field: str) -> str | None:
    """A real member of one of the engine's own name registries that shares a
    namespace with this definition kind, drawn FROM the registry, or None when
    no registry exists for the kind. Only one of the three is the engine leg (the
    parsed rules fragment); the others are the native call declarations and a
    kernel table. Derived rather than spelled: a hand-written probe name can
    silently not be a member of the registry it claims to probe, which is
    exactly how this file's first move-type cell shipped vacuous (it probed
    `play_card`, which `stdlib/moves.py` documents as game-defined)."""
    registry: dict[str, frozenset[str] | set[str]] = {
        "rules": frozenset(stdlib_rules()),
        "functions": frozenset(CALL_FUNCS),
        "move_types": frozenset(LIBRARY_MOVE_TYPES),
    }
    members = registry.get(field)
    return min(members) if members else None


# The engine leg of the collision grid: for each definition kind, whether a
# library defining something under a REAL engine name of that kind is rejected.
# `engine` because the three kinds reach three different namespaces — the
# stdlib rule index, the native `CALL_FUNCS`, and the kernel table
# `LIBRARY_MOVE_TYPES` — so no narrower word covers the axis.
# `False` is as much a commanded decision as `True` — move_types are a
# deliberate non-collision (two disjoint consult paths), and the three kinds
# with no engine registry cannot collide at all.
_ENGINE_REGISTRY_REJECTS: dict[str, bool] = {
    "rules": True,
    "functions": True,
    "move_types": False,
    "types": False,
    "defines": False,
    "procedures": False,
}


def test_stdlib_grid_covers_every_definition_kind() -> None:
    """Both axes of the stdlib leg are derived, so the grid below cannot silently
    stop covering a kind.

    red under: drop any key from `_ENGINE_REGISTRY_REJECTS`."""
    assert set(_ENGINE_REGISTRY_REJECTS) == {field for field, _ in _LIBRARY_DEF_KINDS}
    # A kind commanded to reject must have a registry to collide with, and a
    # kind commanded to accept because no registry exists must really have none.
    assert {f for f in _ENGINE_REGISTRY_REJECTS if _engine_registry_member(f)} == {
        "rules",
        "functions",
        "move_types",
    }


@pytest.mark.parametrize("field,noun", list(_kinds()), ids=lambda v: str(v))
def test_library_definition_against_the_kernel_namespace(
    field: str, noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kernel row of the collision grid, run for every definition kind rather
    than written out for the two that reject.

    The accepting cells are the load-bearing ones. kernel move types and a game's
    `move_type` definitions are disjoint consult paths that never share a
    namespace, so a library defining one under a kernel move-type name must NOT be an
    error: six corpus games depend on that (see `_kernel_move_type_games`).

    red under: extend `_check_library_collisions`'s engine leg to move_types, or
    delete its `stdlib_rules()` leg."""
    name = _engine_registry_member(field)
    if name is None:
        pytest.skip(f"no kernel table shares a namespace with {noun}s")
    source = _DEF_SOURCE[field].replace("collide", name)
    _patch_libraries(
        monkeypatch,
        {"probe_lib": parse_library(f"library probe_lib {{ {source} }}", "pl.cardlang")},
    )
    game = _game(uses="uses probe_lib")
    if _ENGINE_REGISTRY_REJECTS[field]:
        _rejects(game, f"library 'probe_lib' defines {noun} '{name}'", "shadows the")
    else:
        resolve(game)


def _kernel_move_type_games() -> list[str]:
    """Corpus games that define a `move_type` under a kernel move-type name — the
    games the accepting move_types cell above protects. Derived from the corpus,
    because the hand-written version of this list named four games of which three
    were wrong, and one (Stud) was made wrong by the very change that wrote it."""
    games_dir = Path(__file__).resolve().parent.parent / "docs" / "games"
    hits = []
    for path in sorted(games_dir.glob("*.cardlang")):
        game = parse_text(path.read_text(), path.name)
        if {m.name for m in game.move_types} & set(LIBRARY_MOVE_TYPES):
            hits.append(path.stem)
    return hits


def test_the_accepting_move_type_cell_has_real_corpus_dependents() -> None:
    """The accepting cell is only a design decision if something depends on it;
    otherwise it is an untested branch wearing a decision's name.

    red under: add the kernel move-type leg to `_check_library_collisions` — every
    game below then fails to resolve."""
    dependents = _kernel_move_type_games()
    assert len(dependents) >= 3, (
        f"only {dependents} still define a move type under a kernel move-type name; "
        f"if this "
        f"reaches zero the non-collision is no longer load-bearing and the "
        f"residual ledger row should be revisited rather than left standing"
    )


# --- the `requires` contract --------------------------------------------------
#
# A requirement is answered by exactly ONE declaration of the right shape. Both
# halves of that are a grid: how MANY declarations of the name the game holds,
# and what SHAPE the declaration answering it has. The shape axis is derived —
# it is the field set `_check_requires` compares between a `RequireDecl` and the
# `StateDecl` that answers it, which is `n.RequireDecl`'s own fields minus the
# name it is keyed by and its span.

# One `state { }` line declaring `raise_cap` per shape: "matching" is what
# `poker_betting` asks for, and each other key breaks EXACTLY the field it names
# and nothing else. Pinned to `n.RequireDecl` by the test below.
_SHAPE_TEXT: dict[str, str] = {
    "matching": "raise_cap : Integer = 2",
    "type_name": "raise_cap : Boolean = false",
    "index": "raise_cap[player] : Integer = 2",
    "optional": "raise_cap : Integer? = none",
}


def test_shape_axis_covers_every_compared_field() -> None:
    """`_check_requires` compares a requirement against a declaration field by
    field, so the shape axis must be those fields exactly. A field added to
    `n.RequireDecl` — a new dimension the contract can disagree on — fails here
    until the grid gets a row that breaks it.

    red under: add a field to `n.RequireDecl` without adding a `_SHAPE_TEXT`
    row for it."""
    compared = {f.name for f in fields(n.RequireDecl)} - {"name", "span"}
    # `type_args` is the ZONE leg's field. A `state { }` line has no spelling
    # for it, so no row of this grid could break it — a contract carrying one is
    # refused against the library alone, before any declaration is compared
    # (`_check_contract_shapes`), and the crossed cell is
    # `test_a_contract_entry_is_answered_from_the_block_its_type_names`
    # ["state-args1-*"]. Subtracted here rather than silently absent, so the
    # exclusion is a claim this test makes and not a row someone forgot.
    assert "type_args" in compared
    assert set(_SHAPE_TEXT) - {"matching"} == compared - {"type_args"}


def _requires_cells() -> list[object]:
    """Multiplicity x shape, where the shape is the LAST-written declaration's:
    at multiplicity 1 that is the only one, and at multiplicity 2 it is a
    phase-local one written under a game-level declaration left MATCHING. That
    asymmetry is the point — a second declaration whose shape is wrong is
    invisible to a first-wins contract precisely because the first one is
    right. Multiplicity 0 takes one cell, not four: with no declaration at all
    there is nothing for a shape to be wrong about."""
    cells: list[object] = [pytest.param(0, "matching", id="absent")]
    for shape in sorted(_SHAPE_TEXT):
        cells.append(pytest.param(1, shape, id=f"once-{shape}"))
        cells.append(pytest.param(2, shape, id=f"twice-{shape}"))
    return cells


@pytest.mark.parametrize("multiplicity,shape", _requires_cells())
def test_a_requirement_is_answered_by_exactly_one_matching_declaration(
    multiplicity: int, shape: str
) -> None:
    """The one accepting cell is (exactly one declaration, matching shape).

    The multiplicity-2 row is the reason this grid exists. `_check_requires`
    used to take the FIRST declaration it walked, while `typecheck` and
    `runtime/driver.py` both take the LAST — so a game declaring `raise_cap :
    Integer` at game level and `raise_cap : Boolean` in a phase passed this
    contract on the Integer and then bound the Boolean. Neither bias is the fix:
    the question is scoped, not flat — a shadow in the phase where the library
    runs makes last-wins right, a shadow in some other phase makes first-wins
    right — so the contract refuses to answer it at all. Cross-block shadowing
    stays legal in general (`_check_duplicate_names`); it is refused only for a
    `requires`d name, which is an interface rather than game-private state
    (decisions.md "Family libraries", the metamorphic-rename carve-out).

    red under: replace the multiplicity guard in `_check_requires` with either
    bias — `declared[want.name][0]` or `[-1]`."""
    game = _game(
        phase_state=f"state {{ {_SHAPE_TEXT[shape]} }}" if multiplicity == 2 else "",
    )
    if multiplicity == 0:
        assert game.state is not None
        game = replace(
            game,
            state=replace(
                game.state,
                decls=tuple(d for d in game.state.decls if d.name != "raise_cap"),
            ),
        )
    elif multiplicity == 1 and shape != "matching":
        game = _reshaped(game, shape)
    if (multiplicity, shape) == (1, "matching"):
        resolve(game)
        return
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    assert "probe.cardlang:3:" in str(exc.value), (
        "every requires failure lands on the `uses` line, to the game's author"
    )


def _reshaped(game: n.Game, shape: str) -> n.Game:
    """Re-declare the game-level `raise_cap` with the shape's own text, through a
    real parse so the probe never hand-builds a declaration the parser would
    not."""
    assert game.state is not None
    replacement = _parse_state_decl(_SHAPE_TEXT[shape])
    decls = tuple(
        replace(replacement, span=d.span) if d.name == "raise_cap" else d
        for d in game.state.decls
    )
    return replace(game, state=replace(game.state, decls=decls))


def _parse_state_decl(text: str) -> n.StateDecl:
    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 zones {{ deck : Deck }} "
        f"state {{ {text} }} }}",
        "decl.cardlang",
    )
    assert game.state is not None
    return game.state.decls[0]


# --- a requirement malformed in the library's own text ------------------------
#
# Every field of a requirement that can be MALFORMED where the library author
# wrote it, so the contract comparison would otherwise render the malformation
# as a MISMATCH against the game — blaming the game author for a defect in a
# file they did not write. `None` means the field cannot be malformed, with the
# reason, so a new field on `n.RequireDecl` fails the pin below until someone
# decides which it is.
_MALFORMED_REQUIREMENT: dict[str, str | None] = {
    # Not an indexable role. Guarded by `resolve._check_require_indexes`.
    "index": "q[hearts] : Integer",
    # A type the library cannot resolve on its own. Guarded by
    # `resolve._check_library_encapsulation`.
    "type_name": "q : Integar",
    # Cannot be malformed: `?` is present or absent and the grammar admits no
    # third state, so there is no ill-formed value for the comparison to
    # misreport.
    "optional": None,
    # A zone type carrying the wrong number of owner arguments. Guarded by
    # `resolve._check_contract_shapes`, which reports at the requirement's span
    # like the other two — so the suppression covers it with nothing added,
    # which is the property the span-matching design was chosen for.
    "type_args": "q : Hand",
}


def test_the_malformed_requirement_axis_covers_every_compared_field() -> None:
    """The class is every field the contract COMPARES, not the one a review
    happened to name.

    red under: add a field to `n.RequireDecl` without adding a
    `_MALFORMED_REQUIREMENT` row for it."""
    compared = {f.name for f in fields(n.RequireDecl)} - {"name", "span"}
    assert set(_MALFORMED_REQUIREMENT) == compared


@pytest.mark.parametrize("declared", [True, False], ids=["declared", "undeclared"])
@pytest.mark.parametrize(
    "field",
    sorted(k for k, v in _MALFORMED_REQUIREMENT.items() if v is not None),
)
def test_a_malformed_requirement_is_not_also_blamed_on_the_game(
    field: str, declared: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A requirement wrong in the LIBRARY's text produces the library's
    diagnostic and nothing addressed to the game.

    Without the suppression the contract compares the malformed requirement
    anyway and derives a second error that is worse than useless. Both members
    of the class show it, in both directions: with the name declared, a
    non-role index renders as "a scalar" and an unresolvable type renders as
    the GAME's type being wrong; with it undeclared, the game author is told to
    add a declaration the language would refuse.

    Asserted as the ABSENCE of the game's source name across the whole rendered
    bag, not as a message count: the point is that nothing was blamed on the
    game, and a future third diagnostic in the library's own channel should
    not redden this.

    red under: delete the `want.span in malformed` guard from
    `resolve._check_requires`."""
    library = parse_library(
        f"""library probe_lib {{
  state {{ own : Integer = 0 }}
  requires {{ {_MALFORMED_REQUIREMENT[field]} }}
  procedure bump() {{ own := 1 }}
}}""",
        "probe_lib.cardlang",
    )
    _patch_libraries(monkeypatch, {"probe_lib": library})
    game = _game(
        uses="uses probe_lib",
        phase_state="run bump()",
        extra_state="    q : Integer = 0\n" if declared else "",
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    rendered = "\n".join(
        [str(exc.value), *(getattr(exc.value, "__notes__", []) or [])]
    )
    assert "probe_lib.cardlang:" in rendered, rendered
    assert "probe.cardlang:" not in rendered, (
        f"a requirement malformed in the library was also reported against the "
        f"game:\n{rendered}"
    )


def test_unmet_requirement_is_reported_on_the_uses_line() -> None:
    """The diagnostics-channel requirement: the author wrote `uses`, so that is
    where the failure lands — not as an undeclared `raise_cap` deep inside
    library text they never typed."""
    game = _game()
    stripped = replace(
        game,
        state=replace(
            game.state,
            decls=tuple(d for d in game.state.decls if d.name != "raise_cap"),
        ),
    ) if game.state else game
    _rejects(
        stripped,
        "library 'poker_betting' requires state `raise_cap : Integer`",
        "does not declare",
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(stripped)
    assert "probe.cardlang:3:" in str(exc.value), (
        "the requires failure must carry the `uses` line's span"
    )


def test_requirement_declared_at_the_wrong_type_is_rejected() -> None:
    _rejects(
        _mistyped("raise_cap", type_name="Boolean", default="false"),
        "library 'poker_betting' requires state `raise_cap : Integer`",
        "declares it as `Boolean`",
    )


def test_requirement_declared_with_the_wrong_arity_is_rejected() -> None:
    """Per-player where the library wants a scalar. Silently accepting this would
    make every library read of `raise_cap` a subscript-less read of a family."""
    _rejects(
        _mistyped("raise_cap", index="player"),
        "requires state `raise_cap : Integer` to be a scalar",
        "declares it as per-player",
    )


def test_a_requirement_declared_twice_says_so() -> None:
    """The message half of the multiplicity grid's rejecting row: it must name
    the count and the fix, not merely fail. A designer who shadowed on purpose
    has to be told that this particular name may not be shadowed."""
    _rejects(
        _game(phase_state="state { raise_cap : Integer = 2 }"),
        "requires state `raise_cap : Integer`, which game 'Probe' declares 2 times",
        "keep a single declaration of 'raise_cap'",
    )


def _mistyped(
    name: str,
    *,
    type_name: str = "Integer",
    index: str | None = None,
    default: str = "2",
) -> n.Game:
    game = _game()
    assert game.state is not None
    decls = tuple(
        replace(d, type_name=type_name, index=index, default=parse_default(default))
        if d.name == name
        else d
        for d in game.state.decls
    )
    return replace(game, state=replace(game.state, decls=decls))


def parse_default(literal: str) -> n.Expr:
    """The default expression for a rewritten state decl, taken from a real parse
    so the probe never hand-builds an expression shape the parser would not."""
    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 zones {{ deck : Deck }} "
        f"state {{ x : Integer = {literal} }} }}",
        "default.cardlang",
    )
    assert game.state is not None
    return game.state.decls[0].default


# --- the contract is SUFFICIENT, not merely advisory --------------------------
#
# `requires` is only a contract if a game that meets it in full is enough. That
# is a property of the LIBRARY, checked once against the library's own
# namespaces, not of any game that imports it: a leak reaching past the contract
# resolves fine against a game that happens to declare the extra name and fails
# against a game that satisfies the contract exactly — reported inside library
# text the author never wrote, which is the very misaddressed failure the contract
# exists to prevent.
#
# The grid is definition kind x reference kind: WHERE the leak is written (the
# six kinds of `_LIBRARY_DEF_KINDS`, so no definition form is checked less than
# another) times WHAT it reaches for. The reference axis is derived from
# `_Categories` — the namespaces a bare name resolves against — taking the
# fields an importing GAME can populate but a library cannot: `state_vars`
# beyond the contract, `zones`, and the deck-derived `enums`/`ranks`/`suits`,
# reachable both as a bare value name and inside a card literal, whose rank and
# suit are plain strings rather than classified names. `locals` and the stdlib
# `functions` are not on the axis: both are the same for a library as for a
# game, so neither is a channel the game can feed. Calls are the axis's second
# half, since a `Call`'s func is a name the game's own definitions could supply.

# One leak site per definition kind, with a `{read}` slot for the reference. Each
# site puts `{read}` where any of the five spellings is grammatical, so the axes
# are genuinely crossed rather than paired off. The `procedures` site carries a
# move type that runs it, because an uninvoked procedure is separately an error
# and the cell must fail for its OWN reason.
_LEAK_SITE: dict[str, str] = {
    "rules": "rule r {{ applies_when: {read} is not none }}",
    "move_types": (
        "move_type m {{ effect "
        "{{ declared_thing := if {read} is not none then 1 else 2 }} }}"
    ),
    "types": "type T = {{ x : Integer }} derived {{ y = {read} }}",
    "defines": (
        "define d -> {{ a | b }} "
        "{{ if {read} is not none {{ produce a }} else {{ produce b }} }}"
    ),
    "functions": "function f() = {read}",
    "procedures": (
        "procedure p() {{ declared_thing := if {read} is not none then 1 else 2 }} "
        "move_type runner {{ effect {{ run p() }} }}"
    ),
    # The seventh site is not a definition: a PROVIDED variable's default is an
    # expression like any other, and leaks like any other.
    "state": "state {{ provided_thing : Integer = {read} }}",
}

# reference kind -> (the leaking spelling, the contracted spelling that is its
# control, or None where no legal counterpart exists). Where a control exists it
# is the same shape in the same slot, so a cell that rejects can only be
# rejecting the leak. Three kinds have no control by construction: a library
# holds no zones and names no deck, so there is no in-contract way to write a
# zone name, a suit, or a card — for those the guard is total, and the site's
# own validity is established by the `state` and `call` controls beside them.
_LEAK_READS: dict[str, tuple[str, str | None]] = {
    "state": ("undeclared_thing", "declared_thing"),
    "call": ("undeclared_helper()", "contracted_helper()"),
    "zone": ("hand", None),
    "deck_value": ("hearts", None),
    "card_literal": ("(Q of hearts)", None),
}


def test_leak_sites_cover_every_expression_bearing_clause() -> None:
    """Every library clause that can hold an EXPRESSION can leak through it, so
    the grid's site table must be exactly those clauses — the six definition
    kinds plus `state`, whose defaults are expressions.

    `requires` is the one clause excluded, and not by omission: a
    `require_decl` is a name, an index and a type name, with no expression slot
    to leak through. That is why the axis is derived by SUBTRACTING it from
    `n.Library`'s fields rather than by listing the six kinds — a clause added
    to the library with an expression in it joins this grid automatically.

    red under: drop a key from `_LEAK_SITE`."""
    expression_bearing = {f.name for f in fields(n.Library)} - {
        "name",
        "span",
        "requires",
    }
    assert set(_LEAK_SITE) == expression_bearing
    assert {field for field, _ in _LIBRARY_DEF_KINDS} < expression_bearing


# reference kind -> the `_Categories` field(s) it reaches through. `call` has no
# entry: a `Call`'s func is not classified against `_Categories` at all, so it is
# the axis's one non-namespace channel.
_AXIS_NAMESPACE: dict[str, frozenset[str]] = {
    "state": frozenset({"state_vars"}),
    "zone": frozenset({"zones"}),
    "deck_value": frozenset({"enums"}),
    "card_literal": frozenset({"ranks", "suits"}),
}


def test_the_reference_axis_covers_every_game_fed_namespace() -> None:
    """`_Categories` is the registry of namespaces a bare name resolves against,
    and the grid's reference axis must cover every field of it an importing GAME
    can feed. Two are excluded and neither is a gap: `locals` is whatever the
    body binds for itself, and `functions` is the native value set, identical for
    a library and a game — no game can put anything into either.

    Derived rather than spelled, because spelling it is how this axis went wrong:
    it began as {state, call} and silently omitted zones, deck values and card
    literals — three channels the design forbids a library, one of which the
    guard did not in fact refuse.

    red under: add a field to `_Categories`, or drop a key from
    `_AXIS_NAMESPACE`."""
    # `flavor` joins locals/functions as a non-channel: it is the game's
    # scalar content flavor ("card"/"piece"), not a namespace of names a
    # library reference could reach or shadow.
    game_fed = {f.name for f in fields(_Categories)} - {"locals", "functions", "flavor"}
    covered: set[str] = set()
    for reached in _AXIS_NAMESPACE.values():
        covered |= reached
    assert covered == game_fed, (
        f"reference axis reaches {sorted(covered)}, `_Categories` offers "
        f"{sorted(game_fed)}"
    )
    assert set(_AXIS_NAMESPACE) | {"call"} == set(_LEAK_READS)


def _leaky(field: str, kind: str, *, leaking: bool) -> n.Library:
    spellings = _LEAK_READS[kind]
    read = spellings[0] if leaking else spellings[1]
    assert read is not None
    return parse_library(
        "library leaky { requires { declared_thing : Integer } "
        "function contracted_helper() = declared_thing "
        f"{_LEAK_SITE[field].format(read=read)} }}",
        "docs/libraries/leaky.cardlang",
    )


# A game that satisfies `leaky`'s contract AND happens to provide everything the
# leaks reach for — the undeclared state name, the helper function, a `hand`
# zone, and a deck holding the queen of hearts. That second half is what makes
# the cells meaningful: without it they would fail as ordinary unresolved names
# and prove nothing about the contract.
_LEAK_GAME = """
game Host {
  uses leaky
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state {
    declared_thing   : Integer = 0
    undeclared_thing : Integer = 0
    score[player]    : Integer = 0
  }
  phase play { }
  winner: highest score
}
function undeclared_helper() = 1
"""


def _leak_host() -> n.Game:
    return parse_text(_LEAK_GAME, "host.cardlang")


def _leak_cells() -> list[object]:
    """The full cross. The `card_literal` column was the last one open: a card
    literal's rank and suit are plain strings on the node, not classified
    `NameRef`s, so the classification sweep could not see them and they needed a
    channel of their own."""
    return [
        pytest.param(field, kind, id=f"{field}-{kind}")
        for field in sorted(_LEAK_SITE)
        for kind in sorted(_LEAK_READS)
    ]


@pytest.mark.parametrize("field,kind", _leak_cells())
def test_a_library_may_not_reach_past_its_contract(
    field: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every leak is refused, wherever it is written and whatever it reaches
    for, and refused to the LIBRARY's author — the span is in the library
    file, because the library author is who must fix it. A game cannot: the
    only thing it could do is provide the name, which is exactly the accident
    that made the leak invisible.

    red under: delete the `_check_library_encapsulation` call from
    `_apply_uses`. The `state` row has its own, narrower reddening edit,
    verified rather than assumed: deleting the `provided_state` sweep from
    `_library_reach` fails exactly those five cells and no others."""
    _patch_libraries(monkeypatch, {"leaky": _leaky(field, kind, leaking=True)})
    with pytest.raises(DiagnosticError) as exc:
        resolve(_leak_host())
    message = str(exc.value)
    assert "docs/libraries/leaky.cardlang:" in message, (
        f"the failure must land in the library file, not in the game:\n{message}"
    )
    assert "library 'leaky'" in message


# The control row holds only for sites whose expression runs during PLAY, when
# the whole contract is live. `state` is the one site that runs at DECLARE time,
# and reaching the contract there is refused however the read is spelled — so it
# is carved out of the row below and gets its own three-outcome test.
#
# Derived, not listed: the six definition kinds are the play-time sites, and
# subtracting them from the site table leaves exactly the declare-time one. A
# site added to `_LEAK_SITE` joins the control row automatically, and a second
# declare-time site would have to be classified here before it could pass.
_DECLARE_TIME_SITES = set(_LEAK_SITE) - {field for field, _ in _LIBRARY_DEF_KINDS}


def test_exactly_one_leak_site_runs_at_declare_time() -> None:
    """red under: add `state` back to `_LIBRARY_DEF_KINDS`, or drop the
    subtraction and hard-code the carve-out."""
    assert _DECLARE_TIME_SITES == {"state"}


@pytest.mark.parametrize(
    "field,kind",
    [
        (f, k)
        for f in sorted(set(_LEAK_SITE) - _DECLARE_TIME_SITES)
        for k in sorted(_LEAK_READS)
        if _LEAK_READS[k][1] is not None
    ],
    ids=lambda v: str(v),
)
def test_the_same_site_reaching_only_its_contract_is_accepted(
    field: str,
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """The control row. Each cell is its leaking twin with one name swapped —
    a contracted state variable for the undeclared one, a library-defined
    function for the game's — so a rejecting leak cell can only be rejecting
    the leak and not the site.

    Every cell here is a body that runs during play. The declare-time site is
    excluded and covered by `test_a_provided_default_may_not_reach_the_contract`
    — NOT dropped: both of its cells used to sit in this row commanding a defect
    accepted, which is the whole reason that test exists.

    red under: make `_check_library_encapsulation` reject anything it classifies
    rather than only what it fails to."""
    if field == "rules":
        # A library CANNOT declare a rule at all right now, so this control
        # cell has no contract-clean form to be the twin of. A rule must carry
        # an enforceable `demands:`/`exempts:` to reach a decision site
        # (tests/test_rule_surface_reachability.py), an enforceable body must
        # name a zone, and `requires { }` contracts state only — so every
        # writable body here either enforces nothing or leaks. Marked rather
        # than deleted: the cell is real and unreachable, and strict xfail
        # turns it loud the day issue #177 lets a contract name a zone.
        request.node.add_marker(
            pytest.mark.xfail(
                raises=DiagnosticError,
                strict=True,
                reason="issue #177: a library contract cannot name a zone, so "
                "no library rule can be both enforceable and contract-clean",
            )
        )
    _patch_libraries(monkeypatch, {"leaky": _leaky(field, kind, leaking=False)})
    resolve(_leak_host())


@pytest.mark.parametrize("kind", sorted(k for k, v in _LEAK_READS.items() if v[1]))
def test_a_provided_default_may_not_reach_the_contract(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declare-time site's own row, and the correction of a wrong verdict.

    Both cells shipped in the control row above, commanding ACCEPTED. Both were
    wrong: `check_dsl` passed and the playout died on a bare `KeyError` from
    `runtime/state.py`. Provided state is spliced in FRONT of the game's own
    (`resolve._apply_uses`), so a required name — which only the game can
    declare — does not exist yet when a provided default runs. Reaching it
    directly (`state`) and reaching it through a library function that reads it
    (`call`) are the two spellings, and the second is why the fix could not be
    a scope rule alone: the read lives in the callee's body, which the walk over
    a default never enters.

    The two cells are pinned by DIFFERENT guards, and the `state` cell says which
    on purpose. Refusal alone does not distinguish them: the general
    declare-order guard also refuses that sentence, also with a span in this
    file, so an assertion on span-and-raise stays green with the library check
    deleted — verified by deleting it. What only the library check produces is
    the word `contract`, and with it the advice decisions.md commits to. The
    general guard can only say "declare it earlier", which is the one thing a
    library author cannot do.

    red under: delete the provided-default loop from
    `_check_library_encapsulation` (fails `state` on the message assertion, NOT
    on the raise), or the `n.Call` arm from `_check_state_default_scope` (fails
    `call`, which is legitimately the general guard's — the loop matches
    `NameRef`s, not calls)."""
    _patch_libraries(monkeypatch, {"leaky": _leaky("state", kind, leaking=False)})
    with pytest.raises(DiagnosticError) as exc:
        resolve(_leak_host())
    assert "docs/libraries/leaky.cardlang:" in str(exc.value), (
        "the library author is who must fix it, so the span belongs in their file"
    )
    if kind == "state":
        assert "contract" in str(exc.value), (
            "must be the library check's message, not the general guard's: only "
            "one of them can tell the author the name is theirs to contract for"
        )


def test_a_provided_default_may_read_an_earlier_provided_sibling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control the row above needs: a provided default CAN read provided
    state declared before it, so the two refusals are refusing the contract
    reach and not defaults-in-libraries as such.

    This is the cell that shows the rule is about declaration order rather than
    about libraries — the same shape a plain game may write.

    It is PLAYED, not merely resolved, and needs its own host to be: the leak
    grid's `_leak_host` scores on a bare Integer and cannot reach a result. An
    accepted cell that stops at `resolve` is exactly the assertion that
    commanded the original defect green — the front end always accepted it, and
    the `KeyError` was waiting at declare time.

    red under: widen the provided-default loop to refuse every `NameRef`."""
    _patch_libraries(
        monkeypatch,
        {
            "leaky": parse_library(
                "library leaky { requires { declared_thing : Integer } "
                "state { first_thing : Integer = 3 "
                "        second_thing : Integer = first_thing } }",
                "docs/libraries/leaky.cardlang",
            )
        },
    )
    host = parse_text(
        """
game SiblingHost {
  uses leaky
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  declared_thing : Integer = 0 }
  phase play { }
  winner: highest score
}
""",
        "sibling_host.cardlang",
    )
    play_game(resolve(host), random.Random(0))


# A body reading its OWN parameter is the second control the encapsulation check
# needs: a parameter is bound, so counting it as a leak would refuse a perfectly
# ordinary library. The axis is `resolve._PARAM_BEARING` — the registry of
# declaration kinds that HAVE parameters — filtered to the kinds a library can
# hold, so a new parameterized declaration form joins this sweep automatically.
_PARAM_SITE: dict[str, str] = {
    "rules": (
        "rule NoLead(suit : Suit) {{ constrains: play_to_trick "
        "applies_when: {read} is not none }}"
    ),
    "move_types": "move_type m(s : Suit) {{ when: {read} is not none effect {{ }} }}",
    "functions": "function fn(x : Integer) = {read} + 1",
    "procedures": "procedure pr(y : Integer) {{ declared_thing := {read} }}",
}

# Which parameter each site reads, keyed the same way.
_PARAM_READ: dict[str, str] = {
    "rules": "suit",
    "move_types": "s",
    "functions": "x",
    "procedures": "y",
}


def _param_bearing_library_kinds() -> list[str]:
    """The `_PARAM_BEARING` collections a library can hold — all of them, since a
    library holds every definition kind a game does. Derived so the sweep below
    cannot silently stop covering one."""
    kinds = {
        row.library_field
        for row in _PARAM_BEARING.values()
        if row.library_field is not None
    }
    return sorted(kinds & {field for field, _ in _LIBRARY_DEF_KINDS})


def test_param_sites_cover_every_parameterized_kind() -> None:
    """red under: drop a key from `_PARAM_SITE`."""
    assert set(_PARAM_SITE) == set(_param_bearing_library_kinds())
    assert set(_PARAM_READ) == set(_PARAM_SITE)


@pytest.mark.parametrize("field", _param_bearing_library_kinds())
def test_a_body_reading_its_own_parameter_is_not_a_leak(field: str) -> None:
    """A parameter is bound in the body it belongs to, so it is not something the
    contract has to cover — for every kind that has parameters, not the three
    whose scoping happened to be implemented.

    `rules` was the open cell: `_rewrite` scoped move-type, function and
    procedure parameters but not a rule template's, because the game path
    instantiates templates (substituting the arguments away) before it
    classifies, so it never needed the arm. Reading a library's definitions
    directly is the first caller that does.

    red under: delete the `n.RuleDef` arm from `_rewrite`."""
    source = _PARAM_SITE[field].format(read=_PARAM_READ[field])
    library = parse_library(
        f"library probe {{ requires {{ declared_thing : Integer }} {source} }}",
        "docs/libraries/probe.cardlang",
    )
    reach = _library_reach(library)
    assert not reach.unresolved, (
        f"a {field} parameter is bound, not a leak: "
        f"{sorted({r.name for r in reach.unresolved})}"
    )


# --- the BARE-STRING half of the same property --------------------------------
#
# The grid above crosses leak SITE with reference kind, and every one of its
# cells is written as an expression — which is the whole class `_rewrite` can
# see. A name held on a node as a plain `str` is invisible to that pass, so the
# channels below are the same property reached through a different door: not
# "what does a body evaluate", but "what does a construct NAME".
#
# The axis is the reference-slot registry, filtered by two derivations and no
# judgement: the slots reachable from a library's own clauses (a walk over the
# node types `n.Library` can hold), intersected with the namespaces the library
# sweep covers (`_library_slot_names`). What that intersection leaves out is not
# a hand-waved remainder either — every reachable namespace it drops carries its
# reason in `_LIBRARY_UNSWEPT`, and the pin below reads both tables.
#
# Two slots are on the registry's list and NOT in this grid, because the
# expression grid above already owns them: `CardLiteral.rank`/`suit` is its
# `card_literal` column and `Call.func` is its `call` column. They are subtracted
# by derivation rather than skipped — the registry FINDS them now (the hand-list
# in `_library_reach` is gone), and only their wording is still special.

# slot -> (the library clause holding the leak, the name the diagnostic must
# quote, the same clause reaching only what the library has — or None where no
# legal counterpart exists). Three namespaces have no control by construction: a
# library declares no zones, no phases and no position domains, so there is no
# in-contract way to write one, and the guard over them is total.
_SLOT_LEAK: dict[str, tuple[str, str, str | None]] = {
    "Turns.again": (
        "move_type m {{ effect {{ turns q from actor over all players "
        "until true again {read} {{ }} }} }}",
        "undeclared_thing",
        "declared_flag",
    ),
    "TrickRound.source_zone": (
        "move_type m {{ effect {{ round play_to_trick from actor over all players "
        "source {read} into pile winner highest_of_led_suit }} }}",
        "hand",
        None,
    ),
    "TrickRound.play_zone": (
        "move_type m {{ effect {{ round play_to_trick from actor over all players "
        "source pile into {read} winner highest_of_led_suit }} }}",
        "hand",
        None,
    ),
    # The climbing form's zone slots are separate registry rows from the trick
    # form's, so they are separate cells. One node's cells said nothing about
    # the other's the moment the node split.
    "ClimbRound.source_zone": (
        "move_type m {{ effect {{ round climb play_combination from actor "
        "over all players source {read} into pile "
        "combinations bigtwo_lead_options follows bigtwo_follows until true }} }}",
        "hand",
        None,
    ),
    "ClimbRound.play_zone": (
        "move_type m {{ effect {{ round climb play_combination from actor "
        "over all players source pile into {read} "
        "combinations bigtwo_lead_options follows bigtwo_follows until true }} }}",
        "hand",
        None,
    ),
    "ContinueTo.phase": (
        "define d -> {{ a | b }} {{ produce a }} "
        "move_type m {{ effect {{ d produces: a {{ continue to {read} }} b {{ }} }} }}",
        "play",
        None,
    ),
    "DomainQuery.binder": (
        "function f() = number of {read}s where true",
        "column",
        None,
    ),
    "Member.field": (
        "function f() = state.{read}",
        "undeclared_thing",
        "declared_thing",
    ),
    "StateDecl.type_name": (
        "state {{ provided_thing : {read}? = none }}",
        "GameType",
        "Integer",
    ),
    "RequireDecl.type_name": (
        "",  # written into the contract itself — see `_slot_leaky`
        "GameType",
        "Integer",
    ),
    "TypeArg.name": (
        # Also written into the contract: the `<owner>` of a zone contract. The
        # leak is a position domain only the GAME declares — a library has no
        # `positions { }` and cannot name one, so a contract spelling one asks
        # for a zone it could never have been checked against.
        "",
        "column",
        "player",
    ),
    "Parameter.type_name": ("function f(x : {read}) = 1", "GameType", "Integer"),
    "StructField.type_name": ("type T = {{ x : {read} }}", "GameType", "Integer"),
    "StructLit.type_name": (
        "type LibType = {{ x : Integer }} function f() = {read} {{ x: 1 }}",
        "GameType",
        "LibType",
    ),
    "OutcomeCase.payload_types": (
        "define d -> {{ a({read}) | b }} {{ produce b }}",
        "GameType",
        "Integer",
    ),
    "Offer.offering": (
        "move_type lib_move {{ effect {{ declared_thing := 1 }} }} "
        "move_type m {{ effect {{ offer to actor one of [{read}] }} }}",
        "game_move",
        "lib_move",
    ),
    "AuctionRound.offering": (
        "move_type lib_move {{ effect {{ declared_thing := 1 }} }} "
        "move_type m {{ effect {{ round offering [{read}] from actor "
        "over all players until true }} }}",
        "game_move",
        "lib_move",
    ),
    "Produces.define": (
        "define lib_define -> {{ a | b }} {{ produce a }} "
        "move_type m {{ effect {{ {read} produces: a {{ }} b {{ }} }} }}",
        "game_define",
        "lib_define",
    ),
    "RunStmt.name": (
        "procedure lib_proc() {{ declared_thing := 1 }} "
        "move_type m {{ effect {{ run {read}() }} }}",
        "game_proc",
        "lib_proc",
    ),
    "RotateStmt.values": (
        "move_type m {{ effect {{ rotate declared_dir through [{read}] }} }}",
        "hearts",
        "left, right",
    ),
}

_SLOT_CONTRACT = (
    "requires {{ declared_thing : Integer  declared_flag : Boolean "
    "declared_dir : SeatDirection  {wanted} : {wanted_type}? }} "
)

# A game that meets `leaky`'s contract AND happens to hold every namespace the
# leaks reach into — a `hand` and a `pile` zone, a `play` phase, a `column`
# position domain, a type, a define, a procedure and a move type. Without that
# second half the cells would fail as ordinary dangling references and would
# prove nothing about the CONTRACT, which is the distinction this whole section
# is about.
_SLOT_GAME = """
game SlotHost {
  uses leaky
  players: 2
  cards: standard52
  max_length: 100
  zones { deck : Deck  hand[player] : Hand<player>  pile : TrickPile }
  state {
    declared_thing   : Integer     = 0
    declared_flag    : Boolean     = false
    declared_dir     : SeatDirection   = hold
    undeclared_thing : Integer     = 0
    keyed[player]    : Integer     = 0
    wanted_game      : GameType?   = none
    wanted_plain     : Integer?    = none
  }
  positions { column : 1..7 }
  phase play { run game_proc() }
  winner: highest keyed
}
type GameType = { x : Integer }
define game_define -> { a | b } { produce a }
procedure game_proc() { declared_thing := 1 }
move_type game_move { effect { declared_thing := 1 } }
"""


def _slot_leaky(slot: str, *, leaking: bool) -> n.Library:
    """The library for one cell. `RequireDecl.type_name` is the one slot that
    lives in the CONTRACT rather than in a definition, so the substitution goes
    there — which is also why the contract is a template: the requirement's own
    type name is a reference like any other, and `requires` is not exempt from
    the property just because it holds no expression."""
    body, leak, control = _SLOT_LEAK[slot]
    read = leak if leaking else control
    assert read is not None
    if slot == "RequireDecl.type_name":
        contract = _SLOT_CONTRACT.format(
            wanted="wanted_game" if leaking else "wanted_plain", wanted_type=read
        )
    else:
        contract = _SLOT_CONTRACT.format(wanted="wanted_plain", wanted_type="Integer")
    if slot == "TypeArg.name":
        # A zone contract, plus a definition that reads the zone — an entry no
        # definition reaches is dead contract and would fail the minimality
        # check instead of the property this cell is for. A library declares ONE
        # `requires` block, so the zone entry joins the shared contract rather
        # than opening a second one.
        contract = contract.rstrip()[:-1] + f" hand[{read}] : Hand<{read}> }} "
        body = "function f(p : Player) = number of cards in hand[p]"
        return parse_library(
            f"library leaky {{ {contract}{body} }}", "docs/libraries/leaky.cardlang"
        )
    return parse_library(
        f"library leaky {{ {contract}{body.format(read=read)} }}",
        "docs/libraries/leaky.cardlang",
    )


def _library_reachable_node_types() -> set[type]:
    """Every node kind a library can hold, by walking `n.Library`'s own clauses
    through the AST's annotations. Derived, because the alternative is a list of
    "the node kinds a library obviously contains" — and the slot registry exists
    precisely because that list was wrong."""

    def leaves(annotation: object) -> set[type]:
        out: set[type] = set()
        stack = [annotation]
        while stack:
            current = stack.pop()
            if typing.get_origin(current) is not None:
                stack.extend(typing.get_args(current))
            elif isinstance(current, type):
                out.add(current)
        return out

    kinds = set(typing.get_args(n.Node))
    hints = {cls: typing.get_type_hints(cls) for cls in kinds}
    seen: set[type] = set()
    stack = [
        cls
        for field in fields(n.Library)
        if field.name not in ("name", "span")
        for cls in leaves(hints[n.Library][field.name]) & kinds
    ]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for field in fields(current):
            stack.extend(leaves(hints[current][field.name]) & kinds)
    return seen


def _reachable_reference_namespaces() -> set[str]:
    """The namespaces a library's own text can name. The union of what the sweep
    covers and what `_LIBRARY_UNSWEPT` excuses must equal this — that equation is
    the completeness statement, and it is why an unswept namespace has to be
    written down rather than merely not swept."""
    reachable = _library_reachable_node_types()
    contextual = {slot for slot in _CONTEXTUAL_SLOTS}
    return {
        namespace
        for slot, namespace in _REFERENCE_SLOTS.items()
        if slot[0] in reachable and slot not in contextual
    } | {
        namespace
        for (cls, _), slot in _CONTEXTUAL_SLOTS.items()
        if cls in reachable
        for namespace in slot.namespaces
    }


def test_every_reachable_reference_namespace_is_swept_or_excused() -> None:
    """No third state. A reference namespace a library can reach is either swept
    against what the library has, or carries a written reason why reaching it is
    not a channel — and nothing is merely absent.

    This is the check the hand-list era could not have: `_library_reach` used to
    close ONE bare-string slot (card literals) and the rest were invisible, with
    no artifact that could tell "decided not to sweep" from "nobody thought of
    it". Here the two are different table rows and the third possibility fails.

    red under: delete ANY row from `_LIBRARY_UNSWEPT`, or a namespace key from
    `_library_slot_names`. That is now true of every row, and was not when this
    test was written: the table then carried seven excuses for namespaces a
    library cannot reach at all, and deleting all seven left the suite green —
    an audit ran exactly that plant. An excuse for the unreachable excuses
    nothing, so those rows are gone (their content is in the table's header
    comment, where a claim nothing checks belongs)."""
    empty = n.Library(name="none")
    swept = set(_library_slot_names(empty))
    excused = set(_LIBRARY_UNSWEPT)
    reachable = _reachable_reference_namespaces()
    unclassified = sorted(reachable - swept - excused)
    assert not unclassified, (
        f"reference namespaces a library can reach that are neither swept nor "
        f"excused: {unclassified}"
    )
    assert not swept & excused, sorted(swept & excused)
    vacuous = sorted(excused - reachable)
    assert not vacuous, (
        f"excuses for namespaces a library cannot reach: {vacuous} — the row "
        f"guards nothing, and its deletion cannot redden this test, so it reads "
        f"as a verified claim while being an unverified one"
    )


def test_the_slot_grid_covers_every_swept_reachable_slot() -> None:
    """The grid's axis IS the registry, minus what the expression grid above
    already owns. Derived in both directions, so a reference slot added to the
    AST joins this grid or fails here — the failure mode the hand-list had no
    way to produce.

    red under: drop a key from `_SLOT_LEAK`, or add a `str` reference slot to a
    library-reachable node without a cell."""
    empty = n.Library(name="none")
    swept = set(_library_slot_names(empty))
    reachable = _library_reachable_node_types()
    expected = {
        f"{cls.__name__}.{field}"
        for (cls, field), namespace in _REFERENCE_SLOTS.items()
        if cls in reachable and namespace in swept and (cls, field) not in _CONTEXTUAL_SLOTS
    }
    expected |= {
        f"{cls.__name__}.{field}"
        for (cls, field), slot in _CONTEXTUAL_SLOTS.items()
        if cls in reachable and slot.namespaces & swept
    }
    # Owned by the expression grid's `card_literal` and `call` columns.
    expected -= {"CardLiteral.rank", "CardLiteral.suit", "Call.func"}
    assert set(_SLOT_LEAK) == expected


@pytest.mark.parametrize("slot", sorted(_SLOT_LEAK))
def test_a_library_may_not_name_what_it_does_not_have(
    slot: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every bare-string reference into a namespace the library lacks is refused,
    to the LIBRARY's author, quoting the name — so the author is told which
    word made their library depend on one particular game.

    The quoted name is half the command. A refusal alone would not distinguish
    the two zone cells, which share a statement: `source hand into pile` leaks
    twice, and only the name says which slot the diagnostic is about.

    red under: delete the `slot_leaks` loop from
    `_check_library_encapsulation`."""
    _patch_libraries(monkeypatch, {"leaky": _slot_leaky(slot, leaking=True)})
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(_SLOT_GAME, "slot_host.cardlang"))
    # Every diagnostic, not just the first: `_raise_if_errors` puts the rest in a
    # note, and the two zone cells share a statement that leaks twice — reading
    # only the first would make the second cell assert the first cell's finding.
    message = "\n".join([str(exc.value), *getattr(exc.value, "__notes__", [])])
    assert "docs/libraries/leaky.cardlang:" in message, (
        f"the library author is who must fix it:\n{message}"
    )
    assert "library 'leaky'" in message
    assert f"'{_SLOT_LEAK[slot][1]}'" in message, (
        f"the diagnostic must quote the name that leaked:\n{message}"
    )


@pytest.mark.parametrize("slot", sorted(s for s, v in _SLOT_LEAK.items() if v[2]))
def test_the_same_slot_naming_what_the_library_has_is_accepted(
    slot: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control row: each cell is its leaking twin with one name swapped, so a
    rejecting cell can only be rejecting the leak and not the construct.

    Several slots have no twin, and their absence is the design rather than a
    gap: a library declares no zones, no phases and no position domains, so
    there is no legal spelling for either round form's `source_zone` or
    `play_zone`, `ContinueTo.phase` or `DomainQuery.binder` to take. The controls beside them
    establish that the enclosing statements parse and resolve.

    red under: make the sweep reject any name it inspects rather than only the
    ones the library lacks."""
    _patch_libraries(monkeypatch, {"leaky": _slot_leaky(slot, leaking=False)})
    resolve(parse_text(_SLOT_GAME, "slot_host.cardlang"))


def test_the_bare_string_state_read_counts_toward_the_contract() -> None:
    """`turns … again <var>` READS state, so a contract entry answering it is
    live — the minimality half of the same registry, and the reason this slot had
    no correct spelling before it.

    Naming the variable in `requires` used to make the entry look dead (
    `state_reads` accumulated from `NameRef`s alone, and `again` is a string), so
    `test_every_library_contracts_for_exactly_what_it_reaches` called the
    contract non-minimal; leaving it out was the leak. Both directions were
    wrong at once, which is why one sweep answers both.

    red under: drop `slot_reads` from `_library_reach`'s `state_reads`."""
    library = parse_library(
        "library probe { requires { flag : Boolean } "
        "move_type m { effect { turns q from actor over all players "
        "until true again flag { } } } }",
        "docs/libraries/probe.cardlang",
    )
    assert "flag" in _library_reach(library).state_reads


def _patch_libraries(
    monkeypatch: pytest.MonkeyPatch, libraries: dict[str, n.Library]
) -> None:
    """Point resolve at synthetic libraries. Probing collisions against the real
    corpus library would mean adding deliberately-broken files to docs/libraries/,
    where they would be indistinguishable from real family libraries."""
    monkeypatch.setattr(
        "cardlang.resolve.library_names", lambda: frozenset(libraries)
    )
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: libraries[name])


# --- PROVIDED state: the read-only rule ---------------------------------------
#
# A library's `state` block is state the library OWNS. It splices into the game
# like the library's other definitions, and the game may READ it — but a write
# from game text is an error, located in the GAME, because the game's author
# wrote the assignment. The grid is write-site kind x state kind: every way the
# language can write persistent state, crossed with whether the name written is
# the library's (provided) or the game's (required).

_EXECUTE_PY = (
    Path(__file__).resolve().parent.parent / "cardlang" / "runtime" / "execute.py"
)


def _state_write_node_kinds() -> frozenset[str]:
    """The AST node kinds that WRITE persistent state, derived from the runtime
    that does the writing rather than spelled here.

    `runtime/state.py`'s `Store.set` is the one door onto persistent state, so
    the statement kinds reaching it ARE the write sites. This scrapes
    `runtime/execute.py` for every `ctx.rs.set(...)` call and reads the enclosing
    handler's first-parameter annotation, which is the node kind that handler
    handles.

    Derived because spelling it is how the axis would silently stop covering a
    write form: `Turns.again` is a state write that nothing about `AssignStmt`
    would suggest — the runtime clears the go-again flag at each turn boundary —
    and a `rotate` target is a third. A hand-written axis that happened to list
    only `:=` would look complete and prove one third of the property."""
    tree = pyast.parse(_EXECUTE_PY.read_text())
    kinds: set[str] = set()
    for fn in pyast.walk(tree):
        if not isinstance(fn, pyast.FunctionDef):
            continue
        writes_state = any(
            isinstance(call, pyast.Call)
            and isinstance(call.func, pyast.Attribute)
            and call.func.attr == "set"
            and isinstance(call.func.value, pyast.Attribute)
            and call.func.value.attr == "rs"
            for call in pyast.walk(fn)
        )
        if not writes_state or not fn.args.args:
            continue
        annotation = fn.args.args[0].annotation
        if isinstance(annotation, pyast.Attribute):
            kinds.add(annotation.attr)
    assert kinds, (
        f"the `rs.set` scrape of {_EXECUTE_PY.name} found no write sites — it has "
        f"gone stale, and a stale scrape makes every grid below vacuous"
    )
    return frozenset(kinds)


# node kind -> a game statement writing `{var}`, one per write-site kind. Each
# picks the variable of the type its form demands (`rotate` a Direction, `again`
# a Boolean), which is why the probe library below declares three of each.
_WRITE_STMT: dict[str, str] = {
    "AssignStmt": "{var}_int := 1",
    "RotateStmt": "rotate {var}_dir through [left, right]",
    "Turns": "turns t from 0 over all players until true again {var}_flag {{ }}",
}


def test_write_sites_cover_every_state_writing_node() -> None:
    """The registry pin, run in both directions at once. The runtime's set of
    state-writing statements is the authority; `resolve._STATE_WRITE_SITES` (the
    set the read-only guard sweeps) and `_WRITE_STMT` (the set this grid probes)
    must both equal it. A fourth write form added to the language fails here
    until the guard covers it AND a cell exists for it — which is the point: a
    write form the guard does not know is a hole in the read-only rule, and one
    the grid does not know is a hole that looks closed.

    red under: drop an entry from `resolve._STATE_WRITE_SITES`, or a key from
    `_WRITE_STMT`."""
    writing_nodes = _state_write_node_kinds()
    assert {cls.__name__ for cls, _ in _STATE_WRITE_SITES} == writing_nodes
    assert set(_WRITE_STMT) == writing_nodes


def test_every_write_site_field_exists_on_its_node() -> None:
    """The other half of the registry: each entry names a field its node really
    has. A renamed field would otherwise leave `_written_state_name` returning
    None for that whole write form — the guard silently covering two of three
    forms, with every grid cell still green because the grid asks the same
    stale registry.

    red under: point any `_STATE_WRITE_SITES` entry at a field name its node
    does not have."""
    for cls, field_name in _STATE_WRITE_SITES:
        assert field_name in {f.name for f in fields(cls)}, (
            f"{cls.__name__} has no field '{field_name}'"
        )


_CLAIM_LIBRARY = """
library {name} {{
  requires {{
    req_int  : Integer
    req_dir  : SeatDirection
    req_flag : Boolean
  }}
  state {{
    prov_int  : Integer   = 0
    prov_dir  : SeatDirection = left
    prov_flag : Boolean   = false
    prov      : Integer   = 0
    provp[player] : Integer = 0
  }}
}}
"""

_WRITE_HOST = """
game Writer {
  uses provider
  players: 2
  cards: kuhn3
  max_length: 100
  zones { deck : Deck }
  state {
    score[player] : Integer   = 0
    req_int  : Integer   = 0
    req_dir  : SeatDirection = left
    req_flag : Boolean   = false
  }
  phase play {
    WRITE
  }
  winner: highest score
}
"""


def _provider() -> n.Library:
    return parse_library(
        _CLAIM_LIBRARY.format(name="provider"), "docs/libraries/provider.cardlang"
    )


def _write_cells() -> list[object]:
    """Write-site kind x state kind. The `provided` column is the guard; the
    `required` column is its control — the same statement, one name over, which
    must stay legal, since writing state the game declared is the whole point of
    `requires`."""
    return [
        pytest.param(
            kind,
            var,
            id=f"{kind}-{var}",
        )
        for kind in sorted(_WRITE_STMT)
        for var in ("prov", "req")
    ]


@pytest.mark.parametrize("kind,var", _write_cells())
def test_game_text_may_not_write_library_provided_state(
    kind: str, var: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provided state is the library's: the game may read it, and may not write
    it. Refused for every write form the language has, not only `:=`.

    The failure lands in the GAME, unlike the encapsulation guard next door: the
    game's author wrote the assignment, and the only fix is theirs. It names
    both the variable and the library, because "you may not write this" is
    useless without "and here is who owns it"."""
    _patch_libraries(monkeypatch, {"provider": _provider()})
    source = _WRITE_HOST.replace("WRITE", _WRITE_STMT[kind].format(var=var))
    game = parse_text(source, "writer.cardlang")
    if var == "req":
        resolve(game)
        return
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = str(exc.value)
    assert f"cannot write '{var}_" in message, message
    assert "library 'provider' provides it" in message, message
    assert "writer.cardlang:" in message, (
        f"a game's illegal write is reported to the GAME's author:\n{message}"
    )


# Where a write can be WRITTEN — one game-owned container per cell, each holding
# the same illegal write. Not a derived axis, and deliberately so: the guard walks
# `_walk(game)`, which is total dataclass recursion over the whole Game, so
# reachability is ONE property of `_walk` rather than a per-container dispatch
# that could cover some sites and miss others. These cells are regression
# evidence for that, not a completeness argument — the ledger records them as
# sampled. They exist because "the guard fires at a phase statement" would
# otherwise have been the only thing anyone had checked, and a write inside a
# game's own move-type effect is the cell an author would actually hit.
_WRITE_CONTAINER: dict[str, tuple[str, str]] = {
    "phase_statement": ("    prov := 1", ""),
    "if_branch": ("    if true { prov := 1 }", ""),
    "for_each_body": ("    for each player p: prov := 1", ""),
    "move_type_effect": ("", "move_type mt { effect { prov := 1 } }"),
    "procedure_body": ("    run pr()", "procedure pr() { prov := 1 }"),
    "indexed_target": ("    provp[0] := 1", ""),
}

_CONTAINER_HOST = """
game Host {{
  uses provider
  players: 2
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{ score[player] : Integer = 0 }}
  phase outer {{
    phase play {{
{body}
    }}
  }}
  winner: highest score
}}
{extra}
"""


@pytest.mark.parametrize("container", sorted(_WRITE_CONTAINER))
def test_the_read_only_wall_reaches_every_container(
    container: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same illegal write, moved around the game. A guard that fires at a
    top-level phase statement and not inside a move-type effect would be a hole
    wearing a guard's name — and the effect is where a poker author would most
    plausibly write one, since that is where the library's own moves write it.

    Note the host nests `phase play` inside `phase outer`: a sub-phase is the
    cheapest way for a recursion bug to hide.

    red under: narrow `_walk(game)` in `_check_provided_readonly` to
    `_walk(game.phases)` — measured, not predicted: all six cells fail, because
    the game's phase tree is reached THROUGH the Game node and a tuple of phases
    is not the same walk."""
    body, extra = _WRITE_CONTAINER[container]
    _patch_libraries(monkeypatch, {"provider": _provider()})
    game = parse_text(
        _CONTAINER_HOST.format(body=body, extra=extra), "host.cardlang"
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = str(exc.value)
    assert "cannot write" in message, message
    assert "library 'provider' provides it" in message, message
    assert "host.cardlang:" in message, message


def test_game_text_may_read_library_provided_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of read-only, and the reason the rule is not simply
    "provided state is private": a game reads what the library provides all the
    time — Stud's own `fold` guard reads the standing bet. Without this the guard
    could be passing by making provided state unreachable."""
    _patch_libraries(monkeypatch, {"provider": _provider()})
    source = _WRITE_HOST.replace("WRITE", "score := prov_int + 1")
    resolve(parse_text(source, "writer.cardlang"))


# --- PROVIDED state: shadowed by a name the GAME introduces -------------------
#
# The READ face of the read-only rule above. That rule closes the WRITE, and the
# injection guard further up closes the game's DECLARATION level. What is left is
# a name the game introduces into a scope NARROWER than the game — a binder, a
# declaration parameter — spelled like a provided variable: inside that scope the
# bare name is the binder (`_classify` tries `locals` before `state_vars`), so the
# provided variable cannot be read there, and the game's author never opens the
# library file to learn the spelling was taken. That invisibility is why the base
# language's shadowing carve-out — a binder is scoped strictly narrower than a
# same-named outer declaration the author WROTE (`RESERVED_VALUE_NAMES`) — does
# not reach here.

_RESOLVE_PY = Path(__file__).resolve().parent.parent / "cardlang" / "resolve.py"


def _binding_node_kinds() -> frozenset[str]:
    """The AST node kinds that BIND a name, derived from `_node_binders`'s own
    match arms rather than spelled here.

    An arm whose every `return` is the empty tuple is a non-binding arm; any
    other arm binds. `Transfer`/`EpistemicOp` appear in both a guarded binding
    arm and a plain non-binding one, so the union is taken over binding arms
    rather than by subtracting the non-binding ones.

    An arm this cannot read — one naming node kinds but returning from inside a
    branch rather than at its top level — stops loudly rather than falling to
    either answer. Defaulting it to non-binding is the failure that matters: the
    kind would vanish from the axis, and every grid built on the axis would go
    green with one fewer row than the language has.

    Derived because a hand-list is how this axis would silently stop covering a
    binder: `TypeDef` and `ProduceArm` both escaped the registry itself (see
    `_node_binders`'s docstring), and neither is a member of the `Expr` or `Stmt`
    unions, so no union walk would have found them either."""
    tree = pyast.parse(_RESOLVE_PY.read_text())
    fn = next(
        f
        for f in pyast.walk(tree)
        if isinstance(f, pyast.FunctionDef) and f.name == "_node_binders"
    )
    match_stmt = next(s for s in fn.body if isinstance(s, pyast.Match))
    binding: set[str] = set()
    for case in match_stmt.cases:
        named = {
            node.cls.attr
            for node in pyast.walk(case.pattern)
            if isinstance(node, pyast.MatchClass) and isinstance(node.cls, pyast.Attribute)
        }
        if not named:
            continue  # the `case _:` wildcard, which names no node kind
        returns = [s for s in case.body if isinstance(s, pyast.Return)]
        assert returns, (
            f"cannot read the `_node_binders` arm for {sorted(named)}: it returns "
            f"from inside a branch rather than at the arm's top level. Teach this "
            f"scrape to read it — silently calling it non-binding would drop those "
            f"kinds from the axis and leave every grid over the axis green"
        )
        if all(isinstance(r.value, pyast.Tuple) and not r.value.elts for r in returns):
            continue
        binding |= named
    assert binding, (
        f"the `_node_binders` match scrape of {_RESOLVE_PY.name} found no binding "
        f"arms — it has gone stale, and a stale scrape makes the grid vacuous"
    )
    return frozenset(binding)


def _param_scoping_kinds() -> frozenset[str]:
    """The declaration kinds whose parameters `_rewrite` puts into `locals` —
    read off the pass that does the scoping, which is the fact
    `_ParamBearing.scopes_body` restates.

    Derived rather than listed, because the value of the declared field is that a
    new row must ANSWER the question; a hand-list here would let a row answer it
    wrongly and nothing would notice."""
    tree = pyast.parse(_RESOLVE_PY.read_text())
    fn = next(
        f
        for f in pyast.walk(tree)
        if isinstance(f, pyast.FunctionDef) and f.name == "_rewrite"
    )
    kinds: set[str] = set()
    for branch in fn.body:
        if not isinstance(branch, pyast.If):
            continue
        named = {
            attr.attr
            for call in pyast.walk(branch.test)
            if isinstance(call, pyast.Call)
            and isinstance(call.func, pyast.Name)
            and call.func.id == "isinstance"
            for attr in pyast.walk(call.args[1])
            if isinstance(attr, pyast.Attribute)
        }
        scopes = any(
            isinstance(gen.iter, pyast.Attribute) and gen.iter.attr == "params"
            for comp in pyast.walk(branch)
            if isinstance(comp, pyast.SetComp)
            for gen in comp.generators
        )
        if named and scopes:
            kinds |= named
    assert kinds, (
        f"the `_rewrite` params-scoping scrape of {_RESOLVE_PY.name} found no "
        f"arms — it has gone stale, and a stale scrape makes the pin vacuous"
    )
    return frozenset(kinds)


def test_every_param_bearing_row_agrees_with_the_pass_that_scopes_it() -> None:
    """`_ParamBearing.scopes_body` says whether DSL text sits inside a
    declaration's parameters' scope. `_rewrite` is what puts them there, so the
    two must agree — otherwise the field is a comment with a type, and the sweeps
    that read it (which parameters can shadow a name, which cannot) would be
    running on a claim nobody checks.

    red under: flip `scopes_body` on the `n.PrimitiveDecl` row, or delete
    `_rewrite`'s `n.FunctionDef` params-scoping arm."""
    declared = {cls.__name__ for cls, row in _PARAM_BEARING.items() if row.scopes_body}
    assert declared == _param_scoping_kinds(), (
        f"rows claiming a scoped body {sorted(declared)} != the kinds `_rewrite` "
        f"scopes parameters for {sorted(_param_scoping_kinds())}"
    )


def _fixed_spellings() -> dict[str, frozenset[str]]:
    """Per binding node kind, the spellings the LANGUAGE fixes — each read from
    the registry that fixes it, so a member added there is an uncovered row
    rather than a hole. A kind absent from this map is one whose binder the
    author spells.

    `DomainQuery` is the one kind with a spelling from BOTH sides: the bare form
    over a declared `positions { }` domain takes the author's own noun, and that
    sub-position is not here because the guard never reaches it (see
    `test_a_declaration_level_collision_is_reported_by_another_guard`)."""
    flavors = typing.get_args(Flavor)
    content = {content_noun(f, plural=p) for f in flavors for p in (False, True)}
    card = content_noun("card", plural=False)
    return {
        "Quantifier": frozenset(role_names(frozenset(d.id for d in DOMAINS))),
        "EachSimultaneous": frozenset(role_names(SIMULTANEOUS_ROLES)),
        "PlayerQuery": frozenset(role_names(frozenset({Role.PLAYER}))),
        "CardQuery": frozenset({card}),
        "Comprehension": frozenset({card}),
        "TrickOrderRow": frozenset({card}),
        "Transfer": frozenset(content),
        "EpistemicOp": frozenset(content_noun(f, plural=False) for f in flavors),
        "DomainQuery": _COLLECTION_NOUNS | {BOARD_DOMAIN},
    }


# A spelling its registry admits that no game text can reach, mapped to the guard
# that refuses it. Each carries an executed probe, because "refused over there" is
# the claim that rots; without this map the spelling pin below would demand a row
# nobody can write, and widening the pin to admit it would make it vacuous.
_UNREACHABLE_SPELLINGS: dict[tuple[str, str], str] = {
    ("EpistemicOp", "piece"): (
        "`reveal one card` identifies a deck card, so a piece game's reveal is "
        "refused by the flavor guard before a binder exists "
        "(test_a_piece_game_reveal_is_refused_before_it_binds)"
    ),
}


def _whole_bag(exc: DiagnosticError) -> str:
    """Every diagnostic the stage collected, not only the one it leads with.

    `str(DiagnosticError)` renders the FIRST diagnostic; a stage that collected
    more attaches the rest as a note (`cardlang/cli.py`'s rendering reads the
    same two places). A cell asserting on `str` alone therefore measures
    whichever guard happened to fire first, and an assertion that some sentence
    is ABSENT from the bag is vacuous against it — which is exactly what the
    `already` row below asserts."""
    return "\n".join([str(exc), *getattr(exc, "__notes__", [])])


class _Site(typing.NamedTuple):
    """One way a game introduces a name into a scope narrower than the game.

    `kind` names the AST node the introduction belongs to — what the axis pin
    matches against the two registries. `binds` is the spelling the construct
    introduces: free text where the author names the binder, and the fixed noun
    where nobody writing a game gets to name it. `chosen` records which, because
    that is what decides whether the refusal site has anything to rename, and so
    which of the two diagnostics it owes.

    `already` marks the row whose spelling is refused a door earlier, by
    `_check_library_shadows_game`: a DECLARED position domain is one of the
    game's own declarations, so the injection guard sees the clash before any
    binder is reached. The cell stays in the grid — a cell is not covered by
    belonging to someone else — but it is commanded against that guard's
    sentence, and it is held out of the two registry pins below: the shadow
    guard never speaks for it, so neither its `chosen` column nor its spelling
    is a claim about that guard's tables. Its `chosen` records the honest
    reading all the same — the author wrote the `positions { }` row and can
    respell it.

    `accepts` marks the row that is a designed NON-error: a Primitive's
    parameters scope no DSL body, so no game text sits inside their scope and
    there is nothing to shadow."""

    kind: str
    binds: str
    chosen: bool
    body: str
    extra: str = ""
    prelude: str = ""
    clauses: str = ""
    board: bool = False
    already: bool = False
    accepts: bool = False


_INTRODUCE: tuple[_Site, ...] = (
    # --- spellings the game's own text fixes, and the author can therefore
    # --- respell ------------------------------------------------------------
    _Site("ForEach", "shared", True, "for each player shared: score[shared] := 1"),
    _Site(
        "Turns", "shared", True,
        "turns shared from 0 over all players until true { score[shared] := 1 }",
    ),
    _Site("LetStmt", "shared", True, "let shared = 5\n    score[0] := shared"),
    # `index` is `LetStmt`'s OTHER binder, scoped to its own `value` alone.
    _Site("LetStmt", "shared", True, "let m[shared] = shared\n    score[0] := m[0]"),
    _Site(
        "ProduceArm", "shared", True,
        "pick produces:\n      won(shared) { score[0] := shared }",
        prelude="define pick -> { won(Integer) } { produce won(0) }",
    ),
    _Site(
        "TypeDef", "shared", True, "score[0] := 0",
        extra="type T = { shared : Integer } derived { twice = shared + shared }",
    ),
    # The same declaration with no `derived { }` block scopes its field names
    # over no DSL text at all — `_classify_type_derived` only scopes them inside
    # derived bodies. Refused all the same, conservatively: adding one derived
    # field makes the shadow live, and the author who would add it is the one
    # who cannot see the other half. The refusal's sentence is what has to hold
    # for both, which is why it speaks of wherever the name is in scope rather
    # than asserting a scope that may be empty. The registry answering with
    # field names for a struct that scopes them nowhere is issue #503.
    _Site(
        "TypeDef", "shared", True, "score[0] := 0",
        extra="type T = { shared : Integer }",
    ),
    _Site(
        "FunctionDef", "shared", True, "score[0] := f(1)",
        extra="function f(shared : Integer) = shared",
    ),
    _Site(
        "ProcedureDef", "shared", True, "run pr(1)",
        extra="procedure pr(shared : Integer) { score[0] := shared }",
    ),
    _Site(
        "MoveTypeDef", "shared", True, "offer to 0 one of [mt]",
        extra="move_type mt(shared : Suit) { effect { score[0] := 0 } }",
    ),
    # A rule template's parameter shadows by SUBSTITUTION rather than by scoping
    # — `_instantiate_rules` replaces it by name before classification — which
    # reaches the same end: the body's `shared` is the argument, never the
    # provided variable.
    _Site(
        "RuleDef", "shared", True,
        "active_rules: [r(hearts)]\n"
        "    round play_to_trick from 0 over all players source hand "
        "into discard winner highest_of_led_suit",
        extra="rule r(shared : Suit) {\n"
        "  constrains: play_to_trick\n"
        "  demands: cards in hand where card.suit is not shared\n"
        "  if_impossible: hand\n}",
    ),
    # A Primitive's parameters label a Python signature and key its `reads`
    # binders. No DSL body is scoped by them, so the spelling shadows nothing.
    _Site(
        "PrimitiveDecl", "shared", True, "score[0] := belote_decl_size(0)",
        clauses="primitives { belote_decl_size(shared : Player) : Integer reads score }",
        accepts=True,
    ),
    # --- spellings no game gets to choose, and so cannot respell -------------
    _Site("Quantifier", "player", False, "if any player where player is 0 { score[0] := 1 }"),
    _Site("Quantifier", "team", False, "if all teams where true { score[0] := 1 }"),
    _Site("Quantifier", "suit", False, "if any suit where suit is hearts { score[0] := 1 }"),
    _Site("Quantifier", "rank", False, "if any rank where rank is A { score[0] := 1 }"),
    _Site("PlayerQuery", "player", False, "score[0] := number of players where player is 0"),
    _Site(
        "EachSimultaneous", "player", False,
        "each player simultaneously: move chosen 1 card from hand[player] to discard",
    ),
    _Site(
        "CardQuery", "card", False,
        "if any card in deck where card.suit is hearts { score[0] := 1 }",
    ),
    _Site("Comprehension", "card", False, "score[0] := sum of 1 over cards in deck"),
    _Site(
        "TrickOrderRow", "card", False,
        "let w = highest_by_trick_order(pile)\n    score[w] += 1",
        clauses="trick_order { trump: card.suit is hearts }",
    ),
    _Site(
        "Transfer", "card", False,
        "move 1 card from deck where card.suit is hearts to hand[0]",
    ),
    # `where jointly` binds the candidate SET, so its noun is the plural.
    _Site(
        "Transfer", "cards", False,
        "move chosen 2 cards from hand[0] where jointly "
        "(number of cards in cards) is 2 to discard",
    ),
    _Site(
        "EpistemicOp", "card", False,
        "reveal one card from deck where card.suit is hearts",
    ),
    # The board-minted `cell` domain, which the injection guard cannot see:
    # `_resolve_board` mints it after `_apply_uses` has read `game.positions`.
    _Site(
        "DomainQuery", "cell", False,
        "if all cells where square[cell] is empty { result[0] := 1 }",
        board=True,
    ),
    _Site(
        "DomainQuery", "line", False,
        "if any line in lines(3) where true { result[0] := 1 }",
        board=True,
    ),
    # A DECLARED position domain: the noun is the author's own `positions { }`
    # row, so it is one of the game's declarations and the injection guard
    # refuses the clash first.
    _Site(
        "DomainQuery", "slot", True,
        "if any slot where slot is 1 { score[0] := 1 }",
        clauses="positions { slot : 1..4 }",
        already=True,
    ),
    # The two binders whose spelling follows `Game.content_flavor`.
    _Site(
        "Transfer", "piece", False,
        "move all pieces from box where piece.side is x to reserve[0]",
        board=True,
    ),
    _Site(
        "Transfer", "pieces", False,
        "move chosen 2 pieces from box where jointly true to reserve[0]",
        board=True,
    ),
)


# The game the card-flavored rows are written in. `{declared}` carries the game's
# own declaration of the shared spelling, which only the `requires` column needs.
_SHADOW_HOST = """{prelude}
game Host {{
  uses provider
  players: 4
  cards: standard52
  ranking: aces high
  max_length: 100
  teams: [[0, 2], [1, 3]]
  {clauses}
  zones {{ deck : Deck  hand[player] : Hand<player>  discard : Discard  pile : TrickPile }}
  state {{ score[player] : Integer = 0 {declared} }}
  phase play {{
    {body}
  }}
  winner: highest score
}}
{extra}
"""

# The piece/board host for the rows the card host cannot express: a board mints
# the `cell` domain and supplies the `line` collection, and a piece game's
# transfer filter binds `piece`/`pieces`.
_SHADOW_BOARD_HOST = """{prelude}
game Board {{
  uses provider
  players: 2
  direction: clockwise
  max_length: 30
  board: grid(3, 3)
  pieces: xo_marks
  {clauses}
  zones {{
    box             : Deck
    square[cell]    : Cell<cell>
    reserve[player] : PlayerPile<player>
  }}
  state {{ result[player] : Integer = 0 {declared} }}
  phase setup {{
    {body}
    move all pieces from box to reserve[1]
  }}
  phase play {{
    turns t from 0 over all players until true {{ offer to t one of [place] }}
  }}
  winner: highest result
}}
move_type place(at : cell) {{
  when: square[at] is empty
  effect {{ move one piece from reserve[actor] to square[at] }}
}}
{extra}
"""


def _shadow_source(site: _Site, claim: str) -> tuple[str, str]:
    """The game text for one cell, plus the file name it is reported under."""
    host = _SHADOW_BOARD_HOST if site.board else _SHADOW_HOST
    # The `requires` column is the control: the same spelling, claimed by the
    # library's `requires` instead of its `state`, which obliges the GAME to
    # declare it — so the author wrote both and the shadow is theirs to see.
    declared = f" {site.binds} : Integer = 0" if claim == "requires" else ""
    return (
        host.format(
            prelude=site.prelude,
            body=site.body,
            extra=site.extra,
            clauses=site.clauses,
            declared=declared,
        ),
        "board.cardlang" if site.board else "host.cardlang",
    )


def _shadow_library(site: _Site, claim: str) -> n.Library:
    clause = {
        "state": f"state {{ {site.binds} : Integer = 0 }}",
        "requires": f"requires {{ {site.binds} : Integer }}",
        # The third column claims the spelling nowhere, so the row's game text is
        # proven valid on its own — without it a fixture broken for an unrelated
        # reason would read as the guard firing.
        "neither": "state { untouched : Integer = 0 }",
    }[claim]
    return parse_library(
        f"library provider {{ {clause} }}", "docs/libraries/provider.cardlang"
    )


def _shadow_cells() -> list[object]:
    """The commanded cells. A `state` cell is REJECT unless another Owner Guard
    owns it (`already`) or it is a designed non-error (`accepts`); the other two
    columns accept."""
    return [
        pytest.param(index, claim, id=f"{site.kind}-{site.binds}-{claim}")
        for index, site in enumerate(_INTRODUCE)
        for claim in ("state", "requires", "neither")
    ]


def test_introducer_axis_covers_every_way_a_game_introduces_a_name() -> None:
    """The registry pin, run in both directions. The union of the two registries
    — the node kinds `_node_binders` binds a name for, and the declaration kinds
    `_PARAM_BEARING` holds parameters for — IS the set of ways a game introduces
    a name into a narrower scope, and the grid's rows cover it exactly. A binding
    node kind with no row is a hole that looks closed; a row for a kind neither
    registry knows is a cell measuring nothing.

    The two registries are disjoint on purpose, and that is asserted rather than
    assumed: `_node_binders` files the parameter-bearing declarations under
    NON-binding (their parameters scope their own body, which `_classify_names`
    implements per declaration), so a kind in both would mean one of the two had
    changed meaning under the grid.

    red under: delete a row from `_INTRODUCE`, or add an arm to `_node_binders`
    that binds a name."""
    binding = _binding_node_kinds()
    params = {cls.__name__ for cls in _PARAM_BEARING}
    assert not (binding & params), (
        f"{sorted(binding & params)} is in both registries — the grid's axis "
        f"assumes they partition the introductions"
    )
    covered = {site.kind for site in _INTRODUCE}
    assert covered == binding | params, (
        f"grid rows {sorted(covered)} != the registries' {sorted(binding | params)}"
    )


def test_the_fixed_binder_spellings_come_from_their_registries() -> None:
    """The sub-position pin. A node kind is one row of the axis above, but a kind
    whose spelling the language fixes has as many introductions as its registry
    has members — a quantifier binds each `DOMAINS` role noun, a transfer filter
    each `content_noun` of each `Flavor`. Rows are crossed against those
    registries here, so a fifth role or a third content flavor is an uncovered
    row rather than a silent gap.

    A spelling a registry admits that no game text can reach carries its guard in
    `_UNREACHABLE_SPELLINGS` and an executed probe beside it; admitting it by
    widening this assertion instead would make the pin vacuous.

    red under: add a `Domain` to `cardlang/domains.py`, or drop the `Quantifier`
    row for `suit`."""
    for kind, spellings in _fixed_spellings().items():
        rows = {
            site.binds
            for site in _INTRODUCE
            if site.kind == kind and not site.chosen and not site.already
        }
        unreachable = {noun for (k, noun) in _UNREACHABLE_SPELLINGS if k == kind}
        assert rows | unreachable == spellings, (
            f"{kind}: rows {sorted(rows)} plus unreachable {sorted(unreachable)} "
            f"!= the registry's {sorted(spellings)}"
        )
    assert set(_fixed_spellings()) <= _binding_node_kinds(), (
        "a fixed-spelling registry names a kind that binds nothing"
    )


def test_the_author_chosen_split_classifies_every_binding_kind() -> None:
    """`_AUTHOR_CHOSEN_BINDERS` decides which of two fixes the refusal
    prescribes, so an unfiled node kind does not fail — it takes the
    language-fixed branch and tells the author to go and edit a library over a
    binder they could have respelled themselves. That is a wrong-advice default,
    which is why the split is pinned to the binder registry rather than left to a
    membership test.

    The parameter kinds are author-chosen by construction (a parameter name is a
    free NAME in every one of their productions), so they are asserted to need no
    entry rather than listed.

    red under: add `n.Quantifier` to `_AUTHOR_CHOSEN_BINDERS`, or drop
    `n.ForEach` from it."""
    chosen = {cls.__name__ for cls in _AUTHOR_CHOSEN_BINDERS}
    binding = _binding_node_kinds()
    assert chosen <= binding, (
        f"{sorted(chosen - binding)} is filed as an author-chosen BINDER but "
        f"binds nothing"
    )
    assert chosen == {
        site.kind
        for site in _INTRODUCE
        if site.chosen and not site.already and site.kind in binding
    }
    assert not (chosen & {cls.__name__ for cls in _PARAM_BEARING}), (
        "parameters are author-chosen through `_PARAM_BEARING`, not through the "
        "binder split"
    )


@pytest.mark.parametrize("index,claim", _shadow_cells())
def test_a_game_introduced_name_may_not_shadow_provided_state(
    index: int, claim: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name the game introduces into a narrower scope may not be spelled like a
    library-PROVIDED state variable.

    The `state` column is the guard. The other two accept, and each rules out a
    different way the guard could be passing for the wrong reason: `requires`
    holds the spelling fixed and moves only WHICH library clause claims it, so a
    guard refusing every collision with a library NAME (rather than with a
    library-OWNED one) fails there; `neither` proves the row's game text valid on
    its own, so a fixture broken for an unrelated reason cannot read as a
    rejection.

    The refusal is located in the GAME — that is where the shadow is written, and
    the file the author has open — and names the library, because the other half
    is text they never see. Which fix it prescribes follows the binder: a
    spelling the author chose is theirs to respell, and one they did not choose
    is not, so those rows ask for the library's variable to be renamed instead.

    red under: delete `or name in declared` from
    `_check_provided_shadowed_by_binder`'s `check` — measured, and it reddens
    the `already` row alone."""
    site = _INTRODUCE[index]
    _patch_libraries(monkeypatch, {"provider": _shadow_library(site, claim)})
    source, file_name = _shadow_source(site, claim)
    game = parse_text(source, file_name)
    if claim != "state" or site.accepts:
        resolve(game)
        return
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = _whole_bag(exc.value)
    assert f"'{site.binds}'" in message, message
    assert "library 'provider'" in message, message
    assert f"{file_name}:" in message, (
        f"the shadow is written in the GAME, so that is where it is reported:"
        f"\n{message}"
    )
    if site.already:
        assert "this game already uses" in message, message
        # The skip's own claim, and the only assertion that fails when it is
        # removed: the bag collects every diagnostic, so asserting the owning
        # guard's sentence is PRESENT stays true whether or not a second one
        # joins it. One clash, one diagnostic.
        assert "and this form binds" not in message, (
            f"a spelling the game binds at declaration level belongs to the "
            f"guard that owns that level, and this row's second sentence would "
            f"be false — the author's own `positions {{ }}` row is theirs to "
            f"respell:\n{message}"
        )
    elif site.chosen:
        assert "is spelled like state" in message, message
        assert "rename the" in message, message
    else:
        assert "provides state" in message, message
        assert "rename the library's variable" in message, message


def _declaration_level_nouns() -> list[str]:
    """Every noun `_game_bindings` reports, derived by running it over a game
    that populates each of its buckets rather than by listing them — the axis of
    the skip below, and `_check_library_shadows_game`'s own domain."""
    game = parse_text(_DECLARER_HOST, "declarer.cardlang")
    return sorted({noun for noun, _ in _game_bindings(game).values()})


_DECLARER_HOST = """
game Declarer {
  players: 2
  cards: standard52
  max_length: 100
  positions { slot : 1..4 }
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play {
    active_rules: [r]
    round play_to_trick from 0 over all players source hand into deck
      winner highest_of_led_suit
    run pr()
    score[0] := f() + d_use()
  }
  winner: highest score
}
function fn() = 1
function d_use() = 1
function f() = 1
type T = { x : Integer }
define dd -> { w(Integer) } { produce w(0) }
move_type mt { effect { score[0] := 0 } }
procedure pr() { score[0] := 0 }
rule r { constrains: play_to_trick  demands: cards in hand  if_impossible: hand }
"""

# One name per bucket `_game_bindings` reports, chosen so a library providing it
# collides with the game above at declaration level.
_DECLARATION_LEVEL_NAME: dict[str, str] = {
    "state variable": "score",
    "zone": "deck",
    "position domain": "slot",
    "suit value": "hearts",
    "rank value": "A",
    "direction value": "left",
    "function": "fn",
    "type": "T",
    "define": "dd",
    "move type": "mt",
    "rule": "r",
    "procedure": "pr",
    "standard-library value": "highest_of_led_suit",
}


def test_the_declaration_level_axis_covers_every_game_binding_bucket() -> None:
    """The skip below is only honest while every bucket it skips is spoken for.
    Its axis is `_game_bindings`'s own output, so a namespace added there joins
    this grid instead of silently widening the skip.

    red under: delete a row from `_DECLARATION_LEVEL_NAME`, or add a bucket to
    `_game_bindings`."""
    assert sorted(_DECLARATION_LEVEL_NAME) == _declaration_level_nouns()


@pytest.mark.parametrize("noun", sorted(_DECLARATION_LEVEL_NAME))
def test_a_declaration_level_collision_is_reported_by_another_guard(
    noun: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the binder guard stays silent on a spelling the game already binds at
    declaration level: something else has already refused it, in full, with the
    fix on the side that can take it. Executed per bucket rather than asserted,
    because "refused over there" is the claim that rots — and because the skip
    reads `_game_bindings` wholesale, so a bucket nobody probes is a hole with a
    guard's name on it.

    This is also what keeps `DomainQuery` honestly filed as language-fixed: its
    one author-respellable sub-position is a declared position domain, and that
    is a bucket here.

    Each cell asserts the OWNING guard's own sentence, naming the bucket it
    reports — asserting only that the name appears would pass on any unrelated
    diagnostic that happened to quote it, which several of these hosts' names
    do.

    red under: give `_check_library_shadows_game` a `continue` for
    `game_noun == "position domain"` — measured, and it reddens this cell alone."""
    name = _DECLARATION_LEVEL_NAME[noun]
    _patch_libraries(
        monkeypatch,
        {
            "provider": parse_library(
                f"library provider {{ state {{ {name} : Integer = 0 }} }}",
                "docs/libraries/provider.cardlang",
            )
        },
    )
    source = _DECLARER_HOST.replace("game Declarer {", "game Declarer {\n  uses provider", 1)
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(source, "declarer.cardlang"))
    # The state-variable bucket is `_check_state_claims`'s; every other bucket is
    # the injection guard's, whose sentence names the bucket.
    expected = (
        f"state '{name}' is declared by this game and also provided by library"
        if noun == "state variable"
        else f"this game already uses '{name}' as a {noun}"
    )
    assert expected in _whole_bag(exc.value), _whole_bag(exc.value)


def test_one_node_spelling_a_name_twice_draws_one_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`let <name>[<index>]` binds twice, from one span, and nothing stops an
    author spelling the two the same. The registry answers with both, so a
    refusal per returned name would print the identical sentence twice at the
    identical position — noise a reader has to decide is not two problems.

    The grid cannot catch this: its cells assert what the bag SAYS, not how many
    times.

    red under: drop the `dict.fromkeys` around `_introduced_binders` in
    `_check_provided_shadowed_by_binder`."""
    _patch_libraries(monkeypatch, {"provider": _provider()})
    source = _WRITE_HOST.replace("WRITE", "let prov[prov] = 1\n    score[0] := 0")
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(source, "writer.cardlang"))
    message = _whole_bag(exc.value)
    assert message.count("is spelled like state 'prov'") == 1, message


def test_a_library_may_bind_its_own_provided_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard's blast radius, from the other side. A library's own definitions
    bind names too, and they are spliced into the same `Game` the sweep walks —
    so a guard placed one line later would refuse the library for shadowing its
    own variable, in a file the game's author did not write and cannot edit.

    It stays legal because it is not the defect: the library's author wrote both
    the provision and the binder and can see both, which is the ordinary
    shadowing the base language allows. The whole guard turns on the game author
    NOT being able to see the library.

    Both halves are exercised — a parameter and a body binder — because they
    reach the sweep through the two different registries.

    red under: move `_check_provided_shadowed_by_binder`'s call below the splice
    at the end of `_apply_uses`."""
    library = parse_library(
        """
        library provider {
          state { limit : Integer = 0  touched[player] : Boolean = false }
          function scaled(limit : Integer) = limit + 1
          procedure widen(step : Integer) {
            for each player limit: touched[limit] := true
          }
        }
        """,
        "docs/libraries/provider.cardlang",
    )
    _patch_libraries(monkeypatch, {"provider": library})
    source = _WRITE_HOST.replace("WRITE", "run widen(1)\n    score := scaled(2)")
    resolve(parse_text(source, "writer.cardlang"))


def test_a_phase_local_declaration_of_a_provided_name_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one narrower-than-game name introduction that is NOT a binder, and so
    has no row in the grid: a phase's own `state { }` block. It is refused
    already, and by a guard two doors up rather than by this one — but "refused
    elsewhere" is the claim that rots silently, so it is executed here rather
    than asserted in the ledger's prose.

    red under: narrow `_check_state_claims`'s `declared` sweep from `_walk(game)`
    to `game.state.decls`."""
    _patch_libraries(monkeypatch, {"provider": _provider()})
    source = _WRITE_HOST.replace("WRITE", "score := 1").replace(
        "phase play {", "phase play { state { prov : Integer = 1 }", 1
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(source, "writer.cardlang"))
    assert "also provided by library 'provider'" in str(exc.value), str(exc.value)


@pytest.mark.parametrize("word", sorted(RESERVED_VALUE_NAMES))
def test_no_provided_name_can_be_a_pronoun(
    word: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why the pronoun rebinds need no row in the grid. `as`, `offer`, a round's
    `winner` and `state.` namespace, a move effect, `transition_to … where` and
    `demands: actions where` each narrow what a fixed spelling means inside a
    region, exactly as a binder does — but the spellings are the
    `RESERVED_VALUE_NAMES` words, and a library cannot provide one: the reserved
    sweep runs after the splice, so it holds a provided declaration to the same
    bar as the game's own. No provided name can collide, so there is nothing for
    a guard to catch.

    Reported in the LIBRARY, which is the only text that can change.

    red under: drop `reserved=True` from `_check_duplicate_names`'s
    `game.state.decls` sweep."""
    library = parse_library(
        f"library provider {{ state {{ {word} : Integer = 0 }} }}",
        "docs/libraries/provider.cardlang",
    )
    _patch_libraries(monkeypatch, {"provider": library})
    source = _WRITE_HOST.replace("WRITE", "score := 1")
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(source, "writer.cardlang"))
    message = str(exc.value)
    assert f"state variable '{word}' is a reserved word" in message, message
    assert "provider.cardlang:" in message, message


def test_a_piece_game_reveal_is_refused_before_it_binds() -> None:
    """`_UNREACHABLE_SPELLINGS`'s one entry, executed. `content_noun` gives
    `EpistemicOp` a `piece` binder for a piece game, but `reveal one card` names
    a deck card, so the flavor guard refuses the statement outright and the
    binder never exists. The spelling is therefore absent from the grid because
    no game can write it, not because nobody thought of it.

    red under: delete the piece-game arm of `_reject_card_content_clauses`'s
    reveal check."""
    source, _ = _shadow_source(
        _Site(
            "EpistemicOp", "piece", False,
            "reveal one card from box where piece.side is x",
            board=True,
        ),
        "neither",
    )
    with pytest.raises(DiagnosticError) as exc:
        resolve(parse_text(source.replace("uses provider\n", ""), "board.cardlang"))
    assert "reveal one card" in str(exc.value), str(exc.value)


# --- the claim grid: who may claim one state name -----------------------------
#
# A state name can be claimed from three places: the game's own `state { }`, a
# library's `state { }` (provided), and a library's `requires { }` (required).
# The grid is which claims coexist. Its axis is derived from `n.Library`'s
# state-bearing fields, so a third state clause cannot join the language without
# joining this grid.


def _library_state_claim_kinds() -> list[str]:
    """`n.Library`'s state clauses — the fields that are neither its name, its
    span, nor one of the definition kinds the splice loop sweeps."""
    return sorted(
        {f.name for f in fields(n.Library)}
        - {"name", "span"}
        - {field for field, _ in _LIBRARY_DEF_KINDS}
    )


def test_claim_axis_covers_every_library_state_clause() -> None:
    """red under: add a state clause to `n.Library` without adding it here."""
    assert _library_state_claim_kinds() == ["requires", "state"]


_CLAIMED = "claimed"

# The one-library grid: what the library claims about `claimed`, times whether
# the game declares it. `both` is the same library provoking itself, which is why
# the axis is the non-empty SUBSETS of the claim kinds rather than the kinds.
# cell -> (message needle, the FILE the diagnostic must land in), or None to
# accept. The location is half the command, not decoration: these guards split
# author deliberately. A library contradicting itself is the library author's
# to fix, so it lands in the library file; everything else is the game author's.
_GAME_FILE = "claimer.cardlang:"
_LIB_A_FILE = "docs/libraries/lib_a.cardlang:"

_ONE_LIBRARY_CELLS: dict[tuple[str, bool], tuple[str, str] | None] = {
    ("requires", True): None,  # the contract, met
    ("requires", False): ("does not declare", _GAME_FILE),
    ("state", True): (
        "declared by this game and also provided by library",
        _GAME_FILE,
    ),
    ("state", False): None,  # the library owns it and nobody argues
    ("both", True): ("both provides and requires", _LIB_A_FILE),
    ("both", False): ("both provides and requires", _LIB_A_FILE),
}

# The two-library grid: what each of two libraries claims, times the same. Only
# the unordered pairs — the guards are symmetric and a mirrored cell would assert
# nothing the first does not.
_TWO_LIBRARY_CELLS: dict[tuple[str, str, bool], tuple[str, str] | None] = {
    ("requires", "requires", True): None,  # one declaration answers both
    ("requires", "requires", False): ("does not declare", _GAME_FILE),
    ("requires", "state", True): (
        "declared by this game and also provided by library",
        _GAME_FILE,
    ),
    ("requires", "state", False): ("which library 'lib_b' provides", _GAME_FILE),
    ("state", "state", True): (
        "declared by this game and also provided by library",
        _GAME_FILE,
    ),
    ("state", "state", False): ("provided by both library", _GAME_FILE),
}


def _claim_library(name: str, claim: str) -> n.Library:
    """A library claiming `claimed` the way the cell says. Built by parsing real
    source, never by hand-assembling the node, so a claim the parser would not
    accept cannot reach the grid."""
    parts = []
    if claim in ("requires", "both"):
        parts.append(f"requires {{ {_CLAIMED} : Integer }}")
    if claim in ("state", "both"):
        parts.append(f"state {{ {_CLAIMED} : Integer = 0 }}")
    return parse_library(
        f"library {name} {{ {' '.join(parts)} }}", f"docs/libraries/{name}.cardlang"
    )


_CLAIM_HOST = """
game Claimer {
  USES
  players: 2
  cards: kuhn3
  max_length: 100
  zones { deck : Deck }
  state {
    score[player] : Integer = 0
DECL  }
  phase play { }
  winner: highest score
}
"""


def _claim_game(libraries: list[str], *, declares: bool) -> n.Game:
    source = _CLAIM_HOST.replace(
        "USES", "\n  ".join(f"uses {lib}" for lib in libraries)
    ).replace("DECL", f"    {_CLAIMED} : Integer = 0\n" if declares else "")
    return parse_text(source, "claimer.cardlang")


def _one_library_cells() -> list[object]:
    return [
        pytest.param(
            claim,
            declares,
            id=f"{claim}-{'declared' if declares else 'undeclared'}",
        )
        for claim, declares in _ONE_LIBRARY_CELLS
    ]


@pytest.mark.parametrize("claim,declares", _one_library_cells())
def test_one_library_claiming_a_state_name(
    claim: str, declares: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`provides` and `requires` are opposite directions, so claiming a name both
    ways is incoherent — the library cannot both own the initial value and leave
    it to the game — and a game declaring what a library provides is the state
    face of "`uses` imports, it does not inherit"."""
    _patch_libraries(monkeypatch, {"lib_a": _claim_library("lib_a", claim)})
    game = _claim_game(["lib_a"], declares=declares)
    cell = _ONE_LIBRARY_CELLS[(claim, declares)]
    if cell is None:
        resolve(game)
        return
    _rejects(game, *cell)


def _two_library_cells() -> list[object]:
    return [
        pytest.param(
            a,
            b,
            declares,
            id=f"{a}-{b}-{'declared' if declares else 'undeclared'}",
        )
        for a, b, declares in _TWO_LIBRARY_CELLS
    ]


@pytest.mark.parametrize("a,b,declares", _two_library_cells())
def test_two_libraries_claiming_one_state_name(
    a: str, b: str, declares: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two libraries requiring one name is fine — one game declaration answers
    both contracts. Everything else collides: resolution is flat, so a name two
    libraries both provide has no winner, and a name one provides while another
    requires it would have the second library's contract answered by the first
    library's variable rather than by the game's declaration, which is not what
    `requires` says."""
    _patch_libraries(
        monkeypatch,
        {"lib_a": _claim_library("lib_a", a), "lib_b": _claim_library("lib_b", b)},
    )
    game = _claim_game(["lib_a", "lib_b"], declares=declares)
    cell = _TWO_LIBRARY_CELLS[(a, b, declares)]
    if cell is None:
        resolve(game)
        return
    _rejects(game, *cell)


# --- the real corpus library --------------------------------------------------


@pytest.mark.parametrize("name", sorted(library_names()))
def test_every_library_contracts_for_exactly_what_it_reaches(name: str) -> None:
    """Both directions of the contract, for every library in docs/libraries/ —
    the registry, not the one library that exists today.

    Sufficiency (nothing reached past the contract) is what the guard enforces,
    asserted here as the acceptance half: the corpus library must actually
    satisfy the guard the grid above proves fires. Minimality (nothing in the
    contract that is never reached) is the other direction — a `requires` entry
    no definition reads is dead contract, forcing every consumer to declare
    state for no reason.

    Both read the classified `state_reads` set rather than the library's text.
    The text version of the minimality half was a substring search over
    comment-inclusive source, which a bogus entry `street` passed because the
    word appeared in a comment, and `rais` passed as a substring of `raises`.

    red under: add `unused_thing : Integer` to
    docs/libraries/poker_betting.cardlang's `requires` block."""
    library = load_library(name)
    reach = _library_reach(library)
    assert not reach.unresolved, (
        f"library '{name}' reads "
        f"{sorted({r.name for r in reach.unresolved})} past its contract"
    )
    assert not reach.unknown_calls, (
        f"library '{name}' calls "
        f"{sorted({c.func for c in reach.unknown_calls})} past its contract"
    )
    # Both halves of the contract: a state entry is answered by a state read, a
    # zone entry by a zone read. Reading only the first would call every zone
    # contract dead — the same trap `turns … again <var>` sprang on the
    # bare-string half, one namespace over.
    dead = {r.name for r in library.requires} - reach.state_reads - reach.zone_reads
    assert not dead, (
        f"library '{name}' requires {sorted(dead)}, which no definition in it "
        f"reads — drop them from the contract"
    )


def test_poker_betting_is_registered() -> None:
    assert "poker_betting" in library_names()


# --- The CONTRACT-KIND grid: which of a game's declarations an entry may name -
#
# A `requires` entry names something the including GAME declares, and a game has
# more than one block that declares a keyed name. Which block answers an entry
# is decided by the entry's TYPE — so the type slot is the discriminator, and
# every way it can be written is a cell.
#
# Both axes are crossed from registries, never listed: the TYPE axis from the
# two type registries plus the shapes `type_ref` and `type_name` can spell (a
# type argument, a `?`), and the ANSWERING-BLOCK axis from `n.Game`'s own
# fields. A zone type added to the kernel tables, or a third declaring block added to a
# game, joins this grid without anyone remembering to extend it.
#
# The discriminator is only a DERIVATION while no name reaches two registries.
# That is not free: a library may define its own `type`s, and a game its own
# `positions`, in namespaces that did not reserve the zone-type names. Both are
# guarded below, and the guard is what the derivation rests on.

_CONTRACT_TARGETS: dict[str, str] = {"zones": "ZoneDecl", "state": "StateDecl"}


def _contract_target_blocks() -> dict[str, str]:
    """The game blocks a `requires` entry can be answered from, DERIVED: a block
    whose declaration node carries both a `name` and an `index` — exactly the
    pair `n.RequireDecl` compares. `positions { }` is excluded by that test
    rather than by a judgment call, because a `PositionDecl` has no index."""
    hints = typing.get_type_hints(n.Game)

    def leaves(annotation: object) -> set[type]:
        out: set[type] = set()
        stack = [annotation]
        while stack:
            current = stack.pop()
            if typing.get_origin(current) is not None:
                stack.extend(typing.get_args(current))
            elif isinstance(current, type):
                out.add(current)
        return out

    def keyed(cls: type) -> bool:
        return is_dataclass(cls) and {"name", "index"} <= {f.name for f in fields(cls)}

    found: dict[str, str] = {}
    for field in fields(n.Game):
        if field.name in ("name", "span"):
            continue
        for cls in leaves(hints[field.name]):
            if not isinstance(cls, type):
                continue
            if keyed(cls):
                found[field.name] = cls.__name__
            elif cls is n.StateBlock:
                for inner in leaves(typing.get_type_hints(cls)["decls"]):
                    if isinstance(inner, type) and keyed(inner):
                        found[field.name] = inner.__name__
    return found


def test_the_contract_target_axis_is_every_declaring_block() -> None:
    """The grid's answering-block axis IS the derivation. A game clause that
    starts declaring keyed names — a third namespace a contract could be
    answered from — fails here until the grid crosses it.

    red under: give `n.PositionDecl` an `index` field, or add a keyed-name block
    to `n.Game`, without extending `_CONTRACT_TARGETS`."""
    assert _contract_target_blocks() == _CONTRACT_TARGETS


def test_the_type_registries_a_contract_reads_stay_disjoint() -> None:
    """Classifying an entry — state contract or zone contract — reads its type
    name against the registries and nothing else. That is a DERIVATION only
    while no name reaches two of them; one name in both would make the
    classification authored, silently, with no site to author it at.

    The state side is `KNOWN_TYPE_NAMES`, and the two registries were already
    disjoint. The side that was NOT disjoint is the one this test exists for:
    a library's own `type` names and a game's `positions` names are chosen by an
    author, and neither namespace reserved the zone-type spellings.

    red under: add any `KNOWN_TYPE_NAMES` member to `LIBRARY_ZONE_TYPES` in
    cardlang/stdlib/zones.py."""
    overlap = sorted(set(KNOWN_TYPE_NAMES) & set(LIBRARY_ZONE_TYPES))
    assert not overlap, (
        f"{overlap} name both a state type and a zone type, so a `requires` "
        f"entry spelling one cannot be classified from its type alone"
    )


@pytest.mark.parametrize("kind", ["type", "position"])
def test_an_author_may_not_take_a_zone_type_name(kind: str) -> None:
    """The guard the derivation rests on. `Hand` means a zone type; a game `type
    Hand = { … }` or `positions { Hand : 1..5 }` would make `requires { x :
    Hand }` mean two things at once, and the classification would silently pick
    one. Refused where the name is DECLARED — the layer that owns "a name that
    must not mean two things" — rather than at the contract, so the ambiguity
    cannot be constructed in the first place.

    Free against the corpus: no game declares a struct type at all, and every
    position domain is lowercase (`cell`, `column`, `fslot`).

    red under: drop the zone-type row from `resolve.POSITION_NAME_SOURCES`."""
    inside = "positions { Hand : 1..5 }" if kind == "position" else ""
    # A `type` is a TOP-LEVEL item, beside the game rather than inside it.
    outside = "type Hand = { n : Integer }" if kind == "type" else ""
    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 max_length: 10 zones {{ deck : Deck }} "
        f"state {{ s[player] : Integer = 0 }} {inside} "
        f"phase p {{ s[0] := 1 }} winner: highest s }} {outside}",
        "probe.cardlang",
    )
    _rejects(game, "Hand", "zone type")


def _contract_type_cells() -> list[object]:
    """TYPE x ANSWERING BLOCK, crossed from the registries.

    The type axis is itself a cross: which registry the name comes from, how
    many type arguments are written, and whether a `?` is written. One
    representative name per registry bucket — the bucket, not the name, is what
    the classification reads, and `test_every_zone_type_bucket_has_a_probe`
    pins the buckets to `LIBRARY_ZONE_TYPES` so a new zone type cannot land in
    an unprobed one."""
    cells: list[object] = []
    for source in ("state", "zone_owned", "zone_singleton", "unknown"):
        for args in (0, 1, 2):
            for optional in (False, True):
                for declared_in in (*sorted(_CONTRACT_TARGETS), "absent"):
                    cells.append(
                        pytest.param(
                            source,
                            args,
                            optional,
                            declared_in,
                            id=f"{source}-args{args}"
                            f"{'-opt' if optional else ''}-{declared_in}",
                        )
                    )
    return cells


def _bucket_name(source: str) -> str:
    """The probe name for a registry bucket, read OUT of the registry rather
    than spelled here — a hand-picked name is how this file's first kernel
    move-type cell shipped vacuous."""
    if source == "state":
        return sorted(KNOWN_TYPE_NAMES)[0]
    if source == "zone_owned":
        return sorted(k for k, owned in LIBRARY_ZONE_TYPES.items() if owned)[0]
    if source == "zone_singleton":
        return sorted(k for k, owned in LIBRARY_ZONE_TYPES.items() if not owned)[0]
    return "NoSuchTypeAnywhere"


def test_every_zone_type_bucket_has_a_probe() -> None:
    """Both halves of `LIBRARY_ZONE_TYPES` are non-empty, so neither bucket's
    row can be vacuous — a grid row over an empty bucket asserts nothing while
    reading as coverage.

    red under: set every `LIBRARY_ZONE_TYPES` value to `True`."""
    owned = {k for k, v in LIBRARY_ZONE_TYPES.items() if v}
    singleton = set(LIBRARY_ZONE_TYPES) - owned
    assert owned and singleton
    assert _bucket_name("zone_owned") in owned
    assert _bucket_name("zone_singleton") in singleton


def _contract_entry(source: str, args: int, optional: bool) -> str:
    """The `requires` entry text for a cell. An owned zone type is indexed by
    its owner because `_resolve_zone` requires it — the shapes that violate THAT
    class are `_check_contract_shapes`' own probes, not this grid's business."""
    name = _bucket_name(source)
    index = "[player]" if source == "zone_owned" else ""
    spelled = name + ("<" + ", ".join(["player"] * args) + ">" if args else "")
    return f"x{index} : {spelled}{'?' if optional else ''}"


def _contract_answer(source: str, optional: bool, block: str) -> str:
    """The declaration the game writes into `block`, named `x`.

    Shaped for the BLOCK, never for the contract: a cell whose block disagrees
    with the contract's type is testing exactly that disagreement, so the
    declaration has to be a legal line of the block it sits in — otherwise the
    cell fails on a malformed game and proves nothing about the contract."""
    if block == "state":
        matching = source == "state"
        name = _bucket_name("state") if matching else "Integer"
        return (
            f"x : {name}? = none" if matching and optional else f"x : {name} = 0"
        )
    if source == "zone_owned":
        return f"x[player] : {_bucket_name('zone_owned')}<player>"
    return f"x : {_bucket_name('zone_singleton')}"


def _expected_contract_outcome(
    source: str, args: int, optional: bool, declared_in: str
) -> str:
    """accept | library | game.

    `library` means refused against the library ALONE, before any game is
    consulted — a shape no game could answer, so the library's author is the
    only one who can fix it. `game` means the shape is well formed and the
    including game does not answer it, which lands on the `uses` line. The
    library leg is checked first, so a cell wrong in both ways expects
    `library`."""
    if source == "unknown":
        return "library"
    if source == "state":
        if args:
            return "library"  # a state type takes no type arguments
        return "accept" if declared_in == "state" else "game"
    wanted_args = 1 if source == "zone_owned" else 0
    if args != wanted_args or optional:
        # A zone type's arity is `LIBRARY_ZONE_TYPES`', and a zone has no
        # nullable form — `?` is a state spelling that `type_ref` cannot carry.
        return "library"
    return "accept" if declared_in == "zones" else "game"


# What each REJECTING game-addressed cell must actually say. Three guards, and
# which one fires is a property of the cell rather than of the message: a
# contract answered from the wrong block gets the near-miss diagnostic that
# names the block the declaration IS in, and one answered from no block at all
# gets the plain one.
_EXPECTED_NEEDLE: dict[tuple[str, str], str] = {
    ("state", "zones"): "does not declare",
    ("state", "absent"): "does not declare",
    ("zone_owned", "state"): "declares as state",
    ("zone_owned", "absent"): "does not declare",
    ("zone_singleton", "state"): "declares as state",
    ("zone_singleton", "absent"): "does not declare",
}


@pytest.mark.parametrize("source,args,optional,declared_in", _contract_type_cells())
def test_a_contract_entry_is_answered_from_the_block_its_type_names(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    args: int,
    optional: bool,
    declared_in: str,
) -> None:
    """The whole discriminator surface: an entry's TYPE says which of the game's
    declaring blocks answers it, and every way that type can be written is a
    cell here.

    Three cells accept — a state type answered from `state { }`, an owned zone
    type answered from `zones { }`, a singleton zone type answered from
    `zones { }` — and every other cell is a commanded refusal, in the channel
    the failure belongs to. The `?`-on-a-zone and args-on-a-state rows are the
    reason the grid crosses shape with source rather than testing them apart:
    the two spellings the widened type slot can carry are exactly the two that
    are legal on one side of the discriminator and not the other."""
    entry = _contract_entry(source, args, optional)
    expected = _expected_contract_outcome(source, args, optional, declared_in)
    library = parse_library(
        f"library probe {{ requires {{ {entry} }} "
        f"function reach(p : Player) = x }}",
        "docs/libraries/probe.cardlang",
    )
    _patch_libraries(monkeypatch, {"probe": library})
    zones = "deck : Deck" + (
        " " + _contract_answer(source, optional, "zones")
        if declared_in == "zones"
        else ""
    )
    state = "score[player] : Integer = 0" + (
        " " + _contract_answer(source, optional, "state")
        if declared_in == "state"
        else ""
    )
    game = parse_text(
        f"game Probe {{ uses probe players: 2 cards: kuhn3 max_length: 10 "
        f"zones {{ {zones} }} state {{ {state} }} "
        f"phase p {{ score[0] := 1 }} winner: highest score }}",
        "probe.cardlang",
    )
    if expected == "accept":
        resolve(game)
        return
    with pytest.raises(DiagnosticError) as exc:
        resolve(game)
    message = str(exc.value)
    where = (
        "docs/libraries/probe.cardlang" if expected == "library" else "probe.cardlang:1"
    )
    assert where in message, (
        f"cell expected to fail to the {expected}'s author:\n{message}"
    )
    # The span alone is too weak on the game side: every game-level diagnostic
    # carries `probe.cardlang:1`, so a cell could go green on a `max_length`
    # error it was never testing. Both probes in this module's history failed
    # exactly that way, so the cell names the guard it commands as well.
    needle = "requires" if expected == "library" else _EXPECTED_NEEDLE[
        (source, declared_in)
    ]
    assert needle in message, f"expected {needle!r} in:\n{message}"


def _zone_shape_cells() -> list[object]:
    """Every zone type crossed with the shapes a declaration can be written in:
    an owner argument or none, an index or none. Derived from
    `LIBRARY_ZONE_TYPES`, so a zone type added to the kernel tables joins this cross."""
    return [
        pytest.param(name, index, args, id=f"{name}-{index or 'noindex'}-args{args}")
        for name in sorted(LIBRARY_ZONE_TYPES)
        for index in (None, "player")
        for args in (0, 1)
    ]


@pytest.mark.parametrize("zone_type,index,args", _zone_shape_cells())
def test_a_contract_shape_is_refused_exactly_when_the_declaration_would_be(
    zone_type: str, index: str | None, args: int
) -> None:
    """`_check_contract_shapes` and `_resolve_zone` are two implementations of
    one class — is this zone shape well formed? — and this pins them equal.

    They are NOT one function, deliberately: they report in different
    authors (the library's file against the library alone; the game's
    against its own declaration) and they run at different times (before any
    game is consulted; while resolving one). Sharing a body would mean
    threading an author through it. So the copy stays and the AGREEMENT is
    what is checked, which is the shape decisions.md's write-time triage asks
    for — a Shadow Guard naming the guard it shadows, plus a pin that the shadow is
    faithful. A contract admitting a shape the game's own block refuses would
    be a contract no game could ever meet.

    ONE asymmetry, and it is by exclusion rather than omission: `_resolve_zone`
    also refuses a POSITION-indexed family whose type has distinct owner/others
    projections. A contract cannot be position-indexed at all — a library has no
    `positions { }` and cannot name one, so `index_domain` is swept to the roles
    — so the cell cannot be constructed on the contract side. This cross uses
    `player` only, for that reason.

    red under: change any arity or index rule in `_check_contract_shapes`
    without the matching change in `_resolve_zone`."""
    idx = f"[{index}]" if index else ""
    spelled = zone_type + ("<player>" if args else "")

    library = parse_library(
        f"library shapes {{ requires {{ x{idx} : {spelled} }} "
        f"function f(p : Player) = number of cards in x{'[p]' if index else ''} }}",
        "docs/libraries/shapes.cardlang",
    )
    contract_bag = DiagnosticBag()
    _check_contract_shapes(library, contract_bag)

    game = parse_text(
        f"game D {{ players: 2 cards: kuhn3 max_length: 10 "
        f"zones {{ deck : Deck  x{idx} : {spelled} }} "
        f"state {{ s[player] : Integer = 0 }} "
        f"phase p {{ s[0] := 1 }} winner: highest s }}",
        "probe.cardlang",
    )
    zone_bag = DiagnosticBag()
    _resolve_zone(game.zones[1], zone_bag, frozenset())

    assert contract_bag.has_errors == zone_bag.has_errors, (
        f"`{spelled}` at index {index!r}: the contract "
        f"{'refuses' if contract_bag.has_errors else 'accepts'} it while a "
        f"`zones {{ }}` line {'refuses' if zone_bag.has_errors else 'accepts'} "
        f"it — a contract must ask for a shape a game can declare"
    )
