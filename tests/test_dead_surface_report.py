"""The zero-consumer report (`tools/dead_surface.py`, issue #653) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   the report names every construct the grammar defines that no live
            file uses, and nothing else: a rule or keyword leaves the dead
            list exactly when a corpus, library or stdlib file produces or
            writes it, and an experiment or test consumer is named beside the
            row without reviving it. The scoring column names a construct
            exactly when every live occurrence sits in a scoring sentence.
domain:     synthetic sources built here, parsed by the real grammar, so no
            cell depends on what the corpus happens to use today -- the one
            corpus-facing pin is that the real tree renders. The rule axis is
            the grammar scrape's (aliases, un-aliased non-inlined rules, no
            reject twins) and the keyword axis is every `_X_KW` terminal,
            each pinned against the parser's own terminal table. Scoring is
            an assignment to the winner variable or to a variable that flows
            into it, and a function every call of which sits in one, both
            transitively, with `let` bindings read as assignments to a name
            bound for the rest of its block and parameters bound within their
            function -- state and zone names match by spelling, so two phases
            declaring one state name share it; a game with no `winner:
            highest/lowest x` has no scoring sentence, which is stated, not a
            gap. Calls resolve to the calling game's own function, else to a
            library's by name (two libraries defining one name merge,
            conservatively); a Primitive or builtin callee has no body to
            classify and is skipped; only live sources' calls classify a
            function. A NAME in label position -- a callee, a member's
            field, a struct or named argument's label -- is not a read.
registry:   rule axis: `tools.dead_surface.rule_axis`; keyword axis:
            `tools.dead_surface.keyword_axis`, pinned against
            `cardlang.parse._parser().terminals`; consumer tiers:
            `tools.dead_surface.TIERS`.
does not prove:  that a dead row SHOULD be retired -- the report is an input to
            the direction review, which owns that decision, and register
            symmetry keeps some rows alive on purpose. Nor that a `?`-level
            rule with an un-aliased multi-child alternative is on the axis:
            precedence levels are excluded wholesale, so such a construct
            would go unreported rather than misreported.
"""

from __future__ import annotations

import pathlib
import re

from cardlang.parse import _parser
from tools import dead_surface as ds

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAMMAR = (ROOT / "cardlang" / "grammar" / "cardlang.lark").read_text()


def game(body: str, *, state: str = "", functions: str = "", winner: str = "winner: highest score") -> str:
    return (
        "game G {\n"
        "  players: 2\n  max_length: 100\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        f"  state {{ score[player] : Integer = 0  {state} }}\n"
        f"  {winner}\n"
        f"  phase p {{\n{body}\n  }}\n"
        "}\n"
        f"{functions}"
    )


def src(name: str, text: str, tier: str = "corpus") -> ds.Source:
    return ds.Source(name, text, "start", tier)


COUNT = "number of subsets of 2 cards in hand[0] where 1 is 1"


def test_a_live_consumer_takes_a_rule_off_the_dead_list() -> None:
    rep = ds.report(GRAMMAR, [src("a.cardlang", game(f"    score[0] := {COUNT}"))])
    dead = rep.dead_rules()
    assert "sq_count" not in dead and "subset_exact" not in dead
    assert "sq_all" in dead  # nothing synthetic writes `all subsets`


def test_a_planted_production_nothing_produces_is_reported() -> None:
    """Born green; red under: dropping aliases from `rule_axis`."""
    planted = GRAMMAR + "\nplanted_rule: NAME -> planted_dead_form\n"
    rep = ds.report(planted, [src("a.cardlang", game("    score[0] := 1"))])
    assert "planted_dead_form" in rep.dead_rules()


def test_a_reject_twin_is_not_surface() -> None:
    """Red under: dropping the `_reject` exclusion from `rule_axis`."""
    assert "subset_comma_reject" not in ds.rule_axis(GRAMMAR)
    assert "collection_type_reject" not in ds.rule_axis(GRAMMAR)


def test_a_precedence_level_is_not_a_row_but_its_aliases_are() -> None:
    axis = ds.rule_axis(GRAMMAR)
    assert "sum" not in axis and "expr" not in axis
    assert "add" in axis and "sq_any" in axis


def test_an_experiment_or_fixture_consumer_is_named_but_does_not_revive() -> None:
    rep = ds.report(GRAMMAR, [src("tests/fixtures/x.cardlang", game(f"    score[0] := {COUNT}"), "other")])
    assert "sq_count" in rep.dead_rules()
    assert rep.rule_consumers["sq_count"] == {"other": ("tests/fixtures/x.cardlang",)}
    assert "- sq_count  (only in: tests/fixtures/x.cardlang)" in rep.render()


def test_the_scoring_column_names_a_construct_used_only_to_score() -> None:
    only_scoring = src("a.cardlang", game(f"    score[0] := {COUNT}"))
    rep = ds.report(GRAMMAR, [only_scoring])
    assert rep.all_scoring["sq_count"] == ("a.cardlang",)
    in_a_guard = src("b.cardlang", game(f"    if ({COUNT}) > 0 {{ score[0] := 1 }}"))
    rep = ds.report(GRAMMAR, [only_scoring, in_a_guard])
    assert "sq_count" not in rep.all_scoring


def test_scoring_flows_through_a_feeder_variable_and_a_function() -> None:
    text = game(
        "    hand_points := f()\n    score[0] += hand_points",
        state="hand_points : Integer = 0",
        functions=f"function f() = {COUNT}\n",
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "sq_count" in rep.all_scoring
    leaked = game(
        "    hand_points := f()\n    score[0] += hand_points\n    if f() > 0 { score[1] := 1 }",
        state="hand_points : Integer = 0",
        functions=f"function f() = {COUNT}\n",
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", leaked)])
    # the guard's call is not a scoring sentence, so the function is not one either
    assert "sq_count" not in rep.all_scoring


def test_scoring_flows_through_a_let_binding() -> None:
    """Hearts' and French Tarot's shape: a phase-local `let` chain feeding the
    winner variable. Red under: dropping `let_stmt` from
    `_BINDING_STATEMENTS`."""
    text = game(f"    let base = {COUNT}\n    let doubled = base * 2\n    score[0] += doubled")
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "sq_count" in rep.all_scoring
    leaked = game(f"    let base = {COUNT}\n    score[0] += base\n    if base > 0 {{ move all cards to deck }}")
    rep = ds.report(GRAMMAR, [src("a.cardlang", leaked)])
    # the binding scores, and its consumers elsewhere do not unmake that: the
    # construct sits in the binding, which is a scoring sentence
    assert "sq_count" in rep.all_scoring


def test_a_same_named_let_in_another_block_is_its_own_binding() -> None:
    """Two phases each bind `points`; only one feeds the score. Red under:
    binding a `let` by its spelling instead of its position."""
    body = (
        f"    let points = {COUNT}\n    score[0] += points\n"
        "  }\n  phase q {\n"
        "    let points = any card in hand[0] where 1 is 1\n    move all cards to deck"
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", game(body))])
    assert "sq_count" in rep.all_scoring
    assert "cq_any" not in rep.all_scoring


def test_strings_and_comments_are_read_as_the_grammar_defines_them() -> None:
    """A `//` inside a string opens no comment, and a string may span lines.
    Red under: masking with a comment-first, single-line regex."""
    after_a_marker = game(
        '    if any card in hand[0] where card.rank is "x//y" { score[0] := 1 divided by 2 rounded down }'
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", after_a_marker)])
    assert "DOWN" not in rep.dead_keywords()
    inside_a_multiline_string = game(
        '    if any card in hand[0] where card.rank is "a\nrounded down\n" { score[0] := 1 }'
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", inside_a_multiline_string)])
    assert "DOWN" in rep.dead_keywords()


def test_a_library_function_called_only_to_score_is_scoring_surface() -> None:
    """The construct lives in the library; every call sits in a game's
    scoring sentence; the library is where the column names it. Red under:
    resolving calls within one source only."""
    library = ds.Source("l.cardlang", f"library L {{\n  function f() = {COUNT}\n}}\n", "library", "shared")
    scoring_game = src("a.cardlang", game("    score[0] := f()"))
    rep = ds.report(GRAMMAR, [library, scoring_game])
    assert rep.all_scoring["sq_count"] == ("l.cardlang",)
    guarding_game = src("b.cardlang", game("    if f() > 0 { score[0] := 1 }"))
    rep = ds.report(GRAMMAR, [library, scoring_game, guarding_game])
    assert "sq_count" not in rep.all_scoring


def test_a_callee_is_not_a_read_of_a_same_named_state_variable() -> None:
    """State `f` and function `f` may share a spelling; `score[0] := f()`
    reads the function, never the state. Red under: taking every NAME token
    of a value as a read."""
    text = game(
        f"    f := {COUNT}\n    score[0] := f()",
        state="f : Integer = 0",
        functions="function f() = 1\n",
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "sq_count" not in rep.all_scoring


def test_a_member_field_is_a_label_not_a_read() -> None:
    """State `value` and a field `.value` share a spelling; `score[0] :=
    box.value` reads `box`. Red under: visiting a member's field child."""
    text = game(
        f"    value := {COUNT}\n    score[0] := box.value",
        state="value : Integer = 0  box : Integer = 0",
    )
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "sq_count" not in rep.all_scoring


def test_only_live_call_sites_classify_a_shared_function() -> None:
    """A fixture guarding on a library function is not a consumer the column
    speaks about, so it neither unmakes a scoring function (first) nor makes
    one (second). Red under: resolving calls from every tier."""
    library = ds.Source("l.cardlang", f"library L {{\n  function f() = {COUNT}\n}}\n", "library", "shared")
    scoring_game = src("a.cardlang", game("    score[0] := f()"))
    fixture_guard = src("tests/fixtures/g.cardlang", game("    if f() > 0 { score[0] := 1 }"), "other")
    rep = ds.report(GRAMMAR, [library, scoring_game, fixture_guard])
    assert rep.all_scoring["sq_count"] == ("l.cardlang",)
    fixture_scoring = src("tests/fixtures/s.cardlang", game("    score[0] := f()"), "other")
    rep = ds.report(GRAMMAR, [library, fixture_scoring])
    assert "sq_count" not in rep.all_scoring


def test_a_game_with_no_ranked_winner_has_no_scoring_sentence() -> None:
    text = game(f"    score[0] := {COUNT}", winner="winner: the player where score[player] > 0")
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "sq_count" not in rep.all_scoring


def test_a_keyword_in_a_comment_or_a_string_is_not_written() -> None:
    """Red under: dropping the comment or the string stripping in `_read`."""
    text = game('    // override\n    if any card in hand[0] where card.rank is "override" { score[0] := 1 }')
    rep = ds.report(GRAMMAR, [src("a.cardlang", text)])
    assert "OVERRIDE" in rep.dead_keywords()
    written = game("    score[0] := 1 divided by 2 rounded down")
    rep = ds.report(GRAMMAR, [src("a.cardlang", written)])
    assert "DOWN" not in rep.dead_keywords()


def test_the_keyword_axis_is_every_keyword_terminal() -> None:
    """Derived twice: the grammar scrape against the parser's terminal table."""
    scraped = set(ds.keyword_axis(GRAMMAR))
    terminals = {t.name[1:-3] for t in _parser().terminals if t.name.endswith("_KW")}
    assert scraped == terminals


# The denominator, derived a second time here rather than read off `TIERS`, so
# a tier dropped from the tool is a tier this pin still expects.
_EXPECTED_TIERS = {
    "docs/games/*.cardlang": ("corpus", "start"),
    "docs/libraries/*.cardlang": ("shared", "library"),
    "cardlang/stdlib/*.cardlang": ("shared", "stdlib_rules"),
    "experiments/**/*.cardlang": ("other", "start"),
    "tests/**/*.cardlang": ("other", "start"),
}


def test_the_default_denominator_is_every_tier() -> None:
    """Red under: dropping a tier from `TIERS`, or mis-kinding a directory."""
    by_name = {s.name: s for s in ds.default_sources()}
    for pattern, (tier, start) in _EXPECTED_TIERS.items():
        paths = list(ROOT.glob(pattern))
        assert paths, pattern
        for path in paths:
            source = by_name[path.relative_to(ROOT).as_posix()]
            assert (source.tier, source.start) == (tier, start), path


def test_a_source_that_does_not_parse_is_counted_not_fatal() -> None:
    rep = ds.report(GRAMMAR, [src("broken.cardlang", "game G { players: }")])
    assert rep.unparsed == ("broken.cardlang",) and rep.parsed == ()


def test_the_report_is_sorted_in_every_section() -> None:
    """Born green; red under: dropping a `sorted` in `dead_rules`,
    `dead_keywords` or `render`."""
    rep = ds.report(GRAMMAR, [src("a.cardlang", game("    score[0] := 1"))])
    assert rep.dead_rules() == sorted(rep.dead_rules())
    words = [rep.keywords[k] for k in rep.dead_keywords()]
    assert words == sorted(words)
    sections = rep.render().split("\n## ")[1:]
    assert len(sections) == 3
    for section in sections:
        keys = [re.split(r"\s{2,}|`$", line[2:].lstrip("`"))[0] for line in section.splitlines() if line.startswith("- ")]
        assert keys == sorted(keys), section.splitlines()[0]


def test_the_real_tree_renders() -> None:
    """The one corpus-facing pin: the tool runs over the real grammar and
    globs and prints its three sections. No row is asserted -- rows are the
    review's to read, and they move with the corpus."""
    text = ds.report(ds.GRAMMAR.read_text(), ds.default_sources()).render()
    assert text.startswith("# Dead surface -- derived, never maintained")
    assert "## Rules and aliases no corpus, library or stdlib file produces" in text
    assert "## Keywords no corpus, library or stdlib file writes" in text
    assert "## Constructs whose every live consumer is a scoring sentence" in text
