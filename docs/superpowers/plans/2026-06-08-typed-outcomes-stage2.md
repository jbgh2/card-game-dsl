# Typed Outcomes Stage 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build out the `TStruct` and `TVariant` type-system seams: user-defined `type` structs (with derived fields and field-access typing) and param-light `define` variant outcomes (`produce` / `produces:` with exhaustiveness + payload typing), running end-to-end through the runtime.

**Architecture:** Thread each new construct through the established pipeline — grammar (`cardlang/grammar/cardlang.lark`) → AST (`cardlang/ast/nodes.py`) → parse (`cardlang/parse.py`) → resolve (`cardlang/resolve.py`) → typecheck (`cardlang/typecheck.py`) → ir (`cardlang/ir.py`) → runtime (`cardlang/runtime/`). `offer`/`round` are the worked precedent. Validation is by a runnable fixture plus negative tests; the 13-game corpus stays green, untouched.

**Tech Stack:** Python 3.12, Lark (Earley) grammar, frozen-dataclass AST in closed unions dispatched by `match` + `typing.assert_never`, strict mypy (`python -m mypy`, no args), pytest (`python -m pytest -q`).

---

## Critical implementation notes (read before starting)

These come from design review and prevent silent test failures:

1. **Closed-union arms are forced.** The moment a node joins the `Stmt` or `Expr`
   union, the `assert_never` matches in `cardlang/ir.py` (`_stmt`/`_expr`),
   `cardlang/runtime/execute.py` (`execute`), `cardlang/runtime/evaluate.py`
   (`evaluate`), and `cardlang/typecheck.py` (`infer`) stop type-checking under
   mypy until every match gains an arm. So the task that introduces a `Stmt`/`Expr`
   node must add those arms in the same commit. Top-level nodes (`TypeDef`,
   `DefineDef`) are *not* in `Stmt`/`Expr`, so they only touch `ir.emit`.

2. **The checker walk is flat.** `typecheck()` builds one `env` and never extends
   it while descending (this is why `for each`/lambda binders infer `TAny`
   today, by design). Payload-binder typing therefore does **not** fall out of
   "add locals"; it needs a dedicated scoped sub-walk (Task V3 `_check_produces`).

3. **`_all_statements` does not visit `game.defines`.** It iterates routings,
   move_types, and phases. `produce` statements live in define bodies, so they
   are invisible to typecheck until `game.defines` is added to the walk (Task V3).

4. **Negative tests assert on content.** Every new negative test must assert a
   substring of the diagnostic (e.g. `assert "exhaustive" in str(ei.value)`) and,
   in its RED step, you must confirm it fails for the *expected* reason — not an
   unrelated parse/resolve error in the fixture. Bare `pytest.raises(DiagnosticError)`
   is insufficient for brand-new constructs.

5. **Nested exprs need surfacing.** `_child_exprs` (in typecheck) is isinstance-based,
   not `assert_never` — mypy stays green while unsurfaced sub-exprs go unchecked.
   Add `StructLit` field values to `_child_exprs`/`_stmt_exprs` and `Produce`
   payloads to `_stmt_exprs` explicitly.

Run `python -m mypy && python -m pytest -q` as the green bar for every task.

---

## File-by-file responsibilities

- `cardlang/grammar/cardlang.lark` — new productions: `type_def`, `define_def`,
  `produce_stmt`, `produces_stmt`, `struct_lit`.
- `cardlang/ast/nodes.py` — new nodes: `TypeDef`, `StructField`, `DerivedField`,
  `DefineDef`, `VariantCase`, `Produce`, `ProduceArm`, `Produces`, `FieldInit`,
  `StructLit`; `Game.types`/`Game.defines` fields; union updates.
- `cardlang/parse.py` — transformer methods building those nodes; `start()`
  collects `types`/`defines`.
- `cardlang/resolve.py` — register type/define names; struct-field-scoped
  classification for derived bodies; arm-binder locals; validate `Produces.define`
  and `StructLit.type_name`.
- `cardlang/typecheck.py` — `TStruct`/`TVariant` registries, field-access typing,
  struct-literal checks, define-outcome checks, scoped `produces:` exhaustiveness
  + binder typing.
- `cardlang/ir.py` — emit the new top-level decls, statements, and the struct expr.
- `cardlang/runtime/state.py` — `RuntimeState.define_index`/`type_index`;
  `StructValue`; `_ProduceSignal`.
- `cardlang/runtime/execute.py` — `Produce`/`Produces` execution.
- `cardlang/runtime/evaluate.py` — `StructLit` construction; struct member/derived.
- `cardlang/runtime/driver.py` — populate `define_index`/`type_index`.
- `cardlang/types.py` — no semantic change; `TStruct`/`TVariant` already declared.

Test files (new): `tests/test_type_decl.py`, `tests/test_struct_typing.py`,
`tests/test_struct_runtime.py`, `tests/test_define_parse.py`,
`tests/test_variant_runtime.py`, `tests/test_variant_typing.py`,
`tests/test_typed_outcomes_fixture.py`. Extend: `tests/test_typecheck_errors.py`.

---

## Task S1: `type` declarations — parse, resolve, ir

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (top_item ~line 10-13; add productions near `state_decl` ~line 58)
- Modify: `cardlang/ast/nodes.py` (add nodes; `Game` ~line 608; `Node` union ~line 629)
- Modify: `cardlang/parse.py` (transformer methods; `start()` ~line 765)
- Modify: `cardlang/resolve.py` (`_categories` ~line 197; `_classify_names`/`_rewrite` ~line 250; `_validate_refs` ~line 283)
- Modify: `cardlang/ir.py` (`emit` ~line 31; add `_type_def`)
- Test: `tests/test_type_decl.py`

- [ ] **Step 1: Write the failing parse test**

```python
# tests/test_type_decl.py
from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.parse import parse_text

TYPES = """
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
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  winner: highest score
  state { score[player] : Integer = 0 }
}
"""


def test_type_decls_parse_into_game() -> None:
    game = parse_text(TYPES, "g.cardlang")
    assert [t.name for t in game.types] == ["Contract", "HandResult"]
    contract = game.types[0]
    assert [(f.name, f.type_name, f.optional) for f in contract.fields] == [
        ("level", "Integer", False),
        ("suit", "Suit", False),
    ]
    hand_result = game.types[1]
    assert [d.name for d in hand_result.derived] == ["made"]
    assert isinstance(hand_result.derived[0].value, n.BinOp)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_type_decl.py -q`
Expected: FAIL — `parse_text` raises on `type` (unknown start token) or `game.types` does not exist.

- [ ] **Step 3: Add grammar productions**

In `cardlang/grammar/cardlang.lark`, extend `top_item` (line 10-13) with
`type_def` only (`define_def` is added to `top_item` in Task V1, alongside its
production, so there is no dangling rule reference):

```
?top_item: game
         | rule_def
         | routing_def
         | move_type_def
         | type_def
```

Add productions after `state_decl` (after line 60). Reuse the existing
`type_name` rule for optional/plain field types:

```
// User-defined struct type: named fields plus optional computed `derived` fields.
type_def: "type" NAME "=" "{" struct_field* "}" [derived_block]
struct_field: NAME ":" type_name
derived_block: "derived" "{" derived_field* "}"
derived_field: NAME "=" expr
```

- [ ] **Step 4: Add AST nodes**

In `cardlang/ast/nodes.py`, add near the other top-level decls (after `MoveTypeDef`, ~line 558):

```python
@dataclass(frozen=True, slots=True)
class StructField:
    """A declared struct field: `name : Type['?']`."""

    name: str
    type_name: str
    optional: bool
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DerivedField:
    """A computed struct field: `name = <expr>` over the declared fields."""

    name: str
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class TypeDef:
    """`type Name = { field: T … } [derived { name = expr … }]` — a user-defined
    struct value type."""

    name: str
    fields: tuple[StructField, ...]
    derived: tuple[DerivedField, ...]
    span: Span | None = None
```

Add `types` to `Game` (after `move_types`, line 625):

```python
    move_types: tuple[MoveTypeDef, ...] = ()
    types: tuple[TypeDef, ...] = ()
    span: Span | None = None
```

Add `TypeDef | StructField | DerivedField` to the `Node` union (~line 629).

- [ ] **Step 5: Add parse transformer methods**

In `cardlang/parse.py`, add methods (near `state_decl`, after line 269). Reuse
the `_TypeName` helper that `optional_type`/`plain_type` already produce:

```python
    def struct_field(self, meta: Meta, c: list[object]) -> n.StructField:
        assert isinstance(c[1], _TypeName)
        return n.StructField(
            name=str(c[0]),
            type_name=c[1].name,
            optional=c[1].optional,
            span=self._span(meta),
        )

    def derived_field(self, meta: Meta, c: list[object]) -> n.DerivedField:
        return n.DerivedField(
            name=str(c[0]), value=_as_expr(c[1]), span=self._span(meta)
        )

    def derived_block(self, meta: Meta, c: list[n.DerivedField]) -> tuple[n.DerivedField, ...]:
        return tuple(c)

    def type_def(self, meta: Meta, c: list[object]) -> n.TypeDef:
        name = str(c[0])
        fields = tuple(x for x in c if isinstance(x, n.StructField))
        derived = next((x for x in c if isinstance(x, tuple)), ())
        return n.TypeDef(
            name=name, fields=fields, derived=derived, span=self._span(meta)
        )
```

Update `start()` (line 765) to collect types:

```python
    def start(self, meta: Meta, c: list[object]) -> n.Game:
        game = next(x for x in c if isinstance(x, n.Game))
        rules = tuple(x for x in c if isinstance(x, n.RuleDef))
        routings = tuple(x for x in c if isinstance(x, n.RoutingDef))
        move_types = tuple(x for x in c if isinstance(x, n.MoveTypeDef))
        types = tuple(x for x in c if isinstance(x, n.TypeDef))
        return replace(
            game, rules=rules, routings=routings, move_types=move_types, types=types
        )
```

- [ ] **Step 6: Add resolve handling (register types; scope derived-field bodies)**

Derived-field bodies reference sibling field names as bare names; the generic
name-classification pass would call them unresolved. Resolve them in a scoped
pass and skip the generic walk for `TypeDef`.

In `cardlang/resolve.py`, in `_rewrite` (line 258), make `TypeDef` opaque to the
generic walk (add at the top of `_rewrite`, after the `NameRef` branch):

```python
    if isinstance(node, n.TypeDef):
        return node  # derived bodies are rewritten by _classify_type_derived
```

In `_classify_names` (line 250), after the generic rewrite, rewrite each type's
derived bodies with the type's fields in local scope:

```python
def _classify_names(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> n.Game:
    """Immutably rewrite every NameRef with its classification, recording an
    error for any name that resolves to nothing."""
    result = _rewrite(game, cats, bag)
    assert isinstance(result, n.Game)
    types = tuple(_classify_type_derived(t, cats, bag) for t in result.types)
    return replace(result, types=types)


def _classify_type_derived(
    tdef: n.TypeDef, cats: _Categories, bag: DiagnosticBag
) -> n.TypeDef:
    field_names = frozenset(f.name for f in tdef.fields)
    scoped = replace(cats, locals=cats.locals | field_names)
    derived = tuple(
        replace(d, value=_rewrite(d.value, scoped, bag))  # type: ignore[arg-type]
        for d in tdef.derived
    )
    return replace(tdef, derived=derived)
```

In `_validate_refs` (line 283), add a check that struct literals (Task S3) and
later constructs name known types; for now just record the defined type names for
reuse. Add near the top of `_validate_refs`:

```python
    defined_types = {t.name for t in game.types}
```

(`defined_types` is used in S3/V1; leaving it computed now is harmless.)

- [ ] **Step 7: Add ir emit**

In `cardlang/ir.py`, add `"types"` to `emit()` (after `move_types`, line 50):

```python
        "move_types": [_move_type(m) for m in game.move_types],
        "types": [_type_def(t) for t in game.types],
```

Add the emitter (after `_move_type`, ~line 85):

```python
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
```

- [ ] **Step 8: Run tests to verify GREEN**

Run: `python -m pytest tests/test_type_decl.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — the new test passes; mypy clean; all 149 prior tests still pass.

- [ ] **Step 9: Commit**

```bash
git add cardlang/grammar/cardlang.lark cardlang/ast/nodes.py cardlang/parse.py cardlang/resolve.py cardlang/ir.py tests/test_type_decl.py
git commit -m "$(printf 'typed-outcomes: type declarations (parse + resolve + ir)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task S2: struct typing — TStruct registry, field-access typing, derived types

**Files:**
- Modify: `cardlang/typecheck.py` (`type_from_name` ~line 61; `TypeEnv` ~line 94; `env_from_game` ~line 219; `infer` `Member` arm ~line 157)
- Test: `tests/test_struct_typing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_struct_typing.py
from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.parse import parse_text
from cardlang.resolve import resolve
from cardlang.typecheck import env_from_game, infer
from cardlang.types import TBoolean, TEnum, TInteger, TStruct

SRC = """
type Contract = {
  level : Integer
  suit  : Suit
}
type HandResult = {
  tricks_required : Integer
  tricks_actual   : Integer
} derived {
  made = tricks_actual >= tricks_required
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { deal : Contract = none  result : HandResult = none }
  winner: highest score
}
"""


def _env():
    game = resolve(parse_text(SRC, "g.cardlang"))
    return game, env_from_game(game)


def test_struct_state_var_field_access_is_typed() -> None:
    _game, env = _env()
    deal = n.NameRef("deal", ref_kind="state_var")
    assert isinstance(infer(deal, env), TStruct)
    assert infer(n.Member(deal, "level"), env) == TInteger()
    assert infer(n.Member(deal, "suit"), env) == TEnum("Suit")


def test_derived_field_is_typed_from_its_expression() -> None:
    _game, env = _env()
    result = n.NameRef("result", ref_kind="state_var")
    # `made = tricks_actual >= tricks_required` infers Boolean.
    assert infer(n.Member(result, "made"), env) == TBoolean()


def test_unknown_field_infers_permissively_but_known_fields_win() -> None:
    _game, env = _env()
    deal = n.NameRef("deal", ref_kind="state_var")
    # A field not on the struct stays permissive (the error is raised in _check_expr).
    from cardlang.types import TAny
    assert infer(n.Member(deal, "nonesuch"), env) == TAny()
```

> Note: `deal : Contract = none` requires `none` to be assignable to a struct
> state var. A struct state var initialised to `none` reads as the struct's
> declared type for field access (the DSL has no flow narrowing, like every other
> optional/`none` default in the corpus). `type_from_name` returns the bare
> `TStruct`; the `none` default is accepted by the existing `TNull`→`TAny`/optional
> handling only if optional. To keep S2 self-contained, declare these as `Contract`
> (non-optional) and rely on the existing assignability of `none` being checked
> elsewhere — if the resolve/typecheck of the `none` default trips, change the
> defaults to a struct literal in S3 and gate this test behind S3. For S2, if the
> `none` default raises, use `state { }` empty and build the env manually:
> `TypeEnv(state_vars={"deal": structs["Contract"], "result": structs["HandResult"]}, structs=structs)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_struct_typing.py -q`
Expected: FAIL — `infer(Member(...))` returns `TAny` (the deferred arm), not the field type.

- [ ] **Step 3: Build the struct registry and thread it through `TypeEnv`**

In `cardlang/typecheck.py`, add `structs` to `TypeEnv` (line 94):

```python
@dataclass(frozen=True)
class TypeEnv:
    state_vars: Mapping[str, Type] = field(default_factory=dict)
    zones: Mapping[str, Type] = field(default_factory=dict)
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)
    structs: Mapping[str, "TStruct"] = field(default_factory=dict)

    def with_local(self, name: str, t: Type) -> "TypeEnv":
        return replace(self, locals={**self.locals, name: t})
```

Import `TStruct` from `cardlang.types` (extend the existing import block, line 30).

Change `type_from_name` to take the struct registry (line 61):

```python
def type_from_name(name: str, optional: bool, structs: Mapping[str, "TStruct"]) -> Type:
    """Map a declared type name to a `Type`. User-defined struct names resolve to
    their `TStruct`; still-unknown names resolve to the permissive `TAny`."""
    base: Type
    if name in _SCALAR_TYPES:
        base = _SCALAR_TYPES[name]()
    elif name in _ENUM_TYPES:
        base = TEnum(name)
    elif name in structs:
        base = structs[name]
    else:
        base = TAny()
    return TOptional(base) if optional else base
```

Add a builder for the registry (near `value_enum_map`, ~line 77):

```python
def struct_registry(game: Game) -> dict[str, TStruct]:
    """Build the user-defined struct types. Declared fields resolve eagerly;
    derived fields are typed in an env of the declared fields, so each `TStruct`
    carries both declared and derived field types under one mapping."""
    structs: dict[str, TStruct] = {}
    for tdef in game.types:
        fields: dict[str, Type] = {}
        for f in tdef.fields:
            fields[f.name] = type_from_name(f.type_name, f.optional, structs)
        field_env = TypeEnv(locals=dict(fields), structs=structs)
        for d in tdef.derived:
            fields[d.name] = infer(d.value, field_env)
        structs[tdef.name] = TStruct(
            name=tdef.name,
            fields=fields,
            derived=frozenset(d.name for d in tdef.derived),
        )
    return structs
```

> Ordering note: a struct field whose type is another user type only resolves if
> the referenced type was declared earlier (the `structs` dict is built in source
> order). The corpus/fixture declares dependencies first (Contract before
> HandResult). Forward references resolve to `TAny` — acceptable for Stage 2; note
> in roadmap.

- [ ] **Step 4: Type field access in `infer`; wire the registry into `env_from_game`**

Replace the `Member` arm of `infer` (line 157). Split `Member` from `Lambda`:

```python
        case n.Member():
            obj = infer(e.obj, env)
            if isinstance(obj, TStruct):
                return obj.fields.get(e.field, TAny())
            return TAny()  # pronoun member access / sugar: deferred
        case n.Lambda():
            return TAny()  # lambda values: deferred
```

In `env_from_game` (line 219), build the registry first and pass it to
`type_from_name`:

```python
def env_from_game(game: Game) -> TypeEnv:
    structs = struct_registry(game)
    state_vars: dict[str, Type] = {}
    for block in _state_blocks(game):
        for decl in block.decls:
            t = type_from_name(decl.type_name, decl.optional, structs)
            state_vars[decl.name] = TCollection(t) if decl.index is not None else t
    zones: dict[str, Type] = {
        z.name: ZONE_CONTENT.get(z.type_ref.name, TCollection(TAny()))
        for z in game.zones
    }
    return TypeEnv(
        state_vars=state_vars,
        zones=zones,
        value_enums=value_enum_map(game),
        structs=structs,
    )
```

- [ ] **Step 5: Run tests to verify GREEN**

Run: `python -m pytest tests/test_struct_typing.py tests/test_infer.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — struct field/derived inference works; corpus + mypy clean.

- [ ] **Step 6: Commit**

```bash
git add cardlang/typecheck.py tests/test_struct_typing.py
git commit -m "$(printf 'typed-outcomes: struct typing — TStruct registry, field + derived inference\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task S3: struct literal expression — parse, ir, runtime construction, typecheck

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (`primary` ~line 281)
- Modify: `cardlang/ast/nodes.py` (`FieldInit`, `StructLit`; `Expr` union)
- Modify: `cardlang/parse.py` (transformer methods)
- Modify: `cardlang/ir.py` (`_expr` ~line 299)
- Modify: `cardlang/runtime/state.py` (`StructValue`)
- Modify: `cardlang/runtime/evaluate.py` (`evaluate` ~line 18; `_member` ~line 116)
- Modify: `cardlang/typecheck.py` (`infer` Expr arm; `_check_expr` ~line 310; `_child_exprs` ~line 280)
- Modify: `cardlang/resolve.py` (`_validate_refs`)
- Test: `tests/test_struct_runtime.py`, extend `tests/test_typecheck_errors.py`

- [ ] **Step 1: Write the failing parse + typecheck-negative tests**

```python
# tests/test_struct_runtime.py
from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.parse import parse_text


def test_struct_literal_parses_in_expression_position() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state { deal : Contract = Contract { level: 1, suit: hearts } }
      winner: highest score
    }
    """
    game = parse_text(src, "g.cardlang")
    default = game.state.decls[0].default
    assert isinstance(default, n.StructLit)
    assert default.type_name == "Contract"
    assert [(fi.name) for fi in default.fields] == ["level", "suit"]
```

Add a negative to `tests/test_typecheck_errors.py`:

```python
def test_rejects_struct_literal_missing_field() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state { deal : Contract = Contract { level: 1 } }
      winner: highest score
    }
    """
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "suit" in str(ei.value) or "field" in str(ei.value)


def test_rejects_struct_literal_wrong_field_type() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state { deal : Contract = Contract { level: hearts, suit: hearts } }
      winner: highest score
    }
    """
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "level" in str(ei.value) or "Integer" in str(ei.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_struct_runtime.py "tests/test_typecheck_errors.py::test_rejects_struct_literal_missing_field" "tests/test_typecheck_errors.py::test_rejects_struct_literal_wrong_field_type" -q`
Expected: FAIL — parse rejects `Contract { … }`; the negatives raise nothing (no checks yet).

- [ ] **Step 3: Add grammar + AST + parse**

Grammar — add to `primary` (line 281) and the productions:

```
?primary: card_literal
        | all_players
        | choose_expr
        | call
        | struct_lit
        | INT               -> int_lit
        | STRING            -> str_lit
        | NAME              -> name_ref
        | "(" expr ")"

struct_lit: NAME "{" field_init ("," field_init)* "}"
field_init: NAME ":" expr
```

> Earley note: `struct_lit` (`NAME "{"`) sits only in expression position, distinct
> from statement-level `NAME "{"` uses (which all require a keyword like
> `move_type`/`type`/`define`). If the parser reports ambiguity once `define`/match
> land, tighten by requiring at least one `field_init` (done) and re-running the
> grammar tests. Keep the corpus green as the arbiter.

AST (`cardlang/ast/nodes.py`), near the expression nodes (after `Subscript`, ~line 84):

```python
@dataclass(frozen=True, slots=True)
class FieldInit:
    """One `name: value` pair in a struct literal."""

    name: str
    value: Expr
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class StructLit:
    """`TypeName { field: expr, … }` — constructs a user-defined struct value."""

    type_name: str
    fields: tuple[FieldInit, ...]
    span: Span | None = None
```

Add `StructLit` to the `Expr` union and `StructLit | FieldInit` to `Node`.

Parse (`cardlang/parse.py`):

```python
    def field_init(self, meta: Meta, c: list[object]) -> n.FieldInit:
        return n.FieldInit(name=str(c[0]), value=_as_expr(c[1]), span=self._span(meta))

    def struct_lit(self, meta: Meta, c: list[object]) -> n.StructLit:
        return n.StructLit(
            type_name=str(c[0]),
            fields=tuple(x for x in c[1:] if isinstance(x, n.FieldInit)),
            span=self._span(meta),
        )
```

- [ ] **Step 4: Add ir, runtime construction, and infer arm (forced by the Expr union)**

ir (`cardlang/ir.py`, `_expr`, after `AllPlayers`, ~line 310):

```python
        case n.StructLit():
            return {
                "kind": "struct_lit",
                "type": e.type_name,
                "fields": [
                    {"kind": "field_init", "name": fi.name, "value": _expr(fi.value)}
                    for fi in e.fields
                ],
            }
```

Runtime value (`cardlang/runtime/state.py`, near `Move`, ~line 146):

```python
@dataclass(frozen=True, slots=True)
class StructValue:
    """A constructed user-defined struct: its type name plus declared field
    values. Derived fields are computed on access (see evaluate._member)."""

    type_name: str
    fields: dict[str, Any]
```

evaluate (`cardlang/runtime/evaluate.py`, `evaluate`, after `AllPlayers`, ~line 29):

```python
        case n.StructLit():
            return StructValue(
                e.type_name, {fi.name: evaluate(fi.value, ctx) for fi in e.fields}
            )
```

Import `StructValue` into evaluate (line 14). Extend `_member` (line 116) so a
`StructValue`'s declared fields read out (derived handled in S4):

```python
def _member(obj: Any, field: str) -> Any:
    if isinstance(obj, Card):
        return getattr(obj, field)
    if isinstance(obj, Move):
        return getattr(obj, field)
    if isinstance(obj, StructValue):
        return obj.fields[field]
    if isinstance(obj, dict):
        return obj[field]
    raise AssertionError(f"cannot read field '{field}' of {obj!r}")
```

infer arm (`cardlang/typecheck.py`, `infer`) — add before `Member`:

```python
        case n.StructLit():
            return env.structs.get(e.type_name, TAny())
```

- [ ] **Step 5: Add struct-literal checks and surface nested exprs**

In `cardlang/typecheck.py` `_child_exprs` (line 280), surface the field values so
their sub-expressions get checked:

```python
    if isinstance(e, n.StructLit):
        return [fi.value for fi in e.fields]
```

In `_check_expr` (line 310), add field-presence + field-type validation:

```python
    elif isinstance(e, n.StructLit):
        struct = env.structs.get(e.type_name)
        if struct is not None:
            declared = {k for k in struct.fields if k not in struct.derived}
            provided = {fi.name for fi in e.fields}
            for missing in sorted(declared - provided):
                bag.error(f"{e.type_name} {{}} is missing field '{missing}'", e.span)
            for extra in sorted(provided - set(struct.fields)):
                bag.error(f"{e.type_name} {{}} has unknown field '{extra}'", e.span)
            for fi in e.fields:
                expected = struct.fields.get(fi.name)
                if expected is None or fi.name in struct.derived:
                    continue
                got = infer(fi.value, env)
                if not assignable(got, expected):
                    bag.error(
                        f"field '{fi.name}' expects {_type_name(expected)}, "
                        f"got {_type_name(got)}",
                        e.span,
                    )
```

> The `_check_expr` recursion already visits `_child_exprs(e)` first, so nested
> struct literals and their field values are checked depth-first.

Also add the unknown-field diagnostic for `Member` access on a struct (so the
S2 "unknown field" path reports). In `_check_expr`, extend the `Subscript` branch
area with a `Member` branch:

```python
    elif isinstance(e, n.Member):
        obj = infer(e.obj, env)
        if isinstance(obj, TStruct) and e.field not in obj.fields:
            bag.error(f"{obj.name} has no field '{e.field}'", e.span)
```

Import `TStruct` into typecheck if not already (done in S2).

resolve (`cardlang/resolve.py`, `_validate_refs`) — flag construction of an
unknown type:

```python
            case n.StructLit() if nd.type_name not in defined_types:
                bag.error(f"unknown type '{nd.type_name}'", nd.span)
```

- [ ] **Step 6: Add a runtime construction test (declared field read)**

```python
# append to tests/test_struct_runtime.py
import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game


def test_struct_value_field_is_readable_at_runtime() -> None:
    src = """
    type Contract = { level : Integer  suit : Suit }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state { deal : Contract = Contract { level: 7, suit: hearts }  top : Integer = 0 }
      phase play { top := deal.level }
      winner: highest top
    }
    """
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7
```

> `winner: highest top` and `top` indexed by nothing — adjust if the runtime needs
> a per-player score var. If a non-indexed winner target trips the driver, make
> `top[player] : Integer = 0` and assign `top[p]` inside a `for each player p`.
> Confirm against `tests/test_offer_execute.py`'s shape, which uses
> `coins[player]`.

- [ ] **Step 7: Run tests to verify GREEN**

Run: `python -m pytest tests/test_struct_runtime.py tests/test_typecheck_errors.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — parse, negatives, runtime read, corpus, mypy all green.

- [ ] **Step 8: Commit**

```bash
git add cardlang/grammar/cardlang.lark cardlang/ast/nodes.py cardlang/parse.py cardlang/ir.py cardlang/runtime/state.py cardlang/runtime/evaluate.py cardlang/typecheck.py cardlang/resolve.py tests/test_struct_runtime.py tests/test_typecheck_errors.py
git commit -m "$(printf 'typed-outcomes: struct literals — construction, field checks, runtime\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task S4: derived fields at runtime

**Files:**
- Modify: `cardlang/runtime/state.py` (`RuntimeState.__init__` ~line 98)
- Modify: `cardlang/runtime/driver.py` (~line 56)
- Modify: `cardlang/runtime/evaluate.py` (`Member` case ~line 30; `_member`)
- Test: extend `tests/test_struct_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_struct_runtime.py
def test_derived_field_is_computed_at_runtime() -> None:
    src = """
    type HandResult = {
      tricks_required : Integer
      tricks_actual   : Integer
    } derived {
      surplus = tricks_actual - tricks_required
    }
    game G {
      players: 2
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player> }
      state {
        result : HandResult = HandResult { tricks_required: 6, tricks_actual: 9 }
        gained[player] : Integer = 0
      }
      phase play { for each player p: gained[p] := result.surplus }
      winner: highest gained
    }
    """
    game = check_dsl(src, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 3 and result.scores[1] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest "tests/test_struct_runtime.py::test_derived_field_is_computed_at_runtime" -q`
Expected: FAIL — `_member` raises `KeyError`/AssertionError: `surplus` is not in the struct's declared `fields` dict.

- [ ] **Step 3: Add a type index and compute derived fields on access**

`cardlang/runtime/state.py`, in `RuntimeState.__init__` (after `routing_index`, ~line 110):

```python
        self.type_index: dict[str, n.TypeDef] = {}  # type name -> definition
        self.define_index: dict[str, n.DefineDef] = {}  # define name -> definition
```

> `define_index` is unused until V2 but added here to keep the runtime-state shape
> in one place; it stays an empty dict and harms nothing.

`cardlang/runtime/driver.py` (after line 58):

```python
    rs.type_index = {t.name: t for t in game.types}
    rs.define_index = {d.name: d for d in game.defines}
```

> `game.defines` does not exist until V1. If implementing S4 before V1, drop the
> `define_index` line and add it in V1.

`cardlang/runtime/evaluate.py` — derived access needs `ctx` (to evaluate the
derived expr) and the `type_index`. Change the `Member` evaluate case (line 30)
to call a ctx-aware helper:

```python
        case n.Member():
            return _member_eval(e, ctx)
```

Add the helper (replacing direct `_member` use for members):

```python
def _member_eval(e: n.Member, ctx: Ctx) -> Any:
    obj = evaluate(e.obj, ctx)
    if isinstance(obj, StructValue) and e.field not in obj.fields:
        tdef = ctx.rs.type_index[obj.type_name]
        derived = next(d for d in tdef.derived if d.name == e.field)
        dctx = ctx
        for k, v in obj.fields.items():
            dctx = dctx.with_local(k, v)
        return evaluate(derived.value, dctx)
    return _member(obj, e.field)
```

> The derived expr's field references were classified `"local"` by the scoped
> resolve pass in S1, so `_name` reads them from `ctx.locals` — which is exactly
> what `dctx` binds.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest tests/test_struct_runtime.py -q && python -m mypy && python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/state.py cardlang/runtime/driver.py cardlang/runtime/evaluate.py tests/test_struct_runtime.py
git commit -m "$(printf 'typed-outcomes: derived struct fields computed at runtime\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task V1: `define` + variant outcome set — parse, resolve, ir

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (replace the V1 stub `define_def`)
- Modify: `cardlang/ast/nodes.py` (`VariantCase`, `DefineDef`; `Game.defines`; `Node`)
- Modify: `cardlang/parse.py` (transformer; `start()`)
- Modify: `cardlang/resolve.py` (register define names)
- Modify: `cardlang/ir.py` (emit defines)
- Test: `tests/test_define_parse.py`

- [ ] **Step 1: Write the failing parse test**

```python
# tests/test_define_parse.py
from __future__ import annotations

from cardlang.parse import parse_text

SRC = """
define declare_trump -> { trump_declared(Suit) | bid_abandoned } {
  produce bid_abandoned
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  winner: highest score
}
"""


def test_define_parses_with_variant_set() -> None:
    game = parse_text(SRC, "g.cardlang")
    assert [d.name for d in game.defines] == ["declare_trump"]
    define = game.defines[0]
    assert [(c.tag, c.payload_types) for c in define.cases] == [
        ("trump_declared", ("Suit",)),
        ("bid_abandoned", ()),
    ]
    assert len(define.body) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_define_parse.py -q`
Expected: FAIL — `produce` is not a statement / `game.defines` absent (the V1 stub `define_def` matches no body).

- [ ] **Step 3: Add `define_def` to the grammar**

In `cardlang/grammar/cardlang.lark`, add `define_def` to `top_item` (it was
deliberately left out in S1 to avoid a dangling reference):

```
?top_item: game
         | rule_def
         | routing_def
         | move_type_def
         | type_def
         | define_def
```

Add the productions:

```
// A named param-light definition with a typed variant outcome. Its body runs
// with the enclosing context bound (the routing precedent) and `produce`s one
// variant. Consumed by a `produces:` block (see produces_stmt).
define_def: "define" NAME "->" variant_set "{" statement* "}"
variant_set: "{" variant_case ("|" variant_case)* "}"
variant_case: NAME ["(" NAME ("," NAME)* ")"]
```

Add `produce_stmt` to `?statement` (line 112) and its production near `offer`
(line 172):

```
?statement: movement
          | rotate_stmt
          | epistemic_op
          | each_simultaneous
          | for_each
          | repeat_until
          | if_stmt
          | instantiate
          | let_stmt
          | assign_stmt
          | offer
          | round_stmt
          | produce_stmt

produce_stmt: "produce" NAME ["(" expr ("," expr)* ")"]
```

> `produces_stmt` (the consumer) lands in Task V2; `produce_stmt` (the producer)
> lands now so a define body can be parsed.

- [ ] **Step 4: Add AST nodes**

`cardlang/ast/nodes.py`, near `MoveTypeDef` (~line 558):

```python
@dataclass(frozen=True, slots=True)
class VariantCase:
    """One case of a variant outcome: a tag with zero or more typed payloads."""

    tag: str
    payload_types: tuple[str, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class DefineDef:
    """`define NAME -> { case(T) | … } { <stmt>* }` — a param-light definition
    that produces one variant. Runs with the enclosing context bound."""

    name: str
    cases: tuple[VariantCase, ...]
    body: tuple[Stmt, ...]
    span: Span | None = None
```

Add `Produce` to the statement nodes (near `Offer`, ~line 348):

```python
@dataclass(frozen=True, slots=True)
class Produce:
    """`produce TAG[(expr, …)]` — terminal in a define body; sets the variant
    result and unwinds the body."""

    tag: str
    payloads: tuple[Expr, ...]
    span: Span | None = None
```

Add `Produce` to the `Stmt` union (line 375); add `defines` to `Game` (after
`types`):

```python
    types: tuple[TypeDef, ...] = ()
    defines: tuple[DefineDef, ...] = ()
    span: Span | None = None
```

Add `VariantCase | DefineDef | Produce` to `Node`.

- [ ] **Step 5: Add parse transformers + collect in `start()`**

`cardlang/parse.py`:

```python
    def variant_case(self, meta: Meta, c: list[object]) -> n.VariantCase:
        return n.VariantCase(
            tag=str(c[0]),
            payload_types=tuple(str(x) for x in c[1:]),
            span=self._span(meta),
        )

    def variant_set(self, meta: Meta, c: list[n.VariantCase]) -> tuple[n.VariantCase, ...]:
        return tuple(c)

    def define_def(self, meta: Meta, c: list[object]) -> n.DefineDef:
        name = str(c[0])
        cases = next(x for x in c if isinstance(x, tuple))
        body = tuple(_as_stmt(s) for s in c if isinstance(s, n.Stmt) or _is_stmt(s))
        return n.DefineDef(name=name, cases=cases, body=body, span=self._span(meta))

    def produce_stmt(self, meta: Meta, c: list[object]) -> n.Produce:
        return n.Produce(
            tag=str(c[0]),
            payloads=tuple(_as_expr(x) for x in c[1:]),
            span=self._span(meta),
        )
```

> `_as_stmt` already exists (used by `move_effect`). The `define_def` body
> collection must gather every statement child after the `variant_set` tuple and
> the name token. Implement it concretely as: `body = tuple(_as_stmt(s) for s in c
> if not isinstance(s, (str, tuple)) and not isinstance(s, Token))` — i.e. every
> child that is a lowered statement node. Verify against the parse test; adjust the
> filter if a `Token` leaks. (Do not invent `_is_stmt`; use the isinstance filter.)

Final `define_def` body line (use this, not the placeholder above):

```python
        body = tuple(
            _as_stmt(s)
            for s in c[1:]
            if not isinstance(s, (str, tuple, Token))
        )
```

Collect in `start()`:

```python
        types = tuple(x for x in c if isinstance(x, n.TypeDef))
        defines = tuple(x for x in c if isinstance(x, n.DefineDef))
        return replace(
            game,
            rules=rules,
            routings=routings,
            move_types=move_types,
            types=types,
            defines=defines,
        )
```

- [ ] **Step 6: Register define names in resolve; force ir/execute/infer arms for `Produce`**

`Produce` joining `Stmt` forces arms. In `cardlang/ir.py` `_stmt` (after `Round`,
~line 249):

```python
        case n.Produce():
            return {
                "kind": "produce",
                "tag": s.tag,
                "payloads": [_expr(p) for p in s.payloads],
            }
```

In `cardlang/runtime/execute.py` `execute` (after `Round`, ~line 58) — `produce`
raises the signal caught by the define runner (added in V2; the raise is real and
self-contained):

```python
        case n.Produce():
            raise _ProduceSignal(stmt.tag, [evaluate(p, ctx) for p in stmt.payloads])
```

Add `_ProduceSignal` to `cardlang/runtime/state.py` (near `IllegalMove`, ~line 20):

```python
class _ProduceSignal(Exception):
    """Carries a `produce`d variant (tag + payloads) up to the define runner."""

    def __init__(self, tag: str, payloads: list[Any]) -> None:
        super().__init__(f"produced {tag}")
        self.tag = tag
        self.payloads = payloads
```

Import `_ProduceSignal` and `evaluate` where needed in `execute.py` (evaluate is
already imported). Import `_ProduceSignal` from `cardlang.runtime.state`.

`Produce` is a `Stmt` but holds no checkable top-level expr beyond payloads; for
now typecheck ignores it (it is not in `_stmt_exprs` yet — added in V3). No `infer`
arm is needed (`Produce` is a `Stmt`, not an `Expr`).

resolve (`cardlang/resolve.py`): collect define names so a future `produces:`
consumer (V2) can validate against them, and add nothing else yet. In
`_validate_refs`, add the set near `defined_types`:

```python
    defined_defines = {d.name for d in game.defines}
```

(Used by V2's `Produces` validation. No `Produce`-specific resolve check: an
unknown `produce` tag is a typecheck concern, V3.)

- [ ] **Step 7: Emit defines in ir**

`cardlang/ir.py` `emit()` (after `types`):

```python
        "types": [_type_def(t) for t in game.types],
        "defines": [_define(d) for d in game.defines],
```

Add the emitter:

```python
def _define(d: n.DefineDef) -> IRDict:
    return {
        "kind": "define",
        "name": d.name,
        "cases": [
            {"kind": "variant_case", "tag": c.tag, "payload_types": list(c.payload_types)}
            for c in d.cases
        ],
        "body": [_stmt(s) for s in d.body],
    }
```

- [ ] **Step 8: Run tests to verify GREEN**

Run: `python -m pytest tests/test_define_parse.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — define parses; mypy clean (all forced arms present); corpus green.

- [ ] **Step 9: Commit**

```bash
git add cardlang/grammar/cardlang.lark cardlang/ast/nodes.py cardlang/parse.py cardlang/resolve.py cardlang/ir.py cardlang/runtime/state.py cardlang/runtime/execute.py tests/test_define_parse.py
git commit -m "$(printf 'typed-outcomes: define + variant-set + produce (parse, resolve, ir)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task V2: `produces:` consumer — parse, ir, runtime dispatch

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (`?statement`; `produces_stmt`)
- Modify: `cardlang/ast/nodes.py` (`ProduceArm`, `Produces`; `Stmt`; `Node`)
- Modify: `cardlang/parse.py` (transformers)
- Modify: `cardlang/resolve.py` (`_categories` arm binders; `_validate_refs` define name)
- Modify: `cardlang/ir.py` (`_stmt`)
- Modify: `cardlang/runtime/execute.py` (`Produces` dispatch)
- Test: `tests/test_variant_runtime.py`

- [ ] **Step 1: Write the failing runtime test (deterministic chooser)**

```python
# tests/test_variant_runtime.py
from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# A define whose body deterministically produces one variant; the produces:
# consumer dispatches to the matching arm and binds the payload.
SRC = """
define settle -> { won(Integer) | lost } {
  produce won(7)
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""


def test_produces_dispatches_to_the_produced_arm_and_binds_payload() -> None:
    game = check_dsl(SRC, "g.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores[0] == 7 and result.scores[1] == 7
```

> The `produce won(7)` is unconditional, so the result is deterministic without a
> scripted chooser. The binder `amount` must thread the payload `7` into the arm.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_variant_runtime.py -q`
Expected: FAIL — `produces:` is not a statement (parse error).

- [ ] **Step 3: Add grammar**

In `cardlang/grammar/cardlang.lark`, add `produces_stmt` to `?statement` (after
`produce_stmt`) and the productions:

```
          | produce_stmt
          | produces_stmt

// Invoke a param-light `define` by name and dispatch on its variant result.
// Arm bodies use braces, matching if_stmt/repeat_until.
produces_stmt: NAME "produces" ":" produce_arm+
produce_arm: NAME ["(" NAME ("," NAME)* ")"] "{" statement* "}"
```

- [ ] **Step 4: Add AST + parse**

AST (`cardlang/ast/nodes.py`), near `Produce`:

```python
@dataclass(frozen=True, slots=True)
class ProduceArm:
    """One arm of a `produces:` block: a tag, payload binders, and a body."""

    tag: str
    binders: tuple[str, ...]
    body: tuple[Stmt, ...]
    span: Span | None = None


@dataclass(frozen=True, slots=True)
class Produces:
    """`NAME produces: <arm>+` — invoke a define and match its variant result."""

    define: str
    arms: tuple[ProduceArm, ...]
    span: Span | None = None
```

Add `Produces` to `Stmt`; add `ProduceArm | Produces` to `Node`.

Parse (`cardlang/parse.py`):

```python
    def produce_arm(self, meta: Meta, c: list[object]) -> n.ProduceArm:
        tag = str(c[0])
        binders = tuple(str(x) for x in c[1:] if isinstance(x, (str, Token)))
        body = tuple(_as_stmt(s) for s in c[1:] if not isinstance(s, (str, Token)))
        return n.ProduceArm(tag=tag, binders=binders, body=body, span=self._span(meta))

    def produces_stmt(self, meta: Meta, c: list[object]) -> n.Produces:
        return n.Produces(
            define=str(c[0]),
            arms=tuple(x for x in c[1:] if isinstance(x, n.ProduceArm)),
            span=self._span(meta),
        )
```

> The `produce_arm` children are: NAME(tag), then 0+ NAME binder tokens, then 0+
> lowered statements. Binders are `Token`/`str`; statements are dataclass nodes.
> The isinstance split above separates them. Verify against the V2 test; if a
> binder `Token` is mis-bucketed, tighten by checking `isinstance(s, Token)` for
> binders and `not isinstance(s, Token)` for body.

- [ ] **Step 5: Add resolve (arm binders as locals; validate define name)**

`cardlang/resolve.py` `_categories` (line 197), add a case so arm-body references
to binders resolve:

```python
            case n.ProduceArm():
                locals_.update(nd.binders)
```

`_validate_refs` — validate the consumed define exists (using `defined_defines`
from V1):

```python
            case n.Produces() if nd.define not in defined_defines:
                bag.error(f"produces names unknown define '{nd.define}'", nd.span)
```

- [ ] **Step 6: Add ir + runtime dispatch (forced by the Stmt union)**

ir (`cardlang/ir.py` `_stmt`, after `Produce`):

```python
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
```

execute (`cardlang/runtime/execute.py` `execute`, after `Produce`):

```python
        case n.Produces():
            _produces(stmt, ctx)
            return ctx
```

Add the runner (near `_offer`, ~line 207). No frame is pushed (the routing
precedent); `let`-locals inside the body thread via the immutable `Ctx`, and the
`_ProduceSignal` unwind leaves no state to clean up:

```python
def _produces(stmt: n.Produces, ctx: Ctx) -> None:
    define = ctx.rs.define_index[stmt.define]
    try:
        run_body(define.body, ctx)
    except _ProduceSignal as produced:
        arm = next(a for a in stmt.arms if a.tag == produced.tag)
        arm_ctx = ctx
        for binder, value in zip(arm.binders, produced.payloads):
            arm_ctx = arm_ctx.with_local(binder, value)
        run_body(arm.body, arm_ctx)
        return
    raise AssertionError(f"define '{stmt.define}' completed without producing")
```

Import `_ProduceSignal` in `execute.py` from `cardlang.runtime.state`.

- [ ] **Step 7: Run test to verify GREEN**

Run: `python -m pytest tests/test_variant_runtime.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — the produced arm runs and binds `amount=7`; mypy + corpus green.

- [ ] **Step 8: Commit**

```bash
git add cardlang/grammar/cardlang.lark cardlang/ast/nodes.py cardlang/parse.py cardlang/resolve.py cardlang/ir.py cardlang/runtime/execute.py tests/test_variant_runtime.py
git commit -m "$(printf 'typed-outcomes: produces: consumer — runtime dispatch + payload binding\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task V3: variant typechecking — exhaustiveness, payload + binder typing

**Files:**
- Modify: `cardlang/typecheck.py` (`_all_statements` ~line 263; `_stmt_tree` ~line 236; `_stmt_exprs` ~line 361; the main `typecheck()` loop ~line 433; add `_check_define_outcomes`, `_check_produces`, factor `_check_stmt_semantics`)
- Test: extend `tests/test_typecheck_errors.py`; `tests/test_variant_typing.py`

- [ ] **Step 1: Write the failing negative tests (assert on content)**

```python
# tests/test_variant_typing.py
from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _wrap(define_and_consumer: str) -> str:
    return f"""
{define_and_consumer}
game G {{
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ points[player] : Integer = 0 }}
  phase play {{ for each player p: CONSUMER }}
  winner: highest points
}}
"""


def test_accepts_exhaustive_typed_outcome() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce won(7) }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    check_dsl(src, "g.cardlang")  # no raise


def test_rejects_non_exhaustive_match() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce lost }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "exhaustive" in str(ei.value) or "lost" in str(ei.value)


def test_rejects_unknown_variant_in_match() -> None:
    src = """
define settle -> { won(Integer) | lost } { produce lost }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
        drew        { points[p] += 1 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "drew" in str(ei.value) or "unknown variant" in str(ei.value)


def test_rejects_wrong_payload_type_in_produce() -> None:
    # `produce won(hearts)` — a Suit where the case declares Integer.
    src = """
define settle -> { won(Integer) | lost } { produce won(hearts) }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      settle produces:
        won(amount) { points[p] += amount }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "won" in str(ei.value) or "Integer" in str(ei.value)


def test_rejects_wrong_binder_type_use() -> None:
    # `amount` binds an Integer; comparing it to a Suit is a type error — proves
    # the binder is typed (not TAny) inside the arm body.
    src = """
define settle -> { won(Integer) | lost } { produce won(7) }
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0  picked : Suit = hearts }
  phase play {
    for each player p:
      settle produces:
        won(amount) { if amount == hearts { points[p] += 1 } }
        lost        { points[p] += 0 }
  }
  winner: highest points
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "amount" in str(ei.value) or "Integer" in str(ei.value) or "Suit" in str(ei.value)
```

> `test_rejects_wrong_binder_type_use` depends on BinOp operand checking, which is
> a deferred Stage-1 fold-in. If `amount == hearts` is not yet rejected, this test
> proves binder typing only once that check exists. Either (a) implement the
> minimal BinOp `==` operand check in this task (compare `infer(left)`/`infer(right)`
> with `unify`, error if `None`), or (b) rewrite this test to use a context that is
> already checked — e.g. pass the binder to a stdlib function expecting a Card:
> `won(amount) { picked := player_holding(amount) }` where `player_holding` wants a
> Card, so an Integer binder errors via the existing stdlib-arg check. Option (b)
> needs no new checker feature — prefer it. Concretely:
>
> ```
> won(amount) { dealer := player_holding(amount) }
> ```
> with `dealer : Player = 0` in state and asserting `"player_holding" in str(ei.value)`.
> This fires through the existing `_check_expr` Call path *because* `amount` is
> typed `Integer` (not `TAny`) in the arm env — which is exactly what we are
> validating.

Use option (b). Rewrite `test_rejects_wrong_binder_type_use` accordingly before
running.

- [ ] **Step 2: Run tests to verify they fail (for the right reason)**

Run: `python -m pytest tests/test_variant_typing.py -q`
Expected: FAIL — the negatives raise nothing (no variant checks yet). Confirm
`test_accepts_exhaustive_typed_outcome` currently *passes* (permissive), and each
negative currently does NOT raise (proving the check is missing, not mis-firing).

- [ ] **Step 3: Build the TVariant registry and check define outcomes**

In `cardlang/typecheck.py`, import `TVariant` (line 30). Add a registry builder
near `struct_registry`:

```python
def variant_registry(
    game: Game, structs: Mapping[str, "TStruct"]
) -> dict[str, "TVariant"]:
    variants: dict[str, TVariant] = {}
    for d in game.defines:
        cases = {
            c.tag: tuple(type_from_name(t, False, structs) for t in c.payload_types)
            for c in d.cases
        }
        variants[d.name] = TVariant(name=d.name, cases=cases)
    return variants
```

Add `_check_define_outcomes` (checks every `produce` against the define's cases):

```python
def _check_define_outcomes(
    define: n.DefineDef, variant: "TVariant", env: TypeEnv, bag: DiagnosticBag
) -> None:
    for stmt in define.body:
        for sub in _stmt_tree(stmt):
            if not isinstance(sub, n.Produce):
                continue
            if sub.tag not in variant.cases:
                bag.error(
                    f"define '{define.name}' produces unknown variant '{sub.tag}'",
                    sub.span,
                )
                continue
            payload_types = variant.cases[sub.tag]
            if len(sub.payloads) != len(payload_types):
                bag.error(
                    f"variant '{sub.tag}' takes {len(payload_types)} payload(s), "
                    f"got {len(sub.payloads)}",
                    sub.span,
                )
                continue
            for expr, expected in zip(sub.payloads, payload_types):
                got = infer(expr, env)
                if not assignable(got, expected):
                    bag.error(
                        f"variant '{sub.tag}' expects {_type_name(expected)}, "
                        f"got {_type_name(got)}",
                        sub.span,
                    )
```

- [ ] **Step 4: Add the scoped `produces:` consumer check**

First factor the per-statement semantic checks out of `typecheck()` so the scoped
walk can reuse them. Extract from the main loop (lines 436-441) into a helper:

```python
def _check_stmt_semantics(stmt: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """The non-expression checks a statement carries: assignment compatibility
    and Boolean conditions. Used by the flat walk and the scoped produces walk."""
    if isinstance(stmt, n.AssignStmt):
        _check_assign(stmt, env, bag)
    elif isinstance(stmt, n.IfStmt):
        _check_bool(stmt.cond, env, bag, "if condition")
    elif isinstance(stmt, n.RepeatUntil):
        _check_bool(stmt.cond, env, bag, "repeat-until condition")
```

Add `_check_produces` (exhaustiveness + arity + scoped binder-typed arm walk):

```python
def _check_produces(
    stmt: n.Produces, variant: "TVariant", env: TypeEnv, bag: DiagnosticBag
) -> None:
    seen: set[str] = set()
    for arm in stmt.arms:
        if arm.tag not in variant.cases:
            bag.error(
                f"produces names unknown variant '{arm.tag}' "
                f"of '{stmt.define}'",
                arm.span,
            )
            continue
        if arm.tag in seen:
            bag.error(f"duplicate arm '{arm.tag}' in produces", arm.span)
        seen.add(arm.tag)
        payload_types = variant.cases[arm.tag]
        if len(arm.binders) != len(payload_types):
            bag.error(
                f"arm '{arm.tag}' binds {len(arm.binders)} value(s), "
                f"expected {len(payload_types)}",
                arm.span,
            )
        arm_env = env
        for binder, t in zip(arm.binders, payload_types):
            arm_env = arm_env.with_local(binder, t)
        for body_stmt in arm.body:
            for sub in _stmt_tree(body_stmt):
                for expr in _stmt_exprs(sub):
                    _check_expr(expr, arm_env, bag)
                _check_stmt_semantics(sub, arm_env, bag)
    missing = sorted(set(variant.cases) - seen)
    if missing:
        bag.error(
            f"produces on '{stmt.define}' is not exhaustive: missing "
            f"{', '.join(missing)}",
            stmt.span,
        )
```

- [ ] **Step 5: Wire define bodies into the walk; dispatch the new checks**

Extend `_stmt_exprs` (line 361) to surface `Produce` payloads (so they are
generically checked too) — add before the final `return []`:

```python
    if isinstance(s, n.Produce):
        return list(s.payloads)
```

Extend `_all_statements` (line 263) to visit define bodies (critical — produce
statements live here):

```python
def _all_statements(game: Game) -> Iterator[n.Stmt]:
    for routing in game.routings:
        for s in routing.body:
            yield from _stmt_tree(s)
    for move_type in game.move_types:
        for s in move_type.effect:
            yield from _stmt_tree(s)
    for define in game.defines:
        for s in define.body:
            yield from _stmt_tree(s)
    for phase in game.phases:
        yield from _phase_statements(phase)
```

> `_stmt_tree` treats `Produces` as a leaf (it is not in the recursion cases), so
> the flat walk does NOT descend into arm bodies — `_check_produces` owns them with
> the binder-extended env. This is the whole point: arm bodies must be checked with
> the scoped env, never the flat one.

In `typecheck()` (line 433), build the registries once and dispatch. Replace the
main loop body and add the define/consumer passes:

```python
    env = env_from_game(game)
    variants = variant_registry(game, env.structs)
    for stmt in _all_statements(game):
        for expr in _stmt_exprs(stmt):
            _check_expr(expr, env, bag)
        if isinstance(stmt, n.Produces):
            variant = variants.get(stmt.define)
            if variant is not None:
                _check_produces(stmt, variant, env, bag)
        else:
            _check_stmt_semantics(stmt, env, bag)
    for define in game.defines:
        variant = variants.get(define.name)
        if variant is not None:
            _check_define_outcomes(define, variant, env, bag)
```

> Note: `_check_stmt_semantics` replaces the inline `AssignStmt`/`IfStmt`/
> `RepeatUntil` checks. `Produces` is handled by `_check_produces` instead (its arm
> bodies are not double-checked by the flat walk, per the `_stmt_tree` leaf
> behavior).

- [ ] **Step 6: Run tests to verify GREEN**

Run: `python -m pytest tests/test_variant_typing.py tests/test_variant_runtime.py -q && python -m mypy && python -m pytest -q`
Expected: PASS — all five variant-typing cases behave; runtime still runs; corpus
+ mypy green. Re-confirm each negative now raises with the asserted substring.

- [ ] **Step 7: Commit**

```bash
git add cardlang/typecheck.py tests/test_variant_typing.py
git commit -m "$(printf 'typed-outcomes: variant typechecking — exhaustiveness + payload + binder typing\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task I1: end-to-end fixture, doc updates, full green

**Files:**
- Test: `tests/test_typed_outcomes_fixture.py`
- Modify: `docs/decisions.md` ("Typed phase outcomes" consumer arm examples → braced)
- Modify: `docs/roadmap.md` (Stage 2 done; deferred items)

- [ ] **Step 1: Write the integration fixture test (struct payload through a variant, end to end)**

```python
# tests/test_typed_outcomes_fixture.py
from __future__ import annotations

import random

from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

# Both halves together: a define produces a struct-carrying variant; the
# consumer matches exhaustively and reads a field (declared + derived) off the
# bound struct payload.
SRC = """
type Contract = {
  level : Integer
  made  : Integer
} derived {
  surplus = made - level
}
define resolve_hand -> { contract_made(Contract) | passed_out } {
  produce contract_made(Contract { level: 4, made: 6 })
}
game G {
  players: 2
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { points[player] : Integer = 0 }
  phase play {
    for each player p:
      resolve_hand produces:
        contract_made(c) { points[p] += c.surplus }
        passed_out       { points[p] += 0 }
  }
  winner: highest points
}
"""


def test_struct_carrying_variant_runs_end_to_end() -> None:
    game = check_dsl(SRC, "g.cardlang")  # parse + resolve + typecheck all clean
    result = play_game(game, random.Random(0))
    # surplus = made(6) - level(4) = 2, for each player.
    assert result.scores[0] == 2 and result.scores[1] == 2
```

- [ ] **Step 2: Run the fixture to verify it passes**

Run: `python -m pytest tests/test_typed_outcomes_fixture.py -q`
Expected: PASS — the struct payload binds as `c`, its derived `surplus` computes
to 2, the matched arm runs. If it fails, debug the specific layer (typecheck vs
runtime) before proceeding — this is the acceptance test for the whole stage.

- [ ] **Step 3: Update decisions.md consumer examples to braced arms**

In `docs/decisions.md` "Typed phase outcomes" (lines ~24-30 and ~55-63), rewrite
the colon-body arm examples to the braced form the grammar ships, so the doc
depicts the real consumer (shared with Stage 3). Change, e.g.:

```
declare_trump produces:
  trump_declared(t) { trump := t }
  bid_abandoned     { score[high_bidder.team] -= current_bid; skip to next hand }
```

and:

```
bidding produces:
  taker_chosen(_, level) {
    if level == Petite or level == Garde { continue to chien_visible }
    else { continue to play }
  }
  all_pass { skip to next hand }
```

Keep the surrounding prose intact; only the arm syntax changes (spec-not-history:
this is what the language *is* now). Do not add Stage-2-specific narration to this
Stage-3 section beyond the syntax.

- [ ] **Step 4: Update roadmap.md**

In `docs/roadmap.md`, in the "Typed outcomes (Stages 2-3)" bullet (lines ~62-77),
mark Stage 2 done and record what remains/was deferred:

- Stage 2 built: user-defined `type` structs (`TStruct`: fields, `derived`,
  field-access typing) and param-light `define` variant outcomes (`TVariant`:
  `produce`/`produces:`, exhaustiveness + payload + binder typing), end to end.
- Stage 3 remains: phase `→ outcome { … }` + `produces:` on phases (reuses the
  Stage-2 consumer and `TVariant`).
- Newly deferred (add): union-typed and refinement-typed struct fields
  (`suit : Suit | NT`, `Integer in 1..7`); param-full `define` (parameters +
  invocation-as-expression) until the challenge/block/auction stdlib reaches three
  corpus instances; forward references between struct types resolve to `TAny`.

- [ ] **Step 5: Full green + mypy**

Run: `python -m mypy && python -m pytest -q`
Expected: PASS — mypy clean; the full suite (149 prior + ~15 new) green; all 13
corpus games still typecheck and replay unchanged.

- [ ] **Step 6: Commit**

```bash
git add tests/test_typed_outcomes_fixture.py docs/decisions.md docs/roadmap.md
git commit -m "$(printf 'typed-outcomes: Stage 2 fixture + doc updates (braced arms, roadmap)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

- [ ] **Step 7: Open the PR**

```bash
git push -u origin stage2-variant-outcomes
gh pr create --base main --title "Typed outcomes Stage 2 — variant outcomes + user-defined types" --body "$(cat <<'EOF'
Stage 2 of typed outcomes: builds the `TStruct` and `TVariant` seams out.

- User-defined `type` structs: fields, `derived` fields, field-access typing,
  construction, runtime values (declared + computed fields).
- Param-light `define` variant outcomes: `produce` / `produces:` with
  exhaustiveness, payload typing, and scoped payload-binder typing — running
  end to end through the tree-walking runtime.

Validated by a fixture (struct payload through a variant, end to end) and
negative tests (non-exhaustive match, unknown variant, wrong payload type,
binder-type misuse, struct missing/wrong field). The 13-game corpus stays
typecheck-clean and replay-green, untouched.

Spec: docs/superpowers/specs/2026-06-08-typed-outcomes-stage2-design.md
Plan: docs/superpowers/plans/2026-06-08-typed-outcomes-stage2.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review (completed)

- **Spec coverage:** TStruct decl (S1) + typing (S2) + literal (S3) + derived
  runtime (S4); TVariant define/variants (V1) + produces consumer (V2) + typing
  (V3); end-to-end fixture + docs (I1). Every spec section maps to a task.
- **Validation gaps closed:** `_all_statements` visits `game.defines` (V3 step 5);
  payload-binder typing uses a scoped sub-walk (`_check_produces`, V3 step 4);
  every negative asserts a substring and is watched failing for the right reason
  (V3 step 2; S3 negatives); nested exprs surfaced (`_child_exprs` StructLit S3,
  `_stmt_exprs` Produce V3); arm-binder arity checked (V3 step 4); runtime test is
  deterministic via unconditional `produce` (V2).
- **Type consistency:** node names (`TypeDef`, `DefineDef`, `Produce`, `Produces`,
  `ProduceArm`, `StructLit`, `FieldInit`, `VariantCase`, `StructField`,
  `DerivedField`), `Game.types`/`Game.defines`, `RuntimeState.type_index`/
  `define_index`, `StructValue`, `_ProduceSignal`, `TypeEnv.structs`,
  `type_from_name(name, optional, structs)` are used identically across tasks.
- **Forced-arm discipline:** each Stmt/Expr node introduction (S3 StructLit, V1
  Produce, V2 Produces) adds its `ir`/`execute`/`evaluate`/`infer` arms in the same
  task, keeping mypy's `assert_never` matches exhaustive.
```
