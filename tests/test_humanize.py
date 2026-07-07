"""humanize 純函數單元測試。"""
import math

import pytest

from capture import REF_WIDTH, REF_HEIGHT
from device.humanize import (
    HumanizeSettings,
    jitter_point,
    jitter_swipe_endpoints,
    clamp_ref,
    bezier_points,
    ease_in_out_weights,
    random_gap,
    roll,
    roll_sign,
)


def test_humanize_settings_defaults():
    hs = HumanizeSettings()
    assert hs.enabled is True
    assert hs.jitter_px == 8
    assert hs.swipe_jitter_px == 20
    assert hs.double_click_gap == 0.05
    assert hs.double_click_spread == 0.03
    assert hs.swipe_duration_spread == 0.04
    assert hs.curve_strength == 0.3
    assert hs.move_steps == 12


def test_jitter_point_within_radius():
    for _ in range(200):
        jx, jy = jitter_point(100.0, 100.0, 8)
        dist = math.hypot(jx - 100.0, jy - 100.0)
        assert dist <= 8.0 + 1e-9


def test_jitter_point_zero_radius_returns_center():
    assert jitter_point(100.0, 100.0, 0) == (100.0, 100.0)
    assert jitter_point(100.0, 100.0, -3) == (100.0, 100.0)


def test_jitter_swipe_endpoints_both_within_radius():
    (a1, a2), (b1, b2) = jitter_swipe_endpoints((0.0, 0.0), (100.0, 100.0), 5)
    assert math.hypot(a1, a2) <= 5.0 + 1e-9
    assert math.hypot(b1 - 100.0, b2 - 100.0) <= 5.0 + 1e-9


def test_clamp_ref_within_bounds_unchanged():
    assert clamp_ref(100.0, 200.0) == (100.0, 200.0)


def test_clamp_ref_clamps_out_of_bounds():
    assert clamp_ref(-5.0, 5000.0) == (0.0, float(REF_HEIGHT))
    assert clamp_ref(5000.0, -5.0) == (float(REF_WIDTH), 0.0)


def test_bezier_points_count_and_endpoints():
    pts = bezier_points((0.0, 0.0), (1.0, 2.0), (3.0, 4.0), (5.0, 0.0), 10)
    assert len(pts) == 10
    assert pts[0] == pytest.approx((0.0, 0.0))   # t=0 -> P0
    assert pts[-1] == pytest.approx((5.0, 0.0))  # t=1 -> P3


def test_bezier_points_n_less_than_two():
    assert bezier_points((1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), 1) == [(1.0, 1.0)]
    assert bezier_points((1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), 0) == [(1.0, 1.0)]


def test_ease_in_out_weights_count_and_sum():
    weights = ease_in_out_weights(12)
    assert len(weights) == 11            # n 點 -> n-1 段
    assert sum(weights) == pytest.approx(1.0)


def test_ease_in_out_weights_shape():
    """加減速:首尾段權重 < 中間段權重。"""
    weights = ease_in_out_weights(12)
    mid = len(weights) // 2
    assert weights[0] < weights[mid]
    assert weights[-1] < weights[mid]


def test_ease_in_out_weights_n_less_than_two():
    assert ease_in_out_weights(1) == []
    assert ease_in_out_weights(0) == []


def test_random_gap_always_positive_and_in_range():
    for _ in range(200):
        g = random_gap(0.05, 0.03)
        assert g >= 0.01
        assert 0.05 - 0.03 - 1e-9 <= g <= 0.05 + 0.03 + 1e-9


def test_roll_chance_zero_always_false():
    assert all(roll(0.0) is False for _ in range(100))


def test_roll_chance_one_always_true():
    assert all(roll(1.0) is True for _ in range(100))


def test_roll_sign_only_plus_minus_one():
    for _ in range(100):
        assert roll_sign() in (1, -1)
