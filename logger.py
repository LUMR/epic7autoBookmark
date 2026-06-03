"""日志模块 — 双流日志：文件 + Qt Signal。

日志同时写入：
1. 时间戳文件 (logs/run_YYYYMMDD_HHMMSS.log)
2. Qt Signal（用于 GUI 显示）
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


class ShopLogger:
    """商店自动化日志器。

    同时输出到 Python logging（文件 + 控制台）和可选的 Qt Signal。
    """

    def __init__(self, log_signal=None, log_dir: str = "logs"):
        self._qt_signal = log_signal
        self._logger = logging.getLogger("epic7")
        self._logger.setLevel(logging.DEBUG)

        # 避免重复添加 handler
        if not self._logger.handlers:
            self._setup_file_handler(log_dir)
            self._setup_console_handler()

    def _setup_file_handler(self, log_dir: str) -> None:
        """创建带时间戳的文件日志。"""
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(
            log_path / f"run_{timestamp}.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        self._logger.addHandler(file_handler)

    def _setup_console_handler(self) -> None:
        """创建控制台日志。"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(console_handler)

    def _log(self, level: int, msg: str, emit_to_qt: bool = True) -> None:
        """统一日志输出。"""
        self._logger.log(level, msg)
        if emit_to_qt and self._qt_signal:
            self._qt_signal.emit(msg)

    def info(self, msg: str) -> None:
        """记录 INFO 级别日志。"""
        self._log(logging.INFO, msg)

    def error(self, msg: str) -> None:
        """记录 ERROR 级别日志。"""
        self._log(logging.ERROR, msg)

    def debug(self, msg: str) -> None:
        """记录 DEBUG 级别日志（仅写入文件，不发送到 GUI）。"""
        self._log(logging.DEBUG, msg, emit_to_qt=False)
