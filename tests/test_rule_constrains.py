"""What a rule's `constrains:` may name, and what a designer is told when it
names a move no rule can bind.

A rule binds at the trick round's card decision and nowhere else
(decisions.md "Rule demand forms"), so of every spelling `constrains:` can
hold exactly one is accepted -- the move type that decision asks about. Every
other spelling is refused with the fix in designer words: a move type the game
declares is told to write the condition in that move type's `when:`; a kernel
move type the game does not declare is told no decision site consults it; a
spelling no declaration holds is unknown.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a `constrains:` naming `RULE_ENFORCED_MOVE_TYPE` is accepted;
                 every other target is refused once, in the resolve layer,
                 with the remedy its target class calls for.
domain:          the `constrains:` target crossed with the rule's origin. The
                 target axis: the clause absent; every kernel move type,
                 undeclared; every kernel move type but the enforced one,
                 declared by the game under the kernel's spelling; a move
                 type of the game's own, crossed with its parameters (none,
                 one) and its stake (none and every member of `n.STAKES`) and
                 with where it is declared (the game, a family library the
                 game uses); a spelling nothing declares. The origin axis:
                 a game's rule, a game's template instantiated, a family
                 library's rule, a family library's template instantiated.
                 A template parameter never reaches the target, which the
                 grammar holds as a bare name, not an expression. A game
                 move type spelled `play_to_trick` is issue #1010; a
                 family library rule no game activates is issue
                 #1011; a repeated `constrains:` clause is issue #173.
registry:        kernel move types: `cardlang.stdlib.moves.LIBRARY_MOVE_TYPES`;
                 the enforced one: `cardlang.stdlib.moves.RULE_ENFORCED_MOVE_TYPE`;
                 stakes: `cardlang.ast.nodes.STAKES`; the one-site law the
                 refusal rests on: tests/test_rule_sites.py::test_the_rule_cascade_has_one_caller.
held by:         Derived and Pinned. A target is a string the grammar reads as
                 a bare name and the resolver classifies against the game's
                 declarations; no type can hold which names a game declares.
does not prove:  that an accepted rule fires: that is `active_rules:`'s
                 reach (tests/rejections/rules_where_no_trick_round_runs.cardlang)
                 and the cascade's own behaviour (tests/test_legal_cards.py).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import pytest

import cardlang.pipeline as pipeline
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES, RULE_ENFORCED_MOVE_TYPE

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
    active_rules: [{activate}]
    legal_moves:  [play_to_trick]
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
    declaration it needs (None when nothing declares it)."""

    kind: str  # "absent" | "kernel" | "declared" | "unknown"
    spelling: str | None
    declaration: str | None = None
    in_library: bool = False

    @property
    def id(self) -> str:
        where = "lib" if self.in_library else "game"
        return f"{self.kind}-{self.spelling}-{where}" if self.declaration else f"{self.kind}-{self.spelling}"


def _move_type(name: str, params: bool, stake: n.Stake | None) -> str:
    sig = f"{name}(s : Suit)" if params else name
    row = f"{stake} " if stake else ""
    return f"move_type {sig} {{ {row}effect {{ }} }}"


def _targets() -> Iterator[Target]:
    yield Target("absent", None)
    for kernel in sorted(LIBRARY_MOVE_TYPES):
        yield Target("kernel", kernel)
    for kernel in sorted(LIBRARY_MOVE_TYPES - {RULE_ENFORCED_MOVE_TYPE}):
        yield Target("declared", kernel, _move_type(kernel, False, None))
    for in_library in (False, True):
        for params in (False, True):
            for stake in (None, *n.STAKES):
                name = f"step_{'p' if params else 'n'}_{stake or 'plain'}"
                yield Target("declared", name, _move_type(name, params, stake), in_library)
    yield Target("unknown", "nonesuch_move")


ORIGINS = ("game_rule", "game_template", "library_rule", "library_template")


def _rule_text(origin: str, target: Target) -> str:
    clause = f"constrains: {target.spelling}\n  " if target.spelling else ""
    if origin.endswith("template"):
        return (
            f"rule Probe(s : Suit) {{\n  {clause}demands: cards in hand where card.suit is s\n"
            f"  if_impossible: hand\n}}"
        )
    return f"rule Probe {{\n  {clause}demands: hand\n  if_impossible: hand\n}}"


def _source(origin: str, target: Target, monkeypatch: pytest.MonkeyPatch, tag: str) -> str:
    rule = _rule_text(origin, target)
    library_body: list[str] = []
    game_defs: list[str] = []
    (library_body if origin.startswith("library") else game_defs).append(rule)
    offers = ""
    if target.declaration is not None:
        (library_body if target.in_library else game_defs).append(target.declaration)
        if not target.in_library:
            offers = f"    offer to 0 one of [{target.spelling}]"
    uses = ""
    if library_body:
        name = f"lib_{tag}"
        library = parse_library(f"library {name} {{ {' '.join(library_body)} }}", _LIBRARY)
        monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({name}))
        monkeypatch.setattr("cardlang.resolve.load_library", lambda _: library)
        uses = f"uses {name}"
    activate = "Probe(hearts)" if origin.endswith("template") else "Probe"
    return _HOST.format(
        tag=tag, uses=uses, offers=offers, activate=activate, game_defs="\n".join(game_defs)
    )


def _errors(exc: DiagnosticError) -> list[str]:
    notes = getattr(exc, "__notes__", [])
    lines = "\n".join(notes).splitlines() if notes else [str(exc)]
    return [line for line in lines if ": error: " in line or line.startswith("error: ")]


def _expected(target: Target) -> str | None:
    """The phrase the one refusal carries, or None for an accepted rule."""
    if target.kind == "unknown":
        return f"constrains unknown move type '{target.spelling}'"
    if target.spelling == RULE_ENFORCED_MOVE_TYPE and target.declaration is None:
        return None
    if target.kind == "declared":
        return f"write the condition in `{target.spelling}`'s `when:`"
    return (
        "state the constraint where the move is made: a movement's `chosen N`, "
        "or the move type's `when:`"
    )


# The cells whose refusal this change rewords or reroutes; the marks come
# off with the implementation.
_DESIGNED_RED = {"absent", "kernel", "declared"}

CELLS = [
    pytest.param(
        origin,
        target,
        id=f"{origin}-{target.id}",
        marks=(
            [pytest.mark.xfail(strict=True, raises=AssertionError, reason="refusal rewritten")]
            if target.kind in _DESIGNED_RED and _expected(target) is not None
            else []
        ),
    )
    for origin in ORIGINS
    for target in _targets()
]


@pytest.mark.parametrize(("origin", "target"), CELLS)
def test_a_constrains_target_is_accepted_or_refused_with_its_remedy(
    origin: str, target: Target, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    pipeline._check.cache_clear()
    tag = "".join(ch for ch in request.node.callspec.id if ch.isalnum())
    src = _source(origin, target, monkeypatch, tag)
    expected = _expected(target)
    if expected is None:
        check_dsl(src, "grid.cardlang")
        return
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "grid.cardlang")
    errors = _errors(exc.value)
    carrying = [e for e in errors if expected in e]
    assert len(carrying) == 1, errors
    rule_errors = [e for e in errors if "rule " in e and "Probe" in e]
    assert rule_errors == carrying, errors


# Misuse probes: the sentences a designer who learned rules from a trick game
# most plausibly writes for a move made elsewhere. Each is refused, with a
# span, in the resolve or parse layer's diagnostic.
_PROBE_HOST = _HOST.replace("active_rules: [{activate}]\n", "")

PROBES = {
    # a rule on a board move, the case the refusal exists for
    "rule_on_a_declared_move": (
        "move_type step { effect { score[actor] := 1 } }\n"
        "rule MandatoryCapture { constrains: step\n demands: hand\n if_impossible: hand }",
        "    offer to 0 one of [step]",
        "write the condition in `step`'s `when:`",
    ),
    # the move type's name in another case
    "rule_on_a_miscased_move": (
        "move_type step { effect { score[actor] := 1 } }\n"
        "rule MandatoryCapture { constrains: Step\n demands: hand\n if_impossible: hand }",
        "    offer to 0 one of [step]",
        "constrains unknown move type 'Step'",
    ),
    # a function's name where a move type's belongs
    "rule_on_a_function": (
        "function step(p : Player) = true\n"
        "rule MandatoryCapture { constrains: step\n demands: hand\n if_impossible: hand }",
        "",
        "constrains unknown move type 'step'",
    ),
    # a list of moves
    "rule_on_a_list_of_moves": (
        "move_type step { effect { score[actor] := 1 } }\n"
        "rule MandatoryCapture { constrains: [step]\n demands: hand\n if_impossible: hand }",
        "    offer to 0 one of [step]",
        "syntax error",
    ),
    # the trick's move type, activated in the phase that makes the offer
    "trick_rule_active_at_an_offer": (
        "move_type step { effect { score[actor] := 1 } }\n"
        "rule MandatoryCapture { constrains: play_to_trick\n demands: hand\n if_impossible: hand }",
        "    active_rules: [MandatoryCapture]\n    offer to 0 one of [step]",
        "state the condition in the move type's `when:`",
    ),
}


@pytest.mark.parametrize(
    "probe",
    [
        pytest.param(
            key,
            marks=(
                [pytest.mark.xfail(strict=True, raises=AssertionError, reason="refusal rewritten")]
                if key in {"rule_on_a_declared_move", "trick_rule_active_at_an_offer"}
                else []
            ),
        )
        for key in PROBES
    ],
)
def test_a_misuse_probe_is_refused_with_a_span(probe: str) -> None:
    pipeline._check.cache_clear()
    game_defs, offers, expected = PROBES[probe]
    src = _PROBE_HOST.format(
        tag="".join(ch for ch in probe.title() if ch.isalnum()),
        uses="", offers=offers, activate="", game_defs=game_defs,
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "probe.cardlang")
    assert exc.value.diagnostic.span is not None
    assert any(expected in e for e in _errors(exc.value)) or expected in str(exc.value), (
        _errors(exc.value)
    )
