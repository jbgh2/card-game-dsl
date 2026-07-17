"""Mechanized surface totality: the corpus-mutation fuzzer.

docs/design-notes/grammar-fuzzing.md is the plan this package implements
(T1-T3: the oracle harness, the corpus-mutation fuzzer, and the playout
invariants run on mutants that pass the front-end pipeline). Grammar-directed
generation (the plan's T4/T5, a sentence generator walking
`cardlang/grammar/cardlang.lark` directly, plus shrinking) is the next stage
and is deliberately NOT implemented here — see `oracle.py`'s module
docstring for the residual this leaves.
"""
