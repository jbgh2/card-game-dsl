"""Pins the reference-slot registry — the one table saying what every `str`-typed
field of every `n.Node` holds — to the AST's actual fields.

Most name-carrying slots hold a `NameRef`, which `resolve._rewrite` classifies
once and every consumer then reads off `ref_kind`. A minority hold their name as
a plain string, and a pass built on `NameRef` is structurally blind to those.
The blindness is not a design boundary: it is whichever consumer forgot the slot
exists, which is how a family library could reach past its `requires` contract
through `turns … again <var>` while the wall next door reported the property
proven (issue #138).

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property: every `str`-typed field of every AST node carries exactly one
          classification, and the classification set is exhaustive — no field
          can exist unclassified, and no classification can name a field that
          does not exist.
domain:   every (dataclass, field) pair in `cardlang.ast.nodes` that can HOLD a
          string — bare `str`, `str | None`, `tuple[str, ...]`, a union with
          `str` among its members (`Transfer.amount`), and a `Literal` of
          strings (`Game.content_flavor`, annotated `Flavor`). The predicate is
          "can hold", not "mentions `str`": the second spelling shipped first
          and silently excluded the `Literal` member while this ledger claimed
          no field could be excluded.
registry: the AST module itself, introspected. `tests/test_node_registry.py`
          owns the prior link in the chain — that `n.Node` is exactly the
          module's dataclasses — so this module derives its node axis from the
          union and inherits that pin rather than repeating it.
covered:  the full membership equation, both directions, plus pairwise
          disjointness of the seven kinds. The SHAPE column is derived here and
          checked against `resolve.slot_strings`, so the extraction is total by
          construction rather than by the reader believing the annotations were
          read. The gap between "holds a string" and "names `str`" is swept as
          its own class (`test_the_string_valued_class_is_swept_not_patched`)
          and pinned at its members, so widening the domain means widening the
          predicate rather than adding a row.
sampled:  none.
residual: ONE, and it is worth stating in the shape a reader can act on rather
          than as a caveat.

          The SEMANTIC column is authored, not derived, and cannot be otherwise
          — `str` is `str`, and what a slot MEANS is not in its annotation. What
          is derived is the KEY set and the shape column. Stated because "derived
          and pinned" would otherwise read as a claim the classification itself
          is derived.

          WHAT THE EXPOSURE IS: mis-classification, never omission. A slot
          cannot be missing — the derived domain and the membership pin make that
          impossible — so the surviving risk is a slot filed under the wrong kind
          or namespace: something called `keyword`, `binder` or `opaque` that is
          in fact a game-fed reference. That is precisely the original defect
          (issue #138) surviving in a single cell, and a library author would
          meet it exactly as before. A namespace that does not exist at all is
          caught here (`test_every_namespace_is_named`); a wrong-but-real one is
          caught by the consumer grids in `tests/test_family_libraries.py`, and
          only for slots those grids reach.

          WHAT HAS CLOSED, and what has not. The second family library landed
          (`docs/libraries/smuggling.cardlang`, issue #143's first item), and it
          closed part of this BY EXECUTION rather than by more checking
          machinery. Executed: the `type` slot of a `requires` entry, whose
          classification the widening to zone contracts put under real load;
          `index_domain`, whose row in `_LIBRARY_UNSWEPT` claimed the namespace
          was CLOSED and was falsified by a probe the moment a contract could
          name a zone — a library could then reach a game's `positions { }`
          domain through a contract index, and the namespace is now swept rather
          than excused; and `zone`/`zone_type_arg`, both of which went from
          unreachable to reachable and are swept.

          NOT executed, and the residual survives for them: `round`,
          `produces:`, and a struct type. Green Lane's shared core is a commit
          and a wave, and it uses none of the three; the family was not contorted
          into touching them, because a probe written to exercise a slot rather
          than to play a game is the inspection this residual exists to distrust.
          `offer` is a third case worth stating precisely: the family USES it,
          but in game text rather than library text, because the offered move is
          the one that varies. So the slot is exercised by the family and not by
          a library, which is weaker than the closer this row asked for.

          WHAT WOULD CLOSE THE REST: a library holding a `round` — a
          trick-taking family is the natural candidate, and it is the same
          witness issue #177 names. Still deliberately not closed by more
          checking machinery: re-deriving the authored column mechanically would
          re-check only the categories this module already invented, and its
          expected findings are auditor-only — the shape the planning gate routes
          to record-and-file rather than build (decisions.md, "Reachability ranks
          the work"; CLAUDE.md, "Execution finds what enumeration cannot").

The framing check (surface-totality-audit Step 1) ran against `nodes.py` and the
grammar as the definition sources, with the author's table as provisional input;
it did not run in a fresh context, so it is the weaker form of that check. That
weakness lands on the same cell as the residual above and nowhere else: the
check's job is to catch a NARROWED domain, and this domain is derived, so what
it could still have narrowed is which bucket a slot went into. Same exposure,
same closer — do not read the two as separate debts. Its
diff is what moved `NameRef.name`/`ref_kind` out of `reference` into kinds of
their own and what added `Transfer.item` as a game-fed slot. A later plant
against this module's OWN totality claim — the adversarial form, negating the
claim rather than re-reading the table — is what found the `Literal` member;
that is evidence for the plant, not for the framing check, which had passed
over it.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

import cardlang.ast.nodes as n
from cardlang.resolve import (
    STRING_SLOT_KINDS,
    _CONTEXTUAL_SLOTS,
    _BINDER_SLOTS,
    _CLASSIFIED_SLOTS,
    _DECLARATION_SLOTS,
    _KEYWORD_SLOTS,
    _METADATA_SLOTS,
    _OPAQUE_SLOTS,
    _REFERENCE_SLOTS,
    slot_namespace,
    slot_strings,
)

Slot = tuple[type, str]

# The seven kinds, as (name, the membership the registry derives it from). The
# tuple IS the closed domain: `STRING_SLOT_KINDS` is built from exactly these
# tables, so a kind added there without an entry here fails `test_the_kind_axis_
# is_the_whole_registry` rather than silently escaping disjointness.
_KIND_TABLES: tuple[tuple[str, frozenset[Slot]], ...] = (
    ("declaration", frozenset(_DECLARATION_SLOTS)),
    ("binder", _BINDER_SLOTS),
    ("reference", frozenset(_REFERENCE_SLOTS)),
    ("keyword", _KEYWORD_SLOTS),
    ("opaque", _OPAQUE_SLOTS),
    ("classified", _CLASSIFIED_SLOTS),
    ("metadata", _METADATA_SLOTS),
)


def _holds_a_string(annotation: object) -> bool:
    """Whether a field with this annotation can hold a string — the domain's
    defining predicate.

    Deliberately NOT "does the annotation mention `str`". That was the first
    spelling and it was wrong by one member: `Literal["card", "piece"]` holds a
    string and never names `str`, so `Game.content_flavor` sat outside the
    domain while the pin below claimed no field could.

    The second spelling was wrong too, and in the same shape: widening for
    `Literal` alone left `NewType("ZoneName", str)` escaping, and — because
    `_string_valued_but_not_str_annotated` shares this predicate — escaping BOTH
    views at once, which is the "two readings agreeing on being wrong" failure
    this module warns about. So the question is now asked structurally: can a
    value of this annotation BE a string. Three ways it can — the type is a `str`
    subclass, a `Literal` over strings, or a `NewType` whose base qualifies —
    plus recursion through any generic's arguments."""
    if isinstance(annotation, type) and issubclass(annotation, str):
        return True  # `str` itself, and any subclass (a `StrEnum`, a NewType's base)
    if typing.get_origin(annotation) is typing.Literal:
        return any(isinstance(arg, str) for arg in typing.get_args(annotation))
    supertype = getattr(annotation, "__supertype__", None)
    if supertype is not None:
        return _holds_a_string(supertype)  # `NewType("ZoneName", str)`
    return any(_holds_a_string(arg) for arg in typing.get_args(annotation))


def _string_slots() -> dict[Slot, object]:
    """Every `str`-mentioning field of every node kind, mapped to its
    annotation. The node axis comes from the `Node` union, which
    tests/test_node_registry.py pins to the module's dataclasses."""
    slots: dict[Slot, object] = {}
    for cls in typing.get_args(n.Node):
        hints = typing.get_type_hints(cls)
        for field in dataclasses.fields(cls):
            annotation = hints[field.name]
            if _holds_a_string(annotation):
                slots[(cls, field.name)] = annotation
    return slots


def _name(slot: Slot) -> str:
    return f"{slot[0].__name__}.{slot[1]}"


def test_the_registry_is_exactly_the_asts_string_fields() -> None:
    """The membership equation, both directions. A `str` field added to a node
    with no row here is the hole this registry exists to close; a row naming a
    field that no longer exists is a classification of nothing, which reads as
    coverage.

    red under: add a `str` field to any node in `nodes.py`, or delete a row from
    any of the seven tables."""
    derived = set(_string_slots())
    registered = set(STRING_SLOT_KINDS)
    missing = sorted(_name(s) for s in derived - registered)
    extra = sorted(_name(s) for s in registered - derived)
    assert not missing, (
        f"string-bearing AST fields with no classification: {missing} — a slot "
        f"nobody classified is a name channel no sweep can see (issue #138)"
    )
    assert not extra, (
        f"classified slots that do not exist on their node: {extra} — the row "
        f"classifies nothing, and reads as coverage"
    )


def _names_str(annotation: object) -> bool:
    """The domain's FIRST predicate, kept verbatim as the thing to diff against:
    does `str` appear anywhere in the annotation. Recursive, because the shallow
    version is wrong too — `tuple[str, ...] | None` names `str` two levels down,
    and a one-level check reports it as unannotated."""
    if annotation is str:
        return True
    return any(_names_str(arg) for arg in typing.get_args(annotation))


def _string_valued_but_not_str_annotated() -> list[str]:
    """The class the domain's first predicate missed: a field that holds a
    string while its annotation never names `str`."""
    return sorted(
        _name((cls, field.name))
        for cls in typing.get_args(n.Node)
        for field in dataclasses.fields(cls)
        if _holds_a_string(hints := typing.get_type_hints(cls)[field.name])
        and not _names_str(hints)
    )


def test_the_string_valued_class_is_swept_not_patched() -> None:
    """The domain's predicate asks what a field can HOLD, not what its
    annotation says. Those differ for exactly one shape today —
    `Literal["card", "piece"]` — and this pins the class at its members rather
    than at the instance that exposed it.

    The instance was `Game.content_flavor`, found by planting the negation of
    this module's own totality claim. The fix was the predicate, not a row: a
    row would have left the next `Literal`-typed field escaping in the same way.

    red under: drop the `Literal` arm from `_holds_a_string` — RUN, and it
    reddens this test and the membership pin together, the member leaving the
    derived domain while its registry row stays. That pairing is the point: with
    the row absent as well (the state this branch found), only this test can
    fire, because the membership pin compares two views that agree on being
    wrong."""
    members = _string_valued_but_not_str_annotated()
    assert members == ["Game.content_flavor"], (
        f"the string-valued-but-not-str-annotated class is {members} — every "
        f"member must be in the registry's domain, so widening it means "
        f"widening `_holds_a_string`, never adding a row"
    )
    for member in members:
        assert member in {_name(slot) for slot in STRING_SLOT_KINDS}


# One node per BRANCH of each contextual slot's read function. The witnesses are
# authored, but the pin below is self-enforcing in both directions: a declared
# namespace no witness produces fails, and a namespace a witness produces that
# nobody declared fails. So a thin witness set cannot quietly pass — it reddens
# until either the witness or the declaration is fixed.
_CONTEXTUAL_WITNESSES: dict[Slot, tuple[object, ...]] = {
    (n.Member, "field"): (
        n.Member(obj=n.NameRef("state"), field="score"),  # the pronoun -> state
        n.Member(obj=n.NameRef("action"), field="card"),  # any other object -> field
        n.Member(obj=n.Member(obj=n.NameRef("state"), field="a"), field="b"),
    ),
    (n.DomainQuery, "binder"): (
        # bare (`source is None`) names the domain; the collection form binds a
        # fixed noun and names nothing.
        n.DomainQuery(kind="any", binder="cell", spelled="cell", source=None, pred=n.NameRef("t")),
        n.DomainQuery(
            kind="all",
            binder="cell",
            spelled="cells",
            source=n.NameRef("lines"),
            pred=n.NameRef("t"),
        ),
    ),
}


def test_contextual_slots_declare_exactly_the_namespaces_they_return() -> None:
    """`_ContextualSlot.namespaces` is the ONLY hand-written list left in the
    registry, and it is the one the derived grid axis is computed from — so it
    is the one place a wrong entry silently widens or narrows the coverage
    domain in either direction.

    It shipped unpinned. An adversarial audit planted four disagreements — a
    declaration missing a namespace the function returns, a declaration naming
    two it never returns, and a function returning a namespace outside its
    declaration (twice, including one with a non-empty legal set, a real
    behaviour change) — and every one left the whole suite green. This test is
    that hole closed: the field exists to remove a hand-list, so it may not
    itself be an unverified one.

    red under: any of those four plants. Each now reddens here."""
    assert set(_CONTEXTUAL_WITNESSES) == set(_CONTEXTUAL_SLOTS), (
        "every contextual slot needs witnesses, or its declaration is unchecked"
    )
    for (cls, field), witnesses in _CONTEXTUAL_WITNESSES.items():
        declared = _CONTEXTUAL_SLOTS[(cls, field)].namespaces
        assert all(type(w) is cls for w in witnesses), (cls, field)
        observed = {ns for w in witnesses if (ns := slot_namespace(w, field)) is not None}
        assert observed == declared, (
            f"{cls.__name__}.{field} declares {sorted(declared)} but its witnesses "
            f"produce {sorted(observed)} — the declared set is what the grid axis "
            f"is derived from, so a disagreement moves the coverage domain silently"
        )


def test_the_kind_axis_is_the_whole_registry() -> None:
    """`STRING_SLOT_KINDS` is the union of the seven tables and nothing else, so
    a kind cannot be added to the registry without joining this module's axis
    (and therefore the disjointness check below).

    red under: add an eighth table to `STRING_SLOT_KINDS`'s construction without
    a `_KIND_TABLES` entry."""
    union: set[Slot] = set()
    for _, table in _KIND_TABLES:
        union |= table
    assert union == set(STRING_SLOT_KINDS)
    assert {kind for kind, _ in _KIND_TABLES} == set(STRING_SLOT_KINDS.values())


def test_no_slot_carries_two_kinds() -> None:
    """Each slot is classified once. Two kinds would make every consumer's
    verdict depend on which table it happened to consult — the ambiguity a
    single registry exists to remove.

    red under: add any existing slot to a second table."""
    for i, (kind_a, table_a) in enumerate(_KIND_TABLES):
        for kind_b, table_b in _KIND_TABLES[i + 1 :]:
            overlap = sorted(_name(s) for s in table_a & table_b)
            assert not overlap, f"{kind_a} and {kind_b} both claim {overlap}"


# Namespaces whose declarations live outside the AST: a stdlib registry, the
# domain table, or the deck. A reference into one of these is still a reference —
# it just cannot be answered by walking a game's nodes.
_EXTERNALLY_OWNED = frozenset(
    {
        "stdlib_move_type",
        "stdlib_query",
        "deck_rank",
        "deck_suit",
        "enum_value",
        "component_set",
        "board_family",
        "role",
        "index_domain",
        "zone_type",
        "zone_type_arg",
        "content_kind",
        "library",
    }
)


def test_every_namespace_is_named() -> None:
    """Both name-bearing kinds carry a non-empty namespace, and every namespace a
    REFERENCE slot draws from is one some DECLARATION slot fills or one the
    registry records as externally owned.

    The second half is the check with teeth: a reference into a namespace
    nothing declares is either a typo or a namespace whose owner lives outside
    the AST (the stdlib registries, the domain table, the component set). Those
    are listed, so the list is the statement — a new reference namespace must be
    classified as one or the other before it can land.

    red under: point a `_REFERENCE_SLOTS` row at a namespace spelled differently
    from its declaration, or drop one from `_EXTERNALLY_OWNED`."""
    assert all(ns for ns in _DECLARATION_SLOTS.values())
    assert all(ns for ns in _REFERENCE_SLOTS.values())
    declared = set(_DECLARATION_SLOTS.values())
    referenced = set(_REFERENCE_SLOTS.values())
    unowned = sorted(referenced - declared - _EXTERNALLY_OWNED)
    assert not unowned, (
        f"reference namespaces nothing declares and nothing owns: {unowned}"
    )




# --- the shape column, derived --------------------------------------------
#
# `slot_strings` is what every consumer uses to read a slot, so its totality is
# the extraction's completeness argument. The four shapes are derived from the
# annotations rather than listed, and each is exercised on a real node.


def _shape(annotation: object) -> str:
    """Which of the annotation shapes a slot has, read off the annotation."""
    if annotation is str:
        return "bare"
    if typing.get_origin(annotation) is typing.Literal:
        return "literal"
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) is tuple:
        return "tuple"
    if type(None) in args:
        return "optional"
    return "union"


def test_every_slot_shape_is_one_of_four() -> None:
    """The shape axis is closed. A fifth shape (a `dict[str, str]` field, a
    nested tuple) would mean `slot_strings` reads part of a slot and calls it
    the whole, which is the silent half-coverage this registry replaces.

    red under: annotate a node field as `list[str]` or `dict[str, str]`."""
    shapes = {_shape(a) for a in _string_slots().values()}
    assert shapes <= {"bare", "optional", "tuple", "union", "literal"}, shapes


def test_slot_strings_reads_every_shape_whole() -> None:
    """One real node per shape, so the reader is exercised rather than reasoned
    about. The `tuple` row is the one that matters: a consumer taking only the
    first element would see `Offer.offering`' first move type and miss the
    rest, which is coverage that looks total and is not.

    red under: make `slot_strings` return `(value,)` for a tuple slot, or drop
    its `None` guard."""
    bare = n.Call("helper", ())
    assert slot_strings(bare, "func") == ("helper",)

    unset = n.Round(
        move_type=None,
        leader=n.NameRef("p"),
        participants=n.AllPlayers(),
        source_zone=None,
        play_zone=None,
        outcome_fn=None,
        trump=None,
    )
    assert slot_strings(unset, "source_zone") == ()
    set_optional = n.Turns(
        binder="p",
        leader=n.NameRef("l"),
        participants=n.AllPlayers(),
        termination=n.NameRef("t"),
        again="flag",
        body=(),
    )
    assert slot_strings(set_optional, "again") == ("flag",)

    many = n.Offer(player=n.NameRef("p"), offering=("bid", "pass"))
    assert slot_strings(many, "offering") == ("bid", "pass")

    union = n.Transfer(
        verb="deal",
        selection_mode=None,
        amount="all",
        item="cards",
        source=None,
        dest=None,
        dest_each=False,
    )
    assert slot_strings(union, "amount") == ("all",)


def test_slot_namespace_answers_only_for_references() -> None:
    """The accessor is the registry's public face, and it must distinguish "not
    a reference" from "a reference into a namespace I forgot" — the two the
    hand-list era could not tell apart.

    red under: make `slot_namespace` fall back to a default namespace."""
    assert slot_namespace(n.Call("f", ()), "func") == "function"
    assert slot_namespace(n.Call("f", ()), "args") is None
    assert slot_namespace(n.StrLit("x"), "value") is None


def test_the_offering_rename_is_complete_in_the_package() -> None:
    """"vocabulary" is retired from `cardlang/` (issue #206, glossary section 2).

    The word had three senses in code — the OFFERING (a menu of moves presented
    to a decider), the word-stock the DSL gives designers, and assorted closed
    name-sets. Only the second survives the ruling, and it survives in DOCS:
    `principles.md`'s "the vocabulary IS the syntax" and this glossary's own
    section 5 heading. Inside the package the word is gone, which is what makes
    it grep-checkable rather than a judgment call at every future edit.

    Pinned here rather than left as an issue's acceptance line, because an
    acceptance line is checked once and a pin is checked forever: the next
    `vocab_ids` local would otherwise reintroduce the spelling silently.

    red under: put `vocab` back anywhere in `cardlang/` — a comment is enough.
    Verified.
    """
    import pathlib

    import cardlang

    root = pathlib.Path(str(cardlang.__file__)).parent
    offenders = [
        f"{path.relative_to(root.parent)}:{i}"
        for path in sorted(root.rglob("*"))
        if path.suffix in {".py", ".lark"}
        for i, line in enumerate(path.read_text().splitlines(), 1)
        if "vocab" in line.lower()
    ]
    assert not offenders, (
        f"{len(offenders)} site(s) still spell the retired word:\n  "
        + "\n  ".join(offenders)
        + "\n\nThe menu of moves a construct presents is an OFFERING. If the "
        "site means the word-stock the DSL gives designers, that sense lives "
        "in docs — say what the thing is in plain terms instead."
    )
