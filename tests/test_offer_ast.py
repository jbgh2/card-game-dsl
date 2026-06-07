from cardlang.ast import nodes as n


def test_movetypedef_and_offer_construct() -> None:
    mt = n.MoveTypeDef(name="take_one", guard=None, effect=())
    assert mt.name == "take_one" and mt.guard is None and mt.effect == ()
    off = n.Offer(player=n.NameRef("p"), move_types=("take_one", "take_two"))
    assert isinstance(off.player, n.NameRef)
    assert off.player.name == "p" and off.move_types == ("take_one", "take_two")
