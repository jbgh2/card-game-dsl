# Actor vs chooser

**Tier 1 — high impact, ready to commit.**

Bridge's dummy play: dummy is the *actor of record* (move comes
from their zone, attribution to them), but declarer is the
*chooser* (declarer decides which card). The current language
conflates these.

Three possible shapes:

(a) **Zone-level declaration:** `dummy_hand` declares
    `choices_made_by: declarer`. Fits the doctrine "visibility
    and access properties belong to the zone." Probably cleanest.

(b) **Move-type-level declaration:** doesn't fit — choice
    delegation is a property of this dummy in this game, not of
    `play_to_trick` in general.

(c) **Phase-level declaration:** most flexible but most invasive.

Leaning (a). The provisional fix in Bridge (`play_source_for`)
already routes the zone correctly; what remains is the chooser
side. Zone-level `choices_made_by:` defaulting to "the actor"
handles every game in the corpus today, with `dummy_hand`
declaring the override.

**High impact:** Bridge dummy is currently hand-waved; any
delegated-play variant (Whist with a dummy, Doppelkopf "Re"
announcements) will need it.
**Ready now:** Bridge is one clear case; the provisional design
has been in the file for several iterations.
