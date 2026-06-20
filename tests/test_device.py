"""device 層測試 — 純函數解析/縮放 + factory + 後端委派。"""
import subprocess

import pytest

from device.adb_client import AdbClient
from device.base import (
    DeviceError,
    parse_wm_size,
    parse_devices,
    scale_ref_to_device,
    select_serial,
)


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
