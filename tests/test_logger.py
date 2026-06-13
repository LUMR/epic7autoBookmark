import time
from pathlib import Path
import logging

from logger import ShopLogger


def test_handlers_refreshed_each_run(tmp_path):
    """每次建立 ShopLogger 應重建 handler，寫入新檔案。"""
    log1 = ShopLogger(log_dir=str(tmp_path))
    files_1 = set(Path(tmp_path).glob("*.log"))
    log1.info("first run")

    time.sleep(1.05)  # logger 時間戳精度到秒，確保檔名不同

    log2 = ShopLogger(log_dir=str(tmp_path))
    files_2 = set(Path(tmp_path).glob("*.log"))

    assert files_2 > files_1                              # 新檔案產生
    assert len(logging.getLogger("epic7").handlers) == 2  # file+console，不累積


def test_log_writes_to_latest_file(tmp_path):
    log1 = ShopLogger(log_dir=str(tmp_path))
    log1.info("run1-msg")
    time.sleep(1.05)
    log2 = ShopLogger(log_dir=str(tmp_path))
    log2.info("run2-msg")

    files = sorted(Path(tmp_path).glob("*.log"))
    content = files[-1].read_text(encoding="utf-8")
    assert "run2-msg" in content
    assert "run1-msg" not in content  # 第二次只寫自己的檔案
