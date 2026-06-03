"""输入后端抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class InputBackend(ABC):
    """鼠标输入后端的抽象接口。

    所有坐标均为窗口客户区坐标（像素），由实现负责转换为屏幕坐标。
    """

    @abstractmethod
    def click(self, hwnd: int, x: float, y: float) -> None:
        """在指定位置单击。

        Args:
            hwnd: 目标窗口句柄。
            x: 客户区 X 坐标（像素）。
            y: 客户区 Y 坐标（像素）。
        """

    @abstractmethod
    def double_click(self, hwnd: int, x: float, y: float) -> None:
        """在指定位置双击。"""

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
        """从 (x1,y1) 拖拽到 (x2,y2)。

        Args:
            duration: 拖拽持续时间（秒）。
        """

    def scale_coords(
        self, hwnd: int, ref_x: float, ref_y: float
    ) -> tuple[float, float]:
        """将参考分辨率坐标转换为窗口实际坐标。

        Args:
            hwnd: 目标窗口句柄。
            ref_x: 参考分辨率 X 坐标 (基于 1920)。
            ref_y: 参考分辨率 Y 坐标 (基于 1080)。

        Returns:
            (actual_x, actual_y) 窗口客户区像素坐标。
        """
        import win32gui
        from capture import REF_WIDTH, REF_HEIGHT

        rect = win32gui.GetClientRect(hwnd)
        actual_x = ref_x * rect[2] / REF_WIDTH
        actual_y = ref_y * rect[3] / REF_HEIGHT
        return actual_x, actual_y
