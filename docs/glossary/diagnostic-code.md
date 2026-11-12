---
term: Diagnostic Code
definition: The kind of fix a refusal asks of its [[author]], spelled in the designer's words (`unknown-zone`, `written-twice`), one member of the closed registry `cardlang.diagnostic_codes.Code`. Two refusals share a code exactly when the corrective act they ask for is the same kind, whatever their wording and wherever they are raised. Required where a diagnostic is made, kept by every retelling, carried by every [[record-envelope]], and never shown by the text output. A code once shipped is never renamed, removed or given a second meaning, since a tool may key on it.
layer: check
status: canonical
reserved: false
home: `cardlang/diagnostic_codes.py` (`Code`), `cardlang/diagnostics.py` (`Diagnostic.code`)
see: [author, failure-channel, near-miss, record-envelope]
retired_spellings: []
findings: []
---

Always the full phrase: a bare "code" is the engine's source, and an error
code in the ordinary sense names a number, which this is not.
