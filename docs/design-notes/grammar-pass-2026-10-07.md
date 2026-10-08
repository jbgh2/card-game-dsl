# Design review: the Card Game DSL grammar

*An outside read of `cardlang.lark`, the stdlib, the two family libraries and the 34-game corpus. Nothing else was consulted. Every usage figure below was computed from those files; a figure is a count of files unless it says otherwise.*

## 0. The short version

The language has a sound centre and a swollen edge. The centre is: zones with visibility types, one movement statement that emits per-observer events, `move_type` with `when`/`effect`, `offer`, `as`, procedures, functions, libraries with `requires`, and a readable expression register. That centre carries every game in the corpus and is what makes derived information sets possible. Protect it.

The edge is where the growth is going. Of 153 rules, I count **CORE 94, SUGAR 22, SPECIAL-CASE 31, UNUSED 6**. The 31 special cases are not the real problem; the real problem is a pattern they share. The grammar keeps absorbing *game mechanics as syntax* — a trick round, an auction round, a climbing round, a turn loop, a card-points table, a trick-order table, a mode machine, an outcome type — each with its own keywords, its own implicit binders, its own side-channel state (`state.led_suit`, `state.shed_first`) and its own slot for a Python name. Each one is correct for the games that forced it and slightly wrong for the next game, so the next game either grows the construct (`early`, `trump`, `before asking`, `again`, `excluding`) or hand-rolls the mechanic below it. Both happened, repeatedly, and the hand-rolled versions are the evidence that a smaller core already exists inside the language: four of the twelve trick-takers do not use the trick `round` at all.

Three numbers frame the rest. **28 of the grammar's productions exist only to parse a wrong sentence and reject it** (9% of the 314 alternatives, more than one for every six named rules). **9 Python functions are named in grammar slots and declared nowhere in the DSL** (`bridge_auction_outcome`, `tichu_follows`, ...). **595 of the grammar file's 1137 lines are comments** explaining why a production is shaped the way it is — more than the 456 lines of productions and terminals. A grammar that needs that much explanation is carrying decisions that belong in a type checker, a desugaring pass and a library.

---

## 1. Rule census

Method: every one of the 153 named rules in `cardlang.lark` was classified by reading its productions and probing the corpus (comments stripped) with a regex per construct and per optional clause. The one-line-per-rule table is Appendix A. Totals: **CORE 94, SUGAR 22, SPECIAL-CASE 31, UNUSED 6**.

Two things the headline totals hide:

- **Unused alternatives inside live rules.** The six UNUSED rules are whole rules. Beyond them, twelve live alternatives have no user: `rule_remove` (`- Name`) and `rule_override`; `random` selection; the `burn` and `muck` verbs; `all subsets`; `all suits where`, `all ranks where`, `any <domain> where`, `number of <domain> where`; both `over subsets` aggregations. Eight keywords appear in no file: `always`, `card_values`, `down`, `override`, `random`, `ranks`, `suits`, `visibility`.
- **Reject-with-replacement productions.** 28 productions (25 distinct `*_reject` aliases) parse a plausible mistake so the builder can refuse it with a message: the `:` habit on three block clauses, `->` and `= default` in `primitives`, `card_values`, `==`/`!=`, `/`, `%`, the trailing comma in `trick_order`, the `wager:` flag, five malformed `Collection<...>` shapes, `always`, three bare joiners in a subset source, and so on. These are good diagnostics in the wrong layer. They inflate the rule count, they force the grammar to stay on Earley (a reject arm is by construction a near-duplicate of a live arm), and every one of them had to be reasoned about for ambiguity — the comments say so at length.

The CORE count (94) is also generous: a dozen of those are one-alternative wrapper rules (`players_spec`, `type_arg`, `rule_clause`, `library_item`, ...) that a grammar written for an LALR parser would inline.

---

## 2. Keyword families

123 anchored keywords. Grouped by what they are for, with the number of files (of 37: 34 games, 2 libraries, stdlib) that use at least one member:

| Family | Members | Files | Orthogonal? | Could collapse to |
|---|---|---|---|---|
| Game skeleton | `game phase players direction cards pieces board max_length zones state winner loser teams positions uses library requires primitives reads` | 36 | mostly | `cards`/`pieces` are one clause; `positions`/`board` both mint domains; `winner`/`loser` one clause |
| Movement | `deal move draw transfer burn muck from to each all one some chosen random where jointly as-equally-as-possible visibility shuffle reveal` | 35 | **no** | one verb (`move`); `burn`/`muck` unused; `random`/`visibility` unused; `transfer` used once |
| Ring loops | `round offering source into winner trump early climb combinations follows until over from before asking turns again` | 30 | **no** | one loop (`turns`) + `offer`; see Finding 1 |
| Decision | `offer one of choose integer in up to excluding` | 18 | yes | keep |
| Control flow | `repeat until if else elif then for each simultaneously as run continue to skip next hand produce produces outcome before_each after_each mode transition_to when` | 36 | **no** | `if/repeat/for/as/run` + one `exit <block>`; the rest desugar (Finding 6) |
| Trick-play rules | `rule constrains applies_when demands exempts if_impossible active_rules override legal_moves` | 12 | no | filter functions composed in a library (Finding 2) |
| Card facts | `ranking card_points card_values trick_order trump else` | 30 | no | `ranking:` plus `function` definitions with reserved names (Finding 3) |
| Quantifiers / queries | `any all number of players player team teams suit suits rank ranks cards card subset subsets the first where in` | 36 | **no** | one binder-explicit quantifier over a domain expression (Finding 4) |
| Aggregation | `sum highest lowest over or more` | 15 | partly | one `fold` form with an explicit binder |
| Arithmetic / logic | `is not and or offset_by divided by rounded up down` | 37 | yes | keep; `divided by rounded` is one game |
| Definitions | `move_type when effect wager concession function procedure` | 33 | yes | `wager`/`concession` are annotations, not language |
| Betting | *(none)* | 7 | — | the whole betting family is already a library — the existence proof that the others can be |

The last row is the tell. Poker betting, the family that would most tempt a designer to add keywords (`bet`, `raise`, `pot`, `street`), has **zero** keywords and is the cleanest, most reusable part of the corpus. It is written in the language. Trick play, auctions and climbing, by contrast, got grammar.

Overlap inside families is the growth engine. "Where is the next player" is spelled four ways: `from <seat>` on a round, `turns t from`, `the first player from <seat> where`, and `offset_by`. "Choose among these moves" is spelled two ways (`offer to X one of [...]` and a single-participant `round offering [...] from X over players where player is X until <flag>` — eight of the sixteen auction rounds are the latter, i.e. an `offer` that re-asks). "Which cards may I play" is spelled two ways (`rule` cascade through `active_rules`, or `function follow_ok(p, c)` passed as a `where` filter).

---

## 3. Findings, ranked by payoff

### Finding 1 (highest payoff): four ring-loop statements for one loop

`turns_stmt`, `auction_stmt`, `climb_stmt` and `round_stmt` are all the same control structure: *walk a ring of seats from a start seat, over a participant predicate re-evaluated each step, until a predicate holds, making one decision per seat.* The grammar comments concede this ("the same `round` kernel, configured along the offering, accumulator, and termination axes") and then give each configuration its own statement, its own keywords and its own clauses.

The equivalence is nearly literal in the corpus:

```
round offering [check, bet, call, fold] from first_actor
      over players where pending(player)
      until (number of players where pending(player)) is 0          -- kuhn-poker

turns d from first_actor over players where not drawn[player]
      until (number of players where not drawn[player]) is 0 again more {
  offer to d one of [toss, stand]                                 -- five-card-draw
}
```

The first is the second with the body fixed to one `offer`. Sixteen games use the auction form, ten use `turns`; two spellings, one loop. The trick form adds four bundled extras — a rules consultation, a hidden accumulator (`state.led_suit`), a winner chosen from a three-name slot (`highest_of_led_suit` 3 games, `highest_trump_or_led_suit` 4, `highest_by_trick_order` 2), and two bolt-ons that single games forced (`trump <expr>`: oh-hell, bridge, pinochle; `early <name>`: getaway). The climb form adds a native combination engine named in two slots, an interrupt window, a hosted poll (`before asking`, tichu only), and three more hidden accumulators (`state.shed_first`, `state.shed_second`, `state.lead_ended_trick`).

The decisive evidence that the loop is already in the language: **Skat, Doppelkopf, Five Hundred and Schnapsen do not use the trick round.** They write it out:

```
as leader { move chosen one card from hand[leader] to trick_pile }
as second { move chosen one card from hand[second] where follow_ok(second, card) to trick_pile }
as third  { move chosen one card from hand[third]  where follow_ok(third, card)  to trick_pile }
let w = highest_by_trick_order(trick_pile)                        -- skat
```

Each of the four has a reason the bundled construct could not host it (announcements between plays, hand-ordered legality, a three-handed misère, a leader with free actions) — each a configuration axis the construct lacks, each a fifth clause in waiting. Doppelkopf pays with four near-identical 25-line seat blocks, Five Hundred with two trick loops. That cost is not a reason to grow `round`; it is a reason to make the hand-rolled form cheap: a `turns` loop whose body is `as t { move chosen one card from hand[t] where legal(t, card) to trick_pile }`. Then trick, auction and climb are three library procedures over `turns` + `offer`, and Doppelkopf's four blocks are one loop.

What this removes: `round_stmt`, `auction_stmt`, `auction_moves`, `climb_stmt`, `hosted_poll` (5 rules), the keywords `offering source into early climb combinations follows asking before` and the `winner`/`trump`/`outcome` uses on a round (about 11 keyword uses), all five `state.*` side channels (declared as ordinary accumulator state by the library procedure instead), and the three-name winner slot.

### Finding 2: the rule sublanguage is one function, spelled as a block, consulted from one place

`rule_def` and its five clauses, `active_rules`, `rule_ref` (four arms), `rule_args`, `legal_moves`, `mode_def`, `mode_item`, `transition_to`, `move_event` — fifteen rules and nine keywords — exist to answer one question at one site: *which cards may this seat play to the trick?* Only the trick form of `round` reads them (the Hearts file says so: "rules are consulted only at the trick round's card decision, never here").

In the corpus the clauses are degenerate. `constrains:` is `play_to_trick` in every rule in every file. `if_impossible:` is `hand` in every rule but one. `legal_moves:` always lists the move the phase's own `round` statement already names. The `-` and `override` arms of `rule_ref` are unused. `exempts:` exists for one card in one game. `mode` + `transition_to` (two games) is a Boolean plus an `applies_when:`: Hearts could write `applies_when: state.led_suit is none and not hearts_broken` and set `hearts_broken` in the body after the round, which is exactly how Big Two tracks `opened`.

Meanwhile the four hand-rolled trick-takers answer the same question with a function:

```
function follow_ok(p : Player, c : Card) =
  if any card in hand[p] where follows_lead(card, trick_pile)
  then follows_lead(c, trick_pile) else true                       -- skat, doppelkopf
```

The running-intersection cascade (`demands` narrows, `if_impossible: hand` keeps the prior narrowing) is a fold of filters. It is expressible as a library of composable predicates — `must_follow(c, pile)`, `must_head(c, pile)`, `must_trump_if_void(p, c, pile)` — and a game picks its cascade by `and`-ing them, or the library offers `cascade([...])`. Belote's five-rule cascade is the stress test and it already leans on functions (`opp_winning`, `is_royal`) to say what the rule clauses cannot. The one thing the rule shape adds that a plain function lacks is the exempt-cards ordering (Tarot's Excuse "offered after every other legal card"), which is an action-ordering detail the engine owns, not a rule semantics.

### Finding 3: declarative tables that are functions in disguise

Three game-level blocks spell a function over `card` as a keyed table, each with its own key terminal and its own reject twins:

- `card_points { A: 11  10: 10 ... }` (10 games) is `function card_points(c : Card) = if c.rank is A then 11 elif ...`. Belote proves it: its points depend on trump, so it writes `function bel_card_points(c : Card)` by hand and ignores the block. French Tarot half-escapes too (`if is_bout(card) then 9 else card_points(card)` at every read, because the table cannot key on suit). Scopa uses the table for the primiera scale, and the comment admits it is there because "a clause is the only place it can be said once" — the clause is doing the job of a function definition.
- `trick_order { trump: ...  follow_class: ...  card_strength: ... }` (5 games) is three functions with reserved names, `is_trump`, `follow_class`, `card_strength`, that the kernel's `follows_lead` and `highest_by_trick_order` call. Nothing about them needs a block: `function is_trump(c : Card) = c.suit is trump_suit` is the same sentence, and would let a game define only the rows it needs without an "omitted row default".
- `trump: spades` (one game) versus `trump trump_suit` on the round (three games) versus the `trump:` row of `trick_order` (five games): three spellings of one fact.

Cost: 15 rules (`card_points_*` 5, `trick_order*` 3, `trump` 1, plus their key terminals and 8 reject productions) for what two reserved function names and `ranking:` already say. The desugaring is mechanical: the builder already turns the table into a lookup.

### Finding 4: binders implied by position, and a quantifier with thirteen arms

Every query form binds an implicit variable chosen by its noun: `player` in `players where`, `card` in `cards in X where`, `subset` in `any subset of`, `cards` in `where jointly`, `team`, `suit`, `rank`, `cell`, `line`, `piece`, plus the statement-level `actor`, `winner` and `seat`. Thirteen implicit binders. Because the binder is implied, the grammar needs one production per noun — `quantifier` has 13 arms, `card_query` 4, `player_query` 4, `subset_query` 3, `agg_query` 4 — and a separate identifier terminal (`QNOUN`) to keep `any player where` from parsing twice. Five of the quantifier arms are unused.

The corpus pays in two ways. Nesting is impossible without a helper: Go Fish and both Studs say so in comments ("factored as a function so the rank binder does not nest inside the player binder"; "the inner one would rebind `card` and shadow the outer binder"). And functions cannot range over zones, so Cribbage writes its five show functions twice, once for `played[p]` and once for `crib`, with a comment citing the gap. One explicit-binder form fixes both:

```
any p in players where ...          number of c in hand[p] where c.rank is r
sum of card_points(c) for c in z    highest rank_value(c) for c in z or 0
```

That is three rules (`any/all/number of <binder> in <domain> where`, `fold`, and the domain expression) replacing 28 arms across five rules, and it lets a zone be a value a function can take.

### Finding 5: the native boundary leaks through grammar slots

`primitives { }` is a good idea — a native function declares its signature and what it reads, which is exactly what information-set derivation needs. But nine natives bypass it. `outcome bridge_auction_outcome`, `combinations tichu_lead_options follows tichu_follows` and their siblings are Python names in NAME slots of the round forms, declared in no file; the Tichu and Tarot files comment that the block "cannot" cover them (issue #142). `strain_index`, called by Bridge's `next_level`, is defined nowhere in the DSL either. And `native-functions.txt` lists functions no game text calls at all (`decomposition`, `is_wild`, `peg_pairs`, `hand_rank`, `side_pot_payouts`, the whole `salvo` row), which means the native surface is wider than the declared one.

The grammar shape is acting as the FFI: a slot's position decides that its NAME is Python. The fix is the one the block already embodies — every native is declared with reads, and every slot that today takes a bare NAME takes an expression. Then `outcome`, `combinations` and `follows` stop being keywords.

### Finding 6: control flow accreted one game at a time

`skip to next hand` (6 games) is `break` out of the enclosing `repeat` phase, with the word `hand` hard-wired into the grammar. `continue to <phase>` (3 games) is goto-a-sibling, used only inside a `produces:` arm. `produce` / `produces:` / `-> outcome { ... }` (4 games) give a phase a typed return value — but Schnapsen is the only game that `produce`s from DSL text; Bridge, Tarot and Pinochle produce via a native. `before_each` (19 games) is statements at the top of the loop body; `after_each` (5) is a `finally`. `phase X when C` (2) is a guard. `mode` / `transition_to` (2) is a Boolean. Each is small, each is sensible, and together they are nine rules and eleven keywords for: block exit, call-with-return, finally, and a guard. A phase that is a procedure with a result type, plus `exit <phase>`, covers all of them.

### Finding 7: repetition the language cannot factor yet

The copies are the clearest growth signal because each is a missing abstraction, not a missing keyword:

- The poker street terminator `until (number of players where pending(player)) is 0 or (...)` appears **22 times**, byte-identical, because a `round`'s clauses cannot be a procedure. (`open_street` shows what happens when they can be: one procedure, seven consumers.)
- `move all cards to deck  shuffle deck` opens 21 hand loops.
- Canasta declares eleven `meldA..meld4[team]` zones and dispatches with eleven-arm `if` chains three times, because a zone family cannot take two indices (`meld[team][rank]`).
- Doppelkopf's four seat blocks and Five Hundred's two trick loops (Finding 1).
- Cribbage's duplicated show functions (Finding 4).

### Finding 8: ambiguity and precedence hazards

- **Five identifier terminals** (`NAME`, `QNOUN`, `CARD_RANK_NAME`, `CARD_POINTS_KEY`, `TRICK_ORDER_KEY`) match the same strings and are told apart by position. The grammar's own comment: "a context-free lexer ... cannot tokenize this grammar at all." That rules out LALR for good, and every new keyword must be whole-word anchored by hand (123 regex suffixes).
- **`or` is overloaded**: Boolean disjunction and the mandatory empty-set default of `highest ... or 0`. Belote's `(highest card_strength(card) over cards in trick_pile where is_trump(card) or 0)` reads correctly only if you know this `or` is not Boolean.
- **Prepositions carry too many roles**: `where` five (filter, query body, rule, event predicate, `jointly`), `in` four, `to` five, `from` three, `over` two. Fine in English; expensive in a grammar that disambiguates by position.
- **Rank literals have two spellings**: `card.rank is "9"` but `9: 0` in `card_points` and `3 of diamonds` — a type pun Tarot's comment has to explain.
- **`if` is both statement and expression** with different bodies; **`-25`** needs its own `cp_neg_value` arm (Spades writes `0 - 200` to dodge the same hazard); and the comments record three constructs moved between precedence levels to stop a trailing operand being absorbed.

### Finding 9: two spellings, one concept (the residue)

`offer` vs single-seat `round offering` (8 cases); `deal`/`move`/`draw`/`transfer`/`burn`/`muck` (one node, six verbs, two unused, one used once); `winner:` vs `loser:`; `cards:` vs `pieces:`; `positions {}` vs `board:`; `+=`/`-=` vs `:=`; `trump` three ways; `card_points` block vs function; `state.led_suit` vs `suit_of(trick_pile)` (Schnapsen defines `led_suit_now()` as the latter).

---

## 4. A minimal kernel sketch

This is a sketch to think with. Everything below the line "library" is written in the language, not in the grammar.

**Kernel declarations.** `game`, `players`, `direction`, `teams`, `max_length`, one component clause (`cards:` covering piece sets), `domains { column: 1..7 }` (absorbing `positions` and `board`), `zones` with visibility types, `state`, `ranking`, `winner`. Natives: `primitives { }` with `reads`, and nothing else may name Python.

**Kernel expressions.** Literals, names, calls, member/subscript, arithmetic, `is`/`is not`/comparisons, `and`/`or`/`not`, `if then elif else`, one explicit-binder quantifier family — `any x in D where P`, `all x in D where P`, `number of x in D where P`, `the x in D where P`, `the first x from s in D where P` — one fold `sum of E for x in D [where P]` / `highest E for x in D [where P] or d`, subsets as a domain (`subsets of k [or more] of Z`), `choose integer in a .. b [up to n] [excluding e]`, and zones as first-class values so functions can take them.

**Kernel statements.** `move <selection> from Z [where P | where jointly P] to Z'` (one verb; `deal`/`draw` as aliases if the register wants them, not as grammar), `shuffle`, `reveal`, `:=`, `let`, `if/else`, `repeat until`, `for each x in D`, `each x in D simultaneously`, `as p { }`, `offer to p one of [...]`, `run proc(...)`, `exit <phase>`.

**Kernel definitions.** `move_type` (params, `when`, `effect`), `function`, `procedure` (parameters may be zones and seats), `phase` (optionally `-> T`, optionally `repeat until`), `library` / `uses` / `requires`.

**Library (in the language).**

```
procedure turns(start : Player, over : Predicate, done : Predicate, body) ...   -- the ring loop
procedure trick(leader, participants, source, pile, legal, winner_of) {
  turns t from leader over participants until pile is full {
    as t { move chosen one card from source[t] where legal(t, card) to pile }
  }
  winner := winner_of(pile)
}
function must_follow(p, c, pile) = ...   function must_head(p, c, pile) = ...
procedure auction(start, over, done, vocabulary) { turns t from start over over until done { offer to t one of vocabulary } }
```

(The sketch assumes two things the language lacks today: a procedure parameter that is a predicate or a statement block, and a zone-valued parameter. Both are the gaps the corpus already cites.)

**Four games on it.**

- *Hearts (trick-taker).* `round play_to_trick from leader over all players source hand into trick_pile winner highest_of_led_suit` becomes `run trick(leader, all players, hand, trick_pile, legal, highest_of_led_suit)` with `function legal(p, c) = must_follow(p, c, trick_pile) and (hearts_broken or not leading_heart(p, c))`. The `mode` machine becomes `hearts_broken := hearts_broken or any c in trick_pile where c.suit is hearts` after the round. `MustLeadTwoOfClubs` is a third conjunct. The rule block, `active_rules`, `legal_moves`, `mode`, `transition_to` all vanish from the file; the stdlib ships `must_follow` and `no_lead_until_broken(suit)`.
- *Kuhn poker (betting).* Already library. `round offering [check, bet, call, fold] from first_actor over ... until ...` becomes `run betting_street(first_actor)`, a `poker_betting` procedure that owns the 22-times-copied terminator. The game file keeps antes, deal, showdown, `fold`.
- *Big Two (climbing).* `round climb play_combination ... combinations bigtwo_lead_options follows bigtwo_follows until ...` becomes `turns t from leader over players where hand[player] is not empty until <shed> { offer to t one of [play, pass] }` with `move_type play { effect { move chosen some cards from hand[actor] where jointly beats(cards, trick_pile) to trick_pile  last_player := actor } }` and `pass` guarded so the trick closes when `t is last_player`. `beats` is the declared native (`Collection<Card>` predicate), exactly Scopa's `scopa_sums_to` shape, so `combinations`/`follows` stop being slots. `state.shed_first` becomes an ordinary assignment in `play`'s effect.
- *Klondike (patience).* Essentially unchanged: `turns` + `offer` + move_types is already the kernel. `positions { column: 1..7 }` becomes `domains`. The only loss is nothing; the only gain is that `turns` is now the same word the trick-takers use.

---

## 5. Cut / merge / generalise

Ordered so that each step leaves the corpus running. Migration shape is **M** (mechanical rewrite, scriptable from the parse tree) or **R** (redesign of a construct).

| # | Change | Rules affected | Games affected | Shape | Risk |
|---|---|---|---|---|---|
| 1 | Delete unused alternatives and keywords: `random`, `visibility`, `burn`/`muck` verbs, `rule_remove`/`rule_override`, `all subsets`, four quantifier arms, two subset aggregations, `always`, `card_values`, `transfer` verb (hearts rewrites to `move`) | `select_mode vis_clause rule_ref subset_query quantifier agg_query` + TRANSFER_VERB | hearts (1 line) | M | None; reddening tests may exist for the reject arms |
| 2 | Move all 28 reject-with-replacement productions to a post-parse diagnostic layer (token-adjacency suggestions on parse failure) | 25 `*_reject` aliases, `nested_collection`, `subset_of_guarded`, `applies_pred`, `trick_order_eq_row`, `primitive_arrow_decl`, `primitive_default_decl`, `card_source`, DIV_OP, `==`/`!=` | none | R (tooling) | Message quality must be preserved; test each message against the same wrong sentence |
| 3 | `auction_stmt` becomes `turns` + `offer`; `outcome` clause becomes a `let` of the native after the loop or a `produce` | `auction_stmt auction_moves` | 16 games (22 sites) | M | Ring-pointer semantics: confirm `turns` advances past the acting seat identically; the single-seat re-offer cases (8) become plain `offer` in a `repeat until` |
| 4 | Poker street as a `poker_betting` procedure | none (library) | 7 games | M, after 3 | Needs a procedure to take a `Player` start and reach the `until` predicate — already expressible |
| 5 | `card_points { }` and `trick_order { }` become functions with reserved names; `trump:` folds into `is_trump` | `card_points_*` (5), `trick_order*` (3), `trump`, CARD_POINTS_KEY, TRICK_ORDER_KEY | 10 + 5 + 1 games | M | `card_points(card)` callers unchanged; the "omitted row default" becomes a stdlib default function |
| 6 | Explicit-binder quantifiers and folds; zones as function arguments | `quantifier card_query player_query subset_query subset_of subset_source subset_size agg_query all_players card_source` | all 34 (every `where`) | M for the rewrite, R for zone-valued parameters | Largest diff in the corpus; do it with a tree-to-tree rewriter and a byte-identical playout check per game. Removes QNOUN and the nesting restriction |
| 7 | Rules become filter functions in the stdlib; `active_rules`/`legal_moves`/`mode`/`transition_to` deleted | `rule_def rule_params rule_clause constrains applies_when applies_pred demands exempts if_impossible active_rules rule_ref rule_args legal_moves mode_def mode_item transition_to move_event` | belote bridge french-tarot getaway hearts oh-hell pinochle spades + stdlib | R | Candidate ordering for exempt cards (Tarot) must be reproduced in the engine; Belote's five-rule cascade is the regression test |
| 8 | Trick round as a library procedure over `turns`; `state.led_suit` etc. become declared state | `round_stmt` + 5 `state.*` names | 8 round users; 4 hand-rolled trick-takers simplified | R, after 6 and 7 | Needs block-or-predicate procedure parameters; gate on Doppelkopf collapsing to one loop as the acceptance test |
| 9 | Climb as a library procedure; `combinations`/`follows` as declared `Collection<Card>` natives | `climb_stmt hosted_poll` + 3 `state.*` | big-two president tichu | R, after 8 | Tichu's interrupt window and `before asking` poll are the hard cases; Tichu is the acceptance test |
| 10 | Control-flow unification: `exit <phase>` replaces `skip to next hand`; phases with `-> T` return via `produce`; `continue to` removed in favour of sequencing; `before_each` inlined | `skip_stmt continue_to before_each phase_qualifier(when)` | 6 + 3 + 19 + 2 games | M | `after_each` stays (finally semantics) unless `exit` runs it, which it should |
| 11 | `loser:` -> `winner: highest <bool>`; `pieces:` -> `cards:`; `positions`/`board` -> `domains` | `loser pieces positions position_decl board` | getaway, breakthrough, tic-tac-toe, freecell, klondike | M | None |
| 12 | Declare every native: round-slot names and `strain_index` into `primitives { }`; native-functions.txt entries no game calls are deleted or declared | `primitive_type` (absorb `Collection<T>` into `payload_type`) | bridge pinochle french-tarot big-two president tichu | M | Reveals which natives genuinely read hidden state |

Done in that order, the grammar lands near 95 rules and about 75 keywords with every game in the corpus still passing its playouts, and the next trick-taker, auction game or climbing game arrives as a library change.

---

## 6. What not to touch

- **Zones as the only home of hidden information, typed by projection.** `Hand<player>`, `HiddenPile<player>`, `PublicHand<player>`, `FaceDownPile`, `Discard`, `Muck` — and the rule that state is public. Cheat, GOPS, Five-Card Draw and Klondike each say in their headers that the information structure "fell out" of the zone types with no observation rule written. That is the thesis of the language proven four times. Every proposal above preserves it.
- **One movement statement with a per-observer event.** `move chosen 3 cards from hand[p] to gift[p]` being simultaneously the rule, the decision and the observation is the design's best idea. Keep the English register (`all cards`, `chosen one card`, `to each hand`); cut only the verb synonyms.
- **`move_type` with `when`/`effect`, `offer`, `as`, procedures that splice, `choose integer`, `each ... simultaneously`.** These are the decision kernel, they are small, and the Coup file shows them scaling to a genuinely interactive bluffing game with no special syntax.
- **`library` / `uses` / `requires`, with the "variation rides on required state, not import parameters" discipline.** `poker_betting` is the model for everything else that should leave the grammar.
- **`max_length`, `ranking:`, `players`, `teams`, `direction`.** Honest declarations that OpenSpiel and the engine need.
- **The reject-with-replacement *intent*.** A designer should get "write `card_points`, not `card_values`". Keep the messages; move the mechanism.
- **Corpus-first as the gate on *which* constructs exist.** It is the right gate. What it did not gate was *how* a mechanic enters — as grammar or as library — and that is the one dial to add.

---

## 7. What to look out for

A checklist for a first-time language builder running a corpus-first process. Each item names the tell and the measurement that catches it.

1. **A new game adds a clause to an existing statement** (`early`, `trump`, `again`, `before asking`, `excluding`). The construct is a mechanic, not a primitive. Measure: optional clauses per statement rule; past three, it is a library procedure wearing syntax.
2. **A game hand-rolls what a construct was built for** (four trick-takers bypassing `round`). Measure: grep for the construct's body written longhand; each hit is a missing library parameter.
3. **The same text appears N times across games** (22 poker terminators, 21 gather-and-shuffle pairs, 11-arm meld dispatch). Measure: a duplicate-block census per release; three copies with no way to name them is a language gap, never style.
4. **A Python name sits in a grammar slot.** Measure: every NAME in the corpus resolves in the DSL or in a `primitives { }` block. Today nine do not.
5. **The grammar comment is longer than the production.** Measure: comment-to-production ratio in the `.lark` (today 1.3:1). A grammar explaining its own ambiguity work-arounds is doing a type checker's job.
6. **A keyword still has one user after ten more games.** Measure: per-keyword file counts (today 13 keywords at one file, 14 at two), re-run per corpus addition, with a sunset rule.
7. **Two spellings for one concept.** Measure: grammar paths per glossary concept. `trump` has three, "ask one seat" two, "legal cards" two.
8. **Implicit binders.** Tell: a comment says "so the binder does not nest". Measure: distinct implicit binder names (today 13); growth means a noun got its own production.
9. **Error recovery as grammar.** Measure: share of alternatives aliased `_reject` (today 28 of 314, 9%). Anything above zero is a layer violation.
10. **Side-channel state with no declaration** (`state.led_suit`, `state.shed_first`). Measure: every `state.` read resolves to a declaration. Today none of the five do.
11. **The lexer depends on the parser.** Measure: try to build an LALR table once a quarter; the first conflict names the construct that encoded semantics in position.
12. **The library tier is thin.** Measure: non-comment `.cardlang` lines in libraries and stdlib against non-comment `.lark` lines (today 165 against 456, about 1:3). A converging language inverts that ratio: the grammar stops moving and the libraries grow with the games.

The growth table in the brief (98 -> 138 -> 162 -> 153 rules against 13 -> 30 -> 34 games) is consistent with all twelve tells: rules grew roughly one for every new game, and the one contraction came from the author noticing, not from the process. The fix is not to stop adding games; it is to decide, for every new mechanic, "grammar or library?", and to make the library answer cheap enough that it is the default.

---

## Appendix A: per-rule census

153 rules. Totals: **CORE 94, SUGAR 22, SPECIAL-CASE 31, UNUSED 6**. Usage figures are counts of files (34 games, 2 libraries, stdlib) exercising the rule or the named arm; "reject arm" means an alternative that exists only to be refused with a message.

| Rule | Class | Usage / reason |
|---|---|---|
| `start` | CORE | Entry symbol. |
| `stdlib_rules` | SUGAR | Alternate start for stdlib-rules; a `library stdlib { rule ... }` file would use `library` instead. |
| `library` | CORE | poker_betting, smuggling: the only reuse tier. |
| `library_item` | CORE | Structural (library). |
| `requires_block` | CORE | poker_betting, smuggling: the import contract. |
| `require_decl` | CORE | Same. |
| `top_item` | CORE | Structural. |
| `game` | CORE | All 34. |
| `game_item` | CORE | Structural. |
| `uses_decl` | CORE | 7 poker games. |
| `primitives_block` | CORE | 15 games; the declared native boundary (and the `reads` info-set contract). |
| `primitive_decl` | CORE | 15 games. |
| `primitive_arrow_decl` | UNUSED | Reject-only twin (`->` spelling). |
| `primitive_default_decl` | UNUSED | Reject-only twin (`= expr`). |
| `primitive_param` | SUGAR | Duplicate of `parameter` with a different type production; 13 games. |
| `primitive_type` | SUGAR | 3 live arms duplicate `payload_type` plus `Collection<T>` (gin-rummy, scopa); 5 reject arms. |
| `nested_collection` | UNUSED | Helper for a reject arm only. |
| `primitive_reads` | CORE | 13 games; the info-set contract of a native. |
| `primitive_read` | CORE | 13 games; `in <phase>` tail 7, `[binder]` 5; one reject arm. |
| `players` | CORE | All 34. |
| `players_spec` | SUGAR | One alternative (INT); wrapper rule. |
| `direction` | CORE | All 34 (noise for 1- and 2-player games). |
| `cards` | CORE | 32 games. |
| `pieces` | SPECIAL-CASE | breakthrough, tic-tac-toe: `cards:` for a piece set; two spellings of 'component set'. |
| `max_length` | CORE | All 34; OpenSpiel contract. |
| `ranking` | CORE | 28 games (conventions 19, ace-ten 5, enumeration 4). |
| `card_points_table` | SUGAR | 10 games; a rank-to-int table expressible as `function card_points(c: Card) = if ... elif ...` (Belote already writes exactly that for contract-dependent points); 2 reject arms. |
| `card_points_entry` | SUGAR | Part of the table. |
| `card_points_else` | SUGAR | french-tarot, scopa. |
| `card_points_key` | SUGAR | Part of the table; own terminal CARD_POINTS_KEY. |
| `card_points_value` | SUGAR | INT / -INT; tichu uses the negative. |
| `trick_order` | SPECIAL-CASE | belote, doppelkopf, five-hundred, french-tarot, skat: three functions over `card` (is_trump / follow_class / card_strength) spelled as a keyed block; 3 reject arms. |
| `trick_order_row` | SPECIAL-CASE | Same; `follow_class` row only in five-hundred, french-tarot. |
| `trick_order_eq_row` | UNUSED | Reject-only twin (`=` / `:=`). |
| `trump` | SPECIAL-CASE | spades only; oh-hell/bridge/pinochle pass `trump <expr>` on the round instead, trick_order games use its `trump:` row: three spellings of 'what is trump'; 2 reject arms. |
| `teams` | CORE | 7 games; defines the team domain. |
| `team_spec` | CORE | Same. |
| `positions` | SPECIAL-CASE | freecell, klondike: integer index domains; overlaps `board:`, which also mints a domain. |
| `position_decl` | SPECIAL-CASE | Same. |
| `board` | SPECIAL-CASE | breakthrough, tic-tac-toe: registry-backed domain (`grid(3, 3)`). |
| `zones` | CORE | All 34. |
| `zone_decl` | CORE | All 34. |
| `index` | CORE | All 34. |
| `type_ref` | CORE | All 34. |
| `type_args` | CORE | All 34 (`Hand<player>`). |
| `type_arg` | CORE | Same. |
| `state_block` | CORE | All 34 + 1 library. |
| `state_decl` | CORE | Same. |
| `type_name` | CORE | Optional `T?` 19 games; 2 reject arms. |
| `winner` | CORE | 33 games. |
| `rank_dir` | CORE | Shared by `winner:` and the order aggregators. |
| `loser` | SUGAR | getaway only; `winner: highest lost` over a Boolean (the cheat/coup pattern) says the same. |
| `phase` | CORE | All 34. |
| `phase_outcome` | SPECIAL-CASE | bridge, french-tarot, pinochle, schnapsen: typed phase result; belote/skat/five-hundred run the same auctions on state variables. |
| `phase_qualifier` | CORE | `repeat until` 21 games; the `when` arm (gin-rummy, hearts) is sugar for a guard. |
| `phase_item` | CORE | Structural. |
| `mode_def` | SPECIAL-CASE | hearts, spades: a Boolean plus `applies_when:` on the rule says the same. |
| `mode_item` | SPECIAL-CASE | Same. |
| `before_each` | SUGAR | 19 games; statements at the head of the loop body. |
| `after_each` | SPECIAL-CASE | 5 games; a `finally` that survives `skip to next hand`. |
| `active_rules` | CORE | 8 games; the rule system's activation (read only by the trick form of `round`). |
| `rule_ref` | CORE | plain 8, `+` 2 (hearts, spades); the `-` and `override` arms are UNUSED. |
| `rule_args` | CORE | hearts, spades (`NoLeadingSuitUntilBroken(hearts)`). |
| `legal_moves` | SUGAR | 11 games; always names the move the phase's `round` statement already names (plus pinochle's `declare_trump_suit`, a move_type): derivable. |
| `transition_to` | SPECIAL-CASE | hearts, spades. |
| `move_event` | SPECIAL-CASE | hearts, spades. |
| `statement` | CORE | Structural. |
| `run_stmt` | CORE | 10 games + libraries; procedure call. |
| `continue_to` | SPECIAL-CASE | bridge, french-tarot, pinochle: goto a sibling phase, always inside a `produces:` arm. |
| `skip_stmt` | SPECIAL-CASE | 6 games; `break` from the enclosing repeat phase, hard-wiring the word `hand`. |
| `produce_stmt` | SPECIAL-CASE | schnapsen only; the other three outcome phases produce through a native `outcome` function. |
| `produces_stmt` | SPECIAL-CASE | bridge, french-tarot, pinochle, schnapsen. |
| `produce_arm` | SPECIAL-CASE | Same. |
| `transfer` | CORE | All 34; the movement statement (one IR node, six verbs). |
| `dist_clause` | SPECIAL-CASE | getaway, president (`as-equally-as-possible`); a round-robin default for `deal all ... to each` would absorb it. |
| `where_clause` | CORE | `where` filter 17 games; `where jointly` arm 2 (gin-rummy, scopa). |
| `selection` | CORE | All 34. |
| `select_mode` | CORE | `chosen` 18 games; the `random` arm is UNUSED. |
| `amount` | CORE | all 34 / one 19 / count 33; `some` arm 2 (only with `jointly`). |
| `move_dest` | CORE | `to each` 22 games. |
| `vis_clause` | UNUSED | `, visibility = expr` appears in no file. |
| `epistemic_op` | CORE | `shuffle` 32 games; `reveal` 4 (belote, coup, gops, pinochle). |
| `rotate_stmt` | SUGAR | hearts only; `x := next_in([...], x)` or an if/elif chain. |
| `name_list` | SUGAR | Same. |
| `each_simultaneous` | CORE | gops, hearts; the atomic-commit semantics is not otherwise expressible. |
| `for_each` | CORE | 29 games. |
| `repeat_until` | CORE | 22 games. |
| `if_stmt` | CORE | All 34. |
| `else_block` | CORE | 27 games. |
| `as_block` | CORE | 10 files; actor rebinding. |
| `turns_stmt` | SUGAR | 10 games; `repeat until` + `as` + ring step; `again` arm 2 (five-card-draw, go-fish). High-value sugar: keep it, as a library form. |
| `offer` | CORE | 15 games; the one decision statement. |
| `round_stmt` | SPECIAL-CASE | 8 trick-takers; bundles ring + rules + `state.led_suit` + a winner NAME slot + `trump` + `early`; 4 trick-takers bypass it (doppelkopf, five-hundred, schnapsen, skat). |
| `auction_stmt` | SUGAR | 16 games; `round offering [...] from X over P until C` is `turns t from X over P until C { offer to t one of [...] }` plus an `outcome` slot (3 games); 8 of its uses are single-seat re-offers. |
| `auction_moves` | SUGAR | Same. |
| `climb_stmt` | SPECIAL-CASE | big-two, president, tichu; a ring loop whose decision is a native-enumerated combination, with undeclared `combinations` / `follows` natives and `state.shed_*` side channels. |
| `hosted_poll` | SPECIAL-CASE | tichu only (`before asking`). |
| `let_stmt` | CORE | 25 games; indexed `let x[p]` 2. |
| `assign_stmt` | CORE | All 34. |
| `assign_op` | CORE | `:=` 34; `+=` 23 / `-=` 10 are sugar arms. |
| `lvalue` | CORE | All 34. |
| `move_type_def` | CORE | 28 games + libraries; 2 reject arms. |
| `move_params` | CORE | 13 games. |
| `move_stake` | SPECIAL-CASE | pinochle, tichu: `wager` / `concession` annotations read by nothing in the language. |
| `parameter` | CORE | Shared by move / function / procedure / rule. |
| `function_def` | CORE | 23 games. |
| `procedure_def` | CORE | cheat, coup, scopa + both libraries. |
| `move_when` | CORE | 24 games. |
| `move_effect` | CORE | 28 games. |
| `outcome_set` | SPECIAL-CASE | 4 games (phase_outcome). |
| `outcome_case` | SPECIAL-CASE | Same. |
| `payload_type` | CORE | `T?` 4 games; 2 reject arms. |
| `rule_def` | CORE | 5 games + stdlib; consulted only by the trick `round`. |
| `rule_params` | CORE | stdlib only (`NoLeadingSuitUntilBroken(suit: Suit)`). |
| `rule_clause` | CORE | Structural. |
| `constrains` | SUGAR | Every rule in the corpus says `constrains: play_to_trick`; the clause carries no information. |
| `applies_when` | CORE | Every rule. |
| `applies_pred` | SUGAR | Wrapper whose only purpose is the `always` reject arm. |
| `demands` | CORE | Every rule. |
| `exempts` | SPECIAL-CASE | french-tarot only (the Excuse). |
| `if_impossible` | CORE | Every rule, and always `hand` except getaway's `error(...)`: near-degenerate. |
| `expr` | CORE | Structural. |
| `player_query` | CORE | `players where` 26, `number of players where` 18, `the player where` 9, `the first player from` 3. |
| `card_query` | CORE | count 17, any 14, set 9, `all cards in` 1 (cheat). |
| `card_source` | SUGAR | `zone_expr` plus one reject arm. |
| `subset_query` | SPECIAL-CASE | cribbage, scopa; the `all subsets` arm is UNUSED. |
| `subset_of` | SPECIAL-CASE | Same. |
| `subset_source` | SPECIAL-CASE | List form cribbage only (`[played[p], starter]`); 1 reject arm. |
| `subset_of_guarded` | UNUSED | Three reject arms around `subset_of`. |
| `subset_size` | SPECIAL-CASE | `or more` cribbage, scopa. |
| `quantifier` | CORE | 13 arms: any/all player 15/11, any/all team 6/2, any suit 1, any rank 3, domain forms 1 (tic-tac-toe); `all suits`, `all ranks`, `any <domain>`, `number of <domain>` arms UNUSED. |
| `agg_query` | CORE | `sum` 13 games, `highest/lowest ... or` 6; both `over subsets` arms UNUSED. |
| `if_expr` | CORE | 25 games. |
| `elif_clause` | SUGAR | 15 games; nested if/else. |
| `or_expr` | CORE | 28 games. |
| `and_expr` | CORE | 27 games. |
| `not_expr` | CORE | All. |
| `comparison` | CORE | `is` / `is not` / comp_op / `in` all used. |
| `comp_op` | CORE | `==` / `!=` arms are reject-only. |
| `sum` | CORE | 25 games. |
| `term` | CORE | `offset_by` 18 games; `divided by ... rounded up/down` skat only (SPECIAL-CASE arms). |
| `factor` | CORE | `*` 12 games; the DIV_OP arm is reject-only. |
| `postfix` | CORE | member 23, subscript 36. |
| `arg_list` | CORE | All. |
| `primary` | CORE | All. |
| `list_lit` | SPECIAL-CASE | doppelkopf only (`card.rank in [A, "10"]`). |
| `card_literal` | CORE | 5 games (`2 of clubs`). |
| `card_rank` | CORE | Ranking enumeration and card literals; own terminal CARD_RANK_NAME. |
| `all_players` | SUGAR | `over all players` 18 games; a domain name, not a construct. |
| `call` | CORE | All. |
| `choose_expr` | CORE | cheat, oh-hell, pinochle, spades; `up to` 2, `excluding` 1. |
| `index_expr` | CORE | All. |
| `zone_expr` | CORE | All. |

## Appendix B: unused alternatives inside live rules

| Rule | Unused arm(s) |
|---|---|
| `rule_ref` | `- Name` (rule_remove), `override Name` (rule_override) |
| `select_mode` | `random` |
| TRANSFER_VERB | `burn`, `muck` (and `transfer` is used once, by hearts) |
| `subset_query` | `all subsets of ... where` |
| `quantifier` | `all suits where`, `all ranks where`, `any <domain> where`, `number of <domain> where` |
| `agg_query` | `sum ... over subsets`, `highest/lowest ... over subsets` |
| `comp_op` / `factor` | `==`, `!=`, `/`, `%` (reject-only) |

Keywords used by no file: `always card_values down override random ranks suits visibility`. Keywords used by exactly one file: `asking by concession divided early excluding exempts loser produce rotate rounded subsets through`.

## Appendix C: natives named outside `primitives { }`

Round-slot names, declared in no file: `bridge_auction_outcome`, `pinochle_auction_outcome`, `tarot_auction_outcome`, `bigtwo_lead_options`, `bigtwo_follows`, `president_lead_options`, `president_follows`, `tichu_lead_options`, `tichu_follows`. Called but defined nowhere: `strain_index` (bridge). Kernel side-channel state read with no declaration: `state.led_suit` (22 reads), `state.shed_first` (10), `state.shed_second` (8), `state.trick_terminated_early` (1), `state.lead_ended_trick` (1).
