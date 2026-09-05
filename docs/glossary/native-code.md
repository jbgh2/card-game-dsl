---
term: Native Code
definition: Python the DSL can call, either half — a [[builtins]] (generic, ships with the language) or a [[primitive]] (game-local). The union noun: `CALL_FUNCS` is `BUILTIN_CALL_FUNCS | PRIMITIVE_CALL_FUNCS`, and a **native call** is a call into either, resolved by name against that union. Use it when the half genuinely does not matter; name the half when it does. Never "stdlib" for any of this — the [[stdlib]] is written in the language, not in Python.
layer: kernel
status: canonical
reserved: false
home: `cardlang/builtins/`
see: []
retired_spellings: []
findings: []
---

The word this entry exists to displace is `stdlib`. Until #331 was swept, the
repo used "stdlib function", "stdlib call", "stdlib query" and "stdlib
primitive" for both halves and their union — about 120 sites, in the spec and
the corpus as well as the code — while the naming authority had said since the
glossary's first commit that `stdlib` names only the layer written in the
language. `native` was already the repo's own word for the union
(`builtins/__init__.py`: "both halves of the native surface";
`runtime/primitives.py`: "unknown legacy native function"); the sweep promoted
it from incidental usage to the name.

Four sibling words divide the space, and a sentence that reaches for `stdlib`
almost always wants one of them: **Builtin** (generic native), **Primitive**
(game-local native), **Native Code** (either), **[[kernel-tables]]** (registry
data, which is not code at all).
