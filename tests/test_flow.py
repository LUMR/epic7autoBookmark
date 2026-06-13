"""flow 整合測試 — mock 注入 capture/matcher/input，驗證狀態流轉與計數。

保障 Task 9 重構後行為正確：點擊-等待抽象、常量計費、ROI 串接不破壞邏輯。
"""
import numpy as np
import pytest
from unittest.mock import MagicMock

from automation.state import ShopContext, ShopState
from automation.flow import ShopFlow
from detection.matcher import MatchResult


def _match_result(x=500, y=400):
    return MatchResult(name="t", score=0.95, box=(x, y, 10, 10))


def _mk_flow(mode=1, expect_num=2):
    ctx = ShopContext(hwnd=1, mode=mode, expect_num=expect_num,
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
    config.short_sleep_base = 0.0      # 測試不要真的睡
    config.scan_roi_tuple = None
    config.button_roi_tuple = None

    templates = MagicMock()
    matcher = MagicMock()
    input_backend = MagicMock()
    input_backend.scale_coords.return_value = (100.0, 100.0)
    logger = MagicMock()
    flow = ShopFlow(ctx, templates, matcher, input_backend, logger, config)
    return flow, ctx, matcher


@pytest.fixture
def mock_capture(monkeypatch):
    fake = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr("automation.flow.capture_window", lambda *a, **k: fake)


def test_scanning_finds_covenant(mock_capture):
    flow, ctx, matcher = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.SCANNING
    matcher.match.return_value = _match_result(300, 200)
    flow._handle_scanning()

    assert ctx.state == ShopState.BUYING_COVENANT
    assert ctx.target is not None
    assert ctx.target.label == "聖約"


def test_buying_covenant_success(mock_capture):
    flow, ctx, matcher = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    # _click_until_found 第1次 match 找到按鈕；_click_until_gone 第2次 match 返回 None（消失）
    matcher.match.side_effect = [_match_result(900, 140), None]
    flow._handle_buying()

    assert ctx.covenant_bought == 1
    assert ctx.covenant_found is True
    assert ctx.expect_num == 1          # mode 1 扣 1
    assert ctx.money == 10**8 - 184000
    assert ctx.state == ShopState.SCANNING


def test_buying_confirm_timeout_returns_to_scan(mock_capture):
    """確認框逾時不再死磕外層重試，直接回掃描（行為改進）。"""
    flow, ctx, matcher = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    # 找到按鈕，但確認框永遠不消失（_click_until_gone 持續失敗）
    matcher.match.side_effect = [_match_result()] * 100
    flow._handle_buying()

    assert ctx.covenant_bought == 0      # 未成功
    assert ctx.state == ShopState.SCANNING
