"""商店自动化主流程 — 状态驱动的 ShopFlow。

替代原 main.py Worker.run() 中的线性 while 循环。
每个状态有独立的处理器方法，状态之间通过 ctx.state 转换。

修复的 Bug：
- #1: wait_for_stable 超时后 break（而非 continue 导致无效重试）
- #2: 滑动失败计数器 + 阈值退出
- #5: covenantFound/mysticFound 在购买成功后才设为 True
- #8: 圣约/神秘购买逻辑统一为 _handle_buying()
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


def short_sleep(base: float = 1.0) -> None:
    """带随机抖动的短暂延迟，避免固定间隔被检测。"""
    time.sleep(base + random.uniform(-0.2, 0.3))


def wait_for(
    ctx: ShopContext,
    matcher: TemplateMatcher,
    template: np.ndarray,
    threshold: float,
    name: str = "",
    timeout: float = 5.0,
    interval: float = 0.3,
) -> "detection.matcher.MatchResult | None":
    """轮询等待模板出现。

    替代原 main.py 中的 wait_for() 函数，使用 TemplateMatcher 替代 aircv。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return None
        time.sleep(interval)
        img = capture_window(ctx.hwnd)
        result = matcher.match(img, template, threshold, name)
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
) -> bool:
    """轮询等待模板消失。返回 True 表示已消失，False 表示超时。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return True
        time.sleep(interval)
        img = capture_window(ctx.hwnd)
        result = matcher.match(img, template, threshold, name)
        if result is None:
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
    """等待画面停止变化（加载动画结束）。

    连续两次截图差异小于阈值，且与刷新前不同，则认为稳定。
    """
    deadline = time.time() + timeout
    prev = capture_window(ctx.hwnd)
    while time.time() < deadline:
        if not ctx._running:
            return False
        time.sleep(interval)
        curr = capture_window(ctx.hwnd)
        diff = cv2.absdiff(prev, curr).mean()
        if diff < threshold:
            if before_img is not None and cv2.absdiff(before_img, curr).mean() < before_threshold:
                prev = curr
                continue
            return True
        prev = curr
    return False


class ShopFlow:
    """状态驱动的商店自动化流程。"""

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

        # 预加载所有模板
        self._tpl_covenant = templates.covenant
        self._tpl_mystic = templates.mystic
        self._tpl_buy_confirm = templates.buy_confirm
        self._tpl_refresh = templates.refresh_button
        self._tpl_refresh_yes = templates.refresh_yes

    def run(self) -> ShopContext:
        """执行商店自动化主循环。"""
        self._init()

        while self.ctx.should_continue:
            screenshot = capture_window(self.ctx.hwnd)
            self.ctx.loop_count += 1

            state = self.ctx.state

            if state == ShopState.SCANNING:
                self._handle_scanning(screenshot)
            elif state == ShopState.BUYING_COVENANT:
                self._handle_buying(screenshot)
            elif state == ShopState.BUYING_MYSTIC:
                self._handle_buying(screenshot)
            elif state == ShopState.SWIPING:
                self._handle_swiping(screenshot)
            elif state == ShopState.REFRESHING:
                self._handle_refreshing(screenshot)
            elif state == ShopState.DONE or state == ShopState.ERROR:
                break

        self._finish()
        return self.ctx

    # ---- 初始化 ----

    def _init(self) -> None:
        """初始化校验和准备。"""
        self.log.info("===== 初始化 =====")
        short_sleep(0.5)

        if self.ctx.money < 280000:
            self.log.error("錯誤: 金幣不足28萬")
            raise ValueError("out of money")

        if self.ctx.stone < 3:
            self.log.error("錯誤: 天空石不足以刷新商店")
            raise ValueError("out of stone")

        if self.ctx.mode == 3 and self.ctx.expect_num > self.ctx.stone:
            self.log.error("錯誤: 天空石使用數量大於持有數量")
            raise ValueError("stone input error")

        self.log.info("正在尋找遊戲視窗......")
        short_sleep(0.5)

        try:
            win32gui.SetForegroundWindow(self.ctx.hwnd)
        except Exception:
            pass  # 窗口可能已在前台
        short_sleep(0.5)

        self.log.info("遊戲視窗已找到")
        short_sleep(0.5)
        self.log.info("初始化完成")
        short_sleep(0.5)
        self.log.info("===== 刷商店 =====")
        short_sleep(0.5)

    # ---- SCANNING：扫描商店 ----

    def _handle_scanning(self, screenshot: np.ndarray) -> None:
        """扫描商店，查找目标书签。"""
        # 先检查是否需要刷新
        if self.ctx.need_refresh:
            self.ctx.state = ShopState.REFRESHING
            return

        # 检测圣约书签
        if not self.ctx.covenant_found:
            covenant_loc = self.matcher.match(
                screenshot, self._tpl_covenant,
                self.config.match_threshold_location, "covenant"
            )
            if covenant_loc is not None:
                cx, cy = covenant_loc.center
                self.log.info(f"找到聖約書籤 位置:({cx},{cy})")
                self.ctx.target = BookmarkTarget(
                    match_center=(cx, cy), label="聖約"
                )
                self.ctx.state = ShopState.BUYING_COVENANT
                return

        # 检测神秘书签
        if not self.ctx.mystic_found:
            mystic_loc = self.matcher.match(
                screenshot, self._tpl_mystic,
                self.config.match_threshold_location, "mystic"
            )
            if mystic_loc is not None:
                mx, my = mystic_loc.center
                self.log.info(f"找到神秘書籤 位置:({mx},{my})")
                self.ctx.target = BookmarkTarget(
                    match_center=(mx, my), label="神秘"
                )
                self.ctx.state = ShopState.BUYING_MYSTIC
                return

        # 都没找到，滑动商店列表
        self.ctx.state = ShopState.SWIPING

    # ---- BUYING：购买书签（统一处理圣约和神秘） ----

    def _handle_buying(self, screenshot: np.ndarray) -> None:
        """购买书签的统一流程。

        修复 Bug #8：圣约和神秘购买逻辑统一为一个方法。
        修复 Bug #5：购买成功后才设 found=True。
        """
        target = self.ctx.target
        if target is None:
            self.ctx.state = ShopState.SCANNING
            return

        is_covenant = self.ctx.state == ShopState.BUYING_COVENANT
        mode_match = 1 if is_covenant else 2
        cost = 184000 if is_covenant else 280000

        # 计算点击位置：商品中心偏右偏下
        tx, ty = target.match_center
        click_x = tx + 800
        click_y = ty + 40

        max_retry = self.config.max_retry

        for retry in range(max_retry):
            if not self.ctx._running:
                return
            short_sleep(0.5)

            sx, sy = self.input.scale_coords(self.ctx.hwnd, click_x, click_y)
            self.log.debug(f"點擊{target.label}商品 ({sx:.0f},{sy:.0f}) 重試:{retry+1}")
            self.input.double_click(self.ctx.hwnd, sx, sy)

            # 等待购买按钮出现
            buy_btn = wait_for(
                self.ctx, self.matcher, self._tpl_buy_confirm,
                self.config.match_threshold_button, "buy_confirm"
            )

            if buy_btn is not None:
                bx, by = buy_btn.center

                # 点击购买按钮
                for retry2 in range(max_retry):
                    if not self.ctx._running:
                        return
                    short_sleep(0.3)
                    sbx, sby = self.input.scale_coords(self.ctx.hwnd, bx, by)
                    self.log.debug(f"點擊購買按鈕 ({sbx:.0f},{sby:.0f}) 重試:{retry2+1}")
                    self.input.double_click(self.ctx.hwnd, sbx, sby)

                    gone = wait_for_gone(
                        self.ctx, self.matcher, self._tpl_buy_confirm,
                        self.config.match_threshold_button, "buy_confirm"
                    )
                    if gone:
                        break
                else:
                    self.log.info("購買確認超時，跳過")
                    # 购买确认超时，重试外层
                    continue

                # ---- 购买成功 ----
                if self.ctx.mode == mode_match:
                    self.ctx.expect_num -= 1
                    self.log.info(f"剩餘次數: {self.ctx.expect_num}次")

                self.ctx.money -= cost
                if is_covenant:
                    self.ctx.covenant_bought += 1
                    self.ctx.covenant_found = True  # Bug #5 修复：成功后才设 True
                else:
                    self.ctx.mystic_bought += 1
                    self.ctx.mystic_found = True  # Bug #5 修复：成功后才设 True

                # 回到扫描状态
                self.ctx.target = None
                self.ctx.state = ShopState.SCANNING
                return

            self.log.info("未找到購買按鈕，重試...")
            short_sleep(1.0)

        # 重试用尽，回到扫描
        self.log.info(f"{target.label}購買重試耗盡，繼續掃描")
        self.ctx.target = None
        self.ctx.state = ShopState.SCANNING

    # ---- SWIPING：滑动商店列表 ----

    def _handle_swiping(self, screenshot: np.ndarray) -> None:
        """滑动商店列表。

        修复 Bug #2：连续滑动失败计数器 + 阈值退出。
        """
        self.log.info("滑動商店列表")
        short_sleep(0.3)

        before_swipe = capture_window(self.ctx.hwnd)

        sx1, sy1 = self.input.scale_coords(self.ctx.hwnd, 1400, 500)
        sx2, sy2 = self.input.scale_coords(self.ctx.hwnd, 1400, 200)
        self.input.swipe(self.ctx.hwnd, sx1, sy1, sx2, sy2, 0.1)
        self.ctx.need_refresh = True

        short_sleep(1.0)

        after_swipe = capture_window(self.ctx.hwnd)
        changed = cv2.absdiff(before_swipe, after_swipe).mean() > 5

        if not changed:
            self.ctx.swipe_fail_count += 1
            limit = self.config.swipe_fail_limit
            self.log.info(f"滑動未生效 ({self.ctx.swipe_fail_count}/{limit})")
            if self.ctx.swipe_fail_count >= limit:
                self.log.error("連續滑動失敗過多，停止")
                raise RuntimeError("swipe failed repeatedly")
        else:
            self.ctx.swipe_fail_count = 0

        # 滑动后回到扫描
        self.ctx.state = ShopState.SCANNING

    # ---- REFRESHING：刷新商店 ----

    def _handle_refreshing(self, screenshot: np.ndarray) -> None:
        """刷新商店流程。

        修复 Bug #1：wait_for_stable 超时后 break 退出内层循环，
        而非 continue 导致在 retry2 中无效重试。
        """
        refresh_loc = self.matcher.match(
            screenshot, self._tpl_refresh,
            self.config.match_threshold_refresh, "refresh"
        )

        if refresh_loc is None:
            self.log.info("找不到刷新按鈕，重新滑動...")
            self.ctx.covenant_found = False
            self.ctx.mystic_found = False
            self.ctx.need_refresh = False
            short_sleep(1.0)
            self.ctx.state = ShopState.SCANNING
            return

        before_refresh = capture_window(self.ctx.hwnd)
        rx, ry = refresh_loc.center
        max_retry = self.config.max_retry

        for retry in range(max_retry):
            if not self.ctx._running:
                return
            short_sleep(0.5)

            srx, sry = self.input.scale_coords(self.ctx.hwnd, rx, ry)
            self.log.debug(f"點擊刷新按鈕 ({srx:.0f},{sry:.0f}) 重試:{retry+1}")
            self.input.double_click(self.ctx.hwnd, srx, sry)

            # 等待确认对话框
            yes_loc = wait_for(
                self.ctx, self.matcher, self._tpl_refresh_yes,
                self.config.match_threshold_confirm, "refresh_yes"
            )

            if yes_loc is not None:
                yx, yy = yes_loc.center
                stable = False

                for retry2 in range(max_retry):
                    if not self.ctx._running:
                        return
                    short_sleep(0.3)
                    syx, syy = self.input.scale_coords(self.ctx.hwnd, yx, yy)
                    self.log.debug(f"點擊確認刷新 ({syx:.0f},{syy:.0f}) 重試:{retry2+1}")
                    self.input.double_click(self.ctx.hwnd, syx, syy)

                    gone = wait_for_gone(
                        self.ctx, self.matcher, self._tpl_refresh_yes,
                        self.config.match_threshold_confirm, "refresh_yes",
                        timeout=self.config.wait_timeout_long,
                    )
                    if gone:
                        if wait_for_stable(self.ctx, before_refresh):
                            stable = True
                        else:
                            # Bug #1 修复：超时后 break 而非 continue
                            self.log.info("商店載入超時，重試外層...")
                        break
                else:
                    self.log.info("刷新確認超時，重試外層...")

                if not stable:
                    # Bug #1 修复：continue 回到外层 retry，重新点击刷新按钮
                    continue

                # ---- 刷新成功 ----
                self.ctx.stone -= 3
                self.ctx.refresh_count += 1
                self.log.info(f"刷新成功，已用{self.ctx.refresh_count * 3}天空石")

                if self.ctx.mode == 3:
                    self.ctx.expect_num -= 3
                    self.log.info(f"剩餘次數: {int(self.ctx.expect_num / 3)}次")

                self.ctx.need_refresh = False
                self.ctx.covenant_found = False
                self.ctx.mystic_found = False

                short_sleep(1.5)
                self.ctx.state = ShopState.SCANNING
                return

            self.log.info("未彈出確認對話框，重試...")
            short_sleep(1.0)

        # 刷新重试耗尽
        self.log.info("刷新重試耗盡，繼續掃描")
        self.ctx.state = ShopState.SCANNING

    # ---- 结算 ----

    def _finish(self) -> None:
        """输出结算信息。"""
        self.log.info("===== 結算 =====")
        self.log.info("共花費:")
        self.log.info(f"天空石: {self.ctx.total_stone_used}個")
        self.log.info(f"金幣: {self.ctx.total_money_used}元")
        self.log.info("獲得書籤:")
        self.log.info(f"聖約: {self.ctx.covenant_bought}次")
        self.log.info(f"神秘: {self.ctx.mystic_bought}次")
