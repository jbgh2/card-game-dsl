"""Procedure expansion — the pass that makes `run` reuse.

Every `run NAME(args)` is replaced, in place, by the named procedure's body; then
`Game.procedures` is emptied. After this pass no `RunStmt` and no `ProcedureDef`
exists, so the IR, the runtime, and the OpenSpiel adapter never learn that
procedures are a thing — they see the statements. That is the safety argument for
the construct (decisions.md "Named procedures"): because the body IS the inline
statements, the observation events it emits, and therefore the information sets
derived from them, are exactly what inline text would have emitted. A procedure
cannot open an info-set gap because it does not exist at the layer where
observations are emitted.

It runs AFTER typecheck, not inside resolve where rule-template instantiation
lives. That is deliberate: a procedure's `victim : Player` can only bite while the
`run` site still exists to check its arguments against. Expanding in resolve would
leave those annotations parsed and ignored — the accepted-but-ignored defect class.

Expansion is by VALUE, and it is hygienic
-----------------------------------------
A `run f(a, b)` becomes one block:

    if true {                  // a block: the DSL has no block statement, and
      let @f.p = a             // `if true` is the well-defined encoding of one
      let @f.q = b
      <body, with p -> @f.p and q -> @f.q>
    }

Two properties, each of which a naive by-name splice gets wrong, silently:

**Each argument is evaluated exactly once, in the caller's context, before the
body runs.** A by-name splice copies the argument expression to every place the
body reads its parameter — so `run bump(choose integer in 0 .. 1)`, ONE decision
in the written text, became one decision *per read*: two `choose` nodes, polled
independently, whose answers could differ, crediting two different players from a
single written choice. A parameter read zero times dropped the argument, and its
decision, entirely. And an argument naming state the body then mutates (`run
award(turn)` where the body assigns `turn`) denoted a different player on its
second read than its first. Binding each argument to a `let` up front makes the
call read the way it looks: arguments in, once, then the body. It is also what a
careful author writes by hand.

**The body's own bindings scope to the body.** The block is what does that. A bare
splice puts the body's `let`s into the caller's statement sequence, where they
shadow forward — so a procedure whose body binds `target` would silently capture
the caller's own `target`, read *after* the `run` site. State assignments and card
movements still persist, of course; only the `let` bindings are scoped, which is
exactly the difference between a procedure and a paste.

Together these mean the caller cannot corrupt the body and the body cannot corrupt
the caller. The one hygiene wall that remains is in resolve, and it must: a body
binder sharing a *parameter's* name is ambiguous at classification time (both are
`local`), so substitution cannot tell them apart. Resolve rejects that outright.

The temporary's name (`@f.p`) is deliberately unspellable — `@` and `.` are not in
the NAME terminal — so it can never collide with a user's binder, and two runs of
the same procedure in one block simply rebind it before each body, which the
sequential-`let` fold already handles.
"""

from dataclasses import fields, is_dataclass, replace
from typing import cast

import cardlang.ast.nodes as n
from cardlang.diagnostics import Span
from cardlang.resolve import substitute


def expand(game: n.Game) -> n.Game:
    """Splice every procedure body into its `run` sites and consume the procedures.

    Resolve has established that each `run` names a declared procedure, and
    typecheck that it passes the right arguments, so there is nothing left to
    reject here — expansion is total. Every `run` becomes exactly one statement (a
    block), which is why it fits both a statement sequence and the single-statement
    body slots (`for each <role> <b>: <stmt>`) without a special case."""
    if not game.procedures:
        return game
    procs = {p.name: p for p in game.procedures}
    return cast(n.Game, _rewrite(replace(game, procedures=()), procs))


def _expansion(run: n.RunStmt, procs: dict[str, n.ProcedureDef]) -> n.Stmt:
    proc = procs[run.name]
    span = run.span
    prologue: list[n.Stmt] = []
    mapping: dict[str, n.Expr] = {}
    for param, arg in zip(proc.params, run.args):
        tmp = f"@{run.name}.{param.name}"  # unspellable: `@`/`.` are not in NAME
        prologue.append(n.LetStmt(name=tmp, index=None, value=arg, span=span))
        mapping[param.name] = n.NameRef(name=tmp, ref_kind="local", span=arg.span)
    # Matching on `ref_kind == "local"` is exact: inside the body, a parameter
    # reference is the only thing classification could have tagged `local` under
    # that name — resolve rejects a body binder that shadows a parameter, which is
    # the case that would otherwise be ambiguous.
    body = tuple(
        cast(n.Stmt, substitute(stmt, mapping, ref_kind="local")) for stmt in proc.body
    )
    return n.IfStmt(
        cond=n.NameRef(name="true", ref_kind="bool", span=span),
        then_body=tuple(prologue) + body,
        else_body=None,
        span=span,
    )


def _rewrite(node: object, procs: dict[str, n.ProcedureDef]) -> object:
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value, procs)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(value: object, procs: dict[str, n.ProcedureDef]) -> object:
    if isinstance(value, n.RunStmt):
        # A `run` in a single-statement slot (`for each <role> <b>: <stmt>`) — and,
        # via the tuple arm below, in a statement sequence. One shape serves both,
        # because an expansion is always exactly one statement.
        return _expansion(value, procs)
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item, procs) for item in value)
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, procs)
    return value
