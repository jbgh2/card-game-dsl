"""Emit stage: type-annotated AST -> validated IR.

The IR is the resolved AST rendered as a plain JSON-able dict — not desugared
(docs/building.md, "The AST↔IR seam"). Library constructs (phases, the `Trick`
instantiation, rules) are preserved as tagged nodes. Spans are a front-end
diagnostic concern and are deliberately omitted, so the IR is stable under
reformatting of the source and suitable for golden-file snapshots.

Every node carries a ``kind`` tag so downstream consumers (the future
interpreter, the OpenSpiel adapter) can dispatch without re-deriving shape.
This emitter is the first consumer to walk the whole node set, so its `match`
statements are checked exhaustively (`assert_never`) under ``mypy --strict``.

The IR is currently the *resolved* AST; type annotations are layered on when
the type checker grows.
"""

from __future__ import annotations

import json
from typing import TypeAlias, assert_never

from cardlang.ast import nodes as n

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
        "direction": game.direction,
        "ranking": list(game.ranking),
        "trump": game.trump,
        "partnerships": [list(t) for t in game.partnerships],
        "zones": [_zone(z) for z in game.zones],
        "state": _state_block(game.state) if game.state else None,
        "phases": [_phase(p) for p in game.phases],
        "winner": _winner(game.winner) if game.winner else None,
        "loser": _loser(game.loser) if game.loser else None,
        "rules": [_rule(r) for r in game.rules],
        "routings": [_routing(r) for r in game.routings],
    }


def to_json(game: n.Game) -> str:
    """Serialize the IR with stable, diff-friendly formatting."""
    return json.dumps(emit(game), indent=2) + "\n"


# --- header / declarations ---


def _players(p: n.PlayersSpec) -> IRDict:
    return {"kind": "players", "low": p.low, "high": p.high}


def _winner(w: n.Winner) -> IRDict:
    return {"kind": "winner", "rank_dir": w.rank_dir, "target": w.target}


def _loser(lo: n.Loser) -> IRDict:
    return {"kind": "loser", "selection": _expr(lo.selection)}


def _routing(r: n.RoutingDef) -> IRDict:
    return {"kind": "routing", "name": r.name, "body": [_stmt(s) for s in r.body]}


def _zone(z: n.ZoneDecl) -> IRDict:
    return {
        "kind": "zone",
        "name": z.name,
        "index": z.index,
        "type": _type_ref(z.type_ref),
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
        "items": [_phase_item(i) for i in p.items],
    }


def _qualifier(q: n.PhaseQualifier) -> IRDict:
    return {"kind": "phase_qualifier", "qualifier": q.kind, "expr": _expr(q.expr)}


def _phase_item(item: n.PhaseItem) -> IRDict:
    match item:
        case n.StateBlock():
            return _state_block(item)
        case n.ActiveRules():
            return {
                "kind": "active_rules",
                "refs": [
                    {"kind": "rule_ref", "name": r.name, "op": r.op} for r in item.refs
                ],
            }
        case n.LegalMoves():
            return {"kind": "legal_moves", "names": list(item.names)}
        case n.TransitionTo():
            return {
                "kind": "transition_to",
                "target": item.target,
                "event": {
                    "kind": "move_event",
                    "move_type": item.event.move_type,
                    "where": _expr(item.event.where) if item.event.where else None,
                },
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
        case n.Movement():
            return {
                "kind": "movement",
                "verb": s.verb,
                "mode": s.mode,
                "amount": _amount(s.amount),
                "item": s.item,
                "source": _expr(s.source) if s.source else None,
                "dest": _expr(s.dest) if s.dest else None,
                "dest_each": s.dest_each,
                "distribution": s.distribution,
                "visibility": _expr(s.visibility) if s.visibility else None,
            }
        case n.EpistemicOp():
            return {"kind": "epistemic_op", "op": s.op, "target": _expr(s.target)}
        case n.RotateStmt():
            return {"kind": "rotate", "var": s.var, "values": list(s.values)}
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
                "cond": _expr(s.cond),
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
        case n.Instantiate():
            return {
                "kind": "instantiate",
                "mechanic": s.mechanic,
                "args": [_named_arg(a) for a in s.args],
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
                "name": s.name,
                "index": _expr(s.index) if s.index else None,
                "op": s.op,
                "value": _expr(s.value),
            }
        case n.Offer():
            raise NotImplementedError("Offer IR lowering not yet implemented")
        case _ as unreachable:
            assert_never(unreachable)


def _amount(a: str | n.Expr) -> IRValue:
    return a if isinstance(a, str) else _expr(a)


def _named_arg(a: n.NamedArg) -> IRDict:
    value = a.value
    inner = _stmt(value) if isinstance(value, n.Movement) else _expr(value)
    return {"kind": "named_arg", "name": a.name, "value": inner}


# --- rules ---


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
    return {
        "kind": "rule",
        "name": r.name,
        "constrains": r.constrains,
        "applies_when": applies,
        "demands": demands,
        "if_impossible": _expr(r.if_impossible) if r.if_impossible else None,
    }


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
        case n.Member():
            return {"kind": "member", "obj": _expr(e.obj), "field": e.field}
        case n.Subscript():
            return {"kind": "subscript", "obj": _expr(e.obj), "index": _expr(e.index)}
        case n.Call():
            return {"kind": "call", "func": e.func, "args": [_arg(a) for a in e.args]}
        case n.MethodCall():
            return {
                "kind": "method_call",
                "obj": _expr(e.obj),
                "method": e.method,
                "args": [_arg(a) for a in e.args],
            }
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
        case n.Lambda():
            return {"kind": "lambda", "param": e.param, "body": _expr(e.body)}
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
                "kind": "if",
                "cond": _expr(e.cond),
                "then": _expr(e.then),
                "elifs": [[_expr(c), _expr(t)] for c, t in e.elifs],
                "otherwise": _expr(e.otherwise),
            }
        case n.Comprehension():
            return {
                "kind": "comprehension",
                "agg": e.agg,
                "source": _expr(e.source),
                "binder": e.binder,
                "body": _expr(e.body),
            }
        case n.PlayerQuery():
            return {"kind": "player_query", "query": e.kind, "pred": _expr(e.pred)}
        case n.Choose():
            return {
                "kind": "choose",
                "domain": e.domain,
                "lo": _expr(e.lo),
                "hi": _expr(e.hi),
            }
        case _ as unreachable:
            assert_never(unreachable)
