# Terminal play: a seat's view, read by a person

*Design note for epic #613, covering what a seat's view shows, what answers for
a seat, and the session `cardlang play` runs. The settled rulings are in
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
the same value, for the same reason.

The text lives in its own package because its output is not the OpenSpiel
contract. The information state sits in the Interop package because its string
*is* that contract. The text is for a person, and the session that seats a
person shows it from the same package (`cardlang/play/session.py`).

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

## What answers for a seat

A [Seat Policy](../glossary/seat-policy.md) answers for one seat at a decision
node (`cardlang/openspiel/seat_policy.py`). It is handed the seat's Seat View
and the legal action ids, and it answers one of the ids. It reads the value the
text renders, for the same reason: its signature is its whole input.

A line of play is the adapter's own `(seed, history)`, played on
(`replay.LiveLine`). The recorded picks replay through `ReplayChooser`. Past
them the chooser asks the deciding seat's policy instead of pausing, and hands
it the Seat View derived inside the Chooser call, as `demo --view` derives the
text. A decision node would hand it less: the world there has unwound past
every phase frame and already run each `after_each` (issue #612). The line
refuses an answer that is not one of the legal ids before it is played.

One seed and one history name one line, however it was reached. The game's
generator comes from `replay.generator_for` and no policy draws from it, and
the uniform opponent (`UniformSeatPolicy`) draws from a digest of its seed and
the view it is handed. A line cut at any pick and played again therefore
reaches the same line, which is what taking back a pick and resuming a line
need.

An [Opponent](../glossary/opponent.md) is a Seat Policy a person seats by name.
The opponent table (`seat_policy.OPPONENTS`) holds each one, with a line saying
what it does and how it is built from the session's seed. It sits beside the
type in the Interop package because an opponent's input and output are that
boundary's currency, and because a later arena that benchmarks an opponent
must seat the same object a person plays against. `first` answers the lowest
legal id, which is the first item on a person's menu. It is a baseline that
answers the same way every time, so a table where every seat takes the first
item can repeat one exchange until the game's `max_length` refuses it (issue
#698; what the bound means for a legally unbounded line is
[open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md)).

`ranked` is the opponent that plays (`openspiel/ranked.py`). It reads the seat's
view and the game's own declarations and nothing else: the declared ranking
orders its cards, the `winner:` clause says which way the score runs, and the
library type of a zone says which of the view's cards are the trick's and which
are its own. A card of the declared `trump:` suit takes a
trick the suit led cannot. What it does with each block of action ids is a table
beside it, and the blocks it does not rank it draws, which the table states — an
offering's two sides are not distinguishable from anything a game declares today
(issue #703), so it draws there rather than guessing. So are the cards of a game
that declares a `trick_order { }` of its own, whose trumps and strengths are
expressions this reads nothing of. That is why Tichu, whose calls
are exactly that decision, is played as a uniform draw plays it.

The pin is `tests/test_live_line.py`. Along every registered game's line, at
sampled picks, the line asks the seat the adapter's replay pauses at, over the
same legal ids, with the same zones and log. Cut anywhere and played again, it
reaches the same line. Both routes read `sequential_decisions` and
`ActionSpace.match`, so the pin tells the live extension and the generator
discipline apart from the adapter, not the decomposition they share.

A game's identity is `pipeline.game_identity`, a digest of its checked program.
A reformatted or moved copy keeps its identity; an edit to the game, or to a
library it uses, changes it. It is what ties recorded action ids to the game
they were recorded in.

## The session

`cardlang play` seats a person at one seat (`cardlang/play/session.py`). The
session is a line of play and nothing else: its state is `(seed, history)`,
played on through `replay.LiveLine`, and the person is one Seat Policy among the
seats'. At each of their decisions they are shown the text of the Seat View
their seat is handed, with only the latest lines of its log, and a menu that
numbers the legal action ids by `ActionSpace.to_string`, the strings the adapter
and every agent read. The whole text is one keypress away. Every other seat
plays the opponent named for it, built from the session's seed, and the header
names each.

A running game stops only by an exception unwinding it, so a person's controls
travel through their seat as one, the way `ChooserAbort` suspends the adapter's
replay. Taking a pick back plays the line again from the history before the
person's last pick, which asks them again where they made it. The opponents'
picks up to it replay unchanged, because a policy's answer is a function of its
seed and its view. Leaving ends the line where it stands.

A saved session holds the history with the seed, the seat, each other seat's
opponent, the game's identity and a format number. It is written before each of the person's decisions and
whenever the session stops, so a session that dies at a prompt still has the
line up to that decision; a save that cannot be written ends the session with
that refusal, and the file keeps the save before it. Saving replaces a file
only when it holds a saved session, so a path that names the game file is
refused. Resuming refuses a format it does not read, a game whose identity
differs, opponents that do not fill the other seats, and a flag that
contradicts the file, all before anything is dealt.
The history replays through the replay chooser, which refuses a pick that is
not an action id or that the game does not offer. The action ids cross out of
the Interop package here deliberately: a saved session is a recorded history,
and recorded picks have one reader.

A game that refuses mid-session reaches the person as the refusal `demo` would
print, naming who picked for each seat, with the picks before it saved. A game
whose decisions the action space cannot number is refused before it is dealt.

The session shows no more of a decision than the adapter's strings carry
(issue #682). A pick asked while another decision is being made shows as a
decision of its own, with nothing saying it belongs to the other (issue #605).
A choice from a zone the seat cannot see lists the cards the zone holds, as the
adapter's legal actions do (issue #281).

The pin is `tests/test_play_session.py`: every input a person gives, a control
or otherwise, at each place a prompt stands; the flags and the seat range; the
saved files a person most plausibly hands `--resume`; each kind of path the
options that name a file can be handed; and, over every registered game, the
text and menu shown at each of the person's decisions.

## Naming the opponents

A person names who plays each seat they do not take with `--vs WHO=OPPONENT`
(`cardlang/play/opponents.py`). Each item takes one `--vs`. WHO is a seat
number, `all` or `rest`, and OPPONENT is a name in the table:

- `--vs all=random` seats one opponent at every other seat, and stands alone;
- `--vs 1=first --vs 2=random --vs 3=random` names each seat;
- `--vs 1=first --vs rest=random` names seat 1 and fills the seats not numbered.

The flag repeats, one item to each, rather than taking a comma-separated list:
an opponent's argument can hold a comma (the `chat:` seat
`experiments/game-to-artifact-plan.md` plans carries a whole command), and a
list would split it. An item is read on its own when the command line
is parsed, so a malformed item is a usage error. How the items seat the table
depends on the game and the person's seat, so those refusals come after the
game is loaded, in the order a table is set: the game, the person's seat, the
saved game being resumed, the opponents, and last the file saved to.

The items give every other seat exactly one opponent, or they are refused
before anything is dealt. A person's own seat, a seat the game does not have, a
seat named twice, `all` beside another item, `rest` twice, `rest` with no seat
numbered beside it, and `rest` with no seat left to fill are each refused,
naming what to change. The order of the items does not matter.

There is no default opponent. A game with other seats and no `--vs` is refused
before it is dealt, naming the seats that need one, a command that seats them
(the person's own options, with `all=random` or, beside a partial composition,
`rest=random`), and every opponent. Seats filled with no word from the person
would make a choice nobody made, and the game would be judged against it. A
game of one seat takes no `--vs`.

A saved session records each other seat's opponent by name, never as `all` or
`rest`, so resuming seats them with no `--vs`. A `--vs` beside `--resume` that
names the same opponents, however they are spelled, is accepted; one that names
others is refused, naming what the file records. A file whose recorded
opponents are edited replays the recorded picks and then plays on against the
edited ones, and nothing can detect the edit. A session saved in format 1,
which records no opponents, is refused with that reason rather than resumed
against `random`, so only one format is ever read.

In a team game a partner's seat is filled by an opponent too. The word is the
flag's, and it says nothing about which side a seat is on.

The pin is `tests/test_play_opponents.py`. It covers:

- every item spelling across seat numbers, selectors and names;
- each composition at a table of each size a registered game seats, with the
  person at the first seat and the last;
- `--vs` beside `--resume`;
- the order in which each refusal meets its neighbours.

It also carries two oracles that run the opponents themselves. `first` at one
seat plays the line a person picking the first item plays at another, over
every registered game. `all=random` plays the line recorded for a uniform draw
at every other seat.

## What builds on this

- **The rule-based opponent (#553).** A row in the opponent table. A policy
  reads the Seat View, never the node, so the value this text renders is the
  policy's whole input.
- **Structured payloads (#666).** Events that carry zone addresses and cards
  rather than their renderings let a rendering name a zone's owner and order a
  logged group of cards by the game, with no parsing.
