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


def _ins():
    return Inspector(MagicMock(), MagicMock(), MagicMock())


def test_next_index_empty_dir(tmp_path):
    assert _ins().next_index(str(tmp_path), "covenant") == 1


def test_next_index_increments(tmp_path):
    (tmp_path / "covenant_1.png").write_bytes(b"")
    (tmp_path / "covenant_2.png").write_bytes(b"")
    assert _ins().next_index(str(tmp_path), "covenant") == 3


def test_next_index_ignores_other_prefixes(tmp_path):
    (tmp_path / "covenant_1.png").write_bytes(b"")
    (tmp_path / "mystic_5.png").write_bytes(b"")
    assert _ins().next_index(str(tmp_path), "covenant") == 2


def test_next_index_unordered(tmp_path):
    (tmp_path / "covenant_10.png").write_bytes(b"")
    (tmp_path / "covenant_2.png").write_bytes(b"")
    assert _ins().next_index(str(tmp_path), "covenant") == 11


def test_save_screenshot_writes_file(tmp_path):
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    path = _ins().save_screenshot(img, str(tmp_path), "covenant")
    assert path.exists()
    assert path.name == "covenant_1.png"
    data = np.fromfile(str(path), dtype=np.uint8)
    back = cv2.imdecode(data, cv2.IMREAD_COLOR)
    assert back.shape == (1080, 1920, 3)
    assert np.array_equal(back, img)


def test_save_screenshot_increments(tmp_path):
    (tmp_path / "covenant_1.png").write_bytes(b"")
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    path = _ins().save_screenshot(img, str(tmp_path), "covenant")
    assert path.name == "covenant_2.png"


def _mk_inspector_with_template(template):
    templates = MagicMock()
    templates.load.return_value = template
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.scan_roi_tuple = None
    config.button_roi_tuple = None
    return Inspector(templates, TemplateMatcher(), config)


def _write_png(path, img):
    """中文路径安全的 PNG 写入（测试用）。"""
    ok, buf = cv2.imencode(".png", img)
    buf.tofile(str(path))


def test_run_regression_pass_and_fail(tmp_path):
    tpl = _tex(20, 20, 7)
    ins = _mk_inspector_with_template(tpl)
    # covenant_1：含模板 → 通过
    img_pass = _tex(200, 200, 1)
    img_pass[100:120, 100:120] = tpl
    _write_png(tmp_path / "covenant_1.png", img_pass)
    # covenant_2：纯噪声 → 不通过
    _write_png(tmp_path / "covenant_2.png", _tex(200, 200, 2))

    report = ins.run_regression(str(tmp_path))

    assert report.total == 2
    assert report.passed == 1
    assert report.per_prefix["covenant"] == (1, 2)
    assert len(report.failures) == 1
    assert report.failures[0].prefix == "covenant"
    assert report.failures[0].threshold == 0.9
    assert 0.0 <= report.failures[0].score < 0.9


def test_run_regression_missing_dir(tmp_path):
    ins = _mk_inspector_with_template(_tex(10, 10, 1))
    report = ins.run_regression(str(tmp_path / "nope"))
    assert report.total == 0 and report.passed == 0
    assert report.per_prefix == {}
    assert report.failures == []


def test_run_regression_ignores_non_png(tmp_path):
    tpl = _tex(15, 15, 3)
    ins = _mk_inspector_with_template(tpl)
    img = _tex(100, 100, 1)
    img[40:55, 40:55] = tpl
    _write_png(tmp_path / "covenant_1.png", img)
    (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")

    report = ins.run_regression(str(tmp_path))
    assert report.total == 1 and report.passed == 1


def test_run_regression_skips_undecodable(tmp_path):
    tpl = _tex(15, 15, 3)
    ins = _mk_inspector_with_template(tpl)
    img = _tex(100, 100, 1)
    img[40:55, 40:55] = tpl
    _write_png(tmp_path / "covenant_1.png", img)
    (tmp_path / "covenant_2.png").write_bytes(b"not a png")   # 损坏文件
    report = ins.run_regression(str(tmp_path))
    assert report.total == 1      # 损坏文件被跳过,只统计 covenant_1
    assert report.passed == 1
