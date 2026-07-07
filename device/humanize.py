"""輸入人性化純函數 + 設定 — 降低點擊/滑動的機器特徵。

所有函數無 IO、無副作用,可單元測試。座標空間由呼叫端決定
(參考解析度/螢幕/設備),函數本身與座標空間無關。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from capture import REF_WIDTH, REF_HEIGHT


@dataclass
class HumanizeSettings:
    """後端唯一依賴的人性化設定,解耦 AppConfig。

    factory(device/__init__.py)從 AppConfig 扁平欄位組裝此物件注入後端;
    後端不直接依賴整份 AppConfig。
    """
    enabled: bool = True
    jitter_px: int = 8                  # 點擊抖動半徑(參考解析度 px)
    swipe_jitter_px: int = 20           # 滑動起終點抖動半徑
    double_click_gap: float = 0.05      # 雙擊間隔基準(固定,不暴露至 config)
    double_click_spread: float = 0.03   # 雙擊間隔抖動
    swipe_duration_spread: float = 0.04  # 滑動時長抖動(秒)
    curve_strength: float = 0.3         # 僅 Windows:貝茲控制點法向偏移比例
    move_steps: int = 12                # 僅 Windows:移動取樣點數


def jitter_point(x: float, y: float, r: float) -> tuple[float, float]:
    """在以 (x,y) 為中心、半徑 r 的圓內均勻取點。r<=0 回原點。

    用 sqrt(uniform) 確保圓內均勻分布(否則會集中圓心)。
    """
    if r <= 0:
        return float(x), float(y)
    angle = random.uniform(0, 2 * math.pi)
    radius = r * math.sqrt(random.uniform(0, 1))
    return x + radius * math.cos(angle), y + radius * math.sin(angle)


def jitter_swipe_endpoints(
    p1: tuple[float, float], p2: tuple[float, float], r: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """滑動起終點各自 jitter_point。"""
    return jitter_point(*p1, r), jitter_point(*p2, r)


def clamp_ref(x: float, y: float) -> tuple[float, float]:
    """將參考解析度座標 clamp 到 [0, REF_WIDTH]×[0, REF_HEIGHT](防禦抖動出界)。"""
    return (max(0.0, min(float(REF_WIDTH), x)), max(0.0, min(float(REF_HEIGHT), y)))


def bezier_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    n: int,
) -> list[tuple[float, float]]:
    """三階貝茲曲線取 n 點(含端點 t=0..1)。n<2 回 [p0]。

    B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
    """
    if n < 2:
        return [(float(p0[0]), float(p0[1]))]
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        u = 1 - t
        a = u * u * u
        b = 3 * u * u * t
        c = 3 * u * t * t
        d = t * t * t
        x = a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0]
        y = a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]
        pts.append((x, y))
    return pts


def ease_in_out_weights(n: int) -> list[float]:
    """n 個取樣點之間的 n-1 段加減速權重(先慢後快再慢),總和=1。n<2 回 []。

    eased(t) = 0.5(1 - cos(πt)),t=0..1;權重 = 相鄰 eased 差分。
    """
    if n < 2:
        return []
    eased = [0.5 * (1 - math.cos(math.pi * i / (n - 1))) for i in range(n)]
    weights = [eased[i + 1] - eased[i] for i in range(n - 1)]
    total = sum(weights)
    if total <= 0:
        return [1.0 / (n - 1)] * (n - 1)
    return [w / total for w in weights]


def random_gap(base: float, spread: float) -> float:
    """base ± spread 的隨機間隔,恆 >= 0.01(防退化為零/負)。"""
    return max(0.01, base + random.uniform(-spread, spread))


def roll(chance: float) -> bool:
    """以機率 chance 回 True。chance<=0 恆 False,chance>=1 恆 True。"""
    return random.uniform(0, 1) < chance


def roll_sign() -> int:
    """隨機回 +1 或 -1(軌跡法向偏移隨機左右)。"""
    return 1 if roll(0.5) else -1
