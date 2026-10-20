"""A family library may not name a Primitive in a round slot.

property:   a round written in family-library text names in each query slot
            what the same round written in the game may name, less the
            Primitives. A Primitive the slot accepts is refused to the
            library's author, in the library file, with the call position's
            rule and a fix that checks clean: the round written in the game.
            Every other name meets the verdict the game-written round meets:
            a Builtin is accepted, a name the slot does not accept earns the
            slot's own refusal at the library's span, and a name a game
            clause decides is refused on the importer's `uses` line. A
            Primitive's refusal stands alone: no game-clause gate judges a
            round the library may not hold. No other
            reference namespace a library reaches admits a Primitive, so
            these slots and the call position are the whole class.
domain:     query slot x name. The slot axis is every `_REFERENCE_SLOTS` row
            whose namespace is `primitive_query`. The name axis is every
            member of every `WALLED_NAMESPACES` set, every trick-winner name
            (`VALUE_NAMES`), the alphabetically first call-position Primitive
            (`PRIMITIVE_CALL_FUNCS`) and a name nothing declares. Each cell
            runs twice through `check_dsl`: the round in a move type the GAME
            defines -- the oracle, and the fix the refusal names -- and the
            same round in a move type a LIBRARY defines, which the game
            offers. The expected column is the oracle's verdict plus the
            Primitive rule, so the grid reads each slot's registry by
            execution rather than restating it; each host declares the
            clauses every query its slots accept reads (Big Two's own
            `ranking: twos high`), so the oracle's clean verdict is the
            slot's. Only `winner` holds names a library may write: every
            climb query and every early-termination predicate is a
            Primitive, so a family library holds no climbing round and no
            `early` clause, and every climb cell carries its mandatory
            sibling slot's refusal beside its own verdict. An empty walled
            namespace contributes no Primitive cell, and a member added to
            one joins the grid through the name axis. The class pin crosses
            the library-legal set of every swept namespace, and the table of
            every `closed:` row of `_LIBRARY_UNSWEPT`, with the Primitives.
            The misuse probes run the routes and neighbours a designer
            reaches for: a library procedure holding the round, Getaway's
            own trick as a library, and importers whose clauses a game-clause
            gate on climb queries reads (a `trick_order { }` block, no
            `ranking:`).
registry:   slots: `cardlang.resolve._REFERENCE_SLOTS`; each slot's accepted
            names: `cardlang.resolve._ROUND_QUERY_REGISTRIES`; Primitives:
            `cardlang.builtins.functions.PRIMITIVE_CALL_FUNCS`,
            `cardlang.primitives_block.WALLED_NAMESPACES`; what a library may
            name per namespace: `cardlang.resolve._library_slot_names`,
            `cardlang.resolve._LIBRARY_UNSWEPT`; the call position:
            tests/test_library_reach_wording.py.
does not prove:  that the game-written verdict is right -- it is the
            oracle, owned by `_validate_refs`. Nor, for a climb cell whose
            own name its slot refuses, that refusal from library text: the
            sibling's Primitive refusal stops resolve first, so the cell pins
            that refusal alone. Nor that the namespaces `_LIBRARY_UNSWEPT`
            holds as guarded elsewhere or designed name no Primitive: their
            names come from the importing game's own declarations, which the
            class pin does not read. Nor the wording of a game-clause refusal
            a cell meets on the importer's `uses` line: the cell checks that
            it names the library and the name, and
            tests/test_library_clause_gates.py holds the rest.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from cardlang import pipeline
from cardlang.ast import nodes as n
from cardlang.attribution import is_library_warning
from cardlang.builtins.functions import PRIMITIVE_CALL_FUNCS, TRUMP_READING_WINNERS, VALUE_NAMES
from cardlang.diagnostics import DiagnosticError, line_kind
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import WALLED_NAMESPACES
from cardlang.resolve import _LIBRARY_UNSWEPT, _REFERENCE_SLOTS, _library_slot_names
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.stdlib.round_state import ROUND_STATE_FIELDS

_LIB = "probelib"
_LIBRARY_FILE = f"docs/libraries/{_LIB}.cardlang"
_GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"

_PRIMITIVES = frozenset(PRIMITIVE_CALL_FUNCS).union(*WALLED_NAMESPACES.values())

# The slot axis, from the registry.
_SLOTS: tuple[tuple[type, str], ...] = tuple(
    slot for slot, namespace in _REFERENCE_SLOTS.items() if namespace == "primitive_query"
)

_UNKNOWN = "frobnicate"

# The name axis: a superset of every slot's accepted names, so the oracle
# decides each slot's registry rather than this file.
_NAMES: tuple[str, ...] = tuple(
    sorted(
        frozenset(VALUE_NAMES).union(*WALLED_NAMESPACES.values())
        | {min(PRIMITIVE_CALL_FUNCS), _UNKNOWN}
    )
)


# --- the two hosts -----------------------------------------------------------
#
# Each corpus game's own round statement, lifted into a move type the phase
# offers instead: once into a move type the game defines, once into one a
# library defines.


class _Host:
    def __init__(
        self,
        game: str,
        anchor: str,
        discard: str,
        defaults: dict[str, str | None],
        round_text: str,
        *,
        clauses: str = "",
        after: str = "",
    ) -> None:
        self.clauses = clauses
        self.after = after
        self.game = game
        self.anchor = anchor
        self.discard = discard
        self.defaults = defaults
        self.round_text = round_text

    def round(self, fills: dict[str, str | None]) -> str:
        early = fills.get("early_termination")
        text = self.round_text.format(
            **{k: v for k, v in fills.items() if k != "early_termination"},
            early="" if early is None else f" early {early}",
        )
        # A winner reading a trump states it on the round, so the cell's
        # verdict is the slot's and not the unstated-trump refusal.
        if fills.get("winner_fn") in TRUMP_READING_WINNERS:
            text += " trump none"
        return text

    def game_text(self, *, uses: bool, game_local_round: str | None) -> str:
        text = (_GAMES / self.game).read_text()
        assert text.count(self.anchor) == 1, f"the probe's anchor moved in {self.game}"
        text = text.replace(self.anchor, f"    offer to leader one of [start_trick]\n{self.after}")
        if self.clauses:
            text = text.replace("  cards: standard52\n", f"  cards: standard52\n{self.clauses}", 1)
        if uses:
            text = text.replace("  players: 4", f"  uses {_LIB}\n  players: 4", 1)
        if game_local_round is not None:
            text += (
                "\nmove_type start_trick {\n  effect {\n"
                f"    {game_local_round}\n"
                f"    move all cards from trick_pile to {self.discard}\n"
                "    leader := winner\n  }\n}\n"
            )
        return text

    def library_text(self, round_text: str) -> str:
        return (
            f"library {_LIB} {{\n"
            f"  requires {{ hand[player] : Hand<player>  trick_pile : TrickPile  "
            f"{self.discard} : Discard }}\n"
            f"  move_type start_trick {{\n    effect {{\n      {round_text}\n"
            f"      move all cards from trick_pile to {self.discard}\n    }}\n  }}\n}}\n"
        )


_CLIMB = _Host(
    "big-two.cardlang",
    """        round climb play_combination from leader
              over players where hand[player] is not empty
              source hand into trick_pile
              combinations bigtwo_lead_options follows bigtwo_follows
              until (any player where hand[player] is empty)
        opened := true
        move all cards from trick_pile to discard
        leader := winner
""",
    "discard",
    {"combos_fn": "bigtwo_lead_options", "follows_fn": "bigtwo_follows"},
    "round climb play_combination from actor over players where hand[player] "
    "is not empty source hand into trick_pile combinations {combos_fn} "
    "follows {follows_fn} until (any player where hand[player] is empty)",
    # Big Two's own rank order, declared so that every climb query the slot
    # accepts is admitted by the host's clauses: the oracle's verdict is then
    # the slot's, not the `ranking:` gate's.
    clauses="  ranking: twos high\n",
    after="    opened := true\n",
)
_TRICK = _Host(
    "getaway.cardlang",
    """    round play_to_trick from leader over all players source hand into trick_pile
          winner highest_of_led_suit early on_play_off_led_suit
    move all cards from trick_pile to waste
    leader := winner
""",
    "waste",
    {"winner_fn": "highest_of_led_suit", "early_termination": None},
    "round play_to_trick from actor over all players source hand into trick_pile "
    "winner {winner_fn}{early}",
)
_HOSTS: dict[type, _Host] = {n.ClimbRound: _CLIMB, n.TrickRound: _TRICK}


def _fields_of(form: type) -> list[str]:
    """The form's query slots, in the order the registry walks them."""
    return [field for cls, field in _SLOTS if cls is form]


# --- running a cell ----------------------------------------------------------

_LOCATED = re.compile(r"^(?:(?P<source>[^:]+):\d+:\d+: )?error: (?P<message>.*)$")


def _diagnostics(text: str, name: str) -> list[tuple[str | None, str]]:
    """Every error `check_dsl` reports, as (source file, message). The memo is
    keyed on the game alone while the library is a module global, so it is
    cleared before every run."""
    pipeline._check.cache_clear()
    try:
        check_dsl(text, name)
    except DiagnosticError as exc:
        notes = getattr(exc, "__notes__", [])
        if not notes:
            d = exc.diagnostic
            return [(d.span.source_name if d.span else None, d.message)]
        out = []
        for line in "\n".join(notes).splitlines():
            if is_library_warning(line) or line_kind(line) == "note":
                continue
            match = _LOCATED.match(line)
            assert match is not None, line
            out.append((match["source"], match["message"]))
        return out
    return []


def _patch(monkeypatch: pytest.MonkeyPatch, library_text: str) -> None:
    library = parse_library(library_text, _LIBRARY_FILE)
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({_LIB}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: library)


def _fills(slot: tuple[type, str], name: str) -> dict[str, str | None]:
    form, field = slot
    return {**_HOSTS[form].defaults, field: name}


def _game_written(slot: tuple[type, str], name: str) -> list[tuple[str | None, str]]:
    host = _HOSTS[slot[0]]
    text = host.game_text(uses=False, game_local_round=host.round(_fills(slot, name)))
    return _diagnostics(text, host.game)


def _library_reached(
    slot: tuple[type, str], name: str, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[str | None, str]]:
    host = _HOSTS[slot[0]]
    _patch(monkeypatch, host.library_text(host.round(_fills(slot, name))))
    return _diagnostics(host.game_text(uses=True, game_local_round=None), host.game)


def _primitive_rule(name: str) -> str:
    return (
        f"library '{_LIB}' names '{name}', which is a Primitive — a Primitive "
        f"belongs to the one game that declares it, so a library that several "
        f"games import may not name one: a round slot takes a name, never a "
        f"value, so the game cannot pass this one in — write the round in the "
        f"game, in a phase or in a move type the game defines"
    )


def _cells() -> Iterator[object]:
    for slot in _SLOTS:
        for name in _NAMES:
            yield pytest.param(slot, name, id=f"{slot[0].__name__}.{slot[1]}|{name}")


# --- the grid ----------------------------------------------------------------


@pytest.mark.parametrize("slot,name", list(_cells()))
def test_a_library_round_slot_names_what_the_game_may_name_less_the_primitives(
    slot: tuple[type, str], name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    form, field = slot
    oracle = _game_written(slot, name)
    accepted = not oracle
    fills = _fills(slot, name)
    # The Primitives the library's round names where the game's own round
    # accepts them -- the cell's own slot, and a climb round's mandatory
    # sibling -- in the order the registry walks the slots.
    refused = [
        _primitive_rule(fill)
        for f in _fields_of(form)
        if (fill := fills[f]) is not None
        and fill in _PRIMITIVES
        and (accepted or f != field)
    ]
    got = _library_reached(slot, name, monkeypatch)
    if refused:
        assert [message for _, message in got] == refused
        assert {source for source, _ in got} == {_LIBRARY_FILE}
    else:
        # The game-written verdict: a name the slot does not accept earns the
        # slot's own refusal at the library's span, and a name a game clause
        # decides is the importer's, on its `uses` line, naming the library
        # (tests/test_library_clause_gates.py owns that wording).
        assert bool(got) == bool(oracle)
        in_library = [message for source, message in got if source == _LIBRARY_FILE]
        in_game = [message for source, message in got if source != _LIBRARY_FILE]
        if in_library:
            assert in_library == [message for _, message in oracle] and not in_game
        else:
            assert all(m.startswith(f"library '{_LIB}' ") and name in m for m in in_game)


@pytest.mark.parametrize("form", [pytest.param(f, id=f.__name__) for f in _HOSTS])
def test_the_hosts_round_as_the_game_writes_it_checks_clean(form: type) -> None:
    """The control: each host with its corpus round moved into a move type the
    game defines -- the fix the refusal names -- is clean, so a cell's sibling
    slots are accepted and every refusal is its own name's."""
    host = _HOSTS[form]
    assert _diagnostics(
        host.game_text(uses=False, game_local_round=host.round(host.defaults)), host.game
    ) == []


def test_the_slot_axis_is_every_round_query_slot() -> None:
    """The hosts, the defaults and `_ROUND_QUERY_REGISTRIES` all cover exactly
    the registry's `primitive_query` slots, and every name a slot accepts is on
    the name axis. red under: add a `primitive_query` row to
    `_REFERENCE_SLOTS`, or a name to a round-query registry outside
    `VALUE_NAMES` and `WALLED_NAMESPACES`."""
    from cardlang.resolve import _ROUND_QUERY_REGISTRIES

    assert set(_ROUND_QUERY_REGISTRIES) == set(_SLOTS)
    assert {(form, f) for form, host in _HOSTS.items() for f in host.defaults} == set(_SLOTS)
    assert frozenset().union(*_ROUND_QUERY_REGISTRIES.values()) <= set(_NAMES)


# The `closed:` rows of `_LIBRARY_UNSWEPT`, each with the table that closes it.
_CLOSED_TABLES: dict[str, frozenset[str]] = {
    "kernel_move_type": frozenset(LIBRARY_MOVE_TYPES),
    "round_state": frozenset(ROUND_STATE_FIELDS),
}


def test_no_other_namespace_a_library_reaches_admits_a_primitive() -> None:
    """The class: every namespace a library sweep holds names no Primitive,
    and neither does any closed table a library names unswept. So the round
    query slots, and the call position whose `function` namespace is
    `BUILTIN_CALL_FUNCS`, are where library text meets a Primitive. red under:
    add a Primitive to any `_library_slot_names` set, or a `closed:` row to
    `_LIBRARY_UNSWEPT`."""
    swept = _library_slot_names(n.Library(name="none"))
    admitted = {ns: names & _PRIMITIVES for ns, names in swept.items() if names & _PRIMITIVES}
    assert not admitted, admitted
    closed = {ns for ns, reason in _LIBRARY_UNSWEPT.items() if reason.startswith("closed:")}
    assert closed == set(_CLOSED_TABLES)
    assert not any(table & _PRIMITIVES for table in _CLOSED_TABLES.values())
    assert _LIBRARY_UNSWEPT["primitive_query"].startswith("guarded elsewhere:")


# --- misuse probes -----------------------------------------------------------


def test_a_library_procedure_holding_the_round_is_told_the_primitive_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other route a designer reaches for: the round in a library
    procedure the game runs. A procedure holds no round in a game either, so
    the library's own fault is reported first and alone, and the fix it names
    -- the round in a game phase -- is the corpus game itself."""
    host = _CLIMB
    _patch(
        monkeypatch,
        f"library {_LIB} {{\n  requires {{ hand[player] : Hand<player>  "
        f"trick_pile : TrickPile  discard : Discard }}\n"
        f"  procedure climb_once() {{\n    {host.round(host.defaults)}\n"
        f"    move all cards from trick_pile to discard\n  }}\n}}\n",
    )
    text = host.game_text(uses=True, game_local_round=None).replace(
        "    offer to leader one of [start_trick]\n", "    run climb_once()\n"
    )
    assert _diagnostics(text, host.game) == [
        (_LIBRARY_FILE, _primitive_rule(name)) for name in host.defaults.values() if name
    ]
    assert _diagnostics((_GAMES / host.game).read_text(), host.game) == []


def test_a_tochoo_library_is_refused_for_its_early_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The most plausible library a designer writes: Getaway's own trick, with
    its `early` clause, shared between shedding games. The Builtin winner
    beside it is accepted; the predicate is not."""
    fills: dict[str, str | None] = {
        "winner_fn": "highest_of_led_suit",
        "early_termination": "on_play_off_led_suit",
    }
    _patch(monkeypatch, _TRICK.library_text(_TRICK.round(fills)))
    got = _diagnostics(_TRICK.game_text(uses=True, game_local_round=None), _TRICK.game)
    assert got == [(_LIBRARY_FILE, _primitive_rule("on_play_off_led_suit"))]


# An importer's clause a game-clause gate on climb queries reads -> (the
# queries the library's round names, the edit to the host that trips the gate).
_CLAUSE_TRIGGERS: dict[str, tuple[dict[str, str | None], tuple[str, str]]] = {
    "trick_order block": (
        _CLIMB.defaults,
        ("  cards: standard52\n", "  cards: standard52\n  trick_order {\n    trump: false\n  }\n"),
    ),
    "no ranking": (
        {"combos_fn": "president_lead_options", "follows_fn": "president_follows"},
        (_CLIMB.clauses, ""),
    ),
}


@pytest.mark.parametrize("trigger", sorted(_CLAUSE_TRIGGERS))
def test_the_refusal_precedes_the_clause_gates_on_climb_queries(
    trigger: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library's climb queries in an importer whose clauses a game-clause
    gate on climb queries refuses: the library is wrong whatever imports it,
    so its author hears that first and alone -- the clause question is the
    importer's only once the library names something a game may supply.
    red under: running `_check_library_clause_gates` for a library
    `check_library_alone` refused, in `resolve._apply_uses` (executed
    2026-10-15, both triggers)."""
    queries, (old, new) = _CLAUSE_TRIGGERS[trigger]
    _patch(monkeypatch, _CLIMB.library_text(_CLIMB.round(queries)))
    text = _CLIMB.game_text(uses=True, game_local_round=None)
    assert text.count(old) == 1
    got = _diagnostics(text.replace(old, new), _CLIMB.game)
    assert got == [
        (_LIBRARY_FILE, _primitive_rule(name)) for name in queries.values() if name
    ]


def test_a_library_calling_a_primitive_asks_a_piece_game_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #873's witness: a library calling a deck-reading Primitive,
    imported by a piece game. The library's author hears the Primitive refusal
    alone; the game's author is not also told the library reads a card, a
    question that is gone once the library is fixed.

    red under: running `_check_library_clause_gates` for a library
    `check_library_alone` refused, in `resolve._apply_uses` (executed
    2026-10-15: a second, `uses`-line refusal that the game is played with
    pieces)."""
    _patch(
        monkeypatch,
        f"library {_LIB} {{ function probe_fn(p : Player) = belote_royal_player() }}\n",
    )
    text = (_GAMES / "tic-tac-toe.cardlang").read_text()
    anchor = "game TicTacToe {\n"
    assert text.count(anchor) == 1
    got = _diagnostics(text.replace(anchor, f"{anchor}  uses {_LIB}\n"), "tic-tac-toe.cardlang")
    assert len(got) == 1, got
    source, message = got[0]
    assert source == _LIBRARY_FILE, got
    assert "'belote_royal_player', which is a Primitive" in message, got


def test_a_gated_call_inside_a_refused_round_asks_the_importer_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refused round is left out whole: a `ranking:`-gated call in its own
    `until`, in an importer that declares no `ranking:`, adds no `uses`-line
    refusal beside the library author's.

    red under: running `_check_library_clause_gates` for a library
    `check_library_alone` refused, in `resolve._apply_uses` (executed
    2026-10-15: the `rank_value` call drew a second, `uses`-line refusal)."""
    until = "until (any player where hand[player] is empty)"
    gated = "until (any card in trick_pile where rank_value(card) > 13)"
    round_text = _CLIMB.round(_CLIMB.defaults)
    assert round_text.count(until) == 1
    _patch(monkeypatch, _CLIMB.library_text(round_text.replace(until, gated)))
    text = _CLIMB.game_text(uses=True, game_local_round=None)
    assert text.count(_CLIMB.clauses) == 1
    got = _diagnostics(text.replace(_CLIMB.clauses, ""), _CLIMB.game)
    assert got == [
        (_LIBRARY_FILE, _primitive_rule(name)) for name in _CLIMB.defaults.values() if name
    ]
