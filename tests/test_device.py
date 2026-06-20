"""device 層測試 — 純函數解析/縮放 + factory + 後端委派。"""
import subprocess

import numpy as np
import pytest
from unittest.mock import MagicMock

from device.adb import AdbDeviceBackend
from device.adb_client import AdbClient
from device.base import (
    DeviceError,
    parse_wm_size,
    parse_devices,
    scale_ref_to_device,
    select_serial,
)
from device.windows import WindowsDeviceBackend


def test_parse_wm_size():
    assert parse_wm_size("Physical size: 1920x1080") == (1920, 1080)
    assert parse_wm_size("Physical size: 1280x720") == (1280, 720)


def test_parse_wm_size_invalid():
    with pytest.raises(DeviceError):
        parse_wm_size("no size info here")


def test_parse_devices_filters_unusable():
    text = (
        "List of devices attached\n"
        "127.0.0.1:7555\tdevice\n"
        "emulator-5554\toffline\n"
        "usb123\tunauthorized\n"
    )
    assert parse_devices(text) == ["127.0.0.1:7555"]


def test_scale_ref_to_device_1080p_identity():
    assert scale_ref_to_device(960, 540, 1920, 1080) == (960, 540)


def test_scale_ref_to_device_720p():
    # 960/1920*1280 = 640; 540/1080*720 = 360
    assert scale_ref_to_device(960, 540, 1280, 720) == (640, 360)


def test_select_serial_preferred():
    assert select_serial(["a", "b"], "b") == "b"


def test_select_serial_single():
    assert select_serial(["only"], None) == "only"


def test_select_serial_none_raises():
    with pytest.raises(DeviceError):
        select_serial([], None)


def test_select_serial_multiple_raises():
    with pytest.raises(DeviceError):
        select_serial(["a", "b"], None)


def _client_with_devices(monkeypatch, devices_text, adb="adb"):
    """建 AdbClient 但攔截 subprocess,devices 回 devices_text。"""
    calls = []

    def fake_run(cmd, timeout=10, **kwargs):
        calls.append(cmd)
        if "devices" in cmd:
            out = devices_text
        elif "wm" in cmd and "size" in cmd:
            out = "Physical size: 1920x1080"
        else:
            out = ""
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=out, stderr="")

    client_cls = AdbClient
    monkeypatch.setattr("device.adb_client.subprocess.run", fake_run)
    monkeypatch.setattr("device.adb_client.shutil.which", lambda x: adb)
    return client_cls, calls


def test_adb_client_picks_single_device(monkeypatch):
    cls, _ = _client_with_devices(monkeypatch, "List of devices attached\nserial1\tdevice\n")
    client = cls(serial=None)
    assert client._serial == "serial1"


def test_adb_client_uses_preferred_serial(monkeypatch):
    cls, _ = _client_with_devices(monkeypatch, "List of devices attached\na\tdevice\nb\tdevice\n")
    client = cls(serial="b")
    assert client._serial == "b"


def test_adb_client_no_device_raises(monkeypatch):
    cls, _ = _client_with_devices(monkeypatch, "List of devices attached\n")
    with pytest.raises(DeviceError):
        cls(serial=None)


def test_adb_client_missing_adb_raises(monkeypatch):
    monkeypatch.setattr("device.adb_client.shutil.which", lambda x: None)
    with pytest.raises(DeviceError):
        AdbClient(serial=None)


def test_adb_client_tap_builds_command(monkeypatch):
    cls, calls = _client_with_devices(monkeypatch, "List of devices attached\ns\tdevice\n")
    client = cls(serial="s")
    client.tap(640, 360)
    assert calls[-1] == ["adb", "-s", "s", "shell", "input", "tap", "640", "360"]


def test_adb_client_wm_size(monkeypatch):
    cls, _ = _client_with_devices(
        monkeypatch, "List of devices attached\ns\tdevice\n"
    )
    client = cls(serial="s")
    assert client.wm_size() == (1920, 1080)


def test_adb_client_connect_called(monkeypatch):
    calls = []
    def fake(cmd, timeout=10, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr("device.adb_client.subprocess.run", fake)
    monkeypatch.setattr("device.adb_client.shutil.which", lambda x: "adb")
    monkeypatch.setattr(
        "device.adb_client.parse_devices",
        lambda text: ["127.0.0.1:7555"],
    )
    client = AdbClient(connect="127.0.0.1:7555", serial="127.0.0.1:7555")
    assert any("connect" in c for c in calls)
    assert client._serial == "127.0.0.1:7555"


def test_adb_client_returncode_error_raises(monkeypatch):
    """adb 回傳非零(returncode!=0)應拋 DeviceError。"""
    cls, _ = _client_with_devices(monkeypatch, "List of devices attached\ns\tdevice\n")
    client = cls(serial="s")

    def fail(cmd, timeout=10, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="device offline")

    monkeypatch.setattr("device.adb_client.subprocess.run", fail)
    with pytest.raises(DeviceError):
        client.tap(1, 2)


def test_adb_client_timeout_raises(monkeypatch):
    """adb 命令逾時應拋 DeviceError。"""
    cls, _ = _client_with_devices(monkeypatch, "List of devices attached\ns\tdevice\n")
    client = cls(serial="s")

    def slow(cmd, timeout=10, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr("device.adb_client.subprocess.run", slow)
    with pytest.raises(DeviceError):
        client.tap(1, 2)


def _png_bytes_of(shape=(720, 1280, 3)):
    """產生一張固定位元 PNG bytes,供 capture 測試。"""
    import cv2
    img = (np.zeros(shape, dtype=np.uint8) + 7)  # 非零灰階
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _adb_device(monkeypatch, wm="Physical size: 1280x720"):
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size(wm)
    return AdbDeviceBackend(client), client


def test_adb_device_capture_resizes_to_1080p(monkeypatch):
    dev, client = _adb_device(monkeypatch)
    client.exec_out.return_value = _png_bytes_of((720, 1280, 3))
    img = dev.capture()
    assert img.shape == (1080, 1920, 3)


def test_adb_device_click_scales(monkeypatch):
    dev, client = _adb_device(monkeypatch, "Physical size: 1280x720")
    dev.click(960, 540)
    client.tap.assert_called_once_with(640, 360)


def test_adb_device_swipe_converts_duration_to_ms(monkeypatch):
    dev, client = _adb_device(monkeypatch, "Physical size: 1920x1080")
    dev.swipe(100, 200, 100, 800, duration=0.3)
    client.swipe.assert_called_once_with(100, 200, 100, 800, 300)


def test_adb_device_double_click_two_taps(monkeypatch):
    dev, client = _adb_device(monkeypatch, "Physical size: 1920x1080")
    dev.double_click(960, 540)
    assert client.tap.call_count == 2


def test_adb_device_capture_no_resize_at_1080p(monkeypatch):
    """設備為 1920×1080 時 capture 不應呼叫 resize。"""
    dev, client = _adb_device(monkeypatch, "Physical size: 1920x1080")
    client.exec_out.return_value = _png_bytes_of((1080, 1920, 3))
    spy = MagicMock()
    monkeypatch.setattr("device.adb.cv2.resize", spy)
    img = dev.capture()
    assert img.shape == (1080, 1920, 3)
    spy.assert_not_called()


def test_adb_device_capture_decode_failure_raises(monkeypatch):
    """adb screencap 回傳無效 bytes(imdecode 得 None)應拋 DeviceError。"""
    dev, client = _adb_device(monkeypatch)
    client.exec_out.return_value = b""
    with pytest.raises(DeviceError):
        dev.capture()


def test_adb_device_invalid_resolution_raises(monkeypatch):
    """wm_size 解析出無效解析度(w/h<=0)應在建構時拋 DeviceError。"""
    client = MagicMock()
    client.wm_size.return_value = (0, 0)
    with pytest.raises(DeviceError):
        AdbDeviceBackend(client)


def test_windows_device_click_delegates(monkeypatch):
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt")
    dev.double_click(100, 50)

    assert fake_input.double_click.call_count == 1
    args = fake_input.double_click.call_args[0]
    assert args[0] == 42          # hwnd 透傳
    assert args[1] == 200 and args[2] == 100   # scale_to_client 後座標


def test_windows_device_capture_delegates(monkeypatch):
    expected = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr("device.windows.capture_window", lambda hwnd, m: expected)
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: MagicMock())
    dev = WindowsDeviceBackend(hwnd=1, capture_method="bitblt")
    assert dev.capture() is expected


def test_windows_device_close_calls_close_all(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr("device.windows.close_all", lambda: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: MagicMock())
    WindowsDeviceBackend(hwnd=1).close()
    assert called["n"] == 1


def test_windows_device_swipe_delegates(monkeypatch):
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt")
    dev.swipe(100, 50, 200, 60, duration=0.3)

    fake_input.swipe.assert_called_once()
    args = fake_input.swipe.call_args[0]
    assert args[0] == 42          # hwnd 透傳
    assert args[1] == 200 and args[2] == 100    # (100,50) 縮放後
    assert args[3] == 400 and args[4] == 120    # (200,60) 縮放後
    assert args[5] == 0.3         # duration 透傳
