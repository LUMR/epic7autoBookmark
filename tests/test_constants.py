from constants import (
    COVENANT_COST, MYSTIC_COST, REFRESH_STONE_COST,
    BUY_CLICK_OFFSET_X, BUY_CLICK_OFFSET_Y,
    SWIPE_START_REF, SWIPE_END_REF,
    min_money_for_mode,
)


def test_bookmark_costs():
    assert COVENANT_COST == 184000
    assert MYSTIC_COST == 280000
    assert REFRESH_STONE_COST == 3


def test_buy_click_offset():
    assert (BUY_CLICK_OFFSET_X, BUY_CLICK_OFFSET_Y) == (800, 40)


def test_swipe_coords():
    assert SWIPE_START_REF == (1400, 500)
    assert SWIPE_END_REF == (1400, 200)


def test_min_money_for_mode():
    assert min_money_for_mode(1) == 184000
    assert min_money_for_mode(2) == 280000
    assert min_money_for_mode(3) == 280000
