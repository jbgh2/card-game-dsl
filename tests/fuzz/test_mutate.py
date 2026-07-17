"""Unit tests for each operator in mutate.py, on small synthetic fixtures —
independent of the live corpus (test_fuzz.py exercises these against
docs/games/*.cardlang instead)."""

from __future__ import annotations

import random

from .mutate import (
    MUTATORS,
    delete_line,
    duplicate_declaration,
    mutate_text,
    rename_identifier,
    swap_adjacent_tokens,
    truncate_block,
)

FIXTURE = (
    "game X {\n"
    "  players: 2\n"
    "  direction: clockwise\n"
    "  cards: standard52\n"
    "  max_length: 10\n"
    "  zones {\n"
    "    deck : Deck\n"
    "    hand[player] : Hand<player>\n"
    "  }\n"
    "  winner: highest score\n"
    "}\n"
)


def test_registry_matches_plans_five_operators() -> None:
    # The plan's exact Stage-1 list (grammar-fuzzing.md): delete a
    # clause/line, duplicate a declaration, swap adjacent tokens, rename an
    # identifier occurrence, truncate a block. A sixth operator landing here
    # without updating this pin is exactly the "closed registry drifted
    # silently" failure mode the completeness ledger exists to catch.
    assert set(MUTATORS) == {
        "delete_line",
        "duplicate_declaration",
        "swap_adjacent_tokens",
        "rename_identifier",
        "truncate_block",
    }


def test_delete_line_removes_exactly_one_nonblank_line() -> None:
    rng = random.Random(0)
    result = delete_line(FIXTURE, rng)
    assert result is not None
    assert len(result.splitlines()) == len(FIXTURE.splitlines()) - 1


def test_delete_line_none_on_blank_text() -> None:
    assert delete_line("\n\n  \n", random.Random(0)) is None


def test_duplicate_declaration_inserts_a_repeat() -> None:
    rng = random.Random(0)
    result = duplicate_declaration(FIXTURE, rng)
    assert result is not None
    assert len(result.splitlines()) == len(FIXTURE.splitlines()) + 1
    # One of the declaration-shaped lines now appears twice in a row.
    lines = result.splitlines()
    assert any(lines[i] == lines[i + 1] for i in range(len(lines) - 1))


def test_duplicate_declaration_none_without_declarations() -> None:
    assert duplicate_declaration("// just a comment\n\n", random.Random(0)) is None


def test_swap_adjacent_tokens_changes_a_line() -> None:
    rng = random.Random(0)
    result = swap_adjacent_tokens(FIXTURE, rng)
    assert result is not None
    assert result != FIXTURE
    assert sorted(result.split()) == sorted(FIXTURE.split())  # same multiset of tokens


def test_swap_adjacent_tokens_none_without_two_token_lines() -> None:
    assert swap_adjacent_tokens("x\ny\nz\n", random.Random(0)) is None


def test_rename_identifier_touches_one_occurrence() -> None:
    text = "let x = x + x\n"
    rng = random.Random(0)
    result = rename_identifier(text, rng)
    assert result is not None
    assert result.count("_MUT") == 1
    # The other two `x` occurrences are untouched.
    assert result.count("x") == text.count("x")  # x still present (renamed one is x_MUT)


def test_rename_identifier_none_on_empty_text() -> None:
    assert rename_identifier("   \n", random.Random(0)) is None


def test_truncate_block_shortens_the_file() -> None:
    rng = random.Random(0)
    result = truncate_block(FIXTURE, rng)
    assert result is not None
    assert len(result.splitlines()) < len(FIXTURE.splitlines())
    assert FIXTURE.startswith(result)


def test_truncate_block_none_on_short_text() -> None:
    assert truncate_block("a\nb\n", random.Random(0)) is None


def test_mutate_text_is_deterministic() -> None:
    a = mutate_text(FIXTURE, "delete_line", 3, label="fixture.cardlang")
    b = mutate_text(FIXTURE, "delete_line", 3, label="fixture.cardlang")
    assert a == b


def test_mutate_text_seed_and_label_both_matter() -> None:
    by_seed = mutate_text(FIXTURE, "delete_line", 1, label="fixture.cardlang")
    by_other_seed = mutate_text(FIXTURE, "delete_line", 2, label="fixture.cardlang")
    by_other_label = mutate_text(FIXTURE, "delete_line", 1, label="other.cardlang")
    # Not a hard guarantee any single pair differs (small line count), but at
    # least one of these two comparisons should, or the fixture is too small
    # to exercise "the triple matters" at all.
    assert by_seed != by_other_seed or by_seed != by_other_label
