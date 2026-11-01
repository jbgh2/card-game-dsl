"""What a rule's `constrains:` may name, and what a designer is told when it
names a move no rule can bind.

A rule binds at the trick round's card decision and nowhere else
(decisions.md "Rule demand forms"), so of every spelling `constrains:` can
hold exactly one is accepted -- the move type that decision asks about. Every
other spelling is refused naming the construct that makes the move as the
place its condition goes, and every fix a refusal states is applied here and
checks clean: to the cell's game, or, for the climbing form's move type, to
Big Two's climb round. Where a family library's own procedure makes the
offer, the fix is also played, and the constrained move is never offered
once its condition fails: a fix is a claim, and it passes.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a `constrains:` naming `RULE_ENFORCED_MOVE_TYPE` is accepted;
                 every other target is refused once, in the resolve layer,
                 with the head and the fix its target class calls for; each
                 fix the refusal states checks clean where it is applied; and
                 a fix for a move a library's procedure offers keeps the move
                 out of every offer its condition fails at, on a played line.
domain:          the `constrains:` target crossed with the rule's origin. The
                 target axis: the clause absent; every kernel move type,
                 undeclared, each refused by the arm its
                 `KERNEL_MOVE_FORMS` form names; every kernel move type but
                 the enforced one, declared by the game under the kernel's
                 spelling; a move type of the game's own, crossed with its
                 parameters (none, one) and its stake (none and every member
                 of `n.STAKES`) and with where it is declared (the game, a
                 family library the game uses); a family library's move type
                 its own procedure offers; a move type the game declares
                 because a family library contracts for it
                 (`requires { ... : Move }`) and offers it; a spelling
                 nothing declares. The origin axis: a game's rule, a game's
                 template instantiated, a family library's rule, a family
                 library's template instantiated. Every cell activates its
                 rule; a game's own rule is checked whether or not a phase
                 activates it. A template parameter never reaches the
                 target, which the grammar holds as a bare name, not an
                 expression. A game move type spelled `play_to_trick` is
                 issue #1010; a family library rule no game activates is
                 issue #1011; a repeated `constrains:` clause is issue #173.
registry:        kernel move types and their forms:
                 `cardlang.stdlib.moves.KERNEL_MOVE_FORMS` (the set
                 `cardlang.stdlib.moves.LIBRARY_MOVE_TYPES`, the forms
                 `cardlang.stdlib.moves.KERNEL_MOVE_FORM_NAMES`); the
                 enforced one: `cardlang.stdlib.moves.RULE_ENFORCED_MOVE_TYPE`;
                 stakes: `cardlang.ast.nodes.STAKES`; the one-site law the
                 refusal rests on: tests/test_rule_sites.py::test_the_rule_cascade_has_one_caller.
held by:         Derived and Pinned. A target is a string the grammar reads as
                 a bare name and the resolver classifies against the game's
                 declarations; no type can hold which names a game declares.
                 The kernel arms are Unrepresentable: an exhaustive match over
                 `KernelMoveForm`, and `LIBRARY_MOVE_TYPES` is the form
                 table's keys.
does not prove:  that an accepted rule fires: that is `active_rules:`'s
                 reach (tests/rejections/rules_where_no_trick_round_runs.cardlang)
                 and the cascade's own behaviour (tests/test_legal_cards.py);
                 that an applied fix keeps the rule's meaning, since the
                 condition written into each form here is a stand-in; and
                 that a fix applied to the climbing form holds for a
                 Registered Engine, whose `follows` the refusal says the game
                 cannot add to.
"""

from __future__ import annotations

import dataclasses
import pathlib
import random
from collections.abc import Callable, Iterator
from typing import Any, assert_never

import pytest

import cardlang.pipeline as pipeline
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.stdlib.moves import (
    CLIMB_DECISION_MOVE_TYPE,
    KERNEL_MOVE_FORM_NAMES,
    KERNEL_MOVE_FORMS,
    LIBRARY_MOVE_TYPES,
    RULE_ENFORCED_MOVE_TYPE,
    KernelMoveForm,
)

_LIBRARY = "docs/libraries/lib.cardlang"

_HOST = """
game ConstrainsGrid{tag} {{
  {uses}
  players: 2
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{
    deck       : Deck
    hand[player] : Hand<player>
    trick_pile : TrickPile
    captured[player] : PlayerPile<player>
  }}
  state {{
    score[player] : Integer = 0
    leader : Player = 0
  }}
  phase deal {{
    deal 3 cards from deck to each hand
{offers}
  }}
  phase play {{
{activate}    legal_moves:  [play_to_trick]
    repeat until (all players where (number of cards in hand[player]) is 0) {{
      round play_to_trick from leader over all players source hand into trick_pile
            winner highest_of_led_suit
      move all cards from trick_pile to captured[winner]
      leader := winner
    }}
  }}
  winner: highest score
}}
{game_defs}
"""


@dataclasses.dataclass(frozen=True)
class Target:
    """One `constrains:` target: its class, its spelling, and the move type
    it names when something declares it (where, with what parameters and
    stake)."""

    kind: str  # "absent" | "kernel" | "declared" | "unknown"
    spelling: str | None
    declared_in: str | None = None  # "game" | "library" | "library_offered" | "contract"
    params: bool = False
    stake: n.Stake | None = None

    @property
    def id(self) -> str:
        return "-".join(x for x in (self.kind, self.spelling or "none", self.declared_in) if x)


_COND = "score[actor] is 0"
_LIB_REQUIRES = "requires { score[player] : Integer\n leader : Player }"


def _move_type(
    name: str, params: bool, stake: n.Stake | None, when: str | None = None, effect: str = ""
) -> str:
    sig = f"{name}(s : Suit)" if params else name
    row = f"{stake} " if stake else ""
    guard = f"when: {when} " if when else ""
    return f"move_type {sig} {{ {row}{guard}effect {{ {effect} }} }}"


def _targets() -> Iterator[Target]:
    yield Target("absent", None)
    for kernel in sorted(LIBRARY_MOVE_TYPES):
        yield Target("kernel", kernel)
    for kernel in sorted(LIBRARY_MOVE_TYPES - {RULE_ENFORCED_MOVE_TYPE}):
        yield Target("declared", kernel, "game")
    for where in ("game", "library"):
        for params in (False, True):
            for stake in (None, *n.STAKES):
                name = f"step_{'p' if params else 'n'}_{stake or 'plain'}"
                yield Target("declared", name, where, params, stake)
    yield Target("declared", "step_offered", "library_offered")
    yield Target("declared", "step_contracted", "contract")
    yield Target("unknown", "nonesuch_move")


ORIGINS = ("game_rule", "game_template", "library_rule", "library_template")


@dataclasses.dataclass
class Game:
    """One game the grid checks: the rule (if any) and where it lives, plus
    the definitions and offers around it."""

    rule: str | None
    rule_in_library: bool
    activate: str | None
    game_defs: list[str] = dataclasses.field(default_factory=list)
    library_body: list[str] = dataclasses.field(default_factory=list)
    offers: list[str] = dataclasses.field(default_factory=list)

    def source(self, monkeypatch: pytest.MonkeyPatch, tag: str) -> str:
        game_defs = list(self.game_defs)
        library_body = list(self.library_body)
        if self.rule is not None:
            (library_body if self.rule_in_library else game_defs).append(self.rule)
        uses = ""
        if library_body:
            name = f"lib_{tag}"
            library = parse_library(f"library {name} {{ {' '.join(library_body)} }}", _LIBRARY)
            monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({name}))
            monkeypatch.setattr("cardlang.resolve.load_library", lambda _: library)
            uses = f"uses {name}"
        activate = f"    active_rules: [{self.activate}]\n" if self.activate else ""
        return _HOST.format(
            tag=tag, uses=uses, activate=activate,
            offers="\n".join(f"    {o}" for o in self.offers),
            game_defs="\n".join(game_defs),
        )


def _rule_text(origin: str, spelling: str | None) -> str:
    clause = f"constrains: {spelling}\n  " if spelling else ""
    if origin.endswith("template"):
        return (
            f"rule Probe(s : Suit) {{\n  {clause}demands: cards in hand where card.suit is s\n"
            f"  if_impossible: hand\n}}"
        )
    return f"rule Probe {{\n  {clause}demands: hand\n  if_impossible: hand\n}}"


def _activation(origin: str) -> str:
    return "Probe(hearts)" if origin.endswith("template") else "Probe"


_OFFERED_STREET = "procedure street() { offer to leader one of [step_offered, lib_pass] }"


def _surroundings(target: Target, when: str | None) -> Game:
    """The definitions and offers the target's move type needs, its `when:`
    set to `when`; no rule yet."""
    game = Game(rule=None, rule_in_library=False, activate=None)
    if target.declared_in is None:
        return game
    assert target.spelling is not None
    if target.declared_in == "library_offered":
        game.library_body += [
            _LIB_REQUIRES,
            _move_type(target.spelling, False, None, when, "score[actor] := 1"),
            _move_type("lib_pass", False, None),
            _OFFERED_STREET,
        ]
        game.offers += ["run street()", "run street()"]
        return game
    declaration = _move_type(target.spelling, target.params, target.stake, when)
    if target.declared_in == "library":
        game.library_body += [_LIB_REQUIRES, declaration] if when else [declaration]
        return game
    game.game_defs.append(declaration)
    if target.declared_in == "contract":
        game.library_body.append(
            f"requires {{ {target.spelling} : Move\n leader : Player }} "
            f"procedure offer_it() {{ offer to leader one of [{target.spelling}] }}"
        )
        game.offers.append("run offer_it()")
    else:
        game.offers.append(f"offer to 0 one of [{target.spelling}]")
    return game


def _refused_game(origin: str, target: Target) -> Game:
    game = _surroundings(target, None)
    game.rule = _rule_text(origin, target.spelling)
    game.rule_in_library = origin.startswith("library")
    game.activate = _activation(origin)
    return game


def _errors(exc: DiagnosticError) -> list[str]:
    notes = getattr(exc, "__notes__", [])
    lines = "\n".join(notes).splitlines() if notes else [str(exc)]
    return [line for line in lines if ": error: " in line or line.startswith("error: ")]


# --- the kernel arms: one per form, the mapping closed over KernelMoveForm ----


def _kernel_fix(form: KernelMoveForm, spelling: str) -> str | None:
    """The fix the refusal states for an undeclared kernel move type, by the
    construct that makes it; None for the enforced one, which is accepted."""
    match form:
        case "trick_round":
            return None
        case "offer":
            return (
                f"Declare `{spelling}` as a move type of the game, with the condition "
                f"in its `when:`, and offer it."
            )
        case "chosen_movement":
            return (
                "A card passed from hand to hand is a chosen movement (`move chosen N "
                "cards from ... to ...`): state the condition on the movement, its "
                "`chosen N` or a `where` filter."
            )
        case "number_choice":
            return (
                "A number a player names is a `choose integer in ...`: state the "
                f"condition in its range or its `excluding`; or declare `{spelling}` as "
                f"a move type of the game, with the condition in its `when:`, and offer it."
            )
        case "climb_round":
            return (
                "A climb round's play is legal by the round's `follows` function: when "
                "the game declares that function, state the condition there; a "
                "Registered Engine's `follows` fixes the legality, and the game cannot "
                "add to it."
            )
        case _:
            assert_never(form)


_Fix = Callable[[pytest.MonkeyPatch, str], None]
_BIG_TWO = pathlib.Path(__file__).resolve().parent.parent / "docs" / "games" / "big-two.cardlang"
_FOLLOWS_TAIL = "and strength(play) > strength(standing)\n"


def _checks_clean(game: Game) -> _Fix:
    def run(monkeypatch: pytest.MonkeyPatch, tag: str) -> None:
        pipeline._check.cache_clear()
        check_dsl(game.source(monkeypatch, tag), "fixed.cardlang")
    return run


def _big_two_follows_takes_the_condition(monkeypatch: pytest.MonkeyPatch, tag: str) -> None:
    """The climbing form's fix on a game declaring its `follows` function:
    the rule is refused there with the climb arm, and the condition written
    into `big_two_follows` checks clean."""
    source = _BIG_TWO.read_text()
    assert source.count(_FOLLOWS_TAIL) == 1
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source + f"\nrule Probe {{ constrains: {CLIMB_DECISION_MOVE_TYPE} }}\n", "b.cardlang")
    fix = _kernel_fix("climb_round", CLIMB_DECISION_MOVE_TYPE)
    assert fix is not None and [e for e in _errors(exc.value) if fix in e] == _errors(exc.value)
    pipeline._check.cache_clear()
    check_dsl(
        source.replace(
            _FOLLOWS_TAIL, _FOLLOWS_TAIL.rstrip("\n") + "\n       and (number of cards in play) < 6\n"
        ),
        "b.cardlang",
    )


def _offered_moves_after_the_condition_fails(source: str, constrained: set[str]) -> list[str]:
    """Play one line, always taking a constrained move when offered, and
    return every constrained move offered after one was taken (the stand-in
    condition, `score[actor] is 0`, fails from then on). A line that never
    takes one never tests the condition, and fails here."""
    pipeline._check.cache_clear()
    game = check_dsl(source, "played.cardlang")
    taken = False
    late: list[str] = []

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal taken
        names = [c[0] for c in candidates if isinstance(c, tuple) and c and isinstance(c[0], str)]
        if taken:
            late.extend(name for name in names if name in constrained)
        for c in candidates:
            if isinstance(c, tuple) and c and c[0] in constrained:
                taken = True
                return [c]
        return candidates[:k]

    play_game(game, random.Random(0), chooser=chooser)
    assert taken, "no constrained move was offered, so the line never tests its condition"
    return late


def _keeps_the_move_out(game: Game, constrained: set[str]) -> _Fix:
    def run(monkeypatch: pytest.MonkeyPatch, tag: str) -> None:
        assert _offered_moves_after_the_condition_fails(
            game.source(monkeypatch, tag), constrained
        ) == []
    return run


def _remedies(origin: str, target: Target) -> list[_Fix]:
    """Each fix the refusal states, applied."""
    if target.kind == "absent":
        fixed = _refused_game(origin, target)
        fixed.rule = _rule_text(origin, RULE_ENFORCED_MOVE_TYPE)
        return [_checks_clean(fixed)]
    if target.kind == "kernel":
        assert target.spelling is not None
        form = KERNEL_MOVE_FORMS[target.spelling]
        declared = Game(None, False, None, [_move_type(target.spelling, False, None, _COND)],
                        [], [f"offer to 0 one of [{target.spelling}]"])
        match form:
            case "trick_round":
                return []
            case "offer":
                return [_checks_clean(declared)]
            case "chosen_movement":
                return [_checks_clean(Game(None, False, None, offers=[
                    "as leader { move chosen one card from hand[leader] "
                    "where card.suit is hearts to captured[leader] }"
                ]))]
            case "number_choice":
                return [
                    _checks_clean(Game(None, False, None, offers=[
                        "as leader { score[leader] := choose integer in 0 .. 3 excluding 2 }"
                    ])),
                    _checks_clean(declared),
                ]
            case "climb_round":
                return [_big_two_follows_takes_the_condition]
            case _:
                assert_never(form)
    if target.kind == "declared" and target.declared_in == "library_offered":
        in_library = _surroundings(target, _COND)
        own = _surroundings(target, None)
        own.offers = ["offer to leader one of [own_move, lib_pass]"] * 2
        own.game_defs.append(_move_type("own_move", False, None, _COND, "score[actor] := 1"))
        return [
            _checks_clean(in_library),
            _keeps_the_move_out(in_library, {"step_offered"}),
            _checks_clean(own),
            _keeps_the_move_out(own, {"step_offered", "own_move"}),
        ]
    if target.kind == "declared" and target.declared_in == "library":
        in_library = _surroundings(target, _COND)
        own = _surroundings(target, None)
        own.game_defs.append(_move_type("own_move", False, None, _COND))
        own.offers.append("offer to 0 one of [own_move]")
        return [_checks_clean(in_library), _checks_clean(own)]
    if target.kind == "declared":
        return [_checks_clean(_surroundings(target, _COND))]
    return []


def _expected(target: Target) -> tuple[str, str] | None:
    """The head and the fix the one refusal carries, or None for an accepted
    rule."""
    t = target.spelling
    if target.kind == "unknown":
        return (f"constrains unknown move type '{t}'", "")
    if target.kind == "absent":
        return (
            "constrains no move type (the `constrains:` clause is absent), which no "
            "decision site consults",
            f"Name `{RULE_ENFORCED_MOVE_TYPE}` in its `constrains:`.",
        )
    if target.kind == "kernel":
        assert t is not None
        fix = _kernel_fix(KERNEL_MOVE_FORMS[t], t)
        return None if fix is None else (f"constrains '{t}', which no decision site consults", fix)
    if target.declared_in in ("library", "library_offered"):
        return (
            f"constrains `{t}`, a move type of library '",
            "A condition every game using the library shares belongs in that move "
            "type's `when:` in the library; for this game alone, offer a move type "
            f"of the game's own carrying the condition in its `when:`, in place of "
            f"`{t}`, writing the offer in the game wherever the library's own "
            "procedure makes it",
        )
    return (
        f"constrains `{t}`, a move type this game declares",
        "write the condition in its `when:` instead",
    )


CELLS = [
    pytest.param(origin, target, id=f"{origin}-{target.id}")
    for origin in ORIGINS
    for target in _targets()
]


def _tag(request: pytest.FixtureRequest, suffix: str = "") -> str:
    return "".join(ch for ch in request.node.callspec.id + suffix if ch.isalnum())


def test_every_kernel_move_type_names_the_construct_that_makes_it() -> None:
    """The kernel move types are the form table's keys, every form is one
    the refusal has an arm for, and the trick and climb forms are each the
    one move type their round asks about."""
    assert LIBRARY_MOVE_TYPES == frozenset(KERNEL_MOVE_FORMS)
    assert set(KERNEL_MOVE_FORMS.values()) <= set(KERNEL_MOVE_FORM_NAMES)
    by_form = {
        form: {k for k, f in KERNEL_MOVE_FORMS.items() if f == form} for form in KERNEL_MOVE_FORM_NAMES
    }
    assert by_form["trick_round"] == {RULE_ENFORCED_MOVE_TYPE}
    assert by_form["climb_round"] == {CLIMB_DECISION_MOVE_TYPE}
    for spelling, form in KERNEL_MOVE_FORMS.items():
        assert (_kernel_fix(form, spelling) is None) is (spelling == RULE_ENFORCED_MOVE_TYPE)


@pytest.mark.parametrize(("origin", "target"), CELLS)
def test_a_constrains_target_is_accepted_or_refused_with_its_fix(
    origin: str, target: Target, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    pipeline._check.cache_clear()
    src = _refused_game(origin, target).source(monkeypatch, _tag(request))
    expected = _expected(target)
    if expected is None:
        check_dsl(src, "grid.cardlang")
        return
    head, fix = expected
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "grid.cardlang")
    errors = _errors(exc.value)
    carrying = [e for e in errors if head in e and fix in e]
    assert len(carrying) == 1, errors
    assert errors == carrying, errors


@pytest.mark.parametrize(("origin", "target"), CELLS)
def test_each_fix_a_refusal_states_holds(
    origin: str, target: Target, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Every refused cell but an unknown spelling states a fix, and each one,
    applied, checks clean, and where a library's procedure offers the move,
    keeps it out of the offer once its condition fails.

    red under: in `resolve.resolve`, refuse a game's own move type spelled
    like a member of `LIBRARY_MOVE_TYPES` -- the offer arm's fix (declare the
    move type in the game) stops checking clean."""
    remedies = _remedies(origin, target)
    refused = _expected(target) is not None
    assert bool(remedies) is (refused and target.kind != "unknown")
    for i, remedy in enumerate(remedies):
        remedy(monkeypatch, _tag(request, f"fix{i}"))


def test_a_fix_that_leaves_the_librarys_offer_in_place_is_no_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The played gate can fail: a move type of the game's own carrying the
    condition, offered while the library's own procedure still offers the
    constrained move, leaves that move offered after its condition fails."""
    target = Target("declared", "step_offered", "library_offered")
    wrong = _surroundings(target, None)
    wrong.game_defs.append(_move_type("own_move", False, None, _COND, "score[actor] := 1"))
    wrong.offers.insert(0, "offer to leader one of [own_move, lib_pass]")
    late = _offered_moves_after_the_condition_fails(
        wrong.source(monkeypatch, "WrongFix"), {"step_offered", "own_move"}
    )
    assert "step_offered" in late, late


# Misuse probes: the sentences a designer who learned rules from a trick game
# most plausibly writes for a move made elsewhere. Each is refused, with a
# span, in the resolve or parse layer's diagnostic; where the refusal states
# a fix, the probe's game with that fix applied checks clean.
_STEP = "move_type step { effect { score[actor] := 1 } }"
_STEP_GUARDED = f"move_type step {{ when: {_COND} effect {{ score[actor] := 1 }} }}"
_RULE = "rule MandatoryCapture {{ constrains: {target}\n demands: hand\n if_impossible: hand }}"
_OFFER = "offer to 0 one of [step]"

PROBES: dict[str, tuple[Game, str, Game | None]] = {
    # a rule on a board move, the case the refusal exists for
    "rule_on_a_declared_move": (
        Game(_RULE.format(target="step"), False, None, [_STEP], [], [_OFFER]),
        "write the condition in its `when:`",
        Game(None, False, None, [_STEP_GUARDED], [], [_OFFER]),
    ),
    # the move type's name in another case
    "rule_on_a_miscased_move": (
        Game(_RULE.format(target="Step"), False, None, [_STEP], [], [_OFFER]),
        "constrains unknown move type 'Step'",
        None,
    ),
    # a function's name where a move type's belongs
    "rule_on_a_function": (
        Game(_RULE.format(target="step"), False, None, ["function step(p : Player) = true"]),
        "constrains unknown move type 'step'",
        None,
    ),
    # a list of moves
    "rule_on_a_list_of_moves": (
        Game(_RULE.format(target="[step]"), False, None, [_STEP], [], [_OFFER]),
        "syntax error",
        None,
    ),
    # the trick's move type, activated in the phase that makes the offer
    "trick_rule_active_at_an_offer": (
        Game(
            _RULE.format(target="play_to_trick"), False, None, [_STEP], [],
            ["active_rules: [MandatoryCapture]", _OFFER],
        ),
        "state the condition in the move type's `when:`",
        Game(None, False, None, [_STEP_GUARDED], [], [_OFFER]),
    ),
}


@pytest.mark.parametrize("probe", list(PROBES))
def test_a_misuse_probe_is_refused_with_a_span(
    probe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused, expected, fixed = PROBES[probe]
    tag = "".join(ch for ch in probe.title() if ch.isalnum())
    pipeline._check.cache_clear()
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(refused.source(monkeypatch, tag), "probe.cardlang")
    assert exc.value.diagnostic.span is not None
    assert any(expected in e for e in _errors(exc.value)) or expected in str(exc.value), (
        _errors(exc.value)
    )
    if fixed is not None:
        pipeline._check.cache_clear()
        check_dsl(fixed.source(monkeypatch, f"{tag}Fixed"), "fixed.cardlang")
