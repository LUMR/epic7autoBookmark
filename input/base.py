"""輸入後端抽象基類。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import win32gui

from capture import REF_WIDTH, REF_HEIGHT


def scale_to_client(hwnd: int, ref_x: float, ref_y: float) -> tuple[float, float]:
    """將參考解析度座標轉換為視窗客戶區像素座標（純函數）。

    Args:
        hwnd: 目標視窗句柄。
        ref_x: 參考解析度 X 座標（基於 1920）。
        ref_y: 參考解析度 Y 座標（基於 1080）。

    Returns:
        (actual_x, actual_y) 視窗客戶區像素座標。
    """
    rect = win32gui.GetClientRect(hwnd)
    actual_x = ref_x * rect[2] / REF_WIDTH
    actual_y = ref_y * rect[3] / REF_HEIGHT
    return actual_x, actual_y


class InputBackend(ABC):
    """滑鼠輸入後端的抽象介面。

    所有座標均為視窗客戶區座標（像素），由實現負責轉換為螢幕座標。
    """

    @abstractmethod
    def click(self, hwnd: int, x: float, y: float) -> None:
        """在指定位置單擊。"""

    @abstractmethod
    def double_click(self, hwnd: int, x: float, y: float) -> None:
        """在指定位置雙擊。"""

    @abstractmethod
    def swipe(
        self,
        hwnd: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.1,
    ) -> None:
        """從 (x1,y1) 拖拽到 (x2,y2)。"""

    def scale_coords(
        self, hwnd: int, ref_x: float, ref_y: float
    ) -> tuple[float, float]:
        """將參考解析度座標轉為實際座標（委託純函數 scale_to_client）。"""
        return scale_to_client(hwnd, ref_x, ref_y)
