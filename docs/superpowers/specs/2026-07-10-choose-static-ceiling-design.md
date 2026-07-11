# Design: a static ceiling for integer `choose`, retiring `_MAX_CHOOSE`

## Problem

`choose integer in <lo> .. <hi>` is the DSL's numeric decision form (a bid). The
interpreter narrows correctly at runtime — `_choose` offers exactly
`range(lo, hi + 1)` from the live bound — but the OpenSpiel action space is
reconciled by one global magic constant, `_MAX_CHOOSE = 52`
(`cardlang/openspiel/encoding.py`): every game with any integer `choose`
reserves a fixed 53-id block (`0..52`), sized to "the deck," not to any declared
or checked per-`choose` bound. Nothing declares what `_MAX_CHOOSE` should be, or
checks that a game's bounds stay under it. A future game whose natural bound is
larger would silently violate the OpenSpiel contract (a legal action with no id),
and nothing at resolve time would catch it.

This is the `choose` half of the `move-parameter-domains` open question. The
settled goal: put a bounded-`Integer` `choose` domain on the same footing as
`Suit`/`Rank`/`Player`/`Card` — a declared, checked, closed contract the
OpenSpiel adapter reads directly — and retire `_MAX_CHOOSE` as a global magic
constant.

## Scope

**`choose`-only.** `_MAX_CHOOSE`, and `has_integers`, are set solely on
`n.Choose` nodes (`encoding.py`); a bounded-`Integer` *move-parameter* is
rejected in `resolve.py` (`_check_move_params`) before it ever reaches
`enumerate_domain`. The two share a title in the open-question doc but not a code
path. Ninety-Nine's `play_card(delta : Integer)` — the parameter data point — is
moreover a *signed* small-integer domain that does not fit the `_int_base +
value` id scheme at all (negatives have no id), so it is a genuinely different
design, and no corpus game exercises it. Per corpus-first, the bounded-`Integer`
*parameter* domain stays rejected; only the `choose` domain is settled here.

**Corpus sites (both re-pinned):**

- Spades (`docs/games/spades.cardlang:69`): `choose integer in 0 .. 13` — `hi`
  is a static literal.
- Oh Hell (`docs/games/oh-hell.cardlang:69`): `choose integer in 0 .. hand_size`
  — `hi` is a per-hand state var.

## The rule

Every integer `choose` must have a **statically known, non-negative upper
bound** (its ceiling), from which the OpenSpiel action space is sized:

- If `hi` is a static integer literal (Spades' `13`), that literal *is* the
  ceiling. **No syntax change; Spades is untouched.**
- If `hi` is any other expression (Oh Hell's `hand_size`), the author declares
  an explicit static ceiling with a new `up to <literal>` clause:

  ```
  bid[p] := choose integer in 0 .. hand_size up to 10
  ```

A `choose` whose ceiling cannot be determined statically (non-literal `hi` with
no `up to` clause) is a **resolve-time error** (surface totality: rejected
loudly, never parsed-and-ignored).

## Surface

### Grammar

```
choose_expr: "choose" "integer" "in" sum ".." sum ["up" "to" INT]  -> choose_integer
```

The `up to` operand is a bare `INT` token — a literal, not an expression — so
`up to hand_size` is a parse error by construction (a non-literal ceiling can
never satisfy the static contract, and the surrounding `sum`/expression forms
never begin with a bare INT in this position, so there is no ambiguity). A
friendly diagnostic for the *missing*-ceiling case is the resolver's job (below).

### AST

`n.Choose` gains one field:

```python
@dataclass(frozen=True, slots=True)
class Choose:
    domain: str          # "integer"
    lo: Expr
    hi: Expr
    ceiling: int | None  # explicit `up to N`; None => derive from a literal `hi`
    span: Span | None = None
```

`ceiling` holds the declared `up to N` when present, else `None`. The single
place that needs the *resolved* static ceiling — the action-space walk — reads
`ceiling` if set, otherwise requires `hi` to be an `IntLit` and reads its value.
A tiny shared helper, `static_ceiling(choose) -> int | None`, centralizes this
(returns `None` when neither source yields a static value; callers treat `None`
as "unbounded / error").

### Resolve

`resolve.py` gains a check over every `n.Choose`: `static_ceiling(...)` must be a
non-negative integer. Failure messages:

- non-literal `hi`, no `up to`: *"`choose integer` needs a statically known upper
  bound: either write a literal upper bound (`0 .. 13`) or declare a ceiling with
  `up to N` (`0 .. hand_size up to 10`)."*
- negative ceiling: *"`choose integer` ceiling must be non-negative."*

(The existing empty-range runtime error and "no implicit actions" contract are
preserved — an empty *live* range is still a runtime error, unchanged.)

### Runtime guard — on the range, not the drawn value

The only bound check today is in the adapter's `encode` (`encoding.py:254`),
which asserts the drawn *value* is in `0..52`. That is porous twice over: it
lives in the OpenSpiel adapter (so a plain tree-walking playout never hits it),
and even under a conformance walk it only fires for the *value the chooser
actually drew* — a game whose live `hi` exceeds its ceiling passes whenever the
draw happens to be small, while silently offering a legal action with no id.
`_choose` (`evaluate.py`) itself has no bound guard. Add one that guards the
**range** where `hi` is evaluated:

```python
lo = int(evaluate(e.lo, ctx)); hi = int(evaluate(e.hi, ctx))
ceiling = static_ceiling(e)          # resolve guaranteed this is a non-neg int
if lo < 0 or hi > ceiling:
    raise RuntimeError(...)          # the live range escaped its declared domain
```

This makes "every legal action in every state has an id" a checked invariant, not
a hope, and re-excludes signed domains (`lo >= 0`) at the same site.

### OpenSpiel encoding

`encoding.py`:

- Delete `_MAX_CHOOSE`.
- `ActionSpace.for_game`'s `_walk` already visits every `n.Choose`. Alongside
  setting `has_integers = True`, track `max_ceiling = max(max_ceiling,
  static_ceiling(node))` over all integer chooses.
- Size the shared integer block to `max_ceiling + 1` (was `_MAX_CHOOSE + 1`):
  `self._vocab_base = self._int_base + (max_ceiling + 1 if has_integers else 0)`.
  One shared block, indexed `_int_base + value`, exactly as today — **not**
  per-`choose` id ranges. (Two chooses in one game share the block; the corpus
  has at most one per game, and they never co-occur at a decision point.)
- `encode`'s integer branch asserts `0 <= value <= max_ceiling` (the per-game
  bound now carried on the instance), replacing the constant.

Consequence: Spades' integer block shrinks 53 → 14, Oh Hell's 53 → 11, shifting
`_vocab_base`/`_combo_base`/`num_distinct_actions` and every downstream id for
those two games. Their `openspiel_ready` / adapter goldens are re-pinned.

## Docs

- **Settle** the `choose` half into `docs/decisions.md` "Declared parameter
  domains": a bounded-`Integer` `choose` domain with a static, checked ceiling
  (literal `hi`, or `up to N`), masked at runtime, sized into the OpenSpiel
  action space. Note the still-deferred bounded-`Integer` *parameter* domain.
- **Narrow** `docs/open-questions/move-parameter-domains.md` to the remaining
  bounded-`Integer` *parameter* domain only (the signed/`delta` case), now
  blocked on a corpus game — so it moves Tier 1 → Tier 2 in
  `docs/open-questions/_index.md`. Keep the file (not deleted) so the
  `resolve.py` / `enumerate_domain` citations stay valid; rewrite its body to
  the parameter-only scope and drop the `_MAX_CHOOSE` framing (now resolved).
- Update `docs/games/oh-hell.cardlang` (add `up to 10`) and its `.md` companion.
  Spades needs no change.
- `docs/roadmap.md` "Suggested next steps" item 1 is done — fold its residual
  (the parameter domain) into the reworded open question rather than leaving a
  stale "ready now."

## Testing

- **Parser/AST:** `up to N` parses onto `Choose.ceiling`; a literal-`hi` choose
  leaves `ceiling=None`; `up to <non-int>` is a parse error.
- **Resolve:** a non-literal `hi` with no `up to` is rejected with the ceiling
  message; a negative ceiling is rejected; Spades (literal `hi`) and Oh Hell
  (`up to 10`) resolve clean.
- **Runtime guard:** a `choose` whose live `hi` exceeds its ceiling raises at the
  `_choose` site (construct a minimal game or drive `_choose` directly), even
  when the drawn value would have been small — the case today's value-assert
  misses.
- **Encoding:** `ActionSpace.for_game` sizes the integer block to
  `max_ceiling + 1`; assert Spades = 14 and Oh Hell = 11 integer ids and the
  shifted `num_distinct_actions`.
- **Corpus goldens:** re-pin the Spades and Oh Hell `openspiel_ready` / adapter
  goldens; full `pytest -q` green; `mypy` (bare) clean.

## Non-goals

- Bounded-`Integer` *move-parameter* domains (signed `delta`) — stays rejected.
- Refinement-typed state vars (`hand_size : Integer in 0..10`) — an explicitly
  deferred, larger surface that buys no extra static safety here (the runtime
  guard is needed regardless), so the inline literal ceiling is strictly smaller.
- Per-`choose` id sub-ranges — one shared integer block, as today.
