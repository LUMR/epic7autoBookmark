import cv2
import numpy as np
from unittest.mock import MagicMock

from automation.inspection import (
    Inspector, INSPECTION_ITEMS, ITEM_DISPLAY, ItemScore,
)
from detection.matcher import TemplateMatcher


def _tex(h, w, seed):
    """固定种子纹理图（避免 TM_CCOEFF_NORMED 对常量图除零）。"""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 256, (h, w, 3)).astype(np.uint8)


def _mk_inspector(template_img):
    templates = MagicMock()
    templates.load.return_value = template_img
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.scan_roi_tuple = None
    config.button_roi_tuple = None
    return Inspector(templates, TemplateMatcher(), config)


def test_inspection_items_count_and_order():
    prefixes = [it.prefix for it in INSPECTION_ITEMS]
    assert prefixes == [
        "covenant", "mystic", "buyButton", "buyConfirm", "refresh", "refreshYes",
    ]
    for it in INSPECTION_ITEMS:
        assert it.template_name and it.threshold_attr
        assert it.roi_attr and it.display_name


def test_item_display_covers_all_prefixes():
    assert set(ITEM_DISPLAY) == {it.prefix for it in INSPECTION_ITEMS}


def test_inspect_returns_score_per_item():
    tpl = _tex(20, 20, 7)
    img = _tex(200, 200, 1)
    img[100:120, 100:120] = tpl          # 贴模板 → 高分
    scores = _mk_inspector(tpl).inspect(img)
    assert len(scores) == len(INSPECTION_ITEMS)
    assert all(s.score is not None for s in scores)
    assert any(s.score >= 0.85 for s in scores)


def test_inspect_missing_template_is_na():
    img = _tex(200, 200, 1)
    templates = MagicMock()
    templates.load.side_effect = FileNotFoundError("missing")
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.scan_roi_tuple = None
    config.button_roi_tuple = None
    scores = Inspector(templates, MagicMock(), config).inspect(img)
    assert all(s.score is None for s in scores)
    assert all(s.passed is False for s in scores)


def test_pick_default_prefers_bookmark_when_passed():
    scores = [
        ItemScore("covenant", "聖約", 0.95, 0.9, True),
        ItemScore("mystic", "神秘", 0.10, 0.9, False),
        ItemScore("buyButton", "購買", 0.99, 0.85, True),
    ]
    assert Inspector(MagicMock(), MagicMock(), MagicMock()).pick_default(scores) == "covenant"


def test_pick_default_highest_when_no_bookmark_passed():
    scores = [
        ItemScore("covenant", "聖約", 0.10, 0.9, False),
        ItemScore("mystic", "神秘", 0.20, 0.9, False),
        ItemScore("buyButton", "購買", 0.88, 0.85, True),
    ]
    assert Inspector(MagicMock(), MagicMock(), MagicMock()).pick_default(scores) == "buyButton"


def test_pick_default_tie_prefers_bookmark():
    scores = [
        ItemScore("covenant", "聖約", 0.50, 0.9, False),
        ItemScore("buyButton", "購買", 0.50, 0.85, False),
    ]
    assert Inspector(MagicMock(), MagicMock(), MagicMock()).pick_default(scores) == "covenant"


def test_pick_default_all_none_returns_none():
    scores = [ItemScore("covenant", "聖約", None, 0.9, False)]
    assert Inspector(MagicMock(), MagicMock(), MagicMock()).pick_default(scores) is None
