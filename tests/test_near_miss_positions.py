"""A Near Miss names a name that resolves where the refusal stands.

A refused name is offered the declared names it nearly spells
(tests/test_near_misses.py). The offer is advice: applied, it must not meet a
refusal at the same position. A name can classify game-wide and still be
refused where the misspelling stands -- a phase's state outside that phase, a
call-site pronoun in a function, a literal where a zone is wanted -- so the
bare-name and round `trump` refusals offer only the names every positional
Owner Guard of the resolve pass admits there, read from the one record those
guards refuse by (`cardlang.resolve._name_positions`).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        every Near Miss a refusal offers, applied in place of the
                 refused spelling, leaves no new refusal standing at that
                 position.
domain:          every slip the Near Miss census holds (`WITNESSES`,
                 `REF_KIND_WITNESSES` and `_PROBES` of
                 tests/test_near_misses.py, one per routed refusal site and
                 one per bare-name ref kind) and `POSITION_PROBES`, one per
                 positional Owner Guard of the resolve pass that judges a
                 classified bare name (`POSITIONAL_GUARDS`), crossed with
                 every Near Miss each one offers.
registry:        the census dictionaries, pinned to the routed sites by
                 tests/test_near_misses.py; the positional guards,
                 `POSITIONAL_GUARDS`, pinned equal to the functions of
                 `cardlang/resolve.py` that read a name's `ref_kind` and
                 refuse (an AST scrape).
covered:         the state live in a phase body, a game-level clause and a
                 `state { }` default; the call-site pronouns of a function and
                 a procedure body; the kind a zone slot, a write target and a
                 `to each` destination take; a bare zone family; the trick
                 winners a round's trump admits.
residual:        a Near Miss of the wrong TYPE for its position (typecheck's
                 to judge, issue #1088); the positional guards
                 `POSITIONAL_GUARDS` marks residual (issue #1089).
held by:         Derived and Pinned. One record (`_name_positions`), built
                 from the walks the guards refuse by, and one predicate per
                 guard (`_position_refuses` is their disjunction); the scrape
                 pins the guard set. Not higher: whether a guard reads a
                 name's position is a property of its body, which no union
                 states.
does not prove:  that a green offer is the name the designer meant, or that the
                 file checks clean once it is applied -- a refusal standing
                 elsewhere (a move type left unoffered, a deck a clause then
                 refuses) is outside the property. Nor that a position no
                 census slip reaches offers rightly: the domain is the
                 census's slips, not every position the grammar admits.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from tests.test_near_misses import _PROBES, REF_KIND_WITNESSES, WITNESSES, Slip

_ROOT = Path(__file__).resolve().parent.parent
_LIBRARY = "nm_probe.cardlang"


# --------------------------------------------------------------------------
# The positions: one probe per positional Owner Guard.
# --------------------------------------------------------------------------

POSITION_PROBES: dict[str, Slip] = {
    # Issue #1063's four witnesses.
    "phase-local state out of scope": Slip(
        "docs/games/bridge.cardlang", "let required = 6 + contract_level",
        "let required = 6 + cur_levl", "unresolved name 'cur_levl'", "contract_level"),
    "a call-site pronoun in a function": Slip(
        "docs/games/belote.cardlang", "is not team_of(p)", "is not team_of(actr)",
        "unresolved name 'actr'", "p"),
    "a literal where a zone is wanted": Slip(
        "docs/games/hearts.cardlang", "move all cards to deck", "move all cards to tru",
        "unresolved name 'tru'", "deck"),
    "a round's trump": Slip(
        "docs/games/bridge.cardlang", "trump trump_suit", "trump cur_levl",
        "`trump` names 'cur_levl'", "trump_suit"),
    # The other positions.
    "a default reads state not yet declared": Slip(
        "docs/games/bridge.cardlang", "doubled_mult      : Integer = 1",
        "doubled_mult      : Integer = cur_levl", "unresolved name 'cur_levl'", "contract_level"),
    "a bare zone family": Slip(
        "docs/games/bridge.cardlang", "      move all cards to deck\n",
        "      move all cards to captued\n", "unresolved name 'captued'", "deck"),
    "a call-site pronoun in a procedure": Slip(
        "docs/games/cheat.cardlang", "  responder := who\n", "  responder := actr\n",
        "unresolved name 'actr'", "who"),
    "a write target spelled near a zone": Slip(
        "docs/games/hearts.cardlang", "        leader := winner", "        hnad := winner",
        "unresolved name 'hnad'", "leader"),
    "a `to each` destination": Slip(
        "docs/games/hearts.cardlang", "deal 13 cards from deck to each hand",
        "deal 13 cards from deck to each hnad", "unresolved name 'hnad'", "hand"),
}

# The refused spelling, where the slip's own edit does not show it alone.
SPELLED: dict[str, str] = {
    "resolve::_resolve_ranking::ranking: names unknown rank '{}' — not a rank of deck '{}' (": "aces hgih",
    "resolve::_check_template::rule parameter '{}: {}' has an unsupported domain — rule par": "Siut",
    "a ranking convention misspelled": "Aces Hihg",
}

# The cells whose offers a guard outside the record refuses, by the issue that
# holds them.
RESIDUAL: dict[str, str] = {
    "a call-site pronoun in a function": "the state `acted` and the seat direction `across` are not Players (issue #1088)",
    "a call-site pronoun in a procedure": "the seat direction `across` is not a Player (issue #1088)",
    "a round's trump": "`contract_level` is an Integer, not a Suit? (issue #1088)",
    "bool": "`captured` is cards, not a condition (issue #1088)",
}

_CELLS: dict[str, Slip] = {**WITNESSES, **{str(k): v for k, v in REF_KIND_WITNESSES.items()},
                           **{k: v for k, (v, _offered) in _PROBES.items()}, **POSITION_PROBES}


# --------------------------------------------------------------------------
# The oracle: apply each offer, and look for a refusal at the position.
# --------------------------------------------------------------------------

_TOKEN = re.compile(r'"[^"]*"|[A-Za-z_][A-Za-z_0-9]*|\d+')
_LOCATED = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): error: (?P<message>.*)$")


@dataclass(frozen=True)
class _Planted:
    text: str  # the source with the slip and every edit around it
    at: int  # where the slip's new text starts
    new: str  # the slip's new text


def _base(slip: Slip) -> str:
    if slip.source.startswith("library:"):
        return slip.source.removeprefix("library:")
    text = (_ROOT / slip.source).read_text()
    for before, after in slip.also:
        assert before in text, f"{slip.source} no longer holds {before!r}: re-plant this slip"
        text = text.replace(before, after, 1)
    return text


def _plant(slip: Slip, new: str) -> _Planted:
    text = _base(slip)
    assert slip.old in text, f"{slip.source} no longer holds {slip.old!r}: re-plant this slip"
    at = text.index(slip.old)
    return _Planted(text[:at] + new + text[at + len(slip.old):], at, new)


def _errors(slip: Slip, text: str) -> list[str]:
    """Every error line `text` renders, in report order, each once."""
    if slip.source.startswith("library:"):
        from cardlang.resolve import check_library_alone

        bag = DiagnosticBag()
        check_library_alone(parse_library(text, _LIBRARY), bag)
        return [line for d in bag.items for line in d.format().splitlines() if ": error: " in line]
    try:
        check_dsl(text, slip.source)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", [])
        rendered = notes[0] if notes else exc.diagnostic.format()
        return [line for line in rendered.splitlines() if ": error: " in line]
    return []


def _offers(line: str) -> list[str]:
    if "; did you mean " not in line:
        return []
    return re.findall(r"`([^`]*)`", line.rsplit("; did you mean ", 1)[1])


def _spelled(key: str, slip: Slip) -> str:
    if key in SPELLED:
        return SPELLED[key]
    old: set[str] = set(_TOKEN.findall(slip.old))
    fresh: list[str] = [tok for tok in _TOKEN.findall(slip.new) if tok not in old]
    assert len(fresh) == 1, f"{key}: name the refused spelling in SPELLED (fresh tokens {fresh})"
    return fresh[0]


def _applied(key: str, slip: Slip, offer: str) -> _Planted:
    """The slip with `offer` written for the refused spelling. An offer that
    is the designer's own spelling names their declaration a library row
    asks for, so applying it is renaming that declaration back."""
    spelled = _spelled(key, slip)
    if offer == spelled:
        return _plant(slip, slip.old)
    if spelled in slip.new:
        return _plant(slip, slip.new.replace(spelled, offer, 1))
    also = tuple((b, a.replace(spelled, offer, 1)) for b, a in slip.also)
    assert also != slip.also, f"{key}: the refused spelling {spelled!r} is in no edit"
    return _plant(Slip(slip.source, slip.old, slip.new, slip.marker, slip.meant, also), slip.new)


# How many lines before the slip a statement holding it may begin: a refusal
# of the statement stands at its first line.
_STATEMENT_LEAD = 3


def _lines_of(planted: _Planted) -> range:
    """The slip's lines, and the lines before it a statement it continues may
    begin on."""
    first = planted.text.count("\n", 0, planted.at) + 1
    return range(first - _STATEMENT_LEAD, first + planted.new.count("\n") + 1)


def _refused_at_the_position(key: str) -> list[str]:
    """Every offer the cell's refusal makes that, applied, meets a refusal at
    the slip's lines that the unslipped source does not."""
    slip = _CELLS[key]
    slipped = _plant(slip, slip.new)
    hits = [line for line in _errors(slip, slipped.text) if slip.marker in line]
    assert hits, f"no refusal names {slip.marker!r}: the slip no longer reaches its site"
    baseline = set(_errors(slip, _base(slip)))
    found: list[str] = []
    for offer in _offers(hits[0]):
        planted = _applied(key, slip, offer)
        lines = _lines_of(planted)
        for line in _errors(slip, planted.text):
            located = _LOCATED.match(line)
            if line in baseline or located is None:
                continue
            if int(located["line"]) in lines:
                found.append(f"`{offer}`: {line}")
    return found


def _cell(key: str) -> object:
    marks = [pytest.mark.xfail(strict=True, reason=RESIDUAL[key])] if key in RESIDUAL else []
    return pytest.param(key, id=key, marks=marks)


@pytest.mark.parametrize("key", [_cell(key) for key in sorted(_CELLS)])
def test_an_offered_name_is_admitted_where_it_is_offered(key: str) -> None:
    assert _refused_at_the_position(key) == []


def test_the_residual_names_cells() -> None:
    assert set(RESIDUAL) <= set(_CELLS)


# --------------------------------------------------------------------------
# Every position probe, by its whole offer.
# --------------------------------------------------------------------------

OFFERED: dict[str, list[str]] = {
    "phase-local state out of scope": ["contract_level"],
    "a call-site pronoun in a function": ["acted", "across"],
    "a literal where a zone is wanted": [],
    "a round's trump": ["contract_level"],
    "a default reads state not yet declared": ["contract_level"],
    "a bare zone family": [],
    "a call-site pronoun in a procedure": ["across"],
    "a write target spelled near a zone": [],
    "a `to each` destination": ["hand"],
}


def _offer(key: str) -> list[str]:
    slip = _CELLS[key]
    hits = [line for line in _errors(slip, _plant(slip, slip.new).text) if slip.marker in line]
    assert hits, hits
    return _offers(hits[0])


@pytest.mark.parametrize("key", sorted(OFFERED))
def test_a_position_probe_is_offered_only_what_resolves_there(key: str) -> None:
    assert _offer(key) == OFFERED[key]


def test_every_position_probe_states_its_offer() -> None:
    assert set(OFFERED) == set(POSITION_PROBES)


# --------------------------------------------------------------------------
# The positional guards: every resolve function that judges a classified
# name, joined to the record or held as residual.
# --------------------------------------------------------------------------

POSITIONAL_GUARDS: dict[str, str] = {
    # Joined: the guard refuses by a predicate `_position_refuses` reads.
    "_check_state_scope": "joined",
    "_check_state_default_scope": "joined",
    "_check_functions": "joined",
    "_check_procedures": "joined",
    "_check_bare_family_refs": "joined",
    # The zone slots and write targets (`_bad_zone_endpoint`,
    # `_bad_write_target`), and the `to each` destination.
    "_validate_refs": "joined",
    # Residual: the guard judges a position the record does not hold yet.
    "_check_answer_hermeticity": "residual (issue #1089)",
    "_check_play_source": "residual (issue #1089)",
    "_check_arrival_record_pile_args": "residual (issue #1089)",
    "_check_hosted_node": "residual (issue #1089)",
    "_check_alias_operands": "residual (issue #1089)",
    "_HiddenReads": "residual (issue #1089)",
    # Not a positional guard: it classifies, and refuses a name that
    # classifies as nothing.
    "_rewrite": "the classifier itself",
}


def _guards_reading_ref_kind() -> set[str]:
    """Every top-level function or class of `cardlang/resolve.py` that reads
    a name's `ref_kind` and refuses."""
    tree = ast.parse((_ROOT / "cardlang/resolve.py").read_text())
    found: set[str] = set()
    for top in tree.body:
        if not isinstance(top, ast.FunctionDef | ast.ClassDef):
            continue
        reads = any(isinstance(nd, ast.Attribute) and nd.attr == "ref_kind" for nd in ast.walk(top))
        refuses = any(
            isinstance(nd, ast.Call) and isinstance(nd.func, ast.Attribute)
            and nd.func.attr in ("error", "unknown", "_tell", "_emit")
            for nd in ast.walk(top)
        )
        if reads and refuses:
            found.add(top.name)
    return found


def test_every_guard_judging_a_classified_name_is_accounted_for() -> None:
    """red under: a function in `cardlang/resolve.py` that reads `ref_kind`
    and refuses, added without a row here."""
    assert _guards_reading_ref_kind() == set(POSITIONAL_GUARDS)


def _unclassified(value: object) -> object:
    """`value` with every name's classification taken off."""
    from dataclasses import fields, is_dataclass, replace

    from cardlang.ast import nodes as n
    from cardlang.diagnostics import Span

    if isinstance(value, n.NameRef):
        return replace(value, ref_kind=None)
    if isinstance(value, tuple):
        return tuple(_unclassified(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type | Span):
        return replace(value, **{f.name: _unclassified(getattr(value, f.name)) for f in fields(value) if f.init})
    return value


def test_the_record_reads_no_classification() -> None:
    """The record over a tree before classification is the record over it
    after, so the ranking and the guards read the same facts. red under:
    `_name_positions` keying a fact on a name's `ref_kind` (`slot=` recorded
    only for a classified name)."""
    from cardlang import resolve
    from cardlang.ast import nodes as n

    for path in sorted((_ROOT / "docs/games").glob("*.cardlang")):
        game = check_dsl(path.read_text(), str(path))
        bare = _unclassified(game)
        assert isinstance(bare, n.Game)
        after = resolve._name_positions(game)
        before = resolve._name_positions(bare)
        classified = [after[id(x)] for x in resolve._walk(game) if isinstance(x, n.NameRef)]
        unclassified = [before[id(x)] for x in resolve._walk(bare) if isinstance(x, n.NameRef)]
        assert classified == unclassified, path.name
