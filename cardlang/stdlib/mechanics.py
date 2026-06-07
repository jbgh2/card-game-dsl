"""Standard-library mechanics, as data.

The named, parameterized behavioral units from library.md "Mechanics". The
resolver checks every `instantiate` against this set. Seeded with what the
formalized corpus uses; extended corpus-first.
"""

from __future__ import annotations

LIBRARY_MECHANICS: frozenset[str] = frozenset(
    {
        "Trick",
        "SchnapsenHand",  # Schnapsen's trick-and-draw hand with heterogeneous lead moves
        "PinochleHand",  # Pinochle's auction + meld + strict-trick hand
        "BridgeAuction",  # Bridge's ascending auction with double/redouble
        "SkatHand",  # Skat's Reizen auction + contract + suit/grand/null tricks
        "TarotHand",  # French Tarot's bidding + chien + atout tricks + bouts scoring
        "CribbageHand",  # Cribbage's discard + pegging + the show (a counting engine)
        "StudHand",  # Seven-Card Stud's antes + betting streets + showdown
        "TichuHand",  # Tichu's pushing + climbing trick + special cards + scoring
        "CoupGame",  # Coup's influence / coin / challenge-block / elimination engine
    }
)
