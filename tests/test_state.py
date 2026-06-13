from automation.state import ShopContext


def _ctx(mode=1, money=10**8, stone=100, expect_num=5, **kw):
    return ShopContext(hwnd=1, mode=mode, expect_num=expect_num,
                       money=money, stone=stone, **kw)


def test_should_continue_ok():
    assert _ctx().should_continue is True


def test_should_continue_mode1_money():
    assert _ctx(mode=1, money=184000).should_continue is False
    assert _ctx(mode=1, money=184001).should_continue is True


def test_should_continue_mode2_money():
    assert _ctx(mode=2, money=280000).should_continue is False
    assert _ctx(mode=2, money=280001).should_continue is True


def test_should_continue_mode3_budget():
    assert _ctx(mode=3, expect_num=3).should_continue is True
    assert _ctx(mode=3, expect_num=2).should_continue is False


def test_should_continue_stone_for_refresh():
    # 聖約模式：天空石 <3 無法刷新 → 停止
    assert _ctx(mode=1, stone=2).should_continue is False


def test_total_money_used():
    c = _ctx()
    c.covenant_bought = 2
    c.mystic_bought = 1
    assert c.total_money_used == 2 * 184000 + 1 * 280000


def test_total_stone_used():
    c = _ctx()
    c.refresh_count = 4
    assert c.total_stone_used == 12


def test_capture_method_default():
    assert _ctx().capture_method == "auto"
    assert _ctx(capture_method="mss").capture_method == "mss"
