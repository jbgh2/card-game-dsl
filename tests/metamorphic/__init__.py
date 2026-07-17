"""The metamorphic suite (docs/design-notes/metamorphic-suite.md): pure
`Game -> Game` transforms over the PARSED (pre-resolve) AST that the spec
says cannot change a game's meaning. Each transform's own test module pairs
the untransformed and transformed variant through the ordinary pipeline and
a deterministic playout, and requires the traces to agree (modulo the
transform's own `rename` hook). `pairing.py` is the shared harness (T1);
every other module here is one transform."""
