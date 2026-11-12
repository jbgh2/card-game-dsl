## Sub-phase entry and exit

A sub-phase is entered and exited in one of three ways. All three
exist in the corpus; choosing among them is a matter of which one
the rulebook describes.

**Sequencing (default).** The enclosing phase body lists sub-phases
in order; control enters the next sub-phase when the previous one
ends. Used for setup → bidding → play → scoring pipelines.

**Predicate guard.** `phase X when <pred>` makes the sub-phase
active *exactly when* the predicate holds. The phase is entered the
first time the predicate becomes true and exited as soon as it
becomes false. Hearts' `passing` sub-phase uses this for the case
when `pass_direction is not hold`; Tichu's `wish_active` sub-phase uses
this for the case when a Mahjong wish stands. No explicit
`transition_to:` is needed — the predicate is the entry guard *and*
the exit condition.

**Event-triggered sibling transition.** `transition_to: Y when <event>`
inside sibling X switches control to sibling Y when the event fires.
The `<event>` is a move-type event with an optional `where <predicate>`
over the move under inspection; there are no ad-hoc event names.
Hearts breaks hearts with `transition_to: hearts_broken when
play_to_trick where action.card.suit is hearts`; Spades breaks spades with
`transition_to: spades_broken when play_to_trick where action.card.suit is
spades` (the move under inspection is bound as `action` — see "Rule demand
forms"). The transition is one-shot — once Y is entered, X is not
re-entered. Its condition belongs to the phase declaring the modes, as that
phase's state does: **entering the phase begins the condition afresh, and
nothing else resets it**. A parent's `repeat until` re-enters the phase each
iteration, so Hearts' `play`, a sub-phase of the hand loop, re-breaks hearts
each hand; a `repeat until` on the declaring phase itself, or a statement
`repeat until` inside it, iterates within one entry and keeps the condition,
exactly as it keeps the phase's `state { }`. The trick rounds that end a
condition are the ones the declaring phase's subtree runs, so a mode whose
transition must watch every trick of a hand belongs to a phase enclosing
them all, which is why Hearts plays its first trick inside `play` ("The
boolean-as-sub-phase criterion" above). A play reads the rules in force at
that play, so a condition ending on the lead stops constraining the plays
after it in the same trick.

There is no separate construct for "this sub-phase ends and control
returns to the enclosing parent's loop." The predicate-guard form
covers it: when the predicate becomes false, the sub-phase exits,
and control resumes in whatever parent body invoked it. Reaching
for `transition_to: parent` is a sign that what's really needed is a
predicate guard.
