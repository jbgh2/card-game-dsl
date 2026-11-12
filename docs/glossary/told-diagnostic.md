---
term: Told Diagnostic
definition: A diagnostic as told: in the file the attribution step, or the raise that made it, decided, and addressed to the [[author]] who must act on it. Every refusal a `DiagnosticError` carries is one (`Told`); a pass collects plain diagnostics, which carry no author, and only the layer that tells a refusal makes the told one -- `cardlang.attribution` for the checker's passes, the parser's and the extract step's own raises, the command line for its own refusals, and `cardlang.records.refusal_diagnostic` for a runtime refusal.
layer: check
status: canonical
reserved: false
home: `cardlang/diagnostics.py` (`Told`, `DiagnosticError.told`), `cardlang/attribution.py` (`tell`)
see: [author, diagnostic-code, record-envelope, library-note]
retired_spellings: []
findings: []
---

Always the full phrase: "told" alone is the verb the attribution step's
Contract uses for the act, and the act is not the value.
