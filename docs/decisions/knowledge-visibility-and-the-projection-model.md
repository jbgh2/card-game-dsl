## Knowledge, visibility, and the projection model

Knowledge over zone contents is the primitive concept for everything
the language models about information asymmetry. Cards and resources
both live in zones; visibility is a per-observer projection
assignment rather than a binary hidden/public flag.

### Honest Play is assumed, so a rule reading concealed cards is mis-modelled

Everything below describes what a player is *entitled* to know. It says
nothing about a player who takes more, and it does not have to: the
engine models players who follow the game's own disclosure rules.

Information reaches a seat through the projections its zones declare, the
public [[state-variable]]s, and the [[observation-event]]s its moves emit
— the three the next section names and a [[seat-view]] carries — and
through nothing else. What a seat may then *derive* from them is
unbounded and is simply the game: the rules, the running phase, whose
turn it is, the zone structure and a seat's own observations are all
knowledge it holds, and reasoning from them is playing well rather than
cheating.

Where a stage or a rule turns on something only one player can see, a
rulebook makes that player announce or show it, and the rule reads the
announcement. Hearts breaks hearts on the card that was *played*; Gin
Rummy opens its showdown on a [[state-variable]] the knock sets. So a
rule that gates, counts or routes on another seat's concealed cards is
not an information leak to be walled — it is a **mis-modelled rule**,
and what the designer wants is the announcement the real rules have.
Where such a rule is refused, the refusal names the missing
announcement. The checker refuses it wherever a read reaches a decision:
where no seat decides (a phase's `when` gate and `repeat until`
condition, a mode's `transition_to` trigger) every seat must be able to
see what the read needs, and where a seat decides (a move type's
`when:`, a rule's clauses, a `choose`'s range, a chosen movement's
amount, source, `where` and destination) that seat must; the positions
are `resolve.HIDDEN_READ_POSITIONS`, and the positions that decide who
is asked rather than what they may do stay outside it (issue #755).

This is an assumption, and naming it is what makes the derived
information state mean anything: a player who peeks, signals to a
partner, or misreports what they hold has knowledge no projection
models, and every proof taken against that game is a proof about a game
nobody is playing. Relaxing it — signalling, concealment, peeking, and
what a game does when it catches one — is out of scope
([roadmap.md](../roadmap.md), "Out of scope"); issue #717 holds the work.
A *bluff* is already modelled and is not that: Cheat's claim is a legal
move whose truth nothing checks, which is the claim-versus-content
encoding the next section describes.

### Hidden information lives only in zones; state is public

The projection vocabulary below applies to **zones and nothing else**.
Every `state` variable — game-, phase-, and loop-level, scalar or
player-indexed — is public to every observer, always. There is no
observer-dependent scalar state and no way to declare any.

This is a deliberate boundary, not a missing feature. It is what makes
information sets derivable: an observer's knowledge is exactly (their
zone projections) + (the public state and public move history), so the
information-state encoding never has to ask *which* variables an
observer may read. It also gives claim-versus-content games their
natural encoding for free — a public assertion (a claimed rank, a named
bid meaning, a running count) is a state variable *because* it is
public, while the concealed truth it may misrepresent sits in a
face-down zone whose projection hides it.

**A seat holds the public state at every decision node it is shown.**
Public means shown to every seat at each decision node, not announced at
each write. At every decision node the kernel delivers to every seat a
[State Delta](../glossary/state-delta.md): one `was` [observation
event](#observation-events) per State Variable slot whose rendering
changed since the previous decision node, carrying the rendering it had
there, emitted from the one route a decision reaches the
[Chooser](../glossary/chooser.md) by, before the `asked`. A seat's log then
fixes the public state it was shown at every earlier node, so overwriting
a variable, a phase's local variables leaving scope or resetting, and a
branch choosing which value is written cannot make a seat forget what it
was shown: perfect recall holds for the public half of the information
state by construction, whichever write door changed a slot and whatever
chose the write. A value written and overwritten between two decision
nodes was shown at neither, and no seat hears it. Whether a game should
publish a concealed fact into state at all is a separate question
(issue #471); a State Delta makes a seat remember what it was shown, not
whether showing it was honest play.

The corollary is a modeling rule: **anything an observer must not know
is contents, not state.** A hidden scalar (a secret counter, a sealed
simultaneous bid) is encoded as tokens or cards in a zone whose
projection conceals them — `count_only` if the *amount* is the secret's
public residue, `trivial` if even that leaks. If a future game's rules
genuinely require a hidden scalar that resists token encoding, that is
a challenge to this decision and goes through
[open-questions/knowledge-events.md](../open-questions/knowledge-events.md)'s
adjacent territory rather than around it.

### Knowledge as candidate sets

Every observer (player) has, at every moment, a **knowledge state**
about each zone they can observe. The knowledge state is a
**candidate set over possible zone contents**: which configurations
of the zone are consistent with what the observer has seen.

Two extremes:

- **Full knowledge**: the candidate set is a singleton — exactly one
  possible configuration.
- **No knowledge**: the candidate set spans every configuration the
  zone could possibly be in given the observer's prior information.

Most real states sit in between. Perfect recall means candidate sets
only narrow over time.

### Projections: what visibility controls

Visibility declares **which projection of the zone's contents the
observer's knowledge state is informed by**. A projection is a
function from "full zone contents" to "some derived value."
Observers see (and remember) values of the projection; their
candidate set is consistent with those observed values.

Six projections, ordered by informativeness:

| Projection | What it reveals | What an observer with this projection knows |
|---|---|---|
| `identity` | the full multiset of object/resource identities | exact contents, fully resolved |
| `identity_set` | the *set* (not multiset) of identities present | which objects/types are present, ignoring duplicates |
| `count_by_type` | a map from type → count | how many of each type, no individuation |
| `count_only` | one integer: total count | how many things, nothing else |
| `existence_only` | one bit: empty or not | whether the zone has anything |
| `trivial` | nothing | no information at all |

These form a lattice ordered by informativeness:

```text
identity > identity_set > count_by_type > count_only > existence_only > trivial
```

Each step down "forgets" some structure of the full contents.

**Identity for resources** means "this zone holds N units of wood
and M units of brick" — for a fungible Resource, the identity-level
view is the count-by-type level. There is no per-unit identity
below that, because units have no individuated identity.

**Identity for cards** means the full multiset of cards, by suit and
rank — the per-card identification card games are built around.

The lattice is uniform: `identity` is the most informative
projection the contents support, whatever that means for the
contents' type.

### Per-observer visibility on zones

Each zone type fixes a per-observer projection — a mapping from
observer to the level at which it sees the zone's contents. This is
the model a zone type encodes:

```text
public_zone   : Zone<Card>     { composition: identity to all }
private_hand  : Zone<Card>     { composition: identity to owner, count_only to others }
hidden_deck   : Zone<Card>     { composition: count_only to all }
catan_hand    : Zone<Resource> { composition: count_by_type to owner, count_only to others }
```

The set of zone types is a closed kernel table (`ZONE_PROJECTIONS`
in `cardlang/stdlib/zones.py`, wrapped as the named aliases in
[library.md](../library.md), "Library zone types"). A game does not write
a `composition` block or declare a new zone type — it selects a named
type in its `zones {}` block, and the type carries the projection
(`hand[player] : Hand<player>`). Adding a projection profile is a
kernel-table addition, not a surface a game reaches.

**A family named bare is the acting player's own.** A zone family written
without its index (`hand`) means the acting player's instance, and that
reading exists only for a family indexed by player, whose members are
seats. A family indexed by team or by a position is always subscripted
(`captured[team_of(actor)]`, `pile[c]`); named bare, it is refused at
check time. So the instance a bare name reads is always one the acting
seat owns under its zone type's projection, and the information state
derives from that ownership. The rule holds wherever the engine keys a
family by the acting seat: a round's `source` names a family indexed by
player, and `player_holding` searches `hand[player]`, which a game calling
it must declare. A round's `into`
names the one pile every play lands on, so it is a single zone.
A bare team family is not read as the acting player's side's instance,
though the ownership the projection uses could key it so: no game asks
for that reading, and a refusal can grow into it by addition, where a
reading once given cannot be withdrawn without changing what existing
files mean.

### Per-observer visibility on moves

Visibility derives from the declared zone types: a move is observed
through each endpoint's projection (below), and the current language
has no per-move override. The grammar admits a `visibility:` clause on
a transfer, but the type checker rejects it — "visibility derives from
the declared zone types" — reserving the design for
[open-questions/move-level-visibility.md](../open-questions/move-level-visibility.md),
which asks when a move's epistemic effect must differ from what its
zones imply (a card passed face-down, a resource stolen and shown only
to the pair). No corpus game needs it yet.

### Observation events

A move from zone A to zone B transfers some sub-content. Observers
see the move through each side's projection:

- The **source projection** updates: A's contents shrink. Observers
  learn what left if their projection of A reveals it.
- The **destination projection** updates: B's contents grow.
  Observers learn what arrived if their projection of B reveals it.
- **Identity continuity** between source and destination is observed
  only if both projections support identity.

If A is `identity`-visible and B is `identity`-visible to observer
P, P sees the full move (specific object X went from A to B). If A
is `count_by_type` and B is `count_by_type`, P sees "one wood left
A, one wood arrived at B." If A is `identity` but B is
`count_only`, P observes a structurally weaker fact at the
destination — "a piece arrived" without learning its type.

**A seat's own decisions.** A seat asked to decide is told what it
is asked, and each pick it makes enters its own log as one record,
delivered to it alone at the moment the pick is made. A decision
asking for several cards is that many picks, each its own record,
so a seat part-way through a multi-card choice remembers exactly
the cards it has committed. The rule is the same on every route a
game is played by — the table, a native playout, OpenSpiel — so
one decision reads identically in a seat's information state
whichever route produced it.

**The public state at earlier nodes.** Every seat's log carries the
State Delta of each decision node, so the public state a seat was
shown at any earlier node follows from its log and the current state
(["Hidden information lives only in zones; state is
public"](#hidden-information-lives-only-in-zones-state-is-public)).

### Formal distinctions

From the dynamic epistemic logic and partial-observation game theory
literatures:

- **De re vs de dicto knowledge.** *De re* is positional/identity
  knowledge ("I know *this specific card* is the Ace of Spades").
  *De dicto* is existential ("I know there is an Ace of Spades
  somewhere in this zone"). For cards, the `identity` projection
  gives de re; lower projections give progressively weaker de dicto
  knowledge. For resources, de re knowledge doesn't exist — there
  are no individual identities for resource units to have. The
  strongest knowledge available for resources is `identity` =
  `count_by_type` (knowing the type breakdown), which is itself a
  de dicto claim. A shuffle of a resource zone is a no-op
  semantically.

- **Perfect recall vs imperfect recall.** Perfect recall means
  "players never forget information revealed to them, nor the order
  in which it was revealed" (Kuhn 1953). Perfect recall is the
  precondition for CFR's regret bounds and for the equivalence of
  mixed and behavioral strategies. Perfect recall is the default;
  imperfect recall is opt-in via the explicit `forget` operation.
  Under perfect recall, candidate sets only narrow over time.

- **Public vs private vs semi-private events.** A public event is
  one where all observers get the same `identity`-level projection;
  a private event is one where only a subset gets `identity` and
  others get `trivial`; a semi-private event is one where
  non-participants get a non-trivial weaker projection (typically
  `count_only` or `existence_only`), observing that something
  happened without learning what. These distinctions map directly
  onto projection assignment per observer.

### Higher-order knowledge is out of scope

The knowledge model is first-order: an observer's candidate set ranges
over zone contents (what *is* the case), with the de re / de dicto
refinement above. It does **not** model higher-order knowledge — "P knows
that Q knows X" — because no card game's *rules* read it. A survey of the
usual suspects confirms this. Hanabi's rules constrain hints to truthful,
complete facts about tile colours and values and never reference what a
player knows about another's knowledge; its famous higher-order reasoning
(finesses, conventions) is optional play layered on top, explicitly
outside the rules. Sheepshead's called partner is genuine *first-order*
private information — the partner's identity is known only to the partner
— with no rule reading knowledge-of-knowledge. The pattern generalizes:
rulebooks route every legality, resolution, and scoring condition through
observable card facts (and at most one layer of hidden state) precisely so
a referee can adjudicate them. Higher-order reasoning is real in optimal
*play* — Hanabi conventions, bluff modelling in Coup and bridge — but it
lives in strategy, not in the rules the DSL describes, and the candidate
sets the language already tracks are exactly what CFR / IS-MCTS consume.
Modelling belief-about-belief would add machinery no in-scope game
exercises. If a game ever surfaces a rule that reads second-order
knowledge, this is the decision to revisit.

### Native memory-affecting operations

| Operation | What it does | Effect on projections |
|---|---|---|
| `peek(target, observer)` | observer privately gains identity knowledge of the target | projection for observer becomes `identity`; emits private observation; other observers' projections unchanged |
| `reveal(target, observers = all)` | target is shown to observers (default: everyone) | projection for each named observer becomes `identity`; when `observers = all`, knowledge becomes common knowledge |
| `hide(target, hidden_from = all_except_owner)` | target's future projection is downgraded for the listed observers | downgrades to the zone's default-hidden projection; prior identity knowledge is preserved under perfect recall — observers remember what they saw |
| `shuffle(zone)` | the zone is shuffled (cards only; no-op on pure-resource zones) | preserves `count_by_type` and below; destroys any positional or per-card identity knowledge of zone contents |
| `announce(fact, observers = all)` | a propositional fact is communicated | observers' candidate sets updated by intersecting with `fact`; no physical zone change |
| `expose_top(zone)` | the top card flips face-up | shorthand for `reveal(zone.top, all)` |
| `deal(from, to, visibility)` | items move with per-recipient visibility | sequence of moves with per-recipient projection; emits implicit `count_only` semi-private observation to non-recipients (they see something moved) |
| `transfer(amount, from, to, visibility?)` | resource units move | analogous to `deal` for fungible quantities; per-observer projections per visibility clause or zone defaults |
| `muck(target)` | item leaves play to a trivial-projection zone | future zone projection is `trivial` for all observers; prior identity knowledge persists in observer histories (perfect recall) |
| `forget(observer, target)` | observer loses identity knowledge of the target | observer's projection of the target widens to the unseen universe; **breaks perfect recall** |

### `forget` is the escape hatch

`forget` is the only operation that breaks perfect recall. CFR's
regret bounds, the Kuhn-theorem equivalence of mixed and behavioral
strategies, and standard IS-MCTS guarantees no longer apply once a
game uses `forget`. The compiler emits a warning when `forget` is
used. Designers can express memory loss when a game demands it
(Cabo, Coup challenge resolutions, memory variants), but they're
informed of what they're giving up.

### OpenSpiel compilation

Provided no `forget` is used, the resulting game is perfect-recall
and CFR / IS-MCTS apply with standard regret bounds. Observation
events compile to per-player projection emissions; OpenSpiel's
information-state tensors flow through unchanged, generalized to
projection-shaped events.

Ahead of a true compilation pass, one general **runtime adapter** drives
OpenSpiel: every corpus game is registered as a `pyspiel.Game`, and the
readiness proofs (`tests/openspiel_ready/`) hold each to OpenSpiel's own
consistency tester with leak-free, perfect-recall information states. The
OpenSpiel state is `(seed, script, action history)`, and every query is answered
as a replay of that history through the runtime's `chooser` seam answers it — a
replay that suspends at the next decision via a `ChooserAbort` protocol. This
makes the state trivially cloneable (the property OpenSpiel exercises most) and
confirms the finite-action-space anchor end to end. A replay costs the whole
history, so a bounded pool of [[paused-run]]s, one per line walked, answers a
query one pick past a waiting run by advancing it rather than replaying; a run
advanced or closed is never read again, and the replay stays the definition the
pool is held to (`cardlang/openspiel/paused.py`). Neither the pool nor its
absence moves an information state. The game-agnostic encoder, explicit chance
nodes and the rest of the general compilation pass remain issue #139.

A game whose text draws nothing — a Chance-Free Game, see
[glossary/chance-free-game.md](../glossary/chance-free-game.md) — compiles with no
root chance node at all: it registers as `DETERMINISTIC`, declares no chance
outcomes, and opens on its first decision, so its information state is
available at the root rather than after a seed nobody chose. The licence is
derived from the game rather than declared by its author, and it is guarded
both ways: the classification names every drawing construct and refuses one it
does not know, and the run installs a generator that refuses every draw, so a
missed construct stops the game where it draws instead of yielding a tree that
silently omits real chance.

Info-set derivation is uniform across the corpus: every game's decisions run
on kernel sites that emit observation events, no Python mechanic exists (the
`instantiate` construct is deleted), and the readiness proofs cover
every corpus game ([kernel-migration.md](../kernel-migration.md)). The remaining
honesty line is scope, not derivation: no rules-level randomness remains —
every monolith-era rng gate (Coup's windows, claims, and targets; Tichu's
call windows and Dragon routing) is a real announced decision in the
observation stream. What stays reduced is named per game in its file
(Tichu's Mahjong wish and bomb variants, and the like), as scope, not as
hidden randomness.

### The Arrival Record

The kernel performs every movement, and it retains what it performed: each
zone carries an **Arrival Record** — per card now in the zone, the deciding
actor (`None` when no seat decided), the card value, and the source zone
address, in arrival order (`state.Zone`). "Who played this card" is two
facts, deliberately: the attributed actor and the source zone's owner — one
seat spelled twice, and kept the SAME seat under Delegated Play: a delegated
play's record stays the source owner's (Bridge's dummy), because every
observer derives a play's seat from the movement's source label while the
`chose` event is the [[decider]]'s alone, so a decider stored in the record
would be provenance no observer's stream entails. The decider's record is
the decision node and its private recall ("Delegated play"). Consumers read the record in place of
re-deriving attribution: a trick winner's pairing of seat against card is a
read, never a zip of seat order against pile contents, and participation is
nothing to declare — it derives from who acted, so a contract's dead seat is
stated exactly once, in the movement structure the game file already has.

The record is engine truth, mediated exactly as zone contents are: it enters
no observation event and no information state, and any surface that reads it
per-observer is bounded to zones whose type projects identity to every
observer (`PrimitiveReads.arrival_zones`, refused loud otherwise; the
`highest_trump_or_led_suit` call form guards the same predicate) — a
concealed zone's provenance is not derivable from any observer's stream, so
nothing may range over it, legality contexts included. Per-observer
provenance is therefore **derived from the observation stream, never stored
and then stripped**: a fact about an observed play persists exactly as long
as observation entails it, and washing is an invariance rather than an
operation — the record stores values only, so observationally equivalent
duplicate copies produce equal entries and every projection is invariant
under permuting them. The readiness proofs carry the executable form: the
provenance soundness rows (the engine record equals what every observer's
own log derives, per consumed zone), the wash pin (hidden-stock permutation
moves no information state), and the copy-purity pin (two replays of one
world serialize the record identically, so no per-object identity can hide
in it).

### A seat's knowledge, rendered

A seat's knowledge is derived once, as a
[Seat View](../glossary/seat-view.md) (`infostate.derive`): its zones through
their projections, the public state variables, and its own observation log.
Everything that shows a seat's knowledge renders that one value: the
information-state string OpenSpiel keys on, and the text a person reads
(`cardlang/play/view.py`, printed by `cardlang demo --view`). None of them reads
anything else of the World. A second derivation beside it would be a second
implementation of the very property the language exists to guarantee. The
mechanism is [design-notes/terminal-play.md](../design-notes/terminal-play.md).

- **An identity projection is a multiset.** A Seat View holds a zone's visible
  cards in one canonical order. A rendering may reorder them by the game's
  static declarations (the deck's suits, the `ranking:`), which depend on the
  multiset alone. The order the cards sit in is never shown.
- **An event's payload is a rendering.** Observation events carry zone labels
  and card renderings, not zones and cards, because the information state
  spells the log as each event's `repr`. A rendering shows them as the event
  spells them and derives no fact by parsing one (issue #666). It spells them
  so that no two distinct events read alike, since two logs shown as one would
  hide a difference the seat is entitled to.
- **A rendering is certified fact by fact.** The per-visible-fact matrix runs
  with the rendering as its subject. Every zone the seat sees, every state
  variable and every field of every event must move the rendering, and a hidden
  zone's content must not. The content probes come from the declared payload
  table (`observe.EVENT_PAYLOADS`), never from how one rendering spells an
  event, so one matrix certifies every rendering.
- **The whole log is rendered.** A seat with perfect recall knows every event,
  so a certified rendering shows all of them. A window onto the most recent
  events is a presentation choice for a session in which the rest stays
  reachable.
- **A decision's facts are not the seat's, except the one the seat is told.**
  Whose turn a position is, and what can be chosen, are facts of the decision
  node rather than of the Seat View. A rendering shows one only when a proof
  holds it for the seat; the seat's own turn is the one that qualifies, held by
  the swap proof, and every other such fact is the caller's to show beside the
  rendering. **Which decision a position is, the deciding seat is TOLD.** The
  kernel delivers it an `asked` [observation event](#observation-events) at
  every decision, from the one route a decision reaches the [Chooser](../glossary/chooser.md)
  by and before that Chooser is consulted, naming the phase it is asked in, the
  construct asking, how many picks it wants, and the zone the picks land in
  where the site knows that zone before the choice is made. So it reaches a
  Seat View the way every other observation does — through the log, with no
  second channel and no fact beside the view — and one derivation
  (`infostate.current_ask`) reads it for every consumer. A hand number still
  waits for a structural source (issue #573).

### What answers for a seat

A [Seat Policy](../glossary/seat-policy.md) answers for one seat at a decision
node: it is handed that seat's Seat View and the legal action ids, and it
answers one of those ids (`openspiel/seat_policy.py`). Every opponent that
fills a seat answers through it. The mechanism is
[design-notes/terminal-play.md](../design-notes/terminal-play.md).

- **A policy reads the Seat View, never the World.** Its signature is its
  whole input, so what it answers is constant across positions its seat cannot
  tell apart. An opponent that reads the World measures something else, and it
  is a type with its own name, never this one widened.
- **A policy reads what its seat is asked from that same view.** The `asked`
  observation is in the seat's log, so knowing a lead from a pass costs the
  interface nothing: the signature does not widen, and every later tier — a
  rule-based opponent, a trained policy, a language model — sees the fact the
  first one does. A policy that reconstructed the decision by scanning the log
  beside `infostate.current_ask` would be a second derivation of the seat's
  knowledge, which is the thing this design exists to prevent.
- **A line of play is `(seed, history)` played on through the replay
  chooser.** The recorded picks replay through the adapter's own chooser, and
  past them each seat's policy is asked where the adapter would pause. The view
  it is handed is derived inside the Chooser call, where every phase frame
  stands. One rule chooses the game's generator, and no policy draws from it.
- **A policy's randomness is a function of its seed and its view.** The
  uniform opponent draws from a digest of both, never from a stream. So one
  seed and one history name one line of play, however the line was reached.
- **A person at the table is a Seat Policy.** `cardlang play` shows the person
  their Seat View's text and a menu numbering the legal action ids by the
  adapter's own strings, and they answer with a number. Their controls end the
  line through their seat, and taking a pick back plays the line again without
  it.
- **A saved session names the game it was played in.** It carries the game's
  identity (`pipeline.game_identity`) and a format number beside the seed, the
  seat, each other seat's opponent and the history, and resuming refuses a
  mismatch in either before anything replays. A history of action ids carries
  no trace of its game: resumed against another game whose early picks happen
  to be legal, it would replay without complaint. Only the current format is
  read; a file in an earlier one is refused with the reason, never read as a
  guess at what it would have recorded.
- **Opponents are one closed table, and a person names every one.** An
  [Opponent](../glossary/opponent.md) is a row of `seat_policy.OPPONENTS`, and
  `cardlang play --vs WHO=OPPONENT` seats one at each seat the person does not
  take: a seat number, `all`, or `rest` for the seats not numbered, one item per
  `--vs`. Every listing of the opponents is rendered from the table, and an
  unknown name is refused listing it, never read as some other opponent. There
  is no default: a game with other seats and no `--vs` is refused before it is
  dealt, naming the seats, a command that seats them and every opponent,
  because an opponent nobody named is a choice nobody made, and the game would be
  judged against it. A resumed game seats the opponents its file records, and
  a `--vs` that names others is refused.
