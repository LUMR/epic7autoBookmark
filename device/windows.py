"""WindowsDeviceBackend — 組合 BitBlt/MSS 截圖 + SendInput 輸入 + 客戶區縮放。

行為與舊版直接呼叫 capture_window/sendinput 完全一致,僅收攏到 DeviceBackend 介面。
"""

from __future__ import annotations

import win32gui

import numpy as np

from capture import capture_window
from capture.bitblt import close_all
from device.base import DeviceBackend
from device.humanize import HumanizeSettings, jitter_point, jitter_swipe_endpoints, clamp_ref, random_gap
from input.base import scale_to_client
from input.sendinput import SendInputBackend


def find_game_window(window_title: str) -> int | None:
    """查找遊戲視窗句柄(自 worker.py 遷入)。

    回傳面積最大且標題包含關鍵字的可見視窗 HWND,未找到回 None。
    """
    candidates: list[tuple[int, int]] = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and window_title in win32gui.GetWindowText(hwnd):
            rect = win32gui.GetClientRect(hwnd)
            candidates.append((rect[2] * rect[3], hwnd))

    win32gui.EnumWindows(callback, None)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


class WindowsDeviceBackend(DeviceBackend):
    def __init__(self, hwnd: int, capture_method: str = "auto", hs: HumanizeSettings | None = None):
        self._hwnd = hwnd
        self._capture_method = capture_method
        self._hs = hs or HumanizeSettings()
        self._input = SendInputBackend(self._hs)

    def capture(self) -> np.ndarray:
        return capture_window(self._hwnd, self._capture_method)

    def click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        x, y = scale_to_client(self._hwnd, ref_x, ref_y)
        self._input.click(self._hwnd, x, y)

    def double_click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        x, y = scale_to_client(self._hwnd, ref_x, ref_y)
        self._input.double_click(self._hwnd, x, y)

    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None:
        if self._hs.enabled:
            (x1, y1), (x2, y2) = jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
            x1, y1 = clamp_ref(x1, y1)
            x2, y2 = clamp_ref(x2, y2)
            duration = random_gap(duration, self._hs.swipe_duration_spread)
        sx1, sy1 = scale_to_client(self._hwnd, x1, y1)
        sx2, sy2 = scale_to_client(self._hwnd, x2, y2)
        self._input.swipe(self._hwnd, sx1, sy1, sx2, sy2, duration)

    def prepare(self) -> None:
        try:
            win32gui.SetForegroundWindow(self._hwnd)
        except Exception:
            pass  # 視窗可能已在前台

    def close(self) -> None:
        close_all()

    @property
    def resolution(self) -> tuple[int, int]:
        rect = win32gui.GetClientRect(self._hwnd)
        return rect[2], rect[3]
