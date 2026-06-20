"""device 層測試 — 純函數解析/縮放 + factory + 後端委派。"""
import numpy as np
import pytest

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
