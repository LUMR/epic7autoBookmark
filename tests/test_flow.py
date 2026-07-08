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
    config.humanize_enabled = False       # 測試時關閉人性化,流程可預測
    config.humanize_pause_chance = 0.0
    config.humanize_pause_duration = 0.0
    config.humanize_pause_spread = 0.0

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


def test_maybe_pause_noop_when_disabled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = False
    slept = []
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: slept.append(s))
    flow.maybe_pause()
    assert slept == []


def test_maybe_pause_sleeps_when_rolled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = True
    flow.config.humanize_pause_chance = 0.5
    flow.config.humanize_pause_duration = 2.0
    flow.config.humanize_pause_spread = 0.0
    monkeypatch.setattr("automation.flow.humanize.roll", lambda chance: True)
    slept = []
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: slept.append(s))
    flow.maybe_pause()
    assert len(slept) == 1
    assert 2.0 - 0.0 - 1e-9 <= slept[0] <= 2.0 + 0.0 + 1e-9


def test_short_sleep_uses_wider_jitter_when_enabled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = True
    flow.config.short_sleep_base = 0.0
    captured = {}

    def _capture_uniform(a, b):
        captured.setdefault("range", (a, b))
        return 0.0

    monkeypatch.setattr("automation.flow.random.uniform", _capture_uniform)
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: None)
    flow.short_sleep(1.0)
    assert captured["range"] == (-0.3, 0.6)


def test_short_sleep_uses_legacy_jitter_when_disabled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = False
    flow.config.short_sleep_base = 0.0
    captured = {}

    def _capture_uniform(a, b):
        captured.setdefault("range", (a, b))
        return 0.0

    monkeypatch.setattr("automation.flow.random.uniform", _capture_uniform)
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: None)
    flow.short_sleep(1.0)
    assert captured["range"] == (-0.2, 0.3)


def test_swipe_then_scan_finds_bookmark_not_refresh():
    """滑動後畫面出現書籤時應購買,而非因 need_refresh 跳刷新(回歸根因)。"""
    flow, ctx, matcher, device = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.SCANNING

    # 第1輪 SCANNING:無書籤 → SWIPING
    matcher.match.return_value = None
    flow._handle_scanning()
    assert ctx.state == ShopState.SWIPING

    # SWIPING:滑動(FakeDevice 兩次 capture 回同圖 → changed=False,計數+1 但未達 limit)
    flow._handle_swiping()
    assert ctx.state == ShopState.SCANNING

    # 第2輪 SCANNING:滑動後畫面出現聖約書籤
    matcher.match.return_value = _match_result(300, 200)
    flow._handle_scanning()

    # 期望:偵測到書籤 → BUYING_COVENANT(舊代碼會因 need_refresh=True 跳 REFRESHING)
    assert ctx.state == ShopState.BUYING_COVENANT


def test_swipe_at_bottom_triggers_refresh_not_error():
    """連續滑動無變化(到底)達 limit 次應刷新商店,不再 RuntimeError。"""
    flow, ctx, matcher, device = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.SWIPING
    flow.config.swipe_fail_limit = 2

    # FakeDevice 回同圖 → 每次滑動 changed=False
    flow._handle_swiping()   # fail_count=1,未達 limit
    assert ctx.need_refresh is False
    flow._handle_swiping()   # fail_count=2 >= limit → 到底,標記刷新
    assert ctx.need_refresh is True
    assert ctx.swipe_fail_count == 0   # 刷新前重置計數
    assert ctx.state == ShopState.SCANNING   # 下輪 SCANNING 會因 need_refresh 跳 REFRESHING
