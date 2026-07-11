# Rule scope beyond trick play

**Tier 3 — medium impact, narrow scope.**

Rule application has exactly one runtime site: the trick form's card-decision
point calls `rules.legal_cards` with the move type fixed to `play_to_trick`.
Everything the rule grammar can express beyond that site is validated,
type-checked, and emitted to IR — and then never consulted:

- a rule whose `constrains:` names any other move type (Hearts'
  `PassExactlyThreeCards` constrains `transfer_between_hands`) never matches;
- the `demands: actions where <predicate>` form (the move-shape predicate) has
  no enforcement point at all — today the shape is enforced by the construct
  itself (the pass movement's `chosen 3`, a betting move's `when:` guard);
- `legal_moves:` names are resolved but runtime-inert (see
  [phase-legal-moves.md](phase-legal-moves.md)); the climb round's move-type
  name is likewise a validated label (the `climb` keyword selects the form).

The checker now rejects the *silently misread* corners of this cliff (a trick
round naming another move type, transitions on non-trick events — decisions.md
"Surface totality"), but the expressible-yet-unenforced rules above are real
spec content the runtime does not honor, disclosed in decisions.md ("Rule
demand forms", enforcement status).

The design question: **where should declarative rules apply outside a trick
round?** Candidate sites, each with a different enforcement shape:

- **Chosen movements** — a `move chosen N cards …` draw could intersect
  card-set demands from rules constraining its move type, and check
  `actions where` predicates over the completed selection (card_count is a
  natural fit). This would let `PassExactlyThreeCards` actually bind.
- **Auction/betting vocabularies** — move guards (`when:`) already gate
  candidates; rules constraining a vocabulary move would be a second,
  cross-cutting gate. Is that worth two mechanisms, or should vocabulary
  legality stay guard-only?
- **The climb form** — legality lives in the `follows` query; same question.

The data point to wait for: the first game whose non-trick decision genuinely
needs a *reusable, named* constraint (the corpus-first bar) rather than an
inline guard or filter. Schnapsen's follower legality — the corpus's first
non-trick card legality — landed as a function predicate (`follow_ok`)
filtering a chosen movement, which
suggests guards may be enough and rules may be a trick-form-only device; if
so, the resolution is to *say that* (narrow the rule grammar's claim), not to
build the wider machinery.
