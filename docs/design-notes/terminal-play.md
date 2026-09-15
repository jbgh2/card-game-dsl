# Terminal play: a seat's view, read by a person

*Design note for epic #613, covering what `cardlang demo --view` shows today
and how `cardlang play` builds on it. The settled rulings are in
[decisions.md](../decisions.md), "A seat's knowledge, rendered". The stage
sequence is the plan, [plans/2026-09-06-terminal-play.md](../plans/2026-09-06-terminal-play.md).*

## One derivation, and renderings beside it

What a seat knows is derived once, as a [Seat View](../glossary/seat-view.md)
(`cardlang/openspiel/infostate.py`, `derive`): its zones through their declared
projections, the public state variables, and its own observation log. There
are two renderings of that value:

- the **information state**, the string OpenSpiel keys a seat's information
  set on (`render_information_state`);
- the **text a person reads** (`cardlang/play/view.py`, `render_view`), which
  `cardlang demo --view SEAT` prints.

A renderer takes a Seat View and the game's own declarations, never the
[World](../glossary/world.md), so the most it can show is what the seat knows.
The type enforces that, not a reviewer. A policy that chooses for a seat reads
the same value, for the same reason (#617).

The text lives in its own package because its output is not the OpenSpiel
contract. The information state sits in the Interop package because its string
*is* that contract. The text is for a person, and the session that seats a
person (#616) builds on it in the same package.

## What the text shows

- **Whose view it is**, with a turn line when the decision at this position is
  the seat's own.
- **Every zone** as its projection answers: the cards themselves, a count, or
  unseen. Cards show in the game's own order: suit by suit in the deck's order,
  and within a suit by the game's `ranking:` from the highest, or in the deck's
  order where the game declares no ranking. A card the declarations do not name
  sorts after every card they do. Zones appear under their labels (`hand[2]`),
  in the Seat View's order, never regrouped by owner. Grouping them would mean
  reading a seat out of a label, and no rendering derives a fact by parsing one
  (issue #666).
- **Every public state variable**, spelled as the information state spells it
  (`render_state_variable`).
- **The whole observation log**, one line per event (`cardlang/play/events.py`).
  Each kind of event has a line, and each line spells every field its kind
  carries. Labels and card renderings appear as the event carries them. A group
  of cards is bracketed, and a flag or an absent choice is written `true`,
  `false` or `none`, words no declaration may take. So no two distinct events
  read alike, and the text never shows two different logs as one.

## What the text leaves to its caller

A Seat View holds no facts about the decision being made: which decision this
is, whose it is when it is another seat's, and what can be chosen. The text
shows exactly one of them, the seat's own turn, because the swap proof holds
it: worlds the deciding seat cannot tell apart give that seat the decision in
both. Everything else belongs to the caller, which shows it beside the text.
`demo` prints it on its own header line, as narration of the playout rather
than as anything the seat knows. The session adds the menu. Showing a seat
whose turn it is at another seat's decision, or the decision's number, needs a
proof of its own first.

Two more facts wait for a structural source. The phase a decision belongs to
reaches no renderer through the Chooser (issue #605). A hand number has no
marker the engine keeps (issue #573).

The certified rendering is the whole log. A seat with perfect recall knows
every event, so a text showing only the latest ones would hide what the seat is
entitled to see. A window onto recent events is a presentation choice for the
session, and the rest of the log stays one keypress away.

## How the text is certified

**The load-bearing pin** is the per-visible-fact soundness matrix, with the
text as the rendering under test (`tests/test_play_view.py`). It runs from
inside the Chooser, along one seeded line of every registered game, for every
seat. The matrix:

- changes each zone the seat sees and each state variable, and requires the
  text to change;
- changes a hidden zone's content and requires the text not to change;
- perturbs every field of every event, deletes each event, swaps neighbouring
  events and appends one event of each kind, and requires a change each time.

The per-field probes come from the declared payload table
(`observe.EVENT_PAYLOADS`, perturbed through `PAYLOAD_PROBES`), never from how
one rendering spells an event. That is what lets one matrix certify a string
and a text alike. Three plants show the pin catches what it exists to catch: a
text that drops a zone the seat sees, an event line that drops a field, and a
text showing only the latest events.

The pin runs inside the Chooser, which is where `demo` renders, because every
phase frame still stands there. The adapter's decision nodes see a World
unwound past those frames, and they drop the phase-local state variables
(issue #612).

**The secondary check** is the readiness battery's swap proof, which holds the
text equal across a hidden swap beside the information state. It covers only
the leak direction: a text that showed nothing would pass it too.

**The regression pin** is a byte-for-byte golden of every registered game's
first decision as each seat reads it (`tests/test_play_view_format.py`). It
catches a change to the text's arrangement. It says nothing about whether the
arrangement is a good one.

## What builds on this

- **The session (#616).** `cardlang play` seats a person against opponents they
  choose. It shows this text with the menu and the turn beside it, and it lands
  the type the person and every opponent implement.
- **The policies that choose for a seat, and how a caller names an opponent
  (#617), then the rule-based policy (#553).** A policy reads the Seat View,
  never the node, so the value this text renders is the policy's whole input.
- **Structured payloads (#666).** Events that carry zone addresses and cards
  rather than their renderings let a rendering name a zone's owner and order a
  logged group of cards by the game, with no parsing.
