"""The Destination distance report (`tools/destinations.py`) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   each reader derives its facts from its source and nothing else:
            a game's declared Primitives are the `name(` entries of its
            `primitives { }` block and no continuation line; a game-local
            native is a declared entry or a `PRIMITIVE_*` registry name the
            game writes in CODE (a name in a comment or string is not a
            site, and the declaration line is not a site); the adapter facts
            are the literal tensor keyword and the presence of the
            determinization hook on the state class; the read ledger is the
            generator issue's checkboxes; the ladder is the `### ` headings
            of the candidates file's Boards section; a grammar point counts
            lark's defined rules and distinct keyword spellings.
domain:     synthetic texts built here for every reader, so no cell depends
            on what the tree holds today; the tree-facing pins are that every
            name the real corpus declares or writes from the registries
            resolves to a top-level `def` in some runtime module, that the
            real adapter yields a literal for both facts, and that the real
            candidates file has a Boards ladder.
registry:   declared entries: `tools.destinations.declared_primitives`;
            game-local natives: `tools.destinations.registry_natives` over
            `cardlang.builtins.functions`; defining modules:
            `tools.destinations.defining_modules`; adapter:
            `tools.destinations.adapter_facts`; ledger:
            `tools.destinations.read_ledger`; ladder:
            `tools.destinations.ladder`; grammar:
            `tools.destinations.grammar_point`.
does not prove:  that a native site SCORES rather than decides legality --
            the report prints the site and the direction review judges it,
            which is why the report has no scoring column; nor that the
            `PRIMITIVE_*` prefix is the whole game-local set -- a game-local
            registry named otherwise is outside the derivation, and the
            tree-facing pin below would not see it, which is the wall this
            ledger names; nor anything about the git history rows, which are
            exercised only by running the module against a checkout.
"""

from __future__ import annotations

import pathlib
import textwrap

from tools import destinations as d

GAME = textwrap.dedent(
    """
    game T {
      players: 2
      // skat_matadors in a comment is not a site
      primitives {
        skat_next_bid(value : Integer) : Integer
        skat_matadors(p : Player) : Integer
            reads is_null, hand[p]
      }
      phase play {
        let m = skat_matadors(declarer)
        when: skat_next_bid(working_bid) > 0
        effect { note := "skat_next_bid" }
        round climb combinations bigtwo_lead_options follows bigtwo_follows
      }
    }
    """
)


def test_declared_primitives_reads_entries_not_continuations() -> None:
    assert d.declared_primitives(GAME) == ["skat_next_bid", "skat_matadors"]
    assert d.declared_primitives("game G { players: 2 }") == []


def test_native_uses_counts_code_sites_only() -> None:
    natives = frozenset({"bigtwo_lead_options", "bigtwo_follows", "unused_native"})
    modules = {"skat_next_bid": "skat", "skat_matadors": "skat", "bigtwo_follows": "bigtwo"}
    uses = {u.name: u for u in d.native_uses("t", GAME, natives, modules)}
    assert set(uses) == {"skat_next_bid", "skat_matadors", "bigtwo_lead_options", "bigtwo_follows"}
    assert len(uses["skat_matadors"].sites) == 1  # comment and declaration excluded
    assert len(uses["skat_next_bid"].sites) == 1  # the string literal is not a site
    assert uses["skat_next_bid"].module == "skat"
    assert uses["bigtwo_lead_options"].module == "?"


def test_registry_natives_reads_primitive_prefixed_frozensets() -> None:
    class Registries:
        PRIMITIVE_A = frozenset({"a1", "a2"})
        PRIMITIVE_B = frozenset({"b1"})
        BUILTIN_X = frozenset({"x1"})
        PRIMITIVE_NOT_A_SET = ("t1",)

    assert d.registry_natives(Registries) == frozenset({"a1", "a2", "b1"})


def test_defining_modules_takes_public_top_level_defs(tmp_path: pathlib.Path) -> None:
    (tmp_path / "alpha.py").write_text("def pub():\n    pass\ndef _priv():\n    pass\nclass C:\n    def m(self):\n        pass\n")
    (tmp_path / "beta.py").write_text("def pub():\n    pass\ndef other():\n    pass\n")
    assert d.defining_modules(tmp_path) == {"pub": "alpha", "other": "beta"}


def test_adapter_facts_reads_literal_and_hook() -> None:
    src = textwrap.dedent(
        """
        class CardlangState(Base):
            def resample_from_infostate(self, pid, rng):
                pass
        t = GameType(provides_information_state_tensor=True)
        """
    )
    assert d.adapter_facts(src) == {"information_state_tensor": True, "resample_from_infostate": True}
    src2 = "class CardlangState(Base):\n    pass\nt = GameType(provides_information_state_tensor=flag)\n"
    assert d.adapter_facts(src2) == {"information_state_tensor": None, "resample_from_infostate": False}


def test_read_ledger_splits_checkboxes() -> None:
    body = "- [ ] **skat** (22)\n- [x] **tichu** (25)\n- [ ] plain line\n* [x] **not-a-dash**\n"
    assert d.read_ledger(body) == (["tichu"], ["skat"])


def test_ladder_reads_boards_section_only() -> None:
    text = "## Rummy\n### gin\n## Boards: the ladder\n### hex\ntext\n### battleship\n## Edge\n### war\n"
    assert d.ladder(text) == ["hex", "battleship"]


def test_grammar_point_counts_rules_and_keyword_spellings() -> None:
    grammar = textwrap.dedent(
        """
        start: "game" NAME _PLAYERS_KW NUMBER
        _PLAYERS_KW: "players"
        NAME: /[a-z]+/
        NUMBER: /[0-9]+/
        %import common.WS
        %ignore WS
        """
    )
    point = d.grammar_point("x", "0123456789", grammar, ["docs/games/a.cardlang", "docs/games/_candidates.md"])
    assert point.sha == "01234567"
    assert point.games == 1
    assert point.rules == 1
    assert point.keywords == 2  # "game" (plain string) and "players" (_KW terminal)


# --- tree-facing pins ----------------------------------------------------------------


def test_every_corpus_native_resolves_to_a_runtime_def() -> None:
    uses = d.corpus_native_uses()
    assert uses, "the corpus names no native function -- the readers see nothing"
    unresolved = sorted({u.name for u in uses if u.module == "?"})
    assert unresolved == [], unresolved


def test_real_adapter_yields_literals() -> None:
    facts = d.adapter_facts(d.ADAPTER.read_text())
    assert facts["information_state_tensor"] in (True, False)
    assert isinstance(facts["resample_from_infostate"], bool)


def test_real_candidates_file_has_a_boards_ladder() -> None:
    assert d.ladder(d.CANDIDATES.read_text())
