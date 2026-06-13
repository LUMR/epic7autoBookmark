import numpy as np
from detection.matcher import TemplateMatcher


def _rand_img(h, w, seed=0):
    """固定種子的隨機紋理圖（避免 TM_CCOEFF_NORMED 對常數圖除零）。"""
    rng = np.random.RandomState(seed)
    return rng.randint(0, 256, (h, w, 3)).astype(np.uint8)


def test_match_found_full_image():
    img = _rand_img(100, 100, seed=1)
    tpl = img[40:60, 40:60].copy()  # 20×20 有紋理子區
    m = TemplateMatcher().match(img, tpl, 0.9, "t")
    assert m is not None and m.score >= 0.9
    cx, cy = m.center
    assert 40 <= cx <= 60 and 40 <= cy <= 60


def test_match_roi_excludes_target():
    img = _rand_img(100, 100, seed=2)
    stamp = _rand_img(10, 10, seed=99)
    img[80:90, 80:90] = stamp       # 把獨特紋理放在右下
    tpl = stamp.copy()
    # ROI 限定左上 (0,0,50,50)，不含 stamp
    assert TemplateMatcher().match(img, tpl, 0.9, "t", roi=(0, 0, 50, 50)) is None
    # 全圖能找到
    assert TemplateMatcher().match(img, tpl, 0.9, "t") is not None


def test_match_roi_offset_in_center():
    img = _rand_img(100, 100, seed=3)
    stamp = _rand_img(15, 15, seed=77)
    img[60:75, 60:75] = stamp
    tpl = stamp.copy()
    m = TemplateMatcher().match(img, tpl, 0.9, "t", roi=(50, 50, 50, 50))
    assert m is not None
    cx, cy = m.center
    # stamp 在 (60:75, 60:75)，ROI 座標已加 offset
    assert 60 <= cx <= 75 and 60 <= cy <= 75
