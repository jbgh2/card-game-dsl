# Auction rounds are `turns` plus `offer` — the plan record

Issue #819 (epic #818, Destination 3: one meaning, written once). Merge
Lane A: the grammar loses `auction_stmt`, `auction_moves` and the
`offering` keyword; two Merge Lane B capabilities land first; the corpus
moves in lockstep. The operator merges, with Hoyle's counsel below.

## Acceptance criteria

1. Runs: every corpus game checks and plays; the dead-surface report
   (`python -m tools.dead_surface`) names no rule or keyword this change
   leaves orphaned.
2. Regression-clean: bare `mypy`, full `pytest`, the experiment rigs. The
   per-seed score and hand goldens are byte-identical at full width
   (`CARDLANG_GOLDEN_SEEDS=full`). Four IR goldens (Bridge, French Tarot,
   Pinochle, Seven-Card Stud) and four stream-hash goldens (Belote,
   Doppelkopf, Five Hundred, Skat) regenerate for a stated reason: the IR
   holds `turns` + `offer` nodes where it held `auction_round`, and the
   hashed stream carries the `asked` event's construct word, which reads
   `offer` where it read `auction`. The neutrality of each regeneration is
   proven by the identity probe (below), never by the regenerated file.
3. Info sets derive: the converted sites emit the `asked`, `chose` and
   `announce` events `offer` already emits; the per-observer stream is
   byte-identical to the auction form's on every probed seed once the
   construct word is normalised, and the readiness proofs hold on the new
   tree.

Corpus lockstep (operating rule 2), 16 of 34 game files: belote, bridge,
doppelkopf, five-card-draw, five-card-stud, five-hundred, french-tarot,
holdem, holdem-heads-up, kuhn-poker, leduc-poker, pinochle, schnapsen,
seven-card-stud, skat, tichu — 46 auction sites in all, 6 of them
single-seat, 3 carrying an `outcome` clause. Their rulebook twins where
the twin names the form (bridge, pinochle, schnapsen, skat). The family
library `poker_betting` and its seven consumers.

Witness: the corpus itself — Five-Card Draw already writes its draw as
`turns` + `offer`, and every auction game is the same loop.

Reachability: R2 (the issue's label). A designer writing any bidding game
meets both spellings at the first auction.

## Classification

Grammar surface (Lane A) · parse builders, AST, resolve, typecheck, IR,
runtime, OpenSpiel encoding, stdlib tables (Lane B) · 16 corpus games and
one family library (Lane C under a Lane A unit) · spec docs and glossary
(Lane B) · goldens regenerated (Lane B). The surface-totality audit fires
twice: a retired production (the `turns` grid absorbs the auction form's
cells) and a widened closed domain (the `requires` contract gains a kind).

## The library-first proof (run, not asserted)

Every probe plays the rewritten text and the committed text over the same
seeds under the reference policy and compares results, the per-observer
observation stream and the trace stream.

| Probe | Result |
|---|---|
| Kuhn, the one site as `turns` + `offer`, 200 seeds | results, streams and traces identical; the only delta is the `asked` construct word (456 relabels) |
| Kuhn, the same loop inside a game-local `procedure street(first : Player)`, 200 seeds | identical, as above |
| All 16 games rewritten by a tree-to-tree rewriter (spans sliced, the three `outcome` sites hand-written as `produce`), 30 seeds each (Tichu 20) | identical on every seed, every game, modulo the construct word |
| A `poker_betting` procedure offering the game's `fold` | refused: "names the move type 'fold', which the library does not have" |
| The same with `requires { fold : Move }` | parses; refused at the type slot: "names the type 'Move', which the library does not have" |
| Tichu's in-trick small-tichu window as `turns` inside `before asking` | refused: "the Hosted Poll may not hold `turns`"; identical on 20 seeds once the stdlib table admits it |
| The library street's full vocabulary `[check, bet, bet_big, call, fold, raise, raise_big]` in every consumer | candidates identical (identity probe); action-space sizes: Kuhn 4 to 7, Leduc 5 to 7, Five-Card Draw 59 to 61, Hold'em 5 to 7, Hold'em heads-up 5 to 7, both Studs 7 unchanged |

Two capabilities, both Merge Lane B, both sentences the grammar already
parses: a `requires` entry may name a move type the game defines
(`fold : Move`), and a Hosted Poll body may hold `turns`. Neither is a
production; the mechanic lands as definitions.

## Hoyle's counsel

### Headnote

Sixteen of the thirty-four games write a bidding or betting ring as
`round offering [...] from X over P until C`, and ten write the same ring
as `turns t from X over P until C { offer to t one of [...] }`. Both
exist today; a designer meets both at the first auction. The recommended
sentence is the second, in Bridge:

```
turns bidder from dealer over all players
      until (made_bid and passes >= 3) or (not made_bid and passes >= 4) {
  offer to bidder one of [pass, submit_bid, double, redouble]
}
```

The losing rival is the sentence we have, kept beside it. The library
form is the recommended sentence itself: it checked and played identical
to the auction form in all 16 games on every probed seed, so the auction
production is a mechanic wearing syntax and retires. The grammar narrows
and nothing widens; the two capabilities needed (a library contracting
for the game's `fold` as `requires { fold : Move }`, and `turns` inside a
Hosted Poll) are checker and stdlib-table changes, not productions. Three
natives leave engine core with the form (the Bridge, Pinochle and Tarot
outcome functions), their rulings written in the games as `produce`;
Bridge's declarer rule becomes five declared state variables, one per
strain, written as the bids are made. One settled commitment is cut
against in words: the ruling that the ring is "an axis on the `round`,
not a `repeat until` wrapped around a single-pass round" — the ring is
now `turns`, which owns exactly rotation and termination, so the ruling's
reason survives and its sentence does not. Information sets do not move:
the identity probe shows every observer's stream byte-identical once the
decider's own `asked` event reads `offer` for `auction`. The cost: four IR
goldens and four stream-hash goldens regenerate; the OpenSpiel action ids
of nullary bidding moves move from the offering block to the names block
in all 16 games (sizes unchanged); and the one library street adds two or
three never-legal action ids to five of the seven poker games. What the
operator decides: one street procedure with the family's whole
vocabulary (recommended, measured above), or one-size and two-size
twins that keep Kuhn at 5 ids and Hold'em at 5.

### 1. The sentences

In situ, Pinochle's ascending auction (the shrinking ring):

```
turns bidder from opener
      over players where not passed[player]
                        and (lead_bidder is none or player is not lead_bidder)
      until (number of players where not passed[player]) <= 1 {
  offer to bidder one of [submit_bid, pass, pass_with_help]
}
if lead_bidder is none {
  produce bid_won(seat_under, (bid_tens + 1) * 10)
} else {
  produce bid_won(lead_bidder, working_bid)
}
```

and a single-seat site, the trump declaration: `offer to high_bidder one
of [declare_trump_suit]` — a plain `offer`, because any one move
satisfies the clause the ring was written with. Schnapsen's leader, who
may take free actions before leading, keeps the loop: `repeat until
trick_pile is not empty { offer to leader one of [...] }`.

Alternatives weighed:

- Keep `round offering ... until ... [outcome f]` (the rival). Reading:
  "run a bidding ring". It is the sentence sixteen games write; it is
  also the second spelling of the loop ten games write the other way, and
  it binds a bid history no designer can read, consumed by a native no
  designer can write.
- The library form, verbatim: the recommended sentence. It checked.
- `run auction(dealer, ...)` as a library procedure taking the ring's
  predicates (the brief's sketch). Reading: "run the auction". Needs a
  predicate-valued parameter the language lacks, which is a production;
  rejected here because the kernel sentence above already carries every
  auction without it.
- For the street: `requires { fold : Move }` against the keyword-led row
  `requires { move_type fold }`. The first parses today and is refused at
  the type slot — a checker change; the second is a new production for
  the same contract — Lane A for no capability. `fold : MoveType` was
  weighed and loses on the glossary: the type column names the KIND of
  declaration that answers the row, and the player-action family's word
  is Move.

Misparse hazards: `until <expr> {` ends the clause at the brace, so an
`until` written with a trailing `or` operand absorbs up to the brace
exactly as `repeat until` does today; the `offer` list's `[` after `one
of` is the shape every `offer` already has. `fold : Move` shares the
`requires` row shape with state and zone contracts; a `fold[player] :
Move` is a misuse (a move type has no index) and is refused in resolve.

### 2. Precedent

Extends: decisions.md "The `turns` form" (the binder is the turn-holder;
rotation, termination placement and the participants predicate are the
form's), "Named procedures" (a body may hold `turns`), "Family
libraries" (the contract names what the game declares), "Typed phase
outcomes" (`produce` from the phase body), "Interactive decisions: a
kernel and an in-DSL standard library" (a definition adds words, not
semantics — the street is a procedure, the auction is the kernel
sentence). Cuts against, and retires: "The auction form of `round`" as
a section, its ruling that the continuous ring is an axis on `round`
rather than a loop, and the glossary's Round entry naming three forms.
The reserved word `outcome` stays reserved for the phase clause; the
`offering` keyword retires and the Offering glossary entry's home becomes
`n.Offer` alone. The reserved-words check is unchanged.

### 3. Corpus impact

The 16 games above move in lockstep, plus `poker_betting` and the stud
fixtures under tests. Witness: the corpus — ten games already write the
loop this way, and the four hand-rolled trick-takers are the brief's
evidence that `turns` is the loop beneath every ring.

### 4. The totality edge

The grammar accepts nothing new. The retired production's cells move to
the `turns` grid (tests/test_turns_form.py): a shrinking participants
ring re-evaluated per turn; a leader the predicate excludes, skipped with
no draw; termination before the first turn; a counterclockwise ring; a
single-seat re-ask through `repeat until` + `offer`; a typed outcome
`produce`d after the loop in an outcome phase; `turns` spliced through a
procedure; `turns` inside a Hosted Poll (red until the table admits it).
The `requires` grid (tests/test_family_libraries.py) gains the move-type
contract kind: answered by the game's own move type; unanswered; answered
by a state variable or zone of that name; indexed; contracted by a
library that also defines it; answered by another library's definition.
Misuse sentences a designer would write: `requires { fold : move_type }`
(a syntax error naming the row shape), `requires { fold[player] : Move }`,
a library offering a move type it neither defines nor requires.

### 5. The info-set bound

Each converted site emits what `offer` emits: `asked` to the decider,
`chose` to the decider, `announce` to every seat. The identity probe
shows every observer's stream byte-identical to the auction form's on
every probed seed once the `asked` construct word is normalised, and that
word is a per-site constant, so the partition is unchanged. No debt.

### 6. Counsel

For: one loop, one spelling; the bid history becomes declared state a
designer can read; three natives leave engine core; the grammar loses
two rules and a keyword with no replacement; every proof above ran green
on this tree.

Against: four IR goldens and four stream-hash goldens regenerate, and a
regenerated golden proves only that the tree equals itself — the identity
probe is the evidence, so it must be kept beside the regeneration as a
test, not a scratch script. The OpenSpiel action ids move for every
converted game, and the one library street mints never-legal ids in five
games; a recorded action-id history of Kuhn dies with the space.

Hoyle would retire the form, land the two capabilities first with their
grids red, and ship the one library street with the family's whole
vocabulary, naming the id cost in the PR. The operator rules.

## The task list — each step names its proving artifact

0. Grid red first (tests only).
   - tests/test_turns_form.py gains the cells in section 4; born-green
     cells name their reddening mutation; the Hosted Poll cell is
     `xfail(strict=True)` until step 1a.
   - tests/test_family_libraries.py gains the move-type contract rows,
     red until step 1b; the misuse probes above.
   - the identity probe, run against the engine before the form retires
     and quoted in the PR body as a dated measurement: once the production
     is gone, the engine that retired it cannot parse the originals, so
     the comparison cannot live in-tree.
1. Capabilities (Lane B), each with its grid green and its decision line.
   - 1a. `n.Turns` admitted in stdlib/hosted_poll.py; the hosted-poll pin's
     expected column moves; decisions.md "Off-the-clock windows" and
     glossary/hosted-poll.md say so.
   - 1b. resolve: a `requires` row typed `Move` contracts for a move type
     the game defines; `_library_slot_names`/`_library_reach` count it
     as the library's; `_check_requires` answers it from the game's own
     move types and refuses the crossed shapes; decisions.md "Family
     libraries" states it.
2. Corpus (Lane C files): the 16 games, the twins, `poker_betting`'s
   `betting_street`, the seven consumers, the stud fixtures; goldens
   byte-identical at full width; IR and stream-hash goldens regenerated
   with the identity test green beside them.
3. Retire the form (Lane A): grammar, parse, AST, resolve, typecheck,
   IR, deckcheck, execute, mechanics, delegation, encoding, primitives
   and the three natives, builtins/functions, signatures,
   primitives_block, reads, stdlib/round_state, play/events; the round
   grid's templates; the retired-surface pin gains the rows; the
   dead-surface report clean.
4. Docs: decisions.md ("The auction form of `round`" retired; "The
   `turns` form" carries the ring rulings); library.md; model.md;
   kernel-migration.md; glossary entries and the regenerated index; the
   four twins.
5. Gate: bare `mypy`; `pytest -q -n 8`; the rigs; the full-width golden
   sweep; `tools/lane-of.sh`; the PR with this counsel, Headnote first.
