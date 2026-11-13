---
term: Refusal Consequence
definition: A refusal a check makes on a fact it reads from a declaration or reference as written -- which procedures are run, which move types are offered, which cards the deck holds, whether a zone is kept per player, who is acting -- where another check refused the spelling that fact rests on, so a fix of that spelling would clear it. The refused spelling marks the slot it stands in and the set it was looked up in (`Refused`); the consequence marks what clears it (`Unless`); and `DiagnosticBag.settle`, run at every raise, withholds a group of consequences only when one fix of each refused spelling, drawn from its set and never from the [[near-miss]]es, clears them all, and tells the group otherwise. The cause is always told. Never "cascade", which names the symptom, nor a "suppressed error", which reads as a refusal discarded rather than one its cause leaves untold.
layer: check
status: canonical
reserved: false
home: `cardlang/diagnostics.py` (`SlotKind`, `Slot`, `Refused`, `Unless`, `DiagnosticBag.settle`)
see: [near-miss, author, failure-channel]
retired_spellings: []
findings: []
---

Always the full phrase: a bare "consequence" reads as any effect of a rule
in play.
