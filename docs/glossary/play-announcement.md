---
term: Play Announcement
definition: The climb [[form]]'s same-seat regime — a play whose `announce` names tokens is followed by exactly one further decision of the seat that made it, over those tokens, before the ring advances; the token is announced publicly and recorded beside every play in the trick's own event record, which a game-local query reads to enforce a rule that spans plays. Tichu's Mahjong wish is the witness. Void once the round has terminated, since the hand is over. The tokens are the engine's, docked by `primitives.climb_announcements`.
layer: kernel
status: canonical
reserved: false
home: `cardlang/runtime/mechanics.py`, `ClimbForm`
see: [Interrupt Window, Round State, Observation Event]
retired_spellings: []
findings: []
---

**Kernel.** The climb [[form]]'s same-seat regime: a play whose `announce` names tokens is followed by exactly one further decision of the seat that made it, over those tokens, before the ring advances. The token is announced publicly — an ordinary announce [[observation-event]], so every seat's information state derives it — and recorded beside every play in the trick's own event record (the [[round-state]]'s internal `events` key), which a game-local query reads through `EngineFacts.round_state` to enforce a rule that spans plays: Tichu's Mahjong wish, where the engine marks the plays a standing wish compels and the form offers those alone.

The tokens are the engine's, docked by a registry keyed on the lead query (`primitives.climb_announcements`) exactly as the combo codec is, so the action space numbers every token. A pending Play Announcement is void once the round has terminated — the loop consults the end predicate before asking — so the announcement a hand-ending play would open is never asked, as the hand is over.
