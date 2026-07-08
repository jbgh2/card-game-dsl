# Declared parameter domains (Rank/Player) + arity-N move types — design

*Partial resolution of [open-questions/move-parameter-domains.md](../../open-questions/move-parameter-domains.md).
Approved scope: the **fixed-from-type** domains (`Rank`, `Player`), **arity-N**
move-type parameters, and parameter enumeration by plain `offer` — proven in
the corpus by promoting **Go Fish (four-player)**. The **bounded-`Integer`**
axis and the `choose integer` reconciliation are a deliberately deferred
follow-on (see "Deferred", below); this spec settles everything else the open
question raises.*

## Goal

Kill the **nullary-move-type explosion**. A player decision that ranges over
something other than a suit — "ask *any player* for *any rank* you hold"
(Go Fish), "meld a set of *any rank*" (Canasta), "play a card worth *N*"
(Ninety-Nine) — currently has no faithful encoding: a `move_type` parameter
enumerates only `Suit`/`Suit?`, only an auction `round` enumerates parameters
at all, and a move type carries at most one parameter. Authors are forced to
hand-compile the enumeration as a fan of nullary move types (Ninety-Nine's 14
`play_N`), or to distort the rules until they fit `Suit` (Go Fish's "ask a
fixed seat-relation for a rank from a fixed cycle").

That hand-compilation is exactly the contract the **OpenSpiel** target needs
the *language* to own. OpenSpiel mandates one fixed, enumerable action set
(`num_distinct_actions`) declared up front, with per-state legality as a mask
over it. A move type whose parameters range over **declared finite domains**
*is* that contract by construction — the adapter reads the action space off the
declaration instead of reverse-engineering it from a fan of hand-written moves.

This is the load-bearing acceptance criterion of the project (CLAUDE.md): the
new surface must not merely run, it must **derive information sets**. Go Fish is
chosen precisely because its central move is information-rich — an ask is public
and, because you may only ask for a rank you hold, it *leaks* that you hold it —
so proving Go Fish's info sets derive is proving the feature earns its place.

## Why this is the parameterization flex, not a new kernel mechanism

The doctrine (CLAUDE.md "tight kernel; parameterization is the flex";
[decisions.md](../../decisions.md) "The auction form of `round`"): the kernel
owns *mechanism*, the game supplies *values*. The test is **does the kernel gain
a verb, or does the game gain vocabulary?** This feature is the latter, at its
purest:

- **No new kernel mechanism.** The domain-expansion loop already exists
  (`mechanics.AuctionForm.candidates`: expand a declared domain, guard-filter,
  present one flat candidate list, resolve with one chooser draw, announce the
  chosen value uniformly). We generalize it from a single parameter to a
  **fold over a parameter tuple**, and reuse it at the `offer` decision site —
  which *removes* an asymmetry (an auction `round` could enumerate a parameter,
  a plain `offer` could not) rather than adding a form. The single decision
  mechanism is unchanged: one flat candidate list + one chooser draw + one
  uniform observation.
- **Games gain only declarations.** A move's signature declares typed domains;
  the checker validates them; the kernel expands them. Go Fish's give-all-
  matching transfer, the go-fish draw, and go-again all stay in the effect body,
  written in the existing closed verbs. No ask-shaped mechanic enters the
  kernel.
- **It makes the language more uniform, not less.** `FunctionDef.params` is
  already a tuple; a `move_type` carrying at most one parameter was the anomaly.
  Arity-N brings the two into line.

The flex has a boundary worth stating. Three regimes already live in the
encoder, and this feature is regime 1:

1. **Tuples over small closed static domains** → cross-product + legality mask.
   *This feature.* Dependent choices flatten into it: "a rank *you hold*" is a
   guard-filtered subset of the static `Rank` domain; a static superset with a
   per-state mask is the OpenSpiel idiom and covers a surprising amount.
2. **State-dependent domain with a pre-existing static id space** → the `Card`
   carve-out (the live hand enumerates the candidates; the action ids come from
   the shared card block). Unchanged by this spec; subsumed by the same
   `params` machinery.
3. **Set-valued / combinatorial choices** ("play *a combination*") → the
   combo-codec block (the climb engine). Out of scope.

A choice whose domain has **no small static superset** is where parameterization
stops being the answer and a new-mechanism conversation begins. Nothing in the
current corpus or the candidate pipeline crosses that line.

## Scope

**Built and proven in this pass:**

- `enumerate_domain` gains `Rank` and `Player`.
- `move_type` parameters become **arity-N** (a parameter *tuple*); enumeration
  is the guard-filtered cross-product, in declaration order.
- Plain `offer` enumerates a parameterized (including multi-parameter) move type
  the way `round offering` already does.
- **Go Fish (four-player)** enters `docs/games/` as a complete, runnable,
  OpenSpiel-proven corpus game — the totality witness.

**Deferred to a focused follow-on (own spec → plan → build):** bounded-`Integer`
parameter domains and the `choose integer in lo..hi` reconciliation (retire the
`_MAX_CHOOSE = 52` magic constant and the `lo == 0` / identity-map assumption in
`encoding.py`; decide reject-vs-widen-vs-mask for a runtime bound). Oh Hell's
`choose integer in 0 .. hand_size` is that follow-on's in-corpus home. The
follow-on should also decide whether to **warn on a large declared action
space**, since bounded-`Integer` × bounded-`Integer` is the first place the
cross-product can grow beyond the small closed sets this pass deals in.

**Behavior-preserving for existing games.** Single-parameter enumeration is
exactly the 1-tuple case of the fold; no existing chooser draw, action id, or
observation changes. All goldens pass unchanged under `PYTHONHASHSEED=0`.

## The design

### A. Surface — arity-N parameters

A `move_type` takes zero or more comma-separated parameters:

```
move_type ask(target : Player, rank : Rank) {
  when:  target != actor
         and (count of hand[actor] where c => c.rank == rank) > 0
  effect { … }        // give-all-matching or "go fish"; sets go-again
}
```

- **AST.** `MoveTypeDef.param : MoveParam | None` becomes
  `params : tuple[MoveParam, …]` (empty tuple = nullary), mirroring the existing
  `FunctionDef.params : tuple[MoveParam, …]`. `MoveParam` is unchanged.
- **Grammar.** The `move_param` production becomes a comma-separated list inside
  the parens (reuse the function-parameter-list production if practical).
- **Arity is not two.** Go Fish is the N = 2 witness; the semantics are a fold,
  so N = 0 (today's nullary moves), N = 1 (Bridge `submit_bid`, Schnapsen
  `play_card`), and N = 3 fall out with no new code path. The named N = 3
  consumer on the horizon is the **Authors / Quartets** family —
  `ask(target : Player, rank : Rank, suit : Suit)` for a specific card
  (4 × 13 × 4) — and, on the generalization path, Cluedo's
  `suggest(suspect, weapon, room)`. The spec commits to arity-N so "Go Fish
  needs two" never ossifies into "the feature is two".

### B. Domains and totality

`enumerate_domain` grows two cases:

- **`Rank`** → the game's declared ranks, in rank order.
- **`Player`** → the seats `0 .. num_players − 1`, in seat order. A compiled
  game has a **fixed** player count (`driver.py`/`openspiel/game.py` instantiate
  `players.low`; a declared `players: 3-6` range is used only for deck-sizing),
  so `Player` is a closed finite set — *not* the bounded-`Integer` problem.

Two consequences for the function's shape:

- `enumerate_domain` needs the game/runtime in scope: neither the rank set nor
  the seat set is derivable from the type-name string alone. As a side-fix,
  `Suit` should enumerate the **game's declared** suits rather than the module
  `SUITS` constant (correctness for stripped decks; harmless for Go Fish's full
  52).
- **`Card` stays state-dependent** (the live hand; `mechanics.candidates`), with
  its existing single-move / card-block encoding.

Surface totality (every accepted combination implemented + tested, or statically
rejected with a message — [decisions.md](../../decisions.md) "Surface
totality"):

- Multi-parameter enumeration is restricted to the **fixed-from-type** domains
  (`Suit`/`Suit?`, `Rank`, `Player`). A `Card` parameter **combined with any
  other parameter** is rejected at resolve time with a clear message (its domain
  is the live hand and its action ids are the card block — folding it into a
  cross-product is a separate design). At most one `Card` parameter total, and
  only as the sole parameter, for now.
- Bounded-`Integer` as a parameter type is rejected at resolve time (deferred),
  with a message pointing at the follow-on — never parsed-and-ignored.

### C. Enumeration semantics

Parameters enumerate in **declaration order**, leftmost = outermost loop, each
domain in its canonical order (seats in seat order, ranks in rank order). The
guard is evaluated **once per full tuple**, with every parameter bound; only
guard-true tuples become candidates. The flattened candidate list is therefore
deterministic. Single-parameter behavior today is exactly the 1-tuple case, so
Bridge/Schnapsen/Skat/Pinochle enumerations are byte-identical.

### D. OpenSpiel encoding

The vocabulary key becomes `(name, value-tuple)`. The static action space is the
**full cross-product** of the declared domains — Go Fish's `ask` contributes
4 × 13 = 52 action ids — and per-state legality (self-mask; "a rank you hold";
a dropped-out target) is the **mask** over it. `num_distinct_actions` is fixed
and declared-by-construction. `encode`/`decode` handle the value-tuple;
`observe.render` renders a tuple parameter readably (`ask(0, J)` rather than
`ask((0, 'J'))`).

### E. Info-set derivation — the load-bearing criterion

The chosen ask is announced publicly through the **existing** `_offer →
observe.announce` path: `("announce", A, ("ask", (B, R)))` reaches every
observer, so each observer's derived knowledge gains "A asked B for R" and — via
the guard "you may only ask for a rank you hold" — "A holds ≥ 1 R". Give-all-
matching transfer, "go fish", the stock draw (private to the asker unless the
drawn card matches the asked rank and is shown), and book completion all emit
through the existing zone projections. Because info sets derive from **emitted
observations, not legal-action masks** ([decisions.md](../../decisions.md)
"Hidden information lives only in zones; state is public"), the *unchosen* legal
asks do not leak; only the chosen ask reveals its rank.

Go Fish has **no pass** — every turn forces an ask — so the four-proof
`openspiel_ready` harness (indistinguishability under hidden-card swaps,
soundness, perfect recall, conformance) is **not vacuous** here, unlike Bridge's
pass-only greedy-replay line (CLAUDE.md caveat).

**Additionally**, a dedicated observational test asserts the exact semantic
Go Fish was chosen to prove — *after A asks B for R, a third observer C's
information state reflects that A holds R* — mirroring the dedicated tests that
cover Coup's influence flips, Schnapsen's leads, and Skat's pickup rather than
leaning on greedy replay. This is additive proof, not a rescue.

### F. Go Fish — the corpus game (Pagat-faithful)

Rules re-derived live from pagat.com (the stress-branch file was unaudited; five
of eleven audited stress games had silently faked rules). Standard game:

- **Players:** four (pinned ≥ 3 on purpose — at two players the target domain
  degenerates to size one and the `Player` axis is never exercised; four gives
  three real targets, so self-masking and multi-candidate `Player`
  enumeration/ordering are genuinely tested). Standard 52-card deck, **five**
  cards dealt to each; the rest form a face-down stock.
- **A turn:** the current player asks a named opponent for a named rank they
  themselves hold (`offer [ask]`). If the opponent holds cards of that rank they
  give **all** of them, and the asker **goes again**. Otherwise "go fish": the
  asker draws the top stock card; if it is the asked rank they show it and go
  again, otherwise they keep it and the turn passes left.
- **Books:** four of a rank is a book — shown and set aside.
- **End & winner:** the game ends when **any hand empties or the stock runs
  out**; the most books wins. (No empty-hand refill — this corrects the stress
  file's fabricated refill.)

Zone / state modeling:

- `hand[player]` — hidden to non-owners (the standard hand projection).
- `stock` — a face-down draw pile; the asker sees only the card they draw (it
  moves into their hand), which is private unless it matches the asked rank.
- **Book count is public state, not hidden contents** ([decisions.md](../../decisions.md)
  "Hidden information lives only in zones; state is public"): `books[player] :
  Integer`, with the four booked cards moved to an out-of-play discard. A
  completed book is announced (shown) before the cards leave play.
- The turn structure (go-again loop, draw-and-maybe-continue, end checks) is an
  imperative phase body — the Oh Hell / stress-file pattern, which already runs
  green; only the ask changes from a `choose`-pair workaround to a real
  parameterized `offer`.

Full `docs/games/go-fish.cardlang` + `docs/games/go-fish.md`; a non-player must
be able to read the `.md` cold and play a hand (the corpus acceptance test).

### G. AST blast radius

`param → params` is low-risk (the `FunctionDef.params` precedent) but **not
localized**. Touched:

- **Front end:** `parse.py` (grammar + builder), `ast/nodes.py`,
  `typecheck.py`, `ir.py`, `resolve.py` (relax the two walls: `offer`-rejects-
  params and round-vocabulary-rejects-non-`Suit`/`Card`; add the new totality
  rejections), plus the `.param` readers in `openspiel/encoding.py`.
- **Runtime:** `runtime/mechanics.py` (`enumerate_domain`; the `candidates`
  fold), `runtime/execute.py` (`_offer` enumerates + resolves a parameterized
  move), `runtime/evaluate.py` (bind the param tuple), `runtime/observe.py`
  (`render` a tuple param).
- **Corpus (re-run green in the same change — games are the living spec):**
  Bridge `submit_bid(strain : Suit?)`, Skat `declare_suit(s : Suit)`, Pinochle
  `declare_trump_suit(s : Suit)`, Schnapsen `play_card(c : Card)` +
  `declare_marriage(s : Suit)`. French Tarot (nullary bids) re-runs as part of
  the full suite.

## Totality & docs hygiene (on landing)

Per [maintaining.md](../../maintaining.md):

- **Promote to [decisions.md](../../decisions.md):** the settled surface —
  arity-N parameters, the `Rank`/`Player` fixed-from-type domains, and
  parameter enumeration by plain `offer`. Fold it into (or beside) "The Card
  move-parameter domain", widening the enumerable-domain set to
  `{Suit, Suit?, Rank, Player, Card}` and noting Card's multi-param restriction.
- **Rewrite** `open-questions/move-parameter-domains.md` down to the residual
  **bounded-`Integer` + `choose` reconciliation** scope (do not leave a
  "resolved" stub); update `open-questions/_index.md` accordingly.
- **Corpus roster:** add Go Fish to the CLAUDE.md corpus list. Leave the
  `appendix.md` catalogue for the next wholesale refresh — it is a stable
  reference table, not a living document (maintaining.md rule 6).

## Acceptance criteria

1. `ask(target : Player, rank : Rank)` parses, type-checks, resolves, and
   enumerates the guard-filtered Player × Rank cross-product as one flat
   candidate list under a plain `offer`.
2. Go Fish runs to completion across a seed sweep and loads as a `pyspiel.Game`
   with a fixed `num_distinct_actions` = card block + `ask` cross-product +
   any nullary moves.
3. The four `openspiel_ready` proofs pass for Go Fish, **and** the dedicated
   observational test (§E) passes.
4. Every existing corpus game re-runs green; all goldens byte-identical under
   `PYTHONHASHSEED=0`.
5. Totality: every accepted parameter combination is implemented + tested, or
   statically rejected with a clear message (Card-with-others; bounded-`Integer`
   parameter → deferred message). No parsed-and-ignored surface.
6. `mypy` (bare) and `pytest -q` both green.

## Deferred / out of scope

- **Bounded-`Integer` parameters and the `choose` reconciliation** — the
  follow-on (own spec). Ninety-Nine and the `_MAX_CHOOSE` retirement live there.
- **`Card` in a multi-parameter move** — statically rejected until a game needs
  it.
- **Set-valued parameters** (a parameter ranging over card *combinations*) — the
  combo-codec regime; unrelated.

## Risks

- **Info-set derivation is the real bar, not "it runs."** The go-fish stock draw
  (private-unless-shown) and the "you hold it" guard leak are the subtle points;
  §E's dedicated test exists to catch a silent mis-derivation that the greedy
  harness would miss.
- **Blast radius is mechanical but wide.** The `param → params` migration must
  land with every parameterized-move game re-run in the same change, or a game
  file drifts out of lock-step (maintaining.md rule 2).
