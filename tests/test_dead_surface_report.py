"""The zero-consumer report (`tools/dead_surface.py`, issue #653) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   the report names every construct the grammar defines that no live
            file uses, and nothing else: a rule or keyword leaves the dead
            list exactly when a corpus, library or stdlib file produces or
            writes it, and an experiment or test consumer is named beside the
            row without reviving it.
domain:     synthetic sources built here, parsed by the real grammar, so no
            cell depends on what the corpus happens to use today -- the
            corpus-facing pins are that the real tree renders and that every
            tree its sources build is on the axis. The rule axis is
            the compiled grammar's (aliases and un-aliased rules that are
            neither filtered nor precedence levels, named as lark's tree
            builder names their nodes, on the alternatives a start symbol
            reaches without taking a node the parse builder only refuses,
            plus any rule or template no start symbol reaches) and the
            keyword axis is every `_X_KW` terminal, pinned against the
            parser's own terminal table. Which of a live construct's
            consumers are scoring sentences is outside it: that is a
            question for the checked game (issue #664).
registry:   rule axis: `tools.dead_surface.rule_axis`, over lark's compiled
            rules; refusals: `tools.dead_surface.refusing_methods`, over
            `cardlang.parse._Builder`; accepted trees:
            `tools.dead_surface.default_sources` through
            `cardlang.parse._transform`; keyword axis:
            `tools.dead_surface.keyword_axis`, pinned against
            `cardlang.parse._parser().terminals`; consumer tiers:
            `tools.dead_surface.TIERS`.
does not prove:  that a dead row SHOULD be retired -- the report is an input to
            the direction review, which owns that decision, and register
            symmetry keeps some rows alive on purpose. Nor that the axis is
            exact beyond the trees the sources build: the accepted-tree
            oracle proves no such tree carries a name the axis lacks, so an
            omission only an unwritten sentence would show (a `?` level whose
            un-aliased alternative keeps more than one child, say) is
            unchecked, and a name no accepted tree carries is on the axis by
            the model alone -- refusal read from the `_reject` spelling and
            from builder methods that raise on every path through their own
            `raise` or a `self` call, nodes named as lark's tree builder
            names them. Nor that a keyword off the dead list is
            used AS the keyword: the scan reads spellings in code, not the
            parser's tokens, so a live file that spells a keyword as a name
            keeps it off the list.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _Builder, _parser, _transform, parse_to_tree
from tools import dead_surface as ds

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAMMAR = (ROOT / "cardlang" / "grammar" / "cardlang.lark").read_text()


def game(body: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n  max_length: 100\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"  phase p {{\n{body}\n  }}\n"
        "}\n"
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
    """Born green; red under: dropping aliases from `rule_axis`, or dropping
    the rules no start symbol reaches."""
    planted = GRAMMAR + '\n%extend primitive_type: "zzplanted" NAME -> planted_dead_form\nplanted_orphan: NAME\n'
    rep = ds.report(planted, [src("a.cardlang", game("    score[0] := 1"))])
    assert {"planted_dead_form", "planted_orphan"} <= set(rep.dead_rules())


def test_a_reject_twin_is_not_surface() -> None:
    """Red under: walking reject twins in `rule_axis`."""
    assert "subset_comma_reject" not in ds.rule_axis(GRAMMAR)
    assert "collection_type_reject" not in ds.rule_axis(GRAMMAR)


def test_a_rule_only_a_reject_twin_reaches_is_not_surface() -> None:
    """A twin is produced only to refuse, and so is every rule only a twin
    leads to, at any depth; a rule a valid alternative also reaches stays.
    Red under: walking reject twins in `rule_axis`."""
    planted = GRAMMAR + (
        '\n%extend primitive_type: NAME "<" planted_helper ">" -> planted_twin_reject'
        '\nplanted_helper: "zzplanted" planted_deeper'
        "\nplanted_deeper: NAME"
        '\n%extend primitive_type: "zzshared" planted_shared -> planted_shared_form'
        '\n%extend primitive_type: "zzrefused" planted_shared -> planted_shared_reject'
        "\nplanted_shared: NAME\n"
    )
    axis = ds.rule_axis(planted)
    assert not {"planted_helper", "planted_deeper"} & axis
    assert {"planted_shared", "planted_shared_form"} <= axis


def test_an_arrow_the_grammar_matches_as_text_is_not_an_alias() -> None:
    planted = GRAMMAR + '\n%extend primitive_type: planted_arrow -> planted_arrow_holder\nplanted_arrow: "zzarrow" "->" NAME\n'
    assert "planted_arrow" in ds.rule_axis(planted)


class _PlantedBuilder:
    def planted_refused(self, meta: object, c: list[object]) -> None:
        raise ValueError("refused")

    def planted_refused_through_a_helper(self, meta: object, c: list[object]) -> None:
        self._refuse()

    def planted_built(self, meta: object, c: list[object]) -> list[object]:
        if not c:
            raise ValueError("refused")
        return c

    def _refuse(self) -> None:
        raise ValueError("refused")


def test_a_node_its_builder_only_refuses_is_not_surface() -> None:
    """A node is refusal machinery by what its builder does, whatever it is
    named; a builder that refuses on only some paths builds surface.
    Red under: skipping only `_reject` names in `rule_axis`, or not following
    a refusal through a `self` helper in `refusing_methods`."""
    planted = GRAMMAR + (
        '\n%extend primitive_type: "zza" NAME -> planted_refused'
        '\n%extend primitive_type: "zzb" NAME -> planted_refused_through_a_helper'
        '\n%extend primitive_type: "zzc" NAME -> planted_built\n'
    )
    axis = ds.rule_axis(planted, builder=_PlantedBuilder)
    assert not {"planted_refused", "planted_refused_through_a_helper"} & axis
    assert "planted_built" in axis


def test_the_default_builder_is_the_parsers() -> None:
    """`div_symbol` refuses the retired `/` and `%` on every path without the
    `_reject` spelling. Red under: defaulting `builder` to anything but
    `cardlang.parse._Builder`."""
    assert "div_symbol" not in ds.rule_axis(GRAMMAR)


def test_every_node_an_accepted_tree_carries_is_on_the_axis() -> None:
    """The axis against the trees lark builds: every node name in every
    source the parse builder accepts is on it. A source the builder refuses
    is outside the check, since no valid file produces its tree.
    Red under: dropping un-aliased rules from `rule_axis`."""
    axis = ds.rule_axis(GRAMMAR)
    missing: dict[str, str] = {}
    for source in ds.default_sources():
        try:
            tree = parse_to_tree(source.text, source.name, start=source.start)
            names = {str(sub.data) for sub in tree.iter_subtrees()}
            _transform(_Builder(source.name, 0), tree)
        except DiagnosticError:
            continue
        for name in names - axis:
            missing.setdefault(name, source.name)
    assert not missing, missing


def test_a_template_is_named_as_its_nodes_are() -> None:
    """An instance's node carries its template's name, and a template nothing
    reachable instantiates is a row. Red under: naming an instance by its
    compiled rule instead of `template_source`."""
    planted = GRAMMAR + (
        '\nplanted_wrapper{x}: "zzwrap" x'
        "\n%extend primitive_type: planted_wrapper{NAME} -> planted_wrapped"
        '\nplanted_unused{x}: "zzunused" x\n'
    )
    axis = ds.rule_axis(planted)
    assert {"planted_wrapper", "planted_unused"} <= axis
    assert not any("{" in name for name in axis)


def test_a_precedence_level_is_not_a_row_but_its_aliases_are() -> None:
    axis = ds.rule_axis(GRAMMAR)
    assert "sum" not in axis and "expr" not in axis
    assert "add" in axis and "sq_any" in axis


def test_an_experiment_or_fixture_consumer_is_named_but_does_not_revive() -> None:
    rep = ds.report(GRAMMAR, [src("tests/fixtures/x.cardlang", game(f"    score[0] := {COUNT}"), "other")])
    assert "sq_count" in rep.dead_rules()
    assert rep.rule_consumers["sq_count"] == {"other": ("tests/fixtures/x.cardlang",)}
    assert "- sq_count  (only in: tests/fixtures/x.cardlang)" in rep.render()


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
    assert len(sections) == 2
    for section in sections:
        keys = [re.split(r"\s{2,}|`$", line[2:].lstrip("`"))[0] for line in section.splitlines() if line.startswith("- ")]
        assert keys == sorted(keys), section.splitlines()[0]


def test_the_documented_entry_point_renders_the_real_tree(capsys: pytest.CaptureFixture[str]) -> None:
    """The one corpus-facing pin: `python -m tools.dead_surface` runs over the
    real grammar and globs and prints its two sections. No row is asserted --
    rows are the review's to read, and they move with the corpus.
    Red under: `main` not writing the render to stdout."""
    assert ds.main([]) == 0
    text = capsys.readouterr().out
    assert text.startswith("# Dead surface -- derived, never maintained")
    assert "## Rules and aliases no corpus, library or stdlib file produces" in text
    assert "## Keywords no corpus, library or stdlib file writes" in text
