"""Procedure expansion — the pass that makes `run` textual reuse.

Every `run NAME(args)` is replaced, in place, by the named procedure's body with
the arguments substituted for the parameters; `Game.procedures` is then emptied.
After this pass no `RunStmt` and no `ProcedureDef` exists, so the IR, the runtime,
and the OpenSpiel adapter never learn that procedures are a thing — they see the
statements. That is the whole safety argument for the construct (decisions.md
"Named procedures"): because the body IS the inline statements, the observation
events it emits, and therefore the information sets derived from them, are exactly
what inline text would have emitted. A procedure cannot open an info-set gap
because it does not exist at the layer where observations are emitted.

It runs AFTER typecheck, not inside resolve where rule-template instantiation
lives. That is a deliberate split, and the reason is the parameter types: a
procedure's `victim : Player` can only bite while the `run` site still exists to
check its arguments against. Expanding in resolve would leave those annotations
parsed and ignored — the accepted-but-ignored defect class — so the splice waits
until the checker has used them. (procedures.md §5.2 posed the choice; this is the
evidence that settled it.)
"""

from dataclasses import fields, is_dataclass, replace
from typing import cast

import cardlang.ast.nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Span
from cardlang.resolve import substitute


def expand(game: n.Game) -> n.Game:
    """Splice every procedure body into its `run` sites and consume the
    procedures. Resolve has already established that each `run` names a declared
    procedure, and typecheck that it passes the right arguments, so the only
    diagnostic left to raise here is the one neither could see: a body of more
    than one statement spliced into a slot that holds exactly one."""
    if not game.procedures:
        return game
    bag = DiagnosticBag()
    procs = {p.name: p for p in game.procedures}
    expanded = cast(n.Game, _rewrite(replace(game, procedures=()), procs, bag))
    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return expanded


def _body_for(
    run: n.RunStmt, procs: dict[str, n.ProcedureDef], bag: DiagnosticBag
) -> tuple[n.Stmt, ...]:
    """The procedure's body with this call's arguments substituted in. Matching on
    `ref_kind == "local"` is exact: inside the body, a parameter reference is the
    only thing classification could have tagged `local` under that name (resolve
    rejects a binder that shadows a parameter), so nothing else can be captured."""
    proc = procs[run.name]
    mapping = {p.name: a for p, a in zip(proc.params, run.args)}
    body = tuple(
        cast(n.Stmt, substitute(stmt, mapping, ref_kind="local")) for stmt in proc.body
    )
    return body


def _rewrite(node: object, procs: dict[str, n.ProcedureDef], bag: DiagnosticBag) -> object:
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value, procs, bag, owner=node, field=f.name)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(
    value: object,
    procs: dict[str, n.ProcedureDef],
    bag: DiagnosticBag,
    owner: object,
    field: str,
) -> object:
    if isinstance(value, tuple):
        # A statement SEQUENCE: a `run` splices into it, contributing as many
        # statements as its body holds (including none). This is the ordinary case
        # — every braced body in the grammar is a statement tuple.
        out: list[object] = []
        for item in value:
            if isinstance(item, n.RunStmt):
                out.extend(_body_for(item, procs, bag))
            else:
                out.append(_rewrite_value(item, procs, bag, owner=owner, field=field))
        return tuple(out)
    if isinstance(value, n.RunStmt):
        # A SINGLE-statement slot — `for each <role> <b>: <stmt>` and `each <role>
        # simultaneously: <stmt>` take one statement, not a braced block, so there
        # is nowhere to put a sequence. A one-statement procedure still fits;
        # anything else is a loud wall rather than a silent drop.
        body = _body_for(value, procs, bag)
        if len(body) == 1:
            return _rewrite_value(body[0], procs, bag, owner=owner, field=field)
        bag.error(
            f"procedure '{value.name}' has {len(body)} statements, so it cannot be "
            f"the whole body of `{_slot_name(owner)}`, which holds exactly one "
            f"statement — wrap the `run` in a braced body (an `if`, a `repeat "
            f"until`), or call it from a statement sequence",
            value.span,
        )
        return value
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, procs, bag)
    return value


def _slot_name(owner: object) -> str:
    if isinstance(owner, n.ForEach):
        return f"for each {owner.role} {owner.binder}:"
    if isinstance(owner, n.EachSimultaneous):
        return f"each {owner.role} simultaneously:"
    return "this single-statement body"
