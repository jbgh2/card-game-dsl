# OpenSpiel projection substrate + general adapter — design

*Sub-project 1 of the info-set-leak closure (design-notes/kernel-extensibility.md
§6, §9 step 4). Approved scope: substrate + ungated Python-mechanic removals;
the removals are follow-on sub-projects, each its own spec → plan → build.*

## Goal

Close the information-set leak for every fully-kernel game and **prove it
closed**: each game loads as a `pyspiel.Game` whose information states are
**derived** from declared zone visibility plus emitted observation events —
no per-game observation rules, no per-game info-state function, no per-game
action table. This is the GDL-II `sees` semantics made operational
(decisions.md "Knowledge, visibility, and the projection model") and the
delivery of the project's load-bearing requirement (CLAUDE.md).

The substrate is also the foundation of the long-term design-tool goal: a
designer writes zone declarations and rules, and gets an AI-playable OpenSpiel
game — playouts, statistics, and a per-player observation stream suitable for
feedback to a human designer or a supporting LLM — with zero adapter code.

## Scope

**Proven in this sub-project (the six fully-kernel games):** Hearts, Getaway,
Spades, Bridge, Oh Hell, Big Two. Big Two is included deliberately as the
action-encoding forcing function: climb decisions are multi-card combinations,
the case the current 52-card action space cannot encode at all.

**Excluded, honestly:** the eight `instantiate` games (Schnapsen, Pinochle,
Skat, Tarot, Cribbage, Stud, Tichu, Coup). Their Python phases emit no
observations, so their info sets cannot be derived until those mechanics
migrate onto the kernel (sub-projects 2+, per kernel-migration.md). A game
with any `instantiate` statement is rejected by the general adapter with a
clear "info-set debt" error, not silently mis-modeled.

**Behavior-preserving:** observation emission adds no chooser draws and no
RNG. All existing goldens pass unchanged under `PYTHONHASHSEED=0`.

## Current state (what this replaces)

Exactly one game reaches OpenSpiel today, through three Hearts-specific
hardcodings:

- `cardlang/openspiel/replay.py` classifies every chooser pick by raw count
  (`kind = "pass" if n > 1 else "play"`) — a Hearts convention.
- `cardlang/openspiel/infostate.py` keeps a logged action iff
  `kind == "play" or pl == player` — a second Hearts convention; its own
  docstring says the rules are Hearts-specific.
- `cardlang/openspiel/encoding.py` hardcodes a 52-card single-card action
  space (`NUM_DISTINCT_ACTIONS = 52`).

The projection model itself (the six-projection lattice, per-observer zone
visibility) is fully specified in decisions.md and carried by the library zone
types in library.md, but nothing in the runtime reads it: `stdlib/zones.py`
records only `takes_owner`, `ZoneStore` drops the declared type, and the only
event channel is the debug `Ctx.trace`.

What is kept: the `(seed, history)` re-simulation engine (`replay.run`) — the
OpenSpiel state is two values, cloning is trivial, and every query re-runs the
game deterministically. Its cost (every query re-simulates the prefix) is an
accepted trade-off for this sub-project; incremental state or caching is an
orthogonal later optimization nothing here blocks.

## Architecture: two pillars over the re-sim engine

### Pillar 1 — derived observations

**The library-type → projection table becomes data.** The per-observer
compositions already specified prose-side in library.md ("Library zone types")
are recorded in `cardlang/stdlib/zones.py` next to `takes_owner`:

| Library type | Projection map |
|---|---|
| `Hand<O>`, `SharedHand<G>` | `identity` to owner/group, `count_only` to others |
| `PublicHand<O>`, `Discard`, `PlayerPile<O>`, `TeamPile<G>`, `TrickPile` | `identity` to all |
| `Deck`, `FaceDownPile`, `RandomizedPile` | `count_only` to all |
| `Muck`, `Burn` | `trivial` to all |
| `ChipStack<O>` | `count_only` to all |

The corpus exercises only `identity` / `count_only` / `trivial`; the remaining
lattice levels (`identity_set`, `count_by_type`, `existence_only`) are defined
by the table's type but need no emission logic until a game uses them. No
grammar change: the `composition:` zone-declaration syntax from decisions.md
stays future surface; games already carry the projections through their
declared library types. (`Zone<Card>`-style raw declarations, if any appear,
require an explicit entry — the builder fails loudly on a type with no
projection map.)

**`ZoneStore` retains the declared type.** `ZoneDecl.type_ref` currently
drops at construction; the store keeps `zone_type: dict[str, str]` (zone name
→ library type name) so the emitter can look up any zone's projection map at
runtime.

**A new `Ctx.observer` channel** — a sibling of `tracer`, default `None`, so
normal playouts pay nothing. When installed, the runtime emits **per-observer
observation events**:

- **Movements** (`deal`, `move`, the trick/climb card movements inside
  `apply`): each observer sees the transfer through the source and
  destination projections (decisions.md "Observation events"). Identity on
  both sides ⇒ the full card move; identity on one side only ⇒ the weaker
  fact (`+1 card` / `−1 card`); trivial ⇒ nothing. Deals become
  per-recipient-private automatically: destination `Hand<p>` is identity only
  to `p`.
- **Vocabulary decisions** (the interpreter's canonical
  `("decision", (actor, choice))` event — §9 step 4's first move, safe under
  the recorded invariant that every tracer test filters by event name): a bid
  / bet / pass / climb-pass is a public announcement — all players observe
  `(actor, move, value)`. Card-choice decisions carry no separate content
  event for *other* players; what others learn of them is exactly what the
  resulting movement reveals through zone projections. Additionally, **every
  actor observes their own choice at the moment of the draw** (an actor-only
  `chose` event) — this is what carries perfect recall of one's own decisions
  when the resulting movement is deferred or hidden (the simultaneous pass:
  cards are selected before any transfer applies).
- **`EachSimultaneous`** (Hearts's pass): each actor observes their own
  selection at identity; others observe only the movement counts, and no
  cross-player ordering is emitted (the "observers cannot infer any ordering"
  contract, decisions.md "Simultaneous moves").
- **Shuffles / chance**: no observation beyond what subsequent projected
  movements reveal. The root seed is never observable.

**State variables are public.** The projection model governs zones; declared
`state` variables (scores, bids, trump, pass direction) have no visibility
declaration and are readable by every player — in this DSL, hidden
information lives only in zones. The corpus confirms the rule (bids, scores,
and betting state are public announcements in every game); `choose` results
assigned to state are therefore public decisions. If a future game needs a
concealed scalar, it must be modeled as a zone (or the rule revisited then).

**Information state = pure function of (projected zones now, observation log
so far).** One general

```
information_state(player, rs, obs_log) -> str
```

replaces `hearts_information_state`: the player's projected view of every
zone (own hand fully; public piles fully; hidden zones as counts), all public
state variables, plus the player's accumulated event log. The log carries perfect recall — `Muck`
is trivial *going forward* while prior observations persist, exactly the
projection-vs-log distinction. Getaway's `RandomizedPile` works the same way:
entry movements were publicly observed (log), contents thereafter are
count-only (projection). The string stays human/LLM-readable (readable card
names and move names, stable field order), because the observation stream is
also the design-tool feedback artifact — see "Design-tool alignment."

### Pillar 2 — derived action encoding

The per-game **global action universe** is derived from the IR, as the
disjoint union (with offsets, canonically ordered) of the game's decision
domains:

- **Cards** — the 52-card space (`suit_index * 13 + rank_index`), used by
  trick plays, chosen movements, and the simultaneous pass (which stays
  decomposed into sequential single-card actions, as today).
- **Move vocabulary** — every `move_type` reachable from a `round offering`
  or `offer`, nullary moves as one action each, parameterized moves flattened
  over `_enumerate_domain` in declared order.
- **`choose` ranges** — integer/domain choose-expressions (Spades/Oh Hell
  bids), one action per value.
- **Combinations** (the forcing function) — the universe comes from a third
  game-local engine query, `universe()`, registered in the stdlib beside
  `combinations`/`follows` and keyed by the same name: every play the engine
  can ever emit, unique by card-set. (Running the lead query over the full
  deck — the obvious derivation — is *unsound* for representative-based
  engines: Big Two's `_combos` offers only the top-suits representative per
  rank, so a full-deck enumeration omits reachable plays like a ♦♣ pair whose
  hand holds no higher suits.) For Big Two this is 19,898 plays, enumerated
  by shape and verified by a property test: every `_combos(hand)` output over
  sampled hands is a member. Plus `pass`. Canonically ordered by
  (size, kind, card ids) and pinned by a golden so IDs are stable across
  seeds and versions.

**Why global IDs, not candidate-index:** determinization — a headline target
algorithm — replays the observed public history through *resampled* hidden
worlds. In a resampled world an opponent's candidate list differs, so
"candidate #i" silently denotes a different action; cross-world replay is
only sound when an action ID has the same meaning in every world. The current
Hearts adapter already relies on this property of card IDs; the universe
builder extends it to every decision kind.

The `universe()` query is also what keeps enumeration state-neutral: the
lead query is live game state (`ctx` — Big Two's opening-3♦ filter constrains
*legality*), while the universe is a static superset; per-state legality
still comes from the live queries at each decision. A superset is safe — the
one hard invariant is that each card-set appears at most once, so a recorded
action decodes to exactly one play.

## Components

1. **`cardlang/stdlib/zones.py`** — the projection table as data (per library
   type: observer-role → projection), alongside the existing `takes_owner`
   flag. Resolver behavior unchanged (it keeps checking the same names).
2. **Runtime observation emission** — `Ctx.observer` (default `None`) +
   emission at the kernel decision/movement sites: `run_decision_round` (the
   `decision` event + `apply`-site movements), `_movement`/`_select`,
   `_offer`, `_choose`, `_each_simultaneous`. Runtime-only; no grammar / AST
   / parser / IR / typecheck change; IR goldens unchanged.
3. **`cardlang/openspiel/encoding.py`** — `ActionSpace.for_game(ir, engine)`:
   the derived universe, `action_to_string`, `num_distinct_actions`, and the
   pinned combination-universe golden for Big Two.
4. **`cardlang/openspiel/infostate.py`** — the one general
   `information_state(player, rs, obs_log)`; the Hearts-specific function is
   deleted.
5. **`cardlang/openspiel/game.py` / `replay.py`** — `CardlangGame(path)`:
   player count, `GameInfo` bounds, and utilities read from the IR;
   `ReplayChooser` generalized to decode any action kind via the
   `ActionSpace` (the count-based `kind` classification is deleted); all six
   games registered (`cardlang_hearts`, `cardlang_getaway`, …). The
   4096-seed sampled chance root is kept and named as a known limitation — a
   *sampled* deal space, not the combinatorial deal; orthogonal to info-set
   correctness.
6. **Utilities are general-sum, unconditionally.** Returns are the game's
   true scores (sign-adjusted so higher is better for lowest-wins games),
   with team-keyed scores (Bridge, Spades) mapped to each player through
   the declared partnerships; every game is declared
   `GameType.Utility.GENERAL_SUM` (`cardlang/openspiel/game.py`) — true
   scores are the designer-facing signal, so no recentred `ZERO_SUM`
   variant is derived even where the true scores happen to sum to zero. An
   elimination (`loser:`) game has no scores — it returns `+1` per survivor
   and `-(n-1)` for the loser.
   Designer-facing statistics read true scores.
7. **Proof harness** — `tests/test_openspiel_ready.py`, parameterized over
   the six games (see next section), plus a small reusable playtest-report
   helper (games-length / branching / returns / per-seat stats) shared
   between the tests and future design-tool CLI.

## The proof — "OpenSpiel-ready," falsifiable, per game

1. **pyspiel conformance** — `pyspiel.random_sim_test` over several seeds
   (legal actions non-empty at every decision node, terminal returns, clone
   consistency).
2. **Indistinguishability (the leak-closure proof).** For each player P:
   replay a fixed history; construct a second world differing only in cards
   hidden from P (swap cards between two opponents' hands post-deal via a
   harness-level deal-injection hook on the replayed `RuntimeState` — a test
   fixture, not a language feature); replay the same action sequence; assert
   `information_state_string(P)` is **byte-identical** across the two worlds.
   The swapped cards must be ones the recorded history never moves (both
   opponents still hold them at the query point), so the replayed action
   sequence stays legal in both worlds. Soundness converse: perturb something
   P *can* see (a card in P's own hand / a public pile) and assert the string
   **differs** — the info state is not vacuously constant.
3. **Perfect recall** — along sampled playouts, each player's observation-log
   component is append-only (earlier observations are a prefix of later ones),
   the operational form of "candidate sets only narrow."
4. **Hearts regression** — the existing Hearts info-state test suite (hidden
   hands never leak, other players' pass picks hidden mid-pass, perfect
   recall, own-action distinction) is ported to run against the *derived*
   info states and must pass unchanged in meaning; then the bespoke
   `hearts_information_state` and count-based `kind` logic are deleted.
   (Those ported tests are the behavioral content the hand-authored rules
   encoded — the operational form of "at least as fine.")
5. **Byte-identity** — bare `mypy` clean; full `pytest -q` green under
   `PYTHONHASHSEED=0`; no existing golden changes.

## Design-tool alignment (long-term goal)

Three commitments in this design exist specifically for the
designer-plays-and-gets-feedback loop:

- **Derivation, not adapters**: a new `.cardlang` file with kernel-only
  constructs is OpenSpiel-playable with zero engine work — the property that
  makes the DSL a design tool rather than a compiler frontend for hand
  finishing.
- **The per-player observation log is a first-class, readable output** — the
  honest "what this player actually saw" stream for a human designer or an
  LLM player/analyst, non-leaking by construction.
- **The playtest-report helper** (component 7) is the seed of the design-tool
  CLI: run N playouts, report length / branching / score spread / seat
  advantage. The CLI itself is a follow-on, not this sub-project.

## Out of scope

- Observation/information-state **tensors** and OpenSpiel's factored
  observation strings (info-state strings only).
- The true combinatorial chance node (sampled 4096-seed root kept).
- The eight `instantiate` games (follow-on sub-projects; adapter rejects them
  loudly).
- `EachSimultaneous` as a true simultaneous OpenSpiel node (stays
  sequentialized under the documented observational-equivalence argument).
- Re-sim performance work (incremental state, caching).
- The design-tool CLI surface.

## Follow-on sub-projects (approved scope, each its own spec)

Ungated Python-mechanic removals onto the substrate, roughly in order of
increasing risk: Stud settlement, Cribbage, Pinochle rest, Tarot rest,
Schnapsen — each proving its game OpenSpiel-ready as it lands. Coup, Skat,
and Tichu remain flagged info-set debt pending their new-axis sign-offs.
