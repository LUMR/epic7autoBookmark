"""設備門面套件 — 統一截圖/輸入/縮放/生命週期,平台無關。"""

from __future__ import annotations

from config import AppConfig
from device.adb import AdbDeviceBackend
from device.adb_client import AdbClient
from device.base import DeviceBackend, DeviceError
from device.humanize import HumanizeSettings
from device.windows import WindowsDeviceBackend, find_game_window

__all__ = ["DeviceBackend", "DeviceError", "create_device"]


def _humanize_settings(config: AppConfig) -> HumanizeSettings:
    """從 AppConfig 扁平欄位組裝 HumanizeSettings,注入後端。

    double_click_gap 固定 0.05(不暴露至 config)。
    """
    return HumanizeSettings(
        enabled=config.humanize_enabled,
        jitter_px=config.humanize_jitter_px,
        swipe_jitter_px=config.humanize_swipe_jitter_px,
        double_click_gap=0.05,
        double_click_spread=config.humanize_double_click_spread,
        swipe_duration_spread=config.humanize_swipe_duration_spread,
        curve_strength=config.humanize_curve_strength,
        move_steps=config.humanize_move_steps,
    )


def create_device(config: AppConfig) -> DeviceBackend:
    """依 config.platform 建立設備後端,注入人性化設定。"""
    hs = _humanize_settings(config)
    if config.platform == "windows":
        hwnd = find_game_window(config.window_title)
        if not hwnd:
            raise DeviceError("找不到遊戲視窗，請確認遊戲已開啟")
        return WindowsDeviceBackend(hwnd, config.capture_method, hs)
    if config.platform == "adb":
        client = AdbClient(
            adb_path=config.adb_path,
            connect=config.adb_connect,
            serial=config.adb_serial,
        )
        return AdbDeviceBackend(client, hs)
    raise DeviceError(f"不支持的平台: {config.platform}")
