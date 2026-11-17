"""The authoring benchmark's prompt, and the reading of a reply.

`build_prompt` takes the task text, the reference documents (each a label
and its text), the game's rules text, and the history of earlier rounds: the
rig's words for each as strings, and each reply's content blocks as the
model returned them. It is handed no path and reads no file, so what reaches
a model is exactly what its caller put in those arguments, and the
leak-freeness of a run is a property of which files the caller reads
(`author_run.context_files` refuses the target's own corpus files) plus this
function's purity.

The prompt is a `Conversation`, cache-shaped. The first user turn is the
static part, one block for the task and the reference documents and one for
the game, then the request for file 1. Each earlier round appends two
turns: the model's reply as an assistant turn, replayed unchanged, and the
rig's answer as a user turn, which is the checker's words verbatim for a
draft, or why the reply held no file, then the request for the next file.
A reply with no content to replay has no assistant turn. Each round's
conversation extends the one before it turn for turn, so the breakpoint on
its last block lets round k+1 read what round k wrote.

Contract
--------
Assumes: every argument is the text or the reply content it names; nothing
here touches a file, the corpus or a game object.
Establishes: a deterministic `Conversation` that is a pure function of its
arguments, and `read_reply` mapping a reply to exactly one `ReplyKind`.
Illegal after: a prompt-side read of any file, or of anything but the
arguments.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from cardlang.extract import extract_blocks

from .prompts import Conversation, Turn

#: The line a model ends an attempt with when the language cannot say a
#: rule. What follows it is recorded as the rule the model could not write.
GIVE_UP: Final = "CANNOT EXPRESS:"

#: Fence info strings a draft may carry: the language's own name, or none.
DRAFT_INFOS: Final[frozenset[str]] = frozenset({"cardlang", ""})

TASK_TEXT: Final = """\
You are writing one card game as a Cardlang game file. Cardlang is a language
for describing card games so that a checker can verify them and the games can
be played by people and by game-playing programs.

Below are the language's guide for game authors (docs/authoring.md), reference
files from the same repository, and then the rules of the game to write.

HOW THIS WORKS

You write the complete file. It is saved as `game.cardlang` and checked with

    cardlang check game.cardlang

and everything the checker prints is shown to you. You then write the next
complete file, and so on, for at most {rounds} replies in all; a reply that
holds no file still counts as one. The checker prints nothing when the file
is correct; that ends the task.

WHAT TO WRITE

Write the whole game the rules describe, for the variant and player count
named. Do not leave a rule out, simplify one, or substitute an easier variant
to make the file check: a file that checks but describes a smaller game is a
failure, not a success. If you conclude that the language cannot express a
rule, stop and reply with a line that starts

    {give_up} <the rule, and the construct the language lacks for it>

instead of a file.

HOW TO ANSWER

Reply with the complete file in ONE fenced block:

```cardlang
game ... {{
  ...
}}
```

Only the fenced block is read. Anything outside it is ignored.
"""


def task_text(rounds: int) -> str:
    """The task, for a round limit of `rounds` drafts."""
    if rounds < 1:
        raise ValueError(f"a round limit is at least one draft, not {rounds}")
    return TASK_TEXT.format(rounds=rounds, give_up=GIVE_UP)


@dataclass(frozen=True)
class Reference:
    """One reference document as the model is shown it."""

    label: str
    text: str


@dataclass(frozen=True)
class GameBrief:
    """The game to write, as the model is shown it."""

    name: str
    variant: str
    source_url: str
    rules_text: str


@dataclass(frozen=True)
class RoundView:
    """One earlier round as the next prompt carries it: the reply's content
    blocks, and the draft with what the checker said, or why the reply held
    no draft."""

    number: int
    draft: str | None
    said: str
    exit_code: int | None = None
    reply: tuple[Any, ...] = ()


def _references_block(task: str, references: Sequence[Reference]) -> str:
    parts = [task, "\n"]
    for ref in references:
        parts.append(f"===== {ref.label} =====\n\n{ref.text.rstrip()}\n\n")
    return "".join(parts)


def _game_block(game: GameBrief) -> str:
    return (
        "===== THE GAME TO WRITE =====\n\n"
        f"Game: {game.name}\n"
        f"Variant and players: {game.variant}\n"
        f"Rules source: {game.source_url}\n\n"
        f"{game.rules_text.rstrip()}\n\n"
    )


def _answer(view: RoundView) -> str:
    if view.draft is None:
        return f"That reply held no file: {view.said}\n\n"
    said = view.said if view.said else "(nothing)"
    return f"$ cardlang check game.cardlang   (exit {view.exit_code})\n{said}\n\n"


def _request(number: int) -> str:
    return f"Write file {number}: the complete game, in one ```cardlang block.\n"


def build_prompt(
    task: str,
    references: Sequence[Reference],
    game: GameBrief,
    history: Sequence[RoundView],
) -> Conversation:
    """The conversation that asks for the next draft.

    Pure by signature: the rig's strings and the model's own earlier replies
    in, one `Conversation` out.
    """
    first = (_references_block(task, references), _game_block(game), _request(1))
    turns = [Turn("user", first)]
    for view in history:
        if view.reply:
            turns.append(Turn("assistant", tuple(view.reply)))
        turns.append(Turn("user", (_answer(view), _request(view.number + 1))))
    return Conversation(turns=tuple(turns))


class ReplyKind(Enum):
    """What a reply was."""

    DRAFT = "draft"
    GAVE_UP = "gave_up"
    #: No fenced block, or more than one.
    NO_DRAFT = "no_draft"
    #: The reply was cut off at the output limit; never read as a draft.
    TRUNCATED = "truncated"
    #: The API declined the request (`stop_reason` "refusal"); whatever
    #: text came back is never read.
    DECLINED = "declined"


@dataclass(frozen=True)
class ReadReply:
    kind: ReplyKind
    draft: str | None = None
    reason: str = ""


def read_reply(text: str, stop_reason: str | None) -> ReadReply:
    """What a reply holds: a draft, a give-up, or the reason it is neither."""
    if stop_reason == "refusal":
        return ReadReply(ReplyKind.DECLINED, reason="the API declined the request")
    if stop_reason == "max_tokens":
        return ReadReply(
            ReplyKind.TRUNCATED,
            reason="the reply was cut off at the output limit before it ended",
        )
    for line in text.splitlines():
        if line.strip().startswith(GIVE_UP):
            return ReadReply(ReplyKind.GAVE_UP, reason=line.strip()[len(GIVE_UP) :].strip())
    blocks = [b for b in extract_blocks(text, "reply") if b.info in DRAFT_INFOS]
    if len(blocks) == 1:
        return ReadReply(ReplyKind.DRAFT, draft=blocks[0].text)
    if not blocks:
        return ReadReply(ReplyKind.NO_DRAFT, reason="no ```cardlang block was found")
    return ReadReply(
        ReplyKind.NO_DRAFT,
        reason=f"{len(blocks)} ```cardlang blocks were found, and only one file is read",
    )
