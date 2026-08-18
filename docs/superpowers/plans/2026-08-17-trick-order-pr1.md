# Plan: issue #250 PR 1 -- the `trick_order` construct, its grid, and Doppelkopf

Branch `ben/trick-order-250` (worktree `.claude/worktrees/pr1-trick-order`),
planned 2026-08-16 on main 8a722cd. Merge Lane A (grammar): the operator
merges; Hoyle's counsel and the Architect's counsel are attached (below).
This plan is written for an implementer who was not in the planning
context: every step names the artifact that proves it, and the grid IS the
work list.

Prerequisite: PR #365 (`ben/trump-slot-sweep-250`, PR 0 of the #250 plan)
merges to main first; then `git merge origin/main` into this branch. Section
14 names every line where PR 1 touches PR 0's code.

## 0. What is ruled, what is counsel, what is open

RULED (issue #250, the design proposal 5308899646; the operator rulings
5310363374 and 5310382133) -- not re-opened here: define-form block
`trick_order { trump: <Boolean> follow_class: <Suit?> card_strength:
<Integer> }` over the implicit `card` binder; readers `is_trump(card)` /
`follow_class(card)` / `card_strength(card)`; Builtins `highest_by_trick_order`
(round `winner` slot AND a call over an identity-to-all pile; mid-trick =
winner so far, #350 closes) and `follows_lead(card, pile)` (empty pile = the
value `false`); `follow_class` none = class-less; `card_strength` omitted
defaults to `rank_value(card)` (then `ranking:` required); block scope
game-level only; strict presence partition both directions at resolve; row
typing strict, `TAny` refused; rows may not read actor/action/winner or a
concealed zone; upward reader references refused; doctrine edits (decisions.md
paragraph rewritten in place, `ranking:` scope sentence repointed, `order`
reserved); five glossary entries; hand-rolled playout oracles observation-
derived; the harness derives its provenance half from the AST; Doppelkopf:
`doko.py` deleted whole, `doppelkopf_scores.json` byte-identical, 200-seed
old-vs-new stream diff before the module deletes.

COUNSEL (attached; both recommend, the operator rules):
- Hoyle -- https://github.com/jbgh2/card-game-dsl/issues/250#issuecomment-5311049181
- The Architect -- https://github.com/jbgh2/card-game-dsl/issues/250#issuecomment-5311270491

OPEN for the operator (the cut-level points both counsels raise; the plan
takes the joint recommendation as its default and the grid marks the cells
that flip if the ruling differs -- `tests/test_trick_order.py`, ledger
"provisional"). Each line: point -- default taken -- what flips otherwise.

1. Row production shape -- ONE arm `TRICK_ORDER_KEY ":" expr` with the
   builder validating the key against `TRICK_ORDER_ROWS` (Hoyle) -- vs three
   keyword arms + a bad-key terminal (states the row set twice; hides from
   the derived struct-literal absorber pin). Grid-neutral (P4 either way).
2. The `trump:` row REQUIRED, `trump: false` the no-trump spelling (both
   counsels) -- vs default `false` when omitted; flips the three P8 cells to
   accept.
3. Strict typing for `trump:` (exactly Boolean) and `card_strength:`
   (exactly Integer), coercion for `follow_class:` only, `TAny` refused
   (both) -- vs `_check_operand` coercion for all three; flips the
   `Boolean?` / `Integer?` cells to accept.
4. Rows may read NO pronoun of any namespace (`resolve._PRONOUNS`: actor,
   action, winner, state, active_rules), and make no `choose`, direct or
   through a helper (the Architect) -- vs the call-site three only; flips
   the `state`/`active_rules`/`choose` cells to accept.
5. The row-callable Builtin surface is an ALLOW-LIST registry with its
   complement listed (both) -- vs an AST zone-walk only; flips
   `player_holding` / `error` cells to accept.
6. The pile argument of every Arrival-Record call is a static zone
   reference of an identity-to-all type at RESOLVE, the runtime guards
   becoming Shadow Guards (both) -- vs runtime-only; flips the computed /
   concealed pile cells (incl. the EXISTING call form's) to accept.
7. Every `TrickRound`'s play zone projects identity to every observer, at
   resolve (both) -- vs the block winner's slot only; flips the
   `into-Deck` / `Muck` / `Burn` / `FaceDownPile` cells to accept.
8. `early <predicate>` refused beside `highest_by_trick_order` (both) -- vs
   accept; flips one cell.
9. The winner slot's calling shape: TWO contracts keyed by
   `TRICK_ORDER_GATED_WINNERS`, both dispatched by `value_function` (the
   Architect; Hoyle leaves the shape to Foster) -- vs a closure in
   `TrickForm` (fails `tests/test_signatures.py::test_outcome_names_are_dispatchable`
   and every member cell of PR #365's grid) or a fifth `ctx` argument on the
   uniform contract (hands a live Ctx to game-local winners, against the
   Primitive-narrowing contract). Grid: `test_winner_slot_has_two_contracts_keyed_by_registry`.
10. The `=`/`:=` reject arm reaches a MIXED block (one wrong row among colon
    rows) (Hoyle) -- vs all-`=` blocks only; the `eq-row-mixed` cell.
11. The `trick` trace at the call form: NEVER (the Architect; the brief's
    "keeps emitting" is counsel-noted against: a mid-trick winner-so-far read
    is designed surface and would trace false trick ends) -- the round
    form's `outcome` keeps its trace; the oracles are observation-derived.
12. Doppelkopf's `follow_ok` REWRITTEN over `follows_lead` and `led_trump` /
    `led_suit` / `holds_trump` / the `is_trump` function retired (both; the
    brief's "call sites unchanged" is true of the NAME -- the minted reader
    keeps Doppelkopf's spelling and arity -- and the sites retire because
    their only reader, the second led-class spelling, retires) -- vs keeping
    `follow_ok` and replacing the winner only (leaves two led-class
    definitions and ships `follows_lead` corpus-unexercised).

## 1. Acceptance criteria (planning Gate 3)

1. Runs: Doppelkopf plays under the block through `follows_lead` and
   `highest_by_trick_order`; the fixture games of the grid play both winner
   positions.
2. Regression-clean: bare `mypy`; full `pytest -q -n 8`; the rigs
   (`pytest experiments/llm_eval/tests -q`); every golden byte-identical
   (`tests/golden/doppelkopf_scores.json`; no IR golden moves -- there is
   none for Doppelkopf, and `french-tarot.ir.json` moved in PR 0); the
   200-seed stream pin green (`tests/test_trick_order_migration.py`).
3. Info sets derive: no new decision site, no new Observation Event; every
   fact the construct computes is a pure function of the card and public
   state (the hermeticity guards of section 5 are what make that a fact);
   the Doppelkopf proof module (`tests/openspiel_ready/test_doppelkopf.py`)
   stays NON-vacuous through the AST-derived provenance half (section 9);
   the information-state string moves by two retired public variables
   (`led_trump`, `led_suit`) -- the partition does not; say so in the PR body.
4. Completeness: the grid green with every xfail mark removed
   (`tests/test_trick_order.py`; bare run `TRICK_ORDER_GRID_BARE=1` shows 0
   failed), its ledger re-read before commit; the misuse probes are its
   rejection cells.

Corpus lockstep (operating rule 2): `docs/games/doppelkopf.cardlang` +
`docs/games/doppelkopf.md` only. The nine other trick-winner games are
byte-identical by the partition's without-block direction (pinned by the
corpus checks: tests/test_typecheck_corpus.py, the goldens).

Witness: Doppelkopf forces the call form and `follows_lead`; the round-form
slot has no corpus witness until PR 4 (Belote) -- the grid's round-form
fixture (`test_slot_and_call_agree`, `test_block_agrees_with_the_standard_winner`)
is the minimal witness the audit requires, executed.

Reachability: R2 (issue #250 -- a designer writing any big European trick
game meets it at the first computed trump set).

## 2. The grammar diff (`cardlang/grammar/cardlang.lark`)

```text
?game_item: uses_decl | players | direction | cards | pieces | board
          | ranking | card_points_table | trump | trick_order | teams
          | max_length | positions | zones | state_block | phase | winner | loser

// The game's Trick Order (decisions.md "Trick Order"): the three per-card
// facts a trick's resolution and follow legality derive from -- is the card
// a trump, what class does it follow as, how strong is it within its class
// -- each an expression over the implicit `card` binder (the card-query and
// filter convention). The language mints the readers `is_trump(card)`,
// `follow_class(card)`, `card_strength(card)` (the `card_points { }` /
// `card_points(card)` precedent) and two Builtins over the declaration:
// `highest_by_trick_order` (the winner: bare in a round's `winner` slot, or
// called over a public pile's Arrival Record) and `follows_lead(card, pile)`.
// Entry-plus (the empty block is a syntax error); the row key is its own
// terminal, validated by the builder against `TRICK_ORDER_ROWS` (one source
// for the row set; a wrong key gets a rejection naming the rows); each row
// at most once, in any order -- the reference order between rows is the
// language's (trump, follow_class, card_strength), never the textual one.
// Rows are whitespace-separated like every block clause. Reject-with-
// replacement twins (the `card_points_table` mechanism): the colon habit,
// comma-separated rows, and the `derived` / assignment habit `trump = ...` /
// `trump := ...` anywhere in the block.
trick_order: _TRICK_ORDER_KW "{" trick_order_row+ "}"
           | _TRICK_ORDER_KW ":" "{" trick_order_row* "}"                          -> trick_order_colon_reject
           | _TRICK_ORDER_KW "{" trick_order_row ("," trick_order_row)+ "}"        -> trick_order_comma_reject
           | _TRICK_ORDER_KW "{" trick_order_row* trick_order_eq_row (trick_order_row | trick_order_eq_row)* "}" -> trick_order_eq_reject
trick_order_row: TRICK_ORDER_KEY ":" expr
trick_order_eq_row: TRICK_ORDER_KEY TRICK_ORDER_EQ expr
TRICK_ORDER_EQ: ":=" | "="

// The game-level trump clause: the suit that beats all others in a trick,
// named bare (`trump: spades`) -- a suit of the declared deck (resolve,
// `_resolve_trump`), read by a trick round whose winner reads a trump and
// writes no `trump` clause of its own. Refused beside a `trick_order` block
// (the block's `trump:` row is then the trump). A number or string where the
// bare name belongs gets a builder rejection, not the lexer's voice.
trump: _TRUMP_KW ":" NAME
     | _TRUMP_KW ":" INT     -> trump_int_reject
     | _TRUMP_KW ":" STRING  -> trump_string_reject

_TRICK_ORDER_KW: "trick_order" /(?![A-Za-z0-9_])/
// The row-key terminal: NAME's own exclusions (parity with CARD_POINTS_KEY),
// no clause-keyword exclusions (the block is brace-bounded).
TRICK_ORDER_KEY: /(?!(?:always|all|one|some|jointly|not|is|number)\b)[a-zA-Z_][a-zA-Z0-9_]*/
```

Also:
- `trick_order` joins the exclusion lists of `CARD_RANK_NAME` (L709) and
  `STRUCT_TYPE_NAME` (L696); `tests/test_game_clause_guards.py` gains a
  `_CLAUSE_TEXT["trick_order"] = "trick_order { trump: card.suit is hearts }"`
  line, and its `_head_is_name_shaped` (L329) is widened so a `_X_KW` head
  whose word is not in NAME's exclusion counts as identifier-shaped, chasing
  every alternative of the entry production (Hoyle, section 1(i)) -- do this
  even under the single-terminal row shape.
- If the operator takes the three-keyword-arm shape instead: terminals
  `_FOLLOW_CLASS_KW`, `_CARD_STRENGTH_KW` (anchored), reuse `_TRUMP_KW`, and
  a `TRICK_ORDER_BAD_KEY` terminal excluding the three keys; then a derived
  pin reconciles the three arms + the exclusion against `TRICK_ORDER_ROWS`.
- `follow_class` / `card_strength` / `trick_order` are NOT added to NAME's
  exclusion (`trick_order` is a dead first parse after `trump:`, not a second
  parse; the readers are ordinary calls in expression position).
- No `?library_item` arm (pinned: `test_block_in_a_library_is_inexpressible`).
- The keyword-anchoring pin (`tests/test_keyword_anchoring.py`) derives the
  new terminals; run `python -m tests.keyword_fusion_sweep` after the edit.
- The ambiguity budget: every ACCEPTED boundary sentence of the grid
  (`boundary-*` cells) parsed with `ambiguity="explicit"` at zero `_ambig`
  -- add a parametrized pin in `tests/test_grammar_ambiguity.py` over the
  grid's accept sources (import `_grammar_cells` and filter `not needles`),
  or a sibling test in the grid module using `_explicit_parser()`.
- Rewrite the two stale comments on `trump:` (L153-154: "(or rank-set)",
  "the trump-aware outcome functions read") as above.

## 3. AST and parse

`cardlang/ast/nodes.py` (beside `CardPointsTable`, L792-815):

```python
TrickOrderRowKey = Literal["trump", "follow_class", "card_strength"]

@dataclass(frozen=True, slots=True)
class TrickOrderRow:
    key: TrickOrderRowKey
    body: Expr
    span: Span | None = None

@dataclass(frozen=True, slots=True)
class TrickOrder:
    rows: tuple[TrickOrderRow, ...]   # source order; each key at most once (parse)
    span: Span | None = None
    def row(self, key: TrickOrderRowKey) -> Expr | None: ...
```

`Game.trick_order: TrickOrder | None = None` (L1273-1330, beside
`card_points`). Both kinds join the `Node` union (L1343; `tests/test_node_registry.py`
pins it). `TrickOrderRow` is a BINDING node: `_node_binders` (resolve.py
L1977-2075) returns `("card",)` for it; `_BINDER_SCOPE_FIELDS[n.TrickOrderRow] =
("body",)` (L4152-4173); `TrickOrder` binds nothing (file it in the
non-binding arm). `tests/test_binder_registry.py` gets a `TrickOrderRow`
cell.

`cardlang/parse.py`: builder callbacks `trick_order_row` (validate the key
against `TRICK_ORDER_ROWS`, else P4), `trick_order` (rows; repeated key ->
P5; missing `trump:` row -> P8 if ruled required), the three reject
callbacks (P1, P2, P3), `trump_int_reject` / `trump_string_reject` (P7);
`game()` (L1364-1445): `once("trick_order { }", item.span, merge_hint=True)`
(P6) and `trick_order=` on the Game.

## 4. Registries (`cardlang/builtins/functions.py`, `signatures.py`)

```python
# functions.py
BUILTIN_TRICK_WINNERS += {"highest_by_trick_order"}   # a Builtin in both positions
BUILTIN_CALL_FUNCS    += {"is_trump", "follow_class", "card_strength", "follows_lead", "highest_by_trick_order"}
DECK_ONLY_CALL_FUNCS  += the same five
TRICK_ORDER_ROWS: tuple[tuple[str, str], ...] = (("trump", "is_trump"), ("follow_class", "follow_class"), ("card_strength", "card_strength"))
TRICK_ORDER_READERS = tuple(r for _, r in TRICK_ORDER_ROWS)
TRICK_ORDER_GATED_WINNERS = frozenset({"highest_by_trick_order"})
TRICK_ORDER_GATED_FUNCS = frozenset({"highest_by_trick_order", "follows_lead"}) | frozenset(TRICK_ORDER_READERS)
TRICK_ORDER_EXCLUDED_WINNERS = TRICK_WINNER_NAMES - TRICK_ORDER_GATED_WINNERS      # by subtraction
TRICK_ORDER_EXCLUDED_FUNCS = (BUILTIN_TRICK_WINNERS & BUILTIN_CALL_FUNCS) - TRICK_ORDER_GATED_FUNCS   # = {highest_trump_or_led_suit}
TRICK_ORDER_ROW_CALLS = frozenset({"rank_value", "card_points", "suit_of", "strain_index", "team_of", "top_of", "bottom_of"})
TRICK_ORDER_ROW_UNCALLABLE = frozenset({"player_holding", "error", "lines", "neighbor", "has_step", "is_diagonal", "home", "far_row", "highest_trump_or_led_suit", "highest_by_trick_order", "follows_lead"})
#   pinned: ROW_CALLS | ROW_UNCALLABLE | READERS == BUILTIN_CALL_FUNCS, disjoint; every PRIMITIVE_CALL_FUNCS member uncallable by construction
ARRIVAL_RECORD_CALLS: Mapping[str, int] = {"highest_by_trick_order": 0, "follows_lead": 1, "highest_trump_or_led_suit": 0}   # name -> pile-argument index; every member in BUILTIN_CALL_FUNCS with CALL_SIGS[name].params[idx] == TAny()
TRICK_ORDER_EARLY_PREDICATES: frozenset[str] = frozenset()   # refusal of `early` derived by subtraction from PRIMITIVE_EARLY_PREDICATES
```
The header comment (L24) states TWO winner contracts by registry (section 7).
`TRUMP_READING_WINNERS` (PR 0) does NOT gain the new winner (its trump is
the block's row, not the round's argument). `RANKING_GATED_*` (typecheck.py
L184-199) do NOT grow: they are unconditional `rank_index` readers; the block
winner and `card_strength` read it only under the omitted-row default, which
T2 gates at the block; extend the census comment (L160-183) with the five as
NON-members and why.

```python
# signatures.py CALL_SIGS
"is_trump": Sig((TCard(),), TBoolean()),
"follow_class": Sig((TCard(),), TOptional(TEnum("Suit"))),
"card_strength": Sig((TCard(),), TInteger()),
"follows_lead": Sig((TCard(), TAny()), TBoolean()),          # the pile polymorphic like the #256 call form
"highest_by_trick_order": Sig((TAny(),), TPlayer()),
# VALUE_SIGS
"highest_by_trick_order": TAny(),
```
A row's required body type is `CALL_SIGS[reader].ret` -- one source.
Pins that trip: `tests/test_signatures.py` (tables reconcile; outcome names
dispatchable), `tests/test_native_dispatch_split.py` (an arm per Builtin),
`tests/test_piece_content_guards.py` (flavor partition), `tests/test_native_call_boundary.py`
(the `TAny` params of `follows_lead` / `highest_by_trick_order` with a
"still sees the zone" probe like L202-222), and the grid's registry cells.

## 5. Resolve (`cardlang/resolve.py`)

Order in `resolve()` (L1870-1900): after `_resolve_card_points`, add
`_check_trick_order_partition(game, bag)`; the row checks run after
`_check_functions` (they reuse its call map and `_reaches`).

- `_check_trick_order_partition(game, cats, bag)` -- Owner Guard for the
  presence partition. WITH a block: game `trump:` (R1; render the
  `card.suit is X` remedy only when X is in `suit_names(deck)`); every
  `TrickRound.trump is not None` (R2); every round whose `winner_fn` is in
  `TRICK_ORDER_EXCLUDED_WINNERS` (R3); every `Call` in
  `TRICK_ORDER_EXCLUDED_FUNCS` (R4); every round with `early_termination` not
  in `TRICK_ORDER_EARLY_PREDICATES` and a gated winner (R4E); a block with
  no consumer OUTSIDE its rows -- no round naming a gated winner, no Call to
  a gated func outside the block (R7). WITHOUT a block: a round naming a
  gated winner (R5); a Call to a gated func (R6, with the reader's row named).
- PR #365's `_resolve_trump` returns early when `game.trick_order is not
  None` (R1 owns that cell); its winner-slot `trump` arm in `_validate_refs`
  skips gated winners AND block games (R2/R5 own those; grid:
  `with-block-round-trump`, `without-block-slot-with-trump` forbid "reads no
  trump").
- `_check_trick_order_rows(game, bag)` -- Owner Guards over each row's body
  and every designer function reachable from it (the call graph of
  `_check_functions`, L4352-4355 + `_reaches`): any `_PRONOUNS` member (R9;
  for actor/action/winner through a function the existing `_check_functions`
  guard already fires -- keep it, the row guard names the row and the
  function for the other two); a `Choose` (R9c); a zone read whose declared
  type is not `identity_to_all` (R10; count reads included, residual (3));
  a bare per-player family read (R11); a Call outside
  `TRICK_ORDER_ROW_CALLS | readers | designer functions` (R13); a Call to a
  reader of a row at or after this row in the language's order (R8_UP /
  R8_SELF), or to a consumer (R8_CONSUMER); the two Arrival-Record calls
  refused in rows by R8_CONSUMER (they are also in ROW_UNCALLABLE). Every
  message renders "through function `f`" when indirect.
- `_check_arrival_record_pile_args(game, cats, bag)` -- for every `Call` in
  `ARRIVAL_RECORD_CALLS`, the argument at the registry's index must be a
  `NameRef` classified `zone` or a `Subscript` over a zone family (R14), of
  a type with `identity_to_all` (R14_ID). Owner Guard; the runtime's zone-
  shape and identity checks become Shadow Guards naming this function.
- `_validate_refs` TrickRound arm (L5567-5598): the play zone's declared type
  must be `identity_to_all` (R15) -- every trick round, corpus unchanged
  (9 of 9 rounds play into a `TrickPile`).
- `_reject_card_content_clauses` (L3886-3912): a `trick_order` block in a
  piece game (R12).
- `_check_functions` (L4357-4363): the shadowing message for a designer
  function named after a reader appends the block hint (SHADOW_HINT).
- The `card_points` clause-required arm (L5131-5143) is the shape for R6.
- Contract block (L21-58) gains: Establishes -- a `trick_order` block is
  well-formed against `TRICK_ORDER_ROWS`, every row hermetic (no pronoun of
  any namespace, no `choose`, only identity-to-all subscripted zones, only
  `TRICK_ORDER_ROW_CALLS`/earlier readers/designer functions), the presence
  partition holds both ways and the block has a consumer, no `early` beside
  the block winner, every Arrival-Record pile argument is a static
  identity-to-all zone reference, every trick round's play zone is
  identity-to-all. Illegal after: a gated reader/winner reaching typecheck
  or the runtime without a block; an excluded winner/call with one; a row
  that could answer differently for two askers; a computed or concealed
  pile under an Arrival-Record read; a trick round some observer cannot see.

## 6. Typecheck (`cardlang/typecheck.py`)

`_check_trick_order(game, env, bag)` called from `typecheck()` (L3420+,
beside the `loser:` check ~L3507): for each row, `infer(body, _scoped_env(env,
(("card", TCard()),)))`; required type = `CALL_SIGS[reader].ret`; if the
required type is a `TOptional`, route through `_check_operand` (coercion:
`Suit`, `none` satisfy `Suit?`), else EXACT equality; `TAny` refused in both
arms (T1a); T1's three sentences with the `Suit` hint for `trump:` and the
`String` hint for `follow_class:`; T2 when the block has no `card_strength:`
row and `not env.has_ranking`. Rows are inside the generic expression walk
(`_check_expr`) so an unknown card field in a row is the existing
diagnostic -- pin it. The `RANKING_GATED` gate messages (L2104-2106,
L2244-2247) reword their remedy: "-- declare one, or declare a
`trick_order { }` with a `card_strength:` row and name
`highest_by_trick_order`" (grid: `*-names-the-block` cells). Contract
block: Establishes -- each row types exactly its reader's return type,
`TAny` refused; the default-strength ranking demand at the block. Illegal
after: an optional-typed `trump:`/`card_strength:` or a top-typed row
reaching the runtime; a default-strength block with no `ranking:`.

## 7. Runtime

`cardlang/runtime/winners.py` (pure, evaluate-free): 
```python
@dataclass(frozen=True) class Arrival: actor: Player; card: Card; is_trump: bool; follow_class: str | None
def effective_lead(arrivals) -> Arrival | None            # first arrival that is a trump or has a class
def follows_lead(is_trump: bool, follow_class: str | None, arrivals) -> bool   # False with no Effective Lead; trumps if the lead is a trump, else same class and not a trump
def highest_by_trick_order(arrivals, strength_of: Callable[[Card], int], caller: str) -> Player
    # candidates = trumps if any else the Effective Lead's class (non-trump, same class);
    # strength read for CANDIDATES ONLY (PR 5's unranked Excuse); strict `>` in play order (First of Equals);
    # OwnerGuardError W1 (empty), W2 (no candidate can win)
```
State First of Equals as the kernel rule for every winner in the module
docstring (`_strongest`'s `max` semantics stated, not accidental; grid:
`test_first_of_equals_is_the_kernel_rule_for_every_winner`).

`cardlang/runtime/trick_order.py` (new, neutral -- both dispatch halves
import it; imports `winners` and `state`, never `evaluate`): the
materialized table type `TrickOrderTable(is_trump, follow_class,
card_strength)` of `(Card, Ctx) -> value` callables; `project(card, ctx) ->
Arrival`; `public_pile_plays(value, ctx, caller) -> (label, pairs)` -- the
four `_pile_trick_winner` guards factored (zone-shape and identity as
`ShadowGuardError("resolve._check_arrival_record_pile_args", ...)`, empty
and no-deciding-actor as `OwnerGuardError`), returning possibly-empty pairs
so `follows_lead` can answer False; `winner_over_pile(zone, ctx)`,
`follows_lead_over_pile(card, zone, ctx)`; the marker type
`TrickOrderWinner` (a callable `(played, ctx) -> Player`) for the slot.

`cardlang/runtime/driver.py` (~L127, beside `rs.card_points`): materialize
`rs.trick_order` ONCE from `game.trick_order` -- the two defaults decided
here (`follow_class` -> `card.suit`; `card_strength` -> `values.rank_strength(rs.rank_index,
card.rank, "card_strength")`, and when `rank_index` is empty a
`ShadowGuardError("typecheck._check_trick_order (T2)", ...)` -- name T2, not
the RANKING_GATED sentence); the row callables evaluate the row's `Expr`
under the hermetic context. `RuntimeState.trick_order: TrickOrderTable |
None` (state.py ~L360). The driver imports `execute` -> `evaluate`, so no
cycle; `builtins.py` never imports `evaluate`.

`cardlang/runtime/evaluate.py`: factor `_user_function`'s context
construction (L131-147) into one helper with a `keep_actor` flag --
functions inherit `current_player`, ROWS clear it (`locals={"card": c}`,
`winner=None`, `action=None`, `current_player=None`); the bare-family Owner
Guard at L169-182 is then the runtime Shadow Guard behind R11-through-function.

`cardlang/runtime/builtins.py`: five arms in `call` -- `is_trump` /
`follow_class` / `card_strength` read `ctx.rs.trick_order` (a
`ShadowGuardError("resolve._check_trick_order_partition", ...)` when None),
`follows_lead(card, pile)`, `highest_by_trick_order(pile)`; the existing
`highest_trump_or_led_suit` arm routes through `public_pile_plays` too (its
zone-shape/identity guards become Shadow Guards -- update
`tests/test_arrival_record.py`'s runtime cells: `pytest.raises(ShadowGuardError...)`
for those two, `OwnerGuardError` for empty / no-actor; check whether
`ShadowGuardError` inherits from `OwnerGuardError` -- errors.py L46-70 --
before deciding whether those tests must change). No `ctx.trace` in any of
the five.

`cardlang/runtime/primitives.py` `value_function` (L322-339):
`"highest_by_trick_order"` returns a `TrickOrderWinner` (the block
contract); the docstring at L310-315 states two contracts by registry.
`cardlang/runtime/mechanics.py` `TrickForm.outcome` (L214-228): branch on
`stmt.winner_fn in TRICK_ORDER_GATED_WINNERS` -- block contract: project
`state["played"]` (the round's own plays) through `rs.trick_order` and call
`winners.highest_by_trick_order`; else the uniform contract as today; a
triaged Shadow Guard (`assert`, "resolve admits ...") on the branch. `TrickForm.__init__`
(L140-142): a block game has `stmt.trump is None` and `rs.trump is None`.
Contract deltas: builtins Assumes `rs.trick_order` materialized and the pile
argument static-checked; winners Establishes the one algorithm and First of
Equals for every winner; mechanics Assumes the play zone public and the
winner dispatched under one of two contracts by registry.

Assert-triage vocabulary (tests/test_assert_triage.py): every new `assert` /
`raise AssertionError` in `cardlang/runtime` carries a guarantor word
(`resolve`, `typecheck`, `registry`, `grammar`, `parse`, `shadow guard`) or
`unknown ...` in its attached text; every new `OwnerGuardError` names the
fix; every `ShadowGuardError` names the owning check. Prose gate
(tests/test_native_classification_prose.py): every mention of the five
names beside a classification word says Builtin, never Primitive -- run
both after ANY runtime comment edit.

Cost: measured 1.5x per Doppelkopf playout with the lazy Effective Lead
(the Architect's prototype: 62 -> 92 ms/game idle; 7,930 row evaluations
per game against 2,086 `is_trump` calls today); NO cross-call memo (the
epoch-counter memo the repo reverted); record the measurement in the grid's
ledger and re-measure in PRs 2/3.

## 8. IR (`cardlang/ir.py`, L60-75)

Keyed only when present (the `card_points` precedent):
`"trick_order": {"kind": "trick_order", "rows": [{"kind": "trick_order_row",
"key": row.key, "body": _expr(row.body)}]}`. `IR_VERSION` stays 1 (ir.py
L36-38's ruling); `tests/test_ir_schema_version.py::PINNED_SCHEMA` (L52)
gains the two tags and keys. No IR golden moves.

## 9. The proof harness (`tests/openspiel_ready/harness.py`)

`all_provenance_zones` (L216-229): a THIRD source -- walk the checked AST
(`check_source(spec.path)`) for every `n.Call` whose `func` is in
`ARRIVAL_RECORD_CALLS` and take the pile argument's zone name (a `NameRef`
classified `zone` or the family of a `Subscript`; guaranteed static by
section 5's resolve guard); retire the hand-listed `provenance_zones` field
(L203-214) and schnapsen's `provenance_zones=("trick_pile",)`
(tests/openspiel_ready/test_schnapsen.py:31); keep the Primitive half from
`PRIMITIVE_READS` until PR 5 empties it. Non-vacuity pin, DERIVED: for every
corpus game whose checked AST contains an Arrival-Record call or whose reads
row declares `arrival_zones`, the provenance proof records `vacuous=False`
(doppelkopf, schnapsen, skat, five-hundred today). Update the comment at
tests/openspiel_ready/test_doppelkopf.py:40. red under: drop the AST source
-- doppelkopf's provenance proof records `vacuous=True` and the pin fails.

## 10. Diagnostics, verbatim (the grid's needles are substrings of these)

Parse builder:
- P1: "`trick_order` is a block clause and takes no colon -- write `trick_order { trump: ... }`"
- P2: "`trick_order` rows are whitespace-separated, never comma-separated -- write `trick_order { trump: ...  follow_class: ... }`" (render the two keys from `TRICK_ORDER_ROWS`)
- P3: "a `trick_order` row is `{key}: <expr>`, not `{key} {op} <expr>` -- write `{key}: ...`" (`{op}` is `=` or `:=`)
- P4: "`{key}:` is not a row of `trick_order` -- the rows are `trump:`, `follow_class:`, `card_strength:`" (rendered from the registry)
- P5: "`trick_order` declares one `{key}:` row -- the repeat would silently replace the first; keep one"
- P6: the existing `once` mechanism: "a game declares one `trick_order { }` block -- merge the declarations into it" (the existing message spells the dash as an em dash; the grid needle stops before it)
- P7: "`trump:` names a suit of the declared deck by its bare name (`trump: spades`), not a number" / "... not a quoted string -- write the suit unquoted"
- P8: "`trick_order` declares no `trump:` row -- every Trick Order names its trumps; write `trump: false` for one with none"
- PR 0 sibling: `_resolve_trump`'s unknown-suit message, when the NAME is a rank of the deck (`trump: J`), appends " -- a rank as trump is a Trick Order: `trick_order { trump: card.rank is J }`"

Resolve:
- R1: "`trump: {suit}` beside a `trick_order { }` block -- with a Trick Order the block's `trump:` row is the trump (for a fixed suit, `trump: card.suit is {suit}`); drop the game-level clause" (parenthetical only when `{suit}` is a deck suit)
- R2: "round `trump` clause beside a `trick_order { }` block -- the block's `trump:` row is the trump; drop the clause"
- R3: "round winner {name} beside a `trick_order { }` block -- the block declares the Trick Order, and `highest_by_trick_order` is the winner that reads it; name that, or drop the block"
- R4: "`highest_trump_or_led_suit(...)` beside a `trick_order { }` block -- the block's rows are the trick order; call `highest_by_trick_order({pile})`"
- R4E: "`early` clause on winner highest_by_trick_order -- `early` predicates read the literal led suit, and a Trick Order's follow class may differ; no game has needed both -- drop the clause"
- R5: "round winner highest_by_trick_order reads the game's `trick_order { }` block, but this game declares none -- declare one (rows `trump:`, `follow_class:`, `card_strength:`), or name highest_of_led_suit / highest_trump_or_led_suit" (alternatives rendered from `BUILTIN_TRICK_WINNERS - GATED`)
- R6: "`{name}(...)` reads the game's `trick_order { }` block, but this game declares none -- declare one" + for a reader " (`{reader}(card)` is the reader of the block's `{row}:` row)"
- R7: "`trick_order { }` is read by nothing -- no round names `highest_by_trick_order`, and nothing outside the block calls {gated funcs}; name `highest_by_trick_order` on a trick round or call it over the trick pile, or drop the block"
- R8: "`{row}:` reads `{reader}(...)`, the reader of a row that comes after it in the Trick Order -- the rows are read in one order, `trump:`, then `follow_class:`, then `card_strength:`, whatever order they are written in, and a row may read only the readers of the rows before it; spell the fact in this row, or move it to the later one"; self: "`{row}:` reads its own reader `{reader}(...)`"; consumers: "`{row}:` calls `{consumer}(...)`, which reads every row of the Trick Order -- a row may not read the Trick Order it defines"; each + " through function `{f}`" when indirect
- R9: "`{row}:` reads the pronoun '{name}' -- a Trick Order row is hermetic: it is asked from the legality filter, the winner slot and a hand-rolled body under different live frames, so it may read no pronoun ({sorted _PRONOUNS}); a card's trick order is a fact of the card and public state alone" (+ through function); R9c: "`{row}:` makes a `choose` -- a Trick Order row is a fact, not a decision: it may not choose" (+ through function)
- R10: "`{row}:` reads zone '{zone}' ({ztype}), which does not project identity to every observer -- a Trick Order is public by construction and may read only fully public zones" (+ through function)
- R11: "`{row}:` reads `{zone}` bare (the acting player's instance) -- a Trick Order row has no acting player; subscript it with a player the state names (`{zone}[declarer]`)" (+ through function)
- R12: "{kind} -- `trick_order` orders a deck's cards for trick play, which a piece set has no notion of; drop the block"
- R13: "`{f}(...)` may not be called from a Trick Order row -- a row reads the card and public state only" (+ through function)
- R14: "`{call}` reads the Arrival Record of its pile argument, which must name a zone (`{call}(trick_pile)`); got {shape}"; R14_ID: "`{call}` over '{zone}' ({ztype}): the zone type does not project identity to every observer, so its provenance is not derivable from any observer's stream -- a winner may only be named over a fully public pile"
- R15: "round `into {zone}` ({ztype}): a trick's play zone must project identity to every observer -- the plays are the provenance every winner reads; use a TrickPile"
- shadowing hint: "... -- the language mints `{reader}(card)` from a `trick_order { {row}: ... }` row; move the body into the row, or rename"

Typecheck:
- T1: "`trump:` row must type Boolean (is this card a trump?), got {type}" (+ " -- for a fixed trump suit write `trump: card.suit is {suit}`" when Suit; + " -- a Trick Order row is never absent-valued (a `none` would read as not-a-trump silently)" when Boolean?); "`follow_class:` row must type Suit? (the class the card follows as, or none for class-less), got {type}" (+ " -- a trump follows as a trump by the `trump:` row, never by a class value; the class of a trump card is not consulted" when String); "`card_strength:` row must type Integer (strength within its class; higher beats lower), got {type}"
- T1a: "`{row}:` row types as `Any`, the permissive top (a value the checker cannot type -- a mixed-branch `if`, an untyped read); a Trick Order row must type exactly {expected}"
- T2: "`trick_order` declares no `card_strength:` row, so strength defaults to `rank_value(card)`, which reads `ranking:` -- but the game declares no `ranking:`; declare one, or write a `card_strength:` row"
- ranking-gate remedy (both sites): "... -- declare one, or declare a `trick_order { }` with a `card_strength:` row and name `highest_by_trick_order`"

Runtime:
- W1: "highest_by_trick_order over '{label}': the pile is empty -- no plays to name a winner from; guard the read (`{label} is not empty`)"; W2: "highest_by_trick_order over '{label}': no card can win -- every arrival is class-less (`follow_class` none) and none is a trump; guard the read (`any card in {label} where is_trump(card) or follow_class(card) is not none`)"; no deciding actor / not a zone / not identity-to-all: the `_pile_trick_winner` texts parametrized by caller (the last two as Shadow Guards); `follows_lead` non-card first argument: "follows_lead expects a card, got {type}".

## 11. The Doppelkopf migration, in order

The stream pin `tests/golden/doppelkopf_stream_hashes.json` is ALREADY
captured on the pre-migration tree (commit f7d0640, 200 seeds; red under a
planted last-of-equals in doko.py: 33 of the first 40 seeds moved). Do NOT
re-bless it. Steps:

1. Build the construct (sections 2-9) until the grid is green with the
   corpus untouched; run `pytest -q tests/test_trick_order.py` bare and
   marked (0 failed; then remove marks).
2. Edit `docs/games/doppelkopf.cardlang`: add the block after `card_points`
   (L52):
   ```
   trick_order {
     trump:         card.rank is Q or card.rank is J or card.suit is diamonds
                    or (card.suit is hearts and card.rank is "10")
     card_strength: if card.suit is hearts and card.rank is "10" then 300
                    elif card.rank is Q then 200 + suit_order(card.suit)
                    elif card.rank is J then 100 + suit_order(card.suit)
                    else rank_value(card)
   }
   ```
   delete `led_trump` / `led_suit` (L93-94) and their assignments (L142-143);
   `let w = highest_by_trick_order(trick_pile)` at L230; delete `function
   is_trump` (L469-471) and `holds_trump` (L473-474); rewrite `follow_ok`
   (L478-483) as `if any card in hand[p] where follows_lead(card, trick_pile)
   then follows_lead(c, trick_pile) else true`; add `function suit_order(s :
   Suit) = if s is clubs then 4 elif s is spades then 3 elif s is hearts then 2
   else 1`; rewrite the header comment (L39-42) and doppelkopf.md L127-131.
3. Run the stream pin FIRST: `pytest -q tests/test_trick_order_migration.py`
   (all 200 seeds, `-m ""`); then `tests/test_playout_doppelkopf.py`
   (`doppelkopf_scores.json` byte-identical) -- BEFORE deleting `doko.py`.
   Any moved seed: stop, diff the two trees' event streams for the first
   divergence (the Architect's Q9), fix, do not re-bless.
4. Delete `cardlang/runtime/doko.py`; remove `doko_trick_winner` from
   `PRIMITIVE_CALL_FUNCS`, `DECK_ONLY_CALL_FUNCS`, `CALL_SIGS`
   (signatures.py:103), the dispatch arm (primitives.py:123-127), the reads
   row (reads.py:260-265); update `tests/test_primitive_narrowing.py`
   (L346-347, 422, 461 `EMITS_TRACE`, 903, 922), `tests/test_arrival_record.py`
   (L248, 284: repoint the synthetic rows at skat.py / skat.cardlang, whose
   `arrival_zones` row survives until PR 2), `tests/test_primitive_reads.py:307`
   comment, `tests/rejections/arrival_winner_old_arity.cardlang` (+ .expected:
   name `skat_trick_winner(0)`), the `EMITS_TRACE` pin.
5. Move `tests/test_playout_doppelkopf.py` to observation-derived facts (the
   schnapsen shape: plays = observed `move` events into `trick_pile`, winners
   = observed `trick_pile -> captured[w]` drains) -- keeping its Pagat
   recomputation INDEPENDENT (it never calls `follows_lead` /
   `highest_by_trick_order`); the score golden stays as it is.
6. Re-run the openspiel proof module (`tests/openspiel_ready/test_doppelkopf.py`)
   -- non-vacuous provenance through the AST-derived half.
7. Fuzz: the game-file edit shifts lines; `tests/fuzz/test_fuzz.py` has no
   doppelkopf key in `EXCUSED` -- run the sweep; a NEW finding is shrunk and
   recorded per that module's docstring, never silenced.
8. Re-execute the stream pin's red-under against the kernel (flip `>` to
   `>=` in `winners.highest_by_trick_order`, run, revert) and record the
   count of moved seeds in `tests/test_trick_order_migration.py`'s docstring.

The scoreboard tick on epic #248 rides the operator's merge (nobody edits
#248, #143 or docs/design-notes/primitive-inventory.md in this PR).

## 12. Docs (same change; operating rules 1-4, 7)

- `docs/decisions.md`: a new section "Trick Order" (the block, the readers,
  the two Builtins, the Effective Lead, First of Equals, the presence
  partition, the hermeticity rules, the row order, `follows_lead` on an empty
  pile, mid-trick reads); the "Per-game predicates for contextual
  interpretations" paragraph (L366-375) rewritten in place to the block; the
  `ranking:` scope sentence (L516-518) repointed at the block (the open
  question keeps Tichu's Phoenix).
- `docs/library.md`: "The trick" (L7-50: `trump <expr>` for block games),
  "Winner functions" (L250-263: add `highest_by_trick_order`, say which
  winners are refused beside a block), "Native functions" (~L744+: the five
  entries beside `highest_trump_or_led_suit`), "Rules" untouched until PR 5.
- `docs/model.md`: the trick winner sentence names the Trick Order.
- Glossary: mint `docs/glossary/trick-order.md`, `follow-class.md`,
  `card-strength.md` (never bare strength/height/order; `belote_trump_height`
  / `tarot_trump_height` become retired spellings when their PRs land),
  `effective-lead.md` (against `state.led_suit`, the literal first card),
  `first-of-equals.md` (the kernel rule for every winner); add `order` to the
  reserved words (traversal order / trick order / ranking order) as a
  reserved entry; regenerate `docs/glossary.md` with `tools/glossary_index.py`;
  `tests/test_glossary.py` pins the index.
- `docs/games/doppelkopf.md`: L127-131 (the primitive sentence -> the block).
- `docs/kernel-migration.md`: no debt entry (nothing recorded).
- ASCII-only prose in everything new; glossary names in full and Title Case.

## 13. Existing tests the change touches (beyond the grid)

`tests/test_game_clause_guards.py` (`_CLAUSE_TEXT`, `_head_is_name_shaped`),
`tests/test_keyword_anchoring.py` (derived), `tests/test_grammar_ambiguity.py`
(the boundary pin), `tests/test_node_registry.py`, `tests/test_binder_registry.py`,
`tests/test_signatures.py`, `tests/test_native_dispatch_split.py`,
`tests/test_piece_content_guards.py`, `tests/test_native_call_boundary.py`,
`tests/test_ir_schema_version.py`, `tests/test_arrival_record.py`,
`tests/test_primitive_narrowing.py`, `tests/test_primitive_reads.py`,
`tests/rejections/arrival_winner_old_arity.*`, `tests/test_trump_slot_class.py`
(PR 0: `WINNERS` for `reads_trump` and the body-partition witness derived as
`TRICK_WINNER_NAMES - TRICK_ORDER_GATED_WINNERS`; the gated member's cells
DECIDED -- R5 for every spelling without a block, R2 with; the
`test_the_body_partition_is_a_witness_on_this_pile` domain excludes it),
`tests/test_ranking_guard.py` (the reworded remedy), `tests/openspiel_ready/harness.py`,
`tests/openspiel_ready/test_schnapsen.py`, `tests/openspiel_ready/test_doppelkopf.py`,
`tests/test_playout_doppelkopf.py`, `tests/test_glossary.py`, `tests/test_doc_snippets.py`
(any new ```cardlang fence in decisions.md/library.md is extracted and checked).

## 14. Where PR 1 collides with PR #365 (merge main after #365 lands)

- `cardlang/resolve.py`: `_resolve_trump` (new in #365) -- add the early
  return over a block game; the winner-slot `elif nd.trump is not None and
  nd.winner_fn not in TRUMP_READING_WINNERS` arm (#365, ~L5678) -- skip gated
  winners and block games; the Contract block paragraph #365 added.
- `cardlang/builtins/functions.py`: `TRUMP_READING_WINNERS` (#365) -- the new
  winner is NOT a member; the header comment at L22-27 (#365 amended it)
  states the two contracts.
- `cardlang/runtime/winners.py`: `_strongest` / `rank_strength` (#365) -- the
  new algorithm sits beside them; First of Equals stated for both.
- `cardlang/runtime/values.py` `rank_strength` (#365): the default-strength
  closure names T2 as owner when `rank_index` is empty (or `rank_strength`
  takes the owner as a parameter).
- `cardlang/typecheck.py` `_check_round_trump` (#365): runs after resolve's
  partition; unchanged.
- `tests/test_trump_slot_class.py` (#365): section 13.
- `docs/library.md`: #365 edited "The trick" / "Winner functions"; PR 1
  edits the same paragraphs -- merge by hand.

## 15. Order of work (each step's artifact red first)

1. Registries + census pins (grid section 7 cells flip). 2. `winners.py`
algorithm (the solved miniature: `test_winner_cell`, `test_follows_lead_cell`,
`test_strength_is_never_read_on_a_non_candidate`). 3. `runtime/trick_order.py`,
driver table, two-contract slot, builtins arms, evaluate helper
(`test_winner_slot_has_two_contracts_keyed_by_registry`). 4. Grammar + AST +
parse (the P-cells and the derived clause-guard pins). 5. Resolve guards --
partition, rows, pile args, play zone, early (the R-cells). 6. Typecheck (the
T-cells). 7. IR + schema pin. 8. Harness derivation + non-vacuity pin. 9. The
end-to-end cells green (`test_slot_and_call_agree` etc.). 10. Doppelkopf
(section 11). 11. Docs (section 12). 12. Ledger re-read; remove every xfail
mark; the two comment-scraping pins; bare `mypy`; full `pytest -q -n 8`; the
rigs.

## 16. Evidence the implementer quotes (PR body)

- The grid: `pytest -q tests/test_trick_order.py` -- `N passed` with no
  xfail left; the bare run `TRICK_ORDER_GRID_BARE=1 ...` -- `0 failed`; the
  born-red line: `285 failed, 13 passed in 4.57s` (main 8a722cd).
- The stream pin: `pytest -q tests/test_trick_order_migration.py` -- `201
  passed` (all 200 seeds); its re-executed red-under with the count of moved
  seeds.
- `tests/test_playout_doppelkopf.py` green; `doppelkopf_scores.json`
  byte-identical (`git diff --stat` shows no golden moved).
- `tests/openspiel_ready/test_doppelkopf.py` green with the provenance cell
  `vacuous=False`.
- The Doppelkopf playout cost before/after (the 1.5x claim, measured on this
  branch).
- Bare `mypy` clean; full `pytest -q -n 8` summary line; the rigs' summary
  line; CI green on all three.

Ordered red-unders (execute each, revert, record `red under:` in the guard's
grid docstring or the test): (a) `_check_trick_order_partition` skipped ->
every partition cell; (b) `_resolve_trump`'s early return dropped -> the
`with-block-game-trump*` cells show the dead-clause message too (a second
message is not a failure, so pin it as `forbidden`) ; (c) the row-hermeticity
walk stopped at the row body (no call-graph) -> every `*-through-function`
cell; (d) `TRICK_ORDER_ROW_CALLS` grown by `player_holding` -> its cell +
the partition pin; (e) T1 routed through `_check_operand` for `trump:` ->
the `trump-Boolean?` cell; (f) T2 skipped -> `default-strength-without-ranking`;
(g) the pile-argument guard skipped -> the R14 cells; (h) the play-zone arm
skipped -> `into-Deck` etc.; (i) `_strongest`/`highest_by_trick_order` last
of equals -> the tie cells + the stream pin; (j) strength read on every
arrival -> `test_strength_is_never_read_on_a_non_candidate`; (k) the harness
AST source dropped -> the non-vacuity pin; (l) `trick_order` dropped from
`STRUCT_TYPE_NAME` / `CARD_RANK_NAME` -> the derived clause-guard pins and
the absorber cells.

## 17. Risks

- The 1.5x legality-path cost is standing (heavier rows in PRs 2/3); no
  memo is sound without the epoch counter -- record, do not build.
- The tightening cells change the EXISTING call form's static behavior
  (computed/concealed piles refused at resolve) and every trick round's play
  zone -- corpus unchanged, but any downstream fixture that used a computed
  pile must move.
- PR #365's grid must be re-derived, not skipped by name.
- Two diagnostics can co-report on one defect (R1 + `_resolve_trump`, R2 +
  #365's blind-winner arm) if the early returns are missed -- the grid's
  `forbidden` needles catch the second message.
- The stream pin's rendering hashes `repr` of observation events: a change to
  `observe.render` in some unrelated PR would move every hash -- the pin then
  says so loudly and is re-blessed ONLY on the pre-migration commit of that
  PR (its docstring's rule), never as part of a migration.
