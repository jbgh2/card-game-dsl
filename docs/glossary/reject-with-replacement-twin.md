---
term: Reject-with-Replacement Twin
definition: A production that exists to refuse a sentence — one wrong spelling a designer plausibly writes (`card_values { }`, `trick_order { }`, `wager: true`, `a == b`, `of 2 cards in a, b`), derived completely and never as a prefix, whose parse-builder method (`parse.py`, `*_reject`) raises the fix in the designer's words. Every twin lives in the [[diagnostic-grammar]], never in the main grammar, so a sentence of the language has one derivation and a twin is reached only once the main parse has failed; every twin is exercised by a rejection golden under `tests/rejections/`, and `tests/test_diagnostic_grammar.py` pins the twin set, the goldens and the builder's refusals against one another. A refusal that depends on what a name denotes rather than on its spelling (an undeclared `always` as a whole predicate) is the resolver's, not a twin's. Never `teaching twin`, `reject twin` or `twin` alone: the preamble retires the bare word for guards, and a twin is a production, named in full.
layer: compiler
status: canonical
reserved: false
home: `cardlang/grammar/diagnostics.lark`, the `_Builder` methods ending `_reject` and `div_symbol`
see: [diagnostic-grammar, failure-channel]
retired_spellings: []
findings: []
---
