# Design decisions

The design's load-bearing decisions, specified in detail. Each decision is
one file under [decisions/](decisions/), holding its whole section: the
sub-sections and bold-lead rulings that bound it travel with it. This index
lists every decision in reading order with its first sentence, and every
sub-section beneath its decision, so a search for any heading lands on the
file that holds it. It is generated from those files by
`python -m tools.decisions_index --write` and never edited by hand.
A citation of a section by quoted title (`decisions.md, "Surface totality"`)
names a heading listed here, or a bold lead-in inside one of the files.
Open questions — designs that aren't yet committed — live in
[open-questions/](open-questions/).

- [Typed phase outcomes](decisions/typed-phase-outcomes.md) -- Some phases have more than one legitimate way to end.
- [The boolean-as-sub-phase criterion](decisions/the-boolean-as-sub-phase-criterion.md) -- A boolean state variable that *gates rules* should be a sub-phase instead.
- [Sub-phase entry and exit](decisions/sub-phase-entry-and-exit.md) -- A sub-phase is entered and exited in one of three ways.
- [Sub-phase rule and legal-move deltas](decisions/sub-phase-rule-and-legal-move-deltas.md) -- A sub-phase inherits its parent's `active_rules` — the set in force in the parent at that moment, the parent's holding modes included.
- [Rule demand forms](decisions/rule-demand-forms.md) -- A rule's `demands:` clause names **a candidate-card set** — an expression returning the cards a legal move may use, filtering a zone.
- [Rule exemption (`exempts:`)](decisions/rule-exemption-exempts.md) -- A rule may declare `exempts: <card-set expr>` alongside (or instead of) `demands:`.
- [Round configuration vs rules](decisions/round-configuration-vs-rules.md) -- Some phase-level configuration is *not* a rule even though it looks like one.
- [Trick Order](decisions/trick-order-decision.md) -- A trick's resolution and its follow legality both rest on three facts about each card: is it a **trump**, what **class** does it follow as, and how **strong** is it within that class.
- [Auctions, polls and betting rings are `turns` plus `offer`](decisions/auctions-polls-and-betting-rings-are-turns-plus-offer.md) -- A bidding ring, a betting street, a quiescence-lap poll and a declaration round are one loop: walk the seats from a start seat, over a participants predicate re-evaluated each turn, until a predicate holds, asking each seat one flat offering.
- [The `ranking:` declaration: enumeration or convention](decisions/the-ranking-declaration-enumeration-or-convention.md) -- `ranking:` declares the game's rank strength order, strongest first.
- [The `suit ranking:` declaration](decisions/the-suit-ranking-declaration.md) -- `suit ranking:` declares the game's Suit Ranking, strongest first and space-separated, as `ranking:` declares ranks: `suit ranking: spades hearts diamonds clubs`.
- [Declared parameter domains](decisions/declared-parameter-domains.md) -- A `move_type` may take any number of parameters (Go Fish's `ask(target : Player, rank : Rank)`), each drawn from a declared, enumerable value-domain.
  - [The integer `choose` domain](decisions/declared-parameter-domains.md#the-integer-choose-domain)
- [The climbing form of `round`](decisions/the-climbing-form-of-round.md) -- Combination-climbing games (Big Two, President, Tichu) run on a third configuration of the kernel `round`.
- [Combination Catalogues](decisions/combination-catalogues.md) -- A climbing game declares its plays in its own file: a **Combination Catalogue** names the card multisets a play may be, and a **follows function** says which of them a seat may play over the standing play.
- [The `turns` form](decisions/the-turns-form.md) -- The turn loop beneath the round forms — for every ring whose turn is a *body of statements*: a single `offer` (an auction, a poll, a betting street — "Auctions, polls and betting rings are `turns` plus `offer`" below), draw-then-discard shapes, ask-and-resolve shapes, anything with statement structure per turn.
- [No implicit actions](decisions/no-implicit-actions.md) -- Every decision point has at least one legal move, and the engine neither invents one nor silently skips the decision.
- [Single-actor decisions: the `as` block](decisions/single-actor-decisions-the-as-block.md) -- When one *named* player decides — a chosen discard, a follower's answer to a led card, a victim flipping one of their own cards — the binder is `as`:
- [Naming the acting player twice](decisions/naming-the-acting-player-twice.md) -- A construct that binds a seat *and* makes that seat the acting player gives the same player two names: its own binder, and the `actor` pronoun.
- [State scoping (lexical)](decisions/state-scoping-lexical.md) -- A variable is scoped to the phase that lexically encloses its declaration.
- [Loop termination semantics](decisions/loop-termination-semantics.md) -- A `repeat until <pred>` clause on a phase (or `repeat until <pred>` on a phase-body block) is **continuously evaluated**: the loop terminates as soon as the predicate becomes true, including mid-iteration.
- [Game length as a declared contract](decisions/game-length-as-a-declared-contract.md) -- Every game declares `max_length: <n>`, a positive bound on the number of picks a run makes.
- [Loop lifecycle: `before_each` and `after_each`](decisions/loop-lifecycle-before-each-and-after-each.md) -- A `repeat until` phase runs per-iteration setup and teardown through two optional hooks, siblings of its `state` block and distinct from its sub-phases:
- [Mutation semantics](decisions/mutation-semantics.md) -- **Only a declared state variable can be written.**
- [Typed object model](decisions/typed-object-model.md) -- The language has a typed object model with built-in types and convenience sugar that rewrites to underlying forms.
- [`Any` means the top, never a failed lookup](decisions/any-means-the-top-never-a-failed-lookup.md) -- `Any` is the type checker's top: it is compatible with every type in both directions, and every operand guard short-circuits on it.
- [Resource amount syntax](decisions/resource-amount-syntax.md) -- A resource quantity in a transfer is written `<count> <type>` — the count (an integer expression, or `all`) followed by the resource type name:
- [Resource transfer failure](decisions/resource-transfer-failure.md) -- A `transfer` whose source lacks the requested amount is a hard error: the move is illegal.
- [Move, Transfer, and what `move_type` is called](decisions/move-transfer-and-what-move-type-is-called.md) -- A **Move** is one played instance of a Move Type bound to its Parameters; a **Transfer** is one relocation between zones.
- [The operation vocabulary](decisions/the-operation-vocabulary.md) -- Games relocate cards and resources, reveal and hide them, shuffle and rotate.
- [Joint-predicate selection](decisions/joint-predicate-selection.md) -- A transfer's per-card `where` filter tests each candidate alone — `chosen K cards where <pred>` can never say "these K cards *together* form a valid group," which is the load-bearing test of every meld-family game.
- [Meld groups: flattened zone families](decisions/meld-groups-flattened-zone-families.md) -- There is no first-class meld-group object.
- [The expression register](decisions/the-expression-register.md) -- The expression layer speaks the same English register as the statement layer: queries and predicates are rulebook sentences, and their binders are implicit.
- [Named functions](decisions/named-functions.md) -- A game factors an expression it would otherwise repeat with a **named function** — a parameterized expression callable wherever an expression appears:
- [Named procedures](decisions/named-procedures.md) -- A game factors a *statement sequence* it would otherwise repeat with a **named procedure** — the statement layer's sibling of the named function above:
- [Knowledge, visibility, and the projection model](decisions/knowledge-visibility-and-the-projection-model.md) -- Knowledge over zone contents is the primitive concept for everything the language models about information asymmetry.
  - [Honest Play is assumed, so a rule reading concealed cards is mis-modelled](decisions/knowledge-visibility-and-the-projection-model.md#honest-play-is-assumed-so-a-rule-reading-concealed-cards-is-mis-modelled)
  - [Hidden information lives only in zones; state is public](decisions/knowledge-visibility-and-the-projection-model.md#hidden-information-lives-only-in-zones-state-is-public)
  - [Knowledge as candidate sets](decisions/knowledge-visibility-and-the-projection-model.md#knowledge-as-candidate-sets)
  - [Projections: what visibility controls](decisions/knowledge-visibility-and-the-projection-model.md#projections-what-visibility-controls)
  - [Per-observer visibility on zones](decisions/knowledge-visibility-and-the-projection-model.md#per-observer-visibility-on-zones)
  - [Per-observer visibility on moves](decisions/knowledge-visibility-and-the-projection-model.md#per-observer-visibility-on-moves)
  - [Observation events](decisions/knowledge-visibility-and-the-projection-model.md#observation-events)
  - [Formal distinctions](decisions/knowledge-visibility-and-the-projection-model.md#formal-distinctions)
  - [Higher-order knowledge is out of scope](decisions/knowledge-visibility-and-the-projection-model.md#higher-order-knowledge-is-out-of-scope)
  - [Native memory-affecting operations](decisions/knowledge-visibility-and-the-projection-model.md#native-memory-affecting-operations)
  - [`forget` is the escape hatch](decisions/knowledge-visibility-and-the-projection-model.md#forget-is-the-escape-hatch)
  - [OpenSpiel compilation](decisions/knowledge-visibility-and-the-projection-model.md#openspiel-compilation)
  - [The Arrival Record](decisions/knowledge-visibility-and-the-projection-model.md#the-arrival-record)
  - [A seat's knowledge, rendered](decisions/knowledge-visibility-and-the-projection-model.md#a-seats-knowledge-rendered)
  - [What answers for a seat](decisions/knowledge-visibility-and-the-projection-model.md#what-answers-for-a-seat)
- [Position domains and positional zones](decisions/position-domains-and-positional-zones.md) -- Solitaire layouts (and any game whose rules address *places* — columns, cells, piles-by-location) are described with **declared position domains**: per-game, finite, integer-keyed value domains, declared in a game-level `positions { }` block:
- [Component sets: cards and pieces](decisions/component-sets-cards-and-pieces.md) -- A game's individuated zone content is declared with exactly one head clause — `cards: <deck>` (a card deck) or `pieces: <set>` (a piece set) — naming one entry of the closed component-set registry ([library.md](library.md), "Built-in component sets").
- [Zone capacity](decisions/zone-capacity.md) -- Each library zone type carries a **capacity** — a column of the zone-type registry ([library.md](library.md), "Library zone types"), total over every row.
- [Boards and cells](decisions/boards-and-cells.md) -- A game with a spatial board declares it with a `board: <family>(<args>)` clause: it selects a [Board Family](glossary/board-family.md) from the closed `BOARDS` registry ([library.md](library.md), "Built-in boards") and gives its integer arguments.
  - [Transfer: directions, frames, and the class-1 verbs](decisions/boards-and-cells.md#transfer-directions-frames-and-the-class-1-verbs)
  - [Declared adjacency, and which family answers which verb](decisions/boards-and-cells.md#declared-adjacency-and-which-family-answers-which-verb)
- [Game result: `winner:` and `loser:`](decisions/game-result-winner-and-loser.md) -- A game declares its terminal result with exactly one top-level clause, evaluated against the final state when the phase tree finishes:
- [Player-collection queries](decisions/player-collection-queries.md) -- Four expression forms query the player ring by a predicate:
- [Scoring has no constructs of its own](decisions/scoring-has-no-constructs-of-its-own.md) -- Scoring is arithmetic on state, and the language already does arithmetic on state.
- [`choose` as expression](decisions/choose-as-expression.md) -- `choose` elicits an integer decision from the acting player.
- [Bidding patterns](decisions/bidding-patterns.md) -- The corpus has three structurally distinct bidding patterns; bid *value* and bid *meaning* are per-game concerns interpreted by each game's scoring code rather than shared via a mechanic parameter.
- [Delegated play](decisions/delegated-play.md) -- A move is normally chosen by the player it's attributed to: the active player picks from their own hand, submits a bid on their own behalf.
- [Simultaneous moves and atomic effect](decisions/simultaneous-moves-and-atomic-effect.md) -- Some game steps consist of several moves that observers must see as a single event, not as a sequence.
- [Off-the-clock windows](decisions/off-the-clock-windows.md) -- Some rules offer a move "at any time" rather than on a turn: Tichu's tichu call (any time before the caller's first play), Doppelkopf's Re/Kontra and level announcements (any time during the play, gated by the announcer's own hand size).
- [A move type's stake](decisions/a-move-types-stake.md) -- A move type may say, on its own line under its name and before its `when:`, that taking it is a **Wager** or a **Concession** ([glossary/stake.md](glossary/stake.md)):
- [Interactive decisions: a kernel and an in-DSL standard library](decisions/interactive-decisions-a-kernel-and-an-in-dsl-standard-library.md) -- The structure of a game (zones, phases, dealing), trick-taking, and scoring are directly expressible.
- [Surface totality](decisions/surface-totality.md) -- The corpus-first gate ([principles.md](principles.md), "Three implementations before abstracting") governs *admission*: a construct or axis enters the language only when games demonstrate the need.
- [Closed-domain completeness](decisions/closed-domain-completeness.md) -- Surface totality's principle, applied below the grammar.
  - [Every refusal carries its Diagnostic Code](decisions/closed-domain-completeness.md#every-refusal-carries-its-diagnostic-code)
  - [Allow-list, never deny-list](decisions/closed-domain-completeness.md#allow-list-never-deny-list)
  - [Pin the derivation, not just the instance](decisions/closed-domain-completeness.md#pin-the-derivation-not-just-the-instance)
  - [Prefer the guard you cannot need](decisions/closed-domain-completeness.md#prefer-the-guard-you-cannot-need)
  - [The machinery is guarded once](decisions/closed-domain-completeness.md#the-machinery-is-guarded-once)
  - [Reachability ranks the work](decisions/closed-domain-completeness.md#reachability-ranks-the-work)
- [Family libraries](decisions/family-libraries.md) -- A **family library** is the import tier between game-local definitions and the standard library.
