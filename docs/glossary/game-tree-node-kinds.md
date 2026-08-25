---
term: Game Tree Node Kinds
definition: OpenSpiel calls it **decision node** / **terminal node** / **chance node**. Replay reifies the first two as `DecisionNode` / `TerminalNode`. At most one chance node exists, at the root, implicit in `CardlangState` (`_seed is None`); its outcomes are seeds that drive every rng draw, and a [[chance-free-game]] carries none. A future native simultaneous-move export would add `SimultaneousNode`. Not "Terminal" bare — that word is grammar/lexer vocabulary. — translated in `replay.py`, `game.py`.
layer: interop
status: canonical
reserved: false
home: `replay.py`, `game.py`
see: []
retired_spellings: []
findings: []
---

**Interop.** OpenSpiel calls it **decision node** / **terminal node** / **chance node**. Replay reifies the first two as `DecisionNode` / `TerminalNode`. At most one chance node exists, at the root, implicit in `CardlangState` (`_seed is None`); its outcomes are seeds that drive every rng draw, and a [[chance-free-game]] carries none. A future native simultaneous-move export would add `SimultaneousNode`. Not "Terminal" bare — that word is grammar/lexer vocabulary. — translated in `replay.py`, `game.py`.
