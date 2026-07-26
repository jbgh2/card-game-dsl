# Memoising the primitive reads bundle, and the wall that makes it sound

> **OUTCOME: implemented, reviewed three times, NOT SHIPPED (2026-07-25).**
> The measurement holds — 1163.69s -> 679.62s on the full suite, 1.71x, with
> byte-identical results — and one LIVE defect was found and fixed along the
> way (`shuffle <zone>` mutated a memoised zone without moving the version, in
> 17 of 33 games). What did not hold is the wall. Three review rounds each
> disproved claims the change made about its own completeness, the last one
> refuting the central "a NEW method cannot land unclassified" with a two-line
> plant (`classmethod` and `cached_property` are neither `callable` nor
> `property`, so `vars(cls)` filtering misses them).
>
> The conclusion is about METHOD, not effort: a syntactic scan cannot close
> "every present and future mutation site opts in", because Python has
> unbounded ways to reach a live reference. The behavioural suite cannot
> substitute — with a bump silently dropped from `Zone.add`, every playout
> comparison and three golden tests pass.
>
> The work is reverted; the diff and the grid module are preserved in the
> session scratchpad. Issue #83 carries the standing record and the
> two directions worth trying instead (provenance instrumentation as the wall;
> or scoping the memo to one candidate-enumeration pass). Everything below is
> the plan as written BEFORE that verdict — kept because the measurements and
> the design comparison are the durable part, and the rejected design B is
> worth not re-deriving.

Scoping for reusing `reads.game_reads`' frozen bundle while engine state is
unchanged. Written 2026-07-25 against `claude/test-suite-consolidation-8b7a3c`.

## Why: measured, whole-suite, green

A prototype memo took the full suite from **1163.69s to 686.20s — 1.70x, -41%**,
at `5088 passed, 7 skipped, 1 xfailed` both times (byte-identical counts). One
lever, no coverage change. Per game:

| game | today | memo | hit rate |
|---|---|---|---|
| canasta | 12.88s | 1.64s (**7.8x**) | 97.0% |
| french-tarot | 8.14s | 4.36s (1.87x) | 86.3% |
| skat | 1.00s | 0.45s (2.22x) | 74.6% |
| gin-rummy | 3.58s | 2.49s (1.44x) | 74.2% |

The hit rate is high because guards are called in BURSTS during legal-move
enumeration with no state change between — a one-entry cache nearly saturates.

**Read that 1.70x as "what the memo buys", not "what the finished change
measures".** It was taken with the memo and a bare version counter — no wall, no
`take_first`/`set_index` choke points. Those should not move the runtime, but
the wall's refusals may force small refactors, so the number to quote is the one
task 8 prints.

## Gate 1 — Owners

- **`cardlang/runtime/sidecar.py`, Contract.** Establishes "a game module
  receives values only — no engine handle crosses the boundary, so purity is
  structural". The memo does not weaken this: a cache hit returns the same
  frozen bundle a rebuild would.
- **`cardlang/runtime/reads.py`, Contract**, and `deep_freeze`'s docstring — the
  owner of what a bundle guarantees.
- **decisions.md, "Mutation semantics"** — "No transactional isolation, no
  copy-on-write, no implicit ordering tricks." A stale bundle IS an accidental
  copy-on-write, so this change must be *unobservable* to stay inside that
  decision rather than amending it.
- **decisions.md, "Closed-domain completeness"** — governs the wall below.
- **`docs/design-notes/primitive-sidecars.md`** is the neighbouring workstream.
  This is NOT stage 3: stage 3's per-primitive `reads` is a surface/correctness
  change measured at only **1.18x**, because the hot primitive
  (`canasta_add_ok`, 71% of calls) genuinely needs 13 of 22 names. The two are
  independent and compose.

### The new invariant, which has no current owner

`deep_freeze` establishes one direction: **a primitive cannot mutate engine
state through a handed value.** The memo needs the dual: **the engine cannot
mutate a bundle's source without the cache observing it.** Nothing in the repo
owns that today, because nothing needed it. Naming it is this change's real
work; the speedup is a consequence.

## Gate 2 — Classification

**Runtime machinery + a new wall + a closed-domain mechanism.** The
surface-totality audit **FIRES** — the wall's whole job is to close an
enumerable domain (the mutation surface reaching a bundle's source), which is
precisely what "Closed-domain completeness" governs.

## Gate 3 — Acceptance criteria

1. **Runs.** Every corpus game plays identically with the memo on.
2. **Regression-clean.** `mypy` (bare) + full `pytest -q`, goldens
   byte-identical. This change claims total behavioural neutrality, so any
   golden diff is a defect, not a regeneration.
3. **Info sets derive — unchanged.** The memo sits under the primitive boundary
   and must not touch observation emission. The readiness proofs' partition
   coverage record must come out byte-identical, which is the artifact that
   proves it.

**Corpus-lockstep list: empty.** No language surface moves; no file in
`docs/games/` changes. If one must, the change has exceeded its classification.

**Witness:** canasta is the witness for the burst pattern (97% hit rate, 22
declared names). A game with NO primitives (hearts) is the negative witness —
the memo must be inert there, not merely harmless.

## The design space, measured

### Design A — versioned containers + a global counter

Every engine-owned mutable container becomes a versioned type
(`VersionedList` for `Zone.cards`, `VersionedDict` for indexed state maps) that
bumps a counter on mutation. **Measured: 97.0% hit, 7.8x on canasta, whole
suite 1.70x.**

Soundness rests on enumerating every engine-owned mutable container. That is a
closed domain, but a wide one.

### Design B — bracket the statement executor (REJECTED, and why it matters)

No versioned containers at all: clear the memo before and after every
`execute()`, on the theory that statement execution is the only thing that
mutates zones and state variables. Simpler, and nearly as fast — **measured
95.7% hit, 7.09x on canasta, byte-identical results on five games.**

**It is unsound.** `mechanics.py` mutates zones *directly*, inside
`run_decision_round`, outside any `execute()` call:

- `mechanics.py:172-173` — the trick round: `zones.instance(source_family,
  actor).remove(choice)`, `zones.single(play_zone).add(choice)`
- `mechanics.py:550-551` — the climbing round: `self.hands[actor].remove(c)`,
  `self.pile.add_all(play.cards)`

**Record this: design B scored 95.7%, ran five games byte-identically, and is
wrong.** That is the concrete demonstration that green tests cannot back this
invariant — the same conclusion the full-suite run reached from the other side
(the first prototype ran the suite with a knowingly-unsound counter and produced
zero golden or score divergences). Any plan that proposes to validate the memo
by running the suite is proposing a vacuously green check.

### Design C — choke-point bump + a static wall (RECOMMENDED)

Keep design A's counter, but get its completeness from a **statically enforced
closed domain** rather than from having enumerated container types. Two
channels reach a bundle's source, and they are NOT equally tractable.

**Channel 1 — zone cards. Fully closable.** `.cards` is a distinctive
attribute, so an AST scan refusing its mutation outside `state.py` is direct
and reliable — same mechanism and currency as the existing scan in
`tests/test_primitive_reads.py`, which already polices name-keyed access in
these very modules. The declared mutator set becomes
`Zone.add/add_all/remove/take_all`, each bumping.

Two existing sites bypass it, and **neither can simply be "routed through" — no
`Zone` method does what they do**:

- `execute.py:209` — `card = source.cards.pop(0)` (take the first card)
- `execute.py:317-318` — `taken = source.cards[:count]; del source.cards[:count]`
  (take the first N)

`take_all` empties the zone and `remove` is by value, not position. So this
change **adds one method, `Zone.take_first(n)`**, and both sites use it
(`pop(0)` is `take_first(1)`). That is deliberate: the alternative — leaving
them as allowlisted exceptions — puts holes in the very scan whose value is
having none. One new method keeps the wall's allowlist empty.

**Channel 2 — state-variable values. Only partly closable; the rest is a named
residual.** An AST scan cannot generally distinguish `target[key] = v` on a
state value from the same shape on any local, because the value arrives as an
opaque local (`target = ctx.rs.get(name)`). What IS enforceable:

- Writes to a state *variable* go through `RuntimeState.set`/`declare` plus the
  one indexed-assignment site, which this change routes through a new
  `RuntimeState.set_index(name, key, value)` choke point that bumps.
- The wall then scans for the bypass shape: within a function, a name bound
  from `rs.get(...)` that is later subscript-assigned. That is intra-function
  and syntactic, so it is a real scan rather than a general dataflow problem.

**What it does NOT cover, recorded as residual:** mutation of something reached
*inside* a state value — `gr.state["contract"].fields[k] = ...` (a
`StructValue`), or a list held as a state value. `deep_freeze`'s docstring names
these as real channels. Closing them needs a distinguishable type at the
boundary (a `VersionedDict`, i.e. design A) and is deliberately out of scope.

### A or C?

**C wins only if channel 1's scan comes out clean**, and after channel 2 reduces
to a residual the two designs differ mainly in whether `Zone.cards` is a
versioned type or a scanned attribute. A needs no `take_first` (a versioned list
catches the slice-take as-is); C needs no new container type and keeps `Zone`
ordinary. **The state-value channel is a residual either way** — that is the
honest comparison, and it is why the recommendation is C-by-a-margin rather than
C-obviously.

### Two prototype traps, both hit, both to be pinned as tests

- **Do not hang the memo off `RuntimeState`.** That puts `MappingProxyType` into
  the state's attribute graph, and `pyspiel.random_sim_test` deepcopies the
  state: `TypeError: cannot pickle 'mappingproxy'`, five conformance failures.
  Use a module-level `WeakKeyDictionary` keyed by the state.
- **The bracket direction is silent when wrong.** Clearing only on entry to
  `execute` leaves `_repeat_until`'s condition reading a stale bundle
  (`canasta: the discard pile is empty` — a *lucky* loud failure; the same
  mistake elsewhere is silent).

## Gate 4 — The grid (task 1, authored red)

**Domain:** the mutation surface reaching a bundle's source, **derived in code**
by AST scan over `cardlang/` — every call to a `Zone` mutator, every direct
`.cards` mutation, every `RuntimeState` write, every in-place indexed write.
Never a hand-written list, so a new mutation site cannot land uncovered.

**Property per site:** performing that mutation changes the version, i.e. a
bundle built before it is not reused after it.

**Cells and their expected outcomes, authored before the implementation:** each
discovered site is either (a) routed through a bumping choke point, or (b)
refused by the wall. There is no third column — a site that is neither is the
red set.

**The behavioural grid** is the second axis: per `registry.GAMES` game, playouts
with the memo on and off agree on scores, winner and hands_played. Note
explicitly that this grid **cannot** be the completeness evidence — design B
passes it and is wrong. It is a regression check riding alongside the wall.

**Born-green risk:** most sites pass the moment the bump lands. Each names its
reddening mutation — delete one bump, delete the wall's scan entry, revert one
`execute.py` site to direct `.cards` mutation — and the grid must go red.

**Named residual:** `EngineFacts` (round/mech state) is NOT memoised by this
change and keeps being rebuilt per call (~6.4us of a ~93.9us bind). So
`facts.round_state["played"].append(...)`, which `deep_freeze`'s docstring
names, is out of this change's domain. Record it on issue #83 rather than
leaving it implied.

## Task list — every step names its proving artifact

1. **Grid, red.** The AST-derived mutation-site scan with expected outcomes
   authored first. *Artifact:* the grid module, red (it names a version counter
   that does not exist).
2. **Add `Zone.take_first(n)`** and move `execute.py:209` and
   `execute.py:317-318` onto it. Not a pure refactor — it is new surface on
   `Zone`, chosen so the wall's allowlist stays empty. *Artifact:* goldens
   byte-identical; those grid rows green.
3. **Add `RuntimeState.set_index(name, key, value)`** and move `_assign`'s
   indexed branch onto it. *Artifact:* goldens byte-identical; the indexed-write
   grid row green.
4. **The wall, in two parts with different strengths.** (a) AST scan refusing
   `.cards` mutation outside `state.py` — the complete half. (b) AST scan
   refusing subscript-assignment to a name bound from `rs.get(...)` within a
   function — the narrow half. *Artifact:* misuse probes, one per refused shape,
   each proven to fail in the scan's currency, with the red-under verified to
   fail for THIS wall and not a neighbour. The residual (mutation *inside* a
   state value) is recorded, not scanned.
5. **The version counter** at the declared choke points. *Artifact:* the grid's
   per-site rows green.
6. **The memo**, in a `WeakKeyDictionary` keyed by the RuntimeState. *Artifact:*
   a deepcopy test over a registered pyspiel state (the mappingproxy trap), plus
   the memo-on/memo-off behavioural grid.
7. **The inert-game pin.** A game with no primitives (hearts) must build no memo
   entries. *Artifact:* an assertion on memo size, so the fast path cannot
   silently become universal.
8. **Re-measure.** Full `pytest -q`; report the printed number.
9. **Record the residuals** on issue #83 — `EngineFacts`, and mutation reached
   *inside* a state value. *Artifact:* the entries.

## Relationship to the other levers

Independent and composable, in recommended order:

1. **This memo** — 1.70x whole suite, measured, no immutability trade.
2. **`Card` as an atomic leaf** — composes on top (canasta 7.8x -> 9.9x), but
   swaps a runtime guarantee for a static one; its own decision.
3. **Sidecar stage 3** — 1.18x; do it for its surface/correctness reasons, not
   for speed.
4. **The resumable adapter**
   (`2026-07-25-openspiel-walk-api.md`) — this memo shrinks the constant its
   O(n^2) multiplies, so it should be re-measured after this lands.
