"""Runtime interpreter for the Card Game DSL.

Executes the resolved typed AST to play a [[game]] end to end, so a
random-playout harness can test that the [[ir]] is executable. It runs the whole
corpus (`docs/games/`), not one game; docs/decisions.md holds the runtime
semantics it relies on.
"""
