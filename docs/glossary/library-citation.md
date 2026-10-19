---
term: Library Citation
definition: The one way a refusal's sentence names a library or its text -- a library, a definition, a contract row, a provided variable -- in the designer's words, carrying the span of the text it names. Made only by the attribution step (`cite_library`, `cite_definition`, `cite_origin`, `cite_where`); a sentence is composed from plain text and citations, and the bag hands each citation's span to the step, which makes that text's Library Note. A citation never spells into a plain string, so a check naming library text cannot leave its line out.
layer: check
status: canonical
reserved: false
home: `cardlang/attribution.py`, `cardlang/diagnostics.py` (`LibraryCitation`, `Sentence`)
see: [library-note, author]
retired_spellings: []
findings: []
---

Always the full phrase in prose: the bare "citation" also names a reference in
a document to another document, which carries no span.
