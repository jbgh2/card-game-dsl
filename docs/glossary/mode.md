---
term: Mode
definition: A condition the game is in, existing to change which rules are active: entered by `transition_to`, body is configuration only (`active_rules:`, `transition_to:` — being in it *is* its behavior), and an empty mode is the terminal default: no delta, no exits. Modes are INDEPENDENT conditions, not an exclusive state machine: several may hold at once and their deltas stack. Each is exactly one side of one condition — the **before** side, which declares the transition, or the **after** side, which a sibling names; both-or-neither is rejected. Its condition belongs to the phase declaring it: entering that phase begins it afresh, and a play in any trick round of that phase's subtree can end it; a phase holding modes that no trick round can reach is refused. The config-only class is grammar-owned.
layer: kernel
status: canonical
reserved: false
home: `n.Mode`
see: []
retired_spellings: []
findings: []
---
