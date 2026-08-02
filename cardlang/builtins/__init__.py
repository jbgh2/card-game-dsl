"""The declaration side of native code: what the checker may consult.

Name sets and signature tables for the functions a game may call, declared
here and implemented in `cardlang/runtime/`. This package imports nothing
from the runtime — that one-way layering is what lets resolve and typecheck
consult it — and it holds both halves of the native surface: `BUILTIN_*`
names for the generic functions the language ships, `PRIMITIVE_*` names for
the game-local ones (glossary; issue #200).
"""
