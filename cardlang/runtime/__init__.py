"""Runtime interpreter for the Card Game DSL (Hearts vertical slice).

Executes the resolved typed AST to play a game end to end, so a random-playout
harness can test that the IR is executable. See docs/games/hearts.cardlang for
the game and docs/decisions.md for the runtime semantics it relies on.
"""
