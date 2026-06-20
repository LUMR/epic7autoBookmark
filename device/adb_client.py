"""AdbClient — adb 子進程封裝。

遮蔽 subprocess 細節:路徑定位、connect、devices、exec-out、wm size、tap/swipe。
"""

from __future__ import annotations

import shutil
import subprocess

from device.base import (
    DeviceError,
    parse_devices,
    parse_wm_size,
    select_serial,
)


class AdbClient:
    """對單一 adb 設備的指令封裝。"""

    def __init__(
        self,
        adb_path: str | None = None,
        connect: str | None = None,
        serial: str | None = None,
    ):
        # 1. 定位 adb
        self._adb = adb_path or shutil.which("adb") or shutil.which("adb.exe")
        if not self._adb:
            raise DeviceError("找不到 adb，請安裝或在 config 指定 adb_path")

        # 2. 模擬器/WiFi 連線
        if connect:
            self._run_global(["connect", connect])

        # 3. 決定 serial
        if serial is None:
            serial = select_serial(self.devices(), None)
        self._serial = serial

    # ---- 底層執行 ----

    def _run_global(self, args: list[str], timeout: float = 10.0) -> str:
        """不帶 serial 的 adb 命令(devices/connect)。"""
        try:
            res = subprocess.run(
                [self._adb, *args], capture_output=True, text=True, timeout=timeout
            )
            if res.returncode != 0:
                raise DeviceError(f"adb 命令失敗 {' '.join(args)}: {res.stderr.strip()}")
            return res.stdout
        except FileNotFoundError as e:
            raise DeviceError(f"adb 執行失敗: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise DeviceError(f"adb 命令逾時 {' '.join(args)}") from e

    def run(self, args: list[str], timeout: float = 10.0) -> str:
        """帶 -s serial 的 shell 命令,回傳 stdout 文字。"""
        return self._run_global(["-s", self._serial, *args], timeout=timeout)

    def exec_out(self, args: list[str], timeout: float = 10.0) -> bytes:
        """exec-out(二進制安全),回傳 bytes。"""
        try:
            res = subprocess.run(
                [self._adb, "-s", self._serial, "exec-out", *args],
                capture_output=True, timeout=timeout,
            )
            if res.returncode != 0:
                raise DeviceError(
                    f"exec-out 失敗 {' '.join(args)}: {res.stderr.decode(errors='replace').strip()}"
                )
            return res.stdout
        except subprocess.TimeoutExpired as e:
            raise DeviceError(f"exec-out 逾時 {' '.join(args)}") from e

    # ---- 高階能力 ----

    def devices(self) -> list[str]:
        return parse_devices(self._run_global(["devices"]))

    def wm_size(self) -> tuple[int, int]:
        return parse_wm_size(self.run(["shell", "wm", "size"]))

    def tap(self, x: int, y: int) -> None:
        self.run(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        """滑動。duration_ms 為毫秒(注意:DeviceBackend.swipe 的 duration 是秒,換算在 AdbDeviceBackend)。"""
        self.run(
            ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
        )
