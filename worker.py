"""Worker 线程 — 在后台执行商店自动化流程。

修复 Bug #3：使用 stop() 方法优雅停止，替代 worker.terminate()。
terminate() 在 Windows 上调用 TerminateThread，不会执行 finally 块，
导致 GDI 资源泄漏。
"""

from __future__ import annotations

from PyQt6 import QtCore

from automation.flow import ShopFlow
from automation.state import ShopContext, ShopState
from automation.templates import TemplateManager
from capture import REF_WIDTH, REF_HEIGHT
from capture.bitblt import close_all
from config import AppConfig
from detection.matcher import TemplateMatcher
from device.windows import find_game_window
from input import create_backend
from logger import ShopLogger


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
                capture_method=config.capture_method,
            )
            self._ctx = ctx
            self._running = True

            # 初始化组件
            templates = TemplateManager(config.language)
            matcher = TemplateMatcher()
            input_backend = create_backend(config.input_backend)

            # 创建并执行流程
            flow = ShopFlow(ctx, templates, matcher, input_backend, logger, config)

            result = flow.run()

            # 更新 UI 显示的最终数值
            self.emitMoney.emit(str(result.money))
            self.emitStone.emit(str(result.stone))

            self.isFinish.emit()

        except Exception as e:
            self.emitLog.emit(f"錯誤: {e}")
            self.isError.emit()
        finally:
            close_all()
            self._ctx = None
            self._running = False
