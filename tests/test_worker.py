"""Worker 測試 — 驗證人性化開關從 setVariable 正確傳到 config。"""
from PyQt6 import QtWidgets

from config import AppConfig
from worker import Worker

# 首個觸碰 Qt 的測試:確保 QThread 可實例化(不啟動事件循環)。
_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_prepare_config_overrides_humanize(monkeypatch):
    """setVariable 傳入的 humanize_enabled 必須覆蓋 AppConfig.load() 的值。"""
    base = AppConfig._from_dict({"humanize_enabled": True})
    monkeypatch.setattr(AppConfig, "load", lambda: base)

    w = Worker()
    w.setVariable(
        startMode=3, expectNum=99, moneyNum=1000, stoneNum=30000,
        humanize_enabled=False,
    )

    cfg = w._prepare_config()
    assert cfg.humanize_enabled is False
    # 其他欄位維持 load 結果,不受覆蓋影響
    assert cfg.platform == "windows"


def test_prepare_config_default_humanize_true(monkeypatch):
    """未呼叫 setVariable 時,_prepare_config 使用 __init__ 預設(True)。"""
    base = AppConfig._from_dict({"humanize_enabled": False})
    monkeypatch.setattr(AppConfig, "load", lambda: base)

    w = Worker()  # 不呼叫 setVariable
    cfg = w._prepare_config()
    assert cfg.humanize_enabled is True
