"""全域常量 — 集中管理遊戲數值與座標，避免 magic numbers 散落。

所有座標基於 1920×1080 參考解析度（見 capture.REF_WIDTH/REF_HEIGHT）。
"""

from __future__ import annotations

# ---- 書籤價格（金幣）----
COVENANT_COST: int = 184000
MYSTIC_COST: int = 280000

# ---- 刷新消耗 ----
REFRESH_STONE_COST: int = 3

# ---- 商品點擊偏移（書籤匹配中心 → 商品按鈕，參考解析度）----
BUY_CLICK_OFFSET_X: int = 800
BUY_CLICK_OFFSET_Y: int = 40

# ---- 商店列表滑動（參考解析度座標）----
SWIPE_START_REF: tuple[int, int] = (1400, 500)
SWIPE_END_REF: tuple[int, int] = (1400, 200)
SWIPE_DURATION: float = 0.1

# ---- 畫面變化判定閾值 ----
SWIPE_CHANGED_DIFF: float = 5.0
STABLE_DIFF_THRESHOLD: float = 10.0
STABLE_BEFORE_DIFF_THRESHOLD: float = 15.0


def min_money_for_mode(mode: int) -> int:
    """根據模式回傳繼續執行所需的最低金幣。

    Args:
        mode: 1=聖約, 2=神秘, 3=天空石（兩種都可能買）。
    """
    if mode == 1:
        return COVENANT_COST
    return MYSTIC_COST  # mode 2/3 都可能買神秘書籤
