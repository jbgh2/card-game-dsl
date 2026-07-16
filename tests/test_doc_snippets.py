"""Doc-snippet lockstep: every DSL example in the settled-spec docs stays
pipeline-checked against the live grammar/checker.

`docs/games/` already has a harness (the corpus proof modules under
`tests/openspiel_ready/`). The three prose specs — `docs/decisions.md`,
`docs/library.md`, `docs/model.md` — did not: their fenced code blocks were
enforced only by review, so a grammar change could leave a stale example
sitting in the spec indefinitely. This module closes that gap by walking
every fenced block in the three docs, requiring an info-string tag on each
(docs/maintaining.md "Doc snippet tagging"), and pipeline-checking the
blocks whose tag claims they are DSL.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-------------------------------------------------------------------------
Assumes:      the three docs' fenced blocks are extractable by
              `cardlang.extract.extract_blocks`, and `FencedBlock.info`
              carries the opening fence's info string.
Establishes:  every fenced block in the three docs carries a tag in
              KNOWN_TAGS; every `cardlang` block passes
              `cardlang.pipeline.check_dsl` verbatim; every
              `cardlang-fragment` block passes `check_dsl` once embedded in
              its registered WRAPPER_RECIPES entry; every `cardlang-bad`
              block is rejected by `check_dsl` (DiagnosticError). `text` /
              `ebnf` blocks are not executed.
Now illegal:  a bare or unrecognized-tag fenced block in these three docs —
              `test_every_block_is_classified` fails loud, naming the doc
              file and line, before any tag-specific check runs.
Verified by:  this module's own parametrized tests over the live docs, plus
              `test_self_*` synthetic-fixture tests that prove each of the
              four code paths (classified/unclassified,
              cardlang-pass/cardlang-bad-reject/fragment-pass) independently
              of what the corpus of real doc blocks happens to contain.

Completeness ledger
--------------------
property:   every fenced block in docs/{decisions,library,model}.md carries
            a recognized classification tag, and every block tagged
            cardlang / cardlang-fragment / cardlang-bad is PROVEN, by
            execution, to pass or reject the front-end pipeline as its tag
            claims — not merely assumed from its tag.
domain:     the fenced blocks `cardlang.extract.extract_blocks` finds in
            docs/decisions.md, docs/library.md, docs/model.md — 44 + 10 + 4
            = 58 blocks as of this change. (An earlier plan for this task
            cited 88/10/8, i.e. `grep -c '^```'` — fence *lines*, not
            blocks: 88 = 44*2, 8 = 4*2; library.md's "10" underequal already
            counted blocks because five of its ten blocks are indented
            inside list items and a column-anchored grep misses them.
            `extract_blocks` is the authority; block counts, not fence-line
            counts, are what this module classifies.)
registry:   KNOWN_TAGS (below) is the closed tag vocabulary. The three docs
            are the block source. WRAPPER_RECIPES (below) is the closed set
            of fragment shapes with a cheap wrapping harness.
covered:    all 58 blocks carry a recognized tag
            (test_every_block_is_classified, parametrized over every
            block). All 8 `cardlang-fragment` blocks execute through their
            registered wrapper and are proven to pass
            (test_fragment_blocks_pass_when_wrapped). The
            classify/cardlang/cardlang-bad/fragment code paths are each
            independently proven with synthetic fixtures (test_self_*),
            since the real docs currently contain zero `cardlang` and zero
            `cardlang-bad` blocks — the wall still has to have teeth on
            that day one of those tags is used for the first time.
sampled:    n/a — every block this module classifies as executable is
            executed, not sampled.
residual:   fragment KINDS with no cheap wrapping harness. These are never
            tagged `cardlang-fragment` in the docs (they are `text`
            instead, so `test_every_block_is_classified` still covers
            them as a tag, just not as an execution) — each kind is listed
            here and recorded in roadmap.md "Explicitly deferred":
              - phase-outcome pattern matches (`<phase> produces:` /
                `continue to <phase>`) — need a sibling phase declaring a
                matching `-> outcome {...}` variant set plus the variant's
                own tag vocabulary (Tarot's Petite/Garde bid levels); a
                generic skeleton can supply the shape but not the
                game-specific tags.
              - resource-zone movements (`transfer 1 coin from treasury to
                coins[player]`) — roadmap.md "Grammar surface deferred by
                the checker": "resource movements ... undesigned"; no
                zone type in cardlang/stdlib/zones.py models an unowned
                resource pool, so no skeleton can embed one.
              - the `override` rule-delta (`active_rules: [override X]`)
                — grammatically accepted, rejected at resolve time
                (cardlang/resolve.py, `_resolve_phase_item`) as "not yet
                supported by the runtime"; roadmap.md already records it.
              - `legal_moves:` with `+`/`-`/`override` deltas — the
                `legal_moves` grammar production takes a bare NAME list
                only; those operators exist solely on `rule_ref`
                (`active_rules:`).
              - `scoring_component` / `apply_components` — decisions.md's
                own "Scoring composition" section discloses "designed, not
                yet built"; roadmap.md already records it.
              - user-facing `Zone<ContentType> { composition: ... }`
                declarations — no such production exists; per-observer
                projection is a closed Python registry
                (cardlang/stdlib/zones.py `ZONE_PROJECTIONS`), keyed by the
                stdlib zone-type name a game references inside `zones {}`,
                never authored inline.
              - `type` fields with a range/union/parameterized shape
                (`level : Integer in 1..7`, `suit : Suit | NT`,
                `type X<Layer: Integer> = ...`) — `struct_field`/`type_def`
                grammar has none of these; a `type_name` is a bare NAME
                (optionally `?`).
              - the retired `choose <Type> with <constraint>` statement
                form and the `<actor> chooses <description>` expression
                form — superseded by the `round offering [...]` kernel
                construct and plain function calls (`team_of(outcome)`);
                no corpus game uses either retired form today.
              - the old `move_type X { source: ... destination: ...
                emits: ... }` shape — superseded by `when:` / `effect {}`.
            Each kind above is `text`-tagged at every site it appears in
            the three docs today (see the per-block classification in the
            commit that introduced this module).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.extract import FencedBlock, extract_blocks
from cardlang.pipeline import check_dsl

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOC_NAMES = ("decisions.md", "library.md", "model.md")

# The closed tag vocabulary (docs/maintaining.md "Doc snippet tagging"). A
# fenced block whose info string is not in this set — including the empty
# string (a bare fence) and a near-miss typo — is unclassified, and
# `test_every_block_is_classified` fails loud rather than defaulting it to
# either "skip" (accepted-but-ignored) or "check" (a guess that may crash).
KNOWN_TAGS = frozenset({"cardlang", "cardlang-fragment", "cardlang-bad", "text", "ebnf"})


# ---------------------------------------------------------------------------
# Wrapper recipes for `cardlang-fragment` blocks.
#
# Each recipe embeds one doc block's raw text into a minimal but plausible
# game so the front-end pipeline (parse -> resolve -> typecheck -> expand ->
# deck-capacity) has enough context to run. The recipes share a common
# zone/state vocabulary (`_SHARED_ZONES`/`_SHARED_STATE`) so they read like
# one small game, not seven unrelated ones — but each recipe adds only the
# names its own fragment actually references (a stdlib rule/move-type name,
# never an invented game-specific one). Fragments that need genuinely
# game-specific vocabulary (a bid-level enum, an undeclared rule with no
# stdlib analog) have no recipe and are not tagged `cardlang-fragment` in
# the docs — see the module docstring's ledger "residual" section.
# ---------------------------------------------------------------------------

_SHARED_ZONES = """\
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    waste            : Discard
    captured[player] : PlayerPile<player>
"""

_SHARED_STATE = """\
    score[player]      : Integer   = 0
    leader              : Player?  = none
    eliminated[player] : Boolean   = false
    pass_direction     : Direction = hold
"""


def _game(body: str, *, top_level: str = "") -> str:
    """A minimal plausible game: the shared zones/state plus `body` (typically
    one or more `phase` declarations) as the remaining game items."""
    return f"""
{top_level}
game Skeleton {{
  players: 4
  max_length: 1000
  cards: standard52
  zones {{
{_SHARED_ZONES}
  }}
  state {{
{_SHARED_STATE}
  }}
{body}
}}
"""


def _wrap_active_rules_shadowing(frag: str) -> str:
    # decisions.md "Sub-phase rule and legal-move deltas": plain shadowing
    # (no +/-/override). The rule names are the doc's own illustrative
    # letters, given a trivial always-true body against the stdlib move type.
    rules = "\n".join(
        f"rule {name} {{ constrains: play_to_trick applies_when: always }}"
        for name in ("A", "B", "C", "X", "Y")
    )
    return _game(f"{frag}\n  winner: highest score", top_level=rules)


def _wrap_first_trick_phase(frag: str) -> str:
    rule = (
        "rule MustLeadAceOfSpadesOnFirstPlay "
        "{ constrains: play_to_trick applies_when: always }"
    )
    return _game(f"{frag}\n  winner: highest score", top_level=rule)


def _wrap_play_phase(frag: str) -> str:
    # References only stdlib names (play_to_trick, highest_of_led_suit,
    # on_play_of_tochoo) and shared-skeleton state (leader, eliminated).
    return _game(f"{frag}\n  winner: highest score")


def _wrap_before_each(frag: str) -> str:
    body = (
        "  phase main repeat until pass_direction is hold {\n"
        f"{frag}\n"
        "  }\n"
        "  winner: highest score"
    )
    return _game(body)


def _wrap_cards_line(frag: str) -> str:
    # `frag` is the single game_item line `cards: standard52`.
    return f"""
game Skeleton {{
  players: 2
  max_length: 1000
  {frag}
  zones {{ deck : Deck }}
  state {{ score[player] : Integer = 0 }}
  phase main {{ move all cards to deck }}
  winner: highest score
}}
"""


def _wrap_winner_loser(frag: str) -> str:
    # `frag` is the doc's `winner: ...` / `loser: ...` pair, illustrating two
    # alternative game-result clauses. Both parse and typecheck fine declared
    # together (the language does not reject a game declaring both), so the
    # single fenced block round-trips as one wrap.
    return f"""
game Skeleton {{
  players: 4
  max_length: 1000
  cards: standard52
  zones {{ hand[player] : Hand<player> }}
  state {{ cumulative_score[player] : Integer = 0 }}
  phase main {{ move all cards to hand[0] }}
{frag}
}}
"""


def _wrap_passing_phase(frag: str) -> str:
    # `transfer_between_hands` is a stdlib move type (cardlang/stdlib/moves.py);
    # PassExactlyThreeCards is given a trivial always-true body against it.
    rule = (
        "rule PassExactlyThreeCards "
        "{ constrains: transfer_between_hands applies_when: always }"
    )
    return _game(f"{frag}\n  winner: highest score", top_level=rule)


def _wrap_library_zones_block(frag: str) -> str:
    # `frag` is a complete `zones { ... }` game_item (library.md's stdlib
    # zone-type usage example).
    return f"""
game Skeleton {{
  players: 2
  max_length: 1000
  cards: standard52
{frag}
  state {{ score[player] : Integer = 0 }}
  phase main {{ move all cards from deck to deck }}
  winner: highest score
}}
"""


# (doc file name, FencedBlock.start_line) -> wrapper. Keyed by content start
# line (not the fence line) to match `FencedBlock.start_line` exactly.
WRAPPER_RECIPES: dict[tuple[str, int], Callable[[str], str]] = {
    ("decisions.md", 194): _wrap_active_rules_shadowing,
    ("decisions.md", 316): _wrap_first_trick_phase,
    ("decisions.md", 336): _wrap_play_phase,
    ("decisions.md", 961): _wrap_before_each,
    ("decisions.md", 1183): _wrap_cards_line,
    ("decisions.md", 1881): _wrap_winner_loser,
    ("decisions.md", 2337): _wrap_passing_phase,
    ("library.md", 467): _wrap_library_zones_block,
}


# ---------------------------------------------------------------------------
# Block discovery over the live docs.
# ---------------------------------------------------------------------------


def _load_blocks() -> list[FencedBlock]:
    blocks: list[FencedBlock] = []
    for name in DOC_NAMES:
        text = (DOCS_DIR / name).read_text()
        blocks.extend(extract_blocks(text, name))
    return blocks


_BLOCKS: list[FencedBlock] = _load_blocks()


def _block_id(block: FencedBlock) -> str:
    return f"{block.source_name}:{block.start_line}"


def _run_pipeline(text: str, location: str) -> DiagnosticError | None:
    """Run `check_dsl`, returning the DiagnosticError if one was raised, or
    None on success. Any *other* exception (e.g. the bare `StopIteration`
    `cardlang.parse._Builder.start` raises when a fragment has no enclosing
    `game`) is NOT swallowed here — it propagates and fails the test with a
    Python traceback pointing at `location`, rather than being silently
    misread as a pass or a clean rejection."""
    try:
        check_dsl(text, location)
    except DiagnosticError as exc:
        return exc
    return None


# ---------------------------------------------------------------------------
# The wall: every block must be classified.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block", _BLOCKS, ids=[_block_id(b) for b in _BLOCKS])
def test_every_block_is_classified(block: FencedBlock) -> None:
    assert block.info in KNOWN_TAGS, (
        f"{_block_id(block)}: unclassified snippet — every fenced block in "
        f"docs/decisions.md, docs/library.md, docs/model.md must carry an "
        f"info-string tag from {sorted(KNOWN_TAGS)} (got info={block.info!r}). "
        "See docs/maintaining.md 'Doc snippet tagging'."
    )


# ---------------------------------------------------------------------------
# Per-tag execution over the live docs.
# ---------------------------------------------------------------------------

_CARDLANG_BLOCKS = [b for b in _BLOCKS if b.info == "cardlang"]
_BAD_BLOCKS = [b for b in _BLOCKS if b.info == "cardlang-bad"]
_FRAGMENT_BLOCKS = [b for b in _BLOCKS if b.info == "cardlang-fragment"]


@pytest.mark.parametrize(
    "block", _CARDLANG_BLOCKS, ids=[_block_id(b) for b in _CARDLANG_BLOCKS]
)
def test_cardlang_blocks_are_full_valid_games(block: FencedBlock) -> None:
    err = _run_pipeline(block.text, _block_id(block))
    assert err is None, f"{_block_id(block)}: tagged `cardlang` but rejected: {err}"


@pytest.mark.parametrize("block", _BAD_BLOCKS, ids=[_block_id(b) for b in _BAD_BLOCKS])
def test_cardlang_bad_blocks_are_rejected(block: FencedBlock) -> None:
    err = _run_pipeline(block.text, _block_id(block))
    assert err is not None, (
        f"{_block_id(block)}: tagged `cardlang-bad` but the pipeline accepted "
        "it — either the counterexample no longer demonstrates the mistake, "
        "or it should be retagged."
    )


@pytest.mark.parametrize(
    "block", _FRAGMENT_BLOCKS, ids=[_block_id(b) for b in _FRAGMENT_BLOCKS]
)
def test_fragment_blocks_pass_when_wrapped(block: FencedBlock) -> None:
    key = (block.source_name, block.start_line)
    wrapper = WRAPPER_RECIPES.get(key)
    assert wrapper is not None, (
        f"{_block_id(block)}: tagged `cardlang-fragment` but has no entry in "
        "WRAPPER_RECIPES — every cardlang-fragment block must be either "
        "wrapped and checked here, or retagged `text` and added to the "
        "residual list in this module's docstring."
    )
    wrapped = wrapper(block.text)
    err = _run_pipeline(wrapped, _block_id(block))
    assert err is None, (
        f"{_block_id(block)}: tagged `cardlang-fragment`, wrapped via "
        f"{wrapper.__name__}, but rejected: {err}"
    )


# ---------------------------------------------------------------------------
# Self-tests: prove each code path with synthetic fixtures, independent of
# what the real docs currently contain (today they hold zero `cardlang` and
# zero `cardlang-bad` blocks — the wall must still have teeth).
# ---------------------------------------------------------------------------

_TINY_GOOD_GAME = """\
game Tiny {
  players: 2
  max_length: 10
  cards: standard52
  zones { deck : Deck }
  state { score[player] : Integer = 0 }
  phase main { move all cards to deck }
  winner: highest score
}
"""

_TINY_BAD_GAME = """\
game Tiny {
  players: 2
  max_length: 10
  cards: standard52
  zones { deck : Deck }
  state { score[player] : Integer = 0 }
  phase main { if score[0] == 0 { move all cards to deck } }
  winner: highest score
}
"""


def test_self_bare_fence_is_unclassified() -> None:
    [block] = extract_blocks("```\nsome stray dsl\n```\n", "synthetic.md")
    assert block.info == ""
    assert block.info not in KNOWN_TAGS


def test_self_unknown_tag_is_unclassified() -> None:
    # A plausible typo of `cardlang-fragment` must NOT silently fall through
    # to "skipped like text" — that would be the accepted-but-ignored defect
    # this module exists to prevent.
    [block] = extract_blocks("```cardlang-fragmnet\nsome stray dsl\n```\n", "synthetic.md")
    assert block.info not in KNOWN_TAGS


def test_self_cardlang_block_passes() -> None:
    md = f"```cardlang\n{_TINY_GOOD_GAME}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert block.info == "cardlang"
    assert _run_pipeline(block.text, "synthetic.md") is None


def test_self_cardlang_bad_block_is_rejected() -> None:
    md = f"```cardlang-bad\n{_TINY_BAD_GAME}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert block.info == "cardlang-bad"
    err = _run_pipeline(block.text, "synthetic.md")
    assert err is not None
    assert "is not an operator" in err.diagnostic.message


def test_self_cardlang_fragment_block_passes_when_wrapped() -> None:
    md = "```cardlang-fragment\nmove all cards to deck\n```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert block.info == "cardlang-fragment"
    wrapped = _game(f"  phase main {{\n{block.text}  }}\n  winner: highest score")
    assert _run_pipeline(wrapped, "synthetic.md") is None


def test_self_text_block_is_not_executed() -> None:
    # A `text` block need not even be valid DSL — proving that requires it
    # NOT be run. Executing it would raise; the assertion is just that this
    # module makes no such call for `text`-tagged blocks (the dispatch in
    # test_every_block_is_classified / the per-tag tests above only ever
    # calls _run_pipeline for cardlang/cardlang-fragment/cardlang-bad).
    [block] = extract_blocks("```text\nnot ( valid at all\n```\n", "synthetic.md")
    assert block.info == "text"
    assert block.info not in ("cardlang", "cardlang-fragment", "cardlang-bad")


def test_known_tags_is_the_documented_closed_set() -> None:
    # Pins the vocabulary named in docs/maintaining.md "Doc snippet tagging"
    # so a silent addition here is caught by review of that doc too.
    assert KNOWN_TAGS == {"cardlang", "cardlang-fragment", "cardlang-bad", "text", "ebnf"}
