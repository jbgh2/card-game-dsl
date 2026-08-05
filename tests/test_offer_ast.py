from cardlang.ast import nodes as n


def test_movetypedef_and_offer_construct() -> None:
    mt = n.MoveTypeDef(name="take_one", when=None, effect=())
    assert mt.name == "take_one" and mt.when is None and mt.effect == ()
    off = n.Offer(player=n.NameRef("p"), offering=("take_one", "take_two"))
    assert isinstance(off.player, n.NameRef)
    assert off.player.name == "p" and off.offering == ("take_one", "take_two")
