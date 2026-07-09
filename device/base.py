"""DeviceBackend 抽象基類 + 純函數(解析/縮放),無 IO 副作用,易單測。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

import numpy as np

from capture import REF_WIDTH, REF_HEIGHT


class DeviceError(Exception):
    """設備相關錯誤(連線/解析/找不到設備等)。"""


def parse_wm_size(text: str) -> tuple[int, int]:
    """解析 `adb shell wm size` 輸出,回傳 (width, height)。"""
    m = re.search(r"(\d+)\s*[xX]\s*(\d+)", text)
    if not m:
        raise DeviceError(f"無法解析 wm size: {text!r}")
    return int(m.group(1)), int(m.group(2))


def parse_devices(text: str) -> list[str]:
    """解析 `adb devices` 輸出,回傳狀態為 'device' 的可用 serial 列表。"""
    serials: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def scale_ref_to_device(
    ref_x: float, ref_y: float, dev_w: int, dev_h: int
) -> tuple[int, int]:
    """參考解析度座標(1920×1080)→ 設備實際座標。"""
    return round(ref_x * dev_w / REF_WIDTH), round(ref_y * dev_h / REF_HEIGHT)


def select_serial(available: list[str], preferred: str | None) -> str:
    """依偏好/可用清單決定 serial:指定優先 → 唯一自動取 → 0/多台報錯。"""
    if preferred is not None:
        return preferred
    if len(available) == 0:
        raise DeviceError("找不到任何 adb 設備")
    if len(available) > 1:
        raise DeviceError(
            f"偵測到多個設備 {available}，請在 config 指定 adb_serial"
        )
    return available[0]


class DeviceBackend(ABC):
    """統一設備門面。

    契約:
      - capture() 恆輸出 BGR ndarray,形狀 (REF_HEIGHT, REF_WIDTH, 3)。
      - click/swipe 吃「參考解析度座標」(基於 1920×1080),由實作內部縮放。
      - 上層 flow 與平台無關。
    """

    @abstractmethod
    def capture(self) -> np.ndarray: ...

    @abstractmethod
    def click(self, ref_x: float, ref_y: float) -> None: ...

    @abstractmethod
    def double_click(self, ref_x: float, ref_y: float) -> None: ...

    @abstractmethod
    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None: ...

    def prepare(self) -> None:
        """前置(Windows=SetForegroundWindow;ADB=連線檢查)。預設 noop。"""

    def close(self) -> None:
        """釋放資源。預設 noop。"""

    @property
    def resolution(self) -> tuple[int, int]:
        """設備實際解析度(日誌/偵錯)。子類覆寫。"""
        return REF_WIDTH, REF_HEIGHT

    @property
    def window_handle(self) -> int | None:
        """原生視窗句柄(Windows),供 detect 截圖前的前台檢查;無則 None。"""
        return None
