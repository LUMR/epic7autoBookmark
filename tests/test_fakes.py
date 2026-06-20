"""FakeDevice 替身行為自測。"""
import numpy as np

from tests.fakes import FakeDevice


def test_fake_device_default_capture_shape():
    dev = FakeDevice()
    assert dev.capture().shape == (1080, 1920, 3)


def test_fake_device_records_clicks():
    dev = FakeDevice()
    dev.double_click(100, 200)
    dev.click(50, 60)
    assert dev.calls == [("double_click", 100, 200), ("click", 50, 60)]


def test_fake_device_set_image():
    dev = FakeDevice()
    img = np.ones((1080, 1920, 3), dtype=np.uint8) * 5
    dev.set_image(img)
    assert dev.capture() is img


def test_fake_device_swipe_recorded():
    dev = FakeDevice()
    dev.swipe(10, 20, 30, 40, duration=0.5)
    assert dev.calls == [("swipe", 10, 20, 30, 40, 0.5)]
