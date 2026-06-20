"""flow 整合測試 — 注入 FakeDevice/mock matcher,驗證狀態流轉與計費。"""
import numpy as np
import pytest
from unittest.mock import MagicMock

from automation.state import ShopContext, ShopState
from automation.flow import ShopFlow
from detection.matcher import MatchResult
from tests.fakes import FakeDevice
from constants import SWIPE_START_REF, SWIPE_END_REF, SWIPE_DURATION


def _match_result(x=500, y=400):
    return MatchResult(name="t", score=0.95, box=(x, y, 10, 10))


def _mk_flow(mode=1, expect_num=2):
    device = FakeDevice()
    ctx = ShopContext(device=device, mode=mode, expect_num=expect_num,
                      money=10**8, stone=100)
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.wait_timeout = 0.1
    config.wait_timeout_long = 0.2
    config.max_retry = 2
    config.swipe_fail_limit = 5
    config.short_sleep_base = 0.0
    config.scan_roi_tuple = None
    config.button_roi_tuple = None

    templates = MagicMock()
    matcher = MagicMock()
    logger = MagicMock()
    flow = ShopFlow(ctx, templates, matcher, device, logger, config)
    return flow, ctx, matcher, device


def test_scanning_finds_covenant():
    flow, ctx, matcher, _ = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.SCANNING
    matcher.match.return_value = _match_result(300, 200)
    flow._handle_scanning()

    assert ctx.state == ShopState.BUYING_COVENANT
    assert ctx.target is not None
    assert ctx.target.label == "聖約"


def test_buying_covenant_success():
    flow, ctx, matcher, device = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    matcher.match.side_effect = [_match_result(900, 140), None]
    flow._handle_buying()

    assert ctx.covenant_bought == 1
    assert ctx.covenant_found is True
    assert ctx.expect_num == 1
    assert ctx.money == 10**8 - 184000
    assert ctx.state == ShopState.SCANNING
    assert any(c[0] == "double_click" for c in device.calls)


def test_buying_confirm_timeout_returns_to_scan():
    flow, ctx, matcher, _ = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    matcher.match.side_effect = [_match_result()] * 100
    flow._handle_buying()

    assert ctx.covenant_bought == 0
    assert ctx.state == ShopState.SCANNING


def test_swiping_calls_device_swipe():
    """swipe 座標展開正確:SWIPE_START_REF/END_REF + duration 直傳 device。"""
    flow, ctx, matcher, device = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.SWIPING
    flow._handle_swiping()
    swipes = [c for c in device.calls if c[0] == "swipe"]
    assert len(swipes) == 1
    assert swipes[0] == ("swipe", *SWIPE_START_REF, *SWIPE_END_REF, SWIPE_DURATION)


def test_init_calls_device_prepare():
    """_init 應呼叫 device.prepare()(取代舊 SetForegroundWindow)。"""
    device = MagicMock()
    ctx = ShopContext(device=device, mode=1, expect_num=2, money=10**8, stone=100)
    config = MagicMock()
    config.short_sleep_base = 0.0
    flow = ShopFlow(ctx, MagicMock(), MagicMock(), device, MagicMock(), config)
    flow._init()
    device.prepare.assert_called_once()
