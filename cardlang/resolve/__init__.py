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

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed AST (spans present, ``NameRef.ref_kind`` still
              ``None``).
Establishes:  every ``NameRef`` carries its ``ref_kind`` classification;
              rule templates are instantiated into concrete rules; every
              structural reference names a real declaration. This is the
              ONLY pass that classifies names — downstream dispatches on
              ``ref_kind``, never re-derives it. A rule clause's bare
              ``hand`` (not a ``Subscript``'s object, not a binder the
              clause introduces) is ``ref_kind == "play_source"``: the
              trick round's Play Source, so no later pass learns it from
              the spelling ``hand``. Every library's rules — a family
              library's and ``library stdlib``'s — are spliced into
              ``game.rules`` only where an ``active_rules:`` reference
              names them, after the game's own. ``game.ranking`` is the
              operative strength order: a ``ranking:`` convention keyword
              is expanded against the deck here (``_expand_ranking``), so
              no later pass may branch on ``ranking_convention`` for
              semantics — it survives only as the source-form record
              ``ir.emit`` prints. Also: every `primitives { }` entry's
              declared types are SHAPES the block's registries admit — the
              head from `declarable_type_names`, a collection's element from
              `COLLECTION_ELEMENT_NAMES` — and no name declared or minted at
              any of the sites in ``RESERVATION_SITES`` takes a spelling one of
              ``POSITION_NAME_SOURCES`` already holds. And every result
              ranking -- a ``winner:`` clause, a Stop Result's ranking --
              carries its target declaration's index role
              (``Winner.keyed_by``, ``StopResult.keyed_by``), so no later pass
              walks state declarations to learn how the result is keyed, and
              an ``as it stands`` Stop Result sits only on a game with a
              ``winner:`` clause. A bare
              ``DomainQuery`` noun names a declared position domain or, for a
              query kind in ``n.DIRECTION_QUERY_KINDS``, the direction domain the board
              minted; a Set Form's noun names a Position Domain alone, held by
              Derived and Pinned (the noun is a designer's string until this
              pass classifies it against ``game.positions``;
              tests/test_cell_set_form.py's noun grid). A move parameter's
              domain, a function parameter's type and an outcome payload's
              type name the direction domain only where the board minted it
              (``_minted_directions``, the one gate each of them reads), so a
              later pass may look any such name up in the position or the
              direction source and find it. A ``state`` variable's declared
              type names a value type or one of the game's named-member
              position domains (``_declared_type_universe``, the one set the
              ``StateDecl`` arm reads and a function parameter's set
              extends); an integer position domain, ``dir`` and ``cell`` in
              a game with no ``board:`` are refused there
              (``_state_type_refusal``), each naming a declaration that checks
              in that game. A board verb stands only on a
              board whose family declares what the verb reads
              (``BOARD_VERB_NEEDS``; ``_check_board_call`` for the game's
              call, the ``_BOARD_NEED_GATES`` rows on the ``uses`` line for a
              library's), so the runtime may read the board entry's edges,
              lines or frame behind any board verb it meets; held by Derived
              and Pinned, one table pinned total against
              ``BOARD_ONLY_CALL_FUNCS``. Every piece of
              library text spliced into the game -- a family library's move
              types, functions, procedures and provided state declarations,
              and every library rule a game activates, the standard
              library's included -- carries its ``n.LibraryOrigin``, and no
              game text carries one: it is the only record of where spliced
              text came from that any check, this pass's included, may read.
              No check here decides which file a refusal of library text is
              told in: every refusal stands where the text it refuses stands,
              and ``attribution.raise_if_errors`` tells it. A refusal that the
              Kernel Definition Contract answer walk, the play-source walk or the no-acting-seat
              walk reaches through a call from the game's text into a library
              function, that the Hosted Poll walk reaches through a call,
              `run` or offer into library text, or that a library rule the
              game activates earns from the game's rounds, carries that
              crossing (``Route``, at the node ``_library_entry`` names), and
              names the library and its definition; a statement the reached
              definition may hold in no game (``_NEVER_HELD``) carries none. A
              refusal of a decision's seat the hidden-read walk makes in a
              library procedure's body, where the game's text runs it,
              carries that `run` when some caller meets the procedure
              (``_HiddenReads._meeting_callers``), with the first meeting
              caller that passes written in place of that `run` as its fix,
              and no run where none does; where no caller meets it, it carries
              none. A read the run's own arguments make carries the `run`. A
              refusal of spliced library text that a game declaration its
              contract does not name decides -- a ``Card`` parameter's
              ``CARD_PARAMETER_FAMILY`` absent, not kept per player, or
              hidden from its owner, a ``BUILTIN_IMPLICIT_READS`` family's
              shape, a move type spelled like the game's climb engine's
              action, and a library move type's scoped-read containment --
              carries the sentence the game's author reads (``for_game``),
              naming the library and its definition. An `actor` read and a
              refusal reached through the game's answer to a Definition
              Contract stand at their own locations.
              Every Near Miss the bare-name and round `trump` refusals offer
              classifies where the refusal stands and is admitted there by
              every positional Owner Guard that refuses by the position record
              (``_name_positions``, read off the tree's shape alone, and
              ``_position_refuses``, the disjunction of the guards'
              predicates); a trick round's winner is offered the winners that
              round admits (``_winner_refusals``, the one producer the
              guards refusing a round's winner dispatch on). Held by Derived and Pinned
              (tests/test_near_miss_positions.py). A refused spelling's
              consequences are withheld where a fix drawn from the set it was
              looked up in could clear them, and only there: a node whose
              binder source is refused binds nothing, and a name in its scope
              spelled as a binder a fix would bind is not told
              (``_refused_binder_sources``, ``_membership_capture``); a
              phase's modes are judged after its transition targets resolve,
              and a target no sibling holds leaves undecided the role of every
              mode it could name (``_check_modes``). Held by Derived and
              Pinned: a withheld name is one lexical field (``withheld``), set
              where a binder is scoped and read by the one unresolved-name arm
              (tests/test_refusal_consequences.py).
Now illegal:  an unresolved name (``ref_kind is None``) or a dangling
              zone/rule/move-type/phase reference reaching a later pass; an entry's
              collection element outside the block's allow-list reaching the
              type layer; an undeclared ``always`` standing as the whole
              predicate of a clause ``_ALWAYS_SITES`` names, refused with
              the fix by ``_refuse_bare_always`` (its Owner Guard) where the
              predicate is classified, and read off the classified tree by
              ``_library_reach`` for a library's clauses;
              the runtime hard-fails on an unclassified name
              (``runtime/evaluate.py``, ``_name``) as its Shadow Guard. Also
              a ``state { }`` default that cannot be evaluated where it
              is written — one reading state not yet declared, calling a
              function, or containing a ``choose``
              (``_check_state_default_scope``). ``runtime/driver``'s
              ``_declare_state`` may therefore assume every default
              evaluates against the frames standing at that moment. And an
              equality comparison whose two operands are names that
              provably denote the same acting player — the binder of a
              construct that rebinds ``acting_as`` against the ``actor``
              pronoun, or against a ``let`` transitively bound to either
              (``_check_actor_alias_comparisons``, decisions.md "Naming
              the acting player twice"). This is a scope fact, not a type
              fact — both operands are ``Player`` — so it is settled here
              rather than in the type layer. And a subset source that
              names the same zone twice (``_check_subset_source``) -- a
              spelling fact, settled beside the other subset-shape guard.
              And a Kernel Definition Contract answered other than by the
              game's own one definition at the row's one Card parameter, or
              an answer that is not hermetic by reach — a pronoun, a
              `choose`, a zone not public to every observer, a bare
              per-player family, a phase's state, a Primitive, a Builtin
              outside `TRICK_ORDER_ROW_CALLS`, a later Trick Order answer
              (``_check_kernel_answers``, ``_check_answer_hermeticity``); the
              presence of a Trick Order is asked of ``kernel_contracts`` and
              of nothing else.
              And, for a game that ``uses`` a
              library, a game-introduced binder or declaration parameter
              spelled like a variable the library PROVIDES, where the game
              does not already bind that spelling at declaration level
              (``_check_provided_shadowed_by_binder``, decisions.md "Family
              libraries"). Like every other rule about provided state it is
              settled inside ``_apply_uses``, before the splice — afterwards
              the two are one flat declaration block and the distinction no
              longer exists to check. And, for a game that ``uses`` a
              library, anything the library brings in that a game clause the
              game lacks (or holds) gates — a Builtin call or a construct, by
              every row of ``_CLAUSE_GATES``, plus a literal ``lines(k)`` past
              the board — refused on the game's ``uses`` line
              (``_check_library_clause_gates``) before the splice, so the
              gates downstream meet it only as its Shadow Guards. Each row's
              test is the one its gate asks, and each row states the clause it
              gates and its role (``_ClauseGate.clause``, ``.role``). A
              library rule the game does not
              activate is not brought in, and is not judged against the game;
              nor is a library ``check_library_alone`` refuses, whose own
              author speaks first and alone.
              And a Primitive named by family-library text, as a call or in
              a ``round``'s query slot, refused to the library's author
              (``_check_library_encapsulation``) before the splice; the
              slot registries are ``_ROUND_QUERY_REGISTRIES``, which
              ``_validate_refs`` reads for every round. And a round
              ``trump`` clause on a winner whose body reads no
              trump (the winner-slot arm of ``_validate_refs``; the
              partition is ``TRUMP_READING_WINNERS``). And a game clause
              some ``_CLAUSE_GATES`` row reads (``role == "reader"``),
              written and refused by no Owner Guard of its own, that nothing
              in the written text -- the game's own text, every spliced
              definition and provided declaration, every activated library
              or stdlib rule, the clause's own body excluded -- meets with
              any of its reader rows' tests (``_check_unread_clauses``); an
              instrument read (the driver's card census, the OpenSpiel
              ranked policy's trump fallback) is no reader. Typecheck may
              therefore assume every reader clause it meets is read by
              written text. The round clause's TYPE (``Suit?``)
              is typecheck's (``_check_round_trump``); its presence against
              its winner is settled here, with the winner namespace. And a
              result ranking's target (``ranking_slot``) that is not a
              per-member score — unindexed, optional, or declared outside
              ``Integer``/``Boolean`` (``_check_winner_target``, decisions.md "Game result:
              `winner:` and `loser:`"); ``runtime/driver`` may therefore
              assume the target reads as a map from member to score, and
              hard-fails on one this pass did not admit as its Shadow Guard.
              And a ``teams:`` list that does not PARTITION the seats
              (``_check_teams``); every consumer building ``{p: ti for ti,
              members in enumerate(game.teams) for p in members}`` — the
              driver, the returns path, and the readiness proofs — may
              therefore read it as one.
              And a call, in a game that writes no ``primitives { }`` block,
              to any Primitive (``PRIMITIVE_CALL_FUNCS``, the declared-only
              arm of ``_validate_refs``): the name is in the corpus-wide
              namespace, so the unknown-name arm cannot speak for it, and a
              declaration is its only route to Python.
              ``typecheck``'s ``Call`` arm is the Shadow Guard behind this —
              no table states such a call's signature — with
              ``runtime/evaluate.py``'s ``native_call`` refusal behind that.
              And a ``primitives { }`` entry whose ``reads`` clause names a
              declaration the game states in more than one of the four
              namespaces such a name can be declared in — the game's own
              ``state { }``, a phase's, an indexed ``zones { }`` declaration,
              an unindexed one (``_check_primitive_reads``, over
              ``primitives_block``'s three collision predicates). Every name
              reaching ``classify_read`` is therefore single-membership,
              which is what lets ``runtime/driver``'s materialization call
              the same classifier with no refusal of its own.
              And, for a read carrying a [[phase-scoped-read]]'s ``in <phase>``
              tail: the tail names a real phase of the game, that phase's own
              ``state { }`` declares the name, no STRICT DESCENDANT of it
              re-declares the name, the phases ONE entry's clause names lie on
              one ancestor path — so their subtrees nest and the entry's
              REGION is the innermost's subtree, which is the intersection of
              the named subtrees — and every call of that entry sits inside
              that region, or in a game move type every offering mention of
              which does, or at a ``run`` site that does
              (``_check_read_tail``, ``_check_read_tails_nest``,
              ``_check_scoped_read_containment``). Like
              the actor-alias rule this is a SCOPE fact, not a type fact, so
              it is settled here; and necessarily before ``expand``, which
              erases the ``run`` sites a procedure body is judged at.
              ``runtime/driver`` may therefore assume EVERY named phase's
              frame stands, and holds its name, at every call this pass
              admits, and defends a scoped read with nothing but an
              Owner-naming [[shadow-guard]].
              And a zone read that its deciders cannot make, at a position
              ``HIDDEN_READ_POSITIONS`` classes as deciding, however the read
              is reached -- a ``let``, a function, a procedure, a phase
              outcome, a Primitive's ``reads``, a Builtin
              (``BUILTIN_ARGUMENT_READS``, ``BUILTIN_READS_NOTHING``,
              ``BUILTIN_IMPLICIT_READS``) -- judged by the declared zone
              projections (``stdlib.zones.reveals``, ``PROJECTION_LEVELS``)
              in ``_check_hidden_reads``: where no seat is deciding, a read
              not every seat can make; where a seat is deciding, a read that
              seat cannot make, being neither of a zone every seat sees nor
              of the deciding seat's own instance of a zone its owner sees.
              The refusal names the announcement the rules are missing; one
              reached through the game's answer to a library's call of a
              Definition Contract (``Call.contract``) is located in the
              game's text, at the last node the game wrote on the way to the
              read, and names the library, the row and the library's
              decision. The runtime's decision sites may therefore assume every zone read
              at those positions is visible to the seat deciding there:
              under Delegated Play a rule's clauses are judged against
              ``chooser_for(actor)``, since every rule is asked at the trick
              round's card decision, the one decision it routes, and the
              Play Source, or a trick round's source family named bare,
              reads the routed pool, whose visibility to that seat is the
              runtime Owner Guard ``runtime/delegation.check_decider_sees``'s.
              And, beside a rule clause reading the Play Source: a zone
              named ``hand`` not kept per player, a state variable named
              ``hand``, a game that runs no trick round, and a function a
              rule clause reaches that reads bare ``hand`` or a trick
              round's source family (``_check_play_source``); and a rule
              parameter named ``hand`` (``_refuse_play_source_params``).
              ``runtime/evaluate``'s ``play_source`` arm and its
              ``_hermetic_ctx``, which keeps no Play Source in a function
              body, are the Shadow Guards behind them. And a ``uses``
              line naming the standard library, whose rules need none.
              And an implicit decision pool -- one the kernel builds from a
              declared zone with no expression to read, the round-source and
              ``Card``-parameter rows of ``DECISION_POOLS`` -- whose family's
              type does not show its owner the cards in it
              (``_check_implicit_pools``). ``runtime/mechanics``' trick and
              climb forms and its parameter domains may therefore assume the
              deciding seat sees every card they offer from its own
              instance.
              And one of the game's own move types that no reachable
              ``offer`` presents, with or without a
              Stake row on it (``_check_unoffered_move_types``; a library's
              move types are exempt, since a game importing a library need
              not present every move type it offers); every game move type after this
              pass is one some reachable offering presents. And a Stake row no seat
              can read on a ``Card``-parameterized move type,
              whose action id is its card's (``_check_move_params``). Every
              row reaching a Seat Policy is therefore on a move type whose
              action ids name it. And, in a game with a climbing round, a
              move type spelled like one of the engine's own actions
              (``_check_climb_action_names``, over
              ``primitives.engine_actions``): the action space's name block
              and every rendering may therefore assume no move type and no
              climb action share a word.
              And, anywhere in what a [[hosted-poll]] body can execute — its
              own statements and every definition reachable from them by
              name (``HOSTED_REACH_POOLS``: a procedure it runs, a move type
              it offers, guard and effect, a function it calls, each
              transitively, by ``_definition_closure``) — a statement kind
              outside ``HOSTED_POLL_ALLOWED``, the ``state`` pronoun, or a call of a
              Primitive the game's namespace holds; and a Hosted Poll binder spelled like a name
              already classifiable where the clause is written
              (``_check_hosted_polls``, ``_check_hosted_binder``).
              ``runtime/mechanics``' ``run_decision_round`` may therefore
              assume a hosted body, and all it runs, moves no card, starts no
              round of the trick or climbing form, raises no outcome or jump
              out of the round, and reads no live Round State.
              And, wherever the engine keys a zone family by the acting seat
              -- a bare zone ``NameRef``, a round's ``source``, a Builtin in
              ``BUILTIN_IMPLICIT_READS`` -- a family not indexed by player,
              and for such a Builtin a family the game does not declare;
              and a round's ``into`` naming a family
              (``_check_bare_family_refs``). ``runtime/evaluate``'s ``_name``,
              ``runtime/mechanics``' round forms and ``runtime/reads``'
              ``magic_hand`` may therefore assume a seat is a key of every
              family they resolve that way, and ``_check_hidden_reads`` may
              credit a bare read as the acting seat's own instance.
              And, for a library's ``requires { }``: a row is a keyed
              declaration (state, zone) or a Definition Contract of a kind
              in ``CONTRACT_KINDS`` — derived, so a rule, which no library
              text can name, is never one — and every Definition Contract is
              answered by exactly one of the game's own definitions of its
              kind, at its parameters' positions and exact type spellings
              (``_check_definition_requirement``). Illegal after this pass: a
              row whose shape no game could answer, a library both defining
              and requiring a definition, a row answered by another library's
              definition, a function row spelled like a native name or a
              round callback, a procedure row a library procedure runs, and a
              move or procedure row the library never reaches
              (``_check_contract_shapes``, ``_check_definition_claims``). The
              splice records each answer: the game's answering function or
              procedure carries every row it answers (``contracts``), and
              every library call of a contracted function carries its own
              row (``Call.contract``), each stamp with the row's own span
              (``ContractStamp.row_span``), which a refusal naming the row
              cites —
              ``typecheck`` reads both, and nothing else about imports;
              ``_check_hidden_reads``, ``_check_play_source`` and the
              no-acting-seat walk read them to tell the game's author. A
              library ``run`` of a contracted procedure carries no stamp: its
              arity and parameter types are the row's by the check above, and
              a refusal there raises before ``typecheck`` runs. ``expand``
              needs no delta: a contracted procedure is a game procedure, run
              from a library move type's effect.
Verified by:  the per-guard diagnostic tests; the runtime Shadow Guard above.
              For the declare-time rule, the grid in
              ``tests/test_state_default_scope.py`` — which PLAYS every
              accepted cell rather than only resolving it, since
              "accepted" was exactly the assertion that hid the defect
              the grid was written for. For the Definition Contracts, the grid
              in ``tests/test_definition_contracts.py``.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.attribution import raise_if_errors
from cardlang.diagnostics import DiagnosticBag
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


def resolve(game: n.Game) -> n.Game:
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
    game, cats = classification.step(game, refused_binders, bag)
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
