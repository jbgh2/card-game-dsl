---
term: Interrupt Window
definition: The climb [[form]]'s regime between plays — after every play but a trick-ending one, and once more when the ring has returned to the last player, every other participant still holding cards is asked in turn order from that player, offered the plays the engine marks `interrupt` that beat the standing play beside the engine's declared decline token, so a seat with nothing to play submits the same public decline a seat declining by choice does. A taken interrupt stands, the ring resumes after the interrupter, and the window reopens. Opened only for an engine whose registry row declares a decline (`primitives.climb_interrupt_decline`); Tichu's bombs interrupt, Big Two and President declare none.
layer: kernel
status: canonical
reserved: false
home: `cardlang/runtime/mechanics.py`, `ClimbForm`
see: [Decision Episode, Play Announcement, Round State]
retired_spellings: []
findings: []
---

**Kernel.** The climb [[form]]'s regime between plays — after every play but a trick-ending one, and once more when the ring has returned to the last player, every other participant still holding cards is asked in turn order from that player, offered the plays the engine marks `interrupt` that beat the standing play beside the engine's declared decline token. A seat with nothing to play submits the same public decline a seat declining by choice does, which is what keeps who-was-asked a function of public state alone (the off-the-clock idiom's leak-freeness, one level down: decisions.md "Off-the-clock windows"). A taken interrupt stands as the current play and the last player, the ring resumes after the interrupter, and the window reopens.

An Interrupt Window is a [[decision-episode]] of the trick it interrupts: its queue lives in the [[round-state]]'s internal `window` key, idle between plays, and never in a [[state-variable]]. It opens only for an engine whose registry row declares a decline token (`primitives.climb_interrupt_decline`), so absence is a stated fact rather than an empty filter — Tichu's bombs interrupt and its decline is `no_bomb`; Big Two and President declare none and open no window. A compulsion (a [[play-announcement]]'s wish) binds on turn only, never in the window.
