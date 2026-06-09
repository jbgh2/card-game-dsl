# Typed outcomes — Stage 2: variant outcomes + user-defined types

Design spec for Stage 2 of the typed-outcomes initiative. Stage 1 (the
type-system foundation: `cardlang/types.py`, `cardlang/stdlib/signatures.py`,
and the real `cardlang/typecheck.py`) is merged on `main` (PR #4). Stage 2
builds out the two seams Stage 1 declared but left inert — `TStruct` and
`TVariant` — and wires variant outcomes onto a new kernel construct.

## Goal

Lift two more pieces of game logic into the DSL's type system:

1. **Variant outcome types** — a named unit declares a closed set of named
   variants with typed payloads (`-> { trump_declared(Suit) | bid_abandoned }`),
   its body *produces* one variant, and a consumer *matches* exhaustively. The
   checker enforces exhaustiveness and types the payloads.
2. **User-defined types** — `type Name = { field: T … } derived { … }` declares
   a struct-like value type, used for structured payloads (Bridge's `Contract`).

Both run end-to-end through the existing pipeline
(grammar → parse → resolve → typecheck → ir → runtime).

## Scope decisions (from brainstorming)

- **The home is `define`, param-light.** A variant outcome is "a named unit that
  resolves to a tagged result." `offer` is the atom (one decision, no result);
  `round` produces a single *untagged* Player (decisions.md: "the bare `outcome`
  is the shorthand for a single-payload result that needs no tag"). A *tagged*
  result's natural home is a named definition with a declared outcome type —
  `define`, which decisions.md "Interactive decisions" already commits the
  challenge/block/auction stdlib vocabulary to *being*. Stage 2 builds the
  **param-light** form: no parameter list, no invocation-as-expression. The body
  runs with the enclosing context bound (the `routing_def` precedent). Parameter
  scoping is deferred until the stdlib vocabulary actually lands (corpus-first:
  abstract at the third instance, not the first).
- **Full structs.** `type` declarations include `derived { … }` fields and real
  field-access typing — not just declaration. This is the complete
  Contract/HandResult shape from decisions.md "Typed object model".
- **Runs end-to-end** through the tree-walking runtime, not typecheck-only.
- **Validation by fixture, not corpus migration.** No corpus game uses variant
  outcomes today, so there is no migration forcing function. All 13 corpus games
  stay typecheck-clean and replay-green, untouched. The proof is a new runnable
  fixture plus negative tests.

## Surface syntax

### User-defined types

```
type Contract = {
  level : Integer
  suit  : Suit
}

type HandResult = {
  contract        : Contract
  tricks_required : Integer
  tricks_actual   : Integer
} derived {
  made = tricks_actual >= tricks_required
}
```

- A declared field is `NAME : TYPE_NAME ["?"]`. `TYPE_NAME` is any scalar
  (`Integer`, `Boolean`, …), enum (`Suit`, `Rank`, `Direction`), `Card`,
  `Player`/`Team`, or another user-defined type. `?` makes it optional.
- A `derived` field is `NAME "=" EXPR` — a computable function of the declared
  fields. Accessed identically to a declared field (`result.made`); stored
  nowhere; the compiler/runtime inlines it.
- **Deferred:** union-typed fields (`suit : Suit | NT`) and refinement types
  (`level : Integer in 1..7`). These are orthogonal sum-type / refinement
  features; the fixture does not need them, and adding them would expand the
  field-type grammar well past Stage 2's deliverable. A field that wants a small
  closed value set uses a deck/stdlib enum or is left `TAny` for now.

### Struct construction (an expression)

Needed so a struct value can flow as a variant payload:

```
Contract { level: 7, suit: hearts }
```

Fields by name, `:` separator, all declared fields required (Stage 2; partial
construction / update syntax deferred). Infers `TStruct("Contract", …)`.

### `define` and `produce`

```
define declare_trump -> { trump_declared(Suit) | bid_abandoned } {
  offer to bidder one of [pick_trump, abandon]
  if trump_was_picked {
    produce trump_declared(chosen_suit)
  } else {
    produce bid_abandoned
  }
}
```

- A top-level construct, alongside `rule_def` / `routing_def` / `move_type_def`.
- `-> { case ["(" TYPE ("," TYPE)* ")"] ("|" case)* }` declares the closed
  variant set. A bare case (`bid_abandoned`) has no payload; a case with parens
  (`trump_declared(Suit)`) carries typed payloads.
- The body is a statement block. `produce TAG [ "(" EXPR ("," EXPR)* ")" ]` is a
  **terminal** statement — it sets the definition's result and unwinds the body
  (like `return`). It is legal only inside a `define` body.

### `produces:` consumer

Naming a `define` both invokes it (param-light → no args) and dispatches on its
result. Braced arm bodies, matching the grammar's existing brace discipline for
statement blocks (`if_stmt`, `repeat_until`):

```
declare_trump produces:
  trump_declared(t) { trump := t }
  bid_abandoned     { score[bidder] -= current_bid }
```

- An arm is `TAG [ "(" BINDER ("," BINDER)* ")" ] "{" statement* "}"`.
- Binders bind the case's payloads as locals in the arm body, typed from the
  variant declaration (`t : Suit` above). This is **core payload typing**, in
  scope — distinct from the optional Stage-1 binder-typing fold-in.
- The consumer is built **once, against `TVariant`, independent of the host**, so
  Stage 3 can attach it to phases (`phase … produces:`) with zero rework.

> Doc reconciliation: decisions.md "Typed phase outcomes" renders consumer arms
> in colon-body style (`trump_declared(t):`). The real grammar uses braces for
> statement blocks. Since this consumer is shared with Stage 3, the decisions.md
> examples are updated to the braced arm form in this change (spec-not-history).

## Type-system pieces (`cardlang/types.py`)

- `TStruct(name, fields, derived)` is constructed from a `type` decl (the seam is
  already declared). `fields` maps field name → `Type` for declared *and* derived
  fields (derived inferred from its expression); `derived` is the frozenset of
  derived field names. Structural identity is by name: a `TStruct` is `assignable`
  / `unify`-compatible only with an equal `TStruct` (the existing `==` fast path
  covers it).
- `TVariant(name, cases)` is constructed from a define's declared outcome (seam
  already declared). `cases` maps tag → tuple of payload `Type`s.

No change to `unify`/`assignable`/`subscriptable` semantics is required beyond
the two new types flowing through their existing `==` / `TAny` paths.

## Checker rules (`cardlang/typecheck.py`)

- **Type registry.** `type_from_name` is extended to resolve a user-defined type
  name to its `TStruct` (today unknown names fall to `TAny`). A pre-pass builds
  the `name → TStruct` table from the game's `type` decls (derived-field types
  inferred against an env of the declared fields).
- **Field access** (`Member` arm of `infer`): if the receiver infers a `TStruct`,
  `.field` returns that field's type; an unknown field is a diagnostic. Otherwise
  the arm is unchanged (`TAny`) — pronoun member access and the `state.foo` /
  `player.hand` sugar stay permissive.
- **Struct literal** (new expr): infers `TStruct(name)`. Checks every declared
  field is present, each value is `assignable` to its field type, and there are
  no unknown fields.
- **`produce`**: `tag` must be in the define's `cases`; payload arity must match;
  each payload expr must be `assignable` to the declared payload type.
- **`produces:`**: arms must cover the case set *exactly* — every case present, no
  duplicate, no unknown tag. Binders are added to the arm-body env typed from the
  case payloads.

## IR (`cardlang/ir.py`)

New top-level emit entries for `type` and `define` decls; new `_stmt` cases for
`produce` and the `produces:` consumer; a new `_expr` case for the struct
literal. Mirrors the existing emit shape (annotate, don't rewrite — the IR stays
at the resolved-AST level).

## Runtime (`cardlang/runtime/`)

- **Struct value:** a name-tagged record (declared field values). `Member`
  evaluation reads a declared field or evaluates the derived expression on access
  (derived fields are computed, not stored). The struct literal evaluates each
  field expression.
- **`define` registry:** defines are indexed like routings (`define_index` on the
  runtime state). `produce` is terminal: it raises an internal produce-signal
  carrying the tag and evaluated payloads, caught by the define runner, which
  returns the tagged value.
- **`produces:` execution:** look up the define, run its body in a sub-context to
  obtain the tagged value, then bind the payload as locals (`with_local`, the
  existing binder mechanism) and run the matching arm in the enclosing context.

## Validation

- **Regression net.** `tests/test_typecheck_corpus.py` (all 13 games clean) and
  every `tests/test_playout_*.py` stay green, untouched.
- **Negative tests** (`tests/test_typecheck_errors.py`): non-exhaustive
  `produces:`; wrong payload type (in `produce` and in arm-binder use); unknown
  variant (in `produce` and in an arm); struct unknown-field; struct wrong
  field type.
- **Fixture:** a small runnable mini-game whose phase invokes a `define` that
  produces a struct-carrying variant, consumed by a `produces:` block — exercising
  both halves together, end-to-end through the runtime, with a deterministic
  chooser asserting the matched arm ran.

## Deferred (to track in roadmap.md)

- Union-typed and refinement-typed struct fields.
- Param-full `define` (parameter list + invocation-with-arguments +
  invocation-as-expression), until the challenge/block/auction stdlib vocabulary
  reaches three corpus instances.
- Stage 3: phase `→ outcome { … }` declaration + `produces:` control flow
  (reuses this Stage's consumer and `TVariant` machinery).
- The optional Stage-1 checker fold-ins (BinOp operand compatibility, movement
  `amount` must be Integer, rule `demands`/`applies_when` conditions, constraining
  `loser.selection` to Player, scoping binder types) — orthogonal to this Stage;
  fold in opportunistically if cheap, otherwise leave on the roadmap.

## Threading template

`offer`/`round` are the worked precedent for adding a construct; each new piece
follows the same path:

1. **grammar** (`cardlang/grammar/cardlang.lark`) — a production.
2. **AST** (`cardlang/ast/nodes.py`) — a frozen-dataclass node in the closed
   union (`Stmt`, `Expr`, or a new top-level `Node` member), dispatched by `match`
   + `typing.assert_never`.
3. **parse** (`cardlang/parse.py`) — a transformer method building the node.
4. **resolve** (`cardlang/resolve.py`) — name binding / reference validation
   (define names, type names, variant tags).
5. **typecheck** (`cardlang/typecheck.py`) — the rules above.
6. **ir** (`cardlang/ir.py`) — emit.
7. **runtime** (`cardlang/runtime/`) — execution.

Built with strict red/green TDD, one construct slice at a time, committing per
cycle. Strict mypy (`python -m mypy`) and `python -m pytest -q` stay green
throughout.
