---
term: Diagnostic Grammar
definition: The grammar file `cardlang/grammar/diagnostics.lark`, holding every [[reject-with-replacement-twin]] as an `%extend` line over a production of the main grammar. The parser composes it onto the main grammar only after a main parse has failed (`cardlang/parse.py`, `_diagnostic_parser`) — a twin that derives the refused text hands the parse builder its node, and the builder's `*_reject` method raises the fix in the designer's words; a text neither grammar derives meets a syntax error rendered in the main grammar's words. The main grammar accepts only the language, so no sentence of the language reaches this file, and composing it adds nothing to the surface (`tools/dead_surface.py`). Never a name for `cardlang/diagnostics.py`, the module of the [[failure-channel]]; never `composed grammar`, which names the composition the parser builds, not the file.
layer: compiler
status: canonical
reserved: false
home: `cardlang/grammar/diagnostics.lark`, `parse.DIAGNOSTIC_GRAMMAR`, `parse._diagnostic_parser`
see: [reject-with-replacement-twin, failure-channel]
retired_spellings: []
findings: []
---
