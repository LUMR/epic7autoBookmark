"""設備門面套件 — 統一截圖/輸入/縮放/生命週期,平台無關。"""

from __future__ import annotations

from config import AppConfig
from device.base import DeviceBackend, DeviceError
from device.windows import WindowsDeviceBackend, find_game_window
from device.adb_client import AdbClient
from device.adb import AdbDeviceBackend

__all__ = ["DeviceBackend", "DeviceError", "create_device"]


def create_device(config: AppConfig) -> DeviceBackend:
    """依 config.platform 建立設備後端。"""
    if config.platform == "windows":
        hwnd = find_game_window(config.window_title)
        if not hwnd:
            raise DeviceError("找不到遊戲視窗，請確認遊戲已開啟")
        return WindowsDeviceBackend(hwnd, config.capture_method)
    if config.platform == "adb":
        client = AdbClient(
            adb_path=config.adb_path,
            connect=config.adb_connect,
            serial=config.adb_serial,
        )
        return AdbDeviceBackend(client)
    raise DeviceError(f"不支持的平台: {config.platform}")
