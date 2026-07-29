# The second family library: the smuggling family

Issue #143 item 1. Takes the `uses` tier to the smuggling family
(`experiments/green-lane/`), which forces the zone contract (#177) and its
predecessor (#176), and answers the question the item poses: does
parameterization keep riding on required state, or does the family need a
`with` clause?

## Gate 1 — the decision's owners

- settled: `docs/decisions.md` "Family libraries" (what a library holds, the
  no-override rule, "Parameterization rides on state and on procedure
  arguments, not on the import", Survey 2 over this very family).
- open: `docs/open-questions/variant-delta-syntax.md` — the file that says this
  item is the measurement it waits on.
- sequenced: issue #143 item 1; sub-issues #176, #177 (epic #181), #136, #138.
- witnessed: `experiments/green-lane/` (12 files), `docs/libraries/poker_betting.cardlang`.
- pass contracts read before planning around them: `resolve` (`_check_requires`,
  `_check_library_encapsulation`, `_library_slot_names`, `_LIBRARY_UNSWEPT`),
  `cardlang/libraries.py`.

## The survey, by execution

Normalized (comment- and whitespace-stripped) cross-file diff over all 12
files — 6 full, 6 mini:

| block | distinct bodies across 12 files |
|---|---|
| `zones { }` | **1** — byte-identical everywhere |
| `procedure smuggle_round()` | **1** — byte-identical everywhere |
| `move_type wave` | **1** — byte-identical everywhere |
| `state { }` | 4 — differ only by `tokens` default (1 mini / 2 full) and v2b's extra `pending` |
| `phase play` | 2 — v2b adds two escrow lines |
| `phase scoring` | 2 — v1/v4 drop the four `cleared` terms |
| `phase setup` | 4 — the hand filter (deck mix; mini vs full) |
| `move_type inspect` | **10** |

`inspect`'s ten bodies decompose into exactly three orthogonal deltas:

1. **the fine** — `4` / `5` / `2`: a per-GAME constant;
2. **the contraband predicate** — `rank_value >= 11` / `>= 12` /
   `is 5 or is 12`: a card predicate, not a constant;
3. **the bounty** — nothing / `tokens[merchant] += 1` / `pending[merchant] += 1`:
   an added STATEMENT.

## Gate 3 — acceptance criteria

1. **Runs.** All 12 green-lane files parse, check and play out through the
   converted library; the three poker games are untouched.
2. **Regression-clean.** `mypy` (bare) + full `pytest -q`; corpus goldens
   byte-identical; and — the neutrality claim this change actually makes — the
   playout trace of each of the 12 green-lane files is byte-identical before
   and after conversion, captured as a checked-in artifact.
3. **Info sets derive.** The import carries no information-set implication and
   this change must not create one. A *contracted* zone is the GAME's zone: it
   is declared in the game's own `zones { }` with the game's projection, and
   `ZONE_PROJECTIONS` is not consulted differently. The proof is criterion 2's
   trace equality, which covers observations per observer, not just legal
   actions.

**Corpus lockstep.** No corpus game changes: green-lane is deliberately not
corpus (`experiments/green-lane/DESIGN.md`). The lockstep list is instead the
12 experiment files plus the prose that describes the tier:
`docs/decisions.md` "Family libraries", `docs/open-questions/variant-delta-syntax.md`
(line 17 asserts the smuggling family already uses the tier — untrue today),
`cardlang/libraries.py` docstring, `resolve._check_requires` docstring (says
"all nine of `poker_betting`'s requirements"; it is seven).

**Witness question.** No corpus game exercises a zone contract and none will,
so the witness is the green-lane family itself — and it is currently reached by
no test at all. A CI test that binds the library against all 12 files is
therefore a plan step, not a hope.

## What the tree actually does today (probed, not read off the issues)

Two spikes against HEAD, before any change:

1. **#176 no longer reproduces as filed.** Its report is that a zone entry in
   `requires` parses and is then misread as state, surfacing as a game-side
   "does not declare" error. It does not: PR #172's reference-slot registry
   classifies `(n.RequireDecl, "type_name")` into the `type` namespace, so the
   entry is now refused in the LIBRARY's currency —

   > library '_probe' names the type 'Hand', which the library does not have —
   > … declare the type in the library, or keep this definition in the game

   The silent misread is closed. What survives is a misdirecting fix: `Hand` is
   a stdlib zone type and cannot be "declared in the library". The tracker lags
   the tree; #176 gets this on the record either way.

2. **The two walls contradict each other.** A library body naming a zone
   without contracting it is refused with

   > library 'smugglingspike' reads 'hand', which is neither in its `requires`
   > contract nor defined in the library — **add it to `requires { }`** if the
   > including game must declare it

   which is advice the other wall then refuses. Following either diagnostic
   lands on the other. That pair is the strongest argument for implementing
   #177 rather than walling #176: walling makes the contradiction permanent and
   writes it into the message.

## What execution found that no reading would have

Probed against HEAD, each with a runnable witness:

3. **Procedures do not compose.** `procedure 'a' runs procedure 'b'; a
   procedure may not invoke another (v1 — expansion is a single splice, not a
   call graph)`. This caps what a library can hold independently of any
   contract: a game procedure cannot call a library procedure, so the shared
   body must be reached from a PHASE, not from game-local procedure text.
4. A `move_type` effect CAN `run` a procedure, and a phase CAN call two
   procedures in sequence. So the working factoring is: `phase play` calls
   `run commit_shipment()` (library) then `run respond()` (game).
5. Both refactor shapes are **trace-neutral over 12 seeds** — identical
   observation streams, decision points and results.
6. `LIBRARY_ZONE_TYPES` and `KNOWN_TYPE_NAMES` are **disjoint** (16 and 9
   members, empty intersection), so classifying a contract entry state-vs-zone
   is derivable rather than authored. That disjointness becomes load-bearing
   and gets its own pin.
7. `zone_type` and `zone_type_arg` sit today in the set the tier declares
   UNREACHABLE from a library ("`zones { }` is a GAME clause the library
   grammar has no production for"). Giving `require_decl` a `type_ref` makes
   both reachable, and `test_every_reachable_reference_namespace_is_swept_or_excused`
   fires on it automatically — the class sweep is enforced, not remembered.
8. **Provided zones are not the answer, and that is settled by execution, not
   taste.** Every family zone is WRITTEN by game text — `hand` by `phase
   setup`, `cleared`/`seized` by the game-local `inspect`, `warehouse` by the
   game's auto-wave — and provided state is read-only to the game. So every
   zone here must be game-owned, which is exactly what a contract expresses.

### The `_LIBRARY_UNSWEPT` re-probe already has four named rows

Derived, not guessed — each is a recorded reason that leans on a library being
unable to name a zone, and this change removes that premise:

- **`zone_type`, `zone_type_arg`** — today in the set the header comment
  declares UNREACHABLE ("`zones { }` is a GAME clause the library grammar has
  no production for"). A `type_ref` in `require_decl` makes both reachable.
- **`index_domain`** — its excuse is that "a contract naming a position domain
  asks for a declaration the game is itself refused". True for STATE; **false
  for zones** — Klondike declares position-indexed zone families. So the zone
  leg needs its own answer, and the answer is a wall: a library cannot declare
  or name a position domain, so it cannot spell such a contract at all.
  Refused in the library's currency, with the residual recorded against a
  positional family library as its witness.
- **the ledger's `Movement.item` residual (R4)** — its stated reason is that
  "every movement also names a zone as an ordinary expression — so the
  classified pass refuses the statement before the noun can matter", probed
  with `move 1 coin from hand to pile` failing on `hand`. With `hand`
  contracted that probe now resolves clean and the noun IS reached. The row
  must be re-probed; `content_kind`'s row claims typecheck's flavor wall
  catches it in the library's currency, which is the thing to verify.

The type-shape checks are a SECOND implementation of `_resolve_zone`'s class
(unknown type, owner arity, owner-without-index, owner-vs-index disagreement),
not a call into it: the two report in different currencies and run at different
times, so sharing a body would mean threading a currency through it. The copy is
a backstop naming the wall it shadows, and the two are pinned equal over the
whole of `LIBRARY_ZONE_TYPES` — 64 cells, red under disabling either arity rule
alone. `_resolve_zone`'s position-projection wall has no analogue because a
contract cannot be position-indexed at all.

### The third leg, sized rather than waved off

The obvious way to double the library is a **required function**:
`requires { function is_contraband(c : Card) : Boolean }` would put `inspect`
in the library for 8 of the 12 files, and would be the first contract entry
that is neither state nor zone — which is #178's question answered by a
witness. It was sized before being set aside:

- `n.Library.requires` is `tuple[RequireDecl, ...]` — **homogeneous** — and six
  sites in `resolve` iterate it assuming a state variable. The zone leg splits
  those six (a contracted zone name feeds the `zone` namespace, not `state`);
  the function leg additionally makes the tuple **heterogeneous**, which pulls
  in `test_reference_slots` (a new node with new slots),
  `test_shape_axis_covers_every_compared_field`, and the claim and collision
  grids.
- `n.FunctionDef` declares **no return type** — `function can_act(p : Player) =
  …` infers it. So a function contract either cannot state its return type (a
  contract too weak for the use, since `inspect` needs Boolean) or the check
  moves to `typecheck`, a pass that does no contract checking at all today.

So the reuse is the splice-side name plumbing only; the distinctive half is a
new node kind plus a return-type decision that #178 itself lists as open
("can a contract express a capability, or only names?"). That is a second
change, not a third leg on this one. Recorded as the measurement #178 asked
for, and it is a sharper answer than the item's own question expected: what
this family's shared `inspect` wants is **a contract over definitions**, not a
`with` clause.

### What this costs the deliverable, stated plainly

With zone contracts the library holds `commit_shipment()`, `move_type wave`
and a six-entry contract — roughly 19 of each file's ~145 lines. The family
shares ~90% of its text; the tier captures about 13% of it. The rest is
zones, state, phases and `inspect`, and none of those is a parameterization
problem. That gap IS the result: it is the measurement
`docs/open-questions/variant-delta-syntax.md` is waiting on, and it is more
informative than a large library would have been.

## Gate 3.5 — reachability and proportion

- #176 (a `requires` zone entry misread as state) — **R3**, a library
  author who contracts a zone; and smaller than filed, per the probe above.
  Implemented rather than walled: #177 is the same surface, walling something
  this change immediately opens is churn, and a wall would freeze the
  contradictory advice.
- #177 (contract a zone) — **R3**, gated on exactly this witness.
- #136 (cross-kind clash between two libraries) — **R3 today, R2 the moment a
  second library exists**: a designer can then write `uses a  uses b`, and
  decisions.md is explicit that accepted-but-unused surface is R2. Its
  `blocked:needs-witness` label and its `reachability:R3` both become wrong on
  landing. R2 disposition is fix-or-file; sized in step 8 and fixed if the
  single-pool sweep is contained, relabelled and left filed if not.

Proportionate: the item is the top of the tracker's ordering, and the size is
set by the family rather than chosen — no zone contract, no library at all.

**Stop-shapes checked.** This does not edit doctrine (decisions.md "Family
libraries" is a settled *design* section whose own text says the boundary moves
corpus-first), does not revert a settled decision (the no-override rule and
"parameterization rides on state" are confirmed, not weakened), and is not
gate-driven — #176 is a live silent misread. If the verdict had come out
"this family needs overrides", **building** that would be a stop-shape and would
route to the operator; recording it in `variant-delta-syntax.md` is the step.

## The verdict this measures (to be confirmed, not assumed)

Provisionally, from the survey above: **`with` is not forced.** Delta 1 is a
per-game constant and rides on required state exactly as `raise_cap` does.
Deltas 2 and 3 are not parameterization problems at all — a card predicate and
an added statement — and no `with` clause carries either. They are what makes
`inspect` game-local, which is the `poker_betting`-omits-`fold` precedent
landing a second time and by measurement rather than by taste.

The consequence for the library's shape: `smuggle_round` is byte-identical in
all 12 files but contains `offer to inspector one of [inspect, wave]`, and
`inspect` is game-local. `_library_slot_names` gives a library only its OWN
move types, so the library cannot hold that line. The library therefore holds
the commit half and the wave, and the game keeps the offer — the same split
poker draws, one level finer.

## Gate 4 — the framing check, and what survived it

A fresh context got the definition sources only (`cardlang/` wholesale, no
plan, no diff, no domain statement) and enumerated the surface independently.
It confirmed my four axes — type registry, type arguments, nullability,
answering block — and the `zone_type`/`zone_type_arg` reachability flip, the
`index_domain` excuse, and the `Movement.item` residual. **It also found five
things my derivation had missed, and they change the work:**

1. **Two independently-computed "what a library may name" sets, not one.**
   `_library_slot_names()` (the bare-string half) and `_library_reach`'s
   `_Categories(...)` both hardcode zones as empty, in different functions,
   from different inputs. I knew about the first. Feeding one and not the
   other is a silent half-wall.
2. **The classification is NOT derivable from registry disjointness alone.**
   `KNOWN_TYPE_NAMES ∩ LIBRARY_ZONE_TYPES` is empty, but a contract's type
   also resolves against `library.types`, and `_reserved_domain_names` does
   NOT reserve zone-type names — so `type Hand = { … }` in a library, or
   `positions { Hand : 1..5 }` in a game, is legal today and makes
   `requires { x : Hand }` genuinely ambiguous. The disjointness pin I wrote
   covers two of the three sources. A wall is needed, not just a pin.
3. **Unsatisfiable contracts become a class.** A library can spell a zone
   shape no game can legally declare — owner type with no argument, owner
   argument disagreeing with the index, owner type with no index, a
   non-uniform projection on a position index, a `team` index in a game with
   no partnerships. State contracts have almost no such class; this one is
   new, and it is why the zone leg must run `_resolve_zone`'s shape walls
   against the library ALONE rather than discovering the mismatch game-side.
4. **`_check_requires`'s `skip` set is state-keyed** (`contested | provided`),
   so a contracted zone name would be silently skipped by it.
5. **`zone_type_arg` is GAME-FED, so it can never be excused as "closed".**
   `n.Library` has no `positions`, no `partnerships` and no `deck`, so
   `Hand<team>` and `Cascade<column>` cannot be validated library-side at all.
   By `_LIBRARY_UNSWEPT`'s own three-shape taxonomy that is "walled elsewhere"
   at best — and naming which pass does the walling is the row's obligation.

**And one correction to Gate 3's third criterion, which I had stated too
comfortably.** I wrote that a contracted zone is the game's zone so
`ZONE_PROJECTIONS` is not consulted differently. That is true of the runtime
and false of the mechanism: a zone type FIXES the per-observer projection, so
a contract naming `HiddenPile` rather than `PublicHand` constrains who can see
what. decisions.md's sentence — an import "carries no runtime and no
information-set implication" — stays true, because nothing is spliced and the
game's own declaration is what runs. But its stated REASON is about to become
false: today a library is info-set-neutral partly because it names no zone.
After this change the neutrality rests only on "imports are pure name
resolution", and the prose must say so instead.

Pre-existing gaps the check turned up, probed and confirmed, that this change
does NOT cause: duplicate `requires` entries are accepted; reserved names
(`none`, `state`, `actor`) in `requires` are accepted; and the arity
diagnostic hardcodes "per-player"/"a scalar", already wrong for a `team`
index. Same closed domain, so they are swept — filed with the change rather
than folded into it, per Gate 3.5.

## Outcome

Landed: the zone contract (#176, #177), `docs/libraries/smuggling.cardlang`, all
12 family files converted, and the sweep of `_LIBRARY_UNSWEPT`.

**Neutrality, measured.** 12 members x 12 seeds, every per-observer observation
event and every decision point with its candidate list: byte-identical before
and after the conversion. `mypy` clean, full `pytest -q` green.

**The `_LIBRARY_UNSWEPT` sweep found a live leak, not just stale prose.**
`index_domain`'s row claimed the namespace was CLOSED — "a contract naming a
position domain asks for a declaration the game is itself refused". True for
state; false for zones, because a game DOES declare position-indexed zone
families (Klondike's `tableau_down[column]`). Probed and confirmed: a library
could contract `t[column] : Deck` and reach a name only the importing game
declares. The namespace is now swept against the roles rather than excused.
Two more rows had reasons resting on the same falsified premise — `content_kind`
and the ledger's `Movement.item` residual, both of which argued that a movement
always names a zone the classified pass refuses. Re-probed rather than re-read:
both outcomes hold, on typecheck's item-noun and flavor walls, in the library's
currency.

**For the reviewer — tracker actions this change earns, not yet performed:**

- #176 and #177 close. #176's body should also record that its filed
  repro stopped reproducing when PR #172 landed the reference-slot registry —
  the misread became a loud refusal with misdirecting advice.
- #136 moves from `reachability:R3` to `reachability:R2` and loses
  `blocked:needs-witness`: a second library exists, so `uses a  uses b` is a
  sentence a designer can now write. It stays open and stays filed with its
  kind, which is R2's disposition. Not fixed here — the single-pool sweep wants
  its own kind-x-kind grid, and folding it in would put two closed domains in
  one change.
- #143 item 1 is done and comes off the list. What this family's evidence says
  about the tier's next pressure is now filed as **#189** (a contract over
  DEFINITIONS, not a `with` clause), a sibling of #178 rather than the same
  question: a definition is a name in a namespace `requires` does not reach,
  where #178 asks whether a contract can express a capability at all. #140
  independently reached for the same mechanism from the Coup/Cheat challenge
  window, which is what says the need is not an artifact of this family's
  delta-lattice shape.
- **#137 ("Allow family libraries to hold zones and/or phases") is to be narrowed
  ONCE THIS PR LANDS** — authorized by the operator 2026-07-29, deferred to merge
  deliberately, since the narrowing asserts things this PR has to have landed for
  them to be true. Its zone half is answered: this family forced zone CONTRACTS,
  and holding a zone was not merely unforced but unavailable, because every
  family zone is written by game text somewhere and provided state is read-only
  to the game. The live zone question becomes the sharper one — a family whose
  shared zone is written ONLY by library definitions. Its phases half stands and
  gains an argument: procedures do not compose, so shared material reachable only
  from a game procedure has to be lifted to a phase to be shareable at all. Its
  Witness section asks for a family to be named; this one has been, and it does
  NOT force holding, so it must not be left reading as pending evidence.
- The registry residual in `tests/test_reference_slots.py` is **narrowed, not
  closed** — `offer`'s library half, `round`, `produces:` and a struct type are
  still unexecuted, and the module says which.

## Task list

Every step names the artifact that proves it. Steps 1–2 are the audit's Step 1
and produce the red set that IS the rest of the work.

*Steps 1–7 and 9 were done; the Outcome section above reports against them.
Two things this list allowed for were deliberately NOT done, and are dropped
rather than pending: building a `with` clause or an override form (the
measurement says neither is forced, and building one is a planning stop-shape),
and step 8's #136 fix (relabelled instead — the single-pool sweep is its own
closed domain and its own change).*

1. **Framing check + grid, authored red.** Run `surface-totality-audit` Step 1
   against the definition sources (grammar `require_decl`/`zone_decl`/`type_ref`,
   `n.RequireDecl`/`n.ZoneDecl`, `LIBRARY_ZONE_TYPES`, `KNOWN_TYPE_NAMES`,
   `resolve._REFERENCE_SLOTS`, `_LIBRARY_UNSWEPT`). *Artifact:* the accepted
   domain statement, diffed against the author's provisional axes.
2. **The grid as an executable parametrized test**, axes derived in code —
   contract-kind x game-declaration-kind x match/mismatch, with the zone-type
   axis derived from `LIBRARY_ZONE_TYPES` (parameterized and not) and the state
   axis from `KNOWN_TYPE_NAMES`. *Artifact:* the grid module, red
   (`xfail(strict=True)`), before `require_decl` is touched.
3. **Grammar + AST: `require_decl` takes a `type_ref`.** Ownership parameter
   accepted (`HiddenPile<player>`), because the witness needs it — recorded as
   forced, not chosen. *Artifact:* grid rows for the parse layer going green.
4. **Resolve: classify each entry, check zone entries against `zones { }`.**
   Classification derived from the two registries, plus a pin that they are
   disjoint (otherwise the classification is authored and can silently flip).
   Diagnostics for contracted-as-zone/declared-as-state and its mirror, and for
   a type in neither registry. *Artifact:* the misuse-probe rejection tests,
   each loud in resolve's currency on the game's `uses` span.
5. **Re-probe `_LIBRARY_UNSWEPT` as a class.** Opening zone contracts flips
   `_library_slot_names["zone"]` from empty to non-empty, which falsifies the
   comment above it and invalidates every recorded reason that leaned on a
   library being unable to name a zone (`content_kind` names movements
   explicitly; `(n.Round, "source_zone")`/`"play_zone"` become newly
   reachable). Probe each row, do not re-read it. *Artifact:*
   `test_every_reachable_reference_namespace_is_swept_or_excused` plus the
   rewritten rows.
6. **`docs/libraries/smuggling.cardlang`.** Contract over the zones and state
   it actually reaches (minimality is pinned), `procedure commit_shipment()`,
   `procedure wave_shipment()`, `move_type wave`. Header records why a library
   for a non-corpus family lives beside the corpus: it is the only loader path,
   and #180 wants one loader fewer, not one more. *Artifact:*
   `test_every_library_contracts_for_exactly_what_it_reaches` green on the new
   member.
7. **Convert all 12 files and pin the neutrality.** *Artifact:* a CI test that
   binds the library against every green-lane file, plus the before/after
   playout traces from criterion 2.
8. **#136: size the single-pool sweep.** Fix if contained; relabel R3 to R2 and
   drop `blocked:needs-witness` either way, since the witness has arrived.
   *Artifact:* either the cross-kind rejection tests, or the relabelled issue.
9. **Docs and ledgers.** decisions.md "Family libraries" (zone contracts;
   Survey 2 rewritten as executed, with the three-delta decomposition and the
   `with`-not-forced verdict); `variant-delta-syntax.md` (line 17 made true, and
   the verdict recorded — delta 3 is what a delta form would be for);
   `libraries.py` and `_check_requires` docstrings; the ledgers in
   `test_family_libraries.py` and `test_reference_slots.py`. The registry
   residual is **narrowed, not closed**: green-lane executes `offer` and the
   newly-reachable zone slots, and touches neither `round`, `produces:`, nor a
   struct type. Say which slots got executed and leave the rest open.
