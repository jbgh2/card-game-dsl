"""`active_rules:` op x referent totality, and per-template diagnostic dedup.

`RuleRef.op` (cardlang/ast/nodes.py) is one of "plain" | "add" | "remove" |
"override" — closed by the grammar's `rule_ref` productions
(cardlang/grammar/cardlang.lark). `remove` and `override` are grammatically
argument-less (`rule_remove: "-" NAME`, `rule_override: "override" NAME` —
no `[rule_args]` slot, unlike `rule_add`/`rule_plain`), so neither can EVER
instantiate a parameterized rule; asking one to "pass arguments" is an
unsatisfiable diagnostic; no source text repairs it (see git history
"active_rules op dispatch" finding). This module pins the full op x referent
matrix so every cell either works or fails with an EXPRESSIBLE repair.

Property: every (`RuleRef.op`, referent kind) combination has defined, tested
resolve-time semantics — clean acceptance, or a diagnostic whose repair is a
source-text change that actually exists in the grammar.

Domain: `RuleRef.op` (plain/add/remove/override) x referent kind (library
plain, library parameterized, game-local plain, game-local parameterized,
undefined name).

Registry: the `op` field comment on `RuleRef` (cardlang/ast/nodes.py) and the
grammar's four `rule_ref` productions (cardlang/grammar/cardlang.lark).

Covered (20 cells — full cross product):

    op        | lib-plain | lib-param   | local-plain | local-param | undefined
    ----------|-----------|-------------|-------------|-------------|----------
    plain     | clean     | pass-args*  | clean       | pass-args*  | undefined
    add       | clean     | pass-args*  | clean       | pass-args*  | undefined
    remove    | never-add | never-add   | never-add   | never-inst‡ | undefined
    override  | not-supp  | not-supp    | not-supp    | not-supp‡   | undefined

    * "pass-args" only for a BARE reference (no `(...)`); WITH the correct
      argument count and domain, plain/add cleanly instantiate — sampled
      below (`lib-param (args)`, `local-param (args)`).
    ‡ `remove`/`override` of a local template that no `plain`/`add` ever
      instantiates ALSO trips the pre-existing "never instantiated" wall
      (the template's own declaration is never proven, whether or not a
      remove/override references it) — two true, independently repairable
      diagnostics, not a contradiction (both point at the same fix: add it
      with arguments somewhere, or delete the template).

  `add` is sampled, not fully cross-producted: `_instantiate_rules` never
  branches on `op` for `plain` vs `add` (both grammar productions carry the
  same optional `[rule_args]`), so the two are one code path under different
  spellings — two representative cells stand in for the other three.

  `remove`/`override` additionally split on WHERE the reference sits
  relative to a `plain`/`add` that could satisfy it (own list / parent's
  list / a sibling rule-delta phase's list / added-then-removed in one
  list) — covered by the "remove reachability" tests below, independent of
  referent kind (the reachability check runs before referent-kind
  dispatch).

Sampled: `add` (see above). The "reachable remove" shapes are sampled by
kind (a library-plain and a library-parameterized referent), not crossed
with every referent kind again — `_check_remove_reachability` never
inspects the referent's kind, only the ref's `op`/`name` and the phase
tree, so referent kind cannot affect its outcome.

Residual: `_check_remove_reachability`'s cluster precision is coarser than
full runtime precision in two narrow, corpus-unexercised ways (order within
one list; cross-sibling delta references) — recorded in issue #103, not
walled further here.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

LOCAL_PLAIN = """
rule LocalPlain {
  constrains: play_to_trick
  applies_when: state.led_suit is not none
  demands: cards in hand where card.suit is state.led_suit
  if_impossible: hand
}
"""

LOCAL_PARAM = """
rule LocalParam(suit: Suit) {
  constrains: play_to_trick
  applies_when: state.led_suit is none
  demands: cards in hand where card.suit is not suit
  if_impossible: hand
}
"""


def _game(active: str, rules: str = "", nested: str = "", second_phase: str = "") -> str:
    return f"""
game Mini {{
  players: 4
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ score[player] : Integer = 0  leader : Player? = none }}
  phase play {{
    active_rules: [{active}]
    legal_moves: [play_to_trick]
    {nested}
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
  }}
  {second_phase}
  winner: highest score
}}
{rules}
"""


def _accepts(src: str) -> None:
    check_dsl(src, "mini.cardlang")


def _full_report(exc: DiagnosticError) -> str:
    """The complete diagnostic text — `_raise_if_errors` (resolve.py) raises
    the first diagnostic and, only when there is more than one, attaches
    `bag.format()` (EVERY item, including the first) as a single note.
    `str(exc)` alone would miss the rest; `str(exc) + notes` would DOUBLE the
    first when notes are present. This picks exactly one full, deduplicated
    view."""
    notes = getattr(exc, "__notes__", ())
    return notes[0] if notes else str(exc)


def _rejects(src: str, needle: str) -> str:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    report = _full_report(ei.value)
    assert needle in report, report
    return report


# --- plain / add x every referent kind --------------------------------------


def test_plain_x_library_plain_clean() -> None:
    _accepts(_game("MustFollowSuit"))


def test_plain_x_library_param_bare_rejected() -> None:
    report = _rejects(_game("NoLeadingSuitUntilBroken"), "is parameterized")
    assert "pass arguments" in report


def test_plain_x_library_param_args_clean() -> None:
    _accepts(_game("NoLeadingSuitUntilBroken(spades)"))


def test_plain_x_local_plain_clean() -> None:
    _accepts(_game("LocalPlain", rules=LOCAL_PLAIN))


def test_plain_x_local_param_bare_rejected_both_true_and_repairable() -> None:
    report = _rejects(_game("LocalParam", rules=LOCAL_PARAM), "is parameterized")
    assert "pass arguments" in report
    assert "never instantiated" in report
    # The root-cause fix: a name that DOES resolve to a real template is never
    # ALSO reported "undefined" merely because its instantiation failed for
    # some other, already-reported reason.
    assert "undefined rule" not in report


def test_plain_x_local_param_args_clean() -> None:
    _accepts(_game("LocalParam(spades)", rules=LOCAL_PARAM))


def test_plain_x_undefined_rejected() -> None:
    _rejects(_game("Nope"), "active_rules names undefined rule 'Nope'")


def test_add_x_library_plain_clean() -> None:
    # `add` is `plain` under a different spelling (`_instantiate_rules` never
    # branches on plain vs add) — sampled, not fully cross-producted (see
    # module docstring).
    _accepts(_game("+ MustFollowSuit"))


def test_add_x_library_param_args_clean() -> None:
    _accepts(_game("+ NoLeadingSuitUntilBroken(spades)"))


def test_arity_mismatch_no_longer_piles_an_undefined_rule_note() -> None:
    # Regression for the root-cause fix: `known_rule_names` (resolve.py
    # `resolve()`) is captured from the ORIGINAL `game.rules` union the
    # library, before instantiation — so a real name with a real, separately
    # reported mismatch is never ALSO flagged undefined.
    report = _rejects(
        _game("NoLeadingSuitUntilBroken(spades, hearts)"), "takes 1 argument(s), got 2"
    )
    assert "undefined rule" not in report


# --- remove: never instantiates; resolves by name against an activation ----


def test_remove_x_library_plain_never_added_rejected() -> None:
    report = _rejects(_game("- MustFollowSuit"), "removes a rule that is never added")
    assert "pass arguments" not in report  # an unsatisfiable dead-end


def test_remove_x_library_param_never_added_rejected() -> None:
    report = _rejects(
        _game("- NoLeadingSuitUntilBroken"), "removes a rule that is never added"
    )
    assert "pass arguments" not in report


def test_remove_x_local_plain_never_added_rejected() -> None:
    _rejects(_game("- LocalPlain", rules=LOCAL_PLAIN), "removes a rule that is never added")


def test_remove_x_local_param_never_added_rejected_both_true_and_repairable() -> None:
    report = _rejects(_game("- LocalParam", rules=LOCAL_PARAM), "never instantiated")
    assert "removes a rule that is never added" in report
    assert "pass arguments" not in report


def test_remove_x_undefined_rejected() -> None:
    _rejects(_game("- Nope"), "active_rules names undefined rule 'Nope'")


def test_remove_of_a_rule_added_in_the_same_list_is_valid() -> None:
    # The intended, unambiguous usage this whole fix restores: `-NAME` needs
    # no arguments even for a parameterized rule, because only one
    # instantiation per name is ever allowed game-wide — bare `-NAME`
    # unambiguously identifies it.
    _accepts(_game("+ NoLeadingSuitUntilBroken(hearts), - NoLeadingSuitUntilBroken"))


def test_remove_of_a_rule_added_by_the_parents_own_unconditional_list_is_valid() -> None:
    # The realistic idiom: a base phase activates a rule unconditionally; a
    # nested rule-delta sub-phase conditionally removes it once a transition
    # fires (runtime/phases.py `compute_active_rules`: a rule-delta child's
    # own list is layered ON TOP of its parent's).
    _accepts(
        _game(
            "MustFollowSuit",
            nested="""
    phase shed {
      active_rules: [- MustFollowSuit]
      transition_to: done_shedding when play_to_trick where action.card.suit is hearts
    }
    phase done_shedding {
    }
""",
        )
    )


def test_remove_referencing_only_a_sibling_delta_phases_add_is_rejected() -> None:
    # NOT valid, even though it looks parallel to the case above: only one of
    # a "before"/"after" rule-delta sibling pair is ever active at a time
    # (runtime/phases.py `_delta_active`), so a name the OTHER sibling added
    # was never in `names` on the call where this remove runs either — a
    # runtime no-op this check correctly declines to call "reachable".
    report = _rejects(
        _game(
            "MustFollowSuit",
            nested="""
    phase hearts_not_broken {
      active_rules: [+ NoLeadingSuitUntilBroken(hearts)]
      transition_to: hearts_broken when play_to_trick where action.card.suit is hearts
    }
    phase hearts_broken {
      active_rules: [- NoLeadingSuitUntilBroken]
    }
""",
        ),
        "removes a rule that is never added",
    )
    assert "pass arguments" not in report


# --- override: unconditionally unsupported, but with ONE clear diagnostic --


def test_override_x_library_plain_rejected_single_message() -> None:
    report = _rejects(_game("override MustFollowSuit"), "not yet supported")
    assert report.count("not yet supported") == 1


def test_override_x_library_param_rejected_without_the_unsatisfiable_pass_args() -> None:
    report = _rejects(_game("override NoLeadingSuitUntilBroken"), "not yet supported")
    # Were `_instantiate_rules` to ALSO run override refs through the
    # plain/add argument-checking path, then — since override can never carry
    # arguments (no grammar slot) — that would always produce a second,
    # unsatisfiable "pass arguments" diagnostic alongside the real one.
    assert "pass arguments" not in report
    assert "undefined rule" not in report


def test_override_x_local_plain_rejected_single_message() -> None:
    report = _rejects(_game("override LocalPlain", rules=LOCAL_PLAIN), "not yet supported")
    assert report.count("not yet supported") == 1


def test_override_x_local_param_rejected_both_true_and_repairable() -> None:
    # `override` never instantiates (module docstring), so a LOCAL template
    # referenced only by override still trips the pre-existing "never
    # instantiated" wall too — two true, independently repairable messages.
    report = _rejects(_game("override LocalParam", rules=LOCAL_PARAM), "not yet supported")
    assert "never instantiated" in report
    assert "pass arguments" not in report


def test_override_x_undefined_rejected() -> None:
    report = _rejects(_game("override Nope"), "active_rules names undefined rule 'Nope'")
    assert "not yet supported" in report


# --- a defective template validates once, not once per reference


def test_defective_template_diagnostic_fires_exactly_once_across_two_activating_phases() -> None:
    src = """
game Mini {
  players: 4
  max_length: 1000
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }
  state { score[player] : Integer = 0  leader : Player? = none }
  phase phasea {
    active_rules: [Capture(hearts)]
    legal_moves: [play_to_trick]
    leader := 0
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
  }
  phase phaseb {
    active_rules: [Capture(hearts)]
    legal_moves: [play_to_trick]
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
  }
  winner: highest score
}
rule Capture(suit: Suit) {
  constrains: play_to_trick
  applies_when: any suit where suit is hearts
  demands: cards in hand where card.suit is not hearts
  if_impossible: hand
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    report = _full_report(ei.value)
    assert report.count("shadowing its own parameter") == 1, report
