# Phase-scoped read declarations: `reads X in <phase>`

Operator go: Ben, 2026-08-30 — issue #504 closes PROPERLY, option A ("do the
full send"). One new surface: a per-read `in <phase>` tail on the
`primitives { }` block's reads clause, so an entry may declare a read of
state a PHASE declares. Five corpus games wait on exactly this
(seven-card-stud, holdem, pinochle, french-tarot, canasta — the stage plan's
walled five, `docs/plans/2026-08-29-primitives-block-stage3b.md`); the
construct lands WITH pinochle migrated in the same PR (witness-in-change),
and the other four follow one PR each. The last of those closes #504.

Both counsels are attached below and BIND: Hoyle's rules the surface
(the spelling, the containment rule as the designer reads it, the seven
walls, the glossary obligations, the grid frame); the Architect's rules the
engine (the four choices, the premise pin, the prose rewrites). A
fresh-context framing check ran before this plan froze; its load-bearing
facts are folded into the obligations below and its extract travels with
the implementing branch.

## Acceptance criteria

1. **Runs** — pinochle plays under the declared regime with a scoped read;
   every grid accept cell PLAYS, never merely resolves.
2. **Regression-clean** — bare `mypy`; CI's three checks; byte-identical
   full-width playout goldens for pinochle (and each later game); IR goldens
   for the block games regenerate ONCE (the `primitive_read` row gains an
   always-present `phase` key, the `binder` precedent) with that reason
   quoted; no other golden moves.
3. **Info sets derive** — the tail is declaration-only surface: nothing new
   is emitted, nothing hidden moves; `tests/openspiel_ready/` untouched.
   (The framing check verified phase state already participates in the
   information state via the frame merge; the tail changes declarations,
   not that merge.)

## Gate record (cardlang-planning)

- Gate 1: Hoyle counsel attached (Lane A — mandatory); Architect counsel
  attached; glossary obligations named in Hoyle section 2 ([[reads-clause]]
  and [[primitives-block]] extended, [[phase-scoped-read]] minted, the
  primitives-block entry's worked example corrected — it prints this
  construct's sentence today, unwritable until now). Ordering: #504 under
  #142; operator-started.
- Gate 2: grammar surface (one optional tail on one production + one reject
  twin) + a resolve Owner Guard family + an AST field with IR consequence —
  the audit fires; the grid is authored red before implementation.
- Gate 3.5: R2 — five games and every future designer with phase-scoped
  primitive state.
- Gate 4: the framing check ran fresh-context (frames, positions, offer
  edges, consumers) before this plan froze; the surprises it forced into
  the plan: the driver's kind-filter silent-drop hazard (dissolved by the
  no-new-ReadKind ruling), `legal_moves:`' runtime inertness (the premise
  pin's subject), sibling-phase same-name legality (vindicating the
  explicit tail), the IR emit-or-drop channel (made loud by the schema
  pin once the key is emitted), and three witness line numbers that were
  comments (corrected in the counsel's table).
- One operator-reserved choice, adopted as counseled pending veto:
  descendant re-declaration is REFUSED AT COMPILE (fourth leaf predicate;
  zero corpus cost, measured 2026-08-30) rather than resolved by runtime
  frame-targeting (rejected by both seats).

## The construct, as ruled

Surface (Hoyle section 1): `primitive_read: NAME [index] [_IN_KW NAME]` —
per-read tail, one phase per entry's clause; reject-with-replacement twin
for the transposed binder (`X in P[b]` -> "write `X[b] in P`"). The
sentence: `pinochle_meld_value(p : Player) : Integer reads hand[p],
trump_suit in hand_sequence`.

Containment (Hoyle, refined by the Architect's taxonomy): an entry with a
scoped read is callable only (1) inside the declaring phase's subtree —
qualifier expression, `before_each`, `after_each`, body, nested phases (its
own state defaults cannot hold a call: `_check_state_default_scope`'s Call
ban is the cited Owner); (2) from a game move type ALL of whose offering
POSITIONS sit inside that subtree (offered nowhere = refused); (3) a
procedure body is judged at every `RunStmt` naming it (resolve runs
pre-expand; splice is by value); (4) functions, defines, rules, trick-order
rows, `loser:`, and every other game-level expression position — refused.
An offering site's POSITION is where the offer HAPPENS, never where its text
sits: an offer written in a procedure body is positioned at every `run` of
that procedure, by the same by-value reasoning as (3), so a procedure run
only inside the subtree may offer freely. The one container this analysis
does not position is another move type's own body — following an offer made
there means judging the OFFERING move type's containment first, itself
decided by ITS offers, up a chain that can cycle. That is a WALL: refused
with a message saying the analysis does not follow offers made from inside
another move type, never that the state does not stand (issue #521; coup's
move-type effects hold three such offers, and it migrates when its eviction
wall falls). A procedure no statement runs is `_check_procedures`' never-run
refusal, cited rather than shadowed. The offering-surface relation DERIVES
from resolve's reference-slot registry (seven move-type-naming slots today:
five offering, two non-offering), pinned total so an eighth slot arrives
unclassified and reddens; edges match by NAME across both move-type
namespaces (pinochle's `declare_trump_suit` is the live overlap witness).
One correction to the grid frame quoted in Hoyle's counsel below, which
stands as the seat wrote it: `demands:` is a RULE clause, not a move type's,
so there is no move-type `demands:` offering cell — rules are a refused
container, sampled by the rule-applies-when cell.

Engine (Architect section 4): `PrimitiveRead` gains `phase: str | None`;
`classify_read` gains a `phase` parameter (with it: that phase's own block
alone decides kind and indexedness); NO new `ReadKind` members (scope is
not a kind — the designed-constraint sentence lands on the enum);
`rs.get`'s innermost walk unchanged — correct by construction under the
fourth predicate (a strict descendant of the tail's phase re-declaring the
name is refused; the leaf gains a path-aware phase walk, agreement-pinned
against the engine walk). Tail-validation arms land in
`_check_primitive_reads` beside the three collision siblings, BEFORE
classification; the containment analysis is resolve's own check after
`_check_primitives_block`. `run_phase` gains the comment naming resolve's
containment check as the consumer of its declare-before-run ordering.
The declared path's typed miss for a scoped name names the declaring phase
and the Owner (a Shadow Guard by construction). `_block_facts`' tuple
gains the tail (twin drift otherwise invisible); the rename oracle's
`_coupled_names` needs no change (bare names) but `(n.PrimitiveRead,
"phase")` registers as a phase reference slot beside `(n.ContinueTo,
"phase")`.

The runtime PREMISE the guard leans on — game move-type bodies execute
only inside offering sites' dynamic extents — is pinned two-readers style
(a scrape over the runtime's `move_type_index` readers; 2 channels across
4 sites today), and the ledger's does-not-prove line records both the
premise and that a scoped entry with zero calls passes containment
vacuously (the declare-only-called-names recipe discipline stands).

## The grid (red first; Hoyle section 4 is the frame, Architect (d) the witness map)

Axes: spelling forms x referent membership x clause composition x
containment positions x interactions with the three standing collision
arms x the library axis. The five witnesses carry the accept half —
verified by execution, including stud/holdem's INDEXED phase state
(binder-x-tail live), canasta's move-type leg (multi-offer accept, a
declaring phase literally named `hand`), pinochle/tarot's descendant-phase
calls. Every refusal cell is synthetic, declares REAL registered
implementations (the borrowing precedent), and ships with its accept twin
(the corpus-confound rule). Accept cells PLAY; one synthetic nested
fixture's playout reaches a scoped call from qualifier, `before_each`, and
`after_each`. Misuse probes: the list-scope misreading (`reads committed,
folded, in_hand in play` — only the last is scoped; the diagnostic teaches
the per-read form), the wrong-phase and near-miss-descendant tails, the
tail on game state / on a zone, the transposed binder, the later-added
outside offer (span at the offending offer).

## Prose and pins that move in the same change

Six sites asserting the old wall rewrite (the Architect's list):
`classify_read`'s docstring, `phase_local_state_names`,
`shadowed_state_names`, `phase_state_zone_names` + its diagnostic's
parenthetical, and the phase-local arm's message (gains "or declare it
`X in P`"). The reads-clause law in `docs/glossary/reads-clause.md`
("refused outright" becomes "refused unless declared with its phase");
the stage plan's step-2 stop-and-report line and closing-steps section;
issue #504's paths section is superseded by this plan (the issue closes
with the last game PR, never before). All reworded message pins re-bless.

## Delivery shape

- **PR 1 (this plan's own):** the surface, the guards, the grid, the
  glossary, the prose rewrites, the IR field + schema + block-game golden
  regeneration, the premise pin — and pinochle migrated (block with
  `trump_suit in hand_sequence`, row/ROW/arm deleted, auction row
  surviving per the narrowed pin, full-width byte-identical goldens).
  Part of #504 and #142.
- **PRs 2-5:** seven-card-stud, holdem, french-tarot, canasta — one each,
  per the stage recipe (the step-2 gate now passes them), full-width
  proofs; canasta exercises the move-type leg live. The last closes #504.
- Contract blocks read before freezing (the Architect's list): resolve's,
  primitives_block's, reads.py's, expand.py's, and
  `driver.declared_primitives`' totality claim, which gains the
  containment fact.

## Hoyle's counsel (2026-08-30, attached per docs/harness.md "The Language Owner")

**Headnote.** Five games — seven-card-stud, holdem, pinochle, french-tarot, canasta — wait behind one missing sentence, and the ruled sentence is, verbatim: `pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit in hand_sequence` — a per-read `in <phase>` tail on the reads clause, the exact sentence the Primitives Block's own glossary entry already prints as its worked example and which today no game can write. The losing rival is the diagnostic's own path — pass the phase value as an argument, which closes all five games with no grammar change at all; its cost is that every betting-street call site in stud and holdem hauls three arguments the game text never speaks, and the block stops reading like the game. This is Merge Lane A: the grammar widens by one optional tail on one production, plus one reject twin for the transposed binder. Corpus: five game files move, witness-named, thirteen phase-declared names across their five registry rows (measured 2026-08-30 from the rows themselves); at least one witness — pinochle, the smallest — lands in the same change as the surface. One settled commitment is reworded, not cut: the reads-clause law that a phase-only name is refused outright becomes "refused unless declared with its phase", and three existing refusals (game-and-phase shadow, phase-and-zone, two-phases-in-one-clause) stay standing as walls, each with a named unblocking witness. The containment rule the surface implies: an entry with a phase-scoped read is callable only inside that phase's own block, or from a move type offered only inside it — functions, defines, rules, and everywhere else are refused, and among the five witnesses no function body calls a primitive, so the wall over-refuses nobody real. Info sets do not move — the tail declares what the legacy rows already read dynamically, proven by untouched OpenSpiel proofs and byte-identical full-width playout goldens. Bottom line: land the `in <phase>` tail with the seven walls and pinochle in the change; the strongest reason against is that the argument-passing path was free and this path buys new static machinery mid-wave — its cost is a containment guard and its grid; the operator has already ruled the direction, so what remains to decide is the walls as listed and whether the surface lands with its witness or ahead of it.

### 1. The sentences

The ruled surface, in situ. Pinochle (the landing witness — one scalar read, one call, one nested-phase hop):

```
primitives {
  pinochle_meld_value(p : Player) : Integer reads hand[p], trump_suit in hand_sequence
}
```

Read aloud: "pinochle_meld_value of a player is an Integer; it reads that player's hand, and trump_suit in hand_sequence." Stud, the repeated-tail shape:

```
primitives {
  bring_in_seat()       : Player  reads upcards, in_hand in play
  pot_share(p : Player) : Integer reads upcards, hole, committed in play, folded in play, in_hand in play
}
```

Canasta, the mixed clause (game-level `score` beside four phase-scoped names — the witness that forces per-read scoping rather than a clause-wide tail):

```
canasta_can_take_pile(p : Player) : Boolean
    reads hand[p], pile_top, score, meld_rank in hand, taking_pile in hand, pile_frozen in hand, team_melded in hand
```

(Illustrative per-entry reads; each migration PR derives the entry-grain sets from its implementation module, never from this counsel.)

Production: `primitive_read: NAME [index] [_IN_KW NAME]`, plus one reject-with-replacement twin for the transposed binder (`team_melded in hand[team]` -> "the binder rides the variable, not the phase: write `team_melded[team] in hand`") — the block's own colon/arrow/default-twin mechanism, and the one transposition a designer plausibly writes.

**Alternatives weighed and set aside:**

- `reads hand_sequence.trump_suit` — plain reading "the bidding-phase's trump_suit". Rejected: it mints a dotted qualified-name shape where the language reserves `.` for card and type fields (`card.suit`, `x.field` — the fixed-slot rationale in resolve's duplicate-names contract), and it cannot be read aloud as rulebook English. The vocabulary is the syntax.
- Inferred scope — admit bare `reads trump_suit` and let the resolver find the declaring phase. Rejected: sibling phases may legally declare the same state name (uniqueness is per declaration list, so `passed` can live in two auctions), and inference would pick silently — the same silent-classification class the 3b-0 F1 fix just closed. Explicit naming also puts the call-position constraint on the page where the block's reader stands, and lets the containment diagnostic name the phase the designer chose. One extra word per read.
- `during <phase>` — reads slightly better temporally, but mints a new keyword with the full anchoring recipe where `in` already exists anchored (`_IN_KW`, grammar line 917) with settled containment sense ("cards in hand"; "committed in play" = the variable contained in play's state). No new reserved word is the cheaper and the safer purse.

**Adjacency hazards for the misparse prober:** `in_hand in play` (a NAME beginning with the keyword — the anchor keeps it one token; the keyword-fusion sweep covers it); canasta's phase named `hand` beside the zone family `hand` in one clause (`reads hand[p], meld_rank in hand` — position disambiguates for the parser, the grid asserts the `in` slot consults phases only); the list-scope misreading (`reads committed, folded, in_hand in play` — parses with only the last name scoped; the first two stay refused and their diagnostic must teach the per-read form — the most plausible misuse in the whole surface, three-of-a-kind in stud makes it near-certain); the missing comma before the next entry (`... in play  pinochle_meld_value(` — must fail loud at the `(`, never absorb); `in play in play` and `in play[p]` (the twin) fail loud.

### 2. Precedent

- **The glossary's own example.** `docs/glossary/primitives-block.md` prints `reads hand[p], trump_suit` as the block's worked example — a sentence no game can write today, since `trump_suit` is phase-local. The naming authority already wanted this construct; the change corrects that example to the ruled spelling in the same edit.
- **The reads-clause law** (`docs/glossary/reads-clause.md`): "a name only a PHASE declares is refused outright — the row is materialized on every call, while a phase's frame stands only while that phase runs." This sentence goes false and is rewritten in the same change (prose states what is). The law's core — each name denotes exactly ONE declaration — is what the explicit phase name *serves*.
- **The three collision refusals** (resolve `_check_primitive_reads`, plus 3b-0's third sibling): the phase-local arm's message ("declare it in the game's `state { }`, or pass the value as an argument") gains the third fix — "or declare it `X in P`" — and the phase-x-zone arm's parenthetical ("a phase-local variable is unreadable by a declaration either way") goes false and is rewritten. Both are living spec; both move in this change.
- **Phase names are game-unique** — `_check_duplicate_names` runs `check("phase", ...)` over the whole walk. `in P` therefore names exactly one phase, always; the nested-same-name-phases question has an Owner already and the grid cites it rather than re-covering.
- **Cross-level state shadowing is legal at declaration level** (settled law, same docstring) — which is exactly why the flat reads namespace must carry the phase name to be unambiguous, and why the shadowed-pair wall below stays a wall.
- **Zones are game-level only** (resolve's own reason at the zone check: no phase-local `zones { }` form) — a scope tail on a zone name has nothing to denote.
- **A library cannot declare a phase** (`?library_item`: requires/state/rule/move_type/type/define/function/procedure — no phase production). The `in` slot resolves against the game's own phase tree, which is the only phase tree there is; the grid pins the absence off the grammar, the same mechanism as the collision-namespace-axis pin.
- **Procedures splice by value** as a real Block — so containment judges a `run` site's statements at their spliced position, and no procedure wall is needed.
- **Surface totality** (`decisions.md`): the tail crosses with the existing index binder; all four combinations the grammar accepts are implemented, witness or no witness.

### 3. Corpus impact

Five witnesses, derived from the games and the registry rows this sitting (2026-08-30), thirteen phase-declared names across the five rows:

| Game | Declaring phase | Scoped names | Call positions (derived from the file) |
|---|---|---|---|
| seven-card-stud | `play` (in `hand_sequence`) | `committed`, `folded`, `in_hand` | phase-body statements and round-config seat expressions — all lexically inside the declaring phase itself |
| holdem | `play` | same three | phase-body statement — same shape |
| pinochle | `hand_sequence` | `trump_suit` | one call inside `phase play`, a *descendant* of the declaring phase |
| french-tarot | `hand_sequence` | `taker`, `bid_level` | two calls inside `phase play`, descendant; one sits inside a `repeat` block |
| canasta | `hand` (in `deals`, in `match`) | `meld_rank`, `pile_frozen`, `taking_pile`, `team_melded` | phase-body calls in descendant phases `play` and `scoring`, plus five call sites inside `move_type` `when:`/`effect` — the move types are declared at top level and offered only by `offer ... one of` statements inside `phase play` |

Measured and load-bearing: **no function, define, or rule body among the five calls a primitive** (stud and holdem declare none; pinochle's, tarot's, and canasta's functions call only DSL functions). The function/define/rule wall below over-refuses no witness. Also not this surface's business: pinochle's and tarot's surviving auction rows (`lead_bidder`/`opener`/`working_bid`, `lead_taker`/`current_level` — phase-local to their auctions) belong to the walled namespaces and travel with stage 4's declaration slots under the reconcile pin's carve-out; nobody should migrate them through this tail, and the entry-name wall already refuses the attempt.

Lockstep: the surface lands with pinochle migrated in the same PR (witness-in-change — the construct never exists corpus-unused); stud, holdem, french-tarot, canasta follow one PR each per the stage plan, full-width byte-identical playout goldens each. The stage plan's step-2 stop-and-report line and its closing-steps section move when the surface lands; the glossary edits ride the surface PR.

### 4. The totality edge

The crossed domain for the audit's grid (Gate 4's frame — axes named here, cells derived in code, authored red first):

- **Spelling forms:** {bare, `[binder]`} x {no tail, `in P`} — four accepted combinations, all implemented; the scoped-indexed cell (`team_melded[t] in hand`) has no witness among the five and gets a synthetic probe. Reject cells: the transposed-binder twin, dangling `in`, doubled tail, `in` followed by non-NAME.
- **Referent membership** (what `X in P` finds): P declares X, X nowhere else — legal, the target. X also game-level (shadowed pair) — refused, wall. X also a zone — refused, the F1 sibling extended, wall. X declared in a different phase Q only — refused, diagnostic names Q (`declaring_phases` exists). X declared in two phases, P one of them — legal, the explicit name discriminates (synthetic probe, no witness). X nowhere — refused. P not a phase — refused; sub-cell where P names a zone or state variable, so the diagnostic does not mislead. Scope tail on a game-level-only name — refused as meaningless (accepted-but-ignored's cousin). Self-pair and same-list duplicates cite `_check_duplicate_names` and the clause's own repeat guard as Owners.
- **Clause composition:** mixed game-level + one phase's scoped reads — legal (canasta witness). Two distinct phases in one clause — refused, wall. Scoped read on a PURE entry — the existing pure-reads guard Owns it (probe that it still fires with the tail present). Repeat of one name bare and scoped (`X, X in P`) — the repeat guard keys by name and must still refuse.
- **Containment positions** (call sites of a scoped entry): declaring-phase body — legal (stud). Descendant phase — legal (pinochle, tarot, canasta). Round-config expression — legal (stud). `before_each`/`after_each` of the declaring phase — legal, synthetic probe, with the frame-liveness verification obligation named in the ledger. `produces:` handler inside the subtree — legal, synthetic. Ancestor phase, sibling phase, game level, `winner:` — refused. Move type with all offering sites (the four offering surfaces: `legal_moves:`, `offer ... one of`, `round offering [...]`, `round <name>`) inside the subtree — legal (canasta, `when:` and `effect`; `demands:` synthetic). Move type with one outside offering site — refused, span at the offending offer. Move type offered nowhere — refused (vacuous containment is the guard that cannot fire). Function/define/rule body — refused, wall. Procedure body — judged at the spliced position, probed both sides of the phase boundary. The offering-surface enumeration is grammar-derived and pinned, so a fifth offering form reddens the pin.
- **Interaction with the existing refusals:** each of the three standing collision arms probed *with* the tail present — the new surface must not lift them silently — and the legacy regime untouched (no block, no tail).
- **Library axis:** no library phase exists to name (grammar-derived pin); library-provided state is game-level, so a tail on it hits the game-level refusal; a library move type reaching a game's scoped entry is settled by the library-encapsulation sweep — the grid states which wall answers, off the grammar, never by assumption.

Most plausible misuse sentences, each proven loud: the list-scope misreading (`reads committed, folded, in_hand in play`); the wrong-phase guess (`reads committed[player] in betting` — no such phase; diagnostic names `play`); the near-miss descendant (`reads meld_rank in deal` — real phase, wrong declarer; diagnostic names `hand`); the tail on game state (`reads stack in play`); the tail on a zone (`reads hand in play`); the later-added outside offer of a scoped-calling move type (canasta's maintenance hazard — the leak diagnostic's whole audience).

### 5. The info-set bound

The tail is declaration-only surface: no zone, move, or observation change; nothing new is emitted and nothing hidden moves. At run time the scoped names materialize from the live frame — exactly what the legacy `PRIMITIVE_READS` rows already do dynamically; the construct declares the practice, it does not change it. Proof per migrated game: `tests/openspiel_ready/` untouched and the byte-identical full-width playout goldens (the stage's own acceptance criteria). No info-set debt to record. Two obligations for the implementing change: (i) the containment rule's soundness rests on the phase frame being live for every statement lexically inside the phase's subtree, `before_each`/`after_each` included — the implementation cites the kernel site that guarantees it or excludes the hook blocks from the legal set; (ii) any runtime frame-lookup failure kept in the materializer is a Shadow Guard whose comment names the resolve Owner Guard (write-time triage), and an absent declared key still fails in the typed channel per 3b-0 item 3, never as a bare `KeyError`.

### 6. Counsel

**For:** the sentence is the one the block's own naming entry already prints; it keeps the reads clause the load-bearing clause (the state a primitive sees, stated where the primitive is declared) instead of scattering phase values into call-site argument lists that the game's English never speaks; the phase name does double duty — it picks the one declaration the reads-clause law demands, and it carries the call-position constraint to the reader; it reuses an anchored keyword, mints no reserved word, and its containment rule is static, sound, and refuses loudly everywhere it cannot prove liveness. The five witnesses force exactly the three legal position classes the rule admits, and nothing more.

**Against, strongest:** path 1 was free. The diagnostic already tells every migrating agent to pass the value as an argument; that closes all five games with zero grammar surface, zero new guard machinery, and per-game proofs the stage already owns. This path buys a containment analysis (call sites joined to offering sites), a grid across six axes, and seven walls' worth of issues — mid-wave — to make five declarations read like their games. If the operator had not already ruled, Hoyle would have put that choice squarely first: the cost is real and the yield is legibility plus the retirement of five legacy rows on the language's terms rather than the workaround's. A second honest against: the first landing over-refuses (functions, mixed phases, shadowed pairs, no-offer move types) — every one a deliberate wall with a workaround in the diagnostic, but a designer will eventually stand at one.

**What Hoyle would do:** rule the per-read `in <phase>` tail exactly as in section 1, one phase per entry's clause; state the containment rule in the designer's words — *"a read declared `in <phase>` makes the entry callable only where that phase is running: inside that phase's block, or from a move type offered only inside it"* — with the diagnostics of section 4 and spans at the site the addressee must fix; hold the seven walls (walled-namespace rows stay out; library phase state unconstructible and pinned so; shadowed pair stays refused, `in` does not lift it — no witness, and the two-lookup materializer is the silent-wrong-half hazard; phase-x-zone stays refused likewise; one phase per clause; function/define/rule bodies refused; no-offer move types refused), each deferral filed with `blocked:needs-witness` naming the game shape that unblocks it; land the surface with pinochle migrated in the same PR and the glossary edits of section 2 aboard (extend [[reads-clause]] and [[primitives-block]], mint [[phase-scoped-read]]); route the containment guard's placement through the Architect's own counsel (it is new resolve machinery with a Contract to extend — Hoyle rules the surface, not the pass); and hand Gate 4 the section-4 frame with the grid authored red before a line of the implementation exists.

## The Architect's counsel (2026-08-30, phase-scoped reads — #504 option A; attaches beside Hoyle's counsel, whose surface rulings bind throughout)

**Headnote.** Four engine choices, each ruled, none moving an information set — the tail is declaration-only surface and emits nothing. First: the phase rides as a FIELD (`PrimitiveRead.phase`) and a parameter on the one classifier, never as new `ReadKind` members — a scoped state read materializes identically to a game-level one, so a kind split would cost a five-file closed-domain sweep for zero behavioral distinction; the IR read row gains an always-present `phase` (the binder's exact shape), regenerating every block-game's IR golden once with the reason quoted, and the twin pin's fact tuple must carry the tail or twin drift in it is invisible. Second: the containment guard is resolve's — a scope fact, the actor-alias precedent — landing as its own check after block validation and necessarily before `expand` erases the procedure-run sites; its offer edges derive from the resolver's reference-slot registry (7 move-type-naming slots, 5 classified offering, the table pinned total so an eighth slot reddens), matching by NAME across both move-type namespaces because the overlap is real (pinochle's `declare_trump_suit` is kernel-listed and game-defined at once). Third: the materializer does not change — `rs.get`'s innermost walk is CORRECT once a fourth leaf predicate refuses a strict descendant of the declared phase re-declaring the name; measured 2026-08-30, the corpus holds zero such pairs and zero duplicate phase names across 31 games, 92 phases, and 197 phase-state declarations (known-positive control planted and caught), and phase-name uniqueness is already an Owner Guard game-wide. The kernel liveness site is `run_phase` (push, declare, then qualifier, before_each, body, after_each, pop in finally): **before_each and after_each are ADMITTED**, the declaring phase's own qualifier with them, and the one position the subtree admits syntactically but the frame does not — its own state defaults — already cannot hold a call (the default-Call ban owns it). Fourth: the five witnesses carry the accept half exactly as Hoyle derived them — verified by execution, including stud/holdem's player-indexed phase state (the binder-x-tail cell has live witnesses) and canasta's declaring phase literally named `hand` — while every refusal cell is synthetic, built on real registered implementations, each with an accept twin proving the arm discriminates, and every accepted cell PLAYS rather than merely resolves. Newly impossible: a descendant phase re-declaring a name any scoped read names, and a scoped entry called from a function, define, rule, trick-order row, game-level expression, or an offering site outside the declared phase's subtree; newly required for migrating agents: the five games' blocks carry tails, six prose sites asserting the old "unreadable by a declaration" wall rewrite in the same change, and the message pins re-bless. Precedent standing: every citation established (P2, P6, P7, P9, P11, P13); no unverified lead is relied on. Bottom line: take all four rulings; the strongest case against is that the guard's soundness rests on a runtime premise no static pass can see — game move-type bodies execute only inside offering sites' dynamic extents, true today at exactly 2 channels across 4 consumer sites — whose failure mode is a green guard gone silently unsound, priced by a premise pin that must be maintained when the next execution channel lands; the operator decides one thing — descendant re-declaration refused at compile (counseled) versus resolved by frame-targeting at runtime (rejected: a RuntimeState redesign to buy what a refusal buys for four lines).

**1. The decision.** Not whether the tail exists or how it reads — Hoyle's, ruled. Four engine choices: (a) where the phase rides — an AST field plus a classifier parameter, or new `ReadKind` members — with the coordinated-table bill for each; (b) which pass owns the call-site x offering-site containment analysis, how the offering-surface relation derives, and where each refusal's span points; (c) whether the materializer keeps `rs.get`'s innermost frame walk or targets the declared phase's frame — and the compile predicate that decides which is correct; (d) which grid cells the five witnesses carry and which take synthetic fixtures.

**2. The law.** resolve's Contract: the ONLY pass that classifies names; it already establishes that every classified reads name is single-membership across the four namespaces, "which is what lets `runtime/driver`'s materialization call the same classifier with no refusal of its own" — the tail extends that establishment rather than adding a rival. The same Contract carries the placement precedent in its own words: the actor-alias comparison rule is "a scope fact, not a type fact — settled here rather than in the type layer". `_check_state_default_scope` bans every `Call` in every state default, game-wide, and its Contract line licenses the driver to assume defaults evaluate against the standing frames — that guard OWNS the one in-subtree position where the frame stands but the name may not. `_check_duplicate_names` enforces phase-name uniqueness GAME-WIDE (`check("phase", ...)` over the whole walk), so the tail resolves by name with no ambiguity arm; the same guard's docstring settles that cross-level shadowing stays legal at declaration level — the refusal class is reads-clause-level, exactly as the 2026-08-29 counsel ruled for the three sibling predicates. `primitives_block.py`'s Contract: the leaf owns the ONE classification of a reads name, the collision predicates, and the phase attribution diagnostics need. `reads.py`'s Contract: name-keyed reads fail typed through both doors, accessor and bundle halves (3b-0 item 3 is landed machinery). Pipeline order binds choice (b): resolve -> typecheck -> **expand** — resolve sees the un-spliced tree, so "judged at splice position" is a judgment resolve performs at each `RunStmt`, whose position IS the future splice position because expand splices by value. The prior counsel on this plan binds and is not overturned: `classify_read` stays refusal-unaware (it is also the loader's call, where a refusal could never fire); refusal arms sit in resolve before classification; `ReadKind` remains exactly the driver's materializable closed domain.

**3. Precedent.** P2 (pipeline): the phase fact stamps once — the field on the node, the parameter on the one classifier — and no consumer re-walks phase state blocks to rediscover scope. P6 (diagnostics): every new and reworded message lands in the blessed-snapshot rejection harness, tail variants included. P7: addressee, span, applicability — the spans below are chosen per refusal class for the designer who must act. P9: one source, every scrape derived and pinned — the offering-surface relation derives from `_REFERENCE_SLOTS` rather than being authored beside it. P11: a guard is trusted after it catches a planted fault and never calls the code it judges — every refusal fixture ships with its accept twin, and the containment premise pin reads the runtime's consumer sites, not the guard's own output. P13: declared-once, emitted-uniformly is untouched — the tail adds no observation and moves none. House precedent: `RULE_ENFORCED_MOVE_TYPE`'s two-readers pattern (a fact read by both the consumer and the Owner Guard that describes it, so neither drifts) is the shape for pinning the runtime premise; `tests/test_state_default_scope.py`'s played-cells lesson ("accepted" was exactly the assertion that hid the defect) is the shape for the accept rows; `_GAME_LEVEL_OWNED_BY_ANOTHER_GUARD`'s field-set pin is the shape for the position taxonomy's totality.

**4. The options.**

*(a) The AST and classification shape.* **A (counseled): field plus parameter.** `PrimitiveRead` gains `phase: str | None`; `classify_read(game, name)` gains `phase: str | None = None` — with a phase, it classifies against THAT phase's own state block alone (returning `STATE_VAR` or `INDEXED_STATE_VAR` by that declaration's index; zones and game state never consulted); without, current behavior. One classifier, both call sites (resolve's validation, the driver's materialization) coordinated by construction. The phase argument is needed under EITHER shape — which phase's declaration decides indexedness (stud declares `committed[player]`; another game may declare a plain `committed`) — so new enum members would duplicate what the parameter already carries. `BINDABLE_READ_KINDS` is untouched: stud/holdem's indexed phase state and canasta's `team_melded[team]` make the binder-x-tail cell live through the existing `INDEXED_STATE_VAR`. Coordinated tables, priced: the IR `primitive_read` row gains `"phase"` always-present, null when absent — the `binder` key's exact shape — so every block-game's IR golden regenerates once, reason quoted (the plan's stated exception, one extra pass over batch A/B games); `_block_facts`' fact tuple becomes `(r.name, r.binder or "", r.phase or "")` — without it, twin drift in the tail is invisible to the block-agreement pin; the rename oracle needs NO `_coupled_names` change (its derivation covers scoped reads by construction, and no transform renames phases) — the tail registers as `(n.PrimitiveRead, "phase"): "phase"` in `_REFERENCE_SLOTS` beside `(n.ContinueTo, "phase")`, which is what tells a future phase-renaming transform; the regime-product renderer is untouched (it renders entries with no reads clause) — the five games' later migration prices its spelling rows per signature, the recorded belote-gaps precedent. **B (rejected): `ReadKind` gains PHASE members.** The enum's own definition is "each kind materializes differently", and a scoped state read materializes identically — same `rs.get`, same bundle half, same `_narrow` — so the members carry no information the field lacks and cost the sweep across the kind's whole consumer set (primitives_block, resolve, driver, two test modules) plus a `BINDABLE` widening. `ReadKind`'s docstring gains the designed-constraint sentence — scope is not a kind — so the next designer meets the decision at the enum. **C (rejected): phase folded into the name key.** Breaks name-keying at every layer the row touches.

*(b) The containment guard.* **Owner: resolve; its own check, after `_check_primitives_block`.** The tail-validation arms — a tail naming no phase of the game; a tail naming a phase that does not declare the name (which also covers a game-level-only or zone-only name wearing a tail); the shadowed pair with a tail, refused with a message that does NOT say "cannot say which" (with a tail the declaration does say; the refusal stands because the game-level variable would be silently unreadable — Hoyle: `in` does not lift it) — land in `_check_primitive_reads` beside the three collision arms, before classification, plus the **fourth leaf predicate**: a strict descendant of the tail's phase declaring the same name, refused for the siblings' reason — the innermost walk would read the descendant's value, a wrong answer with no failure anywhere. The leaf gains a path-aware phase walk (the name-keyed phase attribution cannot see ancestry) with the engine-walk agreement pin extended to it. Hoyle's one-phase-per-clause wall simplifies the flow half: each entry has ONE containment region — the single named phase's subtree — never an intersection. The flow analysis classifies every `Call` position of a scoped entry into a TOTAL taxonomy, pinned against the `Game` field set and the `PhaseItem` union so a new field forces a decision: (1) inside the phase's subtree — the Phase node's whole extent: its qualifier expression, before_each, after_each, statements, nested phases; its own state defaults cannot hold a call (`_check_state_default_scope`'s Call ban is the cited Owner, not re-covered); (2) inside a game-defined move type — judged by its offering sites, ALL of which must sit inside the subtree, with the offered-nowhere case refused (Hoyle's vacuous-containment wall); (3) inside a function, define, rule, trick-order row, `loser:`, or any other game-level expression position — refused (no containment without interprocedural analysis; the ban has the default-Call ban's shape and the corpus's blessing — zero witness calls sit there, probe 2026-08-30); (4) inside a procedure body — judged at every `RunStmt` naming it, transitively, since resolve runs pre-expand and splice is by value: a procedure run both inside and outside is refused at the offending `RunStmt`. **The offering-surface relation derives, never authored alone:** candidates are every `_REFERENCE_SLOTS` entry whose namespace is `move_type` or `kernel_move_type` — 7 slots today — classified offering (Offer.offering, AuctionRound.offering, TrickRound.move_type, ClimbRound.move_type, LegalMoves.move_types — Hoyle's four spellings, five slots) or non-offering (MoveEvent.move_type, RuleDef.constrains), in one table pinned total against the derived candidates so an eighth slot arrives unclassified and reddens. Edges match by NAME across both namespaces — pinochle proves the overlap live: `declare_trump_suit` is kernel-listed AND game-defined, and its `legal_moves` mention sits inside the subtree (the accept twin of a cell the grid must also refuse). The ledger states the honest asymmetry: the kernel-slot edges are execution-inert for game move-type bodies today — the runtime consults `move_type_index` at exactly 2 channels (the offer interpreter; the auction form's candidates/apply) across 4 sites, census 2026-08-30 — so those edges guard the future consumer, and the PREMISE that game move-type bodies execute only inside offering sites' dynamic extents is pinned by its own scrape over the runtime's `move_type_index` readers, two-readers style. **Spans (P7):** tail arms at the read's span; refused containers at the CALL's span (the offending `RunStmt`'s for procedures), naming entry, phase, container, and fix; offer-outside-subtree as one diagnostic per offending offering site, span at that site, message carrying the chain (move type, the scoped call, the entry, `in P`); vacuous containment at the scoped call inside the move type. Every message pinned in the blessed-snapshot harness.

*(c) The materializer.* **A (counseled): `rs.get` unchanged.** Under the containment rule plus the fourth predicate the innermost walk is correct by construction: at every admitted call the live frames are the declaring phase's, its ancestors', and interposed descendants'; the game frame cannot hold the name (the shadowed wall stands), no descendant may (the new predicate), and the reversed walk meets the declaring phase's frame before any ancestor's — so the walk returns exactly the declared phase's value, with no frame tagging. Corpus cost of the refusal: zero — 31 games, 92 phases, 197 phase-state declarations, zero ancestor-descendant same-name pairs, zero duplicate phase names (known-positive control planted and caught, 2026-08-30). **B (rejected): target the declared frame.** Frames are anonymous by design; tagging taxes every push site to buy correctness only for the case the compile refusal removes, and a runtime-targeted read would let two textually identical calls read different stores — the silent-wrong-answer register the three sibling predicates exist to refuse. **The kernel liveness site is `runtime/driver.run_phase`:** push_frame; `_declare_state`; then the qualifier evaluation, before_each, the body (descendants nest), after_each in the loop's finally; pop_frame in the outer finally on every unwind. **Verdict: before_each and after_each are ADMITTED**, and the declaring phase's own qualifier expression with them — all run strictly between declare and pop. `run_phase` gains the one comment naming resolve's containment check as the consumer of its declare-before-run ordering, so the ordering cannot drift from the guard that leans on it. Residual runtime miss: unreachable with the guard in place, so it is a Shadow Guard — the declared path's typed miss must, for a scoped name, name the declaring phase and resolve's containment check as Owner; the attribution rides the `Declared` entry or the `game_reads` call the way `primitive` already does, and `PrimitiveReads`' row shape does not change. One semantics note for the implementer: phase state declares once per `run_phase` entry, not per repeat-until iteration — re-entry re-initializes, mid-loop reads see current values; the guard does not depend on this, but issue #504's option-2 aside compresses it.

*(d) Witnesses and fixtures.* The five witnesses carry the accept half, verified by execution 2026-08-30 against Hoyle's derivation: stud/holdem call inside the declaring phase itself with player-INDEXED phase state — the binder-x-tail accept cells have live witnesses; pinochle and tarot call from descendant phases one level under `hand_sequence` (calls sitting in IfStmt, RepeatUntil, LetStmt positions — useful variety); canasta carries the move-type leg (four scoped-calling move types offered only in `match/deals/hand/play`, `take_pile` at three offer sites — the ALL-quantifier's multi-offer accept), team-indexed phase state, a second descendant branch (scoring), a three-deep declaring phase, and that phase is literally named `hand` — the tail/zone name-adjacency probe for free. Every REFUSAL cell is synthetic — the corpus, correctly, holds no violation: offer-outside-subtree; offered-nowhere; each refused container of taxonomy arm (3); the outside-`RunStmt` procedure case; subtree re-declaration; the tail arms; the does-not-lift shadowed variant; Hoyle's transposed-binder parse twin. Fixture discipline: fixtures declare REAL registered implementations (the `pinochle_meld_value` borrowing precedent, already the regime-product probe's practice) — never probe-minted Python, so the fixture cannot prove the block against an implementation written to suit it; each refusal fixture ships with its accept twin (the same game, violating element removed) so the arm is proven discriminating, not merely loud — the corpus-confound mode of the verify-the-plant rule. Accept cells PLAY, never merely resolve — `test_state_default_scope`'s recorded lesson is exactly this guard's failure shape — including one synthetic nested fixture whose playout provably reaches a scoped call from the three admitted positions no witness exercises: the qualifier, before_each, after_each.

**5. What becomes illegal after.** *resolve* newly establishes: every scoped read's tail names a real phase that declares the name; no strict descendant of that phase re-declares it; every call of a scoped entry sits inside that phase's subtree or in a game move type all of whose offering mentions do — so downstream may assume the declaring frame stands, and holds the name, at every call the pass admits. Illegal after: the runtime defending a scoped read with anything but the Owner-naming Shadow Guard. *primitives_block* newly claims the phase-carrying classification and the fourth collision predicate in its Establishes clause; illegal after: any consumer walking phase state blocks itself to answer a scope or ancestry question. *driver*: `declared_primitives` passes the tail through the one classifier; illegal after: a materialization arm branching on scope — there is nothing to branch on. *The offering-surface table*: illegal after, a move-type-naming reference slot without an offering/non-offering classification. *The 3b recipe*: the five walled games' step-2 stop-and-report clears; rows, `ROW` bindings, and dispatch arms delete per the recipe, pinochle's and french-tarot's auction rows surviving per the narrowed pin. *Prose*: six sites asserting the old wall — `classify_read`'s docstring, `phase_local_state_names`, `shadowed_state_names`, `phase_state_zone_names` and its diagnostic's parenthetical, the phase-local arm's message (which gains "or scope the read") — are defects the moment the tail lands and rewrite in the same change, with the message pins re-blessed.

**6. Counsel.** *For:* every fact lands in its owner — predicates in the leaf beside the three siblings whose rationale the fourth completes, refusals in the pass whose Contract owns scope facts, a materializer that does not change — and the compile guarantee is exactly what lets the runtime stay four lines; the five games migrate on a construct whose accept cells are real games played, not fixtures resolved. *Against, strongest:* the guard's soundness rests on a runtime premise no static pass can see — that game move-type bodies execute only inside offering sites' dynamic extents. True today at exactly 2 channels across 4 consumer sites, and one future feature away from false (rule enforcement widening past `play_to_trick`, a demands-actions evaluation path, an adapter enumerating legality outside an offer) — and the failure mode is a green guard gone silently unsound. The mitigation is the premise pin plus the ledger's does-not-prove line (which also records that a scoped entry with zero calls passes containment vacuously — the block-declares-what-the-game-calls discipline stays the recipe's); the residual is a pin someone must extend when the next channel lands — priced, not eliminated. *What the Architect would do:* take A on all four choices; author the grid red first with the played accept rows and twin-verified refusal fixtures; land the premise pin in the same PR as the guard; rewrite the six prose sites and re-bless the pins in the same change; and before freezing, have the plan read four Contract blocks and one docstring — `cardlang/resolve.py`'s, `cardlang/primitives_block.py`'s, `cardlang/runtime/reads.py`'s, `cardlang/expand.py`'s (the by-value splice semantics the `RunStmt` judgment mirrors), and `runtime/driver.declared_primitives`' totality claim, which gains the containment fact. *Bottom line (two-persona; this seat writes last):* adopt Hoyle's surface as ruled, zero divergences — the pending frame-liveness verdict comes back ADMIT for before_each/after_each with the declaring phase's qualifier joining them, and the one syntactically-admitted position the frame cannot honor is already owned by the default-Call ban. The strongest against-case from either seat is the runtime premise above, at the cost of a maintained pin. The operator decides one thing: descendant re-declaration refused at compile (counseled), versus frame-targeting at runtime (rejected — a RuntimeState redesign to buy what a refusal buys for nothing, against zero corpus cost measured 2026-08-30).
