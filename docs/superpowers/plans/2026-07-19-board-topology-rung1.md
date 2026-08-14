# Board Topology Rung 1 (Tic-Tac-Toe against Stages 1–2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the walking skeleton of board-game support — the `board:`/`pieces:` clauses, the `BOARDS` and component-set registries (`Card ⊂ Piece`), board-minted named-member position domains, the capacity zone-type property, the cell/line query register — proven by tic-tac-toe: registered in the corpus, differentially validated against OpenSpiel's native `tic_tac_toe`, with a full `openspiel_ready` proof module, and the entire card corpus byte-identical.

**Architecture:** Everything docks into landed machinery: board domains extend the `positions {}` substrate (named members instead of integer bounds, same collision wall, same two consumption surfaces), cells are `Cell`-typed zones (existing row, existing projections — the observation moat does not move), placement is ordinary kernel movement, and the decision is an ordinary parameterized `offer`. The genuinely new registries (component sets, boards, capacity) land closed with pins on day one. Spec: `docs/design-notes/board-topology.md` (§2 model, §4 stage 1–2); requirements: `docs/research/topology-and-query-requirements.md`.

**Tech Stack:** Python 3.11, lark grammar, mypy --strict (covers `tests/` too), pytest, pyspiel (differential oracle + adapter proofs).

## Global Constraints

- **Byte-identical card corpus** is the acceptance wall for `Card ⊂ Piece` (board-topology.md §2.3): all 8 IR goldens (`tests/golden/*.ir.json`) regenerate to zero diff, all behavioral goldens unchanged, full suite green. Never regenerate a golden to *absorb* a diff — a diff is a defect.
- **The observation moat does not move** (wave A): no new zone-type rows, no new projection levels, no change to `ZONE_PROJECTIONS` / `partition.py::ZONE_PROBES` / `observe.py` emission logic.
- **Surface totality + closed-domain completeness**: every task that adds grammar surface, a wall, or a registry runs the `surface-totality-audit` skill BEFORE writing its tests and ships its misuse-probe rejection tests + completeness ledger (in the covering test module's docstring). A residual cell without both a wall and a roadmap.md line fails the task.
- **Assert triage** (`tests/test_assert_triage.py`): any `assert`/`AssertionError` added under `cardlang/runtime/` or `cardlang/stdlib/` must carry a guarantor word or fallthrough marker; game-reachable failures are typed `RuntimeError`s, never asserts.
- **Verification commands** (from repo root, worktree): `export PYTHONPATH="$PWD"` and use `/Users/benh/Projects/Card game DSL/.venv/bin/python -m pytest` / `.venv/bin/mypy`. Bare `mypy` (never `mypy cardlang`), full `pytest -q` before any push.
- **ASCII-only prose** in code/docs (no math glyphs; em dash and ellipsis fine). Comment hygiene: failure-mode comments get subjunctive rewording, never deletion.
- **Nothing beyond the witness**: later-stage surface (directions, `Point`, `HiddenCell`, double indexes, `roll`, probes, `reachable`, cell literals in expressions, piece-query grammar forms, `for each cell`, position-typed state) is NOT built — each is either grammatically inexpressible or loudly walled, and recorded in roadmap.md.
- Commit after every task; message footer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Settled design decisions (the note's §5 "surface residue", decided here)

These were deliberately left open by the design note; rung 1 settles them. They get promoted into `decisions.md` in Task 11.

1. **One component-set registry, DECKS as a derived view.** `ComponentSet` (in `cardlang/runtime/values.py`) carries `flavor: "card" | "piece"`, ordered axis names, and the existing `Deck` payload shape. `COMPONENT_SETS` holds all entries; `DECKS` becomes `{name: cs.deck for card-flavored}` so every existing consumer is untouched. Piece axes bind positionally to the two existing item slots (axis 1 = the `suit` slot, axis 2 = the `rank` slot); the runtime `Card` class is unchanged (it is the runtime representation of the individuated base kind — renaming it would perturb reprs for zero surface gain).
2. **Axis-name-driven field access.** `piece.side` / `card.suit` typecheck against the game's component set's declared axis names (per-game field table replacing the global `CARD_FIELDS` read); each axis types as `TEnum(<axis name>)`, so cross-axis comparison is rejected exactly as `card.rank is spades` is today. Deck games keep `suit`/`rank` spellings and `TEnum("Suit")`/`TEnum("Rank")` — byte-identical by construction.
3. **Noun/content agreement is a typecheck wall** (the layer that owns operand-kind classes): movement item noun, movement/reveal filter binder, the card-query and aggregation forms, `Card`/`Suit`/`Suit?`/`Rank` move parameters, `ranking:`/`trump:` clauses, `suit`/`rank` quantifier+iteration roles, and deck-only stdlib functions each demand deck flavor and reject in a piece game with a message naming the game's declared kind (and vice versa for `piece(s)` in a card game). The classification of stdlib functions is a closed table pinned against `STDLIB_CALL_FUNCS`.
4. **Board declaration form**: `board: <family>(<int-args>)` — `board: grid(3, 3)`. The `BOARDS` registry (new `cardlang/stdlib/boards.py`) maps family name to a generator with declared argument bounds; unknown family / wrong arity / out-of-bounds args are resolve diagnostics.
5. **The board mints one position domain named `cell`** with **string members** (grid cells `a1`, `b1`, ... file letter = column from left, number = row from bottom, row-major from `a1`). It rides the `positions {}` substrate: same collision wall (extended to collide against a declared `positions {}` name), same 256 cap, same two consumption surfaces (zone-family index, move-parameter domain), same unowned rule. Cell values type as the new `TCell`; a zone family indexed by a named-member domain subscripts only with `TCell`-typed expressions (parameters, binders) — integer-keyed domains keep today's `TInteger` rule.
6. **Cell constants are NOT expression surface at rung 1.** No game sentence needs to name `a1` (parameters and quantifiers cover TTT); a bare `a1` stays an unknown-name diagnostic. Recorded residual; the witness is a game whose setup or rules name specific cells (breakthrough).
7. **The cell-query register mirrors the existing registers.** Bare quantifiers over any declared position domain (the recorded wall-lift): `any <domain> where <pred>` / `all <domain>s where <pred>` / `number of <domain>s where <pred>`, fixed binder = the domain name (like `player`). Collection forms only where a collection value exists: `any line in <expr> where <pred>` and `all cells in <expr> where <pred>` (binder `line` / `cell`). `lines(<k>)` is a stdlib call reading the game's board entry. `for each <position>` stays rejected (no witness — breakthrough's setup arrays are the recorded witness).
8. **Capacity is a zone-type registry column** (`ZONE_CAPACITY` in `cardlang/stdlib/zones.py`): `Cell` = 1, every other row unbounded (`None`), pinned total against `LIBRARY_ZONE_TYPES`, enforced as a typed `RuntimeError` in the movement executor. The `Point` row (unbounded stack) is NOT added — its witness is backgammon (stage 3); roadmap records it.
9. **Piece seeding reuses the Deck-typed-zone rule** (the one existing "initial contents" concept, one spelling per concept): the game's `Deck`-typed zone is seeded with the component set at start (`driver.py` already does this via `build_deck`); TTT names it `box`. A piece game with no shuffle consumes no randomness — every seed yields the identical game, pinned by the proof module.
10. **Utilities**: TTT encodes win/draw/loss into `result[player] : Integer` set to `+1`/`-1` (draw leaves `0`/`0`), `winner: highest result` — so adapter returns are `[+1,-1]` / `[0,0]`, matching native TTT's utility structure (raw scores would make losing indistinguishable from drawing — a semantic distortion, not a cosmetic one).

---

### Task 1: Component-set registry (`Card ⊂ Piece` data layer, no surface)

**Files:**
- Modify: `cardlang/runtime/values.py` (add `ComponentSet`, `COMPONENT_SETS`, derive `DECKS`, add `xo_marks`, extend `build_deck` refusal)
- Modify: `cardlang/stdlib/values.py` (size table + accessors flow for piece sets)
- Test: `tests/test_component_sets.py` (new)

**Interfaces:**
- Produces: `ComponentSet(flavor: Literal["card","piece"], axes: tuple[str, str], deck: Deck)` — `axes` = the surface field names bound positionally to the (`suit`, `rank`) item slots; decks are `ComponentSet("card", ("suit", "rank"), <existing Deck>)`.
- Produces: `COMPONENT_SETS: dict[str, ComponentSet]` (all 10 decks + `xo_marks`); `DECKS: dict[str, Deck]` derived as `{n: cs.deck for n, cs in COMPONENT_SETS.items() if cs.flavor == "card"}` — every existing consumer reads `DECKS` unchanged.
- Produces: `xo_marks = ComponentSet("piece", ("side", "kind"), Deck(suits=(), ranks=(), values={}, cards=(("mark","x"),)*5 + (("mark","o"),)*4))` — 9 items, explicit-list form (the canasta108 precedent for asymmetric multiplicities; `cards` entries are `(rank, suit)` = `(kind, side)`).
- Produces: `component_set(name) -> ComponentSet | None` accessor; `build_deck` keeps working for every `COMPONENT_SETS` name (piece sets build through the same explicit-list path).

- [ ] **Step 1: Run the surface-totality audit (Step 1 enumeration) for this registry.** Domain = `COMPONENT_SETS` rows x consumers of `DECKS`/`_DECK_SIZE`/`build_deck`. Registry sources: `cardlang/runtime/values.py:88-137`, `cardlang/stdlib/values.py:23-34`, pins at `tests/test_deckcheck.py:273-275` and `tests/test_ranking_conventions.py:136-154`. Confirm: the ranking-conventions matrix quantifies over `DECKS` (the derived view) so piece sets stay out of it by construction — assert that in the ledger, don't assume it.
- [ ] **Step 2: Write the failing tests** in `tests/test_component_sets.py` (module docstring carries the completeness ledger):

```python
"""Component sets: the one registry behind `cards:` and `pieces:`.

property:   every COMPONENT_SETS row is well-formed; DECKS is exactly its
            card-flavored projection; sizes pin to build_deck
domain:     COMPONENT_SETS rows x {flavor, axes, deck payload, size}
registry:   cardlang/runtime/values.py::COMPONENT_SETS
covered:    all rows, exhaustively parametrized below; DECKS-view equality;
            xo_marks composition pinned card-by-card
sampled:    build_deck ordering (one deck + xo_marks) — order is the
            registry-literal order by construction
residual:   none
"""
from cardlang.runtime.values import COMPONENT_SETS, DECKS, ComponentSet, build_deck
from cardlang.stdlib.values import deck_size
import pytest


def test_decks_is_the_card_flavored_projection() -> None:
    assert DECKS == {
        n: cs.deck for n, cs in COMPONENT_SETS.items() if cs.flavor == "card"
    }
    assert len(DECKS) == 10  # the pre-refactor deck census, unchanged


@pytest.mark.parametrize("name", sorted(COMPONENT_SETS))
def test_every_set_declares_two_axes_and_a_size(name: str) -> None:
    cs = COMPONENT_SETS[name]
    assert len(cs.axes) == 2 and all(a.isidentifier() for a in cs.axes)
    assert cs.flavor in ("card", "piece")
    assert deck_size(name) == len(build_deck(name))


def test_card_sets_spell_the_deck_axes() -> None:
    assert all(
        cs.axes == ("suit", "rank")
        for cs in COMPONENT_SETS.values()
        if cs.flavor == "card"
    )


def test_xo_marks_composition() -> None:
    marks = build_deck("xo_marks")
    assert len(marks) == 9
    assert sum(1 for m in marks if m.suit == "x") == 5
    assert sum(1 for m in marks if m.suit == "o") == 4
    assert all(m.rank == "mark" for m in marks)
```

- [ ] **Step 3: Run them, verify failure** (`ImportError: cannot import name 'COMPONENT_SETS'`): `.venv/bin/python -m pytest tests/test_component_sets.py -q`
- [ ] **Step 4: Implement.** In `cardlang/runtime/values.py`: add the frozen `ComponentSet` dataclass (with a `__post_init__` wall: axes distinct, identifiers, and for piece flavor the axes must not be `("suit","rank")` — the deck spellings are the card flavor's); build `COMPONENT_SETS` by wrapping the ten existing `Deck` literals verbatim (do not retype the data — wrap the same expressions) plus `xo_marks`; derive `DECKS`. Update `build_deck`'s refusal message to name component sets. In `cardlang/stdlib/values.py`: add `"xo_marks": 9` to the size table (rename the table's comment to component sets; keep the deck rows byte-identical).
- [ ] **Step 5: Regenerate nothing; prove byte-identity.** Run the 8 IR golden tests + the full suite:
  `.venv/bin/python -m pytest tests/test_hearts_ir.py tests/test_bridge_ir.py tests/test_getaway_ir.py tests/test_french_tarot_ir.py tests/test_component_sets.py -q` then full `pytest -q`. Expected: all green, `git diff tests/golden/` empty.
- [ ] **Step 6: mypy clean**: `.venv/bin/mypy`
- [ ] **Step 7: Commit** `feat: component-set registry — DECKS becomes its card-flavored view; xo_marks lands`

### Task 2: `pieces:` clause + skeleton walls + flavor stamping

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (game_item alternative `pieces`)
- Modify: `cardlang/parse.py` (builder + `game()` walls)
- Modify: `cardlang/ast/nodes.py` (`Game.content_flavor` or equivalent; keep `Game.deck` as the selected set name)
- Modify: `cardlang/resolve.py` (`_resolve_deck` generalizes to component sets; flavor-aware walls)
- Modify: `cardlang/ir.py` (emit the flavor only if the IR carries the deck today — mirror whatever `deck` emission exists)
- Tests: `tests/test_game_clause_guards.py` (GAME_ITEMS pin + new walls), `tests/rejections/` fixtures
- Modify: `tests/rejections/missing_cards_declaration.expected` (message now names both clauses)

**Interfaces:**
- Consumes: `COMPONENT_SETS`, `component_set()` from Task 1.
- Produces: grammar `pieces: "pieces" ":" NAME`; `Game.deck: str` stays the selected component-set name; `Game.content_flavor: str` (`"card"`/`"piece"`) stamped at parse from which clause appeared. Resolve rejects: a `cards:` name that is piece-flavored ("'xo_marks' is a piece set — declare it with `pieces:`"), a `pieces:` name that is card-flavored, both clauses together ("a game declares `cards:` or `pieces:`, not both — no game has witnessed needing both"), neither ("must declare `cards: <deck>` or `pieces: <set>`" — update the parse wall's message and fixture).

- [ ] **Step 1: Audit first.** Enumerate the clause matrix: {cards only, pieces only, both, neither, duplicate pieces, unknown pieces name, cross-flavor name in each clause} x {parse, resolve} — every cell implemented or walled. Write the five misuse probes as rejection fixtures: `pieces_and_cards_together`, `pieces_unknown_set`, `pieces_names_a_deck`, `cards_names_a_piece_set`, `duplicate_pieces_clause` (each `.cardlang` + `.expected` under `tests/rejections/`, matching the existing fixture format).
- [ ] **Step 2: Write failing wall tests** — extend `tests/test_game_clause_guards.py`: update the `GAME_ITEMS` registry pin to include `pieces` (14 alternatives), add parametrized rejection-fixture runs for the five probes, update the missing-clause message test. Run; expected failures: grammar error on `pieces:` fixture parse.
- [ ] **Step 3: Implement** grammar + parse builder (`pieces` -> `_Pieces(name, span)`; `game()` `once("pieces:")`; mutual-exclusion + missing-either walls with the messages above; stamp `content_flavor`), resolve `_resolve_deck` -> `_resolve_component_set` (unknown-name message lists sets of the matching flavor), and thread flavor into `TypeEnv`/resolve categories for Task 3's walls (a `flavor: str` field, defaulted `"card"`).
- [ ] **Step 4: Run the new tests + full suite + mypy; byte-identity holds** (no golden diffs — card games take the `cards:` path verbatim).
- [ ] **Step 5: Commit** `feat: pieces: clause — component-set selection with flavor walls`

### Task 3: Noun/content agreement + axis-driven fields (the `Card ⊂ Piece` walls)

**Files:**
- Modify: `cardlang/typecheck.py` (per-game axis field table replacing global `CARD_FIELDS` reads at `:347`/`:1439`; item-noun wall at `:1826`; CardQuery/Comprehension flavor walls at `:1316-1338`; binder names at `:1585-1596`)
- Modify: `cardlang/resolve.py` (`_node_binders` `:250-257` flavor-driven; quantifier/iteration roles `suit`/`rank` flavor wall; `Card`/`Suit`/`Suit?`/`Rank` param flavor wall in `_check_move_params`; `ranking:`/`trump:` flavor walls; deck-only stdlib call wall)
- Modify: `cardlang/stdlib/functions.py` (add `DECK_ONLY_CALL_FUNCS: frozenset[str]`)
- Modify: `cardlang/runtime/execute.py` / `cardlang/runtime/evaluate.py` (filter/query binder name from flavor — bind BOTH the flavor noun and keep evaluation identical)
- Tests: `tests/test_piece_content_guards.py` (new; the flavor matrix + ledger), `tests/rejections/` probes, `tests/test_signatures.py` (deck-only classification pin)

**Interfaces:**
- Consumes: `Game.content_flavor`, `ComponentSet.axes`.
- Produces: in a piece game — `move ... pieces ...` legal (noun `piece`/`pieces`), filter binder `piece`, `piece.side`/`piece.kind` typed `TEnum("side")`/`TEnum("kind")`; `card`/`cards` noun, card-query forms, `sum ... over cards in ...`, `ranking:`, `trump:`, `any suit/rank where`, `for each suit/rank`, `Card`/`Suit`/`Suit?`/`Rank` params, and deck-only stdlib calls each rejected with: `"this game declares pieces ('xo_marks') — <construct> reads deck content; <fix>"`. In a card game, `piece`/`pieces` noun rejected symmetrically. Axis values (`x`, `o`, `mark`) enter the enum-value namespace from the component set exactly as deck values do.
- Produces: `DECK_ONLY_CALL_FUNCS` (at minimum `rank_value`, `suit_of`, `card_value`, plus whatever the audit's sweep of `STDLIB_CALL_FUNCS` classifies as reading suit/rank/ranking semantics), pinned by a totality test: every `STDLIB_CALL_FUNCS` member is classified generic-or-deck-only by an explicit table assertion.

- [ ] **Step 1: Audit first — this is the stage-1 flagship matrix.** Domain axes from their registries: noun-bearing constructs (grammar movement/reveal/cq_*/agg productions + `_node_binders` + param-domain table + game_item clauses + `DOMAINS` quantifier roles + `STDLIB_CALL_FUNCS`) x flavor {card, piece}. Every cell: implemented / rejected-naming-the-kind / grammatically inexpressible (piece-query grammar forms — record in roadmap). Include pronoun-rooted field contexts (`action.card.*` if the pronoun surface exposes card fields) in the wrong-axis probe set. Write probes: `piece.suit` in a piece game, `card.side` in a card game, `any card in ...` in a piece game, `rank_value(...)` in a piece game, `ranking: aces low` under `pieces:`, `move one card ...` in a piece game, `any suit where ...` in a piece game, plus the shadowed-binder probe (`piece` referenced outside a filter).
- [ ] **Step 2: Write the failing matrix tests** in `tests/test_piece_content_guards.py` — a parametrized table of (source fragment, expected diagnostic substring) driving `check_source`, with the ledger in the docstring. Include POSITIVE cells: a minimal piece game (hand-rolled inline source with `pieces: xo_marks`, a Deck-typed `box`, one `PlayerPile` reserve, a filtered `move all pieces ... where piece.side is x`) typechecks clean end-to-end.
- [ ] **Step 3: Implement** (walls at the named file:line seams; field table = `{axes[0]: TEnum(axes[0]-spelling), axes[1]: ...}` with the card flavor mapping to today's exact `CARD_FIELDS` values so deck diagnostics/IR are unchanged). Keep every runtime binder binding through one helper that reads the flavor (`"card"` vs `"piece"`) so evaluate/execute cannot drift.
- [ ] **Step 4: Byte-identity + full gates.** 8 IR goldens zero-diff, full `pytest -q`, `mypy`.
- [ ] **Step 5: Commit** `feat: Card is the deck flavor of Piece — noun/axis/flavor walls at the content-kind level`

### Task 4: Capacity as a zone-type property

**Files:**
- Modify: `cardlang/stdlib/zones.py` (`ZONE_CAPACITY: dict[str, int | None]`, total over `LIBRARY_ZONE_TYPES`)
- Modify: `cardlang/runtime/execute.py` (`_movement` destination wall)
- Tests: `tests/test_zone_capacity.py` (new)

**Interfaces:**
- Produces: `ZONE_CAPACITY` — `"Cell": 1`, every other current row `None`; accessor `zone_capacity(zone_type) -> int | None` (KeyError-loud like `zone_projection`).
- Produces: the movement executor wall — before appending to a destination whose type has finite capacity: `raise RuntimeError(f"zone '{label}' is a {ztype} (capacity {cap}) and already holds {n} — the move would overfill it; guard the move (`{label} is empty`)")`. Comment names the guard discipline (this wall backstops game guards; the registry owns the class).

- [ ] **Step 1: Audit.** Property total over `LIBRARY_ZONE_TYPES` (registry-derived pin test: `set(ZONE_CAPACITY) == set(LIBRARY_ZONE_TYPES)`); consumers enumerated (every movement/deal/gather path that appends to a zone — from `execute.py` `_movement`/gather and the auction/trick executors if they move cards — route them through one append-guard helper so the wall cannot be bypassed; the audit lists each call site). Residual: `Point` (unbounded stack row) not added — roadmap line in Task 11.
- [ ] **Step 2: Failing tests**: registry-total pin; FreeCell overfill probe (drive a movement of 2 cards into a `Cell` via a synthetic game source and assert the typed `RuntimeError` message); FreeCell corpus still green (its guards mean the wall never fires on the honest game).
- [ ] **Step 3: Implement**; run capacity tests + full suite + mypy (goldens untouched — no card game overfills).
- [ ] **Step 4: Commit** `feat: capacity is a zone-type registry column with a loud movement wall (Cell = 1)`

### Task 5: The `BOARDS` registry (grid family + lines)

**Files:**
- Create: `cardlang/stdlib/boards.py`
- Test: `tests/test_boards_registry.py` (new)

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class BoardEntry:
    """One instantiated board: closed static data, integrity-pinned from birth."""
    family: str            # "grid"
    args: tuple[int, ...]  # (3, 3)
    cells: tuple[str, ...] # ("a1","b1","c1","a2",...,"c3") — row-major from a1
    def lines(self, k: int) -> tuple[tuple[str, ...], ...]: ...  # precomputed, see below

BOARD_FAMILIES: dict[str, BoardFamily]  # {"grid": BoardFamily(arity=2, lo=1, hi=16, build=_grid)}
def board_entry(family: str, args: tuple[int, ...]) -> BoardEntry  # raises ValueError on bad family/args (resolve turns these into diagnostics)
```

- Cell naming: files `a..p` left-to-right, ranks `1..16` bottom-up, name = file+rank; member order row-major from `a1` (`a1 b1 c1 a2 ...`). `lines(k)`: every length-`k` window of consecutive cells along all four alignments (rows, columns, both diagonal directions), deduplicated, in a deterministic order (sort by cell tuple); for `grid(3,3)`, `lines(3)` is exactly the 8 tic-tac-toe lines. `k` outside `1..max(w,h)` raises (loud, resolve-walled later at the call site for static `k`).

- [ ] **Step 1: Audit.** Domain = `BOARD_FAMILIES` x argument space x entry-integrity properties (cells unique and nonempty; every line a subset of cells; line members distinct; `len(cells) <= 256` so the domain cap can never be hit downstream ambush-style — grid bounds `1..16` guarantee it, assert in the entry constructor as a registry-guarantor backstop). Residual rows recorded: relations/regions/frames/jump-triples fields deliberately absent from `BoardEntry` until their witnesses (breakthrough: relations+frames+regions; draughts: jump triples) — roadmap lines, not empty fields (an unread field would be dead data wearing a completeness pin).
- [ ] **Step 2: Failing tests**: grid(3,3) cells exactly the 9 names in order; lines(3) == the 8 known lines (explicit fixture list); a parametrized integrity sweep over several grids (1x1, 2x5, 16x16): uniqueness, subset, count formula `rows*max(0,w-k+1)... `(assert against an independently computed count); bad args (`grid(0,3)`, `grid(17,3)`, arity 1, arity 3) raise ValueError with messages naming the bounds.
- [ ] **Step 3: Implement + run + mypy. Commit** `feat: BOARDS registry — the grid family with integrity-pinned cells and lines`

### Task 6: `board:` clause — named-member position domains end to end

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (game_item `board: "board" ":" NAME ["(" INT ("," INT)* ")"]`)
- Modify: `cardlang/parse.py` (builder + `once("board:")`), `cardlang/ast/nodes.py` (`BoardDecl(family, args, span)`, `Game.board: BoardDecl | None`; `PositionDecl` grows named-member support: `members_named: tuple[str, ...] | None = None`, `.members` returning named or integer range)
- Create: `cardlang/board_domains.py` — the ONE union function `position_domains_of(game) -> Mapping[str, tuple[int, ...] | tuple[str, ...]]` (declared `positions {}` + board-minted `cell`), consumed by BOTH `runtime/driver.py:68-74` and `openspiel/encoding.py:193-200` (replace their comprehensions; identical by construction)
- Modify: `cardlang/resolve.py` (`_resolve_board`: family/args validation via `board_entry`; mint `cell`; collision walls — board-vs-builtin via the existing `taken` set, board-vs-`positions{}` name; `board:` requires `pieces:`; `cards:` + `board:` rejected-until-witnessed; zone index/type-arg validation reads the union)
- Modify: `cardlang/types.py` (`TCell` in the `Type` union — mypy's `assert_never` dispatches then force every consumer arm), `cardlang/typecheck.py` (named-domain members/params/subscripts type `TCell`; integer domains unchanged `TInteger`)
- Modify: `cardlang/domains.py` (`DomainSources.positions` widens to `Mapping[str, Sequence[int] | Sequence[str]]`), `cardlang/ir.py` (`_position` emits members list for named domains; integer form unchanged byte-for-byte), `cardlang/runtime/state.py` (str zone keys — follow mypy), `cardlang/runtime/driver.py` (store `rs.board = board_entry(...)` for the query verbs; `rs.position_domains` via the union function)
- Tests: `tests/test_board_clause.py` (new), rejection fixtures

**Interfaces:**
- Consumes: `board_entry` (Task 5), flavor stamp (Task 2).
- Produces: a game with `board: grid(3, 3)` + `pieces:` has position domain `cell` = the 9 named members; `square[cell] : Cell<cell>` declares a 9-instance family (runtime keys `"a1"`...); `move_type place(at : cell)` enumerates 9 vocab combos in member order with fixed adapter ids; `zone_observer_key` returns None (unowned — inherited, because the union feeds `rs.position_domains`); `at` types as `TCell` in guards/effects; `square[at]` subscript legal, `square[7]` a type error in a named-domain family.

- [ ] **Step 1: Audit.** Cells: grammar (arg list shapes, missing parens, zero args) x parse x resolve (unknown family, bad arity/bounds, `board:` without `pieces:`, `board:` + `cards:`, name collision with `positions { cell : 1..9 }`, duplicate `board:`) x typecheck (TCell vs TInteger subscript/param/comparison cells — `at is 3` rejected, `at is at2` legal, `square[0]` rejected in TTT but `tableau_up[3]` still legal in Klondike) x IR x runtime x encoding. Pairwise: TCell values x every operation consuming values (comparison, subscript, state assignment — position-typed state stays walled via `KNOWN_TYPE_NAMES`, probe it; `let c = at` typed-let carrying TCell — legal, probe it typechecks; movement endpoints). Probes as rejection fixtures: `board_without_pieces`, `board_with_cards`, `board_unknown_family`, `board_bad_args`, `board_collides_with_positions`, `board_cell_state_var` (position-typed state still rejected), `board_integer_subscript`.
- [ ] **Step 2: Failing tests** in `tests/test_board_clause.py`: a minimal board game source (the Task 3 piece game + `board: grid(3, 3)` + `square[cell] : Cell<cell>` + `place(at : cell)`) — parse/resolve/typecheck clean; `position_domains_of` returns the union with the 9 names; driver instantiates 9 zone instances keyed by name; `enumerate_domain("cell", sources)` yields the 9 members in order; the adapter action space mints 9 vocab ids for `place` and `space.decode`/`encode` round-trip; the rejection fixtures.
- [ ] **Step 3: Implement, following mypy's forced sweep** (widening `DomainSources.positions` and adding `TCell` will surface every consumer arm — resolve each by implementing or delegating to the named/int fork; no `type: ignore`).
- [ ] **Step 4: Full gates + byte-identity** (Klondike/FreeCell IR and playouts untouched — integer path preserved). **Commit** `feat: board: clause — named-member position domains through the landed positions substrate`

### Task 7: Cell and line queries (the quantifier wall-lift + `lines(k)`)

**Files:**
- Modify: `cardlang/grammar/cardlang.lark` (generic position-domain quantifiers + collection forms; keep keyword forms first: `quantifier: ... | "any" NAME "where" expr -> q_any_domain | "all" NAME "where" expr -> q_all_domain | "number" "of" NAME "where" expr -> q_count_domain | "any" NAME "in" expr "where" expr -> q_any_in | "all" NAME "in" expr "where" expr -> q_all_in`)
- Modify: `cardlang/parse.py`, `cardlang/ast/nodes.py` (new nodes or a generalized `DomainQuery(kind, noun, source: Expr | None, pred)`)
- Modify: `cardlang/resolve.py` (noun validation: bare forms — singular noun in `position_domains_of` for `any`/`number of`, plural = member+`s` for `all`, with diagnostics naming the declared domains; binder registration = the singular noun; collection forms — noun in {`cell`,`line`} at rung 1, others rejected naming the witness rule)
- Modify: `cardlang/typecheck.py` (binder types: bare-form binder = domain member type (TCell / TInteger); `line` binder = `TLine`; `any line in <expr>` demands `TCollection(TLine())`-typed source; `all cells in <expr>` demands `TLine()` source), `cardlang/types.py` (`TLine`)
- Modify: `cardlang/runtime/evaluate.py` (evaluation: bare forms enumerate `rs.position_domains[noun]`; collection forms iterate the evaluated source; binder bound by noun)
- Modify: `cardlang/stdlib/functions.py` + `cardlang/stdlib/signatures.py` + `cardlang/runtime/stdlib.py` (the three tables): `lines` — `Sig((TInteger(),), TCollection(TLine()))`, runtime arm reads `ctx.rs.board.lines(k)` with a typed refusal naming `board:` when the game declares no board; resolve wall: `lines(...)` in a boardless game is a static diagnostic (BOARD_ONLY_CALL_FUNCS, the deck-only classification's board twin, pinned in the same classification test)
- Modify: `cardlang/ir.py` (emit the new node kinds)
- Tests: `tests/test_cell_queries.py` (new; ledger), rejection fixtures

**Interfaces:**
- Consumes: `TCell`, `rs.board`, `position_domains_of` (Task 6).
- Produces (all proven on inline sources): `any cell where square[cell] is empty`, `all cells where square[cell] is not empty`, `number of cells where <pred>`, `any line in lines(3) where <pred-with-line>`, `all cells in line where <pred-with-cell>`; and the lift applies to integer domains too (`any column where cascade[column] is empty` legal in a FreeCell-shaped source — one mechanism, both member kinds).

- [ ] **Step 1: Audit.** The grammar-ambiguity axis is load-bearing: the generic `NAME` alternatives must not capture the keyword forms (`player`, `suit`, ...) or the card forms — run `tests/test_grammar_ambiguity.py`'s method over the new productions and add explicit precedence tests. Misuse probes: `any cel where` (typo — unknown domain, names declared ones), `all cell where` (missing plural — diagnostic says `all cells`), `any cell where` in a boardless+positionless game, `any cell in lines(3) where` (noun/element mismatch: lines(3) elements are lines), `all cells in square[a1] where` (source is a zone, not a line), `lines(3)` in a boardless game, `lines(99)` static out-of-range (resolve wall for literal k; runtime refusal backstop), binder escape (`cell` referenced outside the quantifier), nested-binder shadowing (`any line in lines(3) where any line in ...` — the inner rebind: follow the existing binder-shadowing rule and pin whichever way it lands). Bare-form quantifiers over `suit`/`rank` in a piece game are already walled by Task 3 — cross-reference, don't re-wall (backstop comment names the wall).
- [ ] **Step 2: Failing tests** (typecheck + runtime evaluation on a 3x3 fixture game: place three x marks along `a1 b1 c1` by scripted history, assert the win predicate flips true; assert `all cells where ...` counts correctly on partial boards; rejection fixtures).
- [ ] **Step 3: Implement; full gates + byte-identity. Commit** `feat: cell/line query register — the position-quantifier wall lift, with lines(k)`

### Task 8: The tic-tac-toe corpus game

**Files:**
- Create: `docs/games/tic-tac-toe.cardlang`, `docs/games/tic-tac-toe.md` (readable twin, candidates-entry pin: 2 players, 3x3, X first, three-in-a-line wins, full board draws; oracle note)
- Modify: `docs/games/_candidates.md` (graduate the tic-tac-toe entry: remove its section, leave the ladder intro pointing at the corpus file)
- Test: `tests/test_playout_tic_tac_toe.py` (new)

**Interfaces:**
- Consumes: every prior task. Produces: `cardlang_tic_tac_toe` auto-registered (glob), typechecking clean, playable.

- [ ] **Step 1: Write the game** — `docs/games/tic-tac-toe.cardlang`:

```text
// Tic-tac-toe — 2 players, grid(3,3), 5 X marks + 4 O marks. Variant pinned:
// X (player 0) moves first; players alternate placing one mark on an empty
// cell; three own marks in a line win at once; a full board with no line is
// a draw. Rules are common knowledge; the differential oracle is OpenSpiel's
// native `tic_tac_toe` (tests/test_differential_tic_tac_toe.py).
//
// This is the corpus witness for BOARD TOPOLOGY stage 1-2 (decisions.md
// "Boards"; design-notes/board-topology.md): the board declaration, the
// named-member `cell` domain, cell-indexed Cell zones, the placement
// vocabulary, declared lines, `turns` on a board, and draw-on-full-board.
// Perfect information throughout — every zone projects identity to all, so
// information sets are singletons and the observation model does not move.
//
// The result is encoded as result[player] in {+1, 0, -1} (win/draw/loss)
// so the OpenSpiel returns match the native oracle's utility structure —
// a draw must beat a loss.

game TicTacToe {

  players: 2
  direction: clockwise
  max_length: 30

  board: grid(3, 3)
  pieces: xo_marks

  zones {
    box             : Deck                // the unplaced set before setup (empties at once)
    square[cell]    : Cell<cell>          // the nine board squares
    reserve[player] : PlayerPile<player>  // each side's unplaced marks, public
  }

  state {
    result[player] : Integer = 0    // +1 win, -1 loss, 0 running or draw
  }

  phase setup {
    move all pieces from box where piece.side is x to reserve[0]
    move all pieces from box to reserve[1]
  }

  phase play {
    turns t from 0 over all players
          until (any player where result[player] is 1)
                or (all cells where square[cell] is not empty) {
      offer to t one of [place]
    }
  }

  winner: highest result
}

// Place one of your marks on an empty square. Completing a line of your own
// marks decides the game on the spot: the just-placed mark's side is the
// actor's side by construction, so the line test compares against it and no
// player-to-side mapping is needed.
move_type place(at : cell) {
  when: square[at] is empty
  effect {
    move one piece from reserve[actor] to square[at]
    if any line in lines(3)
         where all cells in line
           where (square[cell] is not empty)
                 and (top_of(square[cell]).side is top_of(square[at]).side) {
      let w = actor
      for each player p {
        if p is w { result[p] := 1 } else { result[p] := -1 }
      }
    }
  }
}
```

  If the implementation of any spelling differs from what Tasks 2-7 landed (for example the assign-target or `for each player` fallback details), adjust the game to the landed surface — the game file is the witness, and Tasks 2-7's tests are the spec of record. `tic-tac-toe.md` carries the same source in a fenced block plus the prose rules (a non-player must be able to play a game from it) — follow `docs/games/klondike.md`'s twin structure.
- [ ] **Step 2: Corpus docking** — run the corpus-wide suites and fix ripples: `tests/test_typecheck_corpus.py` (glob picks it up), `tests/openspiel_ready/test_coverage.py` will now DEMAND a proof module (red until Task 10 — sequence Tasks 8-10 in one push to keep the tree green, or add the proof module stub in the same commit), fuzz grid grows to 19 games (`tests/fuzz/test_fuzz.py` — no EXCUSED changes expected; if a mutant surfaces a genuine new finding, record it properly instead of excusing it), ranking-conventions matrix unaffected (piece sets are outside the `DECKS` view — assert by running it).
- [ ] **Step 3: Playout test** `tests/test_playout_tic_tac_toe.py`: random-chooser playouts over 100 seeds asserting per-decision invariants (alternation until terminal, every placement lands on a previously empty cell, decision count <= 9, terminal `result` in {(1,-1),(-1,1),(0,0)}, reserves+board conserve 9 marks) plus one exact-seed characterization (hash-independence verified in-process: the candidate list orders by the declared member order, not set order — assert the same final board across two in-process runs and pin it).
- [ ] **Step 4: Full gates. Commit** `feat: tic-tac-toe — the board-topology walking skeleton enters the corpus`

### Task 9: Native-oracle differential (the reusable walker + TTT instance)

**Files:**
- Create: `tests/native_oracle.py` (the reusable alternating perfect-information paired walker)
- Create: `tests/test_differential_tic_tac_toe.py`
- Do NOT modify `tests/test_differential_gops.py` (its docstring already isolates its GOPS-specific pieces; the walker's docstring records why GOPS stays bespoke — simultaneous moves + chance-following — and that backgammon's chance rung is the walker's planned extension point)

**Interfaces:**
- Produces: `walk_paired_alternating(dsl_path, native_game: str, to_native: Callable[[decoded-action], int], seed, policy_seed, *, expected_first_player=0) -> tuple[list[float], list[float]]` — at every DSL Pause: assert native not chance/simultaneous, current players agree, mapped legal-action SETS agree exactly; apply the same (policy-chosen) action to both; at DSL Terminal: assert native terminal too, return both returns. Plus `assert_outcomes_agree(ours, native)` comparing induced outcome (win/loss/draw classification), since return SCALES may legitimately differ between a DSL scoring convention and a native one; TTT's instance additionally asserts exact numeric equality (`result` was designed to match +1/-1/0).
- TTT mapping: `to_native(("place", cell)) = (3 - int(cell[1:])) * 3 + "abc".index(cell[0])` (native rows count from the top; our ranks from the bottom).

- [ ] **Step 1: Write the failing differential** with three coverage layers, coverage recorded in the module docstring (the coverage-record obligation):
  1. **Exhaustive prefix walk to depth 4**: DFS over OUR legal actions from the empty board (3024 leaf prefixes), comparing mapped legal sets with native at every node.
  2. **Scripted line coverage**: for each of the 8 lines, a constructed history where X completes exactly that line — paired walk asserts native reports the same terminal + returns `[1,-1]`; plus one scripted O-win and one scripted draw (returns `[0,0]`, full board).
  3. **Random full trajectories**: 200 policy seeds walked to terminal, exact returns equality asserted, and the sample must contain X wins, O wins, and draws (assert all three arose — the GOPS both-branches discipline).
- [ ] **Step 2: Run** (`pytest tests/test_differential_tic_tac_toe.py -q`) — it must FAIL before Task 8's game exists and PASS after; on divergence the assertion carries seed/step/board witness. Budget check: the whole module must run in well under 60s (measure; if the depth-4 walk is slow because replay is O(n^2), drop to depth 3 (504 prefixes) and record the reduction in the docstring — never silently).
- [ ] **Step 3: Commit** `test: native-oracle differential for tic-tac-toe over a reusable alternating walker`

### Task 10: The `openspiel_ready` proof module

**Files:**
- Create: `tests/openspiel_ready/test_tic_tac_toe.py`

**Interfaces:**
- Consumes: `ReadinessProofs`, `GameSpec`, `partition` helpers (`zone_instances`, `projection_for`, `record`, `first_divergence`).

- [ ] **Step 1: Write the module** — `class TestReadiness(ReadinessProofs)` with `spec = GameSpec("cardlang_tic_tac_toe", "tic-tac-toe.cardlang", hidden_zone="reserve", depth=4, swap_axis="any", adapter_terminal_steps=<measured greedy line + slack>)` and the two-player perfect-information overrides, FreeCell's honest-degeneracy pattern extended to BOTH observers:
  - `test_indistinguishability_under_hidden_swap` override: at a replayed pause, for EACH player: no populated zone projects below identity to them (`hidden_cards == 0`), every piece identity appears in their rendered information state, and both players' info sets are singletons; `record(...)` with `degenerate="perfect information — no hidden pair exists for either observer"`.
  - `test_soundness_own_view_changes_the_state` override: swap two visible pieces (a placed mark and a reserve mark of the other side, mid-line) and assert BOTH observers' information states change.
  - Inherited proofs run as-is: per-visible-fact matrix (the load-bearing one — every zone x both observers at identity, every perturbation must move the state), seed/rng non-observability, perfect recall, adapter agreement to Terminal with returns equality, pyspiel conformance.
  - Two dedicated tests: (1) `test_placements_are_public_identity_events` — every `move` event in both logs carries full piece identity and both logs agree on the board-directed events (common knowledge pinned at the event level); (2) `test_no_shuffle_means_seed_degeneracy` — for 3 different seeds, the information states of both players at every step of the same action history are byte-identical (a shuffle-free game is seed-independent; the module docstring records the honest caveat that the adapter's root chance node still samples seeds and every branch is provably identical — the stage-3 chance workstream owns collapsing it, roadmap line in Task 11).
- [ ] **Step 2: Run the full openspiel_ready suite** (`pytest tests/openspiel_ready/ -q`): the new module green, `test_coverage.py` green (module name matches the registry), all 18 card-game modules untouched and green.
- [ ] **Step 3: Commit** `test: tic-tac-toe readiness proofs — two-observer perfect-information degeneracy, adapter + conformance + returns`

### Task 11: Docs promotion + walls bookkeeping

**Files:**
- Modify: `docs/decisions.md` (new sections in spec voice: "Boards and cells" — the board declaration, minted named-member domains, cell typing, the query register; "Component sets: cards and pieces" — flavor, axes, noun agreement, seeding rule; "Zone capacity"; cross-reference from "Position domains and positional zones")
- Modify: `docs/model.md` (the content table: Piece is the individuated base kind, Card its deck specialization — rewrite the "canonical individuated content" row)
- Modify: `docs/library.md` (catalogue: BOARDS families + entries, component sets incl. xo_marks composition, capacity column in the zone-type table, `lines(k)` in stdlib functions)
- Modify: `docs/roadmap.md` (update "Positional zones — walled residuals": quantifier cell is now LIVE (remove that residual, keep `for each <position>` + position-typed state); add board-topology residuals: direction domains (witness: breakthrough), `Point` + `HiddenCell` rows, double-index families, cell literals in expressions, piece-query grammar forms, collection-noun quantifiers beyond cell/line, in-file board syntax, adapter root-chance collapse for chance-free games (stage 3))
- Modify: `docs/design-notes/board-topology.md` (§5: the surface-residue bullet points now settled move to a pointer at decisions.md; the ladder and stages 3-7 stay; rung 1 marked by its corpus file existing — no "DONE" markers, spec-not-history)
- Modify: `docs/design-notes/positional-zones.md` ("Adjacency" deferral: now points at the landed board mechanism in decisions.md)
- Check (no edit expected): `docs/kernel-migration.md` (no Python escape hatch was added — nothing to record), `docs/appendix.md` (stable reference table — do not update), `docs/open-questions/rule-scope-beyond-trick-play.md` + `structural-infoset-proofs.md` + `unbounded-lines-and-max-length.md` (untouched — their stages are later)

- [ ] **Step 1: Write the decisions.md sections** (follow the existing register: definitional prose + fenced examples + the walls stated as behavior, cross-references by section name). Every claim must match landed behavior — write them FROM the tests.
- [ ] **Step 2: Sweep the games**: no card game file changes (their surface is untouched — verify with `git diff docs/games/` showing only tic-tac-toe + _candidates.md).
- [ ] **Step 3: Run `tests/test_doc_snippets.py`** (decisions.md fenced blocks are pipeline-checked — new fragments need recipes if fenced as `cardlang-fragment`) and the full suite.
- [ ] **Step 4: Commit** `docs: promote rung-1 board topology into the spec (decisions/model/library/roadmap)`

### Task 12: Final gates + PR

- [ ] **Step 1: Re-run the surface-totality audit ledgers** (Step 4 of the skill): every ledger's residual rows have walls + roadmap lines; confirm no ledger's domain rows were read off its implementation.
- [ ] **Step 2: Full local CI**: `.venv/bin/mypy` (bare) and `.venv/bin/python -m pytest -q` from the worktree root with `PYTHONPATH` set — both green, run as written, no subsetting.
- [ ] **Step 3: Repo review pass**: run the `cardlang-code-review` skill over the branch diff; fix or explicitly answer every finding.
- [ ] **Step 4: Push + PR** onto `main` titled "Board topology rung 1: tic-tac-toe against stages 1-2" — body: the stage-1/2 scope, the info-set acceptance evidence (byte-identical corpus, proof module, differential), the completeness ledgers' locations, the recorded residuals, and the note that rung 2 (breakthrough) is next per the ladder.

## Execution notes for the orchestrator

- Task order is the dependency order; Tasks 8-10 land as one green push (test_coverage.py couples the game file to its proof module).
- Tasks 1-4 are the byte-identity-critical stretch: run the 8 IR goldens + full suite after EACH, not just at the end.
- Each implementer subagent gets: this plan's task text, the relevant explorer facts (file:line anchors are in the task), and the instruction to read the owning pass's `Contract` docstring before placing any check (CLAUDE.md write-time triage).
- If any landed surface diverges from the plan's sketches (spellings, exact messages), the tests + audit artifacts are the spec of record; update the plan file inline when that happens so later tasks read the truth.
