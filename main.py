from PyQt6 import QtCore, QtGui, QtWidgets
from numpy import asarray
import aircv
import cv2
import json
import ctypes
import time

# DPI awareness for accurate coordinates
ctypes.windll.user32.SetProcessDPIAware()

import win32gui
import win32api
import win32ui
import win32con

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
e7_language = config["e7_language"]
window_title = config.get("window_title", "Epic Seven")
foreground_mode = config.get("foreground_mode", False)
default_money = str(config.get("default_money", 0))
default_stone = str(config.get("default_stone", 0))
default_covenant = str(config.get("default_covenant", 0))
default_mystic = str(config.get("default_mystic", 0))
default_stone_usage = str(config.get("default_stone_usage", 0))

# Windows API constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
MK_LBUTTON = 0x0001
PW_RENDERFULLCONTENT = 2
user32 = ctypes.windll.user32


def make_lparam(x, y):
    return (y << 16) | (x & 0xFFFF)


def find_game_window():
    candidates = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and window_title in win32gui.GetWindowText(hwnd):
            rect = win32gui.GetClientRect(hwnd)
            area = rect[2] * rect[3]
            candidates.append((area, hwnd))
    win32gui.EnumWindows(callback, None)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


MAX_RETRY = 20
REF_WIDTH = 1920
REF_HEIGHT = 1080


def capture_window(hwnd):
    client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
    client_rect = win32gui.GetClientRect(hwnd)
    client_width = client_rect[2]
    client_height = client_rect[3]

    desktop_dc = win32gui.GetDC(0)
    mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, client_width, client_height)
    save_dc.SelectObject(bitmap)

    try:
        save_dc.BitBlt(
            (0, 0), (client_width, client_height),
            mfc_dc, (client_left, client_top),
            win32con.SRCCOPY
        )

        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        img = asarray(bytearray(bmp_str), dtype="uint8")
        img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))

        img = img[:, :, :3]
        if client_width != REF_WIDTH or client_height != REF_HEIGHT:
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img
    finally:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, desktop_dc)
        win32gui.DeleteObject(bitmap.GetHandle())


def post_click(hwnd, x, y):
    lparam = make_lparam(int(x), int(y))
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.02)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)


def real_click(hwnd, x, y):
    sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
    win32api.SetCursorPos((sx, sy))
    time.sleep(0.02)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx, sy, 0, 0)
    time.sleep(0.02)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx, sy, 0, 0)


def click_at(hwnd, x, y):
    if foreground_mode:
        real_click(hwnd, x, y)
    else:
        post_click(hwnd, x, y)


def double_click_at(hwnd, x, y):
    click_at(hwnd, x, y)
    time.sleep(0.05)
    click_at(hwnd, x, y)


def post_swipe(hwnd, x1, y1, x2, y2, duration=0.1):
    lparam = make_lparam(int(x1), int(y1))
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    steps = 10
    step_delay = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        cx = int(x1 + (x2 - x1) * t)
        cy = int(y1 + (y2 - y1) * t)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, make_lparam(cx, cy))
        time.sleep(step_delay)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, make_lparam(int(x2), int(y2)))


def real_swipe(hwnd, x1, y1, x2, y2, duration=0.1):
    sx1, sy1 = win32gui.ClientToScreen(hwnd, (int(x1), int(y1)))
    sx2, sy2 = win32gui.ClientToScreen(hwnd, (int(x2), int(y2)))
    win32api.SetCursorPos((sx1, sy1))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)
    steps = 10
    step_delay = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        cx = int(sx1 + (sx2 - sx1) * t)
        cy = int(sy1 + (sy2 - sy1) * t)
        win32api.SetCursorPos((cx, cy))
        time.sleep(step_delay)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)


def swipe_at(hwnd, x1, y1, x2, y2, duration=0.1):
    if foreground_mode:
        real_swipe(hwnd, x1, y1, x2, y2, duration)
    else:
        post_swipe(hwnd, x1, y1, x2, y2, duration)


class Worker(QtCore.QThread):
    isStart = QtCore.pyqtSignal()
    isFinish = QtCore.pyqtSignal()
    isError = QtCore.pyqtSignal()
    emitLog = QtCore.pyqtSignal(str)
    emitMoney = QtCore.pyqtSignal(str)
    emitStone = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.startMode = 0
        self.expectNum = 0
        self.moneyNum = 0
        self.stoneNum = 0
        self.autoRestartDispatch = False

    def setVariable(self, startMode, expectNum, moneyNum, stoneNum, autoRestartDispatch):
        self.startMode = startMode
        self.expectNum = expectNum
        self.moneyNum = moneyNum
        self.stoneNum = stoneNum
        self.autoRestartDispatch = autoRestartDispatch

    def _scale(self, hwnd, x, y):
        rect = win32gui.GetClientRect(hwnd)
        return x * rect[2] / REF_WIDTH, y * rect[3] / REF_HEIGHT

    def _check_dispatch(self, hwnd, restartDispatchImg):
        if not self.autoRestartDispatch:
            return
        screenshot = capture_window(hwnd)
        loc = aircv.find_template(screenshot, restartDispatchImg, 0.75)
        if not loc:
            return
        print("dispatch mission completed!")
        self.emitLog.emit("重新進行派遣任務")
        for _ in range(MAX_RETRY):
            pos = loc["result"]
            dx, dy = self._scale(hwnd, pos[0], pos[1])
            double_click_at(hwnd, dx, dy)
            time.sleep(1)
            double_click_at(hwnd, dx, dy)
            time.sleep(1)
            new_screenshot = capture_window(hwnd)
            loc = aircv.find_template(new_screenshot, restartDispatchImg, 0.75)
            if not loc:
                break
        time.sleep(1)

    def run(self):
        self.isStart.emit()
        print("startMode:", self.startMode)
        print("expectedNum:", self.expectNum)

        try:
            self.emitLog.emit("===== 初始化 =====")
            time.sleep(1)

            if self.moneyNum < 280000:
                self.emitLog.emit("錯誤: 金幣不足28萬")
                raise ValueError("out of money")

            if self.stoneNum < 3:
                self.emitLog.emit("錯誤: 天空石不足以刷新商店")
                raise ValueError("out of stone")

            if self.startMode == 3 and self.expectNum > self.stoneNum:
                self.emitLog.emit("錯誤: 天空石使用數量大於持有數量")
                raise ValueError("stone input error")

            self.emitLog.emit("正在尋找遊戲視窗......")
            time.sleep(1)

            hwnd = find_game_window()
            if not hwnd:
                self.emitLog.emit("錯誤: 找不到遊戲視窗")
                raise RuntimeError("game window not found")

            if foreground_mode:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)

            self.emitLog.emit("遊戲視窗已找到")
            time.sleep(1)

            self.emitLog.emit("初始化完成")
            time.sleep(1)

            self.emitLog.emit("===== 刷商店 =====")
            time.sleep(1)

            refreshTime = 0
            covenantFoundTime = 0
            mysticFoundTime = 0

            covenant = aircv.imread("./img/covenantLocation.png")
            mystic = aircv.imread("./img/mysticLocation.png")
            buyButton = aircv.imread(f"./img/buyButton-{e7_language}.png")
            buyConfirmButton = aircv.imread(f"./img/buyConfirmButton-{e7_language}.png")
            refreshButton = aircv.imread(f"./img/refreshButton-{e7_language}.png")
            refreshYesButton = aircv.imread(f"./img/refreshYesButton-{e7_language}.png")
            restartDispatchButton = aircv.imread(f"./img/restartDispatchButton-{e7_language}.png")

            needRefresh = False
            covenantFound = False
            mysticFound = False

            loopCount = 0
            while self.expectNum > 0 and self.moneyNum > 280000 and self.stoneNum >= 3:
                loopCount += 1
                screenshot = capture_window(hwnd)
                self.emitLog.emit(f"--- 第{loopCount}輪掃描 ---")

                covenantLocation = aircv.find_template(screenshot, covenant, 0.9)
                if covenantLocation and not covenantFound:
                    covenantFound = True
                    self.emitLog.emit(f"找到聖約書籤 位置:({covenantLocation['result'][0]:.0f},{covenantLocation['result'][1]:.0f})")

                    for retry in range(MAX_RETRY):
                        pos = covenantLocation["result"]
                        sx, sy = self._scale(hwnd, pos[0] + 800, pos[1] + 40)
                        self.emitLog.emit(f"點擊聖約商品 ({sx:.0f},{sy:.0f}) 重試:{retry+1}")
                        double_click_at(hwnd, sx, sy)
                        time.sleep(1)

                        self._check_dispatch(hwnd, restartDispatchButton)

                        buy_screenshot = capture_window(hwnd)
                        buyButtonLocation = aircv.find_template(buy_screenshot, buyConfirmButton, 0.85)

                        if buyButtonLocation:
                            buyPos = buyButtonLocation["result"]

                            for retry2 in range(MAX_RETRY):
                                bx, by = self._scale(hwnd, buyPos[0], buyPos[1])
                                self.emitLog.emit(f"點擊購買按鈕 ({bx:.0f},{by:.0f}) 重試:{retry2+1}")
                                double_click_at(hwnd, bx, by)
                                time.sleep(1)
                                self._check_dispatch(hwnd, restartDispatchButton)
                                after_buy = capture_window(hwnd)
                                if not aircv.find_template(after_buy, buyConfirmButton, 0.85):
                                    break
                                time.sleep(1)

                            if self.startMode == 1:
                                self.expectNum -= 1
                                self.emitLog.emit(f"剩餘次數: {self.expectNum}次")

                            self.moneyNum -= 184000
                            covenantFoundTime += 1
                            self.emitMoney.emit(str(self.moneyNum))
                            break
                        self.emitLog.emit("未找到購買按鈕，重試...")
                        time.sleep(1)

                mysticLocation = aircv.find_template(screenshot, mystic, 0.9)
                if mysticLocation and not mysticFound:
                    mysticFound = True
                    self.emitLog.emit(f"找到神秘書籤 位置:({mysticLocation['result'][0]:.0f},{mysticLocation['result'][1]:.0f})")

                    for retry in range(MAX_RETRY):
                        pos = mysticLocation["result"]
                        sx, sy = self._scale(hwnd, pos[0] + 800, pos[1] + 40)
                        self.emitLog.emit(f"點擊神秘商品 ({sx:.0f},{sy:.0f}) 重試:{retry+1}")
                        double_click_at(hwnd, sx, sy)
                        time.sleep(1)

                        self._check_dispatch(hwnd, restartDispatchButton)

                        buy_screenshot = capture_window(hwnd)
                        buyButtonLocation = aircv.find_template(buy_screenshot, buyConfirmButton, 0.85)

                        if buyButtonLocation:
                            buyPos = buyButtonLocation["result"]

                            for retry2 in range(MAX_RETRY):
                                bx, by = self._scale(hwnd, buyPos[0], buyPos[1])
                                self.emitLog.emit(f"點擊購買按鈕 ({bx:.0f},{by:.0f}) 重試:{retry2+1}")
                                double_click_at(hwnd, bx, by)
                                time.sleep(1)
                                self._check_dispatch(hwnd, restartDispatchButton)
                                after_buy = capture_window(hwnd)
                                if not aircv.find_template(after_buy, buyConfirmButton, 0.85):
                                    break
                                time.sleep(1)

                            if self.startMode == 2:
                                self.expectNum -= 1
                                self.emitLog.emit(f"剩餘次數: {self.expectNum}次")

                            self.moneyNum -= 280000
                            mysticFoundTime += 1
                            self.emitMoney.emit(str(self.moneyNum))
                            break
                        self.emitLog.emit("未找到購買按鈕，重試...")
                        time.sleep(1)

                if needRefresh:
                    refreshButtonLocation = aircv.find_template(screenshot, refreshButton, 0.8)
                    if not refreshButtonLocation:
                        self.emitLog.emit("找不到刷新按鈕，重試中...")
                        time.sleep(2)
                        continue
                    for retry in range(MAX_RETRY):
                        refreshPos = refreshButtonLocation["result"]
                        rx, ry = self._scale(hwnd, refreshPos[0], refreshPos[1])
                        self.emitLog.emit(f"點擊刷新按鈕 ({rx:.0f},{ry:.0f}) 重試:{retry+1}")
                        double_click_at(hwnd, rx, ry)
                        time.sleep(1)

                        self._check_dispatch(hwnd, restartDispatchButton)

                        confirm_screenshot = capture_window(hwnd)
                        refreshYesLoc = aircv.find_template(confirm_screenshot, refreshYesButton, 0.9)

                        if refreshYesLoc:
                            yesPos = refreshYesLoc["result"]

                            for retry2 in range(MAX_RETRY):
                                yx, yy = self._scale(hwnd, yesPos[0], yesPos[1])
                                self.emitLog.emit(f"點擊確認刷新 ({yx:.0f},{yy:.0f}) 重試:{retry2+1}")
                                double_click_at(hwnd, yx, yy)
                                time.sleep(1)
                                self._check_dispatch(hwnd, restartDispatchButton)
                                after_yes = capture_window(hwnd)
                                if not aircv.find_template(after_yes, refreshYesButton, 0.9):
                                    break
                                time.sleep(1)

                            self.stoneNum -= 3
                            self.emitStone.emit(str(self.stoneNum))
                            refreshTime += 1
                            self.emitLog.emit(f"刷新成功，已用{refreshTime * 3}天空石")

                            if self.startMode == 3:
                                self.expectNum -= 3
                                self.emitLog.emit(f"剩餘次數: {int(self.expectNum / 3)}次")

                            needRefresh = False
                            covenantFound = False
                            mysticFound = False

                            time.sleep(1)
                            break
                        self.emitLog.emit("未彈出確認對話框，重試...")
                        time.sleep(1)

                else:
                    self.emitLog.emit("滑動商店列表")
                    sx1, sy1 = self._scale(hwnd, 1400, 500)
                    sx2, sy2 = self._scale(hwnd, 1400, 200)
                    swipe_at(hwnd, sx1, sy1, sx2, sy2, 0.1)
                    needRefresh = True

                    time.sleep(1)
                    self._check_dispatch(hwnd, restartDispatchButton)

            self.emitLog.emit("===== 結算 =====")
            self.emitLog.emit("共花費:")
            self.emitLog.emit(f"天空石: {refreshTime * 3}個")
            self.emitLog.emit(f"金幣: {covenantFoundTime * 184000 + mysticFoundTime * 280000}元")
            self.emitLog.emit("獲得書籤:")
            self.emitLog.emit(f"聖約: {covenantFoundTime}次")
            self.emitLog.emit(f"神秘: {mysticFoundTime}次")

            self.isFinish.emit()

        except Exception as e:
            print(e)
            self.emitLog.emit(f"錯誤: {e}")
            self.isError.emit()


class Ui_Main(object):
    start = False

    def setupUi(self, Main):
        Main.setObjectName("Main")
        Main.resize(310, 460)
        Main.setMinimumSize(QtCore.QSize(310, 500))
        Main.setMaximumSize(QtCore.QSize(310, 500))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        Main.setFont(font)
        self.tabWidget = QtWidgets.QTabWidget(Main)
        self.tabWidget.setGeometry(QtCore.QRect(5, 5, 300, 490))
        self.tabWidget.setMinimumSize(QtCore.QSize(300, 490))
        self.tabWidget.setMaximumSize(QtCore.QSize(300, 490))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.tabWidget.setFont(font)
        self.tabWidget.setStyleSheet("")
        self.tabWidget.setObjectName("tabWidget")
        self.functionTab = QtWidgets.QWidget()
        self.functionTab.setMinimumSize(QtCore.QSize(300, 490))
        self.functionTab.setMaximumSize(QtCore.QSize(300, 490))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.functionTab.setFont(font)
        self.functionTab.setObjectName("functionTab")
        self.covenantInput = QtWidgets.QLineEdit(self.functionTab)
        self.covenantInput.setGeometry(QtCore.QRect(140, 130, 70, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.covenantInput.setFont(font)
        self.covenantInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.covenantInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.covenantInput.setObjectName("covenantInput")
        self.mysticInput = QtWidgets.QLineEdit(self.functionTab)
        self.mysticInput.setGeometry(QtCore.QRect(140, 170, 70, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.mysticInput.setFont(font)
        self.mysticInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.mysticInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.mysticInput.setObjectName("mysticInput")
        self.moneyTextShowLabel = QtWidgets.QLabel(self.functionTab)
        self.moneyTextShowLabel.setGeometry(QtCore.QRect(40, 10, 60, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.moneyTextShowLabel.setFont(font)
        self.moneyTextShowLabel.setObjectName("moneyTextShowLabel")
        self.moneyTotalShowEdit = QtWidgets.QLineEdit(self.functionTab)
        self.moneyTotalShowEdit.setGeometry(QtCore.QRect(120, 10, 111, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.moneyTotalShowEdit.setFont(font)
        self.moneyTotalShowEdit.setLayoutDirection(
            QtCore.Qt.LayoutDirection.RightToLeft
        )
        self.moneyTotalShowEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.moneyTotalShowEdit.setObjectName("moneyTotalShowEdit")
        self.divider = QtWidgets.QFrame(self.functionTab)
        self.divider.setGeometry(QtCore.QRect(10, 60, 271, 20))
        self.divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.divider.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.divider.setObjectName("divider")
        self.stoneTextShowLabel = QtWidgets.QLabel(self.functionTab)
        self.stoneTextShowLabel.setGeometry(QtCore.QRect(40, 40, 60, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.stoneTextShowLabel.setFont(font)
        self.stoneTextShowLabel.setObjectName("stoneTextShowLabel")
        self.stoneTotalShowEdit = QtWidgets.QLineEdit(self.functionTab)
        self.stoneTotalShowEdit.setGeometry(QtCore.QRect(119, 40, 111, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.stoneTotalShowEdit.setFont(font)
        self.stoneTotalShowEdit.setLayoutDirection(
            QtCore.Qt.LayoutDirection.RightToLeft
        )
        self.stoneTotalShowEdit.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.stoneTotalShowEdit.setObjectName("stoneTotalShowEdit")
        self.startButton = QtWidgets.QPushButton(self.functionTab)
        self.startButton.setGeometry(QtCore.QRect(140, 400, 100, 40))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.startButton.setFont(font)
        self.startButton.setStyleSheet("")
        self.startButton.setDefault(False)
        self.startButton.setFlat(False)
        self.startButton.setObjectName("startButton")
        self.startButton.clicked.connect(self.startPressEvent)
        self.covenantTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.covenantTimeLabel.setGeometry(QtCore.QRect(220, 130, 20, 20))
        self.covenantTimeLabel.setObjectName("covenantTimeLabel")
        self.mysticTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.mysticTimeLabel.setGeometry(QtCore.QRect(220, 170, 20, 20))
        self.mysticTimeLabel.setObjectName("mysticTimeLabel")
        self.logTextBrowser = QtWidgets.QTextBrowser(self.functionTab)
        self.logTextBrowser.setGeometry(QtCore.QRect(40, 250, 200, 131))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.logTextBrowser.setFont(font)
        self.logTextBrowser.setObjectName("logTextBrowser")
        self.stoneTimeLabel = QtWidgets.QLabel(self.functionTab)
        self.stoneTimeLabel.setGeometry(QtCore.QRect(220, 210, 20, 20))
        self.stoneTimeLabel.setObjectName("stoneTimeLabel")
        self.stoneInput = QtWidgets.QLineEdit(self.functionTab)
        self.stoneInput.setGeometry(QtCore.QRect(140, 210, 70, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.stoneInput.setFont(font)
        self.stoneInput.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)
        self.stoneInput.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
            | QtCore.Qt.AlignmentFlag.AlignTrailing
            | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.stoneInput.setObjectName("stoneInput")
        self.autoRestartDispatchCheckbox = QtWidgets.QCheckBox(self.functionTab)
        self.autoRestartDispatchCheckbox.setGeometry(QtCore.QRect(40, 90, 150, 21))
        self.autoRestartDispatchCheckbox.setObjectName("autoRestartDispatchCheckbox")
        self.autoRestartDispatchCheckbox.setChecked(False)
        self.covenantRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.covenantRadioButton.setGeometry(QtCore.QRect(40, 130, 91, 21))
        self.covenantRadioButton.setChecked(True)
        self.covenantRadioButton.setObjectName("covenantRadioButton")
        self.mysticRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.mysticRadioButton.setGeometry(QtCore.QRect(40, 170, 91, 21))
        self.mysticRadioButton.setObjectName("mysticRadioButton")
        self.stoneRadioButton = QtWidgets.QRadioButton(self.functionTab)
        self.stoneRadioButton.setGeometry(QtCore.QRect(40, 210, 91, 21))
        self.stoneRadioButton.setObjectName("stoneRadioButton")
        self.tabWidget.addTab(self.functionTab, "")
        self.introductionTab = QtWidgets.QWidget()
        self.introductionTab.setMinimumSize(QtCore.QSize(300, 450))
        self.introductionTab.setMaximumSize(QtCore.QSize(300, 450))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.introductionTab.setFont(font)
        self.introductionTab.setObjectName("introductionTab")
        self.textBrowser = QtWidgets.QTextBrowser(self.introductionTab)
        self.textBrowser.setGeometry(QtCore.QRect(20, 200, 256, 192))
        self.textBrowser.setObjectName("textBrowser")
        self.githubText = QtWidgets.QLabel(self.introductionTab)
        self.githubText.setGeometry(QtCore.QRect(20, 20, 61, 20))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(12)
        self.githubText.setFont(font)
        self.githubText.setObjectName("githubText")
        self.githubTextUrl = QtWidgets.QLabel(self.introductionTab)
        self.githubTextUrl.setGeometry(QtCore.QRect(20, 40, 251, 41))
        font = QtGui.QFont()
        font.setFamily("微軟正黑體")
        font.setPointSize(11)
        self.githubTextUrl.setFont(font)
        self.githubTextUrl.setScaledContents(False)
        self.githubTextUrl.setWordWrap(True)
        self.githubTextUrl.setOpenExternalLinks(True)
        self.githubTextUrl.setObjectName("githubTextUrl")
        self.tabWidget.addTab(self.introductionTab, "")

        self.worker = Worker()
        self.worker.isStart.connect(self.startWorker)
        self.worker.isFinish.connect(self.stopWorker)
        self.worker.isError.connect(self.errorWorker)

        self.worker.emitLog.connect(lambda text: self.logTextBrowser.append(text))
        self.worker.emitMoney.connect(
            lambda text: self.moneyTotalShowEdit.setText(text)
        )
        self.worker.emitStone.connect(
            lambda text: self.stoneTotalShowEdit.setText(text)
        )

        self.retranslateUi(Main)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Main)

    def retranslateUi(self, Main):
        _translate = QtCore.QCoreApplication.translate
        Main.setWindowTitle(_translate("Main", "第七史詩刷商店小工具"))
        self.covenantInput.setText(_translate("Main", default_covenant))
        self.mysticInput.setText(_translate("Main", default_mystic))
        self.moneyTextShowLabel.setText(_translate("Main", "金幣"))
        self.moneyTotalShowEdit.setText(_translate("Main", default_money))
        self.stoneTextShowLabel.setText(_translate("Main", "天空石"))
        self.stoneTotalShowEdit.setText(_translate("Main", default_stone))
        self.startButton.setText(_translate("Main", "開始"))
        self.covenantTimeLabel.setText(_translate("Main", "次"))
        self.mysticTimeLabel.setText(_translate("Main", "次"))
        self.logTextBrowser.setHtml(
            _translate(
                "Main",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "</style></head><body style=\" font-family:'微軟正黑體'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">毫無反應, 就是個小工具</p></body></html>',
            )
        )
        self.stoneTimeLabel.setText(_translate("Main", "個"))
        self.stoneInput.setText(_translate("Main", default_stone_usage))
        self.autoRestartDispatchCheckbox.setText(_translate("Main", "自動重新派遣"))
        self.covenantRadioButton.setText(_translate("Main", "聖約書籤"))
        self.mysticRadioButton.setText(_translate("Main", "神秘書籤"))
        self.stoneRadioButton.setText(_translate("Main", "天空石"))
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.functionTab), _translate("Main", "功能")
        )
        self.textBrowser.setHtml(
            _translate(
                "Main",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "</style></head><body style=\" font-family:'微軟正黑體'; font-size:12pt; font-weight:400; font-style:normal;\">\n"
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">啟動條件:</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">金幣至少280000元</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">天空石至少3個</p>\n'
                '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">填的數字為停止的條件，</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">刷到的神秘與聖約都會買，</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">目前沒有只買某種的功能，</p>\n'
                '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">未來也不會做。</p></body></html>',
            )
        )
        self.githubText.setText(_translate("Main", "GitHub:"))
        self.githubTextUrl.setText(
            _translate(
                "Main",
                '<a href="https://www.github.com/steven010116/epic7autoBookmark">https://www.github.com/steven010116/epic7autoBookmark</a>',
            )
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.introductionTab), _translate("Main", "簡介")
        )

    def startPressEvent(self):
        self.start = not self.start

        if self.start:
            startMode = 0
            expectNum = 0
            moneyNum = (
                int(self.moneyTotalShowEdit.text())
                if self.moneyTotalShowEdit.text().isdigit()
                else 0
            )
            stoneNum = (
                int(self.stoneTotalShowEdit.text())
                if self.stoneTotalShowEdit.text().isdigit()
                else 0
            )
            autoRestartDispatch = self.autoRestartDispatchCheckbox.isChecked()

            if moneyNum == 0 or stoneNum == 0:
                self.logTextBrowser.setText("")
                self.logTextBrowser.append("石頭或金幣輸入錯誤")
                self.logTextBrowser.append("===== 停止 =====")
                self.start = not self.start
                self.startProperty(False)
                return

            if self.covenantRadioButton.isChecked():
                startMode = 1
                covenant = self.covenantInput.text()
                expectNum = int(covenant) if covenant.isdigit() else 0
                self.covenantInput.setText(str(expectNum))

            elif self.mysticRadioButton.isChecked():
                startMode = 2
                mystic = self.mysticInput.text()
                expectNum = int(mystic) if mystic.isdigit() else 0
                self.mysticInput.setText(str(expectNum))

            elif self.stoneRadioButton.isChecked():
                startMode = 3
                stone = self.stoneInput.text()
                expectNum = int(stone) if stone.isdigit() else 0
                self.stoneInput.setText(str(expectNum))

            else:
                self.logTextBrowser.append("沒有選取的radioButton,")
                self.logTextBrowser.append("明明就預設會選一個,")
                self.logTextBrowser.append("你是怎麼取消掉的? 能不能教我?")
                self.logTextBrowser.append("===== 停止 =====")
                self.start = not self.start
                self.startProperty(False)
                return

            self.worker.setVariable(startMode, expectNum, moneyNum, stoneNum, autoRestartDispatch)
            self.worker.start()
        else:
            self.worker.terminate()
            self.logTextBrowser.append("===== 停止 =====")
            self.startProperty(False)

    def startProperty(self, isDisabled: bool):
        if isDisabled:
            self.startButton.setText("停止")
        else:
            self.startButton.setText("開始")

        self.covenantRadioButton.setDisabled(isDisabled)
        self.mysticRadioButton.setDisabled(isDisabled)
        self.stoneRadioButton.setDisabled(isDisabled)
        self.moneyTotalShowEdit.setDisabled(isDisabled)
        self.stoneTotalShowEdit.setDisabled(isDisabled)
        self.covenantInput.setDisabled(isDisabled)
        self.mysticInput.setDisabled(isDisabled)
        self.stoneInput.setDisabled(isDisabled)
        self.autoRestartDispatchCheckbox.setDisabled(isDisabled)

    def startWorker(self):
        self.logTextBrowser.setText("")
        self.startProperty(True)

    def errorWorker(self):
        self.start = False
        self.startProperty(False)

    def stopWorker(self):
        self.start = False
        self.startProperty(False)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon("main.ico"))

    Main = QtWidgets.QWidget()
    ui = Ui_Main()
    ui.setupUi(Main)
    Main.show()
    sys.exit(app.exec())
