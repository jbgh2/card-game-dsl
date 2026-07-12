# Game primitives: from stdlib registries to sealed sidecars

*Status: design analysis / proposal — not a settled decision. The committed
spec is in [decisions.md](../decisions.md); the sanctioned role of game-local
Python is described in [library.md](../library.md) "Stdlib functions" and the
history that produced it in [kernel-migration.md](../kernel-migration.md).
This note is about the package boundary and the primitive interface, not the
language surface.*

## 1. The problem: the stdlib is full of games

The standing policy after `instantiate` was deleted is clear: Python is
allowed for **pure value computation** — scorers, trick winners, legality
tables, bid ladders — and never for mechanics, movement, or decisions. Every
game-local primitive in the corpus conforms in spirit: `pot_share`,
`pinochle_meld_value`, `skat_next_bid`, `cribbage_show_value` are all reads.

The implementation of that policy has drifted from its intent in three ways:

1. **The language package contains game knowledge.** Nine game modules sit in
   `cardlang/runtime/` beside the engine core, and of the ~50 names in
   `STDLIB_CALL_FUNCS` (`cardlang/stdlib/functions.py`), roughly 40 are
   game-prefixed (`tichu_*` ×12, `skat_*` ×5, `tarot_*` ×5, `coup_*` ×5,
   cribbage's six, Stud's three, the climb queries, three game-named auction
   outcomes). "Stdlib" is a misnomer for most of its contents. Adding a
   corpus game means editing three language-package files: the name
   registry, `signatures.py`, and a hand-written `match` arm in
   `cardlang/runtime/stdlib.py` — a hand-enumerated dispatch over what
   should be a registry-derived one, the shape
   [decisions.md](../decisions.md) "Closed-domain completeness" warns
   against.
2. **Purity is conventional, not structural.** A primitive receives `Ctx` —
   the engine's whole internal state object — and self-serves:
   `tichu_next_holder` scans hands, `pot_share` reads the betting
   accumulator and the live hole cards. Nothing structural stops a
   "pure read" from mutating state or reading a hidden zone it has no
   business seeing; the guarantee lives in review.
3. **Two primitives are not reads at all.** `coup_note_reveal` and
   `tichu_hand_summary` are trace emitters for the playout harness. Coup
   calls one as `let noted = coup_note_reveal(q)` — a dead variable, purely
   for the side effect. That is harness instrumentation leaking into the
   rules text.

The central placement is not protecting anything. It is a migration
artifact: the primitives were extracted *out of* `instantiate` mechanics
during the kernel migration, and the path of least resistance left them
where the mechanics had lived. What actually separates a sanctioned
primitive from `instantiate` hell is not where its file sits — it is what
its interface lets it touch.

## 2. The end state: sealed sidecars, declared in the game file

The target model has three parts.

**Narrow interface — values in, value out.** A primitive's signature names
value types (`Card`, `Player`, `Integer`, card collections); it never
receives `Ctx` or any engine-internal handle. A function that computes a
cribbage show score from fifteen cards cannot participate in mechanics,
mutate state, or observe anything it was not handed — the property is
structural, so it holds for game sixteen without review.

**A `primitives { }` declaration block in the game file.** The `.cardlang`
declares what it borrows from outside the DSL:

```
primitives {
  pot_share(p : Player) -> Integer
      reads committed, hole, upcards
  skat_matadors(p : Player) -> Integer
      reads hand[p], skat
}
```

The declaration carries the typed signature and — the load-bearing clause —
**what state and zones the implementation reads**. Pure reads are permitted
to touch hidden zones (`pinochle_meld_value` reads a concealed hand;
`skat_matadors` reads hand plus skat — the reason matadors must be a `let`
and never public state), so every primitive is a small information-flow
decision. Declared reads make that decision visible to the checker instead
of a reviewer: if a primitive reads `hand[declarer]` and its result flows
into public state, the implied reveal is derivable — the derived-info-set
story ([decisions.md](../decisions.md) "Knowledge, visibility, and the
projection model") extended to the one place Python still participates. The
resolver checks the block both ways: declared-but-unimplemented and
implemented-but-undeclared are both errors, and the runtime hands the
implementation exactly the declared reads, nothing more.

**Co-location.** With the interface sealed and the declaration in the game
file, the implementation's location stops mattering for safety — so it moves
next to the game it serves, and the language package
(`cardlang/stdlib`, `cardlang/runtime`) becomes game-independent. The
genuinely general names stay in the stdlib: `team_of`, `player_holding`,
`suit_of`, `rank_value`, `card_value`, `error`, `best_five_card_hand` — and
the poker-*family* selectors (`bring_in_seat`, `first_to_act_seat`,
`pot_share`) graduate there when a second poker game lands, per the usual
corpus-first promotion.

**What this is not.** The `instantiate` lesson
([principles.md](../principles.md)) stands untouched: no control flow, no
movement, no decisions, no mutation in Python — hell was Python holding
mechanics and touching state invisibly, not Python computing a score from a
handful of cards. Sidecars do not reopen the escape hatch *because* the
interface cannot express one.

## 3. What blocks it today

- **The `Ctx` coupling.** Most primitives self-serve from engine state
  rather than taking arguments. Each needs its real inputs identified and
  its signature rewritten as values — mechanical for the scorers
  (`tichu_card_points`, `peg_value`), more involved where the function reads
  accumulator state (`pot_share`) or trick-terminal state
  (`tarot_excuse_player`, `tichu_dragon_won`).
- **The trace emitters.** `coup_note_reveal`, `tichu_hand_summary` (and any
  future sibling) are not primitives and cannot be declared as such. They
  move to the harness layer, keyed off observation events the kernel already
  emits; their call sites (including Coup's dead `let`) leave the game
  files.
- **The climb queries and outcome functions.** `bigtwo_lead_options` /
  `tichu_follows` and the game-named outcome functions are named in `round`
  clauses, not called as `f(...)`; they need the same declared-signature
  treatment but their own declaration slots (their signatures are
  mechanic-driven). Same principle, separate wiring.
- **Registry derivation.** Whatever the placement, registry, signatures, and
  dispatch should derive from the declarations rather than being maintained
  as three parallel tables with a hand-written `match`; a static test pins
  the derivation complete, per "Closed-domain completeness".

## 4. Sequence

1. **Evict the trace emitters** to the harness. Independent, small, and
   deletes the strangest lines in the corpus.
2. **Narrow the interface**: rewrite primitive signatures as values-in /
   value-out, engine passes arguments explicitly. No file moves yet; the
   corpus proves the sealed signatures suffice.
3. **Add the `primitives { }` block** to the grammar and the corpus game
   files; derive registry/signatures/dispatch from it; static test pins
   agreement. (This is new grammar surface and pays the
   [decisions.md](../decisions.md) "Surface totality" tax like any other.)
4. **Co-locate**: move each game's implementation out of
   `cardlang/runtime/` to live with its game; `cardlang/stdlib` keeps only
   game-independent names. Byte-identical traces throughout, enforced by the
   existing goldens.

## 5. One pressure to preserve

The declaration block doubles as a per-game inventory of exactly what is
not yet expressible in the DSL — which is what these primitives are, and
why [roadmap.md](../roadmap.md)'s generalization work (the
`scoring_component` subsystem, the shared combination model, in-DSL outcome
expressions) should keep burning them down. Sidecars being well-designed
must not make them so comfortable that the burn-down stops: a shrinking
`primitives { }` block is the visible score.
