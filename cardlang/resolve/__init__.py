"""Resolve stage: name resolution.

This pass checks that the structural references in a game hang together —
the class of error a type checker catches before anything runs:

- every zone's type names a known library zone type (and is parameterized
  correctly);
- every `active_rules:` entry names a rule defined in the game;
- every [[move-type]] referenced by `constrains:`, `legal_moves:`, or a
  transition event is a known library move type;
- every `transition_to:` target is a sibling phase.

Deep expression name resolution (state variables, suits, the `action` fields,
native functions) needs the typed object model and lands with the type
checker; this pass is the structural net.

On success an immutably rewritten :class:`Game` flows on (rule templates
instantiated, every name classified). On any error it raises with every
diagnostic collected, not just the first.

The pass is a package: one module per Resolve Step, which `resolve()` below
calls in a named sequence, and the shared modules the steps read. Each
module states its own Contract Block; the pass establishes their
conjunction, and each clause is stated once, in the module whose check
holds it. In sequence order:

- `splice` -- the library splice (`uses`), and the early raise;
- `declarations` -- the game's declarations: components, ranking, card
  points, suit ranking, climb engines, names, `max_length`, teams;
- `positions` -- the position domains, and the board's minted domains;
- `primitive_declarations` -- the `primitives { }` block and its scoped
  reads;
- `zone_declarations` -- the zones, against the minted positions;
- `rule_instantiation` -- rule instantiation, query nouns, rule references;
- `classification` -- every name classified;
- `references` -- the classified tree's references;
- `classified_checks` -- the checks that read the classified tree;
- `hidden_reads` -- hidden reads at deciding positions;
- `result` -- the result clauses, and the offered move types.

The shared modules: `walk`, `binders`, `reserved`, `slots`, `declared`,
`scope`, `crossings`, `seat_aliases`, `clause_gates`, `round_winners`,
`ranking_slots`, `classifier` (the one classifier, driven by
`classification` for the game and by `library_alone` for a library), and
`library_alone` (driven by `splice` per `uses` line, and by the standard
library's loader).

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed AST (spans present, ``NameRef.ref_kind`` still
              ``None``), and, where the caller holds it, the text it was
              parsed from (``source``, a ``cardlang.parse.SourceText``).
Establishes:  every ``NameRef`` carries its ``ref_kind`` classification;
              rule templates are instantiated into concrete rules; every
              structural reference names a real declaration. This is the
              ONLY pass that classifies names — downstream dispatches on
              ``ref_kind``, never re-derives it.
              No check here decides which file a refusal of library text is
              told in: every refusal stands where the text it refuses stands,
              and ``attribution.raise_if_errors`` tells it.
              A refusal of spliced library text that a game declaration its
              contract does not name decides -- a ``Card`` parameter's
              ``CARD_PARAMETER_FAMILY`` absent, not kept per player, or
              hidden from its owner, a ``BUILTIN_IMPLICIT_READS`` family's
              shape, a move type spelled like the game's climb engine's
              action, and a library move type's scoped-read containment --
              carries the sentence the game's author reads (``for_game``),
              naming the library and its definition. An `actor` read and a
              refusal reached through the game's answer to a Definition
              Contract stand at their own locations.
              The sequence: the steps run in the order ``resolve()`` names
              them, so report order is the order of the sequence (bag order
              is report order). The pass raises twice: once after the splice,
              with every diagnostic the splice collected, and once after the
              last step. A value one step produces and a later step reads
              (the game's own procedure, rule and move-type names, the
              library rules held aside, the tree as written before
              instantiation, the refused reader clauses, the refused binder
              sources, the classified categories, the position domain names)
              is a local of ``resolve()``, handed to its readers as an
              argument.
Now illegal:  an unresolved name (``ref_kind is None``) or a dangling
              zone/rule/move-type/phase reference reaching a later pass;
              the runtime hard-fails on an unclassified name
              (``runtime/evaluate.py``, ``_name``) as its Shadow Guard.
              Within the package: a step importing another step, a shared
              module importing a step, any module importing the package
              root, an import cycle, and a definition in the root other than
              ``resolve``.
Held by:      the import direction: Derived and Pinned, the step set derived
              from the calls ``resolve()`` makes (tests/test_resolve_steps.py).
              A cross-step value's order: Unrepresentable, since a local of
              ``resolve()`` read before its producer runs is a static error.
              Report order: Born-Green Pin, the rejection snapshots under
              tests/rejections/.
Verified by:  the per-guard diagnostic tests; the runtime Shadow Guard above.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.attribution import raise_if_errors
from cardlang.diagnostics import DiagnosticBag
from cardlang.parse import SourceText
from cardlang.resolve import (
    classification,
    classified_checks,
    declarations,
    positions,
    primitive_declarations,
    result,
    rule_instantiation,
    zone_declarations,
)
from cardlang.resolve.splice import (
    _AUTHOR_CHOSEN_BINDERS as _AUTHOR_CHOSEN_BINDERS,
    _INJECTABLE_TARGETS as _INJECTABLE_TARGETS,
    _StateClaims as _StateClaims,
    _USES_SPLICED_KINDS as _USES_SPLICED_KINDS,
    _apply_uses as _apply_uses,
    _check_definition_claims as _check_definition_claims,
    _check_definition_requirement as _check_definition_requirement,
    _check_library_clause_gates as _check_library_clause_gates,
    _check_library_collisions as _check_library_collisions,
    _check_library_lines_span as _check_library_lines_span,
    _check_library_shadows_game as _check_library_shadows_game,
    _check_provided_readonly as _check_provided_readonly,
    _check_provided_shadowed_by_binder as _check_provided_shadowed_by_binder,
    _check_requires as _check_requires,
    _check_state_claims as _check_state_claims,
    _check_zone_requirement as _check_zone_requirement,
    _definition_template as _definition_template,
    _definitions_of_kind as _definitions_of_kind,
    _game_bindings as _game_bindings,
    _game_declarations_of as _game_declarations_of,
    _library_calls as _library_calls,
    _library_nodes as _library_nodes,
    _stamp_contracted_calls as _stamp_contracted_calls,
    _stamp_origin as _stamp_origin,
    _with_held_rules as _with_held_rules,
)
from cardlang.resolve.declarations import (
    _answer_spelling as _answer_spelling,
    _answered_in_two_spellings as _answered_in_two_spellings,
    _check_climb_action_names as _check_climb_action_names,
    _check_duplicate_names as _check_duplicate_names,
    _check_piece_rounds as _check_piece_rounds,
    _check_reserved as _check_reserved,
    _check_reserved_binders as _check_reserved_binders,
    _check_reserved_params as _check_reserved_params,
    _check_teams as _check_teams,
    _check_trick_order_partition as _check_trick_order_partition,
    _expand_ranking as _expand_ranking,
    _gated_calls as _gated_calls,
    _label_namesakes as _label_namesakes,
    _reject_card_content_clauses as _reject_card_content_clauses,
    _resolve_card_points as _resolve_card_points,
    _resolve_climb_engines as _resolve_climb_engines,
    _resolve_component_set as _resolve_component_set,
    _resolve_direction as _resolve_direction,
    _resolve_max_length as _resolve_max_length,
    _resolve_ranking as _resolve_ranking,
    _resolve_suit_ranking as _resolve_suit_ranking,
    _trick_order_named as _trick_order_named,
    _trick_order_rounds as _trick_order_rounds,
    _with_answer_body as _with_answer_body,
)
from cardlang.resolve.positions import (
    DECLARED_POSITION_SITE as DECLARED_POSITION_SITE,
    MINTED_CELL_SITE as MINTED_CELL_SITE,
    MINTED_DIRECTION_SITE as MINTED_DIRECTION_SITE,
    POSITION_NAME_SOURCES as POSITION_NAME_SOURCES,
    RESERVATION_SITES as RESERVATION_SITES,
    ReservedNameSource as ReservedNameSource,
    _POSITION_MEMBER_CEILING as _POSITION_MEMBER_CEILING,
    _reserved_domain_source as _reserved_domain_source,
    _resolve_board as _resolve_board,
    _resolve_positions as _resolve_positions,
)
from cardlang.resolve.primitive_declarations import (
    _CONTAINMENT_BY_GAME_FIELD as _CONTAINMENT_BY_GAME_FIELD,
    _ReadCollisions as _ReadCollisions,
    _SUBTREE_PHASE_ITEMS as _SUBTREE_PHASE_ITEMS,
    _ScopedEntry as _ScopedEntry,
    _UNPOSITIONED_CONTAINERS as _UNPOSITIONED_CONTAINERS,
    _and_list as _and_list,
    _calls_entry as _calls_entry,
    _check_direct_call_positions as _check_direct_call_positions,
    _check_offered_containers as _check_offered_containers,
    _check_primitive_name as _check_primitive_name,
    _check_primitive_reads as _check_primitive_reads,
    _check_primitive_type as _check_primitive_type,
    _check_primitives_block as _check_primitives_block,
    _check_read_tail as _check_read_tail,
    _check_read_tails_nest as _check_read_tails_nest,
    _check_run_sites as _check_run_sites,
    _check_scoped_read_containment as _check_scoped_read_containment,
    _definition_bodies as _definition_bodies,
    _find_phase as _find_phase,
    _offering_positions as _offering_positions,
    _offers_move_type as _offers_move_type,
    _outside as _outside,
    _outside_phase as _outside_phase,
    _phase_list as _phase_list,
    _phase_of_node as _phase_of_node,
    _procedures_reaching as _procedures_reaching,
    _reaches_scoped_entry as _reaches_scoped_entry,
    _scoped_entry_phases as _scoped_entry_phases,
    _statement_owners as _statement_owners,
    _tail_names_instead as _tail_names_instead,
)
from cardlang.resolve.zone_declarations import (
    _KNOWN_ROLES as _KNOWN_ROLES,
    _resolve_zone as _resolve_zone,
)
from cardlang.resolve.rule_instantiation import (
    _bare_noun_refusal as _bare_noun_refusal,
    _binders_a_query_takes as _binders_a_query_takes,
    _check_domain_query as _check_domain_query,
    _check_modes as _check_modes,
    _check_rule_reaches_a_reader as _check_rule_reaches_a_reader,
    _check_rule_removes as _check_rule_removes,
    _check_rules_reach_a_trick as _check_rules_reach_a_trick,
    _check_subset_source as _check_subset_source,
    _check_template as _check_template,
    _direction_is_no_position as _direction_is_no_position,
    _instantiate_rules as _instantiate_rules,
    _nouns_a_query_takes as _nouns_a_query_takes,
    _player_register_spelling as _player_register_spelling,
    _reaches_a_trick_round as _reaches_a_trick_round,
    _refused_binder_sources as _refused_binder_sources,
    _resolve_phase_item as _resolve_phase_item,
    _resolve_phase_level as _resolve_phase_level,
    _resolve_rule as _resolve_rule,
    _resolve_transition as _resolve_transition,
    _spelled_zone as _spelled_zone,
    _subset_refusal as _subset_refusal,
    _substitute_value as _substitute_value,
    _template_binders as _template_binders,
    _transition_targets as _transition_targets,
    _validate_removes as _validate_removes,
    _what_a_bare_noun_names as _what_a_bare_noun_names,
    _zone_source as _zone_source,
    substitute as substitute,
)
from cardlang.resolve.classification import (
    _classify_names as _classify_names,
    _name_positions as _name_positions,
    _stamp_follows_reads as _stamp_follows_reads,
)
from cardlang.resolve.references import (
    _LEGAL_PARAM_DOMAINS as _LEGAL_PARAM_DOMAINS,
    _MISLEADING_LET_INDEXES as _MISLEADING_LET_INDEXES,
    _WRITE_TARGET_KINDS as _WRITE_TARGET_KINDS,
    _bad_write_target as _bad_write_target,
    _bad_zone_endpoint as _bad_zone_endpoint,
    _check_board_call as _check_board_call,
    _check_card_offering as _check_card_offering,
    _check_move_params as _check_move_params,
    _check_offering_moves as _check_offering_moves,
    _named_ref as _named_ref,
    _no_board_for_directions as _no_board_for_directions,
    _state_type_refusal as _state_type_refusal,
    _undeclared_primitive_hint as _undeclared_primitive_hint,
    _validate_refs as _validate_refs,
)
from cardlang.resolve.classified_checks import (
    HOSTED_REACH_INERT_SLOTS as HOSTED_REACH_INERT_SLOTS,
    HOSTED_REACH_POOLS as HOSTED_REACH_POOLS,
    _AnswerVoice as _AnswerVoice,
    _DEFINITION_CLAUSES as _DEFINITION_CLAUSES,
    _ErrorSink as _ErrorSink,
    _FUNCTION_TAKES_A_CARD as _FUNCTION_TAKES_A_CARD,
    _HOSTED_REACH_NOUN as _HOSTED_REACH_NOUN,
    _HOSTED_REACH_PART as _HOSTED_REACH_PART,
    _HOSTED_REACH_VERB as _HOSTED_REACH_VERB,
    _NEVER_HELD as _NEVER_HELD,
    _NON_LOCAL_STMTS as _NON_LOCAL_STMTS,
    _OWN_POOL_BLIND as _OWN_POOL_BLIND,
    _PLAY_SLOT_FIELD as _PLAY_SLOT_FIELD,
    _RouteSink as _RouteSink,
    _SOURCE_SLOT_FIELD as _SOURCE_SLOT_FIELD,
    _STMT_KINDS as _STMT_KINDS,
    _UNREAD_SENTENCES as _UNREAD_SENTENCES,
    _WINNER_BINDING_STMTS as _WINNER_BINDING_STMTS,
    _ZONE_SLOTS as _ZONE_SLOTS,
    _answer_routes as _answer_routes,
    _arg_shape as _arg_shape,
    _card_points_clause as _card_points_clause,
    _check_actor_alias_comparisons as _check_actor_alias_comparisons,
    _check_alias_operands as _check_alias_operands,
    _check_answer_call as _check_answer_call,
    _check_answer_hermeticity as _check_answer_hermeticity,
    _check_answer_zone_read as _check_answer_zone_read,
    _check_arrival_record_pile_args as _check_arrival_record_pile_args,
    _check_bare_family_refs as _check_bare_family_refs,
    _check_chooses as _check_chooses,
    _check_climb_play_zones as _check_climb_play_zones,
    _check_declared_type_names as _check_declared_type_names,
    _check_delegation as _check_delegation,
    _check_functions as _check_functions,
    _check_hosted_node as _check_hosted_node,
    _check_hosted_polls as _check_hosted_polls,
    _check_implicit_pools as _check_implicit_pools,
    _check_kernel_answers as _check_kernel_answers,
    _check_nested_ring_flags as _check_nested_ring_flags,
    _check_play_source as _check_play_source,
    _check_positional_index_range as _check_positional_index_range,
    _check_positive_arguments as _check_positive_arguments,
    _check_procedures as _check_procedures,
    _check_reference_order as _check_reference_order,
    _check_state_default_scope as _check_state_default_scope,
    _check_state_scope as _check_state_scope,
    _check_unread_clauses as _check_unread_clauses,
    _clause_span as _clause_span,
    _closure_steps as _closure_steps,
    _contracted_answer_on as _contracted_answer_on,
    _contracted_remedy as _contracted_remedy,
    _inner_ring_sharing as _inner_ring_sharing,
    _is_stmt as _is_stmt,
    _library_entry as _library_entry,
    _naming_span as _naming_span,
    _offered_move_types as _offered_move_types,
    _reaches as _reaches,
    _report_recursion as _report_recursion,
    _rule_clauses as _rule_clauses,
    _sweep_aliases as _sweep_aliases,
    _sweep_stmt_seq as _sweep_stmt_seq,
    _trick_order_clause as _trick_order_clause,
    _unread_card_points as _unread_card_points,
    _unread_suit_ranking as _unread_suit_ranking,
    _unread_trick_order as _unread_trick_order,
)
from cardlang.resolve.hidden_reads import (
    CHOSEN_MOVEMENT_SEATS as CHOSEN_MOVEMENT_SEATS,
    DECISION_POOLS as DECISION_POOLS,
    HIDDEN_READ_POSITIONS as HIDDEN_READ_POSITIONS,
    HiddenReadVerdict as HiddenReadVerdict,
    POOL_FROM_CARD_PARAMETERS as POOL_FROM_CARD_PARAMETERS,
    POOL_FROM_EXPRESSION as POOL_FROM_EXPRESSION,
    POOL_FROM_ROUND_SOURCE as POOL_FROM_ROUND_SOURCE,
    POOL_KINDS as POOL_KINDS,
    POOL_NONE as POOL_NONE,
    READ_POSITION_CHOSEN as READ_POSITION_CHOSEN,
    READ_POSITION_FOLLOWED as READ_POSITION_FOLLOWED,
    READ_POSITION_KINDS as READ_POSITION_KINDS,
    READ_POSITION_NO_SEAT as READ_POSITION_NO_SEAT,
    READ_POSITION_OUTSIDE as READ_POSITION_OUTSIDE,
    READ_POSITION_SEAT as READ_POSITION_SEAT,
    RULE_CLAUSE_SEATS as RULE_CLAUSE_SEATS,
    SEAT_ACTING as SEAT_ACTING,
    SEAT_EACH_RECEIVER as SEAT_EACH_RECEIVER,
    SEAT_TRICK_DECIDER as SEAT_TRICK_DECIDER,
    ZoneRead as ZoneRead,
    _ACTOR_SCOPE as _ACTOR_SCOPE,
    _ANY_PLAYER as _ANY_PLAYER,
    _Answered as _Answered,
    _Binding as _Binding,
    _CONTROL as _CONTROL,
    _Crossing as _Crossing,
    _HiddenReads as _HiddenReads,
    _LOCATE as _LOCATE,
    _NEED_PHRASE as _NEED_PHRASE,
    _NO_ACTING_SEAT as _NO_ACTING_SEAT,
    _NO_ACTOR_GATE as _NO_ACTOR_GATE,
    _NO_ACTOR_RESULT as _NO_ACTOR_RESULT,
    _NO_ACTOR_ROUND as _NO_ACTOR_ROUND,
    _NO_ACTOR_STATEMENT as _NO_ACTOR_STATEMENT,
    _NO_ACTOR_WHERE as _NO_ACTOR_WHERE,
    _NO_RUN_FIX as _NO_RUN_FIX,
    _NO_SEAT as _NO_SEAT,
    _ReadScope as _ReadScope,
    _RunRoutes as _RunRoutes,
    _Seat as _Seat,
    _check_hidden_reads as _check_hidden_reads,
    _library_functions as _library_functions,
    _made_up_run as _made_up_run,
    _meeting_fix as _meeting_fix,
    _needs as _needs,
    _spell as _spell,
    hidden_read_verdicts as hidden_read_verdicts,
)
from cardlang.resolve.result import (
    _DEFINITION_CONTAINERS as _DEFINITION_CONTAINERS,
    _RANKABLE_TYPES as _RANKABLE_TYPES,
    _UNKNOWN_CONTAINER_NAMESPACES as _UNKNOWN_CONTAINER_NAMESPACES,
    _check_unoffered_move_types as _check_unoffered_move_types,
    _check_winner_target as _check_winner_target,
    _ranking_target_role as _ranking_target_role,
    _reachable_definitions as _reachable_definitions,
    _resolve_winner_loser as _resolve_winner_loser,
)
from cardlang.resolve.walk import (
    _child_nodes as _child_nodes,
    _traverse as _traverse,
    _walk as _walk,
)
from cardlang.resolve.binders import (
    _BINDER_SCOPE_FIELDS as _BINDER_SCOPE_FIELDS,
    _NODE_KINDS as _NODE_KINDS,
    _introduced_binders as _introduced_binders,
    _node_binders as _node_binders,
)
from cardlang.resolve.reserved import (
    PLAY_SOURCE_NAME as PLAY_SOURCE_NAME,
    RESERVED_VALUE_NAMES as RESERVED_VALUE_NAMES,
    _CALL_SITE_PRONOUNS as _CALL_SITE_PRONOUNS,
    _KEYWORD_RESERVED as _KEYWORD_RESERVED,
    _PARAM_BEARING as _PARAM_BEARING,
    _PLAY_SOURCE_READING as _PLAY_SOURCE_READING,
    _PRONOUNS as _PRONOUNS,
    _ParamBearer as _ParamBearer,
    _ParamBearing as _ParamBearing,
    _RESERVED_WHY as _RESERVED_WHY,
    _SUBSCRIPTED_PLAY_SOURCE as _SUBSCRIPTED_PLAY_SOURCE,
    _refuse_play_source_params as _refuse_play_source_params,
)
from cardlang.resolve.slots import (
    STRING_SLOT_KINDS as STRING_SLOT_KINDS,
    _BINDER_SLOTS as _BINDER_SLOTS,
    _CLASSIFIED_SLOTS as _CLASSIFIED_SLOTS,
    _CONTEXTUAL_SLOTS as _CONTEXTUAL_SLOTS,
    _ContextualSlot as _ContextualSlot,
    _DECLARATION_SLOTS as _DECLARATION_SLOTS,
    _KEYWORD_SLOTS as _KEYWORD_SLOTS,
    _METADATA_SLOTS as _METADATA_SLOTS,
    _MOVE_TYPE_SLOT_OFFERS as _MOVE_TYPE_SLOT_OFFERS,
    _NAME_SLOTS as _NAME_SLOTS,
    _NAMING_SLOTS_BY_TYPE as _NAMING_SLOTS_BY_TYPE,
    _OPAQUE_SLOTS as _OPAQUE_SLOTS,
    _REFERENCE_SLOTS as _REFERENCE_SLOTS,
    _ROUND_QUERY_NAMES as _ROUND_QUERY_NAMES,
    _ROUND_QUERY_REGISTRIES as _ROUND_QUERY_REGISTRIES,
    _ROUND_QUERY_SLOT_SPELLINGS as _ROUND_QUERY_SLOT_SPELLINGS,
    _UNCLASSIFIED_MOVE_TYPE_SLOTS as _UNCLASSIFIED_MOVE_TYPE_SLOTS,
    _ZONE_SLOT_KINDS as _ZONE_SLOT_KINDS,
    _domain_query_namespace as _domain_query_namespace,
    _member_namespace as _member_namespace,
    _naming_slots_by_type as _naming_slots_by_type,
    _round_query_slot as _round_query_slot,
    _slot_root as _slot_root,
    slot_namespace as slot_namespace,
    slot_strings as slot_strings,
)
from cardlang.resolve.declared import (
    CARD_PARAMETER_FAMILY as CARD_PARAMETER_FAMILY,
    _STATE_WRITE_SITES as _STATE_WRITE_SITES,
    _combination_outside_a_parameter as _combination_outside_a_parameter,
    _component_known as _component_known,
    _deck_known as _deck_known,
    _declared_board as _declared_board,
    _declared_suits_phrase as _declared_suits_phrase,
    _declared_type_universe as _declared_type_universe,
    _direction_refusal as _direction_refusal,
    _family_shape as _family_shape,
    _map_climb_rounds as _map_climb_rounds,
    _minted_directions as _minted_directions,
    _simultaneous_role_refused as _simultaneous_role_refused,
    _stamped_stdlib_rules as _stamped_stdlib_rules,
    _tell_board_refusal as _tell_board_refusal,
    _unminted_direction as _unminted_direction,
    _written_state_name as _written_state_name,
)
from cardlang.resolve.scope import (
    _DEFAULT_REFUSED_PRONOUNS as _DEFAULT_REFUSED_PRONOUNS,
    _GAME_LEVEL_OWNED_BY_ANOTHER_GUARD as _GAME_LEVEL_OWNED_BY_ANOTHER_GUARD,
    _GAME_LEVEL_SKIP as _GAME_LEVEL_SKIP,
    _GAME_LEVEL_UNCHECKED as _GAME_LEVEL_UNCHECKED,
    _bare_family_refused as _bare_family_refused,
    _bare_seat_family_in_default as _bare_seat_family_in_default,
    _default_reads as _default_reads,
    _game_state_names as _game_state_names,
    _keyed_ids as _keyed_ids,
    _phase_scoped_names as _phase_scoped_names,
    _phase_state_names as _phase_state_names,
    _pronoun_refused as _pronoun_refused,
    _refused_call_site_pronouns as _refused_call_site_pronouns,
    _state_out_of_scope as _state_out_of_scope,
)
from cardlang.resolve.crossings import (
    _DEFINITION_POOLS as _DEFINITION_POOLS,
    _LibraryEntry as _LibraryEntry,
    _cite_in as _cite_in,
    _definition_closure as _definition_closure,
    _entry_route as _entry_route,
)
from cardlang.resolve.seat_aliases import (
    _ActorAliases as _ActorAliases,
    _aliases_after_let as _aliases_after_let,
    _rebound as _rebound,
    _seat_rebinding as _seat_rebinding,
)
from cardlang.resolve.clause_gates import (
    ClauseRole as ClauseRole,
    _ANSWER_IS_TRUMP as _ANSWER_IS_TRUMP,
    _BOARD_NEED_GATES as _BOARD_NEED_GATES,
    _BOARD_NEED_PHRASES as _BOARD_NEED_PHRASES,
    _BOARD_POSITION_GATE as _BOARD_POSITION_GATE,
    _CARD_CONTENT_GATE as _CARD_CONTENT_GATE,
    _CARD_POINTS_CALLS as _CARD_POINTS_CALLS,
    _CELL_RANGE_GATE as _CELL_RANGE_GATE,
    _CLAUSE_FREE_BUILTINS as _CLAUSE_FREE_BUILTINS,
    _CLAUSE_GATES as _CLAUSE_GATES,
    _CLIMB_QUERIES as _CLIMB_QUERIES,
    _ClauseGate as _ClauseGate,
    _LIBRARY_UNSWEPT as _LIBRARY_UNSWEPT,
    _NO_RANKING as _NO_RANKING,
    _NO_TEAMS as _NO_TEAMS,
    _PIECES_FIX as _PIECES_FIX,
    _PIECES_LACK as _PIECES_LACK,
    _PROCEDURE_PARAM_DOMAINS as _PROCEDURE_PARAM_DOMAINS,
    _RANKING_SLOT_GATE as _RANKING_SLOT_GATE,
    _RANK_PARAMETER_GATE as _RANK_PARAMETER_GATE,
    _REGION_CALL_FUNCS as _REGION_CALL_FUNCS,
    _SEAT_CALL_FUNCS as _SEAT_CALL_FUNCS,
    _SEAT_GATES as _SEAT_GATES,
    _SEAT_NEED_REASONS as _SEAT_NEED_REASONS,
    _SUIT_RANKING_CALLS as _SUIT_RANKING_CALLS,
    _TEAM_CALL_FUNCS as _TEAM_CALL_FUNCS,
    _TEAM_RANGE_GATE as _TEAM_RANGE_GATE,
    _TEAM_STATE_GATE as _TEAM_STATE_GATE,
    _TRICK_ORDER_READERS as _TRICK_ORDER_READERS,
    _TRICK_ORDER_READING_GATE as _TRICK_ORDER_READING_GATE,
    _TRICK_ORDER_REPLACED_GATE as _TRICK_ORDER_REPLACED_GATE,
    _activated_rule_names as _activated_rule_names,
    _answered_verbs as _answered_verbs,
    _board_fix as _board_fix,
    _board_need_gate as _board_need_gate,
    _board_positions_past_end as _board_positions_past_end,
    _board_remedy as _board_remedy,
    _board_spelling as _board_spelling,
    _builtin_gate as _builtin_gate,
    _card_contents as _card_contents,
    _card_points_fix as _card_points_fix,
    _cell_ranges as _cell_ranges,
    _climb_queries as _climb_queries,
    _declares_ranking as _declares_ranking,
    _drop_trick_order as _drop_trick_order,
    _mentions_team as _mentions_team,
    _position_past_end as _position_past_end,
    _rank_parameters as _rank_parameters,
    _ranking_slots as _ranking_slots,
    _round_trump_clauses as _round_trump_clauses,
    _seat_gate as _seat_gate,
    _static_length as _static_length,
    _team_keyed_state as _team_keyed_state,
    _team_ranges as _team_ranges,
    _teams_example as _teams_example,
    _teams_fix as _teams_fix,
    _trick_order_excluded_winners as _trick_order_excluded_winners,
    _trick_order_fix as _trick_order_fix,
    _trick_order_reading_slots as _trick_order_reading_slots,
    _trick_order_replaced_slots as _trick_order_replaced_slots,
)
from cardlang.resolve.round_winners import (
    _WinnerRefusal as _WinnerRefusal,
    _refuses as _refuses,
    _unstated_trump_slots as _unstated_trump_slots,
    _winner_refusals as _winner_refusals,
)
from cardlang.resolve.ranking_slots import (
    RankingSlot as RankingSlot,
    _STOP_SLOT as _STOP_SLOT,
    _WINNER_SLOT as _WINNER_SLOT,
    _result_rankings as _result_rankings,
    ranking_slot as ranking_slot,
)
from cardlang.resolve.classifier import (
    ALWAYS_HOLDERS as ALWAYS_HOLDERS,
    MAX_LENGTH_AS_VALUE as MAX_LENGTH_AS_VALUE,
    NamesInScope as NamesInScope,
    _ALWAYS_SITES as _ALWAYS_SITES,
    _AlwaysSite as _AlwaysSite,
    _Categories as _Categories,
    _NamePosition as _NamePosition,
    _always_message as _always_message,
    _callback_outside_slot as _callback_outside_slot,
    _categories as _categories,
    _check_hosted_binder as _check_hosted_binder,
    _classify as _classify,
    _each_destination_refuses as _each_destination_refuses,
    _is_bare_always as _is_bare_always,
    _may_be_a_membership as _may_be_a_membership,
    _membership_capture as _membership_capture,
    _names_bound_anywhere as _names_bound_anywhere,
    _position_refuses as _position_refuses,
    _query_nouns as _query_nouns,
    _record_scope as _record_scope,
    _refuse_bare_always as _refuse_bare_always,
    _resolving_here as _resolving_here,
    _rewrite as _rewrite,
    _rewrite_produce_arm as _rewrite_produce_arm,
    _rewrite_refused_binder as _rewrite_refused_binder,
    _rewrite_value as _rewrite_value,
    _slot_name_outside_slot as _slot_name_outside_slot,
    _slot_refuses as _slot_refuses,
    _unknown_shape_label as _unknown_shape_label,
    collection_nouns as collection_nouns,
)
from cardlang.resolve.library_alone import (
    CONTRACT_KINDS as CONTRACT_KINDS,
    _CONTRACT_KIND_OF as _CONTRACT_KIND_OF,
    _CONTRACT_ROWS as _CONTRACT_ROWS,
    _DEFINITION_KEYWORDS as _DEFINITION_KEYWORDS,
    _DEFINITION_KIND_WORDS as _DEFINITION_KIND_WORDS,
    _LIBRARY_DEF_KINDS as _LIBRARY_DEF_KINDS,
    _LIBRARY_OWN_NAMESPACES as _LIBRARY_OWN_NAMESPACES,
    _LibraryNameIs as _LibraryNameIs,
    _LibraryReach as _LibraryReach,
    _NAMESPACE_ADVICE as _NAMESPACE_ADVICE,
    _NAMESPACE_NOUN as _NAMESPACE_NOUN,
    _PRIMITIVE_POSITIONS as _PRIMITIVE_POSITIONS,
    _PRIMITIVE_QUERY_NAMESPACES as _PRIMITIVE_QUERY_NAMESPACES,
    _PrimitivePosition as _PrimitivePosition,
    _SlotLeak as _SlotLeak,
    _UNION_NAMESPACES as _UNION_NAMESPACES,
    _check_contract_names as _check_contract_names,
    _check_contract_reach as _check_contract_reach,
    _check_contract_shapes as _check_contract_shapes,
    _check_library_encapsulation as _check_library_encapsulation,
    _check_require_indexes as _check_require_indexes,
    _check_signature_result as _check_signature_result,
    _check_signature_row as _check_signature_row,
    _cite_own as _cite_own,
    _contract_kinds as _contract_kinds,
    _contract_rows as _contract_rows,
    _contracted as _contracted,
    _keyed_rows as _keyed_rows,
    _language_name_is as _language_name_is,
    _library_element as _library_element,
    _library_node_types as _library_node_types,
    _library_own_name_is as _library_own_name_is,
    _library_reach as _library_reach,
    _library_slot_names as _library_slot_names,
    _meant as _meant,
    _names_a_kind as _names_a_kind,
    _primitive_in_library as _primitive_in_library,
    _refuse_kind_word as _refuse_kind_word,
    _round_slot_primitives as _round_slot_primitives,
    _slot_leaks as _slot_leaks,
    _spelled_contract as _spelled_contract,
    _state_rows as _state_rows,
    check_library_alone as check_library_alone,
    dead_contract_rows as dead_contract_rows,
    is_zone_contract as is_zone_contract,
    library_reachable_namespaces as library_reachable_namespaces,
)
from cardlang.domains import SIMULTANEOUS_ROLES as SIMULTANEOUS_ROLES
from cardlang.domains import PARAM_DOMAINS as _FIXED_DOMAINS
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES


def resolve(
    game: n.Game,
    *,
    scopes: dict[n.NodeKey, NamesInScope] | None = None,
    source: SourceText | None = None,
) -> n.Game:
    """`scopes`, when given, is filled with the Scope Record: what a bare name
    resolves to at every node the classifying walk visits. `source`, when
    given, is the text `game` was parsed from, which an unresolved name's
    refusal reads to offer the keywords the grammar accepts in its place."""
    bag = DiagnosticBag()
    # First: `uses` splices each named library's definitions but its rules in,
    # so everything below sees one flat game; `_instantiate_rules` splices the
    # rules a game activates. Errors here (unknown library, a collision, an
    # unmet `requires`) make the spliced game unrepresentative, so they are
    # reported as a complete set and raised before the rest of the pass adds
    # noise derived from a half-assembled game.
    # The game's own move types and procedures, before the splice adds a
    # library's: a game importing a library need not present every move type
    # it brings, nor run every procedure. A move type the library contracts
    # for (`requires { fold : Move }`) is the game's own: the library's
    # offer of it is reachable only where the game runs the procedure that
    # holds it, so the ordinary rule applies and a game defining it with no
    # reachable offer is refused like any game-local move type.
    own_procedures = frozenset(p.name for p in game.procedures)
    own_rules = frozenset(r.name for r in game.rules)
    uses = game.uses
    game, library_rules = _apply_uses(game, bag)
    raise_if_errors(bag, _with_held_rules(game, library_rules), uses)
    own_move_types = frozenset(mt.name for mt in game.move_types if mt.origin is None)
    game, refused_clauses = declarations.step(game, bag)
    game, position_names = positions.step(game, bag)
    primitive_declarations.step(game, bag)
    zone_declarations.step(game, bag, position_names)
    written = game
    game, refused_binders = rule_instantiation.step(game, library_rules, bag)
    game, cats = classification.step(game, refused_binders, bag, scopes=scopes, source=source)
    _validate_refs(game, cats, bag)
    classified_checks.step(
        game,
        bag,
        own_rules=own_rules,
        own_procedures=own_procedures,
        written=written,
        refused_clauses=refused_clauses,
    )
    _check_hidden_reads(game, bag)
    game = result.step(game, bag, own_move_types)
    raise_if_errors(bag, _with_held_rules(game, library_rules), uses)
    return game
