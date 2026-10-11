# Grammar pass, Step 2: the grammar accepts only the language (#840)

Epic #818, the third unit. The brief is `docs/design-notes/grammar-pass-2026-10-07.md`,
section 5, row 2, and section 6's "keep the messages; move the mechanism".

## Acceptance criteria

1. Runs: every corpus game, library and stdlib file parses under the main grammar and
   never reaches the diagnostic layer; every wrong sentence a twin refuses today is
   refused with the same message at the same span.
2. Regression-clean: bare `mypy`, the full suite, the rigs; every rejection golden
   byte-identical (the claim this unit is measured by); no game file moves.
3. Info sets derive: no decision site, projection or runtime change.

Corpus lockstep: none. Witness: the rejection goldens under `tests/rejections/`, each a
wrong sentence a designer wrote and the message it earned.

## Classification

Grammar surface (twenty-eight twin alternatives, their helper rules and the terminals
only they use leave the main grammar: Merge Lane A); parse (a diagnostic parser in the
failure path; the twin builders unchanged); resolve (the `always` refusal); tests
(pins and ledgers); docs (the grammar's own comments, parse.py's Contract,
decisions.md "The expression register").

## The mechanism

`cardlang/grammar/diagnostics.lark` is a file of `%extend` lines: each twin verbatim,
the helper rules only twins reach (`nested_collection`, `primitive_arrow_decl`,
`primitive_default_decl`, `trick_order_eq_row`), and the terminals only twins name
(`_CARD_VALUES_KW`, `TRICK_ORDER_EQ`, `STAKE_FLAG_COLON`, `DIV_OP`, the `==` / `!=`
arms of `COMP_OP`). The parser composes it onto the main grammar text only inside
`parse_to_tree`'s failure path: a failed main parse is parsed once more under the
composed grammar, and a twin that derives the text hands the builder the node it hands
it today, so the same method raises the same message. A text neither grammar derives
reports the main parser's own error, computed before the second parse, so no
expected-token list names a retired spelling.

One twin cannot move: `always` is a plain name once its keyword leaves the lexer, so
`applies_when: always` and `when: always` parse. The refusal moves to resolve — an
unresolved `always` standing as the whole predicate is told to leave the clause out, in
the words the builder uses today — which is where a refusal belongs (Hoyle's charter:
a production that exists to refuse a sentence lands in the grammar only when no parse
can recover the sentence any other way). A declared `always` is a condition like any
other, which the main grammar refused and now accepts: the one sentence this unit
newly admits, and a grid cell.

## Reachability

R2 — a designer meets the messages at every slip; nothing a designer sees changes
except that `always` and `card_values` are now names a game may declare.

## The totality edge (audit step 1, run here)

Grid, in `tests/test_diagnostic_grammar.py`, authored red:

- the main grammar carries no alias ending `_reject`, and no terminal only a refused
  rule names (derived from the compiled parser);
- every twin the diagnostic grammar holds is exercised by a rejection golden, derived
  both ways: the twins from `diagnostics.lark`, the exercised set from parsing every
  golden fixture under the composed grammar;
- the corpus, the libraries and the stdlib never reach the diagnostic parser;
- a text neither grammar derives reports the main error, byte for byte;
- `always`: the two teaching sentences (the orphaned-surface pin's), a declared
  `always` accepted as a predicate, and an undeclared `always` as an operand meeting the
  ordinary unresolved-name refusal.

The rejection goldens (`tests/test_rejections.py`) are the regression gate: byte-identical.

## Hoyle's counsel

### Headnote

Twenty-eight productions leave the grammar and no sentence a designer writes changes
its answer. Each was a wrong spelling the grammar accepted in order to refuse it with the
right one — `card_values { }`, `trump: 5`, `wager: true`, `a == b`, `of 2 cards in a,
b` — and each stays refused with the same words, from a second grammar that exists only
in the parser's failure path. The recommended sentence is the one we have for every
designer; the losing rival is the status quo, teaching written as grammar, where every
twin is a place a second derivation can hide. The library form does not apply: nothing
enters, and the Merge Lane is A because the main grammar narrows. Zero game files move.
One settled commitment is cut against in words: `==` and `/` were kept in the lexer "so
the rejection can name the fix"; they are kept now in the diagnostic grammar for the
same reason, so the reason survives and the sentence does not. Information sets do not
move. The cost: one twin, `always`, cannot move with the rest and becomes a resolve
refusal, which means a game may now declare a name called `always` — the one sentence
newly accepted; and a file with a twin's slip AND a later genuine error meets the
later error first, where today it meets the twin's message. What the operator decides:
nothing; the brief ordered this step and the mechanism preserves every message.

### 1. The sentences

No designer sentence changes. The diagnostic file's lines are the twins verbatim, for
example:

```
%extend card_points_table: _CARD_VALUES_KW [":"] "{" card_points_entry* [card_points_else] "}" -> card_values_reject
%extend trump: _TRUMP_KW ":" INT -> trump_int_reject
```

Alternatives weighed: token-adjacency recognizers on parse failure (the brief's
phrasing) — rejected, since hand-written recognizers restate the twin grammars less
precisely and would drift from the messages; keeping the twins in the main grammar —
the status quo, rejected by the brief's Finding 8 (every twin a derivation hazard) and
by the charter. No adjacency hazard: the main grammar loses alternatives and gains none.

### 2. Precedent

decisions.md "The expression register" (`==` and `/` as retired spellings refused with
the fix); "Surface totality" (every accepted composition has an accounted outcome — and
now every ACCEPTED composition is the language's); the grammar's own comments on the
`card_points_table` mechanism; the Language Owner's charter on productions that exist
to refuse.

### 3. Corpus impact

None: no game, library or stdlib file writes a twin. The witness is the rejection
goldens, which exist for every twin and stay byte-identical.

### 4. The totality edge

Newly accepted: a declared name `always` or `card_values` (the keywords leave the
lexer). Newly refused: nothing. Every message preserved: the goldens.

### 5. The info-set bound

No observation, projection or runtime change.

### 6. Counsel

For: the grammar becomes the language and nothing else; the ambiguity hazards the brief
counted vanish from the main parser; the messages stay. Against: a second grammar is a
second artifact to keep in step, and a twin fires only when the whole file parses under
the composed grammar, so a file with two mistakes meets the second one first. Hoyle
would move the twenty-eight, pin the composed grammar's twin set against the goldens
both ways, and let `always` go to the checker where it belonged.

## Task list

1. Red first: `tests/test_diagnostic_grammar.py`.
2. The main grammar loses the twins, helpers and terminals; `diagnostics.lark` gains
   them verbatim; `parse_to_tree` gains the failure-path parse; the `always` refusal
   moves to resolve with its holder table.
3. The coupled tests move with it: the orphaned-surface pin's `always` positions derive
   from resolve's table; the dead-surface pins plant a twin instead of naming one; the
   expected-words helper for refusal-only terminals goes.
4. Docs: the grammar comments and parse.py's Contract read the diagnostic file; "The
   expression register" says where `==` lives.
5. Gate: bare `mypy`; `pytest -q -n 8`; the rigs; `tools/lane-of.sh`; the PR with this
   counsel, Headnote first.
