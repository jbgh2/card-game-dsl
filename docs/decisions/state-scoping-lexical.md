## State scoping (lexical)

A variable is scoped to the phase that lexically encloses its
declaration. The variable's lifetime *is* the duration of one
instance of that phase: it is initialized to its declared default
when the phase is entered, and ceases to exist when the phase exits.
Re-entering the phase produces a fresh instance.

This is the conventional rule essentially every modern programming
language uses for block-scoped local variables. No `per_hand` /
`per_rubber` annotation. No `scoped_to:` keyword. The block that
contains the declaration *is* the scope. Refactoring a phase carries
its state with it.

**Reads from enclosing scopes are free.** A scoring phase inside
`hand_sequence` can read `games_won` declared in `rubber`
because `rubber` lexically encloses `hand_sequence`. This is ordinary
nested-scope visibility.

**Writes follow the same rule.** A phase may write to a variable
declared in its enclosing scope (Bridge's `scoring` writes
`games_won[dteam] += 1` and `below_current[dteam] := 0`, both of which
live in `rubber`). A phase may *not* write to a variable declared in
a sibling or descendant scope, because that variable's owning phase
may not be active.

Reads and writes are both refused at resolve
(`resolve._check_state_scope`), which also owns the game-level
`winner:` clause: it is evaluated after every phase has exited, so it
ranks on game-level state only. One reference position is outside that
guard's reach — a move type, rule, function or procedure body
has no enclosing phase, so whether its state reads are live depends on
which phase invokes it rather than on where it is written. That is a
reachability question, not a lexical one, and it is tracked rather than
enforced (issue #242).

**A default reads only what is already declared.** The free-reads rule
above is about a body running inside the phase, when the whole block
exists. A `= <default>` is evaluated earlier than that — while its own
block is still being declared, top to bottom — so it sees the enclosing
scopes and the declarations *above it in its own block*, and nothing
else. A default naming a variable from later in its block, from itself,
from a sibling phase, or from a phase nested inside its own reaches a
variable that does not exist yet, and is refused
(`resolve._check_state_default_scope`). Without the rule these all
passed every front-end pass and died at playout on a bare `KeyError` out
of `runtime/state.py`.

A default may not **call**, either. A call's state reads live in the
callee's body, so admitting one would mean chasing the declare-time
reachability of every function a default can reach. Refusing the call
outright costs nothing measured — across the whole corpus and every
library, defaults hold integer and enum literals, and not one reads a
state variable — and it keeps the surface total rather than leaving a
check that silently stops at the call boundary. Compute the value in
the phase that needs it.

Nor may a default **`choose`**. A default is evaluated outside any
player's turn, so there is no one to make the decision; the runtime
raised "a `choose` with no acting player" at declare time, and for the
OpenSpiel target a decision with no actor has no information set to
attach to. This is the same rule as the two above and not a separate
one: what a default may do is bounded by how little of the game exists
when it runs.

**A default must fit its declared type.** `v : Integer = "s"` is refused,
not silently stored: the default's inferred type must be assignable to the
variable's declared type — the same `assignable` relation an ordinary
assignment uses (`typecheck._check_state_default_type`, the initial-value
Shadow Guard of `_check_assign`). For an indexed variable the default is checked
against the element type, since `score[player] : Integer = 0` broadcasts
one value to every key. The check is as sharp as the inferencer and no
sharper: a default whose type the inferencer leaves as the permissive top
is accepted whatever the declaration, which is the type system's design
rather than a hole here — no corpus default is untyped.

**Example: Bridge state declarations.**

```text
game Bridge {
  // No game-level state in Bridge.

  phase rubber repeat until (any team where games_won[team] >= 2) {
    state {
      games_won[team]              : Integer = 0
      above_line[team]             : Integer = 0
      below_line_current_game[team]: Integer = 0
    }

    phase hand_sequence {
      state {
        contract       : Contract? = none
        declarer       : Player?   = none
        dummy          : Player?   = none
        tricks_taken[team] : Integer = 0
        dummy_revealed : Boolean   = false
      }
      // ... phases inside hand_sequence ...
    }
  }
}
```

**Variables that need cross-phase visibility live in the smallest
enclosing scope that covers all their uses.** If a variable is read
by both `bidding` and `play`, it lives in their parent `hand_sequence`,
not in either. This is also how a result threads from one sub-phase to
a sibling: the trick `leader` that Getaway's `first_trick` hands to
`play` is a `Player` in the game's own state — `first_trick` seeds it
(the ace-of-spades holder) and updates it to the trick winner, `play`
continues from it, and `loser:` reads it at the end, which is what
makes the game the smallest scope covering its uses. A mechanic's result is read
as bare `outcome` immediately after the mechanic runs (`leader :=
outcome`); there is no construct for referencing a prior phase's
outcome across the phase boundary — the shared enclosing variable is
the channel.

**Round-internal state lives inside the round.** The trick `round`'s
per-trick state (`led_suit`, the played cards) and the climb's
(`lead_ended_trick`, the shed order) live inside the construct's own frame,
readable as `state.x` during the round and, for the just-finished round, in
the surrounding body. (Schnapsen's talon-closing snapshot, once a Python
mechanic's local, is ordinary phase state now that its hand runs on the
kernel — closes and marriages are public declarations at the table, so
`closed_by` and the closer-snapshot counters are public state per "Hidden
information lives only in zones; state is public"; Coup's window results are
public phase-state Booleans the same way.) A round's frame is short-lived;
its state vanishes when the next round runs. (An auction's pass state or a
betting street's `bet_to_match` is *not* round-internal — a `turns` ring
has no frame, and its moves write ordinary **phase state**, declared in the
phase's `state { }`.)

**A round PUBLISHES a closed, typed set of fields, and `state.` names only
those.** A form's frame is also its working memory — the trick form drives its
turn order off a ring cursor and a materialized order list — and the two are not
the same thing. The published fields are declared once, with their types
(`cardlang/stdlib/round_state.py`): the trick form publishes `led_suit : Suit?`
and `trick_terminated_early : Boolean`; the climb form publishes
`lead_ended_trick : Boolean`, `shed_first : Player?` and `shed_second : Player?`.
A `turns` ring publishes nothing: its accumulator is ordinary phase state
("Auctions, polls and betting rings are `turns` plus `offer`"). Naming anything
else — a misspelling, or one of the form's internals — is a compile error that
lists what *is* published. The guard is what keeps a form's working memory out of
the language: without it, a round's private ring cursor is nameable, type-checks,
runs, and silently changes the game. The declared types carry the same weight — an
untyped `state.x` is contagiously `Any`, and every comparison guard is dark behind
it.

**Rules consulted from within a round see the round's published state.**
A rule is asked at the trick round's card decision, so its `state.` names
that round's published fields, the closed set above, exactly as `state.`
does anywhere else; a rule reads game and phase state by the variable's own
name, with no prefix. Examples in the corpus:

- Hearts' `MustFollowSuit` reads `state.led_suit`, which the trick `round`
  publishes.

(A bidding or betting ring expresses its legality differently —
not as `active_rules:` reading round state, but as the move types' own `when:`
guards over phase state: Pinochle's ascending bid guards `submit_bid` on the
standing bid; Stud's `check`/`bet`/`call`/`raise`/`fold` guard on `bet_to_match`,
`bet_by`, and `raises`.)

Rules are reusable across games; what binds them to a particular
round's state is the call site (the phase where the round runs and
the rule is attached as an `active_rules` entry).
Refactoring a form's state shape is a potentially breaking
change for any rule that reads it — same as refactoring any other
in-scope variable. There's no separate "exposed subset" mechanism;
visibility is just lexical scoping.

**Tooling-generated state inventory.** Lexical scoping disperses
declarations across the phase tree. The "what state exists in this
game" view that helps when reading the file is a render of the
program — the doc-rendering pass or language-server walks the phase
tree and emits a per-phase state catalogue. State summary is
documentation, not declaration.

**OpenSpiel compilation.** Each phase frame carries its own state in
the State object, with lifetime tied to phase entry/exit. Standard
activation-record semantics.

**`let` bindings scope forward and carry their type.** A `let` binds
its name for the rest of the statement tuple it appears in — the same
sequential fold at all three layers: the resolver scopes the name, the
checker types it, the runtime binds the value. The binder's static type
is its initializer's inferred type in the environment at that point, so
every guard answers the same for the bound name as for the inline
expression (`let z = hearts` followed by `z is 3` is rejected exactly
as `hearts is 3` is). In a phase body the fold runs across the items:
a preceding `let` scopes over later statements and nested phases (their
`when`/`repeat until` qualifiers included) — what the driver evaluates
mid-body with the threaded context. It does NOT scope over the phase's
own `before_each`/`after_each` hooks or its state-block defaults, which
run at entry, before any body `let` has executed — reading a body `let`
from either is an unresolved name, not a runtime surprise. (An
ENCLOSING body's `let` is visible to both — the nested phase receives
the threaded context.) A transition predicate is stricter still: it may
read no `let` at all, enclosing or not. It is fired by whichever round
matches its event, and rounds both before and after any given `let` can
be in scope, so no lexical position makes a binding reliably live at
evaluation time — configuration reads state and the action, not body
bindings.

The indexed form `let base[p] = E` is a per-player map: the key binder
types as `Player` inside `E` only, and `base` as a collection of `E`'s
type, keyed by `Player`. Keyed collections — indexed lets and indexed
state variables — carry their key domain, and subscript reads and
indexed writes are checked against it (`n[hearts]` on a player-keyed
store is a compile error). A keyed collection is addressed one entry at a
time, and its key decides where it may stand: it never stands where an
unkeyed collection is wanted, nor an unkeyed one where it is wanted, nor
where a collection keyed by another domain is wanted — wherever the
language reads a collection's members (a native's collection parameter, a
card query's or aggregation's source, `is empty`, a turn ring's players),
compares two values, or assigns a whole variable. A crossing is refused at
check time, naming the key and the one-entry spelling (`score[p]`): the
runtime holds a keyed collection as a map, so its members would be read as
its keys, a map never equals a list, and a whole-variable assignment would
replace a store with a differently-keyed one. A conditional whose branches
are keyed differently, or keyed and unkeyed, stands only where the same
mixed shape is wanted. A positional
collection — a `[...]` list, a board region such as `home(p)` — is
addressed by an Integer position counted from 0; a position that does not
type exactly Integer, a negative one, or a literal one past a length the
sentence states, is refused at check time, and a computed one outside the
collection at play time. A zone's cards are not addressed by position. A zone VALUE is likewise distinguished from
a computed card collection: a query result or list literal types
`Collection<Card>` too, but only a zone (or a binder holding one) may
stand in a transfer endpoint or an epistemic target — narrowing a
transfer is the `where` filter's job, not a laundered query's. An initializer the checker deliberately
leaves loose (`outcome`, an unregistered `action` field) carries that
looseness forward — ordinary gradual typing, with the runtime's typed
errors behind it. A `let` is a bound value, not a variable: it is not
assignable (see "Mutation semantics").
