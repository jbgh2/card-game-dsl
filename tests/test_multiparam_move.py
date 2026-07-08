from cardlang.parse import parse_text


def _game(move_src: str) -> str:
    # move_type_def is a top-level construct (a sibling of `game`, per the
    # grammar's `top_item` rule), not nested inside the `game { ... }` body —
    # mirrors tests/fixtures/offer_skeleton.cardlang.
    return (
        "game G {\n"
        "  players: 4\n"
        "  max_length: 100\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "}\n"
        f"{move_src}\n"
    )


def test_two_parameter_move_parses_to_a_tuple() -> None:
    game = parse_text(
        _game("move_type ask(target : Player, rank : Rank) { effect { } }"),
        "test.cardlang",
    )
    mt = next(m for m in game.move_types if m.name == "ask")
    assert [(p.name, p.type_name) for p in mt.params] == [
        ("target", "Player"),
        ("rank", "Rank"),
    ]


def test_nullary_move_has_empty_params() -> None:
    game = parse_text(_game("move_type pass { effect { } }"), "test.cardlang")
    mt = next(m for m in game.move_types if m.name == "pass")
    assert mt.params == ()
