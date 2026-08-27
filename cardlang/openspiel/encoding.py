"""Derived per-game action encoding.

Every decision a kernel game can pose maps to a stable global [[action]] id —
the same id means the same action in every world, which is what makes
determinized replay sound (SP1 spec, Pillar 2). The space is the disjoint union, in a fixed
layout, of: the card block (the standard 52 for any deck expressible in it,
else a per-game block derived from the deck itself, and EMPTY for a game no
decision of which can offer a content item; see `_derived_card_block` and
`_decides_a_content_item`); bare-name actions (offer move-types, the climb "pass");
the integer block `0..ceiling` (games with `choose`, sized to the game's
largest declared `choose` ceiling — decisions.md "Declared parameter domains");
the [[offering]] block (moves
flattened over their parameter domains, declared order); and the combination
block — the climb engine's enumerated `universe()` query (canonically ordered
and golden-pinned; Big Two) or, when the universe is too large to enumerate,
the engine's arithmetic codec (`climb_codec_function`; Tichu's 211,204,694
plays), whose ids are pure functions of the card-set.

A Card-parameterized offering move (Schnapsen's `play_card`) contributes NO
offering ids: its domain is state-dependent (the actor's live hand), and a card
play already has an id — the card block's. `encode` folds a `(move, card)`
candidate into `card_to_action(card)` and `match` accepts either
representation, so a card's id is identical whether it is a leader's
`play_card` or a follower's [[transfer]] pick (Option B, SP6 sign-off 1).

Contract
--------
Assumes: a checked game, whose decision-bearing constructs are all reachable
from the `Game` tree — resolve flattens `uses` imports and `expand` splices
procedure bodies precisely so this module's walk sees them.
Establishes: two implications, not a biconditional. An ABSENT block means no
decision the game can reach offers a candidate this module numbers into it; a
PRESENT block numbers every content item the game can offer. Presence follows
from a construct existing in the tree rather than from its site being
reachable, so a game may still reserve a block nothing exercises — the
over-approximation `_decides_a_content_item` is built to make. Illegal after
this: assuming action id 0 is a card, that `NUM_DISTINCT_ACTIONS` bounds any
game's space from below, or that `verbs()` contains `CARD_VERB`. Encoding a
content item against a game with no card block is refused, never numbered.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from cardlang.ast import nodes as n
from cardlang.board_domains import directions_of, position_domains_of
from cardlang.domains import DomainSources, enumerate_domain
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.mechanics import _pack
from cardlang.runtime.observe import render_candidate
from cardlang.runtime.values import RANKS, SUITS, Card, build_deck, deck_suits

NUM_DISTINCT_ACTIONS = len(SUITS) * len(RANKS)  # 52 — the standard card block

# The verb names for the three blocks whose ids carry a parameter VALUE rather
# than a move-type name: a Card-parameterized move's ids are the card block's
# (see the module docstring), an integer `choose`'s id is the chosen value, and
# a combination id is the card-set. Nothing in the encoding recovers a name
# from those ids, so the block itself is the finest verb they can support.
# Angle brackets keep them disjoint from move-type names, which the grammar
# restricts to identifiers.
CARD_VERB = "<card>"
INT_VERB = "<int>"
COMBO_VERB = "<combo>"


def card_to_action(card: Card) -> int:
    return SUITS.index(card.suit) * len(RANKS) + RANKS.index(card.rank)


def action_to_card(action: int) -> Card:
    if not 0 <= action < NUM_DISTINCT_ACTIONS:
        raise ValueError(f"action {action} out of range 0..{NUM_DISTINCT_ACTIONS - 1}")
    return Card(RANKS[action % len(RANKS)], SUITS[action // len(RANKS)])


def _is_standard_card(card: Card) -> bool:
    return card.suit in SUITS and card.rank in RANKS


def _dedup_deck_cards(deck_name: str) -> list[Card]:
    """A deck's distinct cards, first-occurrence deduped in deck-declaration
    order (a `copies > 1` deck like pinochle48 repeats each card; the action
    space needs one id per distinct card, never one per physical copy)."""
    seen: set[Card] = set()
    out: list[Card] = []
    for c in build_deck(deck_name):
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _derived_card_block(deck_name: str) -> list[Card] | None:
    """The per-game card block `ActionSpace` numbers cards over. `None` — the
    sentinel for "use the standard 52-slot mapping above" — when every distinct
    card the deck holds is expressible as one (`suit in SUITS and rank in
    RANKS`): the module-level `card_to_action` formula already covers it
    exactly, since `build_deck` for a `ranks`-cross-product deck iterates
    suit-major/rank-minor — the SAME order `card_to_action` assumes — so every
    currently-registered game's ids hold verbatim (a subset deck like
    pinochle48 or schnapsen20 just leaves some of the 52 slots unused). Only a
    deck that needs MORE than the standard catalogue (French Tarot's
    atouts/Excuse; a future Tichu/Coup migration) gets its own from-scratch
    numbering, over its full distinct-card list — never a hybrid of the two
    schemes."""
    distinct = _dedup_deck_cards(deck_name)
    if all(_is_standard_card(c) for c in distinct):
        return None
    return distinct


@dataclass(frozen=True)
class ComboAction:
    """A decoded combination action: the card-set it moves. Matched against
    engine plays by card-set (each set denotes exactly one play — a pinned
    invariant of the universe)."""

    cards: frozenset[Card]


def _walk(node: Any) -> Iterator[Any]:
    """Every dataclass node reachable from `node` (AST nodes hold only
    dataclasses, tuples, and leaves)."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in dataclasses.fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _decides_a_content_item(game: n.Game, mt_index: dict[str, n.MoveTypeDef]) -> bool:
    """Whether this game HOLDS a construct whose decision offers a candidate
    the card block numbers — a bare content item, or a Card-parameterized
    move's `(name, card)` pair, which `encode` folds onto the same id.

    Holds, not reaches: see the over-approximation below.

    Every decision point is accounted for — each of
    `runtime.delegation.DECISION_POINTS` (the engine's own enumeration of
    chooser call sites, reconciled against an AST scrape by
    tests/test_delegated_play.py) is either an arm below or named at the
    bottom as offering something the other blocks number. Arms and sites are
    not one-to-one: the three round forms share one site, and the two
    non-joint movement sites share one arm. Each site is crossed against the
    answers it admits in tests/test_card_block_derivation.py.

    A sound over-approximation, deliberately. Node presence does not prove the
    site is reachable — a `when:`-gated phase or an untaken branch may never
    fire — so a game can carry a block it never uses. That direction costs
    ids; the other direction has no id to return at all, so an unclear case
    answers True, and `encode` refuses a content item against an absent block
    rather than numbering it into the next block's range.
    """
    for node in _walk(game):
        if isinstance(node, n.TrickRound):
            # The trick form's candidates are the pool's cards, always.
            return True
        if isinstance(node, n.EachSimultaneous):
            # `_pass_selection` draws from `source.cards` and consults NEITHER
            # `where` nor `jointly`, so a joint body inside this form still
            # offers bare cards. The form is therefore unconditional here, and
            # the Transfer arm below cannot stand in for it.
            return True
        if isinstance(node, n.Transfer):
            # A joint selection's candidates are card SUBSETS, which the combo
            # block numbers; every other chosen movement draws bare cards.
            if node.selection_mode == "chosen" and not node.joint:
                return True
        if isinstance(node, (n.Offer, n.AuctionRound)):
            for mt_name in node.offering:
                mt = mt_index.get(mt_name)
                if mt is None or any(p.type_name == "Card" for p in mt.params):
                    # A move type the index does not hold is unresolvable from
                    # here; answering True keeps the miss to wasted ids.
                    return True
    # Left out deliberately, each numbered by another block: `ClimbRound`
    # (combination plays and the bare "pass"), a joint `Transfer` (card
    # subsets), and `Choose` (integers).
    return False


def _offering_entries(
    mt: n.MoveTypeDef,
    sources: DomainSources,
) -> list[tuple[str, Any]]:
    """One move type's offering entries — nullary is the empty-product
    `[(mt.name, None)]`; otherwise the full cross-product of its parameters'
    *declared* (static) domains, one entry per combination, packed by the
    SAME `mechanics._pack` the runtime's `concrete_moves` uses: arity 1 stays a
    bare value (so an existing single-param offering key like `("submit_bid",
    "hearts")` is byte-identical), arity >= 2 packs as a tuple. Callers have
    already excluded the Card-parameterized case — a card play's action id is
    the card block's, never an offering id (see the module docstring)."""
    if not mt.params:
        return [(mt.name, None)]
    domains = [enumerate_domain(p.type_name, sources) for p in mt.params]
    return [(mt.name, _pack(combo)) for combo in itertools.product(*domains)]


class ActionSpace:
    """The derived global action universe of one game."""

    def __init__(
        self,
        card_block: list[Card] | None,
        names: list[str],
        offering: list[tuple[str, Any]],
        int_ceiling: int | None,
        combos: list[Any],
        combo_codec: Any | None = None,
    ) -> None:
        # Three states, and the empty one is not the `None` one. `None` means
        # "number cards by the standard 52-slot formula"; an EMPTY list means
        # the game decides no content item, so the block reserves no ids at
        # all. Absence deliberately does not reuse the `None` sentinel: `encode`
        # reads `None` as the standard mapping and would hand a card an id
        # inside the next block's range rather than refusing it.
        self._card_block = card_block
        self._card_ids = (
            None if card_block is None else {c: i for i, c in enumerate(card_block)}
        )
        # Stated once, read by `encode` and `verbs` alike: two sites deriving
        # "does this space number content items" separately is two answers
        # waiting to disagree.
        self._has_card_block = card_block is None or len(card_block) > 0
        self._names = names
        self._offering = offering
        # The game's largest integer-`choose` ceiling, or None if it has no
        # integer decision. The shared integer block reserves `ceiling + 1` ids
        # (values `0 .. ceiling`), sized to the declared per-choose bounds rather
        # than a fixed deck-sized constant (decisions.md "Declared parameter
        # domains").
        self._int_ceiling = int_ceiling
        self._combos = combos
        # An arithmetic codec serves the combo block when the engine's universe
        # is too large to enumerate (`primitives.climb_codec_function`): ids are
        # computed from the card-set, never tabled. Exactly one of
        # (combos, combo_codec) is populated.
        self._combo_codec = combo_codec
        assert combo_codec is None or not combos
        self._name_base = NUM_DISTINCT_ACTIONS if card_block is None else len(card_block)
        self._int_base = self._name_base + len(names)
        self._offering_base = self._int_base + (
            int_ceiling + 1 if int_ceiling is not None else 0
        )
        self._combo_base = self._offering_base + len(offering)
        combo_count = combo_codec.size if combo_codec is not None else len(combos)
        self.num_distinct_actions = self._combo_base + combo_count
        self._name_ids = {v: i for i, v in enumerate(names)}
        self._offering_ids = {v: i for i, v in enumerate(offering)}
        self._combo_ids = {frozenset(p.cards): i for i, p in enumerate(combos)}
        assert len(self._combo_ids) == len(combos), "combo card-sets must be unique"

    @staticmethod
    def for_game(game: n.Game) -> ActionSpace:
        from cardlang.runtime import primitives

        names: list[str] = []
        offering: list[tuple[str, Any]] = []
        int_ceiling: int | None = None
        combos: list[Any] = []
        mt_index = {m.name: m for m in game.move_types}
        climb_engines: list[str] = []
        joint_engines: list[str | None] = []
        # The move-parameter domains, sourced from the game AST. Suits come
        # from `runtime.values.deck_suits` — the deck's actual card suits,
        # never the bare module constant or the declared `Deck.suits` field —
        # the SAME origin `driver.py` builds `rs.suits` from, so the two can
        # never diverge (a non-uniform deck like tichu56/tarot78 carries a
        # suit its declared `Deck.suits` omits). Ranks come from `game.ranking`
        # directly — the SAME origin `mechanics.param_domain` reads at runtime
        # (`ctx.rs.rank_index`, which `driver.py` builds from `game.ranking`)
        # — so the advertised action space and the live legal-candidate
        # enumeration are identical by construction, never merely coincident.
        # Presence is DERIVED, not assumed: a game no decision of which can
        # offer a content item reserves no card block, so its
        # `num_distinct_actions` — OpenSpiel's action dimension — carries no id
        # its states can never offer. The empty block is a third state beside
        # "derived" and "the standard 52"; see `ActionSpace.__init__`.
        card_block = (
            _derived_card_block(game.deck)
            if _decides_a_content_item(game, mt_index)
            else []
        )
        sources = DomainSources(
            suits=list(deck_suits(game.deck)),
            ranks=list(game.ranking),
            players=list(range(game.players.low)),
            # Position move-parameter domains, from the same union function the
            # driver hands the runtime (`position_domains_of`) — declared
            # integer domains plus the board-minted `cell`, identical by
            # construction.
            positions=dict(position_domains_of(game)),
            # The board-minted `dir` domain, from the same seam the driver reads
            # (`directions_of`) — so a `dir` move parameter's offering ids match
            # the runtime's live candidates. Empty for a boardless game.
            directions=dict(directions_of(game)),
        )
        for node in _walk(game):
            if isinstance(node, n.Choose):
                # The shared integer block is sized to the game's largest
                # declared ceiling (resolve guarantees each is a non-neg int).
                ceiling = n.static_ceiling(node)
                assert ceiling is not None
                int_ceiling = ceiling if int_ceiling is None else max(int_ceiling, ceiling)
            elif isinstance(node, n.Offer):
                # Routed by arity, same rule the round offering below uses:
                # a nullary offer keeps the bare-name representation in
                # `names`; a parameterized, non-Card move type contributes its
                # cross-product to `offering` instead of a stray, never-used bare
                # name. Without this routing, a parameterized `offer` move,
                # like Go Fish's `ask`, would be silently mis-routed.
                for mt_name in node.offering:
                    mt = mt_index[mt_name]
                    if not mt.params:
                        if mt.name not in names:
                            names.append(mt.name)
                    elif any(p.type_name == "Card" for p in mt.params):
                        pass  # the card block's id, not an offering id — see below
                    else:
                        entries = _offering_entries(mt, sources)
                        offering.extend(e for e in entries if e not in offering)
            elif isinstance(node, n.ClimbRound):
                if node.combos_fn not in climb_engines:
                    climb_engines.append(node.combos_fn)
            elif isinstance(node, n.Transfer) and node.joint:
                # A joint selection's candidates are card SUBSETS — what the combo
                # block deals in, exactly like climb plays. The subset
                # universe is not statically derivable from the inline
                # predicate, so the codec comes from a registry keyed by the
                # predicate's root call (the climb-engine pattern one
                # construct over): `gin_arrange_ok(...)` → the gin meld
                # codec. A predicate whose root is not a registered call is
                # refused below — loudly, not silently absent from the space.
                root = node.where
                fn = root.func if isinstance(root, n.Call) else None
                if fn not in joint_engines:
                    joint_engines.append(fn)
            elif isinstance(node, n.AuctionRound):
                for mt_name in node.offering:
                    mt = mt_index[mt_name]
                    if any(p.type_name == "Card" for p in mt.params):
                        # A Card-parameterized move's concrete actions ARE the
                        # card block (see the module docstring) — minting
                        # per-card offering ids would give a card play two
                        # representations and inflate num_distinct_actions.
                        continue
                    entries = _offering_entries(mt, sources)
                    offering.extend(e for e in entries if e not in offering)
        combo_codec: Any | None = None
        if climb_engines:
            assert len(climb_engines) == 1, "one climb engine per game for now"
            if "pass" not in names:
                names.append("pass")
            combo_codec = primitives.climb_codec_function(climb_engines[0])
            if combo_codec is None:
                universe = primitives.climb_universe_function(climb_engines[0])()
                combos = sorted(
                    universe,
                    key=lambda p: (p.size, p.kind, sorted(card_to_action(c) for c in p.cards)),
                )
        if joint_engines:
            # Corpus-first guards, all loud (issue #139 records the deferrals):
            # the combo block serves one subset universe per game, so a game
            # mixing climb and joint selections — or two joint predicates with
            # different universes — needs a codec-composition design no game
            # has forced yet.
            deck_cards = build_deck(game.deck)
            if len(deck_cards) != len(set(deck_cards)):
                raise NotImplementedError(
                    f"joint selections on a deck with duplicate identical "
                    f"cards ('{game.deck}') need a multiset-safe combo "
                    f"canonicalization — the combo block keys subsets by "
                    f"frozenset, which collapses copies (two identical cards "
                    f"encode as one, colliding distinct subsets); not "
                    f"implemented (no corpus user — Canasta deliberately "
                    f"encodes melds per card instead); recorded in roadmap.md"
                )
            if climb_engines:
                raise NotImplementedError(
                    "a game with BOTH a climb round and joint selections needs "
                    "a composed combo block — not implemented (no corpus user); "
                    "recorded in roadmap.md"
                )
            fns = sorted({f for f in joint_engines if f is not None})
            if None in joint_engines or not fns:
                raise NotImplementedError(
                    "a joint selection's action encoding needs its subset "
                    "universe: root the `where jointly` predicate in a "
                    "registered call (the climb-engine pattern) — an inline "
                    "predicate has no registered codec; recorded in roadmap.md"
                )
            codecs = {f: primitives.joint_codec_function(f) for f in fns}
            missing = sorted(f for f, c in codecs.items() if c is None)
            if missing:
                raise NotImplementedError(
                    f"no subset codec registered for joint predicate root(s) "
                    f"{missing} — register one in "
                    f"cardlang.runtime.primitives.joint_codec_function"
                )
            distinct = {id(c) for c in codecs.values()}
            if len(distinct) > 1:
                raise NotImplementedError(
                    "joint predicates with different subset codecs in one "
                    "game need a composed combo block — not implemented "
                    "(no corpus user); recorded in roadmap.md"
                )
            combo_codec = next(iter(codecs.values()))
        return ActionSpace(
            card_block, sorted(names), offering, int_ceiling, combos, combo_codec
        )

    def encode(self, value: Any) -> int:
        if isinstance(value, Card):
            # Presence is asked FIRST: "which numbering" is only a question
            # once there is a block to number into.
            if not self._has_card_block:
                # The derivation said this game decides no content item, and a
                # decision just offered one. There is no id to return: the next
                # block starts at 0, so any number produced here would name
                # another block's action. A ShadowGuardError rather than an
                # OwnerGuardError because the game is not at fault — the
                # derivation missed a construct, which is an engine gap. A
                # raise stops the run wherever it happens; `tests/conftest.py`
                # additionally fails any test that merely CONSTRUCTS one, which
                # covers `tests/` and not the experiment rigs.
                raise ShadowGuardError(
                    "ActionSpace.for_game's card-block derivation",
                    f"a decision offered {value}, but this game's action space "
                    f"reserves no card block — `_decides_a_content_item` must "
                    f"account for the construct that offered it",
                )
            if self._card_ids is None:
                return card_to_action(value)
            return self._card_ids[value]
        if isinstance(value, bool):
            raise ValueError("boolean is not an action value")
        if isinstance(value, int):
            assert self._int_ceiling is not None, "this game has no integer decisions"
            assert (
                0 <= value <= self._int_ceiling
            ), f"choose value {value} out of 0..{self._int_ceiling}"
            return self._int_base + value
        if isinstance(value, str):
            return self._name_base + self._name_ids[value]
        if isinstance(value, tuple):
            name, param = value
            if isinstance(param, Card):
                return self.encode(param)  # Card-param move: the card block id
            if param is None and name in self._name_ids:
                # A nullary `offer` move: the runtime represents it as
                # `(name, None)` (the same empty-product shape a nullary
                # round-offering move uses), but this game's action space
                # names it as a bare string — it was never a round-offering
                # member, so no `(name, None)` was minted into `offering`. Same
                # action either way.
                return self._name_base + self._name_ids[name]
            return self._offering_base + self._offering_ids[value]
        cards = getattr(value, "cards", None)
        if cards is not None:
            if self._combo_codec is not None:
                return self._combo_base + int(self._combo_codec.encode_cards(frozenset(cards)))
            return self._combo_base + self._combo_ids[frozenset(cards)]
        raise ValueError(f"cannot encode action value {value!r}")

    def decode(self, aid: int) -> Any:
        if 0 <= aid < self._name_base:
            return action_to_card(aid) if self._card_block is None else self._card_block[aid]
        if self._name_base <= aid < self._int_base:
            return self._names[aid - self._name_base]
        if self._int_base <= aid < self._offering_base:
            return aid - self._int_base
        if self._offering_base <= aid < self._combo_base:
            return self._offering[aid - self._offering_base]
        if self._combo_base <= aid < self.num_distinct_actions:
            if self._combo_codec is not None:
                return ComboAction(frozenset(self._combo_codec.decode(aid - self._combo_base)))
            return ComboAction(frozenset(self._combos[aid - self._combo_base].cards))
        raise ValueError(f"action {aid} out of range 0..{self.num_distinct_actions - 1}")

    def match(self, aid: int, pool: list[Any]) -> Any:
        """The candidate in `pool` that `aid` denotes (a recorded action must be
        among the live candidates — anything else is a corrupted history)."""
        _missing = object()
        value = self.decode(aid)
        if isinstance(value, ComboAction):
            found = next(
                (
                    c
                    for c in pool
                    if getattr(c, "cards", None) is not None
                    and frozenset(c.cards) == value.cards
                ),
                _missing,
            )
        elif isinstance(value, Card):
            # A card id denotes a bare card in a movement/trick pool, or a
            # Card-parameterized offering move — a `(name, card)` candidate —
            # in an auction pool (never both in one pool; resolve rejects a
            # second Card-parameterized move per offering).
            found = next(
                (
                    c
                    for c in pool
                    if c == value
                    or (isinstance(c, tuple) and len(c) == 2 and c[1] == value)
                ),
                _missing,
            )
        else:
            # A bare-string `value` (an offer move or the climb "pass") may
            # appear in `pool` as itself or, for an offer's nullary move, as
            # the runtime's `(name, None)` shape — both denote the same action
            # (see the mirroring case in `encode`).
            found = next(
                (
                    c
                    for c in pool
                    if c == value or (isinstance(value, str) and c == (value, None))
                ),
                _missing,
            )
        if found is _missing:
            raise ValueError(
                f"recorded action {aid} ({self.to_string(aid)}) is not among the live candidates"
            )
        return found

    def verb_of(self, aid: int) -> str:
        """The move-type name `aid` denotes, at the granularity the encoding
        preserves: a bare-name or offering id names its move type; a card,
        integer or combination id names its block (`CARD_VERB` etc.).
        Partitions `0..num_distinct_actions` exactly — same block boundaries as
        `decode`, which raises on an out-of-range id."""
        value = self.decode(aid)
        if isinstance(value, Card):
            return CARD_VERB
        if isinstance(value, ComboAction):
            return COMBO_VERB
        if isinstance(value, tuple):
            return str(value[0])
        if isinstance(value, str):
            return value
        return INT_VERB

    def verbs(self) -> frozenset[str]:
        """Every verb this game's action space DECLARES — the universe
        `verb_of` can return, derived from the blocks rather than enumerated
        over ids (the combination block is up to 211M ids wide). A bounded
        conformance walk's coverage claim is stated against this set."""
        # The card block contributes its verb only when it reserves ids — an
        # empty block numbers nothing, so no id can report `CARD_VERB` and
        # declaring it would claim a verb the space cannot produce.
        out = {CARD_VERB} if self._has_card_block else set()
        out.update(self._names)
        if self._int_ceiling is not None:
            out.add(INT_VERB)
        out.update(name for name, _ in self._offering)
        if self._combos or self._combo_codec is not None:
            out.add(COMBO_VERB)
        return frozenset(out)

    def to_string(self, aid: int) -> str:
        value = self.decode(aid)
        if isinstance(value, Card):
            return str(value)
        if isinstance(value, ComboAction):
            if self._combo_codec is not None:
                kind = str(self._combo_codec.kind_of(aid - self._combo_base))
                return f"{kind}[" + ",".join(sorted(str(c) for c in value.cards)) + "]"
            play = self._combos[aid - self._combo_base]
            return f"{play.kind}[" + ",".join(sorted(str(c) for c in play.cards)) + "]"
        if isinstance(value, tuple):
            name, param = value
            return render_candidate(name, param)
        return str(value)
