---
term: Hosted Poll
definition: A climbing round's `before asking <binder> { … }` clause, and the poll its body runs — the game's own statements, run by the shared decision loop once before every turn and every [[interrupt-window]] ask of the trick, with the binder bound to the seat about to be asked; never before a [[play-announcement]], never once the round has ended. The off-the-clock idiom's site inside a form that owns a trick's decisions, for moves that are the game's rather than the form's (Tichu's small tichu call). The body holds decisions and state writes only.
layer: kernel
status: canonical
reserved: false
home: `n.HostedPoll`, `cardlang/runtime/mechanics.py`, `run_decision_round`
see: [Interrupt Window, Play Announcement, Decision Episode, Offering]
retired_spellings: []
findings: []
---

**Kernel.** A climbing round's `before asking <binder> { … }` clause, and the poll its body runs. The shared decision loop (`run_decision_round`) runs the body once before every ask of a kind in `mechanics.HOSTED_ASK_KINDS` — the ring's lead and follow, and the [[interrupt-window]]'s ask after an ordinary turn — with the binder bound to the seat about to be asked. It never runs before a [[play-announcement]], which is the same seat's same act as the play that opened it, and never once the round has ended; the loop consults the round's `until` again after the body, so a body whose writes end the round is followed by no ask.

It is the off-the-clock idiom's site inside a form that owns a trick's decisions (decisions.md "Off-the-clock windows"), for moves that are the game's own — a move type with its guard and effect, Tichu's small tichu call — where the Interrupt Window serves moves that are the form's (Tichu's bombs). The poll inside is an ordinary `round offering` over an [[offering]], so its asks are ordinary decisions emitting ordinary public announce events, and its lap counter belongs to its [[decision-episode]] exactly as between two tricks.

The body holds decisions and state writes only — `if`, `let`, assignment, `offer`, `round offering` without an `outcome` clause, `as`, `for each`, and `run` — never names the `state` pronoun, and calls no Primitive of the game's. The rule binds everything the body can execute: the procedures it runs, the move types it offers (guard and effect), and the functions it calls, transitively (`resolve.HOSTED_REACH_POOLS`); resolve refuses everything else across that closure (`resolve.HOSTED_POLL_ALLOWED`, `resolve._check_hosted_polls`). The binder is a fresh name and never the acting player: the body is no seat's action. The clause is the climbing form's alone.
