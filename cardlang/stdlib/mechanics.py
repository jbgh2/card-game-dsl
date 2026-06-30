"""Standard-library mechanics, as data.

The named, parameterized behavioral units from library.md "Mechanics". The
resolver checks every `instantiate` against this set. Seeded with what the
formalized corpus uses; extended corpus-first.
"""

from __future__ import annotations

LIBRARY_MECHANICS: frozenset[str] = frozenset(
    {
        "SchnapsenHand",  # Schnapsen's trick-and-draw hand with heterogeneous lead moves
        "PinochleRest",  # Pinochle's post-auction hand: trump + meld + strict tricks
        "SkatHand",  # Skat's Reizen auction + contract + suit/grand/null tricks
        "TarotRest",  # French Tarot post-auction: chien + atout tricks + bouts scoring
        "CribbageHand",  # Cribbage's discard + pegging + the show (a counting engine)
        "StudShowdown",  # Seven-Card Stud's RNG-free suffix: side-pot settlement + muck
        "TichuHand",  # Tichu's pushing + climbing trick + special cards + scoring
        "BigTwoHand",  # Big Two's climbing/shedding hand: combinations + penalty scoring
        "CoupGame",  # Coup's influence / coin / challenge-block / elimination engine
    }
)
