"""AdbDeviceBackend — 以 adb 指令截圖/輸入的設備後端。"""

from __future__ import annotations

import time

import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT
from device.adb_client import AdbClient
from device.base import DeviceBackend, DeviceError, scale_ref_to_device
from device.humanize import HumanizeSettings, jitter_point, jitter_swipe_endpoints, clamp_ref, random_gap


class AdbDeviceBackend(DeviceBackend):
    def __init__(self, client: AdbClient, hs: HumanizeSettings | None = None):
        self._client = client
        self._hs = hs or HumanizeSettings()
        self._w, self._h = client.wm_size()        # 啟動偵測一次,快取
        if self._w <= 0 or self._h <= 0:
            raise DeviceError(f"無效的設備解析度: {self._w}x{self._h}")

    def capture(self) -> np.ndarray:
        png = self._client.exec_out(["screencap", "-p"])
        try:
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            raise DeviceError("adb screencap 解碼失敗")
        if img is None:
            raise DeviceError("adb screencap 解碼失敗")
        if (self._w, self._h) != (REF_WIDTH, REF_HEIGHT):
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img

    def click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        dx, dy = scale_ref_to_device(ref_x, ref_y, self._w, self._h)
        self._client.tap(dx, dy)

    def double_click(self, ref_x: float, ref_y: float) -> None:
        # adb 無原生雙擊 → 兩次 tap,間隔隨機化(取代固定 0.05)
        self.click(ref_x, ref_y)
        time.sleep(random_gap(self._hs.double_click_gap, self._hs.double_click_spread))
        self.click(ref_x, ref_y)

    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None:
        if self._hs.enabled:
            (x1, y1), (x2, y2) = jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
            x1, y1 = clamp_ref(x1, y1)
            x2, y2 = clamp_ref(x2, y2)
            duration = random_gap(duration, self._hs.swipe_duration_spread)
        sx1, sy1 = scale_ref_to_device(x1, y1, self._w, self._h)
        sx2, sy2 = scale_ref_to_device(x2, y2, self._w, self._h)
        self._client.swipe(sx1, sy1, sx2, sy2, int(duration * 1000))

    @property
    def resolution(self) -> tuple[int, int]:
        return self._w, self._h
