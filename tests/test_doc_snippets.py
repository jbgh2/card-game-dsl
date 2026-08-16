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
              block (a whole game, like `cardlang`) is rejected by
              `check_dsl` verbatim; every `cardlang-bad-fragment` block (a
              snippet, like `cardlang-fragment`) is rejected by `check_dsl`
              once embedded in its registered WRAPPER_RECIPES entry —
              *after* that same wrapper is proven to PASS on the block's
              paired BAD_FRAGMENT_SMOKE filler, so the rejection can only
              come from the bad content itself, never from the wrapper
              skeleton or from the snippet simply not being a whole game.
              `text` / `ebnf` blocks are not executed.
Now illegal:  a bare or unrecognized-tag fenced block in these three docs —
              `test_every_block_is_classified` fails loud, naming the doc
              file and line, before any tag-specific check runs. Also now
              illegal: a `cardlang-bad`/`cardlang-bad-fragment` block
              "passing" its rejection check only because the pipeline
              crashed instead of cleanly rejecting — `_run_pipeline` turns
              the one known crash path (lark's `VisitError` wrapping the
              `StopIteration` that `cardlang.parse._Builder.start` raises on
              game-less input) into a named `pytest.fail`, not a bare
              traceback a reader has to reverse-engineer.
Verified by:  this module's own parametrized tests over the live docs, plus
              `test_self_*` synthetic-fixture tests that prove each of the
              five code paths (classified/unclassified,
              cardlang-pass/cardlang-bad-reject/fragment-pass/
              bad-fragment-reject) independently of what the corpus of real
              doc blocks happens to contain — including a test that a
              *benign* fragment mistagged `cardlang-bad-fragment` is NOT
              reported as a valid rejection.

Completeness ledger
--------------------
property:   every fenced block in docs/{decisions,library,model}.md carries
            a recognized classification tag, and every block tagged
            cardlang / cardlang-fragment / cardlang-bad / cardlang-bad-
            fragment is PROVEN, by execution, to pass or reject the
            front-end pipeline as its tag claims — not merely assumed from
            its tag, and not merely "rejected" as an artifact of not being
            a whole game or of the pipeline crashing.
domain:     the fenced blocks `cardlang.extract.extract_blocks` finds in
            docs/decisions.md, docs/library.md, docs/model.md. The per-doc
            and total counts are asserted, not stated, by
            test_the_block_domain_is_the_size_the_ledger_claims — a count in
            prose drifts silently as the docs grow.
registry:   KNOWN_TAGS (below) is the closed tag vocabulary — six tags:
            cardlang, cardlang-fragment, cardlang-bad, cardlang-bad-
            fragment, text, ebnf. The three docs are the block source.
            WRAPPER_RECIPES (below) is the closed set of fragment shapes
            with a cheap wrapping harness, shared verbatim by
            cardlang-fragment and cardlang-bad-fragment blocks and keyed by
            the block's recipe LABEL — the second word of its fence info
            string (```cardlang-fragment <label>), a stable name that rides
            with the block through edits rather than a line number that
            every prose change shifts. BAD_FRAGMENT_SMOKE is the closed set
            of benign fillers keyed by the same label, paired 1:1 with
            cardlang-bad-fragment blocks, each proven to PASS through that
            block's wrapper before the block's own (bad) text is checked.
covered:    every block in the domain carries a recognized tag
            (test_every_block_is_classified, parametrized over every
            block). Every `cardlang-fragment` block executes through its
            registered WRAPPER_RECIPES entry and is proven to pass
            (test_fragment_blocks_pass_when_wrapped). The
            classify/cardlang/cardlang-bad/fragment/bad-fragment code paths
            are each independently proven with synthetic fixtures
            (test_self_*), since the real docs currently contain zero
            `cardlang`, zero `cardlang-bad`, and zero `cardlang-bad-
            fragment` blocks — the guard still has to have teeth on the day
            one of those tags is used for the first time. For
            cardlang-bad-fragment specifically, the synthetic fixtures also
            prove the negative: a *benign* fragment mistagged
            cardlang-bad-fragment does NOT read as a valid rejection
            (test_self_cardlang_bad_fragment_mistagged_benign_is_not_rejected),
            which is the exact failure mode PR #56 review flagged.
sampled:    n/a — every block this module classifies as executable is
            executed, not sampled.
residual:   fragment KINDS with no cheap wrapping harness. These are never
            tagged `cardlang-fragment` (or, symmetrically, `cardlang-bad-
            fragment` — the same WRAPPER_RECIPES ceiling applies to both)
            in the docs (they are `text` instead, so
            `test_every_block_is_classified` still covers them as a tag,
            just not as an execution) — each kind is listed here and
            recorded here, in this ledger, which owns them:
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
                supported by the runtime"; roadmap.md, "Grammar surface
                deferred by the checker", already records it.
              - `legal_moves:` with `+`/`-`/`override` deltas — the
                `legal_moves` grammar production takes a bare NAME list
                only; those operators exist solely on `rule_ref`
                (`active_rules:`).
              - `scoring_component` / `apply_components` — decisions.md's
                own "Scoring composition" section discloses "designed, not
                yet built"; issue #115 already records it.
              - user-facing `Zone<ContentType> { composition: ... }`
                declarations — no such production exists; per-observer
                projection is a closed Python registry
                (cardlang/stdlib/zones.py `ZONE_PROJECTIONS`), keyed by the
                kernel zone-type name a game references inside `zones {}`,
                never authored inline.
              - `type` fields with a range/union/parameterized shape
                (`level : Integer in 1..7`, `suit : Suit | NT`,
                `type X<Layer: Integer> = ...`) — `struct_field`/`type_def`
                grammar has none of these; a `type_name` is a bare NAME
                (optionally `?`).
              - the retired `choose <Type> with <constraint>` statement
                form and the `<actor> chooses <description>` expression
                form — superseded by the `round offering [...]` kernel
                construct and plain function calls (`team_of(winner)`);
                no corpus game uses either retired form today.
              - the retired `move_type X { source: ... destination: ...
                emits: ... }` shape — superseded by `when:` / `effect {}`.
            Each kind above is `text`-tagged at every site it appears in
            the three docs today.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from lark.exceptions import VisitError

from cardlang.diagnostics import DiagnosticError
from cardlang.extract import FencedBlock, extract_blocks
from cardlang.pipeline import check_dsl
from tests.empty_axis import may_be_empty

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
DOC_NAMES = ("decisions.md", "library.md", "model.md")

# The closed tag vocabulary (docs/maintaining.md "Doc snippet tagging"). A
# fenced block whose info string is not in this set — including the empty
# string (a bare fence) and a near-miss typo — is unclassified, and
# `test_every_block_is_classified` fails loud rather than defaulting it to
# either "skip" (accepted-but-ignored) or "check" (a guess that may crash).
KNOWN_TAGS = frozenset(
    {"cardlang", "cardlang-fragment", "cardlang-bad", "cardlang-bad-fragment", "text", "ebnf"}
)


# ---------------------------------------------------------------------------
# Wrapper recipes for `cardlang-fragment` AND `cardlang-bad-fragment` blocks.
#
# Each recipe embeds one doc block's raw text into a minimal but plausible
# game so the front-end pipeline (parse -> resolve -> typecheck -> expand ->
# deck-capacity) has enough context to run. The recipes share a common
# zone/state vocabulary (`_SHARED_ZONES`/`_SHARED_STATE`) so they read like
# one small game, not seven unrelated ones — but each recipe adds only the
# names its own fragment actually references (a kernel rule/move-type name,
# never an invented game-specific one). Fragments that need genuinely
# game-specific vocabulary (a bid-level enum, an undeclared rule with no
# kernel analog) have no recipe and are not tagged `cardlang-fragment` or
# `cardlang-bad-fragment` in the docs — see the module docstring's ledger
# "residual" section.
#
# `WRAPPER_RECIPES` is keyed by the block's recipe LABEL — the second word of
# its fence info string (```cardlang-fragment <label>) — regardless of whether
# the block is a `cardlang-fragment` (proven to PASS once wrapped) or a
# `cardlang-bad-fragment` (proven to be REJECTED once wrapped). The label
# rides with the block, so editing prose above it never touches this registry;
# only adding, removing, or renaming a checked fragment does. A
# `cardlang-bad-fragment` block additionally needs an entry in
# `BAD_FRAGMENT_SMOKE`, keyed by the same label: a benign filler of the same
# shape as the bad fragment, proven to PASS through the identical wrapper
# before the bad text is checked — otherwise a rejection could come from the
# wrapper itself, or from the fragment simply lacking an enclosing `game {}`,
# rather than from the mistake the doc is illustrating.
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
    pass_direction     : SeatDirection = hold
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
    # letters, given a trivial always-true body against the kernel move type.
    rules = "\n".join(
        f"rule {name} {{ constrains: play_to_trick applies_when: always demands: cards in hand where card.suit is hearts if_impossible: hand }}"
        for name in ("A", "B", "C", "X", "Y")
    )
    return _game(f"{frag}\n  winner: highest score", top_level=rules)


def _wrap_first_trick_phase(frag: str) -> str:
    rule = (
        "rule MustLeadAceOfSpadesOnFirstPlay "
        "{ constrains: play_to_trick applies_when: always demands: cards in hand where card.suit is hearts if_impossible: hand }"
    )
    return _game(f"{frag}\n  winner: highest score", top_level=rule)


def _wrap_play_phase(frag: str) -> str:
    # References only native names (play_to_trick, highest_of_led_suit,
    # on_play_off_led_suit) and shared-skeleton state (leader, eliminated).
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
    # No rule shim: the passing phase's "exactly three" law is the movement's
    # `chosen 3`, not a rule. A rule constraining `transfer_between_hands`
    # reaches no decision site and is rejected
    # (tests/test_rule_surface_reachability.py).
    return _game(f"{frag}\n  winner: highest score")


def _wrap_actor_alias(frag: str) -> str:
    # decisions.md "Naming the acting player twice": the hoist that keeps a
    # comparison against the acting player legal inside a loop that rebinds
    # them. It has to sit where an acting player exists AND where the hoisted
    # `let` is outside the loop — a move effect, which is where the corpus
    # writes it (docs/games/tic-tac-toe.cardlang). Wrapping it anywhere the
    # `let` fell inside the loop would make this block prove the opposite of
    # what the section claims.
    return f"""
game Skeleton {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ result[player] : Integer = 0 }}
  phase main {{
    deal 2 cards from deck to each hand
    as 0 {{ offer to 0 one of [decide] }}
  }}
  winner: highest result
}}

move_type decide {{
  when: true
  effect {{
{frag}
  }}
}}
"""


def _wrap_as_taker(frag: str) -> str:
    # decisions.md "Single-actor decisions: the `as` block": the French Tarot
    # chien discard quoted as the motivating example. The fragment references
    # the taker (a Player state var), the taker's hidden discard pile, and
    # `is_pref_discard` — in the real game a user-defined `function`
    # (french-tarot.cardlang), so the wrapper declares one of the same shape
    # with a trivial body. `move chosen` needs an acting player, which the
    # fragment's own `as taker` supplies.
    fn = "function is_pref_discard(c : Card) = c.rank is not K"
    return f"""
{fn}
game Skeleton {{
  players: 4
  max_length: 1000
  cards: standard52
  zones {{
    deck            : Deck
    hand[player]    : Hand<player>
    discard[player] : HiddenPile<player>
  }}
  state {{
    taker              : Player = 0
    score[player]      : Integer = 0
  }}
  phase main {{
    deal 6 cards from deck to each hand
{frag}
  }}
  winner: highest score
}}
"""


def _wrap_turns_form(frag: str) -> str:
    # decisions.md "The `turns` form": the elimination-loop sketch. Uses only
    # the shared skeleton's vocabulary (score, eliminated).
    return _game(f"  phase turnly {{\n{frag}\n  }}\n  winner: highest score")


def _wrap_jointly_selection(frag: str) -> str:
    # decisions.md "Joint-predicate selection": the arrangement sketch. The
    # fragment names `arranger` (a Player state var) and moves from their
    # hand into the shared waste; the joint predicate is self-contained.
    return f"""
game Skeleton {{
  players: 2
  max_length: 1000
  cards: standard52
  zones {{
    deck         : Deck
    hand[player] : Hand<player>
    waste        : Discard
  }}
  state {{
    arranger        : Player = 0
    score[player]   : Integer = 0
  }}
  phase main {{
{frag}
  }}
  winner: highest score
}}
"""


def _wrap_library_zones_block(frag: str) -> str:
    # `frag` is a complete `zones { ... }` game_item (library.md's kernel
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


# recipe label -> wrapper. The label is the second word of a fragment block's
# fence info string (```cardlang-fragment <label>) — a stable name that rides
# with the block through edits, so a prose change above it never touches this
# registry. `test_recipe_labels_are_wellformed` pins that every fragment block
# carries a unique label and every non-fragment block carries none;
# `test_no_orphan_recipes` pins that every label here is claimed by a block.
WRAPPER_RECIPES: dict[str, Callable[[str], str]] = {
    "actor_alias": _wrap_actor_alias,
    "active_rules_shadowing": _wrap_active_rules_shadowing,
    "first_trick_phase": _wrap_first_trick_phase,
    "play_phase": _wrap_play_phase,
    "as_taker": _wrap_as_taker,
    "turns_form": _wrap_turns_form,
    "jointly_selection": _wrap_jointly_selection,
    "before_each": _wrap_before_each,
    "cards_line": _wrap_cards_line,
    "winner_loser": _wrap_winner_loser,
    "passing_phase": _wrap_passing_phase,
    "library_zones": _wrap_library_zones_block,
}


# recipe label -> a benign filler of the same shape as the
# `cardlang-bad-fragment` block with that label, wrapped through the *same*
# WRAPPER_RECIPES entry and required to PASS
# (test_bad_fragment_blocks_are_rejected_when_wrapped). Every
# `cardlang-bad-fragment` block must have one, in addition to its
# WRAPPER_RECIPES entry. Empty today: the docs currently tag zero blocks
# `cardlang-bad-fragment` (see the module docstring's ledger "covered"
# section — the code path is proven with synthetic fixtures instead).
BAD_FRAGMENT_SMOKE: dict[str, str] = {}


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


def test_the_block_domain_is_the_size_the_ledger_claims() -> None:
    """The `domain:` cell above, as an assertion rather than a sentence.
    A count stated in prose drifts silently as the docs grow; stated here it
    fails the day it does, and whoever adds a block updates the ledger in the
    same change. (Counting fences with `grep -c '^```'` gives a different,
    wrong answer — it counts fence LINES, and misses blocks indented inside
    list items. `extract_blocks` is the authority.)"""
    per_doc = {
        name: len(extract_blocks((DOCS_DIR / name).read_text(), name))
        for name in DOC_NAMES
    }
    assert per_doc == {"decisions.md": 55, "library.md": 13, "model.md": 5}
    assert len(_BLOCKS) == 73


def _block_id(block: FencedBlock) -> str:
    return f"{block.source_name}:{block.start_line}"


# A fence info string is `<tag>` or, for the fragment tags, `<tag> <label>`.
# The tag classifies the block; the label (a stable name) keys its wrapper
# recipe, so the registry does not depend on the block's line number.
_FRAGMENT_TAGS = frozenset({"cardlang-fragment", "cardlang-bad-fragment"})


def _tag(block: FencedBlock) -> str:
    parts = block.info.split(maxsplit=1)
    return parts[0] if parts else ""


def _label(block: FencedBlock) -> str:
    parts = block.info.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _run_pipeline(text: str, location: str) -> DiagnosticError | None:
    """Run `check_dsl`, returning the DiagnosticError if one was raised, or
    None on success.

    One specific non-DiagnosticError crash is intercepted and converted to a
    named `pytest.fail`: lark's `VisitError` wrapping the `StopIteration`
    that `cardlang.parse._Builder.start` raises when `text` has no enclosing
    `game { ... }` block (i.e. `text` is fragment-shaped but was checked
    raw). Left alone, that crash would still fail the test, but as an opaque
    traceback a reader has to reverse-engineer — and for a `cardlang-bad`
    block specifically, a *different* uncaught exception there would read as
    "rejected, as the tag claims" for the wrong reason (not a whole game,
    rather than the mistake the doc means to demonstrate). Converting it to
    `pytest.fail` keeps that path loud without being either kind of
    vacuous-green.

    Any *other* exception is NOT swallowed — it propagates and fails the
    test with a Python traceback pointing at `location`, rather than being
    silently misread as a pass or a clean rejection."""
    try:
        check_dsl(text, location)
    except DiagnosticError as exc:
        return exc
    except VisitError as exc:
        if isinstance(exc.orig_exc, StopIteration):
            pytest.fail(
                f"{location}: the pipeline crashed (lark VisitError wrapping "
                "StopIteration) instead of raising DiagnosticError — this "
                "snippet has no enclosing `game {...}` block "
                "(cardlang.parse._Builder.start found none among the parsed "
                "top-level items). It is fragment-shaped and must be tagged "
                "`cardlang-fragment` / `cardlang-bad-fragment` and checked "
                "via WRAPPER_RECIPES, not raw as `cardlang` / `cardlang-bad`."
            )
        raise
    return None


def _rejected_when_wrapped(
    wrapper: Callable[[str], str], smoke: str, bad_text: str, location: str
) -> DiagnosticError | None:
    """The `cardlang-bad-fragment` check. `smoke` is a benign filler of the
    same shape as `bad_text`; wrapping it through `wrapper` must PASS before
    `bad_text` wrapped through the same `wrapper` is even checked. This is
    the guard against the trivial-rejection failure mode: without it, a
    broken wrapper (or a fragment that merely isn't a whole game) would make
    *anything* passed through it "reject", proving nothing about `bad_text`
    specifically. Returns whatever DiagnosticError (if any) the pipeline
    raises for the wrapped `bad_text`."""
    smoke_err = _run_pipeline(wrapper(smoke), f"{location} (wrapper smoke test)")
    assert smoke_err is None, (
        f"{location}: wrapper {wrapper.__name__} rejects its own benign "
        f"smoke fragment ({smoke_err}) — fix the wrapper or the smoke text; "
        "a rejection through a wrapper that can't even pass benign input "
        "proves nothing about the bad content."
    )
    return _run_pipeline(wrapper(bad_text), location)


# ---------------------------------------------------------------------------
# The guard: every block must be classified.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block", _BLOCKS, ids=[_block_id(b) for b in _BLOCKS])
def test_every_block_is_classified(block: FencedBlock) -> None:
    assert _tag(block) in KNOWN_TAGS, (
        f"{_block_id(block)}: unclassified snippet — every fenced block in "
        f"docs/decisions.md, docs/library.md, docs/model.md must carry an "
        f"info-string tag from {sorted(KNOWN_TAGS)} (got info={block.info!r}). "
        "See docs/maintaining.md 'Doc snippet tagging'."
    )


def test_recipe_labels_are_wellformed() -> None:
    """A fragment tag carries a unique recipe label; nothing else carries a
    label. This is what lets WRAPPER_RECIPES key by name instead of by line."""
    seen: dict[str, str] = {}
    for block in _BLOCKS:
        tag, label = _tag(block), _label(block)
        if tag in _FRAGMENT_TAGS:
            assert label, (
                f"{_block_id(block)}: `{tag}` block needs a recipe label in its "
                f"fence (```{tag} <label>) so its wrapper is keyed by name, not "
                "line. See docs/maintaining.md 'Doc snippet tagging'."
            )
            assert label not in seen, (
                f"duplicate recipe label {label!r}: {_block_id(block)} and "
                f"{seen[label]} — a label names exactly one block."
            )
            seen[label] = _block_id(block)
        else:
            assert not label, (
                f"{_block_id(block)}: a `{tag}` block must not carry a label "
                f"(got {label!r}); only fragment tags key a recipe."
            )


def test_no_orphan_recipes() -> None:
    """Every WRAPPER_RECIPES / BAD_FRAGMENT_SMOKE label is claimed by a block —
    a recipe with no block is dead code that would silently rot."""
    frag_labels = {_label(b) for b in _FRAGMENT_BLOCKS + _BAD_FRAGMENT_BLOCKS}
    orphan_recipes = set(WRAPPER_RECIPES) - frag_labels
    assert not orphan_recipes, (
        f"WRAPPER_RECIPES labels with no fragment block: {sorted(orphan_recipes)}"
    )
    bad_labels = {_label(b) for b in _BAD_FRAGMENT_BLOCKS}
    orphan_smoke = set(BAD_FRAGMENT_SMOKE) - bad_labels
    assert not orphan_smoke, (
        f"BAD_FRAGMENT_SMOKE labels with no cardlang-bad-fragment block: "
        f"{sorted(orphan_smoke)}"
    )


# ---------------------------------------------------------------------------
# Per-tag execution over the live docs.
# ---------------------------------------------------------------------------

_CARDLANG_BLOCKS = [b for b in _BLOCKS if _tag(b) == "cardlang"]
_BAD_BLOCKS = [b for b in _BLOCKS if _tag(b) == "cardlang-bad"]
_FRAGMENT_BLOCKS = [b for b in _BLOCKS if _tag(b) == "cardlang-fragment"]
_BAD_FRAGMENT_BLOCKS = [b for b in _BLOCKS if _tag(b) == "cardlang-bad-fragment"]


@pytest.mark.parametrize(
    "block",
    may_be_empty(
        _CARDLANG_BLOCKS,
        reason="the live docs carry no `cardlang` block today; the pass path is "
        "proven by test_self_cardlang_block_passes",
    ),
    ids=[_block_id(b) for b in _CARDLANG_BLOCKS],
)
def test_cardlang_blocks_are_full_valid_games(block: FencedBlock) -> None:
    err = _run_pipeline(block.text, _block_id(block))
    assert err is None, f"{_block_id(block)}: tagged `cardlang` but rejected: {err}"


@pytest.mark.parametrize(
    "block",
    may_be_empty(
        _BAD_BLOCKS,
        reason="the live docs carry no `cardlang-bad` block today; the rejection "
        "path is proven by test_self_cardlang_bad_block_is_rejected",
    ),
    ids=[_block_id(b) for b in _BAD_BLOCKS],
)
def test_cardlang_bad_blocks_are_rejected(block: FencedBlock) -> None:
    # `cardlang-bad` is the whole-game counterpart of `cardlang-bad-fragment`
    # (below), just as `cardlang` is the whole-game counterpart of
    # `cardlang-fragment`: checked raw, verbatim, no wrapper. A snippet that
    # isn't already whole-game shaped belongs under `cardlang-bad-fragment`
    # instead — checking a fragment raw here would let it "reject" merely
    # for lacking an enclosing `game {}`, proving nothing about the mistake
    # it's meant to demonstrate (the P2 this module's docstring records).
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
    wrapper = WRAPPER_RECIPES.get(_label(block))
    assert wrapper is not None, (
        f"{_block_id(block)}: tagged `cardlang-fragment {_label(block)}` but "
        f"label {_label(block)!r} has no entry in WRAPPER_RECIPES — every "
        "cardlang-fragment block must be either wrapped and checked here, or "
        "retagged `text` and added to the residual list in this module's "
        "docstring."
    )
    wrapped = wrapper(block.text)
    err = _run_pipeline(wrapped, _block_id(block))
    assert err is None, (
        f"{_block_id(block)}: tagged `cardlang-fragment`, wrapped via "
        f"{wrapper.__name__}, but rejected: {err}"
    )


@pytest.mark.parametrize(
    "block",
    may_be_empty(
        _BAD_FRAGMENT_BLOCKS,
        reason="the live docs carry no `cardlang-bad-fragment` block today; the "
        "wrapped-rejection path is proven by the test_self_cardlang_bad_fragment_* "
        "fixtures",
    ),
    ids=[_block_id(b) for b in _BAD_FRAGMENT_BLOCKS],
)
def test_bad_fragment_blocks_are_rejected_when_wrapped(block: FencedBlock) -> None:
    label = _label(block)
    wrapper = WRAPPER_RECIPES.get(label)
    assert wrapper is not None, (
        f"{_block_id(block)}: tagged `cardlang-bad-fragment {label}` but "
        f"label {label!r} has no entry in WRAPPER_RECIPES — every "
        "cardlang-bad-fragment block must be either wrapped and checked here, "
        "or retagged `text` and added to the residual list in this module's "
        "docstring."
    )
    smoke = BAD_FRAGMENT_SMOKE.get(label)
    assert smoke is not None, (
        f"{_block_id(block)}: tagged `cardlang-bad-fragment {label}` but "
        f"label {label!r} has no entry in BAD_FRAGMENT_SMOKE — every "
        "cardlang-bad-fragment block needs a benign filler of the same shape, "
        "proven to pass through the same wrapper, so a rejection of the "
        "block's own text can only be coming from the mistake it demonstrates."
    )
    err = _rejected_when_wrapped(wrapper, smoke, block.text, _block_id(block))
    assert err is not None, (
        f"{_block_id(block)}: tagged `cardlang-bad-fragment`, wrapped via "
        f"{wrapper.__name__}, but the pipeline accepted it — either the "
        "counterexample no longer demonstrates the mistake, or it should be "
        "retagged."
    )


# ---------------------------------------------------------------------------
# Self-tests: prove each code path with synthetic fixtures, independent of
# what the real docs currently contain (today they hold zero `cardlang`,
# zero `cardlang-bad`, and zero `cardlang-bad-fragment` blocks — the guard
# must still have teeth).
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


def test_self_tag_and_label_split() -> None:
    def block(info: str) -> FencedBlock:
        [b] = extract_blocks(f"```{info}\nx\n```\n", "synthetic.md")
        return b

    assert (_tag(block("cardlang")), _label(block("cardlang"))) == ("cardlang", "")
    assert (_tag(block("cardlang-fragment play_phase")), _label(block("cardlang-fragment play_phase"))) == (
        "cardlang-fragment",
        "play_phase",
    )
    # Extra internal whitespace collapses to a single label word.
    assert _label(block("cardlang-fragment   cards_line")) == "cards_line"
    assert (_tag(block("")), _label(block(""))) == ("", "")


def test_self_bare_fence_is_unclassified() -> None:
    [block] = extract_blocks("```\nsome stray dsl\n```\n", "synthetic.md")
    assert _tag(block) == ""
    assert _tag(block) not in KNOWN_TAGS


def test_self_unknown_tag_is_unclassified() -> None:
    # A plausible typo of `cardlang-fragment` must NOT silently fall through
    # to "skipped like text" — that would be the accepted-but-ignored defect
    # this module exists to prevent.
    [block] = extract_blocks("```cardlang-fragmnet\nsome stray dsl\n```\n", "synthetic.md")
    assert _tag(block) not in KNOWN_TAGS


def test_self_cardlang_block_passes() -> None:
    md = f"```cardlang\n{_TINY_GOOD_GAME}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert _tag(block) == "cardlang"
    assert _run_pipeline(block.text, "synthetic.md") is None


def test_self_cardlang_bad_block_is_rejected() -> None:
    md = f"```cardlang-bad\n{_TINY_BAD_GAME}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert _tag(block) == "cardlang-bad"
    err = _run_pipeline(block.text, "synthetic.md")
    assert err is not None
    assert "is not an operator" in err.diagnostic.message


def test_self_cardlang_fragment_block_passes_when_wrapped() -> None:
    md = "```cardlang-fragment\nmove all cards to deck\n```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert _tag(block) == "cardlang-fragment"
    wrapped = _game(f"  phase main {{\n{block.text}  }}\n  winner: highest score")
    assert _run_pipeline(wrapped, "synthetic.md") is None


def _self_frag_wrapper(frag: str) -> str:
    """The wrapper the `cardlang-bad-fragment` self-tests below use — same
    shape as `test_self_cardlang_fragment_block_passes_when_wrapped`'s inline
    wrap, given a name so `_rejected_when_wrapped`'s error messages (which
    reference `wrapper.__name__`) read sensibly."""
    return _game(f"  phase main {{\n{frag}  }}\n  winner: highest score")


_SELF_BAD_FRAGMENT_SMOKE = "move all cards to deck\n"  # benign filler: passes
_SELF_BAD_FRAGMENT_BAD = "move all cards to nonexistent_zone\n"  # unresolved zone


def test_self_cardlang_bad_fragment_block_is_rejected_when_wrapped() -> None:
    md = f"```cardlang-bad-fragment\n{_SELF_BAD_FRAGMENT_BAD}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert _tag(block) == "cardlang-bad-fragment"
    err = _rejected_when_wrapped(
        _self_frag_wrapper, _SELF_BAD_FRAGMENT_SMOKE, block.text, "synthetic.md"
    )
    assert err is not None
    assert "unresolved name" in err.diagnostic.message


def test_self_cardlang_bad_fragment_mistagged_benign_is_not_rejected() -> None:
    # The negative half of the proof above: a *benign* (valid) fragment
    # mistagged `cardlang-bad-fragment` must NOT be reported as a valid
    # rejection. `_rejected_when_wrapped` returns None here (the wrapped
    # benign text passes) — which is exactly what would make
    # `test_bad_fragment_blocks_are_rejected_when_wrapped`'s
    # `assert err is not None` fail loudly on a real block in this
    # situation, rather than the mistagging silently reading as proven.
    md = f"```cardlang-bad-fragment\n{_SELF_BAD_FRAGMENT_SMOKE}```\n"
    [block] = extract_blocks(md, "synthetic.md")
    assert _tag(block) == "cardlang-bad-fragment"
    err = _rejected_when_wrapped(
        _self_frag_wrapper, _SELF_BAD_FRAGMENT_SMOKE, block.text, "synthetic.md"
    )
    assert err is None


def test_self_text_block_is_not_executed() -> None:
    # A `text` block need not even be valid DSL — proving that requires it
    # NOT be run. Executing it would raise; the assertion is just that this
    # module makes no such call for `text`-tagged blocks (the dispatch in
    # test_every_block_is_classified / the per-tag tests above only ever
    # calls _run_pipeline for cardlang/cardlang-fragment/cardlang-bad).
    [block] = extract_blocks("```text\nnot ( valid at all\n```\n", "synthetic.md")
    assert _tag(block) == "text"
    assert _tag(block) not in (
        "cardlang",
        "cardlang-fragment",
        "cardlang-bad",
        "cardlang-bad-fragment",
    )


def test_known_tags_is_the_documented_closed_set() -> None:
    # Pins the vocabulary named in docs/maintaining.md "Doc snippet tagging"
    # so a silent addition here is caught by review of that doc too.
    assert KNOWN_TAGS == {
        "cardlang",
        "cardlang-fragment",
        "cardlang-bad",
        "cardlang-bad-fragment",
        "text",
        "ebnf",
    }
