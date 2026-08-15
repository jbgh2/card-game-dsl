"""Runtime interpreter for the Card Game DSL.

Executes the resolved typed AST to play a [[game]] end to end, so a
random-playout harness can test that the checked `n.Game` is executable —
`driver.play_game` takes that AST, never the serialized [[ir]], which
`cardlang/ir.py` emits for the CLI and the goldens alone. It runs the whole
corpus (`docs/games/`), not one game; docs/decisions.md holds the runtime
semantics it relies on.
"""
