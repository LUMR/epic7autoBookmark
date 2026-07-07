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


def test_default_platform_is_windows():
    cfg = AppConfig._from_dict({})
    assert cfg.platform == "windows"


def test_platform_from_dict():
    cfg = AppConfig._from_dict({"platform": "adb"})
    assert cfg.platform == "adb"


def test_adb_fields_default_none():
    cfg = AppConfig._from_dict({})
    assert cfg.adb_path is None
    assert cfg.adb_serial is None
    assert cfg.adb_connect is None
    assert cfg.adb_screenshot_method == "screencap"


def test_adb_fields_from_dict():
    raw = {
        "adb_path": "C:/tools/adb.exe",
        "adb_serial": "127.0.0.1:7555",
        "adb_connect": "127.0.0.1:7555",
        "adb_screenshot_method": "screencap",
    }
    cfg = AppConfig._from_dict(raw)
    assert cfg.adb_path == "C:/tools/adb.exe"
    assert cfg.adb_serial == "127.0.0.1:7555"
    assert cfg.adb_connect == "127.0.0.1:7555"
    assert cfg.adb_screenshot_method == "screencap"


def test_validate_rejects_bad_platform():
    cfg = AppConfig._from_dict({"platform": "ios"})
    assert any("平台" in w for w in cfg.validate())


def test_validate_accepts_adb():
    cfg = AppConfig._from_dict({"platform": "adb"})
    assert not any("平台" in w for w in cfg.validate())


def test_validate_rejects_bad_adb_screenshot_method():
    cfg = AppConfig._from_dict({"adb_screenshot_method": "minicap"})
    assert any("ADB 截图方式" in w for w in cfg.validate())


def test_humanize_defaults():
    cfg = AppConfig._from_dict({})
    assert cfg.humanize_enabled is True
    assert cfg.humanize_jitter_px == 8
    assert cfg.humanize_swipe_jitter_px == 20
    assert cfg.humanize_double_click_spread == 0.03
    assert cfg.humanize_swipe_duration_spread == 0.04
    assert cfg.humanize_curve_strength == 0.3
    assert cfg.humanize_move_steps == 12
    assert cfg.humanize_pause_chance == 0.12
    assert cfg.humanize_pause_duration == 1.5
    assert cfg.humanize_pause_spread == 1.0


def test_humanize_from_dict():
    raw = {
        "humanize_enabled": False,
        "humanize_jitter_px": 15,
        "humanize_pause_chance": 0.25,
    }
    cfg = AppConfig._from_dict(raw)
    assert cfg.humanize_enabled is False
    assert cfg.humanize_jitter_px == 15
    assert cfg.humanize_pause_chance == 0.25


def test_old_config_without_humanize_uses_defaults():
    """舊 config.json(無 humanize_*)載入用預設值,不報錯。"""
    raw = {"e7_language": "zh-TW", "default_money": 1000}
    cfg = AppConfig._from_dict(raw)
    assert cfg.humanize_enabled is True
    assert cfg.humanize_jitter_px == 8
