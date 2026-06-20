"""第七史詩刷商店小工具 — 入口。

僅 Windows 原生模式(SendInput)需要管理員權限;ADB 模式為使用者級,跳過提權。
提權在導入 win32 之前執行,故以純 json 讀 config.json 判斷 platform(不依賴 pywin32)。
"""

import ctypes
import json
import sys
from pathlib import Path


def _needs_admin() -> bool:
    """僅 Windows 原生模式需管理員;讀取失敗時保守提權。"""
    try:
        if Path("config.json").exists():
            raw = json.loads(Path("config.json").read_text(encoding="utf-8"))
            return raw.get("platform", "windows") == "windows"
    except Exception:
        pass
    return True


if _needs_admin() and not ctypes.windll.shell32.IsUserAnAdmin():
    params = ' '.join([f'"{a}"' if ' ' in a else a for a in sys.argv])
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    sys.exit(0)

from PyQt6 import QtGui, QtWidgets

from gui import Ui_Main

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon("main.ico"))

    Main = QtWidgets.QWidget()
    ui = Ui_Main()
    ui.setupUi(Main)
    Main.show()
    sys.exit(app.exec())
