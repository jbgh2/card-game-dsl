---
term: Hand Loop
definition: The repetition a game's hands are iterations of — what `skip to next hand` advances to the next pass of, and what deckcheck's per-hand capacity window is measured over. One pass through it is a [[hand]]; the loop is the construct, the hand is the cycle. The language never declares it: `SkipToNextHand` continues the enclosing `repeat until`, and `hands_played` counts phases literally named `scoring`, so a game naming its scoring phase otherwise reports none (→ F-6).
layer: kernel
status: canonical
reserved: false
home: `driver.py`
see: []
retired_spellings: []
findings: [F-6]
---

Naming it does not declare it. Whether the language should carry a structural
marker for the loop is F-6's question, not this entry's.
