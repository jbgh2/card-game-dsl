"""The Diagnostic Codes: what kind of fix a refusal asks of its author.

Every refusal the checker, the command line or the runtime makes carries one
[[diagnostic-code]] from this registry, so a tool reading a Diagnostic Record
(`cardlang.records`) can tell one refusal from another without reading its
sentence. A code names the kind of fix, in the designer's words: two
refusals share a code exactly when the corrective act they ask for is the
same kind, whatever their wording and wherever they are raised.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      nothing; this module is the registry's one definition site.
Establishes:  `Code` is the closed set of Diagnostic Codes; each member
              carries its spelling (`slug`) and its one-line meaning, read
              together, and a member's spelling never changes once shipped.
Now illegal:  a `Diagnostic` built without a code (`code` is a required
              field, so the type checker refuses it); a shipped code renamed,
              removed, or its meaning changed (tests/test_diagnostic_codes.py,
              the blessed list of spellings and meanings); a code no witness
              tells (the witness grid); and a rejection case's refusal moving
              to another code (each case's code golden).
Held by:      Unrepresentable for "every refusal has a code"; Derived and
              Pinned for a code's stability, since a spelling a tool keys on
              lives outside the type checker. A report site no rejection case
              reaches can change its code with no pin reddening.
"""

from __future__ import annotations

from enum import Enum


class Code(Enum):
    """A Diagnostic Code: its spelling, and what the author must do."""

    def __init__(self, slug: str, meaning: str) -> None:
        self.slug = slug
        self.meaning = meaning

    # --- the text and the files -------------------------------------------
    SYNTAX_ERROR = ("syntax-error", "the text does not read as the language; fix it where the message points")
    MISSPELLED_KEYWORD = ("misspelled-keyword", "a word nearly spells a keyword the language expects there; write the keyword")
    WRONG_SPELLING = ("wrong-spelling", "the language spells this construct another way; write the spelling the message gives")
    ONE_GAME_PER_FILE = ("one-game-per-file", "a source holds exactly one `game { }` block; add it, or move the others to their own files")
    ONE_FENCED_BLOCK = ("one-fenced-block", "a Markdown game file holds its game in exactly one fenced block")
    WRONG_FILE_EXTENSION = ("wrong-file-extension", "a game file's name ends in an extension the checker reads; rename the file")
    UNKNOWN_COMMAND = ("unknown-command", "the first word names no command and no file; write a command or a path")
    UNREADABLE_FILE = ("unreadable-file", "the file named cannot be read as text; name a readable game file")

    # --- names ------------------------------------------------------------
    UNKNOWN_NAME = ("unknown-name", "a name nothing in scope declares, refused where the checker cannot tell which sort of name was meant; read the suggestions, spell a declared name, or declare it")
    UNKNOWN_ZONE = ("unknown-zone", "a zone no `zones { }` entry declares; spell a declared zone, or declare it")
    UNKNOWN_STATE_VARIABLE = ("unknown-state-variable", "a state variable no `state { }` block declares; spell a declared one, or declare it")
    UNKNOWN_FUNCTION = ("unknown-function", "a function neither the game nor the language defines; spell a defined one, or define it")
    UNKNOWN_PROCEDURE = ("unknown-procedure", "a procedure the game does not define; spell a defined one, or define it")
    UNKNOWN_RULE = ("unknown-rule", "a rule no definition or library provides; spell a defined rule, or define it")
    UNKNOWN_MOVE_TYPE = ("unknown-move-type", "a move type the game does not declare; spell a declared one, or declare it")
    UNKNOWN_PHASE = ("unknown-phase", "a phase that is not where the construct looks for it; name a phase that is")
    UNKNOWN_MODE = ("unknown-mode", "a mode that is not a sibling of this phase's modes; name one that is")
    UNKNOWN_OUTCOME = ("unknown-outcome", "an outcome phase or case the game does not declare; name a declared one")
    UNKNOWN_RANK = ("unknown-rank", "a rank the game's deck does not have; write one of its ranks")
    UNKNOWN_SUIT = ("unknown-suit", "a suit the game's deck does not have; write one of its suits")
    UNKNOWN_DECK = ("unknown-deck", "a deck or piece set the language does not ship; name a shipped one")
    UNKNOWN_LIBRARY = ("unknown-library", "a family library that does not exist; name one in docs/libraries/")
    UNKNOWN_TYPE = ("unknown-type", "a type name the language does not have in that position; write one it has")
    UNKNOWN_ZONE_TYPE = ("unknown-zone-type", "a zone type the language does not have; write one it has")
    UNKNOWN_INDEX_DOMAIN = ("unknown-index-domain", "an index domain, owner or position domain nothing declares; name one that exists")
    UNKNOWN_FIELD = ("unknown-field", "a field the value does not have; read one of its fields, or read it another way")
    UNKNOWN_TURN_DIRECTION = ("unknown-turn-direction", "a turn direction the language does not have; write one it has")
    UNKNOWN_ROUND_FUNCTION = ("unknown-round-function", "a round names a winner or predicate the language does not have; name one it has")
    UNKNOWN_PLAY_SHAPE = ("unknown-play-shape", "a play shape no row of the game's catalogue labels; write a row's label")
    UNKNOWN_PRIMITIVE = ("unknown-primitive", "a `primitives` entry nothing implements; name an implemented Primitive")
    UNKNOWN_BOARD = ("unknown-board", "a board the language does not have; write a board it has")
    RESERVED_WORD = ("reserved-word", "the name is a word the language reserves; pick another name")
    NAME_TAKEN = ("name-taken", "two things share one name, or one hides another; rename one")
    WRITTEN_TWICE = ("written-twice", "one thing is written more than once; keep one")
    WRONG_SORT_OF_NAME = ("wrong-sort-of-name", "the name is of another sort than the position takes; use a name of the right sort")

    # --- what a game declares ---------------------------------------------
    MISSING_DECLARATION = ("missing-declaration", "something reads a declaration the game does not make; add it")
    UNUSED_DECLARATION = ("unused-declaration", "a declaration nothing reaches; use it, or delete it")
    HAS_NO_EFFECT = ("has-no-effect", "something written changes nothing; drop it, or write what was meant")
    CONFLICTING_CLAUSES = ("conflicting-clauses", "two clauses cannot stand together; keep one of them")
    OUT_OF_PLACE = ("out-of-place", "a clause or statement written where it cannot stand; move it where it belongs")
    NOT_YET_SUPPORTED = ("not-yet-supported", "the language cannot express this yet; write the game another way until it can")
    OUT_OF_RANGE = ("out-of-range", "a number outside the values the position allows; write one inside them")
    PIECES_ARE_NOT_CARDS = ("pieces-are-not-cards", "a card's rank, suit or points read in a game played with pieces")
    DECK_TOO_SMALL = ("deck-too-small", "the deck holds fewer cards than a hand deals from it")
    BOARD_SHAPE = ("board-shape", "a board declaration the board cannot be laid out from; fix the board's shape")

    # --- types and values -------------------------------------------------
    TYPE_MISMATCH = ("type-mismatch", "a value of another type than the position needs; write a value of that type")
    UNTYPED_VALUE = ("untyped-value", "a value whose type the checker cannot know where an exact type is needed; make its type plain")
    WRONG_ARGUMENT_COUNT = ("wrong-argument-count", "a call, a rule or a zone type is given more or fewer arguments than it takes")
    WRONG_ARGUMENT = ("wrong-argument", "an argument of a shape the position does not take; write the shape the message gives")
    WRONG_SIGNATURE = ("wrong-signature", "a definition's parameters or result differ from what its role requires")
    WRONG_SUBSCRIPT = ("wrong-subscript", "a zone or variable subscripted the wrong way, or not subscripted where it must be")
    TYPE_NOT_ALLOWED_HERE = ("type-not-allowed-here", "a type the language allows only in another position; spell it there")
    CONSTANT_CONDITION = ("constant-condition", "a condition that is always true or always false; write the test that was meant")
    NEEDS_PARENTHESES = ("needs-parentheses", "the text reads another way than it seems; add parentheses to say which")

    # --- who reads what, and when -----------------------------------------
    OUT_OF_SCOPE = ("out-of-scope", "something read where it does not exist; read it where it is declared, or pass it in")
    NO_PLAYER_ACTING = ("no-player-acting", "the acting player is named, or a decision made, where no player is acting")
    READS_BEYOND_PARAMETERS = ("reads-beyond-parameters", "a function or procedure reads what its parameters do not pass it")
    RECURSIVE_FUNCTION = ("recursive-function", "a function calls itself, directly or through others")
    ANSWER_READS_BEYOND_THE_CARD = ("answer-reads-beyond-the-card", "an answer the engine asks of a card reads more than the card and public state")
    ANSWER_CALLS_LATER_ANSWER = ("answer-calls-later-answer", "a Trick Order function calls one that comes after it in the Trick Order")
    DECIDES_ON_HIDDEN_CARDS = ("decides-on-hidden-cards", "a seat must check or pick from cards it cannot see; read cards it sees, or announce them")
    WRONG_ZONE_VISIBILITY = ("wrong-zone-visibility", "a zone's type hides cards that the construct needs every seat, or its owner, to see")
    HOSTED_POLL_READS_UNPUBLISHED_STATE = ("hosted-poll-reads-unpublished-state", "a Hosted Poll reads Round State that is not yet published")
    NOT_WRITABLE = ("not-writable", "the target is not a state variable this text may write")

    # --- family libraries -------------------------------------------------
    LIBRARY_REQUIREMENT_UNMET = ("library-requirement-unmet", "the game lacks what a library it uses requires; add it to the game")
    REQUIREMENT_MISMATCH = ("requirement-mismatch", "the game declares what a library requires, but not as the library requires it")
    REQUIREMENT_MATCHES_SEVERAL = ("requirement-matches-several", "a library requirement matches several of the game's declarations; keep one")
    OUTSIDE_LIBRARY_CONTRACT = ("outside-library-contract", "library text reads a name it neither defines nor requires; define it, or require it")
    LIBRARY_REACHES_ONE_GAME = ("library-reaches-one-game", "library text names what belongs to one game; take it as a parameter or a requirement")
    BAD_REQUIRES_ROW = ("bad-requires-row", "a `requires` row the library cannot ask for in that form; write the row the message gives")
    REQUIRES_WHAT_IS_PROVIDED = ("requires-what-is-provided", "a library requires what a library already provides or defines; drop one of the two")
    LIBRARY_NOT_YET_PROVEN = ("library-not-yet-proven", "no game yet checks clean reaching this library text, so its refusal stands in the library's file")

    # --- the game's structure ---------------------------------------------
    RULE_NEVER_CONSULTED = ("rule-never-consulted", "a rule no decision ever asks; constrain a move type a trick round offers, or write the condition elsewhere")
    NEEDS_A_TRICK_ROUND = ("needs-a-trick-round", "a construct only a trick round reads, in a game or phase with none")
    MODE_PAIRING = ("mode-pairing", "modes whose transitions do not pair one condition with its far side")
    CLIMB_ROUND_QUERIES = ("climb-round-queries", "a climbing round's queries that do not belong together; name one engine's pair")
    CHOOSE_INTEGER_BOUNDS = ("choose-integer-bounds", "a `choose integer` whose bounds offer no value, or no fixed ceiling")
    TEAMS_MUST_PARTITION_SEATS = ("teams-must-partition-seats", "`teams:` must put every seat on exactly one team")
    USE_WINNER_NOT_LOSER = ("use-winner-not-loser", "`loser:` cannot decide this game's result; rank a score with `winner:`")
    UNRANKABLE_WINNER_TARGET = ("unrankable-winner-target", "`winner:` ranks something that is not a score each player or team holds")
    RANKING_INCOMPLETE = ("ranking-incomplete", "a ranking leaves out ranks or suits it must order; list them all")
    CATALOGUE_ROW_NAMES_NO_PLAY = ("catalogue-row-names-no-play", "a combination catalogue row no cards of the deck can make")
    AMBIGUOUS_PLAY_SHAPE = ("ambiguous-play-shape", "one play fits two rows of the catalogue; settle it in the rows")
    CARD_PLAY_PARAMETERS = ("card-play-parameters", "a card play's parameters or offering would make two plays look alike")
    DEAL_DISTRIBUTION = ("deal-distribution", "an even deal written with an amount or destination it cannot distribute")
    WRONG_ZONE_SHAPE = ("wrong-zone-shape", "a single zone where a zone per player is needed, or the reverse")
    WRONG_PRIMITIVE_TYPE = ("wrong-primitive-type", "a `primitives` entry spells a type no Primitive implementation takes")
    MISSING_OUTCOME_ARM = ("missing-outcome-arm", "a `produces:` block leaves an outcome case unhandled")
    OUTCOME_READ_BEFORE_PRODUCED = ("outcome-read-before-produced", "an outcome is consumed before the phase producing it has run")

    # --- play time and the installation -----------------------------------
    REFUSED_DURING_PLAY = ("refused-during-play", "a rule only a playout reaches refused the game")
    GAME_ERROR_RAISED = ("game-error-raised", "the game's own `error(...)` refused a move no player was offered")
    ENGINE_GAP = ("engine-gap", "the engine refused what an earlier check should have refused; the engine must change")
    INCOMPLETE_INSTALLATION = ("incomplete-installation", "the checkout is missing files the engine loads; reinstall it")
    UNREGISTRABLE_GAME = ("unregistrable-game", "a game file offered for registration cannot be registered by that name")

    # --- asking the checker a question ------------------------------------
    POSITION_OUTSIDE_THE_FILE = ("position-outside-the-file", "a line or column before the file's first, or past the end of its line or of the file; give a position inside the text")
    POSITION_OUTSIDE_THE_GAME = ("position-outside-the-game", "a position in a comment, a blank line or prose that no part of the game holds; point inside the game's text")
    NOT_AN_EXPRESSION = ("not-an-expression", "the position is on a statement or a declaration, which has no value; point at an expression inside it")
    EXPRESSION_NOT_TYPED = ("expression-not-typed", "the checker reads this expression without working out its own type; ask about the expression around it")
    NOTHING_SEEN_HERE = ("nothing-seen-here", "nothing at this position moves a card or asks a seat; point at a movement or a decision")
