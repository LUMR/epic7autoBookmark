"""商店自動化主流程 — 狀態驅動的 ShopFlow。

每個狀態有獨立的處理器方法，狀態之間透過 ctx.state 轉換。
_click_until_found / _click_until_gone 抽象了重複的「點擊-等待」流程。
"""

from __future__ import annotations

import random
import time

import cv2
import numpy as np
import win32gui

from capture import capture_window
from config import AppConfig
from detection.matcher import TemplateMatcher
from input.base import InputBackend
from automation.state import ShopContext, ShopState, BookmarkTarget
from automation.templates import TemplateManager
from logger import ShopLogger
from constants import (
    COVENANT_COST,
    MYSTIC_COST,
    REFRESH_STONE_COST,
    BUY_CLICK_OFFSET_X,
    BUY_CLICK_OFFSET_Y,
    SWIPE_START_REF,
    SWIPE_END_REF,
    SWIPE_DURATION,
    SWIPE_CHANGED_DIFF,
    min_money_for_mode,
)


def wait_for(
    ctx: ShopContext,
    matcher: TemplateMatcher,
    template: np.ndarray,
    threshold: float,
    name: str = "",
    timeout: float = 5.0,
    interval: float = 0.3,
    roi=None,
) -> "detection.matcher.MatchResult | None":
    """輪詢等待模板出現。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return None
        time.sleep(interval)
        img = capture_window(ctx.hwnd, ctx.capture_method)
        result = matcher.match(img, template, threshold, name, roi=roi)
        if result is not None:
            return result
    return None


def wait_for_gone(
    ctx: ShopContext,
    matcher: TemplateMatcher,
    template: np.ndarray,
    threshold: float,
    name: str = "",
    timeout: float = 5.0,
    interval: float = 0.3,
    roi=None,
) -> bool:
    """輪詢等待模板消失。回傳 True=已消失，False=逾時。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return True
        time.sleep(interval)
        img = capture_window(ctx.hwnd, ctx.capture_method)
        if matcher.match(img, template, threshold, name, roi=roi) is None:
            return True
    return False


def wait_for_stable(
    ctx: ShopContext,
    before_img: np.ndarray | None = None,
    timeout: float = 15.0,
    interval: float = 0.5,
    threshold: float = 10.0,
    before_threshold: float = 15.0,
) -> bool:
    """等待畫面停止變化（載入動畫結束）。

    連續兩次截圖差異小於閾值，且與刷新前不同，則視為穩定。
    """
    deadline = time.time() + timeout
    prev = capture_window(ctx.hwnd, ctx.capture_method)
    while time.time() < deadline:
        if not ctx._running:
            return False
        time.sleep(interval)
        curr = capture_window(ctx.hwnd, ctx.capture_method)
        if cv2.absdiff(prev, curr).mean() < threshold:
            if before_img is not None and cv2.absdiff(before_img, curr).mean() < before_threshold:
                prev = curr
                continue
            return True
        prev = curr
    return False


class ShopFlow:
    """狀態驅動的商店自動化流程。"""

    def __init__(
        self,
        ctx: ShopContext,
        templates: TemplateManager,
        matcher: TemplateMatcher,
        input_backend: InputBackend,
        logger: ShopLogger,
        config: AppConfig,
    ):
        self.ctx = ctx
        self.templates = templates
        self.matcher = matcher
        self.input = input_backend
        self.log = logger
        self.config = config

        # 預載入所有模板
        self._tpl_covenant = templates.covenant
        self._tpl_mystic = templates.mystic
        self._tpl_buy_confirm = templates.buy_confirm
        self._tpl_refresh = templates.refresh_button
        self._tpl_refresh_yes = templates.refresh_yes

    # ---- 時延 ----

    def short_sleep(self, multiplier: float = 1.0) -> None:
        """帶隨機抖動的延遲，時長 = config.short_sleep_base * multiplier + 抖動。"""
        time.sleep(self.config.short_sleep_base * multiplier + random.uniform(-0.2, 0.3))

    # ---- 點擊輔助（抽象重複的「點擊-等待」流程）----

    def _click_until_found(self, ref_pos, tpl, threshold, name, max_retry=None):
        """點擊 ref_pos 直到 tpl 出現。回傳 MatchResult 或 None（重試耗盡）。"""
        max_retry = self.config.max_retry if max_retry is None else max_retry
        cx, cy = self.input.scale_coords(self.ctx.hwnd, *ref_pos)
        for i in range(max_retry):
            if not self.ctx._running:
                return None
            self.short_sleep(0.5)
            self.log.debug(f"點擊{name} ({cx:.0f},{cy:.0f}) 重試:{i+1}")
            self.input.double_click(self.ctx.hwnd, cx, cy)
            result = wait_for(
                self.ctx, self.matcher, tpl, threshold, name,
                timeout=self.config.wait_timeout,
                roi=self.config.button_roi_tuple,
            )
            if result is not None:
                return result
            self.log.info(f"未找到{name}，重試...")
            self.short_sleep(1.0)
        return None

    def _click_until_gone(self, ref_pos, tpl, threshold, name, timeout=None):
        """點擊 ref_pos 直到 tpl 消失。回傳 True=消失，False=重試耗盡。"""
        timeout = self.config.wait_timeout if timeout is None else timeout
        cx, cy = self.input.scale_coords(self.ctx.hwnd, *ref_pos)
        for i in range(self.config.max_retry):
            if not self.ctx._running:
                return True
            self.short_sleep(0.3)
            self.log.debug(f"點擊{name} ({cx:.0f},{cy:.0f}) 重試:{i+1}")
            self.input.double_click(self.ctx.hwnd, cx, cy)
            if wait_for_gone(
                self.ctx, self.matcher, tpl, threshold, name,
                timeout=timeout, roi=self.config.button_roi_tuple,
            ):
                return True
        return False

    # ---- 主循環 ----

    def run(self) -> ShopContext:
        """執行商店自動化主循環。"""
        self._init()

        while self.ctx.should_continue:
            state = self.ctx.state
            if state == ShopState.SCANNING:
                self._handle_scanning()
            elif state in (ShopState.BUYING_COVENANT, ShopState.BUYING_MYSTIC):
                self._handle_buying()
            elif state == ShopState.SWIPING:
                self._handle_swiping()
            elif state == ShopState.REFRESHING:
                self._handle_refreshing()
            elif state in (ShopState.DONE, ShopState.ERROR):
                break

        self._finish()
        return self.ctx

    # ---- 初始化 ----

    def _init(self) -> None:
        """初始化校驗和準備。"""
        self.log.info("===== 初始化 =====")
        self.short_sleep(0.5)

        if self.ctx.money < min_money_for_mode(self.ctx.mode):
            self.log.error("錯誤: 金幣不足")
            raise ValueError("out of money")

        if self.ctx.stone < REFRESH_STONE_COST:
            self.log.error("錯誤: 天空石不足以刷新商店")
            raise ValueError("out of stone")

        if self.ctx.mode == 3 and self.ctx.expect_num > self.ctx.stone:
            self.log.error("錯誤: 天空石使用數量大於持有數量")
            raise ValueError("stone input error")

        self.log.info("正在尋找遊戲視窗......")
        self.short_sleep(0.5)

        try:
            win32gui.SetForegroundWindow(self.ctx.hwnd)
        except Exception:
            pass  # 視窗可能已在前台
        self.short_sleep(0.5)

        self.log.info("遊戲視窗已找到")
        self.short_sleep(0.5)
        self.log.info("初始化完成")
        self.short_sleep(0.5)
        self.log.info("===== 刷商店 =====")
        self.short_sleep(0.5)

    # ---- SCANNING：掃描商店 ----

    def _handle_scanning(self) -> None:
        """掃描商店，查找目標書籤。"""
        if self.ctx.need_refresh:
            self.ctx.state = ShopState.REFRESHING
            return

        screenshot = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        scan_roi = self.config.scan_roi_tuple

        if not self.ctx.covenant_found:
            loc = self.matcher.match(
                screenshot, self._tpl_covenant,
                self.config.match_threshold_location, "covenant", roi=scan_roi,
            )
            if loc is not None:
                cx, cy = loc.center
                self.log.info(f"找到聖約書籤 位置:({cx},{cy})")
                self.ctx.target = BookmarkTarget(match_center=(cx, cy), label="聖約")
                self.ctx.state = ShopState.BUYING_COVENANT
                return

        if not self.ctx.mystic_found:
            loc = self.matcher.match(
                screenshot, self._tpl_mystic,
                self.config.match_threshold_location, "mystic", roi=scan_roi,
            )
            if loc is not None:
                mx, my = loc.center
                self.log.info(f"找到神秘書籤 位置:({mx},{my})")
                self.ctx.target = BookmarkTarget(match_center=(mx, my), label="神秘")
                self.ctx.state = ShopState.BUYING_MYSTIC
                return

        self.ctx.state = ShopState.SWIPING

    # ---- BUYING：購買書籤（聖約/神秘統一處理）----

    def _handle_buying(self) -> None:
        """購買書籤的統一流程。

        行為改進：購買確認逾時不再死磕外層重試，直接回掃描，避免空轉。
        """
        target = self.ctx.target
        if target is None:
            self.ctx.state = ShopState.SCANNING
            return

        is_covenant = self.ctx.state == ShopState.BUYING_COVENANT
        mode_match = 1 if is_covenant else 2
        cost = COVENANT_COST if is_covenant else MYSTIC_COST

        # 計算點擊位置：商品中心偏右偏下
        tx, ty = target.match_center
        click_pos = (tx + BUY_CLICK_OFFSET_X, ty + BUY_CLICK_OFFSET_Y)

        # 點商品直到購買確認按鈕出現
        buy_btn = self._click_until_found(
            click_pos, self._tpl_buy_confirm,
            self.config.match_threshold_button, "buy_confirm",
        )
        if buy_btn is None:
            self.log.info(f"{target.label}購買重試耗盡，繼續掃描")
            self.ctx.target = None
            self.ctx.state = ShopState.SCANNING
            return

        # 點購買按鈕直到確認框消失即視為成功
        if self._click_until_gone(
            buy_btn.center, self._tpl_buy_confirm,
            self.config.match_threshold_button, "buy_confirm",
        ):
            # ---- 購買成功 ----
            if self.ctx.mode == mode_match:
                self.ctx.expect_num -= 1
                self.log.info(f"剩餘次數: {self.ctx.expect_num}次")
            self.ctx.money -= cost
            if is_covenant:
                self.ctx.covenant_bought += 1
                self.ctx.covenant_found = True
            else:
                self.ctx.mystic_bought += 1
                self.ctx.mystic_found = True
        else:
            self.log.info("購買確認逾時，繼續掃描")

        self.ctx.target = None
        self.ctx.state = ShopState.SCANNING

    # ---- SWIPING：滑動商店列表 ----

    def _handle_swiping(self) -> None:
        """滑動商店列表。連續滑動失敗達閾值則停止。"""
        self.log.info("滑動商店列表")
        self.short_sleep(0.3)

        before = capture_window(self.ctx.hwnd, self.ctx.capture_method)

        sx1, sy1 = self.input.scale_coords(self.ctx.hwnd, *SWIPE_START_REF)
        sx2, sy2 = self.input.scale_coords(self.ctx.hwnd, *SWIPE_END_REF)
        self.input.swipe(self.ctx.hwnd, sx1, sy1, sx2, sy2, SWIPE_DURATION)
        self.ctx.need_refresh = True

        self.short_sleep(1.0)

        after = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        changed = cv2.absdiff(before, after).mean() > SWIPE_CHANGED_DIFF

        if not changed:
            self.ctx.swipe_fail_count += 1
            limit = self.config.swipe_fail_limit
            self.log.info(f"滑動未生效 ({self.ctx.swipe_fail_count}/{limit})")
            if self.ctx.swipe_fail_count >= limit:
                self.log.error("連續滑動失敗過多，停止")
                raise RuntimeError("swipe failed repeatedly")
        else:
            self.ctx.swipe_fail_count = 0

        self.ctx.state = ShopState.SCANNING

    # ---- REFRESHING：刷新商店 ----

    def _handle_refreshing(self) -> None:
        """刷新商店流程。"""
        screenshot = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        refresh_loc = self.matcher.match(
            screenshot, self._tpl_refresh,
            self.config.match_threshold_refresh, "refresh",
            roi=self.config.button_roi_tuple,
        )

        if refresh_loc is None:
            self.log.info("找不到刷新按鈕，重新滑動...")
            self.ctx.covenant_found = False
            self.ctx.mystic_found = False
            self.ctx.need_refresh = False
            self.short_sleep(1.0)
            self.ctx.state = ShopState.SCANNING
            return

        before_refresh = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        rx, ry = refresh_loc.center

        for retry in range(self.config.max_retry):
            if not self.ctx._running:
                return
            self.short_sleep(0.5)

            srx, sry = self.input.scale_coords(self.ctx.hwnd, rx, ry)
            self.log.debug(f"點擊刷新按鈕 ({srx:.0f},{sry:.0f}) 重試:{retry+1}")
            self.input.double_click(self.ctx.hwnd, srx, sry)

            # 等待確認對話框
            yes_btn = wait_for(
                self.ctx, self.matcher, self._tpl_refresh_yes,
                self.config.match_threshold_confirm, "refresh_yes",
                roi=self.config.button_roi_tuple,
            )

            if yes_btn is None:
                self.log.info("未彈出確認對話框，重試...")
                self.short_sleep(1.0)
                continue

            # 點確認直到消失，然後等待畫面穩定
            if self._click_until_gone(
                yes_btn.center, self._tpl_refresh_yes,
                self.config.match_threshold_confirm, "refresh_yes",
                timeout=self.config.wait_timeout_long,
            ):
                if wait_for_stable(self.ctx, before_refresh):
                    # ---- 刷新成功 ----
                    self.ctx.stone -= REFRESH_STONE_COST
                    self.ctx.refresh_count += 1
                    self.log.info(f"刷新成功，已用{self.ctx.refresh_count * REFRESH_STONE_COST}天空石")

                    if self.ctx.mode == 3:
                        self.ctx.expect_num -= REFRESH_STONE_COST
                        self.log.info(f"剩餘次數: {int(self.ctx.expect_num / REFRESH_STONE_COST)}次")

                    self.ctx.need_refresh = False
                    self.ctx.covenant_found = False
                    self.ctx.mystic_found = False

                    self.short_sleep(1.5)
                    self.ctx.state = ShopState.SCANNING
                    return
                else:
                    self.log.info("商店載入逾時，重試外層...")
            # gone 失敗或載入逾時 → continue 外層重試

        self.log.info("刷新重試耗盡，繼續掃描")
        self.ctx.state = ShopState.SCANNING

    # ---- 結算 ----

    def _finish(self) -> None:
        """輸出結算資訊。"""
        self.log.info("===== 結算 =====")
        self.log.info("共花費:")
        self.log.info(f"天空石: {self.ctx.total_stone_used}個")
        self.log.info(f"金幣: {self.ctx.total_money_used}元")
        self.log.info("獲得書籤:")
        self.log.info(f"聖約: {self.ctx.covenant_bought}次")
        self.log.info(f"神秘: {self.ctx.mystic_bought}次")
