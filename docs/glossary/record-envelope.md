---
term: Record Envelope
definition: The one JSON document a command prints for a tool: its format's version (`schema`), what it holds (`kind`), and its records. A check's envelope holds one Diagnostic Record per [[told-diagnostic]], each carrying its [[diagnostic-code]], severity, [[author]], place (file, line, column and length), message, notes, and its [[near-miss]]es as suggestions marked `offered`, never as edits to apply. A reader refuses an envelope whose schema or kind it does not know. Made only by `cardlang.records`, which composes no words of its own and decides no author.
layer: check
status: canonical
reserved: false
home: `cardlang/records.py` (`envelope`, `span_record`, `read_envelope`, `SCHEMA`, `Kind`)
see: [diagnostic-code, told-diagnostic, near-miss]
retired_spellings: []
findings: []
---

A Diagnostic Record is one record inside a check's envelope; the envelope is
the document. Neither is the IR, which `--emit-ir` prints and which carries
its own version key.
