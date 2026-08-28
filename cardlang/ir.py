"""Emit stage: checked AST -> validated IR.

The IR is the resolved AST rendered as a plain JSON-able dict — not desugared
(docs/building.md, "The AST↔IR seam"). Library constructs (phases, the `round`
construct, rules) are preserved as tagged nodes. Spans are a front-end
diagnostic concern and are deliberately omitted, so the IR is stable under
reformatting of the source and suitable for golden-file snapshots.

Every node carries a ``[[kind]]`` tag so an IR consumer can dispatch without
re-deriving shape. This emitter is the first consumer to walk the whole node
set, so its `match` statements are checked exhaustively (`assert_never`)
under ``mypy --strict``.

The IR is currently the *resolved* AST; type annotations are layered on when
the type checker grows.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the fully checked, procedure-free AST (post deck-capacity).
Establishes:  a JSON-able rendering that carries resolve's facts forward —
              ``ref_kind`` on every name, the resolved choose ceiling —
              never re-derives them.
Consumed by:  the CLI and the golden-file snapshots. The runtime and the
              OpenSpiel adapter do NOT run off this rendering: they consume
              the checked AST directly (``pipeline.check_source`` ->
              ``runtime/driver.play_game``). This emitter is a sidecar
              serialization, kept in lockstep by the goldens.
Verified by:  golden IR snapshots (tests/golden/) and the per-construct IR
              tests.
"""

from __future__ import annotations

import json
from typing import TypeAlias, assert_never

from cardlang.ast import nodes as n
from cardlang.board_domains import directions_of

# Not bumped for schema changes while nothing consumes serialized IR: the repo
# holds no reader, and the package is unpublished. It starts moving when there
# is something to protect (operator ruling, 2026-08-02).
IR_VERSION = 1

IRValue: TypeAlias = "dict[str, IRValue] | list[IRValue] | str | int | bool | None"
IRDict: TypeAlias = "dict[str, IRValue]"


def emit(game: n.Game) -> IRDict:
    """Lower a resolved :class:`Game` to the IR dict."""
    return {
        "cardlang_ir": IR_VERSION,
        "kind": "game",
        "name": game.name,
        "players": _players(game.players),
        "deck": game.deck,
        # Keyed ONLY for piece games — the card-game IR predates the field
        # and its goldens are byte-stable; an absent key means "card".
        **({"content_flavor": game.content_flavor} if game.content_flavor != "card" else {}),
        "direction": game.direction,
        "max_length": game.max_length,
        "ranking": list(game.ranking),
        # The source form: the convention keyword when one was written, else
        # None. `ranking` above is always the operative (expanded) order.
        "ranking_convention": game.ranking_convention,
        # Keyed ONLY when the game declares a `card_points { }` clause — the
        # `content_flavor` precedent, so clause-less games' IR goldens stay
        # byte-stable.
        **(
            {"card_points": _card_points_table(game.card_points)}
            if game.card_points is not None
            else {}
        ),
        # Keyed ONLY when the game declares a `trick_order { }` block — the
        # `card_points` precedent above, so block-less games' IR goldens stay
        # byte-stable.
        **(
            {"trick_order": _trick_order(game.trick_order)}
            if game.trick_order is not None
            else {}
        ),
        # Keyed ONLY when the game declares a `primitives { }` block, the same
        # precedent — and here the key's PRESENCE is itself a fact the IR must
        # carry, because the block's presence is what partitions the game's
        # native-call namespace. An EMPTY block therefore emits an empty entry
        # list rather than no key at all.
        **(
            {"primitives": _primitives(game.primitives)}
            if game.primitives is not None
            else {}
        ),
        "trump": game.trump,
        "teams": [list(t) for t in game.teams],
        "positions": [_position(p) for p in game.positions],
        # The board-minted movement-direction domain (decisions.md "Boards and
        # cells", rung-2 movement). Keyed ONLY for a board game, like
        # `content_flavor`: a boardless game mints no `dir` source, and an
        # absent key keeps the card-game IR byte-stable.
        **(
            {"directions": [_direction(name, members)
                            for name, members in directions_of(game).items()]}
            if game.board is not None
            else {}
        ),
        "zones": [_zone(z) for z in game.zones],
        "state": _state_block(game.state) if game.state else None,
        "phases": [_phase(p) for p in game.phases],
        "winner": _winner(game.winner) if game.winner else None,
        "loser": _loser(game.loser) if game.loser else None,
        "rules": [_rule(r) for r in game.rules],
        "move_types": [_move_type(m) for m in game.move_types],
        "types": [_type_def(t) for t in game.types],
        "defines": [_define(d) for d in game.defines],
        "functions": [_function(f) for f in game.functions],
    }


def to_json(game: n.Game) -> str:
    """Serialize the IR with stable, diff-friendly formatting."""
    return json.dumps(emit(game), indent=2) + "\n"


# --- header / declarations ---


def _players(p: n.PlayersSpec) -> IRDict:
    return {"kind": "players", "low": p.low, "high": p.high}


def _card_points_table(t: n.CardPointsTable) -> IRDict:
    return {
        "kind": "card_points_table",
        "entries": [
            {"kind": "card_points_entry", "rank": e.rank, "value": e.value}
            for e in t.entries
        ],
        "else_value": t.else_value,
    }


def _trick_order(t: n.TrickOrder) -> IRDict:
    """The game's [[trick-order]]. Rows keep SOURCE order (the node's), so the
    IR is a faithful record of what was written; the order they are READ in is
    the language's and is not a property of any one game."""
    return {
        "kind": "trick_order",
        "rows": [
            {"kind": "trick_order_row", "key": r.key, "body": _expr(r.body)}
            for r in t.rows
        ],
    }


def _primitives(b: n.PrimitivesBlock) -> IRDict:
    """The game's [[primitives-block]]. Entries keep SOURCE order (the node's),
    so the IR is a faithful record of what was written."""
    return {
        "kind": "primitives",
        "entries": [
            {
                "kind": "primitive_decl",
                "name": d.name,
                "params": [
                    {"kind": "primitive_param", "name": p.name, "type": p.type_name}
                    for p in d.params
                ],
                "return_type": d.return_type,
                "reads": [
                    {"kind": "primitive_read", "name": r.name, "binder": r.binder}
                    for r in d.reads
                ],
            }
            for d in b.decls
        ],
    }


def _position(p: n.PositionDecl) -> IRDict:
    # A named-member domain (the board-minted `cell`) carries its members; an
    # integer domain keeps its `lo`/`hi` form byte-for-byte (the board's IR
    # representation is exactly this minted domain — decisions.md "Boards and
    # cells").
    if p.members_named is not None:
        return {"kind": "position", "name": p.name, "members": list(p.members_named)}
    return {"kind": "position", "name": p.name, "lo": p.lo, "hi": p.hi}


def _direction(name: str, members: tuple[str, ...]) -> IRDict:
    # The board-minted `dir` domain rendered like a named-member `_position`,
    # but a SEPARATE top-level key: `dir` is not in `game.positions`.
    return {"kind": "direction", "name": name, "members": list(members)}


def _winner(w: n.Winner) -> IRDict:
    return {"kind": "winner", "rank_dir": w.rank_dir, "state_var": w.state_var}


def _loser(lo: n.Loser) -> IRDict:
    return {"kind": "loser", "selection": _expr(lo.selection)}


def _move_type(m: n.MoveTypeDef) -> IRDict:
    return {
        "kind": "move_type",
        "name": m.name,
        "params": [{"name": p.name, "type_name": p.type_name} for p in m.params],
        "when": _expr(m.when) if m.when is not None else None,
        "effect": [_stmt(s) for s in m.effect],
    }


def _function(f: n.FunctionDef) -> IRDict:
    return {
        "kind": "function",
        "name": f.name,
        "params": [{"name": p.name, "type_name": p.type_name} for p in f.params],
        "body": _expr(f.body),
    }


def _type_def(t: n.TypeDef) -> IRDict:
    return {
        "kind": "type_def",
        "name": t.name,
        "fields": [
            {
                "kind": "struct_field",
                "name": f.name,
                "type": f.type_name,
                "optional": f.optional,
            }
            for f in t.fields
        ],
        "derived": [
            {"kind": "derived_field", "name": d.name, "value": _expr(d.value)}
            for d in t.derived
        ],
    }


def _define(d: n.DefineDef) -> IRDict:
    return {
        "kind": "define",
        "name": d.name,
        "cases": [
            {
                "kind": "outcome_case",
                "tag": c.tag,
                "payload_types": list(c.payload_types),
            }
            for c in d.cases
        ],
        "body": [_stmt(s) for s in d.body],
    }


def _zone(z: n.ZoneDecl) -> IRDict:
    return {
        "kind": "zone",
        "name": z.name,
        "index": z.index,
        "type_ref": _type_ref(z.type_ref),
    }


def _type_ref(t: n.TypeRef) -> IRDict:
    return {"kind": "type_ref", "name": t.name, "args": [a.name for a in t.args]}


def _state_block(s: n.StateBlock) -> IRDict:
    return {"kind": "state", "decls": [_state_decl(d) for d in s.decls]}


def _state_decl(d: n.StateDecl) -> IRDict:
    return {
        "kind": "state_decl",
        "name": d.name,
        "index": d.index,
        "type": d.type_name,
        "optional": d.optional,
        "default": _expr(d.default),
    }


# --- phases ---


def _phase(p: n.Phase) -> IRDict:
    return {
        "kind": "phase",
        "name": p.name,
        "qualifier": _qualifier(p.qualifier) if p.qualifier else None,
        "outcome_cases": [
            {
                "kind": "outcome_case",
                "tag": c.tag,
                "payload_types": list(c.payload_types),
            }
            for c in p.outcome_cases
        ],
        "items": [_phase_item(i) for i in p.items],
    }


def _qualifier(q: n.PhaseQualifier) -> IRDict:
    return {"kind": "phase_qualifier", "qualifier": q.kind, "expr": _expr(q.expr)}


def _transition_to(t: n.TransitionTo) -> IRDict:
    return {
        "kind": "transition_to",
        "mode": t.mode,
        "event": {
            "kind": "move_event",
            "move_type": t.event.move_type,
            "where": _expr(t.event.where) if t.event.where else None,
        },
    }


def _phase_item(item: n.PhaseItem) -> IRDict:
    match item:
        case n.StateBlock():
            return _state_block(item)
        case n.ActiveRules():
            return {
                "kind": "active_rules",
                "refs": [_rule_ref(r) for r in item.refs],
            }
        case n.LegalMoves():
            return {"kind": "legal_moves", "move_types": list(item.move_types)}
        case n.Mode():
            return {
                "kind": "mode",
                "name": item.name,
                "active_rules": [
                    {"kind": "active_rules", "refs": [_rule_ref(r) for r in block.refs]}
                    for block in item.active_rules
                ],
                "transitions": [_transition_to(t) for t in item.transitions],
            }
        case n.BeforeEach():
            return {"kind": "before_each", "body": [_stmt(s) for s in item.body]}
        case n.AfterEach():
            return {"kind": "after_each", "body": [_stmt(s) for s in item.body]}
        case n.Phase():
            return _phase(item)
        case _:
            return _stmt(item)


# --- statements ---


def _stmt(s: n.Stmt) -> IRDict:
    match s:
        case n.Transfer():
            movement: IRDict = {
                "kind": "transfer",
                "verb": s.verb,
                "selection_mode": s.selection_mode,
                "amount": _amount(s.amount),
                "item": s.item,
                "source": _expr(s.source) if s.source else None,
                "dest": _expr(s.dest) if s.dest else None,
                "dest_each": s.dest_each,
                "distribution": s.distribution,
                "visibility": _expr(s.visibility) if s.visibility else None,
            }
            # Emitted ONLY when present, so every existing movement (none of
            # which uses `where`) stays byte-identical in its golden — this is
            # the whole point of the conditional key (plan §2e/§4). `joint`
            # rides the same convention: without it, a subset decision binding
            # `cards` would be IR-indistinguishable from a per-card filter
            # binding `card` — wrong semantics for any IR consumer.
            if s.where is not None:
                movement["where"] = _expr(s.where)
                if s.joint:
                    movement["joint"] = True
            return movement
        case n.EpistemicOp():
            op: IRDict = {"kind": "epistemic_op", "op": s.op, "zone": _expr(s.zone)}
            # Emitted ONLY when present, so `shuffle` (which never sets it)
            # stays byte-identical in its golden — same convention as
            # Transfer.where above.
            if s.where is not None:
                op["where"] = _expr(s.where)
            return op
        case n.RotateStmt():
            # The target is a `NameRef` in the AST (it is a write target and must be
            # classified like any other name), but the IR emits just its name: post-
            # resolve a write target is ALWAYS a state variable — every other
            # classification is rejected — so the `ref_kind` carries no information,
            # and flattening keeps the IR (and its goldens) exactly as it was.
            return {"kind": "rotate", "target": s.target.name, "values": list(s.values)}
        case n.EachSimultaneous():
            return {"kind": "each_simultaneous", "role": s.role, "body": _stmt(s.body)}
        case n.ForEach():
            return {
                "kind": "for_each",
                "role": s.role,
                "binder": s.binder,
                "body": _stmt(s.body),
            }
        case n.RepeatUntil():
            return {
                "kind": "repeat_until",
                "until": _expr(s.until),
                "body": [_stmt(x) for x in s.body],
            }
        case n.IfStmt():
            return {
                "kind": "if",
                "cond": _expr(s.cond),
                "then": [_stmt(x) for x in s.then_body],
                "else": (
                    [_stmt(x) for x in s.else_body]
                    if s.else_body is not None
                    else None
                ),
            }
        case n.AsBlock():
            return {
                "kind": "as",
                "player": _expr(s.player),
                "body": [_stmt(x) for x in s.body],
            }
        case n.Turns():
            return {
                "kind": "turns",
                "binder": s.binder,
                "leader": _expr(s.leader),
                "participants": _expr(s.participants),
                "until": _expr(s.until),
                "again": s.again,
                "body": [_stmt(x) for x in s.body],
            }
        case n.LetStmt():
            return {
                "kind": "let",
                "name": s.name,
                "index": s.index,
                "value": _expr(s.value),
            }
        case n.AssignStmt():
            return {
                "kind": "assign",
                "target": s.target.name,  # always a state variable post-resolve; see above
                "index_expr": _expr(s.index) if s.index else None,
                "op": s.op,
                "value": _expr(s.value),
            }
        case n.Offer():
            return {
                "kind": "offer",
                "player": _expr(s.player),
                "offering": list(s.offering),
            }
        case n.TrickRound():
            return {
                "kind": "trick_round",
                "move_type": s.move_type,
                "leader": _expr(s.leader),
                "participants": _expr(s.participants),
                "source_zone": s.source_zone,
                "play_zone": s.play_zone,
                "winner_fn": s.winner_fn,
                "trump": _expr(s.trump) if s.trump is not None else None,
                "early_termination": s.early_termination,
            }
        case n.AuctionRound():
            return {
                "kind": "auction_round",
                "offering": list(s.offering),
                "leader": _expr(s.leader),
                "participants": _expr(s.participants),
                "until": _expr(s.until),
                "order_mode": s.order_mode,
                "outcome_fn": s.outcome_fn,
            }
        case n.ClimbRound():
            return {
                "kind": "climb_round",
                "move_type": s.move_type,
                "leader": _expr(s.leader),
                "participants": _expr(s.participants),
                "source_zone": s.source_zone,
                "play_zone": s.play_zone,
                "combos_fn": s.combos_fn,
                "follows_fn": s.follows_fn,
                "until": _expr(s.until),
            }
        case n.Produce():
            return {
                "kind": "produce",
                "tag": s.tag,
                "payloads": [_expr(p) for p in s.payloads],
            }
        case n.Produces():
            return {
                "kind": "produces",
                "define": s.define,
                "arms": [
                    {
                        "kind": "produce_arm",
                        "tag": a.tag,
                        "binders": list(a.binders),
                        "body": [_stmt(x) for x in a.body],
                    }
                    for a in s.arms
                ],
            }
        case n.ContinueTo():
            return {"kind": "continue_to", "phase": s.phase}
        case n.SkipToNextHand():
            return {"kind": "skip_to_next_hand"}
        case n.Block():
            return {"kind": "block", "body": [_stmt(x) for x in s.body]}
        case n.RunStmt():
            # There is no IR for a procedure invocation, by design: `expand` has
            # already replaced it with the statements it stands for, so the IR
            # records what runs, not how it was spelled. A `run` here is a compiler
            # bug — emitting a placeholder node would silently teach every IR
            # consumer that procedures survive the front end.
            raise AssertionError(
                f"`run {s.name}(…)` reached IR emission; procedure expansion "
                f"(cardlang/expand.py) must run before `emit`"
            )
        case _ as unreachable:
            assert_never(unreachable)


def _amount(a: str | n.Expr) -> IRValue:
    return a if isinstance(a, str) else _expr(a)


def _named_arg(a: n.NamedArg) -> IRDict:
    value = a.value
    inner = _stmt(value) if isinstance(value, n.Transfer) else _expr(value)
    return {"kind": "named_arg", "name": a.name, "value": inner}


# --- rules ---


def _rule_ref(r: n.RuleRef) -> IRDict:
    ref: IRDict = {"kind": "rule_ref", "name": r.name, "delta": r.delta}
    # Emitted ONLY when present (like the rule `exempts` key), so every
    # argument-free reference's golden stays byte-identical.
    if r.args:
        ref["args"] = [_expr(a) for a in r.args]
    return ref


def _rule(r: n.RuleDef) -> IRDict:
    applies: IRValue = None
    if r.applies_when is not None:
        applies = {
            "kind": "applies_when",
            "always": r.applies_when.always,
            "pred": _expr(r.applies_when.pred) if r.applies_when.pred else None,
        }
    demands: IRValue = None
    if r.demands is not None:
        demands = {
            "kind": "demands",
            "form": r.demands.kind,
            "expr": _expr(r.demands.expr),
        }
    rule: IRDict = {
        "kind": "rule",
        "name": r.name,
        "constrains": r.constrains,
        "applies_when": applies,
        "demands": demands,
        "if_impossible": _expr(r.if_impossible) if r.if_impossible else None,
    }
    # Emitted ONLY when present (like the movement `filter` key), so every
    # existing rule's golden stays byte-identical.
    if r.exempts is not None:
        rule["exempts"] = _expr(r.exempts)
    return rule


# --- expressions ---


def _arg(a: n.Arg) -> IRValue:
    return _named_arg(a) if isinstance(a, n.NamedArg) else _expr(a)


def _expr(e: n.Expr) -> IRDict:
    match e:
        case n.NameRef():
            return {"kind": "name", "name": e.name, "ref": e.ref_kind}
        case n.IntLit():
            return {"kind": "int", "value": e.value}
        case n.StrLit():
            return {"kind": "str", "value": e.value}
        case n.CardLiteral():
            return {"kind": "card", "rank": e.rank, "suit": e.suit}
        case n.AllPlayers():
            return {"kind": "all_players"}
        case n.ListLit():
            return {"kind": "list", "elements": [_expr(x) for x in e.elements]}
        case n.Member():
            return {"kind": "member", "obj": _expr(e.obj), "field": e.field}
        case n.Subscript():
            return {"kind": "subscript", "obj": _expr(e.obj), "index_expr": _expr(e.index)}
        case n.StructLit():
            return {
                "kind": "struct_lit",
                "type": e.type_name,
                "fields": [
                    {"kind": "field_init", "name": fi.name, "value": _expr(fi.value)}
                    for fi in e.fields
                ],
            }
        case n.Call():
            return {"kind": "call", "func": e.func, "args": [_arg(a) for a in e.args]}
        case n.BinOp():
            return {
                "kind": "binop",
                "op": e.op,
                "left": _expr(e.left),
                "right": _expr(e.right),
            }
        case n.Not():
            return {"kind": "not", "operand": _expr(e.operand)}
        case n.IsCheck():
            return {"kind": "is_check", "check": e.kind, "operand": _expr(e.operand)}
        case n.Quantifier():
            return {
                "kind": "quantifier",
                "quant": e.kind,
                "role": e.role,
                "binder": e.binder,
                "body": _expr(e.body),
            }
        case n.IfExpr():
            return {
                "kind": "if_expr",
                "cond": _expr(e.cond),
                "then": _expr(e.then),
                "elifs": [[_expr(c), _expr(t)] for c, t in e.elifs],
                "otherwise": _expr(e.otherwise),
            }
        case n.Comprehension():
            comp: IRDict = {
                "kind": "comprehension",
                "agg": e.agg,
                "source": _expr(e.source),
                "binder": e.binder,
                "body": _expr(e.body),
            }
            # Emitted ONLY when present (like the rule `exempts` key), so
            # every unfiltered comprehension's golden stays byte-identical.
            if e.where is not None:
                comp["where"] = _expr(e.where)
            if e.default is not None:
                comp["default"] = _expr(e.default)
            return comp
        case n.DomainQuery():
            dq: IRDict = {
                "kind": "domain_query",
                "query": e.kind,
                "binder": e.binder,
                "where": _expr(e.where),
            }
            # Emitted only for the collection forms (the bare forms enumerate a
            # declared domain and have no source), keeping the key set minimal.
            if e.source is not None:
                dq["source"] = _expr(e.source)
            return dq
        case n.PlayerQuery():
            pq: IRDict = {"kind": "player_query", "query": e.kind, "where": _expr(e.where)}
            # Emitted only for the ring search (`first_from`), keeping the
            # other kinds' key set minimal (the DomainQuery `source` shape).
            if e.start is not None:
                pq["start"] = _expr(e.start)
            return pq
        case n.CardQuery():
            cq: IRDict = {
                "kind": "card_query",
                "query": e.kind,
                "source": _expr(e.source),
            }
            if e.where is not None:
                cq["where"] = _expr(e.where)
            return cq
        case n.Choose():
            # `ceiling` is the resolved static upper bound (decisions.md "The
            # integer `choose` domain") — a concrete int so an IR consumer can
            # size the integer action block directly, without re-deriving it
            # from a literal `hi` or re-parsing the `up to N` source.
            return {
                "kind": "choose",
                "domain": e.domain,
                "lo": _expr(e.lo),
                "hi": _expr(e.hi),
                "ceiling": n.static_ceiling(e),
            }
        case _ as unreachable:
            assert_never(unreachable)
