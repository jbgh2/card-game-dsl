# Kernel extensibility: from closed axes to a parameterized interpreter

*Status: design analysis / proposal — not a settled decision. The committed spec is in [decisions.md](../decisions.md); this note argues a direction and a sequenced, byte-identical plan.*

*Implementation status: §9 steps 1–3 are done, and step 4 is delivered for the
fully-kernel games (the projection substrate + general adapter; five
`instantiate` games remain). The runtime is now the single
`run_decision_round` interpreter with the trick, auction/betting, and climb forms
as six-slot hook bundles (`TrickForm` / `AuctionForm` / `ClimbForm` in
`cardlang/runtime/mechanics.py`), selected by `build_form` and dispatched once in
`execute.py`. §§1–8 are the rationale that produced it — where they speak of "the
three `run_*` loops," read the discovery basis, not the current structure. The
info-set leak (§6, §9 step 4) is closed for the thirteen fully-kernel games
(Seven-Card Stud joined when its showdown left `instantiate`; Pinochle when its
trump declaration, meld, and trick play did; French Tarot when its chien
handling, tricks, and scoring did — the last also needing a movement `where`
filter and a rule `exempts:` clause, two new closed-axis additions, not engine
hooks; Cribbage when its pegging and show did, reusing the `where` filter with
ordinary statement control flow and no new axis; Schnapsen and Skat via the
auction form's Card domain and role-guarded ring; Tichu when its push, climb
tricks, and scoring did — the climb form gaining the engine-level `ends_trick`
read and terminal round-state, not grammar); it remains open for the one
`instantiate` game (Coup), as does the front-end derivation (§5).*


## 1. The question and the short answer

Each new game fractally adds a small feature, and the decision kernel
keeps needing new machinery to hold it. Adding the climb form for Big
Two and Tichu forced an edit at every one of seven pipeline stages —
grammar, AST, parser, IR, resolve, typecheck, runtime — and the
deferred backlog (Skat call-and-response, out-of-turn bombs, off-the-
clock Tichu calls, Phoenix contextual rank, Coup's response-window
nesting) reads like a queue of the next several such edits. The
question is whether the kernel needs a fundamental redesign.

The short answer is **no rewrite**. The current design ships fourteen
games and migrates byte-identically; that property is not to be spent.
But there *is* a strategic move, and it is not the obvious cleanup —
folding the four hand-written `run_*` loops into one is worth doing, but
as **hygiene**, not strategy. The strategic move is to turn the
interactive-decision kernel into **one parameterized interpreter**: a
single per-step decision loop whose varying behaviour is supplied by a
small set of typed hooks, with the trick / auction / betting / climb
forms becoming **hook bundles over that interpreter** rather than
field-presence-dispatched cases in the runtime. This is a definitional
interpreter (Reynolds) parameterized by a strategy, not a new language;
being precise about that is the point of §3 and §5, because the loose
version of the claim ("stdlib written in the DSL," "constructs compile
down") promises a compile-time win the mechanism does not deliver.

This note diagnoses why the proliferation happens, locates the design
between the two reference points in the literature (GDL and Ludii),
shows that the interpreter is *discovered* from the four existing forms
rather than invented, names the traps — the sharpest being an
information-set leak wider than previously stated — answers the
strongest case against the move, and ends with a sequenced plan that
risks nothing already working.

## 2. Diagnosis

### The family is the expression problem; the specific tax is the dominant decomposition

`Round` is a closed tagged union of **forms** — trick, auction,
betting, climb — dispatched by *field-presence* (`combos_fn is not
None`, `move_types is not None`) across the seven-stage pipeline. This
is an instance of Wadler's expression problem: a datatype defined by
cases, over which one wants to add both new cases and new operations
without editing existing code or breaking static safety. But the pain
the corpus actually inflicts is one-directional — we add *forms*, and
each cuts across all seven stages — so the sharper name is the
**tyranny of the dominant decomposition** (Tarr, Ossher, Harrison &
Sutton, ICSE 1999): the pipeline is decomposed *by stage*, so a feature
that is conceptually one thing (a form) is smeared across every stage.
The climb case forced an edit at grammar, AST, parser, IR, resolve,
typecheck, and runtime for exactly this reason. Naming it precisely
matters because the fix differs by diagnosis: the interpreter move
below collapses the *runtime* smear, and only the *runtime* smear —
§5 is honest about which stages it does and does not touch.

### Proliferation is at the axis level, not the value level

The corpus gives a clean empirical test, and its own docs supply the
criterion: a feature is a **value** (cheap, absorbed silently) when it
slots into an *existing hook* as a value, predicate, or named function
— "the same shape as a `round`'s `outcome` or `early` function"
([decisions.md](../decisions.md), "Round configuration vs rules"). A feature is a **new
mechanism** (expensive, gated) when it needs a new *form*, *axis*, or
construct. The historical tell is decisive: **value features were
merged silently; mechanism features each spawned an open-question file
or an explicit deferral.**

Absorbed as values, no open question: Stud's `priority` betting order
(a value on the order axis); Bridge's static ring and Pinochle/Tarot/
Stud's shrinking ring (participant-filter values); Stud's betting
accumulator ("ordinary phase state written by the move-type effects,"
no construct); Tichu-vs-Big-Two shed-out termination (a value on the
termination axis); contextual-suit jacks (a `same_suit_class`
predicate); bid outcome variants like `contract_finalized | all_pass`
(a named outcome function). None needed sign-off; none left a trace in
`open-questions/`.

Gated or deferred, each with an open-question file: **combination
climbing** (Big Two, Tichu) — a new *form*, "a combination play cannot
be a DSL `move_type` effect the way a bet is" ([decisions.md](../decisions.md)), the
seven-stage edit; **Skat Reizen call-and-response** — filed then as a new
*order axis* with three reasons a ring cannot express it (role-dependent
vocabularies, conditional participation, seat reorder), since resolved as a
ring *configuration* with no new axis ([decisions.md](../decisions.md), "The
auction form of `round`", the call-and-response bullet); **Dog `ends_trick` lead** — "a
genuine new axis to surface and sign off" ([kernel-migration.md](../kernel-migration.md), WS3);
**out-of-turn bombs** — a *mechanism* that *inverts* the model's "rules
constrain" framing, permitting rather than restricting
([open-questions/out-of-turn-moves.md](../open-questions/out-of-turn-moves.md)); **off-the-clock calls** —
"there is no 'optional move during a window' idiom yet"
([open-questions/optional-window-moves.md](../open-questions/optional-window-moves.md)); **Phoenix contextual
rank** — "resolved at play time against trick context"
([open-questions/special-cards-declaration.md](../open-questions/special-cards-declaration.md)); **Coup
challenge/block nesting** — "the highest new-axis risk"
([kernel-migration.md](../kernel-migration.md), WS5).

The strongest statement is qualitative: **the entire deferral backlog
is forms, axes, and mechanisms; not one entry is "add a value to an
existing axis."** Values are free; axes are gated. The closed-axes
discipline is thus a centralized dam that every fractal feature raises
again through the one bottleneck. Steele's *Growing a Language* names
this: a language must be grown *by its users*, with the maintainer
coordinating rather than personally authoring each addition, because
centralized growth does not scale. And the gated cases cluster in the
newest games (Skat, Tichu, Coup): as the corpus leaves plain trick/
auction territory, new-mechanism demand *rises* rather than saturating.

## 3. The strategic fork: GDL substrate vs Ludii derivation

Two reference designs bound the space, and the project sits between
them paying both taxes.

**GDL / GDL-II** specifies any finite game from a handful of logical
primitives — `role`, `init`, `legal`, `next`, `terminal`, `goal`, plus
`sees` and a `random` player — and is *universal* (Thielscher, IJCAI
2011). It has two independent properties, and they must not be
conflated. On axis (a) — *reusability* — GDL is impoverished: nothing
is reusable above the primitives and descriptions are unreadable. On
axis (b) — *information sets* — GDL is the paragon: its `sees`/`random`
relation *derives* each player's information set from the spec, which
is precisely the property our OpenSpiel target needs. Our Python
escape-hatch mechanic (Coup)
shares GDL's *bad* axis (a) — build-from-primitives, nothing reusable
above it — while being the **opposite** of GDL on axis (b): its
info-sets are hand-authored, not derived. So the escape hatch gets
GDL's worst property without its redeeming one — which is exactly the
leak §6 is about.

**Ludii** goes the other way. Its class grammar (Browne, ACG 2016) is
*self-generating*: a context-free grammar is derived from the Java
class hierarchy via reflection, giving a 1:1 map between keyword and
code, and descriptions instantiate straight back to library classes for
compilation. Adding a ludeme is adding a class — the
parse/validate/compile pipeline is *derived*, never hand-written. This
is the exact inverse of our seven-stage manual edit, and the strongest
external evidence that our *front-end* proliferation tax is a **tooling
choice, not a law**.

The project sits in the middle, paying **both** taxes: the seven-stage
pipeline edit per construct (the GDL-side cost of no derivation) *and*
recurring maintainer-gated new axes (the cost of a closed vocabulary
without Ludii's derivation to make growth cheap). The interpreter move
pays down the *runtime* half of the first tax now (four hand-written
loops become one) and closes the info-set leak class-wide; it does
**not**, by itself, buy Ludii's derived front end — §5 is explicit that
grammar/parser/typecheck work still attends any construct with new
surface syntax. Buying the front-end half would require a genuine
derivation or macro layer, named there as separate future work.

## 4. The interpreter, discovered from the four forms

The move is not to invent a substrate. `run_trick`, `run_auction`
(which serves *both* the auction and betting forms), and `run_climb`
are **the same per-step decision loop written three times**. The
interpreter is what remains after the varying slots are lifted out; the
hooks are supplied at runtime and *called* by a fixed loop — this is a
definitional interpreter (Reynolds 1972) parameterized by a strategy,
not a compiler. Being clear about that governs what §5 may and may not
claim.

### The shared skeleton

```
def run_decision_round(F, state, ctx):
    state = F.init(state, ctx)                    # seed accumulator + cursor
    while True:
        if F.terminated(state, ctx):              # predicate end (until/early/shed-out)
            break
        actor = F.next_actor(state, ctx)          # ring / priority-rescan / came-back-to-last
        if actor is None:                         # structural exhaustion
            break
        cands = F.candidates(actor, state, ctx)   # cards / move-vocab / combo query, canonically ordered
        if not cands:
            raise MalformedGame(...)              # FIXED (new): a decision node is non-empty
        choice = ctx.chooser(actor, cands, 1)[0]  # FIXED (unchanged): the single per-step draw
        ctx.trace("decision", (actor, choice))    # FIXED (new): the canonical decision event
        state = F.apply(actor, choice, state, ctx)# enact; emit DOMAIN events here
    return F.outcome(state, ctx)                  # Player | (tag, payloads) | None
```

Three items are marked **FIXED** — not pluggable, identical for every
form. Two of them (the empty-candidate guard, the canonical
`("decision", (actor, choice))` observation event) **do not exist in
the runtime today** and are introduced by this move; the third (the
single `ctx.chooser(actor, cands, 1)[0]` draw) is present in all three
current loops already. This distinction matters for §6 and §9: today
only `run_trick` emits any per-decision trace (a domain `"play"`
event); `run_auction` and `run_climb` emit nothing per decision, and
none emit a uniform decision event. The uniform event is new.

Two transformations make this a real extraction, not three renamed
functions. **The cursor migrates into `state`:** today the loop cursors
(`i` in the auction ring, `idx` in climb) and the ad-hoc `led_suit` /
`current` / `last` are Python loop locals; for `next_actor` to be a
*pure function of `(state, ctx)`* they move into the threaded `State`.
This turns `order_mode` from an **enum** into a **choice of
`next_actor` closure** — the move Danvy & Nielsen call
**refunctionalization**, the inverse of defunctionalization; the enum
dissolves into a function. **Termination collapses to one hook:**
trick's `early`, the auction/betting `until`, and climb's shed-out
predicate are three `Round` *fields* today but one top-of-loop hook;
and trick's "turn order ran out" and climb's "came back to the last
player who played" are the same event — the actor generator is
structurally spent — both folding into `next_actor → None`.

### The primitive signature

Six pluggable functions plus one threaded `State`; order and
participants are **functions**, never enums.

```python
State   = dict[str, Any]                          # accumulator + loop cursor, threaded by value
Outcome = Player | tuple[str, list[Any]] | None   # winner | typed variant | betting-void

class DecisionForm(Protocol):
    def init(self, state, ctx) -> State: ...            # seed accumulator + cursor
    def next_actor(self, state, ctx) -> Player | None:  # who acts, or None for exhaustion
    def candidates(self, actor, state, ctx) -> Sequence: # the finite action set, CANONICALLY ORDERED
    def terminated(self, state, ctx) -> bool: ...       # the predicate end, checked top-of-loop
    def apply(self, actor, choice, state, ctx) -> State:# enact; thread accumulator; emit domain events
    def outcome(self, state, ctx) -> Outcome: ...       # Player | (tag, payloads) | None
```

Hook-arity normalization is part of the content: today the predicates
have heterogeneous signatures (`outcome_fn(played, led_suit, trump,
rank)`, `early_term(choice, led_suit)`, a nullary `until` closure); in
the interpreter every hook is `(…, state, ctx)` and reads what it needs
from `state`.

**This encoding eases one axis of the expression problem and taxes the
other; it does not dissolve it.** Field-presence dispatch — `combos_fn
is not None`, `move_types is not None` — *is* the tag; the six-method
Protocol is the tagless/final encoding (Carette, Kiselyov & Shan, JFP
2009) that removes the tag. That makes adding a **form** cheap (a new
hook bundle, no edit to existing forms) at the cost of making a new
**cross-cutting operation** — a seventh hook every form must implement
— expensive. We adopt the final encoding deliberately because forms are
our dominant growth axis and new cross-cutting operations are rare. So
the honest claim is not "we solve the expression problem" but "we pick
the horn where forms grow freely," which is the horn the corpus needs.

### The four forms as instances

| slot | trick | auction | betting | climb |
|---|---|---|---|---|
| `next_actor` | turn-order-from-leader, once each; exhaust ⇒ None | ring: advance pointer | priority re-scan from leader | ring; None when `turn == last`; skip shed-out |
| `candidates` | `legal_cards(p,"play_to_trick",…)` | move-vocab over domain + guard | *same as auction* | `lead_query` / `[*follow_query, "pass"]` |
| draw | `chooser(p,cands,1)[0]` | *same* | *same* | *same* |
| `terminated` | `early_term` | `until` predicate | *same* | shed-out predicate |
| `apply` | move card, set `led_suit`, fire transitions, emit `trick_end` | run move effect; append history | *same* — effects mutate chip/fold state | move combo hand→pile; set `current`,`last` |
| `outcome` | `outcome_fn(...)` → Player | outcome fn → `(tag, payloads)` | **None** | `last` |

The mapping covers the four *sequential single-actor* forms exactly:
every line of the three loop bodies lands in one slot. The clinching
evidence for "values on slots, not new slots" is that **auction and
betting are already one function**, `run_auction`, differing only in
the *value* of the order slot and the *presence* of an outcome function
— Stud's priority betting cost a new `next_actor` closure, a value on
an existing slot. The value-vs-axis distinction made concrete in code.

**The mapping is not exhaustive over the model's order axis, and the
gap is instructive.** `decisions.md` names the order axis as "turn-
from-a-seat / priority / **simultaneous**," and simultaneous is not a
`Round.order_mode` value — `ROUND_ORDER_MODES` is `{ring, priority}` —
but a *separate construct*, the `EachSimultaneous` AST node
(`each <role> simultaneously: <stmt>`), whose contract is that
"observers cannot infer any ordering among the moves." Simultaneous
resolution cannot be a `next_actor` closure over the single-actor loop:
all actors must choose without seeing each other, which the one-actor-
per-step shell structurally forbids. This is the Goldilocks "too
narrow" failure realized on an **existing** value, not a hypothetical
deferred one. The interpreter therefore covers the sequential forms;
simultaneous either stays a distinct construct or requires the shell to
generalize to a multi-draw step — and if it does, the "exactly one
chooser draw per step" property §8 leans on for OpenSpiel compilation
must be restated. Both options are named honestly in §8; neither is
papered over.

## 5. Forms as hook bundles: what this buys, and what it does not

With the interpreter in place, the four forms stop being kernel `Round`
cases dispatched by field-presence and become **hook bundles over one
loop** — each a bundle of the six slot implementations plus a surface
syntax. This changes the cost curve, but only on the stages it
actually touches, and the note is careful to claim no more.

**What it buys (runtime + dispatch).** Collapsing three loop bodies
into one parameterized interpreter removes the field-presence dispatch
in `execute.py` (the `combos_fn`/`move_types` cascade) and the
duplicated loop logic in `mechanics.py`. A new *form* that reuses the
existing round surface syntax and the six-slot vocabulary is then a new
hook bundle and **nothing else** — no runtime cascade edit, no fourth
copy of the loop. It also **fixes the observation asymmetry**: the
fixed core emits the canonical decision event for every form, not just
trick.

**What it does not buy (front end).** The seven stages include grammar,
AST, parser, resolve, and typecheck. A construct that introduces *any*
new surface syntax — a new keyword, clause, or outcome shape — still
requires work at those stages, because we have **not** adopted Ludii's
derived front end. The grammar has distinct productions per form today
(`auction_stmt` alongside the trick/climb round forms), and a new
surface form adds another. So the honest tally is: the interpreter move
removes the *runtime* stage smear and the `execute.py` dispatch (2 of
the 7 stages, plus the cross-cutting field-dispatch), and leaves the
five front-end stages exactly as costly as today. A construct that
*reuses* existing syntax pays neither; a construct with *new* syntax
still pays the front end.

**Consequently, "small kernel, large stdlib written *in* the DSL" is
not yet delivered by this move, and the note does not claim it is.**
Six Python functions per form is still *metalanguage* — engine code
reorganized behind a Protocol — not object-language DSL text that is
parsed and typechecked. The accurate, still-valuable claim is: *the
decision engine becomes a single parameterized interpreter, and forms
become data (hook bundles) rather than dispatch cases.* Making the
stronger claim true — forms as in-DSL programs under one uniform
surface grammar, so the front-end stages are paid once — requires the
derivation/macro layer named above as future work (the point where the
Ludii class-grammar and Racket "languages as libraries" (Tobin-
Hochstadt et al., PLDI 2011) references would finally be *earned*
rather than borrowed). Until then those citations describe the
*destination*, not this step.

The deferred axes are the real test, and the honest position is that
they are *feature interactions*, not single new axes. Skat call-and-
response is auction order combined with role-dependent vocabularies;
out-of-turn bombs invert the permit-vs-constrain framing on top of turn
order; Phoenix rank couples card identity to trick context; off-the-
clock calls couple announcement to timing. The feature-interaction
literature (Apel, Batory, Kästner & Saake, 2013) is *cautionary* here,
not supportive: interactions historically require dedicated resolution
glue (derivatives, lifters), which cuts *against* the hope that they
"lower cleanly." So "each lowers onto the six slots" is the optimistic
hypothesis the paper-proof (§9 step 2) must **discharge**, not a
premise the note may assume — and one of the four (out-of-turn as a
permit-vs-constrain inversion) is arguably a single mechanism, not an
interaction at all, and should be judged on its own.

## 6. The traps

**The information-set leak (headline).** *Status: the substrate this section
argues for now exists for kernel-form games (`cardlang/runtime/observe.py`,
`cardlang/openspiel/`); the leak persists exactly where `instantiate`
mechanics run — see §9 step 4.* The docs promise that
information sets are "*derived* from zone visibility plus the
observation events emitted by moves — never authored by hand"
([principles.md](../principles.md)) — the GDL-II `sees`/`random` semantics made
operational. The runtime keeps almost none of this promise, and the gap
is *wider* than the thesis states.

There is **no observation-emitting substrate at all**, not even in the
kernel. The only event channel is `Ctx.trace`, whose single consumer is
a caller-supplied debug/characterization hook; its `"play"` / `"trick"`
/ `"coup_reveal"` calls are score/replay traces, not projections per
observer through any visibility declaration. No runtime code reads the
six-projection model of [decisions.md](../decisions.md). And of the three kernel loops
only `run_trick` emits a per-decision trace (`"play"`); `run_auction`
and `run_climb` emit none — so there is no uniform decision event to
project even if a projector existed.

**Exactly one game reaches OpenSpiel, and even it is hand-authored, in
two separate hardcoded conventions.** `pyspiel.register_game` fires
once, for Hearts. Its adapter labels observations public-or-private by
hand: `replay.py` classifies each logged action by the raw *count* `n`
(`kind = "pass" if n > 1 else "play"`), while `infostate.py` keeps a
logged action if `kind == "play" or pl == player` — i.e. by event kind
and ownership. Both are Hearts-specific conventions baked into the
adapter (its own docstring says "These observation rules are Hearts-
specific"), not derived from any DSL visibility declaration. Either
would silently mislabel a move the adapter never anticipated: a Stud
face-up card, a Coup reveal, a Skat bid. For the twelve non-Hearts
games there is no adapter and nothing reaches the AI target; the
Python-mechanic games — Coup's influence cards, Skat's Reizen, Stud's
hole cards, Tichu's concealed hands — run inside one opaque function
whose hidden state never becomes a projected observation. **The leak
lands hardest on exactly the imperfect-information games the OpenSpiel
target exists to serve.**

This is the strongest independent argument for the interpreter. A
uniform loop that routes every move through one observation-emitting
step, projected per observer via declared zone visibility, makes the
info-set of *any* game fall out of the same code path — kernel forms
and future hook bundles alike — instead of a bespoke
`..._information_state` per game. New mechanics defined as hook bundles
inherit derivation; hand-written Python cannot.

**Secondary trap — the hygiene mistake.** The tempting first move is to
unify the four `run_*` forms and stop. That removes the field-dispatch
duplication but keeps a *closed* form vocabulary and an *undelivered*
front end — a fifth form with new syntax still costs a grammar-through-
typecheck edit. Unifying is worth doing, but mistaking it for the whole
strategy leaves the front-end tax intact.

## 7. The counter-case, answered

The strongest case against this note is that the design already
occupies the point the interpreter only *promises*: readable,
statically analyzable, and compilable at once. Fourteen games run;
auctions, betting, and both climb games migrated byte-identically; the
axes are enumerable and inspectable. The interpreter is a *bet* that a
strictly better point exists, and this note's own "prove on paper
first" concedes the bet is unproven.

Three points in that case are correct and accepted here. First,
**refunctionalizing order and participants into closures is the actual
risk, not a tuning knob** — trading enumerable, readable enum values
for opaque callables is *precisely* the direction that costs GDL its
analyzability, threatening both the readability acceptance test and
info-set derivation; §8 treats it as the load-bearing constraint and
notes that *defunctionalization* is the direction that restores
analyzability, so the Goldilocks band is exactly a refunctionalize/
defunctionalize trade-off. Second, **the deferred axes do not yet meet
the three-instance rule** — Skat call-and-response is one instance, out-
of-turn and off-the-clock calls zero live, `ends_trick` one, Phoenix
rank arguably a value. This note therefore does **not** propose
building the interpreter to absorb them now; it proposes *proving on
paper* that it could, and shipping the interpreter only as a byte-
identical refactor of what already exists. Third, **the pipeline cost
is bounded and the leak closes by finishing the stated migration** — a
construct arrives maybe once per several games and amortizes (auction
paid for four).

One asymmetry must be owned: the note wields the three-instance rule to
*reject* new axes, yet *proposes* a class-wide observation-projection
substrate on the strength of a single realized instance (Hearts, itself
hand-authored). The defense is that info-set derivation is not a per-
game feature but the kernel's reason for existing — the OpenSpiel/AI
target the whole project is built to hit — so it is scaffolding, not a
speculative abstraction over one game. That exemption is stated, not
smuggled.

The reconciliation is that the interpreter refactor is **action-
compatible with incrementalism, not a departure from it.** It changes
no game's behavior, adds no axis, and is gated behind the existing
goldens. What it buys is optionality: when the axis-gate *does* fire
three-at-a-time, the machinery to express the interaction as a hook
bundle is already present rather than a fresh kernel redesign under
deadline. The axis-gate remains the detector; the interpreter makes its
positive signal cheaper to act on — cheaper at the runtime stage,
though not yet free at the front end.

## 8. The Goldilocks risk

The interpreter's primitive vocabulary must sit in a narrow band. Too
general — untyped closures over arbitrary state — and it becomes GDL:
unanalyzable, unreadable, info-sets no longer derivable. Too narrow —
closures collapsed back to enums — and it is the current kernel, edited
per axis. The band that satisfies both: **`State` is a structured
record and the six hooks are typed, finite, and total** — info-sets
stay derivable because the fixed core emits the decision event, and the
thing still compiles to OpenSpiel's one-node-per-turn model because
there is exactly one chooser draw per step; this is *not* GDL's untyped
substrate. Yet **`next_actor` and `candidates` are genuine closures,
not enum tags** — the refunctionalized form is what holds the door open
for deferred interactions. Keeping them closures now, even while the
forms exercise only a handful of values, is the cheap option that
preserves the option; if a case ever needs to be re-analyzed, the
inverse move (defunctionalize the closure back to a tagged value) is
the lever that restores inspectability.

Two concrete constraints make "compiles to OpenSpiel" real rather than
asserted, and both are gaps today:

- **`candidates` must return a totally-ordered, stable, declared
  sequence — not an opaque list.** OpenSpiel needs a stable bijection
  between each candidate and an integer action ID, consistent across
  information-set-equivalent states. Today `legal_cards` returns a
  *set* whose iteration order is `PYTHONHASHSEED`-dependent (the reason
  exact-score tests pin the seed), and the sole adapter hardcodes a
  52-card single-card action space. A multi-card climb *combination*
  has no encoding under that space at all. Requiring `candidates` to
  yield a canonical ordered sequence, and requiring each construct to
  supply a canonical candidate↔action-ID encoding (or the interpreter
  to derive one), closes the determinism gap and the multi-card-
  encoding gap in one constraint — and flags that the fixed 52-card
  action space must generalize before any non-single-card construct
  reaches the AI target.

- **The single-draw-per-step property is what the one-node-per-turn
  compilation rests on, and simultaneous resolution breaks it.** As §4
  showed, `EachSimultaneous` is a separate construct precisely because
  all actors choose without ordering. If the interpreter is ever
  generalized to a multi-draw step to absorb it, "exactly one chooser
  draw per step" no longer holds and the OpenSpiel mapping must be
  restated (simultaneous moves compile to a different node shape).
  Until then, the interpreter covers the sequential forms and
  simultaneous stays its own construct — a deliberate scope line, not
  an oversight.

The readability constraint bites here too: a form must still present as
a named, readable surface — a non-player reading the game file must be
able to play a hand ([principles.md](../principles.md)). The hook bundle is an
*implementation* relationship; closures must not leak into the surface
syntax. Proving a given interaction expresses *as a hook bundle* **and**
keeps a readable surface is the content of the paper-proof step.

## 9. Verdict and a safely-sequenced plan

**Verdict: no rewrite.** The current design ships and migrates
byte-identically; that is the property to protect. The strategic move
is the parameterized interpreter plus the observation channel,
sequenced so that nothing already working is risked and the unproven
parts are proven on paper *before* any code depends on them.

1. **Paper-proof the vocabulary first.** Before committing code to the
   six-slot signature, take the two hardest cases — Skat call-and-
   response and out-of-turn bombs — and demonstrate *on paper* that
   each expresses as a hook bundle over the six slots while (a) keeping
   info-sets derivable and (b) keeping a readable surface form. This
   comes first, not second, because step 2 *commits* code to the exact
   signature; if the paper-proof shows a case needs a reshaped hook (as
   opposed to merely a new *value* on an existing hook), the vocabulary
   must change before code depends on it. If a failed proof would only
   ever *add* a slot and never reshape the six, step 2 is safe to
   precede it — but that must be established here, not assumed. Cheap
   and mandatory; it is the de-risking gate.

2. **Hygiene: unify the sequential forms behind the goldens — *done*.**
   The shared skeleton (§4) is extracted as `run_decision_round` in
   `mechanics.py`; `run_trick` / `run_auction` / `run_climb` are migrated
   onto the six-slot `DecisionForm` bundles (`TrickForm`, `AuctionForm`,
   `ClimbForm`); `build_form` selects the bundle by field-presence and
   `execute.py`'s `Round` cascade is collapsed into one `Outcome`-union
   dispatch (`Player` ⇒ bind `outcome`; `(tag, payloads)` ⇒ raise the
   typed variant; `None` ⇒ close a betting ring). The loop cursors that
   were Python locals (the auction ring pointer, the climb index, the
   trick's turn-order position and `led_suit`) moved into the threaded
   `State`, so `next_actor` / `candidates` are pure functions of
   `(state, ctx)` and `order_mode` became a choice of `next_actor`
   closure. It is **byte-identical** in the sense that matters: the single
   `ctx.chooser` draw per step and the per-form domain trace events are
   unchanged, so scores/returns and the *specific named events the
   goldens assert on* are identical — the complete ordered trace stream
   is *not* a claim, and nothing snapshots it. The refactor added **no**
   new event: the canonical `("decision", (actor, choice))` event is
   deferred to step 4, where it is safe under the current suite only
   because every tracer-using test filters by event name (`if event ==
   "trick_end"`, `in ("bridge_contract","trick",…)`), so an unrecognized
   event is ignored; no test may snapshot the full ordered stream without
   first accommodating it. `EachSimultaneous` stays its own construct
   (§4/§8), as do the per-game Python `instantiate` mechanics.

3. **Migrate the forms onto the interpreter one at a time, each behind
   the goldens — *done*.** Carried out as part of step 2: trick, then
   auction/betting, then climb, each landing green (`mypy`; full
   `pytest -q` under `PYTHONHASHSEED=0`) before the next, then the old
   loop bodies and the field-presence cascade were deleted. No new axis
   was added — existing behavior was relocated onto the shared loop,
   nothing more.

4. **Close the info-set leak as its own workstream — *done* for the nine
   fully-kernel games.** The fixed core's decision event is routed through a
   per-observer projection keyed to declared zone visibility
   (`cardlang/runtime/observe.py`), and the Hearts-specific adapter (both its
   count-`n` and its kind/ownership conventions) is replaced by one general
   reader of projected events (`cardlang/openspiel/infostate.py`,
   `cardlang/openspiel/game.py`) covering Hearts, Getaway, Spades, Bridge, Oh
   Hell, Big Two, Seven-Card Stud, Pinochle, French Tarot, and Cribbage — proven by
   `tests/test_openspiel_ready.py` (indistinguishability, soundness, perfect
   recall; Bridge's and French Tarot's swap/soundness/recall proofs cover only
   the pass-only line of their auctions — the harness's greedy replay never
   places a bid, let alone reaches the chien discard or trick play, so French
   Tarot's hidden discard is instead proven derived by a dedicated
   observational test; Stud's and French Tarot's conformance are bounded random
   API walks, their full sims being quadratic in game length). This was the payoff
   that justified the exercise. The four `instantiate` games remain info-set
   debt: the adapter rejects them loudly rather than silently mis-modeling
   them.

New features arrive only *after* this scaffolding — as **hook bundles**
that reuse the existing round surface where possible, not new kernel
axes — and only when the corpus produces the three instances that
corpus-first requires. The axis-gate stays exactly where it is as the
detector. The interpreter makes acting on the detector local and cheap
*at the runtime stage*; buying the same at the front end is a further,
named step (the Ludii/Racket derivation), deliberately not attempted
here.

## Sources

- Wadler, "The Expression Problem" (1998).
  <https://homepages.inf.ed.ac.uk/wadler/papers/expression/expression.txt>
- Tarr, Ossher, Harrison & Sutton, "N Degrees of Separation:
  Multi-Dimensional Separation of Concerns," ICSE 1999.
  <https://www.research.ibm.com/hyperspace/papers/icse99.pdf>
- Reynolds, "Definitional Interpreters for Higher-Order Programming
  Languages," ACM 1972.
  <https://homepages.inf.ed.ac.uk/wadler/papers/papers-we-love/reynolds-definitional-interpreters-1998.pdf>
- Danvy & Nielsen, "Defunctionalization at Work," PPDP 2001
  (refunctionalization is its inverse).
  <https://www.brics.dk/RS/01/23/BRICS-RS-01-23.pdf>
- Carette, Kiselyov & Shan, "Finally Tagless, Partially Evaluated,"
  JFP 2009. <https://okmij.org/ftp/tagless-final/JFP.pdf>
- Browne, "A Class Grammar for General Games," ACG 2016.
  <https://ludii.games/publications/CG2016.pdf>
- Thielscher, "The General Game Playing Description Language Is
  Universal," IJCAI 2011.
  <https://www.ijcai.org/Proceedings/11/Papers/189.pdf>
- Game Description Language (GDL / GDL-II).
  <https://en.wikipedia.org/wiki/Game_Description_Language>
- Steele, "Growing a Language," OOPSLA 1998 keynote.
  <https://archive.org/details/GrowingALanguageByGuySteeleAhvzDzKdB0>
- Tobin-Hochstadt, St-Amour, Culpepper, Flatt & Felleisen, "Languages
  as Libraries," PLDI 2011 (the *destination*, earned only by a
  derivation layer — see §5). <https://www2.ccs.neu.edu/racket/pubs/pldi11-thacff.pdf>
- Apel, Batory, Kästner & Saake, *Feature-Oriented Software Product
  Lines*, Springer 2013 (cited as a *caution*: interactions need glue).
  <https://www.springer.com/gp/book/9783642375200>
- Internal: [principles.md](../principles.md), [model.md](../model.md), [decisions.md](../decisions.md)
  (auction form incl. the resolved call-and-response bullet, climbing form,
  round-config-vs-rules, order axis /
  simultaneous, projection model), [kernel-migration.md](../kernel-migration.md) (WS1–WS5),
  [.../out-of-turn-moves.md],
  [.../optional-window-moves.md], [.../special-cards-declaration.md].

---

## Validation: lowering Skat Reizen

*Status: overtaken by the landed migration. The Reizen runs on the UNMODIFIED
auction form — role-guarded moves over a two-participant ring, with the
exhausted-ladder auto-pass folded into `until` (so even this section's
forced-`["pass"]`-draw caveat does not arise) — see decisions.md, "The auction
form of `round`", the call-and-response bullet. The analysis below validated
the six-hook lowering before that configuration was found; its conclusion that
call-and-response "cannot reuse the `offering` clause" did not survive contact
with the probe.*

*Discharges the Skat call-and-response item queued in §1 against the six-hook interpreter of §4. Ground truth was the `exchange` closure in the pre-migration `run_skat_hand`; the three closed-axis objections were the since-resolved auction-order-axis question's.*

**(1) Verdict.** Reizen lowers **cleanly and completely** onto the six existing hooks. All three properties that `auction-order-axis.md` calls impossible for a value on the *enum* order axis dissolve into ordinary returns of `next_actor` and `candidates` — because §4 makes those hooks **functions of `(state, ctx)`**, not seat-ring pointers. The objections were sound against an *enum*; they say nothing against a *closure*. No hook is reshaped; no seventh slot is needed (see (4)).

**(2) How the three properties dissolve.** The mechanism is refunctionalization: a small Reizen FSM cursor lives in `State` — `bid_value:int` (shared ladder, only rises), `contest∈{1,2}`, `phase∈{speak,respond}`, `speaker`/`responder:Player`, `winner:Player|None` (carried from contest 1) — and the hooks *read* order and vocabulary off it rather than iterating seats.

- **Role-dependent vocabularies** → killed by `candidates`, keyed on `phase` (a role), never on seat: `["bid","pass"]` for speak, `["yes","pass"]` for respond, plus a third `["play18","throwin"]` for the all-pass coda. A ring's "same vocabulary to every seat" is simply not a constraint a function-valued hook has. *Note: the only witness that distinguishes role-keyed from seat-keyed candidates is `winner = Middlehand` — where M, the contest-1 bidder, becomes the contest-2 responder and must be offered `["yes","pass"]`. A seat-memoized lowering passes the F-winner trace below but fails here; the phase-keyed lowering is correct because it reads the live role.*
- **Conditional participation** → killed by `apply`+`next_actor`. `apply` transitions to `phase="respond"` only when the speaker *bids*; on a pass it closes the contest, so `next_actor` structurally never names the responder. Participation is opt-in *by naming*, not opt-out by filter.
- **Seat reorder** → killed by `next_actor`. When contest 1 resolves, the close-helper sets `speaker=rearhand`, `responder=winner` unconditionally; `next_actor` then emits R *before* the winner. When Forehand won contest 1, that is R-before-F — the reverse of seat order, which a ring filter can never produce.

**Worked trace** (seats F<M<R; ladder 18,20,22,…; contest 1 won by F so the reorder is live):

| step | `next_actor` | `candidates` | draw | `apply` effect |
|---|---|---|---|---|
| 1 | M (speak) | `[bid,pass]` | bid | `bid_value=18`, phase→respond |
| 2 | F (respond) | `[yes,pass]` | yes | phase→speak |
| 3 | M (speak) | `[bid,pass]` | **pass** | close c1, winner=F; **c2: speaker=R, responder=F**, ladder carries |
| 4 | **R (speak)** | `[bid,pass]` | bid | `bid_value=20`, phase→respond — *R (seat 3) acts before F (seat 1)* |
| 5 | F (respond) | `[yes,pass]` | pass | close c2, winner=speaker=R; `bid_value≠0` → declarer=R |
| 6 | None | — | — | loop breaks; `outcome`→R at 20 |

Step 3 exhibits the conditional skip (F never drawn to answer M's pass); steps 4→5 exhibit the reorder; steps 1/2 vs 4/5 exhibit role-dependent vocab. Exactly one chooser draw per step throughout — `apply` is a pure transition and never calls `ctx.chooser`, so folding a second draw is structurally impossible.

**(3) The real bar — readable surface, or relocated monolith?** Honest answer: the lowering **absorbs Reizen as an implementation, but does not earn it a readable library surface.** The pivot is the `offering` clause of the auction surface ([`decisions.md`](../decisions.md) lines 332–337), which the call-and-response hope at lines 325–327 wants to reuse as an *order-axis value*. That clause hard-codes **one flat candidate list per turn**; Reizen needs two role-keyed vocabularies, so `order call_and_response` cannot be a value on the existing `round` — it forces a new `offering` production, i.e. front-end work in exactly the five stages §5 says the interpreter move does *not* pay down. A bespoke surface could be minted, but the sketch reveals it as transcription, not abstraction — every clause maps 1:1 onto a branch of the close-helper:

```
call_and_response
  contest 1: middlehand speaks, forehand responds
  contest 2: rearhand speaks, winner-of-1 responds     // seat reorder
  speaker   offering [bid, pass] climbing <ladder>      // ladder shared across contests
  responder offering [yes, pass]
  on speaker pass   -> responder wins
  on responder pass -> speaker wins
  all-pass          -> forehand offering [play18, throwin]
```

The auction surface reads because it is **homogeneous** (one vocabulary, one ring) and **multiply instantiated** (Bridge/Pinochle/Tarot/Stud). Reizen is **heterogeneous** (two contests, two vocabularies, seat reorder, shared ladder, asymmetric close) and **singly instantiated** — it fails the three-instance gate the note wields in §7. This corrects the specific hope in `decisions.md:325–327`.

**(4) Signature stability.** The paper-proof **passes the §9 step-1 gate**: Reizen adds only **new values** on the six hooks — no reshaped signature, no seventh slot, `outcome`'s `Player | (tag,payloads) | None` union already carries throw-in (`None`) and declarer (`Player`) with no change. Therefore **§9 step 2 (unify the four `run_*` forms behind the goldens) is unblocked and need not wait on a signature redesign.** One caveat to the "byte-identical / draw-for-draw" framing: the original short-circuits on ladder exhaustion (`skat.py:120` skips the chooser when no rung remains), but the fixed loop cannot return an empty candidate set, so the interpreter must emit a forced 1-element `["pass"]` node — one extra draw. It is unreachable in a real hand (requires bidding past 264) but, given the documented `PYTHONHASHSEED` score-sensitivity, is worth naming so nobody assumes the unify is draw-identical *in principle*.

**(5) The contrast — where the interpreter boundary actually sits.** Reizen proves the loop absorbs asymmetric, reordering, role-vocabulary sequencing as *hook values*. Out-of-turn Tichu bombs sharpen the boundary from the other side. The permit-vs-constrain inversion they seem to introduce is a **front-end/model.md framing** concern, invisible to the loop: a `candidates` hook that unions in a bomb under a `bomb_window` predicate is indistinguishable to the shell from any other candidate. The one thing the one-draw-per-step loop *structurally forbids* is **true simultaneity** (`EachSimultaneous` — actors choosing without seeing each other), and bombs do **not** need it: bombs are reactive to the table, so serializing eligible bombers under a priority re-scan is faithful (a higher bomb over-bombs a lower one it sees on the table; highest stands, order-independent). The single arbitrary choice — two equal-strength bombs, resolved by reflex in real time — must be a flagged modeling decision (seat-order tiebreak), not a derived rule. So bombs are the *same mechanism as Reizen* (a `State` cursor driving function-valued `next_actor`/`candidates`), a **reshaped-hook value, not a seventh slot**; `EachSimultaneous` remains the genuine boundary the note already names.

**(6) Bottom line.** Reizen is **not** a counterexample to the six-hook interpreter: its three "impossibilities" are artifacts of an enum order axis and dissolve the moment order and vocabulary are computed from a Reizen state machine in `State` — mechanism proven, signature stable, §9 step-1 gate passed, unify may proceed. The genuine §6 win is that the decision now emits the uniform `("decision",(actor,choice))` event that `run_skat_hand` does not today, so Skat's Reizen info-sets become derivable through the same path as every other form. But the lowering **relocates the monolith rather than abstracting it**: call-and-response cannot reuse the `offering` clause and a bespoke surface would transcribe the close-helper branch-for-branch on a single corpus instance — so absorb-as-hooks *yes*, promote-to-named-readable-form *no*, exactly as §5/§7 predict. The interpreter pays the runtime half; the surface half stays unpaid until a second call-and-response instance justifies it.
