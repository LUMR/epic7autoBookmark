"""SendInput 輸入後端 — 使用 Win32 SendInput API 发送鼠标事件。

Epic Seven (Unity/OpenGL) 不响应 PostMessage 鼠标消息,因此只能使用系统级输入。
人性化啟用時:click 沿貝茲曲線移動游標 + 加減速;swipe 沿貝茲軌跡拖曳;
down-up 停留與雙擊間隔隨機化。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import win32api
import win32con
import win32gui

from input.base import InputBackend

if TYPE_CHECKING:
    # 僅型別檢查時用;runtime 不 import 以避開 input.sendinput ↔ device.windows 循環
    from device.humanize import HumanizeSettings


class SendInputBackend(InputBackend):
    """透過 SendInput API 發送滑鼠事件的輸入後端。"""

    def __init__(self, hs: "HumanizeSettings | None" = None):
        # 延遲 import:device.humanize 經由 device/__init__ → device.windows → input.sendinput
        # 形成循環;移到 runtime 才執行,此時所有模組已就緒。
        from device.humanize import (
            HumanizeSettings as _HS,
            bezier_points,
            ease_in_out_weights,
            random_gap,
            roll_sign,
        )
        self._hs = hs or _HS()
        # 綁定人性化純函數至實例,避免後續方法重複 import 查找
        self._bezier_points = bezier_points
        self._ease_in_out_weights = ease_in_out_weights
        self._random_gap = random_gap
        self._roll_sign = roll_sign

    def click(self, hwnd: int, x: float, y: float) -> None:
        sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        if self._hs.enabled:
            self._move_along_bezier(sx, sy)
        else:
            win32api.SetCursorPos((sx, sy))
            time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx, sy, 0, 0)
        time.sleep(self._random_gap(0.02, 0.015))  # down-up 停留隨機
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx, sy, 0, 0)

    def double_click(self, hwnd: int, x: float, y: float) -> None:
        self.click(hwnd, x, y)
        time.sleep(self._random_gap(self._hs.double_click_gap, self._hs.double_click_spread))
        self.click(hwnd, x, y)

    def swipe(
        self,
        hwnd: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.1,
    ) -> None:
        sx1, sy1 = win32gui.ClientToScreen(hwnd, (int(x1), int(y1)))
        sx2, sy2 = win32gui.ClientToScreen(hwnd, (int(x2), int(y2)))
        if self._hs.enabled:
            self._drag_along_bezier(sx1, sy1, sx2, sy2, duration)
            return
        # disabled:原勻速直線(位元級退回)
        win32api.SetCursorPos((sx1, sy1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)
        steps = 10
        step_delay = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(sx1 + (sx2 - sx1) * t)
            cy = int(sy1 + (sy2 - sy1) * t)
            win32api.SetCursorPos((cx, cy))
            time.sleep(step_delay)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)

    # ---- 內部:貝茲軌跡生成(螢幕座標空間)----

    def _bezier_control_points(self, sx, sy, tx, ty):
        """起終點 + 法向偏移的控制點。回傳 (p0, p1, p2, p3)。"""
        dx, dy = tx - sx, ty - sy
        dist = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / dist, dx / dist            # 連線法向量
        off = dist * self._hs.curve_strength * self._roll_sign()
        p0 = (sx, sy)
        p1 = (sx + dx / 3 + nx * off, sy + dy / 3 + ny * off)
        p2 = (sx + 2 * dx / 3 + nx * off, sy + 2 * dy / 3 + ny * off)
        p3 = (tx, ty)
        return p0, p1, p2, p3

    def _move_along_bezier(self, tx, ty) -> None:
        """游標從當前位置沿貝茲曲線(加減速)移到目標。"""
        sx, sy = win32api.GetCursorPos()
        if (sx, sy) == (tx, ty):
            return
        p0, p1, p2, p3 = self._bezier_control_points(sx, sy, tx, ty)
        pts = self._bezier_points(p0, p1, p2, p3, self._hs.move_steps)
        weights = self._ease_in_out_weights(self._hs.move_steps)
        move_dur = self._random_gap(0.15, 0.08)
        for i in range(len(weights)):
            px, py = pts[i + 1]
            win32api.SetCursorPos((int(px), int(py)))
            time.sleep(weights[i] * move_dur)

    def _drag_along_bezier(self, sx1, sy1, sx2, sy2, duration) -> None:
        """按住左鍵沿貝茲軌跡(加減速)拖曳。"""
        p0, p1, p2, p3 = self._bezier_control_points(sx1, sy1, sx2, sy2)
        pts = self._bezier_points(p0, p1, p2, p3, self._hs.move_steps)
        weights = self._ease_in_out_weights(self._hs.move_steps)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)
        for i in range(len(weights)):
            px, py = pts[i + 1]
            win32api.SetCursorPos((int(px), int(py)))
            time.sleep(weights[i] * duration)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)
