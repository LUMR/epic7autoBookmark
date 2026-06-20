"""測試替身 — FakeDevice 用於 flow 整合測試,無 IO。"""
from __future__ import annotations

import numpy as np

from device.base import DeviceBackend


class FakeDevice(DeviceBackend):
    """可程式化的假設備:capture 回固定圖,點擊/滑動記錄於 calls。"""

    def __init__(self, image: np.ndarray | None = None):
        self._image = image if image is not None else np.zeros(
            (1080, 1920, 3), dtype=np.uint8
        )
        self.calls: list[tuple] = []

    def set_image(self, image: np.ndarray) -> None:
        self._image = image

    def capture(self) -> np.ndarray:
        return self._image

    def click(self, ref_x: float, ref_y: float) -> None:
        self.calls.append(("click", ref_x, ref_y))

    def double_click(self, ref_x: float, ref_y: float) -> None:
        self.calls.append(("double_click", ref_x, ref_y))

    def swipe(self, x1, y1, x2, y2, duration=0.1) -> None:
        self.calls.append(("swipe", x1, y1, x2, y2, duration))
