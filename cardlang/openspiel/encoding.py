"""Derived per-game action encoding.

Every decision a kernel game can pose maps to a stable global action id — the
same id means the same action in every world, which is what makes determinized
replay sound (SP1 spec, Pillar 2). The space is the disjoint union, in a fixed
layout, of: the card block (always — the standard 52 for any deck expressible
in it, else a per-game block derived from the deck itself; see
`_derived_card_block`); bare-name actions (offer move-types, the climb "pass");
the integer block 0..52 (games with `choose`); the auction vocabulary (moves
flattened over their parameter domains, declared order); and the combination
block — the climb engine's enumerated `universe()` query (canonically ordered
and golden-pinned; Big Two) or, when the universe is too large to enumerate,
the engine's arithmetic codec (`climb_codec_function`; Tichu's 211,204,694
plays), whose ids are pure functions of the card-set.

A Card-parameterized vocabulary move (Schnapsen's `play_card`) contributes NO
vocab ids: its domain is state-dependent (the actor's live hand), and a card
play already has an id — the card block's. `encode` folds a `(move, card)`
candidate into `card_to_action(card)` and `match` accepts either
representation, so a card's id is identical whether it is a leader's
`play_card` or a follower's movement pick (Option B, SP6 sign-off 1).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Iterator

from cardlang.ast import nodes as n
from cardlang.runtime.mechanics import enumerate_domain
from cardlang.runtime.values import RANKS, SUITS, Card, build_deck

NUM_DISTINCT_ACTIONS = len(SUITS) * len(RANKS)  # 52 — the standard card block


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
    pinochle48 or schnapsen20 just leaves some of the 52 slots unused, exactly
    as before this function existed). Only a deck that needs MORE than the
    standard catalogue (French Tarot's atouts/Excuse; a future Tichu/Coup
    migration) gets its own from-scratch numbering, over its full distinct-card
    list — never a hybrid of the two schemes."""
    distinct = _dedup_deck_cards(deck_name)
    if all(_is_standard_card(c) for c in distinct):
        return None
    return distinct


_MAX_CHOOSE = 52  # integer chooses are bounded by the deck size in a card game


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


class ActionSpace:
    """The derived global action universe of one game."""

    def __init__(
        self,
        card_block: list[Card] | None,
        names: list[str],
        vocab: list[tuple[str, Any]],
        has_integers: bool,
        combos: list[Any],
        combo_codec: Any | None = None,
    ) -> None:
        self._card_block = card_block
        self._card_ids = (
            None if card_block is None else {c: i for i, c in enumerate(card_block)}
        )
        self._names = names
        self._vocab = vocab
        self._has_integers = has_integers
        self._combos = combos
        # An arithmetic codec serves the combo block when the engine's universe
        # is too large to enumerate (`stdlib.climb_codec_function`): ids are
        # computed from the card-set, never tabled. Exactly one of
        # (combos, combo_codec) is populated.
        self._combo_codec = combo_codec
        assert combo_codec is None or not combos
        self._name_base = NUM_DISTINCT_ACTIONS if card_block is None else len(card_block)
        self._int_base = self._name_base + len(names)
        self._vocab_base = self._int_base + (_MAX_CHOOSE + 1 if has_integers else 0)
        self._combo_base = self._vocab_base + len(vocab)
        combo_count = combo_codec.size if combo_codec is not None else len(combos)
        self.num_distinct_actions = self._combo_base + combo_count
        self._name_ids = {v: i for i, v in enumerate(names)}
        self._vocab_ids = {v: i for i, v in enumerate(vocab)}
        self._combo_ids = {frozenset(p.cards): i for i, p in enumerate(combos)}
        assert len(self._combo_ids) == len(combos), "combo card-sets must be unique"

    @staticmethod
    def for_game(game: n.Game) -> "ActionSpace":
        from cardlang.runtime import stdlib

        names: list[str] = []
        vocab: list[tuple[str, Any]] = []
        has_integers = False
        combos: list[Any] = []
        mt_index = {m.name: m for m in game.move_types}
        climb_engines: list[str] = []
        for node in _walk(game):
            if isinstance(node, n.Choose):
                has_integers = True
            elif isinstance(node, n.Offer):
                names.extend(m for m in node.move_types if m not in names)
            elif isinstance(node, n.Round) and node.combos_fn is not None:
                if node.combos_fn not in climb_engines:
                    climb_engines.append(node.combos_fn)
            elif isinstance(node, n.Round) and node.move_types is not None:
                for mt_name in node.move_types:
                    mt = mt_index[mt_name]
                    if mt.param is not None and mt.param.type_name == "Card":
                        # A Card-parameterized move's concrete actions ARE the
                        # card block (see the module docstring) — minting
                        # per-card vocab ids would give a card play two
                        # representations and inflate num_distinct_actions.
                        continue
                    entries = (
                        [(mt.name, None)]
                        if mt.param is None
                        else [(mt.name, v) for v in enumerate_domain(mt.param.type_name)]
                    )
                    vocab.extend(e for e in entries if e not in vocab)
        combo_codec: Any | None = None
        if climb_engines:
            assert len(climb_engines) == 1, "one climb engine per game for now"
            if "pass" not in names:
                names.append("pass")
            combo_codec = stdlib.climb_codec_function(climb_engines[0])
            if combo_codec is None:
                universe = stdlib.climb_universe_function(climb_engines[0])()
                combos = sorted(
                    universe,
                    key=lambda p: (p.size, p.kind, sorted(card_to_action(c) for c in p.cards)),
                )
        card_block = _derived_card_block(game.deck)
        return ActionSpace(
            card_block, sorted(names), vocab, has_integers, combos, combo_codec
        )

    def encode(self, value: Any) -> int:
        if isinstance(value, Card):
            if self._card_ids is None:
                return card_to_action(value)
            return self._card_ids[value]
        if isinstance(value, bool):
            raise ValueError("boolean is not an action value")
        if isinstance(value, int):
            assert self._has_integers, "this game has no integer decisions"
            assert 0 <= value <= _MAX_CHOOSE, f"choose value {value} out of 0..{_MAX_CHOOSE}"
            return self._int_base + value
        if isinstance(value, str):
            return self._name_base + self._name_ids[value]
        if isinstance(value, tuple):
            name, param = value
            if isinstance(param, Card):
                return self.encode(param)  # Card-param move: the card block id
            return self._vocab_base + self._vocab_ids[value]
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
        if self._int_base <= aid < self._vocab_base:
            return aid - self._int_base
        if self._vocab_base <= aid < self._combo_base:
            return self._vocab[aid - self._vocab_base]
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
            # Card-parameterized vocabulary move — a `(name, card)` candidate —
            # in an auction pool (never both in one pool; resolve rejects a
            # second Card-parameterized move per vocabulary).
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
            found = next((c for c in pool if c == value), _missing)
        if found is _missing:
            raise ValueError(
                f"recorded action {aid} ({self.to_string(aid)}) is not among the live candidates"
            )
        return found

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
            return name if param is None else f"{name}({param})"
        return str(value)
