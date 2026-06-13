from config import AppConfig


def test_default_roi_is_none():
    cfg = AppConfig._from_dict({})
    assert cfg.scan_roi is None
    assert cfg.button_roi is None


def test_roi_from_dict():
    raw = {"scan_roi": [100, 200, 800, 600], "button_roi": [300, 400, 500, 200]}
    cfg = AppConfig._from_dict(raw)
    assert cfg.scan_roi == [100, 200, 800, 600]
    assert cfg.button_roi == [300, 400, 500, 200]


def test_roi_tuple_property():
    cfg = AppConfig._from_dict({"scan_roi": [10, 20, 30, 40]})
    assert cfg.scan_roi_tuple == (10, 20, 30, 40)
    assert AppConfig._from_dict({}).scan_roi_tuple is None


def test_button_roi_tuple_property():
    cfg = AppConfig._from_dict({"button_roi": [1, 2, 3, 4]})
    assert cfg.button_roi_tuple == (1, 2, 3, 4)
    assert AppConfig._from_dict({}).button_roi_tuple is None
