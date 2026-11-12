## Off-the-clock windows

Some rules offer a move "at any time" rather than on a turn: Tichu's
tichu call (any time before the caller's first play), Doppelkopf's
Re/Kontra and level announcements (any time during the play, gated by
the announcer's own hand size). The language expresses these as a
**quiescence-lap poll** — an idiom over the existing kernel, not a
construct:

```text
if <public window gate> {
  turns caller from <player about to act> over all players
        until quiet >= <player count> {
    offer to caller one of [<window moves>, decline]
  }
  quiet := 0
}
```

placed before each decision the enclosing phase offers. Every window
move's effect resets the `quiet` counter; the decline increments it; a
full silent lap closes the poll, and the closing poll clears its own
counter: the lap count belongs to the poll's Decision Episode
([glossary/decision-episode.md](../glossary/decision-episode.md)), idle at
every decision the poll does not own, so the information state between
polls names no lap already closed (pinned at
`tests/test_offering_round_state_freshness.py`). An announcement
re-opens the lap, so chains of reactions (Re → no 90 → Kontra) resolve
at a single poll point in any order the players choose.

Three properties make the serialization faithful and leak-free:

- **The gate reads public state only** (hand counts through their
  `count_only` projections, announcement flags), so observers can
  compute exactly when polls are skipped — a closed window emits
  nothing and reveals nothing.
- **Private eligibility lives in the move guards.** A player whose
  guards all fail is offered only the decline and submits the same
  public decline event a player declining by choice submits, so
  ineligibility is indistinguishable from silence — the projection of
  "hasn't announced yet" that real play gives.
- **A participant's own thresholds change only when the participant
  acts** (hand sizes decrement on the owner's plays), so polling before
  each decision offers every window move at exactly the hand sizes the
  paper rules allow; no legal timing is lost to the serialization.

The poll's decisions are ordinary `offer`-shaped kernel decisions
emitting ordinary public announce events — no new observation kind, no
change to how information states derive.

Rejected alternatives: a dedicated `may submit X` phase verb (deferred
per corpus-first promotion — Tichu and Doppelkopf are two witnesses,
and constructs are earned at the third instance, e.g. Belote's
mid-trick declarations); an `optional: true` move-type property
(optionality belongs to the offer site, not the move — beside it stands
the accepted Stake row, "A move type's stake", and the one reason
separates them: what varies by site lives at the site, and what holds at
every site lives on the move); a state write outside the move framework
(removes the decision from the observation stream, breaking derived
information sets).

Where the window falls *inside* a form that owns the decisions of a
trick, no statement sits between the form's own asks, and the idiom
takes one of two shapes there. When the window's moves are the form's
own — Tichu's bombs out of turn, which are plays — the form applies the
idiom itself: the climb form's Interrupt Window ("The climbing form of
`round`") asks every seat in turn after each ordinary turn with the
same public decline for the seat that cannot act and the seat that will
not.
When the window's moves are the game's — Tichu's small tichu call, a
move type with its own guard and effect — the round hosts the poll the
game writes, as a **Hosted Poll**
([glossary/hosted-poll.md](../glossary/hosted-poll.md)):

```text
round climb play_combination from leader over …
      combinations tichu_lead_options follows tichu_follows
      until …
      before asking seat {
        if tichu_window_open() and lead_made() {
          turns caller from seat
                over players where may_call(player)
                until quiet >= (number of players where may_call(player)) {
            offer to caller one of [call_tichu, no_call]
          }
          quiet := 0
        }
      }
```

The body runs once before every turn and every Interrupt Window ask of
the trick, with its binder bound to the seat about to be asked, which is
the placement the idiom asks for — "before each decision the enclosing
phase offers" — made at the one layer that can see those decisions. It
never runs before a Play Announcement, which is the same seat's same act
as the play that opened it, and never once the round has ended; a body
whose writes satisfy the round's `until` is followed by no ask. The poll
inside is written exactly as it would be written between two tricks, so
everything above holds of it unchanged: its asks are ordinary offering
decisions emitting ordinary public announce events, and its gate and
participants read public state. Polling only the seats whose eligibility
is public (Tichu's `may_call`) is the game's choice at the offer site;
where eligibility is private the poll walks every seat instead, as
Doppelkopf's does.

The body holds decisions and state writes only: `if`, `let`, assignment,
`offer`, `turns` (the ring a poll runs over the seats that may still
call, bounded by its participants and `max_length` as the poll's own lap
is), `as`, `for each`, and `run`. The rule binds everything the body can
execute, not only its own text: the body's statements and, transitively,
every procedure it runs, every move type it offers — its `when:` guard and
its effect alike — and every function it calls. Resolve refuses, anywhere in that closure, every other statement —
a card movement changes the hands and pile the live trick reads, a nested
trick or climbing round starts a second trick inside the first, a loop
over no seat ring (`repeat until`, `each … simultaneously`) has no bound
the poll's lap does not already give, non-local control unwinds out of
the trick mid-play. It refuses the `state` pronoun
wherever it stands — not only as a `state.` read, since a `let` or an
argument carries the live frame on to a later one — and a call of a
Primitive the game's own namespace holds, since a round's state is
published only once it ends and a game module reads the live frame
through its engine facts. A designer function spelled like another
game's Primitive is a function there, followed like any other. Resolve's
judgement is the Owner Guard, and the runtime stands behind it on what
actually executes: while a body runs, every statement it executes, the
`state` pronoun, and every Primitive's engine facts are refused as a Shadow
Guard (`cardlang/stdlib/hosted_poll.py`), so a route the static judgement
does not model is still refused when it runs. A
move type the poll offers is judged as part of the poll; offered
anywhere else, the same move type is not. The binder is a fresh name, spelled like
nothing already classifiable where the clause is written, and is never
the acting player: the body is no seat's action, so `actor` inside it
means what it means at the round statement. `before` and `asking` are
keywords only in the clause's position, so a game may still bind a local
named either. The clause is the climbing form's alone; the trick form
has no Hosted Poll, which is why Doppelkopf writes its tricks out by
hand.

Rejected: a Python registry row naming the game's move types and gate on
the combination engine, which runs the same decisions with no grammar —
it hides the offer site from the game file, which is exactly the reason
the `optional: true` property was refused above, and it binds a
combination engine to move types it does not own; a clause with no body
and a form-owned lap (`polling [...]`), which would either leave the
game's lap counter drifting across hosted polls, breaking the Decision
Episode's reset, or have the form write a game State Variable.

Witnesses: Doppelkopf's announcement ladder at full fidelity
([games/doppelkopf.cardlang](../games/doppelkopf.cardlang)); Tichu's call
windows (the WS5 upgrade,
[kernel-migration.md](../kernel-migration.md)), its small tichu hosted in
every climbing trick ([games/tichu.cardlang](../games/tichu.cardlang)).
