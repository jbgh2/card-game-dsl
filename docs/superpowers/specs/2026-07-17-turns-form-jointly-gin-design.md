# The `turns` form, joint-predicate selection, and Gin Rummy — design

**Settles the turn-loop-form question (promoted to
[decisions.md](../../decisions.md) "The `turns` form"; its file is deleted) and consumes the recorded starting
point of [open-questions/meld-groups.md](../../open-questions/meld-groups.md)
(joint-predicate selection is built; the question narrows to first-class
groups, forced next by Canasta).** Anchors: **Gin Rummy** (new corpus game,
anchoring both constructs) and **Go Fish** (existing corpus game, migrating
onto the go-again axis). President was the open question's named anchor but
its corpus encoding has no turn loop — its outer loop is per-trick
(`repeat until … { round climb … }`, the climb owning rotation), so it is
out, and the roadmap bullet claiming it is corrected in this change.

## 1. The `turns` form — the loop beneath the round forms

```
turns <binder> from <leader-expr> over <participants-expr>
      until <pred> [again <state-var>] {
  <statements — binder bound to the current player, who is also the actor>
}
```

- **Binding.** Exactly `for each`'s per-iteration semantics: the binder names
  the current player and `acting_as` binds them (the seat wall at
  `Ctx.acting_as` protects the bind). The body is ordinary statements. The
  dividing line from the open question stands: a turn that is one flat
  candidate list is an auction-form configuration; `turns` is for a body of
  statements per turn.
- **Rotation.** Owned by the form: advance in game direction to the next
  player satisfying the participants predicate, re-evaluated at each advance
  (elimination falls out). No `direction` override clause — no corpus user,
  so it is not grammar (surface totality; recorded residual).
- **Termination.** `until <pred>` is checked at each turn boundary, before
  the turn is offered. Gin: `knocked or number of cards in deck <= 2`.
- **Go-again axis.** `again <state-var>` names a declared Boolean state
  variable. The body's move effects write it (an ordinary fact, written on
  every path); after each turn the form reads it — true means the same
  player takes the next turn. Declarative: no new statement verb, no
  positional-validity class (the named-procedures lesson), the form owns all
  rotation. Go Fish's `ask` writes `went_again := …` instead of mutating a
  cursor.
- **Pipeline.** A new `Stmt` node (`Turns`); the full construct row exactly
  as the `as` block was built — every `assert_never` statement dispatcher
  gains an arm (mypy-forced), the two generic walkers (`expand`,
  `openspiel/encoding`) reach the body by reflection, deckcheck treats the
  body like `repeat until` (not statically boundable — the zero-iteration
  execution is always possible), IR emits a `turns` node.
- **Observations / info sets.** The form emits nothing new: the body's
  decisions already emit through their own sites, and rotation is derivable
  from state. Acceptance is the standard instrument: playouts plus
  `tests/openspiel_ready/` proofs for both anchor games.

## 2. Joint-predicate selection — movement surface

```
move chosen some cards from hand[p] where jointly gin_valid_meld(cards) to meldA[p]
```

- **`where jointly <pred>`** binds **`cards`** (the candidate *set*,
  `Collection<Card>`) instead of the per-card `card` binder — the "these K
  cards together form a valid group" test that per-card filtering cannot
  express (the meld-groups question's core gap).
- **Amount `some`** (new): any non-empty subset satisfying the joint
  predicate — the predicate owns size constraints. `chosen <K> cards where
  jointly <pred>` selects exactly-K subsets; the semantics is uniform
  (candidate subsets of the source, sized per the amount, filtered by the
  joint predicate).
- **Chooser / encoding.** Candidates are the enumerated satisfying subsets
  (≤ 2^11 for Gin before filtering — cheap). OpenSpiel encodes set-valued
  actions through the existing climb-form combo-codec precedent.
- **Totality walls.** `jointly` requires `chosen` (a dealt or `random`
  jointly-selection is rejected loudly; recorded). `some` requires `jointly`
  (rejected otherwise; recorded). The rest of the movement matrix
  (verb × selection × amount × filter × destination) is enumerated in the
  audit ledger; every unimplemented cell is a loud wall.

## 3. Gin Rummy (standard Pagat, 2 players, full fidelity)

Rules source: https://www.pagat.com/rummy/ginrummy.html (fetched live).

- **Game-local pure primitives** (the Cribbage/Pinochle/Skat pattern):
  - `gin_card_points(c)` — A=1, pip value, face=10. (The `card_value` deck
    table is empty for standard52 — the stress-branch finding — so the
    points are a primitive, like Cribbage's `peg_value`.)
  - `gin_valid_meld(cards)` — set (3–4 same rank) or run (3+ consecutive,
    same suit, ace low).
  - `gin_deadwood(zone)` — minimal deadwood over all partitions. Needed by
    the knock *guard* in every design: knock legality is "some arrangement
    has ≤ 10 deadwood", which is the optimal partition.
  - `gin_arrange_ok(cards, rest)` — `cards` is a valid meld AND
    `gin_deadwood(rest)` ≤ 10, so every reachable arrangement stays
    knock-legal (totality under random play — the stress probe's staging
    mechanic almost never melded).
  - `gin_extends(card, meld-zone)` — layoff legality.
- **Flow.**
  1. *Deal*: 10 each, 21st card up (the upcard), rest is stock.
  2. *Upcard ritual* (pre-loop): non-dealer offered take/pass; on pass the
     dealer is offered; on both passing the non-dealer draws from stock.
     Whoever took a card completes turn one (discard) pre-loop; the `turns`
     loop starts from the other player.
  3. *Play*: `turns p … until knocked or number of cards in deck <= 2`
     — draw from stock or take the top discard, then discard or knock. The
     "took the discard → must discard a different card" rule keeps the
     stress branch's proven staging-zone shape (structural enforcement, no
     card-identity comparison).
  4. *Showdown* (skipped entirely on the stock-low no-result): the knocker
     declares melds as jointly-selection decisions (each guarded by
     `gin_arrange_ok` — the `finish` move is guarded by flat remaining
     points ≤ 10, which the arrange guard makes always reachable); the
     defender declares theirs (unguarded budget — suboptimal defender
     arrangement is rule-legal); the defender lays off per-card onto the
     knocker's shown melds (`lay_off_a/b/c(c : Card)` + `done`, three
     bounded slots since 11 cards hold at most 3 melds; laying off is
     forbidden when the knocker went gin).
  5. *Scoring*: knock = deadwood difference; gin = +20 plus opponent's
     count (gin cannot be undercut); undercut (defender ≤ knocker) =
     difference +10 to the defender.
- **Match structure**: hands repeat until a player reaches 100; then +20
  per hand won (boxes) and +100 game bonus (+200 shutout). Stock-at-2 ends
  the hand with no score and the same dealer; otherwise the hand's winner
  deals next.
- **Recorded simplifications**: none of substance — layoffs, the upcard
  ritual, the undercut, boxes, and the no-result hand are all modeled. The
  knocker's *equal-deadwood* arrangement choice is preserved as real
  decisions (the point of the jointly route).

## 4. Go Fish migration

`repeat until … { offer to current_player one of [ask] }` plus the
effect-mutated cursor becomes `turns p from 0 over players until (deck is
empty or any player where hand[player] is empty) again went_again { offer to
p one of [ask] }`. The `current_player` state variable disappears; `ask`'s
effect writes `went_again` on every path (true on a successful ask or on
drawing the asked rank). **Byte-identity is the acceptance instrument**:
existing playout tests and goldens must pass unchanged — the form's rotation
must reproduce the cursor's exact sequence.

## 5. Docs and gates

- decisions.md gains "The `turns` form" (spec-voice promotion of the
  turn-loop-form question, whose file is deleted) and "Joint-predicate selection" (in the
  movement section); meld-groups.md is rewritten in place to its narrowed
  residual (first-class groups, Canasta as the forcing function);
  library.md catalogues `turns` beside the three round forms; roadmap's
  President-as-candidate bullet is corrected; `_candidates.md` drops gin.
- Gates: the `as`-block playbook — surface-totality audit **before** tests
  (two ledgers, one per construct), misuse-probe rejection tests,
  `openspiel_ready` proof module for Gin, byte-identical Go Fish goldens,
  bare `mypy` + full `pytest -q`, ultra review round before the PR.
- Commit structure: construct-by-construct (turns → jointly → gin →
  go-fish migration → docs), so review can bisect. Expected size ~2–3× the
  `as`-block PR.
