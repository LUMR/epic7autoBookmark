# 商店自動化工具優化實施計劃

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復 3 個真實 Bug + 讓配置真正生效 + 集中常量 + 抽象重複流程 + ROI/GDI 效率改進，並引入 pytest 為純邏輯層建立測試保障。

**Architecture:** 分層推進——先建測試基礎設施與常量層（無依賴），再改狀態/配置/日誌等純邏輯層（可單測），然後重構 flow 核心流程，最後處理 IO/GUI 層（手動驗證）。每個任務獨立可提交。

**Tech Stack:** Python 3.9+、PyQt6、OpenCV、pywin32、pytest（新增）

---

## 設計決策（已與使用者確認）

1. **引入 pytest**（dev 依賴）：為 `matcher / config / state / logger / coords / constants` 等純邏輯層寫單元測試。IO 層（capture / input / worker / gui）靠手動驗證。
2. **ROI 可配置、預設全圖**：`config.json` 加 `scan_roi` / `button_roi`（`[x,y,w,h]`），預設 `null`（全圖，行為不變）。matcher 已支援 `roi` 參數，flow 串接起來。另提供 ROI 框選輔助腳本。
3. **GDI 復用**：bitblt 改為模塊級按 `hwnd` 緩存可復用會話，尺寸變化時重建。
4. **行為改進（非 bug，會在任務中標注）**：`_handle_buying` 內層購買確認逾時從「死磕外層重試」改為「回掃描」，避免空轉。

## 檔案結構

| 檔案 | 動作 | 職責 |
|------|------|------|
| `constants.py` | 新建 | 集中遊戲數值與座標常量 |
| `pyproject.toml` | 新建 | pytest 配置 |
| `tests/__init__.py` | 新建 | 測試包 |
| `tests/conftest.py` | 新建 | 共享 fixture |
| `tests/test_*.py` | 新建 | 純邏輯層單元測試 |
| `tools/roi_helper.py` | 新建 | ROI 框選輔助腳本 |
| `config.py` | 修改 | 加 ROI 配置項 + tuple property |
| `automation/state.py` | 修改 | capture_method 欄位 + 金幣閾值按模式 + 用常量 |
| `automation/flow.py` | 修改 | 常量引用 + short_sleep 實例化 + method/timeout 傳遞 + 抽象 click_until + ROI |
| `worker.py` | 修改 | 傳 capture_method + 結束時 close_all |
| `logger.py` | 修改 | 修復 handler 重複 |
| `input/base.py` | 修改 | scale_coords 純函數化 + import 提頂 |
| `capture/bitblt.py` | 修改 | GDI 會話復用 |
| `gui.py` | 修改 | wait 校驗 + start 守衛 |
| `requirements.txt` | 修改 | 加 pytest |

---

## Task 1: 測試基礎設施 + constants.py（P1 #8）

**Files:**
- Create: `pyproject.toml`
- Create: `constants.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_constants.py`

- [ ] **Step 1: 新建 pytest 配置**（避免收集根目錄過時的 `test_*.py`）

`pyproject.toml`：
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-q"
```

- [ ] **Step 2: 新建 constants.py**

```python
"""全域常量 — 集中管理遊戲數值與座標，避免 magic numbers 散落。

所有座標基於 1920×1080 參考解析度（見 capture.REF_WIDTH/REF_HEIGHT）。
"""

from __future__ import annotations

# ---- 書籤價格（金幣）----
COVENANT_COST: int = 184000
MYSTIC_COST: int = 280000

# ---- 刷新消耗 ----
REFRESH_STONE_COST: int = 3

# ---- 商品點擊偏移（書籤匹配中心 → 商品按鈕，參考解析度）----
BUY_CLICK_OFFSET_X: int = 800
BUY_CLICK_OFFSET_Y: int = 40

# ---- 商店列表滑動（參考解析度座標）----
SWIPE_START_REF: tuple[int, int] = (1400, 500)
SWIPE_END_REF: tuple[int, int] = (1400, 200)
SWIPE_DURATION: float = 0.1

# ---- 畫面變化判定閾值 ----
SWIPE_CHANGED_DIFF: float = 5.0
STABLE_DIFF_THRESHOLD: float = 10.0
STABLE_BEFORE_DIFF_THRESHOLD: float = 15.0


def min_money_for_mode(mode: int) -> int:
    """根據模式回傳繼續執行所需的最低金幣。

    Args:
        mode: 1=聖約, 2=神秘, 3=天空石（兩種都可能買）。
    """
    if mode == 1:
        return COVENANT_COST
    return MYSTIC_COST  # mode 2/3 都可能買神秘書籤
```

- [ ] **Step 3: 新建 tests/__init__.py 與 conftest.py**

`tests/conftest.py`：
```python
"""pytest 共享 fixture。"""
import sys
from pathlib import Path

# 讓測試能 import 專案根目錄的模組
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`tests/__init__.py`：（空檔案）

- [ ] **Step 4: 寫測試（先行）**

`tests/test_constants.py`：
```python
from constants import (
    COVENANT_COST, MYSTIC_COST, REFRESH_STONE_COST,
    BUY_CLICK_OFFSET_X, BUY_CLICK_OFFSET_Y,
    SWIPE_START_REF, SWIPE_END_REF,
    min_money_for_mode,
)


def test_bookmark_costs():
    assert COVENANT_COST == 184000
    assert MYSTIC_COST == 280000
    assert REFRESH_STONE_COST == 3


def test_buy_click_offset():
    assert (BUY_CLICK_OFFSET_X, BUY_CLICK_OFFSET_Y) == (800, 40)


def test_swipe_coords():
    assert SWIPE_START_REF == (1400, 500)
    assert SWIPE_END_REF == (1400, 200)


def test_min_money_for_mode():
    assert min_money_for_mode(1) == 184000
    assert min_money_for_mode(2) == 280000
    assert min_money_for_mode(3) == 280000
```

- [ ] **Step 5: 安裝 pytest 並執行**

Run: `pip install pytest && pytest tests/test_constants.py -v`
Expected: PASS（4 個測試全綠）

- [ ] **Step 6: 更新 requirements.txt**

在 `requirements.txt` 末尾加：
```
pytest>=7.0.0
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml constants.py tests/ requirements.txt
git commit -m "feat: 引入 pytest 測試基礎設施 + constants 集中常量"
```

---

## Task 2: config.py 加 ROI 配置項（P2 #4 基礎）

**Files:**
- Modify: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 寫測試（先行）**

`tests/test_config.py`：
```python
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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_config.py -v`
Expected: FAIL（`scan_roi` 屬性不存在）

- [ ] **Step 3: 修改 config.py — 在「檢測閾值」區塊後新增欄位**

在 `match_threshold_refresh` 之後加入：
```python
    # ---- ROI 搜尋區域（可選加速，參考解析度 [x, y, w, h]，None=全圖）----
    scan_roi: list[int] | None = None       # 書籤掃描區域
    button_roi: list[int] | None = None     # 按鈕搜尋區域
```

並新增 property（放在 `ui_defaults` property 之後）：
```python
    @property
    def scan_roi_tuple(self) -> tuple[int, int, int, int] | None:
        """書籤掃描 ROI，轉為 matcher 需要的 tuple。"""
        return tuple(self.scan_roi) if self.scan_roi else None

    @property
    def button_roi_tuple(self) -> tuple[int, int, int, int] | None:
        """按鈕搜尋 ROI，轉為 matcher 需要的 tuple。"""
        return tuple(self.button_roi) if self.button_roi else None
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config 新增可配置 ROI 項（預設全圖）"
```

---

## Task 3: logger.py 修復 handler 重複（P0 #2）

**Bug：** `logging.getLogger("epic7")` 為模塊級單例，`if not handlers` 防重複 → 第二次「開始」時 handler 未刷新，日誌寫入第一次的檔案。

**Files:**
- Modify: `logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: 寫測試（先行）**

`tests/test_logger.py`：
```python
from pathlib import Path
import logging
from logger import ShopLogger


def test_handlers_refreshed_each_run(tmp_path):
    """每次建立 ShopLogger 應重建 handler，寫入新檔案。"""
    log1 = ShopLogger(log_dir=str(tmp_path))
    files_1 = set(Path(tmp_path).glob("*.log"))
    log1.info("first run")

    log2 = ShopLogger(log_dir=str(tmp_path))
    files_2 = set(Path(tmp_path).glob("*.log"))

    assert files_2 > files_1                     # 新檔案產生
    assert len(logging.getLogger("epic7").handlers) == 2  # file+console，不累積


def test_log_writes_to_latest_file(tmp_path):
    log1 = ShopLogger(log_dir=str(tmp_path))
    log1.info("run1-msg")
    log2 = ShopLogger(log_dir=str(tmp_path))
    log2.info("run2-msg")

    files = sorted(Path(tmp_path).glob("*.log"))
    content = files[-1].read_text(encoding="utf-8")
    assert "run2-msg" in content
    assert "run1-msg" not in content             # 第二次只寫自己的檔案
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_logger.py -v`
Expected: FAIL（第二次未產生新檔案 / handler 累積）

- [ ] **Step 3: 修改 logger.py `__init__`**

將 `__init__` 改為：
```python
    def __init__(self, log_signal=None, log_dir: str = "logs"):
        self._qt_signal = log_signal
        self._logger = logging.getLogger("epic7")
        self._logger.setLevel(logging.DEBUG)

        # 每次實例化都重建 handler，確保新 run 寫入新檔案（修復 handler 復用 bug）
        self._clear_handlers()
        self._setup_file_handler(log_dir)
        self._setup_console_handler()

    @staticmethod
    def _clear_handlers() -> None:
        """清空並關閉舊 handler，避免日誌寫入上一次執行的檔案。"""
        logger = logging.getLogger("epic7")
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
```
（原本的 `if not self._logger.handlers:` 判斷整段刪除）

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_logger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add logger.py tests/test_logger.py
git commit -m "fix: logger 每次執行重建 handler，修復日誌寫入舊檔案"
```

---

## Task 4: input/base.py scale_coords 純函數化（P3 #9）

**問題：** `scale_coords` 函數內 `import win32gui`（每次呼叫執行）；職責是座標變換但塞在 InputBackend 基類。

**Files:**
- Modify: `input/base.py`
- Create: `tests/test_coords.py`

- [ ] **Step 1: 寫測試（先行）**

`tests/test_coords.py`：
```python
from input import base


def test_scale_identity(monkeypatch):
    monkeypatch.setattr(base.win32gui, "GetClientRect", lambda hwnd: (0, 0, 1920, 1080))
    assert base.scale_to_client(0, 960, 540) == (960.0, 540.0)


def test_scale_half_window(monkeypatch):
    # 實際視窗 960×540（參考一半），座標等比縮放
    monkeypatch.setattr(base.win32gui, "GetClientRect", lambda hwnd: (0, 0, 960, 540))
    assert base.scale_to_client(0, 1920, 1080) == (1920.0, 540.0)
    assert base.scale_to_client(0, 960, 540) == (960.0, 270.0)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_coords.py -v`
Expected: FAIL（`scale_to_client` 不存在）

- [ ] **Step 3: 改寫 input/base.py**

完整新檔：
```python
"""輸入後端抽象基類。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import win32gui

from capture import REF_WIDTH, REF_HEIGHT


def scale_to_client(hwnd: int, ref_x: float, ref_y: float) -> tuple[float, float]:
    """將參考解析度座標轉為視窗客戶區像素座標（純函數）。"""
    rect = win32gui.GetClientRect(hwnd)
    actual_x = ref_x * rect[2] / REF_WIDTH
    actual_y = ref_y * rect[3] / REF_HEIGHT
    return actual_x, actual_y


class InputBackend(ABC):
    """滑鼠輸入後端的抽象介面。所有座標均為視窗客戶區座標（像素）。"""

    @abstractmethod
    def click(self, hwnd: int, x: float, y: float) -> None: ...

    @abstractmethod
    def double_click(self, hwnd: int, x: float, y: float) -> None: ...

    @abstractmethod
    def swipe(
        self, hwnd: int, x1: float, y1: float,
        x2: float, y2: float, duration: float = 0.1,
    ) -> None: ...

    def scale_coords(
        self, hwnd: int, ref_x: float, ref_y: float
    ) -> tuple[float, float]:
        """將參考解析度座標轉為實際座標（委託純函數）。"""
        return scale_to_client(hwnd, ref_x, ref_y)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_coords.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add input/base.py tests/test_coords.py
git commit -m "refactor: scale_coords 抽為純函數 scale_to_client + import 提頂"
```

---

## Task 5: state.py 加 capture_method + 金幣閾值按模式（P0 #1 部分 / P3 #6）

**Files:**
- Modify: `automation/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: 寫測試（先行）**

`tests/test_state.py`：
```python
from automation.state import ShopContext


def _ctx(mode=1, money=10**8, stone=100, expect_num=5, **kw):
    return ShopContext(hwnd=1, mode=mode, expect_num=expect_num,
                       money=money, stone=stone, **kw)


def test_should_continue_ok():
    assert _ctx().should_continue is True


def test_should_continue_mode1_money():
    assert _ctx(mode=1, money=184000).should_continue is False
    assert _ctx(mode=1, money=184001).should_continue is True


def test_should_continue_mode2_money():
    assert _ctx(mode=2, money=280000).should_continue is False
    assert _ctx(mode=2, money=280001).should_continue is True


def test_should_continue_mode3_budget():
    assert _ctx(mode=3, expect_num=3).should_continue is True
    assert _ctx(mode=3, expect_num=2).should_continue is False


def test_should_continue_stone_for_refresh():
    # 聖約模式：天空石 <3 無法刷新 → 停止
    assert _ctx(mode=1, stone=2).should_continue is False


def test_total_money_used():
    c = _ctx()
    c.covenant_bought = 2
    c.mystic_bought = 1
    assert c.total_money_used == 2 * 184000 + 1 * 280000


def test_total_stone_used():
    c = _ctx()
    c.refresh_count = 4
    assert c.total_stone_used == 12


def test_capture_method_default():
    assert _ctx().capture_method == "auto"
    assert _ctx(capture_method="mss").capture_method == "mss"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_state.py -v`
Expected: FAIL（`capture_method` 不存在；金幣閾值用固定 280000）

- [ ] **Step 3: 修改 automation/state.py**

頂部 import 加：
```python
from constants import COVENANT_COST, MYSTIC_COST, min_money_for_mode
```

`ShopContext` 在 `stone: int` 之後新增欄位：
```python
    stone: int
    capture_method: str = "auto"   # 截圖方式（auto/bitblt/mss）
```

`should_continue` 改金幣判斷：
```python
        if self.money <= min_money_for_mode(self.mode):
            return False
```

`total_money_used` 改用常量：
```python
    @property
    def total_money_used(self) -> int:
        return self.covenant_bought * COVENANT_COST + self.mystic_bought * MYSTIC_COST
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add automation/state.py tests/test_state.py
git commit -m "feat: state 新增 capture_method + 金幣閾值按模式 + 用常量"
```

---

## Task 6: capture/bitblt.py GDI 會話復用（P3 #10）

> 此任務涉及真實 GDI，無法單元測試，靠手動驗證 + 效能腳本。

**Files:**
- Modify: `capture/bitblt.py`

- [ ] **Step 1: 改寫 capture/bitblt.py（完整新檔）**

```python
"""BitBlt 截圖後端 — GDI 會話復用版本。

模塊級按 hwnd 緩存可復用會話，避免每次截圖重建 DC/Bitmap；
視窗尺寸變化時自動重建。程序退出或任務結束時呼叫 close_all() 釋放。
"""

from __future__ import annotations

import win32gui
import win32ui
import win32con
import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT, CaptureError


class _ReusableCapture:
    """可復用的 GDI 截圖會話。"""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._desktop_dc = None
        self._mfc_dc = None
        self._save_dc = None
        self._bitmap = None
        self._w = 0
        self._h = 0
        self._client_left = 0
        self._client_top = 0

    def _ensure(self) -> None:
        """確認 DC/Bitmap 就緒；尺寸變化時重建。"""
        client_left, client_top = win32gui.ClientToScreen(self.hwnd, (0, 0))
        rect = win32gui.GetClientRect(self.hwnd)
        w, h = rect[2], rect[3]
        if self._bitmap is not None and self._w == w and self._h == h:
            self._client_left = client_left
            self._client_top = client_top
            return
        self._close()
        self._client_left, self._client_top = client_left, client_top
        self._w, self._h = w, h
        self._desktop_dc = win32gui.GetDC(0)
        self._mfc_dc = win32ui.CreateDCFromHandle(self._desktop_dc)
        self._save_dc = self._mfc_dc.CreateCompatibleDC()
        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(self._mfc_dc, w, h)
        self._save_dc.SelectObject(self._bitmap)

    def grab(self) -> np.ndarray:
        self._ensure()
        try:
            self._save_dc.BitBlt(
                (0, 0), (self._w, self._h),
                self._mfc_dc, (self._client_left, self._client_top),
                win32con.SRCCOPY,
            )
            bmp_str = self._bitmap.GetBitmapBits(True)
            info = self._bitmap.GetInfo()
            img = np.asarray(bytearray(bmp_str), dtype="uint8")
            img = img.reshape((info["bmHeight"], info["bmWidth"], 4))[:, :, :3]
            if self._w != REF_WIDTH or self._h != REF_HEIGHT:
                img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
            return img
        except Exception as e:
            raise CaptureError(f"BitBlt 失敗: {e}") from e

    def _close(self) -> None:
        for closer in (
            lambda: self._save_dc and self._save_dc.DeleteDC(),
            lambda: self._mfc_dc and self._mfc_dc.DeleteDC(),
            lambda: self._desktop_dc and win32gui.ReleaseDC(0, self._desktop_dc),
            lambda: self._bitmap and win32gui.DeleteObject(self._bitmap.GetHandle()),
        ):
            try:
                closer()
            except Exception:
                pass
        self._save_dc = self._mfc_dc = self._desktop_dc = self._bitmap = None
        self._w = self._h = 0


# 模塊級會話快取
_sessions: dict[int, _ReusableCapture] = {}


def capture_bitblt(hwnd: int) -> np.ndarray:
    """使用 BitBlt 截取視窗客戶區（會話復用）。"""
    sess = _sessions.get(hwnd)
    if sess is None:
        sess = _ReusableCapture(hwnd)
        _sessions[hwnd] = sess
    try:
        return sess.grab()
    except CaptureError:
        # 失敗時丟棄會話，下次重建
        sess._close()
        _sessions.pop(hwnd, None)
        raise


def close_all() -> None:
    """釋放所有快取的 GDI 會話。"""
    for sess in list(_sessions.values()):
        sess._close()
    _sessions.clear()
```

- [ ] **Step 2: 手動驗證**

開啟遊戲視窗，執行臨時腳本驗證連續截圖返回正確尺寸：
```python
import time
from worker import find_game_window
from capture.bitblt import capture_bitblt, close_all
hwnd = find_game_window("第七史诗")
for _ in range(5):
    img = capture_bitblt(hwnd)
    print(img.shape)   # 應為 (1080, 1920, 3)
    time.sleep(0.1)
close_all()
```
Expected: 5 次列印 `(1080, 1920, 3)`，無例外。

- [ ] **Step 3: Commit**

```bash
git add capture/bitblt.py
git commit -m "perf: bitblt GDI 會話復用，減少重複建立 DC/Bitmap"
```

---

## Task 7: worker.py 傳 capture_method + close_all（P0 #1）

**Files:**
- Modify: `worker.py`

- [ ] **Step 1: 修改 worker.py**

import 區加：
```python
from capture.bitblt import close_all
```

`run()` 中建立 ctx 處加入 `capture_method`：
```python
            ctx = ShopContext(
                hwnd=hwnd,
                mode=self.startMode,
                expect_num=self.expectNum,
                money=self.moneyNum,
                stone=self.stoneNum,
                capture_method=config.capture_method,
            )
```

`finally` 區加 `close_all()`：
```python
        finally:
            close_all()
            self._ctx = None
            self._running = False
```

- [ ] **Step 2: 手動驗證**

啟動 GUI，將 `config.json` 設 `"capture_method": "bitblt"`，執行一次掃描流程，確認流程正常且未回退 MSS（日誌無 MSS 相關錯誤）。

- [ ] **Step 3: Commit**

```bash
git add worker.py
git commit -m "fix: worker 傳入 capture_method 使配置生效 + 結束釋放 GDI 會話"
```

---

## Task 8: matcher ROI 行為測試（P2 #4 基礎）

> matcher 已支援 roi 參數，此任務補測試保障行為，為 flow 串接做準備。

**Files:**
- Create: `tests/test_matcher.py`

- [ ] **Step 1: 寫測試**

`tests/test_matcher.py`：
```python
import numpy as np
from detection.matcher import TemplateMatcher


def _img(h, w, val=0):
    return np.full((h, w, 3), val, dtype=np.uint8)


def test_match_found_full_image():
    img = _img(100, 100, 0)
    tpl = _img(20, 20, 0)
    m = TemplateMatcher().match(img, tpl, 0.9, "t")
    assert m is not None and m.score >= 0.9


def test_match_roi_excludes_target():
    img = _img(100, 100, 0)
    img[80:90, 80:90] = 255
    tpl = img[80:90, 80:90].copy()
    assert TemplateMatcher().match(img, tpl, 0.9, "t", roi=(0, 0, 50, 50)) is None
    assert TemplateMatcher().match(img, tpl, 0.9, "t") is not None


def test_match_roi_offset_in_center():
    img = _img(100, 100, 0)
    img[60:70, 60:70] = 255
    tpl = img[60:70, 60:70].copy()
    m = TemplateMatcher().match(img, tpl, 0.9, "t", roi=(50, 50, 50, 50))
    assert m is not None
    cx, cy = m.center
    assert 60 <= cx <= 70 and 60 <= cy <= 70
```

- [ ] **Step 2: 執行確認通過**

Run: `pytest tests/test_matcher.py -v`
Expected: PASS（若 ROI offset 測試失敗，回頭檢查 matcher box 計算）

- [ ] **Step 3: Commit**

```bash
git add tests/test_matcher.py
git commit -m "test: 補 matcher ROI 行為測試"
```

---

## Task 9: flow.py 重構（P1 #5 / P2 #7 / P2 #4）

> 本任務一次性重構 flow.py：常量引用、short_sleep 實例化、capture_method/timeout 傳遞、抽象 `_click_until_found`/`_click_until_gone`、ROI 串接。改動大，改完後用整合測試（Task 10）保障。

**Files:**
- Modify: `automation/flow.py`

- [ ] **Step 1: 改寫 flow.py（完整新檔）**

```python
"""商店自動化主流程 — 狀態驅動的 ShopFlow。"""

from __future__ import annotations

import random
import time

import cv2
import numpy as np
import win32gui

from capture import capture_window
from config import AppConfig
from detection.matcher import TemplateMatcher
from input.base import InputBackend
from automation.state import ShopContext, ShopState, BookmarkTarget
from automation.templates import TemplateManager
from logger import ShopLogger
from constants import (
    COVENANT_COST, MYSTIC_COST, REFRESH_STONE_COST,
    BUY_CLICK_OFFSET_X, BUY_CLICK_OFFSET_Y,
    SWIPE_START_REF, SWIPE_END_REF, SWIPE_DURATION, SWIPE_CHANGED_DIFF,
)


def wait_for(ctx, matcher, template, threshold, name="", timeout=5.0, interval=0.3, roi=None):
    """輪詢等待模板出現。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return None
        time.sleep(interval)
        img = capture_window(ctx.hwnd, ctx.capture_method)
        result = matcher.match(img, template, threshold, name, roi=roi)
        if result is not None:
            return result
    return None


def wait_for_gone(ctx, matcher, template, threshold, name="", timeout=5.0, interval=0.3, roi=None):
    """輪詢等待模板消失。回傳 True=已消失，False=逾時。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ctx._running:
            return True
        time.sleep(interval)
        img = capture_window(ctx.hwnd, ctx.capture_method)
        if matcher.match(img, template, threshold, name, roi=roi) is None:
            return True
    return False


def wait_for_stable(ctx, before_img=None, timeout=15.0, interval=0.5,
                    threshold=10.0, before_threshold=15.0):
    """等待畫面停止變化（載入動畫結束）。"""
    deadline = time.time() + timeout
    prev = capture_window(ctx.hwnd, ctx.capture_method)
    while time.time() < deadline:
        if not ctx._running:
            return False
        time.sleep(interval)
        curr = capture_window(ctx.hwnd, ctx.capture_method)
        if cv2.absdiff(prev, curr).mean() < threshold:
            if before_img is not None and cv2.absdiff(before_img, curr).mean() < before_threshold:
                prev = curr
                continue
            return True
        prev = curr
    return False


class ShopFlow:
    """狀態驅動的商店自動化流程。"""

    def __init__(self, ctx, templates, matcher, input_backend, logger, config):
        self.ctx = ctx
        self.templates = templates
        self.matcher = matcher
        self.input = input_backend
        self.log = logger
        self.config = config

        self._tpl_covenant = templates.covenant
        self._tpl_mystic = templates.mystic
        self._tpl_buy_confirm = templates.buy_confirm
        self._tpl_refresh = templates.refresh_button
        self._tpl_refresh_yes = templates.refresh_yes

    # ---- 時延 ----

    def short_sleep(self, multiplier: float = 1.0) -> None:
        """帶隨機抖動的延遲，時長 = config.short_sleep_base * multiplier + 抖動。"""
        time.sleep(self.config.short_sleep_base * multiplier + random.uniform(-0.2, 0.3))

    # ---- 點擊輔助（抽象重複流程）----

    def _click_until_found(self, ref_pos, tpl, threshold, name, max_retry=None):
        """點擊 ref_pos 直到 tpl 出現。回傳 MatchResult 或 None（重試耗盡）。"""
        max_retry = max_retry if max_retry is not None else self.config.max_retry
        cx, cy = self.input.scale_coords(self.ctx.hwnd, *ref_pos)
        for i in range(max_retry):
            if not self.ctx._running:
                return None
            self.short_sleep(0.5)
            self.log.debug(f"點擊{name} ({cx:.0f},{cy:.0f}) 重試:{i+1}")
            self.input.double_click(self.ctx.hwnd, cx, cy)
            result = wait_for(self.ctx, self.matcher, tpl, threshold, name,
                              timeout=self.config.wait_timeout,
                              roi=self.config.button_roi_tuple)
            if result is not None:
                return result
            self.log.info(f"未找到{name}，重試...")
            self.short_sleep(1.0)
        return None

    def _click_until_gone(self, ref_pos, tpl, threshold, name, timeout=None):
        """點擊 ref_pos 直到 tpl 消失。回傳 True=消失，False=重試耗盡。"""
        timeout = timeout if timeout is not None else self.config.wait_timeout
        cx, cy = self.input.scale_coords(self.ctx.hwnd, *ref_pos)
        for i in range(self.config.max_retry):
            if not self.ctx._running:
                return True
            self.short_sleep(0.3)
            self.log.debug(f"點擊{name} ({cx:.0f},{cy:.0f}) 重試:{i+1}")
            self.input.double_click(self.ctx.hwnd, cx, cy)
            if wait_for_gone(self.ctx, self.matcher, tpl, threshold, name,
                             timeout=timeout, roi=self.config.button_roi_tuple):
                return True
        return False

    # ---- 主循環 ----

    def run(self) -> ShopContext:
        self._init()
        while self.ctx.should_continue:
            state = self.ctx.state
            if state == ShopState.SCANNING:
                self._handle_scanning()
            elif state in (ShopState.BUYING_COVENANT, ShopState.BUYING_MYSTIC):
                self._handle_buying()
            elif state == ShopState.SWIPING:
                self._handle_swiping()
            elif state == ShopState.REFRESHING:
                self._handle_refreshing()
            elif state in (ShopState.DONE, ShopState.ERROR):
                break
        self._finish()
        return self.ctx

    # ---- 初始化 ----

    def _init(self) -> None:
        self.log.info("===== 初始化 =====")
        self.short_sleep(0.5)
        if self.ctx.money < _min_money(self.ctx.mode):
            self.log.error("錯誤: 金幣不足")
            raise ValueError("out of money")
        if self.ctx.stone < REFRESH_STONE_COST:
            self.log.error("錯誤: 天空石不足以刷新商店")
            raise ValueError("out of stone")
        if self.ctx.mode == 3 and self.ctx.expect_num > self.ctx.stone:
            self.log.error("錯誤: 天空石使用數量大於持有數量")
            raise ValueError("stone input error")
        self.log.info("正在尋找遊戲視窗......")
        self.short_sleep(0.5)
        try:
            win32gui.SetForegroundWindow(self.ctx.hwnd)
        except Exception:
            pass
        self.short_sleep(0.5)
        self.log.info("遊戲視窗已找到")
        self.short_sleep(0.5)
        self.log.info("初始化完成")
        self.short_sleep(0.5)
        self.log.info("===== 刷商店 =====")
        self.short_sleep(0.5)

    # ---- SCANNING ----

    def _handle_scanning(self) -> None:
        if self.ctx.need_refresh:
            self.ctx.state = ShopState.REFRESHING
            return

        screenshot = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        scan_roi = self.config.scan_roi_tuple

        if not self.ctx.covenant_found:
            loc = self.matcher.match(screenshot, self._tpl_covenant,
                                     self.config.match_threshold_location, "covenant", roi=scan_roi)
            if loc is not None:
                cx, cy = loc.center
                self.log.info(f"找到聖約書籤 位置:({cx},{cy})")
                self.ctx.target = BookmarkTarget(match_center=(cx, cy), label="聖約")
                self.ctx.state = ShopState.BUYING_COVENANT
                return

        if not self.ctx.mystic_found:
            loc = self.matcher.match(screenshot, self._tpl_mystic,
                                     self.config.match_threshold_location, "mystic", roi=scan_roi)
            if loc is not None:
                mx, my = loc.center
                self.log.info(f"找到神秘書籤 位置:({mx},{my})")
                self.ctx.target = BookmarkTarget(match_center=(mx, my), label="神秘")
                self.ctx.state = ShopState.BUYING_MYSTIC
                return

        self.ctx.state = ShopState.SWIPING

    # ---- BUYING ----

    def _handle_buying(self) -> None:
        target = self.ctx.target
        if target is None:
            self.ctx.state = ShopState.SCANNING
            return

        is_covenant = self.ctx.state == ShopState.BUYING_COVENANT
        mode_match = 1 if is_covenant else 2
        cost = COVENANT_COST if is_covenant else MYSTIC_COST

        tx, ty = target.match_center
        click_pos = (tx + BUY_CLICK_OFFSET_X, ty + BUY_CLICK_OFFSET_Y)

        buy_btn = self._click_until_found(
            click_pos, self._tpl_buy_confirm,
            self.config.match_threshold_button, "buy_confirm")
        if buy_btn is None:
            self.log.info(f"{target.label}購買重試耗盡，繼續掃描")
            self.ctx.target = None
            self.ctx.state = ShopState.SCANNING
            return

        # 點購買按鈕直到確認框消失即視為成功
        if self._click_until_gone(buy_btn.center, self._tpl_buy_confirm,
                                  self.config.match_threshold_button, "buy_confirm"):
            if self.ctx.mode == mode_match:
                self.ctx.expect_num -= 1
                self.log.info(f"剩餘次數: {self.ctx.expect_num}次")
            self.ctx.money -= cost
            if is_covenant:
                self.ctx.covenant_bought += 1
                self.ctx.covenant_found = True
            else:
                self.ctx.mystic_bought += 1
                self.ctx.mystic_found = True
        else:
            self.log.info("購買確認逾時，繼續掃描")
            # 行為改進：逾時不再死磕外層重試，直接回掃描

        self.ctx.target = None
        self.ctx.state = ShopState.SCANNING

    # ---- SWIPING ----

    def _handle_swiping(self) -> None:
        self.log.info("滑動商店列表")
        self.short_sleep(0.3)
        before = capture_window(self.ctx.hwnd, self.ctx.capture_method)

        sx1, sy1 = self.input.scale_coords(self.ctx.hwnd, *SWIPE_START_REF)
        sx2, sy2 = self.input.scale_coords(self.ctx.hwnd, *SWIPE_END_REF)
        self.input.swipe(self.ctx.hwnd, sx1, sy1, sx2, sy2, SWIPE_DURATION)
        self.ctx.need_refresh = True
        self.short_sleep(1.0)

        after = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        changed = cv2.absdiff(before, after).mean() > SWIPE_CHANGED_DIFF
        if not changed:
            self.ctx.swipe_fail_count += 1
            limit = self.config.swipe_fail_limit
            self.log.info(f"滑動未生效 ({self.ctx.swipe_fail_count}/{limit})")
            if self.ctx.swipe_fail_count >= limit:
                self.log.error("連續滑動失敗過多，停止")
                raise RuntimeError("swipe failed repeatedly")
        else:
            self.ctx.swipe_fail_count = 0
        self.ctx.state = ShopState.SCANNING

    # ---- REFRESHING ----

    def _handle_refreshing(self) -> None:
        screenshot = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        refresh_loc = self.matcher.match(
            screenshot, self._tpl_refresh,
            self.config.match_threshold_refresh, "refresh",
            roi=self.config.button_roi_tuple)
        if refresh_loc is None:
            self.log.info("找不到刷新按鈕，重新滑動...")
            self.ctx.covenant_found = False
            self.ctx.mystic_found = False
            self.ctx.need_refresh = False
            self.short_sleep(1.0)
            self.ctx.state = ShopState.SCANNING
            return

        before_refresh = capture_window(self.ctx.hwnd, self.ctx.capture_method)
        rx, ry = refresh_loc.center

        for retry in range(self.config.max_retry):
            if not self.ctx._running:
                return
            self.short_sleep(0.5)
            srx, sry = self.input.scale_coords(self.ctx.hwnd, rx, ry)
            self.log.debug(f"點擊刷新按鈕 ({srx:.0f},{sry:.0f}) 重試:{retry+1}")
            self.input.double_click(self.ctx.hwnd, srx, sry)

            yes_btn = wait_for(self.ctx, self.matcher, self._tpl_refresh_yes,
                               self.config.match_threshold_confirm, "refresh_yes",
                               roi=self.config.button_roi_tuple)
            if yes_btn is None:
                self.log.info("未彈出確認對話框，重試...")
                self.short_sleep(1.0)
                continue

            if self._click_until_gone(yes_btn.center, self._tpl_refresh_yes,
                                      self.config.match_threshold_confirm, "refresh_yes",
                                      timeout=self.config.wait_timeout_long):
                if wait_for_stable(self.ctx, before_refresh):
                    self.ctx.stone -= REFRESH_STONE_COST
                    self.ctx.refresh_count += 1
                    self.log.info(f"刷新成功，已用{self.ctx.refresh_count * REFRESH_STONE_COST}天空石")
                    if self.ctx.mode == 3:
                        self.ctx.expect_num -= REFRESH_STONE_COST
                        self.log.info(f"剩餘次數: {int(self.ctx.expect_num / REFRESH_STONE_COST)}次")
                    self.ctx.need_refresh = False
                    self.ctx.covenant_found = False
                    self.ctx.mystic_found = False
                    self.short_sleep(1.5)
                    self.ctx.state = ShopState.SCANNING
                    return
                else:
                    self.log.info("商店載入逾時，重試外層...")
            # gone 失敗或載入逾時 → continue 外層

        self.log.info("刷新重試耗盡，繼續掃描")
        self.ctx.state = ShopState.SCANNING

    # ---- 結算 ----

    def _finish(self) -> None:
        self.log.info("===== 結算 =====")
        self.log.info("共花費:")
        self.log.info(f"天空石: {self.ctx.total_stone_used}個")
        self.log.info(f"金幣: {self.ctx.total_money_used}元")
        self.log.info("獲得書籤:")
        self.log.info(f"聖約: {self.ctx.covenant_bought}次")
        self.log.info(f"神秘: {self.ctx.mystic_bought}次")


def _min_money(mode: int) -> int:
    """初始化所需的最低金幣（包裝常量函式，避免循環 import）。"""
    from constants import min_money_for_mode
    return min_money_for_mode(mode)
```

> 註：`_init` 用 `_min_money()` 包裝是為了避免頂部重複 import；實際上可直接頂部 import `min_money_for_mode`。執行時請直接在頂部 import 並用 `min_money_for_mode(self.ctx.mode)`，移除 `_min_money` 包裝。

- [ ] **Step 2: 語法檢查**

Run: `python -c "import ast; ast.parse(open('automation/flow.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 手動驗證（短跑）**

啟動 GUI，設定聖約次數=1，執行到買到一個書籤或刷新一次即手動停止，確認流程正常、日誌顯示座標與計數正確。

- [ ] **Step 4: Commit**

```bash
git add automation/flow.py
git commit -m "refactor: flow 用常量 + short_sleep 實例化 + method/timeout 生效 + 抽象 click_until + ROI 串接"
```

---

## Task 10: flow 整合測試（保障重構）

> 用 mock 注入 capture/matcher/input，驗證核心狀態流轉與計數邏輯未被重構破壞。

**Files:**
- Create: `tests/test_flow.py`

- [ ] **Step 1: 寫整合測試**

`tests/test_flow.py`：
```python
from unittest.mock import MagicMock, patch
import numpy as np

from automation.state import ShopContext, ShopState
from automation.flow import ShopFlow


def _mk_flow(mode=1, expect_num=1, found_covenant=True):
    ctx = ShopContext(hwnd=1, mode=mode, expect_num=expect_num,
                      money=10**8, stone=100)
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.wait_timeout = 0.1
    config.wait_timeout_long = 0.2
    config.max_retry = 2
    config.swipe_fail_limit = 5
    config.short_sleep_base = 0.0          # 測試不要真的睡
    config.scan_roi_tuple = None
    config.button_roi_tuple = None

    templates = MagicMock()
    matcher = MagicMock()
    input_backend = MagicMock()
    input_backend.scale_coords.return_value = (100.0, 100.0)
    logger = MagicMock()
    flow = ShopFlow(ctx, templates, matcher, input_backend, logger, config)
    return flow, ctx, matcher, input_backend


def _match_result(x=500, y=400):
    from detection.matcher import MatchResult
    return MatchResult(name="t", score=0.95, box=(x, y, 10, 10))


def test_buying_covenant_success(mock_capture):
    flow, ctx, matcher, inp = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    # _click_until_found 找到按鈕；_click_until_gone 成功
    matcher.match.side_effect = [_match_result(900, 140)] + [None]
    flow._handle_buying()

    assert ctx.covenant_bought == 1
    assert ctx.covenant_found is True
    assert ctx.expect_num == 1          # mode 1 扣 1
    assert ctx.money == 10**8 - 184000
    assert ctx.state == ShopState.SCANNING


def test_buying_confirm_timeout_returns_to_scan(mock_capture):
    """確認框逾時不再死磕，直接回掃描。"""
    flow, ctx, matcher, inp = _mk_flow(mode=1, expect_num=2)
    ctx.state = ShopState.BUYING_COVENANT
    ctx.target = type("T", (), {"match_center": (100, 100), "label": "聖約"})

    # 找到按鈕，但永遠不消失（gone 失敗）
    matcher.match.side_effect = [_match_result()] * 100
    flow._handle_buying()

    assert ctx.covenant_bought == 0      # 未成功
    assert ctx.state == ShopState.SCANNING


import pytest


@pytest.fixture
def mock_capture(monkeypatch):
    fake = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr("automation.flow.capture_window", lambda *a, **k: fake)
```

> 說明：`mock_capture` fixture 注入全黑截圖；matcher 透過 `side_effect` 控制每次回傳。 `_click_until_gone` 內部呼叫 `wait_for_gone` → 反覆 `matcher.match`，`side_effect` 用盡後會拋 StopIteration，故成功路徑給 `[found, None]`（第二個 None 讓 gone 判定成功）。

- [ ] **Step 2: 執行測試**

Run: `pytest tests/test_flow.py -v`
Expected: PASS（若失敗，依日誌調整 side_effect 序列）

- [ ] **Step 3: Commit**

```bash
git add tests/test_flow.py
git commit -m "test: flow 整合測試保障重構後狀態流轉與計數"
```

---

## Task 11: gui.py wait 校驗 + start 守衛（P0 #3）

**Bug：** `_handle_stop` 忽略 `wait(5000)` 回傳值，逾時後恢復「開始」按鈕，再點會對執行中 QThread 調 `start()` 而崩潰。

**Files:**
- Modify: `gui.py`

- [ ] **Step 1: 修改 gui.py `_handle_stop`**

```python
    def _handle_stop(self) -> None:
        """處理停止按鈕點擊。使用 worker.stop() 替代 terminate()。"""
        self.worker.stop()
        if self.worker.wait(5000):
            self.logTextBrowser.append("===== 停止 =====")
            self.start = False
            self.startProperty(False)
        else:
            # 逾時：線程仍在收尾，保持禁用；線程結束後 isFinish/isError 信號會恢復 UI
            self.logTextBrowser.append("停止逾時，線程仍在收尾，請稍候...")
```

- [ ] **Step 2: 修改 gui.py `_handle_start` 加守衛**

在方法開頭（`startMode = 0` 之前）加入：
```python
    def _handle_start(self) -> None:
        """處理開始按鈕點擊。"""
        if self.worker.isRunning():
            self.logTextBrowser.append("上一次任務仍在收尾，請稍候再試")
            self.start = not self.start   # 還原切換
            return

        startMode = 0
        # ...（其餘不變）
```

- [ ] **Step 3: 手動驗證**

啟動 GUI → 開始 → 立即停止 → 觀察：正常時按鈕恢復「開始」；連續快速點擊開始/停止不會崩潰。

- [ ] **Step 4: Commit**

```bash
git add gui.py
git commit -m "fix: 停止線程校驗 wait 回傳值 + start 守衛防止重入"
```

---

## Task 12: ROI 輔助腳本 + 清理 + 文檔

**Files:**
- Create: `tools/roi_helper.py`
- Modify: `CLAUDE.md`
- Delete: 過時 `test_*.py`（根目錄，引用已移除的 aircv）

- [ ] **Step 1: 新建 ROI 框選輔助腳本**

`tools/roi_helper.py`：
```python
"""ROI 框選輔助 — 截取遊戲視窗後互動式框選，輸出 config.json 用的 [x,y,w,h]。

用法：python tools/roi_helper.py
依賴：opencv（已在 requirements）。框選兩個 ROI（書籤區、按鈕區）後列印結果。
"""
import cv2
from worker import find_game_window
from capture import capture_window
from config import AppConfig

config = AppConfig.load()
hwnd = find_game_window(config.window_title)
if not hwnd:
    raise SystemExit("找不到遊戲視窗")

img = capture_window(hwnd, config.capture_method)
clone = img.copy()
rects = {"scan_roi": [], "button_roi": []}
current = "scan_roi"
drawing = False
ix = iy = 0


def on_mouse(event, x, y, flags, param):
    global drawing, ix, iy, current
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing, ix, iy = True, x, y
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        cv2.imshow("roi", cv2.rectangle(clone.copy(), (ix, iy), (x, y), (0, 255, 0), 2))
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        rects[current] = [min(ix, x), min(iy, y), abs(x - ix), abs(y - iy)]
        print(f'{current} = {rects[current]}')
        current = "button_roi" if current == "scan_roi" else "done"


cv2.namedWindow("roi")
cv2.setMouseCallback("roi", on_mouse)
print("框選【書籤掃描區】→ 再框選【按鈕區】→ 按 q 結束")
while True:
    cv2.imshow("roi", clone)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()
print("\n請將以下加入 config.json：")
print(f'  "scan_roi": {rects["scan_roi"]},')
print(f'  "button_roi": {rects["button_roi"]},')
```

- [ ] **Step 2: 刪除過時的根目錄 test_*.py**

這些腳本仍引用已移除的 `aircv`，無法執行，會誤導。執行：
```bash
git rm test_confidence.py test_refresh.py test_buy.py test_buy_confirm.py \
       test_buy_confirm_confidence.py test_covenant.py test_mystic.py \
       test_printwindow.py test_postmessage.py test_threshold.py
```
（若使用者希望保留，改為 `git mv` 到 `legacy/` 目錄。）

- [ ] **Step 3: 更新 CLAUDE.md**

在「Test Files」段落改為：
```markdown
## Test Files

- `tests/` — pytest 單元/整合測試。執行：`pytest`。
- `tools/roi_helper.py` — 互動式框選商店區域，產出 `config.json` 的 ROI 座標。
```

在「Configuration」關鍵欄位加：
```markdown
- `scan_roi` / `button_roi` — 模板匹配搜尋區域 `[x,y,w,h]`（可選，`null`=全圖）。用 `tools/roi_helper.py` 框選。
```

- [ ] **Step 4: 全量測試**

Run: `pytest -v`
Expected: 全部 PASS（constants/config/logger/coords/state/matcher/flow 測試）

- [ ] **Step 5: Commit**

```bash
git add tools/roi_helper.py CLAUDE.md
git rm test_*.py
git commit -m "chore: ROI 輔助腳本 + 清理過時 test 腳本 + 更新文檔"
```

---

## Self-Review

**1. Spec coverage（對照 P0~P3 分析）：**
- P0 #1 capture_method 失效 → Task 5（state 欄位）+ Task 7（worker 傳遞）+ Task 9（flow 使用）✓
- P0 #2 日誌寫錯檔 → Task 3 ✓
- P0 #3 線程停止校驗 → Task 11 ✓
- P1 #5 時序配置生效 → Task 9（short_sleep 實例化 + wait_timeout 傳遞）✓
- P1 #8 magic numbers 集中 → Task 1（constants）+ Task 5/9 引用 ✓
- P2 #4 ROI 加速 → Task 2（config）+ Task 8（matcher 測試）+ Task 9（flow 串接）+ Task 12（輔助腳本）✓
- P2 #7 抽象重複流程 → Task 9（`_click_until_found`/`_gone`）✓
- P3 #6 金幣閾值按模式 → Task 1（`min_money_for_mode`）+ Task 5（state 使用）✓
- P3 #9 scale_coords → Task 4 ✓
- P3 #10 GDI 復用 → Task 6 ✓

**2. Placeholder scan：** 無 TBD/TODO；Task 9 已標註一處「執行時直接頂部 import」的明確指示，非佔位。

**3. Type consistency：** `scan_roi_tuple`/`button_roi_tuple` 在 config（Task 2）、flow（Task 9）、測試（Task 10）一致；`_click_until_found`/`_click_until_gone` 簽名在定義與呼叫處一致；常量名跨檔一致。

**4. 已知行為改進（非 bug）：** Task 9 `_handle_buying` 確認框逾時改為回掃描（原為死磕外層重試），已標註。
