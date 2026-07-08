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
from config import AppConfig
from detection.matcher import TemplateMatcher
from device import create_device, DeviceError
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
        self.humanize_enabled = True   # 預設與 AppConfig.humanize_enabled 一致
        self._running = False
        self._ctx: ShopContext | None = None

    def setVariable(
        self,
        startMode: int,
        expectNum: int,
        moneyNum: int,
        stoneNum: int,
        humanize_enabled: bool,
    ) -> None:
        self.startMode = startMode
        self.expectNum = expectNum
        self.moneyNum = moneyNum
        self.stoneNum = stoneNum
        self.humanize_enabled = humanize_enabled

    def _prepare_config(self) -> AppConfig:
        """載入 config 並套用 GUI 的人性化開關。

        在 create_device 之前覆蓋 config.humanize_enabled,使 flow(讀 config)
        與 device(factory 從 config 組裝 HumanizeSettings)同時生效。
        """
        config = AppConfig.load()
        config.humanize_enabled = self.humanize_enabled
        return config

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
            # 加载配置(GUI 人性化開關在此套用)
            config = self._prepare_config()

            # 创建日志器
            logger = ShopLogger(self.emitLog)

            # 建立設備(Windows:查找視窗;ADB:連線/選設備)
            try:
                device = create_device(config)
            except DeviceError as e:
                logger.error(f"錯誤: {e}")
                raise

            # 创建上下文
            ctx = ShopContext(
                device=device,
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

            # 创建并执行流程
            flow = ShopFlow(ctx, templates, matcher, device, logger, config)

            result = flow.run()

            # 更新 UI 显示的最终数值
            self.emitMoney.emit(str(result.money))
            self.emitStone.emit(str(result.stone))

            self.isFinish.emit()

        except Exception as e:
            self.emitLog.emit(f"錯誤: {e}")
            self.isError.emit()
        finally:
            if self._ctx is not None and self._ctx.device is not None:
                self._ctx.device.close()
            self._ctx = None
            self._running = False
