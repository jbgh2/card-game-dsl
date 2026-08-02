"""Preliminary LLM evaluation harness — a frontier model playing Cheat through
the engine's *proven* information-state interface.

The agent layer sits at the OpenSpiel seam, outside the language: nothing here
imports from `cardlang` except the registered adapter (`cardlang.openspiel`),
and nothing here is imported by `cardlang/` or `tests/`.

The load-bearing property is stated and enforced in `prompts.py`: the prompt
shown to a model is a pure function of (static rules text, the engine's
information-state string, the legal action strings, static boilerplate). See
`REVIEWER.md` for the leak-freeness argument.
"""
