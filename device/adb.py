"""AdbDeviceBackend — 以 adb 指令截圖/輸入的設備後端。"""

from __future__ import annotations

import time

import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT
from device.adb_client import AdbClient
from device.base import DeviceBackend, DeviceError, scale_ref_to_device


class AdbDeviceBackend(DeviceBackend):
    def __init__(self, client: AdbClient):
        self._client = client
        self._w, self._h = client.wm_size()        # 啟動偵測一次,快取
        # 防禦:目前 parse_wm_size 不會回 0/負數,但保留此檢查以防未來解析邏輯變動
        if self._w <= 0 or self._h <= 0:
            raise DeviceError(f"無效的設備解析度: {self._w}x{self._h}")

    def capture(self) -> np.ndarray:
        # exec-out: 二進制透傳,無 \r\n 污染(shell 模式才會壞 PNG)
        png = self._client.exec_out(["screencap", "-p"])
        try:
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            # 空/截斷 bytes 觸發 OpenCV assertion(imdecode_ 內部)
            raise DeviceError("adb screencap 解碼失敗")
        if img is None:
            raise DeviceError("adb screencap 解碼失敗")
        if (self._w, self._h) != (REF_WIDTH, REF_HEIGHT):
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img

    def click(self, ref_x: float, ref_y: float) -> None:
        dx, dy = scale_ref_to_device(ref_x, ref_y, self._w, self._h)
        self._client.tap(dx, dy)

    def double_click(self, ref_x: float, ref_y: float) -> None:
        # adb 無原生雙擊 → 兩次 tap,保持與 Windows 行為等價
        self.click(ref_x, ref_y)
        time.sleep(0.05)
        self.click(ref_x, ref_y)

    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None:
        sx1, sy1 = scale_ref_to_device(x1, y1, self._w, self._h)
        sx2, sy2 = scale_ref_to_device(x2, y2, self._w, self._h)
        self._client.swipe(sx1, sy1, sx2, sy2, int(duration * 1000))

    @property
    def resolution(self) -> tuple[int, int]:
        return self._w, self._h
