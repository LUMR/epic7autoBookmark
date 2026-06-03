"""Worker 线程 — 在后台执行商店自动化流程。

修复 Bug #3：使用 stop() 方法优雅停止，替代 worker.terminate()。
terminate() 在 Windows 上调用 TerminateThread，不会执行 finally 块，
导致 GDI 资源泄漏。
"""

from __future__ import annotations

import win32gui

from PyQt6 import QtCore

from automation.flow import ShopFlow
from automation.state import ShopContext, ShopState
from automation.templates import TemplateManager
from capture import REF_WIDTH, REF_HEIGHT
from config import AppConfig
from detection.matcher import TemplateMatcher
from input import create_backend
from logger import ShopLogger


def find_game_window(window_title: str) -> int | None:
    """查找游戏窗口句柄。

    Args:
        window_title: 窗口标题关键字。

    Returns:
        窗口句柄 (HWND)，未找到返回 None。
    """
    candidates: list[tuple[int, int]] = []

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


class Worker(QtCore.QThread):
    """后台工作线程，执行商店自动化。"""

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
        self._running = False
        self._ctx: ShopContext | None = None

    def setVariable(self, startMode: int, expectNum: int, moneyNum: int, stoneNum: int) -> None:
        self.startMode = startMode
        self.expectNum = expectNum
        self.moneyNum = moneyNum
        self.stoneNum = stoneNum

    def stop(self) -> None:
        """请求优雅停止。

        替代原 worker.terminate()，避免 GDI 资源泄漏 (Bug #3)。
        """
        self._running = False
        if self._ctx is not None:
            self._ctx.stop()

    def run(self) -> None:
        self.isStart.emit()

        try:
            # 加载配置
            config = AppConfig.load()

            # 创建日志器
            logger = ShopLogger(self.emitLog)

            # 查找游戏窗口
            hwnd = find_game_window(config.window_title)
            if not hwnd:
                logger.error("錯誤: 找不到遊戲視窗")
                raise RuntimeError("game window not found")

            # 创建上下文
            ctx = ShopContext(
                hwnd=hwnd,
                mode=self.startMode,
                expect_num=self.expectNum,
                money=self.moneyNum,
                stone=self.stoneNum,
            )
            self._ctx = ctx
            self._running = True

            # 初始化组件
            templates = TemplateManager(config.language)
            matcher = TemplateMatcher()
            input_backend = create_backend(config.input_backend)

            # 创建并执行流程
            flow = ShopFlow(ctx, templates, matcher, input_backend, logger, config)

            # 连接状态变化的 Signal 回调
            original_money = ctx.money
            original_stone = ctx.stone

            result = flow.run()

            # 更新 UI 显示的最终数值
            self.emitMoney.emit(str(result.money))
            self.emitStone.emit(str(result.stone))

            self.isFinish.emit()

        except Exception as e:
            self.emitLog.emit(f"錯誤: {e}")
            self.isError.emit()
        finally:
            self._ctx = None
            self._running = False
