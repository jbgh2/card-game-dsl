---
term: Line End
definition: How one line of a [[prefix-walk]] ended, the closed union `LineEnd` of two arms. `Rules`: both implementations terminal, the game by its rules, their outcomes agreeing; it carries the ply and both returns vectors. `Truncated`: the oracle terminal at one of the game's decisions past the root, by a draw rule the game does not play; it carries the ply and no returns, so returns are never compared past the point the oracle stopped. A line the walker can end neither way fails instead of returning, and a line a caller's script stops has no Line End. `tally_line_ends` counts a manifest's Line Ends and refuses one with no `Rules` arm.
layer: check
status: canonical
reserved: false
home: `tests/native_oracle.py`
see: [prefix-walk]
retired_spellings: []
findings: []
---
