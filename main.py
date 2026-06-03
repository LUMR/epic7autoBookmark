"""第七史詩刷商店小工具 — 入口。

自动请求管理员权限后启动 PyQt6 GUI。
"""

import ctypes
import sys

# 管理员提权（需要在导入 win32 之前执行）
if not ctypes.windll.shell32.IsUserAnAdmin():
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
