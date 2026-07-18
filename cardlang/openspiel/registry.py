"""The adapter's game registry — pure data, importable without pyspiel.

`game.py` registers each entry as a `pyspiel.Game` on import, which needs the
optional `openspiel` extra; the registry itself is consumed by pyspiel-free
callers too (the corpus pin in `tests/test_typecheck_corpus.py` asserts every
game file is registered and vice versa), so it lives here where importing it
cannot fail on a core install.
"""

from __future__ import annotations

# short_name -> game file. Every corpus game (all fully kernel).
GAMES: dict[str, str] = {
    "cardlang_hearts": "hearts.cardlang",
    "cardlang_getaway": "getaway.cardlang",
    "cardlang_spades": "spades.cardlang",
    "cardlang_bridge": "bridge.cardlang",
    "cardlang_oh_hell": "oh-hell.cardlang",
    "cardlang_big_two": "big-two.cardlang",
    "cardlang_seven_card_stud": "seven-card-stud.cardlang",
    "cardlang_pinochle": "pinochle.cardlang",
    "cardlang_french_tarot": "french-tarot.cardlang",
    "cardlang_cribbage": "cribbage.cardlang",
    "cardlang_schnapsen": "schnapsen.cardlang",
    "cardlang_skat": "skat.cardlang",
    "cardlang_tichu": "tichu.cardlang",
    "cardlang_coup": "coup.cardlang",
    "cardlang_go_fish": "go-fish.cardlang",
    "cardlang_doppelkopf": "doppelkopf.cardlang",
    "cardlang_president": "president.cardlang",
    "cardlang_gops": "gops.cardlang",
    "cardlang_gin_rummy": "gin-rummy.cardlang",
}
