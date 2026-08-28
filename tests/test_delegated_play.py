"""Delegated Play — the decider/actor split (decisions.md "Delegated play").

The grid covers the scoped feature (issue #452's scope ruling): routing at the
kernel `round` loop, the two per-game helpers, the refusals around them, and
the attribution law — `Arrival.actor` is the deciding seat while winner
computation pairs cards with the attributed seat, "two facts, deliberately"
(decisions.md "The Arrival Record").

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a game defining the helper functions has its round decisions
                 made by the routed decider from the routed source, observed
                 and attributed per the two-fact law; a game whose helpers
                 cannot reach a routable decision point, or whose helper is
                 mis-shaped, or whose routed source the decider cannot see, is
                 refused loudly; and every chooser call site in the engine is
                 classified routable or actor-only.
domain:          the decision-point axis is every `ctx.chooser(...)` call site
                 under `cardlang/`, AST-derived here and reconciled against
                 `runtime.delegation.DECISION_POINTS`; the behavior cells run
                 minimal fixture games through the real driver and replay
                 engine. Deliberately outside: routing at actor-only sites and
                 hidden-state routing conditions (both issue #458), and the
                 Bridge witness itself, which lands in `docs/games/` with its
                 own proof module.
registry:        decision points: the AST scrape below over `cardlang/`;
                 classification: `cardlang.runtime.delegation.DECISION_POINTS`;
                 helper names: `cardlang.runtime.delegation.HELPER_NAMES`;
                 projections consulted by the visibility guard:
                 `cardlang.stdlib.zones.ZONE_PROJECTIONS`.
does not prove:  fixture playouts walk one deterministic line each, so a
                 routing defect on an unreached branch is seen only by the
                 refusal guards; and corpus neutrality (the nine `source hand`
                 trick games unchanged) is the full suite's evidence, not this
                 module's.
"""

from __future__ import annotations

import ast
import pathlib
import random
from typing import Any

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.delegation import DECISION_POINTS, HELPER_NAMES
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError

CARDLANG = pathlib.Path(__file__).resolve().parent.parent / "cardlang"


# =============================================================================
# The decision-point census — the axis's defining site, derived not listed
# =============================================================================


def _chooser_call_sites() -> set[str]:
    """Every `<expr>.chooser(...)` call site under `cardlang/`, as
    "module.enclosing_function". The scrape reads attribute-call shape, not a
    string, so a renamed local alias still counts and a comment never does."""
    sites: set[str] = set()
    for path in sorted(CARDLANG.rglob("*.py")):
        tree = ast.parse(path.read_text())
        spans = [
            (n.lineno, max(getattr(n, "end_lineno", n.lineno) or n.lineno, n.lineno), n.name)
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "chooser"
            ):
                enclosing = [name for lo, hi, name in spans if lo <= node.lineno <= hi]
                sites.add(f"{path.stem}.{enclosing[-1] if enclosing else '<module>'}")
    return sites


def test_every_decision_point_is_classified() -> None:
    """The classification table and the tree agree in both directions: a new
    chooser call site must take a routing posture to land, and a removed one
    must leave the table.

    red under: add `ctx.chooser(actor, [1], 1)` anywhere under `cardlang/` —
    the scrape gains a key the table lacks (verified at authoring: the scrape
    finds exactly the seven sites the glossary counts)."""
    assert _chooser_call_sites() == set(DECISION_POINTS), (
        "chooser call sites and runtime.delegation.DECISION_POINTS disagree — "
        "classify the new site as routable or actor_only (issue #458 records "
        "what lifting actor_only takes)"
    )


def test_the_postures_are_the_scoped_split() -> None:
    """Exactly one routable site — the round loop — per issue #452's scope
    ruling. Widening this set is issue #458's work, not a drive-by edit."""
    routable = {k for k, v in DECISION_POINTS.items() if v == "routable"}
    assert routable == {"mechanics.run_decision_round"}
    assert set(DECISION_POINTS.values()) <= {"routable", "actor_only"}
    assert HELPER_NAMES == {"chooser_for", "play_source_for"}


# =============================================================================
# Fixtures — minimal games, deterministic deals (no shuffle: the deck order
# is the deal), each a complete game the driver can play to a result
# =============================================================================

_BASE = """
game {name} {{
  players: 2
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {{
    deck             : Deck
    hand[player]     : Hand<player>
    exposed[player]  : PublicHand<player>
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }}

  state {{
    score[player] : Integer = 0
    leader        : Player? = none
    boss          : Player  = 0
  }}

  phase deal {{
    deal 3 cards from deck to each hand
{after_deal}
  }}

  phase play {{
    active_rules: [MustFollowSuit]
    legal_moves:  [play_to_trick]
    leader := boss
    repeat until (all players where
        (number of cards in hand[player]) + (number of cards in exposed[player]) is 0) {{
      round play_to_trick from leader over all players source {source} into trick_pile
            winner highest_of_led_suit
      move all cards from trick_pile to captured[winner]
      leader := winner
    }}
  }}

  phase scoring {{
    for each player p: score[p] := number of cards in captured[p]
  }}

  winner: highest score
}}

{functions}
"""


def _fixture(name: str, functions: str = "", after_deal: str = "", source: str = "hand") -> Any:
    return check_dsl(
        _BASE.format(name=name, functions=functions, after_deal=after_deal, source=source),
        f"{name}.cardlang",
    )


class _Recording:
    """A chooser that records (player, candidates) per draw and picks first."""

    def __init__(self) -> None:
        self.draws: list[tuple[Any, list[Any]]] = []

    def __call__(self, player: Any, candidates: list[Any], n: int) -> list[Any]:
        self.draws.append((player, list(candidates)))
        return list(candidates)[:n]


# =============================================================================
# The routing cells — red until the hook lands
# =============================================================================


def test_chooser_routing_sends_every_draw_to_the_decider() -> None:
    """`chooser_for` routes the draw: with every decision routed to the holder
    of the ace of spades, no round draw ever reaches the other seat."""
    # The pool is public (declared `source exposed`) so routing the draws is
    # epistemically legal — the visibility guard rightly refuses a delegated
    # draw from a private hand, which is its own cell below. The declared
    # non-`hand` source also exercises issue #457's fix: candidates, rule
    # bodies, and removal all read the declared source.
    game = _fixture(
        "ChooserOnly",
        functions="function chooser_for(p : Player) = boss",
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
        source="exposed",
    )
    rec = _Recording()
    play_game(game, random.Random(0), chooser=rec)
    routed = [p for p, _ in rec.draws]
    assert all(int(p) == 0 for p in routed), (
        f"draws reached seats {sorted(set(int(p) for p in routed))}; "
        f"chooser_for routes every round decision to boss (seat 0)"
    )


def test_source_routing_draws_candidates_from_the_routed_zone() -> None:
    """`play_source_for` routes the pool: with every hand exposed and the
    helper naming `exposed`, the game completes and every candidate offered is
    a card — drawn from zones the plain `source hand` would find empty."""
    game = _fixture(
        "SourceOnly",
        functions="function play_source_for(p : Player) = exposed[p]",
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
    )
    rec = _Recording()
    result = play_game(game, random.Random(0), chooser=rec)
    assert sum(result.scores.values()) == 6, (
        f"the six dealt cards should all be captured; scores={result.scores}"
    )


def test_the_delegated_seats_winning_card_crowns_the_delegated_seat() -> None:
    """The attribution law's behavioral half: the decider chooses, but the
    trick belongs to the seat whose card wins. Each trick's rightful winner is
    recomputed here from the public movement events alone (led suit = the
    trick's first card; strongest of the led suit by the declared ranking),
    and the seat that captures must be that seat — under a pairing polluted by
    the decider, tricks the non-boss seat wins would be captured by boss."""
    game = _fixture(
        "BridgeShaped",
        functions=(
            "function chooser_for(p : Player) = boss\n"
            "function play_source_for(p : Player) = exposed[p]"
        ),
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
    )
    logs: list[tuple[Any, ...]] = []
    play_game(
        game,
        random.Random(0),
        chooser=_Recording(),
        observer=lambda p, e: logs.append(e) if p == 0 else None,
    )
    ranking = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]

    def strength(card: str) -> int:  # cards render as e.g. "10♠" — suit is the last char
        return len(ranking) - ranking.index(card[:-1])

    plays: list[tuple[int, str]] = []  # (attributed seat, card) in play order
    checked = 0
    for event in logs:
        if event[0] != "move":
            continue
        src, dst = str(event[1]), str(event[3])
        if dst == "trick_pile" and src.startswith("exposed["):
            seat = int(src[len("exposed[") : -1])
            cards = event[2]
            assert isinstance(cards, tuple) and len(cards) == 1
            plays.append((seat, cards[0]))
        elif src == "trick_pile" and dst.startswith("captured["):
            captured_by = int(dst[len("captured[") : -1])
            led_suit = plays[0][1][-1]
            rightful = max(
                (pl for pl in plays if pl[1][-1] == led_suit),
                key=lambda pl: strength(pl[1]),
            )[0]
            assert captured_by == rightful, (
                f"trick {plays} captured by seat {captured_by}; the winning "
                f"card belongs to seat {rightful} — a winner path paired the "
                f"card with the decider"
            )
            plays = []
            checked += 1
    assert checked >= 3, f"only {checked} tricks observed; the fixture plays 3"


def test_chose_event_lands_in_the_deciders_log() -> None:
    """Perfect recall belongs to the party who chose: the `chose` event for a
    delegated draw lands in the decider's observation log, not the actor's."""
    game = _fixture(
        "ChooserOnly2",
        functions="function chooser_for(p : Player) = boss",
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
        source="exposed",
    )
    logs: dict[Any, list[tuple[Any, ...]]] = {0: [], 1: []}
    rec = _Recording()
    play_game(
        game,
        random.Random(0),
        chooser=rec,
        observer=lambda p, e: logs[p].append(e),
    )
    chose = {p: [e for e in logs[p] if e[0] == "chose"] for p in logs}
    assert chose[0] and not chose[1], (
        f"chose events: seat0={len(chose[0])} seat1={len(chose[1])} — every "
        f"round draw is boss's (seat 0's) decision, so every chose event is "
        f"seat 0's recall"
    )


# =============================================================================
# The refusals — loud, in the right channel, red until the guards land
# =============================================================================


def test_helpers_with_no_routable_decision_are_refused() -> None:
    """A game defining the helpers whose phases hold no `round` is refused by
    name at check time — accepted-but-ignored is the defect class this cell
    exists to keep out."""
    src = """
    game Inert {
      players: 2
      max_length: 50
      cards: standard52
      ranking: A K Q J 10 9 8 7 6 5 4 3 2
      zones { deck : Deck  hand[player] : Hand<player>  pile : Discard }
      state { score[player] : Integer = 0 }
      phase p { for each player q: move chosen one card from hand[q] to pile }
      winner: highest score
    }
    function chooser_for(p : Player) = p
    """
    with pytest.raises(DiagnosticError, match="chooser_for"):
        check_dsl(src, "inert.cardlang")


def test_a_misshapen_helper_is_refused() -> None:
    """The exact helper name activates the signature Owner Guard: a
    `chooser_for` that does not take exactly one Player is refused where the
    designer wrote it."""
    game_src = _BASE.format(
        name="BadSig",
        functions="function chooser_for(p : Player, q : Player) = p",
        after_deal="",
        source="hand",
    )
    with pytest.raises(DiagnosticError, match="chooser_for"):
        check_dsl(game_src, "badsig.cardlang")


def test_a_source_the_decider_cannot_see_is_refused() -> None:
    """The visibility Owner Guard: a delegated draw from a pool that does not
    project identity to the decider refuses at the draw, before any candidate
    is offered — never a blind deal. Runtime rather than resolve because
    whether a seat's pool is delegated depends on both helpers' values at the
    same seat, which two opaque expression bodies do not statically reveal
    (Bridge's own helper legally routes undelegated seats to their private
    hands). `hand` projects count_only to non-owners, so boss deciding the
    other seat's play from that seat's own hand must refuse."""
    game = _fixture(
        "Blind",
        functions=(
            "function chooser_for(p : Player) = boss\n"
            "function play_source_for(p : Player) = hand[p]"
        ),
    )
    with pytest.raises(OwnerGuardError, match="cannot see"):
        play_game(game, random.Random(0), chooser=_Recording())


# =============================================================================
# The review round's cells — the finding is one row of a class
# =============================================================================


def test_source_routing_alone_cannot_reach_an_opponents_private_zone() -> None:
    """`play_source_for` with NO delegation can hand a seat an opponent's
    private hand (`hand[p offset_by left]`) — the decider is the actor, but
    the pool is cards the actor cannot see. The visibility guard fires on any
    routed draw, not only a delegated one."""
    game = _fixture(
        "SelfBlind",
        functions="function play_source_for(p : Player) = hand[p offset_by left]",
    )
    with pytest.raises(OwnerGuardError, match="cannot see"):
        play_game(game, random.Random(0), chooser=_Recording())


def test_an_owner_blind_declared_source_is_refused_statically() -> None:
    """The DECLARED source needs no helper to be wrong: `source stock` over a
    FaceDownPile offers the actor cards they cannot see, known from the
    declaration alone — refused at resolve, where the designer wrote it.

    red under: delete the declared-source projection wall in
    `resolve._check_delegation` (verified)."""
    src = _BASE.format(
        name="DeclaredBlind", functions="", after_deal="", source="stock"
    ).replace(
        "    trick_pile       : TrickPile",
        "    stock[player]    : FaceDownPile\n    trick_pile       : TrickPile",
    ).replace(
        "deal 3 cards from deck to each hand",
        "deal 3 cards from deck to each stock",
    )
    with pytest.raises(DiagnosticError, match="identity to its own seat"):
        check_dsl(src, "declaredblind.cardlang")


def test_the_pile_read_winner_agrees_with_the_round_winner_under_delegation() -> None:
    """The Arrival-Record CALL form (`highest_trump_or_led_suit(pile, ...)`)
    pairs each card with the ATTRIBUTED seat, so it crowns the same winner as
    the round's own winner slot even when every play was the boss's decision.
    The fixture folds the agreement into its own scoring — each seat's final
    score is captured cards minus two per pile-read trick, so every score is
    zero exactly when the two winner paths crowned the same seat every trick.
    Under a record storing the decider, boss's pile-read credit would drive
    boss negative and the true winner positive.

    red under: store `delegation.decider_for(ctx, actor)` as the arrival
    actor in `TrickForm.apply` (verified; the same mutation reddens the
    record cell below)."""
    src = _BASE.format(
        name="PileRead",
        functions=(
            "function chooser_for(p : Player) = boss\n"
            "function play_source_for(p : Player) = exposed[p]"
        ),
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
        source="hand",
    ).replace(
        "    score[player] : Integer = 0",
        "    score[player] : Integer = 0\n    pile_tricks[player] : Integer = 0",
    ).replace(
        "      move all cards from trick_pile to captured[winner]",
        "      pile_tricks[highest_trump_or_led_suit(trick_pile, none)] += 1\n"
        "      move all cards from trick_pile to captured[winner]",
    ).replace(
        "    for each player p: score[p] := number of cards in captured[p]",
        "    for each player p: score[p] := (number of cards in captured[p]) - (2 * pile_tricks[p])",
    )
    game = check_dsl(src, "pileread.cardlang")
    result = play_game(game, random.Random(0), chooser=_Recording())
    assert all(v == 0 for v in result.scores.values()), (
        f"scores {result.scores}: a nonzero seat means the pile-read winner "
        f"and the round winner crowned different seats for some trick — the "
        f"call form paired a card with the decider"
    )


def test_a_delegated_plays_record_carries_the_attributed_seat() -> None:
    """The record itself, read at a pause: after a delegated play, the trick
    pile's arrival names the ACTOR (the source's owner), never the boss who
    chose it — the seat every observer can derive from the movement's source
    label (issue #256's no-leak criterion; the decider's recall is the chose
    event, private to the decider).

    red under: store `delegation.decider_for(ctx, actor)` as the arrival
    actor in `TrickForm.apply` — the delegated lead's arrival then names
    boss (verified; the delegated seat must LEAD in this fixture, since a
    2p trick completes at two plays and a boss-led line leaves no delegated
    arrival at any pause)."""
    src = _BASE.format(
        name="RecordSeat",
        functions=(
            "function chooser_for(p : Player) = boss\n"
            "function play_source_for(p : Player) = exposed[p]"
        ),
        after_deal="    for each player p: move all cards from hand[p] to exposed[p]",
        source="hand",
    ).replace(
        # The delegated seat LEADS, so the trick's first arrival is the
        # delegated play — in a 2p game the trick completes at two plays and
        # the pile empties, so a boss-led line holds no delegated arrival at
        # any pause.
        "    leader := boss\n", "    leader := boss offset_by left\n"
    )
    import tempfile

    from cardlang.openspiel.replay import DecisionNode, run

    with tempfile.NamedTemporaryFile(
        "w", suffix=".cardlang", delete=False
    ) as f:
        f.write(src)
        path = f.name
    r: Any = run(path, 0, ())
    assert isinstance(r, DecisionNode)
    r2: Any = run(path, 0, (r.legal[0],))
    assert isinstance(r2, DecisionNode)
    pile = r2.rs.zones.single("trick_pile")
    assert len(pile.arrivals) == 1, "the leader's play should sit in the pile"
    arrival = pile.arrivals[-1]
    assert arrival.src is not None
    src_family, src_key = arrival.src
    assert src_key is not None and int(src_key) != 0, (
        "the sampled play is boss's own — walk further"
    )
    assert src_family == "exposed" and arrival.actor == src_key, (
        f"the delegated play's arrival names actor {arrival.actor} with "
        f"source {arrival.src}; the record stores the attributed seat (the "
        f"source's owner), and the decider only in the decider's own log"
    )
